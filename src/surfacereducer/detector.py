from __future__ import annotations

from dataclasses import dataclass
from collections import defaultdict
from typing import Iterable

from .probes import Probe


@dataclass(frozen=True)
class HookOpportunity:
    surface: str
    authority: str
    repeated_question: str
    probe_count: int
    total_cost: int
    recommended_event: str
    rationale: str


def _event_name(surface: str, question: str) -> str:
    base = "_".join(part for part in surface.lower().replace("-", "_").split() if part)
    if "fail" in question.lower():
        return f"{base}_failed"
    if "complete" in question.lower() or "done" in question.lower():
        return f"{base}_completed"
    if "run" in question.lower() or "progress" in question.lower():
        return f"{base}_running"
    return f"{base}_changed"


def detect_hook_opportunities(probes: Iterable[Probe], *, min_count: int = 3, min_total_cost: int = 3) -> list[HookOpportunity]:
    groups: dict[tuple[str, str, str], list[Probe]] = defaultdict(list)
    for probe in probes:
        if probe.repeatable and probe.surface and probe.authority and probe.question:
            groups[(probe.surface, probe.authority, probe.question)].append(probe)
    out: list[HookOpportunity] = []
    for (surface, authority, question), rows in groups.items():
        total = sum(row.cost for row in rows)
        if len(rows) < min_count or total < min_total_cost:
            continue
        out.append(HookOpportunity(
            surface=surface,
            authority=authority,
            repeated_question=question,
            probe_count=len(rows),
            total_cost=total,
            recommended_event=_event_name(surface, question),
            rationale=(
                "Repeated agent inference is occurring for a stable project surface; "
                "instrument the authoritative producer after durable state is written."
            ),
        ))
    return sorted(out, key=lambda row: (-row.total_cost, -row.probe_count, row.surface))
