#!/usr/bin/env python3
"""Render five phone-readable, offline Pokémon team PNGs from live story options.

Examples:
  python tools/story_team_cards.py --uid <firebase-uid> --cache <showdown-cache> --output-dir <dir>
  python tools/story_team_cards.py --report-json <saved-report.json> --output-dir <dir>
The latter re-renders an existing snapshot without contacting Firebase.
"""
from __future__ import annotations

import argparse
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
SIZE = (1260, 1360)
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


def fit(draw: ImageDraw.ImageDraw, text: str, face: ImageFont.FreeTypeFont, max_width: int) -> str:
    if draw.textlength(text, font=face) <= max_width:
        return text
    while text and draw.textlength(text + "…", font=face) > max_width:
        text = text[:-1]
    return text.rstrip() + "…"


def blurb(option: dict) -> str:
    if option["category"] == "OG-151":
        return "Kanto-only challenge · stones and friendship needed · lower-tier fillers"
    if option["category"] == "No OG-151":
        return "All five battlers evolve by level · strongest low-friction progression pick"
    return "Mixed roster · type balance, late-game potential and evolution opportunities"


def render_card(report: dict, option: dict, number: int, atlas: Image.Image, output: Path,
                *, generated: str) -> None:
    members = list(option.get("members", []))
    if len(members) != 5 or len({m["dex"] for m in members}) != 5:
        raise ValueError("each card needs five distinct battlers")
    if any(m["dex"] == report["utility_dex"] for m in members):
        raise ValueError("catcher may not occupy a battler slot")
    rows = [{"owned": report["utility"], "final": report["utility"],
             "owned_dex": report["utility_dex"], "dex": report["utility_dex"],
             "types": ["Bug", "Flying"], "evolution": "Sleep / catching utility · fixed slot",
             "tier": "UTILITY", "favorite": True},
            *sorted(members, key=lambda m: (m["final"] != option["anchor"], m["final"]))]
    canvas = Image.new("RGB", SIZE, BG)
    d = ImageDraw.Draw(canvas)
    accent = "#d6b969" if option["category"] == "OG-151" else (
        "#7dcbd5" if option["category"] == "No OG-151" else "#c19ce8")
    d.rounded_rectangle((26, 25, 1234, 1328), radius=34, fill=PANEL, outline=LINE, width=2)
    d.rounded_rectangle((48, 44, 346, 82), radius=18, fill=accent)
    d.text((65, 49), f"STORY TEAM  /  {number:02d} OF 05", fill=BG, font=font(20, True))
    d.text((52, 103), option["category"].upper(), fill=WHITE, font=font(45, True))
    d.text((54, 170), fit(d, blurb(option), font(22), 1140), fill=DIM, font=font(22))
    d.line((50, 215, 1210, 215), fill=LINE, width=2)
    d.text((58, 233), "OWNED → ENDGAME  /  EVOLUTION PATH", font=font(18, True), fill=DIM)
    d.text((917, 233), "TYPE", font=font(18, True), fill=DIM)
    d.text((1128, 233), "DEX", font=font(18, True), fill=DIM)
    for idx, m in enumerate(rows):
        y = 269 + idx * 151
        catcher = idx == 0
        anchor = m["final"] == option["anchor"] and not catcher
        role = "CATCHER" if catcher else ("ANCHOR" if anchor else "PARTNER")
        color = "#76d2b7" if catcher else (accent if anchor else DIM)
        d.rounded_rectangle((50, y, 1210, y + 139), radius=17,
                            fill="#213452" if anchor else "#1b2a43", outline=color if anchor else LINE,
                            width=2 if anchor else 1)
        d.rounded_rectangle((64, y + 9, 177, y + 34), radius=10, fill=color)
        d.text((74, y + 9), role, font=font(14, True), fill=BG)
        canvas.paste(sprite(atlas, int(m["owned_dex"]), 2), (69, y + 40),
                     sprite(atlas, int(m["owned_dex"]), 2))
        if m["owned_dex"] != m["dex"]:
            canvas.paste(sprite(atlas, int(m["dex"]), 2), (169, y + 53),
                         sprite(atlas, int(m["dex"]), 2))
            d.text((151, y + 69), "→", font=font(19, True), fill=color)
        x = 274
        label = m["owned"] if m["owned"] == m["final"] else f"{m['owned']} → {m['final']}"
        d.text((x, y + 18), fit(d, label, font(27, True), 600), font=font(27, True), fill=WHITE)
        evolution = m["evolution"] if not catcher else "Sleep utility · cannot use False Swipe"
        d.text((x, y + 61), fit(d, evolution, font(18), 606), font=font(18), fill=DIM)
        badges = m.get("tier", "")
        if m.get("favorite") and not catcher:
            badges += "  ·  IN PARTY"
        d.text((x, y + 98), badges, font=font(17, True), fill=color)
        for t_index, typ in enumerate(m["types"]):
            ty = y + 28 + t_index * 47
            shade = PALETTE.get(typ, DIM)
            d.rounded_rectangle((912, ty, 1103, ty + 35), radius=10, fill=shade)
            d.text((927, ty + 3), typ.upper(), fill=BG, font=font(18, True))
        d.text((1126, y + 47), f"#{int(m['dex']):03d}", font=font(21, True), fill=WHITE)
    y = 1187
    d.line((54, y, 1206, y), fill=LINE, width=2)
    d.text((56, y + 12), f"ANCHOR  {option['anchor'].upper()}     •     {option['evolving']}/5 EVOLVABLE     •     {option['level_evolving']}/5 LEVEL-BASED", font=font(20, True), fill=accent)
    d.text((56, y + 51), f"5-BATTLER SCORE {option['core_score']:.2f}  /  WITH BUTTERFREE {option['six_score']:.2f}     ·     {report['caught_records']} CAUGHT", font=font(17, True), fill=WHITE)
    d.text((56, y + 88), "STAB type-potential heuristic, not a verified moveset. Ability, sex and items unrecorded.", font=font(16), fill=DIM)
    d.text((56, y + 116), f"Prismatic Moon Standard · {generated} Phoenix · local, read-only roster report", font=font(15), fill=DIM)
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output, optimize=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uid", help="Firebase account UID (read-only live roster)")
    parser.add_argument("--cache", help="verified Gen VII Showdown cache")
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
        result = subprocess.run(command, cwd=ROOT, check=True, capture_output=True, text=True)
        report = json.loads(result.stdout)
    if len(report.get("options", [])) != 5:
        raise ValueError("the selector did not return five options")
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
