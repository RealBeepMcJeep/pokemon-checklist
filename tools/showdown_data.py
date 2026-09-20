#!/usr/bin/env python3
"""Load the commit-pinned historical Pokémon Showdown JavaScript datasets.

The files are deliberately treated as opaque classic Showdown ``.js`` source.
Consumers can request the exact text or a verified filesystem path; parsing stays
with the consumer because this contract owns source identity, not data semantics.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Callable, Mapping

SHOWDOWN_COMMIT = "e7aee8d9ccc983c59c5608929773249adca16b8f"
MANIFEST_FILENAME = "showdown-manifest.json"
CONTRACT_ID = "pokemon-checklist.showdown-data"
CACHE_ENVIRONMENT_VARIABLE = "SHOWDOWN_DATA_CACHE"
DEFAULT_CACHE_DIR = (
    Path(os.environ.get(CACHE_ENVIRONMENT_VARIABLE, "~/.cache/pokemon-checklist/showdown"))
    .expanduser()
)


def configured_cache_dir() -> Path:
    """Return the shared store path used by analysis-tool CLI defaults."""

    return Path(os.environ.get("POKE_DATA_CACHE", str(DEFAULT_CACHE_DIR))).expanduser()


def bootstrap_hint(cache_dir: str | os.PathLike[str]) -> str:
    return f'python tools/showdown_data.py --cache-dir "{Path(cache_dir)}" bootstrap'


class ShowdownDataError(RuntimeError):
    """Base class for a missing, corrupt, or unusable pinned-data cache."""


class UnknownDatasetError(ShowdownDataError):
    """The caller requested a dataset outside the shared contract."""


class CacheIntegrityError(ShowdownDataError):
    """The cache is missing, corrupt, or contains mixed contract metadata."""


class HashMismatchError(CacheIntegrityError):
    """Downloaded or cached bytes do not match the pinned SHA-256."""


class DownloadError(ShowdownDataError):
    """A pinned source could not be downloaded."""


@dataclass(frozen=True)
class DatasetSpec:
    """Immutable identity and provenance for one Showdown source file."""

    name: str
    filename: str
    url: str
    sha256: str
    commit: str = SHOWDOWN_COMMIT
    syntax: str = "classic-showdown-js"

    def __post_init__(self) -> None:
        if not self.name or not self.filename:
            raise ValueError("dataset name and filename are required")
        if Path(self.filename).name != self.filename:
            raise ValueError(f"dataset filename must be a plain name: {self.filename}")
        if re.fullmatch(r"[0-9a-f]{64}", self.sha256) is None:
            raise ValueError(f"dataset {self.name} has an invalid SHA-256")

    def provenance(self) -> dict[str, str]:
        """Return serializable source provenance for this dataset."""

        return {
            "name": self.name,
            "filename": self.filename,
            "url": self.url,
            "sha256": self.sha256,
            "commit": self.commit,
            "syntax": self.syntax,
        }


# These are the only canonical dataset names exposed by this contract.
DATASETS: Mapping[str, DatasetSpec] = MappingProxyType(
    {
        "moves": DatasetSpec(
            name="moves",
            filename="moves.js",
            url=f"https://raw.githubusercontent.com/smogon/pokemon-showdown/{SHOWDOWN_COMMIT}/data/moves.js",
            sha256="f1840be7a5a1006188c5be82235c99be0400c04adee75cf22c9f9c832f0bc849",
        ),
        "pokedex": DatasetSpec(
            name="pokedex",
            filename="pokedex.js",
            url=f"https://raw.githubusercontent.com/smogon/pokemon-showdown/{SHOWDOWN_COMMIT}/data/pokedex.js",
            sha256="3d0f28348380c92cb01e0a9daebeba5ee12b6ed32899f583ed9f2b72029065d0",
        ),
        "learnsets": DatasetSpec(
            name="learnsets",
            filename="learnsets.js",
            url=f"https://raw.githubusercontent.com/smogon/pokemon-showdown/{SHOWDOWN_COMMIT}/data/learnsets.js",
            sha256="97a2819325acac9c76b1b7a323bbe8e2bb77cf1f280f2c83f8d0a6f85aae36aa",
        ),
        "typechart": DatasetSpec(
            name="typechart",
            filename="typechart.js",
            url=f"https://raw.githubusercontent.com/smogon/pokemon-showdown/{SHOWDOWN_COMMIT}/data/typechart.js",
            sha256="2c150a39b84a8baacda1b91e1ad62afe93d27411d745bb29c9d5159236a92e39",
        ),
        "tiers": DatasetSpec(
            name="tiers",
            filename="formats-data.js",
            url=f"https://raw.githubusercontent.com/smogon/pokemon-showdown/{SHOWDOWN_COMMIT}/data/mods/gen7/formats-data.js",
            sha256="5c6608b6c7b71f13d26ccf01963f16b94db8dfb87ed00420ecfc89708616d8c0",
        ),
    }
)
# Alias with an explicit name for callers that prefer the manifest terminology.
DATASET_SPECS = DATASETS


@dataclass(frozen=True)
class LoadedDataset:
    """A verified source with both consumer-facing representations."""

    name: str
    text: str
    path: Path
    provenance: Mapping[str, str]


Downloader = Callable[[str], bytes]


def _sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as error:
        raise CacheIntegrityError(f"cannot read cached dataset {path}") from error
    return digest.hexdigest()


def _download_url(url: str, timeout: float = 30.0) -> bytes:
    """Download one approved pinned URL; callers still verify its hash."""

    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "raw.githubusercontent.com":
        raise DownloadError(f"unapproved Showdown source URL: {url}")
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "pokemon-checklist-showdown-data"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            if response.status != 200:
                raise DownloadError(f"cannot download {url}: HTTP {response.status}")
            return response.read()
    except DownloadError:
        raise
    except (OSError, urllib.error.URLError) as error:
        raise DownloadError(f"cannot download {url}") from error


def _json_read(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise CacheIntegrityError(f"cannot read valid cache manifest {path}") from error


def _fsync_directory(path: Path) -> None:
    """Make directory entry replacement durable where the platform permits it."""

    try:
        descriptor = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


class ShowdownDataStore:
    """Manage one complete, verified cache of the pinned Showdown contract."""

    def __init__(
        self,
        cache_dir: str | os.PathLike[str] = DEFAULT_CACHE_DIR,
        *,
        datasets: Mapping[str, DatasetSpec] = DATASETS,
        downloader: Downloader | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.cache_dir = Path(cache_dir).expanduser()
        self.datasets = dict(datasets)
        self._downloader = downloader
        self.timeout = timeout
        self._validate_datasets()

    @property
    def manifest_path(self) -> Path:
        return self.cache_dir / MANIFEST_FILENAME

    def _validate_datasets(self) -> None:
        if not self.datasets:
            raise ValueError("at least one dataset is required")
        if set(self.datasets) != {spec.name for spec in self.datasets.values()}:
            raise ValueError("dataset mapping keys must equal DatasetSpec.name values")
        commits = {spec.commit for spec in self.datasets.values()}
        if len(commits) != 1:
            raise ValueError("all datasets must use one pinned Showdown commit")

    def _spec(self, name: str) -> DatasetSpec:
        try:
            return self.datasets[name]
        except KeyError as error:
            valid = ", ".join(sorted(self.datasets))
            raise UnknownDatasetError(
                f"unknown Showdown dataset {name!r}; expected one of: {valid}"
            ) from error

    def _manifest(self) -> dict[str, object]:
        commit = next(iter(self.datasets.values())).commit
        return {
            "contract": CONTRACT_ID,
            "commit": commit,
            "datasets": {
                name: self.datasets[name].provenance() for name in sorted(self.datasets)
            },
        }

    def _cached_path(self, spec: DatasetSpec) -> Path:
        return self.cache_dir / spec.filename

    def verify_cache(self) -> dict[str, Path]:
        """Verify manifest and every dataset file, returning verified paths."""

        if not self.cache_dir.is_dir():
            raise CacheIntegrityError(f"Showdown cache directory is missing: {self.cache_dir}")
        actual_manifest = _json_read(self.manifest_path)
        expected_manifest = self._manifest()
        if actual_manifest != expected_manifest:
            raise CacheIntegrityError(
                "Showdown cache manifest does not match the pinned contract; "
                "cache is corrupt or mixed"
            )

        paths: dict[str, Path] = {}
        for name in sorted(self.datasets):
            spec = self.datasets[name]
            path = self._cached_path(spec)
            if path.is_symlink() or not path.is_file():
                raise CacheIntegrityError(f"missing cached Showdown dataset: {path}")
            actual_hash = _sha256_file(path)
            if actual_hash != spec.sha256:
                raise HashMismatchError(
                    f"cached {name} ({path.name}) has the wrong SHA-256: "
                    f"expected {spec.sha256}, got {actual_hash}"
                )
            try:
                path.read_bytes().decode("utf-8")
            except (OSError, UnicodeError) as error:
                raise CacheIntegrityError(f"cached dataset is not UTF-8: {path}") from error
            paths[name] = path
        return paths

    def _download(self, url: str) -> bytes:
        if self._downloader is not None:
            raw = self._downloader(url)
        else:
            raw = _download_url(url, self.timeout)
        if not isinstance(raw, bytes):
            raise DownloadError(f"downloader returned non-bytes for {url}")
        return raw

    @staticmethod
    def _write_bytes(path: Path, raw: bytes) -> None:
        try:
            with path.open("wb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
        except OSError as error:
            raise DownloadError(f"cannot write staged Showdown dataset {path}") from error

    def bootstrap(self) -> dict[str, Path]:
        """Create or repair the cache, downloading only when it is not valid."""

        try:
            return self.verify_cache()
        except ShowdownDataError:
            return self._install()

    def refresh(self, *, downloader: Downloader | None = None) -> dict[str, Path]:
        """Explicitly redownload every pinned file and replace the cache atomically."""

        if downloader is None:
            return self._install()
        original = self._downloader
        self._downloader = downloader
        try:
            return self._install()
        finally:
            self._downloader = original

    def _install(self) -> dict[str, Path]:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        stage = Path(tempfile.mkdtemp(prefix=".showdown-stage-", dir=self.cache_dir))
        try:
            for name in sorted(self.datasets):
                spec = self.datasets[name]
                raw = self._download(spec.url)
                actual_hash = _sha256_bytes(raw)
                if actual_hash != spec.sha256:
                    raise HashMismatchError(
                        f"downloaded {name} ({spec.filename}) has the wrong SHA-256: "
                        f"expected {spec.sha256}, got {actual_hash}"
                    )
                try:
                    raw.decode("utf-8")
                except UnicodeError as error:
                    raise CacheIntegrityError(
                        f"downloaded dataset is not UTF-8: {spec.url}"
                    ) from error
                self._write_bytes(stage / spec.filename, raw)

            manifest_stage = stage / MANIFEST_FILENAME
            self._write_bytes(
                manifest_stage,
                (json.dumps(self._manifest(), indent=2, sort_keys=True) + "\n").encode(
                    "utf-8"
                ),
            )
            for name in sorted(self.datasets):
                spec = self.datasets[name]
                os.replace(stage / spec.filename, self._cached_path(spec))
            os.replace(manifest_stage, self.manifest_path)
            _fsync_directory(self.cache_dir)
        except (OSError, ShowdownDataError) as error:
            if isinstance(error, ShowdownDataError):
                raise
            raise DownloadError(f"cannot install Showdown cache in {self.cache_dir}") from error
        finally:
            shutil.rmtree(stage, ignore_errors=True)

        return self.verify_cache()

    def load(self, name: str, *, refresh: bool = False) -> LoadedDataset:
        """Return verified text, path, and provenance for one canonical dataset."""

        if refresh:
            self.refresh()
        paths = self.verify_cache()
        spec = self._spec(name)
        path = paths[name]
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            raise CacheIntegrityError(f"cannot read verified dataset {path}") from error
        return LoadedDataset(
            name=name,
            text=text,
            path=path,
            provenance=MappingProxyType(spec.provenance()),
        )

    def get_text(self, name: str, *, refresh: bool = False) -> str:
        return self.load(name, refresh=refresh).text

    def get_path(self, name: str, *, refresh: bool = False) -> Path:
        return self.load(name, refresh=refresh).path

    def provenance(self, name: str | None = None) -> dict[str, object] | dict[str, str]:
        """Return one dataset's provenance or the full contract metadata."""

        if name is not None:
            return self._spec(name).provenance()
        return self._manifest()


