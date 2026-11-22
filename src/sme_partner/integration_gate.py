"""Read-only GitHub PR-chain + exact-SHA CI integration gate.

Usage: python -m sme_partner.integration_gate --manifest specs/003-sme-business-needs/integration-chain.json

This command never merges, modifies branches, triggers runs, accesses secrets,
or treats a successful workflow on a stale commit as evidence for the new head.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

_SHA = re.compile(r"^[a-f0-9]{40}$")
_REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_REF = re.compile(r"^[A-Za-z0-9_.\-/]+$")
_ALLOWED_CI = {"success"}
_ROOT = "https://api.github.com"


class GateError(Exception):
    pass


class GitHubReader:
    def __init__(self, *, token: str | None = None, timeout: float = 8.0):
        self.token = token
        self.timeout = timeout

    def get(self, path: str) -> dict:
        if not path.startswith("/repos/") or ".." in path:
            raise GateError("Invalid GitHub API path")
        headers = {"Accept": "application/vnd.github+json",
                   "User-Agent": "sme-partner-integration-gate",
                   "X-GitHub-Api-Version": "2022-11-28"}
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        try:
            with urlopen(Request(_ROOT + path, headers=headers),
                         timeout=self.timeout) as response:
                payload = response.read(512_001)
                if len(payload) > 512_000:
                    raise GateError("GitHub API response exceeds size limit")
                data = json.loads(payload)
                if not isinstance(data, dict):
                    raise GateError("GitHub API response not an object")
                return data
        except (HTTPError, URLError, TimeoutError, ValueError, OSError):
            raise GateError("GitHub API unavailable; verification incomplete") from None


def _safe_spec(data: dict) -> tuple[str, list[dict], dict]:
    repo = data.get("repository")
    nodes = data.get("pull_requests")
    terminal = data.get("terminal_ci")
    if not isinstance(repo, str) or not _REPO.fullmatch(repo):
        raise GateError("Manifest repository invalid")
    if not isinstance(nodes, list) or not nodes or len(nodes) > 60:
        raise GateError("Manifest PR chain must contain 1–60 entries")
    seen: set[int] = set()
    for node in nodes:
        if not isinstance(node, dict):
            raise GateError("Manifest PR entry invalid")
        n, head, base = node.get("number"), node.get("head"), node.get("base")
        if (type(n) is not int or n < 1 or n in seen
                or not isinstance(head, str) or not _SHA.fullmatch(head)
                or not isinstance(base, str) or not _REF.fullmatch(base)):
            raise GateError("Manifest PR entry missing or invalid")
        seen.add(n)
    if (not isinstance(terminal, dict)
            or terminal.get("pr") != nodes[-1]["number"]
            or not isinstance(terminal.get("workflows"), list)
            or not terminal["workflows"] or len(terminal["workflows"]) > 15
            or len(set(terminal["workflows"])) != len(terminal["workflows"])
            or not all(isinstance(x, str) and 1 <= len(x) <= 120
                       for x in terminal["workflows"])):
        raise GateError("Terminal PR and required CI workflow policy invalid")
    return repo, nodes, terminal


def evaluate(manifest: dict, reader: GitHubReader) -> dict:
    """Validate all upstream PR topology and final source SHA CI without mutation."""
    repo, nodes, terminal = _safe_spec(manifest)
    checks: list[dict] = []
    def emit(name: str, ok: bool, reason: str) -> None:
        checks.append({"check": name, "passed": bool(ok), "detail": reason})
    prior = None
    for node in nodes:
        n = node["number"]
        try:
            result = reader.get(f"/repos/{repo}/pulls/{n}")
            head = result["head"]
            base = result["base"]
            current = head["sha"]
            target = base["ref"]
            target_sha = base["sha"]
            state = result["state"]
            merged = result.get("merged_at")
            mergeable = result.get("mergeable")
            head_repo = head.get("repo") or {}
            repo_match = head_repo.get("full_name") == repo
            correct = (current == node["head"] and target == node["base"]
                       and state == "open" and not merged and repo_match
                       and mergeable is True)
            emit(f"pr.{n}.state", correct,
                 "Pinned source, same repository, open and mergeable"
                 if correct else "PR changed, unavailable, conflicted or not open")
            if prior is not None:
                aligned = target == prior["ref"] and target_sha == prior["sha"]
                emit(f"pr.{n}.parent", aligned,
                     "Parent branch and exact head SHA match"
                     if aligned else "Parent branch/SHA mismatch or stale stacked PR")
            prior = {"ref": head["ref"], "sha": current}
        except (GateError, KeyError, TypeError, ValueError):
            emit(f"pr.{n}.state", False, "PR could not be verified")
            if prior is not None:
                emit(f"pr.{n}.parent", False, "PR parent could not be verified")
            prior = None

    final_sha = nodes[-1]["head"]
    required = set(terminal["workflows"])
    found = {name: False for name in required}
    try:
        # Query workflows for this exact commit, not the branch's older CI.
        # Missing required CI, queued/pending runs and failed runs block approval.
        data = reader.get(f"/repos/{repo}/actions/runs?head_sha={final_sha}&per_page=100")
        runs = data.get("workflow_runs")
        if not isinstance(runs, list):
            raise GateError("Missing workflow runs")
        for run in runs:
            if not isinstance(run, dict):
                continue
            name = run.get("name")
            if name in required and run.get("head_sha") == final_sha:
                found[name] = (run.get("status") == "completed"
                               and run.get("conclusion") in _ALLOWED_CI)
        for name in sorted(required):
            emit("ci." + name, found[name],
                 "Successful CI on exact terminal PR commit"
                 if found[name] else "Required CI missing, incomplete or unsuccessful on exact SHA")
    except (GateError, ValueError):
        for name in sorted(required):
            emit("ci." + name, False, "GitHub CI evidence unavailable")

    return {"ready": bool(checks) and all(item["passed"] for item in checks),
            "repository": repo, "terminal_sha": final_sha, "checks": checks}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only stacked PR integration readiness")
    parser.add_argument("--manifest", type=Path,
                        default=Path("specs/003-sme-business-needs/integration-chain.json"))
    args = parser.parse_args(argv)
    try:
        data = json.loads(args.manifest.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise GateError("Manifest must be JSON object")
        report = evaluate(data, GitHubReader(token=os.environ.get("GITHUB_TOKEN")))
    except (GateError, OSError, ValueError, json.JSONDecodeError):
        report = {"ready": False, "checks": [
            {"check": "gate.input", "passed": False,
             "detail": "Manifest or GitHub evidence unavailable"}]}
    print(json.dumps(report, sort_keys=True))
    return 0 if report["ready"] else 1


if __name__ == "__main__":
    sys.exit(main())
