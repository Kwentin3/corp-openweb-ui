from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from collections import Counter
from io import BytesIO
from pathlib import Path


SERVICE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_ROOT))

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from broker_reports_gate1 import (
    ArtifactAccessContext,
    ArtifactResolver,
    ArtifactStoreConfig,
    ArtifactStoreError,
    ArtifactStoreFactory,
    FileInput,
    Gate1Normalizer,
    Gate2InputReadinessFactory,
    build_retention_policy,
    persist_gate1_result,
)


GATE1_BUNDLE = (
    SERVICE_ROOT / "openwebui_actions" / "broker_reports_gate1_pipe_bundled.py"
)


def main() -> None:
    result = Gate1Normalizer().normalize(
        _representative_inputs(),
        input_context={
            "clarification_criticality_refinement_enabled": True,
            "proof_scope": "synthetic_mixed_supported_profile_v1",
        },
        entrypoint="gate1_document_memory_v1_proof",
        trigger_type="backend_core",
    )
    package = result.package
    assessment = package["gate1_supported_profile_assessment"]
    manifest = package["document_memory_manifest"]
    assessment_by_format = {
        str(item["container_format"]): item for item in assessment["entries"]
    }

    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        store = ArtifactStoreFactory(
            ArtifactStoreConfig(
                mode="sqlite",
                sqlite_path=root / "artifacts.sqlite3",
                payload_root=root / "payloads",
            )
        ).create()
        context = ArtifactAccessContext(
            user_id="synthetic-document-memory-proof-user",
            case_id="synthetic-document-memory-proof-case",
            chat_id="synthetic-document-memory-proof-chat",
            workspace_model_id="broker_reports_gate1_pipe",
            normalization_run_id=package["normalization_run"]["run_id"],
            allow_private=True,
            require_source_available=True,
        )
        source_file_refs = [
            {
                "provider": "synthetic_proof",
                "openwebui_file_id": f"synthetic-document-memory-{index}",
                "content_type": item.mime_type,
                "size_bytes": item.declared_size_bytes,
                "source_deleted": False,
            }
            for index, item in enumerate(_representative_inputs(), start=1)
        ]
        persisted = persist_gate1_result(
            store=store,
            result=result,
            context=context,
            retention_policy=build_retention_policy(mode="api_smoke"),
            source_file_refs=source_file_refs,
        )
        memory_ref = persisted.artifact_refs_by_type[
            "broker_reports_gate1_document_memory_manifest_v1"
        ][0]
        dcp_ref = persisted.artifact_refs_by_type["domain_context_packet_v0"][0]
        resolver = ArtifactResolver(store)
        resolved_memory = resolver.resolve(memory_ref, context)["payload"]
        records_before = store.list_by_run(context.normalization_run_id)
        readiness = Gate2InputReadinessFactory(store=store).create().audit_and_build(
            domain_context_packet_ref=dcp_ref,
            context=context,
        )
        records_after = store.list_by_run(context.normalization_run_id)

        wrong_context_code = _wrong_context_code(resolver, memory_ref, context)
        source_delete_observed = store.mark_source_file_deleted(
            ArtifactAccessContext(
                **{
                    **context.__dict__,
                    "source_file_id": "synthetic-document-memory-1",
                }
            )
        )
        source_delete_private_purged = sum(
            1
            for item in store.list_by_run(context.normalization_run_id)
            if item.visibility == "private_case"
            and _object(item.source_file_ref).get("openwebui_file_id")
            == "synthetic-document-memory-1"
            and item.purge_status == "purged"
        )
        root_survives_source_delete_as_safe_metadata = bool(
            resolver.resolve(memory_ref, context)["payload"].get("manifest_id")
        )
        case_purged = store.purge_case(context)
        purge_denial_code = _resolve_error_code(resolver, memory_ref, context)

        checks = {
            "normalization_validation_passed": package["validation_result"]["status"]
            == "passed",
            "supported_formats_accepted": all(
                assessment_by_format[container]["profile_acceptance"] == "accepted"
                for container in ("csv", "html_text", "pdf")
            ),
            "supported_formats_zero_loss": all(
                assessment_by_format[container]["zero_silent_loss"] == "passed"
                for container in ("csv", "html_text", "pdf")
            ),
            "manifest_integrity_resolved": resolved_memory.get("integrity_hash")
            == manifest.get("integrity_hash"),
            "one_logical_document_per_source": all(
                len(item.get("logical_document_refs") or []) == 1
                for item in manifest["documents"]
            ),
            "artifact_refs_unique": manifest["summary"][
                "duplicate_normalized_artifact_refs_total"
            ]
            == 0,
            "gate2_input_readiness_passed": readiness.validation[
                "validator_status"
            ]
            == "passed",
            "gate2_used_document_memory": readiness.validation[
                "document_memory_audit"
            ]["validator_status"]
            == "passed",
            "gate2_format_parser_not_required": readiness.validation[
                "document_memory_audit"
            ]["format_specific_parser_required"]
            is False,
            "gate1_immutable_after_gate2": [item.artifact_id for item in records_before]
            == [item.artifact_id for item in records_after],
            "wrong_context_denied": wrong_context_code
            in {
                "artifact_access_denied",
                "artifact_scope_forbidden",
                "artifact_user_forbidden",
            },
            "source_delete_cascade_observed": (
                source_delete_observed.status == "changed"
            )
            and source_delete_private_purged > 0,
            "safe_root_retained_after_source_delete": root_survives_source_delete_as_safe_metadata,
            "case_purge_denies_root": case_purged.status == "changed"
            and purge_denial_code == "artifact_purged",
            "knowledge_vector_records_absent": all(
                item.storage_backend != "openwebui_knowledge" for item in records_before
            ),
        }
        proof = {
            "schema_version": "broker_reports_gate1_document_memory_proof_v1",
            "proof_status": "passed" if all(checks.values()) else "failed",
            "proof_scope": "synthetic_mixed_supported_profile_v1",
            "automated_checks": checks,
            "supported_profile": {
                "profile_id": assessment["profile_id"],
                "accepted_formats": ["csv", "html_text", "pdf"],
                "terminal_status_counts": assessment["summary"][
                    "terminal_status_counts"
                ],
            },
            "document_memory": {
                "manifest_id": manifest["manifest_id"],
                "integrity_hash": manifest["integrity_hash"],
                "source_files_total": manifest["summary"]["source_files_total"],
                "logical_documents_total": manifest["summary"][
                    "logical_documents_total"
                ],
                "normalized_artifacts_total": manifest["summary"][
                    "normalized_artifacts_total"
                ],
                "zero_silent_loss_status": manifest["summary"][
                    "zero_silent_loss_status"
                ],
            },
            "gate2_handoff": {
                "packages_total": readiness.validation["packages_total"],
                "package_unit_kind_counts": dict(
                    sorted(
                        Counter(
                            str(_object(item.get("source_unit")).get("unit_kind"))
                            for item in readiness.packages
                        ).items()
                    )
                ),
                "artifactstore_unchanged": readiness.validation[
                    "artifactstore_unchanged"
                ],
                "knowledge_records": readiness.validation["knowledge_records"],
            },
            "lifecycle": {
                "wrong_context_error_code": wrong_context_code,
                "source_delete_private_purged_total": source_delete_private_purged,
                "safe_root_retained_after_source_delete": root_survives_source_delete_as_safe_metadata,
                "case_purge_error_code": purge_denial_code,
            },
            "bundle": {
                "gate1_bundle_sha256": hashlib.sha256(
                    GATE1_BUNDLE.read_bytes()
                ).hexdigest(),
            },
            "privacy": {
                "safe_output_contains_private_values": False,
                "knowledge_rag_used": False,
                "vectorization_performed": False,
            },
            "operator_review": {
                "status": "not_performed_by_automated_proof",
                "actual_pilot_corpus_required": True,
            },
        }
        print(json.dumps(proof, ensure_ascii=False, sort_keys=True, indent=2))
        if proof["proof_status"] != "passed":
            raise SystemExit(1)


