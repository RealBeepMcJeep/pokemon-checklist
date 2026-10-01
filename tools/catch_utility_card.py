#!/usr/bin/env python3
"""Six curated catch-utility prospects in first-encounter order, not a raw tier rank.

Move legality/levels/types are verified against Prismatic Standard and pinned Gen VII.
Snapshots retain ownership privately and can be redrawn without Firebase or a cache.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw

import catcher_score as cs
import story_moves as sm
import story_team_cards as art
import team_builder as tb
from showdown_data import configured_cache_dir, require_cache
from showdown_text import top_blocks

ROOT = Path(__file__).resolve().parents[1]
PLANS = (
    ('Caterpie', 'Butterfree', ('Sleep Powder', 'Bug Buzz', 'Air Slash', 'Roost'),
     'Caterpie → Metapod L7 → Butterfree L10',
     'Compound Eyes: sleep 97.5%; needs a separate False Swipe user.'),
    ('Kricketot', 'Kricketune', ('Sing', 'False Swipe', 'Taunt', 'X-Scissor'),
     'Kricketot → Kricketune L10',
     'Sing: 55%; solo sleep + 1 HP. Swarm is fine; no hidden ability.'),
    ('Ralts', 'Gallade', ('Hypnosis', 'False Swipe', 'Taunt', 'Psycho Cut'),
     'Ralts (Hypnosis L37) → Kirlia → Gallade (male + Dawn Stone)',
     'Keep male Ralts to L37; Dawn Stone: Konikoni City mart.'),
    ('Smeargle', 'Smeargle', ('Spore', 'False Swipe', 'Soak', 'Mean Look'),
     'Catch on Route 2; four Sketch copies required for the complete kit',
     'Setup project: Spore donor is on Akala; use Own Tempo or Technician.'),
    ('Shroomish', 'Breloom', ('Spore', 'False Swipe', 'Mach Punch', 'Seed Bomb'),
     'Shroomish → Breloom: delay evolution until AFTER Spore L40',
     'Use normal Poison Heal; avoid Effect Spore accidentally poisoning targets.'),
    ('Paras', 'Parasect', ('Spore', 'False Swipe', 'Swords Dance', 'Seed Bomb'),
     'Paras → Parasect L24; Spore works on Paras already at L22',
     'Use normal Dry Skin; avoid Effect Spore accidentally poisoning targets.'),
)
SKETCH_DONORS = {'spore': ('Paras', 'Paras'), 'falseswipe': ('Kricketune', 'Kricketot'),
                 'soak': ('Psyduck', 'Psyduck'), 'meanlook': ('Gastly', 'Gastly')}
NORMAL_ABILITIES = {'Butterfree': ('Compound Eyes',), 'Kricketune': ('Swarm',),
                    'Gallade': ('Steadfast',), 'Smeargle': ('Own Tempo', 'Technician'),
                    'Breloom': ('Poison Heal',), 'Parasect': ('Dry Skin',)}


def first_encounter(species: str, encounters: dict) -> dict:
    slug = tb.normalize(species)
    for island_i, island in enumerate(encounters['islands']):
        for location_i, location in enumerate(island['locations']):
            for group_i, group in enumerate(location.get('groups', [])):
                if group.get('category') != 'regular' or group.get('conditions'):
                    continue
                for item_i, item in enumerate(group.get('encounters', [])):
                    if item.get('species') != slug or item.get('form'):
                        continue
                    rates = item.get('rates', {})
                    if not any(float(v) > 0 for v in rates.values()):
                        continue
                    time = ('day' if rates.get('day', 0) > 0 and rates.get('night') == 0 else
                            'night' if rates.get('night', 0) > 0 and rates.get('day') == 0 else '')
                    level = group.get('levels', {})
                    label = f"{location['name']} · {group['name']}"
                    if time:
                        label += f' · {time}'
                    if level:
                        label += f" · L{level['min']}–{level['max']}"
                    return {'order': [island_i, location_i, group_i, item_i], 'label': label,
                            'location': location['name'], 'species_id': item['speciesId'],
                            'page': group['sourcePage'], 'rates': rates}
    raise ValueError(f'no unconditional regular encounter for {species}')


def resolve_move(sources: sm.MoveSources, final: str, base: str, key: str) -> dict:
    entry = sources.candidates(final, base).get(key)
    if not entry:
        raise ValueError(f'{final}: no obtainable Standard source for {key}')
    available = [s for s in entry['sources'] if s['via'] in ('level', 'evolution', 'TM', 'tutor')]
    if key == 'hypnosis' and final == 'Gallade':
        available = [s for s in available if s.get('form') == 'Ralts' and s.get('level') == 37]
    if key == 'spore' and final == 'Breloom':
        available = [s for s in available if s.get('form') == 'Shroomish' and s.get('level') == 40]
    if not available:
        raise ValueError(f'{final}: only unavailable/reminder/egg sources for {key}')
    chosen = min(available, key=lambda s: (0 if s['via']=='evolution' else
                 int(s['level']) if s['via']=='level' else 90 if s['via']=='TM' else 110))
    gate = sources.gate_label(key, chosen, final)
    if (key, final) in (('hypnosis', 'Gallade'), ('spore', 'Breloom')):
        gate += ' · delay evolution'
    return {'name': entry['name'], 'type': entry['type'], 'source': chosen, 'gate': gate}


def build_report(cache: Path, records: dict) -> dict:
    sources = sm.MoveSources(cache)  # verifies retained Standard manifest and pinned cache
    store = require_cache(cache)
    dex = dict(top_blocks(store.get_text('pokedex')))
    moves = dict(top_blocks(store.get_text('moves')))
    encounters = json.loads((ROOT / 'data/encounters.json').read_text())
    names = {r['name']: r for r in json.loads((ROOT / 'data/pokemon.json').read_text())}
    caught = sorted(int(k.split(':')[1]) for k, v in records.items()
                    if k.startswith('species:') and isinstance(v, dict) and v.get('s') == 'caught')
    rows = []
    for base, final, goals, evolution, note in PLANS:
        slots = cs.ability_slots(dex[tb.normalize(final)])
        normal = {v for k, v in slots.items() if k != 'H'}
        if not set(NORMAL_ABILITIES[final]) <= normal:
            raise ValueError(f'{final}: recommended ability is not an ordinary slot')
        if final == 'Butterfree':
            hit = cs.accuracy_with_ability(cs.accuracy(moves['sleeppowder']), 'Compound Eyes')
            note = f'Compound Eyes: sleep {hit:g}%; needs a separate False Swipe user.'
        elif final == 'Kricketune':
            hit = cs.accuracy(moves['sing'])
            note = f'Sing: {hit:g}%; solo sleep + 1 HP. Swarm is fine; no hidden ability.'
        selected = []
        for name in goals:
            key = sources.data.meta_by_name.get(tb.normalize(name), tb.normalize(name))
            if final == 'Smeargle':
                donor, donor_base = SKETCH_DONORS[key]
                donor_move = resolve_move(sources, donor, donor_base, key)
                place = first_encounter(donor_base, encounters)['location']
                source = {'via': 'sketch', 'donor': donor, 'donor_source': donor_move['source']}
                gate = f"Sketch ← {donor_move['source']['form']} "
                gate += (f"L{donor_move['source']['level']}" if donor_move['source']['via']=='level' else 'TM54')
                gate += f" · {sm.TM_INFO[key][1] if donor_move['source']['via']=='TM' else place}"
                selected.append({'name': donor_move['name'], 'type': donor_move['type'],
                                 'source': source, 'gate': gate})
            else:
                selected.append(resolve_move(sources, final, base, key))
            category = cs.benefit_details(key, moves[key])
            selected[-1]['category'] = category[0] if category else 'combat/control'
        if len({m['name'] for m in selected}) != 4 or sum(m['category']=='sleep' for m in selected) != 1:
            raise ValueError('four distinct moves and exactly one sleep move required')
        ownership = ('FINAL CAUGHT' if names[final]['id'] in caught else
                     'BASE CAUGHT' if names[base]['id'] in caught else 'NOT CAUGHT')
        rows.append({'base': base, 'final': final, 'owned_dex': names[base]['id'],
                     'dex': names[final]['id'], 'evolution': evolution, 'note': note,
                     'ownership': ownership, 'types': tb.types_of(store.get_text('pokedex'), final),
                     'encounter': first_encounter(base, encounters), 'moves': selected})
    return {'schema': 1, 'source_caught_ids': caught, 'caught_records': len(caught),
            'rows': sorted(rows, key=lambda r: r['encounter']['order']),
            'order_basis': 'first regular encounter, not full moveset readiness',
            'selection': 'six curated utility prospects; not a battle optimizer or raw vanilla score'}


def render(report: dict, output: Path, *, generated: str) -> None:
    rows = report['rows']
    if len(rows) != 6 or len({r['dex'] for r in rows}) != 6:
        raise ValueError('exactly six distinct options required')
    canvas = Image.new('RGB', art.SIZE, art.BG)
    draw = ImageDraw.Draw(canvas)
    atlas = Image.open(art.ATLAS).convert('RGBA')
    accent = '#80d398'
    draw.rounded_rectangle((26, 25, 1234, 2108), radius=34, fill=art.PANEL, outline=art.LINE, width=2)
    draw.rounded_rectangle((48, 44, 440, 82), radius=18, fill=accent)
    draw.text((65, 49), 'CATCH UTILITY / 06 OPTIONS', font=art.font(20, True), fill=art.BG)
    draw.text((56, 103), 'SLEEP + SAFE HP CONTROL', font=art.font(43, True), fill=art.WHITE)
    draw.text((56, 167), 'Earliest encounters first · full-kit gates shown separately', font=art.font(24), fill=art.DIM)
    draw.text((56, 205), 'Prismatic Moon Standard · no eggs / breeding / hidden abilities', font=art.font(21), fill=accent)
    for index, row in enumerate(rows):
        y = art.ROW_TOP + index * art.ROW_STEP
        draw.rounded_rectangle((48, y, 1212, y + art.ROW_HEIGHT), radius=18, fill=art.BG, outline=art.LINE)
        canvas.paste(art.sprite(atlas, row['owned_dex'], 3), (65, y + 12), art.sprite(atlas, row['owned_dex'], 3))
        draw.text((184, y + 38), '→', font=art.font(26, True), fill=art.DIM)
        icon = art.sprite(atlas, row['dex'], 4)
        canvas.paste(icon, (215, y - 2), icon)
        x = 400
        draw.text((x, y + 10), f"{index + 1}. {row['final'].upper()}", font=art.font(28, True), fill=art.WHITE)
        draw.text((x, y + 46), row['ownership'], font=art.font(16, True), fill=accent)
        for i, typ in enumerate(row['types']):
            ty = y + 15 + i * 39
            draw.rounded_rectangle((920, ty, 1095, ty + 30), radius=8, fill=art.PALETTE[typ])
            draw.text((934, ty + 3), typ.upper(), font=art.font(16, True), fill=art.BG)
        draw.text((1120, y + 28), f"#{row['dex']:03d}", font=art.font(22, True), fill=art.WHITE)
        lines = art.wrapped_lines(draw, row['evolution'], art.font(17), 780, max_lines=1)
        draw.text((400, y + 75), lines[0], font=art.font(17), fill=art.DIM)
        art.fit(draw, row['encounter']['label'], art.font(18), 1090, strict=True)
        draw.text((76, y + 102), row['encounter']['label'], font=art.font(18), fill=accent)
        art.fit(draw, row['note'], art.font(18), 1090, strict=True)
        draw.text((76, y + 126), row['note'], font=art.font(18), fill=art.DIM)
        draw.line((76, y + 152, 1185, y + 152), fill=art.LINE)
        if len(row['moves']) != 4:
            raise ValueError('four moves required per option')
        for i, move in enumerate(row['moves']):
            mx, my = 76 + 573 * (i % 2), y + 160 + 49 * (i // 2)
            art.fit(draw, move['name'], art.font(23, True), 345, strict=True)
            draw.text((mx, my), move['name'], font=art.font(23, True), fill=art.WHITE)
            draw.rounded_rectangle((mx + 381, my, mx + 511, my + 29), radius=8, fill=art.PALETTE[move['type']])
            draw.text((mx + 389, my + 3), move['type'].upper(), font=art.font(15, True), fill=art.BG)
            art.fit(draw, move['gate'], art.font(17), 515, strict=True)
            draw.text((mx, my + 29), move['gate'], font=art.font(17), fill=art.DIM)
    draw.line((54, 1934, 1206, 1934), fill=art.LINE, width=2)
    footers = [
        'Butterfree sleeps targets; it CANNOT False Swipe. Use a separate HP-control partner.',
        'Powder sleep fails on Grass / Overcoat; Insomnia / Vital Spirit block sleep.',
        'Ghost targets: Smeargle’s Soak lets False Swipe hit and removes Grass immunity.',
        'Smeargle: copy each move with Sketch; new Sketch at L11 / 21 / 31 / ... / 91.',
        'Breloom / Gallade need delayed evolution. Normal-slot Capsule: after two trials.',
        f"{generated} Phoenix · {report['caught_records']} caught · read-only roster labels",
    ]
    for i, text in enumerate(footers):
        art.fit(draw, text, art.font(18), 1140, strict=True)
        draw.text((56, 1949 + i * 25), text, font=art.font(18), fill=art.DIM if i else accent)
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output, optimize=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--uid')
    parser.add_argument('--cache', type=Path, default=configured_cache_dir())
    parser.add_argument('--report-json', type=Path)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    if args.report_json:
        report = json.loads(args.report_json.read_text())
    else:
        if not args.uid:
            parser.error('live render requires --uid')
        report = build_report(args.cache, tb.read_records(args.uid))
    output = args.output_dir / 'catch-utility.png'
    stamp = datetime.now(ZoneInfo('America/Phoenix')).strftime('%b %-d, %Y · %-I:%M %p')
    render(report, output, generated=stamp)
    snapshot = args.output_dir / 'catch-utility.json'
    snapshot.write_text(json.dumps(report, indent=2) + '\n')
    print(output)
    print(snapshot)
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
