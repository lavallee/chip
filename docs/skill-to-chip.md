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

## Placing a behavior from evidence

The per-behavior test above is asked of a skill you are holding. The same
question gets asked of behavior already running in production, where the
evidence is a call ledger rather than a document — and there the answer should
be derived, not remembered. `chip.placement` is that derivation: an evidence
record in, a verdict plus its rationale out.

It is deliberately only the rubric. It gathers nothing and reaches nothing;
whatever holds the evidence builds a `PlacementEvidence` and calls `assess`.
The scanner is not portable across fleets, but the rubric is, and a placement
report that cannot be re-derived from its own cited measures is an opinion.

Six rules survived a hand-run over 1.1M production calls:

1. **Admission first, scoring second.** Standing-vs-burst (spec §4.1) is
   decided before anything is scored, and rules out roughly a third of a real
   fleet without judgment.
2. **Time series, not aggregates.** Evidence is built from daily observations;
   there is no constructor for a pre-summarized row. A 51-day aggregate hid a
   10-day incident and produced a wrong verdict.
3. **Never rank by cost.** The largest observed loss — 495,130 calls that never
   reached a provider — cost nothing.
4. **Repetition routes the ladder.** Novel input every time is extraction, and
   distils toward *thin skill + CLI*; recurring input over a standing
   relationship is what a chip rung is for.
5. **The failure motif separates the envelope from the judgment.** Terminal
   envelope failure means an observer or a parser, not a judgment chip.
6. **`undecidable` is a verdict.** When evidence cannot decide, the rubric says
   so and names what is missing.

The negative verdicts are the point, not a byproduct. On a real fleet most
subjects are not chip-shaped, and a rubric that only emits positives is an
advocacy tool. `no-standing-relationship`, `no-judgment-stage`, and
`undecidable` are what make the positives worth reading.

Two limits are worth stating plainly. A verdict is single-valued, so a
behavior that is both envelope-failing and novel-input reports as an observer
and the parser reading is displaced — the envelope problem is simply the one to
fix first. And falsifiability itself is not machine-checkable without a declared
output contract: where none exists, a rung verdict is capped at low confidence
and carries `output contract undeclared` as a gap. A placement report is exactly
the external finding system `docs/candidates.md` describes, so `source_limits`
builds the `sourceLimits` block that carries those gaps into any candidate it
commissions.

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

## Worked boundary: design taste and DES

A design skill is not chip-shaped merely because it has a rubric or can produce
code. Brief interpretation, audience negotiation, selecting a surface mode,
making a justified system exception, and composing a visual direction remain
dialogic skill behavior. Deterministic token checks, overflow checks, browser
capture, and receipt generation are tools. Spindle composes and binds the skill;
neither activity needs a chip runtime.

A **design-lineage observer** could qualify later, but only if practice produces
a real standing relationship and cross-run state. Its narrow promise might be:

> Observe receipted DES structural fingerprints for unrelated expressive
> projects and recommend one bounded variation when the same fingerprint repeats
> beyond policy limits.

That candidate would need:

- an input port containing DES receipt references, surface mode, design profile,
  structural fingerprint, and product identity;
- installation-scoped state for prior fingerprints and recommendation effect
  keys;
- a quiet result when repetition is below threshold or consistency is desired;
- no code edit, skill bind, merge, or publication effect;
- fixtures where similar operator layouts are correct and repeated marketing
  layouts are not; and
- evaluation bound to implementation digest, DES profile, requested and served
  model, harness, and declared seeing/browser capabilities.

Until repeated receipts demonstrate that this standing observer pays for its
state and governance, keep structural memory in product-local DES records and
the assessment loop in Projector/Spindle. Minting a chip before that evidence
would turn a one-shot design practice into unnecessary runtime machinery.
