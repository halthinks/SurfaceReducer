from __future__ import annotations

from dataclasses import asdict, dataclass, field
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
class ProjectState:
    revision: int = 0
    last_event_id: str | None = None
    updated_at: float | None = None
    surfaces: dict[str, SurfaceState] = field(default_factory=dict)
    history: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "revision": self.revision,
            "last_event_id": self.last_event_id,
            "updated_at": self.updated_at,
            "surfaces": {k: asdict(v) for k, v in sorted(self.surfaces.items())},
            "history": list(self.history),
        }


def reduce_events(events: Iterable[Event]) -> ProjectState:
    state = ProjectState()
    seen: set[str] = set()
    for event in sorted(events, key=lambda e: (e.observed_at, e.event_id)):
        if event.event_id in seen:
            continue
        seen.add(event.event_id)
        current = state.surfaces.get(event.surface)
        if current is None or event.observed_at >= current.observed_at:
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
        state.revision += 1
        state.last_event_id = event.event_id
        state.updated_at = max(state.updated_at or event.observed_at, event.observed_at)
        state.history.append(event.event_id)
    return state
