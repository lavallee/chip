"""The `chip` CLI and the packaging surface it wraps (§16)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from chip.cli import main
from chip.errors import ManifestError
from chip.packaging import package_digest, preflight, split_entrypoint

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
PUB = EXAMPLES / "publication-attention"


def run(capsys, *argv) -> tuple[int, dict]:
    """Run the CLI with --json and return (exit code, parsed payload)."""
    code = main([*argv, "--json"])
    return code, json.loads(capsys.readouterr().out)


# -- digest -----------------------------------------------------------------


def test_digest_is_stable_and_content_addressed(tmp_path):
    a = tmp_path / "a"
    shutil.copytree(PUB, a)
    assert package_digest(a) == package_digest(PUB)


def test_digest_changes_when_content_changes(tmp_path):
    a = tmp_path / "a"
    shutil.copytree(PUB, a)
    (a / "impl" / "chip_impl.py").write_text("# edited\n", encoding="utf-8")
    assert package_digest(a) != package_digest(PUB)


def test_digest_ignores_build_artifacts(tmp_path):
    a = tmp_path / "a"
    shutil.copytree(PUB, a)
    before = package_digest(a)
    (a / "impl" / "__pycache__").mkdir(parents=True, exist_ok=True)
    (a / "impl" / "__pycache__" / "chip_impl.pyc").write_bytes(b"\x00compiled")
    assert package_digest(a) == before


def test_digest_of_missing_directory_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        package_digest(tmp_path / "nope")


# -- entrypoint (§16.2) -----------------------------------------------------


def test_split_entrypoint():
    assert split_entrypoint("impl.chip_impl:run") == ("impl.chip_impl", "run")


@pytest.mark.parametrize("bad", ["impl.chip_impl", ":run", "impl.chip_impl:"])
def test_malformed_entrypoint_rejected(bad):
    with pytest.raises(ManifestError):
        split_entrypoint(bad)


# -- preflight (§16.4) ------------------------------------------------------


def test_preflight_passes_on_a_shipped_example():
    report = preflight(PUB)
    assert report.ok, report.failures
    assert report.alias == "examples.publication-attention"


def test_preflight_catches_an_unresolvable_entrypoint(tmp_path):
    """The production failure: the package resolves, the implementation does not.

    A package whose impl is absent still has a valid manifest, shipped schemas,
    and full fixture coverage — every check except the one that matters passes.
    """
    pkg = tmp_path / "pkg"
    shutil.copytree(PUB, pkg)
    shutil.rmtree(pkg / "impl")
    report = preflight(pkg)
    assert not report.ok
    assert [name for name, ok, _ in report.checks if not ok] == ["entrypoint"]


def test_preflight_does_not_resolve_from_the_ambient_environment(tmp_path, monkeypatch):
    """A chip that only loads because a same-named module is installed is not portable."""
    pkg = tmp_path / "pkg"
    shutil.copytree(PUB, pkg)
    shutil.rmtree(pkg / "impl")
    # Make an 'impl.chip_impl' importable from the environment; preflight must
    # still fail, because the entry point resolves against the package root only.
    ambient = tmp_path / "ambient" / "impl"
    ambient.mkdir(parents=True)
    (ambient / "__init__.py").write_text("", encoding="utf-8")
    (ambient / "chip_impl.py").write_text("def run(*a, **k): ...\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path / "ambient"))
    assert not preflight(pkg).ok


def test_preflight_reports_a_missing_package_without_raising(tmp_path):
    report = preflight(tmp_path / "nope")
    assert not report.ok
    assert report.checks[0][0] == "package-resolves"


def test_preflight_can_skip_the_entrypoint_probe(tmp_path):
    pkg = tmp_path / "pkg"
    shutil.copytree(PUB, pkg)
    shutil.rmtree(pkg / "impl")
    assert preflight(pkg, check_entrypoint=False).ok


# -- commands ---------------------------------------------------------------


def test_validate_reports_the_contract(capsys):
    code, payload = run(capsys, "validate", str(PUB))
    assert code == 0
    assert payload["alias"] == "examples.publication-attention"
    assert payload["implementationClass"] == "hybrid"


def test_validate_fails_on_a_non_package(capsys, tmp_path):
    code, payload = run(capsys, "validate", str(tmp_path))
    assert code == 1
    assert payload["ok"] is False


def test_fixtures_groups_by_kind(capsys):
    code, payload = run(capsys, "fixtures", str(PUB))
    assert code == 0
    assert set(payload["byKind"]) >= {"positive", "quiet", "failure", "adversarial"}


def test_preflight_command_exits_nonzero_on_failure(capsys, tmp_path):
    pkg = tmp_path / "pkg"
    shutil.copytree(PUB, pkg)
    shutil.rmtree(pkg / "impl")
    code, payload = run(capsys, "preflight", str(pkg))
    assert code == 1
    assert any(c["name"] == "entrypoint" and not c["ok"] for c in payload["checks"])


def test_lint_warns_without_failing(capsys):
    code, payload = run(capsys, "lint", str(PUB))
    assert code == 0
    # The shipped example has no gateway_prompt.md, which `optimize` needs to
    # have anything to re-derive — exactly the refusal seen in production.
    assert any("gateway_prompt.md" in w for w in payload["warnings"])


def test_receipt_validates_a_current_receipt(capsys, tmp_path):
    from chip.receipts import Authority, Coordinates, build_receipt

    receipt = build_receipt(
        Coordinates(run="run:1", installation="i", circuit="c", chip="ch", binding="b"),
        run_status="completed",
        semantic_outcome="quiet",
        terminal_reason="no-actionable-finding",
        digests={"contract": "sha:c", "implementation": "sha:i"},
        authority=Authority(effective_ceiling="observe", reason="unevaluated-tuple"),
    )
    path = tmp_path / "r.jsonl"
    path.write_text(json.dumps(receipt.to_dict()) + "\n", encoding="utf-8")
    code, payload = run(capsys, "receipt", str(path))
    assert code == 0
    assert payload["results"][0]["kind"] == "run"


def test_receipt_rejects_a_superseded_tier_schema(capsys, tmp_path):
    """0.5-era receipts do not validate; the tiers are gone."""
    path = tmp_path / "r.jsonl"
    path.write_text(
        json.dumps({"schema": "chip.receipt/v0alpha1#attention", "coordinates": {}}) + "\n",
        encoding="utf-8",
    )
    code, payload = run(capsys, "receipt", str(path))
    assert code == 1
    assert "unknown schema" in payload["results"][0]["error"]
