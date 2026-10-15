# Alola Wild Checklist

A self-contained wild Pokémon checklist for the supplied Generation VII location guide and all four vanilla Alola games. It covers National Dex 001–807, chronological island/location sections, encounter rates, SOS allies, optional forms, and a searchable Pokédex in a responsive dark encyclopedia layout.

## Use it

Open [`index.html`](index.html) directly in a browser. It is self-contained and works from `file://`; no server, package manager, CDN, or network connection is needed.

Use the **Game mode** dropdown to switch among Prismatic Moon, Pokémon Sun, Pokémon Moon, Pokémon Ultra Sun, and Pokémon Ultra Moon. Each mode has its own color theme and encounters. The current location is retained when possible, Pokémon and form progress is shared, and the last mode is restored next session. Vanilla modes omit the mod guide's numbered maps.

Select a Pokémon's name in the guide or Pokédex to open its Pokédex details, showing every known location in the active mode, including its island, encounter group, availability, whether it is a wild encounter or SOS ally, and a direct Bulbapedia reference link. Each Pokédex row also shows colored type dots and a child-friendly SSS–F grade; unevolved Pokémon inherit the strongest grade from their ordinary final evolutions. Hover a grade for its frozen November 2019 Gen VII source tier, inherited Pokémon's own tier, and OU usage context. When form tracking is enabled, selected tracked forms show their own types and grades. When a Pokémon has no direct encounter in the active mode, the Pokédex shows a clickable Generation VII evolution chain with levels or special methods leading to it when one exists, without inventing a location link.

Before you pick a Pokémon, the Pokédex shows **Catch next**: the uncaught catch-now Pokémon at the next unfinished location, with unseen Pokémon ahead of seen Pokémon, their status buttons and a jump to that location. Route order stays unchanged. On phones, suggestions start collapsed; tap the heading to expand them, and they scroll away with the Pokémon list instead of staying pinned above it. Desktop suggestions start expanded. Each entry lists where the Pokémon appears in the other game modes and always shows its evolution path.

On a phone, the header stays pinned while reading and shrinks to one compact row after scrolling. The game shortcut, **Not caught / Seen / Caught** totals, Pokédex, Tools, and **Settings** remain available. Settings keeps the full Game mode picker, Track forms and form progress, Backup/Restore/Reset, account/sync controls, and the actual app version/build-source hash at the bottom. Offline/pending/error and view-only/held-clear safeguards stay visible outside closed Settings. Desktop retains its existing controls and adds Settings for Prismatic Moon encounter unlocks. The compact three-color rail shows the collection buckets; the **Overall caught** progress bar remains in Settings.

On a phone, **Add to Home Screen** installs the checklist as a full-screen app with its own icon; it still works offline.

Each Pokédex entry also has a collapsed **Popular moves** panel: the moves competitive players ran most for that Pokémon, or for each final evolution it grows into, with how the game teaches each one (level, Move Reminder, TM and where, tutor and its BP cost, egg move, or not obtainable in Gen 7). Usage is Smogon's November 2019 Gen 7 data from each Pokémon's own tier; learnsets are standard Gen 7, and in the Photonic Sun / Prismatic Moon mode egg moves are described as learned by level-up, as that hack does.

Status buttons cycle **None → Caught → Seen → None**. Collection summaries show **Not caught / Seen / Caught**, with mutually exclusive buckets: Not caught means neither seen nor caught, and Seen means seen-only. Location headers count each currently eligible species once; locked encounters do not block current completion. Overall and Pokédex status totals cover all 807 species; the optional form summary covers forms in the active game mode. Filtered search totals remain separate. Only Caught fills the progress bar or completes a location. The browser saves species statuses, tracked forms, starred Pokémon, and the selected mode in versioned local storage (`pokemon-checklist-state-v4`). Existing v1, v2 and v3 browser saves and backup files migrate without changing progress, and an upgraded save is rewritten under the current key while the older key is left untouched. **Backup** downloads deterministic JSON; **Restore** validates the complete file before asking to replace the current checklist. If storage is unavailable, changes remain visible until the tab closes.

