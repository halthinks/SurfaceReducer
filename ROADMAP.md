# SurfaceReducer roadmap

## M0 — MVP core

- Durable semantic event IDs.
- Deterministic read-only reduction.
- Distinct project surfaces.
- Probe records for repeated agent inference.
- Hook-opportunity detector.
- Non-authoritative agent harness.
- Connector-authoring contract.
- CLI and core tests.

Exit: a project can feed events and probes, obtain current projected state, and receive a constrained connector/hook task for a project-local implementation.

## M1 — Durable event/replay contract

- Atomic local event journal reference implementation.
- Projection checkpoints and replay semantics.
- Crash-safe idempotency markers.
- Explicit UNKNOWN, STALE, FAILED, CANCELLED states.
- Source/currentness indexes.

Exit: implementations have a precise persistence/replay contract without requiring a specific database or storage product.

M1 implementation status (2026-10-08): atomic SQLite journal, duplicate-safe insertion, checkpoint/replay, explicit unknown/stale/failure views, owner-generation currentness and indexed source history. Executable acceptance and limitations: [docs/M1_VERIFICATION.md](docs/M1_VERIFICATION.md). Source contract: [docs/M1_DURABLE_JOURNAL.md](docs/M1_DURABLE_JOURNAL.md).

## M2 — Connector authoring kit

- Stable connector contract.
- Connector template.
- Agent instructions for locating the authoritative producer.
- Evidence/currentness/idempotency checklist.
- Acceptance-test template.
- Transport-neutral delivery requirements.

Non-goal: SurfaceReducer will not bundle GitHub, CI, systemd, database, queue, webhook, cloud, or vendor-specific connectors.

Exit: an agent can create a project-local connector for any surface without changing SurfaceReducer core.

## M3 — Project discovery

- Repository/project inventory scanner.
- Discover recurring polls, log reads, status fetches, and manual joins.
- Map each inference to an authoritative owner candidate.
- Score repeatability, cost, confidence, and blast radius.
- Emit connector-ready opportunities against the stable contract.

Exit: detector can generate ranked hook opportunities from real agent telemetry.

## M4 — Governed agent harness

- Pluggable agent interface.
- Connector/hook proposal schema.
- Static safety checks.
- Required acceptance tests generated per opportunity.
- Human/reviewer approval boundary when the host project requires one.
- No direct authority expansion.

Exit: an agent can produce an implementation-ready project-local connector patch without being able to silently redefine truth.

## M5 — Self-improving observability loop

- Observe reducer escapes.
- Cluster repeated inference gaps.
- Propose a project-local connector/hook.
- Validate emitted events against owner evidence.
- Measure reduced polling/inference after adoption.
- Retire low-value/noisy hooks.

Exit: projects measurably reduce repeated state-reconstruction work over time.

## M6 — Multi-agent / multi-project surface

- Per-agent scoped views.
- Global project projection.
- Cross-project dependency surfaces.
- Event federation without central mutation authority.
- Mission-control API and UI.

Exit: long-running agent fleets share one evidence-bound project-state substrate while every integration remains owned by its project.
