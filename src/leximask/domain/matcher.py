"""Deterministic matching and rewriting."""

from __future__ import annotations

from leximask.domain.casing import apply_case_pattern
from leximask.domain.models import MappingRule, Match


def rewrite_text(text: str, rules: tuple[MappingRule, ...]) -> tuple[str, tuple[Match, ...]]:
    """Rewrite text using longest non-overlapping left-to-right matching."""
    ordered_rules = tuple(
        sorted(rules, key=lambda rule: (-len(rule.source), rule.source.casefold()))
    )
    lower_text = text.casefold()
    index = 0
    output_parts: list[str] = []
    matches: list[Match] = []

    while index < len(text):
        best_rule: MappingRule | None = None
        for rule in ordered_rules:
            candidate = rule.source.casefold()
            if lower_text.startswith(candidate, index):
                best_rule = rule
                break

        if best_rule is None:
            output_parts.append(text[index])
            index += 1
            continue

        original_text = text[index : index + len(best_rule.source)]
        replacement_text = apply_case_pattern(original_text, best_rule.replacement)
        replacement_start = sum(len(part) for part in output_parts)
        output_parts.append(replacement_text)
        replacement_end = replacement_start + len(replacement_text)
        matches.append(
            Match(
                start=replacement_start,
                end=replacement_end,
                source=best_rule.source,
                original_text=original_text,
                replacement_text=replacement_text,
            )
        )
        index += len(best_rule.source)

    return "".join(output_parts), tuple(matches)
