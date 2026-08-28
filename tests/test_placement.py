"""Placement assessment: the six rules, the gate, and the abstentions.

Every case here is drawn from the 2026-08-28 hand-run over production
telemetry, so the suite pins the verdicts the rubric was derived from rather
than verdicts invented to match the code.
"""

from __future__ import annotations

import pytest

from chip.errors import PlacementError
from chip.placement import (
    MINT,
    NO_JUDGMENT,
    NO_STANDING,
    OBSERVER,
    PARSER,
    UNDECIDABLE,
    VERDICTS,
    DayObservation,
    Placement,
    PlacementEvidence,
    assess,
    assess_all,
    source_limits,
)


def _days(
    n: int,
    calls: int,
    *,
    failures: int = 0,
    envelope: int = 0,
    start: int = 1,
) -> list[DayObservation]:
    return [
        DayObservation(f"2026-07-{start + i:02d}", calls, failures, envelope)
        for i in range(n)
    ]


def _evidence(days, *, distinct_inputs, **over) -> PlacementEvidence:
    kwargs = {"span_days": None, "dominant_motif": "", "call_site": "src/x.py:1"}
    kwargs.update(over)
    return PlacementEvidence.from_daily(
        over.pop("subject", "proj.workload"),
        days,
        distinct_inputs=distinct_inputs,
        **{k: v for k, v in kwargs.items() if k != "subject"},
    )


# -- the admission gate -----------------------------------------------------


def test_single_day_burst_fails_admission() -> None:
    """barnowl.validity_triage: 7,470 calls in one day is a batch job."""
    ev = _evidence(_days(1, 7470), distinct_inputs=2339)
    p = assess(ev)
    assert p.verdict == NO_STANDING
    assert p.confidence == "high"
    assert p.rationale[0].rule == "burst"
    assert not p.is_candidate


def test_standing_relationship_is_admitted() -> None:
    ev = _evidence(_days(20, 100), distinct_inputs=50, declares_output_contract=True)
    p = assess(ev)
    assert p.rationale[0].rule == "standing"
    assert p.verdict == MINT


def test_high_activity_with_modest_peak_is_standing_not_episodic() -> None:
    """Regression: a peak share just over 0.15 flipped a plainly-standing
    workload (trawler.lookup_synthesis, active every day of its span) to
    "episodic", and printed "active on only 100% of days"."""
    days = _days(20, 100) + [DayObservation("2026-07-21", 380)]
    ev = _evidence(days, distinct_inputs=2200)
    p = assess(ev)
    assert p.measures["activityRatio"] == 1.0
    assert p.measures["peakShare"] > 0.15
    assert p.rationale[0].rule == "standing"
    assert p.verdict != UNDECIDABLE


def test_episodic_without_state_knowledge_abstains() -> None:
    """keel.evaluator.source_score: active 29% of days. Admission turns on
    cross-run state, which a call ledger cannot see."""
    days = _days(4, 100, start=1) + _days(1, 10, start=20)
    ev = _evidence(days, distinct_inputs=300, span_days=20)
    p = assess(ev)
    assert p.verdict == UNDECIDABLE
    assert p.confidence == "low"
    assert "cross-run state unknown" in p.missing_evidence
    assert p.rationale[-1].rule == "episodic"


def test_episodic_with_state_is_admitted() -> None:
    days = _days(4, 100, start=1) + _days(1, 10, start=20)
    ev = _evidence(
        days,
        distinct_inputs=30,
        span_days=20,
        has_cross_run_state=True,
        declares_output_contract=True,
    )
    p = assess(ev)
    assert p.verdict == MINT
    assert p.rationale[0].rule == "episodic-stateful"


def test_episodic_without_state_is_rejected() -> None:
    days = _days(4, 100, start=1) + _days(1, 10, start=20)
    ev = _evidence(days, distinct_inputs=30, span_days=20, has_cross_run_state=False)
    p = assess(ev)
    assert p.verdict == NO_STANDING
    assert p.confidence == "high"


def test_episodic_reason_names_the_measure_that_failed() -> None:
    """A verdict that cites the wrong number is worse than one citing none."""
    days = _days(4, 100, start=1) + _days(1, 10, start=20)
    sparse = assess(_evidence(days, distinct_inputs=300, span_days=20))
    assert "active on only" in sparse.rationale[-1].says

    concentrated = _days(19, 10) + [DayObservation("2026-07-20", 900)]
    p = assess(_evidence(concentrated, distinct_inputs=500))
    assert "fell on a single day" in p.rationale[-1].says


