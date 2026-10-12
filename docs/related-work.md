# Related work: where the socket and the ladder sit

Status: survey, 2026-10-12. Non-normative. Each entry says what the thing does,
what it shares with chip or the socket, and what it lacks or does differently.
Nothing here is a claim that a neighbour is worse; most of them solve a
different problem, and several compose with this one.

## Workflow DSLs with typed decisions

### AgentRun (Parcha)

[AgentRun](https://github.com/Parcha-ai/agentrun) (Apache-2.0, beta;
`@parcha/agentrun-dsl`, `@parcha/agentrun-jev`, `@parcha/agentrun-pi`) is a
workflow DSL for the agents a team already runs. A workflow is a tree of
typed nodes: Jev decisions (`judge`, `route`, `pick`, `sift`), `agent` calls,
`code`, `call` with deadlines, control flow (`chain`, `map`, `parallel`,
`loop`, child `workflow`), and terminal `escalate` / `report` / `artifact`.
Workflows are written with a TypeScript builder over Zod schemas or as JSON;
the host supplies adapters (`runNode`, `runEffect`, `createJevRunner`) and
keeps models, permissions, and budgets. Outputs are validated against declared
schemas, `dryRunWorkflow` and `runWorkflowSlice` exercise mechanics without
live judgments, and `workflowSha256` gives a workflow an identity.

Shared: typed judgments inside deterministic structure, schema-validated
outputs, host-owned authority. Lacks: a receipt per call, shadow or noise runs,
a harvest, and any learning beyond reusing the defined steps.

Position: AgentRun is a graph *above* the call. Chip refuses graph semantics
on purpose (kill criterion #6 in [`falsification.md`](./falsification.md)),
and the socket is the primitive *below* one call. A Jev `judge` node is
exactly what `chipsocket.typesafe` seats as a `model` member, so a socket can
sit inside an AgentRun step and the two compose rather than compete.

### TypeSafe Jev ("System One")

[Jev](https://typesafe.ai) (released 2026-09-15) answers typed questions
(`Noul`, `Score`, `Choice`) about a state and returns probabilities with a
confidence, rather than prose. It is already a gateway in
`chipsocket.typesafe`. The probability is what lets a member *abstain* on a
flat distribution instead of guessing, which is the socket's escalation
signal; the band where it should abstain is read off labels with
`chipsocket.report.band`.

## Shadow evaluation on production traffic

### LiteLLM auto-router shadow evaluations; Ramp router shadow models

[LiteLLM](https://docs.litellm.ai/blog/auto-router-shadow-evaluations) samples
a share of one key's live traffic, replays it through a candidate router, and
has a blind judge compare the answers; the shadow response never reaches the
client. [Ramp's router](https://router.ramp.com/docs/optimizations/shadow-models)
mirrors requests to alternative models and records the outputs without
affecting routing or latency.

Shared: the `shadow` strategy, sampled and never returned to the caller.
Lacks: a noise floor (the same member run twice so a disagreement has a bar to
clear), `code` members, a harvest, and a placement verdict; both are hosted
product features rather than libraries a call can be seated in.

## Routers and cascades

### RouteLLM, LLMRouter, cascade-routing

[RouteLLM](https://github.com/lm-sys/RouteLLM) (Apache-2.0) serves and
evaluates trained routers that send a query to a cheaper or dearer model;
[LLMRouter](https://github.com/ulab-uiuc/LLMRouter) adds threshold routers
trained on difficulty; [cascade-routing](https://github.com/eth-sri/cascade-routing)
(ETH SRI) runs cascades, routing, or both around user-supplied cost and
quality predictors.

Shared: `first-success` is a cascade. Differs: they route *between models* by
predicted difficulty. The socket's first member is deterministic code that
answers what it can and abstains with a score on the rest, and the band it
abstains on is read off harvested labels (`chipsocket.report.band`,
`chipsocket.learn.cuts`) rather than predicted by a trained router.

### Cascades with abstention; learning to defer

["Cost-Saving LLM Cascades with Early Abstention"](https://arxiv.org/abs/2502.09054)
asks whether small models at the front of a cascade should be allowed to
abstain early, and tunes the thresholds as a multi-objective problem. The
learning-to-defer literature (for example
[L2D-Clinical](https://arxiv.org/abs/2604.13285), and conformal deferral in
TMLR 2026) learns when a cheap classifier should hand off to a dearer one.

Shared: abstention as a first-class answer in a cascade. Differs: the socket
makes abstention a receipt *outcome*, recorded with its reason and score on
every call, rather than a modelling assumption; the deferral rule is then
something a report can show and a label set can move.

## Judge reliability

["Reliability without Validity"](https://arxiv.org/abs/2606.19544) and
["The Geometry of LLM-as-Judge"](https://arxiv.org/abs/2606.03043) show that
raw judge agreement overstates discriminative ability without chance
correction, and that run-to-run variance is large enough to matter. This is
why the socket's `noise` flag exists (the answering member re-runs on the
sampled fraction, and agreement is reported net of that floor) and why
`chip.placement` caps every rung verdict at low confidence until suite
adequacy is defined (roadmap item 1).

### Diffy and GitHub Scientist

Both are already cited in [`socket.md`](./socket.md). Twitter's Diffy
multicast each request to a candidate, a primary, and a second copy of the
primary, and reported only differences larger than primary-versus-copy; that
is the noise floor. GitHub's Scientist ran a candidate beside the control and
passed every value through a declared `clean` before recording it; that is the
socket's `clean` hook.

## Decision models

### DMN and rules engines

Camunda's pattern keeps the model as a preprocessing layer ahead of a DMN
decision table, so the business decision itself is deterministic and
traceable; a QCon Boston 2026 session ("Decision Models in Agentic
Architectures") uses decision models as agent skills and as guardrails in
model pipelines. Machine-learned scores enter the table as inputs.

Shared: a deterministic envelope around a probabilistic input, and an audit
trail that ties an outcome to the rule rows and inputs that produced it.
Differs: there is no notion that the boundary between table and model should
*move*, and no shadow evidence that would say when.

## Typed outputs and optimizers

### DSPy, Instructor, BAML

[Instructor](https://github.com/instructor-ai/instructor) is the lightest typed
output layer over Pydantic. [BAML](https://github.com/BoundaryML/baml) puts
prompts and types in a versioned contract language with generated clients.
[DSPy](https://github.com/stanfordnlp/dspy) optimizes prompts and few-shot
examples against a metric, and its `BootstrapFinetune` distils a teacher into
a student model.

Position: all three improve the *model member* — its parsing, its prompt, or
the model behind it. The socket decides whether a model member should exist
for a given band of inputs at all, and records the evidence either way. A
DSPy-optimized program is a fine `model` member; a BAML function is a fine
`result` contract.

## What none of them do

- A receipt per call that records every attempt, including the ones a later
  member repaired.
- Abstention as a recorded outcome with a reason and a score, not a modelling
  assumption.
- A noise floor measured on the same traffic as the comparison.
- A harvest of inputs weighted by deferral and shadow disagreement, so the
  held-out suite is drawn from the cases with the most to say.
- A placement rubric that emits negatives (`no-standing-relationship`,
  `no-judgment-stage`, `undecidable`) as readily as positives.
- A learned code member whose digest includes the receipts and labels it was
  learned from (`chipsocket.learn`, 0.2.0), so the boundary's position is
  itself receipted.
