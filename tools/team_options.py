#!/usr/bin/env python3
"""Five read-only story-team objectives: OG, Non-OG, Mixed, Pokédex, and Best."""
from __future__ import annotations

import itertools
import math
import re

import team_builder as tb
import team_synergy as ts

OG_LIMIT = 151
UNVERIFIED_INDIVIDUAL_GATES = {"Salazzle", "Froslass", "Gallade", "Hitmonlee", "Hitmonchan", "Hitmontop"}
HIDDEN_ABILITY_PENALTY = 0.75  # bounded heuristic; usage share is not a strength fraction
LEVEL_METHOD = re.compile(r"Level \d+\Z", re.IGNORECASE)
CONDITIONAL_LEVEL_EVOLUTIONS = {
    ("Yungoos", "Gumshoos"),  # daytime
    ("Kirlia", "Gallade"),  # male + Dawn Stone
    ("Tyrogue", "Hitmonlee"), ("Tyrogue", "Hitmonchan"), ("Tyrogue", "Hitmontop"),
    ("Nincada", "Shedinja"),  # empty party slot + Poké Ball
    ("Wurmple", "Silcoon"), ("Wurmple", "Cascoon"),  # branch is not recorded
    ("Espurr", "Meowstic"),  # sex-specific form
}

# Standard evolution changes take precedence over the pinned vanilla metadata.
# These entries come from references/prismatic-moon/Evolution Changes.pdf.
HACK_EVOLUTIONS = {
    ("Graveler", "Golem"): "high friendship + level",
    ("Kadabra", "Alakazam"): "high friendship + level",
    ("Machoke", "Machamp"): "high friendship + level",
    ("Haunter", "Gengar"): "high friendship + level",
    ("Onix", "Steelix"): "level holding Metal Coat",
    ("Scyther", "Scizor"): "level holding Metal Coat",
    ("Seadra", "Kingdra"): "level holding Dragon Scale",
    ("Poliwhirl", "Politoed"): "level holding King's Rock",
    ("Poliwhirl", "Poliwrath"): "Water Stone",
    ("Slowpoke", "Slowking"): "level holding King's Rock",
    ("Porygon", "Porygon2"): "level holding Up-Grade",
    ("Porygon2", "Porygon-Z"): "level holding Dubious Disc",
    ("Clamperl", "Huntail"): "level holding Deep Sea Tooth",
    ("Clamperl", "Gorebyss"): "level holding Deep Sea Scale",
    ("Dusclops", "Dusknoir"): "level holding Reaper Cloth",
    ("Magmar", "Magmortar"): "level holding Magmarizer",
    ("Electabuzz", "Electivire"): "level holding Electirizer",
    ("Rhydon", "Rhyperior"): "level holding Protector",
    ("Feebas", "Milotic"): "level holding Prism Scale",
    ("Karrablast", "Escavalier"): "level with Shelmet in party",
    ("Shelmet", "Accelgor"): "level with Karrablast in party",
    ("Gurdurr", "Conkeldurr"): "high friendship + level",
    ("Boldore", "Gigalith"): "high friendship + level",
    ("Spritzee", "Aromatisse"): "level holding Sachet",
    ("Swirlix", "Slurpuff"): "level holding Whipped Dream",
    ("Phantump", "Trevenant"): "high friendship + level",
    ("Pumpkaboo", "Gourgeist"): "high friendship + level",
    ("Cosmoem", "Solgaleo"): "level 53 in Ultra Moon",
    ("Cosmoem", "Lunala"): "level 53 in Ultra Sun",
    ("Rockruff", "Lycanroc-Midday"): "level 25 during the day",
    ("Rockruff", "Lycanroc-Midnight"): "level 25 at night",
    ("Magneton", "Magnezone"): "Thunder Stone",
    ("Nosepass", "Probopass"): "Thunder Stone",
    ("Charjabug", "Vikavolt"): "Thunder Stone",
    ("Crabrawler", "Crabominable"): "Ice Stone",
    ("Snorunt", "Glalie"): "Level 30",
    ("Vanillite", "Vanillish"): "Level 25",
    ("Vanillish", "Vanilluxe"): "Level 37",
    ("Tynamo", "Eelektrik"): "Level 20",
    ("Rufflet", "Braviary"): "Level 34",
    ("Vullaby", "Mandibuzz"): "Level 34",
    ("Pawniard", "Bisharp"): "Level 42",
    ("Deino", "Zweilous"): "Level 40",
    ("Zweilous", "Hydreigon"): "Level 54",
    ("Larvesta", "Volcarona"): "Level 49",
    ("Mienfoo", "Mienshao"): "Level 40",
    ("Klink", "Klang"): "Level 28",
    ("Klang", "Klinklang"): "Level 39",
    ("Skrelp", "Dragalge"): "Level 37",
    ("Noibat", "Noivern"): "high friendship at night",
}


