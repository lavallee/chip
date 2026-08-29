# chip roadmap

The sequenced bets. Distinct from [`docs/falsification.md`](./docs/falsification.md)
(the conditions under which this program should stop), [`docs/pilots.md`](./docs/pilots.md)
(what a pilot must clear), and [`CHANGELOG.md`](./CHANGELOG.md) (what shipped).

Nothing here is committed to a date. Two of these have a clock on them, and
that is said where it is true.

## Where the project actually stands

Spec 0.6.0 cut surface that production disproved and moved everything
non-normative out of the specification. The library is zero-dependency and
conformance-tested. One host exists (fab, being open-sourced), which means the
portability claim currently rests on a document.

An outside review in August 2026 named three moves. Two are on this roadmap.
The third — renaming the project away from a word owned by AI accelerators and
UI components — is deliberately deferred, not rejected: it is cheap now and
gets more expensive with every adopter, so it should be revisited before any
second host commits to the vocabulary.

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
can execute *anything*: single chip, `observe` class, no state, no effects — a
few hundred lines that binds a circuit, runs it, and writes a receipt.

**Graduation:** a second implementation passes the conformance kit without
importing fab, and open question #2 ("what is the smallest second-host
conformance API") can be answered with a number instead of a guess.

**Boundary:** the minimal host is a proof, not a product. It should be
uncomfortable to use.

## 3. Lead with the ladder

**The problem.** The repository's normative weight is a packaging and
governance contract, and its most interesting idea — that the code-vs-model
boundary is a *position that evidence should move*, in both directions — lives
in one non-normative doc a reader reaches last, if ever. §7 hits a newcomer
with SBOM requirements before they have met the idea.

The spec should stay normative-only; 0.6 was right to hollow it out. The fix is
above the spec, not inside it: publish
[`docs/skill-to-chip.md`](./docs/skill-to-chip.md) as a standalone essay with
the distillation ladder as its figure, and let the README lead with that rather
than with the package layout.

**Graduation:** a reader who arrives cold meets the ladder before the manifest.

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
