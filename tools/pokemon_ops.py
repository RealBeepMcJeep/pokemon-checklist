#!/usr/bin/env python3
"""Deterministic, read-before-write checklist workflows for chat operations.

This module is deliberately the only Python entry point for multi-record chat
changes.  It resolves names from the checked-in National Dex, validates the
Realtime Database record schema, computes a minimal patch, applies at most one
atomic patch, and verifies the exact values written by reading them back.

Examples::

    python tools/pokemon_ops.py --uid UID list caught
    python tools/pokemon_ops.py --uid UID mark pikachu caught
    python tools/pokemon_ops.py --uid UID evolve pikachu raichu
    python tools/pokemon_ops.py --uid UID favorites --exact pikachu mewtwo

No reset or delete operation is intentionally exposed here.
"""
from __future__ import annotations

import argparse
import copy
import json
import re
import subprocess
import sys
import unicodedata
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

ROOT = Path(__file__).resolve().parent.parent
POKEMON_PATH = ROOT / "data" / "pokemon.json"
FIREBASE_TOOL = ROOT / "tools" / "firebase-admin-rest.mjs"

Species = dict[str, Any]
RecordMap = dict[str, dict[str, Any]]

STATUS_VALUES = frozenset({"none", "seen", "caught"})
STAR_VALUES = frozenset({"on", "off"})
MODE_VALUES = frozenset({"photonic-prismatic", "sun", "moon", "ultra-sun", "ultra-moon"})
_KEY_RE = re.compile(r"^(species|star):([1-9][0-9]*)$")


class OperationError(Exception):
    """A requested operation cannot be performed safely."""


class SchemaError(OperationError):
    """A database record or requested value is outside the known schema."""


class UnknownSpeciesError(OperationError):
    """A name or National Dex number did not resolve."""


class AmbiguousSpeciesError(OperationError):
    """A name matched more than one species."""


class VerificationError(OperationError):
    """The database did not return the exact value just written."""


def normalize(value: str) -> str:
    """Normalize names exactly as the app and chat parser do."""
    decomposed = unicodedata.normalize("NFD", value)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]", "", stripped.lower())


