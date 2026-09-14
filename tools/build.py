#!/usr/bin/env python3
"""Build the dependency-free, file://-friendly checklist page."""
from __future__ import annotations

import argparse
import base64
import json
import re
import struct
from pathlib import Path
from typing import cast

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "src" / "index.template.html"
POKEMON_PATH = ROOT / "data" / "pokemon.json"
ENCOUNTERS_PATH = ROOT / "data" / "encounters.json"
ATLAS_PATH = ROOT / "assets" / "gen7-icons.png"
OUTPUT = ROOT / "index.html"
ATLAS_WIDTH = 1280
ATLAS_HEIGHT = 780
ATLAS_COLUMNS = 32
ATLAS_FRAME = (40, 30)
REQUIRED_GRASS_MAPS = {
    "Route 1": "assets/locations/route-1-map.png",
    "Hau'oli City": "assets/locations/hau-oli-city-map.jpg",
    "Route 2": "assets/locations/route-2-map.jpg",
    "Route 3": "assets/locations/route-3-map.jpg",
    "Route 5": "assets/locations/route-5-map.jpg",
    "Route 6": "assets/locations/route-6-map.png",
    "Mount Hokulani": "assets/locations/mount-hokulani-map.png",
}
PLACEHOLDERS = {
    "pokemon": "__POKEMON_JSON__",
    "encounters": "__ENCOUNTERS_JSON__",
    "atlas": "__ATLAS_JSON__",
    "assets": "__ASSETS_JSON__",
}


def read_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Cannot read valid JSON from {path.relative_to(ROOT)}") from error


def script_json(value: object) -> str:
    """JSON safe inside a classic script element."""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace(
        "<", "\\u003c"
    ).replace(">", "\\u003e").replace("&", "\\u0026")


def png_size(path: Path) -> tuple[int, int]:
    raw = path.read_bytes()
    if raw[:8] != b"\x89PNG\r\n\x1a\n" or raw[12:16] != b"IHDR" or len(raw) < 24:
        raise ValueError(f"{path.relative_to(ROOT)} is not a valid PNG with an IHDR")
    return struct.unpack(">II", raw[16:24])


def validate_inputs(pokemon: object, encounters: object) -> list[str]:
    errors: list[str] = []
    if not isinstance(pokemon, list) or len(pokemon) != 807:
        errors.append("pokemon.json must contain exactly 807 entries")
        pokemon = pokemon if isinstance(pokemon, list) else []
    ids = [item.get("id") if isinstance(item, dict) else None for item in pokemon]
    if ids != list(range(1, 808)) or len(set(ids)) != len(ids):
        errors.append("pokemon.json IDs must be unique and ordered 1..807")
    by_slug: dict[str, dict] = {}
    for item in pokemon:
        if not isinstance(item, dict) or not isinstance(item.get("slug"), str) or not isinstance(item.get("name"), str):
            errors.append("each Pokémon needs a string name and slug")
            continue
        if item["slug"] in by_slug:
            errors.append(f"duplicate Pokémon slug {item['slug']}")
        by_slug[item["slug"]] = item

    if not isinstance(encounters, dict) or encounters.get("schemaVersion") != 1:
        errors.append("encounters.json schemaVersion must be 1")
        return errors
    islands = encounters.get("islands")
    if not isinstance(islands, list) or len(islands) != 4:
        errors.append("encounters.json must contain four islands")
        islands = islands if isinstance(islands, list) else []
    manifest = encounters.get("assets")
    if not isinstance(manifest, list) or len(manifest) != len(set(manifest)):
        errors.append("encounters.json assets must be a unique list")
        manifest = manifest if isinstance(manifest, list) else []
    manifest_set = set(manifest)
    stable_ids: set[str] = set()
    location_order = 0
    seen_locations = 0

    def stable(value: object, label: str) -> None:
        if not isinstance(value, str) or not value:
            errors.append(f"{label} needs a stable string ID")
        elif value in stable_ids:
            errors.append(f"duplicate stable ID {value}")
        else:
            stable_ids.add(value)

    def asset(value: object, label: str) -> None:
        if not isinstance(value, str) or value not in manifest_set:
            errors.append(f"{label} is not listed in encounters.json assets: {value!r}")
            return
        path = Path(value)
        if path.is_absolute() or ".." in path.parts:
            errors.append(f"unsafe asset path {value}")
        elif not (ROOT / path).is_file():
            errors.append(f"missing asset {value}")

    for island in islands:
        if not isinstance(island, dict):
            errors.append("islands must contain objects")
            continue
        stable(island.get("id"), island.get("name", "island"))
        for value in island.get("assets", []):
            asset(value, island.get("name", "island"))
        for location in island.get("locations", []):
            if not isinstance(location, dict):
                errors.append("locations must contain objects")
                continue
            stable(location.get("id"), location.get("name", "location"))
            order = location.get("order")
            if not isinstance(order, int) or order <= location_order:
                errors.append(f"location order is not strictly increasing at {location.get('name')}")
            location_order = order if isinstance(order, int) else location_order
            seen_locations += 1
            for value in location.get("assets", []):
                asset(value, location.get("name", "location"))
            location_name = location.get("name")
            required_map = (
                REQUIRED_GRASS_MAPS.get(location_name)
                if isinstance(location_name, str)
                else None
            )
            if required_map and required_map not in location.get("assets", []):
                errors.append(f"{location.get('name')} is missing its numbered grass map {required_map}")
            for group in location.get("groups", []):
                if not isinstance(group, dict):
                    errors.append("groups must contain objects")
                    continue
                stable(group.get("id"), group.get("name", "group"))
                if group.get("category") not in {"regular", "return-later"}:
                    errors.append(f"invalid group category at {group.get('id')}")
                levels = group.get("levels")
                if levels is not None and (
                    not isinstance(levels, dict)
                    or not isinstance(levels.get("min"), int)
                    or not isinstance(levels.get("max"), int)
                    or levels["min"] > levels["max"]
                ):
                    errors.append(f"invalid levels at {group.get('id')}")
                for row in group.get("encounters", []):
                    if not isinstance(row, dict):
                        errors.append("encounters must contain objects")
                        continue
                    stable(row.get("id"), "encounter")
                    slug = row.get("species")
                    species_id = row.get("speciesId")
                    if slug is None:
                        if species_id is not None:
                            errors.append(f"null species has an ID at {row.get('id')}")
                    elif slug not in by_slug:
                        errors.append(f"unknown species slug {slug} at {row.get('id')}")
                    elif species_id != by_slug[slug].get("id"):
                        errors.append(f"species ID mismatch at {row.get('id')}")
                    rates = row.get("rates")
                    if rates is not None and (
                        not isinstance(rates, dict)
                        or not rates
                        or any(key not in {"single", "day", "night", "bubbling"} or not isinstance(value, int) or not 0 <= value <= 100 for key, value in rates.items())
                    ):
                        errors.append(f"invalid rates at {row.get('id')}")
                    for ally in row.get("allies", []):
                        if not isinstance(ally, dict) or ally.get("species") not in by_slug:
                            errors.append(f"unknown ally at {row.get('id')}")
                        elif ally.get("speciesId") != by_slug[ally["species"]].get("id"):
                            errors.append(f"ally ID mismatch at {row.get('id')}")

    for value in manifest:
        asset(value, "manifest")
    if seen_locations != 60:
        errors.append(f"expected 60 locations, found {seen_locations}")
    if not ATLAS_PATH.is_file():
        errors.append("missing icon atlas assets/gen7-icons.png")
    else:
        try:
            width, height = png_size(ATLAS_PATH)
            if (width, height) != (ATLAS_WIDTH, ATLAS_HEIGHT):
                errors.append(f"icon atlas must be {ATLAS_WIDTH}x{ATLAS_HEIGHT}, got {width}x{height}")
        except (OSError, ValueError) as error:
            errors.append(str(error))
    return errors


