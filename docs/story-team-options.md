# Local story-team suggestions and pixel cards

A **read-only local analysis tool**, not a checklist feature. Reads current synced caught/favorite records with verified Gen VII Showdown data. Every party has **Butterfree first**, followed by five battlers. A caught species record is checklist-level evidence, not proof that an unevolved individual remains in the box.

## Five independent objectives

1. **OG:** owned starting stage and proposed stages/endpoints must be original-151 Kanto species. Then type synergy > uncaught evolution entries > practical endgame viability.
2. **Non-OG:** starting stage and proposed stages/endpoints outside the original 151; Butterfree exempt. Same priorities.
3. **Mixed:** no Dex restriction or mandatory generation mix. Same priorities.
4. **Pokédex:** each battler has a remaining ordinary-level-up path adding at least one uncaught entry. No required stone, trade, friendship, held item or unconfirmed sex/stat/form gate. New entries > synergy > viability. A plan can stop at a level-evolved intermediate before a non-level gate; show that actual endpoint. Unseen intermediates count even when a later final is caught.
5. **Best:** practical endgame viability > synergy; no evolution bonus. No hidden abilities or breeding-only acquisition assumed. A tier/usage heuristic, **not** a battle simulator, Nash equilibrium or unbeatable-party claim.

Shared members and identical parties are allowed; never force weaker selections for variety. Favorites break exact objective ties. Old family exclusions are cleared; explicit `--off-limits` bans whole families. Unknown forms and individual evolution requirements are not loopholes.

## Running and rendering

```bash
python tools/team_synergy.py --story-options --uid <account-uid> \
  --cache <verified-showdown-cache>
python tools/story_team_cards.py --uid <account-uid> \
  --cache <verified-showdown-cache> --output-dir <output-directory>
```

The renderer reruns selection and writes `team-01.png` through `team-05.png` plus private `story-options.json`. Pillow is in `requirements-dev.txt`. Four editorial move targets per Pokémon show types/acquisition gates. To avoid repeating selection and redraw an enriched snapshot without Firebase **or** data-cache access:

```bash
python tools/story_team_cards.py --report-json <story-options.json> \
  --output-dir <output-directory>
```

Unenriched snapshots require `--cache` once. Personal snapshots/images stay outside public git. Phone cards show owned → planned sprites/names, actual evolution gates, Dex/type/tier, anchor/favorite labels, objective scores and caveats. Intermediate Pokédex plans do not acquire a final evolution's combat strength.

Sprites crop `assets/gen7-icons.png` directly; IDs outside #1–807 are rejected. Credit: `references/PokeAPI-sprites-LICENCE.txt` (image contents © The Pokémon Company). Pillow rendering rejects clipped essential names, evolution paths, moves, types and acquisition gates.

## Evidence and limitations

Manifest-verified Prismatic Moon **Standard** overrides pinned vanilla Gen VII evolution/acquisition data. Story coverage is **STAB-type potential**, not a real four-move set. Quality-independent synergy includes defensive switches, duplicated types/common weaknesses and Butterfree. Tier/usage inform viability with explicit heuristic caution for hidden-dependent builds; **ladder ability popularity is not a measured fraction of ordinary-build combat strength**. The checklist records no individual ability, sex, form, current level or owned items.

Editorial move targets are independently validated against Standard level-ups (which **replace**, not supplement, vanilla levels), pinned move types/learnsets and documented TM/tutor locations. Reject egg/event/transfer-only gates and replaced vanilla TM slots. Label moves to learn before evolution, reminder requirements and late gates. `LATER` and `ENDGAME` denote goals, not present inventory. Butterfree sleeps targets but cannot False Swipe; another party member must provide safe HP control.

Enriched JSON freezes acquisition labels for repeatable offline redraws. To refresh labels, remove `utility_moves` and each member's `moves` from a **private copy**, then rerender with the verified cache. Preserve the original. Legacy snapshots describe historical inputs, not current ownership.

Reports expose source caught IDs, objective rules and search scope. Full-pool results are optimal only within the declared deterministic model/input assumptions. Disclose any candidate pruning and excluded counts. Before delivery, re-read caught IDs and compare against the snapshot; regenerate on change. No workflow command modifies statuses/favorites. Omit `--story-options` for the unchanged competitive mode.

## Six catch-utility options on one card

```bash
python tools/catch_utility_card.py --uid <account-uid> \
  --cache <verified-showdown-cache> --output-dir <output-directory>
python tools/catch_utility_card.py --report-json <catch-utility.json> \
  --output-dir <offline-output-directory>
```

Writes `catch-utility.png` in the same six-row pixel-art style and a private `catch-utility.json` snapshot. These are six **curated catching prospects**, including uncaught options, not a six-member battle party or the raw vanilla catcher score. The list is sorted by the base species' first unconditional regular encounter in the ordered Prismatic documentation: Butterfree (Caterpie), Kricketune (Kricketot), Gallade (Ralts), Smeargle, Breloom (Shroomish), Parasect (Paras). This is **first catch location**, not readiness of a complete four-move set. Encounter/time restrictions and level, TM, stone and setup gates remain visible.

Every option has four distinct, acquisition-checked moves and exactly one sleep move. Butterfree cannot learn False Swipe and needs an HP-control partner; the other five can provide both. Kricketune's Sing is less reliable. Gallade requires a male, a Konikoni Dawn Stone and delaying Ralts evolution for Hypnosis L37. Breloom needs Spore on Shroomish L40 before evolving. Paras can use Spore L22 before evolving at L24. Avoid Effect Spore on Parasect/Breloom: it can accidentally poison the intended catch; Dry Skin/Poison Heal are ordinary slots, not SOS-only hidden abilities. A Capsule to switch between normal slots is sold after two trials; ownership labels do not prove an individual's sex, ability, level or available items.

Smeargle is the specialist **setup project**, not a Route-2-ready complete catcher: all four moves come from separate Sketch copies and checked donors. It uses Spore / False Swipe / Soak / Mean Look rather than duplicate sleep/paralysis moves. The card labels donor species, levels and locations (and Iki Town for the donor's False Swipe TM); Sketch reappears at L11/21/31/.../91. Soak handles Grass-type powder immunity and Ghost-type False Swipe immunity, but does not remove sleep-blocking abilities. No set requires breeding, eggs or hidden-ability farming. Combat moves supplement the sets only when no further critical catching control is included; do not use them to perform safe 1-HP reduction.

The generator validates the Standard replacement level lists, pinned move types/learnsets, ordinary ability slots and encounter provenance, rejecting unavailable sources or clipped labels. The JSON freezes those checks for offline redraws. Images and live roster snapshots remain outside git; the checked test fixture removes all personal ownership data. No website, roster or favorite data is changed.
