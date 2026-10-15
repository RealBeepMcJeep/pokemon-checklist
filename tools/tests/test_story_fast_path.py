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


    def test_runtime_category_kind_matches_the_resolved_numeric_priority(self):
        for label, kind in [('OG', 'Synergy'), ('Non-OG', 'Synergy'), ('Mixed', 'Synergy'),
                            ('Pokedex', 'Pokedex'), ('Best', 'Best'), ('Future', 'Synergy')]:
            with self.subTest(label=label):
                text = wire([float(i) for i in range(6)], label)
                run = subprocess.run([str(self.kernel()), '--pruning-stats'], input=text,
                                     capture_output=True, text=True, check=True)
                self.assertEqual(json.loads(run.stderr).get('category_kind'), kind,
                                 'diagnostic must expose the actual resolved dispatch category')
                normal = subprocess.run([str(self.kernel())], input=text, capture_output=True,
                                        text=True, check=True)
                self.assertEqual(normal.stdout, run.stdout)
                self.assertEqual(normal.stderr, '')


    def test_conflict_masks_filter_candidates_with_exact_counts(self):
        n = 12
        values = [float(i) for i in range(n)]
        conflicts = [{i} for i in range(n)]
        conflicts[3].add(0)
        conflicts[7].add(2)
        text = wire(values, 'Mixed', conflicts=conflicts)
        run = subprocess.run([str(self.kernel()), '--pruning-stats'], input=text,
                             capture_output=True, text=True, check=True)
        stats = json.loads(run.stderr)
        tested = rejected = 0
        def walk(start, depth, prefix):
            nonlocal tested, rejected
            if depth == 5 or start > n - (5 - depth):
                return
            for i in range(start, n - (5 - depth) + 1):
                tested += 1
                if any(j in conflicts[i] for j in prefix):
                    rejected += 1
                    continue
                walk(i + 1, depth + 1, prefix + [i])
        walk(0, 0, [])
        self.assertIs(stats.get('mask_mode'), True,
                      'RED: absent pre-mask diagnostic; GREEN: mask path engaged')
        self.assertEqual(stats.get('candidates_tested'), tested,
                         'every original candidate test must still happen, rejected by mask')
        self.assertEqual(stats.get('mask_rejected'), rejected)
        normal = subprocess.run([str(self.kernel())], input=text, capture_output=True,
                                text=True, check=True)
        self.assertEqual(normal.stdout, run.stdout)


if __name__ == '__main__':
    unittest.main()
