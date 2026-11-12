"""
Dados de TESTE: cria preços INVENTADOS para os 6 meses antes da primeira
coleta real, para ver como gráficos, etiquetas e selos se comportam com histórico.

    python3 simular.py           # cria uma CÓPIA de teste (pasta teste/) com 6 meses inventados
    python3 simular.py --apagar  # apaga a pasta teste/

Os dados inventados NUNCA entram no banco real (precos.db) nem no site publicado:
ficam só na pasta teste/, numa cópia do banco, com páginas próprias.

É sempre a mesma simulação (mesma "semente" do sorteio, mesmo período,
mesmos arredondamentos), igual à usada da primeira vez:
  - preço parado por semanas, mudando em "degraus";
  - Nissei: pequena oscilação diária (câmbio);
  - promoções sazonais do Paraguai (nem toda loja participa de todas);
  - queda dos modelos antigos quando o iPhone 18 é lançado (setembro);
  - iPhone 18 e Duo só existem a partir do lançamento, começando mais caros;
  - alguns dias sem estoque;
  - perfis para testar as etiquetas: alguns modelos aparecem hoje como baratos,
    outros como caros e o resto como preço normal (ver PERFIS).
"""

import os
import random
import shutil
import sys
from datetime import date, timedelta

from coletor import abrir_banco
from normalizar import normalizar

MESES = 6
PROMOCOES = [  # (início, fim, desconto, nome)
    (date(2026, 5, 13), date(2026, 5, 15), 0.05, "Independência"),
    (date(2026, 6, 8), date(2026, 6, 14), 0.08, "Dia dos Pais"),
    (date(2026, 8, 20), date(2026, 8, 23), 0.06, "Aniversário da loja"),
    (date(2026, 10, 5), date(2026, 10, 7), 0.10, "Cyber Day"),
]
# Para testar as etiquetas da página 1: nas ~6 semanas antes da 1ª coleta real, alguns modelos
# ficam mais caros (hoje parece BARATO) e outros mais baratos (hoje parece CARO). Os demais: normal.
PERFIS = {
    "barato": ({"iPhone 17", "iPhone 16 Pro", "iPhone 16e", "iPhone 15", "iPhone 13"}, 1.18),
    "caro": ({"iPhone 18 Pro Max", "iPhone 17 Pro", "iPhone 16", "iPhone Air", "iPhone 14 Plus"}, 0.85),
}
DIAS_PERFIL = 45
LANCAMENTO_18 = date(2026, 9, 25)
LANCAMENTO_DUO = date(2026, 10, 23)


def primeira_coleta_real(con):
    r = con.execute("SELECT MIN(substr(data_hora, 1, 10)) FROM coletas").fetchone()[0]
    if not r:
        sys.exit("Rode uma coleta real primeiro: python3 coletor.py")
    return r


def _arredondar(loja, usd):
    return round(usd, 2) if loja == "Nissei" else float(int(round(usd / 5.0)) * 5)


def _serie(loja, modelo, usd_hoje, dias, rnd):
    if modelo.startswith("iPhone Duo"):
        inicio = LANCAMENTO_DUO
    elif modelo.startswith("iPhone 18"):
        inicio = LANCAMENTO_18
    else:
        inicio = dias[0]
    if inicio != dias[0]:
        inicio += timedelta(days=rnd.randint(0, 4))
    dias = [d for d in dias if d >= inicio]
    if not dias:
        return []
    nivel, fator, proxima = {}, 1.0, rnd.randint(5, 20)
    for k, d in enumerate(reversed(dias)):          # degraus, de trás para frente
        if k == proxima:
            fator *= 1 + (1 if rnd.random() < 0.55 else -1) * rnd.uniform(0.005, 0.025)
            proxima = k + rnd.randint(7, 28)
        nivel[d] = fator
    serie, sem_estoque_ate = [], None
    participa = {nome: rnd.random() < 0.65 for _, _, _, nome in PROMOCOES}
    novo = modelo.startswith(("iPhone 18", "iPhone Duo"))
    for d in dias:
        f = nivel[d]
        if not novo and d < LANCAMENTO_18:
            f *= 1.06
        if novo:
            f *= 1 + 0.10 * max(0.0, 1 - (d - dias[0]).days / 35.0)
        for ini, fim, desc, nome in PROMOCOES:
            if participa[nome] and ini <= d <= fim:
                f *= 1 - desc * rnd.uniform(0.7, 1.0)
        if loja == "Nissei":
            f *= 1 + rnd.uniform(-0.004, 0.004)
        if sem_estoque_ate and d <= sem_estoque_ate:
            continue
        if rnd.random() < 0.005:
            sem_estoque_ate = d + timedelta(days=rnd.randint(2, 6))
            continue
        serie.append((d, _arredondar(loja, usd_hoje * f)))
    return serie


