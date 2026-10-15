# Native ranking fast path — milestone #8

Status: retained implementation and repeated measurements verified locally; exact release acceptance is tracked on issue #8. A feature push is not delivery.

## Scope and correctness

The retained change is **lazy name materialization only**. Numeric priority fields are compared in their original order with the original floating/integer comparisons. A strictly numerically inferior candidate cannot win through the final name tie-break, so its five names need not be copied/sorted. An initial incumbent, numeric improvement or exact numeric tie still materializes the original sorted name ranks and uses the original strict comparator. Equal numeric/name keys retain the first encountered identity.

All original detailed scores are computed and all independent/scored/primary-skip counters are updated before the new numeric-loser return. Thus this does not redefine scored candidates or pretend they became primary skips. Compensated/simple sums, decimal round4, generic weighted/non-disjoint scoring, guarded Best/Pokédex bounds, pools, fixed Butterfree, priority weights, ownership and Python fallback are unchanged. No app, player state, source data, shared enumeration or parallelism change is included.

`--pruning-stats` additionally exposes the real `name_sorts` count on stderr; normal stdout bytes and empty stderr remain unchanged. Witness RED: 792 sorts where only the initial incumbent required one. GREEN: one sort with identical ordinary results/counters. Frozen Non-OG/Mixed requests sort names only 20/23 times instead of 54,639,948/166,562,791 scored candidates. These are observed structural counts, not runtime guarantees.

## Production-branch profiling and individually evaluated candidates

Actual captured flags were uniform/disjoint, with conservative equal-strength STAB features; an unused weighted-vector-loop optimization was not presented as a production gain. Native perf/Valgrind/GDB were unavailable; no host tools or kernel policies were changed. A private sampled timing build of the exact accepted source retained byte-identical ordinary output in both heavy categories. Clock overhead and changed instrumented layout limit phase attribution, so those timings are diagnostic only; speed measurements use the retained uninstrumented binaries.

1. **Lazy names: retained.** 3,000 adversarial ordinary-output byte cases across both sum modes/all categories plus complete actual prepared options matched. Three native process executions per condition (startup/protocol overhead included):

| Objective | Before median (range), seconds | Lazy median (range), seconds |
|---|---:|---:|
| Non-OG | 8.8224 (8.5379–9.0494) | 7.9422 (7.9382–8.0374) |
| Mixed | 28.1649 (26.9172–31.6047) | 26.4181 (25.0667–26.4283) |

2. **Category enum: rejected.** It passed 3,000 byte cases and prepared-option parity, but five-round alternating CPU measurements versus lazy names showed only 0.76%/0.24% median deltas with overlapping ranges. Keeping it as mere cleanup would violate the measured-benefit bar; it was removed.
3. **Permitted masks: rejected.** Five-round CPU comparison against the enum predecessor regressed Non-OG 0.88% and Mixed 2.30%. Small/captured-pool parity passed, but a supported 257-candidate infeasible-pool regression exposed initialization indexing word four of a four-word array even when the fast-path traversal guard was false. The experiment was rejected on the feature branch before release integration; no released default-main artifact uses it. The new regression observed the panic (RED) and passed (GREEN) after forward restoration of the verified lazy source. The regression remains; the masks and enum-only diagnostics/tests were removed, without rewriting branch history. Neither rejected experiment is counted as shipped work.

## Complete workflow measurements

Two excluded cache primes, then three fresh-process before/after cold/warm trials with alternating order. Real account reads, verified data/preparation, all five selections, acquisition checks/enrichment, five PNGs, ZIP and final live Caught/Seen readback are included. Cold bypasses the selection-result cache, not OS caches. No other heavy task was launched by this operator during timing; heavy gates followed timing.

| Condition | Before median (range), seconds | After median (range), seconds | Median CPU before→after, seconds |
|---|---:|---:|---:|
| cold | 44.45 (44.44–44.54) | 41.97 (41.70–42.07) | 44.14→41.72 |
| warm | 9.98 (9.82–10.02) | 9.68 (9.64–10.02) | 9.77→9.53 |

Observed cold median reduction: **5.6% wall / 5.5% CPU** (supervisor plus reaped descendants). Only three samples per condition on a shared host: not a statistical guarantee or a future-runtime promise. Warm makes zero searches, so its variation is not credited to lazy names. Do not combine these percentages with earlier milestones measured under other host conditions.

One additional attempt failed during final account readback because token exchange returned `internal_failure`. Its actual raw/rendered output and failure diagnostics were retained, marked FAILED and excluded from summaries. A separate real read recovered with unchanged complete Caught/Seen/favorites. A resume harness verified all 11 earlier successful outputs/input sets, reran the failed cold trial completely in a new directory and completed the two remaining warm trials. These are **14 successful complete workflows plus one disclosed failed/excluded attempt**, not a clean first-attempt batch and not a fabricated/stale readback. No credentials/auth/host settings changed.

All 14 successful raw AND enriched reports matched the reference. Every timed selector performed a fresh account read; cold used five Rust searches, warm zero. Initial full Caught/Seen/favorites sets matched across trials, and each accepted wrapper independently reread Caught/Seen after rendering; final delivery additionally requires full current source-set readback.

Linux KiB RSS is maximum per supervisor/largest child, not summed process-tree peak:

| Condition | Supervisor RSS before→after | Largest child RSS before→after |
|---|---:|---:|
| cold | 84732→85628 | 107804→107664 |
| warm | 84656→85684 | 107856→107692 |

## Identity and remaining release gates

- Immediate predecessor: `c2c3779f6aa94c5e92a7fb869c9fa0487b13e995`; measured retained candidate: `4b39437da52f33bea0e72e6ca0efab95a10ebbb0`, clean at start. Retained Rust is byte-identical to the earlier measured lazy checkpoint `e143196`; no enum/mask code remains.
- Before native SHA-256: `41353cc01fe5c914afbaec8288f1912a77b39587cf2b9b4e202cf5b1db9ca2ea`; retained after: `797ccde7c70484dca905947e17bdec1d471b1889b983dadb345e72c441b3cb7a`. Both ELF comments confirm Rust 1.98.0 / LLD 22.1.8, portable x86-64; Python 3.12.13, Linux x86-64, eight logical CPUs. CPU scheduling/frequency and OS caches are not controlled.
- Personal captured inputs, reports/images and detailed measurements remain private, never public fixtures. Reusable source/tests/docs only are committed.
- Retained focused suite: 54 tests passed, including ordinary-output/engagement, exhaustive/reference/general-path, cache/card and the large infeasible-pool regression. Full gates: **203 Vitest, 283 Python (zero skips), 13 Node and 214 Playwright browser tests**, all passed on the retained source. Parent solo scope/security review passed (no independent review or extra agents). App HTML bytes match the predecessor. Exact mirror/author/raw/CI/Pages/live/current-main native smoke and actual fresh-source media delivery remain required before #8 closes; see the issue acceptance comment rather than inferring delivery from intermediate feature commits.
