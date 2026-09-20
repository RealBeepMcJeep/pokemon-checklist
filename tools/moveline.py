#!/usr/bin/env python3
"""Move report for a Pokemon family: sorted by competitive usage, tagged by how you get it.

Walks a species' evolution lineage (back to the base form, forward through every branch), then
reports each terminal evolution from its own ancestral path. Moves are tagged by how you get them
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
import re
import subprocess
import sys
import tempfile
import unicodedata
import urllib.request
from pathlib import Path
from typing import Mapping

try:
    from .acquisition_data import (
        MOVE_REMINDER_LOCATION,
        PROFILE_LABELS,
        PROFILE_NOTES,
        TUTOR_BP,
        tm_label,
        tutor_label,
    )
    from . import showdown_text as st
    from .showdown_data import ShowdownDataError, configured_cache_dir, require_cache
except ImportError:  # Running the file directly: python tools/moveline.py ...
    from acquisition_data import (  # type: ignore[no-redef]
        MOVE_REMINDER_LOCATION,
        PROFILE_LABELS,
        PROFILE_NOTES,
        TUTOR_BP,
        tm_label,
        tutor_label,
    )
    import showdown_text as st  # type: ignore[no-redef]
    from showdown_data import ShowdownDataError, configured_cache_dir, require_cache  # type: ignore[no-redef]

REPO = Path(__file__).resolve().parent.parent
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
LEGEND = ("\U0001F7E2 level-up · \U0001F501 move reminder (endgame) · \U0001F4C0 TM · "
          "\U0001F393 tutor · \U0001F95A egg · \U0001F381 event")

# Where a species' usage lives, keyed by the tier the app already records for it. A species
# banned from a tier (BL) is used in the tier above, which is the file that holds its stats.
TIER_FILE = {"OU": "ou", "UUBL": "ou", "UU": "uu", "RUBL": "uu", "RU": "ru", "NUBL": "ru",
             "NU": "nu", "PUBL": "nu", "PU": "pu", "LC": "lc", "LC Uber": "lc"}

# Chip colours, keyed by how a move is obtained, then by type.
GATE_COLOR = {"level": "#2e7d32", "reminder": "#00796b", "TM": "#1565c0", "tutor": "#6a1b9a",
              "egg": "#e65100", "event": "#ad1457", "unavailable": "#b71c1c"}
TYPE_COLOR = {"Normal": "#9e9e9e", "Fire": "#e64a19", "Water": "#1976d2", "Electric": "#f9a825",
              "Grass": "#388e3c", "Ice": "#0097a7", "Fighting": "#c2185b", "Poison": "#7b1fa2",
              "Ground": "#8d6e63", "Flying": "#5c6bc0", "Psychic": "#d81b60", "Bug": "#689f38",
              "Rock": "#a1887f", "Ghost": "#512da8", "Dragon": "#303f9f", "Dark": "#455a64",
              "Steel": "#607d8b", "Fairy": "#ec407a"}


def fetch_stats(url: str, dest: Path) -> Path:
    """Download one Smogon usage snapshot to the analysis cache once."""
    if dest.exists() and dest.stat().st_size > 500:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"fetching {url.rsplit('/', 1)[-1]} ...", file=sys.stderr)
    with urllib.request.urlopen(url, timeout=240) as response:
        dest.write_bytes(response.read())
    return dest


top_blocks = st.top_blocks


def list_field(body: str, field: str) -> list[str]:
    return st.list_field(body, field, normalize)


def short_method(method: str | None) -> str:
    """"Level 25" -> "L25", "Use Dawn Stone" -> "Dawn Stone"."""
    if not method:
        return ""
    found = re.match(r"Level (\d+)", method)
    return f"L{found.group(1)}" if found else method.removeprefix("Use ")


class SpeciesInputError(ValueError):
    """A user-facing species lookup failure, never an indexing/parser failure."""


def normalize(name: str) -> str:
    """Normalize slugs, names, and move labels without losing gender markers."""
    value = unicodedata.normalize("NFKC", str(name)).lower()
    value = value.replace("♀", "f").replace("♂", "m")
    return re.sub(r"[^a-z0-9]", "", value)


def resolve_species(raw: str, rows: list[dict]) -> dict:
    """Resolve a number, slug, or display name with a stable, clean error."""
    query = str(raw or "").strip()
    if not query:
        raise SpeciesInputError("no such species: (empty input)")
    by_id = {int(row["id"]): row for row in rows}
    by_slug = {normalize(row.get("slug", "")): row for row in rows}
    by_name = {normalize(row.get("name", "")): row for row in rows}
    entry = by_id.get(int(query)) if query.isdigit() else None
    entry = entry or by_slug.get(normalize(query)) or by_name.get(normalize(query))
    if not entry:
        raise SpeciesInputError(f"no such species: {raw}")
    return entry


def ancestral_path(final: str, parent_of: Mapping[str, str]) -> list[str]:
    """Return only the base-to-final path, even when the family branches."""
    path: list[str] = []
    current = normalize(final)
    seen: set[str] = set()
    while current and current not in seen:
        seen.add(current)
        path.append(current)
        current = normalize(parent_of.get(current, ""))
    return list(reversed(path))


def path_move_union(path: list[str], learned: Mapping[str, dict]) -> dict[str, dict[str, dict[str, list[str]]]]:
    """Union learnsets only along one final evolution's ancestral path."""
    union: dict[str, dict[str, dict[str, list[str]]]] = {}
    for form in path:
        for move, gates in (learned.get(form) or {}).items():
            union.setdefault(move, {})[form] = gates
    return union


