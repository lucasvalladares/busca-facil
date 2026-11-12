"""
Coletor de preços (celulares e notebooks) em lojas do Paraguai.

    python3 coletor.py                       # TESTE: usa só as cópias em fixtures/ (não acessa nenhum site)
    python3 coletor.py --real                # coleta de verdade, gera as páginas e publica o site
    python3 coletor.py --real --sem-publicar # coleta de verdade, sem publicar
    python3 coletor.py --reprocessar         # refaz a última coleta real a partir das cópias (sem acessar as lojas),
                                             # útil depois de ajustar o produtos.json; grava nos dados reais

Modo de teste (padrão): lê as respostas guardadas em fixtures/, grava num banco
separado (dev/precos-dev.db, cópia do real) e gera as páginas em dev/. Não
publica nada e não mexe nos dados reais.

Modo real (--real): acessa as lojas com o cliente educado (educado.py):
1 pedido a cada 3–5 s por loja, robots.txt respeitado, user-agent honesto,
e a loja PARA ao primeiro erro 403/429/5xx, falha de conexão ou resposta
lenta (> 20 s) — sem nova tentativa no mesmo dia. Cada resposta é guardada
em fixtures/ para os testes.

Fonte usada em cada loja (a mais leve permitida; nunca produto por produto):
  Nissei          API JSON (GraphQL): as buscas em grupos de 6 por pedido + a cotação
  Tecnostore      API JSON da plataforma (WooCommerce), em Gs.
  Tienda Yankee   API JSON da plataforma (WooCommerce), em Gs.
  Tienda Móvil    JSON da busca do site (PrestaShop), em Gs.
  Visuar          JSON das categorias Celulares/iPhone e Celulares/Xiaomi (a busca é proibida no robots.txt)
  Mega            JSON embutido no HTML da busca, em US$
  Alemania Cell   HTML da listagem (categoria Apple + busca), em Gs.
  Bristol         HTML das categorias com filtro de marca (a busca é proibida no robots.txt), em Gs.
  Shopping China  HTML da busca (Gs.) + 1 JSON para a relação Gs./US$ da loja

O que é salvo (tabela "ofertas"): data, loja, nome, modelo normalizado, preço em Gs.,
em estoque (1/0), link. Também: a cotação do dólar (tabela "cambio"), uma foto por
modelo (tabela "fotos"), o resumo de cada execução (tabela "coletas") e as lojas
paradas no dia (tabela "pausas").
"""

import html
import json
import os
import re
import shutil
import sqlite3
import sys
import time
import urllib.error
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from urllib.parse import quote

from cores_principais import e_cor_principal
from educado import Cliente, Dormiu, Parada, SemCopia
from normalizar import CONFIG, normalizar, termos_de_busca

PASTA = os.path.dirname(os.path.abspath(__file__))
BANCO = os.path.join(PASTA, "precos.db")
PASTA_DEV = os.path.join(PASTA, "dev")
ARQUIVO_LOG = os.path.join(PASTA, "coleta.log")
IVA = 0.10
LIMITE_QUEDA = 0.5   # se uma loja trouxer menos da metade dos produtos da última coleta dela: suspeita

# Buscas e categorias vêm do produtos.json; o reconhecimento de nomes (normalizar.py) decide o que entra.
TERMOS = termos_de_busca()
LISTAGENS = CONFIG["listagens_por_loja"]


def log(msg):
    print(msg)
    with open(ARQUIVO_LOG, "a", encoding="utf-8") as f:
        f.write("%s %s\n" % (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg))


def oferta(nome, em_estoque, link, imagem="", gs=None, usd=None):
    """Preço em Gs. (gs) ou em US$ (usd, convertido no fim pela cotação da coleta)."""
    return {"nome": html.unescape(nome).strip(), "gs": gs, "usd": usd,
            "em_estoque": bool(em_estoque), "link": link, "imagem": imagem or ""}


def _reconhecidos(itens):
    return sum(1 for it in itens if normalizar(it["nome"]))


