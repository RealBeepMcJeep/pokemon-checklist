"""SOS leaf metadata fails closed before a published build consumes it."""
import copy
import json
from pathlib import Path
import unittest
from tools.validate_data import validate_inputs

ROOT = Path(__file__).resolve().parents[2]


class StockSosValidationTests(unittest.TestCase):
    def setUp(self):
        self.pokemon = json.loads((ROOT / "data/pokemon.json").read_text())
        self.data = json.loads((ROOT / "data/encounters-sun.json").read_text())
        self.location = next(l for i in self.data["islands"] for l in i["locations"] if l["name"] == "Route 1")
        self.group = next(g for g in self.location["groups"] if any(r.get("sosRules") for r in g["encounters"]))
        self.leaf = next(r for r in self.group["encounters"] if r.get("sosRules"))
        self.original = copy.deepcopy(self.leaf["sosRules"])
        self.assertEqual(self.errors(), [], "the actual stock fixture must be admitted first")

    def errors(self):
        return validate_inputs(self.pokemon, self.data, expected_locations=57, require_grass_maps=False, expected_mode="sun")

    def test_malformed_leaf_rules_fail_closed_without_crashing(self):
        caller = self.original[0]["callerIds"][0]
        foreign = next(r["id"] for i in self.data["islands"] for l in i["locations"] if l is not self.location for g in l["groups"] for r in g["encounters"])
        invalid = [None, {}, "sos", [None], [{}], [{"kind": "wrong", "callerIds": [caller]}],
                   [{"kind": "sos", "callerIds": []}], [{"kind": "sos", "callerIds": caller}],
                   [{"kind": "sos", "callerIds": [caller, caller]}], [{"kind": "sos", "callerIds": [{}]}],
                   [{"kind": "sos", "callerIds": [foreign]}], [{"kind": "sos", "callerIds": ["missing"]}],
                   [{"kind": "sos", "callerIds": [caller], "rates": {"single": 15}}],
                   [{"kind": "sos", "callerIds": [caller], "conditions": "rain"}],
                   [{"kind": "sos", "callerIds": [caller], "conditions": [""]}],
                   [{"kind": "sos", "callerIds": [caller], "conditions": [None]}],
                   [{"kind": "sos", "callerIds": [caller], "weight": 50}],
                   [{"kind": "weather-sos", "callerIds": [caller], "rates": {"single": True}}],
                   [{"kind": "weather-sos", "callerIds": [caller], "rates": {"single": 101}}],
                   [{"kind": "weather-sos", "callerIds": [caller], "rates": {"turn": 11}}],
                   [{"kind": "weather-sos", "callerIds": [caller], "rates": {}}]]
        invalid.extend([[{"kind": kind, "callerIds": [caller]}] for kind in [None, [], {}, True]])
        for rules in invalid:
            with self.subTest(rules=rules):
                self.leaf["sosRules"] = rules
                self.assertTrue(any("invalid sosRules" in e for e in self.errors()))

    def test_empty_unavailable_rules_and_exact_weather_or_chained_refs_are_valid(self):
        caller = self.original[0]["callerIds"][0]
        for rules in [[], [{"kind": "weather-sos", "callerIds": [caller], "conditions": ["During rain"], "rates": {"single": 11}}],
                      [{"kind": "sos", "callerIds": [self.leaf["id"]]}]]:
            with self.subTest(rules=rules):
                self.leaf["sosRules"] = rules
                self.assertEqual(self.errors(), [])

    def test_leaf_metadata_cannot_be_attached_to_a_native_wild_row(self):
        native = next(r for g in self.location["groups"] if g["encounterType"] == "wild" for r in g["encounters"])
        native["sosRules"] = self.original
        self.assertTrue(any("invalid sosRules" in e for e in self.errors()))
