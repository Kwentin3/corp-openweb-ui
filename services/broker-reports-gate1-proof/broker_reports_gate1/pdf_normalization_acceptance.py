from __future__ import annotations

import copy
import gzip
import hashlib
from dataclasses import dataclass
from typing import Any

from .pdf_compact_canonical import (
    PDF_COMPACT_CANONICAL_SCHEMA_VERSION,
    PdfCompactCanonicalError,
    PdfCompactCanonicalValidator,
    canonical_json_bytes,
    compact_source_evidence,
    compact_table_cells,
)


PDF_NORMALIZATION_ACCEPTANCE_SCHEMA_VERSION = (
    "broker_reports_pdf_normalization_acceptance_v1"
)
PDF_NORMALIZATION_ACCEPTANCE_POLICY_VERSION = "pdf_normalization_acceptance_policy_v1"

FACTORY_REQUIRED = (
    "PdfNormalizationAcceptanceFactory.create is the only production PDF acceptance entrypoint"
)
FORBIDDEN = (
    "Acceptance gates are independent and must not be bypassed, merged into one score, "
    "or weakened because current forensic artifacts remain available"
)

_GUARDS = {
    "knowledge_rag_used": False,
    "vectorization_performed": False,
    "ocr_vlm_used": False,
    "page_rendering_used_for_extraction": False,
    "provider_pdf_transport_used": False,
    "production_gate2_selection_changed": False,
    "current_artifacts_deleted": False,
}

_TOP_LEVEL_KEYS = {
    "schema_version",
    "policy_version",
    "acceptance_id",
    "acceptance_checksum_ref",
    "normalization_run_id",
    "document_id",
    "original_pdf_artifact_ref",
    "compact_canonical_artifact_ref",
    "input_pdf_sha256",
    "parser_manifest",
    "metrics",
    "artifact_accounting",
    "differential_summary",
    "gates",
    "acceptance_status",
    "approval_required",
    "retention_decision",
    "cleanup_status",
    *_GUARDS,
}


@dataclass(frozen=True)
class PdfNormalizationAcceptanceConfig:
    compact_target_bytes: int = 750_000
    compact_hard_review_bytes: int = 1_000_000
    gzip_level: int = 9
    policy_version: str = PDF_NORMALIZATION_ACCEPTANCE_POLICY_VERSION


class PdfNormalizationAcceptanceFactory:
    def __init__(self, config: PdfNormalizationAcceptanceConfig | None = None) -> None:
        self.config = config or PdfNormalizationAcceptanceConfig()

    def create(self) -> "PdfNormalizationAcceptanceBuilder":
        if self.config.compact_target_bytes <= 0 or self.config.gzip_level not in range(1, 10):
            raise PdfCompactCanonicalError("pdf_acceptance_config_invalid")
        return PdfNormalizationAcceptanceBuilder(self.config)


