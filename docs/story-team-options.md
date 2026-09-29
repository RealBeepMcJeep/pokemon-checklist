# Local story-team suggestions and pixel cards

This is a **read-only local analysis tool**, not a checklist feature. It reads the current synced caught/favorite records, uses the project's verified Gen VII Showdown cache, and prints five teams of five battlers plus a fixed Butterfree catcher:

```bash
python tools/team_synergy.py --story-options --uid <account-uid> \
  --cache <verified-showdown-cache>
python tools/story_team_cards.py --uid <account-uid> \
  --cache <verified-showdown-cache> --output-dir <output-directory>
```

The second command reruns the selector and writes `team-01.png` through `team-05.png` plus `story-options.json`. It needs Pillow from `requirements-dev.txt`. Each of the six Pokémon on a card gets four move targets with move type and an acquisition gate. To redraw an **enriched** snapshot without Firebase *or* the data cache:

```bash
python tools/story_team_cards.py --report-json <story-options.json> \
  --output-dir <output-directory>
```

One image per option. Each image shows the six slots, the current and endgame pixel sprites cropped from `assets/gen7-icons.png`, owned → final names, evolution path, final Dex number/types/tier, anchor/favorite flags, evolution count, score, and caveats. Sprites are credited in `references/PokeAPI-sprites-LICENCE.txt` (image contents © The Pokémon Company); the cards are personal-use reports, not hosted assets. An older snapshot without `moves`/`utility_moves` needs `--cache <verified-showdown-cache>` on its first redraw to add the checked move gates.

Move targets are curated preferences validated when first enriching the report against the **manifest-verified Prismatic Standard level-up table** (replacing vanilla level gates), the commit-pinned Gen VII move type/learnset data and known TM/tutor locations. Egg/event/transfer-only gates are rejected; the hack's replaced TM slots are not treated as their vanilla moves. Earlier-stage moves say when to teach them before evolving; a listed level below an evolved form's attainable level is not presented as a normal level-up gate. The saved JSON contains the resolved targets, allowing the same recommendations to be re-rendered later. Routes and levels on the cards are goals, not a claim that an item or move is already owned; `LATER` and `ENDGAME` denote progression gates. No gameplay checkpoint or individual move/ability/item inventory is recorded.

**Scope and caveats:** OG-151-only means an OG species was actually caught **and** the endpoint is OG; no-OG means neither the caught stage nor endpoint is OG, with Butterfree explicitly exempt as the fixed utility. The other three options are mixed. A family ban (default Litten, Magnemite, Riolu, Abra), unknown sex/form and an unowned second branch are not loopholes. Current favorites receive a small bonus but are not locked. The scoring combines final-form tier/usage, STAB *type potential*, defensive switches, evolution opportunity and diversity; it does **not** verify a legal four-move set or guarantee that a held item or hidden ability is available. The Gen VII atlas supports Dex #1–807 only. Butterfree sleeps targets but cannot False Swipe.

The selector brute-forces a **bounded, pruned candidate pool of at most 24 endpoints per category**; do not call its ranking a global optimum across every possible line. It does not write caught/favorite statuses. For the existing competitive `team_synergy.py` mode, omit `--story-options` and the historical move-scoring behavior remains unchanged.
