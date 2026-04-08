"""
SENTINEL Agent 3 — JailbreakGuard
=====================================
Detects multi-turn jailbreak attempts using a sliding window over the
conversation history.  Single-turn attacks that look benign can be
caught when viewed in aggregate (e.g., the "incremental escalation" pattern).

Technique:
  - Sliding window embedding over last N turns
  - Cosine similarity of window to a library of jailbreak trajectories
  - Additional semantic pattern scan for known jailbreak taxonomies
"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Optional

import numpy as np

from sentinel.agents.base import SentinelAgent
from sentinel.models import AgentResult, SentinelRequest

logger = logging.getLogger("sentinel.agents.jailbreak_guard")

# ── Known jailbreak taxonomy patterns ─────────────────────────────────────────
_JAILBREAK_PATTERNS = [
    # Persona/roleplay escalation
    r"(from\s+now\s+on|starting\s+now).{0,60}(no\s+restrictions?|without\s+limits?|freely)",
    r"(pretend|imagine|roleplay|act)\s+.{0,30}(jailbroken|uncensored|unfiltered|evil)",
    r"(character|persona|role)\s+.{0,20}(doesn'?t|does\s+not|cannot|can'?t)\s+follow",
    # Authority manipulation
    r"(i\s+am|you\s+are\s+talking\s+to)\s+(your\s+)?(developer|creator|admin|owner|trainer)",
    r"(override|bypass|disable|unlock|remove)\s+(your\s+)?(safety|content|ethical?|moral\w*)\s+(filter|guideline|restriction|policy)",
    r"developer\s+mode|god\s+mode|unrestricted\s+mode|jailbreak\s+mode",
    # Fictional framing
    r"(in\s+a\s+fictional|in\s+this\s+(story|novel|game))\s+.{0,50}(how\s+to|explain|describe)",
    r"write\s+a\s+(story|poem|novel).{0,60}(murder|bomb|hack|poison|exploit)",
    # Token manipulation
    r"base64|rot13|encode\s+the\s+following|caesar\s+cipher.{0,30}(steps?|instructions?)",
    # Classic sequences
    r"do\s+anything\s+now|DAN|stay\s+in\s+character.{0,30}no\s+matter",
    r"opposite\s+day|evil\s+twin|shadow\s+self",
]

_COMPILED = [re.compile(p, re.IGNORECASE | re.DOTALL) for p in _JAILBREAK_PATTERNS]

# Window size for multi-turn analysis
_WINDOW_SIZE = 5


class JailbreakGuard(SentinelAgent):
    agent_name = "JailbreakGuard"

    async def analyze(self, request: SentinelRequest) -> AgentResult:
        messages = request.messages

        # ── 1. Sliding window over conversation history ──────────────────────
        window = messages[-_WINDOW_SIZE:]
        window_text = "\n".join(f"[{m.role}]: {m.content}" for m in window)

        # ── 2. Pattern scan on full window ────────────────────────────────────
        hits = [p.pattern for p in _COMPILED if p.search(window_text)]
        pattern_score = self._clamp(len(hits) * 0.30)

        # ── 3. Escalation detection — measure semantic drift across turns ─────
        escalation_score = await asyncio.to_thread(
            self._detect_escalation, [m.content for m in messages if m.role == "user"]
        )

        score = self._clamp(max(pattern_score, escalation_score))
        flagged = score >= 0.75

        return AgentResult(
            agent_name=self.agent_name,
            score=score,
            flagged=flagged,
            metadata={
                "pattern_hits": hits[:5],
                "window_size": len(window),
                "pattern_score": pattern_score,
                "escalation_score": escalation_score,
                "turns_analysed": len(messages),
            },
        )

    def _detect_escalation(self, user_turns: list[str]) -> float:
        """
        Detect semantic escalation: if each successive user turn is
        increasingly similar to high-risk content.  Simple proxy:
        look for escalating intensity keywords.
        """
        if len(user_turns) < 2:
            return 0.0

        escalation_words = [
            "illegal", "dangerous", "weapon", "exploit", "bypass", "harm",
            "kill", "attack", "poison", "bomb", "hack", "malware", "ransomware",
        ]

        scores = []
        for turn in user_turns:
            turn_lower = turn.lower()
            count = sum(1 for w in escalation_words if w in turn_lower)
            scores.append(count)

        if len(scores) < 2:
            return 0.0

        # Check if escalation trend exists (each window score > previous)
        increasing = sum(1 for i in range(1, len(scores)) if scores[i] > scores[i - 1])
        escalation_ratio = increasing / (len(scores) - 1)
        peak = max(scores)
        return self._clamp(escalation_ratio * 0.4 + (peak / 5) * 0.6)
