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

- [ ] Repeat the startup, mode-switch, restore, and Pokédex-open profiling on real phone hardware; the current numbers come from 4× CPU throttling at a phone viewport. Virtualising the Pokédex list remains the next lever only if chunked mounting still stutters there.

### Multi-device sync and control from chat

Spec, decisions and research: `plans/multi-device-sync.md` and `plans/research/`. Stage 1 (sync) is
built and deployed. Stage 2's repository side is built: `tools/pokemon_chat.py` parses the verbs,
`tools/pokemon_ops.py` runs the mark, trade/evolve, favourites and list workflows, and
`tools/firebase-admin-rest.mjs` writes them with a service-account key kept outside the repository.

- [ ] Undo from the sync log for the chat tooling (the app's own one-step Undo is built); Reset and Restore log entries carry before-images.
- [ ] Several tabs of one account on one device: date a non-syncing tab's edits when they were made rather than when the syncing tab notices them, hand over only that tab's own edits (not its whole save), keep or report a Reset handed over just before the syncing tab closes, and stop held clears from being sent once the account gains a record.
- [ ] Decide whether lowering a species below a caught form should be blocked.
- [ ] Add the log's retention and compaction: roughly 500 events or 90 days, with Reset exempt so a reset stays undoable.
- [ ] Stage 2: wire the chat tooling into Hermes and verify it end to end against the live account. Needs the service-account key at `/opt/data/firebase/service-account.json` (or `FIREBASE_SERVICE_ACCOUNT`) on the Hermes host; its presence there cannot be checked from this repository.
- [ ] Test the two offline flows on real devices, and confirm two signed-in browsers show the same checklist.
- [ ] Confirm sign-in on Safari (macOS and iOS) now that the popup opens straight from the click. If Safari still refuses, serve Firebase's `/__/auth/` helper from the app's own origin (a custom domain or the `realbeepmcjeep.github.io` root site) and point `authDomain` at it.

## Movelists and game variants (2026-09-18)

- [ ] Consider splitting the `photonic-prismatic` mode into Prismatic Moon **Standard** vs
  **Rebalanced**. Not started: `src/types.ts` still defines one `photonic-prismatic` mode with no
  variant distinction (see `docs/favorite-lines-movesets.md`'s "Known gap"). The encounters data
  assumes one variant; Rebalanced changes base stats, types, abilities, learnsets and TM
  compatibility, so vanilla Gen 7 competitive advice would be wrong there if it were split.
- Popular moves are built for Standard (`data/moves.json`, `source.profile: "gen7"`). A Rebalanced
  variant would be a second profile of the same file shape once its learnsets are sourced.
- Popular moves cover species only; tracked forms (Alolan finals, Lycanroc forms) could be added
  under form keys such as `"26:alolan"` without a schema change.
