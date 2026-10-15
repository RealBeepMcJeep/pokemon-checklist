# Exact primary-subtree bounds — design and proof (#7)

Status: kernel, parity and repeated workflow measurements verified; release acceptance is tracked on issue #7 and is not implied by a feature-branch push.

## Preserved behavior

The original increasing-index traversal and incumbent discovery order stay intact. Only unfinished depths three/four (two/one slots remaining) may be skipped. A strict upper bound below the incumbent's primary metric proves that *every* compatible completion would have taken the existing leaf primary-skip path. Rounded equal-quality and equal-addition branches are still visited for secondary/tie comparisons. No Mixed/Non-OG/OG bounds are enabled; no objective, candidate pool, ranking input, scoring code or ordinary protocol-1 JSON field changes.

The optional `--pruning-stats` diagnostic prints subtree count, implied original leaf visits and subtree completion count to stderr only; routine adapter invocations do not use it. It proves that an observed reduction is subtree pruning rather than the pre-existing leaf-only skip.

## Exact ownership-completion counting

Transpose the input conflict rows once: incoming[i] has bit j precisely when candidate j's original conflict row rejects earlier candidate i. This preserves even non-symmetric protocol matrices, without assuming symmetry. At a skipped prefix, start with exactly the legal higher-index bit range and remove every prefix member's incoming conflicts. With one remaining slot the independent count is its popcount. With two, for each legal first bit i count legal bits j>i not in incoming[i]. This is a bijection with the original traversal's independent completions: no ordering, ownership conflict or pair is lost or duplicated. Mask the last word and handle a 64-bit shift via checked_shl; this works across arbitrary mask word boundaries. Add that exact count to independent and primary-skips, never scored. A pruned branch cannot change the incumbent, so later discovery and diagnostic counts remain the same.

## Integer bound

For Pokédex enable the bound only if every addition is in [0, floor((2^53-1)/5)]. The suffix retains the two largest distinct-position values, ignoring conflicts. Current prefix additions plus the largest one/two suffix additions is at least every achievable total; ignoring conflicts only loosens it. All five-term totals are nonnegative, fit i64 and are exactly representable as f64 under this guarded domain. Compare integers strictly with incumbent additions. Other numerical domains keep the original traversal, not a guessed bound.

## Floating-quality bound

Assumptions are the existing native IEEE-754 binary64, round-to-nearest contract, finite five quality inputs of magnitude at most 1e8, and no unsafe reassociation/fast-math. Disable the quality bound outside that input domain. Define u=2^-53, epsilon=2u and eta=2^-1075. Each primitive rounded operation has absolute error at most u times the magnitude of its exact result plus eta. Let S=max(1, sum of absolute input values) for any hypothetical completion.

For at most five terms, the ordinary high accumulator obeys |hi|,|t|<2S: (1+u)^5*S plus the five underflow contributions is below 2S. For each compensated update, write t=fl(hi+x), d=fl(hi-t) and e=fl(d+x); the symmetric branch exchanges hi and x; its condition implies |hi|<|x|<=S, so the same bounds hold. Thus |d|<5S, |e|<7S. Five rounded low-accumulator additions give |lo|<36S. These loose magnitude inequalities hold even under severe cancellation because S uses absolute inputs, not the small result.

Writing the rounding errors of d,e,lo-update as delta2,delta3,delta4, respectively, their magnitudes are bounded by (4uS+eta), (6uS+eta), (43uS+eta). Algebraically hi'+lo' = hi+lo+x+delta2+delta3+delta4: the t addition error cancels, WITHOUT assuming the correction is exact. Across five terms these contribute at most 265uS+15eta. The final value() addition contributes at most 38uS+eta, hence total absolute error <=303uS+16eta <256*epsilon*S for S>=1. The simple accumulator has the smaller bound 10uS+5eta, so the same envelope covers both supported summation modes. The numerical constants/intermediate inequalities were also checked using exact Python Fractions, not a floating sampler.

The implementation upward-rounds each addition of the actual prefix qualities and the largest one/two distinct suffix qualities. This gives U at least the exact real sum of every completion, regardless of hypothetical completion order. Separately it upward-rounds prefix absolute values plus the suffix maximum absolute value repeated for each remaining slot and clamps to one, producing M>=S. E=next_up(256*epsilon*M) is at least the proven error envelope; 256*epsilon is an exactly represented power of two. Upward-rounding U+E gives an upper bound on the *returned floating Sum.value()* of every completion, not merely the ideal real sum. Division by positive five is monotonic; another next_up is conservative. Apply the unchanged monotonic round4 routine and prune only if that rounded upper mean is strictly below incumbent rounded quality. Non-finite bounds fail open. Near-half rounding, negative zero, subnormals and cancellation may weaken pruning, never justify changing scores or pruning equal-primary ties.

## Verified evaluation

