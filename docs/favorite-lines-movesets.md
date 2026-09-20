# Favorited lines — evolutions, movesets, and what to actually do in a run

Scope: the six favorited species in the owner's account (Zigzagoon, Wingull, Ralts, Zorua,
Bunnelby, Salandit) through their final evolutions, with the competitive data that applies to
his game. Compiled 2026-09-18.

**Everything here is Gen 7 (SM/USUM).** The game is **Prismatic Moon (Standard)** — see
"Which hack variant" below — and the competitive data is **Smogon November 2019, Gen 7**,
which is the last meaningful snapshot for those games. No Gen 8/9 data applies.

## Where the data comes from (and how to refresh it)

| Dataset | URL | Size |
|---|---|---|
| Learnset per species (move + method + level) | shared cache `learnsets.js` | commit-pinned; SHA-256 in `tools/showdown_data.py` |
| Move definitions (power/type/accuracy) | shared cache `moves.js` | commit-pinned; SHA-256 in `tools/showdown_data.py` |
| Base stats + ability slots | shared cache `pokedex.js` | commit-pinned; SHA-256 in `tools/showdown_data.py` |
| Ranking (species usage %) | `smogon.com/stats/2019-11/gen7ou-1695.txt` | 73,934 B |
| **Per-set detail (what % of sets run a move)** | `smogon.com/stats/2019-11/moveset/gen7ou-1695.txt` | 1,007,136 B |
| Same, per tier | `.../moveset/gen7uu-1630.txt` / `gen7ru-1630` / `gen7nu-1630` | 889 KB / 746 KB / 726 KB |
| Raw weighted counts (chaos JSON) | `smogon.com/stats/2019-11/chaos/gen7ou-1695.json` | 18,302,232 B |

No scraping is involved: these are published datasets, downloaded with `curl`.

**Cross-check that this is the same source the app already uses:** `data/pokedex-details.json`
records `source: { showdownCommit: e7aee8d9…, usage: "gen7ou-1695, November 2019" }`, and
Pelipper's usage there (6.9682) matches the OU ranking file exactly.

### Two format traps

1. **The moveset/chaos files are indented by one space** (` | Pelipper  |`). An anchored regex
   starting `^|` matches nothing.
2. **Chaos JSON stores raw weighted counts, not percentages.** Normalising by the block total
   gives a *moveslot share* (each move ≤ ~25%). The `moveset/*.txt` files already give the
   intuitive figure: **% of that species' sets running the move**. Quote the latter.

## Which hack variant

Prismatic Moon (author Buffel Saft) patches **Ultra Moon**; Photonic Sun patches Ultra Sun.
It ships in two variants:

- **Rebalanced** — changes base stats, types, abilities, learnsets, TM/tutor compatibility and
  some move effects. Vanilla competitive data does **not** apply.
- **Standard** — omits the Pokémon and move changes, but still applies the hack-wide QoL rules,
  including **egg moves learnable by levelling** and alternate evolution methods for trade
  evolutions.

The owner runs **Standard**, so vanilla USUM data is a reasonable baseline. For the six lines
here, the hack's evolution document records **no changes** to their evolution methods.

Known gap: the app's single `photonic-prismatic` mode (`src/domain.ts:33`) does not distinguish
Standard from Rebalanced. Worth splitting if Rebalanced is ever played.

## The six lines

### Zigzagoon #263 → Linoone #264 (level 20)

- Competitive: **UU, 2.46% usage.** Extreme Speed **99.9%**, Belly Drum **99.8%**,
  Stomping Tantrum **95.8%**, Seed Bomb **88.9%**. Ability **Gluttony 98.3%**
  (Figy Berry 82.0%). Spread Adamant 148/248/8/0/88/16.
- Why Gluttony: it triggers the berry at 50% HP, which is exactly what Belly Drum costs.
- **Availability (verified in the shared `learnsets.js` cache):**
  - **Extreme Speed — a Gen 7 EGG MOVE on Zigzagoon** (`["8E","7E","3S1"]`). It is *not* a
    Linoone level-up move and *not* a USUM tutor move (Linoone's own entry lists only the Gen 6
    event code `6S0`). Check the **base form's** learnset, not the evolution's — this was
    misread twice before being verified.
  - Belly Drum — level 43 (Linoone), 37 (Zigzagoon).
  - Stomping Tantrum, Seed Bomb — USUM tutors.
- In Standard, egg moves can be learned by levelling, so breeding may not even be required.

### Wingull #278 → Pelipper #279 (level 25)

