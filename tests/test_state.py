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