- Observed Best RED→GREEN, then independent Pokédex RED→GREEN. The 52-test focused story/native/cache/card suite passed, including four new end-to-end/exhaustive/cross-word tests.
- 1,200 retained-old/new randomized/adversarial wire cases across both summation modes matched completely. A separate normal-call check verified byte-identical stdout and empty stderr for those 1,200 cases plus all five captured actual category wires (1,205 cases).
- Complete prepared five-category options equal the frozen reference. All 14 complete real refreshes (two excluded cache primes plus three before/after cold/warm trials) produced identical raw AND enriched reports. Initial Caught/Seen/favorites sets matched across trials; each wrapper independently reread Caught/Seen after rendering. Final personalized delivery also requires full live-source readback.
- Every timed selector made one fresh account read. All cold trials made five verified Rust searches; all warm trials made zero rank/search calls. No fake account responses, cached cards presented as fresh, changed moves/inputs or fabricated results were used.

## Repeated native process measurements

Three executions of identical captured wires per condition; process/protocol overhead included, not full refresh latency. Medians and ranges in seconds:

| Objective | Before median (range) | After median (range) |
|---|---:|---:|
| Best | 10.0217 (9.1492–27.0752) | 0.1091 (0.1000–0.3178) |
| Pokedex | 0.9033 (0.8574–2.1459) | 0.0207 (0.0184–0.0546) |

Real structural engagement (same independent/scored/primary-skip totals as the retained original):
- Best: 246,674 skipped unfinished subtrees; 225 actually visited leaves versus 166,562,791 independent completions. Of those completions, 2 receive detailed scores and 166,562,789 remain counted primary skips.
- Pokedex: 67,947 skipped unfinished subtrees; 6,479 actually visited leaves versus 18,086,976 independent completions. Of those completions, 419 receive detailed scores and 18,086,557 remain counted primary skips.

## Complete five-card workflow measurements

Fresh-process, unprofiled supervisor/account reads, verified preparation, all five selections, acquisition preflight/enrichment, five PNGs, ZIP and final Caught/Seen readback. Cold means selection-result-cache bypass, NOT OS-cache flushing. A separate cache-enabled prime is excluded for each code/binary version. Three trials per table cell with alternating before/after order; no other heavy task was launched by this operator during timed trials.

| Condition | Before median (range), seconds | After median (range), seconds | Median CPU seconds before→after |
|---|---:|---:|---:|
| cold | 93.51 (62.60–112.93) | 60.72 (48.44–65.60) | 73.96→54.78 |
| warm | 12.68 (11.54–34.66) | 11.54 (11.32–20.96) | 12.16→11.37 |

Observed cold median reduction: **35.1% wall / 25.9% supervisor-plus-reaped-child CPU**. These are small-sample, shared-host observations, NOT statistical guarantees. Ranges are large and overlap. Warm performs no search, so its variation is not a branch-pruning speedup. Changes in timings of non-pruned categories/preparation must not all be attributed to the new bounds; no scoring/fusion/parallel/rendering optimization is claimed by this milestone. Do not combine these percentages with earlier parser-index measurements taken under different host conditions.

Maximum observed Linux KiB RSS below is per supervisor/largest child, NOT summed process-tree peak:

| Condition | Supervisor RSS before→after | Largest child RSS before→after |
|---|---:|---:|
| cold | 85256→84348 | 107296→107604 |
| warm | 83932→84572 | 107452→107668 |

Per-objective cold-trial native CPU medians (separate child accounting, not wall time):

| Objective | Before CPU seconds | After CPU seconds |
|---|---:|---:|
| OG | 0.0027 | 0.0028 |
| Non-OG | 10.5953 | 9.7915 |
| Mixed | 40.1808 | 31.5989 |
| Pokedex | 0.9984 | 0.0296 |
| Best | 7.6198 | 0.1468 |

## Identity, limitations and release acceptance

- Immediate predecessor: `25ec0819d21da8083a0b637be13ebaa6598804a9`; measured candidate: `7c45f676e1eb79968a03a4fba7e62308072337a7`, both clean at measurement start. Public report/doc follow-ups do not change measured Rust/Python source.
- Both retained ELF comment sections identify the same Rust 1.98.0 compiler (`88d9e12ae`), LLD 22.1.8 and GCC 14.2.0; portable x86-64 build helper, Python 3.12.13, Linux x86-64, eight logical CPUs. Shared host scheduling/frequency and OS caches were not controlled.
- Before native SHA-256: `5ef89dcd30e7dd6f919dfed41b00c6b44eb9521bd445011131f7a3ccbba112e5`. After: `41353cc01fe5c914afbaec8288f1912a77b39587cf2b9b4e202cf5b1db9ca2ea`. Personal frozen inputs/images and detailed measurements remain private, not public fixtures.
- This is kernel-internal acceleration only. Native/Python fallback, cache key/invalidation, live reads and all five report semantics remain unchanged. Later #8–#11 are separate work.
- The initial full project check hit two 5-second timeouts in unchanged tab-lock Vitest tests. Source/config/lockfile and Vitest/Vite versions match pristine main; the full 21-test tab file then passed on both main and candidate without changing code, test timeouts or configuration. Cause is not proven; do not call the initial gate first-pass clean. The unchanged-source full rerun passed 203 Vitest, 281 Python (no skips), 13 Node and 214 browser tests, with no browser flaky/retry-only summary. Parent solo scope/security review passed; Clippy was not installed (no toolchain changes made). Exact mirrors/CI/Pages/live/current-main execution/readback/delivery must also pass before #7 closes. Final release evidence is tracked on #7, not inferred from a feature push.
