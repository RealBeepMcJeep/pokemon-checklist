"""Standard learnsets must use the ROM's form table, not a national-Dex-only join."""
import unittest
import json
import tempfile
from pathlib import Path
from unittest import mock
from tools import story_moves as story


class RegionalStandardMovesTests(unittest.TestCase):
    def test_app_move_builder_emits_exact_regional_finals_and_separate_game_profiles(self):
        from tools import build_moves as builder
        from tools.showdown_data import configured_cache_dir
        from tools.game_move_data import configured_cache_dir as game_cache
        cache = configured_cache_dir()
        if not cache.exists() or not (game_cache() / "pokemon_moves.csv").exists():
            self.skipTest("admitted Showdown/game-move caches not installed")
        data = builder.build(cache)
        self.assertTrue("53:alolan" in data["finals"], "App move payload has no regional final identity")
        self.assertEqual(data["lines"]["52:alolan"], ["53:alolan"])
        self.assertEqual(data["lines"]["52:kanto"], ["53:kanto"])
        self.assertEqual(data["lines"]["52"], [53], "legacy numeric consumers must remain readable")
        self.assertNotEqual(data["finals"]["53:alolan"]["moves"], data["finals"]["53:kanto"]["moves"])
        for final in ["53:alolan", "53:kanto", "475"]:
            for move in data["finals"][final]["moves"]:
                self.assertEqual(set(move["profiles"]), {"sm", "usum", "prismatic"})

    def test_target_projection_covers_the_catalogue_and_keeps_raw_internal_ids_private(self):
        from tools.build_capture_data import form_record_index
        raw = story.standard_levels()
        targets = story.standard_target_levels()
        forms = json.loads((story.ROOT / "data/regional-forms.json").read_text())["forms"]
        personal = (story.ROOT / "data/reference/capture/personal_uu").read_bytes()
        self.assertEqual(len(targets), 807 + len(forms))
        for key, form in forms.items():
            index = form_record_index(personal, form["id"], 1 if form["form"] == "alolan" else 0)
            self.assertEqual(targets[key], raw[index], key)
        self.assertNotIn("922", targets)
        self.assertNotIn("25:alolan", targets)
        self.assertNotIn("808", targets)

    def test_standard_target_join_refuses_changed_personal_source_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "data/reference/capture").mkdir(parents=True)
            source = bytearray((story.ROOT / "data/reference/capture/personal_uu").read_bytes())
            source[0] ^= 1
            (root / "data/reference/capture/personal_uu").write_bytes(source)
            with mock.patch.object(story, "ROOT", root), self.assertRaisesRegex(ValueError, "personal-table hash mismatch"):
                story.standard_target_levels()

    def test_personal_form_resolver_rejects_internal_form_record_numbers_as_species_ids(self):
        from tools.build_capture_data import form_record_index
        personal = (story.ROOT / "data/reference/capture/personal_uu").read_bytes()
        with self.assertRaisesRegex(ValueError, "species/form"):
            form_record_index(personal, 922, 0)

    def test_standard_target_join_refuses_a_swapped_regional_catalogue_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "data/reference/capture").mkdir(parents=True)
            for relative in ["data/pokemon.json", "data/reference/capture/personal_uu"]:
                (root / relative).write_bytes((story.ROOT / relative).read_bytes())
            data = json.loads((story.ROOT / "data/regional-forms.json").read_text())
            data["forms"]["53:alolan"]["id"] = 52
            (root / "data/regional-forms.json").write_text(json.dumps(data))
            with mock.patch.object(story, "ROOT", root), self.assertRaisesRegex(ValueError, "regional"):
                story.standard_target_levels()

    def test_standard_table_resolves_both_meowth_and_persian_forms_without_borrowing(self):
        resolver = getattr(story, "standard_target_levels", None)
        self.assertTrue(callable(resolver), "Standard learnsets have no collection-target identity resolver")
        raw = story.standard_levels()
        targets = resolver()
        self.assertEqual(targets["52:kanto"], raw[52])
        self.assertEqual(targets["53:kanto"], raw[53])
        self.assertEqual(targets["52:alolan"], raw[922])
        self.assertEqual(targets["53:alolan"], raw[923])
        self.assertNotEqual(targets["52:alolan"], targets["52:kanto"])
        self.assertNotEqual(targets["53:alolan"], targets["53:kanto"])
        self.assertEqual(targets["52"], raw[52], "legacy numeric readers must retain their original meaning")


if __name__ == "__main__":
    unittest.main()
