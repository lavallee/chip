"""Evaluated-tuple bookkeeping and the unevaluated-tuple authority cap (§10.2).

Evaluation evidence is valid only for the exact tuple::

    (implementation digest, gateway profile, served model, harness)

Changing any member creates an *unevaluated* tuple. An unevaluated binding is
capped at ``observe`` until its held-out suite passes, and — critically — a
profile alias MUST NOT silently inherit a result from the model it previously
resolved to. This module keys the ledger on the *full* tuple, so no alias
resolution or partial match can smuggle in stale evidence.

Canned vs. live honesty: a fixture-canned evaluation validates the deterministic
envelope and records a tuple whose ``served_model`` is the canned marker; it does
NOT evaluate a live model tuple. Lifting a live binding above ``observe`` requires
the held-out suite to run against the *live* gateway, so the recorded tuple
matches what activation will actually compute. The observe cap is binding-level:
a gateway-bearing binding whose tuple is unevaluated is capped at ``observe`` for
*every* run, including runs where the implementation happens not to invoke the
gateway (the cap is not decided per-run).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from chip.authority import EffectClass
from chip.errors import EvaluationError


@dataclass(frozen=True, slots=True)
class EvaluatedTuple:
    """The four-part identity that evaluation evidence is bound to (§10.2)."""

    implementation_digest: str
    gateway_profile: str
    served_model: str
    harness: str

    def __post_init__(self) -> None:
        for name in ("implementation_digest", "gateway_profile", "served_model", "harness"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise EvaluationError(f"EvaluatedTuple.{name} must be a non-empty string")

    def key(self) -> str:
        """A stable content-addressed key over all four members (order-fixed)."""
        material = "\0".join(
            [self.implementation_digest, self.gateway_profile, self.served_model, self.harness]
        )
        return "cet1-" + hashlib.sha256(material.encode("utf-8")).hexdigest()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvaluatedTuple:
        return cls(
            implementation_digest=data.get("implementation", data.get("implementationDigest", "")),
            gateway_profile=data.get("gatewayProfile", data.get("sommProfile", "")),
            served_model=data.get("servedModel", ""),
            harness=data.get("harness", ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "implementation": self.implementation_digest,
            "gatewayProfile": self.gateway_profile,
            "servedModel": self.served_model,
            "harness": self.harness,
        }


@dataclass(frozen=True, slots=True)
class _LedgerEntry:
    receipt_ref: str
    metrics: dict[str, Any]
    minimums_met: bool


class EvaluationLedger:
    """A record of which tuples have passed their held-out suite (§10.2, §21).

    The ledger is keyed strictly on :meth:`EvaluatedTuple.key`. A tuple counts as
    evaluated only when it was recorded with ``minimums_met=True``. Any tuple the
    ledger has never seen — including one that differs only by a swapped profile
    alias or model — is unevaluated and therefore capped at ``observe``.
    """

    def __init__(self) -> None:
        self._entries: dict[str, _LedgerEntry] = {}

    def record(
        self,
        tuple_: EvaluatedTuple,
        receipt_ref: str,
        metrics: dict[str, Any],
        minimums_met: bool,
    ) -> None:
        """Record an evaluation result for ``tuple_``.

        ``receipt_ref`` must be a non-empty reference to the evaluation receipt.
        Recording with ``minimums_met=False`` keeps the tuple unevaluated.
        """
        if not receipt_ref or not str(receipt_ref).strip():
            raise EvaluationError("record: receipt_ref must be a non-empty reference")
        self._entries[tuple_.key()] = _LedgerEntry(
            receipt_ref=receipt_ref,
            metrics=dict(metrics),
            minimums_met=bool(minimums_met),
        )

    def is_evaluated(self, tuple_: EvaluatedTuple) -> bool:
        """True only if the *exact* tuple was recorded with minimums met."""
        entry = self._entries.get(tuple_.key())
        return entry is not None and entry.minimums_met

    def authority_cap_for(self, tuple_: EvaluatedTuple) -> EffectClass:
        """The authority ceiling this tuple may run under, per §10.2.

        Returns the tuple's evaluated ceiling only when it is evaluated; an
        unevaluated tuple is capped at :data:`EffectClass.OBSERVE`. This is the
        function a host consults to drop a swapped-profile binding back to
        ``observe`` until it re-passes its suite.
        """
        return EffectClass.OBSERVE if not self.is_evaluated(tuple_) else _EVALUATED_CEILING

    def entry_for(self, tuple_: EvaluatedTuple) -> dict[str, Any] | None:
        """Return the recorded metrics/receipt for a tuple, or ``None``."""
        entry = self._entries.get(tuple_.key())
        if entry is None:
            return None
        return {
            "receiptRef": entry.receipt_ref,
            "metrics": entry.metrics,
            "minimumsMet": entry.minimums_met,
        }

    def entries(self) -> list[dict[str, Any]]:
        """Every recorded entry as a list of plain dicts (each carries its ``key``).

        The tuple ``key`` is the content-addressed :meth:`EvaluatedTuple.key`; a
        host that persists these can rebuild an equivalent ledger via
        :meth:`from_dict`, since all lookups (:meth:`is_evaluated`,
        :meth:`authority_cap_for`) are keyed on that hash alone.
        """
        return [
            {
                "key": key,
                "receiptRef": entry.receipt_ref,
                "metrics": dict(entry.metrics),
                "minimumsMet": entry.minimums_met,
            }
            for key, entry in self._entries.items()
        ]

    def to_dict(self) -> dict[str, Any]:
        """Serialize the whole ledger to a plain, JSON-round-trippable dict."""
        return {"version": "cet-ledger-1", "entries": self.entries()}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvaluationLedger:
        """Rebuild a ledger from :meth:`to_dict` output (or an ``entries`` list).

        Faithful for the ledger's purpose: it restores each ``tuple.key`` →
        (receipt, metrics, minimumsMet) mapping so evaluated/observe-cap decisions
        replay identically. Raises :class:`EvaluationError` on a malformed entry.
        """
        ledger = cls()
        if not isinstance(data, dict):
            raise EvaluationError("EvaluationLedger.from_dict: expected a dict")
        for item in data.get("entries", []):
            if not isinstance(item, dict) or "key" not in item:
                raise EvaluationError("EvaluationLedger.from_dict: entry missing 'key'")
            key = item["key"]
            receipt_ref = item.get("receiptRef", "")
            if not receipt_ref or not str(receipt_ref).strip():
                raise EvaluationError(
                    f"EvaluationLedger.from_dict: entry {key!r} missing receiptRef"
                )
            ledger._entries[key] = _LedgerEntry(
                receipt_ref=receipt_ref,
                metrics=dict(item.get("metrics", {})),
                minimums_met=bool(item.get("minimumsMet", False)),
            )
        return ledger


# The ceiling an evaluated tuple is permitted to reach. The spec caps v1 chips at
# `recommend`/synthesize by authority declaration; evaluation does not itself
# grant more than that, so an evaluated tuple's cap defers to the chip/binding
# authority ceilings (intersected elsewhere via chip.authority.effective_authority).
# We express "evaluation imposes no reduction" as PROMOTE so the intersection is
# governed by the declared ceilings, not by the ledger.
_EVALUATED_CEILING = EffectClass.PROMOTE
