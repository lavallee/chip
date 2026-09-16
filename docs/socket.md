# The socket: one contract, several live implementations

Status: design note, 2026-09-16. A convention layered under the spec, not yet
in it. The name is provisional and deliberately electronic: a socket is the
pinout a part is seated in, and a chip is one kind of part that can be seated.
Renaming it is a one-line substitution; nothing below depends on the word.

## The problem this solves

The ladder in [`skill-to-chip.md`](./skill-to-chip.md) says the code-vs-model
boundary is a position that evidence should move, in both directions. Today a
chip package holds exactly one implementation, so the only way to learn whether
a behavior belongs one rung lower is to migrate it and then evaluate. The
evidence arrives after the decision it was supposed to inform.

The same fact is why nobody can plug a chip into existing code. The unit of
adoption is a package bound into an owning system with a scheduler, a policy
gate, and a custody store. Nearly every workload that would benefit from the
ladder is a plain function call inside a program that has none of those.

A socket inverts the order. Several implementations of one contract are live
at the same time. A runtime strategy picks among them per call, every call
writes a receipt saying which one answered and why, and the disagreement
between them is the evidence that moves the boundary. You evaluate before you
migrate, on production traffic, without leaving the program the call lives in.

> Evidence: the busiest workload in one fleet's ledger, a pairwise
> same-event judgment, already runs this way by hand. It has a lexical
> prefilter, a cache, a pinned local model, a lexical fallback, a strict-versus-
> degrade policy, four model variants declared side by side with paired F1
> numbers, and a `decide()` that returns the verdict plus where it came from.
> Every piece of the socket exists there, unnamed, inside one module of one
> project, and a sibling project carries a second copy.

## Definitions

**Contract.** A typed input, a typed output, and invariants that any answer
must satisfy. The contract is the whole public surface. Nothing outside the
socket may depend on which member answered.

**Member.** One implementation of the contract. A member is a pure function
of its input plus at most one gateway call, exactly as a chip implementation
is a pure function of `(signal, state, config, gateway)`. Members come in
three kinds:

- `code`: deterministic, no gateway;
- `model`: a prompt, a result schema, and a gateway profile at some tier;
- `baseline`: the raw model with no envelope, kept so that kill criterion #3
  and the `model-generation` retirement rule have a standing comparator
  rather than a one-off.

A member returns one of three things, and nothing else:

- a **value** that the socket then checks against the invariants;
- an **abstention** with a reason, which is a first-class answer and not a
  failure (the deterministic member of a same-event judge says `undecidable`
  on the band its lexical score cannot separate; that band is the model's
  job);
- a **typed failure** from the closed vocabulary below.

A member MAY also return a **score** beside its value. A score is an ordering,
not a probability. It is what lets a first-success strategy learn its
escalation band from harvested labels instead of guessing a threshold.

**Strategy.** How the socket chooses among members for one call. A closed
vocabulary, for the same reason terminal reasons are closed: a strategy that
can invent its own categories produces receipts that cannot be compared.

**Receipt.** One record per call, in the shape of a chip run receipt, listing
every member that ran, why it ran, what it returned, and what it cost.

**Harvest.** The input of every call is a fixture candidate. The socket
appends it to a harvest file with the receipt reference, the triggers that
fired, and a weight that rises with deferrals and shadow disagreement. A
curator, not the call path, commissions harvested rows into the candidate
ledger of [`candidates.md`](./candidates.md): one ledger line per call would
make replay look like recurrence.

## Strategies

Three, plus one flag.

**`first-success`.** Members are ordered. The first one runs; if it returns a
value that passes the invariants, that is the answer. On abstention or typed
failure the next member runs, and the receipt records the trigger. The
ordering is normally cheapest first, but the strategy does not assume it.

**`shadow`.** One member is primary and answers. Others run on a sampled
fraction of calls, their results are recorded against the primary's, and
nothing they return leaves the socket. A shadow member has a **budget**, not
only a sample rate: a model shadow is metered, and a rate without a budget is
how a background comparison becomes the largest line on the bill.

**`canary`.** A sampled fraction of calls gets a candidate member as primary;
the rest get the incumbent. The receipt marks which. This is the only strategy
under which a member being evaluated can affect an answer, so a canary fraction
is a policy an operator sets, never a default.

