#!/usr/bin/env python3
"""Validate source JSON and optionally refresh names or PDF image assets.

Encounter transcription is intentionally kept only in data/encounters.json.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import unicodedata
from http.client import HTTPSConnection
from io import BytesIO
from pathlib import Path
from typing import cast

from build import validate_inputs
from PIL import Image, ImageDraw, ImageFont
from pypdf import PdfReader
from pypdf.generic import ContentStream

ROOT = Path(__file__).resolve().parents[1]
PDF = ROOT / "references" / "Wild Pokemon Locations.pdf"
DATA = ROOT / "data"
ASSETS = ROOT / "assets" / "locations"
POKEMON_PATH = DATA / "pokemon.json"
ENCOUNTERS_PATH = DATA / "encounters.json"
POKEAPI_HOST = "raw.githubusercontent.com"
POKEAPI_PATH = "/PokeAPI/pokeapi/master/data/v2/csv/pokemon_species_names.csv"

NUMBERED_MAPS = {
    "assets/locations/route-1-map.png": 6,
    "assets/locations/hau-oli-city-map.jpg": 4,
    "assets/locations/route-2-map.jpg": 5,
    "assets/locations/route-3-map.jpg": 3,
    "assets/locations/route-5-map.jpg": 5,
    "assets/locations/route-6-map.png": 3,
    "assets/locations/mount-hokulani-map.png": 3,
}

# (PDF page, image index) -> (output filename, kind). Tiny transparent Word
# artifacts are omitted; map entries receive their PDF vector number overlays.
ASSET_SPECS = {
    (1, 0): ("title.png", "title"),
    (2, 0): ("route-1-map.png", "map"),
    (3, 0): ("melemele-island.jpg", "island-map"),
    (4, 0): ("route-1.jpg", "location"),
    (6, 0): ("hau-oli-city.jpg", "location"),
    (6, 1): ("hau-oli-city-map.jpg", "map"),
    (7, 0): ("trainers-school.jpg", "location"),
    (8, 0): ("route-2.jpg", "location"),
    (8, 1): ("route-2-map.jpg", "map"),
    (9, 0): ("hau-oli-cemetery.jpg", "location"),
    (10, 0): ("sandy-cave.jpg", "location"),
    (11, 0): ("verdant-cavern.jpg", "location"),
    (12, 0): ("route-3.jpg", "location"),
    (12, 1): ("route-3-map.jpg", "map"),
    (13, 0): ("kalae-bay.jpg", "location"),
    (14, 0): ("melemele-meadow.jpg", "location"),
    (15, 0): ("seaward-cave.jpg", "location"),
    (16, 0): ("ten-carat-hill.jpg", "location"),
    (17, 0): ("melemele-sea.jpg", "location"),
    (18, 0): ("akala-island.jpg", "island-map"),
    (19, 0): ("route-4.jpg", "location"),
    (20, 0): ("paniola-ranch.jpg", "location"),
    (21, 0): ("route-5.jpg", "location"),
    (21, 1): ("route-5-map.jpg", "map"),
    (23, 0): ("brooklet-hill.jpg", "location"),
    (25, 0): ("route-6.jpg", "location"),
    (25, 1): ("route-6-map.png", "map"),
    (26, 0): ("digletts-tunnel.jpg", "location"),
    (27, 0): ("route-7.jpg", "location"),
    (28, 0): ("wela-volcano-park.jpg", "location"),
    (29, 0): ("dividing-peak-tunnel.jpg", "location"),
    (30, 0): ("route-8.jpg", "location"),
    (31, 0): ("lush-jungle.jpg", "location"),
    (32, 0): ("lush-jungle-cave.jpg", "location"),
    (33, 0): ("hano-beach.jpg", "location"),
    (34, 0): ("route-9.jpg", "location"),
    (35, 0): ("memorial-hill.jpg", "location"),
    (36, 0): ("akala-outskirts.jpg", "location"),
    (37, 0): ("ulaula-island.jpg", "island-map"),
    (38, 0): ("malie-city.jpg", "location"),
    (39, 0): ("malie-garden.jpg", "location"),
    (40, 0): ("route-10.jpg", "location"),
    (41, 0): ("route-11.jpg", "location"),
    (42, 0): ("mount-hokulani.jpg", "location"),
    (42, 1): ("mount-hokulani-map.png", "map"),
    (43, 0): ("route-12.jpg", "location"),
    (44, 0): ("blush-mountain.jpg", "location"),
    (45, 0): ("ulaula-beach.jpg", "location"),
    (45, 1): ("route-13.jpg", "location"),
    (46, 0): ("tapu-village.jpg", "location"),
    (47, 0): ("mount-lanakila.jpg", "location"),
    (48, 0): ("route-14.jpg", "location"),
    (49, 0): ("thrifty-megamart.jpg", "location"),
    (50, 0): ("route-15-16.jpg", "location"),
    (51, 0): ("ulaula-meadow.jpg", "location"),
    (52, 0): ("route-17.jpg", "location"),
    (53, 0): ("haina-desert.jpg", "location"),
    (54, 0): ("victory-road.jpg", "location"),
    (55, 0): ("poni-island.jpg", "island-map"),
    (56, 0): ("seafolk-village.jpg", "location"),
    (57, 0): ("poni-wilds.jpg", "location"),
    (58, 0): ("exeggutor-island.jpg", "location"),
    (59, 0): ("ancient-poni-path.jpg", "location"),
    (60, 0): ("ponibreaker-coast.jpg", "location"),
    (61, 0): ("vast-poni-canyon.jpg", "location"),
    (62, 0): ("poni-grove.jpg", "location"),
    (63, 0): ("poni-plains.jpg", "location"),
    (64, 0): ("poni-meadow.jpg", "location"),
    (65, 0): ("resolution-cave.jpg", "location"),
    (66, 0): ("poni-coast.jpg", "location"),
    (67, 0): ("poni-gauntlet.jpg", "location"),
}


def read_json(path: Path, label: str) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Cannot read {label}: {path}") from error


def parse_int(value: object, context: str) -> int:
    try:
        return int(str(value))
    except (TypeError, ValueError) as error:
        raise ValueError(f"Invalid integer for {context}: {value!r}") from error


def parse_float(value: object, context: str) -> float:
    try:
        return float(str(value))
    except (TypeError, ValueError) as error:
        raise ValueError(f"Invalid number for {context}: {value!r}") from error


def slugify(name: str) -> str:
    name = name.lower().replace("♀", "-f").replace("♂", "-m").replace("’", "'")
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", name.replace("'", "").replace(".", "")).strip("-")


def download_pokemon_csv() -> bytes:
    connection = HTTPSConnection(POKEAPI_HOST, timeout=30)
    try:
        connection.request(
            "GET", POKEAPI_PATH, headers={"User-Agent": "pokemon-checklist-builder/1"}
        )
        response = connection.getresponse()
        if response.status != 200:
            raise RuntimeError(f"PokéAPI CSV request failed with HTTP {response.status}")
        return response.read()
    finally:
        connection.close()


def refresh_pokemon() -> list[dict]:
    names: dict[int, str] = {}
    raw = download_pokemon_csv().decode("utf-8-sig").splitlines()
    for row in csv.DictReader(raw):
        if row["local_language_id"] == "9":
            dex = parse_int(row["pokemon_species_id"], "Pokédex ID")
            if 1 <= dex <= 807:
                names[dex] = row["name"]
    if set(names) != set(range(1, 808)):
        raise ValueError("PokéAPI snapshot did not contain exactly IDs 1..807")
    pokemon = [{"id": dex, "name": names[dex], "slug": slugify(names[dex])} for dex in range(1, 808)]
    POKEMON_PATH.write_text(
        json.dumps(pokemon, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return pokemon


def compose_numbered_map(image: Image.Image, page, reader, resource_name: str) -> Image.Image:
    """Render the PDF's vector grass markers over its embedded map raster."""
    placements = []

    def find_placement(operator, operands, matrix, _text_matrix) -> None:
        if operator == b"Do" and str(operands[0]).lstrip("/") == resource_name:
            placements.append(tuple(parse_float(value, "map placement") for value in matrix))

    page.extract_text(visitor_operand_before=find_placement)
    if len(placements) != 1:
        raise ValueError(f"Expected one placement for map resource {resource_name}")
    scale_x, _, _, scale_y, offset_x, offset_y = placements[0]
    map_box = (offset_x, offset_y, offset_x + scale_x, offset_y + scale_y)

    circles: list[dict] = []
    path: list[tuple[float, float]] = []
    pending: int | None = None
    for operands, operator in ContentStream(page.get_contents(), reader).operations:
        if operator == b"m":
            path = [(parse_float(operands[0], "marker x"), parse_float(operands[1], "marker y"))]
        elif operator == b"c" and path:
            path.extend(
                (
                    parse_float(operands[index], "marker curve x"),
                    parse_float(operands[index + 1], "marker curve y"),
                )
                for index in (0, 2, 4)
            )
        elif operator in {b"f", b"f*", b"S"} and path:
            xs = [point[0] for point in path]
            ys = [point[1] for point in path]
            bounds = (min(xs), min(ys), max(xs), max(ys))
            left, bottom, right, top = bounds
            map_left, map_bottom, map_right, map_top = map_box
            marker = (
                map_left <= left < right <= map_right
                and map_bottom <= bottom < top <= map_top
                and 10 < right - left < 80
                and 10 < top - bottom < 80
                and len(path) >= 10
            )
            duplicate = any(
                sum(abs(a - b) for a, b in zip(bounds, item["bounds"], strict=True)) < 1
                for item in circles
            )
            if marker and not duplicate:
                circles.append({"bounds": bounds, "label": None})
                pending = len(circles) - 1
            path = []
        elif operator in {b"n", b"re"}:
            path = []
        elif operator == b"TJ" and pending is not None:
            text = "".join(
                str(value) for value in operands[0] if isinstance(value, (str, bytes))
            ).strip()
            if text.isdigit():
                circles[pending]["label"] = text
                pending = None

    if not circles or any(item["label"] is None for item in circles):
        raise ValueError(f"Could not recover every numbered marker for {resource_name}")

    result = image.convert("RGB")
    draw = ImageDraw.Draw(result)
    pixel_x, pixel_y = result.width / scale_x, result.height / scale_y
    font_size = max(10, round(14.04 * min(pixel_x, pixel_y)))
    try:
        font = ImageFont.truetype("DejaVuSerif-Bold.ttf", font_size)
    except OSError:
        font = ImageFont.load_default()

    for item in circles:
        left, bottom, right, top = item["bounds"]
        bounds = (
            round((left - offset_x) * pixel_x),
            round(result.height - (top - offset_y) * pixel_y),
            round((right - offset_x) * pixel_x),
            round(result.height - (bottom - offset_y) * pixel_y),
        )
        draw.ellipse(bounds, fill="white", outline="black", width=max(2, round(min(pixel_x, pixel_y) * 3)))
        draw.ellipse(bounds, outline="#ef1010", width=max(1, round(min(pixel_x, pixel_y) * 2)))
        label = item["label"]
        text_box = draw.textbbox((0, 0), label, font=font)
        width, height = text_box[2] - text_box[0], text_box[3] - text_box[1]
        center_x, center_y = (bounds[0] + bounds[2]) / 2, (bounds[1] + bounds[3]) / 2
        draw.text(
            (center_x - width / 2, center_y - height / 2 - text_box[1]),
            label,
            fill="black",
            font=font,
        )
    return result


