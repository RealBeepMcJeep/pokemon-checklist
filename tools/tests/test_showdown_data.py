from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools import showdown_data as sd


class ShowdownDataStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.cache = Path(self.tempdir.name) / "cache"
        self.payloads = {
            "moves": b"exports.BattleMovedex = {\n\t tackle: {name: 'Tackle'},\n};\n",
            "pokedex": b"exports.BattlePokedex = {\n\t bulbasaur: {species: 'Bulbasaur'},\n};\n",
            "learnsets": b"exports.BattleLearnsets = {\n\t bulbasaur: {learnset: {tackle: ['1L']}},\n};\n",
            "typechart": b"exports.BattleTypeChart = {\n\t Normal: {damageTaken: {}},\n};\n",
            "tiers": b"exports.BattleFormatsData = {\n\t bulbasaur: {tier: 'PU'},\n};\n",
        }
        self.specs = {
            name: sd.DatasetSpec(
                name=name,
                filename=f"{name}.js",
                url=f"https://example.test/{name}.js",
                sha256=hashlib.sha256(payload).hexdigest(),
                commit="test-commit",
            )
            for name, payload in self.payloads.items()
        }
        self.downloads: list[str] = []

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def downloader(self, url: str) -> bytes:
        self.downloads.append(url)
        name = Path(url).stem
        return self.payloads[name]

    def store(self, downloader=None) -> sd.ShowdownDataStore:
        return sd.ShowdownDataStore(
            self.cache,
            datasets=self.specs,
            downloader=downloader or self.downloader,
        )

    def test_canonical_contract_has_commit_pinned_sources_and_known_hashes(self) -> None:
        expected_hashes = {
            "moves": "f1840be7a5a1006188c5be82235c99be0400c04adee75cf22c9f9c832f0bc849",
            "pokedex": "3d0f28348380c92cb01e0a9daebeba5ee12b6ed32899f583ed9f2b72029065d0",
            "learnsets": "97a2819325acac9c76b1b7a323bbe8e2bb77cf1f280f2c83f8d0a6f85aae36aa",
            "typechart": "2c150a39b84a8baacda1b91e1ad62afe93d27411d745bb29c9d5159236a92e39",
            "tiers": "5c6608b6c7b71f13d26ccf01963f16b94db8dfb87ed00420ecfc89708616d8c0",
        }
        expected_paths = {
            "moves": "/data/moves.js",
            "pokedex": "/data/pokedex.js",
            "learnsets": "/data/learnsets.js",
            "typechart": "/data/typechart.js",
            "tiers": "/data/mods/gen7/formats-data.js",
        }

        self.assertEqual(set(sd.DATASETS), set(expected_hashes))
        for name, expected_hash in expected_hashes.items():
            spec = sd.DATASETS[name]
            self.assertEqual(spec.commit, sd.SHOWDOWN_COMMIT)
            self.assertEqual(spec.sha256, expected_hash)
            self.assertIn(f"/{sd.SHOWDOWN_COMMIT}{expected_paths[name]}", spec.url)

    def test_bootstrap_returns_text_path_and_provenance_for_historical_js(self) -> None:
        store = self.store()

        paths = store.bootstrap()
        loaded = store.load("moves")

        self.assertEqual(set(paths), set(self.specs))
        self.assertEqual(loaded.text, self.payloads["moves"].decode())
        self.assertEqual(loaded.path, self.cache / "moves.js")
        self.assertEqual(loaded.provenance["commit"], "test-commit")
        self.assertEqual(loaded.provenance["sha256"], self.specs["moves"].sha256)
        self.assertEqual(len(self.downloads), len(self.specs))
        self.assertEqual(store.get_text("typechart"), self.payloads["typechart"].decode())
        self.assertEqual(store.get_path("learnsets"), self.cache / "learnsets.js")
        self.assertEqual(store.get_path("tiers"), self.cache / "tiers.js")

    def test_every_use_verifies_all_cached_files_and_rejects_corruption(self) -> None:
        store = self.store()
        store.bootstrap()
        (self.cache / "moves.js").write_bytes(b"corrupt")

        with self.assertRaises(sd.CacheIntegrityError) as raised:
            store.get_text("pokedex")

        self.assertIn("moves", str(raised.exception))

    def test_mixed_dataset_file_is_rejected_loudly(self) -> None:
        store = self.store()
        store.bootstrap()
        (self.cache / "moves.js").write_bytes((self.cache / "pokedex.js").read_bytes())

        with self.assertRaises(sd.CacheIntegrityError) as raised:
            store.verify_cache()

        self.assertIn("moves.js", str(raised.exception))
        self.assertIn("sha-256", str(raised.exception).lower())

    def test_failed_refresh_is_atomic_and_leaves_manifest_and_files_unchanged(self) -> None:
        store = self.store()
        store.bootstrap()
        before = {
            path.name: path.read_bytes()
            for path in self.cache.iterdir()
            if path.is_file()
        }

        def bad_downloader(url: str) -> bytes:
            if Path(url).stem == "typechart":
                return b"wrong bytes"
            return self.payloads[Path(url).stem]

        with self.assertRaises(sd.HashMismatchError):
            store.refresh(downloader=bad_downloader)

        after = {
            path.name: path.read_bytes()
            for path in self.cache.iterdir()
            if path.is_file()
        }
        self.assertEqual(after, before)
        self.assertEqual(list(self.cache.glob(".showdown-stage-*")), [])
        store.verify_cache()

    def test_bootstrap_repairs_corrupt_cache_only_when_explicitly_requested(self) -> None:
        store = self.store()
        store.bootstrap()
        (self.cache / "moves.js").write_bytes(b"corrupt")

        with self.assertRaises(sd.CacheIntegrityError):
            store.get_path("moves")

        store.bootstrap()
        self.assertEqual(store.get_text("moves"), self.payloads["moves"].decode())

    def test_manifest_records_the_complete_pinned_contract(self) -> None:
        store = self.store()
        store.bootstrap()

        manifest = json.loads((self.cache / sd.MANIFEST_FILENAME).read_text())

        self.assertEqual(manifest["commit"], "test-commit")
        self.assertEqual(set(manifest["datasets"]), set(self.specs))
        self.assertEqual(
            manifest["datasets"]["typechart"]["sha256"], self.specs["typechart"].sha256
        )
        self.assertEqual(
            manifest["datasets"]["tiers"]["filename"], "tiers.js"
        )


if __name__ == "__main__":
    unittest.main()
