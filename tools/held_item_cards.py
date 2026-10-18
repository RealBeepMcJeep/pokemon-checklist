#!/usr/bin/env python3
"""Render held-item evidence using the checklist's sprite atlas and pixel-card theme."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw

import story_team_cards as art

ROOT = Path(__file__).resolve().parents[1]
SIZE = (1260, 2400)
SOURCES = json.loads((ROOT / 'data/held-item-sources.json').read_text())


def load_context(cache: Path):
    """Verify the real core, add-on and retained hack sources before interpretation."""
    import hashlib
    import held_items as hi
    from showdown_data import require_cache
    corpus = ROOT / 'references/prismatic-moon'
    manifest = json.loads((corpus / 'MANIFEST.json').read_text())
    for entry in manifest:
        raw = (corpus / entry['name']).read_bytes()
        if len(raw) != entry['bytes'] or hashlib.sha256(raw).hexdigest() != entry['sha256']:
            raise ValueError('retained hack corpus integrity mismatch: ' + entry['name'])
    core = require_cache(cache)
    addon = hi.source_store(cache)
    addon.verify_cache()
    items = hi.parse_items(addon.get_text('items'), addon.get_text('items-gen7'))
    addon.get_text('abilities'); addon.get_text('abilities-gen7')
    details = json.loads((ROOT / 'data/pokedex-details.json').read_text())
    utility = next(x for x in details['species'] if x['id'] == 12)
    tables = {}
    def lookup_usage(name, tier):
        if tier not in hi.TIER_TO_FORMAT:
            return None, {'format': 'unavailable', 'cutoff': 0, 'requested_tier': tier, 'format_battles': None,
                          'reason': 'No matching pinned format; no substitute tier was used.'}
        mapped = hi.TIER_TO_FORMAT[tier]
        if mapped not in tables:
            blob, meta = hi.usage_snapshot(addon.cache_dir, tier)
            tables[mapped] = ({hi.normalize_name(k): v for k,v in blob.items()}, meta)
        blob, meta = tables[mapped]
        return blob.get(hi.normalize_name(name)), {**meta, 'requested_tier': tier, 'tier_mapping': mapped != tier}
    return {'items': items, 'dex_text': core.get_text('pokedex'), 'moves_text': core.get_text('moves'),
            'lookup_usage': lookup_usage, 'utility_tier': utility.get('ownTier') or utility['tier']}


def validate_sources(team, expected, records):
    """Reject same-count substitutions, Seen changes and favorites changes alike."""
    if set(expected) != {'caught', 'seen', 'starred'}:
        raise ValueError('snapshot needs all three source sets')
    found = {
        'caught': sorted(int(k.split(':')[1]) for k,v in records.items() if k.startswith('species:') and v.get('s') == 'caught'),
        'seen': sorted(int(k.split(':')[1]) for k,v in records.items() if k.startswith('species:') and v.get('s') == 'seen'),
        'starred': sorted(int(k.split(':')[1]) for k,v in records.items() if k.startswith('star:') and v.get('s') == 'on'),
    }
    if (team['source_caught_ids'] != expected['caught'] or team['source_seen_ids'] != expected['seen']
            or ('source_starred_ids' in team and team['source_starred_ids'] != expected['starred'])):
        raise ValueError('team report and selection snapshot disagree')
    if found != expected:
        raise ValueError('live source sets changed; regenerate the upstream selection')
    return found


def citations(ids):
    return ''.join(f'[{number}]' for number in ids)


def markdown(report):
    text = ['# Held items: story choices and historical competitive evidence', '', report['horizon'], '',
            '**Editorial story-role tiers, not a global tournament ranking.** A = reusable role default; B = flexible/replenishable; C = specialize the build first; X = a separate mechanic. Access is a separate axis. No measured effectiveness or win-rate claim.', '',
            'Items, individual abilities, IVs/EVs/natures and learned moves are unrecorded. “Current” means a reachable collection/quest opportunity at the last-confirmed horizon, not equipped or owned. Stock USUM berry/quest fallbacks are not verified hack-engine behavior.[5][6]', '',
            'Gen VII item definitions merge the pinned root source with its Gen VII overrides, then reject later-generation items. Root data alone includes Gen VIII items. The Mago Berry override has stale prose; its callback and inherited threshold take precedence.[1][3]', '',
            'Historical values are November 2019 per-species weighted Items shares, normalized by their own block sum, not species usage, raw set frequency, correlated builds or win rates. Raw species appearances, weighted denominator and total format battles are distinct quantities.', '',
            '## Retained team-selection assumptions', *report.get('selection_warnings', []),
            'Base/form assumptions and unconfirmed individual inventory remain exactly those of the source team snapshot; no regional form or ability is inferred.', '',
            '## Role-aware overview', '']
    for item in report.get('guide', []):
        text += [f"### {item['rank']} · {item['name']} — {item['role']}",
                 item['effect'] + '[1][3]',
                 f"Editorial reason: {item['reason']} Tradeoff: {item['tradeoff']}",
                 'Suggested users in these teams: ' + (', '.join(item.get('users', [])) or 'No matching planned user; reference only.'),
                 f"Access: {item['access']['location']}. {item['access']['gate']} Cost: {item['access']['cost']}" + citations(item['access']['sources']), '']
    for team in report['teams']:
        text += ['## Team: ' + team['category'], '']
        if team.get('one_free_glasses_allocation'):
            text += ['One free Wise Glasses quest copy allocated to ' + team['one_free_glasses_allocation'] + ' within this alternative party (highest planned base Sp. Atk, stable source-order tie; editorial, not measured battle strength). Other members use replenishable berries until extra copies are available.[5][9]', '']
        for row in team['members']:
            text += [f"### {row['owned']} → {row['final']} · #{row['dex']}", row['evolution'],
                     'Role: ' + row['story']['role'] + '. Possible ability slots: ' + row['abilities_possible'] + '.[2][4]']
            for stage in ['current', 'later']:
                opt = row['story'][stage]
                text += [f"**{stage.title()} conditional choice: {opt['item']['name']}.** {opt['item']['effect']}[1][3]",
                         opt['reason'], f"{opt['access']['location']}. {opt['access']['gate']} {opt['access']['cost']}" + citations(opt['access']['sources'])]
            for note in row['notes']:
                text += [note + '[1][2][4]']
            comp = row['competitive']; meta = comp['provenance']
            cite = next((s['id'] for s in SOURCES if s['url'] == meta.get('url')), None)
            text += [f"**Historical competitive lens:** {meta['format']} / cutoff {meta['cutoff']} / November 2019; requested tier {meta['requested_tier']}. "
                     f"Raw species appearances: {comp['raw_count']}; weighted item denominator: {comp['denominator']:.8g}; format battles: {meta['format_battles']}. "
                     + ('Explicit BL/tier-family mapping to this legal higher format. ' if meta.get('tier_mapping') else '') + (citations([cite]) if cite else '')]
            if comp['status'] != 'ok':
                text += ['No per-species item evidence in this source; no substitute format or invented set.']
            for item in comp['items'][:10]:
                text += [f"- {item['name']}: {item['share']:.2%} of this species' item weight. {item['effect']}[1][3] "
                         f"Flexible-story fit: {'compatible' if item['story_fit'] else 'conditional / unsuitable without changes'} — {item['fit_reason']}"]
            text += ['']
    text += ['## Practical limits and equipment traps', '',
             'Never put Rocky Helmet/contact damage on a catching utility holder: the target can lose HP outside safe control. Life Orb recoil and one-use Focus Sash/berries cost resources in ordinary story battles. Ability-dependent exceptions are not a claim about an unrecorded individual.[1][2]',
             'Hawlucha seeds need actual matching terrain plus a confirmed Unburden plan. Pelipper’s Damp Rock needs a real rain plan; Drizzle is a possible ordinary slot, not confirmed on the individual. Historical shares are not a complete correlated build.[1][2]',
             'Eviolite only helps while the holder’s species can evolve in Gen VII; it stops helping after the final evolution. Light Ball is Pikachu-only, not Raichu. Thick Club is Cubone/Marowak-only. Power equipment halves Speed and is not generic combat speed gear. Training/economy, friendship and bag-use evolution equipment belong to separate goals, not these battle tiers.[1][9]',
             'Mega Stones and Z-Crystals are separate mechanics with species/move/unlock requirements; these reports do not assume them available or equipped. One-use berries are consumed; a Z-Crystal is not a disposable healing berry.[1]',
             'Wide Lens multiplies accuracy; Zoom Lens only does so when moving after the target. The Wide Lens Route 1 gift is Sun/Moon-only, NOT Ultra Sun/Ultra Moon. No verified Standard wild-held acquisition/rate is supplied here.[1][7]',
             'The creator puts many held items at Battle Royal Dome for BP and says prices are reduced, but supplies no numeric prices. Do not substitute vanilla 48 BP. Thick Club and Light Ball are later Mt. Hokulani specialist stock; the school quest is one free copy, not a full-team supply.[5][8][9]', '',
             '## Sources', '']
    text += [f"[{s['id']}] {s['title'] or s['url']} — {s['url']}" for s in SOURCES]
    return '\n\n'.join(text) + '\n'


def render_bundle(report, directory: Path):
    """All six phone images and a cited text report; fail on overflow, never ellipsize."""
    directory.mkdir(parents=True, exist_ok=True)
    if len(report['teams']) != 5:
        raise ValueError('need all five teams')
    paths, layouts = [], []
    atlas = Image.open(art.ATLAS).convert('RGBA')
    for number, team in enumerate(report['teams'], 1):
        if len(team['members']) != 6:
            raise ValueError('need six complete rows including Butterfree')
        canvas = Image.new('RGB', SIZE, art.BG); d = ImageDraw.Draw(canvas)
        face = lru_cache(maxsize=20)(art.font)
        def lines(text, x, y, size, *, width=1100, maximum=2, bold=False, color=art.WHITE):
            parts = art.wrapped_lines(d, text, face(size, bold), width, maximum)
            for line in parts:
                d.text((x, y), line, font=face(size, bold), fill=color); y += size + 5
            return y
        d.rounded_rectangle((26, 25, 1234, 2380), radius=30, fill=art.PANEL, outline=art.LINE, width=2)
        lines('HELD ITEMS · ' + team['category'].upper(), 58, 47, 43, bold=True)
        lines('STORY CHOICES ≠ LADDER POPULARITY', 60, 106, 27, color='#f2cf69')
        lines('Last confirmed: first island complete · item ownership / individual kit unknown', 60, 149, 23, color=art.DIM)
        for index, row in enumerate(team['members']):
            y = 230 + index * 310
            d.rounded_rectangle((43, y, 1217, y + 302), radius=18, fill=art.BG, outline=art.LINE)
            canvas.paste(art.sprite(atlas, row['owned_dex'], 2), (57, y + 10), art.sprite(atlas, row['owned_dex'], 2))
            canvas.paste(art.sprite(atlas, row['dex'], 2), (153, y + 10), art.sprite(atlas, row['dex'], 2))
            lines(f"{row['owned']} → {row['final']}  #{row['dex']}", 250, y + 7, 28, width=930, bold=True)
            lines(row['evolution'], 250, y + 48, 20, width=930, maximum=2, color=art.DIM)
            current, later = row['story']['current'], row['story']['later']
            location = 'School night quest · free [5]' if current['id'] == 'wiseglasses' else 'Route 2 pile · free / daily [6]'
            lines(f"CURRENT IF COLLECTED: {current['item']['name']} · {location}", 62, y + 100, 25, bold=True, color='#80d398')
            lines(current['item']['effect'], 62, y + 136, 20, maximum=2, color=art.DIM)
            place = 'Mt. Hokulani / money' if later['id'] == 'thickclub' else 'Akala Dome / BP'
            lines(f"LATER: {later['item']['name']} · {place} [9]. {later['item']['effect']}", 62, y + 185, 21, maximum=2, color='#f2cf69')
            comp = row['competitive']; meta = comp['provenance']
            choices = ', '.join(f"{x['name']} {x['share']:.1%}" for x in comp['items'][:2]) or 'No species item evidence'
            bottom = lines(f"LADDER {meta['format']}/{int(meta['cutoff'])}: {choices}", 62, y + 244, 20, maximum=2, color='#bca8e7')
            if bottom >= y + 302:
                raise ValueError('row content crosses its panel boundary')
            layouts.append({'team': team['category'], 'row': index, 'bottom': bottom, 'panel_bottom': y + 302})
        footer = [
            'Current access is a collection/quest opportunity, NOT an inventory claim. School: after Hala + Big Wave Beach rumor + night mysteries; only one free copy.[5][6]',
            'Later: Akala Dome needs BP (exact hack prices undocumented). Thick Club needs later Mt. Hokulani access. Effects [1][3]; acquisition [5][6][9].',
            'Ladder shares: Nov 2019 weighted species Items, not effectiveness. Full roles, ability/set caveats, sample data and source links: held-items.md.',
        ]
        fy = 2112
        for text in footer:
            fy = lines(text, 60, fy, 20, maximum=2, color=art.DIM) + 8
        lines(report.get('generated', 'Offline redraw'), 60, 2338, 18, color=art.DIM)
        name = f'held-team-{number:02d}.png'; canvas.save(directory / name, optimize=True); paths.append(name)
    canvas = Image.new('RGB', SIZE, art.BG); d = ImageDraw.Draw(canvas); face = lru_cache(maxsize=10)(art.font)
    d.text((55, 35), 'HELD ITEMS · STORY ROLE TIERS', font=face(42, True), fill=art.WHITE)
    d.text((57, 99), 'Editorial fit first. Access and historical usage are separate.', font=face(25), fill=art.DIM)
    sections = [
        ('A · REUSABLE ROLE DEFAULTS', 'Leftovers: 1/16 max HP each turn. Black Sludge: same healing for Poison only; hurts others. Thick Club: doubles Cubone/Marowak Attack. Wide Lens: 1.1x accuracy, but Standard access is unverified. A means strong WITHIN that role, not universally best.[1][3]'),
        ('B · FLEXIBLE / REPLENISHABLE', 'Muscle Band / Wise Glasses: 1.1x matching physical / special power. Expert Belt: 1.2x super-effective damage only. Sitrus: heals 1/4 max HP at half HP or less; Oran heals 10 HP. Berries are one-use; restock them. Lum cures a status/confusion once, but its access is not verified here.[1]'),
        ('C · SPECIALIZE THE BUILD FIRST', 'Choice Band / Specs / Scarf: 1.5x Attack / Sp. Atk / Speed, but move locking. Life Orb: 1.3x damage with HP cost. Assault Vest: 1.5x Sp. Def, disables status moves. Focus Sash: full-HP activation, single use. Popular on a ladder does not mean convenient in story play.[1]'),
        ('ABILITY / SET TRAPS', 'Butterfree: Compound Eyes is conditional, not confirmed; Wide Lens differs from move-last Zoom Lens. NEVER use Rocky Helmet/contact punishment for catching. Hawlucha seeds need terrain plus Unburden. Pelipper rain gear needs confirmed rain. Hidden-ability builds are not assumed.[1][2]'),
        ('X · SPECIES / TRAINING / SPECIAL MECHANICS', 'Eviolite only while the species can still evolve in Gen VII. Light Ball works on Pikachu, NOT Raichu. Power equipment halves Speed; training/economy goals are separate. Bag-use evolution items, Mega Stones and Z-Crystals are not generic held battle bonuses.[1][9]'),
        ('ACCESS · LAST-CONFIRMED FIRST ISLAND', 'NOW: Route 2 daily berry pile (Sitrus in large piles; RNG / possible battle), or one free Wise Glasses from the school night quest after Hala. LATER: Akala Battle Royal Dome BP vendors; exact reduced hack prices undocumented. Thick Club: Mt. Hokulani specialist mart. Item ownership is unknown.[5][6][9]'),
    ]
    for index, (title, text) in enumerate(sections):
        y = 170 + index * 350
        d.rounded_rectangle((35, y, 1225, y + 332), radius=18, fill=art.PANEL, outline=art.LINE)
        d.text((60, y + 14), title, font=face(27, True), fill='#f2cf69')
        fy = y + 60
        for line in art.wrapped_lines(d, text, face(27), 1130, 8):
            d.text((60, fy), line, font=face(27), fill=art.WHITE); fy += 34
        if fy >= y + 328:
            raise ValueError('overview section overflow')
    d.text((60, 2307), 'Mechanics: pinned Gen VII + overrides. Full citations and per-team evidence:', font=face(23), fill=art.DIM)
    d.text((60, 2343), 'held-items.md · November 2019 competitive data is NOT a win-rate ranking.', font=face(23), fill=art.DIM)
    canvas.save(directory / 'held-overview.png', optimize=True)
    paths.insert(0, 'held-overview.png')
    (directory / 'held-items.md').write_text(markdown(report))
    return {'images': paths, 'row_layouts': layouts, 'size': list(SIZE)}


def main(argv=None):
    import argparse
    import hashlib
    import traceback
    import zipfile
    from datetime import datetime
    from zoneinfo import ZoneInfo
    import held_items as hi
    import team_builder as tb
    from showdown_data import configured_cache_dir
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    boot = sub.add_parser('bootstrap', help='Explicitly fetch and hash-check pinned add-on sources')
    boot.add_argument('--cache', type=Path, default=configured_cache_dir())
    live = sub.add_parser('generate', help='Validate a selected team snapshot against fresh full account sets')
    live.add_argument('--team-report', type=Path, required=True)
    live.add_argument('--source-observations', type=Path, required=True)
    live.add_argument('--uid', required=True)
    live.add_argument('--cache', type=Path, default=configured_cache_dir())
    live.add_argument('--output-dir', type=Path, required=True)
    redraw = sub.add_parser('redraw', help='Offline archival redraw, not a fresh recommendation')
    redraw.add_argument('--report-json', type=Path, required=True)
    redraw.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args(argv)
    if args.action == 'bootstrap':
        hi.bootstrap_sources(args.cache)
        print(json.dumps({'status': 'verified', 'source_directory': str(hi.source_store(args.cache).cache_dir)}))
        return 0
    output = args.output_dir.resolve()
    if output == ROOT or ROOT in output.parents:
        raise ValueError('personal artifacts must stay outside the public repository')
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    output.chmod(0o700)
    def save(name, value):
        path = output / name
        path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
        path.chmod(0o600)
    team, expected = {}, {}
    try:
        if args.action == 'generate':
            team = json.loads(args.team_report.read_text())
            observations = json.loads(args.source_observations.read_text())
            expected = observations.get('initial_source_sets', observations)
            validate_sources(team, expected, tb.read_records(args.uid))
            context = load_context(args.cache)
            report = hi.build_report(team, **context)
            report['guide'] = hi.make_guide(report, context['items'])
            report['source_sets'] = expected
            report['source_team_sha256'] = hashlib.sha256(args.team_report.read_bytes()).hexdigest()
            report['selection_observations_sha256'] = hashlib.sha256(args.source_observations.read_bytes()).hexdigest()
            report['source_provenance'] = {'addon': hi.source_store(args.cache).provenance(), 'usage': hi.USAGE_SOURCES}
            report['generated'] = datetime.now(ZoneInfo('America/Phoenix')).strftime('%b %d, %Y · %I:%M %p MST')
        else:
            report = json.loads(args.report_json.read_text())
        save('held-items.json', report)
        rendered = render_bundle(report, output)
        if len(rendered['images']) != 6:
            raise ValueError('renderer did not produce overview plus all five cards')
        for name in rendered['images']:
            with Image.open(output / name) as image:
                if image.size != SIZE:
                    raise ValueError('wrong held-item image size')
                image.verify()
        if args.action == 'generate':
            validate_sources(team, expected, tb.read_records(args.uid))
        names = [*rendered['images'], 'held-items.json', 'held-items.md']
        with zipfile.ZipFile(output / 'held-items.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
            for name in names:
                archive.write(output / name, name)
        with zipfile.ZipFile(output / 'held-items.zip') as archive:
            if archive.namelist() != names or archive.testzip() is not None:
                raise ValueError('held-item ZIP verification failed')
        receipt = {'status': 'succeeded', 'mode': args.action, 'fresh_account_reads': 2 if args.action == 'generate' else 0,
                   'full_source_sets_equal': args.action == 'generate', **rendered, 'zip_entries': names,
                   'file_sha256': {name: hashlib.sha256((output / name).read_bytes()).hexdigest() for name in [*names, 'held-items.zip']}}
        save('run-status.json', receipt)
        for path in output.iterdir():
            if path.is_file():
                path.chmod(0o600)
        print(json.dumps({'status': 'succeeded', 'mode': args.action, 'images': len(rendered['images']), 'output': str(output),
                          'fresh_account_reads': receipt['fresh_account_reads'], 'full_source_sets_equal': receipt['full_source_sets_equal']}))
        return 0
    except Exception as error:
        path = output / 'traceback.log'
        path.write_text(traceback.format_exc()); path.chmod(0o600)
        save('run-status.json', {'status': 'failed', 'mode': args.action, 'error': str(error), 'traceback': str(path)})
        print(json.dumps({'status': 'failed', 'error': str(error), 'traceback': str(path)}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
