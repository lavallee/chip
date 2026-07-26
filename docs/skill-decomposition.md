<!-- Moved out of spec/chip-spec.md in spec 0.6. The specification is normative
     material only: what a host must implement to interoperate. -->

# The skill-package decomposition challenge

A research program for testing portability against two mature skill suites. Hypotheses and graduation criteria, not a contract a host implements.

The first serious portability test SHOULD decompose representative slices of two
representative mature skill suites: a browser-operations suite and an
engineering-workflow suite.

### 19.1 Required inventory

For every behavior in the selected slice, classify it as:

- chip;
- circuit;
- thin wrapper;
- tool;
- dialogic skill;
- doctrine/rubric;
- host adapter;
- test/evaluation fixture; or
- obsolete model-generation scaffolding.

No behavior may disappear silently. Safety and approval behavior receives an
explicit classification and equivalence test.

The admission rule still applies: an installation must declare an ongoing
observation relationship to a signal class or the package must own durable
cross-run state, and it must produce a bounded response under an authority
contract. A callable operation with neither is a tool, even if a skill currently
wraps it. A capability whose value lies in open-ended conversation and situated
judgment remains a dialogic skill.

### 19.2 Candidate decomposition: browser-operations suite

Potential tools or host capabilities:

- browser snapshot/evidence capture;
- browser security and hostile-content scan;
- PR/diff/test evidence collection;
- normalized review-finding construction; and
- release evidence verification.

Potential chips:

- WIP/PR attention state and context checkpointing;
- stale-signoff invalidation after head or evidence change; and
- post-run outcome/learning candidate attention.

Potential circuits:

- review -> classify findings -> repair proposal -> independent reverify;
- QA -> evidence capture -> finding triage -> bounded retest; and
- ship-readiness -> checks -> proof packet -> human release decision.

These are decomposition hypotheses, not valid version 1 circuit shapes. Each
must first be reduced to a linear composition of no more than three admitted
chips, with ordinary evidence operations remaining tools inside a chip's Fab
attempt.

Potential wrappers or dialogic skills:

- CEO, engineering, design, and developer-experience review dialogues;
- QA, review, and ship command invocation and interpretation; and
- host-specific command discovery.

### 19.3 Candidate decomposition: engineering-workflow suite

Potential tools or Fab capabilities:

- isolated worktree and baseline receipt;
- failing-test proof;
- test-result and verification receipt;
- plan/spec compliance review packet;
- code-quality review packet; and
- branch completion-state inspection.

Potential chips:

- plan/WIP state attention and stalled-decision detection;
- verification freshness invalidation; and
- unresolved-review attention with bounded sign-off response.

Potential circuits:

- approved plan -> isolated work -> red/green verification -> independent
  review -> handoff; and
- bug report -> root-cause evidence -> failing reproduction -> repair ->
  regression proof.

These too are later workflow hypotheses, not version 1 circuit definitions.
Their dialogic and tool portions must not be forced into chips merely to fit the
vocabulary.

Potential wrappers, dialogic skills, or doctrine:

- brainstorming and requirements dialogue;
- systematic debugging heuristics;
- TDD teaching and exception negotiation;
- harness bootstrap and tool mapping; and
- reminders to invoke the correct circuit.

### 19.4 Graduation criteria

The decomposition succeeds only when:

1. all original safety and approval gates are mapped and preserved;
2. wrappers contain no hidden operational state/effect machinery;
3. the same chip artifacts run through at least two host adapters and two Somm
   model/harness profiles;
4. at least one circuit is used in a context not anticipated by the originating
   skill package;
5. original and decomposed variants are compared on the same development and
   held-out tasks;
6. the decomposed form is non-inferior on task outcome and improves at least one
   of portability, diagnosis time, duplicate logic, prompt burden, or upgrade
   effort;
7. changing the model/harness requires changing only a binding, adapter, or thin
   wrapper unless a held-out result proves the chip itself must change;
8. receipts explain every action, abstention, and failure without reading the
   original skill prompt; and
9. an independent reviewer can reconstruct the composition and authority from
   package artifacts alone.

These are later thesis criteria, not gates for the Fab-only prototype. The
whole-suite exercise begins only after the two narrow pilots have operated for
90 days with comparable skill-only baselines. It MUST include adverse judgment
fixtures where strict process is wrong—for example, a justified TDD exception—
so decomposition does not amputate negotiation, taste, or context.

The experiment fails if it merely renames skill steps, moves prompts into a
manifest, reclassifies every useful tool as a chip, or produces a private
runtime coupled to one suite.
