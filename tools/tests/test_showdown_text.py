import unittest

from tools.showdown_text import block, field, list_field, object_after, top_blocks


class ShowdownTextTests(unittest.TestCase):
    TEXT = """exports.BattlePokedex = {
\tmr-mime: {species: 'Mr. Mime', evos: ['mr-rime'], nested: {value: 1}},
\t\"charizard\": {species: \"Charizard\", types: [\"Fire\", \"Flying\"]},
};
"""

    def test_top_blocks_keep_nested_objects_together(self) -> None:
        parsed = dict(top_blocks(self.TEXT))
        self.assertIn("mr-mime", parsed)
        self.assertIn("nested: {value: 1}", parsed["mr-mime"])
        self.assertEqual(block(self.TEXT, "Mr. Mime"), parsed["mr-mime"])

    def test_scalar_list_and_object_parsers_preserve_showdown_text(self) -> None:
        body = block(self.TEXT, "charizard")
        self.assertEqual(field(body, "species"), "Charizard")
        self.assertEqual(list_field(body, "types", str.lower), ["fire", "flying"])
        self.assertEqual(object_after(block(self.TEXT, "mr-mime"), "nested"), "{value: 1}")


if __name__ == "__main__":
    unittest.main()