def asset_data_urls(encounters: dict) -> dict[str, str]:
    result: dict[str, str] = {}
    for path in encounters["assets"]:
        file_path = ROOT / path
        suffix = file_path.suffix.lower()
        mime = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}.get(suffix)
        if mime is None:
            raise ValueError(f"unsupported asset type {path}")
        result[path] = f"data:{mime};base64," + base64.b64encode(file_path.read_bytes()).decode("ascii")
    return result


def render(pokemon: list[dict], encounters: dict) -> str:
    template = TEMPLATE.read_text(encoding="utf-8")
    atlas_raw = base64.b64encode(ATLAS_PATH.read_bytes()).decode("ascii")
    values = {
        PLACEHOLDERS["pokemon"]: script_json(pokemon),
        PLACEHOLDERS["encounters"]: script_json(encounters),
        PLACEHOLDERS["atlas"]: script_json({"data": f"data:image/png;base64,{atlas_raw}", "width": ATLAS_WIDTH, "height": ATLAS_HEIGHT, "columns": ATLAS_COLUMNS, "frameWidth": ATLAS_FRAME[0], "frameHeight": ATLAS_FRAME[1]}),
        PLACEHOLDERS["assets"]: script_json(asset_data_urls(encounters)),
    }
    for placeholder, value in values.items():
        if template.count(placeholder) != 1:
            raise ValueError(f"template must contain exactly one {placeholder} placeholder")
        template = template.replace(placeholder, value)
    if any(value in template for value in PLACEHOLDERS.values()):
        raise ValueError("template placeholders were not fully replaced")
    return template


def validate_output(html: str, pokemon: list[dict], encounters: dict) -> None:
    if "</script>" in "".join(script_json(value) for value in (pokemon, encounters)):
        raise ValueError("JSON escaping failed to protect a closing script tag")
    if re.search(r"https?://", html, re.IGNORECASE):
        raise ValueError("generated HTML contains an external URL")
    if re.search(r"(?:src|href)\s*=\s*['\"]https?://", html, re.IGNORECASE):
        raise ValueError("generated HTML contains an external resource URL")
    for path, data_url in asset_data_urls(encounters).items():
        if data_url not in html:
            raise ValueError(f"generated HTML is missing embedded asset {path}")
    atlas_prefix = "data:image/png;base64,"
    if html.count(atlas_prefix) < 1:
        raise ValueError("generated HTML is missing the icon atlas")
    if script_json(pokemon) not in html or script_json(encounters) not in html:
        raise ValueError("generated HTML is missing canonical JSON")


def build(check: bool) -> int:
    pokemon_data = read_json(POKEMON_PATH)
    encounters_data = read_json(ENCOUNTERS_PATH)
    errors = validate_inputs(pokemon_data, encounters_data)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    pokemon = cast(list[dict], pokemon_data)
    encounters = cast(dict, encounters_data)
    html = render(pokemon, encounters)
    validate_output(html, pokemon, encounters)
    if check:
        if not OUTPUT.is_file() or OUTPUT.read_text(encoding="utf-8") != html:
            print("ERROR: index.html is stale; run python tools/build.py")
            return 1
        print("OK: canonical data, embedded resources, safety checks, and index.html freshness")
    else:
        OUTPUT.write_text(html, encoding="utf-8", newline="\n")
        print(f"Wrote {OUTPUT.relative_to(ROOT)} ({len(html):,} characters)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="validate inputs and fail if index.html is stale")
    return build(parser.parse_args().check)


if __name__ == "__main__":
    raise SystemExit(main())
