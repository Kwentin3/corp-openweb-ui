from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from broker_reports_gate1 import (
    ArtifactAccessContext,
    ArtifactStoreConfig,
    ArtifactStoreFactory,
    FileInput,
    Gate1Normalizer,
    ManagedPrompt,
    apply_clarification_request_stage,
    apply_domain_ingestion_artifacts,
    apply_document_passport_stage,
    apply_metadata_gap_report_stage,
    build_llm_document_packages,
    build_metadata_gap_report,
    build_retention_policy,
    persist_gate1_result,
    render_chat_content,
)
from broker_reports_gate1.clarification import (
    CLARIFICATION_PROMPT_CONTRACT_ID,
    CLARIFICATION_REQUEST_SCHEMA_VERSION,
    ClarificationManagedPrompt,
    ClarificationPromptConfig,
    ClarificationPromptResolverFactory,
    FACTORY_REQUIRED,
    FORBIDDEN,
    PromptUserContext,
    canonicalize_clarification_request,
    clarification_json_schema_response_format,
    gate1_clarification_request_schema_hash,
    prompt_hash as clarification_prompt_hash,
    validate_clarification_request,
)
from broker_reports_gate1.document_passport import model_call_audit_metadata, prompt_hash


class BrokerReportsGate1ClarificationLoopTest(unittest.TestCase):
    def test_clarification_prompt_resolver_factory_anchor_is_explicit(self):
        self.assertIn("ClarificationPromptResolverFactory.create", FACTORY_REQUIRED)
        self.assertIn("must not hardcode", FORBIDDEN)

    def test_openwebui_sqlite_clarification_prompt_resolver_enforces_contract_and_hash(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "webui.db"
            self._create_clarification_prompt_db(db_path)

            prompt = ClarificationPromptResolverFactory(
                ClarificationPromptConfig(
                    db_path=db_path,
                    command="broker_gate1_clarification_request",
                )
            ).create().resolve(PromptUserContext(user_id="user-1"))

        self.assertEqual(prompt.prompt_ref, "prompt-clarification-1")
        self.assertEqual(prompt.command, "broker_gate1_clarification_request")
        self.assertEqual(prompt.version, "clarification-v1")
        self.assertEqual(prompt.template_id, "broker_reports.gate1_clarification_request.v0")
        self.assertEqual(prompt.output_schema_version, "gate1_clarification_request_v0")
        self.assertEqual(
            prompt.hash,
            clarification_prompt_hash(
                "Managed clarification prompt body v1",
                CLARIFICATION_PROMPT_CONTRACT_ID,
                "gate1_clarification_request_v0",
            ),
        )

    def test_clarification_request_schema_is_strict(self):
        schema = clarification_json_schema_response_format()["json_schema"]["schema"]

        self.assertEqual(schema["type"], "object")
        self.assertFalse(schema["additionalProperties"])
        self.assertIn("schema_version", schema["required"])
        self.assertIn("questions", schema["required"])
        self.assertIn("question_groups", schema["required"])
        question_schema = schema["properties"]["questions"]["items"]
        for field in (
            "criticality",
            "blocking_scope",
            "dependency_stage",
            "blocking_reason_category",
            "auto_resolution_policy",
            "blocks_gate2",
            "resolution_required",
            "can_proceed_with_warning",
            "ask_policy",
            "answer_impact",
            "priority",
            "reason_codes",
            "safe_explanation",
        ):
            self.assertIn(field, question_schema["required"])
        self.assertEqual(len(gate1_clarification_request_schema_hash()), 64)

    def test_refined_gap_report_groups_critical_clarifying_and_noncritical_stubs(self):
        gap_report = build_metadata_gap_report(
            self._minimal_criticality_package(),
            criticality_refinement_enabled=True,
        )

        self.assertEqual(gap_report["summary"]["criticality_counts"]["critical"], 1)
        self.assertEqual(gap_report["summary"]["criticality_counts"]["clarifying"], 1)
        self.assertEqual(gap_report["summary"]["criticality_counts"]["non_critical"], 2)
        self.assertEqual(gap_report["summary"]["blocking_gaps_total"], 1)
        stubs = {stub["gap_type"]: stub for stub in gap_report["question_stubs"]}
        self.assertEqual(stubs["missing_period"]["criticality"], "critical")
        self.assertTrue(stubs["missing_period"]["blocks_gate2"])
        self.assertEqual(stubs["missing_account_or_contract"]["criticality"], "clarifying")
        self.assertFalse(stubs["missing_account_or_contract"]["blocks_gate2"])
        self.assertEqual(stubs["other_metadata_conflict"]["criticality"], "non_critical")
        self.assertEqual(stubs["other_metadata_conflict"]["ask_policy"], "defer")
        self.assertNotIn("outside_scope_confirmation", stubs)
        self.assertEqual(len(gap_report["question_groups"]["critical_questions_for_continuation"]), 1)
        self.assertEqual(len(gap_report["question_groups"]["useful_clarifications"]), 1)
        self.assertEqual(len(gap_report["question_groups"]["deferred_non_critical_notes"]), 1)

    def test_refined_duplicate_gap_is_canonical_critical(self):
        package = self._minimal_criticality_package()
        package["document_source_eligibility"]["entries"].append(
            {
                "document_id": "doc_duplicate",
                "source_eligibility": "duplicate_needs_canonical_choice",
                "reason_codes": ["duplicate_review"],
                "blocker_refs": [],
            }
        )
        package["document_inventory"]["documents"].append(
            {
                "document_id": "doc_duplicate",
                "duplicate_of_document_id": "doc_critical",
            }
        )
        gap_report = build_metadata_gap_report(package, criticality_refinement_enabled=True)
        duplicate = next(stub for stub in gap_report["question_stubs"] if stub["gap_type"] == "duplicate_canonical_choice")

        self.assertEqual(duplicate["criticality"], "critical")
        self.assertTrue(duplicate["blocks_gate2"])
        self.assertTrue(duplicate["resolution_required"])
        self.assertEqual(duplicate["answer_impact"], "unblocks_gate2")

    def test_auto_resolved_exact_duplicate_does_not_create_user_question(self):
        package = {
            "normalization_run": {
                "run_id": "normrun_exact_duplicate",
                "gate2_handoff_status": "ready_with_reduced_subset",
                "gate2_handoff_mode": "reduced_subset_ready_for_gate2",
            },
            "document_source_eligibility": {
                "entries": [
                    {
                        "document_id": "doc_canonical",
                        "source_eligibility": "accepted_for_gate2",
                        "reason_codes": ["exact_duplicate_auto_canonical_selected"],
                        "blocker_refs": [],
                        "duplicate_auto_resolution": {
                            "auto_resolved": True,
                            "is_canonical": True,
                            "auto_resolution_policy": "exact_duplicate_latest_wins",
                            "duplicate_group_id": "dupgrp_safe",
                            "canonical_document_id": "doc_canonical",
                            "excluded_document_ids": ["doc_noncanonical"],
                        },
                    },
                    {
                        "document_id": "doc_noncanonical",
                        "source_eligibility": "excluded_from_gate2",
                        "reason_codes": ["noncanonical_exact_duplicate_excluded"],
                        "blocker_refs": [],
                        "duplicate_auto_resolution": {
                            "auto_resolved": True,
                            "is_canonical": False,
                            "auto_resolution_policy": "exact_duplicate_latest_wins",
                            "duplicate_group_id": "dupgrp_safe",
                            "canonical_document_id": "doc_canonical",
                            "excluded_document_ids": ["doc_noncanonical"],
                        },
                    },
                ]
            },
            "document_inventory": {
                "documents": [
                    {"document_id": "doc_canonical", "duplicate_group_id": "dupgrp_safe"},
                    {"document_id": "doc_noncanonical", "duplicate_group_id": "dupgrp_safe"},
                ]
            },
            "document_metadata_passports": [],
            "normalization_blockers": [],
        }

        gap_report = build_metadata_gap_report(package, criticality_refinement_enabled=True)

        self.assertNotIn("duplicate_canonical_choice", gap_report["summary"]["gap_type_counts"])
        self.assertFalse(
            any(stub["gap_type"] == "duplicate_canonical_choice" for stub in gap_report["question_stubs"])
        )

    def test_unresolved_critical_basis_field_is_not_hidden_by_other_metadata_gaps(self):
        package = self._minimal_criticality_package()
        package["document_source_eligibility"]["entries"][0]["clarification_criticality_basis"] = {
            "unresolved_critical_fields": ["document_role"],
            "period_scope_basis": {},
        }
        package["document_metadata_passports"][0]["missing_metadata_fields"] = ["account_or_contract_candidate"]

        gap_report = build_metadata_gap_report(package, criticality_refinement_enabled=True)
        stubs = {stub["gap_type"]: stub for stub in gap_report["question_stubs"]}

        self.assertIn("unclear_document_role", stubs)
        self.assertEqual(stubs["unclear_document_role"]["criticality"], "critical")
        self.assertTrue(stubs["unclear_document_role"]["blocks_gate2"])
        self.assertIn("missing_account_or_contract", stubs)
        self.assertEqual(stubs["missing_account_or_contract"]["criticality"], "clarifying")

    def test_llm_cannot_override_deterministic_criticality_or_blocking_fields(self):
        gap_report = build_metadata_gap_report(
            self._minimal_criticality_package(),
            criticality_refinement_enabled=True,
        )
        prompt = self._clarification_prompt()
        questions = []
        for stub in gap_report["question_stubs"]:
            question = dict(stub)
            question.update(
                {
                    "question_text": "Safe rewritten question",
                    "why_asked": "Safe rewritten reason",
                    "criticality": "non_critical",
                    "blocking_scope": "audit_only",
                    "dependency_stage": "audit_only",
                    "blocking_reason_category": "audit_quality",
                    "auto_resolution_policy": "none",
                    "blocks_gate2": False,
                    "resolution_required": False,
                    "can_proceed_with_warning": True,
                    "ask_policy": "defer",
                    "answer_impact": "adds_audit_context",
                    "priority": "low",
                    "severity": "optional",
                    "required": False,
                    "reason_codes": ["llm_attempted_override"],
                    "safe_explanation": "LLM attempted override",
                }
            )
            question.pop("gap_id", None)
            question.pop("resolved_fields", None)
            questions.append(question)

        request = canonicalize_clarification_request(
            model_output={
                "schema_version": CLARIFICATION_REQUEST_SCHEMA_VERSION,
                "questions": questions,
                "question_groups": {
                    "critical_questions_for_continuation": [],
                    "useful_clarifications": [],
                    "deferred_non_critical_notes": [question["question_id"] for question in questions],
                },
            },
            gap_report=gap_report,
            prompt=prompt,
            model_id="clarification-model",
        )
        critical_question = next(question for question in request["questions"] if question["gap_type"] == "missing_period")
        validation = validate_clarification_request(
            request=request,
            gap_report=gap_report,
            prompt=prompt,
            model_id="clarification-model",
        )

        self.assertEqual(critical_question["criticality"], "critical")
        self.assertTrue(critical_question["blocks_gate2"])
        self.assertTrue(critical_question["resolution_required"])
        self.assertEqual(critical_question["ask_policy"], "ask_now")
        self.assertEqual(critical_question["dependency_stage"], "gate2_handoff")
        self.assertEqual(critical_question["blocking_reason_category"], "source_scope")
        self.assertEqual(critical_question["auto_resolution_policy"], "none")
        self.assertEqual(validation["validator_status"], "passed")

    def test_gap_report_turns_metadata_and_duplicate_blockers_into_question_stubs(self):
        package = self._package_with_missing_period_and_duplicate()

        gap_report = build_metadata_gap_report(package)

        self.assertEqual(gap_report["schema_version"], "gate1_metadata_gap_report_v0")
        self.assertEqual(gap_report["summary"]["metadata_review_document_count"], 1)
        self.assertEqual(gap_report["summary"]["duplicate_group_count"], 1)
        self.assertEqual(gap_report["summary"]["gap_type_counts"]["missing_period"], 1)
        self.assertEqual(gap_report["summary"]["gap_type_counts"]["duplicate_canonical_choice"], 1)
        stubs = {stub["gap_type"]: stub for stub in gap_report["question_stubs"]}
        self.assertEqual(stubs["missing_period"]["answer_type"], "provide_report_period")
        self.assertEqual(stubs["duplicate_canonical_choice"]["answer_type"], "select_canonical_document")
        rendered = json.dumps(gap_report, ensure_ascii=False, sort_keys=True)
        self.assertNotIn("synthetic_note.txt", rendered)
        self.assertNotIn("openwebui-file", rendered)

    def test_skipped_gap_remains_unresolved_in_domain_context_packet(self):
        base = Gate1Normalizer().normalize(
            [
                FileInput.from_bytes(
                    private_ref="outside-scope-source",
                    filename="synthetic_broker_report.txt",
                    content=b"Safe synthetic broker report outside current case scope.",
                    mime_type="text/plain",
                    source_kind="openwebui_pipe",
                )
            ],
            input_context={"test_case": "skipped_gap_domain_context"},
        )
        package = base.package
        document_id = package["document_inventory"]["documents"][0]["document_id"]
        package["document_source_eligibility"]["entries"][0].update(
            {
                "source_eligibility": "outside_case_scope",
                "can_enter_gate2": False,
                "included_in_reduced_subset": False,
                "exclusion_is_terminal": True,
                "reason_codes": ["passport_outside_case_scope"],
            }
        )
        package["gate2_handoff"].update(
            {
                "handoff_mode": "gate2_blocked_no_eligible_sources",
                "gate2_handoff_status": "blocked",
                "included_document_ids": [],
                "excluded_document_ids": [document_id],
            }
        )
        package["normalization_run"]["gate2_handoff_mode"] = "gate2_blocked_no_eligible_sources"
        package["normalization_run"]["gate2_handoff_status"] = "blocked"
        package["document_metadata_passports"] = [
            {
                "schema_version": "document_metadata_passport_v0",
                "passport_id": f"passport_{document_id}",
                "normalization_run_id": package["normalization_run"]["run_id"],
                "document_id": document_id,
                "passport_status": "validated",
                "content_kind": "outside_case_scope",
                "role_hypotheses": [
                    {
                        "role": "outside_case_scope",
                        "confidence": "high",
                        "reason_codes": ["test_outside_scope"],
                        "evidence_refs": [document_id],
                        "source_policy_effect": "excluded_from_gate2",
                    }
                ],
                "source_candidate_confidence": "none",
                "metadata_confidence": "high",
                "evidence_refs": [document_id],
                "missing_metadata_fields": [],
                "conflict_flags": [],
                "review_required": False,
                "validator_status": "passed",
            }
        ]

        applied = apply_metadata_gap_report_stage(
            package,
            private_markers=base.private_markers,
            criticality_refinement_enabled=True,
        )
        issue = next(
            item
            for item in applied["package"]["gate1_issue_ledger"]["entries"]
            if item["issue_type"] == "outside_scope_confirmation"
        )
        packet = applied["package"]["domain_context_packet"]

        self.assertEqual(applied["package"]["gate1_metadata_gap_report"]["question_stubs"], [])
        self.assertEqual(issue["status"], "unresolved")
        self.assertEqual(issue["unresolved_reason"], "skipped_question")
        self.assertFalse(issue["user_was_asked"])
        self.assertFalse(issue["answer_supplied"])
        self.assertEqual(issue["ask_policy"], "do_not_ask")
        self.assertIn(issue["issue_id"], packet["unresolved_issue_refs"])
        self.assertGreater(packet["unresolved_issue_summary"]["skipped_unresolved_issues_total"], 0)

    def test_unanswered_clarification_question_is_carried_as_unresolved_issue(self):
        package = {
            "normalization_run": {"run_id": "normrun_unanswered_question"},
            "summary_counts": {},
            "document_inventory": {
                "documents": [
                    {
                        "document_id": "doc_asked",
                        "container_format": "txt",
                        "bytes_status": "available",
                        "readable": "yes",
                        "machine_readable": True,
                    }
                ]
            },
            "taxonomy_candidates": [
                {
                    "document_id": "doc_asked",
                    "document_class_candidate": "source_broker_report",
                }
            ],
            "document_source_eligibility": {
                "entries": [
                    {
                        "document_id": "doc_asked",
                        "source_eligibility": "accepted_for_gate2",
                        "reason_codes": [],
                    }
                ]
            },
            "normalization_blockers": [],
            "gate1_clarification_request": {
                "schema_version": "gate1_clarification_request_v0",
                "clarification_request_id": "clarreq_unanswered",
                "questions": [
                    {
                        "question_id": "q_unanswered",
                        "gap_id": "gap_unanswered",
                        "gap_type": "missing_account_or_contract",
                        "target_document_refs": ["doc_asked"],
                        "answer_type": "free_text",
                        "criticality": "clarifying",
                        "blocking_scope": "downstream_quality",
                        "dependency_stage": "declaration_model",
                        "blocking_reason_category": "metadata_completeness",
                        "auto_resolution_policy": "none",
                        "blocks_gate2": False,
                        "resolution_required": False,
                        "can_proceed_with_warning": True,
                        "ask_policy": "ask_now",
                        "answer_impact": "adds_audit_context",
                        "priority": "medium",
                        "required": False,
                        "reason_codes": ["missing_account_or_contract"],
                        "safe_explanation": "Account metadata was requested but not answered.",
                    }
                ],
            },
            "gate1_clarification_resolutions": [],
        }

        applied = apply_domain_ingestion_artifacts(package)
        issue = next(
            item
            for item in applied["gate1_issue_ledger"]["entries"]
            if item["issue_type"] == "metadata_gap"
        )
        packet = applied["domain_context_packet"]

        self.assertEqual(issue["status"], "unresolved")
        self.assertEqual(issue["unresolved_reason"], "awaiting_answer")
        self.assertTrue(issue["user_was_asked"])
        self.assertFalse(issue["answer_supplied"])
        self.assertEqual(issue["ask_policy"], "ask_now")
        self.assertIn(issue["issue_id"], packet["unresolved_issue_refs"])
        self.assertGreater(packet["unresolved_issue_summary"]["awaiting_answer_unresolved_issues_total"], 0)

    def test_resolution_answers_rerun_eligibility_without_weaking_passport_validator(self):
        package = self._package_with_missing_period_and_duplicate()
        prompt = self._clarification_prompt()
        raw_output = self._raw_clarification_output(package, prompt)

        applied = apply_clarification_request_stage(
            package=package,
            prompt=prompt,
            model_id="clarification-model",
            raw_output=raw_output,
            private_markers=[],
            answers=[
                {
                    "gap_type": "missing_period",
                    "answer_value": "2025-01-01..2025-12-31",
                    "answered_by": "operator-1",
                    "source": "operator_confirmed",
                    "answered_at": "2026-07-09T00:00:00Z",
                }
            ],
        )

        entry = applied["package"]["document_source_eligibility"]["entries"][0]
        self.assertEqual(applied["package"]["document_metadata_passports"][0]["validator_status"], "passed")
        self.assertEqual(entry["source_eligibility"], "accepted_for_gate2")
        self.assertTrue(entry["included_in_reduced_subset"])
        self.assertIn("report_period_start", entry["clarification_resolution_basis"]["resolved_fields"])
        self.assertEqual(applied["package"]["gate2_handoff"]["handoff_mode"], "reduced_subset_ready_for_gate2")

    def test_artifactstore_persists_clarification_artifacts_with_safe_visibility(self):
        package = self._package_with_missing_period_and_duplicate()
        prompt = self._clarification_prompt()
        raw_output = self._raw_clarification_output(package, prompt)
        gap_report = build_metadata_gap_report(package)
        period_question = next(stub for stub in gap_report["question_stubs"] if stub["gap_type"] == "missing_period")
        applied = apply_clarification_request_stage(
            package=package,
            prompt=prompt,
            model_id="clarification-model",
            raw_output=raw_output,
            private_markers=[],
            answers=[
                {
                    "question_id": period_question["question_id"],
                    "answer_value": "2025-01-01..2025-12-31",
                    "answered_by": "operator-1",
                    "source": "operator_confirmed",
                    "answered_at": "2026-07-09T00:00:00Z",
                },
                {
                    "gap_type": "missing_broker_client_metadata",
                    "answer_value": "operator supplied but not requested for this package",
                    "answered_by": "operator-1",
                    "source": "operator_confirmed",
                    "answered_at": "2026-07-09T00:00:01Z",
                }
            ],
        )
        result = type("Result", (), applied)()
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store = ArtifactStoreFactory(
                ArtifactStoreConfig(
                    mode="sqlite",
                    sqlite_path=root / "artifacts.sqlite3",
                    payload_root=root / "payloads",
                )
            ).create()
            context = ArtifactAccessContext(
                user_id="user-clarification",
                case_id="case-clarification",
                chat_id="chat-clarification",
                workspace_model_id="broker_reports_gate1_pipe",
                normalization_run_id=applied["package"]["normalization_run"]["run_id"],
                allow_private=True,
            )
            manifest = persist_gate1_result(
                store=store,
                result=result,
                context=context,
                retention_policy=build_retention_policy(mode="api_smoke"),
            )
            records = store.list_by_run(context.normalization_run_id)
            handoff_record = store.get_record_unchecked(manifest.gate2_handoff_ref)
            handoff_payload = store.read_payload(handoff_record)

        by_type = {record.artifact_type: record for record in records}
        resolution_records = [
            record
            for record in records
            if record.artifact_type == "gate1_clarification_resolution_v0"
        ]
        passed_resolution_refs = [
            record.artifact_id
            for record in resolution_records
            if record.validation_status == "validated"
        ]
        blocked_resolution_refs = [
            record.artifact_id
            for record in resolution_records
            if record.validation_status == "blocked"
        ]
        self.assertIn("gate1_metadata_gap_report_v0", by_type)
        self.assertIn("llm_clarification_prompt_snapshot_v0", by_type)
        self.assertIn("llm_clarification_raw_output_v0", by_type)
        self.assertIn("gate1_clarification_request_v0", by_type)
        self.assertIn("gate1_clarification_resolution_v0", by_type)
        self.assertEqual(by_type["gate1_metadata_gap_report_v0"].visibility, "safe_internal")
        self.assertEqual(by_type["gate1_clarification_request_v0"].visibility, "safe_internal")
        self.assertEqual(by_type["llm_clarification_raw_output_v0"].visibility, "private_case")
        self.assertEqual(by_type["gate1_clarification_resolution_v0"].visibility, "private_case")
        self.assertNotEqual(by_type["gate1_clarification_resolution_v0"].storage_backend, "openwebui_knowledge")
        self.assertIn("gate1_clarification_request_v0", manifest.artifact_refs_by_type)
        self.assertTrue(passed_resolution_refs)
        self.assertTrue(blocked_resolution_refs)
        self.assertTrue(set(passed_resolution_refs).issubset(set(handoff_payload["clarification_resolution_refs"])))
        self.assertFalse(set(blocked_resolution_refs) & set(handoff_payload["clarification_resolution_refs"]))
        self.assertLess(len(handoff_payload["private_slice_refs"]), len(manifest.private_slice_refs))

    def test_compact_report_groups_clarification_questions_in_russian_without_raw_json(self):
        package = self._package_with_missing_period_and_duplicate()
        prompt = self._clarification_prompt()
        applied = apply_clarification_request_stage(
            package=package,
            prompt=prompt,
            model_id="clarification-model",
            raw_output=self._raw_clarification_output(package, prompt),
            private_markers=[],
        )

        content = render_chat_content(applied["safe_report"])

        self.assertIn("Критично для продолжения", content)
        self.assertIn("Вопросы для уточнения:", content)
        self.assertIn("Не указан период отчета", content)
        self.assertIn("Нужно выбрать основной документ среди дублей", content)
        self.assertNotIn("```json", content)
        self.assertNotIn("answer_value", content)

    def _package_with_missing_period_and_duplicate(self) -> dict:
        base = Gate1Normalizer().normalize(
            [
                FileInput.from_bytes(
                    private_ref="clarification-source-1",
                    filename="synthetic_note.txt",
                    content=b"Safe synthetic broker report candidate.",
                    mime_type="text/plain",
                    source_kind="openwebui_pipe",
                ),
                FileInput.from_bytes(
                    private_ref="clarification-source-2",
                    filename="synthetic_note_copy.txt",
                    content=b"Safe synthetic broker report candidate.",
                    mime_type="text/plain",
                    source_kind="openwebui_pipe",
                ),
            ],
            input_context={"test_case": "clarification_loop"},
        )
        prompt = self._passport_prompt()
        llm_packages = build_llm_document_packages(
            package=base.package,
            prompt=prompt,
            model_id="passport-model",
        )
        passports = []
        for index, llm_package in enumerate(llm_packages):
            passport = self._valid_passport(llm_package, prompt)
            if index == 0:
                passport["report_period_start"] = None
                passport["report_period_end"] = None
                passport["missing_metadata_fields"] = ["report_period_start", "report_period_end"]
                passport["review_required"] = True
                passport["metadata_confidence"] = "low"
            passports.append(
                {
                    "schema_version": "llm_passport_raw_output_v0",
                    "document_id": llm_package["document_id"],
                    "normalization_run_id": llm_package["normalization_run_id"],
                    "llm_input_package_id": llm_package["llm_input_package_id"],
                    "model_call_status": "passed",
                    "raw_output": passport,
                    "error_code": None,
                    **model_call_audit_metadata(
                        prompt=prompt,
                        model_id="passport-model",
                        structured_output_mode="openwebui_response_format_json_schema",
                        response_format_type="json_schema",
                        response_format_schema_mode="strict_json_schema",
                        schema_attempted=True,
                    ),
                }
            )
        applied = apply_document_passport_stage(
            package=base.package,
            prompt=prompt,
            model_id="passport-model",
            llm_packages=llm_packages,
            raw_outputs=passports,
            private_markers=base.private_markers,
        )
        return applied["package"]

    def _minimal_criticality_package(self) -> dict:
        return {
            "normalization_run": {
                "run_id": "normrun_criticality",
                "gate2_handoff_status": "blocked",
                "gate2_handoff_mode": "gate2_blocked_requires_metadata_review",
            },
            "document_source_eligibility": {
                "entries": [
                    {
                        "document_id": "doc_critical",
                        "source_eligibility": "metadata_review_required",
                        "reason_codes": ["document_metadata_passport_incomplete"],
                        "blocker_refs": [],
                    },
                    {
                        "document_id": "doc_clarifying",
                        "source_eligibility": "accepted_for_gate2",
                        "reason_codes": ["metadata_clarification_warning_present"],
                        "blocker_refs": [],
                    },
                    {
                        "document_id": "doc_noncritical",
                        "source_eligibility": "accepted_for_gate2",
                        "reason_codes": ["metadata_non_critical_fields_deferred"],
                        "blocker_refs": [],
                    },
                    {
                        "document_id": "doc_outside",
                        "source_eligibility": "outside_case_scope",
                        "reason_codes": ["passport_outside_case_scope"],
                        "blocker_refs": [],
                    },
                ]
            },
            "document_inventory": {
                "documents": [
                    {"document_id": "doc_critical"},
                    {"document_id": "doc_clarifying"},
                    {"document_id": "doc_noncritical"},
                    {"document_id": "doc_outside"},
                ]
            },
            "document_metadata_passports": [
                self._minimal_passport(
                    "doc_critical",
                    missing_metadata_fields=["report_period_start", "report_period_end"],
                    review_required=True,
                ),
                self._minimal_passport(
                    "doc_clarifying",
                    missing_metadata_fields=["account_or_contract_candidate"],
                    review_required=True,
                ),
                self._minimal_passport(
                    "doc_noncritical",
                    missing_metadata_fields=["metadata_confirmation"],
                    review_required=True,
                ),
                self._minimal_passport("doc_outside", content_kind="outside_case_scope", role="outside_case_scope"),
            ],
            "normalization_blockers": [],
        }

    def _minimal_passport(
        self,
        document_id: str,
        *,
        missing_metadata_fields: list[str] | None = None,
        review_required: bool = False,
        content_kind: str = "source_report_candidate",
        role: str = "source_broker_report",
    ) -> dict:
        return {
            "document_id": document_id,
            "content_kind": content_kind,
            "role_hypotheses": [{"role": role, "confidence": "high"}],
            "missing_metadata_fields": missing_metadata_fields or [],
            "conflict_flags": [],
            "review_required": review_required,
            "evidence_refs": [document_id],
            "validator_status": "passed",
        }

    def _raw_clarification_output(self, package: dict, prompt: ClarificationManagedPrompt) -> dict:
        gap_report = build_metadata_gap_report(package)
        questions = []
        for stub in gap_report["question_stubs"]:
            question = dict(stub)
            question["question_text"] = f"Уточните значение для {stub['gap_type']} по безопасной ссылке документа."
            question["why_asked"] = "Без этого Gate 2 handoff не может быть пересчитан безопасно."
            question.pop("gap_id", None)
            question.pop("resolved_fields", None)
            questions.append(question)
        return {
            "schema_version": "llm_clarification_raw_output_v0",
            "normalization_run_id": package["normalization_run"]["run_id"],
            "gap_report_id": gap_report["gap_report_id"],
            "model_call_status": "passed",
            "raw_output": {
                "schema_version": CLARIFICATION_REQUEST_SCHEMA_VERSION,
                "questions": questions,
                "question_groups": gap_report["question_groups"],
            },
            "error_code": None,
            "llm_model_id": "clarification-model",
            "llm_prompt_ref": prompt.prompt_ref,
            "llm_prompt_command": prompt.command,
            "llm_prompt_version": prompt.version,
            "llm_prompt_hash": prompt.hash,
            "structured_output_mode": "openwebui_response_format_json_schema",
            "response_format_type": "json_schema",
            "response_format_schema_mode": "strict_json_schema",
            "schema_attempted": True,
            "fallback_used": False,
            "output_schema_id": "broker_reports.gate1_clarification_request.schema.v0",
            "output_schema_version": "gate1_clarification_request_v0",
            "output_schema_hash": gate1_clarification_request_schema_hash(),
        }

    def _passport_prompt(self) -> ManagedPrompt:
        content = "Managed prompt body v1"
        return ManagedPrompt(
            prompt_ref="prompt-passport-1",
            command="broker_gate1_document_passport",
            version="passport-v1",
            content=content,
            hash=prompt_hash(content, "broker_reports_document_metadata_passport_prompt_v0", "document_metadata_passport_v0"),
            source="openwebui_prompt",
            template_id="broker_reports.document_metadata_passport.v0",
            template_kind="document_metadata_passport",
            output_schema_version="document_metadata_passport_v0",
            tags=("broker-reports-gate1", "document-metadata-passport"),
            safe_metadata={},
        )

    def _clarification_prompt(self) -> ClarificationManagedPrompt:
        content = "Managed clarification prompt body v1"
        return ClarificationManagedPrompt(
            prompt_ref="prompt-clarification-1",
            command="broker_gate1_clarification_request",
            version="clarification-v1",
            content=content,
            hash=clarification_prompt_hash(content, CLARIFICATION_PROMPT_CONTRACT_ID, "gate1_clarification_request_v0"),
            source="openwebui_prompt",
            template_id="broker_reports.gate1_clarification_request.v0",
            template_kind="gate1_clarification_request",
            output_schema_version="gate1_clarification_request_v0",
            tags=("broker-reports-gate1", "metadata-clarification"),
            safe_metadata={},
        )

    def _valid_passport(self, llm_package: dict, prompt: ManagedPrompt) -> dict:
        evidence_refs = [str(llm_package["evidence_refs"][0]), str(llm_package["llm_input_package_id"])]
        return {
            "schema_version": "document_metadata_passport_v0",
            "passport_id": f"passport_{llm_package['document_id']}",
            "normalization_run_id": llm_package["normalization_run_id"],
            "case_group_id": llm_package.get("case_group_id"),
            "document_id": llm_package["document_id"],
            "source_file_ref": llm_package["source_file_ref"],
            "passport_status": "draft",
            "document_title_candidate": "safe broker report candidate",
            "document_kind_candidate": "broker_activity_statement",
            "broker_name_candidate": "safe broker candidate",
            "client_name_candidate": None,
            "account_or_contract_candidate": "safe account candidate",
            "report_period_start": "2025-01-01",
            "report_period_end": "2025-12-31",
            "tax_year_candidate": 2025,
            "created_at_candidate": None,
            "document_language": "en",
            "document_format": "text",
            "container_format": llm_package["document_summary"]["container_format"],
            "content_kind": "source_report_candidate",
            "sections_detected": [
                {
                    "label": "summary",
                    "normalized_label": "summary",
                    "present": True,
                    "confidence": "medium",
                    "evidence_refs": evidence_refs,
                }
            ],
            "tables_detected": [],
            "operation_sections_detected": [],
            "cashflow_sections_detected": [],
            "income_sections_detected": [],
            "withholding_sections_detected": [],
            "tax_sections_detected": [],
            "role_hypotheses": [
                {
                    "role": "source_broker_report",
                    "confidence": "high",
                    "reason_codes": ["metadata_present"],
                    "evidence_refs": evidence_refs,
                    "source_policy_effect": "accepted_candidate_if_policy_allows",
                }
            ],
            "source_candidate_confidence": "high",
            "metadata_confidence": "high",
            "evidence_refs": evidence_refs,
            "missing_metadata_fields": [],
            "conflict_flags": [],
            "review_required": False,
            "llm_prompt_ref": prompt.prompt_ref,
            "llm_prompt_command": prompt.command,
            "llm_prompt_version": prompt.version,
            "llm_prompt_hash": prompt.hash,
            "llm_model_id": "passport-model",
            "llm_input_refs": [llm_package["llm_input_package_id"]],
            "validator_status": "pending",
            "validator_errors": [],
            "created_at": "2026-07-09T00:00:00Z",
        }

    def _create_clarification_prompt_db(self, path: Path) -> None:
        conn = sqlite3.connect(path)
        try:
            conn.execute(
                """
                CREATE TABLE prompt(
                    id TEXT PRIMARY KEY,
                    command TEXT,
                    user_id TEXT,
                    name TEXT,
                    content TEXT,
                    data TEXT,
                    meta TEXT,
                    tags TEXT,
                    is_active INTEGER,
                    version_id TEXT
                )
                """
            )
            conn.execute(
                """
                INSERT INTO prompt(id, command, user_id, name, content, data, meta, tags, is_active, version_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "prompt-clarification-1",
                    "broker_gate1_clarification_request",
                    "owner-1",
                    "Broker Reports Gate 1 Clarification",
                    "Managed clarification prompt body v1",
                    "{}",
                    json.dumps(
                        {
                            "template_kind": "gate1_clarification_request",
                            "template_id": "broker_reports.gate1_clarification_request.v0",
                            "output_schema_version": "gate1_clarification_request_v0",
                        }
                    ),
                    json.dumps(["broker-reports-gate1", "metadata-clarification"]),
                    1,
                    "clarification-v1",
                ),
            )
            conn.commit()
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
