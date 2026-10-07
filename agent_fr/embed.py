"""Embeddings multilingues 100 % locaux : intfloat/multilingual-e5-small (MIT) via ONNX Runtime (pas de PyTorch).

Modèle attendu dans D:\\llm\\models\\embeddings\\multilingual-e5-small (AGENT_EMBED_DIR pour changer). Préfixes e5 obligatoires :
« query: » pour les questions, « passage: » pour les textes. Les vecteurs sont normalisés (produit scalaire = cosinus).
Rien n'est envoyé hors de la machine : le corpus est encodé localement et les vecteurs sont stockés sous D:\\llm\\index.
"""
import hashlib
import json
import os
import time
from pathlib import Path

import numpy as np

MODEL_DIR = Path(os.environ.get("AGENT_EMBED_DIR", r"D:\llm\models\embeddings\multilingual-e5-small"))
INDEX_DIR = Path(os.environ.get("AGENT_VECTOR_DIR", r"D:\llm\index"))
MAX_LEN = 512


class Embedder:
    def __init__(self, threads: int = 6):
        import onnxruntime as ort
        from tokenizers import Tokenizer
        self.tok = Tokenizer.from_file(str(MODEL_DIR / "tokenizer.json"))
        self.tok.enable_truncation(max_length=MAX_LEN)
        self.tok.enable_padding(pad_id=1, pad_token="<pad>")
        so = ort.SessionOptions()
        so.intra_op_num_threads = threads
        so.inter_op_num_threads = 1
        so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        self.sess = ort.InferenceSession(str(MODEL_DIR / "onnx" / "model.onnx"), so, providers=["CPUExecutionProvider"])
        self.inputs = {i.name for i in self.sess.get_inputs()}

    def _encode_batch(self, texts):
        encs = self.tok.encode_batch(texts)
        ids = np.array([e.ids for e in encs], dtype=np.int64)
        mask = np.array([e.attention_mask for e in encs], dtype=np.int64)
        feed = {"input_ids": ids, "attention_mask": mask}
        if "token_type_ids" in self.inputs:
            feed["token_type_ids"] = np.zeros_like(ids)
        out = self.sess.run(None, feed)[0]                      # (batch, seq, 384)
        m = mask[..., None].astype(np.float32)
        pooled = (out * m).sum(1) / np.clip(m.sum(1), 1e-9, None)  # mean pooling (e5)
        pooled /= np.clip(np.linalg.norm(pooled, axis=1, keepdims=True), 1e-9, None)
        return pooled.astype(np.float32)

    def embed(self, texts, prefix: str, batch: int = 16, progress: bool = False):
        """Encode en triant par longueur (moins de remplissage = plus rapide), restitue l'ordre d'origine."""
        order = sorted(range(len(texts)), key=lambda i: len(texts[i]))
        out = np.zeros((len(texts), 384), dtype=np.float32)
        t0 = time.time()
        for s in range(0, len(order), batch):
            ids = order[s:s + batch]
            out[ids] = self._encode_batch([prefix + texts[i] for i in ids])
            if progress and (s // batch) % 25 == 0:
                done = s + len(ids)
                print(f"  embeddings {done}/{len(texts)}  ({done / max(time.time() - t0, 1e-6):.1f} textes/s)", flush=True)
        return out

    def embed_query(self, q: str) -> np.ndarray:
        return self._encode_batch(["query: " + q])[0]


_EMB = None


def get_embedder(threads: int = 6) -> Embedder:
    global _EMB
    if _EMB is None:
        _EMB = Embedder(threads)
    return _EMB


def corpus_key(chunks_path: Path, langs: str = "fr") -> str:
    st = Path(chunks_path).stat()
    return hashlib.sha1(f"{chunks_path}|{st.st_size}|{int(st.st_mtime)}|{langs}|e5-small|v1".encode()).hexdigest()[:12]


def vector_path(key: str) -> Path:
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    return INDEX_DIR / f"vec_{key}.npy"


def passage_text(c: dict) -> str:
    """Texte encodé : contexte juridique (texte, date, titre, hiérarchie, article) + texte de l'article."""
    return c["text_with_context"]
