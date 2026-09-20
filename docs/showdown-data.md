# Pinned Showdown data contract

`tools/showdown_data.py` is the shared source contract for the historical
Pokémon Showdown snapshot at commit
`e7aee8d9ccc983c59c5608929773249adca16b8f`. The canonical names are
`moves`, `pokedex`, `learnsets`, and `typechart`; each maps to a commit-pinned
`raw.githubusercontent.com` URL and an exact SHA-256. The files remain opaque
classic Showdown `.js` source so consumers can use the historical syntax
without silently converting it to another format.

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
previous cache untouched. The manifest and all four dataset files are installed
as one staged batch. Do not copy files into the cache by hand.

Every `get_text`, `get_path`, or `load` call verifies the manifest and hashes
**every cached dataset file** before returning. A wrong, missing, swapped, or
mixed file raises `CacheIntegrityError` (a downloaded hash mismatch raises
`HashMismatchError`) rather than returning partial data. `load(name)` returns
`LoadedDataset.text`, `LoadedDataset.path`, and `LoadedDataset.provenance`;
`provenance` contains the dataset name, filename, URL, commit, syntax label, and
SHA-256. The CLI `path`, `text`, and `provenance` commands expose the same
representations for inspection.

Tests use injected local byte downloaders and never access the network:

```text
python -m unittest discover -s tools/tests -v
```

Consumers are intentionally not wired to this loader yet.
