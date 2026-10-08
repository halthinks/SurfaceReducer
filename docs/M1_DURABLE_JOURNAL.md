# M1 durable journal and replay contract

SurfaceReducer ships a **local reference journal**, not an authoritative store or a connector. The host project remains responsible for producing truthful, evidence-bound events after its own operation is durable. The journal only persists those observations and derives read-only project state.

## Storage and atomicity

EventJournal(path) uses the Python standard-library sqlite3 module. One database contains:

- events: append-only JSON event payloads with a UNIQUE semantic event_id. Inserting the payload and its duplicate marker is one SQLite transaction; duplicate delivery returns false.
- projection_checkpoint: one checksum-verified JSON projection and its last applied journal sequence. A checkpoint is an optimization, never independent authority.
- events_by_source_currentness: an index on surface, source stream, generation, and observation timestamp.

SQLite transactions use BEGIN IMMEDIATE, with synchronous=FULL. An uncommitted insert or checkpoint is rolled back after a writer crash. A committed event survives an interruption before checkpoint creation and is folded in at the next project() call. A missing, invalid, or checksum-mismatched checkpoint triggers full replay of committed events. If new observations sort before the checkpoint's last canonical event, project() also replays all events rather than introducing a different history order.

EventJournal.append(event) returns true only for a newly committed event. append_many(events) validates the batch before beginning its atomic insert transaction and returns the newly inserted count. A repeated semantic ID is a no-op: the originally committed observed_at remains stored. Invalid schema, forged semantic ID, invalid source ordering or nonfinite timestamps are rejected. Deleting or editing the database directly is outside the contract.

EventJournal.events() returns committed observations in reducer order; replay() ignores checkpoints; project() restores/catches up and atomically writes a checkpoint. For any valid committed journal, project().to_dict() and replay().to_dict() equal reduce_events(journal.events()).to_dict().

## Source ordering: do not compare hashes or arrival clocks

The M0 event schema remains valid. For authoritative, monotonic source ordering, an emitting host may add an owner-assigned currentness token inside event.source:

~~~json
{
  "sha": "exact-source-identity",
  "currentness": {
    "stream": "main",
    "generation": 12,
    "source_id": "exact-source-identity"
  }
}
~~~

generation is a nonnegative integer, assigned monotonically by the authoritative owner **within one comparable stream**. source_id distinguishes sources at the same generation. Use a stable qualification_scope for that stream.

For each projected surface, the index stores the accepted stream, qualification scope, generation and source identity. An older generation cannot replace a newer one even if its observed_at is later. Equal generations may advance their lifecycle state only with the same source_id. Unversioned, conflicting, different-scope or unrelated-stream observations are retained as history but cannot displace an already ordered current surface. When changing to a different incomparable owner/stream, expose a distinct surface name rather than claiming a fabricated global ordering. A newer generation may supersede an older one even when the owner's observation clock runs backward.

Events without currentness retain the original M0 timestamp fallback until an ordered event becomes current. For historical/replay order, all events are sorted by (observed_at, event_id), and duplicate IDs are handled once. No Git SHA, wall-clock delivery time, or connector transport is treated as source order.

## Explicit unknown and failure semantics

ProjectState.surface_status("ci") returns UNKNOWN with reason no_event if nothing authoritative was received. With stale_after=N and an optional now, an expired observation is presented as STALE with its reported_state and provenance retained; this is a read-only freshness view, not an owner transition. FAILED, CANCELLED, UNKNOWN and STALE emitted by a host remain explicit states (as do existing M0 states such as RUNNING or PASSED). None imply an authoritative operation was performed by SurfaceReducer.

A projection must not turn missing or stale evidence into success. Consumer-specific clock/TTL policy belongs to the host. Authoritative terminal success evidence must be validated at the host connector/owner boundary. SurfaceReducer cannot manufacture that evidence.

## Usage (no runtime dependencies)

~~~python
from surfacereducer import EventJournal, make_event

journal = EventJournal("/var/lib/my-project/surfaces.sqlite")
event = make_event(
    producer="host-ci", kind="ci_failed", surface="ci",
    state="FAILED", source={"currentness": {
        "stream": "main", "generation": 12, "source_id": "commit-abc"
    }},
    operation={"run": "owner-run-42"}, evidence=[{"receipt": "owner-evidence-42"}],
    qualification_scope="source_ci",
)
journal.append(event)            # true only for a new semantic event
state = journal.project()        # restore checkpoint, catch up and checkpoint
print(state.surface_status("ci", stale_after=300))
assert state.to_dict() == journal.replay().to_dict()
~~~

The CLI adds journal-append DATABASE EVENTS.jsonl, journal-state DATABASE [--surface NAME --stale-after SECONDS] and journal-replay DATABASE. Existing reduce and detect-hooks commands continue to work unchanged.

The SQLite file is a **single-host local reference implementation**. Store it on a durable local filesystem, back it up as host policy requires, and avoid copying a live database without a SQLite-consistent backup. Multi-host transport, retention/compaction, replication, and vendor integrations belong outside this M1 core. The journal is not an operation scheduler or a substitute for authoritative owner readback.
