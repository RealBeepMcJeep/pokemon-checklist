#!/usr/bin/env python3
"""Read-only combined five-team refresh; saved editorial choices are revalidated."""
import argparse
import copy
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
import zipfile
from contextlib import redirect_stdout
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'tools'))
import pokemon_ops as ops
import story_moves
import story_team_cards as cards
from PIL import Image

p = argparse.ArgumentParser()
p.add_argument('--uid', required=True)
p.add_argument('--cache', type=Path, required=True)
p.add_argument('--output-dir', type=Path, required=True)
p.add_argument('--previous', type=Path, required=True)
p.add_argument('--extra-targets', type=Path, action='append', default=[])
a = p.parse_args()
os.umask(0o077)
a.output_dir.mkdir(parents=True, exist_ok=False)
a.output_dir.chmod(0o700)

state: dict[str, object] = {'status': 'running', 'step': 'setup', 'output_dir': str(a.output_dir)}

def private_file(name, text):
    path = a.output_dir / name
    path.write_text(text)
    path.chmod(0o600)

def stage(name):
    state.update(step=name, status='running')
    private_file('run-status.json', json.dumps(state, indent=2)+'\n')

try:
    t0 = time.monotonic()
    stage('inputs')
    previous = json.loads(a.previous.read_text())
    # Reuse only editorial move NAMES, never frozen acquisition facts or roster inputs.
    saved_goals = {}
    for filename in [a.previous, *a.extra_targets]:
        saved = json.loads(filename.read_text())
        for option in saved['options']:
            for m in option['members']:
                if len(m.get('moves', [])) == 4:
                    saved_goals.setdefault(m['final'], tuple(x['name'] for x in m['moves']))
    command = [sys.executable, str(REPO / 'tools/team_synergy.py'), '--story-options', '--json',
               '--uid', a.uid, '--cache', str(a.cache)]
    # Retain normal fingerprinted-cache behavior; fresh roster loading still occurs.
    stage('selection')
    run = subprocess.run(command, capture_output=True, text=True, cwd=REPO)
    private_file('selection.stdout.log', run.stdout)
    private_file('selection.stderr.log', run.stderr)
    run.check_returncode()
    raw = json.loads(run.stdout)
    assert len(raw['options']) == 5
    raw_path = a.output_dir / 'selection.raw.json'
    raw_path.write_text(json.dumps(raw, indent=2) + '\n')
    raw_path.chmod(0o600)
    if not isinstance(raw.get('source_starred_ids'), list):
        raise ValueError('selector must retain the complete initial starred set')
    observations = {'initial_source_sets': {'caught': raw['source_caught_ids'], 'seen': raw['source_seen_ids'], 'starred': raw['source_starred_ids']}}
    private_file('selector-observations.json', json.dumps(observations, indent=2)+'\n')
    stage('move-preflight')
    paths = {(m['final'], m['owned']) for o in raw['options'] for m in o['members']}
    paths.add((raw['utility'], raw['utility']))
    local_goals = {f: saved_goals[f] for f, owned in paths
                   if len(story_moves.GOALS.get(f, ())) != 4 and f in saved_goals}
    errors = {}
    with patch.dict(story_moves.GOALS, local_goals):
        source = story_moves.MoveSources(a.cache)
        for final, owned in sorted(paths):
            try:
                assert len(source.targets(final, owned)) == 4
            except (ValueError, AssertionError) as exc:
                errors[f'{owned} -> {final}'] = str(exc)
        if errors:
            raise SystemExit(json.dumps({'raw_report': str(raw_path), 'target_errors': errors}))
        stage('render')
        with (a.output_dir / 'render.stdout.log').open('w') as out, (a.output_dir / 'render.stderr.log').open('w') as err:
            from contextlib import redirect_stderr
            with redirect_stdout(out), redirect_stderr(err):
                render_code = cards.main(['--report-json', str(raw_path), '--cache', str(a.cache),
                                '--output-dir', str(a.output_dir)], move_sources=source)
                if render_code != 0:
                    raise RuntimeError(f'renderer returned nonzero exit code {render_code}')
    stage('content-verification')
    enriched = json.loads((a.output_dir / 'story-options.json').read_text())
    stripped = copy.deepcopy(enriched)
    stripped.pop('utility_moves', None)
    for option in stripped['options']:
        for m in option['members']:
            m.pop('moves', None)
    assert stripped == raw, 'enrichment altered selection'
    # ONE final live read establishes all statuses and total, not three list invocations.
    equipment_started = time.monotonic()
    stage('held-item-report')
    import held_item_cards
    equipment_dir = a.output_dir / 'held-items'
    with (a.output_dir / 'equipment.stdout.log').open('w') as out, (a.output_dir / 'equipment.stderr.log').open('w') as err:
        from contextlib import redirect_stderr
        with redirect_stdout(out), redirect_stderr(err):
            code = held_item_cards.main(['generate', '--team-report', str(a.output_dir / 'story-options.json'), '--source-observations', str(a.output_dir / 'selector-observations.json'), '--uid', a.uid, '--cache', str(a.cache), '--output-dir', str(equipment_dir)])
            if code != 0:
                raise RuntimeError(f'held-item report returned {code}; inspect {equipment_dir}')
            stage('combined-render')
            code = cards.main(['--report-json', str(a.output_dir / 'story-options.json'), '--held-items-json', str(equipment_dir / 'held-items.json'), '--cache', str(a.cache), '--output-dir', str(a.output_dir)], move_sources=source)
            if code != 0:
                raise RuntimeError(f'combined renderer returned {code}')
    equipment_seconds = time.monotonic() - equipment_started
    if json.loads((a.output_dir / 'story-options.json').read_text()) != enriched:
        raise ValueError('equipment changed the upstream selection or move targets')
    stage('state-verification')
    records = ops.validate_record_map(ops.FirebaseClient().read_records(a.uid),
                                      [x['id'] for x in ops.load_species()])
    ids = sorted(int(k.split(':')[1]) for k, v in records.items()
                 if k.startswith('species:') and v['s'] == 'caught')
    assert ids == raw['source_caught_ids'], 'caught roster changed; gallery is superseded'
    seen_ids = sorted(int(k.split(':')[1]) for k, v in records.items()
                      if k.startswith('species:') and v['s'] == 'seen')
    if 'source_seen_ids' not in raw:
        raise ValueError('selector lacks source_seen_ids; unseen-only Pokédex rule not verified')
    if seen_ids != raw['source_seen_ids']:
        raise ValueError('Seen statuses changed; Pokédex scores may be stale—regenerate')
    final_stars = sorted(int(k.split(':')[1]) for k,v in records.items() if k.startswith('star:') and v['s'] == 'on')
    if final_stars != raw['source_starred_ids']:
        raise ValueError('complete favorites changed; regenerate selection')
    for option in raw['options']:
        assert len(option['members']) == 5
        assert len({m['dex'] for m in option['members']}) == 5
        for m in option['members']:
            target = ops.resolve_species(m['owned'], ops.load_species())
            assert target['id'] in ids, f"not caught: {m['owned']}"
    stage('png-verification')
    images = sorted(a.output_dir.glob('team-*.png'))
    assert len(images) == 5
    heights = []
    for filename in images:
        with Image.open(filename) as image:
            if image.width != 1260 or image.height <= 2120:
                raise ValueError('combined card did not expand for equipment')
            heights.append(image.height // 2)
        layout = json.loads(filename.with_suffix('.layout.json').read_text())
        if not layout['original_pixels_preserved'] or len(layout['rows']) != 6:
            raise ValueError('combined card lost original content or equipment rows')
    thumb_height = max(heights)
    sheet = Image.new('RGB', (1890, 2 * thumb_height), '#0c1223')
    for i, filename in enumerate(images):
        with Image.open(filename) as image:
            sheet.paste(image.convert('RGB').resize((630, image.height // 2)), ((i % 3)*630, (i // 3)*thumb_height))
    sheet_path = a.output_dir / 'contact-sheet.jpg'
    sheet.save(sheet_path, quality=92)
    stage('archive')
    archive = a.output_dir / 'five-story-teams.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
        for filename in images:
            z.write(filename, filename.name)
        z.write(a.output_dir / 'story-options.json', 'story-options.json')
        for name in ['held-items.json', 'held-items.md']:
            z.write(equipment_dir / name, name)
        for filename in images:
            z.write(filename.with_suffix('.layout.json'), filename.with_suffix('.layout.json').name)
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
    stage('summary')
    changes = []
    for now in raw['options']:
        before = next(o for o in previous['options'] if o['category'] == now['category'])
        project = lambda o: [(m['owned'], m['final'], m.get('evolution')) for m in o['members']]
        changes.append({'category': now['category'], 'selection_changed': project(before) != project(now),
                        'synergy_before': before.get('six_synergy'), 'synergy_now': now.get('six_synergy'),
                        'viability_before': before.get('viability'), 'viability_now': now.get('viability')})
    summary = {'output_dir': str(a.output_dir), 'caught_count': len(ids),
               'elapsed_seconds': round(time.monotonic()-t0, 2), 'roster_verified': True, 'seen_statuses_verified': True, 'complete_favorites_verified': True, 'equipment_seconds': round(equipment_seconds, 3), 'combined_layout': 'A with full Gen VII effects',
               'categories': {o['category']: [m['owned']+' -> '+m['final'] for m in o['members']]
                              for o in raw['options']}, 'deltas': changes,
               'warnings': raw.get('warnings'), 'one_off_targets_revalidated': sorted(local_goals),
               'images': [str(f) for f in images], 'zip': str(archive), 'contact_sheet': str(sheet_path)}
    (a.output_dir / 'refresh-summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    for filename in a.output_dir.iterdir():
        if filename.is_file():
            filename.chmod(0o600)
    state.update(status='succeeded', step='complete', exit_code=0)
    private_file('run-status.json', json.dumps(state, indent=2)+'\n')
    print(json.dumps(summary))

except (Exception, SystemExit) as exc:
    code = getattr(exc, 'returncode', None)
    code = code if isinstance(code, int) and 0 < code < 256 else 1
    detail = traceback.format_exc()
    state.update(status='failed', exit_code=code, error_type=type(exc).__name__, error=str(exc))
    try:
        private_file('traceback.log', detail)
        private_file('run-status.json', json.dumps(state, indent=2)+'\n')
        for filename in a.output_dir.iterdir():
            if filename.is_file():
                filename.chmod(0o600)
    except Exception as logging_error:
        print(f'DIAGNOSTIC WRITE ALSO FAILED: {logging_error}', file=sys.stderr)
    print(f"FAILED at {state['step']}; diagnostics: {a.output_dir}", file=sys.stderr)
    print(detail, file=sys.stderr)
    raise SystemExit(code) from exc
