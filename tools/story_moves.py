"""Acquisition-checked move targets for the local Prismatic Moon Standard team cards.

The four move *preferences* per species are editorial; name, type, and acquisition
come from verified hack/Gen VII data and fail closed if a preferred move is not
obtainable from the actually owned stage. No egg/event/transfer-only gates.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

try:
    from . import moveline as ml
    from .acquisition_data import TM_INFO, TUTOR_BP, TUTOR_LOCATION
except ImportError:
    import moveline as ml  # type: ignore[no-redef]
    from acquisition_data import TM_INFO, TUTOR_BP, TUTOR_LOCATION  # type: ignore[no-redef]

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "references/prismatic-moon"
TYPE_NAMES = set(ml.TYPE_COLOR)
# These vanilla TM slots are replaced by new moves/compatibilities in the hack.
REPLACED_TM = {"quash", "frostbreath", "confide", "brutalswing", "smartstrike"}
# Vendor Changes.pdf, Specialist Marts, Tapu Village. This overrides USUM's locations.
TAPU_TMS = {"earthquake": 26, "swordsdance": 75, "overheat": 50,
             "surf": 94, "waterfall": 98, "darkpulse": 97, "trickroom": 92}

# Curated four-slot story targets, not claims about learnsets. Every goal is resolved
# against Prismatic Standard level-up (which REPLACES vanilla 7L), Gen VII TM/tutor
# gates, and the owned-to-final evolution path before it is put on a card.
GOALS = {
    "Butterfree": ("Sleep Powder", "Bug Buzz", "Roost", "Air Slash"),
    "Gengar": ("Shadow Ball", "Sludge Bomb", "Dazzling Gleam", "Will-O-Wisp"),
    "Slowbro": ("Water Pulse", "Psychic", "Slack Off", "Thunder Wave"),
    "Arcanine": ("Flamethrower", "Extreme Speed", "Crunch", "Close Combat"),
    "Raichu": ("Thunderbolt", "Grass Knot", "Volt Switch", "Thunder Wave"),
    "Pidgeot": ("Fly", "Roost", "U-turn", "Wing Attack"),
    "Infernape": ("Flame Wheel", "Close Combat", "U-turn", "Grass Knot"),
    "Feraligatr": ("Aqua Tail", "Ice Fang", "Crunch", "Brick Break"),
    "Zoroark": ("Foul Play", "Extrasensory", "U-turn", "Flamethrower"),
    "Galvantula": ("Electroweb", "Signal Beam", "Energy Ball", "Thunder Wave"),
    "Gardevoir": ("Psychic", "Dazzling Gleam", "Calm Mind", "Magical Leaf"),
    "Scrafty": ("Brick Break", "Crunch", "Bulk Up", "Rock Tomb"),
    "Linoone": ("Belly Drum", "Extreme Speed", "Seed Bomb", "Stomping Tantrum"),
    "Alakazam": ("Psychic", "Shadow Ball", "Dazzling Gleam", "Recover"),
    "Poliwrath": ("Brick Break", "Waterfall", "Ice Punch", "Bulk Up"),
    "Fearow": ("Drill Peck", "Steel Wing", "U-turn", "Roost"),
    "Pelipper": ("Scald", "Air Slash", "U-turn", "Roost"),
    "Diggersby": ("Return", "Earthquake", "Rock Slide", "U-turn"),
    "Skuntank": ("Crunch", "Poison Jab", "Flamethrower", "Sucker Punch"),
    "Crabominable": ("Brick Break", "Ice Hammer", "Rock Slide", "Bulk Up"),
    "Luxray": ("Thunder Fang", "Crunch", "Ice Fang", "Thunder Wave"),
    "Magnezone": ("Discharge", "Flash Cannon", "Volt Switch", "Thunder Wave"),
    "Decidueye": ("Leaf Blade", "Shadow Claw", "False Swipe", "Roost"),
    "Vivillon": ("Bug Buzz", "Hurricane", "Quiver Dance", "Roost"),
    "Toucannon": ("Beak Blast", "Brick Break", "U-turn", "Roost"),
    "Tentacruel": ("Water Pulse", "Sludge Wave", "Giga Drain", "Ice Beam"),
    "Metagross": ("Meteor Mash", "Zen Headbutt", "Bullet Punch", "Earthquake"),
    "Blaziken": ("Blaze Kick", "Brick Break", "Bulk Up", "Rock Slide"),
    "Exploud": ("Boomburst", "Flamethrower", "Surf", "Ice Beam"),
    "Gastrodon": ("Muddy Water", "Earth Power", "Recover", "Ice Beam"),
    "Hypno": ("Psychic", "Shadow Ball", "Thunder Wave", "Dazzling Gleam"),
    "Meganium": ("Energy Ball", "Reflect", "Light Screen", "Synthesis"),
    "Shiftry": ("Leaf Blade", "Feint Attack", "Brick Break", "Swords Dance"),
    "Vikavolt": ("Thunderbolt", "Bug Buzz", "Energy Ball", "Roost"),
}


def standard_levels() -> dict[int, dict[str, list[int]]]:
    manifest = json.loads((CORPUS / "MANIFEST.json").read_text(encoding="utf-8"))
    for entry in manifest:
        payload = (CORPUS / entry["name"]).read_bytes()
        if len(payload) != entry["bytes"] or hashlib.sha256(payload).hexdigest() != entry["sha256"]:
            raise ValueError(f"Prismatic Moon source changed: {entry['name']}")
    text = (CORPUS / "Level Up Moves, Standard.txt").read_text(encoding="utf-16")
    blocks: dict[int, dict[str, list[int]]] = {}
    for hit in re.finditer(r"(?ms)^======\n(\d+) ([^\n]+)\n======\n(.*?)(?=^======\n\d+ |\Z)", text):
        dex = int(hit.group(1))
        if dex in blocks:
            raise ValueError(f"duplicate Prismatic Standard dex #{dex}")
        moves: dict[str, list[int]] = {}
        for level, name in re.findall(r"(?m)^(\d+)\s+-\s+([^\n]+)$", hit.group(3)):
            moves.setdefault(ml.normalize(name), []).append(int(level))
        blocks[dex] = moves
    if len(blocks) < 807 or not blocks.get(12, {}).get("sleeppowder"):
        raise ValueError("Prismatic Standard level-up table is incomplete")
    return blocks


class MoveSources:
    def __init__(self, cache: Path):
        self.data = ml.load_move_data(cache)
        self.levels = standard_levels()

    def level_threshold(self, stage: str) -> int:
        """Earliest level the stage can normally exist after level evolutions."""
        threshold = 1
        for form in ml.ancestral_path(ml.normalize(stage), self.data.parent_of)[1:]:
            method = self.data.evo_method.get(form, "")
            found = re.match(r"Level (\d+)", method)
            if found:
                threshold = max(threshold, int(found.group(1)))
        return threshold

    def next_level_evolution(self, stage: str, final: str) -> int | None:
        path = ml.ancestral_path(ml.normalize(final), self.data.parent_of)
        pos = path.index(ml.normalize(stage))
        if pos == len(path) - 1:
            return None
        method = self.data.evo_method.get(path[pos + 1], "")
        found = re.match(r"Level (\d+)", method)
        return int(found.group(1)) if found else None

    def candidates(self, final: str, owned: str) -> dict[str, dict]:
        data = self.data
        path = ml.ancestral_path(ml.normalize(final), data.parent_of)
        current = ml.normalize(owned)
        if current not in path or ml.normalize(final) not in path:
            raise ValueError(f"{owned} is not on the {final} evolution path")
        path = path[path.index(current):]
        out: dict[str, dict] = {}
        for stage in path:
            dex = data.id_of[stage]
            if dex not in self.levels:
                raise ValueError(f"no Standard level-up table for {stage}")
            # 7L is intentionally discarded: this hack's Standard table supersedes it.
            gen7 = ml.gen7_moves(data.learned.get(stage, ""))
            for key, gates in gen7.items():
                if key not in data.move_meta:
                    continue
                entry = out.setdefault(key, {"name": data.move_meta[key][0],
                                             "type": data.move_meta[key][1], "sources": []})
                for via in ("TM", "tutor"):
                    if via in gates and not (via == "TM" and key in REPLACED_TM):
                        if via == "TM" and key not in TM_INFO and key not in TAPU_TMS:
                            continue  # Do not invent the location of an unknown TM.
                        if via == "tutor" and key not in TUTOR_LOCATION:
                            continue
                        entry["sources"].append({"via": via, "form": data.nice[stage]})
            for key, levels in self.levels[dex].items():
                meta_key = data.meta_by_name.get(key, key)
                if meta_key not in data.move_meta:
                    continue
                display, typ, _ = data.move_meta[meta_key]
                entry = out.setdefault(meta_key, {"name": display, "type": typ, "sources": []})
                for level in levels:
                    # A level listed below this form's evolution threshold is
                    # not learnable by *leveling that form* in a normal run.
                    # It may still be carried over from an earlier stage.
                    if level > 1 and level < self.level_threshold(stage):
                        continue
                    via = "evolution" if level == 0 and stage != current else (
                        "reminder" if level in (0, 1) else "level")
                    entry["sources"].append({"via": via, "form": data.nice[stage], "level": level})
        return {key: value for key, value in out.items() if value["sources"]}

    def gate_label(self, key: str, source: dict, final: str) -> str:
        via, form = source["via"], source["form"]
        if via == "TM":
            if key in TAPU_TMS:
                return f"TM{TAPU_TMS[key]} · Tapu Village (later)"
            number, place = TM_INFO[key]
            late = any(x in place for x in ("Poni", "Lanakila", "Seafolk", "Aether", "Shady House"))
            return f"TM{number} · {place}{' · LATER' if late else ''}"
        if via == "tutor":
            bp = TUTOR_BP.get(key)
            cost = f" · {bp} BP" if bp is not None else ""
            place = TUTOR_LOCATION[key]
            return f"Tutor · {place}{cost}{' · ENDGAME' if 'Battle Tree' in place else ''}"
        if via == "evolution":
            return f"On evolution → {form}"
        if via == "reminder":
            return "Move Reminder · Mount Lanakila (endgame)"
        if via == "level":
            note = " · BEFORE STONE" if final == "Arcanine" and form == "Growlithe" else (
                " · before evolving" if form != final else "")
            return f"{form} L{source['level']}{note}"
        raise ValueError(f"unsupported acquisition gate: {via}")

    def targets(self, final: str, owned: str) -> list[dict]:
        if final not in GOALS:
            raise ValueError(f"no curated move targets for {final}; do not invent a set")
        pool = self.candidates(final, owned)
        targets: list[dict] = []
        for name in GOALS[final]:
            key = self.data.meta_by_name.get(ml.normalize(name), ml.normalize(name))
            entry = pool.get(key)
            if not entry or entry["type"] not in TYPE_NAMES:
                raise ValueError(f"{final}: {name} not obtainable from {owned} in Standard")
            # Choose an obtainable gate over a late-game reminder. For early forms,
            # prefer the endpoint's level if it is close, avoiding unnecessary delays.
            def priority(source: dict) -> int:
                via = source["via"]
                if via == "evolution":
                    return 0
                if via == "level":
                    distance = len(ml.ancestral_path(ml.normalize(final), self.data.parent_of)) - 1 - (
                        len(ml.ancestral_path(ml.normalize(source["form"]), self.data.parent_of)) - 1)
                    next_evo = self.next_level_evolution(source["form"], final)
                    delay = 70 if next_evo is not None and int(source["level"]) >= next_evo else 0
                    return int(source["level"]) + distance * 4 + delay
                if via == "TM":
                    if key in TAPU_TMS:
                        return 90
                    place = TM_INFO[key][1]
                    if any(a in place for a in ("Route 3", "Route 5", "Verdant Cavern", "Iki Town")):
                        return 25
                    if any(a in place for a in ("Lush Jungle", "Wela Volcano Park", "Royal Avenue", "Konikoni City", "Route 8")):
                        return 40
                    if any(a in place for a in ("Poni", "Lanakila", "Seafolk", "Aether", "Shady House", "Route 14", "Sandy Cave")):
                        return 90
                    return 50
                if via == "tutor":
                    return 55 if "Battle Tree" not in TUTOR_LOCATION[key] else 110
                return 140  # endgame reminder
            source = min(entry["sources"], key=priority)
            targets.append({"name": entry["name"], "type": entry["type"],
                            "gate": self.gate_label(key, source, final), "source": source})
        return targets
