"""
Testes do projeto. Rodam SEM internet (nenhuma loja é acessada).

    python3 testes.py                    # roda todos os testes
    python3 testes.py --atualizar-nomes  # regrava a lista de referência de nomes (depois de uma mudança intencional)

O que é testado:
  1. Nomes      — nomes reais de anúncios continuam reconhecidos do mesmo jeito (tests/nomes.json)
  2. robots.txt — cada endereço que o coletor usa está permitido pelo robots.txt da loja (tests/robots/)
  3. Leitores   — com as cópias de fixtures/, cada loja encontra os mesmos produtos da coleta real
  4. Educação   — ritmo, robots, user-agent, paradas (429/5xx/lentidão), Mac dormindo e cópias, numa loja falsa local
  5. Trava      — uma queda de mais da metade dos produtos é tratada como suspeita
"""

import json
import os
import sqlite3
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PASTA = os.path.dirname(os.path.abspath(__file__))
TESTES = os.path.join(PASTA, "tests")
sys.path.insert(0, PASTA)

import coletor
import educado
from normalizar import cor_canonica, normalizar

resultados = []


def registrar(nome, ok, detalhe=""):
    resultados.append((nome, ok, detalhe))
    print("%s %-38s %s" % ("✓" if ok is True else "–" if ok is None else "✗", nome, detalhe))


def _classificar(nome):
    n = normalizar(nome)
    return {"chave": n["chave"], "condicao": n["condicao"], "cor": cor_canonica(nome)} if n else None


# ---------------------------------------------------------------- 1. Nomes
NAO_RECONHECER = [
    "CAPA PROTECTORA 4LIFE IPHONE 17 CLEAR", "Correa Crossbody Apple para Iphone",
    "Maletin P/Macbook Pro/Air 13'' Gris Oscuro", 'Consola Lenovo Legion Go 8.8" WQXGA, AMD Ryzen Z2 Go, 16GB RAM, 1TB SSD',
    "CELULAR XIAOMI REDMI 15C 8GB 256GB 25078RA3EL MINT GREEN", "Xiaomi Redmi Note 15 Pro+ 5G Dual 512 GB - Negro",
    'Apple MacBook Air (2026) MDVA4LL/A 15.3" M5 1 TB - Silver', "Lamina Puregear Cristal iPhone 14 Pro Max",
]


def gravar_nomes():
    con = sqlite3.connect(coletor.BANCO)
    nomes = sorted({r[0] for r in con.execute("SELECT DISTINCT nome FROM ofertas")} | set(NAO_RECONHECER))
    os.makedirs(TESTES, exist_ok=True)
    with open(os.path.join(TESTES, "nomes.json"), "w", encoding="utf-8") as f:
        json.dump({n: _classificar(n) for n in nomes}, f, ensure_ascii=False, indent=1)
    print("Referência regravada: %d nomes em tests/nomes.json" % len(nomes))


def teste_nomes():
    arq = os.path.join(TESTES, "nomes.json")
    if not os.path.exists(arq):
        return registrar("nomes", None, "sem referência (rode: python3 testes.py --atualizar-nomes)")
    esperado = json.load(open(arq, encoding="utf-8"))
    diferentes = [(n, e, _classificar(n)) for n, e in esperado.items() if _classificar(n) != e]
    registrar("nomes (%d reais)" % len(esperado), not diferentes,
              "" if not diferentes else "%d mudaram, ex.: %s: %s -> %s" % (len(diferentes), *diferentes[0]))


