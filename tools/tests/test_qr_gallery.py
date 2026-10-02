from __future__ import annotations

import base64
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import tempfile
import unittest
import shutil

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.build_qr_gallery import GalleryBuildError, compile_gallery, main

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

    def test_compiles_all_244_original_records_in_dex_order(self):
        self.assertEqual(len(self.manifest["records"]), 244)
        self.assertEqual(len(self.parsed.cards), 244)
        sources = sorted(self.manifest["records"], key=lambda row: (
            row["decoded"]["species"]["id"], row["decoded"]["formId"]))
        for source, card in zip(sources, self.parsed.cards, strict=True):
            species = source["decoded"]["species"]
            self.assertEqual(int(card["data-dex"]), species["id"])
            self.assertEqual(card["data-name"], species["name"])
            self.assertEqual(card["data-form"], str(source["decoded"]["formId"]))
            src = str(card["qr-src"])
            self.assertTrue(src.startswith("data:image/png;base64,"))
            image_bytes = base64.b64decode(src.partition(",")[2], validate=True)
            image_path = ROOT / "references/qr-codes" / source["image"]["file"]
            self.assertEqual(image_bytes, image_path.read_bytes())

    def test_type_chips_reuse_checklist_styles_and_component_markup(self):
        stylesheet = (ROOT / "src/styles/app.css").read_text(encoding="utf-8")
        expected = {".type-marks", ".type-mark", ".type-labels .type-mark"}
        expected.update(".type-" + name.lower() for name in (
            "Normal", "Fire", "Water", "Electric", "Grass", "Ice", "Fighting", "Poison", "Ground",
            "Flying", "Psychic", "Bug", "Rock", "Ghost", "Dragon", "Dark", "Steel", "Fairy"))
        for match in re.finditer(r"(?m)^([^{}\n]+)\{[^{}]*\}", stylesheet):
            if match[1].strip() in expected:
                self.assertIn(match[0], self.html)
        chips = [attrs for tag, attrs in self.parsed.tags
                 if tag == "span" and "type-chip" in attrs.get("class", "").split()]
        self.assertGreater(len(chips), 244)
        for attrs in chips:
            self.assertIn("type-mark", attrs["class"].split())
            self.assertEqual(attrs["aria-hidden"], "true")
            self.assertIn("type-" + attrs["title"].removesuffix(" type").lower(), attrs["class"].split())
        self.assertIn('class="type-list type-marks type-labels"', self.html)

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
        self.assertEqual(gift_section.count('class="gift-card"'), 2)
        self.assertIn("Hau’oli", gift_section)
        self.assertIn("Pikachu Valley", gift_section)
        self.assertIn("cap not pictured", gift_section)
        self.assertIn("US/American-region", gift_section)
        self.assertIn("American/North American and PAL", gift_section)
        self.assertIn("signature", gift_section)
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

    def test_gift_and_ordinary_evidence_drift_fails_closed(self):
        cases = ["path", "url", "hash", "binary", "hex", "key", "family", "decoded", "signature"]
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                for folder in ("references", "tools", "data", "assets", "src"):
                    shutil.copytree(ROOT / folder, root / folder)
                gift_path = root / "references/qr-gifts/manifest.json"
                gifts = json.loads(gift_path.read_text())
                event = gifts["events"][0]
                if case == "path": event["asset_path"] = "../qr-codes/manifest.json"
                elif case == "url": event["source_quotes"][0]["source"] = "javascript:alert(1)"
                elif case == "hash": event["asset_sha256"] = "0" * 64
                elif case == "binary":
                    (root / "references/qr-gifts" / event["raw_payload_path"]).write_bytes(b"bad")
                elif case == "hex": event["raw_payload_hex"] = "00" * 106
                elif case == "key": event["payload_observations"]["MemeCrypto_key_index_observed"] = 3
                elif case == "family": event["payload_observations"]["event_family_name_in_pinned_PKHeX_enum"] = "ordinary-dex"
                else:
                    path = root / "references/qr-codes/manifest.json"
                    manifest = json.loads(path.read_text())
                    row = manifest["records"][0]
                    if case == "decoded": row["decoded"]["genderCode"] ^= 1
                    else: row["payload"]["bodyHex"] = "00" * (len(row["payload"]["bodyHex"]) // 2)
                    path.write_text(json.dumps(manifest))
                gift_path.write_text(json.dumps(gifts))
                with self.assertRaises(GalleryBuildError):
                    compile_gallery(root)

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
