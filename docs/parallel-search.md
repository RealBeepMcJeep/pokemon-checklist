# Bounded deterministic opt-in parallel search — milestone #10

Status: local implementation and retained/native measurements verified; complete real-workflow
and exact release acceptance remain required. A feature push is not delivery.

## Default and explicit controls

**Default remains one serial lane, zero worker threads.** Only fused protocol2 opts into
`STORY_NATIVE_THREADS=2` or `4` for the launched process. Counts1/2/3/4/8 are supported for
validation; other values fail with an explicit native diagnostic, after which the existing
adapter's exact original standalone/Python fallback remains available. Protocol1 ignores the
parallel-only setting; OG, Best and Pokédex stay sequential. No host/Hermes/app configuration,
persistent environment, pool, weight, acquisition assumption or player-state change is included.

## Algorithm and deterministic identity proof

- Enumerate feasible lexicographic two-index prefix units with identical original loop bounds,
  directed new-member conflict checks and ordered State.add operations. Each legal original
  combination belongs to one unique prefix; each suffix retains original traversal order.
- Share immutable features with standard-library Arc. AtomicUsize only allocates unique prefix
  ids; each worker owns mutable counters, incumbents and output records. State is seeded using
  the same two ordered adds, including Neumaier compensation; no floating reduction is moved
  across threads. No unsafe code, new dependencies, global shared incumbent or hidden pruning.
- Reset task counters and take both winners before reusing a worker. Scope/join makes task
  results visible; completion timing does not decide the result. Collect records, sort by unique
  lexicographic task id, and fold both local winners with the unchanged STRICT comparator.
  Each task's first maximal numeric/name key and the first maximal task therefore reproduce the
  sequential first-encountered identity, including duplicate names/keys.
- Only no-skip fused objectives parallelize. All legal leaves still receive the same detailed
  scores, and both independent/scored counters add exactly once. Ordinary primary-skips stay0.
  Best/Pokédex incumbent-dependent skip history is untouched. Subset winner remapping remains
  the existing original-order mapping. Default/legacy full wire replies stay byte-identical.
- Opt-in stderr diagnostics `worker_threads`/`prefix_tasks` count real launched workers and
  feasible tasks. They are not a configured value pretending to prove execution. An infeasible
  task set spawns none. `name_sorts` may differ with task-local incumbents; this opt-in diagnostic
  is not an ordinary report field or a claimed reduction in scored candidates.

## Test-first, cache and frozen evidence

1. Current release lacked the two-worker structural metric (RED); implementation reports two
   real spawned workers/nonzero prefix tasks (GREEN), with full reply equal to sequential.
2.400 repeated ordinary-byte schedule comparisons:20 repeats per supported count across tied,
   duplicate-name, interleaved/all/empty subset and directed-conflict/rounding fixtures. Both
   default and explicit1 spawn none; even invalid parallel settings leave protocol1 serial.
3. Short/infeasible and65/129/257 ownership-word-boundary fixtures preserve replies/counters.
   Invalid-setting native diagnostics and original separate fallback are tested as real code.
4.68 full story-focused tests passed under explicit4thread operation (including generic weighted/
   non-disjoint paths and exhaustive Python comparisons); six parallel-specific tests additionally
   prove validated cached options reuse across1→4 with ZERO native invocation. Thread count does
   not affect output, so no cache fragmentation is required. Source/executing binary changes
   still invalidate keys; full workflow must retain fresh account reads before cache lookup.
5. Retained952cfc2 executable is immutable:3000 protocol1 ordinary-byte cases across all
   categories/both summation modes/adversarial domains match. Complete actual frozen selector
   options and both fused result/counter blocks match under1/2/3/4/8. Actual frozen workers0/2/3/
   4/8 observed respectively, with unchanged166,562,791 Mixed leaves and54,639,948 subset leaves.
   No result-cache hit or fabricated API response is used to prove parallel engagement.

## Native wall/CPU/RSS tradeoffs

Three fresh-process executions per configuration, alternating order. Actual uninstrumented
binaries; no --pruning-stats in timing. Inputs/full ordinary stdout are byte-identical across
all samples. Each fresh Python supervisor reaps one native executable, recording actual wall,
child CPU and Linux-reported child max RSS; RSS can include transient spawn footprint and is
NOT summed per-thread/whole-tree memory. No competing heavy job was launched by this operator.
Shared-host frequency/load are uncontrolled; three samples are observations, not statistical
confidence or future-runtime/scaling guarantees. Compiler/linker identity matches (Rust1.98.0,
LLD22.1.8), portable x86-64, same source-prepared wire.

