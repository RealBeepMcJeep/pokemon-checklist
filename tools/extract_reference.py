#!/usr/bin/env python3
"""Build the committed source data from Wild Pokemon Locations.pdf.

The PDF has a tagged text layer, but its tables are laid out visually.  The
small table catalog below is deliberately curated from the PDF's text and
coordinates; this keeps the generated JSON deterministic and reviewable.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import unicodedata
from pathlib import Path
from urllib.request import urlopen

from PIL import Image
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
PDF = ROOT / "references" / "Wild Pokemon Locations.pdf"
DATA = ROOT / "data"
ASSETS = ROOT / "assets" / "locations"
POKEAPI_CSV = "https://raw.githubusercontent.com/PokeAPI/pokeapi/master/data/v2/csv/pokemon_species_names.csv"

# The document explicitly says that red names are Kantonian forms.  Unmarked
# names use the game's Alolan form where one exists.
ALOLAN = {
    "rattata", "raticate", "raichu", "sandshrew", "sandslash", "vulpix",
    "ninetales", "diglett", "dugtrio", "meowth", "persian", "geodude",
    "graveler", "golem", "grimer", "muk", "exeggutor", "marowak",
}

NAME_FIXES = {
    "Ratatta": "Rattata",
    "Mincinno": "Minccino",
    "Cher rim": "Cherrim",
    "Tentac ruel": "Tentacruel",
    "Slow bro": "Slowbro",
    "Hippo wdon": "Hippowdon",
    "Exegg utor": "Exeggutor",
    "Gre ninja": "Greninja",
    "Jangmo -o": "Jangmo-o",
    "Hakamo -o": "Hakamo-o",
    "Hakamo-o": "Hakamo-o",
    "Seadra*": "Seadra",
    "Tentac ruel": "Tentacruel",
}

FORM_NOTES = {
    "Rockruff": {
        "forms": ["normal", "own-tempo"],
        "note": "Rockruff here can have the normal ability or Own Tempo, with equal encounter chances; Own Tempo Rockruff only summons Own Tempo Rockruff and cannot be called by regular Rockruff.",
    },
    "Deerling": {
        "forms": ["spring", "summer", "autumn", "winter"],
        "note": "All Deerling forms are available; Autumn and Winter can only be found by SOS chaining the Spring and Summer forms.",
    },
    "Lycanroc": {
        "forms": ["midday", "midnight", "dusk"],
        "note": "Lycanroc-Midday appears during the day and Lycanroc-Midnight at night; both have a small chance to call Lycanroc-Dusk.",
    },
    "Pumpkaboo": {
        "forms": ["small", "average", "large", "super-size"],
        "note": "All Pumpkaboo sizes can be found here, and all sizes have a chance to call super-size Pumpkaboo in SOS battles.",
    },
    "Floette": {
        "forms": ["red-flower", "orange-flower", "white-flower"],
        "note": "Floette found here has red flowers and can call Floette with orange and white flowers.",
    },
    "Greninja": {
        "ability": "Battle Bond",
        "note": "Greninja encountered here always has Battle Bond as its ability.",
    },
    "Rotom": {
        "forms": ["base", "heat", "frost"],
        "note": "Rotom can call its Fridge (Frost) and Heat forms via SOS.",
    },
}


def slugify(name: str) -> str:
    name = name.lower().replace("♀", "-f").replace("♂", "-m")
    name = name.replace("’", "'")
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    name = re.sub(r"['.]", "", name)
    name = re.sub(r"[^a-z0-9]+", "-", name).strip("-")
    return name


def clean_name(name: str) -> str:
    name = name.strip().replace("’", "'").replace("–", "-").replace("—", "-")
    name = NAME_FIXES.get(name, name)
    name = re.sub(r"\s*-\s*", "-", name)
    name = re.sub(r"\s+", " ", name)
    return name


def parse_pokemon_csv(raw: bytes) -> list[dict]:
    names: dict[int, str] = {}
    for row in csv.DictReader(raw.decode("utf-8-sig").splitlines()):
        if row["local_language_id"] == "9":
            dex = int(row["pokemon_species_id"])
            if 1 <= dex <= 807:
                names[dex] = row["name"]
    if set(names) != set(range(1, 808)):
        raise ValueError("PokeAPI snapshot did not contain exactly IDs 1..807")
    return [{"id": i, "name": names[i], "slug": slugify(names[i])} for i in range(1, 808)]


def load_pokemon(refresh: bool = False) -> list[dict]:
    path = DATA / "pokemon.json"
    if refresh or not path.exists():
        raw = urlopen(POKEAPI_CSV, timeout=30).read()
        pokemon = parse_pokemon_csv(raw)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(pokemon, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return pokemon
    return json.loads(path.read_text(encoding="utf-8"))


def ref(text: str) -> tuple[str, str | None]:
    """Return source display name and an explicit form marker."""
    form = None
    if text.endswith("#kanto"):
        text, form = text[:-6], "kanto"
    elif text.endswith("#alolan"):
        text, form = text[:-7], "alolan"
    return clean_name(text.rstrip("*")), form


def row(species: str, rate: str | None = None, allies: str = "", condition: str | None = None) -> dict:
    """Compact catalog row syntax: 20, 20/0 (day/night), 25+15 (rate/bubbling)."""
    source = species
    source_form = None
    if species.endswith("*"):
        source = species[:-1]
    source, source_form = ref(source)
    data: dict = {"speciesName": source}
    if source == "All":
        data["species"] = None
        data["speciesId"] = None
    else:
        data["species"] = slugify(source)
    if source_form:
        data["form"] = source_form
    elif data["species"] in ALOLAN:
        data["form"] = "alolan"
    if species.endswith("*") and source in FORM_NOTES:
        data.update({k: v for k, v in FORM_NOTES[source].items() if k != "note"})
    if rate is not None:
        values = rate.split("+")
        if len(values) == 2:
            if "/" in values[0]:
                day, night = values[0].split("/", 1)
                rates = {"day": int(day), "night": int(night), "bubbling": int(values[1])}
            else:
                rates = {"single": int(values[0]), "bubbling": int(values[1])}
        elif "/" in values[0]:
            day, night = values[0].split("/", 1)
            rates = {"day": int(day), "night": int(night)}
        else:
            rates = {"single": int(values[0])}
        data["rates"] = rates
    else:
        data["rates"] = None
    data["allies"] = []
    for ally in filter(None, allies.split(",")):
        ally_name, ally_form = ref(ally)
        ally_data = {"species": slugify(ally_name), "name": ally_name}
        if ally_form:
            ally_data["form"] = ally_form
        elif ally_data["species"] in ALOLAN:
            ally_data["form"] = "alolan"
        data["allies"].append(ally_data)
    if condition:
        data["conditions"] = [condition]
    if source in FORM_NOTES and species.endswith("*"):
        data["note"] = FORM_NOTES[source]["note"]
    return data


def group(name: str, page: int, levels: tuple[int, int] | None, rows: list[dict], *, notes: list[str] | None = None, conditions: list[str] | None = None, category: str | None = None) -> dict:
    lower = name.lower()
    if category is None:
        category = "return-later" if any(x in lower for x in ("fishing", "surfing", "sos", "weather", "rain sos")) else "regular"
    return {
        "name": name,
        "sourcePage": page,
        "category": category,
        "levels": {"min": levels[0], "max": levels[1]} if levels else None,
        "encounters": rows,
        "notes": notes or [],
        "conditions": conditions or [],
    }


def rlist(text: str) -> list[dict]:
    """Parse semicolon-separated catalog rows: Species:rate>Ally,Ally."""
    result = []
    for item in text.split(";"):
        item = item.strip()
        if not item:
            continue
        condition = None
        condition_match = re.search(r"\s+\[([^]]+)\]$", item)
        if condition_match:
            condition = condition_match.group(1)
            item = item[:condition_match.start()]
        left, sep, allies = item.partition(">")
        if ":" in left:
            species, rate = left.rsplit(":", 1)
        else:
            species, rate = left, None
        result.append(row(species.strip(), rate.strip() if rate else None, allies.strip(), condition))
    return result


def location(name: str, page: int, groups: list[dict], *, pages: list[int] | None = None, assets: list[str] | None = None, notes: list[str] | None = None) -> dict:
    return {
        "name": name,
        "sourcePage": page,
        "sourcePages": pages or sorted({page, *(g["sourcePage"] for g in groups)}),
        "assets": assets or [],
        "groups": groups,
        "notes": notes or [],
    }


def build_encounters() -> dict:
    g = group
    # The list is in PDF order.  Do not sort these locations or groups.
    islands = [
        {
            "name": "Melemele Island", "sourcePage": 3, "assets": ["melemele-island.jpg"],
            "locations": [
                location("Route 1", 4, [
                    g("Grass 1", 4, (2, 3), rlist("Pikipek:20; Yungoos:20/0; Ledyba:20/0; Rattata:0/20; Spinarak:0/20; Grubbin:15; Shinx:15; Pichu:10")),
                    g("Grass 2", 4, (2, 3), rlist("Zigzagoon:15; Caterpie:15; Weedle:15; Pidgey:15; Scatterbug:15; Wurmple:15/0; Kricketot:0/15; Purrloin:10")),
                    g("Grass 3", 4, (2, 3), rlist("Bunnelby:20; Buneary:20; Patrat:15; Poochyena:15; Ralts:15; Sentret:15/0; Hoothoot:0/15")),
                ], assets=["route-1.jpg", "route-1-map.png"]),
                location("Hau'oli Outskirts", 4, [
                    g("All Grass", 4, (4, 7), rlist("Inkay:15; Wingull:15; Lotad:15; Shellos:15; Slowpoke:15; Seedot:15; Buizel:10")),
                    g("Tauros Charge Required", 4, (14, 17), rlist("Bidoof:15; Starly:15; Bonsly:15; Pidove:15; Bellsprout:15/0; Oddish:0/15; Doduo:15; Munchlax:10"), category="return-later", conditions=["Requires Tauros Charge."]),
                    g("Fishing", 5, (21, 24), rlist("Magikarp:25+15; Wishiwashi:25+15; Luvdisc:25+15; Remoraid:15+15; Clamperl:5+35; Corsola:5/20+5")),
                    g("Surfing", 5, (21, 24), rlist("Tentacool:20; Wingull:20; Mantyke:20; Finneon:15; Shellos:15; Lapras:10")),
                    g("SOS Calls", 5, None, rlist("Rattata>Rattata#kanto; Pichu>Pikachu,Happiny; Shellos>Shellos; Bonsly>Sudowoodo,Happiny; Munchlax>Snorlax,Happiny; Magikarp>Gyarados; Remoraid>Octillery; Clamperl>Gorebyss,Huntail; Corsola>Mareanie; Mantyke>Remoraid")),
                ], pages=[4, 5]),
                location("Hau'oli City", 6, [
                    g("Grass 1", 6, (6, 9), rlist("Furfrou:15; Abra:15; Mime Jr.:15; Scraggy:15; Nidoran ♂:15; Nidoran ♀:15; Klink:10")),
                    g("Grass 2", 6, (6, 9), rlist("Furfrou:15; Abra:15; Mime Jr.:15; Joltik:15; Tyrogue:15; Grimer:15; Magnemite:10")),
                    g("SOS Calls", 6, None, rlist("Mime Jr.>Happiny,Mr. Mime; Scraggy>Scrafty; Nidoran ♂>Nidorino; Nidoran ♀>Nidorina; Tyrogue>Happiny,Hitmonchan,Hitmonlee,Hitmontop; Grimer>Grimer#kanto")),
                ], assets=["hau-oli-city.jpg", "hau-oli-city-map.jpg"]),
                location("Trainer's School", 7, [
                    g("All Grass", 7, (5, 8), rlist("Meowth:15>Meowth#kanto; Zorua:15; Glameow:15; Riolu:15>Happiny; Grimer:15>Grimer#kanto; Magnemite:15; Nincada:10")),
                ], assets=["trainers-school.jpg"]),
                location("Route 2", 8, [
                    g("Grass 1", 8, (8, 11), rlist("Makuhita:15/10; Drowzee:10/15; Ekans:15; Whismur:15; Smeargle:15; Litleo:15; Espurr:15")),
                    g("Grass 2", 8, (8, 11), rlist("Budew:15; Stunky:15; Growlithe:15; Cutiefly:15; Smeargle:15; Spearow:15; Snubbull:10")),
                    g("Grass 3", 8, (8, 11), rlist("Cherubi:15; Munna:15; Audino:15; Skitty:15; Gulpin:15; Cutiefly:15; Snubbull:10")),
                    g("Ambush Encounters", 9, (8, 11), rlist("Chimchar:20; Cyndaquil:20; Turtwig:20; Chikorita:20; Dunsparce:20")),
                    g("Berry Piles", 9, (9, 12), rlist("Crabrawler:100")),
                    g("SOS Calls", 9, None, rlist("Budew>Happiny,Roselia; Chimchar>Pansage; Cyndaquil>Pansage; Turtwig>Panpour; Chikorita>Panpour")),
                ], pages=[8, 9], assets=["route-2.jpg", "route-2-map.jpg"]),
                location("Hau'oli Cemetery", 9, [
                    g("All Grass", 9, (8, 11), rlist("Gastly:15; Drifloon:15; Duskull:15; Shuppet:15; Misdreavus:10; Murkrow:10; Yamask:10; Litwick:10")),
                ], assets=["hau-oli-cemetery.jpg"]),
                location("Sandy Cave", 10, [
                    g("Everywhere", 10, (8, 11), rlist("Psyduck:20; Woobat:20; Spheal:20; Totodile:15>Pansear; Tynamo:15>Eelektrik; Stunfisk:10")),
                ], assets=["sandy-cave.jpg"]),
                location("Verdant Cavern", 11, [
                    g("Cave", 11, (8, 11), rlist("Zubat:20; Noibat:20; Diglett:20; Drilbur:10; Teddiursa:10; Axew:10; Onix:10")),
                    g("Dust Clouds", 11, (8, 11), rlist("Yungoos:100/0; Rattata:0/100")),
                    g("SOS Calls", 11, None, rlist("Diglett>Diglett#kanto; Yungoos>Gumshoos; Ratatta>Rattata#kanto,Raticate")),
                ], assets=["verdant-cavern.jpg"]),
                location("Route 3", 12, [
                    g("Grass 1", 12, (10, 13), rlist("Geodude#kanto:20>Geodude; Spearow:20; Mankey:20; Taillow:15; Hoppip:15; Hawlucha:10")),
                    g("Grass 2", 12, (10, 13), rlist("Cutiefly:20; Aipom:20; Mienfoo:15; Hawlucha:10; Zangoose:10>Seviper; Seviper:10>Zangoose; Hoppip:14; Bagon:1>Salamence")),
                    g("Shadows", 12, (8, 11), rlist("Rufflet:50; Vullaby:50")),
                ], assets=["route-3.jpg", "route-3-map.jpg"]),
                location("Kala'e Bay", 13, [
                    g("Grass", 13, (21, 24), rlist("Dwebble:20; Wingull:20; Slowpoke:20; Piplup:15; Oshawott:15; Bagon:10")),
                    g("Fishing", 13, (21, 24), rlist("Magikarp:25+0; Wishiwashi:25+25; Remoraid:25+15; Horsea:20+15; Shellder:5+35")),
                    g("Surfing", 13, (21, 24), rlist("Tentacool:25; Wingull:25; Finneon:20; Mantyke:20; Lapras:10")),
                    g("SOS Calls", 13, None, rlist("Slowpoke>Slowbro,Slowking; Piplup>Pansear,Prinplup; Oshawott>Pansear,Dewott; Bagon>She lgon; Magikarp>Gyarados; Remoraid>Octillery; Horsea>Seadra".replace("She lgon", "Shelgon")), notes=["The Seadra entry is available in bubbling spots only."]),
                ], assets=["kalae-bay.jpg"]),
                location("Melemele Meadow", 14, [
                    g("Flowers", 14, (12, 15), rlist("Flabébé:20>Flabébé,Flabébé; Combee:15>Cutiefly; Petilil:15; Cottonee:15; Oricorio:15; Bulbasaur:10>Panpour; Metapod:9>Caterpie,Butterfree; Butterfree:1")),
                ], assets=["melemele-meadow.jpg"]),
                location("Seaward Cave", 15, [
                    g("Cave", 15, (12, 15), rlist("Smoochum:20; Delibird:15; Swinub:15; Bergmite:15/5; Cubchoo:15; Squirtle:10; Sneasel:5/10; Snorunt:5/10")),
                    g("Fishing", 15, (22, 25), rlist("Magikarp:60+20; Barboach:40+80")),
                    g("Surfing", 15, (22, 25), rlist("Seel:20; Psyduck:25/5; Spheal:20; Vanillite:20; Delibird:10; Zubat:5/25")),
                    g("SOS Calls", 15, None, rlist("Smoochum>Happiny,Jynx; Squirtle>Pansear; Snorunt>Froslass; Magikarp>Gyarados; Barboach>Whiscash")),
                ], assets=["seaward-cave.jpg"]),
                location("Ten Carat Hill", 16, [
                    g("Cave", 16, (14, 17), rlist("Carbink:15; Chingling:15; Mawile:15; Roggenrola:15; Aron:15; Timburr:15; Deino:10")),
                    g("Grass", 16, (14, 17), rlist("Rockruff*:20; Machop:15; Spinda:15; Jangmo-o:15; Bronzor:15; Meditite:10; Carbink:10"), notes=[FORM_NOTES["Rockruff"]["note"]]),
                    g("Surfing", 16, (54, 57), rlist("Lapras:30; Crobat:20; Golbat:20; Golduck:20; Eelektrik:10")),
                    g("SOS Calls", 16, None, rlist("Carbink>Sableye; Chingling>Happiny,Chimecho; Deino>Hydreigon; Jangmo-o>Hakamo-o; Golbat>Crobat; Eelektrik>Eelektross")),
                ], assets=["ten-carat-hill.jpg"]),
                location("Melemele Sea (Hau'oli City)", 17, [
                    g("Fishing", 17, (21, 24), rlist("Magikarp:25+10>Gyarados; Wishiwashi:25+15; Luvdisc:25+10; Remoraid:15+15>Octillery; Corsola:5+35>Mareanie; Clamperl:5+20>Gorebyss,Huntail")),
                    g("Surfing", 17, (21, 24), rlist("Tentacool:40; Wingull:20; Finneon:20; Mantyke:20>Remoraid")),
                ], assets=["melemele-sea.jpg"]),
            ],
        },
        {
            "name": "Akala Island", "sourcePage": 18, "assets": ["akala-island.jpg"],
            "locations": [
                location("Route 4", 19, [
                    g("All Grass", 19, (15, 18), rlist("Igglybuff:15/5>Happiny,Jigglypuff; Lillipup:15; Mudbray:15; Venipede:15; Sewaddle:15; Grubbin:10; Eevee:10>Espeon,Umbreon; Houndour:5/15")),
                    g("Berry Piles", 19, (15, 18), rlist("Burmy:100")),
                ], assets=["route-4.jpg"]),
                location("Paniola Ranch", 20, [
                    g("All Grass", 20, (17, 20), rlist("Mareep:20; Mudbray:20; Skiddo:20; Blitzle:15; Ponyta:15; Tauros:5>Miltank; Miltank:5>Tauros")),
                ], assets=["paniola-ranch.jpg"]),
                location("Route 5", 21, [
                    g("Grass 1", 21, (18, 21), rlist("Fomantis:20; Slakoth:15; Shroomish:15; Yanma:15; Foongus:15; Treecko:15; Farfetch'd:10")),
                    g("Grass 2 (via Route 8)", 21, (30, 33), rlist("Lickitung:15; Gligar:15; Sudowoodo:15; Phanpy:15; Emolga:15; Wurmple:15; Silcoon:5; Cascoon:5"), category="return-later", conditions=["Accessible via Route 8."]),
                    g("Berry Piles", 21, (18, 21), rlist("Volbeat:100")),
                    g("Dust Clouds", 21, (30, 33), rlist("Diglett:60; Durant:40")),
                    g("SOS Calls", 22, None, rlist("Treecko>Panpour,Grovyle; Sudowoodo>Trevenant; Phanpy>Donphan; Wurmple>Beautifly,Dustox; Silcoon>Beautifly,Dustox; Cascoon>Dustox,Beautifly; Diglett>Diglett#kanto; Durant>Heatmor; Volbeat>Illumise")),
                ], pages=[21, 22], assets=["route-5.jpg", "route-5-map.jpg"]),
                location("Brooklet Hill", 23, [
                    g("Grass 1 (By entrance)", 23, (20, 23), rlist("Dewpider:15/0; Poliwag:15; Shelmet:15; Ducklett:15; Tympole:15; Paras:15/0; Karrablast:10; Surskit:0/15; Morelull:0/15")),
                    g("Grass 2 (Everywhere else)", 23, (20, 23), rlist("Dewpider:15/0; Froakie:15; Mudkip:15; Croagunk:15; Paras:15/0; Ducklett:10; Tympole:10; Surskit:0/15; Morelull:0/15")),
                    g("Fishing (Trial Site)", 23, (20, 23), rlist("Magikarp:34+0; Goldeen:25+15; Basculin:20+25; Corphish:20+30; Feebas:1+30")),
                    g("Fishing (Totem's Den)", 23, (20, 23), rlist("Magikarp:35+10; Wishiwashi:30+25; Alomomola:15+35; Carvanha:20+30")),
                    g("Surfing (Trial Site)", 23, (20, 23), rlist("Dewpider:20/0; Wooper:20; Marill:20; Poliwag:20; Psyduck:20; Surskit:0/20")),
                    g("Surfing (Totem's Den)", 23, (20, 23), rlist("Tentacool:40; Finneon:40; Wingull:20")),
                    g("SOS Calls", 24, None, rlist("Shelmet>Karrablast; Froakie>Pansear,Frogadier; Mudkip>Pansear,Marshtomp; Magikarp>Gyarados; Goldeen>Seaking; Basculin>Basculin")),
                ], pages=[23, 24], assets=["brooklet-hill.jpg"]),
                location("Route 6", 25, [
                    g("Grass 1", 25, (22, 25), rlist("Pawniard:15; Solosis:15; Gothita:15; Deerling*:15; Electrike:15; Fennekin:10; Herdier:10; Eevee:5"), notes=[FORM_NOTES["Deerling"]["note"]]),
                    g("Grass 2", 25, (22, 25), rlist("Minccino:15; Oricorio:15; Solosis:15; Gothita:15; Deerling:15; Electrike:10; Chespin:10; Eevee:5")),
                    g("SOS Calls", 25, None, rlist("Deerling>Deerling,Deerling; Fennekin>Pansage,Braixen; Herdier>Stoutland; Eevee>Espeon,Umbreon; Chespin>Panpour,Quilladin")),
                ], assets=["route-6.jpg", "route-6-map.png"]),
                location("Diglett's Tunnel", 26, [
                    g("Cave", 26, (24, 27), rlist("Diglett:20>Diglett#kanto; Zubat:15>Golbat; Ferroseed:15>Ferrothorn; Rhyhorn:15>Rhydon; Hippopotas:15; Druddigon:10; Larvitar:10>Pupitar")),
                    g("Dust Clouds", 26, (32, 35), rlist("Diglett:30>Diglett#kanto; Sandshrew#kanto:30>Sandshrew; Durant:20>Heatmor; Gible:20>Gabite")),
                ], assets=["digletts-tunnel.jpg"]),
                location("Route 7", 27, [
                    g("Fishing", 27, (26, 29), rlist("Magikarp:35+10>Gyarados; Wishiwashi:30+10; Staryu:25+50>Starmie; Relicanth:10+30")),
                    g("Surfing", 27, (26, 29), rlist("Tentacool:20; Finneon:20; Wingull:20; Wailmer:20; Pyukumuku:20")),
                    g("Dust Clouds", 27, (26, 29), rlist("Diglett:50>Diglett#kanto; Drilbur:50")),
                ], assets=["route-7.jpg"]),
                location("Wela Volcano Park", 28, [
                    g("Grass 1 (Base of Volcano)", 28, (26, 29), rlist("Cubone:24; Salandit:20; Fletchling:20; Numel:20; Magby:15; Kangaskhan:1")),
                    g("Grass 2 (On Volcano)", 28, (26, 29), rlist("Salandit:15; Fletchinder:15; Spoink:15; Charmander:15; Magby:15; Cubone:14; Koffing:10; Kangaskhan:1")),
                    g("SOS Calls", 28, None, rlist("Cubone>Kangaskhan; Salandit>Salazzle; Fletchling>Fletchinder; Magby>Happiny,Magmar; Charmander>Pansage,Charmeleon")),
                ], assets=["wela-volcano-park.jpg"]),
                location("Dividing Peak Tunnel", 29, [
                    g("Wimpod", 29, (27, 30), rlist("Wimpod:100")),
                    g("Shadows", 29, (27, 30), rlist("Kecleon:100")),
                ], assets=["dividing-peak-tunnel.jpg"]),
                location("Route 8", 30, [
                    g("All Grass", 30, (27, 30), rlist("Swirlix:15; Spritzee:15; Chatot:15; Stufful:15; Swablu:10; Torchic:10; Trumbeak:10; Plusle:5; Minun:5")),
                    g("Berry Piles", 30, (27, 30), rlist("Crabrawler:100")),
                    g("Wimpod", 30, (27, 30), rlist("Wimpod:100")),
                    g("Fishing", 30, (28, 30), rlist("Magikarp:50+10; Wishiwashi:30+20; Chinchou:5+35; Remoraid:15+35")),
                    g("Surfing", 30, (21, 24), rlist("Tentacool:20; Wingull:20; Frillish:20; Finneon:20; Mantyke:20")),
                    g("SOS Calls 1", 30, None, rlist("Swablu>Altaria; Torchic>Pansage,Combusken; Plusle>Minun; Minun>Plusle,Magmar")),
                    g("SOS Calls 2", 30, None, rlist("Magikarp>Gyarados; Chinchou>Lanturn; Remoraid>Octillery; Mantyke>Remoraid")),
                ], assets=["route-8.jpg"]),
                location("Lush Jungle", 31, [
                    g("Grass 1 (Entrance)", 31, (30, 33), rlist("Fomantis:20; Tropius:15/0; Steenee:15; Servine:10; Scyther:10; Comfey:10; Sudowoodo:10; Oranguru:5; Passimian:5; Noctowl:0/15")),
                    g("Grass 2 (Western Area)", 31, (30, 33), rlist("Parasect:15/0; Vulpix#kanto:15; Steenee:15; Comfey:15; Fomantis:10; Sudowoodo:10; Sunkern:10/0; Heracross:10; Shiinotic:0/15; Venonat:0/10")),
                    g("Grass 3 (Northern Area)", 31, (30, 33), rlist("Parasect:15/0; Tangela:15; Steenee:15; Comfey:15/0; Fomantis:10; Cherrim:10; Skorupi:10; Pinsir:10; Shiinotic:0/15; Goomy:0/15")),
                    g("Ambush Encounters", 31, None, rlist("Steenee:30; Oranguru:20; Passimian:20; Pignite:20; Larvesta:10")),
                    g("Weather SOS", 31, None, rlist("Goomy:11 [Rain]; Castform:11 [Hail, Sand]")),
                    g("SOS Calls 1", 31, None, rlist("Fomantis>Lurantis; Servine>Simipour; Sudowoodo>Trevenant; Oranguru>Passimian; Passimian>Oranguru")),
                    g("SOS Calls 2", 31, None, rlist("Pignite>Simisage; Larvesta>Volcarona; Vulpix#kanto>Vulpix; Sunkern>Sunflora; Venonat>Venomoth")),
                    g("SOS Calls 3", 31, None, rlist("Tangela>Tangrowth; Skorupi>Drapion; Goomy>Sliggoo")),
                ], assets=["lush-jungle.jpg"]),
                location("Lush Jungle Cave", 32, [
                    g("Cave", 32, (79, 82), rlist("Golbat:30>Crobat; Dugtrio:20>Dugtrio#kanto; Excadrill:20; Salandit:20>Salazzle; Larvesta:10>Volcarona")),
                ], assets=["lush-jungle-cave.jpg"]),
                location("Hano Beach", 33, [
                    g("Sand", 33, (38, 41), rlist("Staryu:20>Starmie; Sandygast:20; Krabby:20; Dwebble:20; Binacle:20")),
                    g("Surfing", 33, (38, 41), rlist("Finneon:30; Pyukumuku:30; Tentacool:20; Wingull:20")),
                    g("Water Splashes", 33, (38, 41), rlist("Skrelp:50; Clauncher:50")),
                ], assets=["hano-beach.jpg"]),
                location("Route 9", 34, [
                    g("Fishing", 34, (36, 39), rlist("Magikarp:20+10>Gyarados; Wishiwashi:15+5; Luvdisc:50+80; Corsola:15+5>Mareanie")),
                ], assets=["route-9.jpg"]),
                location("Memorial Hill", 35, [
                    g("All Grass", 35, (36, 39), rlist("Pumpkaboo*:30>Pumpkaboo; Haunter:20; Phantump:20>Trevenant; Girafarig:15; Sigilyph:15"), notes=[FORM_NOTES["Pumpkaboo"]["note"]]),
                ], assets=["memorial-hill.jpg"]),
                location("Akala Outskirts", 36, [
                    g("All Grass", 36, (36, 39), rlist("Darumaka:20>Darmanitan; Natu:20>Xatu; Golett:15>Baltoy; Nosepass:15; Honedge:10>Doublade; Pelipper:10; Togepi:10>Togetic")),
                    g("Fishing", 36, (36, 39), rlist("Magikarp:40+25>Gyarados; Wishiwashi:30+15; Clauncher:15+30>Clawitzer; Skrelp:15+30>Dragalge")),
                ], assets=["akala-outskirts.jpg"]),
            ],
        },
        {
            "name": "Ula'ula Island", "sourcePage": 37, "assets": ["ulaula-island.jpg"],
            "locations": [
                location("Malie City", 38, [
                    g("All Grass", 38, (41, 44), rlist("Trubbish:20>Garbodor; Grimer:15>Muk,Grimer#kanto; Mincinno:15; Swalot:15; Voltorb:15>Electrode; Porygon:10>Porygon2; Magneton:10")),
                ], assets=["malie-city.jpg"]),
                location("Malie Garden", 39, [
                    g("All Grass", 39, (41, 44), rlist("Exeggcute:20; Poliwhirl:15; Persian:15; Petilil:10; Cottonee:10; Farfetch'd:10; Araquanid:10/0; Ledian:10/0; Masquerain:0/10; Ariados:0/10")),
                    g("SOS Calls", 39, None, rlist("Poliwhirl>Poliwrath,Politoed; Persian>Persian; Petilil>Lilligant; Cottonee>Whimsicott; Corphish>Crawdaunt; Dratini>Dragonair")),
                    g("Weather SOS", 39, None, rlist("Greninja*:11 [Rain]; Castform:11 [Hail, Sand]"), notes=[FORM_NOTES["Greninja"]["note"]]),
                    g("Fishing", 39, (41, 44), rlist("Corphish:25+30; Basculin:20+30; Dratini:20+30; Seaking:20+0; Gyarados:15+10")),
                ], assets=["malie-garden.jpg"]),
                location("Route 10", 40, [
                    g("All Grass", 40, (41, 44), rlist("Zangoose:20>Seviper; Seviper:20>Zangoose; Fearow:20; Bouffalant:15; Skarmory:10; Pachirisu:10; Ledian:5/0; Ariados:0/5")),
                    g("Ambush Encounters", 40, None, rlist("Fearow:50; Pineco:30; Skarmory:20")),
                    g("Berry Piles", 40, (42, 45), rlist("Pachirisu:100")),
                ], assets=["route-10.jpg"]),
                location("Route 11", 41, [
                    g("All Grass", 41, (41, 44), rlist("Komala:20; Sawk:15>Throh; Throh:15>Sawk; Stantler:15; Pancham:15>Pangoro; Parasect:10/0; Shiinotic:0/10; Ledian:10/0; Ariados:0/10")),
                ], assets=["route-11.jpg"]),
                location("Mount Hokulani", 42, [
                    g("Grass 1", 42, (46, 49), rlist("Elgyem:30/20; Minior:30/20; Solrock:15/0; Beldum:15; Ditto:10; Clefairy:0/20; Lunatone:0/15")),
                    g("Grass 2", 42, (46, 49), rlist("Fearow:30/10; Elgyem:20; Minior:10; Beldum:10; Skarmory:10; Elekid:10; Ditto:10; Clefairy:0/20")),
                    g("SOS Calls", 42, None, rlist("Elgyem>Beheeyem; Beldum>Metang,Metagross; Solrock>Lunatone; Lunatone>Solrock; Elekid>Happiny,Electabuzz")),
                ], assets=["mount-hokulani.jpg", "mount-hokulani-map.png"]),
                location("Route 12", 43, [
                    g("All Grass", 43, (52, 55), rlist("Graveler:20>Graveler#kanto; Helioptile:20>Heliolisk; Torkoal:15; Magcargo:15; Houndoom:15; Manectric:15")),
                ], assets=["route-12.jpg"]),
                location("Blush Mountain", 44, [
                    g("All Grass", 44, (52, 55), rlist("Graveler:20>Golem#kanto,Golem; Rhyhorn:20>Rhydon,Rhyperior; Dedenne:10>Togedemaru; Charjabug:10>Vikavolt; Turtonator:10; Torkoal:10; Togedemaru:10>Dedenne; Electabuzz:10>Electivire")),
                ], assets=["blush-mountain.jpg"]),
                location("Ula'ula Beach", 45, [
                    g("Berry Piles", 45, (51, 54), rlist("Crabrawler:100>Crabominable")),
                ], assets=["ulaula-beach.jpg"]),
                location("Route 13", 45, [
                    g("Fishing", 45, (51, 54), rlist("Magikarp:35+10>Gyarados; Wishiwashi:30+15; Bruxish:25+45; Qwilfish:10+30")),
                ], assets=["route-13.jpg"]),
                location("Tapu Village", 46, [
                    g("All Grass", 46, (54, 57), rlist("Vanillish:15>Vanilluxe; Snover:15>Abomasnow; Vulpix:15>Ninetales; Sandshrew:15>Sandslash; Piloswine:15>Mamoswine; Glalie:15>Froslass; Absol:10")),
                    g("Weather SOS", 46, None, rlist("Vanillite:11 [Hail]; Castform:11 [Rain, Sand]")),
                ], assets=["tapu-village.jpg"]),
                location("Mount Lanakila", 47, [
                    g("Grass", 47, (54, 57), rlist("Sandshrew:15>Sandslash; Vulpix:15>Ninetales; Sneasel:15>Weavile; Snorunt:15>Froslass,Glalie; Bergmite:10>Avalugg; Cryogonal:10; Drampa:10; Absol:10")),
                    g("Weather SOS", 47, None, rlist("Vanillite:11 [Hail]; Castform:11 [Rain, Sand]")),
                ], assets=["mount-lanakila.jpg"]),
                location("Route 14", 48, [
                    g("Fishing", 48, (54, 57), rlist("Magikarp:40+20; Wishiwashi:35+15; Bruxish:15+35; Dhelmise:10+30")),
                    g("Surfing", 48, (54, 57), rlist("Tentacruel:20; Jellicent:20; Pelipper:20; Lapras:20; Lumineon:20")),
                    g("SOS Calls", 48, None, rlist("Magikarp>Gyarados; Jellicent>Frillish; Dhelmise>Skrelp")),
                ], assets=["route-14.jpg"]),
                location("Thrifty Megamart", 49, [
                    g("Building", 49, (57, 60), rlist("Haunter:15>Gengar; Golbat:15>Crobat; Spiritomb:15; Banette:15; Rotom*:15>Rotom; Klefki:10; Mimikyu:10"), notes=[FORM_NOTES["Rotom"]["note"]]),
                ], assets=["thrifty-megamart.jpg"]),
                location("Route 15 / 16", 50, [
                    g("Grass 1 (Route 15)", 50, (54, 57), rlist("Linoone:20; Carnivine:20; Pelipper:20; Slowbro:20; Gumshoos:20/0; Raticate:0/20")),
                    g("Grass 2 (Island)", 50, (57, 60), rlist("Carnivine:20; Wynaut:20; Pelipper:20; Togepi:10; Shuckle:10; Slowbro:10; Gumshoos:10/0; Raticate:0/10")),
                    g("Grass 3 (Route 16)", 50, (57, 60), rlist("Scrafty:20; Granbull:20; Slowbro:20; Pelipper:10; Gumshoos:20/0; Raticate:0/20")),
                    g("Fishing", 50, (54, 57), rlist("Magikarp:30+20; Wishiwashi:25+10; Bruxish:25+35; Clamperl:20+35")),
                    g("Surfing", 50, (55, 58), rlist("Tentacruel:40; Lumineon:40; Pelipper:20")),
                    g("Berry Piles", 50, (55, 58), rlist("Shuckle:100")),
                    g("SOS Calls", 50, None, rlist("Slowbro>Slowking; Raticate>Raticate#kanto; Magikarp>Gyarados; Crabrawler>Crabominable; Togepi>Togetic,Happiny; Wynaut>Wobbuffet,Happiny; Clamperl>Gorebyss,Huntail")),
                ], assets=["route-15-16.jpg"]),
                location("Ula'ula Meadow", 51, [
                    g("Grass", 51, (61, 64), rlist("Ribombee:20; Floette*:20; Oricorio:20; Lilligant:15; Whimsicott:15; Ledian:10/0; Ariados:0/10"), notes=[FORM_NOTES["Floette"]["note"]]),
                ], assets=["ulaula-meadow.jpg"]),
                location("Route 17", 52, [
                    g("Grass 1", 52, (62, 65), rlist("Fearow:20; Scrafty:20; Mienshao:20; Gumshoos:20/0; Ledian:20/0; Raticate:0/20; Ariados:0/20")),
                    g("Grass 2", 52, (62, 65), rlist("Donphan:20; Fearow:20; Scrafty:20; Graveler:20; Skarmory:10; Bisharp:10")),
                    g("Berry Piles", 52, (55, 58), rlist("Crabrawler:100")),
                    g("Weather SOS", 52, None, rlist("Sliggoo:11 [Rain]; Castform:11 [Sand, Hail]")),
                    g("SOS Calls", 52, None, rlist("Graveler>Graveler#kanto; Raticate>Raticate#kanto; Bisharp>Pawniard")),
                ], assets=["route-17.jpg"]),
                location("Haina Desert", 53, [
                    g("Sand", 53, (57, 60), rlist("Krokorok:20; Dugtrio:20; Maractus:20; Drapion:10; Hippowdon:20/10; Cacnea:10/0; Cacturne:0/20")),
                    g("SOS Calls", 53, None, rlist("Krokorok>Krookodile; Krookodile>Krokorok; Gabite>Gible,Garchomp; Vibrava>Trapinch,Flygon; Dugtrio>Dugtrio#kanto; All>Claydol; All>Golurk")),
                    g("Weather SOS", 53, None, rlist("Gabite:10 [Sand]; Castform:11 [Rain, Hail]")),
                    g("Dust Clouds", 53, (57, 60), rlist("Krookodile:30; Vibrava:30; Gabite:20; Dugtrio:20")),
                ], assets=["haina-desert.jpg"], notes=["There is also a 1% chance of encountering Castform in a Sandstorm here. This was not intentional and is leftover from when the encounter rates were unknown, but it is a harmless error retained in the source." ]),
                location("Victory Road", 54, [
                    g("Grass", 54, (87, 90), rlist("Sandshrew:20; Vulpix:20; Glalie:15; Absol:15; Sneasel:15; Abomasnow:10; Weavile:5")),
                    g("Cave", 54, (87, 90), rlist("Crobat:20; Glalie:15; Froslass:15; Drampa:15; Avalugg:15; Medicham:15; Weavile:5")),
                    g("Weather SOS", 54, None, rlist("Vanilluxe:11 [Hail]; Castform:11 [Rain, Sand]")),
                    g("SOS Calls", 54, None, rlist("Sandshrew>Sandslash; Vulpix>Ninetales; Glalie>Froslass; Froslass>Glalie; Sneasel>Weavile")),
                ], assets=["victory-road.jpg"]),
            ],
        },
        {
            "name": "Poni Island", "sourcePage": 55, "assets": ["poni-island.jpg"],
            "locations": [
                location("Seafolk Village", 56, [
                    g("Fishing", 56, (76, 79), rlist("Gyarados:55+30; Wailord:40+20; Dhelmise:5+50>Dragalge")),
                ], assets=["seafolk-village.jpg"]),
                location("Poni Wilds", 57, [
                    g("Grass", 57, (76, 79), rlist("Furfrou:20; Gastrodon:20; Granbull:20; Brionne:15>Primarina; Malamar:15; Pelipper:10")),
                    g("Berry Piles", 57, (76, 79), rlist("Shuckle:100")),
                ], assets=["poni-wilds.jpg"]),
                location("Exeggutor Island", 58, [
                    g("Grass", 58, (78, 81), rlist("Exeggutor:20; Tropius:20; Exeggcute:15>Exeggutor; Pelipper:15; Gastrodon:10; Pinsir:10; Heracross:10")),
                    g("Rain SOS", 58, None, rlist("Goodra:1 [Rain]; Sliggoo:10 [Rain]; Castform:11 [Sand, Hail]")),
                ], assets=["exeggutor-island.jpg"]),
                location("Ancient Poni Path", 59, [
                    g("Grass", 59, (76, 79), rlist("Furfrou:20; Gastrodon:20; Malamar:20; Pelipper:10; Granbull:10; Emboar:10")),
                ], assets=["ancient-poni-path.jpg"]),
                location("Ponibreaker Coast", 60, [
                    g("Fishing", 60, (70, 81), rlist("Gyarados:30+20; Wailord:30+20; Sharpedo:20+30; Relicanth:20+30")),
                    g("Surfing", 60, (76, 79), rlist("Tentacruel:30; Lumineon:20; Gastrodon:20; Pelipper:20; Lapras:10")),
                    g("Water Splashes", 60, (77, 80), rlist("Wailord:30; Dragalge:25; Clawitzer:25; Wailmer:20")),
                    g("Wimpod", 60, (77, 80), rlist("Wimpod:100")),
                ], assets=["ponibreaker-coast.jpg"]),
                location("Vast Poni Canyon", 61, [
                    g("Grass 1", 61, (80, 83), rlist("Machoke:20; Lycanroc*:20; Mienshao:20; Skarmory:10; Dartrix:10; Carbink:10; Hakamo-o:10"), notes=[FORM_NOTES["Lycanroc"]["note"]]),
                    g("Grass 2", 61, (80, 83), rlist("Machoke:20; Lycanroc:20; Mienshao:20; Skarmory:10; Torracat:10; Carbink:10; Hakamo-o:10")),
                    g("Cave", 61, (80, 83), rlist("Golbat:20; Dugtrio:20; Mawile:20; Boldore:20; Carbink:20")),
                    g("Caves with Water", 61, (80, 83), rlist("Zweilous:20; Carbink:20; Golbat:15; Dugtrio:15; Mawile:15; Boldore:15")),
                    g("Dust Clouds", 61, (80, 83), rlist("Dugtrio:40; Excadrill:30; Durant:30")),
                    g("Fishing", 61, (80, 85), rlist("Crawdaunt:30+20; Whiscash:30+20; Dragonair:20+40; Basculin:20+20")),
                    g("Surfing", 61, (80, 83), rlist("Floatzel:20; Golduck:20; Basculin:20; Azumarill:20; Golbat:20")),
                    g("SOS Calls", 62, None, rlist("Machoke>Machamp; Dartrix>Decidueye; Torracat>Incineroar; Hakamo-o>Kommo-o; Zweilous>Hydreigon; Carbink>Diancie; Carbink>Sableye; Golbat>Crobat; Boldore>Gigalith; Dugtrio>Dugtrio#kanto; Durant>Heatmor; Dragonair>Dragonite"), notes=["Lycanroc-Midday appears during the day and Lycanroc-Midnight at night; both have a small chance to call Lycanroc-Dusk.", "Diancie and Sableye are only called by Carbink encountered in caves. Diancie is very rare, though not as rare as the Salamence on Route 3.", "Dragonite is much more likely to be called by a Dragonair encountered in a bubbling spot."]),
                ], pages=[61, 62], assets=["vast-poni-canyon.jpg"]),
                location("Poni Grove", 62, [
                    g("Grass", 62, (95, 98), rlist("Lopunny:20; Toucannon:20; Zoroark:20; Heracross:10; Pinsir:10; Togetic:10>Togekiss; Riolu:10>Happiny,Lucario")),
                ], assets=["poni-grove.jpg"]),
                location("Poni Plains", 63, [
                    g("Grass 1", 63, (95, 98), rlist("Staraptor:20; Aggron:10; Toucannon:10; Tauros:10; Miltank:10; Gumshoos:20/0; Raticate:0/20; Weepinbell:20/0; Gloom:0/20")),
                    g("Grass 2 (Centre)", 63, (95, 98), rlist("Conkeldurr:20; Tangrowth:10; Tauros:10; Miltank:10; Gumshoos:20/0; Raticate:0/20; Hariyama:20/10; Hypno:10/20")),
                    g("Grass 3 (By Mountains)", 63, (95, 98), rlist("Mudsdale:20; Fearow:20; Skuntank:20; Gliscor:10; Miltank:10; Tauros:10; Jumpluff:10")),
                    g("Grass 4 (Coastal)", 63, (95, 98), rlist("Pelipper:20; Staraptor:10; Toucannon:10; Tauros:10; Miltank:10; Gumshoos:20/0; Raticate:0/20; Weepinbell:20/0; Gloom:0/20")),
                    g("Rustling Trees", 63, (95, 98), rlist("Primeape:60; Emolga:20; Ambipom:20")),
                    g("Rustling Grass", 63, (95, 98), rlist("Pyroar:50; Luxray:50")),
                    g("Rustling Bushes", 63, (97, 100), rlist("Blissey:100")),
                    g("Shadows", 63, (95, 98), rlist("Braviary:40; Mandibuzz:40; Talonflame:20")),
                ], assets=["poni-plains.jpg"]),
                location("Poni Meadow", 64, [
                    g("Grass", 64, (95, 98), rlist("Ribombee:20; Leavanny:20; Floette:20>Floette,Florges; Oricorio:10; Mismagius:10; Bellossom:10")),
                    g("Fishing", 64, (85, 98), rlist("Gyarados:50+30; Whiscash:30+30; Dragonair:20+40>Dragonite")),
                ], assets=["poni-meadow.jpg"]),
                location("Resolution Cave", 65, [
                    g("Cave (Exterior)", 65, (95, 98), rlist("Crobat:40; Dugtrio:30; Noivern:15; Druddigon:15")),
                    g("Cave (Interior)", 65, (95, 98), rlist("Unown:100")),
                    g("SOS Calls", 65, None, rlist("Dugtrio>Dugtrio#kanto")),
                ], assets=["resolution-cave.jpg"]),
                location("Poni Coast", 66, [
                    g("Dust Clouds", 66, (95, 98), rlist("Dugtrio:50>Dugtrio#kanto; Excadrill:50")),
                ], assets=["poni-coast.jpg"]),
                location("Poni Gauntlet", 67, [
                    g("Grass", 67, (95, 98), rlist("Lickilicky:20; Pelipper:20; Granbull:10; Malamar:10; Bewear:10; Altaria:10; Golduck:10; Togekiss:5; Eelektross:5")),
                    g("Fishing", 67, (85, 98), rlist("Gyarados:50+30; Whiscash:30+30; Dragonair:20+40>Dragonite")),
                ], assets=["poni-gauntlet.jpg"]),
            ],
        },
    ]

    # Attach stable IDs after the human-readable catalog has been assembled.
    encounter = {
        "schemaVersion": 1,
        "source": {
            "file": "references/Wild Pokemon Locations.pdf",
            "pages": 67,
            "description": "Photonic Sun/Prismatic Moon wild Pokémon locations guide.",
            "pokemonSource": "PokeAPI pokemon_species_names.csv, English names (local_language_id 9), snapshot generated for IDs 1..807.",
            "order": "islands, locations, groups, and rows follow source order; page numbers are PDF page numbers.",
            "formConvention": "The source marks Kantonian forms in red; unmarked regional species use the Alolan form where applicable.",
        },
        "sourcePages": list(range(1, 68)),
        "documentNotes": [
            {"sourcePage": 1, "text": "Wild Pokémon Locations."},
            {"sourcePage": 2, "text": "This document contains encounter rates for each area with wild Pokémon in the games. Areas are listed roughly in the order they become accessible. There are no version exclusives or differences, so this applies to both games; all 807 Pokémon can be obtained in either version. If a Pokémon is not listed here, it is probably a Legendary and will have its location listed in the Special Encounters document instead. Use Ctrl+F to find specific Pokémon quickly."},
            {"sourcePage": 2, "text": "Because each patch of grass in the Generation VII games has its own encounter table, each route has a massive variety of Pokémon to catch. This document includes maps of most areas that take advantage of this feature, showing exactly which patches of grass contain which Pokémon. Circled numbers on the maps correspond to tables labelled Grass 1, Grass 2, and so on."},
            {"sourcePage": 2, "text": "Where encounters change by time of day, the first rate column is daytime and the second is nighttime."},
            {"sourcePage": 2, "text": "Kantonian forms of Pokémon with Alolan forms are listed in red. Most can be found via SOS battles with their respective Alolan forms."},
        ],
        "islands": islands,
        "assets": [],
    }
    asset_paths = set()
    order = 0
    for island in encounter["islands"]:
        island["id"] = slugify(island["name"])
        island["assets"] = [a if a.startswith("assets/") else f"assets/locations/{a}" for a in island["assets"]]
        asset_paths.update(island["assets"])
        for loc in island["locations"]:
            order += 1
            loc["id"] = f"{island['id']}/{slugify(loc['name'])}"
            loc["order"] = order
            loc["assets"] = [a if a.startswith("assets/") else f"assets/locations/{a}" for a in loc["assets"]]
            asset_paths.update(loc["assets"])
            for index, grp in enumerate(loc["groups"], 1):
                grp["id"] = f"{loc['id']}/{slugify(grp['name'])}-{index}"
                for row_index, item in enumerate(grp["encounters"], 1):
                    item["id"] = f"{grp['id']}/{row_index}"
                    if item["species"] is not None:
                        item["speciesName"] = item["speciesName"]
                for note in grp["notes"]:
                    if note not in loc["notes"]:
                        pass
    asset_paths.add("assets/locations/title.png")
    encounter["assets"] = sorted(asset_paths)
    return encounter


# (PDF page, image index) -> (output filename, kind).  Black 65x42 swatches
# are intentionally omitted.  The small vertical map images are retained:
# they are actual map panels, not decoration.
ASSET_SPECS = {
    (1, 0): ("title.png", "title"),
    (2, 0): ("route-1-map.png", "map"),
    (3, 0): ("melemele-island.jpg", "island-map"),
    (4, 0): ("route-1.jpg", "location"),
    (6, 0): ("hau-oli-city.jpg", "location"), (6, 1): ("hau-oli-city-map.jpg", "map"),
    (7, 0): ("trainers-school.jpg", "location"),
    (8, 0): ("route-2.jpg", "location"), (8, 1): ("route-2-map.jpg", "map"),
    (9, 0): ("hau-oli-cemetery.jpg", "location"), (10, 0): ("sandy-cave.jpg", "location"),
    (11, 0): ("verdant-cavern.jpg", "location"), (12, 0): ("route-3.jpg", "location"), (12, 1): ("route-3-map.jpg", "map"),
    (13, 0): ("kalae-bay.jpg", "location"), (14, 0): ("melemele-meadow.jpg", "location"),
    (15, 0): ("seaward-cave.jpg", "location"), (16, 0): ("ten-carat-hill.jpg", "location"), (17, 0): ("melemele-sea.jpg", "location"),
    (18, 0): ("akala-island.jpg", "island-map"), (19, 0): ("route-4.jpg", "location"), (20, 0): ("paniola-ranch.jpg", "location"),
    (21, 0): ("route-5.jpg", "location"), (21, 1): ("route-5-map.jpg", "map"), (23, 0): ("brooklet-hill.jpg", "location"),
    (25, 0): ("route-6.jpg", "location"), (25, 1): ("route-6-map.png", "map"), (26, 0): ("digletts-tunnel.jpg", "location"),
    (27, 0): ("route-7.jpg", "location"), (28, 0): ("wela-volcano-park.jpg", "location"), (29, 0): ("dividing-peak-tunnel.jpg", "location"),
    (30, 0): ("route-8.jpg", "location"), (31, 0): ("lush-jungle.jpg", "location"), (32, 0): ("lush-jungle-cave.jpg", "location"),
    (33, 0): ("hano-beach.jpg", "location"), (34, 0): ("route-9.jpg", "location"), (35, 0): ("memorial-hill.jpg", "location"),
    (36, 0): ("akala-outskirts.jpg", "location"), (37, 0): ("ulaula-island.jpg", "island-map"), (38, 0): ("malie-city.jpg", "location"),
    (39, 0): ("malie-garden.jpg", "location"), (40, 0): ("route-10.jpg", "location"), (41, 0): ("route-11.jpg", "location"),
    (42, 0): ("mount-hokulani.jpg", "location"), (42, 1): ("mount-hokulani-map.png", "map"), (43, 0): ("route-12.jpg", "location"),
    (44, 0): ("blush-mountain.jpg", "location"), (45, 0): ("ulaula-beach.jpg", "location"), (45, 1): ("route-13.jpg", "location"),
    (46, 0): ("tapu-village.jpg", "location"), (47, 0): ("mount-lanakila.jpg", "location"), (48, 0): ("route-14.jpg", "location"),
    (49, 0): ("thrifty-megamart.jpg", "location"), (50, 0): ("route-15-16.jpg", "location"), (51, 0): ("ulaula-meadow.jpg", "location"),
    (52, 0): ("route-17.jpg", "location"), (53, 0): ("haina-desert.jpg", "location"), (54, 0): ("victory-road.jpg", "location"),
    (55, 0): ("poni-island.jpg", "island-map"), (56, 0): ("seafolk-village.jpg", "location"), (57, 0): ("poni-wilds.jpg", "location"),
    (58, 0): ("exeggutor-island.jpg", "location"), (59, 0): ("ancient-poni-path.jpg", "location"), (60, 0): ("ponibreaker-coast.jpg", "location"),
    (61, 0): ("vast-poni-canyon.jpg", "location"), (62, 0): ("poni-grove.jpg", "location"), (63, 0): ("poni-plains.jpg", "location"),
    (64, 0): ("poni-meadow.jpg", "location"), (65, 0): ("resolution-cave.jpg", "location"), (66, 0): ("poni-coast.jpg", "location"),
    (67, 0): ("poni-gauntlet.jpg", "location"),
}


def extract_assets() -> dict[str, dict]:
    reader = PdfReader(str(PDF))
    ASSETS.mkdir(parents=True, exist_ok=True)
    by_hash: dict[str, str] = {}
    metadata: dict[str, dict] = {}
    for (page_no, image_index), (filename, kind) in ASSET_SPECS.items():
        images = list(reader.pages[page_no - 1].images)
        if image_index >= len(images):
            raise ValueError(f"missing PDF image {page_no}:{image_index}")
        image = images[image_index]
        suffix = Path(filename).suffix.lower()
        source_suffix = Path(image.name).suffix.lower()
        if suffix == source_suffix and suffix in {".png", ".jpg", ".jpeg"}:
            payload = image.data
        else:
            # The title is JP2 in the source; PNG is lossless and broadly web-usable.
            out = ASSETS / filename
            image.image.save(out, format="PNG" if suffix == ".png" else "JPEG")
            payload = out.read_bytes()
        digest = hashlib.sha256(payload).hexdigest()
        existing = by_hash.get(digest)
        out_name = existing or filename
        if existing is None:
            (ASSETS / filename).write_bytes(payload)
            by_hash[digest] = filename
        rel = f"assets/locations/{out_name}"
        metadata[rel] = {"path": rel, "sourcePage": page_no, "kind": kind, "sha256": digest}
    return metadata


def link_species(encounters: dict, pokemon: list[dict]) -> None:
    by_slug = {item["slug"]: item for item in pokemon}
    for island in encounters["islands"]:
        for loc in island["locations"]:
            for grp in loc["groups"]:
                for item in grp["encounters"]:
                    if item["species"] is not None:
                        species = by_slug[item["species"]]
                        item["speciesId"] = species["id"]
                        item["speciesName"] = species["name"]
                    for ally in item["allies"]:
                        species = by_slug[ally["species"]]
                        ally["speciesId"] = species["id"]
                        ally["name"] = species["name"]


def resolve_and_validate(pokemon: list[dict], encounters: dict, assets: dict[str, dict]) -> list[str]:
    errors: list[str] = []
    if len(pokemon) != 807 or [x.get("id") for x in pokemon] != list(range(1, 808)) or len({x.get("id") for x in pokemon}) != 807:
        errors.append("pokemon.json must contain exactly unique IDs 1..807")
    by_slug = {x["slug"]: x for x in pokemon}
    seen_ids: set[str] = set()
    seen_pages: set[int] = set()
    previous_order = 0
    previous_page = 0
    def check_page(page: int, label: str) -> None:
        if not isinstance(page, int) or not 1 <= page <= 67:
            errors.append(f"{label} has source page outside 1..67")
        else:
            seen_pages.add(page)
    if encounters.get("sourcePages") != list(range(1, 68)):
        errors.append("sourcePages must enumerate exactly 1..67")
    for note in encounters.get("documentNotes", []):
        check_page(note.get("sourcePage"), "document note")
    for island in encounters["islands"]:
        check_page(island["sourcePage"], island["name"])
        for asset in island["assets"]:
            if not (ROOT / asset).exists():
                errors.append(f"missing asset {asset}")
        if island["id"] in seen_ids:
            errors.append(f"duplicate stable id {island['id']}")
        seen_ids.add(island["id"])
        for loc in island["locations"]:
            check_page(loc["sourcePage"], loc["name"])
            for page in loc["sourcePages"]:
                check_page(page, loc["name"])
            if loc["sourcePage"] < previous_page:
                errors.append("chronological location order is not preserved")
            previous_page = loc["sourcePage"]
            if loc["order"] <= previous_order:
                errors.append("location order is not strictly increasing")
            previous_order = loc["order"]
            if loc["id"] in seen_ids:
                errors.append(f"duplicate stable id {loc['id']}")
            seen_ids.add(loc["id"])
            for asset in loc["assets"]:
                if not (ROOT / asset).exists():
                    errors.append(f"missing asset {asset}")
            for grp in loc["groups"]:
                check_page(grp["sourcePage"], grp["name"])
                if grp["id"] in seen_ids:
                    errors.append(f"duplicate stable id {grp['id']}")
                seen_ids.add(grp["id"])
                if grp["category"] not in {"regular", "return-later"}:
                    errors.append(f"invalid category {grp['id']}")
                for item in grp["encounters"]:
                    if item["id"] in seen_ids:
                        errors.append(f"duplicate stable id {item['id']}")
                    seen_ids.add(item["id"])
                    if item["species"] is not None:
                        if item["species"] not in by_slug:
                            errors.append(f"unknown species slug {item['species']} ({item['speciesName']})")
                        elif item.get("speciesId") != by_slug[item["species"]]["id"]:
                            errors.append(f"species ID mismatch {item['id']}")
                    rates = item["rates"]
                    if rates is not None and (not rates or any(k not in {"single", "day", "night", "bubbling"} or not isinstance(v, int) or not 0 <= v <= 100 for k, v in rates.items())):
                        errors.append(f"invalid rates {item['id']}")
                    for ally in item["allies"]:
                        if ally["species"] not in by_slug:
                            errors.append(f"unknown ally slug {ally['species']}")
                        elif ally.get("speciesId") != by_slug[ally["species"]]["id"]:
                            errors.append(f"ally ID mismatch {item['id']}")
    if not seen_pages <= set(range(1, 68)):
        errors.append("source page outside 1..67")
    for path in encounters["assets"]:
        if not (ROOT / path).exists():
            errors.append(f"listed asset does not exist: {path}")
    # Suspicious tokens are checked against the source catalog after correction.
    for bad in ("Ratatta", "Mincinno", "Cher rim", "Tentac ruel", "Slow bro", "Hippo wdon", "Exegg utor", "Gre ninja", "Jangmo -o", "Hakamo -o"):
        if bad in json.dumps(encounters, ensure_ascii=False):
            errors.append(f"suspicious malformed token remains: {bad}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh-pokemon", action="store_true", help="download the pinned PokeAPI CSV snapshot")
    parser.add_argument("--extract-assets", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()
    pokemon = load_pokemon(args.refresh_pokemon)
    encounters = build_encounters()
    link_species(encounters, pokemon)
    assets = extract_assets() if args.extract_assets else {}
    if args.extract_assets:
        # Asset filenames are already catalogued in encounters; include metadata
        # separately so consumers can inspect provenance without parsing the PDF.
        for path, meta in assets.items():
            pass
    DATA.mkdir(exist_ok=True)
    (DATA / "encounters.json").write_text(json.dumps(encounters, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    errors = resolve_and_validate(pokemon, encounters, assets)
    if args.validate or errors:
        if errors:
            for error in errors:
                print(f"ERROR: {error}")
            return 1
        print(f"OK: 807 Pokémon, {len(encounters['islands'])} islands, {sum(len(i['locations']) for i in encounters['islands'])} locations, {len(encounters['assets'])} assets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
