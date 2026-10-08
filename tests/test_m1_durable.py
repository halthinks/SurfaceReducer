"""Executable M1 durability, currentness, and failure contract."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import json
import sqlite3
import subprocess
import sys

import pytest

from surfacereducer import EventJournal, make_event, reduce_events
from surfacereducer.cli import main


def event(*, generation=None, source_id="sha-a", stream="main", state="RUNNING",
          at=1.0, kind="ci_transition", surface="ci", scope="source_ci"):
    source = {"sha": source_id}
    if generation is not None:
        source["currentness"] = {
            "stream": stream, "generation": generation, "source_id": source_id,
        }
    return make_event(
        producer="owner", kind=kind, surface=surface, state=state,
        source=source, operation={"run": str(at)},
        qualification_scope=scope, evidence=[{"receipt": "signed-by-owner"}], observed_at=at,
    )


def test_duplicates_are_atomic_across_instances_and_threads(tmp_path):
    db = tmp_path / "journal.sqlite"
    j1 = EventJournal(db)
    j2 = EventJournal(db)
    e = event(state="PASSED", at=1)
    with ThreadPoolExecutor(max_workers=8) as pool:
        inserted = list(pool.map(lambda j: j.append(e), [j1, j2] * 12))
    assert inserted.count(True) == 1
    assert j1.count() == 1
    assert j1.project().revision == 1
    assert j2.project().to_dict() == j1.replay().to_dict()
    assert not j2.append(replace(e, observed_at=99))  # stable semantic ID
    assert j2.count() == 1


def test_replay_equals_reducer_after_restart_and_out_of_order_repair(tmp_path):
    path = tmp_path / "journal.sqlite"
    j = EventJournal(path)
    late = event(generation=2, source_id="sha-b", state="PASSED", at=5, kind="done")
    early = event(generation=1, source_id="sha-a", state="RUNNING", at=1, kind="start")
    other = event(surface="deployment", scope="runtime", state="FAILED", at=7)
    assert j.append_many([late, other]) == 2
    assert j.project().revision == 2  # saved checkpoint, not just raw replay
    # Later insertion of an earlier observation forces complete canonical replay.
    assert j.append(early)
    recovered = EventJournal(path).project()
    assert recovered.to_dict() == EventJournal(path).replay().to_dict()
    assert recovered.to_dict() == reduce_events([late, early, other]).to_dict()
    assert recovered.history == [early.event_id, late.event_id, other.event_id]
    # Normal suffix catch-up does not need to invalidate the checkpoint.
    cancelled = event(surface="deployment", scope="runtime", state="CANCELLED", at=8)
    assert EventJournal(path).append(cancelled)
    assert EventJournal(path).project().to_dict() == EventJournal(path).replay().to_dict()
    assert EventJournal(path).project().surfaces["deployment"].state == "CANCELLED"


def test_generation_beats_observation_clock_and_rejects_stale_source(tmp_path):
    j = EventJournal(tmp_path / "journal.sqlite")
    newer = event(generation=7, source_id="sha-new", state="PASSED", at=2, kind="done")
    stale = event(generation=6, source_id="sha-old", state="FAILED", at=200, kind="old")
    assert j.append(newer)
    j.project()
    assert j.append(stale)  # historical evidence retained; projection rejected
    state = j.project()
    assert state.revision == 2
    assert state.surfaces["ci"].state == "PASSED"
    assert state.source_currentness["ci"].generation == 7
    assert state.source_currentness["ci"].source_id == "sha-new"
    assert state.to_dict() == j.replay().to_dict()
    assert [e.event_id for e in j.source_events("ci", "main")] == [newer.event_id, stale.event_id]


def test_incomparable_or_unversioned_events_cannot_override_ordered_state():
    current = event(generation=8, source_id="abc", state="FAILED", at=1)
    other_stream = event(generation=999, stream="feature", source_id="other", state="PASSED", at=100)
    wrong_scope = event(generation=999, source_id="other", state="PASSED", at=101, scope="incomparable")
    conflict = event(generation=8, source_id="different", state="PASSED", at=102)
    unversioned = event(state="PASSED", at=103)
    projection = reduce_events([current, other_stream, wrong_scope, conflict, unversioned])
    assert projection.surfaces["ci"].state == "FAILED"
    assert projection.source_currentness["ci"].source_id == "abc"
    assert projection.revision == 5  # immutable event ledger still records every observation


def test_newer_generation_can_replace_later_old_timestamp():
    old = event(generation=1, source_id="old", state="RUNNING", at=20)
    new = event(generation=2, source_id="new", state="FAILED", at=10)
    result = reduce_events([old, new])
    assert result.surfaces["ci"].state == "FAILED"
    assert result.source_currentness["ci"].generation == 2


def test_explicit_unknown_failed_cancelled_and_stale_surface_status():
    state = reduce_events([])
    assert state.surface_status("ci")["state"] == "UNKNOWN"
    failed = event(generation=1, state="FAILED", at=10)
    assert reduce_events([failed]).surface_status("ci", now=12, stale_after=5)["state"] == "FAILED"
    expired = reduce_events([failed]).surface_status("ci", now=20, stale_after=5)
    assert expired["state"] == "STALE"
    assert expired["reported_state"] == "FAILED"
    assert expired["event_id"] == failed.event_id
    cancelled = event(generation=1, state="CANCELLED", at=11)
    assert reduce_events([cancelled]).surface_status("ci")["state"] == "CANCELLED"
    unknown = event(generation=1, state="UNKNOWN", at=12)
    assert reduce_events([unknown]).surface_status("ci")["state"] == "UNKNOWN"
    with pytest.raises(ValueError):
        state.surface_status("ci", now=12, stale_after=-1)
    with pytest.raises(ValueError):
        reduce_events([failed]).surface_status("ci", now=12, stale_after=-1)


def test_interrupted_event_write_and_checkpoint_transaction_rollback(tmp_path):
    path = tmp_path / "journal.sqlite"
    j = EventJournal(path)
    committed = event(generation=1, at=1)
    pending = event(generation=2, at=2)
    j.append(committed)
    j.project()
    # Crash a separate process without COMMIT while it holds the SQLite write lock.
    # SQLite's rollback journal must restore both event rows and the checkpoint.
    script = """
