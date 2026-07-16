from __future__ import annotations

import copy
import unittest

from broker_reports_gate1.pdf_dual_oracle_contracts import (
    PdfDualOracleContractFactory,
)
from broker_reports_gate1.pdf_hybrid_contracts import sha256_json
from broker_reports_gate1.pdf_visual_topology import (
    PDF_VISUAL_TOPOLOGY_REGION_PROPOSAL_REVISION,
    PDF_VISUAL_TOPOLOGY_RESPONSE_SCHEMA,
    PdfVisualTopologyFactory,
)
from broker_reports_gate1.pdf_vlm_region_binding import (
    FACTORY_REQUIRED,
    FORBIDDEN,
    PDF_VLM_REGION_BINDING_RESULT_SCHEMA,
    PDF_VLM_REGION_RECONCILIATION_PLAN_SCHEMA,
    PdfVlmRegionBindingError,
    PdfVlmRegionBindingFactory,
)


class PdfVlmRegionBindingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.visual = PdfVisualTopologyFactory().create()
        self.runtime = PdfVlmRegionBindingFactory(
            visual_topology=self.visual
        ).create()
        self.projection = _projection()
        self.parent_crop = _crop_manifest(
            table_ref="page-scope",
            bbox=[0.0, 0.0, 200.0, 100.0],
            crop_id="page-crop",
            png_sha256="page-crop-sha",
            page_ref="page-1",
        )

    def test_factory_and_reconciliation_anti_drift_contract(self) -> None:
        self.assertIn("PdfVlmRegionBindingFactory.create", FACTORY_REQUIRED)
        self.assertIn("must not call a provider", FORBIDDEN)
        self.assertIn("split crossing atoms", FORBIDDEN)
        with self.assertRaisesRegex(
            PdfVlmRegionBindingError,
            "pdf_vlm_region_binding_factory_required",
        ):
            type(self.runtime)(
                self.runtime.config,
                contracts=self.runtime.contracts,
                parser_geometry=self.runtime.parser_geometry,
                visual_topology=self.runtime.visual,
                topology_assembly=self.runtime.assembler,
                materializer=self.runtime.materializer,
            )

    def test_page_region_reselects_exact_atoms_and_materializes_source_only(
        self,
    ) -> None:
        package = self.visual.build_region_proposal_package(
            proposal_scope="page_level",
            crop_manifest=self.parent_crop,
        )
        proposal = _proposal(
            package_id=package["package_id"],
            scope="page_level",
            regions=[_region("primary", [0.0, 0.0, 1.0, 1.0])],
        )
        crop = _crop_manifest(
            table_ref="table-from-page",
            bbox=[0.0, 0.0, 200.0, 100.0],
            crop_id="region-crop",
            png_sha256="region-crop-sha",
        )

        result = self.runtime.bind(
            proposal_package=package,
            proposal=self.visual.parse_region_proposal_response(proposal),
            pdf_text_layer_projection=self.projection,
            parent_source_bbox=[0.0, 0.0, 200.0, 100.0],
            region_crop_manifests={"primary": crop},
        )

        self.assertEqual(PDF_VLM_REGION_BINDING_RESULT_SCHEMA, result["schema_version"])
        self.assertEqual("accepted_physical_structure", result["runtime_terminal_status"])
        region = result["region_results"][0]
        self.assertEqual(
            ["word-1", "word-2", "word-3", "word-4"],
            region["included_word_refs"],
        )
        self.assertEqual([], region["crossing_word_refs"])
        self.assertEqual([], region["materialization"]["omitted_candidate_ids"])
        self.assertEqual([], region["materialization"]["extra_candidate_ids"])
        self.assertEqual([], region["materialization"]["duplicate_candidate_ids"])
        self.assertEqual(0, region["materialization"]["model_invented_values_total"])
        self.assertEqual(0, result["provider_calls_performed"])
        self.assertFalse(result["production_authority"])
        self.assertEqual([], self.runtime.validate_result(result))

    def test_candidate_adjusted_bbox_accounts_every_included_or_excluded_atom(
        self,
    ) -> None:
        observation = (
            PdfDualOracleContractFactory()
            .create()
            .build_parser_observation_from_word_atoms(
                document_ref="document-1",
                pdf_sha256="pdf-sha",
                page_ref="page-1",
                page_number=1,
                table_ref="table-1",
                table_bbox=[0.0, 0.0, 200.0, 100.0],
                pdf_text_layer_projection=self.projection,
            )
        )
        candidate_parent_crop = _crop_manifest(
            table_ref="table-1",
            bbox=[0.0, 0.0, 200.0, 100.0],
            crop_id="candidate-parent",
            png_sha256="candidate-parent-sha",
        )
        package = self.visual.build_region_proposal_package(
            proposal_scope="candidate_crop",
            parser_observation=observation,
            crop_manifest=candidate_parent_crop,
        )
        proposal = _proposal(
            package_id=package["package_id"],
            scope="candidate_crop",
            regions=[
                _region(
                    "left_half",
                    [0.0, 0.0, 0.5, 1.0],
                    row_boundaries=[0.0, 0.5, 1.0],
                    column_boundaries=[0.0, 1.0],
                )
            ],
        )
        crop = _crop_manifest(
            table_ref="table-1",
            bbox=[0.0, 0.0, 100.0, 100.0],
            crop_id="candidate-left",
            png_sha256="candidate-left-sha",
        )

        result = self.runtime.bind(
            proposal_package=package,
            proposal=self.visual.parse_region_proposal_response(proposal),
            pdf_text_layer_projection=self.projection,
            parent_source_bbox=[0.0, 0.0, 200.0, 100.0],
            region_crop_manifests={"left_half": crop},
        )

        region = result["region_results"][0]
        accounting = region["candidate_accounting"]
        self.assertEqual("accepted_physical_structure", region["runtime_terminal_status"])
        self.assertEqual(4, accounting["scope_candidates_total"])
        self.assertEqual(2, len(accounting["included_candidate_ids"]))
        self.assertEqual(2, len(accounting["excluded_candidate_ids"]))
        self.assertEqual([], accounting["crossing_candidate_ids"])
        self.assertTrue(accounting["every_scope_candidate_accounted"])
        self.assertEqual(["word-1", "word-3"], region["included_word_refs"])
        self.assertEqual(["word-2", "word-4"], region["excluded_word_refs"])

    def test_candidate_precision_reconciliation_remains_effective_in_binding(
        self,
    ) -> None:
        projection = copy.deepcopy(self.projection)
        original_bbox = [10.0, 60.0, 90.0, 100.0043]
        next(
            item
            for item in projection["bbox_inventory"]
            if item["bbox_ref"] == "bbox-3"
        )["bbox"] = original_bbox
        observation = (
            PdfDualOracleContractFactory()
            .create()
            .build_parser_observation_from_word_atoms(
                document_ref="document-1",
                pdf_sha256="pdf-sha",
                page_ref="page-1",
                page_number=1,
                table_ref="table-1",
                table_bbox=[0.0, 0.0, 200.0, 100.0],
                pdf_text_layer_projection=projection,
            )
        )
        parent_crop = _crop_manifest(
            table_ref="table-1",
            bbox=[0.0, 0.0, 200.0, 100.0],
            crop_id="candidate-parent-precision",
            png_sha256="candidate-parent-precision-sha",
        )
        package = self.visual.build_region_proposal_package(
            proposal_scope="candidate_crop",
            parser_observation=observation,
            crop_manifest=parent_crop,
        )
        proposal = self.visual.parse_region_proposal_response(
            _proposal(
                package_id=package["package_id"],
                scope="candidate_crop",
                regions=[_region("candidate", [0.0, 0.0, 1.0, 1.0])],
            )
        )

        plan = self.runtime.reconcile_proposal_regions(
            proposal_package=package,
            proposal=proposal,
            pdf_text_layer_projection=projection,
            parent_source_bbox=[0.0, 0.0, 200.0, 100.0],
        )
        result = self.runtime.bind(
            proposal_package=package,
            proposal=proposal,
            pdf_text_layer_projection=projection,
            parent_source_bbox=[0.0, 0.0, 200.0, 100.0],
            region_crop_manifests={"candidate": parent_crop},
        )

        geometry = next(
            item
            for item in package["source_atom_geometry_evidence"]
            if item["original_source_bbox"] == original_bbox
        )
        self.assertEqual(
            "source_precision_overshoot_reconciled",
            geometry["classification"],
        )
        self.assertEqual(original_bbox, geometry["original_source_bbox"])
        self.assertEqual(
            [10.0, 60.0, 90.0, 100.0],
            geometry["reconciled_source_bbox"],
        )
        self.assertEqual(4, plan["parent_atom_accounting"]["all_parent_atoms"])
        self.assertEqual(
            0,
            plan["parent_atom_accounting"]["parent_boundary_crossing_atoms"],
        )
        self.assertEqual(
            "accepted_physical_structure",
            result["runtime_terminal_status"],
        )
        region = result["region_results"][0]
        self.assertEqual(
            ["word-1", "word-2", "word-3", "word-4"],
            region["included_word_refs"],
        )
        self.assertEqual([], region["crossing_word_refs"])
        self.assertEqual(original_bbox, observation["candidates"][2]["bbox"])
        self.assertEqual(
            original_bbox,
            package["private_candidate_dictionary"][
                observation["candidate_order"][2]
            ]["source_bbox"],
        )
        self.assertEqual([], self.runtime.validate_result(result))
        self.assertEqual(
            [],
            self.runtime.validate_result_against_inputs(
                result,
                proposal_package=package,
                proposal=proposal,
                pdf_text_layer_projection=projection,
                parent_source_bbox=[0.0, 0.0, 200.0, 100.0],
                region_crop_manifests={"candidate": parent_crop},
            ),
        )

    def test_region_boundary_crossing_atoms_expand_to_exact_source_edges(
        self,
    ) -> None:
        package = self.visual.build_region_proposal_package(
            proposal_scope="page_level",
            crop_manifest=self.parent_crop,
        )
        proposal = _proposal(
            package_id=package["package_id"],
            scope="page_level",
            regions=[
                _region(
                    "cut_word",
                    [0.0, 0.0, 0.25, 1.0],
                    row_boundaries=[0.0, 1.0],
                    column_boundaries=[0.0, 1.0],
                )
            ],
        )
        parsed = self.visual.parse_region_proposal_response(proposal)
        plan = self.runtime.reconcile_proposal_regions(
            proposal_package=package,
            proposal=parsed,
            pdf_text_layer_projection=self.projection,
            parent_source_bbox=[0.0, 0.0, 200.0, 100.0],
        )
        planned = plan["regions"][0]
        evidence = planned["bbox_reconciliation"]
        self.assertEqual(
            PDF_VLM_REGION_RECONCILIATION_PLAN_SCHEMA,
            plan["schema_version"],
        )
        self.assertEqual([0.0, 0.0, 50.0, 100.0], planned["original_source_bbox"])
        self.assertEqual([0.0, 0.0, 90.0, 100.0], planned["reconciled_source_bbox"])
        self.assertEqual(
            ["word-1", "word-3"], evidence["crossing_word_refs_before"]
        )
        self.assertEqual([], evidence["crossing_word_refs_after"])
        self.assertEqual(0, evidence["crossing_atoms"])
        self.assertEqual(
            evidence["all_parent_atoms"],
            evidence["included_atoms"]
            + evidence["excluded_atoms"]
            + evidence["crossing_atoms"],
        )
        self.assertEqual(
            [
                {
                    "iteration": 1,
                    "edge": "right",
                    "from_coordinate": 50.0,
                    "to_coordinate": 90.0,
                    "reason_code": "complete_crossing_source_atom_boundary",
                    "word_refs": ["word-1", "word-3"],
                }
            ],
            evidence["adjustments"],
        )
        self.assertEqual([], self.runtime.validate_reconciliation_plan(plan))
        crop = _crop_manifest(
            table_ref="cut-table",
            bbox=planned["reconciled_source_bbox"],
            crop_id="cut-crop",
            png_sha256="cut-crop-sha",
        )

        result = self.runtime.bind(
            proposal_package=package,
            proposal=parsed,
            pdf_text_layer_projection=self.projection,
            parent_source_bbox=[0.0, 0.0, 200.0, 100.0],
            region_crop_manifests={"cut_word": crop},
        )

        region = result["region_results"][0]
        self.assertEqual([0.0, 0.0, 50.0, 100.0], region["original_source_bbox"])
        self.assertEqual([0.0, 0.0, 90.0, 100.0], region["source_bbox"])
        self.assertEqual([], region["crossing_word_refs"])
        self.assertNotIn(
            "pdf_vlm_region_binding_atom_crosses_region_boundary",
            region["reason_codes"],
        )
        self.assertEqual(evidence, region["bbox_reconciliation"])
        self.assertEqual([], self.runtime.validate_result(result))

    def test_reconciliation_is_a_least_fixed_point_not_one_pass_padding(
        self,
    ) -> None:
        projection = copy.deepcopy(self.projection)
        projection["bbox_inventory"].append(
            {"bbox_ref": "bbox-bridge", "bbox": [89.0, 20.0, 120.0, 30.0]}
        )
        projection["word_inventory"].append(
            {
                "parser_ordinal": 5,
                "word_ref": "word-bridge",
                "page_ref": "page-1",
                "bbox_ref": "bbox-bridge",
                "text": "bridge-private",
                "geometry_reading_order": 5,
                "text_checksum_ref": "checksum-bridge",
                "source_value_ref": "source-bridge",
            }
        )
        package = self.visual.build_region_proposal_package(
            proposal_scope="page_level",
            crop_manifest=self.parent_crop,
        )
        proposal = self.visual.parse_region_proposal_response(
            _proposal(
                package_id=package["package_id"],
                scope="page_level",
                regions=[_region("closure", [0.0, 0.0, 0.25, 1.0])],
            )
        )

        plan = self.runtime.reconcile_proposal_regions(
            proposal_package=package,
            proposal=proposal,
            pdf_text_layer_projection=projection,
            parent_source_bbox=[0.0, 0.0, 200.0, 100.0],
        )

        evidence = plan["regions"][0]["bbox_reconciliation"]
        self.assertEqual([0.0, 0.0, 190.0, 100.0], evidence["reconciled_source_bbox"])
        self.assertEqual(
            [(1, 50.0, 90.0), (2, 90.0, 120.0), (3, 120.0, 190.0)],
            [
                (
                    item["iteration"],
                    item["from_coordinate"],
                    item["to_coordinate"],
                )
                for item in evidence["adjustments"]
                if item["edge"] == "right"
            ],
        )
        self.assertEqual([], evidence["crossing_word_refs_after"])

    def test_candidate_parent_crossing_atom_fails_closed(self) -> None:
        projection = copy.deepcopy(self.projection)
        projection["bbox_inventory"].append(
            {"bbox_ref": "bbox-parent-crossing", "bbox": [195.0, 20.0, 205.0, 30.0]}
        )
        projection["word_inventory"].append(
            {
                "parser_ordinal": 5,
                "word_ref": "word-parent-crossing",
                "page_ref": "page-1",
                "bbox_ref": "bbox-parent-crossing",
                "text": "outside-parent-private",
                "geometry_reading_order": 5,
                "text_checksum_ref": "checksum-parent-crossing",
                "source_value_ref": "source-parent-crossing",
            }
        )
        observation = (
            PdfDualOracleContractFactory()
            .create()
            .build_parser_observation_from_word_atoms(
                document_ref="document-1",
                pdf_sha256="pdf-sha",
                page_ref="page-1",
                page_number=1,
                table_ref="table-1",
                table_bbox=[0.0, 0.0, 200.0, 100.0],
                pdf_text_layer_projection=projection,
            )
        )
        package = self.visual.build_region_proposal_package(
            proposal_scope="candidate_crop",
            parser_observation=observation,
            crop_manifest=_crop_manifest(
                table_ref="table-1",
                bbox=[0.0, 0.0, 200.0, 100.0],
                crop_id="candidate-parent-crossing",
                png_sha256="candidate-parent-crossing-sha",
            ),
        )
        proposal = self.visual.parse_region_proposal_response(
            _proposal(
                package_id=package["package_id"],
                scope="candidate_crop",
                regions=[_region("candidate", [0.0, 0.0, 1.0, 1.0])],
            )
        )

        with self.assertRaisesRegex(
            PdfVlmRegionBindingError,
            "pdf_vlm_region_binding_parent_atom_crossing",
        ):
            self.runtime.reconcile_proposal_regions(
                proposal_package=package,
                proposal=proposal,
                pdf_text_layer_projection=projection,
                parent_source_bbox=[0.0, 0.0, 200.0, 100.0],
            )

    def test_arbitrary_crop_expansion_is_not_accepted_as_reconciliation(
        self,
    ) -> None:
        package = self.visual.build_region_proposal_package(
            proposal_scope="page_level",
            crop_manifest=self.parent_crop,
        )
        proposal = self.visual.parse_region_proposal_response(
            _proposal(
                package_id=package["package_id"],
                scope="page_level",
                regions=[_region("cut_word", [0.0, 0.0, 0.25, 1.0])],
            )
        )
        arbitrary_crop = _crop_manifest(
            table_ref="cut-table",
            bbox=[0.0, 0.0, 100.0, 100.0],
            crop_id="arbitrary-crop",
            png_sha256="arbitrary-crop-sha",
        )

        result = self.runtime.bind(
            proposal_package=package,
            proposal=proposal,
            pdf_text_layer_projection=self.projection,
            parent_source_bbox=[0.0, 0.0, 200.0, 100.0],
            region_crop_manifests={"cut_word": arbitrary_crop},
        )

        region = result["region_results"][0]
        self.assertEqual("validation_blocked", region["runtime_terminal_status"])
        self.assertIn(
            "pdf_vlm_region_binding_crop_geometry_mismatch",
            region["reason_codes"],
        )
        self.assertEqual([0.0, 0.0, 90.0, 100.0], region["source_bbox"])

    def test_no_word_region_preserves_exact_zero_intersection_evidence(
        self,
    ) -> None:
        package = self.visual.build_region_proposal_package(
            proposal_scope="page_level",
            crop_manifest=self.parent_crop,
        )
        proposal = self.visual.parse_region_proposal_response(
            _proposal(
                package_id=package["package_id"],
                scope="page_level",
                regions=[_region("whitespace", [0.45, 0.45, 0.55, 0.55])],
            )
        )
        plan = self.runtime.reconcile_proposal_regions(
            proposal_package=package,
            proposal=proposal,
            pdf_text_layer_projection=self.projection,
            parent_source_bbox=[0.0, 0.0, 200.0, 100.0],
        )
        planned = plan["regions"][0]
        crop = _crop_manifest(
            table_ref="whitespace-table",
            bbox=planned["reconciled_source_bbox"],
            crop_id="whitespace-crop",
            png_sha256="whitespace-crop-sha",
        )

        result = self.runtime.bind(
            proposal_package=package,
            proposal=proposal,
            pdf_text_layer_projection=self.projection,
            parent_source_bbox=[0.0, 0.0, 200.0, 100.0],
            region_crop_manifests={"whitespace": crop},
        )

        region = result["region_results"][0]
        evidence = region["bbox_reconciliation"]
        self.assertEqual(0, evidence["included_atoms"])
        self.assertEqual(4, evidence["excluded_atoms"])
        self.assertEqual(0, evidence["crossing_atoms"])
        self.assertEqual(4, evidence["all_parent_atoms"])
        self.assertEqual([], evidence["adjustments"])
        self.assertIn(
            "pdf_vlm_region_binding_region_has_no_word_atoms",
            region["reason_codes"],
        )

    def test_multiple_hypotheses_remain_ambiguous_and_never_materialize(self) -> None:
        package = self.visual.build_region_proposal_package(
            proposal_scope="page_level",
            crop_manifest=self.parent_crop,
        )
        region = _region("ambiguous", [0.0, 0.0, 1.0, 1.0])
        alternative = copy.deepcopy(region["hypotheses"][0])
        alternative["hypothesis_key"] = "alternative"
        alternative["column_boundaries"] = [0.0, 0.55, 1.0]
        region["hypotheses"].append(alternative)
        proposal = _proposal(
            package_id=package["package_id"],
            scope="page_level",
            regions=[region],
        )
        crop = _crop_manifest(
            table_ref="ambiguous-table",
            bbox=[0.0, 0.0, 200.0, 100.0],
            crop_id="ambiguous-crop",
            png_sha256="ambiguous-crop-sha",
        )

        result = self.runtime.bind(
            proposal_package=package,
            proposal=self.visual.parse_region_proposal_response(proposal),
            pdf_text_layer_projection=self.projection,
            parent_source_bbox=[0.0, 0.0, 200.0, 100.0],
            region_crop_manifests={"ambiguous": crop},
        )

        bound = result["region_results"][0]
        self.assertEqual("proposal_ambiguous", bound["runtime_terminal_status"])
        self.assertEqual("ambiguous", bound["topology_response"]["decision"])
        self.assertEqual(2, len(bound["topology_response"]["hypotheses"]))
        self.assertIsNone(bound["accepted_binding"])
        self.assertIsNone(bound["materialization"])
        self.assertIn(
            "pdf_vlm_region_binding_proposal_ambiguous",
            bound["reason_codes"],
        )

    def test_crop_provenance_or_geometry_mismatch_is_checksummed_and_blocked(
        self,
    ) -> None:
        package = self.visual.build_region_proposal_package(
            proposal_scope="page_level",
            crop_manifest=self.parent_crop,
        )
        proposal = _proposal(
            package_id=package["package_id"],
            scope="page_level",
            regions=[_region("mismatch", [0.0, 0.0, 1.0, 1.0])],
        )
        crop = _crop_manifest(
            table_ref="mismatch-table",
            bbox=[0.0, 0.0, 199.0, 100.0],
            crop_id="mismatch-crop",
            png_sha256="mismatch-crop-sha",
        )

        result = self.runtime.bind(
            proposal_package=package,
            proposal=self.visual.parse_region_proposal_response(proposal),
            pdf_text_layer_projection=self.projection,
            parent_source_bbox=[0.0, 0.0, 200.0, 100.0],
            region_crop_manifests={"mismatch": crop},
        )

        region = result["region_results"][0]
        self.assertEqual("validation_blocked", region["runtime_terminal_status"])
        self.assertIn(
            "pdf_vlm_region_binding_crop_geometry_mismatch",
            region["reason_codes"],
        )
        self.assertIsNone(region["parser_observation"])
        self.assertIsNone(region["materialization"])
        self.assertEqual(sha256_json({k: v for k, v in result.items() if k != "result_checksum"}), result["result_checksum"])
        self.assertEqual([], self.runtime.validate_result(result))

    def test_resealed_top_scope_identity_drift_is_rejected(self) -> None:
        result = self._accepted_page_result()
        mutations = (
            ("document_ref", "document-resealed"),
            ("pdf_sha256", "pdf-resealed"),
            ("page_ref", "page-resealed"),
            ("page_number", 2),
            ("parent_source_bbox", [0.0, 0.0, 201.0, 100.0]),
        )

        for key, replacement in mutations:
            with self.subTest(key=key):
                tampered = copy.deepcopy(result)
                tampered[key] = replacement
                _reseal(tampered)

                self.assertIn(
                    "pdf_vlm_region_binding_scope_identity_mismatch",
                    self.runtime.validate_result(tampered),
                )

    def test_resealed_source_accounting_drift_is_rejected(self) -> None:
        result = self._accepted_page_result()
        tampered = copy.deepcopy(result)
        tampered["source_accounting"]["parent_word_refs_total"] += 1
        _reseal(tampered)

        self.assertIn(
            "pdf_vlm_region_binding_source_accounting_invalid",
            self.runtime.validate_result(tampered),
        )

    def test_resealed_region_partition_universe_drift_is_rejected(self) -> None:
        result = self._accepted_page_result()
        tampered = copy.deepcopy(result)
        tampered["region_results"][0]["excluded_word_refs"] = ["word-forged"]
        _reseal(tampered)

        errors = self.runtime.validate_result(tampered)
        self.assertIn(
            "pdf_vlm_region_binding_source_accounting_invalid",
            errors,
        )

    def test_anchored_validation_rejects_resealed_input_digest_drift(
        self,
    ) -> None:
        result, package, proposal, manifests = self._accepted_page_evidence()
        mutations = (
            (
                "proposal_package_id",
                "package-resealed",
                "pdf_vlm_region_binding_proposal_binding_mismatch",
            ),
            (
                "proposal_checksum",
                "proposal-resealed",
                "pdf_vlm_region_binding_proposal_binding_mismatch",
            ),
            (
                "projection_checksum",
                "projection-resealed",
                "pdf_vlm_region_binding_projection_binding_mismatch",
            ),
            (
                "proposal_scope",
                "candidate_crop",
                "pdf_vlm_region_binding_proposal_binding_mismatch",
            ),
        )

        for key, replacement, expected_error in mutations:
            with self.subTest(key=key):
                tampered = copy.deepcopy(result)
                tampered[key] = replacement
                _reseal(tampered)

                self.assertIn(
                    expected_error,
                    self.runtime.validate_result_against_inputs(
                        tampered,
                        proposal_package=package,
                        proposal=proposal,
                        pdf_text_layer_projection=self.projection,
                        parent_source_bbox=[0.0, 0.0, 200.0, 100.0],
                        region_crop_manifests=manifests,
                    ),
                )

    def test_anchored_validation_recomputes_absent_parent_accounting(
        self,
    ) -> None:
        package = self.visual.build_region_proposal_package(
            proposal_scope="page_level",
            crop_manifest=self.parent_crop,
        )
        proposal = _proposal(
            package_id=package["package_id"],
            scope="page_level",
            regions=[],
        )
        proposal["table_presence"] = "absent"
        proposal = self.visual.parse_region_proposal_response(proposal)
        result = self.runtime.bind(
            proposal_package=package,
            proposal=proposal,
            pdf_text_layer_projection=self.projection,
            parent_source_bbox=[0.0, 0.0, 200.0, 100.0],
            region_crop_manifests={},
        )
        tampered = copy.deepcopy(result)
        tampered["source_accounting"]["parent_word_refs_total"] += 1
        _reseal(tampered)

        self.assertIn(
            "pdf_vlm_region_binding_source_accounting_invalid",
            self.runtime.validate_result_against_inputs(
                tampered,
                proposal_package=package,
                proposal=proposal,
                pdf_text_layer_projection=self.projection,
                parent_source_bbox=[0.0, 0.0, 200.0, 100.0],
                region_crop_manifests={},
            ),
        )

    def test_anchored_validation_rejects_resealed_partition_reassignment(
        self,
    ) -> None:
        observation = (
            PdfDualOracleContractFactory()
            .create()
            .build_parser_observation_from_word_atoms(
                document_ref="document-1",
                pdf_sha256="pdf-sha",
                page_ref="page-1",
                page_number=1,
                table_ref="table-1",
                table_bbox=[0.0, 0.0, 200.0, 100.0],
                pdf_text_layer_projection=self.projection,
            )
        )
        package = self.visual.build_region_proposal_package(
            proposal_scope="candidate_crop",
            parser_observation=observation,
            crop_manifest=_crop_manifest(
                table_ref="table-1",
                bbox=[0.0, 0.0, 200.0, 100.0],
                crop_id="candidate-parent",
                png_sha256="candidate-parent-sha",
            ),
        )
        proposal = self.visual.parse_region_proposal_response(
            _proposal(
                package_id=package["package_id"],
                scope="candidate_crop",
                regions=[
                    _region(
                        "left_half",
                        [0.0, 0.0, 0.5, 1.0],
                        row_boundaries=[0.0, 0.5, 1.0],
                        column_boundaries=[0.0, 1.0],
                    )
                ],
            )
        )
        manifests = {
            "left_half": _crop_manifest(
                table_ref="table-1",
                bbox=[0.0, 0.0, 100.0, 100.0],
                crop_id="candidate-left",
                png_sha256="candidate-left-sha",
            )
        }
        # Keep this non-accepted so no materialization duplicates the partition;
        # the attack can then reseal every internal/outer checksum while
        # preserving the same counts and universe.
        manifests["left_half"]["manifest_hash"] = "invalid-manifest-hash"
        result = self.runtime.bind(
            proposal_package=package,
            proposal=proposal,
            pdf_text_layer_projection=self.projection,
            parent_source_bbox=[0.0, 0.0, 200.0, 100.0],
            region_crop_manifests=manifests,
        )
        tampered = copy.deepcopy(result)
        region = tampered["region_results"][0]
        candidate_by_word = {
            record["word_refs"][0]: candidate_id
            for candidate_id, record in package[
                "private_candidate_dictionary"
            ].items()
        }
        included_candidate = candidate_by_word["word-1"]
        excluded_candidate = candidate_by_word["word-2"]
        region["included_word_refs"] = ["word-2", "word-3"]
        region["excluded_word_refs"] = ["word-1", "word-4"]
        candidate = region["candidate_accounting"]
        candidate["included_candidate_ids"] = sorted(
            excluded_candidate if item == included_candidate else item
            for item in candidate["included_candidate_ids"]
        )
        candidate["excluded_candidate_ids"] = sorted(
            included_candidate if item == excluded_candidate else item
            for item in candidate["excluded_candidate_ids"]
        )
        _reseal(tampered)

        self.assertEqual("validation_blocked", region["runtime_terminal_status"])
        self.assertIn(
            "pdf_vlm_region_binding_reconciliation_accounting_invalid",
            self.runtime.validate_result(tampered),
        )
        self.assertIn(
            "pdf_vlm_region_binding_partition_anchor_invalid",
            self.runtime.validate_result_against_inputs(
                tampered,
                proposal_package=package,
                proposal=proposal,
                pdf_text_layer_projection=self.projection,
                parent_source_bbox=[0.0, 0.0, 200.0, 100.0],
                region_crop_manifests=manifests,
            ),
        )

    def test_page_scope_rejects_same_page_word_outside_parent_bbox(self) -> None:
        projection = copy.deepcopy(self.projection)
        projection["bbox_inventory"].append(
            {"bbox_ref": "bbox-outside", "bbox": [210.0, 10.0, 220.0, 20.0]}
        )
        projection["word_inventory"].append(
            {
                "parser_ordinal": 5,
                "word_ref": "word-outside",
                "page_ref": "page-1",
                "bbox_ref": "bbox-outside",
                "text": "outside-private",
                "geometry_reading_order": 5,
                "text_checksum_ref": "checksum-outside",
                "source_value_ref": "source-outside",
            }
        )
        package = self.visual.build_region_proposal_package(
            proposal_scope="page_level",
            crop_manifest=self.parent_crop,
        )
        proposal = _proposal(
            package_id=package["package_id"],
            scope="page_level",
            regions=[_region("primary", [0.0, 0.0, 1.0, 1.0])],
        )
        crop = _crop_manifest(
            table_ref="table-from-page",
            bbox=[0.0, 0.0, 200.0, 100.0],
            crop_id="region-crop",
            png_sha256="region-crop-sha",
        )

        with self.assertRaises(PdfVlmRegionBindingError) as raised:
            self.runtime.bind(
                proposal_package=package,
                proposal=self.visual.parse_region_proposal_response(proposal),
                pdf_text_layer_projection=projection,
                parent_source_bbox=[0.0, 0.0, 200.0, 100.0],
                region_crop_manifests={"primary": crop},
            )

        self.assertEqual(
            "pdf_vlm_region_binding_parent_atom_outside_scope",
            raised.exception.code,
        )

    def _accepted_page_result(self) -> dict:
        result, _, _, _ = self._accepted_page_evidence()
        return result

    def _accepted_page_evidence(self) -> tuple[dict, dict, dict, dict]:
        package = self.visual.build_region_proposal_package(
            proposal_scope="page_level",
            crop_manifest=self.parent_crop,
        )
        proposal = _proposal(
            package_id=package["package_id"],
            scope="page_level",
            regions=[_region("primary", [0.0, 0.0, 1.0, 1.0])],
        )
        crop = _crop_manifest(
            table_ref="table-from-page",
            bbox=[0.0, 0.0, 200.0, 100.0],
            crop_id="region-crop",
            png_sha256="region-crop-sha",
        )
        proposal = self.visual.parse_region_proposal_response(proposal)
        manifests = {"primary": crop}
        result = self.runtime.bind(
            proposal_package=package,
            proposal=proposal,
            pdf_text_layer_projection=self.projection,
            parent_source_bbox=[0.0, 0.0, 200.0, 100.0],
            region_crop_manifests=manifests,
        )
        return result, package, proposal, manifests


