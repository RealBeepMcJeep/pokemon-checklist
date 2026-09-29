# Changelog

## 2026-09-29

- Added a read-only story-team mode to the local team-synergy tool: Butterfree stays in the catching slot while five suggestions cover OG-151-only, no-OG-151 and three mixed battler lineups from the current caught roster. It shows owned-stage evolution paths and treats party favorites as preferences, not locks.
- Added a repeatable five-card image renderer using the project's Gen VII pixel-sprite atlas. Each phone-sized card labels the catcher, anchor and partners with Dex numbers, types, evolution paths, ranks and caveats; the saved JSON can be rendered again offline. No website or checklist save-format change.

## 2026-09-28

- Added one-tap **Undo** after changing a status, form or star, and after Reset or Restore. It floats at the bottom of the screen, above the phone Pokédex, works offline and signed in, puts back only what that change touched, and disappears if those Pokémon change elsewhere first.
- A change now counts as sent only once the server confirms it, so closing the page on a bad connection can no longer lose a tap that looked saved.
- Fixed sync letting an older change overwrite a newer one: an edit or a Reset made offline no longer replaces what another device or chat changed after it.
- Only one tab per account syncs; the others hand their changes, including Reset and Restore, to it, so two open tabs no longer undo each other's changes.
- Made Restore work while signed in: a confirmed restore now syncs and is logged, instead of being refused as a whole-checklist wipe forever.
- A saved checklist that cannot be read no longer hides a good one: the last good copy loads instead, and every unreadable copy is kept and can be downloaded. If nothing readable is left, a fresh checklist is shown and nothing is saved over the old one.
- Saving recovers by itself after a failed write, and messages no longer say "saved" when nothing was saved.
- Clearing a whole checklist by accident is held back and reported while every other change still syncs; Reset clears everything on purpose.
- A signed-in device shows the account's checklist right away, even offline; a tab opened before signing in elsewhere follows that sign-in; signing out says when changes had not been sent yet; a device that lost its sync records adds only what the account has never had and says so.
- Made the phone Pokédex drawer fill the screen even when a search leaves only a few rows.
- Stopped the chat helper reading a question as a command: "did I already get bulbasaur" used to mark Bulbasaur caught, and "have I got a pikachu yet?" failed on the trailing "yet". Questions now only report status, and "resetting my plan" no longer trips the reset guard.
- Let `pokemon_ops.py` take `--uid` after the subcommand, reported a skipped no-op write as not written rather than "verified", and derived the National Dex bound from `data/pokemon.json`.
- Fixed data-tool drift: the catcher tool now uses the shared TM and tutor location tables (its private copy had three entries under the wrong keys), one normaliser handles accents such as Flabébé, one tier order covers AG, and the vanilla-encounter generator keeps repeated species/rarity rows and tells the two Nidoran apart. Generated data is unchanged.
- Moved the Showdown cache to the same per-platform cache folder as the other generators, still finding an existing `~/.cache` copy; tools-test discovery and the artifact freshness check now behave the same on Windows and Linux.
- Corrected the README and docs on what CI checks and which generator needs the network.
- Made the Pokédex's "Known places in this mode" links open the right location first; before, they did nothing unless that location was already open.
- Kept the Pokédex working after resizing a window or rotating a tablet across the phone/desktop layout switch; it could become visible but unclickable, or hidden but still focusable. A drawer left open on a phone now closes when the layout becomes desktop.
- Counted "Forms caught" against the forms the current mode can actually offer (14 in Sun and Moon, 17 in the Ultra games, 48 in Prismatic Moon) instead of all 54 across every game, so the counter can be completed.
- Gave status, star and ally buttons a full 44-pixel tap target on phones, without changing desktop rows.
- Selecting a Pokémon now updates only the two affected rows instead of all 807, and search no longer re-sorts and re-normalises every name on each keystroke.
- Locked the page behind the phone Pokédex drawer so it cannot scroll underneath, and kept keyboard focus inside the drawer while it is open.
- Stopped the game-mode menu from zooming the page on iPhone, sized full-height panels for Safari's moving toolbar, and kept the desktop Pokédex aligned when the header wraps onto extra lines.
- Darkened three grade badge colours that were too light to read, and made status buttons say what pressing them will change the status to.
- Added a **Catch next** card to the Pokédex: before you pick a Pokémon it lists the uncaught catch-now Pokémon at the next unfinished location, each with its status button and a jump to that location, and it updates as you catch them. **← Catch next** above any selected Pokémon brings it back.
- Showed where a Pokémon can be caught in the other four game modes, including for Pokémon with no wild spot in the current mode.
- Showed the evolution path even when the Pokémon also has a wild location, so a caught Pichu or Feebas still says how to finish its line.
- Added a home-screen icon, theme colour and web-app manifest, all embedded in the one file, so **Add to Home Screen** on iPhone or Android gives a real icon and a full-screen app that still works offline.
- Kept Popular moves from breaking the Pokédex panel if a move were ever missing from its table.
- Fixed a sync bug that could undo other devices' changes. The engine sent every difference between this device's save and the server's copy as local edits, so a change arriving from another device looked like one to reverse, and incoming changes were never written to the device's save. A browser whose old saved copy was blank therefore showed an empty checklist and "64 to send" against a full account; the whole-account guard refused the send, and no data was lost. Only edits recorded on the device are now sent, incoming changes are saved as they arrive, and a sign-in recovers only edits made since that device's last confirmed copy, never a set that would clear the whole account.
- Fixed sign-in on Safari: the first press loaded Google's sign-in helper before opening its window, about 3.5 seconds after the click, so Safari blocked the popup; the app then fell back to a full-page redirect, which cannot return a session to a `github.io` page from `firebaseapp.com` under Safari's storage rules, so it came back signed out. The helper now loads first, and if the browser blocks the window the button becomes **Continue with Google**, whose press opens the popup within the click itself (1 ms in WebKit).
- Removed the full-page redirect fallback, which cannot work on this site in Safari, Firefox's strict mode, or Chrome without third-party cookies.
- Said so when a first sign-in shows an account's existing checklist instead of this device's: the device's own progress is kept and returns on signing out, where before it silently looked deleted.
- Added engine tests proving a first sign-in never loses data: an empty account adopts this device's progress, and an account that already has a checklist is neither cleared nor clears this device's own save.

