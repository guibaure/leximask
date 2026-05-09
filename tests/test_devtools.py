from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests import _path_setup  # noqa: F401

from leximask.devtools import runtime_project, test_runner


def _resolved(path: Path) -> Path:
    return path.resolve()


class TestRunnerTests(unittest.TestCase):
    def test_iter_test_directories_defaults_and_appends_runtime_dir(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)
            (project_root / "tests").mkdir()
            (project_root / "runtime" / "tests").mkdir(parents=True)

            directories = test_runner.iter_test_directories(project_root, "runtime/tests")

            self.assertEqual(
                directories,
                (
                    _resolved(project_root / "tests"),
                    _resolved(project_root / "runtime" / "tests"),
                ),
            )

    def test_iter_test_directories_deduplicates_default_runtime_dir(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)
            (project_root / "tests").mkdir()

            directories = test_runner.iter_test_directories(project_root, "tests")

            self.assertEqual(directories, (_resolved(project_root / "tests"),))

    def test_iter_test_directories_rejects_missing_runtime_dir(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)
            (project_root / "tests").mkdir()

            with self.assertRaisesRegex(FileNotFoundError, "Runtime test directory"):
                test_runner.iter_test_directories(project_root, "runtime/tests")

    def test_iter_test_directories_rejects_missing_default_dir(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)
            (project_root / "runtime" / "tests").mkdir(parents=True)

            with self.assertRaisesRegex(FileNotFoundError, "Default test directory"):
                test_runner.iter_test_directories(project_root, "runtime/tests")

    def test_iter_test_directories_accepts_absolute_runtime_dir(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)
            runtime_test_directory = project_root / "runtime" / "tests"
            (project_root / "tests").mkdir()
            runtime_test_directory.mkdir(parents=True)

            directories = test_runner.iter_test_directories(
                project_root,
                str(runtime_test_directory),
            )

            self.assertEqual(
                directories,
                (
                    _resolved(project_root / "tests"),
                    _resolved(runtime_test_directory),
                ),
            )

    def test_run_test_suites_stops_on_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)
            (project_root / "tests").mkdir()
            (project_root / "runtime" / "tests").mkdir(parents=True)

            with patch(
                "leximask.devtools.test_runner.subprocess.run",
                side_effect=[
                    subprocess.CompletedProcess(args=["python"], returncode=3),
                    subprocess.CompletedProcess(args=["python"], returncode=0),
                ],
            ) as mocked_run:
                return_code = test_runner.run_test_suites(
                    project_root,
                    "runtime/tests",
                    python_executable="python",
                )

            self.assertEqual(return_code, 3)
            self.assertEqual(mocked_run.call_count, 1)

    def test_main_runs_default_and_runtime_suites(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)
            (project_root / "tests").mkdir()
            (project_root / "runtime" / "tests").mkdir(parents=True)

            with patch(
                "leximask.devtools.test_runner.subprocess.run",
                return_value=subprocess.CompletedProcess(args=["python"], returncode=0),
            ) as mocked_run:
                return_code = test_runner.main(
                    [
                        "--project-root",
                        str(project_root),
                        "--runtime-test-dir",
                        "runtime/tests",
                    ]
                )

            self.assertEqual(return_code, 0)
            self.assertEqual(mocked_run.call_count, 2)
            first_call = mocked_run.call_args_list[0]
            second_call = mocked_run.call_args_list[1]
            self.assertEqual(first_call.kwargs["cwd"], _resolved(project_root))
            self.assertEqual(second_call.kwargs["cwd"], _resolved(project_root))
            self.assertEqual(first_call.args[0][-2:], [str(_resolved(project_root / "tests")), "-v"])
            self.assertEqual(
                second_call.args[0][-2:],
                [str(_resolved(project_root / "runtime" / "tests")), "-v"],
            )

    def test_main_rejects_missing_project_root(self) -> None:
        with self.assertRaises(SystemExit) as raised:
            test_runner.main(["--project-root", "/definitely/missing"])

        self.assertEqual(raised.exception.code, 2)


