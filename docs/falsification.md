<!-- Moved out of spec/chip-spec.md in spec 0.6. The specification is normative
     material only: what a host must implement to interoperate. -->

# Falsification and kill criteria

The conditions under which this program should be narrowed or stopped. Kept public deliberately: a spec that cannot say how it would be proven wrong is advertising.

The thesis is not “typed artifacts are always better than prose.” Its durable
core may prove to be only the governance envelope—identity, state, authority,
taint, evaluation, and receipts—while capable models use ordinary tools for the
work. The program SHOULD be narrowed or stopped when:

1. after two quarters, the two pilots do not beat or match skill/manual
   baselines at comparable operator time, model cost, and outcome quality;
2. within one year, no materially different second host can implement the
   public contract without depending on Fab internals—in which case chips
   become a Fab feature or the portability claim is retired;
3. a current frontier model using raw typed tools matches a chip on held-out
   work—in which case keep only any independently valuable policy/receipt
   envelope;
4. PR or research decision time increases because operators must inspect more
   machinery rather than better evidence;
5. chip maintenance, tuple re-evaluation, and migration cost exceed the prompt
   drift or duplicated logic they replace; or
6. the implementation requires scheduling, routing, replay, or graph semantics
   broad enough to recreate n8n or Temporal.
