"""Conditional Own Tempo source identity is not a shared ally on a pooled caller."""
import json
from pathlib import Path
import unittest
from pypdf import PdfReader
from tools.validate_data import validate_inputs

ROOT = Path(__file__).resolve().parents[2]
EXPECTED = {"species": "rockruff", "name": "Rockruff", "speciesId": 744,
            "form": "own-tempo", "callerForm": "own-tempo"}

class ConditionalSosTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((ROOT / "data/encounters.json").read_text())
        self.pokemon = json.loads((ROOT / "data/pokemon.json").read_text())
        self.row = next(row for island in self.data["islands"] for location in island["locations"]
                        for group in location["groups"] for row in group["encounters"]
                        if row["id"] == "melemele-island/ten-carat-hill/grass-2/1")

    def test_creator_own_tempo_call_is_explicitly_conditional(self):
        text = " ".join(PdfReader(ROOT / "references/Wild Pokemon Locations.pdf").pages[15].extract_text().split())
        self.assertIn("Own Tempo will only summon other Own Tempo Rockruff", text)
        self.assertIn("called by regular Rockruff", text)
        self.assertEqual(self.row.get("conditionalAllies"), [EXPECTED])
        self.assertEqual(self.row["allies"], [])
        self.assertEqual(self.row["rates"], {"single": 20})
        self.assertEqual(self.row["forms"], ["normal", "own-tempo"])

    def test_invalid_conditional_callers_fail_closed(self):
        invalid = [None, {}, [], [None], [{**EXPECTED, "callerForm": None}],
                   [{**EXPECTED, "callerForm": ""}], [{**EXPECTED, "callerForm": "winter"}],
                   [{**EXPECTED, "callerForm": []}], [{**EXPECTED, "species": "unknown"}]]
        for value in invalid:
            with self.subTest(value=value):
                self.row["conditionalAllies"] = value
                self.assertTrue(any("conditional" in error for error in validate_inputs(self.pokemon, self.data)))
        self.row["conditionalAllies"] = [EXPECTED]
        self.assertFalse(any("conditional" in error for error in validate_inputs(self.pokemon, self.data)))
