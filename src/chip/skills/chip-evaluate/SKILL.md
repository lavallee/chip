---
name: chip-evaluate
description: Run a chip's held-out suite, record the evaluated tuple, and explain why authority is capped — invoke before lifting a binding above observe, after any model or profile change, and whenever a chip proposes effects that never dispatch.
---

# chip-evaluate

Authority is not configured, it is earned by a specific
`(implementation, gatewayProfile, servedModel, harness)` tuple passing a
held-out suite. Every part of that tuple is load-bearing: change any one of
them and the binding drops back to `observe`.

## Command map (verbs → leaves)

| to do this | run |
|---|---|
| run the suite, record the tuple | `fab chip evaluate <installation-id> [--live] [--operator <id>]` |
| read what a run decided | `fab chip receipts <installation-id> [--tail N]` |
| per-chip rollup | `fab chip stats [alias]` |
| fixture inventory + §7 coverage | `chip fixtures <pkg>` |
| validate receipts | `chip receipt <file…>` |

## The failure this skill exists to prevent

A chip proposes effects on every activation. The effects have
`approvalRequired: automatic`. None of them ever dispatch. Nothing errors, every
receipt is well-formed, and the chip looks like it is working.

The cause is always the same: the served tuple has no passing evaluation, so the
run ceiling is capped at `observe`, so a `synthesize`-class effect is never
approved. In production this ran for weeks across twenty proposed effects and
zero dispatches.

**The receipt says so explicitly.** The `authority` block carries the effective
ceiling and one reason:

```json
"authority": { "effectiveCeiling": "observe", "reason": "unevaluated-tuple" }
```

`unevaluated-tuple` means run an evaluation. `binding-ceiling` means the binding
itself is the constraint and evaluating will change nothing — raise the binding
instead, if you mean to.

## Checklist

1. **Read the current ceiling before doing anything.**
   ```bash
   fab chip receipts <installation-id> --tail 5
   ```
   Find `authority.effectiveCeiling` and `authority.reason`. Those two fields
   tell you whether evaluation is even the right lever.
2. **Check fixture coverage first.** `chip fixtures <pkg>` — an evaluation
   against an incomplete suite records a tuple that means less than it appears
   to.
3. **Run the canned pass** to validate the deterministic envelope:
   ```bash
   fab chip evaluate <installation-id> --operator <you>
   ```
   This records a tuple whose served model is the canned marker.
4. **Understand that the canned pass did not lift anything.** It proves plumbing.
   The recorded tuple's served model is `canned/deterministic`, which is not the
   model any activation will use.
5. **Run the live pass against the model you actually intend to bind:**
   ```bash
   fab chip evaluate <installation-id> --live --operator <you>
   ```
   Now the recorded tuple matches what activation will compute, and the cap can
   lift.
6. **Re-evaluate after any change to any tuple member.** A model swap, a profile
   rename, an implementation edit, or a harness change all mint a new tuple and
   drop the binding back to `observe`. This is deliberate — but it means a model
   upgrade is an evaluation event, not a config change.
7. **Confirm the lift.** Activate once and read the receipt: `effectiveCeiling`
   should now be the binding's ceiling with reason `binding-ceiling`.
8. **If effects still do not dispatch**, the ceiling is no longer the problem —
   check the effect's approval class (a `promote`-class effect requires an
   explicit human approval regardless of ceiling) and see [[chip-audit]].

## Optimize

`fab chip optimize <installation-id>` re-derives a hybrid chip's judgment
artifact and re-evaluates it, accepting only on a held-out improvement. It
refuses outright when the package ships no declared optimizable artifact —
`impl/gateway_prompt.md`. If you get that refusal, the fix is in
[[chip-author]], not here.

Next: [[chip-install]] to bind it, [[chip-audit]] to watch it.