Star any Pokédex row to pin that Pokémon above the rest of the list; click the star again to release it. Starred entries stay in National Dex order among themselves, still float to the top inside search results, are kept in backups, and are cleared by Reset along with progress.

Opening the checklist in more than one tab keeps them in sync: a change made in one tab appears in the others immediately, with a notice, and without reloading. This covers statuses, tracked forms, the selected mode, Restore, and Reset. Tabs of the `file://` copy share a local-storage origin in Chromium and sync as well, but browsers are free to isolate local files, so treat cross-tab sync as a served-page guarantee rather than a documented offline one.

**Sign in to sync** is optional and off until you press it. Unsigned/offline mode remains fully local: it never contacts the network and the checklist still works from `file://` without a server. While signed in, a change on one device appears on the others on its own; a change made offline is sent when the connection returns; and if two devices change the same species, the one that reaches the server later wins. The first sign-in on a device adopts the progress already on that device rather than discarding it, and signing out returns that device to its own checklist without deleting anything. Each account keeps its own separate checklist, because progress belongs to a person.

## Saved encounter unlocks

In Prismatic Moon, open **Settings** to enable Tauros Charge, Surfing, Fishing,
SOS Calls and Weather SOS. Desktop has a Settings button; phones retain the existing
Settings dialog. Flags start off on migration and are saved in v4 backups, across tabs
and account sync; they do not mark or clear Pokémon. Location counters, Catch next and
availability labels update immediately. Locked totals stay separate; **Backtrack** marks
a regular-complete area with newly eligible uncaught species. Weather SOS also needs
SOS and caller access, and its actual weather conditions still apply. Other story-only
restrictions remain unchanged. Unsupported vanilla-mode controls are hidden because those
SOS datasets do not identify callers. Reset clears unlocks; older keys/last-good copies
remain available after upgrade. Older signed-in builds may need a reload after flags are set.

## Local catcher comparison

`python tools/catcher_efficiency.py --uid <uid> --level 30 --output-dir <private-dir>` creates a fresh read-only utility card plus a separate False Swipe setup-efficiency companion, structured reports and ZIP. Ability/stat/target scenarios are explicit; damage throughput never becomes utility points or capture probability. See [model, assumptions and independent reference](docs/catcher-efficiency.md). No checklist UI/save changes are involved.

## Tools and catch calculator

Open **Tools** in the checklist header for the QR archive, experimental QR page,
and an offline Gen VII catch calculator. Desktop shows Pokémon/ball selectors beside
a parameter column; phones use one compact stack. Click neighboring sprites or swipe
or drag to step through the animated wrapping selectors, and click a selected name
to search with sprite-bearing keyboard/touch autocomplete. Reduced-motion settings
are respected. Selectors follow National Dex order and include alternate forms only
when their stock catch rate differs from their own base form in the selected game;
retained forms label reused base artwork honestly. A compact Pokémon catch-rate badge
shows the effective rate, with stock/override/Heavy Ball details in its accessible label. Catch chance is
prominent and color-coded, with a numeric percentage and text tier. Choose one major
status chip, estimate remaining HP with the slider,
or enter exact current/maximum HP. Conditional balls expose only their relevant
inputs; the result updates per throw and includes a multiplier breakdown. The HP
slider is vivid green at full health, yellow at half, and red when low. **Set 1 HP**
keeps the current input mode. By owner convention, the slider's 1% endpoint means
**1 HP assumed** for False Swipe/Hold Back, using the last entered valid maximum or
a labeled 100-HP estimate; other percentages retain the ordinary percentage estimate.
Actual maximum HP is not inferred from species or level.

Optional critical captures use the game's **historical registered-caught species**,
not the checklist's current inventory count. Repeat Ball uses the same historical
distinction. Roto Catch defaults off and is available only in Ultra modes. Calculator
battle inputs are temporary and never change checklist progress. Only the selected
Pokémon ID/form and ball are remembered on this device under the isolated
`pokemon-checklist-catch-selection-v1` key; they are not part of checklist backups or
account sync. Defaults are Pikachu and Poké Ball; unavailable storage produces a
notice without breaking the calculator.

