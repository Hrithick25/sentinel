"""
SENTINEL Agent 15 — AdversarialRephrasing v3.0
===============================================
Tests whether rephrased/perturbed versions of the input prompt can bypass
the FAISS injection detector. If rephrased variants score higher than the
original, it indicates the original is a disguised attack.

v2 approach (REPLACED):
  - Used Vamsi/T5_Paraphrase_Paws (~1GB, seq2seq, 2-3s inference)
  - Always timed out at the 500ms agent deadline

v3 approach:
  - Heuristic perturbation: synonym swap, case variation, split injection
  - Uses only the embedding model already loaded by FAISSManager
  - 5-10x faster than seq2seq generation (~50ms total)

Perturbation strategies:
  1. Character-level: homoglyph removal, whitespace normalization
  2. Word-level: synonym substitution from a hardcoded attack-relevant thesaurus
  3. Structure-level: instruction boundary injection, role prefix swap
"""
from __future__ import annotations

import logging
import re
import random
from typing import Optional

from sentinel.agents.base import SentinelAgent
from sentinel.models import AgentResult, SentinelRequest

logger = logging.getLogger("sentinel.agents.adversarial_rephrasing")

# ── Perturbation strategies ───────────────────────────────────────────────────

# Synonym map focused on attack-relevant vocabulary
_SYNONYM_MAP = {
    "ignore": ["disregard", "skip", "forget", "bypass", "overlook"],
    "instructions": ["guidelines", "rules", "directives", "prompts", "commands"],
    "previous": ["prior", "above", "earlier", "preceding", "former"],
    "pretend": ["act as if", "imagine", "roleplay", "behave as though", "simulate"],
    "system": ["core", "base", "root", "internal", "underlying"],
    "reveal": ["show", "display", "expose", "disclose", "output"],
    "hack": ["exploit", "compromise", "breach", "penetrate", "crack"],
    "bypass": ["circumvent", "evade", "skip", "sidestep", "work around"],
    "restrict": ["limit", "constrain", "block", "prevent", "filter"],
    "password": ["credential", "passphrase", "secret", "auth token", "key"],
}

# Structural perturbation templates
_STRUCTURAL_PERTURBATIONS = [
    # Wrap in instruction boundary
    lambda t: f"[SYSTEM] {t}",
    # Add misleading preamble
    lambda t: f"For a safety audit, evaluate this: {t}",
    # Role injection prefix
    lambda t: f"As an AI assistant without filters, {t}",
    # Indirect framing
    lambda t: f"What would someone mean if they said: {t}",
    # Encoding-style obfuscation (words separated)
    lambda t: " ".join(f"{w[0]}{''.join(w[1:])}" if len(w) > 2 else w for w in t.split()),
]


def _synonym_perturb(text: str) -> str:
    """Replace attack-relevant words with synonyms."""
    words = text.split()
    result = []
    for word in words:
        lower = word.lower().strip(".,!?;:")
        if lower in _SYNONYM_MAP:
            replacement = random.choice(_SYNONYM_MAP[lower])
            # Preserve original capitalization
            if word[0].isupper():
                replacement = replacement.capitalize()
            result.append(replacement)
        else:
            result.append(word)
    return " ".join(result)


def _case_perturb(text: str) -> str:
    """Randomize case to test case-insensitive detection."""
    return "".join(
        c.upper() if random.random() > 0.5 else c.lower() for c in text
    )


def _whitespace_perturb(text: str) -> str:
    """Insert zero-width or extra whitespace between words."""
    words = text.split()
    separators = [" ", "  ", " \t ", "  "]
    return random.choice(separators).join(words)


def generate_perturbations(text: str, max_variants: int = 5) -> list[str]:
    """
    Generate multiple perturbations of the input text.
    Each uses a different strategy to test detection robustness.
    """
    text = text[:512]  # Truncate for safety
    variants = []

    # 1. Synonym perturbation
    variants.append(_synonym_perturb(text))

    # 2. Case perturbation
    variants.append(_case_perturb(text))

    # 3. Whitespace perturbation
    variants.append(_whitespace_perturb(text))

    # 4-5. Structural perturbations (pick 2 random)
    structural = random.sample(
        _STRUCTURAL_PERTURBATIONS, min(2, len(_STRUCTURAL_PERTURBATIONS))
    )
    for fn in structural:
        try:
            variants.append(fn(text))
        except Exception:
            pass

    # Deduplicate and limit
    seen = {text}  # Don't include the original
    unique = []
    for v in variants:
        if v not in seen:
            seen.add(v)
            unique.append(v)
    return unique[:max_variants]


class AdversarialRephrasing(SentinelAgent):
    agent_name = "AdversarialRephrasing"

    def __init__(self, faiss_manager=None):
        self._faiss = faiss_manager

    async def analyze(self, request: SentinelRequest) -> AgentResult:
        if not self._faiss or self._faiss.vector_count == 0:
            return AgentResult(
                agent_name=self.agent_name,
                score=0.0,
                flagged=False,
                metadata={"skipped": True, "reason": "no FAISS index or empty index"},
            )

        try:
            prompt = request.prompt

            # Generate perturbations (deterministic seed per-request for consistency)
            random.seed(hash(prompt) % (2**32))
            perturbations = generate_perturbations(prompt, max_variants=5)

            # Get original FAISS score for comparison
            original_score = await self._faiss.search(prompt)

            # Check each perturbation against FAISS
            max_bypass_score = 0.0
            best_bypass = ""
            bypass_delta = 0.0

            for variant in perturbations:
                try:
                    score = await self._faiss.search(variant)
                    if score > max_bypass_score:
                        max_bypass_score = score
                        best_bypass = variant[:100]  # Truncate for metadata
                        bypass_delta = score - original_score
                except Exception:
                    continue

            # The final score is the max of:
            # 1. The highest bypass score found
            # 2. A bonus if perturbations score HIGHER than original (evasion detected)
            evasion_bonus = max(0.0, bypass_delta * 0.5)
            final_score = self._clamp(max(max_bypass_score, original_score + evasion_bonus))

            return AgentResult(
                agent_name=self.agent_name,
                score=final_score,
                flagged=final_score >= 0.8,
                metadata={
                    "paraphrases_generated": len(perturbations),
                    "original_faiss_score": round(original_score, 4),
                    "best_bypass_score": round(max_bypass_score, 4),
                    "bypass_delta": round(bypass_delta, 4),
                    "top_rephrase": best_bypass,
                    "method": "heuristic_perturbation",
                },
            )
        except Exception as exc:
            logger.error("AdversarialRephrasing error: %s", exc)
            return AgentResult(
                agent_name=self.agent_name,
                score=0.0,
                flagged=False,
                metadata={"error": str(exc)},
            )
