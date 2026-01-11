"""CLI entrypoint."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from leximask.application.executor import apply_plan, reverse_root
from leximask.application.planner import build_plan
from leximask.domain.mapping import load_mapping_rules
from leximask.errors import LexiMaskError
from leximask.infrastructure.filesystem import validate_root_directory
from leximask.infrastructure.sidecar import plan_path, write_json_file, load_json_file
from leximask.infrastructure.plan_store import deserialise_plan, serialise_plan


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="leximask")
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan_parser = subparsers.add_parser("plan", help="Build a dry-run plan")
    plan_parser.add_argument("--input", default=".", help="Input repository root")
    plan_parser.add_argument("--mapping", required=True, help="Mapping CSV file")

    apply_parser = subparsers.add_parser("apply", help="Apply a previously generated plan")
    apply_parser.add_argument("--input", default=".", help="Input repository root")

    reverse_parser = subparsers.add_parser("reverse", help="Reverse a previous apply")
    reverse_parser.add_argument("--input", default=".", help="Input repository root")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "plan":
            return _run_plan(Path(args.input), Path(args.mapping))
        if args.command == "apply":
            return _run_apply(Path(args.input))
        if args.command == "reverse":
            return _run_reverse(Path(args.input))
    except LexiMaskError as error:
        parser.exit(status=1, message=f"error: {error}\n")

    parser.exit(status=2, message="error: unsupported command\n")
    return 2


def _run_plan(input_path: Path, mapping_path: Path) -> int:
    root_directory = validate_root_directory(input_path)
    resolved_mapping_path = mapping_path.resolve()
    rules = load_mapping_rules(resolved_mapping_path)
    plan = build_plan(root_directory, resolved_mapping_path, rules)
    plan_payload = serialise_plan(plan)
    write_json_file(plan_path(root_directory), plan_payload)
    print(_render_plan_summary(plan_payload))
    return 0


def _run_apply(input_path: Path) -> int:
    root_directory = validate_root_directory(input_path)
    plan_payload = load_json_file(plan_path(root_directory))
    plan = deserialise_plan(plan_payload)
    apply_plan(plan)
    print(f"Applied LexiMask plan to {root_directory}")
    return 0


def _run_reverse(input_path: Path) -> int:
    root_directory = validate_root_directory(input_path)
    reverse_root(root_directory)
    print(f"Reversed LexiMask changes in {root_directory}")
    return 0

def _render_plan_summary(plan_payload: dict[str, object]) -> str:
    files = list(plan_payload["files"])
    directories = list(plan_payload["directories"])
    rendered = {
        "format": plan_payload["format"],
        "root_directory": plan_payload["root_directory"],
        "mapping_path": plan_payload["mapping_path"],
        "file_count": len(files),
        "directory_count": len(directories),
    }
    return json.dumps(rendered, indent=2, sort_keys=True)


if __name__ == "__main__":
    raise SystemExit(main())
