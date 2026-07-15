from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import fitz

from broker_reports_gate1.artifact_models import ArtifactAccessContext
from broker_reports_gate1.artifact_resolver import ArtifactResolver
from broker_reports_gate1.artifact_store import ArtifactStoreError
from broker_reports_gate1.artifact_retention import build_retention_policy
from broker_reports_gate1.artifact_store import (
    ArtifactStoreConfig,
    ArtifactStoreFactory,
)
from broker_reports_gate1.pdf_structural_repair_shadow import (
    FACTORY_REQUIRED,
    FORBIDDEN,
    PdfStructuralRepairShadowConfig,
    PdfStructuralRepairShadowError,
    PdfStructuralRepairShadowFactory,
    PdfStructuralRepairShadowRuntime,
)
from broker_reports_gate1.pdf_hybrid_contracts import sha256_json
from broker_reports_gate1.pdf_semantic_header_projection import (
    PdfSemanticHeaderProjectionError,
)
from broker_reports_gate1.pdf_table_intake_contracts import (
    PdfTableIntakeContractFactory,
)
from broker_reports_gate1.pdf_visual_topology import (
    PDF_VISUAL_TOPOLOGY_REGION_PROPOSAL_REVISION,
    PDF_VISUAL_TOPOLOGY_RESPONSE_SCHEMA,
)


class _ProviderBoundary:
    def __init__(
        self,
        *,
        fail_message: str | None = None,
        header_row_count: int = 1,
        ambiguous: bool = False,
        page_regions: int = 1,
        page_presence: str = "present",
        page_uncertain: bool = False,
    ) -> None:
        self.fail_message = fail_message
        self.header_row_count = header_row_count
        self.ambiguous = ambiguous
        self.page_regions = page_regions
        self.page_presence = page_presence
        self.page_uncertain = page_uncertain
        self.qualification_calls = 0
        self.count_calls = 0
        self.generate_calls = 0

    def qualify(self) -> dict:
        self.qualification_calls += 1
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
            "total_tokens": 100,
            "model_requested": "models/gemini-3.5-flash",
            "within_hard_guard": True,
        }

    def invoke(
        self,
        *,
        task_id: str,
        model_view: dict,
        attempt_number: int,
        attempt_lineage: list[str],
        **kwargs,
    ) -> dict:
        self.generate_calls += 1
        if self.fail_message:
            raise RuntimeError(self.fail_message)
        attempt_id = f"{task_id}_a{attempt_number}"
        window = model_view.get("window")
        header_row_count = self.header_row_count
        rows = None
        if isinstance(window, dict):
            core_y = window["core_y_normalized_in_crop"]
            if window["window_index"] == 1:
                rows = [0.0, core_y[1], 1.0]
            else:
                rows = [0.0, core_y[0], 1.0]
                header_row_count = 0
        topology = _topology_response(
            model_view["identity"]["package_id"],
            header_row_count=header_row_count,
            rows=rows,
            ambiguous=self.ambiguous,
        )
        if model_view.get("proposal_scope") == "candidate_crop":
            topology = _candidate_region_response(topology)
        elif model_view.get("proposal_scope") == "page_level":
            topology = _page_region_response(
                topology,
                regions=self.page_regions,
                table_presence=self.page_presence,
                uncertain=self.page_uncertain,
            )
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
                    "input_tokens": 100,
                    "output_tokens": 20,
                    "total_tokens": 120,
                },
                "finish_reason": "STOP",
                "terminal_failure_class": None,
                "hidden_retry": False,
                "provider_failover": False,
            },
            "json_output": topology,
            "raw_private_response": {
                "provider_secret": "private-provider-response"
            },
            "visible_output_bytes": 100,
            "response_bytes": 200,
        }


class _FailingSemanticProjection:
    def project(self, **kwargs) -> dict:
        raise PdfSemanticHeaderProjectionError(
            "pdf_semantic_header_projection_test_failure"
        )


class PdfStructuralRepairShadowTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.store = ArtifactStoreFactory(
            ArtifactStoreConfig(
                mode="sqlite",
                sqlite_path=root / "artifacts.sqlite3",
                payload_root=root / "payloads",
            )
        ).create()
        self.context = ArtifactAccessContext(
            user_id="user_shadow",
            case_id="case_shadow",
            chat_id="chat_shadow",
            workspace_model_id="broker_reports_gate1",
            normalization_run_id="normalization_shadow",
        )
        self.retention = build_retention_policy(mode="api_smoke")
        self.pdf_bytes = _pdf_bytes()
        self.pdf_sha256 = hashlib.sha256(self.pdf_bytes).hexdigest()

    def test_factory_anchors_and_disabled_path_are_deterministic(self) -> None:
        self.assertIn("PdfStructuralRepairShadowFactory.create", FACTORY_REQUIRED)
        self.assertIn("PdfTableIntakeContractFactory.create", FACTORY_REQUIRED)
        self.assertIn("must not invoke structural stages", FORBIDDEN)
        self.assertIn("processability from morphology metadata", FORBIDDEN)
        runtime = PdfStructuralRepairShadowFactory().create(provider=None)

        first = runtime.run(
            store=self.store,
            package={"customer": "private-customer-value"},
            context=self.context,
            retention_policy=self.retention,
            pdf_bytes_by_sha256={},
        )
        second = runtime.run(
            store=self.store,
            package={},
            context=self.context,
            retention_policy=self.retention,
            pdf_bytes_by_sha256={},
        )
        semantic_only_runtime = PdfStructuralRepairShadowFactory(
            PdfStructuralRepairShadowConfig(
                enabled=False,
                semantic_header_shadow_enabled=True,
            )
        ).create(provider=None)
        semantic_only = semantic_only_runtime.run(
            store=self.store,
            package={"customer": "private-customer-value"},
            context=self.context,
            retention_policy=self.retention,
            pdf_bytes_by_sha256={},
        )

        self.assertEqual(first, second)
        self.assertFalse(semantic_only["enabled"])
        self.assertFalse(
            semantic_only["summary"]["semantic_header_shadow_enabled"]
        )
        self.assertEqual([], semantic_only["semantic_projection_refs"])
        self.assertFalse(first["enabled"])
        self.assertEqual("non_authoritative", first["summary"]["authority_state"])
        self.assertFalse(first["summary"]["production_ready"])
        self.assertFalse(
            first["summary"]["production_gate2_selection_changed"]
        )
        self.assertEqual([], self.store.list_by_run("normalization_shadow"))
        with self.assertRaisesRegex(
            PdfStructuralRepairShadowError,
            "pdf_structural_repair_shadow_factory_required",
        ):
            PdfStructuralRepairShadowRuntime(
                config=PdfStructuralRepairShadowConfig(),
                contracts=None,
                geometry=None,
                raster=None,
                visual=None,
                structural_runtime=None,
            )

    def test_real_shadow_path_uses_two_oracles_and_persists_private_state(self) -> None:
        provider = _ProviderBoundary()
        runtime = PdfStructuralRepairShadowFactory(
            PdfStructuralRepairShadowConfig(enabled=True)
        ).create(provider=provider)

        result = self._run(runtime, _package(self.pdf_sha256))

        self.assertEqual(1, provider.qualification_calls)
        self.assertEqual(2, provider.count_calls)
        self.assertEqual(2, provider.generate_calls)
        self.assertEqual(
            1,
            result["summary"]["accepted_supplied_consensus_tables"],
        )
        self.assertEqual(
            "accepted_supplied_consensus",
            result["summary"]["target_outcomes"][0]["terminal_status"],
        )
        self.assertEqual(
            {"success": 1, "partial": 0, "failed": 0},
            result["file_processing_outcomes"]["status_counts"],
        )
        self.assertEqual(1, len(result["private_target_state_refs"]))
        self.assertEqual(1, len(result["runtime_result_refs"]))
        self.assertEqual(1, len(result["repeat_history_refs"]))
        self.assertEqual([], result["private_diagnostic_refs"])
        self.assertFalse(result["summary"]["semantic_header_shadow_enabled"])
        self.assertEqual([], result["semantic_projection_refs"])

        target_record = self.store.list_by_type(
            self.context.normalization_run_id,
            "broker_reports_pdf_structural_repair_target_state_v1",
        )[0]
        runtime_record = self.store.list_by_type(
            self.context.normalization_run_id,
            "broker_reports_pdf_structural_repair_runtime_result_v1",
        )[0]
        summary_record = self.store.list_by_type(
            self.context.normalization_run_id,
            "broker_reports_pdf_structural_repair_shadow_summary_v1",
        )[0]
        target_payload = self.store.read_payload(target_record)
        runtime_payload = self.store.read_payload(runtime_record)
        safe_payload = self.store.read_payload(summary_record)

        self.assertEqual("private_case", target_record.visibility)
        self.assertEqual("private_case", runtime_record.visibility)
        self.assertIn("private-customer-value", repr(target_payload))
        self.assertNotIn("intake_decisions", target_payload)
        self.assertIn("private-provider-response", repr(runtime_payload))
        self.assertEqual("safe_internal", summary_record.visibility)
        self.assertNotIn("private-customer-value", repr(safe_payload))
        self.assertNotIn("private-provider-response", repr(safe_payload))
        self.assertFalse(safe_payload["customer_values_included"])
        self.assertFalse(safe_payload["crop_bytes_included"])
        self.assertFalse(safe_payload["raw_provider_response_included"])

    def test_guided_intake_is_separate_default_disabled_one_call_shadow(self) -> None:
        provider = _ProviderBoundary()
        runtime = PdfStructuralRepairShadowFactory(
            PdfStructuralRepairShadowConfig(
                enabled=True,
                vlm_guided_intake_enabled=True,
            )
        ).create(provider=provider)

        result = self._run(runtime, _package(self.pdf_sha256))

        self.assertTrue(result["summary"]["vlm_guided_intake_enabled"])
        self.assertEqual((1, 1), (provider.count_calls, provider.generate_calls))
        self.assertEqual(0, result["summary"]["accepted_supplied_consensus_tables"])
        self.assertEqual(1, result["summary"]["accepted_physical_structure_tables"])
        self.assertEqual(
            "accepted_physical_structure",
            result["summary"]["target_outcomes"][0]["terminal_status"],
        )
        self.assertEqual([], result["repeat_history_refs"])
        self.assertFalse(
            result["summary"]["target_outcomes"][0]["repeat_history_persisted"]
        )
        state_record = self.store.list_by_type(
            self.context.normalization_run_id,
            "broker_reports_pdf_structural_repair_target_state_v1",
        )[0]
        state = self.store.read_payload(state_record)
        self.assertEqual("guided_candidate_crop", state["execution_mode"])
        self.assertTrue(state["vlm_guided_intake_enabled"])
        self.assertNotIn("window_plan", state)
        intake_decisions = state["intake_decisions"]
        self.assertEqual("plausible", intake_decisions["detection"]["decision"])
        self.assertEqual(
            "processable",
            intake_decisions["processability"]["decision"],
        )
        self.assertEqual(
            100,
            intake_decisions["technical_facts"][
                "counted_input_tokens"
            ],
        )
        self.assertEqual(
            "not_evaluated",
            intake_decisions["holdout"]["decision"],
        )
        self.assertEqual(
            [],
            PdfTableIntakeContractFactory()
            .create()
            .validate_decisions(intake_decisions),
        )
        self.assertEqual(
            "ruled_lines_v0",
            intake_decisions["metadata"]["parser_morphology"][
                "table_strategy_ref"
            ],
        )
        self.assertNotIn(
            "private-customer-value", repr(state_record.safe_metadata)
        )
        guided_records = self.store.list_by_type(
            self.context.normalization_run_id,
            "broker_reports_pdf_vlm_guided_intake_result_v1",
        )
        self.assertEqual(1, len(guided_records))
        guided = self.store.read_payload(guided_records[0])
        self.assertEqual(1, guided["new_provider_count_token_calls"])
        self.assertEqual(1, guided["new_provider_generate_calls"])
        self.assertFalse(guided["production_gate2_selection_changed"])
        self.assertNotIn("private-provider-response", repr(result["summary"]))

    def test_guided_runtime_failure_seals_upstream_intake_terminal(self) -> None:
        provider = _ProviderBoundary(fail_message="private-provider-failure")
        runtime = PdfStructuralRepairShadowFactory(
            PdfStructuralRepairShadowConfig(
                enabled=True,
                vlm_guided_intake_enabled=True,
            )
        ).create(provider=provider)

        result = self._run(runtime, _package(self.pdf_sha256))

        self.assertEqual((1, 1), (provider.count_calls, provider.generate_calls))
        self.assertEqual([], result["runtime_result_refs"])
        state_record = self.store.list_by_type(
            self.context.normalization_run_id,
            "broker_reports_pdf_structural_repair_target_state_v1",
        )[0]
        decisions = self.store.read_payload(state_record)["intake_decisions"]
        self.assertEqual(
            "absent_due_to_upstream_failure",
            decisions["detection"]["decision"],
        )
        self.assertEqual(
            "unsupported",
            decisions["processability"]["decision"],
        )
        self.assertEqual(
            ["pdf_vlm_guided_intake_runtime_execution_failed"],
            decisions["technical_facts"][
                "upstream_failure_reason_codes"
            ],
        )
        self.assertEqual(
            [],
            PdfTableIntakeContractFactory().create().validate_decisions(
                decisions
            ),
        )

    def test_guided_intake_blocks_missing_page_geometry_before_model_calls(
        self,
    ) -> None:
        provider = _ProviderBoundary()
        runtime = PdfStructuralRepairShadowFactory(
            PdfStructuralRepairShadowConfig(
                enabled=True,
                vlm_guided_intake_enabled=True,
            )
        ).create(provider=provider)
        package = _package(self.pdf_sha256)
        page = package["private_normalized_source_payloads"][0][
            "pdf_text_layer_projection"
        ]["page_inventory"][0]
        page.pop("layout_page_width")
        page.pop("layout_page_height")

        result = self._run(runtime, package)

        self.assertEqual(1, provider.qualification_calls)
        self.assertEqual((0, 0), (provider.count_calls, provider.generate_calls))
        self.assertEqual([], result["runtime_result_refs"])
        self.assertEqual(1, len(result["private_target_state_refs"]))
        self.assertEqual(
            "pdf_structural_repair_shadow_intake_unsupported",
            result["summary"]["target_outcomes"][0]["terminal_status"],
        )
        state_record = self.store.list_by_type(
            self.context.normalization_run_id,
            "broker_reports_pdf_structural_repair_target_state_v1",
        )[0]
        state = self.store.read_payload(state_record)
        self.assertEqual(
            "unsupported",
            state["intake_decisions"]["processability"]["decision"],
        )
        self.assertIn(
            "page_bbox_invalid",
            state["intake_decisions"]["processability"]["reason_codes"],
        )
        outcome = result["file_processing_outcomes"]["outcomes"][0]
        self.assertEqual(("failed", "parsing", "parser_failed"), (
            outcome["status"],
            outcome["stage"],
            outcome["reason_code"],
        ))

    def test_guided_intake_keeps_193_atoms_in_one_crop_without_windows(self) -> None:
        provider = _ProviderBoundary()
        runtime = PdfStructuralRepairShadowFactory(
            PdfStructuralRepairShadowConfig(
                enabled=True,
                vlm_guided_intake_enabled=True,
            )
        ).create(provider=provider)

        result = self._run(
            runtime,
            _package(self.pdf_sha256, atom_count=193),
        )

        self.assertEqual((1, 1), (provider.count_calls, provider.generate_calls))
        state_record = self.store.list_by_type(
            self.context.normalization_run_id,
            "broker_reports_pdf_structural_repair_target_state_v1",
        )[0]
        state = self.store.read_payload(state_record)
        self.assertEqual("guided_candidate_crop", state["execution_mode"])
        self.assertNotIn("window_plan", state)
        self.assertEqual(
            193,
            state["visual_package"]["component_accounting"]["atom_count"],
        )
        self.assertEqual(1, len(result["runtime_result_refs"]))

    def test_allowlisted_candidate_less_page_runs_once_and_binds_exact_atoms(
        self,
    ) -> None:
        provider = _ProviderBoundary()
        runtime = PdfStructuralRepairShadowFactory(
            PdfStructuralRepairShadowConfig(
                enabled=True,
                vlm_guided_intake_enabled=True,
                page_allowlist=("page_1",),
            )
        ).create(provider=provider)
        package = _package(self.pdf_sha256)
        projection = package["private_normalized_source_payloads"][0][
            "pdf_text_layer_projection"
        ]
        projection["table_candidate_inventory"] = []

        result = self._run(runtime, package)

        self.assertEqual((1, 1, 1), (
            provider.qualification_calls,
            provider.count_calls,
            provider.generate_calls,
        ))
        self.assertEqual([], result["repeat_history_refs"])
        self.assertEqual(
            "accepted_physical_structure",
            result["summary"]["target_outcomes"][0]["terminal_status"],
        )
        state_record = self.store.get_record_unchecked(
            result["private_target_state_refs"][0]
        )
        state = self.store.read_payload(state_record)
        self.assertEqual("guided_page_level", state["execution_mode"])
        self.assertEqual(
            100,
            state["intake_decisions"]["technical_facts"][
                "counted_input_tokens"
            ]
        )
        self.assertTrue(
            state["private_raster"]["manifest"][
                "full_page_identity_verified"
            ]
        )
        runtime_record = self.store.get_record_unchecked(
            result["runtime_result_refs"][0]
        )
        payload = self.store.read_payload(runtime_record)
        self.assertEqual(
            "broker_reports_pdf_vlm_guided_page_intake_result_v1",
            runtime_record.artifact_type,
        )
        self.assertEqual(
            "accepted_physical_structure",
            payload["binding_result"]["runtime_terminal_status"],
        )
        self.assertEqual(
            4,
            payload["binding_result"]["source_accounting"][
                "unique_region_word_refs_included"
            ],
        )
        self.assertEqual(
            100,
            payload["finalized_intake_decisions"]["technical_facts"][
                "counted_input_tokens"
            ],
        )
        self.assertFalse(payload["production_gate2_selection_changed"])

    def test_allowlisted_page_can_bind_two_nonoverlapping_regions(self) -> None:
        provider = _ProviderBoundary(page_regions=2)
        runtime = PdfStructuralRepairShadowFactory(
            PdfStructuralRepairShadowConfig(
                enabled=True,
                vlm_guided_intake_enabled=True,
                page_allowlist=("page_1",),
            )
        ).create(provider=provider)

        result = self._run(runtime, _package(self.pdf_sha256))

        payload = self.store.read_payload(
            self.store.get_record_unchecked(result["runtime_result_refs"][0])
        )
        self.assertEqual((1, 1), (provider.count_calls, provider.generate_calls))
        self.assertEqual(2, len(payload["binding_result"]["region_results"]))
        self.assertEqual(
            2,
            payload["binding_result"]["source_accounting"][
                "regions_accepted"
            ],
        )
        self.assertEqual(
            "accepted_physical_structure",
            payload["runtime_terminal_status"],
        )

    def test_page_composite_rejects_resealed_cross_evidence_drift(self) -> None:
        provider = _ProviderBoundary()
        runtime = PdfStructuralRepairShadowFactory(
            PdfStructuralRepairShadowConfig(
                enabled=True,
                vlm_guided_intake_enabled=True,
                page_allowlist=("page_1",),
            )
        ).create(provider=provider)
        package = _package(self.pdf_sha256)
        projection = package["private_normalized_source_payloads"][0][
            "pdf_text_layer_projection"
        ]
        result = self._run(runtime, package)
        payload = self.store.read_payload(
            self.store.get_record_unchecked(result["runtime_result_refs"][0])
        )
        counted_drift = copy.deepcopy(payload)
        intake = counted_drift["finalized_intake_decisions"]
        intake["technical_facts"]["counted_input_tokens"] = 101
        intake.pop("contract_checksum")
        intake["contract_checksum"] = sha256_json(intake)
        counted_drift.pop("result_checksum")
        counted_drift["result_checksum"] = sha256_json(counted_drift)
        self.assertIn(
            "pdf_vlm_guided_page_intake_evidence_binding_invalid",
            runtime._validate_page_intake_result(
                counted_drift,
                expected_pdf_text_layer_projection=projection,
            ),
        )

        projection_drift = copy.deepcopy(payload)
        projection_drift["page_identity"]["projection_checksum"] = "0" * 64
        binding = projection_drift["binding_result"]
        binding["projection_checksum"] = "0" * 64
        binding.pop("result_checksum")
        binding["result_checksum"] = sha256_json(binding)
        projection_drift.pop("result_checksum")
        projection_drift["result_checksum"] = sha256_json(projection_drift)
        self.assertIn(
            "pdf_vlm_guided_page_intake_page_identity_invalid",
            runtime._validate_page_intake_result(
                projection_drift,
                expected_pdf_text_layer_projection=projection,
            ),
        )

        crop_drift = copy.deepcopy(payload)
        manifest = crop_drift["region_crop_manifests"]["region_1"]
        manifest["png_sha256"] = "0" * 64
        manifest.pop("manifest_hash")
        manifest["manifest_hash"] = sha256_json(manifest)
        crop_drift.pop("result_checksum")
        crop_drift["result_checksum"] = sha256_json(crop_drift)
        self.assertIn(
            "pdf_vlm_guided_page_intake_region_crop_binding_invalid",
            runtime._validate_page_intake_result(
                crop_drift,
                expected_pdf_text_layer_projection=projection,
            ),
        )

    def test_absent_page_proposal_never_accepts_a_region_binding(self) -> None:
        provider = _ProviderBoundary(page_regions=0, page_presence="absent")
        runtime = PdfStructuralRepairShadowFactory(
            PdfStructuralRepairShadowConfig(
                enabled=True,
                vlm_guided_intake_enabled=True,
                page_allowlist=("page_1",),
            )
        ).create(provider=provider)

        result = self._run(runtime, _package(self.pdf_sha256))

        payload = self.store.read_payload(
            self.store.get_record_unchecked(result["runtime_result_refs"][0])
        )
        self.assertEqual("no_table_proposed", payload["runtime_terminal_status"])
        self.assertEqual(
            0,
            payload["binding_result"]["source_accounting"][
                "regions_accepted"
            ],
        )
        self.assertEqual({}, payload["region_crop_manifests"])
        self.assertEqual(0, result["summary"]["tables_failed"])
        self.assertIsNone(
            result["summary"]["target_outcomes"][0]["reason_code"]
        )
        self.assertEqual(
            {"success": 1, "partial": 0, "failed": 0},
            result["file_processing_outcomes"]["status_counts"],
        )
        self.assertEqual(
            "implausible",
            payload["finalized_intake_decisions"]["detection"]["decision"],
        )
        self.assertEqual(
            "processable",
            payload["finalized_intake_decisions"]["processability"][
                "decision"
            ],
        )

    def test_uncertain_page_proposal_is_not_sent_to_binder(self) -> None:
        provider = _ProviderBoundary(
            page_regions=0,
            page_presence="uncertain",
            page_uncertain=True,
        )
        runtime = PdfStructuralRepairShadowFactory(
            PdfStructuralRepairShadowConfig(
                enabled=True,
                vlm_guided_intake_enabled=True,
                page_allowlist=("page_1",),
            )
        ).create(provider=provider)

        result = self._run(runtime, _package(self.pdf_sha256))

        payload = self.store.read_payload(
            self.store.get_record_unchecked(result["runtime_result_refs"][0])
        )
        self.assertEqual("proposal_ambiguous", payload["runtime_terminal_status"])
        self.assertIsNone(payload["binding_result"])
        self.assertEqual({}, payload["region_crop_manifests"])
        self.assertEqual(1, result["summary"]["tables_failed"])
        self.assertEqual(
            "consensus_not_reached",
            result["summary"]["target_outcomes"][0]["reason_code"],
        )
        self.assertEqual(
            {"success": 0, "partial": 1, "failed": 0},
            result["file_processing_outcomes"]["status_counts"],
        )
        self.assertEqual(
            "uncertain",
            payload["finalized_intake_decisions"]["detection"]["decision"],
        )
        self.assertEqual(
            "processable",
            payload["finalized_intake_decisions"]["processability"][
                "decision"
            ],
        )

    def test_candidate_less_unallowlisted_page_performs_no_provider_calls(
        self,
    ) -> None:
        provider = _ProviderBoundary()
        runtime = PdfStructuralRepairShadowFactory(
            PdfStructuralRepairShadowConfig(
                enabled=True,
                vlm_guided_intake_enabled=True,
                page_allowlist=("page_not_present",),
            )
        ).create(provider=provider)
        package = _package(self.pdf_sha256)
        package["private_normalized_source_payloads"][0][
            "pdf_text_layer_projection"
        ]["table_candidate_inventory"] = []

        result = self._run(runtime, package)

        self.assertEqual((0, 0, 0), (
            provider.qualification_calls,
            provider.count_calls,
            provider.generate_calls,
        ))
        self.assertEqual([], result["runtime_result_refs"])
        self.assertEqual(0, result["summary"]["tables_selected"])

    def test_plain_page_ref_allowlist_does_not_cross_document_identity(self) -> None:
        package = _package(self.pdf_sha256)
        source = package["private_normalized_source_payloads"][0]
        source["pdf_text_layer_projection"]["table_candidate_inventory"] = []
        package["document_inventory"]["documents"].append(
            {
                "document_id": "document_2",
                "container_format": "pdf",
                "sha256": self.pdf_sha256,
            }
        )
        second_source = copy.deepcopy(source)
        second_source["document_ref"] = "document_2"
        package["private_normalized_source_payloads"].append(second_source)

        ambiguous_provider = _ProviderBoundary()
        ambiguous_runtime = PdfStructuralRepairShadowFactory(
            PdfStructuralRepairShadowConfig(
                enabled=True,
                vlm_guided_intake_enabled=True,
                page_allowlist=("page_1",),
            )
        ).create(provider=ambiguous_provider)
        ambiguous_result = self._run(ambiguous_runtime, package)

        self.assertEqual(
            (0, 0, 0),
            (
                ambiguous_provider.qualification_calls,
                ambiguous_provider.count_calls,
                ambiguous_provider.generate_calls,
            ),
        )
        self.assertEqual(0, ambiguous_result["summary"]["tables_selected"])

        exact_provider = _ProviderBoundary()
        exact_runtime = PdfStructuralRepairShadowFactory(
            PdfStructuralRepairShadowConfig(
                enabled=True,
                vlm_guided_intake_enabled=True,
                page_allowlist=("document_1::page_1",),
            )
        ).create(provider=exact_provider)
        exact_result = self._run(exact_runtime, package)

        self.assertEqual(
            (1, 1, 1),
            (
                exact_provider.qualification_calls,
                exact_provider.count_calls,
                exact_provider.generate_calls,
            ),
        )
        self.assertEqual(1, exact_result["summary"]["tables_selected"])

    def test_page_word_outside_owned_bbox_blocks_before_model_calls(self) -> None:
        provider = _ProviderBoundary()
        runtime = PdfStructuralRepairShadowFactory(
            PdfStructuralRepairShadowConfig(
                enabled=True,
                vlm_guided_intake_enabled=True,
                page_allowlist=("page_1",),
            )
        ).create(provider=provider)
        package = _package(self.pdf_sha256)
        projection = package["private_normalized_source_payloads"][0][
            "pdf_text_layer_projection"
        ]
        projection["table_candidate_inventory"] = []
        next(
            item
            for item in projection["bbox_inventory"]
            if item["bbox_ref"] == "bbox_word_1"
        )["bbox"] = [201.0, 10.0, 210.0, 20.0]

        result = self._run(runtime, package)

        self.assertEqual(
            (1, 0, 0),
            (
                provider.qualification_calls,
                provider.count_calls,
                provider.generate_calls,
            ),
        )
        self.assertEqual([], result["runtime_result_refs"])
        self.assertEqual(1, len(result["private_target_state_refs"]))
        state = self.store.read_payload(
            self.store.get_record_unchecked(
                result["private_target_state_refs"][0]
            )
        )
        self.assertEqual(
            "unsupported",
            state["intake_decisions"]["processability"]["decision"],
        )
        self.assertIn(
            "provenance_unverified",
            state["intake_decisions"]["processability"]["reason_codes"],
        )

    def test_page_binding_exception_persists_final_upstream_intake(self) -> None:
        provider = _ProviderBoundary()
        runtime = PdfStructuralRepairShadowFactory(
            PdfStructuralRepairShadowConfig(
                enabled=True,
                vlm_guided_intake_enabled=True,
                page_allowlist=("page_1",),
            )
        ).create(provider=provider)

        def fail_binding(**_kwargs):
            raise RuntimeError("private-binding-failure")

        runtime.vlm_region_binding.bind = fail_binding
        result = self._run(runtime, _package(self.pdf_sha256))

        self.assertEqual((1, 1), (provider.count_calls, provider.generate_calls))
        self.assertEqual([], result["runtime_result_refs"])
        self.assertEqual(1, len(result["private_target_state_refs"]))
        state = self.store.read_payload(
            self.store.get_record_unchecked(
                result["private_target_state_refs"][0]
            )
        )
        decisions = state["intake_decisions"]
        self.assertEqual(
            "absent_due_to_upstream_failure",
            decisions["detection"]["decision"],
        )
        self.assertEqual(
            "unsupported", decisions["processability"]["decision"]
        )
        self.assertEqual(100, decisions["technical_facts"]["counted_input_tokens"])

    def test_full_page_identity_mismatch_blocks_before_model_calls(self) -> None:
        provider = _ProviderBoundary()
        runtime = PdfStructuralRepairShadowFactory(
            PdfStructuralRepairShadowConfig(
                enabled=True,
                vlm_guided_intake_enabled=True,
                page_allowlist=("page_1",),
            )
        ).create(provider=provider)
        package = _package(self.pdf_sha256)
        package["private_normalized_source_payloads"][0][
            "pdf_text_layer_projection"
        ]["page_inventory"][0]["layout_page_width"] = 199.0

        result = self._run(runtime, package)

        self.assertEqual(1, provider.qualification_calls)
        self.assertEqual((0, 0), (provider.count_calls, provider.generate_calls))
        self.assertEqual([], result["runtime_result_refs"])
        self.assertEqual([], result["private_target_state_refs"])
        self.assertEqual(1, len(result["private_diagnostic_refs"]))

    def test_semantic_projection_requires_both_valves_and_persists_privately(
        self,
    ) -> None:
        provider = _ProviderBoundary()
        runtime = PdfStructuralRepairShadowFactory(
            PdfStructuralRepairShadowConfig(
                enabled=True,
                semantic_header_shadow_enabled=True,
            )
        ).create(provider=provider)

        result = self._run(runtime, _package(self.pdf_sha256))

        self.assertTrue(result["summary"]["semantic_header_shadow_enabled"])
        self.assertEqual(
            {"incomplete": 1},
            result["summary"]["semantic_projection_status_counts"],
        )
        self.assertEqual(
            {"pdf_semantic_header_unknown_or_unmapped_columns": 1},
            result["summary"]["semantic_projection_reason_counts"],
        )
        self.assertEqual(1, result["summary"]["private_semantic_projections_persisted"])
        self.assertEqual(0, result["summary"]["private_semantic_diagnostics_persisted"])
        self.assertEqual(1, len(result["semantic_projection_refs"]))
        self.assertEqual([], result["semantic_diagnostic_refs"])
        semantic_ref = result["semantic_projection_refs"][0]
        semantic_record = self.store.get_record_unchecked(semantic_ref)
        semantic_payload = self.store.read_payload(semantic_record)
        self.assertEqual(
            "broker_reports_pdf_semantic_header_projection_v1",
            semantic_record.artifact_type,
        )
        self.assertEqual("private_case", semantic_record.visibility)
        self.assertEqual("project_artifact_payload", semantic_record.storage_backend)
        self.assertEqual(
            semantic_payload["configuration_checksum"],
            semantic_record.safe_metadata["configuration_checksum"],
        )
        self.assertEqual(
            semantic_payload["configuration"]["schema_version"],
            semantic_record.safe_metadata["configuration_schema_version"],
        )
        self.assertEqual("fragment", semantic_record.safe_metadata["projection_scope"])
        self.assertEqual("non_authoritative", semantic_payload["authority_state"])
        self.assertFalse(semantic_payload["production_gate2_selection_changed"])
        self.assertFalse(semantic_payload["source_value_change_allowed"])
        self.assertEqual(
            semantic_payload["structural_result_checksum"],
            self.store.read_payload(
                self.store.get_record_unchecked(result["runtime_result_refs"][0])
            )["result_checksum"],
        )
        safe_summary = result["summary"]
        self.assertNotIn("private-customer-value", repr(safe_summary))
        resolver = ArtifactResolver(self.store)
        resolved = resolver.resolve(
            semantic_ref,
            ArtifactAccessContext(**{**self.context.__dict__, "allow_private": True}),
        )
        self.assertEqual(semantic_payload, resolved["payload"])
        with self.assertRaises(ArtifactStoreError) as denied:
            resolver.resolve(
                semantic_ref,
                ArtifactAccessContext(
                    **{
                        **self.context.__dict__,
                        "user_id": "wrong-user",
                        "allow_private": True,
                    }
                ),
            )
        self.assertEqual("artifact_access_denied", denied.exception.code)
        self.store.purge_run(self.context.normalization_run_id)
        purged = self.store.get_record_unchecked(semantic_ref)
        self.assertEqual("purged", purged.purge_status)
        self.assertIsNone(purged.payload_ref)

    def test_semantic_projection_does_not_materialize_physical_ambiguity(self) -> None:
        provider = _ProviderBoundary(ambiguous=True)
        runtime = PdfStructuralRepairShadowFactory(
            PdfStructuralRepairShadowConfig(
                enabled=True,
                semantic_header_shadow_enabled=True,
            )
        ).create(provider=provider)

        result = self._run(runtime, _package(self.pdf_sha256))

        outcome = result["summary"]["target_outcomes"][0]
        self.assertEqual(
            "historical_conflict_manual_review",
            outcome["terminal_status"],
        )
        runtime_payload = self.store.read_payload(
            self.store.get_record_unchecked(result["runtime_result_refs"][0])
        )
        self.assertEqual(
            "ambiguous_multiple_consensus",
            runtime_payload["runtime_terminal_status"],
        )
        self.assertEqual(
            "not_projected_physical_ambiguity",
            outcome["semantic_projection_status"],
        )
        self.assertEqual([], result["semantic_projection_refs"])
        self.assertEqual(
            {"not_projected_physical_ambiguity": 1},
            result["summary"]["semantic_projection_status_counts"],
        )
        self.assertEqual(
            {"pdf_semantic_header_not_projected_physical_ambiguity": 1},
            result["summary"]["semantic_projection_reason_counts"],
        )

    def test_windowed_shadow_renders_full_width_crops_and_uses_exact_2w_calls(
        self,
    ) -> None:
        provider = _ProviderBoundary()
        runtime = PdfStructuralRepairShadowFactory(
            PdfStructuralRepairShadowConfig(enabled=True)
        ).create(provider=provider)

        result = self._run(
            runtime,
            _package(self.pdf_sha256, atom_count=193),
        )

        self.assertEqual(4, provider.count_calls)
        self.assertEqual(4, provider.generate_calls)
        self.assertEqual(
            "accepted_supplied_consensus",
            result["summary"]["target_outcomes"][0]["terminal_status"],
        )
        state_record = self.store.list_by_type(
            self.context.normalization_run_id,
            "broker_reports_pdf_structural_repair_target_state_v1",
        )[0]
        state = self.store.read_payload(state_record)
        self.assertEqual("vertical_atom_windows", state["execution_mode"])
        self.assertEqual(2, state["window_plan"]["window_count"])
        self.assertFalse(state["visual_package"]["provider_input_allowed"])
        self.assertEqual(2, len(state["private_window_rasters"]))
        for window, private_raster in zip(
            state["window_plan"]["windows"],
            state["private_window_rasters"],
        ):
            manifest = private_raster["rendered"]["manifest"]
            self.assertEqual(window["crop_bbox"], manifest["declared_table_bbox"])
            self.assertEqual(0.0, manifest["declared_table_bbox"][0])
            self.assertEqual(200.0, manifest["declared_table_bbox"][2])

    def test_two_page_continuation_is_discovered_joined_and_persisted_privately(
        self,
    ) -> None:
        pdf_bytes = _continuation_pdf_bytes()
        pdf_sha256 = hashlib.sha256(pdf_bytes).hexdigest()
        provider = _ProviderBoundary()
        runtime = PdfStructuralRepairShadowFactory(
            PdfStructuralRepairShadowConfig(enabled=True)
        ).create(provider=provider)

        result = runtime.run(
            store=self.store,
            package=_continuation_package(pdf_sha256),
            context=self.context,
            retention_policy=self.retention,
            pdf_bytes_by_sha256={pdf_sha256: pdf_bytes},
        )

        self.assertEqual(4, provider.count_calls)
        self.assertEqual(4, provider.generate_calls)
        self.assertEqual(
            2, result["summary"]["accepted_supplied_consensus_tables"]
        )
        self.assertEqual(1, result["summary"]["continuation_groups_discovered"])
        self.assertEqual(1, result["summary"]["continuation_groups_accepted"])
        self.assertEqual(0, result["summary"]["continuation_groups_failed"])
        self.assertEqual(
            {
                "continuation_group_id": result["summary"][
                    "continuation_group_outcomes"
                ][0]["continuation_group_id"],
                "status": "success",
                "fragment_count": 2,
                "row_count": 4,
                "column_count": 2,
                "reason_codes": [],
                "semantic_projection_status": "disabled",
                "semantic_projection_persisted": False,
                "semantic_reason_codes": [],
            },
            result["summary"]["continuation_group_outcomes"][0],
        )
        self.assertEqual(
            {"success": 1, "partial": 0, "failed": 0},
            result["file_processing_outcomes"]["status_counts"],
        )
        self.assertEqual(1, len(result["continuation_discovery_refs"]))
        self.assertEqual(1, len(result["continuation_result_refs"]))
        self.assertEqual(1, len(result["continuation_materialization_refs"]))
        self.assertNotIn("private-page-1", repr(result["summary"]))
        self.assertNotIn("private-page-2", repr(result["summary"]))

        continuation_record = self.store.list_by_type(
            self.context.normalization_run_id,
            "broker_reports_pdf_structural_repair_continuation_result_v1",
        )[0]
        materialization_record = self.store.list_by_type(
            self.context.normalization_run_id,
            "broker_reports_pdf_continuation_materialization_v1",
        )[0]
        continuation_payload = self.store.read_payload(continuation_record)
        materialization_payload = self.store.read_payload(materialization_record)
        self.assertEqual(0, continuation_payload["new_provider_count_token_calls"])
        self.assertEqual(0, continuation_payload["new_provider_generate_calls"])
        self.assertEqual("private_case", continuation_record.visibility)
        self.assertEqual("private_case", materialization_record.visibility)
        self.assertEqual(4, materialization_payload["row_count"])
        self.assertTrue(materialization_payload["candidate_ownership_exact"])
        self.assertEqual(0, materialization_payload["model_invented_values_total"])
        self.assertIn("private-page-1", repr(materialization_payload))
        self.assertIn("private-page-2", repr(materialization_payload))
        self.assertFalse(
            continuation_payload["production_gate2_selection_changed"]
        )

    def test_semantic_shadow_projects_fragments_and_joined_continuation(self) -> None:
        pdf_bytes = _continuation_pdf_bytes()
        pdf_sha256 = hashlib.sha256(pdf_bytes).hexdigest()
        provider = _ProviderBoundary()
        runtime = PdfStructuralRepairShadowFactory(
            PdfStructuralRepairShadowConfig(
                enabled=True,
                semantic_header_shadow_enabled=True,
            )
        ).create(provider=provider)

        result = runtime.run(
            store=self.store,
            package=_continuation_package(pdf_sha256),
            context=self.context,
            retention_policy=self.retention,
            pdf_bytes_by_sha256={pdf_sha256: pdf_bytes},
        )

        self.assertEqual(4, provider.count_calls)
        self.assertEqual(4, provider.generate_calls)
        self.assertEqual(3, len(result["semantic_projection_refs"]))
        self.assertEqual(
            {"incomplete": 3},
            result["summary"]["semantic_projection_status_counts"],
        )
        self.assertEqual(
            {"pdf_semantic_header_unknown_or_unmapped_columns": 3},
            result["summary"]["semantic_projection_reason_counts"],
        )
        self.assertEqual(3, result["summary"]["private_semantic_projections_persisted"])
        group_outcome = result["summary"]["continuation_group_outcomes"][0]
        self.assertEqual("incomplete", group_outcome["semantic_projection_status"])
        self.assertTrue(group_outcome["semantic_projection_persisted"])

        semantic_records = [
            self.store.get_record_unchecked(artifact_ref)
            for artifact_ref in result["semantic_projection_refs"]
        ]
        joined_record = next(
            record
            for record in semantic_records
            if record.safe_metadata["projection_scope"] == "joined_continuation"
        )
        joined_payload = self.store.read_payload(joined_record)
        continuation_payload = self.store.read_payload(
            self.store.get_record_unchecked(result["continuation_result_refs"][0])
        )
        self.assertEqual(
            continuation_payload["result_checksum"],
            joined_payload["structural_result_checksum"],
        )
        self.assertEqual(
            joined_payload["projection_checksum"],
            joined_record.safe_metadata["projection_checksum"],
        )
        self.assertEqual([], result["semantic_diagnostic_refs"])

    def test_typed_semantic_projection_failure_is_safe_and_diagnostic(self) -> None:
        provider = _ProviderBoundary()
        runtime = PdfStructuralRepairShadowFactory(
            PdfStructuralRepairShadowConfig(
                enabled=True,
                semantic_header_shadow_enabled=True,
            )
        ).create(provider=provider)
        runtime.semantic_projection = _FailingSemanticProjection()

        result = self._run(runtime, _package(self.pdf_sha256))

        self.assertEqual(
            {"projection_failed": 1},
            result["summary"]["semantic_projection_status_counts"],
        )
        self.assertEqual(
            {"pdf_semantic_header_projection_test_failure": 1},
            result["summary"]["semantic_projection_reason_counts"],
        )
        self.assertEqual([], result["semantic_projection_refs"])
        self.assertEqual(1, len(result["semantic_diagnostic_refs"]))
        self.assertEqual(1, result["summary"]["private_semantic_diagnostics_persisted"])
        diagnostic = self.store.get_record_unchecked(
            result["semantic_diagnostic_refs"][0]
        )
        self.assertEqual(
            "broker_reports_pdf_semantic_header_private_diagnostic_v1",
            diagnostic.artifact_type,
        )
        self.assertNotIn("private-customer-value", repr(result["summary"]))

    def test_join_policy_failure_is_safe_partial_with_no_joined_materialization(
        self,
    ) -> None:
        pdf_bytes = _continuation_pdf_bytes(duplicate_values=True)
        pdf_sha256 = hashlib.sha256(pdf_bytes).hexdigest()
        provider = _ProviderBoundary()
        runtime = PdfStructuralRepairShadowFactory(
            PdfStructuralRepairShadowConfig(enabled=True)
        ).create(provider=provider)

        result = runtime.run(
            store=self.store,
            package=_continuation_package(
                pdf_sha256,
                duplicate_values=True,
            ),
            context=self.context,
            retention_policy=self.retention,
            pdf_bytes_by_sha256={pdf_sha256: pdf_bytes},
        )

        self.assertEqual(4, provider.count_calls)
        self.assertEqual(4, provider.generate_calls)
        self.assertEqual(
            2, result["summary"]["accepted_supplied_consensus_tables"]
        )
        self.assertEqual(1, result["summary"]["continuation_groups_discovered"])
        self.assertEqual(0, result["summary"]["continuation_groups_accepted"])
        self.assertEqual(1, result["summary"]["continuation_groups_failed"])
        outcome = result["summary"]["continuation_group_outcomes"][0]
        self.assertEqual("partial", outcome["status"])
        self.assertEqual(
            ["pdf_structural_repair_continuation_not_accepted_supplied_scope"],
            outcome["reason_codes"],
        )
        self.assertEqual(
            {"success": 0, "partial": 1, "failed": 0},
            result["file_processing_outcomes"]["status_counts"],
        )
        self.assertEqual(1, len(result["continuation_result_refs"]))
        self.assertEqual([], result["continuation_materialization_refs"])
        self.assertNotIn("private-page-1", repr(result["summary"]))
        self.assertNotIn("private-page-2", repr(result["summary"]))

    def test_repeat_history_appends_globally_and_conflict_is_monotonic(self) -> None:
        first_provider = _ProviderBoundary(header_row_count=1)
        first_runtime = PdfStructuralRepairShadowFactory(
            PdfStructuralRepairShadowConfig(enabled=True)
        ).create(provider=first_provider)
        first = self._run(first_runtime, _package(self.pdf_sha256))
        first_history_record = self.store.get_record_unchecked(
            first["repeat_history_refs"][0]
        )
        first_history = self.store.read_payload(  # type: ignore[arg-type]
            first_history_record
        )

        self.context = ArtifactAccessContext(
            user_id="user_shadow",
            case_id="case_shadow",
            chat_id="chat_shadow",
            workspace_model_id="broker_reports_gate1",
            normalization_run_id="normalization_shadow_second",
        )
        second_provider = _ProviderBoundary(header_row_count=0)
        second_runtime = PdfStructuralRepairShadowFactory(
            PdfStructuralRepairShadowConfig(enabled=True)
        ).create(provider=second_provider)
        second = self._run(second_runtime, _package(self.pdf_sha256))
        second_history_record = self.store.get_record_unchecked(
            second["repeat_history_refs"][0]
        )
        second_history = self.store.read_payload(  # type: ignore[arg-type]
            second_history_record
        )

        self.assertEqual([1, 2], [item["sequence"] for item in first_history["events"]])
        self.assertFalse(first_history["ever_conflicted"])
        self.assertEqual(
            [1, 2, 3, 4],
            [item["sequence"] for item in second_history["events"]],
        )
        self.assertEqual(
            [1, 2, 3, 4],
            [item["attempt_number"] for item in second_history["events"]],
        )
        attempt_ids = [item["attempt_id"] for item in second_history["events"]]
        self.assertEqual(4, len(set(attempt_ids)))
        self.assertTrue(
            all("pdfstructrepairrun_" in item for item in attempt_ids)
        )
        self.assertTrue(second_history["ever_conflicted"])
        self.assertEqual(2, second_provider.count_calls)
        self.assertEqual(2, second_provider.generate_calls)
        self.assertEqual(
            "historical_conflict_manual_review",
            second["summary"]["target_outcomes"][0]["terminal_status"],
        )
        self.assertEqual(
            "partial", second["file_processing_outcomes"]["overall_status"]
        )
        self.assertEqual(
            "consensus_not_reached",
            second["file_processing_outcomes"]["outcomes"][0]["reason_code"],
        )

    def test_repeat_history_does_not_cross_user_boundary_for_same_case(self) -> None:
        first_runtime = PdfStructuralRepairShadowFactory(
            PdfStructuralRepairShadowConfig(enabled=True)
        ).create(provider=_ProviderBoundary(header_row_count=1))
        first = self._run(first_runtime, _package(self.pdf_sha256))

        self.context = ArtifactAccessContext(
            user_id="different_user_shadow",
            case_id="case_shadow",
            chat_id="chat_shadow",
            workspace_model_id="broker_reports_gate1",
            normalization_run_id="normalization_shadow_different_user",
        )
        second_provider = _ProviderBoundary(header_row_count=0)
        second_runtime = PdfStructuralRepairShadowFactory(
            PdfStructuralRepairShadowConfig(enabled=True)
        ).create(provider=second_provider)
        second = self._run(second_runtime, _package(self.pdf_sha256))

        first_record = self.store.get_record_unchecked(first["repeat_history_refs"][0])
        second_record = self.store.get_record_unchecked(second["repeat_history_refs"][0])
        self.assertIsNotNone(first_record)
        self.assertIsNotNone(second_record)
        self.assertEqual("user_shadow", first_record.user_id)  # type: ignore[union-attr]
        self.assertEqual(
            "different_user_shadow",
            second_record.user_id,  # type: ignore[union-attr]
        )
        second_history = self.store.read_payload(second_record)  # type: ignore[arg-type]
        self.assertEqual(
            [1, 2],
            [item["sequence"] for item in second_history["events"]],
        )
        self.assertFalse(second_history["ever_conflicted"])
        self.assertEqual(
            "accepted_supplied_consensus",
            second["summary"]["target_outcomes"][0]["terminal_status"],
        )
        self.assertEqual(2, second_provider.count_calls)
        self.assertEqual(2, second_provider.generate_calls)

    def test_tampered_prior_history_blocks_new_provider_calls(self) -> None:
        first_provider = _ProviderBoundary()
        first_runtime = PdfStructuralRepairShadowFactory(
            PdfStructuralRepairShadowConfig(enabled=True)
        ).create(provider=first_provider)
        first = self._run(first_runtime, _package(self.pdf_sha256))
        history_record = self.store.get_record_unchecked(
            first["repeat_history_refs"][0]
        )
        self.assertIsNotNone(history_record)
        history = self.store.read_payload(history_record)  # type: ignore[arg-type]
        history["events"][0]["attempt_id"] = "tampered-attempt"
        payload_path = self.store.payload_root / str(history_record.payload_ref)  # type: ignore[union-attr]
        payload_path.write_text(
            json.dumps(history, ensure_ascii=False), encoding="utf-8"
        )

        self.context = ArtifactAccessContext(
            user_id="user_shadow",
            case_id="case_shadow",
            chat_id="chat_shadow",
            workspace_model_id="broker_reports_gate1",
            normalization_run_id="normalization_shadow_after_tamper",
        )
        second_provider = _ProviderBoundary()
        second_runtime = PdfStructuralRepairShadowFactory(
            PdfStructuralRepairShadowConfig(enabled=True)
        ).create(provider=second_provider)
        second = self._run(second_runtime, _package(self.pdf_sha256))

        self.assertEqual(1, second_provider.qualification_calls)
        self.assertEqual(0, second_provider.count_calls)
        self.assertEqual(0, second_provider.generate_calls)
        self.assertEqual(
            "partial", second["file_processing_outcomes"]["overall_status"]
        )
        self.assertEqual(
            "consensus_not_reached",
            second["file_processing_outcomes"]["outcomes"][0]["reason_code"],
        )
        self.assertEqual([], second["repeat_history_refs"])
        self.assertEqual(1, len(second["private_diagnostic_refs"]))
        self.assertNotIn("tampered-attempt", repr(second["summary"]))

    def test_provider_exception_is_terminal_per_file_without_hidden_retry(self) -> None:
        private_error = r"C:\customers\secret.pdf token=private-token"
        provider = _ProviderBoundary(fail_message=private_error)
        runtime = PdfStructuralRepairShadowFactory(
            PdfStructuralRepairShadowConfig(enabled=True)
        ).create(provider=provider)

        result = self._run(runtime, _package(self.pdf_sha256))

        self.assertEqual(1, provider.count_calls)
        self.assertEqual(1, provider.generate_calls)
        self.assertEqual(1, result["summary"]["tables_failed"])
        self.assertEqual(
            {"success": 0, "partial": 0, "failed": 1},
            result["file_processing_outcomes"]["status_counts"],
        )
        self.assertNotIn(private_error, repr(result["summary"]))
        self.assertNotIn(
            "private-token", repr(result["file_processing_outcomes"])
        )
        self.assertEqual(1, len(result["private_target_state_refs"]))
        self.assertEqual([], result["runtime_result_refs"])
        self.assertEqual(1, len(result["private_diagnostic_refs"]))
        diagnostic_record = self.store.get_record_unchecked(
            result["private_diagnostic_refs"][0]
        )
        self.assertIsNotNone(diagnostic_record)
        diagnostic = self.store.read_payload(diagnostic_record)  # type: ignore[arg-type]
        self.assertIn(private_error, diagnostic["exception_message"])
        self.assertEqual(
            "provider_response_invalid",
            result["file_processing_outcomes"]["outcomes"][0]["reason_code"],
        )

    def test_missing_provider_is_factory_controlled_safe_terminal(self) -> None:
        runtime = PdfStructuralRepairShadowFactory(
            PdfStructuralRepairShadowConfig(enabled=True)
        ).create(provider=None)

        result = self._run(runtime, _package(self.pdf_sha256))

        outcome = result["file_processing_outcomes"]["outcomes"][0]
        self.assertEqual("failed", outcome["status"])
        self.assertEqual("provider_call", outcome["stage"])
        self.assertEqual(
            "provider_temporarily_unavailable", outcome["reason_code"]
        )
        self.assertEqual(1, len(result["private_diagnostic_refs"]))
        self.assertEqual([], result["private_target_state_refs"])
        self.assertEqual([], result["runtime_result_refs"])
        self.assertEqual([], result["repeat_history_refs"])
        self.assertFalse(
            result["summary"]["production_gate2_selection_changed"]
        )

    def test_allowlist_and_global_table_limit_are_bounded(self) -> None:
        provider = _ProviderBoundary()
        package = _package(self.pdf_sha256, table_refs=("table_1", "table_2"))
        runtime = PdfStructuralRepairShadowFactory(
            PdfStructuralRepairShadowConfig(
                enabled=True,
                maximum_tables=1,
                table_allowlist=("table_1", "table_2"),
            )
        ).create(provider=provider)

        result = self._run(runtime, package)

        self.assertEqual(2, result["summary"]["tables_discovered"])
        self.assertEqual(1, result["summary"]["tables_selected"])
        self.assertEqual(1, result["summary"]["tables_skipped_by_limit"])
        self.assertEqual(2, provider.count_calls)
        self.assertEqual(2, provider.generate_calls)
        self.assertEqual(
            "partial", result["file_processing_outcomes"]["overall_status"]
        )

        excluded_provider = _ProviderBoundary()
        excluded_runtime = PdfStructuralRepairShadowFactory(
            PdfStructuralRepairShadowConfig(
                enabled=True,
                table_allowlist=("table_not_present",),
            )
        ).create(provider=excluded_provider)
        excluded = self._run(excluded_runtime, package)
        self.assertEqual(0, excluded_provider.qualification_calls)
        self.assertEqual(0, excluded_provider.count_calls)
        self.assertEqual(0, excluded_provider.generate_calls)
        self.assertEqual(2, excluded["summary"]["tables_skipped_by_allowlist"])
        self.assertEqual(
            "success",
            excluded["file_processing_outcomes"]["overall_status"],
        )

    def test_atom_limit_1000_fails_before_provider_calls_and_is_safe(self) -> None:
        provider = _ProviderBoundary()
        runtime = PdfStructuralRepairShadowFactory(
            PdfStructuralRepairShadowConfig(enabled=True)
        ).create(provider=provider)
        package = _package(self.pdf_sha256, atom_count=1001)

        result = self._run(runtime, package)

        self.assertEqual(1, provider.qualification_calls)
        self.assertEqual(0, provider.count_calls)
        self.assertEqual(0, provider.generate_calls)
        outcome = result["file_processing_outcomes"]["outcomes"][0]
        self.assertEqual("failed", outcome["status"])
        self.assertEqual("atom_budget_exceeded", outcome["reason_code"])
        self.assertEqual("visual_topology", outcome["stage"])
        self.assertEqual(1, len(result["private_diagnostic_refs"]))
        self.assertNotIn("private-customer-value", repr(result["summary"]))

    def test_enabled_empty_input_persists_safe_zero_summary(self) -> None:
        provider = _ProviderBoundary()
        runtime = PdfStructuralRepairShadowFactory(
            PdfStructuralRepairShadowConfig(enabled=True)
        ).create(provider=provider)

        result = self._run(runtime, {"document_inventory": {"documents": []}})

        self.assertTrue(result["enabled"])
        self.assertEqual(0, result["summary"]["files_total"])
        self.assertEqual(0, result["summary"]["tables_discovered"])
        self.assertIsNone(result["file_processing_outcomes"])
        self.assertEqual(0, provider.qualification_calls)
        self.assertIsNotNone(result["summary_ref"])
        self.assertEqual(1, len(result["artifact_refs"]))

    def _run(self, runtime, package: dict) -> dict:
        return runtime.run(
            store=self.store,
            package=package,
            context=self.context,
            retention_policy=self.retention,
            pdf_bytes_by_sha256={self.pdf_sha256: self.pdf_bytes},
        )


