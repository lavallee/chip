"""Environment profile: parse/validate and binding resolution (spec 0.5.0)."""

from __future__ import annotations

import pytest

from chip.binding import Binding
from chip.environment import (
    EnvironmentProfile,
    load_environment_profile,
    resolve_binding_against_environment,
)
from chip.errors import EnvironmentProfileError


def _profile() -> dict:
    return {
        "apiVersion": "environment.spec/v0alpha1",
        "kind": "EnvironmentProfile",
        "id": "env:reference-host",
        "version": "1",
        "capabilities": ["receipts.v1", "state.single-flight.v1"],
        "adapters": {
            "publication.fetch": "host://adapters/pubfetch",
            "recommendation.emit": "host://adapters/ideas",
        },
        "gatewayProfiles": {"assess": "materiality-mid@1"},
        "stateRoots": {"default": "file:///var/lib/host/state"},
        "policyOverlays": {"maxEffectsPerDay": 2},
        "conventions": {"timezone": "UTC"},
    }


def test_profile_round_trip():
    p = load_environment_profile(_profile())
    assert p.id == "env:reference-host"
    assert "receipts.v1" in p.capabilities
    assert p.adapters["publication.fetch"].startswith("host://")
    # round-trips
    assert EnvironmentProfile.from_dict(p.to_dict()).state_roots == p.state_roots


def test_bad_api_version_rejected():
    data = _profile()
    data["apiVersion"] = "environment.spec/v9"
    with pytest.raises(EnvironmentProfileError):
        load_environment_profile(data)


def test_missing_id_rejected():
    data = _profile()
    del data["id"]
    with pytest.raises(EnvironmentProfileError):
        load_environment_profile(data)


def test_capabilities_must_be_list():
    data = _profile()
    data["capabilities"] = {"nope": True}
    with pytest.raises(EnvironmentProfileError):
        load_environment_profile(data)


def test_resolve_merges_profile_defaults(binding_dict):
    binding_dict["environment"] = "env:reference-host"
    # binding drops the host-owned adapters/gatewayProfiles; profile supplies them
    binding_dict["hostAdapters"] = {}
    binding_dict["gatewayProfiles"] = {}
    binding = Binding.from_dict(binding_dict)
    profile = load_environment_profile(_profile())
    eff = resolve_binding_against_environment(binding, profile)
    assert eff["hostAdapters"]["publication.fetch"] == "host://adapters/pubfetch"
    assert eff["gatewayProfiles"]["assess"] == "materiality-mid@1"
    assert eff["capabilities"] == ["receipts.v1", "state.single-flight.v1"]
    assert eff["stateRoots"]["default"].startswith("file://")
    assert eff["environment"] == "env:reference-host"


def test_binding_local_values_override_profile(binding_dict):
    binding_dict["environment"] = "env:reference-host"
    binding_dict["hostAdapters"] = {"publication.fetch": "host://override/pubfetch"}
    binding = Binding.from_dict(binding_dict)
    profile = load_environment_profile(_profile())
    eff = resolve_binding_against_environment(binding, profile)
    # binding wins for the key it declares; profile fills the rest
    assert eff["hostAdapters"]["publication.fetch"] == "host://override/pubfetch"
    assert eff["hostAdapters"]["recommendation.emit"] == "host://adapters/ideas"


def test_resolve_rejects_mismatched_environment(binding_dict):
    binding_dict["environment"] = "env:some-other-host"
    binding = Binding.from_dict(binding_dict)
    profile = load_environment_profile(_profile())
    with pytest.raises(EnvironmentProfileError, match="references environment"):
        resolve_binding_against_environment(binding, profile)


def test_binding_environment_optional(binding_dict):
    # a binding without an environment ref still resolves against a profile
    binding = Binding.from_dict(binding_dict)
    assert binding.environment is None
    profile = load_environment_profile(_profile())
    eff = resolve_binding_against_environment(binding, profile)
    assert eff["environment"] == "env:reference-host"
