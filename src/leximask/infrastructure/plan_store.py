"""Plan serialisation and deserialisation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from leximask.application.planner import PlanResult
from leximask.domain.models import Match, PlannedDirectory, PlannedFile
from leximask.errors import ValidationError


PLAN_FORMAT = "leximask/plan/v1"


def serialise_plan(plan: PlanResult) -> dict[str, object]:
    return {
        "format": PLAN_FORMAT,
        "root_directory": str(plan.root_directory),
        "mapping_path": str(plan.mapping_path),
        "files": [
            {
                "source_relative_path": str(planned_file.source_relative_path),
                "target_relative_path": str(planned_file.target_relative_path),
                "source_digest": planned_file.source_digest,
                "transformed_digest": planned_file.transformed_digest,
                "transformed_text": planned_file.transformed_text,
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
            }
            for planned_file in plan.files
        ],
        "directories": [
            {
                "source_relative_path": str(directory.source_relative_path),
                "target_relative_path": str(directory.target_relative_path),
            }
            for directory in plan.directories
        ],
    }


def deserialise_plan(payload: dict[str, Any]) -> PlanResult:
    if payload.get("format") != PLAN_FORMAT:
        raise ValidationError("Unsupported plan format")

    files = tuple(
        PlannedFile(
            source_relative_path=Path(str(entry["source_relative_path"])),
            target_relative_path=Path(str(entry["target_relative_path"])),
            source_digest=str(entry["source_digest"]),
            transformed_digest=str(entry["transformed_digest"]),
            source_text="",
            transformed_text=str(entry["transformed_text"]),
            matches=tuple(
                Match(
                    start=int(match["replacement_start"]),
                    end=int(match["replacement_end"]),
                    source=str(match["source"]),
                    original_text=str(match["original_text"]),
                    replacement_text=str(match["replacement_text"]),
                )
                for match in entry["matches"]
            ),
        )
        for entry in payload["files"]
    )
    directories = tuple(
        PlannedDirectory(
            source_relative_path=Path(str(entry["source_relative_path"])),
            target_relative_path=Path(str(entry["target_relative_path"])),
        )
        for entry in payload["directories"]
    )
    return PlanResult(
        root_directory=Path(str(payload["root_directory"])),
        mapping_path=Path(str(payload["mapping_path"])),
        files=files,
        directories=directories,
    )
