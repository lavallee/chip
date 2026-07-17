# Changelog

All notable changes to the chip/circuit specification are recorded here. The
specification uses semantic versions for its own contract, independent of any
implementation.

Schema identifier: `chip.spec/v0alpha1`.

## 0.4.0 — 2026-07-16

Implementation-informed clarifications from the first host (Fab) and the first
pilot (publication triage). Two independent implementations hit the same seams;
these edits sharpen the contract without changing the schema identifier (still
`chip.spec/v0alpha1`).

Clarified:

- **Schema references name a file *and* a version (§7, §11).** A schema reference
  has the form `path/name.json@N`: the on-disk artifact is the versionless file
  `path/name.json`, and the `@N` suffix pins the schema version that circuit port
  compatibility matches on. A host resolves the file half but keeps the whole ref
  (file **and** version) for exact-string port-compatibility matching.
- **Effective authority is intersected per requesting chip (§12).** Added a
  sentence: the chip maximum in the chip ∩ circuit ∩ binding ∩ host ∩ approval
  intersection is the maximum of the chip *requesting* the effect; a sibling
  chip's ceiling does not constrain it. A circuit ceiling is a per-chip cap, not a
  floor min-ed over all members, so an observe-only sensing chip never lowers a
  downstream chip's effective authority.
- **Terminal response kinds named (§8.2).** The response envelope's `kind` is
  exactly one of four run outcomes — `finding`, `quiet`, `abstain`, `needs_input`.
  The observation/claim/evidence/recommendation/uncertainty/expiry distinctions
  are envelope **fields** on a `finding`, not separate kinds.
- **Signal content channel (§8.1).** Added a "content or custody reference"
  bullet: the payload under assessment, carrying its trust classification as
  field-level taint, distinct from the lineage/digest metadata; large payloads may
  use the custody-reference alternative.
- **Effect-key input sources (§8.3).** Documented the canonical sources of the
  four key inputs: source lineage from the signal, effect type from the effect
  declaration, and `target_owner`/`promise_id` binding/manifest-resolved and
  injected by the host into the activation config as `effect_target` and
  `promise_id`, so host and implementation derive identical keys.
- **Entrypoint example (§7.1).** The illustrative manifest entrypoint is now
  `chip_impl:run`, matching the host execution contract's `impl/chip_impl.py`
  convention.

## 0.3.0 — 2026-07-16

First published edition, relocated to this repository
(github.com/lavallee/chip). This is an editorial and status pass over the
narrowed v0.2.0 contract; every normative requirement, section structure,
table, diagram, effect-class ladder, evaluation-tuple rule, taint rule, kill
criterion, and open question is preserved. The schema identifier is unchanged.

Changed:

- **Status and implementation.** Version bumped to 0.3.0; status remains
  `candidate specification`. Implementation status is now
  `v1 experiment in progress (Fab host)`. Removed the pre-publication
  "Promotion status" line and the link to the internal red-team report; added a
  short History line noting that v0.2.0 followed an independent adversarial
  model review and that v0.3.0 is the first published edition.
- **Canonical home.** Added a pointer, immediately after the abstract, to
  github.com/lavallee/chip and to the reference contract library (`chipspec`
  on PyPI, import `chip`), which implements the manifest, envelope, authority,
  receipt, and conformance surfaces of the document.
- **Canonical manifest format (§7.1).** The example manifest is now expressed as
  JSON, and the canonical v1 manifest is a `chip.json` file. Fields and
  semantics are unchanged; a note records that YAML or other tooling may layer
  on later. The caveat that syntax is illustrative and that semantics and
  conformance tests matter more is retained.
- **Status and scope (§25).** Rewritten from a private-workspace decision-status
  list into a public "Status and scope of this document" section: the spec is a
  contract under experiment and does not itself authorize any installation to
  act; authority comes only from an owning system's explicit binding and
  approval receipts; the v1 experiment lives in the Fab host with the two pilots
  of §22; and the evidence/transfer analysis and adversarial review that shaped
  v0.2.0 are internal documents summarized here.
- **Vocabulary genericization.** Internal system names were replaced with their
  public roles so the document reads as one coherent public specification. The
  two public reference implementations, Fab (the v1 host) and Somm (the LLM
  gateway, github.com/lavallee/somm), are named directly; all other internal
  names now appear by role (for example, "the owning system", "the originating
  research service", "the skill registry", "agent surfaces"). The skill-suite
  decomposition challenge (§19) is framed around two representative mature skill
  suites — a browser-operations suite and an engineering-workflow suite — with
  the candidate tool/chip/circuit/wrapper inventories retained.
- **Terminology definitions.** On first use, "Somm stage" is defined as a
  judgment stage executed through an LLM gateway (reference: Somm), and the
  "Somm profile" member of the evaluation tuple is annotated as the gateway
  model profile.
- **Report links removed.** References to internal `../reports/...` files were
  removed; the substantive claims they carried are retained inline or folded
  into this changelog.

## 0.2.0 — pre-publication

Post-red-team narrowing. Following an independent adversarial model review, the
contract was tightened to an explicit experimental v1 core: a single host (Fab)
in a disposable credential-free sandbox, pull-only activation, hybrid
implementations with at most one Somm stage, installation-scoped single-flight
state, linear circuits of at most three chips, target-side effect
deduplication, two-tier receipts, and two pilots (publication triage and PR
sign-off). Registry, multi-host distribution, nested/cyclic circuits, live
installation, and whole-suite decomposition were relocated to explicitly
deferred hypotheses with kill criteria. Not published.

## 0.1.0 — pre-publication

Initial draft of the chip/circuit vocabulary and contract for internal
critique. Established the core primitives (chip, port, circuit, binding,
installation, run, receipt, chipset, wrapper, host, board), the
deterministic-envelope-around-probabilistic-judgment execution pattern, the
authority ladder, the signal/response/effect envelopes, and the evaluation and
receipt model. Not published.
