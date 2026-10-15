#!/usr/bin/env python3
"""Generation VII held-item evidence and editorial story-role recommendations.

Personal reports belong outside the repository. No game/account writes.
"""
from __future__ import annotations

import ast
import re

from showdown_text import integer_field, normalize_name, top_blocks
from showdown_data import DatasetSpec, SHOWDOWN_COMMIT, ShowdownDataStore

_ITEM_URL = f'https://raw.githubusercontent.com/smogon/pokemon-showdown/{SHOWDOWN_COMMIT}/data/'
ITEM_DATASETS = {
    name: DatasetSpec(name, filename, _ITEM_URL + source, digest)
    for name, filename, source, digest in [
        ('items', 'items.js', 'items.js', 'ddb2271d987eb420817d0290593dd4db85f364c44e60aee8e72fe89cf49295f5'),
        ('items-gen7', 'gen7-items.js', 'mods/gen7/items.js', '5f664c9a99eafb07603913f889d215569c6f37056037700da2ce2c93cce6df10'),
        ('abilities', 'abilities.js', 'abilities.js', 'ffa2af8ba0826608b40e6807fe3e3f5b8f2c1f2221bd2691db597ee7685c7b6e'),
        ('abilities-gen7', 'gen7-abilities.js', 'mods/gen7/abilities.js', 'a8b14fa79b322803f2c56088700f7ace7c607f9ef1c89bf64f6b3a4d4396a0d1'),
    ]
}


def source_store(cache, *, datasets=None, downloader=None):
    """A separate add-on contract; never mutate the five-source selector store."""
    from pathlib import Path
    return ShowdownDataStore(Path(cache) / 'held-items-gen7',
                             datasets=ITEM_DATASETS if datasets is None else datasets,
                             downloader=downloader)




USAGE_SOURCES = {'OU': {'filename': 'chaos-gen7ou-1695.json', 'url': 'https://www.smogon.com/stats/2019-11/chaos/gen7ou-1695.json', 'sha256': '67c166dc6a6c24daffd34f898e868f54b9b5fd0f92d9333f0e4e3983a2c04c75', 'format': 'gen7ou', 'cutoff': 1695.0, 'date': '2019-11'}, 'UU': {'filename': 'chaos-gen7uu-1630.json', 'url': 'https://www.smogon.com/stats/2019-11/chaos/gen7uu-1630.json', 'sha256': '39c80d0fbaa1b0b771b89c22177655453fb4d6d626a49b6966714d2c6e1a1260', 'format': 'gen7uu', 'cutoff': 1630.0, 'date': '2019-11'}, 'RU': {'filename': 'chaos-gen7ru-1630.json', 'url': 'https://www.smogon.com/stats/2019-11/chaos/gen7ru-1630.json', 'sha256': '789e0010a86ff71eda514fb89a2819ea3b301f0546e1b3753e50d4953aed088a', 'format': 'gen7ru', 'cutoff': 1630.0, 'date': '2019-11'}, 'NU': {'filename': 'chaos-gen7nu-1630.json', 'url': 'https://www.smogon.com/stats/2019-11/chaos/gen7nu-1630.json', 'sha256': '8de54fb4a9cd434a399047f1e07b3a7f2c23983a33a029e922c976a720f5e194', 'format': 'gen7nu', 'cutoff': 1630.0, 'date': '2019-11'}, 'PU': {'filename': 'chaos-gen7pu-1630.json', 'url': 'https://www.smogon.com/stats/2019-11/chaos/gen7pu-1630.json', 'sha256': '651cf69b9670b9dd1b05e8086c48ff2d67f93632750338212d64c1f520e18254', 'format': 'gen7pu', 'cutoff': 1630.0, 'date': '2019-11'}, 'Uber': {'filename': 'chaos-gen7ubers-1630.json', 'url': 'https://www.smogon.com/stats/2019-11/chaos/gen7ubers-1630.json', 'sha256': 'd017b80318c2c555c5b91816788c95556a7e61815cd97d07b0b4af850167e3df', 'format': 'gen7ubers', 'cutoff': 1630.0, 'date': '2019-11'}}
TIER_TO_FORMAT = {'Uber': 'Uber', 'OU': 'OU', 'UUBL': 'OU', 'UU': 'UU', 'RUBL': 'UU',
                  'RU': 'RU', 'NUBL': 'RU', 'NU': 'NU', 'PUBL': 'NU', 'PU': 'PU', '(PU)': 'PU'}


