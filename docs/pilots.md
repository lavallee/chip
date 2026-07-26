<!-- Moved out of spec/chip-spec.md in spec 0.6. The specification is normative
     material only: what a host must implement to interoperate. -->

# Pilots and graduation

The first two pilots and the bar each must clear before it graduates from disposable evaluation. Program management, not contract.

The first pilot is publication triage. It implements one attention chip and one
two-chip linear circuit in Fab's disposable, credential-free environment. Only
after its state, taint, receipt, and outcome loop is credible should the second
pilot exercise PR sign-off. Both compare against the existing skill/manual
approach at comparable operator time and model cost.

A pilot graduates from disposable evaluation when:

- the manifest and schemas validate;
- duplicate and quiet cases produce no effects;
- the bound implementation/Somm/model/harness tuple has passed its held-out
  suite, and a profile swap correctly drops the new tuple back to `observe`;
- an invalid or hostile model result fails closed;
- at-least-once delivery produces at most one effect request;
- target-side deduplication survives retry and state migration;
- attention and full-judgment receipts meet their declared retention contract;
- Fab capability-denial tests pass;
- a human can pause/revoke the installation;
- the output can be projected through the owning system's existing
  decision/action contracts without copying canonical evidence or creating a
  second board state machine; and
- the held-out result beats or matches a skill-only baseline at acceptable cost.

No package registry, visual builder, automatic promotion, or production binding
is required. A second host is deliberately not a pilot gate; it is a later
portability test with its own kill criterion.
