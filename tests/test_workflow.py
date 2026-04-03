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
            (root / "src" / "alpha.py").write_text(
                "print('Alpha token')\n",
                encoding="utf-8",
            )
            (root / "README.md").write_text("Alpha token\n", encoding="utf-8")
            mapping_path = Path(temporary_directory) / "mapping.csv"
            mapping_path.write_text("source,replacement\nalpha,omega\ntoken,mask\n", encoding="utf-8")

            self._run_cli("plan", "--input", str(root), "--mapping", str(mapping_path))
            plan_data = json.loads((root / ".leximask" / "plan.json").read_text(encoding="utf-8"))
            self.assertEqual(plan_data["format"], "leximask/plan/v1")

            self._run_cli("apply", "--input", str(root))
            self.assertTrue((root / "src" / "omega.py").is_file())
            self.assertEqual(
                (root / "src" / "omega.py").read_text(encoding="utf-8"),
                "print('Omega mask')\n",
            )
            self.assertTrue((root / ".leximask" / "state.json").is_file())
            self.assertTrue(
                (root / ".leximask" / "sidecars" / "src" / "omega.py.leximask.json").is_file()
            )

            self._run_cli("reverse", "--input", str(root))
            self.assertTrue((root / "src" / "alpha.py").is_file())
            self.assertEqual(
                (root / "src" / "alpha.py").read_text(encoding="utf-8"),
                "print('Alpha token')\n",
            )
            self.assertEqual((root / "README.md").read_text(encoding="utf-8"), "Alpha token\n")

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
