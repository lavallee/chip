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

# Sentinel value permitted for ``judgmentReceiptRef`` at EffectRequest
# construction time, before the run's judgment receipt exists (§8.3). The HOST
# MUST back-fill the real receipt reference before persisting or dispatching the
# effect; a dispatched effect still carrying this value is a host conformance
# violation.
PENDING_RECEIPT_REF = "pending"

# A run/attempt marker in a key input is unstable across retries and migrations
# and must never leak in. The guard is deliberately narrow: it rejects ONLY
# explicit run/attempt markers — the word-boundary forms `run-`, `run:`,
# `attempt-`, `attempt:`, `/runs/`, and `/attempts/`. It does NOT reject
# UUID-shaped values, because stable source lineage keys (message ids, entry ids)
# legitimately embed UUIDs. This regex is a best-effort tripwire for the obvious
# mistake, not the enforcement boundary (§8.3).
_RUN_MARKER_RE = re.compile(
    r"(?:^|[^0-9a-z])(?:run|attempt)[-:]|/(?:runs|attempts)/", re.IGNORECASE
)


class TrustClass(StrEnum):
    """Trust classification carried by a signal (§8.1). Retrieved content is hostile."""

    HOSTILE = "hostile"
    UNTRUSTED = "untrusted"
    ATTESTED = "attested"
    TRUSTED = "trusted"


class ResponseKind(StrEnum):
    """The four terminal run-outcome kinds of §8.2.

    ``kind`` names *how the run ended*, not what the envelope carries. The §8.2
    distinctions observation/claim/evidence/recommendation/uncertainty/expiry are
    envelope **fields** (see :class:`Response`), not kinds. Every run terminates as
    exactly one of:

    * ``finding`` — a claim/assessment (optionally with evidence, a recommendation,
      and uncertainty);
    * ``quiet`` — a first-class no-finding success;
    * ``abstain`` — the chip declined to claim (e.g. insufficient evidence); or
    * ``needs_input`` — a typed pending human decision (see :class:`NeedsInput`).
    """

    FINDING = "finding"
    QUIET = "quiet"
    ABSTAIN = "abstain"
    NEEDS_INPUT = "needs_input"


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

    ``content`` is the optional payload the chip actually assesses — typically a
    taint-marked ``{value, taint}`` marker (see :mod:`chip.taint`) — as distinct
    from the lineage/digest *metadata* above. For large payloads a host MAY omit
    ``content`` and carry a ``custody_ref`` to where the raw content lives (§8.1).
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
    content: Any | None = None  # taint-marked payload under assessment (§8.1)

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
            content=data.get("content"),
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
        if self.content is not None:
            out["content"] = self.content
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

    ``kind`` is one of the four terminal run outcomes (``finding`` | ``quiet`` |
    ``abstain`` | ``needs_input``, see :class:`ResponseKind`). The §8.2
    distinctions are carried as *fields*, not kinds: ``body`` (observation/claim),
    ``evidence`` (cited spans), ``recommendation`` (proposed response),
    ``uncertainty`` (confidence/counterevidence), and ``expiry`` (freshness).
    Fields derived from hostile input should be taint-marked (see
    :mod:`chip.taint`); ``needs_input`` carries a typed :class:`NeedsInput`.
    """

    kind: ResponseKind
    produced_by_chip: str
    produced_by_run: str
    body: dict[str, Any] = field(default_factory=dict)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    recommendation: dict[str, Any] | None = None
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
            recommendation=data.get("recommendation"),
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
        if self.recommendation is not None:
            out["recommendation"] = self.recommendation
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

    ``judgment_receipt_ref`` presents a chicken-and-egg: the request is built
    *before* the run's judgment receipt exists. The sentinel
    :data:`PENDING_RECEIPT_REF` (``"pending"``) is therefore allowed at
    construction. The HOST MUST back-fill the real receipt reference before
    persisting or dispatching the effect; a dispatched effect still carrying
    ``"pending"`` is a host conformance violation (see
    :func:`chip.conformance.hostkit.check_dispatched_effects_carry_receipt_refs`).
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
    """Reject a key input carrying an explicit run/attempt marker.

    Lineage keys are source-stable identifiers and may legitimately embed a
    UUID (message id, entry id), so UUID-shaped values are accepted. Only the
    explicit run/attempt marker forms are rejected — a best-effort tripwire, not
    the enforcement boundary (§8.3).
    """
    if not isinstance(value, str) or not value.strip():
        raise EnvelopeError(f"derive_effect_key: {name} must be a non-empty stable string")
    if _RUN_MARKER_RE.search(value):
        raise EnvelopeError(
            f"derive_effect_key: {name}={value!r} carries a run/attempt marker; "
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

    Lineage keys are source-stable identifiers and MAY embed a UUID (message
    id, entry id); such values are accepted. Hosts MUST NOT pass run-scoped ids.
    Each input is validated as a non-empty string; only a value carrying an
    explicit run/attempt marker raises :class:`EnvelopeError` — the guard is a
    best-effort tripwire, not the enforcement (the target owner is the final
    dedup authority, §8.3). The four fields are joined with a NUL separator
    (which cannot appear in the inputs) so distinct field boundaries can never
    collide.
    """
    _reject_unstable("lineage_key", lineage_key)
    _reject_unstable("effect_type", effect_type)
    _reject_unstable("target_owner", target_owner)
    _reject_unstable("promise_id", promise_id)
    material = "\0".join([lineage_key, effect_type, target_owner, promise_id])
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return _EFFECT_KEY_PREFIX + digest
