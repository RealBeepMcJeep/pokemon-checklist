import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import moveline as M


class RendererSmokeTests(unittest.TestCase):
    def test_card_renders_without_narrow_overflow_and_creates_parent(self):
        section = {
            "name": "Gardevoir",
            "tier": "gen7ou-1695",
            "types": ["Psychic", "Fairy"],
            "grade": "A",
            "smogon_tier": "OU",
            "usage": 12.34,
            "dex": 282,
            "rows": [
                (61.2, "Hidden Power Ice", "Ice", "-", [("TM", "Gardevoir")]),
                (32.1, "Psychic", "Psychic", "90", [("level", "TEACH BEFORE EVOLVING: Ralts L20")]),
                (12.0, "Knock Off", "Dark", "65", [("tutor", "Gardevoir")]),
                (4.0, "Shadow Sneak", "Ghost", "40", [("egg", "Gardevoir")]),
            ],
        }
        html = M.card_html(
            "Ralts",
            [
                ("Ralts", 280, "L20", "Kirlia", 281),
                ("Kirlia", 281, "L30", "Gardevoir", 282),
                ("Kirlia", 281, "Dawn Stone", "Gallade", 475),
            ],
            [section],
            profile="prismatic-standard",
        )
        html = html.replace(
            "</head>",
            '<script>document.body.innerHTML = "executed";</script>'
            '<img src="https://invalid.example/remote.png">'
            '<style>.external { background: url(https://invalid.example/remote.png); }</style>'
            "</head>",
        )
        with tempfile.TemporaryDirectory(prefix="render fixture ", dir=ROOT / "tools" / "tests") as raw:
            fixture_dir = Path(raw)
            input_path = fixture_dir / "card input.html"
            input_path.write_text(html)
            output_dir = fixture_dir / "nested output"
            for width in (360, 412, 940):
                output_path = output_dir / f"card {width}.png"
                input_arg = input_path.relative_to(ROOT)
                output_arg = output_path.relative_to(ROOT)
                result = subprocess.run(
                    [
                        "node",
                        "tools/render-png.mjs",
                        str(input_arg),
                        str(output_arg),
                        str(width),
                        "--assert-no-overflow",
                    ],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
                self.assertTrue(output_path.is_file())
                self.assertEqual(output_path.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")


if __name__ == "__main__":
    unittest.main()
