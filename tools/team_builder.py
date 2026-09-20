#!/usr/bin/env python3
"""Build a canonical, form-aware roster from caught records and rank keepers.

The roster pass deliberately separates account records from competitive candidates: every caught
stage is expanded to reachable terminal endpoints, then endpoint/form candidates are deduplicated.
Source names remain attached to each candidate so a result never hides which records supported it.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Iterable

from showdown_data import configured_cache_dir, require_cache
from showdown_text import array_field, block, field, integer_field, list_field, object_after

REPO = Path(__file__).resolve().parent.parent
TIER_ORDER = ["Uber", "OU", "UUBL", "UU", "RUBL", "RU", "NUBL", "NU", "PUBL", "PU", "(PU)", "LC Uber", "LC"]
TIER_RANK = {tier: index for index, tier in enumerate(TIER_ORDER)}
STAT_KEYS = ("hp", "atk", "def", "spa", "spd", "spe")


def normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def normalise_tier(value: str | None) -> str | None:
    if value is None:
        return None
    wanted = str(value).strip().lower()
    for tier in TIER_ORDER:
        if tier.lower() == wanted:
            return tier
    raise ValueError(f"unknown tier {value!r}; choose one of {', '.join(TIER_ORDER)}")


def tier_rank(tier: str | None) -> int:
    normalized = normalise_tier(tier) if tier else None
    return TIER_RANK.get(normalized or "", len(TIER_ORDER) + 1)


def tier_passes(tier: str | None, minimum: str | None) -> bool:
    return minimum is None or tier_rank(tier) <= tier_rank(minimum)


def validate_keep(value: int) -> None:
    if value < 1:
        raise ValueError("--keep must be at least 1")


def read_records(uid: str) -> dict:
    out = subprocess.run(
        ["node", str(REPO / "tools" / "firebase-admin-rest.mjs"), "--read", f"/users/{uid}/state/records"],
        capture_output=True,
        text=True,
        cwd=REPO,
    )
    if out.returncode != 0:
        raise RuntimeError(f"could not read the account: {(out.stderr or out.stdout).strip()[:300]}")
    try:
        value = json.loads(out.stdout or "null") or {}
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"could not decode the account response: {exc}") from exc
    if not isinstance(value, dict):
        raise RuntimeError("could not read the account: records response was not an object")
    return value


def types_of(dex: str, name: str) -> list[str]:
    return array_field(block(dex, name), "types")


def stats_of(dex: str, name: str) -> str:
    stats = object_after(block(dex, name), "baseStats")
    if not stats:
        return ""
    found = dict(re.findall(r"(\w+): (\d+)", stats))
    return "/".join(found.get(key, "?") for key in STAT_KEYS)


def abilities_of(dex: str, name: str) -> str:
    """Slots matter: H is the hidden one, which a normal wild catch cannot have."""
    abilities = object_after(block(dex, name), "abilities")
    if not abilities:
        return ""
    pairs = re.findall(r"[\'\"]?([01H])[\'\"]?: [\'\"]([^\'\"]+)[\'\"]", abilities)
    return ", ".join(f"{name}(H)" if slot == "H" else name for slot, name in pairs)


def evo_of(dex: str, name: str) -> str:
    body = block(dex, name)
    bits = []
    level = integer_field(body, "evoLevel")
    item = field(body, "evoItem")
    kind = field(body, "evoType")
    if level:
        bits.append(f"L{level}")
    if kind:
        bits.append(kind)
    if item:
        bits.append(item)
    return ", ".join(bits) or "-"


def expand_off_limits(tokens: set[str], dex: str) -> set[str]:
    """A token bans its whole line, including pre- and post-evolution names."""
    seen: set[str] = set()
    queue = [token for token in tokens if token]
    while queue:
        current = normalize(queue.pop())
        if not current or current in seen:
            continue
        seen.add(current)
        body = block(dex, current)
        previous = field(body, "prevo")
        if previous:
            queue.append(previous)
        queue.extend(list_field(body, "evos"))
    return seen


def load_world(cache: Path):
    """Load the app snapshot and Showdown snapshot used by both team commands."""
    details = json.loads((REPO / "data" / "pokedex-details.json").read_text())
    det = {int(entry["id"]): entry for entry in details["species"]}
    rows = json.loads((REPO / "data" / "pokemon.json").read_text())
    rows = rows if isinstance(rows, list) else list(rows.values())
    by_id = {int(row["id"]): row for row in rows}
    dex = require_cache(cache).get_text("pokedex")
    form_row: dict[str, dict] = {}
    for entry in details.get("forms", {}).values():
        if not isinstance(entry, dict) or not entry.get("source"):
            continue
        name = entry["source"]
        if name not in form_row or len(entry.get("types") or []) > len(form_row[name].get("types") or []):
            form_row[name] = entry
    return det, by_id, form_row, dex


def _path_names(entry: dict) -> list[str]:
    values = entry.get("evolution") or []
    return [str(item.get("name")) for item in values if isinstance(item, dict) and item.get("name")]


def reachable_endpoint_ids(caught_id: int, det: dict, by_id: dict) -> list[int]:
    """Return terminal records whose recorded path contains the caught species.

    The app snapshot has one terminal record per competitive endpoint. This handles branching
    paths (for example Ralts -> Gardevoir/Gallade) without treating intermediate records as
    separate team members.
    """
    caught = by_id.get(caught_id) or {}
    caught_names = {normalize(caught.get("name", ""))}
    source = det.get(caught_id, {}).get("source")
    if source:
        caught_names.add(normalize(source))
    endpoints: list[int] = []
    for endpoint_id, entry in det.items():
        path = _path_names(entry)
        endpoint_name = normalize(entry.get("source") or (by_id.get(endpoint_id) or {}).get("name", ""))
        if path and normalize(path[-1]) == endpoint_name and caught_names.intersection(normalize(name) for name in path):
            endpoints.append(endpoint_id)
    if not endpoints:
        for endpoint_id, entry in det.items():
            endpoint_name = normalize(entry.get("source") or (by_id.get(endpoint_id) or {}).get("name", ""))
            if endpoint_name in caught_names and not _path_names(entry):
                endpoints.append(endpoint_id)
    if not endpoints and caught_id in det:
        endpoints.append(caught_id)
    # There can be duplicate snapshot records for a form. Prefer the highest id for each endpoint
    # name; the candidate still retains all caught ids after canonicalization.
    chosen: dict[str, int] = {}
    for endpoint_id in endpoints:
        name = normalize(det[endpoint_id].get("source") or by_id.get(endpoint_id, {}).get("name", ""))
        chosen[name] = max(chosen.get(name, 0), endpoint_id)
    return sorted(chosen.values())


def _form_override_for(overrides: dict[str, str] | None, names: Iterable[str]) -> str | None:
    if not overrides:
        return None
    for name in names:
        if normalize(name) in overrides:
            return overrides[normalize(name)]
    return None


def describe_line(
    dex_id: int,
    det: dict,
    by_id: dict,
    form_row: dict,
    dex: str,
    form_overrides: dict[str, str] | None = None,
) -> dict:
    """Describe a terminal endpoint, retaining explicit form assumptions."""
    base = det.get(dex_id) or {}
    base_name = (by_id.get(dex_id) or {}).get("name", "")
    final = base.get("source") or base_name
    assumptions: list[str] = []
    warnings: list[str] = []
    override = _form_override_for(form_overrides, (final, base_name))
    row, selected, form_kind = base, final, "base"
    alt = form_row.get(f"{final}-Alola")
    if override:
        wanted = normalize(override)
        if wanted in {"alola", "alolan"} and alt:
            row, selected, form_kind = alt, alt["source"], "alolan"
        elif wanted in {"base", "kanto", "normal"}:
            row, selected, form_kind = base, final, "base"
        elif normalize(override) == normalize(final):
            row, selected, form_kind = base, final, "base"
        else:
            exact = next((candidate for candidate in form_row.values()
                          if normalize(candidate.get("source", "")) == wanted), None)
            if exact:
                row, selected, form_kind = exact, exact["source"], "override"
            else:
                warnings.append(f"unresolved form override {override!r} for {final}; base form retained")
    elif alt:
        row, selected, form_kind = alt, alt["source"], "alolan"
        assumptions.append(f"form assumed: {selected} (use --form-override {final}=base to override)")
    types = types_of(dex, selected) or row.get("types") or []
    tier = row.get("tier")
    if tier not in TIER_RANK:
        warnings.append(f"unresolved tier for {selected!r}; ranked last")
    return {
        "id": dex_id,
        "endpoint_id": dex_id,
        "as": base_name or final,
        "slug": (by_id.get(dex_id) or {}).get("slug", ""),
        "final": selected,
        "types": types,
        "grade": row.get("grade"),
        "tier": tier,
        "usage": row.get("usage") or 0,
        "alolan": form_kind == "alolan" or normalize(selected).endswith("alola"),
        "form_kind": form_kind,
        "form_assumptions": assumptions,
        "warnings": warnings,
        "stats": stats_of(dex, selected),
        "abilities": abilities_of(dex, selected),
        "evo": evo_of(dex, selected),
        "rank": tier_rank(tier),
    }


def _lineage_ids(endpoint_id: int, det: dict, by_id: dict) -> list[int]:
    names = _path_names(det.get(endpoint_id) or {})
    names += [det.get(endpoint_id, {}).get("source", "")]
    found = []
    for name in names:
        wanted = normalize(name)
        found.extend(i for i, row in by_id.items() if normalize(row.get("name", "")) == wanted)
    return sorted(set(found)) or [endpoint_id]


def canonicalize_roster(
    caught_ids: Iterable[int],
    det: dict,
    by_id: dict,
    form_row: dict,
    dex: str,
    form_overrides: dict[str, str] | None = None,
) -> list[dict]:
    """Collapse caught stages to one candidate per reachable endpoint/form."""
    grouped: dict[tuple[str, tuple[str, ...]], dict] = {}
    for caught_id in sorted(set(caught_ids)):
        caught_name = (by_id.get(caught_id) or {}).get("name", str(caught_id))
        for endpoint_id in reachable_endpoint_ids(caught_id, det, by_id):
            line = describe_line(endpoint_id, det, by_id, form_row, dex, form_overrides)
            line["lineage_ids"] = _lineage_ids(endpoint_id, det, by_id)
            line["caught_ids"] = [caught_id]
            line["caught_as"] = [caught_name]
            line["source_names"] = [caught_name]
            key = (normalize(line["final"]), tuple(line["types"]))
            existing = grouped.get(key)
            if existing is None:
                grouped[key] = line
            else:
                existing["caught_ids"] = sorted(set(existing["caught_ids"]) | {caught_id})
                existing["caught_as"] = sorted(set(existing["caught_as"]) | {caught_name})
                existing["source_names"] = existing["caught_as"][:]
                existing["form_assumptions"] = sorted(set(existing["form_assumptions"]) | set(line["form_assumptions"]))
                existing["warnings"] = sorted(set(existing["warnings"]) | set(line["warnings"]))
    return sorted(grouped.values(), key=lambda line: (line["rank"], -line["usage"], line["final"]))


def allowed_by_gen1(candidate: dict, keep_alolan: bool = False) -> bool:
    """Apply --no-gen1 to the whole lineage, not just the caught record's dex id."""
    final = normalize(candidate.get("final", ""))
    if final == "butterfree":
        return True
    if candidate.get("alolan") and keep_alolan:
        return True
    return not any(int(identifier) <= 151 for identifier in candidate.get("lineage_ids", []))


