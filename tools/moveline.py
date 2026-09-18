#!/usr/bin/env python3
"""Move report for a Pokemon family: sorted by competitive usage, tagged by how you get it.

Walks a species' whole evolution lineage (back to the base form, forward through every
branch), unions the Gen 7 learnsets, and reports each move with the gate that gets it
(level-up and the level, move reminder, TM, tutor, egg, event, or unavailable in Gen 7),
sorted by how often competitive players actually run it.

Sources are published datasets, never scraped:
  - Pokemon Showdown's data files (learnsets, moves, pokedex)
  - Smogon's monthly Gen 7 stats for November 2019, the last real snapshot for USUM
Files are cached outside the repository; the first run downloads what it needs.

Usage:
  python3 tools/moveline.py ralts
  python3 tools/moveline.py 278 --top 15
  python3 tools/moveline.py wingull --cache /tmp/poke-moves
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request
from pathlib import Path
from typing import Iterator

REPO = Path(__file__).resolve().parent.parent
SHOWDOWN_RAW = "https://raw.githubusercontent.com/smogon/pokemon-showdown/master/data/{name}.ts"
STATS = "https://www.smogon.com/stats/2019-11/moveset/gen7{tier}-{cutoff}.txt"

# Tier -> the cutoff its published file uses. OU is published at 1695, lower tiers at 1630.
TIERS = [("ou", "1695"), ("uu", "1630"), ("ru", "1630"), ("nu", "1630"), ("pu", "1630"), ("lc", "1630")]

# Learnset code prefixes. The leading digit is the generation; only 7 is relevant.
GATES = {"7L": "level", "7M": "TM", "7T": "tutor", "7E": "egg", "7S": "event"}

# Easiest first, for tie-breaking moves with equal usage.
EASE = ["level", "reminder", "TM", "tutor", "egg", "event"]

ICON = {
    "level": "\U0001F7E2",     # green circle: levels into it
    "reminder": "\U0001F501",  # move reminder at level 1
    "TM": "\U0001F4C0",
    "tutor": "\U0001F393",
    "egg": "\U0001F95A",
    "event": "\U0001F381",
    "unavailable": "\u274C",
}
LEGEND = ("\U0001F7E2 level-up · \U0001F501 move reminder · \U0001F4C0 TM · "
          "\U0001F393 tutor · \U0001F95A egg · \U0001F381 event")

# Where a species' usage lives, keyed by the tier the app already records for it. A species
# banned from a tier (BL) is used in the tier above, which is the file that holds its stats.
TIER_FILE = {"OU": "ou", "UUBL": "ou", "UU": "uu", "RUBL": "uu", "RU": "ru", "NUBL": "ru",
             "NU": "nu", "PUBL": "nu", "PU": "pu", "LC": "lc", "LC Uber": "lc"}


def fetch(url: str, dest: Path) -> Path:
    """Download to the cache once, then reuse it."""
    if dest.exists() and dest.stat().st_size > 500:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"fetching {url.rsplit('/', 1)[-1]} ...", file=sys.stderr)
    with urllib.request.urlopen(url, timeout=240) as response:
        dest.write_bytes(response.read())
    return dest


def top_blocks(text: str) -> Iterator[tuple[str, str]]:
    """Yield (key, body) for every top-level `key: { ... }` block in a Showdown data file."""
    for m in re.finditer(r"\n\t([a-z0-9\-]+): \{", text):
        key = m.group(1)
        i = m.end() - 1
        depth = 0
        for j in range(i, len(text)):
            ch = text[j]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    yield key, text[i : j + 1]
                    break


def normalize(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def canon(name: str) -> str:
    """Match a stats-file move name to a learnset key.

    The per-set stats file spells out the Hidden Power type ("Hidden Power Grass") while the
    learnset has one entry whose type comes from the Pokemon's IVs, so the two never match
    literally. Everything else compares by alphanumerics only.
    """
    key = normalize(name)
    return "hiddenpower" if key.startswith("hiddenpower") else key


def scalar(body: str, field: str) -> str | None:
    m = re.search(rf'\b{field}: "([^"]*)"', body)
    return m.group(1) if m else None


def list_field(body: str, field: str) -> list[str]:
    m = re.search(rf"{field}: \[([^\]]*)\]", body)
    if not m:
        return []
    return [x.strip().strip('"').lower().replace(" ", "") for x in m.group(1).split(",") if x.strip()]


def lineage(slug: str, dex: dict[str, str]) -> list[str]:
    """Base form first, then every branch forward from it."""
    prevo: dict[str, str] = {}
    evos: dict[str, list[str]] = {}
    for key, body in ((k, b) for k, b in dex.items()):
        p = scalar(body, "prevo")
        if p:
            prevo[key] = p.lower().replace(" ", "")
        e = list_field(body, "evos")
        if e:
            evos[key] = e
    base = slug
    while base in prevo:
        base = prevo[base]
    order: list[str] = []
    seen: set[str] = set()

    def walk(name: str) -> None:
        if name in seen:
            return
        seen.add(name)
        order.append(name)
        for child in evos.get(name, []):
            walk(child)

    walk(base)
    return [name for name in order if name in dex]


def gen7_moves(body: str) -> dict[str, dict[str, list[str]]]:
    """{move: {gate: [levels or empty]}} restricted to Gen 7 sources."""
    m = re.search(r"learnset: \{(.*)", body, re.S)
    if not m:
        return {}
    out: dict[str, dict[str, list[str]]] = {}
    for move, codes in re.findall(r"(\w+): \[([^\]]*)\]", m.group(1)):
        for code in (c.strip().strip('"') for c in codes.split(",")):
            if not code.startswith("7"):
                continue
            gate = GATES.get(code[:2])
            if gate:
                out.setdefault(move, {}).setdefault(gate, []).append(code[2:])
    return out


def usage_rows(text: str, species: str) -> dict[str, float]:
    """{move: percent of that species' sets} from a Smogon moveSet file."""
    lines = text.splitlines()
    head = re.compile(r"^\s*\|\s*([A-Za-z0-9'\u2019.\-: ]+?)\s*\|\s*$")
    start = next((i for i, l in enumerate(lines)
                  if (m := head.match(l)) and m.group(1).strip() == species), None)
    if start is None:
        return {}
    rows: dict[str, float] = {}
    inside = False
    for line in lines[start : start + 200]:
        if inside:
            if line.strip().startswith("+"):
                if rows:
                    break
                continue
            m = re.match(r"^\s*\|\s+(.+?)\s+([\d.]+)%\s*\|\s*$", line)
            if m:
                rows[m.group(1).strip()] = float(m.group(2))
        elif line.strip().startswith("|") and "moves" in line.lower() and "%" not in line:
            inside = True
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Move report for a Pokemon family.")
    parser.add_argument("species", help="any member of the family: name, slug or dex number")
    parser.add_argument("--cache", default=os.environ.get("POKE_DATA_CACHE", "/opt/data/poke-data"))
    parser.add_argument("--top", type=int, default=25, help="moves to list per final evolution (default 25)")
    args = parser.parse_args()

    cache = Path(args.cache)
    rows = json.loads((REPO / "data" / "pokemon.json").read_text())
    rows = rows if isinstance(rows, list) else list(rows.values())
    by_id = {int(r["id"]): r for r in rows}
    by_slug = {normalize(r["slug"]): r for r in rows}
    by_name = {normalize(r["name"]): r for r in rows}
    entry = (by_id.get(int(args.species)) if args.species.isdigit() else None) \
        or by_slug.get(normalize(args.species)) or by_name.get(normalize(args.species))
    if not entry:
        print(f"no such species: {args.species}", file=sys.stderr)
        return 2

    nice = {normalize(r["slug"]): r["name"] for r in rows}
    ls_text = fetch(SHOWDOWN_RAW.format(name="learnsets"), cache / "learnsets.ts").read_text(errors="replace")
    dex_text = fetch(SHOWDOWN_RAW.format(name="pokedex"), cache / "pokedex.ts").read_text(errors="replace")
    moves_text = fetch(SHOWDOWN_RAW.format(name="moves"), cache / "moves.ts").read_text(errors="replace")

    dex = dict(top_blocks(dex_text))
    moves = dict(top_blocks(moves_text))

    def power(body: str) -> str:
        found = re.search(r"\bbasePower: (\d+)", body)
        return found.group(1) if found else "-"

    move_meta = {k: (scalar(b, "name") or k, scalar(b, "type") or "?", power(b))
                 for k, b in moves.items()}
    meta_by_name = {normalize(v[0]): k for k, v in move_meta.items()}
    learned = dict(top_blocks(ls_text))
    details = json.loads((REPO / "data" / "pokedex-details.json").read_text())["species"]
    tier_of = {int(d["id"]): (d.get("tier") or "") for d in details}
    id_of = {normalize(r["slug"]): int(r["id"]) for r in rows}

    family = lineage(entry["slug"].lower(), dex)
    print(f"# {entry['name']} — lineage: {' -> '.join(nice.get(s, s) for s in family)}\n", file=sys.stderr)

    union: dict[str, dict[str, dict[str, list[str]]]] = {}
    for form in family:
        body = learned.get(form)
        if not body:
            continue
        for move, gate_map in gen7_moves(body).items():
            union.setdefault(move, {})[form] = gate_map

    evos_of = {k: list_field(b, "evos") for k, b in dex.items()}
    finals = [f for f in family if not [c for c in evos_of.get(f, []) if c in family]] or [family[-1]]

    for final in finals:
        usage: dict[str, float] = {}
        label = None
        preferred = TIER_FILE.get(tier_of.get(id_of.get(final, -1), ""))
        order = [t for t in TIERS if t[0] == preferred] + [t for t in TIERS if t[0] != preferred]
        for tier, cutoff in order:
            try:
                text = fetch(STATS.format(tier=tier, cutoff=cutoff),
                             cache / f"moveset-gen7{tier}-{cutoff}.txt").read_text(errors="replace")
            except Exception:
                continue
            got = usage_rows(text, nice.get(final, final))
            if got:
                usage, label = got, f"gen7{tier}-{cutoff}"
                break

        print(f"## {nice.get(final, final)}" + (f"   [{label}]" if label else "   [no usage data]"))
        print(f"   {LEGEND}")
        scored = []
        for move, forms in union.items():
            shown, kind, bp = move_meta.get(move, (move, "?", "-"))
            pct = next((v for k, v in usage.items() if canon(k) == canon(shown)), 0.0)
            gates: list[tuple[str, str]] = []
            for form, form_gates in forms.items():
                for gate, levels in form_gates.items():
                    if gate == "level":
                        for level in levels:
                            gates.append((("reminder" if level == "1" else "level"),
                                          f"{nice.get(form, form)} L{level}"))
                    else:
                        gates.append((gate, nice.get(form, form)))
            rank = min((EASE.index(g) for g, _ in gates), default=len(EASE))
            scored.append((pct, rank, shown, kind, bp, gates))
        scored.sort(key=lambda t: (-t[0], t[1], t[2]))
        # Moves the pros run that this game cannot legally produce at all. Worth showing:
        # otherwise they look like the obvious picks.
        known = {canon(row[2]) for row in scored}
        for shown, pct in usage.items():
            key = meta_by_name.get(canon(shown))
            if key is None or canon(shown) in known:
                continue
            name, kind, bp = move_meta[key]
            scored.append((pct, len(EASE), name, kind, bp, [("unavailable", "")]))
        scored.sort(key=lambda t: (-t[0], t[1], t[2]))
        if not scored:
            print("   (no Gen 7 moves found)")
        for pct, rank, shown, kind, bp, gates in scored[: args.top]:
            tags = []
            for gate, where in gates:
                if gate in ("level", "reminder"):
                    tags.append(f"{ICON[gate]} {where}")
                elif gate == "unavailable":
                    tags.append(f"{ICON[gate]} NOT obtainable in Gen 7")
                elif canon(shown) == "hiddenpower":
                    tags.append(f"{ICON[gate]} TM10 (type comes from IVs)")
                else:
                    tags.append(f"{ICON[gate]} {gate}")
            print(f"   {pct:5.1f}%  {shown:18} {kind:8} {bp:>4} BP   {' · '.join(dict.fromkeys(tags))}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
