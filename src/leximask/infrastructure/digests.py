"""Deterministic digest helpers."""

from __future__ import annotations

import hashlib


def sha256_text(value: str) -> str:
    """Return the SHA-256 hex digest for a UTF-8 text value."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
