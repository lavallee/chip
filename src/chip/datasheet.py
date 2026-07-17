"""Chip datasheet — a derived, never-authored comprehension surface (one-pager).

A datasheet is the human-legible **projection** of a chip package: enough to
decide *should I wire this in, and do I trust it here?* without reading the
manifest or the implementation. It is regenerated from canonical sources — the
manifest, the fixtures, and host-supplied telemetry — so it cannot drift; if a
source moves, the projection's declared expiry fires and it is rebuilt.

The generator is a **pure function**: :func:`build_datasheet` reads a chip
package from disk (via :func:`chip.load_chip_package` and
:func:`chip.load_fixtures`) and accepts all host telemetry as plain
dicts/lists — evaluation history, lifecycle events, and a receipt rollup. It
imports no host package and performs no I/O beyond reading the package
directory, so it runs identically on any host or none.

Two renderers consume the same generated model: :func:`render_markdown`
(tight, terminal-friendly) and :func:`render_html` (a self-contained page that
styles itself only with ``artoo-kit`` tokens/classes and makes no external
request).

Discipline this module enforces (comprehension-surfaces design §3, §5):

* **presence is never evidence** — a long eval streak, a high call count, or a
  full fixture set never reads as correctness. Correctness is carried by the
  held-out eval status and the ``authoredAgainst`` drift flag; unknowns stay
  explicit ("not yet evaluated", "no telemetry yet") rather than being
  backfilled.
* **no projection without a manifest and an expiry** — every datasheet carries a
  projection-manifest block naming its source snapshot, generator, scope, a
  coverage/freshness confidence statement, and the change that invalidates it.
* the datasheet **echoes package content verbatim** (title, promise, the
  probabilistic-residue note from the README); this module's own code and
  docstrings stay generic.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from chip.authority import EffectClass
from chip.errors import FixtureError
from chip.fixtures import Fixture, load_fixtures
from chip.manifest import ChipManifest, load_chip_package
from chip.version import VERSION

GENERATOR = f"chip.datasheet/{VERSION}"

# Headings in a package README under which an author records the
# falsifiability-triage residue — why a behavior stayed a probabilistic
# (gateway) judgment rather than being evicted to deterministic code. Matched
# case-insensitively as a conventional marker; absence is rendered gracefully.
_PROBABILISTIC_HEADING_RE = re.compile(
    r"^(#{1,6})\s+(.*(?:stayed\s+probabilistic|what'?s\s+probabilistic|"
    r"probabilistic\s+residue|why\s+the\s+gateway).*)$",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Generated model
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PortView:
    direction: str  # "in" | "out"
    name: str
    schema: str
    delivery: str | None
    example_payload: Any | None  # a real fixture payload, or None


@dataclass(frozen=True, slots=True)
class StageView:
    id: str
    kind: str
    determinism: str
    request_schema: str | None = None
    result_schema: str | None = None
    profile: str | None = None


@dataclass(frozen=True, slots=True)
class ProbabilisticView:
    stages: tuple[StageView, ...]
    has_gateway: bool
    gateway: StageView | None
    # Verbatim README residue note, if the package records one; else None and
    # ``residue_is_doc_gap`` is True (the honest minimum: gateway presence only).
    judgment_rationale: str | None
    residue_is_doc_gap: bool


@dataclass(frozen=True, slots=True)
class AuthorityView:
    ceiling: str
    prohibited: tuple[str, ...]
    effects: tuple[dict[str, Any], ...]
    limits: dict[str, Any]
    input_trust: str
    prompt_injection_policy: str
    never: tuple[str, ...]  # "this chip can never: ..." statements


@dataclass(frozen=True, slots=True)
class EvaluationView:
    # Latest evaluated tuple per gateway profile (most recent event wins).
    latest_by_profile: tuple[dict[str, Any], ...]
    is_evaluated: bool  # any latest tuple passed its held-out suite
    streak: int  # trailing consecutive passes
    authored_against: str | None
    current_generation: str | None
    drift: bool  # authored_against precedes the current served generation
    declared_results: tuple[dict[str, Any], ...]  # manifest evaluation.results


@dataclass(frozen=True, slots=True)
class LiveStatsView:
    present: bool
    call_count: int = 0
    quiet: int = 0
    findings: int = 0
    failed: int = 0
    rejected: int = 0
    quiet_rate: float | None = None
    total_model_cost_usd: float = 0.0
    mean_wall_ms: float = 0.0
    effects_executed: int = 0
    interventions: int = 0
    last_activity: str | None = None


@dataclass(frozen=True, slots=True)
class LineageView:
    version: str
    events: tuple[dict[str, Any], ...]


@dataclass(frozen=True, slots=True)
class ProjectionManifest:
    kind: str
    audience: str
    source_snapshot: str
    generator: str
    scope: tuple[str, ...]
    confidence: str  # coverage×freshness statement — NOT a correctness probability
    expires_on: str
    invalidated_by: str


@dataclass(frozen=True, slots=True)
class Datasheet:
    """The generated, render-agnostic datasheet model for one chip."""

    # Identity & promise
    title: str
    alias: str
    version: str
    implementation_class: str
    promise: str
    description: str
    authority_ceiling: str
    eval_state: str  # "evaluated" | "observe-capped / not yet evaluated"

    ports: tuple[PortView, ...]
    probabilistic: ProbabilisticView
    authority: AuthorityView
    evaluation: EvaluationView
    live_stats: LiveStatsView
    lineage: LineageView
    manifest_block: ProjectionManifest
    absent_inputs: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Fixture → example payload selection
# ---------------------------------------------------------------------------


def _example_input(fixtures: list[Fixture]) -> Any | None:
    for f in fixtures:
        if f.kind == "positive":
            return f.input_signal
    return fixtures[0].input_signal if fixtures else None


def _example_output(port_name: str, fixtures: list[Fixture]) -> Any | None:
    # Prefer a fixture whose asserted outcome names this output port.
    for f in fixtures:
        if f.expected.get("responseKind") == port_name:
            return f.expected
    # Otherwise the first positive fixture's asserted outcome, then any fixture.
    for f in fixtures:
        if f.kind == "positive":
            return f.expected
    return fixtures[0].expected if fixtures else None


# ---------------------------------------------------------------------------
# README residue extraction (verbatim echo)
# ---------------------------------------------------------------------------


def _extract_probabilistic_residue(package_dir: Path) -> str | None:
    """Return the verbatim README section recording the gateway judgment residue.

    Looks for a conventional heading ("## What stayed probabilistic" or similar)
    in the package ``README.md`` and returns that section's body up to the next
    heading of the same or higher level. Absent → ``None`` (rendered as a doc
    gap, never fabricated).
    """
    readme = package_dir / "README.md"
    if not readme.is_file():
        return None
    lines = readme.read_text(encoding="utf-8").splitlines()
    start = None
    level = 0
    for i, line in enumerate(lines):
        m = _PROBABILISTIC_HEADING_RE.match(line.strip())
        if m:
            start = i
            level = len(m.group(1))
            break
    if start is None:
        return None
    body: list[str] = []
    for line in lines[start + 1:]:
        h = re.match(r"^(#{1,6})\s+", line)
        if h and len(h.group(1)) <= level:
            break
        body.append(line)
    text = "\n".join(body).strip()
    return text or None


# ---------------------------------------------------------------------------
# Authority "can never" statements
# ---------------------------------------------------------------------------


def _never_statements(manifest: ChipManifest) -> tuple[str, ...]:
    auth = manifest.authority
    limits = manifest.limits
    sec = manifest.security
    out: list[str] = []
    ceiling = auth.maximum_effect_class
    out.append(f"escalate past its authority ceiling of '{ceiling.label}'")
    # Every effect class strictly above the ceiling is forbidden by construction.
    above = [ec.label for ec in EffectClass if ec > ceiling]
    for label in sorted(set(auth.prohibited) | set(above)):
        try:
            cls = EffectClass.parse(label)
        except Exception:
            out.append(f"perform a '{label}' effect (prohibited)")
            continue
        if cls > ceiling or label in auth.prohibited:
            out.append(f"perform a '{cls.label}'-class effect")
    if limits.max_activations_per_hour is not None:
        out.append(f"run more than {limits.max_activations_per_hour} activation(s) per hour")
    if limits.max_effects_per_day is not None:
        out.append(f"execute more than {limits.max_effects_per_day} effect(s) per day")
    if limits.model_budget_usd is not None:
        out.append(f"spend more than ${limits.model_budget_usd} of model budget per run")
    if sec.prompt_injection_policy == "evidence-only":
        out.append("treat hostile input as instructions (prompt-injection policy: evidence-only)")
    # De-duplicate preserving order.
    seen: set[str] = set()
    deduped: list[str] = []
    for s in out:
        if s not in seen:
            seen.add(s)
            deduped.append(s)
    return tuple(deduped)


# ---------------------------------------------------------------------------
# Telemetry joins (all inputs are plain dicts/lists — no host imports)
# ---------------------------------------------------------------------------


def _latest_evaluations_by_profile(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Latest evaluation event per gateway profile, most-recent wins.

    ``events`` is the append-only evaluation history (oldest first), each item a
    plain dict with a ``tuple`` ({implementation, gatewayProfile, servedModel,
    harness}), ``minimumsMet``, and ``recordedAt``.
    """
    by_profile: dict[str, dict[str, Any]] = {}
    for ev in events:
        tup = ev.get("tuple") or {}
        profile = tup.get("gatewayProfile", "")
        prev = by_profile.get(profile)
        if prev is None or ev.get("recordedAt", "") >= prev.get("recordedAt", ""):
            by_profile[profile] = ev
    out = []
    for profile in sorted(by_profile):
        ev = by_profile[profile]
        tup = ev.get("tuple") or {}
        out.append({
            "gatewayProfile": tup.get("gatewayProfile", ""),
            "implementation": tup.get("implementation", ""),
            "servedModel": tup.get("servedModel", ""),
            "harness": tup.get("harness", ""),
            "minimumsMet": bool(ev.get("minimumsMet", False)),
            "recordedAt": ev.get("recordedAt"),
        })
    return out