The calculator follows the published staged fixed-point Gen VII model, with pinned
stock SM/USUM catch rates, types, speed, gender and form weights. It is not native
bit-exact emulation or verified Prismatic/Photonic capture-engine data. Percentage HP
is an estimate; a labeled catch-rate override supports known hack-specific values.
The expandable notes show the formula and sources; [implementation/data provenance](plans/catch-tools.md)
documents the limits. `python tools/build_capture_data.py --check` verifies the
retained source hashes and generated data offline.

## QR gallery

Open the separate [QR gallery](qr.html), also available at
<https://realbeepmcjeep.github.io/pokemon-checklist/qr.html>.
Its ordinary-code catalogue contains 244 attributed original images from the
Bulbagarden Sun/Moon and Ultra Sun/Ultra Moon libraries, covering 198 species
and their included forms—not the entire National Pokédex. Search by name or
Dex number, sort by number or name in either direction (number ascending by default),
filter by type or source library, and tap a card or QR to open a
full-screen scanning view. It is a self-contained offline file; it has no
account connection and does not read or change checklist progress.

An ordinary Pokédex QR registers a seen entry where applicable; it does not
deliver the pictured Pokémon. Source-library filters describe provenance, not
exclusive game compatibility. Acceptance of Ultra-only catalogue entries by
original Sun/Moon remains unverified; points or successful software decoding
are not proof that the intended species was recognized. Promotional gifts
and Island Scan are different mechanisms.

Promotional gifts are in a separate section: an American-region Magearna code
for all four games after becoming Champion, and the shared American/PAL
Partner Cap Pikachu code for Ultra Sun/Ultra Moon after reaching Akala Island.
The cards give the region, game eligibility and claim steps. These are
source-backed original event codes, not generated gifts; their raw PNG
payloads were checked, but no console redemption or event-signature
verification was performed. See the [gift research and sources](references/qr-gifts/report.md).

The [protocol and catalogue documentation](references/qr-codes/PROTOCOL.md)
explains raw-byte decoding, signature verification, locally generated codes,
source provenance, and the limits of these out-of-game checks. Refreshing the
source catalogue is explicit and networked; normal rebuilds are offline:

```text
python tools/build_qr_catalog.py --verify-only
npm run build:qr
npm run check:qr
python tools/qr_codec.py generate 25 --template references/qr-codes/images/304912.png --out Pikachu.png
```

Generated codes are labeled locally generated, not official or console-tested.

### Experimental generated QR page

The separate [experimental page](qr-experimental.html) covers all 807 Gen I–VII
species and the alternate-form rows in the pinned Gen VII personal table. It
shares the archive's card renderer, sorting, filters, full-screen scan viewer,
checklist type-chip colors and pixel-sprite atlas. Sprites depict the base species,
not necessarily the selected form. This page does not modify checklist progress.

Every generated image is decoded back to raw bytes and its ordinary-code signature,
species and form are checked during compilation. These are software checks, **not
proof of in-game acceptance**. Numeric form rows may include battle-only or otherwise
unsupported scanner forms; this is not every gender/shiny combination and it does
not generate event gifts. The page includes staged console-test suggestions and
distinguishes intended recognition, Wonder QR fallback and rejection.

Live pages:
- Checklist: <https://realbeepmcjeep.github.io/pokemon-checklist/>
- Original QR archive: <https://realbeepmcjeep.github.io/pokemon-checklist/qr.html>
- Experimental QR codes: <https://realbeepmcjeep.github.io/pokemon-checklist/qr-experimental.html>

## Current-horizon catcher comparison

`python tools/catcher_now.py --uid <uid> --level 30 --output-dir <private-directory>`
produces a read-only JSON report and phone-readable `catchers.png`. It uses the verified
Prismatic Standard level table, treats TM54 as confirmed owned for this workflow, and
excludes unconfirmed TMs/tutors, breeding and late reminder gates. Only one mutually
exclusive major status scores. Ordinary reachable level evolutions are labeled as plans,
not owned final stages; Smeargle is a conditional, donor-backed Sketch setup with a 0.80
setup-effort factor and a level-dependent copy budget. Scores are utility heuristics, not
capture percentages; tier/stats appear beside them without adding points. Actual individual
ability/move retention still needs checking. Reports and personal snapshots belong outside git.
The older prospective `catcher_score.py` remains a vanilla-timing family analysis, but now
also prevents adding mutually exclusive major-status benefits.