def usage_snapshot(directory, tier: str, *, specs=None) -> tuple[dict, dict]:
    """Admit one exact historical format; absence never triggers another format."""
    import hashlib
    import json
    from pathlib import Path
    if tier not in TIER_TO_FORMAT:
        raise ValueError(f'unsupported competitive tier: {tier}')
    mapped = TIER_TO_FORMAT[tier]
    spec = (USAGE_SOURCES if specs is None else specs)[mapped]
    raw = (Path(directory) / spec['filename']).read_bytes()
    if hashlib.sha256(raw).hexdigest() != spec['sha256']:
        raise ValueError(f'usage hash mismatch: {spec["filename"]}')
    blob = json.loads(raw)
    info = blob.get('info', {})
    if info.get('metagame') != spec['format'] or info.get('cutoff') != spec['cutoff']:
        raise ValueError('usage format/cutoff mismatch')
    if not isinstance(blob.get('data'), dict):
        raise ValueError('usage data must be an object')
    return blob['data'], {**spec, 'requested_tier': tier, 'tier_mapping': mapped != tier,
                          'format_battles': info.get('number of battles')}


def bootstrap_sources(cache) -> None:
    """Explicit network admission into the isolated add-on, never the selector cache."""
    import hashlib
    import urllib.request
    store = source_store(cache)
    store.bootstrap()
    for spec in USAGE_SOURCES.values():
        path = store.cache_dir / spec['filename']
        if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() == spec['sha256']:
            continue
        with urllib.request.urlopen(spec['url'], timeout=90) as response:
            raw = response.read()
        if hashlib.sha256(raw).hexdigest() != spec['sha256']:
            raise ValueError(f'downloaded usage hash mismatch: {spec["filename"]}')
        path.write_bytes(raw)
    for tier in USAGE_SOURCES:
        usage_snapshot(store.cache_dir, tier)





def item_suitability(item: dict, member: dict, categories: list[str], *, can_evolve=False) -> tuple[bool, str]:
    """Strict flexible-story fit, not battle legality or a damage ranking."""
    key, species = item['id'], normalize_name(member['final'])
    if item.get('kind') in {'mega', 'z-crystal', 'bag-use', 'none'}:
        return False, 'Separate mechanic, not a generic held-item recommendation.'
    if key == 'lightball' and species != 'pikachu':
        return False, 'Pikachu only; evolving to Raichu removes its benefit.'
    if key == 'thickclub' and species not in {'cubone', 'marowak', 'marowakalola'}:
        return False, 'Cubone/Marowak only.'
    if key == 'blacksludge' and 'Poison' not in member['types']:
        return False, 'Damages a non-Poison holder.'
    if key == 'eviolite' and not can_evolve:
        return False, 'Needs a species that can still evolve in Gen VII.'
    if key == 'assaultvest' and 'Status' in categories:
        return False, 'Disables the planned status moves; redesign the set first.'
    if key.startswith('choice') and 'Status' in categories:
        return False, 'Move locking conflicts with this flexible status-containing plan.'
    if key == 'choiceband' and 'Physical' not in categories:
        return False, 'No planned physical attack.'
    if key in {'choicespecs', 'wiseglasses'} and 'Special' not in categories:
        return False, 'No planned special attack.'
    if key == 'muscleband' and 'Physical' not in categories:
        return False, 'No planned physical attack.'
    if key in {'flameorb', 'toxicorb'}:
        return False, 'Needs a confirmed compatible individual ability and a deliberate status plan.'
    if key in {'electricseed', 'psychicseed', 'grassyseed', 'mistyseed', 'damprock'}:
        return False, 'Needs confirmed matching terrain/weather and ability/move setup.'
    return True, 'Role-compatible only; inventory and individual moves/ability remain unverified.'