def _proposal(*, package_id: str, scope: str, regions: list[dict]) -> dict:
    return {
        "schema_version": PDF_VISUAL_TOPOLOGY_RESPONSE_SCHEMA,
        "contract_revision": PDF_VISUAL_TOPOLOGY_REGION_PROPOSAL_REVISION,
        "package_id": package_id,
        "proposal_scope": scope,
        "table_presence": "present",
        "alternatives_complete": True,
        "regions": regions,
        "uncertainty_codes": [],
    }


def _reseal(result: dict) -> None:
    result["result_checksum"] = sha256_json(
        {key: value for key, value in result.items() if key != "result_checksum"}
    )


def _region(
    key: str,
    bbox: list[float],
    *,
    row_boundaries: list[float] | None = None,
    column_boundaries: list[float] | None = None,
) -> dict:
    return {
        "region_key": key,
        "bbox": bbox,
        "border_evidence": "ruled",
        "density": "mixed",
        "continuation_likelihood": "unlikely",
        "hypotheses": [
            {
                "hypothesis_key": "primary",
                "row_boundaries": row_boundaries or [0.0, 0.5, 1.0],
                "column_boundaries": column_boundaries or [0.0, 0.5, 1.0],
                "header_row_count": 1,
                "spans": [],
                "header_hierarchy": [],
                "continuation_required": False,
                "uncertainty_codes": [],
            }
        ],
        "uncertainty_codes": [],
    }


