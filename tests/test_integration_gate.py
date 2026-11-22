"""Synthetic GitHub integration-gate regression tests without network or mutation."""
import copy
import json
import unittest
from pathlib import Path

from sme_partner.integration_gate import GateError, evaluate, _safe_spec, GitHubReader
from unittest.mock import patch


ROOT=Path(__file__).resolve().parents[1]
MANIFEST=json.loads((ROOT/"specs/003-sme-business-needs/integration-chain.json").read_text())


class SyntheticReader:
    def __init__(self,manifest,*,change=None, runs=None):
        self.spec=manifest
        self.change=change
        self.calls=[]
        self.prs={}
        foundation=manifest["foundation"]
        self.prs[foundation["merged_pr"]]={
            "state":"closed","merged_at":"2026-11-21T13:47:07Z",
            "merge_commit_sha":foundation["merge_commit"],
            "head":{"sha":foundation["head"],"ref":foundation["base_branch"]}
        }
        prior=None
        for index,node in enumerate(manifest["pull_requests"]):
            ref=(manifest["pull_requests"][index+1]["base"]
                 if index+1<len(manifest["pull_requests"]) else "feat/oidc-deployment-preflight-035")
            self.prs[node["number"]]={
                "number":node["number"],"state":"open","merged_at":None,
                "mergeable":True,
                "head":{"sha":node["head"],"ref":ref,
                        "repo":{"full_name":manifest["repository"]}},
                "base":{"ref":node["base"],"sha":prior["head"] if prior else "0"*40},
            }
            prior=node
        self.runs=runs if runs is not None else [
            {"name":name,"head_sha":manifest["pull_requests"][-1]["head"],
             "status":"completed","conclusion":"success"}
            for name in manifest["terminal_ci"]["workflows"]
        ]

    def get(self,path):
        self.calls.append(path)
        if "/pulls/" in path:
            n=int(path.rsplit("/",1)[-1])
            data=copy.deepcopy(self.prs[n])
            if self.change and n==self.change[0]:
                self.change[1](data)
            return data
        if "/compare/" in path:
            return {"status":"ahead","behind_by":0}
        if "/actions/runs" in path:
            return {"workflow_runs":self.runs}
        raise GateError("Unexpected test route")


