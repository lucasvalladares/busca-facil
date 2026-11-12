"""
Normalização de nomes de produtos (iPhone, Xiaomi, MacBook e notebooks gamer).

Cada loja escreve o nome de um jeito:
  Nissei:          "Apple iPhone 16 A3287 128 GB - Azul"
  Mega:            'CEL IPHONE 16 6.1" 8GB+128GB A3287 BLACK'
  Shopping China:  "CELULAR APPLE IPHONE 16 128GB PINK CPO"

A função `normalizar` transforma qualquer um deles em três informações:
  modelo         -> "iPhone 16"
  armazenamento  -> "128GB"
  condicao       -> "Novo", "Recondicionado (CPO)" ou "Sem lacre"

Se o nome não for de um iPhone (capa, cabo, película...), ela devolve None.
"""

import re

CONDICOES = ["Novo", "Recondicionado (CPO)", "Sem lacre"]

# Palavras que indicam acessório, não celular.
_ACESSORIOS = re.compile(
    r"\b(capa|funda|case|pel[ií]cula|vidrio|protector|cargador|cable|correa|"
    r"soporte|adaptador|auricular|lapiz|templado)\b",
    re.IGNORECASE,
)

# "iphone" + número (16, 16e, 17...) ou nome (air, duo, se)
# + variante opcional (pro max, pro, plus, mini)
_MODELO = re.compile(
    r"\biphone\s+(\d{1,2}e?|air|duo|se)\b(?:\s+(pro\s*max|pro|plus|mini))?",
    re.IGNORECASE,
)

# Números seguidos de GB ou TB ("128GB", "128 GB", "1 TB")
_CAPACIDADE = re.compile(r"(\d+)\s*(GB|TB)\b", re.IGNORECASE)
_ARMAZENAMENTOS_VALIDOS = {"64GB", "128GB", "256GB", "512GB", "1TB", "2TB"}

_CPO = re.compile(r"\b(cpo|reacondicionado|recondicionado|refurbished|seminuevo|swap)\b", re.IGNORECASE)
_SEM_LACRE = re.compile(r"(s/\s*lacre|sin\s+lacre|sem\s+lacre|open\s*box)", re.IGNORECASE)


def _formatar_modelo(base, variante):
    base = base.lower()
    if base in ("air", "duo", "se"):
        nome = "iPhone " + base.upper() if base == "se" else "iPhone " + base.capitalize()
    else:
        nome = "iPhone " + base  # "16", "16e"
    if variante:
        variante = re.sub(r"\s+", " ", variante.lower()).replace("promax", "pro max")
        nome += " " + variante.title()  # "Pro Max", "Plus"
    return nome


def _armazenamento(nome):
    # Pega todos os "NNN GB/TB" e fica com o que é um armazenamento de iPhone.
    # Na Mega, "8GB+128GB" tem RAM (8GB) e armazenamento (128GB): o 8GB é
    # descartado porque não está na lista de armazenamentos válidos.
    achados = []
    # Formato "6GB/128/5G" (Bristol): RAM/armazenamento, com o armazenamento sem "GB"
    m = re.search(r"\d+\s*GB\s*/\s*(\d{2,4})(?![\d.])(?!\s*(?:GB|TB))", nome, re.IGNORECASE)
    if m and "%sGB" % int(m.group(1)) in _ARMAZENAMENTOS_VALIDOS:
        return "%sGB" % int(m.group(1))
    for numero, unidade in _CAPACIDADE.findall(nome):
        valor = "%s%s" % (int(numero), unidade.upper())
        if valor in _ARMAZENAMENTOS_VALIDOS:
            achados.append(valor)
    return achados[-1] if achados else None


def _condicao(nome):
    if _CPO.search(nome):
        return "Recondicionado (CPO)"
    if _SEM_LACRE.search(nome):
        return "Sem lacre"
    return "Novo"


def _resultado(categoria, linha, modelo, variante, nome):
    return {
        "categoria": categoria,        # "celulares" ou "notebooks"
        "linha": linha,                # "iPhone", "Xiaomi", "MacBook", "Gamer"
        "modelo": modelo,              # ex.: "iPhone 16", "MacBook Air 13\" M5"
        "armazenamento": variante,     # a variação comparável entre lojas (armazenamento, SSD, placa de vídeo)
        "condicao": _condicao(nome),
        "chave": "%s %s" % (modelo, variante),
    }


def _iphone(nome):
    m = _MODELO.search(nome)
    if not m:
        return None
    armazenamento = _armazenamento(nome)
    if not armazenamento:
        return None
    return _resultado("celulares", "iPhone", _formatar_modelo(m.group(1), m.group(2)), armazenamento, nome)


# ---------- Lista de produtos: produtos.json (para monitorar um produto novo, edite só esse arquivo) ----------
import json
import os
import unicodedata as _ud

