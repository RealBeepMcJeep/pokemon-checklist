#!/usr/bin/env python3
"""Compile the collection evolution graph from admitted Gen VII and Standard sources."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path

try:
    from . import build_regional_data as regional
    from . import showdown_data as sd
    from .evolution_data import build_graph
except ImportError:
    import build_regional_data as regional
    import showdown_data as sd
    from evolution_data import build_graph

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "evolutions.json"
REGIONAL_CONDITION_SOURCES = [
    "https://www.serebii.net/ultrasunultramoon/evolution.shtml",
    "https://bulbapedia.bulbagarden.net/wiki/Alolan_Form",
    "https://bulbapedia.bulbagarden.net/wiki/Cubone_(Pok%C3%A9mon)",
    "https://bulbapedia.bulbagarden.net/wiki/Rattata_%28Pok%C3%A9mon%29",
]


def load_standard_methods(root: Path = ROOT) -> tuple[dict, dict]:
    """Verify every retained original, then read the shared literal rule table.

    AST admission avoids importing the team-search engine into a data compiler.
    It neither executes the helper nor creates a second evolution-rule authority.
    """
    directory = root / "references" / "prismatic-moon"
    manifest = json.loads((directory / "MANIFEST.json").read_text(encoding="utf-8"))
    evolution_source = None
    for row in manifest:
        name = row["name"]
        if Path(name).name != name:
            raise ValueError("reference manifest contains an unsafe filename")
        raw = (directory / name).read_bytes()
        if len(raw) != row["bytes"] or hashlib.sha256(raw).hexdigest() != row["sha256"]:
            raise ValueError(f"reference integrity mismatch: {name}")
        if name == "Evolution Changes.pdf":
            evolution_source = {key: row[key] for key in ["name", "bytes", "sha256"]}
    if evolution_source is None:
        raise ValueError("verified Evolution Changes.pdf is missing from the manifest")
    module = ast.parse((root / "tools" / "team_options.py").read_text(encoding="utf-8"))
    definitions = [node for node in module.body if isinstance(node, ast.Assign)
                   and any(isinstance(target, ast.Name) and target.id == "HACK_EVOLUTIONS" for target in node.targets)]
    if len(definitions) != 1:
        raise ValueError("expected one shared HACK_EVOLUTIONS literal")
    methods = ast.literal_eval(definitions[0].value)
    if not isinstance(methods, dict) or any(not isinstance(key, tuple) or len(key) != 2
        or any(not isinstance(name, str) or not name for name in key)
        or not isinstance(value, str) or not value for key, value in methods.items()):
        raise ValueError("shared Standard evolution methods are malformed")
    return methods, evolution_source


def build(cache_dir: str | Path, gen7_pokedex: str | Path) -> dict:
    facts = regional.build(cache_dir, gen7_pokedex)
    methods, reference = load_standard_methods()
    pokemon = json.loads((ROOT / "data" / "pokemon.json").read_text(encoding="utf-8"))
    store = sd.require_cache(cache_dir)
    graph = build_graph(store.get_text("pokedex"), Path(gen7_pokedex).read_text(encoding="utf-8"), pokemon, facts["forms"], standard_methods=methods)
    serialized_methods = json.dumps(sorted((a, b, rule) for (a, b), rule in methods.items()), ensure_ascii=False, separators=(",", ":"))
    return {"schemaVersion": 1, "source": {**facts["source"], "standardEvolution": reference,
            "standardMethodsSha256": hashlib.sha256(serialized_methods.encode("utf-8")).hexdigest(),
            "regionalConditionUrls": REGIONAL_CONDITION_SOURCES},
            "methodScope": "Base requirements from pinned Gen VII metadata, verified Standard overrides and cited regional corrections; additional individual, form, ability and game conditions may apply.",
            **graph}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, default=sd.configured_cache_dir())
    parser.add_argument("--gen7-pokedex", type=Path)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    override = args.gen7_pokedex or args.cache.parent / "regional" / regional.GEN7_POKEDEX.filename
    try:
        data = build(args.cache, override)
        content = json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        if args.check:
            if not args.output.exists() or args.output.read_text(encoding="utf-8") != content:
                parser.exit(1, "Evolution graph is missing or stale; regenerate from the verified sources.\n")
        else:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(content, encoding="utf-8")
    except (OSError, ValueError, SyntaxError, sd.ShowdownDataError) as error:
        parser.exit(1, f"Evolution build refused: {error}\n")
    print(f"Evolution graph {'current' if args.check else 'generated'} ({len(data['nodes'])} targets; {len(data['edges'])} edges)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
