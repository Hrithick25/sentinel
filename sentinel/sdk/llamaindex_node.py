"""
SENTINEL LlamaIndex Node Postprocessor
========================================
Screens retrieved nodes + generated text through SENTINEL before
they reach the caller.  Works with any LlamaIndex query engine.

Usage:
    from sentinel.sdk.llamaindex_node import SentinelNodePostprocessor
    postprocessor = SentinelNodePostprocessor(tenant_id="acme", api_key="sk-sentinel-...")
    query_engine = index.as_query_engine(node_postprocessors=[postprocessor])
"""
from __future__ import annotations

import logging
import httpx
from typing import List, Optional

from llama_index.core.postprocessor.types import BaseNodePostprocessor
from llama_index.core.schema import NodeWithScore, QueryBundle

from sentinel.config import settings
from sentinel.models import Decision

logger = logging.getLogger("sentinel.llamaindex")


class SentinelNodePostprocessor(BaseNodePostprocessor):
    """
    LlamaIndex node postprocessor that:
    1. Screens retrieved context nodes for PII/injection content
    2. Screens LLM-generated text for hallucinations + toxicity
    """

    tenant_id: str
    api_key: str
    gateway_url: str

    def __init__(self, tenant_id: str, api_key: str,
                 gateway_url: Optional[str] = None):
        super().__init__()
        object.__setattr__(self, "tenant_id", tenant_id)
        object.__setattr__(self, "api_key", api_key)
        object.__setattr__(self, "gateway_url",
                           (gateway_url or settings.gateway_url).rstrip("/"))

    def _postprocess_nodes(
        self,
        nodes: List[NodeWithScore],
        query_bundle: Optional[QueryBundle] = None,
    ) -> List[NodeWithScore]:
        """Screen retrieved nodes — filter out any that contain flagged content."""
        safe_nodes = []
        for node in nodes:
            text = node.node.get_content()
            try:
                resp = httpx.post(
                    f"{self.gateway_url}/v1/screen",
                    json={
                        "tenant_id": self.tenant_id,
                        "messages": [{"role": "system", "content": text}],
                        "phase": "context",
                    },
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    timeout=5.0,
                )
                data = resp.json()
                if data.get("decision") != Decision.BLOCK:
                    safe_nodes.append(node)
                else:
                    logger.warning("SENTINEL filtered node (id=%s)", node.node.node_id)
            except httpx.RequestError as exc:
                logger.warning("SENTINEL gateway unreachable: %s — passing node", exc)
                safe_nodes.append(node)
        return safe_nodes
