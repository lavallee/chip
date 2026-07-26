---
name: chip-author
description: Author a chip package from one operational promise — invoke after chip-candidate says "chip", or when adapting an existing package to a new contract version.
---

# chip-author

One promise, typed ports, declared state, declared authority, and a fixture
suite that can fail. The manifest is the contract; the implementation is
replaceable.

## Command map (verbs → leaves)

| to do this | run |
|---|---|
| validate a package | `chip validate <pkg>` |
| fixture inventory + §7 coverage | `chip fixtures <pkg>` |
| package identity (§16.1) | `chip digest <pkg>` |
| would it load *here*? (§16.4) | `chip preflight <pkg>` |
| package + authoring conventions | `chip lint <pkg>` |
| validate receipts | `chip receipt <file…>` |

## Package layout

```text
<pkg>/
  chip.json              the contract — promise, ports, state, authority, limits
  README.md              the human-readable promise, and what stayed probabilistic
  impl/
    chip_impl.py         the declared entrypoint's module
    gateway_prompt.md    hybrid chips only — the artifact `optimize` may re-derive
  schemas/*.json         every schema the manifest declares, shipped
  fixtures/<case>/fixture.json
```

## Checklist

1. **Write the promise first**, in `chip.json` metadata and in the README, in
   the same words. A promise you cannot state without "and" is more than one
   chip.
2. **Declare the ports.** Inputs and outputs carry schema refs of the form
   `schemas/name.json@N`. The `@N` pins the schema *version* — two circuit ports
   are compatible only when their whole refs match, so bump `@N` when the shape
   changes rather than editing a schema in place.
3. **Declare state, or declare none.** `single-flight` for anything with a
   cursor. `partitioned(<keyField>)` only for delegation-profile map/cache
   chips, and the key must name a declared signal-envelope field.
4. **Declare the entrypoint** as `module.path:callable`, resolved **relative to
   the package root** (§16.2). A host will not go looking through your module
   layout for something runnable, and must never need a symbol from the contract
   library's internals — import from `chip`, never from `chip.<submodule>`.
5. **Set the authority ceiling to the lowest class that can work.** Every
   declared effect must sit at or below it; the manifest will not load
   otherwise. `observe` and `synthesize` are the honest defaults. Nothing you
   write here grants authority — a binding does, and the host enforces it.
6. **Set limits that bite.** `maxActivationsPerHour`, `maxEffectsPerDay`,
   `modelBudgetUsd`, `timeout`. An unbounded chip is one bad signal away from
   being the incident.
7. **For a hybrid chip, isolate the judgment.** At most one gateway stage.
   Ship `impl/gateway_prompt.md` so `optimize` has a declared artifact to
   re-derive — a chip without one gets refused, which is the single most common
   thing that has gone wrong in practice. Record
   `implementation.authoredAgainst` with the model generation you tuned against.
8. **Write the fixtures before the implementation.** See [[chip-fixtures]] —
   §7 requires positive, quiet, failure, and adversarial at minimum, and the
   suite is what gates authority later.
9. **Lint until clean, then preflight.**
   ```bash
   chip lint <pkg> && chip preflight <pkg>
   ```
   `lint` warns about conventions; `preflight` answers the only question that
   matters at install time — would this load in the environment where
   activations will actually run.

## What stays probabilistic

Put a heading in the README naming what stayed a gateway judgment and why it
resisted eviction to deterministic code. This is the falsifiability residue: the
part of the chip that a better model might make unnecessary, written down while
you still remember the argument. It is also what `retire --reason
model-generation` will be measured against.

Next: [[chip-fixtures]], then [[chip-evaluate]], then [[chip-install]].