CONFIG = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "produtos.json"), encoding="utf-8"))
PRODUTOS = CONFIG["produtos"]
CATEGORIAS = CONFIG["categorias"]
MACBOOKS = {tuple(m) for p in PRODUTOS if p.get("reconhecedor") == "macbook" for m in p["modelos"]}
ROTULOS = {"armazenamento": "Armazenamento", "polegadas": "Tamanho", "gpu": "Placa de vídeo", "macbook": "Configuração"}
_GPU = re.compile(r"(?:rtx|gtx)\s*-?\s*(\d{4})|\b(3050|3060|4050|4060|4070|4080|5050|5060|5070|5080)\b", re.IGNORECASE)
_POLEGADAS = re.compile(r"\b(\d{2})(?:[.,]\d)?\s*(?:\"|”|″|\'\'|pulg|pulgadas|inch|polegadas)", re.IGNORECASE)


def _simples(texto):
    return "".join(c for c in _ud.normalize("NFD", texto.lower()) if _ud.category(c) != "Mn")


def termos_de_busca():
    """Buscas feitas em cada loja (sem repetir), na ordem do produtos.json."""
    vistos = []
    for p in PRODUTOS:
        for t in p.get("termos", []):
            if t not in vistos:
                vistos.append(t)
    return vistos


def _variacao(prod, nome, t):
    tipo = prod["variacao"]
    if tipo == "armazenamento":
        return _armazenamento(nome)
    if tipo == "gpu":
        g = _GPU.search(nome)
        if g:
            return "RTX " + (g.group(1) or g.group(2))
        return "Placa não informada" if re.search(r"notebook|laptop|gamer|gaming", t) else None
    if tipo == "polegadas":
        m = _POLEGADAS.search(nome) or (re.search(r"(\d{2})\s*-?\s*" + prod["codigo"], t) if prod.get("codigo") else None)
        if m and int(m.group(1)) in prod.get("tamanhos", [int(m.group(1))]):
            return '%d"' % int(m.group(1))
        return None
    return None


def _generico(prod, nome):
    t = _simples(nome)
    if not all(re.search(r, t) for r in prod.get("tem", [])) or any(re.search(r, t) for r in prod.get("nao_tem", [])):
        return None
    variante = _variacao(prod, nome, t)
    if not variante:
        return None
    r = _resultado(prod["categoria"], prod["linha"], prod["nome"], variante, nome)
    r["serie"], r["rotulo"] = prod.get("serie"), ROTULOS[prod["variacao"]]
    return r


# ---------- MacBook: modelos aceitos vêm do produtos.json ----------

_SSD_VALIDOS = ["256GB", "512GB", "1TB", "2TB", "4TB", "8TB"]


def _macbook(nome):
    t = nome.replace("″", '"').replace("”", '"').replace("&quot;", '"')
    tipo = re.search(r"(?:macbook|\bnb\s+apple|notebook\s+apple)\s+(air|pro)\b", t, re.IGNORECASE)  # Mega: "NB APPLE AIR"
    if not tipo:
        return None
    tipo = tipo.group(1).capitalize()
    tela = re.search(r"\b(13|14|15|16)(?:[.,]\d)?\s*(?:\"|\'\'|pulg|inch|ich|polegadas)", t, re.IGNORECASE)
    chip = re.search(r"\bM([1-5])(?:\s*(PRO|MAX))?(?!\w)", t, re.IGNORECASE)
    if not (tela and chip):
        return None
    tela, geracao, nivel = int(tela.group(1)), int(chip.group(1)), (chip.group(2) or "").capitalize()
    if (tipo, tela, geracao) not in MACBOOKS:
        return None
    ssds = [v for v in ("%s%s" % (int(n), u.upper()) for n, u in _CAPACIDADE.findall(t)) if v in _SSD_VALIDOS]
    if not ssds:
        return None
    ssd = max(ssds, key=_SSD_VALIDOS.index)
    variante = ("M%d %s · %s" % (geracao, nivel, ssd)).replace("  ", " ") if tipo == "Pro" else ssd
    return _resultado("notebooks", "MacBook", 'MacBook %s %d" M%d' % (tipo, tela, geracao), variante, nome)



def normalizar(nome):
    """Devolve dict(categoria, linha, modelo, armazenamento, condicao, chave, serie, rotulo) ou None.
    Os produtos são testados na ordem do produtos.json; vale o primeiro que reconhecer o nome."""
    if not nome or _ACESSORIOS.search(nome):
        return None
    for prod in PRODUTOS:
        especial = prod.get("reconhecedor")
        if especial == "iphone":
            r = _iphone(nome)
            rotulo = "Armazenamento"
        elif especial == "macbook":
            r = _macbook(nome)
            rotulo = "Configuração"
        else:
            r = _generico(prod, nome)
            rotulo = r and r["rotulo"]
        if r:
            r.setdefault("serie", None)
            r["rotulo"] = rotulo
            return r
    return None


