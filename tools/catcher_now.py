#!/usr/bin/env python3
"""Read-only Prismatic Standard catcher capabilities at a confirmed training horizon.

Heuristic points, NOT capture percentages or competitive strength. Unconfirmed
individual move retention/ability slots remain explicit assumptions.
"""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path
import catcher_score as cs
import story_moves as sm
from showdown_data import configured_cache_dir
from showdown_text import field, object_after

ROOT = Path(__file__).resolve().parents[1]
STATUS = {'sleep', 'paralysis', 'freeze'}


def select_parts(trace: list[dict], max_slots: int = 4) -> list[dict]:
    best = {}
    for part in trace:
        if part['value'] > best.get(part['category'], {'value': -1})['value']:
            best[part['category']] = part
    status = max((p for p in best.values() if p['category'] in STATUS),
                 key=lambda p: p['value'], default=None)
    core = ([status] if status else []) + ([best['falseswipe']] if 'falseswipe' in best else [])
    extras = sorted((p for p in best.values() if p['category'] not in STATUS | {'falseswipe'}),
                    key=lambda p: -p['value'])[:max(0, max_slots-len(core))]
    return [dict(p, contribution=p['value']) for p in core] + [
        dict(p, contribution=p['value'] * 0.6 ** (i+1)) for i, p in enumerate(extras)]


def available(source: dict, move: str, level: int, owned_tms: set[str]) -> bool:
    return (source['via'] == 'level' and 1 < source['level'] <= level) or (
        source['via'] == 'TM' and move in owned_tms)


def score_stage(slug: str, sources: sm.MoveSources, data: dict, level: int,
                owned_tms: set[str], owned_slug: str | None = None) -> dict:
    owned_slug = owned_slug or slug
    name = sources.data.nice[slug]
    body = data['dex'][slug]
    normal = [v for k, v in cs.ability_slots(body).items() if k != 'H'] or [None]
    pool = sources.candidates(slug, owned_slug)
    variants = []
    future = []
    for ability in normal:
        trace = []
        for move, entry in pool.items():
            meta = data['moves'].get(move, '')
            details = cs.benefit_details(move, meta)
            if not details:
                continue
            category, accuracy, chance = details
            # Damaging secondary statuses aren't safe when the target is at 1 HP.
            if category in STATUS and field(meta, 'category') != 'Status':
                continue
            gates = [g for g in entry['sources'] if available(g, move, level, owned_tms) or g['via'] == 'evolution']
            if not gates:
                if ability == normal[0]:
                    future.append({'name': entry['name'], 'category': category,
                                   'gates': [sources.gate_label(move, g, name) for g in entry['sources']]})
                continue
            source = min(gates, key=lambda g: (0 if g['via'] in {'TM', 'evolution'} else g['level']))
            hit = cs.hit_chance(accuracy * 100, chance, ability)
            value = cs.CATEGORY_BASE[category] * hit
            gate = sources.gate_label(move, source, name)
            if source['via'] == 'TM':
                gate += ' · OWNED'
            trace.append({'move': entry['name'], 'move_id': move, 'type': entry['type'],
                          'category': category, 'land': hit, 'factor': 1.0,
                          'source': source, 'gate': gate, 'value': value})
        parts = select_parts(trace)
        variants.append({'ability': ability, 'parts': parts, 'trace': trace,
                         'score': sum(p['contribution'] for p in parts)})
    chosen = max(variants, key=lambda x: (x['score'], x['ability'] != 'Effect Spore'))
    dex = sources.data.id_of[slug]
    stats = {k: int(v) for k, v in re.findall(r'(\w+):\s*(\d+)', object_after(body, 'baseStats') or '')}
    return {'name': name, 'slug': slug, 'dex': dex, 'owned': sources.data.nice[owned_slug], 'owned_dex': sources.data.id_of[owned_slug],
            'path': [sources.data.nice[s] for s in cs.ml.ancestral_path(slug, sources.data.parent_of)[cs.ml.ancestral_path(slug, sources.data.parent_of).index(owned_slug):]], **chosen, 'false_swipe': any(p['category']=='falseswipe' for p in chosen['parts']),
            'future_moves': future, 'stats': stats, 'bst': sum(stats.values()),
            'tier': data['details'].get(dex, {}).get('ownTier') or data['tier_of'].get(slug, '?'),
            'types': data['details'].get(dex, {}).get('types', [])}


