"""Mapping loading and validation."""

from __future__ import annotations

import csv
from pathlib import Path

from leximask.domain.models import MappingRule
from leximask.errors import ValidationError


def load_mapping_rules(mapping_path: Path) -> tuple[MappingRule, ...]:
    """Load mapping rules from a two-column CSV file."""
    if not mapping_path.is_file():
        raise ValidationError(f"Mapping file does not exist: {mapping_path}")

    rules: list[MappingRule] = []
    with mapping_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        for row_number, row in enumerate(reader, start=1):
            if not row:
                continue
            if len(row) != 2:
                raise ValidationError(
                    f"Mapping row {row_number} must contain exactly two columns"
                )
            source = row[0].strip()
            replacement = row[1].strip()
            if row_number == 1 and source.casefold() == "source" and replacement.casefold() == "replacement":
                continue
            if not source or not replacement:
                raise ValidationError(
                    f"Mapping row {row_number} must not contain empty values"
                )
            rules.append(MappingRule(source=source, replacement=replacement))

    if not rules:
        raise ValidationError("Mapping file must contain at least one rule")

    _validate_mapping_rules(tuple(rules))
    return tuple(rules)


def _validate_mapping_rules(rules: tuple[MappingRule, ...]) -> None:
    normalised_sources = [rule.source.casefold() for rule in rules]
    normalised_replacements = [rule.replacement.casefold() for rule in rules]

    if len(set(normalised_sources)) != len(normalised_sources):
        raise ValidationError("Mapping sources must be unique case-insensitively")
    if len(set(normalised_replacements)) != len(normalised_replacements):
        raise ValidationError("Mapping replacements must be unique case-insensitively")

    replacement_source_overlap = set(normalised_sources) & set(normalised_replacements)
    if replacement_source_overlap:
        overlap = ", ".join(sorted(replacement_source_overlap))
        raise ValidationError(
            f"Replacement terms must not also be source terms: {overlap}"
        )

    for outer in rules:
        outer_normalised = outer.replacement.casefold()
        for inner in rules:
            if outer is inner:
                continue
            if inner.replacement.casefold() in outer_normalised:
                raise ValidationError(
                    "Replacement terms must not contain other replacement terms: "
                    f"{outer.replacement!r} contains {inner.replacement!r}"
                )
