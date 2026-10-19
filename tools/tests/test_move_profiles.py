"""The generated move artifact must validate identities and every mode route."""
import copy
import unittest
from tools.validate_data import validate_moves


def fixture():
    routes = [{"via": "tutor", "form": "53:alolan"}]
    return {"schemaVersion": 1, "moves": {"knockoff": {"name": "Knock Off", "type": "Dark"}},
            "finals": {"53:alolan": {"stats": None, "moves": [{"move": "knockoff", "usage": 50,
                "how": [], "profiles": {"sm": [], "usum": routes, "prismatic": copy.deepcopy(routes)}}]}},
            "lines": {"52:alolan": ["53:alolan"]}}


class MoveProfileValidationTests(unittest.TestCase):
    def test_canonical_regional_targets_and_mode_routes_validate(self):
        self.assertEqual(validate_moves(fixture()), [])

    def test_corrupt_mode_routes_are_rejected_not_ignored(self):
        # A legacy numeric entry is valid even before regional support; the
        # regression is that its new profile was never inspected at all.
        data = fixture()
        data["finals"]["53"] = data["finals"].pop("53:alolan")
        data["lines"] = {"52": [53]}
        data["finals"]["53"]["moves"][0]["profiles"]["usum"][0]["via"] = "invented"
        self.assertTrue(validate_moves(data), "Corrupt profile route passed canonical validation")
