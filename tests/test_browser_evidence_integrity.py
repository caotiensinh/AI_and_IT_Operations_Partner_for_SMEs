"""Boundary and negative tests: evidence manifest integrity is not user acceptance."""
import hashlib
import importlib.util
import json
import struct
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("browser_evidence", ROOT / "scripts/validate_browser_evidence.py")
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)
SHA = "a" * 40


class EvidenceIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)
        entries = []
        for name, (width, height) in validator.EXPECTED.items():
            raw = (b"\x89PNG\r\n\x1a\n" + struct.pack(">I",13) + b"IHDR"
                   + struct.pack(">II",width,height) + b"z" * 5100)
            (self.directory / (name + ".png")).write_bytes(raw)
            entries.append({
                "name":name,"file":name+".png",
                "viewport":{"width":width,"height":height},
                "actual_png":{"width":width,"height":height,"bytes":len(raw),
                              "sha256":hashlib.sha256(raw).hexdigest()}
            })
        self.manifest = {
            "evidence_type":"INTEGRATION_TEST_NOT_USER_ACCEPTANCE",
            "synthetic_data":True,"production_ready":False,
            "acceptance_status":"UNREVIEWED","archival_status":"NOT_VERIFIED",
            "capture_integrity_verified":True,"source_sha":SHA,
            "expected_screen_count":13,"actual_screen_count":13,"screens":entries
        }
        self.write()

    def write(self):
        (self.directory / "manifest.json").write_text(json.dumps(self.manifest))

    def test_matching_capture_integrity_does_not_imply_acceptance(self):
        result = validator.validate(self.directory, SHA)
        self.assertEqual(result["screens"],13)
        self.assertEqual(result["archive"],"NOT_VERIFIED")
        self.assertEqual(result["human_acceptance"],"PENDING")

    def test_missing_capture_rejected(self):
        (self.directory / self.manifest["screens"][0]["file"]).unlink()
        with self.assertRaises(ValueError):
            validator.validate(self.directory,SHA)

    def test_duplicate_capture_rejected(self):
        self.manifest["screens"][1]["name"]=self.manifest["screens"][0]["name"]
        self.write()
        with self.assertRaises(ValueError):
            validator.validate(self.directory,SHA)

    def test_unsafe_capture_name_rejected(self):
        self.manifest["screens"][1]["name"]="../../escape"
        self.write()
        with self.assertRaises(ValueError):
            validator.validate(self.directory,SHA)

    def test_changed_bytes_sha_mismatch_denied(self):
        path=self.directory/self.manifest["screens"][0]["file"]
        data=bytearray(path.read_bytes());data[200]^=1;path.write_bytes(data)
        with self.assertRaises(ValueError):
            validator.validate(self.directory,SHA)

    def test_wrong_sha_wrong_dimensions_and_forged_acceptance_denied(self):
        with self.assertRaises(ValueError):
            validator.validate(self.directory,"b"*40)
        self.manifest["screens"][0]["viewport"]["width"]=999
        self.write()
        with self.assertRaises(ValueError):
            validator.validate(self.directory,SHA)
        self.manifest["screens"][0]["viewport"]["width"]=1440
        self.manifest["acceptance_status"]="ACCEPTED"
        self.write()
        with self.assertRaises(ValueError):
            validator.validate(self.directory,SHA)

    def test_unexpected_file_denied(self):
        (self.directory/"stale.png").write_bytes(b"x")
        with self.assertRaises(ValueError):
            validator.validate(self.directory,SHA)


if __name__=="__main__":
    unittest.main()
