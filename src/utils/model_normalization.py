"""Utilities for standardizing model names across sources."""

from __future__ import annotations

import re
from typing import Any

DATE_PATTERNS = [
    r"(?<!\d)20\d{2}[-_/]\d{2}[-_/]\d{2}(?!\d)",
    r"(?<!\d)20\d{6}(?!\d)",
]

TOKEN_MAP = {
    "gpt": "GPT",
    "o1": "O1",
    "o3": "O3",
    "o4": "O4",
    "claude": "Claude",
    "opus": "Opus",
    "sonnet": "Sonnet",
    "haiku": "Haiku",
    "gemini": "Gemini",
    "deepseek": "DeepSeek",
    "qwen": "Qwen",
    "llama": "Llama",
    "mistral": "Mistral",
    "mixtral": "Mixtral",
    "grok": "Grok",
    "pro": "Pro",
    "mini": "Mini",
    "nano": "Nano",
    "turbo": "Turbo",
    "preview": "Preview",
    "thinking": "Thinking",
    "refine": "Refine",
    "high": "High",
    "medium": "Medium",
    "low": "Low",
    "xhigh": "X-High",
    "bedrock": "Bedrock",
    "instruct": "Instruct",
    "codex": "Codex",
    "flash": "Flash",
    "ultra": "Ultra",
    "max": "Max",
    "beta": "Beta",
    "alpha": "Alpha",
    "k2": "K2",
    "k2.5": "K2.5",
}

VARIANT_TOKENS = {
    "pro",
    "mini",
    "nano",
    "turbo",
    "preview",
    "thinking",
    "refine",
    "high",
    "medium",
    "low",
    "xhigh",
    "bedrock",
    "instruct",
    "codex",
    "flash",
    "ultra",
    "max",
    "beta",
    "alpha",
    "x",
}


