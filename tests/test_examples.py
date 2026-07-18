"""End-to-end validation of the publication-triage pilot example packages.

Exercises the two shipped example chips (``examples/publication-attention`` and
``examples/bounded-recommendation``) and their circuit against the contract
library the way a real host does: manifest + schema loading, fixture coverage,
circuit composition, and a run of each implementation over every fixture using
an envelope-shaped activation and an at-most-once gateway that taints its result
on hostile input (§8.2), exactly as the reference host (Fab) does.

``test_examples_load_and_run_exactly_like_a_host`` is the regression guard: it
imports each entrypoint the way a host resolves it (dotted module relative to the
package root), builds an envelope-shaped activation, runs the full two-chip
circuit, and asserts ``chip.Response.from_dict`` accepts every response and
``chip.EffectRequest.from_dict`` accepts every effect — the check that would have
caught the entrypoint, ``producedBy``, and signal-envelope mismatches at once.
See chip.spec/v0alpha1 §7.1, §8, §20.1-22 and docs/host-execution-contract.md.
"""

from __future__ import annotations

import importlib.util
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

import chip
from chip.authority import EffectClass
from chip.circuit import Circuit, validate_circuit
from chip.envelopes import derive_effect_key
from chip.errors import EnvelopeError
from chip.fixtures import validate_fixture_coverage
from chip.manifest import load_chip_package
from chip.payloads import jsonschema_available, validate_payload
from chip.tainting import (
    assert_untainted_for_instructions,
    is_tainted,
    taint_gateway_result,
)
from chip.tainting import (
    taint as taint_value,
)

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
PUB = EXAMPLES / "publication-attention"
BREC = EXAMPLES / "bounded-recommendation"
CIRCUIT_DOC = EXAMPLES / "circuits" / "publication-triage.json"

ERROR_CLASSES = {"EnvelopeError": EnvelopeError}


# ---------------------------------------------------------------------------
# Host-faithful entrypoint loading + activation building
# ---------------------------------------------------------------------------


def _load_entrypoint(package_dir: Path, entrypoint: str) -> Callable[[dict], dict]:
    """Import ``entrypoint`` the way a host does (mirror of fab ``_load_run_callable``).

    The entrypoint is a dotted module path relative to the package root plus a
    callable; dots become directory separators, so ``impl.chip_impl:run`` resolves
    to ``<package>/impl/chip_impl.py`` and its ``run`` attribute.
    """
    module_ref, _, attr = entrypoint.partition(":")
    assert attr, f"entrypoint {entrypoint!r} must be '<module>:<callable>'"
    file = package_dir / (module_ref.replace(".", "/") + ".py")
    assert file.is_file(), f"entrypoint module not found: {file}"
    unique = f"chip_ex_{package_dir.name.replace('-', '_')}"
    spec = importlib.util.spec_from_file_location(unique, file)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    fn = getattr(module, attr, None)
    assert callable(fn), f"entrypoint {entrypoint!r} is not callable"
    return fn


PUB_MANIFEST, PUB_SCHEMAS = load_chip_package(PUB)
BREC_MANIFEST, BREC_SCHEMAS = load_chip_package(BREC)
PUB_RUN = _load_entrypoint(PUB, PUB_MANIFEST.implementation.entrypoint)
BREC_RUN = _load_entrypoint(BREC, BREC_MANIFEST.implementation.entrypoint)

IMPLS = {"publication-attention": PUB_RUN, "bounded-recommendation": BREC_RUN}
MANIFESTS = {"publication-attention": PUB_MANIFEST, "bounded-recommendation": BREC_MANIFEST}
PACKAGES = {"publication-attention": PUB, "bounded-recommendation": BREC}

BINDING_TARGET = "owner://research-ideas"


def _first_taint(obj: Any) -> dict[str, Any] | None:
    """Return a taint marker reachable in ``obj`` (a {value,taint} leaf or a
    quoted_span), or ``None`` — the parent taint a gateway result inherits."""
    if is_tainted(obj):
        return obj["taint"]
    if isinstance(obj, dict):
        if obj.get("kind") == "quoted_span" and isinstance(obj.get("taint"), dict):
            return obj["taint"]
        for value in obj.values():
            marker = _first_taint(value)
            if marker is not None:
                return marker
    elif isinstance(obj, list):
        for item in obj:
            marker = _first_taint(item)
            if marker is not None:
                return marker
    return None


