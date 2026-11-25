"""PR governance rejects missing records, false acceptance claims and malformed metadata."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("prgov", ROOT / "scripts/check_pr_governance.py")
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)
spec2 = importlib.util.spec_from_file_location("acceptance", ROOT / "scripts/check_acceptance.py")
a = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(a)

class GovernanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.record = json.loads((ROOT / "acceptance/schema-example.json").read_text(encoding="utf-8"))
        self.record["id"] = "TEST-GOV"
        self.save()
        self.body = "Change-Type: governance\nAcceptance-IDs: TEST-GOV\n"
    def save(self):
        (self.root / "TEST-GOV.json").write_text(json.dumps(self.record), encoding="utf-8")
    def check(self, body=None, files=None):
        return p.validate_pr(self.body if body is None else body, self.root, ["AGENTS.md", "acceptance/records/TEST-GOV.json"] if files is None else files, validator=a.validate)
    def test_in_progress_record_is_valid_but_not_accepted(self):
        self.assertEqual(self.check()["ids"],["TEST-GOV"])
        self.assertEqual(self.record["status"],"IN_PROGRESS")
    def test_missing_metadata_rejected(self):
        with self.assertRaises(ValueError): self.check("PR summary")
    def test_duplicate_metadata_rejected(self):
        with self.assertRaises(ValueError): self.check(self.body+"Acceptance-IDs: TEST-GOV\n")
    def test_missing_acceptance_record_rejected(self):
        with self.assertRaises(ValueError): self.check("Change-Type: fix\nAcceptance-IDs: OTHER-GOV\n")
    def test_duplicate_ids_rejected(self):
        with self.assertRaises(ValueError): self.check("Change-Type: fix\nAcceptance-IDs: TEST-GOV, TEST-GOV\n")
    def test_invalid_change_type_rejected(self):
        with self.assertRaises(ValueError): self.check("Change-Type: bypass\nAcceptance-IDs: TEST-GOV\n")
    def test_invalid_id_path_rejected(self):
        with self.assertRaises(ValueError): self.check("Change-Type: docs\nAcceptance-IDs: ../TEST-GOV\n")
    def test_no_changed_files_rejected(self):
        with self.assertRaises(ValueError): self.check(files=[])
    def test_stale_record_reuse_rejected(self):
        with self.assertRaisesRegex(ValueError, "must have a changed acceptance"):
            self.check(files=["AGENTS.md"])
    def test_partial_ids_without_changed_record_rejected(self):
        record2 = dict(self.record)
        record2["id"] = "TEST-SECOND"
        (self.root / "TEST-SECOND.json").write_text(json.dumps(record2), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "must have a changed acceptance"):
            self.check("Change-Type: governance\nAcceptance-IDs: TEST-GOV, TEST-SECOND\n")
    def test_forged_accepted_record_rejected(self):
        self.record["status"]="ACCEPTED"
        self.save()
        with self.assertRaises(ValueError): self.check()
    def test_mismatched_record_id_rejected(self):
        self.record["id"]="ANOTHER-ID"
        self.save()
        with self.assertRaises(ValueError): self.check()

if __name__ == "__main__":
    unittest.main()
