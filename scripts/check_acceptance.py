#!/usr/bin/env python3
"""Validate acceptance attestations; schema PASS is not product acceptance."""
import argparse
import json
import re
import sys
from pathlib import Path

STATES = {"NOT_STARTED", "IN_PROGRESS", "BLOCKED", "READY_FOR_REVIEW", "REJECTED", "ACCEPTED"}
LEVELS = ("L0", "L1", "L2", "L3", "L4", "L5")
GATES = {"contract", "persist", "functional", "security", "integration", "operations", "evidence", "product"}
SHA = re.compile(r"^[a-f0-9]{40}$")
FIELDS = {"schema_version", "id", "title", "status", "level", "scope", "environment", "commit_sha", "owner", "criteria", "gates", "review", "blockers"}
CRITERIA_FIELDS = {"id", "given", "when", "then", "verified", "evidence"}
REVIEW_FIELDS = {"reviewer", "decision", "commit_sha", "environment", "evidence"}

def _url(s):
    return isinstance(s, str) and s.startswith("https://") and len(s) > 9 and not any(c.isspace() for c in s)

def validate(record):
    if not isinstance(record, dict) or set(record) != FIELDS or type(record["schema_version"]) is not int or record["schema_version"] != 1:
        raise ValueError("Missing/extra fields or unsupported schema")
    for field in ("id", "title", "scope", "environment"):
        if not isinstance(record[field], str) or not record[field].strip():
            raise ValueError(f"Missing {field}")
    if record["status"] not in STATES or record["level"] not in LEVELS:
        raise ValueError("Invalid state or evidence level")
    if not isinstance(record["owner"], str) or not isinstance(record["commit_sha"], str):
        raise ValueError("Invalid owner/commit")
    if record["commit_sha"] and not SHA.fullmatch(record["commit_sha"]):
        raise ValueError("Commit must be a 40-hex SHA")
    gates = record["gates"]
    if not isinstance(gates, dict) or set(gates) != GATES or any(type(x) is not bool for x in gates.values()):
        raise ValueError("Gates must contain all exact boolean fields")
    criteria = record["criteria"]
    if not isinstance(criteria, list) or not criteria:
        raise ValueError("At least one written acceptance criterion is required")
    seen = set()
    for c in criteria:
        if not isinstance(c, dict) or set(c) != CRITERIA_FIELDS:
            raise ValueError("Invalid criterion fields")
        if any(not isinstance(c[k], str) or not c[k].strip() for k in ("id", "given", "when", "then")) or c["id"] in seen:
            raise ValueError("Missing or duplicate criterion")
        seen.add(c["id"])
        if type(c["verified"]) is not bool or not isinstance(c["evidence"], list) or any(not _url(u) for u in c["evidence"]):
            raise ValueError("Invalid criterion result/evidence")
        if c["verified"] and not c["evidence"]:
            raise ValueError("Verified criterion requires an HTTPS evidence link")
    review = record["review"]
    if not isinstance(review, dict) or set(review) != REVIEW_FIELDS:
        raise ValueError("Invalid review")
    if any(not isinstance(review[k], str) for k in ("reviewer", "decision", "commit_sha", "environment")) or not isinstance(review["evidence"], list) or any(not _url(u) for u in review["evidence"]):
        raise ValueError("Invalid review fields")
    if not isinstance(record["blockers"], list) or any(not isinstance(b, str) or not b.strip() for b in record["blockers"]):
        raise ValueError("Invalid blockers")
    all_criteria = all(c["verified"] for c in criteria)
    all_gates = all(gates.values())
    if record["status"] in ("READY_FOR_REVIEW", "ACCEPTED"):
        if not all_gates or not all_criteria or not SHA.fullmatch(record["commit_sha"]) or not record["owner"] or record["blockers"]:
            raise ValueError("Review-ready requires all gates, criteria, pinned SHA, owner and no blockers")
        if LEVELS.index(record["level"]) < 3:
            raise ValueError("Review-ready requires at least integrated staging L3")
    if record["status"] == "ACCEPTED":
        if record["level"] not in ("L4", "L5"):
            raise ValueError("ACCEPTED requires L4 or L5")
        if review["decision"] != "APPROVED" or not review["reviewer"] or review["reviewer"] == record["owner"] or not review["evidence"]:
            raise ValueError("ACCEPTED requires independent evidence-backed human approval")
        if review["commit_sha"] != record["commit_sha"] or review["environment"] != record["environment"]:
            raise ValueError("Approval must bind exact SHA and environment")
    else:
        if record["level"] in ("L4", "L5"):
            raise ValueError("L4/L5 reserved for ACCEPTED")
        if review["decision"] == "APPROVED":
            raise ValueError("Approval decision cannot coexist with incomplete status")
    if record["status"] == "BLOCKED" and not record["blockers"]:
        raise ValueError("BLOCKED must name the blocker")
    if record["level"] in ("L1", "L2", "L3") and not record["commit_sha"]:
        raise ValueError("Implementation levels require pinned SHA")
    if record["level"] in ("L2", "L3") and not gates["functional"]:
        raise ValueError("Verified levels require functional evidence")
    if record["level"] == "L3" and not gates["integration"]:
        raise ValueError("L3 requires integration evidence")
    return record["status"] == "ACCEPTED"

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--directory", type=Path, default=Path(__file__).resolve().parents[1] / "acceptance/records")
    p.add_argument("--require-accepted", action="store_true")
    args = p.parse_args(argv)
    files = sorted(args.directory.glob("*.json"))
    if not files:
        print("No acceptance records; nothing is certified", file=sys.stderr)
        return 1 if args.require_accepted else 0
    accepted = 0
    failed = 0
    for path in files:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if path.stem != data.get("id"):
                raise ValueError("File name must match record ID")
            ok = validate(data)
            accepted += int(ok)
            print(f"{data['id']}: {data['status']} ({data['level']})")
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            failed += 1
            print(f"{path}: INVALID: {exc}", file=sys.stderr)
    print(f"ACCEPTED={accepted}; REMAINING={len(files)-accepted}; INVALID={failed}")
    if failed:
        return 2
    return 1 if args.require_accepted and accepted != len(files) else 0

if __name__ == "__main__":
    sys.exit(main())