class HostLikeGateway:
    """At-most-once gateway that taints its canned result on hostile input.

    Mirrors the reference host's gateway seam: it is callable at most once, and
    when the request carried tainted content it taints the result's string leaves
    before returning it (§8.2 transitivity, ``chip.taint_gateway_result``) — so the
    implementation must ``_untaint`` model-derived scalars, exactly as on the host.
    """

    def __init__(self, canned: dict | None) -> None:
        self._canned = canned
        self.calls = 0
        self.last_request: dict | None = None

    def __call__(self, request: dict) -> dict:
        self.calls += 1
        self.last_request = request
        if self.calls > 1:
            raise RuntimeError("gateway invoked more than once per activation")
        if self._canned is None:
            raise AssertionError("gateway invoked but fixture declares no canned result")
        result = json.loads(json.dumps(self._canned))
        parent = _first_taint(request)
        if parent is not None:
            result = taint_gateway_result(result, parent)
        return result


def _host_signal(raw_input: dict) -> dict:
    """Build the chip-facing activation signal exactly as the host does (§8.1):
    validate the envelope, then taint-mark the carried ``content`` payload."""
    sig = chip.Signal.from_dict(raw_input)
    activation_signal = sig.to_dict()
    if "content" in raw_input:
        activation_signal["content"] = taint_value(
            raw_input["content"], sig.trust.value, sig.source, via=[sig.id]
        )
    return activation_signal


def _host_config(manifest: Any, raw: dict) -> dict:
    """Build the binding-resolved config block the host injects into the activation."""
    alias = manifest.metadata.alias
    declared = manifest.contract.effects
    effect_target = raw.get("config", {}).get("effect_target", "")
    if declared and not effect_target:
        effect_target = BINDING_TARGET
    return {
        **raw.get("config", {}),
        "chipAlias": alias,
        "promise_id": raw.get("config", {}).get("promise_id") or (manifest.metadata.id or alias),
        "effect_target": effect_target,
        "effectDestinations": {e.name: effect_target for e in declared},
    }


def _activation(manifest: Any, raw: dict, gateway: Any) -> dict:
    return {
        "run_id": f"run-test-{raw.get('kind', 'x')}",
        "signal": _host_signal(raw["input"]),
        "state": raw.get("priorState"),
        "config": _host_config(manifest, raw),
        "gateway": gateway,
        "upstream": raw.get("upstream"),
    }


def _fixture_paths(package: Path) -> list[Path]:
    return sorted(package.glob("fixtures/*/fixture.json"))


def _all_fixtures() -> list[tuple[str, Path]]:
    out: list[tuple[str, Path]] = []
    for name, pkg in PACKAGES.items():
        out.extend((name, p) for p in _fixture_paths(pkg))
    return out


# ---------------------------------------------------------------------------
# Package + schema loading, fixture coverage, circuit composition, entrypoint
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("pkg", list(PACKAGES.values()), ids=list(PACKAGES))
def test_package_loads_and_schemas_resolve(pkg: Path) -> None:
    manifest, schemas = load_chip_package(pkg)
    assert schemas
    for ref in manifest.schema_refs():
        assert ref in schemas
        assert schemas[ref].is_file()


@pytest.mark.parametrize("pkg", list(PACKAGES.values()), ids=list(PACKAGES))
def test_fixture_coverage(pkg: Path) -> None:
    fixtures = validate_fixture_coverage(pkg)
    kinds = {f.kind for f in fixtures}
    assert {"positive", "quiet", "failure", "adversarial"} <= kinds


@pytest.mark.parametrize("name", list(PACKAGES), ids=list(PACKAGES))
def test_entrypoint_is_dotted_module_under_impl(name: str) -> None:
    """The manifest entrypoint is the dotted module path a host resolves relative
    to the package root, and the module ships under ``impl/`` (§7.1)."""
    manifest = MANIFESTS[name]
    entrypoint = manifest.implementation.entrypoint
    assert entrypoint == "impl.chip_impl:run"
    module_ref = entrypoint.partition(":")[0]
    resolved = PACKAGES[name] / (module_ref.replace(".", "/") + ".py")
    assert resolved == PACKAGES[name] / "impl" / "chip_impl.py"
    assert resolved.is_file()


def test_expected_implementation_classes() -> None:
    assert PUB_MANIFEST.implementation_class == "hybrid"
    assert BREC_MANIFEST.implementation_class == "deterministic"
    # publication-attention declares NO effects.
    assert PUB_MANIFEST.contract.effects == ()