def _projection() -> dict:
    values = (
        ("alpha-private", [10.0, 10.0, 90.0, 40.0]),
        ("beta-private", [110.0, 10.0, 190.0, 40.0]),
        ("gamma-private", [10.0, 60.0, 90.0, 90.0]),
        ("delta-private", [110.0, 60.0, 190.0, 90.0]),
    )
    bboxes: list[dict] = []
    words: list[dict] = []
    for ordinal, (text, bbox) in enumerate(values, start=1):
        bbox_ref = f"bbox-{ordinal}"
        bboxes.append({"bbox_ref": bbox_ref, "bbox": bbox})
        words.append(
            {
                "parser_ordinal": ordinal,
                "word_ref": f"word-{ordinal}",
                "page_ref": "page-1",
                "bbox_ref": bbox_ref,
                "text": text,
                "geometry_reading_order": ordinal,
                "text_checksum_ref": f"checksum-{ordinal}",
                "source_value_ref": f"source-{ordinal}",
            }
        )
    vectors: list[dict] = []
    for ordinal, (label, bbox) in enumerate(
        (
            ("left", [0.0, 0.0, 0.0, 100.0]),
            ("middle", [100.0, 0.0, 100.0, 100.0]),
            ("right", [200.0, 0.0, 200.0, 100.0]),
            ("top", [0.0, 0.0, 200.0, 0.0]),
            ("middle-row", [0.0, 50.0, 200.0, 50.0]),
            ("bottom", [0.0, 100.0, 200.0, 100.0]),
        ),
        start=1,
    ):
        bbox_ref = f"vector-bbox-{ordinal}"
        bboxes.append({"bbox_ref": bbox_ref, "bbox": bbox})
        vectors.append(
            {
                "parser_ordinal": ordinal,
                "object_ref": f"vector-{label}",
                "page_ref": "page-1",
                "bbox_ref": bbox_ref,
                "linewidth": 0.5,
            }
        )
    return {
        "bbox_inventory": bboxes,
        "word_inventory": words,
        "line_inventory": [],
        "vector_line_inventory": vectors,
        "rect_inventory": [],
    }


