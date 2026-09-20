# Changelog

## 2026-09-19

- Consolidated active analysis tools on one commit-pinned, integrity-checked Pokémon Showdown cache and one small shared text parser; ordinary commands no longer download unpinned Showdown data.
- Made icon and vanilla encounter regeneration offline by default through external, hash-verified source caches. Network access now requires explicit `--refresh`, icon sources are commit-pinned, cache refreshes are atomic, and downloads have finite timeouts.
- Removed duplicate Firebase reads and Python subprocess/text interfaces from the catcher and team tools; one command now uses one account snapshot and structured in-process results.
- Bounded exhaustive team search at 100,000 combinations so larger flags fail before performing unbounded work while the default 42,504-combination search remains available.
- Reused the frontend's immutable validation indexes, cached each location's immutable catch-now rows, and removed unused state/sync exports and migration-only interfaces.
- Retained the canonical Prismatic Moon references and added a commit-pinned, SHA-256-verified Pokémon Showdown data contract for reproducible move, Pokédex, learnset, and type data.
- Added and hardened move-card, catcher, roster, team-building, synergy, and chat-checklist tools, including branch-aware move reports, opt-in Roto Catch calculations, and canonical evolution-line selection.
- Made signed-in sync preserve the latest local edit through server echoes, serialize rapid reversals, retry failed startup reads, ignore stale account starts, and register only one authentication watcher.
- Made an intentional Reset propagate atomically with its before-image in the sync log while retaining the guard against accidental whole-account clears; single-step undo remains future work.
- Kept sync changes flowing after a storage write failure, rejected read-only storage at startup, and made all sync cache access non-throwing.
- Enforced append-only Firebase log events, aligned the client allowlist with database-rule email matching, validated admin UIDs and National Dex IDs, and made admin changes ETag-guarded transactions with collision-resistant log IDs.
- Sandboxed static HTML rendering, expanded standalone-build checks to every supported external resource form, and prevented local browser tests from reusing an unrelated server.
- Added deterministic Node and Python tool tests plus the chat parser self-test to `npm run check` and CI, corrected offline/build documentation, and expanded regression coverage for the audited edge cases.
- Replaced the stale sync proposal with a concise current architecture/status document, removed a duplicate 2.3 MB reference PDF, fixed stale inline documentation, and ignored local `.env` credential files.

## 2026-09-18

- Stopped the Pokédex from freezing the page when it closes on a phone: the first close after opening blocked the main thread for about 1.5 seconds and now takes about 70 milliseconds at four-times CPU throttling.
- Found the cause in the icon sprites: the ~900 KB inlined sprite atlas was referenced as a CSS background, so all 807 Pokédex rows carried the entire atlas inside their computed style, and every full style recalculation over the list had to process it row by row.
- Draws each sprite from an image cropped by its icon box instead, which keeps the atlas out of computed styles entirely, and removed the document-wide custom property that held it.
- Kept every sprite, frame and mode theme identical: the same atlas is used, with the same crop per species, so nothing looks different.
- Added a browser check that fails if the atlas returns to a computed style, and that verifies the crop for a species on a lower atlas row.
- Added optional sign-in with Google so the same checklist follows you between your phone, tablet and PC. The app still works entirely offline and contacts nobody until you press **Sign in to sync**.
- Changes made on one signed-in device appear on the others on their own, without a reload.
- A change made while offline is kept and sent when the connection comes back. If two devices change the same species, the one that reaches the server later is the one that stays.
- Signing in adopts the progress already on that device instead of discarding it, and signing out returns that device to its own checklist without deleting anything.
- Each signed-in account keeps its own separate checklist; nothing is shared between accounts.
- Recorded `from` and `to` values on ordinary per-record sync log entries for history and future tooling. Reset before-images are logged, but undo is not built.

## 2026-09-16

