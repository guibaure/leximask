"""Planning workflow."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from leximask.domain.matcher import rewrite_text
from leximask.domain.models import MappingRule, PlannedDirectory, PlannedFile
from leximask.errors import ConflictError
from leximask.infrastructure.filesystem import DiscoveredFile, discover_supported_files


@dataclass(frozen=True, slots=True)
class PlanResult:
    root_directory: Path
    mapping_path: Path
    files: tuple[PlannedFile, ...]
    directories: tuple[PlannedDirectory, ...]


def build_plan(root_directory: Path, mapping_path: Path, rules: tuple[MappingRule, ...]) -> PlanResult:
    discovered_files = discover_supported_files(root_directory)
    planned_files = tuple(_plan_files(discovered_files, root_directory, rules))
    planned_directories = tuple(_plan_directories(discovered_files, rules))
    _validate_path_collisions(planned_files, planned_directories)
    return PlanResult(
        root_directory=root_directory,
        mapping_path=mapping_path,
        files=planned_files,
        directories=planned_directories,
    )


def _plan_files(
    discovered_files: tuple[DiscoveredFile, ...],
    root_directory: Path,
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
                source_text=source_text,
                transformed_text=transformed_text,
                matches=matches,
            )
        )
    return planned_files


def _plan_directories(
    discovered_files: tuple[DiscoveredFile, ...], rules: tuple[MappingRule, ...]
) -> list[PlannedDirectory]:
    directory_paths: set[Path] = {Path(".")}
    for discovered_file in discovered_files:
        directory_paths.update(discovered_file.relative_path.parents)

    planned_directories: list[PlannedDirectory] = []
    for source_relative_path in sorted(
        (path for path in directory_paths if path != Path(".")), key=lambda path: len(path.parts)
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
    planned_files: tuple[PlannedFile, ...], planned_directories: tuple[PlannedDirectory, ...]
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
