"""Explicit, synthetic CSV subsets exercise version/form isolation without network."""
import importlib
import importlib.util
import unittest
import copy
import tempfile
import hashlib
from pathlib import Path


TABLES = {
    "pokemon.csv": [
        {"id": "53", "species_id": "53", "identifier": "persian", "is_default": "1"},
        {"id": "10108", "species_id": "53", "identifier": "persian-alola", "is_default": "0"},
    ],
    "moves.csv": [
        {"id": "282", "identifier": "knock-off", "generation_id": "3"},
        {"id": "44", "identifier": "bite", "generation_id": "1"},
    ],
    "version_groups.csv": [
        {"id": "17", "identifier": "sun-moon", "generation_id": "7"},
        {"id": "18", "identifier": "ultra-sun-ultra-moon", "generation_id": "7"},
    ],
    "pokemon_move_methods.csv": [{"id": "1", "identifier": "level-up"}, {"id": "3", "identifier": "tutor"}],
    "machines.csv": [],
    "pokemon_moves.csv": [
        {"pokemon_id": "10108", "version_group_id": "18", "move_id": "282", "pokemon_move_method_id": "3", "level": "0"},
        {"pokemon_id": "53", "version_group_id": "17", "move_id": "44", "pokemon_move_method_id": "1", "level": "6"},
    ],
}
TARGETS = [{"key": "53:kanto", "id": 53, "form": "kanto", "showdownKey": "persian"},
           {"key": "53:alolan", "id": 53, "form": "alolan", "showdownKey": "persianalola"}]


class GameMoveDataTests(unittest.TestCase):
    def project(self, tables=TABLES, targets=TARGETS):
        self.assertIsNotNone(importlib.util.find_spec("tools.game_move_data"), "Version-specific move-source projection is absent")
        return importlib.import_module("tools.game_move_data").project_sources(tables, targets)

    def test_local_source_reader_admits_only_pinned_bytes_and_never_repairs_corruption(self):
        module = importlib.import_module("tools.game_move_data")
        reader = getattr(module, "load_tables", None)
        self.assertTrue(callable(reader), "No offline, hash-pinned CSV admission exists")
        payload = b"id,identifier,generation_id\n17,sun-moon,7\n18,ultra-sun-ultra-moon,7\n"
        pins = {"version_groups.csv": ("https://example.invalid/fixture", hashlib.sha256(payload).hexdigest())}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "version_groups.csv"
            path.write_bytes(payload)
            self.assertEqual(reader(Path(directory), pins)["version_groups.csv"][0]["identifier"], "sun-moon")
            path.write_bytes(payload + b"corruption")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                reader(Path(directory), pins)
            self.assertEqual(path.read_bytes(), payload + b"corruption")

    def test_machine_numbers_and_special_learning_methods_keep_their_source_meaning(self):
        tables = copy.deepcopy(TABLES)
        tables["pokemon_move_methods.csv"] += [
            {"id": "2", "identifier": "egg"}, {"id": "4", "identifier": "machine"},
            {"id": "6", "identifier": "light-ball-egg"}, {"id": "10", "identifier": "form-change"},
            {"id": "11", "identifier": "zygarde-cube"}]
        tables["machines.csv"] = [{"version_group_id": "18", "move_id": "44", "machine_number": "99"}]
        tables["pokemon_moves.csv"] = [
            {"pokemon_id": "53", "version_group_id": "18", "move_id": "44", "pokemon_move_method_id": method, "level": "0"}
            for method in ["2", "4", "6", "10", "11"]]
        self.assertEqual(self.project(tables)["53:kanto"]["usum"]["bite"], [
            {"via": "egg"}, {"via": "TM", "tm": 99},
            {"via": "egg", "note": "Breed with a parent holding Light Ball"},
            {"via": "special", "note": "Change form"}, {"via": "special", "note": "Zygarde Cube"}])

    def test_level_zero_and_one_are_evolution_and_reminder_not_ordinary_levels(self):
        tables = copy.deepcopy(TABLES)
        tables["pokemon_moves.csv"] = [
            {"pokemon_id": "10108", "version_group_id": "18", "move_id": "44", "pokemon_move_method_id": "1", "level": str(level)}
            for level in [0, 1, 6]
        ]
        self.assertEqual(self.project(tables)["53:alolan"]["usum"]["bite"], [
            {"via": "evolution"}, {"via": "reminder"}, {"via": "level", "level": 6}])

    def test_explicit_bootstrap_checks_all_bytes_before_replacing_a_good_cache(self):
        module = importlib.import_module("tools.game_move_data")
        bootstrap = getattr(module, "bootstrap", None)
        self.assertTrue(callable(bootstrap), "Pinned CSV sources have no reproducible bootstrap")
        payload = b"id,identifier,generation_id\n17,sun-moon,7\n18,ultra-sun-ultra-moon,7\n"
        pins = {"version_groups.csv": ("https://example.invalid/fixture", hashlib.sha256(payload).hexdigest())}
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "cache"
            bootstrap(cache, downloader=lambda url: payload, sources=pins)
            self.assertEqual(module.load_tables(cache, pins)["version_groups.csv"][1]["identifier"], "ultra-sun-ultra-moon")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                bootstrap(cache, downloader=lambda url: b"invalid", sources=pins)
            self.assertEqual((cache / "version_groups.csv").read_bytes(), payload)

    def test_mislabeled_form_slug_is_refused_instead_of_using_its_sibling(self):
        targets = copy.deepcopy(TARGETS)
        targets[0]["showdownKey"] = "persianalola"
        with self.assertRaisesRegex(ValueError, "identity"):
            self.project(targets=targets)

    def test_usum_tutor_and_regular_form_levels_do_not_leak_across_versions_or_forms(self):
        result = self.project()
        self.assertEqual(result["53:alolan"]["usum"]["knockoff"], [{"via": "tutor"}])
        self.assertNotIn("knockoff", result["53:alolan"]["sm"])
        self.assertNotIn("bite", result["53:alolan"]["sm"])
        self.assertEqual(result["53:kanto"]["sm"]["bite"], [{"via": "level", "level": 6}])


if __name__ == "__main__":
    unittest.main()