def conservative_profiles(profiles: list[dict]) -> list[dict]:
    """Use STAB type potential only; these are not claimed as move sets."""
    return [{**p, "moves": [(typ, 80, 1.0) for typ in p["types"]],
             "attack_types": list(p["types"]),
             "coverage_source": "STAB-type potential proxy (not a move list)"}
            for p in profiles]


def _norm(value: object) -> str:
    return tb.normalize(str(value or ""))


def _caught_ids(member: dict) -> set[int]:
    return {int(value) for value in member.get("caught_ids", ())}


def _caught_names(member: dict) -> set[str]:
    return {_norm(name) for name in member.get("caught_as", ())}


def _stage_is_owned(member: dict, stage: dict) -> bool:
    dex = stage.get("id")
    return ((dex is not None and int(dex) in _caught_ids(member))
            or _norm(stage.get("name")) in _caught_names(member))


def _method(previous: str, step: dict) -> str:
    name = str(step.get("name", ""))
    return HACK_EVOLUTIONS.get((previous, name), str(step.get("method", "")))


def _method_label(method: str) -> str:
    return re.sub(r"^Level (\d+)$", r"L\1", method)


def _level_only(method: str) -> bool:
    return bool(LEVEL_METHOD.fullmatch(method.strip()))


def attach_evolution_paths(profiles: list[dict], roster: dict) -> list[dict]:
    """Attach the verified app lineage and dex IDs needed by objective filters."""
    name_to_id = {_norm(row.get("name")): int(identifier)
                  for identifier, row in roster.get("by_id", {}).items()}
    result = []
    for member in profiles:
        entry = roster.get("det", {}).get(int(member["endpoint_id"]), {})
        raw_path = entry.get("evolution") or []
        path = []
        previous = ""
        for raw in raw_path:
            if not isinstance(raw, dict) or not raw.get("name"):
                continue
            name = str(raw["name"])
            step = {"name": name, "id": name_to_id.get(_norm(name))}
            if previous:
                step["method"] = _method(previous, raw)
            elif raw.get("method"):
                step["method"] = str(raw["method"])
            path.append(step)
            previous = name
        result.append({**member, "evolution_path": path})
    return result


def pure_level_plans(member: dict) -> list[dict]:
    """Enumerate still-available, ordinary-level-only plans that add a dex entry."""
    path = list(member.get("evolution_path") or ())
    if len(path) < 2:
        return []
    caught_ids, caught_names = _caught_ids(member), _caught_names(member)

    def is_caught(stage: dict) -> bool:
        return ((stage.get("id") is not None and int(stage["id"]) in caught_ids)
                or _norm(stage.get("name")) in caught_names)

    plans = []
    for start, stage in enumerate(path[:-1]):
        if not is_caught(stage):
            continue
        for end in range(start + 1, len(path)):
            previous = str(path[end - 1].get("name", ""))
            target = path[end]
            pair = (previous, str(target.get("name", "")))
            if pair in CONDITIONAL_LEVEL_EVOLUTIONS:
                break
            method = _method(previous, target)
            if not _level_only(method):
                break
            if is_caught(target):
                continue
            additions = [str(step["name"]) for step in path[start + 1:end + 1]
                         if not is_caught(step)]
            if not additions:
                continue
            plan_path = [dict(step) for step in path[start:end + 1]]
            plans.append({
                "owned": str(stage["name"]),
                "owned_dex": int(stage["id"]) if stage.get("id") is not None else None,
                "planned_final": str(target["name"]),
                "planned_dex": int(target["id"]) if target.get("id") is not None else None,
                "new_entries": additions,
                "evolution_path": plan_path,
            })
    return plans


