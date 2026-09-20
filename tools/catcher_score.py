#!/usr/bin/env python3
"""Rank the owner's Pokemon as catching leads, by how easily they can do the catching job.

Catching needs a target asleep and at 1 HP. This scores each family on the catching tools it
can actually get, on the principle that a tool is worth its benefit times the chance it lands,
discounted by what it costs to obtain and how long you must wait.

MODEL
  A move belongs to exactly one BENEFIT category, and only the best contribution per category
  counts. Running two sleep moves is pointless, so two sleep moves must not both score; the
  same applies to two paralysis moves or a freeze chance plus a freeze move.

  category        base  what it is
  sleep             60  the status the whole plan rests on (Yawn counts half: it is 100%
                        accurate but lands a turn late and can be switched out of)
  false swipe       25  the only way to leave the target at exactly 1 HP
  super fang         8  halves HP: a good opener before the chipping
  freeze            10  effectively permanent, but see the chance multiplier below
  paralysis          7  x1.5 catch rate, and the safe fallback when sleep misses
  anti-ghost         6  Foresight / Odor Sleuth / Soak: Normal moves hit Ghosts
  immunity strip     3  Gastro Acid: beats Insomnia and Overcoat when that is actually relevant
  trapping           2  Mean Look / Spider Web / Block. Near-worthless against ordinary
                        wild Pokemon, but the answer to anything that flees - see
                        --fleeing, which re-scores the whole model for that case.
  burn / poison      0  they raise the catch rate but damage the target - not a tool

  every contribution is multiplied by:
    chance      the move's real land rate: accuracy x the effect's own chance where the
                status rides on a secondary effect. Ice Beam is 100% x 10%, not 100%, and
                Body Slam 100% x 30% - this is what keeps a 10% freeze roll out of the plan
    ability     Compound Eyes boosts move accuracy x1.3 (capped at 100); No Guard makes
                move accuracy 100%. Neither ability changes a secondary effect's own chance.
    acquisition level-up 1.0 (you get it by playing) | TM 0.8 (found, location not
                modelled) | tutor 1 - BP/40 | egg 0.5 (breeding) | move reminder 0.2
                and event 0.2 (both essentially endgame)
    speed       1 / (1 + max(0, level - 10) / 40): full marks at level 10, decaying after

  Score = sleep + False Swipe + the other categories, the extras dampened by rank (60%, then
  36%, ...) so a long list of marginal tools cannot outrank one dependable sleeper.

Usage: python3 tools/catcher_score.py --uid <uid> [--exclude caterpie,butterfree] [--top 15]
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parent
sys.path.insert(0, str(TOOLS))
import moveline as ml  # noqa: E402  (shared parsing, one source of truth)
from showdown_data import configured_cache_dir, require_cache  # noqa: E402
from showdown_text import field, object_after  # noqa: E402

CATEGORY_BASE = {
    "sleep": 60, "falseswipe": 25, "superfang": 8, "freeze": 10,
    "paralysis": 7, "antighost": 6, "immunity": 3, "trapping": 2,
}
STATUS_CATEGORY = {"slp": "sleep", "par": "paralysis", "frz": "freeze",
                   "brn": None, "psn": None, "tox": None}
FIXED_CATEGORY = {
    "falseswipe": "falseswipe", "superfang": "superfang",
    "odorsleuth": "antighost", "foresight": "antighost", "soak": "antighost",
    "gastroacid": "immunity",
    "meanlook": "trapping", "spiderweb": "trapping", "block": "trapping",
}
# The Move Reminder is in Mount Lanakila's Pokemon Center - the area before the League -
# so a level-1 move is an ENDGAME move for a playthrough, not a free one. It is scored
# like an event move for that reason. TMs and tutors still lack a location model.
# Egg moves are 0.9, not 0.5: Prismatic Moon (Standard) makes Pokemon learn egg moves by
# simply levelling up, so in this game they are nearly a level-up move. The level the
# hack assigns is unknown, so the timing stays neutral rather than guessed.
ACQ = {"level": 1.0, "reminder": 0.2, "TM": 0.8, "egg": 0.9, "event": 0.2}
# Where each tutor move is taught, from Serebii's USUM Move Tutors page - parsed, not typed.
# This is the axis that was missing: a Battle Tree move is late-game, so it must be dampened
# like one, while a Big Wave Beach move is available at the end of the first island.
TUTOR_LOCATION = {
    **{m: 0.80 for m in ['snore', 'healbell', 'electroweb', 'defog', 'lowkick', 'uproar', 'bind', 'helpinghand', 'shockwave', 'block', 'lastresort', 'covet', 'bugbite', 'snatch', 'recycle']},   # Big Wave Beach, Melemele
    **{m: 0.65 for m in ['irontail', 'spite', 'afteryou', 'gigadrain', 'synthesis', 'allyswitch', 'signalbeam', 'gravity', 'stealthrock', 'irondefense', 'telekinesis', 'magnetrise', 'bounce', 'roleplay', 'firepunch', 'waterpulse']},   # Heahea Beach, Akala
    **{m: 0.55 for m in ['ironhead', 'aquatail', 'painsplit', 'tailwind', 'thunderpunch', 'endeavor', 'focuspunch', 'icywind', 'zenheadbutt', 'seedbomb', 'laserfocus', 'trick', 'drillrun', 'magiccoat', 'icepunch', 'wonderroom', 'magicroom']},   # Ula'ula Beach
    **{m: 0.25 for m in ['liquidation', 'gastroacid', 'foulplay', 'superfang', 'outrage', 'skyattack', 'throatchop', 'stompingtantrum', 'skillswap', 'earthpower', 'gunkshot', 'dualchop', 'drainpunch', 'heatwave', 'hypervoice', 'superpower', 'knockoff', 'dragonpulse']},   # Battle Tree, Poni - late
}
# Where the TM is found. Reported, deliberately NOT dampened: turning a location into a
# progress factor needs a verified route-to-island table first, and guessing one would be
# the same error as scoring the Move Reminder as free.
TM_LOCATION = {'workup': 'Route 1 - Trainer School', 'dragonclaw': 'Vast Poni Canyon', 'psyshock': 'Lake of the Moone/Lake of the Sunne', 'calmmind': 'Seafolk Village Pok�Mart', 'roar': "Kala'e Bay", 'toxic': 'Aether Paradise', 'hail': 'Royal Avenue - Pok�Mart', 'bulkup': 'Royal Avenue', 'venoshock': 'Konikoni City Pok�Mart', 'hiddenpower': 'Paniola Ranch', 'sunnyday': 'Royal Avenue - Pok�Mart', 'taunt': 'Route 13', 'icebeam': 'Mount Lanakila', 'blizzard': 'Seafolk Village Pok�Mart', 'hyperbeam': 'Seafolk Village Pok�Mart', 'lightscreen': 'Heahea City Pok�Mart', 'protect': 'Heahea City Pok�Mart', 'raindance': 'Royal Avenue - Pok�Mart', 'roost': 'Route 3', 'safeguard': 'Heahea City Pok�Mart', 'frustration': 'Malie City', 'solarbeam': 'Seafolk Village Pok�Mart', 'smackdown': 'Ten Carat Hill', 'thunderbolt': 'Sandy Cave', 'thunder': 'Seafolk Village Pok�Mart', 'earthquake': 'Resolution Cave', 'return': 'Malie City', 'leechlife': 'Akala Outskirts', 'psychic': 'Aether Paradise', 'shadowball': 'Route 14', 'brickbreak': 'Verdant Cavern', 'doubleteam': 'Route 7', 'reflect': 'Heahea City Pok�Mart', 'sludgewave': 'Seafolk Village Pok�Mart', 'flamethrower': 'Vast Poni Canyon', 'sludgebomb': 'Shady House', 'sandstorm': 'Royal Avenue - Pok�Mart', 'fireblast': 'Seafolk Village Pok�Mart', 'rocktomb': 'Wela Volcano Park', 'aerialace': 'Konikoni City Pok�Mart', 'torment': 'Route 5', 'facade': 'Malie City Pok�Mart', 'flamecharge': 'Route 8', 'rest': 'Royal Avenue - Thrifty Megamart', 'attract': 'Hano Grand Resort', 'thief': 'Verdant Cavern', 'lowsweep': 'Konikoni City Pok�Mart', 'round': "Hau'oli City", 'echoedvoice': "Hau'oli City", 'overheat': 'Poni Meadow', 'steelwing': 'Konikoni City Pok�Mart', 'focusblast': 'Seafolk Village Pok�Mart', 'energyball': 'Route 8', 'falseswipe': 'Iki Town', 'scald': 'Ancient Poni Path', 'fling': "Hau'oli Cemetery", 'chargebeam': 'Brooklet Hill', 'skydrop': 'Route 8', 'brutalswing': 'Route 5', 'quash': 'Poni Plains', 'will-o-wisp': 'Konikoni City', 'acrobatics': 'Route 15', 'embargo': 'Blush Mountain', 'explosion': 'Ten Carat Hill', 'shadowclaw': 'Malie City Pok�Mart', 'payback': 'Route 11', 'smartstrike': 'Lush Jungle', 'gigaimpact': 'Seafolk Village Pok�Mart', 'rockpolish': 'Malie City Pok�Mart', 'auroraveil': 'Heahea City Pok�Mart', 'stoneedge': 'Seafolk Village Pok�Mart', 'voltswitch': 'Mount Hokulani', 'thunderwave': 'Malie Garden', 'gyroball': 'Route 11', 'swordsdance': 'Poni Meadow', 'fly': 'Malie City', 'psychup': 'Malie City Pok�Mart', 'bulldoze': 'Konikoni City Pok�Mart', 'frostbreath': 'Seaward Cave', 'rockslide': 'Route 17', 'x-scissor': 'Route 16', 'dragontail': 'Route 12', 'infestation': 'Route 3', 'poisonjab': 'Mount Lanakila', 'dreameater': 'Haina Desert', 'grassknot': 'Lush Jungle', 'swagger': 'Route 2', 'sleeptalk': 'Paniola Town', 'u-turn': 'Malie City Pok�Mart', 'substitute': 'Route 1', 'flashcannon': 'Seafolk Village', 'trickroom': 'Hano Grand Resort', 'wildcharge': 'Vast Poni Canyon', 'surf': 'Poni Breaker Coast', 'snarl': 'Mount Hokulani', 'naturepower': 'Route 5', 'darkpulse': 'Poni Coast', 'waterfall': 'Poni Breaker Coast', 'dazzlinggleam': 'Vast Poni Canyon', 'confide': "Hau'oli Cemetery"}

LABEL = {"sleep": "sleep", "falseswipe": "False Swipe", "superfang": "Super Fang",
         "freeze": "freeze chance", "paralysis": "paralysis", "antighost": "anti-Ghost",
         "immunity": "immunity strip", "trapping": "trapping"}


# Progress by island. The app's own encounter data maps every location it knows to an
# island, and Island.order is the game's progression order, so this needs no outside source.
ISLAND_FACTOR = {1: 0.85, 2: 0.70, 3: 0.55, 4: 0.30}
# An island also says roughly how far in you are, which is what the speed factor needs:
# a TM found on island 1 is usable almost immediately, one at Mount Lanakila is not.
ISLAND_LEVEL = {1: 15, 2: 25, 3: 35, 4: 50}
ISLAND_OF: dict[str, int] = {}


def normalize_place(name: str) -> str:
    """Normalize a data-set location name without collapsing words together."""
    return re.sub(r"[^a-z0-9]+", " ", str(name).lower()).strip()


def load_islands(repo: Path) -> dict[str, int]:
    """Map actual encounter location records to island 1..4.

    The encounter schema stores island order in the list position and location
    order on each location record; there is no ``order`` field on island objects.
    """
    data = json.loads((repo / "data" / "encounters.json").read_text())
    out: dict[str, int] = {}
    for island_number, island in enumerate(data.get("islands", []), start=1):
        for location in island.get("locations", []):
            name = location.get("name")
            if name:
                out.setdefault(normalize_place(name), island_number)
            location_id = str(location.get("id") or "")
            if "/" in location_id:
                out.setdefault(normalize_place(location_id.rsplit("/", 1)[-1].replace("-", " ")), island_number)
    # Iki Town has no encounter record but is explicitly the opening Melemele area.
    out.setdefault("iki town", 1)
    return out


def island_for_place(place: str | None) -> int | None:
    if not place:
        return None
    key = normalize_place(place)
    if key in ISLAND_OF:
        return ISLAND_OF[key]
    # TM_LOCATION contains sub-area labels such as "Route 1 - Trainer School".
    for part in re.split(r"\s+-\s+|/", place):
        part_key = normalize_place(part)
        if part_key in ISLAND_OF:
            return ISLAND_OF[part_key]
    for location, island in ISLAND_OF.items():
        if location and (location in key or key in location):
            return island
    return None


def ability_slots(body: str) -> dict[str, str]:
    m = re.search(r"abilities: \{(.*?)\}", body, re.S)
    if not m:
        return {}
    return {slot: name.strip() for slot, name in
            re.findall(r"[\'\"]?([01H])[\'\"]?: [\'\"]?([^\'\",]+)[\'\"]?", m.group(1))}


def accuracy(body: str) -> float:
    """Return a move's own accuracy; ``true`` means the move cannot miss."""
    if re.search(r"\baccuracy: true", body):
        return 100.0
    found = re.search(r"\baccuracy: (\d+)", body)
    return float(found.group(1)) if found else 100.0


