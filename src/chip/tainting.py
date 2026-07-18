"""Field-level, transitively-propagated taint for hostile-sourced values.

Implements chip.spec/v0alpha1 §8.2: "Trust classification is transitive. Every
response field derived from hostile input MUST retain a taint and provenance
marker. Quoted source spans MUST be structurally separate from chip-authored
assessment rather than interpolated into instruction-position prose ... Removing
taint is a policy decision with its own evidence and receipt, not a formatting
operation."

A tainted value is a plain dict so it survives JSON round-trips unchanged::

    {"value": <payload>, "taint": {"trust": "hostile", "source": "...",
                                    "via": ["...", ...]}}

The ``via`` chain records the derivation lineage so a downstream adapter can
explain *why* a field is tainted. Nothing here interprets the payload; taint is
metadata a host/adapter honours, not executable content.
"""

from __future__ import annotations

from typing import Any

from chip.errors import EnvelopeError

# Trust classifications, least trusted first. "hostile" is the §8.1 default for
# retrieved content.
TRUST_LEVELS = ("hostile", "untrusted", "attested", "trusted")

# Field names a host MUST treat as instruction-position when enforcing §8.2 —
# i.e. keys whose values are interpreted as model/host instruction prose and
# therefore MUST NOT carry tainted (hostile-derived) content. This is the
# spec-defined default key set; a chip MAY extend it for its own outputs via the
# manifest's ``contract.instructionFields`` (see :class:`chip.manifest.Contract`).
# A conforming host enforces the *union* of this default set and any
# manifest-declared fields. The set is intentionally broad and covers the common
# spellings so a host does not have to invent its own heuristic.
DEFAULT_INSTRUCTION_KEYS = (
    "instruction",
    "instructions",
    "directive",
    "command",
    "system",
    "system_prompt",
    "systemPrompt",
    "prompt",
)


def taint(value: Any, trust: str, source: str, via: list[str] | None = None) -> dict[str, Any]:
    """Wrap ``value`` in a taint marker recording its trust level and origin.

    ``trust`` must be one of :data:`TRUST_LEVELS`. ``source`` is the origin
    coordinate (a signal id, adapter name, URL, ...). ``via`` is the optional
    derivation chain; it defaults to ``[source]``.
    """
    if trust not in TRUST_LEVELS:
        allowed = ", ".join(TRUST_LEVELS)
        raise EnvelopeError(f"unknown trust level {trust!r}; expected one of: {allowed}")
    if not source:
        raise EnvelopeError("taint requires a non-empty source coordinate")
    return {
        "value": value,
        "taint": {"trust": trust, "source": source, "via": list(via) if via else [source]},
    }


def is_tainted(obj: Any) -> bool:
    """True when ``obj`` is a taint-marked value (a dict with ``value``+``taint``)."""
    return (
        isinstance(obj, dict)
        and "taint" in obj
        and "value" in obj
        and isinstance(obj["taint"], dict)
        and "trust" in obj["taint"]
    )


def taint_of(obj: Any) -> dict[str, Any] | None:
    """Return the taint marker of ``obj`` if it is tainted, else ``None``."""
    return obj["taint"] if is_tainted(obj) else None


def propagate(parent_taint: dict[str, Any], value: Any, via: str | None = None) -> dict[str, Any]:
    """Derive a new tainted value that inherits ``parent_taint``'s trust.

    Taint is transitive: a field computed from a tainted field is at least as
    tainted as its parent. The new value keeps the parent trust and source and
    extends the ``via`` chain (appending ``via`` when given). Raises
    :class:`EnvelopeError` if ``parent_taint`` is not a valid marker.
    """
    if not (isinstance(parent_taint, dict) and "trust" in parent_taint):
        raise EnvelopeError("propagate requires a valid parent taint marker")
    chain = list(parent_taint.get("via", []))
    if via:
        chain.append(via)
    return {
        "value": value,
        "taint": {
            "trust": parent_taint["trust"],
            "source": parent_taint.get("source", "unknown"),
            "via": chain,
        },
    }


