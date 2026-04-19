"""Planning workflow."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from leximask.domain.matcher import rewrite_text
from leximask.domain.models import MappingRule, PlannedDirectory, PlannedFile
from leximask.domain.path_mapping import build_directory_mapping, rewrite_directory_path, rewrite_file_relative_path
from leximask.errors import ConflictError
from leximask.infrastructure.filesystem import (
    DiscoveredFile,
    discover_passthrough_directories,
    discover_passthrough_files,
    discover_supported_directories,
    discover_supported_files,
)
from leximask.infrastructure.digests import sha256_text

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PlanResult:
    root_directory: Path
    mapping_path: Path
    files: tuple[PlannedFile, ...]
    directories: tuple[PlannedDirectory, ...]


def build_plan(root_directory: Path, mapping_path: Path, rules: tuple[MappingRule, ...]) -> PlanResult:
    LOGGER.info("Building plan for %s using mapping %s", root_directory, mapping_path)
    excluded_relative_paths = _build_excluded_relative_paths(root_directory, mapping_path)
    discovered_files = discover_supported_files(root_directory, excluded_relative_paths)
    discovered_directories = discover_supported_directories(root_directory)
    passthrough_files = discover_passthrough_files(root_directory, excluded_relative_paths)
    passthrough_directories = discover_passthrough_directories(root_directory)
    planned_files = tuple(_plan_files(discovered_files, rules))
    planned_directories = tuple(_plan_directories(discovered_files, discovered_directories, rules))
    _validate_path_collisions(
        planned_files,
        planned_directories,
        passthrough_files,
        passthrough_directories,
    )
    LOGGER.info(
        "Plan built with %d files and %d directories",
        len(planned_files),
        len(planned_directories),
    )
    return PlanResult(
        root_directory=root_directory,
        mapping_path=mapping_path,
        files=planned_files,
        directories=planned_directories,
    )


def _build_excluded_relative_paths(
    root_directory: Path, mapping_path: Path
) -> tuple[Path, ...]:
    try:
        return (mapping_path.resolve().relative_to(root_directory.resolve()),)
    except ValueError:
        return ()


def _plan_files(
    discovered_files: tuple[DiscoveredFile, ...],
    rules: tuple[MappingRule, ...],
) -> list[PlannedFile]:
    planned_files: list[PlannedFile] = []
    for discovered_file in discovered_files:
        source_text = discovered_file.absolute_path.read_text(encoding="utf-8")
        transformed_text, matches = rewrite_text(source_text, rules)
        target_relative_path = _rewrite_relative_path(discovered_file.relative_path, rules)
        planned_files.append(
            PlannedFile(
                source_relative_path=discovered_file.relative_path,
                target_relative_path=target_relative_path,
                source_digest=sha256_text(source_text),
                transformed_digest=sha256_text(transformed_text),
                source_text=source_text,
                transformed_text=transformed_text,
                matches=matches,
            )
        )
    return planned_files


def _plan_directories(
    discovered_files: tuple[DiscoveredFile, ...],
    discovered_directories: tuple[Path, ...],
    rules: tuple[MappingRule, ...],
) -> list[PlannedDirectory]:
    directory_paths: set[Path] = set(discovered_directories)
    for discovered_file in discovered_files:
        directory_paths.update(discovered_file.relative_path.parents)

    planned_directories: list[PlannedDirectory] = []
    for source_relative_path in sorted(
        (path for path in directory_paths if path != Path(".")),
        key=lambda path: (len(path.parts), path.parts),
    ):
        target_relative_path = _rewrite_relative_path(source_relative_path, rules)
        planned_directories.append(
            PlannedDirectory(
                source_relative_path=source_relative_path,
                target_relative_path=target_relative_path,
            )
        )
    return planned_directories


def _rewrite_relative_path(relative_path: Path, rules: tuple[MappingRule, ...]) -> Path:
    rewritten_parts: list[str] = []
    for part in relative_path.parts:
        rewritten_part, _ = rewrite_text(part, rules)
        rewritten_parts.append(rewritten_part)
    return Path(*rewritten_parts)


def _validate_path_collisions(
    planned_files: tuple[PlannedFile, ...],
    planned_directories: tuple[PlannedDirectory, ...],
    passthrough_files: tuple[Path, ...],
    passthrough_directories: tuple[Path, ...],
) -> None:
    file_targets: dict[Path, Path] = {}
    for planned_file in planned_files:
        existing_source = file_targets.get(planned_file.target_relative_path)
        if existing_source is not None and existing_source != planned_file.source_relative_path:
            raise ConflictError(
                "File path collision detected: "
                f"{existing_source} and {planned_file.source_relative_path} -> "
                f"{planned_file.target_relative_path}"
            )
        file_targets[planned_file.target_relative_path] = planned_file.source_relative_path

    directory_targets: dict[Path, Path] = {}
    for planned_directory in planned_directories:
        existing_source = directory_targets.get(planned_directory.target_relative_path)
        if (
            existing_source is not None
            and existing_source != planned_directory.source_relative_path
        ):
            raise ConflictError(
                "Directory path collision detected: "
                f"{existing_source} and {planned_directory.source_relative_path} -> "
                f"{planned_directory.target_relative_path}"
            )
        directory_targets[planned_directory.target_relative_path] = (
            planned_directory.source_relative_path
        )

    for target_file_path, source_file_path in file_targets.items():
        if target_file_path in directory_targets:
            raise ConflictError(
                "Target path would be both a file and a directory: "
                f"{source_file_path} -> {target_file_path}"
            )

    file_target_paths = set(file_targets)
    for target_directory_path, source_directory_path in directory_targets.items():
        if any(parent == target_directory_path for path in file_target_paths for parent in path.parents):
            continue
        if any(path.parent == target_directory_path for path in file_target_paths):
            continue
        if any(path == target_directory_path for path in file_target_paths):
            raise ConflictError(
                "Target path would be both a directory and a file: "
                f"{source_directory_path} -> {target_directory_path}"
            )

    passthrough_directory_mapping = build_directory_mapping(planned_directories, forward=True)
    passthrough_file_targets = _collect_passthrough_file_targets(
        passthrough_files,
        passthrough_directory_mapping,
    )
    passthrough_directory_targets = _collect_passthrough_directory_targets(
        passthrough_directories,
        passthrough_directory_mapping,
    )

    _validate_unique_targets(
        passthrough_file_targets,
        "Passthrough file target collision detected",
    )
    _validate_unique_targets(
        passthrough_directory_targets,
        "Passthrough directory target collision detected",
    )

    passthrough_file_targets_by_target = dict(passthrough_file_targets)
    passthrough_directory_targets_by_target = dict(passthrough_directory_targets)

    for target_file_path, source_file_path in file_targets.items():
        passthrough_file_source = passthrough_file_targets_by_target.get(target_file_path)
        if passthrough_file_source is not None:
            raise ConflictError(
                "Target file path collides with passthrough file: "
                f"{source_file_path} -> {target_file_path}, passthrough {passthrough_file_source}"
            )
        passthrough_directory_source = passthrough_directory_targets_by_target.get(target_file_path)
        if passthrough_directory_source is not None:
            raise ConflictError(
                "Target file path collides with passthrough directory: "
                f"{source_file_path} -> {target_file_path}, passthrough {passthrough_directory_source}"
            )

    for target_directory_path, source_directory_path in directory_targets.items():
        passthrough_file_source = passthrough_file_targets_by_target.get(target_directory_path)
        if passthrough_file_source is not None:
            raise ConflictError(
                "Target directory path collides with passthrough file: "
                f"{source_directory_path} -> {target_directory_path}, passthrough {passthrough_file_source}"
            )
        passthrough_directory_source = passthrough_directory_targets_by_target.get(target_directory_path)
        if passthrough_directory_source is not None:
            raise ConflictError(
                "Target directory path collides with passthrough directory: "
                f"{source_directory_path} -> {target_directory_path}, passthrough {passthrough_directory_source}"
            )


def _collect_passthrough_file_targets(
    passthrough_files: tuple[Path, ...],
    directory_mapping: dict[Path, Path],
) -> list[tuple[Path, Path]]:
    return [
        (rewrite_file_relative_path(path, directory_mapping), path)
        for path in passthrough_files
    ]


def _collect_passthrough_directory_targets(
    passthrough_directories: tuple[Path, ...],
    directory_mapping: dict[Path, Path],
) -> list[tuple[Path, Path]]:
    return [
        (rewrite_directory_path(path, directory_mapping), path)
        for path in passthrough_directories
    ]


def _validate_unique_targets(targets: list[tuple[Path, Path]], message: str) -> None:
    seen: dict[Path, Path] = {}
    for target_path, source_path in targets:
        existing_source = seen.get(target_path)
        if existing_source is not None and existing_source != source_path:
            raise ConflictError(
                f"{message}: {existing_source} and {source_path} -> {target_path}"
            )
        seen[target_path] = source_path
