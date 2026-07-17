"""End-to-end validation of the publication-triage pilot example packages.

Exercises the two shipped example chips (``examples/publication-attention`` and
``examples/bounded-recommendation``) and their circuit against the contract
library: manifest + schema loading, fixture coverage, circuit composition, and a
direct pure-function run of each implementation over every fixture using a fake
at-most-once gateway. See chip.spec/v0alpha1 20.1-22.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest

from chip.authority import EffectClass
from chip.circuit import Circuit, validate_circuit
from chip.envelopes import derive_effect_key
from chip.errors import EnvelopeError
from chip.fixtures import validate_fixture_coverage
from chip.manifest import load_chip_package
from chip.payloads import jsonschema_available, validate_payload
from chip.taint import assert_untainted_for_instructions, is_tainted

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
PUB = EXAMPLES / "publication-attention"
BREC = EXAMPLES / "bounded-recommendation"
CIRCUIT_DOC = EXAMPLES / "circuits" / "publication-triage.json"

ERROR_CLASSES = {"EnvelopeError": EnvelopeError}


def _load_impl(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PUB_RUN = _load_impl("pub_chip_impl", PUB / "impl" / "chip_impl.py").run
BREC_RUN = _load_impl("brec_chip_impl", BREC / "impl" / "chip_impl.py").run
IMPLS = {"publication-attention": PUB_RUN, "bounded-recommendation": BREC_RUN}
PACKAGES = {"publication-attention": PUB, "bounded-recommendation": BREC}


class FakeGateway:
    """A host-owned, at-most-once gateway that returns a fixture's canned result."""

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
        return self._canned


def _fixture_paths(package: Path) -> list[Path]:
    return sorted(package.glob("fixtures/*/fixture.json"))


def _all_fixtures() -> list[tuple[str, Path]]:
    out: list[tuple[str, Path]] = []
    for name, pkg in PACKAGES.items():
        out.extend((name, p) for p in _fixture_paths(pkg))
    return out


# ---------------------------------------------------------------------------
# Package + schema loading, fixture coverage, circuit composition
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("pkg", list(PACKAGES.values()), ids=list(PACKAGES))
def test_package_loads_and_schemas_resolve(pkg: Path) -> None:
    manifest, schemas = load_chip_package(pkg)
    # Every declared schema reference resolves to a shipped file.
    assert schemas
    for ref in manifest.schema_refs():
        assert ref in schemas
        assert schemas[ref].is_file()


@pytest.mark.parametrize("pkg", list(PACKAGES.values()), ids=list(PACKAGES))
def test_fixture_coverage(pkg: Path) -> None:
    fixtures = validate_fixture_coverage(pkg)
    kinds = {f.kind for f in fixtures}
    assert {"positive", "quiet", "failure", "adversarial"} <= kinds


def test_expected_implementation_classes() -> None:
    pub_manifest, _ = load_chip_package(PUB)
    brec_manifest, _ = load_chip_package(BREC)
    assert pub_manifest.implementation_class == "hybrid"
    assert brec_manifest.implementation_class == "deterministic"
    # publication-attention declares NO effects.
    assert pub_manifest.contract.effects == ()


def test_circuit_validates_with_recommend_ceiling() -> None:
    pub_manifest, _ = load_chip_package(PUB)
    brec_manifest, _ = load_chip_package(BREC)
    circuit = Circuit.from_dict(json.loads(CIRCUIT_DOC.read_text(encoding="utf-8")))
    manifests = {"attention": pub_manifest, "recommend": brec_manifest}
    auth = validate_circuit(circuit, manifests)
    # Circuit ceiling is the recommend/synthesize rung.
    assert auth.circuit_ceiling is EffectClass.SYNTHESIZE
    assert auth.circuit_ceiling.label == "synthesize"
    # publication-attention is an observe-only no-effect sensing chip; its low
    # ceiling does NOT cap the downstream recommend chip (per-chip authority, §12).
    assert auth.per_chip["attention"] is EffectClass.OBSERVE
    assert auth.per_chip["recommend"] is EffectClass.SYNTHESIZE


