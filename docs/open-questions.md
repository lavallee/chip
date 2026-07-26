<!-- Moved out of spec/chip-spec.md in spec 0.6. The specification is normative
     material only: what a host must implement to interoperate. -->

# Open questions

Live questions this specification does not answer yet.

1. Should the skill registry expand to own chip/chipset distribution, or should
   chips use a narrower package index with an existing skill-distribution
   boundary only resolving wrappers?
2. After Fab proves the contract, what is the smallest second-host conformance
   API, and can it avoid Fab internals?
3. Should implementation artifacts target source packages, containers, WASM,
   or allow several profiles from the start?
4. `partitioned(<keyField>)` was admitted in v0.5 for delegation-profile
   map/cache chips; what operating evidence would justify `cas` on top of
   `single-flight` and `partitioned` state?
5. Is `chipset` useful vocabulary or does it encourage overly broad bundles?
6. What evidence could ever justify automatic patch adoption?
7. How should registry revocation propagate to active but offline installations?
8. How much of a review or research rubric belongs in doctrine, a wrapper, a
   policy stage, or a model-stage artifact?
9. Does “chip” remain clear in contexts already using UI chips or AI hardware?
10. What decomposition slice of the two representative skill suites (a
    browser-operations suite and an engineering-workflow suite) is small enough
    to test honestly but large enough to exercise state, model judgment,
    effects, and human gates?
