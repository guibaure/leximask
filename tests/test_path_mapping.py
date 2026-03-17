from __future__ import annotations

import unittest
from pathlib import PureWindowsPath

from leximask.domain.path_mapping import rewrite_directory_path, rewrite_file_relative_path


class PathMappingTests(unittest.TestCase):
    def test_rewrite_directory_path_preserves_windows_path_flavour(self) -> None:
        directory_mapping = {
            PureWindowsPath("src\\alpha"): PureWindowsPath("src\\omega")
        }

        rewritten = rewrite_directory_path(
            PureWindowsPath("src\\alpha\\nested"),
            directory_mapping,
        )

        self.assertEqual(rewritten, PureWindowsPath("src\\omega\\nested"))

    def test_rewrite_file_relative_path_preserves_windows_path_flavour(self) -> None:
        directory_mapping = {
            PureWindowsPath("src\\alpha"): PureWindowsPath("src\\omega")
        }

        rewritten = rewrite_file_relative_path(
            PureWindowsPath("src\\alpha\\token.txt"),
            directory_mapping,
        )

        self.assertEqual(rewritten, PureWindowsPath("src\\omega\\token.txt"))

    def test_rewrite_directory_path_returns_windows_current_directory(self) -> None:
        rewritten = rewrite_directory_path(PureWindowsPath("."), {})

        self.assertEqual(rewritten, PureWindowsPath("."))
