# LexiMask Quality, Testing, and Production-Readiness Strategy

## 1. Objective

Define a rigorous, repository-specific quality strategy for LexiMask that maximises confidence in:

- deterministic lexical transformation;
- exact reversibility;
- destructive-operation safety;
- cross-platform behaviour;
- packaging and Docker fidelity;
- release and rollback readiness;
- long-term maintainability and auditability.

This strategy treats coverage as behavioural and operational confidence, not merely line execution.

## 2. Assumptions

Current repository scope:

- Python CLI application only;
- no long-running service;
- no HTTP or RPC API;
- no database;
- no authentication or authorisation layer;
- no background job scheduler;
- local filesystem is the primary state boundary;
- Docker image is used as a packaging and execution environment, not as a multi-service deployment stack.

Constraints and implications:

- the most severe failure mode is destructive or partially reversible repository rewriting;
- metadata integrity is a production concern, not a test-only concern;
- cross-platform path handling is a first-class risk because plans and manifests are persisted;
- packaging, installability, and container execution must be validated independently from source-tree execution;
- if APIs, databases, auth, orchestration, or background workers are introduced later, this strategy must be extended rather than assumed to cover them.

## 3. Quality Principles

LexiMask should follow these release principles:

- fail before write, not after corruption;
- prefer deterministic rules over heuristics;
- treat metadata as part of the correctness contract;
- test from source, from installed package, and from Docker;
- treat Windows and POSIX as separate operational targets;
- block releases on unproven rollback behaviour;
- require human-readable evidence for risk, validation, rollback, and operational impact.

## 4. Current Risk Profile

Highest-value risks in the current application:

- plan/apply/reverse drift between saved metadata and working tree state;
- path collisions across rewritten, ignored, and preserved artefacts;
- cross-platform serialisation defects in manifests and sidecars;
- atomic replacement rollback failures;
- unsupported file handling gaps causing partial or unsafe masking expectations;
- packaging regressions where `python -m leximask.cli` works but the installed console entrypoint fails;
- Docker success that only covers `--help` rather than real bind-mounted workflows;
- false confidence from 100% code coverage without recovery and packaging scenarios.

## 5. Complete Test Strategy

### 5.1 Unit tests

What to test:

- mapping validation;
- deterministic longest-match selection;
- case-preserving replacement logic;
- path rewrite helpers;
- ignore-rule parsing;
- metadata path serialisation;
- digest and sidecar reconstruction helpers.

Why it matters:

- these units define the correctness contract that all higher-level workflows rely on.

How to implement:

- keep logic in small pure functions where possible;
- cover nominal, edge, and invalid-input paths;
- require deterministic assertions, not approximate expectations.

Success criteria:

- each domain helper has explicit nominal and negative tests;
- platform-specific representations are normalised in tests, not assumed.

Release blockers:

- any unit failure;
- any reduction in branch coverage without deliberate sign-off;
- any platform-specific unit regression.

### 5.2 Integration tests

What to test:

- end-to-end `plan -> apply -> reverse`;
- empty-directory renames;
- ignored and preserved artefacts;
- collision detection;
- mapping file exclusion when stored inside the source tree;
- metadata drift rejection;
- apply-time and reverse-time rollback behaviour.

Why it matters:

- LexiMask’s business value is in stateful filesystem orchestration, not isolated functions.

How to implement:

- construct temporary repositories with realistic trees;
- verify both filesystem state and metadata state;
- validate failure behaviour before and after write boundaries.

Success criteria:

- transformed repositories are correct after `apply`;
- source repositories are byte-for-byte restorable after `reverse`;
- failures do not leave partially transformed trees.

Release blockers:

- any reversible-workflow regression;
- any destructive-operation rollback gap;
- any missing assertion on metadata integrity for changed workflows.

### 5.3 Installed-package smoke tests

What to test:

- wheel buildability;
- package installability into a fresh virtual environment;
- installed console script behaviour for `plan`, `apply`, and `reverse`.

Why it matters:

- source-tree execution can hide packaging defects, missing files, broken entrypoints, and build metadata errors.

How to implement:

- build a wheel from the repository;
- install it into a temporary virtual environment without external dependencies;
- run a minimal masking round-trip using the installed `leximask` entrypoint.

Success criteria:

- wheel builds cleanly;
- installed entrypoint runs outside the source tree;
- installed-package masking workflow matches source-tree behaviour.

Release blockers:

- wheel build failure;
- console entrypoint failure;
- behavioural drift between installed and source execution.

