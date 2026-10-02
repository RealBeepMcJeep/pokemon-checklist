from pathlib import Path
import copy
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.build_qr_catalog import (
    inspect_source_image, _from_mediawiki_sha1, verify_catalog, _protocol_comparison,
)
from tools.qr_codec import decode_png, write_qr_png

FIXTURE = Path(__file__).parent / "fixtures" / "qr-sources" / "Rowlet_VII_QR.png"


class QRCatalogTests(unittest.TestCase):
    def test_mediawiki_source_sha1_hex_is_compared_as_binary(self):
        self.assertEqual(
            _from_mediawiki_sha1("3862f97626e20c2c0a8a920c244da1d55009ad04"),
            bytes.fromhex("3862f97626e20c2c0a8a920c244da1d55009ad04"),
        )

    def test_catalog_command_is_runnable_from_repository_root(self):
        root = Path(__file__).resolve().parents[2]
        result = subprocess.run(
            [sys.executable, "tools/build_qr_catalog.py", "--help"],
            cwd=root, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("verify-only", result.stdout)

    def test_real_category_cross_audit_compares_shared_and_ultra_only_payloads(self):
        root = Path(__file__).resolve().parents[2]
        manifest = json.loads((root / "references/qr-codes/manifest.json").read_text())
        audit = manifest["crossCategoryProtocolAudit"]
        shared = audit["sharedRowletButterfree"]
        self.assertEqual({row["species"]["name"] for row in shared}, {"Rowlet", "Butterfree"})
        older = audit["ultraOnlyOlderSpecies"]
        self.assertTrue({"Ampharos", "Buneary"} <= {row["species"]["name"] for row in older})
        for row in shared + older:
            self.assertEqual((row["family"], row["keyIndex"], row["payloadBytes"]),
                             ("ordinary-dex", 3, 108))
            self.assertEqual(row["framing"]["markerOffset"], 98)
            self.assertEqual(row["framing"]["preMarkerHex"], "0000")
            self.assertEqual(row["framing"]["suffixHex"], "0000")
        self.assertEqual(audit["ultraOnlyUSUMAdditions"], [])

    def test_cross_audit_finds_a_usum_added_dusk_form_if_present(self):
        row = {
            "source": {"title": "File:Rockruff-Dusk VII QR.png",
                       "categories": ["ultra-sun-ultra-moon"]},
            "decoded": {"species": {"id": 744, "name": "Rockruff"}, "formId": 1},
            "audit": {"family": "ordinary-dex", "keyIndex": 3},
            "payload": {"byteLength": 108, "rawSha256": "fixture", "framing": {}},
        }
        audit = _protocol_comparison([row])
        self.assertEqual(
            [item["sourceTitle"] for item in audit["ultraOnlyUSUMAdditions"]],
            ["File:Rockruff-Dusk VII QR.png"],
        )

    def test_offline_manifest_verify_rechecks_each_original_and_signature(self):
        root = Path(__file__).resolve().parents[2]
        catalog = root / "references/qr-codes"
        manifest = json.loads((catalog / "manifest.json").read_text())
        report = verify_catalog(catalog)
        self.assertTrue(report["ok"], report["errors"][:3])
        self.assertEqual(report["checked"], len(manifest["records"]))
        expected_verified = sum(
            row["audit"]["status"] == "verified-ordinary-dex"
            for row in manifest["records"]
        )
        self.assertEqual(report["signatureVerified"], expected_verified)

    def test_offline_verifier_rejects_decoded_and_length_metadata_drift(self):
        root = Path(__file__).resolve().parents[2]
        source_catalog = root / "references/qr-codes"
        source_manifest = json.loads((source_catalog / "manifest.json").read_text())
        source_row = next(
            row for row in source_manifest["records"]
            if row["source"]["title"] == "File:Rowlet VII QR.png"
        )
        mutations = (
            ("decoded", "bothGendersFlag", "decoded-fields-mismatch"),
            ("image", "bytes", "image-size-mismatch"),
            ("payload", "byteLength", "payload-length-mismatch"),
        )
        for section, field, expected_status in mutations:
            with self.subTest(section=section, field=field), tempfile.TemporaryDirectory() as directory:
                target = Path(directory)
                (target / "images").mkdir()
                row = copy.deepcopy(source_row)
                source_image = source_catalog / row["image"]["file"]
                shutil.copyfile(source_image, target / "images" / "rowlet.png")
                row["image"]["file"] = "images/rowlet.png"
                row[section][field] = row[section][field] ^ 1
                (target / "manifest.json").write_text(
                    json.dumps({"records": [row]})
                )
                report = verify_catalog(target)
                self.assertFalse(report["ok"])
                self.assertEqual(report["errors"][0]["status"], expected_status)

    def test_record_keeps_memberships_source_hashes_and_verified_fields(self):
        names = {722: "Rowlet"}
        record = inspect_source_image(
            FIXTURE,
            {"pageid": 304912, "title": "File:Rowlet VII QR.png",
             "original": "https://example.invalid/Rowlet.png", "sha1": "source-sha1"},
            {"sun-moon", "ultra-sun-ultra-moon"},
            names,
        )
        self.assertEqual(record["source"]["categories"], ["sun-moon", "ultra-sun-ultra-moon"])
        self.assertEqual(record["source"]["title"], "File:Rowlet VII QR.png")
        self.assertEqual(record["source"]["sourceSha1"], "source-sha1")
        self.assertEqual(record["imageSha256"], hashlib.sha256(FIXTURE.read_bytes()).hexdigest())
        self.assertEqual(record["audit"]["status"], "verified-ordinary-dex")
        self.assertEqual(record["decoded"]["species"], {"id": 722, "name": "Rowlet"})
        self.assertEqual(record["decoded"]["formId"], 0)
        self.assertEqual(record["decoded"]["genderCode"], 0)
        self.assertFalse(record["decoded"]["shiny"])
        self.assertEqual(len(record["payload"]["rawHex"]), 216)
        self.assertEqual(len(record["payload"]["bodyHex"]), 192)

    def test_unsupported_key_is_retained_and_flagged_with_key_index(self):
        raw = bytearray(decode_png(FIXTURE))
        marker = raw.rfind(b"POKE")
        raw[marker + 4:marker + 8] = (4).to_bytes(4, "little")
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "unsupported.png"
            write_qr_png(bytes(raw), image)
            record = inspect_source_image(
                image,
                {"pageid": 2, "title": "File:Unsupported VII QR.png",
                 "original": "https://example.invalid/unsupported.png", "sha1": "not-used"},
                {"ultra-sun-ultra-moon"},
                {722: "Rowlet"},
            )
        self.assertEqual(record["audit"]["status"], "unsupported-key-family")
        self.assertEqual(record["audit"]["unsupportedKeyIndex"], 4)
        self.assertEqual(record["payload"]["rawHex"], bytes(raw).hex())
        self.assertEqual(record["payload"]["framing"]["keyIndex"], 4)

    def test_missing_canonical_species_join_is_explicit_not_guessed(self):
        record = inspect_source_image(
            FIXTURE,
            {"pageid": 1, "title": "File:Rowlet VII QR.png",
             "original": "https://example.invalid/Rowlet.png", "sha1": "not-used"},
            {"sun-moon"},
            {},
        )
        self.assertEqual(record["decoded"]["species"], {"id": 722, "name": None})
        self.assertTrue(record["audit"]["canonicalSpeciesUnknown"])
        self.assertIsNone(record["audit"]["sourceLabelMismatch"])

    def test_source_label_mismatch_is_flagged_not_remapped(self):
        record = inspect_source_image(
            FIXTURE,
            {"pageid": 1, "title": "File:Butterfree VII QR.png",
             "original": "https://example.invalid/Butterfree.png", "sha1": "not-used"},
            {"ultra-sun-ultra-moon"},
            {722: "Rowlet"},
        )
        self.assertEqual(record["decoded"]["species"]["name"], "Rowlet")
        self.assertTrue(record["audit"]["sourceLabelMismatch"])

    def test_source_label_prefix_must_match_species_name(self):
        record = inspect_source_image(
            FIXTURE,
            {"pageid": 1, "title": "File:Not Rowlet VII QR.png",
             "original": "https://example.invalid/Not-Rowlet.png", "sha1": "not-used"},
            {"sun-moon"},
            {722: "Rowlet"},
        )
        self.assertTrue(record["audit"]["sourceLabelMismatch"])


if __name__ == "__main__":
    unittest.main()
