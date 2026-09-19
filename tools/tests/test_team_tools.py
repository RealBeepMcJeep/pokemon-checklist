import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))

import team_builder as tb  # noqa: E402
import team_synergy as ts  # noqa: E402


class TeamBuilderTests(unittest.TestCase):
    def _world(self):
        details = {
            172: {"id": 172, "source": "Raichu", "types": ["Electric"], "tier": "(PU)", "usage": 0.1},
            25: {"id": 25, "source": "Raichu", "types": ["Electric"], "tier": "(PU)", "usage": 0.1,
                 "evolution": [{"name": "Pichu"}, {"name": "Pikachu"}]},
            26: {"id": 26, "source": "Raichu", "types": ["Electric"], "tier": "(PU)", "usage": 0.1,
                 "evolution": [{"name": "Pichu"}, {"name": "Pikachu"}, {"name": "Raichu"}]},
            280: {"id": 280, "source": "Gardevoir", "types": ["Psychic", "Fairy"], "tier": "RU", "usage": 1,
                  "evolution": [{"name": "Ralts"}]},
            282: {"id": 282, "source": "Gardevoir", "types": ["Psychic", "Fairy"], "tier": "RU", "usage": 1,
                  "evolution": [{"name": "Ralts"}, {"name": "Gardevoir"}]},
            475: {"id": 475, "source": "Gallade", "types": ["Psychic", "Fighting"], "tier": "PUBL", "usage": 1,
                  "evolution": [{"name": "Ralts"}, {"name": "Gallade"}]},
        }
        by_id = {i: {"id": i, "name": n, "slug": n.lower()} for i, n in {
            172: "Pichu", 25: "Pikachu", 26: "Raichu", 280: "Ralts", 282: "Gardevoir", 475: "Gallade"}.items()}
        dex = "\n".join(f"\t{name.lower()}: {{ types: [\"Electric\"], baseStats: {{hp: 50, atk: 50, def: 50, spa: 50, spd: 50, spe: 50}}, abilities: {{0: \"Static\"}} }}," for name in ("Raichu", "Gardevoir", "Gallade"))
        return details, by_id, {}, dex

    def test_canonicalizes_duplicate_evolution_records_and_preserves_source_names(self):
        details, by_id, forms, dex = self._world()
        candidates = tb.canonicalize_roster([172, 25, 26], details, by_id, forms, dex)
        self.assertEqual([c["final"] for c in candidates], ["Raichu"])
        self.assertEqual(candidates[0]["caught_ids"], [25, 26, 172])
        self.assertEqual(candidates[0]["caught_as"], ["Pichu", "Pikachu", "Raichu"])

    def test_branching_line_yields_one_candidate_per_reachable_endpoint(self):
        details, by_id, forms, dex = self._world()
        candidates = tb.canonicalize_roster([280], details, by_id, forms, dex)
        self.assertEqual({c["final"] for c in candidates}, {"Gardevoir", "Gallade"})

    def test_uber_is_the_best_tier_and_min_tier_is_deliberately_validated(self):
        self.assertLess(tb.tier_rank("Uber"), tb.tier_rank("OU"))
        self.assertEqual(tb.normalise_tier("uber"), "Uber")
        with self.assertRaises(ValueError):
            tb.normalise_tier("not-a-tier")
        self.assertTrue(tb.tier_passes("Uber", "OU"))
        self.assertFalse(tb.tier_passes("UU", "OU"))

    def test_invalid_selection_arguments_are_rejected(self):
        for kwargs in (
            {"teams": 0, "size": 5, "pool": 10, "shortlist": 10},
            {"teams": 1, "size": 0, "pool": 10, "shortlist": 10},
            {"teams": 1, "size": 6, "pool": 5, "shortlist": 10},
            {"teams": 1, "size": 5, "pool": 10, "shortlist": 0},
        ):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    ts.validate_args(**kwargs)
        with self.assertRaises(ValueError):
            tb.validate_keep(0)

    def test_no_gen1_is_lineage_based_but_keeps_butterfree_and_optional_alola(self):
        old_line = {"final": "Raichu", "lineage_ids": [172, 25, 26], "alolan": False}
        butterfree = {"final": "Butterfree", "lineage_ids": [10, 11, 12], "alolan": False}
        alola = {"final": "Raichu-Alola", "lineage_ids": [172, 25, 26], "alolan": True}
        self.assertFalse(tb.allowed_by_gen1(old_line, keep_alolan=False))
        self.assertTrue(tb.allowed_by_gen1(butterfree, keep_alolan=False))
        self.assertFalse(tb.allowed_by_gen1(alola, keep_alolan=False))
        self.assertTrue(tb.allowed_by_gen1(alola, keep_alolan=True))

    def test_roster_reports_form_assumption(self):
        details, by_id, forms, dex = self._world()
        forms["Raichu-Alola"] = {"source": "Raichu-Alola", "types": ["Electric", "Psychic"], "tier": "UU", "usage": 2}
        candidate = tb.describe_line(26, details, by_id, forms, dex)
        self.assertTrue(candidate["form_assumptions"])
        self.assertIn("assumed", candidate["form_assumptions"][0].lower())

    def test_read_records_propagates_subprocess_failure(self):
        failed = mock.Mock(returncode=17, stdout="", stderr="firebase unavailable")
        with mock.patch.object(tb.subprocess, "run", return_value=failed):
            with self.assertRaises(RuntimeError) as ctx:
                tb.read_records("uid")
        self.assertIn("firebase unavailable", str(ctx.exception))