def _trailing_streak(events: list[dict[str, Any]]) -> int:
    streak = 0
    for ev in reversed(events):
        if ev.get("minimumsMet"):
            streak += 1
        else:
            break
    return streak


def _rollup_triple(rollup: dict[str, Any] | None, digest: str | None) -> dict[str, Any] | None:
    """Normalize a rollup input to a single triple agg dict, or None.

    Accepts either a single agg (has ``callCount``) or a per-alias library doc
    (has ``triples``); for a doc, prefers the triple matching ``digest``.
    """
    if not rollup:
        return None
    if "triples" in rollup:
        triples = rollup.get("triples") or []
        if digest:
            for t in triples:
                if t.get("implementationDigest") == digest:
                    return t
        return triples[0] if triples else None
    if "callCount" in rollup:
        return rollup
    return None


def _source_snapshot(package_dir: Path, triple: dict[str, Any] | None) -> str:
    """The package digest if a rollup supplied one, else a content hash of chip.json."""
    if triple and triple.get("implementationDigest"):
        return str(triple["implementationDigest"])
    chip_json = package_dir / "chip.json"
    if chip_json.is_file():
        h = hashlib.sha256(chip_json.read_bytes()).hexdigest()
        return f"sha256:{h}"
    return "unknown"


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------


def build_datasheet(
    package_dir: str | Path,
    *,
    evaluations: list[dict[str, Any]] | None = None,
    lifecycle_events: list[dict[str, Any]] | None = None,
    rollup: dict[str, Any] | None = None,
    current_generation: str | None = None,
) -> Datasheet:
    """Generate a :class:`Datasheet` for a chip package (pure read-join).

    Reads the package (manifest + fixtures) from ``package_dir`` and joins
    host-supplied telemetry — all plain dicts/lists so the function stays free of
    host imports:

    * ``evaluations`` — append-only evaluation history (oldest first); latest
      tuple per profile and the trailing pass streak are derived from it.
    * ``lifecycle_events`` — mint/transfer/optimize/retire records for lineage.
    * ``rollup`` — a receipt rollup (a single triple agg, or a per-alias library
      doc with ``triples``) for live stats; absent → "no telemetry yet".
    * ``current_generation`` — the model generation currently served, compared
      against the manifest's ``authoredAgainst`` to raise a drift banner.

    Any telemetry that is ``None``/absent is named in the datasheet's coverage
    statement rather than implied; presence never reads as correctness.
    """
    package_dir = Path(package_dir)
    manifest, _schemas = load_chip_package(package_dir)

    try:
        fixtures = load_fixtures(package_dir / manifest.evaluation.fixtures)
    except FixtureError:
        fixtures = []

    evaluations = list(evaluations or [])
    lifecycle_events = list(lifecycle_events or [])

    # ---- ports with one example payload each ----
    ports: list[PortView] = []
    for p in manifest.contract.inputs:
        ports.append(PortView("in", p.name, p.schema, p.delivery, _example_input(fixtures)))
    for p in manifest.contract.outputs:
        ports.append(PortView("out", p.name, p.schema, None, _example_output(p.name, fixtures)))

    # ---- what's probabilistic and why ----
    stage_views = tuple(
        StageView(s.id, s.kind, s.determinism, s.request_schema, s.result_schema, s.profile)
        for s in manifest.implementation.stages
    )
    gateway = next((s for s in stage_views if s.kind == "gateway"), None)
    residue = _extract_probabilistic_residue(package_dir) if gateway is not None else None
    probabilistic = ProbabilisticView(
        stages=stage_views,
        has_gateway=gateway is not None,
        gateway=gateway,
        judgment_rationale=residue,
        residue_is_doc_gap=(gateway is not None and residue is None),
    )

    # ---- authority & limits ----
    limits = manifest.limits
    limits_dict = {
        "timeout": limits.timeout,
        "maxActivationsPerHour": limits.max_activations_per_hour,
        "maxEffectsPerDay": limits.max_effects_per_day,
        "cooldown": limits.cooldown,
        "modelBudgetUsd": limits.model_budget_usd,
    }
    authority = AuthorityView(
        ceiling=manifest.authority.maximum_effect_class.label,
        prohibited=manifest.authority.prohibited,
        effects=tuple(
            {"name": e.name, "class": e.effect_class.label, "defaultApproval": e.default_approval}
            for e in manifest.contract.effects
        ),
        limits={k: v for k, v in limits_dict.items() if v is not None},
        input_trust=manifest.security.input_trust,
        prompt_injection_policy=manifest.security.prompt_injection_policy,
        never=_never_statements(manifest),
    )

    # ---- evaluation status ----
    latest_by_profile = _latest_evaluations_by_profile(evaluations)
    is_evaluated = any(t["minimumsMet"] for t in latest_by_profile)
    streak = _trailing_streak(evaluations)
    authored = manifest.implementation.authored_against
    drift = bool(authored and current_generation and authored < current_generation)
    evaluation = EvaluationView(
        latest_by_profile=tuple(latest_by_profile),
        is_evaluated=is_evaluated,
        streak=streak,
        authored_against=authored,
        current_generation=current_generation,
        drift=drift,
        declared_results=manifest.evaluation.results,
    )

    # ---- live stats ----
    triple = _rollup_triple(rollup, None)
    if triple is not None:
        bo = triple.get("byOutcome", {})
        calls = int(triple.get("callCount", 0))
        quiet = int(bo.get("quiet", 0))
        live_stats = LiveStatsView(
            present=True,
            call_count=calls,
            quiet=quiet,
            findings=int(bo.get("finding", 0)),
            failed=int(bo.get("failed", 0)),
            rejected=int(bo.get("rejected", 0)),
            quiet_rate=(quiet / calls) if calls else None,
            total_model_cost_usd=float(triple.get("totalModelCostUsd", 0.0)),
            mean_wall_ms=float(triple.get("meanWallMs", 0.0)),
            effects_executed=int(triple.get("effectsExecuted", 0)),
            interventions=int(triple.get("interventions", 0)),
            last_activity=triple.get("lastActivity"),
        )
    else:
        live_stats = LiveStatsView(present=False)

    # ---- lineage ----
    lineage = LineageView(
        version=manifest.metadata.version,
        events=tuple(lifecycle_events),
    )

    # ---- projection manifest + coverage statement ----
    snapshot_triple = triple or _rollup_triple(rollup, None)
    source_snapshot = _source_snapshot(package_dir, snapshot_triple)
    absent: list[str] = []
    if not fixtures:
        absent.append("fixtures")
    if not evaluations:
        absent.append("evaluations")
    if not lifecycle_events:
        absent.append("lifecycle events")
    if triple is None:
        absent.append("live telemetry (rollup)")
    if current_generation is None:
        absent.append("current model generation")
    present_bits = ["manifest"]
    if fixtures:
        present_bits.append(f"fixtures({len(fixtures)})")
    if evaluations:
        present_bits.append("evaluations")
    if triple is not None:
        present_bits.append("rollup")
    confidence = (
        "coverage×freshness (never correctness). present: "
        + ", ".join(present_bits)
        + "; absent: "
        + (", ".join(absent) if absent else "none")
    )
    manifest_block = ProjectionManifest(
        kind="chip-datasheet",
        audience="engineer",
        source_snapshot=source_snapshot,
        generator=GENERATOR,
        scope=(f"{manifest.metadata.alias}@{manifest.metadata.version}",),
        confidence=confidence,
        expires_on="none",
        invalidated_by="package digest change",
    )

    eval_state = "evaluated" if is_evaluated else "observe-capped / not yet evaluated"
    return Datasheet(
        title=manifest.metadata.title,
        alias=manifest.metadata.alias,
        version=manifest.metadata.version,
        implementation_class=manifest.implementation_class,
        promise=manifest.contract.promise,
        description=manifest.metadata.description,
        authority_ceiling=manifest.authority.maximum_effect_class.label,
        eval_state=eval_state,
        ports=tuple(ports),
        probabilistic=probabilistic,
        authority=authority,
        evaluation=evaluation,
        live_stats=live_stats,
        lineage=lineage,
        manifest_block=manifest_block,
        absent_inputs=tuple(absent),
    )


