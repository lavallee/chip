# Host execution contract (v1, python runtime)

Status: v1 convention for `implementation.runtime: python`. This is host-facing
guidance layered on the spec; the spec's §7 package contract and §10 stage
responsibilities govern. It will move into the spec once a second host exercises it.

## Entrypoint

A python-runtime chip package declares `implementation.entrypoint` as
`"<module>:<callable>"`, resolved relative to the chip package directory
(v1 convention: `impl/chip_impl.py` exposing `run`, i.e. `chip_impl:run`).

The host imports the module **inside its sandbox** (never in the host process
that holds credentials) and invokes:

```python
def run(activation: dict) -> dict: ...
```

## Activation (host → chip)

```jsonc
{
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

The effect-key inputs are deliberately host-supplied: `signal.lineageKey` and the
effect type come from the envelope and effect declaration, while `config.promise_id`
and `config.effect_target` are binding/manifest-resolved and injected here. An
implementation MUST read `promise_id`/`effect_target` from `config` (not invent
them) so its `derive_effect_key(...)` matches the host's recomputation (spec §8.3).

`gateway(request: dict) -> dict` is a host-owned callable:

- callable **at most once** per activation; a second call raises and fails the run;
- the host validates `request` against the declared gateway-stage request schema
  before dispatch, and the result against the result schema before returning it;
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
- authority: each effect's class is checked against the effective ceiling
  (chip ∩ circuit ∩ binding ∩ host ∩ approval), fail closed;
- budgets/limits (`limits.*`) are metered by the host clock and accounting, not
  by the implementation.

The implementation is therefore a pure function of
`(signal, state, config, gateway)` — deterministic except for the single
gateway call — and everything consequential happens on the host side of the line.
