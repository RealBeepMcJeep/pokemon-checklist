# Held items: a story-role guide, not a global strength ranking

The read-only companion produces an overview, five six-member item cards, JSON, a cited Markdown report and ZIP. It consumes the existing acquisition-checked five-team report; it does **not** change teams, scores, app UI, saves, sync or capture calculations. Personal artifacts stay outside git.

## How the judgments work

The letters are editorial **within a matching story role**, not tournament tiers, measured damage comparisons or win rates. Availability is separate from usefulness:

- **A — reusable role defaults:** Leftovers for sustain, Black Sludge for Poison holders, Thick Club for Cubone/Marowak, and Wide Lens for accuracy utility **if obtained**. These are not interchangeable universal upgrades.[1][3]
- **B — flexible or replenishable:** Muscle Band / Wise Glasses for the matching attack category, Expert Belt for super-effective hits, Rocky Helmet for contact-punishing battles, and suitable one-use berries. Do not use contact punishment on a catching utility Pokémon.[1]
- **C — specialize first:** Choice items, Life Orb, Assault Vest, Focus Sash, status orbs, weather rocks and seeds. Move locking, recoil, prohibited status moves, activation conditions, consumability and confirmed individual ability/move setup matter.[1][2]
- **X — separate decisions:** Eviolite while a Gen VII evolution remains; Light Ball for Pikachu, not Raichu; training/economy gear; bag-use evolution items; Mega Stones and Z-Crystals. Do not turn these into generic final-team combat recommendations.[1][3][9]

Current choices are conditional collection/quest opportunities at the **last owner-confirmed first-island-complete / about-L30 / Tauros / TM54 horizon**, not proof of held-item inventory, learned moves, individual abilities, sex, forms or later progression. Berry and quest acquisition below is a labeled stock-USUM fallback where the retained Standard documents do not override it; it is not verified hack-engine behavior.[5][6][9]

The single documented free Wise Glasses reward is allocated to **at most one member per alternative party**, using highest planned base Sp. Atk with stable source-order ties. This is an editorial resource allocation, not measured battle optimization. Other members use berry alternatives until additional copies are obtained; the five parties are alternatives, not five simultaneous inventories.[5][9]

## Access and costs

- **Route 2, Melemele:** Oran is a random berry-pile result; Sitrus is the first berry in a large pile. Collection is free, daily and RNG-dependent, with a possible guarding encounter. These berries are consumed on activation and need replacing.[1][6]
- **Trainers’ School:** after Hala, hear the Big Wave Beach rumor and solve the school mysteries at night for one free Wise Glasses. Quest completion and current possession are unrecorded.[5]
- **Hau’oli specialist mart:** the creator lists the Power training equipment here. Money is required; no numeric hack price is supplied. Power Anklet halves Speed and is not a generic combat-speed upgrade.[1][9]
- **Battle Royal Dome, Royal Avenue, Akala:** the creator lists many useful held items for BP and says prices are reduced. **Exact hack prices are undocumented; do not copy vanilla 48 BP.** This is later than the last-confirmed Melemele horizon.[8][9]
- **Mt. Hokulani, Ula’ula:** the creator lists Thick Club and Light Ball at the specialist mart. Money and later location access are required; exact prices are undocumented.[9]
- **Wide Lens:** the Route 1 gift is **Sun/Moon-only**, not USUM. This tool does not supply verified Standard wild-held access/rates, so it never calls that item obtainable now.[7]

Popular competitive items can be unsuitable for the planned story set. Choice items are not endorsed as a flexible default for a status-containing plan. Assault Vest disables status moves. Hawlucha seeds require actual matching terrain plus a confirmed Unburden strategy; Pelipper rain gear requires real rain generation, not merely Water typing. Hidden abilities are never inferred from an item’s prevalence.[1][2]

## Source-era and statistical contract

The fixed Showdown revision is `e7aee8d9ccc983c59c5608929773249adca16b8f`. Its root item file already contains Gen VIII entries. The parser therefore merges **Gen VII overrides and filters generation**, rather than trusting root data alone. The pinned Gen VII Mago Berry description conflicts with its callback: the callback and inherited threshold establish half-HP healing at quarter HP, with its nature condition; the report exposes the stale-description warning. This is source-backed simulator metadata, not a native/hack-engine bit-exact claim.[1][3]

Generation-specific ability overrides are also admitted alongside the item sources.[2][4]

Six independent November-2019 snapshots are pinned by URL and SHA-256: OU 1695; UU, RU, NU, PU and Ubers 1630. BL tiers map explicitly to the closest legal higher format; `(PU)` uses PU. There is no silent cross-format fallback. Unsupported tiers or absent species remain missing evidence.[10][11][12]

Each species’ item share is `item weight / sum of that species’ Items weights`. Weighted denominator, raw species appearances and total format battles remain separate. These shares are not species usage, raw-frequency confidence estimates, correlated builds, battle outcomes or win rates. Unknown/later-generation item IDs, invalid weights, altered hashes and mismatched format/cutoff metadata fail closed.[13][14][15]

