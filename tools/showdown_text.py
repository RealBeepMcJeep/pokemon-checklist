from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterator


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


def block(text: str, name: str) -> str:
    """Return one top-level block, matching the existing punctuation normalization."""
    wanted = _key(name)
    return next((body for key, body in top_blocks(text) if _key(key) == wanted), "")


def field(body: str, name: str) -> str | None:
    """Read one quoted Showdown scalar field."""
    match = re.search(rf"\b{re.escape(name)}\s*:\s*['\"]([^'\"]*)['\"]", body)
    return match.group(1) if match else None


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