def _topology_response(
    package_id: str,
    *,
    header_row_count: int = 1,
    rows: list[float] | None = None,
    ambiguous: bool = False,
) -> dict:
    hypotheses = [
        {
            "hypothesis_key": "primary",
            "row_boundaries": rows or [0.0, 0.5, 1.0],
            "column_boundaries": [0.0, 0.5, 1.0],
            "header_row_count": header_row_count,
            "spans": [],
            "header_hierarchy": [],
            "continuation_required": False,
            "uncertainty_codes": [],
        }
    ]
    if ambiguous:
        hypotheses.append(
            {
                **hypotheses[0],
                "hypothesis_key": "alternative",
                "row_boundaries": [0.0, 1.0],
                "header_row_count": 1 if header_row_count else 0,
            }
        )
    return {
        "schema_version": PDF_VISUAL_TOPOLOGY_RESPONSE_SCHEMA,
        "package_id": package_id,
        "decision": "ambiguous" if ambiguous else "bound",
        "alternatives_complete": True,
        "hypotheses": hypotheses,
        "uncertainty_codes": [],
    }


def _candidate_region_response(topology: dict) -> dict:
    return {
        "schema_version": PDF_VISUAL_TOPOLOGY_RESPONSE_SCHEMA,
        "contract_revision": PDF_VISUAL_TOPOLOGY_REGION_PROPOSAL_REVISION,
        "package_id": topology["package_id"],
        "proposal_scope": "candidate_crop",
        "table_presence": "present",
        "alternatives_complete": True,
        "regions": [
            {
                "region_key": "candidate",
                "bbox": [0.0, 0.0, 1.0, 1.0],
                "border_evidence": "mixed",
                "density": "mixed",
                "continuation_likelihood": "unlikely",
                "hypotheses": topology["hypotheses"],
                "uncertainty_codes": [],
            }
        ],
        "uncertainty_codes": [],
    }


