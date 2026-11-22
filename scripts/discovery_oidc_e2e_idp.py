"""Isolated localhost synthetic OIDC authorization/code/token server.

NOT an identity provider for any actual account. No credential input endpoint.
Enforces PKCE and one-use authorization codes; signs JWT with ephemeral RSA key.
"""
import base64
import hashlib
import os
import secrets
import time
from pathlib import Path
from urllib.parse import urlparse
import jwt
import uvicorn
from fastapi import FastAPI,Form,HTTPException,Query
from fastapi.responses import RedirectResponse
from cryptography.hazmat.primitives import serialization

ISSUER="https://127.0.0.1:5174/oidc-test"
CLIENT_ID="synthetic-discovery-client"
CALLBACK="https://127.0.0.1:5174/auth/oidc/callback"
codes:dict[str,tuple[str,str,int]]={}

def checked_local_environment():
    dsn=urlparse(os.environ["SME_TEST_DATABASE_DSN"])
    if (os.getenv("SME_E2E_ONLY")!="1" or os.getenv("SME_E2E_OIDC_MODE")!="1"
            or dsn.hostname not in ("localhost","127.0.0.1") or dsn.path!="/sme_test"):
        raise SystemExit("Synthetic provider MUST run only with local sme_test")

def build_app():
    checked_local_environment()
    key=serialization.load_pem_private_key(Path(os.environ["SME_E2E_IDP_KEY"]).read_bytes(),password=None)
    app=FastAPI(openapi_url=None,docs_url=None,redoc_url=None)

    @app.get("/oidc-test/authorize")
    def authorize(response_type:str=Query(...),client_id:str=Query(...),
                  redirect_uri:str=Query(...),scope:str=Query(...),
                  state:str=Query(...),nonce:str=Query(...),
                  code_challenge:str=Query(...),code_challenge_method:str=Query(...)):
        if (response_type!="code" or client_id!=CLIENT_ID or
                redirect_uri!=CALLBACK or scope!="openid" or
                code_challenge_method!="S256" or len(code_challenge)!=43 or
                len(state)!=43 or len(nonce)!=43):
            raise HTTPException(400,"unsupported test authorization request")
        code=secrets.token_urlsafe(32)
        codes[code]=(code_challenge,nonce,int(time.time())+90)
        return RedirectResponse(CALLBACK+"?state="+state+"&code="+code,status_code=302)

    @app.post("/oidc-test/token")
    def token(grant_type:str=Form(...),code:str=Form(...),redirect_uri:str=Form(...),
              client_id:str=Form(...),code_verifier:str=Form(...)):
        if grant_type!="authorization_code" or redirect_uri!=CALLBACK or client_id!=CLIENT_ID:
            raise HTTPException(400,"invalid grant")
        pending=codes.pop(code,None)
        if pending is None or pending[2]<int(time.time()):
            raise HTTPException(400,"expired or replayed code")
        challenge,nonce,_=pending
        derived=base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest()).rstrip(b"=").decode()
        if not secrets.compare_digest(challenge,derived):
            raise HTTPException(400,"PKCE verifier mismatch")
        now=int(time.time())
        value=jwt.encode({"iss":ISSUER,"sub":os.environ["SME_E2E_IDP_SUBJECT"],
                           "aud":CLIENT_ID,"iat":now,"exp":now+120,"nonce":nonce},
                         key,algorithm="RS256",headers={"kid":"synthetic-e2e"})
        return {"id_token":value,"token_type":"Bearer"}

    return app

if __name__=="__main__":
    uvicorn.run(build_app(),host="127.0.0.1",port=8002,log_level="warning")
