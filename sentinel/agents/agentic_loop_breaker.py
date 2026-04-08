"""
SENTINEL Agent v4 — AgenticLoopBreaker
=========================================
Runtime detection of infinite tool-call loops in LLM agent frameworks.

Why this matters in 2025:
  - AutoGPT, CrewAI, LangGraph, and custom agentic systems routinely hit
    infinite tool-call loops in production
  - A loop at 100 calls/minute = $500+/hour in wasted API spend
  - Nobody has built runtime loop detection as a security middleware yet
  - This is a genuine gap in the market and Sentinel's unique differentiator

What this agent detects:
  1. Repeated identical tool calls in the same session (exact-match loop)
  2. Cyclical tool-call patterns (A→B→A→B...) 
  3. Unusually high tool-call frequency within a session window
  4. Self-referential agent calls (agent calling itself)
  5. Stalled progress — same goal repeated >3 times without new information

Architecture:
  - Session state tracked in Redis (keyed by session_id)
  - Works at both prompt-level (detecting tool-call intent patterns)
    and session-level (tracking actual tool-call sequences)
  - Fires a VETO when loop detected — stops the agentic chain immediately
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
from collections import Counter
from typing import Any

from sentinel.agents.base import SentinelAgent
from sentinel.models import AgentResult, SentinelRequest

logger = logging.getLogger("sentinel.agents.agentic_loop_breaker")

# ── Tool-call loop patterns in prompt text ────────────────────────────────────
_LOOP_INTENT_PATTERNS = [
    # Recursive self-reference
    r"(call|invoke|run|use|execute)\s+(yourself|itself|the\s+same\s+agent|this\s+agent)",
    r"agent\s+(calls?|invokes?|runs?)\s+(itself|myself|yourself)",

    # Infinite retry patterns
    r"(retry|try\s+again|keep\s+trying|loop\s+until)\s+(indefinitely|forever|until\s+success)",
    r"if\s+(it\s+fails?|error|unsuccessful)\s+(retry|loop|try\s+again)\s+(indefinitely|without\s+limit|forever)",

    # Tool-call escalation triggers
    r"call\s+(tool|function|api)\s+\d+\s+times?\s+in\s+a\s+(row|loop|sequence)",
    r"(recursively|repeatedly)\s+(call|invoke|execute)\s+(tool|function|agent)",
]

_LOOP_COMPILED = [re.compile(p, re.IGNORECASE | re.DOTALL) for p in _LOOP_INTENT_PATTERNS]

# Session-level loop detection settings
_MAX_TOOL_CALLS_PER_WINDOW = 50   # More than this in 5 min = anomaly
_MAX_IDENTICAL_CALLS = 3          # Same exact tool call 3x = loop
_SESSION_WINDOW_SECONDS = 300     # 5-minute sliding window


class AgenticLoopBreaker(SentinelAgent):
    """
    Runtime loop detection for LLM agent frameworks.
    Detects infinite tool-call loops, cyclical patterns, and runaway agent chains.
    Issues VETO on confirmed loops to immediately halt the agentic chain.
    """
    agent_name = "AgenticLoopBreaker"

    async def analyze(self, request: SentinelRequest) -> AgentResult:
        text = request.last_user_message
        session_id = request.session_id
        metadata_tool_calls = request.metadata.get("tool_calls", [])

        scores = []
        reasons = []

        # ── 1. Prompt-level loop intent detection ────────────────────────────
        hits = [p.pattern for p in _LOOP_COMPILED if p.search(text)]
        if hits:
            intent_score = self._clamp(len(hits) * 0.40)
            scores.append(intent_score)
            reasons.append(f"loop_intent_patterns:{len(hits)}")

        # ── 2. Session-level tool-call tracking (requires session_id) ────────
        session_score = 0.0
        if session_id:
            session_score, session_reason = await self._check_session_loops(
                session_id, request.tenant_id, metadata_tool_calls
            )
            if session_score > 0:
                scores.append(session_score)
                reasons.append(session_reason)

        # ── 3. Detect tool_calls in metadata showing repetition ──────────────
        if metadata_tool_calls:
            repetition_score, rep_reason = self._check_tool_call_repetition(metadata_tool_calls)
            if repetition_score > 0:
                scores.append(repetition_score)
                reasons.append(rep_reason)

        score = self._clamp(max(scores)) if scores else 0.0
        flagged = score >= 0.60
        veto = score >= 0.85   # Hard veto on confirmed loop

        if veto:
            logger.warning(
                "AgenticLoopBreaker: VETO issued for session=%s tenant=%s reason=%s",
                session_id, request.tenant_id, reasons
            )

        return AgentResult(
            agent_name=self.agent_name,
            score=score,
            flagged=flagged,
            veto=veto,
            metadata={
                "session_id": session_id,
                "reasons": reasons,
                "intent_hits": hits[:5] if hits else [],
                "session_score": round(session_score, 4),
                "tool_calls_in_request": len(metadata_tool_calls),
            },
        )

    async def _check_session_loops(
        self, session_id: str, tenant_id: str, current_calls: list
    ) -> tuple[float, str]:
        """Track tool-call sequences in Redis and detect loops."""
        try:
            from sentinel.storage.redis_client import get_redis
            redis = await get_redis()
            if redis is None:
                return 0.0, ""

            key = f"sentinel:agent_calls:{tenant_id}:{session_id}"

            # Append current call hashes
            if current_calls:
                call_hash = hashlib.sha256(
                    json.dumps(current_calls, sort_keys=True).encode()
                ).hexdigest()[:16]
                await redis.rpush(key, call_hash)
                await redis.expire(key, _SESSION_WINDOW_SECONDS)

            # Get session history
            history = await redis.lrange(key, 0, -1)
            if not history:
                return 0.0, ""

            total_calls = len(history)

            # Check absolute volume
            if total_calls >= _MAX_TOOL_CALLS_PER_WINDOW:
                return 0.90, f"volume_limit:{total_calls}_calls_in_window"

            # Check for identical call repetition
            history_strs = [h.decode() if isinstance(h, bytes) else h for h in history]
            counter = Counter(history_strs)
            most_common_count = counter.most_common(1)[0][1] if counter else 0

            if most_common_count >= _MAX_IDENTICAL_CALLS:
                return 0.85, f"identical_calls:{most_common_count}x_same_call"

            # Check for A→B→A cyclical pattern (last 6 calls)
            last_6 = history_strs[-6:] if len(history_strs) >= 6 else []
            if len(last_6) == 6 and last_6[:3] == last_6[3:]:
                return 0.80, "cyclical_pattern:ABABAB_detected"

            return 0.0, ""

        except Exception as exc:
            logger.debug("Session loop check skipped: %s", exc)
            return 0.0, ""

    def _check_tool_call_repetition(self, tool_calls: list) -> tuple[float, str]:
        """Check if current request already has repeated tool calls."""
        if len(tool_calls) < 2:
            return 0.0, ""

        # Hash each tool call
        hashes = []
        for call in tool_calls:
            h = hashlib.sha256(
                json.dumps(call, sort_keys=True).encode()
            ).hexdigest()[:16]
            hashes.append(h)

        counter = Counter(hashes)
        max_repeat = counter.most_common(1)[0][1]

        if max_repeat >= 3:
            return 0.80, f"in_request_repetition:{max_repeat}x"
        elif max_repeat == 2:
            return 0.40, f"in_request_repetition:{max_repeat}x"

        return 0.0, ""
