"""Prismatic catch-utility gallery: verified moves, chronology and readable output."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import catch_utility_card as card
import showdown_data

CACHE = Path(os.environ.get('SHOWDOWN_DATA_CACHE') or showdown_data.configured_cache_dir())

class CatchUtilityCardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (CACHE / showdown_data.MANIFEST_FILENAME).exists():
            raise unittest.SkipTest('bootstrap the pinned Showdown cache for integration tests')
        cls.report = card.build_report(CACHE, {'species:12': {'s': 'caught'}, 'species:401': {'s': 'caught'}})

    def test_six_options_sorted_by_first_regular_encounter(self):
        rows = self.report['rows']
        self.assertEqual([r['final'] for r in rows], ['Butterfree', 'Kricketune', 'Gallade', 'Smeargle', 'Breloom', 'Parasect'])
        self.assertEqual([r['encounter']['order'] for r in rows], sorted(r['encounter']['order'] for r in rows))
        self.assertEqual(rows[0]['ownership'], 'FINAL CAUGHT')
        self.assertEqual(rows[1]['ownership'], 'BASE CAUGHT')
        self.assertEqual(rows[-1]['ownership'], 'NOT CAUGHT')
        self.assertIn('day', rows[-1]['encounter']['label'].lower())
        self.assertIn('night', rows[1]['encounter']['label'].lower())

    def test_one_sleep_move_and_four_acquisition_checked_slots(self):
        for row in self.report['rows']:
            moves = row['moves']
            self.assertEqual(len(moves), 4)
            self.assertEqual(len({m['name'] for m in moves}), 4)
            self.assertEqual(sum(m['category'] == 'sleep' for m in moves), 1)
            self.assertTrue(all(m['source']['via'] in ('level', 'evolution', 'TM', 'tutor', 'sketch') for m in moves))
            self.assertTrue(all(m['gate'] and m['type'] for m in moves))
        butterfree = self.report['rows'][0]
        self.assertNotIn('False Swipe', [m['name'] for m in butterfree['moves']])
        self.assertTrue(all(any(m['name'] == 'False Swipe' for m in row['moves']) for row in self.report['rows'][1:]))

    def test_delayed_evolutions_tm_and_sketch_are_not_fabricated_levels(self):
        rows = {r['final']: r for r in self.report['rows']}
        gallade = {m['name']: m for m in rows['Gallade']['moves']}
        self.assertEqual(gallade['Hypnosis']['source']['form'], 'Ralts')
        self.assertEqual(gallade['Hypnosis']['source']['level'], 37)
        self.assertEqual(gallade['False Swipe']['source']['via'], 'TM')
        self.assertIn('male', rows['Gallade']['note'].lower())
        self.assertIn('L40', rows['Breloom']['evolution'])
        self.assertEqual(next(m for m in rows['Breloom']['moves'] if m['name']=='Spore')['source']['level'], 40)
        self.assertTrue(all(m['source']['via']=='sketch' for m in rows['Smeargle']['moves']))
        self.assertIn('Iki Town', next(m for m in rows['Smeargle']['moves'] if m['name']=='False Swipe')['gate'])
        self.assertIn('Dry Skin', rows['Parasect']['note'])
        self.assertIn('Effect Spore', rows['Breloom']['note'])

class OfflineCatchUtilityCardTests(unittest.TestCase):
    def test_offline_render_and_long_label_rejection(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'catch-utility.png'
            frozen = json.loads((Path(__file__).parent / 'fixtures/catch-utility-standard.json').read_text())
            card.render(frozen, output, generated='Oct 1, 2026 · 4:00 PM')
            with Image.open(output) as image:
                self.assertEqual(image.size, (1260, 2120))
            frozen['rows'][0]['moves'][0]['gate'] = 'unbreakable_' * 100
            with self.assertRaises(ValueError):
                card.render(frozen, output, generated='offline')
