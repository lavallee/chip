"""Binding: secret-reference enforcement, installation id shape, authority join."""

from __future__ import annotations

import pytest

from chip.authority import EffectClass
from chip.binding import (
    Binding,
    Installation,
    compute_effective_authority,
    validate_installation_id,
    validate_secret_ref,
)
from chip.errors import BindingError


def test_valid_binding(binding_dict):
    b = Binding.from_dict(binding_dict)
    assert b.owner_identity == "owner:demo-desk"
    assert b.authority_ceiling is EffectClass.SYNTHESIZE  # "recommend" alias
    assert b.secret_refs["gateway"] == "ref://vault/gateway-token"


def test_ref_scheme_accepted():
    validate_secret_ref("k", "ref://vault/thing")


def test_symbolic_name_accepted():
    validate_secret_ref("k", "publication-fetch-token")


def test_key_value_secret_rejected():
    with pytest.raises(BindingError):
        validate_secret_ref("k", "AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI1234567890")


def test_high_entropy_literal_rejected():
    with pytest.raises(BindingError):
        validate_secret_ref("k", "sk1234567890abcdefABCDEF0987ZZ")


def test_binding_with_literal_secret_rejected(binding_dict):
    binding_dict["secretRefs"]["gateway"] = "ghp0123456789ABCDEFabcdef0123XYZ"
    with pytest.raises(BindingError):
        Binding.from_dict(binding_dict)


def test_installation_id_validation():
    validate_installation_id("fabexp-3f2a9c81-triage")
    with pytest.raises(BindingError):
        validate_installation_id("")
    with pytest.raises(BindingError):
        validate_installation_id("has space")
    with pytest.raises(BindingError):
        validate_installation_id("short")


def test_installation_round_trip(binding_dict):
    inst = Installation.from_dict(
        {
            "installationId": "fabexp-abcdef01-triage",
            "enabled": True,
            "binding": binding_dict,
            "createdAt": "2026-07-16T00:00:00Z",
            "receiptRefs": ["rcpt:enable-1"],
        }
    )
    assert inst.enabled
    assert inst.installation_id == "fabexp-abcdef01-triage"


def test_effective_authority_join():
    got = compute_effective_authority(
        EffectClass.PROMOTE,
        EffectClass.SYNTHESIZE,
        EffectClass.SYNTHESIZE,
        EffectClass.DRAFT,
        EffectClass.SYNTHESIZE,
    )
    assert got is EffectClass.SYNTHESIZE


def test_effective_authority_missing_approval_fails_closed():
    got = compute_effective_authority(
        EffectClass.PROMOTE,
        EffectClass.SYNTHESIZE,
        EffectClass.SYNTHESIZE,
        EffectClass.DRAFT,
        None,  # no human approval
    )
    assert got is None
