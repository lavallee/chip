# Changelog

All notable changes follow [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- Bindings may carry per-chip configuration under `chipParameters` (spec
  0.4.2): merged into the activation `config` beneath host-injected keys;
  secret literals rejected.

## [0.1.0] — 2026-07-17

### Added

- **Initial contract implementation**: the chip spec (`spec/chip-spec.md`,
  v0.4.1 of `chip.spec/v0alpha1`), the `chip` Python package (manifest,
  circuit, binding, envelope, taint, authority, state, receipt, and
  evaluation models with validation), and a host conformance kit with
  eight checks (quiet/duplicate no-effects, fail-closed judgment,
  at-least-once single effect, pause/revoke receipts, unevaluated-tuple
  observe cap, capability denial, receipt-ref back-fill).
- **Example chips**: `publication-attention` (hybrid, one gateway stage)
  and `bounded-recommendation` (deterministic), composed into the
  `publication-triage` linear circuit — proven end-to-end on the
  reference host (fab) with fixture-driven evaluation and human-gated
  effect approval.
- Zero runtime dependencies; optional `jsonschema` extra for port
  payload validation.

### Release status

- v0 experiment. One host (fab). The spec and library evolve together;
  the operational promise/port/state/effect/authority surface is the
  compatibility contract, per the spec's own versioning rules.