def normalize_model_name(raw: str | None, provider: str | None = None) -> dict[str, Any]:
    """Normalize model names for consistent display and grouping."""
    if not raw:
        return {
            "display": raw or "Unknown",
            "group": "unknown",
            "family": None,
            "variant": None,
        }

    cleaned = _strip_dates(raw)
    cleaned = re.sub(r"[()]", " ", cleaned)
    cleaned = cleaned.replace("_", " ").replace("/", " ")
    cleaned = re.sub(r"-+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    lower = cleaned.lower()
    tokens = lower.split()

    if _looks_like_claude(tokens):
        return _normalize_claude(tokens)
    if "gpt" in tokens:
        return _normalize_gpt(tokens)
    if _looks_like_o_series(tokens):
        return _normalize_o_series(tokens)
    if "gemini" in tokens:
        return _normalize_gemini(tokens)
    if "deepseek" in tokens:
        return _normalize_deepseek(tokens)
    if any(t == "qwen" or t.startswith("qwen") for t in tokens):
        return _normalize_qwen(tokens)
    if "kimi" in tokens or any(t.startswith("kimi") for t in tokens):
        return _normalize_kimi(tokens)
    if "llama" in tokens:
        return _normalize_llama(tokens)
    if "mistral" in tokens or "mixtral" in tokens:
        return _normalize_mistral(tokens)
    if "grok" in tokens:
        return _normalize_grok(tokens)

    display = _title_case_tokens(tokens)
    return _finalize(display, None, None)


def _strip_dates(text: str) -> str:
    result = text
    for pattern in DATE_PATTERNS:
        result = re.sub(pattern, " ", result)
    return result


def _looks_like_claude(tokens: list[str]) -> bool:
    return "claude" in tokens or any(t in tokens for t in ("opus", "sonnet", "haiku"))


def _looks_like_o_series(tokens: list[str]) -> bool:
    return any(re.fullmatch(r"o\d+", t) for t in tokens)


def _normalize_gpt(tokens: list[str]) -> dict[str, Any]:
    version, used = _extract_version(tokens, anchor="gpt", allow_letter=True)
    if version == "4o":
        canonical = "GPT-4o"
    elif version:
        canonical = f"GPT-{version}"
    else:
        canonical = "GPT"

    variants = _extract_variants(tokens, used | {"gpt"})
    return _finalize(canonical, variants, "GPT")


def _normalize_o_series(tokens: list[str]) -> dict[str, Any]:
    series_token = next((t for t in tokens if re.fullmatch(r"o\d+", t)), None)
    canonical = series_token.upper() if series_token else "O-Series"
    variants = _extract_variants(tokens, {series_token} if series_token else set())
    return _finalize(canonical, variants, canonical)


def _normalize_claude(tokens: list[str]) -> dict[str, Any]:
    family = next((t for t in tokens if t in ("opus", "sonnet", "haiku")), None)
    version, used = _extract_version(tokens, allow_letter=False)
    canonical_parts = ["Claude"]
    if family:
        canonical_parts.append(TOKEN_MAP.get(family, family.title()))
    if version:
        canonical_parts.append(version)
    canonical = " ".join(canonical_parts)
    used_tokens = used | {"claude"}
    if family:
        used_tokens.add(family)
    variants = _extract_variants(tokens, used_tokens)
    return _finalize(canonical, variants, canonical)


def _normalize_gemini(tokens: list[str]) -> dict[str, Any]:
    version, used = _extract_version(tokens, anchor="gemini")
    tier = next((t for t in tokens if t in ("pro", "flash", "ultra")), None)
    canonical_parts = ["Gemini"]
    if version:
        canonical_parts.append(version)
    if tier:
        canonical_parts.append(TOKEN_MAP.get(tier, tier.title()))
        used.add(tier)
    canonical = " ".join(canonical_parts)
    variants = _extract_variants(tokens, used | {"gemini"})
    return _finalize(canonical, variants, canonical)


def _normalize_deepseek(tokens: list[str]) -> dict[str, Any]:
    version = next((t for t in tokens if re.fullmatch(r"r\d+", t)), None)
    canonical = f"DeepSeek {version.upper()}" if version else "DeepSeek"
    used = {"deepseek"}
    if version:
        used.add(version)
    variants = _extract_variants(tokens, used)
    return _finalize(canonical, variants, canonical)


def _normalize_qwen(tokens: list[str]) -> dict[str, Any]:
    used: set[str] = set()
    anchor = "qwen"
    inline = next((t for t in tokens if t.startswith("qwen") and t != "qwen"), None)
    if inline and re.fullmatch(r"qwen\d+(\.\d+)?", inline):
        anchor = "qwen"
        version = inline.replace("qwen", "", 1)
        used.add(inline)
    else:
        version, extracted = _extract_version(tokens, anchor="qwen")
        used |= extracted
    size = next((t for t in tokens if re.fullmatch(r"\d+b", t)), None)
    canonical_parts = ["Qwen"]
    if version:
        canonical_parts.append(version)
    if size:
        canonical_parts.append(size.upper())
        used.add(size)
    canonical = " ".join(canonical_parts)
    variants = _extract_variants(tokens, used | {"qwen"})
    return _finalize(canonical, variants, canonical)


def _normalize_kimi(tokens: list[str]) -> dict[str, Any]:
    used: set[str] = set()
    if "kimi" in tokens:
        used.add("kimi")
    inline = next((t for t in tokens if t.startswith("kimi") and t != "kimi"), None)
    version = None
    if inline:
        suffix = inline.replace("kimi", "", 1).strip("-_ ")
        if suffix:
            version = suffix.upper()
            used.add(inline)
    if version is None:
        version = next((t.upper() for t in tokens if re.fullmatch(r"k\d+(\.\d+)?", t)), None)
        if version:
            used.add(version.lower())
    canonical = "Kimi"
    if version:
        canonical = f"Kimi {version}"
    variants = _extract_variants(tokens, used | {"kimi"})
    return _finalize(canonical, variants, canonical)


def _normalize_llama(tokens: list[str]) -> dict[str, Any]:
    version, used = _extract_version(tokens, anchor="llama", allow_letter=False)
    flavor = next((t for t in tokens if t in ("maverick", "scout")), None)
    canonical_parts = ["Llama"]
    if version:
        canonical_parts.append(version)
    if flavor:
        canonical_parts.append(flavor.title())
        used.add(flavor)
    canonical = " ".join(canonical_parts)
    variants = _extract_variants(tokens, used | {"llama"})
    return _finalize(canonical, variants, canonical)


def _normalize_mistral(tokens: list[str]) -> dict[str, Any]:
    brand = "Mixtral" if "mixtral" in tokens else "Mistral"
    used = {"mixtral", "mistral"}
    variants = _extract_variants(tokens, used)
    return _finalize(brand, variants, brand)


def _normalize_grok(tokens: list[str]) -> dict[str, Any]:
    version, used = _extract_version(tokens, anchor="grok")
    canonical = f"Grok {version}" if version else "Grok"
    variants = _extract_variants(tokens, used | {"grok"})
    return _finalize(canonical, variants, canonical)


def _extract_version(tokens: list[str], anchor: str | None = None, allow_letter: bool = True) -> tuple[str | None, set[str]]:
    used: set[str] = set()
    start_idx = tokens.index(anchor) + 1 if anchor in tokens else 0
    candidates = tokens[start_idx:]

    # Prefer tokens like 4o, 4.5, 3.7
    for token in candidates:
        if allow_letter and re.fullmatch(r"\d+[a-z]", token):
            used.add(token)
            return token, used
        if re.fullmatch(r"\d+\.\d+", token):
            used.add(token)
            return token, used

    # Combine two digit tokens into decimal (e.g., 4 5 -> 4.5)
    for i in range(len(candidates) - 1):
        if (
            candidates[i].isdigit()
            and candidates[i + 1].isdigit()
            and len(candidates[i]) <= 2
            and len(candidates[i + 1]) <= 2
        ):
            version = f"{candidates[i]}.{candidates[i + 1]}"
            used.update({candidates[i], candidates[i + 1]})
            return version, used

    # Fallback single digit
    for token in candidates:
        if token.isdigit():
            used.add(token)
            return token, used

    return None, used


def _extract_variants(tokens: list[str], used: set[str]) -> list[str]:
    variants: list[str] = []
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token in used:
            i += 1
            continue
        if token == "x" and i + 1 < len(tokens) and tokens[i + 1] == "high":
            variants.append("X-High")
            i += 2
            continue
        if token in VARIANT_TOKENS or re.fullmatch(r"\d+k", token) or re.fullmatch(r"\d+b", token):
            variants.append(_title_case_token(token))
        i += 1
    return variants


def _title_case_tokens(tokens: list[str]) -> str:
    return " ".join(_title_case_token(t) for t in tokens)


def _title_case_token(token: str) -> str:
    return TOKEN_MAP.get(token, token.upper() if re.fullmatch(r"\d+k|\d+b", token) else token.title())


def _finalize(canonical: str, variants: list[str] | None, family: str | None) -> dict[str, Any]:
    variant = " ".join(variants) if variants else None
    display = f"{canonical} {variant}".strip() if variant else canonical
    group = re.sub(r"[^a-z0-9]+", "-", canonical.lower()).strip("-")
    return {
        "display": display,
        "group": group,
        "family": family,
        "variant": variant,
    }
