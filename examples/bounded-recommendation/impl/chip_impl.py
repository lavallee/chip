"""Bounded-recommendation chip implementation (deterministic).

Pure ``run(activation) -> {response, state, effects, stage_events}`` per the host
execution contract. No gateway stage: every judgment is rule/code based.

Promise: given a materiality finding, emit at most one rate-limited, evidence-
linked research recommendation effect request per unique lineage, or a quiet
result.

Stages: gate (policy) -> compose (code).

No I/O, no network, no imports beyond stdlib + ``chip.*``.
"""

from __future__ import annotations

from typing import Any

from chip.envelopes import derive_effect_key
from chip.errors import EnvelopeError
from chip.taint import is_tainted

CHIP_ID = "https://github.com/lavallee/chip/tree/main/examples/bounded-recommendation"
EFFECT_TYPE = "recommend-research"


def _empty_state() -> dict[str, Any]:
    return {"issued": []}


def _quiet(lineage: dict[str, Any], run_id: str, reason: str, state: dict[str, Any]) -> dict[str, Any]:
    response = {
        "kind": "quiet",
        "reason": reason,
        "lineage": lineage,
        "producedBy": {"chip": CHIP_ID, "run": run_id},
    }
    return {
        "response": response,
        "state": state,
        "effects": [],
        "stage_events": [{"stage": "gate", "kind": "policy", "note": reason}],
    }


def _abstain(lineage: dict[str, Any], run_id: str, reason: str, state: dict[str, Any]) -> dict[str, Any]:
    response = {
        "kind": "abstain",
        "reason": reason,
        "lineage": lineage,
        "producedBy": {"chip": CHIP_ID, "run": run_id},
    }
    return {
        "response": response,
        "state": state,
        "effects": [],
        "stage_events": [{"stage": "gate", "kind": "policy", "note": reason}],
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
    finding: dict[str, Any] = activation["signal"]
    state: dict[str, Any] = activation.get("state") or _empty_state()
    config: dict[str, Any] = activation.get("config") or {}
    run_id = config.get("runId", "run-local")

    lineage = finding.get("lineage")
    if not isinstance(lineage, dict) or not lineage.get("content_digest"):
        raise EnvelopeError("finding missing lineage.content_digest")
    content_digest = lineage["content_digest"]

    issued: list[str] = list(state.get("issued", []))

    # --- gate (deterministic policy) -------------------------------------
    # A finding with no evidence at all is malformed: fail closed.
    evidence = finding.get("evidence")
    if not isinstance(evidence, list) or len(evidence) == 0:
        raise EnvelopeError("finding has no evidence to link (fail closed)")
    # A finding whose evidence lost its taint markers is refused (abstain): the
    # chip will not launder hostile source text into a clean recommendation.
    if not _all_items_linked_and_tainted(evidence):
        return _abstain(lineage, run_id, "evidence-taint-lost-refuse-to-launder", state)

    # At-least-once delivery: one recommendation per unique lineage.
    if content_digest in issued:
        return _quiet(lineage, run_id, "already-issued", state)

    # Effect-key inputs are host-injected into config (§8.3, host-execution
    # contract): the canonical keys are `effect_target` and `promise_id`, so host
    # and implementation derive identical keys. Legacy camelCase kept as fallback.
    target_owner = config.get("effect_target") or config.get("targetOwner", "owner://research-ideas")
    promise_id = config.get("promise_id") or config.get("promiseId", CHIP_ID)

    # --- compose (deterministic) -----------------------------------------
    # Stable target-side dedupe key: lineage + effect type + target + promise id.
    # Excludes run id / mutable state, so it is identical across retries, cursor
    # resets, and state migration (spec 8.3).
    effect_key = derive_effect_key(content_digest, EFFECT_TYPE, target_owner, promise_id)

    assessment = finding.get("assessment", {})
    payload = {
        "recommendation": (
            "Open a bounded research task to corroborate the materiality finding "
            "and gather independent evidence before any downstream action."
        ),
        "rationale": (
            "Upstream materiality finding "
            f"(material={assessment.get('material')}, "
            f"confidence={assessment.get('confidence')}) warrants rate-limited follow-up."
        ),
        # Taint-preserving passthrough of the finding evidence.
        "evidence": finding.get("evidence", []),
        "lineage": lineage,
    }

    effect_request = {
        "type": EFFECT_TYPE,
        "class": "recommend",
        "targetOwner": target_owner,
        "payload": payload,
        "idempotencyKey": effect_key,
        "derivationVersion": "cek1",
        "expectedResultSchema": "schemas/research-recommendation.json@1",
        "originatingEvidenceRef": f"finding:{content_digest}",
        "judgmentReceiptRef": f"receipt:{run_id}",
        "preconditions": [],
        "approvalRequired": "human",
        "rateAccounting": {"scope": "installation", "perLineage": 1},
    }

    # Terminal kind is `finding` (one of the four §8.2 run outcomes); the issued
    # recommendation rides in the `recommendation` field. The circuit output PORT
    # is still named `recommendation-issued` — a port name, not a response kind.
    response = {
        "kind": "finding",
        "recommendation": {"issued": True, "effectKey": effect_key},
        "effectKey": effect_key,
        "lineage": lineage,
        "producedBy": {"chip": CHIP_ID, "run": run_id},
    }
    new_state = {"issued": [*issued, content_digest]}
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