DOME_ITEMS = set('eviolite choicespecs choiceband choicescarf assaultvest rockyhelmet flameorb toxicorb redcard ejectbutton flyinggem normalgem whiteherb powerherb focussash brightpowder blacksludge soothebell scopelens leftovers lifeorb muscleband wiseglasses expertbelt zoomlens metronome destinyknot icyrock smoothrock heatrock damprock floatstone bindingband'.split())


def access_info(key: str) -> dict:
    """Last-confirmed first-island horizon, not an inventory or progression claim."""
    if key in {'sitrusberry', 'oranberry'}:
        return {'location': 'Route 2 berry tree north of Pokemon Center', 'gate': 'Daily pile; Sitrus needs a large pile; possible guarded encounter.',
                'cost': 'Free collection; daily RNG/possible battle; consumed on activation.', 'reachable': True,
                'status': 'stock-USUM-fallback', 'sources': [6]}
    if key == 'wiseglasses':
        return {'location': "Melemele Trainers' School", 'gate': 'After Hala: Big Wave Beach rumor, then solve school mysteries at night.',
                'cost': 'Free one-off quest reward; quest completion and inventory unconfirmed.', 'reachable': True,
                'status': 'stock-USUM-fallback', 'sources': [5]}
    if key in {'powerbracer', 'powerbelt', 'powerlens', 'powerband', 'poweranklet', 'powerweight'}:
        return {'location': 'Hau’oli City specialist mart, Melemele', 'gate': 'Early Hau’oli access; training gear, not a default battle buff.',
                'cost': 'Money; exact hack price undocumented.', 'reachable': True,
                'status': 'creator-vendor', 'sources': [9]}
    if key == 'weaknesspolicy':
        return {'location': 'Standard left-clerk marts', 'gate': 'Complete seven trials; activation also requires surviving a super-effective hit.',
                'cost': 'Money; exact hack price undocumented.', 'reachable': False,
                'status': 'creator-vendor', 'sources': [9]}
    if key in {'thickclub', 'lightball'}:
        return {'location': 'Mt. Hokulani specialist mart, Ula’ula', 'gate': 'Later Ula’ula / Mt. Hokulani access.',
                'cost': 'Money; exact hack price undocumented.', 'reachable': False,
                'status': 'creator-vendor', 'sources': [9]}
    if key in DOME_ITEMS:
        return {'location': 'Battle Royal Dome, Royal Avenue, Akala', 'gate': 'Later Akala / Royal Avenue access; earn BP.',
                'cost': 'BP; exact reduced hack price undocumented (not vanilla 48 BP).', 'reachable': False,
                'status': 'creator-vendor', 'sources': [9, 8]}
    return {'location': 'No confirmed Standard acquisition route in the retained evidence',
            'gate': 'Do not infer access from ladder popularity. Wide Lens Route 1 gift is SM-only, not USUM.',
            'cost': 'Unknown; do not prescribe farming or claim ownership.', 'reachable': False,
            'status': 'unverified-hack-access', 'sources': [7] if key == 'widelens' else []}