def _page_region_response(
    topology: dict,
    *,
    regions: int,
    table_presence: str,
    uncertain: bool,
) -> dict:
    proposed_regions = []
    boxes = (
        [[0.0, 0.0, 1.0, 1.0]]
        if regions == 1
        else [[0.0, 0.0, 1.0, 0.5], [0.0, 0.5, 1.0, 1.0]]
        if regions == 2
        else []
    )
    for index, bbox in enumerate(boxes, start=1):
        hypothesis = {
            **topology["hypotheses"][0],
            "row_boundaries": [0.0, 1.0] if regions == 2 else [0.0, 0.5, 1.0],
        }
        proposed_regions.append(
            {
                "region_key": f"region_{index}",
                "bbox": bbox,
                "border_evidence": "ruled",
                "density": "mixed",
                "continuation_likelihood": "unlikely",
                "hypotheses": [hypothesis],
                "uncertainty_codes": [],
            }
        )
    return {
        "schema_version": PDF_VISUAL_TOPOLOGY_RESPONSE_SCHEMA,
        "contract_revision": PDF_VISUAL_TOPOLOGY_REGION_PROPOSAL_REVISION,
        "package_id": topology["package_id"],
        "proposal_scope": "page_level",
        "table_presence": table_presence,
        "alternatives_complete": True,
        "regions": proposed_regions,
        "uncertainty_codes": (
            ["visual_table_presence_uncertain"] if uncertain else []
        ),
    }


