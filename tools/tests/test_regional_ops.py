"""Regional operations use synthetic records and never contact Firebase."""
import unittest

from test_pokemon_ops import FakeClient, SPECIES, entry, ops


class RegionalResolutionTests(unittest.TestCase):
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
