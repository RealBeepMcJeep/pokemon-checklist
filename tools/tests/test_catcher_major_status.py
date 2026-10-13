"""Mutually exclusive major statuses must not inflate catcher utility."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import catcher_score as cs


class MajorStatusTests(unittest.TestCase):
    def test_sleep_paralysis_freeze_are_alternatives(self):
        parts = [dict(category='sleep', value=60),
                 dict(category='falseswipe', value=25),
                 dict(category='paralysis', value=7),
                 dict(category='freeze', value=10)]
        self.assertEqual(cs.total_from_parts(parts), 85)

    def test_report_parts_do_not_claim_two_major_status_benefits(self):
        result = cs.score_parts('testmon',
            {'testmon': '{ learnset: { sleeppowder: ["7L10"], stunspore: ["7L10"] } }'},
            {'testmon': '{ abilities: {0: "Compound Eyes"} }'},
            {'sleeppowder': '{ accuracy: 75, status: "slp" }',
             'stunspore': '{ accuracy: 75, status: "par" }'})
        self.assertEqual([p['category'] for p in result['parts']], ['sleep'])


if __name__ == '__main__':
    unittest.main()
