"""Execute consumed owner approval proof over a distinct least-privilege DB connection.

The supplied connect callback MUST authenticate as a dedicated execution
principal holding only sme_approval. Never reuse general app or issuer pool.
"""
from __future__ import annotations
from collections.abc import Callable
from uuid import UUID
from .asahi_stepup_oidc_flow import StepupAction


class PostgresApprovalExecutor:
    def __init__(self, connect: Callable):
        if not callable(connect):
            raise ValueError("connection factory required")
        self.connect=connect

    def __call__(self, session_digest: bytes, action: StepupAction,
                 proof: UUID) -> bool:
        with self.connect() as conn:
            with conn.transaction():
                if action.action=="approve":
                    row=conn.execute(
                        "SELECT sme.approve_asahi_delivery_stepup(%s,%s,%s,%s,%s,%s)",
                        (session_digest,action.tenant_id,proof,action.channel,
                         action.destination_ref,action.secret_ref)
                    ).fetchone()
                else:
                    row=conn.execute(
                        "SELECT sme.revoke_asahi_delivery_stepup(%s,%s,%s)",
                        (session_digest,action.tenant_id,proof)
                    ).fetchone()
                return bool(row and row[0])