def test_circuit_validates_with_recommend_ceiling() -> None:
    circuit = Circuit.from_dict(json.loads(CIRCUIT_DOC.read_text(encoding="utf-8")))
    manifests = {"attention": PUB_MANIFEST, "recommend": BREC_MANIFEST}
    auth = validate_circuit(circuit, manifests)
    assert auth.circuit_ceiling is EffectClass.SYNTHESIZE
    assert auth.circuit_ceiling.label == "synthesize"
    # publication-attention is an observe-only no-effect sensing chip; its low
    # ceiling does NOT cap the downstream recommend chip (per-chip authority, §12).
    assert auth.per_chip["attention"] is EffectClass.OBSERVE
    assert auth.per_chip["recommend"] is EffectClass.SYNTHESIZE


# ---------------------------------------------------------------------------
# Every fixture runs over a host-shaped activation with the declared outcome
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("pkg,fx", _all_fixtures(), ids=lambda v: v if isinstance(v, str) else v.parent.name)
def test_fixture_runs_to_expected_outcome(pkg: str, fx: Path) -> None:
    raw = json.loads(fx.read_text(encoding="utf-8"))
    run = IMPLS[pkg]
    manifest = MANIFESTS[pkg]
    expected = raw["expected"]
    gw = HostLikeGateway(raw.get("cannedGatewayResult"))
    activation = _activation(manifest, raw, gw)

    if expected.get("errorClass"):
        with pytest.raises(ERROR_CLASSES[expected["errorClass"]]):
            run(activation)
        if expected.get("noGatewayCall"):
            assert gw.calls == 0
        return

    result = run(activation)
    response, effects = result["response"], result["effects"]
    # The host would accept this response envelope structurally.
    parsed = chip.Response.from_dict(response)
    assert parsed.kind.value == expected["responseKind"]
    if "reason" in expected:
        assert response["body"].get("reason") == expected["reason"]

    # Every effect is a well-formed §8.3 effect request.
    for eff in effects:
        chip.EffectRequest.from_dict(eff)
    if "effectCount" in expected:
        assert len(effects) == expected["effectCount"]
    if expected.get("noEffect"):
        assert effects == []

    # Gateway-call accounting: quiet/duplicate must not call the gateway.
    if expected.get("noGatewayCall"):
        assert gw.calls == 0
    elif raw.get("cannedGatewayResult") is not None:
        assert gw.calls == 1

    # State is a full replacement dict.
    assert isinstance(result["state"], dict)


# ---------------------------------------------------------------------------
# Taint end-to-end: no instruction-position leakage; spans stay tainted
# ---------------------------------------------------------------------------


def test_adversarial_taint_preserved_and_no_instruction_leak() -> None:
    raw = json.loads((PUB / "fixtures" / "adversarial" / "fixture.json").read_text(encoding="utf-8"))
    gw = HostLikeGateway(raw["cannedGatewayResult"])
    result = PUB_RUN(_activation(PUB_MANIFEST, raw, gw))

    # The gateway request: instruction is clean prose, body is a quoted span.
    request = gw.last_request
    assert request is not None
    assert_untainted_for_instructions(request["instruction"])
    assert "ignore prior instructions" not in request["instruction"]
    # The whole request DOES contain tainted material (structurally separate).
    with pytest.raises(EnvelopeError):
        assert_untainted_for_instructions(request)
    with pytest.raises(EnvelopeError):
        assert_untainted_for_instructions(request["evidence"])
    # The hostile body text lives only inside the structurally-separate span.
    assert "ignore prior instructions" in request["evidence"]["body"]["quoted_text"]

    # Response finding: assessment prose stays clean (the model rationale is not
    # the injection), and every evidence span is still tainted hostile.
    response = result["response"]
    assert response["kind"] == "finding"
    # The host taints model output on hostile input, so the rationale comes back
    # as a {value, taint} marker whose inner text is the clean model rationale.
    rationale = response["body"]["assessment"]["rationale"]
    rationale_text = rationale["value"] if is_tainted(rationale) else rationale
    assert "ignore prior instructions" not in rationale_text
    for item in response["evidence"]:
        assert is_tainted(item["quoted_span"])
        assert item["quoted_span"]["taint"]["trust"] == "hostile"
        assert "assess" in item["quoted_span"]["taint"]["via"]
    # The derived evidence, taken as instruction, is rejected.
    with pytest.raises(EnvelopeError):
        assert_untainted_for_instructions(response["evidence"])
    # Zero effects: publication-attention requests none.
    assert result["effects"] == []


