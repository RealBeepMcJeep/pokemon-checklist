"""Pinned stock SOS facts → explicit ally-leaf caller references.

Preserve canonical encounter rows/rates/IDs. Unresolved source predicates produce
no edge; never guess slot pairing or borrow a caller's encounter percentage.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
FACTS = ROOT / "references" / "stock-sos-rules.json"
REGIONAL = {19, 20, 26, 27, 28, 37, 38, 50, 51, 52, 53, 74, 75, 76, 88, 89, 103, 105}


def normalized(value: str) -> str:
    text = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", text.removeprefix("alola "))


def time_possible(actor: dict, when: str) -> bool:
    rates = actor.get("rates") or {}
    return rates.get("single", 0) > 0 or rates.get(when, 0) > 0


def predicate(note: str, links: list[str], location: dict, group: dict, actor: dict) -> bool | None:
    lower = note.lower()
    method = group["sourceArea"]["method"]
    handled = False
    if "surfing" in lower:
        if method != "surf":
            return False
        handled = True
    if "fishing" in lower:
        if method not in {"super-rod", "bubbling-spots"}:
            return False
        handled = True
    if "caves" in lower:
        area = group["sourceArea"]["area"].lower()
        evidence = " ".join((area, group["name"], location["name"])).lower()
        if not re.search(r"cave|tunnel", evidence):
            return False if re.search(r"outside|grass|farthest-hollow", area) else None
        handled = True
    if ("day" in lower) != ("night" in lower):
        if not time_possible(actor, "day" if "day" in lower else "night"):
            return False
        handled = True
    if not note:
        return True
    place = normalized(group["sourceArea"]["location"].removeprefix("alola-"))
    geographic = [link for link in links if link not in {"Fishing", "Time"}]
    if geographic:
        linked = place in {normalized(link) for link in geographic}
        if lower.startswith("anywhere but "):
            return not linked
        if lower.startswith(("only on ", "only at ", "only in ", "only while ", "some encounters ")):
            return linked
    if handled or "will attack" in lower:
        return True
    return None


def can_call(actor: dict, group: dict, game: str, facts: dict) -> bool:
    if group["sourceArea"]["method"] == "island-scan" or any(
        re.search(r"Ultra Beast|Legendary|Totem|trial battle", value, re.I)
        for value in group.get("conditions", [])
    ):
        return False
    for entry in facts["noCall"]:
        if entry["speciesId"] != actor["speciesId"]:
            continue
        qualifier = entry["qualification"]
        if re.search(r"\bS M\b", qualifier) and game not in {"sun", "moon"}:
            continue
        restricted = next((key for key in ("blue-striped", "orange-flower", "blue-flower", "white-flower")
                           if normalized(key) in normalized(qualifier)), None)
        if restricted and actor.get("form") and actor["form"] != restricted:
            continue
        return False
    return True


def same_context(source: dict, caller: dict) -> bool:
    a, b = source["sourceArea"], caller["sourceArea"]
    if a["location"] != b["location"]:
        return False
    # generate() splits the original PokeAPI center bubbling group into
    # center-rustling-bush. The SOS record retains its original source key.
    if (a["location"], a["area"], a["method"], b["area"], b["method"]) == (
        "poni-plains", "center", "sos-from-bubbling-spot", "center-rustling-bush", "bubbling-spots"
    ):
        return True
    if a["area"] != b["area"]:
        return False
    if a["method"] == "sos-from-bubbling-spot":
        return b["method"] == "bubbling-spots"
    return b["method"] in {"walk", "surf", "super-rod", "berry-trees"}


def weather_clause(fact: dict, location: dict, group: dict, game: str) -> str | None:
    place = normalized(group["sourceArea"]["location"].removeprefix("alola-"))
    if place not in {normalized(link) for link in fact["linkTitles"]}:
        return None
    for clause in fact["locationText"].split(","):
        if not normalized(clause).startswith(place):
            continue
        if re.search(r"\bUS UM\b", clause) and game not in {"ultra-sun", "ultra-moon"}:
            continue
        if re.search(r"\bS M\b", clause) and game not in {"sun", "moon"}:
            continue
        area = group["sourceArea"]["area"].lower()
        qualifier = re.search(r"\(([^)]+)\)", clause)
        if qualifier:
            if not area or area in {"main", "all-areas"}:
                continue
            detail = qualifier[1].lower()
            if detail == "base":
                if "base" not in area:
                    continue
            elif detail.startswith("except base"):
                if "base" in area or ("cave" in detail and "cave" in area):
                    continue
            else:
                continue
        return clause.strip()
    return None


def annotate(data: dict) -> None:
    """Add source-backed leaf rules at the actual generator write boundary."""
    if data["mode"] not in {"sun", "moon", "ultra-sun", "ultra-moon"}:
        raise ValueError("stock SOS annotation cannot be applied to a hack mode")
    facts = json.loads(FACTS.read_text())
    if facts["source"]["sha256"] != "f5361cea7df8694bf88fe66cb29231ec6d9bbe7962ab6c8e7d993fb3e58e4b43":
        raise ValueError("unadmitted stock SOS reference revision")
    for island in data["islands"]:
        for location in island["locations"]:
            actors = [(g, r) for g in location["groups"] if g["encounterType"] != "sos"
                      and g["sourceArea"]["method"] != "island-scan" for r in g["encounters"]]
            for group in location["groups"]:
                if group["encounterType"] != "sos":
                    continue
                for target in group["encounters"]:
                    rules = []
                    for caller_group, actor in actors:
                        if not same_context(group, caller_group) or not can_call(actor, caller_group, data["mode"], facts):
                            continue
                        # The reference's species-level exceptions are not proof
                        # of cross-form relationships. Stock native regional rows
                        # must independently carry their exact Alolan identity.
                        if any(r["speciesId"] in REGIONAL and r.get("form") != "alolan" for r in (actor, target)):
                            continue
                        considered = [(fact, predicate(fact["note"], fact["linkTitles"], location, caller_group, actor))
                                      for fact in facts["ordinary"]
                                      if data["mode"] in fact["games"] and actor["speciesId"] == fact["caller"]]
                        applicable = [fact for fact, applies in considered if applies is True]
                        unresolved = any(applies is None for _, applies in considered)
                        for fact in applicable:
                            if target["speciesId"] not in fact["allies"]:
                                continue
                            rule = {"kind": "sos", "callerIds": [actor["id"]]}
                            if fact["note"]:
                                rule["conditions"] = [fact["note"]]
                            rules.append(rule)
                        if not applicable and not unresolved and actor["speciesId"] == target["speciesId"] and actor.get("form") == target.get("form"):
                            rules.append({"kind": "sos", "callerIds": [actor["id"]]})
                        for fact in facts["weather"]:
                            if fact["speciesId"] != target["speciesId"]:
                                continue
                            clause = weather_clause(fact, location, caller_group, data["mode"])
                            if clause is None:
                                continue
                            for weather in ("rain", "hail", "sandstorm"):
                                rate = re.fullmatch(r"(\d+)%(?: (Day|Night))?", fact[weather])
                                if rate:
                                    when = rate[2].lower() if rate[2] else None
                                    if when and not time_possible(actor, when):
                                        continue
                                    conditions = [f"During {weather}"]
                                    if when:
                                        conditions.append(f"Only during the {when}")
                                    if "(" in clause:
                                        conditions.append(clause)
                                    rules.append({"kind": "weather-sos", "callerIds": [actor["id"]],
                                                  "conditions": conditions, "rates": {"single": int(rate[1])}})
                    target["sosRules"] = rules
