"""Plan, state, and sidecar persistence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from leximask.errors import MetadataError


STATE_DIRECTORY_NAME = ".leximask"
PLAN_FILE_NAME = "plan.json"
STATE_FILE_NAME = "state.json"
SIDECAR_DIRECTORY_NAME = "sidecars"


def state_directory(root_directory: Path) -> Path:
    return root_directory / STATE_DIRECTORY_NAME


def plan_path(root_directory: Path) -> Path:
    return state_directory(root_directory) / PLAN_FILE_NAME


def state_path(root_directory: Path) -> Path:
    return state_directory(root_directory) / STATE_FILE_NAME


def sidecar_root(root_directory: Path) -> Path:
    return state_directory(root_directory) / SIDECAR_DIRECTORY_NAME


def load_json_file(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise MetadataError(f"Metadata file does not exist: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def write_json_file(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def sidecar_path(sidecar_directory: Path, relative_path: Path) -> Path:
    return sidecar_directory / relative_path.parent / f"{relative_path.name}.leximask.json"
