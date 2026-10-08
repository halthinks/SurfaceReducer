# SurfaceReducer

SurfaceReducer is a read-only project-surface state machine plus a small hook-discovery harness for long-running agents.

The reducer consumes authoritative events and produces a durable projection of project state. A separate detector records repeated expensive inference (for example, an agent repeatedly polling CI to answer the same question) and identifies where a narrow, idempotent hook could eliminate that work.

The reducer never becomes the authority. CI, Git, deployment, acceptance systems, databases, queues, and other owners remain authoritative for their facts.

## MVP

The MVP provides:

- a deterministic event contract with stable semantic event IDs;
- read-only reduction into distinct project surfaces;
- idempotent duplicate handling and monotonic per-surface currentness;
- probe records for repeated agent inference;
- hook-opportunity detection based on repeatability and accumulated cost;
- an agent-agnostic harness that creates constrained hook tasks without write authority;
- a zero-runtime-dependency CLI;
- tests for the core safety properties.

## Why

A long-running agent should not repeatedly reconstruct project state from logs, CI queues, GitHub, processes, and conversation memory. It should ask a durable projection first, then drill into authoritative evidence only when the projection reports failure, staleness, or unknown state.

SurfaceReducer also turns repeated escape-from-the-reducer behavior into observability feedback: if agents repeatedly infer the same transition at meaningful cost, that is evidence that an authoritative hook may be missing.

## Quick start

```bash
python -m pip install -e .
pytest -q
surface-reducer detect-hooks examples/hardwareclosure_probes.jsonl
```

## Design rules

1. Reducer is read-only.
2. Owners persist their authoritative state before emitting an event.
3. Events carry source identity, operation identity, evidence, and scope.
4. Duplicate delivery is harmless.
5. Late old-source events cannot replace newer current state.
6. Missing events never imply success.
7. Hook discovery proposes instrumentation; it does not grant mutation authority.
8. Project integrations are adapters, not forks of the reducer core.

The initial architecture is distilled from the HardwareClosure reducer/lifecycle work but SurfaceReducer has no HardwareClosure dependency.
