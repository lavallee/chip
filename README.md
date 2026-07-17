# chip

**A contract for portable, versioned operational components.**

Chips are packaged units that observe declared signals, apply bounded
(optionally LLM-backed) judgment, and produce policy-gated responses
with receipts. Chips compose into linear circuits; hosts bind and run
them.

[![CI](https://github.com/lavallee/chip/actions/workflows/ci.yml/badge.svg)](https://github.com/lavallee/chip/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](./LICENSE)

## What is a chip

A **chip** is one packaged, versioned unit of judgment. It declares the
**ports** it reads and writes — its inputs and outputs — and one bounded
operational promise: observe what it's told to observe, decide within
its own scope, and emit a **receipt** for every run, including the
quiet ones where it does nothing. Internally a chip may run several
**stages** (deterministic code, one gateway judgment, validation,
policy), but the stages are implementation detail — the promise, ports,
state, effects, and authority are the contract.

Chips compose into a **circuit** — a linear sequence of chips, each
consuming the prior chip's ports and producing its own. A **host** is
the runtime that owns a **binding**: it wires a circuit's ports to real
data, executes each chip in order, enforces policy, and persists
receipts. A chip that needs LLM-backed judgment reaches it through a
**gateway** — the host-provided path to model access — rather than
holding its own credentials. The **owning system** is whatever product
or team the host and its circuits ultimately serve.

This repository is the contract itself: the spec, a validation
library, and a conformance kit. It is **not a runtime** — it has zero
runtime dependencies. fab is the reference host implementation (being
open-sourced); [somm](https://github.com/lavallee/somm) is a reference
gateway.

## Install

```bash
pip install chipspec
```

With schema validation for port payloads:

```bash
pip install "chipspec[jsonschema]"
```

Requires Python 3.12+. The import package is `chip` (the distribution
is named `chipspec` on PyPI because `chip` is squatted).

## Status

v0 experiment — one host (fab, being open-sourced),
contract under active evolution. See
[`spec/chip-spec.md`](./spec/chip-spec.md) for the current spec.

## Layout

| Path | What it is |
| --- | --- |
| `spec/` | The chip spec — the normative contract text |
| `src/chip/` | The `chip` package: validation and conformance helpers |
| `examples/` | Example chips exercising the contract |
| `tests/` | The conformance test suite |

## Design principles

- **One promise per chip.** A chip declares one bounded job and does
  only that job.
- **Deterministic envelope around probabilistic judgment.** LLM-backed
  decisions live inside a fixed, inspectable shape — ports, policy
  gates, and receipts don't get to be probabilistic too.
- **Authority fails closed.** No implicit escalation. Absent explicit
  policy grant, a chip acts as if it has none.
- **Receipts for every run, including quiet ones.** A chip that
  observes and decides not to act still produces a receipt saying so.
- **Taint is transitive.** Anything a chip's judgment touches carries
  forward whatever provenance or trust constraints it entered with.
- **Targets own final deduplication.** A chip proposes; whatever system
  it writes into is the one source of truth for whether that write is
  new.

## Contributing

See [`CONTRIBUTING.md`](./CONTRIBUTING.md). Security issues:
[`SECURITY.md`](./SECURITY.md). Releasing: [`RELEASING.md`](./RELEASING.md).

## License

MIT — see [`LICENSE`](./LICENSE).
