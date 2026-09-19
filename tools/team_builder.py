#!/usr/bin/env python3
"""Pick five keepers and one utility catcher from the caught roster.

Two questions, two answers, deliberately separate:

* the KEEPERS are a tier-and-type question - rank the caught lines by the app's tier, then
  usage, and take the best ones that do not share a type, because a team of five Normal-types
  is worse than the sum of its usage numbers;
* the CATCHER is a utility question, answered by tools/catcher_score.py, which measures how
  soon and how reliably a line can sleep or paralyse something. Tier plays no part in it.

    python3 tools/team_builder.py --uid <uid>
    python3 tools/team_builder.py --uid <uid> --off-limits magnemite,litten,riolu,abra,pichu

`--off-limits` takes species or slugs of the whole line (the boy's team); it matches the base
form, the slug or the final evolution's name. `--cache` defaults to the retained data dir.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TIER_ORDER = ["OU", "UUBL", "UU", "RUBL", "RU", "NUBL", "NU", "PUBL", "PU", "(PU)", "LC Uber", "LC"]
STAT_KEYS = ("hp", "atk", "def", "spa", "spd", "spe")


def read_records(uid: str) -> dict:
    out = subprocess.run(["node", str(REPO / "tools" / "firebase-admin-rest.mjs"),
                          "--read", f"/users/{uid}/state/records"],
                         capture_output=True, text=True, cwd=REPO)
    if out.returncode != 0:
        raise SystemExit(f"could not read the account: {(out.stderr or out.stdout).strip()[:200]}")
    return json.loads(out.stdout or "null") or {}


def block(dex: str, name: str) -> str:
    # Showdown keys regional forms without the hyphen: mukalola, raticatealola, raichualola.
    key = name.lower().replace("-", "").replace(" ", "")
    m = re.search(rf"^\s*{re.escape(key)}: \{{(.*?)^\s*\}},", dex, re.S | re.M)
    return m.group(1) if m else ""


def types_of(dex: str, name: str) -> list[str]:
    m = re.search(r"types: \[(.*?)\]", block(dex, name))
    return re.findall(r"\"([A-Z][a-z]+)\"", m.group(1)) if m else []


def stats_of(dex: str, name: str) -> str:
    m = re.search(r"baseStats: \{([^}]*)\}", block(dex, name))
    if not m:
        return ""
    found = dict(re.findall(r"(\w+): (\d+)", m.group(1)))
    return "/".join(found.get(key, "?") for key in STAT_KEYS)


def abilities_of(dex: str, name: str) -> str:
    """Slots matter: H is the hidden one, which a normal wild catch cannot have."""
    m = re.search(r"abilities: \{(.*?)\}", block(dex, name), re.S)
    if not m:
        return ""
    pairs = re.findall(r"[\'\"]?([01H])[\'\"]?: [\'\"]([^\'\"]+)[\'\"]", m.group(1))
    return ", ".join(f"{n}(H)" if slot == "H" else n for slot, n in pairs)


def evo_of(dex: str, name: str) -> str:
    body = block(dex, name)
    bits = []
    level = re.search(r"evoLevel: (\d+)", body)
    item = re.search(r"evoItem: \"([^\"]+)\"", body)
    kind = re.search(r"evoType: \"([^\"]+)\"", body)
    if level:
        bits.append(f"L{level.group(1)}")
    if kind:
        bits.append(kind.group(1))
    if item:
        bits.append(item.group(1))
    return ", ".join(bits) or "-"


def load_world(cache: Path):
    """Everything the row description needs: the app's dex, the Showdown dex, and the forms."""
    details = json.loads((REPO / "data" / "pokedex-details.json").read_text())
    det = {int(e["id"]): e for e in details["species"]}
    rows = json.load(open(REPO / "data" / "pokemon.json"))
    rows = rows if isinstance(rows, list) else list(rows.values())
    by_id = {int(r["id"]): r for r in rows}          # id -> the whole record
    dex = (cache / "pokedex.ts").read_text(errors="replace")
    # forms: dedupe by source name, preferring the row with the more complete type list
    form_row: dict[str, dict] = {}
    for entry in details.get("forms", {}).values():
        if not isinstance(entry, dict) or not entry.get("source"):
            continue
        name = entry["source"]
        if name not in form_row or len(entry.get("types") or []) > len(form_row[name].get("types") or []):
            form_row[name] = entry
    return det, by_id, form_row, dex


