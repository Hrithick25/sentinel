---
name: add-new-agent
description: Add a new SentinelAgent subclass to the SENTINEL 7-agent parallel mesh
---

# How to Add a New SENTINEL Agent

Follow this exact pattern every time. The mesh is plug-and-play — adding an agent requires touching exactly **3 files**.

## Step 1 — Create the agent file

Create `sentinel/agents/<snake_case_name>.py`:

```python
"""
SENTINEL Agent N — <AgentName>
<One-sentence description of what it detects>
"""
import asyncio
import logging
from sentinel.agents.base import SentinelAgent
from sentinel.models import AgentResult, SentinelRequest

logger = logging.getLogger("sentinel.agents.<snake_name>")


class <AgentName>(SentinelAgent):
    agent_name = "<AgentName>"   # ← must be unique; used as Redis weight key

    async def analyze(self, request: SentinelRequest) -> AgentResult:
        text = request.last_user_message  # or request.prompt for full context

        # --- YOUR DETECTION LOGIC HERE ---
        score = 0.0     # float in [0.0, 1.0]
        flagged = score >= 0.70   # adjust threshold per agent purpose
        metadata = {}   # include anything useful for the audit trail

        return AgentResult(
            agent_name=self.agent_name,
            score=self._clamp(score),
            flagged=flagged,
            metadata=metadata,
        )
```

### Rules
- `analyze()` MUST be `async`. CPU-bound work goes in `asyncio.to_thread()`.
- `score` is always `float` in `[0.0, 1.0]`. Use `self._clamp()`.
- `metadata` dict goes into the signed audit attestation — include anything an auditor would want.
- P99 latency target: **< 80ms**. Profile with `time.perf_counter()` before registering.
- Lazy-load heavy models with a module-level `_model = None` guard (see `toxicity_screener.py` for the pattern).

---

## Step 2 — Register in the mesh

Edit `sentinel/agents/__init__.py`:

```python
from sentinel.agents.<snake_name> import <AgentName>   # ADD THIS LINE

def build_agent_mesh(faiss_manager=None) -> list[SentinelAgent]:
    return [
        InjectionScout(faiss_manager=faiss_manager),
        PIISentinel(),
        JailbreakGuard(),
        ToxicityScreener(),
        HallucinationProbe(),
        ContextAnchor(),
        ComplianceTagger(),
        <AgentName>(),     # ADD THIS LINE — order doesn't matter (parallel)
    ]
```

---

## Step 3 — Initialise Redis weight

The Bayesian consensus engine loads weights from Redis at `sentinel:weights:{tenant_id}`.
New agents get the default weight `1/N` where N is the total agent count.
You don't need to do anything — `get_agent_weights()` auto-initialises missing agents.

However, if your agent is a **tagger** (no threat score, like ComplianceTagger),
add it to `_STATIC_OVERRIDES` in `sentinel/consensus/bayesian_engine.py`:

```python
_STATIC_OVERRIDES = {
    "ComplianceTagger": 0.01,
    "<AgentName>": 0.01,   # ADD IF TAGGER
}
```

---

## Step 4 — Verify

```bash
# Run the benchmark — P99 should stay under 80ms with new agent
python tests/red_team/run_benchmark.py

# Unit test your agent
pytest tests/ -k "<AgentName>" -v
```

The new agent will automatically appear in the dashboard's AgentBreakdown view.
