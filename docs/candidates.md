# The candidate ledger

Status: convention layered on the spec (spec 0.5.0). The library ships
`chip.candidates` (`Candidate`, `append_candidate`, `load_candidates`, `tally`);
this document explains when and why to use it.

## Why capture is a first-class activity

A chip is *minted, not designed*: it crystallizes only after a path has proven
routine, and minting stays gated on observed call frequency and held-out
evaluation (spec §13.1). That discipline creates a sequencing problem — by the
time a path is provably routine, the raw inputs that would make good held-out
fixtures have scrolled past.

So the scarce resource is not the chip. It is:

1. the **candidate observation** — the moment you notice "I keep doing this shape
   of work"; and
2. the **fixtures** — the real inputs encountered during normal work, which are
   the only honest material for a held-out suite.

Both are cheap to capture in the moment and expensive to reconstruct later.
Minting is the opposite: expensive up front, and wasteful if done eagerly. The
candidate ledger splits those economics apart — capture continuously, mint
rarely.

## The ledger

An append-only `candidates.jsonl`. Each line is one candidate:

```json
{
  "observedAt": "2026-07-17T00:00:00Z",
  "shape": "when a dependency range changes, propose a tested update",
  "occurrenceRefs": ["receipt:abc", "receipt:def"],
  "fixtureRefs": ["fixtures/harvested/001.json"],
  "count": 2,
  "notedBy": "agent:build-loop"
}
```

- **`shape`** — a one-line draft of the operational promise (spec §6). Not a
  design, just a falsifiable sentence: "when X happens, emit Y or a quiet
  receipt."
- **`occurrenceRefs`** — pointers to where the shape was observed (run receipts,
  session references) so frequency is evidenced, not remembered.
- **`fixtureRefs`** — real inputs harvested as future held-out material. This is
  the half that is impossible to reconstruct after the fact.
- **`count`** / **`notedBy`** — the running occurrence tally and who filed it.

## Source-commissioned candidates

External finding systems can use the same ledger without making replay look
like recurrence. A commissioned row adds:

```json
{
  "candidateId": "candidate:stable-across-source-revisions",
  "sourceId": "milton.finding=fnd_123",
  "sourceRevision": "milton.finding-revision=fnr_456",
  "counterexampleRefs": ["fixture:negative:clean-retry"],
  "sourceLimits": {
    "coverage": 0.75,
    "coverageGaps": ["one harness unavailable"],
    "expiresAt": "2026-08-01T00:00:00Z"
  }
}
```

Use `commission_candidate`, not `append_candidate`, for these rows. It requires
the three identity fields together, sorted unique reference lists, `count`
equal to the number of occurrence references, and explicit source limits. The
same candidate id cannot change source or shape. The same source revision
cannot change content.

Commissioning writes a content-addressed `chip.candidate-receipt/v1` to
`candidate-receipts.jsonl` (or an explicit receipt path). Replaying the exact
revision returns the same receipt and appends nothing. `tally` unions occurrence
references across commissioned revisions, so a later source snapshot cannot
recount an earlier occurrence. Counterexamples and negative/exception fixture
references remain distinct inputs to later held-out evaluation; they do not
reduce or increase the occurrence tally.

The candidate ledger remains Chip-owned. The receipt ledger is the public
interop surface consumers can ingest without reading private candidate or
fixture material.

## The loop

1. **Capture** during normal work — a thin standing instruction to notice a
   recurring shape and append a line, harvesting the triggering input as a
   fixture. This is intentionally an instruction (a skill), not a chip: noticing
   is situated judgment.
2. **Tally** by shape (`tally(load_candidates(path))`) to see which shapes have
   crossed a frequency threshold worth the authoring and evaluation upkeep.
3. **Mint** only the shapes that clear the frequency *and* held-out bars. A
   minted chip records a `mint` lifecycle event (spec §13.1); the harvested
   fixtures seed its held-out suite.

Capturing a candidate commits you to nothing. It makes the minting decision
evidence-driven — and it means that when a shape does earn a chip, the fixtures
that prove it were already collected while the work was fresh.
