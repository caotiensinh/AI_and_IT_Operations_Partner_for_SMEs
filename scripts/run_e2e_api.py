"""Bind to localhost only; CI fixture credentials are NOT production credentials."""
import os
import psycopg
import uvicorn
from sme_partner.session_api import create_app

if __name__=="__main__":
    if os.getenv("SME_E2E_FIXTURE_MODE")!="disposable_ci_only":
        raise SystemExit("Refusing to run CI-only API outside disposable mode")
    dsn=os.environ["SME_TEST_DATABASE_DSN"]
    if not ("127.0.0.1" in dsn or "localhost" in dsn):
        raise SystemExit("Remote database forbidden for CI harness")
    uvicorn.run(create_app(lambda:psycopg.connect(dsn)),host="127.0.0.1",port=8091)
