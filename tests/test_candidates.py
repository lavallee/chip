"""Candidate ledger: append/load round-trip and tally-by-shape (spec 0.5.0)."""

from __future__ import annotations

import pytest

from chip.candidates import (
    Candidate,
    append_candidate,
    commission_candidate,
    load_candidates,
    tally,
)
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


def _commissioned(**over) -> dict:
    base = _cand(
        candidateId="candidate:milton:fnd-1",
        sourceId="milton.finding=fnd-1",
        sourceRevision="milton.finding-revision=fnr-1",
        occurrenceRefs=["event:occurrence-1", "event:occurrence-2"],
        counterexampleRefs=["fixture:negative:counter-1"],
        fixtureRefs=["fixture:exception:exception-1", "fixture:positive:positive-1"],
        sourceLimits={
            "coverage": 0.75,
            "coverageGaps": ["one source was unavailable"],
            "contentPolicy": "metadata-only",
            "expiresAt": "2026-08-01T00:00:00Z",
        },
        count=2,
        notedBy="milton:failure-motifs/v1",
    )
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


def test_commission_is_idempotent_and_returns_stable_receipt(tmp_path):
    ledger = tmp_path / "candidates.jsonl"
    first = commission_candidate(ledger, _commissioned())
    replay = commission_candidate(ledger, _commissioned())

    assert replay == first
    assert len(load_candidates(ledger)) == 1
    receipts = (tmp_path / "candidate-receipts.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(receipts) == 1
    assert first.to_dict()["semanticOutcome"] == "candidate-recorded"
    assert first.counterexample_refs == ("fixture:negative:counter-1",)
    assert first.fixture_refs == (
        "fixture:exception:exception-1",
        "fixture:positive:positive-1",
    )


def test_commission_rejects_changed_content_for_one_source_revision(tmp_path):
    ledger = tmp_path / "candidates.jsonl"
    commission_candidate(ledger, _commissioned())

    with pytest.raises(CandidateError, match="other content"):
        commission_candidate(ledger, _commissioned(shape="a silently changed promise"))


def test_commissioned_tally_counts_unique_occurrences_across_revisions(tmp_path):
    ledger = tmp_path / "candidates.jsonl"
    commission_candidate(ledger, _commissioned())
    commission_candidate(
        ledger,
        _commissioned(
            sourceRevision="milton.finding-revision=fnr-2",
            occurrenceRefs=["event:occurrence-2", "event:occurrence-3"],
            count=2,
        ),
    )

    assert len(load_candidates(ledger)) == 2
    assert tally(load_candidates(ledger)) == {
        "when a dependency range changes, propose a tested update": 3
    }


def test_commission_requires_complete_sorted_identity_and_limits():
    with pytest.raises(CandidateError, match="must all be non-empty"):
        Candidate.from_dict(_commissioned(sourceRevision=""))
    with pytest.raises(CandidateError, match="sorted and unique"):
        Candidate.from_dict(_commissioned(occurrenceRefs=["z", "a"], count=2))
    with pytest.raises(CandidateError, match="sourceLimits"):
        Candidate.from_dict(_commissioned(sourceLimits=None))
