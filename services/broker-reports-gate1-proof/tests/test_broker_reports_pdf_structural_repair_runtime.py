from __future__ import annotations

import copy
import hashlib
import unittest

from broker_reports_gate1.contracts import stable_digest
from broker_reports_gate1.pdf_dual_oracle_contracts import (
    PdfDualOracleContractFactory,
)
from broker_reports_gate1.pdf_hybrid_contracts import (
    canonical_json_bytes,
    sha256_json,
)
from broker_reports_gate1.pdf_grid_experiment_provider import PdfGridProviderError
from broker_reports_gate1.pdf_parser_geometry import PdfParserGeometryFactory
from broker_reports_gate1.pdf_structural_repair_runtime import (
    FACTORY_REQUIRED,
    FORBIDDEN,
    PDF_VLM_PAGE_PROPOSAL_RESULT_SCHEMA,
    PdfStructuralRepairRuntime,
    PdfStructuralRepairRuntimeConfig,
    PdfStructuralRepairRuntimeError,
    PdfStructuralRepairRuntimeFactory,
)
from broker_reports_gate1.pdf_visual_topology import (
    PDF_VISUAL_TOPOLOGY_REGION_PROPOSAL_REVISION,
    PDF_VISUAL_TOPOLOGY_RESPONSE_SCHEMA,
    PdfVisualTopologyFactory,
)


class _Provider:
    def __init__(self, *, counted_tokens: int = 100) -> None:
        self.counted_tokens = counted_tokens
        self.count_calls = 0
        self.generate_calls = 0
        self.package_id = ""

    def qualify(self) -> dict:
        return {
            "status": "qualified",
            "provider_profile": "google_gemini",
            "requested_model_id": "models/gemini-3.5-flash",
            "resolved_model_id": "models/gemini-3.5-flash",
            "exact_model_match": True,
            "image_input_supported": True,
            "structured_output_supported": True,
            "maximum_input_tokens": 1_000_000,
            "maximum_output_tokens": 65_536,
            "hidden_retry": False,
            "provider_failover": False,
        }

    def count_tokens(self, **kwargs) -> dict:
        self.count_calls += 1
        return {
            "total_tokens": self.counted_tokens,
            "model_requested": "models/gemini-3.5-flash",
            "within_hard_guard": True,
        }

    def invoke(
        self,
        *,
        task_id: str,
        attempt_number: int,
        attempt_lineage: list[str],
        **kwargs,
    ) -> dict:
        self.generate_calls += 1
        attempt_id = f"{task_id}_a{attempt_number}"
        return {
            "attempt": {
                "task_id": task_id,
                "attempt_id": attempt_id,
                "attempt_number": attempt_number,
                "attempt_lineage": list(attempt_lineage),
                "model_requested": "models/gemini-3.5-flash",
                "model_resolved": "models/gemini-3.5-flash",
                "started_at": f"2026-07-14T00:00:0{attempt_number}Z",
                "usage": {
                    "input_tokens": self.counted_tokens,
                    "output_tokens": 20,
                    "total_tokens": self.counted_tokens + 20,
                },
                "finish_reason": "STOP",
                "terminal_failure_class": None,
                "hidden_retry": False,
                "provider_failover": False,
            },
            "json_output": _topology_response(self.package_id),
            "raw_private_response": {"private": "provider-boundary"},
            "visible_output_bytes": 100,
            "response_bytes": 200,
        }


class _BudgetErrorProvider(_Provider):
    def count_tokens(self, **kwargs) -> dict:
        self.count_calls += 1
        raise PdfGridProviderError(
            "pdf_grid_provider_counted_input_budget_exceeded",
            "context_budget",
            safe_details={
                "observed_total_tokens": 21_337,
                "maximum_counted_input_tokens": 20_000,
            },
        )


class _ResponseProvider(_Provider):
    def __init__(self, response: dict, *, counted_tokens: int = 100) -> None:
        super().__init__(counted_tokens=counted_tokens)
        self.response = copy.deepcopy(response)

    def invoke(self, **kwargs) -> dict:
        result = super().invoke(**kwargs)
        response = copy.deepcopy(self.response)
        response["package_id"] = self.package_id
        result["json_output"] = response
        return result


class _InvokeErrorProvider(_Provider):
    def invoke(self, **kwargs) -> dict:
        self.generate_calls += 1
        raise PdfGridProviderError(
            "pdf_grid_provider_request_failed",
            "provider_transport",
        )


class PdfStructuralRepairRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        contracts = PdfDualOracleContractFactory().create()
        self.projection = _projection()
        self.observation = contracts.build_parser_observation_from_word_atoms(
            document_ref="document-1",
            pdf_sha256="pdf-sha",
            page_ref="page-1",
            page_number=1,
            table_ref="table-1",
            table_bbox=[0.0, 0.0, 200.0, 100.0],
            pdf_text_layer_projection=self.projection,
        )
        self.geometry = (
            PdfParserGeometryFactory()
            .create()
            .build_observation(
                document_ref="document-1",
                pdf_sha256="pdf-sha",
                page_ref="page-1",
                page_number=1,
                table_ref="table-1",
                table_bbox=[0.0, 0.0, 200.0, 100.0],
                pdf_text_layer_projection=self.projection,
            )
        )
        self.png_bytes = b"lossless-test-png"
        self.crop = _crop_manifest(self.png_bytes)
        self.package = (
            PdfVisualTopologyFactory()
            .create()
            .build_package(
                parser_observation=self.observation,
                crop_manifest=self.crop,
            )
        )
        self.page_package = (
            PdfVisualTopologyFactory()
            .create()
            .build_region_proposal_package(
                proposal_scope="page_level",
                crop_manifest=self.crop,
            )
        )
        self.candidate_region_package = (
            PdfVisualTopologyFactory()
            .create()
            .build_region_proposal_package(
                proposal_scope="candidate_crop",
                parser_observation=self.observation,
                crop_manifest=self.crop,
            )
        )

    def test_factory_runtime_executes_exact_two_attempt_terminal(self) -> None:
        provider = _Provider()
        provider.package_id = self.package["package_id"]
        runtime = PdfStructuralRepairRuntimeFactory().create(provider=provider)
        qualification = runtime.qualify_provider()

        result = runtime.run_target(
            target_id="regression_001",
            parser_observation=self.observation,
            parser_geometry_observation=self.geometry,
            visual_package=self.package,
            png_bytes=self.png_bytes,
            provider_qualification=qualification,
        )

        self.assertEqual(
            "accepted_supplied_consensus", result["runtime_terminal_status"]
        )
        self.assertFalse(result["safe_summary"]["uniqueness_proven"])
        self.assertTrue(result["safe_summary"]["supplied_hypotheses_exhausted"])
        self.assertFalse(result["safe_summary"]["structural_domain_complete"])
        self.assertTrue(result["safe_summary"]["domain_incomplete"])
        self.assertEqual(2, provider.count_calls)
        self.assertEqual(2, provider.generate_calls)
        self.assertEqual(2, result["new_provider_count_token_calls"])
        self.assertEqual(2, result["new_provider_generate_calls"])
        self.assertEqual(2, len(result["journal"]))
        self.assertIsNotNone(result["accepted_binding"])
        self.assertEqual(2, result["materialization"]["row_count"])
        self.assertEqual(2, result["materialization"]["column_count"])
        self.assertEqual(0, result["materialization"]["model_invented_values_total"])
        self.assertTrue(result["safe_summary"]["all_candidates_accounted"])
        self.assertFalse(result["safe_summary"]["production_authority"])
        self.assertEqual([], runtime.validate_result(result))

    def test_guided_candidate_executes_exactly_one_call_and_materializes(self) -> None:
        provider = _ResponseProvider(
            _region_proposal_response(
                "",
                scope="candidate_crop",
                presence="present",
                regions=[_proposal_region("candidate", [0.0, 0.0, 1.0, 1.0])],
            )
        )
        provider.package_id = self.candidate_region_package["package_id"]
        runtime = PdfStructuralRepairRuntimeFactory().create(provider=provider)

        result = runtime.run_candidate_once(
            target_id="guided_candidate_001",
            parser_observation=self.observation,
            parser_geometry_observation=self.geometry,
            visual_package=self.candidate_region_package,
            png_bytes=self.png_bytes,
            provider_qualification=runtime.qualify_provider(),
        )

        self.assertEqual(
            "accepted_physical_structure", result["runtime_terminal_status"]
        )
        self.assertEqual((1, 1), (provider.count_calls, provider.generate_calls))
        self.assertEqual(1, len(result["journal"]))
        self.assertTrue(result["post_validation"]["passed"])
        self.assertTrue(result["safe_summary"]["all_candidates_accounted"])
        self.assertEqual(0, result["materialization"]["model_invented_values_total"])
        self.assertFalse(result["safe_summary"]["production_authority"])
        self.assertNotIn("provider-boundary", repr(result["safe_summary"]))
        self.assertEqual([], runtime.validate_result(result))

    def test_guided_candidate_rejects_non_candidate_region_packages_before_calls(
        self,
    ) -> None:
        for label, package in (
            ("legacy_value_free", self.package),
            ("page_level", self.page_package),
        ):
            with self.subTest(package=label):
                provider = _Provider()
                provider.package_id = package["package_id"]
                runtime = PdfStructuralRepairRuntimeFactory().create(
                    provider=provider
                )

                with self.assertRaisesRegex(
                    PdfStructuralRepairRuntimeError,
                    "pdf_structural_repair_input_invalid",
                ):
                    runtime.run_candidate_once(
                        target_id=f"guided_candidate_reject_{label}",
                        parser_observation=self.observation,
                        parser_geometry_observation=self.geometry,
                        visual_package=package,
                        png_bytes=self.png_bytes,
                        provider_qualification=runtime.qualify_provider(),
                    )

                self.assertEqual((0, 0), (provider.count_calls, provider.generate_calls))

    def test_page_proposal_persists_present_regions_with_one_count_and_generate(
        self,
    ) -> None:
        provider = _ResponseProvider(
            _region_proposal_response(
                "",
                scope="page_level",
                presence="present",
                regions=[
                    _proposal_region("left", [0.05, 0.1, 0.45, 0.9]),
                    _proposal_region("right", [0.55, 0.1, 0.95, 0.9]),
                ],
            )
        )
        provider.package_id = self.page_package["package_id"]
        runtime = PdfStructuralRepairRuntimeFactory().create(provider=provider)

        result = runtime.run_page_proposal_once(
            target_id="page_proposal_present",
            visual_package=self.page_package,
            png_bytes=self.png_bytes,
            provider_qualification=runtime.qualify_provider(),
        )

        self.assertEqual(PDF_VLM_PAGE_PROPOSAL_RESULT_SCHEMA, result["schema_version"])
        self.assertEqual("proposal_persisted", result["runtime_terminal_status"])
        self.assertEqual("present", result["table_presence"])
        self.assertEqual(2, len(result["proposal"]["regions"]))
        self.assertEqual((1, 1), (provider.count_calls, provider.generate_calls))
        self.assertEqual(0, result["safe_summary"]["input_atom_count"])
        self.assertEqual(2, result["safe_summary"]["regions_proposed"])
        self.assertTrue(result["safe_summary"]["proposal_persisted"])
        self.assertFalse(result["default_enabled"])
        self.assertEqual("shadow_non_authoritative", result["authority_state"])
        self.assertNotIn("provider-boundary", repr(result["safe_summary"]))
        self.assertEqual([], runtime.validate_result(result))

    def test_page_proposal_persists_absent_and_uncertain_without_atoms(self) -> None:
        for presence, regions, uncertainty in (
            ("absent", [], []),
            ("uncertain", [], ["possible_borderless_table"]),
        ):
            with self.subTest(presence=presence):
                response = _region_proposal_response(
                    "",
                    scope="page_level",
                    presence=presence,
                    regions=regions,
                )
                response["uncertainty_codes"] = uncertainty
                provider = _ResponseProvider(response)
                provider.package_id = self.page_package["package_id"]
                runtime = PdfStructuralRepairRuntimeFactory().create(provider=provider)

                result = runtime.run_page_proposal_once(
                    target_id=f"page_proposal_{presence}",
                    visual_package=self.page_package,
                    png_bytes=self.png_bytes,
                    provider_qualification=runtime.qualify_provider(),
                )

                self.assertEqual(
                    "proposal_persisted", result["runtime_terminal_status"]
                )
                self.assertEqual(presence, result["table_presence"])
                self.assertEqual([], result["proposal"]["regions"])
                self.assertEqual(
                    (1, 1), (provider.count_calls, provider.generate_calls)
                )
                self.assertEqual([], runtime.validate_result(result))

    def test_page_proposal_count_budget_is_one_count_and_zero_generate(self) -> None:
        provider = _Provider(counted_tokens=20_001)
        provider.package_id = self.page_package["package_id"]
        runtime = PdfStructuralRepairRuntimeFactory().create(provider=provider)

        result = runtime.run_page_proposal_once(
            target_id="page_proposal_budget",
            visual_package=self.page_package,
            png_bytes=self.png_bytes,
            provider_qualification=runtime.qualify_provider(),
        )

        self.assertEqual("preflight_blocked", result["runtime_terminal_status"])
        self.assertEqual((1, 0), (provider.count_calls, provider.generate_calls))
        self.assertIsNone(result["proposal"])
        self.assertEqual("not_evaluated", result["table_presence"])
        self.assertEqual(
            ["pdf_structural_repair_counted_input_budget_exceeded"],
            result["safe_summary"]["reason_codes"],
        )
        self.assertEqual([], runtime.validate_result(result))

    def test_page_proposal_provider_and_parse_failures_are_one_count_one_generate(
        self,
    ) -> None:
        invalid_response = _region_proposal_response(
            "",
            scope="page_level",
            presence="absent",
            regions=[],
        )
        invalid_response["unexpected"] = True
        cases = (
            (_InvokeErrorProvider(), "provider_failed"),
            (_ResponseProvider(invalid_response), "proposal_invalid"),
        )
        for provider, expected_terminal in cases:
            with self.subTest(terminal=expected_terminal):
                provider.package_id = self.page_package["package_id"]
                runtime = PdfStructuralRepairRuntimeFactory().create(provider=provider)

                result = runtime.run_page_proposal_once(
                    target_id=f"page_{expected_terminal}",
                    visual_package=self.page_package,
                    png_bytes=self.png_bytes,
                    provider_qualification=runtime.qualify_provider(),
                )

                self.assertEqual(expected_terminal, result["runtime_terminal_status"])
                self.assertEqual(
                    (1, 1), (provider.count_calls, provider.generate_calls)
                )
                self.assertIsNone(result["proposal"])
                self.assertEqual("not_evaluated", result["table_presence"])
                self.assertEqual([], runtime.validate_result(result))

    def test_page_proposal_result_checksum_fails_closed(self) -> None:
        provider = _ResponseProvider(
            _region_proposal_response(
                "",
                scope="page_level",
                presence="absent",
                regions=[],
            )
        )
        provider.package_id = self.page_package["package_id"]
        runtime = PdfStructuralRepairRuntimeFactory().create(provider=provider)
        result = runtime.run_page_proposal_once(
            target_id="page_proposal_checksum",
            visual_package=self.page_package,
            png_bytes=self.png_bytes,
            provider_qualification=runtime.qualify_provider(),
        )
        tampered = copy.deepcopy(result)
        tampered["table_presence"] = "uncertain"

        self.assertIn(
            "pdf_vlm_page_proposal_result_checksum_invalid",
            runtime.validate_result(tampered),
        )

    def test_guided_candidate_consumes_full_scope_region_proposal(self) -> None:
        region_atoms = self.candidate_region_package["model_facing"]["atoms"]
        for field in (
            "source_coordinate_space",
            "pixel_coordinate_space",
            "source_to_pixel_transform",
        ):
            self.assertEqual(
                self.crop[field],
                self.candidate_region_package["crop_identity"][field],
            )
        self.assertTrue(
            all(
                set(atom) == {"atom_id", "bbox", "order", "text"}
                and isinstance(atom["text"], str)
                for atom in region_atoms
            )
        )
        self.assertEqual(
            [
                "alpha-private",
                "beta-private",
                "gamma-private",
                "delta-private",
            ],
            [atom["text"] for atom in region_atoms],
        )
        provider = _ResponseProvider(
            _region_proposal_response(
                "",
                scope="candidate_crop",
                presence="present",
                regions=[_proposal_region("candidate", [0.0, 0.0, 1.0, 1.0])],
            )
        )
        provider.package_id = self.candidate_region_package["package_id"]
        runtime = PdfStructuralRepairRuntimeFactory().create(provider=provider)

        result = runtime.run_candidate_once(
            target_id="guided_candidate_region_full",
            parser_observation=self.observation,
            parser_geometry_observation=self.geometry,
            visual_package=self.candidate_region_package,
            png_bytes=self.png_bytes,
            provider_qualification=runtime.qualify_provider(),
        )

        self.assertEqual(
            "accepted_physical_structure", result["runtime_terminal_status"]
        )
        self.assertEqual((1, 1), (provider.count_calls, provider.generate_calls))
        self.assertEqual(
            "present",
            result["journal"][0]["topology_response"]["table_presence"],
        )
        self.assertTrue(result["post_validation"]["passed"])
        self.assertEqual([], runtime.validate_result(result))

    def test_guided_inputs_classify_transform_tamper_before_provider_calls(
        self,
    ) -> None:
        cases = (
            ("candidate", self.candidate_region_package),
            ("page", self.page_package),
        )
        visual = PdfVisualTopologyFactory().create()
        for label, source_package in cases:
            with self.subTest(scope=label):
                package = copy.deepcopy(source_package)
                package["crop_identity"]["source_to_pixel_transform"][
                    "scale_x"
                ] = 1.5
                _reseal_region_package(package)
                self.assertEqual(
                    ["pdf_visual_topology_coordinate_transform_defect"],
                    visual.validate_region_proposal_package(package),
                )
                provider = _Provider()
                provider.package_id = package["package_id"]
                runtime = PdfStructuralRepairRuntimeFactory().create(
                    provider=provider
                )

                with self.assertRaisesRegex(
                    PdfStructuralRepairRuntimeError,
                    "^pdf_visual_topology_coordinate_transform_defect$",
                ):
                    if label == "candidate":
                        runtime.run_candidate_once(
                            target_id="guided_candidate_transform_tamper",
                            parser_observation=self.observation,
                            parser_geometry_observation=self.geometry,
                            visual_package=package,
                            png_bytes=self.png_bytes,
                            provider_qualification=runtime.qualify_provider(),
                        )
                    else:
                        runtime.run_page_proposal_once(
                            target_id="guided_page_transform_tamper",
                            visual_package=package,
                            png_bytes=self.png_bytes,
                            provider_qualification=runtime.qualify_provider(),
                        )

                self.assertEqual(
                    (0, 0), (provider.count_calls, provider.generate_calls)
                )

    def test_guided_region_bridge_rejects_resealed_text_or_atom_identity_drift(
        self,
    ) -> None:
        cases: list[tuple[str, dict, list[str]]] = []

        text_drift = copy.deepcopy(self.candidate_region_package)
        first_atom = text_drift["model_facing"]["atoms"][0]
        first_candidate_id = text_drift["neutral_atom_to_candidate_id"][
            first_atom["atom_id"]
        ]
        first_atom["text"] = "invented-source-word"
        text_drift["private_candidate_dictionary"][first_candidate_id][
            "exact_source_span"
        ] = "invented-source-word"
        cases.append(("text_drift", _reseal_region_package(text_drift), []))

        identity_drift = copy.deepcopy(self.candidate_region_package)
        neutral_map = identity_drift["neutral_atom_to_candidate_id"]
        first_id = identity_drift["model_facing"]["atoms"][0]["atom_id"]
        second_id = identity_drift["model_facing"]["atoms"][1]["atom_id"]
        neutral_map[first_id], neutral_map[second_id] = (
            neutral_map[second_id],
            neutral_map[first_id],
        )
        dictionary = identity_drift["private_candidate_dictionary"]
        for atom in identity_drift["model_facing"]["atoms"]:
            atom["text"] = dictionary[neutral_map[atom["atom_id"]]][
                "exact_source_span"
            ]
        cases.append(
            (
                "atom_identity_drift",
                _reseal_region_package(identity_drift),
                ["pdf_visual_topology_region_atom_geometry_evidence_invalid"],
            )
        )

        visual = PdfVisualTopologyFactory().create()
        for label, package, expected_visual_errors in cases:
            with self.subTest(case=label):
                self.assertEqual(
                    expected_visual_errors,
                    visual.validate_region_proposal_package(package),
                )
                provider = _Provider()
                provider.package_id = package["package_id"]
                runtime = PdfStructuralRepairRuntimeFactory().create(
                    provider=provider
                )

                with self.assertRaisesRegex(
                    PdfStructuralRepairRuntimeError,
                    "pdf_structural_repair_input_invalid",
                ):
                    runtime.run_candidate_once(
                        target_id=f"guided_candidate_{label}",
                        parser_observation=self.observation,
                        parser_geometry_observation=self.geometry,
                        visual_package=package,
                        png_bytes=self.png_bytes,
                        provider_qualification=runtime.qualify_provider(),
                    )

                self.assertEqual((0, 0), (provider.count_calls, provider.generate_calls))

    def test_guided_candidate_blocks_adjusted_region_before_materialization(
        self,
    ) -> None:
        provider = _ResponseProvider(
            _region_proposal_response(
                "",
                scope="candidate_crop",
                presence="present",
                regions=[_proposal_region("candidate", [0.05, 0.0, 1.0, 1.0])],
            )
        )
        provider.package_id = self.candidate_region_package["package_id"]
        runtime = PdfStructuralRepairRuntimeFactory().create(provider=provider)

        result = runtime.run_candidate_once(
            target_id="guided_candidate_region_adjusted",
            parser_observation=self.observation,
            parser_geometry_observation=self.geometry,
            visual_package=self.candidate_region_package,
            png_bytes=self.png_bytes,
            provider_qualification=runtime.qualify_provider(),
        )

        self.assertEqual("validation_blocked", result["runtime_terminal_status"])
        self.assertEqual((1, 1), (provider.count_calls, provider.generate_calls))
        self.assertIsNone(result["assembly"])
        self.assertIsNone(result["materialization"])
        self.assertIn(
            "pdf_vlm_guided_intake_region_reselection_required",
            result["post_validation"]["reason_codes"],
        )
        self.assertEqual([], runtime.validate_result(result))

    def test_guided_candidate_preserves_ambiguity_without_selecting(self) -> None:
        response = _region_proposal_response(
            "",
            scope="candidate_crop",
            presence="present",
            regions=[_proposal_region("candidate", [0.0, 0.0, 1.0, 1.0])],
        )
        region = response["regions"][0]
        region["hypotheses"].append(
            {
                **copy.deepcopy(region["hypotheses"][0]),
                "hypothesis_key": "alternative",
                "column_boundaries": [0.0, 0.45, 1.0],
            }
        )
        region["uncertainty_codes"] = ["column_boundary_ambiguous"]
        provider = _ResponseProvider(response)
        provider.package_id = self.candidate_region_package["package_id"]
        runtime = PdfStructuralRepairRuntimeFactory().create(provider=provider)

        result = runtime.run_candidate_once(
            target_id="guided_candidate_ambiguous",
            parser_observation=self.observation,
            parser_geometry_observation=self.geometry,
            visual_package=self.candidate_region_package,
            png_bytes=self.png_bytes,
            provider_qualification=runtime.qualify_provider(),
        )

        self.assertEqual("proposal_ambiguous", result["runtime_terminal_status"])
        self.assertEqual((1, 1), (provider.count_calls, provider.generate_calls))
        self.assertIsNone(result["accepted_binding"])
        self.assertIsNone(result["materialization"])
        self.assertFalse(result["post_validation"]["passed"])
        self.assertEqual([], runtime.validate_result(result))

    def test_guided_candidate_count_budget_is_one_count_and_zero_generate(self) -> None:
        provider = _Provider(counted_tokens=20_001)
        provider.package_id = self.candidate_region_package["package_id"]
        runtime = PdfStructuralRepairRuntimeFactory().create(provider=provider)

        result = runtime.run_candidate_once(
            target_id="guided_candidate_budget",
            parser_observation=self.observation,
            parser_geometry_observation=self.geometry,
            visual_package=self.candidate_region_package,
            png_bytes=self.png_bytes,
            provider_qualification=runtime.qualify_provider(),
        )

        self.assertEqual("preflight_blocked", result["runtime_terminal_status"])
        self.assertEqual((1, 0), (provider.count_calls, provider.generate_calls))
        self.assertEqual(1, result["new_provider_count_token_calls"])
        self.assertEqual(0, result["new_provider_generate_calls"])
        self.assertEqual([], runtime.validate_result(result))

    def test_guided_candidate_rejects_more_than_1000_atoms_before_calls(
        self,
    ) -> None:
        oversized = copy.deepcopy(self.candidate_region_package)
        source_atoms = oversized["model_facing"]["atoms"]
        source_map = oversized["neutral_atom_to_candidate_id"]
        dictionary = oversized["private_candidate_dictionary"]
        atoms: list[dict] = []
        neutral_map: dict[str, str] = {}
        for order in range(1_001):
            source_atom = source_atoms[order % len(source_atoms)]
            source_candidate_id = source_map[source_atom["atom_id"]]
            atom_id = f"a{order + 1:04d}"
            atoms.append(
                {
                    "atom_id": atom_id,
                    "bbox": copy.deepcopy(source_atom["bbox"]),
                    "order": order,
                    "text": dictionary[source_candidate_id]["exact_source_span"],
                }
            )
            neutral_map[atom_id] = source_candidate_id
        oversized["model_facing"]["atoms"] = atoms
        oversized["neutral_atom_to_candidate_id"] = neutral_map
        oversized["component_accounting"]["atom_count"] = len(atoms)
        oversized = _reseal_region_package(oversized)

        visual_errors = (
            PdfVisualTopologyFactory()
            .create()
            .validate_region_proposal_package(oversized)
        )
        self.assertIn("pdf_visual_topology_atom_budget_exceeded", visual_errors)
        provider = _Provider()
        provider.package_id = oversized["package_id"]
        runtime = PdfStructuralRepairRuntimeFactory().create(provider=provider)

        with self.assertRaisesRegex(
            PdfStructuralRepairRuntimeError,
            "pdf_structural_repair_input_invalid",
        ):
            runtime.run_candidate_once(
                target_id="guided_candidate_1001_atoms",
                parser_observation=self.observation,
                parser_geometry_observation=self.geometry,
                visual_package=oversized,
                png_bytes=self.png_bytes,
                provider_qualification=runtime.qualify_provider(),
            )

        self.assertEqual((0, 0), (provider.count_calls, provider.generate_calls))

    def test_guided_candidate_reconciles_cutting_boundary_to_unique_gap(
        self,
    ) -> None:
        response = _region_proposal_response(
            "",
            scope="candidate_crop",
            presence="present",
            regions=[_proposal_region("candidate", [0.0, 0.0, 1.0, 1.0])],
        )
        response["regions"][0]["hypotheses"][0]["column_boundaries"] = [
            0.0,
            0.3,
            1.0,
        ]
        provider = _ResponseProvider(response)
        provider.package_id = self.candidate_region_package["package_id"]
        runtime = PdfStructuralRepairRuntimeFactory().create(provider=provider)
        projection_without_rulings = copy.deepcopy(self.projection)
        projection_without_rulings["vector_line_inventory"] = []
        geometry_without_rulings = (
            PdfParserGeometryFactory()
            .create()
            .build_observation(
                document_ref="document-1",
                pdf_sha256="pdf-sha",
                page_ref="page-1",
                page_number=1,
                table_ref="table-1",
                table_bbox=[0.0, 0.0, 200.0, 100.0],
                pdf_text_layer_projection=projection_without_rulings,
            )
        )

        result = runtime.run_candidate_once(
            target_id="guided_candidate_crossing_atom",
            parser_observation=self.observation,
            parser_geometry_observation=geometry_without_rulings,
            visual_package=self.candidate_region_package,
            png_bytes=self.png_bytes,
            provider_qualification=runtime.qualify_provider(),
        )

        self.assertEqual(
            "accepted_physical_structure", result["runtime_terminal_status"]
        )
        self.assertEqual((1, 1), (provider.count_calls, provider.generate_calls))
        self.assertIsNotNone(result["materialization"])
        self.assertTrue(result["post_validation"]["passed"])
        adjustment = next(
            item
            for item in result["assembly"]["structural_adjustments"]
            if item.get("evidence_basis") == "unique_positive_source_atom_gap"
        )
        self.assertEqual("column", adjustment["axis"])
        self.assertEqual(0.3, adjustment["before"])
        self.assertEqual(0.5, adjustment["after"])
        self.assertTrue(adjustment["candidate_assignment_preserved"])
        self.assertEqual([], runtime.validate_result(result))

    def test_counted_input_budget_blocks_before_generate(self) -> None:
        provider = _Provider(counted_tokens=20_001)
        provider.package_id = self.package["package_id"]
        runtime = PdfStructuralRepairRuntimeFactory().create(provider=provider)

        result = runtime.run_target(
            target_id="regression_oversized",
            parser_observation=self.observation,
            parser_geometry_observation=self.geometry,
            visual_package=self.package,
            png_bytes=self.png_bytes,
            provider_qualification=runtime.qualify_provider(),
        )

        self.assertEqual("preflight_blocked", result["runtime_terminal_status"])
        self.assertEqual(1, provider.count_calls)
        self.assertEqual(0, provider.generate_calls)
        self.assertEqual(
            ["pdf_structural_repair_counted_input_budget_exceeded"],
            result["safe_summary"]["reason_codes"],
        )

    def test_provider_budget_error_preserves_safe_observed_count(self) -> None:
        provider = _BudgetErrorProvider()
        provider.package_id = self.package["package_id"]
        runtime = PdfStructuralRepairRuntimeFactory().create(provider=provider)

        result = runtime.run_target(
            target_id="provider_budget_detail",
            parser_observation=self.observation,
            parser_geometry_observation=self.geometry,
            visual_package=self.package,
            png_bytes=self.png_bytes,
            provider_qualification=runtime.qualify_provider(),
        )

        self.assertEqual("preflight_blocked", result["runtime_terminal_status"])
        self.assertEqual(0, provider.generate_calls)
        self.assertEqual([21_337], result["safe_summary"]["counted_input_tokens"])
        self.assertEqual(
            21_337,
            result["journal"][0]["count_tokens"]["total_tokens"],
        )
        self.assertFalse(result["journal"][0]["count_tokens"]["within_hard_guard"])

    def test_private_provider_response_is_not_copied_to_safe_summary(self) -> None:
        provider = _Provider()
        provider.package_id = self.package["package_id"]
        runtime = PdfStructuralRepairRuntimeFactory().create(provider=provider)
        result = runtime.run_target(
            target_id="regression_private_boundary",
            parser_observation=self.observation,
            parser_geometry_observation=self.geometry,
            visual_package=self.package,
            png_bytes=self.png_bytes,
            provider_qualification=runtime.qualify_provider(),
        )

        self.assertIn("provider-boundary", repr(result["journal"]))
        self.assertNotIn("provider-boundary", repr(result["safe_summary"]))
        self.assertNotIn("alpha-private", repr(result["safe_summary"]))

    def test_result_checksum_and_safe_ref_fail_closed(self) -> None:
        provider = _Provider()
        provider.package_id = self.package["package_id"]
        runtime = PdfStructuralRepairRuntimeFactory().create(provider=provider)
        result = runtime.run_target(
            target_id="regression_checksum",
            parser_observation=self.observation,
            parser_geometry_observation=self.geometry,
            visual_package=self.package,
            png_bytes=self.png_bytes,
            provider_qualification=runtime.qualify_provider(),
        )
        tampered = copy.deepcopy(result)
        tampered["safe_summary"]["generate_calls"] = 99

        self.assertIn(
            "pdf_structural_repair_result_checksum_invalid",
            runtime.validate_result(tampered),
        )

    def test_runtime_constructor_requires_factory(self) -> None:
        self.assertIn("PdfStructuralRepairRuntimeFactory.create", FACTORY_REQUIRED)
        self.assertIn("one-call page proposal", FACTORY_REQUIRED)
        self.assertIn(
            "continuation groups must not trigger new provider calls", FORBIDDEN
        )
        self.assertIn("page proposals must not consume parser atoms", FORBIDDEN)
        with self.assertRaisesRegex(
            PdfStructuralRepairRuntimeError,
            "pdf_structural_repair_runtime_factory_required",
        ):
            PdfStructuralRepairRuntime(
                PdfStructuralRepairRuntimeConfig(),
                provider=_Provider(),
            )

    def test_runtime_factory_rejects_any_hard_budget_override(self) -> None:
        for field, value in (
            ("maximum_counted_input_tokens", 30_000),
            ("maximum_output_tokens", 9_000),
            ("maximum_visible_output_bytes", 600_000),
            ("maximum_provider_response_bytes", 3_000_000),
            ("maximum_image_bytes", 9_000_000),
        ):
            with self.subTest(field=field), self.assertRaisesRegex(
                PdfStructuralRepairRuntimeError,
                "pdf_structural_repair_runtime_config_invalid",
            ):
                PdfStructuralRepairRuntimeFactory(
                    PdfStructuralRepairRuntimeConfig(**{field: value})
                ).create(provider=_Provider())

    def test_continuation_group_joins_two_accepted_fragments_without_provider_calls(
        self,
    ) -> None:
        provider = _Provider()
        runtime = PdfStructuralRepairRuntimeFactory().create(provider=provider)
        provider.package_id = self.package["package_id"]
        first = runtime.run_target(
            target_id="continuation_fragment_1",
            parser_observation=self.observation,
            parser_geometry_observation=self.geometry,
            visual_package=self.package,
            png_bytes=self.png_bytes,
            provider_qualification=runtime.qualify_provider(),
        )

        second_projection = _projection(
            page_ref="page-2",
            values=(
                ("epsilon-private", [10.0, 10.0, 90.0, 40.0]),
                ("zeta-private", [110.0, 10.0, 190.0, 40.0]),
                ("eta-private", [10.0, 60.0, 90.0, 90.0]),
                ("theta-private", [110.0, 60.0, 190.0, 90.0]),
            ),
        )
        contracts = PdfDualOracleContractFactory().create()
        second_observation = contracts.build_parser_observation_from_word_atoms(
            document_ref="document-1",
            pdf_sha256="pdf-sha",
            page_ref="page-2",
            page_number=2,
            table_ref="table-2",
            table_bbox=[0.0, 0.0, 200.0, 100.0],
            pdf_text_layer_projection=second_projection,
        )
        second_geometry = (
            PdfParserGeometryFactory()
            .create()
            .build_observation(
                document_ref="document-1",
                pdf_sha256="pdf-sha",
                page_ref="page-2",
                page_number=2,
                table_ref="table-2",
                table_bbox=[0.0, 0.0, 200.0, 100.0],
                pdf_text_layer_projection=second_projection,
            )
        )
        second_png = b"lossless-test-png-page-2"
        second_package = (
            PdfVisualTopologyFactory()
            .create()
            .build_package(
                parser_observation=second_observation,
                crop_manifest=_crop_manifest(
                    second_png,
                    crop_id="crop-2",
                    page_number=2,
                    table_ref="table-2",
                ),
            )
        )
        provider.package_id = second_package["package_id"]
        second = runtime.run_target(
            target_id="continuation_fragment_2",
            parser_observation=second_observation,
            parser_geometry_observation=second_geometry,
            visual_package=second_package,
            png_bytes=second_png,
            provider_qualification=runtime.qualify_provider(),
        )
        calls_before_join = (provider.count_calls, provider.generate_calls)

        joined = runtime.run_continuation_group(
            continuation_group_id="continuation_group_1_2",
            fragments=[
                {
                    "target_id": "continuation_fragment_1",
                    "parser_observation": self.observation,
                    "visual_package": self.package,
                    "runtime_result": first,
                    "repeat_history_ever_conflicted": False,
                },
                {
                    "target_id": "continuation_fragment_2",
                    "parser_observation": second_observation,
                    "visual_package": second_package,
                    "runtime_result": second,
                    "repeat_history_ever_conflicted": False,
                },
            ],
        )

        self.assertEqual((4, 4), calls_before_join)
        self.assertEqual(
            calls_before_join, (provider.count_calls, provider.generate_calls)
        )
        self.assertEqual(
            "accepted_supplied_consensus", joined["runtime_terminal_status"]
        )
        self.assertEqual(0, joined["new_provider_count_token_calls"])
        self.assertEqual(0, joined["new_provider_generate_calls"])
        self.assertEqual(2, len(joined["fragment_evidence"]))
        self.assertEqual(
            "broker_reports_pdf_dual_oracle_continuation_consensus_v2",
            joined["continuation_consensus_result"]["schema_version"],
        )
        self.assertEqual(4, joined["materialization"]["row_count"])
        self.assertEqual(2, joined["materialization"]["column_count"])
        self.assertTrue(joined["materialization"]["candidate_ownership_exact"])
        self.assertEqual(0, joined["materialization"]["model_invented_values_total"])
        self.assertTrue(joined["safe_summary"]["all_candidates_accounted"])
        self.assertNotIn("alpha-private", repr(joined["safe_summary"]))
        self.assertNotIn("epsilon-private", repr(joined["safe_summary"]))
        self.assertEqual([], runtime.validate_continuation_group_result(joined))


