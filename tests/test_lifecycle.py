"""Lifecycle telemetry: exact-schema validation and the gating rules (spec 0.5.0)."""

from __future__ import annotations

import pytest

from chip.errors import LifecycleError
from chip.lifecycle import LifecycleEvent, validate_lifecycle_event


def _event(**over) -> dict:
    base = {
        "event": "mint",
        "at": "2026-07-17T00:00:00Z",
        "operator": "owner:desk",
        "chipAlias": "press.new-report-triage",
        "chipVersion": "0.2.0",
        "implementationDigest": "sha256:aaaa",
        "tupleKey": None,
        "receiptRef": None,
        "details": {},
    }
    base.update(over)
    return base


def test_valid_mint_event():
    validate_lifecycle_event(_event())
    ev = LifecycleEvent.from_dict(_event())
    assert ev.event == "mint"
    assert ev.tuple_key is None
    # exact round-trip
    assert ev.to_dict() == _event()


def test_unknown_event_rejected():
    with pytest.raises(LifecycleError, match="not one of"):
        validate_lifecycle_event(_event(event="frobnicate"))


def test_missing_key_rejected():
    bad = _event()
    del bad["operator"]
    with pytest.raises(LifecycleError, match="missing required keys"):
        validate_lifecycle_event(bad)


def test_extra_key_rejected():
    bad = _event()
    bad["surprise"] = 1
    with pytest.raises(LifecycleError, match="unexpected keys"):
        validate_lifecycle_event(bad)


def test_blank_required_string_rejected():
    with pytest.raises(LifecycleError):
        validate_lifecycle_event(_event(operator="  "))


def test_tuple_key_wrong_type_rejected():
    with pytest.raises(LifecycleError, match="tupleKey"):
        validate_lifecycle_event(_event(event="mint", tupleKey=123))


def test_details_must_be_object():
    with pytest.raises(LifecycleError, match="details"):
        validate_lifecycle_event(_event(details=["nope"]))


@pytest.mark.parametrize("event", ["split", "merge", "optimize"])
def test_tuple_gated_events_require_tuple_key(event):
    with pytest.raises(LifecycleError, match="tupleKey"):
        validate_lifecycle_event(_event(event=event, tupleKey=None))
    validate_lifecycle_event(_event(event=event, tupleKey="cet1-abcd"))


def test_retire_may_be_ungated():
    # Fail-closed asymmetry: adding/reshaping authority is hard, removal is
    # easy — an owning system may retire on judgment alone (spec 13.1).
    validate_lifecycle_event(_event(event="retire", tupleKey=None,
                                    details={"reason": "superseded"}))


def test_model_generation_retire_requires_baseline():
    ev = _event(event="retire", tupleKey="cet1-abcd", details={"reason": "model-generation"})
    with pytest.raises(LifecycleError, match="raw-model baseline"):
        validate_lifecycle_event(ev)
    ev["details"]["rawModelBaseline"] = "receipt:baseline-vs-chip-2026-07"
    validate_lifecycle_event(ev)


def test_non_model_generation_retire_needs_no_baseline():
    ev = _event(event="retire", tupleKey="cet1-abcd", details={"reason": "superseded"})
    validate_lifecycle_event(ev)
