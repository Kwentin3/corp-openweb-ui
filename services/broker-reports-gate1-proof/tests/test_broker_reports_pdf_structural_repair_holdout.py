from __future__ import annotations

import base64
import copy
import hashlib
import importlib.util
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

from broker_reports_gate1.pdf_dual_oracle_contracts import (
    PdfDualOracleContractFactory,
)
from broker_reports_gate1.pdf_grid_experiment_provider import (
    PdfGridProviderConfig,
    PdfGridProviderError,
)
from broker_reports_gate1.pdf_hybrid_contracts import sha256_json
from broker_reports_gate1.pdf_parser_geometry import PdfParserGeometryFactory
from broker_reports_gate1.pdf_structural_repair_holdout_contracts import (
    PDF_STRUCTURAL_HOLDOUT_CORPUS_POLICIES,
    PDF_STRUCTURAL_HOLDOUT_ELIGIBILITY_POLICY_CHECKSUM,
    PDF_STRUCTURAL_HOLDOUT_ELIGIBILITY_POLICY_V5,
    PDF_STRUCTURAL_HOLDOUT_ELIGIBILITY_POLICY_V5_CHECKSUM,
    PDF_STRUCTURAL_HOLDOUT_JOURNAL_SCHEMA,
    PDF_STRUCTURAL_HOLDOUT_POLICY_VERSION_V2,
    PDF_STRUCTURAL_HOLDOUT_PREREGISTRATION_SCHEMA,
    PDF_STRUCTURAL_HOLDOUT_PREREGISTRATION_SCHEMA_V2,
    PDF_STRUCTURAL_HOLDOUT_PREREGISTRATION_SCHEMA_V3,
    PDF_STRUCTURAL_HOLDOUT_TERMINAL_SCHEMA,
    PDF_STRUCTURAL_HOLDOUT_TERMINAL_SCHEMA_V2,
    PDF_STRUCTURAL_HOLDOUT_TERMINAL_SCHEMA_V3,
    PDF_STRUCTURAL_HOLDOUT_WINDOW_JOURNAL_SCHEMA,
    PdfStructuralRepairHoldoutConfig,
    PdfStructuralRepairHoldoutContractError,
    PdfStructuralRepairHoldoutContractFactory,
    PdfStructuralRepairHoldoutContractRuntime,
)
from broker_reports_gate1.pdf_structural_repair_runtime import (
    PdfStructuralRepairRuntimeFactory,
)
from broker_reports_gate1.pdf_visual_topology import (
    PDF_VISUAL_TOPOLOGY_RESPONSE_SCHEMA,
    PdfVisualTopologyFactory,
)
from tests.test_broker_reports_pdf_layout_slice2 import _pdf_bytes


class _StrictWindowProvider:
    """External-provider boundary fixture; runtime and holdout logic stay real."""

    def __init__(self) -> None:
        self.count_calls = 0
        self.generate_calls = 0
        self.provider_package_ids: list[str] = []
        self.counted_tokens = 500

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

    def count_tokens(
        self,
        *,
        model_view: dict,
        output_schema: dict,
        crop_sha256: str,
        **_: object,
    ) -> dict:
        self.count_calls += 1
        self.provider_package_ids.append(model_view["identity"]["package_id"])
        schema_hash = sha256_json(output_schema)
        return {
            "total_tokens": self.counted_tokens,
            "prompt_tokens_details": [],
            "http_status": 200,
            "request_hash": sha256_json(
                {"model_view": model_view, "crop_sha256": crop_sha256}
            ),
            "response_hash": hashlib.sha256(b"count-response").hexdigest(),
            "canonical_schema_hash": schema_hash,
            "adapted_schema_hash": schema_hash,
            "schema_transform_count": 0,
            "model_requested": "models/gemini-3.5-flash",
            "transport_identity": (
                "gemini_count_tokens_generate_content_request"
            ),
            "within_hard_guard": True,
        }

    def invoke(
        self,
        *,
        task_id: str,
        model_view: dict,
        output_schema: dict,
        crop_sha256: str,
        attempt_number: int,
        attempt_lineage: list[str],
        **_: object,
    ) -> dict:
        self.generate_calls += 1
        package_id = model_view["identity"]["package_id"]
        self.provider_package_ids.append(package_id)
        window = model_view["window"]
        window_index = int(window["window_index"])
        core_y = window["core_y_normalized_in_crop"]
        rows = (
            [0.0, core_y[1], 1.0]
            if window_index == 1
            else [0.0, core_y[0], 1.0]
        )
        topology = _window_response(
            package_id=package_id,
            header_row_count=1 if window_index == 1 else 0,
            rows=rows,
        )
        schema_hash = sha256_json(output_schema)
        attempt_id = f"{task_id}_a{attempt_number}"
        attempt = {
            "task_id": task_id,
            "attempt_id": attempt_id,
            "attempt_number": attempt_number,
            "attempt_lineage": list(attempt_lineage),
            "provider": "google",
            "provider_profile": "google_gemini",
            "provider_profile_revision": "fixture-revision",
            "model_requested": "models/gemini-3.5-flash",
            "model_resolved": "models/gemini-3.5-flash",
            "adapter_identity": "fixture-adapter-v1",
            "transport_identity": (
                "gemini_generate_content_native_table_crop_json_schema"
            ),
            "request_hash": sha256_json(
                {
                    "task_id": task_id,
                    "attempt_number": attempt_number,
                    "crop_sha256": crop_sha256,
                }
            ),
            "crop_sha256": crop_sha256,
            "model_view_hash": sha256_json(model_view),
            "canonical_schema_hash": schema_hash,
            "adapted_schema_hash": schema_hash,
            "schema_transform_count": 0,
            "started_at": f"2026-07-14T00:00:0{attempt_number}+00:00",
            "ended_at": f"2026-07-14T00:00:1{attempt_number}+00:00",
            "duration_ms": 1.0,
            "http_status": 200,
            "provider_response_id": f"fixture-{attempt_id}",
            "usage": {
                "input_tokens": self.counted_tokens,
                "output_tokens": 20,
                "total_tokens": self.counted_tokens + 20,
            },
            "finish_reason": "STOP",
            "thinking_level": "minimal",
            "parse_result": "parsed_object",
            "terminal_failure_class": None,
            "hidden_retry": False,
            "provider_failover": False,
        }
        response_hash = sha256_json(topology)
        return {
            "attempt": attempt,
            "json_output": topology,
            "text": "",
            "raw_private_response": {"fixture": True},
            "response_bytes": 200,
            "response_hash": response_hash,
            "visible_output_bytes": 100,
            "visible_output_hash": response_hash,
        }


class _FirstAttemptInvalidWindowProvider(_StrictWindowProvider):
    """One semantic miss in attempt one; attempt two remains stitchable."""

    def invoke(self, **kwargs: object) -> dict:
        result = super().invoke(**kwargs)
        model_view = kwargs["model_view"]
        if (
            kwargs["attempt_number"] == 1
            and model_view["window"]["window_index"] == 1
        ):
            topology = copy.deepcopy(result["json_output"])
            topology["hypotheses"][0]["continuation_required"] = True
            response_hash = sha256_json(topology)
            result["json_output"] = topology
            result["response_hash"] = response_hash
            result["visible_output_hash"] = response_hash
        return result


class PdfStructuralRepairHoldoutContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runtime = PdfStructuralRepairHoldoutContractFactory().create()
        self.preregistration = _preregistration(self.runtime)
        self.preregistration_file_sha256 = hashlib.sha256(
            b"canonical-preregistration-file"
        ).hexdigest()

    def test_factory_is_the_only_runtime_entrypoint(self) -> None:
        with self.assertRaisesRegex(
            PdfStructuralRepairHoldoutContractError,
            "pdf_structural_holdout_factory_required",
        ):
            PdfStructuralRepairHoldoutContractRuntime(
                PdfStructuralRepairHoldoutConfig()
            )

    def test_valid_preregistration_and_typed_terminal_are_closed_and_linked(
        self,
    ) -> None:
        terminal = _terminal(
            self.runtime,
            self.preregistration,
            self.preregistration_file_sha256,
        )

        self.assertEqual(
            [], self.runtime.validate_preregistration(self.preregistration)
        )
        self.assertEqual([], self.runtime.validate_terminal(terminal))
        self.assertEqual(
            [],
            self.runtime.validate_terminal_against_preregistration(
                terminal=terminal,
                preregistration=self.preregistration,
                preregistration_file_sha256=self.preregistration_file_sha256,
            ),
        )
        self.assertTrue(
            all(
                target["consensus_result"]["terminal_status"]
                == "blocked_no_valid_evidence"
                and target["accepted_binding"] is None
                and target["materialization"] is None
                for target in terminal["targets"].values()
            )
        )

    def test_330_atom_holdout_freezes_two_windows_and_executes_exact_4_plus_4(
        self,
    ) -> None:
        (
            observation,
            geometry,
            full_package,
            plan,
            window_inputs,
        ) = _windowed_330_fixture()
        execution = self.runtime.build_target_execution_contract(
            parser_observation=observation,
            visual_package=full_package,
            window_plan=plan,
            window_inputs=window_inputs,
        )

        self.assertEqual("vertical_atom_windows", execution["execution_mode"])
        self.assertEqual(330, execution["candidate_atoms"])
        self.assertEqual(2, execution["window_count"])
        self.assertEqual(4, execution["expected_count_token_calls"])
        self.assertEqual(4, execution["expected_generate_calls"])
        self.assertFalse(execution["hidden_retry_allowed"])
        self.assertFalse(execution["provider_failover_allowed"])
        self.assertFalse(execution["column_splitting_allowed"])
        self.assertFalse(execution["reference_or_source_values_consumed"])
        self.assertTrue(
            all(
                item["full_width"] is True
                for item in execution["window_inputs"]
            )
        )
        self.assertEqual(
            [item["window_package"]["package_hash"] for item in window_inputs],
            [item["package_hash"] for item in execution["window_inputs"]],
        )
        self.assertEqual(
            [
                item["window_package"]["crop_identity"]["crop_sha256"]
                for item in window_inputs
            ],
            [item["crop_sha256"] for item in execution["window_inputs"]],
        )

        provider = _StrictWindowProvider()
        structural_runtime = PdfStructuralRepairRuntimeFactory().create(
            provider=provider
        )
        result = structural_runtime.run_windowed_target(
            target_id="holdout_001",
            parser_observation=observation,
            parser_geometry_observation=geometry,
            visual_package=full_package,
            window_plan=plan,
            window_inputs=window_inputs,
            provider_qualification=structural_runtime.qualify_provider(),
        )
        runner = _load_script_module(
            "local_pdf_structural_repair_holdout.py"
        )
        holdout_journal = runner._holdout_window_journal(result)
        consensus = result.get("consensus_result")
        if not isinstance(consensus, dict):
            consensus = runner._window_fallback_consensus(
                target_id="holdout_001",
                window_result=result,
            )
        hypothesis_set = result.get("hypothesis_set")
        if not isinstance(hypothesis_set, dict):
            hypothesis_set = {
                "windowed_runtime_terminal_status": result.get(
                    "runtime_terminal_status"
                )
            }
        repeatability = result.get("repeatability")
        if not isinstance(repeatability, dict):
            repeatability = {"passed": False}

        self.assertEqual((4, 4), (provider.count_calls, provider.generate_calls))
        self.assertEqual(4, result["new_provider_count_token_calls"])
        self.assertEqual(4, result["new_provider_generate_calls"])
        self.assertEqual(2, len(result["window_stitches"]))
        self.assertTrue(
            all(
                stitch["attempts_mixed"] is False
                and all(
                    attempt_id.endswith(
                        f"_a{stitch['attempt_number']}"
                    )
                    for attempt_id in stitch["window_attempt_ids"]
                )
                for stitch in result["window_stitches"]
            )
        )
        self.assertEqual(4, len(holdout_journal))
        self.assertTrue(
            all(
                item["schema_version"]
                == PDF_STRUCTURAL_HOLDOUT_WINDOW_JOURNAL_SCHEMA
                and item["provider_count_token_call_performed"] is True
                and item["provider_generate_call_performed"] is True
                for item in holdout_journal
            )
        )
        self.assertNotIn(
            full_package["package_id"], provider.provider_package_ids
        )

        terminal = _terminal(
            self.runtime,
            self.preregistration,
            self.preregistration_file_sha256,
        )
        target = terminal["targets"]["holdout_001"]
        target.update(
            {
                "parser_observation": observation,
                "parser_geometry_observation": geometry,
                "visual_package": full_package,
                "assemblies": [
                    item["assembly"]
                    for item in holdout_journal
                    if isinstance(item.get("assembly"), dict)
                ],
                "hypothesis_set": hypothesis_set,
                "repeatability": repeatability,
                "consensus_result": consensus,
                "accepted_binding": result["accepted_binding"],
                "materialization": result["materialization"],
                "execution_contract": execution,
                "window_stitches": result["window_stitches"],
                "window_runtime_result_checksum": result["result_checksum"],
            }
        )
        terminal["journal"] = holdout_journal + terminal["journal"][2:]
        terminal["new_provider_count_token_calls"] = 6
        terminal["new_provider_generate_calls"] = 4
        terminal["expected_provider_count_token_calls"] = 8
        terminal["expected_provider_generate_calls"] = 8
        _refresh_terminal(self.runtime, terminal)
        self.assertEqual([], self.runtime.validate_terminal(terminal))

    def test_terminal_accepts_attempt_two_only_window_stitch(self) -> None:
        (
            observation,
            geometry,
            full_package,
            plan,
            window_inputs,
        ) = _windowed_330_fixture()
        execution = self.runtime.build_target_execution_contract(
            parser_observation=observation,
            visual_package=full_package,
            window_plan=plan,
            window_inputs=window_inputs,
        )
        provider = _FirstAttemptInvalidWindowProvider()
        structural_runtime = PdfStructuralRepairRuntimeFactory().create(
            provider=provider
        )
        result = structural_runtime.run_windowed_target(
            target_id="holdout_001",
            parser_observation=observation,
            parser_geometry_observation=geometry,
            visual_package=full_package,
            window_plan=plan,
            window_inputs=window_inputs,
            provider_qualification=structural_runtime.qualify_provider(),
        )
        runner = _load_script_module(
            "local_pdf_structural_repair_holdout.py"
        )
        holdout_journal = runner._holdout_window_journal(result)

        self.assertEqual((4, 4), (provider.count_calls, provider.generate_calls))
        self.assertEqual(
            [2],
            [item["attempt_number"] for item in result["window_stitches"]],
        )
        consensus = result.get("consensus_result")
        if not isinstance(consensus, dict):
            consensus = runner._window_fallback_consensus(
                target_id="holdout_001",
                window_result=result,
            )
        hypothesis_set = result.get("hypothesis_set")
        if not isinstance(hypothesis_set, dict):
            hypothesis_set = {
                "windowed_runtime_terminal_status": result.get(
                    "runtime_terminal_status"
                )
            }
        repeatability = result.get("repeatability")
        if not isinstance(repeatability, dict):
            repeatability = {"passed": False}

        terminal = _terminal(
            self.runtime,
            self.preregistration,
            self.preregistration_file_sha256,
        )
        target = terminal["targets"]["holdout_001"]
        target.update(
            {
                "parser_observation": observation,
                "parser_geometry_observation": geometry,
                "visual_package": full_package,
                "assemblies": [
                    item["assembly"]
                    for item in holdout_journal
                    if isinstance(item.get("assembly"), dict)
                ],
                "hypothesis_set": hypothesis_set,
                "repeatability": repeatability,
                "consensus_result": consensus,
                "accepted_binding": result["accepted_binding"],
                "materialization": result["materialization"],
                "execution_contract": execution,
                "window_stitches": result["window_stitches"],
                "window_runtime_result_checksum": result["result_checksum"],
            }
        )
        terminal["journal"] = holdout_journal + terminal["journal"][2:]
        terminal["new_provider_count_token_calls"] = 6
        terminal["new_provider_generate_calls"] = 4
        terminal["expected_provider_count_token_calls"] = 8
        terminal["expected_provider_generate_calls"] = 8
        _refresh_terminal(self.runtime, terminal)

        self.assertEqual([], self.runtime.validate_terminal(terminal))

    def test_tampered_window_plan_or_package_hash_blocks_before_provider(self) -> None:
        observation, _, full_package, plan, window_inputs = (
            _windowed_330_fixture()
        )
        execution = self.runtime.build_target_execution_contract(
            parser_observation=observation,
            visual_package=full_package,
            window_plan=plan,
            window_inputs=window_inputs,
        )
        provider = _StrictWindowProvider()

        tampered_plan = copy.deepcopy(execution)
        tampered_plan["window_plan"]["plan_hash"] = "forged"
        tampered_plan["plan_hash"] = "forged"
        _refresh_execution_contract_checksum(tampered_plan)
        self.assertIn(
            "pdf_structural_holdout_window_plan_invalid",
            self.runtime.validate_target_execution_contract(
                parser_observation=observation,
                visual_package=full_package,
                contract=tampered_plan,
            ),
        )

        tampered_package = copy.deepcopy(execution)
        frozen = tampered_package["window_inputs"][0]
        frozen["window_package"]["package_hash"] = hashlib.sha256(
            b"forged-window-package"
        ).hexdigest()
        frozen["package_hash"] = frozen["window_package"]["package_hash"]
        _refresh_execution_contract_checksum(tampered_package)
        self.assertIn(
            "pdf_structural_holdout_window_input_invalid",
            self.runtime.validate_target_execution_contract(
                parser_observation=observation,
                visual_package=full_package,
                contract=tampered_package,
            ),
        )
        self.assertEqual((0, 0), (provider.count_calls, provider.generate_calls))

    def test_192_or_fewer_keeps_two_call_whole_path_and_legacy_v1_v2_validate(
        self,
    ) -> None:
        self.assertTrue(
            all(
                target["execution_contract"]["execution_mode"]
                == "whole_table"
                and target["execution_contract"]["window_count"] == 1
                and target["execution_contract"]["expected_generate_calls"]
                == 2
                for target in self.preregistration["targets"]
            )
        )

        for execution_class, prereg_schema, terminal_schema in (
            (
                "fresh_holdout",
                PDF_STRUCTURAL_HOLDOUT_PREREGISTRATION_SCHEMA,
                PDF_STRUCTURAL_HOLDOUT_TERMINAL_SCHEMA,
            ),
            (
                "fresh_holdout_v2",
                PDF_STRUCTURAL_HOLDOUT_PREREGISTRATION_SCHEMA_V2,
                PDF_STRUCTURAL_HOLDOUT_TERMINAL_SCHEMA_V2,
            ),
        ):
            current = _preregistration(
                self.runtime, execution_class=execution_class
            )
            legacy = _legacy_preregistration(
                self.runtime,
                current,
                schema_version=prereg_schema,
            )
            legacy_terminal = _terminal(
                self.runtime,
                legacy,
                self.preregistration_file_sha256,
            )
            self.assertEqual([], self.runtime.validate_preregistration(legacy))
            self.assertEqual(terminal_schema, legacy_terminal["schema_version"])
            self.assertEqual(
                [], self.runtime.validate_terminal(legacy_terminal)
            )

    def test_v3_terminal_expected_calls_are_bound_to_frozen_execution(self) -> None:
        terminal = _terminal(
            self.runtime,
            self.preregistration,
            self.preregistration_file_sha256,
        )
        terminal["expected_provider_generate_calls"] += 1
        _refresh_terminal(self.runtime, terminal)

        self.assertIn(
            "pdf_structural_holdout_terminal_accounting_invalid",
            self.runtime.validate_terminal(terminal),
        )

    def test_budget_block_journal_keeps_only_observed_and_maximum_tokens(
        self,
    ) -> None:
        runner = _load_script_module(
            "local_pdf_structural_repair_holdout.py"
        )
        error = PdfGridProviderError(
            "pdf_grid_provider_counted_input_budget_exceeded",
            "context_budget",
            safe_details={
                "observed_total_tokens": 20_001,
                "maximum_counted_input_tokens": 20_000,
                "must_not_escape": "private-provider-detail",
            },
        )
        observation = runner._budget_count_observation(error)
        self.assertEqual(
            {
                "observed_total_tokens": 20_001,
                "maximum_counted_input_tokens": 20_000,
            },
            observation,
        )

        terminal = _terminal(
            self.runtime,
            self.preregistration,
            self.preregistration_file_sha256,
        )
        terminal["journal"][0]["count_tokens"] = observation
        terminal["journal"][0]["failure_code"] = (
            "pdf_grid_provider_counted_input_budget_exceeded"
        )
        terminal["journal"][0]["failure_class"] = "context_budget"
        _refresh_terminal(self.runtime, terminal)
        self.assertEqual([], self.runtime.validate_terminal(terminal))

    def test_preflight_block_is_a_sealed_zero_call_terminal(self) -> None:
        scopes = [
            {
                "target_id": target["target_id"],
                "document_id": target["document_id"],
                "page_number": target["page_number"],
                "parser_ordinal": target["parser_ordinal"],
            }
            for target in self.preregistration["targets"]
        ]
        preflight = self.runtime.build_preflight_terminal(
            documents=self.preregistration["documents"],
            target_scopes=scopes,
            frozen_source=self.preregistration["frozen_source"],
            freshness_scan=self.preregistration["freshness_scan"],
            execution_class=self.preregistration["execution_class"],
            failed_target_id="holdout_001",
            failure_code="pdf_visual_topology_atom_budget_exceeded",
        )

        self.assertEqual([], self.runtime.validate_preflight_terminal(preflight))
        self.assertFalse(preflight["provider_calls_started"])
        self.assertEqual(0, preflight["new_provider_generate_calls"])
        self.assertFalse(preflight["reference_process_started"])

    def test_raw_lists_with_junk_are_rejected_not_filtered(self) -> None:
        tampered = copy.deepcopy(self.preregistration)
        tampered["documents"].append(None)
        _refresh_preregistration_checksum(tampered)

        self.assertIn(
            "pdf_structural_holdout_document_contract_invalid",
            self.runtime.validate_preregistration(tampered),
        )

    def test_malformed_numbers_and_assemblies_return_typed_errors(self) -> None:
        malformed_prereg = copy.deepcopy(self.preregistration)
        malformed_prereg["targets"][0]["page_number"] = {"bad": "number"}
        _refresh_preregistration_checksum(malformed_prereg)
        prereg_errors = self.runtime.validate_preregistration(malformed_prereg)

        terminal = _terminal(
            self.runtime,
            self.preregistration,
            self.preregistration_file_sha256,
        )
        terminal["targets"]["holdout_001"]["assemblies"] = "bad"
        terminal.pop("artifact_checksum", None)
        terminal["artifact_checksum"] = sha256_json(terminal)
        terminal_errors = self.runtime.validate_terminal(terminal)

        self.assertTrue(prereg_errors)
        self.assertIn(
            "pdf_structural_holdout_terminal_seal_input_invalid",
            terminal_errors,
        )

    def test_per_target_override_is_rejected_even_with_new_checksum(self) -> None:
        tampered = copy.deepcopy(self.preregistration)
        tampered["targets"][0]["prompt"] = "target-specific"
        _refresh_preregistration_checksum(tampered)

        self.assertIn(
            "pdf_structural_holdout_target_contract_invalid",
            self.runtime.validate_preregistration(tampered),
        )

    def test_selection_cannot_skip_an_earlier_eligible_document(self) -> None:
        tampered = copy.deepcopy(self.preregistration)
        tampered["documents"][0]["table_candidate_count"] = 999
        _refresh_preregistration_checksum(tampered)

        self.assertIn(
            "pdf_structural_holdout_selected_document_invalid",
            self.runtime.validate_preregistration(tampered),
        )

    def test_holdout_id_is_recomputed_not_trusted(self) -> None:
        tampered = copy.deepcopy(self.preregistration)
        tampered["holdout_id"] = "pdfholdout_000000000000000000000000"
        _refresh_preregistration_checksum(tampered)

        self.assertIn(
            "pdf_structural_holdout_id_invalid",
            self.runtime.validate_preregistration(tampered),
        )

    def test_crop_bytes_are_bound_to_visual_package(self) -> None:
        tampered = copy.deepcopy(self.preregistration)
        tampered["targets"][0]["private_png_base64"] = base64.b64encode(
            b"different-crop"
        ).decode("ascii")
        _refresh_preregistration_checksum(tampered)

        self.assertIn(
            "pdf_structural_holdout_target_lineage_invalid",
            self.runtime.validate_preregistration(tampered),
        )

    def test_terminal_call_count_must_match_observable_journal(self) -> None:
        terminal = _terminal(
            self.runtime,
            self.preregistration,
            self.preregistration_file_sha256,
        )
        terminal["journal"][0]["provider_generate_call_performed"] = True
        _refresh_terminal(self.runtime, terminal)

        self.assertIn(
            "pdf_structural_holdout_terminal_journal_invalid",
            self.runtime.validate_terminal(terminal),
        )

    def test_terminal_scope_cannot_diverge_from_preregistration(self) -> None:
        terminal = _terminal(
            self.runtime,
            self.preregistration,
            self.preregistration_file_sha256,
        )
        terminal["targets"]["holdout_001"]["scope"]["page_number"] = 2
        _refresh_terminal(self.runtime, terminal)

        self.assertIn(
            "pdf_structural_holdout_terminal_target_preregistration_mismatch",
            self.runtime.validate_terminal_against_preregistration(
                terminal=terminal,
                preregistration=self.preregistration,
                preregistration_file_sha256=self.preregistration_file_sha256,
            ),
        )

    def test_accepted_terminal_requires_binding_and_materialization(self) -> None:
        terminal = _terminal(
            self.runtime,
            self.preregistration,
            self.preregistration_file_sha256,
        )
        terminal["targets"]["holdout_001"]["consensus_result"] = {
            "terminal_status": "accepted_supplied_consensus",
            "result_checksum": hashlib.sha256(b"accepted").hexdigest(),
        }
        _refresh_terminal(self.runtime, terminal)

        self.assertIn(
            "pdf_structural_holdout_terminal_materialization_boundary_invalid",
            self.runtime.validate_terminal(terminal),
        )

    def test_development_regression_is_explicitly_non_certifying(self) -> None:
        regression = _preregistration(
            self.runtime,
            execution_class="development_regression",
            prior_experiment_matches=2,
        )

        self.assertEqual([], self.runtime.validate_preregistration(regression))
        self.assertEqual("development_regression", regression["execution_class"])
        self.assertFalse(regression["certification_eligible"])
        self.assertEqual(6, len(regression["documents"]))
        self.assertEqual(
            "legacy_exposed_six_pdf_2026_07_14_v1",
            regression["corpus_policy"],
        )

    def test_fresh_policy_is_the_named_seven_document_public_corpus(self) -> None:
        self.assertEqual(7, len(self.preregistration["documents"]))
        self.assertEqual(
            "official_public_broker_pdf_2026_07_14_v1",
            self.preregistration["corpus_policy"],
        )
        self.assertEqual(
            set(
                PDF_STRUCTURAL_HOLDOUT_CORPUS_POLICIES["fresh_holdout"][
                    "sha256"
                ]
            ),
            {
                item["pdf_sha256"]
                for item in self.preregistration["documents"]
            },
        )

        tampered = copy.deepcopy(self.preregistration)
        legacy_hashes = sorted(
            PDF_STRUCTURAL_HOLDOUT_CORPUS_POLICIES[
                "development_regression"
            ]["sha256"]
        )
        for document, digest in zip(
            tampered["documents"], legacy_hashes, strict=False
        ):
            document["pdf_sha256"] = digest
        _refresh_preregistration_checksum(tampered)
        self.assertIn(
            "pdf_structural_holdout_document_identity_invalid",
            self.runtime.validate_preregistration(tampered),
        )

    def test_v2_eligibility_is_parser_only_sealed_and_conservative(self) -> None:
        observation = self.runtime.build_candidate_eligibility_observation(
            candidate=_eligibility_candidate(),
            page=_eligibility_page(),
            candidate_bbox=[30.0, 100.0, 570.0, 300.0],
        )

        self.assertTrue(observation["eligible"])
        self.assertEqual([], observation["reason_codes"])
        self.assertEqual(
            PDF_STRUCTURAL_HOLDOUT_ELIGIBILITY_POLICY_CHECKSUM,
            observation["policy_checksum"],
        )
        self.assertEqual(
            [], self.runtime.validate_candidate_eligibility_observation(observation)
        )

        page_wide = self.runtime.build_candidate_eligibility_observation(
            candidate=_eligibility_candidate(),
            page=_eligibility_page(),
            candidate_bbox=[1.0, 1.0, 599.0, 700.0],
        )
        aligned = _eligibility_candidate()
        aligned["table_strategy_ref"] = "aligned_text_v0"
        multi_region = self.runtime.build_candidate_eligibility_observation(
            candidate=aligned,
            page=_eligibility_page(),
            candidate_bbox=[30.0, 100.0, 570.0, 300.0],
        )

        self.assertFalse(page_wide["eligible"])
        self.assertIn(
            "pdf_structural_holdout_candidate_page_wide_area_rejected",
            page_wide["reason_codes"],
        )
        self.assertFalse(multi_region["eligible"])
        self.assertIn(
            "pdf_structural_holdout_candidate_strategy_unsupported",
            multi_region["reason_codes"],
        )

    def test_fresh_v2_is_separate_and_v1_policy_stays_unchanged(self) -> None:
        v2 = _preregistration(self.runtime, execution_class="fresh_holdout_v2")

        self.assertEqual([], self.runtime.validate_preregistration(v2))
        self.assertEqual(PDF_STRUCTURAL_HOLDOUT_POLICY_VERSION_V2, v2["policy_version"])
        self.assertTrue(v2["certification_eligible"])
        self.assertEqual(
            "official_public_broker_pdf_2026_07_14_v2", v2["corpus_policy"]
        )
        self.assertEqual(
            7,
            len(
                PDF_STRUCTURAL_HOLDOUT_CORPUS_POLICIES["fresh_holdout_v2"][
                    "sha256"
                ]
            ),
        )
        self.assertEqual(
            "official_public_broker_pdf_2026_07_14_v1",
            self.preregistration["corpus_policy"],
        )

        tampered = copy.deepcopy(v2)
        tampered["targets"][0]["eligibility_observation"]["eligible"] = False
        _refresh_preregistration_checksum(tampered)
        self.assertIn(
            "pdf_structural_holdout_target_identity_invalid",
            self.runtime.validate_preregistration(tampered),
        )

    def test_fresh_v3_has_a_new_disjoint_exact_corpus(self) -> None:
        v3 = _preregistration(self.runtime, execution_class="fresh_holdout_v3")
        v3_hashes = set(
            PDF_STRUCTURAL_HOLDOUT_CORPUS_POLICIES["fresh_holdout_v3"][
                "sha256"
            ]
        )
        earlier_hashes = set().union(
            *(
                set(PDF_STRUCTURAL_HOLDOUT_CORPUS_POLICIES[name]["sha256"])
                for name in (
                    "fresh_holdout",
                    "fresh_holdout_v2",
                    "development_regression",
                )
            )
        )

        self.assertEqual([], self.runtime.validate_preregistration(v3))
        self.assertEqual(PDF_STRUCTURAL_HOLDOUT_POLICY_VERSION_V2, v3["policy_version"])
        self.assertEqual(
            "official_public_broker_pdf_2026_07_14_v3",
            v3["corpus_policy"],
        )
        self.assertEqual(7, len(v3_hashes))
        self.assertTrue(v3_hashes.isdisjoint(earlier_hashes))

        v4 = _preregistration(self.runtime, execution_class="fresh_holdout_v4")
        v4_hashes = set(
            PDF_STRUCTURAL_HOLDOUT_CORPUS_POLICIES["fresh_holdout_v4"][
                "sha256"
            ]
        )
        self.assertEqual([], self.runtime.validate_preregistration(v4))
        self.assertEqual(
            "official_public_broker_pdf_2026_07_14_v4",
            v4["corpus_policy"],
        )
        self.assertEqual(7, len(v4_hashes))
        self.assertTrue(v4_hashes.isdisjoint(earlier_hashes | v3_hashes))

    def test_fresh_v5_has_a_disjoint_exact_corpus_and_v5_selection_policy(
        self,
    ) -> None:
        v5 = _preregistration(self.runtime, execution_class="fresh_holdout_v5")
        v5_policy = PDF_STRUCTURAL_HOLDOUT_CORPUS_POLICIES[
            "fresh_holdout_v5"
        ]
        earlier_hashes = set().union(
            *(
                set(PDF_STRUCTURAL_HOLDOUT_CORPUS_POLICIES[name]["sha256"])
                for name in (
                    "fresh_holdout",
                    "fresh_holdout_v2",
                    "fresh_holdout_v3",
                    "fresh_holdout_v4",
                    "development_regression",
                )
            )
        )

        self.assertEqual([], self.runtime.validate_preregistration(v5))
        self.assertEqual(
            "official_public_broker_pdf_2026_07_15_v5",
            v5["corpus_policy"],
        )
        self.assertEqual(
            "local/stage2/"
            "broker_reports_pdf_structural_holdout_public_v5_2026-07-15/corpus",
            v5_policy["repo_relative_root"],
        )
        self.assertEqual(7, len(v5_policy["sha256"]))
        self.assertTrue(set(v5_policy["sha256"]).isdisjoint(earlier_hashes))
        self.assertEqual(
            PDF_STRUCTURAL_HOLDOUT_ELIGIBILITY_POLICY_V5,
            v5["selection_contract"]["eligibility_policy"],
        )
        self.assertEqual(
            PDF_STRUCTURAL_HOLDOUT_ELIGIBILITY_POLICY_V5_CHECKSUM,
            v5["selection_contract"]["eligibility_policy_checksum"],
        )
        self.assertIn(
            "select_first_aligned_then_first_wide_or_highest_column_remaining",
            v5["selection_contract"]["rule"],
        )

    def test_v5_eligibility_has_strategy_specific_fail_closed_thresholds(
        self,
    ) -> None:
        def observe(
            *, strategy: str, confidence: float, rulings: int
        ) -> dict:
            candidate = _eligibility_candidate()
            candidate.update(
                {
                    "table_strategy_ref": strategy,
                    "geometry_confidence": confidence,
                    "ruling_evidence_total": rulings,
                }
            )
            return self.runtime.build_candidate_eligibility_observation(
                candidate=candidate,
                page=_eligibility_page(),
                candidate_bbox=[30.0, 100.0, 570.0, 300.0],
                execution_class="fresh_holdout_v5",
            )

        aligned = observe(
            strategy="aligned_text_v0", confidence=0.8, rulings=0
        )
        ruled = observe(
            strategy="ruled_lines_v0", confidence=0.9, rulings=4
        )
        aligned_low = observe(
            strategy="aligned_text_v0", confidence=0.799, rulings=0
        )
        ruled_low_confidence = observe(
            strategy="ruled_lines_v0", confidence=0.899, rulings=4
        )
        ruled_low_rulings = observe(
            strategy="ruled_lines_v0", confidence=0.9, rulings=3
        )

        self.assertTrue(aligned["eligible"])
        self.assertTrue(ruled["eligible"])
        self.assertEqual(
            PDF_STRUCTURAL_HOLDOUT_ELIGIBILITY_POLICY_V5_CHECKSUM,
            aligned["policy_checksum"],
        )
        self.assertIn(
            "pdf_structural_holdout_candidate_confidence_below_threshold",
            aligned_low["reason_codes"],
        )
        self.assertIn(
            "pdf_structural_holdout_candidate_confidence_below_threshold",
            ruled_low_confidence["reason_codes"],
        )
        self.assertIn(
            "pdf_structural_holdout_candidate_ruling_signal_insufficient",
            ruled_low_rulings["reason_codes"],
        )

    def test_v5_runner_selection_is_class_aware_and_stored_in_parser_order(
        self,
    ) -> None:
        runner = _load_script_module(
            "local_pdf_structural_repair_holdout.py"
        )
        candidates = [
            {"table_candidate_ref": "ruled-ordinary"},
            {"table_candidate_ref": "aligned-first"},
            {"table_candidate_ref": "aligned-wide"},
            {"table_candidate_ref": "ruled-later"},
        ]
        observations = {
            "ruled-ordinary": {
                "table_strategy_ref": "ruled_lines_v0",
                "columns_total": 7,
            },
            "aligned-first": {
                "table_strategy_ref": "aligned_text_v0",
                "columns_total": 3,
            },
            "aligned-wide": {
                "table_strategy_ref": "aligned_text_v0",
                "columns_total": 12,
            },
            "ruled-later": {
                "table_strategy_ref": "ruled_lines_v0",
                "columns_total": 10,
            },
        }

        selected = runner._select_candidates_for_execution_class(
            candidates=candidates,
            eligibility_by_ref=observations,
            execution_class="fresh_holdout_v5",
            table_limit=3,
        )

        self.assertEqual(
            ["ruled-ordinary", "aligned-first", "aligned-wide"],
            [item["table_candidate_ref"] for item in selected],
        )
        no_ruled = {
            key: {**value, "table_strategy_ref": "aligned_text_v0"}
            for key, value in observations.items()
        }
        self.assertEqual(
            [],
            runner._select_candidates_for_execution_class(
                candidates=candidates,
                eligibility_by_ref=no_ruled,
                execution_class="fresh_holdout_v5",
                table_limit=3,
            ),
        )
        self.assertEqual(
            candidates[:3],
            runner._select_candidates_for_execution_class(
                candidates=candidates,
                eligibility_by_ref={},
                execution_class="fresh_holdout_v4",
                table_limit=3,
            ),
        )

    def test_v5_is_in_runner_scorer_and_safe_hash_sets(self) -> None:
        runner = _load_script_module(
            "local_pdf_structural_repair_holdout.py"
        )
        scorer = _load_script_module(
            "local_pdf_structural_repair_holdout_score.py"
        )

        self.assertIn("fresh_holdout_v5", runner.PARSER_ONLY_HOLDOUT_CLASSES)
        self.assertIn("fresh_holdout_v5", runner.FRESH_HOLDOUT_CLASSES)
        self.assertEqual(
            set(PDF_STRUCTURAL_HOLDOUT_CORPUS_POLICIES["fresh_holdout_v5"]["sha256"]),
            set(runner.FRESH_CORPUS_V5_SHA256),
        )
        self.assertIn("fresh_holdout_v5", scorer.CERTIFYING_HOLDOUT_CLASSES)

    def test_freshness_inventory_rejects_non_object_entries(self) -> None:
        tampered = copy.deepcopy(self.preregistration)
        tampered["freshness_scan"]["inventory"].append(None)
        _refresh_preregistration_checksum(tampered)

        self.assertIn(
            "pdf_structural_holdout_freshness_scan_invalid",
            self.runtime.validate_preregistration(tampered),
        )

    def test_terminal_seal_binds_private_journal(self) -> None:
        terminal = _terminal(
            self.runtime,
            self.preregistration,
            self.preregistration_file_sha256,
        )
        self.assertEqual(
            sha256_json(terminal["journal"]),
            terminal["terminal_seal"]["journal_sha256"],
        )
        self.assertEqual(
            sha256_json(terminal["provider_qualification"]),
            terminal["terminal_seal"]["provider_qualification_sha256"],
        )
        self.assertEqual(
            terminal["new_provider_generate_calls"],
            terminal["terminal_seal"]["new_provider_generate_calls"],
        )
        terminal["journal"][0]["failure_code"] = "changed_after_seal"
        terminal.pop("artifact_checksum", None)
        terminal["artifact_checksum"] = sha256_json(terminal)

        self.assertIn(
            "pdf_structural_holdout_terminal_seal_invalid",
            self.runtime.validate_terminal(terminal),
        )

    def test_provider_lineage_and_bool_tokens_are_rejected(self) -> None:
        terminal = _terminal(
            self.runtime,
            self.preregistration,
            self.preregistration_file_sha256,
        )
        _mark_first_attempt_performed(terminal, self.preregistration)
        _refresh_terminal(self.runtime, terminal)
        self.assertEqual([], self.runtime.validate_terminal(terminal))

        bad_lineage = copy.deepcopy(terminal)
        bad_lineage["journal"][0]["provider_attempt"]["attempt_lineage"] = [
            "foreign_attempt"
        ]
        _refresh_terminal(self.runtime, bad_lineage)
        self.assertIn(
            "pdf_structural_holdout_terminal_journal_invalid",
            self.runtime.validate_terminal(bad_lineage),
        )

        bad_tokens = copy.deepcopy(terminal)
        bad_tokens["journal"][0]["count_tokens"]["total_tokens"] = True
        _refresh_terminal(self.runtime, bad_tokens)
        self.assertIn(
            "pdf_structural_holdout_terminal_journal_invalid",
            self.runtime.validate_terminal(bad_tokens),
        )

    def test_provider_usage_must_match_count_tokens(self) -> None:
        terminal = _terminal(
            self.runtime,
            self.preregistration,
            self.preregistration_file_sha256,
        )
        _mark_first_attempt_performed(terminal, self.preregistration)
        attempt = terminal["journal"][0]["provider_attempt"]
        attempt["usage"]["input_tokens"] = 11
        attempt["usage"]["total_tokens"] = 13
        terminal["journal"][0]["provider_result"]["attempt"] = copy.deepcopy(
            attempt
        )
        _refresh_terminal(self.runtime, terminal)

        self.assertIn(
            "pdf_structural_holdout_terminal_journal_invalid",
            self.runtime.validate_terminal(terminal),
        )


