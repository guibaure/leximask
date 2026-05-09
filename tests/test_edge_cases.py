from __future__ import annotations

import tempfile
import unittest
from pathlib import Path, PureWindowsPath
from unittest.mock import patch

from tests import _path_setup  # noqa: F401

from leximask.application.executor import (
    _create_planned_directories,
    _materialise_restored_tree,
    _restore_text,
    _validate_apply_inputs,
    apply_plan,
    reverse_root,
)
from leximask.application.planner import PlanResult, _validate_path_collisions
from leximask.domain.casing import apply_case_pattern
from leximask.domain.mapping import load_mapping_rules
from leximask.domain.models import Match, PlannedDirectory, PlannedFile
from leximask.errors import ConflictError, MetadataError, ValidationError
from leximask.infrastructure.digests import sha256_text
from leximask.infrastructure.filesystem import (
    copy_preserved_entries,
    discover_supported_files,
    replace_directory_atomically,
    validate_root_directory,
)
from leximask.infrastructure.ignore_rules import IgnoreRules, load_ignore_rules
from leximask.infrastructure.plan_store import deserialise_plan, serialise_plan
from leximask.infrastructure.repository_paths import (
    deserialise_repository_relative_path,
    serialise_repository_relative_path,
)
from leximask.infrastructure.sidecar import load_json_file, sidecar_path, sidecar_root, state_path, write_json_file
from leximask.logging_utils import configure_logging


