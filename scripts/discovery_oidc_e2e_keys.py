"""Create short-lived RSA test IdP key material: local synthetic CI ONLY."""
import json
import os
from pathlib import Path
from urllib.parse import urlparse
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from jwt.algorithms import RSAAlgorithm

def main():
    dsn=urlparse(os.environ["SME_TEST_DATABASE_DSN"])
    if (os.getenv("SME_E2E_ONLY")!="1" or os.getenv("SME_E2E_OIDC_MODE")!="1"
        or dsn.hostname not in ("127.0.0.1","localhost") or dsn.path!="/sme_test"):
        raise SystemExit("Synthetic OIDC keys may only be generated for localhost sme_test")
    private_path=Path(os.environ["SME_E2E_IDP_KEY"])
    public_path=Path(os.environ["SME_E2E_IDP_JWKS"])
    if private_path.exists() or public_path.exists():
        raise SystemExit("Refusing to reuse or overwrite test key material")
    key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    private_path.write_bytes(key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()))
    private_path.chmod(0o600)
    jwk=json.loads(RSAAlgorithm.to_jwk(key.public_key()))
    jwk.update({"kid":"synthetic-e2e","use":"sig","alg":"RS256"})
    fd=os.open(str(public_path),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,"w",encoding="utf-8") as out:
        json.dump({"keys":[jwk]},out)
    print("Ephemeral IdP signing key and JWKS generated (no secrets printed)")

if __name__=="__main__":
    main()
