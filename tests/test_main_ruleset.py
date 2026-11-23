"""Read-only GitHub main ruleset audit regressions."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("rules",ROOT/"scripts/audit_main_ruleset.py")
rules=importlib.util.module_from_spec(spec)
spec.loader.exec_module(rules)

def sample():
    return [{"id":7,"target":"branch","enforcement":"active",
     "conditions":{"ref_name":{"include":["~DEFAULT_BRANCH"],"exclude":[]}},
     "rules":[
        {"type":"pull_request","parameters":{"required_approving_review_count":1,
           "dismiss_stale_reviews_on_push":True}},
        {"type":"required_status_checks","parameters":{"required_status_checks":[{"context":"PR governance contract"}]}},
        {"type":"non_fast_forward"},
        {"type":"deletion"}]}]

class RulesetTests(unittest.TestCase):
    def test_valid_config(self):self.assertEqual(rules.rulecheck(sample()),[])
    def test_no_ruleset(self):self.assertTrue(rules.rulecheck([]))
    def test_audit_no_approval(self):
        s=sample();s[0]["rules"][0]["parameters"]["required_approving_review_count"]=0
        self.assertTrue(any("approval" in x for x in rules.rulecheck(s)))
    def test_audit_missing_check(self):
        s=sample();s[0]["rules"][1]["parameters"]["required_status_checks"]=[]
        self.assertTrue(any("governance" in x for x in rules.rulecheck(s)))
    def test_audit_stale_approval_not_dismissed(self):
        s=sample();s[0]["rules"][0]["parameters"]["dismiss_stale_reviews_on_push"]=False
        self.assertTrue(any("Stale" in x for x in rules.rulecheck(s)))
    def test_inactive_ruleset(self):
        s=sample();s[0]["enforcement"]="evaluate"
        self.assertTrue(rules.rulecheck(s))
    def test_wrong_branch(self):
        s=sample();s[0]["conditions"]["ref_name"]["include"]=["refs/heads/develop"]
        self.assertTrue(rules.rulecheck(s))
    def test_read_only_audit(self):
        obj=sample()[0]
        with patch.object(rules,"fetch",side_effect=[[{"id":7,"target":"branch","enforcement":"active"}],obj]) as f:
            self.assertEqual(rules.audit("owner/repo","token"),[])
        self.assertEqual(f.call_count,2)

if __name__=="__main__":
    unittest.main()
