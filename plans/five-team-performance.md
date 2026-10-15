# Five-team pipeline performance — issue #4

Status: #6–#11 and parent#4 verified shipped/CLOSED at25ec081/c2c3779/9bcc2ad/952cfc2/db7e097/2f72723. Exact CI/Pages/live, installed cold+warm, full source readback and actual five-card/ZIP delivery accepted (comments21734/21737). Combined #11 default-serial workflow39.72→36.06s cold/11.49→8.58s warm, NOT summed stage percentages. See docs/fixed-costs.md for measurements and limitations. Remaining owner goal: #5 held-item report/cards, then #1 audit.

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

## Milestone #8 — retained lazy names

The existing Rust kernel now avoids sorted-name construction for numeric losers, not any scoring. Enum and permitted masks were tested and rejected for sub-noise/negative CPU benefit; a 257-pool mask initialization panic was reproduced before any main integration and removed with that experiment. Retained source is byte-identical to the verified e143196 lazy checkpoint. 3,000 ordinary-output cases and full frozen options match; 14 real complete workflow trials match raw/enriched/source sets. Observed cold median44.45→41.97s (5.6% wall,5.5% CPU); ranges do not overlap in this three-trial shared-host batch, not a guarantee. One final account-token readback failure was retained/excluded and its entire cold trial rerun successfully; warm variation is not credited. Full203 Vitest/283 Python/13 Node/214 browser pass. See [the complete experiment report](../docs/native-fast-path.md) for methodology, rejected trials, CPU/RSS/identity and its publication acceptance. #8 was verified released on9bcc2ad/closed; #9/#10 subsequently shipped as recorded below.

## Milestone #9 — conditional shared enumeration

Mixed and Non-OG now share one traversal only under exact flag/feature/subset compatibility, with separate incumbents/counters and original-path fallbacks. Protocol1 stays byte-identical; protocol2 is additive. Frozen3000 ordinary-byte cases and complete prepared reports match; actual native calls5→4 and54,639,948 Non-OG leaves reuse scores. Fourteen successful real workflow trials measured cold medians42.15→35.11s (16.7% wall); warm variation not credited. Native pair CPU32.03→25.17s (21.4%); do not add this to end-to-end savings. A subsequent unsupported-shape guard was observed RED→GREEN before release; hardened release952cfc2 passed exact final gates/current-main/CI/Pages/live/media/readback and#9 closed. See [the complete report](../docs/fused-enumeration.md). Parallelism#10 subsequently shipped below.

## Milestone #10 — optional deterministic workers

Only fused protocol2 may opt into bounded standard-library workers. Default1 spawns0 workers; strict lexicographic prefix-result reduction preserves first-encountered ties/counters. Retained3000-byte/frozen checks across1/2/3/4/8 plus400 repeated schedules and cross-thread cache reuse pass. Native4-thread opt-in measured3.15x elapsed reduction at24%more CPU; whole actual14-run comparison40.89→21.40s (47.6% less wall,16.1% MORE total CPU), not a default change. Warm variation not credited. Report default1+1% median with overlapping ranges and explicit shared-host limits; no zero-cost guarantee. See [detailed evidence](../docs/parallel-search.md). Full project/browser and exactdb7e097 release/default0worker+opt-in4worker media/CI/Pages/live/readback acceptance passed; #10 closed. #11 fixed costs shipped/closed as recorded in the current status and below.

## Milestone #11 — fixed preparation/enrichment/rendering

Pure name content memo is bounded by4096entries/256chars and converts str(value) every use.
Share one invocation-local tier JSON between Moves/Abilities, preserve legacy None-tier union/
fallback rules; inject a matching-cache preflight MoveSources into enrichment; re-resolve GOALS,
preserve default loader per-use integrity and next-constructor rejection. Font reuse is bounded
inside EACH card, not a global factory or old stamped PNG. No new source snapshot subsystem,
native/runtime language rewrite, changed compression or app/save/ownership changes.

Each candidate has its own predecessor comparison. Final combined14 actual default1/unset
workflows compare accepteddb7e097 withfcf5dfb:39.72→36.06s cold (9.2%wall/9.0%CPU),
11.49→8.58s warm (25.3%wall/26.7%CPU), all prepared/options/raw/enriched/full live inputs
identical, cold4native invocations vswarm0/freshread1. SameB50 executable, no default parallelism
credited. Font incremental cold median worsened0.6%wall/0.5%CPU with a retained43.01s outlier;
warm improved4.3%wall/3.6%CPU and isolated renderer14.0%wall/13.4%CPU, so do NOT claim a font
cold gain. Whole child gain is measured, not compounded. Three samples/shared host, no guarantee.

Actual constructors2→1 and font loads1084→65 witnessed in every combined run. Structural RED/
GREEN,10815 normalizer and1215 chaos cases, source/GOALS/error/alias/cache tests, all5 fixedstamp
RGB pixel comparisons pass; real cards retain fresh stamps. Full committed203Vitest/315Python
ZERO skips/13Node/214browser noflake pass. Parent solo/security review is NOT independent.
See [full mechanism/methodology/ranges/tradeoffs](../docs/fixed-costs.md). Final exact2f72723 release,
installed private-wrapper integration/execution (cold+warm), full source readback and actual media
delivery were verified before #11/#4 closure; acceptance comments21734/21737. Local315/0skip
and CI303/15skip were reconciled by test identity;214browser noflake. No remaining performance task.
