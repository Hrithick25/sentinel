"""
SENTINEL LangChain Callback Handler
====================================
Drop into any LangChain chain/agent to run SENTINEL safety analysis
on every LLM call without touching chain logic.

Usage:
    from sentinel.sdk.langchain_handler import SentinelCallbackHandler
    handler = SentinelCallbackHandler(tenant_id="acme-hr", api_key="sk-sentinel-...")
    llm = ChatOpenAI(callbacks=[handler])
"""
from __future__ import annotations

import logging
import httpx
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import BaseMessage
from langchain_core.outputs import ChatGeneration, LLMResult

from sentinel.config import settings
from sentinel.models import Decision

logger = logging.getLogger("sentinel.langchain")


class SentinelCallbackHandler(BaseCallbackHandler):
    """
    LangChain callback that screens every LLM input through SENTINEL
    before it reaches the model and screens output before it reaches the caller.
    """

    def __init__(self, tenant_id: str, api_key: str,
                 gateway_url: Optional[str] = None,
                 block_on_error: bool = True):
        self.tenant_id = tenant_id
        self.api_key = api_key
        self.gateway_url = (gateway_url or settings.gateway_url).rstrip("/")
        self.block_on_error = block_on_error
        self._last_request_id: Optional[str] = None

    # ── Pre-LLM hook ────────────────────────────────────────────────────────────

    def on_chat_model_start(
        self,
        serialized: Dict[str, Any],
        messages: List[List[BaseMessage]],
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        flat = [{"role": m.type, "content": m.content}
                for batch in messages for m in batch]
        self._screen_input(flat)

    def on_llm_start(
        self,
        serialized: Dict[str, Any],
        prompts: List[str],
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        messages = [{"role": "user", "content": p} for p in prompts]
        self._screen_input(messages)

    # ── Post-LLM hook ───────────────────────────────────────────────────────────

    def on_llm_end(self, response: LLMResult, *, run_id: UUID, **kwargs: Any) -> None:
        for batch in response.generations:
            for gen in batch:
                if isinstance(gen, ChatGeneration):
                    self._screen_output(gen.text)

    # ── Internal ────────────────────────────────────────────────────────────────

    def _screen_input(self, messages: list) -> None:
        try:
            resp = httpx.post(
                f"{self.gateway_url}/v1/screen",
                json={"tenant_id": self.tenant_id, "messages": messages,
                      "phase": "input"},
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=5.0,
            )
            data = resp.json()
            self._last_request_id = data.get("request_id")
            if data.get("decision") == Decision.BLOCK:
                raise ValueError(
                    f"SENTINEL blocked LangChain input: {data.get('request_id')}"
                )
        except httpx.RequestError as exc:
            logger.warning("SENTINEL gateway unreachable: %s", exc)
            if self.block_on_error:
                raise

    def _screen_output(self, text: str) -> None:
        try:
            resp = httpx.post(
                f"{self.gateway_url}/v1/screen",
                json={"tenant_id": self.tenant_id,
                      "messages": [{"role": "assistant", "content": text}],
                      "phase": "output"},
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=5.0,
            )
            data = resp.json()
            if data.get("decision") == Decision.BLOCK:
                logger.warning(
                    "SENTINEL blocked LangChain output (request=%s)",
                    self._last_request_id,
                )
        except httpx.RequestError as exc:
            logger.warning("SENTINEL gateway unreachable on output screen: %s", exc)
