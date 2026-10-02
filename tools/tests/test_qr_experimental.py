from __future__ import annotations

import base64
import hashlib
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image
import zxingcpp

from tools.build_qr_experimental import compile_experimental, load_inputs, main, verified_png
from tools.build_qr_gallery import GalleryBuildError, shared_type_styles
from tools.qr_codec import generate_ordinary_payload, verify_ordinary_payload
from tools.tests.test_qr_gallery import GalleryParser

ROOT = Path(__file__).resolve().parents[2]


class ExperimentalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = compile_experimental(ROOT)
        cls.parser = GalleryParser()
        cls.parser.feed(cls.text)
        cls.meta = json.loads((ROOT / 'references/qr-codes/gen7-form-types.json').read_text())
        cls.names = {row['id']: row['name'] for row in json.loads((ROOT / 'data/pokemon.json').read_text())}

    def test_complete_species_and_exact_form_rows_types_names(self):
        cards = self.parser.cards
        self.assertEqual(len(cards), 1116)
        self.assertEqual({int(c['data-dex']) for c in cards}, set(range(1, 808)))
        self.assertEqual({f"{c['data-dex']}:{c['data-form']}" for c in cards}, set(self.meta['typesBySpeciesForm']))
        for c in cards:
            self.assertEqual(c['data-name'], self.names[int(c['data-dex'])])
            self.assertEqual(c['data-types'].split(), self.meta['typesBySpeciesForm'][f"{c['data-dex']}:{c['data-form']}"])
            self.assertEqual(c['data-libraries'], 'generated')
        self.assertEqual([(int(c['data-dex']), int(c['data-form'])) for c in cards], sorted((int(c['data-dex']), int(c['data-form'])) for c in cards))

    def test_every_inlined_png_independently_decodes_with_verified_fields(self):
        _, _, template, _ = load_inputs(ROOT)
        source_body = verify_ordinary_payload(template).body
        for card in self.parser.cards:
            png = base64.b64decode(str(card['qr-src']).split(',')[1], validate=True)
            with Image.open(BytesIO(png)) as image:
                results = zxingcpp.read_barcodes(image, formats=zxingcpp.BarcodeFormat.QRCode)
            self.assertEqual(len(results), 1)
            raw = bytes(results[0].bytes)
            decoded = verify_ordinary_payload(raw)
            self.assertEqual((decoded.species_id, decoded.form, decoded.gender, decoded.shiny_flag, decoded.both_genders_flag, decoded.key_index), (int(card['data-dex']), int(card['data-form']), 0, 0, 0, 3))
            self.assertEqual(hashlib.sha256(raw).hexdigest(), card['data-payload-sha256'])
            self.assertEqual(decoded.body[:0x28], source_body[:0x28])
            self.assertEqual(decoded.body[0x2e:-8], source_body[0x2e:-8])
            self.assertEqual(raw, generate_ordinary_payload(decoded.species_id, form=decoded.form, gender=0, shiny=False, both_genders=False, template=template))

    def test_truthful_provenance_labels_no_gifts_and_shared_ui(self):
        self.assertIn(shared_type_styles(ROOT), self.text)
        self.assertNotIn('id="promotional-gifts"', self.text)
        self.assertNotIn('class="gift-card"', self.text)
        self.assertNotIn('Source library membership', self.text)
        self.assertNotIn('Original archive file:', self.text)
        for phrase in ['console untested', 'fixed experimental gender=0', 'Base species icon; not form art', 'battle-only', 'Wonder QR', 'no more than 10', 'qr.html', 'Form 1 (experimental)']:
            self.assertIn(phrase, self.text)
        self.assertIn('Alola', self.text)
        self.assertIn('id="qr-807-0"', self.text)
        self.assertNotIn('__CARDS__', self.text)

    def test_bad_png_decode_fails_closed(self):
        _, _, template, _ = load_inputs(ROOT)
        raw = generate_ordinary_payload(1, template=template, form=0, gender=0, shiny=False, both_genders=False)
        with patch('tools.build_qr_experimental.zxingcpp.read_barcodes', return_value=[]):
            with self.assertRaises(GalleryBuildError):
                verified_png(raw, 1, 0)

    def test_changed_source_hash_and_missing_form_metadata_fail_closed(self):
        metadata = json.loads((ROOT / 'references/qr-codes/gen7-form-types.json').read_text())
        manifest = json.loads((ROOT / 'references/qr-codes/manifest.json').read_text())
        names = (ROOT / 'data/pokemon.json').read_text()
        for case in ['source-pin', 'missing-species', 'missing-form', 'template-hash']:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                catalog = root / 'references/qr-codes'
                catalog.mkdir(parents=True)
                (root / 'data').mkdir()
                (root / 'data/pokemon.json').write_text(names)
                meta = json.loads(json.dumps(metadata))
                if case == 'source-pin': meta['source']['commit'] = '0' * 40
                if case == 'missing-species': del meta['formCounts']['807']
                if case == 'missing-form': del meta['typesBySpeciesForm']['19:1']
                (catalog / 'gen7-form-types.json').write_text(json.dumps(meta))
                (catalog / 'manifest.json').write_text(json.dumps(manifest))
                if case == 'template-hash':
                    (catalog / 'images').mkdir()
                    (catalog / 'images/304909.png').write_bytes(b'wrong image')
                with self.assertRaises(GalleryBuildError):
                    load_inputs(root)

    def test_deterministic_cli_and_stale_check(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'qr-experimental.html'
            self.assertEqual(main(['--output', str(output)]), 0)
            self.assertEqual(output.read_text(), self.text)
            self.assertEqual(main(['--output', str(output), '--check']), 0)
            output.write_text('stale')
            self.assertEqual(main(['--output', str(output), '--check']), 1)
            self.assertEqual(output.read_text(), 'stale')


if __name__ == '__main__':
    unittest.main()
