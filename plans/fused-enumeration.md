# Fused Mixed + Non-OG enumeration — milestone #9 (stage contract)

Status: implementation contract on `hermes-agent/9-fused-enumeration`. Local and release
acceptance evidence will be appended to `docs/fused-enumeration.md` and issue #9. A feature
push is not delivery.

## Scope

- Fuse the two heaviest native searches — Mixed pool and Non-OG pool — into ONE traversal of
  the unrestricted Mixed pool whenever a compatibility gate passes, retaining separate Mixed
  and Non-OG incumbents when all five selected members are in the Non-OG subset.
- Only this pair fuses. OG, Pokédex, Best, the fixed utility member, pool construction and
  order, scoring formulas/weights, rounding, counters, tie rules and the Python fallback are
  unchanged. No parallelism (#10), no prep/enrichment/render work (#11), no rewrite, no app,
  player-state or UI change.

## Invariants (must hold exactly)

1. **Full-report equality.** For both categories the adapter-level option dicts (winner
   members, objective_key inputs, synergy/core_synergy/six_synergy and detail expansions,
   viability, evolution_opportunities, new_entries, evolving, level_evolving, shared_types,
   searched_combinations, independent_combinations, native scored/primary_skips) are equal
   between fused and separate paths, and each fused output block equals the standalone run's
   full stdout fields.
2. **Encounter order preserved.** Non-OG is an order-preserving filter of the Mixed pool, so
   all-non-OG combinations are visited in the same relative lexicographic order in the fused
   traversal as in a standalone Non-OG traversal. Tie retention stays first-encountered;
   numeric ties resolve through the identical sorted name-rank comparison.
3. **Eligibility, feasibility and skip semantics identical.** Conflict exclusions depend only
   on member rows and are unchanged; the fused category must not acquire Best/Pokédex skip or
   pruning behavior; both blocks have zero primary skips.
4. **Standalone requests untouched.** Base protocol-1 requests and ordinary stdout stay
   byte-identical to the current kernel; fused is a new request shape only.
5. **Fallback exactness.** Any missing/unsupported binary, malformed reply, failed
   cross-check, or compatibility-gate failure falls back to the exact current behavior of two
   separate searches (and the existing Python reference when native is unavailable). Fallback
   never changes visible outputs and is proven by tests, not assumed.
6. **Cache identity.** Result-cache identity continues to include every ranking-affecting
   input and the executing binary's implementation identity; fusing cannot create a class of
   stale hits, and prepared-input invalidation tests keep passing.

## Design

### Wire (protocol 2 — fused requests only)

- Fused request begins with protocol token `2`, then the Mixed pool exactly as today
  (`<n> <category> <compensated> <uniform> <strength> <disjoint>`, member blocks `0..=n`,
  per-candidate extras and conflict rows), plus one Non-OG membership flag per candidate
  (whether that member belongs to the Non-OG subset). Response:
  `{"protocol":2,"mixed":{…today's fields…},"nonog":{…same shape…}}`.
- Base requests stay protocol `1` and byte-identical. An old binary rejects a fused request at
  the protocol assertion (nonzero exit, no stdout) and the adapter falls back.

### Kernel

- One `visit` over the Mixed pool. The Mixed incumbent updates exactly as today; for any
  depth-5 combination whose five indices are all flagged Non-OG, the Non-OG incumbent also
  updates using the already-computed candidate values and the identical `_`-branch comparator.
- No extra per-combo scoring: `quality`, `evolution`, `additions`, `favorites`, `core`,
  `full` and `synergy` are computed once per scored combination and reused for both incumbents.
- Names materialize only when an actual numeric tie needs name resolution (against either
  incumbent); structural diagnostics such as `name_sorts` are informational, not a parity
  surface.
- Split counters: Mixed counters stay today's values; Non-OG counters increment on
  all-non-OG arrivals (scored = independent, skips = 0), reproducing standalone counts.

### Adapter (`tools/story_native.py`, `tools/team_options.py`)

- Compatibility gate before dispatch: both pools have ≥5 members, the binary is present, the
  `uniform` flags are equal, strengths are equal when uniform, and `disjoint` flags are equal.
  Rationale: scoring switches must be interchangeable for the shared per-combo computation;
  anything else uses the original separate paths.
- Construct both prepared objects (needed for validation and fallback); attempt the fused
  call; validate response shape/protocol, indices (sorted, unique, in range, independent),
  per-block counter invariants (Non-OG independent ≤ `comb(|subset|, 5)`; scored+skips = the
  matching independent), and cheap winner cross-checks recomputed from BOTH prepared
  instances under their own index mappings. Any failure → two separate calls.
- `choose_options` keeps producing per-category result entries with identical field meanings;
  a test-only env switch forces the separate path so fused vs separate can be diffed on the
  same binary and pools.

## Correctness argument (summary)

- Feature values, conflict rows, name ranks and per-member objective values are intrinsic;
  standard members carry identical features in both pools, and the Non-OG list preserves the
  Mixed order. The all-non-OG subset of the Mixed traversal is therefore exactly the
  standalone Non-OG combination set, visited in the same relative order with the same
  feasibility filter, so winners (including ties) and counters coincide.
- Compatible scoring switches make each all-non-OG combination's computed candidate identical
  under both setups, so a single scoring serves both incumbents; the gate excludes the only
  structural divergence case, and mismatch triggers fallback.
- Edge coverage: interleaved subset membership, duplicate names, equal numeric keys,
  duplicate identical candidates, asymmetric conflict matrices, word-boundary sizes
  (64/65, 128/129), pools < 5, old-binary and malformed-reply fallbacks.

## RED/GREEN test plan (`tools/tests/test_story_fused.py` + adapter tests)

1. Witness RED: kernel/request does not yet support the fused category (explicit failing
   expectation, not an exception-tolerance).
2. Exhaustive small pools (5–9 members, interleaved subset): every combination enumerated in
   Python; both winners and both counter sets exact.
3. Randomized/adversarial: numeric ties, duplicate names, first-encountered retention,
   duplicate identical members, asymmetric conflicts, boundary pool sizes.
4. Frozen real pools: fused vs forced-separate full-report equality for both categories, plus
   Python cross-check per objective (winner core/full/synergy/quality from each prepared).
5. Fallback paths: old-binary simulation, truncated/malformed replies, gate-mismatch fixtures
   (uniform, strength, disjoint drift) — outputs equal forced-separate, no silent wrong result.
6. Counter identities and bounds for both blocks; `n < 5` pools; cache invalidation suite
   still green.

## Measurement plan

- Repeated real complete workflow, fresh processes, alternating before/after order,
  cache-primes excluded: before = current main (immediate predecessor), after = candidate.
  Report median wall/CPU per condition, per-category native child CPU, and fused child CPU
  vs the sum of the two separate child CPUs. Deltas are quoted against the immediate
  predecessor only — no double-counting of #6–#8 savings.
- Structural expectation: the standalone Non-OG traversal disappears as a separate pass
  (~7.6 s observed in the #8-era smoke). Success requires a meaningful measured end-to-end
  benefit; otherwise the change is recorded as rejected and not shipped.
- Completeness: raw and enriched reports equal, fresh Caught/Seen/favorites readback, five
  PNGs + ZIP from a committed-main run with the fused path engaged and no override.

## Delivery gates

Local full check and browser suites; direct integration on Gitea `main` (no PR); mirror
ref/author/raw-file verification; CI + Pages success on the exact SHA; live check; committed-
main default-native smoke with fresh readback and media; acceptance comment on #9 and only
then closure; parent #4 evidence update; cleanup of owned branch/worktree; GOAL then proceeds
to #10. Disclosures: shared-host samples, parent solo review (no additional agents), known
flake history.

## Non-goals

No fusion for Best/Pokédex/OG; no pool reordering; no scoring, weight or rounding changes; no
base-protocol change; no Python reference change; no threading/parallelism (#10); no
prep/enrich/render optimization (#11).
