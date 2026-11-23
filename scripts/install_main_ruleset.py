#!/usr/bin/env python3
"""Owner-only, fail-closed GitHub main ruleset installer.

Dry run is the DEFAULT. Requires Administration:write and explicit owner action.
Never edits or deletes existing rulesets, and never changes branch history.
"""
import argparse
import json
import os
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

REPO = "caotiensinh/AI_and_IT_Operations_Partner_for_SMEs"
RULESET_NAME = "SME mandatory human-agent acceptance v1"
CHECKS = ("PR governance contract", "Public repository tracked-file safety")
SHA = re.compile(r"^[a-f0-9]{40}$")

def desired():
    return {
        "name": RULESET_NAME,
        "target": "branch",
        "enforcement": "active",
        "bypass_actors": [],
        "conditions": {"ref_name": {"include": ["refs/heads/main"], "exclude": []}},
        "rules": [
            {"type": "deletion"},
            {"type": "non_fast_forward"},
            {"type": "pull_request", "parameters": {
                "dismiss_stale_reviews_on_push": True,
                "require_code_owner_review": False,
                "require_last_push_approval": True,
                "required_approving_review_count": 1,
                "required_review_thread_resolution": True,
            }},
            {"type": "required_status_checks", "parameters": {
                "strict_required_status_checks_policy": True,
                "required_status_checks": [{"context": name} for name in CHECKS],
            }},
        ],
    }

def api_request(method, path, token, data=None):
    if not token:
        raise ValueError("Missing authorization token (Administration:write required for APPLY)")
    if method not in {"GET", "POST"}:
        raise ValueError("Unsupported request method")
    req = Request(
        "https://api.github.com/repos/" + REPO + path,
        data=(json.dumps(data).encode("utf-8") if data is not None else None),
        method=method,
        headers={
            "Authorization": "Bearer " + token,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
            "User-Agent": "sme-main-ruleset-owner-install",
        },
    )
    with urlopen(req, timeout=20) as response:
        return json.load(response)

def inspect(token):
    repo = api_request("GET", "", token)
    if repo.get("default_branch") != "main" or repo.get("full_name") != REPO:
        raise ValueError("Unexpected repository identity or default branch")
    branch = api_request("GET", "/branches/main", token)
    sha = branch.get("commit", {}).get("sha", "")
    if not SHA.fullmatch(sha):
        raise ValueError("Missing current main SHA")
    rules = api_request("GET", "/rulesets?per_page=100", token)
    if not isinstance(rules, list):
        raise ValueError("Untrusted ruleset list")
    return sha, rules

def install(token, expected_main_sha, apply):
    if not SHA.fullmatch(expected_main_sha):
        raise ValueError("Specify exact expected 40-character main commit SHA")
    actual, existing = inspect(token)
    if actual != expected_main_sha:
        raise ValueError("Main changed: abort. Reinspect before applying.")
    if any(x.get("name") == RULESET_NAME for x in existing):
        raise ValueError("Named ruleset already exists; inspect and audit, no overwrite")
    # Do not introduce a second policy if another active main branch policy already exists:
    # overlapping protections must be manually reconciled by the owner.
    if any(x.get("target") == "branch" and x.get("enforcement") == "active" for x in existing):
        raise ValueError("Existing active branch ruleset detected; manual reconciliation required")
    policy = desired()
    if not apply:
        print(json.dumps({"mode":"DRY_RUN","expected_sha":expected_main_sha,"policy":policy},indent=2))
        return False
    result = api_request("POST","/rulesets",token,policy)
    if result.get("name") != RULESET_NAME or result.get("enforcement") != "active":
        raise ValueError("GitHub result uncertain: inspect live ruleset before retry; do not blindly POST")
    print("RULESET_CREATED id=" + str(result.get("id")) + " (server-side validation still REQUIRED)")
    return True

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-main-sha", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm-repository", default="")
    args = parser.parse_args(argv)
    if args.apply and args.confirm_repository != REPO:
        print("RULESET_ABORTED: explicit --confirm-repository required",file=sys.stderr)
        return 2
    try:
        install(os.getenv("GITHUB_TOKEN",""),args.expected_main_sha,args.apply)
    except (ValueError,TypeError,KeyError,HTTPError,URLError,OSError) as exc:
        print("RULESET_ABORTED: "+type(exc).__name__+": "+str(exc).splitlines()[0][:300],file=sys.stderr)
        return 2
    return 0

if __name__=="__main__":
    sys.exit(main())
