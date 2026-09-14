# Changelog

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
