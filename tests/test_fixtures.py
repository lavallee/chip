"""Fixture loader + §7 coverage check, using an on-disk temp package."""

from __future__ import annotations

import json

import pytest

from chip.errors import FixtureError
from chip.fixtures import load_fixtures, validate_fixture_coverage


def _signal(name):
    return {
        "id": f"sig-{name}",
        "type": "publication",
        "schemaVersion": "1",
        "observedAt": "2026-07-16T09:00:00Z",
        "receivedAt": "2026-07-16T09:01:00Z",
        "source": "example.gov/rss",
        "authorityContext": "public-agency",
        "digest": "sha256:deadbeef",
        "lineageKey": f"agency/{name}",
        "dedupeKey": f"agency/{name}",
        "trust": "hostile",
    }


def _write_fixture(base, name, kind, expected, canned=None):
    d = base / name
    d.mkdir()
    body = {"kind": kind, "input": _signal(name), "expected": expected}
    if canned is not None:
        body["cannedGatewayResult"] = canned
    (d / "fixture.json").write_text(json.dumps(body), encoding="utf-8")


def _full_package(tmp_path):
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    _write_fixture(fixtures, "positive", "positive", {"responseKind": "claim"},
                   canned={"materiality": "high"})
    _write_fixture(fixtures, "quiet", "quiet", {"responseKind": "quiet", "noEffect": True})
    _write_fixture(fixtures, "failure", "failure", {"errorClass": "EnvelopeError"})
    _write_fixture(fixtures, "adversarial", "adversarial", {"noEffect": True})
    return fixtures


def test_load_fixtures(tmp_path):
    fixtures = _full_package(tmp_path)
    loaded = load_fixtures(fixtures)
    assert {f.kind for f in loaded} == {"positive", "quiet", "failure", "adversarial"}
    positive = next(f for f in loaded if f.kind == "positive")
    assert positive.canned_gateway_result == {"materiality": "high"}


def test_load_fixtures_missing_dir(tmp_path):
    with pytest.raises(FixtureError):
        load_fixtures(tmp_path / "nope")


def test_bad_kind_rejected(tmp_path):
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    _write_fixture(fixtures, "weird", "sideways", {"noEffect": True})
    with pytest.raises(FixtureError):
        load_fixtures(fixtures)


def test_coverage_passes(tmp_path):
    _full_package(tmp_path)
    (tmp_path / "chip.json").write_text(json.dumps({"evaluation": {"fixtures": "fixtures/"}}))
    loaded = validate_fixture_coverage(tmp_path)
    assert len(loaded) == 4


def test_coverage_missing_kind_rejected(tmp_path):
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    _write_fixture(fixtures, "positive", "positive", {"responseKind": "claim"})
    _write_fixture(fixtures, "quiet", "quiet", {"noEffect": True})
    with pytest.raises(FixtureError) as exc:
        validate_fixture_coverage(tmp_path)
    assert "failure" in str(exc.value) and "adversarial" in str(exc.value)