class PdfNormalizationAcceptanceBuilder:
    def __init__(self, config: PdfNormalizationAcceptanceConfig) -> None:
        self.config = config

    def build(
        self,
        *,
        compact_document: dict[str, Any],
        compact_canonical_artifact_ref: str,
        source_payloads: list[dict[str, Any]],
        source_units: list[dict[str, Any]],
        table_projections: list[dict[str, Any]],
        current_artifact_refs: dict[str, list[str]],
        mapping_validation: dict[str, Any],
        reproducibility_passed: bool,
    ) -> dict[str, Any]:
        compact_validation = PdfCompactCanonicalValidator().validate(compact_document)
        if not compact_validation["passed"]:
            raise PdfCompactCanonicalError("pdf_acceptance_compact_invalid")
        if not compact_canonical_artifact_ref:
            raise PdfCompactCanonicalError("pdf_acceptance_compact_artifact_ref_missing")

        compact_bytes = len(canonical_json_bytes(compact_document))
        compact_gzip_bytes = len(
            gzip.compress(canonical_json_bytes(compact_document), compresslevel=self.config.gzip_level)
        )
        full_payload_bytes, full_payload_gzip = _sizes(source_payloads, self.config.gzip_level)
        source_unit_bytes, source_unit_gzip = _sizes(source_units, self.config.gzip_level)
        table_projection_bytes, table_projection_gzip = _sizes(
            table_projections, self.config.gzip_level
        )
        visible_texts = _visible_page_texts(source_payloads)
        visible_text_bytes = sum(len(value.encode("utf-8")) for value in visible_texts)
        unique_text_bytes = sum(
            len(value.encode("utf-8")) for value in dict.fromkeys(visible_texts)
        )
        duplicate_visible_text_ratio = (
            round(max(visible_text_bytes - unique_text_bytes, 0) / visible_text_bytes, 6)
            if visible_text_bytes
            else 0.0
        )
        coverage = _object(compact_document.get("coverage"))
        accepted_cells = [
            cell
            for table in _dicts(compact_document.get("tables"))
            if table.get("status") == "accepted"
            for cell in compact_table_cells(table)
        ]
        registered_refs = {
            str(item.get("source_value_ref") or "")
            for item in compact_source_evidence(compact_document)
        }
        accounted_refs = {
            str(ref) for cell in accepted_cells for ref in cell.get("source_value_refs") or []
        }
        unaccounted_refs = sorted(accounted_refs - registered_refs)
        unexpected_refs = sorted(registered_refs - accounted_refs)
        artifact_accounting = [
            _artifact_role(
                "original_pdf",
                "permanent_source_evidence",
                [str(compact_document.get("original_pdf_artifact_ref") or "")],
                int(compact_document.get("input_pdf_bytes") or 0),
                int(compact_document.get("input_pdf_bytes") or 0),
                "retain_under_case_source_policy",
            ),
            _artifact_role(
                "compact_canonical",
                "permanent_canonical_normalization",
                [compact_canonical_artifact_ref],
                compact_bytes,
                compact_gzip_bytes,
                "retain",
            ),
            _artifact_role(
                "full_forensic_payload",
                "temporary_parser_working_state_ttl_debug",
                list(current_artifact_refs.get("source_payloads") or []),
                full_payload_bytes,
                full_payload_gzip,
                "retain_while_dual_write_then_ttl_or_delete_in_later_goal",
            ),
            _artifact_role(
                "full_source_units",
                "temporary_parser_working_state_ttl_debug",
                list(current_artifact_refs.get("source_units") or []),
                source_unit_bytes,
                source_unit_gzip,
                "retain_while_dual_write_then_ttl_or_delete_in_later_goal",
            ),
            _artifact_role(
                "table_projections",
                "permanent_during_dual_write_migration",
                list(current_artifact_refs.get("table_projections") or []),
                table_projection_bytes,
                table_projection_gzip,
                "retain_authoritative_for_gate2_during_migration",
            ),
        ]
        provenance_passed = bool(
            _object(compact_document.get("parser_manifest")).get("source_checksum_ref")
        ) and all(
            item.get("source_object_ref")
            and item.get("page_ref")
            and isinstance(item.get("bbox"), list)
            and len(item.get("bbox")) == 4
            and item.get("text_checksum_ref")
            and item.get("value_checksum_ref")
            for item in compact_source_evidence(compact_document)
        )
        required_roles = {
            "original_pdf",
            "compact_canonical",
            "full_forensic_payload",
            "full_source_units",
            "table_projections",
        }
        artifact_classification_passed = (
            {str(item.get("role") or "") for item in artifact_accounting}
            == required_roles
            and _object(compact_document.get("artifact_roles")).get(
                "current_artifacts_deleted"
            )
            is False
        )
        gates = {
            "structural_correctness": _gate(
                compact_validation["passed"],
                [] if compact_validation["passed"] else ["pdf_compact_structural_validation_failed"],
            ),
            "provenance_correctness": _gate(
                provenance_passed,
                [] if provenance_passed else ["pdf_compact_provenance_binding_invalid"],
            ),
            "source_ref_accounting": _gate(
                not unaccounted_refs and not unexpected_refs,
                [
                    *(["pdf_compact_source_refs_unaccounted"] if unaccounted_refs else []),
                    *(["pdf_compact_source_refs_unexpected"] if unexpected_refs else []),
                ],
            ),
            "storage_proportionality": _gate(
                True,
                [],
            ),
            "llm_projection_readiness": _gate(
                mapping_validation.get("passed") is True,
                []
                if mapping_validation.get("passed") is True
                else ["pdf_compact_v0_mapping_validation_failed"],
            ),
            "reproducibility": _gate(
                reproducibility_passed,
                [] if reproducibility_passed else ["pdf_compact_reproducibility_failed"],
            ),
            "artifact_classification": _gate(
                artifact_classification_passed,
                []
                if artifact_classification_passed
                else ["pdf_compact_artifact_classification_invalid"],
            ),
            "cleanup_readiness": _gate(
                True,
                [],
                status="deferred_dual_write_safety",
            ),
        }
        blocked_total = int(coverage.get("tables_blocked_total") or 0)
        result: dict[str, Any] = {
            "schema_version": PDF_NORMALIZATION_ACCEPTANCE_SCHEMA_VERSION,
            "policy_version": self.config.policy_version,
            "acceptance_id": "pdfaccept_"
            + hashlib.sha256(
                canonical_json_bytes(
                    [
                        compact_document.get("canonical_document_checksum_ref"),
                        compact_canonical_artifact_ref,
                        mapping_validation,
                    ]
                )
            ).hexdigest()[:24],
            "acceptance_checksum_ref": None,
            "normalization_run_id": compact_document.get("normalization_run_id"),
            "document_id": compact_document.get("document_ref"),
            "original_pdf_artifact_ref": compact_document.get("original_pdf_artifact_ref"),
            "compact_canonical_artifact_ref": compact_canonical_artifact_ref,
            "input_pdf_sha256": compact_document.get("input_pdf_sha256"),
            "parser_manifest": copy.deepcopy(compact_document.get("parser_manifest") or {}),
            "metrics": {
                "input_pdf_bytes": int(compact_document.get("input_pdf_bytes") or 0),
                "page_count": len(compact_document.get("pages") or []),
                "text_visible_bytes": visible_text_bytes,
                "duplicate_visible_text_ratio": duplicate_visible_text_ratio,
                "full_forensic_json_bytes": full_payload_bytes,
                "full_forensic_gzip_bytes": full_payload_gzip,
                "source_units_json_bytes": source_unit_bytes,
                "source_units_gzip_bytes": source_unit_gzip,
                "table_projections_json_bytes": table_projection_bytes,
                "table_projections_gzip_bytes": table_projection_gzip,
                "compact_json_bytes": compact_bytes,
                "compact_gzip_bytes": compact_gzip_bytes,
                "acceptance_record_core_bytes": 0,
                "intended_permanent_bytes": 0,
                "migration_retained_bytes": (
                    int(compact_document.get("input_pdf_bytes") or 0)
                    + compact_bytes
                    + table_projection_bytes
                ),
                "temporary_working_state_bytes": full_payload_bytes + source_unit_bytes,
                "compact_to_input_ratio": round(
                    compact_bytes / max(int(compact_document.get("input_pdf_bytes") or 0), 1),
                    6,
                ),
                "full_to_compact_ratio": round(full_payload_bytes / max(compact_bytes, 1), 6),
                "visible_text_to_compact_ratio": round(
                    visible_text_bytes / max(compact_bytes, 1), 6
                ),
                "table_candidates_total": int(coverage.get("table_candidates_total") or 0),
                "tables_accepted_total": int(coverage.get("tables_accepted_total") or 0),
                "tables_blocked_total": blocked_total,
                "rows_total": sum(
                    int(item.get("row_count") or 0)
                    for item in _dicts(compact_document.get("tables"))
                ),
                "cells_total": len(accepted_cells),
                "source_refs_registered": len(registered_refs),
                "source_refs_accounted": len(accounted_refs),
                "source_refs_unaccounted": len(unaccounted_refs),
            },
            "artifact_accounting": artifact_accounting,
            "differential_summary": {
                "table_identities_equal": mapping_validation.get("passed") is True,
                "accepted_tables_compared": int(
                    mapping_validation.get("accepted_tables_compared") or 0
                ),
                "blocked_tables_compared": int(
                    mapping_validation.get("blocked_tables_compared") or 0
                ),
                "table_decisions_compared": int(
                    mapping_validation.get("table_decisions_compared") or 0
                ),
                "status_equivalent": mapping_validation.get("status_equivalent") is True,
                "mapping_validator_status": mapping_validation.get("validator_status"),
                "mapping_error_codes": [
                    str(item.get("code") or "")
                    for item in _dicts(mapping_validation.get("errors"))
                ],
                "current_projection_path_authoritative": True,
                "compact_selected_by_gate2": False,
            },
            "gates": gates,
            "acceptance_status": "blocked",
            "approval_required": False,
            "retention_decision": "dual_write_retain_current_and_compact",
            "cleanup_status": "deferred_dual_write_safety",
            **_GUARDS,
        }
        core = copy.deepcopy(result)
        core["metrics"]["acceptance_record_core_bytes"] = 0
        core["metrics"]["intended_permanent_bytes"] = 0
        core.pop("acceptance_checksum_ref", None)
        core_bytes = len(canonical_json_bytes(core))
        result["metrics"]["acceptance_record_core_bytes"] = core_bytes
        result["metrics"]["intended_permanent_bytes"] = (
            int(compact_document.get("input_pdf_bytes") or 0) + compact_bytes + core_bytes
        )
        intended_permanent = int(result["metrics"]["intended_permanent_bytes"])
        result["metrics"]["permanent_artifact_total_bytes"] = intended_permanent
        result["metrics"]["temporary_artifact_total_bytes"] = int(
            result["metrics"]["temporary_working_state_bytes"]
        )
        result["metrics"]["permanent_to_original_ratio"] = round(
            intended_permanent / max(int(compact_document.get("input_pdf_bytes") or 0), 1),
            6,
        )
        result["metrics"]["permanent_to_visible_text_ratio"] = round(
            intended_permanent / max(visible_text_bytes, 1), 6
        )
        storage_passed = intended_permanent <= self.config.compact_target_bytes
        result["gates"]["storage_proportionality"] = _gate(
            storage_passed,
            [] if storage_passed else ["pdf_permanent_envelope_target_exceeded"],
        )
        result["approval_required"] = (
            compact_bytes > self.config.compact_hard_review_bytes or not storage_passed
        )
        non_storage_passed = all(
            item.get("passed") is True
            for key, item in result["gates"].items()
            if key != "storage_proportionality"
        )
        if all(item.get("passed") is True for item in result["gates"].values()):
            result["acceptance_status"] = (
                "accepted_with_explicit_blocked_tables"
                if blocked_total
                else "accepted_complete"
            )
        elif non_storage_passed and result["approval_required"]:
            result["acceptance_status"] = "human_review_required"
        result["acceptance_checksum_ref"] = _acceptance_checksum(result)
        validation = PdfNormalizationAcceptanceValidator().validate(result)
        if not validation["passed"]:
            raise PdfCompactCanonicalError(
                "pdf_acceptance_validation_failed",
                ",".join(item["code"] for item in validation["errors"][:5]),
            )
        return result


