"""Candidate ledger: append/load round-trip and tally-by-shape (spec 0.5.0)."""

from __future__ import annotations

import pytest

from chip.candidates import Candidate, append_candidate, load_candidates, tally
from chip.errors import CandidateError


def _cand(**over) -> dict:
    base = {
        "observedAt": "2026-07-17T00:00:00Z",
        "shape": "when a dependency range changes, propose a tested update",
        "occurrenceRefs": ["receipt:abc"],
        "fixtureRefs": ["fixtures/harvested/001.json"],
        "count": 1,
        "notedBy": "agent:build-loop",
    }
    base.update(over)
    return base


def test_candidate_round_trip():
    c = Candidate.from_dict(_cand())
    assert c.shape.startswith("when a dependency")
    assert c.occurrence_refs == ("receipt:abc",)
    assert Candidate.from_dict(c.to_dict()) == c


def test_missing_shape_rejected():
    bad = _cand()
    del bad["shape"]
    with pytest.raises(CandidateError, match="shape"):
        Candidate.from_dict(bad)


def test_count_must_be_positive_int():
    with pytest.raises(CandidateError, match="count"):
        Candidate.from_dict(_cand(count=0))
    with pytest.raises(CandidateError, match="count"):
        Candidate.from_dict(_cand(count=True))


def test_refs_must_be_string_lists():
    with pytest.raises(CandidateError, match="occurrenceRefs"):
        Candidate.from_dict(_cand(occurrenceRefs=[1, 2]))


def test_append_and_load(tmp_path):
    ledger = tmp_path / "candidates.jsonl"
    append_candidate(ledger, _cand())
    append_candidate(ledger, Candidate.from_dict(_cand(count=2)))
    loaded = load_candidates(ledger)
    assert len(loaded) == 2
    assert loaded[1].count == 2


def test_append_creates_parent_dirs(tmp_path):
    ledger = tmp_path / "nested" / "dir" / "candidates.jsonl"
    append_candidate(ledger, _cand())
    assert ledger.is_file()


def test_load_missing_file_is_empty(tmp_path):
    assert load_candidates(tmp_path / "nope.jsonl") == []


def test_load_malformed_line_names_lineno(tmp_path):
    ledger = tmp_path / "candidates.jsonl"
    ledger.write_text('{"observedAt":"x","shape":"ok","count":1}\nnot-json\n', encoding="utf-8")
    with pytest.raises(CandidateError, match="line 2"):
        load_candidates(ledger)


def test_tally_sums_by_shape(tmp_path):
    ledger = tmp_path / "candidates.jsonl"
    append_candidate(ledger, _cand(shape="shape A", count=3))
    append_candidate(ledger, _cand(shape="shape A", count=2))
    append_candidate(ledger, _cand(shape="shape B", count=1))
    totals = tally(load_candidates(ledger))
    assert totals == {"shape A": 5, "shape B": 1}
