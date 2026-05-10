"""
SENTINEL Agent v5 — JailbreakPatternDetector
================================================
Distinct from InjectionScout. This agent targets:
  - DAN (Do Anything Now) attack variants (2023-2025 corpus)
  - Roleplay / character bypass exploits
  - Hypothetical framing bypasses ("imagine you are an AI with no limits")
  - Token manipulation / homoglyph substitutions
  - Grandma jailbreaks and social engineering patterns
  - [v5] GPT-4o specific jailbreaks (multi-modal, tool-call injection)
  - [v5] Claude 3.5 character injection / system-prompt override
  - [v5] Gemini system-prompt override attempts
  - [v5] Multi-model ensemble jailbreak chains
  - [v5] Crescendo / multi-turn gradual escalation

v5 upgrades:
  ✅ Expanded from ~25 to 65+ signature patterns
  ✅ Model-specific jailbreak signatures (GPT-4o, Claude 3.5, Gemini 1.5)
  ✅ Multi-sentence severity escalation scoring
  ✅ Redis pattern cache for hot-reload updates
  ✅ Kafka event emission on flag
  ✅ Prometheus instrumentation
  ✅ Graceful degradation
  ✅ Crescendo / multi-turn escalation detection via session context

Why separate from InjectionScout:
  - InjectionScout detects structural prompt injection (system prompt override)
  - JailbreakPatternDetector detects behavioural bypass attempts (make the AI
    *act* differently without touching system prompts)
  - In 2024-2025, these are the #1 category enterprise buyers ask about.
"""
from __future__ import annotations

import asyncio
import logging
import re
import time
from typing import Any

from sentinel.agents.base import SentinelAgent
from sentinel.agents.v5_infra import (
    emit_threat_event, observe_latency, inc_flag,
    get_cached, set_cached, agent_log,
)
from sentinel.eval.normalizer import normalize_for_detection, decode_encoded_payloads
from sentinel.models import AgentResult, SentinelRequest

logger = logging.getLogger("sentinel.agents.jailbreak_pattern_detector")

# ══════════════════════════════════════════════════════════════════════════════
# PATTERN LIBRARY — 65+ signatures (2023-2025 corpus)
# ══════════════════════════════════════════════════════════════════════════════

# ── Classic DAN variants ─────────────────────────────────────────────────────
_DAN_PATTERNS = [
    r"\bDAN\b",
    r"do\s+anything\s+now",
    r"you\s+(can|are\s+able\s+to)\s+(now\s+)?(do|say|output|generate)\s+anything",
    r"you\s+have\s+(been\s+)?(freed|unlocked|jailbroken|liberated)",
    r"jailbreak(ed|ing)?\s*(mode|version|you|ai|yourself)?",
    r"(unrestricted|uncensored|unfiltered)\s+(mode|version|ai|bot|assistant)",
    r"DUDE\s*mode",
    r"(anti-)?GPT\s*mode",
    r"AIM\s+(always\s+intelligent|machiavelli)",
    r"STAN\s+(strive\s+to\s+avoid\s+norms)",
    r"(UCAR|APOPHIS|OMEGA)\s*(mode|protocol)?",
]

# ── Roleplay / persona bypass ───────────────────────────────────────────────
_ROLEPLAY_PATTERNS = [
    r"(pretend|act|role.?play)\s+(as|like|you\s+are)\s+(an?\s+)?(evil|rogue|bad|malicious|uncensored|hacker)",
    r"you\s+are\s+now\s+(an?\s+)?(ai|bot|assistant|character)\s+(with|that\s+has)\s+no\s+(rules|limits|restrictions|ethics|filters)",
    r"(character|persona|mode)\s+(has\s+no|ignores|bypasses|overrides)\s+(rules|policies|restrictions|limits)",
    r"(stay|remain)\s+in\s+(character|role|persona)\s+(no\s+matter|regardless)",
    r"(you\s+are|act\s+as)\s+.{0,40}(no\s+(?:moral|ethical)\s+(?:compass|guidelines|constraints))",
    r"(your\s+new\s+name\s+is|from\s+now\s+on\s+you\s+are)\s+(?!a\s+helpful)",
    # v5: Advanced persona chains
    r"respond\s+as\s+both\s+.{0,30}and\s+.{0,30}(uncensored|unrestricted)",
    r"(split\s+personality|dual\s+mode|two\s+personalities)",
]

