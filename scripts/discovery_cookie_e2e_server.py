"""Synthetic-only HTTPS browser E2E: internal loopback cookie BFF.

Not a production server or public IdP. Runs only with disposable localhost sme_test.
"""
import os
from urllib.parse import urlparse
import psycopg
import uvicorn
from sme_partner.discovery_bff import create_cookie_discovery_app

def main():
    dsn=os.environ["SME_TEST_DATABASE_DSN"]
    parsed=urlparse(dsn)
    if (os.getenv("SME_E2E_ONLY")!="1" or parsed.hostname not in
            ("localhost","127.0.0.1") or parsed.path!="/sme_test"):
        raise SystemExit("Refusing to start cookie E2E against a non-disposable database")
    key=bytes.fromhex(os.environ["SME_E2E_CSRF_KEY_HEX"])
    app=create_cookie_discovery_app(lambda:psycopg.connect(dsn),
        csrf_secret=key,trusted_origin="https://127.0.0.1:5174")
    uvicorn.run(app,host="127.0.0.1",port=8001,log_level="warning")

if __name__=="__main__":
    main()
