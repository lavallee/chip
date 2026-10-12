---
name: chip-socket
description: Seat an existing function's code-or-model decision in a socket so every call is receipted and the escalation band can be learned — invoke when adding a model call to a function, when a heuristic-then-LLM threshold was guessed, or before deciding whether a behavior should move a rung on the ladder.
---

# chip-socket

The socket is the primitive below chip. A chip is a socket seated in an
envelope (promise, ports, state, authority); a socket is just one typed
contract with several live implementations and a receipt per call. Most
behavior that would benefit from the ladder is a plain function in a program
with no scheduler, no policy gate, and no custody store. The socket is how
that function gets evidence without becoming a package.

Reach for this before [[chip-candidate]]: a socket's receipts are the evidence
that skill asks you to cite.

## Command map (verbs → leaves)

Socket verbs belong to the `chipsocket` runner, not to `chip`:

| to do this | run |
|---|---|
| live measures per socket | `chipsocket report <receipts>` |
| every member against labels | `chipsocket score <receipts> --truth F --key P` |
| truth by score where a member abstained | `chipsocket band <receipts> --truth F --key P --member M` |
| learn the cut points | `chipsocket cuts <receipts> --truth F --key P --scorer M` |

`<receipts>` is a `.jsonl`, a `.jsonl.gz`, a directory, or a glob. Output is
JSON. The contract library's own verbs (`chip validate`, `chip lint`, …) apply
once a socket graduates into a package.

## When it is a socket

All three hold:

1. **One function decides one thing** with a typed output. If the output is
   prose or a plan, it is not a contract.
2. **Some inputs are decidable by code** and the rest get asked of a model, or
   would be if anyone had measured which is which.
3. **The boundary is a guess.** A threshold, a prefilter, a "fallback" branch,
   or two projects carrying the same judge with different cuts.

Not a socket: a pipeline, a loop, routing between different contracts,
anything that needs a graph. Selection among implementations of one contract
is the whole scope.

## Checklist

1. **Leave the answers alone.** Decorate the function with
   `@contract(input=, output=, invariants=, sink=)`. Where the code used to
   call the model, return `Abstain("reason", score=s)` instead — the score is
   whatever ordering the code already had (a similarity, a margin, a
   relevance). Seat the model behind it with `member(model(gateway,
   prompt=, result=, profile=))`.
2. **Declare what a receipt may hold** with `clean=` before the first run.
   Headlines, claim bodies, and anything under a client-material rule do not
   enter a receipt; keys, domains, and scores do.
3. **In production, start with phase 0.** Seat the incumbent's recorded
   verdict as primary with `recorded(read, id=, digest=, kind="model")`.
   Shadow the candidate code member at `sample=1.0`; shadow a gold model at a
   small sample with `budget_usd_daily=` and `noise=True`. Nothing changes
   for the caller; the receipts start accumulating.
4. **Keep paid members inside the band** with `banded(member, score, lo, hi)`.
   A shadow that asks about inputs the code already closes is spending on
   calls nothing will route to it.
5. **Read the report before reading the agreement number.** `chipsocket
   report` splits escalations into boundary triggers (`abstained`,
   `invariant`) and operations triggers (`schema`, `transport`, `error`,
   `budget`). Operations dominant means a gateway problem, not a placement
   finding. Agreement is reported net of the noise floor; a shadow that
   disagrees less than the incumbent disagrees with itself has said nothing.
6. **Learn the band from labels, not from a script.** With labelled receipts,
   `chipsocket cuts` returns `lo`, `hi`, how much they close, and an evidence
   digest. `cut_member(score, cuts, negative=, positive=)` is the member on
   those cuts, versioned by what it learned from. Seat it as a shadow first.
7. **Promote on a second day, demote on one call.** A learned member becomes
   primary when a second labelled day's cuts agree. A promoted code member
   that fails an invariant on a live call goes back to shadow on that call.
   The runner does neither for you; it records.
8. **Carry the verdict forward.** When the report says the code member closes
   most inputs at gold agreement, that is a `parser` or `mint` reading for
   [[chip-candidate]]; cite the measures, not the impression. A socket whose
   standing relationship and state turn out to be real graduates to
   [[chip-author]]; one whose model member keeps earning its place stays a
   socket, honestly.

## What the receipts are for

- `closedByCodeShare` and the trigger histogram are what `chip.placement`
  reads; a socketed workload closes the placement loop by construction.
- The harvest file weights inputs by deferral and shadow disagreement; a
  curator commissions the heavy ones into the candidate ledger
  ([[chip-candidate]]), never one line per call.
- Every member on a receipt carries a digest, and a learned member's digest
  covers its evidence, so "which code answered" and "what it was learned
  from" are both on the record.

Package: `pip install chipsocket` (import `chipsocket`; depends only on
`chipspec`). Design: `docs/socket.md`. Agent notes: `AGENTS.md` in the
chipsocket repository.
