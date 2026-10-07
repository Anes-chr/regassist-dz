"""Reranker léger 100 % local : cross-encoder multilingue mmarco-mMiniLMv2-L12-H384 (Apache-2.0, ONNX int8 AVX2).
Donne un score de pertinence pour chaque paire (question, passage). Répertoire modèle : AGENT_RERANK_DIR."""
import os
import time
from pathlib import Path

import numpy as np

DIR = Path(os.environ.get("AGENT_RERANK_DIR", r"D:\llm\models\rerankers\mmarco-mMiniLMv2-L12-H384"))
MODEL = os.environ.get("AGENT_RERANK_MODEL", "model_quint8_avx2.onnx")
MAX_LEN = 320


class Reranker:
    def __init__(self, threads: int = 6):
        import onnxruntime as ort
        from tokenizers import Tokenizer
        self.tok = Tokenizer.from_file(str(DIR / "tokenizer.json"))
        self.tok.enable_truncation(max_length=MAX_LEN)
        self.tok.enable_padding(pad_id=1, pad_token="<pad>")
        so = ort.SessionOptions()
        so.intra_op_num_threads = threads
        so.inter_op_num_threads = 1
        self.sess = ort.InferenceSession(str(DIR / "onnx" / MODEL), so, providers=["CPUExecutionProvider"])
        self.inputs = {i.name for i in self.sess.get_inputs()}

    def score(self, query: str, passages: list[str], batch: int = 10) -> list[float]:
        out = []
        for s in range(0, len(passages), batch):
            encs = self.tok.encode_batch([(query, p) for p in passages[s:s + batch]])
            ids = np.array([e.ids for e in encs], dtype=np.int64)
            mask = np.array([e.attention_mask for e in encs], dtype=np.int64)
            feed = {"input_ids": ids, "attention_mask": mask}
            if "token_type_ids" in self.inputs:
                feed["token_type_ids"] = np.array([e.type_ids for e in encs], dtype=np.int64)
            logits = self.sess.run(None, feed)[0]
            out.extend(np.asarray(logits).reshape(len(encs), -1)[:, 0].tolist())
        return out


_R = None


def get_reranker(threads: int = 6) -> Reranker:
    global _R
    if _R is None:
        _R = Reranker(threads)
    return _R


if __name__ == "__main__":
    t = time.time()
    r = get_reranker()
    print("chargement", round(time.time() - t, 2), "s | entrées", sorted(r.inputs))
    q = "Quel est le plafond d'indemnisation par déposant ?"
    ps = ["Le plafond d'indemnisation par déposant est fixé à deux millions de dinars (2.000.000 DA).",
          "Les banques doivent respecter un coefficient minimum de solvabilité de 9,5 %.",
          "La Banque d'Algérie publie un rapport annuel sur ses activités.",
          "Le plafond d'indemnisation par déposant est fixé à six cent mille dinars (600.000 DA)."]
    t = time.time()
    sc = r.score(q, ps)
    print("scores:", [round(x, 2) for x in sc], "| latence 4 paires:", round((time.time() - t) * 1000), "ms")
    t = time.time()
    r.score(q, ps * 5)
    print("latence 20 paires:", round((time.time() - t) * 1000), "ms")
