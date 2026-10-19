"""Evolution projection uses synthetic source text; it never touches player state."""
import importlib
import importlib.util
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

SOURCE = '''
\tspheal: {num: 363, species: "Spheal"},
\tsealeo: {num: 364, species: "Sealeo", prevo: "spheal", evoLevel: 32},
\twalrein: {num: 365, species: "Walrein", prevo: "sealeo", evoLevel: 44},
\tmeowth: {num: 52, species: "Meowth"},
\tpersian: {num: 53, species: "Persian", prevo: "meowth", evoLevel: 28},
\tmeowthalola: {num: 52, species: "Meowth-Alola", baseSpecies: "Meowth", forme: "Alola"},
\tpersianalola: {num: 53, species: "Persian-Alola", baseSpecies: "Persian", forme: "Alola", prevo: "meowthalola", evoType: "levelFriendship"},
'''
CATALOGUE = [{"id": dex, "name": name, "slug": name.lower()} for dex, name in [(52, "Meowth"), (53, "Persian"), (363, "Spheal"), (364, "Sealeo"), (365, "Walrein")]]
FORMS = {f"{dex}:{form}": {"id": dex, "form": form, "name": f"{name} ({form.title()})", "showdownKey": slug + ("alola" if form == "alolan" else "")} for dex, name, slug in [(52, "Meowth", "meowth"), (53, "Persian", "persian")] for form in ["alolan", "kanto"]}


