"""Candidate ledger: the side-activity capture convention (spec 0.5.0).

Minting a chip stays frequency- and eval-gated, but the *scarce* input to that
economy is the candidate observation and the real fixtures harvested during
normal work. This module is the light convention for capturing them: an
append-only ``candidates.jsonl`` of one-line promise drafts with occurrence and
fixture references, plus helpers to append, load, and tally by shape.

Each line is one candidate::

    {
      "observedAt": "2026-07-17T00:00:00Z",
      "shape": "when a repo's dependency range changes, propose a tested update",
      "occurrenceRefs": ["receipt:abc", "receipt:def"],
      "fixtureRefs": ["fixtures/harvested/001.json"],
      "count": 2,
      "notedBy": "agent:build-loop"
    }

Capture and fixture-harvest are cheap to do continuously; minting is not — see
``docs/candidates.md``. This is a convention helper, not a runtime: it appends
and reads a local JSONL file and nothing more.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from chip.errors import CandidateError


@dataclass(frozen=True, slots=True)
class Candidate:
    """One captured chip candidate (spec 0.5.0 candidate ledger)."""

    observed_at: str
    shape: str  # a one-line promise draft
    occurrence_refs: tuple[str, ...] = ()
    fixture_refs: tuple[str, ...] = ()
    count: int = 1
    noted_by: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Candidate:
        if not isinstance(data, dict):
            raise CandidateError(f"candidate must be an object, got {type(data).__name__}")
        observed_at = data.get("observedAt")
        if not isinstance(observed_at, str) or not observed_at.strip():
            raise CandidateError("candidate: 'observedAt' must be a non-empty string")
        shape = data.get("shape")
        if not isinstance(shape, str) or not shape.strip():
            raise CandidateError("candidate: 'shape' must be a non-empty one-line promise draft")

        def _str_list(key: str) -> tuple[str, ...]:
            raw = data.get(key, [])
            if not isinstance(raw, list) or any(not isinstance(x, str) for x in raw):
                raise CandidateError(f"candidate: {key!r} must be a list of strings")
            return tuple(raw)

        count = data.get("count", 1)
        if not isinstance(count, int) or isinstance(count, bool) or count < 1:
            raise CandidateError("candidate: 'count' must be a positive integer")
        return cls(
            observed_at=observed_at,
            shape=shape,
            occurrence_refs=_str_list("occurrenceRefs"),
            fixture_refs=_str_list("fixtureRefs"),
            count=count,
            noted_by=str(data.get("notedBy", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "observedAt": self.observed_at,
            "shape": self.shape,
            "occurrenceRefs": list(self.occurrence_refs),
            "fixtureRefs": list(self.fixture_refs),
            "count": self.count,
            "notedBy": self.noted_by,
        }


def append_candidate(path: str | Path, candidate: Candidate | dict[str, Any]) -> Candidate:
    """Append one candidate to the append-only ``candidates.jsonl`` at ``path``.

    Accepts a :class:`Candidate` or a plain dict (validated via
    :meth:`Candidate.from_dict`). Creates the file and any parent directories on
    first write. Returns the validated :class:`Candidate` that was written.
    """
    cand = candidate if isinstance(candidate, Candidate) else Candidate.from_dict(candidate)
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(cand.to_dict(), separators=(",", ":")) + "\n")
    return cand


def load_candidates(path: str | Path) -> list[Candidate]:
    """Load every candidate from a ``candidates.jsonl`` file (blank lines skipped).

    A missing file yields an empty list. A malformed line raises
    :class:`CandidateError` naming the 1-based line number.
    """
    p = Path(path)
    if not p.is_file():
        return []
    out: list[Candidate] = []
    for lineno, line in enumerate(p.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError as exc:
            raise CandidateError(f"candidates.jsonl line {lineno}: invalid JSON: {exc}") from exc
        try:
            out.append(Candidate.from_dict(data))
        except CandidateError as exc:
            raise CandidateError(f"candidates.jsonl line {lineno}: {exc}") from exc
    return out


def tally(candidates: list[Candidate]) -> dict[str, int]:
    """Sum candidate ``count`` by ``shape`` — the frequency view minting reads.

    Returns a mapping of one-line promise-draft shape -> total observed count,
    so a host can see which candidate shapes have crossed a minting threshold.
    """
    totals: dict[str, int] = {}
    for cand in candidates:
        totals[cand.shape] = totals.get(cand.shape, 0) + cand.count
    return totals
