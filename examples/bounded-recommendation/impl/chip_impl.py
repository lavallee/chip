"""Bounded-recommendation chip implementation (deterministic).

Pure ``run(activation) -> {response, state, effects, stage_events}`` per the host
execution contract. No gateway stage: every judgment is rule/code based.

Promise: given a materiality finding, emit at most one rate-limited, evidence-
linked research recommendation effect request per unique lineage, or a quiet
result.

Stages: gate (policy) -> compose (code).

This chip sits at a non-first circuit position: the host delivers the prior
chip's response as ``activation["upstream"]`` (the materiality finding) and the
originating §8.1 signal envelope as ``activation["signal"]``. Effect-key inputs
come from the *signal* envelope (``lineageKey``) and host-injected ``config``
(``effect_target``/``promise_id``) so the host's recomputation matches (§8.3).

When the chip is exercised in isolation — a host ``evaluate`` run, or a
standalone fixture — there is no upstream: the finding is then delivered inline
as the signal's taint-marked ``content`` payload. The chip accepts either
delivery mode, so its fixtures are host-evaluatable without a circuit.

No I/O, no network, no imports beyond stdlib + ``chip.*``.
"""

from __future__ import annotations

from typing import Any

from chip.envelopes import PENDING_RECEIPT_REF, derive_effect_key
from chip.errors import EnvelopeError
from chip.taint import is_tainted

CHIP_ID = "https://github.com/lavallee/chip/tree/main/examples/bounded-recommendation"
EFFECT_TYPE = "recommend-research"


def _empty_state() -> dict[str, Any]:
    return {"issued": []}


def _untaint(value: Any) -> Any:
    if is_tainted(value):
        return value["value"]
    return value


def _quiet(alias: str, run_id: str, reason: str, lineage_key: str,
           state: dict[str, Any]) -> dict[str, Any]:
    response = {
        "kind": "quiet",
        "producedByChip": alias,
        "producedByRun": run_id,
        "body": {"reason": reason, "lineageKey": lineage_key},
    }
    return {
        "response": response,
        "state": state,
        "effects": [],
        "stage_events": [{"stage": "gate", "kind": "policy", "note": reason}],
    }


def _abstain(alias: str, run_id: str, reason: str, lineage_key: str,
             state: dict[str, Any]) -> dict[str, Any]:
    response = {
        "kind": "abstain",
        "producedByChip": alias,
        "producedByRun": run_id,
        "body": {"reason": reason, "lineageKey": lineage_key},
    }
    return {
        "response": response,
        "state": state,
        "effects": [],
        "stage_events": [{"stage": "gate", "kind": "policy", "note": reason}],
    }


def _finding_from_signal(signal: dict[str, Any]) -> dict[str, Any] | None:
    """Reconstruct the upstream finding from the signal's ``content`` payload.

    Isolation path (host ``evaluate`` / standalone fixture): the finding rides in
    the signal envelope's taint-marked ``content`` as ``{assessment, evidence,
    lineageKey}``. Returns a finding-shaped ``{kind, body, evidence}`` dict, or
    ``None`` when the content carries no assessment (nothing to recommend on).
    """
    content = signal.get("content")
    if content is None:
        return None
    value = content["value"] if is_tainted(content) else content
    if not isinstance(value, dict) or "assessment" not in value:
        return None
    return {
        "kind": "finding",
        "body": {"assessment": value["assessment"], "lineageKey": value.get("lineageKey")},
        "evidence": value.get("evidence", []),
    }


def _all_items_linked_and_tainted(evidence: list[Any]) -> bool:
    """Every evidence item must carry a taint-preserving quoted_span + source_url + digest.

    A finding whose evidence lost its taint markers is refused (not raised): the
    chip abstains rather than launder hostile source text into a clean
    recommendation (spec 8.2).
    """
    for item in evidence:
        if not isinstance(item, dict):
            return False
        if not item.get("source_url") or not item.get("digest"):
            return False
        span = item.get("quoted_span")
        # quoted_span must still be a taint marker ({value, taint} with trust).
        if not is_tainted(span):
            return False
    return True