class PdfStructuralRepairHoldoutRoutingTests(unittest.TestCase):
    def test_runner_has_fixed_factories_and_no_reference_input(self) -> None:
        service_root = Path(__file__).resolve().parents[1]
        runner = (
            service_root
            / "scripts"
            / "local_pdf_structural_repair_holdout.py"
        ).read_text(encoding="utf-8")

        for factory in (
            "PdfStructuralRepairHoldoutContractFactory",
            "PdfDualOracleContractFactory",
            "PdfParserGeometryFactory",
            "PdfVisualTopologyFactory",
            "PdfTableRasterFactory",
            "PdfGridExperimentProviderFactory",
            "PdfTopologyAssemblyFactory",
            "PdfDualOracleConsensusFactory",
            "PdfHybridMaterializationFactory",
        ):
            self.assertIn(factory, runner)
        self.assertNotIn("--reference", runner)
        self.assertNotIn("TARGET_KEYS", runner)
        self.assertNotIn("STRUCTURAL_CASES", runner)
        self.assertNotIn("PdfHybridCompactionFactory", runner)
        self.assertNotIn("PdfHybridWindowFactory", runner)
        self.assertIn("_verify_frozen_boundary", runner)
        self.assertIn("FRESH_CORPUS_SHA256", runner)
        self.assertIn("--execution-class", runner)
        self.assertNotIn("--prior-experiment-root", runner)

    def test_runner_safe_codes_are_closed_not_sanitized_exception_text(self) -> None:
        runner = _load_script_module("local_pdf_structural_repair_holdout.py")

        self.assertEqual(
            "pdf_structural_holdout_provider_attempt_failed",
            runner._safe_code("pdf_structural_holdout_provider_attempt_failed"),
        )
        self.assertEqual(
            "unknown_failure",
            runner._safe_code(r"C:\Users\secret\token=value"),
        )

        fallback = runner._window_fallback_consensus(
            target_id="holdout_001",
            window_result={
                "runtime_terminal_status": "no_valid_consensus",
                "result_checksum": hashlib.sha256(b"runtime").hexdigest(),
                "safe_summary": {
                    "reason_codes": [
                        "pdf_structural_window_response_invalid"
                    ]
                },
            },
        )
        self.assertEqual("blocked_no_valid_evidence", fallback["terminal_status"])
        self.assertEqual(
            ["pdf_structural_window_response_invalid"],
            fallback["reason_codes"],
        )

    def test_runner_counts_container_pages_when_projection_inventory_is_empty(
        self,
    ) -> None:
        runner = _load_script_module("local_pdf_structural_repair_holdout.py")
        pdf_bytes = _pdf_bytes(
            [{"blank": True}, {"blank": True}, {"blank": True}]
        )

        self.assertEqual(3, runner._pdf_page_count(pdf_bytes))
        with self.assertRaisesRegex(
            runner.HoldoutBoundaryError,
            "pdf_structural_holdout_page_count_unavailable",
        ):
            runner._pdf_page_count(b"not-a-pdf")

    def test_prior_inventory_uses_trusted_root_and_detects_drift(self) -> None:
        runner = _load_script_module("local_pdf_structural_repair_holdout.py")
        with tempfile.TemporaryDirectory() as raw_root:
            repo_root = Path(raw_root).resolve()
            stage2 = repo_root / "local" / "stage2"
            prior = stage2 / "broker_reports_pdf_previous"
            prior.mkdir(parents=True)
            input_pdf = prior / "input.pdf"
            input_pdf.write_bytes(b"frozen-input-pdf")
            digest = hashlib.sha256(input_pdf.read_bytes()).hexdigest()
            evidence = prior / "result.json"
            evidence.write_text(digest, encoding="utf-8")
            output = stage2 / "broker_reports_pdf_current"
            with (
                patch.object(runner, "REPO_ROOT", repo_root),
                patch.object(runner, "LOCAL_STAGE2", stage2),
            ):
                frozen, matches = runner._scan_prior_experiments(
                    hashes=[digest],
                    excluded_repo_relative_root=(
                        "local/stage2/broker_reports_pdf_current"
                    ),
                    excluded_input_inventory=[
                        {
                            "repo_relative_path": (
                                "local/stage2/broker_reports_pdf_previous/input.pdf"
                            ),
                            "size_bytes": input_pdf.stat().st_size,
                            "sha256": digest,
                        }
                    ],
                )
                self.assertEqual(1, matches[digest])
                self.assertEqual(1, len(frozen["inventory"]))
                self.assertEqual(
                    digest, frozen["excluded_input_inventory"][0]["sha256"]
                )
                evidence.write_text("changed", encoding="utf-8")
                with self.assertRaisesRegex(
                    runner.HoldoutBoundaryError,
                    "pdf_structural_holdout_freshness_inventory_mismatch",
                ):
                    runner._verify_freshness_scan(
                        frozen, runtime_output_dir=output
                    )

    def test_scorer_has_no_provider_or_reconstruction_imports(self) -> None:
        service_root = Path(__file__).resolve().parents[1]
        scorer = (
            service_root
            / "scripts"
            / "local_pdf_structural_repair_holdout_score.py"
        ).read_text(encoding="utf-8")

        self.assertNotIn("pdf_grid_experiment_provider", scorer)
        self.assertNotIn("pdf_topology_assembly", scorer)
        self.assertNotIn("pdf_dual_oracle_consensus", scorer)
        self.assertNotIn("Gate1Normalizer", scorer)
        self.assertNotIn("import requests", scorer)
        self.assertIn("terminal_raw_sha256_after", scorer)

    def test_scorer_rejects_duplicate_candidate_accounting(self) -> None:
        scorer = _load_script_module(
            "local_pdf_structural_repair_holdout_score.py"
        )
        runtime = PdfStructuralRepairHoldoutContractFactory().create()
        preregistration = _preregistration(runtime)
        target = _accepted_scoring_target(preregistration["targets"][0])

        self.assertIsInstance(
            scorer._validate_independent_scoring_chain(target), dict
        )
        duplicate = copy.deepcopy(target)
        candidate_id = duplicate["accepted_binding"]["rows"][0]["cells"][0][0]
        duplicate["accepted_binding"]["rows"][0]["cells"][0].append(
            candidate_id
        )
        duplicate["materialization"]["binding_output_hash"] = sha256_json(
            duplicate["accepted_binding"]
        )
        with self.assertRaisesRegex(
            scorer.HoldoutScoreError,
            "pdf_structural_holdout_score_candidate_accounting_invalid",
        ):
            scorer._validate_independent_scoring_chain(duplicate)

    def test_scorer_compares_canonical_span_geometry_not_provider_relation_wording(
        self,
    ) -> None:
        scorer = _load_script_module(
            "local_pdf_structural_repair_holdout_score.py"
        )
        runtime = PdfStructuralRepairHoldoutContractFactory().create()
        preregistration = _preregistration(runtime)
        target = _accepted_scoring_target(preregistration["targets"][0])
        binding = copy.deepcopy(target["accepted_binding"])
        binding["header_rows"] = [1, 2]
        binding["spans"] = [
            {
                "start_row": 1,
                "end_row": 2,
                "start_column": 1,
                "end_column": 1,
                "relation": "merged",
            }
        ]
        reference = {
            "review_status": "human_verified",
            "rows": 2,
            "columns": 2,
            "header_rows": [1, 2],
            "spans": [
                {
                    "start_row": 1,
                    "end_row": 2,
                    "start_column": 1,
                    "end_column": 1,
                    "relation": "spanning_header",
                }
            ],
            "header_hierarchy": [],
            "cells": [["", ""], ["", ""]],
        }

        score = scorer._score_binding(
            reference=reference,
            binding=binding,
            package=target["visual_package"],
        )

        self.assertTrue(score["spans_exact"])
        self.assertTrue(score["topology_exact"])

    def test_reference_rejects_non_object_structural_entries(self) -> None:
        scorer = _load_script_module(
            "local_pdf_structural_repair_holdout_score.py"
        )
        value = {
            "schema_version": scorer.REFERENCE_SCHEMA,
            "holdout_id": "pdfholdout_fixture",
            "preregistration_file_sha256": hashlib.sha256(b"pre").hexdigest(),
            "terminal_seal_hash": hashlib.sha256(b"seal").hexdigest(),
            "targets": [
                {
                    "target_id": f"holdout_{index:03d}",
                    "rows": 1,
                    "columns": 1,
                    "header_rows": [],
                    "spans": [None] if index == 1 else [],
                    "header_hierarchy": [],
                    "cells": [["value"]],
                    "review_status": "human_verified",
                }
                for index in range(1, 4)
            ],
        }
        value["reference_checksum"] = sha256_json(value)

        with self.assertRaisesRegex(
            scorer.HoldoutScoreError,
            "pdf_structural_holdout_reference_target_invalid",
        ):
            scorer._validate_reference(
                value,
                holdout_id=value["holdout_id"],
                preregistration_file_sha256=value[
                    "preregistration_file_sha256"
                ],
                terminal_seal_hash=value["terminal_seal_hash"],
            )

    def test_v2_reference_can_honestly_classify_unsupported_without_fake_grid(
        self,
    ) -> None:
        scorer = _load_script_module(
            "local_pdf_structural_repair_holdout_score.py"
        )
        identity = {
            "schema_version": scorer.REFERENCE_SCHEMA_V2,
            "holdout_id": "pdfholdout_fixture",
            "preregistration_file_sha256": hashlib.sha256(b"pre").hexdigest(),
            "terminal_seal_hash": hashlib.sha256(b"seal").hexdigest(),
        }
        supported = {
            "rows": 1,
            "columns": 1,
            "header_rows": [],
            "spans": [],
            "header_hierarchy": [],
            "cells": [["value"]],
            "review_status": "human_verified",
            "unsupported_reason_codes": [],
        }
        unsupported = {
            "rows": 0,
            "columns": 0,
            "header_rows": [],
            "spans": [],
            "header_hierarchy": [],
            "cells": [],
            "review_status": "human_verified_unsupported",
            "unsupported_reason_codes": [
                "human_verified_parser_candidate_false_positive"
            ],
        }
        value = {
            **identity,
            "targets": [
                {"target_id": "holdout_001", **unsupported},
                {"target_id": "holdout_002", **supported},
                {"target_id": "holdout_003", **supported},
            ],
        }
        value["reference_checksum"] = sha256_json(value)

        validated = scorer._validate_reference(
            value,
            holdout_id=identity["holdout_id"],
            preregistration_file_sha256=identity[
                "preregistration_file_sha256"
            ],
            terminal_seal_hash=identity["terminal_seal_hash"],
            policy_version=PDF_STRUCTURAL_HOLDOUT_POLICY_VERSION_V2,
        )
        abstention = scorer._score_binding(
            reference=validated["holdout_001"], binding=None, package={}
        )
        false_positive = scorer._score_binding(
            reference=validated["holdout_001"], binding={"bound": True}, package={}
        )

        self.assertEqual("unsupported", abstention["support_classification"])
        self.assertTrue(abstention["unsupported_abstention"])
        self.assertFalse(abstention["unsupported_false_positive_binding"])
        self.assertTrue(false_positive["unsupported_false_positive_binding"])
        scorer._assert_safe(
            {
                "targets": [abstention, false_positive],
                "classification_only": True,
            }
        )

        fake_grid = copy.deepcopy(value)
        fake_grid["targets"][0]["rows"] = 1
        fake_grid["targets"][0]["columns"] = 1
        fake_grid["targets"][0]["cells"] = [["invented"]]
        fake_grid["reference_checksum"] = sha256_json(
            {key: item for key, item in fake_grid.items() if key != "reference_checksum"}
        )
        with self.assertRaisesRegex(
            scorer.HoldoutScoreError,
            "pdf_structural_holdout_reference_target_invalid",
        ):
            scorer._validate_reference(
                fake_grid,
                holdout_id=identity["holdout_id"],
                preregistration_file_sha256=identity[
                    "preregistration_file_sha256"
                ],
                terminal_seal_hash=identity["terminal_seal_hash"],
                policy_version=PDF_STRUCTURAL_HOLDOUT_POLICY_VERSION_V2,
            )


