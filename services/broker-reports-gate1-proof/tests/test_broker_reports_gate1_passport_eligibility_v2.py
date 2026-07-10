from __future__ import annotations

import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from broker_reports_gate1.eligibility import build_document_source_eligibility


class BrokerReportsGate1PassportEligibilityV2Test(unittest.TestCase):
    def test_valid_passport_source_document_is_accepted_for_gate2(self):
        _, summary, handoff = self._decide(
            documents=[self._document("brdoc_source")],
            taxonomy=[self._taxonomy("brdoc_source", "operations_table")],
            passports=[self._passport("brdoc_source")],
        )

        self.assertEqual(summary["accepted_for_gate2"], 1)
        self.assertEqual(summary["status_counts"], {"accepted_for_gate2": 1})
        self.assertEqual(handoff["handoff_mode"], "full_package_ready_for_gate2")
        self.assertEqual(handoff["included_document_ids"], ["brdoc_source"])

    def test_valid_passport_can_accept_source_candidate_when_taxonomy_is_weak(self):
        eligibility, summary, handoff = self._decide(
            documents=[self._document("brdoc_candidate")],
            taxonomy=[self._taxonomy("brdoc_candidate", "unknown_or_needs_review")],
            passports=[self._passport("brdoc_candidate")],
        )

        entry = eligibility["entries"][0]
        self.assertEqual(entry["source_eligibility"], "accepted_as_source_candidate_for_gate2")
        self.assertTrue(entry["can_enter_gate2"])
        self.assertEqual(summary["accepted_as_source_candidate_for_gate2"], 1)
        self.assertEqual(handoff["handoff_mode"], "full_package_ready_for_gate2")

    def test_missing_passport_metadata_blocks_with_metadata_review_mode(self):
        eligibility, summary, handoff = self._decide(
            documents=[self._document("brdoc_missing")],
            taxonomy=[self._taxonomy("brdoc_missing", "operations_table")],
            passports=[
                self._passport(
                    "brdoc_missing",
                    missing_metadata_fields=["report_period_start"],
                    review_required=True,
                    metadata_confidence="medium",
                )
            ],
        )

        entry = eligibility["entries"][0]
        self.assertEqual(entry["source_eligibility"], "metadata_review_required")
        self.assertFalse(entry["can_enter_gate2"])
        self.assertEqual(summary["metadata_review_required"], 1)
        self.assertEqual(handoff["handoff_mode"], "gate2_blocked_requires_metadata_review")
        self.assertEqual(handoff["handoff_blocker_counts"]["metadata_review_required"], 1)

    def test_refined_period_gap_without_scope_blocks_gate2(self):
        eligibility, summary, handoff = self._decide(
            documents=[self._document("brdoc_missing_period")],
            taxonomy=[self._taxonomy("brdoc_missing_period", "source_broker_report")],
            passports=[
                self._passport(
                    "brdoc_missing_period",
                    missing_metadata_fields=["report_period_start", "report_period_end"],
                    review_required=True,
                    metadata_confidence="medium",
                    evidence_refs=[],
                )
            ],
            criticality_refinement_enabled=True,
        )

        entry = eligibility["entries"][0]
        self.assertEqual(entry["source_eligibility"], "metadata_review_required")
        self.assertFalse(entry["can_enter_gate2"])
        self.assertEqual(entry["clarification_criticality_basis"]["unresolved_critical_count"], 2)
        self.assertIn("critical_metadata_gap_blocks_gate2", entry["reason_codes"])
        self.assertEqual(handoff["handoff_mode"], "gate2_blocked_requires_metadata_review")
        self.assertEqual(handoff["handoff_blocker_counts"]["critical_metadata_review_required"], 1)
        self.assertEqual(summary["critical_metadata_review_required"], 1)

    def test_refined_period_gap_with_case_scope_and_operation_dates_is_deferred(self):
        eligibility, summary, handoff = self._decide(
            documents=[self._document("brdoc_missing_period", machine_readable_table=True)],
            taxonomy=[self._taxonomy("brdoc_missing_period", "operations_table")],
            passports=[
                self._passport(
                    "brdoc_missing_period",
                    role="source_operations_table",
                    missing_metadata_fields=["report_period_start", "report_period_end"],
                    review_required=True,
                    metadata_confidence="low",
                )
            ],
            input_context={"case_group_id": "case_group_safe", "case_tax_year": 2025},
            criticality_refinement_enabled=True,
        )

        entry = eligibility["entries"][0]
        basis = entry["clarification_criticality_basis"]["period_scope_basis"]
        self.assertEqual(entry["source_eligibility"], "accepted_for_gate2")
        self.assertTrue(entry["can_enter_gate2"])
        self.assertEqual(entry["clarification_criticality_basis"]["unresolved_critical_count"], 0)
        self.assertEqual(entry["clarification_criticality_basis"]["unresolved_clarifying_count"], 2)
        self.assertTrue(entry["clarification_criticality_basis"]["can_proceed_with_warning"])
        self.assertIn("period_deferred_to_gate2_operation_dates", entry["reason_codes"])
        self.assertIn("case_tax_year_provides_scope", basis["reason_codes"])
        self.assertEqual(handoff["handoff_mode"], "full_package_ready_for_gate2")
        self.assertTrue(handoff["can_proceed_with_warnings"])
        self.assertEqual(summary["warning_counts"]["clarifying"], 2)

    def test_refined_clarifying_account_gap_does_not_block_when_source_evidence_exists(self):
        eligibility, summary, handoff = self._decide(
            documents=[self._document("brdoc_missing_account")],
            taxonomy=[self._taxonomy("brdoc_missing_account", "operations_table")],
            passports=[
                self._passport(
                    "brdoc_missing_account",
                    missing_metadata_fields=["account_or_contract_candidate"],
                    review_required=True,
                    metadata_confidence="low",
                )
            ],
            criticality_refinement_enabled=True,
        )

        entry = eligibility["entries"][0]
        self.assertEqual(entry["source_eligibility"], "accepted_for_gate2")
        self.assertTrue(entry["can_enter_gate2"])
        self.assertTrue(entry["clarification_criticality_basis"]["can_proceed_with_warning"])
        self.assertEqual(entry["clarification_criticality_basis"]["unresolved_critical_count"], 0)
        self.assertEqual(entry["clarification_criticality_basis"]["unresolved_clarifying_count"], 1)
        self.assertIn("nonblocking_metadata_gaps_allowed_with_warning", entry["reason_codes"])
        self.assertEqual(handoff["handoff_mode"], "full_package_ready_for_gate2")
        self.assertTrue(handoff["can_proceed_with_warnings"])
        self.assertEqual(summary["warning_counts"]["clarifying"], 1)

    def test_refined_duplicate_canonical_choice_remains_blocking_before_ready_modes(self):
        eligibility, summary, handoff = self._decide(
            documents=[
                self._document("brdoc_source"),
                self._document("brdoc_duplicate", duplicate_of_document_id="brdoc_source"),
            ],
            taxonomy=[
                self._taxonomy("brdoc_source", "operations_table"),
                self._taxonomy("brdoc_duplicate", "operations_table"),
            ],
            passports=[
                self._passport("brdoc_source"),
                self._passport("brdoc_duplicate"),
            ],
            blockers=[self._blocker("brdoc_duplicate", "duplicate_review")],
            criticality_refinement_enabled=True,
        )

        entries = {entry["document_id"]: entry for entry in eligibility["entries"]}
        self.assertTrue(entries["brdoc_source"]["included_in_reduced_subset"])
        self.assertEqual(entries["brdoc_duplicate"]["source_eligibility"], "duplicate_needs_canonical_choice")
        self.assertEqual(summary["duplicate_needs_canonical_choice"], 1)
        self.assertEqual(handoff["handoff_mode"], "reduced_subset_ready_for_gate2")
        self.assertEqual(handoff["gate2_handoff_status"], "ready_with_reduced_subset")
        self.assertEqual(handoff["duplicate_review_document_ids"], ["brdoc_duplicate"])

    def test_refined_exact_duplicate_auto_canonicalizes_without_user_question(self):
        eligibility, summary, handoff = self._decide(
            documents=[
                self._document("brdoc_001_samehash", sha256="abc123", duplicate_group_id="dupgrp_abc123"),
                self._document(
                    "brdoc_002_samehash",
                    sha256="abc123",
                    duplicate_group_id="dupgrp_abc123",
                    duplicate_of_document_id="brdoc_001_samehash",
                ),
            ],
            taxonomy=[
                self._taxonomy("brdoc_001_samehash", "operations_table"),
                self._taxonomy("brdoc_002_samehash", "operations_table"),
            ],
            passports=[
                self._passport("brdoc_001_samehash", role="source_operations_table"),
                self._passport("brdoc_002_samehash", role="source_operations_table"),
            ],
            blockers=[self._blocker("brdoc_002_samehash", "duplicate_review")],
            criticality_refinement_enabled=True,
        )

        entries = {entry["document_id"]: entry for entry in eligibility["entries"]}
        canonical = entries["brdoc_002_samehash"]
        noncanonical = entries["brdoc_001_samehash"]
        self.assertEqual(canonical["source_eligibility"], "accepted_for_gate2")
        self.assertTrue(canonical["included_in_reduced_subset"])
        self.assertEqual(noncanonical["source_eligibility"], "excluded_from_gate2")
        self.assertTrue(noncanonical["exclusion_is_terminal"])
        self.assertIn("exact_duplicate_auto_canonical_selected", canonical["reason_codes"])
        self.assertIn("noncanonical_exact_duplicate_excluded", noncanonical["reason_codes"])
        self.assertEqual(summary["duplicate_needs_canonical_choice"], 0)
        self.assertEqual(summary["auto_resolved_exact_duplicate_groups"], 1)
        self.assertEqual(handoff["handoff_mode"], "reduced_subset_ready_for_gate2")
        self.assertEqual(handoff["duplicate_review_document_ids"], [])
        self.assertEqual(handoff["auto_resolved_duplicate_document_ids"], ["brdoc_001_samehash"])
        self.assertEqual(handoff["auto_canonical_duplicate_groups"][0]["canonical_document_id"], "brdoc_002_samehash")

    def test_source_policy_uncertainty_is_carried_forward_without_blocking_ingestion(self):
        eligibility, summary, handoff = self._decide(
            documents=[self._document("brdoc_policy")],
            taxonomy=[
                self._taxonomy(
                    "brdoc_policy",
                    "source_broker_report",
                    source_role_policy_status="review_required",
                    source_policy_review_required=True,
                )
            ],
            passports=[
                self._passport(
                    "brdoc_policy",
                    source_policy_effect="requires_policy_review",
                )
            ],
        )

        entry = eligibility["entries"][0]
        self.assertEqual(entry["source_eligibility"], "accepted_for_gate2")
        self.assertTrue(entry["included_in_reduced_subset"])
        self.assertIn("source_policy_uncertainty_carried_forward", entry["reason_codes"])
        self.assertEqual(summary["source_policy_review_required"], 0)
        self.assertEqual(handoff["handoff_mode"], "full_package_ready_for_gate2")
        self.assertEqual(handoff["source_policy_review_document_ids"], [])

    def test_duplicate_blocks_with_duplicate_resolution_mode(self):
        eligibility, summary, handoff = self._decide(
            documents=[self._document("brdoc_duplicate", duplicate_of_document_id="brdoc_original")],
            taxonomy=[self._taxonomy("brdoc_duplicate", "operations_table")],
            passports=[self._passport("brdoc_duplicate")],
            blockers=[self._blocker("brdoc_duplicate", "duplicate_review")],
        )

        entry = eligibility["entries"][0]
        self.assertEqual(entry["source_eligibility"], "duplicate_needs_canonical_choice")
        self.assertEqual(summary["duplicate_needs_canonical_choice"], 1)
        self.assertEqual(handoff["handoff_mode"], "gate2_blocked_requires_duplicate_resolution")
        self.assertEqual(handoff["duplicate_review_document_ids"], ["brdoc_duplicate"])

    def test_methodology_output_artifact_is_excluded_and_no_eligible_source_blocks(self):
        eligibility, summary, handoff = self._decide(
            documents=[self._document("brdoc_methodology")],
            taxonomy=[self._taxonomy("brdoc_methodology", "calculation_template")],
            passports=[
                self._passport(
                    "brdoc_methodology",
                    content_kind="output_or_calculation_artifact",
                    role="calculation_or_output_artifact",
                    source_candidate_confidence="none",
                    metadata_confidence="high",
                    source_policy_effect="excluded_from_gate2",
                )
            ],
        )

        entry = eligibility["entries"][0]
        self.assertEqual(entry["source_eligibility"], "methodology_or_output_artifact")
        self.assertTrue(entry["exclusion_is_terminal"])
        self.assertEqual(summary["methodology_or_output_artifact"], 1)
        self.assertEqual(summary["excluded_from_gate2"], 1)
        self.assertEqual(handoff["handoff_mode"], "gate2_blocked_no_eligible_sources")

    def _decide(
        self,
        *,
        documents,
        taxonomy,
        passports,
        blockers=None,
        input_context=None,
        criticality_refinement_enabled=False,
    ):
        return build_document_source_eligibility(
            run_id="normrun_test",
            documents=documents,
            taxonomy_candidates=taxonomy,
            blockers=blockers or [],
            document_metadata_passports=passports,
            input_context=input_context or {},
            criticality_refinement_enabled=criticality_refinement_enabled,
        )

    def _document(
        self,
        document_id: str,
        *,
        duplicate_of_document_id: str | None = None,
        duplicate_group_id: str | None = None,
        sha256: str | None = None,
        machine_readable_table: bool = False,
    ) -> dict:
        return {
            "document_id": document_id,
            "container_format": "csv",
            "duplicate_of_document_id": duplicate_of_document_id,
            "duplicate_group_id": duplicate_group_id,
            "sha256": sha256,
            "machine_readable_table": machine_readable_table,
        }

    def _taxonomy(
        self,
        document_id: str,
        document_class: str,
        *,
        source_role_policy_status: str = "not_applicable",
        source_policy_review_required: bool = False,
    ) -> dict:
        return {
            "document_id": document_id,
            "document_class_candidate": document_class,
            "source_role_policy_status": source_role_policy_status,
            "source_policy_review_required": source_policy_review_required,
            "safe_reason_codes": [document_class],
        }

    def _blocker(self, document_id: str, code: str) -> dict:
        return {
            "blocker_id": f"blocker_{document_id}_{code}",
            "document_id": document_id,
            "code": code,
        }

    def _passport(
        self,
        document_id: str,
        *,
        content_kind: str = "source_report_candidate",
        role: str = "source_broker_report",
        source_candidate_confidence: str = "high",
        metadata_confidence: str = "high",
        source_policy_effect: str = "accepted_candidate_if_policy_allows",
        missing_metadata_fields: list[str] | None = None,
        conflict_flags: list[str] | None = None,
        review_required: bool = False,
        evidence_refs: list[str] | None = None,
    ) -> dict:
        safe_evidence_refs = [document_id, f"llmpkg_{document_id}"] if evidence_refs is None else evidence_refs
        return {
            "schema_version": "document_metadata_passport_v0",
            "passport_id": f"passport_{document_id}",
            "normalization_run_id": "normrun_test",
            "document_id": document_id,
            "passport_status": "validated",
            "content_kind": content_kind,
            "role_hypotheses": [
                {
                    "role": role,
                    "confidence": "high",
                    "reason_codes": ["test"],
                    "evidence_refs": safe_evidence_refs,
                    "source_policy_effect": source_policy_effect,
                }
            ],
            "source_candidate_confidence": source_candidate_confidence,
            "metadata_confidence": metadata_confidence,
            "evidence_refs": safe_evidence_refs,
            "missing_metadata_fields": missing_metadata_fields or [],
            "conflict_flags": conflict_flags or [],
            "review_required": review_required,
            "validator_status": "passed",
        }


if __name__ == "__main__":
    unittest.main()
