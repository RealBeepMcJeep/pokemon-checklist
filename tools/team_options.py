#!/usr/bin/env python3
"""Five replayable story-team options: fixed catcher, one anchor, four partners.

Run against the live synced checklist; this command never changes the save.
"""
from __future__ import annotations

import itertools

import team_builder as tb
import team_synergy as ts


# Competitive rankings assume hidden abilities on these lines. They remain eligible
# but are deliberately less attractive when the player will not SOS-chain.
HIDDEN_ABILITY_DEPENDENT = {"Diggersby": 2.0, "Nidoking": 0.55, "Nidoqueen": 0.45}
UNVERIFIED_INDIVIDUAL_GATES = {"Salazzle", "Froslass", "Gallade", "Hitmonlee", "Hitmonchan", "Hitmontop"}
# This is a final-stage property: a Pichu does not make Raichu a non-OG Pokemon.
OG_LIMIT = 151
MAX_POOL = 24  # C(24, 5) = 42,504 per category; bounded brute force.


def conservative_profiles(profiles: list[dict]) -> list[dict]:
    """Score reliable *type potential*, not unverified competitive move acquisition.

    Same neutral attack strength per STAB type: the story decision is about team
    type gaps. A historical ladder coverage move might be egg/event/reminder-only.
    Never claim these are actual moves or an available four-move set.
    """
    return [{**p, "moves": [(typ, 80, 1.0) for typ in p["types"]],
             "attack_types": list(p["types"]),
             "coverage_source": "STAB-type potential proxy (not a move list)"}
            for p in profiles]


def is_evolving(member: dict) -> bool:
    return any(tb.normalize(name) != tb.normalize(member["final"]) for name in member["caught_as"])


def anchor_score(member: dict) -> float:
    """Individual endgame quality with real-catch ability and evolution caveats."""
    return (member["points"] - HIDDEN_ABILITY_DEPENDENT.get(member["final"], 0)
            - (0 if is_evolving(member) else 0.7))


def is_og(member: dict) -> bool:
    return int(member["endpoint_id"]) <= OG_LIMIT


def og_ready(member: dict) -> bool:
    """Strict OG-only: both terminal form and an owned starting stage are Gen 1."""
    return (is_og(member) and not member.get("alolan", False)
            and any(int(identifier) <= OG_LIMIT for identifier in member.get("caught_ids", ())))


def no_og_ready(member: dict) -> bool:
    """Neither the owned stage nor its final form may be an original-151 species."""
    return (not is_og(member)
            and all(int(identifier) > OG_LIMIT for identifier in member.get("caught_ids", ())))


def eligible_for_easy_run(profiles: list[dict]) -> list[dict]:
    """No sex or Tyrogue stat assumptions when the checklist stores neither."""
    return [p for p in profiles if p["final"] not in UNVERIFIED_INDIVIDUAL_GATES]


def _stage_bonus(member: dict) -> float:
    if not is_evolving(member):
        return 0
    # A terminal step reached by level-up is preferred over stones/friendship.
    return 0.27 if str(member.get("evo", "")).startswith("L") else 0.11


def _rank(pool: list[dict], utility: dict, chart: dict, *, category: str) -> list[dict]:
    ranked = []
    for combo in itertools.combinations(pool, 5):
        if category == "Mixed" and (all(is_og(p) for p in combo) or
                                    all(not is_og(p) for p in combo)):
            continue
        # One caught Ralts must not occupy both Gallade and Gardevoir slots.
        owned = [set(p.get("caught_ids", ())) for p in combo]
        if any(a & b for a, b in itertools.combinations(owned, 2)):
            continue
        core, detail = ts.score_team(list(combo), chart)
        full, full_detail = ts.score_team([*combo, utility], chart)
        by_type = [typ for p in combo for typ in p["types"]]
        repeated = len(by_type) - len(set(by_type))
        utility_overlap = len(set(utility["types"]) & set(by_type))
        anchor = max(combo, key=lambda p: (anchor_score(p), p["final"]))
        # Core coverage and defence dominate; fixed Butterfree affects every option.
        # Stage and no-grind preferences break ties, not absolute eligibility.
        value = (0.75 * core + 0.25 * full + sum(_stage_bonus(p) for p in combo)
                 - 0.40 * repeated - 0.32 * utility_overlap
                 - sum(HIDDEN_ABILITY_DEPENDENT.get(p["final"], 0) for p in combo)
                 + 0.18 * anchor_score(anchor)
                 + 0.12 * sum(bool(p.get("favorite")) for p in combo))
        ranked.append({"category": category, "anchor": anchor["final"],
                       "utility": utility["final"], "members": sorted(p["final"] for p in combo),
                       "profiles": combo, "ranking": round(value, 4),
                       "core_score": round(core, 4), "six_score": round(full, 4),
                       "core_detail": detail, "six_detail": full_detail,
                       "evolving": sum(is_evolving(p) for p in combo),
                       "level_evolving": sum(_stage_bonus(p) > 0.2 for p in combo),
                       "shared_types": repeated})
    ranked.sort(key=lambda o: (-o["ranking"], o["members"]))
    return ranked


