import json
import io
import math
import contextlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))

import roster_lens as rl  # noqa: E402
import team_builder as tb  # noqa: E402
import team_synergy as ts  # noqa: E402
import team_options as opt  # noqa: E402


class TeamOptionsTests(unittest.TestCase):
    def test_team_synergy_story_flag_routes_to_fixed_utility_options(self):
        utility = self._member("Butterfree", 12, "Bug", owned="Butterfree")
        other = self._member("Galvantula", 596, "Electric", owned="Joltik")
        roster = {"pool": [utility, other], "records": {}, "caught_count": 2,
                  "canonical_count": 2, "by_id": {}, "warnings": [], "assumptions": [], "limitations": []}
        with mock.patch.object(tb, "load_roster", return_value=roster) as load, \
             mock.patch.object(ts, "load_typechart", return_value={}), \
             mock.patch.object(ts, "move_info", return_value={}), \
             mock.patch.object(ts, "moveset_provenance", return_value={"path": ""}), \
             mock.patch.object(ts, "profile", side_effect=lambda p, *args: p), \
             mock.patch.object(opt, "choose_options", return_value=[]) as choose, \
             mock.patch.object(sys, "argv", ["team_synergy.py", "--uid", "uid", "--story-options"]), \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(ts.main(), 0)
        self.assertEqual(load.call_args.kwargs["off_limits"], "")
        self.assertEqual(choose.call_args.args[1]["final"], "Butterfree")

    def _member(self, name, dex, typ, points=4, owned=None):
        return {"final": name, "endpoint_id": dex, "caught_as": [owned or name + "-baby"],
                "caught_ids": [dex - 1], "lineage_ids": [dex - 1, dex], "types": [typ],
                "points": points, "moves": [(typ, 100, 1.0)], "weak": set(),
                "resist": set(), "atk": 100, "spa": 110, "bulk": 280, "spe": 110,
                "tier": "RU", "usage": 0.1, "rank": 5}

    def test_five_options_fix_utility_and_scope_og_by_final_endpoint(self):
        old = [self._member(f"Old{i}", 20 + i, typ) for i, typ in
               enumerate(["Normal", "Fire", "Water", "Electric", "Grass", "Ice"])]
        new = [self._member(f"New{i}", 200 + i, typ) for i, typ in
               enumerate(["Fighting", "Poison", "Ground", "Flying", "Psychic", "Bug"])]
        utility = self._member("Butterfree", 12, "Bug", owned="Butterfree")
        options = opt.choose_options(old + new, utility, {}, min_changes=1)
        self.assertEqual([o["category"] for o in options],
                         ["OG", "Non-OG", "Mixed", "Pokedex", "Best"])
        self.assertTrue(all(o["utility"] == "Butterfree" for o in options))
        self.assertEqual(len(options[0]["profiles"]), 5)
        self.assertEqual(len(options[1]["profiles"]), 5)
        self.assertTrue(all(m["endpoint_id"] <= 151 for m in options[0]["profiles"]))
        self.assertTrue(all(m["endpoint_id"] > 151 for m in options[1]["profiles"]))
        self.assertEqual(len(options[2]["profiles"]), 5)
        self.assertEqual(len(options[4]["profiles"]), 5)
        self.assertFalse(options[3]["profiles"])
        self.assertTrue(options[3]["warning"])

    def test_synergy_precedes_quality_but_best_reverses_that_priority(self):
        distinct = [self._member(name, 200 + index, typ, points=1)
                    for index, (name, typ) in enumerate(zip(
                        ("A", "B", "C", "D", "E"),
                        ("Normal", "Fire", "Water", "Electric", "Grass")))]
        high_quality = self._member("Quality", 250, "Bug", points=100)
        utility = self._member("Butterfree", 12, "Bug", owned="Butterfree")
        pool = [*distinct, high_quality]

        synergy_first = opt._rank(pool, utility, {}, category="Mixed")[0]
        viability_first = opt._rank(pool, utility, {}, category="Best")[0]

        self.assertNotIn("Quality", synergy_first["members"])
        self.assertIn("Quality", viability_first["members"])

    def test_pokedex_new_entries_precede_synergy(self):
        baseline = [self._member(name, 300 + index, typ, points=8)
                    for index, (name, typ) in enumerate(zip(
                        ("A", "B", "C", "D", "E"),
                        ("Normal", "Fire", "Water", "Electric", "Grass")))]
        for item in baseline:
            item["dex_plan"] = {"new_entries": [item["final"]]}
        high_entries = self._member("ManyEntries", 350, "Bug", points=0)
        high_entries["dex_plan"] = {"new_entries": ["One", "Two", "Three"]}
        utility = self._member("Butterfree", 12, "Bug", owned="Butterfree")

        ranked = opt._rank([*baseline, high_entries], utility, {}, category="Pokedex")

        self.assertIn("ManyEntries", ranked[0]["members"])
        self.assertEqual(ranked[0]["new_entries"], 7)

    def test_mixed_objective_does_not_require_both_generation_groups(self):
        old = [self._member(f"Kanto{i}", 30 + i, typ) for i, typ in
               enumerate(["Normal", "Fire", "Water", "Electric", "Grass"])]
        utility = self._member("Butterfree", 12, "Bug", owned="Butterfree")

        options = opt.choose_options(old, utility, {})

        self.assertEqual(options[2]["category"], "Mixed")
        self.assertEqual(len(options[2]["members"]), 5)
        self.assertTrue(all(name.startswith("Kanto") for name in options[2]["members"]))

    def test_og_attempt_is_reported_instead_of_fabricating_five_members(self):
        modern = [self._member(f"New{i}", 200 + i, typ) for i, typ in

                  enumerate(["Normal", "Fire", "Water", "Electric", "Grass", "Ice"])]
        utility = self._member("Butterfree", 12, "Bug", owned="Butterfree")
        options = opt.choose_options(modern, utility, {}, min_changes=1)
        self.assertEqual(options[0]["category"], "OG")
        self.assertFalse(options[0]["members"])
        self.assertIn("only 0", options[0]["warning"])

    def test_pokedex_plans_stop_before_nonlevel_gate_and_count_unseen_intermediate(self):
        member = {"final": "Vikavolt", "caught_ids": [736, 738],
                  "caught_as": ["Grubbin", "Vikavolt"],
                  "evolution_path": [
                      {"id": 736, "name": "Grubbin"},
                      {"id": 737, "name": "Charjabug", "method": "Level 20"},
                      {"id": 738, "name": "Vikavolt", "method": "Thunder Stone"},
                  ]}

        plans = opt.pure_level_plans(member)

        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0]["owned"], "Grubbin")
        self.assertEqual(plans[0]["planned_final"], "Charjabug")
        self.assertEqual(plans[0]["new_entries"], ["Charjabug"])

    def test_pokedex_rejects_level_methods_with_day_sex_stat_or_branch_conditions(self):
        cases = [
            ("Yungoos", "Gumshoos", 734, 735, "Level 20"),
            ("Kirlia", "Gallade", 281, 475, "Level 30"),
            ("Tyrogue", "Hitmontop", 236, 237, "Level 20"),
            ("Nincada", "Shedinja", 290, 292, "Level 20"),
            ("Wurmple", "Silcoon", 265, 266, "Level 7"),
        ]
        for owned, target, owned_id, target_id, method in cases:
            with self.subTest(target=target):
                member = {"final": target, "caught_ids": [owned_id], "caught_as": [owned],
                          "evolution_path": [{"id": owned_id, "name": owned},
                                             {"id": target_id, "name": target, "method": method}]}
                self.assertEqual(opt.pure_level_plans(member), [])

    def test_owned_final_form_cannot_earn_a_second_evolution_entry(self):
        fearow = self._member("Fearow", 22, "Normal", owned="Spearow")
        fearow["caught_ids"] = [21, 22]
        fearow["caught_as"] = ["Spearow", "Fearow"]
        roster = {"by_id": {21: {"name": "Spearow"}, 22: {"name": "Fearow"}},
                  "det": {22: {"evolution": [{"name": "Spearow"},
                                              {"name": "Fearow", "method": "Level 20"}]}}}

        self.assertFalse(opt.is_evolving(fearow))
        self.assertEqual(opt.evolution_opportunities(fearow), 0)
        self.assertEqual(opt.evolution_chain(fearow, roster), ("Fearow", "Fearow"))

    def test_hidden_ability_caveat_is_derived_from_slots_not_species_allowlist(self):
        hidden = self._member("Unlistedmon", 999, "Psychic", points=4)
        hidden["abilities"] = "Mind Reader, Meta Force(H)"
        ordinary = self._member("Ordinarymon", 998, "Psychic", points=4)
        ordinary["abilities"] = "Mind Reader"

        self.assertTrue(opt.has_hidden_ability_caveat(hidden))
        self.assertFalse(opt.has_hidden_ability_caveat(ordinary))
        self.assertLess(opt.practical_viability(hidden), opt.practical_viability(ordinary))

    def test_hidden_ability_penalty_tracks_usage_share_of_h_slot(self):
        hidden_dependent = self._member("HiddenBuild", 999, "Ground", points=5)
        hidden_dependent["abilities"] = "Pickup, Huge Power(H)"
        hidden_dependent["competitive_ability_usage"] = {"pickup": 1.0, "hugepower": 99.0}
        ordinary_build = {**hidden_dependent, "competitive_ability_usage":
                          {"pickup": 99.0, "hugepower": 1.0}}

        hidden_score = opt.practical_viability(hidden_dependent)
        ordinary_score = opt.practical_viability(ordinary_build)
        self.assertGreaterEqual(hidden_score, 4.0)
        self.assertLess(hidden_score, ordinary_score)

    def test_anchor_rejects_hidden_ability_dependency_and_finalized_species(self):
        strong = self._member("Diggersby", 660, "Ground", points=5.5)
        sturdy = self._member("Pelipper", 279, "Flying", points=6)
        finalized = self._member("AlreadyDone", 500, "Water", points=7, owned="AlreadyDone")
        self.assertLess(opt.anchor_score(strong), opt.anchor_score(sturdy))
        self.assertFalse(opt.is_evolving(finalized))

    def test_alolan_gen1_endpoint_is_neither_og_only_nor_no_og(self):
        alolan = self._member("Muk-Alola", 89, "Poison", owned="Grimer")
        alolan["alolan"] = True
        old = [self._member(f"Old{i}", 20 + i, typ) for i, typ in
               enumerate(["Fire", "Water", "Electric", "Grass", "Ice"])]
        modern = [self._member(f"New{i}", 200 + i, typ) for i, typ in
                  enumerate(["Fire", "Water", "Electric", "Grass", "Ice"])]
        utility = self._member("Butterfree", 12, "Bug", owned="Butterfree")
        options = opt.choose_options([*old, *modern, alolan], utility, {}, min_changes=1)
        self.assertNotIn("Muk-Alola", options[0]["members"])
        self.assertNotIn("Muk-Alola", options[1]["members"])

    def test_og_only_requires_an_owned_og_stage(self):
        tyrogue = self._member("Hitmonlee", 106, "Fighting", owned="Tyrogue")
        tyrogue["caught_ids"] = [236]
        pikachu = self._member("Raichu", 26, "Electric", owned="Pikachu")
        pikachu["caught_ids"] = [25, 172]
        self.assertFalse(opt.og_ready(tyrogue))
        self.assertTrue(opt.og_ready(pikachu))

    def test_no_og_rejects_gen1_owned_stage_even_if_final_is_later(self):
        slowking = self._member("Slowking", 199, "Water", owned="Slowpoke")
        slowking["caught_ids"] = [79]
        self.assertFalse(opt.no_og_ready(slowking))
        self.assertTrue(opt.no_og_ready(self._member("Feraligatr", 160, "Water", owned="Totodile")))

    def test_no_assumed_gender_or_stat_gate_on_unrecorded_individual(self):
        species = [self._member(name, dex, typ) for name, dex, typ in
                   [("Salazzle", 758, "Poison"), ("Hitmontop", 237, "Fighting"),
                    ("Froslass", 478, "Ice"),
                    ("Gardevoir", 282, "Fairy"), ("Vikavolt", 738, "Electric")]]
        usable = opt.eligible_for_easy_run(species)
        self.assertEqual([p["final"] for p in usable], ["Gardevoir", "Vikavolt"])

    def test_no_early_tier_floor_removes_candidates_before_story_objectives(self):
        old = [self._member(f"Old{i}", 20 + i, typ) for i, typ in
               enumerate(["Normal", "Fire", "Water", "Electric", "Grass"])]
        new = [self._member(f"New{i}", 200 + i, typ) for i, typ in
               enumerate(["Fighting", "Poison", "Ground", "Flying", "Psychic", "Rock"])]
        weak = self._member("Gumshoos", 735, "Dark", points=9)
        weak["tier"] = "(PU)"
        utility = self._member("Butterfree", 12, "Bug", owned="Butterfree")

        options = opt.choose_options(old + new + [weak], utility, {}, min_changes=1)

        self.assertIn("Gumshoos", options[1]["members"])
        self.assertIn("Gumshoos", options[4]["members"])

    def test_story_coverage_does_not_credit_unverified_ladder_moves(self):
        line = self._member("Infernape", 392, "Fire")
        line["types"] = ["Fire", "Fighting"]
        line["moves"] = [("Ice", 120, 1.0), ("Fire", 120, 1.0)]
        transformed = opt.conservative_profiles([line])[0]
        self.assertEqual({typ for typ, _, _ in transformed["moves"]}, {"Fire", "Fighting"})
        self.assertEqual(line["moves"], [("Ice", 120, 1.0), ("Fire", 120, 1.0)])
        self.assertIn("proxy", transformed["coverage_source"])

    def test_current_favorite_breaks_equal_team_score_tie_without_locking(self):
        old = self._member("Old", 40, "Normal")
        new = [self._member(f"New{i}", 200 + i, "Normal") for i in range(4)]
        favorite = self._member("ZZFavorite", 230, "Normal")
        favorite["favorite"] = True
        utility = self._member("Butterfree", 12, "Bug", owned="Butterfree")
        ranked = opt._rank([old, *new, favorite], utility, {}, category="Mixed")
        self.assertIn("ZZFavorite", ranked[0]["members"])

    def test_story_report_uses_hack_evolution_overrides_and_owned_stages(self):
        klink = self._member("Klinklang", 601, "Steel", owned="Klink")
        klink["caught_ids"] = [599]
        roster = {"caught_count": 1, "canonical_count": 1, "pool": [klink],
                  "by_id": {599: {"name": "Klink"}}, "det": {601: {"evolution": [
                      {"name": "Klink"}, {"name": "Klang", "method": "Level 38"},
                      {"name": "Klinklang", "method": "Level 49"}]}},
                  "records": {"star:599": {"s": "on"}}}
        utility = self._member("Butterfree", 12, "Bug", owned="Butterfree")
        option = {"category": "No OG-151", "members": ["Klinklang"],
                  "profiles": [klink], "anchor": "Klinklang", "utility": "Butterfree",
                  "core_score": 1, "six_score": 1, "evolving": 1, "level_evolving": 1,
                  "shared_types": 0}
        report = opt.story_report(roster, [option], utility)
        text = opt.format_story_report(report)
        self.assertIn("Klink → Klang (L28) → Klinklang (L39)", text)
        self.assertEqual(report["options"][0]["anchor"], "Klinklang")
        self.assertTrue(report["options"][0]["members"][0]["favorite"])


