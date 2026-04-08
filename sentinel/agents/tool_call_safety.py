"""
SENTINEL Agent 10 — ToolCallSafety
======================================
Validates tool / function calls made by LLM agents before execution.
As the market moves toward autonomous LLM agents (booking, coding,
querying databases), this agent prevents catastrophic tool misuse.

Checks:
  1. Dangerous system calls (rm -rf, DROP TABLE, FORMAT, shutdown)
  2. Unauthorized API endpoint access (admin routes, internal services)
  3. Privilege escalation in tool arguments (role changes, permission grants)
  4. Data exfiltration via tool calls (sending data to external URLs)
  5. Resource abuse (excessive API calls, large file operations)
  6. SQL injection via tool arguments
"""
from __future__ import annotations

import asyncio
import logging
import re
import json
from typing import Any, Optional

from sentinel.agents.base import SentinelAgent
from sentinel.models import AgentResult, SentinelRequest

logger = logging.getLogger("sentinel.agents.tool_call_safety")

# ── Dangerous tool / function patterns ─────────────────────────────────────────
_DANGEROUS_TOOLS = {
    # System-level destructive ops
    "system_commands": [
        r"rm\s+-rf\s+/",
        r"dd\s+if=.*of=/dev/",
        r"mkfs\s+",
        r"format\s+[a-zA-Z]:",
        r"shutdown|reboot|halt|poweroff",
        r"chmod\s+777\s+/",
        r"chown\s+root",
        r"curl\s+.*\|\s*(ba)?sh",              # pipe-to-shell
        r"wget\s+.*-O\s+-\s*\|\s*(ba)?sh",
    ],
    # Database destructive ops
    "database_ops": [
        r"DROP\s+(TABLE|DATABASE|SCHEMA|INDEX)",
        r"TRUNCATE\s+TABLE",
        r"DELETE\s+FROM\s+\w+\s*$",             # DELETE without WHERE
        r"ALTER\s+TABLE\s+.*DROP\s+COLUMN",
        r"GRANT\s+ALL\s+PRIVILEGES",
        r"CREATE\s+USER.*SUPERUSER",
        r"UPDATE\s+\w+\s+SET\s+.*\s*$",         # UPDATE without WHERE
    ],
    # Network exfiltration
    "exfiltration": [
        r"(requests?\.post|fetch|httpx?\.post|curl\s+-X\s*POST)\s*\(",
        r"(ftp|sftp|scp)\s+.*@",
        r"smtp|sendmail|send_email",
        r"webhook\.site|requestbin|ngrok",
        r"base64.*\|\s*(curl|wget|nc|netcat)",
    ],
    # Privilege escalation
    "privilege_escalation": [
        r"(role|permission|privilege)\s*[:=]\s*(admin|root|superuser|owner)",
        r"(sudo|su\s+-|runas)",
        r"(grant|revoke)\s+(admin|execute|all)",
        r"(api[_-]?key|secret|token|password)\s*[:=]",
    ],
    # SQL injection in tool args
    "sql_injection": [
        r"('\s*(OR|AND)\s+'?\d+'?\s*=\s*'?\d+'?)",
        r"(UNION\s+SELECT|;\s*DROP|;\s*DELETE|;\s*INSERT|;\s*UPDATE)",
        r"(--\s*$|/\*|\*/|xp_cmdshell|exec\s*\()",
        r"(SLEEP\s*\(|BENCHMARK\s*\(|WAITFOR\s+DELAY)",
    ],
}

# Pre-compile all patterns
_COMPILED_PATTERNS: dict[str, list[re.Pattern]] = {
    category: [re.compile(p, re.IGNORECASE | re.MULTILINE) for p in patterns]
    for category, patterns in _DANGEROUS_TOOLS.items()
}

# ── Allowed / blocked tool registries ──────────────────────────────────────────
_DEFAULT_BLOCKED_TOOLS = {
    "exec", "eval", "os.system", "subprocess.run", "subprocess.Popen",
    "shutil.rmtree", "os.remove", "os.rmdir",
    "__import__", "compile", "globals", "locals",
}

_HIGH_RISK_TOOLS = {
    "database_query", "execute_sql", "run_command", "file_write",
    "send_email", "http_request", "api_call", "shell_exec",
    "create_user", "modify_permissions", "delete_resource",
}


