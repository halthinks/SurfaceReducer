# SurfaceReducer roadmap

## M0 — MVP core

- Durable semantic event IDs.
- Deterministic read-only reduction.
- Distinct project surfaces.
- Probe records for repeated agent inference.
- Hook-opportunity detector.
- Non-authoritative agent harness.
- CLI and core tests.

Exit: a project can feed events and probes, obtain current projected state, and receive a constrained hook proposal.

## M1 — Durable local store

- Atomic JSONL/SQLite event store.
- Projection checkpoints and replay.
- Crash-safe idempotency markers.
- Explicit UNKNOWN, STALE, FAILED, CANCELLED states.
- Source/currentness indexes.

Exit: process death cannot lose accepted events or corrupt projection state.

## M2 — Adapter SDK

- Producer adapter protocol.
- Git/GitHub adapter.
- CI/job adapter.
- systemd/process adapter.
- database/outbox adapter.
- webhook adapter.

Exit: external systems can emit the same event contract without core-specific code.

## M3 — Project discovery

- Repository/project inventory scanner.
- Discover recurring polls, log reads, status fetches, and manual joins.
- Map each inference to an authoritative owner candidate.
- Score repeatability, cost, confidence, and blast radius.

Exit: detector can generate ranked hook opportunities from real agent telemetry.

## M4 — Governed agent harness

- Pluggable agent interface.
- Hook proposal schema.
- Static safety checks.
- Required acceptance tests generated per opportunity.
- Human/reviewer approval boundary.
- No direct authority expansion.

Exit: an agent can propose an implementation-ready hook patch without being able to silently redefine truth.

## M5 — Self-improving observability loop

- Observe reducer escapes.
- Cluster repeated inference gaps.
- Propose hook.
- Validate hook against owner evidence.
- Measure reduced polling/inference after adoption.
- Retire low-value/noisy hooks.

Exit: projects measurably reduce repeated state-reconstruction work over time.

## M6 — Multi-agent / multi-project surface

- Per-agent scoped views.
- Global project projection.
- Cross-project dependency surfaces.
- Event federation without central mutation authority.
- Mission-control API and UI.

Exit: long-running agent fleets share one evidence-bound project-state substrate while preserving owner authority.
