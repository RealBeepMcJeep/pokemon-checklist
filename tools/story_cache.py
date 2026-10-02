"""Best-effort JSON cache for expensive story selection, never for roster reads.

Call only after fresh input validation/preparation. Results refer to current input
profiles by index; tuples/sets keep their domain types without executable pickle.
"""
from __future__ import annotations

import hashlib
import inspect
import json
import os
import stat
import sys
import tempfile
from pathlib import Path

import story_native

SCHEMA = 1
MAX_BYTES = 8 * 1024 * 1024
_CACHE_ERRORS = (OSError, ValueError, TypeError, KeyError, IndexError, RecursionError)


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _pack(value, references=None):
    if references is not None and id(value) in references:
        return ["profile", references[id(value)]]
    if isinstance(value, dict):
        pairs = [[_pack(k), _pack(v, references)] for k, v in value.items()]
        return ["dict", sorted(pairs, key=lambda pair: _json(pair[0]))]
    if isinstance(value, (list, tuple, set, frozenset)):
        items = [_pack(v, references) for v in value]
        if isinstance(value, (set, frozenset)):
            items.sort(key=_json)
        return [type(value).__name__, items]
    if value is None or type(value) in (bool, int, float, str):
        return ["value", value]
    raise ValueError("unsupported cache value")


def _unpack(value, profiles):
    kind, body = value
    if kind == "profile":
        return profiles[body]
    if kind == "value":
        return body
    if kind == "dict":
        return {_unpack(k, profiles): _unpack(v, profiles) for k, v in body}
    constructors = {"list": list, "tuple": tuple, "set": set, "frozenset": frozenset}
    return constructors[kind](_unpack(v, profiles) for v in body)


def implementation_identity(selector, *, root=None):
    """Hash sources, Python runtime, and the actual runtime-selected executable.

    Ignore dependency/build intermediates, but include target release/debug main
    binaries and the selected external/cache-built executable. Native disable,
    override, availability and same-path replacement all change the key.
    An uninspectable selector (e.g. a test mock) deliberately disables caching.
    """
    source = inspect.getsourcefile(selector)
    if source is None:
        raise ValueError("selector has no inspectable implementation")
    root = Path(root) if root is not None else Path(__file__).resolve().parents[1]
    paths = {Path(source).resolve()}
    ignored = {".git", "node_modules", ".venv", "__pycache__", "deps", "incremental", ".fingerprint", "build"}
    for directory, children, files in os.walk(root):
        children[:] = sorted(d for d in children if d not in ignored)
        for name in files:
            path = Path(directory) / name
            relative = path.relative_to(root)
            if (path.suffix in {".rs", ".so", ".exe"} or name in {"Cargo.toml", "Cargo.lock"}
                    or (path.suffix == ".py" and relative.parts[0] == "tools" and "tests" not in relative.parts)
                    or (not path.suffix and os.access(path, os.X_OK) and path.is_file())):
                paths.add(path.resolve())
    digest = hashlib.sha256()
    binary = story_native.binary_path()
    mode = ("disabled" if os.environ.get("STORY_NATIVE_DISABLE") == "1"
            else "available" if binary is not None else "unavailable")
    digest.update(_json({"python": [sys.implementation.name, list(sys.version_info)],
                         "native_mode": mode,
                         "native_override": os.environ.get("STORY_NATIVE_BINARY"),
                         "native_binary": str(binary.resolve()) if binary is not None else None,
                         "native_protocol": story_native.PROTOCOL}).encode())
    if binary is not None:
        paths.add(binary.resolve())
    # Different supplied callables in one file must not share results.
    digest.update(str(getattr(selector, "__qualname__", "")).encode())
    for path in sorted(paths):
        digest.update(str(path).encode())
        with path.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
    return digest.hexdigest()


def _private_directory(directory):
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        if os.fstat(fd).st_uid != os.getuid():
            raise ValueError("cache directory belongs to another user")
        os.fchmod(fd, 0o700)  # inherited ACLs can widen mkdir's requested mode
    finally:
        os.close(fd)


def _read(path, key, current):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or info.st_nlink != 1 or info.st_size > MAX_BYTES):
            raise ValueError("unsafe or oversized selection cache")
        os.fchmod(stream.fileno(), 0o600)
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("oversized selection cache")
    payload = json.loads(raw)
    if payload["schema"] != SCHEMA or payload["key"] != key:
        raise ValueError("unsupported selection cache")
    if hashlib.sha256(_json(payload["options"]).encode()).hexdigest() != payload["digest"]:
        raise ValueError("corrupt selection cache")
    options = _unpack(payload["options"], current)
    if not isinstance(options, list) or not all(isinstance(o, dict) for o in options):
        raise ValueError("invalid selection result")
    return options


def _write(path, key, options, references):
    # Never overwrite/follow a link, even though atomic replacement is safe.
    if path.is_symlink():
        raise ValueError("cache file is a symlink")
    packed = _pack(options, references)
    raw = _json({"schema": SCHEMA, "key": key, "options": packed,
                 "digest": hashlib.sha256(_json(packed).encode()).hexdigest()}).encode()
    if len(raw) > MAX_BYTES:
        return
    fd, temporary = tempfile.mkstemp(prefix=".selection-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        entries = sorted((p for p in path.parent.glob("*.json")
                          if len(p.stem) == 64 and all(c in "0123456789abcdef" for c in p.stem)),
                         key=lambda p: (p.stat().st_mtime_ns, p.name), reverse=True)
        for old in entries[32:]:
            old.unlink()
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def choose_cached(profiles, utility, chart, *, pokedex_profiles, selector,
                  cache_dir, enabled=True, implementation=None):
    """Cache failures are misses; selector failures retain their original behavior."""
    if not enabled:
        return selector(profiles, utility, chart, pokedex_profiles=pokedex_profiles)
    current = [*profiles, *pokedex_profiles]
    references = {id(p): i for i, p in enumerate(current)}
    path, key = None, ""
    try:
        identity = implementation if implementation is not None else implementation_identity(selector)
        key = hashlib.sha256(_json(_pack([profiles, utility, chart, pokedex_profiles, identity])).encode()).hexdigest()
        directory = Path(cache_dir)
        _private_directory(directory)
        path = directory / f"{key}.json"
        return _read(path, key, current)
    except _CACHE_ERRORS:
        pass
    options = selector(profiles, utility, chart, pokedex_profiles=pokedex_profiles)
    if path is not None:
        try:
            _write(path, key, options, references)
        except _CACHE_ERRORS:
            pass
    return options
