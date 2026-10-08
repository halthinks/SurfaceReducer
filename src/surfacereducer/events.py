from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import time
from typing import Any

SCHEMA = "surfacereducer/event/v1"


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


@dataclass(frozen=True)
class Event:
    schema: str
    event_id: str
    producer: str
    kind: str
    surface: str
    state: str
    source: dict[str, Any]
    operation: dict[str, Any]
    evidence: list[dict[str, str]]
    observed_at: float
    qualification_scope: str
    details: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def make_event(*, producer: str, kind: str, surface: str, state: str,
               source: dict[str, Any], operation: dict[str, Any],
               qualification_scope: str, evidence: list[dict[str, str]] | None = None,
               details: dict[str, Any] | None = None, observed_at: float | None = None) -> Event:
    if not all(isinstance(x, str) and x.strip() for x in (producer, kind, surface, state, qualification_scope)):
        raise ValueError("event identity fields are required")
    semantic = {
        "producer": producer,
        "kind": kind,
        "surface": surface,
        "state": state,
        "source": dict(source),
        "operation": dict(operation),
        "evidence": list(evidence or []),
        "qualification_scope": qualification_scope,
        "details": dict(details or {}),
    }
    event_id = hashlib.sha256(_canonical(semantic)).hexdigest()
    return Event(
        schema=SCHEMA,
        event_id=event_id,
        observed_at=float(time.time() if observed_at is None else observed_at),
        **semantic,
    )