### 5.4 Docker validation

What to test:

- image build reproducibility;
- CLI help execution;
- bind-mounted `plan -> apply -> reverse` under a non-root user;
- file ownership and writable-parent-directory assumptions.

Why it matters:

- Docker is an advertised execution path and can fail even when local execution succeeds.

How to implement:

- build the image from the current tree;
- mount a writable parent directory rather than only the repository leaf;
- assert transformed and restored files from inside the container.

Success criteria:

- image builds without hidden source-tree dependencies;
- documented Docker usage works exactly as documented;
- bind-mounted runs preserve reversibility.

Release blockers:

- Docker build failure;
- bind-mount workflow failure;
- documentation and actual container behaviour diverging.

### 5.5 Cross-platform tests

What to test:

- Linux and Windows execution;
- repository-relative metadata path normalisation;
- path rewrite helpers that preserve platform semantics while persisting POSIX metadata.

Why it matters:

- persisted manifests must be interoperable across operating systems.

How to implement:

- run CI on both Windows and Linux;
- add explicit regression tests for Windows-style paths;
- keep persisted metadata format platform-neutral.

Success criteria:

- both operating systems pass the same behavioural suite;
- no metadata backslash leaks into persisted repository-relative paths.

Release blockers:

- any OS-specific failure;
- any metadata-format incompatibility.

### 5.6 Negative, abuse, and corruption tests

What to test:

- malformed mappings;
- duplicate or overlapping invalid mappings;
- corrupted or missing plan, state, or sidecar metadata;
- modified source files after planning;
- modified transformed files after apply;
- changed ignore rules after planning or apply.

Why it matters:

- safety guarantees are only credible if invalid states fail loudly and predictably.

How to implement:

- inject malformed files and mutated digests;
- assert specific errors and zero partial writes.

Success criteria:

- invalid states fail with actionable errors;
- no silent fallback or partial repair occurs.

Release blockers:

- acceptance of corrupted metadata;
- silent success on invalid or drifted state.

## 6. Test Coverage Matrix

| Surface | Current state | Required coverage | Primary tools | Release blocker |
| --- | --- | --- | --- | --- |
| Mapping rules | Present | Unit and negative tests | `unittest` | Invalid mappings accepted |
| Matcher and casing | Present | Determinism, overlap, casing | `unittest` | Non-deterministic rewrite |
| Path rewriting | Present | POSIX and Windows semantics | `unittest`, CI matrix | OS-specific divergence |
| Planner | Present | Collisions, exclusions, passthroughs | `unittest` integration tests | Unsafe plan generation |
| Apply workflow | Present | Atomicity, drift checks, sidecars | integration tests | Partial rewrite or unsafe apply |
| Reverse workflow | Present | Exact restoration, corruption rejection | integration tests | Irreversible state |
| Metadata persistence | Present | Format stability and portability | unit and integration tests | Cross-platform manifest drift |
| CLI | Present | Argument flow, logging, installed entrypoint | source and package smoke | Broken operational interface |
| Docker image | Present | Build and real workflow smoke | Docker, CI | Broken documented runtime path |
| Packaging | Present | Wheel build and install smoke | `pip wheel`, `venv` | Non-installable release artefact |
| CI workflow | Present | Linux, Windows, Docker, package smoke | GitHub Actions | Missing quality evidence |
| Observability | Minimal | Logs, operator diagnostics, runbooks | documentation, future tests | Unactionable failure reports |
| Security controls | Minimal | Dependency, secret, container, supply-chain scanning | roadmap tools | High-severity unresolved findings |
| Performance | Minimal | Corpus benchmark, memory, large-tree timing | roadmap benchmarks | SLA or cost breach |
| Recovery | Partial | Apply/reverse rollback drills | integration tests, runbooks | No safe operator recovery path |
| API/UI/DB/Auth/Jobs | Not present | Mark as not applicable until introduced | design review | Hidden scope expansion without controls |

## 7. Recommended Tools and Frameworks

### Implemented baseline

- `unittest`: standard-library functional and regression tests;
- `coverage.py`: branch and subprocess coverage gate;
- `compileall`: import-time and syntax smoke;
- `pip check`: dependency metadata consistency;
- `venv` plus `pip wheel`: installed-package validation;
- Docker CLI: image and bind-mounted runtime validation;
- GitHub Actions: cross-platform CI execution.

### Recommended next-stage tools

These are not yet introduced into the repository and should be added deliberately in separate branches:

