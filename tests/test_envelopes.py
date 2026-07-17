"""Signal/Response/EffectRequest round-trips and effect-key stability."""

from __future__ import annotations

import uuid

import pytest

from chip.envelopes import (
    EffectRequest,
    NeedsInput,
    Response,
    ResponseKind,
    Signal,
    TrustClass,
    derive_effect_key,
)
from chip.errors import EnvelopeError


def test_signal_round_trip(make_signal):
    sig = Signal.from_dict(make_signal())
    assert sig.trust is TrustClass.HOSTILE
    again = Signal.from_dict(sig.to_dict())
    assert again == sig


def test_signal_missing_field(make_signal):
    data = make_signal()
    del data["digest"]
    with pytest.raises(EnvelopeError):
        Signal.from_dict(data)


def test_response_kinds_are_the_four_terminal_outcomes():
    assert {k.value for k in ResponseKind} == {"finding", "quiet", "abstain", "needs_input"}


def test_signal_content_round_trip(make_signal):
    marked = {"value": "hostile body text", "taint": {"trust": "hostile", "source": "s"}}
    sig = Signal.from_dict(make_signal(content=marked))
    assert sig.content == marked
    again = Signal.from_dict(sig.to_dict())
    assert again == sig
    # Absent content stays absent (not serialized).
    plain = Signal.from_dict(make_signal())
    assert plain.content is None
    assert "content" not in plain.to_dict()


def test_response_finding_with_recommendation_round_trips():
    resp = Response(
        kind=ResponseKind.FINDING,
        produced_by_chip="chip:x",
        produced_by_run="run:1",
        body={"claim": "material", "confidence": 0.8},
        recommendation={"effectKey": "cek1-abc", "action": "open-research-task"},
    )
    back = Response.from_dict(resp.to_dict())
    assert back == resp
    assert back.kind is ResponseKind.FINDING
    assert back.recommendation == {"effectKey": "cek1-abc", "action": "open-research-task"}
    # abstain and quiet also round-trip cleanly.
    for kind in (ResponseKind.ABSTAIN, ResponseKind.QUIET):
        r = Response(kind=kind, produced_by_chip="c", produced_by_run="r")
        assert Response.from_dict(r.to_dict()).kind is kind


def test_response_needs_input_round_trip():
    resp = Response(
        kind=ResponseKind.NEEDS_INPUT,
        produced_by_chip="chip:x",
        produced_by_run="run:1",
        needs_input=NeedsInput(
            question_schema="schemas/q.json",
            decision_owner="human:editor",
            expiry="2026-07-20T00:00:00Z",
            lapse_outcome="quiet",
        ),
    )
    d = resp.to_dict()
    back = Response.from_dict(d)
    assert back.needs_input is not None
    assert back.needs_input.lapse_outcome == "quiet"


def test_effect_request_round_trip():
    er = EffectRequest(
        type="recommend-research",
        effect_class="recommend",
        target_owner="owner:ideas",
        payload={"topic": "x"},
        idempotency_key=derive_effect_key("lin/1", "recommend-research", "owner:ideas", "promise#p"),
        derivation_version="cek1",
        expected_result_schema="schemas/result.json",
        originating_evidence_ref="ev:1",
        judgment_receipt_ref="rcpt:1",
    )
    assert EffectRequest.from_dict(er.to_dict()) == er


# ---- effect key stability (the safety-critical function) ----


def test_effect_key_stable_across_migration():
    """Same lineage across a 'migration' (different call sites) yields same key."""
    a = derive_effect_key("agency/report/001", "recommend-research", "owner:ideas", "promise#triage")
    b = derive_effect_key("agency/report/001", "recommend-research", "owner:ideas", "promise#triage")
    assert a == b
    assert a.startswith("cek1-")


def test_effect_key_differs_on_any_field():
    base = derive_effect_key("lin", "t", "o", "p")
    assert base != derive_effect_key("lin2", "t", "o", "p")
    assert base != derive_effect_key("lin", "t2", "o", "p")
    assert base != derive_effect_key("lin", "t", "o2", "p")
    assert base != derive_effect_key("lin", "t", "o", "p2")


def test_effect_key_rejects_run_marker_input():
    # Explicit run/attempt markers are still rejected.
    with pytest.raises(EnvelopeError):
        derive_effect_key("run:abcd", "t", "o", "p")
    with pytest.raises(EnvelopeError):
        derive_effect_key("run-abcd", "t", "o", "p")
    with pytest.raises(EnvelopeError):
        derive_effect_key("lin", "attempt-3", "o", "p")
    with pytest.raises(EnvelopeError):
        derive_effect_key("lin", "t", "o", "attempt:7")
    with pytest.raises(EnvelopeError):
        derive_effect_key("host/runs/abc/effect", "t", "o", "p")


def test_effect_key_accepts_uuid_lineage():
    # Stable source lineage keys legitimately embed UUIDs (message/entry ids).
    key = derive_effect_key(str(uuid.uuid4()), "recommend-research", "owner:ideas", "promise#p")
    assert key.startswith("cek1-")
    # An entry id embedding a UUID is fine too.
    embedded = f"entry-{uuid.uuid4()}"
    assert derive_effect_key(embedded, "t", "o", "p").startswith("cek1-")


def test_effect_key_rejects_empty():
    with pytest.raises(EnvelopeError):
        derive_effect_key("", "t", "o", "p")


def test_effect_key_no_field_boundary_collision():
    # NUL-joined so a|bc cannot collide with ab|c.
    assert derive_effect_key("a", "bc", "o", "p") != derive_effect_key("ab", "c", "o", "p")
