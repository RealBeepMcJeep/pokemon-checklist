# Approved goal: reverse-engineered Gen VII QR toolkit and standalone gallery

User approval: research and build the reverse-engineering route FIRST, then publish a separate qr.html beside the unchanged checklist on GitHub Pages. Explain that Gen VII games support older-generation species; distinguish shared QR format from regional-Pokédex applicability and special event eligibility. Do not claim stock SM and USUM are generally incompatible.

## Scope and order

1. Implement/exercise ordinary Dex QR decoding, cryptographic verification/decryption, structured field inspection and ordinary-code generation using published PKHeX/SciresM evidence and real archive QR images. Preserve raw binary bytes. Test tamper rejection and source vectors before the gallery consumes anything.
2. Import both paginated Bulbagarden SM/USUM QR categories; save attributed originals, exact source URLs, category memberships and content hashes; decode/verify every file. Report source counts, unique images/payloads/species/forms, mismatches and unsupported formats. Categories are provenance, not compatibility restrictions. Unknown fields remain unknown. Document source-derived validation separately from console acceptance, generation boundaries and special-event signing limits.
3. Build a separate self-contained qr.html from verified records with the existing pixel sprite atlas, canonical Gen VII names/dex/types/forms, genuine QR images, search/type/game-applicability filters and a full-viewport scan viewer opening from each card or QR. No runtime network, login, Firebase, private roster, checklist changes or CDN. Preserve attribution and explicit form labels; base-sprite fallback must be truthful. Keep event codes separate if independently verified; do not block the ordinary toolkit/gallery on decoding an unsupported event family.
4. Browser/test/source review, publish, read-back verify exact deployed bytes, and deliver the live URL plus HTML/screenshot and research findings. Main must be clean/up-to-date after integration.

## Implementation contract

- Reproducible Python manual CLI; cryptography, QR transport decoder and encoder are justified pinned build/dev dependencies, not browser/runtime dependencies. Use the established unittest suite and tests-first RED/GREEN slices.
- Proposed modules: tools/qr_codec.py (protocol + CLI), tools/build_qr_catalog.py (source import/verified manifest), tools/build_qr_gallery.py and tools/qr_gallery_template.html (standalone compiler/template). Keep one authoritative manifest under references/qr-codes/ with originals and provenance; no live fetch during ordinary rebuild/check.
- Import at most four simultaneous requests, finite per-request timeouts, bounded retries for transient failures, successful-file checkpoints. Explicit refresh only; offline verified read/rebuild otherwise.
- Decode all archive records rather than guessing filenames. Strictly reject truncated/tampered/unsupported payloads where verification is claimed. Report unknown families explicitly.
- Generated code labels say locally generated and cryptographically/transport verified, not official or console-tested. Imported vs generated are separate provenance. Generate ordinary older-generation and Gen VII examples and verify decoder round-trip and field IDs. Do not claim arbitrary Pokémon delivery or event generation.
- QR symbol quiet zone, aspect ratio and raw payload are invariant. No rounded/recolored/overlaid/cropped code modules. Full-viewport modal is primary; native fullscreen is optional. Touch targets >=44px, focus lock/restoration, Escape/close, previous/next, scroll lock, mobile no overflow.
- Card filter game meaning must be explicit: known regional-Dex applicability or source-library membership, not a blacklist of shared payloads. All Pokémon from generations I–VII may be candidates, while species introduced after a particular game and game-specific events need independent eligibility.
- Reuse assets/gen7-icons.png (32 columns, 40x30 frames, IDs 1..807), as cropped img elements; no per-row atlas data URL in CSS computed styles. Derive types from canonical project data/pinned Gen VII form metadata; no invented type/form joins.

## Acceptance checkpoints

- [x] Fetch clean baseline; local main matches origin/main; deployed checklist bytes match origin/main:index.html; baseline npm run check passes (184 app tests, 147 Python tests, 11 Node tests).
- [ ] M1 Protocol: real PNG raw decode + signature/decryption + field parsing; mutation/truncation tests; generated binary PNG round-trips; attributed source fixtures; user-facing format/compatibility report.
- [ ] M2 Catalogue: complete paginated import, inventory reconciliation, all-record statuses, offline hash verification/rebuild, game/form/type evidence.
- [ ] M3 Gallery: real full catalogue renders; standalone and HTTP search/type/catalogue filters; whole-card/QR viewer; keyboard/touch close/navigation; no overflow at 360/390/1440 widths; no external resource requests, including offline operation.
- [ ] Screenshot software-decode checks of both an actual card and large viewer reproduce original bytes; visual PNG review. Explicitly distinguish these from unperformed physical-console tests.
- [ ] Combined project gates and both browser projects pass; build/check reproducibility; committed checklist index.html remains byte-identical to baseline unless an explicit unrelated build-stamp normalization is necessary (avoid it).
- [ ] Reviewed commits integrated on main and pushed; CI and Pages for exact main commit green; deployed qr.html and checklist read-back hashes match committed artifacts; deployed-browser smoke passes; main worktree clean.

## Cut deliberately

No new SPA, framework, backend, accounts, catch-progress sync, QR injection patch, live image hotlinking, game-ROM redistribution, exhaustive enumeration of generic QR symbols, or speculative claim of complete game-validator reverse engineering. Do not expand these without a user request or an observed blocker.

## Sources / prior plan

Prior detailed proposal: /opt/data/.hermes/plans/2026-10-02_073619-pokemon-qr-gallery.md.
Skills: pokemon-checklist references/qr-codes.md; portable-html-artifacts; test-driven-development.
PKHeX inspected source clone: /opt/data/cache/scratch/pokemon-qr-pkhex at 542111fc8584ff29c9d1455553b8acd0e1f8a59a. Patch source: /opt/data/cache/scratch/pokemon-qr-patches.
Seed API: https://archives.bulbagarden.net/w/api.php ; source categories https://archives.bulbagarden.net/wiki/Category:Pok%C3%A9mon_Sun_and_Moon_QR_codes and https://archives.bulbagarden.net/wiki/Category:Pok%C3%A9mon_Ultra_Sun_and_Ultra_Moon_QR_codes.
Published fields/reverse engineering: https://gbatemp.net/threads/pokemon-sun-and-moon-hacking-qr-codes.448369/ . Never treat source inspection alone as exercised software or console acceptance.
