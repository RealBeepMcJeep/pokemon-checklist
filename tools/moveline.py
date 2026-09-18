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
import base64
import html as html_escape
import json
import os
import re
import subprocess
import sys
import tempfile
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

# Battle Points charged by the USUM move tutors, for the tutor-only moves. Costs verified
# against Serebii's Move Tutors page (ultrasunultramoon/movetutors.shtml): Big Wave Beach,
# Ula'ula Beach and the Battle Tree. A move absent here is still a tutor move, cost unknown.
TUTOR_BP = {
    "bind": 4, "snore": 4, "waterpulse": 4,
    "bounce": 8, "defog": 8, "electroweb": 8, "firepunch": 8, "healbell": 8, "ironhead": 8,
    "knockoff": 12, "lowkick": 8, "magiccoat": 8, "magicroom": 8, "painsplit": 8,
    "roleplay": 8, "tailwind": 8, "thunderpunch": 8, "trick": 8, "uproar": 8,
    "wonderroom": 8, "zenheadbutt": 8, "drillrun": 8, "icepunch": 8, "drainpunch": 8,
    "gastroacid": 8, "skillswap": 8, "seedbomb": 12, "icywind": 12, "laserfocus": 12,
    "foulplay": 12, "superfang": 12, "earthpower": 12, "dualchop": 12, "heatwave": 12,
    "hypervoice": 12, "stompingtantrum": 12, "dragonpulse": 12,
    "aquatail": 12, "endeavor": 16, "focuspunch": 16, "liquidation": 16, "outrage": 16,
    "skyattack": 16, "throatchop": 16, "gunkshot": 16, "superpower": 16,
}

# Chip colours, keyed by how a move is obtained, then by type.
GATE_COLOR = {"level": "#2e7d32", "reminder": "#00796b", "TM": "#1565c0", "tutor": "#6a1b9a",
              "egg": "#e65100", "event": "#ad1457", "unavailable": "#b71c1c"}
TYPE_COLOR = {"Normal": "#9e9e9e", "Fire": "#e64a19", "Water": "#1976d2", "Electric": "#f9a825",
              "Grass": "#388e3c", "Ice": "#0097a7", "Fighting": "#c2185b", "Poison": "#7b1fa2",
              "Ground": "#8d6e63", "Flying": "#5c6bc0", "Psychic": "#d81b60", "Bug": "#689f38",
              "Rock": "#a1887f", "Ghost": "#512da8", "Dragon": "#303f9f", "Dark": "#455a64",
              "Steel": "#607d8b", "Fairy": "#ec407a"}


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


def short_method(method: str | None) -> str:
    """"Level 25" -> "L25", "Use Dawn Stone" -> "Dawn Stone"."""
    if not method:
        return ""
    found = re.match(r"Level (\d+)", method)
    return f"L{found.group(1)}" if found else method.removeprefix("Use ")


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


def sprite_style(dex: int | None, atlas_b64: str, scale: int = 3) -> str:
    """Crop one frame out of the app's own icon atlas.

    Geometry comes from src/data.ts (ATLAS): 32 columns of 40x30 frames in a 1280x780 sheet,
    and frame n is at index dex-1 - the same formula the app's sprite <img> uses.
    """
    if not dex:
        return ""
    index = dex - 1
    col, row = index % 32, index // 32
    return (
        f"background-image:url(data:image/png;base64,{atlas_b64});"
        f"background-size:{1280 * scale}px {780 * scale}px;"
        f"background-position:-{40 * scale * col}px -{30 * scale * row}px;"
        "image-rendering:pixelated;"
    )


