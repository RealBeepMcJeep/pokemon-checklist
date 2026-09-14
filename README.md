# Alola Wild Checklist

A dependency-free wild Pokémon checklist for the supplied Generation VII location guide. It covers National Dex 001–807, chronological island/location sections, encounter rates, numbered grass maps, SOS allies, optional forms, and a searchable Pokédex in a responsive dark encyclopedia layout.

## Use it

Open [`index.html`](index.html) directly in a browser. It is self-contained and works from `file://`; no server, package manager, CDN, or network connection is needed.

Select a Pokémon's name in the Pokédex to show every known guide location, including its island, encounter group, availability, and whether it is a wild encounter or SOS ally. The source data does not contain evolution paths, so the app says so instead of guessing when no direct location is listed.

Status buttons cycle **None → Caught → Seen → None**. Only Caught counts toward location and overall progress. The browser saves species statuses, tracked forms, and settings in versioned local storage (`pokemon-checklist-state-v1`). **Backup** downloads deterministic JSON; **Restore** validates the complete file before asking to replace the current checklist. If storage is unavailable, changes remain visible until the tab closes.

## Build and validate

From the repository root:

```text
python tools/extract_reference.py --validate
python tools/build.py
python tools/build.py --check
python -m py_compile tools/build.py tools/extract_reference.py tools/build_icons.py
```

`data/encounters.json` is the canonical encounter transcription. To re-extract the PDF images, use `python tools/extract_reference.py --extract-assets`. To refresh the pinned Pokémon name snapshot, use `--refresh-pokemon`. Run `python tools/build.py` afterward; `--check` verifies data structure, references, stable IDs, categories, assets, atlas dimensions, embedded-resource completeness, script-safe escaping, external-resource absence, and generated `index.html` freshness.

## Attribution and disclaimer

Encounter data and location screenshots/maps come from `references/Wild Pokemon Locations.pdf`, a Photonic Sun/Prismatic Moon wild-location guide. Pokémon names are a snapshot of the English PokéAPI species-name data. The icon atlas is generated from the PokéAPI sprites Generation VII menu icons; its license notice is preserved in `references/PokeAPI-sprites-LICENCE.txt`. Image contents are copyright The Pokémon Company and respective rights holders.

This is a private, personal, non-commercial fan project. It is not affiliated with, endorsed by, or sponsored by Nintendo, Game Freak, The Pokémon Company, PokéAPI, or the guide author. Do not redistribute assets or use this project commercially without checking the applicable rights.