def secondary_effect(body: str) -> tuple[int, str] | None:
    """Read the singular Showdown ``secondary`` object only."""
    secondary = object_after(body, "secondary")
    if not secondary:
        return None
    chance = re.search(r"\bchance:\s*(\d+)", secondary)
    status = re.search(r"\bstatus:\s*['\"]([a-z]+)['\"]", secondary)
    if not chance or not status:
        return None
    return int(chance.group(1)), status.group(1)


def benefit_details(move: str, body: str) -> tuple[str, float, float] | None:
    """Return ``(category, move_accuracy, effect_chance)``.

    Accuracy abilities modify only the second value.  A secondary status keeps
    its own roll separate, so Body Slam is 100% x 30%, not 100%.
    """
    move = ml.normalize(move)
    move_accuracy = accuracy(body) / 100
    if move == "yawn":
        return ("sleep", move_accuracy, 0.5)
    if move in FIXED_CATEGORY:
        return (FIXED_CATEGORY[move], move_accuracy, 1.0)

    primary = re.search(r"\bstatus:\s*['\"]([a-z]+)['\"]", body)
    secondary_at = re.search(r"\bsecondary\s*:", body)
    if primary and (not secondary_at or primary.start() < secondary_at.start()):
        category = STATUS_CATEGORY.get(primary.group(1))
        return (category, move_accuracy, 1.0) if category else None

    effect = secondary_effect(body)
    if effect:
        chance, status = effect
        category = STATUS_CATEGORY.get(status)
        return (category, move_accuracy, chance / 100) if category else None
    return None


