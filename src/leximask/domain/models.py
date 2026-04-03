"""Typed domain models."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class MappingRule:
    """Single lexical replacement rule."""

    source: str
    replacement: str


@dataclass(frozen=True, slots=True)
class Match:
    """Single forward match within a text value."""

    start: int
    end: int
    source: str
    original_text: str
    replacement_text: str


@dataclass(frozen=True, slots=True)
class PlannedFile:
    """Planned file rewrite."""

    source_relative_path: Path
    target_relative_path: Path
    source_text: str
    transformed_text: str
    matches: tuple[Match, ...]


@dataclass(frozen=True, slots=True)
class PlannedDirectory:
    """Directory rename plan."""

    source_relative_path: Path
    target_relative_path: Path
