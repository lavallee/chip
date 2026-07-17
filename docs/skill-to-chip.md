# Skill to chip: the falsifiability triage

Status: method note layered on the spec (spec 0.5.0). This is the conversion
discipline for turning a mature prose skill into a chip (or deciding it should
stay a skill). It operationalizes the classification exercise of spec §19.

## The distillation ladder

A capability moves down a ladder as more of it earns a precise, testable form:

```
prose skill
  → thin skill (typed outputs, recognition + interpretation only)
  → hybrid chip (deterministic envelope, one bounded judgment stage)
  → deterministic chip (all judgments rule/code based)
  → plain code (retired from the model entirely)
```

Each rung evicts more from the model. The framing is not "wrap the model in
code" but **progressively evict everything from the model except what earns its
place**. What earns its place is the irreducible probabilistic essence — the
judgment a fixture cannot decide.

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
