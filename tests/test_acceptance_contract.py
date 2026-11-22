"""Negative, boundary, and positive tests for acceptance ledger."""
import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("check_acceptance", ROOT / "scripts/check_acceptance.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
SHA = "a" * 40

class AcceptanceContractTests(unittest.TestCase):
    def setUp(self):
        self.record = json.loads((ROOT / "acceptance/schema-example.json").read_text())
    def complete(self):
        r = self.record
        r.update(status="ACCEPTED",level="L4",commit_sha=SHA,owner="builder",blockers=[])
        r["criteria"][0].update(verified=True,evidence=["https://github.com/example/test"])
        r["gates"]={k:True for k in mod.GATES}
        r["review"].update(reviewer="independent-reviewer",decision="APPROVED",commit_sha=SHA,environment="staging",evidence=["https://github.com/example/review"])
        return r
    def test_template_is_not_complete(self):
        self.assertFalse(mod.validate(self.record))
    def test_valid_accepted_record(self):
        self.assertTrue(mod.validate(self.complete()))
    def test_missing_gate_rejected(self):
        del self.record["gates"]["security"]
        with self.assertRaises(ValueError): mod.validate(self.record)
    def test_string_boolean_rejected(self):
        self.record["gates"]["persist"]="true"
        with self.assertRaises(ValueError): mod.validate(self.record)
    def test_false_pass_claim_rejected(self):
        self.record["status"]="ACCEPTED"
        with self.assertRaises(ValueError): mod.validate(self.record)
    def test_verified_without_evidence_rejected(self):
        self.record["criteria"][0]["verified"]=True
        with self.assertRaises(ValueError): mod.validate(self.record)
    def test_self_approval_rejected(self):
        self.complete()["review"]["reviewer"]="builder"
        with self.assertRaises(ValueError): mod.validate(self.record)
    def test_stale_sha_rejected(self):
        self.complete()["review"]["commit_sha"]="b"*40
        with self.assertRaises(ValueError): mod.validate(self.record)
    def test_wrong_environment_rejected(self):
        self.complete()["review"]["environment"]="production"
        with self.assertRaises(ValueError): mod.validate(self.record)
    def test_blocked_without_reason_rejected(self):
        self.record.update(status="BLOCKED",blockers=[])
        with self.assertRaises(ValueError): mod.validate(self.record)
    def test_review_ready_not_done(self):
        self.complete().update(status="READY_FOR_REVIEW",level="L3")
        self.record["review"]["decision"]=""
        self.assertFalse(mod.validate(self.record))
    def test_l3_without_integration_rejected(self):
        self.record.update(level="L3",commit_sha=SHA)
        self.record["gates"]["functional"]=True
        with self.assertRaises(ValueError): mod.validate(self.record)
    def test_cli_counts_incomplete_and_blocks_acceptance(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"EXAMPLE-ONLY.json"
            p.write_text(json.dumps(self.record))
            base=[sys.executable,str(ROOT/"scripts/check_acceptance.py"),"--directory",d]
            self.assertEqual(subprocess.run(base,capture_output=True).returncode,0)
            self.assertEqual(subprocess.run(base+["--require-accepted"],capture_output=True).returncode,1)
    def test_cli_invalid_record_exit_2(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d)/"bad.json").write_text("{}")
            cmd=[sys.executable,str(ROOT/"scripts/check_acceptance.py"),"--directory",d]
            self.assertEqual(subprocess.run(cmd,capture_output=True).returncode,2)

    def test_existing_ui_records_remain_unaccepted_without_live_evidence(self):
        for record_id in ("UI-OVERVIEW", "UI-ASSETS", "UI-MONITORING"):
            with self.subTest(record=record_id):
                record = json.loads((ROOT / "acceptance/records" / (record_id + ".json")).read_text(encoding="utf-8"))
                self.assertEqual(record["id"], record_id)
                self.assertEqual(record["level"], "L1")
                self.assertEqual(record["status"], "IN_PROGRESS")
                self.assertFalse(mod.validate(record))
                self.assertTrue(record["blockers"])
                self.assertTrue(all(not criterion["verified"] for criterion in record["criteria"]))

if __name__ == "__main__":
    unittest.main()