def choose_options(profiles: list[dict], utility: dict, chart: dict,
                   *, min_changes: int = 2, pool_limit: int = MAX_POOL) -> list[dict]:
    """Try OG-only, no-OG, then three diverse mixed five-member cores."""
    if pool_limit < 5 or pool_limit > MAX_POOL:
        raise ValueError(f"pool_limit must be between 5 and {MAX_POOL}")
    # Form is absent from the sync record. Do not assume a regional form is owned.
    usable = eligible_for_easy_run([p for p in profiles if p["final"] != utility["final"]
                                    and not p.get("alolan", False)])
    usable.sort(key=lambda p: (-anchor_score(p), -is_evolving(p), p["final"]))
    old = [p for p in usable if og_ready(p)]
    # If the owned roster has a full viable pool, do not fill the story team
    # with a (PU) line merely to win a small heuristic coverage/diversity bonus.
    strong = [p for p in usable if tb.tier_passes(p.get("tier"), "NU")]
    new_strong = [p for p in strong if no_og_ready(p)]
    new = new_strong if len(new_strong) >= 5 else [p for p in usable if no_og_ready(p)]
    mixed = strong if len(strong) >= 5 and any(og_ready(p) for p in strong) and new_strong else usable
    results = []
    for category, candidates in (("OG-151", old), ("No OG-151", new),
                                 ("Mixed", mixed)):
        # In the mixed pool, retain a few of each group even when one dominates tiers.
        if category == "Mixed":
            candidates = ([p for p in mixed if og_ready(p)][:8]
                          + [p for p in mixed if no_og_ready(p)][:pool_limit])
            candidates.sort(key=lambda p: (-anchor_score(p), p["final"]))
            candidates = candidates[:pool_limit]
            if len(old) >= 1 and not any(is_og(p) for p in candidates):
                candidates[-1] = old[0]
            if len(new) >= 1 and not any(not is_og(p) for p in candidates):
                candidates[-1] = new[0]
        else:
            candidates = candidates[:pool_limit]
        if len(candidates) < 5:
            results.append({"category": category, "utility": utility["final"],
                            "members": [], "warning": f"only {len(candidates)} eligible owned candidates"})
            continue
        ranked = _rank(candidates, utility, chart, category=category)
        if category != "Mixed":
            results.append(ranked[0] if ranked else {"category": category, "utility": utility["final"],
                          "members": [], "warning": "no five independently owned lineages"})
            continue
        for option in ranked:
            names = set(option["members"])
            if all(len(names - set(other.get("members", ()))) >= min_changes
                   for other in results if other.get("members")):
                results.append(option)
            if sum(item["category"] == "Mixed" for item in results) == 3:
                break
        while sum(item["category"] == "Mixed" for item in results) < 3:
            results.append({"category": "Mixed", "utility": utility["final"],
                            "members": [], "warning": "insufficient distinct legal teams"})
    return results


# Prismatic Moon Standard overrides pinned vanilla evolution metadata. Keep this
# narrow and sourced from references/prismatic-moon/Evolution Changes.pdf.
HACK_EVOLUTIONS = {
    ("Klink", "Klang"): "L28", ("Klang", "Klinklang"): "L39",
    ("Rufflet", "Braviary"): "L34", ("Snorunt", "Glalie"): "L30",
    ("Charjabug", "Vikavolt"): "Thunder Stone",
    ("Haunter", "Gengar"): "high friendship + level",
    ("Slowpoke", "Slowking"): "level holding King's Rock",
}


