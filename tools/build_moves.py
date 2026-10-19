#!/usr/bin/env python3
"""Build data/moves.json: the most-used Gen 7 moves for every final evolution.

For each species with no further evolution in the National Dex 001-807, it records the moves
competitive players ran most (Smogon, November 2019, the species' own tier file) and how the
game teaches each one along that species' own evolution path. Unevolved species point at their
final evolutions through ``lines``.

Each move has separate SM, USUM and Prismatic Standard learning profiles, with exact regional
stage identities. Empty routes mean no verified native method, not proof against events or
transfers. Legacy numeric entries and ``how`` remain readable for existing tools; the app must
not use their old union as a mode-specific fallback. Shared move metadata and historical usage
remain distinct from acquisition. Only Standard's verified levels and documented shared marts
override USUM; Rebalanced-only TM changes are excluded.

Offline by default: it reads the verified Showdown cache and the hash-pinned Smogon files in the
same directory. ``--refresh`` downloads any missing Smogon file.

  python tools/showdown_data.py bootstrap
  python tools/build_moves.py --refresh     # first run on a machine
  python tools/build_moves.py               # regenerate
  python tools/build_moves.py --check       # fail if data/moves.json is stale
"""

from __future__ import annotations

import argparse
import dataclasses
import re
import json
import sys
from pathlib import Path

try:
    from . import moveline as ml, game_move_data as game
    from .story_moves import standard_target_levels, TAPU_TMS
    from .showdown_data import require_cache
    from .showdown_text import top_blocks, field
    from .acquisition_data import TM_INFO, TUTOR_BP, TUTOR_LOCATION
    from .showdown_data import SHOWDOWN_COMMIT, ShowdownDataError, configured_cache_dir
except ImportError:  # Running the file directly: python tools/build_moves.py ...
    import moveline as ml  # type: ignore[no-redef]
    import game_move_data as game
    from story_moves import standard_target_levels, TAPU_TMS
    from showdown_data import require_cache
    from showdown_text import top_blocks, field
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


def profile_routes(path: list[str], move: str, profile: str, native: dict,
                   levels: dict, refs: dict, edges: dict) -> list[dict]:
    """Only this regional branch, with Standard replacing (not unioning) levels."""
    stages = {}
    minimum = 1
    for i, stage in enumerate(path):
        identity = str(refs[stage])
        if i:
            edge = edges.get((str(refs[path[i - 1]]), identity), {})
            method = edge.get("prismatic", edge.get("stock", "")) if profile == "prismatic" else edge.get("stock", "")
            if match := re.match(r"level (\d+)", method, re.I):
                minimum = max(minimum, int(match.group(1)))
        routes = [route.copy() for route in native[identity]["usum" if profile == "prismatic" else profile].get(move, [])]
        if profile == "prismatic":
            routes = [route for route in routes if route["via"] not in {"level", "reminder", "evolution"}]
            for level in levels[identity].get(move, []):
                routes.append({"via": "evolution"} if level == 0 else {"via": "reminder"} if level == 1 else {"via": "level", "level": level})
            for route in routes:
                if route["via"] == "TM" and move in TAPU_TMS:
                    route["tm"], route["at"] = TAPU_TMS[move], "Tapu Village specialist mart"
        stages[stage] = [route for route in routes if route.get("level", minimum) >= minimum]
    final_kinds = {route["via"] for route in stages[path[-1]]}
    out, seen = [], set()
    # Prefer a route the final itself can use; retain each distinct stage level.
    for stage in reversed(path):
        for route in stages[stage]:
            key = (route["via"], route.get("tm"), route.get("note"), stage if route["via"] == "level" else None, route.get("level"))
            if key in seen:
                continue
            seen.add(key)
            route["form"] = refs[stage]
            if stage != path[-1] and route["via"] not in final_kinds:
                route["beforeEvolving"] = True
            out.append(route)
    return out


