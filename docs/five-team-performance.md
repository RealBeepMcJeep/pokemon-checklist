# Five-team parser/index performance — milestone #6

## Scope and invariants

This milestone indexes immutable Showdown source text once per content value, retaining at most eight source indexes per process. It preserves the old first normalized-key match, duplicate/punctuation behavior, empty/missing/malformed results and content-change invalidation. It does not cache paths or integrity verdicts: existing manifest/file verification, live account reads, selection-cache identity and failure behavior remain in place.

No search/scoring/objective, candidate-pool, native protocol, source dataset, move target, rendering/compression, app or save change is included. Rust acceleration and result caching already existed. Later milestones #7–#11 are separate, not delivered by this change.

## Repeated end-to-end measurements

Three fresh-process trials per condition, plus two cache-prime runs excluded from the medians. Each trial executed the real all-five refresh: account read, preparation, selection, acquisition preflight/enrichment, five PNGs, final Caught/Seen readback, image checks and ZIP. No API replies or selection outputs were fabricated. Cold means result-cache bypass, not flushed OS file caches. Warm means validated result reuse after fresh inputs.

| Condition | Before median (range), seconds | After median (range), seconds | Median reduction |
|---|---:|---:|---:|
| Cold | 108.95 (77.81–114.75) | 71.69 (63.19–79.72) | 34.2% |
| Warm | 56.09 (47.57–62.75) | 15.37 (11.92–17.85) | 72.6% |

The host was shared and timings varied substantially; these are small-sample observations, not statistical guarantees or future-runtime promises. Compare medians/ranges, not the fastest isolated runs. Earlier exploratory unprofiled samples (92.93→56.94 s cold, 38.89→11.34 s warm) were single samples and are superseded for this report by the repeated comparison. Profiler-instrumented timings are diagnostic only.

### CPU, memory and phase observations

CPU seconds below include the supervisor and reaped descendants. RSS is the maximum observed per supervisor/largest child, in Linux KiB, NOT summed process-tree peak memory.

| Condition | Median CPU seconds before→after | Max supervisor RSS before→after (KiB) | Max child RSS before→after (KiB) |
|---|---:|---:|---:|
| cold | 99.27→65.53 | 85232→86812 | 108280→108820 |
| warm | 48.94→14.02 | 85820→86612 | 108224→108724 |

Preparation timing is the selector interval from main entry to the selection-cache boundary, including its fresh account/data/profile work; it excludes interpreter imports. Phase medians are independently calculated and must not be added as though they came from one run.

- cold: preparation median 35.16→4.51 s; selection/cache-boundary median 61.80→59.17 s.
- warm: preparation median 46.06→5.27 s; selection/cache-boundary median 0.29→0.25 s.
- Every timed selector performed one fresh account read. Every cold trial made five rank calls and verified Rust results; every warm trial made zero rank/search calls. The wrapper independently re-read Caught/Seen after rendering.
- All 14 raw selections matched the same frozen reference exactly. Earlier five-mode raw+enriched comparisons plus prepared-input/options checks also matched (12 comparisons). Source inputs, eligible pools and goals did not change.

## Environment and provenance

- Linux x86-64 / TrueNAS kernel 6.12.99, glibc 2.41; eight logical CPUs and eight affinity CPUs. Current cgroup cpu.max was `max 100000`; this does not establish physical-core count or absence of shared-host contention.
- Python 3.12.13 project environment, same Pillow/Node/source cache and the SAME retained native release binary in both halves. No network downloads or Cargo builds during measured runs.
- Published reference source: `828c7bda964fa4295d314cd1de6db0c747a9559a`. Tested index source is committed in `ff7a1f1771d6f1e4887bf30bbedbfeee26b31b48`; measurements began on its identical dirty source at spec commit `0bb3b6490dcad64ab9dbf6b0f4e43fc357a0b9a0`, not a falsely claimed clean build. Source/test hashes were matched to the frozen reviewed files before commit.
- Native executable SHA-256: `5ef89dcd30e7dd6f919dfed41b00c6b44eb9521bd445011131f7a3ccbba112e5`. Rust source and binary are unchanged by this milestone.
- Frozen inputs, personalized outputs, detailed timing records, source hashes and observer scripts are retained privately; they are deliberately not public fixtures.

## Verification and reproducible method

1. Establish a fresh main baseline and freeze the complete selector-boundary inputs/options with domain types preserved. Keep historical Showdown/Standard/chaos sources, native binary, assumptions and editorial move choices identical.
2. Profile parent orchestration and selector separately; preserve true exits, stderr, failed raw selections and diagnostics. Run repeated unprofiled trials in separate processes, alternate before/after ordering, prime each cache, and exclude primes from timing summaries.
3. Instrument existing rank/read boundaries without changing the fingerprinted selector or substituting API responses. Assert cold Rust execution and warm zero-search with a fresh read; verify full structured selections and acquisition enrichment, not merely final species or rounded totals.
4. Use the actual refresh workflow for final readback, all-five PNG/content checks and ZIP integrity. If source ownership/Seen/favorites change, regenerate recommendations and keep frozen benchmark comparisons separate.

Observed RED: two scans for two lookups where one was required. Four deterministic regressions cover reuse, duplicate normalization/first match, content changes/malformed/missing data and bounded eviction. Actual verified corpus comparison covered 3,941 normalized keys (the type-chart format has no matching blocks), plus 1,000 seeded queries against the original published parser. Local full gates passed: 203 Vitest, 277 Python, 13 Node and 214 browser tests. Cache corruption/invalidation/fallback and native/Python parity tests remain part of the full suite.

Publication/current-main/CI verification is recorded on the milestone issue after actual execution; this document does not imply that a local feature branch is already delivered.
