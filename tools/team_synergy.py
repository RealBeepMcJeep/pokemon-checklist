#!/usr/bin/env python3
"""Search distinct, well-rounded teams from the canonical caught roster.

The search is exhaustive over the retained pool, but the pool and shortlist are deliberate
approximations. Every output states those limits, the tier-local moveset snapshot used, and the
account/evolution/form assumptions that affect what the team means.
"""
from __future__ import annotations

import argparse
import heapq
import itertools
import json
import math
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))
from showdown_data import configured_cache_dir, require_cache  # noqa: E402
from showdown_text import field, integer_field, object_after, top_blocks  # noqa: E402
import team_builder as tb  # noqa: E402

# Keep a point value for every tier in tb.TIER_ORDER (see the coverage test in
# tools/tests/test_team_tools.py) so an unscored tier like the missing "AG"
# used to be doesn't silently fall through TIER_POINTS.get(tier, 0.0) as if it
# were the worst possible tier.
TIER_POINTS = {
    "AG": 7.5, "Uber": 7.0, "OU": 6.0, "UUBL": 5.5, "UU": 5.0, "RUBL": 4.5, "RU": 4.0,
    "NUBL": 3.5, "NU": 3.0, "PUBL": 2.5, "PU": 2.0, "(PU)": 1.0,
    "LC Uber": 0.5, "LC": 0.0,
}
ALL_TYPES = ["Normal", "Fire", "Water", "Electric", "Grass", "Ice", "Fighting", "Poison",
             "Ground", "Flying", "Psychic", "Bug", "Rock", "Ghost", "Dragon", "Dark", "Steel", "Fairy"]
TIER_TO_CHAOS = {
    "Uber": "OU", "OU": "OU", "UUBL": "OU", "UU": "UU", "RUBL": "UU", "RU": "RU",
    "NUBL": "RU", "NU": "NU", "PUBL": "NU", "PU": "NU", "(PU)": "NU", "LC Uber": "NU", "LC": "NU",
}
CHAOS_FILES = {"OU": "chaos-gen7ou-1695.json", "UU": "chaos-gen7uu-1630.json",
               "RU": "chaos-gen7ru-1630.json", "NU": "chaos-gen7nu-1630.json"}
RELATIVE_MOVE_USAGE_FLOOR = 0.15
MAX_EXHAUSTIVE_COMBINATIONS = 100_000  # C(24, 5) is 42,504; larger searches need a smaller pool/size.


def combination_budget(pool_size: int, size: int) -> int:
    count = math.comb(pool_size, size) if 0 <= size <= pool_size else 0
    if count > MAX_EXHAUSTIVE_COMBINATIONS:
        raise ValueError(
            f"exhaustive search requires {count:,} combinations, above the hard limit of "
            f"{MAX_EXHAUSTIVE_COMBINATIONS:,}; reduce --pool or --size"
        )
    return count


def validate_args(teams: int, size: int, pool: int, shortlist: int, diversity: int = 3, **_: object) -> None:
    if teams < 1:
        raise ValueError("--teams must be at least 1")
    if size < 1 or size > 6:
        raise ValueError("--size must be between 1 and 6")
    if pool < size:
        raise ValueError("--pool must be at least --size")
    if shortlist < 1:
        raise ValueError("--shortlist must be at least 1")
    if diversity < 1 or diversity > size:
        raise ValueError("--diversity must be between 1 and --size")


def load_typechart(cache: Path) -> dict:
    """Showdown's own chart. damageTaken: 1 = weak, 2 = resist, 3 = immune."""
    text = require_cache(cache).get_text("typechart")
    chunk = object_after(text, "BattleTypeChart") or text
    chunk = re.sub(r"([,{]\s*)([A-Za-z_][A-Za-z0-9_]*)\s*:", r'\1"\2":', chunk)
    chunk = re.sub(r",(\s*[}\]])", r"\1", chunk)
    try:
        chart = json.loads(chunk)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"could not parse the type chart: {exc}") from exc
    return {defender.lower(): {attacker.lower(): value for attacker, value in (entry.get("damageTaken") or {}).items()}
            for defender, entry in chart.items()}


