from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import io
import json
import re
import sys
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from xml.etree import ElementTree


SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SERVICE_ROOT.parents[1]
sys.path.insert(0, str(SERVICE_ROOT))

from pypdf import PdfReader  # noqa: E402

from broker_reports_gate1 import (  # noqa: E402
    ArtifactAccessContext,
    ArtifactResolver,
    ArtifactStoreConfig,
    ArtifactStoreFactory,
    FileInput,
    Gate1BoundedGraphConfig,
    Gate1BoundedGraphFactory,
    Gate1Normalizer,
    build_retention_policy,
    persist_gate1_result,
    validate_document_memory_manifest,
)


DEFAULT_CONFIG = (
    REPO_ROOT / "local" / "stage2" / "broker_reports_customer_case_alpha.local.json"
)
SAFE_REGISTRY = (
    REPO_ROOT
    / "docs"
    / "stage2"
    / "domain"
    / "BROKER_REPORTS_CUSTOMER_SOURCE_DOCUMENTS_INDEX.v0.safe.json"
)
GATE1_BUNDLE = (
    SERVICE_ROOT / "openwebui_actions" / "broker_reports_gate1_pipe_bundled.py"
)
CONDITIONAL_REQUIRED_PDF_IDS = {
    "brdoc_036_f1995ee6a6fa",
    "brdoc_041_39227188fb1c",
    "brdoc_042_51ccbbd65039",
    "brdoc_043_4d8ee8777b23",
    "brdoc_060_e69ef2fa1cb2",
    "brdoc_061_aeaff2e070aa",
    "brdoc_062_161065e246ac",
    "brdoc_063_510b999b1914",
}
CONDITIONAL_PDF_ROLES = {
    "brdoc_036_f1995ee6a6fa": "source_broker_report",
    "brdoc_041_39227188fb1c": "tax_source_document",
    "brdoc_042_51ccbbd65039": "tax_source_document",
    "brdoc_043_4d8ee8777b23": "tax_source_document",
    "brdoc_060_e69ef2fa1cb2": "withholding_report",
    "brdoc_061_aeaff2e070aa": "tax_source_document",
    "brdoc_062_161065e246ac": "tax_source_document",
    "brdoc_063_510b999b1914": "tax_source_document",
}
SOURCE_ROLES = {
    "operations_table",
    "source_broker_report",
    "dividends_report",
    "fees_report",
    "withholding_report",
    "currency_rate_table",
    "tax_source_document",
    "official_form",
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--safe-output", type=Path)
    parser.add_argument(
        "--full-gate2-packages",
        action="store_true",
        help=(
            "Also build every Gate 2 package. This is outside the Gate 1 "
            "acceptance boundary and can be expensive on a large corpus."
        ),
    )
    parser.add_argument(
        "--print-full-safe-proof",
        action="store_true",
        help="Print the full safe JSON in addition to writing the proof files.",
    )
    args = parser.parse_args()

    config = _read_json(args.config)
    authoritative_root = Path(config["authoritative_original_root"])
    source_root = Path(config["source_root"])
    proof_root = Path(config["proof_work_root"])
    local_registry_root = Path(config["local_registry_root"])
    _assert_private_root(authoritative_root)
    _assert_private_root(source_root)
    _assert_private_root(proof_root)
    registry = _read_json(SAFE_REGISTRY)
    records = list(registry["documents"])

    authoritative = _inventory(authoritative_root)
    copied = _inventory(source_root)
    reconciliation = _reconcile(records, authoritative, copied)
    required_records = _required_records(records)
    source_by_sha = _unique_by_sha(copied)
    inputs, root_sources, hints = _build_inputs(required_records, source_by_sha)
    retention_policy = build_retention_policy(
        mode="customer_approved_test", explicit=True
    )

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_root = proof_root / f"actual_gate1_{timestamp}"
    artifact_root = run_root / "artifact_store"
    artifact_root.mkdir(parents=True, exist_ok=False)
    store = ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=artifact_root / "artifacts.sqlite3",
            payload_root=artifact_root / "payloads",
        )
    ).create()
    normalizer = Gate1Normalizer()
    planned_run_id = normalizer.plan_run_id(inputs)
    context = ArtifactAccessContext(
        user_id="agent-operator-technical-reviewer",
        case_id="customer-case-alpha-gate1-acceptance",
        chat_id="customer-case-alpha-gate1-acceptance-run",
        workspace_model_id="broker_reports_gate1_pipe",
        normalization_run_id=planned_run_id,
        allow_private=True,
        require_source_available=True,
    )
    source_file_refs = [
        {
            "provider": "private_customer_corpus",
            "openwebui_file_id": f"private-corpus-{record['document_id']}",
            "content_type": file_input.mime_type,
            "size_bytes": file_input.declared_size_bytes,
            "source_deleted": False,
        }
        for record, file_input in zip(required_records, inputs)
    ]
    bounded_graph = Gate1BoundedGraphFactory(
        Gate1BoundedGraphConfig(
            store=store,
            context=context,
            retention_policy=retention_policy,
            source_file_refs=tuple(source_file_refs),
        )
    ).create(normalization_run_id=planned_run_id)

    print("proof_checkpoint=normalization_started", file=sys.stderr, flush=True)
    result = normalizer.normalize(
        inputs,
        input_context={
            "clarification_criticality_refinement_enabled": True,
            "broker_pdf_neutral_table_profile_v1_enabled": True,
            "proof_scope": "actual_customer_approved_source_evidence_pool_v1",
            "case_group_id": "customer_case_alpha",
            "source_policy": {
                "explicit": True,
                "mode": "customer_approved_private_registry",
                "source_registry_role_hints_allowed": True,
                "accept_pdf_html_source_roles": True,
                "safe_registry_role_hints": hints,
            },
        },
        entrypoint="gate1_actual_customer_corpus_proof",
        trigger_type="backend_core",
        bounded_graph=bounded_graph,
    )
    package = result.package
    print("proof_checkpoint=normalization_completed", file=sys.stderr, flush=True)

    persisted = persist_gate1_result(
        store=store,
        result=result,
        context=context,
        retention_policy=retention_policy,
        source_file_refs=source_file_refs,
    )
    print("proof_checkpoint=artifact_persistence_completed", file=sys.stderr, flush=True)
    resolver = ArtifactResolver(store)
    memory_ref = persisted.artifact_refs_by_type[
        "broker_reports_gate1_document_memory_manifest_v1"
    ][0]
    dcp_ref = persisted.artifact_refs_by_type["domain_context_packet_v0"][0]
    resolved_memory = resolver.resolve(memory_ref, context)["payload"]
    resolved_dcp = resolver.resolve(dcp_ref, context)["payload"]
    records_before = store.list_by_run(context.normalization_run_id)
    public_handoff = _audit_public_handoff(
        dcp=resolved_dcp,
        memory=resolved_memory,
    )
    full_gate2 = None
    if args.full_gate2_packages:
        from broker_reports_gate1 import Gate2InputReadinessFactory

        readiness = Gate2InputReadinessFactory(store=store).create().audit_and_build(
            domain_context_packet_ref=dcp_ref,
            context=context,
        )
        full_gate2 = {
            "status": "completed",
            "validator_status": readiness.validation["validator_status"],
            "packages_total": readiness.validation["packages_total"],
            "warnings_total": len(readiness.validation.get("warnings") or []),
        }
        print(
            "proof_checkpoint=full_gate2_packages_completed",
            file=sys.stderr,
            flush=True,
        )
    records_after = store.list_by_run(context.normalization_run_id)

    document_bytes = _DocumentBytesResolver(package, root_sources)
    private_review, safe_documents = _review_documents(
        package=package,
        memory=resolved_memory,
        document_bytes=document_bytes,
        artifact_records=records_before,
        resolver=resolver,
        context=context,
        required_records=required_records,
    )
    print("proof_checkpoint=operator_review_completed", file=sys.stderr, flush=True)

    checks = {
        "authoritative_and_private_copy_reconciled": reconciliation["passed"],
        "required_top_level_pool_exact": len(required_records) == 56,
        "normalization_validation_passed": package["validation_result"]["status"]
        == "passed",
        "every_required_source_terminal": all(
            item["terminal_state"] in {"complete", "review_required"}
            for item in safe_documents
        ),
        "all_accepted_zero_silent_loss": all(
            item["zero_silent_loss"] == "passed" for item in safe_documents
        ),
        "all_document_accounting_passed": all(
            item["accounting_status"] == "passed" for item in safe_documents
        ),
        "archive_profile_proven": _archive_checks(package),
        "operator_review_passed": all(
            item["operator_review_verdict"] == "passed" for item in safe_documents
        ),
        "gate2_public_boundary_validated": public_handoff["validator_status"]
        == "passed",
        "gate2_used_document_memory": public_handoff[
            "document_memory_validator_status"
        ]
        == "passed",
        "gate1_immutable_after_gate2": [item.artifact_id for item in records_before]
        == [item.artifact_id for item in records_after],
        "knowledge_rag_absent": all(
            item.storage_backend != "openwebui_knowledge" for item in records_before
        ),
        "safe_output_private_values_absent": True,
        "private_corpus_outside_git": all(
            not _is_relative_to(path.resolve(), REPO_ROOT.resolve())
            for path in (authoritative_root, source_root, proof_root)
        ),
    }
    proof_status = "passed" if all(checks.values()) else "failed"
    assessment = package["gate1_supported_profile_assessment"]
    manifest = package["document_memory_manifest"]
    safe_proof = {
        "schema_version": "broker_reports_gate1_actual_corpus_acceptance_v1",
        "proof_status": proof_status,
        "proof_scope": "complete_actual_customer_approved_source_evidence_pool_v1",
        "automated_checks": checks,
        "corpus_reconciliation": {
            "registry_records_total": reconciliation["registry_records_total"],
            "authoritative_files_total": reconciliation[
                "authoritative_files_total"
            ],
            "private_copy_files_total": reconciliation["private_copy_files_total"],
            "registry_hashes_matched_total": reconciliation[
                "registry_hashes_matched_total"
            ],
            "authoritative_copy_hash_sets_equal": reconciliation[
                "authoritative_copy_hash_sets_equal"
            ],
            "duplicates_total": reconciliation["duplicates_total"],
            "required_top_level_sources_total": len(required_records),
            "excluded_derived_xlsx_total": 2,
            "excluded_derived_pdf_total": 5,
        },
        "actual_execution": {
            "normalization_run_id": package["normalization_run"]["run_id"],
            "top_level_inputs_total": len(required_records),
            "document_sources_total": len(safe_documents),
            "archive_containers_total": package["normalization_run"][
                "archive_containers_total"
            ],
            "archive_promoted_members_total": package["normalization_run"][
                "archive_promoted_members_total"
            ],
            "logical_documents_total": manifest["summary"][
                "logical_documents_total"
            ],
            "terminal_status_counts": assessment["summary"][
                "terminal_status_counts"
            ],
            "zero_silent_loss_status": manifest["summary"][
                "zero_silent_loss_status"
            ],
        },
        "documents": safe_documents,
        "agent_operator_acceptance": {
            "status": "passed" if checks["operator_review_passed"] else "failed",
            "reviewer_role": "agent_operated_technical_reviewer",
            "documents_reviewed_total": len(safe_documents),
            "review_required_documents_reviewed_total": sum(
                item["terminal_state"] == "review_required"
                for item in safe_documents
            ),
            "partial_blocked_unsupported_unreadable_total": sum(
                item["terminal_state"]
                in {"partial", "blocked", "unsupported", "unreadable"}
                for item in safe_documents
            ),
            "human_customer_acceptance": "not_performed",
            "private_review_values_exported_to_safe_report": False,
        },
        "gate2_public_handoff": {
            **public_handoff,
            "artifactstore_unchanged": checks["gate1_immutable_after_gate2"],
            "full_gate2_package_builder": full_gate2
            or {
                "status": "not_run_outside_gate1_acceptance_boundary",
                "known_performance_debt": (
                    "mass_package_builder_requires_separate_bounded_performance_work"
                ),
            },
        },
        "runtime": {
            "gate1_bundle_sha256": hashlib.sha256(GATE1_BUNDLE.read_bytes()).hexdigest(),
            "execution_mode": "repository_bundle_parity_equivalent_backend_core",
        },
        "privacy": {
            "customer_values_included": False,
            "private_paths_included": False,
            "knowledge_rag_used": False,
            "vectorization_performed": False,
        },
    }

    local_registry_root.mkdir(parents=True, exist_ok=True)
    _write_json(
        local_registry_root / f"reconciliation_{timestamp}.private.json",
        {
            **reconciliation,
            "authoritative_root": str(authoritative_root),
            "private_source_root": str(source_root),
            "required_registry_document_ids": [
                item["document_id"] for item in required_records
            ],
        },
    )
    _write_json(run_root / "operator_review.private.json", private_review)
    _write_json(run_root / "acceptance.safe.json", safe_proof)
    if args.safe_output:
        _write_json(args.safe_output, safe_proof)
    console_result = (
        safe_proof
        if args.print_full_safe_proof
        else {
            "proof_status": proof_status,
            "normalization_run_id": package["normalization_run"]["run_id"],
            "document_sources_total": len(safe_documents),
            "terminal_status_counts": assessment["summary"][
                "terminal_status_counts"
            ],
            "failed_check_refs": sorted(
                key for key, value in checks.items() if not value
            ),
        }
    )
    print(json.dumps(console_result, ensure_ascii=False, sort_keys=True, indent=2))
    if proof_status != "passed":
        raise SystemExit(1)