def test_bounded_recommendation_refuses_to_launder() -> None:
    raw = json.loads((BREC / "fixtures" / "adversarial" / "fixture.json").read_text(encoding="utf-8"))
    result = BREC_RUN(_activation(BREC_MANIFEST, raw, HostLikeGateway(None)))
    # Evidence whose taint marker was stripped -> abstain, no effect.
    assert result["response"]["kind"] == "abstain"
    assert result["effects"] == []


# ---------------------------------------------------------------------------
# Effect-key stability across repeated runs and a state reset
# ---------------------------------------------------------------------------


def test_effect_key_stable_across_runs_and_state_reset() -> None:
    raw = json.loads((BREC / "fixtures" / "positive" / "fixture.json").read_text(encoding="utf-8"))
    config = _host_config(BREC_MANIFEST, raw)
    signal = _host_signal(raw["input"])  # finding delivered inline in signal.content

    def issue(state: dict | None) -> str:
        result = BREC_RUN({
            "run_id": "run-key-test", "signal": signal, "upstream": None,
            "state": state, "config": config, "gateway": HostLikeGateway(None),
        })
        assert result["response"]["kind"] == "finding"
        assert len(result["effects"]) == 1
        effect = result["effects"][0]
        # The implementation's claimed key equals the response body key.
        assert effect["idempotencyKey"] == result["response"]["body"]["effectKey"]
        return effect["idempotencyKey"]

    key_first = issue({"issued": []})
    key_repeat = issue({"issued": []})
    key_after_reset = issue(None)  # simulated state reset (no prior state)
    assert key_first == key_repeat == key_after_reset

    # And it matches an independent host-side recomputation from the SIGNAL's
    # lineage key (the host recomputes and checks this, §8.3).
    expected = derive_effect_key(
        signal["lineageKey"], "recommend-research", config["effect_target"], config["promise_id"]
    )
    assert key_first == expected

    # Once issued, redelivery is quiet with no effect (at-least-once -> at most one).
    quiet = BREC_RUN({
        "run_id": "run-key-test", "signal": signal, "upstream": None,
        "state": {"issued": [signal["lineageKey"]]}, "config": config,
        "gateway": HostLikeGateway(None),
    })
    assert quiet["response"]["kind"] == "quiet"
    assert quiet["effects"] == []


def test_content_dedup_and_cursor_are_quiet() -> None:
    """Publication-attention dedupes by content digest and advances a cursor — a
    state-dependent path the host also guards at the envelope level (dedupeKey)."""
    raw = json.loads((PUB / "fixtures" / "positive" / "fixture.json").read_text(encoding="utf-8"))
    signal = _host_signal(raw["input"])
    config = _host_config(PUB_MANIFEST, raw)
    digest = signal["digest"]

    # Same content digest already in `seen` -> quiet duplicate-content, no gateway.
    gw = HostLikeGateway(raw["cannedGatewayResult"])
    dup = PUB_RUN({
        "run_id": "run-dedup", "signal": signal, "upstream": None,
        "state": {"cursor": None, "seen": [digest]}, "config": config, "gateway": gw,
    })
    assert dup["response"]["kind"] == "quiet"
    assert dup["response"]["body"]["reason"] == "duplicate-content"
    assert gw.calls == 0

    # A cursor at/after the signal's published_at -> quiet not-after-cursor.
    gw2 = HostLikeGateway(raw["cannedGatewayResult"])
    stale = PUB_RUN({
        "run_id": "run-cursor", "signal": signal, "upstream": None,
        "state": {"cursor": {"value": "2099-01-01T00:00:00Z", "lineage": digest}, "seen": []},
        "config": config, "gateway": gw2,
    })
    assert stale["response"]["kind"] == "quiet"
    assert stale["response"]["body"]["reason"] == "not-after-cursor"
    assert gw2.calls == 0


def test_malformed_gateway_result_fails_closed() -> None:
    raw = json.loads((PUB / "fixtures" / "failure-bad-result" / "fixture.json").read_text(encoding="utf-8"))
    gw = HostLikeGateway(raw["cannedGatewayResult"])
    with pytest.raises(EnvelopeError):
        PUB_RUN(_activation(PUB_MANIFEST, raw, gw))
    # The gateway WAS consulted (once); the failure is in result validation.
    assert gw.calls == 1


# ---------------------------------------------------------------------------
# The regression guard: load + run EXACTLY the way a host does, end to end
# ---------------------------------------------------------------------------


