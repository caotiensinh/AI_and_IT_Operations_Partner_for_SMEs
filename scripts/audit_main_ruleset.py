#!/usr/bin/env python3
"""Fail-closed read-only audit of GitHub's server-side main branch ruleset.

This cannot activate protections. The owner must configure rulesets in GitHub.
"""
import json
import os
import sys
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

REQUIRED_CHECK = "PR governance contract"

def rulecheck(rulesets):
    if not isinstance(rulesets, list):
        raise ValueError("Invalid GitHub ruleset response")
    problems = []
    if not rulesets:
        problems.append("No active main-branch ruleset found")
    for ruleset in rulesets:
        if ruleset.get("target") != "branch" or ruleset.get("enforcement") != "active":
            continue
        cond=ruleset.get("conditions") or {}
        refs=(cond.get("ref_name") or {}).get("include") or []
        if not any(x in refs for x in ("~DEFAULT_BRANCH", "refs/heads/main")):
            continue
        rules=ruleset.get("rules") or []
        by_type={x.get("type"):x.get("parameters") or {} for x in rules}
        pr=by_type.get("pull_request")
        if pr is None:
            problems.append("Active main ruleset has no PR requirement")
            continue
        if pr.get("required_approving_review_count", 0) < 1:
            problems.append("No mandatory independent PR approval")
        if not pr.get("dismiss_stale_reviews_on_push"):
            problems.append("Stale approvals are not dismissed")
        checks=(by_type.get("required_status_checks") or {}).get("required_status_checks") or []
        names=[x.get("context") for x in checks]
        if REQUIRED_CHECK not in names:
            problems.append("PR governance check is not required")
        if "non_fast_forward" not in by_type:
            problems.append("Force-push prevention missing")
        if "deletion" not in by_type:
            problems.append("Branch deletion prevention missing")
        return problems
    problems.append("No active ruleset explicitly targeting main")
    return problems

def fetch(url, token):
    if not token:
        raise ValueError("Token required")
    req=Request(url,headers={"Authorization":"Bearer "+token,
        "Accept":"application/vnd.github+json",
        "X-GitHub-Api-Version":"2022-11-28",
        "User-Agent":"sme-main-ruleset-readonly-check"})
    with urlopen(req,timeout=15) as resp:
        return json.load(resp)

def audit(repo,token):
    if not repo or repo.count("/")!=1:
        raise ValueError("Invalid repo")
    root="https://api.github.com/repos/"+repo
    summaries=fetch(root+"/rulesets?includes_parents=true&per_page=100",token)
    if not isinstance(summaries,list):
        raise ValueError("Invalid ruleset summaries")
    full=[]
    for s in summaries:
        if s.get("target") == "branch" and s.get("enforcement") == "active":
            ident=s.get("id")
            if type(ident) is not int:
                raise ValueError("Invalid ruleset id")
            full.append(fetch(root+"/rulesets/"+str(ident),token))
    return rulecheck(full)

def main():
    try:
        problems=audit(os.getenv("GITHUB_REPOSITORY",""),os.getenv("GITHUB_TOKEN",""))
    except (OSError,ValueError,TypeError,KeyError,HTTPError,URLError) as e:
        print("MAIN_RULESET=BLOCKED: cannot verify server-side protection: "+type(e).__name__,file=sys.stderr)
        return 2
    if problems:
        for problem in problems:print("MAIN_RULESET=BLOCKED: "+problem,file=sys.stderr)
        return 1
    print("MAIN_RULESET=PASS: active branch ruleset, independent PR review and mandatory PR governance check")
    print("NOTE: GitHub server must still independently reject direct pushes and unsigned reviewer bypass; this audit alone is not a live negative test.")
    return 0

if __name__=="__main__":
    sys.exit(main())
