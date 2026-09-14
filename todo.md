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

### Dark encyclopedia polish

- [ ] Apply a dark Bulbapedia-inspired visual theme without copying its layout.
- [ ] Replace remaining developer/game-mechanic shorthand with plain-language labels.
- [ ] Turn encounter tables into readable cards on phones and keep the drawer layout on portrait tablets.
- [ ] Display the bundled Photonic Sun / Prismatic Moon title artwork instead of embedding it unused.

### Simplification

- [ ] Make `data/encounters.json` the canonical dataset and remove its duplicate Python transcription.
- [ ] Retain only the source-image extraction, data validation, and optional Pokémon-name refresh tooling.

### Verification

- [ ] Rebuild the self-contained `index.html` and repeat desktop, tablet, and phone smoke checks.
- [ ] Run final source, build, diagnostics, and repository checks.
