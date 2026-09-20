#!/usr/bin/env python3
"""Build the committed Gen VII icon atlas from an offline input cache."""

from __future__ import annotations

import argparse
import io
import json
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from PIL import Image

try:
    from .cache_support import default_cache_dir, sha256_bytes, staged_directory, write_manifest
except ImportError:  # Running the file directly: python tools/build_icons.py
    from cache_support import default_cache_dir, sha256_bytes, staged_directory, write_manifest  # type: ignore[no-redef]

COUNT = 807
COLUMNS = 32
FRAME = (40, 30)
SOURCE_COMMIT = "6e3e7c43e86db0e1b2277795cfee41b11e8df2a4"
HOST = "raw.githubusercontent.com"
ICON_PATH = (
    f"/PokeAPI/sprites/{SOURCE_COMMIT}/"
    "sprites/pokemon/versions/generation-vii/icons/{dex}.png"
)
LICENSE_PATH = f"/PokeAPI/sprites/{SOURCE_COMMIT}/LICENCE.txt"
ICON_URL = f"https://{HOST}{ICON_PATH}"
LICENSE_URL = f"https://{HOST}{LICENSE_PATH}"
DOWNLOAD_TIMEOUT = 30
CACHE_SCHEMA = 1
DEFAULT_CACHE_DIR = default_cache_dir("icons-v1")
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "gen7-icons.png"
LICENSE_OUT = ROOT / "references" / "PokeAPI-sprites-LICENCE.txt"


class CacheError(ValueError):
    pass


def download_bytes(url: str) -> bytes:
    if not url.startswith(f"https://{HOST}/PokeAPI/sprites/{SOURCE_COMMIT}/"):
        raise ValueError(f"Unapproved icon source URL: {url}")
    request = urllib.request.Request(url, headers={"User-Agent": "pokemon-checklist-builder/1"})
    try:
        with urllib.request.urlopen(request, timeout=DOWNLOAD_TIMEOUT) as response:  # noqa: S310 - URL is pinned above
            if response.status != 200:
                raise RuntimeError(f"Icon request failed with HTTP {response.status}: {url}")
            return response.read()
    except OSError as error:
        raise RuntimeError(f"Could not download pinned icon source {url}") from error


def _icon_name(dex: int) -> str:
    return f"{dex:03d}.png"


def _check_icon(raw: bytes, dex: int) -> None:
    try:
        with Image.open(io.BytesIO(raw)) as image:
            image.load()
            if image.format != "PNG":
                raise ValueError(f"#{dex} is not a PNG")
            if image.size != FRAME:
                raise ValueError(f"#{dex} has unexpected dimensions {image.size}")
            if image.mode not in {"1", "L", "LA", "P", "RGB", "RGBA"}:
                raise ValueError(f"#{dex} has unsupported image mode {image.mode}")
    except (OSError, ValueError) as error:
        raise CacheError(f"Icon {_icon_name(dex)} is not a valid {FRAME[0]}x{FRAME[1]} PNG") from error


def _entry(path: str, raw: bytes) -> dict[str, object]:
    return {"path": path, "bytes": len(raw), "sha256": sha256_bytes(raw)}


def _manifest_for(icons: dict[int, bytes], license_raw: bytes) -> dict[str, object]:
    return {
        "schema": CACHE_SCHEMA,
        "sourceRepository": "PokeAPI/sprites",
        "sourceCommit": SOURCE_COMMIT,
        "iconCount": COUNT,
        "frame": list(FRAME),
        "icons": {
            _icon_name(dex): _entry(f"icons/{_icon_name(dex)}", icons[dex])
            for dex in range(1, COUNT + 1)
        },
        "license": _entry("license.txt", license_raw),
    }


def _cache_command(cache_dir: Path) -> str:
    return f'python tools/build_icons.py --refresh --cache-dir "{cache_dir}"'


def _read_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CacheError(f"Cannot read valid icon cache manifest: {path}") from error
    if not isinstance(value, dict):
        raise CacheError("Icon cache manifest must contain an object")
    return value


def _validate_entry(cache_dir: Path, entry: object, expected_path: str, label: str) -> bytes:
    if not isinstance(entry, dict) or entry.get("path") != expected_path:
        raise CacheError(f"Icon cache manifest has invalid {label} metadata")
    raw_path = cache_dir / expected_path
    try:
        raw = raw_path.read_bytes()
    except OSError as error:
        raise CacheError(f"Icon cache is missing {expected_path}") from error
    if entry.get("bytes") != len(raw) or entry.get("sha256") != sha256_bytes(raw):
        raise CacheError(f"Icon cache has a corrupted or mixed {expected_path}")
    return raw


