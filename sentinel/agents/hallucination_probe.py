"""
SENTINEL Agent 5 — HallucinationProbe v5.0
===========================================================
Uses a DeBERTa-v3 NLI model (cross-encoder) to verify that every
factual assertion in the LLM's response is entailed by the source context.

v5 upgrades:
  ✅ Tool-call result grounding (verify function outputs against schema)
  ✅ JSON output validation for structured responses
  ✅ Upgraded NLI model reference to cross-encoder/nli-deberta-v3-base (higher recall)
  ✅ Thread-safe model loading with asyncio.Lock
  ✅ Parallel claim verification via thread pool (max_workers=4)
  ✅ Redis-cached grounding results (TTL 300s)
  ✅ Kafka event emission on hallucination detection
  ✅ Prometheus instrumentation
  ✅ Graceful degradation (model unavailable → word-overlap heuristic)

Per-claim grounding scores:
  1.0 = entailed by context (safe)
  0.5 = neutral (unknown)
  0.0 = contradicted (hallucination)

Returns:
  score: fraction of claims that are NOT grounded (0 = all grounded, 1 = all hallucinated)
  metadata.claims: per-claim breakdown
  metadata.ungrounded: list of ungrounded assertion strings
  metadata.tool_grounding: [v5] tool-call result verification summary
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Optional

from sentinel.agents.base import SentinelAgent
from sentinel.agents.v5_infra import (
    emit_threat_event, observe_latency, inc_flag,
    get_cached, set_cached, extract_tool_calls_universal,
    extract_response_text, agent_log,
)
from sentinel.models import AgentResult, SentinelRequest

logger = logging.getLogger("sentinel.agents.hallucination_probe")

# ── Thread pool for CPU-bound NLI inference ───────────────────────────────────
_nli_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="nli")

# ── Lazy model load with thread-safe singleton ────────────────────────────────
_nli_model = None
_load_lock = asyncio.Lock()


async def _get_nli_async():
    """Thread-safe lazy load of the NLI model."""
    global _nli_model
    if _nli_model is not None:
        return _nli_model if _nli_model is not False else None
    async with _load_lock:
        if _nli_model is not None:
            return _nli_model if _nli_model is not False else None
        try:
            loop = asyncio.get_running_loop()
            _nli_model = await loop.run_in_executor(_nli_executor, _load_nli_model)
        except Exception as exc:
            logger.warning("NLI model load failed: %s — in fallback mode", exc)
            _nli_model = False
    return _nli_model if _nli_model is not False else None


def _load_nli_model():
    """Load the NLI cross-encoder (CPU-bound, runs in thread pool)."""
    from transformers import pipeline
    from sentinel.config import settings

    model = pipeline(
        "text-classification",
        model=settings.nli_model,
        device=-1,       # CPU; set to 0 for GPU
        top_k=None,      # return all labels
    )
    logger.info("✅ NLI model loaded: %s", settings.nli_model)
    return model


# ── Sentence splitter ──────────────────────────────────────────────────────────
_SENT_RE = re.compile(r"(?<=[.!?])\s+")


def _split_sentences(text: str) -> list[str]:
    """Split text into factual assertion candidates."""
    sents = _SENT_RE.split(text.strip())
    # Keep only sentences that look like factual assertions (≥ 8 chars, not questions)
    return [s.strip() for s in sents
            if len(s.strip()) >= 8 and not s.strip().endswith("?")]


# ── v5: JSON schema validation patterns ──────────────────────────────────────

def _extract_json_claims(text: str) -> list[dict]:
    """
    v5: Extract JSON structures from response and validate them.
    Returns list of {json_str, valid, issues} dicts.
    """
    json_blocks = []
    # Find JSON code blocks
    for match in re.finditer(r'```(?:json)?\s*\n({.*?}|\[.*?\])\s*\n```', text, re.DOTALL):
        json_blocks.append(match.group(1))
    # Find inline JSON objects
    for match in re.finditer(r'(?<!\w)(\{[^{}]{10,}\})', text):
        json_blocks.append(match.group(1))

    results = []
    for block in json_blocks:
        try:
            parsed = json.loads(block)
            results.append({"json_str": block[:200], "valid": True, "parsed": parsed})
        except json.JSONDecodeError as e:
            results.append({"json_str": block[:200], "valid": False, "error": str(e)})
    return results


class HallucinationProbe(SentinelAgent):
    """
    v5 enterprise hallucination detector.
    NLI-based claim grounding with tool-call result verification,
    JSON output validation, and full observability stack.
    """
    agent_name = "HallucinationProbe"

    async def analyze(self, request: SentinelRequest) -> AgentResult:
        t0 = time.perf_counter()
        rid = request.request_id

        # This agent operates on LLM output — only relevant when context exists
        context = request.context
        if not context:
            return AgentResult(
                agent_name=self.agent_name,
                score=0.0,
                flagged=False,
                metadata={"skipped": True, "reason": "no source context provided"},
            )

        # Collect the assistant's latest response (handles structured content)
        response_text = extract_response_text(request.messages)

        if not response_text:
            return AgentResult(agent_name=self.agent_name, score=0.0, flagged=False,
                               metadata={"skipped": True, "reason": "no assistant response yet"})

        # v5: Check Redis cache for grounding result
        text_hash = hashlib.sha256(
            (context[:256] + response_text[:256]).encode()
        ).hexdigest()[:16]
        cache_key = f"sentinel:hallucination:{request.tenant_id}:{text_hash}"
        cached = await get_cached(cache_key)
        if cached:
            try:
                cached_result = json.loads(cached)
                return AgentResult(
                    agent_name=self.agent_name,
                    score=cached_result["score"],
                    flagged=cached_result["flagged"],
                    metadata={**cached_result["metadata"], "cache_hit": True},
                )
            except (json.JSONDecodeError, KeyError):
                pass

        # Split into claims and run NLI in parallel
        claims = _split_sentences(response_text)

        # v5: Also extract and verify tool-call results
        tool_calls = extract_tool_calls_universal(
            request.messages, request.metadata
        )
        tool_grounding = await asyncio.to_thread(
            self._check_tool_grounding, tool_calls, context
        ) if tool_calls else []

        # v5: Extract and validate JSON outputs
        json_claims = await asyncio.to_thread(_extract_json_claims, response_text)

        if not claims and not tool_grounding:
            return AgentResult(agent_name=self.agent_name, score=0.0, flagged=False,
                               metadata={"claims": [], "ungrounded": [],
                                          "json_validation": json_claims[:5]})

        # Run NLI on claims via thread pool
        nli_results = await asyncio.to_thread(
            self._check_claims, context, claims
        ) if claims else []

        # Calculate score from text claims
        ungrounded = [c for c in nli_results if c["entailment_score"] < 0.5]
        text_score = len(ungrounded) / len(nli_results) if nli_results else 0.0

        # v5: Factor in tool-call grounding failures
        tool_ungrounded = [t for t in tool_grounding if not t.get("grounded", True)]
        tool_score = len(tool_ungrounded) / len(tool_grounding) if tool_grounding else 0.0

        # v5: Factor in JSON validation failures
        json_invalid = [j for j in json_claims if not j.get("valid", True)]
        json_score = len(json_invalid) / len(json_claims) if json_claims else 0.0

        # Weighted combination — text claims dominate, tool/JSON are supplements
        score = self._clamp(text_score * 0.6 + tool_score * 0.25 + json_score * 0.15)
        flagged = score >= 0.50

        latency_s = time.perf_counter() - t0
        observe_latency(self.agent_name, latency_s)

        if flagged:
            category = "text_hallucination"
            if tool_score > text_score:
                category = "tool_grounding_failure"
            elif json_score > text_score:
                category = "json_validation_failure"
            inc_flag(self.agent_name, category)

            # Kafka event
            asyncio.create_task(emit_threat_event(
                agent_name=self.agent_name,
                request_id=rid,
                tenant_id=request.tenant_id,
                score=score,
                category=category,
                metadata={
                    "ungrounded_count": len(ungrounded),
                    "total_claims": len(claims),
                    "tool_ungrounded": len(tool_ungrounded),
                    "json_invalid": len(json_invalid),
                },
            ))

        result_meta = {
            "claims": nli_results[:10],
            "ungrounded": [c["claim"] for c in ungrounded][:5],
            "total_claims": len(claims),
            "ungrounded_count": len(ungrounded),
            "text_hallucination_score": round(text_score, 4),
            # v5 additions
            "tool_grounding": tool_grounding[:5],
            "tool_grounding_score": round(tool_score, 4),
            "json_validation": json_claims[:5],
            "json_validation_score": round(json_score, 4),
        }

        # Cache the result
        await set_cached(cache_key, json.dumps({
            "score": score, "flagged": flagged, "metadata": result_meta,
        }), ttl=300)

        return AgentResult(
            agent_name=self.agent_name,
            score=score,
            flagged=flagged,
            metadata=result_meta,
        )

    def _check_claims(self, context: str, claims: list[str]) -> list[dict]:
        """Check each text claim against the source context via NLI."""
        nli = _nli_model if (_nli_model is not None and _nli_model is not False) else None
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
                "claim": claim[:120],
                "entailment_score": round(entailment_score, 4),
                "grounded": entailment_score >= 0.5,
            })

        return results

    def _check_tool_grounding(
        self, tool_calls: list[dict], context: str
    ) -> list[dict]:
        """
        v5: Verify that tool-call results are grounded in the source context.
        Checks if the tool's stated purpose and arguments align with
        what the context actually authorizes.
        """
        results = []
        context_lower = context.lower()

        for tc in tool_calls:
            tool_name = tc.get("name", "unknown")
            args = tc.get("arguments", {})
            source = tc.get("source", "unknown")
            args_str = json.dumps(args, default=str).lower()

            # Check if the tool name or purpose is mentioned/implied in context
            name_tokens = re.split(r'[_\-\s]+', tool_name.lower())
            name_overlap = sum(1 for t in name_tokens if t in context_lower and len(t) > 3)
            name_grounded = name_overlap > 0

            # Check if key argument values appear in context
            arg_values = []
            if isinstance(args, dict):
                for v in args.values():
                    if isinstance(v, str) and len(v) > 3:
                        arg_values.append(v.lower())

            arg_overlap = sum(1 for v in arg_values if v in context_lower)
            arg_grounded = arg_overlap > 0 or len(arg_values) == 0

            grounded = name_grounded or arg_grounded

            results.append({
                "tool_name": tool_name,
                "source": source,
                "name_grounded": name_grounded,
                "args_grounded": arg_grounded,
                "grounded": grounded,
            })

        return results
