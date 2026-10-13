import io
import json
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
import pokemon_ops as ops
from test_pokemon_ops import FakeClient, entry


class AutoEvolutionTests(unittest.TestCase):
    def test_totodile_shorthand_uses_the_next_stage_and_one_atomic_update(self):
        self.assertEqual(Path(ops.__file__).resolve().parent, TOOLS)
        client = FakeClient({"species:158": entry("caught"), "star:158": entry("on")})
        out, err = io.StringIO(), io.StringIO()
        with patch.object(ops, "FirebaseClient", return_value=client), redirect_stdout(out), redirect_stderr(err):
            try:
                code = ops.main(["--uid", "fixture", "--json", "evolve", "Totodile"])
            except SystemExit as exc:
                code = exc.code
        self.assertEqual(code, 0, err.getvalue())
        result = json.loads(out.getvalue())
        self.assertEqual(result["to_species"]["name"], "Croconaw")
        self.assertEqual(client.applied, [{"species:158": "seen", "species:159": "caught"}])
        self.assertEqual(result["verified_statuses"], {"species:158": "seen", "species:159": "caught"})
        self.assertTrue(result["verified"])
        self.assertEqual(result["caught_count"], 1)
        self.assertEqual(client.records["star:158"]["s"], "on")
        self.assertNotIn("species:160", client.records)

    def test_branch_returns_canonical_choices_without_reading_or_writing_account(self):
        client = FakeClient()
        out = io.StringIO()
        with patch.object(ops, "FirebaseClient", return_value=client), redirect_stdout(out):
            code = ops.main(["evolve", "Eevee", "--uid", "fixture", "--json"])
        result = json.loads(out.getvalue())
        self.assertEqual(code, 1)
        self.assertEqual(result.get("code"), "evolution_choice_required")
        self.assertEqual([x["name"] for x in result.get("candidates", [])], [
            "Vaporeon", "Jolteon", "Flareon", "Espeon", "Umbreon", "Leafeon", "Glaceon", "Sylveon"])
        self.assertEqual(client.reads, 0)
        self.assertEqual(client.applied, [])

    def test_uid_bound_api_accepts_an_omitted_target_and_advances_one_stage(self):
        self.assertTrue(callable(getattr(ops.PokemonStatusTool, "evolve_pokemon_status", None)), "UID-scoped evolution API is missing")
        client = FakeClient({"species:159": entry("caught")})
        result = ops.PokemonStatusTool("fixture", client=client).evolve_pokemon_status("Croconaw")
        self.assertEqual(result["to_species"]["name"], "Feraligatr")
        self.assertEqual(result["verified_statuses"], {"species:159": "seen", "species:160": "caught"})
        self.assertEqual(len(client.applied), 1)

    def test_terminal_species_is_a_clear_no_next_refusal_before_account_io(self):
        client = FakeClient()
        with self.assertRaisesRegex(ops.OperationError, "no next Generation VII evolution"):
            ops.run_pair(client, "fixture", "evolve", "Feraligatr")
        self.assertEqual(client.reads, 0)
        self.assertEqual(client.applied, [])

    def test_shorthand_dry_run_resolves_target_without_writing(self):
        client = FakeClient({"species:158": entry("caught")})
        result = ops.run_pair(client, "fixture", "evolve", "Totodile", dry_run=True)
        self.assertEqual(result["to_species"]["name"], "Croconaw")
        self.assertTrue(result["dry_run"])
        self.assertEqual(client.applied, [])
        self.assertEqual(client.records["species:158"]["s"], "caught")

    def test_already_completed_shorthand_is_verified_without_a_write(self):
        client = FakeClient({"species:158": entry("seen"), "species:159": entry("caught")})
        result = ops.run_pair(client, "fixture", "evolve", "Totodile")
        self.assertFalse(result["changed"])
        self.assertTrue(result.get("verified_no_write"), "One-call no-op must include explicit read verification")
        self.assertEqual(result.get("verified_statuses"), {"species:158": "seen", "species:159": "caught"})
        self.assertEqual(client.applied, [])
        self.assertEqual(client.reads, 1)

    def test_unknown_name_is_not_auto_corrected_and_never_reads_account(self):
        client = FakeClient()
        with self.assertRaises(ops.UnknownSpeciesError):
            ops.run_pair(client, "fixture", "evolve", "Totodile-ish")
        self.assertEqual(client.reads, 0)
        self.assertEqual(client.applied, [])

    def test_verification_failure_is_not_reported_as_success(self):
        client = FakeClient({"species:158": entry("caught")})
        client.mismatch = True
        with self.assertRaises(ops.VerificationError):
            ops.run_pair(client, "fixture", "evolve", "Totodile")

    def test_explicit_target_keeps_existing_path_even_if_auto_data_is_unavailable(self):
        client = FakeClient({"species:158": entry("caught")})
        with patch.object(ops, "infer_next_evolution", side_effect=AssertionError("must not infer")):
            result = ops.run_pair(client, "fixture", "evolve", "Totodile", "Croconaw")
        self.assertTrue(result["verified"])

    def test_trade_still_requires_two_names_before_any_read(self):
        client = FakeClient()
        with self.assertRaisesRegex(ops.OperationError, "Trade requires"):
            ops.run_pair(client, "fixture", "trade", "Totodile")
        self.assertEqual(client.reads, 0)
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            ops.build_parser().parse_args(["trade", "Totodile", "--uid", "fixture"])

    def test_duplicate_form_branches_resolve_to_one_species_without_form_writes(self):
        client = FakeClient({"species:744": entry("caught"), "form:745:dusk": entry("seen")})
        result = ops.run_pair(client, "fixture", "evolve", "Rockruff")
        self.assertEqual(result["to_species"]["id"], 745)
        self.assertEqual(client.records["form:745:dusk"]["s"], "seen")
        self.assertEqual(set(client.applied[0]), {"species:744", "species:745"})

    def test_incomplete_branch_data_cannot_turn_eevee_into_an_automatic_guess(self):
        data_path = TOOLS.parent / "data" / "pokedex-details.json"
        real_read = Path.read_text
        payload = json.loads(real_read(data_path))
        payload["species"] = [row for row in payload["species"] if row["id"] != 134]
        def read(path, *args, **kwargs):
            return json.dumps(payload) if path == data_path else real_read(path, *args, **kwargs)
        client = FakeClient()
        with patch.object(Path, "read_text", autospec=True, side_effect=read):
            with self.assertRaises(ops.SchemaError):
                ops.run_pair(client, "fixture", "evolve", "Eevee")
        self.assertEqual(client.reads, 0)
        self.assertEqual(client.applied, [])

    def test_malformed_flabebe_source_token_is_not_silently_repaired(self):
        client = FakeClient()
        with self.assertRaisesRegex(ops.SchemaError, "cannot be resolved safely"):
            ops.run_pair(client, "fixture", "evolve", "Flabébé")
        self.assertEqual(client.reads, 0)
        self.assertEqual(client.applied, [])

    def test_transport_noop_after_a_concurrent_writer_still_has_verified_statuses(self):
        class NoWriteClient:
            def __init__(self):
                self.inner = FakeClient({"species:158": entry("caught")})
            def read_records(self, uid):
                return self.inner.read_records(uid)
            def apply_records(self, uid, records, note="", expected=None):
                for key, value in records.items():
                    self.inner.records[key] = entry(value)  # another device won the race
                return {"changed": False}
        client = NoWriteClient()
        try:
            result = ops.run_pair(client, "fixture", "evolve", "Totodile")
        except KeyError as exc:
            self.fail(f"Concurrent no-write result lost its verification fields: {exc}")
        self.assertFalse(result["changed"])
        self.assertFalse(result["verified"])
        self.assertTrue(result["verified_no_write"])
        self.assertEqual(result["verified_statuses"], {"species:158": "seen", "species:159": "caught"})
        self.assertEqual(result["warning"]["code"], "already_at_status")

    def test_names_with_spaces_use_the_same_local_inference(self):
        client = FakeClient({"species:772": entry("caught")})
        result = ops.run_pair(client, "fixture", "evolve", "Type: Null")
        self.assertEqual(result["to_species"]["name"], "Silvally")
