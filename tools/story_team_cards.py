#!/usr/bin/env python3
"""Render five phone-readable, offline Pokémon team PNGs from live story options.

Examples:
  python tools/story_team_cards.py --uid <firebase-uid> --cache <showdown-cache> --output-dir <dir>
  python tools/story_team_cards.py --report-json <saved-report.json> --output-dir <dir>
The latter re-renders an existing snapshot without contacting Firebase.
"""
from __future__ import annotations

import argparse
import copy
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
ATLAS = ROOT / "assets/gen7-icons.png"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
SIZE = (1260, 2120)
ROW_TOP, ROW_STEP, ROW_HEIGHT = 269, 274, 265
FRAME = (40, 30)
COLS = 32
PALETTE = {
    "Normal": "#b9b9b1", "Fire": "#f18759", "Water": "#72b9f4",
    "Electric": "#f2cf69", "Grass": "#80d398", "Ice": "#8ee2e6",
    "Fighting": "#eb8279", "Poison": "#c694da", "Ground": "#e3ba80",
    "Flying": "#9ba9eb", "Psychic": "#f5a3bd", "Bug": "#c6d672",
    "Rock": "#cfbd83", "Ghost": "#a994d9", "Dragon": "#8683ef",
    "Dark": "#a2a0b9", "Steel": "#a3c5d5", "Fairy": "#e9a9d3",
}
BG, PANEL, WHITE, DIM, LINE = "#0c1223", "#172238", "#f6f5ee", "#aebbd0", "#35445a"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(BOLD if bold else FONT, size)


