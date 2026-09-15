#!/usr/bin/env python3
"""Validate canonical checklist data and assets."""

from __future__ import annotations

import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

POKEMON_PATH = ROOT / "data" / "pokemon.json"
ENCOUNTERS_PATH = ROOT / "data" / "encounters.json"
VANILLA_ENCOUNTERS = {
    "sun": (ROOT / "data" / "encounters-sun.json", 57),
    "moon": (ROOT / "data" / "encounters-moon.json", 57),
    "ultra-sun": (ROOT / "data" / "encounters-ultra-sun.json", 60),
    "ultra-moon": (ROOT / "data" / "encounters-ultra-moon.json", 60),
}
ATLAS_PATH = ROOT / "assets" / "gen7-icons.png"

ATLAS_WIDTH = 1280
ATLAS_HEIGHT = 780
ATLAS_COLUMNS = 32
REQUIRED_GRASS_MAPS = {
    "Route 1": "assets/locations/route-1-map.png",
    "Hau'oli City": "assets/locations/hau-oli-city-map.jpg",
    "Route 2": "assets/locations/route-2-map.jpg",
    "Route 3": "assets/locations/route-3-map.jpg",
    "Route 5": "assets/locations/route-5-map.jpg",
    "Route 6": "assets/locations/route-6-map.png",
    "Mount Hokulani": "assets/locations/mount-hokulani-map.png",
}


def read_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(
            f"Cannot read valid JSON from {path.relative_to(ROOT)}"
        ) from error


def script_json(value: object) -> str:
    """JSON safe inside a classic script element."""
    return (
        json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )


def png_size(path: Path) -> tuple[int, int]:
    raw = path.read_bytes()
    if raw[:8] != b"\x89PNG\r\n\x1a\n" or raw[12:16] != b"IHDR" or len(raw) < 24:
        raise ValueError(f"{path.relative_to(ROOT)} is not a valid PNG with an IHDR")
    return struct.unpack(">II", raw[16:24])


def validate_inputs(
    pokemon: object,
    encounters: object,
    expected_locations: int = 60,
    require_grass_maps: bool = True,
    expected_mode: str | None = None,
) -> list[str]:
    errors: list[str] = []
    if not isinstance(pokemon, list) or len(pokemon) != 807:
        errors.append("pokemon.json must contain exactly 807 entries")
        pokemon = pokemon if isinstance(pokemon, list) else []
    ids = [item.get("id") if isinstance(item, dict) else None for item in pokemon]
    if ids != list(range(1, 808)) or len(set(ids)) != len(ids):
        errors.append("pokemon.json IDs must be unique and ordered 1..807")
    by_slug: dict[str, dict] = {}
    for item in pokemon:
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("slug"), str)
            or not isinstance(item.get("name"), str)
        ):
            errors.append("each Pokémon needs a string name and slug")
            continue
        if item["slug"] in by_slug:
            errors.append(f"duplicate Pokémon slug {item['slug']}")
        by_slug[item["slug"]] = item

    if not isinstance(encounters, dict) or encounters.get("schemaVersion") != 1:
        errors.append("encounters.json schemaVersion must be 1")
        return errors
    if expected_mode and encounters.get("mode") != expected_mode:
        errors.append(f"encounters.json mode must be {expected_mode}")
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
                errors.append(
                    f"location order is not strictly increasing at {location.get('name')}"
                )
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
            if (
                require_grass_maps
                and required_map
                and required_map not in location.get("assets", [])
            ):
                errors.append(
                    f"{location.get('name')} is missing its numbered grass map {required_map}"
                )
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
                        or any(
                            key not in {"single", "day", "night", "bubbling"}
                            or not isinstance(value, int)
                            or not 0 <= value <= 100
                            for key, value in rates.items()
                        )
                    ):
                        errors.append(f"invalid rates at {row.get('id')}")
                    for ally in row.get("allies", []):
                        if (
                            not isinstance(ally, dict)
                            or ally.get("species") not in by_slug
                        ):
                            errors.append(f"unknown ally at {row.get('id')}")
                        elif ally.get("speciesId") != by_slug[ally["species"]].get(
                            "id"
                        ):
                            errors.append(f"ally ID mismatch at {row.get('id')}")

    for value in manifest:
        asset(value, "manifest")
    if seen_locations != expected_locations:
        errors.append(
            f"expected {expected_locations} locations, found {seen_locations}"
        )
    if not ATLAS_PATH.is_file():
        errors.append("missing icon atlas assets/gen7-icons.png")
    else:
        try:
            width, height = png_size(ATLAS_PATH)
            if (width, height) != (ATLAS_WIDTH, ATLAS_HEIGHT):
                errors.append(
                    f"icon atlas must be {ATLAS_WIDTH}x{ATLAS_HEIGHT}, got {width}x{height}"
                )
        except (OSError, ValueError) as error:
            errors.append(str(error))
    return errors


def validate_all() -> list[str]:
    pokemon = read_json(POKEMON_PATH)
    encounters = read_json(ENCOUNTERS_PATH)
    errors = validate_inputs(pokemon, encounters)
    for mode, (path, expected_locations) in VANILLA_ENCOUNTERS.items():
        errors.extend(
            f"{path.name}: {error}"
            for error in validate_inputs(
                pokemon,
                read_json(path),
                expected_locations=expected_locations,
                require_grass_maps=False,
                expected_mode=mode,
            )
        )
    return errors


def main() -> int:
    errors = validate_all()
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("OK: canonical data and assets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
