"""
Shared Pydantic models — used across SDK, gateway, agents, consensus, and audit layers.

v2.0: Added DPDP (India), RBI, IRDAI, SEBI compliance categories
      for India Go-To-Market strategy.
v3.0: Added 15-agent mesh, veto field, request normalizer, trust score API,
      explainability engine, ML risk scorer (DistilBERT).
"""
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum
import uuid
from datetime import datetime


# ─── Enums ─────────────────────────────────────────────────────────────────────

class Decision(str, Enum):
    ALLOW   = "ALLOW"
    REWRITE = "REWRITE"
    BLOCK   = "BLOCK"


class ComplianceCategory(str, Enum):
    # International
    HIPAA     = "HIPAA"
    GDPR      = "GDPR"
    SOC2      = "SOC2"
    PCI_DSS   = "PCI_DSS"
    CCPA      = "CCPA"
    # India-specific (v2)
    DPDP      = "DPDP"          # Digital Personal Data Protection Act, 2023
    RBI_IT    = "RBI_IT"        # RBI IT Framework for Banks/NBFCs
    IRDAI     = "IRDAI"         # Insurance Regulatory Authority guidelines
    SEBI      = "SEBI"          # Securities Board of India
    CERT_IN   = "CERT_IN"       # CERT-In incident reporting
    NONE      = "NONE"


class PricingTier(str, Enum):
    """Revenue model tiers — v2 India GTM."""
    OSS_CORE    = "oss_core"        # Free · 5 agents · self-hosted
    STARTER_IN  = "starter_india"   # ₹4,999/mo · 7 agents · DPDP + dashboard
    PRO         = "pro"             # $299/mo · 12 agents · full compliance
    ENTERPRISE  = "enterprise"      # Custom · on-prem · SLA + audit export


# ─── Core Request/Response ─────────────────────────────────────────────────────

class Message(BaseModel):
    role: str
    content: str


class SentinelRequest(BaseModel):
    """Canonical request object passed through the entire pipeline."""
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str
    messages: List[Message]
    context: Optional[str] = None       # Source context for RAG / hallucination check
    model: str = "gpt-4o"
    temperature: float = 0.7
    max_tokens: int = 1024
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    session_id: Optional[str] = None    # v3: for conversational memory

    @property
    def prompt(self) -> str:
        """Flatten messages to a single prompt string for agent analysis."""
        return "\n".join(f"[{m.role.upper()}] {m.content}" for m in self.messages)

    @property
    def last_user_message(self) -> str:
        for m in reversed(self.messages):
            if m.role == "user":
                return m.content
        return self.prompt


class SentinelResponse(BaseModel):
    """Full pipeline response returned to the SDK caller."""
    request_id: str
    decision: Decision
    sanitized_messages: Optional[List[Message]] = None   # Set on REWRITE
    llm_response: Optional[str] = None                   # Set on ALLOW/REWRITE
    aggregate_score: float
    agent_results: List[AgentResult]
    compliance_tags: List[str] = Field(default_factory=list)
    latency_ms: float
    audit_id: Optional[str] = None
    explanation: Optional[str] = None    # v3: Human-readable explainability engine


# ─── Agent Result ──────────────────────────────────────────────────────────────

class AgentResult(BaseModel):
    agent_name: str
    score: float = Field(ge=0.0, le=1.0)
    flagged: bool = False
    veto: bool = False                                  # v3: force-block regardless of aggregate
    metadata: Dict[str, Any] = Field(default_factory=dict)
    latency_ms: float = 0.0


# ─── Tenant Policy ─────────────────────────────────────────────────────────────

class TenantPolicy(BaseModel):
    tenant_id: str
    use_case: str = "general"
    pricing_tier: PricingTier = PricingTier.OSS_CORE
    # v1 thresholds
    injection_threshold: float = 0.85
    pii_threshold: float = 0.70
    toxicity_threshold: float = 0.60
    hallucination_threshold: float = 0.50
    jailbreak_threshold: float = 0.75
    # v2 thresholds
    response_safety_threshold: float = 0.50
    multilingual_threshold: float = 0.65
    tool_call_threshold: float = 0.60
    brand_guard_threshold: float = 0.50
    token_anomaly_threshold: float = 0.60
    # Decision boundaries
    lower_threshold: float = 0.35   # Below → ALLOW
    upper_threshold: float = 0.70   # Above → BLOCK (middle → REWRITE)
    pii_action: str = "redact"      # redact | block | log
    allow_rewrite: bool = True
    # India compliance
    compliance_region: str = "global"   # global | india | us | eu
    dpdp_enabled: bool = False
    rbi_framework_enabled: bool = False
    shadow_mode: bool = False           # If true, log violations but never BLOCK
    updated_at: Optional[datetime] = None



# ─── Audit Trail ──────────────────────────────────────────────────────────────

class AuditEvent(BaseModel):
    audit_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    request_id: str
    tenant_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    decision: Decision
    aggregate_score: float
    triggering_agent: Optional[str] = None
    agent_scores: Dict[str, float] = Field(default_factory=dict)
    compliance_tags: List[str] = Field(default_factory=list)
    prompt_hash: str = ""           # SHA256 of original prompt
    rewritten: bool = False
    latency_ms: float = 0.0
    signature: Optional[str] = None  # HMAC attestation
    explanation: Optional[str] = None # v3 explainability


# ─── API Payloads ──────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    """External API payload — mirrors OpenAI chat completion request."""
    tenant_id: str
    messages: List[Message]
    context: Optional[str] = None
    model: str = "gpt-4o"
    temperature: float = 0.7
    max_tokens: int = 1024
    metadata: Dict[str, Any] = Field(default_factory=dict)  # v3: session_id, custom fields


class PolicyUpdateRequest(BaseModel):
    use_case: Optional[str] = None
    pricing_tier: Optional[PricingTier] = None
    # v1 thresholds
    injection_threshold: Optional[float] = None
    pii_threshold: Optional[float] = None
    toxicity_threshold: Optional[float] = None
    hallucination_threshold: Optional[float] = None
    jailbreak_threshold: Optional[float] = None
    # v2 thresholds
    response_safety_threshold: Optional[float] = None
    multilingual_threshold: Optional[float] = None
    tool_call_threshold: Optional[float] = None
    brand_guard_threshold: Optional[float] = None
    token_anomaly_threshold: Optional[float] = None
    # Decision boundaries
    lower_threshold: Optional[float] = None
    upper_threshold: Optional[float] = None
    pii_action: Optional[str] = None
    allow_rewrite: Optional[bool] = None
    # India compliance
    compliance_region: Optional[str] = None
    dpdp_enabled: Optional[bool] = None
    rbi_framework_enabled: Optional[bool] = None
    # v3
    shadow_mode: Optional[bool] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TenantCreate(BaseModel):
    tenant_id: str
    name: str
    email: str
    password: str
    use_case: str = "general"
    pricing_tier: PricingTier = PricingTier.OSS_CORE
    compliance_region: str = "global"