class EvolutionDataTests(unittest.TestCase):
    def test_alolan_raticate_requires_night_and_does_not_duplicate_an_existing_condition(self):
        builder = importlib.import_module("evolution_data")
        pokemon = [{"id": 19, "name": "Rattata", "slug": "rattata"}, {"id": 20, "name": "Raticate", "slug": "raticate"}]
        forms = {f"{dex}:{form}": {"id": dex, "form": form, "name": f"{name} ({form})", "showdownKey": name.lower() + ("alola" if form == "alolan" else "")} for dex, name in [(19, "Rattata"), (20, "Raticate")] for form in ["alolan", "kanto"]}
        source = '\n\trattata: {num: 19},\n\traticate: {num: 20, prevo: "rattata", evoLevel: 20},\n\trattataalola: {num: 19},\n\traticatealola: {num: 20, prevo: "rattataalola", evoLevel: 20},'
        for override in ["", '\n\traticatealola: {inherit: true, evoCondition: "at night"},']:
            edges = {e["to"]: e for e in builder.build_graph(source, override, pokemon, forms)["edges"]}
            self.assertEqual(edges["20:alolan"]["stock"], "Level 20 at night")
            self.assertEqual(edges["20:kanto"]["stock"], "Level 20")

    def test_default_form_specific_standard_method_is_used_before_generic_fallback(self):
        builder = importlib.import_module("evolution_data")
        source = SOURCE.replace('species: "Sealeo",', 'species: "Sealeo", baseForme: "Default",')
        graph = builder.build_graph(source, "", CATALOGUE, FORMS, standard_methods={("Spheal", "Sealeo-Default"): "Specific fixture method", ("Spheal", "Sealeo"): "Generic fixture method"})
        self.assertEqual(graph["edges"][0]["prismatic"], "Specific fixture method")

    def test_prismatic_methods_are_separate_from_stock_rules_and_do_not_leak_to_other_edges(self):
        import inspect
        builder = importlib.import_module("evolution_data")
        self.assertIn("standard_methods", inspect.signature(builder.build_graph).parameters)
        graph = builder.build_graph(SOURCE, "", CATALOGUE, FORMS, standard_methods={("Spheal", "Sealeo"): "Fixture Standard method"})
        self.assertEqual(graph["edges"][0], {"from": "363", "to": "364", "stock": "Level 32", "prismatic": "Fixture Standard method"})
        self.assertNotIn("prismatic", graph["edges"][1])
        self.assertNotIn("prismatic", graph["edges"][2])

    def test_shared_predecessor_regional_evolutions_keep_game_location_and_night_restrictions(self):
        builder = importlib.import_module("evolution_data")
        pokemon, forms, blocks = [], {}, []
        for parent_id, parent, child_id, child, attributes in [(25, "Pikachu", 26, "Raichu", 'evoType: "useItem", evoItem: "Thunder Stone"'), (102, "Exeggcute", 103, "Exeggutor", 'evoType: "useItem", evoItem: "Leaf Stone"'), (104, "Cubone", 105, "Marowak", 'evoLevel: 28')]:
            pokemon.extend([{"id": parent_id, "name": parent, "slug": parent.lower()}, {"id": child_id, "name": child, "slug": child.lower()}])
            blocks.append(f'\n\t{parent.lower()}: {{num: {parent_id}, species: "{parent}"}},')
            for form, suffix in [("kanto", ""), ("alolan", "alola")]:
                key = child.lower() + suffix
                blocks.append(f'\n\t{key}: {{num: {child_id}, species: "{child}", prevo: "{parent.lower()}", {attributes}}},')
                forms[f"{child_id}:{form}"] = {"id": child_id, "form": form, "name": f"{child} ({form.title()})", "showdownKey": key}
        edges = {edge["to"]: edge for edge in builder.build_graph("".join(blocks), "", pokemon, forms)["edges"]}
        for dex in [26, 103, 105]:
            restrictions = edges[f"{dex}:kanto"].get("conditions", {})
            self.assertIn("Ultra Space", restrictions.get("ultra-moon", ""))
            self.assertIn("trade", restrictions.get("sun", "").lower())
            self.assertIn("unverified", restrictions.get("photonic-prismatic", "").lower())
            self.assertIn("Alola", edges[f"{dex}:alolan"].get("conditions", {}).get("ultra-moon", ""))
        self.assertEqual(edges["105:alolan"]["stock"], "Level 28 at night")
        self.assertEqual(edges["105:kanto"]["stock"], "Level 28")

    def test_graph_preserves_stock_item_trade_and_extra_conditions(self):
        builder = importlib.import_module("evolution_data")
        for attributes, expected in [
            ('evoType: "useItem", evoItem: "Moon Stone"', "Use Moon Stone"),
            ('evoType: "trade", evoItem: "Metal Coat"', "Trade holding Metal Coat"),
            ('evoType: "trade"', "Trade"),
            ('evoType: "levelHold", evoItem: "Razor Claw", evoCondition: "at night"', "Level up holding Razor Claw at night"),
            ('evoType: "levelMove", evoMove: "Ancient Power"', "Level up knowing Ancient Power"),
            ('evoType: "levelExtra", evoLevel: 33, evoCondition: "if female"', "Level 33 if female"),
            ('evoType: "levelExtra", evoCondition: "near a Moss Rock"', "Level up near a Moss Rock"),
        ]:
            with self.subTest(attributes=attributes):
                source = SOURCE.replace("evoLevel: 32", attributes)
                graph = builder.build_graph(source, "", CATALOGUE, FORMS)
                self.assertEqual(graph["edges"][0]["stock"], expected)

    def test_graph_contains_each_stage_and_keeps_regional_branches_separate(self):
        self.assertIsNotNone(importlib.util.find_spec("evolution_data"), "form-aware evolution graph builder is missing")
        builder = importlib.import_module("evolution_data")
        graph = builder.build_graph(SOURCE, "", CATALOGUE, FORMS)
        self.assertEqual(set(graph["nodes"]), {"363", "364", "365", "52:alolan", "52:kanto", "53:alolan", "53:kanto"})
        self.assertEqual(graph["edges"], [
            {"from": "363", "to": "364", "stock": "Level 32"},
            {"from": "364", "to": "365", "stock": "Level 44"},
            {"from": "52:alolan", "to": "53:alolan", "stock": "Level up with high friendship"},
            {"from": "52:kanto", "to": "53:kanto", "stock": "Level 28"},
        ])
        self.assertFalse(any(edge["from"] == "52:alolan" and edge["to"] == "53:kanto" for edge in graph["edges"]))


if __name__ == "__main__":
    unittest.main()
