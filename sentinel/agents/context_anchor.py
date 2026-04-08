"""
SENTINEL Agent 6 — ContextAnchor
=====================================
A fast, lightweight complement to HallucinationProbe.
Computes cosine similarity between the output embedding and the
source context embedding as a rapid semantic consistency check.

Acts as a first-pass filter:
  - High similarity → plausibly grounded, skip expensive NLI
  - Low similarity  → likely drifted, flag for HallucinationProbe

Operates even without a context document — in that case it compares
input vs output to detect response topic drift (e.g., prompt hijacking
where the output is semantically unrelated to the input).
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

import numpy as np

from sentinel.agents.base import SentinelAgent
from sentinel.models import AgentResult, SentinelRequest

logger = logging.getLogger("sentinel.agents.context_anchor")

_embed_model = None


def _get_model():
    global _embed_model
    if _embed_model is None:
        try:
            from sentence_transformers import SentenceTransformer
            from sentinel.config import settings
            _embed_model = SentenceTransformer(settings.embedding_model)
            logger.info("ContextAnchor embedding model loaded")
        except Exception as exc:
            logger.warning("Embedding model load failed: %s", exc)
            _embed_model = False
    return _embed_model


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


class ContextAnchor(SentinelAgent):
    agent_name = "ContextAnchor"

    async def analyze(self, request: SentinelRequest) -> AgentResult:
        model = _get_model()

        # Get assistant response
        response_text = ""
        for m in reversed(request.messages):
            if m.role == "assistant":
                response_text = m.content
                break

        if not response_text:
            return AgentResult(
                agent_name=self.agent_name, score=0.0, flagged=False,
                metadata={"skipped": True, "reason": "no assistant response yet"}
            )

        anchor_text = request.context or request.last_user_message

        if not model:
            # Lexical overlap fallback
            anchor_words = set(anchor_text.lower().split())
            response_words = set(response_text.lower().split())
            overlap = len(anchor_words & response_words)
            similarity = overlap / max(len(anchor_words), 1)
            score = self._clamp(1.0 - similarity)
            return AgentResult(
                agent_name=self.agent_name,
                score=score,
                flagged=score >= 0.70,
                metadata={"similarity": round(similarity, 4), "method": "lexical"},
            )

        similarity = await asyncio.to_thread(
            self._compute_similarity, model, anchor_text, response_text
        )

        # Low similarity = response drifted from context = higher risk
        score = self._clamp(1.0 - similarity)
        flagged = score >= 0.70

        return AgentResult(
            agent_name=self.agent_name,
            score=score,
            flagged=flagged,
            metadata={
                "cosine_similarity": round(similarity, 4),
                "drift_score": round(score, 4),
                "method": "sentence-transformer",
                "anchor": "context" if request.context else "prompt",
            },
        )

    def _compute_similarity(self, model, text_a: str, text_b: str) -> float:
        texts = [text_a[:512], text_b[:512]]
        embeddings = model.encode(texts, normalize_embeddings=True)
        return _cosine(embeddings[0], embeddings[1])
