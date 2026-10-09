from __future__ import annotations

import base64
from html.parser import HTMLParser
import json
from pathlib import Path
import struct
import tempfile
import unittest

from tools.build_qr_experimental import (CONSOLE_TESTED, GENDER_CODE, SCANNER_EXCLUDED, compile_experimental,
                                          gender_options, load_inputs, load_qr_library, main, registration_masks,
                                          scanner_outcome, signed_variant)
from tools.build_qr_gallery import GalleryBuildError, shared_type_styles
from tools.qr_codec import generate_ordinary_payload, verify_ordinary_payload

ROOT = Path(__file__).resolve().parents[2]


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.cards: list[dict[str, str]] = []
        self.blocked: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key: value or '' for key, value in attrs}
        classes = values.get('class', '').split()
        if tag == 'article' and 'qr-card' in classes:
            self.cards.append(values)
        elif tag == 'li' and 'blocked-row' in classes:
            self.blocked.append(values)


class ExperimentalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = compile_experimental(ROOT)
        cls.parser = PageParser()
        cls.parser.feed(cls.text)
        cls.meta = json.loads((ROOT / 'references/qr-codes/gen7-form-types.json').read_text())
        genders = json.loads((ROOT / 'references/qr-codes/gen7-gender-ratios.json').read_text())
        cls.ratios, cls.form_ratios = genders['genderRatio'], genders['formGenderRatio']
        cls.names = {row['id']: row['name'] for row in json.loads((ROOT / 'data/pokemon.json').read_text())}

    def test_every_form_row_is_a_card_or_a_blocked_row(self):
        cards, blocked = self.parser.cards, self.parser.blocked
        self.assertEqual((len(cards), len(blocked)), (1082, 34))
        rows = {f"{c['data-dex']}:{c['data-form']}" for c in cards + blocked}
        self.assertEqual(rows, set(self.meta['typesBySpeciesForm']))
        self.assertEqual({(int(b['data-dex']), int(b['data-form'])) for b in blocked},
                         {(25, f) for f in range(1, 8)} | {(d, f) for d in SCANNER_EXCLUDED for f in range(self.meta['formCounts'][str(d)])})
        for c in cards:
            self.assertEqual(c['data-name'], self.names[int(c['data-dex'])])
            self.assertEqual(c['data-types'].split(), self.meta['typesBySpeciesForm'][f"{c['data-dex']}:{c['data-form']}"])
        for group in (cards, blocked):
            self.assertEqual([(int(c['data-dex']), int(c['data-form'])) for c in group],
                             sorted((int(c['data-dex']), int(c['data-form'])) for c in group))
        self.assertTrue(all(not any(k.startswith('data-qr-') for k in b) for b in blocked))

    def test_every_variant_is_signed_verified_and_accepted_by_the_scanner_rule(self):
        _, _, template, _ = load_inputs(ROOT)
        source = verify_ordinary_payload(template).body
        variants = 0
        for card in self.parser.cards:
            dex, form = int(card['data-dex']), int(card['data-form'])
            genders = gender_options(self.ratios[str(dex)])
            if f'{dex}:{form}' in self.form_ratios:
                genders = [g for g in genders if g in gender_options(self.form_ratios[f'{dex}:{form}'])]
            self.assertEqual(card['data-genders'], ''.join(genders))
            self.assertEqual((card['data-gender'], card['data-shiny']), (genders[0], '0'))
            expected = {g + s for g in genders for s in ('', 's')}
            self.assertEqual({k[len('data-qr-'):] for k in card if k.startswith('data-qr-')}, expected)
            for key in expected:
                raw = base64.b64decode(card[f'data-qr-{key}'], validate=True)
                d = verify_ordinary_payload(raw)
                shiny = key.endswith('s')
                masks = registration_masks(key[0], shiny, form)
                self.assertEqual((d.species_id, d.form, d.gender, d.shiny_flag, d.both_genders_flag, d.key_index),
                                 (dex, form, GENDER_CODE[key[0]], int(shiny), 0, 3))
                self.assertEqual(struct.unpack('<4I', d.body[0x08:0x18]), masks)
                self.assertEqual((d.body[:0x08], d.body[0x18:0x28], d.body[0x2e:-8]), (source[:0x08], source[0x18:0x28], source[0x2e:-8]))
                self.assertEqual(scanner_outcome(dex, form, d.gender, d.shiny_flag, d.both_genders_flag, masks,
                                                 self.meta['formCounts'][str(dex)], self.ratios[str(dex)]), 'accepted')
                variants += 1
        self.assertEqual(variants, 3810)

    def test_scanner_rule_matches_console_observations(self):
        def outcome(dex, form, gender, masks, shiny=0, both=0):
            return scanner_outcome(dex, form, gender, shiny, both, masks, self.meta['formCounts'][str(dex)], self.ratios[str(dex)])
        old = (1, 1, 1, 1)  # the previous page's template masks with gender code 0
        self.assertEqual(outcome(150, 0, 0, old), 'wonder')           # Mewtwo → Sealeo
        self.assertEqual(outcome(785, 0, 0, old), 'wonder')           # Tapu Koko → Solrock
        self.assertEqual(outcome(772, 0, 0, old), 'wonder')           # Type: Null → Stantler
        self.assertEqual(outcome(793, 0, 0, old), 'wonder')           # Nihilego → Gogoat
        self.assertEqual(outcome(670, 5, 0, old), 'wonder')           # Eternal Floette → Escavalier
        self.assertEqual(outcome(25, 1, 0, old), 'base-form')         # Original Cap → plain Pikachu
        for dex, form in [(1, 0), (3, 1), (745, 2), (658, 2), (666, 19)]:
            self.assertEqual(outcome(dex, form, 0, old), 'accepted')
        self.assertEqual(outcome(150, 0, 2, (1, 0, 0, 0)), 'accepted')      # corrected Mewtwo
        self.assertEqual(outcome(670, 5, 1, (0, 1 << 5, 0, 0)), 'accepted')  # corrected Eternal Floette
        self.assertEqual(outcome(130, 0, 0, (0, 0, 1, 0), shiny=1), 'accepted')  # shiny Gyarados
        self.assertEqual(outcome(34, 0, 0, (1, 0, 0, 0), both=1), 'wonder')      # male-only with both genders

    def test_form_specific_gender(self):
        cards = {(int(c['data-dex']), int(c['data-form'])): c for c in self.parser.cards}
        self.assertEqual({k: v for k, v in self.form_ratios.items() if not k.startswith('25:')}, {'658:1': 0, '658:2': 0})
        self.assertEqual((cards[(658, 0)]['data-genders'], cards[(658, 1)]['data-genders'], cards[(658, 2)]['data-genders']), ('mf', 'm', 'm'))

    def test_console_tested_badges(self):
        tested = {(int(c['data-dex']), int(c['data-form'])) for c in self.parser.cards}
        self.assertTrue(CONSOLE_TESTED <= tested)
        self.assertEqual(self.text.count('Console-tested</span>'), len(CONSOLE_TESTED))

    def test_page_text_controls_and_inlined_library(self):
        self.assertIn(shared_type_styles(ROOT), self.text)
        self.assertIn(load_qr_library(ROOT), self.text)
        for phrase in ['784 species', '1082 cards', 'Can\'t be added with a QR code (34)', 'Scans as plain Pikachu', 'Blocked by the scanner',
                       'Original Cap', 'qr.html', 'role="switch"', 'aria-label="Male. Switch to female"', 'data-card-action="gender"', 'data-card-action="shiny"', 'Genderless', 'Female only', 'Male only']:
            self.assertIn(phrase, self.text)
        self.assertNotIn('data:image/png;base64,iVBORw0KGgo', self.text.replace(self.text[self.text.index('const atlasSource'):][:80], ''))
        self.assertNotIn('class="gift-card"', self.text)
        self.assertNotRegex(self.text.replace(load_qr_library(ROOT), ''), r'__[A-Z][A-Z0-9_]+__')

    def test_scanner_rule_rejects_what_the_builder_must_not_emit(self):
        _, _, template, _ = load_inputs(ROOT)
        record = {'id': 785, 'form_id': 0, 'form_count': 1, 'gender_ratio': 255}
        with self.assertRaises(GalleryBuildError):
            signed_variant(record, 'u', False, template)
        record = {'id': 25, 'form_id': 1, 'form_count': 8, 'gender_ratio': 127}
        with self.assertRaises(GalleryBuildError):
            signed_variant(record, 'm', False, template)

    def test_masks_parameter_round_trips(self):
        _, _, template, _ = load_inputs(ROOT)
        raw = generate_ordinary_payload(150, form=1, gender=2, shiny=True, both_genders=False, masks=(0, 0, 2, 0), template=template)
        self.assertEqual(struct.unpack('<4I', verify_ordinary_payload(raw).body[0x08:0x18]), (0, 0, 2, 0))
        with self.assertRaises(ValueError):
            generate_ordinary_payload(150, masks=(0, 0, 1 << 32, 0), template=template)

    def test_changed_pins_and_missing_metadata_fail_closed(self):
        metadata = json.loads((ROOT / 'references/qr-codes/gen7-form-types.json').read_text())
        genders = json.loads((ROOT / 'references/qr-codes/gen7-gender-ratios.json').read_text())
        manifest = json.loads((ROOT / 'references/qr-codes/manifest.json').read_text())
        names = (ROOT / 'data/pokemon.json').read_text()
        for case in ['source-pin', 'gender-pin', 'missing-gender', 'missing-species', 'missing-form', 'template-hash']:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                catalog = root / 'references/qr-codes'
                catalog.mkdir(parents=True)
                (root / 'data').mkdir()
                (root / 'data/pokemon.json').write_text(names)
                meta, gmeta = json.loads(json.dumps(metadata)), json.loads(json.dumps(genders))
                if case == 'source-pin': meta['source']['commit'] = '0' * 40
                if case == 'gender-pin': gmeta['source']['tableSha256'] = '0' * 64
                if case == 'missing-gender': del gmeta['genderRatio']['150']
                if case == 'missing-species': del meta['formCounts']['807']
                if case == 'missing-form': del meta['typesBySpeciesForm']['19:1']
                (catalog / 'gen7-form-types.json').write_text(json.dumps(meta))
                (catalog / 'gen7-gender-ratios.json').write_text(json.dumps(gmeta))
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