def _chaos_path(cache: Path, tier: str | None) -> tuple[Path | None, dict]:
    requested = tb.normalise_tier(tier) if tier else "OU"
    mapped = TIER_TO_CHAOS.get(requested, "OU")
    wanted = cache / CHAOS_FILES[mapped]
    fallback = requested != mapped
    reason = f"no {requested} chaos snapshot; mapped to {mapped}" if fallback else "tier-local snapshot"
    if wanted.exists():
        return wanted, {"requested_tier": requested, "mapped_tier": mapped, "path": wanted.name,
                        "fallback": fallback, "fallback_reason": reason if fallback else ""}
    available = sorted(cache.glob("chaos-*.json"))
    if not available:
        return None, {"requested_tier": requested, "mapped_tier": mapped, "path": "", "fallback": True,
                      "fallback_reason": "no chaos snapshot available"}
    chosen = available[0]
    return chosen, {"requested_tier": requested, "mapped_tier": mapped, "path": chosen.name, "fallback": True,
                    "fallback_reason": f"mapped file {wanted.name} missing; used {chosen.name}"}


def moveset_provenance(cache: Path, tier: str | None) -> dict:
    """Return the exact snapshot choice, including intentional tier-family fallbacks."""
    _, provenance = _chaos_path(cache, tier)
    return provenance


def load_movesets(cache: Path, tier: str | None = None) -> dict[str, dict[str, float]]:
    """Load one candidate's mapped tier file, never merging tiers during normal search."""
    if tier is None:
        paths = sorted(cache.glob("chaos-*.json"))
    else:
        path, _ = _chaos_path(cache, tier)
        paths = [path] if path else []
    out: dict[str, dict[str, float]] = {}
    for path in paths:
        if path is None:
            continue
        blob = json.loads(path.read_text())
        for name, entry in (blob.get("data") or {}).items():
            key = tb.normalize(name)
            moves = out.setdefault(key, {})
            for move, weight in (entry.get("Moves") or {}).items():
                slug = tb.normalize(move.split(":")[0].strip())
                # A single file can repeat a move in weighted sections; retain its best weight.
                moves[slug] = max(moves.get(slug, 0.0), float(weight))
    return out


def load_ability_usage(cache: Path, tier: str | None = None) -> dict[str, dict[str, float]]:
    """Load the same tier-local chaos ability weights used to qualify story viability."""
    path, _ = _chaos_path(cache, tier)
    if path is None:
        return {}
    blob = json.loads(path.read_text())
    return {
        tb.normalize(name): {
            tb.normalize(ability): float(weight)
            for ability, weight in (entry.get("Abilities") or {}).items()
        }
        for name, entry in (blob.get("data") or {}).items()
        if entry.get("Abilities")
    }


def move_info(cache: Path) -> dict:
    moves = dict(top_blocks(require_cache(cache).get_text("moves")))
    out = {}
    for slug, body in moves.items():
        normalized = tb.normalize(slug)
        typ_name = field(body, "type") or ""
        bp = integer_field(body, "basePower") or 0
        if normalized.startswith("hiddenpower"):
            suffix = normalized.removeprefix("hiddenpower")
            if suffix.capitalize() in ALL_TYPES:
                typ_name = suffix.capitalize()
        out[normalized] = (typ_name, bp)
    return out


