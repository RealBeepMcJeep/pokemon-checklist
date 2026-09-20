import hashlib
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import moveline as M


class MoveLineHardeningTests(unittest.TestCase):
    def test_smogon_stats_cache_and_download_are_hash_verified(self):
        raw = b"fixture stats"
        digest = hashlib.sha256(raw).hexdigest()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "moveset.txt"
            M.fetch_stats(
                "https://www.smogon.com/stats/fixture.txt",
                path,
                digest,
                downloader=lambda url: raw,
            )
            self.assertEqual(path.read_bytes(), raw)
            with self.assertRaises(M.StatsIntegrityError):
                M.fetch_stats("https://www.smogon.com/stats/fixture.txt", path, "0" * 64)
            path.unlink()
            with self.assertRaises(M.StatsIntegrityError):
                M.fetch_stats(
                    "https://www.smogon.com/stats/fixture.txt",
                    path,
                    digest,
                    downloader=lambda url: b"corrupt",
                )

    def test_unavailable_stats_tier_is_distinct_from_download_failure(self):
        with mock.patch.object(M, "_download_stats", side_effect=M.StatsUnavailable("404")):
            with self.assertRaises(M.StatsUnavailable):
                M.fetch_stats(
                    "https://www.smogon.com/stats/missing.txt",
                    Path("missing.txt"),
                    "0" * 64,
                )
        with mock.patch.object(M, "_download_stats", side_effect=OSError("offline")):
            with self.assertRaises(M.StatsDownloadError):
                M.fetch_stats(
                    "https://www.smogon.com/stats/error.txt",
                    Path("error.txt"),
                    "0" * 64,
                )

    def test_missing_shared_cache_fails_without_downloading_showdown_data(self):
        with tempfile.TemporaryDirectory() as cache:
            stderr = io.StringIO()
            with mock.patch.object(M.urllib.request, "urlopen") as download:
                with mock.patch.object(
                    sys, "argv", ["moveline.py", "pikachu", "--cache", cache, "--top", "0"]
                ):
                    with redirect_stderr(stderr):
                        result = M.main()
            self.assertEqual(result, 2)
            self.assertIn("bootstrap", stderr.getvalue())
            download.assert_not_called()

    def test_final_evolution_paths_are_branch_specific(self):
        parent_of = {
            "ralts": "",
            "kirlia": "ralts",
            "gardevoir": "kirlia",
            "gallade": "kirlia",
        }
        learned = {
            "ralts": {"sharedmove": {"level": ["20"]}},
            "kirlia": {"sharedmove": {"level": ["25"]}},
            "gardevoir": {"moonblast": {"level": ["1"]}},
            "gallade": {"closecombat": {"level": ["1"]}},
        }
        gardevoir_path = M.ancestral_path("gardevoir", parent_of)
        gallade_path = M.ancestral_path("gallade", parent_of)
        gardevoir_moves = M.path_move_union(gardevoir_path, learned)
        gallade_moves = M.path_move_union(gallade_path, learned)

        self.assertEqual(gardevoir_path, ["ralts", "kirlia", "gardevoir"])
        self.assertIn("moonblast", gardevoir_moves)
        self.assertNotIn("closecombat", gardevoir_moves)
        self.assertIn("closecombat", gallade_moves)
        self.assertNotIn("moonblast", gallade_moves)

    def test_terminal_selection_keeps_direct_input_on_one_branch(self):
        family = ["ralts", "kirlia", "gardevoir", "gallade"]
        evos_of = {"ralts": ["kirlia"], "kirlia": ["gardevoir", "gallade"]}

        self.assertEqual(M.selected_finals("gardevoir", family, evos_of), ["gardevoir"])
        self.assertEqual(M.selected_finals("gallade", family, evos_of), ["gallade"])
        self.assertEqual(M.selected_finals("ralts", family, evos_of), ["gardevoir", "gallade"])

    def test_card_header_uses_each_section_path_without_sibling_branch(self):
        parent_of = {
            "ralts": "",
            "kirlia": "ralts",
            "gardevoir": "kirlia",
            "gallade": "kirlia",
        }
        nice = {key: key.title() for key in parent_of}
        ids = {"ralts": 280, "kirlia": 281, "gardevoir": 282, "gallade": 475}
        methods = {"kirlia": "Level 20", "gardevoir": "Level 30", "gallade": "Use Dawn Stone"}
        section = {"name": "Gardevoir", "tier": "gen7ru-1630", "types": [], "grade": "B",
                   "smogon_tier": "RU", "usage": 0, "dex": 282, "rows": []}
        gallade_section = {**section, "name": "Gallade", "dex": 475}

        gardevoir = M.card_html(
            "Ralts", M.evolution_edges("gardevoir", parent_of, methods, ids, nice), [section]
        )
        gallade = M.card_html(
            "Ralts", M.evolution_edges("gallade", parent_of, methods, ids, nice), [gallade_section]
        )

        self.assertIn("Ralts", gardevoir)
        self.assertIn("Gardevoir", gardevoir)
        self.assertNotIn("Gallade", gardevoir)
        self.assertIn("Ralts", gallade)
        self.assertIn("Gallade", gallade)
        self.assertNotIn("Gardevoir", gallade)

    def _run_cli(self, species: str) -> tuple[str, str]:
        store = mock.Mock()
        store.get_text.side_effect = lambda name: {
            "learnsets": "exports.BattleLearnsets = {\n};\n",
            "moves": "exports.BattleMovedex = {\n};\n",
            "pokedex": (
                "exports.BattlePokedex = {\n"
                "\tralts: {evos: [\"kirlia\"]},\n"
                "\tkirlia: {prevo: \"Ralts\", evos: [\"Gardevoir\", \"Gallade\"]},\n"
                "\tgardevoir: {prevo: \"Kirlia\"},\n"
                "\tgallade: {prevo: \"Kirlia\"},\n"
                "};\n"
            ),
        }[name]
        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch.object(M, "require_cache", return_value=store):
            with mock.patch.object(M, "fetch_stats", side_effect=M.StatsUnavailable("offline")):
                with mock.patch.object(
                    sys, "argv", ["moveline.py", species, "--cache", "unused", "--top", "0"]
                ):
                    with redirect_stdout(stdout), redirect_stderr(stderr):
                        result = M.main()
        self.assertEqual(result, 0, stderr.getvalue())
        return stdout.getvalue(), stderr.getvalue()

    def test_direct_gardevoir_cli_reports_only_gardevoir_path(self):
        stdout, stderr = self._run_cli("gardevoir")
        self.assertEqual(stdout.count("## "), 1)
        self.assertIn("## Gardevoir", stdout)
        self.assertNotIn("## Gallade", stdout)
        self.assertIn("# Gardevoir — lineage: Ralts -> Kirlia -> Gardevoir", stderr)
        self.assertNotIn("Gallade", stderr)

    def test_direct_gallade_cli_reports_only_gallade_path(self):
        stdout, stderr = self._run_cli("gallade")
        self.assertEqual(stdout.count("## "), 1)
        self.assertIn("## Gallade", stdout)
        self.assertNotIn("## Gardevoir", stdout)
        self.assertIn("# Gallade — lineage: Ralts -> Kirlia -> Gallade", stderr)
        self.assertNotIn("Gardevoir", stderr)

    def test_ralts_cli_keeps_separate_terminal_reports_and_paths(self):
        stdout, stderr = self._run_cli("ralts")
        self.assertEqual(stdout.count("## "), 2)
        self.assertIn("## Gardevoir", stdout)
        self.assertIn("## Gallade", stdout)
        self.assertIn(
            "# Ralts — lineage: Ralts -> Kirlia -> Gardevoir ; Ralts -> Kirlia -> Gallade",
            stderr,
        )

    def test_pre_evolution_only_gate_is_explicit(self):
        gates = M.acquisition_gates(
            "gardevoir",
            ["ralts", "kirlia", "gardevoir"],
            {
                "ralts": {"level": ["20"]},
                "kirlia": {},
                "gardevoir": {},
            },
            {"ralts": "Ralts", "kirlia": "Kirlia", "gardevoir": "Gardevoir"},
        )
        self.assertEqual(gates, [("level", "TEACH BEFORE EVOLVING: Ralts L20")])

    def test_punctuated_species_names_resolve_and_bad_input_is_clean(self):
        rows = [
            {"id": 122, "name": "Mr. Mime", "slug": "mr-mime"},
            {"id": 29, "name": "Nidoran♀", "slug": "nidoran-f"},
            {"id": 772, "name": "Type: Null", "slug": "type-null"},
        ]
        self.assertEqual(M.resolve_species("mr-mime", rows)["id"], 122)
        self.assertEqual(M.resolve_species("nidoran-f", rows)["id"], 29)
        self.assertEqual(M.resolve_species("type-null", rows)["id"], 772)
        self.assertEqual(M.resolve_species("Nidoran♀", rows)["id"], 29)
        with self.assertRaises(M.SpeciesInputError) as ctx:
            M.resolve_species("not-a-real-species", rows)
        self.assertIn("no such species", str(ctx.exception))

    def test_hidden_power_keeps_usage_variant_and_legality_key(self):
        shown, kind, coverage = M.display_move_for_usage(
            "hiddenpower", "Hidden Power", "Normal", {"Hidden Power Ice": 61.2}
        )
        self.assertEqual((shown, kind, coverage), ("Hidden Power Ice", "Ice", "Ice"))
        self.assertEqual(M.canon("Hidden Power Ice"), "hiddenpower")
        self.assertEqual(M.acquisition_label("TM", "hiddenpower", "Gardevoir"),
                         "TM10 — Paniola Ranch")
        self.assertIn("TEACH BEFORE EVOLVING", M.acquisition_label(
            "TM", "psychic", "TEACH BEFORE EVOLVING: Ralts"
        ))

    def test_acquisition_labels_include_locations_and_endgame_warning(self):
        self.assertIn("Battle Tree", M.acquisition_label("tutor", "knockoff", "Gardevoir"))
        self.assertIn("12 BP", M.acquisition_label("tutor", "knockoff", "Gardevoir"))
        reminder = M.acquisition_label("reminder", "Gardevoir L1", "Gardevoir")
        self.assertIn("Mount Lanakila", reminder)
        self.assertIn("endgame", reminder.lower())
        egg = M.acquisition_label("egg", "Gardevoir", "Gardevoir", profile="prismatic-standard")
        self.assertIn("level not specified", egg.lower())
        self.assertNotIn("L", egg)

    def test_card_contains_coverage_metadata_and_responsive_layout(self):
        section = {
            "name": "Gardevoir",
            "tier": "gen7ou-1695",
            "types": ["Psychic", "Fairy"],
            "grade": "A",
            "smogon_tier": "OU",
            "usage": 1.0,
            "dex": 282,
            "rows": [(61.2, "Hidden Power Ice", "Ice", "-", [("TM", "Gardevoir")])],
        }
        rendered = M.card_html("Ralts", [], [section], profile="prismatic-standard")
        self.assertIn('data-legality-key="hiddenpower"', rendered)
        self.assertIn('data-coverage-type="Ice"', rendered)
        self.assertIn("Prismatic Standard", rendered)
        self.assertIn("grid-template-columns:minmax(0, 1fr) auto", rendered)


if __name__ == "__main__":
    unittest.main()
