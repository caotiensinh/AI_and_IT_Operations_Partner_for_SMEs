"""Fail-closed ruleset installer offline tests; never calls real GitHub."""
import importlib.util
from pathlib import Path
from unittest.mock import patch
import unittest

root=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("installer",root/"scripts/install_main_ruleset.py")
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
SHA="a"*40

class RulesetInstallerTests(unittest.TestCase):
    def test_policy_has_required_no_bypass_rules(self):
        d=m.desired()
        self.assertEqual(d["enforcement"],"active")
        self.assertEqual(d["bypass_actors"],[])
        self.assertEqual(d["conditions"]["ref_name"]["include"],["refs/heads/main"])
        types={r["type"]:r for r in d["rules"]}
        self.assertIn("deletion",types)
        self.assertIn("non_fast_forward",types)
        self.assertGreaterEqual(types["pull_request"]["parameters"]["required_approving_review_count"],1)
        self.assertTrue(types["pull_request"]["parameters"]["require_last_push_approval"])
        self.assertTrue(types["required_status_checks"]["parameters"]["strict_required_status_checks_policy"])
        contexts=[x["context"] for x in types["required_status_checks"]["parameters"]["required_status_checks"]]
        self.assertEqual(set(contexts),set(m.CHECKS))
    def test_dry_run_never_posts(self):
        with patch.object(m,"inspect",return_value=(SHA,[])),patch.object(m,"api_request") as req:
            self.assertFalse(m.install("test",SHA,False))
            req.assert_not_called()
    def test_main_sha_conflict_aborts_without_posts(self):
        with patch.object(m,"inspect",return_value=("b"*40,[])),patch.object(m,"api_request") as req:
            with self.assertRaisesRegex(ValueError,"Main changed"):m.install("test",SHA,True)
            req.assert_not_called()
    def test_existing_ruleset_aborts_without_posts(self):
        existing=[{"name":m.RULESET_NAME,"enforcement":"active","target":"branch"}]
        with patch.object(m,"inspect",return_value=(SHA,existing)),patch.object(m,"api_request") as req:
            with self.assertRaisesRegex(ValueError,"already exists"):m.install("test",SHA,True)
            req.assert_not_called()
    def test_other_active_ruleset_aborts(self):
        existing=[{"name":"old","enforcement":"active","target":"branch"}]
        with patch.object(m,"inspect",return_value=(SHA,existing)),patch.object(m,"api_request") as req:
            with self.assertRaisesRegex(ValueError,"Existing active"):m.install("test",SHA,True)
            req.assert_not_called()
    def test_apply_posts_exactly_once(self):
        with patch.object(m,"inspect",return_value=(SHA,[])),patch.object(m,"api_request",return_value={"name":m.RULESET_NAME,"enforcement":"active","id":1}) as req:
            self.assertTrue(m.install("test",SHA,True))
            req.assert_called_once_with("POST","/rulesets","test",m.desired())
    def test_invalid_expected_sha_blocks_early(self):
        with patch.object(m,"inspect") as req:
            with self.assertRaises(ValueError):m.install("test","bad",True)
            req.assert_not_called()
    def test_apply_requires_explicit_repository(self):
        self.assertEqual(m.main(["--expected-main-sha",SHA,"--apply"]),2)

if __name__=="__main__":
    unittest.main()
