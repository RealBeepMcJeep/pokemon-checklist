#!/usr/bin/env python3
"""Build data/moves.json: the most-used Gen 7 moves for every final evolution.

For each species with no further evolution in the National Dex 001-807, it records the moves
competitive players ran most (Smogon, November 2019, the species' own tier file) and how the
game teaches each one along that species' own evolution path. Unevolved species point at their
final evolutions through ``lines``.

The data holds facts, not wording: ``via`` is level, reminder, TM, tutor, egg or event, and the
app phrases them per game mode. An empty ``how`` means the game cannot teach that move at all.
A move's name, type, power, TM and tutor details live once in the ``moves`` table.
Entries are keyed by dex-number strings so forms (``"26:alolan"``) can be added later without a
schema change, and ``source.profile`` names the learnset rules a future variant would replace.

Offline by default: it reads the verified Showdown cache and the hash-pinned Smogon files in the
same directory. ``--refresh`` downloads any missing Smogon file.

  python tools/showdown_data.py bootstrap
  python tools/build_moves.py --refresh     # first run on a machine
  python tools/build_moves.py               # regenerate
  python tools/build_moves.py --check       # fail if data/moves.json is stale
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from . import moveline as ml
    from .acquisition_data import TM_INFO, TUTOR_BP, TUTOR_LOCATION
    from .showdown_data import SHOWDOWN_COMMIT, ShowdownDataError, configured_cache_dir
except ImportError:  # Running the file directly: python tools/build_moves.py ...
    import moveline as ml  # type: ignore[no-redef]
    from acquisition_data import TM_INFO, TUTOR_BP, TUTOR_LOCATION  # type: ignore[no-redef]
    from showdown_data import SHOWDOWN_COMMIT, ShowdownDataError, configured_cache_dir  # type: ignore[no-redef]

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "moves.json"
TOP = 8


def offline_downloader(url: str) -> bytes:
    raise ml.StatsDownloadError(
        f"{url.rsplit('/', 1)[-1]} is not cached; run python tools/build_moves.py --refresh"
    )


def compact_sources(sources: list[dict], id_of: dict[str, int]) -> list[dict]:
    """One entry per way of learning.

    Level-up keeps each form's own level (Ralts L27, Kirlia L30); every other route collapses
    to one entry, preferring one the final evolution can still use. A form is recorded only
    where it matters: level-up, egg moves, and moves that must be taught before evolving.
    """
    out: dict[tuple, dict] = {}
    for source in sources:
        via = source["via"]
        entry: dict = {"via": via}
        if via == "level":
            entry["level"] = int(source["level"])
        if via in ("level", "egg") or source.get("beforeEvolving"):
            entry["form"] = id_of[source["form"]]
        if source.get("beforeEvolving"):
            entry["beforeEvolving"] = True
        key = (via, entry["form"], entry["level"]) if via == "level" else (via,)
        kept = out.get(key)
        if kept is None or (kept.get("beforeEvolving") and not entry.get("beforeEvolving")):
            out[key] = entry
    return list(out.values())


def move_info(key: str, data: ml.MoveData) -> dict:
    """What a move is and where the game sells it, shared by every species that runs it."""
    name, kind, bp = data.move_meta.get(key, (key, "?", "-"))
    info: dict = {"name": name, "type": kind}
    if bp not in ("0", "-"):
        info["power"] = int(bp)
    if key in TM_INFO:
        info["tm"], info["tmAt"] = TM_INFO[key]
    if key in TUTOR_LOCATION:
        info["tutorAt"] = TUTOR_LOCATION[key]
    if key in TUTOR_BP:
        info["tutorBp"] = TUTOR_BP[key]
    return info


def final_forms(data: ml.MoveData) -> list[str]:
    """Species with no evolution inside the Gen 7 dex, in dex order."""
    return [
        slug
        for slug, _ in sorted(data.id_of.items(), key=lambda item: item[1])
        if not any(child in data.nice for child in data.evos_of.get(slug, []))
    ]


def descendant_finals(slug: str, data: ml.MoveData, finals: set[str]) -> list[int]:
    found: set[int] = set()
    stack, seen = [slug], set()
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        for child in data.evos_of.get(current, []):
            if child not in data.nice:
                continue
            if child in finals:
                found.add(data.id_of[child])
            stack.append(child)
    return sorted(found)


def build(cache: Path, refresh: bool = False) -> dict:
    data = ml.load_move_data(cache)
    downloader = None if refresh else offline_downloader
    finals = final_forms(data)
    final_set = set(finals)
    entries: dict[str, dict] = {}
    table: dict[str, dict] = {}
    for final in finals:
        usage, label = ml.tier_usage(final, data, downloader)
        moves = []
        for move in ml.rank_moves(final, data, usage):
            if move["pct"] <= 0 or len(moves) == TOP:
                break
            info = table.setdefault(move["key"], move_info(move["key"], data))
            row: dict = {"move": move["key"], "usage": round(move["pct"], 1)}
            # Hidden Power's set-specific type ("Hidden Power Fire") differs per species.
            if move["name"] != info["name"]:
                row["name"], row["type"] = move["name"], move["type"]
            row["how"] = compact_sources(move["sources"], data.id_of)
            moves.append(row)
        entries[str(data.id_of[final])] = {"stats": label, "moves": moves}
    lines = {
        str(data.id_of[slug]): targets
        for slug in sorted(data.id_of, key=data.id_of.get)
        if slug not in final_set and (targets := descendant_finals(slug, data, final_set))
    }
    return {
        "schemaVersion": 1,
        "source": {
            "showdownCommit": SHOWDOWN_COMMIT,
            "usage": "Smogon Gen 7 moveset statistics, November 2019, each species' own tier",
            "profile": "gen7",
            "top": TOP,
        },
        "moves": dict(sorted(table.items())),
        "finals": entries,
        "lines": lines,
    }


def output_text(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, indent=1) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build data/moves.json from pinned Gen 7 sources.")
    parser.add_argument("--cache", type=Path, default=configured_cache_dir(),
                        help="verified shared Showdown cache (bootstrap it first)")
    parser.add_argument("--refresh", action="store_true",
                        help="download any missing hash-pinned Smogon moveset file")
    parser.add_argument("--check", action="store_true", help="fail if data/moves.json is stale")
    args = parser.parse_args()
    try:
        generated = output_text(build(args.cache, args.refresh))
    except (OSError, ValueError, ShowdownDataError, ml.StatsIntegrityError, ml.StatsDownloadError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    if args.check:
        if not OUTPUT.is_file() or OUTPUT.read_text(encoding="utf-8") != generated:
            print(f"ERROR: {OUTPUT.relative_to(ROOT)} is stale")
            return 1
        print(f"OK: {OUTPUT.relative_to(ROOT)} is current")
        return 0
    OUTPUT.write_text(generated, encoding="utf-8")
    print(f"Wrote {OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