class PdfNormalizationAcceptanceValidator:
    def validate(self, value: dict[str, Any]) -> dict[str, Any]:
        errors: list[dict[str, str]] = []
        if set(value) != _TOP_LEVEL_KEYS:
            errors.append(_error("pdf_acceptance_top_level_keys_invalid", "acceptance"))
        if value.get("schema_version") != PDF_NORMALIZATION_ACCEPTANCE_SCHEMA_VERSION:
            errors.append(_error("pdf_acceptance_schema_mismatch", "acceptance"))
        if value.get("policy_version") != PDF_NORMALIZATION_ACCEPTANCE_POLICY_VERSION:
            errors.append(_error("pdf_acceptance_policy_mismatch", "acceptance"))
        if not value.get("original_pdf_artifact_ref") or not value.get(
            "compact_canonical_artifact_ref"
        ):
            errors.append(_error("pdf_acceptance_artifact_ref_missing", "acceptance"))
        for key, expected in _GUARDS.items():
            if value.get(key) is not expected:
                errors.append(_error("pdf_acceptance_guard_failed", key))
        gates = _object(value.get("gates"))
        expected_gates = {
            "structural_correctness",
            "provenance_correctness",
            "source_ref_accounting",
            "storage_proportionality",
            "llm_projection_readiness",
            "reproducibility",
            "artifact_classification",
            "cleanup_readiness",
        }
        if set(gates) != expected_gates:
            errors.append(_error("pdf_acceptance_gate_set_invalid", "gates"))
        expected_pass = all(_object(item).get("passed") is True for item in gates.values())
        status = value.get("acceptance_status")
        if expected_pass != (status in {"accepted_complete", "accepted_with_explicit_blocked_tables"}):
            errors.append(_error("pdf_acceptance_status_gate_mismatch", "acceptance_status"))
        non_storage_passed = all(
            _object(item).get("passed") is True
            for key, item in gates.items()
            if key != "storage_proportionality"
        )
        if status == "human_review_required" and not (
            non_storage_passed
            and _object(gates.get("storage_proportionality")).get("passed") is False
            and value.get("approval_required") is True
        ):
            errors.append(_error("pdf_acceptance_human_review_status_invalid", "acceptance_status"))
        metrics = _object(value.get("metrics"))
        if int(metrics.get("source_refs_unaccounted") or 0) != 0 and status != "blocked":
            errors.append(_error("pdf_acceptance_unaccounted_refs_accepted", "metrics"))
        if int(metrics.get("compact_json_bytes") or 0) <= 0:
            errors.append(_error("pdf_acceptance_compact_size_missing", "metrics"))
        roles = _dicts(value.get("artifact_accounting"))
        required_roles = {
            "original_pdf",
            "compact_canonical",
            "full_forensic_payload",
            "full_source_units",
            "table_projections",
        }
        if {str(item.get("role") or "") for item in roles} != required_roles:
            errors.append(_error("pdf_acceptance_artifact_roles_invalid", "artifact_accounting"))
        if value.get("acceptance_checksum_ref") != _acceptance_checksum(value):
            errors.append(_error("pdf_acceptance_checksum_mismatch", "acceptance"))
        return {
            "schema_version": "broker_reports_pdf_normalization_acceptance_validation_v1",
            "passed": not errors,
            "validator_status": "passed" if not errors else "failed",
            "errors_count": len(errors),
            "errors": errors,
        }