def story_advice(member: dict, categories: list[str]) -> dict:
    """Editorial flexible-story fit with access as a separate dimension."""
    physical, special, status = (categories.count(x) for x in ['Physical', 'Special', 'Status'])
    utility = member.get('utility', False)
    current = 'wiseglasses' if special and not utility else 'sitrusberry'
    species = normalize_name(member['final'])
    if species in {'cubone', 'marowak', 'marowakalola'}:
        later, why = 'thickclub', 'Doubles Attack for this species, without move locking or recoil.'
    elif utility or status >= 2:
        later, why = 'leftovers', 'Reusable sustain for longer utility/setup turns; no damage to a catching target.'
    elif 'Poison' in member['types']:
        later, why = 'blacksludge', 'Poison-type-only recurring healing; never hand it to a non-Poison teammate.'
    elif physical > special:
        later, why = 'muscleband', 'Modest physical power without move locking, recoil or a hidden-ability requirement.'
    elif special:
        later, why = 'wiseglasses', 'Special power without move locking or recoil; keep the earlier quest copy if obtained.'
    else:
        later, why = 'leftovers', 'Reusable sustain while preserving move flexibility.'
    def option(key, reason):
        access = access_info(key)
        # Wise Glasses later shop alternative differs from its earlier one-off gift.
        if key == 'wiseglasses' and reason == why:
            access = {'location': 'Battle Royal Dome, Akala (or keep earlier school gift)',
                      'gate': 'Extra copies need later Akala access and BP.', 'cost': 'BP shop price undocumented; earlier quest copy is free.',
                      'reachable': False, 'status': 'creator-vendor', 'sources': [9, 5]}
        return {'id': key, 'reason': reason, 'access': access, 'owned': None}
    return {'role': 'catching utility' if utility else f'planned {physical} physical / {special} special / {status} status moves',
            'current': option(current, 'For special attacks IF actually learned; no assumption of kit readiness.' if current == 'wiseglasses'
                              else 'One-use healing IF collected; keep replacements. No hidden ability or learned move required.'),
            'later': option(later, why)}




def gen7_can_evolve(dex_text: str, name: str) -> bool:
    from showdown_text import block, array_field
    return any(1 <= (integer_field(block(dex_text, child), 'num') or 0) <= 807
               for child in array_field(block(dex_text, name), 'evos'))


CATEGORY_ORDER = ['OG', 'Non-OG', 'Mixed', 'Pokedex', 'Best']