def build_report(records: dict, cache: Path, level: int = 30,
                 owned_tms: set[str] | None = None, species: str | None = None) -> dict:
    sources = sm.MoveSources(cache)
    data = cs.load_rank_data(cache, ROOT)
    owned_tms = owned_tms if owned_tms is not None else {'falseswipe'}
    if species:
        slugs = cs.normalize_species_list(species, data['rows'])
        caught = sorted(sources.data.id_of[x] for x in slugs)
    else:
        caught = sorted(int(k.split(':')[1]) for k,v in records.items()
                        if k.startswith('species:') and v.get('s') == 'caught')
        slugs = [data['by_id'][i]['slug'] for i in caught]
    families = {}
    for slug in slugs:
        nodes = {slug}
        for path in cs.reachable_descendant_paths(slug, data['dex']):
            for stage in path[1:]:
                method = sources.data.evo_method.get(stage, '')
                match = re.fullmatch(r'Level (\d+)', method)
                if not match or int(match[1]) > level:
                    break
                nodes.add(stage)
        options = [score_stage(stage, sources, data, level, owned_tms, slug) for stage in sorted(nodes)]
        row = max(options, key=lambda r: (r['score'], -len(r['path'])))
        root = cs.ml.ancestral_path(slug, sources.data.parent_of)[0]
        previous = families.get(root)
        if previous is None or (row['score'], -len(row['path'])) > (previous['score'], -len(previous['path'])):
            families[root] = row
    rows = list(families.values())
    if 'smeargle' in slugs:
        smeargle = next(r for r in rows if r['slug'] == 'smeargle')
        trace = []
        for donor in rows:
            if donor['slug'] == 'smeargle':
                continue
            for part in donor['trace']:
                move = part['move_id']
                details = cs.benefit_details(move, data['moves'][move])
                if details is None:
                    raise ValueError(f'Lost verified move metadata for Sketch donor: {move}')
                category, accuracy, chance = details
                hit = cs.hit_chance(accuracy * 100, chance, smeargle['ability'])
                source = {'via': 'sketch', 'donor': donor['name'], 'owned_donor': donor['owned'],
                          'donor_source': part['source']}
                trace.append(dict(part, source=source, land=hit, factor=0.8,
                                  value=cs.CATEGORY_BASE[category] * hit * 0.8,
                                  gate=f"Sketch ← {donor['name']} · {part['gate']}"))
        budget = min(4, sum(1 for n in sources.levels[235]['sketch'] if n <= level))
        if budget >= 2:
            parts = select_parts(trace, budget)
            smeargle.update(trace=trace, parts=parts, score=sum(p['contribution'] for p in parts),
                            false_swipe=any(p['category']=='falseswipe' for p in parts),
                            setup_required=True, sketch_slots=budget,
                            setup_note='Copy moves BEFORE the L11/L21 milestones; existing higher-level Smeargle may need a fresh Route 2 catch or later Sketch slots.')
    rows = sorted((r for r in rows if r['score'] > 0), key=lambda r: (-r['score'],r['name']))
    return {'schema': 1, 'level': level, 'source_caught_ids': caught, 'owned_tms': sorted(owned_tms),
            'rows': rows, 'scope': 'Current owned stages; trained/retained moves and ordinary ability require checking.',
            'model': 'One best major status + False Swipe + up to two utility moves at 0.6/0.36 decay. Ready sources only; no tier/bulk points.',
            'bases': cs.CATEGORY_BASE, 'source': json.loads((ROOT/'data/pokedex-details.json').read_text())['source']}


