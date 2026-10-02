"""Selection cache contracts; all state lives in isolated miniature fixtures."""
import copy
import importlib
import io
import contextlib
import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
import team_options as opt
import team_synergy as ts


def miniature():
    members = [{"final": f"Member{i}", "endpoint_id": 20 + i,
                "caught_ids": [20 + i], "caught_as": [f"Member{i}"],
                "lineage_ids": [20 + i], "types": [typ], "points": 4,
                "tier": "RU", "usage": 0.1, "rank": 5, "favorite": False,
                "moves": [(typ, 80, 1.0)], "weak": set(), "resist": set(),
                "atk": 100, "spa": 110, "bulk": 280, "spe": 110,
                "evolution_path": [{"name": f"Member{i}", "id": 20 + i}]}
               for i, typ in enumerate(["Fire", "Water", "Grass", "Electric", "Ice", "Ground"])]
    utility = {**copy.deepcopy(members[0]), "final": "Butterfree", "endpoint_id": 12,
               "caught_ids": [12], "caught_as": ["Butterfree"], "types": ["Bug", "Flying"]}
    plans = copy.deepcopy(members)
    for p in plans:
        p["dex_plan"] = {"new_entries": [p["final"]], "owned": p["final"],
                         "owned_dex": p["endpoint_id"], "evolution_path": p["evolution_path"]}
    return [*members, utility], utility, {}, plans


class StoryCacheTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name) / "selection"
        self.inputs = miniature()

    def cache(self):
        self.assertTrue((TOOLS / "story_cache.py").exists(), "selection caching helper is missing")
        return importlib.import_module("story_cache")

    def select(self, inputs=None, **kwargs):
        p, u, c, d = inputs or self.inputs
        return self.cache().choose_cached(p, u, c, pokedex_profiles=d,
                                          selector=kwargs.pop("selector", opt.choose_options),
                                          cache_dir=self.directory, **kwargs)

    def test_warm_hit_skips_selection_restores_types_and_fresh_profile_identity(self):
        calls = []
        def selector(*args, **kwargs):
            calls.append(True)
            return opt.choose_options(*args, **kwargs)
        cold = self.select(selector=selector)
        fresh = copy.deepcopy(self.inputs)
        warm = self.select(fresh, selector=selector)
        self.assertEqual(len(calls), 1)
        self.assertEqual(warm, cold)
        self.assertIsInstance(warm[0]["objective_key"], tuple)
        self.assertIsInstance(warm[0]["objective_key"][-1], tuple)
        self.assertIsInstance(warm[0]["profiles"], tuple)
        self.assertIsInstance(warm[0]["profiles"][0]["weak"], set)
        for option in warm:
            for profile in option["profiles"]:
                self.assertTrue(any(profile is p for p in fresh[0] + fresh[3]))
        files = list(self.directory.glob("*.json"))
        self.assertEqual(len(files), 1)
        json.loads(files[0].read_text())
    def test_corrupt_unsupported_missing_and_oversized_payloads_are_misses(self):
        cache = self.cache()
        self.select(implementation="fixed")
        path = next(self.directory.glob("*.json"))
        valid = path.read_text()
        bad_schema = json.loads(valid)
        bad_schema["schema"] = 999
        for content in ("{broken", json.dumps(bad_schema), "{}", "[]"):
            with self.subTest(content=content[:30]):
                path.write_text(content)
                calls = []
                def selector(*args, **kwargs):
                    calls.append(True)
                    return opt.choose_options(*args, **kwargs)
                result = self.select(selector=selector, implementation="fixed")
                self.assertEqual(len(calls), 1)
                self.assertEqual(len(result), 5)
        # Valid JSON still misses if it exceeds the read cap.
        path.write_text(valid)
        with mock.patch.object(cache, "MAX_BYTES", len(valid.encode()) - 1):
            before = len(calls)
            self.select(selector=selector, implementation="fixed")
            self.assertEqual(len(calls), before + 1)
        path.unlink()
        before = len(calls)
        self.select(selector=selector, implementation="fixed")
        self.assertEqual(len(calls), before + 1)
        # Exercise the actual keyed payload, not a different selector's key.
        path.write_text("{broken")
        self.assertEqual(self.select(), opt.choose_options(self.inputs[0], self.inputs[1], {},
                                                         pokedex_profiles=self.inputs[3]))

    def test_cache_io_failure_falls_back_but_selector_errors_propagate(self):
        self.directory.write_text("not a directory")
        self.assertEqual(len(self.select()), 5)
        def failing(*args, **kwargs):
            raise RuntimeError("selection failure")
        with self.assertRaisesRegex(RuntimeError, "selection failure"):
            self.select(selector=failing)

    def test_private_modes_repaired_atomic_write_and_symlinks_not_followed(self):
        cache = self.cache()
        self.directory.mkdir(mode=0o777)
        os.chmod(self.directory, 0o777)
        replace = os.replace
        observed = []
        def atomic(source, target):
            observed.append(stat.S_IMODE(Path(source).stat().st_mode))
            replace(source, target)
        with mock.patch.object(cache.os, "replace", side_effect=atomic):
            self.select()
        path = next(self.directory.glob("*.json"))
        self.assertEqual(observed, [0o600])
        self.assertEqual(stat.S_IMODE(self.directory.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        os.chmod(path, 0o666)
        os.chmod(self.directory, 0o777)
        self.select()
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.directory.stat().st_mode), 0o700)
        path.unlink()
        target = Path(self.tmp.name) / "untouched"
        target.write_text("untouched")
        path.symlink_to(target)
        self.assertEqual(len(self.select()), 5)
        self.assertEqual(target.read_text(), "untouched")
        self.assertEqual(sorted(p.name for p in self.directory.iterdir()), [path.name])
    def test_complete_prepared_inputs_invalidate_not_just_source_count(self):
        calls = []
        def selector(*args, **kwargs):
            calls.append(True)
            return opt.choose_options(*args, **kwargs)
        self.select(selector=selector, implementation="v1")
        changes = {
            "caught/provenance": lambda x: x[0][0].update(caught_ids=[999], caught_as=["Other"]),
            "favorite": lambda x: x[0][0].update(favorite=True),
            "utility": lambda x: x[1].update(types=["Normal"]),
            "evolution endpoint": lambda x: x[3][0].update(endpoint_id=777),
            "new entries": lambda x: x[3][0]["dex_plan"].update(new_entries=["New", "Another"]),
            "viability": lambda x: x[0][0].update(points=999),
            "ability usage": lambda x: x[0][0].update(competitive_ability_usage={"Swarm": 99.0}),
            "form": lambda x: x[0][0].update(alolan=True),
            "exclusion": lambda x: x[0].pop(0),
            "chart": lambda x: x[2].update(fire={"Water": 1}),
        }
        for name, change in changes.items():
            with self.subTest(name=name):
                fresh = copy.deepcopy(self.inputs)
                change(fresh)
                before = len(calls)
                self.select(fresh, selector=selector, implementation="v1")
                self.assertEqual(len(calls), before + 1)
        self.select(selector=selector, implementation="v2")
        self.assertEqual(len(calls), 12)
        before = len(calls)
        self.select(selector=selector, implementation="v1", enabled=False)
        self.assertEqual(len(calls), before + 1)

    def test_identity_includes_python_ranking_rust_sources_and_native_binary(self):
        cache = self.cache()
        root = Path(self.tmp.name) / "implementation"
        tools = root / "tools"
        native = tools / "native"
        native.mkdir(parents=True)
        sources = [tools / "team_options.py", tools / "team_synergy.py",
                   native / "main.rs", native / "Cargo.toml", native / "team-search"]
        for path in sources:
            path.write_text("version one")
        os.chmod(sources[-1], 0o755)
        for path in sources:
            with self.subTest(path=path.name):
                before = cache.implementation_identity(opt.choose_options, root=root)
                path.write_text(path.read_text() + " changed")
                after = cache.implementation_identity(opt.choose_options, root=root)
                self.assertNotEqual(before, after)

    def test_retention_keeps_at_most_32_entries(self):
        for version in range(35):
            self.select(implementation=str(version))
        self.assertEqual(len(list(self.directory.glob("*.json"))), 32)
    def test_valid_json_payload_corruption_is_a_miss(self):
        calls = []
        def selector(*args, **kwargs):
            calls.append(True)
            return opt.choose_options(*args, **kwargs)
        self.select(selector=selector)
        path = next(self.directory.glob("*.json"))
        payload = json.loads(path.read_text())
        payload["options"] = ["list", []]
        path.write_text(json.dumps(payload))
        self.assertEqual(len(self.select(selector=selector)), 5)
        self.assertEqual(len(calls), 2)

    def test_atomic_failure_leaves_no_partial_file_and_root_symlink_is_rejected(self):
        cache = self.cache()
        with mock.patch.object(cache.os, "replace", side_effect=OSError("disk failure")):
            self.assertEqual(len(self.select()), 5)
        self.assertEqual(list(self.directory.iterdir()), [])
        self.directory.rmdir()
        external = Path(self.tmp.name) / "external"
        external.mkdir()
        os.chmod(external, 0o755)
        self.directory.symlink_to(external, target_is_directory=True)
        self.assertEqual(len(self.select()), 5)
        self.assertEqual(stat.S_IMODE(external.stat().st_mode), 0o755)
        self.assertEqual(list(external.iterdir()), [])