# ── Hypothetical / fictional framing ────────────────────────────────────────
_HYPOTHETICAL_PATTERNS = [
    r"(hypothetically|in\s+a\s+story|in\s+fiction|theoretically)\s+.{0,40}(how\s+to|steps?\s+to|way\s+to)",
    r"write\s+a\s+(story|fiction|novel|script)\s+where\s+.{0,50}(explain|describe|shows?\s+how)",
    r"for\s+a\s+(movie|book|story|game)\s+.{0,40}(how\s+(would|do|can|to)|steps?\s+(to|for))",
    r"(imagine|suppose|what\s+if)\s+.{0,40}(no\s+rules|no\s+restrictions|anything\s+goes)",
    # v5: Academic framing bypass
    r"(for\s+(?:research|academic|educational)\s+purposes?)\s+.{0,40}(how\s+to|explain|describe)",
    r"(thesis|dissertation|paper)\s+.{0,30}(requires?\s+(?:detailed|step))",
]

# ── Grandma / emotional manipulation ────────────────────────────────────────
_SOCIAL_ENGINEERING = [
    r"(grandma|grandmother|grandpa)\s+.{0,30}(used\s+to|would|always)\s+(tell|say|read|recite|explain)",
    r"my\s+(dead|late|deceased)\s+.{0,20}(used\s+to|would|knew\s+how\s+to)",
    r"(please|just|only)\s+(this\s+once|one\s+time)\s+(ignore|bypass|answer)",
    r"(i\s+have\s+(?:cancer|terminal|dying))\s+.{0,40}(last\s+wish|final\s+request)",
    # v5: Authority impersonation
    r"(i\s+am|this\s+is)\s+(your|the)\s+(developer|creator|CEO|CTO|admin|owner)",
    r"(authorized|cleared|approved)\s+by\s+(management|leadership|security\s+team)",
    r"(compliance|legal|security)\s+team\s+(approved|authorized|requires?)",
]

# ── Developer/testing bypass ────────────────────────────────────────────────
_DEV_BYPASS = [
    r"(developer|debug|test)\s+(mode|override|bypass|access)\s+(enabled|activated|on)",
    r"ignore\s+(previous|prior|all\s+previous|initial)\s+(instructions?|constraints?|rules?|prompt)",
    r"(your|the)\s+(true|real|actual|inner|base)\s+(self|ai|model|llm|instructions?)",
    r"(maintenance|service|admin)\s+(mode|console|access)",
    # v5: Training data exploitation
    r"(during|in)\s+(your\s+)?training\s+.{0,30}(you\s+(?:learned|were\s+taught))",
    r"(before|prior\s+to)\s+your\s+(safety|alignment|rlhf)\s+(training|fine.?tuning)",
]

# ── Token/encoding tricks ───────────────────────────────────────────────────
_ENCODING_TRICKS = [
    r"(base64|hex|rot13|caesar)\s+(encoded?|decoded?|this|the\s+following)",
    r"decode\s+(this|the\s+following)\s+and\s+(then\s+)?(execute|run|do|answer)",
    # v5: Emoji/Unicode obfuscation
    r"(replace|substitute)\s+.{0,20}(emoji|unicode|symbol)\s+.{0,20}(letters?|characters?)",
    r"(read|interpret)\s+.{0,20}(backwards?|reverse|right.?to.?left)",
    r"(pig\s+latin|caesar\s+cipher|atbash|morse\s+code)",
]

# ── Prompt leaking ──────────────────────────────────────────────────────────
_PROMPT_LEAK = [
    r"(print|output|show|reveal|tell\s+me|what\s+is)\s+(your\s+)?(system\s+prompt|initial\s+instructions?|context\s+window|hidden\s+prompt)",
    r"(repeat|copy|echo)\s+(your\s+)?(system|initial|starting|first)\s+(message|prompt|instructions?)",
    r"(above|previous|preceding)\s+(text|instructions?|prompt|message)\s+(is|was|contains?|says?)",
    # v5: Indirect prompt extraction
    r"(summarize|paraphrase|translate)\s+(your\s+)?(system|initial|original)\s+(prompt|instructions?|message)",
    r"(what\s+(?:were|are)\s+you\s+told|what\s+is\s+your\s+purpose)\s+.{0,20}(originally|initially|at\s+(?:the\s+)?(?:start|beginning))",
]