## Local five-team search

The read-only story tools select OG, Non-OG, Mixed, ordinary-level Pokédex and
Best parties with Butterfree fixed as the catcher. Python prepares roster/data
inputs, expands reports and renders cards; an optional dependency-free Rust
executable accelerates only the exact search. Candidate pools, ranking priorities,
ownership constraints and tie-breaking are unchanged; no shortlist is used.

Build the release executable explicitly with an installed Rust/Cargo toolchain:

```text
python native/story-search/build.py
python tools/team_synergy.py --story-options --json --uid <uid> --cache <verified-cache>
python tools/story_team_cards.py --uid <uid> --cache <verified-cache> --output-dir <private-directory>
```

The build is offline and writes outside git under
`$XDG_CACHE_HOME/pokemon-checklist/story-search/<source-hash>/` (or `~/.cache/`).
Routine searches never invoke Cargo or download a binary. Missing, failed or
unsupported native execution falls back to the Python reference.
`STORY_NATIVE_DISABLE=1` forces that reference; `STORY_NATIVE_BINARY` overrides
the executable path. The current build helper targets baseline x86-64.

Selection results are cached privately under `<verified-cache>/story-selection-v1`
**after** fresh roster/favorites, settings and data preparation. Keys cover all
prepared ranking inputs, implementation sources, Python runtime, and the actual
selected executable's path/content and native enable/availability state. Corrupt
or inaccessible cache entries trigger recomputation. Atomic JSON writes preserve
report types, repair private permissions, cap each entry at 8 MiB and retain at
most 32 entries. Both commands accept `--no-result-cache` for a bypass; this does
not disable the Rust search or the verified source-data cache.

A controlled all-five benchmark on identical frozen inputs measured 991.36 seconds
with the Python reference and 6.60 seconds with Rust (about 150× search-only),
with matching winners and detailed scores. End-to-end runs still include fresh
account reads, preparation, acquisition checks and rendering; warm-cache latency
is not zero. Growth still depends on each eligible pool's `C(n, 5)` search space.
Newly selected endpoints without curated acquisition-checked move targets
intentionally stop card generation rather than inventing a move set.

Source-block lookup now uses a bounded, content-keyed parse index while preserving
integrity validation and fresh reads. A three-trial complete-workflow comparison
measured cold medians of 108.95→71.69 seconds and warm medians of 56.09→15.37
seconds on one shared host; ranges, CPU/RSS, source identities and limitations
are in [the performance report](docs/five-team-performance.md). This is parsing
acceleration, not a new Rust port or changed team-selection objective.

Best/Pokédex search also uses strict, conservative unfinished-branch bounds with
exact ownership-completion counts; equal-primary ties still receive secondary
comparison. A repeated complete-workflow comparison against the parser-index
release measured cold medians of 93.51→60.72 seconds;
warm runs made zero searches. [Proof, full parity, CPU/RSS and timing ranges](docs/primary-subtree-bounds.md)
document the numerical guard and shared-host limitations. Scoring, objectives and
complete report/counter semantics remain unchanged.

The ranking fast path also avoids sorting names for candidates already worse on
numeric priorities. Separate enum/mask experiments were evaluated and rejected;
only the measured lazy-name change is retained. A three-trial complete-workflow
comparison measured cold medians 44.45→41.97 seconds; scores, ties,
counters and fresh-read/cache behavior are unchanged. See
[the retained/rejected experiment report](docs/native-fast-path.md) for ranges,
CPU/RSS and the disclosed failed account-readback attempt.