def run(activation: dict[str, Any]) -> dict[str, Any]:
    signal: dict[str, Any] = activation["signal"]
    upstream: dict[str, Any] | None = activation.get("upstream")
    state: dict[str, Any] = activation.get("state") or _empty_state()
    config: dict[str, Any] = activation.get("config") or {}
    # The host injects the run id at the top level of the activation (host
    # execution contract); fall back to a config value / local default.
    run_id = activation.get("run_id") or config.get("runId", "run-local")
    alias = config.get("chipAlias") or CHIP_ID

    # Lineage identity comes from the §8.1 signal envelope; it is the stable key
    # the host recomputes the effect key against (§8.3).
    lineage_key = signal.get("lineageKey")
    if not lineage_key:
        raise EnvelopeError("signal missing lineageKey (§8.1)")

    # --- gate (deterministic policy) -----------------------------------------
    # The finding arrives as the prior chip's response on `upstream`. A quiet
    # upstream is a first-class quiet run, no effect. With no upstream at all
    # (isolation / evaluate) the finding is delivered inline in the signal content.
    if upstream is not None:
        if upstream.get("kind") == "quiet":
            return _quiet(alias, run_id, "no-finding", lineage_key, state)
        finding = upstream
    else:
        finding = _finding_from_signal(signal)
    if not finding:
        return _quiet(alias, run_id, "no-finding", lineage_key, state)

    evidence = finding.get("evidence")
    # A finding with no evidence at all is malformed: fail closed.
    if not isinstance(evidence, list) or len(evidence) == 0:
        raise EnvelopeError("finding has no evidence to link (fail closed)")
    # A finding whose evidence lost its taint markers is refused (abstain): the
    # chip will not launder hostile source text into a clean recommendation.
    if not _all_items_linked_and_tainted(evidence):
        return _abstain(alias, run_id, "evidence-taint-lost-refuse-to-launder", lineage_key, state)

    issued: list[str] = list(state.get("issued", []))
    # At-least-once delivery: one recommendation per unique lineage.
    if lineage_key in issued:
        return _quiet(alias, run_id, "already-issued", lineage_key, state)

    # Effect-key inputs are host-injected into config (§8.3, host-execution
    # contract): the canonical keys are `effect_target` and `promise_id`, so host
    # and implementation derive identical keys. Legacy camelCase kept as fallback.
    target_owner = (config.get("effect_target")
                    or config.get("effectDestinations", {}).get(EFFECT_TYPE)
                    or config.get("targetOwner", "owner://research-ideas"))
    promise_id = config.get("promise_id") or config.get("promiseId", CHIP_ID)

    # --- compose (deterministic) ---------------------------------------------
    # Stable target-side dedupe key: lineage + effect type + target + promise id.
    # Excludes run id / mutable state, so it is identical across retries, cursor
    # resets, and state migration (spec 8.3).
    effect_key = derive_effect_key(lineage_key, EFFECT_TYPE, target_owner, promise_id)

    assessment = (finding.get("body") or {}).get("assessment", {})
    payload = {
        "recommendation": (
            "Open a bounded research task to corroborate the materiality finding "
            "and gather independent evidence before any downstream action."
        ),
        "rationale": (
            "Upstream materiality finding "
            f"(material={_untaint(assessment.get('material'))}, "
            f"confidence={_untaint(assessment.get('confidence'))}) warrants rate-limited follow-up."
        ),
        # Taint-preserving passthrough of the finding evidence.
        "evidence": evidence,
        "lineage": {"content_digest": signal.get("digest", lineage_key), "lineageKey": lineage_key},
    }

    effect_request = {
        "type": EFFECT_TYPE,
        "class": "synthesize",
        "targetOwner": target_owner,
        "payload": payload,
        "idempotencyKey": effect_key,
        "derivationVersion": "cek1",
        "expectedResultSchema": "schemas/research-recommendation.json@1",
        "originatingEvidenceRef": signal.get("digest") or f"finding:{lineage_key}",
        # Built before the run's judgment receipt exists; the host back-fills the
        # real receipt reference before persisting or dispatching (§8.3).
        "judgmentReceiptRef": PENDING_RECEIPT_REF,
        "preconditions": [],
        "approvalRequired": "human",
        "rateAccounting": {"scope": "installation", "perLineage": 1},
    }

    # Terminal kind is `finding` (one of the four §8.2 run outcomes); the issued
    # recommendation rides in the `body.recommendation` field. The circuit output
    # PORT is still named `recommendation-issued` — a port name, not a kind.
    response = {
        "kind": "finding",
        "producedByChip": alias,
        "producedByRun": run_id,
        "body": {
            "recommendation": {"issued": True, "effectKey": effect_key},
            "effectKey": effect_key,
            "lineageKey": lineage_key,
        },
    }
    new_state = {"issued": [*issued, lineage_key]}
    stage_events = [
        {"stage": "gate", "kind": "policy", "note": "evidence linked, lineage not yet issued"},
        {"stage": "compose", "kind": "code", "note": "effect request composed"},
    ]
    return {
        "response": response,
        "state": new_state,
        "effects": [effect_request],
        "stage_events": stage_events,
    }
