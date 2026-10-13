"""Real-source tracer for the current-horizon catcher report."""
import json
import subprocess
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import catcher_score as cs

ROOT = Path(__file__).resolve().parents[2]
CACHE = cs.configured_cache_dir()


class CurrentCatcherTests(unittest.TestCase):
    @unittest.skipUnless(CACHE.exists(), 'verified Showdown cache unavailable')
    def test_butterfree_standard_sleep_is_one_status_and_no_false_swipe(self):
        result = subprocess.run([sys.executable, str(ROOT / 'tools/catcher_now.py'),
            '--species', 'butterfree', '--level', '30', '--cache', str(CACHE)],
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        row = json.loads(result.stdout)['rows'][0]
        self.assertEqual(row['name'], 'Butterfree')
        self.assertAlmostEqual(row['score'], 58.5)
        self.assertEqual([p['category'] for p in row['parts']], ['sleep'])
        self.assertEqual(row['parts'][0]['gate'], 'Butterfree L13')
        self.assertFalse(row['false_swipe'])

    @unittest.skipUnless(CACHE.exists(), 'verified Showdown cache unavailable')
    def test_owned_kricketot_can_be_trained_to_kricketune_with_both_tools_by_thirty(self):
        result = subprocess.run([sys.executable, str(ROOT / 'tools/catcher_now.py'),
            '--species', 'kricketot', '--level', '30', '--cache', str(CACHE)],
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        rows = json.loads(result.stdout)['rows']
        self.assertTrue(rows, 'reachable level-10 evolution must be considered')
        self.assertEqual(rows[0]['name'], 'Kricketune')
        self.assertEqual(rows[0]['owned'], 'Kricketot')
        self.assertAlmostEqual(rows[0]['score'], 58)

    @unittest.skipUnless(CACHE.exists(), 'verified Showdown cache unavailable')
    def test_smeargle_uses_owned_donors_and_three_sketch_slots_not_tm_legality(self):
        result = subprocess.run([sys.executable, str(ROOT / 'tools/catcher_now.py'),
            '--species', 'smeargle,paras,gastly,psyduck', '--level', '30', '--cache', str(CACHE)],
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        rows = json.loads(result.stdout)['rows']
        choices = [r for r in rows if r['name'] == 'Smeargle']
        self.assertTrue(choices, 'owned legal donors must enable a labelled Sketch setup option')
        row = choices[0]
        self.assertAlmostEqual(row['score'], 68.96)
        self.assertEqual({p['move'] for p in row['parts']}, {'Spore', 'False Swipe', 'Mean Look'})
        self.assertTrue(all(p['source']['via'] == 'sketch' for p in row['parts']))
        self.assertTrue(row['setup_required'])

    @unittest.skipUnless(CACHE.exists(), 'verified Showdown cache unavailable')
    def test_real_report_renders_a_png_and_retains_score_snapshot(self):
        import os
        import tempfile
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as folder:
            result = subprocess.run([sys.executable, str(ROOT / 'tools/catcher_now.py'),
                '--species', 'butterfree', '--cache', str(CACHE), '--output-dir', folder],
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((Path(folder) / 'catchers.png').read_bytes()[:8], b'\x89PNG\r\n\x1a\n')
            report = json.loads((Path(folder) / 'report.json').read_text())
            self.assertEqual(report['rows'][0]['score'], 58.5)

    @unittest.skipUnless(CACHE.exists(), 'verified Showdown cache unavailable')
    def test_dense_five_choice_card_does_not_overflow(self):
        import os
        import tempfile
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as folder:
            result = subprocess.run([sys.executable, str(ROOT / 'tools/catcher_now.py'),
                '--species', 'butterfree,paras,smeargle,gastly,kricketot,smoochum,psyduck',
                '--cache', str(CACHE), '--output-dir', folder], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((Path(folder) / 'catchers.png').exists())

    @unittest.skipUnless(CACHE.exists(), 'verified Showdown cache unavailable')
    def test_paras_prefers_safe_ordinary_ability_without_changing_score(self):
        result = subprocess.run([sys.executable, str(ROOT / 'tools/catcher_now.py'),
            '--species', 'paras', '--cache', str(CACHE)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        row = json.loads(result.stdout)['rows'][0]
        self.assertEqual(row['ability'], 'Dry Skin')
        self.assertEqual(row['score'], 85)


if __name__ == '__main__':
    unittest.main()
