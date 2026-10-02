# Exact five-team search acceleration

## Approved scope

Speed up the existing five story objectives without changing their winners, ownership constraints, ranking priorities, scores, tied-candidate identity, evolution legality, or card rendering. Use Rust only for the computational search, leaving roster/data preparation, reports, move enrichment, and image rendering in Python. Keep the legacy competitive CLI intact. The owner explicitly requires direct integration into main, not a PR workflow.

## Implementation boundaries

1. Isolate a Rust search engine behind a small Python adapter. Prefer a release-built local executable with no runtime service; preserve a correct Python fallback if the executable is unavailable. The acceleration must not require network, root, a changed browser bundle, or a new frontend dependency. Benchmark before accepting the native path.
2. Prune branches only with admissible objective bounds and share immutable preparation/scoring when safe. No tier shortlist, random heuristic, objective change, or silent candidate cap. Preserve Python rounding/tie semantics; test adversarial near-ties, duplicate names/types, ownership-overlapping siblings, uniform and nonuniform strengths, and self-resist exclusion.
3. Cache selection results only after reading and validating fresh roster/data inputs. Fingerprint all actual prepared search inputs and relevant implementation identity. Include favorites, utility, forms, exclusion effects, ordinary-level endpoints, ability weights, and chart/score changes through their prepared inputs. Private cache outside git, bounded retention, atomic writes, explicit permission repair, corruption treated as miss. Cache must be usable by both real team_synergy.py and story_team_cards.py paths; provide a bypass for cold benchmarks. Do not cache Firebase reads or assume caught count proves identity.
4. Keep category outputs and legacy fields compatible. Existing searched_combinations is the full eligible search space, not a native visited-leaf claim. Put actual work diagnostics in distinctly named fields; never relabel pruned space as evaluated teams.

## Acceptance

- [ ] Baseline npm run check passes under pinned Node 22 and declared Python dev requirements.
- [ ] Freeze one fresh real roster's prepared inputs privately and measure baseline on exactly those inputs.
- [ ] Observe new tests RED before production changes; verify native scores, lexicographic keys, winning indices/identities and detailed component scores against exhaustive reference fixtures.
- [ ] Parent independently reviews and executes each implementation; compare all five real frozen-input results against baseline.
- [ ] Measure native cold selection, cache miss/hit, and full live card CLI; report measured timings, not a promised target.
- [ ] Verify cache invalidation, bypass, corruption, permissions, and unavailable-native fallback.
- [ ] Run complete Python/app/tool gates and both browser projects. Leave index.html, qr.html, and qr-experimental.html unchanged.
- [ ] Update existing docs/changelog with truthful operational/build instructions and measured conclusions.
- [ ] Merge directly into current main, push, verify exact remote commit/CI and unchanged live artifacts, clean task-owned branches/worktrees, and leave main clean.

## Deliberately excluded

No website rewrite, GPU/service integration, schedule changes, save mutations, changed move targets, unproven approximate search, or mandatory inference at runtime. Any native speedup is additional to pruning/caching, not a claim that combinatorial growth disappears.
