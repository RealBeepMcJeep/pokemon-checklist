# Analysis tools hardening

## Goal

Turn the recurring chat workflows and Pokémon-analysis passes into tested, deterministic commands.
Correct known mechanics and scoring defects before adding more heuristics.

## Constraints

- Catch utility remains independent of competitive tier and bulk.
- Long-term team analysis uses reachable final-evolution paths, but reports ability, form,
  evolution and move-acquisition uncertainty rather than silently assuming them.
- Mechanics and learnset data must be pinned to the app's Gen VII snapshot.
- Account writes are minimal, server-timestamped, schema-validated and read back.
- The website and offline-only behavior are not changed by this work.
- Python tools remain standard-library-only.

## Stage 1 — mechanics and catcher correctness

1. Add an exact Gen VI/VII catch-probability calculator with regular and critical captures.
2. Correct secondary-effect parsing, No Guard/Compound Eyes handling, island timing,
   Worry Seed classification and rank-decay reconciliation.
3. Split branching evolutionary paths so one score cannot combine mutually exclusive forms.
4. Add structured JSON output and regression tests.

## Stage 2 — recurring chat operations

1. Add a single `pokemon_ops.py` command for mark, evolve, trade, exact favorites reconciliation,
   roster listing and catch odds.
2. Validate record keys and values; queries never emit writes.
3. Compute minimal diffs, skip no-ops, apply one patch and verify exact values by reading them back.
4. Harden chat log entries to carry one `key/from/to` change per log record.

## Stage 3 — team optimizer

1. Deduplicate multiple caught stages into one evolutionary-line candidate.
2. Share roster/filter logic between builder and synergy search.
3. Add complete tier ordering, argument validation and explicit search-pruning disclosure.
4. Use tier-local moveset data and retain the strongest feasible move per attack type.
5. Fix diversity and shared-weakness thresholds.
6. Surface form, hidden-ability and evolution assumptions.

## Stage 4 — move reports/cards and source integrity

1. Pin Showdown mechanics data to the same historical commit as `pokedex-details.json`.
2. Isolate branching paths per final evolution and normalize punctuated species slugs.
3. Preserve Hidden Power's actual usage type.
4. Show progression-aware TM/tutor/reminder labels and important ability/evolution constraints.
5. Make temporary rendering collision-safe and file URLs robust.
6. Add narrow-card overflow assertions and representative golden/smoke tests.

## Verification

- Run the stdlib tool test suite and include it in `npm run check`.
- Re-run the current roster through catcher and team commands.
- Verify ranking and `--explain` totals agree.
- Compare catch-probability vectors with independent Gen VI/VII mechanics references.
- Render and visually inspect a normal card and a branching card.
- Run all existing unit and Playwright tests.
- Commit and push only after the repository is clean and every relevant gate is green.