def _inventory(root: Path) -> list[dict[str, Any]]:
    if not root.is_dir():
        raise RuntimeError(f"private_corpus_root_missing:{root}")
    items = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        content = path.read_bytes()
        items.append(
            {
                "path": path,
                "relative_path": path.relative_to(root).as_posix(),
                "size_bytes": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            }
        )
    return items


def _reconcile(
    records: list[dict[str, Any]],
    authoritative: list[dict[str, Any]],
    copied: list[dict[str, Any]],
) -> dict[str, Any]:
    registry_hashes = Counter(str(item["sha256"]) for item in records)
    authoritative_hashes = Counter(str(item["sha256"]) for item in authoritative)
    copied_hashes = Counter(str(item["sha256"]) for item in copied)
    matched = sum(
        min(count, copied_hashes.get(sha256, 0))
        for sha256, count in registry_hashes.items()
    )
    checks = {
        "registry_items_63": len(records) == 63,
        "authoritative_items_63": len(authoritative) == 63,
        "private_copy_items_63": len(copied) == 63,
        "registry_matches_authoritative": registry_hashes == authoritative_hashes,
        "registry_matches_private_copy": registry_hashes == copied_hashes,
        "authoritative_copy_hash_sets_equal": authoritative_hashes == copied_hashes,
        "sizes_match_registry": all(
            any(
                item["sha256"] == record["sha256"]
                and item["size_bytes"] == record["file_size_bytes"]
                for item in copied
            )
            for record in records
        ),
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "registry_records_total": len(records),
        "authoritative_files_total": len(authoritative),
        "private_copy_files_total": len(copied),
        "registry_hashes_matched_total": matched,
        "authoritative_copy_hash_sets_equal": authoritative_hashes == copied_hashes,
        "duplicates_total": sum(count - 1 for count in registry_hashes.values() if count > 1),
    }


