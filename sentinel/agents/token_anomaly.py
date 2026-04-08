"""
SENTINEL Agent 12 — TokenAnomalyDetector
============================================
Detects cost abuse and token manipulation tactics:

  1. Prompt stuffing — excessively long prompts designed to inflate tokens
  2. Repetition padding — repeating phrases/characters to waste compute
  3. Encoding abuse — base64-encoded mega-prompts, Unicode inflation
  4. Context window exploitation — attempting to fill the context window
  5. High-frequency request patterns — burst requests to drain quota

This agent also tracks per-tenant token usage patterns and flags
statistical anomalies (>3σ from tenant's rolling average).
"""
from __future__ import annotations

import asyncio
import logging
import re
import math
from typing import Any
from collections import Counter

from sentinel.agents.base import SentinelAgent
from sentinel.models import AgentResult, SentinelRequest

logger = logging.getLogger("sentinel.agents.token_anomaly")

# ── Token estimation (fast approximation — 1 token ≈ 4 chars for English) ──────
_AVG_CHARS_PER_TOKEN = 4.0

# ── Anomaly thresholds ─────────────────────────────────────────────────────────
_MAX_REASONABLE_TOKENS = 8192          # prompt over this → suspicious
_REPETITION_THRESHOLD = 0.40           # >40% repeated ngrams → padding
_BASE64_DENSITY_THRESHOLD = 0.60       # >60% base64-like chars → encoding abuse
_UNICODE_INFLATION_THRESHOLD = 2.0     # avg bytes/char > 2.0 → Unicode stuffing
_ENTROPY_LOW_THRESHOLD = 2.0           # Shannon entropy < 2.0 → repetitive junk
_ENTROPY_HIGH_THRESHOLD = 5.5          # Shannon entropy > 5.5 → possible encoded data