def get_dataset(
    name: str,
    *,
    cache_dir: str | os.PathLike[str] = DEFAULT_CACHE_DIR,
    refresh: bool = False,
) -> LoadedDataset:
    """Convenience loader for consumers that need both text and path."""

    return ShowdownDataStore(cache_dir).load(name, refresh=refresh)


def require_cache(cache_dir: str | os.PathLike[str]) -> ShowdownDataStore:
    """Return a verified store without ever repairing or downloading it."""

    store = ShowdownDataStore(cache_dir)
    try:
        store.verify_cache()
    except ShowdownDataError as error:
        raise CacheIntegrityError(
            f"{error}; bootstrap the shared cache first with `{bootstrap_hint(cache_dir)}`"
        ) from error
    return store


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=DEFAULT_CACHE_DIR,
        help=f"cache directory (default: ${CACHE_ENVIRONMENT_VARIABLE} or {DEFAULT_CACHE_DIR})",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("bootstrap", "refresh", "verify"):
        subparsers.add_parser(command, help=f"{command} the complete pinned cache")
    for command in ("path", "text", "provenance"):
        subparser = subparsers.add_parser(
            command, help="read the verified shared cache (bootstrap it first)"
        )
        if command != "provenance":
            subparser.add_argument("dataset", choices=sorted(DATASETS))
        else:
            subparser.add_argument("dataset", choices=sorted(DATASETS), nargs="?")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    store = ShowdownDataStore(args.cache_dir)
    try:
        if args.command == "bootstrap":
            store.bootstrap()
            print(f"bootstrapped {len(DATASETS)} Showdown datasets in {store.cache_dir}")
        elif args.command == "refresh":
            store.refresh()
            print(f"refreshed {len(DATASETS)} Showdown datasets in {store.cache_dir}")
        elif args.command == "verify":
            store.verify_cache()
            print(f"verified {len(DATASETS)} Showdown datasets in {store.cache_dir}")
        elif args.command == "path":
            print(store.get_path(args.dataset))
        elif args.command == "text":
            sys.stdout.write(store.get_text(args.dataset))
        elif args.command == "provenance":
            print(json.dumps(store.provenance(args.dataset), indent=2, sort_keys=True))
    except ShowdownDataError as error:
        print(
            f"showdown-data: {error}; bootstrap first with `{bootstrap_hint(args.cache_dir)}`",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