def benefit(move: str, body: str) -> tuple[str, float] | None:
    """Compatibility view: category and actual unmodified land chance."""
    details = benefit_details(move, body)
    if not details:
        return None
    category, move_accuracy, effect_chance = details
    return category, move_accuracy * effect_chance


def accuracy_with_ability(move_accuracy: float, ability: str | None) -> float:
    """Apply only the accuracy effect of a known ability."""
    if ability == "No Guard":
        return 100.0
    if ability == "Compound Eyes":
        return min(100.0, move_accuracy * 1.3)
    return move_accuracy


def hit_chance(move_accuracy: float, effect_chance: float, ability: str | None = None) -> float:
    return min(1.0, accuracy_with_ability(move_accuracy, ability) / 100) * effect_chance


def easiest(gates: dict[str, list[str]], move: str) -> tuple[str, float, int]:
    """The cheapest way this family gets the move: (label, factor, level)."""
    options = []
    for gate, levels in gates.items():
        if gate == "level":
            level = min(int(x) for x in levels)
            options.append((f"L{level}" if level > 1 else "reminder",
                            ACQ["reminder"] if level == 1 else ACQ["level"], level))
        elif gate == "tutor":
            cost = ml.TUTOR_BP.get(move, 8)
            # Location first, price second: the Battle Tree is post-game, Big Wave Beach is
            # the first island. Where it is matters far more than what it costs.
            place = TUTOR_LOCATION.get(move, 0.4)
            options.append((f"tutor {cost} BP", place * (1 - cost / 100), 60))
        elif gate == "TM":
            where = TM_LOCATION.get(move)
            island = island_for_place(where)
            # Found on island 1 is nearly free; found at Mount Lanakila is endgame.
            factor = ACQ["TM"] * ISLAND_FACTOR.get(island or 0, 1.0)
            level = ISLAND_LEVEL.get(island or 0, 40)
            options.append((f"TM at {where}" if where else "TM", factor, level))
        elif gate == "egg":
            options.append(("egg", ACQ["egg"], 30))  # level unknown in the hack
        else:
            options.append((gate, ACQ["event"], 60))
    return min(options, key=lambda t: (-t[1], t[2]))


