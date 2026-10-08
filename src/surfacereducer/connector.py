from __future__ import annotations

from dataclasses import asdict, dataclass

REQUIRED_INVARIANTS = (
    "owner state is durable before event emission",
    "duplicate delivery is idempotent",
    "late old-source events cannot overwrite newer current state",
    "terminal claims are evidence-bound",
    "projection failure cannot mask producer failure",
    "connector does not widen execution or acceptance authority",
    "events contain no secrets",
)


@dataclass(frozen=True)
class ConnectorContract:
    connector_id: str
    surface: str
    authority: str
    event_kinds: tuple[str, ...]
    delivery: str
    source_identity: str
    operation_identity: str
    evidence: str
    replay: str
    failure_semantics: str

    def to_dict(self) -> dict:
        return asdict(self)

    def validate(self) -> None:
        required = (
            self.connector_id,
            self.surface,
            self.authority,
            self.delivery,
            self.source_identity,
            self.operation_identity,
            self.evidence,
            self.replay,
            self.failure_semantics,
        )
        if not all(isinstance(value, str) and value.strip() for value in required):
            raise ValueError("connector contract fields are required")
        if not self.event_kinds or not all(isinstance(kind, str) and kind.strip() for kind in self.event_kinds):
            raise ValueError("connector must declare at least one event kind")


def connector_authoring_instruction(*, surface: str, authority: str, event_kind: str) -> str:
    return (
        f"Implement a project-local SurfaceReducer connector for surface '{surface}' "
        f"at authoritative owner '{authority}', emitting '{event_kind}'. "
        "Choose the transport that fits the host project. Emit only after authoritative state is durable. "
        "Bind exact source and operation identity, attach durable evidence, make replay idempotent, "
        "preserve currentness, represent failure/unknown explicitly, emit no secrets, "
        "and do not widen execution, merge, acceptance, deployment, or credential authority."
    )