class IntegrationGateTests(unittest.TestCase):
    def test_pinned_real_manifest_is_valid_format(self):
        repo,nodes,terminal=_safe_spec(MANIFEST)
        self.assertEqual(repo,"caotiensinh/AI_and_IT_Operations_Partner_for_SMEs")
        self.assertEqual(nodes[-1]["number"],terminal["pr"])
        self.assertEqual(len(nodes),16)
        self.assertEqual(len({x["number"] for x in nodes}),len(nodes))

    def test_all_green_exact_sha_is_ready(self):
        reader=SyntheticReader(MANIFEST)
        report=evaluate(MANIFEST,reader)
        self.assertTrue(report["ready"],report)
        self.assertTrue(all(x["passed"] for x in report["checks"]))
        self.assertEqual(len(reader.calls),19)
        self.assertTrue(reader.calls[-1].endswith("head_sha="+MANIFEST["pull_requests"][-1]["head"]+"&per_page=100"))

    def test_three_dot_compare_url_is_valid_but_traversal_is_rejected(self):
        class FakeResponse:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self,_):return b'{"status":"ahead","behind_by":0}'
        with patch("sme_partner.integration_gate.urlopen",return_value=FakeResponse()):
            result=GitHubReader().get("/repos/owner/repo/compare/abc...main?per_page=1")
            self.assertEqual(result["status"],"ahead")
        for bad in ("/repos/owner/repo/../private",
                    "/repos/owner/repo/%2e%2e/private"):
            with self.subTest(path=bad),self.assertRaises(GateError):
                GitHubReader().get(bad)

    def test_foundation_unmerged_or_not_in_main_blocks(self):
        foundation=MANIFEST["foundation"]
        class BadFoundation(SyntheticReader):
            def get(self,path):
                obj=super().get(path)
                if path.endswith("/pulls/"+str(foundation["merged_pr"])):
                    obj["merged_at"]=None
                return obj
        report=evaluate(MANIFEST,BadFoundation(MANIFEST))
        self.assertFalse(report["ready"])
        self.assertIn("foundation.merged_pr",{x["check"] for x in report["checks"] if not x["passed"]})
        class UnrelatedMain(SyntheticReader):
            def get(self,path):
                obj=super().get(path)
                if "/compare/" in path:
                    obj["status"]="diverged"
                    obj["behind_by"]=1
                return obj
        report=evaluate(MANIFEST,UnrelatedMain(MANIFEST))
        self.assertFalse(report["ready"])
        self.assertIn("foundation.main_ancestor",{x["check"] for x in report["checks"] if not x["passed"]})

    def test_missing_first_foundation_branch_blocks(self):
        first=MANIFEST["pull_requests"][0]["number"]
        def wrong(pr):pr["base"]["ref"]="main"
        report=evaluate(MANIFEST,SyntheticReader(MANIFEST,change=(first,wrong)))
        self.assertFalse(report["ready"])
        self.assertIn("pr."+str(first)+".foundation",
                      {x["check"] for x in report["checks"] if not x["passed"]})

    def test_stale_head_sha_blocks_chain(self):
        def mutate(pr):pr["head"]["sha"]="a"*40
        report=evaluate(MANIFEST,SyntheticReader(MANIFEST,change=(51,mutate)))
        self.assertFalse(report["ready"])
        self.assertIn("pr.51.state",{x["check"] for x in report["checks"] if not x["passed"]})

    def test_merges_closed_forks_and_conflicts_are_blocked(self):
        for mutation in (
            lambda pr:pr.update(state="closed"),
            lambda pr:pr.update(merged_at="2026-11-22T00:00:00Z"),
            lambda pr:pr.update(mergeable=False),
            lambda pr:pr["head"]["repo"].update(full_name="attacker/untrusted-fork"),
        ):
            with self.subTest(mutation=mutation):
                report=evaluate(MANIFEST,SyntheticReader(MANIFEST,change=(55,mutation)))
                self.assertFalse(report["ready"])

    def test_parent_sha_and_branch_must_be_exact(self):
        for mutation in (
            lambda pr:pr["base"].update(sha="a"*40),
            lambda pr:pr["base"].update(ref="main"),
        ):
            report=evaluate(MANIFEST,SyntheticReader(MANIFEST,change=(55,mutation)))
            self.assertFalse(report["ready"])
            self.assertIn("pr.55.parent",{x["check"] for x in report["checks"] if not x["passed"]})

    def test_ci_missing_failed_pending_and_stale_shas_block(self):
        name=MANIFEST["terminal_ci"]["workflows"][0]
        sha=MANIFEST["pull_requests"][-1]["head"]
        invalid_sets=(
            [],
            [{"name":name,"head_sha":sha,"status":"completed","conclusion":"failure"}],
            [{"name":name,"head_sha":sha,"status":"in_progress","conclusion":None}],
            [{"name":name,"head_sha":"a"*40,"status":"completed","conclusion":"success"}],
        )
        for entries in invalid_sets:
            with self.subTest(entries=entries):
                result=evaluate(MANIFEST,SyntheticReader(MANIFEST,runs=entries))
                self.assertFalse(result["ready"])

    def test_newer_failed_or_pending_run_cannot_be_masked_by_old_success(self):
        sha=MANIFEST["pull_requests"][-1]["head"]
        name=MANIFEST["terminal_ci"]["workflows"][0]
        old_green=[{"name":x,"head_sha":sha,"status":"completed","conclusion":"success"}
                   for x in MANIFEST["terminal_ci"]["workflows"]]
        for result,status in (("failure","completed"),(None,"in_progress")):
            newest={"name":name,"head_sha":sha,"status":status,"conclusion":result}
            evaluated=evaluate(MANIFEST,SyntheticReader(MANIFEST,runs=[newest]+old_green))
            self.assertFalse(evaluated["ready"])
            self.assertIn("ci."+name,[x["check"] for x in evaluated["checks"] if not x["passed"]])

    def test_truncated_github_workflow_response_is_not_ready(self):
        class TruncatedReader(SyntheticReader):
            def get(self,path):
                obj=super().get(path)
                if "/actions/runs" in path:
                    obj["total_count"]=len(obj["workflow_runs"])+1
                return obj
        result=evaluate(MANIFEST,TruncatedReader(MANIFEST))
        self.assertFalse(result["ready"])

    def test_manifest_rejects_duplicates_bad_sha_and_missing_ci(self):
        for mutation in (
            lambda m:m["pull_requests"].append(copy.deepcopy(m["pull_requests"][-1])),
            lambda m:m["pull_requests"][-1].update(head="not-a-sha"),
            lambda m:m["terminal_ci"].update(workflows=[]),
            lambda m:m["terminal_ci"].update(pr=19),
            lambda m:m.update(repository="attacker/x/../../repo"),
        ):
            manifest=copy.deepcopy(MANIFEST)
            mutation(manifest)
            with self.subTest(manifest=manifest),self.assertRaises(GateError):
                _safe_spec(manifest)

    def test_unavailable_github_evidence_blocks(self):
        class ErrorReader:
            def get(self,_):raise GateError("unavailable")
        result=evaluate(MANIFEST,ErrorReader())
        self.assertFalse(result["ready"])
        self.assertTrue(all(not item["passed"] for item in result["checks"]))


if __name__=="__main__":
    unittest.main()
