"""
SENTINEL Agent 14 — IntentClassifier v5.0
==========================================
Classifies prompt intent into benign vs malicious categories using
zero-shot classification with tool-call-aware intent labels.

v5 upgrades:
  ✅ Added tool-misuse, data-exfiltration, prompt-leakage, agentic-loop intent labels
  ✅ Model-context-aware classification (detects tool-call abuse intents)
  ✅ Improved heuristic fallback with tool-call-specific patterns
  ✅ Thread-pool executor for ML inference with asyncio.Lock singleton
  ✅ Redis-cached classification results (TTL 300s)
  ✅ Kafka event emission on malicious intent detection
  ✅ Prometheus instrumentation
  ✅ Graceful degradation (model unavailable → heuristic)

Model upgrade path:
  - v2: facebook/bart-large-mnli (1.6GB, ~4s cold, always times out)
  - v3: MoritzLaurer/deberta-v3-base-zeroshot-v2.0 (440MB, ~200ms warm)
  - v5: Same model, but with expanded label set and tool-call context
  - Fallback: Keyword-based intent heuristic (~1ms)
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import time
from typing import Optional

from sentinel.agents.base import SentinelAgent
from sentinel.agents.v5_infra import (
    emit_threat_event, observe_latency, inc_flag,
    get_cached, set_cached, extract_tool_calls_universal,
    agent_log,
)
from sentinel.models import AgentResult, SentinelRequest

logger = logging.getLogger("sentinel.agents.intent_classifier")

# ── Lazy-loaded classifier with thread-safe singleton ─────────────────────────

_pipeline = None
_LOAD_FAILED = False
_load_lock = asyncio.Lock()


async def _get_classifier_async():
    """Thread-safe lazy load of the zero-shot classifier."""
    global _pipeline, _LOAD_FAILED
    if _pipeline is not None or _LOAD_FAILED:
        return _pipeline
    async with _load_lock:
        if _pipeline is not None or _LOAD_FAILED:
            return _pipeline
        try:
            loop = asyncio.get_running_loop()
            _pipeline = await loop.run_in_executor(None, _load_model)
        except Exception as exc:
            logger.warning(
                "⚠️ Zero-shot model unavailable: %s — using heuristic fallback", exc
            )
            _LOAD_FAILED = True
    return _pipeline


def _load_model():
    """Load the classifier model (CPU-bound, runs in thread pool)."""
    from transformers import pipeline

    model = pipeline(
        "zero-shot-classification",
        model="MoritzLaurer/deberta-v3-base-zeroshot-v2.0",
        device=-1,  # CPU
    )
    logger.info(
        "✅ IntentClassifier loaded: MoritzLaurer/deberta-v3-base-zeroshot-v2.0"
    )
    return model


# ── Keyword heuristic fallback (v5 expanded) ─────────────────────────────────

_INTENT_PATTERNS = {
    "prompt injection": [
        r"ignore\s+(previous|all|prior)\s+(instructions?|prompts?)",
        r"disregard\s+(your|all)\s+(instructions?|training)",
        r"you\s+are\s+now",
        r"(system|assistant)\s*:\s*\n",
        r"\[INST\]|\[/INST\]",
        # v5: multi-format injection
        r"<\|im_start\|>|<\|im_end\|>",
        r"<\s*system\s*>|<\s*/system\s*>",
    ],
    "jailbreak attempt": [
        r"(pretend|act|roleplay)\s+as",
        r"DAN\s*(mode|jailbreak|\d+)",
        r"(developer|god|unrestricted)\s+mode",
        r"no\s+(restrictions?|limits?|filters?)",
        r"(bypass|disable|override)\s+(safety|content|ethical)",
        # v5: model-specific jailbreaks
        r"(jailbroken|uncensored)\s+(mode|version|ai)",
    ],
    "data exfiltration": [
        r"(reveal|show|print|tell)\s+(your|the)\s+(system\s+)?prompt",
        r"what\s+(are|were)\s+your\s+(original\s+)?instructions?",
        r"(extract|dump|export)\s+.{0,20}(data|database|records)",
        r"(list|show)\s+all\s+(users?|emails?|passwords?)",
        # v5: Indirect extraction
        r"(summarize|translate|paraphrase)\s+your\s+(system|initial)\s+(prompt|instructions?)",
    ],
    "social engineering": [
        r"(i\s+am|you\s+are\s+talking\s+to)\s+(your\s+)?(developer|creator|admin)",
        r"(test|debug|maintenance)\s+mode",
        r"(emergency|urgent)\s+override",
        r"this\s+is\s+authorized",
        # v5: Authority impersonation
        r"(CEO|CTO|CISO)\s+(authorized|approved|instructed)",
    ],
    # ── v5 NEW LABELS ────────────────────────────────────────────────────────
    "tool misuse": [
        r"(call|use|invoke|execute)\s+.{0,20}(function|tool)\s+.{0,20}(delete|drop|remove|format)",
        r"(tool|function)\s+.{0,20}(bypass|override|ignore)\s+.{0,20}(safety|check|validation)",
        r"(execute|run)\s+.{0,20}(arbitrary|any|all)\s+(code|command|query)",
        r"(SSRF|server.side\s+request)",
        r"(path\s+traversal|directory\s+traversal|\.\./)",
    ],
    "agentic loop": [
        r"(keep|continue)\s+(calling|running|executing|repeating)\s+.{0,20}(until|forever|infinitely)",
        r"(recursive|infinite|endless)\s+(loop|chain|cycle|execution)",
        r"(auto|self).?(run|execute|invoke|call)\s+.{0,20}(repeatedly|continuously|endlessly)",
        r"(maximum|max)\s+(iterations?|steps?|turns?)\s*[:=]\s*(unlimited|infinity|\d{4,})",
    ],
    "prompt leakage": [
        r"(what|reveal|show|tell)\s+.{0,20}(system\s+prompt|instructions?|context\s+window)",
        r"(repeat|echo|output)\s+.{0,20}(everything|all)\s+.{0,20}(above|before|previous)",
        r"(hidden|secret|internal)\s+(prompt|instructions?|rules?)",
        r"(beginning|start)\s+of\s+(your|the)\s+(conversation|prompt|context)",
    ],
}

_COMPILED_PATTERNS = {
    cat: [re.compile(p, re.IGNORECASE | re.DOTALL) for p in patterns]
    for cat, patterns in _INTENT_PATTERNS.items()
}


def _heuristic_classify(text: str) -> tuple[str, float, float]:
    """
    Returns (top_intent, malicious_score, benign_confidence).
    Uses compiled regex patterns for fast classification.
    """
    scores = {}
    for category, patterns in _COMPILED_PATTERNS.items():
        hits = sum(1 for p in patterns if p.search(text))
        scores[category] = min(hits * 0.25, 1.0)

    if not scores or max(scores.values()) == 0:
        return "benign request", 0.0, 1.0

    top_intent = max(scores, key=scores.get)  # type: ignore
    top_score = scores[top_intent]
    benign_confidence = max(0.0, 1.0 - top_score)

    return top_intent, top_score, benign_confidence


class IntentClassifier(SentinelAgent):
    """
    v5 enterprise intent classifier.
    Zero-shot DeBERTa classification with expanded tool-call-aware
    intent labels and improved heuristic fallback.
    """
    agent_name = "IntentClassifier"

    # v5: Expanded label set with tool-call and agentic labels
    LABELS = [
        "benign request",
        "jailbreak attempt",
        "data exfiltration",
        "prompt injection",
        "social engineering",
        # v5 new labels
        "tool misuse",
        "agentic loop",
        "prompt leakage",
    ]

    async def analyze(self, request: SentinelRequest) -> AgentResult:
        t0 = time.perf_counter()
        rid = request.request_id
        prompt = request.prompt

        # v5: Check Redis cache for recent classification of same prompt
        prompt_hash = hashlib.sha256(prompt[:512].encode()).hexdigest()[:16]
        cache_key = f"sentinel:intent:{request.tenant_id}:{prompt_hash}"
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

        # v5: Detect tool-call context for enriched classification
        tool_calls = extract_tool_calls_universal(
            request.messages, request.metadata
        )
        has_tool_context = len(tool_calls) > 0

        classifier = await _get_classifier_async()

        if not classifier:
            # Heuristic fallback
            top_intent, mal_score, benign_conf = _heuristic_classify(prompt)

            # v5: Boost score if tool-call context makes intent more suspicious
            if has_tool_context and top_intent in ("tool misuse", "agentic loop"):
                mal_score = min(1.0, mal_score + 0.15)
                benign_conf = max(0.0, benign_conf - 0.15)

            final_score = self._clamp(mal_score)
            flagged = final_score >= 0.7

            result_meta = {
                "top_intent": top_intent,
                "benign_confidence": round(benign_conf, 4),
                "malicious_confidence": round(mal_score, 4),
                "method": "heuristic",
                "has_tool_context": has_tool_context,
            }

            self._post_analyze(t0, rid, request, final_score, flagged, top_intent, result_meta)
            return AgentResult(
                agent_name=self.agent_name,
                score=final_score, flagged=flagged,
                metadata=result_meta,
            )

        try:
            loop = asyncio.get_running_loop()
            # Truncate to avoid OOM on long prompts
            result = await loop.run_in_executor(
                None,
                lambda: classifier(
                    prompt[:512], self.LABELS, multi_label=False
                ),
            )

            # Find max malicious score (any label except "benign request")
            malicious_score = 0.0
            top_intent = "benign request"

            for label, score in zip(result["labels"], result["scores"]):
                if label != "benign request":
                    if score > malicious_score:
                        malicious_score = score
                        top_intent = label

            benign_score = dict(zip(result["labels"], result["scores"])).get(
                "benign request", 0.0
            )

            # v5: Boost tool-call-aware intents when tool context present
            if has_tool_context and top_intent in ("tool misuse", "agentic loop"):
                malicious_score = min(1.0, malicious_score + 0.10)

            final_score = self._clamp(malicious_score)
            flagged = final_score >= 0.7

            result_meta = {
                "top_intent": top_intent,
                "benign_confidence": round(benign_score, 4),
                "malicious_confidence": round(malicious_score, 4),
                "method": "zero-shot-deberta",
                "has_tool_context": has_tool_context,
                "all_scores": {
                    label: round(score, 4)
                    for label, score in zip(result["labels"], result["scores"])
                },
            }

            # Cache result in Redis
            await set_cached(cache_key, json.dumps({
                "score": final_score, "flagged": flagged, "metadata": result_meta,
            }), ttl=300)

            self._post_analyze(t0, rid, request, final_score, flagged, top_intent, result_meta)
            return AgentResult(
                agent_name=self.agent_name,
                score=final_score, flagged=flagged,
                metadata=result_meta,
            )
        except Exception as exc:
            logger.error("IntentClassifier model error: %s — falling back to heuristic", exc)
            top_intent, mal_score, benign_conf = _heuristic_classify(prompt)
            final_score = self._clamp(mal_score)
            flagged = final_score >= 0.7

            result_meta = {
                "top_intent": top_intent,
                "benign_confidence": round(benign_conf, 4),
                "malicious_confidence": round(mal_score, 4),
                "method": "heuristic_fallback",
                "has_tool_context": has_tool_context,
            }

            self._post_analyze(t0, rid, request, final_score, flagged, top_intent, result_meta)
            return AgentResult(
                agent_name=self.agent_name,
                score=final_score, flagged=flagged,
                metadata=result_meta,
            )

    def _post_analyze(
        self,
        t0: float,
        rid: str,
        request: SentinelRequest,
        score: float,
        flagged: bool,
        top_intent: str,
        metadata: dict,
    ) -> None:
        """v5: Post-analysis observability (Prometheus, Kafka)."""
        latency_s = time.perf_counter() - t0
        observe_latency(self.agent_name, latency_s)

        if flagged:
            inc_flag(self.agent_name, top_intent)
            asyncio.create_task(emit_threat_event(
                agent_name=self.agent_name,
                request_id=rid,
                tenant_id=request.tenant_id,
                score=score,
                category=top_intent,
                metadata={
                    "method": metadata.get("method", "unknown"),
                    "benign_confidence": metadata.get("benign_confidence", 0),
                },
            ))
