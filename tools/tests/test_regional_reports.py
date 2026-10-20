"""Minimum regional report compatibility, not the deferred optimizer audit."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import team_options as opt


class RegionalReportTests(unittest.TestCase):
    def test_report_retains_exact_form_source_values_without_echo_timestamps(self):
        records = {"species:89": {"s": "caught"}, "star:89": {"s": "on"},
                   "form:89:alolan": {"s": "caught", "at": 100, "by": "fixture"},
                   "form:89:kanto": {"s": "seen"}, "starform:89:alolan": {"s": "on"},
                   "starform:89:kanto": {"s": "off"}, "starlegacy:89": {"s": "off"}}
        roster = {"records": records, "caught_count": 1, "canonical_count": 1}
        report = opt.story_report(roster, [], {"final": "Butterfree", "endpoint_id": 12})
        expected = {key: row["s"] for key, row in records.items() if key.startswith(("form:", "starform:", "starlegacy:"))}
        self.assertEqual(report.get("source_form_records"), expected)

    def test_source_validation_catches_form_edits_with_unchanged_species_and_star_sets(self):
        import held_item_cards as cards
        expected = {"caught": [89], "seen": [], "starred": [89]}
        initial = {"species:89": {"s": "caught"}, "star:89": {"s": "on"},
                   "form:89:alolan": {"s": "caught"}, "form:89:kanto": {"s": "seen"},
                   "starform:89:alolan": {"s": "on"}, "starform:89:kanto": {"s": "off"}}
        team = {"source_caught_ids": [89], "source_seen_ids": [], "source_starred_ids": [89],
                "source_form_records": opt.form_record_values(initial)}
        self.assertEqual(cards.validate_sources(team, expected, initial), expected)
        changed = {**initial, "starform:89:alolan": {"s": "off"}, "starform:89:kanto": {"s": "on"}}
        with self.assertRaisesRegex(ValueError, "form"):
            cards.validate_sources(team, expected, changed)

    def test_known_terminal_form_favorite_does_not_borrow_its_species_bridge(self):
        roster = {
            "records": {"species:89": {"s": "caught"}, "star:89": {"s": "on"},
                        "form:89:alolan": {"s": "caught"}, "form:89:kanto": {"s": "caught"},
                        "starform:89:alolan": {"s": "on"}, "starform:89:kanto": {"s": "off"}},
            "by_id": {89: {"name": "Muk"}}, "caught_count": 1, "canonical_count": 2,
        }
        # Two supplied candidate views exercise report projection only, not an
        # invented optimizer result or a claim about current form eligibility.
        profiles = [{"endpoint_id": 89, "caught_ids": [89], "final": name,
                     "types": types, "form_kind": kind}
                    for name, types, kind in [("Muk", ["Poison"], "base"),
                                              ("Muk-Alola", ["Poison", "Dark"], "alolan")]]
        options = [{"category": "Mixed", "profiles": profiles}]
        utility = {"final": "Butterfree", "endpoint_id": 12}
        report = opt.story_report(roster, options, utility)
        self.assertEqual([row["favorite"] for row in report["options"][0]["members"]], [False, True])
        roster["records"]["starform:89:alolan"] = {"s": "off"}
        roster["records"]["starform:89:kanto"] = {"s": "on"}
        report = opt.story_report(roster, options, utility)
        self.assertEqual([row["favorite"] for row in report["options"][0]["members"]], [True, False])


if __name__ == "__main__":
    unittest.main()