def build(cache: Path, refresh: bool = False, game_cache: Path | None = None) -> dict:
    data = ml.load_move_data(cache)
    levels = standard_target_levels()  # Also admits all retained creator documents.
    forms = json.loads((ROOT / "data/regional-forms.json").read_text(encoding="utf-8"))["forms"]
    targets = [{"key": str(row["id"]), "id": row["id"]} for row in data.rows]
    targets += [{"key": key, **row} for key, row in forms.items()]
    native = game.project_sources(game.load_tables(game_cache or game.configured_cache_dir()), targets)
    edges = {(edge["from"], edge["to"]): edge for edge in json.loads((ROOT / "data/evolutions.json").read_text())["edges"]}
    refs = {slug: identity for slug, identity in data.id_of.items()}
    refs.update({row["showdownKey"]: key for key, row in forms.items()})
    legacy = data
    data = dataclasses.replace(data, nice=dict(data.nice), id_of=dict(data.id_of), tier_of=dict(data.tier_of))
    tiers = dict(top_blocks(require_cache(cache).get_text("tiers")))
    # Form-local copies prevent tier_of[dex] from overwriting a Kanto sibling.
    contexts = {}
    for key, row in forms.items():
        slug = row["showdownKey"]
        if row["form"] == "alolan":
            context = dataclasses.replace(data, nice={**data.nice, slug: ml.scalar(data.dex[slug], "name") or slug},
                                          id_of={**data.id_of, slug: row["id"]},
                                          tier_of={**data.tier_of, row["id"]: field(tiers.get(slug, ""), "tier") or ""})
            contexts[key] = context
    for row in forms.values():
        if row["form"] == "alolan":
            slug = row["showdownKey"]
            data.nice[slug] = ml.scalar(data.dex[slug], "name") or slug
            data.id_of[slug] = row["id"]
    downloader = None if refresh else offline_downloader
    finals = final_forms(data)
    final_set = set(finals)
    entries: dict[str, dict] = {}
    table: dict[str, dict] = {}
    for final in finals:
        identity = refs[final]
        context = contexts.get(identity, legacy)
        if identity in contexts:
            context = dataclasses.replace(context, nice=data.nice, id_of=data.id_of)
        usage, label = ml.tier_usage(final, context, downloader)
        moves = []
        path = ml.ancestral_path(final, data.parent_of)
        for move in ml.rank_moves(final, context, usage):
            if move["pct"] <= 0 or len(moves) == TOP:
                break
            info = table.setdefault(move["key"], move_info(move["key"], data))
            row: dict = {"move": move["key"], "usage": round(move["pct"], 1)}
            # Hidden Power's set-specific type ("Hidden Power Fire") differs per species.
            if move["name"] != info["name"]:
                row["name"], row["type"] = move["name"], move["type"]
            row["how"] = compact_sources(move["sources"], data.id_of)
            row["profiles"] = {profile: profile_routes(path, move["key"], profile, native, levels, refs, edges)
                               for profile in ("sm", "usum", "prismatic")}
            moves.append(row)
        entries[str(identity)] = {"stats": label, "moves": moves}
        if ":kanto" in str(identity):
            entries[str(data.id_of[final])] = entries[str(identity)]
    legacy_finals = set(final_forms(legacy))
    lines = {
        str(legacy.id_of[slug]): targets
        for slug in sorted(legacy.id_of, key=legacy.id_of.get)
        if slug not in legacy_finals and (targets := descendant_finals(slug, legacy, legacy_finals))
    }
    for key, row in forms.items():
        if key in entries:
            continue
        slug = row["showdownKey"]
        descendants, stack = set(), [slug]
        while stack:
            current = stack.pop()
            for child in data.evos_of.get(current, []):
                if child not in refs:
                    continue
                if child in final_set:
                    descendants.add(str(refs[child]))
                else:
                    stack.append(child)
        if descendants:
            lines[key] = sorted(descendants)
    return {
        "schemaVersion": 1,
        "source": {
            "showdownCommit": SHOWDOWN_COMMIT,
            "usage": "Smogon Gen 7 moveset statistics, November 2019, each species' own tier",
            "profile": "gen7",
            "top": TOP,
            "nativeLearnsets": {"commit": game.COMMIT, "sha256": {name: pin[1] for name, pin in game.SOURCES.items()}},
            "prismatic": "Verified Standard level-up tables replace USUM levels; other methods are stock USUM unless documented. Rebalanced-only TM edits excluded.",
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
    parser.add_argument("--game-cache", type=Path, default=game.configured_cache_dir(), help="hash-pinned PokeAPI CSV cache")
    parser.add_argument("--refresh", action="store_true",
                        help="download any missing hash-pinned Smogon moveset file")
    parser.add_argument("--check", action="store_true", help="fail if data/moves.json is stale")
    args = parser.parse_args()
    try:
        generated = output_text(build(args.cache, args.refresh, args.game_cache))
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
