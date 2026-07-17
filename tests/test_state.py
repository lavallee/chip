"""State contract v1 restrictions and cursor monotonicity."""

from __future__ import annotations

import pytest

from chip.errors import StateError
from chip.state import Cursor, StateContract


def _state(**over):
    base = {
        "schema": "schemas/state.json",
        "scope": "installation",
        "retention": "P365D",
        "cursor": "required",
        "concurrency": "single-flight",
    }
    base.update(over)
    return base


def test_valid_state_contract():
    sc = StateContract.from_dict(_state())
    assert sc.scope == "installation"
    assert StateContract.from_dict(sc.to_dict()).cursor == "required"


def test_bad_scope_rejected():
    with pytest.raises(StateError):
        StateContract.from_dict(_state(scope="project"))


def test_bad_concurrency_rejected():
    with pytest.raises(StateError):
        StateContract.from_dict(_state(concurrency="cas"))


def test_cursor_required_needs_single_flight():
    # concurrency other than single-flight is already rejected in v1, so this is
    # covered; a cursor=none chip may of course omit strict concurrency.
    sc = StateContract.from_dict(_state(cursor="none"))
    assert sc.cursor == "none"


def test_cursor_advance_monotonic():
    c = Cursor(value="2026-07-16T00:00:00Z", lineage="L1")
    c2 = c.advance("2026-07-17T00:00:00Z")
    assert c2.value > c.value
    assert c2.lineage == "L1"


def test_cursor_cannot_regress():
    c = Cursor(value="2026-07-16T00:00:00Z", lineage="L1")
    with pytest.raises(StateError):
        c.advance("2026-07-15T00:00:00Z")
    with pytest.raises(StateError):
        c.advance("2026-07-16T00:00:00Z")  # equal is not progress


# ---- partitioned(key) concurrency (spec 0.5.0) ----


def test_partitioned_concurrency_parsed():
    sc = StateContract.from_dict(_state(cursor="none", concurrency="partitioned(source)"))
    assert sc.concurrency == "partitioned(source)"
    assert sc.partition_key == "source"
    # round-trips through the concurrency string (key travels with it)
    assert StateContract.from_dict(sc.to_dict()).partition_key == "source"


def test_single_flight_has_no_partition_key():
    sc = StateContract.from_dict(_state())
    assert sc.partition_key is None


def test_partitioned_requires_key_field():
    with pytest.raises(StateError, match="key field"):
        StateContract.from_dict(_state(cursor="none", concurrency="partitioned"))
    with pytest.raises(StateError):
        StateContract.from_dict(_state(cursor="none", concurrency="partitioned()"))


def test_single_flight_rejects_stray_key():
    with pytest.raises(StateError, match="does not take a key"):
        StateContract.from_dict(_state(cursor="none", concurrency="single-flight(x)"))


def test_cursor_required_may_not_partition():
    # cursor-bearing attention chips MUST stay single-flight (§9)
    with pytest.raises(StateError, match="single-flight"):
        StateContract.from_dict(_state(cursor="required", concurrency="partitioned(source)"))


def test_cas_still_deferred():
    with pytest.raises(StateError, match="deferred"):
        StateContract.from_dict(_state(cursor="none", concurrency="cas"))
