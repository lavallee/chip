---
name: chip-install
description: Bind and install a chip package against a host, with the preflight that catches unresolvable packages — invoke when wiring a circuit into a host, and before every deploy of a host that runs chips.
---

# chip-install

The install is where a portable contract meets one machine. Almost everything
that has gone wrong in production went wrong here, and every failure looked
identical from the outside: a well-formed receipt saying nothing happened.

## Command map (verbs → leaves)

| to do this | run |
|---|---|
| would it load *here*? (§16.4) | `chip preflight <pkg>` |
| package identity (§16.1) | `chip digest <pkg>` |
| package + authoring conventions | `chip lint <pkg>` |
| install a circuit + binding | `fab chip install <circuit> <binding> --operator <id>` |
| activate | `fab chip activate <installation-id> --signal <file>` |
| approve a pending effect | `fab chip approve <installation-id> <effect-key> --operator <id>` |
| pause / revoke | `fab chip pause <iid>` · `fab chip revoke <iid> --reason <r>` |
| receipts | `fab chip receipts <installation-id> [--tail N]` |

## Checklist

1. **Preflight in the environment the host will actually run in.**
   ```bash
   chip preflight <pkg>
   ```
   Not on your laptop for a service that runs elsewhere — *there*. A package
   whose entry point resolves in the authoring workspace and not in the service
   install took a production chip dark for nearly five days across 74 consecutive
   activations, every one of them fail-soft and silent.
2. **Record the digest you are pinning.** `chip digest <pkg>`. This is the
   package's identity (§16.1), and what an integrity check compares against.
3. **Resolve the binding's three layers.** Manifest defaults, then the host
   environment profile, then the binding. The effective authority is the
   intersection — never the maximum.
4. **Set the binding ceiling to what you mean to allow**, remembering that an
   unevaluated tuple caps it further ([[chip-evaluate]]). Effects of class
   `promote` require explicit human approval regardless.
5. **Install with a named operator.** The operator identity is required and
   never silently defaulted; it is what makes the lifecycle record answerable.
   ```bash
   fab chip install <circuit.json> <binding.json> --operator <you>
   ```
6. **Activate once against a known signal, and read the receipt.** Confirm the
   terminal reason is what you expect and the authority reason is
   `binding-ceiling` rather than `unevaluated-tuple`.
7. **Then activate the same signal again.** The second run must be
   `duplicate-signal` with no new effect. At-least-once delivery is the model;
   if dedupe does not hold here it will not hold under retry.

## Upgrading an installed chip

Editing a chip's implementation changes its digest. Under §16.3 that is a
**succession** — an upgrade in place that preserves installation identity,
cursor lineage, dedupe keys, and effect keys — not a revoke-and-reinstall.

An unexplained digest change, with no succession on record, is an integrity
violation and fails closed with `implementation-digest-mismatch`. If you are
seeing that reason after an ordinary edit, you performed an edit where the host
expected a succession.

Two chips once produced 13 installs and 11 revokes in eight days because every
ordinary edit presented as a supply-chain event. Reinstalling to clear it throws
away the cursor, and the chip re-processes history.

## Deploy checklist for a host that runs chips

Run this on every deploy, not only on the first:

1. `chip preflight <pkg>` for every installed package, in the deployed
   environment;
2. confirm no installation is **dark** — see [[chip-audit]];
3. confirm the contract library version the host ships still satisfies each
   package's declared compatibility. A package must never import a contract
   library submodule directly; if one does, it will break on a library refactor
   that changed nothing in the contract.

Next: [[chip-audit]].