def _paginas(cli, montar_url, ler, limite=20):
    """Folheia uma listagem só enquanto for preciso: para quando a página vem incompleta
    (menos itens que a primeira), sem nada novo, ou sem nenhum produto que monitoramos."""
    itens, vistos, cheia = [], set(), None
    for pagina in range(1, limite + 1):
        try:
            texto = cli.get(montar_url(pagina))
        except urllib.error.HTTPError as e:  # 404 etc.: esta listagem não existe; segue a coleta
            log("   %s: HTTP %d em %s (ignorado)" % (cli.loja, e.code, montar_url(pagina)))
            break
        if texto is None:   # proibido pelo robots.txt
            break
        lote = ler(texto)   # [(chave, oferta)] — oferta None = produto da página que descartamos
        novos = [it for chave, it in lote if chave not in vistos]
        vistos.update(chave for chave, _ in lote)
        uteis = [it for it in novos if it]
        itens += uteis
        cheia = cheia or len(lote)
        if not novos or len(lote) < cheia or _reconhecidos(uteis) == 0:
            break
    return itens


# --------------------------------------------------------------------------
# Lojas. Cada função recebe o cliente educado da loja e devolve (ofertas, cotação ou None).
# --------------------------------------------------------------------------

def coletar_nissei(cli):
    campos = """items { name url_key stock_status image { url }
        price_range { minimum_price { final_price { value currency } } }
        ... on ConfigurableProduct { variants { product { name stock_status image { url }
            price_range { minimum_price { final_price { value currency } } } } } } }"""
    # GraphQL permite várias buscas num pedido (apelidos t0, t1...). A API da Nissei recusa consultas muito
    # complexas (erro 400 com as 20 buscas juntas): vão em grupos de até 6, com a cotação no primeiro.
    POR_PEDIDO = 6
    d, cambio = {}, None
    for inicio in range(0, len(TERMOS), POR_PEDIDO):
        grupo = list(enumerate(TERMOS))[inicio:inicio + POR_PEDIDO]
        consulta = "{ %s %s }" % (" ".join('t%d: products(search: "%s", pageSize: 100) { %s }' % (i, t, campos) for i, t in grupo),
                                  "currency { exchange_rates { currency_to rate } }" if inicio == 0 else "")
        r = cli.get("https://nissei.com/graphql", dados=json.dumps({"query": consulta}),
                    cabecalhos={"Content-Type": "application/json", "Content-Currency": "PYG"})
        if r is None:
            return [], None
        parte = json.loads(r)["data"]
        if "currency" in parte:
            cambio = next((float(x["rate"]) for x in parte.pop("currency")["exchange_rates"]
                           if x["currency_to"] == "PYG" and x["rate"] > 1000), None)
        d.update(parte)
    itens = []
    for i in range(len(TERMOS)):
        for p in d["t%d" % i]["items"]:
            link = "https://nissei.com/py/" + p["url_key"]
            for o in [v["product"] for v in (p.get("variants") or [])] or [p]:
                preco = o["price_range"]["minimum_price"]["final_price"]
                if preco["currency"] != "PYG" or not preco["value"]:
                    continue
                img = ((o.get("image") or p.get("image") or {}).get("url") or "")
                # Nissei mostra o preço com IVA; guardamos o preço exclusivo para estrangeiros (sem IVA)
                itens.append(oferta(o["name"], o["stock_status"] == "IN_STOCK", link,
                                    "" if "placeholder" in img else img, gs=preco["value"] / (1 + IVA)))
    return itens, cambio


def _woocommerce(cli, api):
    def ler(texto):
        lote = []
        for p in json.loads(texto):
            pr = p.get("prices") or {}
            if pr.get("currency_code") == "PYG" and int(pr.get("price") or 0) > 0:
                gs = int(pr["price"]) / (10 ** int(pr.get("currency_minor_unit") or 0))
                lote.append((p["id"], oferta(p["name"], p.get("is_in_stock"), p["permalink"],
                                             ((p.get("images") or [{}])[0]).get("src", ""), gs=gs)))
            else:
                lote.append((p["id"], None))
        return lote
    itens = []
    for t in TERMOS:
        itens += _paginas(cli, lambda pg: api + "?search=%s&per_page=100&page=%d" % (quote(t), pg), ler)
    return itens, None


