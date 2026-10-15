"""Production fast-path engagement without changing ordinary wire results."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

TOOLS = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(TOOLS), str(Path(__file__).resolve().parent)]
import story_native
from test_story_pruning import wire


class NativeFastPathTests(unittest.TestCase):
    def kernel(self):
        path = story_native.binary_path()
        if path is None:
            if not shutil.which('cargo') and not Path('/opt/data/home/.cargo/bin/cargo').exists():
                self.skipTest('native tests require Cargo or an explicit prebuilt executable')
            subprocess.run([sys.executable, str(TOOLS.parent / 'native/story-search/build.py')],
                           capture_output=True, text=True, check=True)
            path = story_native.binary_path()
        self.assertIsNotNone(path)
        return path

    def test_numeric_losers_do_not_materialize_sorted_names(self):
        text = wire([float(20 - i) for i in range(12)], 'Mixed')
        run = subprocess.run([str(self.kernel()), '--pruning-stats'], input=text,
                             capture_output=True, text=True, check=True)
        answer = json.loads(run.stdout)
        stats = json.loads(run.stderr)
        self.assertEqual(answer['indices'], [0, 1, 2, 3, 4])
        self.assertEqual(answer['scored_combinations'], 792)
        self.assertEqual(answer['primary_skips'], 0)
        self.assertEqual(stats.get('name_sorts', answer['scored_combinations']), 1,
                         'only the initial incumbent needs sorted names; numeric losers cannot win')
        normal = subprocess.run([str(self.kernel())], input=text, capture_output=True,
                                text=True, check=True)
        self.assertEqual(normal.stdout, run.stdout)
        self.assertEqual(normal.stderr, '')


if __name__ == '__main__':
    unittest.main()