# ---------------------------------------------------------------------------
# Markdown renderer (tight, terminal-friendly)
# ---------------------------------------------------------------------------


def _fmt_json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False)


def render_markdown(ds: Datasheet) -> str:
    """Render a datasheet as tight, terminal-friendly Markdown."""
    L: list[str] = []
    badge = f"[{ds.authority_ceiling}] · {ds.eval_state}"
    L.append(f"# {ds.title} — datasheet")
    L.append("")
    L.append(f"`{ds.alias}@{ds.version}` · {ds.implementation_class} · {badge}")
    L.append("")
    L.append(f"**Promise.** {ds.promise}")
    L.append("")
    L.append(ds.description)
    L.append("")

    # Ports
    L.append("## Ports")
    L.append("")
    for p in ds.ports:
        delivery = f", {p.delivery}" if p.delivery else ""
        L.append(f"- **{p.direction} · {p.name}** — `{p.schema}`{delivery}")
        if p.example_payload is not None:
            L.append("")
            L.append("  ```json")
            for line in _fmt_json(p.example_payload).splitlines():
                L.append(f"  {line}")
            L.append("  ```")
    L.append("")

    # Probabilistic
    L.append("## What's probabilistic, and why")
    L.append("")
    L.append("| stage | kind | determinism |")
    L.append("|---|---|---|")
    for s in ds.probabilistic.stages:
        L.append(f"| {s.id} | {s.kind} | {s.determinism} |")
    L.append("")
    if ds.probabilistic.has_gateway and ds.probabilistic.gateway is not None:
        g = ds.probabilistic.gateway
        L.append(
            f"The single **gateway** stage `{g.id}` is the one probabilistic step "
            f"(request `{g.request_schema}` → result `{g.result_schema}`); every other "
            "stage is deterministic."
        )
        L.append("")
        if ds.probabilistic.judgment_rationale:
            L.append("Why it stayed probabilistic (from the package README, verbatim):")
            L.append("")
            for line in ds.probabilistic.judgment_rationale.splitlines():
                L.append(f"> {line}" if line.strip() else ">")
            L.append("")
        elif ds.probabilistic.residue_is_doc_gap:
            L.append(
                "_The package does not record why this behavior stayed a gateway judgment "
                "(no 'what stayed probabilistic' section) — a doc gap; gateway presence is "
                "the honest minimum._"
            )
            L.append("")
    else:
        L.append("No gateway stage — every judgment is deterministic (`code`/`policy`/`adapter`).")
        L.append("")

    # Authority & limits
    L.append("## Authority & limits — what this chip can never do")
    L.append("")
    L.append(f"Authority ceiling: **{ds.authority.ceiling}** "
             "(lattice: observe < synthesize < experiment < draft < promote).")
    L.append("")
    L.append("This chip can never:")
    for stmt in ds.authority.never:
        L.append(f"- {stmt}")
    L.append("")
    if ds.authority.effects:
        L.append("Declared effects:")
        for e in ds.authority.effects:
            L.append(f"- `{e['name']}` — {e['class']}, approval `{e['defaultApproval']}`")
        L.append("")
    if ds.authority.limits:
        L.append("Limits: " + ", ".join(f"{k}={v}" for k, v in ds.authority.limits.items()) + ".")
        L.append("")
    L.append(f"Input trust: `{ds.authority.input_trust}` · "
             f"prompt-injection policy: `{ds.authority.prompt_injection_policy}`.")
    L.append("")

    # Evaluation status
    L.append("## Evaluation status")
    L.append("")
    if ds.evaluation.latest_by_profile:
        L.append("| gateway profile | served model | harness | held-out |")
        L.append("|---|---|---|---|")
        for t in ds.evaluation.latest_by_profile:
            state = "passed" if t["minimumsMet"] else "unevaluated"
            L.append(f"| {t['gatewayProfile'] or '—'} | {t['servedModel'] or '—'} | "
                     f"{t['harness'] or '—'} | {state} |")
        L.append("")
        L.append(f"Trailing pass streak: **{ds.evaluation.streak}**. "
                 f"Live state: **{'evaluated' if ds.evaluation.is_evaluated else 'observe-capped'}**.")
        L.append("")
    else:
        L.append("_No evaluation history supplied — treat as observe-capped / not yet evaluated._")
        L.append("")
    if ds.evaluation.authored_against:
        L.append(f"Authored against: `{ds.evaluation.authored_against}`" + (
            f"; current served generation: `{ds.evaluation.current_generation}`."
            if ds.evaluation.current_generation else "."))
        if ds.evaluation.drift:
            L.append("")
            L.append("> AMBER — authored against an older model generation than is now served. "
                     "Re-derive the judgment stage from the fixtures rather than hand-patching.")
        L.append("")

    # Live stats
    L.append("## Live stats")
    L.append("")
    st = ds.live_stats
    if st.present:
        qr = f"{st.quiet_rate:.0%}" if st.quiet_rate is not None else "n/a"
        L.append(f"- calls: {st.call_count} (quiet {st.quiet}, finding {st.findings}, "
                 f"failed {st.failed}, rejected {st.rejected})")
        L.append(f"- quiet rate: {qr} · model cost: ${st.total_model_cost_usd:.4f} · "
                 f"mean wall: {st.mean_wall_ms:.1f}ms")
        L.append(f"- effects executed: {st.effects_executed} · interventions: {st.interventions}")
        L.append(f"- last activity: {st.last_activity or '—'}")
    else:
        L.append("_No telemetry yet — this chip has no recorded activations on this host._")
    L.append("")

    # Lineage
    L.append("## Lineage")
    L.append("")
    L.append(f"Version: `{ds.version}`.")
    if ds.lineage.events:
        L.append("")
        for e in ds.lineage.events:
            det = e.get("details") or {}
            extra = ""
            if det.get("originProject"):
                extra = f" origin={det['originProject']}"
            elif det.get("toOwner"):
                extra = f" → {det['toOwner']}"
            elif det.get("reason"):
                extra = f" reason={det['reason']}"
            L.append(f"- **{e.get('event')}** at {e.get('at')} by {e.get('operator')}{extra}")
    else:
        L.append("")
        L.append("_No lifecycle events supplied._")
    L.append("")

    # Projection manifest
    m = ds.manifest_block
    L.append("## Projection manifest")
    L.append("")
    L.append("```yaml")
    L.append(f"kind: {m.kind}")
    L.append(f"audience: {m.audience}")
    L.append(f"source_snapshot: {m.source_snapshot}")
    L.append(f"generator: {m.generator}")
    L.append(f"scope: [{', '.join(m.scope)}]")
    L.append(f"confidence: {m.confidence}")
    L.append(f"expires_on: {m.expires_on}")
    L.append(f"invalidated_by: {m.invalidated_by}")
    L.append("```")
    L.append("")
    return "\n".join(L)


