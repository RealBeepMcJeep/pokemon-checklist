"""Font resources may be reused within ONE card, never globally across redraws."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import story_team_cards as cards


def fixture():
    # Synthetic layout fixture only; these are not live acquisition recommendations.
    moves = [{"name": name, "type": typ, "gate": gate} for name, typ, gate in [
        ("Sleep Powder", "Grass", "Butterfree L13"), ("Bug Buzz", "Bug", "Butterfree L31"),
        ("Roost", "Flying", "TM19 · Route 3"), ("Air Slash", "Flying", "Butterfree L43")]]
    report = {"utility": "Butterfree", "utility_dex": 12, "caught_records": 58, "utility_moves": moves}
    members = [{"owned": name, "final": name, "dex": dex, "owned_dex": dex,
                "types": [typ], "tier": "RU", "favorite": False,
                "evolution": name, "moves": moves} for name, dex, typ in [
                    ("Gengar", 94, "Ghost"), ("Arcanine", 59, "Fire"),
                    ("Raichu", 26, "Electric"), ("Pidgeot", 18, "Flying"), ("Slowbro", 80, "Water")]]
    option = {"category": "OG", "anchor": "Gengar", "members": members,
              "evolving": 5, "level_evolving": 2, "new_entries": 5,
              "core_synergy": 6.8, "six_synergy": 6.6}
    return report, option


class CardFontScopeTests(unittest.TestCase):
    def test_next_render_does_not_hide_missing_font_or_cache_public_mutable_objects(self):
        report, option = fixture()
        self.assertIsNot(cards.font(18), cards.font(18), "the public font factory must retain its fresh-object contract")
        with Image.open(cards.ATLAS) as original, tempfile.TemporaryDirectory() as tmp:
            atlas = original.convert("RGBA")
            cards.render_card(report, option, 1, atlas, Path(tmp) / "before.png", generated="First timestamp")
            with mock.patch.object(cards, "FONT", str(Path(tmp) / "missing.ttf")):
                with self.assertRaises(OSError):
                    cards.render_card(report, option, 1, atlas, Path(tmp) / "after.png", generated="Second timestamp")
            self.assertFalse((Path(tmp) / "after.png").exists())

    def test_one_card_loads_each_font_resource_once_but_next_card_loads_fresh_resources(self):
        report, option = fixture()
        with Image.open(cards.ATLAS) as original, tempfile.TemporaryDirectory() as tmp:
            atlas = original.convert("RGBA")
            with mock.patch.object(cards.ImageFont, "truetype", wraps=cards.ImageFont.truetype) as loads:
                cards.render_card(report, option, 1, atlas, Path(tmp) / "first.png", generated="First timestamp")
                requests = [(c.args[0], c.args[1]) for c in loads.call_args_list]
                self.assertGreater(len(requests), 0)
                self.assertEqual(len(requests), len(set(requests)), "same size/weight font should load once per card")
                loads.reset_mock()
                cards.render_card(report, option, 1, atlas, Path(tmp) / "second.png", generated="Second timestamp")
                fresh = [(c.args[0], c.args[1]) for c in loads.call_args_list]
                self.assertEqual(fresh, requests, "a new render must admit fresh resources, not use a global font cache")
            with Image.open(Path(tmp) / "first.png") as a, Image.open(Path(tmp) / "second.png") as b:
                self.assertNotEqual(a.tobytes(), b.tobytes(), "a new timestamp must actually be drawn")


if __name__ == "__main__":
    unittest.main()
