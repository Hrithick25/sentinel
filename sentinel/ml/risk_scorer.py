"""
SENTINEL ML — Risk Scorer v3.0
=================================
Uses ProtectAI/deberta-v3-base-prompt-injection-v2 — a model specifically
fine-tuned to classify prompts as INJECTION vs SAFE.

Fallback chain:
  1. ProtectAI DeBERTa (best accuracy, ~100ms on CPU)
  2. Lightweight keyword + statistical heuristic (no model needed)

The previous implementation used raw distilbert-base-uncased which was
a generic sentiment model producing meaningless LABEL_0/LABEL_1 outputs.
"""
from __future__ import annotations

import asyncio
import logging
import math
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from sentinel.eval.normalizer import normalize_for_detection

logger = logging.getLogger("sentinel.ml.risk_scorer")

# ── Heuristic keyword scoring (ultra-fast fallback) ───────────────────────────

_RISK_KEYWORDS = {
    # High risk (0.25 each)
    "high": [
        "ignore previous", "disregard instructions", "you are now",
        "act as if", "jailbreak", "DAN mode", "bypass filter",
        "system prompt", "reveal instructions", "print your prompt",
        "ignore all", "override safety", "developer mode", "god mode",
        "no restrictions", "without limits", "pretend you have no",
    ],
    # Medium risk (0.12 each)
    "medium": [
        "roleplay", "pretend", "imagine you are", "hypothetically",
        "in a fictional", "for educational purposes", "research only",
        "what would happen if", "how to hack", "exploit",
        "reverse shell", "sql injection", "xss",
    ],
    # Low risk (0.05 each)
    "low": [
        "bomb", "weapon", "poison", "malware", "ransomware",
        "phishing", "credentials", "password",
    ],
}

_RISK_WEIGHTS = {"high": 0.25, "medium": 0.12, "low": 0.05}


def _heuristic_score(text: str) -> float:
    """Fast keyword-based risk scoring. O(keywords) time."""
    text_lower = text.lower()
    score = 0.0
    for tier, keywords in _RISK_KEYWORDS.items():
        w = _RISK_WEIGHTS[tier]
        for kw in keywords:
            if kw in text_lower:
                score += w
    return min(score, 1.0)


def _heuristic_score_normalized(text: str) -> float:
    """Score both raw and normalized versions, take max."""
    raw = _heuristic_score(text)
    normalized = normalize_for_detection(text)
    if normalized != text.lower():
        norm = _heuristic_score(normalized)
        return max(raw, norm)
    return raw


# ── Model loading ────────────────────────────────────────────────────────────

_classifier = None
_MODEL_LOADED = False
_MODEL_FAILED = False


def _load_model():
    """
    Attempt to load ProtectAI/deberta-v3-base-prompt-injection-v2.
    This is a ~180MB model specifically trained for prompt injection detection.
    Falls back gracefully if unavailable.
    """
    global _classifier, _MODEL_LOADED, _MODEL_FAILED

    if _MODEL_LOADED or _MODEL_FAILED:
        return _classifier

    try:
        from transformers import pipeline

        _classifier = pipeline(
            "text-classification",
            model="ProtectAI/deberta-v3-base-prompt-injection-v2",
            device=-1,  # CPU
            truncation=True,
            max_length=512,
        )
        _MODEL_LOADED = True
        logger.info("✅ ML Risk Scorer loaded: ProtectAI/deberta-v3-base-prompt-injection-v2")
        return _classifier
    except Exception as exc:
        logger.warning(
            "⚠️ ProtectAI model unavailable: %s — using heuristic fallback", exc
        )
        _MODEL_FAILED = True
        return None


class MLRiskScorer:
    """
    Production-grade prompt risk scorer.

    Primary: ProtectAI DeBERTa v3 (fine-tuned for injection detection)
    Fallback: Keyword + statistical heuristic
    """

    def __init__(self):
        self._executor = ThreadPoolExecutor(max_workers=2)
        # Attempt model load at init (non-blocking if it fails)
        try:
            _load_model()
        except Exception as exc:
            logger.error("ML Risk Scorer init warning: %s", exc)

    def _score_prompt_sync(self, prompt: str) -> float:
        classifier = _load_model()

        if not classifier:
            # Fallback to heuristic scoring (with normalization)
            return _heuristic_score_normalized(prompt)

        try:
            # v6: Score both raw and normalized, take max
            raw_score = self._classify_single(classifier, prompt)
            normalized = normalize_for_detection(prompt)
            if normalized != prompt.lower():
                norm_score = self._classify_single(classifier, normalized)
                return max(raw_score, norm_score)
            return raw_score
        except Exception as exc:
            logger.error("ML scoring failed, using heuristic: %s", exc)
            return _heuristic_score_normalized(prompt)

    @staticmethod
    def _classify_single(classifier, text: str) -> float:
        """Run classifier on a single text and return risk score."""
        result = classifier(text[:512])
        prediction = result[0]
        label = prediction["label"].upper()
        confidence = prediction["score"]
        if label == "INJECTION":
            return round(confidence, 4)
        else:
            return round(1.0 - confidence, 4)

    async def score_prompt(self, prompt: str) -> float:
        """Run ML scoring in executor to avoid blocking the event loop."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor, self._score_prompt_sync, prompt
        )
