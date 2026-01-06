from __future__ import annotations

import unittest

from tests import _path_setup  # noqa: F401

from leximask.domain.matcher import rewrite_text
from leximask.domain.models import MappingRule


class MatcherTests(unittest.TestCase):
    def test_prefers_longest_match_then_scans_left_to_right(self) -> None:
        rules = (
            MappingRule(source="alpha", replacement="omega"),
            MappingRule(source="alp", replacement="sig"),
        )
        transformed, matches = rewrite_text("alpha alp", rules)
        self.assertEqual(transformed, "omega sig")
        self.assertEqual([match.original_text for match in matches], ["alpha", "alp"])

    def test_preserves_simple_case_patterns(self) -> None:
        rules = (MappingRule(source="token", replacement="mask"),)
        transformed, _ = rewrite_text("token Token TOKEN", rules)
        self.assertEqual(transformed, "mask Mask MASK")
