"""Development test runner with optional runtime-suite support."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

DEFAULT_TEST_DIRECTORY = Path("tests")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m leximask.devtools.test_runner",
        description=(
            "Run the tracked LexiMask test suite and, optionally, an additional "
            "runtime test directory."
        ),
    )
    parser.add_argument(
        "--project-root",
        default=".",
        help="LexiMask project root containing the default tests/ directory",
    )
    parser.add_argument(
        "--runtime-test-dir",
        help=(
            "Optional additional test directory to execute after the default tests/ suite, "
            "for example runtime/tests"
        ),
    )
    return parser


def resolve_existing_directory(
    base_directory: Path,
    raw_path: str,
    description: str,
) -> Path:
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = base_directory / candidate
    resolved = candidate.resolve()
    if not resolved.is_dir():
        raise FileNotFoundError(f"{description} does not exist: {resolved}")
    return resolved


def iter_test_directories(
    project_root: Path,
    runtime_test_dir: str | None,
) -> tuple[Path, ...]:
    test_directories = [
        resolve_existing_directory(project_root, str(DEFAULT_TEST_DIRECTORY), "Default test directory")
    ]
    if runtime_test_dir is not None:
        resolved_runtime_directory = resolve_existing_directory(
            project_root,
            runtime_test_dir,
            "Runtime test directory",
        )
        if resolved_runtime_directory not in test_directories:
            test_directories.append(resolved_runtime_directory)
    return tuple(test_directories)


def build_unittest_command(
    python_executable: str,
    test_directory: Path,
) -> list[str]:
    return [
        python_executable,
        "-m",
        "unittest",
        "discover",
        "-s",
        str(test_directory),
        "-v",
    ]


def run_test_suites(
    project_root: Path,
    runtime_test_dir: str | None,
    python_executable: str | None = None,
) -> int:
    selected_python = python_executable or sys.executable
    for test_directory in iter_test_directories(project_root, runtime_test_dir):
        completed = subprocess.run(
            build_unittest_command(selected_python, test_directory),
            cwd=project_root,
            check=False,
        )
        if completed.returncode != 0:
            return int(completed.returncode)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        project_root = resolve_existing_directory(Path.cwd(), args.project_root, "Project root")
    except FileNotFoundError as error:
        parser.exit(status=2, message=f"error: {error}\n")

    return run_test_suites(project_root, args.runtime_test_dir)


if __name__ == "__main__":
    raise SystemExit(main())