- Added a build version stamp to the application header, rendered as `v<version> - <short commit>` (for example `v1.0.0 - 8d7c12`).
- Sourced the release number from `package.json` and the commit from the checked-out `HEAD` at build time, so the stamp is never hand-maintained.
- Injected the stamp as a single Vite/Vitest `define` through `tools/version.mjs`, so the application, the unit tests, and the publisher all read one definition.
- Made the publisher reject any build without a version stamp and normalize the stamp during `--check`, because a commit cannot contain its own hash and therefore the committed artifact always carries the parent commit.
- Synced progress between tabs: a checklist opened twice now mirrors statuses, forms, and the selected mode instead of diverging silently.
- Mirrored through the `storage` event, which browsers fire only in tabs that did not write, so a received state can never echo back into a write loop.
- Kept unreadable stored payloads from replacing progress a tab already holds, while treating a removed save as a cleared checklist.
- Verified the behavior in both browser suites: over the Vite dev server, and from the committed `file://` artifact with every network request blocked.
- Added starring to the Pokédex: click the star on a row to pin that species to the top of the list, and click it again to release it.
- Kept the starred group in National Dex order above everything else, and inside search results too.
- Moved the save format to schema v3 to carry `starred`; v1 and v2 saves and backups still load, migrate losslessly, and rewrite themselves under the new key while the older key is left intact for older builds.
- Included starred species in Backup and Restore, and made Reset clear them along with progress.
- Covered starring with domain, state, and browser tests: pinning, ordering, search interaction, reload persistence, and cross-tab sync.
- Mounted location sections lazily: a section's tables and maps are built the first time it is opened, instead of all 60 sections up front. Also made a location body stay mounted once opened, so anchor jumps and in-page search still find it.
- Mounted the Pokédex list lazily: on phones the drawer starts closed, so its 807 rows are built on first open rather than during startup.
- Measured on the built artifact under 4× CPU throttling at a phone viewport: first paint 26,864 → 2,332 ms, blocking long tasks 26,580 → 2,000 ms, DOM nodes 32,924 → 906 at rest.
- Stopped off-screen Pokédex rows from costing style, layout, and paint work, which removes the stall when the drawer opens or closes and when a search is widened back to the full list.
- Measured after that change, under the same 4× throttling: the first drawer open fell from ~23,700 ms to ~605 ms and later toggles to ~70 ms, repopulating all 807 rows after clearing a search fell from ~1,030 ms to ~560 ms, and the browser suite's own runtime fell from about two minutes to 26 seconds.

## 2026-09-14

