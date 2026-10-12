# chip roadmap

The sequenced bets. Distinct from [`docs/falsification.md`](./docs/falsification.md)
(the conditions under which this program should stop), [`docs/pilots.md`](./docs/pilots.md)
(what a pilot must clear), and [`CHANGELOG.md`](./CHANGELOG.md) (what shipped).

Nothing here is committed to a date. Two of these have a clock on them, and
that is said where it is true.

Numbers are stable identifiers, not a sequence: item 3 (lead with the ladder)
shipped and was moved to the changelog, and the gap stays so that references
to items by number elsewhere keep meaning what they meant.

## Where the project actually stands

Spec 0.6.0 cut surface that production disproved and moved everything
non-normative out of the specification. The library is zero-dependency and
conformance-tested. One host exists (fab, being open-sourced), which means the
portability claim currently rests on a document.

An outside review in August 2026 named three moves. Two are on this roadmap.
The third — renaming the project away from a word owned by AI accelerators and
UI components — was deferred until a second host committed to the vocabulary,
and closed on 2026-09-16 when that host was chosen: the name stays.

The same day added a primitive *below* chip, the socket
([`docs/socket.md`](./docs/socket.md)): one contract with several live
implementations, a runtime strategy, and a receipt per call. It reshapes items
2 and 4 below and is the plug-into-existing-code path the review said was
missing.

As of 2026-10-12 the socket runner has live receipts: gabe's same-event judge
writes about 18,000 a day through it, and barnowl runs a phase-0 pilot on its
claim-verification lane. `chipspec` itself is still not on PyPI — the
trusted-publisher registration for `lavallee/chip` is the one external step
only the owner can take, and it is pending.

## 1. Say what makes an evaluation suite adequate

**The problem.** Everything load-bearing gates on "the held-out suite passes":
tuple changes, rung transitions, retirement, and promotion above `observe`.
Spec §21 enumerates fixture *categories* thoroughly and says nothing about
suite *adequacy* — no minimum size, no provenance rule for held-out material,
no grader specification, no refresh cadence. Small harvested suites plus strong
promotion claims is an overfitting machine, and LLM-as-judge grading has
documented double-digit error rates.

This is the contract's strongest guarantee resting on its least-specified
clause, and it is now measurable: `chip.placement` caps *every* rung verdict at
low confidence for exactly this reason, so the rubric's output is currently all
proposals and no findings.

**Graduation:** a rung verdict can reach medium or high confidence from
declared contracts alone; promotion above `observe` cites a suite that meets a
stated adequacy bar rather than merely existing.

**Boundary:** adequacy is a normative addition to §21, not a new subsystem. If
it needs machinery beyond a declaration and a check, it has grown wrong.

## 2. A minimal second host

**The problem.** Kill criterion #2 says that if no materially different second
host can implement the public contract without depending on fab internals
within a year, chips become a fab feature and the portability claim is retired.
That is the thesis test, and the clock is running.

The fastest path is not more contract surface. It is the smallest runner that
can execute *anything*. That runner exists:
[`chipsocket`](https://github.com/lavallee/chipsocket), the socket runner
described in [`docs/socket.md`](./docs/socket.md). It holds a contract's
members, applies a strategy, writes receipts and harvest, passes its own test
suite, and depends on `chipspec` and nothing else. It never imports fab, which
is what makes it materially different: a library inside an ordinary program,
not a scheduled owning system.

**Graduation (remaining):** the runner passes the conformance kit
(`chip.conformance`) rather than only its own suite, and ships as a tagged
release on PyPI beside `chipspec`. Open question #2 ("what is the smallest
second-host conformance API") is then answered with a number.

**Boundary (revised):** the earlier boundary — a proof, not a product,
uncomfortable to use — is withdrawn. The proof and the adoption path are the
same artifact, as long as the conformance kit is still what it passes and it
never grows a scheduler, policy gate, or custody store.

## 4. Close the placement loop

**The problem.** `chip.placement` decides where a behavior belongs.
`chip.candidates` records what is worth minting. Nothing yet carries a verdict
from one to the other automatically, so the loop that makes the ladder
*bidirectional* — receipts and telemetry telling you when a chip should migrate
rungs or retire — is still assembled by hand.

Two prerequisites landed in somm (schema 23): calls now record where they came
from, so telemetry joins to source, and `somm doctor` reports the workloads
with no declared output contract. The remaining work is the assessment tool
itself: gather evidence, run the rubric, commission candidates through
`source_limits`, and re-run it cheaply enough that placement is a standing
report rather than an expedition.

For a socketed workload the loop closes by construction: every receipt
records which member answered, why, and what the shadow said, and
`chipsocket.report.summarize` folds a receipt file into the measures the
rubric reads — closed-by-code share, boundary versus operations triggers,
shadow agreement net of noise. What remains is the bridge: a function that
turns a receipt stream into `chip.placement.PlacementEvidence` (a daily series
of calls, failures, and envelope failures, plus distinct inputs) so a socket's
placement verdict is one call away from its receipts. The first socket pilot
(a claim-admissibility judgment, [`docs/socket.md`](./docs/socket.md) §Pilot)
is the test of that claim.

**Graduation:** a placement report is regenerable on demand and its verdicts
are traceable to the receipts that produced them.

**Boundary:** the rubric stays here and stays pure. Evidence gathering lives in
whatever tool owns the fleet, and chip never learns to scan.

## 5. The first chips

D2 (2026-07-21) settled what these should be: deterministic attention-profile
observers before any judgment chip. A budget-sentinel/circuit-breaker over the
calls ledger satisfies the admission rule cleanly, is cheap to evaluate with
fixtures, and needs no model. The hand-run confirmed it — the largest observed
loss was 495,130 calls that never reached a provider, invisible to any
cost-ranked detector, and it ran for ten days before anyone noticed.

Judgment chips wait on harvested fixtures and on item 1.

**Graduation:** the two pilots in [`docs/pilots.md`](./docs/pilots.md) clear
their bar against a skill-only baseline.

## 6. Learn the band, then receipt what was learned

**The problem.** The first learned code member exists — gabe's lexical cuts
(answer DIFFERENT below 0.15, SAME at or above 0.75, abstain between) — and it
was derived by a script over one labelled day and typed into the module as two
constants. The evidence that produced the boundary is not attached to the
member that enforces it, so a second labelled day that moves the cuts has
nothing to supersede but a comment.

chipsocket 0.2 ships `learn.cuts` (the cut points where a constant beats the
model at a stated precision, read off receipts and labels) and `cut_member`
(a `code` member built from those cuts whose digest includes the digest of the
receipts and labels it was learned from). A learned member is then a receipted
artifact like any other: where it came from is on the record, and replacing it
is correction by supersession.

**Graduation:** a second labelled day in gabe confirms or moves the cuts
through the tool, not by hand, and the member's digest changes with the
evidence.

**Boundary:** the learner reads scores and labels and emits cuts. It does not
train a router, fit a classifier, or touch a prompt; that is what the
neighbours in [`docs/related-work.md`](./docs/related-work.md) are for.

## Not planning

- A package registry, visual builder, or automatic promotion. None is a pilot
  gate and none is needed to test the thesis.
- Scheduling, routing, replay, or graph semantics broad enough to recreate n8n
  or Temporal. That is kill criterion #6, not a feature request.
- Making chip depend on any particular host, gateway, or scanner.

## Keeping this file honest

When an item ships, move it to `CHANGELOG.md` and delete the entry. When an
item turns out to be wrong, say so here with the reason rather than deleting
it — the record of what was abandoned is worth more than a tidy list, and this
project's whole argument is that published falsification beats advertising.
