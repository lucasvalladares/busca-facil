"""
Publicação do site no GitHub Pages.

A pasta site/ contém só o que o site precisa para funcionar sozinho na
internet (sem depender deste Mac):
    index.html        -> versão vibrante em português (página principal)
    es.html           -> versão vibrante em espanhol
    minimalista.html  -> versão minimalista
    minimalista-es.html -> versão minimalista em espanhol
    fotos/, fontes/   -> imagens dos modelos e fontes
Os preços já vão embutidos dentro de cada página.

Quem publica é o GitHub Actions (.github/workflows/coleta.yml): ele roda a
coleta, chama montar_site() e envia a pasta site/ para o GitHub Pages.
Localmente, "python3 publicar.py" só monta site/ para conferir.
"""

import os
import shutil
from datetime import datetime

PASTA = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(PASTA, "site")

PAGINAS = {  # arquivo gerado -> nome no site
    "relatorio-vibrante.html": "index.html",
    "relatorio-vibrante-es.html": "es.html",
    "relatorio-minimalista.html": "minimalista.html",
    "relatorio-minimalista-es.html": "minimalista-es.html",
}


def montar_site():
    """Copia as páginas, fotos e fontes para site/."""
    os.makedirs(SITE, exist_ok=True)
    for origem, destino in PAGINAS.items():
        caminho = os.path.join(PASTA, origem)
        if os.path.exists(caminho):
            shutil.copyfile(caminho, os.path.join(SITE, destino))
    for pasta in ("fotos", "fontes"):
        o, d = os.path.join(PASTA, pasta), os.path.join(SITE, pasta)
        os.makedirs(d, exist_ok=True)
        for nome in os.listdir(o):
            if nome.endswith((".jpg", ".png", ".webp", ".woff2")):
                shutil.copyfile(os.path.join(o, nome), os.path.join(d, nome))
    # avisa o GitHub Pages para servir os arquivos como estão
    open(os.path.join(SITE, ".nojekyll"), "w").close()
    return SITE


def publicar():
    """A publicação agora é feita pelo GitHub Actions (.github/workflows/coleta.yml), não por este Mac."""
    montar_site()
    print("Publicação: feita pelo GitHub (Actions). Este Mac não envia mais o site. Páginas locais em site/.")
    return False


if __name__ == "__main__":
    montar_site()
    print("Site montado em site/ (para conferir localmente).")
