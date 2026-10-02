from __future__ import annotations

import base64
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import tempfile
import unittest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.build_qr_gallery import compile_gallery, main

ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = ROOT / "references/qr-codes/manifest.json"


class GalleryParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.cards: list[dict[str, object]] = []
        self.current: dict[str, object] | None = None
        self.tags: list[tuple[str, dict[str, str]]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key: value or "" for key, value in attrs}
        self.tags.append((tag, values))
        classes = values.get("class", "").split()
        if tag == "article" and "qr-card" in classes:
            card: dict[str, object] = dict(values)
            card["qr-src"] = ""
            self.current = card
            self.cards.append(card)
        elif self.current is not None and tag == "img" and "qr-original" in classes:
            self.current["qr-src"] = values.get("src", "")

    def handle_endtag(self, tag: str) -> None:
        if tag == "article":
            self.current = None


class QRGalleryCompilerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        cls.html = compile_gallery(ROOT)
        cls.parsed = GalleryParser()
        cls.parsed.feed(cls.html)

    def test_compiles_all_244_original_records_in_manifest_order(self):
        self.assertEqual(len(self.manifest["records"]), 244)
        self.assertEqual(len(self.parsed.cards), 244)
        for source, card in zip(self.manifest["records"], self.parsed.cards, strict=True):
            species = source["decoded"]["species"]
            self.assertEqual(int(card["data-dex"]), species["id"])
            self.assertEqual(card["data-name"], species["name"])
            self.assertEqual(card["data-form"], str(source["decoded"]["formId"]))
            src = str(card["qr-src"])
            self.assertTrue(src.startswith("data:image/png;base64,"))
            image_bytes = base64.b64decode(src.partition(",")[2], validate=True)
            image_path = ROOT / "references/qr-codes" / source["image"]["file"]
            self.assertEqual(image_bytes, image_path.read_bytes())

    def test_source_membership_is_presented_as_catalogue_provenance_not_compatibility(self):
        shared = next(card for card in self.parsed.cards if card["data-name"] == "Rowlet")
        ultra = next(card for card in self.parsed.cards
                     if card["data-name"] == "Buneary" and card["data-form"] == "0")
        self.assertEqual(shared["data-libraries"], "sun-moon ultra-sun-ultra-moon")
        self.assertEqual(ultra["data-libraries"], "ultra-sun-ultra-moon")
        self.assertIn("source library", self.html.lower())
        self.assertRegex(self.html, re.compile(r"USUM-category-only.{0,100}unknown|unknown.{0,100}USUM-category-only", re.I | re.S))
        self.assertIn("universal compatibility or incompatibility", self.html.lower())

    def test_form_labels_and_types_come_from_exact_gen7_form_rows(self):
        def find(name: str, form_label: str) -> dict[str, object]:
            return next(card for card in self.parsed.cards
                        if card["data-name"] == name and card["data-form-label"] == form_label)

        raichu = find("Raichu", "Alola")
        self.assertEqual(raichu["data-types"], "Electric Psychic")
        mega_ampharos = find("Ampharos", "Mega")
        self.assertEqual(mega_ampharos["data-types"], "Electric Dragon")
        flabebe_yellow = find("Flabébé", "Yellow")
        self.assertEqual(flabebe_yellow["data-types"], "Fairy")
        furfrou = find("Furfrou", "Dandy")
        self.assertEqual(furfrou["data-types"], "Normal")
        metadata = json.loads((ROOT / "references/qr-codes/gen7-form-types.json").read_text(encoding="utf-8"))
        types = metadata["typesBySpeciesForm"]
        self.assertEqual(types["669:1"], types["669:0"])
        self.assertEqual(types["676:6"], types["676:0"])
        rowlet = find("Rowlet", "Standard")
        self.assertEqual(rowlet["data-types"], "Grass Flying")
        self.assertIn("PKHeX", self.html)
        self.assertIn("542111fc8584ff29c9d1455553b8acd0e1f8a59a", self.html)

    def test_page_keeps_ordinary_library_and_future_gift_codes_separate(self):
        self.assertIn('id="ordinary-gallery"', self.html)
        self.assertIn('id="promotional-gifts"', self.html)
        gift_section = self.html.split('id="promotional-gifts"', 1)[1].split("</section>", 1)[0]
        self.assertNotIn('class="qr-card', gift_section)
        self.assertIn("No verified promotional gift records are included", gift_section)
        self.assertIn("gift codes are kept separate from the ordinary pokédex archive", self.html.lower())

    def test_generated_document_is_offline_self_contained_and_credits_are_not_in_scan_image(self):
        self.assertNotRegex(self.html, r"(?is)<script\b[^>]*\bsrc\s*=")
        self.assertNotRegex(self.html, r"(?is)<link\b[^>]*\bhref\s*=")
        self.assertNotIn("@import", self.html)
        self.assertNotRegex(self.html, r"(?is)<img\b[^>]*\bsrc\s*=\s*['\"]https?:")
        self.assertIn('class="scan-image"', self.html)
        self.assertIn('class="scan-credits"', self.html)
        self.assertIn("archives.bulbagarden.net", self.html)
        self.assertIn("PokeAPI/sprites", self.html)
        self.assertIn('aria-modal="true"', self.html)

    def test_cli_build_and_check_are_deterministic_and_check_fails_on_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "qr.html"
            self.assertEqual(main(["--output", str(output)]), 0)
            expected = compile_gallery(ROOT).encode("utf-8")
            self.assertEqual(output.read_bytes(), expected)
            self.assertEqual(main(["--output", str(output), "--check"]), 0)
            output.write_text("stale artifact", encoding="utf-8")
            self.assertEqual(main(["--output", str(output), "--check"]), 1)
            self.assertEqual(output.read_text(encoding="utf-8"), "stale artifact")


if __name__ == "__main__":
    unittest.main()
