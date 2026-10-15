"""Deterministic bounded parallel fused search on synthetic feature wires."""
import json
import os
import subprocess
import unittest

import test_story_pruning as pruning


def fused_wire(values, *, flags=None, **kwargs):
    base = pruning.wire(values, 'Mixed', **kwargs)
    flags = flags if flags is not None else [True] * len(values)
    return '2' + base[1:] + ' ' + ' '.join(str(int(v)) for v in flags)


class ParallelSearchTests(unittest.TestCase):
    def kernel(self):
        return pruning.PrimarySubtreeTests().kernel()

    def test_explicit_two_workers_execute_prefix_tasks_with_identical_reply(self):
        text = fused_wire([float(i) for i in range(16)], flags=[i % 3 != 0 for i in range(16)])
        control = subprocess.run([str(self.kernel())], input=text, text=True,
                                 capture_output=True, check=True,
                                 env={**os.environ, 'STORY_NATIVE_THREADS': '1'})
        run = subprocess.run([str(self.kernel()), '--pruning-stats'], input=text,
                             text=True, capture_output=True, check=True,
                             env={**os.environ, 'STORY_NATIVE_THREADS': '2'})
        stats = json.loads(run.stderr)
        self.assertEqual(stats.get('worker_threads', 0), 2,
                         'explicit two-thread requests must spawn two real worker threads')
        self.assertGreater(stats['prefix_tasks'], 0)
        self.assertEqual(run.stdout, control.stdout)
        self.assertEqual(control.stderr, '')


    def test_twenty_repeated_schedules_preserve_full_bytes_for_all_thread_counts(self):
        import random
        rng = random.Random(10010)
        cases = [fused_wire([1.0] * 10, names=[0] * 10),
                 fused_wire([1.0] * 9, flags=[False] * 9, names=[0] * 9),
                 fused_wire([1e8, 0.00005, -1e8, 1.23445, -1.23445, 0.0, -0.0, 1e-300, 2.0],
                            flags=[i % 3 != 0 for i in range(9)], names=[0] * 9)]
        conflicts = [{j for j in range(10) if rng.random() < 0.12} for _ in range(10)]
        cases.append(fused_wire([float(i % 3) for i in range(10)], conflicts=conflicts,
                                flags=[i % 2 == 0 or i > 6 for i in range(10)],
                                names=[i % 2 for i in range(10)], compensated=0))
        comparisons = 0
        for text in cases:
            control = subprocess.run([str(self.kernel())], input=text, text=True,
                                     capture_output=True, check=True,
                                     env={**os.environ, 'STORY_NATIVE_THREADS': '1'}).stdout
            for threads in (1, 2, 3, 4, 8):
                for repeat in range(20):
                    run = subprocess.run([str(self.kernel())], input=text, text=True,
                                         capture_output=True, check=True,
                                         env={**os.environ, 'STORY_NATIVE_THREADS': str(threads)})
                    self.assertEqual(run.stdout, control, (threads, repeat))
                    self.assertEqual(run.stderr, '')
                    comparisons += 1
        self.assertEqual(comparisons, 400)

    def test_default_and_protocol_one_never_spawn_workers(self):
        env = {k: v for k, v in os.environ.items() if k != 'STORY_NATIVE_THREADS'}
        text = fused_wire([float(i) for i in range(9)])
        default = subprocess.run([str(self.kernel()), '--pruning-stats'], input=text,
                                 text=True, capture_output=True, check=True, env=env)
        self.assertEqual(json.loads(default.stderr)['worker_threads'], 0)
        one = subprocess.run([str(self.kernel())], input=text, text=True, capture_output=True,
                             check=True, env={**env, 'STORY_NATIVE_THREADS': '1'})
        self.assertEqual(one.stdout, default.stdout)
        for category in ('OG', 'Non-OG', 'Mixed', 'Best', 'Pokedex'):
            ordinary = pruning.wire([float(i) for i in range(9)], category)
            a = subprocess.run([str(self.kernel()), '--pruning-stats'], input=ordinary,
                               text=True, capture_output=True, check=True, env=env)
            for setting in ('8', 'invalid'):
                b = subprocess.run([str(self.kernel()), '--pruning-stats'], input=ordinary,
                                   text=True, capture_output=True, check=True,
                                   env={**env, 'STORY_NATIVE_THREADS': setting})
                self.assertEqual(a.stdout, b.stdout)
                self.assertEqual(json.loads(b.stderr)['worker_threads'], 0)

    def test_invalid_opt_in_is_diagnosable_and_original_fallback_still_works(self):
        text = fused_wire([1.0] * 8)
        for setting in ('0', '-1', '5', '999999', 'nope', '2.0', ' 2 ', ''):
            run = subprocess.run([str(self.kernel())], input=text, text=True, capture_output=True,
                                 env={**os.environ, 'STORY_NATIVE_THREADS': setting})
            self.assertNotEqual(run.returncode, 0)
            self.assertEqual(run.stdout, '')
            self.assertIn('STORY_NATIVE_THREADS', run.stderr)
        import test_story_native as fixtures
        import team_options as opt
        from unittest.mock import patch
        fixture = fixtures.StoryNativeTests()
        fixture.native()
        pool = [fixture.member(i) for i in range(8)]
        utility = fixture.member(18, 'Bug')
        with patch.dict(os.environ, {'STORY_NATIVE_THREADS': '1'}):
            reference = opt.choose_options(pool, utility, {})
        with patch.dict(os.environ, {'STORY_NATIVE_THREADS': 'invalid'}):
            self.assertEqual(opt.choose_options(pool, utility, {}), reference)

    def test_empty_prefix_sets_and_word_boundaries_match_single_thread(self):
        for n in (0, 4, 65, 129, 257):
            text = fused_wire([1.0] * n, conflicts=[set(range(n)) for _ in range(n)])
            control = subprocess.run([str(self.kernel())], input=text, text=True,
                                     capture_output=True, check=True,
                                     env={**os.environ, 'STORY_NATIVE_THREADS': '1'})
            for threads in (2, 4, 8):
                run = subprocess.run([str(self.kernel()), '--pruning-stats'], input=text,
                                     text=True, capture_output=True, check=True,
                                     env={**os.environ, 'STORY_NATIVE_THREADS': str(threads)})
                self.assertEqual(run.stdout, control.stdout)
                self.assertEqual(json.loads(run.stderr)['worker_threads'], 0)
                self.assertEqual(json.loads(run.stderr)['prefix_tasks'], 0)


if __name__ == '__main__':
    unittest.main()