**`noise` (flag on `shadow`).** The incumbent runs twice on the sampled
fraction, and the disagreement rate between the two runs is recorded as the
call's noise floor.

> Why a noise floor is not optional. Twitter's Diffy multicast every request to
> a candidate, a primary, and a second identical copy of the primary, and
> reported only differences larger than the primary-versus-copy disagreement.
> A model member is nondeterministic at any temperature that matters; a shadow
> mismatch with no same-member repeat is evidence of sampling, not of
> disagreement. Roadmap item 1 names double-digit judge error as the reason
> every rung verdict is capped at low confidence. This is the cheapest
> instrument that measures it.

What is not a strategy: routing between contracts, loops, forks, retries with
state, or anything that needs a graph. Selection among members of one contract
is the whole scope, and kill criterion #6 is the line.

## Triggers: why a member ran

A closed vocabulary, recorded on every attempt in the receipt.

| Trigger | Meaning |
|---|---|
| `primary` | It was the strategy's first choice for this call |
| `abstained` | The prior member returned an abstention |
| `invariant` | The prior member's value failed the contract's invariants |
| `schema` | The prior member's result did not parse or validate |
| `transport` | The prior member's gateway call failed: timeout, rate limit, provider exhausted |
| `error` | The prior member raised something untyped; recorded, never propagated |
| `budget` | The prior member was skipped because its budget was spent |
| `sampled` | A shadow, canary, or noise run selected by the strategy's sample |

Two of these carry most of the information. `abstained` and `invariant` are
where the boundary lives: an input that the code member could not decide, or
decided wrongly by the contract's own test, is the fixture with the most to
say about where the line should move. `transport`, `schema`, and `error` are
operations, and a socket whose escalations are mostly those has a gateway
problem, not a placement problem. Keeping them separate is what lets a placement report tell
the two apart.

> Evidence: one fleet's busiest judgment lane runs a thinking model under a
> 160-token cap. The model spends its budget thinking, the JSON never arrives,
> the parser returns nothing, and the row is judged again next tick. Roughly
> two gateway calls per verdict, for months. Under a socket every one of those
> is a `schema` trigger on the receipt, visible on the first day, and none of
> them would have been mistaken for a hard input.

## The receipt

One per call. Shaped as a chip run receipt (spec §13) so that a host that
already persists those persists these, with one extra block:

```jsonc
{
  "socket":   "<contract id>",
  "strategy": "first-success",
  "answeredBy": "code:claim-rules@sha256:…",
  "attempts": [
    { "member": "code:claim-rules@sha256:…", "trigger": "primary",
      "outcome": "abstained", "reason": "no-entity-no-number",
      "score": 0.41, "latencyMs": 2, "costUsd": 0 },
    { "member": "model:mid@profile:claims-mid", "trigger": "abstained",
      "outcome": "value", "tuple": "<evaluated tuple key>",
      "latencyMs": 812, "costUsd": 0.00012 }
  ],
  "shadows": [
    { "member": "model:gold@profile:claims-gold", "trigger": "sampled",
      "agrees": false, "outcome": "value", "costUsd": 0.0031 }
  ],
  "noise": { "member": "model:mid@profile:claims-mid", "agrees": true },
  "harvest": "candidates.jsonl#<line ref>"
}
```

Rules:

- **Every attempt is recorded, including the ones a later member repaired.**
  A value that failed invariants and was replaced is still on the receipt.
  Guardrails-style `fix` actions that mask the failure they repaired are the
  pattern to avoid.
- **A shadow or noise result never reaches the caller.** The socket's own
  comparison machinery must be unable to fail the call: a shadow that raises
  is recorded as a `transport` outcome and the primary's answer stands. This
  is somm's rule for workload handlers, applied one layer up.
- **Values in the receipt pass through the same taint and redaction path as a
  chip response.** GitHub Scientist's `clean` hook is the precedent: what goes
  into the record is a transformed value, and the transform is declared.
- **The receipt is correction-by-supersession**, like every other receipt.

## From receipts to placement

Receipts are the placement data. Over enough calls they answer, per socket:

- what fraction of inputs the code member closes without abstaining;
- on the fraction it does close, how often it agrees with the gold shadow,
  net of the noise floor;
- on the fraction it abstains on, how often the cheap model agrees with gold,
  net of noise;
- which trigger dominates, and whether it is a boundary trigger or an
  operations trigger.

