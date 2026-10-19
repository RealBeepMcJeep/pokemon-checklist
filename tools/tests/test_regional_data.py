"""Regional metadata: pinned source parsing with no network in ordinary builds."""
import importlib
import importlib.util
import copy
import json
import sys
import subprocess
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ROOT_SOURCE = '''\n\tmeowth: {num: 52, species: "Meowth", types: ["Normal"], baseStats: {hp: 40, atk: 45, def: 35, spa: 40, spd: 40, spe: 90}, abilities: {0: "Pickup", 1: "Technician", H: "Unnerve"}},
\tmeowthalola: {num: 52, species: "Meowth-Alola", baseSpecies: "Meowth", forme: "Alola", types: ["Dark"], baseStats: {hp: 40, atk: 35, def: 35, spa: 50, spd: 40, spe: 90}, abilities: {0: "Pickup", 1: "Technician", H: "Rattled"}},
\tpikachu: {num: 25, species: "Pikachu", types: ["Electric"]},
\tpikachualola: {num: 25, species: "Pikachu-Alola", baseSpecies: "Pikachu", forme: "Alola", types: ["Electric"]},
\tmeowthgalar: {num: 52, species: "Meowth-Galar", baseSpecies: "Meowth", forme: "Galar", types: ["Steel"]},
'''


class RegionalDataTests(unittest.TestCase):
    def test_shared_standard_methods_include_source_documented_eevee_stones(self):
        from team_options import HACK_EVOLUTIONS
        self.assertEqual(HACK_EVOLUTIONS.get(("Eevee", "Leafeon")), "Leaf Stone")
        self.assertEqual(HACK_EVOLUTIONS.get(("Eevee", "Glaceon")), "Ice Stone")

    def test_main_data_validator_rejects_malformed_regional_facts(self):
        import validate_data
        validator = getattr(validate_data, "validate_regional_data", None)
        self.assertTrue(callable(validator), "canonical gate lacks regional metadata validation")
        assert callable(validator)
        data = json.loads((Path(__file__).resolve().parents[2] / "data" / "regional-forms.json").read_text())
        self.assertEqual(validator(data), [])
        for field, value in [("types", ["Invented"]), ("id", 0), ("form", []), ("baseStats", {"hp": "40"}), ("abilities", {"H": "Only hidden"})]:
            invalid = copy.deepcopy(data)
            invalid["forms"]["52:alolan"][field] = value
            with self.subTest(field=field):
                self.assertTrue(validator(invalid))
        missing = copy.deepcopy(data)
        del missing["forms"]["53:kanto"]
        self.assertTrue(validator(missing))
        bad_source = copy.deepcopy(data)
        bad_source["source"]["gen7Pokedex"]["sha256"] = "0" * 64
        self.assertTrue(validator(bad_source))

    def test_cli_generates_checks_and_rejects_stale_output(self):
        import showdown_data as sd
        cache = sd.configured_cache_dir()
        override = cache.parent / "regional" / "gen7-pokedex.js"
        if not cache.exists() or not override.exists():
            self.skipTest("verified pinned data cache is not installed")
        script = Path(__file__).resolve().parents[1] / "build_regional_data.py"
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "regional.json"
            output.write_text("stale")
            args = [sys.executable, str(script), "--cache", str(cache), "--gen7-pokedex", str(override), "--output", str(output)]
            stale = subprocess.run([*args, "--check"], capture_output=True, text=True)
            self.assertNotEqual(stale.returncode, 0, "stale output must fail the CLI check")
            generated = subprocess.run(args, capture_output=True, text=True)
            self.assertEqual(generated.returncode, 0, generated.stderr)
            self.assertIn("36 forms", generated.stdout)
            checked = subprocess.run([*args, "--check"], capture_output=True, text=True)
            self.assertEqual(checked.returncode, 0, checked.stderr)
            first = output.read_bytes()
            subprocess.run(args, check=True, capture_output=True)
            self.assertEqual(output.read_bytes(), first)

    def test_verified_build_covers_all_regional_species_with_pinned_source_provenance(self):
        import showdown_data as sd
        cache = sd.configured_cache_dir()
        override = cache.parent / "regional" / "gen7-pokedex.js"
        if not cache.exists() or not override.exists():
            self.skipTest("verified pinned data cache is not installed")
        builder = importlib.import_module("build_regional_data")
        build = getattr(builder, "build", None)
        self.assertTrue(callable(build), "verified regional data build is missing")
        assert callable(build)
        data = build(cache, override)
        expected_ids = [19, 20, 26, 27, 28, 37, 38, 50, 51, 52, 53, 74, 75, 76, 88, 89, 103, 105]
        self.assertEqual(set(data["forms"]), {f"{dex}:{form}" for dex in expected_ids for form in ["alolan", "kanto"]})
        self.assertEqual(data["source"]["showdownCommit"], sd.SHOWDOWN_COMMIT)
        self.assertEqual(data["source"]["gen7Pokedex"]["sha256"], "70a4080bed36a66a75141d938ec6f90f9ab1cbb6c14c61154e2046498e7d6c34")
        self.assertEqual(data, build(cache, override))

    def test_gen7_overrides_merge_partial_stats_and_ability_slots_without_losing_inherited_fields(self):
        builder = importlib.import_module("build_regional_data")
        override = '\n\tmeowthalola: {inherit: true, types: ["Steel"], baseStats: {spa: 80}, abilities: {H: "Fixture"}},'
        row = builder.build_from_text(ROOT_SOURCE, override)["forms"]["52:alolan"]
        self.assertEqual(row["types"], ["Steel"])
        self.assertEqual(row["baseStats"], {"hp": 40, "atk": 35, "def": 35, "spa": 80, "spd": 40, "spe": 90})
        self.assertEqual(row["abilities"], {"0": "Pickup", "1": "Technician", "H": "Fixture"})

    def test_builds_both_regional_identities_with_exact_types_stats_and_abilities(self):
        self.assertIsNotNone(importlib.util.find_spec("build_regional_data"), "regional metadata builder is missing")
        builder = importlib.import_module("build_regional_data")
        data = builder.build_from_text(ROOT_SOURCE, "")
        self.assertEqual(set(data["forms"]), {"52:alolan", "52:kanto"})
        self.assertEqual(data["forms"]["52:alolan"]["types"], ["Dark"])
        self.assertEqual(data["forms"]["52:kanto"]["types"], ["Normal"])
        self.assertEqual(data["forms"]["52:alolan"]["baseStats"]["spa"], 50)
        self.assertEqual(data["forms"]["52:kanto"]["baseStats"]["atk"], 45)
        self.assertEqual(data["forms"]["52:alolan"]["abilities"]["H"], "Rattled")
        self.assertEqual(data["forms"]["52:kanto"]["abilities"]["H"], "Unnerve")


if __name__ == "__main__":
    unittest.main()
