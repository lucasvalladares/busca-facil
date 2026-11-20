"""
Reforço pelo Mac: quando a coleta do robô (GitHub) falha numa loja, o Mac tenta coletar essa loja.

Roda sozinho (launchd, arquivo com.buscafacil.reforco.plist) ao ligar/entrar no Mac e a cada 30 min
enquanto ele estiver acordado. Se o Mac estiver desligado na hora da falha, a tentativa fica
"pendente" e acontece na próxima vez que ele ligar (no mesmo dia).

A cada execução:
  1. pega o banco mais novo do GitHub (git pull);
  2. vê as lojas que falharam HOJE na coleta do robô e ainda não têm coleta com sucesso hoje;
     (se até as 8h o robô não rodou nada hoje, considera que todas falharam)
  3. coleta cada uma pelo Mac (mesmas regras de educação; uma tentativa por loja por dia —
     se o Mac também falhar, só no dia seguinte);
  4. se trouxe preços: grava o banco no GitHub e pede a publicação do site; avisa no celular.

    python3 reforco_mac.py            # o que o launchd roda
    python3 reforco_mac.py --ver      # só mostra o que faria (não acessa lojas)
"""

import json
import os
import sqlite3
import subprocess
import sys
from datetime import datetime

PASTA = os.path.dirname(os.path.abspath(__file__))
BANCO = os.path.join(PASTA, "precos.db")
ESTADO = os.path.join(PASTA, "reforco-mac.json")        # local (não vai para o GitHub): tentativas do dia
TOPICO = os.path.join(PASTA, ".ntfy-topico")            # local: tópico do aviso no celular
LOG = os.path.join(PASTA, "reforco-mac.log")
HORA_ROBO_ATRASADO = 8   # se até esta hora o robô não coletou nada hoje, o Mac faz a coleta inteira
REPO = "lucasvalladares/busca-facil"


def log(msg):
    linha = "%s %s" % (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg)
    if sys.stdout.isatty():   # no launchd a saída já vai para o mesmo arquivo de log: não repetir
        print(linha)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(linha + "\n")


def rodar(cmd, **kw):
    return subprocess.run(cmd, cwd=PASTA, capture_output=True, text=True, **kw)


def avisar(titulo, msg):
    """Notificação no Mac e, se houver o tópico local, no celular (ntfy)."""
    rodar(["osascript", "-e", 'display notification "%s" with title "%s"' % (msg.replace('"', "'")[:200], titulo)])
    if os.path.exists(TOPICO):
        import urllib.request
        corpo = json.dumps({"topic": open(TOPICO).read().strip(), "title": titulo, "message": msg, "priority": 2,
                            "click": "https://lucasvalladares.github.io/busca-facil/painel.html"}).encode("utf-8")
        try:
            urllib.request.urlopen(urllib.request.Request("https://ntfy.sh/", data=corpo,
                                                          headers={"Content-Type": "application/json"}), timeout=20)
        except Exception as e:
            log("aviso no celular falhou: %s" % e)


def lojas_para_reforcar(hoje, agora):
    import coletor
    todas = [l for l, _ in coletor.LOJAS]
    con = sqlite3.connect(BANCO)
    linhas = con.execute("SELECT loja, erro, itens FROM coletas WHERE substr(data_hora, 1, 10) = ?", (hoje,)).fetchall()
    con.close()
    if not linhas:
        return todas if agora.hour >= HORA_ROBO_ATRASADO else []   # robô ainda não rodou (ou não rodou hoje)
    ok = {l for l, erro, itens in linhas if erro is None and itens > 0}
    falhou = {l for l, erro, _ in linhas if erro is not None}
    return [l for l in todas if l in falhou and l not in ok]


def main():
    ver = "--ver" in sys.argv
    agora = datetime.now()
    hoje = agora.strftime("%Y-%m-%d")
    estado = json.load(open(ESTADO)) if os.path.exists(ESTADO) else {}
    tentadas = estado.get(hoje, {})

    r = rodar(["git", "pull", "-q", "--rebase"])
    if r.returncode != 0:
        log("git pull falhou (alterações locais?): %s" % r.stderr.strip()[:200])
        return
    pendentes = [l for l in lojas_para_reforcar(hoje, agora) if l not in tentadas]
    if not pendentes:
        if ver:
            print("Nada a fazer agora (hoje: %s; já tentadas pelo Mac: %s)." % (hoje, ", ".join(tentadas) or "nenhuma"))
        return
    log("Lojas para coletar pelo Mac: %s" % ", ".join(pendentes))
    if ver:
        return

    import coletor
    resultado = {}
    for loja in sorted(pendentes, key=lambda l: l in coletor.POR_ULTIMO):   # Tecnostore por último
        tentadas[loja] = agora.strftime("%H:%M")
        estado = {hoje: tentadas}   # guarda já (se o Mac dormir no meio, não repete a loja hoje)
        json.dump(estado, open(ESTADO, "w"))
        r = rodar(["caffeinate", "-i", sys.executable, "coletor.py", "--real", "--loja", loja,
                   "--ignorar-pausa", "--sem-publicar"], timeout=1800)
        linha = next((x for x in r.stdout.splitlines() if x.startswith(loja)), "")
        sucesso = linha.rstrip().endswith("ok")
        log("%s: %s" % (loja, linha.strip() or r.stdout[-300:]))
        if "MAC DORMIU" in linha:   # a loja não teve culpa: tenta de novo na próxima vez que o Mac estiver acordado
            tentadas.pop(loja, None)
            json.dump({hoje: tentadas}, open(ESTADO, "w"))
            log("%s: o Mac dormiu durante a coleta — nova tentativa na próxima execução" % loja)
            continue
        resultado[loja] = sucesso

    ok = [l for l, s in resultado.items() if s]
    falha = [l for l, s in resultado.items() if not s]
    # grava SEMPRE o banco no GitHub (também as tentativas que falharam): assim o banco deste Mac nunca fica
    # com alterações pendentes que travariam o próximo "git pull"
    if rodar(["git", "status", "--porcelain", "precos.db"]).stdout.strip():
        rodar(["git", "add", "precos.db", "fotos"])
        rodar(["git", "commit", "-q", "-m", "Reforço pelo Mac %s: %s" % (agora.strftime("%d/%m/%Y %H:%M"),
              "; ".join(x for x in ["ok: " + ", ".join(ok) if ok else "", "falhou: " + ", ".join(falha) if falha else ""] if x)
              or "Mac dormiu")])
        r = rodar(["git", "pull", "-q", "--rebase"])
        r = rodar(["git", "push", "-q"]) if r.returncode == 0 else r
        if r.returncode != 0:
            log("não consegui enviar ao GitHub: %s" % r.stderr.strip()[:300])
            avisar("Busca Fácil: reforço pelo Mac", "Coletei %s, mas não consegui enviar ao GitHub." % ", ".join(ok))
            return
        if ok:
            rodar(["gh", "workflow", "run", "coleta.yml", "-R", REPO, "-f", "modo=so-publicar"])
    if not resultado:
        return
    msg = ("Atualizadas pelo Mac: %s." % ", ".join(ok) if ok else "") + \
          (" Também falharam pelo Mac: %s (nova tentativa amanhã)." % ", ".join(falha) if falha else "")
    log(msg.strip())
    avisar("Busca Fácil: reforço pelo Mac" + (" ✅" if not falha else " ⚠️"), msg.strip())


if __name__ == "__main__":
    os.chdir(PASTA)
    sys.path.insert(0, PASTA)
    main()
