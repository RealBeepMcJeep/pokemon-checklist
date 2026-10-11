import unittest, json, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
class CaptureDataTests(unittest.TestCase):
    def test_pinned_capture_data_complete_and_form_specific(self):
        path = ROOT / 'data/capture.json'
        self.assertTrue(path.exists(), 'generated pinned capture dataset missing')
        data = json.loads(path.read_text())
        rows = data['pokemon']
        bases = {p['id']: p for p in rows if p['form'] == 0}
        self.assertEqual(set(bases), set(range(1, 808)))
        self.assertEqual(bases[143]['usum']['weight'], 4600)
        self.assertEqual(bases[374]['usum']['weight'], 952)
        self.assertEqual(bases[25]['usum']['speed'], 90)
        self.assertIsNone(bases[803]['sm'])
        alola = next(p for p in rows if p['id'] == 19 and p['form'] == 1)
        self.assertIn('Alolan', alola['name'])
        self.assertEqual(alola['usum']['types'], [16, 0])
        self.assertEqual(subprocess.run([sys.executable, str(ROOT/'tools/build_capture_data.py'), '--check']).returncode, 0)
