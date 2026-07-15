from __future__ import annotations

import copy
import unittest

from broker_reports_gate1.pdf_hybrid_contracts import sha256_json
from broker_reports_gate1.pdf_table_intake_contracts import (
    FACTORY_REQUIRED,
    FORBIDDEN,
    PDF_TABLE_INTAKE_DECISION_REVISION,
    PDF_TABLE_INTAKE_DECISION_SCHEMA,
    PdfTableIntakeContractConfig,
    PdfTableIntakeContractError,
    PdfTableIntakeContractFactory,
    PdfTableIntakeContractRuntime,
)


class PdfTableIntakeContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runtime = PdfTableIntakeContractFactory().create()

    def test_factory_is_required_and_budget_overrides_are_forbidden(self) -> None:
        self.assertIn("Factory.create", FACTORY_REQUIRED)
        self.assertIn("metadata only", FORBIDDEN)
        with self.assertRaisesRegex(
            PdfTableIntakeContractError,
            "pdf_table_intake_factory_required",
        ):
            PdfTableIntakeContractRuntime(PdfTableIntakeContractConfig())
        with self.assertRaisesRegex(
            PdfTableIntakeContractError,
            "pdf_table_intake_budget_override_forbidden",
        ):
            PdfTableIntakeContractFactory(
                PdfTableIntakeContractConfig(maximum_atoms=1_001)
            ).create()

    def test_shape_heuristics_are_metadata_not_processability_filters(self) -> None:
        result = self.runtime.build_decisions(
            **_candidate_facts(),
            metadata={
                "rows_total": 1,
                "columns_total": 99,
                "density": 0.001,
                "bbox_area_ratio": 0.999,
                "empty_row_bands_total": 42,
                "empty_column_bands_total": 41,
                "table_strategy_ref": "unusual_borderless_strategy",
                "ruling_evidence_total": 0,
            },
        )

        self.assertEqual("plausible", result["detection"]["decision"])
        self.assertEqual("processable", result["processability"]["decision"])
        self.assertEqual([], result["processability"]["reason_codes"])
        self.assertEqual("not_evaluated", result["holdout"]["decision"])
        self.assertEqual(PDF_TABLE_INTAKE_DECISION_SCHEMA, result["schema_version"])
        self.assertEqual(PDF_TABLE_INTAKE_DECISION_REVISION, result["revision"])
        self.assertNotIn("policy_version", result)
        bindings = [
            result[name]["evidence_binding"]
            for name in ("detection", "processability", "holdout")
        ]
        self.assertEqual([bindings[0]] * 3, bindings)
        self.assertEqual(_identity(), bindings[0])
        self.assertEqual([], self.runtime.validate_decisions(result))

    def test_technical_failures_block_with_exact_reasons_only(self) -> None:
        facts = _candidate_facts()
        facts.update(
            coordinate_bboxes=[[5.0, 5.0, 95.0, 45.0]] * 1_001,
            provenance_verified=False,
            crop_identity_verified=False,
            exact_ownership_verified=False,
            atom_count=1_001,
            model_json_bytes=48 * 1024 + 1,
            counted_input_tokens=20_001,
            image_count=2,
            crop_count=0,
            pdf_count=1,
            image_bytes=8 * 1024 * 1024 + 1,
        )

        result = self.runtime.build_decisions(
            **facts,
            metadata={
                "rows_total": 200,
                "density": 0.0,
                "empty_column_bands_total": 100,
            },
        )

        self.assertEqual("unsupported", result["processability"]["decision"])
        self.assertEqual(
            [
                "candidate_atom_budget_exceeded",
                "candidate_crop_count_invalid",
                "counted_input_token_budget_exceeded",
                "crop_identity_unverified",
                "exact_ownership_unverified",
                "image_budget_exceeded",
                "image_count_invalid",
                "model_json_budget_exceeded",
                "pdf_payload_forbidden",
                "provenance_unverified",
            ],
            result["processability"]["reason_codes"],
        )
        rendered_reasons = " ".join(result["processability"]["reason_codes"])
        self.assertNotIn("row", rendered_reasons)
        self.assertNotIn("density", rendered_reasons)
        self.assertNotIn("area", rendered_reasons)
        self.assertNotIn("empty", rendered_reasons)
        self.assertNotIn("strategy", rendered_reasons)

    def test_coordinates_must_be_finite_and_owned_by_the_candidate_bbox(self) -> None:
        facts = _candidate_facts()
        facts.update(
            coordinate_bboxes=[
                [5.0, 5.0, 20.0, 20.0],
                [90.0, 40.0, 110.0, 55.0],
                [float("nan"), 1.0, 2.0, 3.0],
            ],
            atom_count=3,
        )

        result = self.runtime.build_decisions(**facts)

        self.assertEqual("unsupported", result["processability"]["decision"])
        self.assertEqual(
            [
                "coordinate_bbox_invalid",
                "coordinate_bbox_outside_owned_bbox",
            ],
            result["processability"]["reason_codes"],
        )

    def test_upstream_overflow_is_absence_not_implausibility(self) -> None:
        result = self.runtime.build_decisions(
            **_candidate_facts(
                detection_decision="implausible",
                detection_reason_codes=["no_candidate_detected"],
                upstream_failure_reason_codes=["pdf_inventory_limit_reached"],
            ),
        )

        self.assertEqual(
            "absent_due_to_upstream_failure",
            result["detection"]["decision"],
        )
        self.assertEqual(
            ["pdf_inventory_limit_reached"],
            result["detection"]["reason_codes"],
        )
        self.assertEqual("unsupported", result["processability"]["decision"])
        self.assertEqual(
            ["pdf_inventory_limit_reached"],
            result["processability"]["reason_codes"],
        )

    def test_identity_and_evidence_are_closed_and_scope_specific(self) -> None:
        candidate = self.runtime.build_decisions(**_candidate_facts())
        self.assertEqual([], self.runtime.validate_decisions(candidate))

        for name, value in (
            ("pdf_sha256", "A" * 64),
            ("evidence_checksum", "0" * 63),
            ("document_ref", " document_001"),
            ("page_number", 0),
        ):
            with (
                self.subTest(name=name),
                self.assertRaisesRegex(
                    PdfTableIntakeContractError,
                    "pdf_table_intake_identity_invalid",
                ),
            ):
                self.runtime.build_decisions(**_candidate_facts(**{name: value}))

        with self.assertRaisesRegex(
            PdfTableIntakeContractError,
            "pdf_table_intake_table_ref_required",
        ):
            self.runtime.build_decisions(**_candidate_facts(table_ref=None))
        with self.assertRaisesRegex(
            PdfTableIntakeContractError,
            "pdf_table_intake_page_table_ref_forbidden",
        ):
            self.runtime.build_decisions(
                **_page_facts(table_ref="table_not_allowed_on_page_scope")
            )

    def test_finalization_adds_actual_count_without_decision_drift(self) -> None:
        source = self.runtime.build_decisions(
            **_candidate_facts(),
            holdout_decision="selected",
            holdout_reason_codes=["preregistered_sampling_selection"],
            metadata={"rows_total": 31, "density": 0.03},
        )

        finalized = self.runtime.finalize_decisions(
            decisions=source,
            actual_counted_input_tokens=20_001,
        )

        self.assertIsNone(source["technical_facts"]["counted_input_tokens"])
        self.assertEqual(
            20_001,
            finalized["technical_facts"]["counted_input_tokens"],
        )
        self.assertEqual(source["detection"], finalized["detection"])
        self.assertEqual(source["holdout"], finalized["holdout"])
        self.assertEqual(source["metadata"], finalized["metadata"])
        self.assertEqual(
            source["detection"]["evidence_binding"],
            finalized["processability"]["evidence_binding"],
        )
        self.assertEqual("unsupported", finalized["processability"]["decision"])
        self.assertEqual(
            ["counted_input_token_budget_exceeded"],
            finalized["processability"]["reason_codes"],
        )
        self.assertNotEqual(source["contract_checksum"], finalized["contract_checksum"])
        self.assertEqual([], self.runtime.validate_decisions(source))
        self.assertEqual([], self.runtime.validate_decisions(finalized))
        with self.assertRaisesRegex(
            PdfTableIntakeContractError,
            "pdf_table_intake_counted_input_tokens_conflict",
        ):
            self.runtime.finalize_decisions(
                decisions=finalized,
                actual_counted_input_tokens=20_000,
            )

    def test_finalization_forces_upstream_absence_and_technical_terminal(self) -> None:
        source = self.runtime.build_decisions(
            **_candidate_facts(
                detection_decision="implausible",
                detection_reason_codes=["prose_region_detected"],
            )
        )

        finalized = self.runtime.finalize_decisions(
            decisions=source,
            upstream_failure_reason_codes=[
                "pdf_layout_document_inventory_budget_exceeded"
            ],
        )

        expected_reasons = ["pdf_layout_document_inventory_budget_exceeded"]
        self.assertEqual(
            "absent_due_to_upstream_failure",
            finalized["detection"]["decision"],
        )
        self.assertEqual(expected_reasons, finalized["detection"]["reason_codes"])
        self.assertEqual("unsupported", finalized["processability"]["decision"])
        self.assertEqual(expected_reasons, finalized["processability"]["reason_codes"])
        self.assertEqual(source["holdout"], finalized["holdout"])
        self.assertEqual([], self.runtime.validate_decisions(finalized))

    def test_processability_never_selects_a_holdout(self) -> None:
        not_evaluated = self.runtime.build_decisions(**_candidate_facts())
        not_selected = self.runtime.build_decisions(
            **_candidate_facts(),
            holdout_decision="not_selected",
            holdout_reason_codes=["preregistered_sampling_exclusion"],
        )
        selected = self.runtime.build_decisions(
            **_candidate_facts(),
            holdout_decision="selected",
            holdout_reason_codes=["preregistered_sampling_selection"],
        )

        self.assertEqual(
            ["processable", "processable", "processable"],
            [
                item["processability"]["decision"]
                for item in (not_evaluated, not_selected, selected)
            ],
        )
        self.assertEqual(
            ["not_evaluated", "not_selected", "selected"],
            [
                item["holdout"]["decision"]
                for item in (not_evaluated, not_selected, selected)
            ],
        )

    def test_page_path_has_no_atoms_and_at_most_two_region_proposals(self) -> None:
        processable = self.runtime.build_decisions(
            **_page_facts(
                proposed_region_bboxes=[
                    [10.0, 10.0, 300.0, 350.0],
                    [310.0, 400.0, 600.0, 780.0],
                ]
            )
        )
        blocked = self.runtime.build_decisions(
            **_page_facts(
                atom_count=1,
                coordinate_bboxes=[[1.0, 1.0, 2.0, 2.0]],
                proposed_region_bboxes=[
                    [10.0, 10.0, 300.0, 350.0],
                    [200.0, 200.0, 400.0, 450.0],
                    [410.0, 500.0, 700.0, 900.0],
                ],
            )
        )

        self.assertEqual("processable", processable["processability"]["decision"])
        self.assertEqual(
            [
                "page_atoms_present_before_region_proposal",
                "page_region_bbox_outside_page",
                "page_region_proposal_budget_exceeded",
                "page_region_proposals_overlap",
            ],
            blocked["processability"]["reason_codes"],
        )

    def test_checksum_detects_post_build_mutation(self) -> None:
        result = self.runtime.build_decisions(**_candidate_facts())
        mutated = copy.deepcopy(result)
        mutated["metadata"]["rows_total"] = 999

        self.assertEqual(
            ["pdf_table_intake_checksum_invalid"],
            self.runtime.validate_decisions(mutated),
        )
        malformed = copy.deepcopy(result)
        malformed["technical_facts"]["atom_count"] = "two"
        self.assertEqual(
            [
                "pdf_table_intake_checksum_invalid",
                "pdf_table_intake_technical_facts_invalid",
            ],
            self.runtime.validate_decisions(malformed),
        )

        identity_tampered = copy.deepcopy(result)
        identity_tampered["detection"]["evidence_binding"]["pdf_sha256"] = "A" * 64
        unsigned = copy.deepcopy(identity_tampered)
        unsigned.pop("contract_checksum")
        identity_tampered["contract_checksum"] = sha256_json(unsigned)
        self.assertEqual(
            ["pdf_table_intake_evidence_binding_invalid"],
            self.runtime.validate_decisions(identity_tampered),
        )

        binding_drift = copy.deepcopy(result)
        binding_drift["holdout"]["evidence_binding"]["evidence_checksum"] = "c" * 64
        unsigned = copy.deepcopy(binding_drift)
        unsigned.pop("contract_checksum")
        binding_drift["contract_checksum"] = sha256_json(unsigned)
        self.assertEqual(
            ["pdf_table_intake_evidence_binding_drift"],
            self.runtime.validate_decisions(binding_drift),
        )

        with self.assertRaisesRegex(
            PdfTableIntakeContractError,
            "pdf_table_intake_finalize_source_invalid",
        ):
            self.runtime.finalize_decisions(
                decisions=mutated,
                actual_counted_input_tokens=1_500,
            )

    def test_metadata_cannot_shadow_identity_or_execution_facts(self) -> None:
        for key in (
            "document_ref",
            "evidence_checksum",
            "counted_input_tokens",
            "upstream_failure_reason_codes",
        ):
            with (
                self.subTest(key=key),
                self.assertRaisesRegex(
                    PdfTableIntakeContractError,
                    "pdf_table_intake_metadata_decision_forbidden",
                ),
            ):
                self.runtime.build_decisions(
                    **_candidate_facts(), metadata={key: "shadow"}
                )


