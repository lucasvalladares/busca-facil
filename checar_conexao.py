"""
Teste rápido de conexão: cada loja responde a partir deste computador (ou do GitHub)?
Faz no máximo 2 pedidos por loja (robots.txt + 1 endereço que o coletor usa), com as
mesmas regras de educação do coletor. Não grava nada no banco.

    python3 checar_conexao.py
"""

import sys
import time
import urllib.error
from urllib.parse import urlsplit

import educado
from testes import ENDERECOS


def main():
    vistos, falhas = set(), 0
    for site, caminho, permitido in ENDERECOS:
        if not permitido or site in vistos or caminho == "/graphql":
            continue
        vistos.add(site)
        url = "https://%s%s" % (site, caminho)
        c = educado.Cliente(site, True, lambda m: None)
        inicio = time.time()
        try:
            texto = c.get(url)
            situacao = "ok (%d caracteres)" % len(texto or "")
        except educado.Parada as e:
            situacao, falhas = "BLOQUEADA/FORA: %s" % e, falhas + 1
        except urllib.error.HTTPError as e:
            situacao, falhas = "HTTP %d" % e.code, falhas + 1
        print("%-28s %5.1fs  %s" % (urlsplit(url).netloc, time.time() - inicio, situacao), flush=True)
    sys.exit(1 if falhas else 0)


if __name__ == "__main__":
    main()