def evolution_finals(family: list[str], evos_of: Mapping[str, list[str]]) -> list[str]:
    """Find terminal members without indexing an empty family."""
    members = set(family)
    finals = [form for form in family if not any(child in members for child in evos_of.get(form, []))]
    return finals or ([family[-1]] if family else [])


def selected_finals(selected: str, family: list[str], evos_of: Mapping[str, list[str]]) -> list[str]:
    """Select one terminal branch for direct terminal input, otherwise keep all branches."""
    finals = evolution_finals(family, evos_of)
    candidate = normalize(selected)
    return [candidate] if candidate in finals else finals


def evolution_edges(
    final: str,
    parent_of: Mapping[str, str],
    evo_method: Mapping[str, str],
    id_of: Mapping[str, int],
    nice: Mapping[str, str],
) -> list[tuple[str, int | None, str, str, int | None]]:
    """Return only the rendered evolution edges on one final's ancestral path."""
    path = ancestral_path(final, parent_of)
    return [
        (
            nice.get(parent, parent),
            id_of.get(parent),
            short_method(evo_method.get(member)),
            nice.get(member, member),
            id_of.get(member),
        )
        for parent, member in zip(path, path[1:])
    ]


def lineage_label(finals: list[str], parent_of: Mapping[str, str], nice: Mapping[str, str]) -> str:
    """Describe each selected final's ancestry without flattening sibling branches."""
    return " ; ".join(
        " -> ".join(nice.get(form, form) for form in ancestral_path(final, parent_of))
        for final in finals
    )


def acquisition_gates(
    final: str,
    path: list[str],
    form_gates: Mapping[str, dict[str, list[str]]],
    nice: Mapping[str, str],
) -> list[tuple[str, str]]:
    """Flatten one path's gates and mark moves that must be taught before evolution."""
    final_gates = form_gates.get(final) or {}
    output: list[tuple[str, str]] = []
    for form in path:
        for gate, levels in (form_gates.get(form) or {}).items():
            for level in levels or [""]:
                if gate == "level":
                    actual_gate = "reminder" if level == "1" else "level"
                    detail = f"{nice.get(form, form)} L{level}"
                else:
                    actual_gate = gate
                    detail = nice.get(form, form)
                if form != final and gate not in final_gates:
                    detail = f"TEACH BEFORE EVOLVING: {detail}"
                output.append((actual_gate, detail))
    return output


