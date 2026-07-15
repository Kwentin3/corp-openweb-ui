from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import fitz

from broker_reports_gate1.artifact_models import ArtifactAccessContext
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
from broker_reports_gate1.pdf_visual_topology import (
    PDF_VISUAL_TOPOLOGY_RESPONSE_SCHEMA,
)


class _ProviderBoundary:
    def __init__(
        self,
        *,
        fail_message: str | None = None,
        header_row_count: int = 1,
    ) -> None:
        self.fail_message = fail_message
        self.header_row_count = header_row_count
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
            "json_output": _topology_response(
                model_view["identity"]["package_id"],
                header_row_count=header_row_count,
                rows=rows,
            ),
            "raw_private_response": {
                "provider_secret": "private-provider-response"
            },
            "visible_output_bytes": 100,
            "response_bytes": 200,
        }


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
        self.assertIn("must not invoke structural stages", FORBIDDEN)
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

        self.assertEqual(first, second)
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
            result["summary"]["accepted_unique_consensus_tables"],
        )
        self.assertEqual(
            "accepted_unique_consensus",
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
        self.assertIn("private-provider-response", repr(runtime_payload))
        self.assertEqual("safe_internal", summary_record.visibility)
        self.assertNotIn("private-customer-value", repr(safe_payload))
        self.assertNotIn("private-provider-response", repr(safe_payload))
        self.assertFalse(safe_payload["customer_values_included"])
        self.assertFalse(safe_payload["crop_bytes_included"])
        self.assertFalse(safe_payload["raw_provider_response_included"])

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
            "accepted_unique_consensus",
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
        self.assertEqual(2, result["summary"]["accepted_unique_consensus_tables"])
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
        self.assertEqual(2, result["summary"]["accepted_unique_consensus_tables"])
        self.assertEqual(1, result["summary"]["continuation_groups_discovered"])
        self.assertEqual(0, result["summary"]["continuation_groups_accepted"])
        self.assertEqual(1, result["summary"]["continuation_groups_failed"])
        outcome = result["summary"]["continuation_group_outcomes"][0]
        self.assertEqual("partial", outcome["status"])
        self.assertEqual(
            ["pdf_structural_repair_continuation_consensus_not_unique"],
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
) -> dict:
    return {
        "schema_version": PDF_VISUAL_TOPOLOGY_RESPONSE_SCHEMA,
        "package_id": package_id,
        "decision": "bound",
        "alternatives_complete": True,
        "hypotheses": [
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
        ],
        "uncertainty_codes": [],
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
        "page_inventory": [{"page_ref": "page_1", "page_number": 1}],
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
            }
            for index, table_ref in enumerate(table_refs, start=1)
        ],
    }


if __name__ == "__main__":
    unittest.main()
