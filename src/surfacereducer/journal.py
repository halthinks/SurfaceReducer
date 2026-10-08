"""Durable reference journal: SQLite transactions, replayable projections, no owner writes."""
from __future__ import annotations

from contextlib import closing
import hashlib
import json
import math
from pathlib import Path
import sqlite3
from typing import Iterable

from .events import Event, SCHEMA, make_event
from .reducer import ProjectState, _fold, reduce_events, source_marker


class EventJournal:
    """Local, single-file, crash-safe observation store (not an authority)."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS events (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL UNIQUE,
                    payload TEXT NOT NULL,
                    surface TEXT NOT NULL,
                    observed_at REAL NOT NULL,
                    source_stream TEXT,
                    source_generation INTEGER
                );
                CREATE INDEX IF NOT EXISTS events_by_source_currentness
                  ON events(surface, source_stream, source_generation DESC, observed_at DESC);
                CREATE TABLE IF NOT EXISTS projection_checkpoint (
                    id INTEGER PRIMARY KEY CHECK(id = 1),
                    last_seq INTEGER NOT NULL,
                    state_json TEXT NOT NULL,
                    state_sha256 TEXT NOT NULL
                );
            """)

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10)
        db.execute("PRAGMA busy_timeout=10000")
        db.execute("PRAGMA synchronous=FULL")
        # SQLite's rollback journal keeps both the event row and its UNIQUE
        # idempotency marker atomic, even if the writer is interrupted.
        return db

    @staticmethod
    def _encode(event: Event) -> tuple[str, str | None, int | None]:
        if event.schema != SCHEMA or not math.isfinite(event.observed_at):
            raise ValueError("unsupported event schema or nonfinite observed_at")
        expected = make_event(
            producer=event.producer, kind=event.kind, surface=event.surface,
            state=event.state, source=event.source, operation=event.operation,
            evidence=event.evidence, qualification_scope=event.qualification_scope,
            details=event.details, observed_at=event.observed_at,
        ).event_id
        if expected != event.event_id:
            raise ValueError("event_id does not match semantic payload")
        marker = source_marker(event)
        payload = json.dumps(event.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False)
        return payload, marker.stream if marker else None, marker.generation if marker else None

    def append(self, event: Event) -> bool:
        """Commit the event/unique marker together; False means already stored."""
        payload, stream, generation = self._encode(event)
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            cursor = db.execute(
                "INSERT INTO events(event_id,payload,surface,observed_at,source_stream,source_generation) "
                "VALUES (?,?,?,?,?,?) ON CONFLICT(event_id) DO NOTHING",
                (event.event_id, payload, event.surface, event.observed_at, stream, generation),
            )
            return cursor.rowcount == 1

    def append_many(self, events: Iterable[Event]) -> int:
        """Ingest a batch atomically, including all idempotency markers."""
        prepared = [(event, *self._encode(event)) for event in events]
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            accepted = 0
            for event, payload, stream, generation in prepared:
                accepted += db.execute(
                    "INSERT INTO events(event_id,payload,surface,observed_at,source_stream,source_generation) "
                    "VALUES (?,?,?,?,?,?) ON CONFLICT(event_id) DO NOTHING",
                    (event.event_id, payload, event.surface, event.observed_at, stream, generation),
                ).rowcount
            return accepted

    @staticmethod
    def _decode(payload: str) -> Event:
        event = Event(**json.loads(payload))
        EventJournal._encode(event)  # fail closed on corrupt/tampered journal rows
        return event

    def events(self) -> list[Event]:
        """Committed events in deterministic reducer order (not insertion order)."""
        with closing(self._connect()) as db:
            rows = db.execute("SELECT payload FROM events ORDER BY observed_at, event_id")
            return [self._decode(payload) for (payload,) in rows]

    def count(self) -> int:
        with closing(self._connect()) as db:
            return db.execute("SELECT COUNT(*) FROM events").fetchone()[0]

    def source_events(self, surface: str, stream: str) -> list[Event]:
        """Indexed descending owner-generation lookup; not an authority lookup."""
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT payload FROM events WHERE surface=? AND source_stream=? "
                "ORDER BY source_generation DESC, observed_at DESC, event_id DESC",
                (surface, stream),
            )
            return [self._decode(payload) for (payload,) in rows]

    def replay(self) -> ProjectState:
        """Ignore checkpoints and deterministically reduce all committed events."""
        return reduce_events(self.events())

    @staticmethod
    def _checkpoint(db: sqlite3.Connection) -> tuple[int, ProjectState] | None:
        row = db.execute("SELECT last_seq,state_json,state_sha256 FROM projection_checkpoint WHERE id=1").fetchone()
        if row is None:
            return None
        last_seq, serialized, digest = row
        if hashlib.sha256(serialized.encode("utf-8")).hexdigest() != digest:
            return None
        try:
            state = ProjectState.from_dict(json.loads(serialized))
            if not isinstance(last_seq, int) or last_seq < 0 or state.revision > last_seq:
                return None
            return last_seq, state
        except (TypeError, ValueError, KeyError, AttributeError):
            return None

    def project(self) -> ProjectState:
        """Restore a verified checkpoint, catch up, and atomically checkpoint.

        An out-of-order observation invalidates the incremental fast path,
        because reduce_events sorts by (observed_at, event_id). Rebuild then.
        """
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            checkpoint = self._checkpoint(db)
            last_seq = db.execute("SELECT COALESCE(MAX(seq),0) FROM events").fetchone()[0]
            state = ProjectState()
            rebuild = checkpoint is None or checkpoint[0] > last_seq
            if not rebuild:
                start, state = checkpoint
                rows = db.execute(
                    "SELECT payload,observed_at,event_id FROM events WHERE seq>?",
                    (start,),
                ).fetchall()
                # Existing history is canonically ordered; only a suffix can
                # be folded without replaying all historical observations.
                boundary = (state.updated_at, state.last_event_id) if state.last_event_id else None
                if boundary is not None and any((stamp, eid) < boundary for _, stamp, eid in rows):
                    rebuild = True
                else:
                    for payload, _, _ in sorted(rows, key=lambda r: (r[1], r[2])):
                        _fold(state, self._decode(payload))
            if rebuild:
                rows = db.execute("SELECT payload FROM events ORDER BY observed_at,event_id")
                state = reduce_events(self._decode(payload) for (payload,) in rows)
            serialized = json.dumps(state.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False)
            db.execute(
                "INSERT INTO projection_checkpoint(id,last_seq,state_json,state_sha256) VALUES(1,?,?,?) "
                "ON CONFLICT(id) DO UPDATE SET last_seq=excluded.last_seq, "
                "state_json=excluded.state_json, state_sha256=excluded.state_sha256",
                (last_seq, serialized, hashlib.sha256(serialized.encode("utf-8")).hexdigest()),
            )
            return state
