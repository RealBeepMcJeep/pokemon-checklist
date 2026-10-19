"""Pure projection of Gen VII evolution stages onto collection target identities."""
from __future__ import annotations

import re

try:
    from .showdown_text import field, integer_field, normalize_name, top_blocks
except ImportError:
    from showdown_text import field, integer_field, normalize_name, top_blocks


def _value(body: str, override: str, name: str, reader=field):
    source = override if re.search(rf"\b{re.escape(name)}\s*:", override) else body
    return reader(source, name)


def _method(body: str, override: str) -> str:
    kind = _value(body, override, "evoType")
    level = _value(body, override, "evoLevel", integer_field)
    item = _value(body, override, "evoItem")
    move = _value(body, override, "evoMove")
    if kind == "useItem" and item:
        method = f"Use {item}"
    elif kind == "trade":
        method = f"Trade holding {item}" if item else "Trade"
    elif kind == "levelFriendship":
        method = "Level up with high friendship"
    elif kind == "levelHold" and item:
        method = f"Level up holding {item}"
    elif kind == "levelMove" and move:
        method = f"Level up knowing {move}"
    elif level:
        method = f"Level {level}"
    elif kind == "levelExtra":
        method = "Level up"
    else:
        raise ValueError("evolution method is absent or unsupported in the pinned metadata")
    condition = _value(body, override, "evoCondition")
    return f"{method} {condition}" if condition else method


def build_graph(pokedex_text: str, gen7_text: str, pokemon: list[dict], regional_forms: dict, *, standard_methods: dict | None = None) -> dict:
    """Build stages/edges only; status edits and evolution reports are separate."""
    blocks, overrides = dict(top_blocks(pokedex_text)), dict(top_blocks(gen7_text))
    regional_ids = {row["id"] for row in regional_forms.values()}
    base_names = {row["id"]: row["name"] for row in pokemon}
    nodes, aliases = {}, {}
    for row in pokemon:
        if row["id"] in regional_ids:
            continue
        key, slug = str(row["id"]), normalize_name(row["slug"])
        nodes[key] = {"id": row["id"], "name": row["name"]}
        aliases[slug] = key
    for key, row in regional_forms.items():
        nodes[key] = {"id": row["id"], "form": row["form"], "name": row["name"]}
        aliases[row["showdownKey"]] = key
    edges = []
    for slug, key in aliases.items():
        if slug not in blocks:
            raise ValueError(f"missing evolution source species: {slug}")
        body, override = blocks[slug], overrides.get(slug, "")
        parent = _value(body, override, "prevo")
        if not parent:
            continue
        parent_key = aliases.get(normalize_name(parent))
        if parent_key is None:
            raise ValueError(f"unresolved evolution predecessor: {parent}")
        edge: dict = {"from": parent_key, "to": key, "stock": _method(body, override)}
        names = (base_names[nodes[parent_key]["id"]], base_names[nodes[key]["id"]])
        methods = standard_methods or {}
        default_form = _value(body, override, "baseForme")
        specific = methods.get((names[0], f"{names[1]}-{default_form}")) if default_form else None
        if rule := specific or methods.get(names):
            edge["prismatic"] = rule
        # The pinned battle metadata omits these game-specific evolution gates.
        # Verified: Serebii USUM evolution.shtml and Bulbapedia Alolan_Form/Cubone.
        dual_origins = {"26": "25", "103": "102", "105": "104"}
        dex, _, form = key.partition(":")
        if dual_origins.get(dex) == parent_key and form in {"kanto", "alolan"}:
            sm = "Trade/transfer needed; original form cannot be evolved locally in Sun/Moon." if form == "kanto" else "In Alola."
            usum = "Evolve in Ultra Space." if form == "kanto" else "Evolve in Alola, not Ultra Space."
            edge["conditions"] = {"sun": sm, "moon": sm, "ultra-sun": usum, "ultra-moon": usum,
                                  "photonic-prismatic": f"{usum} Stock USUM rule; hack-specific location behavior unverified."}
        if (parent_key, key) in {("104", "105:alolan"), ("19:alolan", "20:alolan")} and "night" not in edge["stock"].lower():
            edge["stock"] += " at night"
        edges.append(edge)
    edges.sort(key=lambda edge: (edge["from"], edge["to"]))
    return {"nodes": nodes, "edges": edges}
