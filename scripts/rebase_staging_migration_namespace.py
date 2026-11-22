"""Staging-only domain migration namespace reconciliation for concurrent main.

Shared/Asahi migrations retain 0001–0099; Discovery owns 0100–0199.
Runs only in an isolated GitHub Actions checkout before a pinned main merge
and before all backend/frontend acceptance tests. Never touches a database.
"""
from __future__ import annotations

import os
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
REMAP = {
    "0020_discovery_case_write.sql": "0100_discovery_case_write.sql",
    "0021_discovery_idempotency.sql": "0101_discovery_idempotency.sql",
    "0022_discovery_source_intake.sql": "0102_discovery_source_intake.sql",
    "0023_discovery_requirement_intake.sql": "0103_discovery_requirement_intake.sql",
    "0024_discovery_requirement_review.sql": "0104_discovery_requirement_review.sql",
    "0025_discovery_review_history_read.sql": "0105_discovery_review_history_read.sql",
    "0026_cookie_bff_tenants.sql": "0106_cookie_bff_tenants.sql",
}
ORDER = (1,2,3,4,5,6,7,8,9,100,101,102,103,104,105,106)


def main() -> None:
    if (os.getenv("SME_STAGING_NAMESPACE_V2")!="1" or
        os.getenv("GITHUB_REF")!="refs/heads/integration/discovery-staging-20261122"):
        raise SystemExit("Only disposable pinned staging CI can apply namespace reconciliation")
    directory = ROOT / "migrations"
    for old, new in REMAP.items():
        src, dst = directory / old, directory / new
        if not src.is_file() or dst.exists():
            raise RuntimeError(f"Unexpected staging migration namespace: {old}")
        src.rename(dst)

    # All exact references must point to the renamed files on this candidate.
    for file in list((ROOT / "tests").glob("*.py")) + [ROOT / "scripts/discovery_e2e_seed.py"]:
        original = file.read_text()
        current = original
        for old, new in REMAP.items():
            current = current.replace(old, new)
        if current != original:
            file.write_text(current)

    for relative in (
        "tests/test_discovery_postgres.py",
        "tests/test_oidc_preflight_postgres.py",
        "scripts/discovery_e2e_seed.py",
    ):
        path = ROOT / relative
        old = path.read_text()
        pattern = re.escape("(1, 2, 3, 4, 5, 6, 7, 8, 9, 20, 21, 22, 23, 24, 25, 26)")
        new, count = re.subn(pattern, repr(ORDER), old)
        if count != 1:
            raise RuntimeError(f"Migration ordering contract changed in {relative}")
        path.write_text(new)

    suite = ROOT / "tests/test_staging_schema_contract.py"
    original = suite.read_text()
    if "self.assertEqual(len(names), 26)" not in original:
        raise RuntimeError("Staging migration acceptance contract changed")
    revised = original.replace(
        "self.assertEqual(len(names), 26)",
        "self.assertEqual(len(names), 28)"
    ).replace(
        "self.assertEqual(numbers, list(range(1, 27)))",
        "self.assertEqual(numbers, list(range(1, 22)) + list(range(100, 107)))"
    )
    suite.write_text(revised)

    # No discovery migration is allowed to reuse any main-owned number.
    names = sorted(path.name for path in directory.glob("*.sql"))
    by_number: dict[int,str] = {}
    for name in names:
        number = int(name.split("_", 1)[0])
        if number in by_number:
            raise RuntimeError(f"Migration number collision: {number}")
        by_number[number] = name
    expected = list(range(1,20)) + list(range(100,107))
    if sorted(by_number) != expected:
        raise RuntimeError("Unexpected baseline migration number set before main refresh")
    print("STAGING_DOMAIN_NAMESPACE=0100-0106")
    print("NONDESTRUCTIVE_MIGRATION_RENAME=PASS")


if __name__=="__main__":
    main()
