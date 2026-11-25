#!/usr/bin/env python3
"""Read-only branch consolidation inventory via authenticated GitHub REST.

Never merges, deletes, force-pushes, or treats a green CI as human acceptance.
Requires GITHUB_TOKEN and GITHUB_REPOSITORY when executed in Actions.
"""
import argparse
import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

API = "https://api.github.com"

def request(path: str, token: str):
    if not token or any(c.isspace() for c in token):
        raise ValueError("GitHub token missing")
    req = Request(API + path, headers={
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "sme-consolidation-readonly-inventory",
    })
    with urlopen(req, timeout=20) as response:
        return json.load(response)

def classify(ahead: int, behind: int):
    if ahead == 0:
        return "ALREADY_INCLUDED"
    if behind == 0:
        return "UNMERGED_LINEAR_REVIEW"
    return "DIVERGED_REVIEW"

def inventory(repo: str, token: str):
    if repo.count("/") != 1:
        raise ValueError("Expected owner/repository")
    owner, name = repo.split("/")
    if not owner or not name or any(not (c.isalnum() or c in "-_.") for c in owner+name):
        raise ValueError("Unsafe repository name")
    base = "/repos/" + quote(owner, safe="") + "/" + quote(name, safe="")
    main = request(base + "/branches/main", token)["commit"]["sha"]
    branches = []
    for page in range(1, 101):
        data = request(base + f"/branches?per_page=100&page={page}", token)
        if not isinstance(data, list):
            raise ValueError("Unexpected branch response")
        branches.extend(row["name"] for row in data)
        if len(data) < 100:
            break
    else:
        raise ValueError("Too many branches; pagination limit hit")
    results = []
    failures = []
    for branch in sorted(set(branches)):
        if branch == "main":
            continue
        try:
            # Encode branch so '/' stays inside a ref and cannot alter query.
            comparison = request(base + "/compare/" + main + "..." + quote(branch, safe=""), token)
            ahead, behind = comparison["ahead_by"], comparison["behind_by"]
            if type(ahead) is not int or type(behind) is not int:
                raise ValueError("Invalid compare counters")
            results.append({"branch": branch, "ahead": ahead, "behind": behind,
                            "classification": classify(ahead, behind),
                            "safe_to_merge": False})
        except (KeyError, ValueError, HTTPError, URLError, TimeoutError) as err:
            failures.append({"branch": branch, "error_type": type(err).__name__})
            results.append({"branch": branch, "classification": "UNKNOWN_BLOCKED",
                            "safe_to_merge": False})
    return {"base_sha": main, "branch_count": len(branches), "results": results,
            "failures": failures, "merge_authorized": False}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=os.getenv("GITHUB_REPOSITORY", ""))
    parser.add_argument("--summary", default=os.getenv("GITHUB_STEP_SUMMARY", ""))
    parser.add_argument("--json-output", default="")
    args = parser.parse_args()
    try:
        result = inventory(args.repo, os.getenv("GITHUB_TOKEN", ""))
    except (OSError, ValueError, KeyError, HTTPError, URLError, TimeoutError) as err:
        print("BRANCH_INVENTORY=FAILED: " + type(err).__name__, file=sys.stderr)
        return 2
    grouped = {}
    for row in result["results"]:
        grouped[row["classification"]] = grouped.get(row["classification"], 0) + 1
    lines = ["# Branch consolidation: read-only audit", "",
             "Pinned `main`: `" + result["base_sha"] + "`",
             "Total branches including main: " + str(result["branch_count"]),
             "", "| Classification | Count |", "|---|---:|"]
    lines += ["| " + name + " | " + str(count) + " |" for name, count in sorted(grouped.items())]
    lines += ["", "No merges were authorized or executed. AHEAD/DIVERGED requires independent review and integration CI.",
              "", "| Branch | Ahead | Behind | Status |", "|---|---:|---:|---|"]
    for row in result["results"]:
        lines.append("| `" + row["branch"].replace("|", "") + "` | " +
                     str(row.get("ahead", "?")) + " | " + str(row.get("behind", "?")) +
                     " | " + row["classification"] + " |")
    report = "\n".join(lines) + "\n"
    if args.summary:
        with open(args.summary, "a", encoding="utf-8") as f:
            f.write(report)
    if args.json_output:
        with open(args.json_output, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, sort_keys=True)
    print(report)
    return 1 if result["failures"] else 0

if __name__ == "__main__":
    sys.exit(main())
