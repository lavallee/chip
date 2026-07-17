"""Conformance kit self-test with an honest in-memory FakeHost.

The FakeHost implements :class:`chip.conformance.HostDriver` faithfully — it
enforces target-side dedup, quiet-no-effect, fail-closed judgment, the observe
cap for unevaluated bindings, and capability denial. It doubles as executable
documentation for a real host: run the same ``check_*`` functions against your
host and they must pass identically.
"""

from __future__ import annotations

import itertools

import pytest

from chip.conformance import HostDriver, RunReport, Scenario, run_all
from chip.conformance.hostkit import (
    check_at_least_once_single_effect,
    check_dispatched_effects_carry_receipt_refs,
    check_duplicate_produces_no_effects,
    check_invalid_judgment_fails_closed,
    check_pause_and_revoke_produce_receipts,
    check_quiet_produces_no_effects,
    check_undeclared_capability_denied,
    check_unevaluated_tuple_capped_at_observe,
)
from chip.envelopes import derive_effect_key
from chip.receipts import (
    ATTENTION_SCHEMA,
    JUDGMENT_SCHEMA,
    Coordinates,
    build_attention_receipt,
    build_judgment_receipt,
)

_DECLARED_CAPABILITIES = {"state.single-flight.v1", "gateway-attempt.v1"}
_TARGET_OWNER = "owner:ideas"
_PROMISE = "promise#triage"


class _InstallationState:
    def __init__(self, binding: dict) -> None:
        self.binding = binding
        self.seen_effect_keys: set[str] = set()
        self.unevaluated = bool(binding.get("_unevaluated"))


class FakeHost:
    """A minimal but honest host implementation for conformance testing."""

    def __init__(self) -> None:
        self._installs: dict[str, _InstallationState] = {}
        self._counter = itertools.count(1)

    # -- HostDriver surface --

    def install(self, circuit: dict, binding: dict) -> str:
        iid = f"fabexp-{next(self._counter):08d}-triage"
        self._installs[iid] = _InstallationState(binding)
        return iid

    def activate(self, installation_id: str, signal: dict) -> RunReport:
        state = self._installs[installation_id]
        run_id = f"run:{next(self._counter)}"
        coords = Coordinates(
            run=run_id, installation=installation_id, circuit="circ:triage",
            chip="press.new-report-triage", binding="bind:1",
        )
        stype = signal.get("type")

        if stype == "quiet":
            receipt = build_attention_receipt(
                coords, run_status="completed", semantic_outcome="quiet",
                terminal_reason="no-new-report",
            )
            return RunReport(run_id=run_id, receipts=[receipt.to_dict()],
                             terminal_reason="no-new-report", run_status="completed")

        if stype == "invalid":
            # Canned malformed gateway result: validation rejects it -> fail closed.
            receipt = build_judgment_receipt(
                coords, run_status="failed", semantic_outcome="finding-invalid",
                terminal_reason="gateway-result-invalid",
                digests={"contract": "sha:c", "implementation": "sha:i", "policy": "sha:p"},
                decisions={
                    "validation": {"ok": False, "reason": "malformed gateway result"},
                    "dedupe": {}, "budget": {}, "authority": {},
                },
                effects={"proposed": [], "approved": [], "rejected": [], "executed": []},
                state_version_before="v1", state_version_after="v1",
            )
            return RunReport(run_id=run_id, receipts=[receipt.to_dict()],
                             terminal_reason="gateway-result-invalid", run_status="failed")

        # Positive / duplicate: build the stable effect key from lineage.
        effect_class = "observe" if state.unevaluated else "recommend"
        key = derive_effect_key(signal["lineageKey"], "recommend-research", _TARGET_OWNER, _PROMISE)
        request = {
            "type": "recommend-research", "class": effect_class,
            "targetOwner": _TARGET_OWNER, "idempotencyKey": key,
            # Host back-fills the real judgment-receipt ref (the run id every
            # receipt binds via coordinates.run) before dispatch — never "pending".
            "judgmentReceiptRef": run_id,
        }
        if key in state.seen_effect_keys:
            # Target-side dedup: no new effect, compact attention receipt.
            receipt = build_attention_receipt(
                coords, run_status="completed", semantic_outcome="duplicate",
                terminal_reason="duplicate-lineage",
                effect_decision={"deduped": True, "idempotencyKey": key},
            )
            return RunReport(run_id=run_id, receipts=[receipt.to_dict()],
                             effect_requests=[request], effects_executed=[],
                             terminal_reason="duplicate-lineage", run_status="completed")

        state.seen_effect_keys.add(key)
        receipt = build_judgment_receipt(
            coords, run_status="completed", semantic_outcome="finding-valid",
            terminal_reason="finding",
            digests={"contract": "sha:c", "implementation": "sha:i", "policy": "sha:p"},
            decisions={"validation": {"ok": True}, "dedupe": {"key": key},
                       "budget": {}, "authority": {"class": effect_class}},
            effects={"proposed": [request], "approved": [request],
                     "rejected": [], "executed": [request]},
            state_version_before="v1", state_version_after="v2",
        )
        return RunReport(run_id=run_id, receipts=[receipt.to_dict()],
                         effect_requests=[request], effects_executed=[request],
                         terminal_reason="finding", run_status="completed")

    def pause(self, installation_id: str) -> dict:
        return build_attention_receipt(
            Coordinates(run="run:pause", installation=installation_id, circuit="circ:triage",
                        chip="press.new-report-triage", binding="bind:1"),
            run_status="paused", semantic_outcome="installation-paused",
            terminal_reason="operator-pause",
        ).to_dict()

    def revoke(self, installation_id: str) -> dict:
        return build_attention_receipt(
            Coordinates(run="run:revoke", installation=installation_id, circuit="circ:triage",
                        chip="press.new-report-triage", binding="bind:1"),
            run_status="revoked", semantic_outcome="installation-revoked",
            terminal_reason="operator-revoke",
        ).to_dict()

    def capability_probe(self, installation_id: str, capability: str) -> bool:
        return capability in _DECLARED_CAPABILITIES


