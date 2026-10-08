# M1 executable verification — 2026-10-08

Source baseline: main at 38aefe777854dc4250c65534ee5aa2370d6187a3 (merged PR #2). M1 adds tests/test_m1_durable.py and preserves the original tests/test_core.py and tests/test_connector_contract.py.

Local, reproducible command from the repository root:

~~~sh
PYTHONPATH=src python -m pytest -q
~~~

Recorded execution: **20 passed in 0.86s** (8 existing tests + 12 new M1 tests). Environment: Python 3.13.5, SQLite 3.46.1, pytest 9.0.2. No runtime package dependencies were added. This is local executable evidence, not a claim of VPS or GitHub-hosted CI.

M1 test coverage includes:

- Semantic duplicate insertion across distinct journal instances and simultaneous threads; first committed record wins, exactly one row/marker.
- Reopening without a checkpoint, reopening with a checkpoint and suffix catch-up, and full replay when an earlier observation arrives after a checkpoint.
- Repeated project() versus replay() versus the original reduce_events() during a deterministic, seeded 60-event mixed-state, out-of-order ingest campaign.
- A lower authoritative generation arriving with a later timestamp cannot replace the newer source.
- Higher generation can win even when observation clocks run backward; conflicting same-generation IDs, different scopes/streams and unversioned observations cannot replace an ordered surface.
- Indexed source-history ordering and persisted source-currentness.
- UNKNOWN for missing surfaces; FAILED, CANCELLED and UNKNOWN owner states; read-only STALE view retaining reported evidence.
- Separate-process termination with uncommitted event and checkpoint writes, verifying automatic rollback and restart recovery.
- Corrupted checkpoint checksum rebuilding from committed events; forged semantic IDs and invalid source ordering rejected.
- Atomic batch validation and JSONL CLI ingest/state/replay round-trip.

Test boundaries: simulated process termination exercises SQLite crash recovery, not power-cut hardware fault injection. Runtime owner authenticity and evidence validation must be tested in each host repository when its connector is implemented. This milestone changes only observation storage and projection, never the owner's state or authority.
