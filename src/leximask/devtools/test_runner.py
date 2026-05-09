from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Sequence


def resolve_path(base_directory: Path, path_value: str) -> Path:
    candidate_path = Path(path_value)
    if not candidate_path.is_absolute():
        candidate_path = base_directory / candidate_path
    return candidate_path.resolve()


def iter_test_directories(project_root: Path, runtime_test_dir: str) -> tuple[Path, ...]:
    resolved_project_root = project_root.resolve()
    default_test_directory = (resolved_project_root / "tests").resolve()
    runtime_test_directory = resolve_path(resolved_project_root, runtime_test_dir)

    if not default_test_directory.is_dir():
        raise FileNotFoundError(f"Default test directory does not exist: {default_test_directory}")
    if not runtime_test_directory.is_dir():
        raise FileNotFoundError(f"Runtime test directory does not exist: {runtime_test_directory}")

    ordered_directories: list[Path] = []
    for test_directory in (default_test_directory, runtime_test_directory):
        if test_directory not in ordered_directories:
            ordered_directories.append(test_directory)
    return tuple(ordered_directories)


def run_test_suites(
    project_root: Path,
    runtime_test_dir: str,
    *,
    python_executable: str = sys.executable,
) -> int:
    resolved_project_root = project_root.resolve()
    for test_directory in iter_test_directories(resolved_project_root, runtime_test_dir):
        completed_process = subprocess.run(
            [
                python_executable,
                "-m",
                "unittest",
                "discover",
                "-s",
                str(test_directory),
                "-v",
            ],
            cwd=resolved_project_root,
        )
        if completed_process.returncode != 0:
            return completed_process.returncode
    return 0


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run LexiMask source and runtime test suites.")
    parser.add_argument(
        "--project-root",
        default=Path.cwd(),
        type=Path,
        help="LexiMask repository root. Defaults to the current working directory.",
    )
    parser.add_argument(
        "--runtime-test-dir",
        default="runtime/tests",
        help="Runtime test directory, relative to the project root unless absolute.",
    )
    parser.add_argument(
        "--python-executable",
        default=sys.executable,
        help="Python executable used to run unittest discovery.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_argument_parser()
    arguments = parser.parse_args(argv)
    project_root = arguments.project_root.resolve()
    if not project_root.is_dir():
        parser.error(f"Project root does not exist: {project_root}")

    return run_test_suites(
        project_root,
        arguments.runtime_test_dir,
        python_executable=arguments.python_executable,
    )


if __name__ == "__main__":
    raise SystemExit(main())
