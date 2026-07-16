from __future__ import annotations

import copy
import json
import runpy
import unittest
from pathlib import Path

from broker_reports_gate1.contracts import stable_digest
from broker_reports_gate1.pdf_dual_oracle_consensus import (
    PdfDualOracleConsensusFactory,
)
from broker_reports_gate1.pdf_dual_oracle_contracts import (
    PdfDualOracleContractFactory,
)
from broker_reports_gate1.pdf_hybrid_contracts import sha256_json
from broker_reports_gate1.pdf_hybrid_materialization import (
    PdfHybridMaterializationFactory,
)
from broker_reports_gate1.pdf_parser_geometry import (
    PdfParserGeometryConfig,
    PdfParserGeometryError,
    PdfParserGeometryFactory,
    PdfParserGeometryRuntime,
)
from broker_reports_gate1.pdf_topology_assembly import (
    PdfTopologyAssemblyConfig,
    PdfTopologyAssemblyError,
    PdfTopologyAssemblyFactory,
    PdfTopologyAssemblyRuntime,
)
from broker_reports_gate1.pdf_visual_topology import (
    PDF_VISUAL_TOPOLOGY_POLICY_VERSION,
    PDF_VISUAL_TOPOLOGY_RESPONSE_SCHEMA,
    PDF_VISUAL_TOPOLOGY_SOURCE_ATOM_TOLERANCE_POINTS,
    PdfVisualTopologyConfig,
    PdfVisualTopologyError,
    PdfVisualTopologyFactory,
)


class PdfVisualTopologyPackageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contracts = PdfDualOracleContractFactory().create()
        self.visual = PdfVisualTopologyFactory().create()
        self.observation = _observation(self.contracts)
        self.crop = _crop_manifest()

    def test_model_view_contains_only_anonymous_geometry_not_legacy_grid_or_values(
        self,
    ) -> None:
        package = self.visual.build_package(
            parser_observation=self.observation,
            crop_manifest=self.crop,
        )

        model_view = package["model_facing"]
        rendered = repr(model_view)
        self.assertNotIn("alpha-private", rendered)
        self.assertNotIn("delta-private", rendered)
        self.assertNotIn("source-1", rendered)
        self.assertNotIn("wa_", rendered)
        self.assertNotIn("row_count", rendered)
        self.assertNotIn("column_count", rendered)
        self.assertNotIn("cell_inventory", rendered)
        self.assertNotIn("shape_hints", model_view)
        self.assertFalse(model_view["rules"]["parser_header_depth_available"])
        self.assertFalse(
            model_view["rules"]["boundary_evidence_requires_drawn_grid"]
        )
        self.assertFalse(
            model_view["rules"]["borderless_table_implies_unsupported"]
        )
        self.assertNotIn(
            "row_boundary_requires_visible_horizontal_separator",
            model_view["rules"],
        )
        self.assertNotIn(
            "column_boundary_requires_visible_vertical_separator_in_unmerged_regions",
            model_view["rules"],
        )
        self.assertFalse(model_view["rules"]["single_cell_spans_allowed"])
        self.assertTrue(
            model_view["rules"][
                "boundary_arrays_start_at_zero_and_end_at_one"
            ]
        )
        self.assertTrue(
            model_view["rules"]["unsupported_requires_uncertainty_code"]
        )
        self.assertIn("starts with exactly 0.0", model_view["task"])
        self.assertIn("stable whitespace gutters", model_view["task"])
        self.assertIn("repeated horizontal or vertical alignment", model_view["task"])
        self.assertIn("consistent atom bands", model_view["task"])
        self.assertIn("visible separators when present", model_view["task"])
        self.assertIn("absence of drawn grid lines", model_view["task"])
        self.assertIn("at least one precise snake_case uncertainty code", model_view["task"])
        output_schema = package["output_schema"]
        hypothesis_schema = output_schema["properties"]["hypotheses"]["items"]
        self.assertIn(
            "first item must be exactly 0.0",
            hypothesis_schema["properties"]["row_boundaries"]["description"],
        )
        self.assertIn(
            "first item must be exactly 0.0",
            hypothesis_schema["properties"]["column_boundaries"]["description"],
        )
        self.assertTrue(
            all(set(item) == {"atom_id", "bbox", "order"} for item in model_view["atoms"])
        )
        self.assertFalse(package["legacy_grid_consumed"])
        self.assertFalse(package["source_values_exposed_to_model_view"])
        self.assertLessEqual(
            package["component_accounting"]["static_input_token_estimate"],
            1_482,
        )
        self.assertEqual(
            ["a0001", "a0002", "a0003", "a0004"],
            [item["atom_id"] for item in model_view["atoms"]],
        )
        self.assertEqual(
            [],
            self.visual.validate_package(
                parser_observation=self.observation,
                package=package,
            ),
        )

    def test_policy_v6_repairs_visual_contract_without_weakening_budgets(
        self,
    ) -> None:
        config = PdfVisualTopologyConfig()

        self.assertEqual("pdf_visual_topology_policy_v6", config.policy_version)
        self.assertEqual(PDF_VISUAL_TOPOLOGY_POLICY_VERSION, config.policy_version)
        self.assertEqual(1_000, config.maximum_atoms)
        self.assertEqual(48 * 1024, config.maximum_model_json_bytes)
        self.assertEqual(18_000, config.maximum_static_input_tokens)
        self.assertEqual(20_000, config.maximum_counted_input_tokens)
        self.assertEqual(
            0.75,
            PDF_VISUAL_TOPOLOGY_SOURCE_ATOM_TOLERANCE_POINTS,
        )
        with self.assertRaisesRegex(
            PdfVisualTopologyError,
            "pdf_visual_topology_policy_invalid",
        ):
            PdfVisualTopologyFactory(
                PdfVisualTopologyConfig(
                    policy_version="pdf_visual_topology_policy_v4"
                )
            ).create()

    def test_source_atom_bottom_precision_overshoot_is_reconciled_and_audited(
        self,
    ) -> None:
        projection = _projection()
        projection["bbox_inventory"][2]["bbox"] = [
            10.0,
            60.0,
            90.0,
            100.0043,
        ]
        observation = _observation(self.contracts, projection=projection)

        package = self.visual.build_region_proposal_package(
            proposal_scope="candidate_crop",
            parser_observation=observation,
            crop_manifest=self.crop,
        )

        atom = package["model_facing"]["atoms"][2]
        candidate_id = package["neutral_atom_to_candidate_id"]["a0003"]
        source = package["private_candidate_dictionary"][candidate_id]
        geometry = package["source_atom_geometry_evidence"][2]
        unsigned_geometry = dict(geometry)
        stored_checksum = unsigned_geometry.pop("evidence_checksum")
        self.assertEqual(
            {
                "atom_id": "a0003",
                "candidate_id": candidate_id,
                "classification": "source_precision_overshoot_reconciled",
                "original_source_bbox": [10.0, 60.0, 90.0, 100.0043],
                "reconciled_source_bbox": [10.0, 60.0, 90.0, 100.0],
                "normalized_bbox": [0.05, 0.6, 0.45, 1.0],
                "selected_source_region_bbox": [0.0, 0.0, 200.0, 100.0],
                "maximum_overshoot_points": 0.75,
                "adjustments": [
                    {
                        "edge": "bottom",
                        "from_coordinate": 100.0043,
                        "to_coordinate": 100.0,
                        "overshoot_points": 0.0043,
                        "reason_code": (
                            "pdf_visual_topology_source_atom_precision_"
                            "overshoot_reconciled"
                        ),
                    }
                ],
            },
            unsigned_geometry,
        )
        self.assertEqual(sha256_json(unsigned_geometry), stored_checksum)
        self.assertEqual([0.05, 0.6, 0.45, 1.0], atom["bbox"])
        self.assertNotIn("source_geometry", source)
        self.assertEqual(
            sha256_json(package["source_atom_geometry_evidence"]),
            package["source_atom_geometry_evidence_hash"],
        )
        contained_geometry = package["source_atom_geometry_evidence"][0]
        self.assertEqual(
            "within_selected_source_region",
            contained_geometry["classification"],
        )
        self.assertEqual([], contained_geometry["adjustments"])
        self.assertEqual(
            [],
            self.visual.validate_region_proposal_package(package),
        )

    def test_source_atom_geometry_evidence_is_recomputed_during_validation(
        self,
    ) -> None:
        projection = _projection()
        projection["bbox_inventory"][2]["bbox"] = [
            10.0,
            60.0,
            90.0,
            100.0043,
        ]
        observation = _observation(self.contracts, projection=projection)
        package = self.visual.build_region_proposal_package(
            proposal_scope="candidate_crop",
            parser_observation=observation,
            crop_manifest=self.crop,
        )
        tampered = copy.deepcopy(package)
        geometry = tampered["source_atom_geometry_evidence"][2]
        geometry["classification"] = "within_selected_source_region"
        unsigned_geometry = dict(geometry)
        unsigned_geometry.pop("evidence_checksum")
        geometry["evidence_checksum"] = sha256_json(unsigned_geometry)
        tampered["source_atom_geometry_evidence_hash"] = sha256_json(
            tampered["source_atom_geometry_evidence"]
        )
        _reseal_region_package(tampered)

        self.assertEqual(
            ["pdf_visual_topology_region_atom_geometry_evidence_invalid"],
            self.visual.validate_region_proposal_package(tampered),
        )

    def test_genuinely_invalid_source_bbox_is_classified_during_validation(
        self,
    ) -> None:
        package = self.visual.build_region_proposal_package(
            proposal_scope="candidate_crop",
            parser_observation=self.observation,
            crop_manifest=self.crop,
        )
        tampered = copy.deepcopy(package)
        candidate_id = tampered["neutral_atom_to_candidate_id"]["a0003"]
        tampered["private_candidate_dictionary"][candidate_id]["source_bbox"] = [
            10.0,
            60.0,
            10.0,
            90.0,
        ]
        tampered["candidate_dictionary_hash"] = sha256_json(
            tampered["private_candidate_dictionary"]
        )
        _reseal_region_package(tampered)

        self.assertEqual(
            ["pdf_visual_topology_atom_bbox_invalid"],
            self.visual.validate_region_proposal_package(tampered),
        )

    def test_atom_outside_selected_source_region_is_not_precision_reconciled(
        self,
    ) -> None:
        projection = _projection()
        projection["bbox_inventory"][2]["bbox"] = [
            199.8,
            60.0,
            200.4,
            90.0,
        ]
        observation = _observation(self.contracts, projection=projection)

        with self.assertRaisesRegex(
            PdfVisualTopologyError,
            "^pdf_visual_topology_atom_outside_selected_source_region$",
        ):
            self.visual.build_region_proposal_package(
                proposal_scope="candidate_crop",
                parser_observation=observation,
                crop_manifest=self.crop,
            )

    def test_normalization_collapse_is_classified_before_provider_package(self) -> None:
        projection = _projection()
        projection["bbox_inventory"][2]["bbox"] = [
            10.0,
            60.0,
            10.000000001,
            90.0,
        ]
        observation = _observation(self.contracts, projection=projection)

        with self.assertRaisesRegex(
            PdfVisualTopologyError,
            "^pdf_visual_topology_atom_normalization_defect$",
        ):
            self.visual.build_region_proposal_package(
                proposal_scope="candidate_crop",
                parser_observation=observation,
                crop_manifest=self.crop,
            )

    def test_coordinate_transform_defect_is_classified_before_atoms_are_built(
        self,
    ) -> None:
        crop = copy.deepcopy(self.crop)
        crop["source_to_pixel_transform"]["scale_x"] = 1.5
        crop.pop("manifest_hash")
        crop["manifest_hash"] = sha256_json(crop)

        with self.assertRaisesRegex(
            PdfVisualTopologyError,
            "^pdf_visual_topology_coordinate_transform_defect$",
        ):
            self.visual.build_region_proposal_package(
                proposal_scope="candidate_crop",
                parser_observation=self.observation,
                crop_manifest=crop,
            )

    def test_malformed_normalized_atom_is_provider_package_construction_error(
        self,
    ) -> None:
        package = self.visual.build_region_proposal_package(
            proposal_scope="candidate_crop",
            parser_observation=self.observation,
            crop_manifest=self.crop,
        )
        tampered = copy.deepcopy(package)
        tampered["model_facing"]["atoms"][2]["bbox"] = [
            0.05,
            0.6,
            0.05,
            0.9,
        ]
        tampered["neutral_atom_manifest_hash"] = sha256_json(
            tampered["model_facing"]["atoms"]
        )
        _reseal_region_package(tampered)

        self.assertEqual(
            ["pdf_visual_topology_provider_package_construction_invalid"],
            self.visual.validate_region_proposal_package(tampered),
        )

    def test_source_atom_overshoot_beyond_parser_allowance_fails_closed(self) -> None:
        package = self.visual.build_region_proposal_package(
            proposal_scope="candidate_crop",
            parser_observation=self.observation,
            crop_manifest=self.crop,
        )
        tampered = copy.deepcopy(package)
        candidate_id = tampered["neutral_atom_to_candidate_id"]["a0003"]
        source = tampered["private_candidate_dictionary"][candidate_id]
        source["source_bbox"] = [10.0, 60.0, 90.0, 100.7501]
        geometry = tampered["source_atom_geometry_evidence"][2]
        geometry.update(
            {
                "classification": "source_precision_overshoot_reconciled",
                "original_source_bbox": [10.0, 60.0, 90.0, 100.7501],
                "reconciled_source_bbox": [10.0, 60.0, 90.0, 100.0],
                "normalized_bbox": [0.05, 0.6, 0.45, 1.0],
                "adjustments": [
                    {
                        "edge": "bottom",
                        "from_coordinate": 100.7501,
                        "to_coordinate": 100.0,
                        "overshoot_points": 0.7501,
                        "reason_code": (
                            "pdf_visual_topology_source_atom_precision_"
                            "overshoot_reconciled"
                        ),
                    }
                ],
            }
        )
        unsigned_geometry = dict(geometry)
        unsigned_geometry.pop("evidence_checksum")
        geometry["evidence_checksum"] = sha256_json(unsigned_geometry)
        tampered["source_atom_geometry_evidence_hash"] = sha256_json(
            tampered["source_atom_geometry_evidence"]
        )
        tampered["candidate_dictionary_hash"] = sha256_json(
            tampered["private_candidate_dictionary"]
        )
        _reseal_region_package(tampered)

        self.assertEqual(
            ["pdf_visual_topology_atom_outside_selected_source_region"],
            self.visual.validate_region_proposal_package(tampered),
        )

    def test_default_policy_accepts_exposed_330_atom_regression_shape(self) -> None:
        observation = _observation(
            self.contracts,
            projection=_dense_projection(330),
        )

        package = self.visual.build_package(
            parser_observation=observation,
            crop_manifest=self.crop,
        )

        self.assertEqual(330, package["component_accounting"]["atom_count"])
        self.assertEqual(1_000, package["component_accounting"]["maximum_atoms"])
        self.assertLessEqual(
            package["component_accounting"]["model_json_bytes"],
            48 * 1024,
        )
        self.assertEqual(
            [],
            self.visual.validate_package(
                parser_observation=observation,
                package=package,
            ),
        )

    def test_atom_1001_is_rejected_before_request_construction(self) -> None:
        observation = _observation(
            self.contracts,
            projection=_dense_projection(1_001),
        )

        with self.assertRaisesRegex(
            PdfVisualTopologyError,
            "pdf_visual_topology_atom_budget_exceeded",
        ):
            self.visual.build_package(
                parser_observation=observation,
                crop_manifest=self.crop,
            )

    def test_model_json_budget_still_fails_closed_below_atom_cap(self) -> None:
        observation = _observation(
            self.contracts,
            projection=_dense_projection(20),
        )
        visual = PdfVisualTopologyFactory(
            PdfVisualTopologyConfig(maximum_model_json_bytes=1)
        ).create()

        with self.assertRaisesRegex(
            PdfVisualTopologyError,
            "pdf_visual_topology_model_json_budget_exceeded",
        ):
            visual.build_package(
                parser_observation=observation,
                crop_manifest=self.crop,
            )

    def test_static_token_budget_still_fails_closed_below_atom_cap(self) -> None:
        observation = _observation(
            self.contracts,
            projection=_dense_projection(20),
        )
        visual = PdfVisualTopologyFactory(
            PdfVisualTopologyConfig(maximum_static_input_tokens=1)
        ).create()

        with self.assertRaisesRegex(
            PdfVisualTopologyError,
            "pdf_visual_topology_static_token_budget_exceeded",
        ):
            visual.build_package(
                parser_observation=observation,
                crop_manifest=self.crop,
            )

    def test_legacy_projection_poison_does_not_change_raw_atom_package(self) -> None:
        clean_projection = _projection()
        poisoned_projection = copy.deepcopy(clean_projection)
        poisoned_projection.update(
            {
                "row_count": 99,
                "column_count": 77,
                "header_depth": 8,
                "cell_inventory": [
                    {
                        "expected_row_ordinal": 99,
                        "expected_column_ordinal": 77,
                    }
                ],
            }
        )
        clean = _observation(self.contracts, projection=clean_projection)
        poisoned = _observation(self.contracts, projection=poisoned_projection)
        clean_package = self.visual.build_package(
            parser_observation=clean,
            crop_manifest=self.crop,
        )
        poisoned_package = self.visual.build_package(
            parser_observation=poisoned,
            crop_manifest=self.crop,
        )

        self.assertEqual(clean, poisoned)
        self.assertEqual(clean_package, poisoned_package)
        geometry = PdfParserGeometryFactory().create()
        self.assertEqual(
            _geometry_observation(geometry, projection=clean_projection),
            _geometry_observation(geometry, projection=poisoned_projection),
        )

    def test_response_is_bound_to_package_and_closed_shape(self) -> None:
        package = self.visual.build_package(
            parser_observation=self.observation,
            crop_manifest=self.crop,
        )
        response = _response(package["package_id"])
        parsed = self.visual.parse_response(
            response,
            expected_package_id=package["package_id"],
        )
        self.assertEqual(response, parsed)

        foreign = copy.deepcopy(response)
        foreign["package_id"] = "foreign-package"
        with self.assertRaisesRegex(
            PdfVisualTopologyError,
            "pdf_visual_topology_response_package_mismatch",
        ):
            self.visual.parse_response(
                foreign,
                expected_package_id=package["package_id"],
            )

        leaked = copy.deepcopy(response)
        leaked["hypotheses"][0]["text"] = "invented"
        with self.assertRaisesRegex(
            PdfVisualTopologyError,
            "pdf_visual_topology_hypothesis_keys_invalid",
        ):
            self.visual.parse_response(
                leaked,
                expected_package_id=package["package_id"],
            )

    def test_borderless_contract_preserves_two_and_three_column_alternatives(
        self,
    ) -> None:
        package = self.visual.build_package(
            parser_observation=self.observation,
            crop_manifest=self.crop,
        )
        response = _response(package["package_id"])
        response["decision"] = "ambiguous"
        response["uncertainty_codes"] = ["two_or_three_columns_plausible"]
        two_columns = response["hypotheses"][0]
        two_columns["hypothesis_key"] = "two_columns"
        three_columns = copy.deepcopy(two_columns)
        three_columns["hypothesis_key"] = "three_columns"
        three_columns["column_boundaries"] = [0.0, 0.4, 0.7, 1.0]
        response["hypotheses"].append(three_columns)

        parsed = self.visual.parse_response(
            response,
            expected_package_id=package["package_id"],
        )

        self.assertEqual("ambiguous", parsed["decision"])
        self.assertEqual(
            ["two_columns", "three_columns"],
            [item["hypothesis_key"] for item in parsed["hypotheses"]],
        )
        self.assertEqual(
            [[0.0, 0.5, 1.0], [0.0, 0.4, 0.7, 1.0]],
            [item["column_boundaries"] for item in parsed["hypotheses"]],
        )

    def test_provider_schema_is_canonical_merged_and_legacy_span_normalizes(
        self,
    ) -> None:
        package = self.visual.build_package(
            parser_observation=self.observation,
            crop_manifest=self.crop,
        )
        provider_schema = package["output_schema"]
        hypothesis_schema = provider_schema["properties"]["hypotheses"]["items"]
        relation_schema = hypothesis_schema["properties"]["spans"]["items"][
            "properties"
        ]["relation"]
        self.assertEqual(["merged"], relation_schema["enum"])

        canonical = _response(package["package_id"])
        canonical["hypotheses"][0]["spans"] = [
            {
                "start_row": 1,
                "end_row": 1,
                "start_column": 1,
                "end_column": 2,
                "relation": "merged",
            }
        ]
        canonical["hypotheses"][0]["header_hierarchy"] = [
            {
                "parent_row": 1,
                "parent_column": 1,
                "child_start_column": 1,
                "child_end_column": 2,
            }
        ]
        legacy = copy.deepcopy(canonical)
        legacy["hypotheses"][0]["spans"][0]["relation"] = "spanning_header"

        parsed_canonical = self.visual.parse_response(
            canonical,
            expected_package_id=package["package_id"],
        )
        parsed_legacy = self.visual.parse_response(
            legacy,
            expected_package_id=package["package_id"],
        )

        self.assertEqual(parsed_canonical, parsed_legacy)
        self.assertEqual(
            "merged",
            parsed_legacy["hypotheses"][0]["spans"][0]["relation"],
        )
        self.assertEqual(
            "spanning_header",
            legacy["hypotheses"][0]["spans"][0]["relation"],
        )

    def test_package_validation_survives_canonical_json_key_sorting(self) -> None:
        package = self.visual.build_package(
            parser_observation=self.observation,
            crop_manifest=self.crop,
        )
        persisted = json.loads(json.dumps(package, sort_keys=True))

        self.assertEqual(
            [],
            self.visual.validate_package(
                parser_observation=self.observation,
                package=persisted,
            ),
        )

    def test_package_rejects_padding_and_rotated_crop_until_transform_is_proven(
        self,
    ) -> None:
        padded = copy.deepcopy(self.crop)
        padded["padding_points"] = 2.0
        padded["rendered_bbox"] = [-2.0, -2.0, 202.0, 102.0]
        padded.pop("manifest_hash")
        padded["manifest_hash"] = sha256_json(padded)
        with self.assertRaisesRegex(
            PdfVisualTopologyError,
            "pdf_visual_topology_crop_identity_invalid",
        ):
            self.visual.build_package(
                parser_observation=self.observation,
                crop_manifest=padded,
            )

    def test_research_runner_is_factory_routed_and_does_not_import_legacy_grid_path(
        self,
    ) -> None:
        service_root = Path(__file__).resolve().parents[1]
        runner = (
            service_root / "scripts" / "local_pdf_structural_repair_proof.py"
        ).read_text(encoding="utf-8")

        self.assertIn("PdfVisualTopologyFactory", runner)
        self.assertIn("PdfTopologyAssemblyFactory", runner)
        self.assertIn("PdfParserGeometryFactory", runner)
        self.assertIn("PdfGridExperimentProviderFactory", runner)
        self.assertIn("PdfTableRasterFactory", runner)
        self.assertNotIn("PdfHybridCompactionFactory", runner)
        self.assertNotIn("PdfHybridWindowFactory", runner)
        self.assertNotIn("PdfHybridEvidenceFactory", runner)
        self.assertNotIn("PdfHybridStructureFactory", runner)

    def test_replay_runner_separates_solver_and_reference_scoring_processes(
        self,
    ) -> None:
        service_root = Path(__file__).resolve().parents[1]
        replay_path = (
            service_root / "scripts" / "local_pdf_structural_repair_replay.py"
        )
        runner = replay_path.read_text(encoding="utf-8")
        solve_start = runner.index("def solve_replay(")
        score_start = runner.index("def score_replay(")
        solve_body = runner[solve_start:score_start]

        self.assertNotIn("reference_path", solve_body)
        self.assertNotIn("PdfGridExperimentProviderFactory", runner)
        self.assertNotIn("Gate1Normalizer", runner)
        self.assertNotIn("import requests", runner)
        self.assertIn('"accepted_binding_sha256"', runner)
        self.assertIn('"hypothesis_set_sha256"', runner)
        self.assertIn('"repeatability_sha256"', runner)
        self.assertIn('"assembly_result_sha256s"', runner)
        self.assertIn("terminal_after_scoring", runner)

    def test_replay_reference_validator_rejects_duplicate_table_keys(self) -> None:
        service_root = Path(__file__).resolve().parents[1]
        namespace = runpy.run_path(
            str(service_root / "scripts" / "local_pdf_structural_repair_replay.py")
        )
        validate_reference = namespace["_validate_reference"]
        replay_error = namespace["ReplayError"]
        duplicate = {
            "table_key": "1:2",
            "rows": 1,
            "columns": 1,
            "header_rows": 1,
            "cells": [["value"]],
        }

        with self.assertRaisesRegex(
            replay_error,
            "structural_repair_replay_reference_table_key_invalid",
        ):
            validate_reference({"tables": [duplicate, copy.deepcopy(duplicate)]})


class PdfTopologyAssemblyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contracts = PdfDualOracleContractFactory().create()
        self.geometry = PdfParserGeometryFactory().create()
        self.visual = PdfVisualTopologyFactory().create()
        self.assembler = PdfTopologyAssemblyFactory(
            visual_topology=self.visual
        ).create()
        self.observation = _observation(self.contracts)
        self.geometry_observation = _geometry_observation(self.geometry)
        self.package = self.visual.build_package(
            parser_observation=self.observation,
            crop_manifest=_crop_manifest(),
        )

    def test_clean_topology_binds_every_atom_and_materializes_only_source_values(
        self,
    ) -> None:
        assembly = self._assemble(_response(self.package["package_id"]))

        self.assertEqual(
            "broker_reports_pdf_topology_assembly_result_v6",
            assembly["schema_version"],
        )
        self.assertEqual(
            "pdf_topology_assembly_policy_v6", assembly["policy_version"]
        )
        self.assertEqual("assembled", assembly["reconstruction_status"])
        evidence = assembly["geometry_evidence"][0]
        self.assertEqual("confirmed", evidence["row_boundaries"]["status"])
        self.assertEqual("confirmed", evidence["column_boundaries"]["status"])
        self.assertEqual("confirmed", evidence["candidate_separators"]["status"])
        self.assertEqual("not_applicable", evidence["span_separators"]["status"])
        self.assertEqual("not_evaluated", assembly["certification_status"])
        self.assertFalse(assembly["value_mutation_performed"])
        self.assertFalse(assembly["nearest_cell_fallback_used"])
        accounting = assembly["source_accounting"]
        self.assertTrue(accounting["all_bound_alternatives_exactly_once"])
        binding = assembly["binding_hypotheses"][0]["binding_output"]
        self.assertEqual(2, binding["row_count"])
        self.assertEqual(2, binding["column_count"])
        self.assertEqual([1], binding["header_rows"])
        self.assertEqual(
            self.observation["candidate_order"],
            [
                candidate_id
                for row in binding["rows"]
                for cell in row["cells"]
                for candidate_id in cell
            ],
        )
        materialized = PdfHybridMaterializationFactory().create().materialize(
            evidence_package=self.package,
            binding_output=binding,
        )
        self.assertEqual(0, materialized["model_invented_values_total"])
        self.assertEqual([], materialized["omitted_candidate_ids"])
        self.assertEqual([], materialized["extra_candidate_ids"])

    def test_wide_table_preserves_both_multiline_cell_atoms_through_materialization(
        self,
    ) -> None:
        projection = _wide_multiline_projection()
        observation = _observation(self.contracts, projection=projection)
        package = self.visual.build_package(
            parser_observation=observation,
            crop_manifest=_crop_manifest(),
        )
        boundaries = [value / 200.0 for value in _wide_column_boundaries()]
        response = _response(package["package_id"])
        response["hypotheses"][0].update(
            {
                "row_boundaries": [0.0, 0.33, 0.66, 1.0],
                "column_boundaries": boundaries,
            }
        )

        assembly = self.assembler.assemble(
            parser_observation=observation,
            parser_geometry_observation=_geometry_observation(
                self.geometry, projection=projection
            ),
            visual_package=package,
            topology_response=response,
            attempt_evidence=_attempt_evidence(1),
            hypothesis_id_prefix="wide-multiline-a1",
        )

        self.assertEqual("assembled", assembly["reconstruction_status"])
        self.assertTrue(
            assembly["source_accounting"][
                "all_bound_alternatives_exactly_once"
            ]
        )
        binding = assembly["binding_hypotheses"][0]["binding_output"]
        self.assertEqual((3, 12), (binding["row_count"], binding["column_count"]))

        multiline_candidate_ids = observation["candidate_order"][15:17]
        multiline_atom_ids = ["a0016", "a0017"]
        atom_to_candidate = package["neutral_atom_to_candidate_id"]
        self.assertEqual(
            multiline_candidate_ids,
            [atom_to_candidate[atom_id] for atom_id in multiline_atom_ids],
        )
        self.assertEqual(
            multiline_candidate_ids,
            binding["rows"][1]["cells"][3],
        )

        materialized = PdfHybridMaterializationFactory().create().materialize(
            evidence_package=package,
            binding_output=binding,
        )
        multiline_cell = next(
            cell
            for cell in materialized["cells"]
            if cell["row_ordinal"] == 2 and cell["column_ordinal"] == 4
        )
        self.assertEqual((3, 12), (materialized["row_count"], materialized["column_count"]))
        self.assertEqual(multiline_candidate_ids, multiline_cell["candidate_ids"])
        self.assertEqual([], materialized["omitted_candidate_ids"])
        self.assertEqual([], materialized["extra_candidate_ids"])
        self.assertEqual([], materialized["duplicate_candidate_ids"])
        self.assertEqual(0, materialized["model_invented_values_total"])

    def test_jitter_is_snapped_to_one_canonical_geometry_without_assignment_change(
        self,
    ) -> None:
        left = _response(self.package["package_id"], split=0.49)
        right = _response(self.package["package_id"], split=0.51)
        first = self._assemble(left, attempt=1)
        second = self._assemble(right, attempt=2)

        self.assertEqual("assembled", first["reconstruction_status"])
        self.assertEqual("assembled", second["reconstruction_status"])
        first_input = first["binding_hypotheses"][0]
        second_input = second["binding_hypotheses"][0]
        self.assertEqual(
            first_input["binding_output"], second_input["binding_output"]
        )
        self.assertEqual(
            first_input["proposed_geometry"], second_input["proposed_geometry"]
        )
        self.assertEqual(
            [0.0, 0.5, 1.0],
            first_input["proposed_geometry"]["columns"]["boundaries"],
        )
        self.assertTrue(first["structural_adjustments"])
        self.assertTrue(second["structural_adjustments"])
        self.assertTrue(
            all(
                item["source_value_change_allowed"] is False
                for item in first["structural_adjustments"]
                + second["structural_adjustments"]
            )
        )
        self.assertTrue(
            all(
                item["operation"]
                == "replace_visual_boundary_with_parser_geometry"
                for item in first["structural_adjustments"]
                + second["structural_adjustments"]
            )
        )

    def test_visual_boundary_drift_is_replaced_by_independent_parser_geometry(
        self,
    ) -> None:
        response = _response(self.package["package_id"], split=0.45)
        assembly = self._assemble(response)

        self.assertEqual("assembled", assembly["reconstruction_status"])
        self.assertFalse(assembly["nearest_cell_fallback_used"])
        self.assertEqual(
            [0.0, 0.5, 1.0],
            assembly["binding_hypotheses"][0]["proposed_geometry"]["columns"][
                "boundaries"
            ],
        )
        self.assertEqual(1, len(assembly["structural_adjustments"]))
        self.assertEqual(
            1,
            assembly["source_accounting"]["alternative_accounting"][0][
                "structural_adjustments"
            ],
        )

        missing = copy.deepcopy(assembly)
        missing["structural_adjustments"] = []
        missing.pop("result_checksum")
        missing["result_checksum"] = sha256_json(missing)
        self.assertIn(
            "pdf_topology_assembly_structural_adjustment_invalid",
            self.assembler.validate_result(missing),
        )

        forged = copy.deepcopy(assembly)
        adjustment = forged["structural_adjustments"][0]
        adjustment["after"] = 0.51
        adjustment["delta"] = round(
            adjustment["after"] - adjustment["before"], 9
        )
        forged.pop("result_checksum")
        forged["result_checksum"] = sha256_json(forged)
        self.assertIn(
            "pdf_topology_assembly_structural_adjustment_invalid",
            self.assembler.validate_result(forged),
        )

    def test_cutting_internal_boundary_snaps_to_unique_source_atom_gap(
        self,
    ) -> None:
        projection = _projection()
        projection["vector_line_inventory"] = []
        observation = _observation(self.contracts, projection=projection)
        package = self.visual.build_package(
            parser_observation=observation,
            crop_manifest=_crop_manifest(),
        )
        response = _response(package["package_id"])
        response["hypotheses"][0]["row_boundaries"] = [0.0, 0.35, 1.0]

        assembly = self.assembler.assemble(
            parser_observation=observation,
            parser_geometry_observation=_geometry_observation(
                self.geometry, projection=projection
            ),
            visual_package=package,
            topology_response=response,
            attempt_evidence=_attempt_evidence(1),
            hypothesis_id_prefix="source-gap-a1",
        )

        self.assertEqual("assembled", assembly["reconstruction_status"])
        bound = assembly["binding_hypotheses"][0]
        self.assertEqual(
            [0.0, 0.5, 1.0],
            bound["proposed_geometry"]["rows"]["boundaries"],
        )
        self.assertEqual(
            observation["candidate_order"],
            [
                candidate_id
                for row in bound["binding_output"]["rows"]
                for cell in row["cells"]
                for candidate_id in cell
            ],
        )
        adjustment = next(
            item
            for item in assembly["structural_adjustments"]
            if item.get("evidence_basis") == "unique_positive_source_atom_gap"
        )
        self.assertEqual(
            "replace_visual_boundary_with_unique_source_atom_gap",
            adjustment["operation"],
        )
        self.assertEqual("row", adjustment["axis"])
        self.assertEqual(1, adjustment["boundary_index"])
        self.assertEqual(0.35, adjustment["before"])
        self.assertEqual(0.5, adjustment["after"])
        self.assertEqual([0.4, 0.6], adjustment["source_atom_gap"])
        self.assertTrue(adjustment["candidate_assignment_preserved"])
        self.assertFalse(adjustment["candidate_assignment_change_allowed"])
        self.assertEqual(2, len(adjustment["crossing_candidate_ids"]))

        for mutate in (
            lambda item: item.pop("source_atom_gap"),
            lambda item: item.__setitem__(
                "candidate_assignment_preserved", False
            ),
        ):
            tampered = copy.deepcopy(assembly)
            source_gap_adjustment = next(
                item
                for item in tampered["structural_adjustments"]
                if item.get("operation")
                == "replace_visual_boundary_with_unique_source_atom_gap"
            )
            mutate(source_gap_adjustment)
            tampered.pop("result_checksum")
            tampered["result_checksum"] = sha256_json(tampered)
            self.assertIn(
                "pdf_topology_assembly_structural_adjustment_invalid",
                self.assembler.validate_result(tampered),
            )

    def test_result_validation_rejects_resealed_forged_structural_adjustment(
        self,
    ) -> None:
        assembly = self._assemble(_response(self.package["package_id"]))
        tampered = copy.deepcopy(assembly)
        tampered["structural_adjustments"] = ["forged-unvalidated"]
        tampered.pop("result_checksum")
        tampered["result_checksum"] = sha256_json(tampered)

        self.assertIn(
            "pdf_topology_assembly_structural_adjustment_invalid",
            self.assembler.validate_result(tampered),
        )

    def test_cutting_internal_boundary_without_unique_source_gap_fails_closed(
        self,
    ) -> None:
        projection = _projection()
        projection["vector_line_inventory"] = []
        projection["bbox_inventory"][0]["bbox"] = [10.0, 10.0, 90.0, 60.0]
        projection["bbox_inventory"][1]["bbox"] = [110.0, 10.0, 190.0, 60.0]
        projection["bbox_inventory"][2]["bbox"] = [10.0, 40.0, 90.0, 90.0]
        projection["bbox_inventory"][3]["bbox"] = [110.0, 40.0, 190.0, 90.0]
        observation = _observation(self.contracts, projection=projection)
        package = self.visual.build_package(
            parser_observation=observation,
            crop_manifest=_crop_manifest(),
        )

        assembly = self.assembler.assemble(
            parser_observation=observation,
            parser_geometry_observation=_geometry_observation(
                self.geometry, projection=projection
            ),
            visual_package=package,
            topology_response=_response(package["package_id"]),
            attempt_evidence=_attempt_evidence(1),
            hypothesis_id_prefix="source-gap-overlap-a1",
        )

        self.assertEqual(
            "regional_retry_required", assembly["reconstruction_status"]
        )
        self.assertEqual([], assembly["binding_hypotheses"])
        self.assertEqual([], assembly["structural_adjustments"])
        self.assertIn(
            "pdf_topology_assembly_internal_boundary_source_gap_not_unique",
            [item["reason_code"] for item in assembly["regional_issues"]],
        )

    def test_merged_header_atoms_are_anchored_and_covered_cell_is_explicit_empty(
        self,
    ) -> None:
        response = _response(self.package["package_id"])
        response["hypotheses"][0]["spans"] = [
            {
                "start_row": 1,
                "end_row": 1,
                "start_column": 1,
                "end_column": 2,
                "relation": "spanning_header",
            }
        ]
        response["hypotheses"][0]["header_hierarchy"] = [
            {
                "parent_row": 1,
                "parent_column": 1,
                "child_start_column": 1,
                "child_end_column": 2,
            }
        ]
        merged_projection = _projection(merged_header=True)
        observation = _observation(self.contracts, projection=merged_projection)
        package = self.visual.build_package(
            parser_observation=observation,
            crop_manifest=_crop_manifest(),
        )
        geometry_observation = _geometry_observation(
            self.geometry, projection=merged_projection
        )
        response["package_id"] = package["package_id"]
        assembly = self.assembler.assemble(
            parser_observation=observation,
            parser_geometry_observation=geometry_observation,
            visual_package=package,
            topology_response=response,
            attempt_evidence=_attempt_evidence(1),
            hypothesis_id_prefix="merged-header-a1",
        )

        self.assertEqual("assembled", assembly["reconstruction_status"])
        binding = assembly["binding_hypotheses"][0]["binding_output"]
        self.assertEqual(
            observation["candidate_order"][:2],
            binding["rows"][0]["cells"][0],
        )
        self.assertEqual([], binding["rows"][0]["cells"][1])
        self.assertEqual(1, len(binding["spans"]))

    def test_redundant_single_column_header_links_are_pruned_explicitly(self) -> None:
        response = _response(self.package["package_id"])
        response["hypotheses"][0]["header_hierarchy"] = [
            {
                "parent_row": 1,
                "parent_column": column,
                "child_start_column": column,
                "child_end_column": column,
            }
            for column in (1, 2)
        ]
        assembly = self._assemble(response)

        self.assertEqual("assembled", assembly["reconstruction_status"])
        binding = assembly["binding_hypotheses"][0]["binding_output"]
        self.assertEqual([], binding["header_hierarchy"])
        self.assertEqual(
            2,
            sum(
                item["operation"]
                == "drop_redundant_identity_header_relation"
                for item in assembly["structural_adjustments"]
            ),
        )

    def test_center_on_boundary_fails_closed(self) -> None:
        projection = _projection()
        projection["bbox_inventory"][0]["bbox"] = [90.0, 10.0, 110.0, 40.0]
        observation = _observation(self.contracts, projection=projection)
        package = self.visual.build_package(
            parser_observation=observation,
            crop_manifest=_crop_manifest(),
        )
        assembly = self.assembler.assemble(
            parser_observation=observation,
            parser_geometry_observation=_geometry_observation(
                self.geometry, projection=projection
            ),
            visual_package=package,
            topology_response=_response(package["package_id"]),
            attempt_evidence=_attempt_evidence(1),
            hypothesis_id_prefix="center-boundary-a1",
        )

        self.assertEqual(
            "regional_retry_required", assembly["reconstruction_status"]
        )
        self.assertEqual([], assembly["binding_hypotheses"])
        self.assertIn(
            "pdf_topology_assembly_atom_on_column_boundary",
            [item["reason_code"] for item in assembly["regional_issues"]],
        )

    def test_atom_bbox_crossing_certified_separator_fails_closed(self) -> None:
        projection = _projection()
        projection["bbox_inventory"][0]["bbox"] = [80.0, 10.0, 105.0, 40.0]
        observation = _observation(self.contracts, projection=projection)
        package = self.visual.build_package(
            parser_observation=observation,
            crop_manifest=_crop_manifest(),
        )
        assembly = self.assembler.assemble(
            parser_observation=observation,
            parser_geometry_observation=_geometry_observation(
                self.geometry, projection=projection
            ),
            visual_package=package,
            topology_response=_response(package["package_id"]),
            attempt_evidence=_attempt_evidence(1),
            hypothesis_id_prefix="crossing-separator-a1",
        )

        self.assertEqual("regional_retry_required", assembly["reconstruction_status"])
        self.assertEqual([], assembly["binding_hypotheses"])
        self.assertIn(
            "pdf_topology_assembly_candidate_bbox_crosses_parser_separator",
            [item["reason_code"] for item in assembly["regional_issues"]],
        )
        self.assertEqual(
            "contradicted",
            assembly["geometry_evidence"][0]["candidate_separators"]["status"],
        )
        tampered = copy.deepcopy(assembly)
        tampered["geometry_evidence"] = []
        tampered.pop("result_checksum")
        tampered["result_checksum"] = sha256_json(tampered)
        self.assertIn(
            "pdf_topology_assembly_geometry_evidence_invalid",
            self.assembler.validate_result(tampered),
        )

    def test_noncontiguous_multiline_span_membership_uses_region_ownership_not_global_order_or_common_band(
        self,
    ) -> None:
        projection = _projection(merged_header=True)
        projection["bbox_inventory"][0]["bbox"] = [10.0, 10.0, 30.0, 40.0]
        projection["bbox_inventory"][2]["bbox"] = [60.0, 60.0, 90.0, 90.0]
        middle_row = next(
            item
            for item in projection["vector_line_inventory"]
            if item["object_ref"] == "vector-middle-row"
        )
        middle_bbox = next(
            item
            for item in projection["bbox_inventory"]
            if item["bbox_ref"] == middle_row["bbox_ref"]
        )
        middle_bbox["bbox"] = [100.0, 50.0, 200.0, 50.0]
        observation = _observation(self.contracts, projection=projection)
        package = self.visual.build_package(
            parser_observation=observation,
            crop_manifest=_crop_manifest(),
        )
        response = _response(package["package_id"])
        response["hypotheses"][0]["spans"] = [
            {
                "start_row": 1,
                "end_row": 2,
                "start_column": 1,
                "end_column": 1,
                "relation": "merged",
            }
        ]

        assembly = self.assembler.assemble(
            parser_observation=observation,
            parser_geometry_observation=_geometry_observation(
                self.geometry, projection=projection
            ),
            visual_package=package,
            topology_response=response,
            attempt_evidence=_attempt_evidence(1),
            hypothesis_id_prefix="multiline-span-a1",
        )

        self.assertEqual("assembled", assembly["reconstruction_status"])
        binding = assembly["binding_hypotheses"][0]["binding_output"]
        self.assertEqual(
            [observation["candidate_order"][0], observation["candidate_order"][2]],
            binding["rows"][0]["cells"][0],
        )
        self.assertEqual([], binding["rows"][1]["cells"][0])
        self.assertEqual(1, len(binding["spans"]))
        accounting = assembly["source_accounting"]["alternative_accounting"][0]
        self.assertEqual(4, accounting["used_candidates"])
        self.assertEqual(4, accounting["unique_used_candidates"])
        self.assertEqual([], accounting["omitted_candidate_ids"])
        self.assertEqual([], accounting["duplicate_candidate_ids"])
        self.assertEqual(
            "insufficient_evidence",
            assembly["geometry_evidence"][0]["span_separators"]["status"],
        )
        self.assertNotIn(
            "pdf_topology_assembly_span_source_order_not_contiguous",
            [item["reason_code"] for item in assembly["regional_issues"]],
        )
        self.assertNotIn(
            "pdf_topology_assembly_span_atom_band_incoherent",
            [item["reason_code"] for item in assembly["regional_issues"]],
        )

    def test_two_explicit_attempts_reach_supplied_scope_consensus(self) -> None:
        first = self._assemble(
            _response(self.package["package_id"], split=0.49), attempt=1
        )
        second = self._assemble(
            _response(self.package["package_id"], split=0.51), attempt=2
        )
        inputs = [
            *first["binding_hypotheses"],
            *second["binding_hypotheses"],
        ]
        hypothesis_set = self.contracts.build_vlm_hypothesis_set(
            parser_observation=self.observation,
            binding_hypotheses=inputs,
            rejected_evidence=[
                *first["rejected_evidence"],
                *second["rejected_evidence"],
            ],
            model_context=_model_context(self.package),
        )
        solver = PdfDualOracleConsensusFactory().create()
        repeatability = solver.build_repeatability_record(
            parser_observation=self.observation,
            vlm_hypothesis_set=hypothesis_set,
        )
        result = solver.solve(
            parser_observation=self.observation,
            vlm_hypothesis_set=hypothesis_set,
            historical_repeatability=repeatability,
        )

        self.assertTrue(repeatability["passed"])
        self.assertEqual("accepted_supplied_consensus", result["terminal_status"])
        self.assertFalse(result["uniqueness_proven"])
        self.assertTrue(result["supplied_hypotheses_exhausted"])
        self.assertFalse(result["structural_domain_complete"])
        self.assertTrue(result["domain_incomplete"])
        self.assertEqual("supplied_vlm_hypotheses_only", result["search_scope"])
        persisted_package = json.loads(
            json.dumps(self.package, sort_keys=True)
        )
        accepted_binding = solver.binding_from_accepted_consensus(
            parser_observation=self.observation,
            consensus_result=result,
            vlm_hypothesis_set=hypothesis_set,
            evidence_package=persisted_package,
        )
        materialized = PdfHybridMaterializationFactory().create().materialize(
            evidence_package=persisted_package,
            binding_output=accepted_binding,
        )
        self.assertEqual(0, materialized["model_invented_values_total"])
        self.assertEqual([], materialized["omitted_candidate_ids"])

    def test_false_vertical_span_crossing_parser_separator_is_dropped(self) -> None:
        response = _response(self.package["package_id"])
        response["hypotheses"][0]["spans"] = [
            {
                "start_row": 1,
                "end_row": 2,
                "start_column": 1,
                "end_column": 1,
                "relation": "merged",
            }
        ]

        assembly = self._assemble(response)

        self.assertEqual("assembled", assembly["reconstruction_status"])
        binding = assembly["binding_hypotheses"][0]["binding_output"]
        self.assertEqual([], binding["spans"])
        self.assertEqual(
            [[self.observation["candidate_order"][0]], [self.observation["candidate_order"][2]]],
            [binding["rows"][0]["cells"][0], binding["rows"][1]["cells"][0]],
        )
        self.assertIn(
            "drop_span_reduced_to_single_cell_by_parser_separator",
            [item["operation"] for item in assembly["structural_adjustments"]],
        )

    def test_overextended_span_is_trimmed_to_parser_certified_gap(self) -> None:
        projection = _three_column_projection()
        observation = _observation(self.contracts, projection=projection)
        package = self.visual.build_package(
            parser_observation=observation,
            crop_manifest=_crop_manifest(),
        )
        geometry = _geometry_observation(self.geometry, projection=projection)
        response = _response(package["package_id"])
        response["hypotheses"][0]["column_boundaries"] = [0.0, 0.3, 0.7, 1.0]
        response["hypotheses"][0]["spans"] = [
            {
                "start_row": 1,
                "end_row": 1,
                "start_column": 1,
                "end_column": 3,
                "relation": "spanning_header",
            }
        ]

        assembly = self.assembler.assemble(
            parser_observation=observation,
            parser_geometry_observation=geometry,
            visual_package=package,
            topology_response=response,
            attempt_evidence=_attempt_evidence(1),
            hypothesis_id_prefix="overextended-span-a1",
        )

        self.assertEqual("assembled", assembly["reconstruction_status"])
        binding = assembly["binding_hypotheses"][0]["binding_output"]
        self.assertEqual(2, binding["spans"][0]["end_column"])
        self.assertEqual(
            [observation["candidate_order"][0], observation["candidate_order"][1]],
            binding["rows"][0]["cells"][0],
        )
        self.assertEqual(
            [observation["candidate_order"][2]],
            binding["rows"][0]["cells"][2],
        )
        self.assertIn(
            "trim_span_to_parser_separator",
            [item["operation"] for item in assembly["structural_adjustments"]],
        )

    def test_degenerate_single_cell_spans_are_explicitly_pruned_as_noops(self) -> None:
        response = _response(self.package["package_id"])
        response["hypotheses"][0]["spans"] = [
            {
                "start_row": 1,
                "end_row": 1,
                "start_column": column,
                "end_column": column,
                "relation": "merged",
            }
            for column in (1, 2)
        ]
        with self.assertRaisesRegex(
            PdfVisualTopologyError,
            "pdf_visual_topology_span_invalid",
        ):
            self.visual.parse_response(
                response,
                expected_package_id=self.package["package_id"],
            )

        assembly = self._assemble(response)

        self.assertEqual("assembled", assembly["reconstruction_status"])
        self.assertEqual(
            [],
            assembly["binding_hypotheses"][0]["binding_output"]["spans"],
        )
        self.assertEqual(
            2,
            sum(
                item["operation"] == "drop_degenerate_single_cell_span"
                for item in assembly["structural_adjustments"]
            ),
        )

    def test_geometry_certified_empty_span_is_projected_to_explicit_empty_cells(
        self,
    ) -> None:
        projection = _projection(merged_header=True)
        projection["bbox_inventory"][0]["bbox"] = [10.0, 60.0, 90.0, 90.0]
        projection["bbox_inventory"][1]["bbox"] = [110.0, 60.0, 190.0, 90.0]
        observation = _observation(self.contracts, projection=projection)
        package = self.visual.build_package(
            parser_observation=observation,
            crop_manifest=_crop_manifest(),
        )
        response = _response(package["package_id"])
        response["hypotheses"][0]["spans"] = [
            {
                "start_row": 1,
                "end_row": 1,
                "start_column": 1,
                "end_column": 2,
                "relation": "merged",
            }
        ]

        assembly = self.assembler.assemble(
            parser_observation=observation,
            parser_geometry_observation=_geometry_observation(
                self.geometry, projection=projection
            ),
            visual_package=package,
            topology_response=response,
            attempt_evidence=_attempt_evidence(1),
            hypothesis_id_prefix="empty-span-a1",
        )

        self.assertEqual("assembled", assembly["reconstruction_status"])
        binding = assembly["binding_hypotheses"][0]["binding_output"]
        self.assertEqual([[], []], binding["rows"][0]["cells"])
        self.assertEqual([], binding["spans"])
        self.assertIn(
            "project_geometry_certified_empty_span_to_explicit_empty_cells",
            [item["operation"] for item in assembly["structural_adjustments"]],
        )

    def test_partial_separator_evidence_abstains_without_rejecting_visual_span(self) -> None:
        projection = _projection(merged_header=True)
        bbox_ref = "vector-bbox-partial-middle"
        projection["bbox_inventory"].append(
            {"bbox_ref": bbox_ref, "bbox": [100.0, 0.0, 100.0, 25.0]}
        )
        projection["vector_line_inventory"].append(
            {
                "parser_ordinal": 99,
                "object_ref": "vector-partial-middle",
                "page_ref": "page-1",
                "bbox_ref": bbox_ref,
                "linewidth": 0.5,
            }
        )
        observation = _observation(self.contracts, projection=projection)
        package = self.visual.build_package(
            parser_observation=observation,
            crop_manifest=_crop_manifest(),
        )
        response = _response(package["package_id"])
        response["hypotheses"][0]["spans"] = [
            {
                "start_row": 1,
                "end_row": 1,
                "start_column": 1,
                "end_column": 2,
                "relation": "spanning_header",
            }
        ]

        assembly = self.assembler.assemble(
            parser_observation=observation,
            parser_geometry_observation=_geometry_observation(
                self.geometry, projection=projection
            ),
            visual_package=package,
            topology_response=response,
            attempt_evidence=_attempt_evidence(1),
            hypothesis_id_prefix="partial-separator-a1",
        )

        self.assertEqual("assembled", assembly["reconstruction_status"])
        self.assertEqual(
            1,
            len(assembly["binding_hypotheses"][0]["binding_output"]["spans"]),
        )
        self.assertEqual(
            "insufficient_evidence",
            assembly["geometry_evidence"][0]["span_separators"]["status"],
        )

    def test_rect_fill_edge_cannot_contradict_span_without_vector_line(self) -> None:
        projection = _projection(merged_header=True)
        bbox_ref = "rect-bbox-fill"
        projection["bbox_inventory"].append(
            {"bbox_ref": bbox_ref, "bbox": [0.0, 0.0, 100.0, 50.0]}
        )
        projection["rect_inventory"].append(
            {
                "parser_ordinal": 1,
                "object_ref": "rect-fill",
                "page_ref": "page-1",
                "bbox_ref": bbox_ref,
                "linewidth": 0.0,
            }
        )
        observation = _observation(self.contracts, projection=projection)
        package = self.visual.build_package(
            parser_observation=observation,
            crop_manifest=_crop_manifest(),
        )
        response = _response(package["package_id"])
        response["hypotheses"][0]["spans"] = [
            {
                "start_row": 1,
                "end_row": 1,
                "start_column": 1,
                "end_column": 2,
                "relation": "spanning_header",
            }
        ]

        assembly = self.assembler.assemble(
            parser_observation=observation,
            parser_geometry_observation=_geometry_observation(
                self.geometry, projection=projection
            ),
            visual_package=package,
            topology_response=response,
            attempt_evidence=_attempt_evidence(1),
            hypothesis_id_prefix="rect-fill-a1",
        )

        self.assertEqual("assembled", assembly["reconstruction_status"])
        self.assertEqual(
            1,
            len(assembly["binding_hypotheses"][0]["binding_output"]["spans"]),
        )

    def test_missing_parser_geometry_boundary_abstains_and_keeps_visual_hypothesis(
        self,
    ) -> None:
        projection = _projection()
        projection["vector_line_inventory"] = [
            item
            for item in projection["vector_line_inventory"]
            if item["object_ref"] != "vector-middle"
        ]
        observation = _observation(self.contracts, projection=projection)
        package = self.visual.build_package(
            parser_observation=observation,
            crop_manifest=_crop_manifest(),
        )

        assembly = self.assembler.assemble(
            parser_observation=observation,
            parser_geometry_observation=_geometry_observation(
                self.geometry, projection=projection
            ),
            visual_package=package,
            topology_response=_response(package["package_id"]),
            attempt_evidence=_attempt_evidence(1),
            hypothesis_id_prefix="missing-boundary-a1",
        )

        self.assertEqual("assembled", assembly["reconstruction_status"])
        self.assertEqual(
            [0.0, 0.5, 1.0],
            assembly["binding_hypotheses"][0]["proposed_geometry"]["columns"][
                "boundaries"
            ],
        )
        column_evidence = assembly["geometry_evidence"][0]["column_boundaries"]
        self.assertEqual("insufficient_evidence", column_evidence["status"])
        self.assertEqual(2, column_evidence["observed_count"])
        self.assertEqual(3, column_evidence["required_count"])
        self.assertEqual(
            ["pdf_topology_assembly_parser_geometry_incomplete"],
            column_evidence["reason_codes"],
        )

    def test_missing_vector_line_sets_are_insufficient_evidence_not_rejection(
        self,
    ) -> None:
        projection = _projection()
        projection["vector_line_inventory"] = []
        observation = _observation(self.contracts, projection=projection)
        package = self.visual.build_package(
            parser_observation=observation,
            crop_manifest=_crop_manifest(),
        )

        assembly = self.assembler.assemble(
            parser_observation=observation,
            parser_geometry_observation=_geometry_observation(
                self.geometry, projection=projection
            ),
            visual_package=package,
            topology_response=_response(package["package_id"]),
            attempt_evidence=_attempt_evidence(1),
            hypothesis_id_prefix="missing-geometry-a1",
        )

        self.assertEqual("assembled", assembly["reconstruction_status"])
        evidence = assembly["geometry_evidence"][0]
        for subject in ("row_boundaries", "column_boundaries"):
            self.assertEqual("insufficient_evidence", evidence[subject]["status"])
            self.assertEqual(0, evidence[subject]["observed_count"])
            self.assertEqual(
                ["pdf_topology_assembly_parser_geometry_missing"],
                evidence[subject]["reason_codes"],
            )
        self.assertEqual(
            "insufficient_evidence", evidence["candidate_separators"]["status"]
        )
        self.assertEqual("not_applicable", evidence["span_separators"]["status"])

    def test_parser_geometry_scope_mismatch_fails_closed(self) -> None:
        foreign = _geometry_observation(self.geometry, table_ref="foreign-table")

        with self.assertRaisesRegex(
            PdfTopologyAssemblyError,
            "pdf_topology_assembly_parser_geometry_scope_mismatch",
        ):
            self.assembler.assemble(
                parser_observation=self.observation,
                parser_geometry_observation=foreign,
                visual_package=self.package,
                topology_response=_response(self.package["package_id"]),
                attempt_evidence=_attempt_evidence(1),
                hypothesis_id_prefix="foreign-geometry-a1",
            )

    def test_parser_geometry_v1_upgrade_is_explicit_and_canonical(self) -> None:
        current = _geometry_observation(self.geometry)
        legacy = copy.deepcopy(current)
        legacy["schema_version"] = (
            "broker_reports_pdf_parser_geometry_observation_v1"
        )
        legacy["policy_version"] = "pdf_parser_geometry_policy_v1"
        legacy_config = {
            "policy_version": "pdf_parser_geometry_policy_v1",
            "axis_alignment_tolerance_points": 0.75,
            "table_intersection_tolerance_points": 1.5,
            "minimum_signal_extent_points": 0.5,
            "maximum_signals": 20_000,
        }
        legacy["policy_configuration_hash"] = sha256_json(legacy_config)
        legacy["observation_id"] = "pdfparsergeom_legacy-persisted-id"
        legacy.pop("observation_checksum")
        legacy["observation_checksum"] = sha256_json(legacy)

        persisted = json.loads(json.dumps(legacy, sort_keys=True))
        upgraded = self.geometry.upgrade_v1_observation(persisted)

        self.assertEqual(current, upgraded)
        self.assertEqual([], self.geometry.validate_observation(upgraded))

    def test_parser_geometry_v1_upgrade_rejects_tampered_checksum(self) -> None:
        legacy = copy.deepcopy(_geometry_observation(self.geometry))
        legacy["schema_version"] = (
            "broker_reports_pdf_parser_geometry_observation_v1"
        )
        legacy["policy_version"] = "pdf_parser_geometry_policy_v1"
        legacy["policy_configuration_hash"] = sha256_json(
            {
                "policy_version": "pdf_parser_geometry_policy_v1",
                "axis_alignment_tolerance_points": 0.75,
                "table_intersection_tolerance_points": 1.5,
                "minimum_signal_extent_points": 0.5,
                "maximum_signals": 20_000,
            }
        )
        legacy["observation_checksum"] = "tampered"

        with self.assertRaisesRegex(
            PdfParserGeometryError,
            "pdf_parser_geometry_legacy_observation_checksum_invalid",
        ):
            self.geometry.upgrade_v1_observation(legacy)

    def test_runtime_constructor_requires_factory(self) -> None:
        with self.assertRaisesRegex(
            PdfTopologyAssemblyError,
            "pdf_topology_assembly_factory_required",
        ):
            PdfTopologyAssemblyRuntime(
                PdfTopologyAssemblyConfig(),
                visual_topology=self.visual,
                parser_geometry=self.geometry,
            )

        with self.assertRaisesRegex(
            PdfParserGeometryError,
            "pdf_parser_geometry_factory_required",
        ):
            PdfParserGeometryRuntime(PdfParserGeometryConfig())

    def _assemble(self, response: dict, *, attempt: int = 1) -> dict:
        return self.assembler.assemble(
            parser_observation=self.observation,
            parser_geometry_observation=self.geometry_observation,
            visual_package=self.package,
            topology_response=response,
            attempt_evidence=_attempt_evidence(attempt),
            hypothesis_id_prefix=f"visual-topology-a{attempt}",
        )


