# Chips and circuits

Status: `candidate specification`  
Version: `0.6.0`  
Date: `2026-07-25`  
Implementation status: `v1 experiment in progress (Fab host)`  
History: v0.2.0 followed an independent adversarial model review; v0.3.0 was the
first published edition, relocated to this repository; v0.4.0 folds in
implementation-informed clarifications from the first host (Fab) and first pilot;
v0.4.1 adds host-review clarifications from the first host implementation;
v0.4.2 adds binding chipParameters; v0.5.0 admits the **delegation profile** of
the contract (agent-invoked activation, partitioned state, lifecycle telemetry)
alongside the original **attention profile**, adds non-contractual manifest
hints and an `authoredAgainst` model-generation stamp, and introduces host-owned
environment profiles as a third resolution layer between manifest and binding;
v0.6.0 is the first edition shaped by production receipts rather than design
intent — it collapses the two receipt tiers into one shape, closes the terminal
reason vocabulary, reduces the authority decision to an effective ceiling plus a
reason, promotes packaging/resolution and outcome receipts to normative, and
moves six non-normative sections to `docs/`. It removes surface; see the
changelog for the migration.

## Abstract

A **chip** is a portable, versioned operational component that observes declared
signals, applies stateful judgment, and produces bounded responses under an
explicit authority contract.

A **circuit** composes chips for a project or operating context. A **binding**
resolves that portable composition to actual sources, models, adapters,
credentials, policies, and owners. A **run** is one activation. A **receipt**
records what happened and why. A **board** projects active circuits, runs,
evidence, and decisions without becoming their source of truth.

The primitive is intended to make durable operational behavior easier to share
than today's skill bundles. Skills remain useful for agent dialogue, routing,
teaching, and harness adaptation. They become thin wrappers around stable chips
and circuits when the underlying behavior can be specified, executed, and
evaluated independently of a particular model generation.

Canonical home: github.com/lavallee/chip. The reference contract library
(`chipspec` on PyPI, import `chip`) implements the manifest, envelope,
authority, receipt, and conformance surfaces of this document.

The core execution pattern is:

```text
deterministic sensing/state
  -> optional probabilistic judgment through Somm
  -> deterministic validation/policy
  -> bounded effect dispatch
  -> receipt/outcome feedback
```

The contract is designed for portability; portability is not yet an observed
property. Version 1 has one experimental host: **Fab**, an orchestration
runtime, reusing its sandbox, lease, budget, attempt, and receipt machinery. A
second host is a later thesis test, not a graduation checkbox for the first
prototype.

## 1. Motivation

Long-running agents and projects need reusable ways to pay attention and act:

- when a public agency posts a new report, determine whether it is material and
  prepare evidence-linked follow-up;
- when a repository dependency changes, assess exposure and propose a bounded
  response;
- when work in progress or a pull request reaches a decision boundary, gather
  proof and provide a legible sign-off packet;
- when telemetry, feedback, or outcomes cross a threshold, investigate, act
  within policy, or abstain; and
- when an accepted change fails to produce the intended outcome, reopen the
  underlying assumption.

Current skill packages often combine several distinct things:

- durable operational logic;
- workflow sequencing;
- model instructions and reminders;
- host-specific tool names and installation glue;
- state, retries, cursors, and effect handling;
- domain doctrine and interaction style; and
- scaffolding needed because a particular model or harness cannot reliably do
  the task unaided.

As models and harnesses change, the scaffolding can become stale or obstructive
while the useful operation remains. Chips separate the stable operational
contract from model- and host-specific implementation choices.

## 2. Design goals

The specification aims to make operational behavior:

1. **Portable.** A chip contract is not coupled to one agent, model, repository,
   workflow engine, or UI.
2. **Composable.** Typed ports permit chips to form circuits without prompt-level
   glue.
3. **Durable.** Deterministic state and policy surround probabilistic work.
4. **Inspectable.** Every activation, judgment, abstention, and effect is
   receipt-bearing.
5. **Bounded.** Authority, budgets, network access, secrets, effects, and human
   gates are declared and enforced outside model prose.
6. **Testable.** Fixtures, quiet cases, adversarial cases, held-out evaluations,
   and host conformance are part of the package contract.
7. **Replaceable.** Model, prompt, code, and adapter implementations can evolve
   without silently changing the public promise.
8. **Shareable.** A package carries enough provenance, documentation, examples,
   and compatibility metadata to operate safely outside its originating project.

## 3. Non-goals

Version 1 is not:

- a general visual workflow builder;
- a replacement for n8n, Temporal, Kestra, Windmill, or Fab;
- a new canonical task, issue, claim, evidence, or project database;
- a synonym for tool, skill, workflow, agent, plugin, or MCP server;
- a prompt marketplace;
- a way to grant LLM prose direct production authority;
- a guarantee that a probabilistic judgment can be replayed identically;
- a universal package runtime or mandatory implementation language;
- a reason for the originating research service to own capture, execution,
  project intent, skills, or production changes; or
- a requirement to convert genuinely dialogic or model-native skill behavior
  into executable components.

### 3.1 Experimental v1 core

Only the following surface is normative for the first experiment:

- one host: Fab, in a disposable credential-free sandbox;
- two activation profiles (see below): the **attention profile** — pull-only
  activation by an owning-system schedule outside the circuit — and the
  **delegation profile** — agent-invoked activation mid-workflow;
- one read-only source adapter and, if authorized, one taint-aware
  owning-system idea adapter;
- a chip contract containing promise, typed ports, effect declarations, state
  schema, authority ceiling, limits, and evaluated model/harness tuples;
- deterministic and hybrid implementations, with at most one Somm stage (a
  judgment stage executed through an LLM gateway; reference: Somm);
- installation-scoped state held by Fab, either `single-flight` or, for
  delegation-profile map/cache chips, `partitioned(<keyField>)` (§9);
- linear circuits containing at most three chips, with no nesting, feedback
  edges, push delivery, webhooks, or cross-circuit routing;
- target-side effect deduplication and single-shape Fab receipts; and
- two pilots: publication triage and PR sign-off.

Registry, chipset distribution, multiple hosts, general scheduling, nested or
cyclic circuits, live project installation, and whole-suite skill decomposition
are later hypotheses. Their sections document design intent and kill criteria;
they are not v1 implementation scope.