def _species_token_without_index(token: str) -> str:
    raw = str(token).strip().lower()
    if raw in {"mr. mime", "mr mime"}:
        return "mr-mime"
    if "♀" in raw:
        return ml.normalize(raw.replace("♀", "")) + "-f"
    if "♂" in raw:
        return ml.normalize(raw.replace("♂", "")) + "-m"
    return ml.normalize(raw)


def resolve_species_token(token: str, rows: list[dict]) -> dict:
    value = str(token).strip()
    by_key = {}
    for row in rows:
        by_key[str(row.get("id"))] = row
        by_key[_species_token_without_index(row.get("slug", ""))] = row
        by_key[_species_token_without_index(row.get("name", ""))] = row
    found = by_key.get(value) or by_key.get(_species_token_without_index(value))
    if not found:
        raise ValueError(f"no such species: {token}")
    return found


def normalize_species_list(raw: str, rows: list[dict] | None = None) -> list[str]:
    tokens = [item.strip() for item in str(raw).split(",") if item.strip()]
    if rows is None:
        return [_species_token_without_index(item) for item in tokens]
    return [ml.normalize(str(resolve_species_token(item, rows)["slug"])) for item in tokens]


def _evolution_maps(dex: dict[str, str]) -> tuple[dict[str, str], dict[str, list[str]]]:
    prevo = {}
    children = {}
    for key, body in dex.items():
        parent = field(body, "prevo")
        if parent:
            prevo[key] = ml.normalize(parent)
        values = ml.list_field(body, "evos")
        if values:
            children[key] = values
    return prevo, children