class TeamBuilderTests(unittest.TestCase):
    def _world(self):
        details = {
            172: {"id": 172, "source": "Raichu", "types": ["Electric"], "tier": "(PU)", "usage": 0.1},
            25: {"id": 25, "source": "Raichu", "types": ["Electric"], "tier": "(PU)", "usage": 0.1,
                 "evolution": [{"name": "Pichu"}, {"name": "Pikachu"}]},
            26: {"id": 26, "source": "Raichu", "types": ["Electric"], "tier": "(PU)", "usage": 0.1,
                 "evolution": [{"name": "Pichu"}, {"name": "Pikachu"}, {"name": "Raichu"}]},
            280: {"id": 280, "source": "Gardevoir", "types": ["Psychic", "Fairy"], "tier": "RU", "usage": 1,
                  "evolution": [{"name": "Ralts"}]},
            282: {"id": 282, "source": "Gardevoir", "types": ["Psychic", "Fairy"], "tier": "RU", "usage": 1,
                  "evolution": [{"name": "Ralts"}, {"name": "Gardevoir"}]},
            475: {"id": 475, "source": "Gallade", "types": ["Psychic", "Fighting"], "tier": "PUBL", "usage": 1,
                  "evolution": [{"name": "Ralts"}, {"name": "Gallade"}]},
        }
        by_id = {i: {"id": i, "name": n, "slug": n.lower()} for i, n in {
            172: "Pichu", 25: "Pikachu", 26: "Raichu", 280: "Ralts", 282: "Gardevoir", 475: "Gallade"}.items()}
        dex = "\n".join(f"\t{name.lower()}: {{ types: [\"Electric\"], baseStats: {{hp: 50, atk: 50, def: 50, spa: 50, spd: 50, spe: 50}}, abilities: {{0: \"Static\"}} }}," for name in ("Raichu", "Gardevoir", "Gallade"))
        return details, by_id, {}, dex

    def test_canonicalizes_duplicate_evolution_records_and_preserves_source_names(self):
        details, by_id, forms, dex = self._world()
        candidates = tb.canonicalize_roster([172, 25, 26], details, by_id, forms, dex)
        self.assertEqual([c["final"] for c in candidates], ["Raichu"])
        self.assertEqual(candidates[0]["caught_ids"], [25, 26, 172])
        self.assertEqual(candidates[0]["caught_as"], ["Pichu", "Pikachu", "Raichu"])

    def test_branching_line_yields_one_candidate_per_reachable_endpoint(self):
        details, by_id, forms, dex = self._world()
        candidates = tb.canonicalize_roster([280], details, by_id, forms, dex)
        self.assertEqual({c["final"] for c in candidates}, {"Gardevoir", "Gallade"})

    def test_uber_is_the_best_tier_and_min_tier_is_deliberately_validated(self):
        self.assertLess(tb.tier_rank("Uber"), tb.tier_rank("OU"))
        self.assertEqual(tb.normalise_tier("uber"), "Uber")
        with self.assertRaises(ValueError):
            tb.normalise_tier("not-a-tier")
        self.assertTrue(tb.tier_passes("Uber", "OU"))
        self.assertFalse(tb.tier_passes("UU", "OU"))

    def test_ag_is_a_recognized_tier_above_uber(self):
        # TIER_ORDER used to be a private 13-entry list missing "AG"; any species
        # ever tiered AG would make normalise_tier() raise instead of ranking it.
        self.assertEqual(tb.normalise_tier("ag"), "AG")
        self.assertLess(tb.tier_rank("AG"), tb.tier_rank("Uber"))

    def test_normalize_folds_accents_so_flabebe_resolves(self):
        # normalize() used to ascii-ignore-encode, which drops an accented letter
        # entirely instead of folding it to its base letter, so "Flabébé" and a
        # plain-ascii "flabebe" lookup normalized to different keys.
        self.assertEqual(tb.normalize("Flabébé"), tb.normalize("flabebe"))

    def test_invalid_selection_arguments_are_rejected(self):
        for kwargs in (
            {"teams": 0, "size": 5, "pool": 10, "shortlist": 10},
            {"teams": 1, "size": 0, "pool": 10, "shortlist": 10},
            {"teams": 1, "size": 6, "pool": 5, "shortlist": 10},
            {"teams": 1, "size": 5, "pool": 10, "shortlist": 0},
        ):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    ts.validate_args(**kwargs)
        with self.assertRaises(ValueError):
            tb.validate_keep(0)

    def test_no_gen1_is_lineage_based_but_keeps_butterfree_and_optional_alola(self):
        old_line = {"final": "Raichu", "lineage_ids": [172, 25, 26], "alolan": False}
        butterfree = {"final": "Butterfree", "lineage_ids": [10, 11, 12], "alolan": False}
        alola = {"final": "Raichu-Alola", "lineage_ids": [172, 25, 26], "alolan": True}
        self.assertFalse(tb.allowed_by_gen1(old_line, keep_alolan=False))
        self.assertTrue(tb.allowed_by_gen1(butterfree, keep_alolan=False))
        self.assertFalse(tb.allowed_by_gen1(alola, keep_alolan=False))
        self.assertTrue(tb.allowed_by_gen1(alola, keep_alolan=True))

    def test_roster_reports_form_assumption(self):
        details, by_id, forms, dex = self._world()
        forms["Raichu-Alola"] = {"source": "Raichu-Alola", "types": ["Electric", "Psychic"], "tier": "UU", "usage": 2}
        candidate = tb.describe_line(26, details, by_id, forms, dex)
        self.assertTrue(candidate["form_assumptions"])
        self.assertIn("assumed", candidate["form_assumptions"][0].lower())

    def test_read_records_propagates_subprocess_failure(self):
        failed = mock.Mock(returncode=17, stdout="", stderr="firebase unavailable")
        with mock.patch.object(tb.subprocess, "run", return_value=failed):
            with self.assertRaises(RuntimeError) as ctx:
                tb.read_records("uid")
        self.assertIn("firebase unavailable", str(ctx.exception))


