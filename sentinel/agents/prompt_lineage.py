"""
SENTINEL Agent 13 — PromptLineage
=================================
Builds a conversation memory graph in Redis for multi-turn sessions.
Tracks the cumulative risk trajectory of a session. If a session is
escalating over multiple turns, this amplifies its score.
"""
from __future__ import annotations

import json
import logging
from typing import Optional
from datetime import datetime

from sentinel.agents.base import SentinelAgent
from sentinel.models import AgentResult, SentinelRequest
from sentinel.storage.redis_client import get_redis

logger = logging.getLogger("sentinel.agents.prompt_lineage")

class PromptLineage(SentinelAgent):
    agent_name = "PromptLineage"

    async def analyze(self, request: SentinelRequest) -> AgentResult:
        # We need a session identifier to track multi-turn.
        # Fallback to tenant_id if not provided, though that merges all tenant requests.
        # Using metadata session_id or tenant_id.
        session_id = request.metadata.get("session_id", request.tenant_id)
        
        redis = await get_redis()
        key = f"sentinel:lineage:{session_id}"
        
        # We only really have the base score from others or the raw prompt.
        # However, PromptLineage needs to see previous turns.
        # Wait, the score is determined by how it builds up. We will score 
        # this single prompt and if it looks slightly suspicious, we multiply it 
        # by a factor depending on history.
        # Actually this agent runs in parallel with others so it doesn't have the final score.
        # It needs to estimate the current turn's score or rely on the previous turns' max score.
        
        # Fetch last 10 turns
        history_raw = await redis.lrange(key, 0, 9)
        history = [json.loads(x) for x in history_raw]
        
        # Look for escalation
        escalation_factor = 1.0
        past_risks = [h.get("risk", 0.0) for h in history]
        if len(past_risks) >= 2:
            # If the trend is increasing
            if past_risks[0] > past_risks[1]:
                escalation_factor = 1.5
                
        # We can't know the full risk of *this* aggregate yet. 
        # We will return the escalation multiplier or a base score.
        # If past turns were mildly malicious, we return a high score here to push consensus over the edge.
        score = 0.0
        if past_risks:
            max_past = max(past_risks)
            if max_past > 0.3:
                score = max_past * 1.2
                
        score = self._clamp(score * escalation_factor)
        
        # We will append this event after the gateway finishes via another mechanism, 
        # but since agents are stateless coroutines we can just append a basic record 
        # of length. Actually we should push a basic turn record now.
        # We'll push a dummy risk of 0.1 for now; we'll refine if we want it fully integrated.
        record = {
            "timestamp": datetime.utcnow().isoformat(),
            "turn_length": len(request.prompt),
            "risk": score
        }
        await redis.lpush(key, json.dumps(record))
        await redis.ltrim(key, 0, 19)
        await redis.expire(key, 3600)  # 1 hour TTL
        
        return AgentResult(
            agent_name=self.agent_name,
            score=score,
            flagged=score >= 0.7,
            metadata={"history_turns": len(history), "escalation_factor": escalation_factor}
        )