def _pdf_bytes() -> bytes:
    document = fitz.open()
    page = document.new_page(width=200, height=100)
    for point, text in (
        ((10, 20), "alpha"),
        ((110, 20), "beta"),
        ((10, 70), "gamma"),
        ((110, 70), "delta"),
    ):
        page.insert_text(point, text)
    for start, end in (
        ((0, 0), (0, 100)),
        ((100, 0), (100, 100)),
        ((199, 0), (199, 100)),
        ((0, 1), (200, 1)),
        ((0, 50), (200, 50)),
        ((0, 99), (200, 99)),
    ):
        page.draw_line(start, end)
    value = document.tobytes()
    document.close()
    return value


def _continuation_pdf_bytes(*, duplicate_values: bool = False) -> bytes:
    first_values = ("private-page-1-a", "private-page-1-b", "private-page-1-c", "private-page-1-d")
    second_values = (
        first_values
        if duplicate_values
        else (
            "private-page-2-a",
            "private-page-2-b",
            "private-page-2-c",
            "private-page-2-d",
        )
    )
    document = fitz.open()
    for page_number, (table_bbox, values) in enumerate(
        (
            ([20.0, 210.0, 300.0, 310.0], first_values),
            ([20.0, 10.0, 300.0, 110.0], second_values),
        ),
        start=1,
    ):
        page = document.new_page(width=320, height=320)
        x0, y0, x1, y1 = table_bbox
        x_mid = (x0 + x1) / 2.0
        y_mid = (y0 + y1) / 2.0
        text_points = (
            ((x0 + 10.0, y0 + 25.0), values[0]),
            ((x_mid + 10.0, y0 + 25.0), values[1]),
            ((x0 + 10.0, y_mid + 25.0), values[2]),
            ((x_mid + 10.0, y_mid + 25.0), values[3]),
        )
        for point, text in text_points:
            page.insert_text(point, text, fontsize=6)
        for start, end in (
            ((x0, y0), (x0, y1)),
            ((x_mid, y0), (x_mid, y1)),
            ((x1, y0), (x1, y1)),
            ((x0, y0), (x1, y0)),
            ((x0, y_mid), (x1, y_mid)),
            ((x0, y1), (x1, y1)),
        ):
            page.draw_line(start, end)
        page.insert_text((5, 5), f"page-{page_number}", fontsize=3)
    value = document.tobytes()
    document.close()
    return value


