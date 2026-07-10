from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT))

from broker_reports_gate1 import (
    ArtifactAccessContext,
    ArtifactStoreConfig,
    ArtifactStoreFactory,
    FileInput,
    Gate1Normalizer,
    ManagedPrompt,
    build_retention_policy,
    persist_gate1_result,
    render_chat_content,
)
from broker_reports_gate1.document_passport import (
    DocumentPassportPromptConfig,
    DocumentPassportPromptResolverFactory,
    FACTORY_REQUIRED,
    FORBIDDEN,
    PromptUserContext,
    apply_document_passport_stage,
    build_llm_document_packages,
    document_metadata_passport_json_schema,
    document_metadata_passport_schema_hash,
    model_call_audit_metadata,
    passport_json_schema_response_format,
    prompt_hash,
    validate_document_metadata_passport,
)


FIXTURES = REPO / "docs" / "stage2" / "testdata" / "broker_reports_gate1_normalization"


def fixture_bytes(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


class BrokerReportsGate1DocumentPassportTest(unittest.TestCase):
    def test_prompt_resolver_factory_anchor_is_explicit(self):
        self.assertIn("DocumentPassportPromptResolverFactory.create", FACTORY_REQUIRED)
        self.assertIn("must not read OpenWebUI prompt tables directly", FORBIDDEN)

    def test_openwebui_sqlite_prompt_resolver_enforces_contract_and_hash(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "webui.db"
            self._create_prompt_db(db_path)

            prompt = DocumentPassportPromptResolverFactory(
                DocumentPassportPromptConfig(
                    db_path=db_path,
                    command="broker_gate1_document_passport",
                )
            ).create().resolve(PromptUserContext(user_id="user-1"))

        self.assertEqual(prompt.prompt_ref, "prompt-passport-1")
        self.assertEqual(prompt.command, "broker_gate1_document_passport")
        self.assertEqual(prompt.version, "passport-v1")
        self.assertEqual(prompt.template_id, "broker_reports.document_metadata_passport.v0")
        self.assertEqual(prompt.output_schema_version, "document_metadata_passport_v0")
        self.assertEqual(
            prompt.hash,
            prompt_hash(
                "Managed prompt body v1",
                "broker_reports_document_metadata_passport_prompt_v0",
                "document_metadata_passport_v0",
            ),
        )

    def test_machine_schema_hash_and_response_format_are_explicit(self):
        schema = document_metadata_passport_json_schema()
        response_format = passport_json_schema_response_format()

        self.assertEqual(schema["type"], "object")
        self.assertFalse(schema["additionalProperties"])
        self.assertIn("schema_version", schema["required"])
        self.assertIn("document_id", schema["required"])
        self.assertEqual(response_format["type"], "json_schema")
        self.assertTrue(response_format["json_schema"]["strict"])
        self.assertEqual(response_format["json_schema"]["schema"], schema)
        self.assertEqual(document_metadata_passport_schema_hash(), document_metadata_passport_schema_hash())
        self.assertEqual(len(document_metadata_passport_schema_hash()), 64)

    def test_passport_validator_rejects_raw_rows_and_unknown_refs(self):
        base = self._normalize_unknown_text()
        prompt = self._prompt()
        llm_package = build_llm_document_packages(
            package=base.package,
            prompt=prompt,
            model_id="passport-model",
        )[0]
        passport = self._valid_passport(llm_package, prompt)
        passport["raw_rows"] = [["private"]]
        passport["evidence_refs"] = ["missing-ref"]

        validation = validate_document_metadata_passport(
            passport=passport,
            document_package=llm_package,
            prompt=prompt,
            model_id="passport-model",
        )

        self.assertEqual(validation["validator_status"], "failed")
        self.assertIn("passport_unknown_field", validation["error_codes"])
        self.assertIn("passport_unknown_evidence_ref", validation["error_codes"])
        self.assertIn("passport_forbidden_field", validation["error_codes"])

    def test_valid_passport_can_promote_unknown_text_source_candidate_without_chat_leak(self):
        base = self._normalize_unknown_text()
        prompt = self._prompt()
        llm_package = build_llm_document_packages(
            package=base.package,
            prompt=prompt,
            model_id="passport-model",
            case_group_id="case_group_synthetic_passport",
        )[0]
        raw_outputs = [
            {
                "schema_version": "llm_passport_raw_output_v0",
                "document_id": llm_package["document_id"],
                "normalization_run_id": llm_package["normalization_run_id"],
                "llm_input_package_id": llm_package["llm_input_package_id"],
                "model_call_status": "passed",
                "raw_output": json.dumps(self._valid_passport(llm_package, prompt), ensure_ascii=False),
                "error_code": None,
            }
        ]

        applied = apply_document_passport_stage(
            package=base.package,
            prompt=prompt,
            model_id="passport-model",
            llm_packages=[llm_package],
            raw_outputs=raw_outputs,
            private_markers=base.private_markers,
        )
        report = applied["safe_report"]
        content = render_chat_content(report)
        eligibility = report["document_source_eligibility"]["entries"][0]

        self.assertEqual(report["validation_result"]["status"], "passed")
        self.assertEqual(eligibility["source_eligibility"], "accepted_as_source_candidate_for_gate2")
        self.assertTrue(eligibility["included_in_reduced_subset"])
        self.assertEqual(report["document_metadata_passport_summary"]["validated"], 1)
        self.assertIn("LLM паспорта документов: 1 проверено, 0 заблокировано", content)
        self.assertNotIn("document_metadata_passports", content)
        self.assertNotIn("private account", content.lower())
        self.assertNotIn("Just a synthetic note", content)

    def test_html_source_policy_uncertainty_uses_passport_and_carries_issue_context(self):
        base = Gate1Normalizer().normalize(
            [
                FileInput.from_bytes(
                    private_ref="html-passport",
                    filename="synthetic_broker_report.html",
                    content=fixture_bytes("synthetic_broker_report.html"),
                    mime_type="text/html",
                )
            ],
            input_context={
                "source_policy": {
                    "mode": "customer_approved_private_registry",
                    "explicit": True,
                    "source_registry_role_hints_allowed": True,
                    "pdf_html_source_policy": "review_required",
                    "accept_pdf_html_source_roles": False,
                }
            },
        )
        prompt = self._prompt()
        llm_package = build_llm_document_packages(
            package=base.package,
            prompt=prompt,
            model_id="passport-model",
        )[0]
        applied = apply_document_passport_stage(
            package=base.package,
            prompt=prompt,
            model_id="passport-model",
            llm_packages=[llm_package],
            raw_outputs=[
                {
                    "schema_version": "llm_passport_raw_output_v0",
                    "document_id": llm_package["document_id"],
                    "normalization_run_id": llm_package["normalization_run_id"],
                    "llm_input_package_id": llm_package["llm_input_package_id"],
                    "model_call_status": "passed",
                    "raw_output": self._valid_passport(llm_package, prompt),
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
            ],
            private_markers=base.private_markers,
        )

        eligibility = applied["safe_report"]["document_source_eligibility"]["entries"][0]
        self.assertEqual(eligibility["source_eligibility"], "accepted_for_gate2")
        self.assertTrue(eligibility["included_in_reduced_subset"])
        self.assertIn("document_metadata_passport_source_role_supported", eligibility["reason_codes"])
        self.assertIn("source_policy_uncertainty_carried_forward", eligibility["reason_codes"])
        self.assertEqual(applied["safe_report"]["source_eligibility_summary"]["source_policy_review"], 0)
        self.assertIn(
            "source_role_policy_uncertainty",
            {
                issue["issue_type"]
                for issue in applied["safe_report"]["gate1_issue_ledger"]["entries"]
            },
        )

    def test_validator_guided_repair_declares_missing_metadata_without_accepting_document(self):
        base = self._normalize_unknown_text()
        prompt = self._prompt()
        llm_package = build_llm_document_packages(
            package=base.package,
            prompt=prompt,
            model_id="passport-model",
        )[0]
        passport = self._valid_passport(llm_package, prompt)
        passport["broker_name_candidate"] = None
        passport["missing_metadata_fields"] = []
        passport["review_required"] = False

        applied = apply_document_passport_stage(
            package=base.package,
            prompt=prompt,
            model_id="passport-model",
            llm_packages=[llm_package],
            raw_outputs=[
                {
                    "schema_version": "llm_passport_raw_output_v0",
                    "document_id": llm_package["document_id"],
                    "normalization_run_id": llm_package["normalization_run_id"],
                    "llm_input_package_id": llm_package["llm_input_package_id"],
                    "model_call_status": "passed",
                    "raw_output": passport,
                    "error_code": None,
                }
            ],
            private_markers=base.private_markers,
        )

        repaired_passport = applied["package"]["document_metadata_passports"][0]
        eligibility = applied["safe_report"]["document_source_eligibility"]["entries"][0]
        self.assertEqual(applied["safe_report"]["document_metadata_passport_summary"]["validated"], 1)
        self.assertEqual(applied["package"]["document_metadata_passport_validation"]["validator_guided_repair_count"], 1)
        self.assertIn("broker_name_candidate", repaired_passport["missing_metadata_fields"])
        self.assertTrue(repaired_passport["review_required"])
        self.assertEqual(eligibility["source_eligibility"], "metadata_review_required")
        self.assertFalse(eligibility["included_in_reduced_subset"])

    def test_artifactstore_persists_passport_artifacts_with_expected_visibility(self):
        base = self._normalize_unknown_text()
        prompt = self._prompt()
        llm_package = build_llm_document_packages(
            package=base.package,
            prompt=prompt,
            model_id="passport-model",
        )[0]
        applied = apply_document_passport_stage(
            package=base.package,
            prompt=prompt,
            model_id="passport-model",
            llm_packages=[llm_package],
            raw_outputs=[
                {
                    "schema_version": "llm_passport_raw_output_v0",
                    "document_id": llm_package["document_id"],
                    "normalization_run_id": llm_package["normalization_run_id"],
                    "llm_input_package_id": llm_package["llm_input_package_id"],
                    "model_call_status": "passed",
                    "raw_output": self._valid_passport(llm_package, prompt),
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
            ],
            private_markers=base.private_markers,
        )
        result = type(base)(package=applied["package"], safe_report=applied["safe_report"], private_markers=base.private_markers)
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
                user_id="user-passport",
                case_id="case-passport",
                chat_id="chat-passport",
                workspace_model_id="broker_reports_gate1_pipe",
                normalization_run_id=result.package["normalization_run"]["run_id"],
                allow_private=True,
            )
            manifest = persist_gate1_result(
                store=store,
                result=result,
                context=context,
                retention_policy=build_retention_policy(mode="api_smoke"),
            )
            records = store.list_by_run(context.normalization_run_id)

        by_type = {record.artifact_type: record for record in records}
        self.assertIn("llm_prompt_snapshot_v0", by_type)
        self.assertIn("llm_document_package_v0", by_type)
        self.assertIn("llm_passport_raw_output_v0", by_type)
        self.assertIn("document_metadata_passport_v0", by_type)
        self.assertIn("document_metadata_passport_validation_v0", by_type)
        self.assertEqual(by_type["llm_document_package_v0"].visibility, "private_case")
        self.assertEqual(by_type["llm_document_package_v0"].storage_backend, "project_artifact_payload")
        self.assertEqual(by_type["llm_passport_raw_output_v0"].visibility, "private_case")
        self.assertEqual(by_type["document_metadata_passport_v0"].visibility, "safe_internal")
        self.assertEqual(
            by_type["llm_document_package_v0"].safe_metadata["output_schema_hash"],
            document_metadata_passport_schema_hash(),
        )
        self.assertEqual(
            by_type["llm_passport_raw_output_v0"].safe_metadata["structured_output_mode"],
            "openwebui_response_format_json_schema",
        )
        self.assertEqual(
            by_type["llm_passport_raw_output_v0"].safe_metadata["output_schema_hash"],
            document_metadata_passport_schema_hash(),
        )
        self.assertEqual(
            by_type["document_metadata_passport_validation_v0"].safe_metadata["structured_output_mode_counts"],
            {"openwebui_response_format_json_schema": 1},
        )
        self.assertEqual(
            by_type["document_metadata_passport_validation_v0"].safe_metadata["output_schema_hash"],
            document_metadata_passport_schema_hash(),
        )
        self.assertIn("document_metadata_passport_v0", manifest.artifact_refs_by_type)
        self.assertIn("llm_document_package_v0", manifest.artifact_refs_by_type)

    def _normalize_unknown_text(self):
        return Gate1Normalizer().normalize(
            [
                FileInput.from_bytes(
                    private_ref="passport-unknown-text",
                    filename="synthetic_note.txt",
                    content=b"Just a synthetic note without document role signals.",
                    mime_type="text/plain",
                )
            ],
            input_context={"test_case": "document_metadata_passport"},
        )

    def _prompt(self) -> ManagedPrompt:
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

    def _valid_passport(self, llm_package: dict, prompt: ManagedPrompt) -> dict:
        evidence_refs = [str(llm_package["evidence_refs"][0]), str(llm_package["llm_input_package_id"])]
        return {
            "schema_version": "document_metadata_passport_v0",
            "passport_id": "passport_test",
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
            "created_at": "2026-07-08T00:00:00Z",
        }

    def _create_prompt_db(self, path: Path) -> None:
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
                CREATE TABLE access_grant(
                    resource_type TEXT,
                    resource_id TEXT,
                    principal_type TEXT,
                    principal_id TEXT,
                    permission TEXT
                )
                """
            )
            conn.execute(
                """
                INSERT INTO prompt(id, command, user_id, name, content, data, meta, tags, is_active, version_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "prompt-passport-1",
                    "broker_gate1_document_passport",
                    "owner-1",
                    "Broker Reports Passport",
                    "Managed prompt body v1",
                    "{}",
                    json.dumps(
                        {
                            "template_kind": "document_metadata_passport",
                            "template_id": "broker_reports.document_metadata_passport.v0",
                            "output_schema_version": "document_metadata_passport_v0",
                        }
                    ),
                    json.dumps(["broker-reports-gate1", "document-metadata-passport"]),
                    1,
                    "passport-v1",
                ),
            )
            conn.execute(
                """
                INSERT INTO access_grant(resource_type, resource_id, principal_type, principal_id, permission)
                VALUES ('prompt', 'prompt-passport-1', 'user', '*', 'read')
                """
            )
            conn.commit()
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