def has_hidden_ability_caveat(member: dict) -> bool:
    """True when pinned ability slots include an unavailable-by-default H slot."""
    return bool(re.search(r"\(H\)", str(member.get("abilities", ""))))


def hidden_ability_usage_share(member: dict) -> float:
    """Share of the mapped ladder ability weight assigned to hidden slots."""
    slots = [token.strip() for token in str(member.get("abilities", "")).split(",") if token.strip()]
    hidden = {_norm(re.sub(r"\s*\(H\)$", "", token)) for token in slots
              if re.search(r"\(H\)$", token)}
    if not hidden:
        return 0.0
    usage = member.get("competitive_ability_usage") or {}
    normalized = {_norm(key): max(0.0, float(value)) for key, value in usage.items()}
    known = {_norm(re.sub(r"\s*\(H\)$", "", token)) for token in slots}
    denominator = sum(normalized.get(name, 0.0) for name in known)
    if denominator <= 0:
        return 1.0 if not usage else 0.0
    return min(1.0, sum(normalized.get(name, 0.0) for name in hidden) / denominator)


def practical_viability(member: dict) -> float:
    """Use tier/usage only to the extent the ordinary-ability build supports it."""
    score = float(member.get("points", 0.0))
    if has_hidden_ability_caveat(member):
        if member.get("competitive_ability_usage"):
            score -= HIDDEN_ABILITY_PENALTY * hidden_ability_usage_share(member)
        else:
            score -= HIDDEN_ABILITY_PENALTY
    return round(score, 4)


def anchor_score(member: dict) -> float:
    return practical_viability(member)


def is_evolving(member: dict) -> bool:
    """Whether the endpoint itself is not already in the caught records."""
    endpoint = member.get("endpoint_id")
    if endpoint is not None and int(endpoint) in _caught_ids(member):
        return False
    if _norm(member.get("final")) in _caught_names(member):
        return False
    return any(_norm(name) != _norm(member.get("final"))
               for name in member.get("caught_as", ()))


def evolution_opportunities(member: dict) -> int:
    """Count not-yet-caught forms on the path from any owned stage to this endpoint."""
    path = list(member.get("evolution_path") or ())
    if not path:
        return int(is_evolving(member))
    found = set()
    for start, stage in enumerate(path[:-1]):
        if not _stage_is_owned(member, stage):
            continue
        for step in path[start + 1:]:
            if not _stage_is_owned(member, step):
                found.add(_norm(step.get("name")))
    return len(found)


def has_level_evolution_opportunity(member: dict) -> bool:
    path = list(member.get("evolution_path") or ())
    for index, stage in enumerate(path[:-1]):
        if not _stage_is_owned(member, stage):
            continue
        next_step = path[index + 1]
        if (not _stage_is_owned(member, next_step)
                and _level_only(_method(str(stage.get("name", "")), next_step))):
            return True
    return str(member.get("evo", "")).startswith("L") and is_evolving(member)


def _path_category_ready(member: dict, *, og: bool) -> bool:
    endpoint = int(member.get("endpoint_id", 10**9))
    if member.get("alolan"):
        return False
    path = list(member.get("evolution_path") or ())
    if not path:
        if og:
            return endpoint <= OG_LIMIT and any(i <= OG_LIMIT for i in _caught_ids(member))
        return endpoint > OG_LIMIT and bool(_caught_ids(member)) and all(
            i > OG_LIMIT for i in _caught_ids(member))
    for index, stage in enumerate(path):
        if not _stage_is_owned(member, stage):
            continue
        proposed = path[index:]
        ids = [int(item["id"]) for item in proposed if item.get("id") is not None]
        if len(ids) != len(proposed):
            continue
        if og and endpoint <= OG_LIMIT and all(identifier <= OG_LIMIT for identifier in ids):
            return True
        if not og and endpoint > OG_LIMIT and all(identifier > OG_LIMIT for identifier in ids):
            return True
    return False


