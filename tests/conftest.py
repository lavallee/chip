"""Shared fixtures: realistic, generic-vocabulary chip/circuit/binding dicts.

Everything here uses the public vocabulary (chip, port, stage, gateway, effect,
binding, installation). The shape mirrors a publication-triage pilot without any
private system names.
"""

from __future__ import annotations

import copy

import pytest


def _publication_attention_manifest() -> dict:
    """A hybrid attention chip: normalize (code) -> assess (gateway) -> validate (policy)."""
    return {
        "apiVersion": "chip.spec/v0alpha1",
        "kind": "Chip",
        "metadata": {
            "id": "https://example.invalid/chips/press#new-report-triage",
            "alias": "press.new-report-triage",
            "version": "0.1.0",
            "title": "New report triage",
            "description": "Assess newly published reports and emit a finding or a quiet receipt.",
            "license": "Apache-2.0",
            "source": {
                "repository": "https://example.invalid/chips/press",
                "revision": "4f3c2a1",
                "path": "chips/new-report-triage",
            },
            "artifact": {"digest": "sha256:aaaa", "signature": "sig:demo"},
        },
        "contract": {
            "promise": "For every new in-scope report, produce one materiality finding or a quiet receipt.",
            "inputs": [
                {
                    "name": "publication",
                    "schema": "schemas/publication-signal.json@1",
                    "delivery": "at-least-once",
                }
            ],
            "outputs": [
                {"name": "finding", "schema": "schemas/materiality-finding.json@1"},
                {"name": "quiet", "schema": "schemas/quiet-run.json@1"},
            ],
            "effects": [
                {
                    "name": "recommend-research",
                    "schema": "schemas/research-recommendation.json@1",
                    "class": "recommend",
                    "defaultApproval": "human",
                }
            ],
        },
        "state": {
            "schema": "schemas/state.json@1",
            "scope": "installation",
            "retention": "P365D",
            "cursor": "required",
            "concurrency": "single-flight",
            "migration": "migrations/state-v1.json",
        },
        "implementation": {
            "runtime": "python",
            "entrypoint": "chip:run",
            "stagesAreContractual": False,
            "stages": [
                {"id": "normalize", "kind": "code", "determinism": "deterministic"},
                {
                    "id": "assess",
                    "kind": "gateway",
                    "determinism": "probabilistic",
                    "requestSchema": "schemas/assessment-request.json@1",
                    "resultSchema": "schemas/assessment-result.json@1",
                    "profile": "materiality-mid",
                },
                {"id": "validate", "kind": "policy", "determinism": "deterministic"},
            ],
        },
        "dependencies": {
            "capabilities": ["state.single-flight.v1", "gateway-attempt.v1"],
            "adapters": ["publication.fetch"],
            "secrets": [],
        },
        "authority": {
            "maximumEffectClass": "recommend",
            "prohibited": ["promote"],
            "approval": {"mode": "most-restrictive-wins"},
        },
        "limits": {
            "timeout": "PT5M",
            "maxActivationsPerHour": 4,
            "maxEffectsPerDay": 2,
            "cooldown": "PT6H",
            "modelBudgetUsd": 0.5,
            "retry": {"scope": "pre-effect-stage", "attempts": 2, "backoff": "exponential"},
        },
        "security": {
            "inputTrust": "hostile",
            "networkAllowlist": ["example.gov"],
            "filesystem": "none",
            "promptInjectionPolicy": "evidence-only",
        },
        "evaluation": {
            "fixtures": "fixtures/",
            "heldoutSuite": "evals/heldout-v1.json",
            "results": [],
        },
        "compatibility": {
            "chipSpec": ">=0.1.0 <0.2.0",
            "requiredHostCapabilities": ["receipts.v1", "state.single-flight.v1"],
        },
    }


