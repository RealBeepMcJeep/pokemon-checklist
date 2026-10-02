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

    def test_beldum_targets_preserve_pre_evolution_levels_and_late_tm_gate(self):
        targets = {m["name"]: m for m in self.source.targets("Metagross", "Beldum")}
        self.assertEqual(len(targets), 4)
        self.assertEqual(targets["Meteor Mash"]["type"], "Steel")
        self.assertEqual(targets["Meteor Mash"]["gate"], "Metang L44 · before evolving")
        self.assertEqual(targets["Zen Headbutt"]["gate"], "Metang L32 · before evolving")
        self.assertEqual(targets["Bullet Punch"]["gate"], "Metang L26 · before evolving")
        self.assertEqual(targets["Earthquake"]["type"], "Ground")
        self.assertEqual(targets["Earthquake"]["gate"], "TM26 · Tapu Village (later)")
        self.assertTrue(all(m["source"]["via"] in ("level", "TM") for m in targets.values()))

    def test_turtwig_targets_use_standard_evolution_and_level_gates(self):
        self.assertIn("Torterra", moves.GOALS)
        targets = {m["name"]: m for m in self.source.targets("Torterra", "Turtwig")}
        self.assertEqual(len(targets), 4)
        expected = {"Earthquake": ("Ground", "On evolution → Torterra", "evolution"),
                    "Wood Hammer": ("Grass", "Torterra L48", "level"),
                    "Crunch": ("Dark", "Torterra L45", "level"),
                    "Synthesis": ("Grass", "Torterra L39", "level")}
        self.assertEqual(set(targets), set(expected))
        for name, (typ, gate, via) in expected.items():
            with self.subTest(move=name):
                self.assertEqual(targets[name]["type"], typ)
                self.assertEqual(targets[name]["gate"], gate)
                self.assertEqual(targets[name]["source"]["via"], via)
                self.assertEqual(targets[name]["source"]["form"], "Torterra")

    def test_new_endpoints_have_four_verified_story_targets(self):
        paths = {"Blaziken": "Torchic", "Exploud": "Whismur", "Gastrodon": "Shellos",
                 "Hypno": "Drowzee", "Meganium": "Chikorita", "Shiftry": "Seedot",
                 "Vikavolt": "Grubbin"}
        for final, owned in paths.items():
            with self.subTest(final=final):
                self.assertIn(final, moves.GOALS)
                targets = self.source.targets(final, owned)
                self.assertEqual(len(targets), 4)
                self.assertEqual(len({m["name"] for m in targets}), 4)
                self.assertTrue(all(m["type"] in moves.TYPE_NAMES and m["gate"] for m in targets))
                self.assertTrue(all(m["source"]["via"] in ("level", "evolution", "TM", "tutor", "reminder")
                                    for m in targets))
        blaziken = {m["name"]: m for m in self.source.targets("Blaziken", "Torchic")}
        self.assertEqual(blaziken["Bulk Up"]["gate"], "Combusken L31 · before evolving")
        self.assertEqual(blaziken["Blaze Kick"]["gate"], "On evolution → Blaziken")
        shiftry = {m["name"]: m for m in self.source.targets("Shiftry", "Seedot")}
        self.assertEqual(shiftry["Leaf Blade"]["gate"], "Nuzleaf L28 · before evolving")
        self.assertIn("Feint Attack", shiftry)
        self.assertNotIn("nightslash", self.source.candidates("Shiftry", "Seedot"))
        for final, owned in (("Exploud", "Whismur"), ("Gastrodon", "Shellos")):
            ice_beam = next(m for m in self.source.targets(final, owned) if m["name"] == "Ice Beam")
            self.assertIn("LATER", ice_beam["gate"])
        vikavolt = self.source.targets("Vikavolt", "Grubbin")
        self.assertEqual([m["source"]["via"] for m in vikavolt[:2]], ["evolution", "evolution"])

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
                             ("Alakazam", "Alakazam"), ("Poliwrath", "Poliwag"),
                             ("Fearow", "Fearow"), ("Pelipper", "Pelipper"),
                             ("Diggersby", "Bunnelby"), ("Skuntank", "Stunky"),
                             ("Crabominable", "Crabrawler"), ("Luxray", "Shinx"),
                             ("Magnezone", "Magnemite"), ("Decidueye", "Decidueye"),
                             ("Vivillon", "Scatterbug"), ("Toucannon", "Pikipek"),
                             ("Tentacruel", "Tentacool"),
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
