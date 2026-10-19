"""Regional operations use synthetic records and never contact Firebase."""
import unittest
import inspect
import io
import json
from contextlib import redirect_stdout
from unittest.mock import patch as mock_patch

from test_pokemon_ops import FakeClient, SPECIES, entry, ops


class RegionalResolutionTests(unittest.TestCase):
    def test_cli_status_reports_exact_form_separately_from_aggregate_ownership(self):
        argv = ["--uid", "fixture-account", "--json", "status", "Raichu", "--form", "kanto"]
        _, unknown = ops.build_parser().parse_known_args(argv)
        self.assertEqual(unknown, [], "status CLI lacks exact-form reads")
        client = FakeClient({"species:26": entry("caught"), "form:26:alolan": entry("caught")})
        output = io.StringIO()
        with mock_patch.object(ops, "FirebaseClient", return_value=client), redirect_stdout(output):
            code = ops.main(argv)
        self.assertEqual(code, 0, output.getvalue())
        result = json.loads(output.getvalue())
        self.assertEqual(result["status"], "none")
        self.assertEqual(result["aggregate_status"], "caught")
        self.assertEqual(result["form"], "kanto")
        self.assertEqual(client.applied, [])
        text = io.StringIO()
        with redirect_stdout(text):
            ops._print_result(result, False)
        self.assertIn("Raichu (Kanto)", text.getvalue())

    def test_evolution_wrapper_accepts_an_explicit_regional_target(self):
        self.assertIn("to_form", inspect.signature(ops.PokemonStatusTool.evolve_pokemon_status).parameters, "evolution wrapper lacks form endpoints")
        client = FakeClient({"species:25": entry("caught"), "setting:forms": entry("on")})
        tool = ops.PokemonStatusTool("fixture-account", client, SPECIES)
        result = tool.evolve_pokemon_status("Pikachu", "Raichu", to_form="kanto")
        self.assertEqual(result["to_form"], "kanto")
        self.assertEqual(client.records["form:26:kanto"]["s"], "caught")
        self.assertEqual(ops.record_value(client.records, "form:26:alolan"), "none")
        self.assertEqual(client.records["species:25"]["s"], "seen")
        self.assertEqual(len(client.applied), 1)

    def test_exact_favorites_accept_more_than_six_collection_targets(self):
        client = FakeClient()
        result = ops.run_favorites_exact(client, "fixture-account", [row["name"] for row in SPECIES], SPECIES, form_targets=["26:alolan", "26:kanto"])
        canonical_count = len(result["exact"]) - len({key.split(":")[0] for key in result["exact_forms"]}) + len(result["exact_forms"])
        self.assertGreater(canonical_count, 6)
        self.assertEqual(len(client.applied), 1)

    def test_ambiguous_trade_endpoint_never_partially_removes_the_other_endpoint(self):
        cases = [
            ("Raichu", "Pikachu", {"species:26": entry("caught"), "form:26:alolan": entry("caught"), "form:26:kanto": entry("caught")}),
            ("Pikachu", "Raichu", {"species:25": entry("caught"), "form:26:alolan": entry("caught"), "setting:forms": entry("on")}),
        ]
        for source, target, records in cases:
            with self.subTest(source=source, target=target):
                client = FakeClient(records)
                with self.assertRaises(ops.FormChoiceRequired):
                    ops.run_pair(client, "fixture-account", "trade", source, target, SPECIES)
                self.assertEqual(client.applied, [])
                self.assertEqual(client.records, records)

    def test_last_owned_regional_trade_infers_sole_source_and_downgrades_species_to_seen(self):
        client = FakeClient({"species:26": entry("caught"), "form:26:kanto": entry("caught")})
        result = ops.run_pair(client, "fixture-account", "trade", "Raichu", "Pikachu", SPECIES)
        self.assertEqual(result["changes"], {"species:26": "seen", "form:26:kanto": "seen", "species:25": "caught"})
        self.assertEqual(result["from_form"], "kanto")
        self.assertEqual(client.expected[0]["form:26:alolan"], "none")
        self.assertEqual(len(client.applied), 1)

    def test_exact_form_favorite_tokens_are_not_silently_normalized(self):
        for token in ["026:kanto", "26:Kanto", "26:kanto/extra", "25:alolan", "999:alolan"]:
            with self.subTest(token=token):
                client = FakeClient()
                with self.assertRaises(ops.OperationError):
                    ops.run_favorites_exact(client, "fixture-account", [], SPECIES, form_targets=[token])
                self.assertEqual(client.applied, [])

    def test_cli_exact_form_favorites_can_name_both_forms_without_a_party_limit(self):
        for names in [["Raichu"], []]:
            argv = ["--uid", "fixture-account", "--json", "favorites", "--exact", *names, "--forms", "26:alolan", "26:kanto"]
            _, unknown = ops.build_parser().parse_known_args(argv)
            self.assertEqual(unknown, [], "favorites CLI lacks explicit full-set form targets")
            client = FakeClient({"species:26": entry("caught"), "form:26:alolan": entry("caught"), "form:26:kanto": entry("caught")})
            output = io.StringIO()
            with mock_patch.object(ops, "FirebaseClient", return_value=client), redirect_stdout(output):
                code = ops.main(argv)
            self.assertEqual(code, 0, output.getvalue())
            self.assertEqual(json.loads(output.getvalue())["exact_forms"], ["26:alolan", "26:kanto"])
            self.assertEqual(client.records["species:26"]["s"], "caught")
            self.assertEqual(client.records["starform:26:alolan"]["s"], "on")
            self.assertEqual(client.records["starform:26:kanto"]["s"], "on")

    def test_exact_favorites_refuse_success_if_an_unrequested_favorite_arrives_during_the_write(self):
        class ConcurrentClient(FakeClient):
            def apply_records(self, uid, records, **kwargs):
                super().apply_records(uid, records, **kwargs)
                self.records["star:150"] = entry("on")
        client = ConcurrentClient()
        with self.assertRaises(ops.VerificationError):
            ops.run_favorites_exact(client, "fixture-account", ["Pikachu"], SPECIES)
        self.assertEqual(client.records["star:150"]["s"], "on")

    def test_explicit_form_favorite_set_can_select_one_unowned_form_without_touching_ownership(self):
        self.assertIn("form_targets", inspect.signature(ops.run_favorites_exact).parameters, "exact favorites lack typed form targets")
        client = FakeClient({"star:25": entry("on")})
        result = ops.run_favorites_exact(client, "fixture-account", [], SPECIES, form_targets=["26:kanto"])
        self.assertEqual(result["changes"], {"star:25": "off", "star:26": "on", "starform:26:kanto": "on"})
        self.assertEqual(result["exact_forms"], ["26:kanto"])
        self.assertFalse(any(key.startswith(("species:", "form:")) for key in client.applied[0]))

    def test_exact_favorites_do_not_guess_between_two_owned_regional_forms(self):
        client = FakeClient({"species:26": entry("caught"), "form:26:alolan": entry("caught"), "form:26:kanto": entry("caught"), "star:26": entry("on")})
        with self.assertRaises(ops.FormChoiceRequired):
            ops.run_favorites_exact(client, "fixture-account", ["Raichu"], SPECIES)
        self.assertEqual(client.applied, [])

    def test_exact_nonregional_favorites_also_clear_out_of_set_regional_form_flags(self):
        client = FakeClient({"star:26": entry("on"), "starform:26:alolan": entry("on"), "starform:26:kanto": entry("on"), "species:26": entry("caught")})
        result = ops.run_favorites_exact(client, "fixture-account", ["Pikachu"], SPECIES)
        self.assertEqual(result["changes"], {"star:26": "off", "starform:26:alolan": "off", "starform:26:kanto": "off", "star:25": "on"})
        self.assertEqual(client.records["species:26"]["s"], "caught")
        self.assertEqual(len(client.applied), 1)

    def test_cli_trade_exposes_exact_form_endpoints_and_form_status_readback(self):
        argv = ["--uid", "fixture-account", "--json", "trade", "Raichu", "Pikachu", "--from-form", "alolan"]
        _, unknown = ops.build_parser().parse_known_args(argv)
        self.assertEqual(unknown, [], "trade CLI must expose form endpoint arguments")
        client = FakeClient({"species:26": entry("caught"), "form:26:alolan": entry("caught"), "form:26:kanto": entry("caught"), "setting:forms": entry("on")})
        output = io.StringIO()
        with mock_patch.object(ops, "FirebaseClient", return_value=client), redirect_stdout(output):
            code = ops.main(argv)
        self.assertEqual(code, 0, output.getvalue())
        result = json.loads(output.getvalue())
        self.assertEqual(result["statuses"], {"Raichu (Alolan)": "seen", "Pikachu": "caught"})
        self.assertEqual(client.records["species:26"]["s"], "caught")
        self.assertEqual(len(client.applied), 1)

    def test_regional_trade_preserves_sibling_ownership_in_one_guarded_transaction(self):
        self.assertIn("from_form", inspect.signature(ops.run_pair).parameters, "paired writes lack explicit regional endpoints")
        client = FakeClient({"species:26": entry("caught"), "form:26:alolan": entry("caught"), "form:26:kanto": entry("caught"), "setting:forms": entry("on")})
        result = ops.run_pair(client, "fixture-account", "trade", "Raichu", "Pikachu", SPECIES, from_form="alolan")
        self.assertEqual(result["changes"], {"form:26:alolan": "seen", "species:25": "caught"})
        self.assertEqual(len(client.applied), 1)
        self.assertEqual(client.records["species:26"]["s"], "caught")
        self.assertEqual(client.records["form:26:kanto"]["s"], "caught")
        self.assertEqual(client.expected[0], {"species:26": "caught", "form:26:alolan": "caught", "form:26:kanto": "caught", "species:25": "none", "setting:forms": "on"})
        self.assertEqual(result["from_form"], "alolan")

    def test_cli_guarded_set_status_checks_the_form_instead_of_aggregate_ownership(self):
        argv = ["--uid", "fixture-account", "--json", "set-status", "Raichu", "caught", "--old-status", "none", "--form", "kanto"]
        _, unknown = ops.build_parser().parse_known_args(argv)
        self.assertEqual(unknown, [], "guarded setter CLI lacks the exact form argument")
        client = FakeClient({"species:26": entry("caught"), "form:26:alolan": entry("caught"), "setting:forms": entry("on")})
        output = io.StringIO()
        with mock_patch.object(ops, "FirebaseClient", return_value=client), redirect_stdout(output):
            code = ops.main(argv)
        self.assertEqual(code, 0, output.getvalue())
        self.assertEqual(json.loads(output.getvalue())["form"], "kanto")
        self.assertEqual(client.expected[0]["form:26:kanto"], "none")
        self.assertEqual(client.expected[0]["form:26:alolan"], "caught")
        self.assertEqual(client.records["form:26:alolan"]["s"], "caught")
        self.assertEqual(client.records["form:26:kanto"]["s"], "caught")

    def test_legacy_status_entrypoints_cannot_bypass_tracking_on_form_resolution(self):
        for method in ["set_pokemon_status", "_set_pokemon_status"]:
            with self.subTest(method=method):
                client = FakeClient({"species:26": entry("caught"), "form:26:alolan": entry("caught"), "setting:forms": entry("on")})
                tool = ops.PokemonStatusTool("fixture-account", client, SPECIES)
                with self.assertRaises(ops.FormChoiceRequired):
                    getattr(tool, method)("Raichu", "caught")
                self.assertEqual(client.applied, [])

    def test_cli_returns_structured_form_choices_without_writing(self):
        client = FakeClient({"setting:forms": entry("on")})
        output = io.StringIO()
        with mock_patch.object(ops, "FirebaseClient", return_value=client), redirect_stdout(output):
            code = ops.main(["--uid", "fixture-account", "--json", "mark", "Raichu", "caught"])
        payload = json.loads(output.getvalue())
        self.assertEqual(code, 1)
        self.assertEqual(payload.get("code"), "form_choice_required")
        self.assertEqual({row["form"] for row in payload["candidates"]}, {"alolan", "kanto"})
        self.assertEqual(client.applied, [])

    def test_cli_mark_accepts_and_applies_the_explicit_form(self):
        argv = ["--uid", "fixture-account", "--json", "mark", "Raichu", "caught", "--form", "kanto"]
        _, unknown = ops.build_parser().parse_known_args(argv)
        self.assertEqual(unknown, [], "CLI must expose an explicit form argument")
        client = FakeClient({"species:26": entry("caught"), "form:26:alolan": entry("caught"), "setting:forms": entry("on")})
        output = io.StringIO()
        with mock_patch.object(ops, "FirebaseClient", return_value=client), redirect_stdout(output):
            code = ops.main(argv)
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output.getvalue())["form"], "kanto")
        self.assertEqual(client.records["form:26:kanto"]["s"], "caught")
        self.assertEqual(client.records["form:26:alolan"]["s"], "caught")

    def test_explicit_mark_changes_only_the_named_form_and_preserves_owned_sibling(self):
        self.assertIn("form", inspect.signature(ops.run_mark).parameters, "mark lacks an explicit regional form argument")
        client = FakeClient({"species:26": entry("caught"), "form:26:alolan": entry("caught"), "form:26:kanto": entry("caught"), "setting:forms": entry("on")})
        result = ops.run_mark(client, "fixture-account", "Raichu", "seen", SPECIES, form="alolan")
        self.assertEqual(result["changes"], {"form:26:alolan": "seen"})
        self.assertEqual(client.records["species:26"]["s"], "caught")
        self.assertEqual(client.records["form:26:kanto"]["s"], "caught")
        self.assertEqual(result["form"], "alolan")

    def test_real_writer_style_absent_default_guards_verify_without_materializing_them(self):
        class MinimalClient(FakeClient):
            def apply_records(self, uid, records, **kwargs):
                changed = {key: value for key, value in records.items() if ops.record_value(self.records, key) != value}
                super().apply_records(uid, changed, **kwargs)
        client = MinimalClient()
        error = None
        try:
            result = ops.run_mark(client, "fixture-account", "Raichu", "caught", SPECIES)
        except ops.VerificationError as caught:
            error = caught
        self.assertIsNone(error, "absent None/Off guard records must verify by their documented defaults")
        self.assertTrue(result["verified"])
        self.assertEqual(set(client.records), {"species:26", "form:26:alolan"})

    def test_tracking_off_catch_updates_alolan_target_under_full_form_and_setting_guards(self):
        client = FakeClient({"species:26": entry("caught"), "form:26:kanto": entry("caught")})
        result = ops.run_mark(client, "fixture-account", "Raichu", "caught", SPECIES)
        self.assertEqual(result["changes"], {"form:26:alolan": "caught"})
        self.assertEqual(client.expected, [{"species:26": "caught", "form:26:alolan": "none", "form:26:kanto": "caught", "setting:forms": "off"}])
        self.assertEqual(client.applied, [{"species:26": "caught", "form:26:alolan": "caught", "form:26:kanto": "caught", "setting:forms": "off"}])
        self.assertTrue(result["verified"])

    def test_unspecified_regional_catch_requests_a_choice_without_writing(self):
        client = FakeClient({"setting:forms": entry("on"), "form:26:alolan": entry("caught"), "species:26": entry("caught")})
        error = None
        try:
            ops.run_mark(client, "fixture-account", "Raichu", "caught", SPECIES)
        except ops.OperationError as caught:
            error = caught
        self.assertIsNotNone(error, "tracking-on incoming catches must require an explicit form")
        self.assertEqual(getattr(error, "code", None), "form_choice_required")
        self.assertEqual({row["form"] for row in error.candidates}, {"alolan", "kanto"})
        self.assertEqual(client.applied, [])

    def test_resolution_rejects_unknown_form_tokens_without_normalizing_them(self):
        for explicit in ["ALOLAN", "future", "", 0]:
            with self.subTest(explicit=explicit), self.assertRaises(ops.OperationError):
                ops.choose_regional_form(explicit=explicit, tracking=True, owned=[], incoming=True)
        with self.assertRaises(ops.OperationError):
            ops.choose_regional_form(explicit=None, tracking=False, owned=["future"], incoming=False)

    def test_outgoing_resolution_infers_only_a_single_owned_form_even_when_tracking_is_off(self):
        for tracking in [False, True]:
            for owned, expected in [([], None), (["alolan"], "alolan"), (["kanto"], "kanto"), (["alolan", "kanto"], None)]:
                with self.subTest(tracking=tracking, owned=owned):
                    self.assertEqual(ops.choose_regional_form(explicit=None, tracking=tracking, owned=owned, incoming=False), expected)

    def test_incoming_resolution_respects_tracking_and_never_uses_existing_ownership(self):
        resolver = getattr(ops, "choose_regional_form", None)
        self.assertTrue(callable(resolver), "shared regional form resolver is missing")
        assert callable(resolver)
        for owned in [[], ["alolan"], ["kanto"], ["alolan", "kanto"]]:
            with self.subTest(owned=owned):
                self.assertIsNone(resolver(explicit=None, tracking=True, owned=owned, incoming=True))
                self.assertEqual(resolver(explicit=None, tracking=False, owned=owned, incoming=True), "alolan")
        self.assertEqual(resolver(explicit="kanto", tracking=False, owned=[], incoming=True), "kanto")


if __name__ == "__main__":
    unittest.main()