def _artifact_role(
    role: str,
    lifecycle_class: str,
    refs: list[str],
    json_bytes: int,
    gzip_bytes: int,
    target_state: str,
) -> dict[str, Any]:
    return {
        "role": role,
        "lifecycle_class": lifecycle_class,
        "artifact_refs": refs,
        "canonical_json_bytes": json_bytes,
        "gzip_bytes": gzip_bytes,
        "target_state": target_state,
    }


def _gate(passed: bool, reason_codes: list[str], *, status: str | None = None) -> dict[str, Any]:
    return {
        "passed": bool(passed),
        "status": status or ("passed" if passed else "failed"),
        "reason_codes": list(reason_codes),
    }


def _sizes(values: list[dict[str, Any]], gzip_level: int) -> tuple[int, int]:
    payload = canonical_json_bytes(values)
    return len(payload), len(gzip.compress(payload, compresslevel=gzip_level))


def _visible_page_texts(source_payloads: list[dict[str, Any]]) -> list[str]:
    result: list[str] = []
    for payload in source_payloads:
        projection = _object(payload.get("pdf_text_layer_projection"))
        for page in _dicts(projection.get("page_inventory")):
            result.append(str(page.get("text") or ""))
    return result


def _acceptance_checksum(value: dict[str, Any]) -> str:
    material = copy.deepcopy(value)
    material.pop("acceptance_checksum_ref", None)
    return "pdfacceptchk_" + hashlib.sha256(canonical_json_bytes(material)).hexdigest()


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _dicts(value: Any) -> list[dict[str, Any]]:
    return [item for item in value or [] if isinstance(item, dict)] if isinstance(value, list) else []


def _error(code: str, subject: Any) -> dict[str, str]:
    return {"code": code, "subject": str(subject or "")}
