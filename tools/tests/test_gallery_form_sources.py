"""Execute the real final-read boundary with synthetic records, never a gallery/API."""
import ast
import copy
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
import held_item_cards
import pokemon_ops
import team_options


def final_read_boundary(path):
    tree = ast.parse(path.read_text())
    def stage(node, name):
        return (isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
                and isinstance(node.value.func, ast.Name) and node.value.func.id == "stage"
                and node.value.args and isinstance(node.value.args[0], ast.Constant)
                and node.value.args[0].value == name)
    for block in ast.walk(tree):
        body = getattr(block, "body", None)
        if not isinstance(body, list):
            continue
        start = next((i for i, node in enumerate(body) if stage(node, "state-verification")), None)
        end = next((i for i, node in enumerate(body) if stage(node, "png-verification")), None)
        if start is not None and end is not None and end > start:
            return compile(ast.fix_missing_locations(ast.Module(body=body[start:end], type_ignores=[])), str(path), "exec")
    raise AssertionError("Actual final source-read boundary not found")


class GalleryFormSourceTests(unittest.TestCase):
    def test_final_read_detects_form_change_without_species_or_star_bridge_change(self):
        scripts = [TOOLS / "gallery_refresh.py"]
        if os.environ.get("GALLERY_LEGACY_SCRIPT"):
            scripts.append(Path(os.environ["GALLERY_LEGACY_SCRIPT"]))
        initial = {"species:89": {"s": "caught"}, "star:89": {"s": "on"},
                   "form:89:alolan": {"s": "caught"}, "starform:89:alolan": {"s": "on"}}
        raw = {"source_caught_ids": [89], "source_seen_ids": [], "source_starred_ids": [89],
               "source_form_records": team_options.form_record_values(initial), "options": []}
        changed = {**initial, "starform:89:alolan": {"s": "off"}}
        for script in scripts:
            with self.subTest(script=script.name):
                code = final_read_boundary(script)
                def run(records):
                    client = SimpleNamespace(read_records=lambda uid: copy.deepcopy(records))
                    ops = SimpleNamespace(FirebaseClient=lambda: client,
                                          validate_record_map=pokemon_ops.validate_record_map,
                                          load_species=lambda: [{"id": 89}])
                    exec(code, {"a": SimpleNamespace(uid="offline-fixture"), "raw": copy.deepcopy(raw),
                                "ops": ops, "stage": lambda name: None, "held_item_cards": held_item_cards})
                run(initial)
                with self.assertRaisesRegex(ValueError, "form"):
                    run(changed)


if __name__ == "__main__":
    unittest.main()
