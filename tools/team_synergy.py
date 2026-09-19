#!/usr/bin/env python3
"""Generate distinct, well-rounded teams from the caught roster, and score them.

A team is judged on four things, then penalised for redundancy:

1. QUALITY   - the mean competitive tier of its members (OU down to PU).
2. COVERAGE  - how many of the 18 types at least one member can hit SUPER EFFECTIVELY, taken
               from the moves each Pokemon actually runs on the ladder (Smogon chaos files),
               not from its species typing. A Water/Flying Pokemon whose ladder moves are
               Scald, Hurricane, Knock Off and Ice Beam really brings Water, Flying, Dark and
               Ice; that is what matters for breaking a team's defence.
3. DEFENCE   - for every weakness a member has, is there a teammate that resists or ignores it?
4. ROLES     - at least one physical attacker, one special attacker, one bulky Pokemon and one
               fast one, so the team is not five of the same thing.

Penalties: members sharing a species type, and three or more members weak to the same type.

    python3 tools/team_synergy.py --uid <uid> --off-limits litten,pichu,riolu,abra,magnemite
    python3 tools/team_synergy.py --uid <uid> --teams 5 --size 5 --pool 24
"""
from __future__ import annotations

import argparse
import heapq
import itertools
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))
import team_builder as tb  # noqa: E402

TIER_POINTS = {"OU": 6.0, "UUBL": 5.5, "UU": 5.0, "RUBL": 4.5, "RU": 4.0, "NUBL": 3.5,
               "NU": 3.0, "PUBL": 2.5, "PU": 2.0, "(PU)": 1.0, "LC Uber": 0.5, "LC": 0.0}
ALL_TYPES = ["Normal", "Fire", "Water", "Electric", "Grass", "Ice", "Fighting", "Poison",
             "Ground", "Flying", "Psychic", "Bug", "Rock", "Ghost", "Dragon", "Dark",
             "Steel", "Fairy"]


def load_typechart(cache: Path) -> dict:
    """Showdown's own chart. damageTaken: 1 = weak to the column type, 2 = resists, 3 = immune."""
    cached = cache / "typechart.json"
    if cached.exists():
        chart = json.loads(cached.read_text())
    else:
        # Showdown ships this as JS with unquoted keys, so quote them before parsing.
        text = (cache / "typechart.js").read_text(errors="replace")
        found = re.search(r"=\s*(\{.*\})\s*;?\s*$", text.strip(), re.S)
        chunk = found.group(1) if found else text
        chunk = re.sub(r"([{,}\s*)([A-Za-z_][A-Za-z0-9_]*)\s*:", r'\1"\2":', chunk)
        chunk = re.sub(r",(\s*[}\]])", r"\1", chunk)
        try:
            chart = json.loads(chunk)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"could not parse the type chart: {exc}") from exc
    out = {}
    for defender, entry in chart.items():
        taken = entry.get("damageTaken") or {}
        out[defender.lower()] = {attacker.lower(): v for attacker, v in taken.items()}
    return out


def load_movesets(cache: Path) -> dict:
    """mon (normalised) -> {move slug: usage weight}, merged across every tier file we have."""
    out: dict[str, dict[str, float]] = {}
    for path in sorted(cache.glob("chaos-*.json")):
        blob = json.loads(path.read_text())
        for name, entry in (blob.get("data") or {}).items():
            key = re.sub(r"[^a-z0-9]", "", name.lower())
            moves = out.setdefault(key, {})
            for move, weight in (entry.get("Moves") or {}).items():
                slug = move.split(":")[0].strip().lower().replace(" ", "").replace("-", "")
                moves[slug] = max(moves.get(slug, 0.0), float(weight))
    return out


def move_info(cache: Path) -> dict:
    sys.path.insert(0, str(REPO / "tools"))
    import moveline as ml
    moves = dict(ml.top_blocks((cache / "moves.ts").read_text(errors="replace")))
    out = {}
    for slug, body in moves.items():
        typ = re.search(r"type: \"([^\"]+)\"", body)
        bp = re.search(r"basePower: (\d+)", body)
        out[slug.lower().replace("-", "")] = (typ.group(1) if typ else "", int(bp.group(1)) if bp else 0)
    return out