def _crop_manifest(
    *,
    table_ref: str,
    bbox: list[float],
    crop_id: str,
    png_sha256: str,
    page_ref: str | None = None,
) -> dict:
    width = max(1, int((bbox[2] - bbox[0]) * 2))
    height = max(1, int((bbox[3] - bbox[1]) * 2))
    value = {
        "schema_version": "broker_reports_pdf_table_crop_v1",
        "policy_version": "pdf_table_raster_policy_v1",
        "crop_id": crop_id,
        "document_ref": "document-1",
        "pdf_sha256": "pdf-sha",
        "page_number": 1,
        "table_ref": table_ref,
        "declared_table_bbox": bbox,
        "rendered_bbox": bbox,
        "source_coordinate_space": "pdf_top_left_points",
        "pixel_coordinate_space": "crop_top_left_pixels",
        "source_to_pixel_transform": {
            "scale_x": 2.0,
            "scale_y": 2.0,
            "translate_source_x": -bbox[0],
            "translate_source_y": -bbox[1],
        },
        "renderer": "pymupdf",
        "renderer_version": "1.26.5",
        "page_rotation": 0,
        "applied_rotation": 0,
        "padding_points": 0.0,
        "dpi": 150,
        "dpi_revision_reason": "primary_150_dpi",
        "width": width,
        "height": height,
        "pixels": width * height,
        "png_bytes": 100,
        "png_sha256": png_sha256,
        "lossless": True,
        "silent_resize_performed": False,
    }
    if page_ref is not None:
        value["page_ref"] = page_ref
    value["manifest_hash"] = sha256_json(value)
    return value


if __name__ == "__main__":
    unittest.main()