class EdgeCaseTests(unittest.TestCase):
    def test_case_pattern_handles_empty_and_mixed_tokens(self) -> None:
        self.assertEqual(apply_case_pattern("", "mask"), "mask")
        self.assertEqual(apply_case_pattern("aBc", "token"), "tOken")
        self.assertEqual(apply_case_pattern("abC", "token"), "toKEN")

    def test_mapping_loader_rejects_malformed_and_empty_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            missing_path = Path(temporary_directory) / "missing.csv"
            with self.assertRaisesRegex(ValidationError, "does not exist"):
                load_mapping_rules(missing_path)

            mapping_path = Path(temporary_directory) / "mapping.csv"
            mapping_path.write_text("\n", encoding="utf-8")
            with self.assertRaisesRegex(ValidationError, "at least one rule"):
                load_mapping_rules(mapping_path)

            mapping_path.write_text("source,replacement,extra\n", encoding="utf-8")
            with self.assertRaisesRegex(ValidationError, "exactly two columns"):
                load_mapping_rules(mapping_path)

            mapping_path.write_text("source,replacement\nalpha,\n", encoding="utf-8")
            with self.assertRaisesRegex(ValidationError, "empty values"):
                load_mapping_rules(mapping_path)

            mapping_path.write_text("source,replacement\nalpha,omega\nALPHA,sigma\n", encoding="utf-8")
            with self.assertRaisesRegex(ValidationError, "sources must be unique"):
                load_mapping_rules(mapping_path)

            mapping_path.write_text("source,replacement\nalpha,omega\nbeta,omega-project\n", encoding="utf-8")
            with self.assertRaisesRegex(ValidationError, "must not contain"):
                load_mapping_rules(mapping_path)

    def test_ignore_rules_reject_invalid_paths_and_normalise_valid_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            ignore_path = root / ".leximaskignore"

            ignore_path.write_text("/absolute\n", encoding="utf-8")
            with self.assertRaisesRegex(ValidationError, "repository-relative"):
                load_ignore_rules(root)

            ignore_path.write_text("../outside\n", encoding="utf-8")
            with self.assertRaisesRegex(ValidationError, "invalid"):
                load_ignore_rules(root)

            ignore_path.write_text(".\n", encoding="utf-8")
            with self.assertRaisesRegex(ValidationError, "invalid"):
                load_ignore_rules(root)

            ignore_path.write_text(
                "# comment\n\n./runtime/jobs.sqlite3\ncache\\\\\n",
                encoding="utf-8",
            )
            rules = load_ignore_rules(root)
            self.assertTrue(rules.matches_file(Path("runtime/jobs.sqlite3")))
            self.assertTrue(rules.matches_directory(Path("cache/nested")))

    def test_filesystem_helpers_cover_validation_and_preserved_file_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "repo"
            root.mkdir()
            with self.assertRaisesRegex(ValidationError, "does not exist"):
                validate_root_directory(root / "missing")

            (root / ".leximask.skip").write_text("ignored\n", encoding="utf-8")
            (root / "supported.txt").write_text("alpha\n", encoding="utf-8")
            files = discover_supported_files(root, _empty_ignore_rules())
            self.assertEqual([file.relative_path for file in files], [Path("supported.txt")])

            preserved_source = Path(temporary_directory) / "preserved-source"
            preserved_target = Path(temporary_directory) / "preserved-target"
            preserved_source.mkdir()
            preserved_target.mkdir()
            (preserved_source / ".git").write_text("file-shaped preserved entry\n", encoding="utf-8")
            copy_preserved_entries(preserved_source, preserved_target)
            self.assertEqual(
                (preserved_target / ".git").read_text(encoding="utf-8"),
                "file-shaped preserved entry\n",
            )

    def test_filesystem_reports_long_unsupported_file_list(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            for index in range(11):
                (root / f"unsupported-{index}.bin").write_bytes(b"\x00")

            with self.assertRaisesRegex(ValidationError, "and 1 more"):
                discover_supported_files(root, _empty_ignore_rules())

    def test_atomic_replace_handles_backup_file_and_rolls_back_target(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            parent = Path(temporary_directory)
            target = parent / "target"
            prepared = parent / "prepared"
            target.mkdir()
            prepared.mkdir()
            (target / "old.txt").write_text("old\n", encoding="utf-8")
            (prepared / "new.txt").write_text("new\n", encoding="utf-8")
            (parent / ".leximask-apply-backup").write_text("stale backup\n", encoding="utf-8")

            replace_directory_atomically(target, prepared, "apply")

            self.assertEqual((target / "new.txt").read_text(encoding="utf-8"), "new\n")

        with tempfile.TemporaryDirectory() as temporary_directory:
            parent = Path(temporary_directory)
            target = parent / "target"
            prepared = parent / "prepared"
            target.mkdir()
            prepared.mkdir()
            (target / "old.txt").write_text("old\n", encoding="utf-8")
            (prepared / "new.txt").write_text("new\n", encoding="utf-8")
            backup = parent / ".leximask-apply-backup"
            backup.mkdir()
            (backup / "stale.txt").write_text("stale\n", encoding="utf-8")

            replace_directory_atomically(target, prepared, "apply")

            self.assertEqual((target / "new.txt").read_text(encoding="utf-8"), "new\n")

        with tempfile.TemporaryDirectory() as temporary_directory:
            target = Path(temporary_directory) / "target"
            prepared = Path(temporary_directory) / "prepared"
            target.mkdir()
            prepared.mkdir()
            (target / "old.txt").write_text("old\n", encoding="utf-8")

            original_rename = Path.rename

            def failing_rename(path: Path, target_path: Path) -> Path:
                if path == prepared:
                    raise OSError("forced rename failure")
                return original_rename(path, target_path)

            with patch.object(Path, "rename", failing_rename):
                with self.assertRaisesRegex(OSError, "forced rename failure"):
                    replace_directory_atomically(target, prepared, "apply")

            self.assertEqual((target / "old.txt").read_text(encoding="utf-8"), "old\n")

        with tempfile.TemporaryDirectory() as temporary_directory:
            target = Path(temporary_directory) / "target"
            prepared = Path(temporary_directory) / "prepared"
            target.mkdir()
            prepared.mkdir()
            (target / "old.txt").write_text("old\n", encoding="utf-8")

            original_rename = Path.rename

            def failing_first_rename(path: Path, target_path: Path) -> Path:
                if path == target:
                    raise OSError("forced first rename failure")
                return original_rename(path, target_path)

            with patch.object(Path, "rename", failing_first_rename):
                with self.assertRaisesRegex(OSError, "forced first rename failure"):
                    replace_directory_atomically(target, prepared, "apply")

            self.assertEqual((target / "old.txt").read_text(encoding="utf-8"), "old\n")

        with tempfile.TemporaryDirectory() as temporary_directory:
            target = Path(temporary_directory) / "target"
            prepared = Path(temporary_directory) / "prepared"
            target.mkdir()
            prepared.mkdir()
            (target / "old.txt").write_text("old\n", encoding="utf-8")

            original_rename = Path.rename

            def create_partial_target_then_fail(path: Path, target_path: Path) -> Path:
                if path == prepared:
                    target_path.mkdir()
                    (target_path / "partial.txt").write_text("partial\n", encoding="utf-8")
                    raise OSError("forced partial target failure")
                return original_rename(path, target_path)

            with patch.object(Path, "rename", create_partial_target_then_fail):
                with self.assertRaisesRegex(OSError, "forced partial target failure"):
                    replace_directory_atomically(target, prepared, "apply")

            self.assertEqual((target / "old.txt").read_text(encoding="utf-8"), "old\n")

    def test_executor_validation_and_metadata_failure_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "repo"
            other_root = Path(temporary_directory) / "other"
            root.mkdir()
            other_root.mkdir()
            (root / "alpha.txt").write_text("alpha\n", encoding="utf-8")
            plan = _single_file_plan(root)

            with self.assertRaisesRegex(ValidationError, "not requested root"):
                _validate_apply_inputs(other_root, plan)

            (root / "alpha.txt").unlink()
            with self.assertRaisesRegex(ValidationError, "missing"):
                _validate_apply_inputs(root, plan)

    def test_apply_and_reverse_cleanup_staging_on_materialisation_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "repo"
            root.mkdir()
            (root / "alpha.txt").write_text("alpha\n", encoding="utf-8")
            plan = _single_file_plan(root)

            with patch(
                "leximask.application.executor._materialise_transformed_tree",
                side_effect=RuntimeError("forced apply failure"),
            ):
                with self.assertRaisesRegex(RuntimeError, "forced apply failure"):
                    apply_plan(plan)

            self.assertFalse(list(Path(temporary_directory).glob(".leximask-apply-*")))

            def remove_apply_staging_then_fail(staging_root: Path, *_args: object) -> None:
                staging_root.parent.rmdir()
                raise RuntimeError("forced apply failure without staging")

            with patch(
                "leximask.application.executor._materialise_transformed_tree",
                side_effect=remove_apply_staging_then_fail,
            ):
                with self.assertRaisesRegex(RuntimeError, "without staging"):
                    apply_plan(plan)

            write_json_file(
                state_path(root),
                {
                    "format": "leximask/state/v1",
                    "ignore_file_digest": None,
                    "mapping_path": str(root / "mapping.csv"),
                    "directories": [],
                    "files": [],
                },
            )
            with patch(
                "leximask.application.executor._materialise_restored_tree",
                side_effect=RuntimeError("forced reverse failure"),
            ):
                with self.assertRaisesRegex(RuntimeError, "forced reverse failure"):
                    reverse_root(root)

            self.assertFalse(list(Path(temporary_directory).glob(".leximask-reverse-*")))

            def remove_reverse_staging_then_fail(
                _root: Path,
                staging_root: Path,
                *_args: object,
            ) -> None:
                staging_root.parent.rmdir()
                raise RuntimeError("forced reverse failure without staging")

            with patch(
                "leximask.application.executor._materialise_restored_tree",
                side_effect=remove_reverse_staging_then_fail,
            ):
                with self.assertRaisesRegex(RuntimeError, "without staging"):
                    reverse_root(root)

    def test_reverse_rejects_invalid_state_and_sidecar_inconsistencies(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "repo"
            root.mkdir()
            write_json_file(state_path(root), {"format": "bad"})
            with self.assertRaisesRegex(MetadataError, "Unsupported state"):
                reverse_root(root)

            manifest = _single_file_manifest(root)

            with self.assertRaisesRegex(MetadataError, "missing"):
                _materialise_restored_tree(
                    root,
                    Path(temporary_directory) / "staging-missing",
                    manifest,
                    _empty_ignore_rules(),
                )

            (root / "omega.txt").write_text("omega\n", encoding="utf-8")
            sidecar = sidecar_path(sidecar_root(root), Path("omega.txt"))
            write_json_file(sidecar, {"format": "bad"})
            with self.assertRaisesRegex(MetadataError, "Unsupported sidecar"):
                _materialise_restored_tree(
                    root,
                    Path(temporary_directory) / "staging-format",
                    manifest,
                    _empty_ignore_rules(),
                )

            write_json_file(
                sidecar,
                {
                    "format": "leximask/sidecar/v1",
                    "transformed_digest": "bad",
                    "matches": [],
                },
            )
            with self.assertRaisesRegex(MetadataError, "Sidecar digest mismatch"):
                _materialise_restored_tree(
                    root,
                    Path(temporary_directory) / "staging-digest",
                    manifest,
                    _empty_ignore_rules(),
                )

            write_json_file(
                sidecar,
                {
                    "format": "leximask/sidecar/v1",
                    "transformed_digest": sha256_text("omega\n"),
                    "matches": [
                        {
                            "replacement_start": 0,
                            "replacement_end": 5,
                            "replacement_text": "omega",
                            "original_text": "alpha",
                        }
                    ],
                },
            )
            bad_manifest = dict(manifest)
            bad_manifest["files"] = [dict(manifest["files"][0], source_digest="bad")]
            with self.assertRaisesRegex(MetadataError, "integrity"):
                _materialise_restored_tree(
                    root,
                    Path(temporary_directory) / "staging-integrity",
                    bad_manifest,
                    _empty_ignore_rules(),
                )

    def test_restore_text_rejects_mismatched_boundaries(self) -> None:
        with self.assertRaisesRegex(MetadataError, "does not match"):
            _restore_text(
                "sigma\n",
                {
                    "matches": [
                        {
                            "replacement_start": 0,
                            "replacement_end": 5,
                            "replacement_text": "omega",
                            "original_text": "alpha",
                        }
                    ]
                },
            )

    def test_private_helpers_cover_noop_branches(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            destination = root / "destination"
            destination.mkdir()
            _create_planned_directories(destination, (Path("."), Path("alpha")))
            self.assertTrue((destination / "alpha").is_dir())

            missing_mapping = root / "missing.json"
            with self.assertRaisesRegex(MetadataError, "does not exist"):
                load_json_file(missing_mapping)

            with self.assertRaisesRegex(ValidationError, "Unsupported plan"):
                deserialise_plan({"format": "bad"})

            with self.assertRaisesRegex(ValidationError, "Unsupported log level"):
                configure_logging("not-a-level")

    def test_repository_relative_metadata_paths_use_posix_separators(self) -> None:
        self.assertEqual(
            serialise_repository_relative_path(PureWindowsPath("alpha/empty/nested")),
            "alpha/empty/nested",
        )
        self.assertEqual(
            deserialise_repository_relative_path("alpha\\empty\\nested"),
            Path("alpha/empty/nested"),
        )
        payload = serialise_plan(
            PlanResult(
                root_directory=Path("/repo"),
                mapping_path=Path("/mapping.csv"),
                ignore_file_digest=None,
                files=(),
                directories=(
                    PlannedDirectory(
                        PureWindowsPath("alpha/empty"),
                        PureWindowsPath("omega/empty"),
                    ),
                ),
            )
        )
        self.assertEqual(
            payload["directories"][0]["source_relative_path"],
            "alpha/empty",
        )

    def test_planner_collision_branches_are_explicit(self) -> None:
        file_a = _planned_file(Path("a.txt"), Path("target.txt"))
        file_b = _planned_file(Path("b.txt"), Path("target.txt"))
        with self.assertRaisesRegex(ConflictError, "File path collision"):
            _validate_path_collisions((file_a, file_b), (), (), ())

        _validate_path_collisions(
            (_planned_file(Path("source/file.txt"), Path("target/file.txt")),),
            (PlannedDirectory(Path("source"), Path("target")),),
            (),
            (),
        )

        dir_a = PlannedDirectory(Path("alpha"), Path("target"))
        dir_b = PlannedDirectory(Path("beta"), Path("target"))
        with self.assertRaisesRegex(ConflictError, "Directory path collision"):
            _validate_path_collisions((), (dir_a, dir_b), (), ())

        with self.assertRaisesRegex(ConflictError, "both a file and a directory"):
            _validate_path_collisions((file_a,), (PlannedDirectory(Path("source"), Path("target.txt")),), (), ())

        with self.assertRaisesRegex(ConflictError, "passthrough directory"):
            _validate_path_collisions((file_a,), (), (), (Path("target.txt"),))

        with self.assertRaisesRegex(ConflictError, "passthrough file"):
            _validate_path_collisions((), (PlannedDirectory(Path("source"), Path("target.txt")),), (Path("target.txt"),), ())

        with self.assertRaisesRegex(ConflictError, "passthrough directory"):
            _validate_path_collisions((), (PlannedDirectory(Path("source"), Path("target")),), (), (Path("target"),))

        with self.assertRaisesRegex(ConflictError, "Passthrough file target collision"):
            _validate_path_collisions((), (PlannedDirectory(Path("alpha"), Path("omega")),), (Path("alpha/file.bin"), Path("omega/file.bin")), ())


def _empty_ignore_rules() -> IgnoreRules:
    return IgnoreRules(frozenset(), frozenset(), None)


def _planned_file(source: Path, target: Path) -> PlannedFile:
    return PlannedFile(
        source_relative_path=source,
        target_relative_path=target,
        source_digest=sha256_text("alpha\n"),
        transformed_digest=sha256_text("omega\n"),
        source_text="alpha\n",
        transformed_text="omega\n",
        matches=(
            Match(
                start=0,
                end=5,
                source="alpha",
                original_text="alpha",
                replacement_text="omega",
            ),
        ),
    )


def _single_file_plan(root: Path) -> PlanResult:
    return PlanResult(
        root_directory=root,
        mapping_path=root / "mapping.csv",
        ignore_file_digest=None,
        files=(_planned_file(Path("alpha.txt"), Path("omega.txt")),),
        directories=(),
    )


def _single_file_manifest(root: Path) -> dict[str, object]:
    return {
        "format": "leximask/state/v1",
        "ignore_file_digest": None,
        "mapping_path": str(root / "mapping.csv"),
        "directories": [],
        "files": [
            {
                "original_relative_path": "alpha.txt",
                "transformed_relative_path": "omega.txt",
                "source_digest": sha256_text("alpha\n"),
                "transformed_digest": sha256_text("omega\n"),
            }
        ],
    }
