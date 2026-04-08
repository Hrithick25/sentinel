"""
SENTINEL Audit — Logger
==========================
Writes signed JSON audit attestations.

Supports multiple backends:
  1. Kafka → Postgres (default for Docker self-hosted)
  2. Direct Postgres (fallback when Kafka is unavailable)
  3. Supabase (cloud-hosted, no Docker needed)
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
from datetime import datetime

from sentinel.config import settings
from sentinel.models import AuditEvent

logger = logging.getLogger("sentinel.audit")

class AuditLogger:
    def _sign(self, payload: dict) -> str:
        """HMAC-SHA256 attestation signature."""
        canonical = json.dumps(payload, sort_keys=True, default=str)
        return hmac.new(
            settings.secret_key.encode(),
            canonical.encode(),
            hashlib.sha256,
        ).hexdigest()

    async def write(self, event: AuditEvent) -> None:
        """
        Route audit event to the appropriate backend:
          1. If database_backend=supabase → write to Supabase
          2. If Kafka is available → produce to Kafka topic
          3. Fallback → direct Postgres write
        """
        # ── Supabase backend ──────────────────────────────────────────────────
        if settings.use_supabase:
            await self._write_supabase(event)
            return

        # ── Kafka → Postgres backend ──────────────────────────────────────────
        try:
            from sentinel.audit.kafka_layer import produce_audit_event
            success = await produce_audit_event(event)
            if not success:
                # Fallback to direct DB write
                from sentinel.audit.models import AsyncSessionLocal
                async with AsyncSessionLocal() as db:
                    await self._write_db(event, db)
        except Exception as exc:
            logger.error("Audit direct write fallback: %s. Kafka failed: %s", event.request_id, exc)

    async def _write_supabase(self, event: AuditEvent) -> None:
        """Persist audit event to Supabase."""
        try:
            from sentinel.storage.supabase_adapter import supabase_audit

            payload = self._build_payload(event)
            payload["signature"] = self._sign(payload)
            success = await supabase_audit.write_event(payload)
            if success:
                logger.info("Audit Supabase write: id=%s dec=%s score=%.2f",
                            event.audit_id, event.decision, event.aggregate_score)
        except Exception as exc:
            logger.error("Supabase audit write failed: %s", exc)

    async def _write_db(self, event: AuditEvent, db) -> None:
        """Persist audit event to Postgres with HMAC signature (used by consumer)."""
        from sqlalchemy.ext.asyncio import AsyncSession
        from sentinel.audit.models import AuditRecord

        payload = self._build_payload(event)
        signature = self._sign(payload)

        # Serialize decision enum to string for DB storage
        decision_str = event.decision.value if hasattr(event.decision, 'value') else str(event.decision)

        record = AuditRecord(
            audit_id         = event.audit_id,
            request_id       = event.request_id,
            tenant_id        = event.tenant_id,
            timestamp        = event.timestamp,
            decision         = decision_str,
            aggregate_score  = event.aggregate_score,
            triggering_agent = event.triggering_agent,
            agent_scores     = json.dumps(event.agent_scores),
            compliance_tags  = json.dumps(event.compliance_tags),
            prompt_hash      = event.prompt_hash,
            rewritten        = event.rewritten,
            latency_ms       = event.latency_ms,
            signature        = signature,
            explanation      = event.explanation,
        )
        db.add(record)
        try:
            await db.commit()
            logger.info("Audit DB write: id=%s dec=%s score=%.2f", event.audit_id, event.decision, event.aggregate_score)
        except Exception as exc:
            await db.rollback()
            logger.error("Audit DB write failed: %s", exc)

    def _build_payload(self, event: AuditEvent) -> dict:
        """Build the canonical payload dict for signing/storage."""
        return {
            "audit_id":        event.audit_id,
            "request_id":      event.request_id,
            "tenant_id":       event.tenant_id,
            "timestamp":       event.timestamp.isoformat(),
            "decision":        event.decision.value if hasattr(event.decision, 'value') else str(event.decision),
            "aggregate_score": event.aggregate_score,
            "triggering_agent": event.triggering_agent,
            "agent_scores":    event.agent_scores,
            "compliance_tags": event.compliance_tags,
            "prompt_hash":     event.prompt_hash,
            "rewritten":       event.rewritten,
            "latency_ms":      event.latency_ms,
            "explanation":     event.explanation,
        }
