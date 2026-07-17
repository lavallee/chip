"""Environment profiles: the host-owned system-shape layer (§12, spec 0.5.0).

Spec 0.5.0 splits installation-specific facts into three layers, not two:

* the **portable manifest** (with its non-contractual :class:`~chip.manifest.Hints`);
* the **binding** — installation-specific resolution (:mod:`chip.binding`); and
* the **environment profile** (this module) — a *host-owned* document describing
  what exists in one environment: capabilities offered, adapters available,
  gateway profiles, state roots, policy overlays, and conventions.

A binding MAY reference a profile by id (``binding.environment: <profile-id>``)
instead of restating host facts. :func:`resolve_binding_against_environment`
folds a profile into a binding, with **binding-local values overriding profile
values** — the profile supplies defaults for the system's shape, the binding
keeps the last word.

The profile is a plain document with the schema identifier
``environment.spec/v0alpha1``. Like the chip contract, this is an alpha
identifier, not a claim of ecosystem standardization.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from chip.errors import EnvironmentProfileError

if TYPE_CHECKING:
    from chip.binding import Binding

ENVIRONMENT_API_VERSION = "environment.spec/v0alpha1"


def _require(data: dict[str, Any], key: str, ctx: str) -> Any:
    if key not in data or data[key] in (None, ""):
        raise EnvironmentProfileError(f"{ctx}: missing required field {key!r}")
    return data[key]


@dataclass(frozen=True, slots=True)
class EnvironmentProfile:
    """A host-owned description of one environment's system shape (§12, 0.5.0).

    All maps are host facts, not portable contract: ``adapters`` name available
    host adapters, ``gateway_profiles`` the gateway model profiles this
    environment offers, ``state_roots`` where installation state lives here,
    ``policy_overlays`` local policy defaults, and ``conventions`` free-form
    local conventions. ``capabilities`` lists the host capabilities offered.
    """

    id: str
    version: str
    capabilities: tuple[str, ...] = ()
    adapters: dict[str, str] = field(default_factory=dict)
    gateway_profiles: dict[str, str] = field(default_factory=dict)
    state_roots: dict[str, str] = field(default_factory=dict)
    policy_overlays: dict[str, Any] = field(default_factory=dict)
    conventions: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EnvironmentProfile:
        if not isinstance(data, dict):
            raise EnvironmentProfileError("environment profile must be a JSON object")
        api_version = data.get("apiVersion", ENVIRONMENT_API_VERSION)
        if api_version != ENVIRONMENT_API_VERSION:
            raise EnvironmentProfileError(
                f"apiVersion {api_version!r} unsupported; expected {ENVIRONMENT_API_VERSION}"
            )
        kind = data.get("kind", "EnvironmentProfile")
        if kind != "EnvironmentProfile":
            raise EnvironmentProfileError(f"kind {kind!r} unsupported; expected 'EnvironmentProfile'")

        def _str_map(key: str) -> dict[str, str]:
            raw = data.get(key, {})
            if not isinstance(raw, dict):
                raise EnvironmentProfileError(f"environment profile: {key!r} must be an object")
            return {str(k): str(v) for k, v in raw.items()}

        def _obj_map(key: str) -> dict[str, Any]:
            raw = data.get(key, {})
            if not isinstance(raw, dict):
                raise EnvironmentProfileError(f"environment profile: {key!r} must be an object")
            return dict(raw)

        capabilities = data.get("capabilities", [])
        if not isinstance(capabilities, list):
            raise EnvironmentProfileError("environment profile: 'capabilities' must be a list")
        return cls(
            id=_require(data, "id", "environment profile"),
            version=_require(data, "version", "environment profile"),
            capabilities=tuple(str(c) for c in capabilities),
            adapters=_str_map("adapters"),
            gateway_profiles=_str_map("gatewayProfiles"),
            state_roots=_str_map("stateRoots"),
            policy_overlays=_obj_map("policyOverlays"),
            conventions=_obj_map("conventions"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "apiVersion": ENVIRONMENT_API_VERSION,
            "kind": "EnvironmentProfile",
            "id": self.id,
            "version": self.version,
            "capabilities": list(self.capabilities),
            "adapters": dict(self.adapters),
            "gatewayProfiles": dict(self.gateway_profiles),
            "stateRoots": dict(self.state_roots),
            "policyOverlays": dict(self.policy_overlays),
            "conventions": dict(self.conventions),
        }


def load_environment_profile(data: dict[str, Any]) -> EnvironmentProfile:
    """Validate an environment-profile dict and return an :class:`EnvironmentProfile`."""
    return EnvironmentProfile.from_dict(data)


def resolve_binding_against_environment(
    binding: Binding, profile: EnvironmentProfile
) -> dict[str, Any]:
    """Fold ``profile`` into ``binding``, returning an *effective binding* dict (§12).

    The profile supplies host-owned defaults for the system's shape; the binding
    keeps the last word — **binding-local values override profile values**.
    Concretely: host adapters and gateway profiles are the profile's maps updated
    by the binding's; the profile's capabilities, policy overlays, conventions,
    and state roots are surfaced on the effective binding.

    If ``binding`` declares ``environment`` and that id disagrees with
    ``profile.id``, this raises — a binding may only be resolved against the
    profile it references.
    """
    if binding.environment is not None and binding.environment != profile.id:
        raise EnvironmentProfileError(
            f"binding references environment {binding.environment!r} "
            f"but profile id is {profile.id!r}"
        )

    effective: dict[str, Any] = {
        "chipImplementations": dict(binding.chip_implementations),
        "sourceEndpoints": dict(binding.source_endpoints),
        "secretRefs": dict(binding.secret_refs),
        "ownerIdentity": binding.owner_identity,
        "authorityCeiling": binding.authority_ceiling.label,
        "approvalRoutes": dict(binding.approval_routes),
        "stateNamespace": binding.state_namespace,
        "effectDestinations": dict(binding.effect_destinations),
        "budgets": dict(binding.budgets),
        "cadence": dict(binding.cadence),
        "chipParameters": {a: dict(p) for a, p in binding.chip_parameters.items()},
        "environment": profile.id,
        # Binding-local values override profile values (the profile is the default).
        "hostAdapters": {**profile.adapters, **binding.host_adapters},
        "gatewayProfiles": {**profile.gateway_profiles, **binding.gateway_profiles},
        # Host-owned facts the binding references rather than restates.
        "capabilities": list(profile.capabilities),
        "stateRoots": dict(profile.state_roots),
        "policyOverlays": dict(profile.policy_overlays),
        "conventions": dict(profile.conventions),
    }
    return effective
