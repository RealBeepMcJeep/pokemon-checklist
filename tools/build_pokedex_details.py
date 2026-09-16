#!/usr/bin/env python3
"""Build child-friendly grades and type data from pinned Generation VII sources."""

from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import re
import unicodedata
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "pokedex-details.json"
SHOWDOWN_COMMIT = "e7aee8d9ccc983c59c5608929773249adca16b8f"
SOURCES = {
    "pokedex": (
        f"https://raw.githubusercontent.com/smogon/pokemon-showdown/{SHOWDOWN_COMMIT}/data/pokedex.js",
        "3d0f28348380c92cb01e0a9daebeba5ee12b6ed32899f583ed9f2b72029065d0",
    ),
    "tiers": (
        f"https://raw.githubusercontent.com/smogon/pokemon-showdown/{SHOWDOWN_COMMIT}/data/mods/gen7/formats-data.js",
        "5c6608b6c7b71f13d26ccf01963f16b94db8dfb87ed00420ecfc89708616d8c0",
    ),
    "usage": (
        "https://www.smogon.com/stats/2019-11/gen7ou-1695.txt",
        "3e5dbb64cd8f5e0bfb01ade6856c3005b34addcfbf56bc32c590ac123b65d322",
    ),
}
GRADE_BY_TIER = {
    "AG": "SSS",
    "Uber": "SSS",
    "OU": "S",
    "UUBL": "S",
    "UU": "A",
    "RUBL": "A",
    "RU": "B",
    "NUBL": "B",
    "NU": "C",
    "PUBL": "C",
    "PU": "D",
    "(PU)": "F",
}
GRADE_ORDER = {
    grade: index for index, grade in enumerate(("SSS", "S", "A", "B", "C", "D", "F"))
}


def normalize(value: object) -> str:
    return re.sub(
        "[^a-z0-9]",
        "",
        unicodedata.normalize("NFD", str(value))
        .encode("ascii", "ignore")
        .decode()
        .lower(),
    )


def download(url: str, expected_hash: str) -> str:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in {
        "raw.githubusercontent.com",
        "www.smogon.com",
    }:
        raise ValueError(f"unapproved source URL: {url}")
    connection = http.client.HTTPSConnection(parsed.hostname, timeout=30)
    path = parsed.path + (f"?{parsed.query}" if parsed.query else "")
    try:
        connection.request(
            "GET", path, headers={"User-Agent": "pokemon-checklist-data-builder"}
        )
        response = connection.getresponse()
        if response.status != 200:
            raise ValueError(f"cannot download {url}: HTTP {response.status}")
        raw = response.read()
    except OSError as error:
        raise ValueError(f"cannot download {url}") from error
    finally:
        connection.close()
    actual_hash = hashlib.sha256(raw).hexdigest()
    if actual_hash != expected_hash:
        raise ValueError(f"source hash changed for {url}: {actual_hash}")
    return raw.decode("utf-8")


def read_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(
            f"cannot read valid JSON from {path.relative_to(ROOT)}"
        ) from error


def number(value: str) -> float:
    try:
        return float(value)
    except ValueError as error:
        raise ValueError(f"invalid usage percentage: {value}") from error


def form_key_parts(value: str) -> tuple[int, str]:
    match = re.fullmatch(r"([1-9][0-9]{0,2}):([a-z0-9-]+)", value)
    if not match:
        raise ValueError(f"invalid form key: {value}")
    try:
        species_id = int(match.group(1))
    except ValueError as error:
        raise ValueError(f"invalid species number in form key: {value}") from error
    return species_id, match.group(2)


def js_entries(text: str) -> dict[str, str]:
    return {
        match.group(1): match.group(2)
        for match in re.finditer(
            r"^\t([a-z0-9]+): \{\n(.*?)(?=^\t[a-z0-9]+: \{|^\};)",
            text,
            re.MULTILINE | re.DOTALL,
        )
    }


def quoted_field(block: str, field: str) -> str | None:
    match = re.search(rf'^\t\t{field}: ["\']([^"\']+)', block, re.MULTILINE)
    return match.group(1) if match else None