def _bounded_recommendation_manifest() -> dict:
    """A deterministic downstream chip taking a finding, emitting a recommendation."""
    return {
        "apiVersion": "chip.spec/v0alpha1",
        "kind": "Chip",
        "metadata": {
            "id": "https://example.invalid/chips/press#bounded-recommendation",
            "alias": "press.bounded-recommendation",
            "version": "0.1.0",
            "title": "Bounded recommendation",
            "description": "Emit a rate-limited, evidence-linked recommendation from a finding.",
            "license": "Apache-2.0",
            "source": {
                "repository": "https://example.invalid/chips/press",
                "revision": "4f3c2a1",
                "path": "chips/bounded-recommendation",
            },
            "artifact": {"digest": "sha256:bbbb"},
        },
        "contract": {
            "promise": "Given a materiality finding, emit at most one human-gated recommendation.",
            "inputs": [{"name": "finding", "schema": "schemas/materiality-finding.json@1"}],
            "outputs": [{"name": "recommendation", "schema": "schemas/research-recommendation.json@1"}],
            "effects": [
                {
                    "name": "recommend-research",
                    "schema": "schemas/research-recommendation.json@1",
                    "class": "recommend",
                    "defaultApproval": "human",
                }
            ],
        },
        "state": {
            "schema": "schemas/rec-state.json@1",
            "scope": "installation",
            "retention": "P90D",
            "cursor": "optional",
            "concurrency": "single-flight",
        },
        "implementation": {
            "runtime": "python",
            "entrypoint": "chip:run",
            "stagesAreContractual": False,
            "stages": [{"id": "emit", "kind": "code", "determinism": "deterministic"}],
        },
        "dependencies": {"capabilities": [], "adapters": ["recommendation.emit"], "secrets": []},
        "authority": {"maximumEffectClass": "recommend", "prohibited": ["promote"]},
        "limits": {"maxEffectsPerDay": 2},
        "security": {"inputTrust": "untrusted"},
        "evaluation": {"fixtures": "fixtures/"},
        "compatibility": {"chipSpec": ">=0.1.0 <0.2.0", "requiredHostCapabilities": ["receipts.v1"]},
    }


@pytest.fixture
def publication_attention_manifest() -> dict:
    return copy.deepcopy(_publication_attention_manifest())


@pytest.fixture
def bounded_recommendation_manifest() -> dict:
    return copy.deepcopy(_bounded_recommendation_manifest())


@pytest.fixture
def linear_circuit_dict() -> dict:
    return {
        "id": "circuit:publication-triage",
        "version": "0.1.0",
        "activationSignalType": "publication",
        "authorityCeiling": "recommend",
        "chips": [
            {
                "ref": "attention",
                "chip": "press.new-report-triage",
                "contractVersion": "0.1.0",
                "implementation": "sha256:aaaa",
            },
            {
                "ref": "recommend",
                "chip": "press.bounded-recommendation",
                "contractVersion": "0.1.0",
                "implementation": "sha256:bbbb",
            },
        ],
        "connections": [
            {
                "fromChip": "attention",
                "fromPort": "finding",
                "toChip": "recommend",
                "toPort": "finding",
            },
            {"fromChip": "recommend", "fromPort": "recommendation", "toChip": "terminal"},
        ],
        "terminalOutcomes": ["recommendation-emitted"],
        "quietOutcomes": ["no-new-report"],
    }


@pytest.fixture
def binding_dict() -> dict:
    return {
        "chipImplementations": {
            "press.new-report-triage": "sha256:aaaa",
            "press.bounded-recommendation": "sha256:bbbb",
        },
        "hostAdapters": {"publication.fetch": "host://adapters/pubfetch"},
        "sourceEndpoints": {"publication": "file:///snapshots/agency-rss"},
        "secretRefs": {"gateway": "ref://vault/gateway-token"},
        "gatewayProfiles": {"assess": "materiality-mid@1"},
        "ownerIdentity": "owner:demo-desk",
        "authorityCeiling": "recommend",
        "approvalRoutes": {"recommend-research": "human:desk-editor"},
        "stateNamespace": "demo-desk/publication-triage",
        "effectDestinations": {"recommend-research": "owner://ideas"},
        "budgets": {"modelBudgetUsd": 0.5},
        "cadence": {"note": "operator emits activation daily"},
    }


def signal_dict(**overrides) -> dict:
    base = {
        "id": "sig-0001",
        "type": "publication",
        "schemaVersion": "1",
        "observedAt": "2026-07-16T09:00:00Z",
        "receivedAt": "2026-07-16T09:01:00Z",
        "source": "example.gov/rss",
        "authorityContext": "public-agency",
        "digest": "sha256:deadbeef",
        "lineageKey": "agency/report/2026-07-16/001",
        "dedupeKey": "agency/report/2026-07-16/001",
        "trust": "hostile",
    }
    base.update(overrides)
    return base


@pytest.fixture
def make_signal():
    return signal_dict
