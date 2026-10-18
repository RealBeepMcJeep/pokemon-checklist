"""Offline failure-path checks for the private gallery wrapper (no account writes)."""
import contextlib
import io
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

SCRIPT = Path(os.environ.get('GALLERY_SCRIPT', str(Path(__file__).resolve().parents[1] / 'gallery_refresh.py')))

class GalleryFailureTests(unittest.TestCase):
    def test_selector_failure_keeps_stderr_stage_traceback_and_nonzero_exit(self):
        with tempfile.TemporaryDirectory(dir=os.environ['TMPDIR']) as root:
            root = Path(root)
            previous = root / 'previous.json'
            previous.write_text(json.dumps({'options': []}))
            output = root / 'run'
            argv = [str(SCRIPT), '--uid', 'offline-test', '--cache', str(root / 'cache'),
                    '--output-dir', str(output), '--previous', str(previous)]
            mods = {name: types.ModuleType(name) for name in ('pokemon_ops', 'story_moves', 'story_team_cards')}
            failed = subprocess.CompletedProcess(['selector'], 7, 'partial stdout', 'intentional selector failure')
            def selector(*args, **kwargs):
                if kwargs.get('check'):
                    raise subprocess.CalledProcessError(7, args[0], output=failed.stdout, stderr=failed.stderr)
                return failed
            with patch.dict(sys.modules, mods), patch.object(sys, 'argv', argv), patch('subprocess.run', selector), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                try:
                    runpy.run_path(str(SCRIPT), run_name='__main__')
                except BaseException as exc:
                    failure = exc
                else:
                    failure = None
            self.assertFalse((output / 'refresh-summary.json').exists(), 'failure must not look successful')
            self.assertTrue((output / 'run-status.json').exists(), 'diagnostic stage record is missing')
            status = json.loads((output / 'run-status.json').read_text())
            self.assertEqual(status['status'], 'failed')
            self.assertEqual(status['step'], 'selection')
            self.assertEqual(status['exit_code'], 7)
            self.assertIn('intentional selector failure', (output / 'selection.stderr.log').read_text())
            self.assertIn('CalledProcessError', (output / 'traceback.log').read_text())
            self.assertIsInstance(failure, SystemExit)
            assert isinstance(failure, SystemExit)
            self.assertEqual(failure.code, 7)

    def test_renderer_nonzero_return_is_not_ignored_and_keeps_output(self):
        with tempfile.TemporaryDirectory(dir=os.environ['TMPDIR']) as root:
            root = Path(root)
            previous = root / 'previous.json'
            raw = {'options': [{'category': str(i), 'members': []} for i in range(5)],
                   'utility': 'Butterfree', 'source_caught_ids': [], 'source_seen_ids': [], 'source_starred_ids': []}
            previous.write_text(json.dumps(raw))
            output = root / 'run'
            argv = [str(SCRIPT), '--uid', 'offline-test', '--cache', str(root / 'cache'),
                    '--output-dir', str(output), '--previous', str(previous)]
            mods = {name: types.ModuleType(name) for name in ('pokemon_ops', 'story_moves', 'story_team_cards')}
            setattr(mods['story_moves'], 'GOALS', {'Butterfree': ('a', 'b', 'c', 'd')})
            admitted = types.SimpleNamespace(targets=lambda *args: ['a', 'b', 'c', 'd'])
            setattr(mods['story_moves'], 'MoveSources', lambda _: admitted)
            def render(_, *, move_sources=None):
                self.assertIs(move_sources, admitted, 'renderer failure must exercise the shared preflight source')
                print('renderer stdout marker')
                print('renderer stderr marker', file=sys.stderr)
                return 9
            setattr(mods['story_team_cards'], 'main', render)
            selected = subprocess.CompletedProcess(['selector'], 0, json.dumps(raw), '')
            with patch.dict(sys.modules, mods), patch.object(sys, 'argv', argv), patch('subprocess.run', return_value=selected), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                try:
                    runpy.run_path(str(SCRIPT), run_name='__main__')
                except BaseException as exc:
                    failure = exc
                else:
                    failure = None
            status = json.loads((output / 'run-status.json').read_text())
            self.assertEqual(status['status'], 'failed')
            self.assertEqual(status['step'], 'render', 'nonzero renderer return must fail at its own boundary')
            self.assertIn('9', status['error'])
            self.assertIn('renderer stdout marker', (output / 'render.stdout.log').read_text())
            self.assertIn('renderer stderr marker', (output / 'render.stderr.log').read_text())
            self.assertTrue((output / 'selection.raw.json').exists())
            self.assertFalse((output / 'refresh-summary.json').exists())
            self.assertIsInstance(failure, SystemExit)

if __name__ == '__main__':
    unittest.main()
