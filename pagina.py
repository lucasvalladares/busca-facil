"""
Gera as páginas (relatorio-*.html) a partir do banco precos.db.

Roda sozinho no fim de cada coleta, mas você também pode gerar a página
sem coletar de novo:
    python3 pagina.py

O visual da página fica em template.html; aqui só preparamos os dados
e baixamos as fotos dos modelos (pasta fotos/).
"""

import json
import os
import re
import sqlite3
from datetime import date, datetime

from cores_principais import CORES_PRINCIPAIS
from normalizar import CONDICOES, cor_canonica, normalizar

SEM_COR = "Cor não informada"

PASTA = os.path.dirname(os.path.abspath(__file__))
BANCO = os.path.join(PASTA, "precos.db")
# Versões visuais da página: cada uma tem seu template e gera seu próprio arquivo.
VERSOES = {
    "minimalista": "template-minimalista.html",
    "vibrante": "template-vibrante.html",
}
PASTA_FOTOS = os.path.join(PASTA, "fotos")
PASTA_SAIDA = PASTA  # onde as páginas são gravadas (o simular.py muda para teste/)

# Ordem fixa das lojas = cor fixa de cada loja no gráfico.
# (máximo 8 cores; a Cellshop, não monitorada, fica sem cor)
ORDEM_LOJAS = ["Nissei", "Mega Eletrônicos", "Shopping China", "Alemania Cell",
               "Tecnostore", "Visuar", "Tienda Yankee", "Bristol", "Tienda Móvil"]



def _slug(texto):
    return re.sub(r"[^a-z0-9]+", "-", texto.lower()).strip("-")


# Categorias, linhas e ordem dos produtos vêm do produtos.json
from normalizar import CATEGORIAS, PRODUTOS
ORDEM_LINHAS = []
for _c in CATEGORIAS:
    ORDEM_LINHAS += [l for l in _c["linhas"] if l not in ORDEM_LINHAS]
ORDEM_OUTROS = []
for _p in PRODUTOS:
    if _p.get("reconhecedor") == "macbook":
        ORDEM_OUTROS += ['MacBook %s %d" M%d' % tuple(m) for m in sorted(_p["modelos"], key=lambda m: (m[0] != "Pro", -m[1], -m[2]))]
    else:
        ORDEM_OUTROS.append(_p["nome"])


def _ordem_modelo(linha, modelo):
    """iPhones: mais novo primeiro (18 Pro Max, 18 Pro, 17 ...), depois Air/Duo. Demais: ordem da lista acima."""
    if linha != "iPhone":
        return (1 + ORDEM_LINHAS.index(linha), ORDEM_OUTROS.index(modelo) if modelo in ORDEM_OUTROS else 99, 0, 0, modelo)
    m = re.match(r"iPhone (\w+)(.*)$", modelo)
    num = re.match(r"(\d+)(e?)$", m.group(1)) if m else None
    if not num:
        return (0, 1, 0, 0, modelo)  # Air, Duo, SE: no fim
    ordem_var = {"": 2, " Plus": 1, " Pro": 3, " Pro Max": 4}.get(m.group(2), 0)
    return (0, 0, -int(num.group(1)) * 10 + (1 if num.group(2) else 0), -ordem_var, modelo)


def _ordem_variante(variante):
    """128GB < 256GB < 1TB; M5 < M5 Pro < M5 Max; RTX 3050 < RTX 4050; "não informada" por último."""
    nivel = 2 if " Max" in variante else 1 if " Pro" in variante else 0
    cap = re.search(r"(\d+)\s*(GB|TB)", variante)
    gb = int(cap.group(1)) * (1024 if cap.group(2) == "TB" else 1) if cap else 0
    gpu = re.search(r"RTX (\d+)", variante)
    return (nivel, gb, int(gpu.group(1)) if gpu else 99999, variante)


def _inicio_janela(ultima):
    """Primeiro dia do mesmo mês, 12 meses atrás (ex.: 10/11/2026 -> 01/11/2025)."""
    d = datetime.strptime(ultima, "%Y-%m-%d").date()
    return date(d.year - 1, d.month, 1).isoformat()


# --------------------------------------------------------------------------
# Fotos
# --------------------------------------------------------------------------

def _baixar_foto(cliente, url, destino_sem_ext):
    dados, tipo = cliente.baixar_arquivo(url)
    if dados is None:
        raise RuntimeError("proibido pelo robots.txt")
    ext = ".webp" if "webp" in tipo else ".png" if "png" in tipo else ".jpg"
    with open(destino_sem_ext + ext, "wb") as f:
        f.write(dados)
    return destino_sem_ext + ext


