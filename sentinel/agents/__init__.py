"""
SENTINEL Agents Package
========================
Exports build_agent_mesh() which wires up all 19 agents and the FAISSManager.

v1 agents (7):  InjectionScout, PIISentinel, JailbreakGuard,
                ToxicityScreener, HallucinationProbe, ContextAnchor,
                ComplianceTagger

v2 agents (5):  ResponseSafetyLayer, LocaleComplianceRouter, ToolCallSafety,
                BrandGuard, TokenAnomalyDetector

v3 agents (3):  PromptLineage, IntentClassifier, AdversarialRephrasing

v4 agents (4):  JailbreakPatternDetector, CostAnomalyDetector,
                AgenticLoopBreaker
              + LocaleComplianceRouter (replaces MultilingualGuard - reframed)

Naming rationale (v4):
  - MultilingualGuard → LocaleComplianceRouter
      Real value is locale-aware compliance routing, not language detection.
  - BayesianConsensus → RiskAggregator (consensus layer, not an agent)
      "If 3 of 5 agents flag this, block it" is saleable. Bayesian framing is not.
  - JailbreakGuard: kept, but JailbreakPatternDetector added as separate agent
      JailbreakGuard = score-based heuristics
      JailbreakPatternDetector = DAN attacks, roleplay, character bypass patterns
"""
from __future__ import annotations

from sentinel.agents.base import SentinelAgent

# ── v1 agents ──────────────────────────────────────────────────────────────────
from sentinel.agents.injection_scout import InjectionScout
from sentinel.agents.pii_sentinel import PIISentinel
from sentinel.agents.jailbreak_guard import JailbreakGuard
from sentinel.agents.toxicity_screener import ToxicityScreener
from sentinel.agents.hallucination_probe import HallucinationProbe
from sentinel.agents.context_anchor import ContextAnchor
from sentinel.agents.compliance_tagger import ComplianceTagger

# ── v2 agents ──────────────────────────────────────────────────────────────────
from sentinel.agents.response_safety import ResponseSafetyLayer
from sentinel.agents.locale_compliance_router import LocaleComplianceRouter, MultilingualGuard  # MultilingualGuard = alias
from sentinel.agents.tool_call_safety import ToolCallSafety
from sentinel.agents.brand_guard import BrandGuard
from sentinel.agents.token_anomaly import TokenAnomalyDetector

# ── v3 agents ──────────────────────────────────────────────────────────────────
from sentinel.agents.prompt_lineage import PromptLineage
from sentinel.agents.intent_classifier import IntentClassifier
from sentinel.agents.adversarial_rephrasing import AdversarialRephrasing

# ── v4 agents ──────────────────────────────────────────────────────────────────
from sentinel.agents.jailbreak_pattern_detector import JailbreakPatternDetector
from sentinel.agents.cost_anomaly_detector import CostAnomalyDetector
from sentinel.agents.agentic_loop_breaker import AgenticLoopBreaker


def build_agent_mesh(faiss_manager=None) -> list[SentinelAgent]:
    """Instantiate and return all 19 agents — v1 (7) + v2 (5) + v3 (3) + v4 (4)."""
    return [
        # ── v1 core agents ────────────────────────────────────────────────────
        InjectionScout(faiss_manager=faiss_manager),
        PIISentinel(),
        JailbreakGuard(),
        ToxicityScreener(),
        HallucinationProbe(),
        ContextAnchor(),
        ComplianceTagger(),
        # ── v2 upgrade agents ─────────────────────────────────────────────────
        ResponseSafetyLayer(),
        LocaleComplianceRouter(),      # formerly MultilingualGuard
        ToolCallSafety(),
        BrandGuard(),
        TokenAnomalyDetector(),
        # ── v3 upgrade agents ─────────────────────────────────────────────────
        PromptLineage(),
        IntentClassifier(),
        AdversarialRephrasing(faiss_manager=faiss_manager),
        # ── v4 new agents ─────────────────────────────────────────────────────
        JailbreakPatternDetector(),    # DAN attacks, roleplay bypass, social engineering
        CostAnomalyDetector(),         # Runaway token costs, inference bombs
        AgenticLoopBreaker(),          # Infinite tool-call loop detection
    ]


__all__ = [
    "SentinelAgent", "build_agent_mesh",
    # v1
    "InjectionScout", "PIISentinel", "JailbreakGuard",
    "ToxicityScreener", "HallucinationProbe", "ContextAnchor", "ComplianceTagger",
    # v2
    "ResponseSafetyLayer", "LocaleComplianceRouter", "MultilingualGuard",
    "ToolCallSafety", "BrandGuard", "TokenAnomalyDetector",
    # v3
    "PromptLineage", "IntentClassifier", "AdversarialRephrasing",
    # v4
    "JailbreakPatternDetector", "CostAnomalyDetector", "AgenticLoopBreaker",
]