def profile(line: dict, chart: dict, movesets: dict, mtype: dict, provenance: dict | None = None) -> dict:
    types = line["types"]
    stats = [int(x) if x.isdigit() else 0 for x in (line.get("stats") or "").split("/")] or [0] * 6
    while len(stats) < 6:
        stats.append(0)
    hp, atk, dfn, spa, spd, spe = stats[:6]
    raw = movesets.get(tb.normalize(line["final"]), {}) or {}
    best = max(raw.values()) if raw else 0.0

    # Keep one strongest contribution per attack type. Taking the first five raw moves used to
    # discard a rare but excellent type whenever a species had several moves of one type.
    # Restore the per-Pokemon relative usage floor before selecting a best move for each type.
    # Otherwise every marginally listed move becomes a type and broadens coverage artificially.
    best_by_type: dict[str, tuple[float, str, int, float]] = {}
    for slug, weight in raw.items():
        typ, bp = mtype.get(slug, ("", 0))
        if bp <= 0 or not typ or not best:
            continue
        if weight < RELATIVE_MOVE_USAGE_FLOOR * best:
            continue
        share = weight / best
        contribution = share * min(bp, 120) / 120
        prior = best_by_type.get(typ)
        if prior is None or contribution > prior[0]:
            best_by_type[typ] = (contribution, slug, bp, share)
    attacks = [(typ, value[2], value[3]) for typ, value in sorted(best_by_type.items(), key=lambda item: (-item[1][0], item[0]))]
    if attacks:
        source = "ladder moves"
        if provenance and provenance.get("fallback"):
            source += f" ({provenance['path']}; fallback: {provenance['fallback_reason']})"
        elif provenance:
            source += f" ({provenance['path']})"
    else:
        attacks, source = [(typ, 0, 0) for typ in types], "typing only (no ladder data)"

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
    return {
        **line,
        "hp": hp, "atk": atk, "dfn": dfn, "spa": spa, "spd": spd, "spe": spe,
        "bulk": hp + dfn + spd,
        "attack_types": [typ for typ, _, _ in attacks],
        "coverage_source": source,
        "moves": attacks,
        "weak": set(weak), "resist": set(resist),
        "points": TIER_POINTS.get(line.get("tier"), 0.0) + min(line.get("usage", 0), 3.0) * 0.15,
        "usable": source.startswith("ladder moves"),
        "moveset_provenance": provenance or {},
    }


def score_team(team: list[dict], chart: dict) -> tuple[float, dict]:
    if not team:
        return 0.0, {"quality": 0.0, "coverage": 0.0, "defence": 0.0, "roles": 0.0,
                      "shared_types": 0, "shared_weak": 0, "shared_weak_penalty": 0.0, "hit": [], "missed": ALL_TYPES[:]}
    quality = sum(member["points"] for member in team) / (6.0 * len(team))
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

    pairs = [(member, weakness) for member in team for weakness in member["weak"]]
    distinct_weak = {weakness for _, weakness in pairs}
    covered = {weakness for weakness in distinct_weak
               if any(weakness in other["resist"] for member, weakness2 in pairs if weakness2 == weakness
                      for other in team if other is not member)}
    defence = len(distinct_weak & covered) / len(distinct_weak) if distinct_weak else 1.0
    phys = sum(1 for member in team if member["atk"] >= member["spa"] and member["atk"] >= 90)
    spec = sum(1 for member in team if member["spa"] > member["atk"] and member["spa"] >= 100)
    roles = sum([phys >= 2, spec >= 2, any(member["bulk"] >= 280 for member in team),
                 any(member["spe"] >= 100 for member in team)]) / 4

    shared_types = sum(len(set(a["types"]) & set(b["types"])) for a, b in itertools.combinations(team, 2))
    weak_counts: dict[str, int] = {}
    for _, weakness in pairs:
        weak_counts[weakness] = weak_counts.get(weakness, 0) + 1
    shared_weak = max(weak_counts.values() or [0])
    shared_weak_penalty = max(0, shared_weak - 2) / len(team)
    total = (3.0 * quality + 4.0 * coverage + 2.5 * defence + 1.5 * roles
             - 1.5 * (shared_types / len(team)) - 1.5 * shared_weak_penalty)
    return total, {"quality": quality, "coverage": coverage, "defence": defence, "roles": roles,
                   "shared_types": shared_types, "shared_weak": shared_weak,
                   "shared_weak_penalty": shared_weak_penalty, "hit": sorted(hit),
                   "missed": sorted(set(ALL_TYPES) - hit)}


