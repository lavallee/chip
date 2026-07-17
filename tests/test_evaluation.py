"""Evaluation ledger: profile swap -> unevaluated -> observe cap."""

from __future__ import annotations

import pytest

from chip.authority import EffectClass
from chip.errors import EvaluationError
from chip.evaluation import EvaluatedTuple, EvaluationLedger


def _tuple(profile="materiality-mid@1"):
    return EvaluatedTuple(
        implementation_digest="sha256:aaaa",
        gateway_profile=profile,
        served_model="provider/model-v1",
        harness="gateway/structured-attempt-v1",
    )


def test_tuple_key_is_stable_and_order_fixed():
    t1 = _tuple()
    t2 = _tuple()
    assert t1.key() == t2.key()
    assert t1.key().startswith("cet1-")


def test_empty_member_rejected():
    with pytest.raises(EvaluationError):
        EvaluatedTuple("", "p", "m", "h")


def test_recorded_tuple_is_evaluated():
    ledger = EvaluationLedger()
    t = _tuple()
    ledger.record(t, "eval-receipt:1", {"precision": 0.8}, minimums_met=True)
    assert ledger.is_evaluated(t)
    assert ledger.authority_cap_for(t) is EffectClass.PROMOTE


def test_profile_swap_drops_to_observe():
    ledger = EvaluationLedger()
    evaluated = _tuple(profile="materiality-mid@1")
    ledger.record(evaluated, "eval-receipt:1", {}, minimums_met=True)
    # A swapped profile alias is a DIFFERENT tuple; it must not inherit the result.
    swapped = _tuple(profile="materiality-mid@2")
    assert not ledger.is_evaluated(swapped)
    assert ledger.authority_cap_for(swapped) is EffectClass.OBSERVE


def test_model_swap_drops_to_observe():
    ledger = EvaluationLedger()
    ledger.record(_tuple(), "r", {}, minimums_met=True)
    other = EvaluatedTuple("sha256:aaaa", "materiality-mid@1", "provider/model-v2", "gateway/x")
    assert ledger.authority_cap_for(other) is EffectClass.OBSERVE


def test_minimums_not_met_stays_unevaluated():
    ledger = EvaluationLedger()
    t = _tuple()
    ledger.record(t, "r", {}, minimums_met=False)
    assert not ledger.is_evaluated(t)
    assert ledger.authority_cap_for(t) is EffectClass.OBSERVE


def test_record_requires_receipt_ref():
    ledger = EvaluationLedger()
    with pytest.raises(EvaluationError):
        ledger.record(_tuple(), "", {}, minimums_met=True)