def og_ready(member: dict) -> bool:
    """Owned stage and every proposed stage through the endpoint are Kanto #1–151."""
    return _path_category_ready(member, og=True)


def no_og_ready(member: dict) -> bool:
    """Owned stage and every proposed stage are outside the original 151."""
    return _path_category_ready(member, og=False)


def eligible_for_easy_run(profiles: list[dict]) -> list[dict]:
    """Exclude unknown regional forms and unproven sex/stat evolutions, not weak tiers."""
    usable = []
    for member in profiles:
        if member.get("alolan"):
            continue
        if member["final"] in UNVERIFIED_INDIVIDUAL_GATES and is_evolving(member):
            continue
        usable.append(member)
    return usable


def _independent(combo: tuple[dict, ...]) -> bool:
    caught = [_caught_ids(member) for member in combo]
    return not any(first & second for first, second in itertools.combinations(caught, 2))


def _combo_counts(combo: tuple[dict, ...]) -> tuple[int, int]:
    return (sum(evolution_opportunities(member) > 0 for member in combo),
            sum(has_level_evolution_opportunity(member) for member in combo))


def _objective_key(category: str, synergy: float, evolution: int,
                   viability: float, favorites: int, names: tuple[str, ...],
                   new_entries: int) -> tuple:
    if category == "Best":
        return (-viability, -synergy, -favorites, names)
    if category == "Pokedex":
        return (-new_entries, -synergy, -viability, -favorites, names)
    return (-synergy, -evolution, -viability, -favorites, names)


def _rank(pool: list[dict], utility: dict, chart: dict, *, category: str) -> list[dict]:
    """Exhaustively scan the full pool while retaining only the best valid lineup."""
    searched = math.comb(len(pool), 5) if len(pool) >= 5 else 0
    metrics = {
        id(member): {
            "caught": _caught_ids(member),
            "opportunities": evolution_opportunities(member),
            "level_evolving": has_level_evolution_opportunity(member),
            "viability": practical_viability(member),
            "new_entries": len(member.get("dex_plan", {}).get("new_entries", ())),
            "favorite": bool(member.get("favorite")),
        }
        for member in pool
    }
    best = None
    independent = 0
    for combo in itertools.combinations(pool, 5):
        seen = set()
        valid = True
        for member in combo:
            caught = metrics[id(member)]["caught"]
            if seen.intersection(caught):
                valid = False
                break
            seen.update(caught)
        if not valid:
            continue
        independent += 1
        core, core_detail = ts.story_synergy_score(list(combo), chart)
        full, full_detail = ts.story_synergy_score([*combo, utility], chart)
        synergy = round(0.65 * core + 0.35 * full, 4)
        opportunity = sum(metrics[id(member)]["opportunities"] for member in combo)
        new_entries = sum(metrics[id(member)]["new_entries"] for member in combo)
        viability = round(sum(metrics[id(member)]["viability"] for member in combo) / 5, 4)
        favorite_count = sum(metrics[id(member)]["favorite"] for member in combo)
        names = tuple(sorted(str(member["final"]) for member in combo))
        key = _objective_key(category, synergy, opportunity, viability,
                             favorite_count, names, new_entries)
        anchor = max(combo, key=lambda member: (metrics[id(member)]["viability"],
                                                str(member["final"])))
        evolving = sum(metrics[id(member)]["opportunities"] > 0 for member in combo)
        level_evolving = sum(metrics[id(member)]["level_evolving"] for member in combo)
        candidate = {
            "category": category, "anchor": anchor["final"], "utility": utility["final"],
            "members": list(names), "profiles": combo, "objective_key": key,
            "synergy": synergy, "core_synergy": core, "six_synergy": full,
            "core_synergy_detail": core_detail, "six_synergy_detail": full_detail,
            "viability": viability, "evolution_opportunities": opportunity,
            "new_entries": new_entries, "evolving": evolving,
            "level_evolving": level_evolving,
            "shared_types": full_detail["shared_types"],
            "searched_combinations": searched,
        }
        if best is None or key < best["objective_key"]:
            best = candidate
    if best is None:
        return []
    best["independent_combinations"] = independent
    return [best]


