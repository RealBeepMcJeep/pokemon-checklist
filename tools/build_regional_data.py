#!/usr/bin/env python3
"""Build regional collection facts from pinned historical Showdown metadata."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

try:
    from . import showdown_data as sd
except ImportError:
    import showdown_data as sd

try:
    from .showdown_text import array_field, field, integer_field, normalize_name, object_after, top_blocks
except ImportError:
    from showdown_text import array_field, field, integer_field, normalize_name, object_after, top_blocks

STATS = frozenset({"hp", "atk", "def", "spa", "spd", "spe"})

GEN7_POKEDEX = sd.DatasetSpec(
    name="gen7-pokedex", filename="gen7-pokedex.js",
    url=f"https://raw.githubusercontent.com/smogon/pokemon-showdown/{sd.SHOWDOWN_COMMIT}/data/mods/gen7/pokedex.js",
    sha256="70a4080bed36a66a75141d938ec6f90f9ab1cbb6c14c61154e2046498e7d6c34",
)
OUTPUT = Path(__file__).resolve().parents[1] / "data" / "regional-forms.json"


def build(cache_dir: str | Path, gen7_pokedex: str | Path) -> dict:
    """Admit immutable cached bytes. Never download or repair a normal build."""
    store = sd.require_cache(cache_dir)
    override = Path(gen7_pokedex).read_bytes()
    if hashlib.sha256(override).hexdigest() != GEN7_POKEDEX.sha256:
        raise ValueError("Gen VII Pokédex override hash mismatch")
    result = build_from_text(store.get_text("pokedex"), override.decode("utf-8"))
    result["source"] = {"showdownCommit": sd.SHOWDOWN_COMMIT, "pokedex": store.provenance("pokedex"), "gen7Pokedex": GEN7_POKEDEX.provenance()}
    return result



def _stats(body: str) -> dict[str, int]:
    raw = object_after(body, "baseStats") or ""
    return {key: int(value) for key, value in re.findall(r"\b(hp|atk|def|spa|spd|spe)\s*:\s*([0-9]+)", raw)}


def _abilities(body: str) -> dict[str, str]:
    raw = object_after(body, "abilities") or ""
    return dict(re.findall(r'''["']?([01HS])["']?\s*:\s*["']([^"']+)["']''', raw))


def build_from_text(pokedex_text: str, gen7_text: str) -> dict:
    """Project only regional collection identities; cosmetic caps are not targets."""
    blocks = dict(top_blocks(pokedex_text))
    overrides = dict(top_blocks(gen7_text))
    regional = sorted((integer_field(body, "num") or 0, key, body) for key, body in blocks.items()
                      if field(body, "forme") == "Alola" and 0 < (integer_field(body, "num") or 0) <= 807
                      and integer_field(body, "num") != 25)
    forms = {}
    for dex, alolan_key, alolan in regional:
        base_name = field(alolan, "baseSpecies")
        base_key = normalize_name(base_name or "")
        if not base_name or base_key not in blocks:
            raise ValueError(f"missing regular identity for {alolan_key}")
        for form, key, body in [("alolan", alolan_key, alolan), ("kanto", base_key, blocks[base_key])]:
            override = overrides.get(key, "")
            types = array_field(override, "types") if re.search(r"\btypes\s*:", override) else array_field(body, "types")
            stats, abilities = {**_stats(body), **_stats(override)}, {**_abilities(body), **_abilities(override)}
            if not types or set(stats) != STATS or not abilities:
                raise ValueError(f"incomplete regional facts for {key}")
            identity = f"{dex}:{form}"
            if identity in forms:
                raise ValueError(f"duplicate regional identity: {identity}")
            forms[identity] = {"id": dex, "form": form, "name": f"{base_name} ({'Alolan' if form == 'alolan' else 'Kanto'})",
                               "showdownKey": key, "types": types, "baseStats": stats, "abilities": abilities}
    if not forms:
        raise ValueError("no regional collection identities found")
    return {"schemaVersion": 1, "forms": forms}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, default=sd.configured_cache_dir())
    parser.add_argument("--gen7-pokedex", type=Path, help="SHA-256-verified pinned Gen VII override; never downloaded automatically")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    override = args.gen7_pokedex or args.cache.parent / "regional" / GEN7_POKEDEX.filename
    try:
        data = build(args.cache, override)
        content = json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        if args.check:
            if not args.output.exists() or args.output.read_text(encoding="utf-8") != content:
                parser.exit(1, "Regional catalogue is missing or stale; regenerate from the verified sources.\n")
        else:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(content, encoding="utf-8")
    except (OSError, ValueError, sd.ShowdownDataError) as error:
        parser.exit(1, f"Regional data build refused: {error}\n")
    print(f"Regional catalogue {'current' if args.check else 'generated'} ({len(data['forms'])} forms)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
