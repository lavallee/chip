<!-- Moved out of spec/chip-spec.md in spec 0.6. The specification is normative
     material only: what a host must implement to interoperate. -->

# Reference circuits

Two worked circuit shapes. Illustrative; the normative material they draw on lives in the spec's circuit, envelope, and authority sections.

### 20.1 Publication attention circuit

```text
source adapter
  -> publication-attention chip
       [lineage/cursor -> original-artifact validation -> Somm materiality]
  -> bounded-recommendation chip
  -> owning-system idea adapter
```

Required behavior:

- no new artifact produces a quiet receipt;
- discovery mentions lead to original artifacts before evidence claims;
- duplicate lineage does not masquerade as corroboration;
- low-confidence materiality may abstain or request input;
- the originating research service emits an evidence-linked, rate-limited
  recommendation and does not commission work; and
- later outcomes calibrate the materiality and source policy.

### 20.2 PR sign-off circuit

```text
owning-system immutable PR snapshot signal
  -> PR-evidence chip
  -> independent-signoff chip [Somm rubric inside policy envelope]
  -> freshness-and-decision chip
  -> owning-system decision-card adapter
```

The sign-off output is one of:

- `ready`: required proof present and no unresolved blocking concern;
- `concerns`: exact findings and affected evidence;
- `abstain`: the model or policy cannot justify a verdict;
- `stale`: head, checks, review, or evidence changed after assessment;
- `conflict`: independent reviewers or policies disagree materially; or
- `needs_input`: a named human decision is required.

The circuit MUST bind immutable base/head SHAs, reviewer independence, rubric,
model/harness, prompt/skill/chip versions, tests, artifacts, review-thread state,
cost, freshness, and disposition. `ready` does not itself authorize merge.
