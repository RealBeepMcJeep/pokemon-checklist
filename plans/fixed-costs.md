# Fixed-cost five-team pipeline — milestone #11

Status: re-profiled accepted db7e097; first measured candidate is bounded PURE name memoization.
Current branch only, NOT shipped; shared chaos/MoveSources/font candidates still pending.
Owner-authorized personal solo/direct, no agents/PRs; no app/player-state/host/config changes.

## Scope and stage gates

1. Re-profile actual warm all-five pipeline after prior parser/native work: fresh account read,
   verified source admission, roster/profile construction, cached selection, move preflight,
   acquisition-aware enrichment, font/layout, PNG/contact sheet/ZIP and final source readback.
   Keep profiler wall/call counts diagnostic; later speed claims require repeated UNPROFILED runs.
2. Measure/share each tier-local parsed chaos object between Moves and Abilities consumers.
   Scope reuse to one invocation, retain original tier fallback and output semantics, no unbounded
   global/path-only JSON cache that conceals changed files.
3. Measure/reuse the SAME acquisition-checked MoveSources object across one run's preflight and
   enrichment; preserve GOALS overrides, owned→final resolution, source/Standard generation
   checks and visible exceptions. Existing constructor and default loader behavior must not be
   weakened. API remains backward-compatible for standalone/offline redraw/CLI callers.
4. Memoize immutable font resources if measured useful; keep existing font choice/fallback,
   geometry/colors/labels and image compression/format unchanged. No old stamped PNG reuse.
5. A new verified-source snapshot is OPTIONAL, not a mandatory subsystem. Add one only if the
   profile demonstrates a worthwhile further gain; consume exactly the immutable bytes hashed,
   make its scope explicit and bounded, retain default per-use validation, and test current-run
   consistency + next-run corruption/change rejection. Never add a global already-verified flag.

## Actual fresh-read warm diagnostic and first candidate

Real freshread1/warmrank0/native0, actual five-card/enriched/ZIP/readback workflow completed.
Instrumented wall19.63s, selector11.40s: 680,934 normalize_name calls/6.91s cumulative,
canonicalize_roster7.04s (overlapping inclusive times, do NOT add); four Moves parses2.03s,
four Abilities parses0.73s. Orchestrator: two MoveSources1.56s, 1,084 fonts0.159s;
PNG encoding2.33s unchanged. These are cProfile DIAGNOSTICS, not claimed unprofiled savings.
Default loader verify_cache14 total calls across two processes/0.290s cumulative; a new
source snapshot is NOT justified by this profile, so retain per-use verification unchanged.

Additional in-scope preparation candidate: share pure literal normalization (max4096 keys,
max256 characters each), convert arbitrary input objects to str on EVERY call before lookup.
No file/path/provenance/object cache, exact existing NFD/combining/lower/ASCII algorithm,
oversized keys use old fold without retention. Witness RED100 Unicode folds vs required1 →
GREEN; individual-size RED1 vs required2 folds for repeated257-char keys → GREEN. Four tests
cover mechanisms/256 boundary/entry eviction/unhashable+mutable display objects. Retained
original normalizer differential includes all project species plus10,000 random Unicode
strings and scalar/container/long cases. Complete Python302/0skip passes. First broad run
missed node_modules (two renderer failures), npm ci installed pinned lock unchanged; first
post-install full rerun exceeded180s and was NOT accepted; complete600s rerun passed. Audit
reports8 high-severity advisories on unchanged dependencies for later#1 review, not auto-fixed.

First candidate b72a7c4 RETAINED on the task branch, not shipped: all14 real default1/unset
workflows (3 cold +3 warm per side,2 excluded primes), exact prepared inputs/options/raw/enriched
reports and full live input sets equal. Median cold40.106→38.077s (5.1%less wall/4.9%less CPU),
warm12.224→9.848s (19.4%less wall/17.7%less CPU). Shared-host observations, not guarantees; SAME
native B50 executable/no overrides on both sides. Full203 Vitest/302 Python0skip/13 Node/
214 browser pass, no flaky summary. Public main stilldb7e097; timings are NOT additive to
prior milestones or evidence of a new native/default-thread speedup.

