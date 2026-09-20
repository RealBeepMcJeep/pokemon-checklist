"""Move-acquisition labels shared by the move report.

This module contains presentation metadata only. It deliberately does not import the catcher
scoring model: the report needs the game's source location and cost, not its scoring heuristics.
Unknown entries stay explicit instead of receiving an invented location or price.
"""

from __future__ import annotations

from typing import Mapping

MOVE_REMINDER_LOCATION = "Mount Lanakila Pokémon Center (endgame)"

# Gen 7 TM numbers and locations used by the published USUM learnsets.  The location is kept
# next to the number so a new TM cannot silently acquire a stale label in a second table.
TM_INFO: Mapping[str, tuple[int, str]] = {
    "workup": (1, "Route 1 - Trainer School"),
    "dragonclaw": (2, "Vast Poni Canyon"),
    "psyshock": (3, "Lake of the Moone/Lake of the Sunne"),
    "calmmind": (4, "Seafolk Village PokéMart"),
    "roar": (5, "Kala'e Bay"),
    "toxic": (6, "Aether Paradise"),
    "hail": (7, "Royal Avenue PokéMart"),
    "bulkup": (8, "Royal Avenue"),
    "venoshock": (9, "Konikoni City PokéMart"),
    "hiddenpower": (10, "Paniola Ranch"),
    "sunnyday": (11, "Royal Avenue PokéMart"),
    "taunt": (12, "Route 13"),
    "icebeam": (13, "Mount Lanakila"),
    "blizzard": (14, "Seafolk Village PokéMart"),
    "hyperbeam": (15, "Seafolk Village PokéMart"),
    "lightscreen": (16, "Heahea City PokéMart"),
    "protect": (17, "Heahea City PokéMart"),
    "raindance": (18, "Royal Avenue PokéMart"),
    "roost": (19, "Route 3"),
    "safeguard": (20, "Heahea City PokéMart"),
    "frustration": (21, "Malie City"),
    "solarbeam": (22, "Seafolk Village PokéMart"),
    "smackdown": (23, "Ten Carat Hill"),
    "thunderbolt": (24, "Sandy Cave"),
    "thunder": (25, "Seafolk Village PokéMart"),
    "earthquake": (26, "Resolution Cave"),
    "return": (27, "Malie City"),
    "leechlife": (28, "Akala Outskirts"),
    "psychic": (29, "Aether Paradise"),
    "shadowball": (30, "Route 14"),
    "brickbreak": (31, "Verdant Cavern"),
    "doubleteam": (32, "Route 7"),
    "reflect": (33, "Heahea City PokéMart"),
    "sludgewave": (34, "Seafolk Village PokéMart"),
    "flamethrower": (35, "Vast Poni Canyon"),
    "sludgebomb": (36, "Shady House"),
    "sandstorm": (37, "Royal Avenue PokéMart"),
    "fireblast": (38, "Seafolk Village PokéMart"),
    "rocktomb": (39, "Wela Volcano Park"),
    "aerialace": (40, "Konikoni City"),
    "torment": (41, "Route 5"),
    "facade": (42, "Malie City PokéMart"),
    "flamecharge": (43, "Route 8"),
    "rest": (44, "Royal Avenue Thrifty Megamart"),
    "attract": (45, "Hano Grand Resort"),
    "thief": (46, "Verdant Cavern"),
    "lowsweep": (47, "Konikoni City PokéMart"),
    "round": (48, "Hau'oli City"),
    "echoedvoice": (49, "Hau'oli City"),
    "overheat": (50, "Poni Meadow"),
    "steelwing": (51, "Konikoni City"),
    "focusblast": (52, "Seafolk Village PokéMart"),
    "energyball": (53, "Route 8"),
    "falseswipe": (54, "Iki Town"),
    "scald": (55, "Ancient Poni Path"),
    "fling": (56, "Hau'oli Cemetery"),
    "chargebeam": (57, "Brooklet Hill"),
    "skydrop": (58, "Route 8"),
    "brutalswing": (59, "Route 5"),
    "quash": (60, "Poni Plains"),
    "willowisp": (61, "Konikoni City"),
    "acrobatics": (62, "Melemele Meadow"),
    "embargo": (63, "Malie City"),
    "explosion": (64, "Battle Royal Dome"),
    "shadowclaw": (65, "Royal Avenue"),
    "payback": (66, "Royal Avenue"),
    "smartstrike": (67, "Lush Jungle"),
    "gigaimpact": (68, "Seafolk Village PokéMart"),
    "rockpolish": (69, "Ten Carat Hill"),
    "stoneedge": (71, "Seafolk Village PokéMart"),
    "voltswitch": (72, "Route 10"),
    "thunderwave": (73, "Route 7"),
    "gyroball": (74, "Lush Jungle"),
    "swordsdance": (75, "Lush Jungle"),
    "fly": (76, "Malie City"),
    "psychup": (77, "Royal Avenue"),
    "bulldoze": (78, "Route 17"),
    "frostbreath": (79, "Mount Lanakila"),
    "rockslide": (80, "Route 17"),
    "xscissor": (81, "Route 3"),
    "dragontail": (82, "Route 12"),
    "infestation": (83, "Route 3"),
    "poisonjab": (84, "Route 17"),
    "dreameater": (85, "Hau'oli Cemetery"),
    "grassknot": (86, "Lush Jungle"),
    "swagger": (87, "Route 2"),
    "sleeptalk": (88, "Route 7"),
    "uturn": (89, "Route 5"),
    "substitute": (90, "Heahea City"),
    "flashcannon": (91, "Seafolk Village PokéMart"),
    "trickroom": (92, "Hau'oli City"),
    "wildcharge": (93, "Poni Plains"),
    "snarl": (95, "Route 2"),
    "naturepower": (96, "Route 1"),
    "darkpulse": (97, "Poni Meadow"),
    "dazzlinggleam": (99, "Lush Jungle"),
    "confide": (100, "Hau'oli City"),
}

