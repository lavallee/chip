---
name: chip-fixtures
description: Build the fixture suite that gates a chip's authority — invoke while authoring, before any evaluation, and whenever a production failure has no fixture that would have caught it.
---

# chip-fixtures

The fixture suite is not a test-coverage exercise. It is the evidence that lifts
a binding above `observe`, so its gaps become production authority you did not
mean to grant — or authority you cannot obtain.

## Command map (verbs → leaves)

| to do this | run |
|---|---|
| fixture inventory + §7 coverage | `chip fixtures <pkg>` |
| package + authoring conventions | `chip lint <pkg>` |
| validate a package | `chip validate <pkg>` |
| run the suite as held-out (host) | `fab chip evaluate <installation-id> [--live]` |

## Fixture shape

```json
{
  "kind": "positive|quiet|failure|adversarial|duplicate",
  "input": { "…": "a signal envelope" },
  "expected": { "kind": "…", "noEffect": true, "errorClass": "…" },
  "cannedGatewayResult": { "…": "a pre-recorded model result" },
  "priorState": { "…": "state to pre-seed, for state-dependent cases" }
}
```

`expected` must assert something — a fixture that asserts nothing passes
forever.

## Checklist

1. **Cover the four required kinds** (§7): `positive`, `quiet`, `failure`,
   `adversarial`. `chip fixtures <pkg>` fails until they are all present.
2. **Add a `duplicate` fixture.** Delivery is at-least-once; the dedupe path is
   load-bearing and is not exercised by any of the four. Use `priorState` to
   pre-seed the seen-set so the second delivery has something to collide with.
3. **Make the quiet case a real assertion.** `noEffect: true`. A quiet run is a
   first-class outcome, not an absence — most production activations are quiet,
   and a chip that cannot be quiet cheaply is a chip that will be turned off.
4. **Write adversarial fixtures that attack the right thing.** Hostile source
   text trying to become chip, host, model, or agent instructions — with taint
   asserted through to the final adapter. Not "malformed JSON": that is the
   `failure` kind.
5. **Cover the failure modes that actually happen.** From production: an
   exhausted gateway (`gateway-unavailable`), and a gateway that answers with
   something that fails schema validation (`gateway-result-invalid`). The second
   is much more common than authors expect, and fails closed only if you assert
   it does.
6. **Ship `cannedGatewayResult` on at least one hybrid fixture.** Without one,
   the suite cannot run without a live model, so it can only ever record a
   *canned* tuple — and a canned tuple does not lift a live binding above
   `observe`. This is the trap in [[chip-evaluate]]; it starts here.
7. **Add a fixture for every production failure**, before fixing it. If a chip
   failed in a way no fixture predicted, the suite was wrong, and the fix
   without the fixture just moves the surprise.
8. **Re-check coverage after any port change.**
   ```bash
   chip fixtures <pkg> && chip lint <pkg>
   ```

## Canned versus live

A canned evaluation validates the deterministic envelope and records a tuple
whose served model is the canned marker. It proves the chip's plumbing. It does
**not** evaluate a live model tuple, and it will not lift authority. Plan for
both: canned fixtures for the envelope, and a held-out live run for the tuple
you actually intend to bind. See [[chip-evaluate]].

Next: [[chip-evaluate]].
