"""Creator footnotes have a caller scope, not every row in the source table."""
import json
from pathlib import Path
import unittest
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[2]

class SosNoteScopeTests(unittest.TestCase):
    def test_canyon_notes_are_scoped_without_losing_creator_evidence(self):
        data = json.loads((ROOT / "data/encounters.json").read_text())
        canyon = next(location for island in data["islands"] for location in island["locations"]
                      if location["id"] == "poni-island/vast-poni-canyon")
        sos = next(group for group in canyon["groups"] if group["name"] == "SOS Calls")
        text = " ".join(PdfReader(ROOT / "references/Wild Pokemon Locations.pdf").pages[61].extract_text().split())
        self.assertIn("Diancie and Sableye will only be called by Carbink encountered in caves", text)
        self.assertIn("Dragonair encountered in a bubbling spot", text)
        self.assertEqual(sos.get("notes", []), [])
        for row in sos["encounters"]:
            if row["speciesId"] == 703:
                self.assertIn("only called by Carbink encountered in caves", row["note"])
                self.assertNotIn("Lycanroc", row["note"])
                self.assertNotIn("Dragonair", row["note"])
            elif row["speciesId"] == 148:
                self.assertIn("bubbling spot", row["note"])
                self.assertNotIn("Carbink", row["note"])
            else:
                self.assertNotIn("note", row)
        for group in canyon["groups"]:
            for row in group["encounters"]:
                if row.get("speciesId") == 745:
                    self.assertIn("small chance to call Lycanroc-Dusk", row["note"])
