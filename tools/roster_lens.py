#!/usr/bin/env python3
"""The team-viability lens, deliberately outside the catcher score.

Catcher utility and long-run team value are separate questions, so they are answered by
separate programs. This one takes the catcher algorithm's output and prints it next to each
family's final evolution, grade, tier, usage and base stats, taken from the app's own
data/pokedex-details.json and its Showdown cache.

Nothing here feeds back into the score. Tier and bulk do not change how easily a Pokemon is
caught, and a score that quietly included them would read as catch utility when it was not.
Weigh the two columns side by side and decide.

    python3 tools/roster_lens.py --uid <uid> --top 12
    python3 tools/roster_lens.py --uid <uid> --fleeing --top 8
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
STAT_KEYS = ("hp", "atk", "def", "spa", "spd", "spe")
HEADER = (f"{'pokemon':13}{'caught':>7}  {'final evolution':17}{'grade':>6}{'tier':>6}"
          f"{'usage':>8}   {'HP/Atk/Def/SpA/SpD/Spe':22}")


def base_stats(dex_text: str, name: str) -> str:
    """Base stats of one species, from Showdown's pokedex."""
    block = re.search(rf"^\s*{re.escape(name.lower())}: \{{(.*?)^\s*\}},", dex_text, re.S | re.M)
    if not block:
        return ""
    stats = re.search(r"baseStats: \{([^}]*)\}", block.group(1))
    if not stats:
        return ""
    found = dict(re.findall(r"(\w+): (\d+)", stats.group(1)))
    return "/".join(found.get(key, "?") for key in STAT_KEYS)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--uid", required=True, help="account uid holding the roster")
    parser.add_argument("--cache", default="/opt/data/poke-moves", help="Showdown data cache")
    parser.add_argument("--top", type=int, default=12, help="how many rows to show")
    parser.add_argument("--fleeing", action="store_true", help="pass through to the score")
    parser.add_argument("--exclude", default="", help="pass through to the score")
    args = parser.parse_args()

    cmd = [sys.executable, str(REPO / "tools" / "catcher_score.py"), "--uid", args.uid,
           "--cache", args.cache, "--top", str(args.top)]
    if args.fleeing:
        cmd.append("--fleeing")
    if args.exclude:
        cmd += ["--exclude", args.exclude]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stderr or result.stdout, file=sys.stderr)
        return result.returncode

    rows = json.load(open(REPO / "data" / "pokemon.json"))
    rows = rows if isinstance(rows, list) else list(rows.values())
    id_by_name = {row["name"]: int(row["id"]) for row in rows}
    details = {entry["id"]: entry for entry in
               json.loads((REPO / "data" / "pokedex-details.json").read_text())["species"]}
    dex_text = (Path(args.cache) / "pokedex.ts").read_text(errors="replace")

    print(f"{'catch utility':13}{'score':>7}   {'grade':>5} {'tier':>5} {'usage':>7}  stats")
    for line in result.stdout.splitlines():
        hit = re.match(r"^\s*(\d+\.\d+)\s+(\S+)", line)
        if not hit:
            continue
        score, name = float(hit.group(1)), hit.group(2)
        entry = details.get(id_by_name.get(name, -1), {})
        final = entry.get("source", "?")
        usage = entry.get("usage")
        usage = f"{float(usage):.2f}%" if isinstance(usage, (int, float)) else "n/a"
        print(f"{name:13}{score:7.1f}   {str(entry.get('grade', '?')):>5} "
              f"{str(entry.get('tier', '?')):>5} {usage:>7}  {base_stats(dex_text, final)}"
              f"   ({final})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
