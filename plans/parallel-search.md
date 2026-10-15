# Deterministic bounded parallel fused search — milestone #10

Status: contract only, based on accepted main952cfc2. No implementation or speed claim yet.
Mode: owner-authorized personal solo/direct; no agents/PRs/app/player-state/host changes.

## Scope and controls

- Parallelize only the additive protocol-2 fused Mixed/Non-OG pass. Keep protocol1 requests,
  OG, Best and Pokédex sequential. No pool/scoring/weight/summation/rounding/tie/counter change.
- Default exactly one main-thread execution lane, spawning no workers. Explicit process-local
  `STORY_NATIVE_THREADS=2` or `4` opts in; accept1/2/3/4/8 for deterministic validation, cap8.
  No automatic use of available CPUs, environment/config persistence or host tuning.
- Invalid explicit protocol2 thread setting fails visibly at the native boundary; the existing
  pair-miss adapter then retains exact original standalone native/Python fallback. Protocol1
  ignores this parallel-only setting and stays available for that fallback.

## Algorithm and proof obligations

1. Construct feasible two-index prefix tasks in original increasing-index lexicographic order.
   Use identical top-level loop limits and directed new-member conflict check. Build the prefix
   State by the same two ordered adds, including compensated quality arithmetic; carry subset
   eligibility for those two members. Each original legal five-member tuple belongs to exactly
   one task, and suffix visit order is unchanged within a task.
2. Share immutable member/ownership/overlap features through std Arc (no unsafe code/deps).
   A relaxed AtomicUsize only allocates unique task ids; each worker owns all mutable search
   state and result storage. Scope/join establish result visibility. No shared incumbent,
   synchronization inside scoring, dynamic pruning, unordered numeric reduction or float atomics.
3. Each task returns both local winners, ordinary independent/scored counts and opt-in structural
   diagnostics. No Best/Pokédex pruning is enabled in workers, so ordinary skip counters stay0.
   Reset task-local counters/incumbents between tasks; do not aggregate arbitrary worker winners
   and hope that completion order preserves first-encountered identities.
4. Collect all task results, sort by unique lexicographic task id, then reduce in that order
   with the unchanged strict comparator for each incumbent. First maximal numeric/name key
   wins exactly as sequential traversal; integer counters add exactly once per legal leaf.
   Reordered global discovery cannot affect scores because every candidate's arithmetic remains
   in original member order. The no-skip objectives' scored/skip history is incumbent-independent.
5. Default one-thread and protocol1 wire bytes stay identical to retained952cfc2. Multi-thread
   protocol2 ordinary full stdout must also be byte-identical, including both counters and
   original subset index mapping. Only opt-in stderr diagnostics may add real worker/task counts.

## RED/GREEN sequence

1. Real structural witness: `STORY_NATIVE_THREADS=2` plus --pruning-stats must report two
   actually spawned workers and nonzero prefix tasks, not a timing threshold; current kernel
   lacks those metrics (RED). Compare the complete reply to sequential before GREEN.
2. Exhaustive small/general-path and directed ownership fixtures, all-equal and duplicate-name
   first-identity ties, both compensated/simple modes and decimal boundaries; repeat20 times
   under1/2/3/4/8 and require identical ordinary bytes. Include fewer-than-five/infeasible and
   arbitrary ownership word-boundary pools, all/none/interleaved subset flags.
3. Old/malformed/failed native requests preserve original fallback and visible diagnostics.
   Result-cache identity includes executing implementation/binary; thread count changes execution
   only, not answers, so it need not fragment validated cache keys. Warm still reads fresh account
   state and makes zero native invocations. Timing must explicitly bypass result cache.
4. Retain immutable952cfc2 binary; compare3000 ordinary protocol1 byte cases and full frozen
   protocol2 replies across all supported thread counts, plus complete selector reports/Python
   cross-checks. Verify engagement and identical compiler/linker before performance measurement.

## Measurement and disposition

- Measure explicit2/4-thread opt-in against immediate predecessor's sequential fused pass,
  repeated fresh processes with alternating order; report wall, supervisor/child CPU and RSS,
  medians/ranges, cache/host assumptions and thread settings. Shared-host contention/turbo can
  raise CPU cost or diminish wall benefit; never call CPU cost a wall speedup or promise scaling.
- Require meaningful opt-in speedup; otherwise record unprofitability and seek owner disposition
  before treating the child as terminal. Default stays1 regardless of benchmark result.
- After frozen correctness, run actual all-five cold/warm workflow with explicit experimental
  after-side thread setting. Preserve raw/enriched options, full fresh status/favorites inputs,
  complete source verification, acquisition preflight, current stamps and actual five PNGs/ZIP.
- Full project/browser gates, solo scope/security review, direct primary-main integration/push,
  exact mirror/author/raw/CI/Pages/live checks, committed-main default and opted-in native smoke,
  fresh full source readback and actual media delivery precede original-issue acceptance/closure.
  Synchronize parent#4/GOAL/ledger; clean only owned merged branch/worktree; then advance#11.