def story_synergy_score(team: list[dict], chart: dict) -> tuple[float, dict]:
    """Return the quality-independent type/switching score for story selection."""
    _, detail = score_team(team, chart)
    size = max(1, len(team))
    score = (4.0 * detail["coverage"] + 2.5 * detail["defence"]
             - 1.5 * detail["shared_types"] / size
             - 1.5 * detail["shared_weak_penalty"])
    return round(score, 4), {
        "coverage": detail["coverage"], "defence": detail["defence"],
        "shared_types": detail["shared_types"], "shared_weak": detail["shared_weak"],
        "score": round(score, 4),
    }


class PreparedStorySynergy:
    """Exact story scores with per-member type work prepared once per search.

    Bitmasks optimize the uniform STAB proxy; a vector fallback preserves arbitrary
    move strengths for callers/tests. Reference scoring still expands winner details.
    """

    def __init__(self, profiles: list[dict], chart: dict):
        types = sorted(set(ALL_TYPES) | {t for p in profiles
                       for t in (*p['types'], *p['weak'], *p['resist'])})
        bits = {typ: 1 << i for i, typ in enumerate(types)}
        mask = lambda values: sum(bits[t] for t in set(values))
        self.weak = [mask(p['weak']) for p in profiles]
        self.resist = [mask(p['resist']) for p in profiles]
        type_masks = [mask(p['types']) for p in profiles]
        self.overlap = [[(a & b).bit_count() for b in type_masks] for a in type_masks]
        self.disjoint = all(not (w & r) for w, r in zip(self.weak, self.resist))
        self.coverage = []
        for member in profiles:
            self.coverage.append(tuple(max(
                (share * min(bp, 120) / 120 for typ, bp, share in member['moves']
                 if (chart.get(defender.lower(), {}).get(typ.lower()) or 0) == 1),
                default=0.0) for defender in ALL_TYPES))
        strengths = {v for row in self.coverage for v in row if v > 0}
        self.uniform = len(strengths) <= 1
        self.strength = next(iter(strengths), 0.0)
        self.hit_masks = [sum(1 << i for i, v in enumerate(row) if v > 0)
                          for row in self.coverage]

    def score(self, indices: tuple[int, ...]) -> float:
        size = len(indices)
        if not size:
            return 0.0
        weak_union = resist_union = ones = twos = fours = hit = 0
        shared_types = 0
        for position, index in enumerate(indices):
            w = self.weak[index]
            weak_union |= w
            resist_union |= self.resist[index]
            carry_one = ones & w
            ones ^= w
            carry_two = twos & carry_one
            twos ^= carry_one
            fours ^= carry_two
            hit |= self.hit_masks[index]
            shared_types += sum(self.overlap[index][other] for other in indices[:position])
        if self.uniform:
            coverage = hit.bit_count() * self.strength / len(ALL_TYPES)
        else:
            coverage = sum(max(self.coverage[i][column] for i in indices)
                           for column in range(len(ALL_TYPES))) / len(ALL_TYPES)
        if self.disjoint:
            covered = weak_union & resist_union
        else:
            # A member may not count itself as the switch covering its weakness.
            covered = 0
            for index in indices:
                other_resist = 0
                for other in indices:
                    if other != index:
                        other_resist |= self.resist[other]
                covered |= self.weak[index] & other_resist
        defence = covered.bit_count() / weak_union.bit_count() if weak_union else 1.0
        worst = (6 if fours & twos else 5 if fours & ones else 4 if fours else
                 3 if twos & ones else 2 if twos else 1 if ones else 0)
        return round(4.0 * coverage + 2.5 * defence
                     - 1.5 * shared_types / size - 1.5 * max(0, worst - 2) / size, 4)


def member_replacements(first: tuple[str, ...], second: tuple[str, ...]) -> int:
    return len(set(first) - set(second))


def diverse_enough(first: tuple[str, ...], second: tuple[str, ...], replacements: int = 3) -> bool:
    return member_replacements(first, second) >= replacements