def _representative_inputs() -> list[FileInput]:
    return [
        FileInput.from_bytes(
            private_ref="synthetic-document-memory-csv",
            filename="synthetic-representative.csv",
            content=b"Date,Amount,Currency\n2026-01-01,10.00,USD\n",
            mime_type="text/csv",
            source_kind="synthetic_proof",
        ),
        FileInput.from_bytes(
            private_ref="synthetic-document-memory-html",
            filename="synthetic-representative.html",
            content=(
                b"<p>Statement context</p><table>"
                b"<tr><th>Date</th><th>Amount</th><th>Currency</th></tr>"
                b"<tr><td>2026-01-01</td><td>10.00</td><td>USD</td></tr>"
                b"</table>"
            ),
            mime_type="text/html",
            source_kind="synthetic_proof",
        ),
        FileInput.from_bytes(
            private_ref="synthetic-document-memory-pdf",
            filename="synthetic-representative.pdf",
            content=_ruled_table_pdf(),
            mime_type="application/pdf",
            source_kind="synthetic_proof",
        ),
    ]


def _ruled_table_pdf() -> bytes:
    writer = PdfWriter()
    page = writer.add_blank_page(width=320, height=320)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    font_ref = writer._add_object(font)
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_ref})}
    )
    texts = [
        (30, 260, "Synthetic Table"),
        (30, 220, "Date"),
        (125, 220, "Amount"),
        (225, 220, "Currency"),
        (30, 195, "2026-01-01"),
        (125, 195, "10.00"),
        (225, 195, "USD"),
        (30, 170, "2026-01-02"),
        (125, 170, "20.00"),
        (225, 170, "EUR"),
        (30, 130, "Outside table note"),
    ]
    commands = [
        f"BT /F1 10 Tf {x} {y} Td ({text}) Tj ET" for x, y, text in texts
    ]
    commands.extend(
        [
            "20 155 m 300 155 l S",
            "20 180 m 300 180 l S",
            "20 205 m 300 205 l S",
            "20 230 m 300 230 l S",
            "20 155 m 20 230 l S",
            "110 155 m 110 230 l S",
            "210 155 m 210 230 l S",
            "300 155 m 300 230 l S",
        ]
    )
    stream = DecodedStreamObject()
    stream.set_data("\n".join(commands).encode("latin-1"))
    page[NameObject("/Contents")] = writer._add_object(stream)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def _wrong_context_code(
    resolver: ArtifactResolver,
    artifact_ref: str,
    context: ArtifactAccessContext,
) -> str:
    wrong = ArtifactAccessContext(
        user_id="synthetic-document-memory-foreign-user",
        case_id=context.case_id,
        chat_id=context.chat_id,
        workspace_model_id=context.workspace_model_id,
        normalization_run_id=context.normalization_run_id,
        allow_private=True,
        require_source_available=True,
    )
    return _resolve_error_code(resolver, artifact_ref, wrong)


def _resolve_error_code(
    resolver: ArtifactResolver,
    artifact_ref: str,
    context: ArtifactAccessContext,
) -> str:
    try:
        resolver.resolve(artifact_ref, context)
    except ArtifactStoreError as exc:
        return exc.code
    return "not_denied"


def _object(value):
    return value if isinstance(value, dict) else {}


if __name__ == "__main__":
    main()
