"""Pure business-discovery evidence model. NOT a database/API/auth boundary.

All inputs are caller-controlled. Host services MUST authenticate the actor,
resolve the tenant server-side, check permissions and persist audit records.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping


class EvidenceClass(str, Enum):
    EXPLICIT = "explicit"
    INFERRED = "inferred"
    UNVERIFIED = "unverified"


class ApprovalState(str, Enum):
    PROPOSED = "proposed"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class CandidateDecision(str, Enum):
    KEEP = "keep"
    INTEGRATE = "integrate"
    BUY = "buy"
    BUILD = "build"
    REPLACE = "replace"
    DEFER = "defer"


@dataclass(frozen=True)
class SourceReference:
    source_id: str
    company_code: str
    document_name: str
    page: int
    visibility: str = "private"

    def __post_init__(self) -> None:
        if not self.source_id.strip() or not self.company_code.strip():
            raise ValueError("source and company IDs are required")
        if not self.document_name.strip() or self.page < 1:
            raise ValueError("document name and page >=1 are required")
        if self.visibility != "private":
            raise ValueError("source files must remain private by default")


@dataclass(frozen=True)
class BusinessRequirement:
    requirement_id: str
    tenant_id: str
    source_id: str | None
    statement: str
    classification: EvidenceClass
    approval: ApprovalState = ApprovalState.PROPOSED

    def __post_init__(self) -> None:
        if not self.requirement_id.strip() or not self.tenant_id.strip():
            raise ValueError("requirement ID and tenant ID are required")
        if not self.statement.strip():
            raise ValueError("requirement statement is required")
        if not isinstance(self.classification, EvidenceClass):
            raise ValueError("classification must be explicit, inferred or unverified")
        if not isinstance(self.approval, ApprovalState):
            raise ValueError("invalid approval state")
        if self.classification is EvidenceClass.EXPLICIT and not self.source_id:
            raise ValueError("explicit evidence must reference a source")
        if self.classification is not EvidenceClass.EXPLICIT and self.approval is ApprovalState.CONFIRMED:
            raise ValueError("inferred/unverified evidence cannot be confirmed as a source fact")


@dataclass(frozen=True)
class DecisionProposal:
    requirement_id: str
    tenant_id: str
    system_name: str
    decision: CandidateDecision
    owner_approved: bool = False

    def __post_init__(self) -> None:
        if not self.requirement_id.strip() or not self.tenant_id.strip():
            raise ValueError("requirement ID and tenant ID are required")
        if not self.system_name.strip():
            raise ValueError("system name is required")
        if not isinstance(self.decision, CandidateDecision):
            raise ValueError("invalid decision")


# Archetype-specific constraints are *research hypotheses* and are not customer
# authorizations. Caller must still check actual contract, ownership and scope.
RYOKI_PROTECTED_SYSTEMS = frozenset({
    "production management", "accounting", "hr"
})


def check_research_constraints(company_code: str, proposal: DecisionProposal) -> None:
    """Refuse obviously out-of-scope recommendations before presenting a draft."""
    company = company_code.strip().upper()
    system = " ".join(proposal.system_name.casefold().replace("_", " ").split())
    if (company == "R" and proposal.decision is CandidateDecision.REPLACE
            and system in RYOKI_PROTECTED_SYSTEMS):
        raise ValueError("Ryoki excludes replacement of production, accounting and HR")
    if (company == "B" and proposal.decision is CandidateDecision.REPLACE
            and system in {"sieve os", "sieveos"} and not proposal.owner_approved):
        raise ValueError("Beight requires owner approval before replacing existing SIEVE OS")


def validate_research_case(
    tenant_id: str,
    sources: Mapping[str, SourceReference],
    requirements: list[BusinessRequirement],
) -> None:
    """Validate a *single* scoped case; this is NOT a substitute for database RLS."""
    if not tenant_id.strip():
        raise ValueError("tenant ID required")
    seen: set[str] = set()
    for item in requirements:
        if item.tenant_id != tenant_id:
            raise PermissionError("cross-tenant requirement in case")
        if item.requirement_id in seen:
            raise ValueError("duplicate requirement ID")
        seen.add(item.requirement_id)
        if item.source_id is not None:
            source = sources.get(item.source_id)
            if source is None:
                raise ValueError("unresolved source reference")
    # The caller is responsible for permission checks on sources and their bytes.
