import pytest

from surfacereducer import ConnectorContract, build_hook_tasks, detect_hook_opportunities, make_probe


def test_connector_contract_is_transport_agnostic():
    contract = ConnectorContract(
        connector_id="project.ci",
        surface="ci",
        authority="canonical-ci-owner",
        event_kinds=("ci_running", "ci_completed"),
        delivery="whatever-the-host-project-uses",
        source_identity="exact git sha",
        operation_identity="typed job reference",
        evidence="durable receipt hash",
        replay="semantic event id / duplicate-safe delivery",
        failure_semantics="explicit UNKNOWN/FAILED/STALE",
    )
    contract.validate()
    assert "github" not in contract.delivery.lower()
    assert "systemd" not in contract.delivery.lower()


def test_connector_contract_requires_event_kind():
    contract = ConnectorContract(
        connector_id="project.empty",
        surface="ci",
        authority="owner",
        event_kinds=(),
        delivery="callback",
        source_identity="sha",
        operation_identity="job",
        evidence="receipt",
        replay="idempotent",
        failure_semantics="explicit",
    )
    with pytest.raises(ValueError):
        contract.validate()


def test_harness_instructs_agent_to_modify_host_project():
    probes = [
        make_probe(
            surface="ci",
            question="Is qualification still running?",
            method="poll queue",
            authority="canonical-ci-owner",
            cost=2,
            observed_at=i,
        )
        for i in range(3)
    ]
    task = build_hook_tasks(detect_hook_opportunities(probes))[0]
    assert task.implementation_location == "host_project"
    assert task.write_authority_granted is False
    assert "Choose the transport that fits the host project" in task.instruction
    assert "credential authority" in task.instruction