| Execution | Wall median (range), s | CPU median (range), s | Reported child RSS median (range), KiB |
|---|---:|---:|---:|
| Retained sequential fused | 28.50 (28.41–29.03) | 28.31 (28.20–28.82) | 15008 (14972–15052) |
| New default1 | 28.78 (28.63–29.34) | 28.63 (28.51–29.21) | 15044 (15016–15200) |
| Explicit2 | 15.68 (14.88–16.45) | 31.05 (29.58–31.98) | 15028 (14832–15088) |
| Explicit4 | 9.03 (8.76–9.67) | 35.10 (34.00–36.78) | 15088 (15016–15152) |

- Default1: 0.99× wall ratio, +1.0% wall change, +1.1% CPU cost.
- Explicit2: 1.82× wall ratio, -45.0% wall change, +9.7% CPU cost.
- Explicit4: 3.16× wall ratio, -68.3% wall change, +24.0% CPU cost.

The default's small median increase has overlapping ranges: neither a meaningful regression nor
zero overhead is demonstrated. Four-thread opt-in substantially lowers measured latency at a
higher total CPU cost; keep default1 for host-sharing safety, not silent automatic4/8. These
are SEARCH-ONLY results; do not present them as complete-gallery speedups, combine percentages
with previous milestones or promise linear scaling. No memory improvement is claimed.

## Complete real five-card workflow

**Explicit comparison: retained sequential before1 vs experimental after4. Default remains1.**
Two cache primes excluded; three fresh-process before/after cold/warm samples each, alternating
order. All14 actual workflows succeeded: full raw/enriched reports and initial Caught/Seen/
favorites sets equal; final wrapper Caught/Seen readbacks passed. Cold bypasses result cache,
not OS caches. Both variants include live reads, verified sources/preparation, full selection,
move preflight/enrichment, five PNGs, ZIP and final source verification. Warm performs0 native
invocations and still reads live account state once. No competing heavy job was launched;
project/browser gates followed timing. Private source admission was clean d5b1ce2 after952cfc2.

| Condition | Before1 median (range), s | After4 median (range), s | CPU median before→after, s |
|---|---:|---:|---:|
| cold | 40.89 (40.80–41.01) | 21.40 (21.08–21.86) | 40.55→47.09 |
| warm | 11.94 (11.77–13.19) | 12.58 (11.82–13.51) | 11.84→12.53 |

Observed complete cold elapsed reduction: **47.6%**, at **16.1% MORE total CPU**.
This is a latency/CPU tradeoff under explicit4-thread opt-in, not a claim that the default got
faster or work/energy decreased. Warm's no-search ranges overlap; its variation is not credited
or attributed causally to parallelism. Three shared-host samples per condition do not prove
future runtime, statistical significance or scaling; do not combine with prior stage savings.

| Condition | Supervisor max RSS before→after, KiB | Largest child max RSS before→after, KiB |
|---|---:|---:|
| cold | 84608→85436 | 107780→107544 |
| warm | 83904→85424 | 107796→107608 |

RSS is a per-process high-water, not a summed whole-tree/thread peak. Native CPU attribution
uses actual subprocess boundaries, not per-rank deltas (the fused pass runs before those rank
callbacks). Observed pair CPU before→after: 28.63→34.64s;
this attribution is not an additional speedup to add to the whole-workflow result.

## Release acceptance still required

Full local gates passed on d5b1ce2: **203 Vitest /298 Python (zero skips)/13 Node/214 browser**.
Parent solo scope/security/ordered-reduction review passed (NOT independent; no agents/PRs).
Exact publication and committed-main default+opt-in smoke/media still remain required. Final
delivery rereads full relevant source sets and validates all actual PNGs/ZIP before closure.

Then require parent solo scope/security review (not independent), exact current main/mirror/
author/raw/CI/Pages/live verification, committed-main DEFAULT and OPT-IN actual native smoke,
full fresh status/favorites readback and actual five PNGs+ZIP delivery before #10 closes.
See the final issue acceptance rather than intermediate branch commits for release status.

Private inputs/roster reports and detailed measurements remain outside public git. Retained
native SHA256: `2ad014ffddea8d29a3daf1ef288c549fbbf5c400c62abb795ef43cfde802d920`.
Candidate native SHA256: `b50a629608d84b48daba95a695a3ebfd40a6750391e739cdab532a3d877c0695`.
