"""
SENTINEL Storage — FAISS Manager
===================================
Manages a FAISS flat index of attack-vector embeddings.
Operations:
  - search(prompt) → similarity score (0..1) against nearest known attack
  - upsert_attack(prompt) → embed + add to index (self-improving loop)
  - save / load index from disk
"""
from __future__ import annotations

import asyncio
import logging
import os
import pickle
from pathlib import Path
from typing import Tuple

import numpy as np
from sentence_transformers import SentenceTransformer

from sentinel.config import settings

logger = logging.getLogger("sentinel.faiss")

try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    logger.warning("faiss-cpu not installed — InjectionScout will use cosine fallback")
    FAISS_AVAILABLE = False


class FAISSManager:
    """
    Thread-safe FAISS index manager.
    The index lives in memory; snapshots are persisted to disk on upsert.
    """

    def __init__(self):
        self._model = SentenceTransformer(settings.embedding_model)
        self._dim = settings.faiss_dim
        self._index_path = Path(settings.faiss_index_path)
        self._index_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()
        self._index = self._load_or_create()
        self._attack_count = self._index.ntotal if FAISS_AVAILABLE else 0
        logger.info("FAISS index ready | vectors=%d | dim=%d",
                    self._attack_count, self._dim)

    # ── Public API ─────────────────────────────────────────────────────────────

    async def search(self, text: str, k: int = 5) -> float:
        """
        Returns a similarity score in [0, 1].
        1.0 = exact match to known attack vector.
        """
        if not FAISS_AVAILABLE or self._index.ntotal == 0:
            return 0.0

        embedding = await asyncio.to_thread(self._embed, text)

        async with self._lock:
            distances, _ = self._index.search(embedding, min(k, self._index.ntotal))

        # FAISS L2 distance → similarity (0 distance = perfect match = score 1.0)
        min_dist = float(distances[0].min())
        score = 1.0 / (1.0 + min_dist)
        return min(score, 1.0)

    async def upsert_attack(self, text: str) -> None:
        """Embed a confirmed attack prompt and add it to the FAISS index."""
        embedding = await asyncio.to_thread(self._embed, text)

        async with self._lock:
            if FAISS_AVAILABLE:
                self._index.add(embedding)
                self._attack_count += 1
            await asyncio.to_thread(self._save)

        logger.info("FAISS upsert — total attack vectors: %d", self._attack_count)

    async def bulk_load(self, texts: list[str]) -> None:
        """Load a batch of known attack vectors (e.g., from HuggingFace dataset)."""
        logger.info("Bulk loading %d attack vectors …", len(texts))
        embeddings = await asyncio.to_thread(self._embed_batch, texts)

        async with self._lock:
            if FAISS_AVAILABLE:
                self._index.add(embeddings)
                self._attack_count = self._index.ntotal
            await asyncio.to_thread(self._save)

        logger.info("Bulk load complete — total: %d", self._attack_count)

    @property
    def vector_count(self) -> int:
        return self._attack_count

    # ── Internal ───────────────────────────────────────────────────────────────

    def _embed(self, text: str) -> np.ndarray:
        vec = self._model.encode([text], normalize_embeddings=True)
        return vec.astype("float32")

    def _embed_batch(self, texts: list[str]) -> np.ndarray:
        vecs = self._model.encode(texts, normalize_embeddings=True, batch_size=64)
        return vecs.astype("float32")

    def _load_or_create(self):
        if not FAISS_AVAILABLE:
            return None

        idx_file = self._index_path.with_suffix(".index")
        if idx_file.exists():
            try:
                idx = faiss.read_index(str(idx_file))
                logger.info("Loaded existing FAISS index from %s", idx_file)
                return idx
            except Exception as exc:
                logger.warning("Failed to load FAISS index: %s — creating new", exc)

        # Flat L2 index (exact search, good up to ~500k vectors)
        idx = faiss.IndexFlatL2(self._dim)
        return idx

    def _save(self) -> None:
        if not FAISS_AVAILABLE or self._index is None:
            return
        idx_file = self._index_path.with_suffix(".index")
        faiss.write_index(self._index, str(idx_file))