def _preregistration(
    runtime,
    *,
    execution_class: str = "fresh_holdout",
    prior_experiment_matches: int = 0,
) -> dict:
    documents = []
    policy = PDF_STRUCTURAL_HOLDOUT_CORPUS_POLICIES[execution_class]
    hashes = sorted(policy["sha256"])
    required_root = policy["repo_relative_root"]
    for index, digest in enumerate(hashes, start=1):
        documents.append(
            {
                "document_id": f"holdout_doc_{index:03d}",
                "repo_relative_path": (
                    f"{required_root}/document-{index}.pdf"
                    if isinstance(required_root, str)
                    else f"fixtures/document-{index}.pdf"
                ),
                "pdf_sha256": digest,
                "size_bytes": 100 + index,
                "page_count": 0,
                "table_candidate_count": 0,
                "selection_status": "not_evaluated",
                "prior_experiment_matches": prior_experiment_matches,
                **(
                    {"eligible_table_candidate_count": 0}
                    if execution_class
                    in {
                        "fresh_holdout_v2",
                        "fresh_holdout_v3",
                        "fresh_holdout_v4",
                        "fresh_holdout_v5",
                    }
                    else {}
                ),
            }
        )
    documents[0].update(
        {
            "page_count": 1,
            "table_candidate_count": 0,
            "selection_status": "not_selected_insufficient_candidates",
        }
    )
    documents[1].update(
        {
            "page_count": 1,
            "table_candidate_count": 3,
            "selection_status": "selected",
            **(
                {"eligible_table_candidate_count": 3}
                if execution_class
                in {
                    "fresh_holdout_v2",
                    "fresh_holdout_v3",
                    "fresh_holdout_v4",
                    "fresh_holdout_v5",
                }
                else {}
            ),
        }
    )
    pdf_sha256 = documents[1]["pdf_sha256"]
    parser_contracts = PdfDualOracleContractFactory().create()
    parser_geometry = PdfParserGeometryFactory().create()
    visual = PdfVisualTopologyFactory().create()
    projection = _projection()
    parser_observation = parser_contracts.build_parser_observation_from_word_atoms(
        document_ref="document-ref",
        pdf_sha256=pdf_sha256,
        page_ref="page-ref",
        page_number=1,
        table_ref="table-ref",
        table_bbox=[0.0, 0.0, 200.0, 100.0],
        pdf_text_layer_projection=projection,
    )
    geometry_observation = parser_geometry.build_observation(
        document_ref="document-ref",
        pdf_sha256=pdf_sha256,
        page_ref="page-ref",
        page_number=1,
        table_ref="table-ref",
        table_bbox=[0.0, 0.0, 200.0, 100.0],
        pdf_text_layer_projection=projection,
    )
    png_bytes = b"synthetic-private-crop-bytes"
    crop = _crop_manifest(pdf_sha256=pdf_sha256, png_bytes=png_bytes)
    package = visual.build_package(
        parser_observation=parser_observation,
        crop_manifest=crop,
    )
    targets = []
    for index in range(1, 4):
        target = {
            "target_id": f"holdout_{index:03d}",
            "document_id": documents[1]["document_id"],
            "page_number": 1,
            "parser_ordinal": index,
            "parser_observation": copy.deepcopy(parser_observation),
            "parser_geometry_observation": copy.deepcopy(geometry_observation),
            "visual_package": copy.deepcopy(package),
            "private_png_base64": base64.b64encode(png_bytes).decode("ascii"),
        }
        if execution_class in {
            "fresh_holdout_v2",
            "fresh_holdout_v3",
            "fresh_holdout_v4",
            "fresh_holdout_v5",
        }:
            eligibility_candidate = _eligibility_candidate(
                parser_ordinal=index, table_ref="table-ref"
            )
            if execution_class == "fresh_holdout_v5" and index == 1:
                eligibility_candidate.update(
                    {
                        "table_strategy_ref": "aligned_text_v0",
                        "geometry_confidence": 0.8,
                        "ruling_evidence_total": 0,
                    }
                )
            target["eligibility_observation"] = (
                runtime.build_candidate_eligibility_observation(
                    candidate=eligibility_candidate,
                    page=_eligibility_page(),
                    candidate_bbox=[30.0, 100.0, 570.0, 300.0],
                    execution_class=execution_class,
                )
            )
        target["execution_contract"] = (
            runtime.build_target_execution_contract(
                parser_observation=target["parser_observation"],
                visual_package=target["visual_package"],
            )
        )
        targets.append(target)
    inventory = [
        {
            "repo_relative_path": (
                "services/broker-reports-gate1-proof/broker_reports_gate1/"
                "pdf_structural_repair_holdout_contracts.py"
            ),
            "size_bytes": 10,
            "sha256": hashlib.sha256(b"contract").hexdigest(),
        },
        {
            "repo_relative_path": (
                "services/broker-reports-gate1-proof/scripts/"
                "local_pdf_structural_repair_holdout.py"
            ),
            "size_bytes": 20,
            "sha256": hashlib.sha256(b"runner").hexdigest(),
        },
    ]
    source_freeze = {
        "git_revision": hashlib.sha256(b"revision").hexdigest(),
        "inventory": inventory,
        "inventory_checksum": sha256_json(inventory),
    }
    freshness_inventory: list[dict] = []
    excluded_input_inventory = sorted(
        [
            {
                "repo_relative_path": item["repo_relative_path"],
                "size_bytes": item["size_bytes"],
                "sha256": item["pdf_sha256"],
            }
            for item in documents
        ],
        key=lambda item: item["repo_relative_path"],
    )
    freshness_scan = {
        "schema_version": (
            "broker_reports_pdf_structural_holdout_freshness_scan_private_v1"
        ),
        "root_repo_relative_path": "local/stage2",
        "excluded_repo_relative_root": (
            "local/stage2/broker_reports_pdf_holdout_test_output"
        ),
        "excluded_input_inventory": excluded_input_inventory,
        "experiment_roots": [],
        "inventory": freshness_inventory,
        "inventory_checksum": sha256_json(
            {
                "excluded_input_inventory": excluded_input_inventory,
                "experiment_roots": [],
                "inventory": freshness_inventory,
            }
        ),
    }
    return runtime.build_preregistration(
        documents=documents,
        targets=targets,
        frozen_source=source_freeze,
        freshness_scan=freshness_scan,
        execution_class=execution_class,
    )


