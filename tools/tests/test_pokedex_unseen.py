"""Unseen-only Pokédex gains; no live account or personal data in fixtures."""
import copy
import sys
import os
from unittest import mock
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import team_options as opt


def torchic():
    return {"final": "Blaziken", "endpoint_id": 257,
            "caught_ids": [255], "caught_as": ["Torchic"],
            "evolution_path": [
                {"id": 255, "name": "Torchic", "status": "caught"},
                {"id": 256, "name": "Combusken", "method": "Level 16", "status": "seen"},
                {"id": 257, "name": "Blaziken", "method": "Level 36", "status": "none"}]}


class PokedexUnseenTests(unittest.TestCase):
    def test_report_exposes_only_actual_seen_species_ids_in_sorted_order(self):
        roster = {"caught_count": 1, "canonical_count": 1, "records": {
            "species:257": {"s": "seen"}, "species:256": {"s": "seen"},
            "species:255": {"s": "caught"}, "species:258": {"s": "none"},
            "star:259": {"s": "seen"}, "species:260": None}}
        report = opt.story_report(roster, [], {"final": "Butterfree", "endpoint_id": 12})
        self.assertEqual(report.get("source_seen_ids"), [256, 257])
        self.assertEqual(report["source_caught_ids"], [255])

    def test_pokedex_report_gains_exclude_seen_in_both_search_engines(self):
        pool = []
        for i, typ in enumerate(("Fire", "Water", "Grass", "Electric", "Ice", "Ground")):
            member = torchic()
            member.update(final=f"Final{i}", endpoint_id=1000 + i, caught_ids=[2000 + i],
                          caught_as=[f"Baby{i}"], types=[typ], points=4,
                          moves=[(typ, 80, 1.0)], weak=set(), resist=set(),
                          atk=100, spa=110, bulk=280, spe=110)
            member["evolution_path"] = [
                {"id": 2000 + i, "name": f"Baby{i}", "status": "caught"},
                {"id": 3000 + i, "name": f"Middle{i}", "method": "Level 16", "status": "seen"},
                {"id": 1000 + i, "name": f"Final{i}", "method": "Level 36", "status": "none"}]
            member["dex_plan"] = opt.pure_level_plans(member)[0]
            pool.append(member)
        utility = {**copy.deepcopy(pool[0]), "final": "Butterfree", "caught_ids": [12],
                   "types": ["Bug", "Flying"]}
        with mock.patch.dict(os.environ, {"STORY_NATIVE_DISABLE": "1"}):
            reference = opt._rank(pool, utility, {}, category="Pokedex")[0]
        self.assertEqual(reference["new_entries"], 5)
        self.assertEqual(reference["evolution_opportunities"], 5)
        import story_native
        if story_native.binary_path() is None:
            self.skipTest("native parity requires an explicitly built accelerator")
        result = opt._rank(pool, utility, {}, category="Pokedex")[0]
        self.assertEqual(result["native_search"]["engine"], "rust")
        self.assertEqual({k: v for k, v in result.items() if k != "native_search"}, reference)

    def test_caught_only_input_does_not_invent_unseen_stages(self):
        member = torchic()
        for stage in member["evolution_path"]:
            stage.pop("status")
        self.assertEqual(opt.pure_level_plans(member), [])

    def test_only_none_stages_gain_even_when_seen_intermediate_is_traversed(self):
        member = torchic()
        plans = opt.pure_level_plans(member)
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0]["new_entries"], ["Blaziken"])
        self.assertEqual([s["name"] for s in plans[0]["evolution_path"]],
                         ["Torchic", "Combusken", "Blaziken"])
        member["evolution_path"][1]["status"] = "none"
        self.assertEqual(opt.pure_level_plans(member)[-1]["new_entries"],
                         ["Combusken", "Blaziken"])
        member["evolution_path"][1]["status"] = "caught"
        self.assertEqual(opt.pure_level_plans(member)[-1]["new_entries"], ["Blaziken"])
        member["evolution_path"][-1]["status"] = "seen"
        self.assertEqual(opt.pure_level_plans(member), [])
