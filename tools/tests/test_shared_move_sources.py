"""Preflight-to-render reuse is explicit and scoped to one admitted MoveSources object."""
import contextlib
import inspect
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import showdown_data as sd
import story_moves
import story_team_cards as cards


def raw_report():
    # Synthetic routing fixture, not a user's roster. Real acquisition resolution below.
    return {"utility": "Butterfree", "options": [
        {"members": [{"owned": "Gastly", "final": "Gengar"}]} for _ in range(5)]}


class SharedMoveSourcesTests(unittest.TestCase):
    def cache(self):
        cache = (Path(os.environ["SHOWDOWN_DATA_CACHE"]).expanduser() if
                 os.environ.get("SHOWDOWN_DATA_CACHE") else sd.configured_cache_dir())
        if not (cache / sd.MANIFEST_FILENAME).exists():
            self.skipTest("pinned Showdown cache not bootstrapped")
        return cache

    def test_existing_source_stays_consistent_but_default_store_and_next_constructor_reject_corruption(self):
        import shutil
        cache = self.cache()
        store = sd.require_cache(cache)
        with tempfile.TemporaryDirectory() as tmp:
            clone = Path(tmp) / "cache"
            clone.mkdir()
            for path in store.verify_cache().values():
                shutil.copy2(path, clone / path.name)
            shutil.copy2(cache / sd.MANIFEST_FILENAME, clone / sd.MANIFEST_FILENAME)
            admitted = sd.require_cache(clone)
            source = story_moves.MoveSources(clone)
            expected = cards.add_move_targets(raw_report(), clone, move_sources=source)
            paths = admitted.verify_cache()
            paths["moves"].write_text("corrupt after preflight")
            self.assertEqual(cards.add_move_targets(raw_report(), clone, move_sources=source), expected)
            with self.assertRaises(sd.CacheIntegrityError):
                admitted.get_text("moves")
            with self.assertRaises(sd.CacheIntegrityError):
                story_moves.MoveSources(clone)

    def test_goals_are_resolved_again_by_the_same_source_not_cached_targets(self):
        cache = self.cache()
        source = story_moves.MoveSources(cache)
        first = source.targets("Butterfree", "Butterfree")
        changed = tuple(m["name"] for m in reversed(first))
        with mock.patch.dict(story_moves.GOALS, {"Butterfree": changed}):
            actual = cards.add_move_targets(raw_report(), cache, move_sources=source)
        self.assertEqual(tuple(m["name"] for m in actual["utility_moves"]), changed)
        self.assertNotEqual(actual["utility_moves"], first)
        self.assertEqual(source.targets("Butterfree", "Butterfree"), first)

    def test_cache_identity_is_bound_before_admission_if_an_alias_changes_mid_load(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            before, after, alias = root / "before", root / "after", root / "alias"
            before.mkdir()
            after.mkdir()
            alias.symlink_to(before, target_is_directory=True)
            def admit(path):
                alias.unlink()
                alias.symlink_to(after, target_is_directory=True)
                return SimpleNamespace()
            with mock.patch.object(story_moves.ml, "load_move_data", side_effect=admit) as load, \
                 mock.patch.object(story_moves, "standard_levels", return_value={}):
                source = story_moves.MoveSources(alias)
            self.assertEqual(source.cache_dir, before.resolve(), "metadata must name the admitted directory, not the later alias")
            self.assertEqual(load.call_args.args[0], before.resolve())

    def test_shared_target_error_propagates_without_output_or_silent_reconstruction(self):
        from types import SimpleNamespace
        from typing import cast
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cache = root / "cache"
            raw = root / "raw.json"
            raw.write_text(json.dumps(raw_report()))
            source = cast(story_moves.MoveSources, SimpleNamespace(
                cache_dir=cache.resolve(), targets=mock.Mock(side_effect=ValueError("source gate failure"))))
            with mock.patch.object(story_moves, "MoveSources", side_effect=AssertionError("silent reconstruction")):
                with self.assertRaisesRegex(ValueError, "source gate failure"):
                    cards.main(["--report-json", str(raw), "--cache", str(cache),
                                "--output-dir", str(root / "cards")], move_sources=source)
            self.assertFalse((root / "cards").exists())
            self.assertTrue(raw.exists(), "the caller's real raw report must be retained")

    def test_source_from_different_cache_is_rejected_before_any_target_use(self):
        from types import SimpleNamespace
        from typing import cast
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            targets = mock.Mock(return_value=[{"name": "routing fixture"}] * 4)
            # A negative-boundary double; no real source admission is needed.
            source = cast(story_moves.MoveSources, SimpleNamespace(
                cache_dir=(root / "other").resolve(), targets=targets))
            with self.assertRaisesRegex(ValueError, "does not match"):
                cards.add_move_targets(raw_report(), root / "wanted", move_sources=source)
            targets.assert_not_called()

    def test_preflight_instance_is_used_without_a_second_source_construction(self):
        cache = self.cache()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw = raw_report()
            path = root / "raw.json"
            path.write_text(json.dumps(raw))
            constructor = story_moves.MoveSources
            def render(report, option, number, atlas, output, **kwargs):
                output.write_bytes(b"routing fixture, not a PNG")
            with mock.patch.object(story_moves, "MoveSources", wraps=constructor) as builds:
                source = story_moves.MoveSources(cache)
                with mock.patch.object(source, "targets", wraps=source.targets) as targets:
                    self.assertEqual(len(source.targets("Butterfree", "Butterfree")), 4)
                    self.assertEqual(len(source.targets("Gengar", "Gastly")), 4)
                    # Run the OLD entrypoint as the real RED control, rather than
                    # erroring on a keyword the old signature does not accept.
                    supported = "move_sources" in inspect.signature(cards.main).parameters
                    kwargs = {"move_sources": source} if supported else {}
                    with mock.patch.object(cards, "render_card", side_effect=render), \
                         contextlib.redirect_stdout(io.StringIO()):
                        code = cards.main(["--report-json", str(path), "--cache", str(cache),
                                           "--output-dir", str(root / "cards")], **kwargs)
                self.assertEqual(code, 0)
                self.assertEqual(builds.call_count, 1, "preflight and enrichment must share one source admission")
                self.assertTrue(supported, "renderer must expose the explicit run-scoped injection boundary")
                self.assertEqual(targets.call_count, 8, "preflight2 + real enrichment6 must use THAT instance")
                enriched = json.loads((root / "cards/story-options.json").read_text())
                self.assertEqual(len(enriched["utility_moves"]), 4)
                self.assertTrue(all(len(o["members"][0]["moves"]) == 4 for o in enriched["options"]))
                self.assertNotIn("utility_moves", raw)


if __name__ == "__main__":
    unittest.main()
