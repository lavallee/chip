"""chip — the portable contract for versioned operational components.

This package is the *contract*, not a runtime: schema models, validation, pure
policy functions, receipt schemas, fixture loading, and a host conformance kit.
It performs no scheduling, subprocess management, gateway (LLM) calls, or
network I/O. The only optional dependency is ``jsonschema`` (guarded), used
solely to validate port payload documents when installed.

Names are exported lazily (mirroring somm's ``somm`` package) so importing
``chip`` stays cheap and free of import cycles. See chip.spec/v0alpha1 for the
normative contract these models implement.
"""

from __future__ import annotations

import importlib
from typing import Any

from chip.errors import (
    AuthorityError,
    BindingError,
    ChipError,
    CircuitError,
    EnvelopeError,
    EvaluationError,
    FixtureError,
    ManifestError,
    ReceiptError,
    StateError,
)
from chip.version import SPEC_VERSION, VERSION

# name -> (module, attribute)
_LAZY: dict[str, tuple[str, str]] = {
    # authority
    "EffectClass": ("chip.authority", "EffectClass"),
    "effective_authority": ("chip.authority", "effective_authority"),
    "most_restrictive_approval": ("chip.authority", "most_restrictive_approval"),
    "check_effect_allowed": ("chip.authority", "check_effect_allowed"),
    # manifest
    "ChipManifest": ("chip.manifest", "ChipManifest"),
    "load_manifest": ("chip.manifest", "load_manifest"),
    "load_chip_package": ("chip.manifest", "load_chip_package"),
    "satisfies_range": ("chip.manifest", "satisfies_range"),
    "parse_semver": ("chip.manifest", "parse_semver"),
    # envelopes
    "Signal": ("chip.envelopes", "Signal"),
    "Response": ("chip.envelopes", "Response"),
    "ResponseKind": ("chip.envelopes", "ResponseKind"),
    "NeedsInput": ("chip.envelopes", "NeedsInput"),
    "EffectRequest": ("chip.envelopes", "EffectRequest"),
    "TrustClass": ("chip.envelopes", "TrustClass"),
    "derive_effect_key": ("chip.envelopes", "derive_effect_key"),
    "PENDING_RECEIPT_REF": ("chip.envelopes", "PENDING_RECEIPT_REF"),
    # taint
    "DEFAULT_INSTRUCTION_KEYS": ("chip.taint", "DEFAULT_INSTRUCTION_KEYS"),
    "taint": ("chip.taint", "taint"),
    "taint_gateway_result": ("chip.taint", "taint_gateway_result"),
    "is_tainted": ("chip.taint", "is_tainted"),
    "propagate": ("chip.taint", "propagate"),
    "quote_span": ("chip.taint", "quote_span"),
    "assert_untainted_for_instructions": ("chip.taint", "assert_untainted_for_instructions"),
    "remove_taint": ("chip.taint", "remove_taint"),
    # state
    "StateContract": ("chip.state", "StateContract"),
    "Cursor": ("chip.state", "Cursor"),
    # receipts
    "AttentionReceipt": ("chip.receipts", "AttentionReceipt"),
    "JudgmentReceipt": ("chip.receipts", "JudgmentReceipt"),
    "Coordinates": ("chip.receipts", "Coordinates"),
    "validate_receipt": ("chip.receipts", "validate_receipt"),
    "build_attention_receipt": ("chip.receipts", "build_attention_receipt"),
    "build_judgment_receipt": ("chip.receipts", "build_judgment_receipt"),
    # evaluation
    "EvaluatedTuple": ("chip.evaluation", "EvaluatedTuple"),
    "EvaluationLedger": ("chip.evaluation", "EvaluationLedger"),
    # circuit
    "Circuit": ("chip.circuit", "Circuit"),
    "CircuitAuthority": ("chip.circuit", "CircuitAuthority"),
    "validate_circuit": ("chip.circuit", "validate_circuit"),
    # binding
    "Binding": ("chip.binding", "Binding"),
    "Installation": ("chip.binding", "Installation"),
    "compute_effective_authority": ("chip.binding", "compute_effective_authority"),
    # fixtures
    "Fixture": ("chip.fixtures", "Fixture"),
    "load_fixtures": ("chip.fixtures", "load_fixtures"),
    "validate_fixture_coverage": ("chip.fixtures", "validate_fixture_coverage"),
    # optional payload validation (guarded jsonschema)
    "validate_payload": ("chip.payloads", "validate_payload"),
    "jsonschema_available": ("chip.payloads", "jsonschema_available"),
}


def __getattr__(name: str) -> Any:
    target = _LAZY.get(name)
    if target is None:
        if name == "conformance":
            module = importlib.import_module("chip.conformance")
            globals()[name] = module
            return module
        raise AttributeError(f"module 'chip' has no attribute {name!r}")
    module = importlib.import_module(target[0])
    value = getattr(module, target[1])
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted([*globals().keys(), *_LAZY.keys(), "conformance"])


__all__ = [
    "VERSION",
    "SPEC_VERSION",
    # errors
    "ChipError",
    "ManifestError",
    "CircuitError",
    "BindingError",
    "EnvelopeError",
    "AuthorityError",
    "StateError",
    "ReceiptError",
    "FixtureError",
    "EvaluationError",
    # lazy
    *_LAZY.keys(),
    "conformance",
]