- Competitive: **OU, 6.97% usage** (best of the six). U-turn **82.6%**, Scald **81.9%**,
  Roost **78.3%**, Hurricane **67.1%**, Defog **51.0%**. **Drizzle 99.9%.** Damp Rock 93.2%.
  Spread Bold 248/0/252/0/8/0.
- It is a rain **support** Pokémon: Drizzle sets rain, which also makes Hurricane perfectly
  accurate.
- Availability: Hurricane — **level 1 relearner** on Pelipper. Roost/Scald/U-turn — TMs.
  Defog — USUM tutor.
- **Drizzle is ability slot 1, not hidden.** Wingull's slot 1 is **Hydration**, so a Hydration
  Wingull becomes a Drizzle Pelipper. No hidden ability required.

### Ralts #280 → Kirlia #281 (level 20) → Gardevoir #282 (level 30) or Gallade #475 (Dawn Stone, male Kirlia only)

- **Gardevoir — RU, 9.34%.** Moonblast **98.1%**, Psyshock **70.6%**, Healing Wish **49.6%**,
  Trick **47.0%**. **Trace 94.5%** (slot 1). Choice Scarf 69.4%. Timid 252 SpA/Spe.
- **Gallade — NU, 2.95%.** Close Combat **58.7%**, Knock Off **55.9%**, Zen Headbutt **48.3%**,
  Swords Dance **47.5%**. **Justified 76.9% — that is Gallade's HIDDEN ability.** Psychium Z.
  Jolly 252 Atk/Spe.
- Availability: Moonblast / Healing Wish (relearner), Psyshock (TM), Trick (tutor);
  Close Combat / Psycho Cut (relearner), Knock Off / Zen Headbutt (tutors), Swords Dance (TM).

### Zorua #570 → Zoroark #571 (level 30)

- Competitive: **UU, 0.87%.** Dark Pulse **61.4%**, Flamethrower **60.3%**, Sludge Bomb
  **44.3%**, Sucker Punch **33.3%**. **Illusion 100%** (its only ability). Choice Specs 26.9%
  or Band 25.1%. Timid 46.5% / Jolly 26.6% — the ladder splits special and physical.
- Availability: Sucker Punch — **Gen 7 egg move on Zorua** (`7E`), event-only on Zoroark.
  Sludge Bomb — **not legally available in Gen 7** (Gen 6 event / Gen 8+ TM), so a
  Gen-7-legal Zoroark cannot run it despite the usage figure.
- Illusion means Zoroark shows as your last party member until it takes a hit; party order matters.

### Bunnelby #659 → Diggersby #660 (level 20)

- Competitive: **UUBL, 0.75% usage**, OU-level set. Earthquake **99.3%**, Quick Attack
  **87.8%**, Swords Dance **52.0%**, Frustration/Return ~**50/41%**. **Huge Power 98.9%.**
  Choice Band 35.2% or Silk Scarf 30.1%. Adamant 252 Atk/Spe.
- **Huge Power is the HIDDEN ability.** Base Attack is only 56; the entire set is Huge Power
  doubling it. Without the hidden ability the set does not function.
- Availability: Earthquake (TM26 / level 57), Return (TM27), Quick Attack (level 7),
  Swords Dance (TM75 / relearner), Fire Punch (tutor).

### Salandit #757 → Salazzle #758 (level 33, FEMALE ONLY)

- Competitive: **RU, 10.19% usage.** Sludge Wave **86.8%**, Fire Blast **70.1%**, Nasty Plot
  **65.6%**, HP Grass **31.4%**. Corrosion **56.6%** / Oblivious **43.4%** (Oblivious is hidden).
  Poisonium Z 49.9%. Timid 252 SpA/Spe.
- Note the split: the Smogon RU set recommends **Oblivious** (Taunt immunity) while the ladder
  actually runs **Corrosion** slightly more. Both are defensible.
- Availability: Nasty Plot (relearner), Fire Blast / Sludge Wave (TMs), Dragon Pulse (tutor).
- **Only female Salandit evolve** — verified against Bulbapedia and the hack's evolution doc.

## Corrections this compilation produced

1. **ExtremeSpeed on the Zigzagoon line is a Gen 7 egg move.** Two earlier claims were wrong:
   mine ("Gen 6 event only, unobtainable") because I read Linoone's entry instead of
   Zigzagoon's; and a research subagent's ("USUM move tutor") which the learnset data does not
   support.
2. **Showdown's current data carries later-generation ability slots.** Gallade shows
   "Sharpness" on master, which is a Gen 9 ability and does not exist in Gen 7. Use the Gen 7
   usage data for abilities, not the current data file.
3. Chaos JSON figures are weighted counts; quoting them as percentages overstates every move by
   roughly 4×.
