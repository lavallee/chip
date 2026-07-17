"""Fixture package format and coverage check (§7, §21).

A fixture package is a ``fixtures/`` directory whose immediate children each hold
a ``fixture.json``. Every fixture declares:

* ``kind`` — one of ``positive`` | ``quiet`` | ``failure`` | ``adversarial`` |
  ``duplicate``;
* ``input`` — a signal envelope (the activation);
* ``expected`` — the asserted outcome: an expected response ``kind``, a
  ``noEffect`` assertion, and/or an expected ``errorClass``; and
* optionally ``cannedGatewayResult`` — a pre-recorded gateway (model) result so
  a host can exercise a judgment stage without a live model (§10.2).

§7 requires a package to ship at least one positive, quiet, failure, and
adversarial fixture; :func:`validate_fixture_coverage` enforces that.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from chip.errors import FixtureError

FIXTURE_KINDS = ("positive", "quiet", "failure", "adversarial", "duplicate")
# §7 requires at least one of each of these four kinds.
REQUIRED_KINDS = ("positive", "quiet", "failure", "adversarial")


@dataclass(frozen=True, slots=True)
class Fixture:
    """A single loaded fixture case."""

    name: str
    kind: str
    input_signal: dict[str, Any]
    expected: dict[str, Any]
    canned_gateway_result: dict[str, Any] | None = None
    # Optional pre-seeded chip state for state-dependent behaviors (e.g. a
    # duplicate/dedup case). Hosts MUST pass this as the activation ``state``
    # when running the fixture; ``None`` means first-run (fresh state).
    prior_state: dict[str, Any] | None = None
    path: Path | None = field(default=None, compare=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any], name: str, path: Path | None = None) -> Fixture:
        kind = data.get("kind")
        if kind not in FIXTURE_KINDS:
            allowed = ", ".join(FIXTURE_KINDS)
            raise FixtureError(
                f"fixture {name!r}: unknown kind {kind!r}; expected one of: {allowed}"
            )
        if "input" not in data or not isinstance(data["input"], dict):
            raise FixtureError(f"fixture {name!r}: missing or non-object 'input' signal")
        expected = data.get("expected")
        if not isinstance(expected, dict) or not expected:
            raise FixtureError(f"fixture {name!r}: missing 'expected' outcome assertion")
        prior_state = data.get("priorState")
        if prior_state is not None and not isinstance(prior_state, dict):
            raise FixtureError(f"fixture {name!r}: 'priorState' must be an object when present")
        return cls(
            name=name,
            kind=kind,
            input_signal=data["input"],
            expected=expected,
            canned_gateway_result=data.get("cannedGatewayResult"),
            prior_state=prior_state,
            path=path,
        )


def load_fixtures(fixtures_dir: str | Path) -> list[Fixture]:
    """Load every ``*/fixture.json`` under ``fixtures_dir`` (sorted by name).

    Raises :class:`FixtureError` if the directory is missing or a fixture file is
    malformed.
    """
    root = Path(fixtures_dir)
    if not root.is_dir():
        raise FixtureError(f"fixtures directory not found: {root}")
    fixtures: list[Fixture] = []
    for child in sorted(root.iterdir()):
        fixture_file = child / "fixture.json"
        if not fixture_file.is_file():
            continue
        try:
            data = json.loads(fixture_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise FixtureError(f"fixture {child.name!r}: invalid JSON: {exc}") from exc
        fixtures.append(Fixture.from_dict(data, name=child.name, path=fixture_file))
    if not fixtures:
        raise FixtureError(f"no fixtures (*/fixture.json) found under {root}")
    return fixtures


def validate_fixture_coverage(manifest_dir: str | Path) -> list[Fixture]:
    """Assert a chip package ships the §7-required fixture kinds; return them.

    Reads the package's ``chip.json`` to locate the ``evaluation.fixtures``
    directory, loads all fixtures, and requires at least one positive, quiet,
    failure, and adversarial fixture. Raises :class:`FixtureError` listing any
    missing kinds.
    """
    root = Path(manifest_dir)
    manifest_path = root / "chip.json"
    fixtures_subdir = "fixtures/"
    if manifest_path.is_file():
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            fixtures_subdir = data.get("evaluation", {}).get("fixtures", "fixtures/")
        except json.JSONDecodeError as exc:
            raise FixtureError(f"chip.json is not valid JSON: {exc}") from exc
    fixtures = load_fixtures(root / fixtures_subdir)
    present = {f.kind for f in fixtures}
    missing = [k for k in REQUIRED_KINDS if k not in present]
    if missing:
        raise FixtureError(
            f"fixture coverage incomplete: missing required kind(s) {', '.join(missing)} "
            f"(§7 requires at least one each of {', '.join(REQUIRED_KINDS)})"
        )
    return fixtures