def build_report(team: dict, *, items: dict, dex_text: str, moves_text: str, lookup_usage, utility_tier: str) -> dict:
    """One structured source for every team picture and the full private report."""
    import json
    from pathlib import Path
    from showdown_text import block, array_field
    import team_builder as tb
    if [o['category'] for o in team['options']] != CATEGORY_ORDER:
        raise ValueError('need all five objective teams in canonical order')
    if team['utility'] != 'Butterfree' or team['utility_dex'] != 12:
        raise ValueError('expected the fixed Butterfree utility slot')
    canonical = {p['id']: p['name'] for p in json.loads((Path(__file__).resolve().parents[1] / 'data/pokemon.json').read_text())}
    def row(member):
        for label, identifier in [('final', 'dex'), ('owned', 'owned_dex')]:
            if normalize_name(canonical.get(member[identifier], '')) != normalize_name(member[label]):
                raise ValueError(f'canonical species ID/name mismatch: {label}')
        body = block(dex_text, member['final'])
        if not body or array_field(body, 'types') != member['types']:
            raise ValueError(f'Gen VII type/species mismatch: {member["final"]}')
        if len(member.get('moves', [])) != 4:
            raise ValueError('need four already acquisition-checked planned moves per member')
        categories = []
        for move in member['moves']:
            key = normalize_name(move['name'])
            category = scalar(block(moves_text, 'hiddenpower' if key.startswith('hiddenpower') else key), 'category')
            if category not in {'Physical', 'Special', 'Status'}:
                raise ValueError(f'unknown verified move category: {move["name"]}')
            categories.append(category)
        advice = story_advice(member, categories)
        for option in [advice['current'], advice['later']]:
            item = resolve_item(option['id'], items)
            ok, reason = item_suitability(item, member, categories, can_evolve=gen7_can_evolve(dex_text, member['final']))
            if not ok:
                raise ValueError(f'incompatible story recommendation: {reason}')
            option['item'] = item
        species, meta = lookup_usage(member['final'], member['tier'])
        comp = {**item_usage(species, items), 'provenance': meta}
        for item in comp['items']:
            item['story_fit'], item['fit_reason'] = item_suitability(item, member, categories, can_evolve=gen7_can_evolve(dex_text, member['final']))
        notes = ['Planned moves/evolution, not proof of the current individual’s kit.']
        key = normalize_name(member['final'])
        if member.get('utility'):
            notes += ['Compound Eyes is an ordinary ability option, not a confirmed individual ability. Wide Lens multiplies accuracy; Zoom Lens needs moving after the target. Do not use Rocky Helmet/contact damage when catching.']
        if key == 'hawlucha':
            notes += ['Ladder seeds need matching terrain AND a confirmed Unburden plan; this party is not proof of either.']
        if key == 'pelipper':
            notes += ['Damp Rock only helps a confirmed rain plan, e.g. ordinary-slot Drizzle; do not assume the individual has it.']
        if key == 'raichu':
            notes += ['Light Ball does not work on Raichu; it is Pikachu-only.']
        if key == 'malamar':
            notes += ['Superpower synergy requires confirmed Contrary (ordinary slot); do not assume it over Suction Cups.']
        if member.get('hidden_ability_caveat'):
            notes += ['Historical set dependence includes a hidden-ability caveat from the selector; no hidden ability is assumed here.']
        return {**member, 'categories': categories, 'planned_can_evolve': gen7_can_evolve(dex_text, member['final']),
                'owned_can_evolve': gen7_can_evolve(dex_text, member['owned']), 'abilities_possible': tb.abilities_of(dex_text, member['final']),
                'story': advice, 'competitive': comp, 'notes': notes}
    utility = {'owned': 'Butterfree', 'owned_dex': 12, 'final': 'Butterfree', 'dex': 12, 'types': ['Bug', 'Flying'],
               'tier': utility_tier, 'evolution': 'Fixed catching utility', 'utility': True, 'moves': team['utility_moves']}
    teams = []
    for option in team['options']:
        if len(option['members']) != 5 or len({m['dex'] for m in option['members']}) != 5:
            raise ValueError('each objective requires five distinct battlers')
        members = [row(utility)] + [row(m) for m in option['members']]
        eligible = [r for r in members if r['story']['current']['id'] == 'wiseglasses']
        allocation = None
        if eligible:
            from showdown_text import object_after
            # Editorial allocation of the ONE documented free copy; stable source-order tie.
            winner = max(eligible, key=lambda r: integer_field(object_after(block(dex_text, r['final']), 'baseStats') or '', 'spa') or 0)
            allocation = winner['final']
            for r in eligible:
                if r is winner:
                    continue
                r['story']['current'] = story_advice({**r, 'utility': True}, r['categories'])['current']
                r['story']['current']['item'] = resolve_item('sitrusberry', items)
                r['story']['current']['reason'] += ' The one documented free school copy is allocated to ' + allocation + '; extra glasses need later BP access.[5][9]'
        teams.append({'category': option['category'], 'members': members, 'one_free_glasses_allocation': allocation})
    return {'schema': 'pokemon-checklist.held-items.v1', 'horizon': 'Last confirmed first island complete / about L30 / Tauros / TM54; no inferred advance.',
            'ranking': 'Editorial story-role tiers, not measured effectiveness. Historical competitive shares are a separate lens.',
            'selection_warnings': team.get('warnings', []), 'selection_objective_rules': team.get('objective_rules', {}),
            'selection_search_scope': team.get('search_scope', {}), 'teams': teams}




