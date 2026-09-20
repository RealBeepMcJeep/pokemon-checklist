import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image

from tools import build_icons as icons
from tools import build_vanilla_encounters as vanilla


class GeneratorCacheTests(unittest.TestCase):
    @staticmethod
    def icon_bytes() -> bytes:
        output = io.BytesIO()
        Image.new("RGBA", icons.FRAME, (1, 2, 3, 255)).save(output, format="PNG")
        return output.getvalue()

    def test_icon_refresh_is_injected_and_cache_reads_are_offline(self):
        raw_icon = self.icon_bytes()
        license_raw = b"fixture license\n"
        calls = []

        def downloader(url):
            calls.append(url)
            return license_raw if url == icons.LICENSE_URL else raw_icon

        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary) / "icons"
            icons.refresh_cache(cache, downloader)
            self.assertEqual(len(calls), icons.COUNT + 1)
            cached, cached_license = icons.read_inputs(cache)
            self.assertEqual(len(cached), icons.COUNT)
            self.assertEqual(cached_license, license_raw)
            with mock.patch.object(icons, "download_bytes", side_effect=AssertionError("network")):
                icons.read_inputs(cache)

    def test_icon_check_accepts_equivalent_crlf_committed_license(self):
        raw_icon = self.icon_bytes()
        license_raw = b"fixture license\nsecond line\n"

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cache = root / "icons"
            output = root / "assets" / "gen7-icons.png"
            license_output = root / "references" / "PokeAPI-sprites-LICENCE.txt"
            icons.refresh_cache(
                cache,
                lambda url: license_raw if url == icons.LICENSE_URL else raw_icon,
            )
            output.parent.mkdir()
            output.write_bytes(icons.atlas_bytes({dex: raw_icon for dex in range(1, icons.COUNT + 1)}))
            license_output.parent.mkdir()
            license_output.write_bytes(license_raw.replace(b"\n", b"\r\n"))

            with mock.patch.object(icons, "ROOT", root), mock.patch.object(
                icons, "OUT", output
            ), mock.patch.object(icons, "LICENSE_OUT", license_output):
                icons.build(cache, check=True)

    def test_icon_cache_rejects_missing_corrupt_and_mixed_inputs(self):
        raw_icon = self.icon_bytes()

        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary) / "icons"
            icons.refresh_cache(cache, lambda url: b"license\n" if url == icons.LICENSE_URL else raw_icon)
            (cache / "icons" / "001.png").write_bytes(b"corrupt")
            with self.assertRaisesRegex(icons.CacheError, "corrupted or mixed"):
                icons.read_inputs(cache)

            icons.refresh_cache(cache, lambda url: b"license\n" if url == icons.LICENSE_URL else raw_icon)
            manifest_path = cache / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["sourceCommit"] = "master"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(icons.CacheError, "stale"):
                icons.read_inputs(cache)

        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(icons.CacheError, "--refresh"):
                icons.read_inputs(Path(temporary) / "missing")

    def test_icon_source_is_commit_pinned(self):
        self.assertIn(icons.SOURCE_COMMIT, icons.ICON_URL)
        self.assertNotIn("/master/", icons.ICON_URL)
        self.assertIn(icons.SOURCE_COMMIT, icons.LICENSE_URL)

    def test_vanilla_csv_refresh_writes_cache_and_never_downloads_on_read(self):
        calls = []

        def downloader(url):
            calls.append(url)
            return (f"fixture for {url}\n").encode("utf-8")

        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary) / "vanilla"
            vanilla.refresh_cache(cache, [], downloader)
            self.assertEqual(len(calls), len(vanilla.CSV_FILES))
            manifest = json.loads((cache / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["pokeapiCommit"], vanilla.POKEAPI_COMMIT)
            self.assertEqual(set(manifest["csv"]), set(vanilla.CSV_FILES))
            vanilla.load_csv_sources(None, cache)
            with mock.patch.object(vanilla, "download_bytes", side_effect=AssertionError("network")):
                vanilla.load_csv_sources(None, cache)

    def test_vanilla_refresh_records_pinned_table_identity(self):
        table_raw = b"fixture table\n"
        table_hash = hashlib.sha256(table_raw).hexdigest()
        config = dict(vanilla.GAME_CONFIGS["sun"])
        config.update(
            tableSources=[("https://example.test/sun-table", table_hash)],
            tableRevision="fixture-revision",
            tableHash=table_hash,
        )

        def downloader(url):
            if url == "https://example.test/sun-table":
                return table_raw
            return b"fixture csv\n"

        with tempfile.TemporaryDirectory() as temporary, mock.patch.dict(
            vanilla.GAME_CONFIGS, {"sun": config}, clear=False
        ):
            cache = Path(temporary) / "vanilla"
            vanilla.refresh_cache(cache, ["sun"], downloader)
            self.assertEqual(vanilla.load_table("sun", None, cache), "fixture table\n")
            manifest = json.loads((cache / "manifest.json").read_text(encoding="utf-8"))
            table = manifest["tables"]["sun"]
            self.assertEqual(table["sourceRevision"], "fixture-revision")
            self.assertEqual(table["expectedSha256"], table_hash)
            self.assertEqual(table["sources"][0]["sha256"], table_hash)

    def test_vanilla_refresh_preserves_raw_bytes_for_multi_source_tables(self):
        first = b"first\r\nrow\r\n"
        second = b"second\r\nrow\r\n"
        combined = b"\n".join((first, second))
        config = dict(vanilla.GAME_CONFIGS["moon"])
        config.update(
            tableSources=[
                ("https://example.test/moon-first", hashlib.sha256(first).hexdigest()),
                ("https://example.test/moon-second", hashlib.sha256(second).hexdigest()),
            ],
            tableRevision="fixture-revision",
            tableHash=hashlib.sha256(combined).hexdigest(),
        )

        def downloader(url):
            return {
                "https://example.test/moon-first": first,
                "https://example.test/moon-second": second,
            }.get(url, b"fixture csv\n")

        with tempfile.TemporaryDirectory() as temporary, mock.patch.dict(
            vanilla.GAME_CONFIGS, {"moon": config}, clear=False
        ):
            cache = Path(temporary) / "vanilla"
            vanilla.refresh_cache(cache, ["moon"], downloader)
            self.assertEqual(vanilla.load_table("moon", None, cache), "first\nrow\n\nsecond\nrow\n")
            self.assertEqual((cache / "tables" / "moon.txt").read_bytes(), combined)

    def test_vanilla_cache_rejects_corruption_and_missing_cache_explains_refresh(self):
        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary) / "vanilla"
            vanilla.refresh_cache(cache, [], lambda url: b"fixture csv\n")
            (cache / "csv" / vanilla.CSV_FILES[0]).write_bytes(b"changed")
            with self.assertRaisesRegex(vanilla.CacheError, "corrupted or mixed"):
                vanilla.load_csv_sources(None, cache)

            with self.assertRaisesRegex(vanilla.CacheError, "--refresh"):
                vanilla.load_csv_sources(None, Path(temporary) / "missing")

    def test_vanilla_download_uses_a_finite_timeout(self):
        class Response:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            @staticmethod
            def read():
                return b"fixture"

        with mock.patch.object(vanilla.urllib.request, "urlopen", return_value=Response()) as urlopen:
            vanilla.download_bytes("https://example.test/source")
        self.assertEqual(urlopen.call_args.kwargs["timeout"], vanilla.DOWNLOAD_TIMEOUT)
        self.assertGreater(vanilla.DOWNLOAD_TIMEOUT, 0)


if __name__ == "__main__":
    unittest.main()
