from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT))

from broker_reports_gate1 import (  # noqa: E402
    ArtifactAccessContext,
    ArtifactStoreConfig,
    ArtifactStoreError,
    ArtifactStoreFactory,
    FileInput,
    Gate1Normalizer,
    build_retention_policy,
    persist_gate1_result,
    render_chat_content,
)
from broker_reports_gate1.artifact_retention import RetentionPolicyError  # noqa: E402


DEFAULT_PRIVATE_REGISTRY = (
    "local/stage2/broker_reports_customer_source_documents_intake_2026-07-06/private_registry.json"
)
DEFAULT_SAFE_SOURCE_REGISTRY = (
    "docs/stage2/domain/BROKER_REPORTS_CUSTOMER_SOURCE_DOCUMENTS_INDEX.v0.safe.json"
)
DEFAULT_SAFE_REGISTRY = (
    "docs/stage2/domain/BROKER_REPORTS_CUSTOMER_SOURCE_DOCUMENTS_INDEX.vNEXT.safe.json"
)
DEFAULT_CASE_GROUPS = "docs/stage2/domain/BROKER_REPORTS_CUSTOMER_CASE_GROUPS.v0.safe.json"
DEFAULT_REPORT = (
    "docs/reports/2026-07-08/"
    "OPENWEBUI_BROKER_REPORTS_CUSTOMER_APPROVED_PACKAGE_GROUPING.report.md"
)
DEFAULT_ARTIFACT_ROOT = (
    "local/stage2/broker_reports_customer_approved_package_grouping_2026-07-08/artifactstore"
)

SOURCE_CLASSES = {
    "source_broker_report",
    "operations_table",
    "dividends_report",
    "fees_report",
    "withholding_report",
    "currency_rate_table",
}
OUTPUT_OR_METHODOLOGY_CLASSES = {
    "calculation_template",
    "tax_base_calculation",
    "explanation_template",
    "official_form",
    "official_filling_instruction",
    "official_electronic_format",
    "methodology_instruction",
    "expected_output_example",
}
REVIEW_CLASSES = {
    "archive_package",
    "image_or_scan_requires_review",
    "unknown_or_needs_review",
    "unsupported",
}


