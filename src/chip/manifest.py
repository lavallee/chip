"""Chip manifest model, loader, and a dependency-free semver-range matcher.

Implements chip.spec/v0alpha1 §7 (package contract), §7.1 (manifest shape),
§10.3 (implementation class), and the §3.1 v1 restrictions. The canonical
interchange is a plain JSON dict (``chip.json`` at a chip package root); YAML in
§7.1 is illustrative only. Field names use the manifest's camelCase; Python
attributes use snake_case.

Key v1 rules enforced on load:

* at most **one** gateway stage per chip (§10.3), and the implementation class
  is ``deterministic`` when there is none, else ``hybrid``;
* ``dependencies.secrets`` MUST be an empty list (§3.1 — the pilot is
  credential-free);
* state scope/concurrency restricted to installation/single-flight (via
  :class:`chip.state.StateContract`); and
* ``compatibility.chipSpec`` is a satisfiable semver range for this library.

The stage kind the spec calls a "Somm stage" is named ``gateway`` here (public
vocabulary). ``somm`` is accepted as a deprecated alias when parsing manifests.

Two accretive, non-contractual surfaces arrived in spec 0.5.0:

* ``implementation.authoredAgainst`` — the model generation the judgment-stage
  artifacts were tuned for (§7.1/§10.2); and
* a top-level ``hints`` block — harness/model-keyed annotations that sit
  explicitly OUTSIDE the compatibility contract (like stages) and may be pruned
  without a version bump (§7). :func:`prune_hints` drops entries older than a
  given model generation.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from chip.authority import EffectClass
from chip.errors import ManifestError, StateError
from chip.state import StateContract
from chip.version import SPEC_VERSION

# ---------------------------------------------------------------------------
# Semver + range matching (no dependency; supports the ">=X.Y.Z <A.B.C" forms
# used by compatibility.chipSpec).
# ---------------------------------------------------------------------------

_OPERATORS = (">=", "<=", "==", ">", "<")


def parse_semver(value: str) -> tuple[int, int, int]:
    """Parse ``"MAJOR.MINOR.PATCH"`` into an int tuple.

    Pre-release/build suffixes are not part of v1 chip versions and are
    rejected. Raises :class:`ManifestError` on anything malformed.
    """
    parts = value.strip().split(".")
    if len(parts) != 3:
        raise ManifestError(f"invalid semver {value!r}: expected MAJOR.MINOR.PATCH")
    try:
        major, minor, patch = (int(p) for p in parts)
    except ValueError as exc:
        raise ManifestError(f"invalid semver {value!r}: non-integer component") from exc
    if major < 0 or minor < 0 or patch < 0:
        raise ManifestError(f"invalid semver {value!r}: negative component")
    return (major, minor, patch)


def _split_constraint(constraint: str) -> tuple[str, tuple[int, int, int]]:
    for op in _OPERATORS:
        if constraint.startswith(op):
            return op, parse_semver(constraint[len(op):])
    raise ManifestError(
        f"invalid version constraint {constraint!r}: must start with one of {', '.join(_OPERATORS)}"
    )


def satisfies_range(version: str, range_spec: str) -> bool:
    """Return whether ``version`` satisfies a space-separated ANDed range.

    Example: ``satisfies_range("0.1.0", ">=0.1.0 <0.2.0") is True``. Each
    whitespace-separated token is a ``<op><semver>`` constraint; all must hold.
    Supports ``>=``, ``>``, ``<=``, ``<``, ``==``.
    """
    v = parse_semver(version)
    tokens = range_spec.split()
    if not tokens:
        raise ManifestError("empty version range")
    for token in tokens:
        op, bound = _split_constraint(token)
        if op == ">=" and not v >= bound:
            return False
        if op == ">" and not v > bound:
            return False
        if op == "<=" and not v <= bound:
            return False
        if op == "<" and not v < bound:
            return False
        if op == "==" and v != bound:
            return False
    return True


# ---------------------------------------------------------------------------
# Manifest sub-models
# ---------------------------------------------------------------------------


def _require(d: dict[str, Any], key: str, ctx: str) -> Any:
    if key not in d or d[key] in (None, ""):
        raise ManifestError(f"{ctx}: missing required field {key!r}")
    return d[key]


@dataclass(frozen=True, slots=True)
class SourceCoordinate:
    repository: str
    revision: str
    path: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SourceCoordinate:
        ctx = "metadata.source"
        return cls(
            repository=_require(data, "repository", ctx),
            revision=_require(data, "revision", ctx),
            path=_require(data, "path", ctx),
        )


@dataclass(frozen=True, slots=True)
class ArtifactInfo:
    digest: str
    signature: str | None = None
    provenance: str | None = None
    sbom: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ArtifactInfo:
        return cls(
            digest=_require(data, "digest", "metadata.artifact"),
            signature=data.get("signature"),
            provenance=data.get("provenance"),
            sbom=data.get("sbom"),
        )


@dataclass(frozen=True, slots=True)
class Metadata:
    id: str
    alias: str
    version: str
    title: str
    description: str
    license: str
    source: SourceCoordinate
    artifact: ArtifactInfo

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Metadata:
        ctx = "metadata"
        version = _require(data, "version", ctx)
        parse_semver(version)  # validate shape early
        return cls(
            id=_require(data, "id", ctx),
            alias=_require(data, "alias", ctx),
            version=version,
            title=_require(data, "title", ctx),
            description=_require(data, "description", ctx),
            license=_require(data, "license", ctx),
            source=SourceCoordinate.from_dict(_require(data, "source", ctx)),
            artifact=ArtifactInfo.from_dict(_require(data, "artifact", ctx)),
        )


@dataclass(frozen=True, slots=True)
class Port:
    """A named, schema-bound input or output port (§4)."""

    name: str
    schema: str
    delivery: str | None = None  # only meaningful on inputs, e.g. "at-least-once"

    @classmethod
    def from_dict(cls, data: dict[str, Any], ctx: str) -> Port:
        return cls(
            name=_require(data, "name", ctx),
            schema=_require(data, "schema", ctx),
            delivery=data.get("delivery"),
        )


@dataclass(frozen=True, slots=True)
class EffectDecl:
    name: str
    schema: str
    effect_class: EffectClass
    default_approval: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EffectDecl:
        ctx = "contract.effects[]"
        return cls(
            name=_require(data, "name", ctx),
            schema=_require(data, "schema", ctx),
            effect_class=EffectClass.parse(_require(data, "class", ctx)),
            default_approval=data.get("defaultApproval", "human"),
        )


@dataclass(frozen=True, slots=True)
class Contract:
    promise: str
    inputs: tuple[Port, ...]
    outputs: tuple[Port, ...]
    effects: tuple[EffectDecl, ...]
    instruction_fields: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Contract:
        ctx = "contract"
        inputs = tuple(Port.from_dict(p, "contract.inputs[]") for p in data.get("inputs", []))
        outputs = tuple(Port.from_dict(p, "contract.outputs[]") for p in data.get("outputs", []))
        if not inputs:
            raise ManifestError(f"{ctx}: at least one input port is required")
        if not outputs:
            raise ManifestError(f"{ctx}: at least one output port is required")
        # Additional instruction-position field names for this chip's outputs
        # (§8.2). A host enforces the UNION of chip.taint.DEFAULT_INSTRUCTION_KEYS
        # and these. Must be a list of non-empty strings.
        raw_fields = data.get("instructionFields", [])
        if not isinstance(raw_fields, list):
            raise ManifestError(f"{ctx}.instructionFields must be a list of strings")
        instruction_fields = []
        for f in raw_fields:
            if not isinstance(f, str) or not f.strip():
                raise ManifestError(
                    f"{ctx}.instructionFields entries must be non-empty strings, got {f!r}"
                )
            instruction_fields.append(f)
        return cls(
            promise=_require(data, "promise", ctx),
            inputs=inputs,
            outputs=outputs,
            effects=tuple(EffectDecl.from_dict(e) for e in data.get("effects", [])),
            instruction_fields=tuple(instruction_fields),
        )


@dataclass(frozen=True, slots=True)
class Stage:
    """One internal implementation step (§7, §10). Non-contractual by default."""

    id: str
    kind: str  # "code" | "gateway" | "adapter" | "policy"
    determinism: str  # "deterministic" | "probabilistic"
    request_schema: str | None = None
    result_schema: str | None = None
    profile: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Stage:
        ctx = "implementation.stages[]"
        kind = _require(data, "kind", ctx)
        if kind == "somm":  # deprecated alias for the public "gateway" kind
            kind = "gateway"
        if kind not in ("code", "gateway", "adapter", "policy"):
            raise ManifestError(
                f"{ctx}: unknown stage kind {kind!r}; expected code|gateway|adapter|policy"
            )
        return cls(
            id=_require(data, "id", ctx),
            kind=kind,
            determinism=data.get("determinism", "deterministic"),
            request_schema=data.get("requestSchema"),
            result_schema=data.get("resultSchema"),
            profile=data.get("profile"),
        )


@dataclass(frozen=True, slots=True)
class Implementation:
    runtime: str
    entrypoint: str
    stages_are_contractual: bool
    stages: tuple[Stage, ...]
    # The model generation the judgment-stage artifacts were tuned for, e.g.
    # "provider/model-2026-05" (§7.1/§10.2). Optional; a build output, not a
    # contract term — on a model-generation change the judgment stage SHOULD be
    # re-derived from the fixtures rather than hand-patched.
    authored_against: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Implementation:
        ctx = "implementation"
        stages = tuple(Stage.from_dict(s) for s in data.get("stages", []))
        gateway_stages = [s for s in stages if s.kind == "gateway"]
        if len(gateway_stages) > 1:
            ids = ", ".join(s.id for s in gateway_stages)
            raise ManifestError(
                f"{ctx}: at most one gateway stage is allowed (§10.3), found {len(gateway_stages)}"
                f": {ids}"
            )
        for gs in gateway_stages:
            if not gs.request_schema or not gs.result_schema:
                raise ManifestError(
                    f"{ctx}: gateway stage {gs.id!r} MUST declare requestSchema and resultSchema"
                    " (§10.2)"
                )
        authored_against = data.get("authoredAgainst")
        if authored_against is not None and (
            not isinstance(authored_against, str) or not authored_against.strip()
        ):
            raise ManifestError(f"{ctx}.authoredAgainst must be a non-empty model-generation string")
        return cls(
            runtime=_require(data, "runtime", ctx),
            entrypoint=_require(data, "entrypoint", ctx),
            stages_are_contractual=bool(data.get("stagesAreContractual", False)),
            stages=stages,
            authored_against=authored_against,
        )

    @property
    def implementation_class(self) -> str:
        """``"hybrid"`` if a gateway stage exists, else ``"deterministic"`` (§10.3)."""
        return "hybrid" if any(s.kind == "gateway" for s in self.stages) else "deterministic"


@dataclass(frozen=True, slots=True)
class Dependencies:
    capabilities: tuple[str, ...]
    adapters: tuple[str, ...]
    secrets: tuple[str, ...]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Dependencies:
        secrets = data.get("secrets", [])
        if secrets:
            raise ManifestError(
                "dependencies.secrets MUST be empty in v1 (§3.1); the pilot is credential-free"
            )
        return cls(
            capabilities=tuple(data.get("capabilities", [])),
            adapters=tuple(data.get("adapters", [])),
            secrets=(),
        )


@dataclass(frozen=True, slots=True)
class Authority:
    maximum_effect_class: EffectClass
    prohibited: tuple[str, ...]
    approval_mode: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Authority:
        ctx = "authority"
        approval = data.get("approval", {})
        return cls(
            maximum_effect_class=EffectClass.parse(_require(data, "maximumEffectClass", ctx)),
            prohibited=tuple(data.get("prohibited", [])),
            approval_mode=approval.get("mode", "most-restrictive-wins"),
        )


@dataclass(frozen=True, slots=True)
class Retry:
    scope: str
    attempts: int
    backoff: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Retry:
        return cls(
            scope=data.get("scope", "pre-effect-stage"),
            attempts=int(data.get("attempts", 0)),
            backoff=data.get("backoff", "exponential"),
        )


@dataclass(frozen=True, slots=True)
class Limits:
    timeout: str | None = None
    max_activations_per_hour: int | None = None
    max_effects_per_day: int | None = None
    cooldown: str | None = None
    model_budget_usd: float | None = None
    retry: Retry | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Limits:
        retry = data.get("retry")
        return cls(
            timeout=data.get("timeout"),
            max_activations_per_hour=data.get("maxActivationsPerHour"),
            max_effects_per_day=data.get("maxEffectsPerDay"),
            cooldown=data.get("cooldown"),
            model_budget_usd=data.get("modelBudgetUsd"),
            retry=Retry.from_dict(retry) if retry else None,
        )


@dataclass(frozen=True, slots=True)
class Security:
    input_trust: str
    network_allowlist: tuple[str, ...]
    filesystem: str
    prompt_injection_policy: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Security:
        return cls(
            input_trust=data.get("inputTrust", "hostile"),
            network_allowlist=tuple(data.get("networkAllowlist", [])),
            filesystem=data.get("filesystem", "none"),
            prompt_injection_policy=data.get("promptInjectionPolicy", "evidence-only"),
        )


@dataclass(frozen=True, slots=True)
class EvaluationDecl:
    fixtures: str
    heldout_suite: str | None
    results: tuple[dict[str, Any], ...]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvaluationDecl:
        return cls(
            fixtures=data.get("fixtures", "fixtures/"),
            heldout_suite=data.get("heldoutSuite"),
            results=tuple(data.get("results", [])),
        )


@dataclass(frozen=True, slots=True)
class Compatibility:
    chip_spec: str
    required_host_capabilities: tuple[str, ...]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Compatibility:
        ctx = "compatibility"
        chip_spec = _require(data, "chipSpec", ctx)
        # Validate the range parses; membership is a host concern.
        satisfies_range("0.1.0", chip_spec)
        return cls(
            chip_spec=chip_spec,
            required_host_capabilities=tuple(data.get("requiredHostCapabilities", [])),
        )


@dataclass(frozen=True, slots=True)
class Hints:
    """Non-contractual, accretive annotations keyed by surface/harness (§7, 0.5.0).

    Hints sit **outside** the compatibility contract — exactly like internal
    stages. They carry harness-specific phrasings and per-model-generation notes
    (``hints.harnesses.<name>.phrasing``, ``hints.models.<generation>.notes``)
    that rot as model generations advance, and they may be pruned without a
    version bump (see :func:`prune_hints`). Shape is validated *loosely*: a
    mapping of category -> (name -> entry), where each **entry** is an object
    carrying a non-empty ``authoredAgainst`` model-generation string. Anything
    else about an entry is free-form.

    ``categories`` preserves the raw nested dict so a host can read arbitrary
    keys; :meth:`entries` iterates ``(category, name, entry)`` triples.
    """

    categories: dict[str, dict[str, dict[str, Any]]]

    @classmethod
    def from_dict(cls, data: Any) -> Hints:
        ctx = "hints"
        if not isinstance(data, dict):
            raise ManifestError(f"{ctx} must be an object of category -> (name -> entry)")
        categories: dict[str, dict[str, dict[str, Any]]] = {}
        for category, names in data.items():
            if not isinstance(names, dict):
                raise ManifestError(f"{ctx}.{category} must be an object of name -> entry")
            entries: dict[str, dict[str, Any]] = {}
            for name, entry in names.items():
                if not isinstance(entry, dict):
                    raise ManifestError(f"{ctx}.{category}.{name} must be an entry object")
                authored = entry.get("authoredAgainst")
                if not isinstance(authored, str) or not authored.strip():
                    raise ManifestError(
                        f"{ctx}.{category}.{name} must carry a non-empty 'authoredAgainst' "
                        "model-generation string (every hint entry is generation-tagged, §7)"
                    )
                entries[name] = dict(entry)
            categories[category] = entries
        return cls(categories=categories)

    def entries(self) -> list[tuple[str, str, dict[str, Any]]]:
        """Every hint entry as an ordered ``(category, name, entry)`` triple."""
        return [
            (category, name, entry)
            for category, names in self.categories.items()
            for name, entry in names.items()
        ]

    def to_dict(self) -> dict[str, Any]:
        return {c: {n: dict(e) for n, e in names.items()} for c, names in self.categories.items()}


def prune_hints(manifest_dict: dict[str, Any], older_than_generation: str) -> dict[str, Any]:
    """Return a copy of ``manifest_dict`` with stale hint entries removed (§7, 0.5.0).

    A hint entry is dropped when its ``authoredAgainst`` model generation sorts
    strictly *before* ``older_than_generation``. Model-generation strings are
    compared lexically (like cursor values in :mod:`chip.state`), so they should
    be written to sort chronologically — e.g. ``"provider/model-2026-05"``.
    Pruning a hint is explicitly **not** a version bump: hints are outside the
    compatibility contract.

    The input dict is not mutated. Categories left empty after pruning are
    dropped, and a manifest with no ``hints`` is returned unchanged.
    """
    if not isinstance(older_than_generation, str) or not older_than_generation.strip():
        raise ManifestError("prune_hints: older_than_generation must be a non-empty string")
    result = copy.deepcopy(manifest_dict)
    hints = result.get("hints")
    if not isinstance(hints, dict):
        return result
    pruned: dict[str, Any] = {}
    for category, names in hints.items():
        if not isinstance(names, dict):
            continue
        kept = {
            name: entry
            for name, entry in names.items()
            if not (
                isinstance(entry, dict)
                and isinstance(entry.get("authoredAgainst"), str)
                and entry["authoredAgainst"] < older_than_generation
            )
        }
        if kept:
            pruned[category] = kept
    if pruned:
        result["hints"] = pruned
    else:
        result.pop("hints", None)
    return result


@dataclass(frozen=True, slots=True)
class ChipManifest:
    """A full chip manifest (§7.1)."""

    api_version: str
    kind: str
    metadata: Metadata
    contract: Contract
    state: StateContract | None
    implementation: Implementation
    dependencies: Dependencies
    authority: Authority
    limits: Limits
    security: Security
    evaluation: EvaluationDecl
    compatibility: Compatibility
    hints: Hints | None = None
    raw: dict[str, Any] = field(default_factory=dict, compare=False)

    @property
    def implementation_class(self) -> str:
        return self.implementation.implementation_class

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ChipManifest:
        api_version = data.get("apiVersion", SPEC_VERSION)
        if api_version != SPEC_VERSION:
            raise ManifestError(
                f"apiVersion {api_version!r} unsupported; this library implements {SPEC_VERSION}"
            )
        kind = data.get("kind", "Chip")
        if kind != "Chip":
            raise ManifestError(f"kind {kind!r} unsupported; expected 'Chip'")
        state_block = data.get("state")
        try:
            state = StateContract.from_dict(state_block) if state_block else None
        except StateError as exc:
            # Surface state-contract violations as a manifest-level error.
            raise ManifestError(str(exc)) from exc
        # A partitioned(keyField) chip's key MUST name a signal envelope field (§9).
        if state is not None and state.partition_key is not None:
            from chip.envelopes import SIGNAL_ENVELOPE_FIELDS

            if state.partition_key not in SIGNAL_ENVELOPE_FIELDS:
                allowed = ", ".join(sorted(SIGNAL_ENVELOPE_FIELDS))
                raise ManifestError(
                    f"state concurrency partition key {state.partition_key!r} is not a declared "
                    f"signal field (§8.1/§9); expected one of: {allowed}"
                )
        contract = Contract.from_dict(_require(data, "contract", "manifest"))
        authority = Authority.from_dict(_require(data, "authority", "manifest"))
        # Every declared effect must sit at or below the authority ceiling.
        for eff in contract.effects:
            if eff.effect_class > authority.maximum_effect_class:
                raise ManifestError(
                    f"effect {eff.name!r} class '{eff.effect_class.label}' exceeds authority "
                    f"ceiling '{authority.maximum_effect_class.label}'"
                )
        return cls(
            api_version=api_version,
            kind=kind,
            metadata=Metadata.from_dict(_require(data, "metadata", "manifest")),
            contract=contract,
            state=state,
            implementation=Implementation.from_dict(_require(data, "implementation", "manifest")),
            dependencies=Dependencies.from_dict(data.get("dependencies", {})),
            authority=authority,
            limits=Limits.from_dict(data.get("limits", {})),
            security=Security.from_dict(data.get("security", {})),
            evaluation=EvaluationDecl.from_dict(data.get("evaluation", {})),
            compatibility=Compatibility.from_dict(_require(data, "compatibility", "manifest")),
            hints=Hints.from_dict(data["hints"]) if data.get("hints") is not None else None,
            raw=data,
        )

    def schema_refs(self) -> list[str]:
        """Every schema reference the manifest declares, de-duplicated in order."""
        refs: list[str] = []

        def add(ref: str | None) -> None:
            if ref and ref not in refs:
                refs.append(ref)

        for port in (*self.contract.inputs, *self.contract.outputs):
            add(port.schema)
        for eff in self.contract.effects:
            add(eff.schema)
        if self.state is not None:
            add(self.state.schema)
        for stage in self.implementation.stages:
            add(stage.request_schema)
            add(stage.result_schema)
        return refs


def load_manifest(data: dict[str, Any]) -> ChipManifest:
    """Validate a manifest dict and return a :class:`ChipManifest` (raises on error)."""
    if not isinstance(data, dict):
        raise ManifestError(f"manifest must be a JSON object, got {type(data).__name__}")
    return ChipManifest.from_dict(data)


def split_schema_ref(ref: str) -> tuple[str, str | None]:
    """Split a schema reference ``path/name.json@N`` into ``(file_path, version)``.

    A schema reference names both a file *and* a schema version: the on-disk file
    is ``path/name.json``; the ``@N`` suffix pins the schema version. The full ref
    string (including ``@N``) is what circuit port compatibility matches on — two
    ports are compatible only when their **whole** refs are equal (same file AND
    same version, §11). This helper resolves only the file half, so a package can
    ship ``schemas/name.json`` while its manifest declares ``schemas/name.json@1``.

    A ref with no ``@`` returns ``(ref, None)``. The ``@`` must follow the ``.json``
    extension; an ``@`` earlier in the path is treated as part of the file name.
    """
    marker = ".json@"
    idx = ref.rfind(marker)
    if idx == -1:
        return ref, None
    file_path = ref[: idx + len(".json")]
    version = ref[idx + len(marker):]
    if not version:
        raise ManifestError(f"schema ref {ref!r} has an empty version after '@'")
    return file_path, version


def load_chip_package(package_dir: str | Path) -> tuple[ChipManifest, dict[str, Path]]:
    """Load ``chip.json`` from a package directory and resolve its schema paths.

    Returns ``(manifest, resolved_schemas)`` where ``resolved_schemas`` maps each
    declared schema reference — the **full** ``path/name.json@N`` string — to the
    absolute :class:`~pathlib.Path` of its on-disk file ``path/name.json``. The
    version suffix pins the schema version for port compatibility but is not part
    of the file name (see :func:`split_schema_ref`). A reference whose file does
    not exist raises :class:`ManifestError` — a package must ship the schemas it
    declares (§7).
    """
    root = Path(package_dir)
    manifest_path = root / "chip.json"
    if not manifest_path.is_file():
        raise ManifestError(f"no chip.json found at package root {root}")
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ManifestError(f"chip.json is not valid JSON: {exc}") from exc
    manifest = load_manifest(data)
    resolved: dict[str, Path] = {}
    for ref in manifest.schema_refs():
        file_path, _version = split_schema_ref(ref)
        schema_path = (root / file_path).resolve()
        if not schema_path.is_file():
            raise ManifestError(
                f"declared schema {ref!r} not found at {schema_path} (package must ship its schemas)"
            )
        # Key on the FULL ref (with @version) so callers matching port refs keep
        # the version; the value is the resolved versionless file.
        resolved[ref] = schema_path
    return manifest, resolved
