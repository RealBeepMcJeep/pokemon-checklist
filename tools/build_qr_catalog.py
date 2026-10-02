"""Fetch and audit the two Bulbagarden Gen VII ordinary-QR source categories."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from hashlib import sha1, sha256
import json
from pathlib import Path
import re
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.qr_codec import decode_png, verify_ordinary_payload

API = "https://archives.bulbagarden.net/w/api.php"
USER_AGENT = "PokemonChecklistQRResearch/1.0 (offline Gen VII QR protocol catalogue)"
CATEGORIES = {
    "sun-moon": "Category:Pokémon_Sun_and_Moon_QR_codes",
    "ultra-sun-ultra-moon": "Category:Pokémon_Ultra_Sun_and_Ultra_Moon_QR_codes",
}


def _request_json(params: dict) -> dict:
    query = urlencode(params)
    for attempt in range(3):
        try:
            request = Request(f"{API}?{query}", headers={"User-Agent": USER_AGENT})
            with urlopen(request, timeout=30) as response:
                return json.load(response)
        except HTTPError as error:
            if error.code not in (429, 500, 502, 503, 504) or attempt == 2:
                raise
        except (TimeoutError, URLError):
            if attempt == 2:
                raise
        time.sleep(0.5 * (2 ** attempt))
    raise RuntimeError("MediaWiki API retry loop exhausted")


def fetch_category_members(category: str) -> list[dict]:
    params = {
        "action": "query", "format": "json", "list": "categorymembers",
        "cmtitle": category, "cmtype": "file", "cmlimit": "max",
    }
    members: list[dict] = []
    while True:
        response = _request_json(params)
        members.extend(response.get("query", {}).get("categorymembers", []))
        continuation = response.get("continue")
        if not continuation:
            break
        params.update(continuation)
    return members


def fetch_image_info(titles: list[str]) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for start in range(0, len(titles), 50):
        batch = titles[start:start + 50]
        response = _request_json({
            "action": "query", "format": "json", "prop": "imageinfo",
            "iiprop": "url|size|sha1", "titles": "|".join(batch),
        })
        for page in response.get("query", {}).get("pages", {}).values():
            infos = page.get("imageinfo", [])
            if infos:
                info = infos[0]
                result[page["title"]] = {
                    "pageid": page["pageid"], "title": page["title"],
                    "original": info["url"], "sha1": info.get("sha1"),
                    "size": info.get("size"), "width": info.get("width"),
                    "height": info.get("height"),
                }
    return result


def _from_mediawiki_sha1(value: str) -> bytes:
    if re.fullmatch(r"[0-9a-fA-F]{40}", value):
        return bytes.fromhex(value)
    number = int(value, 36)
    return number.to_bytes(20, "big")


def _has_source_sha1(path: Path, expected: str | None) -> bool:
    if not path.is_file() or not expected:
        return False
    try:
        return sha1(path.read_bytes()).digest() == _from_mediawiki_sha1(expected)
    except (ValueError, OverflowError):
        return False


def _download_original(info: dict, destination: Path) -> tuple[str, str | None]:
    if _has_source_sha1(destination, info.get("sha1")):
        return str(destination), None
    for attempt in range(3):
        try:
            request = Request(info["original"], headers={"User-Agent": USER_AGENT})
            with urlopen(request, timeout=30) as response:
                data = response.read()
            if info.get("sha1") and sha1(data).digest() != _from_mediawiki_sha1(info["sha1"]):
                raise ValueError("downloaded bytes do not match MediaWiki SHA-1")
            temporary = destination.with_suffix(destination.suffix + ".part")
            temporary.write_bytes(data)
            temporary.replace(destination)
            return str(destination), None
        except (HTTPError, URLError, TimeoutError, ValueError) as error:
            if isinstance(error, HTTPError) and error.code not in (429, 500, 502, 503, 504):
                return "", str(error)
            if attempt == 2:
                return "", str(error)
            time.sleep(0.5 * (2 ** attempt))
    return "", "download failed"


def _source_label(title: str) -> str:
    label = title.removeprefix("File:").rsplit(".", 1)[0]
    return re.sub(r"\s+VII\s+QR$", "", label, flags=re.IGNORECASE).strip()


def _normalize_label(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def inspect_source_image(
    image_path: str | Path,
    info: dict,
    categories: set[str],
    species_names: dict[int, str],
) -> dict:
    """Preserve original provenance and report protocol/label disagreements."""
    path = Path(image_path)
    image_bytes = path.read_bytes()
    source = {
        "pageId": info.get("pageid"), "title": info["title"],
        "originalUrl": info.get("original"), "sourceSha1": info.get("sha1"),
        "categories": sorted(categories),
    }
    record = {
        "source": source,
        "image": {"file": path.name, "bytes": len(image_bytes)},
        "imageSha256": sha256(image_bytes).hexdigest(),
        "payload": None, "decoded": None,
        "audit": {"status": "qr-decode-failed", "sourceLabelMismatch": None},
    }
    try:
        raw = decode_png(path)
    except Exception as error:
        record["audit"]["error"] = f"{type(error).__name__}: {error}"
        return record
    record["payload"] = {
        "rawHex": raw.hex(), "rawSha256": sha256(raw).hexdigest(),
        "byteLength": len(raw),
    }
    marker = raw.rfind(b"POKE")
    if marker >= 0 and marker + 8 <= len(raw):
        record["payload"]["framing"] = {
            "markerOffset": marker, "marker": "POKE",
            "preMarkerHex": raw[max(0, marker - 2):marker].hex(),
            "keyIndex": int.from_bytes(raw[marker + 4:marker + 8], "little"),
            "suffixHex": raw[marker + 8:].hex(),
        }
    try:
        decoded = verify_ordinary_payload(raw)
    except ValueError as error:
        message = str(error)
        unsupported = "unsupported MemeCrypto key index" in message
        record["audit"]["status"] = (
            "unsupported-key-family" if unsupported
            else "signature-invalid-or-unsupported"
        )
        if unsupported and record["payload"].get("framing"):
            record["audit"]["unsupportedKeyIndex"] = record["payload"]["framing"]["keyIndex"]
        record["audit"]["error"] = message
        return record
    canonical_name = species_names.get(decoded.species_id)
    source_label = _source_label(info["title"])
    mismatch = (
        None if canonical_name is None
        else _normalize_label(canonical_name) not in _normalize_label(source_label)
    )
    record["payload"]["bodyHex"] = decoded.body.hex()
    record["decoded"] = {
        "species": {"id": decoded.species_id, "name": canonical_name},
        "formId": decoded.form, "genderCode": decoded.gender,
        "shinyFlag": decoded.shiny_flag, "shiny": decoded.shiny_flag != 0,
        "bothGendersFlag": decoded.both_genders_flag,
        "bodyBytes": len(decoded.body),
    }
    record["audit"] = {
        "status": "verified-ordinary-dex", "family": decoded.family,
        "keyIndex": decoded.key_index, "signatureVerified": True,
        "sourceLabel": source_label, "sourceLabelMismatch": mismatch,
        "canonicalSpeciesUnknown": canonical_name is None,
        "gameAcceptance": "not-console-tested",
    }
    return record


def _load_species_names(root: Path) -> dict[int, str]:
    rows = json.loads((root / "data" / "pokemon.json").read_text())
    return {int(row["id"]): row["name"] for row in rows}


def _summary(records: list[dict]) -> dict:
    counts = {name: 0 for name in CATEGORIES}
    for record in records:
        for category in record["source"]["categories"]:
            counts[category] += 1
    statuses: dict[str, int] = {}
    payload_hashes: set[str] = set()
    species: set[int] = set()
    forms: set[tuple[int, int]] = set()
    mismatches = []
    unknown_canonical = []
    for record in records:
        status = record["audit"]["status"]
        statuses[status] = statuses.get(status, 0) + 1
        payload = record.get("payload")
        if payload:
            payload_hashes.add(payload["rawSha256"])
        decoded = record.get("decoded")
        if decoded:
            sid = decoded["species"]["id"]
            species.add(sid)
            forms.add((sid, decoded["formId"]))
            if record["audit"].get("canonicalSpeciesUnknown"):
                unknown_canonical.append({"title": record["source"]["title"], "speciesId": sid})
            if record["audit"].get("sourceLabelMismatch"):
                mismatches.append({"title": record["source"]["title"], "species": decoded["species"]})
    return {
        "sourceFiles": len(records), "categoryMemberships": counts,
        "sharedSourcePages": sum(len(r["source"]["categories"]) == 2 for r in records),
        "sunMoonOnly": sum(r["source"]["categories"] == ["sun-moon"] for r in records),
        "ultraOnly": sum(r["source"]["categories"] == ["ultra-sun-ultra-moon"] for r in records),
        "uniquePayloads": len(payload_hashes), "verifiedSpecies": len(species),
        "verifiedSpeciesForms": len(forms), "statuses": statuses,
        "sourceLabelMismatches": mismatches,
        "unknownCanonicalSpecies": unknown_canonical,
    }


def _protocol_comparison(records: list[dict]) -> dict:
    def select(name: str, categories: set[str], *, ultra_species_only: bool = False,
               usum_additions: bool = False) -> list[dict]:
        out = []
        for record in records:
            if not record.get("decoded") or set(record["source"]["categories"]) != categories:
                continue
            decoded = record["decoded"]
            species = decoded["species"]
            if name == "shared-rowlet-butterfree" and species["name"] not in ("Rowlet", "Butterfree"):
                continue
            if name == "ultra-only-older" and species["name"] not in ("Ampharos", "Buneary"):
                continue
            if ultra_species_only and not (722 <= species["id"] <= 807):
                continue
            if usum_additions and not (
                803 <= species["id"] <= 807
                or (species["name"] == "Rockruff" and decoded["formId"] > 0)
                or (species["name"] == "Lycanroc" and decoded["formId"] == 2)
                or (species["name"] == "Necrozma" and decoded["formId"] > 0)
            ):
                continue
            out.append({
                "sourceTitle": record["source"]["title"],
                "categories": record["source"]["categories"],
                "species": species, "formId": decoded["formId"],
                "family": record["audit"]["family"], "keyIndex": record["audit"]["keyIndex"],
                "payloadBytes": record["payload"]["byteLength"],
                "payloadSha256": record["payload"]["rawSha256"],
                "framing": record["payload"].get("framing"),
            })
        return out
    return {
        "sharedRowletButterfree": select("shared-rowlet-butterfree", set(CATEGORIES)),
        "ultraOnlyOlderSpecies": select("ultra-only-older", {"ultra-sun-ultra-moon"}),
        "ultraOnlyGenVIIIntroductions": select(
            "ultra-only-gen7", {"ultra-sun-ultra-moon"}, ultra_species_only=True
        ),
        "ultraOnlyUSUMAdditions": select(
            "ultra-only-usum-additions", {"ultra-sun-ultra-moon"}, usum_additions=True
        ),
        "interpretation": (
            "Category membership and binary signature validity do not establish scan acceptance "
            "by either game's code or regional-Dex applicability."
        ),
    }


def build_catalog(root: str | Path, catalog_dir: str | Path) -> dict:
    root, catalog_dir = Path(root), Path(catalog_dir)
    catalog_dir.mkdir(parents=True, exist_ok=True)
    images_dir = catalog_dir / "images"
    images_dir.mkdir(exist_ok=True)
    page_members: dict[int, dict] = {}
    memberships: dict[int, set[str]] = {}
    for label, category in CATEGORIES.items():
        for member in fetch_category_members(category):
            pageid = int(member["pageid"])
            page_members[pageid] = {"pageid": pageid, "title": member["title"]}
            memberships.setdefault(pageid, set()).add(label)
    titles = [row["title"] for row in page_members.values()]
    infos = fetch_image_info(titles)
    downloads: dict[int, tuple[Path, dict, str | None]] = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {}
        for pageid, member in page_members.items():
            info = infos.get(member["title"])
            if not info:
                downloads[pageid] = (Path(), member, "missing imageinfo")
                continue
            extension = Path(info["original"].split("?", 1)[0]).suffix or ".png"
            path = images_dir / f"{pageid}{extension}"
            futures[pool.submit(_download_original, info, path)] = (pageid, path, info)
        for future in as_completed(futures):
            pageid, path, info = futures[future]
            _, error = future.result()
            downloads[pageid] = (path, info, error)
    species_names = _load_species_names(root)
    records = []
    for pageid in sorted(page_members):
        image_path, info, error = downloads[pageid]
        if error:
            records.append({
                "source": {"pageId": pageid, "title": page_members[pageid]["title"],
                           "originalUrl": info.get("original") if info else None,
                           "sourceSha1": info.get("sha1") if info else None,
                           "categories": sorted(memberships[pageid])},
                "image": {"file": None}, "imageSha256": None,
                "payload": None, "decoded": None,
                "audit": {"status": "download-failed", "error": error,
                          "sourceLabelMismatch": None},
            })
        else:
            record = inspect_source_image(image_path, info, memberships[pageid], species_names)
            record["image"]["file"] = str(image_path.relative_to(catalog_dir))
            records.append(record)
    manifest = {
        "schemaVersion": 1,
        "provenance": {
            "source": "Bulbagarden Archives MediaWiki API",
            "api": API,
            "categories": CATEGORIES,
            "protocolReference": "https://gbatemp.net/threads/pokemon-sun-and-moon-hacking-qr-codes.448369/",
            "verifier": "PKHeX MemeCrypto/MemeKey source at 542111fc8584ff29c9d1455553b8acd0e1f8a59a",
            "images": "originals; source SHA-1 and local SHA-256 retained",
            "consoleAcceptance": "not tested; category and signature are not acceptance evidence",
        },
        "records": records,
        "summary": _summary(records),
        "crossCategoryProtocolAudit": _protocol_comparison(records),
    }
    target = catalog_dir / "manifest.json"
    target.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return manifest


def verify_catalog(catalog_dir: str | Path) -> dict:
    catalog_dir = Path(catalog_dir)
    manifest = json.loads((catalog_dir / "manifest.json").read_text())
    errors = []
    checked = 0
    signature_verified = 0
    for record in manifest["records"]:
        title = record["source"]["title"]
        relative = record.get("image", {}).get("file")
        if not relative or not record.get("imageSha256"):
            errors.append({"title": title, "status": record["audit"]["status"]})
            continue
        image_path = catalog_dir / relative
        if not image_path.is_file():
            errors.append({"title": title, "status": "image-missing"})
            continue
        image_bytes = image_path.read_bytes()
        if sha256(image_bytes).hexdigest() != record["imageSha256"]:
            errors.append({"title": title, "status": "image-hash-mismatch"})
            continue
        source_hash = record["source"].get("sourceSha1")
        if source_hash and sha1(image_bytes).digest() != _from_mediawiki_sha1(source_hash):
            errors.append({"title": title, "status": "source-sha1-mismatch"})
            continue
        try:
            raw = decode_png(image_path)
        except Exception as error:
            errors.append({"title": title, "status": f"decode-error: {error}"})
            continue
        payload = record.get("payload")
        if payload and (
            raw.hex() != payload["rawHex"]
            or sha256(raw).hexdigest() != payload.get("rawSha256")
        ):
            errors.append({"title": title, "status": "payload-mismatch"})
            continue
        if record["audit"]["status"] == "verified-ordinary-dex":
            try:
                decoded = verify_ordinary_payload(raw)
            except ValueError as error:
                errors.append({"title": title, "status": f"signature-reverify-failed: {error}"})
                continue
            expected = record.get("decoded") or {}
            if (
                decoded.body.hex() != payload.get("bodyHex")
                or decoded.species_id != expected.get("species", {}).get("id")
                or decoded.form != expected.get("formId")
                or decoded.gender != expected.get("genderCode")
                or decoded.shiny_flag != expected.get("shinyFlag")
            ):
                errors.append({"title": title, "status": "decoded-fields-mismatch"})
                continue
            signature_verified += 1
        checked += 1
    return {
        "checked": checked, "signatureVerified": signature_verified,
        "errors": errors, "ok": not errors,
    }


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--catalog", type=Path)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    catalog_dir = args.catalog or args.root / "references" / "qr-codes"
    if args.verify_only:
        report = verify_catalog(catalog_dir)
        print(json.dumps(report, indent=2))
        return 0 if report["ok"] else 1
    manifest = build_catalog(args.root, catalog_dir)
    print(json.dumps(manifest["summary"], indent=2))
    return 0 if manifest["summary"]["statuses"].get("download-failed", 0) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