def _stage_catalog(profiles: list[dict], roster: dict, chart: dict) -> dict[str, dict]:
    names = {str(stage.get("name")) for member in profiles
             for stage in member.get("evolution_path", ()) if stage.get("name")}
    by_name = {_norm(row.get("name")): int(identifier)
               for identifier, row in roster.get("by_id", {}).items()}
    catalog = {}
    for name in names:
        dex_id = by_name.get(_norm(name))
        if dex_id is None:
            continue
        details = roster.get("det", {}).get(dex_id, {})
        row = roster.get("by_id", {}).get(dex_id, {})
        tier = details.get("tier")
        usage = float(details.get("usage") or 0.0)
        types = tb.types_of(roster["dex"], name) or details.get("types") or []
        raw = {
            "final": name, "endpoint_id": dex_id, "types": types,
            "stats": tb.stats_of(roster["dex"], name), "tier": tier,
            "usage": usage, "evo": tb.evo_of(roster["dex"], name),
            "abilities": tb.abilities_of(roster["dex"], name),
            "rank": tb.tier_rank(tier), "points": ts.TIER_POINTS.get(tier, 0.0)
            + min(usage, 3.0) * 0.15,
        }
        catalog[_norm(name)] = ts.profile(raw, chart, {}, {})
    return catalog


def build_pokedex_profiles(profiles: list[dict], roster: dict, chart: dict) -> list[dict]:
    """Create a selectable profile for each reachable pure-level endpoint stage."""
    catalog = _stage_catalog(profiles, roster, chart)
    planned = {}
    for member in profiles:
        if member.get("alolan"):
            continue
        for plan in pure_level_plans(member):
            target_key = _norm(plan["planned_final"])
            target = catalog.get(target_key)
            if target is None:
                continue
            candidate = {**target,
                         "caught_ids": list(member.get("caught_ids", ())),
                         "caught_as": list(member.get("caught_as", ())),
                         "lineage_ids": list(member.get("lineage_ids", ())),
                         "favorite": bool(member.get("favorite")),
                         "alolan": False,
                         "evolution_path": plan["evolution_path"],
                         "dex_plan": plan,
                         "source_endpoint": member["final"]}
            key = (target_key, tuple(sorted(candidate["caught_ids"])),
                   plan["owned"], tuple(plan["new_entries"]))
            planned[key] = candidate
    return list(planned.values())


def choose_options(profiles: list[dict], utility: dict, chart: dict,
                   *, min_changes: int | None = None, pool_limit: int | None = None,
                   pokedex_profiles: list[dict] | None = None) -> list[dict]:
    """Choose one full-pool lineup for each approved objective; duplication is allowed."""
    del min_changes, pool_limit  # retained only for callers of the retired five-mixed mode
    usable = eligible_for_easy_run([p for p in profiles
                                    if _norm(p["final"]) != _norm(utility["final"])])
    pools = [
        ("OG", [p for p in usable if og_ready(p)], len(usable) - sum(og_ready(p) for p in usable)),
        ("Non-OG", [p for p in usable if no_og_ready(p)], len(usable) - sum(no_og_ready(p) for p in usable)),
        ("Mixed", usable, 0),
        ("Pokedex", pokedex_profiles or [],
         max(0, len(usable) - len({tuple(sorted(_caught_ids(p))) for p in pokedex_profiles or []}))),
        ("Best", usable, 0),
    ]
    results = []
    for category, candidates, excluded in pools:
        ranked = _rank(candidates, utility, chart, category=category) if len(candidates) >= 5 else []
        if not ranked:
            eligible = len(candidates)
            warning = (f"only {eligible} eligible owned candidates; fewer than five independent lineages"
                       if eligible >= 5 else f"only {eligible} eligible owned candidates")
            results.append({"category": category, "utility": utility["final"],
                            "members": [], "profiles": [], "warning": warning,
                            "eligible_pool": eligible, "searched_combinations": 0,
                            "independent_combinations": 0, "excluded_count": excluded})
            continue
        best = ranked[0]
        best["eligible_pool"] = len(candidates)
        best["excluded_count"] = excluded
        results.append(best)
    return results


