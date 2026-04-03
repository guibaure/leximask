"""Apply and reverse workflows."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from leximask.application.planner import PlanResult
from leximask.errors import ConflictError, MetadataError
from leximask.infrastructure.filesystem import (
    copy_preserved_entries,
    create_staging_directory,
    replace_directory_atomically,
    write_text_file,
)
from leximask.infrastructure.sidecar import (
    sidecar_path,
    sidecar_root,
    state_directory,
    state_path,
    write_json_file,
    load_json_file,
)


def apply_plan(plan: PlanResult) -> Path:
    root_directory = plan.root_directory
    staging_directory = create_staging_directory(root_directory, "apply")
    staging_root = staging_directory / root_directory.name
    try:
        _materialise_transformed_tree(staging_root, plan)
        replace_directory_atomically(root_directory, staging_root, "apply")
    except Exception:
        if staging_directory.exists():
            shutil.rmtree(staging_directory, ignore_errors=True)
        raise
    return root_directory


def reverse_root(root_directory: Path) -> Path:
    manifest = load_json_file(state_path(root_directory))
    if manifest.get("format") != "leximask/state/v1":
        raise MetadataError("Unsupported state file format")

    staging_directory = create_staging_directory(root_directory, "reverse")
    staging_root = staging_directory / root_directory.name
    try:
        _materialise_restored_tree(root_directory, staging_root, manifest)
        replace_directory_atomically(root_directory, staging_root, "reverse")
    except Exception:
        if staging_directory.exists():
            shutil.rmtree(staging_directory, ignore_errors=True)
        raise
    return root_directory


def _materialise_transformed_tree(staging_root: Path, plan: PlanResult) -> None:
    staging_root.mkdir(parents=True, exist_ok=False)
    copy_preserved_entries(plan.root_directory, staging_root)

    for planned_file in plan.files:
        write_text_file(
            staging_root / planned_file.target_relative_path, planned_file.transformed_text
        )

    sidecar_directory = sidecar_root(staging_root)
    for planned_file in plan.files:
        write_json_file(
            sidecar_path(sidecar_directory, planned_file.target_relative_path),
            {
                "format": "leximask/sidecar/v1",
                "original_relative_path": str(planned_file.source_relative_path),
                "transformed_relative_path": str(planned_file.target_relative_path),
                "matches": [
                    {
                        "replacement_start": match.start,
                        "replacement_end": match.end,
                        "source": match.source,
                        "original_text": match.original_text,
                        "replacement_text": match.replacement_text,
                    }
                    for match in planned_file.matches
                ],
            },
        )

    write_json_file(
        state_path(staging_root),
        {
            "format": "leximask/state/v1",
            "mapping_path": str(plan.mapping_path.resolve()),
            "root_name": plan.root_directory.name,
            "directories": [
                {
                    "original_relative_path": str(directory.source_relative_path),
                    "transformed_relative_path": str(directory.target_relative_path),
                }
                for directory in plan.directories
            ],
            "files": [
                {
                    "original_relative_path": str(planned_file.source_relative_path),
                    "transformed_relative_path": str(planned_file.target_relative_path),
                }
                for planned_file in plan.files
            ],
        },
    )


def _materialise_restored_tree(
    transformed_root: Path, staging_root: Path, manifest: dict[str, Any]
) -> None:
    staging_root.mkdir(parents=True, exist_ok=False)
    copy_preserved_entries(transformed_root, staging_root)

    sidecars_base = sidecar_root(transformed_root)
    for file_entry in manifest.get("files", []):
        transformed_relative_path = Path(file_entry["transformed_relative_path"])
        original_relative_path = Path(file_entry["original_relative_path"])
        transformed_text = (transformed_root / transformed_relative_path).read_text(
            encoding="utf-8"
        )
        sidecar = load_json_file(sidecar_path(sidecars_base, transformed_relative_path))
        if sidecar.get("format") != "leximask/sidecar/v1":
            raise MetadataError(
                f"Unsupported sidecar format for {transformed_relative_path}"
            )
        restored_text = _restore_text(transformed_text, sidecar)
        write_text_file(staging_root / original_relative_path, restored_text)


def _restore_text(transformed_text: str, sidecar: dict[str, Any]) -> str:
    fragments: list[str] = []
    cursor = 0
    for match in sidecar.get("matches", []):
        start = int(match["replacement_start"])
        end = int(match["replacement_end"])
        replacement_text = str(match["replacement_text"])
        if start < cursor or transformed_text[start:end] != replacement_text:
            raise MetadataError("Sidecar does not match transformed file content")
        fragments.append(transformed_text[cursor:start])
        fragments.append(str(match["original_text"]))
        cursor = end
    fragments.append(transformed_text[cursor:])
    return "".join(fragments)
