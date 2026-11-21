"""CI-only seeded PostgreSQL fixtures; never point at a customer database."""
import base64
import hashlib
import json
import os
from pathlib import Path
import secrets
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import psycopg

ROOT=Path(__file__).resolve().parents[1]


def token():
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii").rstrip("=")


def main():
    if os.getenv("SME_E2E_FIXTURE_MODE")!="disposable_ci_only":
        raise SystemExit("Refusing to seed outside disposable CI mode")
    dsn=os.environ["SME_TEST_DATABASE_DSN"]
    if not ("127.0.0.1" in dsn or "localhost" in dsn):
        raise SystemExit("Refusing to seed remote database")
    with psycopg.connect(dsn,autocommit=True) as db:
        for script in sorted((ROOT/"migrations").glob("*.sql")):
            db.execute(script.read_text())
        a,b,u,other,site_a,site_b,asset_a1,asset_a2,asset_b=[uuid4() for _ in range(9)]
        db.execute("INSERT INTO sme.tenants(id,slug,display_name) VALUES (%s,%s,'Aichi Manufacturing'),(%s,%s,'Owari Logistics')",
                   (a,'e2e-'+a.hex[:12],b,'e2e-'+b.hex[:12]))
        db.execute("INSERT INTO sme.identities(id,issuer,subject) VALUES (%s,'https://ci.example',%s),(%s,'https://ci.example',%s)",
                   (u,u.hex,other,other.hex))
        db.execute("INSERT INTO sme.memberships(tenant_id,identity_id,status) VALUES (%s,%s,'active'),(%s,%s,'active'),(%s,%s,'active')",
                   (a,u,b,u,a,other))
        db.execute("INSERT INTO sme.sites(tenant_id,id,label) VALUES (%s,%s,'Nagoya'),(%s,%s,'Ichinomiya')",
                   (a,site_a,b,site_b))
        db.execute("INSERT INTO sme.assets(tenant_id,id,site_id,name) VALUES (%s,%s,%s,'Aichi NAS'),(%s,%s,%s,'Aichi Router'),(%s,%s,%s,'Owari Camera')",
                   (a,asset_a1,site_a,a,asset_a2,site_a,b,asset_b,site_b))
        for identity,tenant in ((u,a),(u,b),(other,a)):
            db.execute("INSERT INTO sme.role_assignments(tenant_id,id,identity_id,role,scope_type) VALUES (%s,%s,%s,'viewer','tenant')",
                       (tenant,uuid4(),identity))
        both,only_a=token(),token()
        now=datetime.now(timezone.utc)
        for identity,value in ((u,both),(other,only_a)):
            db.execute("INSERT INTO sme.sessions(id,identity_id,token_digest,expires_at) VALUES (%s,%s,%s,%s)",
                       (uuid4(),identity,hashlib.sha256(value.encode()).digest(),now+timedelta(hours=1)))
    out=Path(os.environ["SME_E2E_FIXTURE_PATH"])
    out.write_text(json.dumps({"tenant_a":str(a),"tenant_b":str(b),"both_token":both,"only_a_token":only_a}))
    out.chmod(0o600)
    print("Disposable two-tenant fixture created (secrets not logged).")


if __name__=="__main__":
    main()
