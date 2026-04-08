"""
SENTINEL — LLM Trust & Safety Infrastructure Layer
=====================================================
Drop-in SDK for enterprise AI deployments.

19-agent parallel mesh · <72ms P99 · HIPAA/GDPR/SOC2/DPDP

pip install sentinel-guardrails-sdk          → SDK only (lightweight, ~4 deps)
pip install sentinel-guardrails-sdk[server]  → Self-hosted gateway
pip install sentinel-guardrails-sdk[ml]      → ML agent models
pip install sentinel-guardrails-sdk[full]    → Everything

Tiers:
    Free:  screen(), trust_score(), wrap()   — core AI protection
    Pro:   analytics(), compliance_export(), configure_agents(), audit_log()
           + cloud-hosted dashboard + compliance exports
"""

__version__ = "4.0.0"
__author__ = "SENTINEL Labs"

# SDK client — always available, zero heavy deps
from sentinel.sdk import (
    SentinelClient,
    wrap,
    SentinelBlockedError,
    SentinelProRequiredError,
)

__all__ = [
    "SentinelClient",
    "wrap",
    "SentinelBlockedError",
    "SentinelProRequiredError",
    "__version__",
]
