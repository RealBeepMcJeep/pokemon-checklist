"""Exact dual results from a single traversal; synthetic features, no personal data."""
import json
import subprocess
import unittest

import test_story_pruning as pruning
from test_story_pruning import wire


# Do not inherit PrimarySubtreeTests (that would duplicate its collected methods).
class FusedTraversalTests(unittest.TestCase):
    def kernel(self):
        return pruning.PrimarySubtreeTests().kernel()

    def test_fused_request_returns_two_standalone_results(self):
        values = [float(i % 3) for i in range(9)]
        flags = [True, False, True, True, False, True, True, False, True]
        names = [2, 1, 0, 2, 1, 0, 2, 1, 0]
        mixed_wire = wire(values, 'Mixed', names=names)
        fused_wire = '2' + mixed_wire[1:] + ' ' + ' '.join(str(int(v)) for v in flags)
        run = subprocess.run([str(self.kernel())], input=fused_wire, capture_output=True, text=True)
        self.assertEqual(run.returncode, 0,
                         'the kernel must accept a genuine fused protocol-2 request: ' + run.stderr)
        self.assertEqual(run.stderr, '')
        answer = json.loads(run.stdout)
        self.assertEqual(answer['protocol'], 2)
        mixed = subprocess.run([str(self.kernel())], input=mixed_wire, capture_output=True,
                               text=True, check=True)
        selected = [i for i, flag in enumerate(flags) if flag]
        subset = subprocess.run([str(self.kernel())], input=wire(
            [values[i] for i in selected], 'Non-OG', names=[names[i] for i in selected]),
            capture_output=True, text=True, check=True)
        self.assertEqual(answer['mixed'], json.loads(mixed.stdout))
        self.assertEqual(answer['nonog'], json.loads(subset.stdout))


    def test_compatible_adapter_pair_runs_one_native_process(self):
        import test_story_native as fixtures
        import story_native
        import team_synergy as ts
        from unittest.mock import patch
        fixture = fixtures.StoryNativeTests()
        fixture.native()
        pool = [fixture.member(i) for i in range(9)]
        utility = fixture.member(18, 'Bug')
        subset = [0, 2, 3, 5, 6, 8]
        prepared = ts.PreparedStorySynergy([*pool, utility], {})
        subprepared = ts.PreparedStorySynergy([*(pool[i] for i in subset), utility], {})
        args = dict(owned=[1 << i for i in range(9)], opportunities=[0] * 9,
                    viability=[float(i % 3) for i in range(9)], additions=[0] * 9,
                    favorites=[False] * 9, names=[p['final'] for p in pool])
        adapter = getattr(story_native, 'search_pair', None)
        self.assertTrue(callable(adapter), 'a compatible pair needs a real fused adapter')
        original = subprocess.run
        with patch.object(story_native.subprocess, 'run', wraps=original) as calls:
            pair = adapter(prepared, subprepared, subset=subset, **args)
        self.assertEqual(calls.call_count, 1, 'do not disguise two searches as fusion')
        self.assertIsNotNone(pair)
        self.assertEqual(pair['Mixed'], story_native.search(prepared, category='Mixed', **args))
        subargs = {key: [values[i] for i in subset] for key, values in args.items()}
        self.assertEqual(pair['Non-OG'], story_native.search(subprepared, category='Non-OG', **subargs))


    def test_choose_options_engages_fusion_without_changing_any_report(self):
        import os
        import test_story_native as fixtures
        import story_native
        import team_options as opt
        from unittest.mock import patch
        fixture = fixtures.StoryNativeTests()
        fixture.native()
        pool = [fixture.member(i) for i in range(9)]
        utility = fixture.member(18, 'Bug')
        for i in (1, 4, 7):
            pool[i].update(endpoint_id=i, caught_ids=[i])
        with patch.dict(os.environ, {'STORY_NATIVE_FUSION_DISABLE': '1'}):
            reference = opt.choose_options(pool, utility, {})
        original = subprocess.run
        requests = []
        def observe(command, *args, **kwargs):
            if command == [str(story_native.binary_path())]:
                requests.append(kwargs['input'].split()[0])
            return original(command, *args, **kwargs)
        with patch.object(story_native.subprocess, 'run', side_effect=observe):
            actual = opt.choose_options(pool, utility, {})
        self.assertEqual(requests.count('2'), 1, 'choose_options must engage one real fused request')
        self.assertEqual(actual, reference)


    def test_random_subsets_match_separate_native_and_exhaustive_python(self):
        import os
        import random
        import test_story_native as fixtures
        import story_native
        import team_options as opt
        import team_synergy as ts
        from unittest.mock import patch
        fixture = fixtures.StoryNativeTests()
        fixture.native()
        rng = random.Random(9009)
        engaged = 0
        for trial in range(48):
            n = rng.randrange(6, 11)
            subset = sorted(rng.sample(range(n), rng.randrange(5, n + 1)))
            pool = [fixture.member(i) for i in range(n)]
            utility = fixture.member(18, 'Bug')
            chart = {d.lower(): {a.lower(): rng.randrange(3) for a in ts.ALL_TYPES}
                     for d in ts.ALL_TYPES}
            for i, member in enumerate([*pool, utility]):
                member.update(weak=set(rng.sample(ts.ALL_TYPES, 3)),
                              resist=set(rng.sample(ts.ALL_TYPES, 3)),
                              points=rng.choice([0.00005, 1.23445, 1e-300, 2.0]),
                              final='Same' if trial % 3 == 0 else member['final'])
                if trial % 2:
                    member['moves'] = [(member['types'][0], rng.choice([79, 80, 120]),
                                        rng.choice([0.15, 1.0]))]
                if i < n and i not in subset:
                    member.update(endpoint_id=i + 1, caught_ids=[i + 1])
            utility['final'] = 'Utility'
            if trial % 4 == 0:
                pool[subset[1]]['caught_ids'] = pool[subset[0]]['caught_ids']
            prepared = ts.PreparedStorySynergy([*pool, utility], chart)
            subpool = [pool[i] for i in subset]
            subprepared = ts.PreparedStorySynergy([*subpool, utility], chart)
            args = dict(owned=[sum(1 << x for x in opt._caught_ids(p)) for p in pool],
                        opportunities=[opt.evolution_opportunities(p) for p in pool],
                        viability=[opt.practical_viability(p) for p in pool],
                        additions=[0] * n, favorites=[p['favorite'] for p in pool],
                        names=[p['final'] for p in pool])
            pair = story_native.search_pair(prepared, subprepared, subset=subset, **args)
            if pair is not None:
                engaged += 1
                self.assertEqual(pair['Mixed'], story_native.search(prepared, category='Mixed', **args))
                subargs = {k: [v[i] for i in subset] for k, v in args.items()}
                self.assertEqual(pair['Non-OG'], story_native.search(subprepared, category='Non-OG', **subargs))
            with patch.dict(os.environ, {'STORY_NATIVE_DISABLE': '1'}):
                reference = opt.choose_options(pool, utility, chart)
            actual = opt.choose_options(pool, utility, chart)
            self.assertEqual([{k: v for k, v in a.items() if k != 'native_search'} for a in actual], reference)
        self.assertGreaterEqual(engaged, 40, 'random coverage must really execute the fused path')

    def test_pair_gate_and_malformed_reply_fall_back_without_changed_reports(self):
        import copy
        import os
        import test_story_native as fixtures
        import story_native
        import team_options as opt
        import team_synergy as ts
        from unittest.mock import patch
        fixture = fixtures.StoryNativeTests()
        fixture.native()
        pool = [fixture.member(i) for i in range(8)]
        utility = fixture.member(18, 'Bug')
        subset = [0, 2, 3, 4, 6, 7]
        for i in (1, 5):
            pool[i].update(endpoint_id=i, caught_ids=[i])
        prepared = ts.PreparedStorySynergy([*pool, utility], {})
        subprepared = ts.PreparedStorySynergy([*(pool[i] for i in subset), utility], {})
        args = dict(owned=[1 << i for i in range(8)], opportunities=[0] * 8,
                    viability=[1.0] * 8, additions=[0] * 8, favorites=[False] * 8,
                    names=[p['final'] for p in pool])
        for field in ('uniform', 'strength', 'disjoint', 'weak', 'overlap'):
            changed = copy.deepcopy(subprepared)
            if field in ('uniform', 'disjoint'):
                setattr(changed, field, not getattr(changed, field))
            elif field == 'strength':
                changed.strength += 1.0
            elif field == 'weak':
                changed.weak[0] ^= 1
            else:
                changed.overlap[0][0] += 1
            with patch.object(story_native.subprocess, 'run') as run:
                self.assertIsNone(story_native.search_pair(prepared, changed, subset=subset, **args))
                run.assert_not_called()
        for bad_subset in ([0, 1, 2, 3], [0, 0, 1, 2, 3, 4], [4, 3, 2, 1, 0], [0, 1, 2, 3, 99]):
            self.assertIsNone(story_native.search_pair(prepared, subprepared, subset=bad_subset, **args))
        with patch.dict(os.environ, {'STORY_NATIVE_FUSION_DISABLE': '1'}):
            reference = opt.choose_options(pool, utility, {})
        original = subprocess.run
        for stdout in (None, '{}', '{"protocol":2,"mixed":{}}', 'not json',
                       '{"protocol":1}', '{"protocol":2,"mixed":null,"nonog":null}'):
            def broken_pair(command, *a, **kw):
                if command == [str(story_native.binary_path())] and kw['input'].split()[0] == '2':
                    if stdout is None:
                        raise subprocess.CalledProcessError(101, command, stderr='old protocol-only executable')
                    return subprocess.CompletedProcess(command, 0, stdout, '')
                return original(command, *a, **kw)
            with patch.object(story_native.subprocess, 'run', side_effect=broken_pair):
                self.assertEqual(opt.choose_options(pool, utility, {}), reference)

    def test_fused_arbitrary_word_count_and_empty_subset_keep_exact_counts(self):
        for n in (4, 65, 129, 257):
            text = wire([1.0] * n, 'Mixed', conflicts=[set(range(n)) for _ in range(n)])
            for flag in (0, 1):
                fused = '2' + text[1:] + ' ' + ' '.join([str(flag)] * n)
                run = subprocess.run([str(self.kernel()), '--pruning-stats'], input=fused,
                                     capture_output=True, text=True, check=True)
                answer = json.loads(run.stdout)
                for key in ('mixed', 'nonog'):
                    self.assertIsNone(answer[key]['indices'])
                    self.assertEqual(answer[key]['independent_combinations'], 0)
                    self.assertEqual(answer[key]['scored_combinations'], 0)
                self.assertEqual(json.loads(run.stderr)['fused_reused_scores'], 0)


    def test_incomplete_metadata_is_a_pair_miss_not_an_exception(self):
        import test_story_native as fixtures
        import story_native
        import team_synergy as ts
        fixture = fixtures.StoryNativeTests()
        fixture.native()
        pool = [fixture.member(i) for i in range(6)]
        utility = fixture.member(18, 'Bug')
        prepared = ts.PreparedStorySynergy([*pool, utility], {})
        error = result = None
        try:
            result = story_native.search_pair(
                prepared, prepared, subset=list(range(6)), owned=[], opportunities=[0] * 6,
                viability=[1.0] * 6, additions=[0] * 6, favorites=[False] * 6,
                names=[p['final'] for p in pool])
        except Exception as exc:
            error = type(exc).__name__
        self.assertIsNone(error, 'incomplete pair metadata must fail open before projection')
        self.assertIsNone(result)


    def test_asymmetric_subset_wires_match_standalone_in_both_sum_modes(self):
        import random
        rng = random.Random(97009)
        for case in range(96):
            n = rng.randrange(5, 11)
            values = [rng.choice([1e8, -1e8, 1.23445, 1e-300, 0.0, -0.0]) for _ in range(n)]
            names = [rng.randrange(4) for _ in range(n)]
            conflicts = [{j for j in range(n) if rng.random() < 0.18} for _ in range(n)]
            subset = sorted(rng.sample(range(n), rng.randrange(n + 1)))
            subconflicts = [{b for b, j in enumerate(subset) if j in conflicts[i]} for i in subset]
            for compensated in (0, 1):
                text = wire(values, 'Mixed', names=names, conflicts=conflicts, compensated=compensated)
                fused = '2' + text[1:] + ' ' + ' '.join(str(int(i in subset)) for i in range(n))
                run = subprocess.run([str(self.kernel()), '--pruning-stats'], input=fused,
                                     capture_output=True, text=True, check=True)
                answer = json.loads(run.stdout)
                for label, request in (
                        ('mixed', text),
                        ('nonog', wire([values[i] for i in subset], 'Non-OG',
                                       names=[names[i] for i in subset], conflicts=subconflicts,
                                       compensated=compensated))):
                    separate = subprocess.run([str(self.kernel())], input=request,
                                              capture_output=True, text=True, check=True)
                    self.assertEqual(answer[label], json.loads(separate.stdout))
                self.assertEqual(json.loads(run.stderr)['fused_reused_scores'],
                                 answer['nonog']['scored_combinations'])


    def test_unsupported_mixed_feature_shape_misses_before_projection(self):
        import test_story_native as fixtures
        import story_native
        import team_synergy as ts
        fixture = fixtures.StoryNativeTests()
        fixture.native()
        pool = [fixture.member(i) for i in range(6)]
        utility = fixture.member(18, 'Bug')
        prepared = ts.PreparedStorySynergy([*pool, utility], {})
        subprepared = ts.PreparedStorySynergy([*pool, utility], {})
        prepared.weak.pop()  # The original standalone adapter rejects this shape.
        args = dict(owned=[1 << i for i in range(6)], opportunities=[0] * 6,
                    viability=[1.0] * 6, additions=[0] * 6, favorites=[False] * 6,
                    names=[p['final'] for p in pool])
        self.assertIsNone(story_native.search(prepared, category='Mixed', **args))
        error = result = None
        try:
            result = story_native.search_pair(prepared, subprepared, subset=list(range(6)), **args)
        except Exception as exc:
            error = type(exc).__name__
        self.assertIsNone(error, 'unsupported feature shape must miss before subset projection')
        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()
