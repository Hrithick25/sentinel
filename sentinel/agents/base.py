"""
SENTINEL Base Agent
=====================
Abstract base class every agent must implement.
All agents are stateless coroutines — they receive a SentinelRequest,
analyse it, and return an AgentResult.  No agent holds conversation state.
"""
from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod

from sentinel.models import AgentResult, SentinelRequest


class SentinelAgent(ABC):
    """
    Contract:
      - agent_name   : unique identifier (used as dict key in Redis weight store)
      - analyze()    : async, must return AgentResult in < 200ms P99
    """

    agent_name: str = "BaseAgent"

    @abstractmethod
    async def analyze(self, request: SentinelRequest) -> AgentResult:
        """
        Analyse the request, return an AgentResult.
        score: float  0.0 (safe) → 1.0 (certain threat)
        flagged: bool convenience alias for score > threshold
        metadata: dict  agent-specific payload (entities, labels, claims, etc.)
        """

    async def _timed_analyze(self, request: SentinelRequest) -> AgentResult:
        """Wrapper that auto-populates latency_ms on the result."""
        t0 = time.perf_counter()
        result = await self.analyze(request)
        result.latency_ms = (time.perf_counter() - t0) * 1000
        return result

    @staticmethod
    def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
        return max(lo, min(hi, value))