# -- verdicts ---------------------------------------------------------------


def test_no_judgment_stage_is_ruled_out_by_construction() -> None:
    """magpie.appraisal_embeddings: embeddings, nothing to evict."""
    ev = _evidence(_days(30, 1000), distinct_inputs=20000, emits_judgment=False)
    p = assess(ev)
    assert p.verdict == NO_JUDGMENT
    assert p.confidence == "high"
    # Checked before the admission gate: out of scope, not merely low-scoring.
    assert len(p.rationale) == 1


def test_envelope_failure_yields_an_observer() -> None:
    """barnowl.hg_verify: 79% failure, all terminal-envelope, no model needed."""
    ev = _evidence(
        _days(50, 12000, failures=9500, envelope=9500),
        distinct_inputs=96464,
        dominant_motif="SommProvidersExhausted",
        emits_judgment=True,
    )
    p = assess(ev)
    assert p.verdict == OBSERVER
    assert p.confidence == "high"
    assert p.is_candidate
    assert "SommProvidersExhausted" in p.rationale[-1].says


def test_judgment_failure_does_not_yield_an_observer() -> None:
    """Same failure rate, but the failures are not envelope-shaped."""
    ev = _evidence(
        _days(50, 12000, failures=9500, envelope=0),
        distinct_inputs=96464,
        declares_output_contract=True,
    )
    assert assess(ev).verdict != OBSERVER


def test_novel_inputs_route_to_a_parser() -> None:
    """barnowl.artifact_extract shape: one distinct input per call."""
    ev = _evidence(_days(48, 230), distinct_inputs=11040, declares_output_contract=True)
    p = assess(ev)
    assert p.verdict == PARSER
    assert not p.is_candidate
    assert p.rationale[-1].rule == "novel-inputs"


def test_recurring_inputs_route_to_a_chip_rung() -> None:
    """keel.ask.synthesis: 8 calls per distinct input over 48 days."""
    ev = _evidence(_days(48, 180), distinct_inputs=1086, declares_output_contract=True)
    p = assess(ev)
    assert p.verdict == MINT
    assert p.confidence == "medium"


# -- honesty ----------------------------------------------------------------


def test_undeclared_output_contract_caps_confidence_on_rung_verdicts() -> None:
    """Falsifiability is the ladder's hinge; without an output contract it is
    not checkable, so the rung is a proposal rather than a finding."""
    days = _days(48, 180)
    declared = assess(_evidence(days, distinct_inputs=1086, declares_output_contract=True))
    undeclared = assess(_evidence(days, distinct_inputs=1086))
    assert declared.verdict == undeclared.verdict == MINT
    assert declared.confidence == "medium"
    assert undeclared.confidence == "low"
    assert "output contract undeclared" in undeclared.missing_evidence
    assert "output contract undeclared" not in declared.missing_evidence


def test_observer_verdict_survives_an_undeclared_output_contract() -> None:
    """An observer's promise is a count, so it does not need one."""
    ev = _evidence(
        _days(50, 12000, failures=9500, envelope=9500),
        distinct_inputs=96464,
        emits_judgment=True,
    )
    p = assess(ev)
    assert p.verdict == OBSERVER
    assert "output contract undeclared" not in p.missing_evidence


def test_unresolved_call_site_is_recorded_as_a_gap() -> None:
    ev = _evidence(_days(20, 100), distinct_inputs=50, call_site="")
    assert "code location unresolved" in assess(ev).missing_evidence


def test_cost_decides_nothing() -> None:
    """The largest observed loss — 495,130 calls — cost nothing."""
    free = [DayObservation(d.date, d.calls, d.failures, d.envelope_failures, 0.0) for d in _days(50, 12000, failures=9500, envelope=9500)]
    paid = [DayObservation(d.date, d.calls, d.failures, d.envelope_failures, 99.0) for d in _days(50, 12000, failures=9500, envelope=9500)]
    a = assess(_evidence(free, distinct_inputs=96464, emits_judgment=True))
    b = assess(_evidence(paid, distinct_inputs=96464, emits_judgment=True))
    assert a.verdict == b.verdict == OBSERVER
    assert a.confidence == b.confidence


