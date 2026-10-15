from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Callable, Iterator
from functools import lru_cache


def _key(value: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def top_blocks(text: str) -> Iterator[tuple[str, str]]:
    """Yield ``(key, body)`` for top-level Showdown ``key: { ... }`` blocks."""
    for match in re.finditer(
        r'\n\t(?:"([a-z0-9\-]+)"|([a-z0-9\-]+))\s*:\s*\{', text
    ):
        key = match.group(1) or match.group(2)
        start = match.end() - 1
        depth = 0
        for index in range(start, len(text)):
            if text[index] == "{":
                depth += 1
            elif text[index] == "}":
                depth -= 1
                if depth == 0:
                    yield key, text[start : index + 1]
                    break


@lru_cache(maxsize=8)
def _block_index(text: str) -> dict[str, str]:
    """Index immutable source content, not a path or a verification result.

    Bound retained sources; content changes miss. Preserve the old iterator's
    FIRST normalized-key match, including duplicate/punctuation collisions.
    """
    result: dict[str, str] = {}
    for key, body in top_blocks(text):
        result.setdefault(_key(key), body)
    return result


def block(text: str, name: str) -> str:
    """Return one block without rescanning unchanged, already-read source text."""
    return _block_index(text).get(_key(name), "")


def field(body: str, name: str) -> str | None:
    """Read one quoted Showdown scalar field."""
    match = re.search(rf"\b{re.escape(name)}\s*:\s*['\"]([^'\"]*)['\"]", body)
    return match.group(1) if match else None


def normalize_name(value: object) -> str:
    """Fold a display name to a bare key: strip accents, case, and punctuation.

    Shared by every tool (and the chat parser) that matches a typed or stored name
    against data/pokemon.json, so an accented species like Flabébé resolves the
    same way everywhere instead of drifting per hand-rolled copy -- a plain
    ascii-ignore encode used to drop accented letters whole instead of folding
    them to their base letter, silently losing the only accented Latin-letter
    species in the dex.
    """
    # Convert on EVERY use: arbitrary/unhashable objects and mutable __str__
    # implementations keep their existing behavior. Only pure string content is cached.
    literal = str(value)
    # Bound individual retained payloads as well as the number of names. This
    # changes work/retention only; oversized inputs still use the exact old fold.
    if len(literal) > 256:
        return _normalize_name_text.__wrapped__(literal)
    return _normalize_name_text(literal)


@lru_cache(maxsize=4096)
def _normalize_name_text(value: str) -> str:
    """Bounded pure-name work; never a file/path/provenance validation cache."""
    decomposed = unicodedata.normalize("NFD", value)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]", "", stripped.lower())


def list_field(
    body: str,
    name: str,
    normalize: Callable[[str], str] | None = None,
) -> list[str]:
    """Read a quoted one-line Showdown list, optionally normalizing each value."""
    match = re.search(rf"\b{re.escape(name)}\s*:\s*(\[[^\]]*\])", body)
    if not match:
        return []
    values = re.findall(r"['\"]([^'\"]+)['\"]", match.group(1))
    return [normalize(value) if normalize else value for value in values]


def integer_field(body: str, name: str) -> int | None:
    match = re.search(rf"\b{re.escape(name)}\s*:\s*([0-9]+)", body)
    return int(match.group(1)) if match else None


def array_field(body: str, name: str) -> list[str]:
    match = re.search(rf"\b{re.escape(name)}\s*:\s*(\[[^\]]*\])", body)
    if not match:
        return []
    try:
        values = json.loads(match.group(1))
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid {name} array in Showdown data") from error
    if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
        raise ValueError(f"invalid {name} values in Showdown data")
    return values


def object_after(body: str, name: str) -> str | None:
    """Extract one balanced ``name: { ... }`` or ``name = { ... }`` object."""
    match = re.search(rf"\b{re.escape(name)}\s*(?::|=)\s*\{{", body)
    if not match:
        return None
    start = match.end() - 1
    depth = 0
    for index in range(start, len(body)):
        if body[index] == "{":
            depth += 1
        elif body[index] == "}":
            depth -= 1
            if depth == 0:
                return body[start : index + 1]
    return None
