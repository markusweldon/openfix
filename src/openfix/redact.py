"""Best-effort credential redaction for anything that leaves the process (prompts, receipts, logs)."""

from __future__ import annotations

import re
from typing import Any

SECRET_KEYS = re.compile(
    r"^(password|passwd|secret|token|access_token|refresh_token|api_key|apikey|authorization|"
    r"private_key|client_secret|match|secret_value)$",
    re.IGNORECASE,
)

PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
        "[REDACTED PRIVATE KEY]",
    ),
    (re.compile(r"\b(?:sk-(?:proj-|ant-)?[A-Za-z0-9_-]{20,})\b"), "[REDACTED API KEY]"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"), "[REDACTED GITHUB TOKEN]"),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{40,}\b"), "[REDACTED GITHUB TOKEN]"),
    (re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"), "[REDACTED AWS KEY]"),
    (re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b"), "[REDACTED SLACK TOKEN]"),
    (re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"), "[REDACTED GOOGLE KEY]"),
    (re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"), "[REDACTED JWT]"),
]


def redact_text(text: str) -> str:
    for pattern, replacement in PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def redact(value: Any, _depth: int = 0) -> Any:
    if _depth > 50:
        return "[TRUNCATED]"
    if isinstance(value, dict):
        return {
            k: ("[REDACTED]" if isinstance(k, str) and SECRET_KEYS.match(k) else redact(v, _depth + 1))
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [redact(v, _depth + 1) for v in value]
    if isinstance(value, str):
        return redact_text(value)
    return value
