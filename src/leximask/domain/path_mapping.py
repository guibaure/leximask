"""Deterministic path-rewrite helpers."""

from __future__ import annotations

from pathlib import Path, PurePath
from typing import Mapping, TypeVar, cast

from leximask.domain.models import PlannedDirectory

PathT = TypeVar("PathT", bound=PurePath)


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
    relative_path: PathT, directory_mapping: Mapping[PathT, PathT]
) -> PathT:
    rewritten_parent = rewrite_directory_path(relative_path.parent, directory_mapping)
    return cast(PathT, rewritten_parent / relative_path.name)


def rewrite_directory_path(path: PathT, directory_mapping: Mapping[PathT, PathT]) -> PathT:
    current_directory = cast(PathT, type(path)("."))
    if path == current_directory:
        return current_directory
    for candidate in (path, *path.parents):
        if candidate == current_directory:
            continue
        rewritten_prefix = directory_mapping.get(candidate)
        if rewritten_prefix is None:
            continue
        suffix_parts = path.parts[len(candidate.parts) :]
        if not suffix_parts:
            return rewritten_prefix
        return cast(PathT, rewritten_prefix.joinpath(*suffix_parts))
    return path