GUIDE_RULES = [
    ('leftovers', 'A', 'Sustain / utility / setup', 'Reusable healing with no move lock.', 'Small per-turn recovery; short fights give less value.'),
    ('blacksludge', 'A', 'Poison-type sustain', 'Reusable healing for a Poison holder.', 'Hurts non-Poison holders; not a general team hand-me-down.'),
    ('thickclub', 'A', 'Cubone / Marowak physical damage', 'Large species-specific Attack benefit.', 'Does nothing for other species; later specialist shop.'),
    ('widelens', 'A', 'Accuracy / catching utility', 'Helps inaccurate moves without requiring a move-last condition.', 'Standard acquisition unverified; not the SM-only Route 1 gift.'),
    ('muscleband', 'B', 'Physical flexible attacks', 'Small passive benefit without recoil or locking.', 'Only physical attacks; weaker raw bonus than a specialized item.'),
    ('wiseglasses', 'B', 'Special flexible attacks', 'Small passive benefit; one early quest copy.', 'Only special attacks; extra copies need later BP access.'),
    ('expertbelt', 'B', 'Coverage attackers', 'No-recoil benefit when hitting super effectively.', 'No benefit on neutral/resisted hits; no assumed perfect coverage.'),
    ('rockyhelmet', 'B', 'Contact punishment in battles', 'Punishes opposing contact without selecting an attack.', 'NEVER a catching default: uncontrolled target HP loss.'),
    ('sitrusberry', 'B', 'One-use sustain', 'Move-independent healing; reachable berry collection opportunity.', 'Consumed; daily RNG / guarded pile and replacement cost.'),
    ('oranberry', 'B', 'Early one-use sustain', 'Small fixed healing with no move/ability requirement.', 'Only 10 HP; less useful as maximum HP grows; consumed.'),
    ('lumberry', 'B', 'One-use status protection', 'Protects a setup/status-sensitive turn.', 'Consumed; no verified access route supplied here.'),
    ('choiceband', 'C', 'Dedicated physical attacker', 'Large Attack modifier for a committed attacking plan.', 'Locks moves; conflicts with flexible setup/status targets.'),
    ('choicespecs', 'C', 'Dedicated special attacker', 'Large Sp. Atk modifier for a committed attacking plan.', 'Locks moves; conflicts with flexible setup/status targets.'),
    ('choicescarf', 'C', 'Dedicated speed control', 'Speed boost for a specialized attacking plan.', 'Move lock; not a universal damage or story-utility upgrade.'),
    ('lifeorb', 'C', 'Damage-focused mixed/offensive sets', 'Broad attack damage benefit.', 'HP cost across story encounters; ability exceptions are not assumed.'),
    ('assaultvest', 'C', 'All-attacks special bulk', 'Raises special bulk without using a setup turn.', 'Cannot select status moves; change the set first if needed.'),
    ('focussash', 'C', 'Full-HP emergency / setup', 'Can preserve a setup turn from full HP.', 'Single use and full-HP condition; not endless insurance.'),
    ('flameorb', 'C', 'Confirmed ability/status strategy', 'Deliberate activation only in a compatible build.', 'Self-status is harmful otherwise; no individual ability is known.'),
    ('toxicorb', 'C', 'Confirmed ability/status strategy', 'Deliberate activation only in a compatible build.', 'Self-status is harmful otherwise; no individual ability is known.'),
    ('damprock', 'C', 'Confirmed rain strategy', 'Extends the relevant weather plan.', 'Needs actual rain generation, not merely a Water type.'),
    ('electricseed', 'C', 'Terrain / Unburden strategy', 'Potential activation plan, not a plug-in speed boost.', 'Needs matching terrain and confirmed ability; no assumed terrain setter.'),
    ('eviolite', 'X', 'Still-evolving stage only', 'Defensive equipment while a Gen VII evolution remains.', 'No effect after final evolution; not a final-team battle default.'),
    ('lightball', 'X', 'Pikachu only', 'Large species-specific offensive benefit.', 'Does NOT benefit Raichu; evolution changes the equipment decision.'),
    ('poweranklet', 'X', 'Training, not general battle gear', 'A separate training/economy objective.', 'Halves Speed; do not present it as combat speed control.'),
]