def _topology_response(package_id: str) -> dict:
    return {
        "schema_version": PDF_VISUAL_TOPOLOGY_RESPONSE_SCHEMA,
        "package_id": package_id,
        "decision": "bound",
        "alternatives_complete": True,
        "hypotheses": [
            {
                "hypothesis_key": "primary",
                "row_boundaries": [0.0, 0.5, 1.0],
                "column_boundaries": [0.0, 0.5, 1.0],
                "header_row_count": 1,
                "spans": [],
                "header_hierarchy": [],
                "continuation_required": False,
                "uncertainty_codes": [],
            }
        ],
        "uncertainty_codes": [],
    }


def _region_proposal_response(
    package_id: str,
    *,
    scope: str,
    presence: str,
    regions: list[dict],
) -> dict:
    return {
        "schema_version": PDF_VISUAL_TOPOLOGY_RESPONSE_SCHEMA,
        "contract_revision": PDF_VISUAL_TOPOLOGY_REGION_PROPOSAL_REVISION,
        "package_id": package_id,
        "proposal_scope": scope,
        "table_presence": presence,
        "alternatives_complete": True,
        "regions": regions,
        "uncertainty_codes": [],
    }


def _proposal_region(key: str, bbox: list[float]) -> dict:
    return {
        "region_key": key,
        "bbox": bbox,
        "border_evidence": "alignment_based",
        "density": "mixed",
        "continuation_likelihood": "unlikely",
        "hypotheses": [
            {
                "hypothesis_key": "primary",
                "row_boundaries": [0.0, 0.5, 1.0],
                "column_boundaries": [0.0, 0.5, 1.0],
                "header_row_count": 1,
                "spans": [],
                "header_hierarchy": [],
                "continuation_required": False,
                "uncertainty_codes": [],
            }
        ],
        "uncertainty_codes": [],
    }


