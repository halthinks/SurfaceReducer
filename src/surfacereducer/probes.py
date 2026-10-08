from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any


@dataclass(frozen=True)
class Probe:
    surface: str
    question: str
    method: str
    authority: str
    cost: int
    repeatable: bool
    observed_at: float
    context: dict[str, Any]


def make_probe(*, surface: str, question: str, method: str, authority: str,
               cost: int = 1, repeatable: bool = True,
               observed_at: float | None = None, context: dict[str, Any] | None = None) -> Probe:
    if cost < 1:
        raise ValueError("cost must be positive")
    return Probe(
        surface=surface.strip(),
        question=question.strip(),
        method=method.strip(),
        authority=authority.strip(),
        cost=cost,
        repeatable=bool(repeatable),
        observed_at=float(time.time() if observed_at is None else observed_at),
        context=dict(context or {}),
    )