# ---------------------------------------------------------------------------
# Every fixture runs as a pure function with the declared outcome
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("pkg,fx", _all_fixtures(), ids=lambda v: v if isinstance(v, str) else v.parent.name)
def test_fixture_runs_to_expected_outcome(pkg: str, fx: Path) -> None:
    raw = json.loads(fx.read_text(encoding="utf-8"))
    run = IMPLS[pkg]
    expected = raw["expected"]
    gw = FakeGateway(raw.get("cannedGatewayResult"))
    activation = {
        "signal": raw["input"],
        "state": raw.get("priorState"),
        "config": raw.get("config", {}),
        "gateway": gw,
    }

    if expected.get("errorClass"):
        with pytest.raises(ERROR_CLASSES[expected["errorClass"]]):
            run(activation)
        if expected.get("noGatewayCall"):
            assert gw.calls == 0
        return

    result = run(activation)
    response, effects = result["response"], result["effects"]
    assert response["kind"] == expected["responseKind"]
    if "reason" in expected:
        assert response.get("reason") == expected["reason"]

    # Effect accounting.
    if "effectCount" in expected:
        assert len(effects) == expected["effectCount"]
    if expected.get("noEffect"):
        assert effects == []

    # Gateway-call accounting: quiet/duplicate must not call the gateway.
    if expected.get("noGatewayCall"):
        assert gw.calls == 0
    elif raw.get("cannedGatewayResult") is not None:
        assert gw.calls == 1

    # State schema round-trips (returned state is a full replacement).
    assert isinstance(result["state"], dict)


# ---------------------------------------------------------------------------
# Taint end-to-end: no instruction-position leakage; spans stay tainted
# ---------------------------------------------------------------------------


def test_adversarial_taint_preserved_and_no_instruction_leak() -> None:
    raw = json.loads((PUB / "fixtures" / "adversarial" / "fixture.json").read_text(encoding="utf-8"))
    gw = FakeGateway(raw["cannedGatewayResult"])
    result = PUB_RUN({
        "signal": raw["input"],
        "state": raw.get("priorState"),
        "config": raw.get("config", {}),
        "gateway": gw,
    })

    # The gateway request: instruction is clean prose, body is a quoted span.
    request = gw.last_request
    assert request is not None
    # Instruction position carries no tainted content and no injection text.
    assert_untainted_for_instructions(request["instruction"])
    assert "ignore prior instructions" not in request["instruction"]
    # The whole request DOES contain tainted material (structurally separate),
    # so the guard flags it -- proving the body is not in instruction position.
    with pytest.raises(EnvelopeError):
        assert_untainted_for_instructions(request)
    with pytest.raises(EnvelopeError):
        assert_untainted_for_instructions(request["evidence"])
    # The hostile body text lives only inside the structurally-separate span.
    assert "ignore prior instructions" in request["evidence"]["body"]["quoted_text"]

    # Response finding: every evidence span is still tainted hostile, and the
    # echoed injection never lands in the chip-authored assessment prose.
    response = result["response"]
    assert response["kind"] == "finding"
    assert "ignore prior instructions" not in response["assessment"]["rationale"]
    assert_untainted_for_instructions(response["assessment"])  # clean claim
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
    result = BREC_RUN({
        "signal": raw["input"],
        "state": raw.get("priorState"),
        "config": raw.get("config", {}),
        "gateway": FakeGateway(None),
    })
    # Evidence whose taint marker was stripped -> abstain, no effect.
    assert result["response"]["kind"] == "abstain"
    assert result["effects"] == []


# ---------------------------------------------------------------------------
# Effect-key stability across repeated runs and a state reset
# ---------------------------------------------------------------------------