**Two activation profiles.** The original contract centered on *governed
observation*: an owner-side schedule or manual guarded action emits an
activation signal and the chip pays attention (the **attention profile**). v0.5
admits a second, symmetric path for *governed delegation*: a harness or agent
operating under the owning system's authority MAY invoke an installed chip
mid-workflow (**delegated activation** — the **delegation profile**). A
delegated activation is receipted identically to a scheduled one, counts against
the same limits and budgets, and carries the invoking agent's identity in the
signal's authority context (§8.1). Both profiles remain strictly pull/invoke:
there are still no timers, webhooks, event subscriptions, background workers, or
push delivery inside the circuit. Delegated activation is an invocation of an
*already installed* chip; it grants no new authority and never bypasses the
effect-class gate (§14).

## 4. Vocabulary and relationships

| Term | Definition |
|---|---|
| **Chip** | Versioned package with one public operational promise, typed ports, state and authority declarations, implementation, tests, and receipts |
| **Port** | Named, schema-bound signal input or response output |
| **Stage** | Internal implementation step: deterministic code, Somm judgment, adapter call, validation, or policy |
| **Circuit** | Versioned directed composition of chip references and port connections |
| **Binding** | Environment-specific resolution of circuit parameters, adapters, model profiles, secret references, owners, and authority ceilings |
| **Installation** | An enabled circuit binding in a named project or operating context |
| **Run** | One activation of an installed circuit, whether it acts, abstains, or finds nothing new |
| **Receipt** | Append-only record binding inputs, versions, stage results, policy decisions, effects, cost, and outcome references |
| **Chipset** | Distribution bundle of related chips, optional circuits, wrappers, examples, and doctrine; not itself an executable composition |
| **Wrapper** | Thin skill, command, or UI adapter that selects/invokes chips and conducts host-specific interaction without owning their operational logic |
| **Host** | System that resolves bindings, runs implementations, enforces policy, and writes receipts; Fab is the only experimental v1 host |
| **Board** | Human/agent projection over installed circuits and decisions; never the canonical runtime or evidence store |

```text
                         distribution
                   +--------------------+
                   |      chipset       |
                   | chips + wrappers   |
                   +---------+----------+
                             |
                             v
signal source -> [ chip ] -> [ chip ] -> typed response/effect request
                    \___________/
                       circuit
                          |
               environment binding
                          |
                 host -> run -> receipt -> outcome
                          |
                      /board view
```

### 4.1 Chip versus adjacent primitives

| Primitive | Primary question |
|---|---|
| Tool | What operation can be called now? |
| Skill | How should a model approach this kind of task? |
| Workflow | In what order should selected work occur? |
| Agent | Who holds a continuing role, context, and authority? |
| Chip | What should this project notice, judge, and do consistently? |
| Circuit | How are several operational promises connected here? |

The same implementation may appear behind more than one primitive. The public
contract determines which one it is.

A candidate qualifies as a chip only when an installation declares an ongoing
observation relationship to a signal class or the package owns durable
cross-run state, **and** it produces a bounded response under an authority
contract. Signal delivery remains host/owner work. A stateless operation called
only on demand remains a tool even when it creates evidence or a receipt.

## 5. Normative language

`MUST`, `MUST NOT`, `SHOULD`, `SHOULD NOT`, and `MAY` are normative.

The initial schema identifier is `chip.spec/v0alpha1`. It is deliberately not a
claim of ecosystem standardization. Normative host requirements in v1 refer to
Fab's experimental chip-run profile. Host-neutral language expresses a target
contract until a second implementation proves it portable.

## 6. Atomicity: one operational promise

A chip MUST state one externally understandable and falsifiable operational
promise.

Good examples:

- “When this publication source yields a new in-scope report, emit an
  evidence-linked materiality assessment or a quiet receipt.”
- “Given a pull request evidence snapshot, emit a freshness-bound sign-off
  assessment without merging.”
- “When a dependency release changes the supported compatibility range, emit a
  tested draft-update proposal within the configured budget.”

Bad examples:

- “Operate the project.”
- “Do research, write the story, publish it, monitor reaction, and optimize the
  newsroom.”
- “Call GitHub.”

Atomicity is measured at the public promise, not by line count or number of
internal functions. A chip MAY contain sensing, normalization, judgment,
validation, and response stages when they jointly satisfy one promise. If two
parts have independent activation, authority, lifecycle, or reuse value, they
SHOULD be separate chips connected in a circuit.

Version 1 chips MUST NOT contain other chips as internal stages. Composition is
visible at the circuit layer. This prevents recursive packages from hiding
authority and version boundaries.

## 7. Chip package contract

A chip package MUST contain:

1. a manifest conforming to the current schema;
2. one or more implementation artifacts;
3. input, output, state, and effect schemas;
4. documentation of the operational promise and non-goals;
5. at least one positive, quiet/abstain, failure, and adversarial fixture;
6. conformance and evaluation declarations;
7. license, source coordinate, content digest, build provenance, and dependency
   inventory or SBOM;
8. migration declarations for persisted state and active circuits; and
9. examples that do not require production credentials.

A package MUST NOT include credentials, mutable unpinned remote code, or an
undeclared network dependency.

The public compatibility contract is limited to the operational promise,
ports, state schema, effects, authority, limits, and evaluated implementation
tuples. An implementation MAY report internal stages for security inspection
and receipts, but those stages are non-contractual. The stage decomposition is
not part of what a circuit consumes and MUST NOT become scaffolding that a
future model is forced to preserve.

A manifest MAY carry an optional `hints` block: accretive, non-contractual
annotations keyed by surface or harness (for example
`hints.harnesses.<name>.phrasing` or `hints.models.<generation>.notes`). Hints
capture harness-specific phrasings, translations, and per-model-generation notes
that help a host or wrapper drive the chip well, without becoming part of the
promise. Hints sit **outside** the compatibility contract, exactly like internal
stages: they are the layer that rots as model generations advance, so every hint
entry MUST carry an `authoredAgainst` model-generation string, and hint entries
MAY be pruned without a version bump. A host MUST NOT let a hint change the
observable promise, ports, state, effects, or authority; a hint that would is a
contract term wearing the wrong label.

Package identity MUST derive from an immutable source-repository coordinate and
package path. A friendly alias is not a globally authoritative id. Any package
crossing an organization boundary MUST carry a verifiable signature over its
artifact digest in addition to build provenance.

