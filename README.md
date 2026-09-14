# Alola Wild Checklist

A dependency-free wild Pokémon checklist for the supplied Generation VII location guide and vanilla Pokémon Sun. It covers National Dex 001–807, chronological island/location sections, encounter rates, SOS allies, optional forms, and a searchable Pokédex in a responsive dark encyclopedia layout.

## Use it

Open [`index.html`](index.html) directly in a browser. It is self-contained and works from `file://`; no server, package manager, CDN, or network connection is needed.

Use the **Mode** button to switch between Photonic Sun / Prismatic Moon and vanilla Pokémon Sun in one step. The current location is retained when both modes contain it; Pokémon and form progress is shared. Sun mode uses its own encounters and omits the mod guide's numbered maps.

Select a Pokémon's name in the Pokédex to show every known location in the active mode, including its island, encounter group, availability, and whether it is a wild encounter or SOS ally. The source data does not contain evolution paths, so the app says so instead of guessing when no direct location is listed.

Status buttons cycle **None → Caught → Seen → None**. Only Caught counts toward location and overall progress. The browser saves species statuses, tracked forms, and the selected mode in versioned local storage (`pokemon-checklist-state-v2`). Existing v1 browser saves and backup files migrate without changing progress. **Backup** downloads deterministic JSON; **Restore** validates the complete file before asking to replace the current checklist. If storage is unavailable, changes remain visible until the tab closes.

## Build and validate

From the repository root:

```text
python tools/extract_reference.py --validate
python tools/build_sun_encounters.py --check
python tools/build.py
python tools/build.py --check
python -m py_compile tools/build.py tools/build_sun_encounters.py tools/extract_reference.py tools/build_icons.py
```

`data/encounters.json` and `data/encounters-sun.json` are the canonical mode datasets. To re-extract the PDF images, use `python tools/extract_reference.py --extract-assets`. To refresh the pinned Pokémon name snapshot, use `--refresh-pokemon`.

`python tools/build_sun_encounters.py` regenerates the Sun snapshot from pinned source revisions and requires network access; normal builds remain fully offline. Direct encounter tables come from the pinned [Pokémon Sun encounter-table mirror](https://gist.github.com/RichardPaulAstley/42fbabe24250969f22d18fe8b919c520), while the pinned [PokeAPI repository](https://github.com/PokeAPI/pokeapi/tree/4b82c204ddd19ecb8eda2ea044ccb59e222b721c/data/v2/csv) supplies normalized area, method, SOS, Island Scan, berry-pile, and postgame records. Representative Sun tables were checked against Bulbapedia's [Blush Mountain](https://bulbapedia.bulbagarden.net/wiki/Blush_Mountain), [Mount Lanakila](https://bulbapedia.bulbagarden.net/wiki/Mount_Lanakila), [Vast Poni Canyon](https://bulbapedia.bulbagarden.net/wiki/Vast_Poni_Canyon), and [Poni Plains](https://bulbapedia.bulbagarden.net/wiki/Poni_Plains) pages.

Run `python tools/build.py` afterward; `--check` verifies both data structures, references, stable IDs, categories, assets, atlas dimensions, embedded-resource completeness, script-safe escaping, external-resource absence, and generated `index.html` freshness.

## Attribution and disclaimer

Photonic Sun / Prismatic Moon encounter data and location screenshots/maps come from `references/Wild Pokemon Locations.pdf`. Vanilla Sun data uses the pinned sources described above; reused scenic screenshots come from the same guide, while mod/Ultra-only numbered maps are excluded. Pokémon names are a snapshot of the English PokéAPI species-name data. The icon atlas is generated from the PokéAPI sprites Generation VII menu icons; its license notice is preserved in `references/PokeAPI-sprites-LICENCE.txt`. Image contents are copyright The Pokémon Company and respective rights holders.

This is a private, personal, non-commercial fan project. It is not affiliated with, endorsed by, or sponsored by Nintendo, Game Freak, The Pokémon Company, PokéAPI, or the guide author. Do not redistribute assets or use this project commercially without checking the applicable rights.
