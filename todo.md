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

### Pokémon Sun mode

- [ ] Confirm a reproducible vanilla Pokémon Sun encounter source and cross-check representative locations.
- [ ] Generate canonical Sun encounter JSON with forms, rates, levels, methods, conditions, SOS encounters, and provenance.
- [ ] Map Sun areas onto reusable islands, locations, and screenshots; hide Ultra/mod-only or misleading numbered maps.
- [ ] Add a one-click mode toggle that swaps encounter information while preserving the current location when possible.
- [ ] Persist the selected mode and migrate existing local saves/backups without changing shared Pokémon/form progress.
- [ ] Update Pokédex known-place links, progress totals, validation, build embedding, documentation, and attribution for both modes.
- [ ] Test data invariants, migration, rapid mode switching, backup/restore, desktop, tablet, mobile, and offline operation.

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

### Verification

- [x] Rebuild the self-contained `index.html` and repeat desktop, tablet, and phone smoke checks.
- [x] Run final source, build, diagnostics, and repository checks.
