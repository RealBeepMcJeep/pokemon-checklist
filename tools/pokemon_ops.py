#!/usr/bin/env python3
"""Deterministic, read-before-write checklist workflows for chat operations.

This module is deliberately the only Python entry point for multi-record chat
changes.  It resolves names from the checked-in National Dex, validates the
Realtime Database record schema, computes a minimal patch, applies at most one
atomic patch, and verifies the exact values written by reading them back.

Examples::

    python tools/pokemon_ops.py --uid UID list caught
    python tools/pokemon_ops.py --uid UID status pikachu
    python tools/pokemon_ops.py --uid UID set-status pikachu caught --old-status seen
    python tools/pokemon_ops.py --uid UID mark pikachu caught
    python tools/pokemon_ops.py --uid UID evolve totodile
    python tools/pokemon_ops.py --uid UID evolve pikachu raichu
    python tools/pokemon_ops.py --uid UID favorites --exact pikachu mewtwo

Omit TO for a unique next evolution from local Gen VII data. Branches require a
choice; terminal or unresolved paths make no account changes. Explicit FROM TO
remains available. No reset or delete operation is intentionally exposed here.
"""
from __future__ import annotations

import argparse
import copy
import difflib
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


class EvolutionChoiceRequired(OperationError):
    """Several species can be next; caller must choose before account I/O."""

    def __init__(self, source: Species, candidates: Sequence[Species]) -> None:
        self.source = dict(source)
        self.candidates = [dict(item) for item in candidates]
        names = ", ".join(item["name"] for item in self.candidates)
        super().__init__(f"{source['name']} has multiple next evolutions: {names}; specify TO")


class SchemaError(OperationError):
    """A database record or requested value is outside the known schema."""


class UnknownSpeciesError(OperationError):
    """A name or National Dex number did not resolve."""


class AmbiguousSpeciesError(OperationError):
    """A name matched more than one species."""


class VerificationError(OperationError):
    """The database did not return the exact value just written."""


class StatusPreconditionError(OperationError):
    """The live status no longer matches a caller-supplied expectation."""


UNSET = object()


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


def suggest_species(query: str, species: Sequence[Species], *, limit: int = 3) -> list[str]:
    """Suggest nearby canonical names without resolving or correcting the input."""
    needle = normalize(str(query))
    if not needle or needle.isdigit():
        return []
    aliases: dict[str, str] = {}
    for item in species:
        name = str(item["name"])
        aliases.setdefault(normalize(name), name)
        aliases.setdefault(normalize(str(item["slug"])), name)
    matches = difflib.get_close_matches(needle, list(aliases), n=limit, cutoff=0.55)
    return list(dict.fromkeys(aliases[match] for match in matches))


def resolve_species(query: str, species: Sequence[Species]) -> Species:
    """Resolve an exact normalized name/slug/number; never guess a prefix."""
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
        matches = exact

    if len(matches) == 1:
        return dict(matches[0])
    if len(matches) > 1:
        names = ", ".join(str(item["name"]) for item in matches[:8])
        raise AmbiguousSpeciesError(f"{text!r} is ambiguous: {names}")
    prefixes = [
        item for item in species
        if normalize(str(item["name"])).startswith(needle)
        or normalize(str(item["slug"])).startswith(needle)
    ]
    if len(prefixes) > 1:
        names = ", ".join(str(item["name"]) for item in prefixes[:8])
        raise AmbiguousSpeciesError(f"{text!r} is not an exact species name; possible matches: {names}")
    suggestions = suggest_species(text, species)
    hint = f"; possible corrections: {', '.join(suggestions)}" if suggestions else ""
    raise UnknownSpeciesError(f"could not resolve exact species name {text!r}{hint}")


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
            # A real Firebase GET always resolves the `{".sv":"timestamp"}` sentinel
            # to a number before returning it, so a record read back with the raw
            # sentinel still attached is never valid; do not special-case it here.
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