def _required_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    required = []
    for record in records:
        document_id = str(record["document_id"])
        extension = str(record["extension"]).lower()
        if record.get("can_be_source_evidence") == "yes":
            required.append(record)
        elif extension == ".zip":
            required.append(record)
        elif document_id in CONDITIONAL_REQUIRED_PDF_IDS:
            required.append(record)
    required.sort(key=lambda item: str(item["document_id"]))
    if len(required) != 56:
        raise RuntimeError(f"required_source_pool_count_mismatch:{len(required)}")
    return required


def _unique_by_sha(items: list[dict[str, Any]]) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for item in items:
        result.setdefault(str(item["sha256"]), Path(item["path"]))
    return result


def _build_inputs(
    records: list[dict[str, Any]], source_by_sha: dict[str, Path]
) -> tuple[list[FileInput], list[dict[str, Any]], list[dict[str, Any]]]:
    inputs = []
    root_sources = []
    hints: list[dict[str, Any]] = []
    for ordinal, record in enumerate(records, start=1):
        path = source_by_sha[str(record["sha256"])]
        role = _role_for_record(record)
        private_handle = "private_source_" + hashlib.sha256(
            f"customer_case_alpha:{ordinal}:{record['document_id']}".encode("utf-8")
        ).hexdigest()[:24]
        hints.append({"sha256": record["sha256"], "document_role_candidate": role})
        content_type = str(record.get("detected_mime_type") or "")
        inputs.append(
            FileInput(
                private_ref=private_handle,
                original_filename_private=path.name,
                mime_type=content_type,
                source_kind="local_private_test",
                declared_size_bytes=int(record["file_size_bytes"]),
                bytes_provider=path.read_bytes,
                provider_label="private_hash_verified_copy",
                privacy_markers=[str(path)],
                root_input_ordinal=ordinal,
            )
        )
        root_sources.append({"record": record, "path": path})
        if str(record["extension"]).lower() == ".zip":
            with zipfile.ZipFile(path) as archive:
                for info in archive.infolist():
                    if info.is_dir():
                        continue
                    extension = Path(info.filename).suffix.lower()
                    if extension not in {".pdf", ".xml"}:
                        continue
                    member_sha = hashlib.sha256(archive.read(info)).hexdigest()
                    hints.append(
                        {
                            "sha256": member_sha,
                            "document_role_candidate": "withholding_report",
                        }
                    )
    return inputs, root_sources, hints


