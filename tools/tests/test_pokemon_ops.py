import copy
import subprocess
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
REPO = TOOLS.parent
sys.path.insert(0, str(TOOLS))

import pokemon_ops as ops  # noqa: E402
import pokemon_chat  # noqa: E402


SPECIES = [
    {"id": 1, "name": "Bulbasaur", "slug": "bulbasaur"},
    {"id": 4, "name": "Charmander", "slug": "charmander"},
    {"id": 5, "name": "Charmeleon", "slug": "charmeleon"},
    {"id": 6, "name": "Charizard", "slug": "charizard"},
    {"id": 25, "name": "Pikachu", "slug": "pikachu"},
    {"id": 26, "name": "Raichu", "slug": "raichu"},
    {"id": 150, "name": "Mewtwo", "slug": "mewtwo"},
]


def entry(value):
    return {"s": value, "at": 1, "by": "fixture"}


class FakeClient:
    def __init__(self, records=None):
        self.records = copy.deepcopy(records or {})
        self.applied = []
        self.reads = 0
        self.mismatch = False

    def read_records(self, uid):
        self.reads += 1
        result = copy.deepcopy(self.records)
        if self.mismatch and self.applied:
            for key in self.applied[-1]:
                result[key] = entry("seen")
        return result

    def apply_records(self, uid, records, note=""):
        self.applied.append(copy.deepcopy(records))
        for key, value in records.items():
            self.records[key] = entry(value)


