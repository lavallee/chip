---
name: chip-outcome
description: Wire a host to emit outcome receipts so a chip can be calibrated rather than merely evaluated — invoke when a host consumes a chip's judgment to make a decision, and whenever someone asks whether a chip is actually any good.
---

# chip-outcome

A run receipt records what a chip decided. It cannot record whether the chip was
right, because that is not known yet. The outcome receipt (§13.3) is the record
that closes the loop, and it is the difference between a chip you can evaluate
against fixtures you wrote yourself and a chip you can calibrate against
reality.

## Command map (verbs → leaves)

| to do this | run |
|---|---|
| validate run + outcome receipts | `chip receipt <file…>` · or pipe JSONL on stdin |
| receipts for one installation | `fab chip receipts <installation-id> [--tail N]` |
| per-chip rollup | `fab chip stats [alias]` |

## The shape

```json
{
  "schema": "chip.outcome/v0alpha1",
  "runRef": "receipt:<iid>:<n>",
  "chipVerdict": "skip-verification",
  "hostDecision": "verified",
  "followedChip": false,
  "floorDecision": "verify",
  "downstreamVerdict": "pass",
  "audited": false,
  "at": "2026-07-25T12:00:00Z"
}
```

## The four fields that carry the weight

**`floorDecision`** — what the host would have done *without* the chip. Without
a floor there is nothing to compare against and the chip's contribution is
unmeasurable. If your host has an independent rule (a label ladder, a policy
default, a human's standing habit), that rule is the floor and it must be
recorded on every run, including the ones where it agreed.

**`followedChip`** — whether the host actually took the chip's advice. A host
that always follows the chip is not measuring the chip, it is trusting it.

**`audited`** — the run where the chip's advice was deliberately **not** taken so
its precision could be measured instead of inferred from silence. This is the
only field that generates new information: a chip that says "skip" and is always
obeyed produces no evidence about what it would have missed. Sample a rate,
record it, and accept the cost.

**`downstreamVerdict`** — what actually happened, once known. Usually written
later than the rest, which is fine; outcome receipts are append-only and
correction is by supersession.

## Checklist

1. **Find the decision the chip feeds.** If the chip's output does not change a
   host decision, there is no outcome to record — and probably no reason for the
   chip to be `synthesize` class.
2. **Identify the floor and make it explicit.** Most hosts already have one and
   have never named it. Write it down before wiring anything.
3. **Emit the outcome receipt where the downstream result is known**, which is
   usually a different place in the code from where the chip ran. Carry the run
   ref through; that is the join key.
4. **Sample counterfactual audits.** A deterministic rate keyed on the change's
   lineage, so the sampling is reproducible and cannot be gamed by retry. An
   audited run's result stays safety-relevant — a failure still downgrades the
   change; you are measuring the chip, not suspending the check.
5. **Never mark a followed run as audited.** An audit is by definition a run
   where the advice was not taken; the contract rejects the combination.
6. **Read the join, not the receipts.** Chip verdict against floor against
   downstream verdict, over time, is the only thing that answers "is this chip
   earning its keep" — and it is exactly the question `retire --reason
   model-generation` demands evidence for.

## Why this is in the contract

The reference host maintained precisely this record — chip plan, independent
ladder decision, verifier verdict, final status, audit flag — in a host-private
file, because the contract had nowhere to put it. Meanwhile every run receipt's
`outcomeLinks` field sat empty on all 91 production receipts. Spec 0.6 deleted
the field that failed to hold it and promoted the record that worked.

See [[chip-audit]] for finding chips with no outcome receipts at all, and
[[chip-evaluate]] for the held-out suite that outcome data should eventually
inform.