def display_move_for_usage(
    move_key: str,
    base_name: str,
    base_type: str,
    usage: Mapping[str, float],
) -> tuple[str, str, str]:
    """Preserve Hidden Power's set-specific coverage type while retaining its legal key."""
    if canon(move_key) != "hiddenpower":
        return base_name, base_type, base_type
    variant = next((name for name in usage if canon(name) == "hiddenpower"), "")
    match = re.match(r"Hidden Power\s+(.+)$", variant, re.I)
    coverage = match.group(1).strip().title() if match else base_type
    return (f"Hidden Power {coverage}" if match else base_name, coverage, coverage)


def acquisition_label(gate: str, move_or_where: str, where: str = "", profile: str = "gen7") -> str:
    """Human-readable acquisition label; ``where`` is the originating form/provenance."""
    key = canon(move_or_where)
    prefix_source = where if where.startswith("TEACH BEFORE EVOLVING:") else move_or_where
    prefix = f"{prefix_source} · " if prefix_source.startswith("TEACH BEFORE EVOLVING:") else ""
    if gate in ("level",):
        return move_or_where
    if gate == "reminder":
        return f"{prefix}MOVE REMINDER — {MOVE_REMINDER_LOCATION}"
    if gate == "TM":
        return f"{prefix}{tm_label(key)}"
    if gate == "tutor":
        return f"{prefix}{tutor_label(key)}"
    if gate == "egg":
        note = " — level not specified" if profile == "prismatic-standard" else ""
        return f"{prefix}EGG MOVE{note}"
    if gate == "unavailable":
        return "NOT IN GEN 7"
    return f"{prefix}{gate.upper()}"

def canon(name: str) -> str:
    """Match a stats-file move name to a learnset key."""
    key = normalize(name)
    return "hiddenpower" if key.startswith("hiddenpower") else key


def scalar(body: str, field: str) -> str | None:
    return st.field(body, field)


