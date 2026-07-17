"""Manifest validation: valid case + the required rejections, plus semver."""

from __future__ import annotations

import json

import pytest

from chip.errors import ManifestError
from chip.manifest import (
    ChipManifest,
    load_chip_package,
    load_manifest,
    parse_semver,
    satisfies_range,
    split_schema_ref,
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


def test_instruction_fields_default_empty(publication_attention_manifest):
    m = load_manifest(publication_attention_manifest)
    assert m.contract.instruction_fields == ()


def test_instruction_fields_parsed(publication_attention_manifest):
    publication_attention_manifest["contract"]["instructionFields"] = ["rationale", "summary"]
    m = load_manifest(publication_attention_manifest)
    assert m.contract.instruction_fields == ("rationale", "summary")


def test_instruction_fields_rejects_non_string(publication_attention_manifest):
    publication_attention_manifest["contract"]["instructionFields"] = ["ok", ""]
    with pytest.raises(ManifestError):
        load_manifest(publication_attention_manifest)
    publication_attention_manifest["contract"]["instructionFields"] = "notalist"
    with pytest.raises(ManifestError):
        load_manifest(publication_attention_manifest)


# ---- schema ref split (file vs. version) ----


def test_split_schema_ref():
    assert split_schema_ref("schemas/x.json@1") == ("schemas/x.json", "1")
    assert split_schema_ref("schemas/x.json@12") == ("schemas/x.json", "12")
    # no @ -> versionless
    assert split_schema_ref("schemas/x.json") == ("schemas/x.json", None)
    # empty version rejected
    with pytest.raises(ManifestError):
        split_schema_ref("schemas/x.json@")


def test_load_chip_package_resolves_versionless_file(publication_attention_manifest, tmp_path):
    # Manifest refs carry @1; the on-disk file is versionless. The resolved map
    # keys on the FULL ref but points at the versionless file.
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "chip.json").write_text(json.dumps(publication_attention_manifest), encoding="utf-8")
    m = load_manifest(publication_attention_manifest)
    for ref in m.schema_refs():
        file_path, version = split_schema_ref(ref)
        assert version == "1"  # every example ref is pinned @1
        p = pkg / file_path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"$id": ref, "type": "object"}), encoding="utf-8")
    _, resolved = load_chip_package(pkg)
    for ref in m.schema_refs():
        assert ref in resolved  # keyed on full @-versioned ref
        assert resolved[ref].name.endswith(".json")  # versionless file on disk
        assert "@" not in resolved[ref].name


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
