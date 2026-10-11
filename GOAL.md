# Goal: unseen-only Pokédex evolution gains

Only the Pokédex objective counts species whose fresh checklist status is `none`
(unseen). `seen` and `caught` stages earn zero; each candidate must have at least
one unseen gain on an ordinary-level-only path. Priorities remain gains, synergy,
then practical viability. OG, Non-OG, Mixed and Best are unchanged.

Read full live records before preparation and fingerprinted selection caching;
never infer unseen input from a caught-only snapshot. Preserve complete Rust /
Python report parity without changing native search when gains are precomputed.

Use per-behavior RED/GREEN tests for scoring and live propagation/cache freshness,
then run selector/cache/native suites and a read-only real story-options JSON CLI.
Keep personal results under scratch. No account writes, cards, operations-tool
edits, changelog, integration, push or PR. Commit only scoped reusable sources,
tests and this goal on the isolated branch.