def lineage(slug: str, dex: dict[str, str]) -> list[str]:
    """Base form first, then every branch forward from it."""
    prevo: dict[str, str] = {}
    evos: dict[str, list[str]] = {}
    for key, body in ((k, b) for k, b in dex.items()):
        p = scalar(body, "prevo")
        if p:
            prevo[normalize(key)] = normalize(p)
        e = list_field(body, "evos")
        if e:
            evos[normalize(key)] = e
    base = normalize(slug)
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
    profile: str = "gen7",
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
                text = acquisition_label(gate, shown if gate not in ("level", "reminder") else where,
                                         where, profile)
                # One chip per way of getting it. Without this a move learnable by TM in
                # three forms printed three identical TM chips.
                key = f"{gate}:{text if gate in ('level', 'reminder') else text}"
                if key in seen_chips:
                    continue
                seen_chips.add(key)
                chips.append(
                    f'<span class="chip" style="background:{GATE_COLOR.get(gate, "#455a64")}">'
                    f"{html_escape.escape(text)}</span>"
                )
            legality = html_escape.escape(canon(shown), quote=True)
            coverage = html_escape.escape(kind, quote=True)
            rows.append(
                f'<div class="move-row">'
                f'<div class="bar"><i style="width:{max(pct, 0.4):.1f}%"></i></div>'
                f'<div class="pct">{pct:4.1f}%</div>'
                f'<div class="move" data-legality-key="{legality}" '
                f'data-coverage-type="{coverage}">{html_escape.escape(shown)}</div>'
                f'<div class="move-type"><span class="chip" style="background:{TYPE_COLOR.get(kind, "#455a64")}">'
                f"{html_escape.escape(kind)}</span></div>"
                f'<div class="bp">{"" if bp in ("0", "-") else html_escape.escape(str(bp)) + " BP"}</div>'
                f'<div class="gates">{" ".join(chips)}</div>'
                f'</div>'
            )
        type_chips = " ".join(
            f'<span class="chip" style="background:{TYPE_COLOR.get(str(kind), "#455a64")}">'
            f"{html_escape.escape(str(kind))}</span>"
            for kind in (section.get("types") or [])
        )
        stats = (f'{type_chips} <span class="tierline">Grade '
                 f"{html_escape.escape(str(section.get('grade', '?')))} &middot; "
                 f"{html_escape.escape(str(section.get('smogon_tier', '?')))} &middot; "
                 f"{(section.get('usage') or 0):.2f}% usage</span>")
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
        for g, label in (("level", "LEVEL UP"), ("reminder", "MOVE REMINDER (ENDGAME)"),
                         ("TM", "TM"), ("tutor", "TUTOR (BP)"), ("egg", "EGG MOVE"),
                         ("event", "EVENT"), ("unavailable", "NOT LEGAL IN GEN 7"))
    )
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><style>
  body {{ margin:0; padding:26px 30px 22px; background:#0f1117; color:#e9ecf3;
         font-family:"DejaVu Sans",system-ui,sans-serif; font-size:14px; overflow-x:hidden; }}
  * {{ box-sizing:border-box; }}
  h1 {{ margin:0 0 4px; font-size:26px; letter-spacing:.2px; }}
  .lineage {{ color:#8b93a7; font-size:13px; display:flex; align-items:center; flex-wrap:wrap; gap:4px; min-width:0; }}
  .mini {{ width:52px; height:39px; display:inline-block; vertical-align:middle; flex:0 0 auto; }}
  .edge {{ display:inline-flex; align-items:center; gap:3px; white-space:nowrap; max-width:100%; }}
  .evo {{ background:#243043; color:#8fd0ff; border-radius:8px; padding:2px 8px;
          font-size:11.5px; font-weight:700; margin:0 5px; }}
  .sep {{ color:#333c4e; margin:0 10px; }}
  .arrow {{ color:#4a5266; margin:0 4px; }}
  section {{ margin-top:20px; padding-top:14px; border-top:1px solid #232735; min-width:0; }}
  header {{ display:flex; align-items:center; gap:14px; margin-bottom:10px; min-width:0; }}
  .hero {{ width:160px; height:120px; flex:0 0 auto; }}
  .titles {{ min-width:0; }}
  .titles b {{ font-size:21px; display:block; }}
  .titles em {{ color:#8b93a7; font-style:normal; font-size:12px; }}
  .tierline {{ color:#8b93a7; }}
  .grid {{ display:flex; flex-direction:column; gap:5px; min-width:0; }}
  .move-row {{ display:grid; grid-template-columns:170px 56px 152px 78px 62px minmax(0, 1fr);
               gap:5px 10px; align-items:center; min-width:0; }}
  .bar {{ background:#1c212e; height:9px; border-radius:5px; overflow:hidden; min-width:0; }}
  .bar i {{ display:block; height:100%; background:linear-gradient(90deg,#3d6fd6,#59c1e8); }}
  .pct {{ text-align:right; color:#aeb6c8; font-variant-numeric:tabular-nums; }}
  .move {{ font-weight:600; min-width:0; overflow-wrap:anywhere; }}
  .move-type, .bp, .gates {{ min-width:0; }}
  .bp {{ color:#8b93a7; font-size:12px; }}
  .gates {{ display:flex; flex-wrap:wrap; gap:4px; }}
  .chip {{ display:inline-block; padding:2px 7px; border-radius:9px; color:#fff;
           font-size:11px; font-weight:600; letter-spacing:.2px; white-space:nowrap; }}
  .gates .chip {{ white-space:normal; overflow-wrap:anywhere; }}
  footer {{ margin-top:18px; padding-top:12px; border-top:1px solid #232735;
            color:#8b93a7; font-size:11.5px; line-height:1.7; overflow-wrap:anywhere; }}
  @media (max-width: 600px) {{
    body {{ padding:16px 12px 18px; font-size:13px; }}
    h1 {{ font-size:22px; }}
    header {{ gap:10px; align-items:flex-start; }}
    .hero {{ width:96px; height:72px; }}
    .titles b {{ font-size:18px; }}
    .titles em {{ font-size:11px; }}
    .move-row {{ grid-template-columns:minmax(0, 1fr) auto; gap:4px 8px; }}
    .bar {{ grid-column:1 / -1; }}
    .move {{ grid-column:1; grid-row:2; }}
    .pct {{ grid-column:2; grid-row:2; }}
    .move-type {{ grid-column:1; grid-row:3; justify-self:start; }}
    .bp {{ grid-column:2; grid-row:3; justify-self:end; }}
    .gates {{ grid-column:1 / -1; grid-row:4; }}
    .chip {{ white-space:normal; overflow-wrap:anywhere; }}
    .mini {{ width:40px; height:30px; }}
    .sep {{ margin:0 4px; }}
  }}
</style></head><body>
  <h1>{html_escape.escape(base_name)}</h1>
  <div class="lineage">{chain}</div>
  {"".join(blocks)}
  <footer>{legend}<br>
    Profile: {html_escape.escape(PROFILE_LABELS.get(profile, profile))}. {html_escape.escape(PROFILE_NOTES.get(profile, ""))}<br>
    Usage = share of that Pok&eacute;mon's competitive sets running the move, from
    Smogon's {html_escape.escape(str(sections[0].get("tier", "") if sections else ""))} moveset file
    (November 2019, Gen 7). Grade and tier are the app's own dex fields.
    Sprites from the app's gen7-icons atlas; tutor costs are the USUM Battle Point prices.
  </footer>
</body></html>"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Move report for a Pokemon family.")
    parser.add_argument("species", help="any member of the family: name, slug or dex number")
    parser.add_argument(
        "--cache",
        default=str(configured_cache_dir()),
        help="verified shared Showdown cache (bootstrap it first)",
    )
    parser.add_argument("--top", type=int, default=25, help="moves to list per final evolution (default 25)")
    parser.add_argument("--png", help="also render the report to this PNG path")
    parser.add_argument("--all", action="store_true",
                        help="include moves nothing runs (0%%) in the rendered card")
    parser.add_argument("--profile", choices=sorted(PROFILE_LABELS), default="gen7",
                        help="acquisition profile (default: gen7)")
    args = parser.parse_args()

    cache = Path(args.cache)
    rows = json.loads((REPO / "data" / "pokemon.json").read_text())
    rows = rows if isinstance(rows, list) else list(rows.values())
    try:
        entry = resolve_species(args.species, rows)
    except SpeciesInputError as error:
        print(str(error), file=sys.stderr)
        return 2

    nice = {normalize(r["slug"]): r["name"] for r in rows}
    try:
        store = require_cache(cache)
        ls_text = store.get_text("learnsets")
        dex_text = store.get_text("pokedex")
        moves_text = store.get_text("moves")
    except ShowdownDataError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

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
        normalize(key): normalize(scalar(body, "prevo") or "")
        for key, body in dex.items()
    }

    raw_family = lineage(entry["slug"], dex)
    # The app's checked-in Gen 7 dex is the compatibility boundary. Current Showdown data
    # can include later regional forms (for example Galar Mr. Mime); do not leak them into a
    # Gen 7 report just because they share a modern Showdown family block.
    family = [form for form in raw_family if form in nice]
    if not family:
        print(f"no learnset lineage for species: {entry['name']}", file=sys.stderr)
        return 2

    learned_by_form = {form: gen7_moves(learned.get(form, "")) for form in family}
    evos_of = {normalize(k): list_field(b, "evos") for k, b in dex.items()}
    finals = selected_finals(entry["slug"], family, evos_of)
    print(f"# {entry['name']} — lineage: {lineage_label(finals, parent_of, nice)}\n", file=sys.stderr)
    sections: list[dict] = []

    for final in finals:
        usage: dict[str, float] = {}
        label = None
        preferred = TIER_FILE.get(tier_of.get(id_of.get(final, -1), ""))
        order = [t for t in TIERS if t[0] == preferred] + [t for t in TIERS if t[0] != preferred]
        for tier, cutoff in order:
            try:
                text = fetch_stats(STATS.format(tier=tier, cutoff=cutoff),
                                   cache / f"moveset-gen7{tier}-{cutoff}.txt").read_text(errors="replace")
            except Exception:
                continue
            got = usage_rows(text, nice.get(final, final))
            if got:
                usage, label = got, f"gen7{tier}-{cutoff}"
                break

        detail = details_by_id.get(id_of.get(final, -1)) or {}
        print(f"## {nice.get(final, final)}")
        types = "/".join(str(t) for t in (detail.get("types") or [])) or "?"
        print(f"   {types} · grade {detail.get('grade', '?')} · Smogon {detail.get('tier', '?')} · "
              f"{(detail.get('usage') or 0):.2f}% usage" + (f"   [{label}]" if label else ""))
        print(f"   {LEGEND}")
        if args.profile == "prismatic-standard":
            print(f"   Profile: {PROFILE_LABELS[args.profile]} — {PROFILE_NOTES[args.profile]}")
        card_rows: list[tuple[float, str, str, str, list[tuple[str, str]]]] = []
        scored = []
        path = ancestral_path(final, parent_of)
        union = path_move_union(path, learned_by_form)
        for move, forms in union.items():
            base_name, base_type, bp = move_meta.get(move, (move, "?", "-"))
            shown, kind, coverage = display_move_for_usage(move, base_name, base_type, usage)
            pct = next((v for k, v in usage.items() if canon(k) == canon(shown)), 0.0)
            gates = acquisition_gates(final, path, forms, nice)
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
            name, base_kind, bp = move_meta[key]
            name, kind, coverage = display_move_for_usage(key, name, base_kind, usage)
            scored.append((pct, len(EASE), name, kind, bp, [("unavailable", "")]))
        scored.sort(key=lambda t: (-t[0], t[1], t[2]))
        if not scored:
            print("   (no Gen 7 moves found)")
        for pct, rank, shown, kind, bp, gates in scored[: args.top]:
            tags = []
            for gate, where in gates:
                acq_label = acquisition_label(gate, shown if gate not in ("level", "reminder") else where,
                                               where, args.profile)
                tags.append(f"{ICON.get(gate, '')} {acq_label}".strip())
            print(f"   {pct:5.1f}%  {shown:18} {kind:8} {bp:>4} BP   {' · '.join(dict.fromkeys(tags))}")
            # The card is for reading on a phone, so it carries the shortlist. The text
            # output keeps the 0% rows, which answer "what else can it even learn".
            if pct > 0 or args.all:
                card_rows.append((pct, shown, kind, bp, gates))
        print()
        sections.append({"name": nice.get(final, final), "tier": label,
                         "types": detail.get("types") or [],
                         "grade": detail.get("grade") or "?",
                         "smogon_tier": detail.get("tier") or "?",
                         "usage": detail.get("usage"),
                         "dex": id_of.get(final), "rows": card_rows})

    if args.png:
        out = Path(args.png).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="moveline-") as temp_dir:
            temp_root = Path(temp_dir)
            for section, final in zip(sections, finals):
                # One image per Pokemon: a family with two finals (Gardevoir and Gallade) gets
                # two cards rather than one image nobody can read.
                target = out if len(sections) == 1 else out.with_name(
                    f"{out.stem}-{normalize(section['name'])}{out.suffix}"
                )
                html_path = temp_root / f"{normalize(section['name'])}.html"
                chain = evolution_edges(final, parent_of, evo_method, id_of, nice)
                html_path.write_text(card_html(entry["name"], chain, [section], args.profile))
                subprocess.run(
                    ["node", str(REPO / "tools" / "render-png.mjs"), str(html_path), str(target),
                     "940", "--assert-no-overflow"],
                    check=True,
                )
                print(f"wrote {target}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