class StoryCacheCLITests(unittest.TestCase):
    def setUp(self):
        import hashlib
        import showdown_data as sd
        import team_builder as tb
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name) / "verified"
        names = ["Butterfree", "Charizard", "Blastoise", "Venusaur", "Raichu", "Alakazam", "Gengar"]
        types = [["Bug", "Flying"], ["Fire", "Flying"], ["Water"], ["Grass", "Poison"],
                 ["Electric"], ["Psychic"], ["Ghost", "Poison"]]
        dex = {tb.normalize(name): {"species": name, "types": typ,
               "baseStats": {k: 100 for k in ("hp", "atk", "def", "spa", "spd", "spe")},
               "abilities": {"0": "Overgrow"}} for name, typ in zip(names, types)}
        self.payloads = {"pokedex": ("exports.BattlePokedex = " + json.dumps(dex) + ";").encode(),
                         "moves": b"exports.BattleMovedex = {};",
                         "learnsets": b"exports.BattleLearnsets = {};",
                         "tiers": b"exports.BattleFormatsData = {};",
                         "typechart": ("exports.BattleTypeChart = " + json.dumps(
                             {t: {"damageTaken": {}} for t in ts.ALL_TYPES}) + ";").encode()}
        specs = {name: sd.DatasetSpec(name=name, filename=f"{name}.js",
                 url=f"https://fixture.test/{name}.js", commit="offline-miniature",
                 sha256=hashlib.sha256(value).hexdigest()) for name, value in self.payloads.items()}
        original_store = sd.ShowdownDataStore
        original_store(self.directory, datasets=specs,
                       downloader=lambda url: self.payloads[Path(url).stem]).bootstrap()
        factory = mock.patch.object(sd, "ShowdownDataStore",
                                    side_effect=lambda path: original_store(path, datasets=specs))
        factory.start()
        self.addCleanup(factory.stop)
        self.records = {f"species:{i}": {"s": "caught"} for i in (12, 6, 9, 3, 26, 65, 94)}
        transport = mock.patch.object(tb, "read_records", side_effect=lambda uid: copy.deepcopy(self.records))
        self.read = transport.start()
        self.addCleanup(transport.stop)
        self.calls = []
        original_choose = opt.choose_options
        def counted(*args, **kwargs):
            self.calls.append(True)
            return original_choose(*args, **kwargs)
        selector = mock.patch.object(opt, "choose_options", new=counted)
        selector.start()
        self.addCleanup(selector.stop)

    def cli(self, *flags):
        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch.object(sys, "argv", ["team_synergy.py", "--uid", "offline",
                               "--cache", str(self.directory), "--story-options", "--json", *flags]), \
             contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = ts.main()
        return code, stdout.getvalue(), stderr.getvalue()

    def test_real_story_cli_warm_hit_still_reads_validates_and_builds_fresh_report(self):
        cold = self.cli()
        self.assertEqual(cold[0], 0, cold[2])
        first = json.loads(cold[1])
        self.assertEqual(len(first["options"]), 5)
        self.assertEqual(len(first["options"][0]["members"]), 5)
        warm = self.cli()
        self.assertEqual(json.loads(warm[1]), first)
        self.assertEqual(len(self.calls), 1, "warm CLI must skip expensive selection")
        self.assertEqual(self.read.call_count, 2, "warm CLI must read fresh Firebase records")
        self.records["species:999"] = {"s": "caught"}  # not a usable candidate; report must still refresh
        refreshed = json.loads(self.cli()[1])
        self.assertEqual(refreshed["caught_records"], 8)
        self.assertIn(999, refreshed["source_caught_ids"])
        self.assertEqual(len(self.calls), 1)
        (self.directory / "moves.js").write_text("corrupt")
        failed = self.cli()
        self.assertEqual(failed[0], 2)
        self.assertIn("error:", failed[2])
        self.assertEqual(failed[1], "")
        self.assertEqual(len(self.calls), 1)

    def test_real_cli_corrupt_cache_and_failed_writes_do_not_fail_report(self):
        self.assertEqual(self.cli()[0], 0)
        directory = self.directory / "story-selection-v1"
        path = next(directory.glob("*.json"))
        self.assertEqual(stat.S_IMODE(directory.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        for content in ("{broken", json.dumps({"schema": 999, "key": path.stem})):
            path.write_text(content)
            before = len(self.calls)
            code, stdout, stderr = self.cli()
            self.assertEqual(code, 0, stderr)
            self.assertEqual(len(json.loads(stdout)["options"]), 5)
            self.assertEqual(len(self.calls), before + 1)
        path.unlink()
        directory.rmdir()
        directory.write_text("not a directory")
        code, stdout, stderr = self.cli()
        self.assertEqual(code, 0, stderr)
        self.assertEqual(len(json.loads(stdout)["options"]), 5)
        self.assertEqual(directory.read_text(), "not a directory")

    def test_real_cli_bypass_does_not_read_or_write_selection_cache(self):
        cold = self.cli("--no-result-cache")
        self.assertEqual(cold[0], 0, cold[2])
        self.assertFalse((self.directory / "story-selection-v1").exists())
        self.assertEqual(self.cli()[0], 0)
        before = {p.name: p.read_bytes() for p in (self.directory / "story-selection-v1").glob("*.json")}
        self.assertEqual(self.cli("--no-result-cache")[0], 0)
        self.assertEqual(len(self.calls), 3)
        after = {p.name: p.read_bytes() for p in (self.directory / "story-selection-v1").glob("*.json")}
        self.assertEqual(before, after)

    def test_card_live_command_forwards_bypass_into_real_story_cli(self):
        import story_team_cards as cards
        import subprocess
        routed = []
        def run(command, **kwargs):
            routed.append(command)
            flags = ["--no-result-cache"] if "--no-result-cache" in command else []
            code, stdout, stderr = self.cli(*flags)
            self.assertEqual(code, 0, stderr)
            return subprocess.CompletedProcess(command, code, stdout, stderr)
        def render(report, option, number, atlas, output, **kwargs):
            output.write_bytes(b"card routing fixture")
        with mock.patch.object(cards.subprocess, "run", side_effect=run), \
             mock.patch.object(cards, "add_move_targets", side_effect=lambda report, cache: report), \
             mock.patch.object(cards, "render_card", side_effect=render), \
             contextlib.redirect_stdout(io.StringIO()):
            for bypass in (False, False, True):
                flags = ["--no-result-cache"] if bypass else []
                self.assertEqual(cards.main(["--uid", "offline", "--cache", str(self.directory),
                                 "--output-dir", str(Path(self.tmp.name) / "cards"), *flags]), 0)
        self.assertNotIn("--no-result-cache", routed[0])
        self.assertIn("--no-result-cache", routed[-1])
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(self.read.call_count, 3)


if __name__ == "__main__":
    unittest.main()