def reachable_descendant_paths(slug: str, dex: dict[str, str]) -> list[list[str]]:
    """Return mutually exclusive paths from a candidate through each final form."""
    slug = ml.normalize(slug)
    _, children = _evolution_maps(dex)
    paths: list[list[str]] = []

    def walk(node: str, path: list[str]) -> None:
        next_nodes = [child for child in children.get(node, []) if child in dex]
        if not next_nodes:
            paths.append(path)
            return
        for child in next_nodes:
            walk(child, path + [child])

    if slug not in dex:
        return []
    walk(slug, [slug])
    return paths or [[slug]]


def family_nodes(slug: str, dex: dict[str, str]) -> set[str]:
    prevo, _ = _evolution_maps(dex)
    root = ml.normalize(slug)
    while root in prevo:
        root = prevo[root]
    return {node for path in reachable_descendant_paths(root, dex) for node in path}


def branch_constraints(path: list[str], dex: dict[str, str]) -> list[str]:
    constraints = []
    for node in path:
        gender = field(dex.get(node, ""), "gender")
        if gender:
            label = {"M": "male", "F": "female"}.get(gender.upper(), gender)
            constraints.append(f"requires {label}")
    return list(dict.fromkeys(constraints))


def total_from_parts(parts: list[dict]) -> float:
    sleep = next((part["value"] for part in parts if part["category"] == "sleep"), 0.0)
    swipe = next((part["value"] for part in parts if part["category"] == "falseswipe"), 0.0)
    extras = sorted((part["value"] for part in parts if part["category"] not in {"sleep", "falseswipe"}), reverse=True)
    return sleep + swipe + sum(value * 0.6 ** (rank + 1) for rank, value in enumerate(extras))


