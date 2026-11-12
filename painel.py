"""
Painel interno (só para o dono do projeto): o que mudou de preço e como foram as coletas.

    python3 painel.py            # gera painel-aberto.html (SEM senha, só para conferir neste Mac; não é publicado)

No GitHub, a publicação chama gerar_site(): os dados do painel são CRIPTOGRAFADOS com a
senha guardada no segredo PAINEL_SENHA (AES-256 + PBKDF2, via openssl) e gravados em
site/painel.html. Sem a senha, a página não mostra nada. Sem o segredo, o painel não é publicado.

Regras:
  - "preço" de um produto numa loja = menor preço em estoque daquela variante (modelo +
    armazenamento/tamanho + condição) naquele dia;
  - variação = mesmo produto, mesma loja, dia da coleta x coleta anterior;
  - variações menores que 0,5% (arredondamento, câmbio) são ignoradas;
  - um produto "subiu" se todas as lojas que mudaram subiram, "baixou" se todas baixaram,
    "misto" se umas subiram e outras baixaram.
"""

import base64
import json
import os
import sqlite3
import subprocess
import sys

from normalizar import normalizar

PASTA = os.path.dirname(os.path.abspath(__file__))
BANCO = os.path.join(PASTA, "precos.db")
TEMPLATE = os.path.join(PASTA, "template-painel.html")
DIAS_COMPARADOS = 30      # quantos dias de comparação ficam disponíveis no painel
ITERACOES = 300000        # PBKDF2 (o navegador refaz a mesma conta para abrir)
MINIMO = 0.005            # variações menores que 0,5% são arredondamento/câmbio, não mudança de preço


def _precos_do_dia(con, data):
    precos = {}
    for chave, loja, preco in con.execute(
            "SELECT modelo, loja, MIN(preco_gs) FROM ofertas WHERE data = ? AND em_estoque = 1 GROUP BY modelo, loja", (data,)):
        precos.setdefault(chave, {})[loja] = preco
    return precos


def _nomes(con, datas):
    """chave -> descrição legível (modelo, variante, condição, categoria)."""
    marcas = ",".join("?" * len(datas))
    nomes = {}
    for chave, nome in con.execute("SELECT modelo, MIN(nome) FROM ofertas WHERE data IN (%s) GROUP BY modelo" % marcas, datas):
        n = normalizar(nome)
        if n:
            nomes[chave] = {"modelo": n["modelo"], "variante": n["armazenamento"], "condicao": n["condicao"],
                            "categoria": n["categoria"], "linha": n["linha"]}
    return nomes


def comparar(con, data, anterior):
    hoje, antes = _precos_do_dia(con, data), _precos_do_dia(con, anterior)
    nomes = _nomes(con, [data, anterior])
    produtos, novas, sumiram = [], 0, 0
    for chave in sorted(set(hoje) | set(antes)):
        h, a = hoje.get(chave, {}), antes.get(chave, {})
        novas += len(set(h) - set(a))
        sumiram += len(set(a) - set(h))
        lojas = [{"loja": l, "antes": a[l], "hoje": h[l], "pct": (h[l] - a[l]) / a[l]}
                 for l in sorted(set(h) & set(a)) if abs(h[l] - a[l]) / a[l] >= MINIMO]
        if not lojas or chave not in nomes:
            continue
        subiu = sum(1 for x in lojas if x["pct"] > 0)
        direcao = "subiu" if subiu == len(lojas) else "baixou" if subiu == 0 else "misto"
        lojas.sort(key=lambda x: -abs(x["pct"]))
        produtos.append(dict(nomes[chave], chave=chave, direcao=direcao, lojas=lojas,
                             menorAntes=min(a.values()), menorHoje=min(h.values()) if h else None,
                             outras=sorted(({"loja": l, "preco": h[l]} for l in h if l not in {x["loja"] for x in lojas}),
                                           key=lambda x: x["preco"])))
    produtos.sort(key=lambda p: -max(abs(x["pct"]) for x in p["lojas"]))
    return {"data": data, "anterior": anterior, "produtos": produtos, "novas": novas, "sumiram": sumiram,
            "subiu": sum(1 for p in produtos if p["direcao"] == "subiu"),
            "baixou": sum(1 for p in produtos if p["direcao"] == "baixou"),
            "misto": sum(1 for p in produtos if p["direcao"] == "misto")}