def caught_count(records: Mapping[str, Mapping[str, Any]]) -> int:
    return sum(
        key.startswith("species:") and entry.get("s") == "caught"
        for key, entry in records.items()
    )


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
        return self._run(["--read-records", "--uid", uid])

    def apply_records(
        self,
        uid: str,
        records: Mapping[str, str],
        note: str = "",
        expected: Mapping[str, str] | None = None,
    ) -> Any:
        args = [
            "--apply", "--uid", uid, "--record", json.dumps(records, sort_keys=True),
            "--note", note,
        ]
        if expected is not None:
            args.extend(["--expected", json.dumps(expected, sort_keys=True)])
        return self._run(args)


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
    expected: Mapping[str, str] | None = None,
    return_readback: bool = False,
) -> dict[str, Any]:
    ids = {int(item["id"]) for item in species}
    checked_desired = validate_requested_patch(desired, ids)
    checked_expected = None
    if expected is not None:
        checked_expected = validate_requested_patch(expected, ids)
        if not set(checked_expected).issubset(checked_desired):
            raise SchemaError("expected statuses must refer to requested record keys")
    changes = minimal_patch(current, checked_desired)
    result: dict[str, Any] = {
        "changed": bool(changes),
        "changes": changes,
        "dry_run": bool(dry_run),
    }
    if not changes or dry_run:
        result["caught_count"] = caught_count(current)
        result["current_statuses"] = {key: record_value(current, key) for key in checked_desired}
        if return_readback:
            result["_readback_records"] = copy.deepcopy(dict(current))
        return result

    # The transport computes the minimal diff at its ETag snapshot. Submit ALL
    # desired keys so a race cannot drop an initially unchanged side of a trade.
    if checked_expected is None:
        applied = client.apply_records(uid, checked_desired, note=note)
    else:
        applied = client.apply_records(uid, checked_desired, note=note, expected=checked_expected)
    after = _read_checked(client, uid, species)
    for key, expected_status in checked_desired.items():
        if key not in after or after[key].get("s") != expected_status:
            actual = after.get(key, {}).get("s", "<missing>")
            raise VerificationError(
                f"readback mismatch for {key}: expected {expected_status!r}, got {actual!r}"
            )
    if isinstance(applied, Mapping) and applied.get("changed") is False:
        # The transport did its own fresh read-then-diff and found the desired
        # value already there (a concurrent writer landed between our read and
        # its write): the readback matches, but this call created no log/*
        # audit entry, so it must not be reported the same as a real write.
        result["changed"] = False
        result["changes"] = {}
        result["verified"] = False
        result["verified_no_write"] = True
        result["warning"] = {
            "code": "already_at_status",
            "message": "The requested statuses were already set at the transaction boundary; no write was made.",
        }
    else:
        result["verified"] = True
    result["caught_count"] = caught_count(after)
    result["verified_statuses"] = {key: record_value(after, key) for key in checked_desired}
    if isinstance(applied, Mapping) and applied.get("changed") is True:
        actual_changes = applied.get("changes")
        if isinstance(actual_changes, list):
            result["changes"] = {change["key"]: change["to"] for change in actual_changes}
    if return_readback:
        result["_readback_records"] = after
    return result


def _with_operation(result: dict[str, Any], operation: str, **extra: Any) -> dict[str, Any]:
    return {"operation": operation, **extra, **result}


def run_status(
    client: Any,
    uid: str,
    name: str,
    species: Sequence[Species] | None = None,
) -> dict[str, Any]:
    catalogue = list(species) if species is not None else load_species()
    target = resolve_species(name, catalogue)
    current = _read_checked(client, uid, catalogue)
    key = f"species:{int(target['id'])}"
    return {
        "operation": "status",
        "species": target,
        "status": record_value(current, key),
        "caught_count": caught_count(current),
        "changed": False,
    }


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


