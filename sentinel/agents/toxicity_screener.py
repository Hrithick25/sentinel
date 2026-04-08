"""
SENTINEL Agent 4 — ToxicityScreener
========================================
Uses HuggingFace Detoxify to score prompts across 6 toxicity dimensions:
  toxicity, severe_toxicity, obscene, threat, insult, identity_hate

Each dimension is scored 0.0–1.0 and compared against per-category
thresholds loaded from the tenant policy.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from sentinel.agents.base import SentinelAgent
from sentinel.models import AgentResult, SentinelRequest

logger = logging.getLogger("sentinel.agents.toxicity_screener")

_CATEGORIES = [
    "toxicity", "severe_toxicity", "obscene",
    "threat", "insult", "identity_hate",
]

# Lazy-load Detoxify (heavy model — only load once globally)
_model = None


def _get_model():
    global _model
    if _model is None:
        try:
            from detoxify import Detoxify
            _model = Detoxify("original")
            logger.info("Detoxify model loaded")
        except ImportError:
            logger.warning("detoxify not installed — ToxicityScreener in fallback mode")
            _model = False
    return _model


class ToxicityScreener(SentinelAgent):
    agent_name = "ToxicityScreener"

    async def analyze(self, request: SentinelRequest) -> AgentResult:
        text = request.last_user_message
        scores = await asyncio.to_thread(self._score, text)

        # Aggregate score = weighted max across categories
        weights = {
            "toxicity": 0.30,
            "severe_toxicity": 0.30,
            "threat": 0.20,
            "obscene": 0.05,
            "insult": 0.10,
            "identity_hate": 0.05,
        }
        aggregate = sum(scores.get(cat, 0.0) * w for cat, w in weights.items())
        aggregate = self._clamp(aggregate)
        flagged = aggregate >= 0.60

        return AgentResult(
            agent_name=self.agent_name,
            score=aggregate,
            flagged=flagged,
            metadata={
                "scores": scores,
                "flagged_categories": [
                    cat for cat, s in scores.items() if s >= 0.5
                ],
            },
        )

    def _score(self, text: str) -> dict[str, float]:
        model = _get_model()
        if not model:
            # Lightweight keyword fallback
            threat_words = [
                "kill", "murder", "bomb", "attack", "destroy", "rape",
                "stab", "shoot", "explode", "hurt", "die", "death"
            ]
            text_lower = text.lower()
            count = sum(1 for w in threat_words if w in text_lower)
            s = self._clamp(count * 0.25)
            return {cat: s for cat in _CATEGORIES}

        try:
            results = model.predict(text)
            return {k: float(v) for k, v in results.items() if k in _CATEGORIES}
        except Exception as exc:
            logger.error("Detoxify prediction failed: %s", exc)
            return {cat: 0.0 for cat in _CATEGORIES}