def montar(banco=BANCO):
    con = sqlite3.connect(banco)
    datas = [r[0] for r in con.execute("SELECT DISTINCT data FROM ofertas ORDER BY data DESC LIMIT ?", (DIAS_COMPARADOS + 1,))]
    dias = [comparar(con, datas[i], datas[i + 1]) for i in range(len(datas) - 1)]
    cambio = {d: v for d, v in con.execute("SELECT data, gs_por_usd FROM cambio")}
    coletas = []
    for data_hora, seg, itens, lojas, com_erro, erros in con.execute(
            "SELECT data_hora, MAX(segundos), SUM(itens), COUNT(*), SUM(erro IS NOT NULL), "
            "GROUP_CONCAT(CASE WHEN erro IS NOT NULL THEN loja END, ', ') "
            "FROM coletas GROUP BY data_hora ORDER BY data_hora DESC LIMIT 90"):
        coletas.append({"quando": data_hora, "segundos": round(seg or 0), "produtos": itens, "lojas": lojas,
                        "problemas": com_erro, "lojasProblema": erros or ""})
    con.close()
    return {"dias": dias, "coletas": coletas[::-1], "cambio": cambio}


def _pagina(conteudo_dados, cifrado):
    with open(TEMPLATE, encoding="utf-8") as f:
        html = f.read()
    return html.replace("__CIFRADO__", "true" if cifrado else "false").replace("__ITERACOES__", str(ITERACOES)) \
               .replace("__DADOS__", conteudo_dados)


def _json(dados):
    return json.dumps(dados, ensure_ascii=False, separators=(",", ":"))


def cifrar(texto, senha):
    """AES-256-CBC com chave e IV derivados por PBKDF2-SHA256 (formato 'Salted__' do openssl)."""
    r = subprocess.run(["openssl", "enc", "-aes-256-cbc", "-pbkdf2", "-iter", str(ITERACOES), "-md", "sha256",
                        "-salt", "-pass", "env:PAINEL_SENHA"],
                       input=texto.encode("utf-8"), capture_output=True, env=dict(os.environ, PAINEL_SENHA=senha))
    if r.returncode != 0:
        raise RuntimeError("openssl falhou: " + r.stderr.decode()[:200])
    return base64.b64encode(r.stdout).decode()


def gerar_site(pasta_site=os.path.join(PASTA, "site")):
    senha = os.environ.get("PAINEL_SENHA")
    if not senha:
        print("Painel: sem o segredo PAINEL_SENHA — painel NÃO publicado (nunca publicamos sem senha).")
        return None
    destino = os.path.join(pasta_site, "painel.html")
    with open(destino, "w", encoding="utf-8") as f:
        f.write(_pagina(json.dumps(cifrar(_json(montar()), senha)), True))
    print("Painel: gerado (criptografado) em " + destino)
    return destino


if __name__ == "__main__":
    saida = os.path.join(PASTA, "painel-aberto.html")
    with open(saida, "w", encoding="utf-8") as f:
        f.write(_pagina(_json(montar()).replace("</", "<\\/"), False))
    print("Painel SEM senha (só local, não publicado): " + saida)
    if "--resumo" in sys.argv:
        d = montar()["dias"]
        if d:
            print("%s x %s: subiu %d, baixou %d, misto %d" % (d[0]["data"], d[0]["anterior"], d[0]["subiu"], d[0]["baixou"], d[0]["misto"]))
