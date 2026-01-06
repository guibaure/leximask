"""Case-preserving replacement helpers."""

from __future__ import annotations


def apply_case_pattern(original: str, replacement: str) -> str:
    """Apply a basic case pattern from the original token to the replacement."""
    if not original:
        return replacement
    if original.isupper():
        return replacement.upper()
    if original.islower():
        return replacement.lower()
    if len(original) > 1 and original[0].isupper() and original[1:].islower():
        return replacement.capitalize()

    transformed_characters: list[str] = []
    for index, character in enumerate(replacement):
        if index < len(original):
            transformed_characters.append(
                character.upper() if original[index].isupper() else character.lower()
            )
        else:
            transformed_characters.append(
                character.upper() if original[-1].isupper() else character.lower()
            )
    return "".join(transformed_characters)
