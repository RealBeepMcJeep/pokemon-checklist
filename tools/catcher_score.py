#!/usr/bin/env python3
"""Rank the owner's Pokemon as catching leads, by how easily they can do the catching job.

The job has two halves: put the target to sleep, and get it to 1 HP without fainting it.
A good lead does one of those early, for free, by levelling up.

Scoring (per evolution family; the family is scored on its best form):

  sleep move        base 60 for 100%-accurate sleep (Spore), 40 for a sleep-status move,
                    25 for Yawn (delayed, two turns), 6 for a damaging move that can freeze
                    (a 10% roll - a bonus, never a plan)
  False Swipe       base 25
  Super Fang        base 8   (halves HP: a good opener before chipping)
  paralysis         base 6   (x1.5 catch rate, and the safe fallback when sleep misses)
  anti-Ghost        base 6   (Foresight / Odor Sleuth / Soak: Normal moves hit Ghosts)
  immunity strip    base 3   (Worry Seed / Gastro Acid: beats Insomnia and Overcoat)
  trapping          base 2   (Mean Look / Spider Web: nothing you must trap in USUM)

  and every component is multiplied by:

  accuracy     the move's real accuracy, with an ability boost where the family has one
               (Compound Eyes x1.3; a hidden ability or a second-slot ability costs more
               effort to obtain, so those are discounted)
  acquisition  level-up 1.0 (natural) | move reminder 0.85 (free) | TM 0.8 (free)
               | tutor 1 - BP/40 (costs Battle Points) | egg 0.5 (breeding) | event 0.2
  speed        1 / (1 + max(0, level - 10) / 40): full marks at level 10, decaying after

  Score is additive: every core catcher move a family can get adds its own contribution.
  Contributions decay by rank, so a kit's second-best tool counts 60% of its value, the
  third 36%, and so on - a long list of marginal tools cannot outrank one reliable sleeper.

Usage: python3 tools/catcher_score.py --uid <uid> [--exclude butterfree] [--top 15]
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

SLEEP_MOVES = {"spore", "sleeppowder", "hypnosis", "sing", "lovelykiss", "grasswhistle",
               "darkvoid", "wickedtorque", "relicsong"}
BASE_POINTS = {
    **{m: 40 for m in SLEEP_MOVES},
    "spore": 60,
    "yawn": 25,
    "falseswipe": 25,
    "superfang": 8,
    "thunderwave": 6, "glare": 6, "stunspore": 6, "bodyslam": 6, "nuzzle": 6,
    "odorsleuth": 6, "foresight": 6, "soak": 6,
    "worryseed": 3, "gastroacid": 3,
    "meanlook": 2, "spiderweb": 2, "block": 2,
}
FREEZE_MOVES = {"icebeam", "blizzard", "icepunch", "freezedry", "powdersnow", "icefang",
                "frostbreath", "glaciate", "iceball", "iceshard"}
TUTOR_BP = ml.TUTOR_BP


def field(body: str, name: str) -> str | None:
    m = re.search(rf"\b{name}: [\'\"]([^\'\"]*)[\'\"]", body)
    return m.group(1) if m else None


def ability_slots(body: str) -> dict[str, str]:
    m = re.search(r"abilities: \{(.*?)\}", body, re.S)
    if not m:
        return {}
    return {slot: name.strip() for slot, name in
            re.findall(r"[\'\"]?([01H])[\'\"]?: [\'\"]?([^\'\",]+)[\'\"]?", m.group(1))}


def easiest(gates: dict[str, list[str]], move: str) -> tuple[str, float, int]:
    """The cheapest way this family gets the move: (label, factor, level)."""
    options = []
    for gate, levels in gates.items():
        if gate == "level":
            level = min(int(x) for x in levels)
            options.append((f"L{level}" if level > 1 else "reminder",
                            ACQ["reminder"] if level == 1 else ACQ["level"], level))
        elif gate == "tutor":
            cost = TUTOR_BP.get(move, 8)
            options.append((f"tutor {cost} BP", 1 - cost / 40, 60))
        elif gate == "TM":
            options.append(("TM", ACQ["TM"], 40))
        elif gate == "egg":
            options.append(("egg", ACQ["egg"], 60))
        else:
            options.append((gate, ACQ["event"], 60))
    return min(options, key=lambda t: (-t[1], t[2]))


ACQ = {"level": 1.0, "reminder": 0.85, "TM": 0.8, "egg": 0.5, "event": 0.2}


def main() -> int:
    parser = argparse.ArgumentParser(description="Rank Pokemon as catching leads.")
    parser.add_argument("--uid", help="read this account's caught and starred species")
    parser.add_argument("--species", help="comma-separated slugs instead of an account")
    parser.add_argument("--cache", default="/opt/data/poke-data")
    parser.add_argument("--top", type=int, default=15)
    parser.add_argument("--exclude", default="", help="slugs to leave out")
    args = parser.parse_args()

    cache = Path(args.cache)
    learned = dict(ml.top_blocks((cache / "learnsets.ts").read_text(errors="replace")))
    dex = dict(ml.top_blocks((cache / "pokedex.ts").read_text(errors="replace")))
    moves = dict(ml.top_blocks((cache / "moves.ts").read_text(errors="replace")))

    def move_name(key: str) -> str:
        return field(moves.get(key, ""), "name") or key

    def accuracy(key: str) -> float:
        """Accuracy is a NUMBER in the data (60, 75, 55); only "true" is never-miss.

        Reading it as a quoted string silently made every move 100% accurate, which scored
        Hypnosis and Sing as if they could not miss and put a 60% sleeper at the top.
        """
        body = moves.get(key, "")
        if re.search(r"\baccuracy: true", body):
            return 100.0
        found = re.search(r"\baccuracy: (\d+)", body)
        return float(found.group(1)) if found else 100.0

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
            body = learned.get(form)
            if not body:
                continue
            slots = ability_slots(dex.get(form, ""))
            boost_factor, boost_note = 1.0, ""
            for slot, ability in slots.items():
                if ability == "Compound Eyes":
                    boost_factor = 1.3
                    boost_note = (f"{ability} (hidden - needs the HA)" if slot == "H"
                                  else f"{ability}" + (" (2nd ability slot)" if slot == "1" else ""))
                    if slot == "H":
                        boost_factor = 1.3 * 0.7
                elif ability == "No Guard":
                    boost_factor = 1.3
                    boost_note = f"{ability} (never misses)"
            for move, gates in ml.gen7_moves(body).items():
                base = BASE_POINTS.get(move)
                if base is None and move in FREEZE_MOVES:
                    base = 6
                if base is None:
                    continue
                label, factor, level = easiest(gates, move)
                hit = min(100.0, accuracy(move) * boost_factor)
                speed = 1 / (1 + max(0, level - 10) / 40)
                value = base * (hit / 100) * factor * speed
                if value <= 0:
                    continue
                kind = ("sleep" if move in SLEEP_MOVES | {"yawn"}
                        else "other:" + move)
                note = f"{move_name(move)} via {name_of.get(form, form)} {label}"
                if move in SLEEP_MOVES | {"yawn"} and boost_note and boost_factor > 1:
                    note += f"  [{boost_note}]"
                if value > best.get(kind, (0.0, ""))[0]:
                    best[kind] = (value, note)
        if not best:
            continue
        sleep_value = best.get("sleep", (0.0, ""))[0]
        swipe_value = best.get("other:falseswipe", (0.0, ""))[0]
        extras = sorted((value for kind, (value, _) in best.items()
                         if kind not in ("sleep", "other:falseswipe")), reverse=True)
        # Every core catcher move adds score, and every contribution is already dampened by
        # how long it takes and what it costs. The one extra rule: the second-best tool in a
        # kit is worth less than the first, so a long list of marginal tools (Ice Beam's 10%
        # freeze, a trapping move) cannot outrank one dependable sleeper. Rank decay, not a
        # hard cap, keeps the sum additive and the ranking honest.
        extras_total = sum(value * (0.6 ** rank) for rank, value in enumerate(extras))
        total = sleep_value + swipe_value + extras_total
        parts = sorted(best.values(), reverse=True)
        scored.append((total, name_of.get(slug, slug), tier_of.get(slug, "?"), parts))

    scored.sort(reverse=True)
    print(f"{'score':>6}  {'pokemon':16} {'tier':8} best tool")
    for total, name, tier, parts in scored[: args.top]:
        print(f"{total:6.0f}  {name:16} {tier:8} {parts[0][1]}")
        for value, label in parts[1:6]:
            print(f"{'':6}  {'':16} {'':8} + {value:4.0f}  {label}")
    if len(scored) > args.top:
        print(f"\n  ... {len(scored) - args.top} more from {len(roster)} candidates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
