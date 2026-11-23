#!/usr/bin/env python3
"""Validate PR contribution governance; not a replacement for GitHub branch rulesets."""
import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECORD_ID = re.compile(r"^[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+$")
ALLOWED_TYPES = {"implementation", "fix", "docs", "governance", "integration"}
FENCE = re.compile(r"^\s*(Acceptance-IDs|Change-Type):\s*(.*?)\s*$", re.MULTILINE)

def _validator():
    path = ROOT / "scripts/check_acceptance.py"
    spec = importlib.util.spec_from_file_location("governance_acceptance", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.validate

def validate_pr(body: str, records_root: Path, changed_files: list[str], validator=None):
    if not isinstance(body, str) or not body.strip():
        raise ValueError("PR body missing: Acceptance-IDs and Change-Type are mandatory")
    pairs = FENCE.findall(body)
    tags = {}
    for key, value in pairs:
        if key in tags:
            raise ValueError(f"Duplicate {key}")
        tags[key] = value
    if set(tags) != {"Acceptance-IDs", "Change-Type"}:
        raise ValueError("Exactly one Acceptance-IDs and Change-Type line required")
    if tags["Change-Type"] not in ALLOWED_TYPES:
        raise ValueError("Unknown Change-Type")
    identifiers = [x.strip() for x in tags["Acceptance-IDs"].split(",")]
    if not identifiers or len(identifiers) > 20 or len(identifiers) != len(set(identifiers)):
        raise ValueError("Acceptance-IDs missing or duplicated")
    if any(not RECORD_ID.fullmatch(x) for x in identifiers):
        raise ValueError("Invalid acceptance ID")
    if not changed_files:
        raise ValueError("PR has no changed files")
    # Verification is structural; a local PR record cannot grant human approval.
    validate = validator or _validator()
    for identifier in identifiers:
        path = records_root / f"{identifier}.json"
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"Missing acceptance record: {identifier}")
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("id") != identifier:
            raise ValueError(f"Acceptance record ID mismatch: {identifier}")
        validate(data)
    # All contributors, including docs-only, must provide a traceable acceptance record.
    # An old record with no modified acceptance files may be referenced but never asserts
    # the current PR passed L4; independent GitHub approval is still mandatory.
    return {"type": tags["Change-Type"], "ids": identifiers, "files": len(changed_files)}

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event", type=Path, default=None)
    parser.add_argument("--record-root", type=Path, default=ROOT / "acceptance/records")
    parser.add_argument("--changed-files", type=Path, default=None)
    args = parser.parse_args(argv)
    import os
    event_path = args.event or Path(os.environ.get("GITHUB_EVENT_PATH", "/missing/event.json"))
    try:
        event = json.loads(event_path.read_text(encoding="utf-8"))
        pr = event.get("pull_request")
        if not isinstance(pr, dict):
            raise ValueError("Expected pull_request event")
        if args.changed_files:
            changed = [x for x in args.changed_files.read_text(encoding="utf-8").splitlines() if x]
        else:
            import subprocess
            base = pr.get("base", {}).get("sha")
            if not isinstance(base, str) or not re.fullmatch(r"[0-9a-f]{40}", base):
                raise ValueError("Missing exact PR base SHA")
            proc = subprocess.run(["git", "diff", "--name-only", "--diff-filter=ACMR", base, "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True)
            changed = [x for x in proc.stdout.splitlines() if x]
        result = validate_pr(pr.get("body", ""), args.record_root, changed)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError, __import__("subprocess").CalledProcessError) as exc:
        print(f"PR_GOVERNANCE=FAILED: {exc}", file=sys.stderr)
        return 2
    print(f"PR_GOVERNANCE=PASS: {result['type']}, acceptance IDs={','.join(result['ids'])}, changed files={result['files']}.")
    print("Not user acceptance. Requires independently configured GitHub ruleset and review.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