def _continuation_package(
    pdf_sha256: str,
    *,
    duplicate_values: bool = False,
) -> dict:
    return {
        "document_inventory": {
            "documents": [
                {
                    "document_id": "document_continuation",
                    "container_format": "pdf",
                    "sha256": pdf_sha256,
                }
            ]
        },
        "private_normalized_source_payloads": [
            {
                "document_ref": "document_continuation",
                "pdf_text_layer_projection": _continuation_projection(
                    duplicate_values=duplicate_values
                ),
            }
        ],
        "unchanged_gate2_selection": {"must_remain": "unchanged"},
    }


def _continuation_projection(*, duplicate_values: bool = False) -> dict:
    first_values = (
        "private-page-1-a",
        "private-page-1-b",
        "private-page-1-c",
        "private-page-1-d",
    )
    second_values = (
        first_values
        if duplicate_values
        else (
            "private-page-2-a",
            "private-page-2-b",
            "private-page-2-c",
            "private-page-2-d",
        )
    )
    bbox_inventory = []
    words = []
    vectors = []
    candidates = []
    page_specs = (
        ("page_1", 1, [20.0, 210.0, 300.0, 310.0], first_values),
        ("page_2", 2, [20.0, 10.0, 300.0, 110.0], second_values),
    )
    for page_ref, page_number, table_bbox, values in page_specs:
        table_bbox_ref = f"bbox_table_{page_number}"
        bbox_inventory.append(
            {"bbox_ref": table_bbox_ref, "bbox": table_bbox}
        )
        x0, y0, x1, y1 = table_bbox
        x_mid = (x0 + x1) / 2.0
        y_mid = (y0 + y1) / 2.0
        word_boxes = (
            [x0 + 10.0, y0 + 10.0, x_mid - 10.0, y_mid - 10.0],
            [x_mid + 10.0, y0 + 10.0, x1 - 10.0, y_mid - 10.0],
            [x0 + 10.0, y_mid + 10.0, x_mid - 10.0, y1 - 10.0],
            [x_mid + 10.0, y_mid + 10.0, x1 - 10.0, y1 - 10.0],
        )
        for ordinal, (text, bbox) in enumerate(
            zip(values, word_boxes), start=1
        ):
            bbox_ref = f"bbox_word_{page_number}_{ordinal}"
            bbox_inventory.append({"bbox_ref": bbox_ref, "bbox": bbox})
            words.append(
                {
                    "parser_ordinal": ordinal,
                    "word_ref": f"word_{page_number}_{ordinal}",
                    "page_ref": page_ref,
                    "bbox_ref": bbox_ref,
                    "text": text,
                    "geometry_reading_order": ordinal,
                    "text_checksum_ref": f"text_checksum_{page_number}_{ordinal}",
                    "source_value_ref": f"source_value_{page_number}_{ordinal}",
                }
            )
        vector_boxes = (
            [x0, y0, x0, y1],
            [x_mid, y0, x_mid, y1],
            [x1, y0, x1, y1],
            [x0, y0, x1, y0],
            [x0, y_mid, x1, y_mid],
            [x0, y1, x1, y1],
        )
        for ordinal, bbox in enumerate(vector_boxes, start=1):
            bbox_ref = f"bbox_vector_{page_number}_{ordinal}"
            bbox_inventory.append({"bbox_ref": bbox_ref, "bbox": bbox})
            vectors.append(
                {
                    "parser_ordinal": ordinal,
                    "object_ref": f"vector_{page_number}_{ordinal}",
                    "page_ref": page_ref,
                    "bbox_ref": bbox_ref,
                    "linewidth": 0.5,
                }
            )
        candidates.append(
            {
                "parser_ordinal": 1,
                "table_candidate_ref": f"table_{page_number}",
                "page_ref": page_ref,
                "bbox_ref": table_bbox_ref,
                "table_strategy_ref": "ruled_lines_v0",
                "geometry_confidence": 0.95,
                "rows_total": 2,
                "columns_total": 2,
            }
        )
    return {
        "page_inventory": [
            {
                "page_ref": page_ref,
                "page_number": page_number,
                "layout_page_width": 320.0,
                "layout_page_height": 320.0,
            }
            for page_ref, page_number, _, _ in page_specs
        ],
        "bbox_inventory": bbox_inventory,
        "word_inventory": words,
        "line_inventory": [],
        "vector_line_inventory": vectors,
        "rect_inventory": [],
        "table_candidate_inventory": candidates,
    }


