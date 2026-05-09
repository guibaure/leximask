# LexiMask

## Overview

LexiMask is a deterministic, rule-based obfuscation engine engineered to securely mutate sensitive terms across file names, directory structures, and file contents. Designed for reliability, auditability, and large-scale deployment in production environments, it provides strict guarantees around traceability and rollback capabilities.

LexiMask recursively scans repositories, applies safe, configurable mappings, and outputs rewritten structures while preserving exact structural and metadata fidelity.

## Engineering Principles

LexiMask adheres to stringent enterprise engineering standards:
* **Determinism:** Execution yields identical outcomes for the same inputs.
* **Fail-Fast Validation:** Mapping and path validation strictly reject ambiguous or conflicting configurations before any mutating operation begins.
* **Auditability:** Immutable dry-run plans and applied state manifests are retained, ensuring comprehensive operational traceability.
* **Reversibility:** Transformations are structurally reversible without relying on heuristics. Exact text fragments and offsets are preserved via sidecar metadata.
* **Transactional Integrity:** File and directory rewrites are executed via atomic, transactional operations to prevent partial states.

## Architecture

The system is decoupled into explicit layers to enforce separation of concerns:

* **Interface Layer:** CLI parsing, configuration ingestion, and human-readable operational reporting.
* **Application Layer:** Orchestration of the core workflows: `plan`, `apply`, and `reverse`.
* **Domain Layer:** Mapping validation, deterministic pattern matching, and casing preservation logic.
* **Infrastructure Layer:** Filesystem traversal, atomic directory replacement, and immutable metadata persistence.

This architecture prioritises explicitness and systemic reversibility over aggressive, opaque optimisations.

## Governance and Quality Strategy

LexiMask enforces rigorous testing, release, and production-readiness criteria. Detailed repository-specific quality strategies, including CI/CD integration and release gating, are documented in `docs/quality-strategy.md`.

## Operational Guidelines

### Mapping Configuration

Transformations are driven by mappings stored in a UTF-8 encoded, two-column CSV file.

**Expected Column Order:**
1. Source term
2. Replacement term

An optional header row is supported and must strictly match:
```csv
source,replacement
```

**Example:**
```csv
alpha,omega
token,mask
client,project
```

**Validation and Execution Rules:**
* Each non-empty row must contain exactly two columns.
* Leading and trailing whitespace is stripped.
* Empty source or replacement values are strictly rejected.
* Sources and replacements must be unique case-insensitively.
* A replacement must not duplicate an existing source, nor contain another replacement as a substring.
* Lexical matching is deterministic: longest match first, non-overlapping, evaluated left to right.
* Matching is case-insensitive, but original casing is preserved and recorded in sidecar metadata for accurate reversibility.
* Source terms may match substrings inside file names, directory names, and file contents.
* A malformed or conflicting mapping file causes the `plan` phase to fail immediately, preventing any unsafe writes.

### Metadata and State Management

LexiMask persists operational state and sidecar metadata within a `.leximask/` directory in the target repository. This ensures full traceability and safe reversal:

* `.leximask/plan.json`: The immutable, deterministic dry-run plan.
* `.leximask/plan.txt`: A human-readable audit report of the plan.
* `.leximask/state.json`: The applied repository state manifest.
* `.leximask/sidecars/**/*.leximask.json`: Per-file sidecar metadata containing original path offsets and text fragments required for exact reversal.

**Important Considerations:**
* Sidecars store exact transformed offsets to guarantee heuristic-free reversion.
* Metadata employs POSIX `/` separators universally across all operating systems.
* The `apply` phase consumes the saved plan artefact (`plan.json`) strictly; it does not recompute from the mapping file.
* The `reverse` phase verifies transformed file digests and sidecar consistency prior to initiating any restoration.

### Passthrough Controls (`.leximaskignore`)

The `.leximaskignore` file, placed at the repository root, defines strict passthrough rules for artefacts that must remain unmodified. This file is preserved unchanged across `apply` and `reverse` workflows.