PASTA = os.path.dirname(os.path.abspath(__file__))
TESTE = os.path.join(PASTA, "teste")                     # tudo o que é inventado fica SÓ aqui
BANCO_TESTE = os.path.join(TESTE, "precos-teste.db")


def main():
    # REGRA: dados inventados nunca entram no banco real (precos.db) nem no site publicado.
    # O simulador trabalha numa CÓPIA, na pasta teste/, que pode ser apagada a qualquer momento.
    if "--apagar" in sys.argv:
        shutil.rmtree(TESTE, ignore_errors=True)
        print("Pasta teste/ apagada. O banco real e o site não foram tocados.")
        return
    os.makedirs(TESTE, exist_ok=True)
    shutil.copyfile(os.path.join(PASTA, "precos.db"), BANCO_TESTE)
    for pasta in ("fotos", "fontes"):   # as páginas de teste usam as mesmas fotos e fontes
        if not os.path.exists(os.path.join(TESTE, pasta)):
            os.symlink(os.path.join(PASTA, pasta), os.path.join(TESTE, pasta))
    con = abrir_banco(BANCO_TESTE)
    primeira = primeira_coleta_real(con)
    taxa = con.execute("SELECT gs_por_usd FROM cambio WHERE data = ?", (primeira,)).fetchone()[0]
    fim = date.fromisoformat(primeira) - timedelta(days=1)
    ini = date(fim.year if fim.month > MESES else fim.year - 1, (fim.month - MESES - 1) % 12 + 1, fim.day)
    dias = [ini + timedelta(days=i) for i in range((fim - ini).days + 1)]

    # Ponto de partida: menor preço de cada loja + variante (modelo, armazenamento, condição) no 1º dia real
    base = {}
    for loja, nome, preco, link in con.execute(
            "SELECT loja, nome, preco_gs, link FROM ofertas WHERE data = ? AND em_estoque = 1", (primeira,)):
        n = normalizar(nome)
        if not n:
            continue
        k = (loja, n["modelo"], n["armazenamento"], n["condicao"])
        if k not in base or preco < base[k][0]:
            base[k] = (preco, nome, link, n["chave"])

    rnd = random.Random(2026)
    linhas = []
    for (loja, modelo, _arm, _cond), (preco, nome, link, chave) in sorted(base.items()):
        usd_hoje = preco / taxa
        fator = next((f for modelos, f in PERFIS.values() if modelo in modelos), 1.0)
        for d, usd in _serie(loja, modelo, usd_hoje, dias, rnd):
            if fator != 1.0 and (fim - d).days < DIAS_PERFIL:
                usd = _arredondar(loja, usd * fator)
            linhas.append((d.isoformat(), loja, nome, chave, int(round(usd * taxa)), 1, link))
    con.executemany("INSERT INTO ofertas VALUES (?,?,?,?,?,?,?)", linhas)
    con.commit()
    con.close()
    print("%d preços inventados (%s a %s) — só na cópia teste/precos-teste.db" % (
        len(linhas), dias[0].strftime("%d/%m/%Y"), fim.strftime("%d/%m/%Y")))

    import pagina
    pagina.BANCO, pagina.PASTA_SAIDA = BANCO_TESTE, TESTE
    for caminho in pagina.gerar():
        print("Página de teste: %s" % caminho)
    print("Abra: open teste/relatorio-vibrante.html  (não é publicada; o site e o banco real não mudam)")


if __name__ == "__main__":
    main()