def profile(line: dict, chart: dict, movesets: dict, mtype: dict) -> dict:
    types = line["types"]
    stats = [int(x) if x.isdigit() else 0 for x in (line["stats"] or "").split("/")] or [0] * 6
    while len(stats) < 6:
        stats.append(0)
    hp, atk, dfn, spa, spd, spe = stats[:6]

    # attack types from the moves the ladder actually runs; falls back to species typing
    raw = movesets.get(re.sub(r"[^a-z0-9]", "", line["final"].lower()), {}) or {}
    best = max(raw.values()) if raw else 0.0
    attacks, source = [], "typing only (no ladder data)"
    for slug, weight in sorted(raw.items(), key=lambda kv: -kv[1]):
        typ, bp = mtype.get(slug, ("", 0))
        # relative to its own most-used move: chaos scaling differs between scrapes, and an
        # absolute cutoff silently discarded every Pokemon the ladder runs rarely.
        if bp > 0 and typ and best and weight >= 0.15 * best:
            attacks.append((typ, bp, weight / best))
    if attacks:
        source = "ladder moves"
    seen, attack_types = set(), []
    for typ, bp, weight in attacks:
        if typ not in seen:
            seen.add(typ)
            attack_types.append(typ)
        if len(attack_types) == 5:
            break
    if not attack_types:
        attack_types, attacks = list(types), [(t, 0, 0) for t in types]

    weak, resist = {}, {}
    for defender in types:
        for attacker, value in (chart.get(defender.lower()) or {}).items():
            if value == 1:
                weak[attacker.capitalize()] = True
            elif value in (2, 3):
                resist[attacker.capitalize()] = True
    for attacker in list(weak):
        if attacker in resist:
            del weak[attacker]

    return {**line, "hp": hp, "atk": atk, "dfn": dfn, "spa": spa, "spd": spd, "spe": spe,
            "bulk": hp + dfn + spd, "attack_types": attack_types, "coverage_source": source,
            "moves": attacks[:5], "weak": set(weak), "resist": set(resist),
            "points": TIER_POINTS.get(line["tier"], 0.0) + min(line["usage"], 3.0) * 0.15,
            "usable": source == "ladder moves"}


