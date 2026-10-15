"""One-run JSON sharing, without a global path/mtime/verification cache."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import team_synergy as ts


class SharedChaosTests(unittest.TestCase):
    def test_tiers_missing_mapped_files_and_none_keep_standalone_contracts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixtures = {
                "OU": {"data": {"Flabébé": {"Moves": {"Air Slash: weighted": 25, "Air Slash": 75},
                                                  "Abilities": {"Flower Veil": 50}}}},
                "RU": {"data": {"Flabébé": {"Moves": {"Moonblast": 99},
                                                  "Abilities": {"Flower Veil": 10}}}},
            }
            for tier, payload in fixtures.items():
                (root / ts.CHAOS_FILES[tier]).write_text(json.dumps(payload))
            for tier in [None, "OU", "UUBL", "UU", "RUBL", "RU", "NU", "PU", "LC"]:
                with self.subTest(tier=tier):
                    actual = ts.load_competitive_usage(root, tier)
                    self.assertEqual(actual, (ts.load_movesets(root, tier), ts.load_ability_usage(root, tier)))
            for loader in [ts.load_competitive_usage, ts.load_movesets, ts.load_ability_usage]:
                with self.assertRaisesRegex(ValueError, "unknown tier"):
                    loader(root, "Untiered")
            moves, abilities = ts.load_competitive_usage(root, None)
            self.assertEqual(moves["flabebe"], {"airslash": 75.0, "moonblast": 99.0})
            self.assertEqual(abilities["flabebe"], {"flowerveil": 50.0})
            for p in root.glob("chaos-*.json"):
                p.unlink()
            self.assertEqual(ts.load_competitive_usage(root, "OU"), ({}, {}))
            self.assertEqual(ts.load_competitive_usage(root, None), ({}, {}))

    def test_same_admitted_blob_is_consistent_if_file_changes_then_next_use_rejects_corruption(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / ts.CHAOS_FILES["OU"]
            path.write_text(json.dumps({"data": {"Butterfree": {
                "Moves": {"Air Slash": 75}, "Abilities": {"Compound Eyes": 50}}}}))
            original = Path.read_text
            reads = []
            def change_after_admission(filename, *args, **kwargs):
                value = original(filename, *args, **kwargs)
                if filename == path:
                    reads.append(filename)
                    path.write_text("{corrupt after admission")
                return value
            with mock.patch.object(Path, "read_text", new=change_after_admission):
                moves, abilities = ts.load_competitive_usage(root, "OU")
            self.assertEqual(len(reads), 1)
            self.assertEqual(moves, {"butterfree": {"airslash": 75.0}})
            self.assertEqual(abilities, {"butterfree": {"compoundeyes": 50.0}})
            with self.assertRaises(json.JSONDecodeError):
                ts.load_competitive_usage(root, "OU")
            path.write_text(json.dumps({"data": {"Butterfree": {
                "Moves": {"Air Slash": 17}, "Abilities": {"Compound Eyes": 21}}}}))
            self.assertEqual(ts.load_competitive_usage(root, "OU"),
                             ({"butterfree": {"airslash": 17.0}}, {"butterfree": {"compoundeyes": 21.0}}))

    def test_missing_sections_and_normalized_collisions_keep_old_weight_rules(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / ts.CHAOS_FILES["OU"]
            path.write_text(json.dumps({"data": {
                "Flabébé": {"Moves": {"Air Slash": "75"}, "Abilities": {"Flower Veil": "50"}},
                "Flabe\u0301be\u0301": {"Moves": {"Air Slash: weighted": 25, "Moonblast": 99},
                                     "Abilities": {"Flower Veil": "10"}},
                "Empty": {"Moves": None, "Abilities": None}}}))
            moves, abilities = ts.load_competitive_usage(root, "OU")
            self.assertEqual(moves, {"flabebe": {"airslash": 75.0, "moonblast": 99.0}, "empty": {}})
            self.assertEqual(abilities, {"flabebe": {"flowerveil": 10.0}})


if __name__ == "__main__":
    unittest.main()
