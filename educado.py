"""
Cliente "educado": a única forma de o coletor acessar as lojas.

Regras (valem para cada loja separadamente):
  1. Ritmo: no máximo 1 pedido a cada 3–5 segundos (sorteado). Se o robots.txt
     da loja pedir um intervalo maior (Crawl-delay), vale o maior.
  2. robots.txt: lido no primeiro pedido a cada site; endereços proibidos para
     o nosso robô não são acessados (ficam registrados no log).
  3. User-agent honesto, com o nome do projeto, o site e um e-mail de contato.
  4. Erro 403, 429, 5xx, falha de conexão ou resposta que demore mais de 20s:
     a loja PARA na hora (exceção Parada). Quem chama registra e não tenta de
     novo no mesmo dia.
     Exceção: se o próprio Mac dormiu durante o pedido (exceção Dormiu), a culpa
     não é da loja: ela não é pausada e o dia incompleto não é publicado.
  5. Cópias (fixtures/): no modo real, cada resposta é guardada em fixtures/<loja>/.
     No modo de desenvolvimento (padrão), as respostas vêm SÓ dessas cópias
     e nenhum site é acessado.
"""

import hashlib
import json
import os
import random
import re
import threading
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit

PASTA = os.path.dirname(os.path.abspath(__file__))
FIXTURES = os.path.join(PASTA, "fixtures")

ROBO = "BuscaFacilBot"
USER_AGENT = "%s/1.0 (+https://lucasvalladares.github.io/busca-facil/; lucas.valladaresm@gmail.com)" % ROBO
INTERVALO = (3.0, 5.0)   # segundos entre pedidos à mesma loja
LIMITE_SEGUNDOS = 20     # resposta mais lenta que isso = parar a loja


class Parada(Exception):
    """A loja deve parar agora (erro 403/429/5xx, falha de conexão, lentidão)."""


class Dormiu(Exception):
    """O computador dormiu durante o pedido: a culpa não é da loja (não pausar, não publicar)."""


def _dormido(inicio_relogio, inicio_mono):
    """Segundos em que o Mac dormiu desde o início do pedido. O relógio comum (time.time) anda
    durante o sono; o monotônico do macOS não. A diferença entre os dois é o tempo dormindo."""
    return (time.time() - inicio_relogio) - (time.monotonic() - inicio_mono)


SONO_TOLERADO = 5   # segundos


class SemCopia(Exception):
    """Modo de desenvolvimento: não existe cópia salva para este pedido."""


def _slug(texto):
    return re.sub(r"[^a-z0-9]+", "-", texto.lower()).strip("-")


# --------------------------------------------------------------------------
# robots.txt (regras no formato do Google: *, $ e a regra mais específica vence)
# --------------------------------------------------------------------------

def ler_robots(texto):
    """Devolve (regras, crawl_delay) do grupo que se aplica ao nosso robô (ou ao grupo "*")."""
    grupos, atuais, em_regras = [], [], False
    for linha in texto.splitlines():
        linha = linha.split("#", 1)[0].strip()
        if ":" not in linha:
            continue
        campo, valor = [x.strip() for x in linha.split(":", 1)]
        campo = campo.lower()
        if campo == "user-agent":
            if em_regras or not grupos:
                grupos.append({"agentes": [], "regras": [], "delay": None})
                em_regras = False
            grupos[-1]["agentes"].append(valor.lower())
        elif grupos and campo in ("allow", "disallow"):
            em_regras = True
            grupos[-1]["regras"].append((campo == "allow", valor))
        elif grupos and campo == "crawl-delay":
            em_regras = True
            try:
                grupos[-1]["delay"] = float(valor)
            except ValueError:
                pass
    nosso = [g for g in grupos if any(a and a != "*" and a in ROBO.lower() for a in g["agentes"])]
    geral = [g for g in grupos if "*" in g["agentes"]]
    escolhidos = nosso or geral
    regras = [r for g in escolhidos for r in g["regras"]]
    delays = [g["delay"] for g in escolhidos if g["delay"]]
    return regras, (max(delays) if delays else None)


def permitido(regras, caminho):
    """caminho = path + "?" + query. A regra mais longa que casar decide; empate: Allow vence."""
    melhor = None  # (tamanho, permite)
    for permite, padrao in regras:
        if not padrao:
            continue  # "Disallow:" vazio = sem restrição
        rx = "^" + re.escape(padrao).replace(r"\*", ".*")
        if rx.endswith(r"\$"):
            rx = rx[:-2] + "$"
        if re.match(rx, caminho):
            chave = (len(padrao), permite)
            if melhor is None or chave > melhor:
                melhor = chave
    return True if melhor is None else melhor[1]


# --------------------------------------------------------------------------
# Cliente de uma loja
# --------------------------------------------------------------------------

