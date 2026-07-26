---
name: chip-audit
description: Read a chip's receipts to find dark installations, fallback streaks, capped authority, and digest mismatches — invoke on a cadence, after any host deploy, and whenever a chip "seems fine" but nothing it recommends ever happens.
---

# chip-audit

A chip that is failing loudly gets fixed. This skill is for the other kind: the
one whose every receipt is well-formed, whose host degrades politely, and whose
silence reads as quiet operation. That failure mode is the default, not the
exception — plan to go looking.

## Command map (verbs → leaves)

| to do this | run |
|---|---|
| receipts for one installation | `fab chip receipts <installation-id> [--tail N]` |
| per-chip rollup | `fab chip stats [alias]` |
| comprehension one-pager | `fab chip datasheet <target> [--html PATH]` |
| validate receipts | `chip receipt <file…>` · or pipe JSONL on stdin |
| would it still load? (§16.4) | `chip preflight <pkg>` |
| package identity | `chip digest <pkg>` |

## The four silent failures

**1. Dark installation.** The chip has not completed an activation since some
date, and the host has been falling soft ever since. Nothing errors; the caller
just quietly gets the old behavior. Check the last *successful* activation
against the attention cadence — not the last receipt, which keeps arriving.

**2. Capped authority.** Effects proposed, none dispatched, every run. Read
`authority.reason`: `unevaluated-tuple` means go to [[chip-evaluate]];
`binding-ceiling` means the binding is the constraint and evaluation will not
help.

**3. Digest mismatch churn.** Repeated `implementation-digest-mismatch` failures
against one pin means ordinary edits are being made where the host expects a
succession (§16.3). See [[chip-install]].

**4. Effects that never execute.** `effects.proposed` is non-empty and
`effects.executed` is empty across many runs — either capped (see 2), or awaiting
a human approval nobody knows is pending. `promote`-class effects always require
one.

## Checklist

1. **Start with the rollup.** `fab chip stats` — call count, quiet rate, failure
   count, evaluation streak, interventions, and last activity per chip. Anything
   whose last activity is stale is suspect regardless of what its receipts say.
2. **Read the terminal reasons in bulk**, not one receipt at a time. The
   distribution is the diagnosis: an all-`no-actionable-finding` chip may be
   correctly quiet or may be broken upstream of its own judgment, and only the
   ratio over time distinguishes them.
3. **Look for a reason that repeats.** One `gateway-unavailable` is weather. Forty
   consecutive is an outage nobody was paged for.
4. **Check for fallback streaks on the host side.** A host is obliged to record
   fail-soft fallbacks against the installation that caused them and expose the
   consecutive count (§16.4). If the host cannot answer "how many activations in
   a row fell back", that is the first thing to fix — it is the difference
   between a five-day outage and a five-minute one.
5. **Re-preflight the installed packages.** `chip preflight <pkg>` in the
   deployed environment. A host upgrade can invalidate a package that installed
   cleanly months ago.
6. **Validate a sample of receipts against the contract.**
   ```bash
   fab chip receipts <iid> --tail 50 | chip receipt
   ```
   Receipts that no longer validate mean the host and the contract have drifted,
   and every conclusion drawn from those receipts is now suspect.
7. **Check that outcome receipts exist at all** (§13.3). A chip with run receipts
   and no outcome receipts can be evaluated but not calibrated: you can see what
   it decided and never learn whether it was right. If the host is keeping that
   record privately, it belongs in the contract — that is what the outcome
   receipt is for.

## Reading the authority block

```json
"authority": { "effectiveCeiling": "observe", "reason": "unevaluated-tuple" }
```

| reason | meaning | lever |
|---|---|---|
| `binding-ceiling` | the binding's own ceiling bound the run | raise the binding, if you mean to |
| `unevaluated-tuple` | no passing held-out suite for the served tuple | [[chip-evaluate]] `--live` |
| `environment-profile` | a host environment profile lowered it | host config |
| `operator-paused` | the installation is paused | `fab chip` resume path |
| `policy-denied` | policy refused outright | read the decisions block |

## What to do with what you find

Fix the host obligation before the chip. A dark chip that gets restarted without
liveness reporting will go dark again, and you will find it the same way: by
accident, later.