def load_species(path: Path = POKEMON_PATH) -> list[Species]:
    """Load and validate the deterministic species catalogue."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        for key in ("species", "pokemon", "pokedex"):
            if isinstance(payload.get(key), list):
                payload = payload[key]
                break
    if not isinstance(payload, list):
        raise SchemaError("pokemon.json must contain a list of species")

    result: list[Species] = []
    ids: set[int] = set()
    slugs: set[str] = set()
    for raw in payload:
        if not isinstance(raw, dict) or "id" not in raw or "name" not in raw:
            raise SchemaError("every species must have id and name")
        try:
            species_id = int(raw["id"])
        except (TypeError, ValueError) as exc:
            raise SchemaError("species ids must be integers") from exc
        name = str(raw["name"]).strip()
        slug = str(raw.get("slug") or normalize(name)).strip()
        if species_id <= 0 or not name or not slug:
            raise SchemaError("species has an invalid id, name, or slug")
        if species_id in ids or slug in slugs:
            raise SchemaError("pokemon.json contains duplicate species ids or slugs")
        ids.add(species_id)
        slugs.add(slug)
        result.append({"id": species_id, "name": name, "slug": slug})
    if not result:
        raise SchemaError("pokemon.json contains no species")
    return sorted(result, key=lambda item: int(item["id"]))


def resolve_species(query: str, species: Sequence[Species]) -> Species:
    """Resolve one name/slug/number; prefixes are accepted only when unique."""
    text = str(query).strip().lstrip("#").strip()
    needle = normalize(text)
    if not needle:
        raise UnknownSpeciesError("a species name or National Dex number is required")

    if needle.isdigit():
        matches = [item for item in species if int(item["id"]) == int(needle)]
    else:
        exact = [
            item for item in species
            if normalize(str(item["name"])) == needle or normalize(str(item["slug"])) == needle
        ]
        matches = exact or [
            item for item in species if normalize(str(item["name"])).startswith(needle)
        ]

    if len(matches) == 1:
        return dict(matches[0])
    if len(matches) > 1:
        names = ", ".join(str(item["name"]) for item in matches[:8])
        raise AmbiguousSpeciesError(f"{text!r} is ambiguous: {names}")
    raise UnknownSpeciesError(f"could not resolve species {text!r}")


def _valid_key(key: str, species_ids: set[int]) -> str:
    if not isinstance(key, str):
        raise SchemaError("record keys must be strings")
    match = _KEY_RE.fullmatch(key)
    if match:
        kind, raw_id = match.groups()
        species_id = int(raw_id)
        if species_id not in species_ids:
            raise SchemaError(f"unknown species record key: {key}")
        return kind
    if key.startswith("form:") and len(key) > len("form:") and "/" not in key:
        return "form"
    if key == "setting:mode":
        return "setting:mode"
    if key == "setting:forms":
        return "setting:forms"
    raise SchemaError(f"unknown record key: {key}")


def _allowed_value(kind: str) -> frozenset[str]:
    if kind in {"species", "form"}:
        return STATUS_VALUES
    if kind == "star" or kind == "setting:forms":
        return STAR_VALUES
    if kind == "setting:mode":
        return MODE_VALUES
    raise SchemaError(f"unknown record kind: {kind}")


def validate_record_map(records: Mapping[str, Any] | None, species_ids: Iterable[int]) -> RecordMap:
    """Validate a Firebase ``state/records`` snapshot and return a copy.

    Existing sync metadata is tolerated only in its known fields (``s``, ``at``
    and ``by``); unknown record fields and unknown keys fail closed.
    """
    if records is None:
        return {}
    if not isinstance(records, Mapping):
        raise SchemaError("state/records must be an object or null")
    ids = {int(value) for value in species_ids}
    checked: RecordMap = {}
    for key, raw in records.items():
        kind = _valid_key(key, ids)
        if not isinstance(raw, Mapping):
            raise SchemaError(f"record {key} must be an object")
        unknown_fields = set(raw) - {"s", "at", "by"}
        if unknown_fields:
            raise SchemaError(f"record {key} has unknown fields: {sorted(unknown_fields)}")
        value = raw.get("s")
        if not isinstance(value, str) or value not in _allowed_value(kind):
            raise SchemaError(f"record {key} has invalid value {value!r}")
        if "at" in raw and not (
            isinstance(raw["at"], (int, float)) and not isinstance(raw["at"], bool)
        ):
            # A fake/test transport may retain the server-value sentinel before
            # Firebase resolves it; permit only that exact sentinel shape.
            if raw["at"] != {".sv": "timestamp"}:
                raise SchemaError(f"record {key} has invalid at")
        if "by" in raw and not isinstance(raw["by"], str):
            raise SchemaError(f"record {key} has invalid by")
        checked[str(key)] = copy.deepcopy(dict(raw))
    return checked


def validate_requested_patch(patch: Mapping[str, str], species_ids: Iterable[int]) -> dict[str, str]:
    """Validate a patch before it can reach an external transport."""
    ids = {int(value) for value in species_ids}
    result: dict[str, str] = {}
    for key, value in patch.items():
        kind = _valid_key(key, ids)
        if not isinstance(value, str) or value not in _allowed_value(kind):
            raise SchemaError(f"invalid requested value {value!r} for {key}")
        result[key] = value
    return result


def _empty_value(key: str) -> str:
    return "off" if key.startswith("star:") else "none"


def record_value(records: Mapping[str, Mapping[str, Any]], key: str) -> str:
    entry = records.get(key)
    return str(entry["s"]) if entry is not None else _empty_value(key)


def minimal_patch(records: Mapping[str, Mapping[str, Any]], desired: Mapping[str, str]) -> dict[str, str]:
    """Return only changed keys, preserving the caller's deterministic order."""
    return {key: value for key, value in desired.items() if record_value(records, key) != value}


