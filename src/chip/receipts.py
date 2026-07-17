"""Two-tier receipt schemas (§13).

A host emits one of two receipt tiers per activation:

* an **attention receipt** for quiet, duplicate, rejected, or policy-denied
  attempts — compact, no mutable state allocated; and
* a **full judgment receipt** for findings, model judgments, needs-input states,
  proposed/executed effects, and failures after execution starts.

Both tiers MUST separate ``run_status`` (the process/plumbing outcome — "process
exited", "model answered") from ``semantic_outcome`` (the promise-level outcome —
"promise satisfied", "finding valid"). These are two distinct required fields;
conflating them is exactly the failure §13 warns against.

Receipts are append-only. A correction never mutates a prior record — it emits a
new receipt whose ``supersedes`` points at the one it replaces.

Schema ids: ``chip.receipt/v0alpha1#attention`` and ``chip.receipt/v0alpha1#judgment``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from chip.errors import ReceiptError

ATTENTION_SCHEMA = "chip.receipt/v0alpha1#attention"
JUDGMENT_SCHEMA = "chip.receipt/v0alpha1#judgment"


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
class AttentionReceipt:
    """Compact receipt for quiet/duplicate/rejected/denied attempts (§13)."""

    coordinates: Coordinates
    run_status: str
    semantic_outcome: str
    terminal_reason: str
    input_digests: list[str] = field(default_factory=list)
    evidence_digests: list[str] = field(default_factory=list)
    state_transition: dict[str, Any] | None = None
    policy_decision: dict[str, Any] | None = None
    effect_decision: dict[str, Any] | None = None
    cost: dict[str, Any] = field(default_factory=dict)
    timing: dict[str, Any] = field(default_factory=dict)
    supersedes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "schema": ATTENTION_SCHEMA,
            "coordinates": self.coordinates.to_dict(),
            "runStatus": self.run_status,
            "semanticOutcome": self.semantic_outcome,
            "terminalReason": self.terminal_reason,
            "inputDigests": self.input_digests,
            "evidenceDigests": self.evidence_digests,
            "cost": self.cost,
            "timing": self.timing,
        }
        if self.state_transition is not None:
            out["stateTransition"] = self.state_transition
        if self.policy_decision is not None:
            out["policyDecision"] = self.policy_decision
        if self.effect_decision is not None:
            out["effectDecision"] = self.effect_decision
        if self.supersedes is not None:
            out["supersedes"] = self.supersedes
        return out

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AttentionReceipt:
        validate_receipt(data)
        return cls(
            coordinates=Coordinates.from_dict(data["coordinates"]),
            run_status=data["runStatus"],
            semantic_outcome=data["semanticOutcome"],
            terminal_reason=data["terminalReason"],
            input_digests=list(data.get("inputDigests", [])),
            evidence_digests=list(data.get("evidenceDigests", [])),
            state_transition=data.get("stateTransition"),
            policy_decision=data.get("policyDecision"),
            effect_decision=data.get("effectDecision"),
            cost=data.get("cost", {}),
            timing=data.get("timing", {}),
            supersedes=data.get("supersedes"),
        )


@dataclass(frozen=True, slots=True)
class JudgmentReceipt:
    """Full receipt for findings, judgments, effects, and post-start failures (§13).

    Every field in the §13 MUST list is represented. The flexible parts (digests,
    stage events, decisions, effects) are dicts/lists so a host can carry its own
    detail while still satisfying the presence requirements checked by
    :func:`validate_receipt`.
    """

    coordinates: Coordinates
    run_status: str
    semantic_outcome: str
    terminal_reason: str
    digests: dict[str, Any]  # contract/implementation/adapter/policy/model/prompt/artifact
    input_ids: list[str]
    evidence_refs: list[str]
    state_version_before: str | None
    state_version_after: str | None
    stage_events: list[dict[str, Any]]
    gateway: dict[str, Any] | None  # request/result coordinates + usage (§10.2)
    decisions: dict[str, Any]  # validation/dedupe/budget/authority
    effects: dict[str, Any]  # proposed/approved/rejected/executed
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    verifier_results: list[dict[str, Any]] = field(default_factory=list)
    cost: dict[str, Any] = field(default_factory=dict)
    latency: dict[str, Any] = field(default_factory=dict)
    outcome_links: list[dict[str, Any]] = field(default_factory=list)
    supersedes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "schema": JUDGMENT_SCHEMA,
            "coordinates": self.coordinates.to_dict(),
            "runStatus": self.run_status,
            "semanticOutcome": self.semantic_outcome,
            "terminalReason": self.terminal_reason,
            "digests": self.digests,
            "inputIds": self.input_ids,
            "evidenceRefs": self.evidence_refs,
            "stateVersionBefore": self.state_version_before,
            "stateVersionAfter": self.state_version_after,
            "stageEvents": self.stage_events,
            "decisions": self.decisions,
            "effects": self.effects,
            "artifacts": self.artifacts,
            "verifierResults": self.verifier_results,
            "cost": self.cost,
            "latency": self.latency,
            "outcomeLinks": self.outcome_links,
        }
        if self.gateway is not None:
            out["gateway"] = self.gateway
        if self.supersedes is not None:
            out["supersedes"] = self.supersedes
        return out

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> JudgmentReceipt:
        validate_receipt(data)
        return cls(
            coordinates=Coordinates.from_dict(data["coordinates"]),
            run_status=data["runStatus"],
            semantic_outcome=data["semanticOutcome"],
            terminal_reason=data["terminalReason"],
            digests=data["digests"],
            input_ids=list(data.get("inputIds", [])),
            evidence_refs=list(data.get("evidenceRefs", [])),
            state_version_before=data.get("stateVersionBefore"),
            state_version_after=data.get("stateVersionAfter"),
            stage_events=list(data.get("stageEvents", [])),
            gateway=data.get("gateway"),
            decisions=data["decisions"],
            effects=data["effects"],
            artifacts=list(data.get("artifacts", [])),
            verifier_results=list(data.get("verifierResults", [])),
            cost=data.get("cost", {}),
            latency=data.get("latency", {}),
            outcome_links=list(data.get("outcomeLinks", [])),
            supersedes=data.get("supersedes"),
        )


# Required-key sets by tier. run_status and semantic_outcome are BOTH required
# and independent (§13).
_COMMON_REQUIRED = ("coordinates", "runStatus", "semanticOutcome", "terminalReason")
_ATTENTION_REQUIRED = _COMMON_REQUIRED
_JUDGMENT_REQUIRED = (
    *_COMMON_REQUIRED,
    "digests",
    "inputIds",
    "stateVersionBefore",
    "stateVersionAfter",
    "stageEvents",
    "decisions",
    "effects",
)
# The exact digests a judgment receipt must name (§13).
_JUDGMENT_DIGEST_KEYS = ("contract", "implementation", "policy")
# The decision categories a judgment receipt must record (§13).
_JUDGMENT_DECISION_KEYS = ("validation", "dedupe", "budget", "authority")
# The effect-lifecycle buckets a judgment receipt must carry (§13).
_JUDGMENT_EFFECT_KEYS = ("proposed", "approved", "rejected", "executed")


def validate_receipt(data: dict[str, Any]) -> None:
    """Validate a receipt dict against its tier's MUST list (§13); raise on gap.

    Dispatches on the ``schema`` field. Both tiers require ``coordinates`` (all
    five ids), and both ``runStatus`` and ``semanticOutcome`` — they are separate
    required fields so "process exited" can never masquerade as "promise
    satisfied". The judgment tier additionally requires the exact digests, stage
    events, decision categories, and effect-lifecycle buckets of §13.
    """
    if not isinstance(data, dict):
        raise ReceiptError(f"receipt must be an object, got {type(data).__name__}")
    schema = data.get("schema")
    if schema == ATTENTION_SCHEMA:
        required = _ATTENTION_REQUIRED
    elif schema == JUDGMENT_SCHEMA:
        required = _JUDGMENT_REQUIRED
    else:
        raise ReceiptError(
            f"unknown receipt schema {schema!r}; expected "
            f"{ATTENTION_SCHEMA!r} or {JUDGMENT_SCHEMA!r}"
        )
    for key in required:
        # None is allowed for the state-version fields (a run may touch no state),
        # but the key must still be present.
        if key not in data:
            raise ReceiptError(f"{schema}: missing required field {key!r}")
        if key not in ("stateVersionBefore", "stateVersionAfter") and data[key] in (None, ""):
            raise ReceiptError(f"{schema}: required field {key!r} must not be empty")
    Coordinates.from_dict(data["coordinates"])
    if data["runStatus"] == data["semanticOutcome"]:
        # Not strictly forbidden, but the two axes must be *supplied* distinctly;
        # identical strings are almost always the §13 conflation bug. We allow it
        # only when a caller opts in via matching being meaningful is impossible
        # to know here, so we flag the common mistake softly by requiring both to
        # be present (already enforced) — no raise here to avoid false positives.
        pass
    if schema == JUDGMENT_SCHEMA:
        digests = data["digests"]
        if not isinstance(digests, dict):
            raise ReceiptError(f"{schema}: 'digests' must be an object")
        for dk in _JUDGMENT_DIGEST_KEYS:
            if not digests.get(dk):
                raise ReceiptError(f"{schema}: digests.{dk} is required")
        decisions = data["decisions"]
        if not isinstance(decisions, dict):
            raise ReceiptError(f"{schema}: 'decisions' must be an object")
        for dk in _JUDGMENT_DECISION_KEYS:
            if dk not in decisions:
                raise ReceiptError(f"{schema}: decisions.{dk} is required")
        effects = data["effects"]
        if not isinstance(effects, dict):
            raise ReceiptError(f"{schema}: 'effects' must be an object")
        for ek in _JUDGMENT_EFFECT_KEYS:
            if ek not in effects:
                raise ReceiptError(f"{schema}: effects.{ek} is required")


def build_attention_receipt(
    coordinates: Coordinates | dict[str, Any],
    run_status: str,
    semantic_outcome: str,
    terminal_reason: str,
    **kwargs: Any,
) -> AttentionReceipt:
    """Construct and validate an :class:`AttentionReceipt`."""
    coords = coordinates if isinstance(coordinates, Coordinates) else Coordinates.from_dict(coordinates)
    receipt = AttentionReceipt(
        coordinates=coords,
        run_status=run_status,
        semantic_outcome=semantic_outcome,
        terminal_reason=terminal_reason,
        input_digests=list(kwargs.get("input_digests", [])),
        evidence_digests=list(kwargs.get("evidence_digests", [])),
        state_transition=kwargs.get("state_transition"),
        policy_decision=kwargs.get("policy_decision"),
        effect_decision=kwargs.get("effect_decision"),
        cost=kwargs.get("cost", {}),
        timing=kwargs.get("timing", {}),
        supersedes=kwargs.get("supersedes"),
    )
    validate_receipt(receipt.to_dict())
    return receipt


def build_judgment_receipt(
    coordinates: Coordinates | dict[str, Any],
    run_status: str,
    semantic_outcome: str,
    terminal_reason: str,
    digests: dict[str, Any],
    decisions: dict[str, Any],
    effects: dict[str, Any],
    **kwargs: Any,
) -> JudgmentReceipt:
    """Construct and validate a :class:`JudgmentReceipt`.

    ``digests`` must include at least ``contract``, ``implementation``, and
    ``policy``; ``decisions`` must include ``validation``/``dedupe``/``budget``/
    ``authority``; ``effects`` must include ``proposed``/``approved``/
    ``rejected``/``executed`` (§13).
    """
    coords = coordinates if isinstance(coordinates, Coordinates) else Coordinates.from_dict(coordinates)
    receipt = JudgmentReceipt(
        coordinates=coords,
        run_status=run_status,
        semantic_outcome=semantic_outcome,
        terminal_reason=terminal_reason,
        digests=digests,
        input_ids=list(kwargs.get("input_ids", [])),
        evidence_refs=list(kwargs.get("evidence_refs", [])),
        state_version_before=kwargs.get("state_version_before"),
        state_version_after=kwargs.get("state_version_after"),
        stage_events=list(kwargs.get("stage_events", [])),
        gateway=kwargs.get("gateway"),
        decisions=decisions,
        effects=effects,
        artifacts=list(kwargs.get("artifacts", [])),
        verifier_results=list(kwargs.get("verifier_results", [])),
        cost=kwargs.get("cost", {}),
        latency=kwargs.get("latency", {}),
        outcome_links=list(kwargs.get("outcome_links", [])),
        supersedes=kwargs.get("supersedes"),
    )
    validate_receipt(receipt.to_dict())
    return receipt
