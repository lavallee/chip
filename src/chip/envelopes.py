"""Signal, response, and effect-request envelopes, plus stable key derivation.

Implements chip.spec/v0alpha1 §8. These are the typed boundaries a chip
observes and produces. All three are frozen dataclasses with ``from_dict`` /
``to_dict`` so the canonical interchange stays plain JSON dicts.

The most safety-critical function here is :func:`derive_effect_key`, which
produces the target-side deduplication key (§8.3). It is deliberately narrow:
it MUST NOT incorporate a run id or mutable state, and it MUST survive state
migration, because "the target owning system is the final deduplication
authority" (§8.3, §12).
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from chip.errors import EnvelopeError

# Effect-key scheme prefix; version it so a future derivation change is legible.
_EFFECT_KEY_PREFIX = "cek1-"

# Inputs that look like run ids or mutable state are rejected by
# derive_effect_key. A bare UUID, or any token carrying a run/attempt/state
# marker, is unstable across retries and migrations and must never leak in.
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
)
_UNSTABLE_TOKEN_RE = re.compile(
    r"(?:^|[^a-z])(run|attempt|state|session)[-_:#=]", re.IGNORECASE
)


class TrustClass(StrEnum):
    """Trust classification carried by a signal (§8.1). Retrieved content is hostile."""

    HOSTILE = "hostile"
    UNTRUSTED = "untrusted"
    ATTESTED = "attested"
    TRUSTED = "trusted"


class ResponseKind(StrEnum):
    """The mutually-distinguished response varieties of §8.2."""

    OBSERVATION = "observation"
    CLAIM = "claim"
    EVIDENCE = "evidence"
    RECOMMENDATION = "recommendation"
    UNCERTAINTY = "uncertainty"
    ABSTENTION = "abstention"
    QUIET = "quiet"
    NEEDS_INPUT = "needs_input"
    EXPIRY = "expiry"


def _require(d: dict[str, Any], key: str, ctx: str) -> Any:
    if key not in d or d[key] in (None, ""):
        raise EnvelopeError(f"{ctx}: missing required field {key!r}")
    return d[key]


@dataclass(frozen=True, slots=True)
class Signal:
    """An input envelope (§8.1).

    ``lineage_key`` and ``dedupe_key`` are the stable identifiers a host uses to
    detect duplicate and successor signals. ``trust`` defaults to ``hostile``
    because retrieved content is hostile data that MUST NOT be interpreted as
    instructions.
    """

    id: str
    type: str
    schema_version: str
    observed_at: str
    received_at: str
    source: str  # source coordinate
    authority_context: str
    digest: str  # content or evidence digest
    lineage_key: str
    dedupe_key: str
    trust: TrustClass = TrustClass.HOSTILE
    prior_signal: str | None = None
    custody_ref: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Signal:
        ctx = "signal"
        return cls(
            id=_require(data, "id", ctx),
            type=_require(data, "type", ctx),
            schema_version=_require(data, "schemaVersion", ctx),
            observed_at=_require(data, "observedAt", ctx),
            received_at=_require(data, "receivedAt", ctx),
            source=_require(data, "source", ctx),
            authority_context=_require(data, "authorityContext", ctx),
            digest=_require(data, "digest", ctx),
            lineage_key=_require(data, "lineageKey", ctx),
            dedupe_key=_require(data, "dedupeKey", ctx),
            trust=TrustClass(data.get("trust", "hostile")),
            prior_signal=data.get("priorSignal"),
            custody_ref=data.get("custodyRef"),
        )

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "id": self.id,
            "type": self.type,
            "schemaVersion": self.schema_version,
            "observedAt": self.observed_at,
            "receivedAt": self.received_at,
            "source": self.source,
            "authorityContext": self.authority_context,
            "digest": self.digest,
            "lineageKey": self.lineage_key,
            "dedupeKey": self.dedupe_key,
            "trust": self.trust.value,
        }
        if self.prior_signal is not None:
            out["priorSignal"] = self.prior_signal
        if self.custody_ref is not None:
            out["custodyRef"] = self.custody_ref
        return out


@dataclass(frozen=True, slots=True)
class NeedsInput:
    """A typed pending decision produced by a ``needs_input`` response (§8.2).

    A ``needs_input`` result is never terminal prose: it creates a correlated,
    schema-bound question with a decision owner, an expiry, and a declared lapse
    outcome so an unanswered question becomes a quiet/failed run rather than an
    indefinite wait.
    """

    question_schema: str
    decision_owner: str
    expiry: str
    lapse_outcome: str  # e.g. "quiet" | "failed"
    question: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NeedsInput:
        ctx = "needs_input"
        return cls(
            question_schema=_require(data, "questionSchema", ctx),
            decision_owner=_require(data, "decisionOwner", ctx),
            expiry=_require(data, "expiry", ctx),
            lapse_outcome=_require(data, "lapseOutcome", ctx),
            question=data.get("question", {}),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "questionSchema": self.question_schema,
            "decisionOwner": self.decision_owner,
            "expiry": self.expiry,
            "lapseOutcome": self.lapse_outcome,
            "question": self.question,
        }


@dataclass(frozen=True, slots=True)
class Response:
    """An output envelope (§8.2).

    ``kind`` selects among the distinguished varieties (observation, claim,
    evidence, recommendation, uncertainty, abstention, quiet, needs_input,
    expiry). Fields derived from hostile input should be taint-marked (see
    :mod:`chip.taint`); ``needs_input`` carries a typed :class:`NeedsInput`.
    """

    kind: ResponseKind
    produced_by_chip: str
    produced_by_run: str
    body: dict[str, Any] = field(default_factory=dict)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    uncertainty: dict[str, Any] | None = None
    expiry: str | None = None
    needs_input: NeedsInput | None = None
    produced_by_circuit: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Response:
        ctx = "response"
        kind = ResponseKind(_require(data, "kind", ctx))
        needs = data.get("needsInput")
        return cls(
            kind=kind,
            produced_by_chip=_require(data, "producedByChip", ctx),
            produced_by_run=_require(data, "producedByRun", ctx),
            body=data.get("body", {}),
            evidence=list(data.get("evidence", [])),
            uncertainty=data.get("uncertainty"),
            expiry=data.get("expiry"),
            needs_input=NeedsInput.from_dict(needs) if needs else None,
            produced_by_circuit=data.get("producedByCircuit"),
        )

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "kind": self.kind.value,
            "producedByChip": self.produced_by_chip,
            "producedByRun": self.produced_by_run,
            "body": self.body,
            "evidence": self.evidence,
        }
        if self.uncertainty is not None:
            out["uncertainty"] = self.uncertainty
        if self.expiry is not None:
            out["expiry"] = self.expiry
        if self.needs_input is not None:
            out["needsInput"] = self.needs_input.to_dict()
        if self.produced_by_circuit is not None:
            out["producedByCircuit"] = self.produced_by_circuit
        return out


@dataclass(frozen=True, slots=True)
class EffectRequest:
    """A typed request for the host policy boundary to dispatch an effect (§8.3).

    Model text never executes an effect directly; it constructs one of these and
    hands it to the host, which decides authorisation and dispatches through an
    adapter. ``idempotency_key`` must come from :func:`derive_effect_key`.
    """

    type: str
    effect_class: str  # EffectClass label, kept as string for round-trip fidelity
    target_owner: str
    payload: dict[str, Any]
    idempotency_key: str
    derivation_version: str
    expected_result_schema: str
    originating_evidence_ref: str
    judgment_receipt_ref: str
    preconditions: list[dict[str, Any]] = field(default_factory=list)
    freshness_deadline: str | None = None
    approval_required: str = "human"
    approval_receipt_ref: str | None = None
    compensation: dict[str, Any] | None = None
    rate_accounting: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EffectRequest:
        ctx = "effect request"
        return cls(
            type=_require(data, "type", ctx),
            effect_class=_require(data, "class", ctx),
            target_owner=_require(data, "targetOwner", ctx),
            payload=data.get("payload", {}),
            idempotency_key=_require(data, "idempotencyKey", ctx),
            derivation_version=_require(data, "derivationVersion", ctx),
            expected_result_schema=_require(data, "expectedResultSchema", ctx),
            originating_evidence_ref=_require(data, "originatingEvidenceRef", ctx),
            judgment_receipt_ref=_require(data, "judgmentReceiptRef", ctx),
            preconditions=list(data.get("preconditions", [])),
            freshness_deadline=data.get("freshnessDeadline"),
            approval_required=data.get("approvalRequired", "human"),
            approval_receipt_ref=data.get("approvalReceiptRef"),
            compensation=data.get("compensation"),
            rate_accounting=data.get("rateAccounting", {}),
        )

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "type": self.type,
            "class": self.effect_class,
            "targetOwner": self.target_owner,
            "payload": self.payload,
            "idempotencyKey": self.idempotency_key,
            "derivationVersion": self.derivation_version,
            "expectedResultSchema": self.expected_result_schema,
            "originatingEvidenceRef": self.originating_evidence_ref,
            "judgmentReceiptRef": self.judgment_receipt_ref,
            "preconditions": self.preconditions,
            "approvalRequired": self.approval_required,
            "rateAccounting": self.rate_accounting,
        }
        if self.freshness_deadline is not None:
            out["freshnessDeadline"] = self.freshness_deadline
        if self.approval_receipt_ref is not None:
            out["approvalReceiptRef"] = self.approval_receipt_ref
        if self.compensation is not None:
            out["compensation"] = self.compensation
        return out


def _reject_unstable(name: str, value: str) -> None:
    """Reject a key input that looks like a run id or mutable-state token."""
    if not isinstance(value, str) or not value.strip():
        raise EnvelopeError(f"derive_effect_key: {name} must be a non-empty stable string")
    if _UUID_RE.match(value.strip()):
        raise EnvelopeError(
            f"derive_effect_key: {name}={value!r} looks like a run id (UUID); "
            "the key must derive only from stable lineage, not run identity (§8.3)"
        )
    if _UNSTABLE_TOKEN_RE.search(value):
        raise EnvelopeError(
            f"derive_effect_key: {name}={value!r} carries a run/attempt/state marker; "
            "the key MUST NOT include a run id or mutable state (§8.3)"
        )


def derive_effect_key(
    lineage_key: str,
    effect_type: str,
    target_owner: str,
    promise_id: str,
) -> str:
    """Derive the stable target-side deduplication key for an effect (§8.3).

    The key is ``"cek1-" + sha256hex`` over the four stable inputs: source
    lineage, effect type, target owning system, and operational-promise
    identity. It deliberately excludes any run id or mutable state so it is
    identical across retries, cursor resets, and state migrations — the property
    the target owner relies on as the *final* deduplication authority.

    Each input is validated as a stable string; a run-id-shaped or
    state-marked value raises :class:`EnvelopeError`. The four fields are joined
    with a NUL separator (which cannot appear in the inputs) so distinct field
    boundaries can never collide.
    """
    _reject_unstable("lineage_key", lineage_key)
    _reject_unstable("effect_type", effect_type)
    _reject_unstable("target_owner", target_owner)
    _reject_unstable("promise_id", promise_id)
    material = "\0".join([lineage_key, effect_type, target_owner, promise_id])
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return _EFFECT_KEY_PREFIX + digest
