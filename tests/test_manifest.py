"""Manifest validation: valid case + the required rejections, plus semver."""

from __future__ import annotations

import pytest

from chip.errors import ManifestError
from chip.manifest import (
    ChipManifest,
    load_manifest,
    parse_semver,
    satisfies_range,
)


def test_valid_manifest_loads(publication_attention_manifest):
    m = load_manifest(publication_attention_manifest)
    assert isinstance(m, ChipManifest)
    assert m.metadata.alias == "press.new-report-triage"
    # one gateway stage -> hybrid
    assert m.implementation_class == "hybrid"
    # recommend alias parsed to the synthesize rung
    assert m.authority.maximum_effect_class.label == "synthesize"
    assert "schemas/publication-signal.json@1" in m.schema_refs()


def test_deterministic_class_when_no_gateway(bounded_recommendation_manifest):
    m = load_manifest(bounded_recommendation_manifest)
    assert m.implementation_class == "deterministic"


def test_two_gateway_stages_rejected(publication_attention_manifest):
    stages = publication_attention_manifest["implementation"]["stages"]
    stages.append(
        {
            "id": "assess2",
            "kind": "gateway",
            "determinism": "probabilistic",
            "requestSchema": "schemas/a.json",
            "resultSchema": "schemas/b.json",
        }
    )
    with pytest.raises(ManifestError) as exc:
        load_manifest(publication_attention_manifest)
    assert "gateway" in str(exc.value)


def test_somm_alias_kind_accepted(publication_attention_manifest):
    # deprecated 'somm' kind maps to the public 'gateway' kind
    for s in publication_attention_manifest["implementation"]["stages"]:
        if s["id"] == "assess":
            s["kind"] = "somm"
    m = load_manifest(publication_attention_manifest)
    assert m.implementation_class == "hybrid"


def test_nonempty_secrets_rejected(publication_attention_manifest):
    publication_attention_manifest["dependencies"]["secrets"] = ["ref://x"]
    with pytest.raises(ManifestError) as exc:
        load_manifest(publication_attention_manifest)
    assert "secrets" in str(exc.value)


def test_bad_concurrency_rejected(publication_attention_manifest):
    publication_attention_manifest["state"]["concurrency"] = "cas"
    with pytest.raises(ManifestError):
        load_manifest(publication_attention_manifest)


def test_effect_exceeding_ceiling_rejected(publication_attention_manifest):
    publication_attention_manifest["contract"]["effects"][0]["class"] = "promote"
    with pytest.raises(ManifestError) as exc:
        load_manifest(publication_attention_manifest)
    assert "exceeds authority ceiling" in str(exc.value)


def test_gateway_stage_requires_schemas(publication_attention_manifest):
    for s in publication_attention_manifest["implementation"]["stages"]:
        if s["id"] == "assess":
            del s["requestSchema"]
    with pytest.raises(ManifestError):
        load_manifest(publication_attention_manifest)


def test_bad_api_version_rejected(publication_attention_manifest):
    publication_attention_manifest["apiVersion"] = "chip.spec/v9"
    with pytest.raises(ManifestError):
        load_manifest(publication_attention_manifest)


# ---- semver helpers ----


def test_parse_semver():
    assert parse_semver("1.2.3") == (1, 2, 3)
    with pytest.raises(ManifestError):
        parse_semver("1.2")
    with pytest.raises(ManifestError):
        parse_semver("1.2.x")


def test_satisfies_range():
    assert satisfies_range("0.1.0", ">=0.1.0 <0.2.0")
    assert not satisfies_range("0.2.0", ">=0.1.0 <0.2.0")
    assert not satisfies_range("0.0.9", ">=0.1.0 <0.2.0")
    assert satisfies_range("1.4.2", ">=1.0.0")
    assert satisfies_range("2.0.0", "==2.0.0")