**Format Rules:**
* UTF-8 text file, one rule per line.
* Blank lines and lines prefixed with `#` (comments) are ignored.
* Rules must be repository-relative paths.
* Directory rules must terminate with `/` or `\` to preserve the entire subtree.
* Absolute paths, `..` traversal, and ambiguous root markers are rejected.

**Operational Behaviour:**
* Ignored files and directories are treated as passthrough artefacts; they are not scanned or mutated but are copied to the target output.
* Passthrough paths follow planned parent-directory renames.
* Ignored paths participate in collision detection; unsafe target overlaps will fail the plan phase.
* Unsupported artefacts not explicitly ignored via `.leximaskignore` will fail the planning phase by design.
* `apply` and `reverse` operations fail if the `.leximaskignore` file is modified after planning.

## Usage and Deployment

LexiMask provides a comprehensive CLI for local execution and integration into automated pipelines.

### Local CLI Execution

Run the module directly from the source tree:

```bash
# Generate a transformation plan
PYTHONPATH=src python -m leximask.cli --log-level INFO plan --mapping <path to mapping CSV> --input <path to repository>

# Apply the generated plan
PYTHONPATH=src python -m leximask.cli --log-level INFO apply --input <path to repository>

# Reverse a previously applied transformation
PYTHONPATH=src python -m leximask.cli --log-level INFO reverse --input <path to repository>
```

Alternatively, if installed as a package:

```bash
leximask plan --input ./repo --mapping ./mapping.csv
leximask apply --input ./repo
leximask reverse --input ./repo
```

**Logging:**
Operational verbosity can be controlled via the `--log-level` flag or the `LEXIMASK_LOG_LEVEL` environment variable (supported levels: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`).

### Docker Integration

For isolated or CI-driven environments, LexiMask provides a containerised distribution.

**Image Build:**
```bash
docker build -t leximask:local .
```

**Execution via Docker Bind Mounts:**
LexiMask stages atomic `apply` and `reverse` operations in a temporary sibling directory relative to the input repository. When executing as a non-root user, ensure a writable parent directory is mounted.

```bash
# Plan
docker run --rm \
  --user "$(id -u):$(id -g)" \
  -v "<parent directory containing repository>:/work" \
  -v "<path to mapping CSV>:/mapping.csv:ro" \
  leximask:local plan --input "/work/<repository directory name>" --mapping /mapping.csv

# Apply
docker run --rm \
  --user "$(id -u):$(id -g)" \
  -v "<parent directory containing repository>:/work" \
  leximask:local apply --input "/work/<repository directory name>"

# Reverse
docker run --rm \
  --user "$(id -u):$(id -g)" \
  -v "<parent directory containing repository>:/work" \
  leximask:local reverse --input "/work/<repository directory name>"
```

## System Support and Limitations

* **Supported Formats:** Text-oriented inputs are explicitly supported, including source code, Markdown, JSON, YAML, CSV, TOML, INI, CFG, CONF, properties files, `Dockerfile`, `.gitignore`, `.dockerignore`, `.editorconfig`, and `.env`.
* **Passthrough Artefacts:** Known binary, media, database, and specific control directories (e.g., `.codex`, `.sqlite3`, `.mp3`) are preserved unchanged automatically.
* **Empty Directories:** Empty directories within the supported repository tree are included in the planning phase and undergo deterministic rename and restoration.
* **Internal State:** Critical internal directories, notably `.git` and `.leximask`, are structurally preserved and excluded from mutation scanning.
* **Mapping Artefact Exception:** If the mapping CSV is stored inside the input repository, LexiMask excludes that specific file from the transformation plan and preserves it unchanged.
* **Integrity Enforcement:** The `apply` operation will safely abort if any planned source file is modified externally subsequent to the `plan` phase. Similarly, `reverse` operations fail if the transformed files or sidecar metadata drift from the recorded digest state.
* **Cross-Platform Compatibility:** Windows path-rewrite helpers are rigorously tested, and the CI matrix validates core operational parity across Linux and Windows environments.

## Developer Workflow

Local validation and quality gating commands:

```bash
# Execute unit and integration tests
make test

# Enforce 100% branch coverage gating
make coverage

# Execute bytecode compilation and installed-package smoke tests
make compile
make package-smoke

# Execute local CI parity checks
make ci

# Validate CLI interface
make cli
```

Comprehensive continuous integration is enforced via GitHub Actions (`.github/workflows/ci.yml`), verifying dependency integrity, bytecode compilation, exhaustive branch coverage, installed-package execution, and cross-platform Docker runtime compliance.