def describe_line(dex_id: int, det: dict, by_id: dict, form_row: dict, dex: str) -> dict:
    """The row matching what he actually owns, preferring the regional form the game gives."""
    base = det.get(dex_id) or {}
    final = base.get("source") or by_id[dex_id]["name"]
    row, alolan = base, False
    alt = form_row.get(f"{final}-Alola")
    if alt:
        row, final, alolan = alt, alt["source"], True
    # The app's species row carries the BASE form's typing (Bunnelby is Normal, Diggersby is
    # Normal/Ground; Rowlet is Grass/Flying, Decidueye is Grass/Ghost). Always take typing from
    # the final evolution and only fall back to the app's row.
    types = types_of(dex, final) or row.get("types") or []
    return {"id": dex_id, "as": by_id[dex_id]["name"], "slug": by_id[dex_id].get("slug", ""),
            "final": final, "types": types, "grade": row.get("grade"),
            "tier": row.get("tier"), "usage": row.get("usage") or 0, "alolan": alolan,
            "stats": stats_of(dex, final), "abilities": abilities_of(dex, final),
            "evo": evo_of(dex, final),
            "rank": TIER_ORDER.index(row["tier"]) if row.get("tier") in TIER_ORDER else 99}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--uid", required=True)
    parser.add_argument("--cache", default="/opt/data/poke-data")
    parser.add_argument("--keep", type=int, default=5)
    parser.add_argument("--off-limits", default="",
                        help="comma-separated species/slugs to exclude (the boy's team)")
    parser.add_argument("--show-all", action="store_true", help="print the whole pool")
    args = parser.parse_args()

    cache = Path(args.cache)
    det, by_id, form_row, dex = load_world(cache)
    describe = lambda dex_id: describe_line(dex_id, det, by_id, form_row, dex)  # noqa: E731

    off = {s.strip().lower() for s in args.off_limits.split(",") if s.strip()}

    records = read_records(args.uid)
    caught = sorted(int(k.split(":")[1]) for k, v in records.items()
                    if k.startswith("species:") and v.get("s") == "caught")
    pool, excluded = [], []
    for dex_id in caught:
        line = describe(dex_id)
        keys = {line["as"].lower(), line["slug"].lower(), line["final"].lower()}
        if keys & off:
            excluded.append(line)
        else:
            pool.append(line)
    pool.sort(key=lambda r: (r["rank"], -r["usage"]))

    if args.show_all:
        print(f"=== pool: {len(pool)} lines ({len(caught)} caught) ===")
        for line in pool:
            print(f"  #{line['id']:03d} {line['as']:12} -> {line['final']:15} "
                  f"{'/'.join(line['types']):16} {str(line['grade']):>3} {str(line['tier']):>5} "
                  f"{line['usage']:5.2f}%  evo {line['evo']:14} {line['abilities']}")

    # greedy: best available line whose types are all new
    keepers, used, rejected = [], set(), []
    for line in pool:
        if len(keepers) == args.keep:
            break
        clash = used & set(line["types"])
        if clash:
            rejected.append((line, f"shares {'/'.join(sorted(clash))}"))
            continue
        keepers.append(line)
        used |= set(line["types"])

    print(f"\n=== {len(keepers)} keepers (tier first, then usage, no shared types) ===")
    print(f"{'score':>0} {'caught as':12}{'-> final':16}{'types':17}{'grade':>6}{'tier':>7}"
          f"{'usage':>8}  {'stats':22}evolution")
    for line in keepers:
        print(f"{'':0} {line['as']:12}{'-> ' + line['final']:16}{'/'.join(line['types']):17}"
              f"{str(line['grade']):>6}{str(line['tier']):>7}{line['usage']:>7.2f}%  "
              f"{line['stats']:22}{line['evo']}")
        print(f"{'':32}abilities: {line['abilities']}")

    print(f"\n=== catcher, from catcher_score.py (utility, tier plays no part) ===")
    score = subprocess.run([sys.executable, str(REPO / "tools" / "catcher_score.py"),
                            "--uid", args.uid, "--cache", args.cache, "--top", "3"],
                           capture_output=True, text=True, cwd=REPO)
    for line in (score.stdout or score.stderr).splitlines()[:6]:
        print("  " + line.rstrip())

    if excluded:
        print(f"\n=== off limits ({len(excluded)}) ===")
        for line in sorted(excluded, key=lambda r: (r["rank"], -r["usage"])):
            print(f"  {line['final']:15} {str(line['tier']):>5} {line['usage']:5.2f}%")
    if rejected:
        print("\n=== next best, and why not ===")
        for line, reason in rejected[:6]:
            print(f"  {line['final']:15} {str(line['tier']):>5} {line['usage']:5.2f}%  ({reason})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