def test_assess_is_pure() -> None:
    ev = _evidence(_days(20, 100), distinct_inputs=50, declares_output_contract=True)
    assert assess(ev).to_dict() == assess(ev).to_dict()


# -- reporting --------------------------------------------------------------


def test_assess_all_leads_with_proposals() -> None:
    records = [
        _evidence(_days(1, 500), distinct_inputs=400, subject="p.burst"),
        _evidence(
            _days(50, 12000, failures=9500, envelope=9500),
            distinct_inputs=96464,
            subject="p.storm",
            emits_judgment=True,
        ),
        _evidence(
            _days(48, 180), distinct_inputs=1086, subject="p.routine",
            declares_output_contract=True,
        ),
    ]
    order = [p.subject for p in assess_all(records)]
    assert order == ["p.storm", "p.routine", "p.burst"]


def test_explain_names_the_verdict_and_its_reasons() -> None:
    p = assess(_evidence(_days(1, 500), distinct_inputs=400))
    text = p.explain()
    assert "no-standing-relationship" in text
    assert "batch run" in text
    assert "undetermined" in text


def test_source_limits_reports_coverage_and_the_union_of_gaps() -> None:
    records = [
        _evidence(_days(20, 100), distinct_inputs=50, subject="p.decided", call_site=""),
        _evidence(
            _days(4, 100, start=1) + _days(1, 10, start=20),
            distinct_inputs=300,
            span_days=20,
            subject="p.abstained",
        ),
    ]
    limits = source_limits(assess_all(records), expires_at="2026-09-28T00:00:00Z")
    assert limits["coverage"] == 0.5
    assert limits["coverageGaps"] == sorted(set(limits["coverageGaps"]))
    assert "code location unresolved" in limits["coverageGaps"]
    assert "cross-run state unknown" in limits["coverageGaps"]
    assert limits["expiresAt"] == "2026-09-28T00:00:00Z"


def test_source_limits_accepts_one_placement() -> None:
    p = assess(_evidence(_days(1, 500), distinct_inputs=400))
    assert source_limits(p)["coverage"] == 1.0


def test_source_limits_rejects_an_empty_report() -> None:
    with pytest.raises(PlacementError):
        source_limits([])


def test_every_verdict_is_in_the_closed_vocabulary() -> None:
    records = [
        _evidence(_days(1, 500), distinct_inputs=400),
        _evidence(_days(20, 100), distinct_inputs=50),
        _evidence(_days(30, 1000), distinct_inputs=20000, emits_judgment=False),
    ]
    assert all(p.verdict in VERDICTS for p in assess_all(records))


# -- malformed evidence -----------------------------------------------------


def test_day_observation_rejects_impossible_counts() -> None:
    with pytest.raises(PlacementError):
        DayObservation("2026-07-01", 10, failures=11)
    with pytest.raises(PlacementError):
        DayObservation("2026-07-01", 10, failures=2, envelope_failures=3)
    with pytest.raises(PlacementError):
        DayObservation("", 10)
    with pytest.raises(PlacementError):
        DayObservation("2026-07-01", -1)


def test_evidence_rejects_more_distinct_inputs_than_calls() -> None:
    with pytest.raises(PlacementError):
        PlacementEvidence.from_daily("p.w", _days(2, 10), distinct_inputs=100)


def test_evidence_rejects_active_days_beyond_the_span() -> None:
    with pytest.raises(PlacementError):
        PlacementEvidence.from_daily("p.w", _days(10, 10), distinct_inputs=5, span_days=3)


def test_evidence_needs_a_day_with_calls() -> None:
    with pytest.raises(PlacementError):
        PlacementEvidence.from_daily(
            "p.w", [DayObservation("2026-07-01", 0)], distinct_inputs=1
        )


def test_evidence_needs_a_subject() -> None:
    with pytest.raises(PlacementError):
        PlacementEvidence.from_daily("  ", _days(2, 10), distinct_inputs=5)


def test_assess_rejects_a_non_evidence_argument() -> None:
    with pytest.raises(PlacementError):
        assess({"subject": "p.w"})  # type: ignore[arg-type]


def test_placement_is_frozen() -> None:
    p = assess(_evidence(_days(1, 500), distinct_inputs=400))
    assert isinstance(p, Placement)
    with pytest.raises(AttributeError):
        p.verdict = MINT  # type: ignore[misc]
