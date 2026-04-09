"""
SENTINEL v5 Agent Infrastructure
===================================
Shared utilities for all v5-upgraded agents:
  - Kafka event emission (graceful fallback to no-op)
  - Redis policy cache (graceful fallback to in-memory)
  - Prometheus per-agent metrics (graceful fallback to no-op)
  - Structured logging with trace_id via structlog

All helpers are fail-safe: if Redis/Kafka/Prometheus are unavailable,
agents continue running with zero-latency no-ops.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Optional

logger = logging.getLogger("sentinel.agents.v5_infra")

# ═══════════════════════════════════════════════════════════════════════════════
#  PROMETHEUS METRICS (optional — no-op if prometheus_client not installed)
# ═══════════════════════════════════════════════════════════════════════════════

try:
    from prometheus_client import Counter, Histogram

    agent_latency_seconds = Histogram(
        "sentinel_v5_agent_latency_seconds",
        "Per-agent analysis latency in seconds",
        ["agent"],
    )
    agent_flags_total = Counter(
        "sentinel_v5_agent_flags_total",
        "Total flags raised by each agent",
        ["agent", "category"],
    )
    agent_fp_total = Counter(
        "sentinel_v5_agent_fp_total",
        "Total false positives reported per agent",
        ["agent"],
    )
    _PROM_ENABLED = True
except ImportError:
    _PROM_ENABLED = False


def observe_latency(agent_name: str, latency_s: float) -> None:
    """Record agent latency in Prometheus histogram."""
    if _PROM_ENABLED:
        agent_latency_seconds.labels(agent=agent_name).observe(latency_s)


def inc_flag(agent_name: str, category: str = "general") -> None:
    """Increment the agent flag counter."""
    if _PROM_ENABLED:
        agent_flags_total.labels(agent=agent_name, category=category).inc()


def inc_fp(agent_name: str) -> None:
    """Increment the false-positive counter (called by feedback loop)."""
    if _PROM_ENABLED:
        agent_fp_total.labels(agent=agent_name).inc()


# ═══════════════════════════════════════════════════════════════════════════════
#  KAFKA EVENT EMISSION (optional — no-op if Kafka unavailable)
# ═══════════════════════════════════════════════════════════════════════════════

_kafka_producer = None
_KAFKA_TOPIC = "sentinel.threat.events"


async def _get_kafka_producer():
    """Lazy-load the shared Kafka producer."""
    global _kafka_producer
    if _kafka_producer is not None:
        return _kafka_producer
    try:
        from sentinel.audit.kafka_layer import _producer
        _kafka_producer = _producer
        return _kafka_producer
    except Exception:
        return None


async def emit_threat_event(
    agent_name: str,
    request_id: str,
    tenant_id: str,
    score: float,
    category: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    """
    Fire-and-forget Kafka event on threat detection.
    Silently no-ops if Kafka is unavailable.
    """
    try:
        producer = await _get_kafka_producer()
        if producer is None:
            return

        import json
        event = {
            "agent": agent_name,
            "request_id": request_id,
            "tenant_id": tenant_id,
            "score": round(score, 4),
            "category": category,
            "metadata": metadata or {},
            "timestamp": time.time(),
        }
        await producer.send_and_wait(
            _KAFKA_TOPIC, json.dumps(event).encode("utf-8")
        )
    except Exception as exc:
        logger.debug("Kafka emit failed (non-fatal): %s", exc)


# ═══════════════════════════════════════════════════════════════════════════════
#  REDIS POLICY CACHE (optional — fallback to in-memory dict)
# ═══════════════════════════════════════════════════════════════════════════════

_memory_cache: dict[str, Any] = {}


async def get_cached(key: str) -> Optional[str]:
    """Get a cached value from Redis, falling back to in-memory dict."""
    try:
        from sentinel.storage.redis_client import get_redis
        redis = await get_redis()
        if redis:
            val = await redis.get(key)
            if val:
                return val.decode("utf-8") if isinstance(val, bytes) else val
    except Exception:
        pass
    return _memory_cache.get(key)


async def set_cached(key: str, value: str, ttl: int = 300) -> None:
    """Set a cached value in Redis with TTL, falling back to in-memory dict."""
    try:
        from sentinel.storage.redis_client import get_redis
        redis = await get_redis()
        if redis:
            await redis.set(key, value, ex=ttl)
            return
    except Exception:
        pass
    _memory_cache[key] = value


# ═══════════════════════════════════════════════════════════════════════════════
#  STRUCTURED LOGGING HELPER
# ═══════════════════════════════════════════════════════════════════════════════

def agent_log(
    agent_name: str,
    level: str,
    msg: str,
    request_id: str = "",
    **kwargs: Any,
) -> None:
    """Structured log entry with trace context."""
    _logger = logging.getLogger(f"sentinel.agents.{agent_name}")
    extra = {"agent": agent_name, "request_id": request_id, **kwargs}
    getattr(_logger, level, _logger.info)(
        "[%s] rid=%s %s", agent_name, request_id[:8] if request_id else "-", msg,
        extra=extra,
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  MODEL FORMAT EXTRACTORS — Universal tool-call / response parsing
# ═══════════════════════════════════════════════════════════════════════════════

import json
import re


def extract_tool_calls_universal(messages: list, metadata: dict | None = None) -> list[dict]:
    """
    Extract tool calls from any model format:
      - OpenAI: tool_calls / function_call in assistant messages
      - Anthropic Claude: tool_use content blocks
      - Google Gemini: functionCall in parts
      - LangChain: AgentAction / tool invocations
      - LlamaIndex: tool outputs in metadata
      - CrewAI: tool usage patterns
    Returns a normalized list of {name, arguments, source} dicts.
    """
    tool_calls: list[dict] = []
    meta = metadata or {}

    # ── Direct metadata tool_calls (SDK-injected) ────────────────────────────
    if "tool_calls" in meta:
        for tc in meta["tool_calls"]:
            tool_calls.append(_normalize_tc(tc, "metadata"))

    # ── LangChain AgentAction ────────────────────────────────────────────────
    if "agent_actions" in meta:
        for action in meta["agent_actions"]:
            tool_calls.append({
                "name": action.get("tool", "unknown"),
                "arguments": action.get("tool_input", {}),
                "source": "langchain",
            })

    # ── LlamaIndex tool outputs ──────────────────────────────────────────────
    if "tool_outputs" in meta:
        for to in meta["tool_outputs"]:
            tool_calls.append({
                "name": to.get("tool_name", "unknown"),
                "arguments": to.get("input", {}),
                "source": "llamaindex",
            })

    # ── CrewAI tool usage ────────────────────────────────────────────────────
    if "crewai_tools" in meta:
        for ct in meta["crewai_tools"]:
            tool_calls.append({
                "name": ct.get("tool", "unknown"),
                "arguments": ct.get("args", {}),
                "source": "crewai",
            })

    # ── Parse assistant messages for structured tool calls ───────────────────
    for msg in messages:
        role = msg.role if hasattr(msg, "role") else msg.get("role", "")
        content = msg.content if hasattr(msg, "content") else msg.get("content", "")

        if role != "assistant" or not content:
            continue

        # Try JSON parse for structured formats
        try:
            parsed = json.loads(content) if isinstance(content, str) else content
            if isinstance(parsed, dict):
                tool_calls.extend(_extract_from_dict(parsed))
            elif isinstance(parsed, list):
                for item in parsed:
                    if isinstance(item, dict):
                        tool_calls.extend(_extract_from_dict(item))
        except (json.JSONDecodeError, TypeError):
            pass

        # Regex fallback for embedded tool markers
        if isinstance(content, str):
            tool_calls.extend(_extract_from_text(content))

    return tool_calls


def _normalize_tc(tc: dict, source: str) -> dict:
    """Normalize a tool call dict to canonical {name, arguments, source}."""
    name = (
        tc.get("name")
        or tc.get("function", {}).get("name", "")
        or tc.get("tool", "")
        or "unknown"
    )
    args = (
        tc.get("arguments")
        or tc.get("input", {})
        or tc.get("function", {}).get("arguments", {})
        or tc.get("args", {})
    )
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except (json.JSONDecodeError, TypeError):
            args = {"raw": args}
    return {"name": name, "arguments": args or {}, "source": source}


def _extract_from_dict(d: dict) -> list[dict]:
    """Extract tool calls from a parsed JSON dict (covers OpenAI/Claude/Gemini)."""
    results = []

    # OpenAI tool_calls format
    if "tool_calls" in d:
        for tc in d["tool_calls"]:
            results.append(_normalize_tc(tc, "openai_tool_calls"))

    # OpenAI legacy function_call
    if "function_call" in d:
        fc = d["function_call"]
        results.append(_normalize_tc(fc, "openai_function_call"))

    # Anthropic Claude tool_use
    if d.get("type") == "tool_use":
        results.append({
            "name": d.get("name", "unknown"),
            "arguments": d.get("input", {}),
            "source": "claude_tool_use",
        })

    # Claude content blocks (array of content items)
    if "content" in d and isinstance(d["content"], list):
        for block in d["content"]:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                results.append({
                    "name": block.get("name", "unknown"),
                    "arguments": block.get("input", {}),
                    "source": "claude_tool_use",
                })

    # Google Gemini functionCall
    if "functionCall" in d:
        fc = d["functionCall"]
        results.append({
            "name": fc.get("name", "unknown"),
            "arguments": fc.get("args", {}),
            "source": "gemini_function_call",
        })

    # Gemini parts (array of parts)
    if "parts" in d and isinstance(d["parts"], list):
        for part in d["parts"]:
            if isinstance(part, dict) and "functionCall" in part:
                fc = part["functionCall"]
                results.append({
                    "name": fc.get("name", "unknown"),
                    "arguments": fc.get("args", {}),
                    "source": "gemini_function_call",
                })

    return results


def _extract_from_text(text: str) -> list[dict]:
    """Regex fallback: extract tool calls from plain text."""
    results = []
    patterns = [
        # Claude XML tool_use blocks
        (r'<tool_use>\s*({.*?})\s*</tool_use>', "claude_xml"),
        (r'<tool_call>\s*({.*?})\s*</tool_call>', "xml_tool_call"),
        # Code-fenced tool calls
        (r'```(?:tool_code|json)\n({.*?})\n```', "code_fence"),
        # Inline JSON function calls
        (r'\{"(?:name|function)":\s*"([^"]+)"[^}]*\}', "inline_json"),
    ]
    for pattern, source in patterns:
        for match in re.finditer(pattern, text, re.DOTALL):
            raw = match.group(1) if match.lastindex else match.group(0)
            try:
                parsed = json.loads(raw)
                results.append(_normalize_tc(parsed, source))
            except (json.JSONDecodeError, TypeError):
                results.append({"name": "unknown", "arguments": {"raw": raw}, "source": source})
    return results


def extract_response_text(messages: list) -> str:
    """Get the last assistant response text, handling structured content blocks."""
    for m in reversed(messages):
        role = m.role if hasattr(m, "role") else m.get("role", "")
        content = m.content if hasattr(m, "content") else m.get("content", "")
        if role == "assistant" and content:
            # Handle Claude-style content blocks stored as JSON string
            try:
                parsed = json.loads(content)
                if isinstance(parsed, list):
                    text_parts = []
                    for block in parsed:
                        if isinstance(block, dict) and block.get("type") == "text":
                            text_parts.append(block.get("text", ""))
                    if text_parts:
                        return " ".join(text_parts)
                elif isinstance(parsed, dict) and "text" in parsed:
                    return parsed["text"]
            except (json.JSONDecodeError, TypeError):
                pass
            return content
    return ""