class PokemonOpsTests(unittest.TestCase):
    def test_mark_writes_only_the_minimal_diff(self):
        client = FakeClient({"species:25": entry("seen"), "species:1": entry("caught")})
        result = ops.run_mark(client, "uid", "pikachu", "caught", SPECIES)
        self.assertEqual(result["changes"], {"species:25": "caught"})
        self.assertEqual(client.applied, [{"species:25": "caught"}])
        self.assertGreaterEqual(client.reads, 2)

    def test_mark_noop_does_not_write(self):
        client = FakeClient({"species:25": entry("caught")})
        result = ops.run_mark(client, "uid", "Pikachu", "caught", SPECIES)
        self.assertFalse(result["changed"])
        self.assertEqual(client.applied, [])
        self.assertEqual(client.reads, 1)

    def test_exact_favorites_turns_set_difference_into_one_patch(self):
        client = FakeClient({
            "star:1": entry("on"),
            "star:25": entry("on"),
            "star:150": entry("off"),
            "species:25": entry("caught"),
        })
        result = ops.run_favorites_exact(client, "uid", ["Pikachu", "Mewtwo"], SPECIES)
        self.assertEqual(result["changes"], {"star:1": "off", "star:150": "on"})
        self.assertEqual(client.applied, [{"star:1": "off", "star:150": "on"}])
        self.assertIn("species:25", client.records)

    def test_exact_favorites_noop_is_not_a_write(self):
        client = FakeClient({"star:25": entry("on"), "star:150": entry("on")})
        result = ops.run_favorites_exact(client, "uid", ["mewtwo", "pikachu"], SPECIES)
        self.assertFalse(result["changed"])
        self.assertEqual(client.applied, [])

    def test_evolve_payload_marks_from_seen_and_to_caught(self):
        client = FakeClient({"species:25": entry("caught")})
        result = ops.run_pair(client, "uid", "evolve", "pikachu", "raichu", SPECIES)
        self.assertEqual(result["changes"], {"species:25": "seen", "species:26": "caught"})
        self.assertEqual(client.applied, [result["changes"]])

    def test_trade_payload_marks_from_seen_and_to_caught(self):
        client = FakeClient()
        result = ops.run_pair(client, "uid", "trade", "bulbasaur", "charmander", SPECIES)
        self.assertEqual(result["changes"], {"species:1": "seen", "species:4": "caught"})

    def test_invalid_status_is_rejected_before_read(self):
        client = FakeClient()
        with self.assertRaises(ops.OperationError):
            ops.run_mark(client, "uid", "pikachu", "query", SPECIES)
        self.assertEqual(client.reads, 0)

    def test_invalid_query_record_value_is_rejected(self):
        with self.assertRaises(ops.SchemaError):
            ops.validate_record_map({"species:25": entry("query")}, {25})

    def test_unresolved_server_value_sentinel_is_rejected_as_at(self):
        # A real Firebase GET always resolves {".sv": "timestamp"} to a number;
        # a record still carrying the raw sentinel must fail closed, not be
        # special-cased as valid.
        with self.assertRaises(ops.SchemaError):
            ops.validate_record_map(
                {"species:25": {"s": "caught", "at": {".sv": "timestamp"}}}, {25}
            )

    def test_uid_flag_is_accepted_after_the_subcommand(self):
        # argparse's subparsers action swallows every token after the subcommand,
        # so --uid must work whether it comes before or after `mark`.
        parser = ops.build_parser()
        before = parser.parse_args(["--uid", "u1", "mark", "pikachu", "caught"])
        after = parser.parse_args(["mark", "pikachu", "caught", "--uid", "u1"])
        self.assertEqual(before.uid, "u1")
        self.assertEqual(after.uid, "u1")

    def test_missing_uid_anywhere_is_still_rejected(self):
        parser = ops.build_parser()
        args = parser.parse_args(["mark", "pikachu", "caught"])
        self.assertIsNone(args.uid)

    def test_apply_reports_no_write_when_transport_no_ops_the_write(self):
        # A concurrent writer can land between pokemon_ops.py's own read and the
        # transport's later fresh read-then-diff, so the transport makes no write
        # (and no log/* entry) even though the value already matches by the time
        # we read it back. That must not be reported the same as a verified write.
        class RaceClient:
            def __init__(self):
                self.applied = 0

            def read_records(self, uid):
                if self.applied:
                    return {"species:25": entry("seen")}
                return {"species:25": entry("caught")}

            def apply_records(self, uid, records, note=""):
                self.applied += 1
                return {"ok": True, "changed": False, "changes": []}

        result = ops.run_mark(RaceClient(), "uid", "pikachu", "seen", SPECIES)
        self.assertTrue(result["changed"])
        self.assertFalse(result.get("verified"))
        self.assertTrue(result.get("verified_no_write"))

    def test_ambiguous_name_fails_without_a_write(self):
        client = FakeClient()
        with self.assertRaises(ops.AmbiguousSpeciesError):
            ops.run_mark(client, "uid", "char", "seen", SPECIES)
        self.assertEqual(client.reads, 0)
        self.assertEqual(client.applied, [])

    def test_readback_mismatch_fails(self):
        client = FakeClient()
        client.mismatch = True
        with self.assertRaises(ops.VerificationError):
            ops.run_mark(client, "uid", "pikachu", "caught", SPECIES)
        self.assertEqual(client.applied, [{"species:25": "caught"}])

    def test_schema_rejects_unknown_key_and_bad_value(self):
        with self.assertRaises(ops.SchemaError):
            ops.validate_record_map({"species:9999": entry("caught")}, {25})
        with self.assertRaises(ops.SchemaError):
            ops.validate_record_map({"star:25": entry("caught")}, {25})

    def test_dry_run_reads_but_does_not_write(self):
        client = FakeClient()
        result = ops.run_mark(client, "uid", "pikachu", "caught", SPECIES, dry_run=True)
        self.assertTrue(result["dry_run"])
        self.assertEqual(client.applied, [])
        self.assertEqual(client.reads, 1)

    def test_query_intents_have_no_mutation_record(self):
        species = pokemon_chat.load_species()
        result = pokemon_chat.parse("status of pikachu", species)
        self.assertEqual(result["intent"], "status_query")
        self.assertNotIn("record", result)

    def test_question_phrasing_never_emits_a_mutation_record(self):
        species = pokemon_chat.load_species()
        for text in (
            "did I already get bulbasaur",
            "have I got a pikachu yet?",
            "did you catch a mewtwo",
        ):
            result = pokemon_chat.parse(text, species)
            self.assertEqual(result["intent"], "status_query", text)
            self.assertNotIn("record", result, text)

    def test_multi_species_chat_phrase_fails_clearly(self):
        species = pokemon_chat.load_species()
        result = pokemon_chat.parse("evolve pikachu into raichu", species)
        self.assertEqual(result["intent"], "multi_species")
        self.assertNotIn("record", result)
        self.assertIn("pokemon_ops", result["reply"])

    def test_ops_help_has_no_reset_or_delete_subcommand(self):
        for command in ("reset", "delete"):
            proc = subprocess.run(
                [sys.executable, str(TOOLS / "pokemon_ops.py"), "--uid", "uid", command],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(proc.returncode, 0, command)
            self.assertNotIn("unknown species", proc.stderr.lower())

    def test_firebase_wrapper_has_settled_per_key_logs_and_hidden_delete_help(self):
        source = (TOOLS / "firebase-admin-rest.mjs").read_text(encoding="utf-8")
        self.assertIn("key: change.key", source)
        self.assertIn("from: change.from", source)
        self.assertIn("to: change.to", source)
        self.assertNotIn('"  --delete <path>', source)
        self.assertIn("--verified and --confirm-delete", source)


if __name__ == "__main__":
    unittest.main()