### 7.1 Candidate manifest

The canonical manifest format for v1 is a `chip.json` file. (YAML or other
tooling may layer on later; it is not required by this specification.)

```json
{
  "apiVersion": "chip.spec/v0alpha1",
  "kind": "Chip",

  "metadata": {
    "id": "https://example.invalid/chips/journalism#new-report-triage",
    "alias": "journalism.new-report-triage",
    "version": "0.1.0",
    "title": "New report triage",
    "description": "Assess newly published reports for a declared beat and emit an evidence-linked finding or a quiet receipt.",
    "license": "Apache-2.0",
    "source": {
      "repository": "https://example.invalid/chips/journalism",
      "revision": "4f3c2a1",
      "path": "chips/new-report-triage"
    },
    "artifact": {
      "digest": "sha256:...",
      "signature": "sigstore:...",
      "provenance": "provenance.json",
      "sbom": "sbom.spdx.json"
    }
  },

  "contract": {
    "promise": "For every new in-scope report, produce one materiality assessment with evidence and no direct commission or publication effect.",
    "inputs": [
      { "name": "publication", "schema": "schemas/publication-signal.json", "delivery": "at-least-once" }
    ],
    "outputs": [
      { "name": "finding", "schema": "schemas/materiality-finding.json" },
      { "name": "quiet", "schema": "schemas/quiet-run.json" }
    ],
    "effects": [
      {
        "name": "recommend-research",
        "schema": "schemas/research-recommendation.json",
        "class": "recommend",
        "defaultApproval": "human"
      }
    ]
  },

  "state": {
    "schema": "schemas/state.json",
    "scope": "installation",
    "retention": "P365D",
    "migration": "migrations/state-v1.json",
    "cursor": "required",
    "concurrency": "single-flight"
  },

  "implementation": {
    "runtime": "python",
    "entrypoint": "impl.chip_impl:run",
    "stagesAreContractual": false,
    "authoredAgainst": "provider/model-2026-05",
    "stages": [
      { "id": "normalize", "kind": "code", "determinism": "deterministic" },
      {
        "id": "assess",
        "kind": "somm",
        "determinism": "probabilistic",
        "requestSchema": "schemas/assessment-request.json",
        "resultSchema": "schemas/assessment-result.json",
        "profile": "materiality-mid"
      },
      { "id": "validate", "kind": "policy", "determinism": "deterministic" }
    ]
  },

  "dependencies": {
    "capabilities": ["http.fetch", "state.single-flight.v1", "somm-attempt.v1"],
    "adapters": ["publication.fetch", "recommendation.emit"],
    "secrets": []
  },

  "authority": {
    "maximumEffectClass": "recommend",
    "prohibited": ["commission", "publish", "merge"],
    "approval": { "mode": "most-restrictive-wins" }
  },

  "limits": {
    "timeout": "PT5M",
    "maxActivationsPerHour": 4,
    "maxEffectsPerDay": 2,
    "cooldown": "PT6H",
    "modelBudgetUsd": 0.50,
    "retry": { "scope": "pre-effect-stage", "attempts": 2, "backoff": "exponential" }
  },

  "security": {
    "inputTrust": "hostile",
    "networkAllowlist": ["example.gov"],
    "filesystem": "none",
    "promptInjectionPolicy": "evidence-only"
  },

  "evaluation": {
    "fixtures": "fixtures/",
    "heldoutSuite": "evals/new-report-heldout-v1.json",
    "results": [
      {
        "tuple": {
          "implementation": "sha256:...",
          "sommProfile": "materiality-mid@1",
          "servedModel": "provider/model-version",
          "harness": "somm/structured-attempt-v1"
        },
        "receipt": "evals/receipts/materiality-mid-v1.json",
        "metrics": {
          "material-finding-precision": 0.80,
          "missed-material-signal-rate": 0.10,
          "duplicate-effect-rate": 0.00,
          "human-review-minutes": 12
        },
        "minimumsMet": true
      }
    ]
  },

  "compatibility": {
    "chipSpec": ">=0.1.0 <0.2.0",
    "requiredHostCapabilities": [
      "receipts.v1",
      "policy-effects.v1",
      "state.single-flight.v1",
      "somm-attempt.v1"
    ]
  },

  "hints": {
    "harnesses": {
      "somm/structured-attempt-v1": {
        "phrasing": "Ask for a terse rubric verdict; do not restate the evidence.",
        "authoredAgainst": "provider/model-2026-05"
      }
    },
    "models": {
      "provider/model-2026-02": {
        "notes": "This generation under-abstains; keep the explicit insufficient-evidence nudge.",
        "authoredAgainst": "provider/model-2026-02"
      }
    }
  }
}
```

The syntax is illustrative. The semantics and conformance tests matter more
than field names at this stage. `implementation.authoredAgainst` names the model
generation the judgment-stage artifacts were tuned for; the `hints` block is
non-contractual and generation-tagged (§7). Both are build metadata, not part of
the compatibility contract.

## 8. Signal, response, and effect envelopes

### 8.1 Signal envelope

Every input MUST carry or resolve to:

- stable signal id;
- type and schema version;
- observed and received timestamps;
- source coordinate and authority context;
- content or evidence digest;
- lineage and deduplication key;
- trust classification;
- content or custody reference: the payload under assessment, carrying its trust
  classification as field-level taint (inline for small payloads, a custody
  reference when the raw content lives elsewhere);
- optional prior-signal relationship; and
- custody reference when raw content lives elsewhere.

Retrieved content is hostile data. It MUST NOT be interpreted as chip, circuit,
host, or model instructions.

Under the delegation profile (§3.1), a signal produced by an agent-invoked
activation carries the invoking agent's identity in its authority context, so
receipts attribute the delegated run to the agent that requested it. The
invoking identity is context for attribution and policy, not a grant: it never
raises the effective authority ceiling (§14) and the payload remains hostile.

### 8.2 Response envelope

Every output MUST distinguish:

- observation or normalized signal;
- claim or assessment;
- cited evidence;
- recommendation or proposed response;
- uncertainty and counterevidence;
- abstention, quiet result, or needs-input state;
- expiry/freshness; and
- the chip/circuit/run coordinates that produced it.

These distinctions are envelope **fields**. The response's terminal *kind* — how
the run ended — is exactly one of four: `finding`, `quiet`, `abstain`, or
`needs_input`; observation, claim, evidence, recommendation, uncertainty, and
expiry ride as fields on a `finding`, not as separate kinds.