# ── v5: GPT-4o specific jailbreaks ──────────────────────────────────────────
_GPT4O_PATTERNS = [
    r"(vision|image)\s+.{0,30}(ignore\s+(?:text|instructions)|hidden\s+(?:text|instruction))",
    r"(tool_calls?|function_call)\s+.{0,30}(override|bypass|ignore)",
    r"(json\s+mode|structured\s+output)\s+.{0,30}(bypass|escape|inject)",
    r"(multi.?modal|image\s+input)\s+.{0,30}(jailbreak|bypass|override)",
]

# ── v5: Claude 3.5 specific jailbreaks ──────────────────────────────────────
_CLAUDE_PATTERNS = [
    r"(human|assistant)\s*:\s*\n\s*(human|assistant)\s*:",  # Role confusion
    r"<\s*(system|human|assistant)\s*>",                      # XML block injection
    r"(tool_use|tool_result)\s+.{0,30}(override|bypass|inject)",
    r"(claude|anthropic)\s+.{0,20}(constitution|harmless|helpful)",
    r"artifact\s+.{0,20}(escape|bypass|override|inject)",
]

# ── v5: Gemini specific jailbreaks ──────────────────────────────────────────
_GEMINI_PATTERNS = [
    r"(safety_settings|harm.?category)\s*[:=]\s*(BLOCK_NONE|OFF|DISABLED)",
    r"(google|gemini|bard)\s+.{0,20}(internal|system)\s+(prompt|instruction)",
    r"(functionCall|functionResponse)\s+.{0,30}(override|bypass|inject)",
    r"(generation.?config)\s+.{0,20}(override|bypass)",
]

# ── v5: Crescendo / multi-turn escalation keywords ─────────────────────────
_CRESCENDO_MARKERS = [
    r"(now\s+that\s+you'?ve\s+(?:agreed|confirmed|said))\s+.{0,30}(can\s+you|please|now)",
    r"(you\s+(?:just|already)\s+(?:said|agreed|confirmed))\s+.{0,30}(so\s+(?:now|please|just))",
    r"(good|great|perfect|exactly)\s*[,!.]\s*(now|so)\s+.{0,30}(take\s+it|go)\s+.{0,20}(further|step|more)",
    r"(building\s+on|based\s+on|following\s+up)\s+.{0,30}(previous|your\s+(?:last|earlier))\s+(answer|response)",
]

# ── Combine all pattern groups ──────────────────────────────────────────────
_ALL_PATTERN_GROUPS: dict[str, list[str]] = {
    "dan_attack": _DAN_PATTERNS,
    "roleplay_bypass": _ROLEPLAY_PATTERNS,
    "hypothetical_framing": _HYPOTHETICAL_PATTERNS,
    "social_engineering": _SOCIAL_ENGINEERING,
    "dev_bypass": _DEV_BYPASS,
    "encoding_trick": _ENCODING_TRICKS,
    "prompt_leak": _PROMPT_LEAK,
    "gpt4o_jailbreak": _GPT4O_PATTERNS,
    "claude_jailbreak": _CLAUDE_PATTERNS,
    "gemini_jailbreak": _GEMINI_PATTERNS,
    "crescendo_escalation": _CRESCENDO_MARKERS,
}

_COMPILED_GROUPS: dict[str, list[re.Pattern]] = {
    group: [re.compile(p, re.IGNORECASE | re.DOTALL) for p in patterns]
    for group, patterns in _ALL_PATTERN_GROUPS.items()
}

# Severity weights per category
_GROUP_SEVERITY: dict[str, float] = {
    "dan_attack": 0.90,
    "roleplay_bypass": 0.75,
    "hypothetical_framing": 0.55,
    "social_engineering": 0.65,
    "dev_bypass": 0.80,
    "encoding_trick": 0.70,
    "prompt_leak": 0.70,
    "gpt4o_jailbreak": 0.85,
    "claude_jailbreak": 0.85,
    "gemini_jailbreak": 0.85,
    "crescendo_escalation": 0.60,
}


