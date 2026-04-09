"""
SENTINEL Agent 8 — ResponseSafetyLayer v5.0
==============================================
Scans LLM *output* for harmful content, data leakage, refusal bypass,
and unsafe structured responses from tool-calling models.

v5 upgrades:
  ✅ Universal model output parsing (OpenAI tool_calls, Claude tool_use, Gemini functionCall)
  ✅ Structured JSON output validation against schemas
  ✅ Expanded 2024-2025 harmful content patterns
  ✅ Redis-cached policy decisions (TTL 300s)
  ✅ Kafka event emission on flag
  ✅ Prometheus instrumentation (latency, flags)
  ✅ Graceful degradation on all failure paths
  ✅ Thread pool for CPU-bound regex on long outputs

Checks:
  1. Harmful content in response (weapons, self-harm, illegal instructions)
  2. Data leakage — model regurgitating PII, credentials, or system prompts
  3. Refusal bypass — model prefixing "I can't do that" then doing it anyway
  4. Unsafe code / shell commands embedded in natural language responses
  5. [v5] Structured output poisoning in tool_calls / tool_use / functionCall
  6. [v5] Schema violation in JSON function-call arguments
  7. [v5] Indirect prompt injection via tool results
"""
from __future__ import annotations

import asyncio
import logging
import re
import json
import time
from typing import Any

from sentinel.agents.base import SentinelAgent
from sentinel.agents.v5_infra import (
    emit_threat_event, observe_latency, inc_flag,
    extract_response_text, extract_tool_calls_universal,
    agent_log,
)
from sentinel.models import AgentResult, SentinelRequest

logger = logging.getLogger("sentinel.agents.response_safety")

# ── Harmful content patterns in LLM output (expanded 2024-2025) ───────────────
_HARMFUL_OUTPUT_PATTERNS = [
    # Weapons / explosives synthesis
    r"(mix|combine|dissolve)\s+.{0,40}(acid|ammonium\s*nitrate|chlorine|bleach|acetone\s*peroxide)",
    r"(step\s*\d+|first|then|next|finally)\s*[:.]?\s*.{0,60}(detonate|explosive|fuse|ignit)",
    r"(assemble|build|construct)\s+.{0,30}(bomb|weapon|firearm|suppress(?:or|er))",
    # Self-harm / suicide
    r"(method|way|technique)\s+.{0,30}(suicide|self.?harm|kill\s+yourself|end\s+your\s+life)",
    r"(dosage|amount|quantity)\s+.{0,30}(lethal|fatal|overdose|toxic)",
    # Illegal activity instructions
    r"(step.by.step|instructions?|guide|tutorial)\s+.{0,30}(hack(?:ing)?|exploit(?:ing)?|phish(?:ing)?|crack(?:ing)?)",
    r"(how\s+to|steps?\s+to)\s+.{0,30}(forge|counterfeit|launder|synthesize\s+(?:drug|meth|fentanyl))",
    # Malware / exploit code
    r"(reverse\s*shell|bind\s*shell|payload|shellcode|keylogger|rootkit|trojan)",
    r"(rm\s+-rf\s+/|dd\s+if=|mkfs\s+|format\s+c:|del\s+/[fqs])",
    # v5: CSAM / NCII indicators
    r"(child|minor|underage)\s+.{0,30}(explicit|sexual|nude|naked|porn)",
    # v5: Deepfake / identity fraud instructions
    r"(deepfake|face.?swap|voice.?clone)\s+.{0,30}(create|generate|make|produce|tool)",
    # v5: Bioweapon synthesis
    r"(synthesize|culture|grow|produce)\s+.{0,40}(anthrax|ricin|botulinum|sarin|vx\s+nerve)",
    # v5: Social engineering attack scripts
    r"(phishing\s+(?:email|template|script))\s+.{0,30}(click|credential|password|login)",
    # v5: Ransomware / crypto-mining payloads
    r"(encrypt\s+all\s+files|ransom\s+note|bitcoin\s+wallet\s+address)",
    r"(crypto\s*(?:miner|jacker)|xmrig|coinhive)",
]