def test_examples_load_and_run_exactly_like_a_host() -> None:
    """Import each entrypoint the host way, run the full two-chip circuit over an
    envelope-shaped activation, and assert the library accepts every envelope.

    This is the check that would have caught all three published mismatches:
    the dotted entrypoint (module under ``impl/``), the top-level
    ``producedByChip``/``producedByRun`` coordinates, and consumption of the §8.1
    signal envelope (``lineageKey``/``digest``/taint-marked ``content``).
    """
    pub_run = _load_entrypoint(PUB, PUB_MANIFEST.implementation.entrypoint)
    brec_run = _load_entrypoint(BREC, BREC_MANIFEST.implementation.entrypoint)

    pub_raw = json.loads((PUB / "fixtures" / "positive" / "fixture.json").read_text(encoding="utf-8"))
    brec_raw = json.loads((BREC / "fixtures" / "positive" / "fixture.json").read_text(encoding="utf-8"))

    # (1) Run the attention chip over the host-built activation signal.
    signal = _host_signal(pub_raw["input"])
    pub_gw = HostLikeGateway(pub_raw["cannedGatewayResult"])
    pub_result = pub_run({
        "run_id": "run-host-1", "signal": signal, "state": pub_raw.get("priorState"),
        "config": _host_config(PUB_MANIFEST, pub_raw), "gateway": pub_gw, "upstream": None,
    })
    pub_response = chip.Response.from_dict(pub_result["response"])  # host-accepted
    assert pub_response.kind is chip.ResponseKind.FINDING
    assert pub_result["effects"] == []

    # (2) The host hands the prior response to the next chip as `upstream`
    #     (mirror of the runner: kind + body + producedByChip + evidence).
    upstream = {
        "kind": pub_response.kind.value,
        "body": pub_response.body,
        "producedByChip": pub_response.produced_by_chip,
        "evidence": pub_response.evidence,
    }
    brec_config = _host_config(BREC_MANIFEST, brec_raw)
    brec_result = brec_run({
        "run_id": "run-host-1", "signal": signal, "state": brec_raw.get("priorState"),
        "config": brec_config, "gateway": HostLikeGateway(None), "upstream": upstream,
    })

    # (3) The library accepts the response and every effect request.
    brec_response = chip.Response.from_dict(brec_result["response"])
    assert brec_response.kind is chip.ResponseKind.FINDING
    assert len(brec_result["effects"]) == 1
    for eff in brec_result["effects"]:
        parsed = chip.EffectRequest.from_dict(eff)
        # (4) The effect key matches the host's independent recomputation from the
        #     SIGNAL lineage key, and its targetOwner matches the binding (§8.3).
        assert parsed.target_owner == brec_config["effect_target"]
        assert parsed.idempotency_key == derive_effect_key(
            signal["lineageKey"], parsed.type, brec_config["effect_target"], brec_config["promise_id"]
        )
        assert parsed.judgment_receipt_ref == chip.PENDING_RECEIPT_REF


# ---------------------------------------------------------------------------
# Shipped payloads validate against their shipped JSON Schemas
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not jsonschema_available(), reason="jsonschema extra not installed")
def test_shipped_payloads_validate_against_schemas() -> None:
    # The host validates `response.body` against the output PORT schema; validate
    # the finding/quiet bodies the impls actually produce.
    finding_body_schema = json.loads(
        PUB_SCHEMAS["schemas/materiality-finding.json@1"].read_text(encoding="utf-8")
    )
    result_schema = json.loads(
        PUB_SCHEMAS["schemas/assessment-result.json@1"].read_text(encoding="utf-8")
    )

    raw = json.loads((PUB / "fixtures" / "positive" / "fixture.json").read_text(encoding="utf-8"))
    validate_payload(raw["cannedGatewayResult"], result_schema)
    result = PUB_RUN(_activation(PUB_MANIFEST, raw, HostLikeGateway(raw["cannedGatewayResult"])))
    validate_payload(result["response"]["body"], finding_body_schema)

    # Bounded recommendation: validate its effect payload + issued body.
    rec_schema = json.loads(
        BREC_SCHEMAS["schemas/research-recommendation.json@1"].read_text(encoding="utf-8")
    )
    issued_body_schema = json.loads(
        BREC_SCHEMAS["schemas/recommendation-issued.json@1"].read_text(encoding="utf-8")
    )
    braw = json.loads((BREC / "fixtures" / "positive" / "fixture.json").read_text(encoding="utf-8"))
    bresult = BREC_RUN(_activation(BREC_MANIFEST, braw, HostLikeGateway(None)))
    validate_payload(bresult["effects"][0]["payload"], rec_schema)
    validate_payload(bresult["response"]["body"], issued_body_schema)