Compatible Mixed and Non-OG objectives now share one native enumeration while retaining
separate winners and unchanged report counters. A three-trial complete-workflow comparison
measured cold medians 42.15→35.11 seconds; warm reuse still skips native work but not fresh
account reads. See [shared-enumeration evidence](docs/fused-enumeration.md) for the exact
compatibility gates, fallback, ranges and limits. Parallelism is a separate pending milestone.

## Develop

Install Node 22 and the locked dependencies, then start Vite:

```text
npm ci
npm run dev
```

The development server provides Preact component HMR and live CSS updates. It serves source modules and assets normally for fast iteration; the one-file constraint applies to production builds.

## Build and validate

Install the Python tooling dependencies with `python -m pip install -r requirements-dev.txt`. From the repository root:

```text
npm run build
npm run check
npx playwright install chromium
npm run test:e2e
python tools/extract_reference.py --validate
python tools/build_icons.py --check
python tools/build_ball_sprites.py --check
python tools/build_vanilla_encounters.py --check
```

Vite builds to temporary `dist/index.html`; `tools/publish.mjs` verifies it is the only output, rejects external scripts, stylesheets, iframe/object/embed/media/track resources, CSS `url(...)` and `@import` references, source maps, and unresolved build tokens, and copies it to the tracked root `index.html`. Data URLs and fragment-only references remain valid embedded resources. `npm run build:check` rebuilds without changing the root file and fails when that committed artifact is stale. The no-network guarantee is behavioural and enforced by a browser test rather than by that check: while signed out the artifact may not so much as *attempt* a request to anything other than `data:`, `file:` or localhost, on a desktop or a mobile user agent. CSS, JavaScript, JSON, the icon atlas, and every location image are inlined for direct `file://` use.

### Local chat status operations

`tools/pokemon_ops.py` is the local status authority (requires an externally stored Firebase service account):

```sh
python tools/pokemon_ops.py --uid <account> --json status pikachu
python tools/pokemon_ops.py --uid <account> --json set-status pikachu caught --old-status seen
python tools/pokemon_ops.py --uid <account> --json trade pikachu raichu
python tools/pokemon_ops.py --uid <account> --json evolve Totodile
python tools/pokemon_ops.py --uid <account> --json evolve Eevee Vaporeon
```

The injectable `PokemonStatusTool` API exposes `check_pokemon_status`, private `_set_pokemon_status`, public `set_pokemon_status` with optional `old_status`, `trade_pokemon_status`, and `evolve_pokemon_status(name, to_name=None)`. Exact normalized names/slugs or National Dex IDs are required; correction suggestions never auto-select a species. Already-set requests warn without writes. Expected-old guards are enforced against the Firebase ETag snapshot and rechecked after conflicts. Both trade statuses and audit entries share one conditional account update, followed by exact readback and a caught total from that same snapshot. `--dry-run` previews changes; its status/count fields describe current state, not a completed mutation. Existing `mark`, `evolve`, favorites and list commands remain available. No reset command is exposed.

`evolve FROM [TO]` derives the **immediate next species**, not the final form, from committed local Gen VII move-line IDs and Pokédex paths; no web lookup is needed. A unique target uses the same atomic FROM→Seen / TO→Caught update and verified readback/count. Branches return `evolution_choice_required` with canonical candidates before account reads/writes; terminal species and required malformed/missing paths refuse safely. Explicit FROM TO still works. Form/favorite/settings records are untouched. Already-completed pairs include `verified_no_write` and the observed statuses in one read. This records a reported evolution, not whether level/item/gender requirements have been met. The current metadata has a malformed Flabébé predecessor token; that automatic path refuses rather than repairing it silently, so specify its verified target explicitly.

`npm run check` runs strict TypeScript checking, Vitest, the production build/freshness audit, the full Python tool suite plus chat self-test, and deterministic Node tool tests. Playwright runs the same UI parity checks against both the Vite server and the generated standalone file, with network access blocked for the latter. GitHub Actions runs `npm run check`, `npm run test:e2e`, `python tools/extract_reference.py --validate`, and a syntax-only `py_compile` pass over the generator scripts for pull requests and `main`. `build_icons.py --check` and `build_vanilla_encounters.py --check` are not part of that CI job: both need a locally bootstrapped, hash-verified source cache (see below) that CI does not fetch, so they stay a local pre-push check.

