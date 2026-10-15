# Five-team pipeline performance — issue #4

Status: bounded source index implemented and full local gates passed; milestone #6 repeated measurements and publication are in progress. Parent #4 remains open for #6–#11.

## Approved contract

Solo/direct integration, no subagents/PRs. Preserve fixed Butterfree, all five objectives, full eligible pools, independent ownership, priority/tie order, source/acquisition/ability gates, fresh live reads and report semantics. No app/save changes or personal snapshots in git. Existing Rust acceleration and selection cache are baseline, not new work.

## Measured baseline and hypothesis

Actual all-five wrapper, 131-caught read-only live snapshot, Linux x86-64, 8 logical CPUs, retained verified Showdown/Standard/chaos sources and native Rust engine. Source code: 828c7bd. Cold means result-cache bypass, not OS page-cache flushing. Separate profiler-instrumented and unprofiled measurements; private evidence under /opt/data/goals/gallery-perf-baseline/.

Unprofiled complete cold run: 92.928 seconds; warm run: 38.891 seconds. Both actual galleries succeeded, fresh Caught/Seen readbacks matched, and all five parties/scores matched the prior gallery. Profiled cold: 98.249 seconds; warm: 53.790 seconds. Do not compute improvement from profiled vs unprofiled halves.

The profiled selector called block() 1,556 times, repeatedly advancing top_blocks() 729,516 times and spending 30.812 cumulative seconds scanning. Native full-pool search remains substantial (117-candidate Mixed/Best, 94 Non-OG, 76 Pokédex, 15 OG); no search rewrite is proposed for this slice.

## Approved milestone sequence

The owner approved retaining #4 as the umbrella and recording original proposals,
Opus 5.5 High read-only review and evidence-checked reconciliation separately.
Execute #6 (source index/baseline), #7 (exact Best/Pokédex bounds), #8 (actual
Rust fast path), #9 (compatible Mixed/Non-OG fusion), #10 (bounded deterministic
parallelism), then #11 (fixed preparation/enrichment/render costs). Preserve
complete diagnostic counters as well as winners/ties; do not silently call an
unprofitable, deferred or blocked experiment delivered. Scope reduction needs
an explicit owner disposition. No additional agents or PR workflow are authorized.

Actual frozen story profiles have uniform coverage and disjoint weakness/resist
flags for all five objectives; do not optimize the generic vector path assuming
it is this gallery's hot path. Existing Rust execution is baseline functionality.

## Minimal change and acceptance

1. RED: repeated different-name lookups into one immutable source text must index it once.
2. GREEN: bounded eight-source content-keyed LRU index; preserve first normalized-key match exactly, empty/missing results and current parser behavior. A changed source string must miss. Do not cache away manifest reads or filesystem integrity validation.
3. Prove semantic preservation on duplicate/punctuation keys, malformed/changed/missing content, eviction, and all blocks in the verified corpus. Retain source verification/corruption tests.
4. Compare prepared profiles and complete frozen/native reports before/after on identical source/account settings. Retain existing native/Python small exhaustive/random/adversarial/tie/cache tests; no scoring/selection code changes.
5. Re-run actual cold/warm all-five wrapper with same profiling boundaries and inputs, including PNG/ZIP/content checks and fresh reads; prove warm makes zero rank/search calls. Report phase costs, pools, measured deltas and limitations, not future-runtime guarantees.
6. Run full project/Python/browser gates; parent review, explicit staging/security scan, integrate/push, verify exact mirrors/author/files/CI/Pages and unchanged app bytes. Deliver actual five cards/ZIP and measured report before issue closeout.