def _eligibility_page() -> dict:
    return {
        "page_ref": "page-ref",
        "page_number": 1,
        "layout_page_width": 600.0,
        "layout_page_height": 800.0,
    }


def _eligibility_candidate(
    *, parser_ordinal: int = 1, table_ref: str = "table-ref"
) -> dict:
    cells = []
    contributing = []
    for row in range(1, 5):
        for column in range(1, 4):
            word_ref = f"word-{parser_ordinal}-{row}-{column}"
            contributing.append(word_ref)
            cells.append(
                {
                    "row_ordinal": row,
                    "column_ordinal": column,
                    "word_refs": [word_ref],
                }
            )
    return {
        "parser_ordinal": parser_ordinal,
        "table_candidate_ref": table_ref,
        "table_strategy_ref": "ruled_lines_v0",
        "geometry_confidence": 0.95,
        "rows_total": 4,
        "columns_total": 3,
        "cell_inventory": cells,
        "contributing_word_refs": contributing,
        "ruling_evidence_total": 12,
        "table_reconstruction_status": "candidate",
    }


def _terminal(runtime, preregistration: dict, preregistration_sha256: str) -> dict:
    execution_v3 = (
        preregistration.get("schema_version")
        == PDF_STRUCTURAL_HOLDOUT_PREREGISTRATION_SCHEMA_V3
    )
    provider_config = asdict(
        PdfGridProviderConfig(
            provider_profile="google_gemini",
            model_id="models/gemini-3.5-flash",
            maximum_output_tokens=8192,
            maximum_counted_input_tokens=20_000,
            thinking_level="minimal",
        )
    )
    provider_config_hash = sha256_json(provider_config)
    journal = []
    for target_index in range(1, 4):
        target_id = f"holdout_{target_index:03d}"
        package = preregistration["targets"][target_index - 1]["visual_package"]
        evidence_revision = sha256_json(
            {
                "package_hash": package["package_hash"],
                "provider_config_hash": provider_config_hash,
                "model_view_hash": sha256_json(package["model_facing"]),
                "output_schema_hash": sha256_json(package["output_schema"]),
                "holdout_id": preregistration["holdout_id"],
            }
        )
        task_id = "pdfvisualtopotask_" + sha256_json(
            {
                "holdout_id": preregistration["holdout_id"],
                "target_id": target_id,
                "package_hash": package["package_hash"],
                "evidence_revision": evidence_revision,
                "model_id": "models/gemini-3.5-flash",
            }
        )[:24]
        for attempt in (1, 2):
            journal.append(
                {
                    "schema_version": PDF_STRUCTURAL_HOLDOUT_JOURNAL_SCHEMA,
                    "target_id": target_id,
                    "attempt_number": attempt,
                    "task_id": task_id,
                    "job_key": f"{task_id}|a{attempt}",
                    "evidence_revision": evidence_revision,
                    "provider_config_hash": provider_config_hash,
                    "count_tokens": {},
                    "provider_attempt": {},
                    "provider_result": {},
                    "topology_response": None,
                    "assembly": None,
                    "failure_code": (
                        "provider_not_called_fixture"
                        if attempt == 1
                        else (
                            "pdf_structural_holdout_previous_attempt_not_started"
                        )
                    ),
                    "failure_class": "typed_test_terminal",
                    "provider_generate_call_performed": False,
                }
            )
    prereg_targets = {
        target["target_id"]: target for target in preregistration["targets"]
    }
    terminal_targets = {}
    for target_id, target in prereg_targets.items():
        terminal_target = {
            "scope": {
                "target_id": target_id,
                "document_id": target["document_id"],
                "page_number": target["page_number"],
                "parser_ordinal": target["parser_ordinal"],
            },
            "parser_observation": copy.deepcopy(target["parser_observation"]),
            "parser_geometry_observation": copy.deepcopy(
                target["parser_geometry_observation"]
            ),
            "visual_package": copy.deepcopy(target["visual_package"]),
            "assemblies": [],
            "hypothesis_set": {"fixture": "typed_no_evidence"},
            "repeatability": {"passed": False},
            "consensus_result": {
                "terminal_status": "blocked_no_valid_evidence",
                "result_checksum": hashlib.sha256(target_id.encode("ascii")).hexdigest(),
            },
            "accepted_binding": None,
            "materialization": None,
        }
        if execution_v3:
            terminal_target.update(
                {
                    "execution_contract": copy.deepcopy(
                        target["execution_contract"]
                    ),
                    "window_stitches": [],
                    "window_runtime_result_checksum": None,
                }
            )
        if preregistration["execution_class"] in {
            "fresh_holdout_v2",
            "fresh_holdout_v3",
            "fresh_holdout_v4",
            "fresh_holdout_v5",
        }:
            terminal_target["eligibility_observation"] = copy.deepcopy(
                target["eligibility_observation"]
            )
        terminal_targets[target_id] = terminal_target
    terminal = {
        "schema_version": (
            PDF_STRUCTURAL_HOLDOUT_TERMINAL_SCHEMA_V3
            if execution_v3
            else (
                PDF_STRUCTURAL_HOLDOUT_TERMINAL_SCHEMA_V2
                if preregistration["execution_class"]
                in {
                    "fresh_holdout_v2",
                    "fresh_holdout_v3",
                    "fresh_holdout_v4",
                    "fresh_holdout_v5",
                }
                else PDF_STRUCTURAL_HOLDOUT_TERMINAL_SCHEMA
            )
        ),
        "policy_version": preregistration["policy_version"],
        "holdout_id": preregistration["holdout_id"],
        "execution_class": preregistration["execution_class"],
        "certification_eligible": preregistration["certification_eligible"],
        "corpus_policy": preregistration["corpus_policy"],
        "preregistration_file_sha256": preregistration_sha256,
        "source_freeze": copy.deepcopy(preregistration["frozen_source"]),
        "provider_qualification": {
            "status": "qualified",
            "provider_profile": "google_gemini",
            "provider_profile_revision": "fixture-revision",
            "requested_model_id": "models/gemini-3.5-flash",
            "resolved_model_id": "models/gemini-3.5-flash",
            "exact_model_match": True,
            "image_input_supported": True,
            "structured_output_supported": True,
            "maximum_output_tokens": 8192,
            "maximum_input_tokens": 1_000_000,
            "http_status": 200,
            "response_hash": hashlib.sha256(b"qualification").hexdigest(),
            "native_provider_transport": True,
            "credentials_from_openwebui_connection": True,
            "hidden_retry": False,
            "provider_failover": False,
        },
        "provider_config": provider_config,
        "journal": journal,
        "targets": terminal_targets,
        "new_provider_generate_calls": 0,
        **(
            {
                "new_provider_count_token_calls": 3,
                "expected_provider_count_token_calls": 6,
                "expected_provider_generate_calls": 6,
            }
            if execution_v3
            else {}
        ),
        "reference_process_started": False,
    }
    _refresh_terminal(runtime, terminal)
    return terminal