def parse_form_overrides(value: str | None) -> dict[str, str]:
    result: dict[str, str] = {}
    for token in (value or "").split(","):
        token = token.strip()
        if not token:
            continue
        if "=" not in token:
            raise ValueError("--form-override entries must use name=form")
        name, form = (part.strip() for part in token.split("=", 1))
        if not name or not form:
            raise ValueError("--form-override entries must use name=form")
        result[normalize(name)] = form
    return result


def filter_roster(
    candidates: list[dict],
    off_limits: set[str] | None = None,
    *,
    no_gen1: bool = False,
    keep_alolan: bool = False,
    min_tier: str | None = None,
) -> tuple[list[dict], list[tuple[dict, str]]]:
    minimum = normalise_tier(min_tier)
    banned = {normalize(token) for token in (off_limits or set())}
    kept, excluded = [], []
    for candidate in candidates:
        names = set(map(normalize, candidate.get("caught_as", [])))
        names.update(map(normalize, (candidate.get("as", ""), candidate.get("slug", ""), candidate.get("final", ""))))
        if names & banned:
            excluded.append((candidate, "off limits"))
        elif no_gen1 and not allowed_by_gen1(candidate, keep_alolan):
            excluded.append((candidate, "Gen 1 lineage"))
        elif not tier_passes(candidate.get("tier"), minimum):
            excluded.append((candidate, f"below {minimum}"))
        else:
            kept.append(candidate)
    return kept, excluded