def _observation(contracts, *, projection: dict | None = None) -> dict:
    return contracts.build_parser_observation_from_word_atoms(
        document_ref="document-1",
        pdf_sha256="pdf-sha",
        page_ref="page-1",
        page_number=1,
        table_ref="table-1",
        table_bbox=[0.0, 0.0, 200.0, 100.0],
        pdf_text_layer_projection=projection or _projection(),
    )


def _projection(*, merged_header: bool = False) -> dict:
    values = (
        ("alpha-private", [10.0, 10.0, 90.0, 40.0]),
        ("beta-private", [110.0, 10.0, 190.0, 40.0]),
        ("gamma-private", [10.0, 60.0, 90.0, 90.0]),
        ("delta-private", [110.0, 60.0, 190.0, 90.0]),
    )
    bboxes = []
    words = []
    for ordinal, (text, bbox) in enumerate(values, start=1):
        bbox_ref = f"bbox-{ordinal}"
        bboxes.append({"bbox_ref": bbox_ref, "bbox": list(bbox)})
        words.append(
            {
                "parser_ordinal": ordinal,
                "word_ref": f"word-{ordinal}",
                "page_ref": "page-1",
                "bbox_ref": bbox_ref,
                "text": text,
                "geometry_reading_order": ordinal,
                "text_checksum_ref": f"text-checksum-{ordinal}",
                "source_value_ref": f"source-{ordinal}",
            }
        )
    vector_specs = [
        ([0.0, 0.0, 0.0, 100.0], "left"),
        ([100.0, 50.0 if merged_header else 0.0, 100.0, 100.0], "middle"),
        ([200.0, 0.0, 200.0, 100.0], "right"),
        ([0.0, 0.0, 200.0, 0.0], "top"),
        ([0.0, 50.0, 200.0, 50.0], "middle-row"),
        ([0.0, 100.0, 200.0, 100.0], "bottom"),
    ]
    vectors = []
    for ordinal, (bbox, label) in enumerate(vector_specs, start=1):
        bbox_ref = f"vector-bbox-{ordinal}"
        bboxes.append({"bbox_ref": bbox_ref, "bbox": list(bbox)})
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