def integer_field(block: str, field: str) -> int | None:
    match = re.search(rf"^\t\t{field}: ([0-9]+)", block, re.MULTILINE)
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError as error:
        raise ValueError(f"invalid {field} number in Showdown data") from error


def array_field(block: str, field: str) -> list[str]:
    match = re.search(rf"^\t\t{field}: (\[.*?\])", block, re.MULTILINE)
    if not match:
        return []
    try:
        values = json.loads(match.group(1))
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid {field} array in Showdown data") from error
    if not isinstance(values, list) or not all(
        isinstance(value, str) for value in values
    ):
        raise ValueError(f"invalid {field} values in Showdown data")
    return values


def encounter_form_keys() -> set[str]:
    forms: set[str] = set()

    def add(species_id: object, name: object, kind: str = "form") -> None:
        if not isinstance(species_id, int) or not isinstance(name, str):
            return
        slug = normalize(name)
        if slug:
            forms.add(f"{species_id}:{slug if kind == 'form' else f'{kind}-{slug}'}")

    for path in sorted((ROOT / "data").glob("encounters*.json")):
        data = read_json(path)
        if not isinstance(data, dict):
            raise ValueError(f"{path.relative_to(ROOT)} must contain an object")
        for island in data["islands"]:
            for location in island["locations"]:
                for group in location["groups"]:
                    for row in group["encounters"]:
                        add(row.get("speciesId"), row.get("form"))
                        for form in row.get("forms", []):
                            add(row.get("speciesId"), form)
                        add(row.get("speciesId"), row.get("ability"), "ability")
                        for ally in row.get("allies", []):
                            add(ally.get("speciesId"), ally.get("form"))
    return forms


def form_source(base: str, slug: str) -> tuple[str, bool]:
    if slug in {
        "base",
        "normal",
        "kanto",
        "redstriped",
        "spring",
        "average",
        "baile",
        "midday",
        "eastsea",
    }:
        return base, False
    if slug == "alolan":
        return f"{base}alola", True
    if slug == "bluestriped":
        return f"{base}bluestriped", True
    if slug in {"heat", "frost", "midnight", "dusk", "small", "large"}:
        return f"{base}{slug}", True
    if slug == "supersize":
        return f"{base}super", True
    if slug == "eternalflower":
        return f"{base}eternal", True
    if slug == "owntempo":
        return "lycanrocdusk", True
    if slug == "ability-battlebond":
        return "greninjaash", True
    return base, False


