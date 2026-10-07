"""Index BM25 (implémentation locale, sans dépendance) sur corpus/chunks/chunks_fr.jsonl + métadonnées des textes."""
import hashlib
import os
import json
import math
import pickle
from collections import Counter, defaultdict
from pathlib import Path

from .refs import num_key
from .textproc import tokens

ROOT = Path(__file__).resolve().parent.parent
# AGENT_CORPUS_DIR : dossier plat contenant chunks_fr.jsonl et documents_fr.json (instantané figé pour les évaluations).
# Par défaut : le corpus vivant (corpus/chunks, corpus/metadata).
_SNAP = os.environ.get("AGENT_CORPUS_DIR")
if _SNAP:
    CHUNKS = Path(_SNAP) / "chunks_fr.jsonl"
    DOCS = Path(_SNAP) / "documents_fr.json"
else:
    CHUNKS = ROOT / "corpus" / "chunks" / "chunks_fr.jsonl"
    DOCS = ROOT / "corpus" / "metadata" / "documents_fr.json"
CACHE = Path(__file__).resolve().parent / ".cache" / f"index_{hashlib.sha1(str(CHUNKS).encode()).hexdigest()[:8]}.pkl"
K1, B = 1.4, 0.75


class Index:
    def __init__(self, chunks: list[dict], docs: list[dict]):
        self.chunks = chunks
        self.docs = {d["document_id"]: d for d in docs}
        self.work_docs = defaultdict(list)
        for d in docs:
            self.work_docs[d["work_id"]].append(d["document_id"])
        self.tf, self.dl = [], []
        df = Counter()
        for c in chunks:
            toks = tokens(c["text_with_context"])
            cnt = Counter(toks)
            self.tf.append(cnt)
            self.dl.append(len(toks))
            df.update(cnt.keys())
        n = len(chunks)
        self.n = n
        self.avgdl = sum(self.dl) / max(n, 1)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}
        self.max_idf = max(self.idf.values()) if self.idf else 1.0
        self.postings = defaultdict(list)
        for i, cnt in enumerate(self.tf):
            for t in cnt:
                self.postings[t].append(i)
        self.by_doc = defaultdict(list)
        for i, c in enumerate(chunks):
            self.by_doc[c["document_id"]].append(i)
        # accès par référence : (type, clé de numéro) -> indices de chunks
        self.by_ref = defaultdict(list)
        for i, c in enumerate(chunks):
            if c.get("number"):
                self.by_ref[(c["document_type"], num_key(c["number"]))].append(i)

    def expansion_terms(self, ranked: list[int], q_tokens: list[str], m: int = 4, n: int = 8, min_idf: float = 2.2) -> dict[str, float]:
        """Pseudo-retour de pertinence : termes saillants (tf·idf) des m meilleurs passages, absents de la question."""
        have = set(q_tokens)
        w = defaultdict(float)
        for i in ranked[:m]:
            for t, f in self.tf[i].items():
                idf = self.idf.get(t, 0)
                if t in have or idf < min_idf or t.isdigit():
                    continue
                w[t] += (f / self.dl[i]) * idf
        top = sorted(w.items(), key=lambda kv: -kv[1])[:n]
        mx = top[0][1] if top else 1.0
        return {t: v / mx for t, v in top}

    def scores(self, q_tokens: list[str], restrict: set | None = None, extra: dict | None = None) -> dict[int, float]:
        sc = defaultdict(float)
        weighted = {t: 1.0 for t in set(q_tokens)}
        for t, wt in (extra or {}).items():
            weighted.setdefault(t, wt)
        for t, wt in weighted.items():
            idf = self.idf.get(t)
            if idf is None:
                continue
            idf = idf * wt
            for i in self.postings[t]:
                if restrict is not None and i not in restrict:
                    continue
                f = self.tf[i][t]
                sc[i] += idf * f * (K1 + 1) / (f + K1 * (1 - B + B * self.dl[i] / self.avgdl))
        return sc


def _signature() -> str:
    h = hashlib.sha256()
    for p in (CHUNKS, DOCS):
        st = p.stat()
        h.update(f"{p.name}:{st.st_size}:{int(st.st_mtime)}".encode())
    return h.hexdigest()


def load_index(force: bool = False) -> Index:
    sig = _signature()
    if not force and CACHE.exists():
        try:
            with open(CACHE, "rb") as f:
                saved = pickle.load(f)
            if saved["sig"] == sig:
                return saved["index"]
        except Exception:
            pass
    chunks = [json.loads(l) for l in open(CHUNKS, encoding="utf-8")]
    docs = json.loads(DOCS.read_text(encoding="utf-8"))
    idx = Index(chunks, docs)
    CACHE.parent.mkdir(exist_ok=True)
    with open(CACHE, "wb") as f:
        pickle.dump({"sig": sig, "index": idx}, f)
    return idx
