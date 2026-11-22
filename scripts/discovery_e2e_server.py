"""Disposable E2E FastAPI launcher, loopback only. Not a production entrypoint."""
import os
from urllib.parse import urlparse

import psycopg
import uvicorn

from sme_partner.discovery_api import create_discovery_app


def main():
    dsn=os.environ["SME_TEST_DATABASE_DSN"]
    parsed=urlparse(dsn)
    if (os.getenv("SME_E2E_ONLY")!="1"
            or parsed.hostname not in {"localhost","127.0.0.1"}
            or parsed.path!="/sme_test"):
        raise SystemExit("Refusing E2E server outside disposable local DB")
    app=create_discovery_app(lambda: psycopg.connect(dsn))
    uvicorn.run(app,host="127.0.0.1",port=8000,log_level="warning")


if __name__=="__main__":
    main()