The four previously retained usage snapshots were independently downloaded and byte-identical during research. New PU/Ubers sources live only in an isolated item add-on; they do not change the selector’s ability-weight sources or results. All retained hack documents are validated against their manifest before analysis. Source URLs are recorded in [`data/held-item-sources.json`](../data/held-item-sources.json); exact source hashes are in the generator’s immutable specifications.

## Run it

Use the project’s existing Python/rendering environment and Node dependencies. Explicitly bootstrap the independent source cache once:

```bash
python tools/held_item_cards.py bootstrap --cache <verified-core-cache>
```

This installs the four item/ability JavaScript sources and six detailed usage snapshots under `<cache>/held-items-gen7/`. It does not alter the existing five-source Showdown contract. Normal report generation does not silently download or repair data.

Generate from the **latest valid** enriched team report and the full source sets captured during its selection:

```bash
python tools/held_item_cards.py generate \
  --team-report <private-gallery>/story-options.json \
  --source-observations <private-gallery>/selector-observations.json \
  --uid <uid> --cache <verified-core-cache> \
  --output-dir <new-private-output-directory>
```

The observations file contains `initial_source_sets` with complete sorted integer lists `caught`, `seen` and `starred`; those three lists may alternatively be supplied directly. They must agree with the team report and two fresh read-only account reads. Same-count trades, Seen changes or favorites changes invalidate the input. If selection rules or ranking sources changed, regenerate upstream first: this is an item companion, not a second selector or permission to trust stale party choices.

Outputs: `held-overview.png`, `held-team-01.png` through `held-team-05.png`, `held-items.json`, `held-items.md`, `held-items.zip` and `run-status.json`. Images use the existing sprite atlas/palette and fail on essential-text overflow. Every new output directory is private; success requires six valid images, a complete archive and final source-set equality. Failure returns nonzero and retains its JSON and `traceback.log`, not a partial-success receipt.

For a clearly archival offline redraw, without claiming fresh ownership:

```bash
python tools/held_item_cards.py redraw \
  --report-json <private-run>/held-items.json --output-dir <new-private-directory>
```

## Verification and limits

Portable tests cover ID joins/generation filtering/overrides, the Mago discrepancy, isolated cache admission/corruption, normalized usage and malformed inputs, explicit format mapping, item/species/move restrictions, current versus later access, one-free-copy allocation, Gen VII-only Eviolite eligibility, full-set invalidation, complete rendering and failure diagnostics. One additional test uses the real verified add-on when installed; CI explicitly skips that cache-dependent test rather than pretending to download or execute it.

Local gates passed: 203 Vitest, 330 Python with zero skips, 13 Node and 214 browser tests. All 389 source item IDs/names/generations/effects match independent Node exports, apart from the explicitly tested Mago prose correction. A fresh current-main upstream gallery matched the prior parties/scores exactly and used zero native searches while retaining its fresh account read. The actual item CLI produced all six PNGs, a cited report and verified archive with two fresh complete account reads; one-free-copy allocation and private file modes were checked. Exact publication, committed-main execution and final delivery are release acceptance steps, not an implication of a feature-branch push. No native damage model, item inventory database, automatic progression inference or app feature is implied.

## Sources

[1] https://raw.githubusercontent.com/smogon/pokemon-showdown/e7aee8d9ccc983c59c5608929773249adca16b8f/data/items.js — Pinned Gen VII items
[2] https://raw.githubusercontent.com/smogon/pokemon-showdown/e7aee8d9ccc983c59c5608929773249adca16b8f/data/abilities.js — Pinned Gen VII abilities
[3] https://raw.githubusercontent.com/smogon/pokemon-showdown/e7aee8d9ccc983c59c5608929773249adca16b8f/data/mods/gen7/items.js — Generation 7 items overrides
[4] https://raw.githubusercontent.com/smogon/pokemon-showdown/e7aee8d9ccc983c59c5608929773249adca16b8f/data/mods/gen7/abilities.js — Generation 7 abilities overrides
[5] https://bulbapedia.bulbagarden.net/wiki/Trainers%27_School_%28Alola%29
[6] https://bulbapedia.bulbagarden.net/wiki/Alola_Route_2
[7] https://bulbapedia.bulbagarden.net/wiki/Wide_Lens
[8] https://bulbapedia.bulbagarden.net/wiki/Battle_Royal_Dome
[9] https://drive.google.com/file/d/12YsIQwV_nTphy4-2k7VhuThEeD8qwrOo/view
[10] https://www.smogon.com/stats/2019-11/chaos/gen7ou-1695.json
[11] https://www.smogon.com/stats/2019-11/chaos/gen7uu-1630.json
[12] https://www.smogon.com/stats/2019-11/chaos/gen7ru-1630.json
[13] https://www.smogon.com/stats/2019-11/chaos/gen7nu-1630.json
[14] https://www.smogon.com/stats/2019-11/chaos/gen7pu-1630.json
[15] https://www.smogon.com/stats/2019-11/chaos/gen7ubers-1630.json