`chip.placement` reads exactly these measures. The socket is the instrument
that produces them by construction instead of by scanning a ledger after the
fact, which is what closes roadmap item 4.

**Promotion** of a member to primary is a rung transition and is gated the way
[`skill-to-chip.md`](./skill-to-chip.md) already says: non-inferior on the
held-out suite, with the suite now drawn from the harvest. Two priors are
worth adopting as starting thresholds and revising on evidence:

- a model member replacing a larger one: at least fifty calls in shadow with
  agreement at or above the incumbent's own noise-adjusted agreement;
- a code member replacing a model member: agreement at or above 99% on the
  inputs it does not abstain on, **and** the harvested inputs cover the
  observed variation, stated as a coverage measure rather than a call count.

> Why coverage and not count. The one published program with production
> numbers for this ladder (Progressive Crystallization, July 2026, one author,
> one deployment) promotes on run counts and consistency, and names "pattern
> under-observation triggers premature promotion" as its own failure mode. The
> program-synthesis literature says the same thing about learning a function
> from a small static example set. Rule 4 of the placement rubric, repetition
> routes the ladder, is a coverage statement and should be measured as one.

**Demotion** is a circuit breaker, not a review. A promoted code member that
fails an invariant on a live call is moved to shadow on that call, and the
receipt says so. Retirement was already allowed to be ungated in §13.1 because
removing authority is cheap; this is the same asymmetry applied to placement.
A member moves down on one piece of evidence and up on a suite.

## What a socket is not, and how a chip is one

A socket has no standing observation relationship, no cross-run state, and no
authority contract. It is called; it answers; it records. By the admission
rule in spec §4.1 that makes it a tool, and that is correct. The socket is the
primitive **below** chip.

A chip is a socket seated in an envelope: a promise, ports, installation
state, effects, and an authority ceiling. The hybrid class in §10.3, a
deterministic envelope with at most one gateway stage, is a chip whose socket
has one `code` member and one `model` member in `first-success`. Nothing in
the spec changes for that case. What the socket adds is that the same envelope
can hold several members and a strategy, and that the stage list in
`implementation.stages` becomes one member's stage list rather than the
package's.

Two spec consequences to decide before this reaches the spec, not now:

- **The one-gateway-stage rule.** Escalating from a code member to a model
  member is still one gateway call per run. Escalating from a mid-tier model
  member to a gold one is two. The proposal is that the rule applies per
  member, escalation is the socket's business, and the receipt records every
  attempt. A run with two attempts is not a chip with two stages.
- **Implementation identity.** A package's digest today identifies one
  implementation. Under a socket it identifies the contract plus the member
  set plus the strategy; each member carries its own digest, and the evaluated
  tuple keys on the member that answered.

The falsification doc allows that chip's durable core might turn out to be
only the governance envelope. The socket is the other candidate: the seat may
outlive the part. Both should be stated as live hypotheses.

## The runtime, and why it is the second host

The socket needs a runner: something that holds members, applies a strategy,
calls the gateway, writes receipts and harvest. A runner that does that for a
plain function inside an ordinary Python program is a few hundred lines, and
it is also roadmap item 2, the minimal second host, in a form people would
adopt rather than merely a proof.

```python
from chipsocket import contract, model        # `socket` is a stdlib module; the
                                              # distribution is `chipsocket`

@contract(input=Claim, output=Verdict, strategy="first-success")
def admissible(claim: Claim) -> Verdict | Abstain:
    ...                                       # the existing code, unchanged

admissible.member(model(profile="claims-mid",  result=Verdict))
admissible.shadow(model(profile="claims-gold", result=Verdict),
                  sample=0.03, budget_usd_daily=2.0, noise=True)
```