class FirebaseClient:
    """Small subprocess transport for the dependency-free Node admin wrapper."""

    def __init__(self, tool: Path = FIREBASE_TOOL, node: str = "node", runner: Any = None):
        self.tool = Path(tool)
        self.node = node
        self.runner = runner or subprocess.run

    def _run(self, args: list[str]) -> Any:
        completed = self.runner(
            [self.node, str(self.tool), *args],
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            message = (completed.stderr or completed.stdout or "firebase command failed").strip()
            raise OperationError(message)
        try:
            return json.loads(completed.stdout or "null")
        except json.JSONDecodeError as exc:
            raise OperationError("firebase wrapper returned invalid JSON") from exc

    def read_records(self, uid: str) -> Mapping[str, Any] | None:
        return self._run(["--read", f"/users/{uid}/state/records"])

    def apply_records(self, uid: str, records: Mapping[str, str], note: str = "") -> Any:
        return self._run([
            "--apply", "--uid", uid, "--record", json.dumps(records, sort_keys=True),
            "--note", note,
        ])


def _read_checked(client: Any, uid: str, species: Sequence[Species]) -> RecordMap:
    raw = client.read_records(uid)
    return validate_record_map(raw, {int(item["id"]) for item in species})


def _apply_verified(
    client: Any,
    uid: str,
    current: RecordMap,
    desired: Mapping[str, str],
    species: Sequence[Species],
    *,
    dry_run: bool = False,
    note: str = "",
) -> dict[str, Any]:
    ids = {int(item["id"]) for item in species}
    checked_desired = validate_requested_patch(desired, ids)
    changes = minimal_patch(current, checked_desired)
    result: dict[str, Any] = {
        "changed": bool(changes),
        "changes": changes,
        "dry_run": bool(dry_run),
    }
    if not changes or dry_run:
        return result

    # Exactly one transport call is made for a multi-key workflow. The wrapper
    # turns it into one Firebase PATCH, not one request per record.
    client.apply_records(uid, changes, note=note)
    after = _read_checked(client, uid, species)
    for key, expected in changes.items():
        if key not in after or after[key].get("s") != expected:
            actual = after.get(key, {}).get("s", "<missing>")
            raise VerificationError(
                f"readback mismatch for {key}: expected {expected!r}, got {actual!r}"
            )
    result["verified"] = True
    return result


def _with_operation(result: dict[str, Any], operation: str, **extra: Any) -> dict[str, Any]:
    return {"operation": operation, **extra, **result}


def run_mark(
    client: Any,
    uid: str,
    name: str,
    status: str,
    species: Sequence[Species] | None = None,
    *,
    dry_run: bool = False,
    note: str = "",
) -> dict[str, Any]:
    if status not in STATUS_VALUES:
        raise OperationError(f"invalid status {status!r}; expected caught, seen, or none")
    catalogue = list(species) if species is not None else load_species()
    target = resolve_species(name, catalogue)
    current = _read_checked(client, uid, catalogue)
    key = f"species:{int(target['id'])}"
    result = _apply_verified(
        client, uid, current, {key: status}, catalogue, dry_run=dry_run, note=note or f"chat mark {target['name']}",
    )
    return _with_operation(result, "mark", species=target, status=status)


def run_pair(
    client: Any,
    uid: str,
    operation: str,
    from_name: str,
    to_name: str,
    species: Sequence[Species] | None = None,
    *,
    dry_run: bool = False,
    note: str = "",
) -> dict[str, Any]:
    if operation not in {"evolve", "trade"}:
        raise OperationError("pair operation must be evolve or trade")
    catalogue = list(species) if species is not None else load_species()
    source = resolve_species(from_name, catalogue)
    target = resolve_species(to_name, catalogue)
    if int(source["id"]) == int(target["id"]):
        raise OperationError("FROM and TO must resolve to different species")
    current = _read_checked(client, uid, catalogue)
    desired = {
        f"species:{int(source['id'])}": "seen",
        f"species:{int(target['id'])}": "caught",
    }
    result = _apply_verified(
        client, uid, current, desired, catalogue, dry_run=dry_run,
        note=note or f"chat {operation} {source['name']} to {target['name']}",
    )
    return _with_operation(result, operation, from_species=source, to_species=target)


def run_favorites_exact(
    client: Any,
    uid: str,
    names: Sequence[str],
    species: Sequence[Species] | None = None,
    *,
    dry_run: bool = False,
    note: str = "",
) -> dict[str, Any]:
    if not names:
        raise OperationError("favorites --exact requires at least one species")
    catalogue = list(species) if species is not None else load_species()
    targets = [resolve_species(name, catalogue) for name in names]
    target_ids = {int(item["id"]) for item in targets}
    current = _read_checked(client, uid, catalogue)
    current_ids = {
        int(key.split(":", 1)[1])
        for key, entry in current.items()
        if key.startswith("star:") and entry.get("s") == "on"
    }
    desired: dict[str, str] = {}
    for species_id in sorted(current_ids - target_ids):
        desired[f"star:{species_id}"] = "off"
    for species_id in sorted(target_ids - current_ids):
        desired[f"star:{species_id}"] = "on"
    result = _apply_verified(
        client, uid, current, desired, catalogue, dry_run=dry_run,
        note=note or "chat exact favorites",
    )
    return _with_operation(result, "favorites", exact=list(sorted(target_ids)), species=targets)


def run_list(
    client: Any,
    uid: str,
    category: str,
    species: Sequence[Species] | None = None,
) -> dict[str, Any]:
    if category not in {"caught", "seen-only", "favorites"}:
        raise OperationError("invalid list category; expected caught, seen-only, or favorites")
    catalogue = list(species) if species is not None else load_species()
    current = _read_checked(client, uid, catalogue)
    items: list[dict[str, Any]] = []
    for target in catalogue:
        species_id = int(target["id"])
        status = record_value(current, f"species:{species_id}")
        starred = record_value(current, f"star:{species_id}") == "on"
        include = (
            status == "caught" if category == "caught" else
            status == "seen" if category == "seen-only" else starred
        )
        if include:
            items.append({"id": species_id, "name": target["name"], "slug": target["slug"], "status": status, "favorite": starred})
    return {"operation": "list", "category": category, "items": items}


def _add_common_flags(parser: argparse.ArgumentParser, *, suppress_defaults: bool = False) -> None:
    default = argparse.SUPPRESS if suppress_defaults else None
    parser.add_argument("--uid", required=not suppress_defaults, default=default, help="Firebase account uid")
    parser.add_argument("--json", action="store_true", default=default, help="emit machine-readable JSON")
    parser.add_argument("--dry-run", action="store_true", default=default, help="show the patch without writing")
    parser.add_argument("--note", default=default, help="audit note for the write")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    _add_common_flags(parser)
    commands = parser.add_subparsers(dest="command", required=True)

    list_parser = commands.add_parser("list", help="list caught, seen-only, or favorite species")
    _add_common_flags(list_parser, suppress_defaults=True)
    list_parser.add_argument("category", choices=("caught", "seen-only", "favorites"))

    mark_parser = commands.add_parser("mark", help="mark one species")
    _add_common_flags(mark_parser, suppress_defaults=True)
    mark_parser.add_argument("name")
    mark_parser.add_argument("status", choices=tuple(sorted(STATUS_VALUES)))

    for operation in ("evolve", "trade"):
        pair_parser = commands.add_parser(operation, help=f"mark FROM seen and TO caught atomically")
        _add_common_flags(pair_parser, suppress_defaults=True)
        pair_parser.add_argument("from_name", metavar="FROM")
        pair_parser.add_argument("to_name", metavar="TO")

    favorites_parser = commands.add_parser("favorites", help="reconcile favorites")
    _add_common_flags(favorites_parser, suppress_defaults=True)
    favorites_parser.add_argument("--exact", nargs="+", metavar="NAME", required=True)
    return parser


def _print_result(result: Mapping[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return
    if result.get("operation") == "list":
        for item in result["items"]:
            suffix = " [favorite]" if item.get("favorite") else ""
            print(f"#{int(item['id']):03d} {item['name']} ({item['status']}){suffix}")
        print(f"{len(result['items'])} species")
        return
    changes = result.get("changes", {})
    if not changes:
        print("No changes required.")
    elif result.get("dry_run"):
        print("Dry run; would change: " + ", ".join(f"{key}={value}" for key, value in changes.items()))
    else:
        print("Changed: " + ", ".join(f"{key}={value}" for key, value in changes.items()))


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    species = load_species()
    client = FirebaseClient()
    try:
        if args.command == "list":
            result = run_list(client, args.uid, args.category, species)
        elif args.command == "mark":
            result = run_mark(client, args.uid, args.name, args.status, species, dry_run=args.dry_run, note=args.note or "")
        elif args.command in {"evolve", "trade"}:
            result = run_pair(client, args.uid, args.command, args.from_name, args.to_name, species, dry_run=args.dry_run, note=args.note or "")
        elif args.command == "favorites":
            result = run_favorites_exact(client, args.uid, args.exact, species, dry_run=args.dry_run, note=args.note or "")
        else:  # argparse makes this unreachable, but keeps the dispatch total.
            raise OperationError(f"unknown command {args.command}")
    except OperationError as exc:
        if args.json:
            print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        else:
            print(f"error: {exc}", file=sys.stderr)
        return 1
    _print_result(result, args.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