class TeamSynergyTests(unittest.TestCase):
    def test_tier_local_chaos_file_does_not_merge_other_tiers(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp)
            (cache / "chaos-gen7ou-1695.json").write_text(json.dumps({"data": {"Testmon": {"Moves": {"Surf": 90}}}}))
            (cache / "chaos-gen7ru-1630.json").write_text(json.dumps({"data": {"Testmon": {"Moves": {"Earthquake": 99}}}}))
            moves = ts.load_movesets(cache, "OU")
            self.assertIn("surf", moves["testmon"])
            self.assertNotIn("earthquake", moves["testmon"])
            provenance = ts.moveset_provenance(cache, "OU")
            self.assertEqual(provenance["mapped_tier"], "OU")
            self.assertFalse(provenance["fallback"])

    def test_profile_keeps_best_contribution_for_each_attack_type(self):
        line = {"types": ["Normal"], "stats": "50/100/50/120/50/100", "final": "Testmon",
                "tier": "OU", "usage": 1.0}
        movesets = {"testmon": {"tackle": 100, "quickattack": 90, "flamethrower": 80,
                                "fireblast": 70, "surf": 60, "icebeam": 50}}
        mtype = {"tackle": ("Normal", 40), "quickattack": ("Normal", 40),
                 "flamethrower": ("Fire", 90), "fireblast": ("Fire", 110),
                 "surf": ("Water", 90), "icebeam": ("Ice", 90)}
        result = ts.profile(line, {}, movesets, mtype)
        self.assertEqual(set(result["attack_types"]), {"Normal", "Fire", "Water", "Ice"})
        best = {typ: (bp, share) for typ, bp, share in result["moves"]}
        self.assertEqual(best["Fire"][0], 110)

    def test_diversity_counts_member_replacements_not_symmetric_difference(self):
        a = ("A", "B", "C", "D", "E")
        two_replaced = ("A", "B", "C", "F", "G")
        three_replaced = ("A", "B", "F", "G", "H")
        self.assertEqual(ts.member_replacements(a, two_replaced), 2)
        self.assertFalse(ts.diverse_enough(a, two_replaced, replacements=3))
        self.assertTrue(ts.diverse_enough(a, three_replaced, replacements=3))

    def test_shared_weakness_penalty_starts_at_three(self):
        def member(name):
            return {"name": name, "points": 1, "types": ["Normal"], "moves": [],
                    "weak": {"Water"}, "resist": set(), "atk": 100, "spa": 100,
                    "bulk": 100, "spe": 100, "attack_types": []}
        two = [member("a"), member("b")]
        three = two + [member("c")]
        self.assertEqual(ts.score_team(two, {})[1]["shared_weak_penalty"], 0)
        self.assertGreater(ts.score_team(three, {})[1]["shared_weak_penalty"], 0)

    def test_search_finds_a_synergy_pair_that_individual_order_would_miss(self):
        def member(name, points, typ):
            return {"final": name, "points": points, "types": [typ], "moves": [], "weak": set(),
                    "resist": set(), "atk": 100, "spa": 50, "bulk": 100, "spe": 50,
                    "attack_types": [], "rank": 0, "usage": 0, "caught_as": [name]}
        pool = [member("A", 6, "Normal"), member("B", 6, "Normal"), member("C", 5, "Fire")]
        chosen = ts.search_teams(pool, size=2, shortlist=3, teams=1, diversity=1, chart={})
        self.assertEqual(chosen[0][1], ("A", "C"))

    def test_catcher_subprocess_failure_is_not_reported_as_success(self):
        failed = mock.Mock(returncode=9, stdout="", stderr="catcher unavailable")
        with mock.patch.object(tb.subprocess, "run", return_value=failed):
            with self.assertRaises(RuntimeError) as ctx:
                tb._run_catcher("uid", "/tmp/cache")
        self.assertIn("catcher unavailable", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
