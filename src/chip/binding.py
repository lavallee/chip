"""Binding and installation models (§12).

A binding resolves a portable circuit to a concrete environment: chip
implementations, host adapters, source endpoints, secret *references* (never
values), gateway profiles, owner identity, budgets/cadence, authority ceiling
and approval routes, state namespace, and effect destinations. An installation
is an *enabled* binding with a globally-unique installation id minted by the
owning system (§9, §12).

Two invariants are enforced here:

* **Secret references only** — a value that looks like an actual secret (a
  ``KEY=``/``TOKEN=``/``SECRET=`` assignment or a long high-entropy token) is
  rejected. Only ``ref://...`` references or short symbolic names are accepted.
* **Effective authority fails closed** — :func:`compute_effective_authority`
  intersects chip ∩ circuit ∩ binding ∩ host ∩ approval; any missing ceiling
  collapses the result to no authority (via :mod:`chip.authority`).

Cadence is descriptive metadata only in v1: the owning system emits activation
signals; the circuit never schedules itself (§12).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from chip.authority import EffectClass, effective_authority
from chip.errors import BindingError

# A secret *reference* either uses the ref:// scheme or is a short symbolic name.
_REF_SCHEME = "ref://"
# Assignment carrying a secret-ish key on its left-hand side.
_SECRET_ASSIGNMENT_RE = re.compile(r"(KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL)\w*\s*=", re.I)
# A long, separator-free, mixed alphanumeric run looks like a raw secret value.
_HIGH_ENTROPY_RE = re.compile(r"^[A-Za-z0-9+/=_.\-]{24,}$")


def _looks_like_secret_value(value: str) -> bool:
    """Heuristic: does ``value`` look like a literal secret rather than a reference?"""
    if _SECRET_ASSIGNMENT_RE.search(value):
        return True
    token = value.strip()
    if not _HIGH_ENTROPY_RE.match(token):
        return False
    # Symbolic names use separators between words (my-api-key, my.token.ref) and
    # are not both-case + digit soups. Treat a token with a mix of upper, lower,
    # and digits and few separators as a raw secret.
    has_upper = any(c.isupper() for c in token)
    has_lower = any(c.islower() for c in token)
    has_digit = any(c.isdigit() for c in token)
    separators = sum(token.count(sep) for sep in "-._")
    if has_digit and has_upper and has_lower and separators <= 1:
        return True
    return has_digit and len(token) >= 32 and separators <= 2


def validate_secret_ref(name: str, value: str) -> None:
    """Assert ``value`` is a secret *reference*, not a secret value (§12).

    Accepts a ``ref://...`` reference or a short symbolic name. Raises
    :class:`BindingError` when the value looks like a literal credential.
    """
    if not isinstance(value, str) or not value.strip():
        raise BindingError(f"secret ref {name!r}: must be a non-empty reference string")
    if value.startswith(_REF_SCHEME):
        return
    if _looks_like_secret_value(value):
        raise BindingError(
            f"secret ref {name!r} looks like a literal secret value; bindings carry "
            "references only (use 'ref://...' or a symbolic name), never secret values (§12)"
        )


@dataclass(frozen=True, slots=True)
class Binding:
    """An environment-specific resolution of a circuit (§12)."""

    chip_implementations: dict[str, str]
    host_adapters: dict[str, str]
    source_endpoints: dict[str, str]
    secret_refs: dict[str, str]
    gateway_profiles: dict[str, str]
    owner_identity: str
    authority_ceiling: EffectClass
    approval_routes: dict[str, str] = field(default_factory=dict)
    state_namespace: str = ""
    effect_destinations: dict[str, str] = field(default_factory=dict)
    budgets: dict[str, Any] = field(default_factory=dict)
    cadence: dict[str, Any] = field(default_factory=dict)  # descriptive only in v1
    # Per-chip configuration the host merges into the activation ``config``
    # (keyed by chip alias). Host-injected keys (promise_id, effect_target, ...)
    # always win over these; values must not carry secret literals (§12).
    chip_parameters: dict[str, dict[str, Any]] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Binding:
        secret_refs = dict(data.get("secretRefs", {}))
        for name, value in secret_refs.items():
            validate_secret_ref(name, value)
        owner = data.get("ownerIdentity")
        if not owner:
            raise BindingError("binding: missing required field 'ownerIdentity'")
        ceiling = data.get("authorityCeiling")
        if not ceiling:
            raise BindingError("binding: missing required field 'authorityCeiling'")
        chip_parameters = data.get("chipParameters", {})
        if not isinstance(chip_parameters, dict) or any(
            not isinstance(v, dict) for v in chip_parameters.values()
        ):
            raise BindingError("binding: 'chipParameters' must map chip alias -> parameter object")
        for alias, params in chip_parameters.items():
            for key, value in params.items():
                if isinstance(value, str) and _looks_like_secret_value(value):
                    raise BindingError(
                        f"chipParameters[{alias!r}][{key!r}] looks like a literal secret value; "
                        "bindings carry references only (§12)"
                    )
        return cls(
            chip_implementations=dict(data.get("chipImplementations", {})),
            host_adapters=dict(data.get("hostAdapters", {})),
            source_endpoints=dict(data.get("sourceEndpoints", {})),
            secret_refs=secret_refs,
            gateway_profiles=dict(data.get("gatewayProfiles", {})),
            owner_identity=owner,
            authority_ceiling=EffectClass.parse(ceiling),
            approval_routes=dict(data.get("approvalRoutes", {})),
            state_namespace=data.get("stateNamespace", ""),
            effect_destinations=dict(data.get("effectDestinations", {})),
            budgets=data.get("budgets", {}),
            cadence=data.get("cadence", {}),
            chip_parameters={a: dict(p) for a, p in chip_parameters.items()},
        )


# A globally-unique-shaped installation id: no whitespace, reasonably long.
_INSTALLATION_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:\-]{7,}$")


@dataclass(frozen=True, slots=True)
class Installation:
    """An enabled binding owning a globally-unique installation id (§9, §12)."""

    installation_id: str
    binding: Binding
    enabled: bool = True
    created_at: str | None = None
    receipt_refs: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Installation:
        iid = data.get("installationId")
        validate_installation_id(iid)
        binding_data = data.get("binding")
        if not binding_data:
            raise BindingError("installation: missing required field 'binding'")
        return cls(
            installation_id=iid,  # type: ignore[arg-type]  # validated above
            binding=Binding.from_dict(binding_data),
            enabled=bool(data.get("enabled", True)),
            created_at=data.get("createdAt"),
            receipt_refs=tuple(data.get("receiptRefs", [])),
        )


def validate_installation_id(iid: Any) -> None:
    """Assert an installation id is a non-empty, globally-unique-shaped string (§9)."""
    if not isinstance(iid, str) or not iid.strip():
        raise BindingError("installation id must be a non-empty string")
    if not _INSTALLATION_ID_RE.match(iid):
        raise BindingError(
            f"installation id {iid!r} is not globally-unique-shaped "
            "(need >=8 chars, no whitespace, minted by the owning system, §9)"
        )


def compute_effective_authority(
    chip_max: EffectClass | None,
    circuit_max: EffectClass | None,
    binding_max: EffectClass | None,
    host_max: EffectClass | None,
    approval: EffectClass | None,
) -> EffectClass | None:
    """Intersect the five §12 authority ceilings, failing closed on any gap.

    Returns the most restrictive of chip ∩ circuit ∩ binding ∩ host ∩ current
    human approval. ``approval`` is the class a human has approved up to; if it
    (or any other ceiling) is ``None``, the result is ``None`` — no authority.
    """
    return effective_authority(chip_max, circuit_max, binding_max, host_max, approval)
