"""Regressions for the retained creator guide's SOS scope and footnotes.

The canonical encounter JSON is a manual transcription, not generated output
(see extract_reference.py). Never fill a missing caller or ally rate from stock.
"""

import json
from pathlib import Path
import unittest

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[2]


class SosSourceScopeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.guide = PdfReader(ROOT / "references" / "Wild Pokemon Locations.pdf")

    def setUp(self):
        self.data = json.loads((ROOT / "data" / "encounters.json").read_text())

    def location(self, location_id):
        return next(
            loc
            for island in self.data["islands"]
            for loc in island["locations"]
            if loc["id"] == location_id
        )

    def test_ulaula_floette_colors_keep_the_red_caller_and_two_sos_only_colors(self):
        source = " ".join(self.guide.pages[50].extract_text().split())
        self.assertIn("Floette found here will have red flowers", source)
        self.assertIn("can call Floette with orange and white flowers", source)
        loc = self.location("ulaula-island/ulaula-meadow")
        row = next(r for g in loc["groups"] for r in g["encounters"] if r.get("speciesId") == 670)
        self.assertEqual(row.get("form"), "red-flower")
        self.assertEqual(row["forms"], ["red-flower"])
        self.assertEqual(row["rates"], {"single": 20})
        self.assertEqual({a.get("form") for a in row["allies"]}, {"orange-flower", "white-flower"})
        self.assertTrue(all(a["speciesId"] == 670 and "rates" not in a for a in row["allies"]))

    def test_rotom_appliances_are_distinct_documented_allies_not_extra_wild_forms(self):
        source = " ".join(self.guide.pages[48].extract_text().split())
        self.assertIn("Rotom can call its Fridge and Heat forms via SOS", source)
        loc = self.location("ulaula-island/thrifty-megamart")
        row = next(r for g in loc["groups"] for r in g["encounters"] if r.get("speciesId") == 479)
        self.assertEqual(row.get("form"), "base")
        self.assertEqual(row["forms"], ["base"])
        self.assertEqual(row["rates"], {"single": 15})
        self.assertEqual({a.get("form") for a in row["allies"]}, {"frost", "heat"})
        self.assertTrue(all(a["speciesId"] == 479 and "rates" not in a for a in row["allies"]))

    def test_deerling_seasons_preserve_pooled_wild_rates_and_sos_only_identity(self):
        source = " ".join(self.guide.pages[24].extract_text().split())
        self.assertIn("Autumn and Winter can only be found by SOS chaining the Spring and Summer forms", source)
        loc = self.location("akala-island/route-6")
        wild = [r for g in loc["groups"] if g["category"] == "regular" for r in g["encounters"] if r.get("speciesId") == 585]
        self.assertEqual(len(wild), 2)
        for row in wild:
            self.assertEqual(row["speciesName"], "Deerling (Spring / Summer)")
            self.assertEqual(row["forms"], ["spring", "summer"])
            self.assertEqual(row["rates"], {"single": 15})
            self.assertIn("does not assign", row["note"])
        calls = next(g for g in loc["groups"] if g["name"] == "SOS Calls")
        caller = next(r for r in calls["encounters"] if r["speciesId"] == 585)
        self.assertEqual(caller["speciesName"], "Deerling (Spring / Summer)")
        self.assertIsNone(caller["rates"])
        self.assertEqual({a.get("form") for a in caller["allies"]}, {"autumn", "winter"})
        self.assertTrue(all(a["speciesId"] == 585 and "rates" not in a for a in caller["allies"]))
        self.assertIn("order", caller["note"])

    def test_sand_castform_keeps_its_own_documented_condition_and_rate(self):
        source = " ".join(self.guide.pages[52].extract_text().split())
        self.assertIn("1% chance of encountering Castform in a Sandstorm", source)
        loc = self.location("ulaula-island/haina-desert")
        weather = next(g for g in loc["groups"] if g["name"] == "Weather SOS")
        castform = [r for r in weather["encounters"] if r["speciesId"] == 351]
        sand = [r for r in castform if r.get("conditions") == ["Sandstorm"]]
        self.assertEqual(len(sand), 1, "p53 sandstorm footnote must be a distinct rate row")
        self.assertEqual(sand[0]["rates"], {"single": 1})
        self.assertIn("guide-reported", sand[0]["note"].lower())
        rain_hail = [r for r in castform if r.get("conditions") == ["Rain, Hail"]]
        self.assertEqual(len(rain_hail), 1)
        self.assertEqual(rain_hail[0]["rates"], {"single": 11})


    def test_route_one_shared_table_attaches_callers_to_their_native_area(self):
        # p4 has both Route 1 and its Outskirts; the p5 SOS table covers both.
        page4 = " ".join(self.guide.pages[3].extract_text().split()).replace("’", "'")
        proper, outskirts = page4.split("Hau'oli Outskirts", 1)
        self.assertIn("Rattata", proper)
        self.assertIn("Pichu", proper)
        self.assertNotIn("Rattata", outskirts)
        self.assertNotIn("Pichu", outskirts)
        page5 = " ".join(self.guide.pages[4].extract_text().split())
        self.assertIn("Rattata Rattata", page5)
        self.assertIn("Pichu Pikachu Happiny", page5)

        loc = self.location("melemele-island/route-1")
        calls = [g for g in loc["groups"] if g["name"] == "SOS Calls"]
        self.assertEqual(len(calls), 1, "shared table callers belong with Route 1 wild rows")
        self.assertEqual(calls[0]["sourcePage"], 5)
        self.assertIn(5, loc["sourcePages"])
        rows = {r["speciesId"]: r for r in calls[0]["encounters"]}
        self.assertEqual(set(rows), {19, 172})
        self.assertEqual(rows[19]["form"], "alolan")
        self.assertEqual([(a["speciesId"], a.get("form")) for a in rows[19]["allies"]], [(19, "kanto")])
        self.assertEqual([a["speciesId"] for a in rows[172]["allies"]], [25, 440])
        self.assertTrue(all(r["rates"] is None for r in rows.values()))
        old_location = self.location("melemele-island/hauoli-outskirts")
        old_calls = next(g for g in old_location["groups"] if g["name"] == "SOS Calls")
        self.assertTrue({19, 172}.isdisjoint(r["speciesId"] for r in old_calls["encounters"]))


    def test_unlisted_crabrawler_caller_stays_explicitly_unverified(self):
        source = " ".join(self.guide.pages[49].extract_text().split())
        self.assertIn("Shuckle 100", source)
        self.assertIn("Crabrawler Crabominable", source)
        loc = self.location("ulaula-island/route-15-16")
        berries = next(g for g in loc["groups"] if g["name"] == "Berry Piles")
        self.assertEqual([(r["speciesId"], r["rates"]) for r in berries["encounters"]], [(213, {"single": 100})])
        calls = next(g for g in loc["groups"] if g["name"] == "SOS Calls")
        caller = next(r for r in calls["encounters"] if r["speciesId"] == 739)
        self.assertEqual([a["speciesId"] for a in caller["allies"]], [740])
        self.assertIsNone(caller["rates"])
        self.assertIn("unverified", caller.get("note", "").lower())
        self.assertIn("Shuckle", caller["note"])


if __name__ == "__main__":
    unittest.main()