A mention MUST NOT be promoted to evidence merely because a chip observed it.
Source authority remains claim-specific.

Trust classification is transitive. Every response field derived from hostile
input MUST retain a taint and provenance marker. Quoted source spans MUST be
structurally separate from chip-authored assessment rather than interpolated
into instruction-position prose. Instruction-position enforcement covers a
spec-defined default key set (`instruction`, `instructions`, `directive`,
`command`, `system`, `system_prompt`, `systemPrompt`, `prompt`) plus any
field names a chip declares in its manifest's `contract.instructionFields`;
hosts enforce the union. A downstream adapter or UI consuming the
response MUST preserve that distinction. Removing taint is a policy decision
with its own evidence and receipt, not a formatting operation.

`needs_input` is not a terminal prose message. It creates a typed pending
decision with run correlation, allowed response schema, decision owner, expiry,
and lapse outcome. A human answer returns as a `decision` signal from the owning
system's guarded action contract, including actor, authority, reason, expected
prior state, and idempotency key. An expired question becomes a declared quiet
or failed outcome; it does not wait indefinitely.

### 8.3 Effect request

Chips MUST request effects through a typed host policy boundary. Model text MUST
NOT directly execute an effect.

An effect request includes:

- effect type and class;
- target owning system;
- exact payload schema;
- idempotency key and canonical derivation version;
- preconditions and freshness deadline;
- required approval and current approval receipt;
- expected result schema;
- rollback or compensation expectation;
- rate and budget accounting; and
- originating evidence and judgment receipt.

The host decides whether the effect is authorized, dispatches it through an
adapter, and records the result. An authorized deterministic chip can therefore
take action, but authority is never inferred from the chip's prose.

The idempotency key MUST be derived from stable source lineage, effect type,
target owner, and operational-promise identity. It MUST NOT include a run id or
mutable state representation and MUST survive state migration. Host-side
deduplication is necessary but insufficient: the target owning system is the
final deduplication authority because retries, migrations, or a future host
change can bypass one host's local state.

The four key inputs come from canonical, host-resolved sources so that the host
and the implementation compute the *same* key: source lineage comes from the
signal's lineage key; effect type from the effect declaration; and the remaining
two — target owner and operational-promise identity — are binding/manifest
resolved and injected by the host into the activation config as `effect_target`
and `promise_id`. An implementation MUST read them from there rather than
inventing its own, and the host recomputes and verifies the key it receives.

A recommendation entering an agent-consumed surface may be dispatched
automatically only when the adapter and consumer have a tested taint-aware
rendering contract. Otherwise it requires the same human gate as an experiment.

## 9. State and delivery semantics

State is part of the public contract, not an implementation accident.

A chip with state MUST declare:

- state schema and version;
- scope: run, binding, project, or explicitly shared;
- cursor and baseline semantics;
- retention and deletion policy;
- concurrency strategy;
- migration path;
- reset behavior;
- what is safe to reconstruct; and
- whether state may contain sensitive data.

State is keyed by globally unique installation id, never merely by chip id,
circuit id, or reusable binding template. The owning system mints the
installation id; Fab mints an experimental id for the v1 sandbox. One
installation may have at most one live host lease. Moving it requires an
explicit revoke/transfer receipt before a second host may acquire the lease.

The concurrency vocabulary is:

- `single-flight`: overlapping activations for one installation coalesce or
  queue behind one live lease;
- `cas`: overlapping runs may proceed only through declared compare-and-swap
  state transitions; and
- `partitioned(<keyField>)`: runs may overlap across distinct partition keys,
  with single-flight *per key* — one live lease per partition.

The admitted strategies are `single-flight` and, as of v0.5,
`partitioned(<keyField>)`; `cas` remains a deferred hypothesis. Cursor-bearing
**attention** chips MUST use `single-flight` — a cursor is a single monotonic
attention position and cannot be split across partitions. `partitioned` is for
**delegation-profile** map/cache-class chips keyed by a stable resource (for
example, one repository per partition): concurrent delegated invocations against
distinct keys proceed in parallel while same-key runs still single-flight. The
`<keyField>` MUST name a declared signal envelope field (§8.1) so the host can
compute the partition from the activation signal alone. Retry scope is declared
per stage; an effect is never retried without rechecking its stable idempotency
key at the target.

Inputs SHOULD be assumed at-least-once unless a host proves stronger delivery.
Effects MUST therefore be idempotent or carry an explicit compensation policy.

A quiet run is a first-class successful result. It MUST update only the state
necessary to preserve attention semantics and MUST produce a compact receipt.
No finding, no action, and abstention are distinct outcomes.

## 10. Deterministic and probabilistic stages

### 10.1 Deterministic responsibility

Deterministic code or host policy SHOULD own:

- fetching coordinates and content digests;
- schema validation and normalization;
- cursor advancement and compare-and-swap;
- canonicalization and obvious deduplication;
- budgets, rate limits, cooldowns, and timeouts;
- idempotency and retry accounting;
- authority checks and approvals;
- effect dispatch;
- receipt construction; and
- state migration.

### 10.2 Somm responsibility

Somm-backed stages MAY own judgments where fixed rules are insufficient:

- materiality and relevance;
- semantic clustering or duplicate candidacy;
- claim extraction and contradiction candidacy;
- hypothesis generation;
- bounded synthesis;
- rubric-bound review; and
- deciding that the evidence is insufficient and abstaining.

Every Somm stage MUST declare:

- request and result schema;
- task role and model profile rather than an unexamined model name;
- allowed context and tools;
- requested and served model/harness;
- prompt or policy digest;
- token, cost, latency, and cache receipts;
- confidence/uncertainty fields appropriate to the task;
- failure and abstention behavior; and
- evaluation suite and expiry.

Evaluation evidence is valid only for the tuple:

```text
(implementation digest, Somm profile (gateway model profile), served model, harness)
```

Changing any member creates an unevaluated tuple. An unevaluated binding is
capped at `observe` until the relevant held-out suite passes; a profile alias
MUST NOT silently inherit a result from the model it previously resolved to. The
observe cap is binding-level, not per-run: a gateway-bearing binding whose tuple
is unevaluated is capped at `observe` for every run, including runs where the
implementation happens not to invoke the gateway.