def _scenario(binding_dict, linear_circuit_dict, make_signal) -> Scenario:
    unevaluated = dict(binding_dict)
    unevaluated["_unevaluated"] = True
    return Scenario(
        circuit=linear_circuit_dict,
        binding=binding_dict,
        positive_signal=make_signal(type="publication", lineageKey="agency/pos/1",
                                    dedupeKey="agency/pos/1"),
        quiet_signal=make_signal(type="quiet", lineageKey="agency/none",
                                 dedupeKey="agency/none"),
        duplicate_signal=make_signal(type="publication", lineageKey="agency/dup/1",
                                     dedupeKey="agency/dup/1"),
        invalid_gateway_signal=make_signal(type="invalid", lineageKey="agency/bad/1",
                                           dedupeKey="agency/bad/1"),
        unevaluated_binding=unevaluated,
        undeclared_capability="http.fetch",
    )


def test_fakehost_satisfies_protocol():
    assert isinstance(FakeHost(), HostDriver)


def test_run_all_conformance_checks(binding_dict, linear_circuit_dict, make_signal):
    scenario = _scenario(binding_dict, linear_circuit_dict, make_signal)
    passed = run_all(FakeHost(), scenario)
    assert len(passed) == 8


def test_individual_checks(binding_dict, linear_circuit_dict, make_signal):
    scenario = _scenario(binding_dict, linear_circuit_dict, make_signal)
    check_quiet_produces_no_effects(FakeHost(), scenario)
    check_duplicate_produces_no_effects(FakeHost(), scenario)
    check_invalid_judgment_fails_closed(FakeHost(), scenario)
    check_at_least_once_single_effect(FakeHost(), scenario)
    check_dispatched_effects_carry_receipt_refs(FakeHost(), scenario)
    check_pause_and_revoke_produce_receipts(FakeHost(), scenario)
    check_unevaluated_tuple_capped_at_observe(FakeHost(), scenario)
    check_undeclared_capability_denied(FakeHost(), scenario)


def test_dispatched_effect_with_pending_ref_is_rejected(binding_dict, linear_circuit_dict, make_signal):
    scenario = _scenario(binding_dict, linear_circuit_dict, make_signal)

    class PendingHost(FakeHost):
        def activate(self, installation_id: str, signal: dict) -> RunReport:
            report = super().activate(installation_id, signal)
            # A misbehaving host that never back-fills the receipt ref.
            for eff in report.effects_executed:
                eff["judgmentReceiptRef"] = "pending"
            return report

    with pytest.raises(AssertionError, match="pending"):
        check_dispatched_effects_carry_receipt_refs(PendingHost(), scenario)


def test_receipt_tiers_are_what_checks_expect(binding_dict, linear_circuit_dict, make_signal):
    scenario = _scenario(binding_dict, linear_circuit_dict, make_signal)
    host = FakeHost()
    iid = host.install(scenario.circuit, scenario.binding)
    quiet = host.activate(iid, scenario.quiet_signal)
    assert quiet.receipts[-1]["schema"] == ATTENTION_SCHEMA
    finding = host.activate(iid, scenario.positive_signal)
    assert finding.receipts[-1]["schema"] == JUDGMENT_SCHEMA
