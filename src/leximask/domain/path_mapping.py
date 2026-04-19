"""Deterministic path-rewrite helpers."""

from __future__ import annotations

from pathlib import Path

from leximask.domain.models import PlannedDirectory


def build_directory_mapping(
    directories: tuple[PlannedDirectory, ...], forward: bool
) -> dict[Path, Path]:
    mapping: dict[Path, Path] = {}
    for directory in directories:
        source_path = directory.source_relative_path
        target_path = directory.target_relative_path
        mapping[source_path if forward else target_path] = (
            target_path if forward else source_path
        )
    return mapping


def rewrite_file_relative_path(
    relative_path: Path, directory_mapping: dict[Path, Path]
) -> Path:
    rewritten_parent = rewrite_directory_path(relative_path.parent, directory_mapping)
    return rewritten_parent / relative_path.name


def rewrite_directory_path(path: Path, directory_mapping: dict[Path, Path]) -> Path:
    if path in (Path(""), Path(".")):
        return Path(".")
    for candidate in (path, *path.parents):
        if candidate in (Path(""), Path(".")):
            continue
        rewritten_prefix = directory_mapping.get(candidate)
        if rewritten_prefix is None:
            continue
        suffix_parts = path.parts[len(candidate.parts) :]
        return rewritten_prefix.joinpath(*suffix_parts) if suffix_parts else rewritten_prefix
    return path
