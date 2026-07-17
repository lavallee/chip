# Host execution contract (v1, python runtime)

Status: v1 convention for `implementation.runtime: python`. This is host-facing
guidance layered on the spec; the spec's §7 package contract and §10 stage
responsibilities govern. It will move into the spec once a second host exercises it.

## Entrypoint

A python-runtime chip package declares `implementation.entrypoint` as a dotted
module path relative to the chip package root, plus the callable:
`"<dotted.module.path>:<callable>"`. The host resolves the module path relative
to the package root, turning dots into directory separators — so a module
shipped at `impl/chip_impl.py` is addressed as `impl.chip_impl`. The v1
convention is `impl/chip_impl.py` exposing `run`, i.e. `impl.chip_impl:run`.

The host imports the module **inside its sandbox** (never in the host process
that holds credentials) and invokes:

```python
def run(activation: dict) -> dict: ...
```

## Activation (host → chip)

```jsonc
{
  "run_id":  "<host-minted run id; REQUIRED>",  // see below
  "signal":  { /* validated signal envelope, spec §8.1; hostile fields taint-marked.
                  May carry a taint-marked `content` payload under assessment. */ },
  "state":   { /* prior installation state per state schema, or null on first run */ },
  "config":  {
    /* binding-resolved chip parameters; never secret values. The host injects the
       canonical effect-key inputs (spec §8.3) so host and chip derive identical keys: */
    "promise_id":    "<operational-promise identity, manifest/binding-resolved>",
    "effect_target": "<target owning system for effects, binding-resolved>"
    /* ...plus any other binding-resolved parameters (gatewayProfile, approvalRoutes, ...) */
  },
  "gateway": "<callable>",  // host-provided; see below
  "upstream": { /* the prior chip's response for non-first circuit positions; null
                   for the first chip in the circuit */ }
}
```

`run_id` is a REQUIRED, host-injected top-level key (alongside `signal`, `state`,
`config`, `gateway`, and `upstream`). The host mints it and the implementation
uses it for its response coordinates (`producedByRun`) — the implementation MUST
NOT invent a run id of its own, and MUST NOT feed `run_id` into
`derive_effect_key` (the effect key excludes run identity, spec §8.3).

### Activation profiles (attention vs delegation)

The activation reaches the chip the same way regardless of how it was triggered
(spec §3.1). Two profiles produce it:

- **Attention profile** — an owner-side schedule or manual guarded action emits
  the activation signal (the original v1 path).
- **Delegation profile** — a harness or agent operating under the owning
  system's authority invokes an already-installed chip mid-workflow. The host
  constructs the same activation dict; the only difference the implementation can
  observe is that `signal.authorityContext` names the invoking agent's identity.

The implementation MUST NOT branch on the profile: a delegated run is receipted
identically, metered against the same `limits.*`, and gated by the same
effective authority (`chip ∩ circuit ∩ binding ∩ host ∩ approval`). The invoking
identity in `authorityContext` is attribution/policy context, never a grant. A
`partitioned(<keyField>)` chip (spec §9) is a delegation-profile shape: the host
computes the partition from the named signal field and single-flights per key,
letting distinct-key invocations proceed in parallel.

The effect-key inputs are deliberately host-supplied: `signal.lineageKey` and the
effect type come from the envelope and effect declaration, while `config.promise_id`
and `config.effect_target` are binding/manifest-resolved and injected here. An
implementation MUST read `promise_id`/`effect_target` from `config` (not invent
them) so its `derive_effect_key(...)` matches the host's recomputation (spec §8.3).

`gateway(request: dict) -> dict` is a host-owned callable:

- callable **at most once** per activation; a second call raises and fails the run;
- the host validates `request` against the declared gateway-stage request schema
  before dispatch, and the result against the result schema before returning it;
- when the `request` contains tainted content, the host MUST apply taint markers
  to the result's string fields before returning it — model output derived from
  hostile input is itself hostile-derived (spec §8.2 transitivity). The result
  inherits the trust of the request's most-hostile input, with the derivation
  chain appended with `"gateway"`; the library helper
  `chip.taint.taint_gateway_result(result, parent_taint)` does exactly this
  (string leaves wrapped, numbers/bools/None left bare, structure preserved);
- for a `deterministic`-class chip the host passes a gateway that always raises;
- in fixture/eval mode the host substitutes the fixture's canned result — the
  implementation cannot tell the difference and must not try;
- the host records the gateway request/result coordinates, usage, and cost in the
  run's judgment receipt (spec §10.2, §13).

## Result (chip → host)

```jsonc
{
  "response":     { /* response envelope, spec §8.2; kind: finding|quiet|abstain|needs_input */ },
  "state":        { /* full replacement state; host enforces schema + cursor monotonicity */ },
  "effects":      [ /* effect REQUESTS, spec §8.3; host owns policy, approval, dispatch */ ],
  "stage_events": [ /* ordered {stage, kind, started, ended, note} for receipts; non-contractual */ ]
}
```

Rules the host enforces (not the implementation's honor system):

- response/effects/state are schema-validated; any violation fails the run closed;
- taint markers present on signal fields must survive into any response field
  derived from them (`chip.taint`); the host rejects responses that place tainted
  content in instruction position;
- effect idempotency keys must be host-recomputed via `chip.envelopes.derive_effect_key`
  and match the implementation's claim;
- effect `judgmentReceiptRef` back-fill: an effect request is constructed before
  the run's judgment receipt exists, so the implementation MAY set
  `judgmentReceiptRef` to the sentinel `"pending"` (`chip.envelopes.PENDING_RECEIPT_REF`).
  The host MUST back-fill the real receipt reference before persisting or
  dispatching the effect; a dispatched effect still carrying `"pending"` is a host
  conformance violation (`chip.conformance` `check_dispatched_effects_carry_receipt_refs`);
- authority: each effect's class is checked against the effective ceiling
  (chip ∩ circuit ∩ binding ∩ host ∩ approval), fail closed;
- budgets/limits (`limits.*`) are metered by the host clock and accounting, not
  by the implementation.

The implementation is therefore a pure function of
`(signal, state, config, gateway)` — deterministic except for the single
gateway call — and everything consequential happens on the host side of the line.
