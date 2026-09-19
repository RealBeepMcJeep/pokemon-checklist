import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import moveline as M


class MoveLineHardeningTests(unittest.TestCase):
    def test_final_evolution_paths_are_branch_specific(self):
        parent_of = {
            "ralts": "",
            "kirlia": "ralts",
            "gardevoir": "kirlia",
            "gallade": "kirlia",
        }
        learned = {
            "ralts": {"sharedmove": {"level": ["20"]}},
            "kirlia": {"sharedmove": {"level": ["25"]}},
            "gardevoir": {"moonblast": {"level": ["1"]}},
            "gallade": {"closecombat": {"level": ["1"]}},
        }
        gardevoir_path = M.ancestral_path("gardevoir", parent_of)
        gallade_path = M.ancestral_path("gallade", parent_of)
        gardevoir_moves = M.path_move_union(gardevoir_path, learned)
        gallade_moves = M.path_move_union(gallade_path, learned)

        self.assertEqual(gardevoir_path, ["ralts", "kirlia", "gardevoir"])
        self.assertIn("moonblast", gardevoir_moves)
        self.assertNotIn("closecombat", gardevoir_moves)
        self.assertIn("closecombat", gallade_moves)
        self.assertNotIn("moonblast", gallade_moves)

    def test_pre_evolution_only_gate_is_explicit(self):
        gates = M.acquisition_gates(
            "gardevoir",
            ["ralts", "kirlia", "gardevoir"],
            {
                "ralts": {"level": ["20"]},
                "kirlia": {},
                "gardevoir": {},
            },
            {"ralts": "Ralts", "kirlia": "Kirlia", "gardevoir": "Gardevoir"},
        )
        self.assertEqual(gates, [("level", "TEACH BEFORE EVOLVING: Ralts L20")])

    def test_punctuated_species_names_resolve_and_bad_input_is_clean(self):
        rows = [
            {"id": 122, "name": "Mr. Mime", "slug": "mr-mime"},
            {"id": 29, "name": "Nidoran♀", "slug": "nidoran-f"},
            {"id": 772, "name": "Type: Null", "slug": "type-null"},
        ]
        self.assertEqual(M.resolve_species("mr-mime", rows)["id"], 122)
        self.assertEqual(M.resolve_species("nidoran-f", rows)["id"], 29)
        self.assertEqual(M.resolve_species("type-null", rows)["id"], 772)
        self.assertEqual(M.resolve_species("Nidoran♀", rows)["id"], 29)
        with self.assertRaises(M.SpeciesInputError) as ctx:
            M.resolve_species("not-a-real-species", rows)
        self.assertIn("no such species", str(ctx.exception))

    def test_hidden_power_keeps_usage_variant_and_legality_key(self):
        shown, kind, coverage = M.display_move_for_usage(
            "hiddenpower", "Hidden Power", "Normal", {"Hidden Power Ice": 61.2}
        )
        self.assertEqual((shown, kind, coverage), ("Hidden Power Ice", "Ice", "Ice"))
        self.assertEqual(M.canon("Hidden Power Ice"), "hiddenpower")
        self.assertEqual(M.acquisition_label("TM", "hiddenpower", "Gardevoir"),
                         "TM10 — Paniola Ranch")
        self.assertIn("TEACH BEFORE EVOLVING", M.acquisition_label(
            "TM", "psychic", "TEACH BEFORE EVOLVING: Ralts"
        ))

    def test_acquisition_labels_include_locations_and_endgame_warning(self):
        self.assertIn("Battle Tree", M.acquisition_label("tutor", "knockoff", "Gardevoir"))
        self.assertIn("12 BP", M.acquisition_label("tutor", "knockoff", "Gardevoir"))
        reminder = M.acquisition_label("reminder", "Gardevoir L1", "Gardevoir")
        self.assertIn("Mount Lanakila", reminder)
        self.assertIn("endgame", reminder.lower())
        egg = M.acquisition_label("egg", "Gardevoir", "Gardevoir", profile="prismatic-standard")
        self.assertIn("level not specified", egg.lower())
        self.assertNotIn("L", egg)

    def test_card_contains_coverage_metadata_and_responsive_layout(self):
        section = {
            "name": "Gardevoir",
            "tier": "gen7ou-1695",
            "types": ["Psychic", "Fairy"],
            "grade": "A",
            "smogon_tier": "OU",
            "usage": 1.0,
            "dex": 282,
            "rows": [(61.2, "Hidden Power Ice", "Ice", "-", [("TM", "Gardevoir")])],
        }
        rendered = M.card_html("Ralts", [], [section], profile="prismatic-standard")
        self.assertIn('data-legality-key="hiddenpower"', rendered)
        self.assertIn('data-coverage-type="Ice"', rendered)
        self.assertIn("Prismatic Standard", rendered)
        self.assertIn("grid-template-columns:minmax(0, 1fr) auto", rendered)


if __name__ == "__main__":
    unittest.main()
