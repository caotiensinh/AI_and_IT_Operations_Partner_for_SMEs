#!/usr/bin/env python3
"""Fail-closed, evidence-linked production release-readiness gate."""
import argparse
import json
import sys
from pathlib import Path

REQUIRED = (
    "external_oidc_provider_e2e",
    "trusted_https_ingress",
    "distributed_rate_limiting",
    "independent_security_review",
    "production_role_and_secret_provisioning",
    "backup_restore_and_incident_drill",
    "multi_instance_observability",
    "tenant_owner_acceptance",
)

def validate(document):
    if not isinstance(document, dict) or set(document) != {"schema_version", "environment", "status", "checks", "evidence"}:
        raise ValueError("Unexpected readiness manifest fields")
    if type(document["schema_version"]) is not int or document["schema_version"] != 1:
        raise ValueError("Unsupported schema_version")
    if document["environment"] != "production":
        raise ValueError("Manifest must target production")
    checks = document["checks"]
    evidence = document["evidence"]
    if not isinstance(checks, dict) or set(checks) != set(REQUIRED):
        raise ValueError("Missing or unexpected production release checks")
    if not isinstance(evidence, dict) or set(evidence) - set(REQUIRED):
        raise ValueError("Invalid evidence keys")
    if any(type(value) is not bool for value in checks.values()):
        raise ValueError("Each check must be a boolean")
    if any(not isinstance(value, str) or not value.startswith("https://") or not value.strip() for value in evidence.values()):
        raise ValueError("Evidence must contain HTTPS links")
    for key, passed in checks.items():
        if passed and key not in evidence:
            raise ValueError(f"PASS requires evidence: {key}")
    ready = all(checks.values())
    expected_status = "ready" if ready else "blocked"
    if document["status"] != expected_status:
        raise ValueError(f"Status inconsistent with checks: expected {expected_status}")
    return ready

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path(__file__).resolve().parents[1] / "release/readiness.json")
    parser.add_argument("--check-production", action="store_true", help="Exit nonzero while any production check is blocked")
    args = parser.parse_args(argv)
    try:
        document = json.loads(args.manifest.read_text(encoding="utf-8"))
        ready = validate(document)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"INVALID release manifest: {exc}", file=sys.stderr)
        return 2
    blocked = [key for key, passed in document["checks"].items() if not passed]
    print(f"Release manifest valid; production ready: {ready}; blocked: {', '.join(blocked) or 'none'}")
    return 1 if args.check_production and not ready else 0

if __name__ == "__main__":
    sys.exit(main())
