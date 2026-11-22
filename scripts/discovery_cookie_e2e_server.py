"""Synthetic-only HTTPS browser E2E: internal loopback cookie BFF.

Not a production server or public IdP. Runs only with disposable localhost sme_test.
"""
import os
import json
import urllib.parse
import urllib.request
from pathlib import Path
from urllib.parse import urlparse
import psycopg
import uvicorn
from sme_partner.discovery_bff import create_cookie_discovery_app
from sme_partner.oidc_flow import OIDCLoginFlow,OIDCLoginSettings,PostgresLoginStore
from sme_partner.oidc import OIDCConfig

def main():
    dsn=os.environ["SME_TEST_DATABASE_DSN"]
    parsed=urlparse(dsn)
    if (os.getenv("SME_E2E_ONLY")!="1" or parsed.hostname not in
            ("localhost","127.0.0.1") or parsed.path!="/sme_test"):
        raise SystemExit("Refusing to start cookie E2E against a non-disposable database")
    key=bytes.fromhex(os.environ["SME_E2E_CSRF_KEY_HEX"])
    oidc_flow=None
    if os.getenv("SME_E2E_OIDC_MODE")=="1":
        issuer="https://127.0.0.1:5174/oidc-test"
        client_id="synthetic-discovery-client"
        redirect_uri="https://127.0.0.1:5174/auth/oidc/callback"
        jwks=json.loads(Path(os.environ["SME_E2E_IDP_JWKS"]).read_text())
        def auth_connect():
            conn=psycopg.connect(dsn)
            conn.execute("SET ROLE sme_auth")
            return conn
        def exchange_code(code,verifier,expected_redirect,expected_client):
            if expected_redirect!=redirect_uri or expected_client!=client_id:
                raise ValueError("test provider configuration mismatch")
            data=urllib.parse.urlencode({
                "grant_type":"authorization_code","code":code,
                "redirect_uri":redirect_uri,"client_id":client_id,
                "code_verifier":verifier,
            }).encode()
            request=urllib.request.Request("http://127.0.0.1:8002/oidc-test/token",
                data=data,headers={"Content-Type":"application/x-www-form-urlencoded"},
                method="POST")
            with urllib.request.urlopen(request,timeout=5) as response:
                return json.loads(response.read(20000))["id_token"]
        oidc_flow=OIDCLoginFlow(OIDCLoginSettings(
            authorization_endpoint=issuer+"/authorize",
            redirect_uri=redirect_uri,
            oidc=OIDCConfig(issuer=issuer,client_id=client_id,jwks=jwks)),
            PostgresLoginStore(auth_connect),exchange_code)
    app=create_cookie_discovery_app(lambda:psycopg.connect(dsn),
        csrf_secret=key,trusted_origin="https://127.0.0.1:5174",oidc_flow=oidc_flow)
    uvicorn.run(app,host="127.0.0.1",port=8001,log_level="warning")

if __name__=="__main__":
    main()