def card_html(
    base_name: str,
    edges: list[tuple[str, int | None, str, str, int | None]],
    sections: list[dict],
) -> str:
    atlas_b64 = base64.b64encode((REPO / "assets" / "gen7-icons.png").read_bytes()).decode()
    # One block per evolution edge, so the level or item that causes it sits next to the
    # arrow. A branching family reads "Ralts L20-> Kirlia" then "Kirlia L30-> Gardevoir"
    # and "Kirlia Dawn Stone-> Gallade", which is unambiguous where a flat list was not.
    # Each edge is one unbreakable unit: a wrapped arrow with its level stranded at the end
    # of the previous line read badly on the branching cards.
    chain = '<span class="sep">|</span>'.join(
        "<span class=\"edge\">"
        f'<span class="mini" style="{sprite_style(from_dex, atlas_b64, 2)}"></span>'
        f"{html_escape.escape(from_name)}"
        f'<span class="evo">{html_escape.escape(method)}</span>'
        '<span class="arrow">&rarr;</span>'
        f'<span class="mini" style="{sprite_style(to_dex, atlas_b64, 2)}"></span>'
        f"{html_escape.escape(to_name)}"
        "</span>"
        for from_name, from_dex, method, to_name, to_dex in edges
    )
    blocks = []
    for section in sections:
        rows = []
        for pct, shown, kind, bp, gates in section["rows"]:
            chips = []
            seen_chips: set[str] = set()
            for gate, where in gates:
                if gate in ("level", "reminder"):
                    text = where
                elif gate == "tutor":
                    cost = TUTOR_BP.get(canon(shown))
                    text = f"TUTOR {cost} BP" if cost else "TUTOR"
                elif gate == "unavailable":
                    text = "NOT IN GEN 7"
                else:
                    text = gate.upper()
                if canon(shown) == "hiddenpower" and gate == "TM":
                    text = "TM10 (IVs)"
                # One chip per way of getting it. Without this a move learnable by TM in
                # three forms printed three identical TM chips.
                key = f"{gate}:{text if gate in ('level', 'reminder') else ''}"
                if key in seen_chips:
                    continue
                seen_chips.add(key)
                chips.append(
                    f'<span class="chip" style="background:{GATE_COLOR.get(gate, "#455a64")}">'
                    f"{html_escape.escape(text)}</span>"
                )
            rows.append(
                f'<div class="bar"><i style="width:{max(pct, 0.4):.1f}%"></i></div>'
                f'<div class="pct">{pct:4.1f}%</div>'
                f'<div class="move">{html_escape.escape(shown)}</div>'
                f'<div><span class="chip" style="background:{TYPE_COLOR.get(kind, "#455a64")}">'
                f"{html_escape.escape(kind)}</span></div>"
                f'<div class="bp">{"" if bp in ("0", "-") else html_escape.escape(str(bp)) + " BP"}</div>'
                f'<div class="gates">{" ".join(chips)}</div>'
            )
        stats = (f"Grade {html_escape.escape(str(section.get('grade', '?')))} &middot; "
                 f"{html_escape.escape(str(section.get('smogon_tier', '?')))} &middot; "
                 f"{(section.get('usage') or 0):.2f}% usage")
        blocks.append(
            f'<section>'
            f'<header>'
            f'<span class="hero" style="{sprite_style(section["dex"], atlas_b64, 4)}"></span>'
            f'<span class="titles"><b>{html_escape.escape(section["name"])}</b>'
            f"<em>{stats}</em></span>"
            f"</header>"
            f'<div class="grid">{"".join(rows)}</div>'
            f"</section>"
        )
    legend = " ".join(
        f'<span class="chip" style="background:{GATE_COLOR[g]}">{label}</span>'
        for g, label in (("level", "LEVEL UP"), ("reminder", "MOVE REMINDER (FREE)"),
                         ("TM", "TM"), ("tutor", "TUTOR (BP)"), ("egg", "EGG MOVE"),
                         ("event", "EVENT"), ("unavailable", "NOT LEGAL IN GEN 7"))
    )
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><style>
  body {{ margin:0; padding:26px 30px 22px; background:#0f1117; color:#e9ecf3;
         font-family:"DejaVu Sans",system-ui,sans-serif; font-size:14px; }}
  h1 {{ margin:0 0 4px; font-size:26px; letter-spacing:.2px; }}
  .lineage {{ color:#8b93a7; font-size:13px; display:flex; align-items:center; flex-wrap:wrap; gap:4px; }}
  .mini {{ width:52px; height:39px; display:inline-block; vertical-align:middle; }}
  .edge {{ display:inline-flex; align-items:center; gap:3px; white-space:nowrap; }}
  .evo {{ background:#243043; color:#8fd0ff; border-radius:8px; padding:2px 8px;
          font-size:11.5px; font-weight:700; margin:0 5px; }}
  .sep {{ color:#333c4e; margin:0 10px; }}
  .arrow {{ color:#4a5266; margin:0 4px; }}
  section {{ margin-top:20px; padding-top:14px; border-top:1px solid #232735; }}
  header {{ display:flex; align-items:center; gap:14px; margin-bottom:10px; }}
  .hero {{ width:160px; height:120px; flex:0 0 auto; }}
  .titles b {{ font-size:21px; display:block; }}
  .titles em {{ color:#8b93a7; font-style:normal; font-size:12px; }}
  .grid {{ display:grid; grid-template-columns:170px 56px 152px 78px 62px 1fr;
           gap:5px 10px; align-items:center; }}
  .bar {{ background:#1c212e; height:9px; border-radius:5px; overflow:hidden; }}
  .bar i {{ display:block; height:100%; background:linear-gradient(90deg,#3d6fd6,#59c1e8); }}
  .pct {{ text-align:right; color:#aeb6c8; font-variant-numeric:tabular-nums; }}
  .move {{ font-weight:600; }}
  .bp {{ color:#8b93a7; font-size:12px; }}
  .gates {{ display:flex; flex-wrap:wrap; gap:4px; }}
  .chip {{ display:inline-block; padding:2px 7px; border-radius:9px; color:#fff;
           font-size:11px; font-weight:600; letter-spacing:.2px; white-space:nowrap; }}
  footer {{ margin-top:18px; padding-top:12px; border-top:1px solid #232735;
            color:#8b93a7; font-size:11.5px; line-height:1.7; }}
</style></head><body>
  <h1>{html_escape.escape(base_name)}</h1>
  <div class="lineage">{chain}</div>
  {"".join(blocks)}
  <footer>{legend}<br>
    Usage = share of that Pok&eacute;mon's competitive sets running the move, from
    Smogon's {html_escape.escape(str(sections[0].get("tier", "")))}  moveset file
    (November 2019, Gen 7). Grade and tier are the app's own dex fields.
    Sprites from the app's gen7-icons atlas; tutor costs are the USUM Battle Point prices.
  </footer>
</body></html>"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Move report for a Pokemon family.")
    parser.add_argument("species", help="any member of the family: name, slug or dex number")
    parser.add_argument("--cache", default=os.environ.get("POKE_DATA_CACHE", "/opt/data/poke-data"))
    parser.add_argument("--top", type=int, default=25, help="moves to list per final evolution (default 25)")
    parser.add_argument("--png", help="also render the report to this PNG path")
    parser.add_argument("--all", action="store_true",
                        help="include moves nothing runs (0%%) in the rendered card")
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
    details_by_id = {int(d["id"]): d for d in details}
    id_of = {normalize(r["slug"]): int(r["id"]) for r in rows}
    # How each species is reached, from the app's own evolution data ("Level 25",
    # "Use Dawn Stone"). Keyed by the species that is reached.
    evo_method: dict[str, str] = {}
    for detail in details:
        for step in detail.get("evolution") or []:
            method = str(step.get("method") or "").strip()
            if method and method != "?":
                evo_method[normalize(str(step.get("name", "")))] = method
    parent_of = {
        key: (scalar(body, "prevo") or "").lower().replace(" ", "")
        for key, body in dex.items()
    }

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
    sections: list[dict] = []

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

        detail = details_by_id.get(id_of.get(final, -1)) or {}
        print(f"## {nice.get(final, final)}")
        print(f"   grade {detail.get('grade', '?')} · Smogon {detail.get('tier', '?')} · "
              f"{(detail.get('usage') or 0):.2f}% usage" + (f"   [{label}]" if label else ""))
        print(f"   {LEGEND}")
        card_rows: list[tuple[float, str, str, str, list[tuple[str, str]]]] = []
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
                    cost = TUTOR_BP.get(canon(shown)) if gate == "tutor" else None
                    tags.append(f"{ICON[gate]} {gate}{f' {cost} BP' if cost else ''}")
            print(f"   {pct:5.1f}%  {shown:18} {kind:8} {bp:>4} BP   {' · '.join(dict.fromkeys(tags))}")
            # The card is for reading on a phone, so it carries the shortlist. The text
            # output keeps the 0% rows, which answer "what else can it even learn".
            if pct > 0 or args.all:
                card_rows.append((pct, shown, kind, bp, gates))
        print()
        sections.append({"name": nice.get(final, final), "tier": label,
                         "grade": detail.get("grade") or "?",
                         "smogon_tier": detail.get("tier") or "?",
                         "usage": detail.get("usage"),
                         "dex": id_of.get(final), "rows": card_rows})

    if args.png:
        out = Path(args.png)
        chain = [
            (
                nice.get(parent_of.get(member, ""), parent_of.get(member, "")),
                id_of.get(parent_of.get(member, "")),
                short_method(evo_method.get(member)),
                nice.get(member, member),
                id_of.get(member),
            )
            for member in family[1:]
        ]
        for section in sections:
            # One image per Pokemon: a family with two finals (Gardevoir and Gallade) gets
            # two cards rather than one image nobody can read.
            target = out if len(sections) == 1 else out.with_name(f"{out.stem}-{normalize(section['name'])}.png")
            html_path = Path(tempfile.gettempdir()) / f"moveline-{target.stem}.html"
            html_path.write_text(card_html(entry["name"], chain, [section]))
            subprocess.run(
                ["node", str(REPO / "tools" / "render-png.mjs"), str(html_path), str(target)],
                check=True,
            )
            print(f"wrote {target}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
