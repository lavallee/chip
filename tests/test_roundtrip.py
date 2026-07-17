"""End-to-end round trip over a realistic publication-triage chip package.

Writes a full chip package to disk (chip.json + schemas + fixtures), loads it via
load_chip_package, wires a two-chip linear circuit, derives a stable effect key,
and builds both receipt tiers — the whole portable contract exercised once.
"""

from __future__ import annotations

import json

from chip.authority import EffectClass
from chip.circuit import Circuit, validate_circuit
from chip.envelopes import EffectRequest, Signal, derive_effect_key
from chip.fixtures import validate_fixture_coverage
from chip.manifest import load_chip_package, load_manifest
from chip.receipts import Coordinates, build_judgment_receipt, validate_receipt


def _write_schemas(pkg, schema_refs):
    for ref in schema_refs:
        path = pkg / ref
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"$id": ref, "type": "object"}), encoding="utf-8")


def _write_fixtures(pkg):
    for kind in ("positive", "quiet", "failure", "adversarial"):
        d = pkg / "fixtures" / kind
        d.mkdir(parents=True)
        (d / "fixture.json").write_text(
            json.dumps(
                {
                    "kind": kind,
                    "input": {
                        "id": f"sig-{kind}",
                        "type": "publication",
                        "schemaVersion": "1",
                        "observedAt": "2026-07-16T00:00:00Z",
                        "receivedAt": "2026-07-16T00:01:00Z",
                        "source": "example.gov",
                        "authorityContext": "public",
                        "digest": "sha256:x",
                        "lineageKey": f"agency/{kind}",
                        "dedupeKey": f"agency/{kind}",
                    },
                    "expected": {"noEffect": kind != "positive"},
                }
            ),
            encoding="utf-8",
        )


def test_full_package_round_trip(publication_attention_manifest, tmp_path):
    pkg = tmp_path / "new-report-triage"
    pkg.mkdir()
    (pkg / "chip.json").write_text(json.dumps(publication_attention_manifest), encoding="utf-8")
    manifest = load_manifest(publication_attention_manifest)
    _write_schemas(pkg, manifest.schema_refs())
    _write_fixtures(pkg)

    loaded, resolved = load_chip_package(pkg)
    assert loaded.metadata.alias == "press.new-report-triage"
    assert set(resolved) == set(manifest.schema_refs())
    for path in resolved.values():
        assert path.is_file()

    coverage = validate_fixture_coverage(pkg)
    assert len(coverage) == 4


def test_circuit_and_effect_and_receipt_cohere(
    publication_attention_manifest, bounded_recommendation_manifest, linear_circuit_dict
):
    manifests = {
        "attention": load_manifest(publication_attention_manifest),
        "recommend": load_manifest(bounded_recommendation_manifest),
    }
    circuit = Circuit.from_dict(linear_circuit_dict)
    ceiling = validate_circuit(circuit, manifests)
    assert ceiling is EffectClass.SYNTHESIZE

    # A signal comes in; a bounded effect request is produced with a stable key.
    signal = Signal.from_dict(
        {
            "id": "sig-1",
            "type": "publication",
            "schemaVersion": "1",
            "observedAt": "2026-07-16T00:00:00Z",
            "receivedAt": "2026-07-16T00:01:00Z",
            "source": "example.gov",
            "authorityContext": "public",
            "digest": "sha256:x",
            "lineageKey": "agency/report/42",
            "dedupeKey": "agency/report/42",
        }
    )
    key = derive_effect_key(
        signal.lineage_key, "recommend-research", "owner:ideas", manifests["attention"].contract.promise[:16]
    )
    effect = EffectRequest(
        type="recommend-research",
        effect_class=ceiling.label,
        target_owner="owner:ideas",
        payload={"reportId": signal.id},
        idempotency_key=key,
        derivation_version="cek1",
        expected_result_schema="schemas/research-recommendation.json@1",
        originating_evidence_ref="ev:report/42",
        judgment_receipt_ref="rcpt:run/1",
    )
    assert EffectRequest.from_dict(effect.to_dict()) == effect

    receipt = build_judgment_receipt(
        Coordinates(run="run:1", installation="fabexp-abc12345-triage",
                    circuit=circuit.id, chip="press.new-report-triage", binding="bind:1"),
        run_status="completed",
        semantic_outcome="finding-valid",
        terminal_reason="finding",
        digests={"contract": "sha:c", "implementation": "sha256:aaaa", "policy": "sha:p"},
        decisions={"validation": {"ok": True}, "dedupe": {"key": key},
                   "budget": {"usd": 0.02}, "authority": {"ceiling": ceiling.label}},
        effects={"proposed": [effect.to_dict()], "approved": [], "rejected": [],
                 "executed": []},
        state_version_before="v1", state_version_after="v2",
        gateway={"requestId": "gw:1", "usage": {"tokensIn": 800, "tokensOut": 120}},
    )
    validate_receipt(receipt.to_dict())
    assert receipt.to_dict()["decisions"]["dedupe"]["key"] == key
