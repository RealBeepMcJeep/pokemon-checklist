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
  immunity strip     3  Worry Seed / Gastro Acid: beats Insomnia and Overcoat
  trapping           2  Mean Look / Spider Web / Block: nothing to trap in USUM
  burn / poison      0  they raise the catch rate but damage the target - not a tool

  every contribution is multiplied by:
    chance      the move's real land rate: accuracy x the effect's own chance where the
                status rides on a secondary effect. Ice Beam is 100% x 10%, not 100%, and
                Body Slam 100% x 30% - this is what keeps a 10% freeze roll out of the plan
    ability     Compound Eyes / No Guard raise the accuracy of the move (x1.3, capped at
                100), discounted when the ability is hidden
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

CATEGORY_BASE = {
    "sleep": 60, "falseswipe": 25, "superfang": 8, "freeze": 10,
    "paralysis": 7, "antighost": 6, "immunity": 3, "trapping": 2,
}
STATUS_CATEGORY = {"slp": "sleep", "par": "paralysis", "frz": "freeze",
                   "brn": None, "psn": None, "tox": None}
FIXED_CATEGORY = {
    "falseswipe": "falseswipe", "superfang": "superfang",
    "odorsleuth": "antighost", "foresight": "antighost", "soak": "antighost",
    "worryseed": "immunity", "gastroacid": "immunity",
    "meanlook": "trapping", "spiderweb": "trapping", "block": "trapping",
}
# The Move Reminder is in Mount Lanakila's Pokemon Center - the area before the League -
# so a level-1 move is an ENDGAME move for a playthrough, not a free one. It is scored
# like an event move for that reason. TMs and tutors still lack a location model.
ACQ = {"level": 1.0, "reminder": 0.2, "TM": 0.8, "egg": 0.5, "event": 0.2}
# Where each tutor move is taught, from Serebii's USUM Move Tutors page - parsed, not typed.
# This is the axis that was missing: a Battle Tree move is late-game, so it must be dampened
# like one, while a Big Wave Beach move is available at the end of the first island.
TUTOR_LOCATION = {
    **{m: 0.80 for m in ['snore', 'healbell', 'electroweb', 'defog', 'lowkick', 'uproar', 'bind', 'helpinghand', 'shockwave', 'block', 'lastresort', 'worryseed', 'covet', 'bugbite', 'snatch', 'recycle']},   # Big Wave Beach, Melemele
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


def load_islands(repo: Path) -> dict[str, int]:
    data = json.loads((repo / "data" / "encounters.json").read_text())
    out: dict[str, int] = {}
    for island in data.get("islands", []):
        order = int(island.get("order") or 0)
        for location in island.get("locations", []):
            if location.get("name"):
                out[str(location["name"]).lower()] = order
    # Places with no wild Pokemon are absent from the encounter data. Of the 18 TM locations
    # this leaves unplaced, only False Swipe's matters - every other one teaches a move this
    # scoring does not consider. Iki Town is Melemele, the starting town.
    out.setdefault("iki town", 1)
    return out


def field(body: str, name: str) -> str | None:
    m = re.search(rf"\b{name}: [\'\"]([^\'\"]*)[\'\"]", body)
    return m.group(1) if m else None


def ability_slots(body: str) -> dict[str, str]:
    m = re.search(r"abilities: \{(.*?)\}", body, re.S)
    if not m:
        return {}
    return {slot: name.strip() for slot, name in
            re.findall(r"[\'\"]?([01H])[\'\"]?: [\'\"]?([^\'\",]+)[\'\"]?", m.group(1))}


def accuracy(body: str) -> float:
    """Accuracy is a NUMBER in this data (60, 75, 90); only `true` means never miss."""
    if re.search(r"\baccuracy: true", body):
        return 100.0
    found = re.search(r"\baccuracy: (\d+)", body)
    return float(found.group(1)) if found else 100.0


def benefit(move: str, body: str) -> tuple[str, float] | None:
    """The category a move contributes to, and the chance that contribution actually lands."""
    if move == "yawn":
        return ("sleep", accuracy(body) / 100 * 0.5)  # lands, but a turn late
    if move in FIXED_CATEGORY:
        return (FIXED_CATEGORY[move], accuracy(body) / 100)

    chance = accuracy(body) / 100
    primary = re.search(r"status: [\'\"]([a-z]+)[\'\"]", body)
    secondary_at = re.search(r"secondaries?:", body)
    if primary and (not secondary_at or primary.start() < secondary_at.start()):
        category = STATUS_CATEGORY.get(primary.group(1))
        return (category, chance) if category else None

    # A status riding on a secondary effect only lands on that effect's own roll, so a 10%
    # freeze is worth a tenth of a freeze move - not the value of one.
    best: tuple[str, float] | None = None
    for roll, status in re.findall(r"chance: (\d+)[^}]*?status: [\'\"]([a-z]+)[\'\"]", body, re.S):
        category = STATUS_CATEGORY.get(status)
        if not category:
            continue
        candidate = (category, chance * int(roll) / 100)
        if best is None or candidate[1] > best[1]:
            best = candidate
    return best


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
            island = ISLAND_OF.get((where or "").lower())
            # Found on island 1 is nearly free; found at Mount Lanakila is endgame.
            factor = ACQ["TM"] * ISLAND_FACTOR.get(island or 0, 1.0)
            level = ISLAND_LEVEL.get(island or 0, 40)
            options.append((f"TM at {where}" if where else "TM", factor, level))
        elif gate == "egg":
            options.append(("egg", ACQ["egg"], 60))
        else:
            options.append((gate, ACQ["event"], 60))
    return min(options, key=lambda t: (-t[1], t[2]))


def main() -> int:
    parser = argparse.ArgumentParser(description="Rank Pokemon as catching leads.")
    parser.add_argument("--uid", help="read this account's caught and starred species")
    parser.add_argument("--species", help="comma-separated slugs instead of an account")
    parser.add_argument("--cache", default="/opt/data/poke-data")
    parser.add_argument("--top", type=int, default=15)
    parser.add_argument("--exclude", default="", help="slugs to leave out (matches whole families)")
    parser.add_argument("--explain", help="print every arithmetic step for one slug")
    args = parser.parse_args()

    cache = Path(args.cache)
    learned = dict(ml.top_blocks((cache / "learnsets.ts").read_text(errors="replace")))
    dex = dict(ml.top_blocks((cache / "pokedex.ts").read_text(errors="replace")))
    moves = dict(ml.top_blocks((cache / "moves.ts").read_text(errors="replace")))
    global ISLAND_OF
    ISLAND_OF = load_islands(REPO)
    move_name = lambda key: field(moves.get(key, ""), "name") or key  # noqa: E731

    rows = json.loads((REPO / "data" / "pokemon.json").read_text())
    rows = rows if isinstance(rows, list) else list(rows.values())
    name_of = {ml.normalize(r["slug"]): r["name"] for r in rows}
    by_id = {int(r["id"]): r for r in rows}
    details = {int(d["id"]): d for d in
               json.loads((REPO / "data" / "pokedex-details.json").read_text())["species"]}
    tier_of = {ml.normalize(r["slug"]): (details.get(int(r["id"]), {}).get("tier") or "?")
               for r in rows}

    if args.species:
        roster = [s.strip().lower() for s in args.species.split(",") if s.strip()]
    else:
        out = subprocess.run(["node", str(TOOLS / "firebase-admin-rest.mjs"),
                              "--read", f"/users/{args.uid}/state/records"],
                             capture_output=True, text=True, cwd=REPO)
        records = json.loads(out.stdout or "null") or {}
        caught = {int(k.split(":")[1]) for k, v in records.items()
                  if k.startswith("species:") and v.get("s") == "caught"}
        stars = {int(k.split(":")[1]) for k, v in records.items()
                 if k.startswith("star:") and v.get("s") == "on"}
        roster = sorted({ml.normalize(by_id[d]["slug"]) for d in (caught | stars) if d in by_id})

    excluded = {s.strip().lower() for s in args.exclude.split(",") if s.strip()}
    scored = []
    for slug in roster:
        family = ml.lineage(slug, dex)
        if not family or excluded & set(family):
            continue
        best: dict[str, tuple[float, str]] = {}
        trace: list[tuple] = []
        for form in family:
            body_text = learned.get(form)
            if not body_text:
                continue
            boost, boost_note = 1.0, ""
            for slot, ability in ability_slots(dex.get(form, "")).items():
                if ability == "Compound Eyes":
                    boost = 1.3 * (0.7 if slot == "H" else 1.0)
                    boost_note = ability + (" (hidden ability)" if slot == "H" else "")
                elif ability == "No Guard":
                    boost, boost_note = 1.3, ability
            for move, gates in ml.gen7_moves(body_text).items():
                found = benefit(move, moves.get(move, ""))
                if not found or found[0] not in CATEGORY_BASE:
                    continue
                category, land = found
                label, factor, level = easiest(gates, move)
                hit = min(1.0, land * boost)
                speed = 1 / (1 + max(0, level - 10) / 40)
                value = CATEGORY_BASE[category] * hit * factor * speed
                if value <= 0:
                    continue
                note = (f"{move_name(move)} via {name_of.get(form, form)} {label} "
                        f"[{hit * 100:.0f}%]")
                if boost_note and hit > land:
                    note += f" *{boost_note}*"
                if args.explain == slug:
                    trace.append((category, move_name(move), name_of.get(form, form), label,
                                  land, boost, factor, level, speed, value))
                # One contribution per benefit: a second sleep move adds nothing.
                if value > best.get(category, (0.0, ""))[0]:
                    best[category] = (value, note)
        if not best:
            continue
        sleep_value = best.get("sleep", (0.0, ""))[0]
        swipe_value = best.get("falseswipe", (0.0, ""))[0]
        extras = sorted((v for c, (v, _) in best.items()
                         if c not in ("sleep", "falseswipe")), reverse=True)
        # Sleep and False Swipe count in full; the best of the REST counts 60%, the next
        # 36%. The first version used 0.6**rank over the extras, which made the first extra
        # count at full weight, so the ranking disagreed with this document.
        total = sleep_value + swipe_value + sum(v * 0.6 ** (rank + 1)
                                                for rank, v in enumerate(extras))
        parts = sorted(best.items(), key=lambda kv: -kv[1][0])
        scored.append((total, name_of.get(slug, slug), tier_of.get(slug, "?"),
                       [(LABEL[c], value, note) for c, (value, note) in parts]))

        if args.explain == slug:
            print(f"\n=== how {name_of.get(slug, slug)} is scored ===")
            print(f"{'category':12} {'move':16} {'form':12} how                "
                  f"{'land':>6} {'ability':>7} {'acq':>5} {'speed':>6} {'= value':>8}")
            for category, move, form, label, land, boost, factor, level, speed, value in trace:
                # * marks the option that actually counts; the rest are dropped because
                # they give the same benefit (you would not run two sleep moves).
                mark = "*" if abs(best[category][0] - value) < 1e-9 else " "
                print(f"{mark}{category:12} {move:16} {form:12} {label:18} "
                      f"{land * 100:5.0f}% {boost:7.2f} {factor:5.2f} {speed:6.2f} {value:8.2f}")
            print("\n  * = this category's best option; the others are dropped (you would "
                  "not run two sleep moves)")
            chosen = sorted(best.items(), key=lambda kv: -kv[1][0])
            total_check = 0.0
            for rank, (category, (value, _)) in enumerate(chosen):
                weight = 1.0 if category in ("sleep", "falseswipe") else 0.6 ** (rank - 0)
                if category in ("sleep", "falseswipe"):
                    print(f"  {category:12} {value:7.2f}  x1.00 (counts in full)   = {value:7.2f}")
                    total_check += value
                else:
                    print(f"  {category:12} {value:7.2f}  x{weight:.2f} (rank decay)    = {value * weight:7.2f}")
                    total_check += value * weight
            print(f"  {'TOTAL':12} {total_check:7.2f}   (this is the score in the table)\n")

    scored.sort(key=lambda t: (-t[0], t[1]))
    print(f"{'score':>6}  {'pokemon':14} {'tier':7} best tool")
    for total, name, tier, parts in scored[: args.top]:
        print(f"{total:6.1f}  {name:14} {tier:7} [{parts[0][0]}] {parts[0][2]}")
        for label, value, note in parts[1:4]:
            print(f"{'':6}  {'':14} {'':7} +{value:5.1f} [{label}] {note}")
    if len(scored) > args.top:
        print(f"\n  ... {len(scored) - args.top} more from {len(roster)} candidates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
