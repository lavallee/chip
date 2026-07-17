# Changelog

All notable changes follow [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [0.2.0] — 2026-07-17

Unreleased 0.2.0 work. Tracks spec 0.5.0: the delegation profile, the
three-layer resolution split, and two non-contractual manifest surfaces. All
additive; the schema identifier is unchanged (`chip.spec/v0alpha1`).

### Added

- **Manifest `hints` block** (spec 0.5.0 §7): optional, non-contractual,
  accretive annotations keyed by surface/harness, every entry carrying an
  `authoredAgainst` model generation. Parsed and exposed as `manifest.hints`;
  `prune_hints(manifest_dict, older_than_generation)` drops stale entries
  without a version bump.
- **`implementation.authoredAgainst`** (spec 0.5.0 §7.1/§10.2): the model
  generation the judgment-stage artifacts were tuned for, exposed as
  `implementation.authored_against`.
- **Environment profiles** (`chip.environment`, spec 0.5.0 §12.1): the host-owned
  `environment.spec/v0alpha1` document (`EnvironmentProfile`), plus
  `resolve_binding_against_environment(binding, profile)` returning an effective
  binding dict. Bindings gain an optional `environment` profile reference.
- **`partitioned(<keyField>)` state** (spec 0.5.0 §9): admitted for
  delegation-profile map/cache chips; `StateContract` parses and exposes
  `partition_key`, and the manifest loader requires the key to name a declared
  signal envelope field. Cursor-bearing attention chips still require
  `single-flight`.
- **Lifecycle telemetry** (`chip.lifecycle`, spec 0.5.0 §13.1): `LifecycleEvent`
  and `validate_lifecycle_event` enforcing the exact `mint`/`transfer`/`split`/
  `merge`/`optimize`/`retire` schema, the tuple-gating rule, and the raw-model
  baseline requirement for model-generation retirement.
- **Candidate ledger** (`chip.candidates`, spec 0.5.0): `Candidate`,
  `append_candidate`, `load_candidates`, and `tally` for the append-only
  `candidates.jsonl` side-activity capture convention.
- **Agent-invoked activation** (the *delegation profile*): documented in the
  spec (§3.1, §8.1) and the host execution contract; delegated activations are
  receipted identically and carry the invoking agent's identity.
- Docs: `docs/candidates.md` (candidate-capture convention) and
  `docs/skill-to-chip.md` (the falsifiability-triage skill→chip conversion
  method).
- **Chip datasheet** (`chip.datasheet`): a derived, never-authored comprehension
  surface for one chip. `build_datasheet(package_dir, *, evaluations,
  lifecycle_events, rollup, current_generation)` is a pure read-join over the
  manifest and fixtures plus plain-dict host telemetry (no host imports); it
  emits identity/promise, ports with a fixture-drawn example payload each, a
  probabilistic-stage table with the README residue echoed verbatim,
  authority/limits as "what this chip can never do", evaluation status with an
  `authoredAgainst` drift banner, live stats (with a "no telemetry yet"
  fallback), lineage, and a projection-manifest block (source snapshot,
  generator, coverage×freshness confidence, invalidation trigger). Two
  renderers: `render_markdown` (terminal-friendly) and `render_html`
  (self-contained artoo-kit page, no external requests). Presence is never
  evidence — correctness rides the held-out eval status and drift flag, and
  absent inputs are named in the coverage statement.

### Changed

- Bindings may carry per-chip configuration under `chipParameters` (spec
  0.4.2): merged into the activation `config` beneath host-injected keys;
  secret literals rejected. (Landed since 0.1.0; ships in 0.2.0.)
- Library version bumped to 0.2.0.

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
