#!/usr/bin/env python3
"""Turn a phrase from chat into a checklist change.

Hermes-side helper for the chat channel (Stage 2). It resolves what a player meant
and emits the record keys the sync engine writes ("species:25", "star:25"), so the
agent never has to guess a species or invent a key.

Parsing and resolution live here and are self-tested, because they are the part
that can be quietly wrong. Writing to the database is the small remainder and needs
a credential (see plans/multi-device-sync.md); it is deliberately not in this file.

    python tools/pokemon_chat.py --self-test
    python tools/pokemon_chat.py --text "i caught a pikachu"
    python tools/pokemon_chat.py --text "star 150"
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
POKEMON_PATH = ROOT / "data" / "pokemon.json"

Species = dict[str, Any]
Intent = dict[str, Any]

# Verbs, tried in this order. "trade" is sugar for seen: a traded Pokémon is one you
# no longer own, so it stops counting as caught but stays remembered. "team" is
# deliberately absent — see `parse`, where it means "star" only when it has a target.
INTENTS: list[tuple[str, tuple[str, ...]]] = [
    ("status_seen", ("trade", "traded", "trading", "released", "release")),
    ("status_seen", ("seen", "saw", "spotted", "sighted", "encountered")),
    ("status_none", ("uncaught", "uncatch", "unsee", "unseen", "forget", "cleared")),
    ("star_off", ("unstar", "unpin", "bench", "sub")),
    ("star_on", ("star", "pin", "favourite", "favorite", "team")),
    ("status_caught", ("caught", "catch", "catches", "got", "get", "obtained", "hatched")),
    ("team", ("roster", "lineup")),
    ("status_query", ("status", "check", "progress", "info", "where")),
    ("help", ("help", "commands", "how")),
]

FILLER = {
    "a", "an", "the", "i", "im", "ive", "just", "now", "my", "me", "to", "as", "is",
    "was", "were", "have", "had", "has", "did", "do", "does", "again", "please",
    "pokemon", "one", "it", "him", "her", "them", "in", "on", "for", "and", "then",
    "also", "today", "finally", "up", "down", "that", "this", "of", "no", "number",
    "from", "with", "you", "your", "am",
}

# Anything the player should not be able to trigger by chatting.
DANGEROUS = ("reset", "wipe", "clear everything", "delete everything", "start over")


def normalize(value: str) -> str:
    """Same rule the app uses: strip accents, case and punctuation."""
    decomposed = unicodedata.normalize("NFD", value)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]", "", stripped.lower())


def load_species() -> list[Species]:
    """data/pokemon.json, tolerating either a bare list or a wrapped one."""
    payload = json.loads(POKEMON_PATH.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        for key in ("species", "pokemon", "pokedex"):
            if isinstance(payload.get(key), list):
                payload = payload[key]
                break
    if not isinstance(payload, list):
        raise SystemExit("data/pokemon.json is not a list of species")
    species: list[Species] = []
    for raw in payload:
        if not isinstance(raw, dict) or "id" not in raw or "name" not in raw:
            continue
        species.append(
            {
                "id": int(raw["id"]),
                "name": str(raw["name"]),
                "slug": str(raw.get("slug") or normalize(str(raw["name"]))),
            }
        )
    if not species:
        raise SystemExit("data/pokemon.json contains no usable species")
    return species


def resolve(query: str, species: list[Species]) -> Intent:
    """Find one species, or say why not. Deterministic: no fuzzy guessing."""
    text = query.strip().lstrip("#").strip()
    if not text:
        return {"kind": "missing"}

    needle = normalize(text)
    if not needle:
        return {"kind": "missing"}

    # A bare number is a National Dex number, whether it arrived as "25" or "#025".
    if needle.isdigit():
        number = int(needle)
        for candidate in species:
            if candidate["id"] == number:
                return {"kind": "one", "species": candidate}
        return {"kind": "unknown_number", "number": number}

    for candidate in species:
        if candidate["slug"] == needle or normalize(str(candidate["name"])) == needle:
            return {"kind": "one", "species": candidate}

    prefixed = [
        candidate
        for candidate in species
        if normalize(str(candidate["name"])).startswith(needle)
    ]
    if len(prefixed) == 1:
        return {"kind": "one", "species": prefixed[0]}
    if prefixed:
        return {"kind": "ambiguous", "matches": prefixed[:5], "query": text}
    return {"kind": "unknown", "query": text}


def parse(text: str, species: list[Species]) -> Intent:
    """Text in, intent out. Never raises for anything a player might type."""
    cleaned = " ".join(text.split())
    lowered = cleaned.lower()
    for phrase in DANGEROUS:
        if phrase in lowered:
            return {
                "intent": "confirm_required",
                "reply": (
                    "That would clear progress. The app's Reset button is the only way "
                    "to do that, because it asks you to confirm first."
                ),
            }

    tokens = [token for token in re.split(r"[\s,]+", cleaned) if token]
    if tokens and tokens[0].startswith("/"):
        tokens[0] = tokens[0].lstrip("/")

    verb_index: int | None = None
    verb_word = ""
    intent = "status_query"
    for index, token in enumerate(tokens):
        word = normalize(token)
        matched = next(
            (name for name, verbs in INTENTS if word and word in verbs), None
        )
        if matched:
            verb_index = index
            verb_word = word
            intent = matched
            break

    def target_tokens() -> list[str]:
        remaining = tokens[verb_index + 1 :] if verb_index is not None else tokens
        return [token for token in remaining if normalize(token) not in FILLER]

    query = " ".join(target_tokens())

    # Bare "team" is a question about the roster; "team pikachu" is an instruction.
    if intent == "star_on" and verb_word == "team" and not query:
        return {"intent": "team"}
    if intent in ("team", "help"):
        return {"intent": intent}
    if not query.strip():
        return {"intent": "missing_target", "intent_kind": intent}

    found = resolve(query, species)
    kind = found["kind"]
    if kind == "one":
        target = found["species"]
        return {
            "intent": intent,
            "species": target,
            "record": record_for(intent, int(target["id"])),
            "reply": reply_for(intent, target),
        }
    if kind == "ambiguous":
        names = ", ".join(str(match["name"]) for match in found["matches"])
        return {
            "intent": "ambiguous",
            "reply": f"More than one match for “{query}”: {names}. Which one?",
        }
    if kind == "unknown_number":
        return {
            "intent": "unknown",
            "reply": f"There is no #{found['number']} in the National Dex.",
        }
    return {
        "intent": "unknown",
        "reply": f"I could not find a Pokémon called “{query}” in the National Dex.",
    }


def record_for(intent: str, species_id: int) -> dict[str, str]:
    """The record keys the sync engine writes, matching src/sync/records.ts."""
    if intent == "star_on":
        return {f"star:{species_id}": "on"}
    if intent == "star_off":
        return {f"star:{species_id}": "off"}
    status = {
        "status_caught": "caught",
        "status_seen": "seen",
        "status_none": "none",
        "status_query": "query",
    }[intent]
    return {f"species:{species_id}": status}


def reply_for(intent: str, target: Species) -> str:
    name = target["name"]
    number = int(target["id"])
    if intent == "status_caught":
        return f"Caught: {name} #{number:03d}."
    if intent == "status_seen":
        return f"Marked {name} #{number:03d} as seen."
    if intent == "status_none":
        return f"Cleared {name} #{number:03d}."
    if intent == "star_on":
        return f"Starred {name} #{number:03d} — it moves to the top of your Pokédex."
    if intent == "star_off":
        return f"Unstarred {name} #{number:03d}."
    return f"{name} #{number:03d}."


CASES: list[tuple[str, Intent]] = [
    ("i caught a pikachu", {"intent": "status_caught", "id": 25, "record": {"species:25": "caught"}}),
    ("Caught Pikachu!", {"intent": "status_caught", "id": 25}),
    ("/caught 25", {"intent": "status_caught", "id": 25}),
    ("just caught #025", {"intent": "status_caught", "id": 25}),
    ("got mewtwo", {"intent": "status_caught", "id": 150}),
    ("i traded my pikachu", {"intent": "status_seen", "id": 25, "record": {"species:25": "seen"}}),
    ("saw a bulbasaur", {"intent": "status_seen", "id": 1}),
    ("star mewtwo", {"intent": "star_on", "id": 150, "record": {"star:150": "on"}}),
    ("team pikachu", {"intent": "star_on", "id": 25}),
    ("team", {"intent": "team"}),
    ("unstar pikachu", {"intent": "star_off", "id": 25, "record": {"star:25": "off"}}),
    ("mr mime", {"intent": "status_query", "id": 122}),
    ("status of 445", {"intent": "status_query", "id": 445}),
    ("pikachu please", {"intent": "status_query", "id": 25}),
    ("caught zzzznope", {"intent": "unknown"}),
    ("caught 999", {"intent": "unknown"}),
    ("reset everything", {"intent": "confirm_required"}),
    ("cleared my pikachu", {"intent": "status_none", "id": 25}),
]


def case_value(result: Intent, key: str) -> Any:
    if key == "id":
        species = result.get("species")
        return species.get("id") if isinstance(species, dict) else None
    return result.get(key)


def self_test() -> int:
    species = load_species()
    failures = 0
    for text, expected in CASES:
        result = parse(text, species)
        mismatch = next(
            (
                (key, want, case_value(result, key))
                for key, want in expected.items()
                if case_value(result, key) != want
            ),
            None,
        )
        if mismatch:
            failures += 1
            key, want, got = mismatch
            print(f"FAIL  {text!r}: {key} expected {want!r}, got {got!r}")
        else:
            print(f"ok    {text!r} -> {result.get('intent')}")
    print(f"\n{len(CASES) - failures}/{len(CASES)} parsing cases pass")
    return 1 if failures else 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--text", help="a phrase to interpret")
    parser.add_argument("--self-test", action="store_true", help="run the parsing cases")
    args = parser.parse_args(argv)

    if args.self_test:
        return self_test()
    if not args.text:
        parser.error("pass --text or --self-test")
    print(json.dumps(parse(args.text, load_species()), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
