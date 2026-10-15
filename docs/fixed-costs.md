# Fixed preparation, enrichment and rendering — milestone #11

Measured code: accepted `db7e097` versus `fcf5dfb`. Default **one serial native lane** on BOTH
sides; same native binary, no binary pin/override, no compilation in timed runs. The four
changes below preserve the full eligible pools, five objectives, scores, counters, ties,
ownership/generation/acquisition assumptions, Python fallback and output. No checklist UI,
save, player-state, dependency, compression or native-search changes.

## Combined complete-workflow measurement

Three fresh-process samples per side per mode, alternating order, plus two excluded primes:
**14 successful actual workflows**, each producing five PNGs, enriched report/contact sheet/
ZIP and real account checks. No account response substitution. Times are seconds; parentheses
show observed min–max, not confidence intervals. Warm is validated result reuse after a fresh
account read; cold bypasses only the result cache, NOT OS filesystem caches.

| Mode | Before median (range) | After median (range) | Less elapsed | Median total CPU |
|---|---:|---:|---:|---:|
| cold | 39.72 (39.44–39.95) | 36.06 (35.97–36.45) | 9.2% | 39.36→35.81 (9.0% less) |
| warm | 11.49 (11.41–11.63) | 8.58 (8.37–8.61) | 25.3% | 11.46→8.41 (26.7% less) |

These are measured combined savings, **not a sum/product of stage percentages**, and not a
future-runtime guarantee. Shared Linux host, eight logical CPUs; variable native execution
and network latency remain. Same Rust executable SHA-256
`b50a629608d84b48daba95a695a3ebfd40a6750391e739cdab532a3d877c0695` on both sides.
Four actual native invocations on each cold run, including one compatible protocol-2 pair;
warm runs perform zero native/rank calls and still one fresh selector account read.

## Retained mechanisms and boundaries

1. **Pure literal normalization (`b72a7c4`).** Convert `str(value)` on EVERY call, then memoize
   exact NFD/accent-stripping/lowercase/ASCII folding of that immutable text. Max4096 entries,
   max256 characters per retained key; longer names still use the exact uncached algorithm.
   No object-identity, filesystem or verification cache. Unhashable containers and changing
   `__str__` objects retain existing behavior. Repeat-work/entry eviction/size-boundary tests
   and10,815 comparisons with the original normalizer pass.
2. **One parsed chaos blob (`87f3aaa`).** Invocation-local Moves/Abilities extraction uses the
   SAME JSON read. Standalone APIs keep per-use reads and existing tier-family/missing-file
   fallback, normalized collisions and best repeated-move weights. Preserve legacy tier=None
   Moves-union versus OU/fallback Abilities behavior. Stream the union; do not retain every
   raw tier object or create a global path/mtime JSON cache.1,215 actual/randomized retained
   comparisons cover all tier/None choices and80 randomized missing-file layouts.
3. **Explicit preflight source reuse (`2123e74`).** `add_move_targets` and Python `main` accept
   keyword-only `move_sources=`. Caller constructs/preflights one source and passes THAT object
   to enrichment. Match the requested canonical cache directory BEFORE target use; bind and
   load that directory BEFORE admission so a retargeted alias cannot mislabel its source.
   Targets/GOALS resolve again. No automatic global trusted-source flag. Current in-memory facts
   remain consistent; existing default store.get_text and a NEW constructor still reject
   post-admission corruption. Target errors propagate; no silent reconstruction/partial PNGs.
   Standalone CLI already constructs once; its count did NOT decrease. The measured orchestration
   changes from two actual successful constructions to one, witnessed in every combined run.
4. **Per-card fonts (`fcf5dfb`).** A bounded32-entry local factory lives only for one render_card.
   Five actual cards load1,084→65 fonts. Public font() still returns fresh mutable objects;
   next card reloads resources and redraws its supplied timestamp. Missing-font errors on the
   next render remain visible. No global/path font cache or old stamped image reuse. Palette,
   geometry, source atlas, PNG format and optimize=True compression policy remain unchanged.

Source snapshot caching was considered and NOT introduced: the post-native warm diagnostic
spent only0.290 cumulative seconds on14 default verification calls across the two processes.
It was not worth weakening per-use checks or adding a new source-snapshot subsystem. Reusing
an existing run-local parsed object is NOT a new promise that separate hash-then-read loader
calls are an atomic immutable-byte snapshot. Existing provenance/validation stays intact.

## Incremental results (immediate predecessor, independent batches)

