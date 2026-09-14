#!/usr/bin/env python3
"""Generate canonical vanilla Alola encounter datasets from pinned sources."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import unicodedata
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POKEMON_PATH = ROOT / "data" / "pokemon.json"
REFERENCE_PATH = ROOT / "data" / "encounters.json"
POKEAPI_COMMIT = "4b82c204ddd19ecb8eda2ea044ccb59e222b721c"
GAME_CONFIGS = {
    "sun": {
        "name": "Pokémon Sun",
        "versionId": 27,
        "tableSources": [
            (
                "https://gist.githubusercontent.com/RichardPaulAstley/42fbabe24250969f22d18fe8b919c520/raw/89ad2ad61cb86b03b34abb831a1f4b63549a0758/Encounter%20Tables%20Sun",
                "d94f1fd3e425415ff1a838ce5395cb05b66e6e2e32052ef88a32ca7a2f81b8ef",
            )
        ],
        "tableRevision": "89ad2ad61cb86b03b34abb831a1f4b63549a0758",
        "tableHash": "d94f1fd3e425415ff1a838ce5395cb05b66e6e2e32052ef88a32ca7a2f81b8ef",
        "poniGrass": {20, 297, 735},
        "poniBush": {123, 546},
    },
    "moon": {
        "name": "Pokémon Moon",
        "versionId": 28,
        "tableSources": [
            (
                "https://pastebin.com/raw/YjNi4Qdk",
                "0b87ec721b341aed33c7679f6f32a868044238498bab00efb2d05a053a43ade8",
            ),
            (
                "https://pastebin.com/raw/HKEVPUYX",
                "83e1a160e2bb89409b77a68f3fa087f6e63b0134bbc9cc45e33eb0de578a4896",
            ),
        ],
        "tableRevision": "Pastebin YjNi4Qdk + HKEVPUYX",
        "tableHash": "b13935988846219db3710253e14e4a01eb06daa8858a17712cf3eaa5581348c1",
        "poniGrass": {20, 297, 735},
        "poniBush": {123, 548},
    },
    "ultra-sun": {
        "name": "Pokémon Ultra Sun",
        "versionId": 29,
        "tableSources": [
            (
                "https://gist.githubusercontent.com/SciresM/a539739085e24af55dffdf443cb70eb2/raw/08f1cebd1486a0d36ce484a0d544ca9c50966136/Pokemon%20Ultra%20Sun%20-%20Encounter%20Tables.txt",
                "a61928a01e10554aa0163dbee6017d9a1ce94b06e966d37629d67c29500bbb30",
            )
        ],
        "tableRevision": "08f1cebd1486a0d36ce484a0d544ca9c50966136",
        "tableHash": "a61928a01e10554aa0163dbee6017d9a1ce94b06e966d37629d67c29500bbb30",
        "poniGrass": {20, 668, 735},
        "poniBush": {113, 123, 546},
    },
    "ultra-moon": {
        "name": "Pokémon Ultra Moon",
        "versionId": 30,
        "tableSources": [
            (
                "https://gist.githubusercontent.com/SciresM/deecdcf5fc49fc8191a29d111643c6b6/raw/5d019633233ec882c940bf8c1bcd42599ce0e2f2/Pokemon%20Ultra%20Moon%20-%20Encounter%20Tables.txt",
                "3b9b39cd549ba42b4286fa7970678fac7273f56725f3b1a5fcdd64612dba6241",
            )
        ],
        "tableRevision": "5d019633233ec882c940bf8c1bcd42599ce0e2f2",
        "tableHash": "3b9b39cd549ba42b4286fa7970678fac7273f56725f3b1a5fcdd64612dba6241",
        "poniGrass": {20, 668, 735},
        "poniBush": {113, 123, 548},
    },
}
EXPECTED_TOTALS = {
    "sun": ((57, 269, 771), (146, 137, 9)),
    "moon": ((57, 269, 771), (146, 137, 9)),
    "ultra-sun": ((60, 285, 937), (147, 146, 1)),
    "ultra-moon": ((60, 285, 935), (147, 146, 1)),
}
CSV_FILES = (
    "encounters.csv",
    "encounter_slots.csv",
    "encounter_methods.csv",
    "locations.csv",
    "location_areas.csv",
    "pokemon.csv",
)
CSV_URL = (
    "https://raw.githubusercontent.com/PokeAPI/pokeapi/"
    f"{POKEAPI_COMMIT}/data/v2/csv/{{name}}"
)
ALLOWED_METHODS = {
    "walk",
    "surf",
    "super-rod",
    "bubbling-spots",
    "berry-trees",
    "island-scan",
    "sos",
    "sos-from-bubbling-spot",
}
METHOD_ORDER = {
    "walk": 0,
    "surf": 1,
    "super-rod": 2,
    "bubbling-spots": 3,
    "berry-trees": 4,
    "island-scan": 5,
    "sos": 6,
    "sos-from-bubbling-spot": 7,
}
METHOD_LABELS = {
    "walk": "Walking encounters",
    "surf": "Surfing",
    "super-rod": "Fishing",
    "bubbling-spots": "Bubbling / rustling spots",
    "berry-trees": "Berry piles",
    "island-scan": "Island Scan",
    "sos": "SOS allies",
    "sos-from-bubbling-spot": "SOS allies from bubbling spots",
}
METHOD_CONDITIONS = {
    "surf": ["Requires Lapras Paddle."],
    "super-rod": ["Requires the Fishing Rod."],
    "bubbling-spots": ["Use a bubbling or rustling encounter spot."],
    "berry-trees": ["Check berry piles."],
    "island-scan": ["Available through Island Scan."],
    "sos": ["Appears as an SOS ally; the caller depends on the encounter."],
    "sos-from-bubbling-spot": [
        "Appears as an SOS ally from a bubbling or rustling encounter spot."
    ],
}
ISLAND_SCAN_DAYS = {
    "totodile": "Monday",
    "spheal": "Monday",
    "swinub": "Monday",
    "conkeldurr": "Monday",
    "deino": "Tuesday",
    "luxio": "Tuesday",
    "duosion": "Tuesday",
    "togekiss": "Tuesday",
    "horsea": "Wednesday",
    "honedge": "Wednesday",
    "roselia": "Wednesday",
    "leavanny": "Wednesday",
    "klink": "Thursday",
    "venipede": "Thursday",
    "staravia": "Thursday",
    "serperior": "Thursday",
    "chikorita": "Friday",
    "bellsprout": "Friday",
    "vigoroth": "Friday",
    "samurott": "Friday",
    "litwick": "Saturday",
    "marill": "Saturday",
    "axew": "Saturday",
    "emboar": "Saturday",
    "cyndaquil": "Sunday",
    "gothita": "Sunday",
    "rhyhorn": "Sunday",
    "eelektross": "Sunday",
    "scatterbug": "Thursday",
    "bulbasaur": "Friday",
    "charmander": "Sunday",
    "squirtle": "Monday",
    "onix": "Tuesday",
    "beedrill": "Thursday",
    "grovyle": "Friday",
    "marshtomp": "Saturday",
    "ralts": "Sunday",
    "combusken": "Tuesday",
    "pidgeot": "Thursday",
    "monferno": "Friday",
    "prinplup": "Tuesday",
    "grotle": "Wednesday",
    "greninja": "Friday",
    "chesnaught": "Thursday",
    "delphox": "Saturday",
    "aggron": "Monday",
    "rotom": "Tuesday",
}
WEATHER_CONDITIONS = {
    "castform": "Weather-dependent SOS encounter.",
    "goomy": "SOS encounter while it is raining.",
    "sliggoo": "SOS encounter while it is raining.",
    "vanillite": "SOS encounter while it is hailing.",
    "vanillish": "SOS encounter while it is hailing.",
    "gabite": "SOS encounter during a sandstorm.",
    "poliwhirl": "SOS encounter while it is raining.",
    "poliwrath": "Daytime SOS encounter while it is raining.",
    "politoed": "Nighttime SOS encounter while it is raining.",
}

# PokeAPI areas are folded into the guide's existing stable location IDs where possible.
TARGET_NAMES = {
    ("alola-route-1", "east"): "Route 1",
    ("alola-route-1", "south"): "Route 1",
    ("alola-route-1", "west"): "Route 1",
    ("alola-route-1", "hauoli-outskirts"): "Hau'oli Outskirts",
    ("alola-route-1", "trainers-school"): "Trainer's School",
    ("hauoli-city", "main"): "Hau'oli City",
    ("hauoli-city", "beachfront"): "Hau'oli City",
    ("hauoli-city", "shopping-district"): "Trainer's School",
    ("alola-route-2", "main"): "Route 2",
    ("alola-route-2", "north"): "Route 2",
    ("alola-route-2", "south"): "Route 2",
    ("alola-berry-fields", ""): "Route 2",
    ("hauoli-cemetery", ""): "Hau'oli Cemetery",
    ("verdant-cavern", "trial-site"): "Verdant Cavern",
    ("alola-route-3", "main"): "Route 3",
    ("alola-route-3", "north"): "Route 3",
    ("alola-route-3", "south"): "Route 3",
    ("kalae-bay", ""): "Kala'e Bay",
    ("melemele-meadow", ""): "Melemele Meadow",
    ("seaward-cave", ""): "Seaward Cave",
    ("ten-carat-hill", "inside"): "Ten Carat Hill",
    ("ten-carat-hill", "farthest-hollow"): "Ten Carat Hill",
    ("melemele-sea", ""): "Melemele Sea (Hau'oli City)",
    ("alola-route-4", ""): "Route 4",
    ("paniola-ranch", ""): "Paniola Ranch",
    ("paniola-town", ""): "Paniola Ranch",
    ("alola-route-5", ""): "Route 5",
    ("brooklet-hill", "main"): "Brooklet Hill",
    ("brooklet-hill", "north"): "Brooklet Hill",
    ("brooklet-hill", "south"): "Brooklet Hill",
    ("brooklet-hill", "totems-den"): "Brooklet Hill",
    ("alola-route-6", "north"): "Route 6",
    ("alola-route-6", "south"): "Route 6",
    ("digletts-tunnel", ""): "Diglett's Tunnel",
    ("alola-route-7", ""): "Route 7",
    ("wela-volcano-park", ""): "Wela Volcano Park",
    ("alola-route-8", "main"): "Route 8",
    ("lush-jungle", "all-areas"): "Lush Jungle",
    ("lush-jungle", "north"): "Lush Jungle",
    ("lush-jungle", "south"): "Lush Jungle",
    ("lush-jungle", "west"): "Lush Jungle",
    ("lush-jungle", "east-cave"): "Lush Jungle Cave",
    ("hano-beach", ""): "Hano Beach",
    ("alola-route-9", "main"): "Route 9",
    ("memorial-hill", ""): "Memorial Hill",
    ("akala-outskirts", ""): "Akala Outskirts",
    ("malie-city", "outer-cape"): "Malie City",
    ("malie-garden", ""): "Malie Garden",
    ("mount-hokulani", "main"): "Mount Hokulani",
    ("alola-route-10", ""): "Route 10",
    ("alola-route-11", ""): "Route 11",
    ("alola-route-12", ""): "Route 12",
    ("secluded-shore", ""): "Route 12",
    ("blush-mountain", ""): "Blush Mountain",
    ("alola-route-13", ""): "Route 13",
    ("tapu-village", ""): "Tapu Village",
    ("mount-lanakila", "outside"): "Mount Lanakila",
    ("mount-lanakila", "base"): "Mount Lanakila",
    ("alola-route-14", ""): "Route 14",
    ("thrifty-megamart", "abandoned-site"): "Thrifty Megamart",
    ("alola-route-15", "main"): "Route 15 / 16",
    ("alola-route-16", "main"): "Route 15 / 16",
    ("alola-route-16", "east"): "Route 15 / 16",
    ("alola-route-16", "west"): "Route 15 / 16",
    ("ulaula-meadow", ""): "Ula'ula Meadow",
    ("alola-route-17", "all-areas"): "Route 17",
    ("alola-route-17", "northeast"): "Route 17",
    ("alola-route-17", "west"): "Route 17",
    ("haina-desert", ""): "Haina Desert",
    ("mount-lanakila", "cave"): "Victory Road",
    ("seafolk-village", "main"): "Seafolk Village",
    ("poni-wilds", ""): "Poni Wilds",
    ("exeggutor-island", ""): "Exeggutor Island",
    ("ancient-poni-path", ""): "Ancient Poni Path",
    ("poni-breaker-coast", ""): "Ponibreaker Coast",
    ("vast-poni-canyon", "outside"): "Vast Poni Canyon",
    ("vast-poni-canyon", "inside"): "Vast Poni Canyon",
    ("vast-poni-canyon", "northwest"): "Vast Poni Canyon",
    ("poni-grove", ""): "Poni Grove",
    ("poni-plains", "center"): "Poni Plains",
    ("poni-plains", "east"): "Poni Plains",
    ("poni-plains", "north"): "Poni Plains",
    ("poni-plains", "west"): "Poni Plains",
    ("poni-meadow", ""): "Poni Meadow",
    ("resolution-cave", ""): "Resolution Cave",
    ("poni-coast", ""): "Poni Coast",
    ("poni-gauntlet", ""): "Poni Gauntlet",
    ("sandy-cave", ""): "Sandy Cave",
    ("dividing-peak-tunnel", ""): "Dividing Peak Tunnel",
    ("ulaula-beach", ""): "Ula'ula Beach",
}
SUN_LEVEL_OVERRIDES = {
    ("blush-mountain", "", "sos"): (27, 30),
    ("mount-lanakila", "cave", "sos"): (45, 48),
}
TABLE_OVERRIDES = {
    ("verdant-cavern", "trial-site", "bubbling-spots"): ("024 - Verdant Cavern", 2),
    ("blush-mountain", "", "walk"): ("164 - Blush Mountain", 1),
    ("mount-lanakila", "cave", "walk"): ("180 - Mount Lanakila", 1),
    ("vast-poni-canyon", "outside", "walk"): ("240 - Vast Poni Canyon", 1),
}
SOURCE_LABELS = {
    ("hauoli-city", "shopping-district"): "School grounds",
    ("alola-route-1", "trainers-school"): "School grounds",
    ("hauoli-city", "beachfront"): "Beachfront",
    ("alola-berry-fields", ""): "Berry Fields",
    ("paniola-town", ""): "Paniola Town",
    ("secluded-shore", ""): "Secluded Shore",
    ("alola-route-15", "main"): "Route 15",
    ("alola-route-16", "main"): "Route 16",
    ("alola-route-16", "east"): "Route 16 east",
    ("alola-route-16", "west"): "Route 16 west",
    ("mount-hokulani", "east"): "East",
    ("mount-hokulani", "west"): "West",
    ("mount-lanakila", "base"): "Base",
}
AREA_LABELS = {
    "east": "East",
    "west": "West",
    "north": "North",
    "south": "South",
    "center": "Center",
    "outside": "Outside",
    "inside": "Inside",
    "northwest": "Northwest",
    "farthest-hollow": "Farthest Hollow",
    "outer-cape": "Outer Cape",
    "shopping-district": "Shopping District",
    "totems-den": "Totem's Den",
    "trial-site": "Trial Site",
    "center-rustling-grass": "Center rustling grass",
    "center-rustling-bush": "Center rustling bush",
}
TABLE_ENTRY_PATTERN = re.compile(r"(?:^|, )([^,(]+?)(?: \(Forme (\d+)\))? \((\d+)%\)")
ALOLAN_SPECIES = {
    19,
    20,
    26,
    27,
    28,
    37,
    38,
    50,
    51,
    52,
    53,
    74,
    75,
    76,
    88,
    89,
    103,
}


def normalize(value: str) -> str:
    ascii_value = (
        unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    )
    return re.sub(r"[^a-z0-9]", "", ascii_value.lower())


def rows(text: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(text)))


def parse_int(value: object, label: str) -> int:
    try:
        return int(str(value))
    except (TypeError, ValueError) as error:
        raise ValueError(f"Invalid integer for {label}: {value!r}") from error


def read_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(
            f"Cannot read valid JSON from {path.relative_to(ROOT)}"
        ) from error


def download_text(url: str, expected_hash: str | None = None) -> str:
    if not url.startswith("https://"):
        raise ValueError("Source URLs must use HTTPS")
    try:
        request = urllib.request.Request(  # noqa: S310 - HTTPS checked above
            url, headers={"User-Agent": "pokemon-checklist-builder"}
        )
        with urllib.request.urlopen(request) as response:  # noqa: S310 - HTTPS checked above
            raw = response.read()
    except OSError as error:
        raise RuntimeError(f"Could not download pinned source {url}") from error
    if expected_hash and hashlib.sha256(raw).hexdigest() != expected_hash:
        raise ValueError(f"Pinned encounter-table source changed: {url}")
    try:
        return raw.decode("utf-8").replace("\r\n", "\n")
    except UnicodeDecodeError as error:
        raise RuntimeError(f"Could not decode pinned source {url}") from error


def form_label(
    species_id: int, pokemon_identifier: str, raw_form: int | None = None
) -> str | None:
    if pokemon_identifier.endswith("-alola") or (
        raw_form == 1 and species_id in ALOLAN_SPECIES
    ):
        return "alolan"
    if species_id == 741:
        suffix = pokemon_identifier.removeprefix("oricorio-")
        named = {
            "oricorio": "baile",
            "pom-pom": "pom-pom",
            "pau": "pa'u",
            "sensu": "sensu",
        }
        numbered = {0: "baile", 1: "pom-pom", 2: "pa'u", 3: "sensu"}
        return named.get(suffix) or (
            numbered.get(raw_form) if raw_form is not None else None
        )
    if species_id in {669, 670} and raw_form is not None:
        return {
            0: "red-flower",
            1: "yellow-flower",
            2: "orange-flower",
            3: "blue-flower",
            4: "white-flower",
        }.get(raw_form)
    if species_id == 745:
        if pokemon_identifier.endswith("-dusk") or raw_form == 2:
            return "dusk"
        if pokemon_identifier.endswith("-midnight") or raw_form == 1:
            return "midnight"
        return "midday"
    if species_id == 550:
        if pokemon_identifier.endswith("-blue-striped") or raw_form == 1:
            return "blue-striped"
        return "red-striped"
    if species_id == 423 and raw_form == 1:
        return "east-sea"
    return None


def parse_table_entries(text: str, by_name: dict[str, dict]) -> list[dict]:
    found = []
    for name, raw_form, rate in TABLE_ENTRY_PATTERN.findall(text):
        name = name.strip()
        if name == "(None)":
            continue
        pokemon = by_name[normalize(name)]
        form_number = parse_int(raw_form, "encounter-table form") if raw_form else None
        found.append(
            {
                "speciesId": pokemon["id"],
                "form": form_label(pokemon["id"], pokemon["slug"], form_number),
                "rate": parse_int(rate, "encounter-table rate"),
            }
        )
    return found


def parse_tables(text: str, by_name: dict[str, dict]) -> list[dict]:
    result = []
    pattern = re.compile(
        r"Table (\d+) \((Day|Night)\):\n"
        r"Encounters \(Levels (\d+)(?:-(\d+))?\): (.+)"
    )
    for block in text.split("=========="):
        header_match = re.search(r"Map: (.+)\nTables: (\d+)", block)
        if not header_match:
            continue
        tables: dict[int, dict] = defaultdict(dict)
        for number, when, minimum, maximum, entries in pattern.findall(block):
            table_number = parse_int(number, "encounter-table number")
            tables[table_number][when.lower()] = {
                "minimum": parse_int(minimum, "encounter-table minimum level"),
                "maximum": parse_int(
                    maximum or minimum, "encounter-table maximum level"
                ),
                "entries": parse_table_entries(entries, by_name),
            }
        for number, halves in tables.items():
            if set(halves) == {"day", "night"}:
                result.append(
                    {"header": header_match.group(1), "number": number, **halves}
                )
    return result


def signature(entries: list[dict]) -> Counter:
    return Counter((entry["speciesId"], entry["rate"]) for entry in entries)


def table_for(
    records: list[dict],
    tables: list[dict],
    location_slug: str,
    area_slug: str,
    method: str,
    original_games: bool,
) -> dict | None:
    override = (
        TABLE_OVERRIDES.get((location_slug, area_slug, method))
        if original_games
        else None
    )
    if override:
        header, number = override
        matched = next(
            (
                table
                for table in tables
                if table["header"].startswith(header) and table["number"] == number
            ),
            None,
        )
        if matched:
            return matched
    wanted = Counter({(record["speciesId"], record["rarity"]) for record in records})
    candidates = [
        table
        for table in tables
        if (signature(table["day"]["entries"]) | signature(table["night"]["entries"]))
        == wanted
    ]
    location_hint = normalize(
        location_slug.removeprefix("alola-").replace("s-tunnel", "s tunnel")
    )
    local = [
        table for table in candidates if location_hint in normalize(table["header"])
    ]
    candidates = local or candidates
    exact = [
        table
        for table in candidates
        if table["day"]["minimum"] == records[0]["minimum"]
        and table["day"]["maximum"] == records[0]["maximum"]
    ]
    return (exact or candidates or [None])[0]


def rate_map(day: int | None, night: int | None) -> dict[str, int]:
    if day == night and day is not None:
        return {"single": day}
    return {"day": day or 0, "night": night or 0}


def direct_rows(
    records: list[dict], table: dict | None, by_id: dict[int, dict], group_id: str
) -> list[dict]:
    if table:
        combined: dict[tuple[int, str | None], dict[str, int | None]] = defaultdict(
            lambda: {"day": None, "night": None}
        )
        for when in ("day", "night"):
            for entry in table[when]["entries"]:
                key = (entry["speciesId"], entry["form"])
                combined[key][when] = (combined[key][when] or 0) + entry["rate"]
        items = []
        for index, ((species_id, form), rates) in enumerate(combined.items(), 1):
            pokemon = by_id[species_id]
            item = {
                "speciesName": pokemon["name"],
                "species": pokemon["slug"],
                "rates": rate_map(rates["day"], rates["night"]),
                "allies": [],
                "id": f"{group_id}/{index}",
                "speciesId": species_id,
            }
            if form:
                item["form"] = form
            items.append(item)
        return items

    unique: dict[tuple[int, str | None], dict] = {}
    for record in records:
        key = (record["speciesId"], record["form"])
        unique.setdefault(key, record)
    items = []
    for index, ((species_id, form), record) in enumerate(unique.items(), 1):
        pokemon = by_id[species_id]
        item = {
            "speciesName": pokemon["name"],
            "species": pokemon["slug"],
            "rates": {"single": record["rarity"]},
            "allies": [],
            "id": f"{group_id}/{index}",
            "speciesId": species_id,
        }
        if form:
            item["form"] = form
        items.append(item)
    return items


def optional_rows(
    records: list[dict], by_id: dict[int, dict], group_id: str, method: str
) -> list[dict]:
    unique: dict[tuple[int, str | None], dict] = {}
    for record in records:
        unique.setdefault((record["speciesId"], record["form"]), record)
    items = []
    for index, ((species_id, form), record) in enumerate(unique.items(), 1):
        pokemon = by_id[species_id]
        item = {
            "speciesName": pokemon["name"],
            "species": pokemon["slug"],
            "rates": None if method.startswith("sos") else {"single": record["rarity"]},
            "allies": [],
            "id": f"{group_id}/{index}",
            "speciesId": species_id,
        }
        if form:
            item["form"] = form
        condition = WEATHER_CONDITIONS.get(pokemon["slug"])
        if method.startswith("sos") and condition:
            item["conditions"] = [condition]
        items.append(item)
    return items


def source_prefix(location_slug: str, area_slug: str) -> str:
    special = SOURCE_LABELS.get((location_slug, area_slug))
    if special:
        return special
    return AREA_LABELS.get(area_slug, "")


def load_csv_sources(source_dir: Path | None) -> dict[str, str]:
    if source_dir:
        try:
            return {
                name: (source_dir / name).read_text(encoding="utf-8")
                for name in CSV_FILES
            }
        except OSError as error:
            raise ValueError(f"Could not read local CSV source: {error}") from error
    return {name: download_text(CSV_URL.format(name=name)) for name in CSV_FILES}


def load_table(game: str, tables_dir: Path | None) -> str:
    config = GAME_CONFIGS[game]
    if tables_dir:
        path = tables_dir / f"{game}.txt"
        try:
            raw = path.read_bytes()
        except OSError as error:
            raise ValueError(
                f"Could not read local encounter table {path}: {error}"
            ) from error
        if hashlib.sha256(raw).hexdigest() != config["tableHash"]:
            raise ValueError(f"Local encounter table has the wrong hash: {path}")
        return raw.decode("utf-8").replace("\r\n", "\n")
    return "\n".join(
        download_text(url, digest) for url, digest in config["tableSources"]
    )


def generate(
    csv_text: dict[str, str], table_text: str, game: str
) -> tuple[dict, list[str], int, int]:
    config = GAME_CONFIGS[game]
    version_id = config["versionId"]
    original_games = version_id in {27, 28}
    pokemon = read_json(POKEMON_PATH)
    reference = read_json(REFERENCE_PATH)
    if not isinstance(pokemon, list) or not isinstance(reference, dict):
        raise ValueError("Canonical Pokémon and encounter sources have invalid roots")
    by_id = {item["id"]: item for item in pokemon}
    by_name = {normalize(item["name"]): item for item in pokemon}
    reference_locations = {
        location["name"]: (island["id"], location)
        for island in reference["islands"]
        for location in island["locations"]
    }

    slots = {item["id"]: item for item in rows(csv_text["encounter_slots.csv"])}
    methods = {
        item["id"]: item["identifier"]
        for item in rows(csv_text["encounter_methods.csv"])
    }
    areas = {item["id"]: item for item in rows(csv_text["location_areas.csv"])}
    location_names = {
        item["id"]: item["identifier"] for item in rows(csv_text["locations.csv"])
    }
    pokemon_forms = {item["id"]: item for item in rows(csv_text["pokemon.csv"])}
    grouped: dict[tuple, list[dict]] = defaultdict(list)

    for encounter in rows(csv_text["encounters.csv"]):
        if encounter["version_id"] != str(version_id):
            continue
        slot = slots[encounter["encounter_slot_id"]]
        method = methods[slot["encounter_method_id"]]
        if method not in ALLOWED_METHODS:
            continue
        area = areas[encounter["location_area_id"]]
        source_key = (location_names[area["location_id"]], area["identifier"])
        target_name = TARGET_NAMES.get(source_key)
        if not original_games and source_key == ("hauoli-city", "shopping-district"):
            target_name = "Hau'oli City"
        if not target_name:
            continue
        pokemon_form = pokemon_forms[encounter["pokemon_id"]]
        species_id = parse_int(pokemon_form["species_id"], "Pokémon species ID")
        if species_id not in by_id:
            continue
        minimum = parse_int(encounter["min_level"], "minimum encounter level")
        maximum = parse_int(encounter["max_level"], "maximum encounter level")
        key = (*source_key, target_name, method, minimum, maximum)
        grouped[key].append(
            {
                "speciesId": species_id,
                "form": form_label(species_id, pokemon_form["identifier"]),
                "rarity": parse_int(slot["rarity"], "encounter rarity"),
                "minimum": minimum,
                "maximum": maximum,
            }
        )

    poni_rustling = grouped.pop(
        ("poni-plains", "center", "Poni Plains", "bubbling-spots", 54, 57)
    )
    grouped[
        (
            "poni-plains",
            "center-rustling-grass",
            "Poni Plains",
            "bubbling-spots",
            54,
            57,
        )
    ] = [
        record for record in poni_rustling if record["speciesId"] in config["poniGrass"]
    ]
    grouped[
        ("poni-plains", "center-rustling-bush", "Poni Plains", "bubbling-spots", 54, 57)
    ] = [
        record for record in poni_rustling if record["speciesId"] in config["poniBush"]
    ]

    parsed_tables = parse_tables(table_text, by_name)
    unmatched = []
    direct_groups = 0
    matched_groups = 0
    groups_by_location: dict[str, list[dict]] = defaultdict(list)
    sorted_groups = sorted(
        grouped.items(),
        key=lambda item: (
            reference_locations[item[0][2]][1]["order"],
            item[0][0],
            item[0][1],
            METHOD_ORDER[item[0][3]],
            item[0][4],
            item[0][5],
        ),
    )
    for key, records in sorted_groups:
        location_slug, area_slug, target_name, method, minimum, maximum = key
        reference_location = reference_locations[target_name][1]
        prefix = source_prefix(location_slug, area_slug)
        name = " · ".join(part for part in (prefix, METHOD_LABELS[method]) if part)
        if game == "sun":
            minimum, maximum = SUN_LEVEL_OVERRIDES.get(
                (location_slug, area_slug, method), (minimum, maximum)
            )
        direct = method in {"walk", "surf", "super-rod", "bubbling-spots"}
        table = (
            table_for(
                records, parsed_tables, location_slug, area_slug, method, original_games
            )
            if direct
            else None
        )
        if table:
            minimum = table["day"]["minimum"]
            maximum = table["day"]["maximum"]
        group_id = (
            f"{reference_location['id']}/{game}-{location_slug}-{area_slug or 'main'}-"
            f"{method}-{minimum}-{maximum}"
        )
        if direct:
            direct_groups += 1
            if table:
                matched_groups += 1
            else:
                unmatched.append(group_id)
        postgame = (
            method == "walk"
            and len({record["speciesId"] for record in records}) == 1
            and minimum >= 55
        )
        category = "regular" if method == "walk" and not postgame else "return-later"
        conditions = list(METHOD_CONDITIONS.get(method, []))
        if method == "island-scan":
            species_slug = by_id[records[0]["speciesId"]]["slug"]
            weekday = ISLAND_SCAN_DAYS[species_slug]
            conditions = [
                f"Use Island Scan on {weekday}; the encounter remains available for one hour."
            ]
        if postgame:
            conditions.append("Postgame Ultra Beast encounter.")
        encounter_rows = (
            direct_rows(records, table, by_id, group_id)
            if method in {"walk", "surf", "super-rod", "bubbling-spots"}
            else optional_rows(records, by_id, group_id, method)
        )
        groups_by_location[target_name].append(
            {
                "name": name,
                "category": category,
                "levels": {"min": minimum, "max": maximum},
                "encounters": encounter_rows,
                "notes": [],
                "conditions": conditions,
                "encounterType": "sos" if method.startswith("sos") else "wild",
                "sourceArea": {
                    "location": location_slug,
                    "area": area_slug,
                    "method": method,
                },
                "id": group_id,
            }
        )

    islands = []
    asset_manifest = []
    for reference_island in reference["islands"]:
        locations = []
        for reference_location in reference_island["locations"]:
            location_groups = groups_by_location.get(reference_location["name"])
            if not location_groups:
                continue
            assets = [
                path
                for path in reference_location.get("assets", [])
                if "map" not in path.lower()
            ]
            asset_manifest.extend(assets)
            locations.append(
                {
                    "name": reference_location["name"],
                    "assets": assets,
                    "groups": location_groups,
                    "notes": [],
                    "id": reference_location["id"],
                    "order": reference_location["order"],
                }
            )
        islands.append(
            {
                "name": reference_island["name"],
                "assets": [],
                "locations": locations,
                "id": reference_island["id"],
            }
        )

    data = {
        "schemaVersion": 1,
        "mode": game,
        "source": {
            "game": config["name"],
            "versionId": version_id,
            "description": f"Vanilla {config['name']} wild encounters.",
            "primary": f"Datamined {config['name']} encounter tables",
            "tableRevision": config["tableRevision"],
            "tableSha256": config["tableHash"],
            "normalization": "PokeAPI encounter CSV data",
            "pokeapiCommit": POKEAPI_COMMIT,
            "method": f"The encounter-table dump supplies direct species, forms, levels, rates, and day/night splits. PokeAPI version {version_id} records map tables to named areas and methods and supplies SOS, Island Scan, berry-pile, and postgame records.",
        },
        "documentNotes": [
            f"Only {config['name']} records (version ID {version_id}) are included.",
            "Walking encounters count toward location completion; Surfing, fishing, bubbling spots, berry piles, Island Scan, SOS allies, and postgame Ultra Beasts are Return later.",
            "SOS rows list available allies. The source does not identify one caller for every normalized SOS record.",
            f"Prismatic Moon numbered maps are intentionally omitted in {config['name']} mode.",
        ],
        "islands": islands,
        "assets": list(dict.fromkeys(asset_manifest)),
    }
    return data, unmatched, direct_groups, matched_groups


def validate_generated(
    game: str,
    data: dict,
    unmatched: list[str],
    direct_groups: int,
    matched_groups: int,
) -> None:
    locations = [
        location for island in data["islands"] for location in island["locations"]
    ]
    groups = [group for location in locations for group in location["groups"]]
    encounter_rows = [row for group in groups for row in group["encounters"]]
    if (
        data["mode"] != game
        or data["source"]["versionId"] != GAME_CONFIGS[game]["versionId"]
    ):
        raise ValueError(f"{game} metadata does not match its source configuration")
    expected_totals, expected_coverage = EXPECTED_TOTALS[game]
    totals = (len(locations), len(groups), len(encounter_rows))
    coverage = (direct_groups, matched_groups, len(unmatched))
    if totals != expected_totals:
        raise ValueError(f"Unexpected {game} location, group, or row count: {totals}")
    if coverage != expected_coverage:
        raise ValueError(f"Unexpected {game} direct-table match coverage: {coverage}")
    groups_by_id = {group["id"]: group for group in groups}
    if any(
        groups_by_id[group_id]["category"] != "return-later" for group_id in unmatched
    ):
        raise ValueError(f"{game} has a regular encounter without a direct-table match")
    if any("map" in path.lower() for path in data["assets"]):
        raise ValueError(f"{game} must not reuse mod-specific numbered maps")
    for group in groups:
        if group["encounterType"] == "sos":
            if any(row["rates"] is not None for row in group["encounters"]):
                raise ValueError(f"SOS rates must be omitted at {group['id']}")
            continue
        for when in ("day", "night"):
            total = sum(
                row["rates"].get("single", 0) + row["rates"].get(when, 0)
                for row in group["encounters"]
            )
            if total != 100:
                raise ValueError(f"{when} rates total {total}% at {group['id']}")

    verdant = next(item for item in locations if item["name"] == "Verdant Cavern")
    bubbling = next(item for item in verdant["groups"] if "Bubbling" in item["name"])
    expected = "yungoos" if game in {"sun", "ultra-sun"} else "rattata"
    if {row["species"] for row in bubbling["encounters"]} != {expected}:
        raise ValueError(f"{game} contains the wrong Verdant Cavern exclusive")

    poni = next(item for item in locations if item["name"] == "Poni Plains")
    bush = next(item for item in poni["groups"] if "rustling bush" in item["name"])
    plant = "cottonee" if game in {"sun", "ultra-sun"} else "petilil"
    expected_bush = {plant, "scyther"}
    if game.startswith("ultra-"):
        expected_bush.add("chansey")
    if {row["species"] for row in bush["encounters"]} != expected_bush:
        raise ValueError(f"{game} contains the wrong Poni Plains rustling encounters")

    ultra_locations = {"Sandy Cave", "Dividing Peak Tunnel", "Ula'ula Beach"}
    present = ultra_locations & {location["name"] for location in locations}
    if present != (ultra_locations if game.startswith("ultra-") else set()):
        raise ValueError(f"{game} contains the wrong Ultra-only locations")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, help="Use local PokeAPI CSV files")
    parser.add_argument(
        "--tables-dir", type=Path, help="Use local <game>.txt encounter-table dumps"
    )
    parser.add_argument(
        "--game",
        action="append",
        choices=GAME_CONFIGS,
        help="Build one game (repeatable)",
    )
    parser.add_argument(
        "--check", action="store_true", help="Fail if canonical JSON is stale"
    )
    args = parser.parse_args()
    csv_text = load_csv_sources(args.source_dir)
    stale = False
    for game in args.game or GAME_CONFIGS:
        table_text = load_table(game, args.tables_dir)
        data, unmatched, direct_groups, matched_groups = generate(
            csv_text, table_text, game
        )
        validate_generated(game, data, unmatched, direct_groups, matched_groups)
        output = ROOT / "data" / f"encounters-{game}.json"
        rendered = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
        if args.check:
            if not output.is_file() or output.read_text(encoding="utf-8") != rendered:
                print(f"ERROR: {output.relative_to(ROOT)} is stale")
                stale = True
        else:
            output.write_text(rendered, encoding="utf-8")
        locations = sum(len(island["locations"]) for island in data["islands"])
        groups = sum(
            len(location["groups"])
            for island in data["islands"]
            for location in island["locations"]
        )
        encounters = sum(
            len(group["encounters"])
            for island in data["islands"]
            for location in island["locations"]
            for group in location["groups"]
        )
        print(
            f"OK: {GAME_CONFIGS[game]['name']} has {locations} locations, "
            f"{groups} groups, and {encounters} rows"
        )
        print(
            f"Day/night table matches: {matched_groups}/{direct_groups}; "
            f"direct fallbacks: {len(unmatched)}"
        )
        for group_id in unmatched:
            print(f"  fallback: {group_id}")
    return 1 if stale else 0


if __name__ == "__main__":
    try:
        exit_code = main()
    except (OSError, RuntimeError, ValueError) as error:
        print(f"ERROR: {error}")
        exit_code = 1
    raise SystemExit(exit_code)