def read_cache(cache_dir: Path) -> tuple[dict[int, bytes], bytes]:
    cache_dir = cache_dir.expanduser()
    manifest_path = cache_dir / "manifest.json"
    manifest = _read_json(manifest_path)
    if (
        manifest.get("schema") != CACHE_SCHEMA
        or manifest.get("sourceRepository") != "PokeAPI/sprites"
        or manifest.get("sourceCommit") != SOURCE_COMMIT
        or manifest.get("iconCount") != COUNT
        or manifest.get("frame") != list(FRAME)
    ):
        raise CacheError("Icon cache manifest is stale or for a different source")
    icon_entries = manifest.get("icons")
    expected_names = {_icon_name(dex) for dex in range(1, COUNT + 1)}
    if not isinstance(icon_entries, dict) or set(icon_entries) != expected_names:
        raise CacheError("Icon cache manifest does not contain exactly 807 icons")
    expected_files = {"manifest.json", "license.txt"} | {
        f"icons/{name}" for name in expected_names
    }
    actual_files = {
        path.relative_to(cache_dir).as_posix()
        for path in cache_dir.rglob("*")
        if path.is_file()
    }
    if actual_files != expected_files:
        raise CacheError("Icon cache has partial, extra, or mixed files")
    icons = {
        dex: _validate_entry(cache_dir, icon_entries[_icon_name(dex)], f"icons/{_icon_name(dex)}", f"icon #{dex}")
        for dex in range(1, COUNT + 1)
    }
    license_raw = _validate_entry(cache_dir, manifest.get("license"), "license.txt", "license")
    if not license_raw:
        raise CacheError("Icon cache license is empty")
    try:
        license_raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise CacheError("Icon cache license is not valid UTF-8") from error
    return icons, license_raw


def read_inputs(cache_dir: Path) -> tuple[dict[int, bytes], bytes]:
    try:
        return read_cache(cache_dir)
    except CacheError as error:
        raise CacheError(f"{error}. Refresh it with {_cache_command(cache_dir)}") from error


def refresh_cache(
    cache_dir: Path = DEFAULT_CACHE_DIR,
    downloader=None,
) -> None:
    cache_dir = cache_dir.expanduser()
    downloader = downloader or download_bytes
    icons: dict[int, bytes] = {}
    with ThreadPoolExecutor(max_workers=12) as pool:
        futures = {
            pool.submit(downloader, ICON_URL.format(dex=dex)): dex
            for dex in range(1, COUNT + 1)
        }
        for future in as_completed(futures):
            dex = futures[future]
            raw = future.result()
            if not isinstance(raw, bytes):
                raise TypeError(f"Icon downloader returned non-bytes for #{dex}")
            _check_icon(raw, dex)
            icons[dex] = raw
    license_raw = downloader(LICENSE_URL)
    if not isinstance(license_raw, bytes) or not license_raw:
        raise ValueError("Icon license download was empty")
    try:
        license_raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError("Icon license download is not valid UTF-8") from error
    if set(icons) != set(range(1, COUNT + 1)):
        raise RuntimeError("Icon refresh is incomplete")
    manifest = _manifest_for(icons, license_raw)
    with staged_directory(cache_dir) as staging:
        (staging / "icons").mkdir()
        for dex in range(1, COUNT + 1):
            (staging / "icons" / _icon_name(dex)).write_bytes(icons[dex])
        (staging / "license.txt").write_bytes(license_raw)
        write_manifest(staging / "manifest.json", manifest)
    read_cache(cache_dir)


def atlas_bytes(icons: dict[int, bytes]) -> bytes:
    atlas = Image.new("RGBA", (COLUMNS * FRAME[0], ((COUNT + COLUMNS - 1) // COLUMNS) * FRAME[1]))
    for dex in range(1, COUNT + 1):
        with Image.open(io.BytesIO(icons[dex])) as image:
            atlas.paste(image.convert("RGBA"), (((dex - 1) % COLUMNS) * FRAME[0], ((dex - 1) // COLUMNS) * FRAME[1]))
    output = io.BytesIO()
    atlas.save(output, format="PNG", optimize=True)
    return output.getvalue()


def build(cache_dir: Path = DEFAULT_CACHE_DIR, check: bool = False) -> None:
    icons, license_raw = read_inputs(cache_dir)
    rendered = atlas_bytes(icons)
    if check:
        if not OUT.is_file() or OUT.read_bytes() != rendered:
            raise RuntimeError(f"{OUT.relative_to(ROOT)} is stale")
        if not LICENSE_OUT.is_file() or LICENSE_OUT.read_bytes() != license_raw:
            raise RuntimeError(f"{LICENSE_OUT.relative_to(ROOT)} is stale")
        print(f"OK: {OUT.relative_to(ROOT)} and {LICENSE_OUT.relative_to(ROOT)} are current")
        return
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(rendered)
    LICENSE_OUT.parent.mkdir(parents=True, exist_ok=True)
    LICENSE_OUT.write_bytes(license_raw)
    print(f"Wrote {OUT.relative_to(ROOT)} ({COLUMNS * FRAME[0]}x{((COUNT + COLUMNS - 1) // COLUMNS) * FRAME[1]}, {len(rendered)} bytes)")
    print(f"Wrote {LICENSE_OUT.relative_to(ROOT)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=DEFAULT_CACHE_DIR,
        help="external verified raw-input cache (default: %(default)s)",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="NETWORKED: download all 807 pinned icons and the license into the cache",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="read the cache offline and fail if the committed atlas or license is stale",
    )
    args = parser.parse_args()
    try:
        if args.refresh:
            refresh_cache(args.cache_dir)
        build(args.cache_dir, check=args.check)
    except (OSError, RuntimeError, TypeError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