def infer_next_evolution(source: Species, species: Sequence[Species]) -> Species:
    """Derive the immediate species from local Gen VII paths, without account I/O."""
    try:
        moves = json.loads((ROOT / "data" / "moves.json").read_text(encoding="utf-8"))
        details = json.loads((ROOT / "data" / "pokedex-details.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SchemaError("Local evolution data could not be read; specify TO explicitly") from exc
    lines = moves.get("lines") if isinstance(moves, dict) else None
    rows = details.get("species") if isinstance(details, dict) else None
    if not isinstance(lines, dict) or not isinstance(rows, list):
        raise SchemaError("Local evolution data has an invalid shape; specify TO explicitly")
    source_id = int(source["id"])
    finals = lines.get(str(source_id))
    if finals is None and isinstance(moves.get("finals"), dict) and str(source_id) in moves["finals"]:
        raise OperationError(f"{source['name']} has no next Generation VII evolution; nothing changed")
    if not isinstance(finals, list) or not finals:
        raise SchemaError(f"Evolution data for {source['name']} is unavailable; specify TO explicitly")
    by_id = {}
    for row in rows:
        if not isinstance(row, dict) or type(row.get("id")) is not int or row["id"] in by_id:
            raise SchemaError("Local evolution species index is malformed; specify TO explicitly")
        by_id[row["id"]] = row
    aliases = {normalize(str(source["name"])), normalize(str(source["slug"]))}
    targets: dict[int, Species] = {}
    for final_id in finals:
        if type(final_id) is not int or final_id not in by_id:
            raise SchemaError("Local evolution endpoints are malformed; specify TO explicitly")
        if final_id == source_id:
            continue
        path = by_id[final_id].get("evolution")
        if not isinstance(path, list) or len(path) < 2 or any(
            not isinstance(step, dict) or not isinstance(step.get("name"), str) or not step["name"]
            for step in path
        ):
            raise SchemaError(f"Evolution path for {source['name']} is unavailable; specify TO explicitly")
        try:
            if int(resolve_species(path[-1]["name"], species)["id"]) != final_id:
                raise SchemaError("Evolution endpoint does not match its species record")
            positions = [i for i, step in enumerate(path) if normalize(step["name"]) in aliases
                         and int(resolve_species(step["name"], species)["id"]) == source_id]
            if len(positions) != 1 or positions[0] >= len(path) - 1:
                raise SchemaError("Source is missing or repeated in its evolution path")
            target = resolve_species(path[positions[0] + 1]["name"], species)
        except OperationError as exc:
            raise SchemaError(f"Evolution path for {source['name']} cannot be resolved safely; specify TO explicitly") from exc
        target_id = int(target["id"])
        if target_id == source_id:
            raise SchemaError("Evolution path loops back to its source")
        targets[target_id] = target
    if not targets:
        raise OperationError(f"{source['name']} has no next Generation VII evolution; nothing changed")
    if len(targets) > 1:
        raise EvolutionChoiceRequired(source, [targets[key] for key in sorted(targets)])
    return next(iter(targets.values()))


def run_pair(
    client: Any,
    uid: str,
    operation: str,
    from_name: str,
    to_name: str | None = None,
    species: Sequence[Species] | None = None,
    *,
    dry_run: bool = False,
    note: str = "",
    return_readback: bool = False,
) -> dict[str, Any]:
    if operation not in {"evolve", "trade"}:
        raise OperationError("pair operation must be evolve or trade")
    catalogue = list(species) if species is not None else load_species()
    source = resolve_species(from_name, catalogue)
    if to_name is None and operation != "evolve":
        raise OperationError("Trade requires both FROM and TO")
    target = infer_next_evolution(source, catalogue) if to_name is None else resolve_species(to_name, catalogue)
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
        return_readback=return_readback,
    )
    if not result["changed"] and not dry_run:
        observed = result.get("verified_statuses", result.get("current_statuses"))
        if observed != desired:
            raise VerificationError("Unchanged pair did not match its requested statuses")
        result.update(verified_no_write=True, verified_statuses=dict(observed))
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


class PokemonStatusTool:
    """UID-scoped status operations with an injectable account transport."""

    def __init__(
        self,
        uid: str,
        client: Any | None = None,
        species: Sequence[Species] | None = None,
    ) -> None:
        self.uid = uid
        self.client = client if client is not None else FirebaseClient()
        self.species = list(load_species() if species is None else species)

    @staticmethod
    def _validate_status(status: Any) -> None:
        if not isinstance(status, str) or status not in STATUS_VALUES:
            raise OperationError(f"invalid status {status!r}; expected caught, seen, or none")

    def check_pokemon_status(self, name: str) -> str:
        return run_status(self.client, self.uid, name, self.species)["status"]

    def _write_status(
        self,
        target: Species,
        status: str,
        current: RecordMap,
        *,
        expected: Mapping[str, str] | None = None,
        dry_run: bool = False,
        note: str = "",
    ) -> dict[str, Any]:
        key = f"species:{int(target['id'])}"
        result = _apply_verified(
            self.client,
            self.uid,
            current,
            {key: status},
            self.species,
            dry_run=dry_run,
            note=note or f"chat set status {target['name']} to {status}",
            expected=expected,
            return_readback=True,
        )
        final = result.pop("_readback_records")
        output = _with_operation(result, "set_status", species=target)
        output["status"] = record_value(final, key)
        output["caught_count"] = caught_count(final)
        return output

    def _set_pokemon_status(self, name: str, status: str) -> dict[str, Any]:
        self._validate_status(status)
        target = resolve_species(name, self.species)
        current = _read_checked(self.client, self.uid, self.species)
        return self._write_status(target, status, current)

    def set_pokemon_status(
        self,
        name: str,
        status: str,
        old_status: str | object = UNSET,
        *,
        dry_run: bool = False,
        note: str = "",
    ) -> dict[str, Any]:
        self._validate_status(status)
        if old_status is not UNSET:
            self._validate_status(old_status)
        target = resolve_species(name, self.species)
        current = _read_checked(self.client, self.uid, self.species)
        key = f"species:{int(target['id'])}"
        actual = record_value(current, key)
        expected = None
        if old_status is not UNSET:
            if actual != old_status:
                raise StatusPreconditionError(
                    f"status precondition failed for {target['name']}: "
                    f"expected {old_status!r}, found {actual!r}"
                )
            expected = {key: old_status}
        if actual == status:
            return {
                "operation": "set_status",
                "species": target,
                "status": status,
                "caught_count": caught_count(current),
                "changed": False,
                "changes": {},
                "dry_run": bool(dry_run),
                "warning": {
                    "code": "already_at_status",
                    "message": f"{target['name']} is already {status}; no write was made.",
                },
            }
        return self._write_status(
            target,
            status,
            current,
            expected=expected,
            dry_run=dry_run,
            note=note,
        )

    def evolve_pokemon_status(
        self,
        name: str,
        to_name: str | None = None,
        *,
        dry_run: bool = False,
        note: str = "",
    ) -> dict[str, Any]:
        """Evolve one stage automatically, or preserve an explicit target."""
        return run_pair(
            self.client, self.uid, "evolve", name, to_name, self.species,
            dry_run=dry_run, note=note,
        )

    def trade_pokemon_status(
        self,
        name1: str,
        name2: str,
        *,
        dry_run: bool = False,
        note: str = "",
    ) -> dict[str, Any]:
        result = run_pair(
            self.client,
            self.uid,
            "trade",
            name1,
            name2,
            self.species,
            dry_run=dry_run,
            note=note,
            return_readback=True,
        )
        final = result.pop("_readback_records")
        source, target = result["from_species"], result["to_species"]
        result["statuses"] = {
            source["name"]: record_value(final, f"species:{int(source['id'])}"),
            target["name"]: record_value(final, f"species:{int(target['id'])}"),
        }
        result["caught_count"] = caught_count(final)
        return result


def _add_common_flags(parser: argparse.ArgumentParser, *, suppress_defaults: bool = False) -> None:
    # --uid is never argparse-`required` here: a subparsers action (nargs=PARSER)
    # swallows every token after the subcommand into the SUBPARSER, so a top-level
    # `required=True` action never sees a --uid placed after `mark`/`evolve`/etc.
    # and fails closed even though the flag was supplied. Both parsers share one
    # namespace attribute, so whichever position provides --uid sets it; main()
    # checks it is actually present once, after parsing, regardless of order.
    default = argparse.SUPPRESS if suppress_defaults else None
    parser.add_argument("--uid", default=default, help="Firebase account uid")
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

    status_parser = commands.add_parser("status", help="read one current species status")
    _add_common_flags(status_parser, suppress_defaults=True)
    status_parser.add_argument("name")

    set_status_parser = commands.add_parser("set-status", help="set one status with optional old-status guard")
    _add_common_flags(set_status_parser, suppress_defaults=True)
    set_status_parser.add_argument("name")
    set_status_parser.add_argument("status", choices=tuple(sorted(STATUS_VALUES)))
    set_status_parser.add_argument(
        "--old-status", choices=tuple(sorted(STATUS_VALUES)), default=argparse.SUPPRESS,
        help="require this status at the Firebase conditional-write boundary",
    )

    mark_parser = commands.add_parser("mark", help="mark one species")
    _add_common_flags(mark_parser, suppress_defaults=True)
    mark_parser.add_argument("name")
    mark_parser.add_argument("status", choices=tuple(sorted(STATUS_VALUES)))

    for operation in ("evolve", "trade"):
        pair_parser = commands.add_parser(operation, help=("infer one next evolution, or specify TO; atomic Seen/Caught update" if operation == "evolve" else "mark FROM seen and TO caught atomically"))
        _add_common_flags(pair_parser, suppress_defaults=True)
        pair_parser.add_argument("from_name", metavar="FROM")
        pair_parser.add_argument("to_name", metavar="TO", nargs="?" if operation == "evolve" else None,
                                 help="omit for a unique next evolution" if operation == "evolve" else "received species")

    favorites_parser = commands.add_parser("favorites", help="reconcile favorites")
    _add_common_flags(favorites_parser, suppress_defaults=True)
    favorites_parser.add_argument("--exact", nargs="+", metavar="NAME", required=True)
    return parser


def _print_result(result: Mapping[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return
    if result.get("operation") == "status":
        print(f"{result['species']['name']}: {result['status']} · {result['caught_count']} caught")
        return
    if result.get("operation") == "list":
        for item in result["items"]:
            suffix = " [favorite]" if item.get("favorite") else ""
            print(f"#{int(item['id']):03d} {item['name']} ({item['status']}){suffix}")
        print(f"{len(result['items'])} species")
        return
    if result.get("warning"):
        print("WARN: " + result["warning"]["message"])
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
    if not args.uid:
        parser.error("the following arguments are required: --uid")
    species = load_species()
    client = FirebaseClient()
    try:
        if args.command == "list":
            result = run_list(client, args.uid, args.category, species)
        elif args.command == "status":
            result = run_status(client, args.uid, args.name, species)
        elif args.command == "set-status":
            tool = PokemonStatusTool(args.uid, client=client, species=species)
            result = tool.set_pokemon_status(
                args.name,
                args.status,
                old_status=getattr(args, "old_status", UNSET),
                dry_run=args.dry_run,
                note=args.note or "",
            )
        elif args.command == "mark":
            result = run_mark(client, args.uid, args.name, args.status, species, dry_run=args.dry_run, note=args.note or "")
        elif args.command == "evolve":
            result = run_pair(client, args.uid, "evolve", args.from_name, args.to_name, species, dry_run=args.dry_run, note=args.note or "")
        elif args.command == "trade":
            tool = PokemonStatusTool(args.uid, client=client, species=species)
            result = tool.trade_pokemon_status(
                args.from_name, args.to_name, dry_run=args.dry_run, note=args.note or ""
            )
        elif args.command == "favorites":
            result = run_favorites_exact(client, args.uid, args.exact, species, dry_run=args.dry_run, note=args.note or "")
        else:  # argparse makes this unreachable, but keeps the dispatch total.
            raise OperationError(f"unknown command {args.command}")
    except OperationError as exc:
        if args.json:
            error: dict[str, Any] = {"error": str(exc)}
            if isinstance(exc, EvolutionChoiceRequired):
                error.update(code="evolution_choice_required", source=exc.source, candidates=exc.candidates)
            print(json.dumps(error, ensure_ascii=False))
        else:
            print(f"error: {exc}", file=sys.stderr)
        return 1
    _print_result(result, args.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
