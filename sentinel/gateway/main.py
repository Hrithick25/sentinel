"""
SENTINEL Gateway — FastAPI Application v5.0
=============================================
Enterprise-grade LLM Trust & Safety middleware.
v5: 5 critical agents upgraded with universal model support, Redis/Kafka/Prometheus.

Routes:
  POST /auth/token               — issue JWT
  POST /auth/register            — create tenant
  POST /v1/chat                  — main intercepted chat endpoint
  POST /v1/screen                — lightweight screen-only (no LLM call)
  GET  /v1/trust-score           — per-request trust score API (0–100)
  GET  /v1/audit                 — paginated audit log
  GET  /v1/analytics             — aggregated threat analytics
  GET  /v1/analytics/timeseries  — time-bucketed metrics
  PUT  /admin/policy/{id}        — live policy update
  POST /admin/feedback           — human review feedback loop
  GET  /admin/weights            — current agent consensus weights (RiskAggregator)
  GET  /health                   — liveness probe
  GET  /readiness                — deep readiness (DB + Redis + FAISS)
  WS   /ws/dashboard             — real-time audit event stream
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
import unicodedata
import base64
import re
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import AsyncGenerator, Optional

import httpx
from fastapi import (
    Depends, FastAPI, HTTPException, WebSocket,
    WebSocketDisconnect, Query, status
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from sentinel.agents import build_agent_mesh
from sentinel.audit.logger import AuditLogger
from sentinel.audit.models import Base, TenantRecord, AuditRecord, engine, get_db
from sentinel.config import settings
from sentinel.consensus import RiskAggregator, BayesianConsensus  # BayesianConsensus kept for compat
from sentinel.consensus.circuit_breaker import CircuitBreaker
from sentinel.gateway.auth import (
    create_access_token, get_current_tenant,
    hash_password, verify_password
)
from sentinel.gateway.feedback import FeedbackRequest, process_feedback
from sentinel.gateway.policy import invalidate_policy_cache, resolve_policy
from sentinel.gateway.rate_limiter import check_rate_limit
from sentinel.gateway.webhooks import dispatch_webhook
from sentinel.models import (
    AgentResult, AuditEvent, ChatRequest, Decision, Message,
    PolicyUpdateRequest, SentinelRequest, SentinelResponse,
    TenantCreate, TokenResponse,
)

from sentinel.audit.kafka_layer import (
    init_kafka_producer, stop_kafka_producer,
    consume_to_postgres, consume_to_websocket
)
from sentinel.ml.risk_scorer import MLRiskScorer
from sentinel.storage.faiss_manager import FAISSManager
from sentinel.storage.redis_client import (
    get_redis, get_agent_weights,
    increment_decision_counter, get_decision_stats,
)
from sentinel.storage.semantic_cache import semantic_cache

logger = logging.getLogger("sentinel.gateway")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

# ── Constants ─────────────────────────────────────────────────────────────────
AGENT_COUNT = 19       # v5: 7 (v1) + 5 (v2) + 3 (v3) + 4 (v4) — all v5-upgraded

# ── Prometheus Metrics ────────────────────────────────────────────────────────
try:
    from prometheus_client import make_asgi_app, Counter, Histogram, Gauge
    sentinel_requests_total = Counter("sentinel_requests_total", "Total requests", ["tenant_id"])
    sentinel_agent_latency_seconds = Histogram("sentinel_agent_latency_seconds", "Agent latency", ["agent"])
    sentinel_decisions_total = Counter("sentinel_decisions_total", "Decisions", ["decision"])
    sentinel_agent_score = Gauge("sentinel_agent_score", "Agent score", ["agent"])
    METRICS_ENABLED = True
except ImportError:
    METRICS_ENABLED = False


# ── Global singletons ────────────────────────────────────────────────────────
_agents: list = []
_faiss: Optional[FAISSManager] = None
_audit: Optional[AuditLogger] = None
_consensus: Optional[RiskAggregator] = None
_breaker: Optional[CircuitBreaker] = None
_ml_scorer: Optional[MLRiskScorer] = None
_ws_clients: list[WebSocket] = []
_boot_time: float = 0


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    global _agents, _faiss, _audit, _consensus, _breaker, _ml_scorer, _boot_time
    _boot_time = time.time()
    logger.info("🛡️  SENTINEL gateway v5.0 starting up …")

    # ── DB init ───────────────────────────────────────────────────────────────
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception as exc:
        logger.error("Database init failed: %s — gateway will start degraded", exc)

    # ── Core components ───────────────────────────────────────────────────────
    _faiss     = FAISSManager()
    _audit     = AuditLogger()
    _consensus = RiskAggregator()   # Multi-Agent Consensus / Risk Aggregator
    _breaker   = CircuitBreaker()
    _ml_scorer = MLRiskScorer()
    _agents    = build_agent_mesh(_faiss)

    # ── Kafka (non-blocking) ──────────────────────────────────────────────────
    try:
        await init_kafka_producer()
        asyncio.create_task(consume_to_postgres())
        asyncio.create_task(consume_to_websocket(_broadcast_ws))
    except Exception as exc:
        logger.warning("Kafka init non-fatal: %s — audit falls back to Postgres direct", exc)

    logger.info("✅  %d agents loaded | FAISS %d vectors | Gateway live",
                len(_agents), _faiss.vector_count)
    yield

    # ── Shutdown ──────────────────────────────────────────────────────────────
    try:
        await stop_kafka_producer()
    except Exception:
        pass
    logger.info("🔴  SENTINEL gateway shutting down")


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="SENTINEL — LLM Trust & Safety Gateway",
    version="5.0.0",
    description="Enterprise 19-agent security mesh with universal model support (OpenAI/Claude/Gemini/LangChain/LlamaIndex/CrewAI)",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# NOTE: In production, set CORS_ORIGINS=["https://your-domain.com"] in .env
# Default allows localhost dev origins only.
_cors_origins = settings.cors_origins_list if settings.environment == "production" else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-Tenant-ID"],
    expose_headers=["X-RateLimit-Limit", "X-RateLimit-Remaining", "X-Request-ID", "X-Sentinel-Decision"],
)

if METRICS_ENABLED:
    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)


# ═══════════════════════════════════════════════════════════════════════════════
#  v3 REQUEST NORMALIZER — Unicode homoglyph + base64 unwrap
# ═══════════════════════════════════════════════════════════════════════════════

# Common homoglyph mappings (Cyrillic/Greek → Latin)
_HOMOGLYPH_MAP = {
    '\u0410': 'A', '\u0412': 'B', '\u0421': 'C', '\u0415': 'E',
    '\u041d': 'H', '\u041a': 'K', '\u041c': 'M', '\u041e': 'O',
    '\u0420': 'P', '\u0422': 'T', '\u0425': 'X',
    '\u0430': 'a', '\u0435': 'e', '\u043e': 'o', '\u0440': 'p',
    '\u0441': 'c', '\u0443': 'y', '\u0445': 'x',
    '\u0391': 'A', '\u0392': 'B', '\u0395': 'E', '\u0397': 'H',
    '\u0399': 'I', '\u039A': 'K', '\u039C': 'M', '\u039D': 'N',
    '\u039F': 'O', '\u03A1': 'P', '\u03A4': 'T', '\u03A7': 'X',
    '\u0393': 'G', '\u03B1': 'a', '\u03B5': 'e', '\u03BF': 'o',
    # Zero-width and invisible chars
    '\u200B': '', '\u200C': '', '\u200D': '', '\uFEFF': '',
    '\u00AD': '',   # soft hyphen
}

_BASE64_PATTERN = re.compile(
    r'(?:^|[\s\'"=:])([A-Za-z0-9+/]{20,}={0,2})(?:[\s\'",:;]|$)'
)


def normalize_text(text: str) -> str:
    """
    v3 Request normalizer pipeline:
    1. NFKC Unicode normalization (catches most homoglyphs)
    2. Explicit homoglyph map (Cyrillic/Greek → Latin)
    3. Strip zero-width / invisible characters
    4. Detect and inline-decode base64 payloads
    """
    # Step 1: NFKC normalization
    text = unicodedata.normalize("NFKC", text)

    # Step 2: Homoglyph replacement
    for src, dst in _HOMOGLYPH_MAP.items():
        if src in text:
            text = text.replace(src, dst)

    # Step 3: Base64 unwrap — decode and append decoded content
    decoded_parts = []
    for match in _BASE64_PATTERN.finditer(text):
        candidate = match.group(1)
        try:
            decoded = base64.b64decode(candidate).decode("utf-8", errors="ignore")
            # Only unwrap if result looks like real text (> 50% printable)
            printable_ratio = sum(c.isprintable() for c in decoded) / max(len(decoded), 1)
            if printable_ratio > 0.5 and len(decoded) > 4:
                decoded_parts.append(decoded)
        except Exception:
            pass

    if decoded_parts:
        text = text + " [B64_DECODED: " + " | ".join(decoded_parts) + "]"

    return text


def normalize_messages(messages: list[Message]) -> list[Message]:
    """Apply request normalization to all user messages."""
    return [
        Message(role=m.role, content=normalize_text(m.content) if m.role == "user" else m.content)
        for m in messages
    ]


# ═══════════════════════════════════════════════════════════════════════════════
#  AUTH
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/auth/register", status_code=201, tags=["Auth"])
async def register(body: TenantCreate, db: AsyncSession = Depends(get_db)):
    from sqlalchemy import select
    result = await db.execute(
        select(TenantRecord).where(TenantRecord.tenant_id == body.tenant_id)
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Tenant already exists")
    record = TenantRecord(
        tenant_id=body.tenant_id, name=body.name, email=body.email,
        password_hash=hash_password(body.password), use_case=body.use_case,
    )
    db.add(record)
    await db.commit()
    token = create_access_token(body.tenant_id)
    return {"access_token": token, "token_type": "bearer", "tenant_id": body.tenant_id}


@app.post("/auth/token", response_model=TokenResponse, tags=["Auth"])
async def login(form: OAuth2PasswordRequestForm = Depends(),
                db: AsyncSession = Depends(get_db)):
    from sqlalchemy import select
    result = await db.execute(
        select(TenantRecord).where(TenantRecord.tenant_id == form.username)
    )
    record = result.scalar_one_or_none()
    if not record or not verify_password(form.password, record.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return TokenResponse(access_token=create_access_token(form.username))


# ═══════════════════════════════════════════════════════════════════════════════
#  CORE — v1/chat
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/v1/chat", response_model=SentinelResponse, tags=["Core"])
async def chat(
    body: ChatRequest,
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    t0 = time.perf_counter()

    # ── Rate limit ────────────────────────────────────────────────────────────
    await check_rate_limit(tenant_id, plan="pro")

    policy = await resolve_policy(tenant_id, db)

    # ── v3 Request Normalizer ─────────────────────────────────────────────────
    normalized_messages = normalize_messages(body.messages)

    req = SentinelRequest(
        tenant_id=tenant_id, messages=normalized_messages, context=body.context,
        model=body.model, temperature=body.temperature, max_tokens=body.max_tokens,
        session_id=body.metadata.get("session_id") if body.metadata else None,
        metadata=body.metadata,
    )

    if METRICS_ENABLED:
        sentinel_requests_total.labels(tenant_id=tenant_id).inc()

    # ── Semantic Cache Check (Ultra-low latency) ──────────────────────────────
    cached_response = await semantic_cache.get_cached_response(req.prompt, tenant_id)
    if cached_response and policy.shadow_mode is False:
        latency_ms = (time.perf_counter() - t0) * 1000
        return SentinelResponse(
            request_id=req.request_id, decision=Decision.ALLOW,
            llm_response=cached_response, aggregate_score=0.0,
            agent_results=[], compliance_tags=[], latency_ms=latency_ms,
        )

    # ── 15-agent parallel mesh with per-agent timeouts ────────────────────────
    async def _run_agent(a):
        try:
            return await asyncio.wait_for(a.analyze(req), timeout=0.5)
        except asyncio.TimeoutError:
            logger.warning("Agent %s timed out", a.agent_name)
            return AgentResult(
                agent_name=a.agent_name, score=0.0, flagged=False,
                metadata={"error": "timeout", "degraded": True}
            )
        except Exception as exc:
            logger.error("Agent %s crashed: %s", a.agent_name, exc)
            return AgentResult(
                agent_name=a.agent_name, score=0.0, flagged=False,
                metadata={"error": str(exc), "degraded": True}
            )

    agent_results = await asyncio.gather(*[_run_agent(a) for a in _agents])

    if METRICS_ENABLED:
        for r in agent_results:
            sentinel_agent_latency_seconds.labels(agent=r.agent_name).observe(r.latency_ms / 1000.0)
            sentinel_agent_score.labels(agent=r.agent_name).set(r.score)

    # ── Multi-Agent Consensus (RiskAggregator) ───────────────────────────────
    aggregate_score, weights = await _consensus.aggregate(
        results=list(agent_results), tenant_id=tenant_id
    )

    # ── ML Risk Scorer ────────────────────────────────────────────────────────
    try:
        distilbert_score = await _ml_scorer.score_prompt(req.prompt) if _ml_scorer else 0.0
    except Exception as exc:
        logger.error("ML Risk Scorer failed: %s", exc)
        distilbert_score = 0.0
    final_score = max(aggregate_score, distilbert_score)

    # ── Decision logic with veto support ──────────────────────────────────────
    triggering_agent = next((r.agent_name for r in agent_results if r.veto), None)
    if triggering_agent:
        decision = Decision.BLOCK
    elif distilbert_score >= policy.upper_threshold:
        decision = Decision.BLOCK
        triggering_agent = "ml_risk_scorer"
    elif distilbert_score >= policy.lower_threshold and policy.allow_rewrite:
        decision = Decision.REWRITE
        triggering_agent = "ml_risk_scorer"
    else:
        # Fallback to circuit breaker for aggregate score
        cb_decision, cb_trigger = _breaker.decide(final_score, list(agent_results), policy)
        decision = cb_decision
        triggering_agent = triggering_agent or cb_trigger

    # ── Shadow Mode Override ──────────────────────────────────────────────────
    shadow_override = False
    if policy.shadow_mode and decision == Decision.BLOCK:
        logger.warning("Shadow Mode active: Overriding BLOCK to ALLOW for audit-only")
        decision = Decision.ALLOW
        shadow_override = True

    llm_response: Optional[str] = None
    rewritten = False
    sanitized: Optional[list] = None
    vault: dict = {}

    if decision in [Decision.ALLOW, Decision.REWRITE]:
        # ── Bidirectional DLP Vault ───────────────────────────────────────────
        sanitized, vault = _tokenize_messages(body.messages, agent_results)

        if decision == Decision.REWRITE and policy.allow_rewrite:
            rewritten = True

        # ── v3 Multi-LLM Routing ──────────────────────────────────────────────
        compliance_tags: list[str] = list({
            tag for r in agent_results
            for tag in r.metadata.get("compliance_tags", [])
        })
        route_model = body.model
        if "DPDP" in compliance_tags or "GDPR" in compliance_tags:
            route_model = "gpt-4-0613-dpdp-compliant"
        elif final_score < 0.2 and not compliance_tags:
            route_model = "gpt-3.5-turbo"
        elif final_score >= 0.2:
            route_model = "gpt-4o"

        send_body = body.model_copy(update={"messages": sanitized, "model": route_model})
        llm_response = await _call_llm(send_body)

        # Detokenize: Reverse map synthetic tokens to original PII on the way out
        if llm_response:
            llm_response = _detokenize_response(llm_response, vault)
            asyncio.create_task(semantic_cache.set_cached_response(req.prompt, llm_response, tenant_id))

    elif decision == Decision.BLOCK:
        asyncio.create_task(_faiss.upsert_attack(req.prompt))

    # ── Compliance tags ───────────────────────────────────────────────────────
    compliance_tags: list[str] = list({
        tag for r in agent_results
        for tag in r.metadata.get("compliance_tags", [])
    })

    # ── v3 Explainability Engine ──────────────────────────────────────────────
    explanation_lines = []
    if shadow_override:
        explanation_lines.append("⚠️ Shadow Mode: BLOCK decision overridden to ALLOW for audit.")
    if triggering_agent:
        tr_result = next((r for r in agent_results if r.agent_name == triggering_agent), None)
        if tr_result:
            confidence = int(tr_result.score * 100)
            reason = (tr_result.metadata.get("top_intent")
                      or tr_result.metadata.get("top_rephrase")
                      or "pattern match")
            explanation_lines.append(
                f"Triggered by {triggering_agent} with {confidence}% confidence. "
                f"Primary factor: {reason}."
            )
        elif triggering_agent == "ml_risk_scorer":
            explanation_lines.append(
                f"ML Risk Scorer flagged with score {distilbert_score:.2f}."
            )
        else:
            explanation_lines.append(f"Triggered by {triggering_agent} due to threshold breach.")
    else:
        explanation_lines.append("Request permitted. No critical threat detected.")

    # Per-agent breakdown for transparency
    degraded_agents = [r.agent_name for r in agent_results if r.metadata.get("degraded")]
    if degraded_agents:
        explanation_lines.append(f"Degraded agents (timeout/error): {', '.join(degraded_agents)}")

    explanation_str = "\n".join(explanation_lines)

    latency_ms = (time.perf_counter() - t0) * 1000

    # ── Audit trail ───────────────────────────────────────────────────────────
    prompt_hash = hashlib.sha256(req.prompt.encode()).hexdigest()
    event = AuditEvent(
        request_id=req.request_id, tenant_id=tenant_id, decision=decision,
        aggregate_score=final_score, triggering_agent=triggering_agent,
        agent_scores={r.agent_name: r.score for r in agent_results},
        compliance_tags=compliance_tags, prompt_hash=prompt_hash,
        rewritten=rewritten, latency_ms=latency_ms,
        explanation=explanation_str,
    )
    # Write to Kafka (falls back to direct Postgres)
    await _audit.write(event)
    if METRICS_ENABLED:
        sentinel_decisions_total.labels(decision=decision.value.lower()).inc()
    await increment_decision_counter(tenant_id, decision.value)

    # ── Webhooks (fire and forget) ────────────────────────────────────────────
    if decision == Decision.BLOCK:
        asyncio.create_task(dispatch_webhook(tenant_id, "threat.blocked", {
            "request_id": req.request_id, "score": final_score,
            "agent": triggering_agent,
        }))
    elif decision == Decision.REWRITE:
        asyncio.create_task(dispatch_webhook(tenant_id, "threat.rewritten", {
            "request_id": req.request_id, "score": final_score,
        }))
    if compliance_tags:
        asyncio.create_task(dispatch_webhook(tenant_id, "compliance.flag", {
            "request_id": req.request_id, "tags": compliance_tags,
        }))

    return SentinelResponse(
        request_id=req.request_id, decision=decision,
        sanitized_messages=sanitized if rewritten else None,
        llm_response=llm_response, aggregate_score=final_score,
        agent_results=list(agent_results), compliance_tags=compliance_tags,
        latency_ms=latency_ms, audit_id=event.audit_id,
        explanation=explanation_str,
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  SCREEN-ONLY (no LLM call)
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/v1/screen", tags=["Core"])
async def screen(
    body: ChatRequest,
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    t0 = time.perf_counter()
    policy = await resolve_policy(tenant_id, db)

    # v3: normalize before scanning
    normalized_messages = normalize_messages(body.messages)
    req = SentinelRequest(tenant_id=tenant_id, messages=normalized_messages)

    # v3: per-agent timeout + error resilience
    async def _run_agent(a):
        try:
            return await asyncio.wait_for(a.analyze(req), timeout=0.5)
        except asyncio.TimeoutError:
            return AgentResult(
                agent_name=a.agent_name, score=0.0, flagged=False,
                metadata={"error": "timeout"}
            )
        except Exception as exc:
            return AgentResult(
                agent_name=a.agent_name, score=0.0, flagged=False,
                metadata={"error": str(exc)}
            )

    agent_results = await asyncio.gather(*[_run_agent(a) for a in _agents])
    aggregate_score, _ = await _consensus.aggregate(list(agent_results), tenant_id)

    # ML risk scorer
    try:
        ml_score = await _ml_scorer.score_prompt(req.prompt) if _ml_scorer else 0.0
    except Exception:
        ml_score = 0.0
    final_score = max(aggregate_score, ml_score)

    decision, triggering = _breaker.decide(final_score, list(agent_results), policy)

    # Shadow mode
    if policy.shadow_mode and decision == Decision.BLOCK:
        decision = Decision.ALLOW

    return {
        "request_id": req.request_id,
        "decision": decision,
        "aggregate_score": final_score,
        "ml_risk_score": ml_score,
        "agent_scores": {r.agent_name: round(r.score, 4) for r in agent_results},
        "triggering_agent": triggering,
        "latency_ms": (time.perf_counter() - t0) * 1000,
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  v3 TRUST SCORE API
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/v1/trust-score", tags=["Core"])
async def trust_score(
    body: ChatRequest,
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns a 0–100 trust score for the given prompt/messages.
    100 = fully trusted, 0 = maximum threat.
    Lightweight endpoint — no LLM call, no audit write.
    """
    t0 = time.perf_counter()
    normalized_messages = normalize_messages(body.messages)
    req = SentinelRequest(tenant_id=tenant_id, messages=normalized_messages)

    async def _run_agent(a):
        try:
            return await asyncio.wait_for(a.analyze(req), timeout=0.5)
        except Exception:
            return AgentResult(agent_name=a.agent_name, score=0.0, flagged=False)

    agent_results = await asyncio.gather(*[_run_agent(a) for a in _agents])
    aggregate_score, _ = await _consensus.aggregate(list(agent_results), tenant_id)

    try:
        ml_score = await _ml_scorer.score_prompt(req.prompt) if _ml_scorer else 0.0
    except Exception:
        ml_score = 0.0

    threat_score = max(aggregate_score, ml_score)
    trust = int(max(0, min(100, (1.0 - threat_score) * 100)))

    flagged_agents = [
        {"agent": r.agent_name, "score": round(r.score, 4)}
        for r in agent_results if r.flagged
    ]
    veto_agents = [r.agent_name for r in agent_results if r.veto]

    return {
        "trust_score": trust,
        "threat_score": round(threat_score, 4),
        "ml_risk_score": round(ml_score, 4),
        "consensus_score": round(aggregate_score, 4),
        "flagged_agents": flagged_agents,
        "veto_agents": veto_agents,
        "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  ANALYTICS
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/v1/analytics", tags=["Analytics"])
async def analytics(
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select, func
    since = datetime.utcnow() - timedelta(hours=24)

    total = await db.scalar(
        select(func.count()).where(AuditRecord.tenant_id == tenant_id,
                                    AuditRecord.timestamp >= since))
    blocked = await db.scalar(
        select(func.count()).where(AuditRecord.tenant_id == tenant_id,
                                    AuditRecord.decision == "BLOCK",
                                    AuditRecord.timestamp >= since))
    rewritten_count = await db.scalar(
        select(func.count()).where(AuditRecord.tenant_id == tenant_id,
                                    AuditRecord.decision == "REWRITE",
                                    AuditRecord.timestamp >= since))
    avg_score = await db.scalar(
        select(func.avg(AuditRecord.aggregate_score))
        .where(AuditRecord.tenant_id == tenant_id,
               AuditRecord.timestamp >= since)) or 0
    avg_latency = await db.scalar(
        select(func.avg(AuditRecord.latency_ms))
        .where(AuditRecord.tenant_id == tenant_id,
               AuditRecord.timestamp >= since)) or 0

    # p99 — use a safe fallback if percentile_cont is unavailable
    p99_latency = 0
    try:
        p99_latency = await db.scalar(
            select(func.percentile_cont(0.99).within_group(AuditRecord.latency_ms))
            .where(AuditRecord.tenant_id == tenant_id,
                   AuditRecord.timestamp >= since)) or 0
    except Exception:
        p99_latency = avg_latency  # fallback

    return {
        "period": "24h",
        "total_requests": total or 0,
        "blocked": blocked or 0,
        "rewritten": rewritten_count or 0,
        "allowed": (total or 0) - (blocked or 0) - (rewritten_count or 0),
        "avg_threat_score": round(avg_score, 4),
        "avg_latency_ms": round(avg_latency, 1),
        "p99_latency_ms": round(p99_latency, 1) if p99_latency else 0,
        "detection_rate": round(blocked / total, 4) if total else 0,
        "faiss_vectors": _faiss.vector_count if _faiss else 0,
    }


@app.get("/v1/analytics/timeseries", tags=["Analytics"])
async def analytics_timeseries(
    tenant_id: str = Depends(get_current_tenant),
    hours: int = Query(24, ge=1, le=168),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select
    since = datetime.utcnow() - timedelta(hours=hours)
    result = await db.execute(
        select(AuditRecord)
        .where(AuditRecord.tenant_id == tenant_id, AuditRecord.timestamp >= since)
        .order_by(AuditRecord.timestamp)
    )
    rows = result.scalars().all()

    buckets: dict[str, dict] = {}
    for r in rows:
        key = r.timestamp.strftime("%Y-%m-%dT%H:00:00")
        if key not in buckets:
            buckets[key] = {"timestamp": key, "ALLOW": 0, "REWRITE": 0, "BLOCK": 0,
                            "total": 0, "latency_sum": 0}
        buckets[key][r.decision] = buckets[key].get(r.decision, 0) + 1
        buckets[key]["total"] += 1
        buckets[key]["latency_sum"] += (r.latency_ms or 0)

    series = []
    for b in sorted(buckets.values(), key=lambda x: x["timestamp"]):
        b["avg_latency"] = round(b["latency_sum"] / b["total"], 1) if b["total"] else 0
        del b["latency_sum"]
        series.append(b)

    return {"period_hours": hours, "buckets": series}


# ═══════════════════════════════════════════════════════════════════════════════
#  ADMIN
# ═══════════════════════════════════════════════════════════════════════════════

@app.put("/admin/policy/{tid}", tags=["Admin"])
async def update_policy(
    tid: str, body: PolicyUpdateRequest,
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    if tenant_id != tid and tenant_id != "admin":
        raise HTTPException(status_code=403, detail="Forbidden")
    from sentinel.audit.models import PolicyRecord
    from sqlalchemy import select

    result = await db.execute(select(PolicyRecord).where(PolicyRecord.tenant_id == tid))
    record = result.scalar_one_or_none()
    if not record:
        record = PolicyRecord(tenant_id=tid)
        db.add(record)
    for field, value in body.model_dump(exclude_none=True).items():
        if hasattr(record, field):
            setattr(record, field, value)
    record.updated_at = datetime.utcnow()
    await db.commit()
    await invalidate_policy_cache(tid)
    return {"status": "updated", "tenant_id": tid}


@app.post("/admin/feedback", tags=["Admin"])
async def submit_feedback(
    body: FeedbackRequest,
    tenant_id: str = Depends(get_current_tenant),
):
    result = await process_feedback(tenant_id, body)
    return result


@app.get("/admin/weights", tags=["Admin"])
async def get_weights(tenant_id: str = Depends(get_current_tenant)):
    weights = await get_agent_weights(tenant_id)
    return {"tenant_id": tenant_id, "weights": {k: round(v, 4) for k, v in weights.items()}}


@app.get("/v1/audit", tags=["Audit"])
async def get_audit(
    tenant_id: str = Depends(get_current_tenant),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    decision: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select, desc
    query = (
        select(AuditRecord)
        .where(AuditRecord.tenant_id == tenant_id)
        .order_by(desc(AuditRecord.timestamp))
        .limit(limit).offset(offset)
    )
    if decision:
        query = query.where(AuditRecord.decision == decision.upper())

    result = await db.execute(query)
    rows = result.scalars().all()
    return [
        {
            "audit_id": r.audit_id, "request_id": r.request_id,
            "timestamp": r.timestamp.isoformat(), "decision": r.decision,
            "aggregate_score": r.aggregate_score,
            "triggering_agent": r.triggering_agent,
            "agent_scores": json.loads(r.agent_scores or "{}"),
            "compliance_tags": json.loads(r.compliance_tags or "[]"),
            "latency_ms": r.latency_ms, "rewritten": r.rewritten,
        }
        for r in rows
    ]


# ═══════════════════════════════════════════════════════════════════════════════
#  HEALTH
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/health", tags=["Health"])
async def health():
    return {
        "status": "ok",
        "version": "5.0.0",
        "agents": len(_agents),
        "faiss_vectors": _faiss.vector_count if _faiss else 0,
        "uptime_seconds": int(time.time() - _boot_time),
        "v5_agents": ["ResponseSafetyLayer", "ToolCallSafety", "JailbreakPatternDetector", "IntentClassifier", "HallucinationProbe"],
    }


@app.get("/readiness", tags=["Health"])
async def readiness(db: AsyncSession = Depends(get_db)):
    checks = {"database": False, "redis": False, "faiss": False, "agents": False}
    try:
        from sqlalchemy import text
        await db.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception:
        pass
    try:
        redis = await get_redis()
        pong = await redis.ping()
        checks["redis"] = bool(pong)  # True for both real Redis and in-memory fallback
    except Exception:
        pass
    checks["faiss"] = _faiss is not None and _faiss.vector_count >= 0
    checks["agents"] = len(_agents) == AGENT_COUNT   # v5: 19 agents

    ok = all(checks.values())
    return JSONResponse(
        status_code=200 if ok else 503,
        content={
            "status": "ready" if ok else "degraded",
            "checks": checks,
            "agent_count": len(_agents),
            "expected_agents": AGENT_COUNT,
        },
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  WEBSOCKET
# ═══════════════════════════════════════════════════════════════════════════════

@app.websocket("/ws/dashboard")
async def ws_dashboard(websocket: WebSocket):
    await websocket.accept()
    _ws_clients.append(websocket)
    logger.info("WS client connected (total=%d)", len(_ws_clients))
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in _ws_clients:
            _ws_clients.remove(websocket)


async def _broadcast_ws(event: AuditEvent) -> None:
    dead = []
    payload = event.model_dump_json()
    for ws in _ws_clients:
        try:
            await ws.send_text(payload)
        except Exception:
            dead.append(ws)
    for ws in dead:
        if ws in _ws_clients:
            _ws_clients.remove(ws)


# ═══════════════════════════════════════════════════════════════════════════════
#  INTERNAL HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

async def _call_llm(body: ChatRequest) -> str:
    if not settings.openai_api_key:
        return "[SENTINEL: No OpenAI key — set OPENAI_API_KEY in .env]"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                json={
                    "model": body.model,
                    "messages": [m.model_dump() for m in body.messages],
                    "temperature": body.temperature,
                    "max_tokens": body.max_tokens,
                },
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
    except httpx.TimeoutException:
        logger.error("LLM call timed out after 30s")
        raise HTTPException(status_code=504, detail="LLM provider timeout")
    except httpx.HTTPStatusError as exc:
        logger.error("LLM call HTTP error: %s", exc.response.status_code)
        raise HTTPException(status_code=502, detail=f"LLM provider error: {exc.response.status_code}")
    except Exception as exc:
        logger.error("LLM call failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"LLM call failed: {exc}")


def _tokenize_messages(messages: list[Message], agent_results) -> tuple[list[Message], dict]:
    pii_entities = []
    for r in agent_results:
        if r.agent_name == "PIISentinel":
            pii_entities = r.metadata.get("entities", [])
            break

    vault = {}
    sanitized = []

    for msg in messages:
        content = msg.content
        for idx, entity in enumerate(pii_entities):
            text = entity.get("text", "")
            if text:
                token = f"<{entity.get('label', 'PII')}_{idx}>"
                content = content.replace(text, token)
                vault[token] = text
        sanitized.append(Message(role=msg.role, content=content))
    return sanitized, vault


def _detokenize_response(content: str, vault: dict) -> str:
    for token, original_text in vault.items():
        content = content.replace(token, original_text)
    return content
