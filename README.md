# chip

**The code-vs-model boundary is a position that evidence should move.**

[![CI](https://github.com/lavallee/chip/actions/workflows/ci.yml/badge.svg)](https://github.com/lavallee/chip/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](./LICENSE)

Every behavior an agent performs sits somewhere on a ladder between prose a
model reads and plain code nothing reads. Most of it pools at the prose end,
because prose is frictionless to write and nothing pushes back. This project
is the push-back: a way to find the rung each behavior belongs on, move it
there on evidence rather than taste, and move it back when a stronger model
reclaims it. The goal is not to drive everything to the code end. It is to
evict from the model everything except the judgment that earns its place.

## The ladder

```
prose skill
  → thin skill (typed outputs, recognition + interpretation only)
  → hybrid chip (deterministic envelope, one bounded judgment stage)
  → deterministic chip (all judgments rule/code based)
  → thin skill + CLI (judgment and envelope both gone; a versioned
      deterministic tool plus a skill that only teaches discovery/invocation)
  → plain code (no skill at all; invoked by system wiring, not by an agent
      reading prose)
```

The early rungs evict **judgment** from the model; the late rungs evict
**governance** and **teaching**. Movement is bidirectional, and the evidence
that moves it is the receipt stream: call frequency, quiet rates, abstentions,
and how often a cheaper implementation agrees with a dearer one. The method
is [`docs/skill-to-chip.md`](./docs/skill-to-chip.md); the rubric that turns
evidence into a verdict is `chip.placement`.

## Two ways in

### The socket: plug into code you already have

A **socket** is one typed contract with several live implementations seated
behind it — deterministic code, a model at some tier, a model at a higher
tier — and a strategy that picks among them per call. Every call writes a
receipt saying which member answered, why the earlier ones did not, and what
any shadow would have said. Over enough calls the receipts are the evidence
for where the boundary belongs, produced on production traffic without
leaving the program the call lives in.

```python
from chipsocket import Abstain, contract, model

@contract(input=Claim, output=Verdict, invariants=[reason_is_short],
          sink="receipts.jsonl", harvest="harvest.jsonl")
def admissible(claim: Claim) -> Verdict | Abstain:
    ...                                   # your existing code, unchanged;
                                          # return Abstain("band") where it cannot decide

admissible.member(model(gateway, prompt=render, result=Verdict, profile="claims-mid"))
admissible.shadow(model(gateway, prompt=render, result=Verdict, profile="claims-gold"),
                  sample=0.03, budget_usd_daily=2.0, noise=True)

verdict = admissible(claim)               # code first; model on abstain; gold shadows 3%
```

`chipsocket report receipts.jsonl` then states the closed-by-code share, the
escalation triggers split into boundary causes and operations causes, and each
shadow's agreement with the answering member net of that member's own noise
floor. With labels, `chipsocket.report.band` reads the escalation band off the
receipts instead of guessing it.

The runner is [`chipsocket`](https://github.com/lavallee/chipsocket)
(`pip install chipsocket`). It depends on `chipspec` and nothing else, never
imports the reference host, and is this project's minimal second host
(roadmap item 2). The design is [`docs/socket.md`](./docs/socket.md).

### The chip: package the behavior that has earned governance

A **chip** is one packaged, versioned unit of judgment for behavior that has a
standing observation relationship to a signal, owns cross-run state, or acts
under an authority contract. It declares the **ports** it reads and writes and
one bounded operational promise: observe what it is told to observe, decide
within its own scope, and emit a **receipt** for every run, including the
quiet ones where it does nothing. A chip is a socket seated in an envelope —
promise, ports, state, effects, authority ceiling — and the hybrid class
(deterministic envelope, at most one gateway stage) is a socket with one
`code` member and one `model` member.

Chips compose into a **circuit** — a linear sequence, each consuming the prior
chip's ports. A **host** owns a **binding**: it wires ports to real data,
executes each chip in order, enforces policy, and persists receipts. A chip
that needs model judgment reaches it through a **gateway** the host provides,
never through credentials of its own. Activation is pull/invoke only, in an
**attention profile** (an owner-side schedule emits a signal) or a
**delegation profile** (an agent invokes an installed chip mid-workflow); both
are receipted, metered, and gated identically.

Most behaviors should not be chips. The admission rule (spec §4.1) and the
`chip-candidate` skill exist to say so.

## What this repository is

The contract itself: the spec, a validation library, a conformance kit, and
seven agent skills over the lifecycle. It is **not a runtime** and has zero
runtime dependencies. fab is the reference host (being open-sourced);
[chipsocket](https://github.com/lavallee/chipsocket) is the second host;
[somm](https://github.com/lavallee/somm) is a reference gateway and meter.

## Install

`chipspec` is not yet on PyPI: the trusted-publisher registration is pending,
so the package line below does not resolve today. Install from source:

```bash
pip install git+https://github.com/lavallee/chip
pip install "chipspec[jsonschema] @ git+https://github.com/lavallee/chip"   # schema validation for port payloads
```

Once published:

```bash
pip install chipspec
```

Requires Python 3.12+. The import package is `chip` (the distribution is
named `chipspec` because `chip` is squatted). The `chip` CLI ships with it:
`validate`, `fixtures`, `digest`, `preflight`, `lint`, `receipt` — the
host-independent verbs only.

## Status

v0 experiment — two hosts (fab, and the socket runner), contract under active
evolution. See [`spec/chip-spec.md`](./spec/chip-spec.md) for the current
spec, [`ROADMAP.md`](./ROADMAP.md) for what happens next, and
[`docs/falsification.md`](./docs/falsification.md) for the conditions under
which this program should stop. [`docs/related-work.md`](./docs/related-work.md)
places the socket and the ladder beside routers, cascades, workflow DSLs, and
decision models.

## Layout

| Path | What it is |
| --- | --- |
| `spec/` | The chip spec — the normative contract text |
| `src/chip/` | The `chip` package: validation, placement, candidates, conformance helpers, and the CLI |
| `src/chip/skills/` | The seven agent skills, mirrored to `skills/` as a Claude Code plugin |
| `examples/` | Example chips exercising the contract |
| `docs/` | The ladder, the socket, host execution contract, candidate ledger, related work |
| `ROADMAP.md` | The sequenced bets |
| `tests/` | The conformance test suite |

## Design principles

- **One promise per chip.** A chip declares one bounded job and does
  only that job.
- **Deterministic envelope around probabilistic judgment.** LLM-backed
  decisions live inside a fixed, inspectable shape — ports, policy
  gates, and receipts don't get to be probabilistic too.
- **Abstention is an answer.** A member that cannot decide says so, with a
  reason and a score, and the next member runs. The abstentions are where the
  boundary lives.
- **Authority fails closed.** No implicit escalation. Absent explicit
  policy grant, a chip acts as if it has none.
- **Receipts for every run, including quiet ones.** A chip that
  observes and decides not to act still produces a receipt saying so.
- **Taint is transitive.** Anything a chip's judgment touches carries
  forward whatever provenance or trust constraints it entered with.
- **Targets own final deduplication.** A chip proposes; whatever system
  it writes into is the one source of truth for whether that write is
  new.

## Contributing

See [`CONTRIBUTING.md`](./CONTRIBUTING.md). Security issues:
[`SECURITY.md`](./SECURITY.md). Releasing: [`RELEASING.md`](./RELEASING.md).

## License

MIT — see [`LICENSE`](./LICENSE).
