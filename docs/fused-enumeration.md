# Conditional Mixed + Non-OG shared enumeration — milestone #9

Status: implementation, frozen parity and complete-workflow measurements verified locally;
full release acceptance is tracked on issue #9. A feature push is not delivery.

## Exactness and scope

Only compatible Mixed + Non-OG searches share a traversal. OG, Pokédex and Best remain
separate; no parallelism, shortlist, objective/weight/data change, or app/player-state write.
The fixed Butterfree utility slot and full eligible pools are unchanged.

Non-OG is an order-preserving filter of Mixed. Restricting increasing-index Mixed combinations
to all-subset combinations preserves the standalone subset's lexicographic encounter order,
including first-encountered identity ties. Per-member numeric values, ownership conflicts and
scores are unchanged; both no-skip objectives have the same numeric/name comparator. Reuse a
computed candidate for two independent incumbents, sorting names whenever either incumbent
requires them. Remap the subset winner's indices to the original subset positions.

Mixed counters are unchanged. Non-OG independent/scored counters count the all-subset legal
leaves; primary skips remain zero. This reuses evaluation, not a semantic reclassification of
scored leaves. `--pruning-stats` opt-in stderr reports actual `fused_reused_scores`;
ordinary requests remain quiet and protocol-1 stdout is byte-identical.

## Versioned protocol and fallback

Protocol 1 stays supported. Additive protocol 2 carries the same Mixed features followed by
one membership flag per candidate and returns independently validated `mixed`/`nonog`
protocol-1-shaped blocks. Only Mixed requests may use protocol 2.

Gate on equal uniform/strength/disjoint switches AND exact projected weak/resist/hit/coverage/
overlap features, including utility. Matching switches alone is insufficient: a pool-specific
custom type universe can shift encoded bit positions. Require strictly increasing subset
indices, preserve original profile order, and validate each reply's indices, independence,
finite scores, counter bounds/identities and winner-only Python score/quality cross-checks
under its OWN prepared/index mapping. Reject malformed/old/unsupported replies and use the
original two native calls (or existing Python fallback), never a partial pair.

Cache identity already hashes executing sources, Rust source and the selected binary. Those
identities change here; the result-cache schema stays unchanged because all options are equal.
The force-separate test switch changes execution only, not results, and does not bypass the
normal fresh-read/cache admission contract. Runtime never downloads/builds Cargo implicitly.

## Test-first and retained-oracle evidence

1. Kernel RED: existing release rejected protocol 2; GREEN: both complete result blocks equal
   standalone runs, ordinary stderr empty.
2. Adapter RED: missing real pair entry point; GREEN: one actual native subprocess, two
   independently validated results equal standalone requests.
3. Integration RED: choose_options made zero fused requests; GREEN: one actual protocol-2
   request with complete option/report equality against forced-separate mode.
4. Unsupported metadata RED: incomplete owned vector raised IndexError; GREEN: fail open
   before projecting incomplete metadata.
5. 62 focused tests passed: 48 randomized full-report/exhaustive Python comparisons, 192
   asymmetric subset/both-summation-mode cases, duplicate names/ownership/ties, mismatch gates,
   malformed/old-binary fallbacks, infeasible/short/empty subsets and 65/129/257-member boundaries.
6. Retained predecessor vs candidate: 3,000 protocol-1 ordinary-byte cases across all categories,
   both summation modes and adversarial numeric/name/conflict domains. Complete actual prepared
   options and both full fused blocks equal the prior independent outputs, not merely winners.
7. Actual frozen selector: five native invocations become four, including one real pair. Its
   166,562,791 Mixed legal/scored leaves reuse already computed scores for 54,639,948 Non-OG
   leaves. Optional diagnostic observed `fused_reused_scores=54639948`; no second subset pass.

### Final review hardening

After timing completed, solo review observed a second unsupported-input edge: the new
pair gate could index an incomplete Mixed weak-mask vector before the original supported-
shape check returned a miss. A dedicated regression reproduced IndexError (RED); checking
both feature-vector lengths before projection made it GREEN. The original standalone
unsupported-shape fallback and the fused fallback now agree. Also corrected the internal
request helper's return annotation/docstring (it returns a binary/token tuple, not a result).
These changes do not change Rust/scoring or the native binary. The timing table below is
explicitly for clean e824906, before these constant-time admission checks; it is not a
measurement of their overhead. Final correctness/gates and committed-main smoke are required
after the hardening. No timing or failed test was silently relabeled as a final-code result.

## Real complete-workflow measurements

Two cache primes excluded, then three fresh-process cold/warm before/after trials each,
alternating order. All 14 complete workflows succeeded; all raw AND enriched reports and
complete initial Caught/Seen/favorites sets matched; wrappers independently read back Caught/
Seen after rendering. Final delivery additionally rereads full relevant source sets.
Cold bypasses result cache, not OS file caches. Warm makes zero native invocations and still
reads the account once. Both variants run actual API reads, source verification/preparation,
selection, move preflight/enrichment, five PNGs, ZIP and final state verification.

No heavy gates competed with timing; they were queued afterward. Python 3.12.13, Linux x86-64,
eight logical CPUs. Both ELF comments verify Rust 1.98.0 / LLD 22.1.8; portable CPU target.
Shared-host frequency/load/OS caches are uncontrolled. Three samples per condition are
observations, not a statistical guarantee or future-runtime promise. Compare only against
immediate predecessor 9bcc2ad; do not add earlier milestone percentages.

| Condition | Before median (range), s | After median (range), s | Median CPU before→after, s |
|---|---:|---:|---:|
| cold | 42.15 (41.91–42.20) | 35.11 (34.93–35.16) | 41.80→34.78 |
| warm | 9.84 (9.83–10.06) | 9.79 (9.54–9.81) | 9.60→9.55 |

Observed cold reductions: **16.7% wall, 16.8% CPU**. Warm variation is not credited to fusion.

### Native CPU attribution

Fusion executes before the per-category rank callbacks. Measuring only RUSAGE_CHILDREN
around those callbacks would incorrectly report zero heavy search CPU. Instead record every
actual native subprocess and compare the pair against the sum of the two previous calls.

| Executing searches | Median child CPU (range), s |
|---|---:|
| Before: Mixed + Non-OG separate | 32.03 (31.75–32.04) |
| After: single fused pass | 25.17 (25.05–25.19) |

Observed native combined CPU reduction: **21.4%**. This is separate attribution,
not an additional reduction to add to the complete-workflow percentage.

Linux RSS is per supervisor/largest child maximum, not a summed process-tree peak:

| Condition | Supervisor max RSS before→after, KiB | Largest child max RSS before→after, KiB |
|---|---:|---:|
| cold | 86124→85304 | 108036→108292 |
| warm | 85812→85284 | 108036→108044 |

## Identity and release acceptance

- Measured candidate: e824906 (clean at admission), based on main 9bcc2ad. Personal frozen inputs,
  reports/images and detailed measurements remain private, never public fixtures.
- Retained predecessor native SHA-256: `797ccde7c70484dca905947e17bdec1d471b1889b983dadb345e72c441b3cb7a`.
- Candidate native SHA-256: `2ad014ffddea8d29a3daf1ef288c549fbbf5c400c62abb795ef43cfde802d920`.
- Parent solo review only (no extra agent/PR). Full project/browser summaries and exact
  remote/CI/Pages/live/default-native paired smoke/fresh-source/media verification must be read
  and recorded before issue #9 closure. See its final acceptance comment, not intermediate
  feature commits, for release status.