def _refresh_preregistration_checksum(value: dict) -> None:
    value.pop("payload_checksum", None)
    value["payload_checksum"] = sha256_json(value)


def _refresh_terminal(runtime, value: dict) -> None:
    value["terminal_seal"] = runtime.terminal_seal(
        preregistration_file_sha256=value["preregistration_file_sha256"],
        source_freeze=value["source_freeze"],
        execution_class=value["execution_class"],
        certification_eligible=value["certification_eligible"],
        corpus_policy=value["corpus_policy"],
        provider_qualification=value["provider_qualification"],
        provider_config=value["provider_config"],
        journal=value["journal"],
        targets=value["targets"],
        new_provider_generate_calls=value["new_provider_generate_calls"],
        new_provider_count_token_calls=value.get(
            "new_provider_count_token_calls"
        ),
        expected_provider_count_token_calls=value.get(
            "expected_provider_count_token_calls"
        ),
        expected_provider_generate_calls=value.get(
            "expected_provider_generate_calls"
        ),
        reference_process_started=value["reference_process_started"],
    )
    value["terminal_seal_hash"] = sha256_json(value["terminal_seal"])
    value.pop("artifact_checksum", None)
    value["artifact_checksum"] = sha256_json(value)


def _mark_first_attempt_performed(
    terminal: dict, preregistration: dict
) -> None:
    entry = terminal["journal"][0]
    target = preregistration["targets"][0]
    package = target["visual_package"]
    canonical_schema_hash = hashlib.sha256(b"canonical-schema").hexdigest()
    adapted_schema_hash = hashlib.sha256(b"adapted-schema").hexdigest()
    counted = {
        "total_tokens": 10,
        "prompt_tokens_details": [],
        "http_status": 200,
        "request_hash": hashlib.sha256(b"count-request").hexdigest(),
        "response_hash": hashlib.sha256(b"count-response").hexdigest(),
        "canonical_schema_hash": canonical_schema_hash,
        "adapted_schema_hash": adapted_schema_hash,
        "schema_transform_count": 0,
        "model_requested": "models/gemini-3.5-flash",
        "transport_identity": "gemini_count_tokens_generate_content_request",
        "within_hard_guard": True,
    }
    attempt = {
        "task_id": entry["task_id"],
        "attempt_id": f"{entry['task_id']}_a1",
        "attempt_number": 1,
        "attempt_lineage": [],
        "provider": "google",
        "provider_profile": "google_gemini",
        "provider_profile_revision": "fixture-revision",
        "model_requested": "models/gemini-3.5-flash",
        "model_resolved": "models/gemini-3.5-flash",
        "adapter_identity": "fixture-adapter-v1",
        "transport_identity": (
            "gemini_generate_content_native_table_crop_json_schema"
        ),
        "request_hash": hashlib.sha256(b"generate-request").hexdigest(),
        "crop_sha256": package["crop_identity"]["crop_sha256"],
        "model_view_hash": sha256_json(package["model_facing"]),
        "canonical_schema_hash": canonical_schema_hash,
        "adapted_schema_hash": adapted_schema_hash,
        "schema_transform_count": 0,
        "started_at": "2026-07-14T00:00:00+00:00",
        "ended_at": "2026-07-14T00:00:01+00:00",
        "duration_ms": 1.0,
        "http_status": 200,
        "provider_response_id": "fixture-response",
        "usage": {
            "input_tokens": 10,
            "output_tokens": 2,
            "total_tokens": 12,
        },
        "finish_reason": "STOP",
        "thinking_level": "minimal",
        "parse_result": "parsed_object",
        "terminal_failure_class": None,
        "hidden_retry": False,
        "provider_failover": False,
    }
    topology = {"fixture": "valid-provider-json"}
    result = {
        "attempt": copy.deepcopy(attempt),
        "json_output": copy.deepcopy(topology),
        "text": "{}",
        "raw_private_response": {},
        "response_bytes": 2,
        "response_hash": hashlib.sha256(b"{}").hexdigest(),
        "visible_output_bytes": 2,
        "visible_output_hash": hashlib.sha256(b"{}").hexdigest(),
    }
    entry.update(
        {
            "count_tokens": counted,
            "provider_attempt": attempt,
            "provider_result": result,
            "topology_response": topology,
            "failure_code": "pdf_topology_assembly_binding_failed",
            "failure_class": "contract_or_terminal_failure",
            "provider_generate_call_performed": True,
        }
    )
    terminal["journal"][1]["failure_code"] = "provider_not_called_fixture"
    if "new_provider_count_token_calls" in terminal:
        terminal["new_provider_count_token_calls"] += 1
    terminal["new_provider_generate_calls"] = 1


