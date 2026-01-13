# leximask

Deterministic rule-based tool to obfuscate sensitive terms across file names and contents. Recursively scans directories, applies safe and configurable mappings, and outputs rewritten structures with full traceability. Designed for reliability, auditability, and large-scale use in production environments.

## Status

The repository now contains an initial production-oriented Python implementation with:

- a CLI entrypoint;
- deterministic planning;
- fail-fast mapping and path validation;
- apply and reverse workflows;
- per-file sidecar metadata and a repository state manifest;
- immutable saved plans with source and transformed digests.

## Architecture

The codebase follows explicit layers:

- interface layer: CLI parsing and human-readable reporting;
- application layer: planning, apply, and reverse orchestration;
- domain layer: mapping validation, deterministic matching, and case handling;
- infrastructure layer: filesystem traversal, atomic directory replacement, and metadata persistence.

This first version favours explicitness and reversibility over aggressive optimisation.

## Mapping format

Mappings are stored in a UTF-8 encoded two-column CSV file.

Expected column order:

- column 1: source term;
- column 2: replacement term.

The first row may optionally be a header. If present, it must be:

```csv
source,replacement
```

Example:

```csv
alpha,omega
token,mask
client,project
```

Format rules:

- each non-empty row must contain exactly two columns;
- leading and trailing whitespace around each cell is stripped during loading;
- empty source values are rejected;
- empty replacement values are rejected;
- matching is case-insensitive, but original casing is preserved through sidecar metadata;
- source terms may match substrings inside file names, directory names, and file contents.

Validation rules enforced before any write:

- sources must be unique case-insensitively;
- replacements must be unique case-insensitively;
- a replacement must not also be a source;
- a replacement must not contain another replacement.

Operational implications:

- rule order in the CSV file does not define execution order;
- matching is deterministic: longest match first, non-overlapping, left to right;
- a malformed or conflicting mapping file causes `leximask plan` to fail before generating any writable output.

## Metadata format

LexiMask writes metadata under `.leximask/` inside the transformed repository:

- `.leximask/plan.json`: last computed dry-run plan;
- `.leximask/state.json`: applied repository state manifest;
- `.leximask/sidecars/**/*.leximask.json`: per-file sidecars with original path and exact replacement boundaries.

Sidecars store the transformed offsets and original text fragments required for exact reverse without heuristics.
`apply` consumes the saved plan artifact rather than recomputing from the mapping file. `reverse` verifies transformed file digests and sidecar consistency before restoring any content.

## Usage

Plan a transformation:

```bash
leximask plan --input ./repo --mapping ./mapping.csv
```

Apply the last stored plan:

```bash
leximask apply --input ./repo
```

Reverse a previous apply:

```bash
leximask reverse --input ./repo
```

## Notes

- Only supported text file types are processed in this version.
- Unsupported files outside ignored internal directories cause planning to fail.
- Internal directories such as `.git` and `.leximask` are preserved and ignored by scanning.
- `apply` fails if any planned source file changed after `plan`.
- `reverse` fails if transformed files or sidecars drift from the recorded metadata.

## Developer workflow

Run the current validation set:

```bash
make test
```

Inspect the CLI:

```bash
make cli
```