`data/encounters.json` and the four `data/encounters-{game}.json` files are the canonical mode datasets. To re-extract the PDF images, use `python tools/extract_reference.py --extract-assets`. To refresh the pinned Pokémon name snapshot, use `--refresh-pokemon`. `python tools/build_moves.py` regenerates `data/moves.json` (Popular moves) offline from the same pinned Showdown cache plus hash-pinned Smogon moveset files; see `docs/showdown-data.md`. `python tools/build_pokedex_details.py` regenerates the type, evolution, inherited-grade, form, and usage snapshot from checksum-pinned Pokémon Showdown sources; it requires network access, while normal builds remain offline.

The source regenerators are offline by default, with one exception: `build_pokedex_details.py` downloads its separate, hash-pinned Smogon usage snapshot on every run, including `--check`, because that snapshot is not part of the bootstrapped cache contract below — it has no offline-only code path. The 22 ball sprites are a small committed hash-verified input cache under `references/ball-sprites/`, pinned to the same PokéAPI commit as the Pokémon atlas; `build_ball_sprites.py --check` runs offline in ordinary builds and CI, and `--refresh` explicitly refetches those exact sources. Every other regenerator's verified raw inputs live outside the repository in the platform cache directory (`%LOCALAPPDATA%/pokemon-checklist/` on Windows, `$XDG_CACHE_HOME/pokemon-checklist/` or `~/.cache/pokemon-checklist/` elsewhere); use `--cache-dir` to override it. Normal generation and `--check` only read that cache and fail clearly when it is missing or corrupt. The explicit refresh commands are networked and should be run only when inputs need bootstrapping or updating:

```text
python tools/build_icons.py --refresh
python tools/build_vanilla_encounters.py --refresh
```

Both commands accept `--cache-dir PATH`; `build_vanilla_encounters.py --game sun` (repeatable) limits table refresh/build. Direct `--source-dir` and `--tables-dir` overrides remain available for fully local vanilla builds. The icon cache pins the PokéAPI sprites source to commit `6e3e7c43e86db0e1b2277795cfee41b11e8df2a4` and validates all 807 40×30 PNGs plus the license. Vanilla tables come from the pinned [Pokémon Sun mirror](https://gist.github.com/RichardPaulAstley/42fbabe24250969f22d18fe8b919c520), SciresM's Pokémon Moon Pastebins (`YjNi4Qdk` and `HKEVPUYX`), and the pinned [Ultra Sun](https://gist.github.com/SciresM/a539739085e24af55dffdf443cb70eb2) and [Ultra Moon](https://gist.github.com/SciresM/deecdcf5fc49fc8191a29d111643c6b6) dumps. SHA-256 checks guard every table download and cache entry. The pinned [PokeAPI repository](https://github.com/PokeAPI/pokeapi/tree/4b82c204ddd19ecb8eda2ea044ccb59e222b721c/data/v2/csv) supplies normalized area, method, SOS, Island Scan, berry-pile, and postgame records.

## Attribution and disclaimer

Photonic Sun / Prismatic Moon encounter data and location screenshots/maps come from `references/Wild Pokemon Locations.pdf`. Vanilla Alola data uses the pinned sources described above; reused scenic screenshots come from the same guide, while mod-specific numbered maps are excluded. Pokémon names are a snapshot of the English PokéAPI species-name data. Types and source tiers come from the pinned MIT-licensed Pokémon Showdown Gen VII data, and usage is from Smogon's November 2019 Gen VII OU statistics; the displayed SSS–F grades are this project's simplified, child-friendly mapping. The icon atlas is generated from the PokéAPI sprites Generation VII menu icons; its license notice is preserved in `references/PokeAPI-sprites-LICENCE.txt`. Image contents are copyright The Pokémon Company and respective rights holders.

This is a private, personal, non-commercial fan project. It is not affiliated with, endorsed by, or sponsored by Nintendo, Game Freak, The Pokémon Company, PokéAPI, or the guide author. Do not redistribute assets or use this project commercially without checking the applicable rights.
