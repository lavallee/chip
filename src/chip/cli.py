"""The ``chip`` command — host-independent verbs over a chip package.

This CLI deliberately cannot install, activate, approve, or revoke anything. Those
verbs need a host: they touch durable state, authority, and effects, and the
whole point of the contract is that the host owns them. What lives here is
everything you can do to a *package* without a runtime — validate it, digest it,
check its fixtures, and ask whether it would load in this environment.

    chip validate <pkg>     manifest + declared schemas
    chip fixtures <pkg>     fixture inventory and §7 coverage
    chip digest <pkg>       the package's content-addressed identity (§16.1)
    chip preflight <pkg>    would this activate *here*? (§16.4)
    chip lint <pkg>         everything above, plus authoring conventions
    chip receipt <file>     validate a run or outcome receipt (§13)

Every command exits 0 on success and 1 on failure, and takes ``--json`` for
machine-readable output, so a skill or a CI step can consume it without parsing
prose.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from chip.errors import ChipError, FixtureError, ManifestError, ReceiptError
from chip.fixtures import load_fixtures, validate_fixture_coverage
from chip.manifest import load_chip_package
from chip.packaging import package_digest, preflight
from chip.receipts import OUTCOME_SCHEMA, RECEIPT_SCHEMA, validate_outcome, validate_receipt
from chip.version import SPEC_VERSION, VERSION

_OK = "ok"
_FAIL = "FAIL"


def _emit(payload: dict[str, Any], as_json: bool, lines: list[str]) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        for line in lines:
            print(line)


# -- commands ---------------------------------------------------------------


def cmd_validate(args: argparse.Namespace) -> int:
    try:
        manifest, resolved = load_chip_package(args.package)
    except (ManifestError, ChipError) as exc:
        _emit({"ok": False, "error": str(exc)}, args.json, [f"{_FAIL}: {exc}"])
        return 1
    meta = manifest.metadata
    payload = {
        "ok": True,
        "alias": meta.alias,
        "version": meta.version,
        "implementationClass": manifest.implementation.implementation_class,
        "entrypoint": manifest.implementation.entrypoint,
        "authorityCeiling": manifest.authority.maximum_effect_class.label,
        "schemas": sorted(resolved),
    }
    _emit(payload, args.json, [
        f"{_OK}: {meta.alias} {meta.version}",
        f"    class      {payload['implementationClass']}",
        f"    entrypoint {payload['entrypoint']}",
        f"    ceiling    {payload['authorityCeiling']}",
        f"    schemas    {len(resolved)} declared, all present",
    ])
    return 0


def cmd_fixtures(args: argparse.Namespace) -> int:
    try:
        fixtures = validate_fixture_coverage(args.package)
    except (FixtureError, ChipError) as exc:
        _emit({"ok": False, "error": str(exc)}, args.json, [f"{_FAIL}: {exc}"])
        return 1
    by_kind: dict[str, list[str]] = {}
    for f in fixtures:
        by_kind.setdefault(f.kind, []).append(f.name)
    payload = {"ok": True, "count": len(fixtures), "byKind": by_kind}
    lines = [f"{_OK}: {len(fixtures)} fixture(s), required kinds present"]
    for kind in sorted(by_kind):
        lines.append(f"    {kind:<12} {', '.join(sorted(by_kind[kind]))}")
    _emit(payload, args.json, lines)
    return 0


def cmd_digest(args: argparse.Namespace) -> int:
    try:
        digest = package_digest(args.package)
    except OSError as exc:
        _emit({"ok": False, "error": str(exc)}, args.json, [f"{_FAIL}: {exc}"])
        return 1
    _emit({"ok": True, "digest": digest}, args.json, [digest])
    return 0


def cmd_preflight(args: argparse.Namespace) -> int:
    report = preflight(args.package, check_entrypoint=not args.no_entrypoint)
    payload = {
        "ok": report.ok,
        "package": str(report.package_dir),
        "alias": report.alias,
        "digest": report.digest,
        "checks": [{"name": n, "ok": o, "detail": d} for n, o, d in report.checks],
    }
    lines = []
    for name, ok, detail in report.checks:
        lines.append(f"{_OK if ok else _FAIL}: {name:<17} {detail}")
    if not report.ok:
        lines.append("")
        lines.append(
            "This package would not activate in this environment. A host that "
            "installs it anyway will fail soft on every activation (§16.4)."
        )
    _emit(payload, args.json, lines)
    return 0 if report.ok else 1


def cmd_lint(args: argparse.Namespace) -> int:
    """Preflight plus the authoring conventions a package should follow."""
    report = preflight(args.package, check_entrypoint=not args.no_entrypoint)
    checks = [{"name": n, "ok": o, "detail": d} for n, o, d in report.checks]
    warnings: list[str] = []

    root = Path(args.package)
    if report.alias:
        manifest, _ = load_chip_package(root)
        if not (root / "README.md").is_file():
            warnings.append(
                "no README.md — a package that travels needs a human-readable promise"
            )
        if manifest.implementation.implementation_class == "hybrid":
            if manifest.implementation.authored_against is None:
                warnings.append(
                    "hybrid chip declares no implementation.authoredAgainst — the model "
                    "generation its judgment stage was tuned for is not recorded (§7.1)"
                )
            gateway_prompt = root / "impl" / "gateway_prompt.md"
            if not gateway_prompt.is_file():
                warnings.append(
                    "hybrid chip ships no impl/gateway_prompt.md — nothing declares which "
                    "artifact `optimize` may re-derive"
                )
        try:
            fixtures = load_fixtures(root / manifest.evaluation.fixtures)
            kinds = {f.kind for f in fixtures}
            if "duplicate" not in kinds:
                warnings.append(
                    "no duplicate fixture — at-least-once delivery is the delivery model, "
                    "so the dedupe path deserves a case"
                )
            if manifest.implementation.implementation_class == "hybrid" and not any(
                f.canned_gateway_result for f in fixtures
            ):
                warnings.append(
                    "hybrid chip has no fixture with a cannedGatewayResult — its suite "
                    "cannot run without a live model, so it can only ever record a "
                    "canned tuple and stays capped at observe (§10.2)"
                )
        except FixtureError:
            pass  # already a hard failure in the preflight checks

    payload = {"ok": report.ok, "checks": checks, "warnings": warnings}
    lines = [f"{_OK if o else _FAIL}: {n:<17} {d}" for n, o, d in report.checks]
    for w in warnings:
        lines.append(f"warn: {w}")
    if report.ok and not warnings:
        lines.append("")
        lines.append("clean")
    _emit(payload, args.json, lines)
    return 0 if report.ok else 1


def cmd_receipt(args: argparse.Namespace) -> int:
    """Validate receipts from files or stdin; one JSON object or JSONL per source."""
    sources: list[tuple[str, str]] = []
    if args.files:
        for path in args.files:
            try:
                sources.append((path, Path(path).read_text(encoding="utf-8")))
            except OSError as exc:
                _emit({"ok": False, "error": str(exc)}, args.json, [f"{_FAIL}: {exc}"])
                return 1
    else:
        sources.append(("<stdin>", sys.stdin.read()))

    results: list[dict[str, Any]] = []
    for name, text in sources:
        for lineno, raw in enumerate(text.splitlines(), start=1):
            raw = raw.strip()
            if not raw:
                continue
            entry: dict[str, Any] = {"source": name, "line": lineno}
            try:
                data = json.loads(raw)
            except json.JSONDecodeError as exc:
                entry.update(ok=False, error=f"invalid JSON: {exc}")
                results.append(entry)
                continue
            schema = data.get("schema")
            try:
                if schema == OUTCOME_SCHEMA:
                    validate_outcome(data)
                    entry.update(ok=True, kind="outcome")
                elif schema == RECEIPT_SCHEMA:
                    validate_receipt(data)
                    entry.update(
                        ok=True, kind="run", terminalReason=data.get("terminalReason")
                    )
                else:
                    entry.update(ok=False, error=f"unknown schema {schema!r}")
            except ReceiptError as exc:
                entry.update(ok=False, error=str(exc))
            results.append(entry)

    ok = all(r["ok"] for r in results) and bool(results)
    lines = []
    for r in results:
        if r["ok"]:
            lines.append(f"{_OK}: {r['source']}:{r['line']} {r.get('kind')}")
        else:
            lines.append(f"{_FAIL}: {r['source']}:{r['line']} {r.get('error')}")
    if not results:
        lines.append(f"{_FAIL}: no receipts found")
    _emit({"ok": ok, "results": results}, args.json, lines)
    return 0 if ok else 1


# -- parser -----------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="chip",
        description=(
            "Host-independent verbs over a chip package. Installing, activating, "
            "approving, and revoking need a host; this does not do them."
        ),
    )
    parser.add_argument(
        "--version", action="version", version=f"chipspec {VERSION} ({SPEC_VERSION})"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def add(name: str, help_: str, func) -> argparse.ArgumentParser:
        sp = sub.add_parser(name, help=help_)
        sp.add_argument("--json", action="store_true", help="machine-readable output")
        sp.set_defaults(func=func)
        return sp

    p = add("validate", "validate a package's manifest and declared schemas", cmd_validate)
    p.add_argument("package", help="path to the chip package directory")

    p = add("fixtures", "list fixtures and check §7 coverage", cmd_fixtures)
    p.add_argument("package", help="path to the chip package directory")

    p = add("digest", "print the package's content-addressed identity (§16.1)", cmd_digest)
    p.add_argument("package", help="path to the chip package directory")

    p = add("preflight", "check the package would load in THIS environment (§16.4)", cmd_preflight)
    p.add_argument("package", help="path to the chip package directory")
    p.add_argument("--no-entrypoint", action="store_true", help="skip the entry-point probe")

    p = add("lint", "preflight plus authoring conventions", cmd_lint)
    p.add_argument("package", help="path to the chip package directory")
    p.add_argument("--no-entrypoint", action="store_true", help="skip the entry-point probe")

    p = add("receipt", "validate run/outcome receipts (JSON or JSONL; stdin by default)", cmd_receipt)
    p.add_argument("files", nargs="*", help="receipt files; omit to read stdin")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.func(args))
    except ChipError as exc:  # a contract error is a failure, not a traceback
        print(f"{_FAIL}: {exc}", file=sys.stderr)
        return 1
    except BrokenPipeError:
        return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
