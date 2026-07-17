"""The effect-class authority lattice and its composition rules.

Implements chip.spec/v0alpha1 §14 (authority, effect classes) and the §12
effective-authority intersection. Every function here is pure: no I/O, no
state. Authority is *never* inferred from model prose — these helpers are the
deterministic boundary a host consults before dispatching an effect.

Effect classes are totally ordered by how consequential they are::

    observe < synthesize < experiment < draft < promote

The legacy manifest term ``recommend`` maps to :data:`EffectClass.SYNTHESIZE`;
the original text is retained by callers that need to echo a manifest verbatim.

Fail-closed is the governing rule: any missing or unparseable authority
resolves to *no authority* (``None``), never to a permissive default.
"""

from __future__ import annotations

from enum import IntEnum

from chip.errors import AuthorityError

# Approval modes, least-restrictive first. "human" always wins a composition.
_APPROVAL_ORDER = ("automatic", "human")


class EffectClass(IntEnum):
    """Ordered ladder of effect consequence (§14).

    Backed by :class:`enum.IntEnum` so the natural ``<``/``min`` operators give
    the lattice ordering directly. The integer values are an implementation
    detail; the wire form is the lowercase :pyattr:`label` (e.g. ``"observe"``).

    Numbering is deliberately **1-based**: the lowest rung (``OBSERVE``) must be
    truthy so a ``if ceiling:`` guard cannot silently treat an observe-only
    ceiling as "no authority". Only ``None`` means no authority (fail closed).
    """

    OBSERVE = 1
    SYNTHESIZE = 2
    EXPERIMENT = 3
    DRAFT = 4
    PROMOTE = 5

    @property
    def label(self) -> str:
        """Lowercase spec wire name, e.g. ``EffectClass.OBSERVE.label == 'observe'``."""
        return self.name.lower()

    @classmethod
    def parse(cls, value: str | EffectClass) -> EffectClass:
        """Parse a spec effect-class string into an :class:`EffectClass`.

        Accepts the canonical labels and the legacy alias ``"recommend"``
        (→ :data:`SYNTHESIZE`). Raises :class:`AuthorityError` on anything else
        so an unknown class fails closed rather than silently widening.
        """
        if isinstance(value, cls):
            return value
        if not isinstance(value, str):
            raise AuthorityError(
                f"effect class must be a string, got {type(value).__name__}"
            )
        key = value.strip().lower()
        if key == "recommend":  # legacy alias, retained in manifest text
            return cls.SYNTHESIZE
        for member in cls:
            if member.label == key:
                return member
        allowed = ", ".join(m.label for m in cls)
        raise AuthorityError(
            f"unknown effect class {value!r}; expected one of: {allowed} (or legacy 'recommend')"
        )


# Public alias retained so manifest text using "recommend" round-trips.
RECOMMEND_ALIAS = "recommend"


def effective_authority(*maxima: EffectClass | None) -> EffectClass | None:
    """Intersect a set of authority ceilings, failing closed on any gap.

    The effective ceiling is the *minimum* (most restrictive) of every provided
    ceiling — this is the §12 intersection of chip ∩ circuit ∩ binding ∩ host ∩
    approval. Per §12, "any missing authority fails closed": if the caller
    supplies no ceilings, or any ceiling is ``None``, the result is ``None``,
    meaning *no authority granted*.
    """
    if not maxima:
        return None
    if any(m is None for m in maxima):
        return None
    return min(maxima)  # type: ignore[type-var]  # None excluded above


def most_restrictive_approval(modes: list[str] | tuple[str, ...]) -> str:
    """Compose approval modes by choosing the most restrictive (§12).

    ``"human"`` outranks ``"automatic"``; a permissive overlay can never weaken
    a stricter requirement. Fails closed: an empty set of modes yields
    ``"human"`` (require a human) rather than assuming automation is allowed.
    Unknown mode strings raise :class:`AuthorityError`.
    """
    if not modes:
        return "human"
    rank = -1
    winner = "human"
    for mode in modes:
        key = mode.strip().lower()
        if key not in _APPROVAL_ORDER:
            allowed = ", ".join(_APPROVAL_ORDER)
            raise AuthorityError(
                f"unknown approval mode {mode!r}; expected one of: {allowed}"
            )
        if _APPROVAL_ORDER.index(key) > rank:
            rank = _APPROVAL_ORDER.index(key)
            winner = key
    return winner


def check_effect_allowed(
    effect_class: EffectClass,
    ceiling: EffectClass | None,
    prohibited: list[str] | tuple[str, ...] = (),
) -> None:
    """Assert an effect may be dispatched under a ceiling, else raise.

    Raises :class:`AuthorityError` when:

    * ``ceiling`` is ``None`` (no authority — fail closed);
    * ``effect_class`` outranks ``ceiling``; or
    * ``effect_class`` is named in ``prohibited``.

    ``prohibited`` entries are matched against the effect class label, tolerating
    the legacy ``recommend`` alias.
    """
    if ceiling is None:
        raise AuthorityError(
            f"effect '{effect_class.label}' denied: no authority granted (failed closed)"
        )
    prohibited_classes = {EffectClass.parse(p) for p in prohibited}
    if effect_class in prohibited_classes:
        raise AuthorityError(
            f"effect '{effect_class.label}' is prohibited by authority contract"
        )
    if effect_class > ceiling:
        raise AuthorityError(
            f"effect '{effect_class.label}' exceeds authority ceiling "
            f"'{ceiling.label}'"
        )
