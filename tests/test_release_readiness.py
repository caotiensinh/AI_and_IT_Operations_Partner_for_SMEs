"""Contract regressions for the fail-closed production readiness gate."""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from check_release_readiness import REQUIRED, validate

class ReleaseReadinessTests(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads((ROOT / "release/readiness.json").read_text(encoding="utf-8"))

    def test_current_manifest_is_valid_but_blocked(self):
        self.assertFalse(validate(self.manifest))
        self.assertEqual(self.manifest["status"], "blocked")

    def test_missing_gate_fails_closed(self):
        del self.manifest["checks"][REQUIRED[0]]
        with self.assertRaises(ValueError):
            validate(self.manifest)

    def test_string_true_not_allowed(self):
        self.manifest["checks"][REQUIRED[0]] = "true"
        with self.assertRaises(ValueError):
            validate(self.manifest)

    def test_unsubstantiated_pass_rejected(self):
        self.manifest["checks"][REQUIRED[0]] = True
        with self.assertRaisesRegex(ValueError, "PASS requires evidence"):
            validate(self.manifest)

    def test_fully_evidenced_ready_manifest(self):
        self.manifest["checks"] = {key: True for key in REQUIRED}
        self.manifest["evidence"] = {key: "https://github.com/example/evidence/" + key for key in REQUIRED}
        self.manifest["status"] = "ready"
        self.assertTrue(validate(self.manifest))

    def test_inconsistent_status_rejected(self):
        self.manifest["status"] = "ready"
        with self.assertRaises(ValueError):
            validate(self.manifest)

    def test_untrusted_evidence_rejected(self):
        self.manifest["evidence"][REQUIRED[0]] = "http://untrusted.local"
        with self.assertRaises(ValueError):
            validate(self.manifest)

    def test_production_cli_blocks_and_schema_cli_passes(self):
        script = ROOT / "scripts/check_release_readiness.py"
        base = [sys.executable, str(script)]
        self.assertEqual(subprocess.run(base, capture_output=True).returncode, 0)
        self.assertEqual(subprocess.run(base + ["--check-production"], capture_output=True).returncode, 1)

    def test_invalid_json_cli_returns_two(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "invalid.json"
            path.write_text("{invalid", encoding="utf-8")
            result = subprocess.run([sys.executable, str(ROOT / "scripts/check_release_readiness.py"), "--manifest", str(path)], capture_output=True)
            self.assertEqual(result.returncode, 2)

if __name__ == "__main__":
    unittest.main()