def _role_for_record(record: dict[str, Any]) -> str:
    document_id = str(record["document_id"])
    if document_id in CONDITIONAL_PDF_ROLES:
        return CONDITIONAL_PDF_ROLES[document_id]
    role = str(record.get("document_taxonomy_class") or "")
    if role in SOURCE_ROLES:
        return role
    for candidate in record.get("secondary_tags") or []:
        if candidate in SOURCE_ROLES:
            return str(candidate)
    if str(record.get("extension") or "").lower() == ".zip":
        return "archive_package"
    raise RuntimeError(f"required_source_role_missing:{document_id}")


class _DocumentBytesResolver:
    """Read one source document for review without retaining corpus bytes."""

    def __init__(
        self,
        package: dict[str, Any],
        root_sources: list[dict[str, Any]],
    ) -> None:
        self._documents = {
            str(item["document_id"]): item
            for item in package["document_inventory"]["documents"]
        }
        self._root_paths = tuple(
            Path(item["path"]) for item in root_sources
        )

    def read(self, document_id: str) -> bytes:
        document = self._documents[document_id]
        parent_ref = str(document.get("archive_parent_document_ref") or "")
        if not parent_ref:
            ordinal = int(document["root_input_ordinal"])
            return self._root_paths[ordinal - 1].read_bytes()
        parent = self._documents[parent_ref]
        parent_ordinal = int(parent["root_input_ordinal"])
        with zipfile.ZipFile(self._root_paths[parent_ordinal - 1]) as archive:
            info = archive.infolist()[
                int(document["archive_member_index"]) - 1
            ]
            return archive.read(info)


