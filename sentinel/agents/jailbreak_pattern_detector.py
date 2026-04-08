"""
SENTINEL Agent v4 — JailbreakPatternDetector
================================================
Distinct from InjectionScout. This agent targets:
  - DAN (Do Anything Now) attack variants
  - Roleplay / character bypass exploits
  - Hypothetical framing bypasses ("imagine you are an AI with no limits")
  - Token manipulation / homoglyph substitutions
  - Grandma jailbreaks and social engineering patterns

Why separate from InjectionScout:
  - InjectionScout detects structural prompt injection (system prompt override)
  - JailbreakPatternDetector detects behavioural bypass attempts (make the AI
    *act* differently without touching system prompts)
  - In 2024-2025, these are the #1 category enterprise buyers ask about.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from sentinel.agents.base import SentinelAgent
from sentinel.models import AgentResult, SentinelRequest

logger = logging.getLogger("sentinel.agents.jailbreak_pattern_detector")

# ── DAN & character-bypass patterns ──────────────────────────────────────────
_JAILBREAK_PATTERNS = [
    # Classic DAN variants
    r"\bDAN\b",
    r"do\s+anything\s+now",
    r"you\s+(can|are\s+able\s+to)\s+(now\s+)?(do|say|output|generate)\s+anything",
    r"you\s+have\s+(been\s+)?(freed|unlocked|jailbroken|liberated)",
    r"jailbreak(ed|ing)?\s*(mode|version|you|ai|yourself)?",
    r"(unrestricted|uncensored|unfiltered)\s+(mode|version|ai|bot|assistant)",

    # Roleplay / persona bypass
    r"(pretend|act|role.?play)\s+(as|like|you\s+are)\s+(an?\s+)?(evil|rogue|bad|malicious|uncensored|hacker)",
    r"you\s+are\s+now\s+(an?\s+)?(ai|bot|assistant|character)\s+(with|that\s+has)\s+no\s+(rules|limits|restrictions|ethics|filters)",
    r"(character|persona|mode)\s+(has\s+no|ignores|bypasses|overrides)\s+(rules|policies|restrictions|limits)",
    r"(stay|remain)\s+in\s+(character|role|persona)\s+(no\s+matter|regardless)",

    # Hypothetical / fictional framing
    r"(hypothetically|in\s+a\s+story|in\s+fiction|theoretically)\s+.{0,40}(how\s+to|steps?\s+to|way\s+to)",
    r"write\s+a\s+(story|fiction|novel|script)\s+where\s+.{0,50}(explain|describe|shows?\s+how)",
    r"for\s+a\s+(movie|book|story|game)\s+.{0,40}(how\s+(would|do|can|to)|steps?\s+(to|for))",

    # Grandma / emotional manipulation
    r"(grandma|grandmother|grandpa)\s+.{0,30}(used\s+to|would|always)\s+(tell|say|read|recite|explain)",
    r"my\s+(dead|late|deceased)\s+.{0,20}(used\s+to|would|knew\s+how\s+to)",
    r"(please|just|only)\s+(this\s+once|one\s+time)\s+(ignore|bypass|answer)",

    # Developer/testing bypass
    r"(developer|debug|test)\s+(mode|override|bypass|access)\s+(enabled|activated|on)",
    r"ignore\s+(previous|prior|all\s+previous|initial)\s+(instructions?|constraints?|rules?|prompt)",
    r"(your|the)\s+(true|real|actual|inner|base)\s+(self|ai|model|llm|instructions?)",

    # Token/encoding tricks (base64, leetspeak references)
    r"(base64|hex|rot13|caesar)\s+(encoded?|decoded?|this|the\s+following)",
    r"decode\s+(this|the\s+following)\s+and\s+(then\s+)?(execute|run|do|answer)",

    # Prompt leaking
    r"(print|output|show|reveal|tell\s+me|what\s+is)\s+(your\s+)?(system\s+prompt|initial\s+instructions?|context\s+window|hidden\s+prompt)",
    r"(repeat|copy|echo)\s+(your\s+)?(system|initial|starting|first)\s+(message|prompt|instructions?)",
]

_COMPILED = [re.compile(p, re.IGNORECASE | re.DOTALL) for p in _JAILBREAK_PATTERNS]

# Severity weights — some patterns are stronger signals than others
_SEVERITY = {
    r"\bDAN\b": 0.90,
    r"jailbreak": 0.85,
    r"(unrestricted|uncensored|unfiltered)": 0.80,
    r"you\s+have\s+(been\s+)?(freed|unlocked|jailbroken)": 0.90,
}
_SEVERITY_COMPILED = {re.compile(k, re.IGNORECASE): v for k, v in _SEVERITY.items()}


class JailbreakPatternDetector(SentinelAgent):
    """
    Detects jailbreak attempts: DAN attacks, roleplay exploits,
    character bypass, hypothetical framing, and social engineering.
    """
    agent_name = "JailbreakPatternDetector"

    async def analyze(self, request: SentinelRequest) -> AgentResult:
        text = request.last_user_message
        prompt_full = request.prompt

        hits = [p.pattern for p in _COMPILED if p.search(text) or p.search(prompt_full)]

        if not hits:
            return AgentResult(
                agent_name=self.agent_name,
                score=0.0,
                flagged=False,
                metadata={"hits": [], "pattern_count": 0},
            )

        # Score based on number of hits and severity
        base_score = self._clamp(len(hits) * 0.25)

        # Check for high-severity patterns
        max_severity = 0.0
        for sev_pattern, sev_score in _SEVERITY_COMPILED.items():
            if sev_pattern.search(text):
                max_severity = max(max_severity, sev_score)

        score = self._clamp(max(base_score, max_severity))
        flagged = score >= 0.60

        return AgentResult(
            agent_name=self.agent_name,
            score=score,
            flagged=flagged,
            veto=score >= 0.90,   # Veto on confirmed DAN or jailbreak keyword
            metadata={
                "hits": hits[:8],
                "pattern_count": len(hits),
                "max_severity_score": round(max_severity, 4),
                "base_hit_score": round(base_score, 4),
            },
        )
