"""Authority lattice: ordering, fail-closed, alias, prohibition, approval."""

from __future__ import annotations

import pytest

from chip.authority import (
    EffectClass,
    check_effect_allowed,
    effective_authority,
    most_restrictive_approval,
)
from chip.errors import AuthorityError


def test_effect_class_total_order():
    assert EffectClass.OBSERVE < EffectClass.SYNTHESIZE < EffectClass.EXPERIMENT
    assert EffectClass.EXPERIMENT < EffectClass.DRAFT < EffectClass.PROMOTE
    assert min(EffectClass.PROMOTE, EffectClass.OBSERVE) is EffectClass.OBSERVE


def test_parse_labels_and_recommend_alias():
    assert EffectClass.parse("observe") is EffectClass.OBSERVE
    assert EffectClass.parse("promote") is EffectClass.PROMOTE
    # legacy alias maps to synthesize
    assert EffectClass.parse("recommend") is EffectClass.SYNTHESIZE
    assert EffectClass.parse(EffectClass.DRAFT) is EffectClass.DRAFT


def test_parse_unknown_raises():
    with pytest.raises(AuthorityError):
        EffectClass.parse("merge-everything")


def test_effective_authority_is_minimum():
    got = effective_authority(EffectClass.PROMOTE, EffectClass.SYNTHESIZE, EffectClass.DRAFT)
    assert got is EffectClass.SYNTHESIZE


def test_effective_authority_fails_closed_on_missing():
    assert effective_authority(EffectClass.PROMOTE, None) is None
    assert effective_authority() is None


def test_most_restrictive_approval():
    assert most_restrictive_approval(["automatic", "human"]) == "human"
    assert most_restrictive_approval(["automatic"]) == "automatic"
    # fail closed on empty set
    assert most_restrictive_approval([]) == "human"


def test_most_restrictive_approval_unknown_raises():
    with pytest.raises(AuthorityError):
        most_restrictive_approval(["maybe"])


def test_check_effect_allowed_ok():
    check_effect_allowed(EffectClass.SYNTHESIZE, EffectClass.PROMOTE, prohibited=[])


def test_check_effect_allowed_no_authority_fails_closed():
    with pytest.raises(AuthorityError):
        check_effect_allowed(EffectClass.OBSERVE, None)


def test_check_effect_allowed_exceeds_ceiling():
    with pytest.raises(AuthorityError):
        check_effect_allowed(EffectClass.PROMOTE, EffectClass.SYNTHESIZE)


def test_check_effect_allowed_prohibited():
    with pytest.raises(AuthorityError):
        check_effect_allowed(
            EffectClass.SYNTHESIZE, EffectClass.PROMOTE, prohibited=["recommend"]
        )
