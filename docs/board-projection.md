<!-- Moved out of spec/chip-spec.md in spec 0.6. The specification is normative
     material only: what a host must implement to interoperate. -->

# Board projection and steering

How an owning system should surface chip state on its existing board. No host implements this to interoperate, so it is guidance, not contract.

The owning system owns installation and project-operation steering. Its existing
board/decision surface should project chip/circuit state through the owning
system's existing decision-card and guarded-action contracts rather than
acquiring a chip-specific state machine. The originating research service
supplies evidence-linked recommendations and learns from outcomes; it does not
command the board. Agent surfaces see thin wrappers, receipts, and typed
decisions, not host credentials or canonical installation state.

The board may show freshness, quiet/finding/needs-input/failed state, evidence,
cost, proposed effects, and pause/revoke/re-run actions. Canonical state remains
with Fab and the owning system. Prose may accompany a guarded action but cannot
mutate state without a validated action and receipt.
