"""Lifecycle telemetry: mint/transfer/split/merge/optimize/retire (spec 0.5.0).

A host banks and evolves chips over their lifetime. This module models the
append-only lifecycle events that record those transitions, and validates them
against the **exact** schema a host writes:

.. code-block:: json

    {
      "event": "mint",
      "at": "2026-07-17T00:00:00Z",
      "operator": "owner:desk",
      "chipAlias": "press.new-report-triage",
      "chipVersion": "0.2.0",
      "implementationDigest": "sha256:...",
      "tupleKey": null,
      "receiptRef": null,
      "details": {}
    }

:func:`validate_lifecycle_event` matches that shape exactly (no missing keys, no
extra keys) so a parallel host implementation writing these dicts stays in lock
step with the library. Beyond the shape, three spec rules are enforced:

* minting SHOULD be gated on observed call frequency (advisory — not enforced
  here, but ``details`` is where a host records the gating frequency);
* ``split``/``merge``/``optimize``/``retire`` MUST carry the held-out
  ``tupleKey`` that gated them; and
* a ``retire`` whose ``details.reason`` is ``"model-generation"`` MUST reference
  a raw-model baseline comparison under ``details.rawModelBaseline`` — banked
  knowledge is only retired against evidence that the raw model now matches it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from chip.errors import LifecycleError

# The six admitted lifecycle events (spec 0.5.0 "Lifecycle telemetry").
LIFECYCLE_EVENTS: frozenset[str] = frozenset(
    {"mint", "transfer", "split", "merge", "optimize", "retire"}
)

# Events that MUST carry the held-out tuple that gated them.
_TUPLE_GATED_EVENTS: frozenset[str] = frozenset({"split", "merge", "optimize", "retire"})

# The exact top-level key set of a lifecycle event dict.
_REQUIRED_KEYS: frozenset[str] = frozenset(
    {
        "event",
        "at",
        "operator",
        "chipAlias",
        "chipVersion",
        "implementationDigest",
        "tupleKey",
        "receiptRef",
        "details",
    }
)


@dataclass(frozen=True, slots=True)
class LifecycleEvent:
    """One append-only lifecycle-telemetry record (spec 0.5.0)."""

    event: str
    at: str
    operator: str
    chip_alias: str
    chip_version: str
    implementation_digest: str
    tuple_key: str | None = None
    receipt_ref: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LifecycleEvent:
        validate_lifecycle_event(data)
        return cls(
            event=data["event"],
            at=data["at"],
            operator=data["operator"],
            chip_alias=data["chipAlias"],
            chip_version=data["chipVersion"],
            implementation_digest=data["implementationDigest"],
            tuple_key=data["tupleKey"],
            receipt_ref=data["receiptRef"],
            details=dict(data["details"]),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "event": self.event,
            "at": self.at,
            "operator": self.operator,
            "chipAlias": self.chip_alias,
            "chipVersion": self.chip_version,
            "implementationDigest": self.implementation_digest,
            "tupleKey": self.tuple_key,
            "receiptRef": self.receipt_ref,
            "details": dict(self.details),
        }


def validate_lifecycle_event(data: dict[str, Any]) -> None:
    """Validate a lifecycle-event dict against the exact 0.5.0 schema, else raise.

    Enforces the exact top-level key set, the value types, the admitted event
    set, the tuple-gating rule for split/merge/optimize/retire, and the
    raw-model-baseline requirement for model-generation retirement. Raises
    :class:`LifecycleError` on any violation.
    """
    if not isinstance(data, dict):
        raise LifecycleError(f"lifecycle event must be an object, got {type(data).__name__}")
    keys = set(data)
    missing = _REQUIRED_KEYS - keys
    if missing:
        raise LifecycleError(f"lifecycle event missing required keys: {', '.join(sorted(missing))}")
    extra = keys - _REQUIRED_KEYS
    if extra:
        raise LifecycleError(f"lifecycle event has unexpected keys: {', '.join(sorted(extra))}")

    event = data["event"]
    if event not in LIFECYCLE_EVENTS:
        allowed = ", ".join(sorted(LIFECYCLE_EVENTS))
        raise LifecycleError(f"lifecycle event {event!r} not one of: {allowed}")

    for key in ("at", "operator", "chipAlias", "chipVersion", "implementationDigest"):
        value = data[key]
        if not isinstance(value, str) or not value.strip():
            raise LifecycleError(f"lifecycle event field {key!r} must be a non-empty string")

    for key in ("tupleKey", "receiptRef"):
        value = data[key]
        if value is not None and (not isinstance(value, str) or not value.strip()):
            raise LifecycleError(f"lifecycle event field {key!r} must be a non-empty string or null")

    details = data["details"]
    if not isinstance(details, dict):
        raise LifecycleError("lifecycle event field 'details' must be an object")

    if event in _TUPLE_GATED_EVENTS and not (
        isinstance(data["tupleKey"], str) and data["tupleKey"].strip()
    ):
        raise LifecycleError(
            f"lifecycle event {event!r} MUST carry the held-out 'tupleKey' that gated it "
            "(spec 0.5.0 Lifecycle telemetry)"
        )

    if event == "retire" and details.get("reason") == "model-generation":
        baseline = details.get("rawModelBaseline")
        if not isinstance(baseline, str) or not baseline.strip():
            raise LifecycleError(
                "a 'model-generation' retirement MUST reference a raw-model baseline comparison "
                "under details.rawModelBaseline (spec 0.5.0 Lifecycle telemetry)"
            )