- `ruff` for linting and import/style correctness;
- `mypy` or `pyright` for stronger type checking;
- `bandit` for Python SAST;
- `pip-audit` for dependency vulnerability scanning;
- `gitleaks` or equivalent for secret detection;
- `trivy` or `grype` for container and filesystem vulnerability scanning;
- `syft` for SBOM generation;
- GitHub CodeQL for code-scanning coverage;
- `hyperfine` or custom benchmark harnesses for repeatable performance testing.

Tool-adoption success criteria:

- tools run deterministically in CI;
- findings are triaged and severity-thresholded;
- false-positive handling is documented rather than silently ignored.

Release blockers for security and supply-chain tools:

- critical vulnerability without mitigation or exception record;
- leaked secret or credential;
- container image finding above agreed severity threshold.

## 8. Docker and Container Validation Procedures

What should be done:

- build the image on every PR;
- run a documented bind-mounted masking round-trip;
- run as a non-root user;
- verify writable-parent-directory requirement;
- record base image update policy and rebuild cadence.

Why it matters:

- container execution is part of the supported user contract;
- ownership, mount layout, and working-directory assumptions are common hidden failures.

How to implement:

- keep Docker smoke in CI;
- extend later with image scanning and digest pinning review;
- pin base image by digest once release governance is tighter.

Success criteria:

- container behaviour matches README instructions;
- no hidden dependency on the source checkout or root permissions.

Release blockers:

- Docker workflow drift from documentation;
- image build or runtime failure;
- critical image scan findings once scanning is enabled.

## 9. CI/CD Quality Gates

### Current required gates

- dependency metadata consistency via `pip check`;
- bytecode compilation via `compileall`;
- full unit and integration suite;
- 100% branch coverage gate;
- installed-package smoke on Linux;
- Docker smoke workflow;
- Linux and Windows matrix execution.

### Recommended next gates

- lint;
- static typing;
- dependency vulnerability scan;
- secret scan;
- container vulnerability scan;
- signed release artefacts and SBOM publication;
- release-candidate dry run from a clean checkout.

Success criteria:

- every gate is reproducible from the repository;
- every failure is attributable to a specific quality contract.

Release blockers:

- any failing mandatory gate;
- missing validation evidence in PR review;
- unreviewed dependency or build-pipeline change.

## 10. Security Testing Procedures

Current application-specific security scope:

- no network surface in the shipped CLI;
- main security concern is unintended repository damage, metadata tampering, and supply-chain risk.

What should be done:

- treat destructive rewrite paths as security-relevant;
- scan dependencies and container image;
- scan commits and CI for secrets;
- review path-handling changes for traversal and unsafe copy semantics;
- review logs for sensitive path or content leakage.

Why it matters:

- a local CLI can still cause severe data-loss and supply-chain incidents.

How to implement:

- keep fail-fast path validation;
- add SAST, dependency scanning, and secret scanning in later branches;
- introduce a security-review section in every PR.

Success criteria:

- no known critical dependency or image vulnerability without exception;
- no secret in repository or CI logs;
- no path-handling change merged without regression coverage.

Release blockers:

- secret exposure;
- critical unmitigated vulnerability;
- unreviewed destructive-operation logic changes.

## 11. Performance and Scalability Tests

What should be done:

- define representative repository corpora;
- measure planning time, apply time, reverse time, and memory footprint;
- test repositories with many small files, large text files, deep trees, and many mappings.

Why it matters:

- line coverage does not reveal algorithmic cost, repeated copies, or memory blow-ups.

How to implement:

- create benchmark fixtures outside the unit suite;
- record baseline timings in documentation;
- fail benchmark jobs only on sustained regression thresholds, not transient noise.

Success criteria:

- documented throughput and memory baselines;
- regression threshold agreed and enforced.

Release blockers:

- severe regression against baseline;
- inability to process the documented supported scale.

## 12. Reliability, Backup, and Disaster-Recovery Tests

What should be done:

- test rollback after failures during atomic replacement;
- test sidecar loss and corruption handling;
- test operator recovery instructions after interrupted apply or reverse;
- document pre-run backup expectations for high-value repositories.

Why it matters:

- this tool transforms live repository trees and can destroy trust if recovery is unclear.

How to implement:

- maintain failure-injection tests around staging and rename operations;
- document a recovery runbook;
- require pre-production dry runs on disposable copies before high-value usage.

Success criteria:

- failures leave the source tree recoverable or intentionally blocked with clear operator action;
- recovery steps are documented and reproducible.

