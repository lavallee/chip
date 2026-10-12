# Changelog

All notable changes follow [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [0.4.0] — 2026-10-12

The release that leads with the ladder. The placement rubric, the socket design
note, the eighth skill, and a second host (`chipsocket`, released the same day
as v0.2.0) that passes its own suite without importing fab.

### Added

- `chip-socket`, the eighth agent skill: when an existing function's
  code-or-model decision is a socket, the smallest correct change, phase 0 in
  production, keeping paid members inside the band, learning the cuts from
  labelled receipts, and carrying the verdict into `chip-candidate`. Shipped
  under `src/chip/skills/` and mirrored to the plugin tree.
- `chip.placement` — the placement rubric for the distillation ladder
  (`docs/skill-to-chip.md`): `PlacementEvidence` / `DayObservation` in,
  a `Placement` verdict plus the `Reason`s that produced it out. Pure and
  gathering-free, so any scanner or telemetry store can feed it. Verdicts are a
  closed vocabulary (`observer`, `mint`, `parser`, `no-standing-relationship`,
  `no-judgment-stage`, `undecidable`), and `source_limits` builds the
  `sourceLimits` block that carries a report's gaps into a commissioned
  candidate. The six encoded rules are the ones that survived a hand-run over
  1.1M production calls; evidence is only constructible from a daily series
  because aggregates produced a wrong verdict during it.
- `PlacementError` (`CHIP_PLACEMENT_ERROR`).
- `docs/socket.md` — the socket design note (one contract, several live
  implementations). Restored from the rescued checkout: the two commits that
  added it on 2026-09-16 were missing from this clone.
- `docs/related-work.md` — where the socket and the ladder sit beside workflow
  DSLs, shadow evaluation, routers and cascades, judge-reliability work,
  decision models, and typed-output optimizers.

### Changed

- The README leads with the distillation ladder and the socket before the
  manifest (roadmap item 3, now shipped and removed from `ROADMAP.md`). The
  install section says plainly that `chipspec` is not yet on PyPI and gives
  the from-source line.

## [0.3.0] — 2026-07-25

Tracks spec 0.6.0. **Breaking**: the receipt surface is rebuilt around one shape,
and the datasheet generator has moved to the reference host. See
`spec/CHANGELOG.md` for the reasoning and the production evidence behind each cut.

### Removed

- `AttentionReceipt`, `JudgmentReceipt`, `build_attention_receipt`,
  `build_judgment_receipt`, `ATTENTION_SCHEMA`, `JUDGMENT_SCHEMA` — replaced by
  the single `Receipt` / `build_receipt` / `RECEIPT_SCHEMA`.
- `Datasheet`, `build_datasheet`, `render_markdown`, `render_html` and the
  `chip.datasheet` module — moved to fab (`fab.chips.datasheet_generator`).

### Added

- **A `chip` CLI** (`chip.cli:main`) with the host-independent verbs only:
  `validate`, `fixtures`, `digest`, `preflight`, `lint`, `receipt`. It
  deliberately cannot install, activate, approve, or revoke — those need a host.
  Every command takes `--json` and exits 0/1 so CI and skills can consume it.
  `chip preflight` is §16.4 in executable form: it catches the package that
  resolves in the authoring workspace and not in the environment where
  activations run.
- **`chip.packaging`** — `package_digest` (moved from the reference host, since
  two hosts that digest a package differently do not have the same chip),
  `split_entrypoint`, `preflight`, `PreflightReport`.
- **Seven agent skills** under `src/chip/skills/`, shipped with the package and
  mirrored to `skills/` as a Claude Code plugin (`chip-contract`):
  `chip-candidate`, `chip-author`, `chip-fixtures`, `chip-evaluate`,
  `chip-install`, `chip-audit`, `chip-outcome`. `tests/test_plugin_skills.py`
  enforces byte-parity between the two trees and fails if a skill's command map
  names a `chip` verb the CLI does not implement.
- `Receipt`, `build_receipt`, `RECEIPT_SCHEMA` — one run receipt with a required
  core and optional blocks.
- `OutcomeReceipt`, `build_outcome_receipt`, `validate_outcome`,
  `OUTCOME_SCHEMA` — spec §13.3, the record that links a judgment to what
  happened next.
- `Authority` — the effective ceiling plus one reason, replacing the host-side
  five-field authority record.
- `TERMINAL_REASONS` and `AUTHORITY_REASONS` — the closed vocabularies, exported
  so hosts validate against the contract instead of inventing strings.
- Source-commissioned candidate identity (`candidateId`, `sourceId`, and exact
  `sourceRevision`), separate counterexample references, and explicit source
  limits.
- `commission_candidate` and content-addressed
  `chip.candidate-receipt/v1` custody receipts. Exact replay is idempotent and
  commissioned tallies union occurrence references across source revisions.

### Fixed

- `Receipt.to_dict()` copies its mutable members. The dataclass is frozen, but
  the old exports handed out live references, so a caller could edit a receipt
  through its own export.
- Renamed the internal `chip.taint` module to `chip.tainting`: importing the
  submodule used to shadow the package's exported `taint()` function
  (Python binds the submodule to the package attribute on import, silently
  replacing the lazy export). Public `chip.taint(...)` and every other
  package-level export are unchanged; only direct submodule imports
  (`from chip.taint import ...`) must become `from chip.tainting import ...`.

### Migration

- `build_attention_receipt(coords, …)` → `build_receipt(coords, …, digests=…,
  authority=…)`. Attention-tier callers now supply digests and an authority
  decision; runs that reached no state/gateway/effect stage simply omit those
  blocks.
- `build_judgment_receipt(…)` → `build_receipt(…)`, with
  `state_version_before`/`_after` → `state={"versionBefore": …, "versionAfter": …}`,
  `input_ids`/`evidence_refs` → `inputs={"ids": …, "evidenceRefs": …}`,
  `stage_events` → `stages`, and `latency` folded into `cost`.
- `decisions["authority"]` → the top-level `authority` field.
- Freeform terminal reasons must map onto `TERMINAL_REASONS`. Operator actions
  (install, pause, revoke, evaluate, approve) are **not runs** and no longer
  borrow run-receipt vocabulary — hosts should give them their own record shape.


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