def load_roster(
    uid: str,
    cache: Path,
    *,
    off_limits: str = "",
    no_gen1: bool = False,
    keep_alolan: bool = False,
    min_tier: str | None = None,
    form_overrides: dict[str, str] | None = None,
) -> dict:
    """Shared account loading, canonicalization, and filtering for both team tools."""
    det, by_id, form_row, dex = load_world(cache)
    records = read_records(uid)
    caught_ids = sorted({int(key.split(":", 1)[1]) for key, value in records.items()
                         if key.startswith("species:") and isinstance(value, dict) and value.get("s") == "caught"})
    candidates = canonicalize_roster(caught_ids, det, by_id, form_row, dex, form_overrides)
    expanded = expand_off_limits({normalize(token) for token in off_limits.split(",") if token.strip()}, dex)
    pool, excluded = filter_roster(candidates, expanded, no_gen1=no_gen1, keep_alolan=keep_alolan, min_tier=min_tier)
    warnings = sorted({warning for candidate in candidates for warning in candidate.get("warnings", [])})
    assumptions = sorted({assumption for candidate in candidates for assumption in candidate.get("form_assumptions", [])})
    return {
        "records": records,
        "caught_count": len(caught_ids),
        "canonical_count": len(candidates),
        "candidates": candidates,
        "pool": pool,
        "excluded": excluded,
        "warnings": warnings,
        "assumptions": assumptions,
        "limitations": [
            "ability availability is inferred from the Showdown snapshot; caught abilities are not recorded",
            "evolution reachability is inferred from the app lineage; sex, trade, item, and hack-specific gates are not verified",
        ],
        "det": det,
        "by_id": by_id,
        "form_row": form_row,
        "dex": dex,
    }


