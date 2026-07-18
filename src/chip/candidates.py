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

import hashlib
import json
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Any

from chip.errors import CandidateError

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows fallback
    fcntl = None  # type: ignore[assignment]


CANDIDATE_RECEIPT_SCHEMA = "chip.candidate-receipt/v1"


@dataclass(frozen=True, slots=True)
class Candidate:
    """One captured chip candidate (spec 0.5.0 candidate ledger)."""

    observed_at: str
    shape: str  # a one-line promise draft
    occurrence_refs: tuple[str, ...] = ()
    fixture_refs: tuple[str, ...] = ()
    count: int = 1
    noted_by: str = ""
    candidate_id: str = ""
    source_id: str = ""
    source_revision: str = ""
    counterexample_refs: tuple[str, ...] = ()
    source_limits: dict[str, Any] | None = None

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
        if not isinstance(count, int) or isinstance(count, bool):
            raise CandidateError("candidate: 'count' must be an integer")

        candidate_id = data.get("candidateId", "")
        source_id = data.get("sourceId", "")
        source_revision = data.get("sourceRevision", "")
        identity = (candidate_id, source_id, source_revision)
        if any(identity) and not all(
            isinstance(value, str) and value.strip() for value in identity
        ):
            raise CandidateError(
                "candidate: candidateId, sourceId, and sourceRevision must all be non-empty strings"
            )
        commissioned = bool(candidate_id)
        if count < (0 if commissioned else 1):
            qualifier = "non-negative" if commissioned else "positive"
            raise CandidateError(f"candidate: 'count' must be a {qualifier} integer")

        occurrence_refs = _str_list("occurrenceRefs")
        fixture_refs = _str_list("fixtureRefs")
        counterexample_refs = _str_list("counterexampleRefs")
        source_limits = data.get("sourceLimits")
        if source_limits is not None and not isinstance(source_limits, dict):
            raise CandidateError("candidate: 'sourceLimits' must be an object when present")
        try:
            json.dumps(source_limits, sort_keys=True, separators=(",", ":"))
        except (TypeError, ValueError) as exc:
            raise CandidateError("candidate: 'sourceLimits' must contain JSON values") from exc
        if commissioned:
            for key, refs in (
                ("occurrenceRefs", occurrence_refs),
                ("fixtureRefs", fixture_refs),
                ("counterexampleRefs", counterexample_refs),
            ):
                if refs != tuple(sorted(set(refs))):
                    raise CandidateError(
                        f"candidate: commissioned {key!r} must be sorted and unique"
                    )
            if count != len(occurrence_refs):
                raise CandidateError(
                    "candidate: commissioned 'count' must equal unique occurrenceRefs"
                )
            if source_limits is None:
                raise CandidateError("candidate: commissioned rows require 'sourceLimits'")

        return cls(
            observed_at=observed_at,
            shape=shape,
            occurrence_refs=occurrence_refs,
            fixture_refs=fixture_refs,
            count=count,
            noted_by=str(data.get("notedBy", "")),
            candidate_id=str(candidate_id),
            source_id=str(source_id),
            source_revision=str(source_revision),
            counterexample_refs=counterexample_refs,
            source_limits=source_limits,
        )

    def to_dict(self) -> dict[str, Any]:
        result = {
            "observedAt": self.observed_at,
            "shape": self.shape,
            "occurrenceRefs": list(self.occurrence_refs),
            "fixtureRefs": list(self.fixture_refs),
            "count": self.count,
            "notedBy": self.noted_by,
        }
        if self.candidate_id:
            result.update(
                {
                    "candidateId": self.candidate_id,
                    "sourceId": self.source_id,
                    "sourceRevision": self.source_revision,
                    "counterexampleRefs": list(self.counterexample_refs),
                    "sourceLimits": self.source_limits,
                }
            )
        return result