def _stage_path(member: dict, roster: dict) -> list[dict]:
    path = list(member.get("evolution_path") or ())
    if path:
        return path
    raw = (roster.get("det", {}).get(int(member["endpoint_id"]), {}).get("evolution") or [])
    ids = {_norm(row.get("name")): int(identifier)
           for identifier, row in roster.get("by_id", {}).items()}
    result, previous = [], ""
    for item in raw:
        if not isinstance(item, dict) or not item.get("name"):
            continue
        name = str(item["name"])
        stage = {"name": name, "id": ids.get(_norm(name))}
        if previous:
            stage["method"] = _method(previous, item)
        result.append(stage)
        previous = name
    return result


def evolution_chain(member: dict, roster: dict, *, og_only: bool = False) -> tuple[str, str]:
    """Show a currently owned stage and its verified remaining path."""
    if member.get("dex_plan"):
        plan = member["dex_plan"]
        path = plan["evolution_path"]
        pieces = [str(path[0]["name"])]
        for previous, stage in zip(path, path[1:]):
            method = _method(str(previous["name"]), stage)
            pieces.append(f"{stage['name']} ({_method_label(method)})" if method else str(stage["name"]))
        return str(plan["owned"]), " → ".join(pieces)
    owned = [(int(identifier), roster["by_id"][int(identifier)]["name"])
             for identifier in member.get("caught_ids", ())
             if int(identifier) in roster.get("by_id", {})]
    if og_only:
        owned = [(identifier, name) for identifier, name in owned if identifier <= OG_LIMIT]
    path = _stage_path(member, roster)
    if not path:
        chosen = owned[0] if owned else (int(member["endpoint_id"]), member["final"])
        return chosen[1], str(member["final"])
    indexes = {_norm(stage["name"]): index for index, stage in enumerate(path)}
    starts = [(indexes[_norm(name)], identifier, name) for identifier, name in owned
              if _norm(name) in indexes]
    if starts:
        index, _, selected = max(starts, key=lambda item: item[0])
    else:
        selected = str(member["final"])
        index = next((i for i, stage in enumerate(path)
                      if _norm(stage["name"]) == _norm(selected)), len(path) - 1)
    pieces = [selected]
    for previous, stage in zip(path[index:-1], path[index + 1:]):
        name = str(stage["name"])
        method = _method(str(previous["name"]), stage)
        pieces.append(f"{name} ({_method_label(method)})" if method else name)
    return selected, " → ".join(pieces)


def starred_ids(roster: dict) -> set[int]:
    return {int(key.split(":", 1)[1]) for key, record in roster.get("records", {}).items()
            if key.startswith("star:") and record.get("s") == "on"}


