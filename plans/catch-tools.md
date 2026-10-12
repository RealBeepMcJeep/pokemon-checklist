# Tools + documented Gen VII catch model

Approved scope: subordinate header Tools dialog, relative QR archive / experimental links,
inline offline capture calculator. English only, existing Preact/theme controls, no dependencies,
no checklist save/schema changes. Battle inputs are component-local and ephemeral; the
approved sprite-selector upgrade separately remembers only selected Pokémon/form and ball.
Stable review handles: `#tools-toggle`, `#tools-panel`, `#catch-calculator`.

## Decisions and accuracy boundary

- Native dialog provides modal focus containment, Escape and return focus; the calculator is
  outside the sticky header and scrolls inside a viewport-contained dialog.
- Selected names become inline keyboard/pointer autocomplete with sprites. Draft queries do
  not change the selected identity, odds or persistence; selection commits, and Escape/blur
  reverts the label. Default Pikachu / Poké Ball is explicit.
- Approximate percent HP above 1 uses H=percent, M=100. At the owner-approved 1%
  convenience endpoint, H=1 and M is the last entered valid maximum or an explicitly
  labeled 100-HP estimate. Exact mode accepts positive integer HP. Set 1 HP preserves
  the input mode; no species/level inference of maximum HP. Major status chips are exclusive.
- Conditional ball controls appear only when relevant. Turn 1 has zero elapsed turns.
  Repeated registrations and critical history are not inferred from currently-owned checklist
  records. Roto defaults off and is unavailable in SM. Game variant follows app game mode;
  the Photonic / Prismatic mode assumes USUM engine and stock personal data, not verified hack stats.
- Rate override is explicitly marked and accepts 0–255. It cannot override weight, speed or type.
  Trainer battles / fainted targets are excluded; this is not an encounter-availability lookup.
- The staged Q12 model follows the retained Dragonfly JavaScript worker, NOT the older Python CLI.
  It is not proved bit-exact USUM native code: JS double Math.pow differs from XY float32 powf,
  and the USUM executable / hack modifications have not been verified.
- Moon Ball applies to the six actual Moon Stone evolution targets, NOT every family member:
  Nidorina, Nidorino, Clefairy, Jigglypuff, Skitty, Munna. The approved brief's "families" wording
  is interpreted with this source restriction (worker lines 117–120 and retained Catch_rate table).
- Lure is fishing only, ×5 in Gen VII; Dive accepts surfing or fishing. Heavy adjusts rate before
  ball multiplier, with SM zero-rate bug vs USUM minimum 1. Ordinary balls penalized against UBs;
  Master bypasses only legal catchable inputs. Nest uses (41−level)/10 below 30 and staged rounding.

## Approved sprite-selector upgrade

- Desktop B2: stacked Pokémon and ball rows beside the battle-parameter column. Phones use
  the approved shared compact vertical layout. Catch chance stays prominent near the top,
  with numeric, text-tier and color feedback; compact chip borders keep 44px hit areas.
- Each selector draws previous/current/next icons through cropped atlas `<img>` elements.
  Neighbor clicks, keyboard left/right and real touch/mouse drags animate and wrap both ends,
  while native vertical scroll and reduced motion remain supported. The underlying 975-entry
  dataset stays intact; selectors show base species plus only forms whose selected-game stock
  catchRate differs from their base. Search and rail share that same numeric ID/form order.
  Remembered excluded forms visibly migrate to their own base. Retained forms label base-art
  reuse; a compact effective-rate badge occupies the existing caption. Search stays bounded.
- Only `{id, form, ball}` is persisted under `pokemon-checklist-catch-selection-v1`. This
  per-device key is separate from progress/backups/sync and does not remember battle values.
  Invalid or blocked storage falls back with a notice; choosing unavailable stock SM forms
  still reports the game-availability error rather than silently substituting another record.
- Ball art: 22 30×30 frames, eight columns, committed `assets/catch-balls.png`; raw cache and
  source hashes in `references/ball-sprites/`, PokéAPI/sprites commit
  `6e3e7c43e86db0e1b2277795cfee41b11e8df2a4` (same pin as Pokémon icons).
  `python tools/build_ball_sprites.py --check` checks hashes, dimensions and rendered
  freshness offline; `--refresh` explicitly downloads the pinned inputs. License attribution
  stays in `references/PokeAPI-sprites-LICENCE.txt`.
- Capture engine/data remain byte-identical. Exact/estimated HP, Set 1 HP, every conditional
  ball, historical critical history, Roto, override and detailed assumptions remain available.

## Reproducible data provenance

`tools/build_capture_data.py` uses stdlib only and verifies the three pinned SHA256 hashes before
extracting `data/capture.json`. Offline freshness is required by `npm run validate:data` and `check`.
Retained small resources: `data/reference/capture/{personal_sm,personal_uu,PersonalInfo7.cs}`.
PKHeX commit `542111fc8584ff29c9d1455553b8acd0e1f8a59a`, resources
`PKHeX.Core/Resources/byte/personal/personal_{sm,uu}` and schema
`PKHeX.Core/PersonalInfo/Info/PersonalInfo7.cs`.
84-byte records; speed at 0x03, types 0x06/07, rate 0x08, gender 0x12,
form pointer LE16 0x1c, count 0x20, weight LE16 0x26 (0.1 kg).
SM IDs stop at 802; USUM IDs stop at 807; never read SM alternate-form records as IDs 803–807.
Alternate forms map FormStatsIndex + form − 1. Alolan forms are labeled explicitly; selected
additional forms have labels, and remaining forms use honest personal-table form numbers.
Base stats are stock Gen VII types (not inherited final-evolution Showdown types).

Reference worker: https://www.dragonflycave.com/gen6capture-worker.js?v=2, retained verbatim
at `tools/tests/fixtures/dragonfly-worker.js`. Vitest executes its actual code in a VM and checks
HP / rate / status / Roto / historical-count boundaries. Mechanics and Roto/Nest source:
https://www.dragonflycave.com/mechanics/gen-vi-vii-capturing and
https://www.dragonflycave.com/update-archive/2018.
Source checkpoint: approved parent scratch formula audit, not a shipped native-engine claim.

## Verification

Vertical RED/GREEN logs and disposable screenshots belong outside the public repository in
`/opt/data/cache/scratch/catch-tools-build-qa/`. Browser suite runs both real HTTP Vite and the
rebuilt committed standalone artifact. Tests verify controls, responsive containment, invalid
selection / HP, local progress preservation and signed-out request silence. Parent owns independent
Claude Opus 5.5 high browser review, README/changelog, integration and deployment; builder does not push.

## Independent review corrections

The native Opus 5.5/high candidate review identified feedback below the fold, a scrolling Close
button and pointer-down selection interfering with touch scrolling. Compact feedback/errors now
stick below the Tools heading, while the full probability breakdown remains below the inputs.
Suggestions select on click and preserve native touch panning; related-target containment keeps
focus within the combobox without blur timers. Exact HP errors identify and mark the invalid field,
percentage-to-exact conversion preserves the estimate, and action buttons have 44px minimum height.
Regressions measure viewport rectangles and perform actual CDP touch drags followed by real taps
in both HTTP and standalone-file projects. Calculator math, reference data and save format are unchanged.
