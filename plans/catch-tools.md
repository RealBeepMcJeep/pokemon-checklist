# Tools + documented Gen VII catch model

Approved scope: subordinate header Tools dialog, relative QR archive / experimental links,
inline offline capture calculator. English only, existing Preact/theme controls, no dependencies,
no new save keys or schema changes. All calculator inputs are component-local and ephemeral.
Stable review handles: `#tools-toggle`, `#tools-panel`, `#catch-calculator`.

## Decisions and accuracy boundary

- Native dialog provides modal focus containment, Escape and return focus; the calculator is
  outside the sticky header and scrolls inside a viewport-contained dialog.
- Shared keyboard / pointer combobox filters local names and ball labels. Editing to an invalid
  value removes the result immediately. Default Pikachu / Poké Ball is explicit.
- Approximate percent HP uses H=percent, M=100; exact mode accepts positive integer HP;
  Set 1 HP switches to exact mode. Major status checkboxes are mutually exclusive.
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
