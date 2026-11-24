"""Hook embeddings: sentence-transformers if available, else a hashed n-gram fallback.

Set FA_EMBEDDER=hash to force the fallback (e.g. offline / fast tests).
"""
from __future__ import annotations

import hashlib
import logging
import os
import re
from typing import Protocol

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import HookEmbedding, Reel, ReelLabel

log = logging.getLogger(__name__)

DIM = 384
ST_MODEL = "all-MiniLM-L6-v2"


class Embedder(Protocol):
    model_name: str
    dim: int

    def embed(self, texts: list[str]) -> np.ndarray: ...


def _l2_normalize(m: np.ndarray) -> np.ndarray:
    m = np.asarray(m, dtype=np.float32)
    if m.ndim == 1:
        m = m[None, :]
    norms = np.linalg.norm(m, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return (m / norms).astype(np.float32)


class HashedNgramEmbedder:
    """Deterministic hashed character n-gram TF vector (384-dim, L2-normalized)."""

    def __init__(self, dim: int = DIM, ngram_range: tuple[int, int] = (2, 4)):
        self.dim = dim
        self.ngram_range = ngram_range
        self.model_name = f"hashed-char-ngram-{ngram_range[0]}-{ngram_range[1]}-{dim}"

    def _features(self, text: str) -> list[str]:
        text = re.sub(r"\s+", " ", (text or "").lower()).strip()
        feats: list[str] = []
        for word in re.findall(r"\w+", text):
            feats.append("w:" + word)
            padded = f" {word} "
            lo, hi = self.ngram_range
            for n in range(lo, hi + 1):
                feats.extend("c:" + padded[i : i + n] for i in range(len(padded) - n + 1))
        return feats

    def embed(self, texts: list[str]) -> np.ndarray:
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for row, text in enumerate(texts):
            for f in self._features(text):
                h = int.from_bytes(hashlib.md5(f.encode("utf-8")).digest()[:8], "little")
                sign = 1.0 if (h >> 63) & 1 else -1.0
                out[row, h % self.dim] += sign
        return _l2_normalize(out) if len(texts) else out


class SentenceTransformerEmbedder:
    def __init__(self, model: str = ST_MODEL):
        from sentence_transformers import SentenceTransformer  # noqa: PLC0415

        self._model = SentenceTransformer(model)
        self.model_name = model
        getdim = getattr(self._model, "get_embedding_dimension", None) or self._model.get_sentence_embedding_dimension
        self.dim = int(getdim())

    def embed(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        vecs = self._model.encode(list(texts), convert_to_numpy=True, normalize_embeddings=True)
        return _l2_normalize(vecs)


_EMBEDDER: Embedder | None = None


def get_embedder() -> Embedder:
    """Cached embedder; falls back to hashed n-grams if sentence-transformers fails."""
    global _EMBEDDER
    if _EMBEDDER is None:
        if os.environ.get("FA_EMBEDDER", "").lower() in ("hash", "hashed", "fallback"):
            _EMBEDDER = HashedNgramEmbedder()
        else:
            try:
                _EMBEDDER = SentenceTransformerEmbedder()
            except Exception as exc:  # ImportError, no network for model download, etc.
                log.warning("sentence-transformers unavailable (%s); using hashed n-gram fallback", exc)
                _EMBEDDER = HashedNgramEmbedder()
    return _EMBEDDER


def _to_bytes(vec: np.ndarray) -> bytes:
    return np.asarray(vec, dtype=np.float32).reshape(-1).tobytes()


def _from_bytes(b: bytes, dim: int) -> np.ndarray:
    return np.frombuffer(b, dtype=np.float32, count=dim)


def upsert_hook_embedding(session: Session, reel_id: int, text: str) -> HookEmbedding:
    emb = get_embedder()
    vec = emb.embed([text or ""])[0]
    row = session.get(HookEmbedding, reel_id)
    if row is None:
        row = HookEmbedding(reel_id=reel_id)
        session.add(row)
    row.model = emb.model_name
    row.dim = emb.dim
    row.vector = _to_bytes(vec)
    return row


def similar_hooks(
    session: Session, text: str | None = None, reel_code: str | None = None, k: int = 10
) -> list[tuple[Reel, ReelLabel, float]]:
    """Most cosine-similar labeled hooks to `text` or to the hook of `reel_code`.

    When `reel_code` is given, that reel itself is excluded from the results.
    """
    emb = get_embedder()
    exclude_id: int | None = None
    query: np.ndarray | None = None

    if reel_code is not None:
        reel = session.scalar(select(Reel).where(Reel.code == reel_code))
        if reel is None:
            return []
        exclude_id = reel.id
        stored = session.get(HookEmbedding, reel.id)
        if stored is not None and stored.model == emb.model_name and stored.dim == emb.dim:
            query = _from_bytes(stored.vector, stored.dim)
        else:
            label = session.get(ReelLabel, reel.id)
            hook = (label.hook_text if label else None) or text
            if not hook:
                return []
            query = emb.embed([hook])[0]
    elif text:
        query = emb.embed([text])[0]
    else:
        return []

    rows = session.execute(
        select(HookEmbedding, Reel, ReelLabel)
        .join(Reel, Reel.id == HookEmbedding.reel_id)
        .join(ReelLabel, ReelLabel.reel_id == HookEmbedding.reel_id)
        .where(HookEmbedding.model == emb.model_name, HookEmbedding.dim == emb.dim)
    ).all()
    rows = [r for r in rows if r[1].id != exclude_id]
    if not rows:
        return []

    matrix = np.stack([_from_bytes(h.vector, h.dim) for h, _, _ in rows])
    q = _l2_normalize(query)[0]
    scores = matrix @ q
    order = np.argsort(-scores, kind="stable")[: max(k, 0)]
    return [(rows[i][1], rows[i][2], float(scores[i])) for i in order]