# ---------------------------------------------------------------------------
# HTML renderer (self-contained, artoo-kit styled)
# ---------------------------------------------------------------------------


def _esc(text: Any) -> str:
    s = str(text)
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def render_html(ds: Datasheet, *, kit_css_hrefs: list[str]) -> str:
    """Render a self-contained artoo-kit page for a datasheet.

    ``kit_css_hrefs`` are (relative, ``file://``-resolvable) hrefs to the
    ``artoo-kit`` stylesheets — the page links them and adds no other external
    reference, so it renders offline. Styling uses only artoo-kit classes
    (``.article`` grid, ``.card``/``.card-grid``, ``.stat``/``.stat-row``,
    ``.callout``, ``.badge``) plus token-referencing page-scoped CSS.
    """
    links = "\n".join(f'<link rel="stylesheet" href="{_esc(h)}">' for h in kit_css_hrefs)
    P: list[str] = []
    badge_cls = "badge--success" if ds.eval_state == "evaluated" else "badge--warn"

    P.append("<!doctype html>")
    P.append('<html lang="en">')
    P.append("<head>")
    P.append('<meta charset="utf-8">')
    P.append('<meta name="viewport" content="width=device-width, initial-scale=1">')
    P.append(f"<title>{_esc(ds.title)} — chip datasheet</title>")
    P.append(f'<meta name="description" content="{_esc(ds.promise)}">')
    P.append(links)
    P.append("<style>")
    P.append("""  .ds-badges { display: flex; gap: var(--sp-2); flex-wrap: wrap; margin: var(--sp-3) 0; }
  .ds-payload { margin: var(--sp-2) 0 0; }
  .ds-payload > summary { cursor: pointer; color: var(--text-2); font-size: var(--text-sm); }
  pre.ds-code { font-size: var(--text-sm); overflow-x: auto; background: var(--surface);
    border: 1px solid var(--border); border-radius: var(--radius); padding: var(--sp-3); }
  table.ds-table { width: 100%; border-collapse: collapse; font-size: var(--text-sm); }
  table.ds-table th, table.ds-table td { text-align: left; padding: var(--sp-2) var(--sp-3);
    border-bottom: 1px solid var(--border); }
  .ds-never { list-style: none; padding-left: 0; }
  .ds-never li::before { content: "\\2717"; color: var(--warn); font-weight: 700;
    margin-right: 0.5em; }""")
    P.append("</style>")
    P.append("</head>")
    P.append("<body>")
    P.append('<main class="article">')

    # Header
    P.append('<header class="article-header">')
    P.append(f'<div class="article-kicker">chip datasheet · {_esc(ds.implementation_class)}</div>')
    P.append(f'<h1 class="article-title">{_esc(ds.title)}</h1>')
    P.append(f'<p class="article-dek">{_esc(ds.promise)}</p>')
    P.append('<div class="ds-badges">')
    P.append(f'<span class="badge badge--accent">{_esc(ds.alias)}@{_esc(ds.version)}</span>')
    P.append(f'<span class="badge badge--accent">ceiling: {_esc(ds.authority_ceiling)}</span>')
    P.append(f'<span class="badge {badge_cls}">{_esc(ds.eval_state)}</span>')
    P.append("</div>")
    P.append(f"<p>{_esc(ds.description)}</p>")
    P.append("</header>")

    # Drift banner
    if ds.evaluation.drift:
        P.append('<div class="callout callout--warn">')
        P.append('<span class="callout-title">Authored against an older model generation</span>')
        P.append(f"Authored against <code>{_esc(ds.evaluation.authored_against)}</code>; now "
                 f"serving <code>{_esc(ds.evaluation.current_generation)}</code>. Re-derive the "
                 "judgment stage from the fixtures rather than hand-patching.")
        P.append("</div>")

    # Ports
    P.append('<h2 id="ports">Ports</h2>')
    for p in ds.ports:
        delivery = f" · {_esc(p.delivery)}" if p.delivery else ""
        P.append('<div class="card">')
        P.append(f"<h3>{_esc(p.direction)} · {_esc(p.name)}</h3>")
        P.append(f"<p><code>{_esc(p.schema)}</code>{delivery}</p>")
        if p.example_payload is not None:
            P.append('<details class="ds-payload"><summary>example payload (from a fixture)</summary>')
            P.append(f'<pre class="ds-code"><code>{_esc(_fmt_json(p.example_payload))}</code></pre>')
            P.append("</details>")
        P.append("</div>")

    # Probabilistic
    P.append('<h2 id="probabilistic">What\'s probabilistic, and why</h2>')
    P.append('<table class="ds-table"><thead><tr><th>stage</th><th>kind</th>'
             "<th>determinism</th></tr></thead><tbody>")
    for s in ds.probabilistic.stages:
        P.append(f"<tr><td>{_esc(s.id)}</td><td>{_esc(s.kind)}</td>"
                 f"<td>{_esc(s.determinism)}</td></tr>")
    P.append("</tbody></table>")
    if ds.probabilistic.has_gateway and ds.probabilistic.gateway is not None:
        g = ds.probabilistic.gateway
        P.append(f"<p>The single <strong>gateway</strong> stage <code>{_esc(g.id)}</code> is the "
                 f"one probabilistic step (request <code>{_esc(g.request_schema)}</code> → result "
                 f"<code>{_esc(g.result_schema)}</code>); every other stage is deterministic.</p>")
        if ds.probabilistic.judgment_rationale:
            P.append('<blockquote class="article-pullquote">')
            P.append(_esc(ds.probabilistic.judgment_rationale))
            P.append("<cite>package README</cite></blockquote>")
        elif ds.probabilistic.residue_is_doc_gap:
            P.append('<div class="callout callout--warn"><span class="callout-title">Doc gap'
                     "</span>The package does not record why this behavior stayed a gateway "
                     "judgment. Gateway presence is the honest minimum.</div>")
    else:
        P.append("<p>No gateway stage — every judgment is deterministic "
                 "(<code>code</code>/<code>policy</code>/<code>adapter</code>).</p>")

    # Authority
    P.append('<h2 id="authority">Authority &amp; limits — what this chip can never do</h2>')
    P.append(f"<p>Authority ceiling: <strong>{_esc(ds.authority.ceiling)}</strong> "
             "(lattice: observe &lt; synthesize &lt; experiment &lt; draft &lt; promote).</p>")
    P.append('<ul class="ds-never">')
    for stmt in ds.authority.never:
        P.append(f"<li>{_esc(stmt)}</li>")
    P.append("</ul>")
    if ds.authority.effects:
        P.append("<p>Declared effects:</p><ul>")
        for e in ds.authority.effects:
            P.append(f"<li><code>{_esc(e['name'])}</code> — {_esc(e['class'])}, approval "
                     f"<code>{_esc(e['defaultApproval'])}</code></li>")
        P.append("</ul>")
    if ds.authority.limits:
        lim = ", ".join(f"{_esc(k)}={_esc(v)}" for k, v in ds.authority.limits.items())
        P.append(f"<p>Limits: {lim}.</p>")
    P.append(f"<p>Input trust: <code>{_esc(ds.authority.input_trust)}</code> · "
             f"prompt-injection policy: <code>{_esc(ds.authority.prompt_injection_policy)}</code>.</p>")

    # Evaluation
    P.append('<h2 id="evaluation">Evaluation status</h2>')
    if ds.evaluation.latest_by_profile:
        P.append('<table class="ds-table"><thead><tr><th>gateway profile</th><th>served model</th>'
                 "<th>harness</th><th>held-out</th></tr></thead><tbody>")
        for t in ds.evaluation.latest_by_profile:
            state = "passed" if t["minimumsMet"] else "unevaluated"
            P.append(f"<tr><td>{_esc(t['gatewayProfile'] or '—')}</td>"
                     f"<td>{_esc(t['servedModel'] or '—')}</td>"
                     f"<td>{_esc(t['harness'] or '—')}</td><td>{_esc(state)}</td></tr>")
        P.append("</tbody></table>")
        P.append(f"<p>Trailing pass streak: <strong>{ds.evaluation.streak}</strong>. Live state: "
                 f"<strong>{'evaluated' if ds.evaluation.is_evaluated else 'observe-capped'}"
                 "</strong>.</p>")
    else:
        P.append("<p><em>No evaluation history supplied — treat as observe-capped / not yet "
                 "evaluated.</em></p>")

    # Live stats
    P.append('<h2 id="live-stats">Live stats</h2>')
    st = ds.live_stats
    if st.present:
        qr = f"{st.quiet_rate:.0%}" if st.quiet_rate is not None else "n/a"
        P.append('<div class="stat-row">')
        P.append(f'<div class="stat"><span class="value">{st.call_count}</span>'
                 '<span class="label">calls</span></div>')
        P.append(f'<div class="stat"><span class="value">{_esc(qr)}</span>'
                 '<span class="label">quiet rate</span></div>')
        P.append(f'<div class="stat"><span class="value">${st.total_model_cost_usd:.4f}</span>'
                 '<span class="label">model cost</span></div>')
        P.append(f'<div class="stat"><span class="value">{st.effects_executed}</span>'
                 '<span class="label">effects executed</span></div>')
        P.append(f'<div class="stat"><span class="value">{st.interventions}</span>'
                 '<span class="label">interventions</span></div>')
        P.append("</div>")
        P.append(f"<p>Findings {st.findings}, failed {st.failed}, rejected {st.rejected}. "
                 f"Last activity: {_esc(st.last_activity or '—')}.</p>")
    else:
        P.append('<div class="callout"><span class="callout-title">No telemetry yet</span>'
                 "This chip has no recorded activations on this host.</div>")

    # Lineage
    P.append('<h2 id="lineage">Lineage</h2>')
    P.append(f"<p>Version: <code>{_esc(ds.version)}</code>.</p>")
    if ds.lineage.events:
        P.append("<ul>")
        for e in ds.lineage.events:
            det = e.get("details") or {}
            extra = ""
            if det.get("originProject"):
                extra = f" origin={_esc(det['originProject'])}"
            elif det.get("toOwner"):
                extra = f" → {_esc(det['toOwner'])}"
            elif det.get("reason"):
                extra = f" reason={_esc(det['reason'])}"
            P.append(f"<li><strong>{_esc(e.get('event'))}</strong> at {_esc(e.get('at'))} "
                     f"by {_esc(e.get('operator'))}{extra}</li>")
        P.append("</ul>")
    else:
        P.append("<p><em>No lifecycle events supplied.</em></p>")

    # Projection manifest
    m = ds.manifest_block
    P.append('<h2 id="manifest">Projection manifest</h2>')
    manifest_yaml = (
        f"kind: {m.kind}\naudience: {m.audience}\nsource_snapshot: {m.source_snapshot}\n"
        f"generator: {m.generator}\nscope: [{', '.join(m.scope)}]\nconfidence: {m.confidence}\n"
        f"expires_on: {m.expires_on}\ninvalidated_by: {m.invalidated_by}"
    )
    P.append(f'<pre class="ds-code"><code>{_esc(manifest_yaml)}</code></pre>')

    P.append('<footer class="colophon">Derived, never authored. Generated by '
             f"<code>{_esc(m.generator)}</code>. Contract: "
             '<a href="https://github.com/lavallee/chip">github.com/lavallee/chip</a>.</footer>')
    P.append("</main>")
    P.append("</body>")
    P.append("</html>")
    return "\n".join(P)
