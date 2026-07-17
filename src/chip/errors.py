"""Error taxonomy for the chip contract library.

Every loader and validator in this package raises a subclass of
:class:`ChipError` with a precise, operator-facing message that names the
offending field or path. Callers catch :class:`ChipError` to distinguish a
contract violation from an ordinary Python exception. Each class carries a
canonical ``code`` so error surfaces stay stable across versions.

See chip.spec/v0alpha1 §7 (package contract) and §13 (receipts) for the
kinds of failures modelled here.
"""

from __future__ import annotations


class ChipError(Exception):
    """Base for every error this package raises."""

    code: str = "CHIP_ERROR"


class ManifestError(ChipError):
    """A chip manifest (chip.json) is missing, malformed, or violates §7/§3.1."""

    code = "CHIP_MANIFEST_ERROR"


class CircuitError(ChipError):
    """A circuit document violates the §11 composition rules."""

    code = "CHIP_CIRCUIT_ERROR"


class BindingError(ChipError):
    """A binding or installation violates §12 (secret refs, identity, authority)."""

    code = "CHIP_BINDING_ERROR"


class EnvelopeError(ChipError):
    """A signal, response, or effect request violates §8, or a key derivation is unsafe."""

    code = "CHIP_ENVELOPE_ERROR"


class AuthorityError(ChipError):
    """An effect exceeds its authority ceiling, is prohibited, or fails closed (§14)."""

    code = "CHIP_AUTHORITY_ERROR"


class StateError(ChipError):
    """A state contract or cursor advance violates §9 (monotonicity, scope, concurrency)."""

    code = "CHIP_STATE_ERROR"


class ReceiptError(ChipError):
    """A receipt is missing a required field or mutates append-only history (§13)."""

    code = "CHIP_RECEIPT_ERROR"


class FixtureError(ChipError):
    """A fixture package is malformed or fails the §7/§21 coverage requirement."""

    code = "CHIP_FIXTURE_ERROR"


class EvaluationError(ChipError):
    """An evaluated-tuple record or ledger operation violates §10.2/§21."""

    code = "CHIP_EVALUATION_ERROR"


class EnvironmentProfileError(ChipError):
    """An environment profile is malformed or a binding/profile resolution fails (§12)."""

    code = "CHIP_ENVIRONMENT_ERROR"


class LifecycleError(ChipError):
    """A lifecycle-telemetry event violates the mint/transfer/split/merge/optimize/retire schema."""

    code = "CHIP_LIFECYCLE_ERROR"


class CandidateError(ChipError):
    """A candidate-ledger entry is malformed (the side-activity capture convention)."""

    code = "CHIP_CANDIDATE_ERROR"
