"""Image cards: same report JSON as the CLI, with Gen VII project atlas sprites."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import story_team_cards as cards
import showdown_data


class StoryTeamCardsTests(unittest.TestCase):
    def test_render_uses_project_atlas_and_writes_a_complete_image(self):
        atlas = Image.open(cards.ATLAS).convert("RGBA")
        moves = [{"name": name, "type": typ, "gate": gate} for name, typ, gate in
                 [("Sleep Powder", "Grass", "Butterfree L13"),
                  ("Bug Buzz", "Bug", "Butterfree L31"),
                  ("Roost", "Flying", "TM19 · Route 3"),
                  ("Air Slash", "Flying", "Butterfree L43")]]
        report = {"utility": "Butterfree", "utility_dex": 12, "caught_records": 58,
                  "utility_moves": moves}
        members = [{"owned": name, "final": name, "dex": dex, "owned_dex": dex,
                    "types": [typ], "tier": "RU", "favorite": False,
                    "evolution": name, "moves": moves} for name, dex, typ in
                   [("Gengar", 94, "Ghost"), ("Arcanine", 59, "Fire"),
                    ("Raichu", 26, "Electric"), ("Pidgeot", 18, "Flying"),
                    ("Slowbro", 80, "Water")]]
        option = {"category": "OG-151", "anchor": "Gengar", "members": members,
                  "evolving": 5, "level_evolving": 2, "core_score": 6.8, "six_score": 6.6}
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "cards" / "team-01.png"
            cards.render_card(report, option, 1, atlas, dest, generated="test")
            with Image.open(dest) as image:
                self.assertEqual(image.size, cards.SIZE)
                frame = cards.sprite(atlas, 12, 2)
                alpha = frame.getchannel("A")
                opaque = next((x, y) for y in range(frame.height) for x in range(frame.width)
                              if alpha.getpixel((x, y)) == 255)
                self.assertEqual(image.getpixel((69 + opaque[0], 269 + 40 + opaque[1])),
                                 frame.convert("RGB").getpixel(opaque))
            with self.assertRaisesRegex(ValueError, "distinct battlers"):
                cards.render_card(report, {**option, "members": members[:4]}, 1, atlas, dest,
                                  generated="test")
            with self.assertRaisesRegex(ValueError, "acquisition-checked"):
                cards.render_card({**report, "utility_moves": []}, option, 1, atlas, dest,
                                  generated="test")

    def test_enrich_once_and_redraw_without_firebase_or_cache(self):
        old = {"utility": "Butterfree", "options": [{"members": [
            {"owned": "Gastly", "final": "Gengar"}]}]}
        cache = (Path(os.environ["SHOWDOWN_DATA_CACHE"]).expanduser() if
                 os.environ.get("SHOWDOWN_DATA_CACHE") else showdown_data.configured_cache_dir())
        if not (cache / showdown_data.MANIFEST_FILENAME).exists():
            self.skipTest("pinned Showdown cache not bootstrapped; run showdown_data.py bootstrap")
        enriched = cards.add_move_targets(old, cache)
        self.assertNotIn("utility_moves", old)
        self.assertEqual(len(enriched["utility_moves"]), 4)
        self.assertEqual(len(enriched["options"][0]["members"][0]["moves"]), 4)
        self.assertEqual(cards.add_move_targets(enriched, None), enriched)
        with self.assertRaisesRegex(ValueError, "needs --cache"):
            cards.add_move_targets(old, None)

    def test_no_guessed_sprite_for_out_of_atlas_dex(self):
        with Image.open(cards.ATLAS) as atlas:
            with self.assertRaisesRegex(ValueError, "no Gen VII atlas icon"):
                cards.sprite(atlas, 808, 2)


if __name__ == "__main__":
    unittest.main()
