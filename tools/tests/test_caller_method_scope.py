"""Source-only method predicates must not create player state or guessed rates."""
import json
from pathlib import Path
import unittest
from pypdf import PdfReader
from tools.validate_data import validate_inputs
ROOT=Path(__file__).resolve().parents[2]
class CallerMethodScopeTests(unittest.TestCase):
 def setUp(self):
  self.data=json.loads((ROOT/"data/encounters.json").read_text())
  self.pokemon=json.loads((ROOT/"data/pokemon.json").read_text())
  self.canyon=next(l for i in self.data["islands"] for l in i["locations"] if l["id"]=="poni-island/vast-poni-canyon")
  self.rules=[r for g in self.canyon["groups"] if g["name"]=="SOS Calls" for r in g["encounters"] if r.get("speciesId")==703]

 def test_invalid_caller_group_scopes_are_rejected_not_silently_ignored(self):
  for value in ["cave",[],["unknown"],["poni-island/vast-poni-canyon/cave-3"]*2,["poni-island/vast-poni-canyon/sos-calls-8"],[None],[{}],["melemele-island/route-1/grass-1-1"]]:
   with self.subTest(value=value):
    self.rules[0]["callerGroups"]=value
    self.assertTrue(any("invalid callerGroups" in e for e in validate_inputs(self.pokemon,self.data)))
  self.rules[0]["callerGroups"]=["poni-island/vast-poni-canyon/cave-3"]
  self.assertFalse(any("invalid callerGroups" in e for e in validate_inputs(self.pokemon,self.data)))

 def test_creator_canyon_cave_only_predicate_is_structured_without_changed_rates(self):
  text=" ".join(PdfReader(ROOT/"references/Wild Pokemon Locations.pdf").pages[61].extract_text().split())
  self.assertIn("Diancie and Sableye will only be called by Carbink encountered in caves",text)
  groups=["poni-island/vast-poni-canyon/cave-3","poni-island/vast-poni-canyon/caves-with-water-4"]
  self.assertEqual(len(self.rules),2)
  for rule in self.rules:
   self.assertEqual(rule.get("callerGroups"),groups)
   self.assertIsNone(rule["rates"])
   self.assertTrue(all("rates" not in a for a in rule["allies"]))
  self.assertEqual([r["rates"] for g in self.canyon["groups"] if g["category"]=="regular" for r in g["encounters"] if r.get("speciesId")==703],[{"single":10},{"single":10},{"single":20},{"single":20}])