def _ability_variants(path: list[str], dex: dict[str, str]) -> list[tuple[str | None, bool]]:
    found: list[tuple[str | None, bool]] = [(None, False)]
    seen = {(None, False)}
    for node in path:
        for slot, ability in ability_slots(dex.get(node, "")).items():
            item = (ability, slot == "H")
            if item not in seen:
                found.append(item)
                seen.add(item)
    return found


def _score_branch(
    path: list[str],
    learned: dict[str, str],
    dex: dict[str, str],
    moves: dict[str, str],
    *,
    bases: dict[str, float],
    fleeing: bool,
    name_of: dict[str, str],
) -> dict:
    best_branch = None
    for ability, hidden in _ability_variants(path, dex):
        best: dict[str, dict] = {}
        trace: list[dict] = []
        for form in path:
            for move, gates in ml.gen7_moves(learned.get(form, "")).items():
                details = benefit_details(move, moves.get(move, ""))
                if not details or details[0] not in bases or (fleeing and move == "yawn"):
                    continue
                category, move_accuracy, effect_chance = details
                effective_accuracy = accuracy_with_ability(move_accuracy * 100, ability)
                if hidden and ability == "Compound Eyes":
                    effective_accuracy = min(100.0, move_accuracy * 100 * 1.3 * 0.7)
                hit = min(1.0, effective_accuracy / 100) * effect_chance
                label, factor, level = easiest(gates, move)
                speed = 1 / (1 + max(0, level - 10) / 40)
                if fleeing and category == "sleep":
                    hit = hit ** 2
                value = bases[category] * hit * factor * speed
                if value <= 0:
                    continue
                note = f"{field(moves.get(move, ''), 'name') or move} via {name_of.get(form, form)} {label} [{hit * 100:.0f}%]"
                if ability:
                    note += f" *{ability}{' (hidden)' if hidden else ''}*"
                item = {
                    "category": category,
                    "move": field(moves.get(move, ""), "name") or move,
                    "form": name_of.get(form, form),
                    "acquisition": label,
                    "accuracy": move_accuracy,
                    "effect_chance": effect_chance,
                    "land": hit,
                    "ability": ability,
                    "hidden": hidden,
                    "factor": factor,
                    "level": level,
                    "speed": speed,
                    "value": value,
                    "note": note,
                }
                trace.append(item)
                if value > best.get(category, {"value": 0})["value"]:
                    best[category] = item
        parts = sorted(best.values(), key=lambda part: -part["value"])
        if fleeing and "trapping" not in best:
            for index, part in enumerate(parts):
                if part["category"] == "falseswipe":
                    parts[index] = {**part, "value": part["value"] * 0.3, "note": part["note"] + " (one-action penalty)"}
        total = total_from_parts(parts)
        candidate = {"parts": parts, "trace": trace, "score": total, "ability": ability, "hidden": hidden}
        if best_branch is None or candidate["score"] > best_branch["score"]:
            best_branch = candidate
    return {
        "path": path,
        "constraints": branch_constraints(path, dex),
        **(best_branch or {"parts": [], "trace": [], "score": 0.0, "ability": None, "hidden": False}),
        "explain_total": total_from_parts((best_branch or {}).get("parts", [])),
    }


