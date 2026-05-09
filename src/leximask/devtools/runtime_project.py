from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Sequence


CLICK_REPOSITORY_URL = "https://github.com/pallets/click.git"
CLICK_PROJECT_NAME = "pallets-click"


def build_click_mapping_csv() -> str:
    return "source,replacement\nclick,nimbus\n"


def build_click_ignore_file() -> str:
    return ".git/\n.devcontainer/\ndocs/\nexamples/\nCHANGES.rst\nsrc/click/py.typed\nuv.lock\n"


def resolve_path(base_directory: Path, path_value: str) -> Path:
    candidate_path = Path(path_value)
    if not candidate_path.is_absolute():
        candidate_path = base_directory / candidate_path
    return candidate_path.resolve()


def resolve_existing_directory(base_directory: Path, path_value: str, label: str) -> Path:
    resolved_path = resolve_path(base_directory, path_value)
    if not resolved_path.is_dir():
        raise FileNotFoundError(f"{label} does not exist: {resolved_path}")
    return resolved_path


def build_leximask_environment(project_root: Path) -> dict[str, str]:
    environment = os.environ.copy()
    source_directory = str((project_root / "src").resolve())
    existing_python_path = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = (
        f"{source_directory}{os.pathsep}{existing_python_path}"
        if existing_python_path
        else source_directory
    )
    return environment


def build_leximask_command(
    project_root: Path,
    *arguments: str,
) -> tuple[list[str], dict[str, str]]:
    return (
        [sys.executable, "-m", "leximask.cli", *arguments],
        build_leximask_environment(project_root),
    )


def virtualenv_python_path(virtualenv_directory: Path) -> Path:
    scripts_directory, python_binary = {
        "nt": ("Scripts", "python.exe"),
    }.get(os.name, ("bin", "python"))
    return virtualenv_directory / scripts_directory / python_binary


def run_command(
    command: list[str],
    *,
    cwd: Path,
    environment: dict[str, str] | None = None,
) -> None:
    subprocess.run(command, cwd=cwd, env=environment, check=True)


def prepare_click_runtime_project(
    runtime_root: Path,
    *,
    refresh_checkout: bool = False,
) -> Path:
    checkout_path = runtime_root / "checkouts" / CLICK_PROJECT_NAME
    runtime_root.mkdir(parents=True, exist_ok=True)

    if refresh_checkout:
        shutil.rmtree(checkout_path, ignore_errors=True)
    if checkout_path.exists():
        return checkout_path

    checkout_path.parent.mkdir(parents=True, exist_ok=True)
    run_command(
        ["git", "clone", "--depth", "1", CLICK_REPOSITORY_URL, str(checkout_path)],
        cwd=runtime_root,
    )
    return checkout_path


def create_click_workspace(runtime_root: Path, checkout_path: Path) -> Path:
    workspace_path = runtime_root / "workspaces" / CLICK_PROJECT_NAME
    shutil.rmtree(workspace_path, ignore_errors=True)
    workspace_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        checkout_path,
        workspace_path,
        ignore=shutil.ignore_patterns(".git"),
    )
    return workspace_path


def ensure_click_runtime_inputs(runtime_root: Path, workspace_path: Path) -> Path:
    fixture_directory = runtime_root / "fixtures"
    fixture_directory.mkdir(parents=True, exist_ok=True)

    mapping_path = fixture_directory / "pallets-click-mapping.csv"
    mapping_path.write_text(build_click_mapping_csv(), encoding="utf-8")
    (workspace_path / ".leximaskignore").write_text(build_click_ignore_file(), encoding="utf-8")
    return mapping_path


def ensure_runtime_virtualenv(runtime_root: Path, project_root: Path) -> Path:
    virtualenv_directory = runtime_root / ".venvs" / CLICK_PROJECT_NAME
    python_path = virtualenv_python_path(virtualenv_directory)
    if python_path.exists():
        return python_path

    run_command(
        [sys.executable, "-m", "venv", str(virtualenv_directory)],
        cwd=project_root,
    )
    return python_path


def run_leximask_command(project_root: Path, *arguments: str) -> None:
    command, environment = build_leximask_command(project_root, *arguments)
    run_command(command, cwd=project_root, environment=environment)


def validate_click_runtime_project(
    project_root: Path,
    runtime_root: Path,
    *,
    refresh_checkout: bool = False,
) -> Path:
    runtime_python = ensure_runtime_virtualenv(runtime_root, project_root)
    checkout_path = prepare_click_runtime_project(
        runtime_root,
        refresh_checkout=refresh_checkout,
    )
    workspace_path = create_click_workspace(runtime_root, checkout_path)
    mapping_path = ensure_click_runtime_inputs(runtime_root, workspace_path)

    run_leximask_command(
        project_root,
        "plan",
        "--input",
        str(workspace_path),
        "--mapping",
        str(mapping_path),
    )
    run_leximask_command(project_root, "apply", "--input", str(workspace_path))
    run_command(
        [str(runtime_python), "-m", "pip", "install", "-e", ".", "pytest"],
        cwd=workspace_path,
    )
    run_command([str(runtime_python), "-m", "pytest", "tests", "-q"], cwd=workspace_path)
    run_leximask_command(project_root, "reverse", "--input", str(workspace_path))
    run_command([str(runtime_python), "-m", "pip", "install", "-e", "."], cwd=workspace_path)
    run_command([str(runtime_python), "-m", "pytest", "tests", "-q"], cwd=workspace_path)
    return workspace_path


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare and validate LexiMask runtime projects.")
    parser.add_argument(
        "--project-root",
        default=Path.cwd(),
        type=Path,
        help="LexiMask repository root. Defaults to the current working directory.",
    )
    parser.add_argument(
        "--runtime-root",
        default="runtime/tests",
        help="Runtime root directory, relative to the project root unless absolute.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare_parser = subparsers.add_parser("prepare-click")
    prepare_parser.add_argument(
        "--refresh-checkout",
        action="store_true",
        help="Delete and reclone the Click checkout before preparing runtime files.",
    )

    validate_parser = subparsers.add_parser("validate-click")
    validate_parser.add_argument(
        "--refresh-checkout",
        action="store_true",
        help="Delete and reclone the Click checkout before validating runtime behaviour.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_argument_parser()
    arguments = parser.parse_args(argv)
    project_root = arguments.project_root.resolve()
    if not project_root.is_dir():
        parser.error(f"Project root does not exist: {project_root}")

    runtime_root = resolve_path(project_root, arguments.runtime_root)
    try:
        if arguments.command == "prepare-click":
            prepare_click_runtime_project(
                runtime_root,
                refresh_checkout=arguments.refresh_checkout,
            )
        else:
            validate_click_runtime_project(
                project_root,
                runtime_root,
                refresh_checkout=arguments.refresh_checkout,
            )
    except subprocess.CalledProcessError as error:
        return error.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
