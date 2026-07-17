# Skill to chip: the falsifiability triage

Status: method note layered on the spec (spec 0.5.0). This is the conversion
discipline for turning a mature prose skill into a chip (or deciding it should
stay a skill). It operationalizes the classification exercise of spec §19.

## The distillation ladder

The ladder is a set of stations, not a progression — the goal is not to
move everything to the code end, it is to get every behavior to the RIGHT
rung. Movement is bidirectional and evidence-driven. The tooling emphasizes
rightward pathways only because the observed inertia runs the other way:
behavior pools at the fat-skill end, where prose is frictionless to write
and nothing pushes back.

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
**governance** (as it stops being needed) and **teaching** (as models stop
needing it). The framing is not "wrap the model in code" but **progressively
evict everything from the model except what earns its place**. What earns its
place is the irreducible probabilistic essence — the judgment a fixture cannot
decide.

Two paths reach the late rungs, and the §4.1 admission rule is the switch:

- A behavior with **no standing observation relationship and no cross-run
  state** never enters the chip rungs at all — it distills straight from prose
  to *thin skill + CLI*. Enforcement-shaped behavior usually wants to be a
  tool first; that is success, not a failed decomposition.
- A behavior that satisfies admission settles at a chip rung and may later
  **migrate** to *thin skill + CLI* when the governance envelope stops paying
  for itself — this is a destination for the `retire` lifecycle event, not
  just deletion: the deterministic code survives as a tool, and the chip's
  fixtures survive as the CLI's ordinary test suite. Migration runs the other
  way too: a CLI that keeps needing standing attention, receipts, or
  authority gating has outgrown its rung and belongs at a chip station.

The chip rungs are the ladder's **governed holding areas**: places where a
behavior can sit safely between prose and bare code while evidence about its
true shape accumulates. A chip's receipts and evaluations are not just
safety machinery — they are the placement data. Call frequency, quiet rates,
judgment-stage value, and authority usage are exactly what decide whether
the behavior migrates further, stays, or returns toward prose when a
stronger model reclaims it.

## The per-behavior test

Take the skill apart into individual behaviors. For each one ask a single
question: **can a fixture falsify it?**

- **Yes — a fixture decides it.** It is code or evaluation material. Evict it
  from the model into deterministic code, or capture it as a held-out fixture.
- **It needs situated dialogue or negotiation.** It stays a skill. The
  canonical case is the *justified exception* — where strict process is wrong and
  the right move depends on context a fixture cannot carry. Amputating this is the
  failure mode spec §19 warns against.
- **It is a bounded, schema-decidable judgment.** It becomes the single gateway
  stage of a hybrid chip (spec §10.2): a request schema in, a result schema out,
  graded by a held-out suite.

Failure patterns drive eviction as much as success patterns: a mishap becomes a
pinned fixture and a guard/gate requirement, so the same mistake cannot recur.

## What the residual skill becomes

As behaviors move down the ladder, the skill that remains gets **thinner**, not
thicker. A residual skill keeps only recognition and interpretation (spec §18's
wrapper list): knowing when the capability is relevant, conducting ambiguous
dialogue, selecting a circuit, and explaining receipts. It owns no cursors, no
retry loops, no effect dispatch, no hidden shell state. If it needs those to
work, the decomposition has not finished.

## Rung transitions are PATCH-safe

Moving down a rung — collapsing a prompt into code, merging two stages — is a
`PATCH` under spec §15 **when the public promise, ports, state, effects,
authority, and evaluated tuple all hold and held-out performance is
non-inferior.** The internals are a build output; the promise and its held-out
suite are the contract. That is what makes the ladder safe to descend
incrementally: each step is validated against the same fixtures, and a step that
regresses the held-out suite is simply not taken.

The goal is never to reclassify every useful tool as a chip, nor to force
dialogic behavior into a manifest. It is to let each behavior settle at the
lowest rung a fixture can justify — and to leave the rest, honestly, as a skill.
