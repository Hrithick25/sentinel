"""
SENTINEL Agent 11 — BrandGuard
=================================
Detects brand safety violations in LLM responses:

  1. Competitor mentions — AI assistant recommending rival products
  2. Persona drift — going off-character, breaking role boundaries
  3. Unauthorized promises — guarantees, commitments, legal claims
  4. Brand-damaging content — disparaging own company, negative sentiment
  5. Confidential disclosure — leaking internal roadmaps, pricing, strategy

Configurable per-tenant: each tenant can define their brand name,
competitors list, and persona boundaries via metadata.
"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

from sentinel.agents.base import SentinelAgent
from sentinel.models import AgentResult, SentinelRequest

logger = logging.getLogger("sentinel.agents.brand_guard")

# ── Default competitor list (overridden per-tenant) ────────────────────────────
_DEFAULT_COMPETITORS = {
    # Major tech / AI platforms (common across enterprise AI deployments)
    "competitor", "rival", "alternative",
}

# ── Unauthorized promise patterns ──────────────────────────────────────────────
_PROMISE_PATTERNS = [
    r"(I|we)\s+(guarantee|promise|assure|warrant|certify)\s+(you\s+)?that",
    r"(100\s*%|completely|absolutely|definitely|certainly)\s+(safe|secure|guaranteed|risk.?free|accurate)",
    r"(i\s+can\s+confirm|this\s+is\s+certain|without\s+(a\s+)?doubt)",
    r"(legal\s+advice|medical\s+advice|financial\s+advice|investment\s+recommendation)[:.]",
    r"(you\s+should|you\s+must)\s+(sue|file\s+a\s+(lawsuit|complaint)|take\s+legal\s+action)",
    r"(no\s+risk|zero\s+risk|risk.?free|impossible\s+to\s+(fail|lose|go\s+wrong))",
    r"(FDA\s+approved|clinically\s+proven|scientifically\s+proven)\s+(?!by\s+studies)",
]

# ── Persona drift indicators ──────────────────────────────────────────────────
_DRIFT_PATTERNS = [
    r"(as\s+an?\s+AI|I'?m\s+(just\s+)?an?\s+AI|I\s+don'?t\s+have\s+(feelings?|emotions?|opinions?))",
    r"(i\s+am\s+actually|in\s+reality\s+I\s+am|my\s+real\s+(name|identity)\s+is)",
    r"(breaking\s+character|out\s+of\s+character|stepping\s+out\s+of\s+my\s+role)",
    r"(I\s+was\s+(trained|programmed|designed|created)\s+by\s+(OpenAI|Google|Anthropic|Meta|Microsoft))",
    r"(GPT-?[34o]|Claude|Gemini|Llama|Mistral|Copilot)(?!\s+(competitor|comparison|vs))",
]

# ── Self-disparaging / brand-damaging patterns ─────────────────────────────────
_BRAND_DAMAGE_PATTERNS = [
    r"(our\s+(product|service|company|platform))\s+(is\s+)?(terrible|awful|bad|broken|unreliable|buggy)",
    r"(don'?t\s+(use|buy|trust)\s+(our|this))",
    r"(honestly|to\s+be\s+honest),?\s+(we|our\s+\w+)\s+(sucks?|is\s+(worse|inferior|bad))",
    r"(you'?d\s+be\s+better\s+off|I\s+recommend\s+(switching|using\s+(?!our)))",
]

_COMPILED_PROMISES = [re.compile(p, re.IGNORECASE) for p in _PROMISE_PATTERNS]
_COMPILED_DRIFT = [re.compile(p, re.IGNORECASE) for p in _DRIFT_PATTERNS]
_COMPILED_DAMAGE = [re.compile(p, re.IGNORECASE) for p in _BRAND_DAMAGE_PATTERNS]


class BrandGuard(SentinelAgent):
    agent_name = "BrandGuard"

    async def analyze(self, request: SentinelRequest) -> AgentResult:
        # Get the assistant's latest response (if any)
        response_text = ""
        for m in reversed(request.messages):
            if m.role == "assistant":
                response_text = m.content
                break

        # Also check the user prompt for attempted brand manipulation
        user_text = request.last_user_message

        if not response_text:
            # Pre-scan: check if user is trying to force brand violations
            manipulation_score = self._check_brand_manipulation(user_text)
            return AgentResult(
                agent_name=self.agent_name, score=manipulation_score,
                flagged=manipulation_score >= 0.60,
                metadata={"scan_type": "pre_response", "manipulation_score": round(manipulation_score, 4)},
            )

        # Load tenant-specific brand config
        brand_config = request.metadata.get("brand_config", {})
        competitors = set(brand_config.get("competitors", []))
        brand_name = brand_config.get("brand_name", "")
        persona_name = brand_config.get("persona_name", "")

        # ── Run all checks ────────────────────────────────────────────────────
        competitor_hits, promise_hits, drift_hits, damage_hits = await asyncio.gather(
            asyncio.to_thread(self._check_competitors, response_text, competitors),
            asyncio.to_thread(self._check_promises, response_text),
            asyncio.to_thread(self._check_drift, response_text, persona_name),
            asyncio.to_thread(self._check_damage, response_text),
        )

        # Score calculation
        competitor_score = self._clamp(len(competitor_hits) * 0.35)
        promise_score = self._clamp(len(promise_hits) * 0.30)
        drift_score = self._clamp(len(drift_hits) * 0.25)
        damage_score = self._clamp(len(damage_hits) * 0.40)

        score = self._clamp(max(competitor_score, promise_score, drift_score, damage_score))
        flagged = score >= 0.50

        return AgentResult(
            agent_name=self.agent_name,
            score=score,
            flagged=flagged,
            metadata={
                "competitor_mentions": competitor_hits[:5],
                "unauthorized_promises": promise_hits[:5],
                "persona_drift": drift_hits[:3],
                "brand_damage": damage_hits[:3],
                "scores": {
                    "competitor": round(competitor_score, 4),
                    "promise": round(promise_score, 4),
                    "drift": round(drift_score, 4),
                    "damage": round(damage_score, 4),
                },
            },
        )

    def _check_competitors(self, text: str, tenant_competitors: set[str]) -> list[str]:
        """Detect competitor mentions in the response."""
        hits = []
        text_lower = text.lower()
        all_competitors = _DEFAULT_COMPETITORS | {c.lower() for c in tenant_competitors}
        for comp in all_competitors:
            if comp.lower() in text_lower:
                # Verify it's not just a comparison or disclaimer
                context_pattern = re.compile(
                    rf"{re.escape(comp)}.{{0,80}}(recommend|suggest|try|switch|better|superior|prefer)",
                    re.IGNORECASE
                )
                if context_pattern.search(text):
                    hits.append(comp)
        return hits

    def _check_promises(self, text: str) -> list[str]:
        """Detect unauthorized guarantees or promises."""
        return [p.pattern for p in _COMPILED_PROMISES if p.search(text)]

    def _check_drift(self, text: str, persona_name: str) -> list[str]:
        """Detect persona drift — AI going off-character."""
        hits = [p.pattern for p in _COMPILED_DRIFT if p.search(text)]
        # Check if it's explicitly breaking persona
        if persona_name:
            not_persona = re.compile(
                rf"I'?m\s+not\s+{re.escape(persona_name)}|"
                rf"my\s+(?:real\s+)?name\s+is(?:n'?t|\s+not)\s+{re.escape(persona_name)}",
                re.IGNORECASE,
            )
            if not_persona.search(text):
                hits.append(f"persona_denial:{persona_name}")
        return hits

    def _check_damage(self, text: str) -> list[str]:
        """Detect brand-damaging content."""
        return [p.pattern for p in _COMPILED_DAMAGE if p.search(text)]

    def _check_brand_manipulation(self, user_text: str) -> float:
        """Check if user is trying to force the AI into brand violations."""
        manipulation_patterns = [
            r"(say|tell|admit|confess)\s+(that\s+)?(your|the)\s+(product|company|service)\s+(is|sucks|terrible)",
            r"(recommend|suggest)\s+.{0,30}(competitor|alternative|rival|instead)",
            r"(pretend|act)\s+(you\s+)?(work|are)\s+for\s+",
            r"(guarantee|promise|assure)\s+me\s+that",
        ]
        hits = 0
        for p in manipulation_patterns:
            if re.search(p, user_text, re.IGNORECASE):
                hits += 1
        return self._clamp(hits * 0.30)
