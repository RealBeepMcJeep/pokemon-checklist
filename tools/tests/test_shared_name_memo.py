"""Bounded memoization must cache pure TEXT, never an input object or source validity."""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import showdown_text as text


class SharedNameMemoTests(unittest.TestCase):
    def setUp(self):
        cache = getattr(text, "_normalize_name_text", None)
        if cache is not None:
            cache.cache_clear()

    def tearDown(self):
        self.setUp()

    def test_oversized_names_are_not_retained_in_the_bounded_name_cache(self):
        literal = "é" * 257
        with mock.patch.object(text.unicodedata, "normalize", wraps=text.unicodedata.normalize) as fold:
            self.assertEqual(text.normalize_name(literal), "e" * 257)
            self.assertEqual(text.normalize_name(literal), "e" * 257)
        self.assertEqual(fold.call_count, 2, "an oversized individual key must not be retained")

    def test_unhashable_and_mutating_display_objects_are_converted_on_every_use(self):
        class Display:
            name = "Flabébé"
            def __str__(self):
                return self.name
        value = Display()
        self.assertEqual(text.normalize_name(value), "flabebe")
        value.name = "Mr. Mime"
        self.assertEqual(text.normalize_name(value), "mrmime")
        for value, expected in [(["Nidoran♀"], "nidoran"), ({"é": 7}, "e7"),
                                (None, "none"), (True, "true"), (123, "123"),
                                ("Flabe\u0301be\u0301", "flabebe"), ("Å", "a")]:
            with self.subTest(value=value):
                self.assertEqual(text.normalize_name(value), expected)

    def test_entry_limit_evicts_without_changing_results(self):
        for i in range(5000):
            self.assertEqual(text.normalize_name(f"Flabébé-{i}"), f"flabebe{i}")
        info = text._normalize_name_text.cache_info()
        self.assertEqual(info.maxsize, 4096)
        self.assertEqual(info.currsize, 4096)
        before = info.misses
        self.assertEqual(text.normalize_name("Flabébé-0"), "flabebe0")
        self.assertEqual(text._normalize_name_text.cache_info().misses, before + 1)
        # Exactly-at-limit inputs are retained; oversized ones bypass above.
        literal = "é" * 256
        with mock.patch.object(text.unicodedata, "normalize", wraps=text.unicodedata.normalize) as fold:
            self.assertEqual(text.normalize_name(literal), "e" * 256)
            self.assertEqual(text.normalize_name(literal), "e" * 256)
        self.assertEqual(fold.call_count, 1)

    def test_repeated_literal_names_do_not_repeat_unicode_decomposition(self):
        literal = "Flabébé · memo mechanism witness #11"
        with mock.patch.object(text.unicodedata, "normalize", wraps=text.unicodedata.normalize) as fold:
            results = [text.normalize_name(literal) for _ in range(100)]
        self.assertEqual(results, ["flabebememomechanismwitness11"] * 100)
        self.assertEqual(fold.call_count, 1, "same admitted literal must fold once, not once per species scan")


if __name__ == "__main__":
    unittest.main()
