# Pokémon Checklist TODO

Completed items move to `changelog.md`.

## Specification

- Deliver one self-contained `index.html` that works when opened directly.
- Bundle all CSS, JavaScript, encounter data, location screenshots, and Pokémon icons; require no runtime network access.
- Include National Dex species 001–807 in one shared collection state.
- Cycle status on click: **None → Caught → Seen → None**.
- Present PDF locations in chronological order under expandable island/location sections.
- Count ordinary direct encounters, including day/night variants, toward location completion.
- Display fishing, surfing, bubbling, SOS, weather, and explicitly gated encounters as **Return later**; these do not block location completion.
- Initially open the first incomplete regular location.
- Provide a searchable mobile sidebar. Each Pokémon expands direct and optional location links.
- Support optional Form Dex tracking for permanent forms explicitly identified by the PDF. Form progress is separate; catching a form marks its species caught, never the reverse.
- Persist one save in browser localStorage.
- Export versioned user-state JSON. Import replaces current progress after confirmation.
- Keep editable extracted JSON and images as source assets while generating one portable application file.

## Outstanding work

### Mobile performance

- [ ] Repeat the startup, mode-switch, and restore profiling on real phone hardware; the current numbers come from 4× CPU throttling at a phone viewport.
- [ ] Cut the first Pokédex open: mounting the 807 rows still blocks the main thread for ~0.8 s at 4× throttling on the first open after a page load (later toggles cost ~90 ms, and closing no longer stalls at all). Windowing or virtualising the list is the lever, and it needs the "807 rows in the DOM" assertions rewritten with keyboard and accessibility care.

### Game modes

- [x] Confirm reproducible sources for Pokémon Sun, Moon, Ultra Sun, and Ultra Moon.
- [x] Generate canonical vanilla encounter JSON with forms, rates, levels, methods, conditions, SOS encounters, and provenance.
- [x] Reconcile vanilla areas with stable guide locations and omit misleading mod-specific numbered maps.
- [x] Replace the two-mode button with a five-mode native dropdown while preserving overlapping locations.
- [x] Persist the selected mode without changing shared Pokémon/form progress or the v1 save migration.
- [x] Apply a distinct accessible theme to each mode and restore it with the saved selection.
- [x] Reuse the embedded atlas for small sprites beside location-table Pokémon.
- [x] Update known-place links, progress totals, build validation, documentation, and attribution for all modes.
- [x] Test data invariants, migration, mode switching, backup/restore, desktop, tablet, mobile, and offline operation.

### Stable Pokédex scrolling

- [x] Keep selected Pokémon details pinned above the scrolling Pokédex list.
- [x] Preserve the current list position and existing rows when a Pokémon is selected.
- [x] Bound long location lists so they do not cover the entire drawer.
- [x] Update the browser regression check for sticky details without a jump to 001.

### Targeted status updates

- [x] Stop rebuilding all 60 locations and 807 Pokédex rows for an ordinary status change.
- [x] Update matching status buttons, location totals, and overall totals in place.
- [x] Keep full renders for area transitions, forms, restore, and reset.
- [x] Add a browser regression check that unaffected DOM nodes survive a status click.

### Pokédex location discovery

- [x] Bring the selected Pokémon's guide locations into view after any Pokédex-row click.
- [x] Show island, location, encounter group, availability, and SOS/wild encounter type.
- [x] Explain when the guide contains no direct location rather than guessing an evolution path.
- [x] Add a browser regression check for selecting a Pokémon far down the Pokédex.

### Dark encyclopedia polish

- [x] Apply a dark Bulbapedia-inspired visual theme without copying its layout.
- [x] Replace remaining developer/game-mechanic shorthand with plain-language labels.
- [x] Turn encounter tables into readable cards on phones and keep the drawer layout on portrait tablets.
- [x] Display the bundled Photonic Sun / Prismatic Moon title artwork instead of embedding it unused.

### Simplification

- [x] Make `data/encounters.json` the canonical dataset and remove its duplicate Python transcription.
- [x] Retain only the source-image extraction, data validation, and optional Pokémon-name refresh tooling.

### Multi-device sync and control from chat

Spec and options: `plans/multi-device-sync.md`. Nothing here is scheduled; the open decisions in
that file come first.

- [ ] Settle the artifact question: whether sync rides in a second opt-in build or the network-free publisher rule changes.
- [ ] Settle the conflict model: per-record timestamps merged field by field, tombstones for cleared statuses.
- [ ] Choose a backend once the free-tier and Google sign-in facts are verified, and record the migration and backup story for it.
- [ ] Extend the save to schema v4 carrying sync metadata, migrating v1-v3 saves losslessly.
- [ ] Sign in with Google restricted to the owner's account, with the checklist stored per account.
- [ ] Sync statuses, form progress, stars and mode across phone, tablet and PC, merging offline edits on reconnect.
- [ ] Add a Telegram command channel: caught, seen, trade, star, unstar, status, team, linked to the account by a one-time code.
- [ ] Keep export/import and Reset semantics correct once the data lives in two places.

### Verification

- [x] Rebuild the self-contained `index.html` and repeat desktop, tablet, and phone smoke checks.
- [x] Run final source, build, diagnostics, and repository checks.
