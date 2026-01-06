# leximask

Deterministic rule-based tool to obfuscate sensitive terms across file names and contents. Recursively scans directories, applies safe and configurable mappings, and outputs rewritten structures with full traceability. Designed for reliability, auditability, and large-scale use in production environments.

## Status

The repository now contains an initial production-oriented Python implementation with:

- a CLI entrypoint;
- deterministic planning;
- fail-fast mapping and path validation;
- apply and reverse workflows;
- per-file sidecar metadata and a repository state manifest.

## Architecture

The codebase follows explicit layers:

- interface layer: CLI parsing and human-readable reporting;
- application layer: planning, apply, and reverse orchestration;
- domain layer: mapping validation, deterministic matching, and case handling;
- infrastructure layer: filesystem traversal, atomic directory replacement, and metadata persistence.

This first version favours explicitness and reversibility over aggressive optimisation.

## Mapping format

Mappings are stored in a two-column CSV file:

```csv
source,replacement
alpha,omega
token,mask
```

Rules are validated before any write:

- sources must be unique case-insensitively;
- replacements must be unique case-insensitively;
- a replacement must not also be a source;
- a replacement must not contain another replacement.

## Metadata format

LexiMask writes metadata under `.leximask/` inside the transformed repository:

- `.leximask/plan.json`: last computed dry-run plan;
- `.leximask/state.json`: applied repository state manifest;
- `.leximask/sidecars/**/*.leximask.json`: per-file sidecars with original path and exact replacement boundaries.

Sidecars store the transformed offsets and original text fragments required for exact reverse without heuristics.

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
