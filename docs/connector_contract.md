# Connector contract

A SurfaceReducer connector is a project-local observation adapter. It converts one authoritative project transition into a SurfaceReducer event.

SurfaceReducer deliberately does not ship concrete connectors. The same contract applies whether the host project needs a Git hook, CI callback, database outbox, queue consumer, systemd transition, proprietary API adapter, webhook, file watcher, or another transport.

## What an agent must do

When SurfaceReducer identifies a hook opportunity, the implementing agent should:

1. Locate the authoritative owner of the fact.
2. Identify the exact transition worth observing.
3. Add the narrowest hook at that owner.
4. Emit only after the owner has durably persisted the authoritative state.
5. Populate source identity, operation identity, evidence, state, surface, and qualification scope.
6. Make duplicate delivery harmless.
7. Preserve ordering/currentness so late old-source events cannot overwrite newer state.
8. Keep secrets and unrelated payloads out of events.
9. Keep projection failure separate from owner-operation failure.
10. Prove the connector does not gain execution, merge, acceptance, deployment, or credential authority.

## Required connector declaration

Every connector should declare:

- `connector_id`: stable project-local identifier;
- `surface`: reducer surface affected;
- `authority`: authoritative producer being observed;
- `event_kinds`: lifecycle transitions emitted;
- `delivery`: transport/mechanism used by the host project;
- `source_identity`: how exact source/currentness is represented;
- `operation_identity`: how the owner operation/job/transition is identified;
- `evidence`: what durable receipt/readback/hash proves the event;
- `replay`: how duplicate/replayed delivery remains safe;
- `failure_semantics`: how UNKNOWN/FAILED/STALE states are represented.

## Acceptance requirements

A connector is acceptable only when tests prove:

- duplicate event delivery is idempotent;
- terminal success requires authoritative evidence;
- missing event delivery never implies success;
- late events cannot replace newer current state;
- wrong-source evidence cannot qualify a different source;
- projection failure cannot mask the original owner failure;
- no secret material is emitted;
- no authority is widened by the connector.

## Agent output

The normal output of the SurfaceReducer harness is a constrained implementation task. The agent is expected to modify the host project—not SurfaceReducer core—to implement the connector.

SurfaceReducer consumes events. Projects own connectors. Authoritative systems own facts.
