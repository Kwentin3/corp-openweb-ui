from __future__ import annotations

import asyncio
import hashlib
import json
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from broker_reports_gate1 import (
    ArtifactStoreError,
    BytesUnavailable,
    RetentionPolicyError,
)
from broker_reports_gate1 import ManagedPrompt
from broker_reports_gate1.private_intake_bytes import PrivateIntakeBytesError
from broker_reports_gate1.document_passport import document_metadata_passport_schema_hash, prompt_hash
from openwebui_actions.broker_reports_gate1_pipe import NORMALIZER_VERSION, SAFETY_STATEMENT, Pipe
from tests.test_broker_reports_pdf_layout_slice2 import _ruled_table_pdf


def run_pipe(pipe: Pipe, body: dict, **kwargs) -> str:
    kwargs.setdefault("__user__", {"id": "pipe-test-user"})
    kwargs.setdefault(
        "__metadata__",
        {"chat_id": "pipe-test-chat", "model_id": "broker_reports_gate1_pipe_test"},
    )
    return asyncio.run(pipe.pipe(body, **kwargs))


def file_ref(file_id: str, filename: str, mime_type: str, **extra):
    payload = {
        "id": file_id,
        "filename": filename,
        "mime_type": mime_type,
    }
    payload.update(extra)
    return {"type": "file", "file": payload}


class PassportRepairPipe(Pipe):
    def __init__(self) -> None:
        super().__init__()
        content = "{{document_package_json}}"
        self.prompt = ManagedPrompt(
            prompt_ref="prompt-passport-test",
            command="broker_gate1_document_passport",
            version="passport-test-v1",
            content=content,
            hash=prompt_hash(
                content,
                "broker_reports_document_metadata_passport_prompt_v0",
                "document_metadata_passport_v0",
            ),
            source="openwebui_prompt",
            template_id="broker_reports.document_metadata_passport.v0",
            template_kind="document_metadata_passport",
            output_schema_version="document_metadata_passport_v0",
            tags=("broker-reports-gate1", "document-metadata-passport"),
            safe_metadata={},
        )
        self.completion_forms: list[dict] = []

    def _resolve_passport_prompt(self, *, user, metadata: dict, body: dict) -> ManagedPrompt:
        return self.prompt

    def _openwebui_completion_dependencies(self, user_id: str):
        class UserModel:
            role = "admin"

        return self._fake_completion, UserModel()

    def _fake_completion(self, *, request, form_data, user, bypass_filter=False, bypass_system_prompt=False):
        self.completion_forms.append(form_data)
        package = json.loads(form_data["messages"][0]["content"])
        if len(self.completion_forms) == 1:
            payload = {"schema_version": "document_metadata_passport_v0"}
        else:
            payload = self._valid_passport(package)
        return {"choices": [{"message": {"content": json.dumps(payload, ensure_ascii=False)}}]}

    def _valid_passport(self, llm_package: dict) -> dict:
        evidence_refs = [str(llm_package["evidence_refs"][0]), str(llm_package["llm_input_package_id"])]
        return {
            "schema_version": "document_metadata_passport_v0",
            "passport_id": "passport_pipe_repaired",
            "normalization_run_id": llm_package["normalization_run_id"],
            "case_group_id": llm_package.get("case_group_id"),
            "document_id": llm_package["document_id"],
            "source_file_ref": llm_package["source_file_ref"],
            "passport_status": "draft",
            "document_title_candidate": "safe repaired broker report candidate",
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
            "llm_prompt_ref": self.prompt.prompt_ref,
            "llm_prompt_command": self.prompt.command,
            "llm_prompt_version": self.prompt.version,
            "llm_prompt_hash": self.prompt.hash,
            "llm_model_id": "passport-model",
            "llm_input_refs": [llm_package["llm_input_package_id"]],
            "validator_status": "pending",
            "validator_errors": [],
            "created_at": "2026-07-09T00:00:00Z",
        }


