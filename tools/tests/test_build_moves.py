import unittest
from types import SimpleNamespace

from tools import build_moves as B


class BuildMovesTests(unittest.TestCase):
    def test_sources_collapse_to_one_route_each_but_keep_every_level(self):
        id_of = {"ralts": 280, "kirlia": 281, "gardevoir": 282}
        sources = [
            {"via": "TM", "form": "ralts"},
            {"via": "TM", "form": "kirlia"},
            {"via": "TM", "form": "gardevoir"},
            {"via": "level", "form": "ralts", "level": "27"},
            {"via": "level", "form": "gardevoir", "level": "31"},
            {"via": "tutor", "form": "ralts", "beforeEvolving": True},
            {"via": "egg", "form": "ralts", "beforeEvolving": True},
        ]
        self.assertEqual(
            B.compact_sources(sources, id_of),
            [
                {"via": "TM"},
                {"via": "level", "level": 27, "form": 280},
                {"via": "level", "level": 31, "form": 282},
                {"via": "tutor", "form": 280, "beforeEvolving": True},
                {"via": "egg", "form": 280, "beforeEvolving": True},
            ],
        )

    def test_a_route_the_final_can_use_replaces_a_before_evolving_one(self):
        sources = [
            {"via": "tutor", "form": "ralts", "beforeEvolving": True},
            {"via": "tutor", "form": "gardevoir"},
        ]
        self.assertEqual(B.compact_sources(sources, {"ralts": 280, "gardevoir": 282}), [{"via": "tutor"}])

    def test_finals_and_lines_stay_inside_the_gen7_dex(self):
        data = SimpleNamespace(
            nice={"ralts": "Ralts", "kirlia": "Kirlia", "gardevoir": "Gardevoir", "gallade": "Gallade",
                  "meltan": "Meltan"},
            id_of={"ralts": 280, "kirlia": 281, "gardevoir": 282, "gallade": 475, "meltan": 807},
            # Meltan's evolution is outside 001-807, so Meltan itself counts as final.
            evos_of={"ralts": ["kirlia"], "kirlia": ["gardevoir", "gallade"], "meltan": ["melmetal"]},
        )
        finals = B.final_forms(data)
        self.assertEqual(finals, ["gardevoir", "gallade", "meltan"])
        self.assertEqual(B.descendant_finals("ralts", data, set(finals)), [282, 475])


if __name__ == "__main__":
    unittest.main()
