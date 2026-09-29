"""Image cards: same report JSON as the CLI, with Gen VII project atlas sprites."""
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import story_team_cards as cards


class StoryTeamCardsTests(unittest.TestCase):
    def test_render_uses_project_atlas_and_writes_a_complete_image(self):
        atlas = Image.open(cards.ATLAS).convert("RGBA")
        report = {"utility": "Butterfree", "utility_dex": 12, "caught_records": 58}
        members = [{"owned": name, "final": name, "dex": dex, "owned_dex": dex,
                    "types": [typ], "tier": "RU", "favorite": False,
                    "evolution": name} for name, dex, typ in
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

    def test_no_guessed_sprite_for_out_of_atlas_dex(self):
        with Image.open(cards.ATLAS) as atlas:
            with self.assertRaisesRegex(ValueError, "no Gen VII atlas icon"):
                cards.sprite(atlas, 808, 2)


if __name__ == "__main__":
    unittest.main()