def _run_catcher(uid: str, cache: str) -> str:
    result = subprocess.run(
        [sys.executable, str(REPO / "tools" / "catcher_score.py"), "--uid", uid, "--cache", cache, "--top", "3"],
        capture_output=True,
        text=True,
        cwd=REPO,
    )
    if result.returncode != 0:
        raise RuntimeError(f"catcher_score failed: {(result.stderr or result.stdout).strip()[:300]}")
    return result.stdout or result.stderr


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--uid", required=True)
    parser.add_argument(
        "--cache",
        default=str(configured_cache_dir()),
        help="verified shared Showdown cache (bootstrap it first)",
    )
    parser.add_argument("--keep", type=int, default=5)
    parser.add_argument("--min-tier", default=None, help=f"drop lines worse than this tier ({', '.join(TIER_ORDER)})")
    parser.add_argument("--off-limits", default="", help="comma-separated species/slugs to exclude")
    parser.add_argument("--form-override", default="", help="comma-separated name=form entries, such as vulpix=alolan")
    parser.add_argument("--show-all", action="store_true", help="print the whole pool")
    args = parser.parse_args()
    try:
        validate_keep(args.keep)
        minimum = normalise_tier(args.min_tier)
        overrides = parse_form_overrides(args.form_override)
        roster = load_roster(args.uid, Path(args.cache), off_limits=args.off_limits, min_tier=minimum,
                             form_overrides=overrides)
        pool = sorted(roster["pool"], key=lambda line: (line["rank"], -line["usage"], line["final"]))
        catcher = _run_catcher(args.uid, args.cache)
    except (RuntimeError, ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(f"=== roster: {roster['caught_count']} caught records -> {roster['canonical_count']} endpoint/form candidates ===")
    print(f"pool: {len(pool)} candidates after filters; canonicalization removes duplicate caught stages")
    for message in roster["assumptions"] + roster["warnings"] + roster["limitations"]:
        print(f"note: {message}")
    if args.show_all:
        print(f"=== pool: {len(pool)} candidates ===")
        for line in pool:
            print(f"  {line['final']:15} from {', '.join(line['caught_as']):18} {'/'.join(line['types']):16} "
                  f"{str(line['tier']):>7} {line['usage']:5.2f}% evo {line['evo']:14} {line['abilities']}")

    keepers, used, rejected = [], set(), []
    for line in pool:
        if len(keepers) == args.keep:
            break
        clash = used & set(line["types"])
        if clash:
            rejected.append((line, f"shares {'/'.join(sorted(clash))}"))
            continue
        keepers.append(line)
        used.update(line["types"])

    print(f"\n=== {len(keepers)} keepers (tier first, then usage, no shared types) ===")
    print(f"{'caught as':18}{'-> final':16}{'types':17}{'grade':>6}{'tier':>7}{'usage':>8}  {'stats':22}evolution")
    for line in keepers:
        print(f"{', '.join(line['caught_as']):18}-> {line['final']:13}{'/'.join(line['types']):17}"
              f"{str(line['grade']):>6}{str(line['tier']):>7}{line['usage']:>7.2f}%  {line['stats']:22}{line['evo']}")
        print(f"{'':34}abilities: {line['abilities']}")

    print("\n=== catcher, from catcher_score.py (utility, tier plays no part) ===")
    for line in catcher.splitlines()[:6]:
        print("  " + line.rstrip())
    if roster["excluded"]:
        print(f"\n=== excluded ({len(roster['excluded'])}) ===")
        for line, reason in sorted(roster["excluded"], key=lambda item: (item[0]["rank"], -item[0]["usage"])):
            print(f"  {line['final']:15} {str(line['tier']):>7} {line['usage']:5.2f}% ({reason})")
    if rejected:
        print("\n=== next best, and why not ===")
        for line, reason in rejected[:6]:
            print(f"  {line['final']:15} {str(line['tier']):>7} {line['usage']:5.2f}% ({reason})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