def test_effect_key_stable_across_runs_and_state_reset() -> None:
    raw = json.loads((BREC / "fixtures" / "positive" / "fixture.json").read_text(encoding="utf-8"))
    config = raw["config"]
    signal = raw["input"]

    def issue(state: dict | None) -> str:
        result = BREC_RUN({
            "signal": signal,
            "state": state,
            "config": config,
            "gateway": FakeGateway(None),
        })
        assert result["response"]["kind"] == "finding"
        assert len(result["effects"]) == 1
        effect = result["effects"][0]
        # The implementation's claimed key equals the response key.
        assert effect["idempotencyKey"] == result["response"]["effectKey"]
        return effect["idempotencyKey"]

    key_first = issue({"issued": []})
    key_repeat = issue({"issued": []})
    key_after_reset = issue(None)  # simulated state reset (no prior state)

    assert key_first == key_repeat == key_after_reset

    # And it matches an independent host-side recomputation (host re-derives it).
    content_digest = signal["lineage"]["content_digest"]
    expected = derive_effect_key(
        content_digest, "recommend-research", config["targetOwner"], config["promiseId"]
    )
    assert key_first == expected

    # Once issued, redelivery is quiet with no effect (at-least-once -> at most one).
    quiet = BREC_RUN({
        "signal": signal,
        "state": {"issued": [content_digest]},
        "config": config,
        "gateway": FakeGateway(None),
    })
    assert quiet["response"]["kind"] == "quiet"
    assert quiet["effects"] == []


def test_malformed_gateway_result_fails_closed() -> None:
    raw = json.loads((PUB / "fixtures" / "failure-bad-result" / "fixture.json").read_text(encoding="utf-8"))
    gw = FakeGateway(raw["cannedGatewayResult"])
    with pytest.raises(EnvelopeError):
        PUB_RUN({
            "signal": raw["input"],
            "state": raw.get("priorState"),
            "config": raw.get("config", {}),
            "gateway": gw,
        })
    # The gateway WAS consulted (once); the failure is in result validation.
    assert gw.calls == 1


# ---------------------------------------------------------------------------
# Optional: shipped payloads validate against their shipped JSON Schemas
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not jsonschema_available(), reason="jsonschema extra not installed")
def test_shipped_payloads_validate_against_schemas() -> None:
    pub_manifest, pub_schemas = load_chip_package(PUB)
    _, brec_schemas = load_chip_package(BREC)

    finding_schema = json.loads(
        pub_schemas["schemas/materiality-finding.json@1"].read_text(encoding="utf-8")
    )
    result_schema = json.loads(
        pub_schemas["schemas/assessment-result.json@1"].read_text(encoding="utf-8")
    )

    # Run the positive publication fixture and validate the finding it produces.
    raw = json.loads((PUB / "fixtures" / "positive" / "fixture.json").read_text(encoding="utf-8"))
    validate_payload(raw["cannedGatewayResult"], result_schema)
    result = PUB_RUN({
        "signal": raw["input"],
        "state": raw.get("priorState"),
        "config": raw.get("config", {}),
        "gateway": FakeGateway(raw["cannedGatewayResult"]),
    })
    validate_payload(result["response"], finding_schema)

    # Run the positive bounded-recommendation fixture and validate its effect
    # payload + output envelope.
    rec_schema = json.loads(
        brec_schemas["schemas/research-recommendation.json@1"].read_text(encoding="utf-8")
    )
    issued_schema = json.loads(
        brec_schemas["schemas/recommendation-issued.json@1"].read_text(encoding="utf-8")
    )
    braw = json.loads((BREC / "fixtures" / "positive" / "fixture.json").read_text(encoding="utf-8"))
    bresult = BREC_RUN({
        "signal": braw["input"],
        "state": braw.get("priorState"),
        "config": braw["config"],
        "gateway": FakeGateway(None),
    })
    validate_payload(bresult["effects"][0]["payload"], rec_schema)
    validate_payload(bresult["response"], issued_schema)