def coletar_tecnostore(cli):
    return _woocommerce(cli, "https://tecnostore.com.py/v2/wp-json/wc/store/v1/products")


def coletar_yankee(cli):
    return _woocommerce(cli, "https://tiendayankee.com/wp-json/wc/store/v1/products")


def _ler_prestashop(texto):
    lote = []
    for p in json.loads(texto).get("products") or []:
        capa = p.get("cover") or {}
        img = ((capa.get("bySize") or {}).get("large_default") or capa.get("large") or {}).get("url", "")
        if float(p.get("price_amount") or 0) > 0:
            lote.append((p["id_product"], oferta(p["name"], bool(p.get("add_to_cart_url")), p["url"], img,
                                                 gs=float(p["price_amount"]))))
        else:
            lote.append((p["id_product"], None))
    return lote


def coletar_tienda_movil(cli):
    itens = []
    for t in TERMOS:
        itens += _paginas(cli, lambda pg: "https://tiendamovil.com.py/shop/busqueda?controller=search&s=%s&ajax=1"
                                          "&resultsPerPage=100&page=%d" % (quote(t), pg), _ler_prestashop)
    return itens, None


def coletar_visuar(cli):
    # o robots.txt da Visuar proíbe a busca (controller=search) e o parâmetro resultsPerPage: usamos as categorias
    itens = []
    for cat in LISTAGENS["Visuar"]:
        itens += _paginas(cli, lambda pg: "https://visuar.com.py/%s/?ajax=1&page=%d" % (cat, pg),
                          _ler_prestashop)
    return itens, None


def coletar_mega(cli):
    def ler(h):
        lote = []
        for b in re.findall(r'addItemToFavorite\((\{.*?\})\)"', h):
            d = json.loads(html.unescape(b))
            usd, promo = float(d.get("price") or 0), float(d.get("price_promo") or 0)
            if 0 < promo < usd:
                usd = promo
            if usd <= 1:   # a Mega usa US$ 1 para "sem preço"
                lote.append((d["code"], None))
                continue
            idioma = (d.get("product_langs") or [{}])[0]
            lote.append((d["code"], oferta(idioma.get("name", ""), d.get("in_stock"),
                                           "https://www.megaeletronicos.com/producto/%s/%s" % (d["code"], idioma.get("slug", "")),
                                           ("https://resource.megaeletronicos.com" + d["image"]) if d.get("image") else "",
                                           usd=usd)))
        return lote
    itens = []
    for t in TERMOS:
        itens += _paginas(cli, lambda pg: "https://www.megaeletronicos.com/producto/buscar?search=%s&page=%d" % (quote(t), pg), ler)
    return itens, None


def _ler_fenicio(h):
    lote = []
    for cartao in h.split("data-disp='")[1:]:
        cod = re.search(r"data-codProd='([^']+)'", cartao)
        tit = re.search(r'<a class="tit" href="([^"]+)"[^>]*><h2>([^<]+)</h2>', cartao)
        preco = re.search(r'<strong class="precio venta"><span class="sim">(\w+)</span>\s*<span class="monto">([\d.]+)', cartao)
        if cod and not (tit and preco and preco.group(1) == "PYG"):
            lote.append((cod.group(1), None))
        elif cod:
            # foto do produto (pasta /catalogo/); a 1ª imagem do cartão pode ser o logotipo da marca
            img = re.search(r"<img[^>]*src='(//[^']*/catalogo/[^']+)'", cartao)
            if not img:
                img = re.search(r"data-im='(//[^']*/catalogo/[^']+)'", cartao)   # miniatura: pede o tamanho grande
                img = re.match(r"(.*)", img.group(1).replace("/40x40/", "/480x480/")) if img else None
            lote.append((cod.group(1), oferta(tit.group(2), cartao[0] == "1", tit.group(1),
                                              ("https:" + img.group(1)) if img else "",
                                              gs=float(preco.group(2).replace(".", "")))))
    return lote


def _fenicio(cli, listagens):
    """listagens: endereços da 1ª página (com "?"); as seguintes usam &js=1&pag=N."""
    itens = []
    for base in listagens:
        itens += _paginas(cli, lambda pg: base + ("&js=1&pag=%d" % pg if pg > 1 else ""), _ler_fenicio)
    return itens, None


