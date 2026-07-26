---
name: chip-candidate
description: Decide whether a behavior should become a chip, stay a skill, or remain a plain prompt — invoke before authoring anything, and whenever someone says "we should make this a chip".
---

# chip-candidate

Most things should not be chips. This skill is the gate that keeps the
vocabulary honest, and the cheapest step in the whole lifecycle: a wrong answer
here costs a package, a fixture suite, an evaluation, and an upkeep burden that
never amortizes.

## Command map (verbs → leaves)

`chip --help` prints the full map. Package-level verbs are host-independent:

| to do this | run |
|---|---|
| validate a package | `chip validate <pkg>` |
| fixture inventory + §7 coverage | `chip fixtures <pkg>` |
| package identity (§16.1) | `chip digest <pkg>` |
| would it load *here*? (§16.4) | `chip preflight <pkg>` |
| package + authoring conventions | `chip lint <pkg>` |
| validate receipts | `chip receipt <file…>` · or pipe JSONL on stdin |

Host verbs need a host; the reference host is fab (`fab chip …`). See
[[chip-install]].

## The admission rule

A behavior is admissible as a chip **only if both** hold:

1. it declares an ongoing observation relationship to a signal class, **or** the
   package owns durable cross-run state; **and**
2. it produces a bounded response under an authority contract.

A callable operation with neither is a **tool**, even if a skill currently wraps
it. A capability whose value is open-ended conversation and situated judgment is
a **dialogic skill**. A principle that informs work without executing is
**doctrine**.

## Checklist

1. **Say the promise in one sentence.** If it needs "and" to be accurate, it is
   at least two chips or it is not a chip. One chip, one operational promise.
2. **Run the admission rule.** Both clauses, out loud, against the actual
   behavior — not against the tidied version you would like it to be.
3. **Look for the state.** Which cursor, ledger, or seen-set does this behavior
   need between runs? If the answer is "none", you are probably describing a
   tool. Real state is the strongest chip signal there is.
4. **Find the effect and its class.** `observe` · `synthesize` · `experiment` ·
   `draft` · `promote`. A behavior with no effect at all is a report, and a
   report is a tool.
5. **Check it against the model.** Would a current frontier model with ordinary
   typed tools do this as well, right now? If yes, the honest answer is "not
   yet a chip" — the value would be the governance envelope alone (identity,
   state, authority, taint, receipts), which is worth banking only if the
   behavior is genuinely recurring.
6. **Check the frequency.** Minting SHOULD be gated on observed call frequency
   (§13.1). A path that has run three times is a candidate, not a chip. If a
   candidate ledger exists, cite the tally rather than an impression.
7. **Name what it is if it isn't a chip**, and say where the behavior goes
   instead. No behavior may disappear silently — that is how safety gates get
   lost in a decomposition.

## Where this usually lands

- **Chip.** Attention with a cursor; a stale-invalidation rule; a bounded
  sign-off; a triage that must not re-fire on a duplicate.
- **Tool.** Snapshot capture; diff collection; a normalized finding
  constructor; anything a chip would *call*.
- **Dialogic skill.** Requirements interviews; design critique; teaching a
  method; negotiating an exception.
- **Doctrine.** "Evidence before claims." "Write the failing test first."

If the answer is chip, continue with [[chip-author]]. If it is anything else,
write down which and why — that record is what stops the same argument
recurring next quarter.