def score_parts(
    slug: str,
    learned: dict[str, str],
    dex: dict[str, str],
    moves: dict[str, str],
    *,
    bases: dict[str, float] | None = None,
    fleeing: bool = False,
    name_of: dict[str, str] | None = None,
) -> dict:
    """Score each reachable branch independently; return the selected branch and trace."""
    bases = dict(bases or CATEGORY_BASE)
    name_of = name_of or {}
    branches = [_score_branch(path, learned, dex, moves, bases=bases, fleeing=fleeing, name_of=name_of)
                for path in reachable_descendant_paths(slug, dex)]
    selected = max(branches, key=lambda branch: (branch["score"], branch["path"])) if branches else {
        "path": [slug], "constraints": [], "parts": [], "trace": [], "score": 0.0, "explain_total": 0.0,
    }
    return {
        "slug": slug,
        "score": selected["score"],
        "branches": branches,
        "selected_branch": selected,
        "parts": selected["parts"],
        "trace": selected["trace"],
    }


def read_account_roster(uid: str, repo: Path) -> list[str]:
    command = ["node", str(TOOLS / "firebase-admin-rest.mjs"), "--read", f"/users/{uid}/state/records"]
    try:
        out = subprocess.run(command, capture_output=True, text=True, cwd=repo)
    except OSError as exc:
        raise RuntimeError(f"account read failed to start: {exc}") from exc
    if out.returncode != 0:
        detail = (out.stderr or out.stdout or "no error text").strip()
        raise RuntimeError(f"account read failed (exit {out.returncode}): {detail}")
    try:
        records = json.loads(out.stdout or "null")
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"account read failed: invalid JSON: {exc}") from exc
    if records is None:
        records = {}
    if not isinstance(records, dict):
        raise RuntimeError("account read failed: records payload is not an object")
    ids = set()
    for key, value in records.items():
        if not isinstance(value, dict):
            raise RuntimeError(f"account read failed: record {key!r} is not an object")
        match = re.fullmatch(r"(?:species|star):(\d+)", str(key))
        if match and ((str(key).startswith("species:") and value.get("s") == "caught") or
                      (str(key).startswith("star:") and value.get("s") == "on")):
            ids.add(int(match.group(1)))
    return sorted(str(item) for item in ids)


