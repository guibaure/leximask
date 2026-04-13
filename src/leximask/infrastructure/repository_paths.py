"""Repository-relative path serialisation helpers."""

from __future__ import annotations

from pathlib import Path, PurePath


def serialise_repository_relative_path(relative_path: PurePath) -> str:
    """Return a platform-neutral metadata path."""

    return relative_path.as_posix()


def deserialise_repository_relative_path(value: object) -> Path:
    """Read a metadata path, accepting legacy Windows separators."""

    return Path(str(value).replace("\\", "/"))
