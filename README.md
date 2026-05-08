# leximask

Deterministic rule-based tool to obfuscate sensitive terms across file names and contents. Recursively scans directories, applies safe and configurable mappings, and outputs rewritten structures with full traceability. Designed for reliability, auditability, and large-scale use in production environments.

## Status

The repository now contains an initial production-oriented Python implementation with:

- a CLI entrypoint;
- deterministic planning;
- fail-fast mapping and path validation;
- apply and reverse workflows;
- transactional file and directory path rewrites for planned entries;
- empty-directory rename and restoration support;
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
- `.leximask/plan.txt`: human-readable dry-run report;
- `.leximask/state.json`: applied repository state manifest;
- `.leximask/sidecars/**/*.leximask.json`: per-file sidecars with original path and exact replacement boundaries.
- `.leximaskignore`: optional repository-local passthrough control file preserved unchanged across apply and reverse.

Sidecars store the transformed offsets and original text fragments required for exact reverse without heuristics.
`apply` consumes the saved plan artifact rather than recomputing from the mapping file. `reverse` verifies transformed file digests and sidecar consistency before restoring any content. If `.leximaskignore` exists, both `apply` and `reverse` also verify that it still matches the digest captured during planning.

## Usage

Run directly from the repository without installation:

```bash
PYTHONPATH=src python -m leximask.cli plan --mapping "<path to mapping CSV>" --input "<path to repository to obfuscate>"
PYTHONPATH=src python -m leximask.cli apply --input "<path to repository to obfuscate>"
```

Equivalent generic example:

```bash
PYTHONPATH=src python -m leximask.cli --log-level INFO plan --mapping <path to mapping CSV> --input <path to repository to obfuscate>
PYTHONPATH=src python -m leximask.cli --log-level INFO apply --input <path to repository to obfuscate>
PYTHONPATH=src python -m leximask.cli --log-level INFO reverse --input <path to repository to obfuscate>
```

If the mapping CSV is stored inside the input repository, LexiMask excludes that specific file from the transformation plan and preserves it unchanged.

If the `plan` command succeeds, it writes both `.leximask/plan.json` and `.leximask/plan.txt` inside the target repository. `apply` consumes the saved JSON plan. If `plan` fails, `apply` will fail because no plan file was produced.

Use `--log-level DEBUG|INFO|WARNING|ERROR|CRITICAL` or the `LEXIMASK_LOG_LEVEL` environment variable to control operational logging.

### `.leximaskignore`

Use `.leximaskignore` at the repository root to preserve additional unsupported artefacts unchanged instead of failing planning.

Format rules:

- UTF-8 text file, one rule per line;
- blank lines are ignored;
- lines starting with `#` are treated as comments;
- rules are repository-relative paths;
- file rules are exact relative file paths;
- directory rules must end with `/` or `\` and preserve the whole subtree;
- `/` and `\` are both accepted in the file, but rules are resolved relative to the repository root;
- absolute paths, `..`, and ambiguous root markers are rejected.

Example:

```text
# Preserve runtime artefacts that must stay outside lexical rewriting
runtime/jobs.sqlite3
runtime/archive/
service/.cache/
```

Operational behaviour:

- ignored files and directories are treated as passthrough artefacts during planning, apply, and reverse;
- passthrough paths still follow planned parent-directory renames;
- ignored paths still participate in collision detection, so unsafe target overlaps fail before any write;
- unsupported files not covered by built-in passthrough handling or `.leximaskignore` still fail planning by design.

Plan a transformation with the installed CLI:

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

### Docker usage

Build the image:

```bash
docker build -t leximask:local .
```

LexiMask stages atomic apply and reverse operations in a temporary sibling directory beside the input repository. When running as a non-root Docker user, mount a writable parent directory rather than only the repository leaf.

Run LexiMask against a repository from the host with bind mounts:

```bash
docker run --rm \
  --user "$(id -u):$(id -g)" \
  -v "<parent directory containing repository>:/work" \
  -v "<path to mapping CSV>:/mapping.csv:ro" \
  leximask:local plan --input "/work/<repository directory name>" --mapping /mapping.csv
```

Apply the saved plan from the same mounted repository:

```bash
docker run --rm \
  --user "$(id -u):$(id -g)" \
  -v "<parent directory containing repository>:/work" \
  leximask:local apply --input "/work/<repository directory name>"
```

Reverse a previous apply from Docker:

```bash
docker run --rm \
  --user "$(id -u):$(id -g)" \
  -v "<parent directory containing repository>:/work" \
  leximask:local reverse --input "/work/<repository directory name>"
```

## Notes

- Supported text inputs include source files, Markdown, JSON, YAML, CSV, TOML, INI, CFG, CONF, properties files, `Dockerfile`, `.gitignore`, `.dockerignore`, `.editorconfig`, `.env`, and related text-oriented configuration files.
- Known binary, media, database, and hidden control artefacts such as `.codex`, `.sqlite3`, and `.mp3` are preserved unchanged and do not block planning.
- Unknown unsupported artefacts can be preserved explicitly through `.leximaskignore`; unlisted unsupported files still fail planning.
- Ignored directories such as nested `.codex` trees are preserved as passthrough artefacts during apply and reverse.
- Preserved passthrough artefacts follow planned parent-directory renames and are restored on reverse.
- Empty directories inside the supported repository tree are included in planning and are renamed and restored deterministically.
- Planning fails if a target path would collide with a preserved, ignored, or excluded passthrough path.
- The Windows path-rewrite helpers are covered by dedicated unit tests and the CI matrix runs on both Linux and Windows.
- Internal directories such as `.git` and `.leximask` are preserved and ignored by scanning.
- `apply` fails if any planned source file changed after `plan`.
- `apply` and `reverse` fail if `.leximaskignore` changes after planning.
- `reverse` fails if transformed files or sidecars drift from the recorded metadata.

## Developer workflow

Run the current validation set:

```bash
make test
```

Run the 100% branch coverage gate:

```bash
make coverage
```

Run the local CI-equivalent checks:

```bash
make ci
```

Inspect the CLI:

```bash
make cli
```

The repository also includes a GitHub Actions workflow at `.github/workflows/ci.yml` that runs the 100% branch coverage gate on Python 3.12 and 3.13, then validates Docker help and bind-mounted plan/apply/reverse usage.
