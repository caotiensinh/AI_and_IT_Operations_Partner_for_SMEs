"""Staging-only migration namespace reconciliation after verified three-way merge.

The live main branch uses 0005–0019 for security/Asahi migrations, while
the Discovery feature stack independently allocated 0005–0012. Reconcile
Discovery suffixes to 0020–0026 WITHOUT touching existing main migrations.
Never run on a production database. The CI runner runs this on source files
before ANY validation or staging-only push.
"""
from __future__ import annotations

import ast
import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "a75015371c32e77a751c38a06a32d1166a1e08cf"
MAIN = "778933534d167315144fc692d350ba1803b17e94"
RENAME = {
    "0006_discovery_case_write.sql": "0020_discovery_case_write.sql",
    "0007_discovery_idempotency.sql": "0021_discovery_idempotency.sql",
    "0008_discovery_source_intake.sql": "0022_discovery_source_intake.sql",
    "0009_discovery_requirement_intake.sql": "0023_discovery_requirement_intake.sql",
    "0010_discovery_requirement_review.sql": "0024_discovery_requirement_review.sql",
    "0011_discovery_review_history_read.sql": "0025_discovery_review_history_read.sql",
    "0012_cookie_bff_tenants.sql": "0026_cookie_bff_tenants.sql",
}
REFERENCE_MAP = {
    "0005_discovery_read_model.sql": "0008_discovery_read_model.sql",
    **RENAME,
}
ORDER = (1, 2, 3, 4, 5, 6, 7, 8, 9, 20, 21, 22, 23, 24, 25, 26)


def _git_file(revision: str, path: str) -> str:
    return subprocess.check_output(
        ["git", "show", f"{revision}:{path}"], cwd=ROOT, text=True
    )


def _assert_equivalent_discovery_read_model() -> None:
    baseline = _git_file(MAIN, "migrations/0008_discovery_read_model.sql")
    staged = (ROOT / "migrations/0008_discovery_read_model.sql").read_text()
    original_feature = _git_file(SOURCE, "migrations/0005_discovery_read_model.sql")
    if staged != baseline or staged.splitlines()[1:] != original_feature.splitlines()[1:]:
        raise RuntimeError("Discovery read-model DDL differs; manual review required")
    if (ROOT / "migrations/0005_discovery_read_model.sql").exists():
        raise RuntimeError("Unexpected duplicate read-model migration")


def _replace_references(path: Path) -> None:
    old = path.read_text()
    new = old
    for before, after in REFERENCE_MAP.items():
        new = new.replace(before, after)
    if new != old:
        path.write_text(new)


def main() -> None:
    if (os.getenv("SME_STAGING_RECONCILE") != "1"
            or os.getenv("GITHUB_REF") != "refs/heads/integration/discovery-staging-20261122"):
        raise SystemExit("Reconciliation permitted only on pinned staging candidate")
    _assert_equivalent_discovery_read_model()
    root = ROOT / "migrations"
    for before, after in RENAME.items():
        source = root / before
        target = root / after
        if not source.is_file() or target.exists():
            raise RuntimeError(f"Unexpected staging migration state: {before}")
        source.rename(target)
    # Main's 0006 tenant selector has RETURNS TABLE(..., display_name),
    # whereas Discovery BFF's new selector uses tenant_label and LIMIT 101.
    # PostgreSQL disallows CREATE OR REPLACE with a changed OUT signature.
    # Preserve the main API and give the browser selector a distinct name.
    for relative in (
        "migrations/0026_cookie_bff_tenants.sql",
        "src/sme_partner/discovery_bff.py",
        "src/sme_partner/oidc_preflight.py",
        "tests/test_oidc_preflight.py",
    ):
        file = ROOT / relative
        original = file.read_text()
        if "list_session_tenants" not in original:
            raise RuntimeError(f"Missing expected browser tenant selector reference: {relative}")
        file.write_text(original.replace(
            "list_session_tenants", "list_browser_session_tenants"
        ))
    for path in (ROOT / "tests").glob("*.py"):
        _replace_references(path)
    # The original Discovery test uses an obsolete contiguous migration list.
    # Apply main's canonical 0001–0009 first, then Discovery 0020–0026.
    case_path = ROOT / "tests/test_discovery_postgres.py"
    content = case_path.read_text()
    pattern = (r'        for name in \(.*?\):\n'
               r'            cls\.db\.execute\(\(ROOT / "migrations" / name\)\.read_text\(\)\)')
    replacement = (
        '        for number in ' + repr(ORDER) + ':\n'
        '            matches = list((ROOT / "migrations").glob(f"{number:04d}_*.sql"))\n'
        '            if len(matches) != 1:\n'
        '                raise RuntimeError(f"Non-unique migration {number:04d}")\n'
        '            cls.db.execute(matches[0].read_text())'
    )
    content, changes = re.subn(pattern, lambda _: replacement, content, count=1, flags=re.S)
    if changes != 1:
        raise RuntimeError("Discovery integration test migration setup changed unexpectedly")
    case_path.write_text(content)

    path = ROOT / "scripts/discovery_e2e_seed.py"
    content = path.read_text()
    pattern = r'        for number in \(\(1,2,3,4,5,6,7,8,9,10,11,12\).*?\):\n'
    content, changed = re.subn(
        pattern, "        for number in " + repr(ORDER) + ":\n",
        content, count=1, flags=re.S
    )
    if changed != 1:
        raise RuntimeError("Synthetic E2E migration setup changed unexpectedly")
    path.write_text(content)

    path = ROOT / "tests/test_oidc_preflight_postgres.py"
    content = path.read_text()
    if "for n in (1,2,3,4,12):" not in content:
        raise RuntimeError("OIDC role preflight migration setup changed unexpectedly")
    path.write_text(content.replace(
        "for n in (1,2,3,4,12):",
        "for n in " + repr(ORDER) + ":",
        1
    ))

    # Do not silently reallocate main migrations or introduce duplicate numbers.
    by_number: dict[int, str] = {}
    for migration in root.glob("*.sql"):
        number = int(migration.name.split("_", 1)[0])
        if number in by_number:
            raise RuntimeError(f"Duplicate staging migration number {number:04d}")
        by_number[number] = migration.name
    expected = list(range(1, 27))
    if sorted(by_number) != expected:
        raise RuntimeError("Staging migration sequence incomplete")
    print("MIGRATION_RECONCILED=1")
    print("CANONICAL_DISCOVERY_MIGRATIONS=0020-0026")
    print("CANONICAL_TOTAL_MIGRATIONS=26")


if __name__ == "__main__":
    main()
