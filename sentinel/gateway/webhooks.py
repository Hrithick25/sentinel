"""
SENTINEL — Webhook Dispatcher
================================
Fires webhooks to tenant-configured endpoints on key events:
  - threat.blocked     → a request was blocked
  - threat.rewritten   → a request was sanitized and retried
  - compliance.flag    → a compliance tag was raised
  - audit.export       → periodic audit digest available

All payloads are HMAC-SHA256 signed with the tenant's webhook secret
in the X-Sentinel-Signature header so receivers can verify authenticity.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import time
from typing import Optional

import httpx

logger = logging.getLogger("sentinel.webhooks")

# In-memory registry — in production load from DB
_webhook_registry: dict[str, dict] = {}


def register_webhook(tenant_id: str, url: str, secret: str,
                     events: list[str] | None = None):
    _webhook_registry[tenant_id] = {
        "url": url,
        "secret": secret,
        "events": events or ["threat.blocked", "threat.rewritten", "compliance.flag"],
    }


def _sign_payload(payload: str, secret: str) -> str:
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


async def dispatch_webhook(
    tenant_id: str,
    event_type: str,
    data: dict,
) -> None:
    """
    Fire-and-forget webhook dispatch.
    Retries up to 3 times with exponential backoff.
    """
    config = _webhook_registry.get(tenant_id)
    if not config:
        return

    if event_type not in config.get("events", []):
        return

    payload = json.dumps({
        "event": event_type,
        "timestamp": time.time(),
        "tenant_id": tenant_id,
        "data": data,
    }, default=str)

    signature = _sign_payload(payload, config["secret"])
    headers = {
        "Content-Type": "application/json",
        "X-Sentinel-Signature": f"sha256={signature}",
        "X-Sentinel-Event": event_type,
        "User-Agent": "SENTINEL-Webhook/1.0",
    }

    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(config["url"], content=payload, headers=headers)
                if resp.status_code < 300:
                    logger.info("Webhook delivered: tenant=%s event=%s status=%d",
                                tenant_id, event_type, resp.status_code)
                    return
                logger.warning("Webhook failed: status=%d body=%s", resp.status_code, resp.text[:200])
        except Exception as exc:
            logger.warning("Webhook attempt %d failed: %s", attempt + 1, exc)

        await asyncio.sleep(2 ** attempt)

    logger.error("Webhook exhausted retries: tenant=%s event=%s", tenant_id, event_type)
