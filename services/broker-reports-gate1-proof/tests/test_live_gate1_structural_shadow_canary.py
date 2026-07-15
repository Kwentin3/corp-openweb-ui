from __future__ import annotations

import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = (
    ROOT
    / "services"
    / "broker-reports-gate1-proof"
    / "scripts"
    / "live_gate1_structural_shadow_canary.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "live_gate1_structural_shadow_canary_tested",
        SCRIPT,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("structural_shadow_canary_import_failed")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _snapshot(file_rows: int, *, embeddings: int = 11) -> dict:
    return {
        "db": {
            "file_count": file_rows,
            "document_count": 3,
            "knowledge_count": 2,
        },
        "vector": {
            "file_count": 4,
            "dir_count": 2,
            "collections_count": 1,
            "size_bytes": 4096,
        },
        "artifact_store": {"record_count": 10},
        "vector_rag_rows": {
            "database_exists": True,
            "table_counts": {
                "collections": 1,
                "embeddings": embeddings,
                "segments": 2,
            },
        },
    }


def _workspace_model() -> dict:
    return {
        "id": "test",
        "name": "Broker Reports test workspace",
        "is_active": True,
        "meta": {
            "capabilities": {"file_upload": True, "file_context": False},
            "knowledge": [],
        },
        "params": {},
    }


def _valid_artifact_cleanup(
    records: int = 30,
    *,
    active_before: int | None = None,
) -> dict:
    active = records if active_before is None else active_before
    return {
        "performed": True,
        "records_before_total": records,
        "active_records_before_total": active,
        "private_payload_refs_before_total": 12 if active else 0,
        "payload_files_before_total": 12 if active else 0,
        "purged_records_total": active,
        "records_after_total": records,
        "active_records_after_total": 0,
        "private_payload_refs_after_total": 0,
        "payload_files_absent": True,
        "tombstone_records_after_total": records,
        "all_records_tombstoned": True,
    }


def _valid_quiescence(records: int = 30) -> dict:
    observations = [
        {
            "ordinal": ordinal,
            "wait_seconds": wait_seconds,
            "active_records_before_purge": 0,
            "purged_records_total": 0,
            "active_records_after_purge": 0,
            "private_payload_refs_after_total": 0,
            "payload_files_absent": True,
            "upload_id_absent": True,
            "upload_alias_absent": True,
            "post_state_verified": True,
        }
        for ordinal, wait_seconds in enumerate((5.0, 15.0, 30.0), start=1)
    ]
    return {
        "performed": True,
        "bounded_wait_seconds": 50.0,
        "observation_count": 3,
        "required_zero_observations": 3,
        "zero_artifact_observations": 3,
        "post_state_checks_total": 3,
        "upload_absence_checks_total": 3,
        "late_writes_detected": False,
        "verified": True,
        "evidence_boundary": (
            "no_late_writes_observed_within_bounded_quiescence_window"
        ),
        "errors": [],
        "observations": observations,
        "records_after_total": records,
    }


def _valid_chat() -> str:
    return "\n".join(
        (
            "Автоматическая проверка структуры PDF-таблиц:",
            "- Выбрано таблиц: 2; согласовано двумя проверками "
            "в переданном наборе: 0",
            "- Режим: проверочный shadow; основной результат Gate 2 не изменён.",
            "- Семантические заголовки: сохранено приватных проекций 2; "
            "статусы: incomplete: 2.",
        )
    )


def _valid_artifacts(module) -> dict:
    required_types = {
        "broker_reports_pdf_structural_repair_target_state_v1": 2,
        "broker_reports_pdf_vlm_guided_intake_result_v1": 2,
        "broker_reports_pdf_semantic_header_projection_v1": 2,
        "broker_reports_pdf_structural_repair_shadow_summary_v1": 1,
        "broker_reports_pdf_dual_oracle_repeat_history_v1": 0,
        "broker_reports_pdf_structural_repair_runtime_result_v1": 0,
        "broker_reports_pdf_continuation_discovery_v1": 0,
        "broker_reports_pdf_structural_repair_continuation_result_v1": 0,
        "broker_reports_pdf_continuation_materialization_v1": 0,
    }
    contracts = {}
    for artifact_type, count in required_types.items():
        is_summary = (
            artifact_type
            == "broker_reports_pdf_structural_repair_shadow_summary_v1"
        )
        contracts[artifact_type] = {
            "count": count,
            "visibility_counts": (
                {"safe_internal" if is_summary else "private_case": count}
                if count
                else {}
            ),
            "storage_backend_counts": (
                {
                    "project_artifact_store"
                    if is_summary
                    else "project_artifact_payload": count
                }
                if count
                else {}
            ),
            "validation_status_counts": {"validated": count} if count else {},
        }
    fragment = {
        "schema_version": "broker_reports_pdf_vlm_guided_intake_result_v1",
        "target_id_present": True,
        "execution_contract": "candidate_crop_one_call_v1",
        "proposal_decision": "bound",
        "post_validation_passed": True,
        "terminal_status": "accepted_physical_structure",
        "count_token_calls": module.EXPECTED_COUNT_TOKEN_CALLS_PER_FRAGMENT,
        "generate_calls": module.EXPECTED_GENERATE_CALLS_PER_FRAGMENT,
        "all_candidates_accounted": True,
        "model_invented_values_total": 0,
        "hidden_retry": False,
        "provider_failover": False,
        "authority_state": "non_authoritative",
        "production_ready": False,
        "production_gate2_selection_changed": False,
    }
    provider_route = {
        "fragment_ordinal": 1,
        "status": "qualified",
        "provider_profile": "google_gemini",
        "requested_model_id": "models/gemini-3.5-flash",
        "resolved_model_id": "models/gemini-3.5-flash",
        "exact_model_match": True,
        "native_provider_transport": True,
        "credentials_from_openwebui_connection": True,
        "hidden_retry": False,
        "provider_failover": False,
    }
    provider_journal = {
        "fragment_ordinal": 1,
        "attempt_number": 1,
        "count_token_call_performed": True,
        "generate_call_performed": True,
        "count_tokens_observation_present": True,
        "generate_started_at_present": True,
        "independent_call_order_proven": False,
        "call_order_evidence_boundary": (
            "runtime_journal_co_recorded_without_count_tokens_timestamp"
        ),
        "counted_input_tokens": 321,
        "actual_input_tokens": 321,
        "output_tokens": 11,
        "within_input_budget": True,
        "within_output_budget": True,
        "provider_profile": "google_gemini",
        "model_requested": "models/gemini-3.5-flash",
        "model_resolved": "models/gemini-3.5-flash",
        "finish_reason": "STOP",
        "hidden_retry": False,
        "provider_failover": False,
    }
    provider_routes = []
    provider_journal_records = []
    for fragment_ordinal in (1, 2):
        route = copy.deepcopy(provider_route)
        route["fragment_ordinal"] = fragment_ordinal
        provider_routes.append(route)
        journal = copy.deepcopy(provider_journal)
        journal["fragment_ordinal"] = fragment_ordinal
        provider_journal_records.append(journal)
    semantic_safe_metadata_keys = sorted(
        {
            "schema_version",
            "target_id",
            "projection_scope",
            "projection_status",
            "semantic_equivalence_status",
            "physical_topology_status",
            "physical_alternatives_total",
            "semantic_fields_total",
            "qualifiers_total",
            "reason_codes",
            "configuration_schema_version",
            "configuration_checksum",
            "projection_checksum",
            "structural_result_checksum",
            "input_hash",
            "authority_state",
            "production_ready",
            "production_gate2_selection_changed",
        }
    )
    semantic_records = []
    for ordinal in (1, 2):
        scope = "fragment"
        result_checksum = f"{ordinal:064x}"
        semantic_records.append(
            {
                "target_id_present": True,
                "projection_scope": scope,
                "projection_status": "incomplete",
                "semantic_equivalence_status": "incomplete",
                "physical_topology_status": "accepted_supplied_consensus",
                "reason_codes": [
                    "pdf_semantic_header_unknown_or_unmapped_columns"
                ],
                "configuration_schema_version": (
                    "broker_reports_pdf_semantic_header_projection_"
                    "configuration_v1"
                ),
                "configuration_max_context_bytes": 48 * 1024,
                "configuration_bytes": 512,
                "configuration_checksum": "a" * 64,
                "configuration_checksum_valid": True,
                "projection_checksum": "b" * 64,
                "input_hash": "c" * 64,
                "context_bytes": [512],
                "structural_result_checksum": result_checksum,
                "expected_structural_result_checksum": result_checksum,
                "structural_result_checksum_bound": True,
                "source_value_change_allowed": False,
                "geometry_change_allowed": False,
                "physical_cell_change_allowed": False,
                "reference_answer_used": False,
                "authority_state": "non_authoritative",
                "production_gate2_selection_changed": False,
                "provider_call_fields_present": False,
                "safe_metadata_keys": semantic_safe_metadata_keys,
                "safe_metadata_matches_payload": True,
            }
        )
    return {
        "type_counts": required_types,
        "record_contracts": contracts,
        "tables_selected": 2,
        "accepted_supplied_consensus_tables": 0,
        "accepted_physical_structure_tables": 2,
        "vlm_guided_intake_enabled": True,
        "private_repeat_histories_persisted": 0,
        "continuation_groups_discovered": 0,
        "continuation_groups_accepted": 0,
        "continuation_groups_failed": 0,
        "continuation_descriptors_not_grouped": 0,
        "continuation_manual_review_required": False,
        "private_continuation_discoveries_persisted": 0,
        "private_continuation_results_persisted": 0,
        "private_continuation_materializations_persisted": 0,
        "semantic_header_shadow_enabled": True,
        "semantic_projection_status_counts": {"incomplete": 2},
        "semantic_projection_reason_counts": {
            "pdf_semantic_header_unknown_or_unmapped_columns": 2
        },
        "private_semantic_projections_persisted": 2,
        "private_semantic_diagnostics_persisted": 0,
        "base_normalization_mutated": False,
        "knowledge_rag_used": False,
        "customer_values_included": False,
        "crop_bytes_included": False,
        "raw_provider_response_included": False,
        "private_diagnostics_included": False,
        "authority_state": "non_authoritative",
        "production_ready": False,
        "production_gate2_selection_changed": False,
        "target_state_records": [
            {
                "target_id_present": True,
                "execution_mode": "guided_candidate_crop",
                "vlm_guided_intake_enabled": True,
                "repeat_history_scope_empty": True,
                "prior_repeat_history_ref": None,
                "prior_repeat_history_checksum": None,
                "authority_state": "non_authoritative",
                "production_ready": False,
                "production_gate2_selection_changed": False,
            },
            {
                "target_id_present": True,
                "execution_mode": "guided_candidate_crop",
                "vlm_guided_intake_enabled": True,
                "repeat_history_scope_empty": True,
                "prior_repeat_history_ref": None,
                "prior_repeat_history_checksum": None,
                "authority_state": "non_authoritative",
                "production_ready": False,
                "production_gate2_selection_changed": False,
            },
        ],
        "fragment_runtime_records": [copy.deepcopy(fragment), copy.deepcopy(fragment)],
        "distinct_fragment_target_ids": 2,
        "count_token_calls": 2,
        "generate_calls": 2,
        "provider_route_records": provider_routes,
        "provider_journal_records": provider_journal_records,
        "provider_token_totals": {
            "count_token_calls": 2,
            "generate_calls": 2,
            "counted_input_tokens": 2 * 321,
            "actual_input_tokens": 2 * 321,
            "output_tokens": 2 * 11,
        },
        "semantic_projection_records": semantic_records,
        "semantic_new_provider_count_token_calls": 0,
        "semantic_new_provider_generate_calls": 0,
        "discovery_records": [],
        "continuation_records": [],
        "materialization_records": [],
    }


class StructuralShadowCanaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = _load_module()

    def _assert(self, artifacts: dict, *, chat: str | None = None, embeddings: int = 11):
        self.module._assert_canary(
            chat_content=chat if chat is not None else _valid_chat(),
            artifacts=artifacts,
            before=_snapshot(10),
            after_upload=_snapshot(11, embeddings=embeddings),
            after_chat=_snapshot(11, embeddings=embeddings),
        )

    def test_exact_terminal_evidence_passes(self):
        self._assert(_valid_artifacts(self.module))

    def test_shadow_must_be_disabled_before_any_mutation(self):
        with self.assertRaisesRegex(RuntimeError, "canary_shadow_initially_enabled"):
            self.module._assert_live_preflight(
                valves={"pdf_structural_repair_shadow_enabled": True},
                workspace_model=_workspace_model(),
            )

    def test_semantic_shadow_must_be_disabled_before_any_mutation(self):
        with self.assertRaisesRegex(
            RuntimeError, "canary_semantic_shadow_initially_enabled"
        ):
            self.module._assert_live_preflight(
                valves={"pdf_semantic_header_shadow_enabled": True},
                workspace_model=_workspace_model(),
            )

    def test_guided_shadow_must_be_disabled_before_any_mutation(self):
        with self.assertRaisesRegex(
            RuntimeError,
            "canary_guided_intake_shadow_initially_enabled",
        ):
            self.module._assert_live_preflight(
                valves={"pdf_vlm_guided_intake_shadow_enabled": True},
                workspace_model=_workspace_model(),
            )

    def test_guided_page_allowlist_must_be_empty_before_any_mutation(self):
        with self.assertRaisesRegex(
            RuntimeError,
            "canary_guided_page_allowlist_initially_nonempty",
        ):
            self.module._assert_live_preflight(
                valves={
                    "pdf_vlm_guided_intake_shadow_page_allowlist": "page_1"
                },
                workspace_model=_workspace_model(),
            )

    def test_canary_enables_guided_and_semantic_shadows_with_exact_allowlist(self):
        before = {"unrelated_valve": "preserved"}
        valves = self.module._canary_valves(
            before,
            ["pdftablecand_a", "pdftablecand_b"],
        )

        self.assertEqual("preserved", valves["unrelated_valve"])
        self.assertTrue(valves["pdf_structural_repair_shadow_enabled"])
        self.assertTrue(valves["pdf_vlm_guided_intake_shadow_enabled"])
        self.assertEqual(
            "", valves["pdf_vlm_guided_intake_shadow_page_allowlist"]
        )
        self.assertTrue(valves["pdf_semantic_header_shadow_enabled"])
        self.assertEqual(2, valves["pdf_structural_repair_max_tables"])
        self.assertEqual(
            "pdftablecand_a,pdftablecand_b",
            valves["pdf_structural_repair_shadow_table_allowlist"],
        )

    def test_guided_bundle_markers_and_synthetic_candidate_count_are_exact(self):
        self.assertTrue(
            {
                "pdf_vlm_guided_intake_shadow_enabled",
                "pdf_vlm_guided_intake_shadow_page_allowlist",
                "run_candidate_once",
                "broker_reports_pdf_vlm_guided_intake_result_v1",
            }.issubset(self.module.REQUIRED_MARKERS)
        )
        pdf_bytes = self.module._two_fragment_guided_intake_pdf()
        self.assertEqual(2, len(self.module._candidate_refs(pdf_bytes)))

    def test_guided_flag_is_restored_disabled_exactly(self):
        before = {
            "pdf_structural_repair_shadow_enabled": False,
            "pdf_vlm_guided_intake_shadow_enabled": False,
            "pdf_semantic_header_shadow_enabled": False,
        }
        session = mock.Mock()
        with (
            mock.patch.object(self.module, "_update_valves") as update,
            mock.patch.object(
                self.module,
                "_get_valves",
                return_value=copy.deepcopy(before),
            ),
        ):
            self.module._restore_valves_exact(
                session,
                "https://example.invalid",
                before_valves=before,
                before_valves_sha=self.module._json_sha(before),
            )

        update.assert_called_once_with(
            session,
            "https://example.invalid",
            before,
        )

    def test_workspace_model_preflight_and_exact_restore_are_strict(self):
        model = _workspace_model()
        self.module._assert_live_preflight(valves={}, workspace_model=model)
        sha = self.module._json_sha(model)
        self.module._assert_workspace_model_unchanged(
            before=model,
            before_sha=sha,
            after=copy.deepcopy(model),
        )

        invalid = _workspace_model()
        invalid["meta"]["capabilities"]["file_context"] = True
        with self.assertRaisesRegex(
            RuntimeError, "canary_workspace_model_file_context_enabled"
        ):
            self.module._assert_live_preflight(valves={}, workspace_model=invalid)

        changed = _workspace_model()
        changed["params"] = {"temperature": 0.1}
        with self.assertRaisesRegex(
            RuntimeError, "canary_workspace_model_state_mismatch"
        ):
            self.module._assert_workspace_model_unchanged(
                before=model,
                before_sha=sha,
                after=changed,
            )

    def test_provider_route_mismatch_fails_closed(self):
        artifacts = _valid_artifacts(self.module)
        artifacts["provider_route_records"][0]["resolved_model_id"] = (
            "models/gemini-3.1-flash-lite"
        )

        with self.assertRaisesRegex(RuntimeError, "canary_provider_route_invalid"):
            self._assert(artifacts)

    def test_generate_without_count_tokens_observation_fails_closed(self):
        artifacts = _valid_artifacts(self.module)
        artifacts["provider_journal_records"][0][
            "count_tokens_observation_present"
        ] = False

        with self.assertRaisesRegex(
            RuntimeError, "canary_provider_token_accounting_invalid"
        ):
            self._assert(artifacts)

    def test_provider_token_mismatch_fails_closed(self):
        artifacts = _valid_artifacts(self.module)
        artifacts["provider_journal_records"][0]["actual_input_tokens"] = 322

        with self.assertRaisesRegex(
            RuntimeError, "canary_provider_token_accounting_invalid"
        ):
            self._assert(artifacts)

    def test_independent_provider_call_order_overclaim_fails_closed(self):
        artifacts = _valid_artifacts(self.module)
        artifacts["provider_journal_records"][0][
            "independent_call_order_proven"
        ] = True

        with self.assertRaisesRegex(
            RuntimeError, "canary_provider_token_accounting_invalid"
        ):
            self._assert(artifacts)

    def test_provider_aggregate_totals_fail_closed(self):
        artifacts = _valid_artifacts(self.module)
        artifacts["provider_token_totals"]["generate_calls"] = 3

        with self.assertRaisesRegex(
            RuntimeError, "canary_provider_token_accounting_invalid"
        ):
            self._assert(artifacts)

    def test_extra_fragment_runtime_record_fails_closed(self):
        artifacts = _valid_artifacts(self.module)
        artifacts["type_counts"][
            "broker_reports_pdf_vlm_guided_intake_result_v1"
        ] = 3

        with self.assertRaisesRegex(RuntimeError, "canary_structural_artifact_missing"):
            self._assert(artifacts)

    def test_semantic_projection_must_bind_to_structural_result(self):
        artifacts = _valid_artifacts(self.module)
        artifacts["semantic_projection_records"][0][
            "structural_result_checksum_bound"
        ] = False

        with self.assertRaisesRegex(
            RuntimeError, "canary_semantic_artifact_invalid"
        ):
            self._assert(artifacts)

    def test_semantic_canary_accepts_payload_derived_status_mix(self):
        artifacts = _valid_artifacts(self.module)
        artifacts["semantic_projection_records"][0]["projection_status"] = (
            "projected"
        )
        artifacts["semantic_projection_records"][0][
            "semantic_equivalence_status"
        ] = "not_applicable"
        artifacts["semantic_projection_records"][0]["reason_codes"] = []
        artifacts["semantic_projection_status_counts"] = {
            "projected": 1,
            "incomplete": 1,
        }
        artifacts["semantic_projection_reason_counts"] = {
            "pdf_semantic_header_unknown_or_unmapped_columns": 1
        }
        chat = _valid_chat().replace(
            "статусы: incomplete: 2",
            "статусы: incomplete: 1, projected: 1",
        )
        self._assert(artifacts, chat=chat)

    def test_semantic_summary_must_equal_payload_derived_counts(self):
        artifacts = _valid_artifacts(self.module)
        artifacts["semantic_projection_status_counts"] = {"projected": 2}

        with self.assertRaisesRegex(
            RuntimeError, "canary_semantic_summary_invalid"
        ):
            self._assert(artifacts)

    def test_semantic_context_budget_and_configuration_checksum_fail_closed(self):
        artifacts = _valid_artifacts(self.module)
        artifacts["semantic_projection_records"][0]["context_bytes"] = [
            48 * 1024 + 1
        ]

        with self.assertRaisesRegex(
            RuntimeError, "canary_semantic_artifact_invalid"
        ):
            self._assert(artifacts)

        artifacts = _valid_artifacts(self.module)
        artifacts["semantic_projection_records"][0][
            "configuration_checksum_valid"
        ] = False
        with self.assertRaisesRegex(
            RuntimeError, "canary_semantic_artifact_invalid"
        ):
            self._assert(artifacts)

    def test_semantic_fragment_scope_and_safe_metadata_are_required(self):
        artifacts = _valid_artifacts(self.module)
        artifacts["semantic_projection_records"][1]["projection_scope"] = (
            "joined_continuation"
        )
        with self.assertRaisesRegex(
            RuntimeError, "canary_semantic_artifact_set_invalid"
        ):
            self._assert(artifacts)

        artifacts = _valid_artifacts(self.module)
        artifacts["semantic_projection_records"][0][
            "safe_metadata_matches_payload"
        ] = False
        with self.assertRaisesRegex(
            RuntimeError, "canary_semantic_artifact_invalid"
        ):
            self._assert(artifacts)

    def test_semantic_provider_call_delta_fails_closed(self):
        artifacts = _valid_artifacts(self.module)
        artifacts["semantic_new_provider_generate_calls"] = 1

        with self.assertRaisesRegex(
            RuntimeError, "canary_semantic_provider_call_invalid"
        ):
            self._assert(artifacts)

    def test_continuation_artifact_fails_closed(self):
        artifacts = _valid_artifacts(self.module)
        artifacts["type_counts"][
            "broker_reports_pdf_structural_repair_continuation_result_v1"
        ] = 1

        with self.assertRaisesRegex(
            RuntimeError, "canary_forbidden_artifact_present"
        ):
            self._assert(artifacts)

    def test_repeat_history_artifact_fails_closed(self):
        artifacts = _valid_artifacts(self.module)
        artifacts["type_counts"][
            "broker_reports_pdf_dual_oracle_repeat_history_v1"
        ] = 1

        with self.assertRaisesRegex(
            RuntimeError, "canary_forbidden_artifact_present"
        ):
            self._assert(artifacts)

    def test_wrong_artifact_visibility_fails_closed(self):
        artifacts = _valid_artifacts(self.module)
        artifacts["record_contracts"][
            "broker_reports_pdf_vlm_guided_intake_result_v1"
        ]["visibility_counts"] = {"safe_internal": 1}

        with self.assertRaisesRegex(
            RuntimeError, "canary_record_contract_state_invalid"
        ):
            self._assert(artifacts)

    def test_embedding_row_delta_fails_no_rag_proof(self):
        with self.assertRaisesRegex(RuntimeError, "vector_rag_table_counts"):
            self._assert(_valid_artifacts(self.module), embeddings=12)

    def test_json_or_non_specific_chat_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, "canary_compact_report_shape_invalid"):
            self._assert(
                _valid_artifacts(self.module),
                chat='{"PDF": "guided intake"}',
            )

    def test_semantic_chat_private_value_fails_closed(self):
        with self.assertRaisesRegex(
            RuntimeError, "canary_private_chat_marker_detected"
        ):
            self._assert(
                _valid_artifacts(self.module),
                chat=_valid_chat() + "\n2026-01-01 USD 10.00",
            )

    def test_chat_uses_explicit_supported_api_smoke_retention_policy(self):
        response = mock.Mock()
        response.json.return_value = {
            "choices": [{"message": {"content": "ok"}}]
        }
        session = mock.Mock()
        session.post.return_value = response

        content = self.module._run_chat(
            session,
            "https://example.invalid",
            upload={
                "id": "upload-1",
                "filename": "synthetic.pdf",
                "size": 42,
            },
            case_id="case-safe",
            timeout=30,
        )

        self.assertEqual("ok", content)
        payload = session.post.call_args.kwargs["json"]
        self.assertEqual(
            {
                "mode": "api_smoke",
                "explicit": True,
                "ttl_seconds": 24 * 60 * 60,
            },
            payload["broker_reports_gate1"]["retention_policy"],
        )

    def test_artifact_cleanup_requires_tombstones_and_no_payloads(self):
        self.module._assert_artifact_cleanup(
            _valid_artifact_cleanup(), require_records=True
        )
        invalid = _valid_artifact_cleanup()
        invalid["private_payload_refs_after_total"] = 1
        with self.assertRaisesRegex(
            RuntimeError, "canary_artifact_cleanup_unverified"
        ):
            self.module._assert_artifact_cleanup(invalid, require_records=True)

    def test_bounded_quiescence_repeats_zero_artifact_and_post_state_checks(self):
        repeat_cleanup = _valid_artifact_cleanup(active_before=0)
        with (
            mock.patch.object(
                self.module,
                "_wait_quiescence_interval",
            ) as wait_interval,
            mock.patch.object(
                self.module,
                "_cleanup_upload_exactly",
                return_value={
                    "upload_id_absent": True,
                    "upload_alias_absent": True,
                },
            ) as cleanup_upload,
            mock.patch.object(
                self.module,
                "_purge_case_artifacts",
                return_value=repeat_cleanup,
            ) as purge_case,
            mock.patch.object(
                self.module,
                "_runtime_snapshot_strict",
                return_value=_snapshot(10),
            ) as runtime_snapshot,
        ):
            evidence, final_snapshot = self.module._bounded_terminal_quiescence(
                session=mock.Mock(),
                base_url="https://example.invalid",
                ssh_target="root@example.invalid",
                case_id="case-safe",
                bundle_source="bundle-content",
                upload={"id": "upload-1"},
                upload_filename="unique.pdf",
                before_runtime=_snapshot(10),
            )

        self.module._assert_bounded_quiescence(evidence)
        self.assertEqual(_valid_quiescence(), evidence)
        self.assertEqual(_snapshot(10), final_snapshot)
        self.assertEqual(3, cleanup_upload.call_count)
        self.assertEqual(3, purge_case.call_count)
        self.assertEqual(3, runtime_snapshot.call_count)
        self.assertEqual(
            [mock.call(value) for value in (5.0, 15.0, 30.0)],
            wait_interval.call_args_list,
        )

    def test_bounded_quiescence_purges_late_write_and_fails_closed(self):
        late_cleanup = _valid_artifact_cleanup(records=31, active_before=1)
        zero_cleanup = _valid_artifact_cleanup(records=31, active_before=0)
        with (
            mock.patch.object(self.module, "_wait_quiescence_interval"),
            mock.patch.object(
                self.module,
                "_cleanup_upload_exactly",
                return_value={
                    "upload_id_absent": True,
                    "upload_alias_absent": True,
                },
            ),
            mock.patch.object(
                self.module,
                "_purge_case_artifacts",
                side_effect=[late_cleanup, zero_cleanup, zero_cleanup],
            ) as purge_case,
            mock.patch.object(
                self.module,
                "_runtime_snapshot_strict",
                return_value=_snapshot(10),
            ),
        ):
            evidence, _ = self.module._bounded_terminal_quiescence(
                session=mock.Mock(),
                base_url="https://example.invalid",
                ssh_target="root@example.invalid",
                case_id="case-safe",
                bundle_source="bundle-content",
                upload={"id": "upload-1"},
                upload_filename="unique.pdf",
                before_runtime=_snapshot(10),
            )

        self.assertTrue(evidence["late_writes_detected"])
        self.assertFalse(evidence["verified"])
        self.assertEqual(3, purge_case.call_count)
        self.assertEqual(2, evidence["zero_artifact_observations"])
        with self.assertRaisesRegex(
            RuntimeError, "canary_terminal_quiescence_unverified"
        ):
            self.module._assert_bounded_quiescence(evidence)

    def test_cleanup_error_forces_old_function_restore(self):
        before_function = {
            "id": "broker_reports_gate1_pipe",
            "name": "Gate 1",
            "meta": {},
            "is_active": True,
            "content": "old-content",
        }
        workspace_model = _workspace_model()
        with (
            mock.patch.object(
                self.module,
                "_cleanup_upload_exactly",
                return_value={
                    "upload_id_absent": True,
                    "upload_alias_absent": True,
                },
            ),
            mock.patch.object(
                self.module,
                "_runtime_snapshot_strict",
                return_value=_snapshot(10),
            ),
            mock.patch.object(
                self.module,
                "_purge_case_artifacts",
                return_value=_valid_artifact_cleanup(),
            ),
            mock.patch.object(
                self.module,
                "_bounded_terminal_quiescence",
                return_value=(_valid_quiescence(), _snapshot(10)),
            ),
            mock.patch.object(
                self.module,
                "_get_workspace_model",
                return_value=copy.deepcopy(workspace_model),
            ),
            mock.patch.object(
                self.module,
                "_restore_valves_exact",
                side_effect=[RuntimeError("restore-failed"), None, None, None],
            ) as restore_valves,
            mock.patch.object(self.module, "_restore_function_exact") as restore_function,
            mock.patch.object(
                self.module,
                "_get_function",
                return_value=before_function,
            ),
        ):
            terminal = self.module._finalize_canary(
                session=mock.Mock(),
                base_url="https://example.invalid",
                ssh_target="root@example.invalid",
                function_update_attempted=True,
                body_passed=True,
                before_function=before_function,
                before_valves={},
                before_valves_sha=self.module._json_sha({}),
                before_workspace_model=workspace_model,
                before_workspace_model_sha=self.module._json_sha(workspace_model),
                bundle_source="new-content",
                bundle_sha=self.module._text_sha("new-content"),
                case_id="case-safe",
                upload={"id": "upload-1"},
                upload_filename="unique.pdf",
                before_runtime=_snapshot(10),
            )

        self.assertFalse(terminal["function_retained"])
        self.assertTrue(terminal["cleanup_errors"])
        self.assertEqual(2, restore_function.call_count)
        self.assertEqual(4, restore_valves.call_count)

    def test_interrupt_after_fast_safety_barrier_cannot_leave_shadow_enabled(self):
        before_function = {
            "id": "broker_reports_gate1_pipe",
            "name": "Gate 1",
            "meta": {},
            "is_active": True,
            "content": "old-content",
        }
        workspace_model = _workspace_model()
        events: list[str] = []

        def restore_valves(*_args, **_kwargs):
            events.append("restore_valves")

        def restore_function(*_args, **_kwargs):
            events.append("restore_function")

        def interrupted_upload(*_args, **_kwargs):
            events.append("slow_upload_cleanup")
            raise KeyboardInterrupt()

        with (
            mock.patch.object(
                self.module,
                "_restore_valves_exact",
                side_effect=restore_valves,
            ),
            mock.patch.object(
                self.module,
                "_restore_function_exact",
                side_effect=restore_function,
            ),
            mock.patch.object(
                self.module,
                "_cleanup_upload_exactly",
                side_effect=interrupted_upload,
            ),
            mock.patch.object(
                self.module,
                "_purge_case_artifacts",
                return_value=_valid_artifact_cleanup(),
            ),
            mock.patch.object(
                self.module,
                "_runtime_snapshot_strict",
                return_value=_snapshot(10),
            ),
            mock.patch.object(
                self.module,
                "_bounded_terminal_quiescence",
                return_value=(_valid_quiescence(), _snapshot(10)),
            ),
            mock.patch.object(
                self.module,
                "_get_workspace_model",
                return_value=workspace_model,
            ),
        ):
            terminal = self.module._finalize_canary(
                session=mock.Mock(),
                base_url="https://example.invalid",
                ssh_target="root@example.invalid",
                function_update_attempted=True,
                body_passed=True,
                before_function=before_function,
                before_valves={},
                before_valves_sha=self.module._json_sha({}),
                before_workspace_model=workspace_model,
                before_workspace_model_sha=self.module._json_sha(workspace_model),
                bundle_source="new-content",
                bundle_sha=self.module._text_sha("new-content"),
                case_id="case-safe",
                upload={"id": "upload-1"},
                upload_filename="unique.pdf",
                before_runtime=_snapshot(10),
            )

        self.assertEqual(
            [
                "restore_valves",
                "restore_function",
                "restore_valves",
                "slow_upload_cleanup",
            ],
            events[:4],
        )
        self.assertFalse(terminal["function_retained"])
        self.assertTrue(terminal["terminal_state_restored"])
        self.assertTrue(
            any("KeyboardInterrupt" in item for item in terminal["cleanup_errors"])
        )
        self.assertEqual(2, events.count("restore_function"))
        self.assertEqual(4, events.count("restore_valves"))

    def test_late_artifact_write_forces_terminal_function_rollback(self):
        before_function = {
            "id": "broker_reports_gate1_pipe",
            "name": "Gate 1",
            "meta": {},
            "is_active": True,
            "content": "old-content",
        }
        workspace_model = _workspace_model()
        late_evidence = _valid_quiescence(records=31)
        late_evidence.update(
            {
                "zero_artifact_observations": 2,
                "late_writes_detected": True,
                "verified": False,
                "evidence_boundary": (
                    "bounded_quiescence_failed_or_late_writes_observed"
                ),
            }
        )
        late_evidence["observations"][0]["active_records_before_purge"] = 1
        late_evidence["observations"][0]["purged_records_total"] = 1

        with (
            mock.patch.object(
                self.module,
                "_restore_old_runtime_state",
                side_effect=[[], []],
            ) as restore_old_state,
            mock.patch.object(
                self.module,
                "_cleanup_upload_exactly",
                return_value={
                    "upload_id_absent": True,
                    "upload_alias_absent": True,
                },
            ),
            mock.patch.object(
                self.module,
                "_purge_case_artifacts",
                return_value=_valid_artifact_cleanup(),
            ),
            mock.patch.object(
                self.module,
                "_runtime_snapshot_strict",
                return_value=_snapshot(10),
            ),
            mock.patch.object(
                self.module,
                "_bounded_terminal_quiescence",
                return_value=(late_evidence, _snapshot(10)),
            ),
            mock.patch.object(
                self.module,
                "_get_workspace_model",
                return_value=workspace_model,
            ),
            mock.patch.object(
                self.module,
                "_update_function_with_timeout_recovery",
            ) as terminal_deploy,
        ):
            terminal = self.module._finalize_canary(
                session=mock.Mock(),
                base_url="https://example.invalid",
                ssh_target="root@example.invalid",
                function_update_attempted=True,
                body_passed=True,
                before_function=before_function,
                before_valves={},
                before_valves_sha=self.module._json_sha({}),
                before_workspace_model=workspace_model,
                before_workspace_model_sha=self.module._json_sha(workspace_model),
                bundle_source="new-content",
                bundle_sha=self.module._text_sha("new-content"),
                case_id="case-safe",
                upload={"id": "upload-1"},
                upload_filename="unique.pdf",
                before_runtime=_snapshot(10),
            )

        self.assertFalse(terminal["function_retained"])
        terminal_deploy.assert_not_called()
        self.assertEqual(2, restore_old_state.call_count)
        self.assertTrue(
            any("quiescence" in item for item in terminal["cleanup_errors"])
        )

    def test_success_terminal_retains_only_exact_new_function(self):
        before_function = {
            "id": "broker_reports_gate1_pipe",
            "name": "Gate 1",
            "meta": {},
            "is_active": True,
            "content": "old-content",
        }
        deployed = {**before_function, "content": "new-content"}
        workspace_model = _workspace_model()
        with (
            mock.patch.object(
                self.module,
                "_cleanup_upload_exactly",
                return_value={
                    "upload_id_absent": True,
                    "upload_alias_absent": True,
                },
            ),
            mock.patch.object(
                self.module,
                "_runtime_snapshot_strict",
                return_value=_snapshot(10),
            ),
            mock.patch.object(
                self.module,
                "_purge_case_artifacts",
                return_value=_valid_artifact_cleanup(),
            ),
            mock.patch.object(
                self.module,
                "_bounded_terminal_quiescence",
                return_value=(_valid_quiescence(), _snapshot(10)),
            ),
            mock.patch.object(
                self.module,
                "_get_workspace_model",
                return_value=copy.deepcopy(workspace_model),
            ),
            mock.patch.object(self.module, "_restore_valves_exact"),
            mock.patch.object(self.module, "_restore_function_exact") as restore_function,
            mock.patch.object(
                self.module,
                "_update_function_with_timeout_recovery",
            ) as terminal_deploy,
            mock.patch.object(
                self.module,
                "_get_function",
                return_value=deployed,
            ),
        ):
            terminal = self.module._finalize_canary(
                session=mock.Mock(),
                base_url="https://example.invalid",
                ssh_target="root@example.invalid",
                function_update_attempted=True,
                body_passed=True,
                before_function=before_function,
                before_valves={},
                before_valves_sha=self.module._json_sha({}),
                before_workspace_model=workspace_model,
                before_workspace_model_sha=self.module._json_sha(workspace_model),
                bundle_source="new-content",
                bundle_sha=self.module._text_sha("new-content"),
                case_id="case-safe",
                upload={"id": "upload-1"},
                upload_filename="unique.pdf",
                before_runtime=_snapshot(10),
            )

        self.assertTrue(terminal["function_retained"])
        self.assertEqual([], terminal["cleanup_errors"])
        self.assertEqual(
            self.module._text_sha("new-content"),
            terminal["final_function_sha256"],
        )
        self.assertTrue(terminal["workspace_model_restored_exactly"])
        self.assertEqual(
            {
                "initial": _valid_artifact_cleanup(),
                "quiescence": _valid_quiescence(),
            },
            terminal["artifact_cleanup"],
        )
        restore_function.assert_called_once()
        terminal_deploy.assert_called_once()
        self.assertTrue(terminal["safety_barrier_completed"])

    def test_expected_deployed_function_uses_bundle_frontmatter_manifest(self):
        before = {
            "id": "broker_reports_gate1_pipe",
            "name": "Gate 1",
            "meta": {
                "description": "preserved",
                "manifest": {"version": "old"},
            },
            "is_active": True,
            "is_global": False,
            "content": "old-content",
        }
        bundle = '\n'.join(
            (
                '"""',
                "title: Gate 1",
                "author: Alpha Soft",
                "version: 0.12.0",
                "required_open_webui_version: 0.9.6",
                "requirements: pydantic,PyMuPDF==1.26.5",
                '"""',
                "new-content",
            )
        )

        expected = self.module._expected_deployed_function(before, bundle)

        self.assertEqual("preserved", expected["meta"]["description"])
        self.assertEqual(
            {
                "title": "Gate 1",
                "author": "Alpha Soft",
                "version": "0.12.0",
                "required_open_webui_version": "0.9.6",
                "requirements": "pydantic,PyMuPDF==1.26.5",
            },
            expected["meta"]["manifest"],
        )
        self.assertEqual(bundle, expected["content"])

    def test_terminal_function_drift_after_success_forces_rollback(self):
        before_function = {
            "id": "broker_reports_gate1_pipe",
            "name": "Gate 1",
            "meta": {},
            "is_active": True,
            "content": "old-content",
        }
        drifted = {**before_function, "content": "unexpected-content"}
        workspace_model = _workspace_model()
        with (
            mock.patch.object(
                self.module,
                "_cleanup_upload_exactly",
                return_value={
                    "upload_id_absent": True,
                    "upload_alias_absent": True,
                },
            ),
            mock.patch.object(
                self.module,
                "_runtime_snapshot_strict",
                return_value=_snapshot(10),
            ),
            mock.patch.object(
                self.module,
                "_purge_case_artifacts",
                return_value=_valid_artifact_cleanup(),
            ),
            mock.patch.object(
                self.module,
                "_bounded_terminal_quiescence",
                return_value=(_valid_quiescence(), _snapshot(10)),
            ),
            mock.patch.object(
                self.module,
                "_get_workspace_model",
                return_value=copy.deepcopy(workspace_model),
            ),
            mock.patch.object(self.module, "_restore_valves_exact") as restore_valves,
            mock.patch.object(self.module, "_restore_function_exact") as restore_function,
            mock.patch.object(
                self.module,
                "_update_function_with_timeout_recovery",
            ),
            mock.patch.object(
                self.module,
                "_get_function",
                return_value=drifted,
            ),
        ):
            terminal = self.module._finalize_canary(
                session=mock.Mock(),
                base_url="https://example.invalid",
                ssh_target="root@example.invalid",
                function_update_attempted=True,
                body_passed=True,
                before_function=before_function,
                before_valves={},
                before_valves_sha=self.module._json_sha({}),
                before_workspace_model=workspace_model,
                before_workspace_model_sha=self.module._json_sha(workspace_model),
                bundle_source="new-content",
                bundle_sha=self.module._text_sha("new-content"),
                case_id="case-safe",
                upload={"id": "upload-1"},
                upload_filename="unique.pdf",
                before_runtime=_snapshot(10),
            )

        self.assertFalse(terminal["function_retained"])
        self.assertTrue(
            any("terminal_deploy" in item for item in terminal["cleanup_errors"])
        )
        self.assertEqual(2, restore_function.call_count)
        self.assertEqual(5, restore_valves.call_count)

    def test_workspace_model_drift_after_success_forces_function_rollback(self):
        before_function = {
            "id": "broker_reports_gate1_pipe",
            "name": "Gate 1",
            "meta": {},
            "is_active": True,
            "content": "old-content",
        }
        workspace_model = _workspace_model()
        changed_model = _workspace_model()
        changed_model["params"] = {"temperature": 0.1}
        with (
            mock.patch.object(
                self.module,
                "_cleanup_upload_exactly",
                return_value={
                    "upload_id_absent": True,
                    "upload_alias_absent": True,
                },
            ),
            mock.patch.object(
                self.module,
                "_purge_case_artifacts",
                return_value=_valid_artifact_cleanup(),
            ),
            mock.patch.object(
                self.module,
                "_bounded_terminal_quiescence",
                return_value=(_valid_quiescence(), _snapshot(10)),
            ),
            mock.patch.object(
                self.module,
                "_runtime_snapshot_strict",
                return_value=_snapshot(10),
            ),
            mock.patch.object(self.module, "_restore_valves_exact") as restore_valves,
            mock.patch.object(self.module, "_restore_function_exact") as restore_function,
            mock.patch.object(
                self.module,
                "_get_workspace_model",
                return_value=changed_model,
            ),
            mock.patch.object(
                self.module,
                "_get_function",
                return_value=before_function,
            ),
        ):
            terminal = self.module._finalize_canary(
                session=mock.Mock(),
                base_url="https://example.invalid",
                ssh_target="root@example.invalid",
                function_update_attempted=True,
                body_passed=True,
                before_function=before_function,
                before_valves={},
                before_valves_sha=self.module._json_sha({}),
                before_workspace_model=workspace_model,
                before_workspace_model_sha=self.module._json_sha(workspace_model),
                bundle_source="new-content",
                bundle_sha=self.module._text_sha("new-content"),
                case_id="case-safe",
                upload={"id": "upload-1"},
                upload_filename="unique.pdf",
                before_runtime=_snapshot(10),
            )

        self.assertFalse(terminal["function_retained"])
        self.assertTrue(
            any("workspace_model" in item for item in terminal["cleanup_errors"])
        )
        self.assertEqual(2, restore_function.call_count)
        self.assertEqual(4, restore_valves.call_count)

    def test_ambiguous_upload_is_recovered_only_by_unique_alias_and_size(self):
        with mock.patch.object(
            self.module,
            "_find_uploads_by_filename",
            return_value=[{"id": "upload-1", "size": 42}],
        ):
            recovered = self.module._recover_ambiguous_upload(
                mock.Mock(),
                "https://example.invalid",
                upload_filename="unique.pdf",
                expected_size=42,
            )

        self.assertEqual(
            {
                "id": "upload-1",
                "filename": "unique.pdf",
                "mime_type": "application/pdf",
                "size": 42,
            },
            recovered,
        )

    def test_exact_upload_cleanup_verifies_id_and_unique_alias_absence(self):
        with (
            mock.patch.object(
                self.module,
                "_find_uploads_by_filename",
                side_effect=[[{"id": "upload-1"}], []],
            ),
            mock.patch.object(self.module, "_delete_upload_exact") as delete_upload,
            mock.patch.object(
                self.module,
                "_upload_exists",
                return_value=False,
            ),
        ):
            result = self.module._cleanup_upload_exactly(
                mock.Mock(),
                "https://example.invalid",
                upload={"id": "upload-1"},
                upload_filename="unique.pdf",
            )

        self.assertEqual(
            {"upload_id_absent": True, "upload_alias_absent": True},
            result,
        )
        delete_upload.assert_called_once_with(
            mock.ANY,
            "https://example.invalid",
            "upload-1",
        )

    def test_remote_read_only_probes_are_valid_python(self):
        captured: list[str] = []

        def capture(_target, code, *, timeout):
            compile(code, "<canary-remote-probe>", "exec")
            captured.append(f"{timeout}:{code}")
            return {}

        with mock.patch.object(self.module, "_ssh_json", side_effect=capture):
            self.module._artifact_case_summary(
                "root@example.invalid",
                "case-safe",
                "bundle_marker = True",
            )
            self.module._vector_rag_row_snapshot("root@example.invalid")
            self.module._purge_case_artifacts(
                "root@example.invalid",
                case_id="case-safe",
                bundle_source="bundle_marker = True",
            )

        self.assertEqual(3, len(captured))
        self.assertNotIn("__CASE_ID__", captured[0])
        self.assertTrue(captured[0].startswith("60:"))
        self.assertIn("ArtifactStoreFactory", captured[0])
        self.assertIn("store.list_by_case", captured[0])
        self.assertIn("store.read_payload", captured[0])
        self.assertNotIn("select artifact_type", captured[0].lower())
        self.assertTrue(captured[1].startswith("60:"))
        self.assertTrue(captured[2].startswith("180:"))
        self.assertIn("ArtifactStoreFactory", captured[2])
        self.assertIn("purge_case", captured[2])
        self.assertNotIn("delete from artifact_records", captured[2].lower())

    def test_remote_artifact_summary_executes_semantic_checksum_path(self):
        fake_bundle = r'''
import hashlib
import json
import sys
import types

class _Row:
    artifact_type = 'broker_reports_pdf_semantic_header_projection_v1'
    visibility = 'private_case'
    storage_backend = 'private_file'
    validation_status = 'validated'
    safe_metadata = {
        'schema_version': 'broker_reports_pdf_semantic_header_projection_v1',
        'target_id': 'target-1',
        'projection_scope': 'fragment',
        'projection_status': 'projected',
        'semantic_equivalence_status': 'not_applicable',
        'physical_topology_status': 'accepted_supplied_consensus',
        'reason_codes': [],
        'production_ready': False,
        'production_gate2_selection_changed': False,
    }

class _Store:
    def list_by_case(self, _case_id):
        return [_Row()]

    def read_payload(self, _record):
        configuration = {
            'schema_version': (
                'broker_reports_pdf_semantic_header_projection_configuration_v1'
            ),
            'max_context_bytes': 49152,
        }
        checksum = hashlib.sha256(
            json.dumps(
                configuration,
                ensure_ascii=False,
                sort_keys=True,
                separators=(',', ':'),
            ).encode('utf-8')
        ).hexdigest()
        return {
            'schema_version': 'broker_reports_pdf_semantic_header_projection_v1',
            'target_id': 'target-1',
            'projection_scope': 'fragment',
            'projection_status': 'projected',
            'semantic_equivalence_status': 'not_applicable',
            'physical_topology_status': 'accepted_supplied_consensus',
            'reason_codes': [],
            'configuration': configuration,
            'configuration_checksum': checksum,
            'physical_alternatives': [],
            'authority_state': 'non_authoritative',
            'production_gate2_selection_changed': False,
        }

class ArtifactStoreConfig:
    def __init__(self, *args, **kwargs):
        pass

class ArtifactStoreFactory:
    def __init__(self, _config):
        pass

    def create(self):
        return _Store()

module = types.ModuleType('broker_reports_gate1')
module.ArtifactStoreConfig = ArtifactStoreConfig
module.ArtifactStoreFactory = ArtifactStoreFactory
sys.modules['broker_reports_gate1'] = module
'''

        def execute(_target, code, *, timeout):
            self.assertEqual(60, timeout)
            previous = sys.modules.get("broker_reports_gate1")
            try:
                with mock.patch("builtins.print") as printed:
                    exec(compile(code, "<canary-remote-probe>", "exec"), {})
                return json.loads(printed.call_args.args[0])
            finally:
                if previous is None:
                    sys.modules.pop("broker_reports_gate1", None)
                else:
                    sys.modules["broker_reports_gate1"] = previous

        with mock.patch.object(self.module, "_ssh_json", side_effect=execute):
            result = self.module._artifact_case_summary(
                "root@example.invalid",
                "case-safe",
                fake_bundle,
            )

        semantic = result["semantic_projection_records"]
        self.assertEqual(1, len(semantic))
        self.assertTrue(semantic[0]["configuration_checksum_valid"])

    def test_ssh_transport_requires_verified_known_host_identity(self):
        completed = mock.Mock(returncode=0, stdout="{}")
        with mock.patch.object(
            self.module.subprocess,
            "run",
            return_value=completed,
        ) as run:
            self.module._ssh_json(
                "root@example.invalid",
                "print('{}')",
                timeout=30,
            )

        command = run.call_args.args[0]
        self.assertIn("StrictHostKeyChecking=yes", command)
        self.assertNotIn("StrictHostKeyChecking=no", command)
        self.assertIn("BatchMode=yes", command)


if __name__ == "__main__":
    unittest.main()