# ---------------------------------------------------------------- 2. robots.txt
ENDERECOS = [  # (arquivo robots, endereço usado pelo coletor, deve ser permitido?)
    ("nissei.com", "/graphql", True),
    ("www.megaeletronicos.com", "/producto/buscar?search=iphone&page=2", True),
    ("www.shoppingchina.com.py", "/site/search?query=macbook&page=1", True),
    ("www.shoppingchina.com.py", "/quick_search?search=celular%20apple%20iphone", True),
    ("www.alemaniacell.com", "/celulares?marca=apple&js=1&pag=2", True),
    ("www.alemaniacell.com", "/catalogo?q=redmi%20note%2015", True),
    ("tecnostore.com.py", "/v2/wp-json/wc/store/v1/products?search=iphone&per_page=100&page=1", True),
    ("tiendayankee.com", "/wp-json/wc/store/v1/products?search=loq&per_page=100&page=1", True),
    ("tiendamovil.com.py", "/shop/busqueda?controller=search&s=iphone&ajax=1&resultsPerPage=100&page=1", True),
    ("visuar.com.py", "/celulares/iphone/?ajax=1&page=2", True),
    ("visuar.com.py", "/busqueda?controller=search&s=iphone&ajax=1", False),      # proibido: por isso usamos categorias
    ("www.bristol.com.py", "/celulares-y-smartwatches/celulares?marca=apple&js=1&pag=2", True),
    ("www.bristol.com.py", "/tecnologia/informatica/notebooks?marca=lenovo", True),
    ("www.bristol.com.py", "/catalogo?q=iphone", False),                         # proibido: por isso usamos ?marca=
    ("visuar.com.py", "/tvs/smart-tv-55-pulgadas/?ajax=1&page=2", True),
    ("www.bristol.com.py", "/televisores-y-audio/televisores?marca=samsung&js=1&pag=2", True),
    ("www.megaeletronicos.com", "/producto/buscar?search=galaxy%20a17&page=1", True),
]


def teste_robots():
    errados = []
    for site, caminho, esperado in ENDERECOS:
        arq = os.path.join(TESTES, "robots", site + ".txt")
        regras, _ = educado.ler_robots(open(arq, encoding="utf-8", errors="ignore").read())
        if educado.permitido(regras, caminho) != esperado:
            errados.append(site + caminho)
    registrar("robots.txt (%d endereços)" % len(ENDERECOS), not errados, ", ".join(errados))


# ---------------------------------------------------------------- 3. Leitores das lojas
def teste_leitores():
    for loja, funcao in coletor.LOJAS:
        resumo = os.path.join(educado.FIXTURES, educado._slug(loja), "resumo.json")
        if not os.path.exists(resumo):
            registrar("leitor: " + loja, None, "pulado: ainda sem cópias (rode uma vez: python3 coletor.py --real)")
            continue
        esperado = json.load(open(resumo, encoding="utf-8"))
        try:
            itens, _ = funcao(educado.Cliente(loja, False, lambda m: None))
            achados = sum(1 for it in itens if normalizar(it["nome"]))
            registrar("leitor: " + loja, achados == esperado["produtos"],
                      "%d produtos (coleta real de %s: %d)" % (achados, esperado["data"], esperado["produtos"]))
        except Exception as e:
            registrar("leitor: " + loja, False, "%s: %s" % (type(e).__name__, str(e)[:90]))


