"""Stock SOS generator integration; synthetic encounter input, no network/player I/O."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import build_vanilla_encounters as builder


def pokemon(key, dex, form=None):
    row = {"id": key, "speciesId": dex, "speciesName": str(dex), "rates": {"single": 25}, "allies": []}
    if form:
        row["form"] = form
    return row


def group(key, rows, method="walk", area="south"):
    return {"id": key, "name": "SOS allies" if method == "sos" else "Grass", "category": "return-later" if method == "sos" else "regular",
            "levels": {"min": 10, "max": 13}, "encounterType": "sos" if method == "sos" else "wild",
            "sourceArea": {"location": "alola-route-1", "area": area, "method": method},
            "conditions": [], "notes": [], "encounters": rows}


def dataset(groups, game="sun", name="Route 1"):
    # Keep synthetic source place IDs consistent, preserving explicit alias-test IDs.
    for item in groups:
        if item["sourceArea"]["location"] == "alola-route-1" and name != "Route 1":
            item["sourceArea"]["location"] = name.lower().replace(" ", "-")
    return {"schemaVersion": 1, "mode": game, "source": {}, "documentNotes": [], "assets": [],
            "islands": [{"id": "island", "locations": [{"id": "location", "name": name, "order": 1, "groups": groups}]}]}


def generated(data):
    """Exercise the real CLI post-generation/write boundary with controlled source acquisition."""
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "data").mkdir()
        game = data["mode"]
        with patch.object(builder, "ROOT", root), patch.object(builder, "load_csv_sources", return_value={}), \
             patch.object(builder, "load_table", return_value=""), \
             patch.object(builder, "generate", return_value=(copy.deepcopy(data), [], 1, 1)), \
             patch.object(builder, "validate_generated"), patch("sys.argv", ["builder", "--game", game]):
            assert builder.main() == 0
        return json.loads((root / "data" / f"encounters-{game}.json").read_text())


class StockSosTests(unittest.TestCase):
    def test_poni_rustling_normalization_preserves_the_original_center_sos_context(self):
        for area, method, allowed in [("center-rustling-bush", "bubbling-spots", True),
                                      ("east", "bubbling-spots", False), ("center-rustling-bush", "surf", False)]:
            with self.subTest(area=area, method=method):
                native = group("native", [pokemon("chansey", 113)], method, area)
                ally = group("sos", [pokemon("blissey", 242)], "sos", "center")
                ally["sourceArea"]["method"] = "sos-from-bubbling-spot"
                for item in [native, ally]:
                    item["sourceArea"]["location"] = "poni-plains"
                rules = generated(dataset([native, ally], "ultra-moon", "Poni Plains"))["islands"][0]["locations"][0]["groups"][1]["encounters"][0]["sosRules"]
                self.assertEqual(bool(rules), allowed)

    def test_stock_source_locations_take_precedence_over_reused_hack_display_aliases(self):
        cases = [("Victory Road", "mount-lanakila", 361, 362, "sun"),
                 ("Lush Jungle Cave", "lush-jungle", 42, 169, "ultra-moon"),
                 ("Route 15 / 16", "alola-route-15", 456, 457, "ultra-moon")]
        for display, slug, caller, ally, game in cases:
            with self.subTest(display=display):
                groups = [group("wild", [pokemon("caller", caller)]), group("sos", [pokemon("ally", ally)], "sos")]
                for item in groups:
                    item["sourceArea"]["location"] = slug
                rules = generated(dataset(groups, game, display))["islands"][0]["locations"][0]["groups"][1]["encounters"][0]["sosRules"]
                self.assertEqual([rule["callerIds"] for rule in rules], [["caller"]])

    def test_weather_time_game_and_subarea_predicates_keep_their_source_boundaries(self):
        cases = [("Malie Garden", "ultra-moon", "south", 62, {"night": 25, "day": 0}, False),
                 ("Malie Garden", "ultra-moon", "south", 62, {"night": 0, "day": 25}, True),
                 ("Mount Lanakila", "sun", "base", 582, {"single": 25}, False),
                 ("Mount Lanakila", "ultra-moon", "base", 582, {"single": 25}, True),
                 ("Mount Lanakila", "ultra-moon", "mountain", 584, {"single": 25}, True),
                 ("Mount Lanakila", "ultra-moon", "base", 584, {"single": 25}, False),
                 ("Mount Lanakila", "ultra-moon", "cave", 584, {"single": 25}, False)]
        for place, game, area, dex, rates, allowed in cases:
            with self.subTest(place=place, game=game, area=area, dex=dex):
                caller = pokemon("caller", 361)
                caller["rates"] = rates
                source = dataset([group("wild", [caller], "walk", area), group("sos", [pokemon("ally", dex)], "sos", area)], game, place)
                rules = generated(source)["islands"][0]["locations"][0]["groups"][1]["encounters"][0]["sosRules"]
                self.assertEqual(bool(rules), allowed)
                if allowed:
                    self.assertTrue(all(rule["kind"] == "weather-sos" and rule["rates"]["single"] in {1, 10} for rule in rules))

    def test_source_method_cave_and_time_qualifiers_are_applied_without_losing_partial_notes(self):
        cases = [(320, 321, "Route 13", "surf", "south", {"single": 25}, False),
                 (320, 321, "Route 13", "super-rod", "south", {"single": 25}, True),
                 (703, 302, "Ten Carat Hill", "walk", "cave", {"single": 25}, True),
                 (703, 302, "Ten Carat Hill", "walk", "farthest-hollow", {"single": 25}, False),
                 (133, 196, "Route 4", "walk", "south", {"day": 25, "night": 0}, True),
                 (133, 196, "Route 4", "walk", "south", {"day": 0, "night": 25}, False),
                 (559, 22, "Route 17", "walk", "south", {"day": 0, "night": 25}, True)]
        for caller, ally, place, method, area, rates, allowed in cases:
            with self.subTest(caller=caller, method=method, area=area, rates=rates):
                native = group("wild", [pokemon("caller", caller)], method, area)
                native["encounters"][0]["rates"] = rates
                source = dataset([native, group("sos", [pokemon("ally", ally)], "sos", area)], "ultra-moon", place)
                rules = generated(source)["islands"][0]["locations"][0]["groups"][1]["encounters"][0]["sosRules"]
                self.assertEqual(bool(rules), allowed)
                if caller == 559:
                    self.assertIn("Some encounters on Route 17 at night", rules[0]["conditions"])

    def test_unresolved_special_predicate_cannot_fall_through_to_a_same_species_guess(self):
        # The admitted USUM Charjabug daytime exception replaces its ordinary
        # partners. Until that predicate is resolved, do not guess a self call.
        source = dataset([group("wild", [pokemon("charjabug", 737)]),
                          group("sos", [pokemon("ally", 737)], "sos")], "ultra-moon")
        rules = generated(source)["islands"][0]["locations"][0]["groups"][1]["encounters"][0]["sosRules"]
        self.assertEqual(rules, [])

    def test_weather_rates_are_attached_to_capable_documented_callers_not_borrowed_from_wild_rates(self):
        groups = [group("wild", [pokemon("dugtrio", 51, "alolan"), pokemon("snorlax", 143)]),
                  group("sos", [pokemon("gabite", 444), pokemon("castform", 351)], "sos")]
        for item in groups:
            item["sourceArea"]["location"] = "haina-desert"
        rows = generated(dataset(groups, "ultra-moon", "Haina Desert"))["islands"][0]["locations"][0]["groups"][1]["encounters"]
        rules = rows[0]["sosRules"]
        self.assertEqual(len(rules), 1)
        self.assertEqual(rules[0]["kind"], "weather-sos")
        self.assertEqual(rules[0]["callerIds"], ["dugtrio"])
        self.assertEqual(rules[0]["rates"], {"single": 10})
        self.assertIn("During sandstorm", rules[0]["conditions"])
        self.assertEqual(sorted(rule["rates"]["single"] for rule in rows[1]["sosRules"]), [1, 11, 11])

    def test_no_call_game_form_and_battle_context_exceptions_override_the_default(self):
        cases = [(143, None, "sun", [], False), (550, "blue-striped", "ultra-moon", [], False),
                 (670, "blue-flower", "ultra-moon", [], False), (113, None, "sun", [], False),
                 (113, None, "ultra-moon", [], True), (796, None, "sun", ["Postgame Ultra Beast encounter."], False)]
        for dex, form, game, conditions, allowed in cases:
            with self.subTest(dex=dex, game=game):
                wild = group("wild", [pokemon("caller", dex, form)])
                wild["conditions"] = conditions
                source = dataset([wild, group("sos", [pokemon("ally", dex, form)], "sos")], game)
                rules = generated(source)["islands"][0]["locations"][0]["groups"][1]["encounters"][0]["sosRules"]
                self.assertEqual(bool(rules), allowed)

    def test_generator_uses_the_documented_same_species_default_without_copying_a_wild_percentage(self):
        source = dataset([group("wild", [pokemon("pikipek", 731)]), group("sos", [pokemon("ally", 731)], "sos")])
        target = generated(source)["islands"][0]["locations"][0]["groups"][1]["encounters"][0]
        self.assertEqual(target.get("sosRules"), [{"kind": "sos", "callerIds": ["pikipek"]}])

    def test_generator_maps_route_one_metapod_to_caterpie_without_replacing_source_rows(self):
        source = dataset([group("wild", [pokemon("metapod", 11), pokemon("munchlax", 446)]),
                          group("sos", [pokemon("caterpie", 10), pokemon("snorlax", 143)], "sos")])
        result = generated(source)
        rows = result["islands"][0]["locations"][0]["groups"][1]["encounters"]
        self.assertTrue(rows[0].get("sosRules"), "generator did not attach documented stock caller metadata")
        self.assertEqual(rows[0]["sosRules"][0]["callerIds"], ["metapod"])
        self.assertEqual(rows[1]["sosRules"][0]["callerIds"], ["munchlax"])
        for before, after in zip(source["islands"][0]["locations"][0]["groups"][1]["encounters"], rows):
            self.assertEqual({key: value for key, value in after.items() if key != "sosRules"}, before)
        self.assertEqual(result["islands"][0]["locations"][0]["groups"][0], source["islands"][0]["locations"][0]["groups"][0])


if __name__ == "__main__":
    unittest.main()