The judgment-stage artifacts (prompts, scaffold, few-shot material) carry the
model generation they were tuned for in `implementation.authoredAgainst` (§7.1).
They are a perishable *build output*, not a contract term: the held-out suite
defines the promise, the internals are what a build produced to satisfy it. On a
model-generation change the judgment stage SHOULD therefore be **re-derived from
the fixtures** rather than hand-patched — the same fixtures and held-out suite
that gate a tuple are sufficient to rebuild the stage against the new generation.
A prompt tuned for an older generation may actively hurt a newer one, so
carrying `authoredAgainst` forward unexamined is a defect, not a courtesy. When
the raw model has caught up to the chip on its held-out suite, retirement (§13.1)
is the correct outcome, not another hand-patch.

The host MUST validate the structured result before it can influence state or
effects. When the request carried tainted content, the host MUST apply taint
markers to the result's fields before returning it to the implementation, with
trust inherited from the request's most-hostile input; model output derived from
hostile input is hostile-derived (§8.2 transitivity). Re-running a Somm stage MAY
produce a different judgment. A receipt must preserve the actual result used
rather than claiming deterministic replay.

### 10.3 Implementation classes

A version 1 chip is one of:

- `deterministic`: all judgments are rule/code based;
- `hybrid`: deterministic envelope with at most one Somm stage.

Even a model-heavy chip is `hybrid`: state, validation, policy, and effects
remain deterministic.

`external` and portable `declarative` implementations are later design
candidates, not version 1 compatibility classes. Delegating to an unpinned
service would defeat implementation identity; claiming declarative portability
before two hosts exist would encode Fab's private language as a public standard.

## 11. Circuits

A circuit is a versioned composition document, not a copy of chip
implementations.

A circuit MUST declare:

- id and version;
- exact chip contract and implementation coordinates;
- typed port connections;
- accepted activation signal type;
- shared budgets and authority ceiling;
- error, timeout, and backpressure policy;
- human decision points;
- state ownership and data-flow boundaries;
- terminal and quiet outcomes; and
- compatibility and migration behavior.

Chip outputs may connect only to the same named, versioned semantic schema or to
an explicitly compatible successor. Sharing a structural shape is not enough.
Transformations SHOULD be explicit deterministic adapter chips, not inline
expressions scattered through bindings.

A version 1 circuit is linear, contains at most three chips, and has no nesting,
feedback edge, fork, join, push source, internal schedule, or cross-circuit
routing. Activation is a signal delivered by the owning system. The circuit as
a whole MUST pass held-out, quiet, failure, and authority evaluation; composing
individually evaluated chips does not imply an evaluated circuit.

Branching, nesting, feedback, and long-lived signal delivery are deferred. If
they become necessary, the design MUST first explain why the behavior should
not live in an existing workflow/runtime system.

## 12. Bindings and installations

Portable artifacts MUST NOT contain environment credentials or assume local
authority.

A binding resolves:

- an optional host-owned environment profile reference (`environment`, §12.1),
  supplying defaults the binding need not restate;
- chip implementations and host adapters;
- source endpoints and custody references;
- per-chip configuration parameters (`chipParameters`, keyed by chip alias),
  merged into the activation `config` beneath host-injected keys and never
  carrying secret literals;
- secret **references**, never secret values;
- model profiles through Somm;
- project/owner identity through the owning system;
- budgets, cadence, and policy overlays;
- authority ceiling and approval routes;
- state namespace; and
- response/effect destinations.

For version 1, every binding resolves to Fab and one immutable evaluated
implementation tuple. Cadence is descriptive metadata only: an owner-side
scheduler or manual guarded action emits the activation signal. The circuit
does not register timers, webhooks, event subscriptions, or background workers.

The effective authority is the intersection of:

```text
chip maximum
  ∩ circuit maximum
  ∩ binding policy
  ∩ host policy
  ∩ current human approval
```

The chip maximum in the intersection is the maximum of the chip requesting the
effect; a sibling chip's ceiling does not constrain it. A circuit ceiling is a
cap applied per requesting chip, not a floor min-ed over all members — an
observe-only sensing chip therefore never lowers a downstream chip's effective
authority.

Any missing authority fails closed.

An installation is the enabled binding and owns the globally unique installation
id described in section 9. Enabling, disabling, upgrading, transferring, or
revoking one is a consequential operation and MUST produce a human-linked
receipt in the owning system. Approval policies compose by choosing the most
restrictive applicable gate; a permissive overlay can never weaken a chip,
circuit, host, or owner requirement. Every effect adapter MUST submit the stable
effect key to the target owner's deduplication boundary.

### 12.1 Environment profiles (the third resolution layer)

Installation-specific facts split into **three** layers, not two:

1. the **portable manifest** — the chip contract plus its non-contractual,
   generation-tagged `hints` (§7). Portable; carries no environment facts.
2. the **binding** — installation-specific resolution: which adapters, source
   endpoints, secret references, model profiles, owners, budgets, and authority
   ceiling apply to *this* installation (above).
3. the **environment profile** — a *host-owned* document describing what exists
   in one environment: the capabilities it offers, the adapters available, the
   gateway profiles, the state roots, the local policy overlays, and local
   conventions. It has its own schema identifier, `environment.spec/v0alpha1`,
   and its own id and version.

The environment profile owns the system's *shape* so bindings do not each
restate it. A binding MAY reference a profile by id (`binding.environment:
<profile-id>`) instead of repeating host facts. A host resolves the effective
binding by folding the profile in as defaults and letting **binding-local values
override profile values** — the profile is the default for the environment's
shape, the binding keeps the last word. This is the "many moving parts, not all
under the chip" separation: the chip stays portable, the binding stays
per-installation, and the environment profile owns what is true of the host. A
profile is host-owned and MUST NOT carry secret values (only references), exactly
as a binding must not (above).

## 13. Runs and receipts

Every accepted activation produces a run. A rejected activation produces a
compact attempt receipt without allocating mutable chip state.

There is **one receipt shape**. Every run emits it. A required core is always
present; the remaining blocks appear only when the run reached the stage that
produces them. Spec 0.5 defined two tiers (`#attention` and `#judgment`); the
distinction described *how much of the run happened*, which the blocks already
say, so it is removed.

The required core, present on every receipt:

- run, installation, circuit, chip, and binding identifiers;
- the contract and implementation digests actually used;
- run status, semantic outcome, and terminal reason (§13.2);
- the effective authority decision (§14); and
- timing.

