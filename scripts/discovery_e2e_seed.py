"""Provision synthetic-only PostgreSQL identity/session for disposable browser E2E.

Never execute against customer databases. Requires SME_E2E_ONLY=1 and a
localhost PostgreSQL DSN. The JSON fixture contains a bearer session: private
to the CI job, never committed, uploaded, or printed.
"""
import base64
import hashlib
import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4
from urllib.parse import urlparse

import psycopg

ROOT = Path(__file__).resolve().parents[1]
DSN = os.environ["SME_TEST_DATABASE_DSN"]
FIXTURE = Path(os.environ["SME_E2E_FIXTURE_PATH"])


def main():
    parsed = urlparse(DSN)
    if (os.getenv("SME_E2E_ONLY") != "1"
            or parsed.hostname not in {"localhost", "127.0.0.1"}
            or parsed.path != "/sme_test"):
        raise SystemExit("Refusing E2E seed outside dedicated localhost sme_test")
    if FIXTURE.exists():
        raise SystemExit("Fixture already exists; refusing overwrite")
    tenant, site, identity = uuid4(), uuid4(), uuid4()
    token = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip("=")
    token_negative = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip("=") if os.getenv("SME_E2E_COOKIE_MODE")=="1" else None
    with psycopg.connect(DSN) as conn:
        # Migrations run with the migration/provisioning owner, never runtime app.
        for number in ((1,2,3,4,5,6,7,8,9,10,11,12) if os.getenv("SME_E2E_OIDC_MODE")=="1" else
                       (1,2,3,5,6,7,8,9,10,11,12) if os.getenv("SME_E2E_COOKIE_MODE")=="1" else
                       (1,2,3,5,6,7,8,9,10,11)):
            matches = list((ROOT / "migrations").glob(f"{number:04d}_*.sql"))
            if len(matches) != 1:
                raise RuntimeError(f"Expected exactly one migration {number:04d}")
            conn.execute(matches[0].read_text(encoding="utf-8"))
        conn.execute(
            "INSERT INTO sme.tenants(id,slug,display_name) VALUES (%s,%s,%s)",
            (tenant,"synthetic-"+tenant.hex[:12],"Synthetic test tenant"))
        conn.execute(
            "INSERT INTO sme.sites(tenant_id,id,label) VALUES (%s,%s,%s)",
            (tenant,site,"Synthetic office"))
        conn.execute(
            "INSERT INTO sme.identities(id,issuer,subject) VALUES (%s,%s,%s)",
            (identity,"https://127.0.0.1:5174/oidc-test" if os.getenv("SME_E2E_OIDC_MODE")=="1" else "https://synthetic.test",identity.hex))
        conn.execute(
            "INSERT INTO sme.memberships(tenant_id,identity_id) VALUES (%s,%s)",
            (tenant,identity))
        conn.execute(
            "INSERT INTO sme.role_assignments"
            "(tenant_id,id,identity_id,role,scope_type) "
            "VALUES (%s,%s,%s,'manager','tenant')",
            (tenant,uuid4(),identity))
        conn.execute(
            "INSERT INTO sme.sessions(id,identity_id,token_digest,expires_at) "
            "VALUES (%s,%s,%s,%s)",
            (uuid4(),identity,hashlib.sha256(token.encode()).digest(),
             datetime.now(timezone.utc)+timedelta(minutes=40)))
        if token_negative:
            conn.execute("INSERT INTO sme.sessions(id,identity_id,token_digest,expires_at) "
                "VALUES (%s,%s,%s,%s)",(uuid4(),identity,
                hashlib.sha256(token_negative.encode()).digest(),
                datetime.now(timezone.utc)+timedelta(minutes=40)))
    FIXTURE.parent.mkdir(parents=True,exist_ok=True)
    fd = os.open(str(FIXTURE), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd,"w",encoding="utf-8") as writer:
        json.dump({"tenant":str(tenant),"site":str(site),"token":token,
                   **({"subject":identity.hex} if os.getenv("SME_E2E_OIDC_MODE")=="1" else {}),
                   **({"token_negative":token_negative} if token_negative else {})},writer)
    print("Synthetic E2E fixture initialized (no secrets logged)")


if __name__ == "__main__":
    main()