| Candidate | Cold median | Warm median | Interpretation |
|---|---:|---:|---|
| Name memo |40.11→38.08|12.22→9.85|5.1%/19.4% less elapsed; exact reports|
| Shared chaos |38.12→37.43|10.00→9.00|1.8%/10.0%; exact reports|
| Explicit sources |37.36→36.86|9.48→8.74|1.3%/7.8%; actual constructors2→1|
| Scoped fonts |36.93→37.16|8.80→8.42|cold0.6% MORE elapsed/0.5% MORE CPU, warm4.3% less elapsed/3.6% less CPU|

Each row has its own three-sample real cold/warm before/after batch, two excluded primes,
complete prepared/options/raw/enriched equality and full observed live-input sets equal.
Do NOT compound rows or call their different starting points a single trend. Font cold
samples include a43.01-second after run (retained, not excluded); overlapping/wide ranges
and unchanged native timing variation do not establish a cold gain. Fonts are retained for
repeatable render/warm savings, not a claim of faster native search.

A separate UNINSTRUMENTED fresh-process five-card renderer comparison (3 samples per side)
measured median wall3.164→2.719s (14.0% less), CPU3.139→2.718s (13.4% less). Counts were
observed separately, not inside these timed samples. Same actual enriched report/atlas/fixed
stamp/Pillow/optimize=True, with no selector/account/enrichment work inside this component
boundary. Renderer peak self RSS ranged39,520–39,556KiB before versus40,532–40,600KiB after:
resource-retention tradeoff, NOT a memory improvement. Whole-workflow child high-water RSS
includes spawn transients; it is not a sum of workers or proof of energy efficiency.

## Correctness, diagnostics and actual verification

- Structural RED/GREEN for repeat normalization, oversized-key retention, real CLI JSON reads,
  actual source construction, wrong-directory rejection, alias-before-admission binding and
  font loads; no timing threshold used as a mechanism witness.
- Default loader integrity tests, mid-read/next-read JSON replacement/corruption, warm fresh
  admission and source invalidation, changed GOALS, source errors/raw-report preservation,
  fresh next-render fonts/timestamps and old standalone/fake call shapes remain covered.
- Full five-team prepared inputs/options and raw/enriched reports equal in all combined runs.
  All actual frozen22 owned→final/utility paths revalidated. Five decoded RGB PNGs match the
  retained renderer at a fixed timestamp, not merely file sizes or rounded winning species.
  Real workflows stamp fresh current Phoenix time and decode five1260×2120 PNGs plus a valid
  six-entry ZIP; they do NOT copy old stamped images.
- Full committed-code local gates: **203 Vitest /315 Python (zero skips) /13 Node /214 browser**,
  no flaky final browser summary. Exact CI run coverage must be reconciled separately at
  release; a green job alone is not proof it ran cache-backed local classes.
- Expected RED failures are preserved. An initial new-worktree broad invocation lacked Node
  packages and failed two renderer tests; locked npm ci corrected the prerequisite without
  changing the lock/install-script policy. A180s passing prefix was interrupted, not accepted;
  a complete rerun passed. A fixture incorrectly expected unknown tier Untiered accepted and
  was corrected to verify the SAME rejection in all three APIs; no production tier policy
  changed. Npm audit reports8 high advisories on unchanged dependencies, left for audit#1,
  not auto-fixed or attributed to this change.
- Private snapshots/UIDs/reports/input corpora remain outside public git. Parent solo scope/
  security review is NOT independent review. No additional agents/PRs were used.

Every measured selector reads full Caught/Seen/favorites before result-cache admission; initial
sets are logged and compared across trials. Wrapper checks Caught/Seen again. Final delivery
additionally reads ALL three sets fresh and compares them to the observed selection inputs;
a matching caught COUNT alone is insufficient. Do not turn unchanged results into authority
to reuse old ownership or erase a changed favorite. No player-state writes occur.

## Integration and release acceptance

For orchestrators that already preflight (Python, not a new CLI flag):

```python
source = story_moves.MoveSources(cache)
for final, owned in paths:
    source.targets(final, owned)  # acquisition/GOALS failures remain visible
cards.main(argv, move_sources=source)
```

Use this only within one run and the matching cache. Install an external/private caller update
AFTER current main supports the API; a backed-up feature branch is not installed behavior.
The release must exercise that installed wrapper, compare its actual source/font witnesses,
raw/enriched results, current timestamps and fresh full input sets, then deliver all five
cards/ZIP. Require exact primary/mirror author/raw/ref, CI, Pages/live/unchanged app bytes and
canonical issue acceptance before claiming shipped. Parent#4 remains subject to combined
child acceptance; held-item report/cards#5 and public-material audit#1 remain separate work.
