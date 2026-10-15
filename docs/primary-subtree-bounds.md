# Exact primary-subtree bounds — design and proof (#7)

Status: implementation under local test; NOT yet benchmarked, accepted or published.

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

## Required acceptance still pending

Observed Best RED→GREEN; independent Pokédex RED→GREEN; complete exhaustive/random/adversarial/native/Python/old-binary differential outputs and counters; actual frozen Best/Pokédex and complete cold/warm measurements against 25ec081; meaningful measured improvement; full source-bound gates and CI-skip reconciliation; parent self-review and exact main/mirror/CI/Pages/live/current-main PNG/ZIP/fresh-input delivery. A local proof/test or pushed feature branch is not completion.