The runner exists: [`chipsocket`](https://github.com/lavallee/chipsocket),
v0.1, with the receipt schema `chip.socket-receipt/v0alpha1`. Boundaries:

- it depends on `chipspec` for envelopes, receipts, taint, candidates, and
  placement, and on nothing else;
- it never imports fab, which is what makes it a materially different second
  host for kill criterion #2;
- it is not a runtime for chips: it has no scheduler, no policy gate, no
  custody store. A chip host that wants sockets embeds this runner behind its
  own envelope.

The roadmap said the minimal host should be uncomfortable to use, a proof and
not a product. That boundary is withdrawn here. The proof and the adoption
path can be the same artifact as long as the conformance kit is still what it
passes.

## The meter: somm

Somm's vision already describes this loop under the name "workloads climb",
and its workload-handler mechanism is the seat for it. The integration is
inside somm's existing surfaces, per the July 2026 decision, and never a new
broker:

- the runner registers as a workload-handler **kind**; a socket's `code`
  member serves the calls it can and **declines** the rest, and the provider
  chain answers what it declined under the **same workload id**, so "should
  this still be a model call" is a `GROUP BY provider`;
- `model` members are ordinary somm calls with the gateway profile as the
  route, so cost, latency, and outcome land where they already land;
- shadow and noise runs are recorded as calls with `observation_role` set and
  `source_call_id` pointing at the primary, which are columns somm already
  has;
- the contract's output type is written to the workload's
  `output_schema_json`, which closes somm's own "0 of 166 workloads declare a
  contract" gap for every socketed workload;
- one gap on somm's side: `generate_structured` does not yet let a caller set
  `observation_role` or `source_call_id`, so until it does, shadow calls are
  distinguishable by the session id they share with the primary and by the
  receipt, not by the somm row alone;
- somm remains the meter and the memory. It does not own members, strategies,
  or promotion. The placement verdict is derived from somm's record by
  `chip.placement` and stays chip's.

> Evidence: somm's shadow evaluation was configured for three workloads in one
> fleet, gold model named, sample rate set, 216,000 shadow candidates queued,
> and zero evaluation results were ever produced. The instrument was declared
> and never wired to a strategy. The socket is the strategy it was missing.

## Pilot

The first socket is a **claim admissibility** judgment: given one extracted
claim and its source, decide `verified`, `dropped`, or `needs_review` with a
short reason. It is chosen because the split is honestly unknown, the volume
is real, the labels exist, and three sibling projects produce claims with no
admissibility gate at all. Details, numbers, and file paths are in the private
pilot note; the shape is:

- **members:** a `code` member of rules the lane already half-implements
  (concrete entity or number present, opinion and navigation filters, a
  relevance-score override), a `model` member on a non-thinking mid-tier
  profile, a `model` member on the gold profile somm's shadow config already
  names, and a `baseline` member;
- **phase 0, shadow with noise, no answers change:** the incumbent stays
  primary; the code member and gold member shadow at a budgeted sample; the
  noise floor is measured before any agreement number is read;
- **phase 1, first-success with the code member primary,** on the calls
  phase 0 showed it closes at gold-agreement above the incumbent's own;
- **phase 2, promotion or not,** by the thresholds above, against a human-
  graded anchor set drawn from the harvest and not from the lane's own past
  verdicts.

**Graduation:** the placement report for this socket is regenerable from its
receipts alone; the code member's share of closed calls and its noise-adjusted
agreement are numbers, not estimates; the sibling projects can adopt the
contract by importing the package; and total gateway calls per verdict fall
below one.

**Kill:** the noise floor of the mid-tier model is so high that no agreement
number clears it; or the code member closes under a fifth of inputs after the
harvest covers a month of variation; or the runner needs anything from fab.

The second socket is the same-event judge, whose hand-rolled form is described
above. It is chosen second because its split is largely measured already, so
it tests whether the socket can absorb a mature workload without losing what
that workload learned, and because it runs on a free local model at ten
thousand calls a day, which makes it the portability test with no money in it.

## What this changes in the roadmap

- Item 2, the minimal second host, becomes the socket runner, and its
  "uncomfortable to use" boundary is withdrawn.
- Item 4, closing the placement loop, is closed by construction for socketed
  workloads: the receipts carry the measures.
- Item 1, suite adequacy, gains an instrument (the noise floor) and a
  criterion (harvest coverage) but is not closed; the anchor set still has to
  be human-graded.
- Open question #9, the name, is closed: chip stays. The trigger for
  renaming was a second host adopting the vocabulary, and the second host is
  now this runner.

## Open questions

1. Does `canary` earn its place in v1, or is `shadow` plus a manual promotion
   enough until a socket has been promoted once by hand?
2. Should a member's score be required, or optional with `abstained` as the
   only escalation signal from a scoreless member?
3. Where does the harvested input's taint marker live when the harvest is
   read back as a fixture months later?
4. When a chip's socket has three members, is the package one artifact with
   three digests or three artifacts with one manifest? The evaluated-tuple
   rules in §21 need one answer before this reaches the spec.
