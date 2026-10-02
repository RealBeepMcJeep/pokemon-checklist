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
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.build_qr_catalog import verify_catalog
from tools.qr_codec import decode_png
from PIL import Image

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
        image_path = (catalog / image_relpath).resolve()
        if not image_path.is_relative_to(catalog.resolve()):
            raise GalleryBuildError(f"Unsafe original image path for {name}")
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
    report = verify_catalog(catalog)
    if not report["ok"] or report["checked"] != EXPECTED_RECORDS or report["signatureVerified"] != EXPECTED_RECORDS:
        raise GalleryBuildError(f"Ordinary QR offline verification failed: {report}")
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


def _load_gifts(root: Path) -> list[dict[str, Any]]:
    catalog = root / "references/qr-gifts"
    manifest = _read_json(catalog / "manifest.json", "promotional gift manifest")
    events = manifest.get("events")
    expected = {"magearna-us-american-region": (801, 5, "MagearnaEvent"),
                "partner-cap-pikachu-na-pal": (25, 9, "CapPikachuEvent")}
    if not isinstance(events, list) or len(events) != 2 or {e.get("id") for e in events} != set(expected):
        raise GalleryBuildError("Expected exactly the two source-backed promotional gifts")
    types = _read_json(root / "references/qr-codes/gen7-form-types.json", "canonical types")["typesBySpeciesForm"]
    hosts = {"www.pokemon.com", "mcdn.pokemon.com", "bulbapedia.bulbagarden.net",
             "archives.bulbagarden.net", "www.nintendo-insider.com", "www.serebii.net", "raw.githubusercontent.com"}
    def source_url(value: str) -> None:
        parsed = urlsplit(value)
        if parsed.scheme != "https" or parsed.hostname not in hosts or parsed.username or parsed.password or parsed.port not in (None, 443):
            raise GalleryBuildError(f"Unsafe gift source URL: {value!r}")
    def asset(relative: str, digest: str) -> tuple[Path, bytes]:
        if not isinstance(relative, str) or Path(relative).is_absolute() or ".." in Path(relative).parts:
            raise GalleryBuildError("Unsafe gift asset path")
        path = (catalog / relative).resolve()
        if not path.is_relative_to(catalog.resolve()):
            raise GalleryBuildError("Unsafe gift asset path")
        data = path.read_bytes()
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest) or hashlib.sha256(data).hexdigest() != digest:
            raise GalleryBuildError(f"Gift asset hash mismatch: {relative}")
        return path, data
    cards = []
    for event in events:
        dex, key, family = expected[event["id"]]
        obs = event["payload_observations"]
        for url in [event["image_page_source"], event["image_direct_source"], obs["family_mapping_source"], *[s["source"] for s in event["source_quotes"]]]:
            source_url(url)
        image_path, _ = asset(event["asset_path"], event["asset_sha256"])
        _, raw = asset(event["raw_payload_path"], event["raw_payload_sha256"])
        scan_path, scan = asset(event["presentation_image"], event.get("presentation_sha256", event["asset_sha256"]))
        if (event["dex_number"] != dex or len(raw) != 106 or raw.hex() != event["raw_payload_hex"]
                or raw[96:100] != b"POKE" or int.from_bytes(raw[100:104], "little") != key
                or obs["qr_count"] != 1 or obs["payload_bytes"] != 106 or obs["POKE_marker_offset"] != 96
                or obs["MemeCrypto_key_index_observed"] != key or obs["event_family_name_in_pinned_PKHeX_enum"] != family
                or obs["signature_verified"] is not False or obs["console_scan_tested"] is not False):
            raise GalleryBuildError("Gift payload/family evidence drift")
        if decode_png(image_path) != raw or decode_png(scan_path) != raw:
            raise GalleryBuildError("Gift source/presentation raw payload mismatch")
        with Image.open(image_path) as original, Image.open(scan_path) as presentation:
            if presentation.size != (147, 147):
                raise GalleryBuildError("Gift scanning image must preserve its verified square")
            crop = event.get("presentation_crop_box")
            if crop is not None and (crop != [216, 20, 363, 167] or original.crop(crop).convert("RGB").tobytes() != presentation.convert("RGB").tobytes()):
                raise GalleryBuildError("Gift presentation crop drift")
        event = dict(event)
        event["types"] = types[f"{dex}:0"]
        event["image_data"] = "data:image/png;base64," + base64.b64encode(scan).decode("ascii")
        cards.append(event)
    return cards


def _render_gift(event: dict[str, Any]) -> str:
    steps = " ".join(event["unlock_and_redeem"])
    details = "Eligible games: " + ", ".join(event["eligible_games"]) + ". Region: " + event["region_applicability"] + " Prerequisites and redemption: " + steps
    sprite_note = "Base species icon; cap not pictured." if event["dex_number"] == 25 else "Base species icon."
    card = _render_card({"id": event["dex_number"], "name": event["display_name"], "form_label": "Event gift",
        "form_id": 0, "types": event["types"], "categories": [], "source_url": event["image_page_source"],
        "source_title": event["display_name"] + " distribution source", "image_data": event["image_data"]})
    card = card.replace('class="qr-card"', f'class="gift-card" data-gift="{_escape(event["id"])}" data-scan-details="{_escape(details)}"')
    card = card.replace('Source library membership', 'Promotional gift — not an ordinary Dex scan')
    card = card.replace('Pokédex QR code', 'promotional gift QR code').replace('Original ', 'Source-backed ')
    info = f'<span class="dex-form">{_escape(sprite_note)}</span><span class="gift-details">{_escape(details)}</span>'
    info += f'<span class="gift-details">{_escape(event["expiry"])} Repeat/per-save limit unknown.</span>'
    card = card.replace('</span></button>', info + '</span></button>')
    urls = list(dict.fromkeys([event["image_page_source"], *[s["source"] for s in event["source_quotes"]]]))
    links = " · ".join(f'<a href="{_escape(url)}" target="_blank" rel="noopener noreferrer">{_escape(urlsplit(url).hostname)}</a>' for url in urls)
    return card.replace('</article>', f'<p class="gift-sources">Sources: {links}</p></article>')


def compile_gallery(root: Path = ROOT) -> str:
    root = Path(root).resolve()
    try:
        gifts = _load_gifts(root)
        records, type_names, atlas = _load_source_data(root)
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise GalleryBuildError(f"Source verification failed: {error}") from error
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
        "__GIFT_CARDS__": ("\n".join(_render_gift(event) for event in gifts), 1),
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