def extract_assets() -> None:
    reader = PdfReader(str(PDF))
    ASSETS.mkdir(parents=True, exist_ok=True)
    for (page_number, image_index), (filename, kind) in ASSET_SPECS.items():
        images = list(reader.pages[page_number - 1].images)
        if image_index >= len(images):
            raise ValueError(f"Missing PDF image {page_number}:{image_index}")
        image = images[image_index]
        suffix = Path(filename).suffix.lower()
        decoded = image.image
        if kind == "map":
            if decoded is None:
                raise ValueError(f"PDF map {page_number}:{image_index} could not be decoded")
            rendered = compose_numbered_map(
                decoded, reader.pages[page_number - 1], reader, Path(image.name).stem
            )
            buffer = BytesIO()
            rendered.save(buffer, format="PNG" if suffix == ".png" else "JPEG", quality=95)
            payload = buffer.getvalue()
        elif suffix == Path(image.name).suffix.lower() and suffix in {".png", ".jpg", ".jpeg"}:
            payload = image.data
        else:
            if decoded is None:
                raise ValueError(f"PDF image {page_number}:{image_index} could not be decoded")
            buffer = BytesIO()
            decoded.save(buffer, format="PNG" if suffix == ".png" else "JPEG")
            payload = buffer.getvalue()
        (ASSETS / filename).write_bytes(payload)


def validate_numbered_maps() -> list[str]:
    errors = []
    for path, marker_count in NUMBERED_MAPS.items():
        try:
            image = Image.open(ROOT / path).convert("RGB")
            red_pixels = sum(
                1
                for red, green, blue in image.getdata()
                if red > 150 and red > green * 1.5 and red > blue * 1.5
            )
        except OSError as error:
            errors.append(f"Cannot inspect numbered map {path}: {error}")
            continue
        if red_pixels < marker_count * 20:
            errors.append(f"Numbered overlays are missing from map {path}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh-pokemon", action="store_true")
    parser.add_argument("--extract-assets", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()

    pokemon = cast(
        list[dict],
        refresh_pokemon()
        if args.refresh_pokemon
        else read_json(POKEMON_PATH, "Pokémon data"),
    )
    encounters = cast(dict, read_json(ENCOUNTERS_PATH, "encounter data"))
    if args.extract_assets:
        extract_assets()

    errors = validate_inputs(pokemon, encounters) + validate_numbered_maps()
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    if args.validate:
        locations = sum(len(island["locations"]) for island in encounters["islands"])
        print(f"OK: 807 Pokémon, {len(encounters['islands'])} islands, {locations} locations, {len(encounters['assets'])} assets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
