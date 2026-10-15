"""Portable item evidence tests: no account or local source cache required."""
import importlib.util
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class ItemEvidenceTests(unittest.TestCase):
    def test_gen7_overrides_and_generation_filter_are_both_required(self):
        self.assertIsNotNone(importlib.util.find_spec('held_items'), 'missing item analysis')
        import held_items as hi
        base = '''exports.BattleItems = {
\twidelens: {name: "Wide Lens", gen: 4, desc: "Holder's accuracy is 1.1x."},
\tfigyberry: {name: "Figy Berry", gen: 3, desc: "One third HP.", isBerry: true},
\theavydutyboots: {name: "Heavy-Duty Boots", gen: 8, desc: "Not Gen VII."},
};'''
        mod = '''let BattleItems = {
\tfigyberry: {inherit: true, desc: "Half HP. Single use."},
};'''
        items = hi.parse_items(base, mod)
        self.assertNotIn('heavydutyboots', items)
        self.assertEqual(items['figyberry']['effect'], 'Half HP. Single use.')
        self.assertEqual(items['figyberry']['kind'], 'berry')
        self.assertEqual(items['widelens']['effect'], "Holder's accuracy is 1.1x.")
        self.assertEqual(hi.resolve_item('Wide Lens', items)['id'], 'widelens')
        with self.assertRaisesRegex(ValueError, 'unknown|Generation'):
            hi.resolve_item('Heavy-Duty Boots', items)


    def test_item_usage_uses_its_own_weight_sum_not_species_usage(self):
        import held_items as hi
        self.assertTrue(callable(getattr(hi, 'item_usage', None)), 'missing item usage normalization')
        items = {'leftovers': {'id': 'leftovers', 'name': 'Leftovers', 'gen': 2},
                 'lifeorb': {'id': 'lifeorb', 'name': 'Life Orb', 'gen': 4}}
        block = {'Raw count': 200, 'usage': .9, 'Items': {'leftovers': 3.0, 'lifeorb': 1.0}}
        result = hi.item_usage(block, items)
        self.assertEqual(result['denominator'], 4.0)
        self.assertEqual(result['raw_count'], 200)
        self.assertEqual([x['share'] for x in result['items']], [.75, .25])
        self.assertEqual(hi.item_usage(None, items)['status'], 'missing')
        self.assertEqual(hi.item_usage({'Items': {}}, items)['status'], 'empty')
        for weights in [{'leftovers': -1}, {'leftovers': float('nan')}, {'leftovers': True}, {'bogus': 1}]:
            with self.subTest(weights=weights), self.assertRaises(ValueError):
                hi.item_usage({'Items': weights}, items)


    def test_addon_sources_cannot_replace_or_bypass_core_manifest(self):
        import held_items as hi
        self.assertTrue(callable(getattr(hi, 'source_store', None)), 'missing isolated source store')
        import tempfile
        import hashlib
        from showdown_data import DatasetSpec, CacheIntegrityError
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            core = root / 'showdown-manifest.json'
            core.write_text('core sentinel')
            data = b'fixed test source'
            spec = DatasetSpec('items', 'items.js', 'https://raw.githubusercontent.com/example/pin/items.js', hashlib.sha256(data).hexdigest())
            store = hi.source_store(root, datasets={'items': spec}, downloader=lambda _: data)
            store.bootstrap()
            self.assertEqual(core.read_text(), 'core sentinel')
            self.assertEqual(store.get_text('items'), data.decode())
            (root / 'held-items-gen7' / 'items.js').write_text('corrupted')
            with self.assertRaises(CacheIntegrityError):
                hi.source_store(root, datasets={'items': spec}).get_text('items')


    def test_mago_uses_gen7_callback_instead_of_known_stale_description(self):
        import held_items as hi
        base = '\n\tmagoberry: {name: "Mago Berry", gen: 3, isBerry: true, onUpdate(pokemon) {if (pokemon.hp <= pokemon.maxhp / 4) pokemon.eatItem();}}'
        mod = '\n\tmagoberry: {inherit: true, desc: "Restores 1/8 max HP at 1/2 max HP or less.", onEat(pokemon) {this.heal(pokemon.maxhp / 2);}}'
        item = hi.parse_items(base, mod)['magoberry']
        self.assertIn('1/2 max HP at 1/4', item['effect'])
        self.assertIn('description', item['source_warning'])


    def test_usage_snapshot_enforces_hash_format_and_explicit_tier_mapping(self):
        import held_items as hi
        self.assertTrue(callable(getattr(hi, 'usage_snapshot', None)), 'missing usage provenance admission')
        import tempfile
        import hashlib
        import json
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            body = {'info': {'metagame': 'gen7ou', 'cutoff': 1695, 'number of battles': 10}, 'data': {}}
            raw = json.dumps(body).encode()
            spec = {'filename': 'ou.json', 'sha256': hashlib.sha256(raw).hexdigest(), 'url': 'https://www.smogon.com/stats/2019-11/chaos/gen7ou-1695.json', 'format': 'gen7ou', 'cutoff': 1695}
            (root / 'ou.json').write_bytes(raw)
            data, meta = hi.usage_snapshot(root, 'UUBL', specs={'OU': spec})
            self.assertEqual(data, {})
            self.assertEqual(meta['format'], 'gen7ou')
            self.assertEqual(meta['requested_tier'], 'UUBL')
            self.assertTrue(meta['tier_mapping'])
            with self.assertRaisesRegex(ValueError, 'tier'):
                hi.usage_snapshot(root, 'unknown', specs={'OU': spec})
            (root / 'ou.json').write_bytes(raw + b' ')
            with self.assertRaisesRegex(ValueError, 'hash'):
                hi.usage_snapshot(root, 'OU', specs={'OU': spec})
            body['info']['metagame'] = 'gen8ou'
            raw = json.dumps(body).encode()
            spec['sha256'] = hashlib.sha256(raw).hexdigest()
            (root / 'ou.json').write_bytes(raw)
            with self.assertRaisesRegex(ValueError, 'format'):
                hi.usage_snapshot(root, 'OU', specs={'OU': spec})


    def test_story_suitability_rejects_species_and_planned_set_conflicts(self):
        import held_items as hi
        self.assertTrue(callable(getattr(hi, 'item_suitability', None)), 'missing story suitability')
        def suitable(item, name='Raichu', types=('Electric',), categories=('Special', 'Status'), nfe=False, kind='held'):
            return hi.item_suitability({'id': item, 'kind': kind}, {'final': name, 'types': list(types)}, list(categories), can_evolve=nfe)[0]
        self.assertFalse(suitable('lightball'))
        self.assertTrue(suitable('lightball', name='Pikachu', nfe=True))
        self.assertFalse(suitable('thickclub'))
        self.assertTrue(suitable('thickclub', name='Marowak'))
        self.assertFalse(suitable('blacksludge'))
        self.assertTrue(suitable('blacksludge', name='Gengar', types=('Ghost', 'Poison')))
        self.assertFalse(suitable('eviolite'))
        self.assertTrue(suitable('eviolite', nfe=True))
        self.assertFalse(suitable('assaultvest'))
        self.assertFalse(suitable('choicespecs'))
        self.assertTrue(suitable('assaultvest', categories=('Special', 'Physical')))
        self.assertFalse(suitable('normaliumz', kind='z-crystal'))
        self.assertFalse(suitable('charizarditex', kind='mega'))
        self.assertFalse(suitable('thunderstone', kind='bag-use'))
        self.assertFalse(suitable('flameorb'))
        self.assertFalse(suitable('electricseed'))


    def test_story_advice_separates_reachable_sidequest_from_later_bp_and_species_item(self):
        import held_items as hi
        self.assertTrue(callable(getattr(hi, 'story_advice', None)), 'missing story advice')
        gengar = {'final': 'Gengar', 'types': ['Ghost', 'Poison']}
        a = hi.story_advice(gengar, ['Special', 'Special', 'Special', 'Status'])
        self.assertEqual(a['current']['id'], 'wiseglasses')
        self.assertTrue(a['current']['access']['reachable'])
        self.assertIn('night', a['current']['access']['gate'])
        self.assertIsNone(a['current']['owned'])
        self.assertEqual(a['later']['id'], 'blacksludge')
        self.assertFalse(a['later']['access']['reachable'])
        self.assertIn('undocumented', a['later']['access']['cost'])
        b = hi.story_advice({'final': 'Marowak', 'types': ['Ground']}, ['Physical'] * 4)
        self.assertEqual(b['later']['id'], 'thickclub')
        self.assertIn('Hokulani', b['later']['access']['location'])
        c = hi.story_advice({'final': 'Butterfree', 'types': ['Bug', 'Flying'], 'utility': True}, ['Status'] * 4)
        self.assertEqual(c['current']['id'], 'sitrusberry')
        self.assertEqual(c['later']['id'], 'leftovers')
        self.assertFalse(hi.access_info('widelens')['reachable'])
        self.assertEqual(hi.access_info('widelens')['status'], 'unverified-hack-access')
        self.assertTrue(hi.access_info('poweranklet')['reachable'])
        self.assertIn('Hau', hi.access_info('poweranklet')['location'])


    def test_structured_report_keeps_all_five_teams_and_separate_competitive_evidence(self):
        import held_items as hi
        self.assertTrue(callable(getattr(hi, 'build_report', None)), 'missing structured held-item report')
        members = [{'owned': name, 'owned_dex': dex, 'final': name, 'dex': dex, 'types': types,
                    'tier': 'PU', 'evolution': 'Synthetic fixture', 'moves': [{'name': x} for x in ['Beam', 'Strike', 'Focus', 'Guard']]}
                   for name, dex, types in [('Pikachu', 25, ['Electric']), ('Rattata', 19, ['Normal']),
                   ('Oddish', 43, ['Grass', 'Poison']), ('Abra', 63, ['Psychic']), ('Spearow', 21, ['Normal', 'Flying'])]]
        team = {'warnings': ['Synthetic retained assumption'], 'utility': 'Butterfree', 'utility_dex': 12, 'utility_moves': [{'name': x} for x in ['Beam', 'Strike', 'Focus', 'Guard']],
                'options': [{'category': c, 'members': members} for c in ['OG', 'Non-OG', 'Mixed', 'Pokedex', 'Best']]}
        # Synthetic parser fixtures, not claims that these species learn these moves.
        dex = ''.join('\n\t%s: {types: %s, abilities: {0: "Fixture Ability"}}' % (m['final'].lower(), __import__('json').dumps(m['types'])) for m in members)
        dex += '\n\tbutterfree: {types: ["Bug", "Flying"], abilities: {0: "Compound Eyes"}}'
        moves = '\n\tbeam: {category: "Special"},\n\tstrike: {category: "Physical"},\n\tfocus: {category: "Status"},\n\tguard: {category: "Status"}'
        items = {k: {'id': k, 'name': k, 'kind': 'held', 'effect': 'Fixture effect', 'gen': 4} for k in ['wiseglasses', 'sitrusberry', 'leftovers', 'blacksludge', 'muscleband', 'thickclub', 'choicescarf']}
        def usage(name, tier):
            return {'Raw count': 20, 'Items': {'choicescarf': 3, 'leftovers': 1}}, {'format': 'gen7pu', 'cutoff': 1630, 'requested_tier': tier, 'format_battles': 100}
        report = hi.build_report(team, items=items, dex_text=dex, moves_text=moves, lookup_usage=usage, utility_tier='PU')
        self.assertEqual([x['category'] for x in report['teams']], ['OG', 'Non-OG', 'Mixed', 'Pokedex', 'Best'])
        self.assertEqual(sum(len(x['members']) for x in report['teams']), 30)
        self.assertEqual(report['selection_warnings'], ['Synthetic retained assumption'])
        self.assertEqual(sum(r['story']['current']['id'] == 'wiseglasses' for r in report['teams'][0]['members']), 1)
        row = report['teams'][0]['members'][1]
        self.assertEqual(row['competitive']['items'][0]['id'], 'choicescarf')
        self.assertFalse(row['competitive']['items'][0]['story_fit'])
        self.assertNotEqual(row['story']['current']['id'], 'choicescarf')
        with self.assertRaisesRegex(ValueError, 'five'):
            hi.build_report({**team, 'options': team['options'][:1]}, items=items, dex_text=dex, moves_text=moves, lookup_usage=usage, utility_tier='PU')


    def test_renderer_writes_overview_all_five_cards_and_cited_report_without_clipping(self):
        self.assertIsNotNone(importlib.util.find_spec('held_item_cards'), 'missing held-item renderer')
        import held_item_cards as cards
        import tempfile
        from PIL import Image
        names = [('Butterfree', 12), ('Pikachu', 25), ('Chikorita', 152), ('Torchic', 255), ('Snivy', 495), ('Froakie', 656)]
        rows = []
        for name, dex in names:
            item = {'id': 'sitrusberry', 'name': 'Sitrus Berry', 'effect': 'Restores 1/4 max HP when at 1/2 max HP or less. Single use.'}
            option = {'id': 'sitrusberry', 'item': item, 'reason': 'Fixture reason', 'access': {'location': 'Route 2', 'gate': 'Daily pile', 'cost': 'Free collection', 'sources': [6]}}
            rows.append({'owned': name, 'owned_dex': dex, 'final': name, 'dex': dex, 'types': ['Normal'], 'tier': 'PU',
                         'evolution': 'Synthetic layout fixture: a deliberately long evolution and acquisition condition that must wrap without dropping words.',
                         'story': {'role': 'fixture planned role', 'current': option, 'later': option},
                         'competitive': {'status': 'missing', 'items': [], 'denominator': 0, 'raw_count': None, 'provenance': {'format': 'gen7pu', 'cutoff': 1630, 'format_battles': 100, 'requested_tier': 'PU'}},
                         'abilities_possible': 'Unconfirmed fixture', 'notes': ['Fixture note.'], 'moves': []})
        report = {'horizon': 'Synthetic fixture, not a recommendation.', 'ranking': 'Editorial heuristic.',
                  'generated': 'Fixture timestamp', 'teams': [{'category': c, 'members': rows} for c in ['OG', 'Non-OG', 'Mixed', 'Pokedex', 'Best']], 'guide': []}
        with tempfile.TemporaryDirectory() as td:
            result = cards.render_bundle(report, Path(td))
            self.assertEqual(len(result['images']), 6)
            self.assertEqual(len(result['row_layouts']), 30)
            self.assertTrue(all(x['bottom'] < x['panel_bottom'] for x in result['row_layouts']))
            for name in result['images']:
                with Image.open(Path(td) / name) as image:
                    image.verify()
            text = (Path(td) / 'held-items.md').read_text()
            self.assertEqual(text.count('## Team: '), 5)
            self.assertIn('## Sources', text)
            self.assertIn('[6]', text)


    def test_source_validation_checks_full_caught_seen_and_favorites_not_totals(self):
        import held_item_cards as cards
        self.assertTrue(callable(getattr(cards, 'validate_sources', None)), 'missing source-set validation')
        expected = {'caught': [12, 25], 'seen': [26], 'starred': [12]}
        team = {'source_caught_ids': [12, 25], 'source_seen_ids': [26]}
        records = {'species:12': {'s': 'caught'}, 'species:25': {'s': 'caught'}, 'species:26': {'s': 'seen'}, 'star:12': {'s': 'on'}}
        self.assertEqual(cards.validate_sources(team, expected, records), expected)
        cases = [
            {'species:12': {'s': 'caught'}, 'species:26': {'s': 'caught'}, 'species:25': {'s': 'seen'}, 'star:12': {'s': 'on'}},
            {**records, 'species:26': {'s': 'none'}},
            {**records, 'star:12': {'s': 'off'}, 'star:25': {'s': 'on'}},
        ]
        for changed in cases:
            with self.subTest(changed=changed), self.assertRaisesRegex(ValueError, 'changed|snapshot'):
                cards.validate_sources(team, expected, changed)


    @unittest.skipUnless(__import__('os').environ.get('SHOWDOWN_DATA_CACHE') and (Path(__import__('os').environ.get('SHOWDOWN_DATA_CACHE', '')) / 'held-items-gen7/showdown-manifest.json').is_file(), 'verified item add-on cache unavailable')
    def test_real_context_admits_root_overrides_and_tier_local_pu_ubers(self):
        import held_item_cards as cards
        self.assertTrue(callable(getattr(cards, 'load_context', None)), 'missing real item context')
        context = cards.load_context(Path(__import__('os').environ['SHOWDOWN_DATA_CACHE']))
        self.assertNotIn('heavydutyboots', context['items'])
        self.assertIn('1/2 max HP at 1/4', context['items']['magoberry']['effect'])
        _, pu = context['lookup_usage']('Butterfree', 'PU')
        _, uber = context['lookup_usage']('Aegislash', 'Uber')
        self.assertEqual(pu['format'], 'gen7pu')
        self.assertEqual(uber['format'], 'gen7ubers')


    def test_eviolite_checks_gen7_evolutions_not_newer_generation_children(self):
        import held_items as hi
        self.assertTrue(callable(getattr(hi, 'gen7_can_evolve', None)), 'missing generation-safe evolution check')
        dex = '\n\tpikachu: {evos: ["Raichu"]},\n\traichu: {num: 26},\n\tfarfetchd: {evos: ["Sirfetchd"]},\n\tsirfetchd: {num: 865}'
        self.assertTrue(hi.gen7_can_evolve(dex, 'Pikachu'))
        self.assertFalse(hi.gen7_can_evolve(dex, 'Raichu'))
        self.assertFalse(hi.gen7_can_evolve(dex, 'Farfetchd'))


    def test_editorial_guide_labels_roles_and_unevolved_users_not_universal_strength(self):
        import held_items as hi
        self.assertTrue(callable(getattr(hi, 'make_guide', None)), 'missing role-aware guide')
        row = {'final': 'Raichu', 'owned': 'Pikachu', 'types': ['Electric'], 'categories': ['Special', 'Status'], 'planned_can_evolve': False, 'owned_can_evolve': True}
        items = {key: {'id': key, 'name': key, 'effect': 'Fixture effect', 'kind': 'held'} for key in ['eviolite', 'lightball', 'wiseglasses']}
        guide = {x['id']: x for x in hi.make_guide({'teams': [{'members': [row]}]}, items)}
        self.assertIn('Pikachu (while unevolved)', guide['eviolite']['users'])
        self.assertEqual(guide['lightball']['users'], [])
        self.assertEqual(guide['wiseglasses']['rank'], 'B')
        self.assertTrue(all(x['reason'] and x['tradeoff'] and x['access'] for x in guide.values()))


    def test_cli_renderer_failure_retains_report_trace_and_nonzero_failed_receipt(self):
        import held_item_cards as cards
        self.assertTrue(callable(getattr(cards, 'main', None)), 'missing held-item CLI')
        import tempfile
        import json
        import io
        from unittest import mock
        from contextlib import redirect_stdout
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); output = root / 'out'
            team = {'source_caught_ids': [12], 'source_seen_ids': []}
            (root / 'team.json').write_text(json.dumps(team))
            (root / 'source.json').write_text(json.dumps({'caught': [12], 'seen': [], 'starred': []}))
            context = {'items': {}, 'dex_text': '', 'moves_text': '', 'lookup_usage': None, 'utility_tier': 'PU'}
            with mock.patch('team_builder.read_records', return_value={'species:12': {'s': 'caught'}}), mock.patch.object(cards, 'load_context', return_value=context), mock.patch('held_items.build_report', return_value={'teams': []}), mock.patch.object(cards, 'render_bundle', side_effect=ValueError('deliberate layout failure')), redirect_stdout(io.StringIO()):
                code = cards.main(['generate', '--team-report', str(root / 'team.json'), '--source-observations', str(root / 'source.json'), '--uid', 'fixture-user', '--cache', str(root / 'cache'), '--output-dir', str(output)])
            self.assertNotEqual(code, 0)
            self.assertEqual(json.loads((output / 'run-status.json').read_text())['status'], 'failed')
            self.assertIn('deliberate layout failure', (output / 'traceback.log').read_text())
            self.assertTrue((output / 'held-items.json').is_file())


    def test_actual_item_kind_distinguishes_bag_use_from_mega_and_z(self):
        import held_items as hi
        source = '\n\tthunderstone: {name: "Thunder Stone", gen: 1, desc: "Evolves a species when used."},\n\tpokeball: {name: "Poke Ball", gen: 1, isPokeball: true},\n\tcharizarditex: {name: "Charizardite X", gen: 6, megaStone: "Charizard-Mega-X"},\n\tnormaliumz: {name: "Normalium Z", gen: 7, zMove: true}'
        items = hi.parse_items(source, '')
        self.assertEqual(items['thunderstone']['kind'], 'bag-use')
        self.assertEqual(items['pokeball']['kind'], 'bag-use')
        self.assertEqual(items['charizarditex']['kind'], 'mega')
        self.assertEqual(items['normaliumz']['kind'], 'z-crystal')


if __name__ == '__main__':
    unittest.main()
