"""Boundary and classification tests for the non-persistent discovery model."""
import unittest

from sme_partner.business_discovery import (
    ApprovalState, BusinessRequirement, CandidateDecision, DecisionProposal,
    EvidenceClass, SourceReference, check_research_constraints,
    validate_research_case,
)


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.sources = {"b-sheet": SourceReference(
            "b-sheet", "B", "pj_Beight.pdf", 1
        )}

    def test_explicit_source_traceable(self):
        item = BusinessRequirement(
            "B-01", "tenant-a", "b-sheet", "Fragmented salon data",
            EvidenceClass.EXPLICIT, ApprovalState.CONFIRMED
        )
        validate_research_case("tenant-a", self.sources, [item])

    def test_explicit_requires_source(self):
        with self.assertRaises(ValueError):
            BusinessRequirement("B-01", "tenant-a", None, "text", EvidenceClass.EXPLICIT)

    def test_inferred_cannot_be_confirmed_source_fact(self):
        with self.assertRaises(ValueError):
            BusinessRequirement("B-02", "tenant-a", "b-sheet", "AI tool",
                                EvidenceClass.INFERRED, ApprovalState.CONFIRMED)

    def test_unknown_evidence_label_is_rejected(self):
        with self.assertRaises(ValueError):
            BusinessRequirement("X-1", "tenant-a", None, "text", "explicit")

    def test_unknown_approval_is_rejected(self):
        with self.assertRaises(ValueError):
            BusinessRequirement("X-1", "tenant-a", None, "text",
                                EvidenceClass.UNVERIFIED, "confirmed")

    def test_empty_statement_rejected(self):
        with self.assertRaises(ValueError):
            BusinessRequirement("X-1", "tenant-a", None, "  ", EvidenceClass.UNVERIFIED)

    def test_unresolved_source_rejected(self):
        req = BusinessRequirement("B-01", "tenant-a", "absent", "text", EvidenceClass.EXPLICIT)
        with self.assertRaises(ValueError):
            validate_research_case("tenant-a", self.sources, [req])

    def test_cross_tenant_rejected(self):
        req = BusinessRequirement("B-01", "tenant-b", "b-sheet", "text", EvidenceClass.EXPLICIT)
        with self.assertRaises(PermissionError):
            validate_research_case("tenant-a", self.sources, [req])

    def test_duplicate_id_rejected(self):
        req = BusinessRequirement("B-01", "tenant-a", "b-sheet", "text", EvidenceClass.EXPLICIT)
        with self.assertRaises(ValueError):
            validate_research_case("tenant-a", self.sources, [req, req])

    def test_public_source_rejected(self):
        with self.assertRaises(ValueError):
            SourceReference("a", "B", "pj_Beight.pdf", 1, "public")

    def test_invalid_page_rejected(self):
        with self.assertRaises(ValueError):
            SourceReference("a", "B", "pj_Beight.pdf", 0)

    def test_ryoki_protected_system_no_replace(self):
        for system in ("production_management", "Accounting", " hr "):
            with self.subTest(system=system), self.assertRaises(ValueError):
                check_research_constraints("R", DecisionProposal(
                    "R-05", "tenant-r", system, CandidateDecision.REPLACE
                ))

    def test_ryoki_integrate_is_not_blocked(self):
        check_research_constraints("R", DecisionProposal(
            "R-05", "tenant-r", "production management", CandidateDecision.INTEGRATE
        ))

    def test_beight_rewrite_requires_approval(self):
        with self.assertRaises(ValueError):
            check_research_constraints("B", DecisionProposal(
                "B-02", "tenant-b", "SIEVE OS", CandidateDecision.REPLACE
            ))

    def test_beight_approved_rewrite_allowed_as_research(self):
        check_research_constraints("B", DecisionProposal(
            "B-02", "tenant-b", "SIEVE OS", CandidateDecision.REPLACE, owner_approved=True
        ))

    def test_other_domains_do_not_inherit_constraints(self):
        check_research_constraints("L", DecisionProposal(
            "L-01", "tenant-l", "production management", CandidateDecision.REPLACE
        ))


if __name__ == "__main__":
    unittest.main()
