"""Exact prepared search: same scores and winners, no repeated full team parsing."""
import itertools
import random
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import team_options as opt
import team_synergy as ts


class PreparedStorySearchTests(unittest.TestCase):
    def profiles(self):
        rng = random.Random(427)
        chart = {typ.lower(): {a.lower(): rng.choice([0, 0, 1, 2, 3])
                              for a in ts.ALL_TYPES} for typ in ts.ALL_TYPES}
        profiles = []
        for i in range(9):
            types = rng.sample(ts.ALL_TYPES, 2)
            profiles.append({"final": f"Member{i}", "endpoint_id": 300 + i,
                             "caught_ids": [200 + i], "caught_as": [f"Baby{i}"],
                             "types": types, "points": 2 + i / 10, "tier": "RU",
                             "moves": [(t, 80, 1.0) for t in types],
                             "weak": set(rng.sample(ts.ALL_TYPES, 4)),
                             "resist": set(rng.sample(ts.ALL_TYPES, 5)),
                             "atk": 100, "spa": 110, "bulk": 280, "spe": 110})
        return profiles, chart

    def test_prepared_score_matches_reference_including_self_resist_exclusion(self):
        profiles, chart = self.profiles()
        prepared = ts.PreparedStorySynergy(profiles, chart)
        for size in (5, 6):
            for indices in itertools.combinations(range(len(profiles)), size):
                with self.subTest(indices=indices):
                    expected = ts.story_synergy_score([profiles[i] for i in indices], chart)[0]
                    self.assertEqual(prepared.score(indices), expected)

    def test_prepared_score_handles_nonuniform_move_strengths(self):
        profiles, chart = self.profiles()
        profiles[0]["moves"] = [("Fire", 120, 0.3), ("Ice", 90, 0.7)]
        prepared = ts.PreparedStorySynergy(profiles, chart)
        for indices in itertools.combinations(range(len(profiles)), 5):
            expected = ts.story_synergy_score([profiles[i] for i in indices], chart)[0]
            self.assertEqual(prepared.score(indices), expected)

    def test_search_same_winners_but_only_expands_winning_team_details(self):
        profiles, chart = self.profiles()
        utility, pool = profiles[-1], profiles[:-1]
        for category in ("Mixed", "Pokedex", "Best"):
            for i, p in enumerate(pool):
                p["dex_plan"] = {"new_entries": [f"New{i}"] * (1 + i % 2)}
            expected = None
            for combo in itertools.combinations(pool, 5):
                core = ts.story_synergy_score(list(combo), chart)[0]
                full = ts.story_synergy_score([*combo, utility], chart)[0]
                synergy = round(0.65 * core + 0.35 * full, 4)
                names = tuple(sorted(p["final"] for p in combo))
                key = opt._objective_key(category, synergy,
                                         sum(opt.evolution_opportunities(p) for p in combo),
                                         round(sum(opt.practical_viability(p) for p in combo) / 5, 4),
                                         0, names, sum(len(p["dex_plan"]["new_entries"]) for p in combo))
                if expected is None or key < expected[0]:
                    expected = (key, names)
            with mock.patch.object(ts, "story_synergy_score", wraps=ts.story_synergy_score) as score:
                result = opt._rank(pool, utility, chart, category=category)[0]
            self.assertEqual(tuple(result["members"]), expected[1])
            self.assertEqual(result["objective_key"], expected[0])
            self.assertEqual(result["searched_combinations"], 56)
            self.assertLessEqual(score.call_count, 2)


if __name__ == "__main__":
    unittest.main()