class Cliente:
    def __init__(self, loja, real, log):
        self.loja, self.real, self.log = loja, real, log
        self.pedidos = 0          # pedidos feitos à internet (inclui robots.txt)
        self.pulados = 0          # endereços não acessados por causa do robots.txt
        self._ultimo = 0.0
        self._robots = {}         # site -> (regras, delay)
        self._trava = threading.Lock()
        self._pasta = os.path.join(FIXTURES, _slug(loja))

    # ---- cópias ----
    def _arquivo(self, url, dados):
        chave = hashlib.sha1(("%s\n%s" % (url, dados or "")).encode("utf-8")).hexdigest()[:20]
        return os.path.join(self._pasta, chave + ".txt")

    def _guardar(self, url, dados, texto):
        os.makedirs(self._pasta, exist_ok=True)
        arq = self._arquivo(url, dados)
        with open(arq, "w", encoding="utf-8") as f:
            f.write(texto)
        indice = os.path.join(self._pasta, "indice.json")
        mapa = json.load(open(indice, encoding="utf-8")) if os.path.exists(indice) else {}
        mapa[os.path.basename(arq)] = {"url": url, "dados": dados, "salvo": time.strftime("%Y-%m-%d %H:%M")}
        with open(indice, "w", encoding="utf-8") as f:
            json.dump(mapa, f, ensure_ascii=False, indent=1)

    # ---- acesso à internet ----
    def _esperar_vez(self, extra=None):
        intervalo = max(random.uniform(*INTERVALO), extra or 0)
        espera = self._ultimo + intervalo - time.time()
        if espera > 0:
            time.sleep(espera)

    def _baixar(self, url, dados=None, cabecalhos=None, delay=None):
        self._esperar_vez(delay)
        cab = {"User-Agent": USER_AGENT, "Accept-Language": "es-PY,es;q=0.9"}
        cab.update(cabecalhos or {})
        inicio, inicio_mono = time.time(), time.monotonic()
        self.pedidos += 1
        try:
            req = urllib.request.Request(url, data=dados.encode("utf-8") if dados is not None else None, headers=cab)
            with urllib.request.urlopen(req, timeout=LIMITE_SEGUNDOS) as resp:
                texto = resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            if e.code in (403, 429) or e.code >= 500:
                raise Parada("HTTP %d em %s" % (e.code, url))
            raise
        except Exception as e:  # falha de conexão, tempo esgotado etc.
            self._checar_sono(inicio, inicio_mono, url)
            raise Parada("%s em %s" % (type(e).__name__, url))
        finally:
            self._ultimo = time.time()
        self._checar_sono(inicio, inicio_mono, url)
        if time.time() - inicio > LIMITE_SEGUNDOS:
            raise Parada("resposta levou %.0fs (> %ds) em %s" % (time.time() - inicio, LIMITE_SEGUNDOS, url))
        return texto

    def _checar_sono(self, inicio, inicio_mono, url):
        dormiu = _dormido(inicio, inicio_mono)
        if dormiu > SONO_TOLERADO:
            raise Dormiu("o computador dormiu %.0fs durante o pedido a %s" % (dormiu, url))

    def _regras_do_site(self, site):
        if site not in self._robots:
            url = site + "/robots.txt"
            try:
                texto = self._baixar(url) if self.real else self._copia(url, None)
                if self.real:
                    self._guardar(url, None, texto)
            except urllib.error.HTTPError:   # sem robots.txt (404 etc.) = sem restrições
                texto = ""
            self._robots[site] = ler_robots(texto)
        return self._robots[site]

    def _copia(self, url, dados):
        arq = self._arquivo(url, dados)
        if not os.path.exists(arq):
            raise SemCopia("sem cópia salva para %s (rode uma vez: python3 coletor.py --real)" % url)
        with open(arq, encoding="utf-8") as f:
            return f.read()

    def baixar_arquivo(self, url):
        """Bytes de um arquivo (ex.: foto), com as mesmas regras (ritmo, robots, user-agent). Só no modo real."""
        if not self.real:
            raise SemCopia("modo de teste: não baixa arquivos")
        with self._trava:
            partes = urlsplit(url)
            regras, delay = self._regras_do_site("%s://%s" % (partes.scheme, partes.netloc))
            if not permitido(regras, partes.path + ("?" + partes.query if partes.query else "")):
                self.pulados += 1
                self.log("   %s: arquivo proibido pelo robots.txt, não baixado: %s" % (self.loja, url))
                return None, None
            self._esperar_vez(delay)
            self.pedidos += 1
            inicio, inicio_mono = time.time(), time.monotonic()
            try:
                req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(req, timeout=LIMITE_SEGUNDOS) as resp:
                    return resp.read(), resp.headers.get("Content-Type", "")
            except urllib.error.HTTPError as e:
                if e.code in (403, 429) or e.code >= 500:
                    raise Parada("HTTP %d em %s" % (e.code, url))
                raise
            except Exception as e:
                self._checar_sono(inicio, inicio_mono, url)
                raise Parada("%s em %s" % (type(e).__name__, url))
            finally:
                self._ultimo = time.time()
                if time.time() - inicio > LIMITE_SEGUNDOS:
                    raise Parada("resposta levou mais de %ds em %s" % (LIMITE_SEGUNDOS, url))

    def get(self, url, dados=None, cabecalhos=None):
        """Texto da resposta, ou None se o robots.txt proíbe o endereço."""
        with self._trava:  # um pedido por vez por loja
            partes = urlsplit(url)
            regras, delay = self._regras_do_site("%s://%s" % (partes.scheme, partes.netloc))
            caminho = partes.path + ("?" + partes.query if partes.query else "")
            if not permitido(regras, caminho or "/"):
                self.pulados += 1
                self.log("   %s: endereço proibido pelo robots.txt, não acessado: %s" % (self.loja, url))
                return None
            if not self.real:
                return self._copia(url, dados)
            texto = self._baixar(url, dados, cabecalhos, delay)
            self._guardar(url, dados, texto)
            return texto