def preparar_fotos(con, modelos, baixar=False):
    """
    Baixa (uma vez só) a foto de cada modelo. O endereço vem da tabela "fotos",
    que o coletor preenche quando aparece um modelo novo ou a cor principal.
    Guarda o que foi baixado em fotos/fotos.json.
    """
    os.makedirs(PASTA_FOTOS, exist_ok=True)
    indice_arq = os.path.join(PASTA_FOTOS, "fotos.json")
    indice = json.load(open(indice_arq, encoding="utf-8")) if os.path.exists(indice_arq) else {}
    origem = {m: (u, bool(cp)) for m, u, cp in con.execute("SELECT modelo, url, cor_principal FROM fotos")}
    from educado import Cliente
    cliente = Cliente("Fotos", baixar, lambda msg: print(msg))

    for modelo in modelos:
        atual = indice.get(modelo)
        tem_arquivo = bool(atual) and os.path.exists(os.path.join(PASTA, atual["arquivo"]))
        if modelo not in origem:
            continue
        url, principal = origem[modelo]
        # baixa se ainda não tem foto, ou se agora apareceu a cor principal e a atual não é
        if tem_arquivo and (atual.get("corPrincipal") or not principal or atual.get("url") == url):
            continue
        if not baixar:
            continue  # modo de teste: usa só as fotos que já existem
        try:
            caminho = _baixar_foto(cliente, url, os.path.join(PASTA_FOTOS, _slug(modelo)))
        except Exception as e:
            print("   aviso: não baixou a foto de %s (%s)" % (modelo, e))
            continue
        indice[modelo] = {"arquivo": os.path.relpath(caminho, PASTA), "corPrincipal": principal, "url": url}

    with open(indice_arq, "w", encoding="utf-8") as f:
        json.dump(indice, f, ensure_ascii=False, indent=2)
    return indice


# --------------------------------------------------------------------------
# Dados da página
# --------------------------------------------------------------------------