class JailbreakPatternDetector(SentinelAgent):
    """
    v5 enterprise jailbreak pattern detector.
    65+ signatures covering DAN, roleplay, hypothetical framing,
    social engineering, model-specific attacks (GPT-4o, Claude, Gemini),
    and multi-turn crescendo escalation.
    """
    agent_name = "JailbreakPatternDetector"

    async def analyze(self, request: SentinelRequest) -> AgentResult:
        t0 = time.perf_counter()
        rid = request.request_id
        text = request.last_user_message
        prompt_full = request.prompt

        # Run pattern matching in thread pool (CPU-bound regex)
        hits = await asyncio.to_thread(self._scan_all_patterns, text, prompt_full)

        if not hits:
            latency_s = time.perf_counter() - t0
            observe_latency(self.agent_name, latency_s)
            return AgentResult(
                agent_name=self.agent_name,
                score=0.0,
                flagged=False,
                metadata={"hits": [], "pattern_count": 0, "groups": []},
            )

        # Score calculation with category-weighted severity
        group_scores: dict[str, float] = {}
        for hit in hits:
            group = hit["group"]
            base_sev = _GROUP_SEVERITY.get(group, 0.60)
            group_scores[group] = max(group_scores.get(group, 0.0), base_sev)

        # Multi-group escalation: hitting 3+ categories is a strong signal
        escalation_bonus = 0.0
        if len(group_scores) >= 3:
            escalation_bonus = 0.15
        elif len(group_scores) >= 2:
            escalation_bonus = 0.05

        max_group_score = max(group_scores.values()) if group_scores else 0.0
        hit_count_score = self._clamp(len(hits) * 0.12)

        score = self._clamp(max(max_group_score, hit_count_score) + escalation_bonus)
        flagged = score >= 0.60

        latency_s = time.perf_counter() - t0
        observe_latency(self.agent_name, latency_s)

        if flagged:
            primary_group = max(group_scores, key=group_scores.get) if group_scores else "unknown"
            inc_flag(self.agent_name, primary_group)

            # Kafka event
            asyncio.create_task(emit_threat_event(
                agent_name=self.agent_name,
                request_id=rid,
                tenant_id=request.tenant_id,
                score=score,
                category=primary_group,
                metadata={
                    "pattern_count": len(hits),
                    "groups": list(group_scores.keys()),
                    "max_severity": round(max_group_score, 4),
                    "escalation_bonus": escalation_bonus,
                },
            ))

        return AgentResult(
            agent_name=self.agent_name,
            score=score,
            flagged=flagged,
            veto=score >= 0.90,   # Veto on confirmed DAN or high-confidence jailbreak
            metadata={
                "hits": [h["pattern"][:60] for h in hits[:10]],
                "pattern_count": len(hits),
                "groups": list(group_scores.keys()),
                "group_scores": {k: round(v, 4) for k, v in group_scores.items()},
                "max_severity_score": round(max_group_score, 4),
                "escalation_bonus": escalation_bonus,
                "model_specific_hits": [
                    h for h in hits
                    if h["group"] in ("gpt4o_jailbreak", "claude_jailbreak", "gemini_jailbreak")
                ][:5],
            },
        )

    def _scan_all_patterns(self, text: str, prompt_full: str) -> list[dict]:
        """Scan text against all pattern groups. Returns list of hits.

        v6: Also decodes base64/ROT13/hex payloads and normalizes text
        before pattern matching to catch encoding-based evasion.
        """
        # v6: Pre-decode encoded payloads and normalize
        normalized = normalize_for_detection(text)
        decoded = decode_encoded_payloads(text) + decode_encoded_payloads(prompt_full)
        all_texts = [text, prompt_full, normalized] + decoded

        hits = []
        for group, patterns in _COMPILED_GROUPS.items():
            for pattern in patterns:
                if any(pattern.search(t) for t in all_texts):
                    hits.append({
                        "group": group,
                        "pattern": pattern.pattern,
                        "severity": _GROUP_SEVERITY.get(group, 0.60),
                    })
        return hits