def _accepted_scoring_target(preregistered_target: dict) -> dict:
    package = copy.deepcopy(preregistered_target["visual_package"])
    candidate_ids = sorted(package["private_candidate_dictionary"])
    if len(candidate_ids) != 4:
        raise AssertionError("fixture candidate count drift")
    binding = {
        "schema_version": "broker_reports_pdf_hybrid_binding_output_v1",
        "package_id": package["package_id"],
        "crop_sha256": package["crop_identity"]["crop_sha256"],
        "candidate_dictionary_hash": package["candidate_dictionary_hash"],
        "decision": "bound",
        "row_count": 2,
        "column_count": 2,
        "header_rows": [],
        "header_hierarchy": [],
        "rows": [
            {
                "row_ordinal": 1,
                "row_kind": "data",
                "cells": [[candidate_ids[0]], [candidate_ids[1]]],
            },
            {
                "row_ordinal": 2,
                "row_kind": "data",
                "cells": [[candidate_ids[2]], [candidate_ids[3]]],
            },
        ],
        "spans": [],
        "uncertainty_codes": [],
    }
    materialization = {
        "package_id": package["package_id"],
        "binding_output_hash": sha256_json(binding),
        "crop_sha256": binding["crop_sha256"],
        "candidate_dictionary_hash": binding["candidate_dictionary_hash"],
        "row_count": 2,
        "column_count": 2,
        "header_rows": [],
        "header_hierarchy": [],
        "spans": [],
        "selected_candidate_ids": candidate_ids,
        "omitted_candidate_ids": [],
        "extra_candidate_ids": [],
        "duplicate_candidate_ids": [],
        "model_invented_values_total": 0,
    }
    return {
        "consensus_result": {"terminal_status": "accepted_supplied_consensus"},
        "visual_package": package,
        "accepted_binding": binding,
        "materialization": materialization,
    }


