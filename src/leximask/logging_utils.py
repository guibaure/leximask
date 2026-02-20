"""Logging configuration helpers."""

from __future__ import annotations

import logging

from leximask.errors import ValidationError


def configure_logging(level_name: str) -> None:
    level = _resolve_log_level(level_name)
    logging.basicConfig(
        level=level,
        format="%(levelname)s %(name)s %(message)s",
        force=True,
    )


def _resolve_log_level(level_name: str) -> int:
    resolved_level = getattr(logging, level_name.upper(), None)
    if not isinstance(resolved_level, int):
        raise ValidationError(f"Unsupported log level: {level_name}")
    return resolved_level
