"""Placement assessment: where on the distillation ladder a behavior belongs.

The ladder (``docs/skill-to-chip.md``) says movement between rungs should be
driven by evidence, not taste. This module is the portable half of that: it
takes an *evidence record* about an observed behavior and returns a
:class:`Placement` — a verdict, a confidence, and the rationale that produced
it, citing the measures it relied on.

It is a convention helper, not a runtime and not a scanner. It gathers nothing.
Whatever holds the evidence — a telemetry store, a static analyzer, a host's
receipt stream — builds a :class:`PlacementEvidence` and calls :func:`assess`.
That split is deliberate: the scanner is not portable, the rubric is.

Six rules survived a hand-run against 1.1M production calls across 113
workloads (``chip-internal/placement-assessment/2026-08-28-hand-run.md``), and
only those are encoded here:

1. **Admission gate first, scoring second.** Standing-vs-burst (spec §4.1) is
   decided before anything is scored, and rules out roughly a third of a real
   fleet without judgment. The gate is deliberately loose in the middle: it
   answers "is there a standing observation relationship", and abstains rather
   than guessing at the boundary.
2. **Time series, not aggregates.** Evidence is built from daily observations
   via :meth:`PlacementEvidence.from_daily`; there is deliberately no
   constructor that accepts a pre-summarized row. A 51-day aggregate hid a
   10-day incident and produced a wrong verdict during the hand-run.
3. **Never rank by cost.** The largest observed loss — 495,130 calls that
   never reached a provider — cost exactly nothing. ``cost_usd`` is carried
   for reporting and is read by no rule.
4. **Repetition routes the ladder.** Inputs that are novel every time are
   extraction, and distill toward *thin skill + CLI*; inputs that recur over a
   standing relationship are what a chip rung is for.
5. **The dominant failure motif separates the envelope from the judgment.**
   Terminal-envelope failure means an observer or a parser, not a judgment
   chip.
6. **"Undecidable" is a first-class verdict.** When the evidence cannot decide,
   the rubric says so and names what is missing, rather than guessing.

Verdicts are a closed vocabulary (:data:`VERDICTS`), like the spec's terminal
reasons: a placement report that can invent its own categories cannot be
compared across runs.

See ``docs/skill-to-chip.md`` for the ladder, spec §4.1 for the admission rule,
and ``docs/candidates.md`` for what to do with a verdict — :func:`source_limits`
builds the ``sourceLimits`` block for a commissioned candidate so the gaps
travel with the finding.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any

from chip.errors import PlacementError

# -- vocabulary -------------------------------------------------------------

#: A deterministic observer chip: standing attention, envelope-shaped failure,
#: no model judgment required to detect the condition.
OBSERVER = "observer"

#: A chip rung: recurring judgment over a standing observation relationship.
MINT = "mint"

#: Distil toward *thin skill + CLI*: novel input every time, so the work is
#: extraction or parsing rather than recurring judgment.
PARSER = "parser"

#: Fails the admission rule (spec §4.1): no standing observation relationship.
NO_STANDING = "no-standing-relationship"

#: Nothing to evict from the model — no judgment stage in the first place.
NO_JUDGMENT = "no-judgment-stage"

#: The evidence cannot decide. ``missing_evidence`` names what would.
UNDECIDABLE = "undecidable"

#: Closed vocabulary of placement verdicts.
VERDICTS: tuple[str, ...] = (
    OBSERVER,
    MINT,
    PARSER,
    NO_STANDING,
    NO_JUDGMENT,
    UNDECIDABLE,
)

#: Confidence in a verdict, most to least.
CONFIDENCES: tuple[str, ...] = ("high", "medium", "low")

#: Reasons a rung verdict cannot be fully trusted. These do not change a
#: verdict; they cap its confidence and travel into ``sourceLimits``.
GAP_OUTPUT_CONTRACT = "output contract undeclared"
GAP_CALL_SITE = "code location unresolved"
GAP_CROSS_RUN_STATE = "cross-run state unknown"
GAP_JUDGMENT_UNKNOWN = "judgment stage unknown"

# -- thresholds -------------------------------------------------------------
#
# Named and exported so a rationale can cite the number that decided it, and so
# a host can show the operator what the boundary was rather than a bare verdict.

#: At or above this share of all calls on one day, the behavior is a batch run
#: wearing a workload name, not a standing relationship.
BURST_PEAK_SHARE = 0.98

#: A standing relationship is active on nearly every day of its span...
STANDING_ACTIVITY_RATIO = 0.94

#: ...and is not dominated by any single day. This is deliberately far from
#: :data:`BURST_PEAK_SHARE`: a behavior can be genuinely standing and still
#: have an uneven day, and an early version set this at 0.15, where a peak
#: share of 0.1503 flipped a plainly-standing workload to "episodic".
CONCENTRATED_PEAK_SHARE = 0.5

#: Below this, inputs are effectively novel every time: extraction, not
#: recurring judgment.
NOVEL_REPETITION = 1.15

#: A failure population this envelope-dominated implicates the envelope, not
#: the judgment.
ENVELOPE_DOMINANT_SHARE = 0.5

#: Failure at this rate over a standing relationship is a condition worth
#: standing attention.
OBSERVER_FAILURE_RATE = 0.10

THRESHOLDS: dict[str, float] = {
    "burstPeakShare": BURST_PEAK_SHARE,
    "standingActivityRatio": STANDING_ACTIVITY_RATIO,
    "concentratedPeakShare": CONCENTRATED_PEAK_SHARE,
    "novelRepetition": NOVEL_REPETITION,
    "envelopeDominantShare": ENVELOPE_DOMINANT_SHARE,
    "observerFailureRate": OBSERVER_FAILURE_RATE,
}


# -- evidence ---------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DayObservation:
    """One day of observed activity for a behavior.

    The unit of evidence is a day, not a total: see rule 2 in the module
    docstring. ``envelope_failures`` counts the subset of ``failures`` whose
    terminal reason was the deterministic envelope (provider exhausted, empty
    response, rate limited) rather than the judgment itself.
    """

    date: str
    calls: int
    failures: int = 0
    envelope_failures: int = 0
    cost_usd: float = 0.0

    def __post_init__(self) -> None:
        if not isinstance(self.date, str) or not self.date.strip():
            raise PlacementError("day observation: 'date' must be a non-empty string")
        for name in ("calls", "failures", "envelope_failures"):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise PlacementError(
                    f"day observation {self.date}: {name!r} must be a non-negative integer"
                )
        if self.failures > self.calls:
            raise PlacementError(
                f"day observation {self.date}: 'failures' ({self.failures}) exceeds "
                f"'calls' ({self.calls})"
            )
        if self.envelope_failures > self.failures:
            raise PlacementError(
                f"day observation {self.date}: 'envelope_failures' "
                f"({self.envelope_failures}) exceeds 'failures' ({self.failures})"
            )


@dataclass(frozen=True, slots=True)
class PlacementEvidence:
    """What is known about one observed behavior.

    Build this with :meth:`from_daily`. The three tri-state fields
    (``emits_judgment``, ``has_cross_run_state``, ``declares_output_contract``)
    are ``None`` when unknown, and ``None`` is meaningful: it is what turns a
    confident verdict into :data:`UNDECIDABLE` or caps its confidence, instead
    of being silently read as ``False``.
    """

    subject: str
    calls: int
    distinct_inputs: int
    active_days: int
    span_days: int
    peak_day_calls: int
    failures: int = 0
    envelope_failures: int = 0
    dominant_motif: str = ""
    cost_usd: float = 0.0
    window: str = ""
    call_site: str = ""
    emits_judgment: bool | None = None
    has_cross_run_state: bool | None = None
    declares_output_contract: bool | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.subject, str) or not self.subject.strip():
            raise PlacementError("placement evidence: 'subject' must be a non-empty string")
        if self.calls <= 0:
            raise PlacementError(f"{self.subject}: 'calls' must be positive")
        if self.distinct_inputs <= 0:
            raise PlacementError(f"{self.subject}: 'distinct_inputs' must be positive")
        if self.distinct_inputs > self.calls:
            raise PlacementError(
                f"{self.subject}: 'distinct_inputs' ({self.distinct_inputs}) cannot exceed "
                f"'calls' ({self.calls})"
            )
        if self.span_days <= 0 or self.active_days <= 0:
            raise PlacementError(f"{self.subject}: 'active_days' and 'span_days' must be positive")
        if self.active_days > self.span_days:
            raise PlacementError(
                f"{self.subject}: 'active_days' ({self.active_days}) cannot exceed "
                f"'span_days' ({self.span_days})"
            )
        if not 0 < self.peak_day_calls <= self.calls:
            raise PlacementError(
                f"{self.subject}: 'peak_day_calls' must be in (0, {self.calls}]"
            )

    @classmethod
    def from_daily(
        cls,
        subject: str,
        days: Sequence[DayObservation],
        *,
        distinct_inputs: int,
        span_days: int | None = None,
        dominant_motif: str = "",
        call_site: str = "",
        emits_judgment: bool | None = None,
        has_cross_run_state: bool | None = None,
        declares_output_contract: bool | None = None,
    ) -> PlacementEvidence:
        """Derive evidence from a daily series.

        This is the only constructor that composes measures, and it is the
        only one a caller should reach for. ``span_days`` defaults to the
        number of observed days, which assumes the series is dense; pass it
        explicitly (calendar days between first and last observation) whenever
        the series omits quiet days, or a bursty behavior will read as
        standing.

        ``distinct_inputs`` is supplied separately because distinct input
        counts do not sum across days — the same input recurring on two days is
        one distinct input, and only the caller's store can deduplicate it.
        """
        observed = [d for d in days if d.calls > 0]
        if not observed:
            raise PlacementError(f"{subject}: needs at least one day with calls")
        total = sum(d.calls for d in observed)
        span = span_days if span_days is not None else len(observed)
        return cls(
            subject=subject,
            calls=total,
            distinct_inputs=distinct_inputs,
            active_days=len(observed),
            span_days=span,
            peak_day_calls=max(d.calls for d in observed),
            failures=sum(d.failures for d in observed),
            envelope_failures=sum(d.envelope_failures for d in observed),
            dominant_motif=dominant_motif,
            cost_usd=round(sum(d.cost_usd for d in observed), 6),
            window=f"{min(d.date for d in observed)}..{max(d.date for d in observed)}",
            call_site=call_site,
            emits_judgment=emits_judgment,
            has_cross_run_state=has_cross_run_state,
            declares_output_contract=declares_output_contract,
        )

    # -- derived measures ---------------------------------------------------

    @property
    def repetition(self) -> float:
        """Calls per distinct input. ``1.0`` means novel input every time."""
        return self.calls / self.distinct_inputs

    @property
    def activity_ratio(self) -> float:
        """Days active over days in span. Near ``1.0`` means standing."""
        return self.active_days / self.span_days

    @property
    def peak_share(self) -> float:
        """Largest single day over total calls. ``1.0`` means one batch run."""
        return self.peak_day_calls / self.calls

    @property
    def failure_rate(self) -> float:
        return self.failures / self.calls

    @property
    def envelope_share(self) -> float:
        """Share of failures attributable to the deterministic envelope."""
        if not self.failures:
            return 0.0
        return self.envelope_failures / self.failures

    def measures(self) -> dict[str, Any]:
        """The derived measures, rounded for display and for receipts."""
        return {
            "calls": self.calls,
            "distinctInputs": self.distinct_inputs,
            "repetition": round(self.repetition, 2),
            "activityRatio": round(self.activity_ratio, 3),
            "peakShare": round(self.peak_share, 3),
            "failureRate": round(self.failure_rate, 3),
            "envelopeShare": round(self.envelope_share, 3),
            "costUsd": self.cost_usd,
            "window": self.window,
        }


# -- verdict ----------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Reason:
    """One rule that fired, in a form an operator can argue with.

    ``cites`` carries the measures the rule actually read, so a verdict can be
    checked against its own evidence without re-running the assessment.
    """

    rule: str
    says: str
    cites: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"rule": self.rule, "says": self.says, "cites": dict(self.cites)}


@dataclass(frozen=True, slots=True)
class Placement:
    """A verdict about where a behavior belongs, and why."""

    subject: str
    verdict: str
    confidence: str
    rationale: tuple[Reason, ...]
    missing_evidence: tuple[str, ...] = ()
    measures: dict[str, Any] = field(default_factory=dict)

    @property
    def is_candidate(self) -> bool:
        """Whether this verdict proposes a chip at all.

        The negatives are the point, not a byproduct: on a real fleet most
        subjects are not chip-shaped, and a rubric that only emits positives
        is an advocacy tool.
        """
        return self.verdict in (OBSERVER, MINT)

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject": self.subject,
            "verdict": self.verdict,
            "confidence": self.confidence,
            "rationale": [r.to_dict() for r in self.rationale],
            "missingEvidence": list(self.missing_evidence),
            "measures": dict(self.measures),
        }

    def explain(self) -> str:
        """The verdict as prose, for a report or a terminal."""
        head = f"{self.subject}: {self.verdict} ({self.confidence} confidence)"
        lines = [head] + [f"  - {r.says}" for r in self.rationale]
        if self.missing_evidence:
            lines.append(f"  ! undetermined: {'; '.join(self.missing_evidence)}")
        return "\n".join(lines)


def _cap(confidence: str, ceiling: str) -> str:
    return max(confidence, ceiling, key=CONFIDENCES.index)


def assess(evidence: PlacementEvidence) -> Placement:
    """Decide where a behavior belongs, from its evidence record.

    Pure: no I/O, no clock, no model. The same evidence always yields the same
    verdict, which is what makes a placement report comparable across runs and
    reviewable after the fact.
    """
    if not isinstance(evidence, PlacementEvidence):
        raise PlacementError(
            f"assess() takes a PlacementEvidence, got {type(evidence).__name__}"
        )

    m = evidence.measures()
    reasons: list[Reason] = []
    gaps: list[str] = []

    if not evidence.call_site:
        gaps.append(GAP_CALL_SITE)

    def done(verdict: str, confidence: str) -> Placement:
        return Placement(
            subject=evidence.subject,
            verdict=verdict,
            confidence=confidence,
            rationale=tuple(reasons),
            missing_evidence=tuple(dict.fromkeys(gaps)),
            measures=m,
        )

    # Rule 0 — nothing to evict. Checked before anything else: a behavior with
    # no judgment stage is out of scope by construction, not by low score.
    if evidence.emits_judgment is False:
        reasons.append(
            Reason(
                "no-judgment",
                "The behavior emits no model judgment, so there is nothing to "
                "evict from the model and no rung to place it on.",
                {"emitsJudgment": False},
            )
        )
        return done(NO_JUDGMENT, "high")

    if evidence.emits_judgment is None:
        gaps.append(GAP_JUDGMENT_UNKNOWN)

    # Rule 1 — the admission gate (spec §4.1), standing-observation half.
    if evidence.peak_share >= BURST_PEAK_SHARE:
        reasons.append(
            Reason(
                "burst",
                f"{m['peakShare']:.0%} of all calls fell on a single day: this is a "
                "batch run wearing a workload name, not a standing observation "
                "relationship, so it fails the admission rule.",
                {"peakShare": m["peakShare"], "threshold": BURST_PEAK_SHARE},
            )
        )
        return done(NO_STANDING, "high")

    sparse = evidence.activity_ratio < STANDING_ACTIVITY_RATIO
    concentrated = evidence.peak_share >= CONCENTRATED_PEAK_SHARE
    if not sparse and not concentrated:
        reasons.append(
            Reason(
                "standing",
                f"Active on {m['activityRatio']:.0%} of days in {m['window']} with no "
                f"day above {m['peakShare']:.0%} of calls: a standing observation "
                "relationship, so the admission rule is satisfied.",
                {
                    "activityRatio": m["activityRatio"],
                    "peakShare": m["peakShare"],
                    "thresholds": {
                        "activityRatio": STANDING_ACTIVITY_RATIO,
                        "peakShare": CONCENTRATED_PEAK_SHARE,
                    },
                },
            )
        )
    else:
        # Episodic. The admission rule's other half is cross-run state, and
        # that is a code fact no call ledger can see. Name the measure that
        # actually failed — a verdict that cites the wrong number is worse
        # than one that cites none.
        if sparse and concentrated:
            why = (
                f"active on only {m['activityRatio']:.0%} of days, and "
                f"{m['peakShare']:.0%} of calls fell on one of them"
            )
        elif sparse:
            why = f"active on only {m['activityRatio']:.0%} of days in {m['window']}"
        else:
            why = f"{m['peakShare']:.0%} of all calls fell on a single day"
        cites = {
            "activityRatio": m["activityRatio"],
            "peakShare": m["peakShare"],
            "thresholds": {
                "activityRatio": STANDING_ACTIVITY_RATIO,
                "peakShare": CONCENTRATED_PEAK_SHARE,
            },
        }
        if evidence.has_cross_run_state is None:
            gaps.append(GAP_CROSS_RUN_STATE)
            reasons.append(
                Reason(
                    "episodic",
                    f"Episodic rather than standing — {why}. Whether it holds "
                    "cross-run state would decide admission, and that is not visible "
                    "here.",
                    cites,
                )
            )
            return done(UNDECIDABLE, "low")
        if not evidence.has_cross_run_state:
            reasons.append(
                Reason(
                    "episodic-stateless",
                    f"Episodic — {why} — and holds no cross-run state, so it satisfies "
                    "neither half of the admission rule.",
                    {**cites, "hasCrossRunState": False},
                )
            )
            return done(NO_STANDING, "high")
        reasons.append(
            Reason(
                "episodic-stateful",
                f"Episodic — {why} — but holds cross-run state, which admits it under "
                "the second half of the rule.",
                {**cites, "hasCrossRunState": True},
            )
        )

    # Rule 2 — envelope failure means an observer, not a judgment chip.
    if (
        evidence.failures
        and evidence.envelope_share >= ENVELOPE_DOMINANT_SHARE
        and evidence.failure_rate >= OBSERVER_FAILURE_RATE
    ):
        motif = f" ({evidence.dominant_motif})" if evidence.dominant_motif else ""
        reasons.append(
            Reason(
                "envelope-failure",
                f"Failing at {m['failureRate']:.0%}, and {m['envelopeShare']:.0%} of those "
                f"failures are terminal-envelope{motif} rather than judgment. Detecting "
                "this condition needs standing attention and no model, which is a "
                "deterministic observer chip.",
                {
                    "failureRate": m["failureRate"],
                    "envelopeShare": m["envelopeShare"],
                    "dominantMotif": evidence.dominant_motif,
                    "thresholds": {
                        "failureRate": OBSERVER_FAILURE_RATE,
                        "envelopeShare": ENVELOPE_DOMINANT_SHARE,
                    },
                },
            )
        )
        # An observer's promise is a count, so an undeclared output contract
        # does not weaken it the way it weakens a judgment rung.
        return done(OBSERVER, "high" if evidence.emits_judgment is not None else "medium")

    # Rules 3 and 4 — repetition routes the ladder.
    confidence = "medium"
    if evidence.declares_output_contract is not True:
        gaps.append(GAP_OUTPUT_CONTRACT)
        confidence = _cap(confidence, "low")
        reasons.append(
            Reason(
                "falsifiability-unknown",
                "No output contract is declared, so whether a fixture could falsify "
                "this behavior cannot be checked from evidence alone — the rung is a "
                "proposal, not a finding.",
                {"declaresOutputContract": evidence.declares_output_contract},
            )
        )

    if evidence.repetition < NOVEL_REPETITION:
        reasons.append(
            Reason(
                "novel-inputs",
                f"{m['repetition']} calls per distinct input: the input is effectively "
                "novel every time, so this is extraction rather than recurring "
                "judgment. It distils toward a thin skill plus a CLI, skipping the "
                "chip rungs.",
                {"repetition": m["repetition"], "threshold": NOVEL_REPETITION},
            )
        )
        return done(PARSER, confidence)

    reasons.append(
        Reason(
            "routine-judgment",
            f"{m['repetition']} calls per distinct input over a standing relationship: "
            "the same judgment recurs often enough to be worth governing, which is "
            "what a chip rung is for.",
            {"repetition": m["repetition"], "threshold": NOVEL_REPETITION},
        )
    )
    return done(MINT, confidence)


def assess_all(records: Iterable[PlacementEvidence]) -> list[Placement]:
    """Assess many subjects, most actionable first.

    Ordering puts proposals ahead of rejections and higher confidence ahead of
    lower, so a long report leads with what someone might act on without
    hiding what was ruled out.
    """
    placements = [assess(r) for r in records]
    placements.sort(
        key=lambda p: (
            VERDICTS.index(p.verdict),
            CONFIDENCES.index(p.confidence),
            -p.measures.get("calls", 0),
        )
    )
    return placements


def source_limits(
    placements: Placement | Iterable[Placement],
    *,
    expires_at: str = "",
) -> dict[str, Any]:
    """Build the ``sourceLimits`` block for a commissioned candidate.

    A placement report is exactly the "external finding system" that
    ``docs/candidates.md`` describes, so its limits belong in the candidate it
    commissions rather than in a footnote. ``coverage`` is the share of
    subjects the rubric could actually decide; ``coverageGaps`` is the union of
    what was missing.
    """
    items = [placements] if isinstance(placements, Placement) else list(placements)
    if not items:
        raise PlacementError("source_limits() needs at least one placement")
    decided = sum(1 for p in items if p.verdict != UNDECIDABLE)
    gaps: dict[str, None] = {}
    for p in items:
        for gap in p.missing_evidence:
            gaps[gap] = None
    limits: dict[str, Any] = {
        "coverage": round(decided / len(items), 3),
        "coverageGaps": sorted(gaps),
    }
    if expires_at:
        limits["expiresAt"] = expires_at
    return limits
