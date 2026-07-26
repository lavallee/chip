"""Package identity, resolution, and preflight (§16).

Two hosts that compute a package's identity differently do not have the same
chip, so identity is part of the contract rather than a host detail:
:func:`package_digest` is the normative computation.

:func:`preflight` is the §16.4 obligation in executable form — it answers "would
this package activate *here*", in the environment where activations will run,
which is the check whose absence took a production chip dark for nearly five
days while every receipt it wrote looked well-formed.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

from chip.errors import ChipError, FixtureError, ManifestError
from chip.fixtures import validate_fixture_coverage
from chip.manifest import load_chip_package

# Build artifacts are excluded so a byte-identical source tree yields the same
# digest whether or not it has been imported.
_EXCLUDE_DIR_NAMES = {"__pycache__", ".git", ".mypy_cache", ".pytest_cache", ".ruff_cache"}
_EXCLUDE_SUFFIXES = {".pyc", ".pyo"}


def _iter_files(root: Path):
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        parts = set(path.relative_to(root).parts)
        if parts & _EXCLUDE_DIR_NAMES:
            continue
        if path.suffix in _EXCLUDE_SUFFIXES:
            continue
        yield path


def package_digest(package_dir: str | Path) -> str:
    """Return ``"sha256:<hex>"`` over the package directory's sorted file set (§16.1).

    A package's identity is this value. A host resolves an installed chip from a
    content-addressed store keyed on it, recomputes it at activation, and fails
    closed on an unexplained mismatch (§16.3).

    Raises :class:`FileNotFoundError` if the directory does not exist.
    """
    root = Path(package_dir)
    if not root.is_dir():
        raise FileNotFoundError(f"chip package directory not found: {root}")
    h = hashlib.sha256()
    for path in _iter_files(root):
        rel = path.relative_to(root).as_posix()
        h.update(rel.encode("utf-8"))
        h.update(b"\0")
        h.update(path.read_bytes())
        h.update(b"\0")
    return "sha256:" + h.hexdigest()


def split_entrypoint(entrypoint: str) -> tuple[str, str]:
    """Split a ``module.path:callable`` entry point (§16.2).

    The entry point is *declared*, never discovered: a host may not go looking
    through a package's module layout for something that looks runnable.
    """
    if ":" not in entrypoint:
        raise ManifestError(
            f"entrypoint {entrypoint!r} must be 'module.path:callable' (§16.2)"
        )
    module, _, attr = entrypoint.partition(":")
    if not module or not attr:
        raise ManifestError(f"entrypoint {entrypoint!r} is missing a module or callable (§16.2)")
    return module, attr


@dataclass
class PreflightReport:
    """The result of asking whether a package would activate in this environment."""

    package_dir: Path
    digest: str | None = None
    alias: str | None = None
    checks: list[tuple[str, bool, str]] = field(default_factory=list)

    def record(self, name: str, ok: bool, detail: str = "") -> None:
        self.checks.append((name, ok, detail))

    @property
    def ok(self) -> bool:
        return all(ok for _name, ok, _detail in self.checks)

    @property
    def failures(self) -> list[tuple[str, bool, str]]:
        return [c for c in self.checks if not c[1]]


def preflight(package_dir: str | Path, *, check_entrypoint: bool = True) -> PreflightReport:
    """Check that a package resolves and would load, here (§16.4).

    Runs, in order: the package directory exists; ``chip.json`` parses and
    validates; every declared schema ships; fixture coverage meets §7; and — the
    check that matters most — the declared entry point's module is importable
    **in this environment**, not merely present in the authoring workspace.

    Never raises for a failed check; the report carries them. Pass
    ``check_entrypoint=False`` to skip the import probe when validating a package
    for a runtime other than this one.
    """
    root = Path(package_dir)
    report = PreflightReport(package_dir=root)

    if not root.is_dir():
        report.record("package-resolves", False, f"no such directory: {root}")
        return report
    report.record("package-resolves", True, str(root))

    try:
        report.digest = package_digest(root)
        report.record("digest", True, report.digest)
    except OSError as exc:
        report.record("digest", False, str(exc))
        return report

    try:
        manifest, resolved = load_chip_package(root)
    except (ManifestError, ChipError) as exc:
        report.record("manifest", False, str(exc))
        return report
    report.alias = manifest.metadata.alias
    report.record("manifest", True, f"{manifest.metadata.alias} {manifest.metadata.version}")
    report.record("schemas", True, f"{len(resolved)} declared schema(s) present")

    try:
        fixtures = validate_fixture_coverage(root)
        report.record("fixtures", True, f"{len(fixtures)} fixture(s), required kinds present")
    except FixtureError as exc:
        report.record("fixtures", False, str(exc))

    if check_entrypoint:
        entry = manifest.implementation.entrypoint
        if manifest.implementation.runtime != "python":
            report.record(
                "entrypoint", True,
                f"{entry} (runtime {manifest.implementation.runtime!r} not probed here)",
            )
        else:
            try:
                module, attr = split_entrypoint(entry)
                found = _module_is_importable(root, module)
                if found is None:
                    report.record(
                        "entrypoint", False,
                        f"module {module!r} of entrypoint {entry!r} is not importable from "
                        f"{root} — this is the failure that resolves in the authoring "
                        "workspace and not in the execution environment (§16.4)",
                    )
                else:
                    report.record("entrypoint", True, f"{entry} -> {found} (callable {attr!r})")
            except ManifestError as exc:
                report.record("entrypoint", False, str(exc))

    return report


def _module_is_importable(root: Path, module: str) -> Path | None:
    """Resolve ``module`` to a file under ``root``, or return None.

    Deliberately a *path* resolution rather than a real import: preflight must not
    execute package code to decide whether the package is loadable. The entry
    point is resolved **relative to the package root** and nowhere else — a chip
    that only loads because something happened to be importable from the ambient
    environment is exactly the non-portable case §16.2 rules out.
    """
    rel = Path(*module.split("."))
    for candidate in (root / rel.with_suffix(".py"), root / rel / "__init__.py"):
        if candidate.is_file():
            return candidate
    return None
