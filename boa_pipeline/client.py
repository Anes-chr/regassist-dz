"""Client HTTP poli : robots.txt, délai, retries, requêtes conditionnelles."""
import random
import time
from collections import Counter
from urllib import robotparser
from urllib.parse import urlsplit, urlunsplit, unquote

import requests
try:  # magasin de certificats du système (le serveur n'envoie pas son certificat intermédiaire)
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

from . import config as C


def normalize_url(url: str) -> str:
    """Normalise : sans fragment, hôte en minuscules, hôte canonique www."""
    p = urlsplit(url.strip())
    host = (p.hostname or "").lower()
    if host == "bank-of-algeria.dz":
        host = C.HOST
    scheme = "https" if host == C.HOST else p.scheme
    return urlunsplit((scheme, host, p.path or "/", p.query, ""))


def ext_of(url: str) -> str:
    path = unquote(urlsplit(url).path)
    return path.rsplit(".", 1)[-1].lower() if "." in path.rsplit("/", 1)[-1] else ""


class Client:
    RECYCLE_EVERY = 100          # connexion neuve toutes les N requêtes : une connexion keep-alive longue finit par recevoir des HTTP 500 (mesuré, 6 oct. 2026)

    def _new_session(self):
        s = requests.Session()
        s.headers.update({"User-Agent": C.USER_AGENT, "Accept-Language": "fr,ar;q=0.8,en;q=0.5"})
        return s

    def _reset(self):
        try:
            self.s.close()
        except Exception:
            pass
        self.s = self._new_session()

    def __init__(self, delay: float = C.REQUEST_DELAY):
        self.s = self._new_session()
        self.n_req = 0
        self.delay = delay
        self._last = 0.0
        self.rp = robotparser.RobotFileParser()
        self.stats = Counter()
        self._load_robots()

    def _load_robots(self):
        try:
            r = self.s.get(C.BASE + "/robots.txt", timeout=C.TIMEOUT)
            self.robots_txt = r.text
            self.rp.parse(r.text.splitlines())
        except Exception as e:  # robots injoignable => prudence : on n'explore que ce qui est évident
            self.robots_txt = f"<erreur: {e}>"
            self.rp.parse(["User-agent: *", "Disallow: /wp-admin/"])

    def allowed(self, url: str) -> bool:
        return self.rp.can_fetch(C.USER_AGENT, url) and self.rp.can_fetch("*", url)

    def _wait(self):
        dt = time.time() - self._last
        if dt < self.delay:
            time.sleep(self.delay - dt + random.uniform(0, 0.15))
        self._last = time.time()

    def request(self, method: str, url: str, headers=None, stream=False):
        if not self.allowed(url):
            self.stats["blocked_by_robots"] += 1
            return None
        last_err = None
        for attempt in range(C.RETRIES):
            self._wait()
            self.n_req += 1
            if self.n_req % self.RECYCLE_EVERY == 0:
                self._reset()
            try:
                r = self.s.request(method, url, headers=headers, timeout=C.TIMEOUT,
                                   allow_redirects=True, stream=stream)
                self.stats[f"http_{r.status_code}"] += 1
                if r.status_code in (429, 500, 502, 503, 504) and attempt < C.RETRIES - 1:  # surcharge serveur : on ralentit (backoff), on ne contourne rien
                    self._reset()                                           # nouvelle connexion avant de réessayer (la connexion en cours peut être la cause)
                    time.sleep(8 * (attempt + 1) if r.status_code in (429, 503) else 3)
                    continue
                return r
            except requests.RequestException as e:
                last_err = e
                self._reset()
                self.stats["network_error"] += 1
                time.sleep(2 * (attempt + 1))
        self.last_error = str(last_err)
        return None

    def get(self, url, headers=None, stream=False):
        return self.request("GET", url, headers, stream)

    def head(self, url):
        return self.request("HEAD", url)