def score_team(team: list[dict], chart: dict) -> tuple[float, dict]:
    quality = sum(m["points"] for m in team) / (6.0 * len(team))

    # Weighted coverage: a type is worth as much as the best move the team has for it, where
    # the move's share of that Pokemon's sets and its base power both count. A type only
    # "covered" by a 15%-usage Hidden Power is worth far less than one behind a 90% STAB.
    coverage_total, hit = 0.0, set()
    for defender in ALL_TYPES:
        best = 0.0
        for member in team:
            for attacker_type, bp, share in member["moves"]:
                if (chart.get(defender.lower(), {}).get(attacker_type.lower()) or 0) == 1:
                    best = max(best, share * min(bp, 120) / 120)
        coverage_total += best
        if best >= 0.35:
            hit.add(defender)
    coverage = coverage_total / len(ALL_TYPES)

    pairs = [(m, w) for m in team for w in m["weak"]]
    distinct_weak = {w for _, w in pairs}
    covered = {w for w in distinct_weak
               if any(w in other["resist"]
                      for member, _ in pairs if w in member["weak"] for other in team
                      if other is not member)}
    defence = (len(distinct_weak & covered) / len(distinct_weak)) if distinct_weak else 1.0

    phys = sum(1 for m in team if m["atk"] >= m["spa"] and m["atk"] >= 90)
    spec = sum(1 for m in team if m["spa"] > m["atk"] and m["spa"] >= 100)
    bulk = any(m["bulk"] >= 280 for m in team)
    fast = any(m["spe"] >= 100 for m in team)
    roles = sum([phys >= 2, spec >= 2, bulk, fast]) / 4

    shared_types = 0
    for a, b in itertools.combinations(team, 2):
        shared_types += len(set(a["types"]) & set(b["types"]))
    weak_counts: dict[str, int] = {}
    for member, weakness in pairs:
        weak_counts[weakness] = weak_counts.get(weakness, 0) + 1
    shared_weak = max([c for c in weak_counts.values()] or [0])

    total = (3.0 * quality + 4.0 * coverage + 2.5 * defence + 1.5 * roles
             - 1.5 * (shared_types / len(team)) - 1.5 * (max(0, shared_weak - 1) / len(team)))
    return total, {"quality": quality, "coverage": coverage, "defence": defence, "roles": roles,
                   "shared_types": shared_types, "shared_weak": shared_weak,
                   "hit": sorted(hit), "missed": sorted(set(ALL_TYPES) - hit)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--uid", required=True)
    parser.add_argument("--cache", default="/opt/data/poke-data")
    parser.add_argument("--off-limits", default="")
    parser.add_argument("--teams", type=int, default=5)
    parser.add_argument("--size", type=int, default=5)
    parser.add_argument("--pool", type=int, default=24, help="how many lines to search over")
    parser.add_argument("--shortlist", type=int, default=400, help="combinations kept for diversity")
    parser.add_argument("--no-gen1", action="store_true",
                        help="ban Red/Blue-era dex numbers (1-151); Butterfree is always allowed")
    parser.add_argument("--keep-alolan", action="store_true",
                        help="with --no-gen1, keep Alolan forms - they are Gen 7 Pokemon whose "
                             "BASE species happens to be an old dex number")
    parser.add_argument("--show-all", action="store_true", help="print the whole pool first")
    parser.add_argument("--min-tier", default=None,
                        help="drop lines worse than this tier (e.g. NU bars PU and (PU))")
    args = parser.parse_args()

    cache = Path(args.cache)
    det, by_id, form_row, dex = tb.load_world(cache)
    chart = load_typechart(cache)
    movesets = load_movesets(cache)
    mtype = move_info(cache)

    off = tb.expand_off_limits({s.strip().lower() for s in args.off_limits.split(",") if s.strip()}, dex)
    records = tb.read_records(args.uid)
    caught = sorted(int(k.split(":")[1]) for k, v in records.items()
                    if k.startswith("species:") and v.get("s") == "caught")

    pool = []
    for dex_id in caught:
        line = tb.describe_line(dex_id, det, by_id, form_row, dex)
        if {re.sub(r"[^a-z0-9]", "", k.lower())
                for k in (line["as"], line["slug"], line["final"])} & off:
            continue
        pool.append(profile(line, chart, movesets, mtype))
    if args.no_gen1:
        pool = [r for r in pool
                if r["id"] > 151 or r["final"] == "Butterfree"
                or (args.keep_alolan and r["alolan"])]
    if args.min_tier:
        ceiling = tb.TIER_ORDER.index(args.min_tier)
        pool = [r for r in pool if r["rank"] <= ceiling]
    pool.sort(key=lambda r: (r["rank"], -r["usage"]))
    pool = pool[:args.pool]
    if args.show_all:
        print(f"=== pool after the bans ({len(pool)} of the caught lines) ===")
        for r in pool:
            print(f"  {r['final']:15} {'/'.join(r['types']):16} {r['tier']:>5} {r['usage']:5.2f}%  "
                  f"moves bring {'/'.join(r['attack_types'])}")
        print()
    print(f"searching {len(pool)} lines ({len(caught)} caught, banned lines removed), "
          f"team size {args.size}\n")

    heap = []
    for combo in itertools.combinations(pool, args.size):
        total, detail = score_team(list(combo), chart)
        item = (round(total, 4), tuple(sorted(m["final"] for m in combo)), detail)
        if len(heap) < args.shortlist:
            heapq.heappush(heap, item)
        elif item[0] > heap[0][0]:
            heapq.heapreplace(heap, item)

    ranked = sorted(heap, key=lambda x: -x[0])
    chosen = []
    for total, names, detail in ranked:
        if all(len(set(names) ^ set(other_names)) >= 3 for _, other_names, _ in chosen):
            chosen.append((total, names, detail))
        if len(chosen) == args.teams:
            break

    for index, (total, names, detail) in enumerate(chosen, 1):
        members = [next(m for m in pool if m["final"] == n) for n in names]
        print(f"=== team {index}   score {total:.2f}  "
              f"(quality {detail['quality']:.2f} · coverage {detail['coverage']:.2f} · "
              f"defence {detail['defence']:.2f} · roles {detail['roles']:.2f} · "
              f"shared types {detail['shared_types']} · worst shared weakness {detail['shared_weak']})")
        for m in sorted(members, key=lambda m: m["rank"]):
            print(f"   {m['final']:15} {'/'.join(m['types']):16} {m['tier']:>5} {m['usage']:5.2f}%  "
                  f"evo {m['evo']:6} moves bring {'/'.join(m['attack_types'])}")
        print(f"   reliable super-effective answers for {len(detail['hit'])}/18 types"
              f"{'; thin on: ' + ', '.join(detail['missed']) if detail['missed'] else ''}")
        weak_counts: dict[str, int] = {}
        for m in members:
            for weakness in m["weak"]:
                weak_counts[weakness] = weak_counts.get(weakness, 0) + 1
        worst = sorted(weak_counts.items(), key=lambda kv: -kv[1])[:3]
        print(f"   most vulnerable to: " + ", ".join(f"{t} x{n}" for t, n in worst))
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
