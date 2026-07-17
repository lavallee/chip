"""Circuit composition model and validator (§11).

A circuit is a versioned composition document — it references chip contracts and
pinned implementations and wires their typed ports; it is *not* a copy of the
implementations. Version 1 circuits are strictly limited (§3.1, §11):

* linear, at most three chips;
* no nesting, feedback edge, fork, or join — a connection may only run from
  chip *i*'s output to chip *i+1*'s input, or to a terminal;
* no self-reference; and
* a port connection matches only when the two ports declare the **same schema
  name and version** — sharing a structural shape is not enough (§11).

Effective authority is computed **per effect-requesting chip**, not min-ed over
the whole circuit (§12). The circuit ceiling is a *cap*: a chip whose own maximum
sits below it stays low, and a no-effect chip's ``observe`` ceiling does **not**
constrain a downstream chip. :func:`validate_circuit` returns a
:class:`CircuitAuthority` carrying the circuit ceiling plus a per-chip
effective-ceiling map (each chip's own maximum intersected with the circuit cap).
A chip whose *declared* effect class exceeds the circuit ceiling makes the circuit
unsatisfiable and is a hard error.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from chip.authority import EffectClass, effective_authority
from chip.errors import CircuitError
from chip.manifest import ChipManifest

TERMINAL = "terminal"
MAX_CHIPS = 3


@dataclass(frozen=True, slots=True)
class ChipRef:
    """A pinned reference to a chip contract + implementation inside a circuit."""

    ref: str  # local node id used by connections
    chip_id: str
    contract_version: str
    implementation: str  # implementation coordinate or digest

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ChipRef:
        def req(key: str) -> Any:
            if not data.get(key):
                raise CircuitError(f"circuit chip ref: missing required field {key!r}")
            return data[key]

        return cls(
            ref=req("ref"),
            chip_id=req("chip"),
            contract_version=req("contractVersion"),
            implementation=req("implementation"),
        )


@dataclass(frozen=True, slots=True)
class Connection:
    """A typed port connection between two circuit nodes (or to the terminal)."""

    from_chip: str
    from_port: str
    to_chip: str  # a chip ref, or TERMINAL
    to_port: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Connection:
        def req(key: str) -> Any:
            if not data.get(key):
                raise CircuitError(f"circuit connection: missing required field {key!r}")
            return data[key]

        return cls(
            from_chip=req("fromChip"),
            from_port=req("fromPort"),
            to_chip=req("toChip"),
            to_port=data.get("toPort"),
        )


@dataclass(frozen=True, slots=True)
class Circuit:
    """A version-1 circuit composition document (§11)."""

    id: str
    version: str
    chips: tuple[ChipRef, ...]
    connections: tuple[Connection, ...]
    activation_signal_type: str
    authority_ceiling: EffectClass
    shared_budgets: dict[str, Any] = field(default_factory=dict)
    error_policy: dict[str, Any] = field(default_factory=dict)
    human_decision_points: tuple[str, ...] = ()
    state_ownership: dict[str, Any] = field(default_factory=dict)
    terminal_outcomes: tuple[str, ...] = ()
    quiet_outcomes: tuple[str, ...] = ()
    compatibility: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Circuit:
        def req(key: str) -> Any:
            if not data.get(key):
                raise CircuitError(f"circuit: missing required field {key!r}")
            return data[key]

        return cls(
            id=req("id"),
            version=req("version"),
            chips=tuple(ChipRef.from_dict(c) for c in data.get("chips", [])),
            connections=tuple(Connection.from_dict(c) for c in data.get("connections", [])),
            activation_signal_type=req("activationSignalType"),
            authority_ceiling=EffectClass.parse(req("authorityCeiling")),
            shared_budgets=data.get("sharedBudgets", {}),
            error_policy=data.get("errorPolicy", {}),
            human_decision_points=tuple(data.get("humanDecisionPoints", [])),
            state_ownership=data.get("stateOwnership", {}),
            terminal_outcomes=tuple(data.get("terminalOutcomes", [])),
            quiet_outcomes=tuple(data.get("quietOutcomes", [])),
            compatibility=data.get("compatibility", {}),
        )


@dataclass(frozen=True, slots=True)
class CircuitAuthority:
    """The authority result of validating a circuit (§12).

    ``circuit_ceiling`` is the circuit's declared cap. ``per_chip`` maps each
    :attr:`ChipRef.ref` to that chip's *static* effective ceiling — its own
    declared maximum intersected with the circuit ceiling. It is deliberately
    **not** a single min over every member: a no-effect chip's low ceiling never
    caps a downstream effect-requesting chip. At enforcement time a host further
    intersects a chip's entry with binding ∩ host ∩ approval (see
    :func:`chip.binding.compute_effective_authority`).
    """

    circuit_ceiling: EffectClass
    per_chip: dict[str, EffectClass] = field(default_factory=dict)


def _output_schema(manifest: ChipManifest, port_name: str, ref: str) -> str:
    for port in manifest.contract.outputs:
        if port.name == port_name:
            return port.schema
    raise CircuitError(f"chip {ref!r} declares no output port named {port_name!r}")


def _input_schema(manifest: ChipManifest, port_name: str, ref: str) -> str:
    for port in manifest.contract.inputs:
        if port.name == port_name:
            return port.schema
    raise CircuitError(f"chip {ref!r} declares no input port named {port_name!r}")


def validate_circuit(circuit: Circuit, manifests: dict[str, ChipManifest]) -> CircuitAuthority:
    """Validate a circuit against the §11 rules; return its :class:`CircuitAuthority`.

    ``manifests`` maps each :attr:`ChipRef.ref` to the resolved
    :class:`~chip.manifest.ChipManifest`. Raises :class:`CircuitError` on any
    structural violation (too many chips, missing manifest, feedback/self edge,
    schema-name mismatch) *or* when a chip declares an effect whose class exceeds
    the circuit ceiling (the circuit would be unsatisfiable — §12).

    On success returns a :class:`CircuitAuthority`: the circuit's declared ceiling
    plus a per-chip effective-ceiling map (each chip's own maximum ∩ the circuit
    ceiling). Authority is per effect-requesting chip; a sibling chip's ceiling
    does not constrain it.
    """
    if not circuit.chips:
        raise CircuitError(f"circuit {circuit.id!r} contains no chips")
    if len(circuit.chips) > MAX_CHIPS:
        raise CircuitError(
            f"circuit {circuit.id!r} has {len(circuit.chips)} chips; v1 allows at most {MAX_CHIPS}"
            " (§3.1/§11)"
        )

    # Node index by ref; detect duplicate refs.
    index_of: dict[str, int] = {}
    for i, cref in enumerate(circuit.chips):
        if cref.ref in index_of:
            raise CircuitError(f"circuit {circuit.id!r}: duplicate chip ref {cref.ref!r}")
        index_of[cref.ref] = i
        if cref.ref not in manifests:
            raise CircuitError(
                f"circuit {circuit.id!r}: no manifest supplied for chip ref {cref.ref!r}"
            )

    for conn in circuit.connections:
        if conn.from_chip not in index_of:
            raise CircuitError(
                f"circuit {circuit.id!r}: connection from unknown chip {conn.from_chip!r}"
            )
        if conn.to_chip == conn.from_chip:
            raise CircuitError(
                f"circuit {circuit.id!r}: self-referential connection on {conn.from_chip!r}"
                " (nesting/feedback forbidden, §11)"
            )
        from_idx = index_of[conn.from_chip]
        from_manifest = manifests[conn.from_chip]
        out_schema = _output_schema(from_manifest, conn.from_port, conn.from_chip)

        if conn.to_chip == TERMINAL:
            continue

        if conn.to_chip not in index_of:
            raise CircuitError(
                f"circuit {circuit.id!r}: connection to unknown chip {conn.to_chip!r}"
            )
        to_idx = index_of[conn.to_chip]
        # Linear-only: the sole permitted edge is chip i -> chip i+1 (§11).
        if to_idx <= from_idx:
            raise CircuitError(
                f"circuit {circuit.id!r}: backward/feedback edge {conn.from_chip!r} -> "
                f"{conn.to_chip!r} forbidden; v1 circuits are linear (§11)"
            )
        if to_idx != from_idx + 1:
            raise CircuitError(
                f"circuit {circuit.id!r}: non-adjacent edge {conn.from_chip!r} -> "
                f"{conn.to_chip!r} forbidden; connect only chip i to chip i+1 (§11)"
            )
        if not conn.to_port:
            raise CircuitError(
                f"circuit {circuit.id!r}: connection to {conn.to_chip!r} missing toPort"
            )
        in_schema = _input_schema(manifests[conn.to_chip], conn.to_port, conn.to_chip)
        # Match by schema NAME AND VERSION: compare the declared refs directly.
        if out_schema != in_schema:
            raise CircuitError(
                f"circuit {circuit.id!r}: port schema mismatch on "
                f"{conn.from_chip}.{conn.from_port} ({out_schema!r}) -> "
                f"{conn.to_chip}.{conn.to_port} ({in_schema!r}); structural shape is not enough,"
                " schema name and version must match (§11)"
            )

    # Per-chip effective ceiling = that chip's own maximum ∩ the circuit ceiling.
    # We do NOT min over every member: a no-effect chip's low ceiling must not cap
    # a downstream effect-requesting chip (§12).
    per_chip: dict[str, EffectClass] = {}
    for cref in circuit.chips:
        manifest = manifests[cref.ref]
        chip_max = manifest.authority.maximum_effect_class
        # A chip whose DECLARED effect exceeds the circuit ceiling is unsatisfiable.
        for eff in manifest.contract.effects:
            if eff.effect_class > circuit.authority_ceiling:
                raise CircuitError(
                    f"circuit {circuit.id!r}: chip {cref.ref!r} declares effect "
                    f"{eff.name!r} of class '{eff.effect_class.label}' exceeding the "
                    f"circuit ceiling '{circuit.authority_ceiling.label}'; the circuit "
                    "is unsatisfiable (§12)"
                )
        effective = effective_authority(chip_max, circuit.authority_ceiling)
        if effective is None:  # pragma: no cover - both inputs are non-None here
            raise CircuitError(f"circuit {circuit.id!r}: authority failed closed for {cref.ref!r}")
        per_chip[cref.ref] = effective
    return CircuitAuthority(circuit_ceiling=circuit.authority_ceiling, per_chip=per_chip)
