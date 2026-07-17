# Examples — publication-triage pilot

This directory contains the first pilot from chip-spec §22: **publication
triage**, the reference circuit of §20.1. It is one attention chip plus one
two-chip linear circuit, runnable in a disposable, credential-free environment.

```text
  public agency                                        host applies
  publication feed        publication-attention        policy + human gate
  (owner-scheduled)   ┌──────────────────────────┐   ┌────────────────────┐
        │             │  normalize → assess →     │   │ recommend-research │
        │  signal     │  validate   (gateway)     │   │ effect request     │
        └────────────▶│                           │   │  (approval: human) │
                      │  emits: finding | quiet   │   └─────────▲──────────┘
                      └───────────┬──────────────┘             │
                        finding   │  materiality-finding.json@1 │ effect
                                  ▼                             │ request
                      ┌──────────────────────────┐             │
                      │  bounded-recommendation   │─────────────┘
                      │  gate → compose (code)    │
                      │  emits: recommendation-   │──▶ quiet (already-issued)
                      │  issued | quiet           │
                      └──────────────────────────┘
```

- **`publication-attention/`** — hybrid chip. Senses a new publication, dedupes
  by content digest against an installation cursor, and runs a single gateway
  (LLM) materiality judgment inside a deterministic envelope. Emits an
  evidence-linked `finding`, an `abstain` (low confidence), or a `quiet` result.
  Declares **no effects**.
- **`bounded-recommendation/`** — deterministic chip. Turns a finding into at
  most one rate-limited, human-gated `recommend-research` effect request per
  unique lineage, with a stable idempotency key. Refuses to launder untainted
  evidence.
- **`circuits/publication-triage.json`** — the linear composition wiring
  `attention.finding → recommend.finding` by exact schema ref, with a `synthesize`
  authority ceiling and a human decision point on `recommend-research`.

## What the pilot demonstrates

- **No new artifact → quiet receipt.** Already-seen / duplicate content is quiet
  and costs no gateway call.
- **Duplicate lineage ≠ corroboration.** Dedupe is by content digest, so the
  same report on a different feed entry id does not count twice.
- **Hostile content stays evidence.** Injection text in a publication body is
  carried only as structurally-separate, taint-preserving quoted spans; it never
  reaches instruction position, and the derived recommendation refuses to strip
  the taint.
- **At-least-once in, at most once out.** The effect idempotency key derives only
  from stable lineage, so retries, cursor resets, and state migration all yield
  the same key — the target owner is the final deduplication authority.
- **Fail closed.** A malformed signal or an invalid gateway result aborts the run
  with no effect.

## Running without credentials

Every fixture ships a `cannedGatewayResult` (or `null` where no gateway call is
expected), so any host can exercise the full contract with **no model
credentials and no network**. In fixture/eval mode the host substitutes the
canned result for the live gateway; the pure `run(activation)` implementation
cannot tell the difference (`docs/host-execution-contract.md`).

`tests/test_examples.py` is exactly such a host: it loads both packages the way a
host resolves the dotted entrypoint, checks fixture coverage, validates the
circuit, and drives each implementation over every fixture with an at-most-once
gateway that taints its result on hostile input — asserting the quiet, content
dedup, adversarial, idempotency, and fail-closed properties above, and that the
library accepts every response and effect envelope. Fab is the reference host and
`somm` the reference gateway; nothing in these packages depends on either.

## A note on authority (per-chip effective ceiling)

`publication-attention` emits no effects and declares `maximumEffectClass:
observe`, its honest ceiling. This does **not** cap the downstream
`bounded-recommendation` chip: authority is computed **per effect-requesting
chip** (§12). `validate_circuit` returns a per-chip effective-ceiling map — the
sensing chip resolves to `observe`, the recommendation chip to the circuit's
`synthesize` ceiling — so a low upstream ceiling never denies the downstream
effect the pilot exists to make.
