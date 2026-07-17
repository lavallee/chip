"""Receipt validation: required digest fields, run_status vs semantic_outcome."""

from __future__ import annotations

import pytest

from chip.errors import ReceiptError
from chip.receipts import (
    ATTENTION_SCHEMA,
    JUDGMENT_SCHEMA,
    Coordinates,
    build_attention_receipt,
    build_judgment_receipt,
    validate_receipt,
)

COORDS = Coordinates(
    run="run:1", installation="inst:1", circuit="circ:1", chip="chip:1", binding="bind:1"
)


def _judgment_kwargs():
    return dict(
        digests={"contract": "sha:c", "implementation": "sha:i", "policy": "sha:p"},
        decisions={"validation": {"ok": True}, "dedupe": {}, "budget": {}, "authority": {}},
        effects={"proposed": [], "approved": [], "rejected": [], "executed": []},
        state_version_before="v1",
        state_version_after="v2",
        stage_events=[{"stage": "normalize", "ms": 3}],
        input_ids=["sig-1"],
    )


def test_attention_receipt_valid():
    r = build_attention_receipt(
        COORDS,
        run_status="completed",
        semantic_outcome="quiet",
        terminal_reason="no-new-report",
    )
    d = r.to_dict()
    assert d["schema"] == ATTENTION_SCHEMA
    validate_receipt(d)


def test_judgment_receipt_valid():
    r = build_judgment_receipt(
        COORDS,
        run_status="completed",
        semantic_outcome="finding-valid",
        terminal_reason="finding",
        **_judgment_kwargs(),
    )
    d = r.to_dict()
    assert d["schema"] == JUDGMENT_SCHEMA
    validate_receipt(d)


def test_judgment_missing_digest_rejected():
    r = build_judgment_receipt(
        COORDS,
        run_status="completed",
        semantic_outcome="finding-valid",
        terminal_reason="finding",
        **_judgment_kwargs(),
    )
    d = r.to_dict()
    del d["digests"]["implementation"]
    with pytest.raises(ReceiptError) as exc:
        validate_receipt(d)
    assert "digests.implementation" in str(exc.value)


def test_judgment_missing_decision_rejected():
    kwargs = _judgment_kwargs()
    del kwargs["decisions"]["authority"]
    with pytest.raises(ReceiptError):
        build_judgment_receipt(
            COORDS,
            run_status="completed",
            semantic_outcome="finding-valid",
            terminal_reason="finding",
            **kwargs,
        )


def test_run_status_and_semantic_outcome_are_independent():
    # A run whose process completed but whose promise was NOT satisfied.
    r = build_judgment_receipt(
        COORDS,
        run_status="completed",
        semantic_outcome="finding-invalid",
        terminal_reason="validation-failed",
        **_judgment_kwargs(),
    )
    d = r.to_dict()
    assert d["runStatus"] == "completed"
    assert d["semanticOutcome"] == "finding-invalid"
    assert d["runStatus"] != d["semanticOutcome"]


def test_missing_run_status_rejected():
    d = {
        "schema": ATTENTION_SCHEMA,
        "coordinates": COORDS.to_dict(),
        "semanticOutcome": "quiet",
        "terminalReason": "none",
    }
    with pytest.raises(ReceiptError) as exc:
        validate_receipt(d)
    assert "runStatus" in str(exc.value)


def test_unknown_schema_rejected():
    with pytest.raises(ReceiptError):
        validate_receipt({"schema": "chip.receipt/vX#other", "coordinates": {}})


def test_supersedes_is_append_only_pointer():
    r = build_attention_receipt(
        COORDS,
        run_status="completed",
        semantic_outcome="corrected",
        terminal_reason="supersede",
        supersedes="rcpt:old",
    )
    assert r.to_dict()["supersedes"] == "rcpt:old"
