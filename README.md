# Alola Wild Checklist

A self-contained wild Pokémon checklist for the supplied Generation VII location guide and all four vanilla Alola games. It covers National Dex 001–807, chronological island/location sections, encounter rates, SOS allies, optional forms, and a searchable Pokédex in a responsive dark encyclopedia layout.

## Use it

Open [`index.html`](index.html) directly in a browser. It is self-contained and works from `file://`; no server, package manager, CDN, or network connection is needed.

Use the **Game mode** dropdown to switch among Prismatic Moon, Pokémon Sun, Pokémon Moon, Pokémon Ultra Sun, and Pokémon Ultra Moon. Each mode has its own color theme and encounters. The current location is retained when possible, Pokémon and form progress is shared, and the last mode is restored next session. Vanilla modes omit the mod guide's numbered maps.

Select a Pokémon's name in the guide or Pokédex to open its Pokédex details, showing every known location in the active mode, including its island, encounter group, availability, whether it is a wild encounter or SOS ally, and a direct Bulbapedia reference link. Each Pokédex row also shows colored type dots and a child-friendly SSS–F grade; unevolved Pokémon inherit the strongest grade from their ordinary final evolutions. Hover a grade for its frozen November 2019 Gen VII source tier, inherited Pokémon's own tier, and OU usage context. When form tracking is enabled, selected tracked forms show their own types and grades. When a Pokémon has no direct encounter in the active mode, the Pokédex shows a clickable Generation VII evolution chain with levels or special methods leading to it when one exists, without inventing a location link.

Status buttons cycle **None → Caught → Seen → None**. Only Caught counts toward location and overall progress. The browser saves species statuses, tracked forms, starred Pokémon, and the selected mode in versioned local storage (`pokemon-checklist-state-v3`). Existing v1 and v2 browser saves and backup files migrate without changing progress, and an upgraded save is rewritten under the current key while the older key is left untouched. **Backup** downloads deterministic JSON; **Restore** validates the complete file before asking to replace the current checklist. If storage is unavailable, changes remain visible until the tab closes.

Star any Pokédex row to pin that Pokémon above the rest of the list; click the star again to release it. Starred entries stay in National Dex order among themselves, still float to the top inside search results, are kept in backups, and are cleared by Reset along with progress.

Opening the checklist in more than one tab keeps them in sync: a change made in one tab appears in the others immediately, with a notice, and without reloading. This covers statuses, tracked forms, the selected mode, Restore, and Reset. Tabs of the `file://` copy share a local-storage origin in Chromium and sync as well, but browsers are free to isolate local files, so treat cross-tab sync as a served-page guarantee rather than a documented offline one.

**Sign in to sync** is optional and off until you press it. Unsigned/offline mode remains fully local: it never contacts the network and the checklist still works from `file://` without a server. While signed in, a change on one device appears on the others on its own; a change made offline is sent when the connection returns; and if two devices change the same species, the one that reaches the server later wins. The first sign-in on a device adopts the progress already on that device rather than discarding it, and signing out returns that device to its own checklist without deleting anything. Each account keeps its own separate checklist, because progress belongs to a person.

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
python tools/build_icons.py --check
python tools/build_vanilla_encounters.py --check
```

Vite builds to temporary `dist/index.html`; `tools/publish.mjs` verifies it is the only output, rejects external scripts, stylesheets, iframe/object/embed/media/track resources, CSS `url(...)` and `@import` references, source maps, and unresolved build tokens, and copies it to the tracked root `index.html`. Data URLs and fragment-only references remain valid embedded resources. `npm run build:check` rebuilds without changing the root file and fails when that committed artifact is stale. The no-network guarantee is behavioural and enforced by a browser test rather than by that check: while signed out the artifact may not so much as *attempt* a request to anything other than `data:`, `file:` or localhost, on a desktop or a mobile user agent. CSS, JavaScript, JSON, the icon atlas, and every location image are inlined for direct `file://` use.

`npm run check` runs strict TypeScript checking, Vitest, the production build/freshness audit, the full Python tool suite plus chat self-test, and deterministic Node tool tests. Playwright runs the same UI parity checks against both the Vite server and the generated standalone file, with network access blocked for the latter. GitHub Actions enforces these checks for pull requests and `main`.

`data/encounters.json` and the four `data/encounters-{game}.json` files are the canonical mode datasets. To re-extract the PDF images, use `python tools/extract_reference.py --extract-assets`. To refresh the pinned Pokémon name snapshot, use `--refresh-pokemon`. `python tools/build_pokedex_details.py` regenerates the type, evolution, inherited-grade, form, and usage snapshot from checksum-pinned Pokémon Showdown sources; it requires network access, while normal builds remain offline.

The source regenerators are offline by default. Their verified raw inputs live outside the repository in the platform cache directory (`%LOCALAPPDATA%/pokemon-checklist/` on Windows, `$XDG_CACHE_HOME/pokemon-checklist/` or `~/.cache/pokemon-checklist/` elsewhere); use `--cache-dir` to override it. Normal generation and `--check` only read that cache and fail clearly when it is missing or corrupt. The explicit refresh commands are networked and should be run only when inputs need bootstrapping or updating:

```text
python tools/build_icons.py --refresh
python tools/build_vanilla_encounters.py --refresh
```

Both commands accept `--cache-dir PATH`; `build_vanilla_encounters.py --game sun` (repeatable) limits table refresh/build. Direct `--source-dir` and `--tables-dir` overrides remain available for fully local vanilla builds. The icon cache pins the PokéAPI sprites source to commit `6e3e7c43e86db0e1b2277795cfee41b11e8df2a4` and validates all 807 40×30 PNGs plus the license. Vanilla tables come from the pinned [Pokémon Sun mirror](https://gist.github.com/RichardPaulAstley/42fbabe24250969f22d18fe8b919c520), SciresM's Pokémon Moon Pastebins (`YjNi4Qdk` and `HKEVPUYX`), and the pinned [Ultra Sun](https://gist.github.com/SciresM/a539739085e24af55dffdf443cb70eb2) and [Ultra Moon](https://gist.github.com/SciresM/deecdcf5fc49fc8191a29d111643c6b6) dumps. SHA-256 checks guard every table download and cache entry. The pinned [PokeAPI repository](https://github.com/PokeAPI/pokeapi/tree/4b82c204ddd19ecb8eda2ea044ccb59e222b721c/data/v2/csv) supplies normalized area, method, SOS, Island Scan, berry-pile, and postgame records.

## Attribution and disclaimer

Photonic Sun / Prismatic Moon encounter data and location screenshots/maps come from `references/Wild Pokemon Locations.pdf`. Vanilla Alola data uses the pinned sources described above; reused scenic screenshots come from the same guide, while mod-specific numbered maps are excluded. Pokémon names are a snapshot of the English PokéAPI species-name data. Types and source tiers come from the pinned MIT-licensed Pokémon Showdown Gen VII data, and usage is from Smogon's November 2019 Gen VII OU statistics; the displayed SSS–F grades are this project's simplified, child-friendly mapping. The icon atlas is generated from the PokéAPI sprites Generation VII menu icons; its license notice is preserved in `references/PokeAPI-sprites-LICENCE.txt`. Image contents are copyright The Pokémon Company and respective rights holders.

This is a private, personal, non-commercial fan project. It is not affiliated with, endorsed by, or sponsored by Nintendo, Game Freak, The Pokémon Company, PokéAPI, or the guide author. Do not redistribute assets or use this project commercially without checking the applicable rights.
