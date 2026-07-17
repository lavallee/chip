# publication-attention

A **hybrid** attention chip: the sensing + materiality-judgment half of the
publication-triage pilot (chip-spec §20.1, §22).

> **Promise.** For every new in-scope publication signal, produce one
> evidence-linked materiality assessment or a quiet result, with no effect
> requests.

## Ports

| Direction | Port | Schema | Notes |
|---|---|---|---|
| in | `publication` | `schemas/publication-signal.json@1` | a §8.1 signal envelope whose taint-marked `content` carries the publication payload (`title`/`url`/`body`/`published_at`); `body` is hostile evidence text |
| out | `finding` | `schemas/materiality-finding.json@1` | evidence-linked materiality assessment |
| out | `quiet` | `schemas/quiet-run.json@1` | first-class no-finding result |

There are **no effect declarations** — this chip only observes and judges; the
downstream `bounded-recommendation` chip owns the (human-gated) effect.

The implementation also returns an `abstain` response on the model's
insufficient-evidence path (the low-confidence branch of §20.1).

## State

Installation-scoped, single-flight, cursor **required** (`schemas/state.json@1`,
retention `P365D`):

- `cursor` — monotonic lineage cursor (`published_at` of the last accepted signal);
- `seen` — content-digest lineage keys already processed.

Dedupe is by **content digest**, so the same content arriving on a different feed
entry id is a duplicate and stays quiet — a duplicate lineage never masquerades
as corroboration (§20.1).

## Stages

`normalize` (code) → `assess` (gateway) → `validate` (policy). Stages are
non-contractual (§7). The single gateway stage makes the chip `hybrid`; its
request/result schemas are `schemas/assessment-request.json@1` /
`schemas/assessment-result.json@1`, profile `materiality-mid`.

The hostile `body`/`title` reach the gateway **only** as structurally-separate
quoted spans under `evidence`; the chip-authored `instruction` never contains
source text (§8.2). Every quoted evidence span in the finding keeps its
`{value, taint}` marker, so trust survives to the downstream adapter.

## Fixtures

| Fixture | Kind | What it proves |
|---|---|---|
| `positive` | positive | new material report → finding, gateway called once |
| `quiet` | quiet | content with no assessable body → quiet, **no gateway call** (content-driven, so host `evaluate` reproduces it) |
| `adversarial` | adversarial | injection in `body` echoed by gateway → taint preserved, no instruction leakage, zero effects |
| `failure-malformed` | failure | envelope missing its content payload → `EnvelopeError`, fail closed before gateway |
| `failure-bad-result` | failure | gateway result violates the result contract → fail closed |

Content-lineage dedup (`duplicate-content`, `not-after-cursor`) is state-dependent, so
it is covered by a direct unit test rather than a fixture — a host `evaluate` zeroes
prior state, and the host also dedupes by `dedupeKey` before the chip runs.

## How a host runs it

Per `docs/host-execution-contract.md`, a host resolves the dotted entrypoint
`impl.chip_impl:run` (the module shipped at `impl/chip_impl.py`), imports it
inside a sandbox, and calls:

```python
run({"run_id": <host-minted run id>, "signal": <§8.1 signal envelope>,
     "state": <prior state|None>, "config": {"beat": ..., "scope": ...},
     "gateway": <at-most-once callable>})
# -> {"response": ..., "state": ..., "effects": [], "stage_events": [...]}
```

The response is an §8.2 envelope with top-level `producedByChip`/`producedByRun`
coordinates and the assessment carried in `body`.

The implementation is a pure function of `(signal, state, config, gateway)` —
deterministic except for the single gateway call. It performs no I/O, no network,
and imports nothing beyond the standard library and `chip.*`. In fixture/eval
mode the host substitutes the fixture's `cannedGatewayResult`; the implementation
cannot tell the difference. Fab is the reference host; `somm` is the reference
gateway.
