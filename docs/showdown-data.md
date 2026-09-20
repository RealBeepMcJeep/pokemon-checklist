# Pinned Showdown data contract

`tools/showdown_data.py` is the shared source contract used by `tools/moveline.py`
and other data tooling for the historical Pokémon Showdown snapshot at commit
`e7aee8d9ccc983c59c5608929773249adca16b8f`. The canonical names are
`moves`, `pokedex`, `learnsets`, `typechart`, and `tiers`; each maps to a
commit-pinned `raw.githubusercontent.com` URL and an exact SHA-256. `tiers` is
Showdown's `data/mods/gen7/formats-data.js`. The files remain opaque classic
Showdown `.js` source so consumers can use the historical syntax without
silently converting it to another format. Smogon usage-stat files are not part
of this contract.

## Bootstrap and refresh

The cache is outside the repository by default:

```text
python tools/showdown_data.py bootstrap
python tools/showdown_data.py --cache-dir /tmp/pokemon-showdown-data bootstrap
python tools/showdown_data.py --cache-dir /tmp/pokemon-showdown-data refresh
python tools/showdown_data.py --cache-dir /tmp/pokemon-showdown-data verify
```

`bootstrap` is idempotent: an exact cache is reused, while a missing, corrupt,
or mixed cache is rebuilt. `refresh` explicitly downloads every file. Downloads
are written to a same-directory staging area, hash-checked and UTF-8 checked,
then replaced with `os.replace`; a failed download or hash check leaves the
previous cache untouched. The manifest and all five dataset files are installed
as one staged batch. Do not copy files into the cache by hand.

Every `get_text`, `get_path`, or `load` call verifies the manifest and hashes
**every cached dataset file** before returning. A wrong, missing, swapped, or
mixed file raises `CacheIntegrityError` (a downloaded hash mismatch raises
`HashMismatchError`) rather than returning partial data. `load(name)` returns
`LoadedDataset.text`, `LoadedDataset.path`, and `LoadedDataset.provenance`;
`provenance` contains the dataset name, filename, URL, commit, syntax label, and
SHA-256. The CLI `path`, `text`, and `provenance` commands expose the same
representations for inspection.

Analysis commands use their existing `--cache` option as this shared store.
Run bootstrap explicitly before the first analysis (and after changing the
cache location):

```text
python tools/showdown_data.py --cache-dir /tmp/pokemon-showdown-data bootstrap
python tools/moveline.py ralts --cache /tmp/pokemon-showdown-data
python tools/catcher_score.py --species ralts --cache /tmp/pokemon-showdown-data
```

Analysis commands verify the complete cache and fail with a bootstrap hint;
they never download or repair Showdown files. Only the explicit `bootstrap` and
`refresh` commands download Showdown data. Some analysis reports may still
cache separately acquired Smogon usage snapshots in the same directory; those
files are not pinned by this contract.

Tests use injected local byte downloaders and never access the network:

```text
python -m unittest tools.tests.test_showdown_data -v
python -m unittest tools.tests.test_moveline.MoveLineHardeningTests.test_pinned_showdown_loader_uses_injected_local_store -v
```

`tools/moveline.py` uses this loader for its moves, Pokédex, and learnset inputs. Its explicit
`--cache` directory is the verified contract cache; it no longer downloads Showdown `master` data.
The historical Smogon moveset files used for ranking are separate, hash-verified snapshots and
an unavailable tier is skipped while corruption or a network error stops the report.

`build_pokedex_details.py` also requires a bootstrapped `--cache`; it downloads
only its separate, hash-pinned Smogon usage snapshot when regeneration is
explicitly requested.