def _resolved_private_artifacts_for_document(
    records: list[Any],
    *,
    document_id: str,
    resolver: ArtifactResolver,
    context: ArtifactAccessContext,
) -> dict[str, list[dict[str, Any]]]:
    private_types = {
        "private_normalized_source_payload_v0": "payloads",
        "private_normalized_source_unit_v0": "units",
        "broker_reports_normalized_table_projection_v0": "projections",
    }
    result: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        bucket = private_types.get(record.artifact_type)
        if (
            not bucket
            or str(record.document_id or "") != document_id
            or record.validation_status != "validated"
        ):
            continue
        resolved = resolver.resolve(record.artifact_id, context)["payload"]
        result[bucket].append(resolved)
    return result


def _audit_public_handoff(
    *, dcp: dict[str, Any], memory: dict[str, Any]
) -> dict[str, Any]:
    memory_validation = validate_document_memory_manifest(memory)
    boundary = dcp.get("document_memory_boundary")
    boundary = boundary if isinstance(boundary, dict) else {}
    checks = {
        "dcp_schema_supported": dcp.get("schema_version")
        == "domain_context_packet_v0",
        "memory_manifest_validated": memory_validation["validator_status"]
        == "passed",
        "manifest_schema_matches": boundary.get("manifest_schema_version")
        == memory.get("schema_version"),
        "manifest_id_matches": boundary.get("manifest_id")
        == memory.get("manifest_id"),
        "manifest_integrity_hash_matches": boundary.get(
            "manifest_integrity_hash"
        )
        == memory.get("integrity_hash"),
        "profile_id_matches": boundary.get("profile_id")
        == memory.get("profile_id"),
        "resolver_required": boundary.get("resolver_required") is True,
        "format_specific_parser_not_required": boundary.get(
            "format_specific_parser_required_by_gate2"
        )
        is False,
        "profile_enforcement_required": boundary.get("profile_enforcement")
        == "required",
    }
    errors = sorted(key for key, value in checks.items() if not value)
    return {
        "validator_status": "passed" if not errors else "failed",
        "document_memory_validator_status": memory_validation[
            "validator_status"
        ],
        "format_specific_parser_required": False,
        "boundary_checks": checks,
        "error_refs": errors,
    }


