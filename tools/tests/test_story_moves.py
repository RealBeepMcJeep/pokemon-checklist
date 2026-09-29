"""Hack-correct, acquisition-checked story move targets for the five image cards."""
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import story_moves as moves
import showdown_data

CACHE = (Path(os.environ["SHOWDOWN_DATA_CACHE"]).expanduser() if
         os.environ.get("SHOWDOWN_DATA_CACHE") else showdown_data.configured_cache_dir())

class StoryMoveOfflineTests(unittest.TestCase):
    def test_standard_table_is_manifest_verified_without_a_showdown_cache(self):
        self.assertIn("sleeppowder", moves.standard_levels()[12])

    def test_late_tms_and_tutors_are_labeled(self):
        source = moves.MoveSources.__new__(moves.MoveSources)
        self.assertIn("LATER", source.gate_label("sludgebomb", {"via": "TM", "form": "Gengar"}, "Gengar"))
        self.assertIn("ENDGAME", source.gate_label("stompingtantrum", {"via": "tutor", "form": "Linoone"}, "Linoone"))


class StoryMovesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (CACHE / showdown_data.MANIFEST_FILENAME).exists():
            raise unittest.SkipTest("pinned Showdown cache not bootstrapped; run showdown_data.py bootstrap")
        cls.source = moves.MoveSources(CACHE)

    def test_standard_replaces_vanilla_levels_and_includes_hack_extras(self):
        goals = self.source.candidates("Linoone", "Zigzagoon")
        self.assertIn(54, [s["level"] for s in goals["extremespeed"]["sources"]
                       if s["via"] == "level" and s["form"] == "Linoone"])
        gallade = self.source.candidates("Gallade", "Ralts")
        self.assertFalse(any(s["via"] == "level" for s in gallade["falseswipe"]["sources"]))
        self.assertTrue(any(s["via"] == "TM" for s in gallade["falseswipe"]["sources"]))
        infernape = self.source.candidates("Infernape", "Monferno")
        self.assertFalse(any(s["via"] == "level" and s["form"] == "Infernape" and
                             s["level"] == 19 for s in infernape["flamewheel"]["sources"]))
        self.assertTrue(any(s["via"] == "level" and s["form"] == "Monferno" and
                            s["level"] == 19 for s in infernape["flamewheel"]["sources"]))

    def test_not_breeding_event_or_overwritten_tm(self):
        zoroark = self.source.candidates("Zoroark", "Zorua")
        self.assertNotIn("sludgebomb", zoroark)
        self.assertFalse(any(s["via"] in ("egg", "event") for m in zoroark.values()
                             for s in m["sources"]))
        pidgeot = self.source.candidates("Pidgeot", "Pidgey")
        self.assertNotIn("confide", pidgeot)  # TM100 is Curse in this hack.

    def test_curated_targets_have_types_and_reachable_gates(self):
        for final, owned in (("Arcanine", "Growlithe"), ("Gengar", "Gastly"),
                             ("Infernape", "Monferno"), ("Feraligatr", "Totodile"),
                             ("Zoroark", "Zorua"), ("Galvantula", "Joltik"),
                             ("Gardevoir", "Ralts"), ("Scrafty", "Scraggy"),
                             ("Linoone", "Zigzagoon"), ("Slowbro", "Slowpoke"),
                             ("Raichu", "Pikachu"), ("Pidgeot", "Pidgey"),
                             ("Butterfree", "Butterfree")):
            with self.subTest(final=final):
                targets = self.source.targets(final, owned)
                self.assertEqual(len(targets), 4)
                self.assertEqual(len({m["name"] for m in targets}), 4)
                self.assertTrue(all(m["type"] in moves.TYPE_NAMES and m["gate"] for m in targets))
        arcanine = self.source.targets("Arcanine", "Growlithe")
        self.assertIn("BEFORE STONE", next(m["gate"] for m in arcanine
                                           if m["name"] == "Crunch"))
        self.assertEqual(next(m["gate"] for m in self.source.targets("Slowbro", "Slowpoke")
                              if m["name"] == "Psychic"), "Slowbro L49")
        self.assertIn("Ula'ula Beach", next(m["gate"] for m in
                                          self.source.targets("Feraligatr", "Totodile")
                                          if m["name"] == "Aqua Tail"))
        self.assertIn("Tapu Village", self.source.gate_label(
            "waterfall", {"via": "TM", "form": "Feraligatr"}, "Feraligatr"))


if __name__ == "__main__":
    unittest.main()
