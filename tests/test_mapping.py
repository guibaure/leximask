from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests import _path_setup  # noqa: F401

from leximask.domain.mapping import load_mapping_rules
from leximask.errors import ValidationError


class MappingValidationTests(unittest.TestCase):
    def test_rejects_duplicate_replacements(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            mapping_path = Path(temporary_directory) / "mapping.csv"
            mapping_path.write_text("source,replacement\nfoo,bar\nbaz,bar\n", encoding="utf-8")
            with self.assertRaises(ValidationError):
                load_mapping_rules(mapping_path)

    def test_rejects_replacement_source_overlap(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            mapping_path = Path(temporary_directory) / "mapping.csv"
            mapping_path.write_text("source,replacement\nfoo,bar\nbar,baz\n", encoding="utf-8")
            with self.assertRaises(ValidationError):
                load_mapping_rules(mapping_path)