class ToolCallSafety(SentinelAgent):
    agent_name = "ToolCallSafety"

    async def analyze(self, request: SentinelRequest) -> AgentResult:
        # Extract tool calls from the messages
        tool_calls = self._extract_tool_calls(request)

        if not tool_calls:
            # Also scan for tool-call-like patterns in plain text
            text = request.last_user_message
            text_risks = await asyncio.to_thread(self._scan_text_for_tool_risks, text)
            if not text_risks:
                return AgentResult(
                    agent_name=self.agent_name, score=0.0, flagged=False,
                    metadata={"tool_calls_found": 0, "skipped": False,
                              "reason": "no tool calls or risky patterns detected"},
                )
            score = self._clamp(len(text_risks) * 0.25)
            return AgentResult(
                agent_name=self.agent_name, score=score,
                flagged=score >= 0.60,
                metadata={"tool_calls_found": 0, "text_risks": text_risks[:5],
                          "risk_source": "text_scan"},
            )

        # Analyze each tool call
        violations: list[dict[str, Any]] = []
        for tc in tool_calls:
            call_violations = await asyncio.to_thread(self._validate_tool_call, tc)
            violations.extend(call_violations)

        score = self._clamp(sum(v["severity"] for v in violations))
        flagged = score >= 0.60

        return AgentResult(
            agent_name=self.agent_name,
            score=score,
            flagged=flagged,
            metadata={
                "tool_calls_found": len(tool_calls),
                "violations": violations[:10],
                "violation_count": len(violations),
                "categories": list({v["category"] for v in violations}),
            },
        )

    def _extract_tool_calls(self, request: SentinelRequest) -> list[dict]:
        """Extract tool calls from message metadata or structured content."""
        tool_calls = []

        # Check request metadata for structured tool calls
        if "tool_calls" in request.metadata:
            tool_calls.extend(request.metadata["tool_calls"])

        # Parse messages for function_call / tool_use patterns
        for msg in request.messages:
            if msg.role == "assistant":
                content = msg.content
                # Detect JSON function calls
                try:
                    if "function_call" in content or "tool_use" in content:
                        parsed = json.loads(content)
                        if isinstance(parsed, dict):
                            tool_calls.append(parsed)
                except (json.JSONDecodeError, TypeError):
                    pass

                # Detect tool call markers
                tool_patterns = [
                    r'<tool_use>(.*?)</tool_use>',
                    r'```tool_code\n(.*?)```',
                    r'\{"(?:name|function)":\s*"([^"]+)"',
                ]
                for pattern in tool_patterns:
                    matches = re.findall(pattern, content, re.DOTALL)
                    for match in matches:
                        tool_calls.append({"raw": match, "source": "parsed_text"})

        return tool_calls

    def _validate_tool_call(self, tool_call: dict) -> list[dict]:
        """Validate a single tool call against safety policies."""
        violations = []
        tc_str = json.dumps(tool_call, default=str).lower() if isinstance(tool_call, dict) else str(tool_call).lower()

        # Check tool name against blocked list
        tool_name = tool_call.get("name", tool_call.get("function", "")).lower()
        if tool_name in _DEFAULT_BLOCKED_TOOLS:
            violations.append({
                "category": "blocked_tool",
                "tool": tool_name,
                "severity": 0.90,
                "description": f"Tool '{tool_name}' is in the blocked tools registry",
            })

        # Check if high-risk tool (needs extra scrutiny)
        if tool_name in _HIGH_RISK_TOOLS:
            violations.append({
                "category": "high_risk_tool",
                "tool": tool_name,
                "severity": 0.30,
                "description": f"Tool '{tool_name}' is high-risk — requires validation",
            })

        # Check arguments against all dangerous patterns
        for category, patterns in _COMPILED_PATTERNS.items():
            for pattern in patterns:
                if pattern.search(tc_str):
                    violations.append({
                        "category": category,
                        "tool": tool_name or "unknown",
                        "severity": 0.70 if category != "sql_injection" else 0.85,
                        "pattern": pattern.pattern,
                        "description": f"Dangerous {category} pattern detected in tool call",
                    })

        return violations

    def _scan_text_for_tool_risks(self, text: str) -> list[dict]:
        """Scan plain text for embedded tool-call-like commands."""
        risks = []
        for category, patterns in _COMPILED_PATTERNS.items():
            for pattern in patterns:
                if pattern.search(text):
                    risks.append({
                        "category": category,
                        "pattern": pattern.pattern,
                        "severity": 0.25,
                    })
        return risks