class RuntimeProjectTests(unittest.TestCase):
    def test_build_click_runtime_files_are_stable(self) -> None:
        self.assertEqual(
            runtime_project.build_click_mapping_csv(),
            "source,replacement\nclick,nimbus\n",
        )
        self.assertEqual(
            runtime_project.build_click_ignore_file(),
            ".git/\n.devcontainer/\ndocs/\nexamples/\nCHANGES.rst\nsrc/click/py.typed\nuv.lock\n",
        )

    def test_path_helpers_resolve_relative_and_absolute_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            base_directory = Path(temporary_directory)
            existing_directory = base_directory / "existing"
            existing_directory.mkdir()

            self.assertEqual(
                runtime_project.resolve_existing_directory(
                    base_directory,
                    "existing",
                    "Example directory",
                ),
                _resolved(existing_directory),
            )
            self.assertEqual(
                runtime_project.resolve_existing_directory(
                    base_directory,
                    str(existing_directory),
                    "Example directory",
                ),
                _resolved(existing_directory),
            )
            self.assertEqual(
                runtime_project.resolve_path(base_directory, "runtime/tests"),
                _resolved(base_directory / "runtime" / "tests"),
            )
            self.assertEqual(
                runtime_project.resolve_path(base_directory, str(existing_directory)),
                _resolved(existing_directory),
            )

    def test_resolve_existing_directory_rejects_missing_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            base_directory = Path(temporary_directory)

            with self.assertRaisesRegex(FileNotFoundError, "Example directory"):
                runtime_project.resolve_existing_directory(
                    base_directory,
                    "missing",
                    "Example directory",
                )

    def test_build_leximask_command_adds_source_directory_to_pythonpath(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)
            (project_root / "src").mkdir()
            with patch.dict("os.environ", {"PYTHONPATH": "/existing"}, clear=False):
                command, environment = runtime_project.build_leximask_command(
                    project_root,
                    "plan",
                    "--input",
                    "/tmp/repo",
                    "--mapping",
                    "/tmp/mapping.csv",
                )

            self.assertEqual(command[:3], [runtime_project.sys.executable, "-m", "leximask.cli"])
            self.assertEqual(
                environment["PYTHONPATH"],
                f"{_resolved(project_root / 'src')}{runtime_project.os.pathsep}/existing",
            )

    def test_build_leximask_environment_sets_pythonpath_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)
            (project_root / "src").mkdir()

            with patch.dict("os.environ", {}, clear=True):
                environment = runtime_project.build_leximask_environment(project_root)

            self.assertEqual(environment["PYTHONPATH"], str(_resolved(project_root / "src")))

    def test_virtualenv_python_path_matches_current_platform(self) -> None:
        virtualenv_directory = Path("/tmp/example-venv")
        expected = (
            virtualenv_directory / "Scripts" / "python.exe"
            if runtime_project.os.name == "nt"
            else virtualenv_directory / "bin" / "python"
        )
        self.assertEqual(runtime_project.virtualenv_python_path(virtualenv_directory), expected)

    def test_virtualenv_python_path_supports_windows_layout(self) -> None:
        virtualenv_directory = Path("/tmp/example-venv")
        with patch("leximask.devtools.runtime_project.os.name", "nt"):
            self.assertEqual(
                runtime_project.virtualenv_python_path(virtualenv_directory),
                virtualenv_directory / "Scripts" / "python.exe",
            )

    def test_run_command_wraps_subprocess_run(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            working_directory = Path(temporary_directory)
            environment = {"PYTHONPATH": "src"}

            with patch("leximask.devtools.runtime_project.subprocess.run") as mocked_run:
                runtime_project.run_command(
                    ["python", "--version"],
                    cwd=working_directory,
                    environment=environment,
                )

            mocked_run.assert_called_once_with(
                ["python", "--version"],
                cwd=working_directory,
                env=environment,
                check=True,
            )

    def test_prepare_click_runtime_project_clones_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            runtime_root = Path(temporary_directory)

            with patch("leximask.devtools.runtime_project.run_command") as mocked_run:
                checkout_path = runtime_project.prepare_click_runtime_project(runtime_root)

            self.assertEqual(
                checkout_path,
                runtime_root / "checkouts" / "pallets-click",
            )
            mocked_run.assert_called_once_with(
                [
                    "git",
                    "clone",
                    "--depth",
                    "1",
                    runtime_project.CLICK_REPOSITORY_URL,
                    str(checkout_path),
                ],
                cwd=runtime_root,
            )

    def test_prepare_click_runtime_project_reuses_existing_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            runtime_root = Path(temporary_directory)
            checkout_path = runtime_root / "checkouts" / "pallets-click"
            checkout_path.mkdir(parents=True)

            with patch("leximask.devtools.runtime_project.run_command") as mocked_run:
                result = runtime_project.prepare_click_runtime_project(runtime_root)

            self.assertEqual(result, checkout_path)
            mocked_run.assert_not_called()

    def test_prepare_click_runtime_project_refreshes_existing_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            runtime_root = Path(temporary_directory)
            checkout_path = runtime_root / "checkouts" / "pallets-click"
            checkout_path.mkdir(parents=True)

            with patch("leximask.devtools.runtime_project.run_command") as mocked_run:
                result = runtime_project.prepare_click_runtime_project(
                    runtime_root,
                    refresh_checkout=True,
                )

            self.assertEqual(result, checkout_path)
            self.assertFalse(checkout_path.exists())
            mocked_run.assert_called_once()

    def test_create_workspace_and_runtime_inputs_are_materialised(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            runtime_root = Path(temporary_directory)
            checkout_path = runtime_root / "checkouts" / "pallets-click"
            checkout_path.mkdir(parents=True)
            (checkout_path / ".git").mkdir()
            (checkout_path / ".git" / "config").write_text("config\n", encoding="utf-8")
            (checkout_path / "README.md").write_text("Click\n", encoding="utf-8")

            workspace_path = runtime_project.create_click_workspace(runtime_root, checkout_path)
            mapping_path = runtime_project.ensure_click_runtime_inputs(runtime_root, workspace_path)

            self.assertTrue((workspace_path / "README.md").is_file())
            self.assertFalse((workspace_path / ".git").exists())
            self.assertEqual(
                mapping_path,
                runtime_root / "fixtures" / "pallets-click-mapping.csv",
            )
            self.assertEqual(
                mapping_path.read_text(encoding="utf-8"),
                "source,replacement\nclick,nimbus\n",
            )
            self.assertEqual(
                (workspace_path / ".leximaskignore").read_text(encoding="utf-8"),
                ".git/\n.devcontainer/\ndocs/\nexamples/\nCHANGES.rst\nsrc/click/py.typed\nuv.lock\n",
            )

    def test_ensure_runtime_virtualenv_creates_once_then_reuses(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory) / "project"
            runtime_root = project_root / "runtime" / "tests"
            project_root.mkdir()
            (project_root / "src").mkdir()
            created_python = runtime_project.virtualenv_python_path(
                runtime_root / ".venvs" / "pallets-click"
            )

            def record_venv_creation(
                command: list[str],
                *,
                cwd: Path,
                environment: dict[str, str] | None = None,
            ) -> None:
                self.assertEqual(command[:3], [runtime_project.sys.executable, "-m", "venv"])
                self.assertEqual(cwd, project_root)
                created_python.parent.mkdir(parents=True, exist_ok=True)
                created_python.write_text("", encoding="utf-8")

            with patch(
                "leximask.devtools.runtime_project.run_command",
                side_effect=record_venv_creation,
            ) as mocked_run:
                first_python = runtime_project.ensure_runtime_virtualenv(runtime_root, project_root)
                second_python = runtime_project.ensure_runtime_virtualenv(runtime_root, project_root)

            self.assertEqual(first_python, created_python)
            self.assertEqual(second_python, created_python)
            mocked_run.assert_called_once()

    def test_validate_click_runtime_project_runs_expected_commands(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory) / "project"
            runtime_root = project_root / "runtime" / "tests"
            checkout_path = runtime_root / "checkouts" / "pallets-click"
            project_root.mkdir()
            (project_root / "src").mkdir()
            checkout_path.mkdir(parents=True)
            (checkout_path / "README.md").write_text("Click\n", encoding="utf-8")
            commands: list[tuple[list[str], Path, dict[str, str] | None]] = []

            def record_command(
                command: list[str],
                *,
                cwd: Path,
                environment: dict[str, str] | None = None,
            ) -> None:
                commands.append((command, cwd, environment))
                if command[:3] == [runtime_project.sys.executable, "-m", "venv"]:
                    runtime_project.virtualenv_python_path(
                        runtime_root / ".venvs" / "pallets-click"
                    ).parent.mkdir(
                        parents=True,
                        exist_ok=True,
                    )
                    runtime_project.virtualenv_python_path(
                        runtime_root / ".venvs" / "pallets-click"
                    ).write_text("", encoding="utf-8")

            with patch(
                "leximask.devtools.runtime_project.run_command",
                side_effect=record_command,
            ):
                workspace_path = runtime_project.validate_click_runtime_project(
                    project_root,
                    runtime_root,
                )

            self.assertEqual(workspace_path, runtime_root / "workspaces" / "pallets-click")
            self.assertEqual(
                (runtime_root / "fixtures" / "pallets-click-mapping.csv").read_text(encoding="utf-8"),
                "source,replacement\nclick,nimbus\n",
            )
            self.assertEqual(
                (workspace_path / ".leximaskignore").read_text(encoding="utf-8"),
                ".git/\n.devcontainer/\ndocs/\nexamples/\nCHANGES.rst\nsrc/click/py.typed\nuv.lock\n",
            )
            self.assertEqual(
                commands[0][0],
                [
                    runtime_project.sys.executable,
                    "-m",
                    "venv",
                    str(runtime_root / ".venvs" / "pallets-click"),
                ],
            )
            self.assertEqual(commands[1][0][1:3], ["-m", "leximask.cli"])
            self.assertEqual(commands[2][0][1:3], ["-m", "leximask.cli"])
            self.assertEqual(commands[3][0][-2:], [".", "pytest"])
            self.assertEqual(commands[4][0][-2:], ["tests", "-q"])
            self.assertEqual(commands[5][0][1:3], ["-m", "leximask.cli"])
            self.assertEqual(commands[6][0][-2:], ["-e", "."])
            self.assertEqual(commands[7][0][-2:], ["tests", "-q"])

    def test_main_dispatches_prepare_and_propagates_command_failures(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)
            (project_root / "src").mkdir()

            with patch(
                "leximask.devtools.runtime_project.prepare_click_runtime_project",
                return_value=project_root / "runtime" / "tests" / "checkouts" / "pallets-click",
            ):
                return_code = runtime_project.main(
                    [
                        "--project-root",
                        str(project_root),
                        "prepare-click",
                    ]
                )
            self.assertEqual(return_code, 0)

            with patch(
                "leximask.devtools.runtime_project.validate_click_runtime_project",
                side_effect=subprocess.CalledProcessError(7, ["python"]),
            ):
                return_code = runtime_project.main(
                    [
                        "--project-root",
                        str(project_root),
                        "validate-click",
                    ]
                )
            self.assertEqual(return_code, 7)

            with patch(
                "leximask.devtools.runtime_project.validate_click_runtime_project",
                return_value=project_root / "runtime" / "tests" / "workspaces" / "pallets-click",
            ):
                return_code = runtime_project.main(
                    [
                        "--project-root",
                        str(project_root),
                        "validate-click",
                    ]
                )
            self.assertEqual(return_code, 0)

    def test_main_rejects_missing_project_root(self) -> None:
        with self.assertRaises(SystemExit) as raised:
            runtime_project.main(["--project-root", "/definitely/missing", "prepare-click"])

        self.assertEqual(raised.exception.code, 2)