- Initialized the Git repository with `main` as the default branch.
- Added the supplied Wild Pokémon Locations PDF and ignored local `.pi` working files.
- Inspected the 67-page reference and agreed on the application specification.
- Created the private Gitea repository `dsh-adult/pokemon-checklist` and connected `main` to it.
- Built and verified an offline 807-frame Gen VII Pokémon icon atlas from PokéAPI's sprite repository.
- Preserved the upstream sprite licensing notice and documented asset provenance.
- Added the complete National Dex 001–807 name snapshot.
- Transcribed and normalized all 60 locations, 172 encounter groups, and 908 encounter rows from the 67-page guide.
- Preserved levels, rates, day/night and bubbling columns, SOS allies, conditions, forms, notes, source pages, and chronological ordering.
- Classified 104 encounter groups as regular and 68 as Return later.
- Extracted and mapped 71 useful title, island, location, and map images while excluding decorative swatches.
- Added a reproducible extraction and validation utility and corrected the explicit Floette-Eternal and Route 5 revisit metadata.
- Validated all 807 species IDs, encounter references, stable IDs, source pages, and asset paths.
- Corrected all seven grass-region maps to include the PDF's numbered vector overlays, with regression validation to prevent stripped markers.
- Added the responsive chronological location checklist with expandable sections, all associated images, encounter details, and Return later labels.
- Added the searchable National Dex sidebar/mobile drawer with all 807 icons, shared tri-state statuses, and links to direct and optional encounters.
- Added first-incomplete location navigation based on unique regular species.
- Added optional Living Form Dex tracking and form-to-species status promotion.
- Added versioned localStorage persistence, reset, deterministic export, and validated replace-only import.
- Added keyboard-accessible controls, focus management, visible labels, reduced-motion support, and responsive layouts.
- Added `tools/build.py` and generated the self-contained, offline `index.html` with every data and image asset embedded.
- Added usage, regeneration, attribution, and save-format documentation to `README.md`.
- Corrected imported status handling for National Dex entries 800–807.
- Verified `file://` operation in Edge at desktop and 390×844 mobile viewports with no horizontal overflow or browser exceptions.
- Smoke-tested all 60 location sections, 807 sidebar rows, status cycling and persistence, Form Dex promotion, search, valid/invalid imports, drawer behavior, and embedded map visibility.
- Passed source extraction validation, generated-file freshness checks, Python compilation, HTML/JSON checks, LSP diagnostics, and repository-wide static diagnostics with no blocking findings.
- Replaced internal “blocker” terminology with clear regular-encounter progress labels.
- Reworked the interface into a dark, green encyclopedia theme inspired by Bulbapedia's information hierarchy without copying its layout.
- Displayed the bundled Photonic Sun / Prismatic Moon title artwork in the application header.
- Replaced technical and ambiguous UI terms with Catch now, Track forms, Backup, Restore, Chance, When / where, and explanatory SOS labels.
- Changed phone encounter tables into stacked cards and extended the Pokédex drawer layout through portrait-tablet widths.
- Made `data/encounters.json` the sole encounter transcription and reduced the extraction utility from 2,512 to 349 lines.
- Re-extracted all PDF assets to confirm deterministic output and repeated desktop, 820px tablet, and 390px phone smoke tests with no overflow or browser exceptions.
- Made selected-Pokémon details automatically return to view even after choosing an entry far down the Pokédex list.
- Expanded known-place links with island, location, encounter group, Catch now/Return later availability, and wild/SOS encounter type.
- Added a clear no-direct-location message instead of inventing evolution paths absent from the source data.
- Replaced ordinary status-click full-page rebuilding with targeted button and progress updates while retaining full renders for location transitions and bulk state changes.
- Preserved unrelated location and Pokédex DOM nodes during status changes and reduced the representative Edge smoke timing from roughly 66 ms to 5 ms without adding Preact.
- Pinned selected-Pokémon details above the scrolling Pokédex list, preserved the selected row and scroll position, and capped long detail panels at 45% of the viewport.
- Added a pinned, reproducible vanilla Pokémon Sun data generator and canonical 57-location, 269-group, 771-row encounter snapshot.
- Restored day/night rates from datamined Sun tables, retained normalized methods and SOS data, and corrected source disagreements at Verdant Cavern, Blush Mountain, Mount Lanakila, Vast Poni Canyon, and Poni Plains.
- Added a one-click Prismatic Moon ↔ Pokémon Sun mode switch with shared species/form progress, active-mode location links and totals, and location preservation where IDs overlap.
- Migrated browser saves and backups to schema v2 with a persistent mode setting while accepting existing v1 data losslessly.
- Reused accurate location screenshots in Sun mode while omitting mod-specific numbered and island maps.
- Verified pinned-source reproducibility, encounter-rate invariants, v1 migration, invalid restore safety, rapid switching, shared progress, 57/60 mode-specific location counts, desktop/tablet/mobile layouts, and offline browser operation with no exceptions.
- Added canonical Pokémon Moon, Ultra Sun, and Ultra Moon encounter datasets from checksum-pinned table dumps and PokeAPI versions 28–30.
- Replaced the two-mode button with a five-mode dropdown while retaining shared progress, overlapping locations, and remembered selection.
- Added distinct Prismatic Moon, Sun, Moon, Ultra Sun, and Ultra Moon themes that restore with the selected mode.
- Added small Pokémon sprites to location encounter rows and SOS ally controls by reusing the embedded icon atlas.
- Verified all five mode datasets, pinned-source checks, version-exclusive forms, theme restoration, cross-mode restore/reset synchronization, desktop/tablet/mobile layouts, and offline operation with no browser exceptions.
- Increased location-table sprites from 28×21 to 36×27 pixels while preserving the native atlas frames' 4:3 proportions.
- Standardized Pokédex and encounter-table sprites at their native 40×30-pixel atlas frame size.
- Replaced the monolithic HTML/Python UI builder with Vite 8, strict TypeScript, Preact, and Preact Signals.
- Split the frontend into typed data, domain, signal-state, UI action, component, and global style modules with working component and CSS HMR.
- Added a production publisher that emits and audits one minified `index.html` containing all CSS, JavaScript, JSON, and 72 images for network-free `file://` use.
- Preserved save schema v2, v1 migration, deterministic backups, five game modes, fine-grained status updates, location navigation, accessibility, and responsive layouts.
- Declared and clean-environment-tested the Python tooling dependencies in `requirements-dev.txt`.
- Added Vitest domain coverage, dual Vite/standalone Playwright parity tests, and pinned GitHub Actions CI.
- Verified strict types, seven domain tests, ten browser tests, canonical data, generated-file freshness, blocked-network standalone operation, and component HMR without a page reload.
- Added compact colored type markers and child-friendly SSS–F grades to all 807 Pokédex rows, with ordinary final-evolution grade inheritance for unevolved Pokémon.
- Added form-specific types and grades to selected Form Dex details and historical November 2019 Gen VII OU usage context to grade tooltips.
- Added a checksum-pinned Pokémon Showdown data generator and offline validation for the generated Pokédex details snapshot.
- Added type markers and grade badges to guide Pokémon and SOS allies, with compact separate ❌/✅/👁️ status buttons placed before each Pokémon.
- Expanded inherited-grade tooltips to show the Pokémon's own non-inherited tier alongside the evolution source and historical usage.
- Added a direct Bulbapedia link to each selected Pokédex entry.
- Added clickable Generation VII evolution paths with level, item, trade, friendship, move, and special-condition methods for Pokémon without a direct encounter in the selected game mode.
- Made Pokémon names in guide and SOS rows open their Pokédex details, revealing the desktop sidebar or mobile drawer automatically.
