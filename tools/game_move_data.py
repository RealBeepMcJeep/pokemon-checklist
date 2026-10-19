"""Version- and form-specific Gen VII learning methods from pinned PokeAPI rows."""
from __future__ import annotations

import argparse
import csv
import tempfile
import urllib.request
import hashlib
import io
import os
from pathlib import Path

try:
    from .showdown_text import normalize_name
    from .cache_support import default_cache_dir
except ImportError:
    from showdown_text import normalize_name
    from cache_support import default_cache_dir

COMMIT = "4b82c204ddd19ecb8eda2ea044ccb59e222b721c"
BASE = f"https://raw.githubusercontent.com/PokeAPI/pokeapi/{COMMIT}/data/v2/csv/"
SOURCES = {name: (BASE + name, digest) for name, digest in {
    "pokemon.csv": "16c81c33188b0eac403aa2f759fcbe9e42c611f722d263f5b5a6a5bff9f8ce6b",
    "pokemon_moves.csv": "22a807cef26891eeac0d0c900bd363e66baf421f7ee795bc7bc3e718f23b939e",
    "moves.csv": "8aafd37bf78f19471495c05b201545180f50f0a08a2a2a844d69f9837dd39ac9",
    "version_groups.csv": "28da8d89d8eb4966941f81a9e62b3990510ed4d76dd774158246551a8e7707a7",
    "pokemon_move_methods.csv": "78b75acfcf6dca4c82da9d4851357cbbd65e61b08154eddfc2ace0efd00e408e",
    "machines.csv": "f9df7faaf0a60896fa344abd2b639f83f79c2a24e1fd4bb3560ca7da76e9a6ad",
}.items()}


def configured_cache_dir() -> Path:
    return Path(os.environ.get("POKEMON_GAME_MOVE_CACHE", default_cache_dir("game-moves"))).expanduser()


def load_tables(cache: Path, sources: dict | None = None) -> dict:
    """Read admitted local bytes only. A missing/corrupt cache is never repaired."""
    sources = SOURCES if sources is None else sources
    tables = {}
    for name, (_, expected) in sources.items():
        if Path(name).name != name:
            raise ValueError("Unsafe move-source filename")
        path = Path(cache) / name
        if not path.is_file():
            raise ValueError(f"Missing pinned game-move source {name}; bootstrap the source cache explicitly")
        content = path.read_bytes()
        if hashlib.sha256(content).hexdigest() != expected:
            raise ValueError(f"Game-move source hash mismatch: {name}")
        rows = csv.DictReader(io.StringIO(content.decode("utf-8")))
        # The pinned version-group file establishes these two immutable IDs.
        tables[name] = [row for row in rows if name != "pokemon_moves.csv" or row["version_group_id"] in {"17", "18"}]
    return tables


def bootstrap(cache: Path, downloader=None, sources: dict | None = None) -> None:
    """Explicit network admission; validate the entire batch before replacing files."""
    pins = SOURCES if sources is None else sources
    cache = Path(cache).expanduser().resolve()
    cache.parent.mkdir(parents=True, exist_ok=True)
    def fetch(url):
        with urllib.request.urlopen(url, timeout=60) as response:
            return response.read(32 * 1024 * 1024 + 1)
    with tempfile.TemporaryDirectory(prefix="game-moves-", dir=cache.parent) as directory:
        staging = Path(directory)
        for name, (url, digest) in pins.items():
            if Path(name).name != name:
                raise ValueError("Unsafe move-source filename")
            content = (downloader or fetch)(url)
            if len(content) > 32 * 1024 * 1024 or hashlib.sha256(content).hexdigest() != digest:
                raise ValueError(f"Game-move source hash mismatch: {name}")
            (staging / name).write_bytes(content)
        load_tables(staging, pins)
        cache.mkdir(parents=True, exist_ok=True)
        for name in pins:
            os.replace(staging / name, cache / name)


def project_sources(tables: dict, targets: list[dict]) -> dict:
    """Project one exact Pokemon row into SM/USUM; do not union versions/forms."""
    expected = {"sun-moon": "sm", "ultra-sun-ultra-moon": "usum"}
    versions = {row["id"]: expected[row["identifier"]] for row in tables["version_groups.csv"]
                if row["identifier"] in expected and row["generation_id"] == "7"}
    if set(versions.values()) != {"sm", "usum"}:
        raise ValueError("Both Gen VII version groups are required")
    names = {row["id"]: normalize_name(row["identifier"]) for row in tables["moves.csv"]}
    methods = {row["id"]: row["identifier"] for row in tables["pokemon_move_methods.csv"]}
    machines = {(row["version_group_id"], row["move_id"]): int(row["machine_number"])
                for row in tables["machines.csv"] if row["version_group_id"] in versions}
    aliases: dict[str, list[str]] = {}
    result = {}
    for target in targets:
        form = target.get("form")
        if type(target["id"]) is not int or not 1 <= target["id"] <= 807 or (
            form and (form not in {"kanto", "alolan"} or target["key"] != f"{target['id']}:{form}")
        ):
            raise ValueError(f"Invalid Pokemon identity: {target['key']}")
        matches = [row for row in tables["pokemon.csv"] if int(row["species_id"]) == target["id"] and (
            (row["is_default"] == "1" if form in {None, "kanto"} else row["identifier"].endswith("-alola"))
            and (not form or normalize_name(row["identifier"]) == target["showdownKey"]))]
        if len(matches) != 1:
            raise ValueError(f"No unique Pokemon identity for {target['key']}")
        aliases.setdefault(matches[0]["id"], []).append(target["key"])
        result[target["key"]] = {"sm": {}, "usum": {}}
    for row in tables["pokemon_moves.csv"]:
        profile = versions.get(row["version_group_id"])
        if profile is None or row["pokemon_id"] not in aliases:
            continue
        method = methods[row["pokemon_move_method_id"]]
        if method == "level-up":
            level = int(row["level"])
            route = {"via": "evolution"} if level == 0 else {"via": "reminder"} if level == 1 else {"via": "level", "level": level}
        elif method == "tutor":
            route = {"via": "tutor"}
        elif method == "egg":
            route = {"via": "egg"}
        elif method == "machine":
            route = {"via": "TM", "tm": machines[(row["version_group_id"], row["move_id"])]}
        elif method == "light-ball-egg":
            route = {"via": "egg", "note": "Breed with a parent holding Light Ball"}
        elif method in {"form-change", "zygarde-cube"}:
            route = {"via": "special", "note": "Change form" if method == "form-change" else "Zygarde Cube"}
        else:
            raise ValueError(f"Unsupported Gen VII learning method: {method}")
        for target in aliases[row["pokemon_id"]]:
            routes = result[target][profile].setdefault(names[row["move_id"]], [])
            if route not in routes:
                routes.append(route.copy())
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, default=configured_cache_dir())
    parser.add_argument("action", choices=["bootstrap", "verify"])
    args = parser.parse_args(argv)
    try:
        if args.action == "bootstrap":
            bootstrap(args.cache)
        load_tables(args.cache)
    except (OSError, ValueError) as error:
        parser.exit(1, f"Game-move source admission refused: {error}\n")
    print(f"Verified {len(SOURCES)} pinned game-move CSV sources")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