# --------------------------------------------------------------------------
# Cor: as lojas escrevem a cor dentro do nome, em inglês ou espanhol.
# Cada cor oficial da Apple tem a lista de jeitos como ela aparece nos sites.
# Para incluir um novo jeito de escrever, basta acrescentar na lista.
# (A ordem importa: nomes compostos, como "Deep Blue", vêm antes de "Blue".)
# --------------------------------------------------------------------------
import unicodedata

_CORES = [
    ("Cosmic Orange",    ["cosmic orange", "cos or", "naranja cosmico", "naranja", "orange", "orang"]),
    ("Deep Blue",        ["deep blue", "dee blu", "d bl", "azul profundo"]),
    ("Mist Blue",        ["mist blue", "azul bruma"]),
    ("Sky Blue",         ["sky blue", "azul cielo"]),
    ("Sierra Blue",      ["sierra blue", "azul sierra"]),
    ("Night Sky",        ["night sky", "azul noche"]),
    ("Star White",       ["star white"]),
    ("Cloud White",      ["cloud white", "blanco nube"]),
    ("Light Gold",       ["light gold", "dorado claro"]),
    ("Space Black",      ["space black", "negro espacial"]),
    ("Glacier",          ["azul glaciar", "glacier", "glaciar"]),
    ("Burgundy",         ["burgundy", "burdundy", "borgona", "dark cherry", "cereza", "cherry"]),
    ("Desert Titanium",  ["desert", "desierto"]),
    ("Natural Titanium", ["natural"]),
    ("White Titanium",   ["white titanium", "titanium blanco", "titanio blanco"]),
    ("Black Titanium",   ["black titanium", "titanium negro", "titanio negro"]),
    ("Blue Titanium",    ["blue titanium", "titanium azul", "titanio azul"]),
    ("Ultramarine",      ["ultramarine", "ultramar"]),
    ("Teal",             ["verde azulado", "teal"]),
    ("Lavender",         ["lavender", "lavander", "lavanda"]),
    ("Sage",             ["sage", "salvia"]),
    ("Deep Purple",      ["deep purple", "morado oscuro"]),
    ("Midnight",         ["midnight", "medianoche"]),
    ("Starlight",        ["starlight", "blanco estelar", "luz estelar"]),
    ("Graphite",         ["graphite", "grafito"]),
    ("Purple",           ["purple", "morado", "lila"]),
    ("Yellow",           ["yellow", "amarillo"]),
    ("Green",            ["green", "verde"]),
    ("Red",              ["red", "rojo"]),
    ("Gold",             ["gold", "dorado"]),
    ("Silver",           ["silver", "plateado", "plata"]),
    ("Pink",             ["soft pink", "pink", "rosa"]),
    ("Blue",             ["blue", "azul"]),
    ("White",            ["white", "blanco"]),
    ("Black",            ["black", "negro"]),
]
_CORES_RE = [(nome, re.compile(r"\b(" + "|".join(re.escape(a) for a in aliases) + r")\b")) for nome, aliases in _CORES]


def _sem_acento(texto):
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")


def cor_canonica(texto):
    """Devolve o nome oficial da cor (ex.: "Cosmic Orange") ou None se não reconhecer."""
    t = _sem_acento((texto or "").lower())
    for nome, rx in _CORES_RE:
        if rx.search(t):
            return nome
    return None


if __name__ == "__main__":
    # Teste rápido: python3 normalizar.py
    exemplos = [
        "Apple iPhone 16 A3287 128 GB - Azul",
        'CEL IPHONE 16 6.1" 8GB+128GB A3287 BLACK',
        "CELULAR APPLE IPHONE 16 128GB PINK CPO",
        'CEL IPHONE 18 PRO ESIM 6.3"  12GB+256GB A3472(S/LACRE) GLACIER(LL)',
        "Apple iPhone 17 Pro Max A3257 Dual 1 TB - Naranja Cósmico",
        'CEL IPHONE 17 DUAL 6.3" 8GB+256GB A3521 WHITE',
        "CELULAR APPLE IPHONE 16E 128GB BLACK CPO",
        "Apple iPhone Air A3517 5G Dual 512 GB - Sky Blue",
        'CEL IPHONE DUO ESIM 7.6"  12GB+512GB A3447 NIGHT SKY(LL)',
        "CAPA PROTECTORA 4LIFE IPHONE 17 CLEAR",
        "Correa Crossbody Apple para Iphone",
    ]
    for e in exemplos:
        print("%-70s -> %s" % (e, normalizar(e)))