class BrokerReportsGate1PipeSlice1Test(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def _pipe(self) -> Pipe:
        pipe = Pipe()
        root = Path(self._tmp.name)
        pipe.valves.artifact_store_path = str(root / "artifacts.sqlite3")
        pipe.valves.artifact_payload_root = str(root / "payloads")
        return pipe

    def _passport_pipe(self) -> PassportRepairPipe:
        pipe = PassportRepairPipe()
        root = Path(self._tmp.name)
        pipe.valves.artifact_store_path = str(root / "artifacts.sqlite3")
        pipe.valves.artifact_payload_root = str(root / "payloads")
        pipe.valves.passport_enabled = True
        pipe.valves.passport_model_id = "passport-model"
        return pipe

    def test_unaccepted_broker_pdf_profile_is_release_gated_by_default(self):
        pipe = self._pipe()

        self.assertFalse(
            pipe.valves.broker_pdf_neutral_table_profile_v1_enabled
        )

    def test_artifact_context_ignores_client_selected_scope(self):
        context = self._pipe()._artifact_context(
            user={"id": "trusted-user"},
            metadata={
                "chat_id": "trusted-chat",
                "model_id": "trusted-model",
            },
            body={
                "chat_id": "forged-chat",
                "case_id": "forged-case",
                "model_id": "forged-model",
                "metadata": {"case_id": "forged-nested-case"},
            },
            kwargs={"chat_id": "forged-kwarg-chat"},
            normalization_run_id="trusted-run",
        )

        self.assertEqual(context.user_id, "trusted-user")
        self.assertEqual(context.chat_id, "trusted-chat")
        self.assertIsNone(context.case_id)
        self.assertEqual(context.workspace_model_id, "trusted-model")
        self.assertEqual(context.normalization_run_id, "trusted-run")

    def test_private_intake_bytes_ignore_client_inline_content_and_path(self):
        pipe = self._pipe()
        trusted = b"trusted receipt-owned bytes"

        class Resolver:
            async def resolve(self, *, source_id: str, actor_user_id: str):
                self.call = (source_id, actor_user_id)
                return trusted

        resolver = Resolver()
        file_ref_value = {
            "file_id": "br-11111111-2222-3333-4444-555555555555",
            "filename": "synthetic.pdf",
            "_private_file_obj": {
                "content_bytes": b"forged client bytes",
                "path": "forged/client/path",
            },
        }

        with patch.object(
            pipe,
            "_private_intake_bytes_resolver",
            return_value=resolver,
        ):
            asyncio.run(
                pipe._hydrate_private_intake_file_refs(
                    [file_ref_value],
                    actor_user_id="trusted-user",
                )
            )

        self.assertEqual(
            resolver.call,
            ("br-11111111-2222-3333-4444-555555555555", "trusted-user"),
        )
        self.assertEqual(pipe._read_original_bytes(file_ref_value), trusted)

    def test_private_intake_resolution_failure_does_not_use_client_bytes(self):
        pipe = self._pipe()

        class Resolver:
            async def resolve(self, *, source_id: str, actor_user_id: str):
                raise PrivateIntakeBytesError("private_intake_receipt_invalid")

        file_ref_value = {
            "file_id": "br-aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            "filename": "synthetic.pdf",
            "_private_file_obj": {"content_bytes": b"forged client bytes"},
        }
        with patch.object(
            pipe,
            "_private_intake_bytes_resolver",
            return_value=Resolver(),
        ):
            asyncio.run(
                pipe._hydrate_private_intake_file_refs(
                    [file_ref_value],
                    actor_user_id="trusted-user",
                )
            )

        with self.assertRaisesRegex(
            BytesUnavailable,
            "private_intake_receipt_invalid",
        ):
            pipe._read_original_bytes(file_ref_value)

    def test_artifact_context_requires_server_user_and_case_or_chat(self):
        pipe = self._pipe()
        with self.assertRaisesRegex(
            ArtifactStoreError,
            "Authenticated server user context is required",
        ):
            pipe._artifact_context(
                user=None,
                metadata={"chat_id": "trusted-chat"},
                body={"user_id": "forged-user"},
                kwargs={},
                normalization_run_id="trusted-run",
            )
        with self.assertRaisesRegex(
            ArtifactStoreError,
            "Server-attested case or chat context is required",
        ):
            pipe._artifact_context(
                user={"id": "trusted-user"},
                metadata={"model_id": "trusted-model"},
                body={"case_id": "forged-case", "chat_id": "forged-chat"},
                kwargs={"chat_id": "forged-kwarg-chat"},
                normalization_run_id="trusted-run",
            )

    def test_pipe_clarification_model_id_ignores_workspace_model_metadata(self):
        pipe = self._pipe()
        body = {
            "broker_reports_gate1": {
                "clarification": {
                    "enabled": True,
                    "model_id": "clarification-model",
                    "prompt_command": "broker_gate1_clarification_request",
                }
            },
            "metadata": {
                "broker_reports_gate1": {
                    "clarification": {
                        "enabled": True,
                        "model_id": "clarification-model",
                        "prompt_command": "broker_gate1_clarification_request",
                    }
                }
            },
            "messages": [{"role": "user", "content": "broker_reports_gate1_clarification enabled=true"}],
        }
        metadata = {"chat_id": "pipe-test-chat", "model_id": "broker_reports_gate1_pipe"}

        self.assertEqual(pipe._clarification_model_id(body, metadata), "clarification-model")

    def test_pipe_collects_files_and_returns_contract_safe_inventory(self):
        pipe = self._pipe()
        txt = (
            "Synthetic Person Alpha\n"
            "Synthetic Broker LLC\n"
            "SYNTH-ACCOUNT-001\n"
            "SYNTH-A\n"
            "SYNTH-FCY\n"
        )
        csv = (
            "synthetic_symbol,synthetic_quantity,synthetic_currency,synthetic_note\n"
            "SYNTH-A,1,SYNTH-FCY,synthetic operation row for Gate 1 only\n"
        )

        content = run_pipe(
            pipe,
            {
                "messages": [
                    {
                        "role": "user",
                        "content": "Gate 1 normalization with private prompt text",
                        "files": [
                            file_ref(
                                "pipe-file-txt-1",
                                "synthetic_gate1_text_pdf_or_txt.txt",
                                "text/plain",
                                content=txt,
                            ),
                            file_ref(
                                "pipe-file-csv-1",
                                "synthetic_gate1_operations.csv",
                                "text/csv",
                                content=csv,
                            ),
                        ],
                    }
                ],
            },
        )

        report = pipe.last_safe_report
        self.assertIsNotNone(report)
        self.assertNotIn("```json", content)
        self.assertIn("Нормализация завершена.", content)
        self.assertIn("Техническая ссылка: run", content)
        self.assertIsNotNone(pipe.last_artifact_manifest)
        self.assertEqual(report["trigger_type"], "pipe_backend_normalizer")
        self.assertEqual(report["entrypoint"], "broker_reports_gate1_pipe")
        self.assertEqual(report["normalizer_version"], NORMALIZER_VERSION)
        self.assertEqual(report["input_context"]["normalizer_version"], NORMALIZER_VERSION)
        self.assertEqual(report["run_status"], "completed")
        self.assertEqual(report["file_ref_visibility"], "visible")
        self.assertEqual(report["files_total"], 2)
        self.assertEqual(report["summary_counts"]["files_total"], 2)
        self.assertEqual(report["container_counts"], {"txt": 1, "csv": 1})
        self.assertEqual(report["summary_counts"]["container_counts"], {"txt": 1, "csv": 1})
        self.assertEqual(report["duplicate_count"], 0)
        self.assertEqual(report["blockers_total"], 0)
        self.assertEqual(len(report["documents"]), 2)
        self.assertEqual(
            report["documents"][0]["sha256"],
            hashlib.sha256(txt.encode("utf-8")).hexdigest(),
        )
        self.assertEqual(
            report["documents"][1]["sha256"],
            hashlib.sha256(csv.encode("utf-8")).hexdigest(),
        )
        self.assertEqual(report["normalization_run"]["schema_version"], "normalization_run_v0")
        self.assertEqual(report["normalization_run"]["gate2_handoff_status"], "ready_with_safe_refs")
        self.assertEqual(report["normalization_run"]["gate2_handoff_mode"], "full_package_ready_for_gate2")
        self.assertEqual(report["source_eligibility_summary"]["accepted_for_gate2"], 2)
        self.assertEqual(report["safety_statement"], SAFETY_STATEMENT)
        self.assertFalse(report["safety_flags"]["tax_correctness_claimed"])
        self.assertFalse(report["safety_flags"]["source_fact_extraction_performed"])
        self.assertFalse(report["safety_flags"]["declaration_generated"])
        self.assertFalse(report["safety_flags"]["xlsx_generated"])
        self.assertFalse(report["safety_flags"]["ocr_performed"])
        self.assertNotIn("pipe-file-csv-1", content)
        self.assertNotIn("synthetic_gate1_operations.csv", content)
        self.assertNotIn("private prompt text", content)
        self.assertNotIn("SYNTH-ACCOUNT-001", content)
        self.assertNotIn("SYNTH-A,1,SYNTH-FCY", content)
        self.assertNotIn(csv, content)

    def test_pipe_passport_uses_json_schema_and_one_bounded_repair_attempt(self):
        pipe = self._passport_pipe()

        content = run_pipe(
            pipe,
            {
                "metadata": {"case_id": "case-passport-repair"},
                "messages": [
                    {
                        "role": "user",
                        "content": "Gate 1 normalization with passport",
                        "files": [
                            file_ref(
                                "pipe-file-passport-1",
                                "passport_source.txt",
                                "text/plain",
                                content="Safe synthetic broker report summary for passport repair test.",
                            )
                        ],
                    }
                ],
            },
            __request__=object(),
        )

        self.assertEqual(len(pipe.completion_forms), 2)
        self.assertEqual(pipe.completion_forms[0]["response_format"]["type"], "json_schema")
        self.assertEqual(pipe.completion_forms[1]["response_format"]["type"], "json_schema")
        llm_package = json.loads(pipe.completion_forms[0]["messages"][0]["content"])
        allowed_evidence_refs = [
            *llm_package["evidence_refs"],
            llm_package["llm_input_package_id"],
        ]
        repair_payload = json.loads(pipe.completion_forms[1]["messages"][1]["content"])
        self.assertEqual(repair_payload["allowed_evidence_refs"], allowed_evidence_refs)
        self.assertIn("error_subjects_by_code", repair_payload["validator_error_summary"])
        for ref in allowed_evidence_refs:
            self.assertIn(ref, pipe.completion_forms[0]["messages"][1]["content"])
        self.assertEqual(
            pipe.completion_forms[0]["metadata"]["broker_reports_gate1"]["structured_output_mode"],
            "openwebui_response_format_json_schema",
        )
        report = pipe.last_safe_report
        self.assertIsNotNone(report)
        self.assertEqual(report["document_metadata_passport_summary"]["validated"], 1)
        self.assertEqual(report["document_metadata_passport_summary"]["failed"], 0)
        self.assertNotIn("```json", content)
        conn = sqlite3.connect(pipe.valves.artifact_store_path)
        try:
            raw_meta = json.loads(
                conn.execute(
                    "SELECT safe_metadata_json FROM artifact_records WHERE artifact_type = 'llm_passport_raw_output_v0'"
                ).fetchone()[0]
            )
            validation_meta = json.loads(
                conn.execute(
                    "SELECT safe_metadata_json FROM artifact_records WHERE artifact_type = 'document_metadata_passport_validation_v0'"
                ).fetchone()[0]
            )
        finally:
            conn.close()
        self.assertEqual(raw_meta["structured_output_mode"], "openwebui_response_format_json_schema")
        self.assertEqual(raw_meta["response_format_type"], "json_schema")
        self.assertTrue(raw_meta["repair_attempted"])
        self.assertEqual(raw_meta["repair_attempt_count"], 1)
        self.assertIn("passport_missing_field", raw_meta["validator_error_summary"]["error_codes"])
        self.assertEqual(raw_meta["output_schema_hash"], document_metadata_passport_schema_hash())
        self.assertEqual(validation_meta["structured_output_mode_counts"], {"openwebui_response_format_json_schema": 1})
        self.assertEqual(validation_meta["repair_attempted_count"], 1)
        self.assertEqual(validation_meta["output_schema_hash"], document_metadata_passport_schema_hash())

    def test_pipe_live_artifactstore_smoke_proves_retention_without_private_leaks(self):
        pipe = self._pipe()
        txt = (
            "Synthetic Person Alpha\n"
            "Synthetic Broker LLC\n"
            "SYNTH-ACCOUNT-001\n"
            "SYNTH-A\n"
            "SYNTH-FCY\n"
        )
        csv = (
            "synthetic_symbol,synthetic_quantity,synthetic_currency,synthetic_note\n"
            "SYNTH-A,1,SYNTH-FCY,synthetic operation row for Gate 1 only\n"
        )

        content = run_pipe(
            pipe,
            {
                "metadata": {"case_id": "case-live-smoke"},
                "messages": [
                    {
                        "role": "user",
                        "content": "Gate 1 normalization\nartifactstore retention smoke",
                        "files": [
                            file_ref(
                                "pipe-file-txt-1",
                                "synthetic_gate1_text_pdf_or_txt.txt",
                                "text/plain",
                                content=txt,
                            ),
                            file_ref(
                                "pipe-file-csv-1",
                                "synthetic_gate1_operations.csv",
                                "text/csv",
                                content=csv,
                            ),
                        ],
                    }
                ],
            },
            __metadata__={
                "case_id": "case-live-smoke",
                "chat_id": "pipe-test-chat",
                "model_id": "broker_reports_gate1_pipe_test",
            },
        )

        self.assertIn("Проверка ArtifactStore:", content)
        self.assertIn("хранилище доступно для записи: да", content)
        self.assertIn("retention policy: mode=api_smoke, explicit=True, ttl_seconds=86400", content)
        self.assertIn("normalization_run_v0", content)
        self.assertIn("document_source_eligibility_v0", content)
        self.assertIn("private_normalized_text_slice_v0", content)
        self.assertIn("private_normalized_table_slice_v0", content)
        self.assertIn("private slices в chat: нет", content)
        self.assertIn("private slices в Knowledge: нет", content)
        self.assertIn("customer_docs_loaded_to_knowledge=false", content)
        self.assertIn("Gate 2 handoff использует opaque refs, не chat JSON", content)
        self.assertIn("resolver same-context: allow", content)
        self.assertIn("resolver denies wrong-user/wrong-case/expired/purged: ok", content)
        self.assertIn("purge удалил private payloads и оставил tombstones", content)
        self.assertIn("source facts/tax/declaration/xlsx/ocr flags=false", content)
        self.assertNotIn("```json", content)
        self.assertNotIn("pipe-file-csv-1", content)
        self.assertNotIn("synthetic_gate1_operations.csv", content)
        self.assertNotIn("SYNTH-ACCOUNT-001", content)
        self.assertNotIn("SYNTH-A,1,SYNTH-FCY", content)
        self.assertNotIn(csv, content)

    def test_pipe_uses_explicit_customer_approved_retention_from_metadata(self):
        pipe = self._pipe()

        content = run_pipe(
            pipe,
            {
                "metadata": {
                    "case_id": "case-customer-retention",
                    "broker_reports_gate1": {
                        "retention_policy": {
                            "mode": "customer_approved_test",
                            "explicit": True,
                        }
                    },
                },
                "messages": [
                    {
                        "role": "user",
                        "content": "Gate 1 normalization",
                        "files": [
                            file_ref(
                                "pipe-file-customer-1",
                                "customer_approved_test.csv",
                                "text/csv",
                                content="symbol,quantity\nSAFE-A,1\n",
                            )
                        ],
                    }
                ],
            },
        )

        self.assertNotIn("```json", content)
        self.assertEqual(pipe.last_safe_report["input_context"]["retention_policy_mode"], "customer_approved_test")
        self.assertTrue(pipe.last_safe_report["input_context"]["retention_policy_explicit"])
        conn = sqlite3.connect(pipe.valves.artifact_store_path)
        try:
            policies = [
                json.loads(row[0])
                for row in conn.execute("SELECT retention_policy_json FROM artifact_records")
            ]
        finally:
            conn.close()
        self.assertTrue(policies)
        self.assertTrue(all(policy["mode"] == "customer_approved_test" for policy in policies))
        self.assertTrue(all(policy["explicit"] is True for policy in policies))

    def test_pipe_refuses_customer_approved_retention_without_explicit_policy(self):
        pipe = self._pipe()

        with self.assertRaises(RetentionPolicyError) as raised:
            run_pipe(
                pipe,
                {
                    "metadata": {
                        "case_id": "case-customer-retention-missing",
                        "retention_policy": {
                            "mode": "customer_approved_test",
                            "explicit": False,
                        },
                    },
                    "messages": [
                        {
                            "role": "user",
                            "content": "Gate 1 normalization",
                            "files": [
                                file_ref(
                                    "pipe-file-customer-1",
                                    "customer_approved_test.csv",
                                    "text/csv",
                                    content="symbol,quantity\nSAFE-A,1\n",
                                )
                            ],
                        }
                    ],
                },
            )

        self.assertEqual(raised.exception.code, "retention_policy_missing")

    def test_pipe_sanitizes_source_policy_hints_and_routes_html_to_policy_review(self):
        pipe = self._pipe()
        html = (
            "<html><body><table>"
            "<tr><th>Broker</th><th>Dividend</th></tr>"
            "<tr><td>Safe Broker</td><td>1</td></tr>"
            "</table></body></html>"
        )
        sha256 = hashlib.sha256(html.encode("utf-8")).hexdigest()

        content = run_pipe(
            pipe,
            {
                "metadata": {
                    "case_id": "case-source-policy",
                    "broker_reports_gate1": {
                        "source_policy": {
                            "mode": "customer_approved_private_registry",
                            "explicit": True,
                            "source_registry_role_hints_allowed": True,
                            "pdf_html_source_policy": "review_required",
                            "accept_pdf_html_source_roles": False,
                            "safe_registry_role_hints": [
                                {
                                    "document_id": "safe-doc-001",
                                    "sha256": sha256,
                                    "filename": "should-not-leak.html",
                                    "document_role_candidate": "source_broker_report",
                                    "source_evidence_candidate": "yes",
                                    "source_vs_output": "source_evidence_candidate",
                                }
                            ],
                        }
                    },
                },
                "messages": [
                    {
                        "role": "user",
                        "content": "Gate 1 normalization",
                        "files": [
                            file_ref(
                                "pipe-file-source-policy-1",
                                "source_policy.html",
                                "text/html",
                                content=html,
                            )
                        ],
                    }
                ],
            },
        )

        source_policy = pipe.last_safe_report["input_context"]["source_policy"]
        hint = source_policy["safe_registry_role_hints"][0]
        self.assertEqual(hint["sha256_prefix"], sha256[:12])
        self.assertNotIn("filename", hint)
        self.assertEqual(
            pipe.last_safe_report["source_eligibility_summary"]["source_policy_review"],
            0,
        )
        self.assertEqual(
            pipe.last_safe_report["document_source_eligibility"]["entries"][0]["source_eligibility"],
            "accepted_for_gate2",
        )
        self.assertIn(
            "source_role_policy_uncertainty",
            {
                issue["issue_type"]
                for issue in pipe.last_safe_report["gate1_issue_ledger"]["entries"]
            },
        )
        self.assertNotIn("should-not-leak.html", content)
        self.assertNotIn("pipe-file-source-policy-1", content)
        self.assertNotIn("<table>", content)

    def test_pipe_fails_closed_without_files(self):
        pipe = self._pipe()

        content = run_pipe(
            pipe,
            {
                "messages": [
                    {
                        "role": "user",
                        "content": "Gate 1 normalization PRIVATE NAME",
                    }
                ],
            },
        )

        report = pipe.last_safe_report
        self.assertIsNotNone(report)
        self.assertNotIn("```json", content)
        self.assertIn("Нормализация остановлена.", content)
        self.assertEqual(report["run_status"], "failed_safe")
        self.assertEqual(report["file_ref_visibility"], "not_visible")
        self.assertEqual(report["summary_counts"]["blockers_total"], 1)
        self.assertEqual(report["blockers"][0]["code"], "no_files")
        self.assertEqual(report["recommended_next_step"], "attach_synthetic_files_and_retry")
        self.assertNotIn("PRIVATE NAME", content)

    def test_passport_enabled_without_files_stays_safe_without_model_call(self):
        pipe = self._passport_pipe()

        content = run_pipe(
            pipe,
            {
                "messages": [
                    {
                        "role": "user",
                        "content": "Gate 1 passport without attachments PRIVATE NAME",
                    }
                ],
            },
            __request__=object(),
        )

        report = pipe.last_safe_report
        self.assertIsNotNone(report)
        self.assertEqual(report["run_status"], "failed_safe")
        self.assertEqual(report["blockers"][0]["code"], "no_files")
        self.assertEqual([], pipe.completion_forms)
        self.assertNotIn("PRIVATE NAME", content)

    def test_pipe_can_require_trigger_phrase(self):
        pipe = self._pipe()
        pipe.valves.require_trigger_phrase = True

        content = run_pipe(
            pipe,
            {
                "messages": [
                    {
                        "role": "user",
                        "content": "hello",
                        "files": [
                            file_ref(
                                "pipe-file-csv-1",
                                "synthetic_gate1_operations.csv",
                                "text/csv",
                                content="synthetic_symbol\nSYNTH-A\n",
                            )
                        ],
                    }
                ],
            },
        )

        self.assertIn("Gate 1 normalization is available", content)
        self.assertNotIn("pipe-file-csv-1", content)

    def test_pipe_reports_bytes_unavailable_without_failing(self):
        pipe = self._pipe()
        pipe.valves.allow_upload_path_access = False

        run_pipe(
            pipe,
            {
                "messages": [
                    {
                        "role": "user",
                        "content": "Gate 1 normalization",
                        "files": [
                            file_ref(
                                "pipe-file-csv-1",
                                "synthetic_gate1_operations.csv",
                                "text/csv",
                            )
                        ],
                    }
                ],
            },
        )

        report = pipe.last_safe_report
        self.assertIsNotNone(report)
        self.assertEqual(report["run_status"], "completed_with_blockers")
        self.assertEqual(report["container_counts"], {"csv": 1})
        self.assertEqual(report["blockers_total"], 1)
        self.assertEqual(report["blockers"][0]["code"], "bytes_unavailable")
        self.assertEqual(report["blockers"][0]["reason_code"], "upload_path_access_disabled")
        self.assertEqual(report["documents"][0]["sha256"], None)
        self.assertEqual(report["documents"][0]["read_error_class"], "bytes_unavailable")
        self.assertEqual(report["recommended_next_step"], "verify_pipe_byte_access_boundary")

    def test_pipe_hashes_uploaded_bytes_from_guarded_upload_root(self):
        pipe = self._pipe()
        csv_bytes = b"synthetic_symbol,synthetic_quantity\nSYNTH-A,1\n"
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            pipe.valves.upload_root = str(tmp_path)
            (tmp_path / "pipe-file-csv-1_synthetic_gate1_operations.csv").write_bytes(csv_bytes)

            content = run_pipe(
                pipe,
                {
                    "messages": [
                        {
                            "role": "user",
                            "content": "Gate 1 normalization",
                            "files": [
                                file_ref(
                                    "pipe-file-csv-1",
                                    "synthetic_gate1_operations.csv",
                                    "text/csv",
                                )
                            ],
                        }
                    ],
                },
            )

        report = pipe.last_safe_report
        self.assertIsNotNone(report)
        self.assertEqual(report["run_status"], "completed")
        self.assertEqual(report["documents"][0]["sha256"], hashlib.sha256(csv_bytes).hexdigest())
        self.assertEqual(report["documents"][0]["size_bytes"], len(csv_bytes))
        self.assertNotIn("SYNTH-A,1", content)
        self.assertNotIn("synthetic_gate1_operations.csv", content)

    def test_pipe_detects_duplicate_file_bytes(self):
        pipe = self._pipe()
        duplicate = "synthetic duplicate content\nSYNTH-FCY\n"

        content = run_pipe(
            pipe,
            {
                "messages": [
                    {
                        "role": "user",
                        "content": "Gate 1 normalization",
                        "files": [
                            file_ref("pipe-file-1", "first.txt", "text/plain", content=duplicate),
                            file_ref("pipe-file-2", "second.txt", "text/plain", content=duplicate),
                        ],
                    }
                ],
            },
        )

        report = pipe.last_safe_report
        self.assertIsNotNone(report)
        self.assertEqual(report["run_status"], "completed_with_blockers")
        self.assertEqual(report["duplicate_count"], 1)
        self.assertEqual(report["summary_counts"]["duplicate_hashes"], 1)
        self.assertIn("duplicate_review", {blocker["code"] for blocker in report["blockers"]})
        self.assertEqual(report["documents"][1]["duplicate_of_document_id"], report["documents"][0]["document_id"])
        self.assertNotIn("pipe-file-1", content)
        self.assertNotIn("first.txt", content)
        self.assertNotIn(duplicate, content)

    def test_repeated_native_source_scope_reuses_one_terminal_gate1_result(self):
        pipe = self._pipe()
        csv_bytes = b"synthetic_symbol,synthetic_quantity\nSYNTH-IDEM,1\n"

        def request_body() -> dict:
            return {
                "messages": [
                    {
                        "role": "user",
                        "content": "Gate 1 normalization",
                        "files": [
                            file_ref(
                                "pipe-file-idempotent-1",
                                "synthetic_idempotent.csv",
                                "text/csv",
                                content_bytes=csv_bytes,
                            )
                        ],
                    }
                ]
            }

        first_content = run_pipe(
            pipe,
            request_body(),
            __metadata__={"chat_id": "pipe-test-chat"},
        )
        artifact_db = Path(pipe.valves.artifact_store_path)
        workload_db = artifact_db.with_name("workloads.sqlite3")
        with closing(sqlite3.connect(artifact_db)) as conn:
            first_artifact_count = conn.execute(
                "SELECT COUNT(*) FROM artifact_records"
            ).fetchone()[0]

        replay_content = run_pipe(
            pipe,
            request_body(),
            __metadata__={
                "chat_id": "pipe-test-chat",
                "model_id": "broker_reports_gate1_pipe",
            },
        )

        self.assertTrue(first_content)
        self.assertIn("available for questions", replay_content)
        self.assertTrue(pipe.last_workload_snapshot["idempotency_reused"])
        self.assertEqual(pipe.last_workload_snapshot["state"], "completed")
        with closing(sqlite3.connect(artifact_db)) as conn:
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM artifact_records").fetchone()[0],
                first_artifact_count,
            )
            self.assertEqual(
                conn.execute(
                    "SELECT COUNT(*) FROM artifact_records "
                    "WHERE artifact_type = 'domain_context_packet_v0'"
                ).fetchone()[0],
                1,
            )
        with closing(sqlite3.connect(workload_db)) as conn:
            conn.row_factory = sqlite3.Row
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM workload_jobs").fetchone()[0],
                1,
            )
            self.assertEqual(
                conn.execute(
                    "SELECT workspace_model_id FROM workload_jobs"
                ).fetchone()["workspace_model_id"],
                "broker_reports_gate1_pipe",
            )
            self.assertEqual(
                conn.execute(
                    "SELECT COUNT(*) FROM workload_jobs WHERE state = 'completed'"
                ).fetchone()[0],
                1,
            )
            self.assertEqual(
                conn.execute(
                    "SELECT COUNT(*) FROM workload_transitions "
                    "WHERE to_state = 'completed'"
                ).fetchone()[0],
                1,
            )

    def test_pipe_marks_unknown_container_with_typed_blocker(self):
        pipe = self._pipe()

        content = run_pipe(
            pipe,
            {
                "messages": [
                    {
                        "role": "user",
                        "content": "Gate 1 normalization",
                        "files": [
                            file_ref(
                                "pipe-file-unknown-1",
                                "synthetic_unknown_payload.bin",
                                "application/octet-stream",
                                content_bytes=b"\x00\x01unknown synthetic bytes",
                            )
                        ],
                    }
                ],
            },
        )

        report = pipe.last_safe_report
        self.assertIsNotNone(report)
        self.assertEqual(report["run_status"], "completed_with_blockers")
        self.assertEqual(report["container_counts"], {"unknown": 1})
        self.assertIn("unsupported_format", {blocker["code"] for blocker in report["blockers"]})
        self.assertNotIn("pipe-file-unknown-1", content)
        self.assertNotIn("synthetic_unknown_payload.bin", content)

    def test_pipe_blocks_upload_path_escape_without_printing_private_path(self):
        pipe = self._pipe()
        with tempfile.TemporaryDirectory() as tmp_dir:
            pipe.valves.upload_root = tmp_dir
            content = run_pipe(
                pipe,
                {
                    "messages": [
                        {
                            "role": "user",
                            "content": "Gate 1 normalization",
                            "files": [
                                file_ref(
                                    "..\\escape-file",
                                    "synthetic_gate1_operations.csv",
                                    "text/csv",
                                )
                            ],
                        }
                    ],
                },
            )

        report = pipe.last_safe_report
        self.assertIsNotNone(report)
        self.assertEqual(report["run_status"], "completed_with_blockers")
        self.assertEqual(report["blockers"][0]["code"], "bytes_unavailable")
        self.assertEqual(report["blockers"][0]["reason_code"], "upload_path_escape_detected")
        self.assertNotIn("escape-file", content)
        self.assertNotIn("synthetic_gate1_operations.csv", content)

    def test_structural_shadow_failure_is_safe_and_visible_to_passport_llm(self):
        pipe = self._passport_pipe()
        pipe.valves.pdf_structural_repair_shadow_enabled = True
        pipe.valves.pdf_semantic_header_shadow_enabled = True

        content = run_pipe(
            pipe,
            {
                "metadata": {"case_id": "case-structural-safe-outcome"},
                "messages": [
                    {
                        "role": "user",
                        "content": "Gate 1 normalization with passport",
                        "files": [
                            file_ref(
                                "pipe-file-structural-1",
                                "private-structural-source.pdf",
                                "application/pdf",
                                content_bytes=_ruled_table_pdf(),
                            )
                        ],
                    }
                ],
            },
            __request__=object(),
        )

        report = pipe.last_safe_report
        self.assertIsNotNone(report)
        shadow = report["pdf_structural_repair_shadow"]
        self.assertTrue(shadow["enabled"])
        self.assertFalse(shadow["production_gate2_selection_changed"])
        self.assertTrue(shadow["summary"]["semantic_header_shadow_enabled"])
        self.assertEqual(
            {"not_projected_structural_terminal": 1},
            shadow["summary"]["semantic_projection_status_counts"],
        )
        self.assertEqual(
            [],
            pipe.last_artifact_manifest["pdf_structural_repair_shadow"][
                "semantic_projection_refs"
            ],
        )
        self.assertEqual(
            {
                "enabled": True,
                "artifact_refs": [],
                "status_counts": {"not_projected_structural_terminal": 1},
                "reason_counts": {
                    "pdf_semantic_header_not_projected_structural_terminal": 1
                },
                "private_projections_persisted": 0,
                "private_diagnostics_persisted": 0,
                "authority_state": "non_authoritative",
                "production_gate2_selection_changed": False,
            },
            pipe.last_artifact_manifest["pdf_semantic_header_shadow"],
        )
        structural_outcome = shadow["summary"]["file_processing_outcomes"][
            "outcomes"
        ][0]
        self.assertEqual(structural_outcome["status"], "failed")
        self.assertEqual(
            structural_outcome["reason_code"],
            "provider_temporarily_unavailable",
        )
        first_llm_input = json.loads(
            pipe.completion_forms[0]["messages"][0]["content"]
        )
        self.assertEqual(
            first_llm_input["structural_repair_outcome"],
            structural_outcome,
        )
        self.assertTrue(
            pipe.last_artifact_manifest["pdf_structural_repair_shadow"][
                "private_diagnostic_refs"
            ]
        )
        rendered = json.dumps(report, ensure_ascii=False)
        self.assertNotIn("private-structural-source.pdf", rendered)
        self.assertNotIn("provider_payload", rendered)
        self.assertNotIn("exception_message", rendered)
        self.assertNotIn("private-structural-source.pdf", content)

    def test_structural_shadow_runtime_exception_returns_safe_failed_outcome(self):
        pipe = self._passport_pipe()
        pipe.valves.pdf_structural_repair_shadow_enabled = True

        with patch(
            "openwebui_actions.broker_reports_gate1_pipe."
            "PdfStructuralRepairShadowFactory.create",
            side_effect=RuntimeError("private runtime failure detail"),
        ):
            content = run_pipe(
                pipe,
                {
                    "metadata": {"case_id": "case-structural-runtime-exception"},
                    "messages": [
                        {
                            "role": "user",
                            "content": "Gate 1 normalization with passport",
                            "files": [
                                file_ref(
                                    "pipe-file-structural-exception-1",
                                    "private-structural-exception.pdf",
                                    "application/pdf",
                                    content_bytes=_ruled_table_pdf(),
                                )
                            ],
                        }
                    ],
                },
                __request__=object(),
            )

        report = pipe.last_safe_report
        self.assertIsNotNone(report)
        outcome = report["pdf_structural_repair_shadow"]["summary"][
            "file_processing_outcomes"
        ]["outcomes"][0]
        self.assertEqual(outcome["status"], "failed")
        self.assertEqual(outcome["reason_code"], "internal_processing_failed")
        self.assertEqual(outcome["stage"], "processing")
        first_llm_input = json.loads(
            pipe.completion_forms[0]["messages"][0]["content"]
        )
        self.assertEqual(first_llm_input["structural_repair_outcome"], outcome)
        rendered = json.dumps(report, ensure_ascii=False)
        self.assertNotIn("private runtime failure detail", rendered)
        self.assertNotIn("private-structural-exception.pdf", rendered)
        self.assertNotIn("private runtime failure detail", content)
        self.assertNotIn("private-structural-exception.pdf", content)


if __name__ == "__main__":
    unittest.main()
