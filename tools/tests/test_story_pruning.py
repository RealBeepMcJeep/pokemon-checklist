"""End-to-end unfinished-branch pruning; ordinary protocol output stays exact."""
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
import story_native


def wire(values, category, *, additions=None, conflicts=None, names=None, compensated=1):
    """Synthetic prepared features, not factual species/account data."""
    n = len(values)
    words = (n + 63) // 64
    tokens = ['1', str(n), category, str(compensated), '1', '1.0', '1']
    for _ in range(n + 1):
        tokens += ['0', '0', '1'] + ['1.0'] + ['0.0'] * 17 + ['0'] * (n + 1)
    for i, value in enumerate(values):
        row = conflicts[i] if conflicts is not None else {i}
        masks = [sum(1 << (j % 64) for j in row if j // 64 == word) for word in range(words)]
        tokens += [repr(value), '0', str(additions[i] if additions is not None else 0),
                   '0', str(names[i] if names is not None else i)]
        tokens += list(map(str, masks))
    return ' '.join(tokens)


class PrimarySubtreeTests(unittest.TestCase):
    def kernel(self):
        path = story_native.binary_path()
        if path is None:
            if not shutil.which('cargo') and not Path('/opt/data/home/.cargo/bin/cargo').exists():
                self.skipTest('native subtree tests require explicit Cargo/prebuilt support')
            subprocess.run([sys.executable, str(TOOLS.parent / 'native/story-search/build.py')],
                           check=True, capture_output=True, text=True)
            path = story_native.binary_path()
        self.assertIsNotNone(path)
        return path

    def run_wire(self, text, *flags):
        run = subprocess.run([str(self.kernel()), *flags], input=text, text=True,
                             capture_output=True, check=True)
        return json.loads(run.stdout), json.loads(run.stderr or '{}')

    def test_best_prunes_unfinished_subtrees_without_changing_wire_counters(self):
        values = [float(20 - i) for i in range(12)]
        text = wire(values, 'Best')
        answer, stats = self.run_wire(text, '--pruning-stats')
        self.assertEqual(answer['indices'], [0, 1, 2, 3, 4])
        self.assertEqual(answer['independent_combinations'], math.comb(12, 5))
        self.assertEqual(answer['scored_combinations'], 1)
        self.assertEqual(answer['primary_skips'], math.comb(12, 5) - 1)
        self.assertGreater(stats.get('pruned_subtrees', 0), 0,
                           'leaf-only skips do not implement unfinished-branch pruning')
        self.assertLess(stats['leaf_visits'], answer['independent_combinations'])
        normal, normal_stats = self.run_wire(text)
        self.assertEqual(normal, answer)
        self.assertEqual(normal_stats, {}, 'ordinary native calls must remain quiet')


    def test_pokedex_prunes_unfinished_addition_branches_with_exact_counters(self):
        values = [0.0] * 12
        text = wire(values, 'Pokedex', additions=list(range(20, 8, -1)))
        answer, stats = self.run_wire(text, '--pruning-stats')
        self.assertEqual(answer['indices'], [0, 1, 2, 3, 4])
        self.assertEqual(answer['independent_combinations'], math.comb(12, 5))
        self.assertEqual(answer['scored_combinations'], 1)
        self.assertEqual(answer['primary_skips'], math.comb(12, 5) - 1)
        self.assertGreater(stats.get('pruned_subtrees', 0), 0,
                           'integer leaf skips do not implement unfinished-branch pruning')
        self.assertLess(stats['leaf_visits'], answer['independent_combinations'])
        normal, normal_stats = self.run_wire(text)
        self.assertEqual(normal, answer)
        self.assertEqual(normal_stats, {})

    def test_frozen_small_pools_match_exhaustive_python_scores_and_every_counter(self):
        import itertools
        import random
        rng = random.Random(7017)
        compensated = int(sys.version_info >= (3, 12))
        cases = [[1e8, 0.00005, -1e8, 1.23445, -1.23445, 0.0, -0.0, 1e-300],
                 [1.23445, math.nextafter(1.23445, math.inf),
                  math.nextafter(1.23445, -math.inf)] * 3]
        cases += [[rng.choice([-1e8, 1e8, 0.00005, -0.00005, 1.23455,
                               1.23445, 3.2, -2.1, 0.0, 1e-300])
                   for _ in range(rng.randrange(5, 11))] for _ in range(80)]
        for values in cases:
            n = len(values)
            additions = [rng.randrange(5) for _ in values]
            names = [rng.randrange(4) for _ in values]
            conflicts = [{i} for i in range(n)]
            for i in range(n):
                for j in range(n):
                    if i != j and rng.random() < 0.12:
                        conflicts[i].add(j)
            for category in ('Best', 'Pokedex', 'Mixed'):
                with self.subTest(n=n, category=category, values=values):
                    expected = self.reference(values, category, additions, conflicts, names,
                                              itertools.combinations(range(n), 5))
                    actual, _ = self.run_wire(wire(values, category, additions=additions,
                                                  conflicts=conflicts, names=names,
                                                  compensated=compensated))
                    self.assertEqual(actual, expected)

    def reference(self, values, category, additions, conflicts, names, combinations):
        answer = {'protocol': 1, 'indices': None}
        independent = scored = skips = 0
        best_key = None
        core = round(4.0 / 18.0 + 2.5, 4)
        synergy = round(0.65 * core + 0.35 * core, 4)
        for indices in combinations:
            if any(j in conflicts[i] for pos, i in enumerate(indices) for j in indices[:pos]):
                continue
            independent += 1
            quality = round(sum(values[i] for i in indices) / 5, 4)
            gained = sum(additions[i] for i in indices)
            primary = quality if category == 'Best' else gained
            if best_key is not None and category in ('Best', 'Pokedex') and primary < best_key[0]:
                skips += 1
                continue
            scored += 1
            tie = tuple(-v for v in sorted(names[i] for i in indices))
            key = ((quality, synergy, 0, tie) if category == 'Best' else
                   (gained, synergy, quality, 0, tie) if category == 'Pokedex' else
                   (synergy, 0, quality, 0, tie))
            if best_key is None or key > best_key:
                best_key = key
                answer.update(indices=list(indices), quality=quality, core=core,
                              full=core, synergy=synergy)
        answer.update(independent_combinations=independent, scored_combinations=scored,
                      primary_skips=skips)
        return answer

    def test_completion_masks_cross_words_and_retain_duplicate_name_ties(self):
        import itertools
        n = 70
        values = [float(80 - i) for i in range(n)]
        additions = [5 if i < 65 else 1 for i in range(n)]
        names = [0] * n
        conflicts = [set(range(65)) if i < 65 else {i} for i in range(n)]
        conflicts[0].add(65)
        conflicts[65].add(0)
        combinations = [(i, *tail) for i in range(65)
                        for tail in itertools.combinations(range(65, 70), 4)]
        combinations.append(tuple(range(65, 70)))
        for category in ('Best', 'Pokedex'):
            expected = self.reference(values, category, additions, conflicts, names, combinations)
            actual, _ = self.run_wire(wire(values, category, additions=additions,
                                          conflicts=conflicts, names=names))
            self.assertEqual(actual, expected)
            self.assertEqual(actual['independent_combinations'], 322)


if __name__ == '__main__':
    unittest.main()
