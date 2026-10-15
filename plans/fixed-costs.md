# Fixed-cost five-team pipeline — milestone #11

Status: picked up from accepted main db7e097; re-profile BEFORE production changes.
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
