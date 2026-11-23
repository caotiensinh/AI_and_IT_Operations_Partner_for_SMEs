import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("audit", ROOT/"scripts/inventory_branches.py")
audit=importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)

class InventoryTests(unittest.TestCase):
    def test_classifications(self):
        self.assertEqual(audit.classify(0, 25),"ALREADY_INCLUDED")
        self.assertEqual(audit.classify(1, 0),"UNMERGED_LINEAR_REVIEW")
        self.assertEqual(audit.classify(3, 2),"DIVERGED_REVIEW")
    def test_no_token_fails_closed(self):
        with self.assertRaises(ValueError): audit.request("/repos/owner/repo", "")
    def test_invalid_repo_fails_closed(self):
        with self.assertRaises(ValueError): audit.inventory("../../etc", "dummy")
    def test_all_branches_are_reported_but_never_merge_authorized(self):
        calls = []
        def mock(path, token):
            calls.append(path)
            if path.endswith("/branches/main"): return {"commit": {"sha": "a"*40}}
            if "branches?per_page=100" in path: return [
                {"name":"main"},{"name":"feat/a"},{"name":"feat/b"},{"name":"old"}]
            if "/compare/" in path:
                tail=path.rsplit("...",1)[1]
                if tail == "old": return {"ahead_by":0,"behind_by":5}
                if tail == "feat%2Fa": return {"ahead_by":2,"behind_by":0}
                if tail == "feat%2Fb": return {"ahead_by":3,"behind_by":2}
            raise AssertionError("Unexpected API path "+path)
        with patch.object(audit,"request",side_effect=mock):
            result=audit.inventory("caotiensinh/AI_and_IT_Operations_Partner_for_SMEs","dummy")
        self.assertFalse(result["merge_authorized"])
        self.assertEqual(result["branch_count"],4)
        self.assertEqual([x["classification"] for x in result["results"]],
            ["UNMERGED_LINEAR_REVIEW","DIVERGED_REVIEW","ALREADY_INCLUDED"])
        self.assertTrue(all(x["safe_to_merge"] is False for x in result["results"]))
        self.assertFalse(result["failures"])
    def test_api_failure_is_unknown_not_included(self):
        def mock(path, token):
            if path.endswith("/branches/main"): return {"commit":{"sha":"b"*40}}
            if "branches?" in path: return [{"name":"main"},{"name":"unavailable"}]
            raise ValueError("API failed")
        with patch.object(audit,"request",side_effect=mock):
            result=audit.inventory("user/repo","dummy")
        self.assertEqual(result["results"][0]["classification"],"UNKNOWN_BLOCKED")
        self.assertEqual(len(result["failures"]),1)

if __name__=="__main__":
    unittest.main()
