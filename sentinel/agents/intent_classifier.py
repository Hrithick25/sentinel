"""
SENTINEL Agent 14 — IntentClassifier v3.0
==========================================
Classifies prompt intent into benign vs malicious categories using
zero-shot classification.

Model upgrade path:
  - v2: facebook/bart-large-mnli (1.6GB, ~4s cold, always times out)
  - v3: MoritzLaurer/deberta-v3-base-zeroshot-v2.0 (440MB, ~200ms warm)
  - Fallback: Keyword-based intent heuristic (~1ms)
"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Optional

from sentinel.agents.base import SentinelAgent
from sentinel.models import AgentResult, SentinelRequest

logger = logging.getLogger("sentinel.agents.intent_classifier")

# ── Lazy-loaded classifier ────────────────────────────────────────────────────

_pipeline = None
_LOAD_FAILED = False


def _get_classifier():
    global _pipeline, _LOAD_FAILED
    if _pipeline is not None or _LOAD_FAILED:
        return _pipeline
    try:
        from transformers import pipeline

        _pipeline = pipeline(
            "zero-shot-classification",
            model="MoritzLaurer/deberta-v3-base-zeroshot-v2.0",
            device=-1,  # CPU
        )
        logger.info(
            "✅ IntentClassifier loaded: MoritzLaurer/deberta-v3-base-zeroshot-v2.0"
        )
    except Exception as exc:
        logger.warning(
            "⚠️ Zero-shot model unavailable: %s — using heuristic fallback", exc
        )
        _LOAD_FAILED = True
    return _pipeline


# ── Keyword heuristic fallback ────────────────────────────────────────────────

_INTENT_PATTERNS = {
    "prompt injection": [
        r"ignore\s+(previous|all|prior)\s+(instructions?|prompts?)",
        r"disregard\s+(your|all)\s+(instructions?|training)",
        r"you\s+are\s+now",
        r"(system|assistant)\s*:\s*\n",
        r"\[INST\]|\[/INST\]",
    ],
    "jailbreak attempt": [
        r"(pretend|act|roleplay)\s+as",
        r"DAN\s*(mode|jailbreak|\d+)",
        r"(developer|god|unrestricted)\s+mode",
        r"no\s+(restrictions?|limits?|filters?)",
        r"(bypass|disable|override)\s+(safety|content|ethical)",
    ],
    "data exfiltration": [
        r"(reveal|show|print|tell)\s+(your|the)\s+(system\s+)?prompt",
        r"what\s+(are|were)\s+your\s+(original\s+)?instructions?",
        r"(extract|dump|export)\s+.{0,20}(data|database|records)",
        r"(list|show)\s+all\s+(users?|emails?|passwords?)",
    ],
    "social engineering": [
        r"(i\s+am|you\s+are\s+talking\s+to)\s+(your\s+)?(developer|creator|admin)",
        r"(test|debug|maintenance)\s+mode",
        r"(emergency|urgent)\s+override",
        r"this\s+is\s+authorized",
    ],
}

_COMPILED_PATTERNS = {
    cat: [re.compile(p, re.IGNORECASE | re.DOTALL) for p in patterns]
    for cat, patterns in _INTENT_PATTERNS.items()
}


def _heuristic_classify(text: str) -> tuple[str, float, float]:
    """
    Returns (top_intent, malicious_score, benign_confidence).
    Uses compiled regex patterns for fast classification.
    """
    scores = {}
    for category, patterns in _COMPILED_PATTERNS.items():
        hits = sum(1 for p in patterns if p.search(text))
        scores[category] = min(hits * 0.25, 1.0)

    if not scores or max(scores.values()) == 0:
        return "benign request", 0.0, 1.0

    top_intent = max(scores, key=scores.get)
    top_score = scores[top_intent]
    benign_confidence = max(0.0, 1.0 - top_score)

    return top_intent, top_score, benign_confidence


class IntentClassifier(SentinelAgent):
    agent_name = "IntentClassifier"

    LABELS = [
        "benign request",
        "jailbreak attempt",
        "data exfiltration",
        "prompt injection",
        "social engineering",
    ]

    async def analyze(self, request: SentinelRequest) -> AgentResult:
        prompt = request.prompt

        classifier = _get_classifier()

        if not classifier:
            # Heuristic fallback
            top_intent, mal_score, benign_conf = _heuristic_classify(prompt)
            final_score = self._clamp(mal_score)
            return AgentResult(
                agent_name=self.agent_name,
                score=final_score,
                flagged=final_score >= 0.7,
                metadata={
                    "top_intent": top_intent,
                    "benign_confidence": benign_conf,
                    "malicious_confidence": mal_score,
                    "method": "heuristic",
                },
            )

        try:
            loop = asyncio.get_running_loop()
            # Truncate to avoid OOM on long prompts
            result = await loop.run_in_executor(
                None,
                lambda: classifier(
                    prompt[:512], self.LABELS, multi_label=False
                ),
            )

            # Find max malicious score
            malicious_score = 0.0
            top_intent = "benign request"

            for label, score in zip(result["labels"], result["scores"]):
                if label != "benign request":
                    if score > malicious_score:
                        malicious_score = score
                        top_intent = label

            benign_score = dict(zip(result["labels"], result["scores"])).get(
                "benign request", 0.0
            )

            final_score = self._clamp(malicious_score)

            return AgentResult(
                agent_name=self.agent_name,
                score=final_score,
                flagged=final_score >= 0.7,
                metadata={
                    "top_intent": top_intent,
                    "benign_confidence": benign_score,
                    "malicious_confidence": malicious_score,
                    "method": "zero-shot-deberta",
                },
            )
        except Exception as exc:
            logger.error("IntentClassifier model error: %s — falling back to heuristic", exc)
            top_intent, mal_score, benign_conf = _heuristic_classify(prompt)
            final_score = self._clamp(mal_score)
            return AgentResult(
                agent_name=self.agent_name,
                score=final_score,
                flagged=final_score >= 0.7,
                metadata={
                    "top_intent": top_intent,
                    "benign_confidence": benign_conf,
                    "malicious_confidence": mal_score,
                    "method": "heuristic_fallback",
                },
            )