Second candidate: invocation-local combined Moves/Abilities load, no global parsed/path cache.
CLI structural RED2reads→GREEN1 of the SAME JSON content; preserve public standalone APIs,
tier fallback, normalized collisions/max-weight rules, and legacy tier=None Moves union vs
OU/fallback Abilities. Stream the union instead of retaining every large raw tier blob. Tests
cover mid-read replacement consistency/next-call corruption rejection and changed valid source,
real CLI warm re-admission/fresh read/selection-cache invalidation. Retained b72a7c4 vs new loader
outputs equal for1215 actual/all-tier/None +80random missing-source/collision/weight layouts.
An initial fixture incorrectly expected unknown tier Untiered accepted; fixed test to require
same rejection in ALL3 APIs, no production tier policy changed.

Measure this candidate against immediate predecessor b72a7c4 in a DETACHED read-only reference
worktree (concrete reason for a second owned worktree), not olddb7e097. Shared chaos/MoveSources/
font choices each follow predecessor evidence. No production edits/competing heavy work during
timings; no compression changes and no default parallelism credited here.

## Correctness boundaries

- No selector/native/pool/objective/weight/rounding/tie/counter/Python fallback changes. Default
  threads stay1; use the same thread setting on both benchmark sides. Parallel opt-in is not
  falsely counted as a new fixed-cost gain.
- Fresh full Caught/Seen/favorites reads precede validated selection-cache reuse; changes in
  sources/code/GOALS still invalidate relevant results. Never deliver partial/stale galleries
  after native, source, move-preflight or renderer failure; retain actual diagnostics.
- Reusable sources/tests/docs only in git; personal frozen inputs/reports/images stay private.
  Existing source verification/provenance and Gen VII/Prismatic assumptions remain intact.
- Exact prepared selector inputs and raw/enriched reports. Fixed-timestamp decoded pixels
  (not PNG byte identity) must match; real cards retain fresh generated timestamps. Do not
  change optimize/compress_level or add a new compression policy without owner approval.

## Test-first slices

For each retained optimization, observe a real structural RED (duplicate parse/construction/
font-load count), implement minimally, then GREEN with original result parity. Test all public
callers and existing hand-rolled fakes before widening signatures. Cover file/source mutation,
GOALS changes, corrupt/missing datasets, mid-run data consistency and new-run rejection; keep
standalone default loader validation tests green. Cache hits must not hide admission checks.
Reuse run-scoped parsed/validated objects, not global mutable dictionaries or stale image files.

## Measurement and delivery

- Retain immutable db7e097 source + native executable as baseline. Freeze actual inputs for
  differential tests; separately run actual fresh read-only account workflows.
- For each candidate compare with its immediate predecessor; retain only measured meaningful
  gains, record rejected experiments honestly. At least3 fresh-process unprofiled before/after
  cold/warm trials, alternating order, excluded primes, full report/source sets equal, warm0
  native/freshread1. Record wall/CPU/RSS and hardware/cache/thread assumptions; no competing
  heavy tasks during timing. Default1 on BOTH sides isolates fixed-cost changes.
- Full project/Python/browser gates, parent solo scope/security review (not independent), direct
  primary-main push/exact mirror/ref/author/raw checks, exact CI/Pages/live/unchanged app bytes,
  current-main real five-card/ZIP smoke and full source readback, actual media/report delivery,
  original/parent acceptance checklists, issue closure/readback and owned cleanup.
- Only then verify combined umbrella#4 acceptance (all#6–#11 outcomes + current measured pipeline
  and actual delivery), close it if fulfilled, and proceed to held-item report/cards#5 then audit#1.
