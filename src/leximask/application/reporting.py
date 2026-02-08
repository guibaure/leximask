"""Human-readable planning reports."""

from __future__ import annotations

from typing import Any


def render_plan_report(plan_payload: dict[str, Any]) -> str:
    files = sorted(
        list(plan_payload["files"]),
        key=lambda entry: str(entry["source_relative_path"]),
    )
    directories = sorted(
        list(plan_payload["directories"]),
        key=lambda entry: str(entry["source_relative_path"]),
    )

    renamed_directories = [
        entry
        for entry in directories
        if entry["source_relative_path"] != entry["target_relative_path"]
    ]
    changed_files = [
        entry
        for entry in files
        if entry["source_relative_path"] != entry["target_relative_path"] or entry["matches"]
    ]
    unchanged_file_count = len(files) - len(changed_files)

    lines = [
        "LexiMask Plan Report",
        f"Root directory: {plan_payload['root_directory']}",
        f"Mapping path: {plan_payload['mapping_path']}",
        f"Directory count: {len(directories)}",
        f"Renamed directories: {len(renamed_directories)}",
        f"File count: {len(files)}",
        f"Changed files: {len(changed_files)}",
        f"Unchanged files: {unchanged_file_count}",
        "",
        "Directory actions:",
    ]

    if renamed_directories:
        for entry in renamed_directories:
            lines.append(
                f"- {entry['source_relative_path']} -> {entry['target_relative_path']}"
            )
    else:
        lines.append("- none")

    lines.extend(["", "File actions:"])
    if changed_files:
        for entry in changed_files:
            source_path = entry["source_relative_path"]
            target_path = entry["target_relative_path"]
            match_count = len(entry["matches"])
            lines.append(
                f"- {source_path} -> {target_path} [matches={match_count}]"
            )
    else:
        lines.append("- none")

    return "\n".join(lines) + "\n"