def _three_column_projection() -> dict:
    values = (
        ("one-private", [10.0, 10.0, 50.0, 40.0]),
        ("two-private", [70.0, 10.0, 130.0, 40.0]),
        ("three-private", [150.0, 10.0, 190.0, 40.0]),
        ("four-private", [10.0, 60.0, 50.0, 90.0]),
        ("five-private", [70.0, 60.0, 130.0, 90.0]),
        ("six-private", [150.0, 60.0, 190.0, 90.0]),
    )
    bboxes = []
    words = []
    for ordinal, (value, bbox) in enumerate(values, start=1):
        bbox_ref = f"three-word-bbox-{ordinal}"
        bboxes.append({"bbox_ref": bbox_ref, "bbox": list(bbox)})
        words.append(
            {
                "parser_ordinal": ordinal,
                "word_ref": f"three-word-{ordinal}",
                "page_ref": "page-1",
                "bbox_ref": bbox_ref,
                "text": value,
                "geometry_reading_order": ordinal,
                "text_checksum_ref": f"three-text-checksum-{ordinal}",
                "source_value_ref": f"three-source-{ordinal}",
            }
        )
    vector_specs = (
        ("left", [0.0, 0.0, 0.0, 100.0]),
        ("first", [60.0, 50.0, 60.0, 100.0]),
        ("second", [140.0, 0.0, 140.0, 100.0]),
        ("right", [200.0, 0.0, 200.0, 100.0]),
        ("top", [0.0, 0.0, 200.0, 0.0]),
        ("middle-row", [0.0, 50.0, 200.0, 50.0]),
        ("bottom", [0.0, 100.0, 200.0, 100.0]),
    )
    vectors = []
    for ordinal, (label, bbox) in enumerate(vector_specs, start=1):
        bbox_ref = f"three-vector-bbox-{ordinal}"
        bboxes.append({"bbox_ref": bbox_ref, "bbox": list(bbox)})
        vectors.append(
            {
                "parser_ordinal": ordinal,
                "object_ref": f"three-vector-{label}",
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


def _wide_column_boundaries() -> list[float]:
    return [float(value) for value in range(0, 192, 16)] + [200.0]


def _wide_multiline_projection() -> dict:
    column_boundaries = _wide_column_boundaries()
    row_boundaries = [0.0, 33.0, 66.0, 100.0]
    bboxes = []
    words = []
    ordinal = 0
    for row in range(3):
        for column in range(12):
            x0 = column_boundaries[column]
            x1 = column_boundaries[column + 1]
            y0 = row_boundaries[row]
            y1 = row_boundaries[row + 1]
            line_boxes = (
                [(x0 + 2.0, y0 + 5.0, x1 - 2.0, y0 + 13.0),
                 (x0 + 2.0, y0 + 18.0, x1 - 2.0, y0 + 26.0)]
                if (row, column) == (1, 3)
                else [(x0 + 2.0, y0 + 9.0, x1 - 2.0, y1 - 9.0)]
            )
            for line, bbox in enumerate(line_boxes, start=1):
                ordinal += 1
                bbox_ref = f"wide-word-bbox-{ordinal}"
                bboxes.append({"bbox_ref": bbox_ref, "bbox": list(bbox)})
                words.append(
                    {
                        "parser_ordinal": ordinal,
                        "word_ref": f"wide-word-{ordinal}",
                        "page_ref": "page-1",
                        "bbox_ref": bbox_ref,
                        "text": f"r{row + 1}c{column + 1}l{line}-private",
                        "geometry_reading_order": ordinal,
                        "text_checksum_ref": f"wide-checksum-{ordinal}",
                        "source_value_ref": f"wide-source-{ordinal}",
                    }
                )

    vector_specs = [
        (f"column-{index}", [x, 0.0, x, 100.0])
        for index, x in enumerate(column_boundaries)
    ] + [
        (f"row-{index}", [0.0, y, 200.0, y])
        for index, y in enumerate(row_boundaries)
    ]
    vectors = []
    for vector_ordinal, (label, bbox) in enumerate(vector_specs, start=1):
        bbox_ref = f"wide-vector-bbox-{vector_ordinal}"
        bboxes.append({"bbox_ref": bbox_ref, "bbox": list(bbox)})
        vectors.append(
            {
                "parser_ordinal": vector_ordinal,
                "object_ref": f"wide-vector-{label}",
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


def _dense_projection(atom_count: int) -> dict:
    bboxes = []
    words = []
    columns = 20
    for ordinal in range(1, atom_count + 1):
        row = (ordinal - 1) // columns
        column = (ordinal - 1) % columns
        x0 = float(column * 10 + 1)
        y0 = float(row * 1.8 + 0.2)
        bbox_ref = f"dense-bbox-{ordinal}"
        bboxes.append(
            {
                "bbox_ref": bbox_ref,
                "bbox": [x0, y0, x0 + 8.0, y0 + 1.0],
            }
        )
        words.append(
            {
                "parser_ordinal": ordinal,
                "word_ref": f"dense-word-{ordinal}",
                "page_ref": "page-1",
                "bbox_ref": bbox_ref,
                "text": f"v{ordinal}",
                "geometry_reading_order": ordinal,
                "text_checksum_ref": f"dense-checksum-{ordinal}",
                "source_value_ref": f"dense-source-{ordinal}",
            }
        )
    return {
        "bbox_inventory": bboxes,
        "word_inventory": words,
        "line_inventory": [],
        "vector_line_inventory": [],
        "rect_inventory": [],
    }


def _geometry_observation(
    geometry, *, projection: dict | None = None, table_ref: str = "table-1"
) -> dict:
    return geometry.build_observation(
        document_ref="document-1",
        pdf_sha256="pdf-sha",
        page_ref="page-1",
        page_number=1,
        table_ref=table_ref,
        table_bbox=[0.0, 0.0, 200.0, 100.0],
        pdf_text_layer_projection=projection or _projection(),
    )


def _crop_manifest() -> dict:
    value = {
        "schema_version": "broker_reports_pdf_table_crop_v1",
        "policy_version": "pdf_table_raster_policy_v1",
        "crop_id": "crop-1",
        "document_ref": "document-1",
        "pdf_sha256": "pdf-sha",
        "page_number": 1,
        "table_ref": "table-1",
        "declared_table_bbox": [0.0, 0.0, 200.0, 100.0],
        "rendered_bbox": [0.0, 0.0, 200.0, 100.0],
        "source_coordinate_space": "pdf_top_left_points",
        "pixel_coordinate_space": "crop_top_left_pixels",
        "source_to_pixel_transform": {
            "scale_x": 2.0,
            "scale_y": 2.0,
            "translate_source_x": 0.0,
            "translate_source_y": 0.0,
        },
        "renderer": "pymupdf",
        "renderer_version": "1.26.5",
        "page_rotation": 0,
        "applied_rotation": 0,
        "padding_points": 0.0,
        "dpi": 150,
        "dpi_revision_reason": "primary_150_dpi",
        "width": 400,
        "height": 200,
        "pixels": 80_000,
        "png_bytes": 100,
        "png_sha256": "crop-sha",
        "lossless": True,
        "silent_resize_performed": False,
    }
    value["manifest_hash"] = sha256_json(value)
    return value


def _reseal_region_package(package: dict) -> None:
    package_id = "pdfvisualregionpkg_" + stable_digest(
        [
            package["pdf_sha256"],
            package["page_number"],
            package["crop_identity"]["manifest_hash"],
            package["proposal_scope"],
            package["neutral_atom_manifest_hash"],
            package["policy_version"],
            package["contract_revision"],
        ],
        length=24,
    )
    package["package_id"] = package_id
    package["model_facing"]["identity"]["package_id"] = package_id
    unsigned = dict(package)
    unsigned.pop("package_hash")
    package["package_hash"] = sha256_json(unsigned)


def _response(package_id: str, *, split: float = 0.5) -> dict:
    return {
        "schema_version": PDF_VISUAL_TOPOLOGY_RESPONSE_SCHEMA,
        "package_id": package_id,
        "decision": "bound",
        "alternatives_complete": True,
        "hypotheses": [
            {
                "hypothesis_key": "primary",
                "row_boundaries": [0.0, 0.5, 1.0],
                "column_boundaries": [0.0, split, 1.0],
                "header_row_count": 1,
                "spans": [],
                "header_hierarchy": [],
                "continuation_required": False,
                "uncertainty_codes": [],
            }
        ],
        "uncertainty_codes": [],
    }


def _attempt_evidence(attempt: int) -> dict:
    return {
        "attempt_id": f"visual-attempt-{attempt}",
        "attempt_number": attempt,
        "evidence_revision": "stable-visual-package-revision",
        "provider": "test-provider",
        "model": "test-model",
        "provider_config_hash": "test-provider-config",
    }


def _model_context(package: dict) -> dict:
    return {
        "provider": "test-provider",
        "model": "test-model",
        "configuration_hash": "test-provider-config",
        "bounded_row_windows": True,
        "provider_calls_replayed": 0,
        "new_provider_calls": 2,
        "topology_input_basis": "visual_crop_without_parser_grid",
        "topology_dimensions_source": "vlm_visual_observation",
        "alternative_generation_contract": "explicit_exhaustive_bounded_alternatives",
        "topology_prompt_contract_hash": sha256_json(
            package["model_facing"]["task"]
        ),
        "crop_manifest_hash": package["crop_identity"]["manifest_hash"],
        "observed_image_bytes": package["crop_identity"]["png_bytes"],
        "maximum_image_bytes": 8 * 1024 * 1024,
        "observed_output_tokens": 100,
        "maximum_output_tokens": 8192,
        "provider_token_accounting_exact": True,
        "candidate_ownership_exact": True,
        "no_silent_truncation": True,
        "column_splitting_used": False,
        "hidden_provider_failover": False,
        "alternative_topology_hypotheses_complete": True,
    }


if __name__ == "__main__":
    unittest.main()
