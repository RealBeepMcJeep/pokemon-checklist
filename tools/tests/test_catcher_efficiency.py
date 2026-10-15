"""Independent pinned Gen VII damage and nonlethal setup-action regressions."""
import importlib.util
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

class EfficiencyTests(unittest.TestCase):
    def module(self):
        self.assertIsNotNone(importlib.util.find_spec("catcher_efficiency"),
                             "A separate damage lens must exist; do not mix it into utility points")
        import catcher_efficiency
        return catcher_efficiency

    def test_technician_and_normal_stab_match_published_gen7_reference(self):
        e=self.module()
        import json
        data=json.loads(Path(__file__).with_name("false_swipe_reference.json").read_text())
        v=next(v for v in data["vectors"] if v["name"]=="Smeargle" and v["ability"]=="Technician" and v["defender"]=="Pikachu")
        self.assertEqual(e.damage_rolls(**{k:v[k] for k in ["level","attack","defense","attacker_types","defender_types","ability"]}),v["damage"])

    def test_all_pinned_damage_vectors_match_without_reference_package(self):
        import json
        e=self.module()
        data=json.loads(Path(__file__).with_name("false_swipe_reference.json").read_text())
        for v in data["vectors"]:
            with self.subTest(name=v["name"],ability=v["ability"],target=v["defender"]):
                args={k:v[k] for k in ["level","attack","defense","attacker_types","defender_types","ability","status"]}
                self.assertEqual(e.damage_rolls(**args),v["damage"])

    def test_setup_counts_nonlethal_hits_and_misses_not_capture_odds(self):
        import math
        e=self.module()
        self.assertTrue(callable(getattr(e,"expected_actions",None)),"Need a nonlethal stochastic setup model, not base-power-only claims")
        self.assertEqual(e.expected_actions(100,[10]*16),math.ceil((100-1)/10))
        self.assertEqual(e.expected_actions(100,[10]*16,accuracy=0.5),math.ceil((100-1)/10)/0.5)
        self.assertEqual(e.expected_actions(1,[100]*16),0)
        self.assertIsNone(e.expected_actions(30,[0]*16))
        self.assertIsNone(e.expected_actions(30,[10]*16,accuracy=0))

    def test_stats_and_optional_fang_policy_are_explicit_and_nonlethal(self):
        e=self.module()
        self.assertTrue(callable(getattr(e,"stat",None)),"Stats must use declared level/IV/EV/nature")
        self.assertEqual(e.stat(20,30),26)
        self.assertEqual(e.stat(35,20,hp=True),50)
        self.assertEqual(e.stat(35,20,hp=True,iv=0),44)
        self.assertTrue(callable(getattr(e,"expected_with_fang",None)))
        self.assertLess(e.expected_with_fang(100,[2]*16),e.expected_actions(100,[2]*16))
        self.assertEqual(e.expected_with_fang(1,[2]*16),0)
        self.assertIsNone(e.expected_with_fang(30,[0]*16))

    @unittest.skipUnless(__import__("catcher_score").configured_cache_dir().exists(),"verified Gen VII cache unavailable")
    def test_report_keeps_utility_scores_and_unknown_ability_assumptions_separate(self):
        import copy
        import catcher_now as now
        from showdown_data import configured_cache_dir
        e=self.module()
        self.assertTrue(callable(getattr(e,"compare",None)),"Need an independent report lens")
        source=now.build_report({},configured_cache_dir(),species="paras,smeargle,butterfree,kricketot,gastly")
        before=copy.deepcopy(source)
        report=e.compare(source,configured_cache_dir())
        self.assertEqual(source,before)
        self.assertTrue(report["rows"])
        self.assertTrue(any(x["name"]=="Smeargle" and x["ability"]=="Technician" for x in report["rows"]))
        self.assertTrue(any(x["name"]=="Parasect" and x["optional_evolution"] for x in report["rows"]))
        for row in report["rows"]:
            self.assertTrue(row["ability_unconfirmed"])
            ghost=next(t for t in row["targets"] if t["name"]=="Gastly")
            self.assertIsNone(ghost["swipe_attempts"])
        self.assertTrue(any(x["name"]=="Butterfree" for x in report["no_false_swipe"]))

    @unittest.skipUnless(__import__("catcher_score").configured_cache_dir().exists(),"verified Gen VII cache unavailable")
    def test_real_cli_writes_both_cards_and_explicit_assumptions(self):
        import subprocess,tempfile,os,json
        with tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR")) as folder:
            result=subprocess.run([sys.executable,str(Path(__file__).resolve().parents[1]/"catcher_efficiency.py"),"--species","paras,smeargle,butterfree,kricketot,gastly","--output-dir",folder],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            for name in ["catchers.png","false-swipe-efficiency.png"]:
                self.assertTrue((Path(folder)/name).exists(),"Real CLI must render "+name)
            report=json.loads((Path(folder)/"efficiency.json").read_text())
            self.assertTrue(report["assumptions"]["actual_ability_unknown"])
            self.assertNotIn("capture_probability",report)

    def test_unsupported_assumptions_fail_closed_and_zero_rolls_self_loop(self):
        e=self.module()
        with self.assertRaises(ValueError):
            e.damage_rolls(level=30,attack=26,defense=27,attacker_types=["Normal"],defender_types=["Electric"],ability="Sharpness")
        with self.assertRaises(ValueError):e.expected_actions(0,[1])
        self.assertEqual(e.expected_actions(5,[0,2]),4)
        self.assertEqual(e.expected_actions(2,[100]*16),1)
        with self.assertRaises(ValueError):e.stat(20,30,iv=32)

if __name__=="__main__":unittest.main()