def _load_script_module(filename: str):
    path = Path(__file__).resolve().parents[1] / "scripts" / filename
    name = "holdout_test_" + filename.replace(".", "_")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _projection() -> dict:
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
                "page_ref": "page-ref",
                "bbox_ref": bbox_ref,
                "text": text,
                "geometry_reading_order": ordinal,
                "text_checksum_ref": f"text-checksum-{ordinal}",
                "source_value_ref": f"source-{ordinal}",
            }
        )
    vectors = []
    vector_specs = (
        [0.0, 0.0, 0.0, 100.0],
        [100.0, 0.0, 100.0, 100.0],
        [200.0, 0.0, 200.0, 100.0],
        [0.0, 0.0, 200.0, 0.0],
        [0.0, 50.0, 200.0, 50.0],
        [0.0, 100.0, 200.0, 100.0],
    )
    for ordinal, bbox in enumerate(vector_specs, start=1):
        bbox_ref = f"vector-bbox-{ordinal}"
        bboxes.append({"bbox_ref": bbox_ref, "bbox": list(bbox)})
        vectors.append(
            {
                "parser_ordinal": ordinal,
                "object_ref": f"vector-{ordinal}",
                "page_ref": "page-ref",
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


def _crop_manifest(*, pdf_sha256: str, png_bytes: bytes) -> dict:
    value = {
        "schema_version": "broker_reports_pdf_table_crop_v1",
        "policy_version": "pdf_table_raster_policy_v1",
        "crop_id": "crop-1",
        "document_ref": "document-ref",
        "pdf_sha256": pdf_sha256,
        "page_number": 1,
        "table_ref": "table-ref",
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


def _windowed_330_fixture() -> tuple[dict, dict, dict, dict, list[dict]]:
    projection = _projection_330()
    parser_contracts = PdfDualOracleContractFactory().create()
    observation = parser_contracts.build_parser_observation_from_word_atoms(
        document_ref="document-window",
        pdf_sha256="pdf-window-sha",
        page_ref="page-window-1",
        page_number=1,
        table_ref="table-window-1",
        table_bbox=[0.0, 0.0, 200.0, 100.0],
        pdf_text_layer_projection=projection,
    )
    geometry = PdfParserGeometryFactory().create().build_observation(
        document_ref="document-window",
        pdf_sha256="pdf-window-sha",
        page_ref="page-window-1",
        page_number=1,
        table_ref="table-window-1",
        table_bbox=[0.0, 0.0, 200.0, 100.0],
        pdf_text_layer_projection=projection,
    )
    runtime = PdfStructuralRepairRuntimeFactory().create(
        provider=_StrictWindowProvider()
    )
    plan = runtime.plan_windowed_target(observation)
    full_png = b"holdout-full-ledger-330"
    full_package = runtime.build_windowed_ledger_package(
        parser_observation=observation,
        crop_manifest=_window_crop_manifest(
            png_bytes=full_png,
            crop_id="holdout-full-ledger-330",
            bbox=[0.0, 0.0, 200.0, 100.0],
        ),
    )
    visual = PdfVisualTopologyFactory().create()
    window_inputs: list[dict] = []
    for window in plan["windows"]:
        png_bytes = (
            b"holdout-window-330-"
            + str(window["window_index"]).encode("ascii")
        )
        package = visual.build_window_package(
            parser_observation=observation,
            full_package=full_package,
            window_plan=plan,
            window=window,
            crop_manifest=_window_crop_manifest(
                png_bytes=png_bytes,
                crop_id=f"holdout-window-{window['window_index']}",
                bbox=window["crop_bbox"],
            ),
        )
        window_inputs.append(
            {
                "window_id": window["window_id"],
                "window_package": package,
                "png_bytes": png_bytes,
            }
        )
    return observation, geometry, full_package, plan, window_inputs


def _projection_330() -> dict:
    bboxes: list[dict] = []
    words: list[dict] = []
    ordinal = 0
    for band_index, band_size in enumerate((165, 165)):
        for item_index in range(band_size):
            ordinal += 1
            left_column = item_index % 2 == 0
            bbox = [
                10.0 if left_column else 110.0,
                10.0 if band_index == 0 else 60.0,
                90.0 if left_column else 190.0,
                40.0 if band_index == 0 else 90.0,
            ]
            bbox_ref = f"window-bbox-{ordinal}"
            bboxes.append({"bbox_ref": bbox_ref, "bbox": bbox})
            words.append(
                {
                    "parser_ordinal": ordinal,
                    "word_ref": f"window-word-{ordinal}",
                    "page_ref": "page-window-1",
                    "bbox_ref": bbox_ref,
                    "text": f"private-value-{ordinal}",
                    "geometry_reading_order": ordinal,
                    "text_checksum_ref": f"window-text-{ordinal}",
                    "source_value_ref": f"window-source-{ordinal}",
                }
            )
    vectors: list[dict] = []
    for vector_ordinal, bbox in enumerate(
        (
            [0.0, 0.0, 0.0, 100.0],
            [100.0, 0.0, 100.0, 100.0],
            [200.0, 0.0, 200.0, 100.0],
            [0.0, 0.0, 200.0, 0.0],
            [0.0, 50.0, 200.0, 50.0],
            [0.0, 100.0, 200.0, 100.0],
        ),
        start=1,
    ):
        bbox_ref = f"window-vector-bbox-{vector_ordinal}"
        bboxes.append({"bbox_ref": bbox_ref, "bbox": list(bbox)})
        vectors.append(
            {
                "parser_ordinal": vector_ordinal,
                "object_ref": f"window-vector-{vector_ordinal}",
                "page_ref": "page-window-1",
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


def _window_crop_manifest(
    *, png_bytes: bytes, crop_id: str, bbox: list[float]
) -> dict:
    crop_bbox = [float(value) for value in bbox]
    width = 400
    height = max(
        1,
        round(width * (crop_bbox[3] - crop_bbox[1]) / 200.0),
    )
    value = {
        "schema_version": "broker_reports_pdf_table_crop_v1",
        "policy_version": "pdf_table_raster_policy_v1",
        "crop_id": crop_id,
        "document_ref": "document-window",
        "pdf_sha256": "pdf-window-sha",
        "page_number": 1,
        "table_ref": "table-window-1",
        "declared_table_bbox": crop_bbox,
        "rendered_bbox": crop_bbox,
        "source_coordinate_space": "pdf_top_left_points",
        "pixel_coordinate_space": "crop_top_left_pixels",
        "source_to_pixel_transform": {
            "scale_x": 2.0,
            "scale_y": 2.0,
            "translate_source_x": crop_bbox[0],
            "translate_source_y": crop_bbox[1],
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
        "png_bytes": len(png_bytes),
        "png_sha256": hashlib.sha256(png_bytes).hexdigest(),
        "lossless": True,
        "silent_resize_performed": False,
    }
    value["manifest_hash"] = sha256_json(value)
    return value


def _window_response(
    *, package_id: str, header_row_count: int, rows: list[float]
) -> dict:
    return {
        "schema_version": PDF_VISUAL_TOPOLOGY_RESPONSE_SCHEMA,
        "package_id": package_id,
        "decision": "bound",
        "alternatives_complete": True,
        "hypotheses": [
            {
                "hypothesis_key": "primary",
                "row_boundaries": rows,
                "column_boundaries": [0.0, 0.5, 1.0],
                "header_row_count": header_row_count,
                "spans": [],
                "header_hierarchy": [],
                "continuation_required": False,
                "uncertainty_codes": [],
            }
        ],
        "uncertainty_codes": [],
    }


def _refresh_execution_contract_checksum(value: dict) -> None:
    value.pop("execution_contract_checksum", None)
    value["execution_contract_checksum"] = sha256_json(value)


def _legacy_preregistration(
    runtime,
    value: dict,
    *,
    schema_version: str,
) -> dict:
    legacy = copy.deepcopy(value)
    legacy["schema_version"] = schema_version
    for target in legacy["targets"]:
        target.pop("execution_contract", None)
    legacy["holdout_id"] = runtime._expected_holdout_id(
        documents=legacy["documents"],
        targets=legacy["targets"],
        frozen_source=legacy["frozen_source"],
        freshness_scan=legacy["freshness_scan"],
        execution_class=legacy["execution_class"],
    )
    _refresh_preregistration_checksum(legacy)
    return legacy


if __name__ == "__main__":
    unittest.main()
