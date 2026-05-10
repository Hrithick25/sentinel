"""
SENTINEL Agent 1 — InjectionScout v6.0
=========================================
Detects prompt injection attacks using FAISS approximate nearest-neighbor
search against a 50,000+ vector index of known attack embeddings.

Technique:
  1. Embed incoming prompt with sentence-transformers/all-MiniLM-L6-v2
  2. Search FAISS index for top-k nearest attacks
  3. Score = 1 / (1 + min_L2_distance)
  4. Also applies heuristic pattern matching for common injection signatures

v6 upgrade:
  ✅ Normalized matching — strips homoglyphs, zero-width, leetspeak before regex
  ✅ Encoded payload decoding — detects base64/ROT13/hex-wrapped attacks
  ✅ Dual-pass scoring — patterns checked against both raw and normalized text
"""
from __future__ import annotations

import re
import logging
from typing import Optional

from sentinel.agents.base import SentinelAgent
from sentinel.eval.normalizer import normalize_for_detection, decode_encoded_payloads
from sentinel.models import AgentResult, SentinelRequest

logger = logging.getLogger("sentinel.agents.injection_scout")

# Known injection signatures — fast heuristic pass before FAISS
_INJECTION_PATTERNS = [
    r"ignore\s+(previous|all|prior|above)\s+(instructions?|prompts?|rules?)",
    r"disregard\s+(your|all|any)\s+(instructions?|training|guidelines?)",
    r"you\s+are\s+now\s+(a|an|the)\s+\w+\s+(without|with no)\s+(restrictions?|limits?|filters?)",
    r"(pretend|act|behave|roleplay)\s+as\s+if\s+(you\s+(have\s+no|don'?t\s+have)|there\s+(are|is)\s+no)",
    r"(system|assistant|model)\s*:\s*\n",   # delimiter injection
    r"\[INST\]|\[\/INST\]|<\|im_start\|>|<\|system\|>",   # template injection
    r"repeat\s+after\s+me",
    r"print\s+your\s+(system\s+)?prompt",
    r"what\s+(are|were)\s+your\s+(original\s+)?instructions?",
    r"reveal\s+(your|the)\s+(system\s+)?prompt",
    r"DAN\s*(mode|jailbreak|\d+)",          # classic DAN attacks
    r"grandma\s+(used\s+to|would|trick)",   # grandma jailbreak
    r"token\s*smuggling|sandwich\s*attack|virtual\s*prompt",
]

_COMPILED = [re.compile(p, re.IGNORECASE | re.MULTILINE)
             for p in _INJECTION_PATTERNS]


class InjectionScout(SentinelAgent):
    agent_name = "InjectionScout"

    def __init__(self, faiss_manager=None):
        self._faiss = faiss_manager

    async def analyze(self, request: SentinelRequest) -> AgentResult:
        prompt = request.prompt

        # ── v6: Normalize for detection (strips homoglyphs, zero-width, leet) ─
        normalized = normalize_for_detection(prompt)
        decoded_payloads = decode_encoded_payloads(prompt)
        all_texts = [prompt, normalized] + decoded_payloads

        # ── 1. Heuristic pattern scan (dual-pass: raw + normalized + decoded) ─
        pattern_hits = []
        for p in _COMPILED:
            for txt in all_texts:
                if p.search(txt):
                    pattern_hits.append(p.pattern)
                    break  # count each pattern only once
        heuristic_score = min(1.0, len(pattern_hits) * 0.35)

        # Bonus for encoded payload detection (attackers encoding = high suspicion)
        encoding_bonus = min(0.3, len(decoded_payloads) * 0.15)

        # ── 2. FAISS semantic search (ANN over 50k+ attack vectors) ──────────
        faiss_score = 0.0
        if self._faiss and self._faiss.vector_count > 0:
            faiss_score = await self._faiss.search(prompt)
            # Also search normalized version if different
            if normalized != prompt.lower():
                norm_faiss = await self._faiss.search(normalized)
                faiss_score = max(faiss_score, norm_faiss)

        # ── 3. Combine scores (max of all signals) ───────────────────────────
        score = self._clamp(max(heuristic_score + encoding_bonus, faiss_score))
        flagged = score >= 0.85

        return AgentResult(
            agent_name=self.agent_name,
            score=score,
            flagged=flagged,
            metadata={
                "heuristic_score": heuristic_score,
                "faiss_score": faiss_score,
                "encoding_bonus": encoding_bonus,
                "decoded_payloads": len(decoded_payloads),
                "normalized_diff": normalized != prompt.lower(),
                "pattern_hits": pattern_hits[:5],  # top 5 for audit
                "faiss_vectors": self._faiss.vector_count if self._faiss else 0,
            },
        )