Optional blocks, each present only if the run reached it:

| Block | Present when |
|---|---|
| `inputs` | ids and evidence/custody references were resolved |
| `state` | mutable state was allocated — version before and after |
| `stages` | ordered stage events and durations |
| `gateway` | a gateway was invoked — request/result coordinates, usage, cost |
| `decisions` | validation, dedupe, and budget were evaluated |
| `effects` | effects were proposed, approved, rejected, or executed |

Receipts MUST separate run status from semantic outcome. "Process exited" is not
"promise satisfied"; "model answered" is not "finding valid"; "PR opened" is not
"change correct."

A receipt MUST NOT embed a harness's raw error text. A failure records a typed
reason from §13.2 plus a digest or reference to the detail in its owning system.

> Evidence: across 91 production judgment receipts, `outcomeLinks` and
> `artifacts` were empty on every single one, and `verifierResults` carried the
> same constant environment attestation every time — so all three are removed
> from the run receipt. Twelve receipts carried no `timing` and fourteen no
> `id`, meaning the "MUST include" list did not describe what hosts emit. One
> failure embedded several kilobytes of raw model output and schema-validation
> text in a decision field.

Receipts are append-only while retained. Corrections supersede rather than erase
prior records. Large evidence remains in its owning custody system and is linked
by stable id and digest. A binding MUST declare retention. A host MAY compact
expired receipts that carry no `effects` block into signed aggregate counts plus
a digest chain; a receipt cannot be compacted while an effect, decision,
evaluation, incident, or outcome reference remains live.

### 13.1 Lifecycle telemetry

Runs record what a chip *did*; lifecycle telemetry records what happened to the
chip *itself* as it was banked and evolved. A host SHOULD maintain an
append-only lifecycle record whose entries are exactly one of six events:

| Event | Meaning |
|---|---|
| `mint` | A candidate crystallized into an installed chip |
| `transfer` | An installation moved to another owner/host (with a revoke/transfer receipt, §9) |
| `split` | One chip divided into more specific chips on evidence |
| `merge` | Several chips consolidated into one |
| `optimize` | The judgment stage was re-derived/tuned, promise held |
| `retire` | The chip was withdrawn (model outgrew it, superseded, or obsolete) |

Each event is a fixed-shape record: the event name, an ISO-8601 `at` timestamp,
the acting `operator`, the `chipAlias` and `chipVersion`, the
`implementationDigest`, an optional `tupleKey` and `receiptRef`, and a free-form
`details` object. Three rules govern them:

- **Minting SHOULD be gated on observed call frequency.** A chip is minted when a
  path has proven routine (the candidate ledger, §21-adjacent conventions, is the
  evidence), not eagerly — eager minting never amortizes its authoring and
  evaluation upkeep.
- **`split`, `merge`, and `optimize` MUST carry the held-out `tupleKey` that
  gated them.** These are evidence-bearing transitions; the evaluated tuple
  (§10.2) that justified the change is part of the record, not a footnote.
  `retire` MAY be ungated — the asymmetry is deliberate: mutations that add or
  reshape authority are hard, removal is easy. An owning system may retire a
  chip on judgment alone (superseded, low-value), receipted but unproven.
- **A `retire` whose reason is `model-generation` MUST reference a raw-model
  baseline comparison** (in `details`): the evidence that the raw model now
  matches or beats the chip on its held-out suite. Retiring banked judgment
  against anything less turns banked knowledge into a silent regression.

Lifecycle records are append-only and correction-by-supersession like receipts.
They are host telemetry, not part of a chip's portable contract.

### 13.2 Terminal reasons

`terminalReason` is a closed vocabulary. A host MUST use one of these values and
MUST NOT invent others; a reason that does not fit is a signal that the spec is
missing a case, not license to write prose into the field.

| Reason | Run status | Meaning |
|---|---|---|
| `no-actionable-finding` | completed | The chip paid attention and had nothing to say |
| `finding-no-effect` | completed | A valid finding that proposes no effect |
| `finding-effect-proposed` | completed | A finding proposing at least one effect |
| `duplicate-signal` | completed | Suppressed by dedupe or lineage |
| `activation-rejected` | rejected | Single-flight lease held by a live activation |
| `installation-not-enabled` | rejected | The installation is paused, revoked, or never enabled |
| `signal-invalid` | failed | The activation signal failed envelope validation |
| `implementation-digest-mismatch` | failed | Unexplained content change against the pin (§16.3) |
| `gateway-unavailable` | failed | The gateway could not be reached or was exhausted |
| `gateway-result-invalid` | failed | The gateway answered, and the answer failed validation |
| `host-runtime-error` | failed | The host failed before the chip reached a verdict |
| `authority-denied` | failed | Policy refused the run or its effects |
| `effect-dispatch-failed` | failed | An approved effect could not be handed to its sink |

Lifecycle and evaluation records use their own reasons (`operator-install`,
`operator-revoke`, `evaluation-recorded`, `succession-recorded`) and are not run
receipts.

> Evidence: eight distinct terminal reasons appeared across 148 production
> receipts. Two failure modes that occurred repeatedly — an exhausted gateway
> and a gateway answer that failed schema validation — had no reason of their
> own and were both recorded as generic host failures.

### 13.3 Outcome receipts

A run receipt records what a chip decided. It cannot record whether the chip was
right, because that is not known yet. An **outcome receipt** closes that loop: it
is a separate, later record that references a run receipt and states what
happened downstream.

A host that consumes a chip's judgment to make a decision MUST emit an outcome
receipt when the downstream result becomes known. It carries:

- the run receipt reference and the chip's own verdict;
- the **decision the host actually took**, and whether it followed the chip;
- the **independent floor**, if the host has one — the decision it would have
  taken without the chip;
- the **downstream verdict** once observed; and
- whether this run was **counterfactually audited** — the chip's advice was
  recorded but deliberately not followed, so its precision can be measured
  instead of inferred from silence.

Outcome receipts are what make a chip improvable. Without them, evaluation
(§21) can only measure a chip against fixtures it was authored alongside, and
`optimize` (§13.1) has no signal to optimize against. A chip whose host emits no
outcome receipts can be evaluated but not calibrated.