def evolution_chain(member: dict, roster: dict, *, og_only: bool = False) -> tuple[str, str]:
    """Show one actually owned entry stage and its canonical, hack-correct path."""
    owned = [(int(i), roster["by_id"][int(i)]["name"]) for i in member["caught_ids"]]
    if og_only:
        owned = [(i, name) for i, name in owned if i <= OG_LIMIT]
    path = (roster.get("det", {}).get(member["endpoint_id"], {}).get("evolution") or [])
    steps = [step for step in path if isinstance(step, dict) and step.get("name")]
    stages = [str(step["name"]) for step in steps]
    selected = next(((i, name) for i, name in owned if tb.normalize(name) in
                     {tb.normalize(stage) for stage in stages}), owned[0])
    index = next((n for n, stage in enumerate(stages)
                  if tb.normalize(stage) == tb.normalize(selected[1])), 0)
    pieces = [selected[1]]
    for previous, step in zip(stages[index:-1], steps[index + 1:]):
        name = str(step["name"])
        method = HACK_EVOLUTIONS.get((previous, name), str(step.get("method", "")).replace("Level ", "L"))
        pieces.append(f"{name} ({method})" if method else name)
    if len(pieces) == 1 and tb.normalize(pieces[-1]) != tb.normalize(member["final"]):
        pieces.append(member["final"])
    return selected[1], " → ".join(pieces)


def starred_ids(roster: dict) -> set[int]:
    return {int(key.split(":", 1)[1]) for key, record in roster.get("records", {}).items()
            if key.startswith("star:") and record.get("s") == "on"}


def story_report(roster: dict, options: list[dict], utility: dict) -> dict:
    stars = starred_ids(roster)
    rendered = []
    for option in options:
        members = []
        for p in option.get("profiles", ()):
            owned, chain = evolution_chain(p, roster, og_only=option["category"] == "OG-151")
            owned_dex = next((int(i) for i in p["caught_ids"]
                              if roster["by_id"][int(i)]["name"] == owned), int(p["caught_ids"][0]))
            members.append({"owned": owned, "owned_dex": owned_dex,
                            "final": p["final"], "dex": int(p["endpoint_id"]), "evolution": chain,
                            "types": p["types"], "tier": p["tier"],
                            "favorite": bool(stars.intersection(p["caught_ids"])),
                            "hidden_ability_caveat": p["final"] in HIDDEN_ABILITY_DEPENDENT})
        rendered.append({k: v for k, v in option.items() if k != "profiles"}
                        | {"members": members})
    return {"caught_records": roster["caught_count"], "endpoints": roster["canonical_count"],
            "utility": utility["final"], "utility_dex": int(utility["endpoint_id"]), "options": rendered,
            "warnings": ["Heuristic scores are not win probabilities; attack coverage is a STAB-type potential proxy, not a verified move list.",
                         "The checklist does not store ability, sex, regional form, current level or owned items.",
                         "Butterfree is sleep utility; it cannot use False Swipe. Pair with another safe HP-control move when catching."]}


def format_story_report(report: dict) -> str:
    lines = [f"{report['caught_records']} caught, {report['endpoints']} evolution endpoints; fixed catcher: {report['utility']}"]
    for index, option in enumerate(report["options"], 1):
        if not option["members"]:
            lines.append(f"{index}. {option['category']}: {option['warning']}")
            continue
        lines.append(f"{index}. {option['category']} | anchor {option['anchor']} | "
                     f"{option['evolving']}/5 can evolve ({option['level_evolving']} by level) | "
                     f"core {option['core_score']:.2f}, with catcher {option['six_score']:.2f}")
        for member in sorted(option["members"], key=lambda p: p["final"] != option["anchor"]):
            lines.append(f"   {'ANCHOR' if member['final'] == option['anchor'] else '      '} "
                         f"{member['evolution']} — {'/'.join(member['types'])}, {member['tier']}"
                         f"{' [current favorite]' if member['favorite'] else ''}"
                         f"{' [hidden-ability tier caveat]' if member['hidden_ability_caveat'] else ''}")
    lines.extend("note: " + warning for warning in report["warnings"])
    return "\n".join(lines)
