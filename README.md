# Alola Wild Checklist

A self-contained wild Pokémon checklist for the supplied Generation VII location guide and all four vanilla Alola games. It covers National Dex 001–807, chronological island/location sections, encounter rates, SOS allies, optional forms, and a searchable Pokédex in a responsive dark encyclopedia layout.

## Use it

Open [`index.html`](index.html) directly in a browser. It is self-contained and works from `file://`; no server, package manager, CDN, or network connection is needed.

Use the **Game mode** dropdown to switch among Prismatic Moon, Pokémon Sun, Pokémon Moon, Pokémon Ultra Sun, and Pokémon Ultra Moon. Each mode has its own color theme and encounters. The current location is retained when possible, Pokémon and form progress is shared, and the last mode is restored next session. Vanilla modes omit the mod guide's numbered maps.

Select a Pokémon's name in the Pokédex to show every known location in the active mode, including its island, encounter group, availability, and whether it is a wild encounter or SOS ally. Each Pokédex row also shows colored type dots and a child-friendly SSS–F grade; unevolved Pokémon inherit the strongest grade from their ordinary final evolutions. Hover a grade for its frozen November 2019 Gen VII source tier, inherited Pokémon's own tier, and OU usage context. When form tracking is enabled, selected tracked forms show their own types and grades. The encounter source does not describe acquisition by evolution, so the app does not invent location links when no direct encounter exists.

Status buttons cycle **None → Caught → Seen → None**. Only Caught counts toward location and overall progress. The browser saves species statuses, tracked forms, and the selected mode in versioned local storage (`pokemon-checklist-state-v2`). Existing v1 browser saves and backup files migrate without changing progress. **Backup** downloads deterministic JSON; **Restore** validates the complete file before asking to replace the current checklist. If storage is unavailable, changes remain visible until the tab closes.

## Develop

Install Node 22 and the locked dependencies, then start Vite:

```text
npm ci
npm run dev
```

The development server provides Preact component HMR and live CSS updates. It serves source modules and assets normally for fast iteration; the one-file constraint applies to production builds.

## Build and validate

Install the Python tooling dependencies with `python -m pip install -r requirements-dev.txt`. From the repository root:

```text
npm run build
npm run check
npx playwright install chromium
npm run test:e2e
python tools/extract_reference.py --validate
python tools/build_vanilla_encounters.py --check
python -m py_compile tools/validate_data.py tools/build_vanilla_encounters.py tools/extract_reference.py tools/build_icons.py
```

Vite builds to temporary `dist/index.html`; `tools/publish.mjs` verifies it is the only output, rejects external resources and runtime network APIs, and copies it to the tracked root `index.html`. `npm run build:check` rebuilds without changing the root file and fails when that committed artifact is stale. CSS, JavaScript, JSON, the icon atlas, and every location image are inlined for direct `file://` use.

`npm run check` runs strict TypeScript checking, Vitest domain tests, canonical Python data validation, and the production build/freshness audit. Playwright runs the same UI parity checks against both the Vite server and the generated standalone file, with network access blocked for the latter. GitHub Actions enforces these checks for pull requests and `main`.

`data/encounters.json` and the four `data/encounters-{game}.json` files are the canonical mode datasets. To re-extract the PDF images, use `python tools/extract_reference.py --extract-assets`. To refresh the pinned Pokémon name snapshot, use `--refresh-pokemon`. `python tools/build_pokedex_details.py` regenerates the type, inherited-grade, form, and usage snapshot from checksum-pinned Pokémon Showdown sources; it requires network access, while normal builds remain offline.

`python tools/build_vanilla_encounters.py` regenerates all four vanilla snapshots from pinned sources and requires network access; normal builds remain fully offline. Direct tables come from the pinned [Pokémon Sun mirror](https://gist.github.com/RichardPaulAstley/42fbabe24250969f22d18fe8b919c520), SciresM's Pokémon Moon Pastebins (`YjNi4Qdk` and `HKEVPUYX`), and the pinned [Ultra Sun](https://gist.github.com/SciresM/a539739085e24af55dffdf443cb70eb2) and [Ultra Moon](https://gist.github.com/SciresM/deecdcf5fc49fc8191a29d111643c6b6) dumps. SHA-256 checks guard every table download. The pinned [PokeAPI repository](https://github.com/PokeAPI/pokeapi/tree/4b82c204ddd19ecb8eda2ea044ccb59e222b721c/data/v2/csv) supplies normalized area, method, SOS, Island Scan, berry-pile, and postgame records.

## Attribution and disclaimer

Photonic Sun / Prismatic Moon encounter data and location screenshots/maps come from `references/Wild Pokemon Locations.pdf`. Vanilla Alola data uses the pinned sources described above; reused scenic screenshots come from the same guide, while mod-specific numbered maps are excluded. Pokémon names are a snapshot of the English PokéAPI species-name data. Types and source tiers come from the pinned MIT-licensed Pokémon Showdown Gen VII data, and usage is from Smogon's November 2019 Gen VII OU statistics; the displayed SSS–F grades are this project's simplified, child-friendly mapping. The icon atlas is generated from the PokéAPI sprites Generation VII menu icons; its license notice is preserved in `references/PokeAPI-sprites-LICENCE.txt`. Image contents are copyright The Pokémon Company and respective rights holders.

This is a private, personal, non-commercial fan project. It is not affiliated with, endorsed by, or sponsored by Nintendo, Game Freak, The Pokémon Company, PokéAPI, or the guide author. Do not redistribute assets or use this project commercially without checking the applicable rights.