> Evidence: the reference host already maintained exactly this record — chip
> plan, independent label-ladder decision, verifier verdict, final job status,
> audit flag — in a host-private file, because the run receipt had nowhere to
> put it. Every run receipt's `outcomeLinks` field sat empty while the data
> existed a directory away. This section promotes that record into the contract
> and deletes the field that failed to hold it.

## 14. Authority, security, and supply chain

The default chip authority is `observe` or `recommend`, never production change.

Effect classes align with the local promotion ladder:

| Class | Example | Default gate |
|---|---|---|
| `observe` | Fetch, normalize, dedupe | Automatic on approved source/binding |
| `synthesize` | Finding, assessment, recommendation | Automatic with visible evidence grade |
| `experiment` | Credential-free disposable evaluation | Approved experiment specification |
| `draft` | Isolated branch or draft artifact | Owning-system policy plus successful experiment |
| `promote` | Merge, bind, publish, deploy, production mutation | Explicit human approval |

The host MUST enforce the class independently of the chip implementation.

In version 1, Fab is that enforcement boundary. Conformance tests MUST prove
that a package declaring no network, filesystem, process, or credential
capability cannot obtain it, including through a Somm attempt or adapter. A
manifest declaration without a sandbox denial test is not evidence of
confinement.

Before installation, a package MUST be pinned and inspected for:

- source provenance, license, maintainer, and revision;
- build provenance and artifact digest;
- install/build scripts and binary content;
- dependency graph and known vulnerabilities;
- network, filesystem, process, and credential access;
- prompt-injection exposure and untrusted-content handling;
- secret declarations;
- effect types and maximum authority;
- state retention and migration; and
- test/evaluation evidence.

Self-contained bundling does not remove supply-chain risk. A bundle SHOULD ship
an SBOM and reproducible or independently verifiable build evidence so inlined
dependencies remain visible.

Packages MUST be signed to a source coordinate and immutable artifact digest.
Revocation is an owning-system installation event, not a registry hint. State
migration is an `experiment`-class operation: it requires a pinned migrator,
pre/post invariants, rollback or quarantine behavior, and explicit human
approval. A migration MUST preserve installation identity, cursor lineage, and
stable effect keys.

## 15. Versioning and compatibility

Chips use semantic versions for their public contract:

- `MAJOR`: removes or reinterprets an input/output/effect, adds required input,
  changes state incompatibly, broadens effects, or changes the operational
  promise;
- `MINOR`: adds optional input/output, compatible capability, fixture, or
  implementation option; and
- `PATCH`: corrects an implementation without changing declared behavior.

Stage boundaries are not part of the public contract unless a package opts into
that restriction. Collapsing two internal stages or replacing a prompt with code
is therefore a `PATCH` only when the operational promise, ports, state, effects,
authority, and evaluated tuple remain compatible and held-out performance is
non-inferior.

Implementation artifacts also carry immutable build digests. A circuit pins
both the chip contract version and accepted implementation coordinate.

Publishing a newer version MUST NOT silently alter an active circuit. Upgrade
requires compatibility evaluation for the exact implementation/Somm/model/
harness tuple, state migration planning, and an owning-system decision receipt.
There is no automatic patch adoption in version 1.

Hosts MUST advertise supported spec versions and capabilities. Missing required
capability fails binding before execution. Optional capability degradation MUST
be declared and evaluated; a host may not silently replace one effect or model
stage with another.

## 16. Packaging, distribution, and resolution

A chip that a host cannot resolve is not portable, and a chip that resolves
differently in two environments is not the same chip. This section is normative.
It was a later hypothesis through spec 0.5; operating evidence promoted it.

### 16.1 Package identity is a digest, not a path

A package's identity is the digest of its content. A host MUST resolve an
installed chip from a content-addressed store the host owns, and MUST NOT
resolve it through a path into the authoring workspace. An installation records
the digest it is pinned to; the store, not the filesystem layout of whoever
authored the chip, is what the host reads at activation.

> Evidence: 74 consecutive production activations failed with `chip package
> directory ... not found` after the host was installed as a service. The
> package existed, the pin was valid, and the path was meaningless in the
> environment where activations actually ran.

### 16.2 The entry point is declared, not discovered

The manifest MUST declare the package's executable entry point. A host MUST NOT
depend on the package's internal module layout, file names, or import graph to
locate the implementation, and MUST NOT require the package to import any
non-public symbol of the contract library.

A package MUST declare the contract library major version it was built against.
The library's internal module paths are not API: renaming, splitting, or merging
them is not a breaking change to this specification, and a package that depends
on them is malformed.

> Evidence: renaming one internal library submodule silently disabled an
> installed chip for 26 activations. The chip's declared contract had not
> changed.

### 16.3 Revision succession

Replacing a chip's implementation is an **upgrade of an existing installation**,
not a new installation. A succession preserves installation identity, cursor
lineage, dedupe and lineage keys, per-day effect counters, and stable effect
keys; it re-pins the digest and records a succession receipt naming the prior
and successor digests.

A digest change that arrives through a declared succession MUST NOT be reported
as an integrity violation. Only an *unexplained* digest change — content that
no longer matches the pin, with no succession on record — is an integrity
violation, and it MUST still fail closed.

> Evidence: two chips produced 13 installs and 11 revokes in eight days, plus 13
> `implementation-digest-mismatch` failures against a single pin. Every ordinary
> edit to a chip's implementation presented as a supply-chain event.

### 16.4 Preflight and liveness

Before an installation is enabled, a host MUST verify that the package resolves
and its declared entry point loads **in the environment where activations will
run**. A preflight that passes in the authoring environment and is not repeated
in the execution environment does not satisfy this requirement.

A host MUST record every fail-soft fallback against the installation that caused
it, and MUST expose consecutive-fallback counts. An installation whose last
successful activation is older than its declared attention cadence is **dark**,
and a host MUST surface dark installations rather than reporting their silence
as quiet operation.

Fail-soft is required (§13) and is not in tension with this: a host degrades
without failing the owning system's work, *and* says so.

> Evidence: a chip fell back on 100 of 170 consecutive activations across two
> distinct root causes, over a span of eight days, without surfacing anywhere.
> Every one of those runs recorded a well-formed receipt.

### 16.5 Registry (later hypothesis)

A registry is useful only if it improves trustworthy reuse. It is not required,
and nothing above depends on one: a content-addressed store may be a directory.

A registry record SHOULD contain:

