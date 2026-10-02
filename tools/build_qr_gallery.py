#!/usr/bin/env python3
"""Compile the verified ordinary Gen VII QR archive into a standalone HTML page."""

from __future__ import annotations

import argparse
import base64
import hashlib
import html
import json
from pathlib import Path
import re
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "references" / "qr-codes"
MANIFEST = CATALOG / "manifest.json"
FORM_TYPES = CATALOG / "gen7-form-types.json"
TEMPLATE = ROOT / "tools" / "qr_gallery_template.html"
ATLAS = ROOT / "assets" / "gen7-icons.png"
OUTPUT = ROOT / "qr.html"
EXPECTED_RECORDS = 244
EXPECTED_CATEGORY_COUNTS = {"sun-moon": 186, "ultra-sun-ultra-moon": 244}
PKHEX_COMMIT = "542111fc8584ff29c9d1455553b8acd0e1f8a59a"

CATEGORY_LABELS = {
    "sun-moon": "Sun / Moon",
    "ultra-sun-ultra-moon": "Ultra Sun / Ultra Moon",
}


class GalleryBuildError(ValueError):
    """Raised when source evidence is inconsistent or incomplete."""


def _read_json(path: Path, description: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise GalleryBuildError(f"Cannot read {description}: {path}") from error
    if not isinstance(value, dict):
        raise GalleryBuildError(f"{description} must be a JSON object")
    return value


def _escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def _form_label(record: dict[str, Any]) -> str:
    form_id = record["decoded"]["formId"]
    if form_id == 0:
        return "Standard"
    source_title = record["source"]["title"]
    if not isinstance(source_title, str) or not source_title.startswith("File:"):
        raise GalleryBuildError(f"Invalid source file title for form {form_id}: {source_title!r}")
    stem = Path(source_title[5:]).stem
    stem = re.sub(r"\s+VII QR$", "", stem)
    name = record["decoded"]["species"]["name"]
    prefix = f"{name}-"
    if not stem.startswith(prefix) or not stem[len(prefix):].strip():
        raise GalleryBuildError(f"Cannot derive a source-backed form label from {source_title!r}")
    return stem[len(prefix):].replace("_", " ").strip()


def _load_source_data(root: Path) -> tuple[list[dict[str, Any]], list[str], bytes]:
    catalog = root / "references" / "qr-codes"
    manifest = _read_json(catalog / "manifest.json", "QR source manifest")
    type_data = _read_json(catalog / "gen7-form-types.json", "pinned Gen VII form-type metadata")
    provenance = manifest.get("provenance")
    records = manifest.get("records")
    if not isinstance(provenance, dict) or not isinstance(records, list):
        raise GalleryBuildError("QR manifest must include provenance and records")
    if len(records) != EXPECTED_RECORDS:
        raise GalleryBuildError(f"Expected {EXPECTED_RECORDS} verified archive records, found {len(records)}")
    if not isinstance(type_data.get("source"), dict):
        raise GalleryBuildError("Gen VII form-type metadata is missing source attribution")
    type_source = type_data["source"]
    if type_source.get("repository") != "kwsch/PKHeX" or type_source.get("commit") != PKHEX_COMMIT:
        raise GalleryBuildError("Gen VII form types must use the pinned PKHeX source revision")
    types_by_form = type_data.get("typesBySpeciesForm")
    form_counts = type_data.get("formCounts")
    type_names = type_source.get("typeValues")
    if not isinstance(types_by_form, dict) or not isinstance(form_counts, dict) or not isinstance(type_names, list):
        raise GalleryBuildError("Gen VII form-type metadata has an invalid schema")
    if not all(isinstance(value, str) for value in type_names):
        raise GalleryBuildError("Gen VII type list must contain names")

    names_path = root / "data" / "pokemon.json"
    try:
        name_rows = json.loads(names_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise GalleryBuildError(f"Cannot read canonical species names from {names_path}") from error
    if not isinstance(name_rows, list):
        raise GalleryBuildError("data/pokemon.json must contain a list")
    names = {row.get("id"): row.get("name") for row in name_rows if isinstance(row, dict)}

    atlas_path = root / "assets" / "gen7-icons.png"
    try:
        atlas = atlas_path.read_bytes()
    except OSError as error:
        raise GalleryBuildError(f"Missing existing Gen VII icon atlas: {atlas_path}") from error
    if not atlas.startswith(b"\x89PNG\r\n\x1a\n"):
        raise GalleryBuildError("Gen VII icon atlas is not a PNG")

    counts = {category: 0 for category in CATEGORY_LABELS}
    normalized: list[dict[str, Any]] = []
    for row in records:
        if not isinstance(row, dict):
            raise GalleryBuildError("Manifest record must be an object")
        if not isinstance(row.get("source"), dict) or not isinstance(row.get("image"), dict):
            raise GalleryBuildError("Manifest record is missing source or image data")
        if not isinstance(row.get("decoded"), dict) or not isinstance(row.get("audit"), dict):
            raise GalleryBuildError("Manifest record is missing decoded or audit data")
        source: dict[str, Any] = row["source"]
        image: dict[str, Any] = row["image"]
        decoded: dict[str, Any] = row["decoded"]
        audit: dict[str, Any] = row["audit"]
        if audit.get("status") != "verified-ordinary-dex" or audit.get("family") != "ordinary-dex":
            raise GalleryBuildError(f"Refusing unverified/non-ordinary record: {source.get('title')}")
        species = decoded.get("species")
        if not isinstance(species, dict):
            raise GalleryBuildError("Decoded record is missing canonical species identity")
        species_id = species.get("id")
        name = species.get("name")
        form_id = decoded.get("formId")
        if not isinstance(species_id, int) or species_id < 1 or species_id > 807:
            raise GalleryBuildError(f"Invalid National Pokédex ID: {species_id!r}")
        if not isinstance(name, str) or names.get(species_id) != name:
            raise GalleryBuildError(f"Manifest name does not match canonical species #{species_id}: {name!r}")
        if not isinstance(form_id, int) or form_id < 0:
            raise GalleryBuildError(f"Invalid decoded form ID for {name}: {form_id!r}")
        if str(species_id) not in form_counts or form_id >= form_counts[str(species_id)]:
            raise GalleryBuildError(f"Form {form_id} is outside the pinned Gen VII table for {name}")
        key = f"{species_id}:{form_id}"
        types = types_by_form.get(key)
        if not isinstance(types, list) or not 1 <= len(types) <= 2:
            raise GalleryBuildError(f"Missing pinned Gen VII type row for {name} form {form_id}")
        if any(not isinstance(value, str) or value not in type_names for value in types):
            raise GalleryBuildError(f"Invalid pinned type row for {name} form {form_id}")
        categories = source.get("categories")
        if not isinstance(categories, list) or not categories or any(category not in CATEGORY_LABELS for category in categories):
            raise GalleryBuildError(f"Invalid source-library membership for {name}")
        categories = [category for category in CATEGORY_LABELS if category in categories]
        for category in categories:
            counts[category] += 1
        image_relpath = image.get("file")
        if not isinstance(image_relpath, str) or Path(image_relpath).is_absolute() or ".." in Path(image_relpath).parts:
            raise GalleryBuildError(f"Invalid original image path for {name}")
        image_path = catalog / image_relpath
        try:
            image_bytes = image_path.read_bytes()
        except OSError as error:
            raise GalleryBuildError(f"Missing original QR PNG: {image_path}") from error
        if not image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
            raise GalleryBuildError(f"Original QR is not a PNG: {image_path}")
        digest = hashlib.sha256(image_bytes).hexdigest()
        if row.get("imageSha256") != digest:
            raise GalleryBuildError(f"Original image hash mismatch for {source.get('title')}")
        if image.get("bytes") != len(image_bytes):
            raise GalleryBuildError(f"Original image size mismatch for {source.get('title')}")
        form_label = _form_label(row)
        source_url = source.get("originalUrl")
        source_title = source.get("title")
        if not isinstance(source_url, str) or not source_url.startswith("https://archives.bulbagarden.net/"):
            raise GalleryBuildError(f"Invalid original archive URL for {name}")
        if not isinstance(source_title, str):
            raise GalleryBuildError(f"Missing source title for {name}")
        normalized.append({
            "id": species_id,
            "name": name,
            "form_id": form_id,
            "form_label": form_label,
            "types": types,
            "categories": categories,
            "source_url": source_url,
            "source_title": source_title,
            "image_data": "data:image/png;base64," + base64.b64encode(image_bytes).decode("ascii"),
        })
    if counts != EXPECTED_CATEGORY_COUNTS:
        raise GalleryBuildError(f"Source-library membership counts changed: {counts!r}")
    return normalized, type_names, atlas


def _render_card(record: dict[str, Any]) -> str:
    dex = record["id"]
    name = record["name"]
    form = record["form_label"]
    types = record["types"]
    categories = record["categories"]
    library_labels = [CATEGORY_LABELS[category] for category in categories]
    search_terms = " ".join((name, str(dex), f"{dex:03d}", f"#{dex:03d}", form))
    type_tags = "".join(f'<span class="type-chip">{_escape(value)}</span>' for value in types)
    sources = "".join(f'<span class="source-chip">{_escape(value)} archive</span>' for value in library_labels)
    aria = f"Open scan view for #{dex:03d} {name}, {form} form"
    return (
        f'<article class="qr-card" data-dex="{dex}" data-name="{_escape(name)}" '
        f'data-form="{record["form_id"]}" data-form-label="{_escape(form)}" '
        f'data-types="{_escape(" ".join(types))}" data-libraries="{_escape(" ".join(categories))}" '
        f'data-library-labels="{_escape(", ".join(library_labels))}" '
        f'data-search="{_escape(search_terms)}" data-source-url="{_escape(record["source_url"])}" '
        f'data-source-title="{_escape(record["source_title"])}">'
        f'<button class="card-open" type="button" aria-label="{_escape(aria)}">'
        f'<span class="qr-frame"><img class="qr-original" src="{record["image_data"]}" '
        f'alt="Original { _escape(name) } { _escape(form) } Pokédex QR code" draggable="false"></span>'
        f'<span class="card-meta"><span class="identity"><span class="sprite-crop" aria-hidden="true">'
        f'<img class="sprite-atlas" data-dex="{dex}" alt=""></span>'
        f'<span class="names"><strong class="species-name">{_escape(name)}</strong>'
        f'<span class="dex-form">National Pokédex #{dex:03d} · { _escape(form) } form</span></span></span>'
        f'<span class="type-list" aria-label="Types: {_escape(" and ".join(types))}">{type_tags}</span>'
        f'<span><span class="source-label">Source library membership</span><span class="source-list">{sources}</span></span>'
        f'</span></button></article>'
    )


def compile_gallery(root: Path = ROOT) -> str:
    root = Path(root).resolve()
    records, type_names, atlas = _load_source_data(root)
    try:
        template = (root / "tools" / "qr_gallery_template.html").read_text(encoding="utf-8")
    except OSError as error:
        raise GalleryBuildError(f"Cannot read gallery template under {root}") from error
    values = {
        "__CARD_COUNT__": (str(len(records)), 2),
        "__TYPE_OPTIONS__": ("".join(
            f'<option value="{_escape(type_name)}">{_escape(type_name)}</option>'
            for type_name in type_names
        ), 1),
        "__CARDS__": ("\n".join(_render_card(record) for record in records), 1),
        "__ATLAS_DATA_URI__": ("data:image/png;base64," + base64.b64encode(atlas).decode("ascii"), 1),
    }
    for marker, (replacement, occurrences) in values.items():
        if template.count(marker) != occurrences:
            raise GalleryBuildError(f"Template must contain exactly {occurrences} {marker} placeholder(s)")
        template = template.replace(marker, replacement)
    if "__" in template and re.search(r"__[A-Z][A-Z0-9_]+__", template):
        raise GalleryBuildError("Unresolved template placeholders remain")
    return template


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT, help="output HTML path (default: qr.html)")
    parser.add_argument("--check", action="store_true", help="rebuild in memory and verify output is current")
    args = parser.parse_args(argv)
    try:
        expected = compile_gallery(ROOT).encode("utf-8")
        if args.check:
            try:
                actual = args.output.read_bytes()
            except OSError:
                actual = None
            if actual != expected:
                print(f"QR gallery is missing or stale: {args.output}", file=sys.stderr)
                return 1
            print(f"QR gallery is reproducible: {args.output} ({len(expected):,} bytes)")
            return 0
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(expected)
        print(f"Built {args.output} ({len(expected):,} bytes, {EXPECTED_RECORDS} original QR records)")
        return 0
    except (GalleryBuildError, OSError) as error:
        print(f"QR gallery build failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
