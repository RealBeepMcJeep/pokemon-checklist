#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import os
import subprocess
import sys
import unittest
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))

import catch_odds as odds  # noqa: E402
import catcher_score as score  # noqa: E402
import roster_lens  # noqa: E402


class CatchOddsTests(unittest.TestCase):
    def test_catch_odds_vector_uses_gen_vi_vii_floors_and_critical_mix(self):
        result = odds.calculate_catch_odds(
            max_hp=100,
            current_hp=50,
            rate=30,
            ball=1,
            status="none",
            roto=1,
            caught_count=151,
        )
        self.assertEqual(result["base_a"], 81920)
        self.assertEqual(result["a"], 81920)
        self.assertEqual(result["b"], 40662)
        self.assertEqual(result["critical_threshold"], 3)
        self.assertAlmostEqual(result["regular_probability"], 0.148195570033327, places=14)
        self.assertAlmostEqual(result["critical_probability"], 3 / 256, places=14)
        self.assertAlmostEqual(result["total_probability"], 0.15372983539456975, places=14)

    def test_status_and_roto_are_applied_after_base_floor(self):
        plain = odds.calculate_catch_odds(100, 25, 30, 1, "none", 1, 301)
        boosted = odds.calculate_catch_odds(100, 25, 30, 1, "paralysis", 2, 301)
        self.assertEqual(plain["base_a"], 102400)
        self.assertEqual(plain["a"], 102400)
        self.assertEqual(boosted["a"], 307200)
        self.assertGreater(boosted["total_probability"], plain["total_probability"])

    def test_capture_rate_cap_is_guaranteed(self):
        result = odds.calculate_catch_odds(100, 1, 255, 2, "sleep", 2, 0)
        self.assertEqual(result["a"], 255 * 4096)
        self.assertEqual(result["b"], 65536)
        self.assertEqual(result["total_probability"], 1.0)

    def test_cumulative_ball_counts(self):
        self.assertEqual(odds.balls_for_probability(0.5, 0.5), 1)
        self.assertEqual(odds.balls_for_probability(0.1, 0.95), 29)
        self.assertIsNone(odds.balls_for_probability(0.0, 0.5))

    def test_json_cli_requires_explicit_rate_and_reports_mechanics(self):
        command = [
            sys.executable,
            str(TOOLS / "catch_odds.py"),
            "--max-hp",
            "100",
            "--current-hp",
            "50",
            "--rate",
            "30",
            "--ball",
            "1",
            "--status",
            "none",
            "--roto",
            "1",
            "--caught-count",
            "151",
            "--json",
        ]
        completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=True)
        payload = json.loads(completed.stdout)
        self.assertIn("mechanics", payload)
        self.assertEqual(payload["a"], 81920)
        self.assertIn("critical", payload["mechanics"]["formula"])

    def test_roto_catch_is_opt_in_and_preserves_both_known_results(self):
        command = [
            sys.executable,
            str(TOOLS / "catch_odds.py"),
            "--max-hp",
            "100",
            "--current-hp",
            "100",
            "--rate",
            "45",
            "--ball",
            "poke",
            "--status",
            "sleep",
            "--caught-count",
            "58",
            "--json",
        ]
        default = json.loads(subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=True).stdout)
        boosted = json.loads(
            subprocess.run(command[:-1] + ["--roto", "--json"], cwd=ROOT, text=True, capture_output=True, check=True).stdout
        )

        self.assertEqual(default["inputs"]["roto"], 1)
        library_default = odds.calculate_catch_odds(100, 100, 45, "poke", "sleep", caught_count=58)
        self.assertEqual(library_default["inputs"]["roto"], 1)
        self.assertEqual(library_default["a"], default["a"])
        self.assertEqual(default["a"], 153600)
        self.assertEqual(default["b"], 45749)
        self.assertEqual(default["critical_threshold"], 3)
        self.assertAlmostEqual(default["total_probability"], 0.24286659789722265)
        self.assertEqual(default["mechanics"]["roto_default"], 1)
        self.assertFalse(default["mechanics"]["roto_active"])

        self.assertEqual(boosted["inputs"]["roto"], 2)
        self.assertEqual(boosted["a"], 307200)
        self.assertEqual(boosted["b"], 52098)
        self.assertEqual(boosted["critical_threshold"], 6)
        self.assertAlmostEqual(boosted["total_probability"], 0.4086316243792341)
        self.assertTrue(boosted["mechanics"]["roto_active"])

    def test_help_and_plain_output_name_roto_mode(self):
        help_result = subprocess.run(
            [sys.executable, str(TOOLS / "catch_odds.py"), "--help"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        help_text = " ".join(help_result.stdout.split())
        self.assertIn("bare --roto enables USUM Roto Catch x2", help_text)
        self.assertIn("default: no active Roto bonus (x1)", help_text)

        command = [
            sys.executable,
            str(TOOLS / "catch_odds.py"),
            "--max-hp",
            "100",
            "--current-hp",
            "100",
            "--rate",
            "45",
            "--ball",
            "poke",
            "--status",
            "sleep",
            "--caught-count",
            "58",
        ]
        default_output = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=True).stdout
        boosted_output = subprocess.run(command + ["--roto"], cwd=ROOT, text=True, capture_output=True, check=True).stdout
        self.assertIn("Roto Catch: inactive (x1)", default_output)
        self.assertIn("Roto Catch: active (USUM x2)", boosted_output)


class CatcherScoreTests(unittest.TestCase):
    def test_negative_top_is_a_clean_cli_error(self):
        result = subprocess.run(
            [sys.executable, str(TOOLS / "catcher_score.py"), "--species", "pikachu", "--top", "-1"],
            cwd=ROOT, text=True, capture_output=True,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("--top must be non-negative", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_empty_explain_is_a_clean_cli_error(self):
        result = subprocess.run(
            [sys.executable, str(TOOLS / "catcher_score.py"), "--species", "pikachu", "--explain", "   "],
            cwd=ROOT, text=True, capture_output=True,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("--explain requires a species name", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_roster_lens_reads_full_names_from_catcher_json(self):
        payload = json.dumps({"candidates": [{"name": "Mr. Mime", "score": 12.5}]})
        self.assertEqual(roster_lens.parse_candidates(payload), [(12.5, "Mr. Mime")])

    def test_secondary_chance_is_separate_from_accuracy(self):
        body_slam = "{ accuracy: 100, secondary: { chance: 30, status: 'par' } }"
        ice_beam = "{ accuracy: 100, secondary: { chance: 10, status: 'frz' } }"
        thunderbolt = "{ accuracy: 100, secondary: { chance: 10, status: 'par' } }"
        self.assertEqual(score.benefit("bodyslam", body_slam), ("paralysis", 0.30))
        self.assertEqual(score.benefit("icebeam", ice_beam), ("freeze", 0.10))
        self.assertEqual(score.benefit("thunderbolt", thunderbolt), ("paralysis", 0.10))
        self.assertAlmostEqual(score.hit_chance(100, 0.30, "Compound Eyes"), 0.30)
        self.assertAlmostEqual(score.hit_chance(80, 0.30, "Compound Eyes"), 0.30)

    def test_no_guard_makes_move_accuracy_100_but_not_secondary_roll(self):
        self.assertEqual(score.accuracy_with_ability(55, "No Guard"), 100.0)
        self.assertAlmostEqual(score.hit_chance(55, 0.10, "No Guard"), 0.10)
        self.assertAlmostEqual(score.hit_chance(55, 0.10, "Compound Eyes"), 0.0715)

    def test_worry_seed_is_not_a_catching_category(self):
        self.assertIsNone(score.benefit("worryseed", "{ accuracy: 100 }"))

    def test_island_mapping_uses_encounter_island_order(self):
        mapping = score.load_islands(ROOT)
        self.assertEqual(mapping[score.normalize_place("Route 1")], 1)
        self.assertEqual(mapping[score.normalize_place("Hano Beach")], 2)
        self.assertEqual(mapping[score.normalize_place("Mount Lanakila")], 3)
        self.assertEqual(mapping[score.normalize_place("Poni Gauntlet")], 4)

    def test_normalized_species_and_exclude_names(self):
        rows = json.loads((ROOT / "data" / "pokemon.json").read_text())
        self.assertEqual(score.resolve_species_token("Mr. Mime", rows)["slug"], "mr-mime")
        self.assertEqual(score.normalize_species_list("Mr. Mime, Nidoran♀"), ["mr-mime", "nidoran-f"])
        self.assertEqual(score.normalize_species_list("  gardevoir , Gallade "), ["gardevoir", "gallade"])

    def test_branch_isolation_and_known_gender_constraint(self):
        dex = {
            "ralts": '{ evos: ["kirlia"], abilities: { 0: "Trace" } }',
            "kirlia": '{ prevo: "Ralts", evos: ["Gardevoir", "Gallade"], abilities: { 0: "Trace" } }',
            "gardevoir": '{ prevo: "Kirlia", abilities: { 0: "Trace" } }',
            "gallade": '{ prevo: "Kirlia", gender: "M", abilities: { 0: "No Guard" } }',
        }
        learned = {
            "ralts": '{ learnset: { } }',
            "kirlia": '{ learnset: { } }',
            "gardevoir": '{ learnset: { hypnosis: ["7L1"] } }',
            "gallade": '{ learnset: { falseswipe: ["7M"] } }',
        }
        moves = {
            "hypnosis": "{ accuracy: 60, status: 'slp' }",
            "falseswipe": "{ accuracy: 100 }",
        }
        result = score.score_parts("ralts", learned, dex, moves)
        self.assertEqual(len(result["branches"]), 2)
        branch_text = [b["path"] for b in result["branches"]]
        self.assertTrue(any("gardevoir" in path for path in branch_text))
        self.assertTrue(any("gallade" in path for path in branch_text))
        for branch in result["branches"]:
            categories = {part["category"] for part in branch["parts"]}
            self.assertFalse({"sleep", "falseswipe"} <= categories)
        gallade = next(b for b in result["branches"] if "gallade" in b["path"])
        self.assertIn("requires male", gallade["constraints"])

    def test_score_and_explain_share_one_total(self):
        dex = {"abra": '{ abilities: { 0: "No Guard" } }'}
        learned = {"abra": '{ learnset: { hypnosis: ["7L1"] } }'}
        moves = {"hypnosis": "{ accuracy: 60, status: 'slp' }"}
        result = score.score_parts("abra", learned, dex, moves)
        branch = result["selected_branch"]
        self.assertAlmostEqual(result["score"], score.total_from_parts(branch["parts"]))
        self.assertAlmostEqual(branch["explain_total"], result["score"])


if __name__ == "__main__":
    unittest.main()
