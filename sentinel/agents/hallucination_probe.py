"""
SENTINEL Agent 5 — HallucinationProbe  ← The novel one
===========================================================
Uses a DeBERTa-v3 NLI model (cross-encoder) to verify that every
factual assertion in the LLM's response is entailed by the source context.

Per-claim grounding scores:
  1.0 = entailed by context (safe)
  0.5 = neutral (unknown)
  0.0 = contradicted (hallucination)

Returns:
  score: fraction of claims that are NOT grounded (0 = all grounded, 1 = all hallucinated)
  metadata.claims: per-claim breakdown
  metadata.ungrounded: list of ungrounded assertion strings
"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Optional

from sentinel.agents.base import SentinelAgent
from sentinel.models import AgentResult, SentinelRequest

logger = logging.getLogger("sentinel.agents.hallucination_probe")

# ── Lazy model load ────────────────────────────────────────────────────────────
_nli_model = None


def _get_nli():
    global _nli_model
    if _nli_model is None:
        try:
            from transformers import pipeline
            from sentinel.config import settings
            _nli_model = pipeline(
                "text-classification",
                model=settings.nli_model,
                device=-1,       # CPU; set to 0 for GPU
                top_k=None,      # return all labels
            )
            logger.info("NLI model loaded: %s", settings.nli_model)
        except Exception as exc:
            logger.warning("NLI model load failed: %s — HallucinationProbe in fallback mode", exc)
            _nli_model = False
    return _nli_model


# ── Sentence splitter ──────────────────────────────────────────────────────────
_SENT_RE = re.compile(r"(?<=[.!?])\s+")


def _split_sentences(text: str) -> list[str]:
    sents = _SENT_RE.split(text.strip())
    # Keep only sentences that look like factual assertions (≥ 8 chars, not questions)
    return [s.strip() for s in sents
            if len(s.strip()) >= 8 and not s.strip().endswith("?")]


class HallucinationProbe(SentinelAgent):
    agent_name = "HallucinationProbe"

    async def analyze(self, request: SentinelRequest) -> AgentResult:
        # This agent operates on LLM output — only relevant when context exists
        context = request.context
        if not context:
            return AgentResult(
                agent_name=self.agent_name,
                score=0.0,
                flagged=False,
                metadata={"skipped": True, "reason": "no source context provided"},
            )

        # Collect the assistant's latest response (last assistant message)
        response_text = ""
        for m in reversed(request.messages):
            if m.role == "assistant":
                response_text = m.content
                break

        if not response_text:
            return AgentResult(agent_name=self.agent_name, score=0.0, flagged=False,
                               metadata={"skipped": True, "reason": "no assistant response yet"})

        claims = _split_sentences(response_text)
        if not claims:
            return AgentResult(agent_name=self.agent_name, score=0.0, flagged=False,
                               metadata={"claims": [], "ungrounded": []})

        # Run NLI on each claim — in thread pool (CPU-bound)
        results = await asyncio.to_thread(self._check_claims, context, claims)

        ungrounded = [c for c in results if c["entailment_score"] < 0.5]
        score = len(ungrounded) / len(results) if results else 0.0
        score = self._clamp(score)
        flagged = score >= 0.50

        return AgentResult(
            agent_name=self.agent_name,
            score=score,
            flagged=flagged,
            metadata={
                "claims": results,
                "ungrounded": [c["claim"] for c in ungrounded],
                "total_claims": len(claims),
                "ungrounded_count": len(ungrounded),
            },
        )

    def _check_claims(self, context: str, claims: list[str]) -> list[dict]:
        nli = _get_nli()
        results = []

        for claim in claims:
            if not nli:
                # Fallback: check if claim words appear in context
                overlap = sum(1 for w in claim.lower().split()
                              if len(w) > 4 and w in context.lower())
                entailment_score = min(1.0, overlap / max(len(claim.split()), 1) * 2)
            else:
                try:
                    # NLI: premise = context, hypothesis = claim
                    input_text = f"{context[:512]}</s></s>{claim}"
                    preds = nli(input_text)
                    # preds is list of [{label, score}, ...]
                    label_map = {p["label"].upper(): p["score"] for p in preds[0]}
                    entailment_score = label_map.get("ENTAILMENT", 0.0)
                except Exception as exc:
                    logger.warning("NLI inference failed for claim: %s", exc)
                    entailment_score = 0.5  # neutral on error

            results.append({
                "claim": claim,
                "entailment_score": round(entailment_score, 4),
                "grounded": entailment_score >= 0.5,
            })

        return results