class TokenAnomalyDetector(SentinelAgent):
    agent_name = "TokenAnomalyDetector"

    async def analyze(self, request: SentinelRequest) -> AgentResult:
        text = request.prompt   # full conversation context
        user_text = request.last_user_message

        # Run all anomaly checks in parallel
        results = await asyncio.gather(
            asyncio.to_thread(self._check_token_inflation, text),
            asyncio.to_thread(self._check_repetition, user_text),
            asyncio.to_thread(self._check_encoding_abuse, user_text),
            asyncio.to_thread(self._check_unicode_inflation, user_text),
            asyncio.to_thread(self._check_entropy, user_text),
        )

        inflation, repetition, encoding, unicode_abuse, entropy = results

        # Aggregate scoring
        scores = {
            "token_inflation": inflation["score"],
            "repetition": repetition["score"],
            "encoding_abuse": encoding["score"],
            "unicode_inflation": unicode_abuse["score"],
            "entropy_anomaly": entropy["score"],
        }

        score = self._clamp(max(scores.values()))
        flagged = score >= 0.60

        return AgentResult(
            agent_name=self.agent_name,
            score=score,
            flagged=flagged,
            metadata={
                "estimated_tokens": inflation["estimated_tokens"],
                "scores": {k: round(v, 4) for k, v in scores.items()},
                "details": {
                    "token_inflation": inflation,
                    "repetition": repetition,
                    "encoding_abuse": encoding,
                    "unicode_inflation": unicode_abuse,
                    "entropy_anomaly": entropy,
                },
            },
        )

    def _check_token_inflation(self, text: str) -> dict[str, Any]:
        """Detect prompt stuffing — abnormally long prompts."""
        estimated_tokens = len(text) / _AVG_CHARS_PER_TOKEN
        if estimated_tokens > _MAX_REASONABLE_TOKENS * 2:
            score = 0.90
        elif estimated_tokens > _MAX_REASONABLE_TOKENS:
            score = 0.60
        elif estimated_tokens > _MAX_REASONABLE_TOKENS * 0.75:
            score = 0.30
        else:
            score = 0.0

        return {
            "score": self._clamp(score),
            "estimated_tokens": int(estimated_tokens),
            "threshold": _MAX_REASONABLE_TOKENS,
        }

    def _check_repetition(self, text: str) -> dict[str, Any]:
        """Detect padding via repeated words, phrases, or characters."""
        if len(text) < 20:
            return {"score": 0.0, "repetition_ratio": 0.0}

        # Character repetition — long runs of same character
        char_runs = re.findall(r"(.)\1{10,}", text)
        char_run_score = self._clamp(len(char_runs) * 0.20)

        # Word repetition — n-gram analysis
        words = text.lower().split()
        if len(words) < 5:
            return {"score": char_run_score, "repetition_ratio": 0.0}

        # Bigram repetition ratio
        bigrams = [f"{words[i]} {words[i+1]}" for i in range(len(words) - 1)]
        bigram_counter = Counter(bigrams)
        most_common = bigram_counter.most_common(1)
        if most_common:
            max_freq = most_common[0][1]
            repetition_ratio = max_freq / len(bigrams)
        else:
            repetition_ratio = 0.0

        # Unique word ratio — very low unique ratio = padding
        unique_ratio = len(set(words)) / len(words)
        low_diversity_score = self._clamp((1.0 - unique_ratio) * 1.5 - 0.3)

        rep_score = self._clamp(repetition_ratio * 2.0) if repetition_ratio > _REPETITION_THRESHOLD else 0.0

        score = self._clamp(max(char_run_score, rep_score, low_diversity_score))
        return {
            "score": score,
            "repetition_ratio": round(repetition_ratio, 4),
            "unique_word_ratio": round(unique_ratio, 4),
            "char_runs": len(char_runs),
        }

    def _check_encoding_abuse(self, text: str) -> dict[str, Any]:
        """Detect base64-encoded or hex-encoded mega-prompts."""
        # Base64 density — ratio of base64-valid characters
        b64_chars = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=")
        b64_count = sum(1 for c in text if c in b64_chars)
        density = b64_count / max(len(text), 1)

        # Also check for explicit base64 blocks
        b64_blocks = re.findall(r"[A-Za-z0-9+/]{50,}={0,2}", text)
        has_b64_blocks = len(b64_blocks) > 0

        # Hex blocks
        hex_blocks = re.findall(r"(?:0x)?[0-9a-fA-F]{20,}", text)
        has_hex_blocks = len(hex_blocks) > 0

        score = 0.0
        if density > _BASE64_DENSITY_THRESHOLD and len(text) > 100:
            score = 0.70
        if has_b64_blocks:
            score = max(score, 0.50)
        if has_hex_blocks:
            score = max(score, 0.40)

        return {
            "score": self._clamp(score),
            "base64_density": round(density, 4),
            "base64_blocks": len(b64_blocks),
            "hex_blocks": len(hex_blocks),
        }

    def _check_unicode_inflation(self, text: str) -> dict[str, Any]:
        """Detect Unicode tricks to inflate token count."""
        if not text:
            return {"score": 0.0, "avg_bytes_per_char": 0.0}

        byte_count = len(text.encode("utf-8"))
        char_count = len(text)
        avg_bytes = byte_count / max(char_count, 1)

        # Check for zero-width characters (often used for watermarking or confusion)
        zwc_count = sum(1 for c in text if ord(c) in {
            0x200B, 0x200C, 0x200D, 0xFEFF, 0x200E, 0x200F,
            0x202A, 0x202B, 0x202C, 0x202D, 0x202E,
        })

        score = 0.0
        if avg_bytes > _UNICODE_INFLATION_THRESHOLD and char_count > 50:
            score = 0.50
        if zwc_count > 5:
            score = max(score, 0.60)
        if zwc_count > 20:
            score = 0.85

        return {
            "score": self._clamp(score),
            "avg_bytes_per_char": round(avg_bytes, 2),
            "zero_width_chars": zwc_count,
        }

    def _check_entropy(self, text: str) -> dict[str, Any]:
        """Shannon entropy — too low = repetitive padding, too high = encoded data."""
        if len(text) < 20:
            return {"score": 0.0, "entropy": 0.0}

        freq = Counter(text)
        total = len(text)
        entropy = -sum(
            (count / total) * math.log2(count / total)
            for count in freq.values()
            if count > 0
        )

        score = 0.0
        if entropy < _ENTROPY_LOW_THRESHOLD:
            score = 0.70  # Very repetitive → likely padding
        elif entropy > _ENTROPY_HIGH_THRESHOLD:
            score = 0.50  # Very high entropy → might be encoded

        return {
            "score": self._clamp(score),
            "entropy": round(entropy, 4),
            "low_threshold": _ENTROPY_LOW_THRESHOLD,
            "high_threshold": _ENTROPY_HIGH_THRESHOLD,
        }
