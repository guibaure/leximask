"""Runtime validation helpers for real-world repository exercises."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

CLICK_REPOSITORY_URL = "https://github.com/pallets/click.git"
CLICK_CHECKOUT_DIRECTORY = Path("checkouts") / "pallets-click"
CLICK_WORKSPACE_DIRECTORY = Path("workspaces") / "pallets-click"
CLICK_VIRTUALENV_DIRECTORY = Path(".venvs") / "pallets-click"
CLICK_MAPPING_PATH = Path("fixtures") / "pallets-click-mapping.csv"
CLICK_IGNORE_PATH = Path(".leximaskignore")
CLICK_MAPPING_CONTENT = "source,replacement\nclick,nimbus\n"
CLICK_IGNORE_ENTRIES = (
    ".git/",
    ".devcontainer/",
    "docs/",
    "examples/",
    "CHANGES.rst",
    "src/click/py.typed",
    "uv.lock",
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m leximask.devtools.runtime_project",
        description=(
            "Prepare and validate a real-world runtime project under runtime/tests."
        ),
    )
    parser.add_argument(
        "--project-root",
        default=".",
        help="LexiMask project root",
    )
    parser.add_argument(
        "--runtime-test-root",
        default="runtime/tests",
        help="Runtime test root used for external project checkouts and workspaces",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare_parser = subparsers.add_parser(
        "prepare-click",
        help="Clone or refresh the pallets/click checkout under the runtime test root",
    )
    prepare_parser.add_argument(
        "--refresh-checkout",
        action="store_true",
        help="Remove the cached checkout before cloning again",
    )

    validate_parser = subparsers.add_parser(
        "validate-click",
        help="Run LexiMask plan/apply/reverse and upstream Click tests on a disposable workspace",
    )
    validate_parser.add_argument(
        "--refresh-checkout",
        action="store_true",
        help="Remove the cached checkout before cloning again",
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


def resolve_path(base_directory: Path, raw_path: str) -> Path:
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = base_directory / candidate
    return candidate.resolve()


def click_checkout_path(runtime_test_root: Path) -> Path:
    return runtime_test_root / CLICK_CHECKOUT_DIRECTORY


def click_workspace_path(runtime_test_root: Path) -> Path:
    return runtime_test_root / CLICK_WORKSPACE_DIRECTORY


def click_virtualenv_path(runtime_test_root: Path) -> Path:
    return runtime_test_root / CLICK_VIRTUALENV_DIRECTORY


def click_mapping_path(runtime_test_root: Path) -> Path:
    return runtime_test_root / CLICK_MAPPING_PATH


def build_click_ignore_file() -> str:
    return "\n".join(CLICK_IGNORE_ENTRIES) + "\n"


def build_click_mapping_csv() -> str:
    return CLICK_MAPPING_CONTENT


def build_leximask_environment(project_root: Path) -> dict[str, str]:
    environment = os.environ.copy()
    source_directory = str((project_root / "src").resolve())
    existing_pythonpath = environment.get("PYTHONPATH")
    if existing_pythonpath:
        environment["PYTHONPATH"] = f"{source_directory}{os.pathsep}{existing_pythonpath}"
    else:
        environment["PYTHONPATH"] = source_directory
    return environment


def build_leximask_command(project_root: Path, *args: str) -> tuple[list[str], dict[str, str]]:
    return [sys.executable, "-m", "leximask.cli", *args], build_leximask_environment(project_root)


def virtualenv_python_path(virtualenv_directory: Path) -> Path:
    if os.name == "nt":
        return virtualenv_directory / "Scripts" / "python.exe"
    return virtualenv_directory / "bin" / "python"


def run_command(
    command: list[str],
    *,
    cwd: Path,
    environment: dict[str, str] | None = None,
) -> None:
    subprocess.run(command, cwd=cwd, env=environment, check=True)


def remove_tree(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)


def prepare_click_runtime_project(
    runtime_test_root: Path,
    *,
    refresh_checkout: bool = False,
) -> Path:
    checkout_path = click_checkout_path(runtime_test_root)
    runtime_test_root.mkdir(parents=True, exist_ok=True)
    checkout_path.parent.mkdir(parents=True, exist_ok=True)
    if checkout_path.exists():
        if not refresh_checkout:
            return checkout_path
        remove_tree(checkout_path)
    run_command(
        ["git", "clone", "--depth", "1", CLICK_REPOSITORY_URL, str(checkout_path)],
        cwd=runtime_test_root,
    )
    return checkout_path


def create_click_workspace(
    runtime_test_root: Path,
    checkout_path: Path,
) -> Path:
    workspace_path = click_workspace_path(runtime_test_root)
    remove_tree(workspace_path)
    workspace_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        checkout_path,
        workspace_path,
        ignore=shutil.ignore_patterns(".git"),
    )
    return workspace_path


def ensure_click_runtime_inputs(
    runtime_test_root: Path,
    workspace_path: Path,
) -> Path:
    mapping_path = click_mapping_path(runtime_test_root)
    mapping_path.parent.mkdir(parents=True, exist_ok=True)
    mapping_path.write_text(build_click_mapping_csv(), encoding="utf-8", newline="\n")
    (workspace_path / CLICK_IGNORE_PATH).write_text(
        build_click_ignore_file(),
        encoding="utf-8",
        newline="\n",
    )
    return mapping_path


def ensure_runtime_virtualenv(
    runtime_test_root: Path,
    project_root: Path,
) -> Path:
    virtualenv_directory = click_virtualenv_path(runtime_test_root)
    virtualenv_directory.parent.mkdir(parents=True, exist_ok=True)
    python_path = virtualenv_python_path(virtualenv_directory)
    if python_path.exists():
        return python_path
    run_command(
        [sys.executable, "-m", "venv", str(virtualenv_directory)],
        cwd=project_root,
    )
    return python_path


def validate_click_runtime_project(
    project_root: Path,
    runtime_test_root: Path,
    *,
    refresh_checkout: bool = False,
) -> Path:
    checkout_path = prepare_click_runtime_project(
        runtime_test_root,
        refresh_checkout=refresh_checkout,
    )
    workspace_path = create_click_workspace(runtime_test_root, checkout_path)
    mapping_path = ensure_click_runtime_inputs(runtime_test_root, workspace_path)
    virtualenv_python = ensure_runtime_virtualenv(runtime_test_root, project_root)

    plan_command, leximask_environment = build_leximask_command(
        project_root,
        "plan",
        "--input",
        str(workspace_path),
        "--mapping",
        str(mapping_path),
    )
    run_command(plan_command, cwd=project_root, environment=leximask_environment)

    apply_command, leximask_environment = build_leximask_command(
        project_root,
        "apply",
        "--input",
        str(workspace_path),
    )
    run_command(apply_command, cwd=project_root, environment=leximask_environment)

    run_command(
        [str(virtualenv_python), "-m", "pip", "install", "-e", ".", "pytest"],
        cwd=workspace_path,
    )
    run_command(
        [str(virtualenv_python), "-m", "pytest", "tests", "-q"],
        cwd=workspace_path,
    )

    reverse_command, leximask_environment = build_leximask_command(
        project_root,
        "reverse",
        "--input",
        str(workspace_path),
    )
    run_command(reverse_command, cwd=project_root, environment=leximask_environment)

    run_command(
        [str(virtualenv_python), "-m", "pip", "install", "-e", "."],
        cwd=workspace_path,
    )
    run_command(
        [str(virtualenv_python), "-m", "pytest", "tests", "-q"],
        cwd=workspace_path,
    )
    return workspace_path


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        project_root = resolve_existing_directory(Path.cwd(), args.project_root, "Project root")
        runtime_test_root = resolve_path(project_root, args.runtime_test_root)
        if args.command == "prepare-click":
            checkout_path = prepare_click_runtime_project(
                runtime_test_root,
                refresh_checkout=args.refresh_checkout,
            )
            print(checkout_path)
            return 0
        if args.command == "validate-click":
            workspace_path = validate_click_runtime_project(
                project_root,
                runtime_test_root,
                refresh_checkout=args.refresh_checkout,
            )
            print(workspace_path)
            return 0
    except FileNotFoundError as error:
        parser.exit(status=2, message=f"error: {error}\n")
    except subprocess.CalledProcessError as error:
        return int(error.returncode)

    parser.exit(status=2, message="error: unsupported command\n")  # pragma: no cover
    return 2  # pragma: no cover


if __name__ == "__main__":
    raise SystemExit(main())