def coletar_alemania(cli):
    return _fenicio(cli, ["https://www.alemaniacell.com/celulares?marca=apple"] +
                    ["https://www.alemaniacell.com/catalogo?q=" + quote(t) for t in TERMOS if t != "iphone"])


def coletar_bristol(cli):
    # o robots.txt da Bristol proíbe a busca e endereços com "?", menos os filtros de marca (?marca=)
    return _fenicio(cli, ["https://www.bristol.com.py/" + caminho for caminho in LISTAGENS["Bristol"]])


def coletar_shopping_china(cli):
    base = "https://www.shoppingchina.com.py"
    amostra = cli.get(base + "/quick_search?search=celular%20apple%20iphone", cabecalhos={"Accept": "application/json"})
    relacoes = sorted(float(p["regular_price_pyg"]) / float(p["regular_price_usd"])
                      for p in json.loads(amostra or "[]") if float(p.get("regular_price_usd") or 0) > 0)
    if not relacoes:
        raise RuntimeError("não deu para descobrir a relação Gs./US$ da loja")
    gs_por_usd = relacoes[len(relacoes) // 2]

    def ler(h):
        lote = []
        for caminho, img, nome, gs in re.findall(
                r'<a href="(/producto/[^"]+)">\s*<div class\s*=\s*"card-container">\s*<img[^>]*?src="([^"]+)".*?'
                r'<span class="lightning-prod-desc[^"]*">\s*([^<]+?)\s*</span>.*?'
                r'lightning-prod-sale[^"]*">\s*Gs\.\s*([\d.]+)', h, re.S):
            # preço "tax free" em US$, como a loja anuncia (múltiplos de 5)
            usd = round(float(gs.replace(".", "")) / gs_por_usd / 5) * 5
            lote.append((caminho, oferta(nome, True, base + caminho, img, usd=usd)))
        return lote
    itens = []
    # "celular apple iphone" traz os mesmos iPhones que "iphone" em metade das páginas
    for t in ["celular apple iphone" if t == "iphone" else t for t in TERMOS]:
        itens += _paginas(cli, lambda pg: base + "/site/search?query=%s&page=%d" % (quote(t), pg), ler)
    return itens, None


# Não incluídas (ver LEIA-ME): Cellshop e Compulandia (proteção anti-robô), Gonzalez Gimenez e Compumarket
# (busca por serviço externo com chave), Tupi (produtos só aparecem com o navegador montando a página).
LOJAS = [
    ("Nissei", coletar_nissei),
    ("Mega Eletrônicos", coletar_mega),
    ("Shopping China", coletar_shopping_china),
    ("Alemania Cell", coletar_alemania),
    ("Tecnostore", coletar_tecnostore),
    ("Visuar", coletar_visuar),
    ("Tienda Yankee", coletar_yankee),
    ("Bristol", coletar_bristol),
    ("Tienda Móvil", coletar_tienda_movil),
]


# --------------------------------------------------------------------------
# Banco de dados
# --------------------------------------------------------------------------

def abrir_banco(caminho=None):
    con = sqlite3.connect(caminho or BANCO)
    tabelas = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "precos" in tabelas:  # formato antigo (até 10/11/2026)
        con.execute("DROP TABLE precos")
    if "cambio" in tabelas and "hora" not in [c[1] for c in con.execute("PRAGMA table_info(cambio)")]:
        con.execute("DROP TABLE cambio")
    con.executescript("""
        CREATE TABLE IF NOT EXISTS ofertas (
            data TEXT NOT NULL,          -- AAAA-MM-DD
            loja TEXT NOT NULL,
            nome TEXT NOT NULL,          -- como a loja escreve
            modelo TEXT NOT NULL,        -- normalizado, ex.: iPhone 16 128GB
            preco_gs INTEGER NOT NULL,   -- em guaranis
            em_estoque INTEGER NOT NULL, -- 1 = sim, 0 = não
            link TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_ofertas ON ofertas(data, modelo);
        CREATE TABLE IF NOT EXISTS cambio (
            data TEXT PRIMARY KEY, hora TEXT NOT NULL, gs_por_usd REAL NOT NULL, fonte TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS fotos (
            modelo TEXT PRIMARY KEY, url TEXT NOT NULL, cor_principal INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS coletas (   -- resumo de cada execução, por loja
            data_hora TEXT NOT NULL, loja TEXT NOT NULL, itens INTEGER NOT NULL,
            segundos REAL NOT NULL, pedidos INTEGER NOT NULL, erro TEXT
        );
        CREATE TABLE IF NOT EXISTS pausas (    -- loja parada (erro/bloqueio): não tentar de novo no mesmo dia
            data TEXT NOT NULL, loja TEXT NOT NULL, motivo TEXT NOT NULL
        );
    """)
    colunas = [c[1] for c in con.execute("PRAGMA table_info(coletas)")]
    if "pedidos" not in colunas:   # versão anterior: sem contagem de pedidos
        con.execute("ALTER TABLE coletas ADD COLUMN pedidos INTEGER NOT NULL DEFAULT 0")
    if "segundos" not in colunas:
        con.execute("ALTER TABLE coletas ADD COLUMN segundos REAL NOT NULL DEFAULT 0")
    return con


def verificar_queda(con, loja, data, produtos_hoje):
    """Trava contra quebra silenciosa: compara com a última coleta bem-sucedida da loja.
    Devolve o texto do problema, ou None se está tudo bem."""
    anterior = con.execute("""SELECT data, COUNT(*) FROM ofertas WHERE loja = ? AND data < ?
                              GROUP BY data ORDER BY data DESC LIMIT 1""", (loja, data)).fetchone()
    if anterior and produtos_hoje < LIMITE_QUEDA * anterior[1]:
        return ("queda suspeita: %d produtos hoje contra %d em %s — o site pode ter mudado; "
                "dados de hoje descartados, mantidos os anteriores" % (produtos_hoje, anterior[1], anterior[0]))
    return None


def avisar(titulo, mensagem):
    """Notificação na tela do Mac (não envia nada para fora). No GitHub, vai para o resumo da execução."""
    import subprocess
    resumo = os.environ.get("GITHUB_STEP_SUMMARY")
    if resumo:
        with open(resumo, "a", encoding="utf-8") as f:
            f.write("### ⚠️ %s\n\n%s\n\n" % (titulo, mensagem))
        return
    if sys.platform != "darwin":
        return
    texto = mensagem.replace('"', "'")[:200]
    subprocess.run(["osascript", "-e", 'display notification "%s" with title "%s" sound name "Basso"' % (texto, titulo)],
                   capture_output=True)


def _guardar_resumo_copias(loja, data, produtos):
    """Junto com as cópias de uma loja, guarda quantos produtos a coleta real achou (usado nos testes)."""
    from educado import FIXTURES, _slug
    pasta = os.path.join(FIXTURES, _slug(loja))
    if os.path.isdir(pasta):
        with open(os.path.join(pasta, "resumo.json"), "w", encoding="utf-8") as f:
            json.dump({"data": data, "produtos": produtos}, f)


def _rodar_loja(loja, funcao, real):
    cli = Cliente(loja, real, log)
    inicio = time.time()
    try:
        itens, cambio = funcao(cli)
        return dict(loja=loja, itens=itens, cambio=cambio, erro=None, parada=False, cli=cli, seg=time.time() - inicio)
    except Dormiu as e:   # o Mac dormiu: a loja não tem culpa (não pausar)
        return dict(loja=loja, itens=[], cambio=None, erro=str(e), parada=False, dormiu=True, cli=cli,
                    seg=time.time() - inicio)
    except Parada as e:
        return dict(loja=loja, itens=[], cambio=None, erro=str(e), parada=True, cli=cli, seg=time.time() - inicio)
    except Exception as e:
        return dict(loja=loja, itens=[], cambio=None, erro="%s: %s" % (type(e).__name__, str(e)[:200]),
                    parada=False, cli=cli, seg=time.time() - inicio)


def main():
    real = "--real" in sys.argv
    reprocessar = "--reprocessar" in sys.argv and not real   # dados reais, mas lidos das cópias
    inicio = time.time()
    agora = datetime.now()
    data, hora = agora.strftime("%Y-%m-%d"), agora.strftime("%H:%M")

    if real or reprocessar:
        banco = BANCO
    else:
        # teste: trabalha numa cópia do banco, em dev/, e nunca publica
        os.makedirs(PASTA_DEV, exist_ok=True)
        for pasta in ("fotos", "fontes"):   # as páginas de teste usam as mesmas fotos e fontes
            if not os.path.exists(os.path.join(PASTA_DEV, pasta)):
                os.symlink(os.path.join(PASTA, pasta), os.path.join(PASTA_DEV, pasta))
        banco = os.path.join(PASTA_DEV, "precos-dev.db")
        if os.path.exists(BANCO):
            shutil.copyfile(BANCO, banco)
    con = abrir_banco(banco)
    modo = "Coleta REAL" if real else "REPROCESSAMENTO das cópias (sem acessar lojas)" if reprocessar else "Coleta de TESTE (cópias em fixtures/)"
    log("=== %s %s (%s) ===" % (modo, agora.strftime("%d/%m/%Y"), hora))

    pausadas = {l: m for l, m in con.execute("SELECT loja, motivo FROM pausas WHERE data = ?", (data,))} if real else {}
    lojas = []
    for loja, funcao in LOJAS:
        if loja in pausadas:
            log("   %s: pausada hoje (%s) — não será acessada até amanhã" % (loja, pausadas[loja]))
        else:
            lojas.append((loja, funcao))

    with ThreadPoolExecutor(max_workers=max(1, len(lojas))) as ex:
        resultados = list(ex.map(lambda l: _rodar_loja(l[0], l[1], real), lojas))   # reprocessar: real=False (cópias)

    # Cotação: a que a Nissei publicou nesta coleta; se não veio, a última salva
    cambio = next((r["cambio"] for r in resultados if r["cambio"]), None)
    fonte = "Nissei"
    if not cambio:
        ultima = con.execute("SELECT gs_por_usd FROM cambio ORDER BY data DESC LIMIT 1").fetchone()
        if not ultima:
            sys.exit("Sem cotação do dólar e nenhuma salva antes.")
        cambio, fonte = ultima[0], "última salva"
    con.execute("INSERT OR REPLACE INTO cambio VALUES (?,?,?,?)", (data, hora, cambio, fonte))

    fotos = {m: (u, cp) for m, u, cp in con.execute("SELECT modelo, url, cor_principal FROM fotos")}
    for r in resultados:
        linhas = []
        for it in r["itens"]:
            n = normalizar(it["nome"])
            if not n:
                continue
            gs = it["gs"] if it["gs"] is not None else it["usd"] * cambio
            linhas.append((data, r["loja"], it["nome"], n["chave"], int(round(gs)), int(it["em_estoque"]), it["link"]))
            if it["imagem"]:  # foto: só quando o modelo ainda não tem, ou quando aparece a cor principal
                atual, principal = fotos.get(n["modelo"]), e_cor_principal(n["modelo"], it["nome"])
                if atual is None or (principal and not atual[1]):
                    fotos[n["modelo"]] = (it["imagem"], principal)
                    con.execute("INSERT OR REPLACE INTO fotos VALUES (?,?,?)", (n["modelo"], it["imagem"], int(principal)))
        r["linhas"] = linhas
        r["suspeita"] = False
        if not r["erro"]:
            problema = verificar_queda(con, r["loja"], data, len(linhas))
            if problema:
                r["erro"], r["suspeita"] = problema, True
        if not r["erro"]:
            if real:
                _guardar_resumo_copias(r["loja"], data, len(linhas))
            # uma coleta por dia e por loja: a mais recente substitui a anterior do mesmo dia
            con.execute("DELETE FROM ofertas WHERE data = ? AND loja = ?", (data, r["loja"]))
            con.executemany("INSERT INTO ofertas VALUES (?,?,?,?,?,?,?)", linhas)
        else:
            log("   %s: %s %s" % (r["loja"], "PARADA:" if r["parada"] else "SUSPEITA:" if r["suspeita"]
                                else "MAC DORMIU:" if r.get("dormiu") else "ERRO:", r["erro"]))
            if r["parada"] and real:
                con.execute("INSERT INTO pausas VALUES (?,?,?)", (data, r["loja"], r["erro"]))
        con.execute("INSERT INTO coletas (data_hora, loja, itens, segundos, pedidos, erro) VALUES (?,?,?,?,?,?)",
                    (agora.isoformat(timespec="seconds"), r["loja"], len(linhas), round(r["seg"], 1), r["cli"].pedidos, r["erro"]))
    con.commit()
    if real or reprocessar:
        con.execute("VACUUM")   # mantém o arquivo do banco pequeno (ele é guardado no GitHub a cada coleta)
    con.close()
    total = time.time() - inicio

    # Resumo
    log("Cotação: 1 US$ = Gs. %s (%s)" % ("{:,.0f}".format(cambio).replace(",", "."), fonte))
    log("%-17s %9s %10s %8s %8s %7s  %s" % ("Loja", "produtos", "em estoque", "pedidos", "robots", "tempo", "situação"))
    for r in resultados:
        situacao = ("PARADA: " if r["parada"] else "SUSPEITA: " if r["suspeita"] else "MAC DORMIU: " if r.get("dormiu")
                    else "ERRO: ") + r["erro"] if r["erro"] else "ok"
        log("%-17s %9d %10d %8d %8d %6.0fs  %s" % (r["loja"], len(r["linhas"]), sum(1 for l in r["linhas"] if l[5]),
                                                  r["cli"].pedidos, r["cli"].pulados, r["seg"], situacao[:90]))
    for loja in pausadas:
        log("%-17s %9s %10s %8d %8s %7s  pausada hoje" % (loja, "-", "-", 0, "-", "-"))
    erros = sum(1 for r in resultados if r["erro"])
    dormidas = [r["loja"] for r in resultados if r.get("dormiu")]
    if dormidas and real:
        avisar("Busca Fácil: o Mac dormiu durante a coleta",
               "%d loja(s) sem dados. Nada foi publicado. Com o Mac acordado, rode: python3 coletor.py --real" % len(dormidas))
    elif erros and real:
        lojas_com_problema = [r["loja"] for r in resultados if r["erro"]]
        avisar("Busca Fácil: %d loja(s) com problema na coleta" % erros,
               ", ".join(lojas_com_problema) + ". Detalhes em coleta.log")
    if real:   # resumo para o aviso no celular (notificar.py)
        with open(os.path.join(PASTA, "ultima-coleta.json"), "w", encoding="utf-8") as f:
            json.dump({"data": data, "hora": hora, "segundos": round(total),
                       "produtos": sum(len(r["linhas"]) for r in resultados),
                       "lojas": len(resultados) + len(pausadas), "lojas_ok": sum(1 for r in resultados if not r["erro"]),
                       "problemas": [{"loja": r["loja"], "erro": r["erro"][:120]} for r in resultados if r["erro"]] +
                                    [{"loja": l, "erro": "pausada hoje"} for l in pausadas]}, f, ensure_ascii=False)
    log("Total: %d produtos · %d pedidos · %.0f segundos · %d loja(s) com problema" % (
        sum(len(r["linhas"]) for r in resultados), sum(r["cli"].pedidos for r in resultados), total, erros))

    # Páginas e publicação
    import pagina
    pagina.BANCO = banco
    if not (real or reprocessar):
        pagina.PASTA_SAIDA = PASTA_DEV
    for caminho in pagina.gerar(baixar_fotos=real):
        log("Página atualizada: %s" % caminho)
    if not (real or reprocessar):
        log("Teste: nada foi publicado. Páginas de teste em dev/.")
    elif dormidas:
        log("Publicação: NÃO feita — o Mac dormiu durante a coleta e %d loja(s) ficaram sem dados (%s). "
            "O site continua com a coleta anterior. Com o Mac acordado, rode de novo: python3 coletor.py --real"
            % (len(dormidas), ", ".join(dormidas)))
    elif "--sem-publicar" in sys.argv:
        log("Publicação: pulada (--sem-publicar).")
    else:
        try:
            import publicar
            publicar.publicar()
        except Exception as e:
            log("Publicação: erro inesperado (%s)" % e)
    return 1 if erros else 0


if __name__ == "__main__":
    sys.exit(main())