@dataclass(frozen=True, slots=True)
class CandidateReceipt:
    """Stable custody receipt for one commissioned source revision."""

    receipt_id: str
    recorded_at: str
    candidate_id: str
    source_id: str
    source_revision: str
    occurrence_refs: tuple[str, ...]
    counterexample_refs: tuple[str, ...]
    fixture_refs: tuple[str, ...]
    source_limits: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": CANDIDATE_RECEIPT_SCHEMA,
            "receiptId": self.receipt_id,
            "recordedAt": self.recorded_at,
            "candidateId": self.candidate_id,
            "sourceId": self.source_id,
            "sourceRevision": self.source_revision,
            "occurrenceRefs": list(self.occurrence_refs),
            "counterexampleRefs": list(self.counterexample_refs),
            "fixtureRefs": list(self.fixture_refs),
            "sourceLimits": self.source_limits,
            "semanticOutcome": "candidate-recorded",
        }

    @classmethod
    def from_candidate(cls, candidate: Candidate) -> CandidateReceipt:
        if not candidate.candidate_id or candidate.source_limits is None:
            raise CandidateError("candidate receipt requires a commissioned candidate")
        receipt_id = _stable_id(
            "ccr",
            CANDIDATE_RECEIPT_SCHEMA,
            _canonical_json(candidate.to_dict()),
        )
        return cls(
            receipt_id,
            candidate.observed_at,
            candidate.candidate_id,
            candidate.source_id,
            candidate.source_revision,
            candidate.occurrence_refs,
            candidate.counterexample_refs,
            candidate.fixture_refs,
            candidate.source_limits,
        )


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


def commission_candidate(
    path: str | Path,
    candidate: Candidate | dict[str, Any],
    *,
    receipts_path: str | Path | None = None,
) -> CandidateReceipt:
    """Idempotently commission one source-owned candidate revision.

    The candidate ledger remains append-only. Replaying the same exact source
    revision writes neither a second candidate row nor a second receipt. The
    returned receipt is content-addressed and therefore identical on first
    ingest and replay. A source revision that changes content, or a candidate id
    that is reused for another source/shape, fails closed.
    """

    cand = candidate if isinstance(candidate, Candidate) else Candidate.from_dict(candidate)
    if not cand.candidate_id:
        raise CandidateError("commission_candidate requires stable candidate/source identity")
    receipt = CandidateReceipt.from_candidate(cand)
    ledger_path = Path(path)
    receipt_path = (
        Path(receipts_path)
        if receipts_path is not None
        else ledger_path.with_name("candidate-receipts.jsonl")
    )
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.parent.mkdir(parents=True, exist_ok=True)

    with _ledger_lock(ledger_path):
        existing = load_candidates(ledger_path)
        for row in existing:
            if row.source_id == cand.source_id and row.source_revision == cand.source_revision:
                if row.to_dict() != cand.to_dict():
                    raise CandidateError(
                        "sourceRevision is already commissioned with other content"
                    )
                _append_receipt_once(receipt_path, receipt)
                return receipt
            if row.candidate_id == cand.candidate_id and (
                row.source_id != cand.source_id or row.shape != cand.shape
            ):
                raise CandidateError(
                    "candidateId is already commissioned for a different source or shape"
                )
        _append_json_line(ledger_path, cand.to_dict())
        _append_receipt_once(receipt_path, receipt)
    return receipt


def tally(candidates: list[Candidate]) -> dict[str, int]:
    """Sum candidate ``count`` by ``shape`` — the frequency view minting reads.

    Returns a mapping of one-line promise-draft shape -> total observed count,
    so a host can see which candidate shapes have crossed a minting threshold.
    """
    totals: dict[str, int] = {}
    commissioned: dict[tuple[str, str, str], set[str]] = {}
    for cand in candidates:
        if not cand.candidate_id:
            totals[cand.shape] = totals.get(cand.shape, 0) + cand.count
            continue
        key = (cand.candidate_id, cand.source_id, cand.shape)
        commissioned.setdefault(key, set()).update(cand.occurrence_refs)
    for (_, _, shape), occurrence_refs in commissioned.items():
        totals[shape] = totals.get(shape, 0) + len(occurrence_refs)
    return totals


def _append_receipt_once(path: Path, receipt: CandidateReceipt) -> None:
    document = receipt.to_dict()
    if path.is_file():
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                existing = json.loads(line)
            except json.JSONDecodeError as exc:
                raise CandidateError(
                    f"candidate receipt line {lineno}: invalid JSON: {exc}"
                ) from exc
            if existing.get("receiptId") == receipt.receipt_id:
                if existing != document:
                    raise CandidateError("candidate receipt id collision")
                return
    _append_json_line(path, document)


def _append_json_line(path: Path, document: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as fh:
        fh.write(_canonical_json(document) + "\n")


@contextmanager
def _ledger_lock(path: Path) -> Iterator[IO[str]]:
    lock_path = path.with_suffix(path.suffix + ".lock")
    with lock_path.open("a+", encoding="utf-8") as lock:
        if fcntl is not None:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            yield lock
        finally:
            if fcntl is not None:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("\x1f".join(parts).encode()).hexdigest()[:24]
    return f"{prefix}_{digest}"