def search_teams(pool: list[dict], size: int, shortlist: int, teams: int, diversity: int, chart: dict) -> list[tuple[float, tuple[str, ...], dict]]:
    """Score every combination in the retained pool, then apply shortlist and diversity caps."""
    combination_budget(len(pool), size)
    heap = []
    for combo in itertools.combinations(pool, size):
        total, detail = score_team(list(combo), chart)
        item = (round(total, 4), tuple(sorted(member["final"] for member in combo)), detail)
        if len(heap) < shortlist:
            heapq.heappush(heap, item)
        elif item[0] > heap[0][0]:
            heapq.heapreplace(heap, item)
    ranked = sorted(heap, key=lambda item: (-item[0], item[1]))
    chosen: list[tuple[float, tuple[str, ...], dict]] = []
    for total, names, detail in ranked:
        if all(diverse_enough(names, other_names, diversity) for _, other_names, _ in chosen):
            chosen.append((total, names, detail))
        if len(chosen) == teams:
            break
    return chosen


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--uid", required=True)
    parser.add_argument(
        "--cache",
        default=str(configured_cache_dir()),
        help="verified shared Showdown cache (bootstrap it first)",
    )
    parser.add_argument("--off-limits", default="")
    parser.add_argument("--teams", type=int, default=5)
    parser.add_argument("--size", type=int, default=5)
    parser.add_argument("--pool", type=int, default=24,
                        help=f"how many canonical lines to search over (max {MAX_EXHAUSTIVE_COMBINATIONS:,} combinations)")
    parser.add_argument("--shortlist", type=int, default=400, help="top combinations retained before diversity")
    parser.add_argument("--diversity", type=int, default=3, help="minimum member replacements between teams")
    parser.add_argument("--no-gen1", action="store_true", help="exclude candidates with a Gen 1 lineage; Butterfree remains exempt")
    parser.add_argument("--keep-alolan", action="store_true", help="with --no-gen1, retain Alolan candidates")
    parser.add_argument("--show-all", action="store_true")
    parser.add_argument("--min-tier", default=None, help=f"drop lines worse than this tier ({', '.join(tb.TIER_ORDER)})")
    parser.add_argument("--form-override", default="", help="comma-separated name=form entries")
    parser.add_argument("--story-options", action="store_true",
                        help="five read-only story teams: fixed catcher, anchor + four partners")
    parser.add_argument("--utility", default="butterfree", help="fixed story catcher (default: butterfree)")
    parser.add_argument("--no-result-cache", action="store_true",
                        help="bypass story selection cache (fresh reads always run)")
    parser.add_argument("--json", action="store_true", help="JSON report for --story-options")
    args = parser.parse_args()
    try:
        validate_args(args.teams, args.size, args.pool, args.shortlist, args.diversity)
        if args.story_options and args.size != 5:
            raise ValueError("--story-options requires five battlers plus the fixed catcher")
        minimum = tb.normalise_tier(args.min_tier)
        overrides = tb.parse_form_overrides(args.form_override)
        off_limits = args.off_limits
        roster = tb.load_roster(args.uid, Path(args.cache), off_limits=off_limits, no_gen1=args.no_gen1,
                                keep_alolan=args.keep_alolan, min_tier=minimum, form_overrides=overrides)
        chart = load_typechart(Path(args.cache))
        mtype = move_info(Path(args.cache))
    except (RuntimeError, ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    profiles = []
    moveset_cache: dict[str, dict] = {}
    ability_cache: dict[str, dict[str, dict[str, float]]] = {}
    for line in roster["pool"]:
        provenance = moveset_provenance(Path(args.cache), line.get("tier"))
        cache_key = provenance.get("path", "")
        if cache_key not in moveset_cache:
            moveset_cache[cache_key] = load_movesets(Path(args.cache), line.get("tier")) if cache_key else {}
        member = profile(line, chart, moveset_cache[cache_key], mtype, provenance)
        if args.story_options:
            if cache_key not in ability_cache:
                ability_cache[cache_key] = (load_ability_usage(Path(args.cache), line.get("tier"))
                                            if cache_key else {})
            member["competitive_ability_usage"] = ability_cache[cache_key].get(
                tb.normalize(line["final"]), {})
        profiles.append(member)
    if args.story_options:
        import team_options as opt
        profiles = opt.attach_evolution_paths(profiles, roster)
        stars = opt.starred_ids(roster)
        for member in profiles:
            member["favorite"] = bool(stars.intersection(member["caught_ids"]))
        profiles = opt.conservative_profiles(profiles)
        utility = next((p for p in profiles if tb.normalize(p["final"]) == tb.normalize(args.utility)), None)
        if utility is None:
            print(f"error: utility {args.utility!r} is not caught or is off limits", file=sys.stderr)
            return 2
        pokedex_profiles = opt.conservative_profiles(
            opt.build_pokedex_profiles(profiles, roster, chart))
        from story_cache import choose_cached
        options = choose_cached(profiles, utility, chart,
                                pokedex_profiles=pokedex_profiles,
                                selector=opt.choose_options,
                                cache_dir=Path(args.cache) / "story-selection-v1",
                                enabled=not args.no_result_cache)
        report = opt.story_report(roster, options, utility)
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print(opt.format_story_report(report))
        return 0
    profiles.sort(key=lambda member: (member["rank"], -member["usage"], member["final"]))
    pool = profiles[:args.pool]
    try:
        combination_count = combination_budget(len(pool), args.size)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(f"=== roster: {roster['caught_count']} caught records -> {roster['canonical_count']} endpoint/form candidates ===")
    print(f"search pool: {len(pool)} of {len(profiles)} filtered candidates (rank/usage approximation; --pool={args.pool})")
    print(f"shortlist: at most {args.shortlist} of {combination_count} combinations before diversity "
          f"(hard limit {MAX_EXHAUSTIVE_COMBINATIONS:,})")
    for message in roster["assumptions"] + roster["warnings"] + roster["limitations"]:
        print(f"note: {message}")
    if args.show_all:
        for member in pool:
            print(f"  {member['final']:15} from {', '.join(member['caught_as']):18} {str(member['tier']):>7} "
                  f"moves bring {','.join(member['attack_types'])} [{member['coverage_source']}]")
        print()

    chosen = search_teams(pool, args.size, args.shortlist, args.teams, args.diversity, chart)

    by_final = {member["final"]: member for member in pool}
    for index, (total, names, detail) in enumerate(chosen, 1):
        members = [by_final[name] for name in names]
        print(f"=== team {index} score {total:.2f} (quality {detail['quality']:.2f} · coverage {detail['coverage']:.2f} · "
              f"defence {detail['defence']:.2f} · roles {detail['roles']:.2f} · shared types {detail['shared_types']} · "
              f"worst shared weakness {detail['shared_weak']} · shared weakness penalty {detail['shared_weak_penalty']:.2f} · "
              f"replacements >= {args.diversity}) ===")
        for member in sorted(members, key=lambda item: (item["rank"], item["final"])):
            provenance = member.get("moveset_provenance", {})
            print(f"   {member['final']:15} from {', '.join(member['caught_as']):18} {'/'.join(member['types']):16} "
                  f"{member['tier']:>7} {member['usage']:5.2f}% evo {member['evo']:6} "
                  f"moves bring {','.join(member['attack_types'])} [{member['coverage_source']}]")
        print(f"   reliable super-effective answers for {len(detail['hit'])}/18 types"
              f"{'; thin on: ' + ', '.join(detail['missed']) if detail['missed'] else ''}")
        weak_counts: dict[str, int] = {}
        for member in members:
            for weakness in member["weak"]:
                weak_counts[weakness] = weak_counts.get(weakness, 0) + 1
        worst = sorted(weak_counts.items(), key=lambda item: (-item[1], item[0]))[:3]
        print("   most vulnerable to: " + ", ".join(f"{typ} x{count}" for typ, count in worst))
        print()
    if not chosen:
        print("no complete team met the requested size after filtering")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
