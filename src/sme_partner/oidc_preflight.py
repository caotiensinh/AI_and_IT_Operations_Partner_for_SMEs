"""Read-only readiness preflight for a real enterprise OIDC cookie-BFF deployment.

The operator runs this before enabling customer access. Database checks use
read-only transactions; failures are reported as sanitized, stable check IDs.
No session credentials, DSNs, tokens, secrets, JWKs or private keys are emitted.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import json
import os
from urllib.parse import urlsplit

import psycopg

from .discovery_runtime import _REQUIRED
from .oidc_provider import PinnedProvider, ProviderHTTP, ProviderUnavailable, VerifiedProviderClient


@dataclass(frozen=True)
class Check:
    name: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class Report:
    checks: tuple[Check, ...]

    @property
    def ready(self) -> bool:
        required = {
            "config.required", "config.database_split", "config.csrf",
            "config.origin", "config.callback", "config.mfa_policy",
            "provider.pinned", "provider.discovery", "provider.jwks",
            "db.sme_app.identity", "db.sme_auth.identity",
        }
        present = {item.name for item in self.checks}
        # Skipped live provider/database checks can never mean deployment-ready.
        return required.issubset(present) and all(item.passed for item in self.checks)

    def public_dict(self) -> dict:
        return {"ready": self.ready,
                "checks": [{"name": c.name, "passed": c.passed, "detail": c.detail}
                           for c in self.checks]}


def _check(name: str, result: bool, good: str, bad: str) -> Check:
    return Check(name, bool(result), good if result else bad)


def _db_verify(connect: Callable[[], psycopg.Connection], *, expected_role: str) -> tuple[Check, ...]:
    prefix="db." + expected_role
    try:
        with connect() as conn:
            with conn.transaction():
                conn.execute("SET TRANSACTION READ ONLY")
                row=conn.execute(
                    "SELECT current_user, session_user, r.rolsuper, r.rolbypassrls, "
                    "pg_has_role(current_user, %s, 'SET'), "
                    "pg_has_role(current_user, %s, 'SET') "
                    "FROM pg_roles r WHERE r.rolname=current_user",
                    (expected_role,"sme_auth" if expected_role=="sme_app" else "sme_app"),
                ).fetchone()
                if row is None:
                    return (Check(prefix+".identity",False,"Database login role not found"),)
                current, login, superuser, bypass, can_assume, cross_assume=row
                identity_ok=(current==login and current not in ("postgres","sme_app","sme_auth")
                             and not superuser and not bypass and can_assume and not cross_assume)
                result=[_check(prefix+".identity",identity_ok,
                    "Dedicated least-privilege login and role boundary confirmed",
                    "Database login is privileged, shared, or has incorrect role grants")]
                conn.execute("SET LOCAL ROLE "+expected_role)
                if expected_role=="sme_app":
                    checks=(
                        ("execute_tenant_listing","has_function_privilege(current_user, 'sme.list_browser_session_tenants(bytea)', 'EXECUTE')",True),
                        ("no_session_issue","has_function_privilege(current_user, 'sme.issue_oidc_session(text,text,bytea,integer)', 'EXECUTE')",False),
                        ("no_pending_login","has_function_privilege(current_user, 'sme.begin_oidc_login(bytea,bytea,text,text)', 'EXECUTE')",False),
                        ("no_raw_session_read","has_table_privilege(current_user, 'sme.sessions', 'SELECT')",False),
                        ("no_raw_login_read","has_table_privilege(current_user, 'sme.pending_oidc_logins', 'SELECT')",False),
                    )
                else:
                    checks=(
                        ("can_begin","has_function_privilege(current_user, 'sme.begin_oidc_login(bytea,bytea,text,text)', 'EXECUTE')",True),
                        ("can_consume","has_function_privilege(current_user, 'sme.consume_oidc_login(bytea,bytea)', 'EXECUTE')",True),
                        ("can_issue","has_function_privilege(current_user, 'sme.issue_oidc_session(text,text,bytea,integer)', 'EXECUTE')",True),
                        ("no_tenant_listing","has_function_privilege(current_user, 'sme.list_browser_session_tenants(bytea)', 'EXECUTE')",False),
                        ("no_raw_session_read","has_table_privilege(current_user, 'sme.sessions', 'SELECT')",False),
                        ("no_raw_login_read","has_table_privilege(current_user, 'sme.pending_oidc_logins', 'SELECT')",False),
                    )
                for name,expr,expected in checks:
                    # Expressions are all hard-coded above; not user input.
                    actual=bool(conn.execute("SELECT "+expr).fetchone()[0])
                    result.append(_check(prefix+"."+name,actual==expected,
                        "Privilege boundary confirmed",
                        "Database function/table privilege differs from least-privilege policy"))
                return tuple(result)
    except (psycopg.Error, OSError, ValueError):
        return (Check(prefix+".connection",False,"Connection or privilege probe failed"),)


def run_preflight(
    env: Mapping[str,str] | None = None,
    *, provider_http: ProviderHTTP | None = None,
    db_connect: Callable[[str], psycopg.Connection] | None = None,
    check_network: bool = True,
    check_database: bool = True,
) -> Report:
    values = env if env is not None else os.environ
    checks: list[Check]=[]
    missing=[key for key in _REQUIRED if not values.get(key)]
    checks.append(_check("config.required",not missing,
        "Required settings are present","Required settings are incomplete"))
    if missing:
        return Report(tuple(checks))
    def probe(name: str, fn: Callable[[], bool], success: str, failure: str) -> bool:
        try:
            passed=bool(fn())
        except (ValueError,TypeError,ProviderUnavailable,OSError,psycopg.Error):
            passed=False
        checks.append(_check(name,passed,success,failure))
        return passed
    probe("config.database_split",
          lambda: values["SME_APP_DATABASE_DSN"]!=values["SME_AUTH_DATABASE_DSN"],
          "Separate database connections configured","App and auth database connections are identical")
    probe("config.csrf",lambda:len(bytes.fromhex(values["SME_CSRF_SECRET_HEX"]))>=32,
          "CSRF secret meets length requirement","CSRF secret is invalid or too short")
    probe("config.origin",lambda:
          (lambda u:u.scheme=="https" and bool(u.hostname) and
           not u.username and not u.password and not u.query and not u.fragment and
           u.path in ("","/"))(urlsplit(values["SME_TRUSTED_ORIGIN"])),
          "HTTPS origin configured","Trusted origin is not a fixed HTTPS origin")
    probe("config.callback",lambda:
          (values["SME_OIDC_REDIRECT_URI"]==
           values["SME_TRUSTED_ORIGIN"].rstrip("/")+"/auth/oidc/callback"),
          "Callback matches HTTPS origin","OIDC callback does not match BFF origin")
    def policy() -> bool:
        mfa=values.get("SME_OIDC_REQUIRE_MFA","true").lower()
        return mfa=="true"
    probe("config.mfa_policy",policy,
          "MFA required for enterprise onboarding",
          "MFA policy is disabled or invalid for enterprise onboarding")
    provider:VerifiedProviderClient|None=None
    try:
        provider=VerifiedProviderClient(PinnedProvider(
            issuer=values["SME_OIDC_ISSUER"],
            authorization_endpoint=values["SME_OIDC_AUTHORIZATION_ENDPOINT"],
            token_endpoint=values["SME_OIDC_TOKEN_ENDPOINT"],
            jwks_uri=values["SME_OIDC_JWKS_URI"],
            client_id=values["SME_OIDC_CLIENT_ID"],
            redirect_uri=values["SME_OIDC_REDIRECT_URI"],
            client_secret=values["SME_OIDC_CLIENT_SECRET"],
            require_mfa=True,
            accepted_acr=frozenset(filter(None,(
                s.strip() for s in values.get("SME_OIDC_ACCEPTED_ACR","").split(",")))),
        ),http=provider_http)
        checks.append(Check("provider.pinned",True,"OIDC endpoints and registration format accepted"))
    except (ValueError,TypeError):
        checks.append(Check("provider.pinned",False,"OIDC provider registration is not valid"))
    if check_network:
        if provider is None:
            checks.append(Check("provider.discovery",False,"Provider configuration invalid"))
            checks.append(Check("provider.jwks",False,"Provider configuration invalid"))
        else:
            probe("provider.discovery",lambda:provider.verify_discovery() is None,
                  "Pinned discovery metadata verified",
                  "Provider metadata unavailable or differs from operator-pinned values")
            probe("provider.jwks",lambda:bool(provider.fetch_trusted_jwks()["keys"]),
                  "RS256 public signing keys verified",
                  "Provider signing keys invalid or unavailable")
    if check_database:
        connector=db_connect or (lambda dsn:psycopg.connect(dsn))
        for role,dsn_key in (("sme_app","SME_APP_DATABASE_DSN"),
                             ("sme_auth","SME_AUTH_DATABASE_DSN")):
            checks.extend(_db_verify(lambda dsn=values[dsn_key]:connector(dsn),
                                     expected_role=role))
    return Report(tuple(checks))


def main() -> int:
    # This command NEVER prints secret-bearing raw exceptions, DSNs, provider
    # tokens, request/response bodies or full URLs.
    report=run_preflight()
    print(json.dumps(report.public_dict(),sort_keys=True))
    return 0 if report.ready else 1


if __name__=="__main__":
    raise SystemExit(main())