def taint_gateway_result(result: Any, parent_taint: dict[str, Any]) -> Any:
    """Taint every string leaf of a gateway result as hostile-derived (§8.2).

    Model output derived from hostile input is itself hostile-derived: §8.2
    transitivity means the structured result a gateway returns for a request that
    contained tainted content MUST inherit that taint before it re-enters the
    implementation. A host calls this with ``parent_taint`` set to the marker of
    the request's *most-hostile* input; every string leaf of ``result`` is then
    wrapped as a tainted ``{value, taint}`` marker whose trust and source are
    inherited and whose ``via`` chain is the parent's chain with ``"gateway"``
    appended. Structure is preserved: dicts and lists are walked; numbers,
    booleans, and ``None`` are left as bare scalars; an already-tainted value is
    left untouched (never double-wrapped). Raises :class:`EnvelopeError` if
    ``parent_taint`` is not a valid marker.
    """
    if not (isinstance(parent_taint, dict) and "trust" in parent_taint):
        raise EnvelopeError("taint_gateway_result requires a valid parent taint marker")
    trust = parent_taint["trust"]
    source = parent_taint.get("source", "unknown")
    chain = [*parent_taint.get("via", []), "gateway"]

    def _wrap(obj: Any) -> Any:
        if is_tainted(obj):
            return obj
        if isinstance(obj, str):
            return {"value": obj, "taint": {"trust": trust, "source": source, "via": list(chain)}}
        if isinstance(obj, dict):
            return {key: _wrap(val) for key, val in obj.items()}
        if isinstance(obj, list):
            return [_wrap(val) for val in obj]
        return obj

    return _wrap(result)


def quote_span(text: str, source_taint: dict[str, Any]) -> dict[str, Any]:
    """Produce a structurally-separate quoted span (never string-interpolated).

    §8.2 forbids splicing hostile source text into instruction-position prose.
    A quoted span is therefore its own object a renderer places in a quote slot;
    it can never be mistaken for chip-authored instruction because it is not a
    bare string. The span carries its originating taint so trust survives to the
    final adapter.
    """
    if not (isinstance(source_taint, dict) and "trust" in source_taint):
        raise EnvelopeError("quote_span requires a valid source taint marker")
    return {
        "kind": "quoted_span",
        "quoted_text": text,
        "taint": {
            "trust": source_taint["trust"],
            "source": source_taint.get("source", "unknown"),
            "via": list(source_taint.get("via", [])),
        },
    }


def _walk_tainted(obj: Any, path: str, found: list[str]) -> None:
    """Collect the paths of every tainted field reachable from ``obj``."""
    if is_tainted(obj):
        found.append(path or "<root>")
        return
    if isinstance(obj, dict):
        # A quoted span is structurally separate content, not instruction text —
        # but it is still tainted material, so it counts.
        if obj.get("kind") == "quoted_span" and "taint" in obj:
            found.append(path or "<root>")
            return
        for key, val in obj.items():
            _walk_tainted(val, f"{path}.{key}" if path else str(key), found)
    elif isinstance(obj, list):
        for idx, val in enumerate(obj):
            _walk_tainted(val, f"{path}[{idx}]", found)


def assert_untainted_for_instructions(obj: Any) -> None:
    """Raise if any tainted field would land in instruction position.

    Callers pass the object that is about to be used as model/host instruction
    prose (a prompt fragment, a policy directive, ...). If any field within it
    still carries a taint marker or is a quoted span, this raises
    :class:`EnvelopeError` naming every offending path — hostile content must be
    quoted structurally, never used as instruction. See §8.2.
    """
    found: list[str] = []
    _walk_tainted(obj, "", found)
    if found:
        raise EnvelopeError(
            "tainted content in instruction position at: " + ", ".join(sorted(found))
        )


def remove_taint(obj: Any, policy_receipt_ref: str) -> Any:
    """Strip a taint marker, but only against a non-empty policy receipt ref.

    §8.2: "Removing taint is a policy decision with its own evidence and
    receipt, not a formatting operation." This helper enforces that discipline —
    it refuses to unwrap a tainted value unless the caller supplies a real
    receipt reference authorising the removal. Returns the inner ``value``.
    Non-tainted objects are returned unchanged (still requiring the receipt, so
    the caller cannot use this as a cheap identity function on hostile data).
    """
    if not policy_receipt_ref or not str(policy_receipt_ref).strip():
        raise EnvelopeError(
            "removing taint requires a non-empty policy receipt reference"
        )
    if is_tainted(obj):
        return obj["value"]
    return obj