def _candidate_facts(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        **_identity(),
        "scope": "candidate_crop",
        "detection_decision": "plausible",
        "page_bbox": [0.0, 0.0, 100.0, 50.0],
        "candidate_bbox": [4.0, 4.0, 96.0, 46.0],
        "coordinate_bboxes": [
            [5.0, 5.0, 20.0, 20.0],
            [22.0, 5.0, 40.0, 20.0],
        ],
        "provenance_verified": True,
        "crop_identity_verified": True,
        "exact_ownership_verified": True,
        "atom_count": 2,
        "model_json_bytes": 2_048,
        "counted_input_tokens": None,
        "image_count": 1,
        "crop_count": 1,
        "pdf_count": 0,
        "image_bytes": 16_384,
    }
    values.update(overrides)
    return values


def _page_facts(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        **_identity(
            page_ref="page_002",
            page_number=2,
            scope_ref="page_scope_002",
            table_ref=None,
            assessor_stage="vlm_guided_page_intake",
        ),
        "scope": "page",
        "detection_decision": "uncertain",
        "detection_reason_codes": ["page_level_detection_requested"],
        "page_bbox": [0.0, 0.0, 612.0, 792.0],
        "candidate_bbox": None,
        "coordinate_bboxes": [],
        "provenance_verified": True,
        "crop_identity_verified": True,
        "exact_ownership_verified": False,
        "atom_count": 0,
        "model_json_bytes": 1_024,
        "counted_input_tokens": 1_500,
        "image_count": 1,
        "crop_count": 0,
        "pdf_count": 0,
        "image_bytes": 64_000,
        "proposed_region_bboxes": [],
    }
    values.update(overrides)
    return values


def _identity(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "document_ref": "document_001",
        "pdf_sha256": "a" * 64,
        "page_ref": "page_001",
        "page_number": 1,
        "scope_ref": "candidate_scope_001",
        "table_ref": "table_001",
        "evidence_checksum": "b" * 64,
        "assessor_stage": "vlm_guided_candidate_intake",
    }
    values.update(overrides)
    return values


if __name__ == "__main__":
    unittest.main()
