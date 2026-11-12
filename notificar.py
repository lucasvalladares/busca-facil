"""
Aviso no celular ao fim de cada coleta no GitHub (sucesso, problema ou falha), pelo ntfy.sh
(serviço gratuito de notificações: app "ntfy" no iPhone/Android, assinando o tópico secreto).

O nome do tópico fica no segredo NTFY_TOPICO do GitHub (não aparece no código público).
O aviso leva só números (produtos, lojas, duração, quantos preços mudaram) — nenhum dado pessoal.

    NTFY_TOPICO=... STATUS=success python3 notificar.py
"""

import json
import os
import urllib.request

PASTA = os.path.dirname(os.path.abspath(__file__))
PAINEL = "https://lucasvalladares.github.io/busca-facil/painel.html"


def _duracao(s):
    return "%d s" % s if s < 60 else "%d min %02d s" % (s // 60, s % 60)


def montar_aviso(status):
    arq = os.path.join(PASTA, "ultima-coleta.json")
    if status != "success" or not os.path.exists(arq):
        return ("❌ Busca Fácil: a coleta FALHOU",
                "A execução no GitHub parou com erro. Toque para ver os detalhes.", "high", os.environ.get("RUN_URL") or PAINEL)
    r = json.load(open(arq, encoding="utf-8"))
    linha = "%d produtos · %d de %d lojas ok · %s" % (r["produtos"], r["lojas_ok"], r["lojas"], _duracao(r["segundos"]))
    try:
        import painel
        dias = painel.montar()["dias"]
        if dias and dias[0]["data"] == r["data"]:
            linha += "\nPreços: %d subiram · %d baixaram · %d misto" % (dias[0]["subiu"], dias[0]["baixou"], dias[0]["misto"])
    except Exception:
        pass
    if r["problemas"]:
        lojas = ", ".join(p["loja"] for p in r["problemas"])
        return ("⚠️ Busca Fácil: coleta com problema em %d loja(s)" % len(r["problemas"]),
                linha + "\nCom problema: " + lojas, "default", PAINEL)
    return ("✅ Busca Fácil: coleta OK", linha, "low", PAINEL)


def main():
    topico = os.environ.get("NTFY_TOPICO")
    titulo, msg, prioridade, link = montar_aviso(os.environ.get("STATUS", "success"))
    print(titulo + "\n" + msg)
    if not topico:
        print("Aviso: sem o segredo NTFY_TOPICO — nada enviado.")
        return
    corpo = json.dumps({"topic": topico, "title": titulo, "message": msg, "priority": {"low": 2, "default": 3, "high": 5}[prioridade],
                        "click": link}).encode("utf-8")
    req = urllib.request.Request("https://ntfy.sh/", data=corpo, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        print("Aviso enviado (HTTP %d)." % resp.status)


if __name__ == "__main__":
    main()
