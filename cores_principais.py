"""
Cor principal ("cor de destaque" do lançamento) de cada modelo.

É usada para escolher a foto do modelo no catálogo. Para trocar uma cor,
edite a lista abaixo e rode `python3 pagina.py`. Depois apague a foto antiga
do modelo na pasta fotos/, para ela ser baixada de novo na cor nova.

Cada entrada tem os nomes que essa cor pode ter nos sites
(as lojas escrevem em inglês ou espanhol).

A Apple não publica uma lista oficial de "cor principal". As marcadas com
"A CONFIRMAR" foram escolhidas por notícias/pré-lançamento, não pela Apple.
"""

CORES_PRINCIPAIS = {
    "iPhone 13":          ["pink", "rosa"],
    "iPhone 13 Pro":      ["sierra blue", "azul sierra"],
    "iPhone 14":          ["purple", "morado", "lila"],
    "iPhone 14 Plus":     ["purple", "morado", "lila"],
    "iPhone 15":          ["pink", "rosa"],
    "iPhone 15 Plus":     ["pink", "rosa"],
    "iPhone 15 Pro":      ["natural"],
    "iPhone 15 Pro Max":  ["natural"],
    "iPhone 16":          ["ultramarine", "ultramar"],
    "iPhone 16 Plus":     ["ultramarine", "ultramar"],
    "iPhone 16 Pro":      ["desert", "desierto"],
    "iPhone 16 Pro Max":  ["desert", "desierto"],
    "iPhone 16e":         ["white", "blanco"],
    "iPhone 17":          ["sage", "salvia"],                       # A CONFIRMAR (imprensa cita Sage e Mist Blue)
    "iPhone 17e":         ["soft pink", "pink", "rosa"],             # Apple lista o rosa primeiro
    "iPhone 17 Pro":      ["cosmic orange", "naranja", "orange"],
    "iPhone 17 Pro Max":  ["cosmic orange", "naranja", "orange"],
    "iPhone Air":         ["sky blue", "azul cielo"],
    "iPhone 18 Pro":      ["burgundy", "cherry", "cereza", "borgo"],  # A CONFIRMAR (vazamentos: "Dark Cherry")
    "iPhone 18 Pro Max":  ["burgundy", "cherry", "cereza", "borgo"],  # A CONFIRMAR
    "iPhone Duo":         ["night sky", "azul noche"],              # A CONFIRMAR (só 2 cores: Night Sky e Star White)
}


def e_cor_principal(modelo, texto):
    """True se o texto (nome do anúncio + cor) menciona a cor principal do modelo."""
    texto = (texto or "").lower()
    return any(alias in texto for alias in CORES_PRINCIPAIS.get(modelo, []))