def montar_dados(baixar_fotos=False):
    con = sqlite3.connect(BANCO)
    ultima = con.execute("SELECT MAX(data) FROM ofertas").fetchone()[0]
    base = {"condicoes": CONDICOES, "lojas": ORDEM_LOJAS, "categorias": CATEGORIAS,
            "geradoEm": datetime.now().strftime("%d/%m/%Y %H:%M")}
    if not ultima:
        con.close()
        return dict(base, ultimaData=None, inicioJanela=None, status=[], modelos=[], cambio=None)
    inicio = _inicio_janela(ultima)

    # Ofertas em estoque da janela de 12 meses. Condição, armazenamento e cor saem do nome.
    linhas = con.execute("""
        SELECT data, loja, nome, preco_gs, link FROM ofertas
        WHERE data >= ? AND em_estoque = 1 ORDER BY data
    """, (inicio,)).fetchall()

    # Situação da última coleta de cada loja
    status = [{"loja": l, "data_hora": d, "status": "erro" if e else "ok", "itens": n} for l, d, n, e in con.execute("""
        SELECT loja, data_hora, itens, erro FROM coletas c
        WHERE data_hora = (SELECT MAX(data_hora) FROM coletas WHERE loja = c.loja)
    """)]
    # Para cada loja, quantos iPhones em estoque havia na última coleta bem-sucedida
    em_estoque = dict(con.execute("SELECT loja, COUNT(*) FROM ofertas WHERE data = ? AND em_estoque = 1 GROUP BY loja", (ultima,)))
    for st in status:
        st["itens"] = em_estoque.get(st["loja"], 0)

    # Cotação usada no site: a do momento da coleta mais recente (todas as contas do site usam esta)
    c = con.execute("SELECT data, hora, gs_por_usd, fonte FROM cambio ORDER BY data DESC LIMIT 1").fetchone()
    cambio = {"valor": c[2], "data": c[0], "hora": c[1], "fonte": c[3]} if c else None

    # Menor preço por variante, cor, loja e dia. A cor "" = todas as cores juntas.
    modelos, info = {}, {}
    cache = {}
    for data, loja, nome, preco, link in linhas:
        if nome not in cache:
            cache[nome] = (normalizar(nome), cor_canonica(nome) or SEM_COR)
        n, cor_nome = cache[nome]
        if not n:
            continue
        info[n["modelo"]] = (n["categoria"], n["linha"], n.get("serie"), n["rotulo"])
        v = modelos.setdefault(n["modelo"], {}).setdefault((n["condicao"], n["armazenamento"]), {
            "condicao": n["condicao"], "armazenamento": n["armazenamento"], "porCor": {}})
        for cor in ("", cor_nome):
            g = v["porCor"].setdefault(cor, {"dia": {}})
            atual = g["dia"].get((loja, data))
            if atual is None or preco < atual["preco"]:
                g["dia"][(loja, data)] = {"preco": preco, "link": link, "nome": nome}

    fotos = preparar_fotos(con, list(modelos), baixar_fotos)
    # Dados de teste (simular.py): tudo o que for anterior à primeira coleta real
    primeira = con.execute("SELECT MIN(substr(data_hora, 1, 10)) FROM coletas").fetchone()[0]
    sim = con.execute("SELECT MIN(data), MAX(data) FROM ofertas WHERE data < ?", (primeira or "",)).fetchone()
    simulado = {"de": sim[0], "ate": sim[1]} if sim and sim[0] else None
    con.close()

    def resumir(g):
        """Transforma os preços de um grupo (variante + cor) em série, ofertas de hoje e lojas sem oferta."""
        series, ultimo = {}, {}
        for (loja, data), info in sorted(g["dia"].items(), key=lambda x: x[0][1]):
            series.setdefault(loja, []).append([data, info["preco"]])
            ultimo[loja] = dict(info, data=data)
        hoje = sorted(({"loja": l, "preco": u["preco"], "link": u["link"], "nome": u["nome"]}
                       for l, u in ultimo.items() if u["data"] == ultima), key=lambda x: x["preco"])
        sem_oferta = [{"loja": l, "desde": u["data"]} for l, u in ultimo.items() if u["data"] != ultima]
        return {"series": series, "hoje": hoje, "semOfertaHoje": sem_oferta}

    lista = []
    for modelo, variantes in modelos.items():
        vs = []
        for v in variantes.values():
            todas = resumir(v["porCor"][""])
            por_cor = {c: resumir(g) for c, g in v["porCor"].items() if c}
            # cores com oferta hoje, da mais barata para a mais cara ("cor não informada" por último)
            cores = sorted((c for c, r in por_cor.items() if r["hoje"]),
                           key=lambda c: (c == SEM_COR, por_cor[c]["hoje"][0]["preco"]))
            vs.append(dict(todas, condicao=v["condicao"], armazenamento=v["armazenamento"],
                           cores=cores, porCor=por_cor))
        vs.sort(key=lambda v: (CONDICOES.index(v["condicao"]), _ordem_variante(v["armazenamento"])))
        foto = fotos.get(modelo, {})
        categoria, linha, serie, rotulo = info[modelo]
        lista.append({
            "categoria": categoria,
            "linha": linha,
            "serie": serie,
            "rotuloVariante": rotulo,
            "modelo": modelo,
            "slug": _slug(modelo),
            "foto": foto.get("arquivo"),
            "fotoCorPrincipal": foto.get("corPrincipal", False),
            "corPrincipal": (CORES_PRINCIPAIS.get(modelo) or [""])[0].title(),
            "variantes": vs,
        })
    lista.sort(key=lambda m: _ordem_modelo(m["linha"], m["modelo"]))

    return dict(base, ultimaData=ultima, inicioJanela=inicio, status=status, modelos=lista, cambio=cambio,
                simulado=simulado)


def gerar(baixar_fotos=False):
    """Gera relatorio-<versão>.html para cada versão visual. Devolve a lista de arquivos.
    baixar_fotos=True só na coleta real (fotos de modelos novos, pelo cliente educado)."""
    dados = montar_dados(baixar_fotos)
    # "</" escapado para o JSON não conseguir fechar a tag <script>
    js = json.dumps(dados, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    gerados = []
    for nome, template in VERSOES.items():
        caminho_template = os.path.join(PASTA, template)
        if not os.path.exists(caminho_template):
            continue
        with open(caminho_template, encoding="utf-8") as f:
            modelo_html = f.read()
        saida = os.path.join(PASTA_SAIDA, "relatorio-%s.html" % nome)
        with open(saida, "w", encoding="utf-8") as f:
            f.write(modelo_html.replace("__DADOS__", js))
        gerados.append(saida)

        # Versão em espanhol da vibrante: gerada a partir do mesmo template, com a tabela de traducao_es.py
        if nome == "vibrante":
            import traducao_es
            html_es, avisos = traducao_es.traduzir(modelo_html.replace("__DADOS__", js))
            for aviso in avisos:
                print("   aviso (espanhol): " + aviso)
            saida_es = os.path.join(PASTA_SAIDA, "relatorio-vibrante-es.html")
            with open(saida_es, "w", encoding="utf-8") as f:
                f.write(html_es)
            gerados.append(saida_es)
    return gerados


if __name__ == "__main__":
    for caminho in gerar():
        print("Página gerada: %s" % caminho)