TUTOR_BP: Mapping[str, int] = {
    "bind": 4, "snore": 4, "waterpulse": 4,
    "bounce": 8, "defog": 8, "electroweb": 8, "firepunch": 8, "healbell": 8,
    "ironhead": 8, "knockoff": 12, "lowkick": 8, "magiccoat": 8,
    "magicroom": 8, "painsplit": 8, "roleplay": 8, "tailwind": 8,
    "thunderpunch": 8, "trick": 8, "uproar": 8, "wonderroom": 8,
    "zenheadbutt": 8, "drillrun": 8, "icepunch": 8, "drainpunch": 8,
    "gastroacid": 8, "skillswap": 8, "seedbomb": 12, "icywind": 12,
    "laserfocus": 12, "foulplay": 12, "superfang": 12, "earthpower": 12,
    "dualchop": 12, "heatwave": 12, "hypervoice": 12, "stompingtantrum": 12,
    "dragonpulse": 12, "aquatail": 12, "endeavor": 16, "focuspunch": 16,
    "liquidation": 16, "outrage": 16, "skyattack": 16, "throatchop": 16,
    "gunkshot": 16, "superpower": 16,
}

TUTOR_LOCATION: Mapping[str, str] = {
    **{m: "Big Wave Beach (Melemele)" for m in (
        "snore healbell electroweb defog lowkick uproar bind helpinghand shockwave block "
        "lastresort worryseed covet bugbite snatch recycle" ).split()},
    **{m: "Heahea Beach (Akala)" for m in (
        "irontail spite afteryou gigadrain synthesis allyswitch signalbeam gravity stealthrock "
        "irondefense telekinesis magnetrise bounce roleplay firepunch waterpulse" ).split()},
    **{m: "Ula'ula Beach" for m in (
        "ironhead aquatail painsplit tailwind thunderpunch endeavor focuspunch icywind "
        "zenheadbutt seedbomb laserfocus trick drillrun magiccoat icepunch wonderroom magicroom" ).split()},
    **{m: "Battle Tree (Poni)" for m in (
        "liquidation gastroacid foulplay superfang outrage skyattack throatchop stompingtantrum "
        "skillswap earthpower gunkshot dualchop drainpunch heatwave hypervoice superpower "
        "knockoff dragonpulse" ).split()},
}

PROFILE_LABELS = {
    "gen7": "Gen 7 / USUM",
    "prismatic-standard": "Prismatic Standard",
}
PROFILE_NOTES = {
    "gen7": "",
    "prismatic-standard": (
        "Prismatic Standard egg moves learned through leveling are marked as egg moves; "
        "the source provides no level (level not specified), so none is inferred."
    ),
}


def tm_label(move: str) -> str:
    info = TM_INFO.get(move)
    return f"TM{info[0]} — {info[1]}" if info else "TM (location unknown)"


def tutor_label(move: str) -> str:
    cost = TUTOR_BP.get(move)
    place = TUTOR_LOCATION.get(move)
    bits = ["TUTOR"]
    if place:
        bits.append(place)
    if cost is not None:
        bits.append(f"{cost} BP")
    return " — ".join(bits[:2]) + (f" · {bits[2]}" if len(bits) > 2 else "")
