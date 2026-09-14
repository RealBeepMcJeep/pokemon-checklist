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

## Milestones

### 1. Repository documentation and remote

- [ ] Connect and push `main` to the private Gitea repository.
- [ ] Add a concise README with usage and regeneration instructions.

### 2. Source dataset

- [ ] Snapshot National Dex 001–807 names and Gen VII menu icons.
- [ ] Extract and normalize every location, encounter group, rate, level, condition, SOS ally, note, and explicitly named form from the PDF.
- [ ] Extract the PDF location screenshots.
- [ ] Classify encounter groups as regular or Return later.
- [ ] Validate species names, location order, encounter rates, references, and image coverage.
- [ ] Save normalized source data as JSON.

### 3. Application

- [ ] Build the responsive location checklist and expandable sections.
- [ ] Build the searchable desktop/mobile Pokédex sidebar and location links.
- [ ] Implement shared species status, completion counts, and first-incomplete navigation.
- [ ] Implement optional Form Dex tracking.
- [ ] Implement localStorage, reset, versioned export, and replace-only import.
- [ ] Add accessible controls, keyboard operation, and reduced-motion support.

### 4. Self-contained build and verification

- [ ] Generate one self-contained `index.html` with embedded data and image assets.
- [ ] Add the smallest runnable dataset/state checks.
- [ ] Verify direct `file://` use on desktop and mobile-sized layouts.
- [ ] Run diagnostics and final repository checks.
