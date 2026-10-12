# Collection status counters

Approved display order: **Not caught / Seen / Caught**. Buckets are mutually
exclusive: status `none` (neither seen nor caught), `seen` only, and `caught`.
Visible labels plus status colors carry meaning; accessible group labels expose
every value. Shared StatusCounts prevents order drift.

1. Location headers partition `catchNowRows`: unique regular-species IDs only.
   Return-later encounters and SOS allies remain excluded from completion.
   Empty locations retain their no-catch-now message. Only all-caught is Complete.
2. Overall species and Pokédex collection summaries partition all 807 species.
   Pokédex `filtered of total` stays a separate result-size statistic.
3. Optional form totals partition only activeFormDefinitions, not every game
   combined. Tracking toggle controls visibility, not stored form ownership.
4. Counts are read-only computed signals and small subscribed summary components.
   No save/schema changes, new writes, or full-list rerender subscriptions.
   Restore/Undo/reset/status cycles/mode changes remain the source of truth.
5. Keep labels readable and unclipped at 360/412/1440; compact wrapping is safer
   than hiding labels or shrinking essential text. Native caught-progress bars
   preserve their existing meaning; HP/spawn/grade ratios are unrelated.

Acceptance: frozen parent location helper RED→GREEN, unique/status partition
unit cases, active forms and seeded browser counts, renderer-isolation and save
checks in both HTTP/standalone projects, then full combined app gates, Opus
design review and exact production verification.
