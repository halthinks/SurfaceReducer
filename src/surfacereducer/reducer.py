from __future__ import annotations

from dataclasses import asdict, dataclass, field
import math
import time
from typing import Any, Iterable

from .events import Event


@dataclass
class SurfaceState:
    surface: str
    state: str
    source: dict[str, Any]
    operation: dict[str, Any]
    evidence: list[dict[str, str]]
    observed_at: float
    event_id: str
    qualification_scope: str


@dataclass
class SourceCurrentness:
    """Owner-provided order of one authoritative stream for a surface."""

    stream: str
    generation: int
    source_id: str
    qualification_scope: str
    event_id: str


@dataclass
class ProjectState:
    revision: int = 0
    last_event_id: str | None = None
    updated_at: float | None = None
    surfaces: dict[str, SurfaceState] = field(default_factory=dict)
    history: list[str] = field(default_factory=list)
    source_currentness: dict[str, SourceCurrentness] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "revision": self.revision,
            "last_event_id": self.last_event_id,
            "updated_at": self.updated_at,
            "surfaces": {k: asdict(v) for k, v in sorted(self.surfaces.items())},
            "history": list(self.history),
            "source_currentness": {k: asdict(v) for k, v in sorted(self.source_currentness.items())},
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProjectState:
        state = cls(
            revision=data["revision"],
            last_event_id=data["last_event_id"],
            updated_at=data["updated_at"],
            surfaces={k: SurfaceState(**v) for k, v in data["surfaces"].items()},
            history=list(data["history"]),
            source_currentness={
                k: SourceCurrentness(**v) for k, v in data["source_currentness"].items()
            },
        )
        if (type(state.revision) is not int or state.revision != len(state.history)
                or (state.last_event_id != state.history[-1] if state.history else state.last_event_id is not None)):
            raise ValueError("invalid projection checkpoint")
        return state

    def surface_status(self, surface: str, *, now: float | None = None,
                       stale_after: float | None = None) -> dict[str, Any]:
        """Read-only status. Missing and expired observations never imply success."""
        if stale_after is not None and (not math.isfinite(stale_after) or stale_after < 0):
            raise ValueError("stale_after must be a nonnegative finite duration")
        current = self.surfaces.get(surface)
        if current is None:
            return {"surface": surface, "state": "UNKNOWN", "reason": "no_event",
                    "event_id": None, "observed_at": None, "source": None}
        result = asdict(current)
        if stale_after is not None:
            if (time.time() if now is None else now) - current.observed_at > stale_after:
                result["reported_state"] = current.state
                result["state"] = "STALE"
                result["reason"] = "observation_expired"
        return result


def source_marker(event: Event) -> SourceCurrentness | None:
    """Optional, transport-neutral source.currentness stream/generation/source_id."""
    value = event.source.get("currentness")
    if value is None:
        return None
    if (not isinstance(value, dict) or set(value) != {"stream", "generation", "source_id"}
            or not isinstance(value["stream"], str) or not value["stream"].strip()
            or type(value["generation"]) is not int or value["generation"] < 0
            or not isinstance(value["source_id"], str) or not value["source_id"].strip()):
        raise ValueError("source.currentness needs stream, nonnegative integer generation and source_id")
    return SourceCurrentness(
        stream=value["stream"], generation=value["generation"],
        source_id=value["source_id"], qualification_scope=event.qualification_scope,
        event_id=event.event_id,
    )


def _fold(state: ProjectState, event: Event) -> None:
    marker = source_marker(event)
    current = state.surfaces.get(event.surface)
    index = state.source_currentness.get(event.surface)
    promote = False
    if marker is not None and index is not None:
        if marker.stream == index.stream and marker.qualification_scope == index.qualification_scope:
            if marker.generation > index.generation:
                promote = True
            elif marker.generation == index.generation and marker.source_id == index.source_id:
                promote = current is None or event.observed_at >= current.observed_at
    elif index is None:
        # Backward compatibility for M0 observations lacking ordered source metadata.
        promote = current is None or event.observed_at >= current.observed_at
    # Once an ordered source is current, an unversioned or unrelated stream may
    # be recorded in history but cannot silently supersede it.
    if promote:
        state.surfaces[event.surface] = SurfaceState(
            surface=event.surface,
            state=event.state,
            source=dict(event.source),
            operation=dict(event.operation),
            evidence=list(event.evidence),
            observed_at=event.observed_at,
            event_id=event.event_id,
            qualification_scope=event.qualification_scope,
        )
        if marker is not None:
            state.source_currentness[event.surface] = marker
    state.revision += 1
    state.last_event_id = event.event_id
    state.updated_at = (event.observed_at if state.updated_at is None
                        else max(state.updated_at, event.observed_at))
    state.history.append(event.event_id)


def reduce_events(events: Iterable[Event]) -> ProjectState:
    state = ProjectState()
    seen: set[str] = set()
    for event in sorted(events, key=lambda e: (e.observed_at, e.event_id)):
        if not math.isfinite(event.observed_at):
            raise ValueError("observed_at must be finite")
        if event.event_id in seen:
            continue
        seen.add(event.event_id)
        _fold(state, event)
    return state
