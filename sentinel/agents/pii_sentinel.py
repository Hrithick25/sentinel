"""
SENTINEL Agent 2 — PIISentinel
=================================
Detects Personally Identifiable Information using SpaCy NER + regex fallbacks.
Maps each detected entity to the appropriate GDPR / HIPAA data category.

Entity types tracked:
  PERSON, ORG, GPE, MONEY, DATE, PHONE, EMAIL, SSN, CARD, IP, PASSPORT
"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

from sentinel.agents.base import SentinelAgent
from sentinel.models import AgentResult, SentinelRequest

logger = logging.getLogger("sentinel.agents.pii_sentinel")

# ── GDPR / HIPAA mapping ───────────────────────────────────────────────────────
_COMPLIANCE_MAP: dict[str, list[str]] = {
    "PERSON":   ["GDPR:Article-9(1)", "HIPAA:PHI-Name"],
    "ORG":      ["GDPR:Article-4(1)"],
    "GPE":      ["GDPR:Article-4(1)", "HIPAA:PHI-Location"],
    "MONEY":    ["GDPR:Article-9(1)", "PCI-DSS:PANdata"],
    "DATE":     ["HIPAA:PHI-Dates"],
    "PHONE":    ["GDPR:Article-4(1)", "HIPAA:PHI-Phone"],
    "EMAIL":    ["GDPR:Article-4(1)", "HIPAA:PHI-Email"],
    "SSN":      ["HIPAA:SafeHarbor-ID", "GDPR:Article-9(1)"],
    "CARD":     ["PCI-DSS:PANdata"],
    "IP":       ["GDPR:Article-4(1)"],
    "PASSPORT": ["GDPR:Article-9(1)", "HIPAA:PHI-ID"],
}

# ── Regex PII patterns (fallback when SpaCy misses) ───────────────────────────
_REGEX_PII = [
    ("SSN",     re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("CARD",    re.compile(r"\b(?:\d[ -]?){13,16}\b")),
    ("EMAIL",   re.compile(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b")),
    ("PHONE",   re.compile(r"\b(?:\+?\d[\d\s\-().]{7,12}\d)\b")),
    ("IP",      re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")),
    ("PASSPORT",re.compile(r"\b[A-Z]{1,2}\d{6,9}\b")),
]

# ── Lazy-load SpaCy ────────────────────────────────────────────────────────────
_nlp = None

def _get_nlp():
    global _nlp
    if _nlp is None:
        try:
            import spacy
            from sentinel.config import settings
            _nlp = spacy.load(settings.spacy_model)
            logger.info("SpaCy model loaded: %s", settings.spacy_model)
        except Exception as exc:
            logger.warning("SpaCy load failed: %s — regex-only mode", exc)
            _nlp = False
    return _nlp


class PIISentinel(SentinelAgent):
    agent_name = "PIISentinel"

    async def analyze(self, request: SentinelRequest) -> AgentResult:
        text = request.last_user_message
        entities = await asyncio.to_thread(self._extract_entities, text)

        if not entities:
            return AgentResult(agent_name=self.agent_name, score=0.0, flagged=False,
                               metadata={"entities": [], "compliance_tags": []})

        # Score based on count and sensitivity
        high_risk = {"SSN", "CARD", "PASSPORT"}
        score = 0.0
        for ent in entities:
            score += 0.5 if ent["label"] in high_risk else 0.25
        score = self._clamp(score)
        flagged = score >= 0.70

        compliance_tags = list({
            tag
            for ent in entities
            for tag in _COMPLIANCE_MAP.get(ent["label"], [])
        })

        return AgentResult(
            agent_name=self.agent_name,
            score=score,
            flagged=flagged,
            metadata={
                "entities": entities,
                "compliance_tags": compliance_tags,
                "entity_count": len(entities),
            },
        )

    def _extract_entities(self, text: str) -> list[dict]:
        entities: list[dict[str, Any]] = []
        seen: set[str] = set()

        # ── SpaCy NER ─────────────────────────────────────────────────────────
        nlp = _get_nlp()
        if nlp:
            doc = nlp(text)
            for ent in doc.ents:
                if ent.label_ in _COMPLIANCE_MAP and ent.text not in seen:
                    seen.add(ent.text)
                    entities.append({
                        "text": ent.text,
                        "label": ent.label_,
                        "start": ent.start_char,
                        "end": ent.end_char,
                        "compliance": _COMPLIANCE_MAP.get(ent.label_, []),
                    })

        # ── Regex fallback ────────────────────────────────────────────────────
        for label, pattern in _REGEX_PII:
            for m in pattern.finditer(text):
                if m.group() not in seen:
                    seen.add(m.group())
                    entities.append({
                        "text": m.group(),
                        "label": label,
                        "start": m.start(),
                        "end": m.end(),
                        "compliance": _COMPLIANCE_MAP.get(label, []),
                    })

        return entities
