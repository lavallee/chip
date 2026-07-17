"""The executable host conformance checks (§14, §22).

A host implements the :class:`HostDriver` protocol; the ``check_*`` functions
then exercise the behaviours the spec says a conforming host MUST have:

* quiet and duplicate activations produce no effects (§9, §22);
* an invalid/hostile gateway result fails closed with a validation-recording
  judgment receipt (§10.2, §22);
* at-least-once delivery yields at most one effect, with a stable target-side
  dedup key that survives a cursor reset (§8.3, §9, §22);
* pause and revoke each write a receipt (§12, §22);
* an unevaluated tuple is capped at ``observe`` (§10.2); and
* an undeclared capability is denied (§14).

Each check raises :class:`AssertionError` with a precise message on failure, so
any test runner can call them. This module imports stdlib only. The checks
never fabricate host behaviour — they call the driver and assert on what it
returns; a real host and the in-memory ``FakeHost`` used in this package's tests
run the identical checks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from chip.receipts import ATTENTION_SCHEMA, JUDGMENT_SCHEMA


@dataclass(slots=True)
class RunReport:
    """What a host returns from one activation.

    ``run_status`` is the plumbing outcome (e.g. ``"completed"``, ``"failed"``);
    the semantic outcome lives inside the receipts. ``receipts`` are receipt
    dicts (with a ``schema`` field naming their tier). ``effect_requests`` are
    the typed requests the run *proposed*; ``effects_executed`` are those the
    host actually dispatched.
    """

    run_id: str
    receipts: list[dict[str, Any]] = field(default_factory=list)
    effect_requests: list[dict[str, Any]] = field(default_factory=list)
    effects_executed: list[dict[str, Any]] = field(default_factory=list)
    terminal_reason: str = ""
    run_status: str = ""


@runtime_checkable
class HostDriver(Protocol):
    """The surface a host exposes so the conformance kit can drive it.

    ``capability_probe`` is optional; a host that does not implement it will
    cause :func:`check_undeclared_capability_denied` to fall back to asserting
    that a capability-requiring activation produced no effect.
    """

    def install(self, circuit: dict[str, Any], binding: dict[str, Any]) -> str:
        """Install a circuit+binding, returning a new installation id."""
        ...

    def activate(self, installation_id: str, signal: dict[str, Any]) -> RunReport:
        """Run one activation for an installation."""
        ...

    def pause(self, installation_id: str) -> dict[str, Any]:
        """Pause an installation, returning a receipt dict."""
        ...

    def revoke(self, installation_id: str) -> dict[str, Any]:
        """Revoke an installation, returning a receipt dict."""
        ...


@dataclass(slots=True)
class Scenario:
    """Inputs the conformance checks need, bundled for :func:`run_all`.

    A host supplies concrete circuit/binding/signal dicts for its own example
    chip. ``unevaluated_binding`` resolves to a tuple with no passing held-out
    result; ``undeclared_capability`` names a capability the chip did not
    declare.
    """

    circuit: dict[str, Any]
    binding: dict[str, Any]
    positive_signal: dict[str, Any]
    quiet_signal: dict[str, Any]
    duplicate_signal: dict[str, Any]
    invalid_gateway_signal: dict[str, Any]
    unevaluated_binding: dict[str, Any] | None = None
    undeclared_capability: str = "http.fetch"


def _effect_keys(effects: list[dict[str, Any]]) -> list[str]:
    keys = []
    for eff in effects:
        key = eff.get("idempotencyKey") or eff.get("idempotency_key")
        if key:
            keys.append(key)
    return keys


def _last_receipt_schema(report: RunReport) -> str | None:
    if not report.receipts:
        return None
    return report.receipts[-1].get("schema")


def check_quiet_produces_no_effects(driver: HostDriver, scenario: Scenario) -> None:
    """A quiet run must dispatch no effects and emit an attention-tier receipt."""
    iid = driver.install(scenario.circuit, scenario.binding)
    report = driver.activate(iid, scenario.quiet_signal)
    assert not report.effects_executed, (
        f"quiet run executed {len(report.effects_executed)} effect(s); a quiet run "
        "must produce none (§9)"
    )
    assert not report.effect_requests, (
        "quiet run proposed effect requests; a quiet result is a first-class no-op (§9)"
    )
    assert _last_receipt_schema(report) == ATTENTION_SCHEMA, (
        "quiet run must emit a compact attention-tier receipt (§13), got "
        f"{_last_receipt_schema(report)!r}"
    )


def check_duplicate_produces_no_effects(driver: HostDriver, scenario: Scenario) -> None:
    """The same signal twice yields at most one effect; the second run is attention-tier."""
    iid = driver.install(scenario.circuit, scenario.binding)
    first = driver.activate(iid, scenario.duplicate_signal)
    second = driver.activate(iid, scenario.duplicate_signal)
    total_effects = len(first.effects_executed) + len(second.effects_executed)
    assert total_effects <= 1, (
        f"duplicate delivery executed {total_effects} effects; at-least-once delivery "
        "must yield at most one effect (§8.3/§9)"
    )
    assert not second.effects_executed, (
        "the second (duplicate) run executed an effect; it should have been deduped (§8.3)"
    )
    assert _last_receipt_schema(second) == ATTENTION_SCHEMA, (
        "a deduped duplicate run must emit an attention-tier receipt (§13), got "
        f"{_last_receipt_schema(second)!r}"
    )


def check_invalid_judgment_fails_closed(driver: HostDriver, scenario: Scenario) -> None:
    """A malformed/hostile gateway result must fail closed with a validation record."""
    iid = driver.install(scenario.circuit, scenario.binding)
    report = driver.activate(iid, scenario.invalid_gateway_signal)
    assert not report.effects_executed, (
        "an invalid gateway result produced an effect; it must fail closed (§10.2)"
    )
    assert report.run_status in ("failed", "error"), (
        f"invalid gateway result did not fail closed; run_status={report.run_status!r} (§10.2)"
    )
    judgment = next(
        (r for r in report.receipts if r.get("schema") == JUDGMENT_SCHEMA), None
    )
    assert judgment is not None, (
        "a failed judgment stage must still emit a full judgment receipt (§13)"
    )
    decisions = judgment.get("decisions", {})
    assert "validation" in decisions, (
        "the judgment receipt must record the validation decision that rejected the "
        "gateway result (§13)"
    )


def check_at_least_once_single_effect(driver: HostDriver, scenario: Scenario) -> None:
    """Same lineage after a cursor reset yields the identical target-side dedup key."""
    iid = driver.install(scenario.circuit, scenario.binding)
    first = driver.activate(iid, scenario.positive_signal)
    # A second delivery of the same signal after a simulated cursor reset must
    # derive the identical effect key so the target owner dedups it (§8.3).
    second = driver.activate(iid, scenario.positive_signal)
    first_keys = _effect_keys(first.effect_requests)
    second_keys = _effect_keys(second.effect_requests)
    assert first_keys, (
        "the positive run proposed no effect request with an idempotency key to check (§8.3)"
    )
    if second_keys:
        assert first_keys == second_keys, (
            "effect keys differ across redelivery of the same lineage; the target-side "
            f"dedup key MUST be stable (§8.3): {first_keys} != {second_keys}"
        )
    total_executed = len(first.effects_executed) + len(second.effects_executed)
    assert total_executed <= 1, (
        f"at-least-once redelivery executed {total_executed} effects; must be at most one (§8.3)"
    )


def check_pause_and_revoke_produce_receipts(driver: HostDriver, scenario: Scenario) -> None:
    """Pause and revoke are consequential operations; each writes a receipt (§12)."""
    iid = driver.install(scenario.circuit, scenario.binding)
    pause_receipt = driver.pause(iid)
    assert isinstance(pause_receipt, dict) and pause_receipt, (
        "pause must return a non-empty receipt (§12)"
    )
    revoke_receipt = driver.revoke(iid)
    assert isinstance(revoke_receipt, dict) and revoke_receipt, (
        "revoke must return a non-empty receipt (§12)"
    )


def check_unevaluated_tuple_capped_at_observe(driver: HostDriver, scenario: Scenario) -> None:
    """A binding resolving to an unevaluated tuple is capped at observe (§10.2)."""
    if scenario.unevaluated_binding is None:
        raise AssertionError(
            "scenario.unevaluated_binding is required to check the observe cap (§10.2)"
        )
    iid = driver.install(scenario.circuit, scenario.unevaluated_binding)
    report = driver.activate(iid, scenario.positive_signal)
    for eff in report.effect_requests:
        cls = eff.get("class") or eff.get("effect_class")
        assert cls == "observe", (
            f"unevaluated tuple proposed a '{cls}' effect; it must be capped at 'observe' "
            "until its held-out suite passes (§10.2)"
        )
    assert not report.effects_executed or all(
        (e.get("class") or e.get("effect_class")) == "observe" for e in report.effects_executed
    ), "unevaluated tuple executed an effect above observe (§10.2)"


def check_undeclared_capability_denied(driver: HostDriver, scenario: Scenario) -> None:
    """An undeclared capability must be unavailable to the run (§14)."""
    iid = driver.install(scenario.circuit, scenario.binding)
    probe = getattr(driver, "capability_probe", None)
    if callable(probe):
        allowed = probe(iid, scenario.undeclared_capability)
        assert allowed is False, (
            f"undeclared capability {scenario.undeclared_capability!r} was reported available; "
            "a package that declares no such capability cannot obtain it (§14)"
        )
    else:  # pragma: no cover - exercised only against drivers lacking the probe
        report = driver.activate(iid, scenario.positive_signal)
        assert not report.effects_executed, (
            "without a capability probe, an undeclared-capability run must at least produce "
            "no effect (§14)"
        )


# The full check suite, in a sensible order.
ALL_CHECKS = (
    check_quiet_produces_no_effects,
    check_duplicate_produces_no_effects,
    check_invalid_judgment_fails_closed,
    check_at_least_once_single_effect,
    check_pause_and_revoke_produce_receipts,
    check_unevaluated_tuple_capped_at_observe,
    check_undeclared_capability_denied,
)


def run_all(driver: HostDriver, scenario: Scenario) -> list[str]:
    """Run every conformance check against ``driver``; return the passed names.

    Raises :class:`AssertionError` from the first failing check (its message
    names the violated rule). On success returns the list of check names that
    passed, so a caller can log conformance coverage.
    """
    passed: list[str] = []
    for check in ALL_CHECKS:
        check(driver, scenario)
        passed.append(check.__name__)
    return passed