Release blockers:

- no documented rollback path;
- untested failure mode near filesystem replacement boundary.

## 13. Observability and Monitoring Requirements

Current state:

- operator-facing logs exist but are minimal.

Required baseline:

- structured, severity-based logs;
- clear log events for plan build, apply start/end, reverse start/end, and validation failures;
- no secret or content-heavy log leakage;
- runbook references for common failure messages.

Future observability if service deployment is introduced:

- metrics for operation latency, failure counts, and rollback incidence;
- traceable job identifiers;
- alerting for repeated operational failures.

Release blockers:

- opaque or misleading operator errors;
- logs that expose sensitive repository content.

## 14. Documentation Requirements

Required documentation set:

- user README for normal operation;
- mapping-format contract;
- metadata-format contract;
- Docker usage instructions;
- quality strategy and acceptance criteria;
- PR template with validation and rollback evidence;
- future recovery runbook and benchmark baseline once introduced.

Success criteria:

- documentation matches executable behaviour;
- CI paths exercise documented commands directly where practical.

Release blockers:

- documentation drift on supported execution paths;
- undocumented operator-critical assumptions.

## 15. Production-Readiness Acceptance Criteria

LexiMask is release-ready only if:

- Linux and Windows CI pass;
- Docker smoke passes;
- installed-package smoke passes;
- branch coverage gate passes;
- destructive-operation failure paths remain covered;
- metadata portability contract is enforced;
- README and strategy documentation match actual behaviour;
- PR evidence includes validation, risk, rollback, and security notes.

For higher-trust enterprise adoption, add:

- lint and static typing gates;
- dependency, secret, and image scanning;
- signed artefacts and SBOM generation;
- benchmark baselines and recovery runbooks.

## 16. Risks, Blind Spots, and Mitigations

| Risk | Why it is easy to miss | Mitigation |
| --- | --- | --- |
| Superficial 100% coverage | line execution can miss packaging, Docker, or rollback scenarios | require package and Docker smoke, not only coverage |
| Metadata portability drift | local tests on one OS can hide persisted-path bugs | enforce POSIX metadata paths and Windows CI |
| Partial filesystem replacement | happy-path tests hide rollback breakage | keep failure-injection tests around rename boundaries |
| Unsupported-file surprises | users assume “text-like” means universally supported | document supported formats and require explicit ignore rules |
| Docker documentation drift | `--help` passing does not prove mounted workflows | test documented bind-mounted commands in CI |
| Supply-chain blind spots | no runtime dependencies can create false confidence | add dependency and image scanning in later phases |
| Weak recovery posture | reverse exists, but operator recovery may still be unclear | add runbook and pre-run backup guidance |
| Hidden scope expansion | future API or database additions may inherit no controls | mark non-present surfaces as not applicable until introduced |

## 17. Implementation Roadmap

### Phase 1: enforced now

- branch and subprocess coverage gate;
- Linux and Windows CI matrix;
- Docker bind-mounted smoke workflow;
- installed-package smoke;
- compile-time smoke;
- PR evidence template;
- repository-specific quality strategy document.

### Phase 2: next dedicated branches

- lint and type-check branch;
- dependency and secret scanning branch;
- container scanning and SBOM branch;
- benchmark harness and scale-baseline branch;
- recovery runbook and operational drill branch.

### Phase 3: governance maturity

- signed releases;
- controlled exception process for vulnerabilities;
- periodic base-image refresh policy;
- formal release checklist and release-candidate promotion workflow.

## 18. Concrete Example Test Cases

### Functional

- plan a repository with overlapping mapping rules and assert longest-match wins;
- apply a plan where the mapping file is inside the repository and assert it remains preserved;
- reverse a transformed repository and assert exact content restoration.

### Negative

- load a mapping with duplicate replacements and assert failure before planning;
- modify a source file after planning and assert `apply` fails;
- modify a transformed file after apply and assert `reverse` fails.

### Filesystem safety

- inject failure after moving the original tree but before replacing it and assert rollback restoration;
- preserve ignored binary artefacts across parent-directory renames;
- detect file-versus-directory target collisions before any write.

### Cross-platform

- serialise a Windows-style relative path into metadata and assert POSIX separators are persisted;
- deserialise legacy backslash metadata and assert reverse still works.

### Packaging and Docker

- install from built wheel into a clean virtual environment and run `plan -> apply -> reverse`;
- run the Docker image as a non-root user with a bind-mounted parent directory and verify the same round-trip.