# ---------------------------------------------------------------- 4. Educação (loja falsa local)
def teste_educado():
    chegadas, agentes = [], set()

    class Loja(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            chegadas.append(time.time())
            agentes.add(self.headers.get("User-Agent"))
            cod, corpo = 200, ("pagina " + self.path).encode()
            if self.path == "/robots.txt":
                corpo = b"User-agent: *\nDisallow: /proibido\n"
            elif self.path.startswith("/erro429"):
                cod = 429
            elif self.path.startswith("/erro503"):
                cod = 503
            elif self.path.startswith("/naoexiste"):
                cod = 404
            elif self.path.startswith("/lenta"):
                time.sleep(3)
            self.send_response(cod)
            self.end_headers()
            self.wfile.write(corpo)

    srv = ThreadingHTTPServer(("127.0.0.1", 0), Loja)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = "http://127.0.0.1:%d" % srv.server_address[1]
    original = (educado.INTERVALO, educado.LIMITE_SEGUNDOS, educado.FIXTURES)
    educado.INTERVALO, educado.LIMITE_SEGUNDOS = (0.3, 0.5), 2   # versões curtas, só para o teste ser rápido
    educado.FIXTURES = tempfile.mkdtemp()
    try:
        c = educado.Cliente("Loja Falsa", True, lambda m: None)
        ok_paginas = c.get(base + "/a") == "pagina /a" and c.get(base + "/b") == "pagina /b"
        registrar("educação: páginas normais", ok_paginas)
        registrar("educação: robots.txt respeitado", c.get(base + "/proibido/x") is None and c.pulados == 1)
        intervalo = min(chegadas[i] - chegadas[i - 1] for i in range(1, len(chegadas)))
        registrar("educação: ritmo entre pedidos", intervalo >= 0.3, "menor intervalo %.2fs" % intervalo)
        registrar("educação: user-agent honesto", all("BuscaFacilBot" in a and "@" in a for a in agentes), list(agentes)[0])
        for caminho, deve_parar in [("/erro429", True), ("/erro503", True), ("/lenta", True), ("/naoexiste", False)]:
            try:
                c.get(base + caminho)
                parou = False
            except educado.Parada:
                parou = True
            except Exception:
                parou = False
            registrar("educação: %s %s" % (caminho, "para a loja" if deve_parar else "não para"), parou == deve_parar)
        dormido_original = educado._dormido
        educado._dormido = lambda *a: 900     # finge que o Mac dormiu 15 min durante o pedido
        try:
            c.get(base + "/lenta")
            resultado = "nada"
        except educado.Dormiu:
            resultado = "dormiu"
        except educado.Parada:
            resultado = "parada"
        finally:
            educado._dormido = dormido_original
        registrar("educação: Mac dormiu não culpa a loja", resultado == "dormiu", resultado)
        antes = len(chegadas)
        d = educado.Cliente("Loja Falsa", False, lambda m: None)
        registrar("educação: modo teste usa cópias", d.get(base + "/a") == "pagina /a" and len(chegadas) == antes,
                  "0 pedidos à rede")
    finally:
        educado.INTERVALO, educado.LIMITE_SEGUNDOS, educado.FIXTURES = original
        srv.shutdown()


# ---------------------------------------------------------------- 5. Trava contra queda
def teste_trava():
    with tempfile.TemporaryDirectory() as tmp:
        con = coletor.abrir_banco(os.path.join(tmp, "t.db"))
        con.executemany("INSERT INTO ofertas VALUES (?,?,?,?,?,?,?)",
                        [("2026-01-01", "Loja X", "n%d" % i, "m", 1, 1, "l") for i in range(100)])
        caiu = coletor.verificar_queda(con, "Loja X", "2026-01-02", 40)
        normal = coletor.verificar_queda(con, "Loja X", "2026-01-02", 60)
        nova = coletor.verificar_queda(con, "Loja Nova", "2026-01-02", 3)
        registrar("trava: queda de 100 para 40", caiu is not None)
        registrar("trava: 100 para 60 é aceito", normal is None)
        registrar("trava: loja sem histórico é aceita", nova is None)
        con.close()


if __name__ == "__main__":
    if "--atualizar-nomes" in sys.argv:
        gravar_nomes()
        sys.exit(0)
    inicio = time.time()
    teste_nomes()
    teste_robots()
    teste_leitores()
    teste_educado()
    teste_trava()
    falhas = [r for r in resultados if r[1] is False]
    pulados = [r for r in resultados if r[1] is None]
    print("\n%d testes · %d ok · %d falha(s) · %d pulado(s) · %.0fs" % (
        len(resultados), len(resultados) - len(falhas) - len(pulados), len(falhas), len(pulados), time.time() - inicio))
    sys.exit(1 if falhas else 0)
