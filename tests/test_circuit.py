"""Circuit validation: linear/<=3, schema-name match, feedback + self edges."""

from __future__ import annotations

import copy

import pytest

from chip.authority import EffectClass
from chip.circuit import Circuit, validate_circuit
from chip.errors import CircuitError
from chip.manifest import load_manifest


@pytest.fixture
def manifests(publication_attention_manifest, bounded_recommendation_manifest):
    return {
        "attention": load_manifest(publication_attention_manifest),
        "recommend": load_manifest(bounded_recommendation_manifest),
    }


def test_valid_circuit(linear_circuit_dict, manifests):
    circuit = Circuit.from_dict(linear_circuit_dict)
    ceiling = validate_circuit(circuit, manifests)
    assert ceiling is EffectClass.SYNTHESIZE  # intersection of recommend ceilings


def test_four_chips_rejected(linear_circuit_dict, manifests):
    d = copy.deepcopy(linear_circuit_dict)
    for i in range(2):
        d["chips"].append(
            {
                "ref": f"extra{i}",
                "chip": "press.bounded-recommendation",
                "contractVersion": "0.1.0",
                "implementation": "sha256:bbbb",
            }
        )
    circuit = Circuit.from_dict(d)
    m = dict(manifests)
    m["extra0"] = manifests["recommend"]
    m["extra1"] = manifests["recommend"]
    with pytest.raises(CircuitError) as exc:
        validate_circuit(circuit, m)
    assert "at most" in str(exc.value)


def test_schema_name_mismatch_rejected(linear_circuit_dict, manifests, bounded_recommendation_manifest):
    # Change the downstream input schema so it no longer matches the upstream output.
    bad = copy.deepcopy(bounded_recommendation_manifest)
    bad["contract"]["inputs"][0]["schema"] = "schemas/materiality-finding.json@2"
    m = dict(manifests)
    m["recommend"] = load_manifest(bad)
    circuit = Circuit.from_dict(linear_circuit_dict)
    with pytest.raises(CircuitError) as exc:
        validate_circuit(circuit, m)
    assert "schema mismatch" in str(exc.value)


def test_feedback_edge_rejected(linear_circuit_dict, manifests):
    d = copy.deepcopy(linear_circuit_dict)
    d["connections"].append(
        {"fromChip": "recommend", "fromPort": "recommendation", "toChip": "attention", "toPort": "publication"}
    )
    circuit = Circuit.from_dict(d)
    with pytest.raises(CircuitError) as exc:
        validate_circuit(circuit, manifests)
    assert "feedback" in str(exc.value) or "backward" in str(exc.value)


def test_self_reference_rejected(linear_circuit_dict, manifests):
    d = copy.deepcopy(linear_circuit_dict)
    d["connections"].append(
        {"fromChip": "attention", "fromPort": "finding", "toChip": "attention", "toPort": "publication"}
    )
    circuit = Circuit.from_dict(d)
    with pytest.raises(CircuitError) as exc:
        validate_circuit(circuit, manifests)
    assert "self-referential" in str(exc.value)


def test_effective_ceiling_is_intersection(linear_circuit_dict, manifests, publication_attention_manifest):
    # Lower one member's ceiling to observe; the circuit effective drops to observe.
    lowered = copy.deepcopy(publication_attention_manifest)
    lowered["authority"]["maximumEffectClass"] = "observe"
    lowered["contract"]["effects"][0]["class"] = "observe"
    m = dict(manifests)
    m["attention"] = load_manifest(lowered)
    circuit = Circuit.from_dict(linear_circuit_dict)
    assert validate_circuit(circuit, m) is EffectClass.OBSERVE
