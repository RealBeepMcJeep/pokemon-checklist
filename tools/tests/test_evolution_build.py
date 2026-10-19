"""Exercise the actual admitted-source evolution compiler when caches are installed."""
import importlib
import importlib.util
import sys
import subprocess
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class EvolutionBuildTests(unittest.TestCase):
    def test_cli_builds_a_reproducible_artifact_and_refuses_stale_output(self):
        import showdown_data as sd
        cache = sd.configured_cache_dir()
        override = cache.parent / "regional" / "gen7-pokedex.js"
        if not cache.exists() or not override.exists():
            self.skipTest("verified pinned data cache is not installed")
        script = Path(__file__).resolve().parents[1] / "build_evolution_data.py"
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "evolutions.json"
            output.write_text("stale")
            args = [sys.executable, str(script), "--cache", str(cache), "--gen7-pokedex", str(override), "--output", str(output)]
            stale = subprocess.run([*args, "--check"], capture_output=True, text=True)
            self.assertNotEqual(stale.returncode, 0, "stale evolution data must fail its CLI check")
            generated = subprocess.run(args, capture_output=True, text=True)
            self.assertEqual(generated.returncode, 0, generated.stderr)
            self.assertIn("825 targets", generated.stdout)
            first = output.read_bytes()
            subprocess.run(args, check=True, capture_output=True)
            self.assertEqual(first, output.read_bytes())
            subprocess.run([*args, "--check"], check=True, capture_output=True)

    def test_compiled_graph_uses_verified_sources_and_separate_standard_methods(self):
        import showdown_data as sd
        cache = sd.configured_cache_dir()
        override = cache.parent / "regional" / "gen7-pokedex.js"
        if not cache.exists() or not override.exists():
            self.skipTest("verified pinned data cache is not installed")
        self.assertIsNotNone(importlib.util.find_spec("build_evolution_data"), "verified evolution compiler is missing")
        compiler = importlib.import_module("build_evolution_data")
        graph = compiler.build(cache, override)
        self.assertEqual(len(graph["nodes"]), 825)
        self.assertEqual(len(graph["edges"]), 398)
        edges = {(row["from"], row["to"]): row for row in graph["edges"]}
        self.assertEqual(edges[("737", "738")]["prismatic"], "Thunder Stone")
        self.assertEqual(edges[("133", "470")]["prismatic"], "Leaf Stone")
        self.assertEqual(edges[("744", "745")]["prismatic"], "level 25 during the day")
        self.assertEqual(edges[("74:alolan", "75:alolan")]["stock"], "Level 25")
        self.assertEqual(edges[("75:alolan", "76:alolan")]["prismatic"], "high friendship + level")
        self.assertEqual(edges[("104", "105:alolan")]["stock"], "Level 28 at night")
        self.assertNotIn("52", graph["nodes"])
        self.assertNotIn(("52:alolan", "53:kanto"), edges)
        self.assertEqual(graph["source"]["showdownCommit"], sd.SHOWDOWN_COMMIT)
        self.assertEqual(graph["source"]["standardEvolution"]["sha256"], "206c040f4b4ddad295a8f3680508ab41514d65ad6cec06acda036a356b0355b1")
        self.assertEqual(graph, compiler.build(cache, override))


if __name__ == "__main__":
    unittest.main()