def _reseal_region_package(package: dict) -> dict:
    atoms = package["model_facing"]["atoms"]
    atom_manifest_hash = sha256_json(atoms)
    package["neutral_atom_manifest_hash"] = atom_manifest_hash
    package["candidate_dictionary_hash"] = sha256_json(
        package["private_candidate_dictionary"]
    )
    package_id = "pdfvisualregionpkg_" + stable_digest(
        [
            package["pdf_sha256"],
            package["page_number"],
            package["crop_identity"]["manifest_hash"],
            package["proposal_scope"],
            atom_manifest_hash,
            package["policy_version"],
            PDF_VISUAL_TOPOLOGY_REGION_PROPOSAL_REVISION,
        ],
        length=24,
    )
    package["package_id"] = package_id
    package["model_facing"]["identity"] = {"package_id": package_id}
    model_bytes = len(canonical_json_bytes(package["model_facing"]))
    schema_bytes = len(canonical_json_bytes(package["output_schema"]))
    package["component_accounting"]["model_json_bytes"] = model_bytes
    package["component_accounting"]["schema_json_bytes"] = schema_bytes
    package["component_accounting"]["static_input_token_estimate"] = (
        model_bytes + schema_bytes + 3
    ) // 4
    package.pop("package_hash", None)
    package["package_hash"] = sha256_json(package)
    return package


