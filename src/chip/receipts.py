"""Receipts (§13).

One shape. Every run emits it. A required core is always present; the optional
blocks appear only when the run reached the stage that produces them.

Spec 0.5 had two tiers (``#attention`` and ``#judgment``). The tier said how much
of the run happened — which the blocks already say — so 0.6 removes it. Fields
that were required by 0.5 and empty on every production receipt (``artifacts``,
``outcomeLinks``, ``verifierResults``) are gone.

A receipt MUST separate ``run_status`` (the process outcome — "process exited",
"model answered") from ``semantic_outcome`` (the promise-level outcome —
"promise satisfied", "finding valid"). Conflating them is the failure §13 warns
against.

What a run receipt cannot say is whether the chip was *right*; that is not known
yet. :class:`OutcomeReceipt` (§13.3) closes that loop later, and is what makes a
chip calibratable rather than merely evaluable.

Receipts are append-only. A correction never mutates a prior record — it emits a
new receipt whose ``supersedes`` points at the one it replaces.

Schema ids: ``chip.receipt/v0alpha1`` and ``chip.outcome/v0alpha1``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from chip.errors import ReceiptError

RECEIPT_SCHEMA = "chip.receipt/v0alpha1"
OUTCOME_SCHEMA = "chip.outcome/v0alpha1"

#: Closed terminal-reason vocabulary (§13.2), each mapped to the run status it
#: may appear with. A reason that does not fit means the spec is missing a case;
#: it is not license to write prose into the field.
TERMINAL_REASONS: dict[str, str] = {
    "no-actionable-finding": "completed",
    "finding-no-effect": "completed",
    "finding-effect-proposed": "completed",
    "duplicate-signal": "completed",
    "activation-rejected": "rejected",
    "installation-not-enabled": "rejected",
    "signal-invalid": "failed",
    "implementation-digest-mismatch": "failed",
    "gateway-unavailable": "failed",
    "gateway-result-invalid": "failed",
    "host-runtime-error": "failed",
    "authority-denied": "failed",
    "effect-dispatch-failed": "failed",
}

#: Why the effective authority ceiling is what it is (§14). Closed vocabulary:
#: the receipt records one ceiling and one reason, not a lattice of caps.
AUTHORITY_REASONS = frozenset(
    {
        "binding-ceiling",  # the binding's own declared ceiling bound the run
        "unevaluated-tuple",  # no passing held-out suite for the served tuple (§10.2)
        "environment-profile",  # a host environment profile lowered it (§12.1)
        "operator-paused",  # the installation is paused
        "policy-denied",  # policy refused outright
    }
)


@dataclass(frozen=True, slots=True)
class Coordinates:
    """The five identifiers every receipt binds (§13)."""

    run: str
    installation: str
    circuit: str
    chip: str
    binding: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Coordinates:
        missing = [k for k in ("run", "installation", "circuit", "chip", "binding") if not data.get(k)]
        if missing:
            raise ReceiptError(f"coordinates: missing {', '.join(missing)}")
        return cls(
            run=data["run"],
            installation=data["installation"],
            circuit=data["circuit"],
            chip=data["chip"],
            binding=data["binding"],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "run": self.run,
            "installation": self.installation,
            "circuit": self.circuit,
            "chip": self.chip,
            "binding": self.binding,
        }


@dataclass(frozen=True, slots=True)
class Authority:
    """The effective authority decision for one run (§14).

    0.5 hosts recorded five fields (installed ceiling, run ceiling, tuple cap,
    whether a cap applied, which case applied) to express one outcome. Across
    every observed live run the answer was the same value; the derivation is the
    host's business, and the receipt records the result and the binding reason.
    """

    effective_ceiling: str
    reason: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Authority:
        ceiling = data.get("effectiveCeiling")
        reason = data.get("reason")
        if not ceiling:
            raise ReceiptError("authority: 'effectiveCeiling' is required")
        if reason not in AUTHORITY_REASONS:
            raise ReceiptError(
                f"authority: reason {reason!r} is not one of {sorted(AUTHORITY_REASONS)}"
            )
        return cls(effective_ceiling=ceiling, reason=reason)

    def to_dict(self) -> dict[str, Any]:
        return {"effectiveCeiling": self.effective_ceiling, "reason": self.reason}


@dataclass(frozen=True, slots=True)
class Receipt:
    """One run, one receipt (§13).

    Required core: coordinates, the two outcome axes, the terminal reason, the
    contract/implementation digests actually used, the effective authority
    decision, and timing.

    Optional blocks, each present only if the run reached it: ``inputs``,
    ``state``, ``stages``, ``gateway``, ``decisions``, ``effects``, ``cost``.
    """

    coordinates: Coordinates
    run_status: str
    semantic_outcome: str
    terminal_reason: str
    digests: dict[str, Any]
    authority: Authority
    timing: dict[str, Any] = field(default_factory=dict)
    inputs: dict[str, Any] | None = None
    state: dict[str, Any] | None = None
    stages: list[dict[str, Any]] | None = None
    gateway: dict[str, Any] | None = None
    decisions: dict[str, Any] | None = None
    effects: dict[str, Any] | None = None
    cost: dict[str, Any] | None = None
    supersedes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        # Copy the mutable members: the dataclass is frozen, and handing out live
        # references would let a caller edit a receipt through its own export.
        out: dict[str, Any] = {
            "schema": RECEIPT_SCHEMA,
            "coordinates": self.coordinates.to_dict(),
            "runStatus": self.run_status,
            "semanticOutcome": self.semantic_outcome,
            "terminalReason": self.terminal_reason,
            "digests": dict(self.digests),
            "authority": self.authority.to_dict(),
            "timing": dict(self.timing),
        }
        for key, value in (
            ("inputs", self.inputs),
            ("state", self.state),
            ("stages", self.stages),
            ("gateway", self.gateway),
            ("decisions", self.decisions),
            ("effects", self.effects),
            ("cost", self.cost),
            ("supersedes", self.supersedes),
        ):
            if value is not None:
                out[key] = value
        return out

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Receipt:
        validate_receipt(data)
        return cls(
            coordinates=Coordinates.from_dict(data["coordinates"]),
            run_status=data["runStatus"],
            semantic_outcome=data["semanticOutcome"],
            terminal_reason=data["terminalReason"],
            digests=data["digests"],
            authority=Authority.from_dict(data["authority"]),
            timing=data.get("timing", {}),
            inputs=data.get("inputs"),
            state=data.get("state"),
            stages=data.get("stages"),
            gateway=data.get("gateway"),
            decisions=data.get("decisions"),
            effects=data.get("effects"),
            cost=data.get("cost"),
            supersedes=data.get("supersedes"),
        )


@dataclass(frozen=True, slots=True)
class OutcomeReceipt:
    """What happened after the chip spoke (§13.3).

    Emitted later than the run receipt it references, by the host that consumed
    the chip's judgment. ``floor_decision`` is the decision the host would have
    taken without the chip — without it there is nothing to compare against, and
    the chip's contribution is unmeasurable. ``audited`` marks a run where the
    chip's advice was deliberately *not* followed so its precision could be
    measured rather than inferred from silence.
    """

    run_ref: str
    chip_verdict: str
    host_decision: str
    followed_chip: bool
    at: str
    floor_decision: str | None = None
    downstream_verdict: str | None = None
    audited: bool = False
    supersedes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "schema": OUTCOME_SCHEMA,
            "runRef": self.run_ref,
            "chipVerdict": self.chip_verdict,
            "hostDecision": self.host_decision,
            "followedChip": self.followed_chip,
            "audited": self.audited,
            "at": self.at,
        }
        for key, value in (
            ("floorDecision", self.floor_decision),
            ("downstreamVerdict", self.downstream_verdict),
            ("supersedes", self.supersedes),
        ):
            if value is not None:
                out[key] = value
        return out

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OutcomeReceipt:
        validate_outcome(data)
        return cls(
            run_ref=data["runRef"],
            chip_verdict=data["chipVerdict"],
            host_decision=data["hostDecision"],
            followed_chip=bool(data["followedChip"]),
            at=data["at"],
            floor_decision=data.get("floorDecision"),
            downstream_verdict=data.get("downstreamVerdict"),
            audited=bool(data.get("audited", False)),
            supersedes=data.get("supersedes"),
        )


_REQUIRED = (
    "coordinates",
    "runStatus",
    "semanticOutcome",
    "terminalReason",
    "digests",
    "authority",
)
#: The digests a receipt must name. 0.5 also required ``policy``; hosts that
#: enforce policy outside the package had nothing meaningful to put there.
_REQUIRED_DIGESTS = ("contract", "implementation")
_OUTCOME_REQUIRED = ("runRef", "chipVerdict", "hostDecision", "followedChip", "at")


def validate_receipt(data: dict[str, Any]) -> None:
    """Validate a run receipt against §13; raise :class:`ReceiptError` on a gap."""
    if not isinstance(data, dict):
        raise ReceiptError(f"receipt must be an object, got {type(data).__name__}")
    if data.get("schema") != RECEIPT_SCHEMA:
        raise ReceiptError(f"unknown receipt schema {data.get('schema')!r}; expected {RECEIPT_SCHEMA!r}")
    for key in _REQUIRED:
        if key not in data:
            raise ReceiptError(f"receipt: missing required field {key!r}")
        if data[key] in (None, "", {}):
            raise ReceiptError(f"receipt: required field {key!r} must not be empty")

    Coordinates.from_dict(data["coordinates"])
    Authority.from_dict(data["authority"])

    reason = data["terminalReason"]
    expected_status = TERMINAL_REASONS.get(reason)
    if expected_status is None:
        raise ReceiptError(
            f"receipt: terminalReason {reason!r} is not one of {sorted(TERMINAL_REASONS)}"
        )
    if data["runStatus"] != expected_status:
        raise ReceiptError(
            f"receipt: terminalReason {reason!r} requires runStatus "
            f"{expected_status!r}, got {data['runStatus']!r}"
        )

    digests = data["digests"]
    if not isinstance(digests, dict):
        raise ReceiptError("receipt: 'digests' must be an object")
    for key in _REQUIRED_DIGESTS:
        if not digests.get(key):
            raise ReceiptError(f"receipt: digests.{key} is required")

    effects = data.get("effects")
    if effects is not None:
        if not isinstance(effects, dict):
            raise ReceiptError("receipt: 'effects' must be an object")
        for key in ("proposed", "approved", "rejected", "executed"):
            if key not in effects:
                raise ReceiptError(f"receipt: effects.{key} is required when the block is present")


def validate_outcome(data: dict[str, Any]) -> None:
    """Validate an outcome receipt against §13.3; raise on a gap."""
    if not isinstance(data, dict):
        raise ReceiptError(f"outcome receipt must be an object, got {type(data).__name__}")
    if data.get("schema") != OUTCOME_SCHEMA:
        raise ReceiptError(f"unknown outcome schema {data.get('schema')!r}; expected {OUTCOME_SCHEMA!r}")
    for key in _OUTCOME_REQUIRED:
        if key not in data:
            raise ReceiptError(f"outcome receipt: missing required field {key!r}")
        if data[key] in (None, ""):
            raise ReceiptError(f"outcome receipt: required field {key!r} must not be empty")
    if not isinstance(data["followedChip"], bool):
        raise ReceiptError("outcome receipt: 'followedChip' must be a boolean")
    if data.get("audited") and data["followedChip"]:
        raise ReceiptError(
            "outcome receipt: an audited run is one where the chip's advice was "
            "deliberately not followed; 'audited' and 'followedChip' cannot both be true"
        )


def build_receipt(
    coordinates: Coordinates | dict[str, Any],
    run_status: str,
    semantic_outcome: str,
    terminal_reason: str,
    digests: dict[str, Any],
    authority: Authority | dict[str, Any],
    **kwargs: Any,
) -> Receipt:
    """Construct and validate a :class:`Receipt`."""
    coords = coordinates if isinstance(coordinates, Coordinates) else Coordinates.from_dict(coordinates)
    auth = authority if isinstance(authority, Authority) else Authority.from_dict(authority)
    receipt = Receipt(
        coordinates=coords,
        run_status=run_status,
        semantic_outcome=semantic_outcome,
        terminal_reason=terminal_reason,
        digests=digests,
        authority=auth,
        timing=kwargs.get("timing", {}),
        inputs=kwargs.get("inputs"),
        state=kwargs.get("state"),
        stages=kwargs.get("stages"),
        gateway=kwargs.get("gateway"),
        decisions=kwargs.get("decisions"),
        effects=kwargs.get("effects"),
        cost=kwargs.get("cost"),
        supersedes=kwargs.get("supersedes"),
    )
    validate_receipt(receipt.to_dict())
    return receipt


def build_outcome_receipt(
    run_ref: str,
    chip_verdict: str,
    host_decision: str,
    followed_chip: bool,
    at: str,
    **kwargs: Any,
) -> OutcomeReceipt:
    """Construct and validate an :class:`OutcomeReceipt`."""
    receipt = OutcomeReceipt(
        run_ref=run_ref,
        chip_verdict=chip_verdict,
        host_decision=host_decision,
        followed_chip=followed_chip,
        at=at,
        floor_decision=kwargs.get("floor_decision"),
        downstream_verdict=kwargs.get("downstream_verdict"),
        audited=bool(kwargs.get("audited", False)),
        supersedes=kwargs.get("supersedes"),
    )
    validate_outcome(receipt.to_dict())
    return receipt