def build() -> dict[str, object]:
    source = {name: download(*config) for name, config in SOURCES.items()}
    pokedex_blocks = js_entries(source["pokedex"])
    tier_blocks = js_entries(source["tiers"])
    pokedex = {
        key: {
            "name": quoted_field(block, "species") or key,
            "base": quoted_field(block, "baseSpecies"),
            "types": array_field(block, "types"),
            "evos": array_field(block, "evos"),
            "prevo": quoted_field(block, "prevo"),
            "evoType": quoted_field(block, "evoType"),
            "evoLevel": integer_field(block, "evoLevel"),
            "evoItem": quoted_field(block, "evoItem"),
            "evoMove": quoted_field(block, "evoMove"),
            "evoCondition": quoted_field(block, "evoCondition"),
        }
        for key, block in pokedex_blocks.items()
    }
    tiers = {
        key: tier
        for key, block in tier_blocks.items()
        if (tier := quoted_field(block, "tier"))
    }
    usage = {
        normalize(name): number(value)
        for name, value in re.findall(
            r"^ \|\s*\d+\s*\|\s*(.*?)\s*\|\s*([0-9.]+)%",
            source["usage"],
            re.MULTILINE,
        )
    }
    pokemon = read_json(ROOT / "data" / "pokemon.json")
    if not isinstance(pokemon, list):
        raise ValueError("data/pokemon.json must contain a list")
    base_keys = {item["id"]: normalize(item["slug"]) for item in pokemon}

    def evolution_method(entry: dict[str, object]) -> str | None:
        evo_type = entry["evoType"]
        level = entry["evoLevel"]
        item = entry["evoItem"]
        move = entry["evoMove"]
        condition = entry["evoCondition"]
        if evo_type == "useItem":
            method = f"Use {item}"
        elif evo_type == "trade":
            method = f"Trade holding {item}" if item else "Trade"
        elif evo_type == "levelFriendship":
            method = "Level up with high friendship"
        elif evo_type == "levelMove":
            method = f"Level up knowing {move}"
        elif evo_type == "levelHold":
            method = f"Level up holding {item}"
        elif evo_type == "levelExtra":
            method = "Level up"
        elif level:
            method = f"Level {level}"
        else:
            return None
        return f"{method} {condition}" if condition else method

    def evolution_path(key: str) -> list[dict[str, str]]:
        path: list[dict[str, str]] = []
        seen: set[str] = set()
        while key in pokedex and key not in seen:
            seen.add(key)
            entry = pokedex[key]
            step = {"name": entry["name"]}
            if method := evolution_method(entry):
                step["method"] = method
            path.insert(0, step)
            key = entry["prevo"] or ""
        return path

    def leaves(
        key: str, allow_forms: bool, seen: frozenset[str] = frozenset()
    ) -> list[str]:
        if key in seen or key not in pokedex:
            return []
        evos = pokedex[key]["evos"]
        if not allow_forms:
            evos = [evo for evo in evos if evo in pokedex and not pokedex[evo]["base"]]
        if not evos:
            return [key]
        result: list[str] = []
        for evo in evos:
            result.extend(leaves(evo, allow_forms, seen | {key}))
        return result or [key]

    def details(
        key: str,
        fallback: str,
        allow_forms: bool,
        own_tier_key: str | None = None,
    ) -> dict[str, object]:
        entry = pokedex.get(key) or pokedex[fallback]
        candidates = leaves(key, allow_forms)
        graded = [
            candidate
            for candidate in candidates
            if tiers.get(candidate) in GRADE_BY_TIER
        ]
        if not graded and key != fallback:
            candidates = leaves(fallback, False)
            graded = [
                candidate
                for candidate in candidates
                if tiers.get(candidate) in GRADE_BY_TIER
            ]
        if not graded:
            raise ValueError(f"no grade source for {key}")
        source_key = min(
            graded, key=lambda item: GRADE_ORDER[GRADE_BY_TIER[tiers[item]]]
        )
        result: dict[str, object] = {
            "types": entry["types"] or pokedex[fallback]["types"],
            "grade": GRADE_BY_TIER[tiers[source_key]],
            "source": pokedex[source_key]["name"],
            "tier": tiers[source_key],
            "ownTier": tiers.get(own_tier_key or key, tiers[fallback]),
        }
        if usage.get(source_key, 0) > 0:
            result["usage"] = usage[source_key]
        return result

    species = []
    for item in pokemon:
        key = base_keys[item["id"]]
        if key not in pokedex or key not in tiers:
            raise ValueError(f"missing Showdown data for {item['name']}")
        entry = {"id": item["id"], **details(key, key, False)}
        path = evolution_path(key)
        if len(path) > 1:
            entry["evolution"] = path
        species.append(entry)

    forms = {}
    form_keys = [(form_key_parts(value)[0], value) for value in encounter_form_keys()]
    for raw_id, form_key in sorted(form_keys):
        _, slug = form_key_parts(form_key)
        base = base_keys[raw_id]
        source_key, allow_forms = form_source(base, slug)
        own_tier_key = "rockruffdusk" if slug == "owntempo" else source_key
        forms[form_key] = details(source_key, base, allow_forms, own_tier_key)

    return {
        "schemaVersion": 1,
        "source": {
            "showdownCommit": SHOWDOWN_COMMIT,
            "usage": "gen7ou-1695, November 2019",
        },
        "species": species,
        "forms": forms,
    }


def output_text(data: dict[str, object]) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="fail if generated data differs"
    )
    args = parser.parse_args()
    generated = output_text(build())
    if args.check:
        if not OUTPUT.is_file() or OUTPUT.read_text(encoding="utf-8") != generated:
            print(f"ERROR: {OUTPUT.relative_to(ROOT)} is stale")
            return 1
        print(f"OK: {OUTPUT.relative_to(ROOT)} is current")
        return 0
    OUTPUT.write_text(generated, encoding="utf-8")
    print(f"Wrote {OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
