"""Host conformance kit for the chip contract (§14, §22).

A host proves it enforces the chip contract by implementing
:class:`~chip.conformance.hostkit.HostDriver` and running the ``check_*``
functions in :mod:`chip.conformance.hostkit` against it. The checks raise
:class:`AssertionError` with precise text, so any test framework — or a plain
script — can drive them. The kit imports stdlib only.
"""

from __future__ import annotations

from chip.conformance.hostkit import (
    HostDriver,
    RunReport,
    Scenario,
    check_at_least_once_single_effect,
    check_dispatched_effects_carry_receipt_refs,
    check_duplicate_produces_no_effects,
    check_invalid_judgment_fails_closed,
    check_pause_and_revoke_produce_receipts,
    check_quiet_produces_no_effects,
    check_undeclared_capability_denied,
    check_unevaluated_tuple_capped_at_observe,
    run_all,
)

__all__ = [
    "HostDriver",
    "RunReport",
    "Scenario",
    "check_at_least_once_single_effect",
    "check_dispatched_effects_carry_receipt_refs",
    "check_duplicate_produces_no_effects",
    "check_invalid_judgment_fails_closed",
    "check_pause_and_revoke_produce_receipts",
    "check_quiet_produces_no_effects",
    "check_undeclared_capability_denied",
    "check_unevaluated_tuple_capped_at_observe",
    "run_all",
]