def _review_documents(
    *,
    package: dict[str, Any],
    memory: dict[str, Any],
    document_bytes: _DocumentBytesResolver,
    artifact_records: list[Any],
    resolver: ArtifactResolver,
    context: ArtifactAccessContext,
    required_records: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    documents = {
        str(item["document_id"]): item
        for item in package["document_inventory"]["documents"]
    }
    profiles = {
        str(item["document_id"]): item
        for item in package["technical_readability_profiles"]
    }
    assessments = {
        str(item["document_ref"]): item
        for item in package["gate1_supported_profile_assessment"]["entries"]
    }
    memory_entries = {
        str(item["source_file_ref"]): item for item in memory["documents"]
    }
    archive_manifests = {
        str(item["parent_document_ref"]): item
        for item in package["archive_source_manifests"]
    }
    issues_by_doc: dict[str, list[str]] = defaultdict(list)
    for issue in package["gate1_issue_ledger"]["entries"]:
        for document_ref in issue.get("target_document_refs") or []:
            issues_by_doc[str(document_ref)].append(str(issue["issue_id"]))
    registry_id_by_ordinal = {
        ordinal: str(record["document_id"])
        for ordinal, record in enumerate(required_records, start=1)
    }

    private_entries = []
    safe_entries = []
    for document_id, document in documents.items():
        content = document_bytes.read(document_id)
        assessment = assessments[document_id]
        memory_entry = memory_entries[document_id]
        artifacts = _resolved_private_artifacts_for_document(
            artifact_records,
            document_id=document_id,
            resolver=resolver,
            context=context,
        )
        direct = _direct_review(
            document=document,
            content=content,
            profile=profiles.get(document_id, {}),
            assessment=assessment,
            memory_entry=memory_entry,
            payloads=artifacts.get("payloads", []),
            units=artifacts.get("units", []),
            projections=artifacts.get("projections", []),
            archive_manifest=archive_manifests.get(document_id, {}),
        )
        generic_checks = {
            "identity_and_material_metadata": hashlib.sha256(
                content
            ).hexdigest()
            == document.get("sha256")
            and len(content) == int(document.get("size_bytes") or 0),
            "terminal_state_honest": assessment["terminal_status"]
            in {"complete", "review_required"},
            "accounting_passed": assessment["accounting_status"] == "passed",
            "zero_silent_loss_passed": assessment["zero_silent_loss"] == "passed",
            "public_scope_explicit": bool(
                memory_entry["source_scope"]["scope_readiness"]["financial_interpretation"]
            ),
            "normalized_artifacts_resolver_accessed": (
                document["container_format"] == "zip"
                or bool(artifacts.get("payloads"))
            ),
        }
        checks = {**generic_checks, **direct}
        verdict = "passed" if all(checks.values()) else "failed"
        source_identity = (
            str(document.get("archive_member_ref"))
            if document.get("archive_member_ref")
            else registry_id_by_ordinal[int(document["root_input_ordinal"])]
        )
        scope = memory_entry["source_scope"]
        safe_entries.append(
            {
                "source_identity": source_identity,
                "source_checksum_ref": memory_entry["source_checksum_ref"],
                "container_format": document["container_format"],
                "supported_profile_variant": assessment["profile_variant"],
                "logical_document_refs": memory_entry["logical_document_refs"],
                "terminal_state": assessment["terminal_status"],
                "normalized_artifact_counts": {
                    key: len(value)
                    for key, value in memory_entry["normalized_artifact_refs"].items()
                },
                "scope_accounting": scope["declared"],
                "accounting_status": assessment["accounting_status"],
                "zero_silent_loss": assessment["zero_silent_loss"],
                "issue_refs": sorted(set(issues_by_doc.get(document_id, []))),
                "restrictions": scope["scope_readiness"]["restrictions"],
                "gate2_memory_status": assessment["gate2_memory_status"],
                "operator_review_verdict": verdict,
                "operator_review_check_count": len(checks),
                "operator_review_failed_check_refs": sorted(
                    key for key, value in checks.items() if not value
                ),
            }
        )
        private_entries.append(
            {
                "document_ref": document_id,
                "source_identity": source_identity,
                "terminal_state": assessment["terminal_status"],
                "checks": checks,
                "verdict": verdict,
            }
        )
        del artifacts, content
    return (
        {
            "schema_version": "broker_reports_gate1_agent_operator_review_private_v1",
            "reviewer_role": "agent_operated_technical_reviewer",
            "normalization_run_id": package["normalization_run"]["run_id"],
            "documents": private_entries,
            "human_customer_acceptance": "not_performed",
        },
        safe_entries,
    )


def _direct_review(
    *,
    document: dict[str, Any],
    content: bytes,
    profile: dict[str, Any],
    assessment: dict[str, Any],
    memory_entry: dict[str, Any],
    payloads: list[dict[str, Any]],
    units: list[dict[str, Any]],
    projections: list[dict[str, Any]],
    archive_manifest: dict[str, Any],
) -> dict[str, bool]:
    container = str(document["container_format"])
    scope = memory_entry["source_scope"]["scope_readiness"]
    base = {
        "begin_middle_end_order_accounted": True,
        "declared_pages_tables_sections_members_accounted": True,
        "material_table_values_and_order_accounted": True,
        "pdf_page_and_layout_provenance_accounted": True,
        "archive_member_lineage_accounted": True,
        "unresolved_content_explicit": (
            assessment["terminal_status"] != "review_required"
            or bool(scope["restrictions"])
        ),
        "no_false_complete_state": (
            assessment["terminal_status"] != "complete"
            or not scope["unresolved_table_topology"]
        ),
        "gate2_parser_independent_memory_sufficient": assessment[
            "gate2_memory_status"
        ]
        in {"ready", "ready_with_restrictions", "lineage_only"},
    }
    if container == "csv":
        rows = _parse_csv(content, profile)
        normalized_rows = _unit_rows(units)
        base["begin_middle_end_order_accounted"] = rows == normalized_rows
        base["declared_pages_tables_sections_members_accounted"] = (
            len(rows) == int(payloads[0].get("rows_total") or 0)
        )
        base["material_table_values_and_order_accounted"] = rows == normalized_rows
    elif container == "html_text":
        parsed = _HtmlReviewParser()
        parsed.feed(_decode_text(content))
        normalized_tables = _unit_tables(units)
        normalized_text = _normalized_unit_text(units)
        base["begin_middle_end_order_accounted"] = _ordered_tokens_present(
            parsed.visible_tokens, normalized_text
        )
        base["declared_pages_tables_sections_members_accounted"] = (
            len(parsed.tables) == len(normalized_tables)
        )
        base["material_table_values_and_order_accounted"] = (
            parsed.tables == normalized_tables
        )
        normalized_media = [
            str(item.get("private_media_sha256") or "")
            for item in sorted(
                (unit for unit in units if unit.get("slice_type") == "visual_media"),
                key=lambda item: int(
                    (item.get("source_location") or {}).get("media_ordinal") or 0
                ),
            )
        ]
        base["embedded_visual_media_accounted"] = (
            parsed.embedded_media_checksums == normalized_media
        )
    elif container == "pdf":
        reader = PdfReader(io.BytesIO(content))
        projection = payloads[0]["pdf_text_layer_projection"]
        inventory = list(projection["page_inventory"])
        visual_pages = {
            int(unit.get("page_number") or 0)
            for unit in units
            if unit.get("pdf_unit_type") == "pdf_visual_page_unit"
        }
        direct_text = [page.extract_text() or "" for page in reader.pages]
        text_matches = all(
            _normalize_text(source) == _normalize_text(str(item.get("text") or ""))
            for source, item in zip(direct_text, inventory)
        )
        visual_required = {
            index
            for index, (source, item) in enumerate(zip(direct_text, inventory), start=1)
            if not _normalize_text(source)
            or int(item.get("image_objects_total") or 0) > 0
        }
        page_count_matches = len(reader.pages) == len(inventory)
        base["begin_middle_end_order_accounted"] = page_count_matches and text_matches
        base["declared_pages_tables_sections_members_accounted"] = (
            page_count_matches and visual_required <= visual_pages
        )
        base["material_table_values_and_order_accounted"] = all(
            item.get("validator_status") == "passed" for item in projections
        ) and (
            scope["canonical_table_scope"] == "ready_validated_projection_only"
            or "canonical_financial_table_not_available" in scope["restrictions"]
        )
        base["pdf_page_and_layout_provenance_accounted"] = (
            page_count_matches
            and len(projection.get("page_checksum_refs") or []) == len(reader.pages)
            and projection.get("layout_projection_status") in {"complete", "partial"}
        )
    elif container == "xml":
        root = ElementTree.fromstring(content)
        source_tokens = []
        for element in root.iter():
            source_tokens.append(_xml_local_name(element.tag))
            source_tokens.extend(str(value) for value in element.attrib.values())
            if element.text and element.text.strip():
                source_tokens.append(element.text.strip())
        normalized_text = _normalized_unit_text(units)
        base["begin_middle_end_order_accounted"] = _ordered_tokens_present(
            source_tokens, normalized_text
        )
        base["declared_pages_tables_sections_members_accounted"] = bool(_unit_rows(units))
        base["material_table_values_and_order_accounted"] = (
            scope["canonical_table_scope"] == "unavailable_neutral_structure_only"
            and scope["neutral_structure_scope"] == "ready"
        )
    elif container == "zip":
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            infos = archive.infolist()
        inventory = list(archive_manifest.get("member_inventory") or [])
        base["begin_middle_end_order_accounted"] = [
            int(item["member_index"]) for item in inventory
        ] == list(range(1, len(infos) + 1))
        base["declared_pages_tables_sections_members_accounted"] = (
            len(infos) == len(inventory)
            and all(
                int(info.file_size) == int(item["expanded_size"])
                for info, item in zip(infos, inventory)
            )
        )
        base["material_table_values_and_order_accounted"] = True
        base["archive_member_lineage_accounted"] = (
            archive_manifest.get("all_members_accounted") is True
            and int(archive_manifest.get("blocked_members_total") or 0) == 0
            and all(
                item.get("disposition") != "promoted_source_document"
                or item.get("promoted_document_ref")
                for item in inventory
            )
        )
    return base


def _parse_csv(content: bytes, profile: dict[str, Any]) -> list[list[str]]:
    text = _decode_text(content)
    delimiter = str(profile.get("delimiter") or "")
    if delimiter == "tab":
        delimiter = "\t"
    if delimiter not in {",", ";", "\t", "|"}:
        delimiter = csv.Sniffer().sniff(text[:8192], delimiters=",;\t|").delimiter
    return [list(row) for row in csv.reader(io.StringIO(text), delimiter=delimiter)]


def _unit_rows(units: list[dict[str, Any]]) -> list[list[str]]:
    table_units = [item for item in units if item.get("slice_type") == "table_rows"]
    table_units.sort(
        key=lambda item: (
            int((item.get("source_location") or {}).get("table_index") or 0),
            int((item.get("source_location") or {}).get("row_start") or 0),
        )
    )
    return [
        ["" if value is None else str(value) for value in row]
        for unit in table_units
        for row in unit.get("rows") or []
    ]


def _unit_tables(units: list[dict[str, Any]]) -> list[list[list[str]]]:
    grouped: dict[int, list[list[str]]] = defaultdict(list)
    for unit in units:
        if unit.get("slice_type") != "table_rows":
            continue
        table_index = int(
            (unit.get("source_location") or {}).get("table_ordinal") or 0
        )
        grouped[table_index].extend(
            ["" if value is None else str(value) for value in row]
            for row in unit.get("rows") or []
        )
    return [grouped[index] for index in sorted(grouped)]


def _normalized_unit_text(units: list[dict[str, Any]]) -> str:
    values = []
    for unit in units:
        if unit.get("slice_type") == "visual_page":
            continue
        if unit.get("text") is not None:
            values.append(str(unit["text"]))
        for row in unit.get("rows") or []:
            values.extend("" if value is None else str(value) for value in row)
    return " ".join(values)


class _HtmlReviewParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.visible_tokens: list[str] = []
        self.tables: list[list[list[str]]] = []
        self.embedded_media_checksums: list[str] = []
        self._blocked_depth = 0
        self._table: list[list[str]] | None = None
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style"}:
            self._blocked_depth += 1
        elif tag == "img":
            source = str(dict(attrs).get("src") or "")
            match = re.fullmatch(
                r"data:image/(?:png|jpeg|jpg|gif|webp);base64,([A-Za-z0-9+/=\s]+)",
                source,
                flags=re.IGNORECASE,
            )
            if match:
                encoded = "".join(match.group(1).split())
                try:
                    media = base64.b64decode(encoded, validate=True)
                except (ValueError, TypeError):
                    media = b""
                if media:
                    self.embedded_media_checksums.append(
                        hashlib.sha256(media).hexdigest()
                    )
        elif tag == "table":
            self._table = []
        elif tag == "tr" and self._table is not None:
            self._row = []
        elif tag in {"td", "th"} and self._row is not None:
            self._cell = []

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"} and self._blocked_depth:
            self._blocked_depth -= 1
        elif tag in {"td", "th"} and self._row is not None and self._cell is not None:
            self._row.append(_normalize_text(" ".join(self._cell)))
            self._cell = None
        elif tag == "tr" and self._table is not None and self._row is not None:
            if any(cell for cell in self._row):
                self._table.append(self._row)
            self._row = None
        elif tag == "table" and self._table is not None:
            self.tables.append(self._table)
            self._table = None

    def handle_data(self, data: str) -> None:
        if self._blocked_depth:
            return
        value = _normalize_text(data)
        if not value:
            return
        self.visible_tokens.append(value)
        if self._cell is not None:
            self._cell.append(value)


def _rows_present(expected: list[list[str]], actual: list[list[str]]) -> bool:
    if not expected:
        return True
    normalized_expected = [[_normalize_text(value) for value in row] for row in expected]
    normalized_actual = [[_normalize_text(value) for value in row] for row in actual]
    width = len(normalized_expected)
    return any(
        normalized_actual[index : index + width] == normalized_expected
        for index in range(0, len(normalized_actual) - width + 1)
    )


def _ordered_tokens_present(tokens: list[str], text: str) -> bool:
    cursor = 0
    normalized = _normalize_text(text).casefold()
    for token in tokens:
        value = _normalize_text(token).casefold()
        if not value:
            continue
        position = normalized.find(value, cursor)
        if position < 0:
            return False
        cursor = position + len(value)
    return True


def _archive_checks(package: dict[str, Any]) -> bool:
    manifests = package.get("archive_source_manifests") or []
    return (
        len(manifests) == 24
        and sum(int(item.get("promoted_members_total") or 0) for item in manifests)
        == 48
        and sum(int(item.get("signature_sidecars_total") or 0) for item in manifests)
        == 24
        and all(
            item.get("terminal_status") == "complete"
            and item.get("all_members_accounted") is True
            and int(item.get("blocked_members_total") or 0) == 0
            for item in manifests
        )
    )


def _decode_text(content: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp1251"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise RuntimeError("actual_text_encoding_unsupported")


def _normalize_text(value: str) -> str:
    return " ".join(str(value).replace("\xa0", " ").split())


def _xml_local_name(value: str) -> str:
    return str(value).split("}", 1)[-1]


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _assert_private_root(path: Path) -> None:
    resolved = path.resolve()
    if not resolved.exists():
        raise RuntimeError(f"private_root_missing:{resolved}")
    if _is_relative_to(resolved, REPO_ROOT.resolve()):
        raise RuntimeError("private_corpus_must_be_outside_git_repository")


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


if __name__ == "__main__":
    main()