def make_guide(report, items):
    rows = [m for t in report['teams'] for m in t['members']]
    result = []
    for key, rank, role, reason, tradeoff in GUIDE_RULES:
        if key not in items:
            continue
        item = items[key]
        users = set()
        for row in rows:
            if key == 'eviolite' and row.get('owned_can_evolve'):
                users.add(row['owned'] + ' (while unevolved)')
                continue
            ok, _ = item_suitability(item, row, row['categories'], can_evolve=row.get('planned_can_evolve', False))
            if key == 'rockyhelmet' and row.get('utility'):
                ok = False
            if key == 'widelens' and not row.get('utility'):
                ok = False
            if key == 'poweranklet':
                ok = False
            if ok:
                users.add(row['final'])
        result.append({**item, 'rank': rank, 'role': role, 'reason': reason, 'tradeoff': tradeoff,
                       'users': sorted(users), 'access': access_info(key)})
    return result


def scalar(body: str, key: str) -> str | None:
    """Quoted scalar including apostrophes and escapes; never evaluate JS."""
    match = re.search(r'\b' + re.escape(key) + r'''\s*:\s*("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')''', body)
    return ast.literal_eval(match[1]) if match else None


def parse_items(base: str, overrides: str) -> dict[str, dict]:
    mods = dict(top_blocks(overrides))
    result = {}
    for key, body in top_blocks(base):
        gen = integer_field(body, 'gen')
        if gen is None or not 1 <= gen <= 7:
            continue
        mod = mods.get(key, '')
        name = scalar(body, 'name')
        if not name:
            raise ValueError(f'missing item name: {key}')
        effect = scalar(mod, 'desc') or scalar(body, 'desc') or 'Effect not described by source.'
        warning = ''
        if key == 'magoberry' and mod:
            if 'this.heal(pokemon.maxhp / 2)' not in mod or 'pokemon.maxhp / 4' not in body:
                raise ValueError('unrecognized Gen VII Mago callback')
            effect = 'Restores 1/2 max HP at 1/4 max HP or less; confuses if -Spe Nature. Single use.'
            warning = 'Pinned Gen7 description is stale; callback and inherited threshold supply the effect.'
        kind = ('mega' if scalar(body, 'megaStone') else 'z-crystal' if re.search(r'\bzMove\s*:', body)
                else 'berry' if re.search(r'\bisBerry\s*:\s*true', body)
                else 'bag-use' if effect.startswith('Evolves ') or re.search(r'\bisPokeball\s*:\s*true', body) else 'held')
        result[normalize_name(key)] = {'id': normalize_name(key), 'name': name, 'gen': gen,
                                       'effect': effect, 'kind': kind, 'gen7_override': bool(mod),
                                       'source_warning': warning}
    return result


def resolve_item(value: str, items: dict[str, dict]) -> dict:
    key = normalize_name(value)
    if key == 'nothing':
        return {'id': 'nothing', 'name': 'No held item', 'gen': 0, 'kind': 'none', 'effect': 'No held item.'}
    if key not in items:
        raise ValueError(f'unknown or non-Generation-VII item: {value!r}')
    return items[key]


def item_usage(species: dict | None, items: dict[str, dict]) -> dict:
    """One species' weighted item shares; never mix format denominators."""
    import math
    if species is None:
        return {'status': 'missing', 'denominator': 0, 'raw_count': None, 'items': []}
    weights = species.get('Items', {})
    if not isinstance(weights, dict):
        raise ValueError('Items must be an object')
    rows = []
    for key, weight in weights.items():
        if type(weight) not in (int, float) or not math.isfinite(weight) or weight < 0:
            raise ValueError(f'invalid item weight for {key}')
        item = resolve_item(key, items)
        rows.append({**item, 'weight': weight})
    denominator = math.fsum(row['weight'] for row in rows)
    if not math.isfinite(denominator):
        raise ValueError('nonfinite item denominator')
    rows = [{**row, 'share': row['weight'] / denominator} for row in rows if row['weight'] > 0] if denominator else []
    rows.sort(key=lambda row: (-row['share'], row['id']))
    return {'status': 'ok' if rows else 'empty', 'denominator': denominator,
            'raw_count': species.get('Raw count'), 'items': rows}