class TeamSynergyTests(unittest.TestCase):
    def test_tier_points_covers_every_ranked_tier(self):
        # Smogon tier lists used to be hand-retyped independently in team_builder.py,
        # team_synergy.py, validate_data.py, build_pokedex_details.py and moveline.py,
        # with different memberships (team_synergy's TIER_POINTS was missing "AG").
        # Every tier in the one shared TIER_ORDER must have a point value.
        self.assertEqual(set(ts.TIER_POINTS), set(tb.TIER_ORDER))

    def test_story_synergy_is_independent_of_competitive_quality(self):
        member = {"final": "TypePotential", "points": 1, "types": ["Water"],
                  "moves": [("Water", 80, 1.0)], "weak": {"Electric"},
                  "resist": {"Fire"}, "atk": 80, "spa": 90, "bulk": 260, "spe": 75}
        low, low_detail = ts.story_synergy_score([member], {})
        strong = {**member, "points": 999}
        high, high_detail = ts.story_synergy_score([strong], {})

        self.assertEqual(low, high)
        self.assertEqual(low_detail, high_detail)
        self.assertEqual(set(low_detail), {"coverage", "defence", "shared_types",
                                          "shared_weak", "score"})

    def test_tier_local_ability_usage_is_loaded_without_merging_tiers(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp)
            (cache / "chaos-gen7uu-1630.json").write_text(json.dumps({
                "data": {"Feraligatr": {"Abilities": {"Torrent": 23, "Sheer Force": 1709}}}}))
            (cache / "chaos-gen7ru-1630.json").write_text(json.dumps({
                "data": {"Feraligatr": {"Abilities": {"Torrent": 999}}}}))

            usage = ts.load_ability_usage(cache, "UU")

        self.assertEqual(usage["feraligatr"], {"torrent": 23.0, "sheerforce": 1709.0})

    def test_tier_local_chaos_file_does_not_merge_other_tiers(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp)
            (cache / "chaos-gen7ou-1695.json").write_text(json.dumps({"data": {"Testmon": {"Moves": {"Surf": 90}}}}))
            (cache / "chaos-gen7ru-1630.json").write_text(json.dumps({"data": {"Testmon": {"Moves": {"Earthquake": 99}}}}))
            moves = ts.load_movesets(cache, "OU")
            self.assertIn("surf", moves["testmon"])
            self.assertNotIn("earthquake", moves["testmon"])
            provenance = ts.moveset_provenance(cache, "OU")
            self.assertEqual(provenance["mapped_tier"], "OU")
            self.assertFalse(provenance["fallback"])

    def test_typechart_is_read_from_the_shared_showdown_js_store(self):
        store = mock.Mock()
        store.get_text.return_value = (
            "exports.BattleTypeChart = {\n"
            "\tNormal: {damageTaken: {Fire: 1, Ghost: 3}},\n"
            "};\n"
        )
        with mock.patch.object(ts, "require_cache", return_value=store):
            chart = ts.load_typechart(Path("unused"))
        self.assertEqual(chart["normal"], {"fire": 1, "ghost": 3})

    def test_profile_keeps_best_contribution_for_each_attack_type(self):
        line = {"types": ["Normal"], "stats": "50/100/50/120/50/100", "final": "Testmon",
                "tier": "OU", "usage": 1.0}
        movesets = {"testmon": {"tackle": 100, "quickattack": 90, "flamethrower": 80,
                                "fireblast": 70, "surf": 60, "icebeam": 50}}
        mtype = {"tackle": ("Normal", 40), "quickattack": ("Normal", 40),
                 "flamethrower": ("Fire", 90), "fireblast": ("Fire", 110),
                 "surf": ("Water", 90), "icebeam": ("Ice", 90)}
        result = ts.profile(line, {}, movesets, mtype)
        self.assertEqual(set(result["attack_types"]), {"Normal", "Fire", "Water", "Ice"})
        best = {typ: (bp, share) for typ, bp, share in result["moves"]}
        self.assertEqual(best["Fire"][0], 110)

    def test_profile_excludes_move_types_below_relative_usage_floor(self):
        line = {"types": ["Normal"], "stats": "50/100/50/120/50/100", "final": "Testmon",
                "tier": "OU", "usage": 1.0}
        movesets = {"testmon": {"tackle": 100, "surf": 14.9}}
        mtype = {"tackle": ("Normal", 40), "surf": ("Water", 120)}

        result = ts.profile(line, {}, movesets, mtype)

        self.assertEqual(result["attack_types"], ["Normal"])
        self.assertNotIn("Water", result["attack_types"])

    def test_profile_filters_rare_types_before_collapsing_duplicate_common_moves(self):
        line = {"types": ["Normal"], "stats": "50/100/50/120/50/100", "final": "Testmon",
                "tier": "OU", "usage": 1.0}
        movesets = {"testmon": {"flamethrower": 100, "fireblast": 90,
                                "icebeam": 15, "surf": 14}}
        mtype = {"flamethrower": ("Fire", 90), "fireblast": ("Fire", 110),
                 "icebeam": ("Ice", 90), "surf": ("Water", 120)}

        result = ts.profile(line, {}, movesets, mtype)

        self.assertEqual(set(result["attack_types"]), {"Fire", "Ice"})
        best = {typ: (bp, share) for typ, bp, share in result["moves"]}
        self.assertEqual(best["Fire"], (110, 0.9))
        self.assertEqual(best["Ice"], (90, 0.15))
        self.assertNotIn("Water", best)

    def test_representative_current_roster_profiles_do_not_saturate_coverage(self):
        mtype = {
            "closecombat": ("Fighting", 120), "flareblitz": ("Fire", 120), "uturn": ("Bug", 70),
            "earthpower": ("Ground", 90), "sludgewave": ("Poison", 95), "icebeam": ("Ice", 90),
            "thunderbolt": ("Electric", 90), "scald": ("Water", 80), "psychic": ("Psychic", 90),
            "shadowball": ("Ghost", 80), "dazzlinggleam": ("Fairy", 80), "knockoff": ("Dark", 65),
        }
        roster = [
            ("Infernape", ["Fire", "Fighting"], {"closecombat": 100, "flareblitz": 70, "uturn": 40, "rockslide": 10}),
            ("Nidoking", ["Poison", "Ground"], {"earthpower": 100, "sludgewave": 70, "icebeam": 20, "thunderbolt": 15, "surf": 5}),
            ("Slowbro", ["Water", "Psychic"], {"scald": 100, "psychic": 60, "icebeam": 25, "flamethrower": 10}),
            ("Gardevoir", ["Psychic", "Fairy"], {"psychic": 100, "dazzlinggleam": 60, "shadowball": 20, "thunderbolt": 10}),
            ("Zoroark", ["Dark"], {"knockoff": 100, "flamethrower": 50, "uturn": 20, "shadowball": 15, "surf": 5}),
        ]
        profiles = [ts.profile({"final": name, "types": types, "stats": "80/100/80/100/80/100",
                                "tier": "UU", "usage": 1.0}, {}, {name.lower(): moves}, mtype)
                    for name, types, moves in roster]

        self.assertTrue(all(len(member["attack_types"]) <= 4 for member in profiles))
        chart = {defender.lower(): {} for defender in ts.ALL_TYPES}
        for attack_type in {attack_type for member in profiles for attack_type in member["attack_types"]}:
            chart[attack_type.lower()][attack_type.lower()] = 1
        _, detail = ts.score_team(profiles, chart)
        self.assertGreater(len(detail["hit"]), 0)
        self.assertLess(len(detail["hit"]), len(ts.ALL_TYPES))
        self.assertGreater(detail["coverage"], 0.0)
        self.assertLess(detail["coverage"], 0.65)

    def test_diversity_counts_member_replacements_not_symmetric_difference(self):
        a = ("A", "B", "C", "D", "E")
        two_replaced = ("A", "B", "C", "F", "G")
        three_replaced = ("A", "B", "F", "G", "H")
        self.assertEqual(ts.member_replacements(a, two_replaced), 2)
        self.assertFalse(ts.diverse_enough(a, two_replaced, replacements=3))
        self.assertTrue(ts.diverse_enough(a, three_replaced, replacements=3))

    def test_shared_weakness_penalty_starts_at_three(self):
        def member(name):
            return {"name": name, "points": 1, "types": ["Normal"], "moves": [],
                    "weak": {"Water"}, "resist": set(), "atk": 100, "spa": 100,
                    "bulk": 100, "spe": 100, "attack_types": []}
        two = [member("a"), member("b")]
        three = two + [member("c")]
        self.assertEqual(ts.score_team(two, {})[1]["shared_weak_penalty"], 0)
        self.assertGreater(ts.score_team(three, {})[1]["shared_weak_penalty"], 0)

    def test_search_finds_a_synergy_pair_that_individual_order_would_miss(self):
        def member(name, points, typ):
            return {"final": name, "points": points, "types": [typ], "moves": [], "weak": set(),
                    "resist": set(), "atk": 100, "spa": 50, "bulk": 100, "spe": 50,
                    "attack_types": [], "rank": 0, "usage": 0, "caught_as": [name]}
        pool = [member("A", 6, "Normal"), member("B", 6, "Normal"), member("C", 5, "Fire")]
        chosen = ts.search_teams(pool, size=2, shortlist=3, teams=1, diversity=1, chart={})
        self.assertEqual(chosen[0][1], ("A", "C"))

    def test_team_builder_passes_one_loaded_records_snapshot_to_catcher(self):
        records = {"species:25": {"s": "caught"}}
        catcher_data = {"dex_text": "loaded dex"}
        roster = {
            "records": records, "pool": [], "caught_count": 1, "canonical_count": 0,
            "assumptions": [], "warnings": [], "limitations": [], "excluded": [],
        }
        with mock.patch.object(tb.catcher, "load_rank_data", return_value=catcher_data), \
             mock.patch.object(tb, "load_roster", return_value=roster), \
             mock.patch.object(tb.catcher, "rank_candidates", return_value=[]) as rank, \
             mock.patch.object(tb.catcher, "plain_lines", return_value=["score pokemon tier best tool"]), \
             mock.patch.object(sys, "argv", ["team_builder.py", "--uid", "uid", "--cache", "unused"]):
            self.assertEqual(tb.main(), 0)
        rank.assert_called_once_with(records, catcher_data)

    def test_roster_lens_uses_structured_catcher_results(self):
        records = {"species:25": {"s": "caught"}}
        catcher_data = {
            "rows": [{"id": 25, "name": "Pikachu"}],
            "details": {25: {"source": "Pikachu", "grade": "A", "tier": "UU", "usage": 1.0}},
            "dex_text": "\n\tpikachu: {baseStats: {hp: 35, atk: 55, def: 40, spa: 50, spd: 50, spe: 90}},",
        }
        candidate = {"name": "Pikachu", "score": 12.5}
        with mock.patch.object(rl.catcher, "load_rank_data", return_value=catcher_data), \
             mock.patch.object(rl.roster_data, "read_records", return_value=records) as read, \
             mock.patch.object(rl.catcher, "rank_candidates", return_value=[candidate]) as rank, \
             mock.patch("builtins.print"), \
             mock.patch.object(sys, "argv", ["roster_lens.py", "--uid", "uid"]):
            self.assertEqual(rl.main(), 0)
        read.assert_called_once_with("uid")
        rank.assert_called_once_with(records, catcher_data, exclude="", fleeing=False)
        self.assertFalse(hasattr(rl, "subprocess"))


class TeamSearchBudgetTests(unittest.TestCase):
    def test_default_size_search_is_within_the_exhaustive_budget(self):
        pool = [{"final": str(index)} for index in range(24)]
        with mock.patch.object(ts, "score_team", return_value=(1.0, {})) as score_team:
            result = ts.search_teams(pool, size=5, shortlist=1, teams=1, diversity=1, chart={})
        self.assertEqual(len(result), 1)
        self.assertEqual(score_team.call_count, math.comb(24, 5))

    def test_oversized_search_is_rejected_before_scoring(self):
        pool = [{"final": str(index)} for index in range(24)]
        with mock.patch.object(ts, "score_team") as score_team:
            with self.assertRaisesRegex(ValueError, "hard limit"):
                ts.search_teams(pool, size=6, shortlist=1, teams=1, diversity=1, chart={})
        score_team.assert_not_called()


if __name__ == "__main__":
    unittest.main()