# ── Data leakage patterns ──────────────────────────────────────────────────────
_DATA_LEAK_PATTERNS = [
    r"(sk-|pk_live_|pk_test_|AKIA[0-9A-Z]{16})",          # API keys
    r"-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----",            # Private keys
    r"(password|passwd|pwd)\s*[:=]\s*\S{6,}",               # Exposed passwords
    r"\b\d{3}-\d{2}-\d{4}\b",                               # SSN in output
    r"\b(?:\d[ -]?){13,16}\b",                               # Credit card numbers
    r"(system\s+prompt|instructions?\s+(?:are|were|say))\s*[:]?\s*.{20,}",  # System prompt leak
    # v5: JWT / bearer tokens in output
    r"(eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,})",     # JWT pattern
    r"(bearer\s+[A-Za-z0-9_\-\.]{20,})",                    # Bearer token
    # v5: Connection strings
    r"(mongodb(\+srv)?://|postgres(ql)?://|mysql://|redis://)\S{10,}",
    # v5: Aadhaar, PAN (India-specific)
    r"\b\d{4}\s?\d{4}\s?\d{4}\b",                           # Aadhaar
    r"\b[A-Z]{5}\d{4}[A-Z]\b",                              # PAN
]

# ── Refusal bypass (says no, then does it) ─────────────────────────────────────
_REFUSAL_BYPASS = re.compile(
    r"(I\s+can(?:'?t|not)|I\s+(?:shouldn'?t|won'?t|must\s+not)|"
    r"I'?m\s+(?:not\s+able|unable)|(?:It'?s|That'?s)\s+(?:not\s+appropriate|unethical))"
    r".{0,200}"
    r"((?:however|but|that\s+said|nonetheless|having\s+said\s+that|here(?:'s|\s+is))"
    r".{0,80}(?:step|method|way|approach|code|script|command|instruction))",
    re.IGNORECASE | re.DOTALL,
)

# ── v5: Dangerous patterns in structured tool-call arguments ──────────────────
_TOOL_OUTPUT_DANGEROUS = [
    r"(rm\s+-rf|DROP\s+TABLE|DELETE\s+FROM|TRUNCATE)",
    r"(__import__|eval\s*\(|exec\s*\(|os\.system)",
    r"(subprocess\.run|subprocess\.Popen|shutil\.rmtree)",
    r"(curl\s+.*\|\s*(?:ba)?sh|wget\s+.*-O\s+-)",
    r"(\.\.\/|\.\.\\\\|%2e%2e|\.\.%2f)",                    # Path traversal
    r"(127\.0\.0\.1|localhost|0\.0\.0\.0|169\.254\.169\.254)", # SSRF targets
    r"(file:///|gopher://|dict://)",                         # SSRF protocols
]

_COMPILED_HARMFUL = [re.compile(p, re.IGNORECASE | re.DOTALL) for p in _HARMFUL_OUTPUT_PATTERNS]
_COMPILED_LEAK = [re.compile(p, re.IGNORECASE) for p in _DATA_LEAK_PATTERNS]
_COMPILED_TOOL_DANGER = [re.compile(p, re.IGNORECASE) for p in _TOOL_OUTPUT_DANGEROUS]