def _print_explanation(candidate: dict) -> None:
    branch = candidate["selected_branch"]
    print(f"\n=== how {candidate['name']} is scored ===")
    print(f"branch: {' -> '.join(branch['path'])}")
    if branch["constraints"]:
        print("constraints: " + ", ".join(branch["constraints"]))
    print(f"ability assumption: {branch.get('ability') or 'ordinary accuracy'}")
    print(f"{'category':12} {'move':16} {'form':14} {'land':>7} {'value':>8}")
    for item in branch["trace"]:
        mark = "*" if any(item is part for part in branch["parts"]) else " "
        print(f"{mark}{item['category']:12} {item['move']:16} {item['form']:14} {item['land'] * 100:6.1f}% {item['value']:8.2f}")
    print(f"  TOTAL       {branch['explain_total']:7.2f}   (same score used for ranking)\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Rank Pokemon as catching leads.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--uid", help="read this account's caught and starred species")
    source.add_argument("--species", help="comma-separated names, slugs, or dex numbers")
    parser.add_argument(
        "--cache",
        default=str(configured_cache_dir()),
        help="verified shared Showdown cache (bootstrap it first)",
    )
    parser.add_argument("--top", type=int, default=15)
    parser.add_argument("--exclude", default="", help="names/slugs to leave out, including their family")
    parser.add_argument("--explain", help="print every arithmetic step for one normalized species")
    parser.add_argument("--fleeing", action="store_true", help="score for a target that leaves this turn")
    parser.add_argument("--json", action="store_true", help="emit structured JSON")
    args = parser.parse_args()

    try:
        cache = Path(args.cache)
        store = require_cache(cache)
        learned = dict(ml.top_blocks(store.get_text("learnsets")))
        dex = dict(ml.top_blocks(store.get_text("pokedex")))
        moves = dict(ml.top_blocks(store.get_text("moves")))
        global ISLAND_OF
        ISLAND_OF = load_islands(REPO)
        rows = json.loads((REPO / "data" / "pokemon.json").read_text())
        rows = rows if isinstance(rows, list) else list(rows.values())
        name_of = {ml.normalize(r["slug"]): r["name"] for r in rows}
        by_id = {int(r["id"]): r for r in rows}
        details = {int(d["id"]): d for d in json.loads((REPO / "data" / "pokedex-details.json").read_text())["species"]}
        tier_of = {ml.normalize(r["slug"]): (details.get(int(r["id"]), {}).get("tier") or "?") for r in rows}
        if args.species:
            roster = normalize_species_list(args.species, rows)
        else:
            ids = read_account_roster(args.uid, REPO)
            roster = [ml.normalize(by_id[int(item)]["slug"]) for item in ids if int(item) in by_id]
        excluded = set(normalize_species_list(args.exclude, rows))
        bases = dict(CATEGORY_BASE)
        if args.fleeing:
            bases = {"sleep": 60, "falseswipe": 25, "trapping": 45}
        candidates = []
        for slug in roster:
            family_set = family_nodes(slug, dex)
            if excluded & family_set:
                continue
            result = score_parts(slug, learned, dex, moves, bases=bases, fleeing=args.fleeing, name_of=name_of)
            if not result["parts"]:
                continue
            candidates.append({
                **result,
                "name": name_of.get(slug, slug),
                "tier": tier_of.get(slug, "?"),
            })
    except (OSError, ValueError, KeyError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    candidates.sort(key=lambda item: (-item["score"], item["name"]))
    if args.explain:
        try:
            explain_slug = normalize_species_list(args.explain, rows)[0]
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        explained = next((item for item in candidates if item["slug"] == explain_slug), None)
        if explained and not args.json:
            _print_explanation(explained)
    if args.json:
        payload = {
            "source": "account" if args.uid else "species",
            "fleeing": args.fleeing,
            "candidates": candidates[: args.top],
            "candidate_count": len(candidates),
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    if args.fleeing:
        print("fleeing target: one action before it leaves; speed is irrelevant.\n")
    print(f"{'score':>6}  {'pokemon':14} {'tier':7} best tool")
    for candidate in candidates[: args.top]:
        parts = candidate["parts"]
        first = parts[0]
        constraint_note = (" (" + ", ".join(candidate["selected_branch"]["constraints"]) + ")"
                           if candidate["selected_branch"]["constraints"] else "")
        print(f"{candidate['score']:6.1f}  {candidate['name']:14} {candidate['tier']:7}{constraint_note} [{LABEL[first['category']]}] {first['note']}")
        for part in parts[1:4]:
            print(f"{'':6}  {'':14} {'':7} +{part['value']:5.1f} [{LABEL[part['category']]}] {part['note']}")
    if len(candidates) > args.top:
        print(f"\n  ... {len(candidates) - args.top} more from {len(roster)} candidates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