def render(report: dict, output: Path) -> None:
    from PIL import Image, ImageDraw
    import story_team_cards as art
    rows = report['rows'][:5]
    if not any(r['name'] == 'Butterfree' for r in rows):
        reference = next((r for r in report['rows'] if r['name'] == 'Butterfree'), None)
        if reference is not None:
            rows = rows[:4] + [dict(reference, reference_inclusion=True)]
    height = 340 + len(rows) * 460 + 330
    canvas = Image.new('RGB', (1260, height), art.BG)
    draw = ImageDraw.Draw(canvas)
    atlas = Image.open(art.ATLAS).convert('RGBA')
    accent = '#80d398'
    def text(x, y, value, size=23, color=art.DIM, bold=False, width=1130):
        lines = art.wrapped_lines(draw, str(value), art.font(size, bold), width, max_lines=6)
        for n, line in enumerate(lines):
            draw.text((x, y+n*(size+6)), line, font=art.font(size,bold), fill=color)
        return len(lines)*(size+6)
    text(54, 32, 'CATCHER COMPARISON / PRISMATIC STANDARD', 22, accent, True)
    text(54, 79, 'YOUR NEXT CATCHER', 46, art.WHITE, True)
    text(54, 148, f"First island complete · training ceiling L{report['level']} · TM54 owned", 26)
    practical = next((r['name'] for r in rows if r['false_swipe'] and not r.get('setup_required')), 'a separate HP-control partner')
    text(54, 191, f'Practical safe-HP option: {practical}.', 24, accent)
    text(54, 231, 'Score = one best major status + safe HP control + discounted utility.', 23)
    text(54, 269, 'Heuristic points, NOT catch percentages. Tier/stats do not affect the score.', 22)
    notes = {
        'Paras': 'Spore + False Swipe is usable by L22. Prefer Dry Skin; Effect Spore can poison targets. Learn Spore before optional Parasect evolution at L24.',
        'Butterfree': 'Compound Eyes required for 97.5%. Cannot learn False Swipe. Stun Spore is a fallback, not extra score. Keep it with a separate HP-control partner.',
        'Kricketune': 'Owned Kricketot → Kricketune at L10; Sing at L18. Solo sleep + 1 HP, but Sing only lands 55% under neutral accuracy/evasion.',
        'Jynx': 'Owned Smoochum → Jynx at L30 grants Lovely Kiss. Keep Mean Look from Smoochum L25. No False Swipe; use a separate HP-control partner.',
        'Smeargle': 'SETUP PROJECT: each Sketch copy gets a ×0.80 effort factor (heuristic). Consume Sketch before L11/L21; a higher-level individual may need a fresh Route 2 catch.'}
    for index, row in enumerate(rows):
        top = 328 + index*460
        draw.rounded_rectangle((35,top,1225,top+444),radius=22,fill=art.PANEL,outline=art.LINE,width=2)
        icon = art.sprite(atlas,row['dex'],3)
        canvas.paste(icon,(54,top+12),icon)
        name = f"{index+1}. {row['name'].upper()}" + (' · REFERENCE' if row.get('reference_inclusion') else '')
        text(192,top+16,name,28,art.WHITE,True,width=740)
        text(1000,top+17,f"{row['score']:.2f}",31,accent,True,width=200)
        text(1000,top+58,'POINTS',16,art.DIM,True,width=200)
        path = ' → '.join(row['path'])
        text(192,top+59,f"Owned: {row['owned']} · Plan: {path}",20,width=780)
        stats = row['stats']
        text(192,top+90,f"Battle lens only: tier {row['tier']} · BST {row['bst']} · Atk {stats.get('atk','?')} / SpA {stats.get('spa','?')} · {row['ability'] or 'ordinary ability'}",18,width=985)
        y = top+124
        for part in row['parts']:
            base = cs.CATEGORY_BASE[part['category']]
            decay = part['contribution']/part['value'] if part['value'] else 0
            formula = f"{base:g} × {part['land']*100:g}% × {part['factor']:g}"
            if decay != 1:
                formula += f" × {decay:g}"
            text(65,y,f"{part['move']}  |  {formula} = {part['contribution']:.2f} pts",22,art.WHITE,True)
            text(65,y+29,part['gate'],18,width=1110)
            y += 56
        note = notes.get(row['name'], 'Training/retention and ordinary ability need checking; future moves are not scored.')
        used = text(65,y+7,note,19,accent,width=1100)
        if y+7+used > top+437:
            raise ValueError(f"Card row text overflows: {row['name']}")
    footer = 338+len(rows)*460
    draw.line((45,footer,1215,footer),fill=art.LINE,width=2)
    foot = [
        f"Buildable by L{report['level']}; check your individual's ability and retained moves before switching.",
        'Sleep = ×2.5 catch-rate modifier; paralysis = ×1.5. Major statuses never stack.',
        'Spore / Sleep Powder fail on Grass, Overcoat or Safety Goggles; sleep immunity still applies.',
        'False Swipe cannot hit Ghosts: use Odor Sleuth/Foresight first, or Soak.',
        'Smeargle: replace Super Fang with a sourced Odor Sleuth for Ghosts; Soak donor Psyduck needs L31.',
        'Super Fang is an opener only: NEVER use it on a target already at 1 HP.',
        f"Pinned Gen VII + verified Standard levels · {len(report['source_caught_ids'])} caught · read-only snapshot."]
    y=footer+20
    for line in foot:
        y += text(54,y,line,20,width=1145)+8
    if y > height-12:
        raise ValueError('Card footer overflows')
    output.parent.mkdir(parents=True,exist_ok=True)
    canvas.save(output, optimize=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--uid')
    group.add_argument('--species')
    parser.add_argument('--cache', type=Path, default=configured_cache_dir())
    parser.add_argument('--level', type=int, default=30)
    parser.add_argument('--output-dir', type=Path)
    args = parser.parse_args()
    if not 2 <= args.level <= 100:
        parser.error('--level must be 2..100')
    records = cs.read_account_records(args.uid, ROOT) if args.uid else {}
    report = build_report(records, args.cache, args.level, species=args.species)
    if args.output_dir:
        args.output_dir.mkdir(parents=True,exist_ok=True)
        (args.output_dir/'report.json').write_text(json.dumps(report,indent=2))
        render(report,args.output_dir/'catchers.png')
    print(json.dumps(report, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
