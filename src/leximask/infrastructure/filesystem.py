"""Filesystem helpers."""

from __future__ import annotations

import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from leximask.errors import ValidationError

SUPPORTED_SUFFIXES = {
    ".py",
    ".ts",
    ".js",
    ".json",
    ".yaml",
    ".yml",
    ".md",
    ".txt",
    ".log",
    ".csv",
}
IGNORED_NAMES = {".git", ".hg", ".svn", ".leximask", "__pycache__"}
PRESERVED_DIRECTORY_NAMES = {".git", ".hg", ".svn", "__pycache__"}


@dataclass(frozen=True, slots=True)
class DiscoveredFile:
    relative_path: Path
    absolute_path: Path


def validate_root_directory(root_directory: Path) -> Path:
    resolved_root = root_directory.resolve()
    if not resolved_root.is_dir():
        raise ValidationError(f"Input directory does not exist: {resolved_root}")
    return resolved_root


def discover_supported_files(root_directory: Path) -> tuple[DiscoveredFile, ...]:
    discovered: list[DiscoveredFile] = []
    unsupported: list[Path] = []

    for current_root, directory_names, file_names in os.walk(root_directory):
        directory_names[:] = sorted(
            name for name in directory_names if name not in IGNORED_NAMES
        )
        current_root_path = Path(current_root)
        for file_name in sorted(file_names):
            absolute_path = current_root_path / file_name
            relative_path = absolute_path.relative_to(root_directory)
            if file_name.startswith(".leximask."):
                continue
            if absolute_path.suffix.lower() not in SUPPORTED_SUFFIXES:
                unsupported.append(relative_path)
                continue
            discovered.append(
                DiscoveredFile(relative_path=relative_path, absolute_path=absolute_path)
            )

    if unsupported:
        rendered = ", ".join(str(path) for path in unsupported[:10])
        suffix = "" if len(unsupported) <= 10 else f" and {len(unsupported) - 10} more"
        raise ValidationError(
            "Unsupported files were found outside ignored directories: "
            f"{rendered}{suffix}"
        )

    return tuple(discovered)


def copy_preserved_entries(source_root: Path, destination_root: Path) -> None:
    for entry in sorted(source_root.iterdir(), key=lambda path: path.name):
        if entry.name not in PRESERVED_DIRECTORY_NAMES:
            continue
        target_path = destination_root / entry.name
        if entry.is_dir():
            shutil.copytree(entry, target_path, symlinks=True)
        else:
            shutil.copy2(entry, target_path)


def write_text_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="")


def create_staging_directory(root_directory: Path, prefix: str) -> Path:
    parent = root_directory.parent
    staging_path = Path(
        tempfile.mkdtemp(prefix=f".leximask-{prefix}-", dir=str(parent))
    )
    return staging_path


def replace_directory_atomically(
    target_directory: Path, prepared_directory: Path, backup_prefix: str
) -> None:
    backup_directory = target_directory.parent / f".leximask-{backup_prefix}-backup"
    if backup_directory.exists():
        if backup_directory.is_dir():
            shutil.rmtree(backup_directory)
        else:
            backup_directory.unlink()

    try:
        target_directory.rename(backup_directory)
        prepared_directory.rename(target_directory)
        shutil.rmtree(backup_directory)
    except Exception:
        if target_directory.exists() and not backup_directory.exists():
            shutil.rmtree(target_directory)
        if backup_directory.exists() and not target_directory.exists():
            backup_directory.rename(target_directory)
        raise
