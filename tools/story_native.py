"""Optional exact Rust kernel. Missing/unsupported native execution is a Python miss.

Build explicitly with ``python native/story-search/build.py``. Routine selection
never invokes Cargo, downloads a dependency, or changes the toolchain.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys

CRATE = Path(__file__).resolve().parents[1] / "native/story-search"
PROTOCOL = 1
FUSED_PROTOCOL = 2


def build_directory() -> Path:
    identity = hashlib.sha256()
    for relative in ("Cargo.toml", "src/main.rs"):
        identity.update(relative.encode())
        identity.update((CRATE / relative).read_bytes())
    base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return base / "pokemon-checklist/story-search" / identity.hexdigest()[:24]


def binary_path() -> Path | None:
    if os.environ.get("STORY_NATIVE_DISABLE") == "1":
        return None
    override = os.environ.get("STORY_NATIVE_BINARY")
    try:
        path = Path(override) if override else build_directory() / "release/story-search"
        return path if path.is_file() and os.access(path, os.X_OK) else None
    except OSError:
        return None


def _request(prepared, *, owned, opportunities, viability, additions, favorites,
             names, category) -> tuple[Path, list[str]] | None:
    """Build a supported standalone request, or return None for the reference.

    The wire uses precomputed features and integer name ranks, not species data.
    Ownership is represented by pair-conflict bitsets of arbitrary word count.
    Unsupported numerical/type domains deliberately use the Python reference.
    """
    binary = binary_path()
    if binary is None:
        return None
    n = len(names)
    if (sys.implementation.name != 'cpython'
            or sys.version_info[:2] not in ((3, 10), (3, 11), (3, 12), (3, 13))
            or category not in ("OG", "Non-OG", "Mixed", "Pokedex", "Best")
            or math.comb(n, 5) > (1 << 64) - 1
            or any(len(values) != n for values in
                   (owned, opportunities, viability, additions, favorites))
            or sum(sorted(opportunities, reverse=True)[:5]) >= (1 << 53)
            or sum(sorted(additions, reverse=True)[:5]) >= (1 << 53)
            or len(prepared.weak) != n + 1
            or any(mask.bit_length() > 64 for mask in (*prepared.weak, *prepared.resist))
            or any(not math.isfinite(v) or abs(v) > 1e8 for v in viability)
            or any(not math.isfinite(v) or v < 0 or v > 1e8
                   for row in prepared.coverage for v in row)):
        return None
    ranks = {name: i for i, name in enumerate(sorted(set(names)))}
    words = (n + 63) // 64
    rows = [[sum(1 << (j % 64) for j in range(word * 64, min(n, (word + 1) * 64))
                 if owned[i] & owned[j]) for word in range(words)] for i in range(n)]
    tokens = [str(PROTOCOL), str(n), category, str(int(sys.version_info >= (3, 12))),
              str(int(prepared.uniform)), repr(prepared.strength), str(int(prepared.disjoint))]
    for i in range(n + 1):
        tokens += [str(prepared.weak[i]), str(prepared.resist[i]), str(prepared.hit_masks[i])]
        tokens += [repr(v) for v in prepared.coverage[i]]
        tokens += [str(v) for v in prepared.overlap[i]]
    for i in range(n):
        tokens += [repr(viability[i]), str(opportunities[i]), str(additions[i]),
                   str(int(favorites[i])), str(ranks[names[i]])]
        tokens += [str(v) for v in rows[i]]
    return binary, tokens


def _validate(answer, prepared, *, owned, viability, names):
    n = len(names)
    if not isinstance(answer, dict) or answer.get('protocol') != PROTOCOL:
        return None
    indices = answer.get('indices')
    if 'indices' not in answer or (indices is not None and (
            not isinstance(indices, list) or len(indices) != 5
            or any(type(i) is not int or i < 0 or i >= n for i in indices)
            or indices != sorted(set(indices))
            or any(owned[i] & owned[j] for pos, i in enumerate(indices) for j in indices[:pos]))):
        return None
    counters = ('independent_combinations', 'scored_combinations', 'primary_skips')
    if any(type(answer.get(key)) is not int or answer[key] < 0 for key in counters):
        return None
    if (answer['independent_combinations'] > math.comb(n, 5)
            or answer['scored_combinations'] + answer['primary_skips']
            != answer['independent_combinations']):
        return None
    if indices is None:
        return answer if answer['independent_combinations'] == 0 else None
    if any(type(answer.get(key)) not in (int, float) or not math.isfinite(answer[key])
           for key in ('core', 'full', 'synergy', 'quality')):
        return None
    core = prepared.score(tuple(indices))
    full = prepared.score((*indices, n))
    if (answer['core'] != core or answer['full'] != full
            or answer['synergy'] != round(0.65 * core + 0.35 * full, 4)
            or answer['quality'] != round(sum(viability[i] for i in indices) / 5, 4)):
        return None
    return answer


def search(prepared, *, owned, opportunities, viability, additions, favorites,
           names, category) -> dict | None:
    """Exact standalone request; None preserves the existing Python reference path."""
    request = _request(prepared, owned=owned, opportunities=opportunities,
                       viability=viability, additions=additions, favorites=favorites,
                       names=names, category=category)
    if request is None:
        return None
    binary, tokens = request
    try:
        result = subprocess.run([str(binary)], input=' '.join(tokens), text=True,
                                capture_output=True, check=True)
        return _validate(json.loads(result.stdout), prepared,
                         owned=owned, viability=viability, names=names)
    except (OSError, subprocess.SubprocessError, ValueError, TypeError):
        return None


def search_pair(prepared, subset_prepared, *, subset, owned, opportunities, viability,
                additions, favorites, names) -> dict | None:
    """One no-skip traversal only when BOTH score representations are compatible.

    A miss asks the caller to run the original separate searches. Subset indices
    must be a strictly increasing projection, preserving encounter/tie order.
    """
    if os.environ.get('STORY_NATIVE_FUSION_DISABLE') == '1':
        return None
    n = len(names)
    if (len(prepared.weak) != n + 1
            or len(subset_prepared.weak) != len(subset) + 1):
        return None
    if (len(subset) < 5 or any(type(i) is not int or i < 0 or i >= n for i in subset)
            or subset != sorted(set(subset))):
        return None
    if (prepared.uniform != subset_prepared.uniform
            or (prepared.uniform and prepared.strength != subset_prepared.strength)
            or prepared.disjoint != subset_prepared.disjoint):
        return None
    # Extra/custom types can shift encoded mask positions when a pool shrinks.
    # Check exact projection, not merely the global switches or species names.
    projection = [*subset, n]
    for field in ('weak', 'resist', 'hit_masks', 'coverage'):
        if [getattr(prepared, field)[i] for i in projection] != list(getattr(subset_prepared, field)):
            return None
    if [[prepared.overlap[i][j] for j in projection] for i in projection] != subset_prepared.overlap:
        return None
    args = dict(owned=owned, opportunities=opportunities, viability=viability,
                additions=additions, favorites=favorites, names=names)
    request = _request(prepared, category='Mixed', **args)
    if request is None:
        return None
    subargs = {key: [values[i] for i in subset] for key, values in args.items()}
    if _request(subset_prepared, category='Non-OG', **subargs) is None:
        return None
    binary, tokens = request
    tokens[0] = str(FUSED_PROTOCOL)
    indices = set(subset)
    tokens += [str(int(i in indices)) for i in range(n)]
    try:
        result = subprocess.run([str(binary)], input=' '.join(tokens), text=True,
                                capture_output=True, check=True)
        answer = json.loads(result.stdout)
        if not isinstance(answer, dict) or answer.get('protocol') != FUSED_PROTOCOL:
            return None
        mixed = _validate(answer.get('mixed'), prepared,
                          owned=owned, viability=viability, names=names)
        nonog = _validate(answer.get('nonog'), subset_prepared,
                          owned=subargs['owned'], viability=subargs['viability'], names=subargs['names'])
        if mixed is None or nonog is None or mixed['primary_skips'] or nonog['primary_skips']:
            return None
        if nonog['independent_combinations'] > mixed['independent_combinations']:
            return None
        return {'Mixed': mixed, 'Non-OG': nonog}
    except (OSError, subprocess.SubprocessError, ValueError, TypeError):
        return None
