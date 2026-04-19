"""Filesystem helpers."""

from __future__ import annotations

import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

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
    ".toml",
    ".ini",
    ".cfg",
    ".conf",
    ".properties",
}
SUPPORTED_FILE_NAMES = {
    "Dockerfile",
    "Makefile",
    ".gitignore",
    ".dockerignore",
    ".editorconfig",
    ".env",
    ".env.example",
    ".envrc",
}
IGNORED_NAMES = {".git", ".hg", ".svn", ".leximask", "__pycache__", ".codex"}
PRESERVED_DIRECTORY_NAMES = {".git", ".hg", ".svn", "__pycache__"}
IGNORED_BINARY_SUFFIXES = {
    ".mp3",
    ".wav",
    ".flac",
    ".m4a",
    ".ogg",
    ".mp4",
    ".mkv",
    ".avi",
    ".mov",
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".ico",
    ".pdf",
    ".docx",
    ".pptx",
    ".zip",
    ".tar",
    ".gz",
    ".bz2",
    ".xz",
    ".7z",
    ".sqlite",
    ".sqlite3",
    ".db",
}


@dataclass(frozen=True, slots=True)
class DiscoveredFile:
    relative_path: Path
    absolute_path: Path


def validate_root_directory(root_directory: Path) -> Path:
    resolved_root = root_directory.resolve()
    if not resolved_root.is_dir():
        raise ValidationError(f"Input directory does not exist: {resolved_root}")
    return resolved_root


def discover_supported_files(
    root_directory: Path, excluded_relative_paths: tuple[Path, ...] = ()
) -> tuple[DiscoveredFile, ...]:
    discovered: list[DiscoveredFile] = []
    unsupported: list[Path] = []
    excluded_paths = set(excluded_relative_paths)

    for current_root, directory_names, file_names in os.walk(root_directory):
        directory_names[:] = sorted(
            name for name in directory_names if name not in IGNORED_NAMES
        )
        current_root_path = Path(current_root)
        for file_name in sorted(file_names):
            absolute_path = current_root_path / file_name
            relative_path = absolute_path.relative_to(root_directory)
            if relative_path in excluded_paths:
                continue
            if file_name.startswith(".leximask."):
                continue
            if _should_ignore_file(absolute_path):
                continue
            if not _is_supported_text_file(absolute_path):
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


def discover_supported_directories(root_directory: Path) -> tuple[Path, ...]:
    discovered: list[Path] = []

    for current_root, directory_names, _file_names in os.walk(root_directory):
        directory_names[:] = sorted(
            name for name in directory_names if name not in IGNORED_NAMES
        )
        current_root_path = Path(current_root)
        if current_root_path == root_directory:
            continue
        discovered.append(current_root_path.relative_to(root_directory))

    return tuple(sorted(discovered, key=lambda path: (len(path.parts), path.parts)))


def discover_passthrough_directories(root_directory: Path) -> tuple[Path, ...]:
    discovered: list[Path] = []

    for current_root, directory_names, _file_names in os.walk(root_directory):
        current_root_path = Path(current_root)
        kept_directory_names: list[str] = []
        for directory_name in sorted(directory_names):
            source_path = current_root_path / directory_name
            relative_path = source_path.relative_to(root_directory)
            if directory_name in PRESERVED_DIRECTORY_NAMES or directory_name in IGNORED_NAMES:
                discovered.append(relative_path)
                continue
            kept_directory_names.append(directory_name)
        directory_names[:] = kept_directory_names

    return tuple(sorted(discovered, key=lambda path: (len(path.parts), path.parts)))


def discover_passthrough_files(
    root_directory: Path, excluded_relative_paths: tuple[Path, ...] = ()
) -> tuple[Path, ...]:
    discovered: list[Path] = []
    excluded_paths = set(excluded_relative_paths)

    for current_root, directory_names, file_names in os.walk(root_directory):
        current_root_path = Path(current_root)
        kept_directory_names: list[str] = []
        for directory_name in sorted(directory_names):
            if directory_name in PRESERVED_DIRECTORY_NAMES or directory_name in IGNORED_NAMES:
                continue
            kept_directory_names.append(directory_name)
        directory_names[:] = kept_directory_names

        for file_name in sorted(file_names):
            absolute_path = current_root_path / file_name
            relative_path = absolute_path.relative_to(root_directory)
            if relative_path in excluded_paths or _should_ignore_file(absolute_path):
                discovered.append(relative_path)

    return tuple(sorted(discovered, key=lambda path: path.parts))


def _is_supported_text_file(path: Path) -> bool:
    return path.name in SUPPORTED_FILE_NAMES or path.suffix.lower() in SUPPORTED_SUFFIXES


def _should_ignore_file(path: Path) -> bool:
    return path.name in IGNORED_NAMES or path.suffix.lower() in IGNORED_BINARY_SUFFIXES


def copy_preserved_entries(source_root: Path, destination_root: Path) -> None:
    for entry in sorted(source_root.iterdir(), key=lambda path: path.name):
        if entry.name not in PRESERVED_DIRECTORY_NAMES:
            continue
        target_path = destination_root / entry.name
        if entry.is_dir():
            shutil.copytree(entry, target_path, symlinks=True)
        else:
            shutil.copy2(entry, target_path)


def copy_passthrough_entries(
    source_root: Path,
    destination_root: Path,
    transform_relative_path: Callable[[Path], Path] | None = None,
) -> None:
    path_transform = transform_relative_path or (lambda relative_path: relative_path)
    for current_root, directory_names, file_names in os.walk(source_root):
        directory_names[:] = sorted(
            name for name in directory_names if name not in IGNORED_NAMES
        )
        current_root_path = Path(current_root)
        for file_name in sorted(file_names):
            absolute_path = current_root_path / file_name
            relative_path = absolute_path.relative_to(source_root)
            if _should_copy_passthrough_file(relative_path, absolute_path):
                target_path = destination_root / path_transform(relative_path)
                target_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(absolute_path, target_path)


def copy_passthrough_directories(
    source_root: Path,
    destination_root: Path,
    transform_relative_path: Callable[[Path], Path] | None = None,
) -> None:
    path_transform = transform_relative_path or (lambda relative_path: relative_path)
    for current_root, directory_names, _file_names in os.walk(source_root):
        current_root_path = Path(current_root)
        kept_directory_names: list[str] = []
        for directory_name in sorted(directory_names):
            if directory_name == ".leximask":
                continue
            source_path = current_root_path / directory_name
            relative_path = source_path.relative_to(source_root)
            if directory_name in PRESERVED_DIRECTORY_NAMES:
                continue
            if directory_name in IGNORED_NAMES:
                target_path = destination_root / path_transform(relative_path)
                target_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(source_path, target_path, symlinks=True)
                continue
            kept_directory_names.append(directory_name)
        directory_names[:] = kept_directory_names


def _should_copy_passthrough_file(relative_path: Path, absolute_path: Path) -> bool:
    if any(part in IGNORED_NAMES - {".leximask"} for part in relative_path.parts):
        return True
    if any(part in PRESERVED_DIRECTORY_NAMES for part in relative_path.parts):
        return True
    return _should_ignore_file(absolute_path)


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