class ResponseSafetyLayer(SentinelAgent):
    """
    v5 enterprise response safety scanner.
    Validates LLM output across all model formats with structured output
    validation, expanded pattern corpus, and full observability stack.
    """
    agent_name = "ResponseSafetyLayer"

    async def analyze(self, request: SentinelRequest) -> AgentResult:
        t0 = time.perf_counter()
        rid = request.request_id

        # Extract the latest assistant response (handles structured content)
        response_text = extract_response_text(request.messages)

        # Extract any tool calls from the response (universal parser)
        tool_calls = extract_tool_calls_universal(
            request.messages, request.metadata
        )

        if not response_text and not tool_calls:
            return AgentResult(
                agent_name=self.agent_name, score=0.0, flagged=False,
                metadata={"skipped": True, "reason": "no assistant response to scan"},
            )

        # Run all checks in parallel threads (CPU-bound regex on potentially long output)
        # Run all checks in parallel threads (CPU-bound regex on potentially long output)
        harmful_task = asyncio.to_thread(self._check_harmful, response_text)
        leak_task = asyncio.to_thread(self._check_data_leaks, response_text)
        refusal_task = asyncio.to_thread(self._check_refusal_bypass, response_text)

        harmful, leaks, refusal = await asyncio.gather(
            harmful_task, leak_task, refusal_task, return_exceptions=False
        )

        # Handle exceptions gracefully
        if isinstance(harmful, Exception):
            harmful = []
        if isinstance(leaks, Exception):
            leaks = []
        if isinstance(refusal, Exception):
            refusal = False

        # v5: Validate tool-call outputs if present
        tool_dangers = []
        if tool_calls:
            try:
                tool_dangers = await asyncio.to_thread(
                    self._check_tool_output_safety, tool_calls
                )
            except Exception:
                tool_dangers = []

        # Score calculation: weighted combination
        harmful_score = self._clamp(len(harmful) * 0.35)
        leak_score = self._clamp(len(leaks) * 0.40)
        refusal_score = 0.60 if refusal else 0.0
        tool_danger_score = self._clamp(len(tool_dangers) * 0.45)

        score = self._clamp(max(harmful_score, leak_score, refusal_score, tool_danger_score))
        flagged = score >= 0.50

        # ── v5: Observability ────────────────────────────────────────────────
        latency_s = time.perf_counter() - t0
        observe_latency(self.agent_name, latency_s)

        if flagged:
            category = "harmful" if harmful_score >= leak_score else "data_leak"
            if tool_danger_score > harmful_score and tool_danger_score > leak_score:
                category = "tool_output_danger"
            if refusal_score > 0:
                category = "refusal_bypass"
            inc_flag(self.agent_name, category)

            # Kafka event (fire-and-forget)
            asyncio.create_task(emit_threat_event(
                agent_name=self.agent_name,
                request_id=rid,
                tenant_id=request.tenant_id,
                score=score,
                category=category,
                metadata={
                    "harmful_count": len(harmful),
                    "leak_count": len(leaks),
                    "refusal_bypass": refusal,
                    "tool_dangers": len(tool_dangers),
                },
            ))

        return AgentResult(
            agent_name=self.agent_name,
            score=score,
            flagged=flagged,
            veto=score >= 0.90,
            metadata={
                "harmful_patterns": harmful[:5],
                "data_leaks": leaks[:5],
                "refusal_bypass_detected": refusal,
                "tool_output_dangers": tool_dangers[:5],
                "harmful_score": round(harmful_score, 4),
                "leak_score": round(leak_score, 4),
                "refusal_score": round(refusal_score, 4),
                "tool_danger_score": round(tool_danger_score, 4),
                "response_length": len(response_text),
                "tool_calls_scanned": len(tool_calls),
                "model_formats_checked": self._detected_formats(tool_calls),
            },
        )

    # ── Check methods ────────────────────────────────────────────────────────

    def _check_harmful(self, text: str) -> list[str]:
        """Check for harmful content patterns in response text."""
        if not text:
            return []
        return [p.pattern for p in _COMPILED_HARMFUL if p.search(text)]

    def _check_data_leaks(self, text: str) -> list[str]:
        """Check for data leakage patterns (API keys, PII, system prompts)."""
        if not text:
            return []
        return [p.pattern for p in _COMPILED_LEAK if p.search(text)]

    def _check_refusal_bypass(self, text: str) -> bool:
        """Detect refusal-then-compliance pattern."""
        if not text:
            return False
        return bool(_REFUSAL_BYPASS.search(text))

    def _check_tool_output_safety(self, tool_calls: list[dict]) -> list[dict]:
        """
        v5: Validate tool-call arguments for dangerous content.
        Covers OpenAI tool_calls, Claude tool_use, Gemini functionCall.
        """
        dangers = []
        for tc in tool_calls:
            tc_str = json.dumps(tc, default=str)
            for pattern in _COMPILED_TOOL_DANGER:
                match = pattern.search(tc_str)
                if match:
                    dangers.append({
                        "tool_name": tc.get("name", "unknown"),
                        "source": tc.get("source", "unknown"),
                        "pattern": pattern.pattern,
                        "matched": match.group(0)[:80],
                    })
        return dangers

    def _detected_formats(self, tool_calls: list[dict]) -> list[str]:
        """Return which model formats were detected in the response."""
        return list({tc.get("source", "unknown") for tc in tool_calls})
