"""Receipt validation: the required core, the closed vocabularies, outcome receipts."""

from __future__ import annotations

import pytest

from chip.errors import ReceiptError
from chip.receipts import (
    OUTCOME_SCHEMA,
    RECEIPT_SCHEMA,
    Authority,
    Coordinates,
    build_outcome_receipt,
    build_receipt,
    validate_outcome,
    validate_receipt,
)

COORDS = Coordinates(
    run="run:1", installation="inst:1", circuit="circ:1", chip="chip:1", binding="bind:1"
)
AUTH = Authority(effective_ceiling="observe", reason="unevaluated-tuple")


def _receipt(**overrides):
    kwargs = dict(
        coordinates=COORDS,
        run_status="completed",
        semantic_outcome="finding-valid",
        terminal_reason="finding-no-effect",
        digests={"contract": "sha:c", "implementation": "sha:i"},
        authority=AUTH,
    )
    kwargs.update(overrides)
    return build_receipt(**kwargs)


def test_quiet_run_needs_only_the_core():
    """A quiet run allocates no state, calls no gateway, proposes no effects."""
    r = _receipt(semantic_outcome="quiet", terminal_reason="no-actionable-finding")
    d = r.to_dict()
    assert d["schema"] == RECEIPT_SCHEMA
    # The blocks a quiet run never reached are absent, not empty.
    for block in ("inputs", "state", "stages", "gateway", "decisions", "effects", "cost"):
        assert block not in d
    validate_receipt(d)


def test_full_run_carries_its_blocks():
    r = _receipt(
        inputs={"ids": ["sig-1"], "evidenceRefs": ["sha:e"]},
        state={"versionBefore": "v1", "versionAfter": "v2"},
        stages=[{"stage": "normalize", "ms": 3}],
        gateway={"profile": "triage", "servedModel": "m", "usage": {"tokensIn": 10}},
        decisions={"validation": {"ok": True}, "dedupe": {"deduped": False}},
        effects={"proposed": [], "approved": [], "rejected": [], "executed": []},
        cost={"modelCostUsd": 0.002},
    )
    d = r.to_dict()
    assert d["gateway"]["profile"] == "triage"
    validate_receipt(d)


def test_missing_digest_rejected():
    d = _receipt().to_dict()
    del d["digests"]["implementation"]
    with pytest.raises(ReceiptError) as exc:
        validate_receipt(d)
    assert "digests.implementation" in str(exc.value)


def test_terminal_reason_is_a_closed_vocabulary():
    with pytest.raises(ReceiptError) as exc:
        _receipt(terminal_reason="finding")  # a 0.5-era freeform reason
    assert "not one of" in str(exc.value)


def test_terminal_reason_must_match_run_status():
    """'digest mismatch' is a failure; it cannot be reported as a completed run."""
    with pytest.raises(ReceiptError) as exc:
        _receipt(run_status="completed", terminal_reason="implementation-digest-mismatch")
    assert "requires runStatus 'failed'" in str(exc.value)


def test_authority_reason_is_a_closed_vocabulary():
    with pytest.raises(ReceiptError):
        _receipt(authority={"effectiveCeiling": "observe", "reason": "because"})


def test_authority_is_required():
    d = _receipt().to_dict()
    del d["authority"]
    with pytest.raises(ReceiptError) as exc:
        validate_receipt(d)
    assert "authority" in str(exc.value)


def test_run_status_and_semantic_outcome_are_independent():
    """A run whose process completed but whose promise was not satisfied."""
    d = _receipt(
        run_status="failed",
        semantic_outcome="gateway-answer-unusable",
        terminal_reason="gateway-result-invalid",
    ).to_dict()
    assert d["runStatus"] != d["semanticOutcome"]


def test_effects_block_must_be_complete_when_present():
    with pytest.raises(ReceiptError) as exc:
        _receipt(effects={"proposed": [], "approved": []})
    assert "effects.rejected" in str(exc.value)


def test_unknown_schema_rejected():
    with pytest.raises(ReceiptError):
        validate_receipt({"schema": "chip.receipt/v0alpha1#judgment", "coordinates": {}})


def test_supersedes_is_append_only_pointer():
    assert _receipt(supersedes="rcpt:old").to_dict()["supersedes"] == "rcpt:old"


# --- outcome receipts (§13.3) ---


def test_outcome_receipt_records_the_floor_it_was_measured_against():
    r = build_outcome_receipt(
        run_ref="rcpt:1",
        chip_verdict="skip-verification",
        host_decision="verified",
        followed_chip=False,
        at="2026-07-25T12:00:00Z",
        floor_decision="verify",
        downstream_verdict="pass",
    )
    d = r.to_dict()
    assert d["schema"] == OUTCOME_SCHEMA
    assert d["floorDecision"] == "verify"
    validate_outcome(d)


def test_audited_run_cannot_have_followed_the_chip():
    """An audit is precisely a run where the advice was deliberately not taken."""
    with pytest.raises(ReceiptError) as exc:
        build_outcome_receipt(
            run_ref="rcpt:1",
            chip_verdict="skip",
            host_decision="skip",
            followed_chip=True,
            at="2026-07-25T12:00:00Z",
            audited=True,
        )
    assert "cannot both be true" in str(exc.value)


def test_outcome_receipt_requires_a_run_reference():
    with pytest.raises(ReceiptError) as exc:
        validate_outcome(
            {
                "schema": OUTCOME_SCHEMA,
                "chipVerdict": "skip",
                "hostDecision": "skip",
                "followedChip": True,
                "at": "2026-07-25T12:00:00Z",
            }
        )
    assert "runRef" in str(exc.value)
