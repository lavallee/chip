"""Tests for the chip datasheet generator + its two renderers.

Builds datasheets against the two shipped example packages
(``examples/publication-attention``, a hybrid chip with a gateway stage, and
``examples/bounded-recommendation``, a deterministic effect chip), with and
without host-supplied telemetry, and asserts:

* section presence in the Markdown render (snapshot-ish, structural);
* the HTML carries no ``http(s)`` references except GitHub links, and links the
  supplied artoo-kit stylesheets;
* the projection-manifest coverage statement names every absent input;
* presence-is-never-evidence: no telemetry → observe-capped + "no telemetry yet".
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from chip.datasheet import GENERATOR, build_datasheet, render_html, render_markdown

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
PUB = EXAMPLES / "publication-attention"
BREC = EXAMPLES / "bounded-recommendation"

KIT_HREFS = [
    "lib/artoo-kit/tokens.css",
    "lib/artoo-kit/base.css",
    "lib/artoo-kit/article.css",
    "lib/artoo-kit/components.css",
]

MD_SECTIONS = [
    "## Ports",
    "## What's probabilistic, and why",
    "## Authority & limits — what this chip can never do",
    "## Evaluation status",
    "## Live stats",
    "## Lineage",
    "## Projection manifest",
]


def _evaluations(digest: str, profile: str, *, passes: int) -> list[dict]:
    """A synthetic append-only evaluation history: ``passes`` consecutive passes."""
    return [
        {
            "tupleKey": f"cet1-{i}",
            "tuple": {
                "implementation": digest,
                "gatewayProfile": profile,
                "servedModel": "provider/model-2026-06",
                "harness": "somm/generate_structured-v1",
            },
            "minimumsMet": True,
            "recordedAt": f"2026-07-1{i}T00:00:00Z",
        }
        for i in range(passes)
    ]


def _rollup(digest: str) -> dict:
    return {
        "chipAlias": "examples.publication-attention",
        "generatedAt": "2026-07-16T00:00:00Z",
        "triples": [
            {
                "chipAlias": "examples.publication-attention",
                "chipVersion": "0.1.0",
                "implementationDigest": digest,
                "callCount": 12,
                "byOutcome": {"quiet": 7, "finding": 4, "failed": 1, "rejected": 0},
                "totalModelCostUsd": 0.1234,
                "meanWallMs": 812.5,
                "effectsExecuted": 0,
                "lastActivity": "2026-07-15T18:00:00Z",
                "evalPassStreak": 3,
                "interventions": 2,
            }
        ],
    }


# --------------------------------------------------------------------------- #
# Build: no telemetry (manifest + fixtures only)                              #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("pkg", [PUB, BREC])
def test_build_without_telemetry_is_observe_capped(pkg: Path) -> None:
    ds = build_datasheet(pkg)
    # Identity echoes package content verbatim.
    assert ds.promise
    assert ds.alias.startswith("examples.")
    # Presence is never evidence: no eval history → observe-capped, honest.
    assert ds.eval_state == "observe-capped / not yet evaluated"
    assert ds.evaluation.is_evaluated is False
    assert ds.live_stats.present is False
    # The coverage statement names every absent input.
    for absent in ("evaluations", "lifecycle events", "live telemetry (rollup)"):
        assert absent in ds.absent_inputs
    assert absent in ds.manifest_block.confidence
    # Ports carry a real example payload pulled from a fixture.
    in_ports = [p for p in ds.ports if p.direction == "in"]
    assert in_ports and in_ports[0].example_payload is not None
    # Generator label is version-stamped.
    assert ds.manifest_block.generator == GENERATOR
    # No rollup supplied → source snapshot falls back to a chip.json content hash.
    assert ds.manifest_block.source_snapshot.startswith("sha256:")


def test_hybrid_flags_gateway_deterministic_flags_none() -> None:
    pub = build_datasheet(PUB)
    assert pub.implementation_class == "hybrid"
    assert pub.probabilistic.has_gateway is True
    assert pub.probabilistic.gateway is not None
    assert pub.probabilistic.gateway.request_schema
    # No conventional "what stayed probabilistic" heading in the README → doc gap,
    # rendered gracefully rather than fabricated.
    assert pub.probabilistic.judgment_rationale is None
    assert pub.probabilistic.residue_is_doc_gap is True

    brec = build_datasheet(BREC)
    assert brec.implementation_class == "deterministic"
    assert brec.probabilistic.has_gateway is False


def test_never_statements_from_authority_and_limits() -> None:
    pub = build_datasheet(PUB)
    joined = " ".join(pub.authority.never).lower()
    # observe-ceiling chip can never perform anything above observe.
    assert "ceiling of 'observe'" in joined
    assert "synthesize" in joined and "promote" in joined
    # evidence-only prompt-injection policy surfaces as a hard "never".
    assert "hostile input as instructions" in joined


# --------------------------------------------------------------------------- #
# Build: with telemetry                                                        #
# --------------------------------------------------------------------------- #


def test_build_with_full_telemetry() -> None:
    digest = "sha256:deadbeefcafe"
    evals = _evaluations(digest, "materiality-mid@1", passes=3)
    lifecycle = [
        {"event": "mint", "at": "2026-06-01T00:00:00Z", "operator": "op",
         "chipAlias": "examples.publication-attention", "chipVersion": "0.1.0",
         "implementationDigest": digest, "tupleKey": None, "receiptRef": None,
         "details": {"originProject": "owner:desk"}},
    ]
    ds = build_datasheet(
        PUB, evaluations=evals, lifecycle_events=lifecycle, rollup=_rollup(digest),
        current_generation="provider/model-2026-07",
    )
    assert ds.eval_state == "evaluated"
    assert ds.evaluation.is_evaluated is True
    assert ds.evaluation.streak == 3
    assert ds.live_stats.present is True
    assert ds.live_stats.call_count == 12
    assert ds.live_stats.quiet_rate == pytest.approx(7 / 12)
    assert ds.lineage.events and ds.lineage.events[0]["event"] == "mint"
    # A rollup supplied its implementation digest → that is the source snapshot.
    assert ds.manifest_block.source_snapshot == digest
    # Nothing absent → coverage statement says so.
    assert "absent: none" in ds.manifest_block.confidence


def test_drift_banner_when_authored_against_precedes_current(tmp_path: Path) -> None:
    # Copy the package and inject an authoredAgainst older than the served gen.
    import json
    import shutil

    dest = tmp_path / "pub"
    shutil.copytree(PUB, dest)
    cj = dest / "chip.json"
    data = json.loads(cj.read_text())
    data["implementation"]["authoredAgainst"] = "provider/model-2026-01"
    cj.write_text(json.dumps(data))

    ds = build_datasheet(dest, current_generation="provider/model-2026-07")
    assert ds.evaluation.drift is True
    assert "AMBER" in render_markdown(ds)
    assert "older model generation" in render_html(ds, kit_css_hrefs=KIT_HREFS)


def test_verbatim_probabilistic_residue_is_echoed(tmp_path: Path) -> None:
    import shutil

    dest = tmp_path / "pub"
    shutil.copytree(PUB, dest)
    residue = ("The materiality call needs situated judgment; no fixture falsifies it, "
               "so it stays in the gateway rather than being evicted to code.")
    readme = dest / "README.md"
    readme.write_text(readme.read_text() + f"\n\n## What stayed probabilistic\n\n{residue}\n")

    ds = build_datasheet(dest)
    assert ds.probabilistic.judgment_rationale == residue
    assert ds.probabilistic.residue_is_doc_gap is False
    assert residue in render_markdown(ds)
    assert residue in render_html(ds, kit_css_hrefs=KIT_HREFS)


# --------------------------------------------------------------------------- #
# Renderers                                                                    #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("pkg", [PUB, BREC])
def test_markdown_has_all_sections(pkg: Path) -> None:
    md = render_markdown(build_datasheet(pkg))
    for section in MD_SECTIONS:
        assert section in md, f"missing section: {section}"
    # No-telemetry fallbacks are explicit.
    assert "No telemetry yet" in md


def test_markdown_renders_telemetry_rows() -> None:
    digest = "sha256:deadbeefcafe"
    ds = build_datasheet(
        PUB, evaluations=_evaluations(digest, "materiality-mid@1", passes=2),
        rollup=_rollup(digest),
    )
    md = render_markdown(ds)
    assert "materiality-mid@1" in md  # eval tuple row
    assert "quiet rate:" in md  # live-stats row
    assert "Trailing pass streak: **2**" in md


@pytest.mark.parametrize("pkg", [PUB, BREC])
def test_html_is_self_contained(pkg: Path) -> None:
    html = render_html(build_datasheet(pkg), kit_css_hrefs=KIT_HREFS)
    # Links every supplied artoo-kit stylesheet.
    for href in KIT_HREFS:
        assert f'href="{href}"' in html
    # No external requests: every resource-loading position (href/src attributes,
    # CSS url()) is either a relative kit asset or a github link — never a remote
    # fetch. (Example-payload URLs echoed as text content are data, not requests.)
    resource_refs = re.findall(r'(?:href|src)\s*=\s*"([^"]+)"', html)
    resource_refs += re.findall(r"url\(\s*['\"]?([^)'\"]+)", html)
    for ref in resource_refs:
        if ref.startswith(("http://", "https://")):
            assert "github.com" in ref, f"external resource reference: {ref}"
        else:
            assert not ref.startswith("//"), f"protocol-relative reference: {ref}"
    # A github link IS present (the colophon), and it is the only external URL kind.
    assert "github.com/lavallee/chip" in html
    # artoo-kit class idioms are used.
    assert 'class="article"' in html
    assert "stat-row" in html or "No telemetry yet" in html