def _projection(
    *,
    page_ref: str = "page-1",
    values: tuple[tuple[str, list[float]], ...] = (
        ("alpha-private", [10.0, 10.0, 90.0, 40.0]),
        ("beta-private", [110.0, 10.0, 190.0, 40.0]),
        ("gamma-private", [10.0, 60.0, 90.0, 90.0]),
        ("delta-private", [110.0, 60.0, 190.0, 90.0]),
    ),
) -> dict:
    bboxes = []
    words = []
    for ordinal, (text, bbox) in enumerate(values, start=1):
        bbox_ref = f"bbox-{ordinal}"
        bboxes.append({"bbox_ref": bbox_ref, "bbox": list(bbox)})
        words.append(
            {
                "parser_ordinal": ordinal,
                "word_ref": f"word-{ordinal}",
                "page_ref": page_ref,
                "bbox_ref": bbox_ref,
                "text": text,
                "geometry_reading_order": ordinal,
                "text_checksum_ref": f"text-checksum-{ordinal}",
                "source_value_ref": f"source-{ordinal}",
            }
        )
    vector_specs = (
        [0.0, 0.0, 0.0, 100.0],
        [100.0, 0.0, 100.0, 100.0],
        [200.0, 0.0, 200.0, 100.0],
        [0.0, 0.0, 200.0, 0.0],
        [0.0, 50.0, 200.0, 50.0],
        [0.0, 100.0, 200.0, 100.0],
    )
    vectors = []
    for ordinal, bbox in enumerate(vector_specs, start=1):
        bbox_ref = f"vector-bbox-{ordinal}"
        bboxes.append({"bbox_ref": bbox_ref, "bbox": list(bbox)})
        vectors.append(
            {
                "parser_ordinal": ordinal,
                "object_ref": f"vector-{ordinal}",
                "page_ref": page_ref,
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
    png_bytes: bytes,
    *,
    crop_id: str = "crop-1",
    page_number: int = 1,
    table_ref: str = "table-1",
) -> dict:
    value = {
        "schema_version": "broker_reports_pdf_table_crop_v1",
        "policy_version": "pdf_table_raster_policy_v1",
        "crop_id": crop_id,
        "document_ref": "document-1",
        "pdf_sha256": "pdf-sha",
        "page_number": page_number,
        "table_ref": table_ref,
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
        "png_bytes": len(png_bytes),
        "png_sha256": hashlib.sha256(png_bytes).hexdigest(),
        "lossless": True,
        "silent_resize_performed": False,
    }
    value["manifest_hash"] = sha256_json(value)
    return value


if __name__ == "__main__":
    unittest.main()
