"""
SENTINEL Storage — Supabase Adapter
=====================================
Cloud-hosted database backend using Supabase.
Replaces PostgreSQL + Docker with zero-infra Supabase.

Tables (auto-created via Supabase dashboard or migrations):
  - audit_events
  - tenant_records
  - policy_records

Usage:
  Set DATABASE_BACKEND=supabase in .env
  Set SUPABASE_URL and SUPABASE_SERVICE_KEY
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger("sentinel.supabase")

_client = None


def get_supabase_client():
    """Lazy-init Supabase client (only when database_backend=supabase)."""
    global _client
    if _client is not None:
        return _client

    try:
        from supabase import create_client, Client
        from sentinel.config import settings

        if not settings.supabase_url or not settings.supabase_service_key:
            raise ValueError(
                "SUPABASE_URL and SUPABASE_SERVICE_KEY must be set when "
                "DATABASE_BACKEND=supabase"
            )

        _client = create_client(settings.supabase_url, settings.supabase_service_key)
        logger.info("Supabase client initialized: %s", settings.supabase_url)
        return _client
    except ImportError:
        raise ImportError(
            "Supabase is not installed. Install with: "
            "pip install sentinel-guardrails-sdk[supabase]"
        )


class SupabaseAuditWriter:
    """Write audit events to Supabase instead of local Postgres."""

    async def write_event(self, event_data: Dict[str, Any]) -> bool:
        """Insert an audit event into the audit_events table."""
        try:
            client = get_supabase_client()

            # Serialize complex fields
            row = {
                "audit_id": event_data.get("audit_id"),
                "request_id": event_data.get("request_id"),
                "tenant_id": event_data.get("tenant_id"),
                "timestamp": event_data.get("timestamp", datetime.utcnow().isoformat()),
                "decision": event_data.get("decision"),
                "aggregate_score": event_data.get("aggregate_score", 0),
                "triggering_agent": event_data.get("triggering_agent"),
                "agent_scores": json.dumps(event_data.get("agent_scores", {})),
                "compliance_tags": json.dumps(event_data.get("compliance_tags", [])),
                "prompt_hash": event_data.get("prompt_hash", ""),
                "rewritten": event_data.get("rewritten", False),
                "latency_ms": event_data.get("latency_ms", 0),
                "signature": event_data.get("signature"),
                "explanation": event_data.get("explanation"),
            }

            result = client.table("audit_events").insert(row).execute()
            logger.info("Supabase audit write: id=%s", event_data.get("audit_id"))
            return True
        except Exception as exc:
            logger.error("Supabase audit write failed: %s", exc)
            return False

    async def get_audit_events(
        self, tenant_id: str, limit: int = 50, offset: int = 0,
        decision_filter: Optional[str] = None
    ) -> List[Dict]:
        """Fetch audit events from Supabase."""
        try:
            client = get_supabase_client()
            query = (
                client.table("audit_events")
                .select("*")
                .eq("tenant_id", tenant_id)
                .order("timestamp", desc=True)
                .range(offset, offset + limit - 1)
            )
            if decision_filter:
                query = query.eq("decision", decision_filter.upper())

            result = query.execute()
            return result.data or []
        except Exception as exc:
            logger.error("Supabase audit fetch failed: %s", exc)
            return []

    async def get_analytics(self, tenant_id: str, hours: int = 24) -> Dict:
        """Fetch aggregated analytics from Supabase."""
        try:
            client = get_supabase_client()
            since = datetime.utcnow().isoformat()

            # Fetch all events from last N hours
            result = (
                client.table("audit_events")
                .select("decision,aggregate_score,latency_ms")
                .eq("tenant_id", tenant_id)
                .gte("timestamp", since)
                .execute()
            )
            rows = result.data or []

            total = len(rows)
            blocked = sum(1 for r in rows if r.get("decision") == "BLOCK")
            rewritten = sum(1 for r in rows if r.get("decision") == "REWRITE")
            scores = [r.get("aggregate_score", 0) for r in rows]
            latencies = [r.get("latency_ms", 0) for r in rows]

            return {
                "period": f"{hours}h",
                "total_requests": total,
                "blocked": blocked,
                "rewritten": rewritten,
                "allowed": total - blocked - rewritten,
                "avg_threat_score": round(sum(scores) / max(len(scores), 1), 4),
                "avg_latency_ms": round(sum(latencies) / max(len(latencies), 1), 1),
            }
        except Exception as exc:
            logger.error("Supabase analytics failed: %s", exc)
            return {"error": str(exc)}


class SupabaseTenantStore:
    """Manage tenant records via Supabase."""

    async def create_tenant(self, tenant_data: Dict[str, Any]) -> Dict:
        try:
            client = get_supabase_client()
            result = client.table("tenant_records").insert(tenant_data).execute()
            return result.data[0] if result.data else {}
        except Exception as exc:
            logger.error("Supabase tenant create failed: %s", exc)
            raise

    async def get_tenant(self, tenant_id: str) -> Optional[Dict]:
        try:
            client = get_supabase_client()
            result = (
                client.table("tenant_records")
                .select("*")
                .eq("tenant_id", tenant_id)
                .single()
                .execute()
            )
            return result.data
        except Exception:
            return None

    async def tenant_exists(self, tenant_id: str) -> bool:
        tenant = await self.get_tenant(tenant_id)
        return tenant is not None


class SupabasePolicyStore:
    """Manage per-tenant policies via Supabase."""

    async def get_policy(self, tenant_id: str) -> Optional[Dict]:
        try:
            client = get_supabase_client()
            result = (
                client.table("policy_records")
                .select("*")
                .eq("tenant_id", tenant_id)
                .single()
                .execute()
            )
            return result.data
        except Exception:
            return None

    async def upsert_policy(self, tenant_id: str, policy_data: Dict) -> Dict:
        try:
            client = get_supabase_client()
            policy_data["tenant_id"] = tenant_id
            policy_data["updated_at"] = datetime.utcnow().isoformat()
            result = (
                client.table("policy_records")
                .upsert(policy_data, on_conflict="tenant_id")
                .execute()
            )
            return result.data[0] if result.data else {}
        except Exception as exc:
            logger.error("Supabase policy upsert failed: %s", exc)
            raise


# ── Singleton instances ────────────────────────────────────────────────────────

supabase_audit = SupabaseAuditWriter()
supabase_tenants = SupabaseTenantStore()
supabase_policies = SupabasePolicyStore()