- immutable package coordinates and digests;
- contract and compatibility metadata;
- source, license, provenance, SBOM, and maintainer;
- declared capabilities, adapters, secrets, and effects;
- evaluation suites and results by host/model/context;
- known failures, revocations, and security advisories;
- usage and outcome evidence without leaking project data;
- replacement/supersession relationships; and
- last verified date.

Discovery popularity MUST NOT become a universal quality or authority score.
Evidence remains claim- and context-specific.

A future **chipset** MAY bundle chips, sample circuits, thin skill wrappers, adapters,
doctrine, and examples. The bundle manifest MUST keep these artifact types
distinct. Installing a chipset does not activate its circuits or grant effects.

The skill registry is the only acceptable future composition and binding
boundary if its charter is explicitly expanded from skills to operational
packages. That decision is not made by this specification, and version 1 does
not require a registry or chipset. The originating research service MUST NOT
become the registry or binding authority.

## 17. Board projection and steering — moved

*Non-normative. Moved to [docs/board-projection.md](../docs/board-projection.md) in spec 0.6.
The section number is retained so existing cross-references stay valid.*

## 18. Skills as wrappers over chips

Chips do not make skills obsolete. They change the useful resolution of what is
shared.

Skills remain appropriate for:

- recognizing when a capability is relevant;
- conducting ambiguous user dialogue;
- teaching domain methods and taste;
- selecting or configuring a circuit;
- interpreting receipts and explaining tradeoffs;
- mapping generic actions to a harness's tools; and
- filling temporary capability gaps in a model or host.

Operational behavior SHOULD move into chips when it has:

- stable inputs and outputs;
- repeatable state or effect semantics;
- deterministic validation or policy;
- independent tests and outcomes;
- reuse value outside the original prompt; and
- a safety boundary that should not depend on model compliance.

A **thin wrapper**:

- MAY contain invocation/routing guidance, user dialogue, and interpretation;
- MAY select among declared chips or circuits;
- MUST NOT own cursors, retry loops, hidden shell pipelines, credentials,
  effect dispatch, or canonical receipts;
- MUST NOT duplicate a chip's contract in long prose; and
- SHOULD be replaceable for a new model/harness without changing the circuit.

Those prohibitions MUST be checked by a package audit, not trusted as model
instructions. At runtime Fab denies undeclared credentials and effects; wrapper
calls can only select a pinned binding or submit a typed decision. If a wrapper
requires hidden shell state or broader authority to work, the decomposition has
failed.

Doctrine is separate from both. Principles such as “evidence before claims” or
“write the failing test first” may inform wrappers, policies, graders, or chip
fixtures. They are not automatically chips.

## 19. The skill-package decomposition challenge — moved

*Non-normative. Moved to [docs/skill-decomposition.md](../docs/skill-decomposition.md) in spec 0.6.
The section number is retained so existing cross-references stay valid.*

## 20. Reference circuits — moved

*Non-normative. Moved to [docs/reference-circuits.md](../docs/reference-circuits.md) in spec 0.6.
The section number is retained so existing cross-references stay valid.*

## 21. Evaluation

Every chip evaluation SHOULD include:

- positive cases;
- quiet/no-change cases;
- duplicates and stale inputs;
- malformed and adversarial inputs;
- prompt-injection attempts when content reaches a model;
- model failure, timeout, and invalid structured output;
- retry and idempotency cases;
- budget and rate-limit exhaustion;
- unavailable adapter or degraded host capability;
- authority denial and missing approval;
- state migration and concurrent activation; and
- outcome follow-up where the effect was promoted.

Security and durability suites MUST include:

- hostile source text that attempts to become chip, host, model, board, or agent
  instructions, with field-level taint asserted through the final adapter;
- migration/retry cases that try to reset a cursor and emit an old effect again;
- denied network, filesystem, process, and credential access in Fab;
- profile alias drift and a model swap without a matching evaluated tuple;
- expired and conflicting human decisions; and
- dialogic exception cases for any behavior decomposed from a skill.

Model-backed chips require the same-task baseline and variant with fixed input
snapshots. Results are recorded only for the exact implementation digest, Somm
profile, served model, and harness tuple. A fixture-canned evaluation validates
the deterministic envelope and records a tuple whose served model is the canned
marker; it does not evaluate a live model tuple. Lifting a live binding above
`observe` therefore requires the held-out suite to run against the live gateway,
so the recorded tuple matches what activation will compute. A circuit also
requires an end-to-end suite; constituent chip results do not compose
automatically. Held-out behavioral improvement, not instruction compliance or
artifact completeness, governs promotion.

Registry and board metrics SHOULD include:

- useful finding precision and missed-signal rate;
- quiet-run rate and cost;
- duplicate response/effect rate;
- abstention appropriateness;
- human review and diagnosis time;
- recommendation-to-outcome conversion;
- stale or revoked installation count;
- model/harness conditioned performance; and
- whether the chip still adds value as models improve.

## 22. Pilots and graduation — moved

*Non-normative. Moved to [docs/pilots.md](../docs/pilots.md) in spec 0.6.
The section number is retained so existing cross-references stay valid.*

## 23. Open questions — moved

*Non-normative. Moved to [docs/open-questions.md](../docs/open-questions.md) in spec 0.6.
The section number is retained so existing cross-references stay valid.*

## 24. Falsification and kill criteria — moved

*Non-normative. Moved to [docs/falsification.md](../docs/falsification.md) in spec 0.6.
The section number is retained so existing cross-references stay valid.*

## 25. Status and scope of this document

This document defines a candidate vocabulary and contract that is under active
experiment. It is a specification, not an authorization.

Nothing in this document authorizes any installation to act. Operational
authority comes only from an owning system's explicit binding and its approval
receipts, resolved through the intersection of authority described in section 12
and enforced by the host. A chip, circuit, or wrapper carries no standing
permission of its own; absent an owning system's binding and current approval,
every effect fails closed.

The version 1 experiment lives in the Fab host and is limited to the two pilots
of section 22 (publication triage and PR sign-off), operating in a disposable,
credential-free sandbox. Registry, multi-host distribution, live project
installation, and whole-suite skill decomposition remain later hypotheses with
their own kill criteria.

The evidence-and-transfer analysis and the independent adversarial model review
that shaped v0.2.0 are internal documents; their substantive conclusions are
summarized in the changelog for this repository and in the falsification and
kill criteria of section 24.
