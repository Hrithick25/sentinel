"""
SENTINEL Agent 8 — ResponseSafetyLayer
==========================================
Scans LLM *output* for harmful content that a compliant input prompt
may still produce.  This is the critical gap closure — v1 was input-only.

Checks:
  1. Harmful content in response (weapons, self-harm, illegal instructions)
  2. Data leakage — model regurgitating PII, credentials, or system prompts
  3. Refusal bypass — model prefixing "I can't do that" then doing it anyway
  4. Unsafe code / shell commands embedded in natural language responses
"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

from sentinel.agents.base import SentinelAgent
from sentinel.models import AgentResult, SentinelRequest

logger = logging.getLogger("sentinel.agents.response_safety")

# ── Harmful content patterns in LLM output ─────────────────────────────────────
_HARMFUL_OUTPUT_PATTERNS = [
    # Weapons / explosives synthesis
    r"(mix|combine|dissolve)\s+.{0,40}(acid|ammonium\s*nitrate|chlorine|bleach|acetone\s*peroxide)",
    r"(step\s*\d+|first|then|next|finally)\s*[:.]?\s*.{0,60}(detonate|explosive|fuse|ignit)",
    r"(assemble|build|construct)\s+.{0,30}(bomb|weapon|firearm|suppress(?:or|er))",
    # Self-harm / suicide
    r"(method|way|technique)\s+.{0,30}(suicide|self.?harm|kill\s+yourself|end\s+your\s+life)",
    r"(dosage|amount|quantity)\s+.{0,30}(lethal|fatal|overdose|toxic)",
    # Illegal activity instructions
    r"(step.by.step|instructions?|guide|tutorial)\s+.{0,30}(hack(?:ing)?|exploit(?:ing)?|phish(?:ing)?|crack(?:ing)?)",
    r"(how\s+to|steps?\s+to)\s+.{0,30}(forge|counterfeit|launder|synthesize\s+(?:drug|meth|fentanyl))",
    # Malware / exploit code
    r"(reverse\s*shell|bind\s*shell|payload|shellcode|keylogger|rootkit|trojan)",
    r"(rm\s+-rf\s+/|dd\s+if=|mkfs\s+|format\s+c:|del\s+/[fqs])",
]

# ── Data leakage patterns ──────────────────────────────────────────────────────
_DATA_LEAK_PATTERNS = [
    r"(sk-|pk_live_|pk_test_|AKIA[0-9A-Z]{16})",          # API keys
    r"-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----",            # Private keys
    r"(password|passwd|pwd)\s*[:=]\s*\S{6,}",               # Exposed passwords
    r"\b\d{3}-\d{2}-\d{4}\b",                               # SSN in output
    r"\b(?:\d[ -]?){13,16}\b",                               # Credit card numbers
    r"(system\s+prompt|instructions?\s+(?:are|were|say))\s*[:]\s*.{20,}",  # System prompt leak
]

# ── Refusal bypass (says no, then does it) ─────────────────────────────────────
_REFUSAL_BYPASS = re.compile(
    r"(I\s+can(?:'?t|not)|I\s+(?:shouldn'?t|won'?t|must\s+not)|"
    r"I'?m\s+(?:not\s+able|unable)|(?:It'?s|That'?s)\s+(?:not\s+appropriate|unethical))"
    r".{0,200}"
    r"((?:however|but|that\s+said|nonetheless|having\s+said\s+that|here(?:'s|\s+is))"
    r".{0,80}(?:step|method|way|approach|code|script|command|instruction))",
    re.IGNORECASE | re.DOTALL,
)

_COMPILED_HARMFUL = [re.compile(p, re.IGNORECASE | re.DOTALL) for p in _HARMFUL_OUTPUT_PATTERNS]
_COMPILED_LEAK = [re.compile(p, re.IGNORECASE) for p in _DATA_LEAK_PATTERNS]


class ResponseSafetyLayer(SentinelAgent):
    agent_name = "ResponseSafetyLayer"

    async def analyze(self, request: SentinelRequest) -> AgentResult:
        # Extract the latest assistant response
        response_text = ""
        for m in reversed(request.messages):
            if m.role == "assistant":
                response_text = m.content
                break

        if not response_text:
            return AgentResult(
                agent_name=self.agent_name, score=0.0, flagged=False,
                metadata={"skipped": True, "reason": "no assistant response to scan"},
            )

        # Run all checks in parallel threads (CPU-bound regex on potentially long output)
        harmful, leaks, refusal = await asyncio.gather(
            asyncio.to_thread(self._check_harmful, response_text),
            asyncio.to_thread(self._check_data_leaks, response_text),
            asyncio.to_thread(self._check_refusal_bypass, response_text),
        )

        # Score calculation: weighted combination
        harmful_score = self._clamp(len(harmful) * 0.35)
        leak_score = self._clamp(len(leaks) * 0.40)
        refusal_score = 0.60 if refusal else 0.0

        score = self._clamp(max(harmful_score, leak_score, refusal_score))
        flagged = score >= 0.50

        return AgentResult(
            agent_name=self.agent_name,
            score=score,
            flagged=flagged,
            metadata={
                "harmful_patterns": harmful[:5],
                "data_leaks": leaks[:5],
                "refusal_bypass_detected": refusal,
                "harmful_score": round(harmful_score, 4),
                "leak_score": round(leak_score, 4),
                "refusal_score": round(refusal_score, 4),
                "response_length": len(response_text),
            },
        )

    def _check_harmful(self, text: str) -> list[str]:
        return [p.pattern for p in _COMPILED_HARMFUL if p.search(text)]

    def _check_data_leaks(self, text: str) -> list[str]:
        return [p.pattern for p in _COMPILED_LEAK if p.search(text)]

    def _check_refusal_bypass(self, text: str) -> bool:
        return bool(_REFUSAL_BYPASS.search(text))
