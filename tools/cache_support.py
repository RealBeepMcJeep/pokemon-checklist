"""Small stdlib-only helpers for external generator input caches."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


def default_cache_dir(name: str) -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return base / "pokemon-checklist" / name


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


@contextmanager
def staged_directory(target: Path) -> Iterator[Path]:
    """Build a cache in a temporary sibling, then promote it as one unit."""
    target = target.expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{target.name}.tmp-", dir=target.parent))
    backup: Path | None = None
    committed = False
    try:
        yield staging
        if target.exists():
            backup = Path(
                tempfile.mkdtemp(prefix=f".{target.name}.old-", dir=target.parent)
            )
            backup.rmdir()
            os.replace(target, backup)
        try:
            os.replace(staging, target)
            committed = True
        except Exception:
            if backup is not None and not target.exists():
                os.replace(backup, target)
            raise
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
        if committed and backup is not None and backup.exists():
            shutil.rmtree(backup, ignore_errors=True)


def write_manifest(path: Path, manifest: dict) -> None:
    path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
