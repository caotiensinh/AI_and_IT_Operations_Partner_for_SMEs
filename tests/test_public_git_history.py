"""Negative/positive history audit with disposable Git repositories."""
import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "git_history_audit", ROOT / "scripts/check_public_git_history.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args],
                          check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout


class HistoryAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        git(self.root, "init", "-q")
        git(self.root, "config", "user.email", "ci@example.invalid")
        git(self.root, "config", "user.name", "Disposable CI")
        self.commit("README.md", "Public documentation")
    def commit(self, name, data):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(data)
        git(self.root, "add", name)
        git(self.root, "commit", "-qm", "disposable fixture")

    def test_clean_history_and_refs_pass(self):
        findings, stats = audit.scan(self.root)
        self.assertEqual(findings, {})
        self.assertGreater(stats["blobs"], 0)

    def test_deleted_credential_still_found_in_reachable_parent(self):
        self.commit(".env", "DATABASE_URL=fake-example-only")
        git(self.root, "rm", "-q", ".env")
        git(self.root, "commit", "-qm", "remove sensitive fixture")
        findings, stats = audit.scan(self.root)
        self.assertTrue(any("restricted historical filename" in v
                            for values in findings.values() for v in values), findings)
        self.assertGreater(stats["history_paths"], 0)

    def test_secret_only_on_other_branch_is_found(self):
        git(self.root, "checkout", "-qb", "secret-branch")
        # Construct marker dynamically to avoid embedding a fake credential
        # as a contiguous token in the scanner's own tracked test source.
        self.commit("readme-note.txt", "Authorization: " + "ghp_" + "x"*40)
        git(self.root, "checkout", "-q", "master")
        findings, _ = audit.scan(self.root)
        self.assertTrue(any("credential-looking token" in v
                            for values in findings.values() for v in values), findings)

    def test_history_oversized_blob_fails_closed(self):
        self.commit("large-text.txt", "a" * (audit.MAX_SCAN_BYTES + 1))
        findings, stats = audit.scan(self.root)
        self.assertGreater(stats["oversized"], 0)
        self.assertTrue(any("oversized blob not audited" in v
                            for values in findings.values() for v in values))

    def test_tracked_key_deleted_from_current_tree_fails_closed(self):
        self.commit("certs/private.key", "example-only")
        git(self.root, "rm", "-q", "certs/private.key")
        git(self.root, "commit", "-qm", "remove key file")
        findings, _ = audit.scan(self.root)
        self.assertTrue(any("restricted historical filename" in v
                            for values in findings.values() for v in values))

    def test_bad_git_directory_returns_error(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(audit.main(["--root", d]), 2)


if __name__ == "__main__":
    unittest.main()