def _package(
    pdf_sha256: str,
    *,
    table_refs: tuple[str, ...] = ("table_1",),
    atom_count: int = 4,
) -> dict:
    projection = _projection(atom_count=atom_count, table_refs=table_refs)
    return {
        "document_inventory": {
            "documents": [
                {
                    "document_id": "document_1",
                    "container_format": "pdf",
                    "sha256": pdf_sha256,
                }
            ]
        },
        "private_normalized_source_payloads": [
            {
                "document_ref": "document_1",
                "pdf_text_layer_projection": projection,
            }
        ],
        "unchanged_gate2_selection": {
            "customer": "private-customer-value"
        },
    }


def _projection(*, atom_count: int, table_refs: tuple[str, ...]) -> dict:
    bbox_inventory = [
        {"bbox_ref": "bbox_table", "bbox": [0.0, 0.0, 200.0, 100.0]}
    ]
    words = []
    for index in range(atom_count):
        if atom_count == 4:
            values = (
                ("private-customer-value", [10.0, 10.0, 90.0, 40.0]),
                ("beta-private", [110.0, 10.0, 190.0, 40.0]),
                ("gamma-private", [10.0, 60.0, 90.0, 90.0]),
                ("delta-private", [110.0, 60.0, 190.0, 90.0]),
            )
            text, bbox = values[index]
        else:
            column = index % 40
            row = index // 40
            x0 = 1.0 + column * 4.8
            y0 = 1.0 + row * 3.7
            text = f"private-{index}"
            bbox = [x0, y0, x0 + 2.0, y0 + 1.0]
        bbox_ref = f"bbox_word_{index + 1}"
        bbox_inventory.append({"bbox_ref": bbox_ref, "bbox": bbox})
        words.append(
            {
                "parser_ordinal": index + 1,
                "word_ref": f"word_{index + 1}",
                "page_ref": "page_1",
                "bbox_ref": bbox_ref,
                "text": text,
                "geometry_reading_order": index + 1,
                "text_checksum_ref": f"text_checksum_{index + 1}",
                "source_value_ref": f"source_value_{index + 1}",
            }
        )
    vectors = []
    for index, bbox in enumerate(
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
        bbox_ref = f"bbox_vector_{index}"
        bbox_inventory.append({"bbox_ref": bbox_ref, "bbox": bbox})
        vectors.append(
            {
                "parser_ordinal": index,
                "object_ref": f"vector_{index}",
                "page_ref": "page_1",
                "bbox_ref": bbox_ref,
                "linewidth": 0.5,
            }
        )
    return {
        "page_inventory": [
            {
                "page_ref": "page_1",
                "page_number": 1,
                "layout_page_width": 200.0,
                "layout_page_height": 100.0,
            }
        ],
        "bbox_inventory": bbox_inventory,
        "word_inventory": words,
        "line_inventory": [],
        "vector_line_inventory": vectors,
        "rect_inventory": [],
        "table_candidate_inventory": [
            {
                "parser_ordinal": index,
                "table_candidate_ref": table_ref,
                "page_ref": "page_1",
                "bbox_ref": "bbox_table",
                "table_strategy_ref": "ruled_lines_v0",
                "geometry_confidence": 0.95,
                "rows_total": 2,
                "columns_total": 2,
            }
            for index, table_ref in enumerate(table_refs, start=1)
        ],
    }


if __name__ == "__main__":
    unittest.main()
