from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable

from .detector import HookOpportunity


@dataclass(frozen=True)
class HookTask:
    authority: str
    surface: str
    event_kind: str
    instruction: str
    acceptance: tuple[str, ...]
    write_authority_granted: bool = False

    def to_dict(self):
        return asdict(self)


def build_hook_tasks(opportunities: Iterable[HookOpportunity]) -> list[HookTask]:
    tasks: list[HookTask] = []
    for item in opportunities:
        tasks.append(HookTask(
            authority=item.authority,
            surface=item.surface,
            event_kind=item.recommended_event,
            instruction=(
                f"Inspect the authoritative producer '{item.authority}' for surface '{item.surface}'. "
                f"Propose the narrowest idempotent hook for event '{item.recommended_event}'. "
                "Emit only after durable owner state exists; include source/operation identity and evidence. "
                "Do not change reducer authority or mutate project state."
            ),
            acceptance=(
                "duplicate delivery is idempotent",
                "late old-source events cannot overwrite newer current state",
                "event cites authoritative evidence",
                "projection failure cannot mask producer failure",
                "hook does not grant execution or acceptance authority",
            ),
        ))
    return tasks
