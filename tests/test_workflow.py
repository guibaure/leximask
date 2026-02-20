from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class WorkflowIntegrationTests(unittest.TestCase):
    def test_plan_apply_reverse_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "repo"
            root.mkdir()
            (root / "src").mkdir()
            (root / "src" / "alpha").mkdir()
            (root / "src" / "alpha" / "alpha.py").write_text(
                "print('Alpha token')\n",
                encoding="utf-8",
            )
            (root / "README.md").write_text("Alpha token\n", encoding="utf-8")
            mapping_path = Path(temporary_directory) / "mapping.csv"
            mapping_path.write_text("source,replacement\nalpha,omega\ntoken,mask\n", encoding="utf-8")

            plan_result = self._run_cli("plan", "--input", str(root), "--mapping", str(mapping_path))
            plan_data = json.loads((root / ".leximask" / "plan.json").read_text(encoding="utf-8"))
            plan_report = (root / ".leximask" / "plan.txt").read_text(encoding="utf-8")
            self.assertEqual(plan_data["format"], "leximask/plan/v1")
            self.assertTrue(plan_data["files"][0]["transformed_text"])
            self.assertTrue(plan_data["files"][0]["source_digest"])
            self.assertEqual(plan_result.stdout, plan_report)
            self.assertIn("LexiMask Plan Report", plan_report)
            self.assertIn("Directory actions:", plan_report)
            self.assertIn("File actions:", plan_report)

            self._run_cli("apply", "--input", str(root))
            self.assertTrue((root / "src" / "omega" / "omega.py").is_file())
            self.assertFalse((root / "src" / "alpha" / "alpha.py").exists())
            self.assertFalse((root / "src" / "alpha").exists())
            self.assertEqual(
                (root / "src" / "omega" / "omega.py").read_text(encoding="utf-8"),
                "print('Omega mask')\n",
            )
            self.assertTrue((root / ".leximask" / "state.json").is_file())
            self.assertTrue(
                (root / ".leximask" / "sidecars" / "src" / "omega" / "omega.py.leximask.json").is_file()
            )

            self._run_cli("reverse", "--input", str(root))
            self.assertTrue((root / "src" / "alpha" / "alpha.py").is_file())
            self.assertEqual(
                (root / "src" / "alpha" / "alpha.py").read_text(encoding="utf-8"),
                "print('Alpha token')\n",
            )
            self.assertEqual((root / "README.md").read_text(encoding="utf-8"), "Alpha token\n")
            self.assertFalse((root / ".leximask").exists())

    def test_fails_on_unsupported_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "repo"
            root.mkdir()
            (root / "binary.bin").write_bytes(b"\x00\x01")
            mapping_path = Path(temporary_directory) / "mapping.csv"
            mapping_path.write_text("source,replacement\nalpha,omega\n", encoding="utf-8")

            result = self._run_cli(
                "plan",
                "--input",
                str(root),
                "--mapping",
                str(mapping_path),
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Unsupported files", result.stderr)

    def test_plan_supports_common_config_files_and_ignores_runtime_binaries(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "repo"
            root.mkdir()
            (root / ".codex").write_text("ignore me\n", encoding="utf-8")
            (root / ".git").mkdir()
            (root / ".git" / "config").write_text("[core]\nrepositoryformatversion = 0\n", encoding="utf-8")
            (root / ".gitignore").write_text("alpha\n", encoding="utf-8")
            (root / ".dockerignore").write_text("alpha\n", encoding="utf-8")
            (root / "Dockerfile").write_text("FROM alpha\n", encoding="utf-8")
            (root / "pyproject.toml").write_text("[project]\nname='alpha'\n", encoding="utf-8")
            (root / "runtime").mkdir()
            (root / "runtime" / "jobs.sqlite3").write_bytes(b"\x00\x01")
            (root / "runtime" / "archive").mkdir()
            (root / "runtime" / "archive" / "sample-fr.mp3").write_bytes(b"\x00\x01")
            mapping_path = Path(temporary_directory) / "mapping.csv"
            mapping_path.write_text("source,replacement\nalpha,omega\n", encoding="utf-8")

            self._run_cli("plan", "--input", str(root), "--mapping", str(mapping_path))
            self._run_cli("apply", "--input", str(root))

            self.assertEqual((root / ".gitignore").read_text(encoding="utf-8"), "omega\n")
            self.assertEqual((root / ".dockerignore").read_text(encoding="utf-8"), "omega\n")
            self.assertEqual((root / "Dockerfile").read_text(encoding="utf-8"), "FROM omega\n")
            self.assertIn("omega", (root / "pyproject.toml").read_text(encoding="utf-8"))
            self.assertTrue((root / ".git" / "config").is_file())
            self.assertTrue((root / "runtime" / "jobs.sqlite3").is_file())
            self.assertTrue((root / "runtime" / "archive" / "sample-fr.mp3").is_file())

    def test_passthrough_files_follow_directory_renames_and_reverse_restores_them(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "repo"
            root.mkdir()
            (root / "alpha").mkdir()
            (root / "alpha" / "alpha.txt").write_text("alpha token\n", encoding="utf-8")
            (root / "alpha" / ".codex").write_text("control\n", encoding="utf-8")
            (root / "alpha" / "runtime").mkdir()
            (root / "alpha" / "runtime" / "sample.mp3").write_bytes(b"\x00\x01")
            mapping_path = Path(temporary_directory) / "mapping.csv"
            mapping_path.write_text("source,replacement\nalpha,omega\ntoken,mask\n", encoding="utf-8")

            self._run_cli("plan", "--input", str(root), "--mapping", str(mapping_path))
            self._run_cli("apply", "--input", str(root))

            self.assertTrue((root / "omega" / "omega.txt").is_file())
            self.assertFalse((root / "alpha").exists())
            self.assertTrue((root / "omega" / ".codex").is_file())
            self.assertTrue((root / "omega" / "runtime" / "sample.mp3").is_file())

            self._run_cli("reverse", "--input", str(root))

            self.assertTrue((root / "alpha" / "alpha.txt").is_file())
            self.assertTrue((root / "alpha" / ".codex").is_file())
            self.assertTrue((root / "alpha" / "runtime" / "sample.mp3").is_file())
            self.assertFalse((root / "omega").exists())

    def test_passthrough_ignored_directories_follow_directory_renames_and_reverse_restores_them(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "repo"
            root.mkdir()
            (root / "alpha").mkdir()
            (root / "alpha" / "alpha.txt").write_text("alpha token\n", encoding="utf-8")
            (root / "alpha" / ".codex").mkdir()
            (root / "alpha" / ".codex" / "state.json").write_text("control\n", encoding="utf-8")
            mapping_path = Path(temporary_directory) / "mapping.csv"
            mapping_path.write_text("source,replacement\nalpha,omega\ntoken,mask\n", encoding="utf-8")

            self._run_cli("plan", "--input", str(root), "--mapping", str(mapping_path))
            self._run_cli("apply", "--input", str(root))

            self.assertTrue((root / "omega" / "omega.txt").is_file())
            self.assertTrue((root / "omega" / ".codex" / "state.json").is_file())
            self.assertFalse((root / "alpha").exists())

            self._run_cli("reverse", "--input", str(root))

            self.assertTrue((root / "alpha" / "alpha.txt").is_file())
            self.assertTrue((root / "alpha" / ".codex" / "state.json").is_file())
            self.assertFalse((root / "omega").exists())

    def test_empty_directories_are_renamed_and_restored(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "repo"
            root.mkdir()
            (root / "alpha").mkdir()
            (root / "alpha" / "empty").mkdir()
            (root / "alpha" / "empty" / "nested").mkdir()
            mapping_path = Path(temporary_directory) / "mapping.csv"
            mapping_path.write_text("source,replacement\nalpha,omega\n", encoding="utf-8")

            self._run_cli("plan", "--input", str(root), "--mapping", str(mapping_path))
            plan_data = json.loads((root / ".leximask" / "plan.json").read_text(encoding="utf-8"))
            planned_directories = {
                entry["source_relative_path"]: entry["target_relative_path"]
                for entry in plan_data["directories"]
            }

            self.assertEqual(planned_directories["alpha"], "omega")
            self.assertEqual(planned_directories["alpha/empty"], "omega/empty")
            self.assertEqual(planned_directories["alpha/empty/nested"], "omega/empty/nested")

            self._run_cli("apply", "--input", str(root))

            self.assertTrue((root / "omega").is_dir())
            self.assertTrue((root / "omega" / "empty").is_dir())
            self.assertTrue((root / "omega" / "empty" / "nested").is_dir())
            self.assertFalse((root / "alpha").exists())

            self._run_cli("reverse", "--input", str(root))

            self.assertTrue((root / "alpha").is_dir())
            self.assertTrue((root / "alpha" / "empty").is_dir())
            self.assertTrue((root / "alpha" / "empty" / "nested").is_dir())
            self.assertFalse((root / "omega").exists())

    def test_plan_report_lists_changed_and_unchanged_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "repo"
            root.mkdir()
            (root / "alpha.txt").write_text("alpha\n", encoding="utf-8")
            (root / "notes.txt").write_text("leave me\n", encoding="utf-8")
            mapping_path = Path(temporary_directory) / "mapping.csv"
            mapping_path.write_text("source,replacement\nalpha,omega\n", encoding="utf-8")

            self._run_cli("plan", "--input", str(root), "--mapping", str(mapping_path))

            plan_report = (root / ".leximask" / "plan.txt").read_text(encoding="utf-8")
            self.assertIn("Changed files: 1", plan_report)
            self.assertIn("Unchanged files: 1", plan_report)
            self.assertIn("- alpha.txt -> omega.txt [matches=1]", plan_report)
            self.assertNotIn("- notes.txt -> notes.txt [matches=0]", plan_report)

    def test_log_level_info_emits_operational_logs_to_stderr(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "repo"
            root.mkdir()
            (root / "alpha.txt").write_text("alpha\n", encoding="utf-8")
            mapping_path = Path(temporary_directory) / "mapping.csv"
            mapping_path.write_text("source,replacement\nalpha,omega\n", encoding="utf-8")

            result = self._run_cli(
                "--log-level",
                "INFO",
                "plan",
                "--input",
                str(root),
                "--mapping",
                str(mapping_path),
            )

            self.assertIn("INFO leximask.application.planner Building plan", result.stderr)
            self.assertIn("INFO leximask.cli Plan artefacts written", result.stderr)

    def test_apply_fails_when_source_changes_after_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "repo"
            root.mkdir()
            (root / "alpha.txt").write_text("alpha\n", encoding="utf-8")
            mapping_path = Path(temporary_directory) / "mapping.csv"
            mapping_path.write_text("source,replacement\nalpha,omega\n", encoding="utf-8")

            self._run_cli("plan", "--input", str(root), "--mapping", str(mapping_path))
            (root / "alpha.txt").write_text("alpha changed\n", encoding="utf-8")

            result = self._run_cli("apply", "--input", str(root), check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Source file changed after planning", result.stderr)

    def test_reverse_fails_when_transformed_file_drifts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "repo"
            root.mkdir()
            (root / "alpha.txt").write_text("alpha token\n", encoding="utf-8")
            mapping_path = Path(temporary_directory) / "mapping.csv"
            mapping_path.write_text("source,replacement\nalpha,omega\ntoken,mask\n", encoding="utf-8")

            self._run_cli("plan", "--input", str(root), "--mapping", str(mapping_path))
            self._run_cli("apply", "--input", str(root))
            (root / "omega.txt").write_text("omega drift\n", encoding="utf-8")

            result = self._run_cli("reverse", "--input", str(root), check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Transformed file content drift detected", result.stderr)

    def test_apply_uses_saved_plan_even_if_mapping_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "repo"
            root.mkdir()
            (root / "alpha.txt").write_text("alpha\n", encoding="utf-8")
            mapping_path = Path(temporary_directory) / "mapping.csv"
            mapping_path.write_text("source,replacement\nalpha,omega\n", encoding="utf-8")

            self._run_cli("plan", "--input", str(root), "--mapping", str(mapping_path))
            mapping_path.write_text("source,replacement\nalpha,sigma\n", encoding="utf-8")

            self._run_cli("apply", "--input", str(root))
            self.assertTrue((root / "omega.txt").is_file())
            self.assertFalse((root / "sigma.txt").exists())

    def test_mapping_file_inside_input_root_is_excluded_from_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "repo"
            root.mkdir()
            (root / "alpha.txt").write_text("alpha\n", encoding="utf-8")
            mapping_path = root / "mapping.csv"
            mapping_path.write_text("source,replacement\nalpha,omega\n", encoding="utf-8")

            self._run_cli("plan", "--input", str(root), "--mapping", str(mapping_path))
            plan_data = json.loads((root / ".leximask" / "plan.json").read_text(encoding="utf-8"))
            planned_sources = {entry["source_relative_path"] for entry in plan_data["files"]}

            self.assertNotIn("mapping.csv", planned_sources)

            self._run_cli("apply", "--input", str(root))
            self.assertTrue((root / "omega.txt").is_file())
            self.assertTrue((root / "mapping.csv").is_file())
            self.assertEqual(
                (root / "mapping.csv").read_text(encoding="utf-8"),
                "source,replacement\nalpha,omega\n",
            )

    def test_plan_fails_on_file_target_collision(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "repo"
            root.mkdir()
            (root / "alpha.txt").write_text("alpha\n", encoding="utf-8")
            (root / "omega.txt").write_text("omega\n", encoding="utf-8")
            mapping_path = Path(temporary_directory) / "mapping.csv"
            mapping_path.write_text(
                "source,replacement\nalpha,omega\n",
                encoding="utf-8",
            )

            result = self._run_cli(
                "plan",
                "--input",
                str(root),
                "--mapping",
                str(mapping_path),
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("File path collision detected", result.stderr)

    def test_plan_fails_on_file_directory_target_collision(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "repo"
            root.mkdir()
            (root / "alpha.txt").mkdir()
            (root / "alpha.txt" / "note.md").write_text("alpha\n", encoding="utf-8")
            (root / "omega.txt").write_text("omega\n", encoding="utf-8")
            mapping_path = Path(temporary_directory) / "mapping.csv"
            mapping_path.write_text(
                "source,replacement\nalpha,omega\n",
                encoding="utf-8",
            )

            result = self._run_cli(
                "plan",
                "--input",
                str(root),
                "--mapping",
                str(mapping_path),
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Target path would be both a file and a directory", result.stderr)

    def test_plan_fails_when_target_file_collides_with_excluded_mapping_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "repo"
            root.mkdir()
            (root / "alpha.csv").write_text("alpha\n", encoding="utf-8")
            mapping_path = root / "mapping.csv"
            mapping_path.write_text("source,replacement\nalpha,mapping\n", encoding="utf-8")

            result = self._run_cli(
                "plan",
                "--input",
                str(root),
                "--mapping",
                str(mapping_path),
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Target file path collides with passthrough file", result.stderr)

    def test_plan_fails_when_target_file_collides_with_ignored_passthrough_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "repo"
            root.mkdir()
            (root / "alpha.txt").write_text("alpha\n", encoding="utf-8")
            (root / "alpha.sqlite3").write_bytes(b"\x00\x01")
            mapping_path = Path(temporary_directory) / "mapping.csv"
            mapping_path.write_text("source,replacement\ntxt,sqlite3\n", encoding="utf-8")

            result = self._run_cli(
                "plan",
                "--input",
                str(root),
                "--mapping",
                str(mapping_path),
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Target file path collides with passthrough file", result.stderr)

    def _run_cli(self, *arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        environment = dict(os.environ)
        source_directory = Path(__file__).resolve().parents[1] / "src"
        existing = environment.get("PYTHONPATH")
        environment["PYTHONPATH"] = (
            f"{source_directory}{os.pathsep}{existing}" if existing else str(source_directory)
        )
        command = [sys.executable, "-m", "leximask.cli", *arguments]
        return subprocess.run(
            command,
            check=check,
            text=True,
            capture_output=True,
            env=environment,
        )
