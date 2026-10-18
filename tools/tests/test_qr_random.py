"""Experimental random controls never change the shared original archive template."""
import unittest
from pathlib import Path
from tools.build_qr_experimental import add_random_sort
from tools.build_qr_gallery import GalleryBuildError

class RandomSortTests(unittest.TestCase):
    def setUp(self):
        self.template = (Path(__file__).resolve().parents[1] / 'qr_gallery_template.html').read_text()

    def test_adds_one_experimental_random_option_without_mutating_template(self):
        result = add_random_sort(self.template)
        self.assertEqual(result.count('<option value="random">Random</option>'), 1)
        self.assertEqual(result.count('id="shuffle-again"'), 1)
        self.assertNotIn('<option value="random">', self.template)
        self.assertIn('for (let i = cards.length - 1; i > 0; i--)', result)
        self.assertIn('shuffleAgain.addEventListener("click", applySort)', result)

    def test_shared_renderer_drift_fails_instead_of_silently_omitting_random(self):
        anchor = '        const order = sortOrder.value;'
        for broken in [self.template.replace(anchor, ''), self.template + anchor]:
            with self.subTest(broken=broken[-40:]), self.assertRaises(GalleryBuildError):
                add_random_sort(broken)

if __name__ == '__main__':
    unittest.main()
