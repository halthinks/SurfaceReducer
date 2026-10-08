from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable

from .connector import REQUIRED_INVARIANTS, connector_authoring_instruction
from .detector import HookOpportunity


@dataclass(frozen=True)
class HookTask:
    authority: str
    surface: str
    event_kind: str
    instruction: str
    acceptance: tuple[str, ...]
    implementation_location: str = "host_project"
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
            instruction=connector_authoring_instruction(
                surface=item.surface,
                authority=item.authority,
                event_kind=item.recommended_event,
            ),
            acceptance=REQUIRED_INVARIANTS,
        ))
    return tasks
