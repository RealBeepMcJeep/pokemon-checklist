import hashlib
import io
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from tools import build_ball_sprites as balls

class BallSpriteTests(unittest.TestCase):
    def test_real_pinned_inputs_rebuild_committed_atlas(self):
        self.assertEqual(len(balls.MANIFEST["balls"]), 22)
        self.assertEqual(balls.atlas_bytes(balls.DEFAULT_CACHE), balls.OUT.read_bytes())
        self.assertEqual(Image.open(io.BytesIO(balls.atlas_bytes(balls.DEFAULT_CACHE))).size, (240,90))
    def test_corrupt_hash_and_dimensions_fail_closed(self):
        frame = balls.MANIFEST["balls"][0]
        with self.assertRaisesRegex(ValueError, "hash"):
            balls.validate(b"bad", frame)
        image = Image.new("RGBA", (1,1)); out=io.BytesIO(); image.save(out,format="PNG"); raw=out.getvalue()
        with self.assertRaisesRegex(ValueError, "dimensions"):
            balls.validate(raw, {**frame,"sha256":hashlib.sha256(raw).hexdigest(),"bytes":len(raw)})
    def test_missing_cache_explains_refresh(self):
        with tempfile.TemporaryDirectory() as path:
            with self.assertRaisesRegex(ValueError,"refresh"):
                balls.atlas_bytes(Path(path))