class CustomerGroupingError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class SourceFile:
    document_id: str
    absolute_path: Path
    relative_path_private: str
    original_filename_private: str
    sha256: str | None
    mime_type: str


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build safe customer-approved Broker Reports package grouping artifacts."
    )
    parser.add_argument("--private-registry", default=os.getenv("BROKER_REPORTS_CUSTOMER_PRIVATE_REGISTRY", DEFAULT_PRIVATE_REGISTRY))
    parser.add_argument("--safe-source-registry", default=DEFAULT_SAFE_SOURCE_REGISTRY)
    parser.add_argument("--safe-registry", default=DEFAULT_SAFE_REGISTRY)
    parser.add_argument("--case-groups", default=DEFAULT_CASE_GROUPS)
    parser.add_argument("--report", default=DEFAULT_REPORT)
    parser.add_argument("--artifact-root", default=os.getenv("BROKER_REPORTS_CUSTOMER_ARTIFACT_ROOT", DEFAULT_ARTIFACT_ROOT))
    parser.add_argument("--retention-mode", default=os.getenv("BROKER_REPORTS_GATE1_RETENTION_MODE", "customer_approved_test"))
    parser.add_argument("--retention-explicit", action="store_true", default=_env_truthy("BROKER_REPORTS_GATE1_RETENTION_EXPLICIT"))
    parser.add_argument("--expected-file-count", type=int, default=63)
    parser.add_argument("--case-id", default="customer_approved_package_grouping_2026_07_08")
    parser.add_argument("--user-id", default="operator_customer_approved_test")
    parser.add_argument("--workspace-model-id", default="broker_reports_gate1_customer_approved_cli")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--check-openwebui-knowledge", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        summary = run_grouping(args)
    except CustomerGroupingError as exc:
        print(
            json.dumps(
                {
                    "status": "blocked",
                    "blocker_code": exc.code,
                    "message": exc.message,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 2
    except (ArtifactStoreError, RetentionPolicyError) as exc:
        code = getattr(exc, "code", exc.__class__.__name__)
        message = getattr(exc, "message", str(exc))
        print(
            json.dumps(
                {
                    "status": "blocked",
                    "blocker_code": code,
                    "message": message,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 2
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def run_grouping(args: argparse.Namespace) -> dict[str, Any]:
    if args.retention_mode != "customer_approved_test":
        raise CustomerGroupingError(
            "retention_policy_invalid",
            "customer-approved grouping requires retention_policy.mode=customer_approved_test",
        )
    if not args.retention_explicit:
        raise CustomerGroupingError(
            "retention_policy_missing",
            "customer_approved_test requires an explicit retention policy",
        )

    private_registry_path = _repo_path(args.private_registry)
    safe_source_registry_path = _repo_path(args.safe_source_registry)
    safe_registry_path = _repo_path(args.safe_registry)
    case_groups_path = _repo_path(args.case_groups)
    report_path = _repo_path(args.report)
    artifact_root = _repo_path(args.artifact_root)

    private_registry = _load_json(private_registry_path)
    source_registry = _load_json(safe_source_registry_path)
    source_files = _source_files(private_registry, source_registry)
    if len(source_files) != args.expected_file_count:
        raise CustomerGroupingError(
            "customer_package_file_count_mismatch",
            f"Expected {args.expected_file_count} approved files, got {len(source_files)}",
        )

    knowledge_before = None
    if args.check_openwebui_knowledge:
        knowledge_before = _knowledge_count(args.env_file)

    file_inputs = [_file_input(item) for item in source_files]
    result = Gate1Normalizer().normalize(
        file_inputs,
        input_context={
            "case_id": args.case_id,
            "source_boundary": "operator_approved_private_registry",
            "customer_docs_loaded_to_knowledge": False,
            "retention_policy_mode": "customer_approved_test",
        },
        entrypoint="customer_approved_package_grouping_cli",
        trigger_type="customer_approved_test",
    )
    retention_policy = build_retention_policy(mode="customer_approved_test", explicit=True)
    context = ArtifactAccessContext(
        user_id=args.user_id,
        case_id=args.case_id,
        chat_id=None,
        workspace_model_id=args.workspace_model_id,
        normalization_run_id=result.package["normalization_run"]["run_id"],
        allow_private=True,
    )
    store = ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=artifact_root / "artifacts.sqlite3",
            payload_root=artifact_root / "payloads",
        )
    ).create()
    manifest = persist_gate1_result(
        store=store,
        result=result,
        context=context,
        retention_policy=retention_policy,
        source_file_refs=[
            {
                "provider": "operator_private_registry",
                "openwebui_file_id": None,
                "file_hash_sha256": item.sha256,
                "content_type": item.mime_type,
                "size_bytes": item.absolute_path.stat().st_size,
                "source_deleted": False,
            }
            for item in source_files
        ],
    )
    records = store.list_by_run(context.normalization_run_id)
    knowledge_after = None
    if args.check_openwebui_knowledge:
        knowledge_after = _knowledge_count(args.env_file)

    safe_registry, case_group_registry = _build_safe_outputs(
        source_registry=source_registry,
        result=result,
        manifest=manifest.to_dict(),
        records=records,
        retention_policy=retention_policy.to_dict(),
        artifact_boundary_label=str(Path(args.artifact_root).as_posix()),
    )
    safe_registry_path.parent.mkdir(parents=True, exist_ok=True)
    case_groups_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(safe_registry_path, safe_registry)
    _write_json(case_groups_path, case_group_registry)
    _write_report(
        report_path,
        safe_registry=safe_registry,
        case_group_registry=case_group_registry,
        result=result,
        manifest=manifest.to_dict(),
        retention_policy=retention_policy.to_dict(),
        artifact_boundary_label=str(Path(args.artifact_root).as_posix()),
        knowledge_before=knowledge_before,
        knowledge_after=knowledge_after,
    )

    chat_content = render_chat_content(result.safe_report)
    _assert_no_private_leaks(
        outputs=[
            safe_registry_path.read_text(encoding="utf-8-sig"),
            case_groups_path.read_text(encoding="utf-8-sig"),
            report_path.read_text(encoding="utf-8-sig"),
            chat_content,
        ],
        source_files=source_files,
    )
    _assert_knowledge_guard(records, knowledge_before, knowledge_after)

    return {
        "status": "passed",
        "files_processed": len(source_files),
        "safe_registry": _repo_relative(safe_registry_path),
        "case_groups": _repo_relative(case_groups_path),
        "report": _repo_relative(report_path),
        "retention_policy": {
            "mode": retention_policy.mode,
            "explicit": retention_policy.explicit,
            "ttl_seconds": retention_policy.ttl_seconds,
        },
        "artifactstore": {
            "records": len(records),
            "private_payload_records": sum(1 for record in records if record.visibility == "private_case"),
            "knowledge_backend_records": sum(1 for record in records if record.storage_backend == "openwebui_knowledge"),
            "gate2_handoff_ref_available": bool(manifest.gate2_handoff_ref),
        },
        "knowledge": {
            "checked": args.check_openwebui_knowledge,
            "before": knowledge_before,
            "after": knowledge_after,
            "unchanged": knowledge_before == knowledge_after if knowledge_before is not None else None,
        },
        "recommended_case_group_id": case_group_registry["recommended_first_package"]["case_group_id"],
        "safety_flags": result.safe_report["safety_flags"],
    }


def _build_safe_outputs(
    *,
    source_registry: dict[str, Any],
    result: Any,
    manifest: dict[str, Any],
    records: list[Any],
    retention_policy: dict[str, Any],
    artifact_boundary_label: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    source_docs = list(source_registry.get("documents", []))
    source_groups = list(source_registry.get("case_groups", []))
    package = result.package
    gate_docs = package["document_inventory"]["documents"]
    gate_taxonomy = {item["document_id"]: item for item in package["taxonomy_candidates"]}
    gate_profiles = {item["document_id"]: item for item in package["technical_readability_profiles"]}
    gate_docs_by_sha = {item.get("sha256"): item for item in gate_docs if item.get("sha256")}
    record_refs = _record_refs(records)
    source_doc_by_id = {item["document_id"]: item for item in source_docs}
    group_by_doc = {
        doc_id: group["case_group_id"]
        for group in source_groups
        for doc_id in group.get("document_ids", [])
    }
    duplicate_map = _duplicate_map(source_docs)
    duplicate_doc_ids = {doc_id for item in duplicate_map for doc_id in item["duplicate_document_ids"]}
    vnext_docs = []
    for doc in source_docs:
        gate_doc = gate_docs_by_sha.get(doc.get("sha256")) or {}
        gate_doc_id = gate_doc.get("document_id")
        taxonomy = gate_taxonomy.get(str(gate_doc_id), {})
        profile = gate_profiles.get(str(gate_doc_id), {})
        role = doc.get("document_taxonomy_class") or taxonomy.get("document_class_candidate") or "unknown_or_needs_review"
        review_reasons = _review_reasons(doc, gate_doc, profile, duplicate_doc_ids)
        vnext_docs.append(
            {
                "schema_version": "broker_reports_customer_source_document_vNEXT_safe",
                "document_id": doc["document_id"],
                "gate1_document_id": gate_doc_id,
                "case_group_id": group_by_doc.get(doc["document_id"], "case_group_unassigned"),
                "container_format": gate_doc.get("container_format") or doc.get("container_format"),
                "extension": doc.get("extension"),
                "file_size_bytes": doc.get("file_size_bytes"),
                "sha256": doc.get("sha256"),
                "hash_prefix": str(doc.get("sha256") or "")[:16],
                "duplicate_group_id": _duplicate_group_id(doc, duplicate_map),
                "duplicate_of_document_id": _duplicate_of(doc, duplicate_map),
                "readability_status": gate_doc.get("readable") or doc.get("readable"),
                "document_role_candidate": role,
                "secondary_role_candidates": _safe_secondary_tags(doc),
                "source_vs_output": _source_vs_output(role, doc),
                "source_evidence_candidate": doc.get("can_be_source_evidence", "conditional"),
                "methodology_or_output_candidate": doc.get("can_be_methodology", "conditional"),
                "can_move_to_next_gate": not review_reasons and role in SOURCE_CLASSES,
                "manual_review_required": bool(review_reasons) or role not in SOURCE_CLASSES,
                "review_reasons": review_reasons,
                "artifact_refs": {
                    "source_file_ref": record_refs.get((gate_doc_id, "source_file_ref_v0")),
                    "private_slice_refs": record_refs.get((gate_doc_id, "private_slice"), []),
                },
                "safety": {
                    "raw_filename_published": False,
                    "raw_path_published": False,
                    "raw_rows_or_text_published": False,
                    "customer_docs_loaded_to_knowledge": False,
                },
            }
        )

    case_groups = [_enrich_case_group(group, source_doc_by_id, duplicate_map) for group in source_groups]
    review_queue = _review_queue(vnext_docs)
    archive_review_map = _archive_review_map(vnext_docs, source_doc_by_id)
    recommended = _recommend_first_package(case_groups)
    generated_at = _now_msk()
    safe_registry = {
        "schema_version": "broker_reports_customer_source_documents_index_vNEXT_safe",
        "generated_at_msk": generated_at,
        "base_registry_ref": DEFAULT_SAFE_SOURCE_REGISTRY,
        "source_root_path_included": False,
        "source_root_public_label": source_registry.get("source_root_public_label", "withheld_customer_local_folder"),
        "retention_policy": retention_policy,
        "artifactstore": {
            "storage_boundary": "project_artifact_store",
            "artifact_boundary_public_label": artifact_boundary_label,
            "private_payloads_persisted": True,
            "private_payload_paths_published": False,
            "gate2_handoff_ref": manifest["gate2_handoff_ref"],
            "customer_docs_loaded_to_knowledge": False,
        },
        "summary": _summary(vnext_docs, case_groups, duplicate_map, review_queue, archive_review_map),
        "safety_boundary": _safety_boundary(),
        "documents": vnext_docs,
    }
    case_group_registry = {
        "schema_version": "broker_reports_customer_case_groups_v0_safe",
        "generated_at_msk": generated_at,
        "source_registry_ref": DEFAULT_SAFE_REGISTRY,
        "retention_policy": retention_policy,
        "artifactstore": safe_registry["artifactstore"],
        "case_groups": case_groups,
        "duplicate_map": duplicate_map,
        "unknown_review_queue": review_queue,
        "archive_zip_review_map": archive_review_map,
        "recommended_first_package": recommended,
        "gate2_handoff": {
            "normalization_run_id": manifest["normalization_run_id"],
            "gate2_handoff_ref": manifest["gate2_handoff_ref"],
            "uses_opaque_refs": True,
            "chat_json_used_as_handoff": False,
        },
        "safety_boundary": _safety_boundary(),
    }
    return safe_registry, case_group_registry


def _enrich_case_group(
    group: dict[str, Any],
    source_doc_by_id: dict[str, dict[str, Any]],
    duplicate_map: list[dict[str, Any]],
) -> dict[str, Any]:
    docs = [source_doc_by_id[doc_id] for doc_id in group.get("document_ids", []) if doc_id in source_doc_by_id]
    class_counts = Counter(str(doc.get("document_taxonomy_class")) for doc in docs)
    source_count = sum(1 for doc in docs if doc.get("document_taxonomy_class") in SOURCE_CLASSES)
    output_count = sum(1 for doc in docs if doc.get("document_taxonomy_class") in OUTPUT_OR_METHODOLOGY_CLASSES)
    review_count = sum(1 for doc in docs if doc.get("document_taxonomy_class") in REVIEW_CLASSES or doc.get("container_format") == "zip")
    duplicate_count = sum(
        1
        for dup in duplicate_map
        for doc_id in dup["duplicate_document_ids"]
        if doc_id in group.get("document_ids", [])
    )
    archive_count = sum(1 for doc in docs if doc.get("container_format") == "zip")
    confidence = "medium"
    if group.get("probable_broker_or_role") == "unknown" or review_count:
        confidence = "low"
    if source_count >= 3 and not review_count and group.get("probable_broker_or_role") != "unknown":
        confidence = "high"
    review_reasons = list(group.get("missing_or_blocking_items") or [])
    if archive_count:
        review_reasons.append("archive_package_requires_manual_review")
    if review_count:
        review_reasons.append("unknown_or_review_documents_present")
    if duplicate_count:
        review_reasons.append("duplicate_documents_present")
    return {
        "case_group_id": group["case_group_id"],
        "broker_provider_candidate": group.get("probable_broker_or_role", "unknown"),
        "tax_year_candidate": group.get("probable_tax_years") or ["unknown"],
        "account_package_candidate": group.get("account_marker_hash", "unknown"),
        "document_family_counts": dict(sorted(class_counts.items())),
        "document_ids": list(group.get("document_ids", [])),
        "source_vs_output": {
            "source_evidence_candidates": source_count,
            "output_or_methodology_artifacts": output_count,
            "review_or_unknown_documents": review_count,
        },
        "duplicate_relation_count": duplicate_count,
        "archive_membership_relation": {
            "archive_documents_count": archive_count,
            "archive_contents_not_promoted_to_source_evidence": True,
        },
        "confidence": confidence,
        "manual_review_required": bool(review_reasons),
        "review_reason": sorted(set(review_reasons)),
        "readiness": group.get("readiness", "needs_review"),
        "can_move_to_gate2_proof": source_count > 0 and not archive_count,
    }


def _summary(
    docs: list[dict[str, Any]],
    case_groups: list[dict[str, Any]],
    duplicate_map: list[dict[str, Any]],
    review_queue: list[dict[str, Any]],
    archive_review_map: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "files_total": len(docs),
        "container_counts": dict(sorted(Counter(item["container_format"] for item in docs).items())),
        "document_role_counts": dict(sorted(Counter(item["document_role_candidate"] for item in docs).items())),
        "case_group_count": len(case_groups),
        "duplicate_group_count": len(duplicate_map),
        "duplicate_document_count": sum(len(item["duplicate_document_ids"]) for item in duplicate_map),
        "review_queue_count": len(review_queue),
        "archive_review_count": len(archive_review_map),
        "source_evidence_candidate_count": sum(1 for item in docs if item["source_vs_output"] == "source_evidence_candidate"),
        "output_or_methodology_candidate_count": sum(1 for item in docs if item["source_vs_output"] == "output_or_methodology_artifact"),
    }


def _review_queue(docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    queue = []
    for doc in docs:
        if not doc["manual_review_required"]:
            continue
        queue.append(
            {
                "document_id": doc["document_id"],
                "case_group_id": doc["case_group_id"],
                "document_role_candidate": doc["document_role_candidate"],
                "container_format": doc["container_format"],
                "review_reasons": doc["review_reasons"],
                "can_move_to_next_gate": doc["can_move_to_next_gate"],
            }
        )
    return queue


def _archive_review_map(
    docs: list[dict[str, Any]],
    source_doc_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    result = []
    for doc in docs:
        if doc["container_format"] != "zip":
            continue
        source = source_doc_by_id.get(doc["document_id"], {})
        profile = source.get("technical_profile", {}) or {}
        result.append(
            {
                "document_id": doc["document_id"],
                "case_group_id": doc["case_group_id"],
                "member_count": profile.get("archive_member_count") or profile.get("members_count") or profile.get("member_count"),
                "extension_counts": profile.get("archive_extension_summary") or profile.get("extension_counts") or {},
                "review_required": True,
                "archive_contents_promoted_to_source_evidence": False,
            }
        )
    return result


def _duplicate_map(docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_hash: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for doc in docs:
        sha = doc.get("sha256")
        if sha:
            by_hash[str(sha)].append(doc)
    duplicates = []
    for sha, items in sorted(by_hash.items()):
        if len(items) <= 1:
            continue
        canonical = items[0]["document_id"]
        duplicates.append(
            {
                "duplicate_group_id": f"dupgrp_{sha[:12]}",
                "content_sha256": sha,
                "canonical_document_id": canonical,
                "duplicate_document_ids": [item["document_id"] for item in items[1:]],
                "all_document_ids": [item["document_id"] for item in items],
                "relation": "same_content_sha256",
            }
        )
    return duplicates


def _recommend_first_package(case_groups: list[dict[str, Any]]) -> dict[str, Any]:
    candidates = sorted(
        case_groups,
        key=lambda item: (
            item["can_move_to_gate2_proof"],
            item["source_vs_output"]["source_evidence_candidates"],
            item["confidence"] == "high",
            -item["source_vs_output"]["review_or_unknown_documents"],
        ),
        reverse=True,
    )
    selected = candidates[0]
    return {
        "case_group_id": selected["case_group_id"],
        "reason": "largest coherent source-evidence group with no archive dependency preferred for controlled Gate 2 proof",
        "gate2_scope": "selected_case_group_only",
        "requires_before_gate2_execution": [
            "operator confirms selected case_group_id",
            "customer/specialist confirms methodology boundary",
            "source-fact extraction approval is explicit",
        ],
    }


def _write_report(
    path: Path,
    *,
    safe_registry: dict[str, Any],
    case_group_registry: dict[str, Any],
    result: Any,
    manifest: dict[str, Any],
    retention_policy: dict[str, Any],
    artifact_boundary_label: str,
    knowledge_before: int | None,
    knowledge_after: int | None,
) -> None:
    summary = safe_registry["summary"]
    selected = case_group_registry["recommended_first_package"]
    group_lines = []
    for group in case_group_registry["case_groups"]:
        group_lines.append(
            f"- `{group['case_group_id']}`: брокер/провайдер=`{group['broker_provider_candidate']}`, "
            f"документов={len(group['document_ids'])}, source={group['source_vs_output']['source_evidence_candidates']}, "
            f"output/methodology={group['source_vs_output']['output_or_methodology_artifacts']}, "
            f"review={group['source_vs_output']['review_or_unknown_documents']}, confidence={group['confidence']}"
        )
    lines = [
        "# OpenWebUI Broker Reports: Customer-Approved Package Grouping Report",
        "",
        "Date: 2026-07-08",
        "",
        "Status:",
        "",
        "- CUSTOMER_APPROVED_PACKAGE_GROUPING_READY",
        "- CUSTOMER_SOURCE_REGISTRY_UPDATED",
        "- CUSTOMER_CASE_GROUPS_CREATED",
        "- CUSTOMER_DUPLICATE_MAP_READY",
        "- CUSTOMER_REVIEW_QUEUE_READY",
        "- CUSTOMER_APPROVED_RETENTION_APPLIED",
        "- CUSTOMER_ARTIFACTSTORE_PERSISTENCE_READY",
        "- CUSTOMER_KNOWLEDGE_GUARD_PASSED",
        "- READY_FOR_SELECTED_CASE_GROUP_GATE2_PROOF",
        "",
        "## 1. Граница среза",
        "",
        "Выполнена controlled Gate 1 группировка operator-approved customer test package.",
        "Источник взят только из ignored private local registry предыдущего approved intake run.",
        "",
        "Raw filenames, relative paths, full local paths, rows, sheet names и private text в отчёте не публикуются.",
        "Customer documents не копировались в репозиторий и не коммитились.",
        "",
        "## 2. Файлы и форматы",
        "",
        f"- Обработано файлов: `{summary['files_total']}`",
        f"- Форматы: `{summary['container_counts']}`",
        f"- Классы документов: `{summary['document_role_counts']}`",
        "",
        "## 3. Case/package groups",
        "",
        *group_lines,
        "",
        "## 4. Source vs output/methodology",
        "",
        f"- Source evidence candidates: `{summary['source_evidence_candidate_count']}`",
        f"- Output/methodology/calculation artifacts: `{summary['output_or_methodology_candidate_count']}`",
        f"- Документов в review queue: `{summary['review_queue_count']}`",
        f"- ZIP/archive review entries: `{summary['archive_review_count']}`",
        "",
        "Source evidence здесь означает только Gate 1 role candidate. Source-fact extraction не запускался.",
        "",
        "## 5. Дубликаты, архивы и blockers",
        "",
        f"- Duplicate groups: `{summary['duplicate_group_count']}`",
        f"- Duplicate documents: `{summary['duplicate_document_count']}`",
        f"- Архивов, требующих review: `{summary['archive_review_count']}`",
        f"- Gate 1 normalizer blockers: `{len(result.package.get('normalization_blockers', []))}`",
        "",
        "ZIP/archive contents не повышались до source evidence. OCR/VLM не выполнялся.",
        "",
        "## 6. Рекомендованный первый пакет для Gate 2 proof",
        "",
        f"Рекомендованный case group: `{selected['case_group_id']}`",
        "",
        "Причина: самая связная группа с большим количеством source-evidence candidates и без зависимости от ZIP/archive review.",
        "",
        "Перед Gate 2 execution нужно спросить заказчика/специалиста:",
        "",
        "- подтвердить выбранный case group;",
        "- подтвердить tax year/account boundary, если он не следует из safe metadata;",
        "- уточнить, являются ли output/calculation files примерами, методологией или прежними результатами;",
        "- явно подтвердить разрешение на source-fact extraction для этого пакета;",
        "- подтвердить методологию по fees, FX/rates, withholding и tax-base treatment.",
        "",
        "## 7. Safe/private artifacts",
        "",
        f"- Safe source registry: `{DEFAULT_SAFE_REGISTRY}`",
        f"- Case/package grouping registry: `{DEFAULT_CASE_GROUPS}`",
        f"- Private ArtifactStore boundary: `{artifact_boundary_label}`",
        f"- Gate 2 handoff ref available: `{bool(manifest.get('gate2_handoff_ref'))}`",
        "- Gate 2 handoff использует opaque ArtifactStore refs, not chat JSON.",
        "",
        "Private ArtifactStore boundary находится в ignored local storage и не коммитится.",
        "",
        "## 8. Retention и Knowledge guard",
        "",
        f"- retention_policy.mode: `{retention_policy['mode']}`",
        f"- retention_policy.explicit: `{retention_policy['explicit']}`",
        f"- retention_policy.ttl_seconds: `{retention_policy['ttl_seconds']}`",
        "- private slices persisted as `private_case` records;",
        "- purge policy доступна через ArtifactStore case/run purge;",
        "- customer_docs_loaded_to_knowledge=false.",
        "",
        f"OpenWebUI Knowledge count before: `{knowledge_before}`",
        f"OpenWebUI Knowledge count after: `{knowledge_after}`",
        f"Knowledge unchanged: `{knowledge_before == knowledge_after if knowledge_before is not None else 'not_checked'}`",
        "",
        "## 9. Commands",
        "",
        "```text",
        "python services/broker-reports-gate1-proof/scripts/customer_approved_package_grouping.py --retention-explicit --check-openwebui-knowledge --env-file .env",
        "python -m unittest discover -s services/broker-reports-gate1-proof/tests -v",
        "python -m compileall -q services/broker-reports-gate1-proof",
        "git diff --check",
        "```",
        "",
        "## 10. Запрещённые работы не выполнялись",
        "",
        "- source_fact_extraction_performed=false;",
        "- tax_correctness_claimed=false;",
        "- declaration_generated=false;",
        "- xlsx_generated=false;",
        "- ocr_performed=false;",
        "- customer documents/private slices не загружались в Knowledge;",
        "- raw filenames/private paths/rows/text/sheet names не публиковались.",
        "",
    ]
    _write_text_bom(path, "\n".join(lines))


def _source_files(private_registry: dict[str, Any], source_registry: dict[str, Any]) -> list[SourceFile]:
    safe_docs_by_id = {doc["document_id"]: doc for doc in source_registry.get("documents", [])}
    source_files: list[SourceFile] = []
    for item in private_registry.get("documents", []):
        doc_id = str(item.get("document_id") or "")
        if not doc_id:
            raise CustomerGroupingError("private_registry_invalid", "Private registry document is missing document_id")
        absolute_path = Path(str(item.get("absolute_path") or ""))
        if not absolute_path.is_file():
            raise CustomerGroupingError("customer_source_file_missing", "A private-registry source file is unavailable")
        safe_doc = safe_docs_by_id.get(doc_id, {})
        source_files.append(
            SourceFile(
                document_id=doc_id,
                absolute_path=absolute_path,
                relative_path_private=str(item.get("relative_path") or ""),
                original_filename_private=str(item.get("original_filename") or absolute_path.name),
                sha256=item.get("sha256") or safe_doc.get("sha256"),
                mime_type=str(safe_doc.get("detected_mime_type") or mimetypes.guess_type(str(absolute_path))[0] or ""),
            )
        )
    return source_files


def _file_input(item: SourceFile) -> FileInput:
    return FileInput(
        private_ref=f"customer-approved:{item.document_id}",
        original_filename_private=item.original_filename_private,
        mime_type=item.mime_type,
        source_kind="local_private_test",
        declared_size_bytes=item.absolute_path.stat().st_size,
        bytes_provider=item.absolute_path.read_bytes,
        provider_label="operator_private_registry",
        privacy_markers=[
            str(item.absolute_path),
            str(item.absolute_path.resolve()),
            item.relative_path_private,
            item.original_filename_private,
        ],
    )


def _record_refs(records: list[Any]) -> dict[tuple[str | None, str], Any]:
    refs: dict[tuple[str | None, str], Any] = {}
    for record in records:
        if record.artifact_type == "source_file_ref_v0":
            refs[(record.document_id, "source_file_ref_v0")] = record.artifact_id
        if record.visibility == "private_case":
            refs.setdefault((record.document_id, "private_slice"), []).append(record.artifact_id)
    return refs


def _review_reasons(
    doc: dict[str, Any],
    gate_doc: dict[str, Any],
    profile: dict[str, Any],
    duplicate_doc_ids: set[str],
) -> list[str]:
    reasons = []
    role = doc.get("document_taxonomy_class")
    if role in REVIEW_CLASSES:
        reasons.append(str(role))
    if doc.get("container_format") == "zip" or gate_doc.get("container_format") == "zip":
        reasons.append("archive_requires_manual_review")
    if doc["document_id"] in duplicate_doc_ids:
        reasons.append("duplicate_document")
    if doc.get("can_be_source_evidence") == "conditional":
        reasons.append("conditional_source_evidence")
    if doc.get("can_be_methodology") == "conditional":
        reasons.append("conditional_methodology_or_output")
    if profile.get("raster_or_scan_likelihood") == "high" or profile.get("ocr_performed") is False and profile.get("text_layer") == "no":
        reasons.append("scan_or_raster_requires_review_no_ocr_performed")
    if gate_doc.get("blocker_refs"):
        reasons.append("gate1_blockers_present")
    return sorted(set(reasons))


def _source_vs_output(role: str, doc: dict[str, Any]) -> str:
    if role in SOURCE_CLASSES:
        return "source_evidence_candidate"
    if role in OUTPUT_OR_METHODOLOGY_CLASSES or doc.get("declaration_relevance") in {"review_output", "methodology"}:
        return "output_or_methodology_artifact"
    return "review_or_unknown"


def _safe_secondary_tags(doc: dict[str, Any]) -> list[str]:
    return [
        str(tag)
        for tag in doc.get("secondary_tags", [])
        if tag not in {"customer_sample_pending_review"}
    ]


def _duplicate_group_id(doc: dict[str, Any], duplicate_map: list[dict[str, Any]]) -> str | None:
    for item in duplicate_map:
        if doc["document_id"] in item["all_document_ids"]:
            return item["duplicate_group_id"]
    return None


def _duplicate_of(doc: dict[str, Any], duplicate_map: list[dict[str, Any]]) -> str | None:
    for item in duplicate_map:
        if doc["document_id"] in item["duplicate_document_ids"]:
            return item["canonical_document_id"]
    return None


def _safety_boundary() -> dict[str, bool]:
    return {
        "source_documents_copied_to_repo": False,
        "source_documents_committed": False,
        "raw_filenames_in_safe_registry": False,
        "raw_relative_paths_in_safe_registry": False,
        "full_local_paths_in_safe_registry": False,
        "raw_rows_or_text_in_safe_registry": False,
        "tax_calculation_performed": False,
        "source_fact_extraction_performed": False,
        "declaration_generated": False,
        "xls_xlsx_generated": False,
        "ocr_vlm_performed": False,
        "customer_docs_loaded_to_knowledge": False,
    }


def _assert_no_private_leaks(outputs: list[str], source_files: list[SourceFile]) -> None:
    combined = "\n".join(outputs)
    forbidden = []
    for item in source_files:
        candidates = {
            item.original_filename_private,
            item.relative_path_private,
            str(item.absolute_path),
            str(item.absolute_path.resolve()),
        }
        for candidate in candidates:
            if candidate and candidate in combined:
                forbidden.append(candidate)
    if forbidden:
        raise CustomerGroupingError(
            "privacy_violation",
            "Generated safe outputs contain private source markers",
        )
    forbidden_literals = [
        "private_normalized_slices",
        '"rows"',
        '"text"',
        "openwebui_knowledge",
    ]
    for literal in forbidden_literals:
        if literal in combined:
            raise CustomerGroupingError(
                "privacy_violation",
                "Generated safe outputs contain forbidden private/internal marker",
            )


def _assert_knowledge_guard(records: list[Any], before: int | None, after: int | None) -> None:
    if any(record.storage_backend == "openwebui_knowledge" for record in records):
        raise CustomerGroupingError(
            "knowledge_storage_forbidden",
            "ArtifactStore records used OpenWebUI Knowledge storage",
        )
    if before is not None and before != after:
        raise CustomerGroupingError(
            "knowledge_count_changed",
            "OpenWebUI Knowledge count changed during customer-approved grouping",
        )


def _knowledge_count(env_file: str) -> int:
    import urllib.error
    import urllib.request

    env = _load_env_file(_repo_path(env_file))
    host = env.get("OPENWEBUI_HOST")
    email = env.get("WEBUI_ADMIN_EMAIL")
    password = env.get("WEBUI_ADMIN_PASSWORD")
    if not host or not email or not password:
        raise CustomerGroupingError(
            "openwebui_env_missing",
            "OpenWebUI Knowledge check requires OPENWEBUI_HOST, WEBUI_ADMIN_EMAIL and WEBUI_ADMIN_PASSWORD",
        )
    host = host.rstrip("/")
    if "://" not in host:
        host = f"https://{host}"
    payload = json.dumps({"email": email, "password": password}).encode("utf-8")
    request = urllib.request.Request(
        f"{host}/api/v1/auths/signin",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            token = json.loads(response.read().decode("utf-8")).get("token")
    except (urllib.error.URLError, ValueError) as exc:
        raise CustomerGroupingError("openwebui_auth_failed", "OpenWebUI auth failed for Knowledge check") from exc
    if not token:
        raise CustomerGroupingError("openwebui_auth_failed", "OpenWebUI auth token missing")
    request = urllib.request.Request(
        f"{host}/api/v1/knowledge/",
        headers={"Authorization": f"Bearer {token}"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, ValueError) as exc:
        raise CustomerGroupingError("openwebui_knowledge_check_failed", "OpenWebUI Knowledge check failed") from exc
    if isinstance(data, list):
        return len(data)
    if isinstance(data, dict) and isinstance(data.get("total"), int):
        return int(data["total"])
    if isinstance(data, dict) and isinstance(data.get("items"), list):
        return len(data["items"])
    if isinstance(data, dict) and isinstance(data.get("data"), list):
        return len(data["data"])
    raise CustomerGroupingError("openwebui_knowledge_shape_unknown", "OpenWebUI Knowledge response shape is unknown")


def _load_env_file(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    if not path.exists():
        return result
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key.strip()] = value.strip().strip('"').strip("'")
    return result


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise CustomerGroupingError("input_file_missing", f"Required input is missing: {_repo_relative(path)}")
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_text_bom(path: Path, text: str) -> None:
    path.write_text("\ufeff" + text, encoding="utf-8")


def _repo_path(value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return REPO / path


def _repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO.resolve()).as_posix()
    except ValueError:
        return path.name


def _now_msk() -> str:
    return datetime.now(ZoneInfo("Europe/Moscow")).isoformat(timespec="seconds")


def _env_truthy(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "y", "on"}


if __name__ == "__main__":
    raise SystemExit(main())
