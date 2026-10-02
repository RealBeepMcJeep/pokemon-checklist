from pathlib import Path
import json
import subprocess
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.qr_codec import (decode_png, generate_ordinary_payload,
                            verify_ordinary_payload, write_qr_png)


FIXTURES = Path(__file__).parent / "fixtures" / "qr-sources"
ROWLET_PAYLOAD = bytes.fromhex(
    "aefbad81766fd945af38fd352d5062d800ed436a690d411f6a2cabfc6ba8ddd1"
    "52fbf8c5ab128788de39c93840ab22ea092e667497cf958595696891a5ad36d5"
    "d88255865c7b7d3de156575be974590e71f00113f9a42c617413567d550a9da"
    "30000504f4b45030000000000"
)


class QRCodecTests(unittest.TestCase):
    def test_png_decode_preserves_exact_binary_payload(self):
        payload = decode_png(FIXTURES / "Rowlet_VII_QR.png")
        self.assertIsInstance(payload, bytes)
        self.assertEqual(payload, ROWLET_PAYLOAD)
        self.assertIn(b"\x00", payload)
    def test_published_rowlet_ordinary_code_verifies_and_exposes_fields(self):
        record = verify_ordinary_payload(ROWLET_PAYLOAD)
        self.assertEqual(record.key_index, 3)
        self.assertIsInstance(record.body, bytes)
        self.assertEqual(len(record.body), 0x60)
        self.assertEqual(record.species_id, 722)
        self.assertEqual(record.form, 0)

    def test_published_butterfree_archive_png_verifies(self):
        payload = decode_png(FIXTURES / "Butterfree_VII_QR.png")
        record = verify_ordinary_payload(payload)
        self.assertEqual(record.species_id, 12)
        self.assertEqual(record.key_index, 3)

    def test_tampered_signature_is_rejected(self):
        damaged = bytearray(ROWLET_PAYLOAD)
        damaged[12] ^= 1
        with self.assertRaisesRegex(ValueError, "signature"):
            verify_ordinary_payload(bytes(damaged))

    def test_truncated_code_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "framing|truncated"):
            verify_ordinary_payload(ROWLET_PAYLOAD[:-1])

    def test_noncanonical_trailer_bytes_are_rejected(self):
        damaged = bytearray(ROWLET_PAYLOAD)
        damaged[-1] = 1
        with self.assertRaisesRegex(ValueError, "framing|trailer"):
            verify_ordinary_payload(bytes(damaged))

    def test_nonzero_pre_marker_padding_is_rejected(self):
        damaged = bytearray(ROWLET_PAYLOAD)
        damaged[96] = 1
        with self.assertRaisesRegex(ValueError, "framing|padding"):
            verify_ordinary_payload(bytes(damaged))

    def test_unobserved_short_framing_variant_is_rejected(self):
        shortened = ROWLET_PAYLOAD[:96] + ROWLET_PAYLOAD[98:]
        with self.assertRaisesRegex(ValueError, "framing"):
            verify_ordinary_payload(shortened)

    def test_generation_requires_verified_template_for_unknown_header_bytes(self):
        with self.assertRaisesRegex(ValueError, "template"):
            generate_ordinary_payload(25)

    def test_generation_uses_canonical_108_byte_trailer(self):
        payload = generate_ordinary_payload(25, template=ROWLET_PAYLOAD)
        self.assertEqual(len(payload), 108)
        self.assertEqual(payload[96:98], b"\x00\x00")
        marker = payload.rfind(b"POKE")
        self.assertEqual(marker, 98)
        self.assertEqual(payload[marker + 8:], b"\x00\x00")

    def test_generated_older_and_gen7_codes_roundtrip_through_png(self):
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            for species_id in (25, 722):
                payload = generate_ordinary_payload(species_id, template=ROWLET_PAYLOAD)
                record = verify_ordinary_payload(payload)
                self.assertEqual(record.species_id, species_id)
                path = Path(directory) / f"species-{species_id}.png"
                write_qr_png(payload, path)
                self.assertEqual(decode_png(path), payload)

    def test_cli_generates_then_inspects_a_verified_ordinary_png(self):
        import tempfile

        root = Path(__file__).resolve().parents[2]
        cli = root / "tools" / "qr_codec.py"
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "Pikachu.png"
            generated = subprocess.run(
                [sys.executable, str(cli), "generate", "25", "--template",
                 str(FIXTURES / "Rowlet_VII_QR.png"), "--out", str(output)],
                cwd=root, capture_output=True, text=True,
            )
            self.assertEqual(generated.returncode, 0, generated.stderr)
            self.assertTrue(output.is_file())
            generation_report = json.loads(generated.stdout)
            self.assertEqual(generation_report["speciesId"], 25)
            self.assertEqual(generation_report["verification"], "local-signature-and-qr-verified")
            inspected = subprocess.run(
                [sys.executable, str(cli), "inspect", str(output)],
                cwd=root, capture_output=True, text=True,
            )
            self.assertEqual(inspected.returncode, 0, inspected.stderr)
            record = json.loads(inspected.stdout)
            self.assertEqual(record["decoded"]["speciesId"], 25)
            self.assertIn("not console tested", record["consoleAcceptance"])

    def test_generation_from_source_template_preserves_unknown_bytes(self):
        original = verify_ordinary_payload(ROWLET_PAYLOAD).body
        generated = verify_ordinary_payload(
            generate_ordinary_payload(25, template=ROWLET_PAYLOAD)
        ).body
        self.assertEqual(generated[:0x28], original[:0x28])
        self.assertEqual(generated[0x10:0x28], original[0x10:0x28])
        self.assertEqual(generated[0x2E:0x58], original[0x2E:0x58])
        self.assertEqual(generated[0x28:0x2A], b"\x19\x00")
