# bounded-recommendation

A **deterministic** chip: the bounded-effect half of the publication-triage
pilot (chip-spec §20.1, §22).

> **Promise.** Given a materiality finding, emit at most one rate-limited,
> evidence-linked research recommendation effect request per unique lineage, or a
> quiet result.

## Ports

| Direction | Port | Schema | Notes |
|---|---|---|---|
| in | `finding` | `schemas/materiality-finding.json@1` | **exact same schema ref** as `publication-attention`'s `finding` output, so the circuit port match passes (§11) |
| out | `recommendation-issued` | `schemas/recommendation-issued.json@1` | records the stable effect key + lineage |
| out | `quiet` | `schemas/quiet-run.json@1` | first-class no-effect result |

> **Port name vs. response kind.** `recommendation-issued` is the output *port*
> name. The response envelope `kind` is one of the four terminal §8.2 run
> outcomes — here `finding` (issued), `quiet` (already-issued / idempotent
> re-run), or `abstain` (evidence taint lost). The issued recommendation rides in
> the response's `recommendation` field.

## Effect

| Effect | Schema | Class | Approval |
|---|---|---|---|
| `recommend-research` | `schemas/research-recommendation.json@1` | `recommend` | `human` |

The chip constructs an **effect request** and hands it to the host; it never
dispatches. The host decides authorization, approval, and dispatch (§8.3).

## State

Installation-scoped, single-flight (`schemas/rec-state.json@1`, retention
`P365D`): `issued` — the set of content-digest lineage keys already granted a
recommendation, for per-lineage rate accounting.

## Stages

`gate` (policy) → `compose` (code). No gateway stage — every judgment is
rule/code based, so the implementation class is `deterministic`.

The idempotency key is
`derive_effect_key(lineage.content_digest, "recommend-research", targetOwner, promiseId)`.
It excludes any run id or mutable state, so it is **identical across retries,
cursor resets, and state migration** — the property the target owner relies on
as the final deduplication authority (§8.3). At-least-once delivery therefore
yields at most one effect request per lineage.

## Refusing to launder

The `gate` stage checks that every evidence item carries a taint-preserving
`quoted_span` (`{value, taint}`) plus `source_url` and `digest`:

- **no evidence at all** → fails closed with `EnvelopeError`;
- **evidence present but taint stripped** → **abstains** rather than launder
  hostile source text into a clean recommendation (§8.2).

## Fixtures

| Fixture | Kind | What it proves |
|---|---|---|
| `positive` | positive | well-formed finding → one effect request, stable key |
| `duplicate` | duplicate | redelivery of an already-issued lineage → quiet, zero effects |
| `quiet` | quiet | idempotent re-run of an issued lineage → quiet, zero effects |
| `adversarial` | adversarial | evidence lost its taint marker → abstain, zero effects |
| `failure` | failure | finding with no evidence → `EnvelopeError`, fail closed |

## How a host runs it

```python
run({"signal": <materiality finding>, "state": <prior state|None>,
     "config": {"targetOwner": "owner://research-ideas", "promiseId": <manifest id>},
     "gateway": <always-raises for a deterministic chip>})
# -> {"response": ..., "state": ..., "effects": [<effect request>|...], "stage_events": [...]}
```

Pure function of `(signal, state, config)`; no gateway call, no I/O, no network,
nothing imported beyond the standard library and `chip.*`.
