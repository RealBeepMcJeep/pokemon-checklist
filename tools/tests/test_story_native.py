"""Exact native search parity; builds are explicit, never a runtime side effect."""
import importlib.util
import itertools
import math
import os
from pathlib import Path
import subprocess
import sys
import unittest

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
import team_options as opt
import team_synergy as ts


class StoryNativeTests(unittest.TestCase):
    def member(self, index, typ=None):
        typ = typ or ts.ALL_TYPES[index % len(ts.ALL_TYPES)]
        return {'final': f'Member{index:03}', 'endpoint_id': index + 200,
                'caught_ids': [index + 199], 'caught_as': [f'Baby{index}'],
                'types': [typ], 'weak': set(), 'resist': set(),
                'moves': [(typ, 80, 1.0)], 'points': float(index % 7),
                'favorite': index % 3 == 0, 'atk': 100, 'spa': 110,
                'bulk': 280, 'spe': 110}

    def native(self):
        self.assertIsNotNone(importlib.util.find_spec('story_native'),
                             'the exact Rust adapter is not implemented')
        import story_native
        if story_native.binary_path() is None:
            cargo = Path('/opt/data/home/.cargo/bin/cargo')
            import shutil
            if not cargo.exists() and not shutil.which('cargo'):
                self.skipTest('explicit native tests require Cargo or a prebuilt binary')
            subprocess.run([sys.executable, str(TOOLS.parent / 'native/story-search/build.py')],
                           check=True, capture_output=True, text=True)
        self.assertIsNotNone(story_native.binary_path())
        return story_native

    def select(self, pool, utility, chart, category):
        return self.native().search(
            ts.PreparedStorySynergy([*pool, utility], chart),
            owned=[sum(1 << i for i in opt._caught_ids(p)) for p in pool],
            opportunities=[opt.evolution_opportunities(p) for p in pool],
            viability=[opt.practical_viability(p) for p in pool],
            additions=[len(p.get('dex_plan', {}).get('new_entries', ())) for p in pool],
            favorites=[bool(p.get('favorite')) for p in pool],
            names=[p['final'] for p in pool], category=category)

    def test_unverified_python_summation_implementation_uses_reference(self):
        native = self.native()
        from unittest.mock import patch
        pool = [self.member(i) for i in range(7)]
        utility = self.member(18, 'Bug')
        with patch.object(native.sys, 'version_info', (3, 99)):
            self.assertIsNone(self.select(pool, utility, {}, 'Mixed'))

    def test_compensated_float_sum_matches_python(self):
        pool = [self.member(i) for i in range(5)]
        utility = self.member(18, 'Bug')
        values = [1000000.0001, 0.0001, -1000000.0, 0.0001, 0.0001]
        for member, value in zip(pool, values):
            member['points'] = value
        result = self.select(pool, utility, {}, 'Best')
        self.assertIsNotNone(result)
        self.assertEqual(result['quality'], round(sum(opt.practical_viability(p) for p in pool) / 5, 4))

    def test_incomplete_native_reply_falls_back(self):
        self.native()
        from unittest.mock import patch
        pool = [self.member(i) for i in range(7)]
        utility = self.member(18, 'Bug')
        with patch.dict(os.environ, {'STORY_NATIVE_DISABLE': '1'}):
            reference = opt._rank(pool, utility, {}, category='Mixed')
        response = subprocess.CompletedProcess([], 0,
            '{"protocol":1,"indices":[0,1,2,3,4],"independent_combinations":21}', '')
        with patch('story_native.subprocess.run', return_value=response):
            self.assertEqual(opt._rank(pool, utility, {}, category='Mixed'), reference)

    def test_randomized_nonuniform_scores_keys_details_and_identities(self):
        self.native()
        import random
        from unittest.mock import patch
        rng = random.Random(2914)
        for trial in range(24):
            pool = [self.member(i) for i in range(9)]
            utility = self.member(18, 'Bug')
            chart = {defender.lower(): {attacker.lower(): rng.randrange(4)
                     for attacker in ts.ALL_TYPES} for defender in ts.ALL_TYPES}
            for i, member in enumerate([*pool, utility]):
                member['types'] = rng.choices(ts.ALL_TYPES, k=2)
                if i % 3 == 0:
                    member['types'] *= 2
                member['weak'] = set(rng.sample(ts.ALL_TYPES, 4))
                member['resist'] = set(rng.sample(ts.ALL_TYPES, 4))
                member['moves'] = ([(typ, 80, 1.0) for typ in member['types']] if trial % 2 == 0
                                   else [(typ, rng.choice([79, 80, 120, 130]),
                                          rng.choice([0.15, 0.99999, 1.0])) for typ in member['types']])
                member['points'] = rng.choice([0.0001, 1.2344, 1.2345, 6.0001])
                member['dex_plan'] = {'new_entries': ['New'] * rng.randrange(4)}
            pool[1]['caught_ids'] = list(pool[0]['caught_ids'])
            pool[3]['final'] = pool[4]['final']
            for category in ('OG', 'Non-OG', 'Mixed', 'Pokedex', 'Best'):
                with self.subTest(trial=trial, category=category):
                    with patch.dict(os.environ, {'STORY_NATIVE_DISABLE': '1'}):
                        reference = opt._rank(pool, utility, chart, category=category)[0]
                    result = opt._rank(pool, utility, chart, category=category)[0]
                    self.assertEqual(result['native_search']['engine'], 'rust')
                    self.assertEqual({k: v for k, v in result.items() if k != 'native_search'}, reference)
                    selected = self.select(pool, utility, chart, category)
                    indices = tuple(selected['indices'])
                    prepared = ts.PreparedStorySynergy([*pool, utility], chart)
                    self.assertEqual(selected['core'], prepared.score(indices))
                    self.assertEqual(selected['full'], prepared.score((*indices, len(pool))))

    def test_duplicate_names_ties_retain_first_independent_identity(self):
        pool = [self.member(i, 'Normal') for i in range(8)]
        utility = self.member(18, 'Bug')
        for member in pool:
            member.update(final='Same', points=1.0, favorite=False)
        pool[1]['caught_ids'] = pool[0]['caught_ids']
        for category in ('OG', 'Non-OG', 'Mixed', 'Pokedex', 'Best'):
            result = self.select(pool, utility, {}, category)
            self.assertEqual(result['indices'], [0, 2, 3, 4, 5])
            self.assertEqual(result['independent_combinations'], math.comb(8, 5) - math.comb(6, 3))
        for member in pool:
            member['caught_ids'] = [2000]
        self.assertIsNone(self.select(pool, utility, {}, 'Mixed')['indices'])
        self.assertEqual(opt._rank(pool, utility, {}, category='Mixed'), [])

    def test_ownership_conflicts_cross_word_boundary(self):
        pool = [self.member(i) for i in range(70)]
        utility = self.member(80, 'Bug')
        for i, member in enumerate(pool):
            member['points'] = 0.0
            member['caught_ids'] = [50000] if i < 65 else [10000 + i]
        pool[0]['caught_ids'].append(77777)
        pool[65]['caught_ids'].append(77777)
        pool[0]['points'], pool[65]['points'] = 9.0, 8.0
        for i in range(66, 70):
            pool[i]['points'] = 20.0
        result = self.select(pool, utility, {}, 'Best')
        self.assertEqual(result['indices'], [0, 66, 67, 68, 69])
        self.assertEqual(result['independent_combinations'], 1 + 64 * math.comb(5, 4) + math.comb(4, 4))

    def test_absent_or_disabled_binary_preserves_python_fallback(self):
        self.native()
        from unittest.mock import patch
        pool = [self.member(i) for i in range(7)]
        utility = self.member(18, 'Bug')
        with patch.dict(os.environ, {'STORY_NATIVE_DISABLE': '1'}):
            reference = opt._rank(pool, utility, {}, category='Mixed')
        with patch.dict(os.environ, {'STORY_NATIVE_BINARY': '/nonexistent/story-search'}):
            self.assertEqual(opt._rank(pool, utility, {}, category='Mixed'), reference)

    def test_python_decimal_rounding_at_adversarial_halves(self):
        native = self.native()
        import random
        rng = random.Random(114)
        values = [0.00005, -0.00005, 1.23445, 1.23455, -1.23445,
                  2.675, math.nextafter(1.23445, math.inf),
                  math.nextafter(1.23445, -math.inf)]
        values += [(rng.randrange(-100000, 100000) + 0.5) / 10000 for _ in range(2000)]
        import json
        run = subprocess.run([str(native.binary_path()), '--round4'],
                             input=' '.join(map(repr, values)), text=True,
                             capture_output=True)
        self.assertEqual(run.returncode, 0, 'native rounding probe is unavailable')
        self.assertEqual(json.loads(run.stdout), [round(v, 4) for v in values])

    def test_integrated_all_objectives_preserve_detailed_reference(self):
        self.native()
        pool = [self.member(i) for i in range(9)]
        utility = self.member(18, 'Bug')
        for index, member in enumerate(pool):
            member['dex_plan'] = {'new_entries': ['New'] * (index % 3)}
        for category in ('OG', 'Non-OG', 'Mixed', 'Pokedex', 'Best'):
            with self.subTest(category=category):
                from unittest.mock import patch
                with patch.dict(os.environ, {'STORY_NATIVE_DISABLE': '1'}):
                    reference = opt._rank(pool, utility, {}, category=category)[0]
                result = opt._rank(pool, utility, {}, category=category)[0]
                self.assertEqual(result.get('native_search', {}).get('engine'), 'rust')
                self.assertEqual({k: v for k, v in result.items() if k != 'native_search'}, reference)

    def test_exact_native_winner_and_full_counts(self):
        pool = [self.member(i) for i in range(7)]
        utility = self.member(18, 'Bug')
        reference = opt._rank(pool, utility, {}, category='Mixed')[0]
        result = self.select(pool, utility, {}, 'Mixed')
        self.assertEqual(tuple(pool[i] for i in result['indices']), reference['profiles'])
        self.assertEqual(result['independent_combinations'], math.comb(7, 5))
        self.assertEqual(result['synergy'], reference['synergy'])
        self.assertEqual(result['core'], reference['core_synergy'])
        self.assertEqual(result['full'], reference['six_synergy'])
        self.assertEqual(result['quality'], reference['viability'])


if __name__ == '__main__':
    unittest.main()
