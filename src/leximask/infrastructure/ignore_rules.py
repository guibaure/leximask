"""Repository-local passthrough ignore rules."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from leximask.errors import ValidationError
from leximask.infrastructure.digests import sha256_text


IGNORE_FILE_NAME = ".leximaskignore"


@dataclass(frozen=True, slots=True)
class IgnoreRules:
    """Exact repository-relative passthrough rules."""

    file_paths: frozenset[PurePosixPath]
    directory_paths: frozenset[PurePosixPath]
    digest: str | None

    def matches_file(self, relative_path: Path) -> bool:
        repository_path = _to_repository_path(relative_path)
        return repository_path in self.file_paths or self._matches_parent_directory(
            repository_path
        )

    def matches_directory(self, relative_path: Path) -> bool:
        repository_path = _to_repository_path(relative_path)
        return repository_path in self.directory_paths or self._matches_parent_directory(
            repository_path
        )

    def _matches_parent_directory(self, repository_path: PurePosixPath) -> bool:
        return any(
            parent != PurePosixPath(".") and parent in self.directory_paths
            for parent in repository_path.parents
        )


def ignore_file_path(root_directory: Path) -> Path:
    return root_directory / IGNORE_FILE_NAME


def load_ignore_rules(root_directory: Path) -> IgnoreRules:
    config_path = ignore_file_path(root_directory)
    if not config_path.is_file():
        return IgnoreRules(
            file_paths=frozenset(),
            directory_paths=frozenset(),
            digest=None,
        )

    content = config_path.read_text(encoding="utf-8")
    file_paths: set[PurePosixPath] = set()
    directory_paths: set[PurePosixPath] = set()
    for line_number, raw_line in enumerate(content.splitlines(), start=1):
        stripped_line = raw_line.strip()
        if not stripped_line or stripped_line.startswith("#"):
            continue

        is_directory = stripped_line.endswith(("/", "\\"))
        normalised_text = stripped_line.rstrip("/\\").replace("\\", "/")
        if normalised_text.startswith("./"):
            normalised_text = normalised_text[2:]
        if normalised_text.startswith("/"):
            raise ValidationError(
                f"{IGNORE_FILE_NAME}:{line_number}: ignore paths must be repository-relative"
            )
        rule_path = PurePosixPath(normalised_text)
        if normalised_text in {"", "."} or any(part == ".." for part in rule_path.parts):
            raise ValidationError(
                f"{IGNORE_FILE_NAME}:{line_number}: ignore path is invalid"
            )

        if is_directory:
            directory_paths.add(rule_path)
            continue
        file_paths.add(rule_path)

    return IgnoreRules(
        file_paths=frozenset(file_paths),
        directory_paths=frozenset(directory_paths),
        digest=sha256_text(content),
    )


def _to_repository_path(relative_path: Path) -> PurePosixPath:
    return PurePosixPath(relative_path.as_posix())