def story_report(roster: dict, options: list[dict], utility: dict) -> dict:
    stars = starred_ids(roster)
    rendered = []
    for option in options:
        members = []
        for profile in option.get("profiles", ()):
            owned, chain = evolution_chain(profile, roster,
                                           og_only=option["category"] == "OG")
            owned_dex = (int(profile["dex_plan"]["owned_dex"])
                         if profile.get("dex_plan") and profile["dex_plan"].get("owned_dex")
                         else next((int(i) for i in profile.get("caught_ids", ())
                                    if roster["by_id"].get(int(i), {}).get("name") == owned),
                                   int(profile.get("caught_ids", [profile["endpoint_id"]])[0])))
            members.append({
                "owned": owned, "owned_dex": owned_dex,
                "final": profile["final"], "dex": int(profile["endpoint_id"]),
                "evolution": chain, "types": profile["types"],
                "tier": profile.get("tier"),
                "favorite": bool(stars.intersection(profile.get("caught_ids", ()))),
                "hidden_ability_caveat": has_hidden_ability_caveat(profile),
                "hidden_ability_usage_share": (hidden_ability_usage_share(profile)
                                               if profile.get("competitive_ability_usage") else None),
                "competitive_ability_usage_recorded": bool(profile.get("competitive_ability_usage")),
                "caught_ids": sorted(_caught_ids(profile)),
                "new_entries": profile.get("dex_plan", {}).get("new_entries", []),
                "abilities": profile.get("abilities", ""),
            })
        rendered_option = {key: value for key, value in option.items()
                           if key not in ("profiles", "objective_key")}
        rendered.append({**rendered_option, "members": members})
    caught_ids = sorted(int(key.split(":", 1)[1]) for key, record in roster.get("records", {}).items()
                        if key.startswith("species:") and isinstance(record, dict)
                        and record.get("s") == "caught")
    return {
        "caught_records": roster["caught_count"],
        "source_caught_ids": caught_ids,
        "endpoints": roster["canonical_count"],
        "utility": utility["final"], "utility_dex": int(utility["endpoint_id"]),
        "options": rendered,
        "search_scope": {
            "mode": "full eligible pool; five-member combinations; no tier floor or shortlist",
            "categories": {option["category"]: {
                "eligible_candidates": option.get("eligible_pool", 0),
                "searched_combinations": option.get("searched_combinations", 0),
                "excluded_candidates": option.get("excluded_count", 0),
            } for option in options},
        },
        "objective_rules": {
            "OG": "synergy, new evolution entries, practical viability",
            "Non-OG": "synergy, new evolution entries, practical viability",
            "Mixed": "synergy, new evolution entries, practical viability; no required generation mix",
            "Pokedex": "new level-only dex entries, synergy, practical viability",
            "Best": "practical viability, synergy; no evolution/favorite bonus",
        },
        "warnings": [
            "Scores are deterministic heuristics, not win probabilities or a battle simulation.",
            "Attack coverage is STAB-type potential, not a verified four-move set; card moves are checked separately.",
            "The checklist does not store individual ability, sex, regional form, current level, or owned items.",
            "Butterfree is fixed sleep utility and cannot use False Swipe.",
        ],
    }


def format_story_report(report: dict) -> str:
    lines = [f"{report['caught_records']} caught records, {report['endpoints']} evolution endpoints; "
             f"fixed slot: {report['utility']}"]
    for index, option in enumerate(report["options"], 1):
        if not option["members"]:
            lines.append(f"{index}. {option['category']}: {option['warning']}")
            continue
        lines.append(f"{index}. {option['category']} | anchor {option['anchor']} | "
                     f"{option['evolving']}/5 can add entries ({option['level_evolving']} by level) | "
                     f"synergy {option.get('synergy', option.get('core_score', 0.0)):.2f} | "
                     f"viability {option.get('viability', 0.0):.2f}")
        for member in sorted(option["members"], key=lambda item: item["final"] != option["anchor"]):
            additions = (f" [+{', '.join(member['new_entries'])}]" if member.get("new_entries") else "")
            if member["hidden_ability_caveat"]:
                share = member.get("hidden_ability_usage_share")
                caveat = (f" [hidden slot: {share:.0%} of mapped ability usage; normal build scored]"
                          if share is not None else " [hidden ability exists; not assumed]")
            else:
                caveat = ""
            favorite = " [favorite]" if member["favorite"] else ""
            lines.append(f"   {'ANCHOR' if member['final'] == option['anchor'] else '      '} "
                         f"{member['evolution']} — {'/'.join(member['types'])}, {member['tier']}"
                         f"{additions}{favorite}{caveat}")
    lines.extend("note: " + warning for warning in report["warnings"])
    return "\n".join(lines)
