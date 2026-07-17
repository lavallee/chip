# Contributing to chip

`chip` is the contract for portable, versioned operational components.
This repository is the spec, the validation library, and the
conformance kit — not a runtime. Contributions welcome.

## Dev setup

```bash
git clone https://github.com/lavallee/chip && cd chip
uv sync
uv run pytest
uv run ruff check src/ tests/
```

That's it — no separate venv bootstrapping, no Docker required.

## Repo layout

- `spec/` — the chip spec itself (`chip-spec.md`)
- `src/chip/` — the `chip` package: validation and conformance helpers
- `examples/` — example chips exercising the contract
- `tests/` — the conformance test suite

## Making a change

1. Write the code and tests. Behavior changes need tests — a PR that
   changes what `chip` validates or accepts without a test covering it
   will get bounced.
2. Add a `CHANGELOG.md` entry under `## [Unreleased]`. Be specific
   about what changed and why; future-you and downstream hosts both
   read this file.
3. If your change touches versioned files (`pyproject.toml`,
   `src/chip/version.py`), see [`RELEASING.md`](./RELEASING.md) before
   bumping anything yourself.
4. Run the full check before opening a PR:
   ```bash
   uv run pytest
   uv run ruff check src/ tests/
   ```

## Scope note

Changes that add a runtime, a host, or an LLM-gateway integration to
this repository are out of scope — those live in downstream projects
(a host such as fab (being open-sourced), a gateway such
as [somm](https://github.com/lavallee/somm)). This repo stays the
contract every host and gateway can implement against.
