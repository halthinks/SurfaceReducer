from surfacereducer import build_hook_tasks, detect_hook_opportunities, make_event, make_probe, reduce_events


def test_duplicate_event_is_idempotent():
    e = make_event(producer="ci", kind="ci_completed", surface="ci", state="PASSED", source={"sha":"a"*40}, operation={"job":"1"}, qualification_scope="source_ci", observed_at=2)
    state = reduce_events([e, e])
    assert state.revision == 1
    assert state.surfaces["ci"].state == "PASSED"


def test_older_event_cannot_replace_newer_surface_state():
    old = make_event(producer="ci", kind="ci_running", surface="ci", state="RUNNING", source={"sha":"a"*40}, operation={"job":"1"}, qualification_scope="source_ci", observed_at=1)
    new = make_event(producer="ci", kind="ci_completed", surface="ci", state="PASSED", source={"sha":"a"*40}, operation={"job":"1"}, qualification_scope="source_ci", observed_at=3)
    state = reduce_events([new, old])
    assert state.surfaces["ci"].state == "PASSED"


def test_project_surfaces_remain_distinct():
    ci = make_event(producer="ci", kind="ci_completed", surface="ci", state="PASSED", source={}, operation={}, qualification_scope="ci", observed_at=1)
    deploy = make_event(producer="runtime", kind="runtime_verified", surface="runtime", state="VERIFIED", source={}, operation={}, qualification_scope="runtime", observed_at=2)
    state = reduce_events([ci, deploy])
    assert set(state.surfaces) == {"ci", "runtime"}


def test_repeated_expensive_probe_becomes_hook_opportunity():
    probes = [make_probe(surface="ci", question="Is qualification still running?", method="poll queue", authority="canonical-ci-owner", cost=2, observed_at=i) for i in range(3)]
    rows = detect_hook_opportunities(probes)
    assert len(rows) == 1
    assert rows[0].recommended_event == "ci_running"
    assert rows[0].total_cost == 6


def test_harness_never_grants_write_authority():
    probes = [make_probe(surface="release", question="Is release complete?", method="inspect receipts", authority="release-owner", cost=1, observed_at=i) for i in range(3)]
    task = build_hook_tasks(detect_hook_opportunities(probes))[0]
    assert task.write_authority_granted is False
    assert "idempotent" in task.instruction