def sprite(atlas: Image.Image, dex: int, scale: int) -> Image.Image:
    if not 1 <= dex <= 807 or atlas.size != (1280, 780):
        raise ValueError(f"no Gen VII atlas icon for dex #{dex} (atlas {atlas.size})")
    ix = dex - 1
    x, y = (ix % COLS) * FRAME[0], (ix // COLS) * FRAME[1]
    return atlas.crop((x, y, x + FRAME[0], y + FRAME[1])).resize(
        (FRAME[0] * scale, FRAME[1] * scale), Image.Resampling.NEAREST)


def fit(draw: ImageDraw.ImageDraw, text: str, face: ImageFont.FreeTypeFont,
        max_width: int, *, strict: bool = False) -> str:
    if draw.textlength(text, font=face) <= max_width:
        return text
    if strict:
        raise ValueError(f"essential card text does not fit ({max_width}px): {text}")
    while text and draw.textlength(text + "…", font=face) > max_width:
        text = text[:-1]
    return text.rstrip() + "…"

def wrapped_lines(draw: ImageDraw.ImageDraw, text: str, face: ImageFont.FreeTypeFont,
                  width: int, max_lines: int = 2) -> list[str]:
    """Wrap essential text without truncating words, bounded by the row geometry."""
    lines = []
    current = ''
    for word in text.split():
        fit(draw, word, face, width, strict=True)
        candidate = f'{current} {word}'.strip()
        if current and draw.textlength(candidate, font=face) > width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    if len(lines) > max_lines:
        raise ValueError(f'essential card text needs more than {max_lines} lines: {text}')
    return lines


def card_title(option: dict) -> str:
    if option["category"] != "Mixed":
        return option["category"].upper()
    partner = next((m["final"] for m in option["members"]
                    if m["final"] != option["anchor"]), None)
    if partner is None:
        raise ValueError("a mixed card needs a partner distinct from its anchor")
    return f"{option['anchor'].upper()} + {partner.upper()}"


def blurb(option: dict) -> str:
    labels = {
        "OG": "Original-151 battlers only",
        "Non-OG": "No original-151 battlers",
        "Mixed": "Unrestricted Dex range",
        "Pokedex": f"Pure level-only Pokédex path · {option.get('new_entries', 0)} new entries",
        "Best": "Buildable endgame heuristic",
    }
    label = labels.get(option["category"], "Story team")
    return (f"{label} · {option.get('evolving', 0)}/5 can still evolve · "
            f"{option.get('level_evolving', 0)}/5 by level")


def add_move_targets(report: dict, cache: Path | None) -> dict:
    """Enrich a read-only snapshot once; later offline renders reuse the frozen gates."""
    enriched = copy.deepcopy(report)
    if (len(enriched.get("utility_moves", [])) == 4 and
            all(len(m.get("moves", [])) == 4 for o in enriched["options"]
                for m in o.get("members", []))):
        return enriched
    if cache is None:
        raise ValueError("an unenriched report needs --cache for verified move sources")
    import story_moves
    source = story_moves.MoveSources(cache)
    enriched["utility_moves"] = source.targets(enriched["utility"], enriched["utility"])
    for option in enriched["options"]:
        for member in option.get("members", []):
            member["moves"] = source.targets(member["final"], member["owned"])
    return enriched


def render_card(report: dict, option: dict, number: int, atlas: Image.Image, output: Path,
                *, generated: str) -> None:
    members = list(option.get("members", []))
    if len(members) != 5 or len({m["dex"] for m in members}) != 5:
        raise ValueError("each card needs five distinct battlers")
    if any(m["dex"] == report["utility_dex"] for m in members):
        raise ValueError("catcher may not occupy a battler slot")
    if len(report.get("utility_moves", [])) != 4 or any(len(m.get("moves", [])) != 4 for m in members):
        raise ValueError("each Pokémon needs four acquisition-checked move targets")
    rows = [{"owned": report["utility"], "final": report["utility"],
             "owned_dex": report["utility_dex"], "dex": report["utility_dex"],
             "types": ["Bug", "Flying"], "evolution": "Sleep / catching utility · fixed slot",
             "tier": "UTILITY", "favorite": True, "moves": report["utility_moves"]},
            *sorted(members, key=lambda m: (m["final"] != option["anchor"], m["final"]))]
    canvas = Image.new("RGB", SIZE, BG)
    d = ImageDraw.Draw(canvas)
    accent = {"OG": "#d6b969", "Non-OG": "#7dcbd5", "Mixed": "#c19ce8",
              "Pokedex": "#80d398", "Best": "#f18759"}.get(option["category"], "#c19ce8")
    d.rounded_rectangle((26, 25, 1234, 2108), radius=34, fill=PANEL, outline=LINE, width=2)
    d.rounded_rectangle((48, 44, 346, 82), radius=18, fill=accent)
    d.text((65, 49), f"{option['category'].upper()}  /  {number:02d} OF 05", fill=BG, font=font(20, True))
    d.text((52, 103), fit(d, card_title(option), font(45, True), 1135, strict=True),
           fill=WHITE, font=font(45, True))
    d.text((54, 170), fit(d, blurb(option), font(22), 1140, strict=True), fill=DIM, font=font(22))
    d.line((50, 215, 1210, 215), fill=LINE, width=2)
    d.text((58, 233), "OWNED → ENDGAME  /  FOUR MOVE TARGETS + HOW TO GET THEM", font=font(18, True), fill=DIM)
    d.text((917, 233), "TYPE", font=font(18, True), fill=DIM)
    d.text((1128, 233), "DEX", font=font(18, True), fill=DIM)
    for idx, m in enumerate(rows):
        y = ROW_TOP + idx * ROW_STEP
        catcher = idx == 0
        anchor = m["final"] == option["anchor"] and not catcher
        role = "CATCHER" if catcher else ("ANCHOR" if anchor else "PARTNER")
        color = "#76d2b7" if catcher else (accent if anchor else DIM)
        d.rounded_rectangle((50, y, 1210, y + ROW_HEIGHT), radius=17,
                            fill="#213452" if anchor else "#1b2a43", outline=color if anchor else LINE,
                            width=2 if anchor else 1)
        d.rounded_rectangle((64, y + 9, 177, y + 34), radius=10, fill=color)
        d.text((74, y + 9), role, font=font(14, True), fill=BG)
        owned_icon = sprite(atlas, int(m["owned_dex"]), 3)
        canvas.paste(owned_icon, (65, y + 39), owned_icon)
        if m["owned_dex"] != m["dex"]:
            final_icon = sprite(atlas, int(m["dex"]), 3)
            canvas.paste(final_icon, (190, y + 39), final_icon)
        x = 326
        label = m["owned"] if m["owned"] == m["final"] else f"{m['owned']} → {m['final']}"
        d.text((x, y + 18), fit(d, label, font(29, True), 570, strict=True),
               font=font(29, True), fill=WHITE)
        evolution = m["evolution"] if not catcher else "Sleep utility · cannot use False Swipe"
        for line_index, line in enumerate(wrapped_lines(d, evolution, font(19), 570)):
            d.text((x, y + 57 + line_index * 22), line, font=font(19), fill=DIM)
        badges = m.get("tier", "")
        if m.get("favorite") and not catcher:
            badges += "  ·  FAVORITE"
        if m.get("hidden_ability_caveat") and not catcher:
            share = m.get("hidden_ability_usage_share")
            badges += (f"  ·  H USAGE {share:.0%}" if share is not None else "  ·  H NOT ASSUMED")
        d.text((x, y + 105), fit(d, badges, font(18, True), 570, strict=True),
               font=font(18, True), fill=color)
        for t_index, typ in enumerate(m["types"]):
            ty = y + 28 + t_index * 47
            shade = PALETTE.get(typ, DIM)
            d.rounded_rectangle((912, ty, 1103, ty + 35), radius=10, fill=shade)
            d.text((927, ty + 3), typ.upper(), fill=BG, font=font(18, True))
        d.text((1126, y + 47), f"#{int(m['dex']):03d}", font=font(21, True), fill=WHITE)
        d.line((76, y + 137, 1185, y + 137), fill=LINE, width=1)
        for move_index, move in enumerate(m["moves"]):
            col, subrow = move_index % 2, move_index // 2
            mx, my = 76 + 573 * col, y + 148 + 52 * subrow
            typ = str(move["type"])
            d.text((mx, my), fit(d, str(move["name"]), font(24, True), 345, strict=True),
                   fill=WHITE, font=font(24, True))
            d.rounded_rectangle((mx + 381, my - 2, mx + 511, my + 30), radius=8,
                                fill=PALETTE.get(typ, DIM))
            d.text((mx + 389, my + 2), fit(d, typ.upper(), font(16, True), 114, strict=True),
                   font=font(16, True), fill=BG)
            d.text((mx, my + 31), fit(d, str(move["gate"]), font(18), 515, strict=True),
                   font=font(18), fill=DIM)
    y = 1934
    d.line((54, y, 1206, y), fill=LINE, width=2)
    d.text((56, y + 12), f"ANCHOR  {option['anchor'].upper()}     •     {option['evolving']}/5 CAN ADD ENTRIES     •     {option['level_evolving']}/5 BY LEVEL", font=font(20, True), fill=accent)
    d.text((56, y + 51), f"TYPE SYNERGY {option['core_synergy']:.2f} / WITH BUTTERFREE {option['six_synergy']:.2f}     ·     {report['caught_records']} CAUGHT", font=font(19, True), fill=WHITE)
    d.text((56, y + 86), "MOVES: Prismatic Standard + Gen VII · LATER / ENDGAME = progression gate.", font=font(18), fill=DIM)
    d.text((56, y + 111), "Scores use type potential, not these moves. Items and abilities unrecorded.", font=font(18), fill=DIM)
    d.text((56, y + 140), f"{generated} Phoenix · local, read-only roster report · Butterfree cannot False Swipe", font=font(17), fill=DIM)
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output, optimize=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uid", help="Firebase account UID (read-only live roster)")
    parser.add_argument("--cache", help="verified Gen VII Showdown cache")
    parser.add_argument("--no-result-cache", action="store_true",
                        help="bypass live story selection cache")
    parser.add_argument("--report-json", type=Path, help="render an existing --story-options --json snapshot")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.report_json:
        report = json.loads(args.report_json.read_text(encoding="utf-8"))
    else:
        if not args.uid or not args.cache:
            parser.error("live render requires --uid and --cache")
        command = [sys.executable, str(ROOT / "tools/team_synergy.py"), "--story-options", "--json",
                   "--uid", args.uid, "--cache", args.cache]
        if args.no_result_cache:
            command.append("--no-result-cache")
        result = subprocess.run(command, cwd=ROOT, check=True, capture_output=True, text=True)
        report = json.loads(result.stdout)
    if len(report.get("options", [])) != 5:
        raise ValueError("the selector did not return five options")
    report = add_move_targets(report, Path(args.cache) if args.cache else None)
    atlas = Image.open(ATLAS).convert("RGBA")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(ZoneInfo("America/Phoenix")).strftime("%b %-d, %Y · %-I:%M %p")
    for number, option in enumerate(report["options"], 1):
        output = args.output_dir / f"team-{number:02d}.png"
        render_card(report, option, number, atlas, output, generated=stamp)
        print(f"{number}: {output} ({output.stat().st_size} bytes)")
    snapshot = args.output_dir / "story-options.json"
    snapshot.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"snapshot: {snapshot}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