import json, sqlite3, os, sys
path, payload = sys.argv[1], sys.argv[2]
db = sqlite3.connect(path)
db.execute('BEGIN IMMEDIATE')
e = json.loads(payload)
db.execute('INSERT INTO events(event_id,payload,surface,observed_at,source_stream,source_generation) VALUES (?,?,?,?,?,?)', (e['event_id'],payload,e['surface'],e['observed_at'],'main',2))
db.execute("UPDATE projection_checkpoint SET state_json='torn' WHERE id=1")
os._exit(0)
"""
    proc = subprocess.run([sys.executable, "-c", script, str(path), json.dumps(pending.to_dict())], check=True)
    assert proc.returncode == 0
    reopened = EventJournal(path)
    assert reopened.count() == 1
    assert reopened.project().to_dict() == reduce_events([committed]).to_dict()
    assert reopened.append(pending)
    assert reopened.project().to_dict() == reduce_events([committed, pending]).to_dict()


def test_corrupted_checkpoint_is_ignored_and_rebuilt(tmp_path):
    path = tmp_path / "journal.sqlite"
    j = EventJournal(path)
    a, b = event(generation=1, at=1), event(generation=2, at=2)
    j.append_many([a, b])
    j.project()
    with sqlite3.connect(path) as db:
        db.execute("UPDATE projection_checkpoint SET state_json='partial' WHERE id=1")
    assert EventJournal(path).project().to_dict() == reduce_events([a, b]).to_dict()


def test_invalid_marker_and_forged_event_id_fail_closed(tmp_path):
    j = EventJournal(tmp_path / "journal.sqlite")
    good = event(generation=1)
    with pytest.raises(ValueError, match="event_id"):
        j.append(replace(good, event_id="0" * 64))
    invalid = event(generation=1)
    tampered_source = {**invalid.source, "currentness": {"stream": "main", "generation": True, "source_id": "abc"}}
    # A correctly hashed but semantically invalid currentness field is still refused.
    forged = make_event(producer="owner", kind=invalid.kind, surface="ci", state="RUNNING", source=tampered_source,
                        operation=invalid.operation, qualification_scope="source_ci", evidence=invalid.evidence, observed_at=1)
    with pytest.raises(ValueError, match="source.currentness"):
        j.append(forged)
    assert j.count() == 0


def test_atomic_batch_validation_and_cli_roundtrip(tmp_path, capsys):
    path = tmp_path / "journal.sqlite"
    a = event(generation=1, at=1)
    b = event(generation=2, at=2)
    j = EventJournal(path)
    with pytest.raises(ValueError):
        j.append_many([a, replace(b, event_id="broken")])
    assert j.count() == 0
    events_path = tmp_path / "events.jsonl"
    events_path.write_text("\n".join(json.dumps(e.to_dict()) for e in [a, b, a]) + "\n")
    assert main(["journal-append", str(path), str(events_path)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result == {"accepted": 2, "stored": 2}
    assert main(["journal-state", str(path), "--surface", "missing"]) == 0
    assert json.loads(capsys.readouterr().out)["state"] == "UNKNOWN"
    assert main(["journal-replay", str(path)]) == 0
    assert json.loads(capsys.readouterr().out) == j.project().to_dict()


def test_immutable_ledger_survives_restart_without_checkpoint(tmp_path):
    path = tmp_path / "journal.sqlite"
    e = event(state="FAILED", at=1)
    journal = EventJournal(path)
    journal.append(e)
    # No checkpoint created yet. Reopen and reconstruct from the durable journal.
    assert EventJournal(path).project().to_dict() == reduce_events([e]).to_dict()


def test_seeded_stream_matches_full_replay_after_every_checkpoint(tmp_path):
    import random
    rng = random.Random(20261008)
    j = EventJournal(tmp_path / "journal.sqlite")
    candidates = []
    for i in range(60):
        candidates.append(event(
            generation=rng.randrange(0, 8),
            source_id=f"sha-{rng.randrange(0, 8)}",
            state=rng.choice(["RUNNING", "PASSED", "FAILED", "CANCELLED", "UNKNOWN"]),
            at=rng.randrange(0, 20),
            kind=f"event-{i}",
        ))
    rng.shuffle(candidates)
    committed = []
    for e in candidates:
        assert j.append(e)
        committed.append(e)
        j = EventJournal(j.path)  # simulate separate process/session opening the DB
        assert j.project().to_dict() == reduce_events(committed).to_dict()
        assert j.project().to_dict() == j.replay().to_dict()
    assert j.count() == len(committed)