## 2026-09-27

- Added **Popular moves** to every Pokédex entry: the eight moves competitive players ran most for each of the 439 final evolutions (434 with usage data), with how the game teaches each one. Unevolved Pokémon list their final evolutions' moves; Ubers and every tier through LC are covered, each from its own tier's November 2019 Smogon file.
- Worded egg moves per mode: bred in the vanilla games, learned by level-up in Photonic Sun / Prismatic Moon. Moves players ran that Gen 7 cannot teach are marked as not obtainable.
- Generated the data with a new offline `tools/build_moves.py` (`--refresh` downloads missing pinned files, `--check` detects staleness) on the move report's own ranking, now shared as functions in `moveline.py`; `validate_data.py` checks the file's shape and cross-references.
- Stored facts rather than wording, keyed by dex number with a named learnset profile, so forms and a Rebalanced variant can be added without a schema change; move details live once in a shared table, keeping the embedded data to ~300 KB.
- Pinned the Smogon Ubers moveset file, matched Smogon's straight-apostrophe names (Farfetch'd), and read `(PU)` species from the PU file instead of whichever tier listed them first.
- Fixed the full-page sign-in fallback returning signed out: Firebase's initial "signed out" report cleared the flag that tells the reloaded page to look for its session.
- Signed a disallowed Google account straight back out of Firebase, and stopped the sign-in success notice from overwriting the "not on the list" message.
- Gave the sync controls their own full-width row on phones; they were squeezed into one third of the button grid, clipping the status and spilling the sign-in button at 320 px. Errors now wrap in full, the signed-in address shows on phones, and the status is coloured by state.
- Showed "Offline" instead of "Synced" (or "3 to send") while the database connection is down.
- Stopped the first Pokédex open from freezing a phone: the list now mounts 30 rows per animation frame instead of all 807 in one render. The longest main-thread block on first open fell from a median of ~1,100 ms to ~120 ms at 4× CPU throttling and a phone viewport; every row is still in the DOM once mounting finishes.
- Made search hide non-matching rows instead of unmounting them, so clearing a search no longer rebuilds the list: its longest block fell from a median of ~775 ms to ~100 ms, and typing a first letter stays under the 50 ms long-task threshold.
- Memoised each row's contents so a new chunk or a keystroke only toggles a row's `hidden` attribute; status, star, and selection still update each row through its own signals.
- Added a browser check that Pokédex rows survive a search and its clearing as the same DOM nodes, and made the search tests count only visible rows.
- Corrected the sync status document: a signed-in Reset propagates atomically with a single `reset` log event carrying its before-image; only undo is outstanding.

## 2026-09-19

- Consolidated active analysis tools on one commit-pinned, integrity-checked Pokémon Showdown cache and one small shared text parser; ordinary commands no longer download unpinned Showdown data.
- Made icon and vanilla encounter regeneration offline by default through external, hash-verified source caches. Network access now requires explicit `--refresh`, icon sources are commit-pinned, cache refreshes are atomic, and downloads have finite timeouts.
- Removed duplicate Firebase reads and Python subprocess/text interfaces from the catcher and team tools; one command now uses one account snapshot and structured in-process results.
- Bounded exhaustive team search at 100,000 combinations so larger flags fail before performing unbounded work while the default 42,504-combination search remains available.
- Reused the frontend's immutable validation indexes, cached each location's immutable catch-now rows, and removed unused state/sync exports and migration-only interfaces.
- Retained the canonical Prismatic Moon references and added a commit-pinned, SHA-256-verified Pokémon Showdown data contract for reproducible move, Pokédex, learnset, and type data.
- Added and hardened move-card, catcher, roster, team-building, synergy, and chat-checklist tools, including branch-aware move reports, opt-in Roto Catch calculations, and canonical evolution-line selection.
- Built Stage 2's repository side in `tools/pokemon_ops.py`: validated mark (caught / seen / none), trade and evolve pairs, exact favourites, and list workflows, each sent as one minimal patch and verified by reading it back. Wiring it into Hermes remains.
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
- Set up the Firebase project on the Spark plan with billing off: a Realtime Database, Google sign-in (a popup, falling back to a full-page redirect), and authorized domains, with an email allowlist enforced by the database's security rules.
- Restated the offline promise as "no request unless signed in" and enforced it with a browser test that records every request and fails on anything but `data:`, `file:` or localhost while signed out, on desktop and mobile user agents.
- Kept the player's save untouched: sync bookkeeping lives in its own document, and signed-in saves are namespaced per account.
- Derived pending work from the last server-confirmed document instead of queueing operations, so a retry is idempotent and a server-side change is never mistaken for an unpublished local edit.
- Added the chat channel's phrase parser (`tools/pokemon_chat.py`), which resolves a species and emits the exact record keys sync writes, and a dependency-free service-account client (`tools/firebase-admin-rest.mjs`) that refuses a key stored inside the repository.

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
