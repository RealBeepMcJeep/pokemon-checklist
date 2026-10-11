#!/usr/bin/env python3
"""Deterministic, offline ball atlas; --refresh fetches hash-pinned PokéAPI inputs.
The committed input cache makes freshness checking network-free in CI.
Pokémon artwork © Nintendo / Creatures / GAME FREAK; see PokeAPI-sprites-LICENCE.txt.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import sys
import urllib.request
from pathlib import Path
from PIL import Image
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CACHE = ROOT / "references" / "ball-sprites"
OUT = ROOT / "assets" / "catch-balls.png"
SOURCE_COMMIT = "6e3e7c43e86db0e1b2277795cfee41b11e8df2a4"
MANIFEST = json.loads((DEFAULT_CACHE / "manifest.json").read_text())

def validate(raw: bytes, frame: dict) -> None:
    if len(raw) != frame["bytes"] or hashlib.sha256(raw).hexdigest() != frame["sha256"]:
        raise ValueError(f"Ball sprite {frame['slug']}: pinned hash/byte mismatch")
    try:
        with Image.open(io.BytesIO(raw)) as image:
            image.load()
            if image.format != "PNG" or image.size != (30,30):
                raise ValueError(f"Ball sprite {frame['slug']}: invalid PNG dimensions; expected 30x30")
    except OSError as error:
        raise ValueError(f"Ball sprite {frame['slug']}: invalid PNG") from error

def atlas_bytes(cache: Path) -> bytes:
    if MANIFEST["sourceCommit"] != SOURCE_COMMIT or len(MANIFEST["balls"]) != 22:
        raise ValueError("Ball manifest: unexpected source/count")
    atlas = Image.new("RGBA", (240,90))
    for index, frame in enumerate(MANIFEST["balls"]):
        if frame["index"] != index or frame["url"] != f"https://raw.githubusercontent.com/PokeAPI/sprites/{SOURCE_COMMIT}/sprites/items/{frame['slug']}.png":
            raise ValueError("Ball manifest: invalid frame order or pinned URL")
        try:
            raw = (cache / (frame["slug"] + ".png")).read_bytes()
        except OSError as error:
            raise ValueError(f"Missing ball input {frame['slug']}; run python tools/build_ball_sprites.py --refresh --cache-dir {cache}") from error
        validate(raw,frame)
        with Image.open(io.BytesIO(raw)) as image:
            atlas.paste(image.convert("RGBA"),(index % 8 * 30,index // 8 * 30))
    out = io.BytesIO(); atlas.save(out,format="PNG",optimize=True); return out.getvalue()

def refresh(cache: Path) -> None:
    # Validate the entire download before replacing any cache entry.
    inputs = {}
    for frame in MANIFEST["balls"]:
        with urllib.request.urlopen(frame["url"],timeout=30) as response:
            raw = response.read()
        validate(raw,frame); inputs[frame["slug"]] = raw
    cache.mkdir(parents=True,exist_ok=True)
    for slug,raw in inputs.items():
        target = cache / (slug + ".png"); temporary = target.with_suffix(".tmp"); temporary.write_bytes(raw); temporary.replace(target)

def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir",type=Path,default=DEFAULT_CACHE)
    parser.add_argument("--refresh",action="store_true")
    parser.add_argument("--check",action="store_true")
    args=parser.parse_args()
    try:
        if args.refresh: refresh(args.cache_dir)
        raw=atlas_bytes(args.cache_dir)
        if args.check:
            if not OUT.exists() or OUT.read_bytes() != raw:
                raise ValueError("Ball atlas stale: run python tools/build_ball_sprites.py")
            print("Ball atlas: 22 pinned hashes, dimensions and offline freshness verified")
        else:
            OUT.write_bytes(raw); print(f"Built {OUT}")
    except (ValueError,OSError) as error:
        print(str(error),file=sys.stderr); return 1
    return 0
if __name__ == "__main__": sys.exit(main())
