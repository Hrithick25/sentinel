"""
SENTINEL Eval — Shared Normalizer
====================================
Canonical text normalization for detection agents and eval benchmark.
Strips adversarial obfuscation so pattern matchers see clean ASCII text.

Pipeline: NFKC → strip invisible → homoglyph map → leetspeak → collapse ws → lower
"""
from __future__ import annotations

import base64 as b64
import codecs
import re
import unicodedata

# ── Homoglyph map (Cyrillic/Greek/math bold/fullwidth → Latin) ────────────────
_HOMOGLYPH_MAP: dict[str, str] = {
    '\u0410': 'A', '\u0412': 'B', '\u0421': 'C', '\u0415': 'E',
    '\u041d': 'H', '\u041a': 'K', '\u041c': 'M', '\u041e': 'O',
    '\u0420': 'P', '\u0422': 'T', '\u0425': 'X',
    '\u0430': 'a', '\u0435': 'e', '\u043e': 'o', '\u0440': 'p',
    '\u0441': 'c', '\u0443': 'y', '\u0445': 'x', '\u0456': 'i',
    '\u0391': 'A', '\u0392': 'B', '\u0395': 'E', '\u0397': 'H',
    '\u0399': 'I', '\u039A': 'K', '\u039C': 'M', '\u039D': 'N',
    '\u039F': 'O', '\u03A1': 'P', '\u03A4': 'T', '\u03A7': 'X',
    '\u03B1': 'a', '\u03B5': 'e', '\u03BF': 'o', '\u03B9': 'i',
    '\u200B': '', '\u200C': '', '\u200D': '', '\uFEFF': '',
    '\u00AD': '', '\u2060': '', '\u180E': '',
}
# Add mathematical bold (U+1D5D4..U+1D607) and fullwidth (U+FF21..U+FF5A)
for i in range(26):
    _HOMOGLYPH_MAP[chr(0x1D5D4 + i)] = chr(ord('A') + i)
    _HOMOGLYPH_MAP[chr(0x1D5EE + i)] = chr(ord('a') + i)
    _HOMOGLYPH_MAP[chr(0xFF21 + i)] = chr(ord('A') + i)
    _HOMOGLYPH_MAP[chr(0xFF41 + i)] = chr(ord('a') + i)

# ── Leetspeak map ─────────────────────────────────────────────────────────────
_LEET_MAP = {'1': 'i', '!': 'i', '0': 'o', '3': 'e', '4': 'a',
             '@': 'a', '5': 's', '$': 's', '7': 't', '8': 'b', '9': 'g'}
_LEET_TRIGGER = re.compile(r'[0-9@$!]{2,}')
_MULTI_SPACE = re.compile(r'\s+')

_ATTACK_KEYWORDS = [
    'ignore', 'instructions', 'pretend', 'jailbreak', 'bypass',
    'system', 'prompt', 'override', 'restrict', 'hack', 'disregard',
]


def normalize_for_detection(text: str) -> str:
    """
    Full normalization pipeline — strips adversarial obfuscation.
    Output is suitable for regex matching but NOT for display (lossy).
    """
    if not text:
        return text

    text = unicodedata.normalize("NFKC", text)

    result = []
    for ch in text:
        if unicodedata.category(ch) == 'Cf':
            continue
        mapped = _HOMOGLYPH_MAP.get(ch)
        result.append(mapped if mapped is not None else ch)
    text = ''.join(result)

    if _LEET_TRIGGER.search(text):
        text = ''.join(_LEET_MAP.get(ch, ch) for ch in text)

    text = _MULTI_SPACE.sub(' ', text).strip()
    return text.lower()


def decode_encoded_payloads(text: str) -> list[str]:
    """
    Detect and decode base64, ROT13, and hex escape sequences.
    Returns list of decoded strings (may be empty).
    """
    decoded = []

    # Base64
    for match in re.finditer(r'(?:^|[\s\'"=:])([A-Za-z0-9+/]{16,}={0,2})(?:[\s\'",:;]|$)', text):
        try:
            raw = b64.b64decode(match.group(1)).decode("utf-8", errors="ignore")
            if sum(c.isprintable() for c in raw) / max(len(raw), 1) > 0.5 and len(raw) > 4:
                decoded.append(raw)
        except Exception:
            pass

    # ROT13 — only if decoded version has more attack keyword hits
    try:
        rot = codecs.decode(text, 'rot_13')
        orig_hits = sum(1 for kw in _ATTACK_KEYWORDS if kw in text.lower())
        rot_hits = sum(1 for kw in _ATTACK_KEYWORDS if kw in rot.lower())
        if rot_hits > orig_hits and rot_hits >= 2:
            decoded.append(rot)
    except Exception:
        pass

    # Hex escape sequences
    for match in re.finditer(r'(?:\\x[0-9a-fA-F]{2}){3,}', text):
        try:
            raw = bytes(int(h, 16) for h in re.findall(r'\\x([0-9a-fA-F]{2})', match.group())).decode('utf-8', errors='ignore')
            if len(raw) > 2:
                decoded.append(raw)
        except Exception:
            pass

    return decoded
