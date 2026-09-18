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
LABEL = {"sleep": "sleep", "falseswipe": "False Swipe", "superfang": "Super Fang",
         "freeze": "freeze chance", "paralysis": "paralysis", "antighost": "anti-Ghost",
         "immunity": "immunity strip", "trapping": "trapping"}


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
            options.append((f"tutor {cost} BP", 1 - cost / 40, 60))
        elif gate == "TM":
            options.append(("TM", ACQ["TM"], 40))
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
    args = parser.parse_args()

    cache = Path(args.cache)
    learned = dict(ml.top_blocks((cache / "learnsets.ts").read_text(errors="replace")))
    dex = dict(ml.top_blocks((cache / "pokedex.ts").read_text(errors="replace")))
    moves = dict(ml.top_blocks((cache / "moves.ts").read_text(errors="replace")))
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
                # One contribution per benefit: a second sleep move adds nothing.
                if value > best.get(category, (0.0, ""))[0]:
                    best[category] = (value, note)
        if not best:
            continue
        sleep_value = best.get("sleep", (0.0, ""))[0]
        swipe_value = best.get("falseswipe", (0.0, ""))[0]
        extras = sorted((v for c, (v, _) in best.items()
                         if c not in ("sleep", "falseswipe")), reverse=True)
        total = sleep_value + swipe_value + sum(v * 0.6 ** rank for rank, v in enumerate(extras))
        parts = sorted(best.items(), key=lambda kv: -kv[1][0])
        scored.append((total, name_of.get(slug, slug), tier_of.get(slug, "?"),
                       [(LABEL[c], value, note) for c, (value, note) in parts]))

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
