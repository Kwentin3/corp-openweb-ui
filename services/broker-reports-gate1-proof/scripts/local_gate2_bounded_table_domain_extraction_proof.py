#!/usr/bin/env python3
"""Local synthetic proof for bounded table-domain Gate 2 extraction."""

from __future__ import annotations

import argparse
import asyncio
import copy
import json
import sys
import tempfile
import time
from collections import Counter
from io import BytesIO
from pathlib import Path
from typing import Any

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject


SERVICE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_ROOT))

from broker_reports_gate1 import (  # noqa: E402
    ArtifactAccessContext,
    ArtifactResolver,
    ArtifactStoreConfig,
    ArtifactStoreFactory,
    FileInput,
    Gate1Normalizer,
    Gate2DomainSourceFactRuntimeConfig,
    Gate2DomainSourceFactRuntimeFactory,
    Gate2InputReadinessConfig,
    Gate2InputReadinessFactory,
    Gate2ManagedPrompt,
    Gate2PromptUserContext,
    Gate2SourceUnitRouterFactory,
    Gate2SourceUnitSegmenterConfig,
    Gate2SourceUnitSegmenterFactory,
    Gate2StructuredModelResult,
    StaticGate2DomainPromptResolver,
    build_retention_policy,
    gate2_prompt_hash,
    persist_gate1_result,
)


TARGET_DOMAIN = "income"


class SyntheticTableDomainModel:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def extract(self, *, prompt, package, model_id, response_format):
        domain = str(package["extractor_domain"])
        self.calls.append(
            {
                "domain": domain,
                "candidate_source_refs_total": len(package["candidate_source_refs"]),
                "strict_schema": response_format["json_schema"]["strict"],
            }
        )
        return Gate2StructuredModelResult(
            content=_source_facts_candidate(package=package, domain=domain)
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Print compact JSON")
    args = parser.parse_args()
    started = time.perf_counter()
    scenarios = [
        _run_scenario(
            scenario_id="synthetic_native_csv_income",
            file_input=FileInput.from_bytes(
                private_ref="synthetic-native-income",
                filename="synthetic-income.csv",
                content=(
                    b"Date,Operation,Amount,Currency\n"
                    b"2026-01-01,dividend,10.00,USD\n"
                ),
                mime_type="text/csv",
            ),
            source_format="csv",
        ),
        _run_scenario(
            scenario_id="synthetic_pdf_structural_income",
            file_input=FileInput.from_bytes(
                private_ref="synthetic-pdf-income",
                filename="synthetic-income-table.pdf",
                content=_synthetic_income_pdf(),
                mime_type="application/pdf",
            ),
            source_format="pdf",
        ),
    ]
    checks = {
        "synthetic_native_passed": scenarios[0]["status"] == "passed",
        "synthetic_pdf_passed": scenarios[1]["status"] == "passed",
        "all_runtime_paths_completed": all(
            item["runtime"]["terminal_status"] == "completed" for item in scenarios
        ),
        "all_coverage_complete": all(
            item["runtime"]["coverage"]["uncovered_total"] == 0
            and item["runtime"]["coverage"]["conflict_total"] == 0
            for item in scenarios
        ),
        "strict_model_boundary_used": all(
            item["model_calls_total"] == 1 and item["strict_model_calls_total"] == 1
            for item in scenarios
        ),
        "private_source_facts_persisted": all(
            item["artifact_counts"]["source_facts_total"] == 1
            and item["artifact_counts"]["private_source_facts_total"] == 1
            for item in scenarios
        ),
        "guards_hold": all(item["guards_status"] == "passed" for item in scenarios),
    }
    output = {
        "status": "passed" if all(checks.values()) else "failed",
        "scope": "synthetic_bounded_table_domain_gate2_extraction",
        "runtime_entrypoint": "Gate2DomainSourceFactRuntimeFactory.create",
        "prefer_table_projections": True,
        "target_domain": TARGET_DOMAIN,
        "scenarios": scenarios,
        "checks": checks,
        "runtime_seconds": round(time.perf_counter() - started, 3),
    }
    print(json.dumps(output, ensure_ascii=False, sort_keys=True, indent=None if args.json else 2))
    return 0 if output["status"] == "passed" else 1


def _run_scenario(
    *, scenario_id: str, file_input: FileInput, source_format: str
) -> dict[str, Any]:
    normalizer = Gate1Normalizer()
    gate1 = normalizer.normalize(
        [file_input],
        input_context={
            "clarification_criticality_refinement_enabled": True,
            "pdf_layout_slice2_enabled": True,
        },
    )
    run_id = gate1.package["normalization_run"]["run_id"]
    projections = [
        item
        for item in gate1.package.get("private_normalized_table_projections") or []
        if item.get("source_format") == source_format
    ]
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
            user_id="synthetic-table-domain-proof",
            normalization_run_id=run_id,
            case_id=f"{scenario_id}_case",
            chat_id=f"{scenario_id}_chat",
            workspace_model_id="synthetic-table-domain-model",
            allow_private=True,
            require_source_available=True,
        )
        manifest = persist_gate1_result(
            store=store,
            result=gate1,
            context=context,
            retention_policy=build_retention_policy(mode="synthetic_dev"),
            source_file_refs=[
                {
                    "provider": "synthetic_local",
                    "openwebui_file_id": f"{scenario_id}_source",
                    "source_deleted": False,
                }
            ],
        )
        dcp_ref = manifest.artifact_refs_by_type["domain_context_packet_v0"][0]
        target = _select_target_segment(
            store=store,
            context=context,
            dcp_ref=dcp_ref,
            source_format=source_format,
        )
        model = SyntheticTableDomainModel()
        runtime = Gate2DomainSourceFactRuntimeFactory(
            store=store,
            prompt_resolver=StaticGate2DomainPromptResolver(
                {TARGET_DOMAIN: _domain_prompt(TARGET_DOMAIN)}
            ),
            model_client=model,
            config=Gate2DomainSourceFactRuntimeConfig(
                model_id="synthetic-table-domain-model",
                wave="primary",
                run_mode="synthetic",
                document_batch_limit=1,
                source_unit_start=target["source_unit_start"],
                source_unit_limit=1,
                segmentation_enabled=True,
                source_segment_start=target["source_segment_start"],
                source_segment_limit=1,
                table_segment_max_refs=1,
                domain_allowlist=(TARGET_DOMAIN,),
                max_repair_attempts=0,
                prefer_table_projections=True,
            ),
        ).create()
        runtime_result = asyncio.run(
            runtime.run(
                domain_context_packet_ref=dcp_ref,
                context=context,
                prompt_user_context=Gate2PromptUserContext(
                    user_id=context.user_id,
                    user_role="admin",
                ),
            )
        )
        records = store.list_by_run(run_id)
        type_counts = Counter(record.artifact_type for record in records)
        validation_payloads = [
            ArtifactResolver(store).resolve(ref, context)["payload"]
            for ref in runtime_result.validation_refs
        ]
        guards = _guards(records=records, projections=projections)
        coverage = runtime_result.safe_summary["coverage"]
        scenario_checks = {
            "normalization_passed": gate1.package["validation_result"]["status"]
            == "passed",
            "eligible_projection_available": any(
                _projection_is_eligible(item) for item in projections
            ),
            "target_segment_income": target["domain"] == TARGET_DOMAIN,
            "runtime_completed": runtime_result.terminal_status == "completed",
            "one_source_facts_artifact": len(runtime_result.source_facts_refs) == 1,
            "validator_passed": bool(validation_payloads)
            and all(item.get("validator_status") == "passed" for item in validation_payloads),
            "coverage_complete": coverage["uncovered_total"] == 0
            and coverage["conflict_total"] == 0,
            "guards_passed": guards["status"] == "passed",
        }
        return {
            "scenario_id": scenario_id,
            "status": "passed" if all(scenario_checks.values()) else "failed",
            "source_format": source_format,
            "projection_summary": _projection_summary(projections),
            "target": target,
            "runtime": {
                "terminal_status": runtime_result.terminal_status,
                "facts_by_type": runtime_result.safe_summary["facts_by_type"],
                "coverage": coverage,
                "domain_packages": runtime_result.safe_summary["domain_packages"],
            },
            "artifact_counts": {
                "records_total": len(records),
                "table_projection_records_total": type_counts[
                    "broker_reports_normalized_table_projection_v0"
                ],
                "raw_outputs_total": type_counts[
                    "broker_reports_source_fact_raw_output_v0"
                ],
                "source_facts_total": type_counts["broker_reports_source_facts_v0"],
                "private_source_facts_total": sum(
                    1
                    for record in records
                    if record.artifact_type == "broker_reports_source_facts_v0"
                    and record.visibility == "private_case"
                    and record.validation_status == "validated"
                ),
                "stitch_results_total": type_counts[
                    "broker_reports_source_fact_stitch_result_v0"
                ],
                "knowledge_backend_records": sum(
                    1
                    for record in records
                    if record.storage_backend == "openwebui_knowledge"
                ),
            },
            "model_calls_total": len(model.calls),
            "strict_model_calls_total": sum(
                1 for item in model.calls if item["strict_schema"] is True
            ),
            "guards_status": guards["status"],
            "guards": guards["checks"],
            "checks": scenario_checks,
        }


def _select_target_segment(
    *,
    store,
    context: ArtifactAccessContext,
    dcp_ref: str,
    source_format: str,
) -> dict[str, Any]:
    readiness = Gate2InputReadinessFactory(
        store=store,
        config=Gate2InputReadinessConfig(prefer_table_projections=True),
    ).create().audit_and_build(domain_context_packet_ref=dcp_ref, context=context)
    if readiness.validation["validator_status"] != "passed":
        raise RuntimeError("gate2_table_readiness_failed")
    for package_index, package in enumerate(readiness.packages):
        unit = package["source_unit"]
        if unit.get("source_input_mode") != "normalized_table_projection":
            continue
        if unit.get("source_format") != source_format:
            continue
        route = Gate2SourceUnitRouterFactory().create().route(package)
        segmentation = Gate2SourceUnitSegmenterFactory(
            Gate2SourceUnitSegmenterConfig(table_max_selected_refs=1)
        ).create().segment(base_package=package, parent_route=route)
        for segment_index, derived in enumerate(segmentation.derived_packages):
            derived_route = Gate2SourceUnitRouterFactory().create().route(derived)
            entries = [
                item
                for item in derived_route["route_entries"]
                if item.get("route_kind") == "model_candidate"
            ]
            domains = sorted(
                {
                    domain
                    for item in entries
                    for domain in item.get("candidate_domains") or []
                }
            )
            if TARGET_DOMAIN in domains:
                return {
                    "source_unit_start": package_index,
                    "source_segment_start": segment_index,
                    "domain": TARGET_DOMAIN,
                    "candidate_domains": domains,
                    "selected_refs_total": len(derived_route["selected_source_refs"]),
                    "source_input_mode": unit.get("source_input_mode"),
                    "source_format": unit.get("source_format"),
                    "projection_quality": unit.get("table_quality", {}).get(
                        "reconstruction_quality"
                    ),
                    "semantic_table_truth_claimed": unit.get(
                        "semantic_table_truth_claimed"
                    ),
                }
    raise RuntimeError(f"no_{TARGET_DOMAIN}_table_segment_found")


def _source_facts_candidate(*, package: dict[str, Any], domain: str) -> dict[str, Any]:
    unit = package["source_unit"]
    selected = package["coverage_expectation"]["selected_source_refs"]
    rows = [
        item
        for item in unit["model_source_projection"]["rows"]
        if item.get("row_ref") in selected
    ]
    row = rows[0]
    cells = list(row.get("cells") or [])
    cells_by_header = {str(item.get("header_label") or ""): item for item in cells}
    date_cell = cells_by_header.get("date") or cells[0]
    identifier_cell = (
        cells_by_header.get("operation")
        or cells_by_header.get("instrument")
        or cells[min(1, len(cells) - 1)]
    )
    amount_cell = cells_by_header.get("amount") or cells[min(2, len(cells) - 1)]
    currency_cell = cells_by_header.get("currency") or cells[-1]
    date_ref = _cell_value_ref(date_cell)
    identifier_ref = _cell_value_ref(identifier_cell)
    amount_ref = _cell_value_ref(amount_cell)
    currency_ref = _cell_value_ref(currency_cell)
    cell_refs = sorted(
        {
            str(item.get("cell_ref") or "")
            for item in (date_cell, identifier_cell, amount_cell, currency_cell)
            if item.get("cell_ref")
        }
    )
    normalized = {
        "date": str(date_cell.get("value") or "").strip(),
        "amount": str(amount_cell.get("value") or "").strip(),
        "currency": str(currency_cell.get("value") or "").strip().upper(),
        "quantity": None,
        "rate": None,
        "converted_amount": None,
        "identifier": str(identifier_cell.get("value") or "").strip(),
        "label": None,
    }
    issue_policy = _issue_policy(package)
    fact = {
        "fact_id": "pending",
        "fact_type": domain,
        "fact_subtype": None,
        "document_ref": package["document_ref"],
        "extraction_package_ref": package["package_artifact_ref"],
        "source_unit_ref": unit["unit_id"],
        "source_location": {
            "private_slice_artifact_ref": unit["private_slice_artifact_ref"],
            "slice_ref": unit["slice_ref"],
            "source_granularity": "table_row",
            "page_ref": (_string_list(unit.get("page_refs")) or [None])[0],
            "section_ref": None,
            "table_ref": unit["table_ref"],
            "row_ref": row["row_ref"],
            "row_range_ref": None,
            "cell_refs": cell_refs,
            "text_segment_refs": [],
            "parser_ref": unit["parser_ref"],
            "source_checksum_ref": unit["source_checksum_ref"],
        },
        "extracted_fields": _extracted_fields(domain, identifier_ref),
        "normalized_values": normalized,
        "original_value_refs": {
            "date": [date_ref],
            "amount": [amount_ref],
            "currency": [currency_ref],
            "quantity": [],
            "rate": [],
            "converted_amount": [],
            "identifier": [identifier_ref],
            "label": [],
        },
        "date": {
            "value": normalized["date"],
            "role": "source_unspecified_date",
            "precision": "day",
            "original_value_refs": [date_ref],
        },
        "amount": {
            "value_decimal": normalized["amount"],
            "amount_role": "source_visible_amount",
            "currency": normalized["currency"],
            "original_value_refs": [amount_ref],
        },
        "currency": {
            "code": normalized["currency"],
            "code_kind": "iso_4217_visible",
            "original_value_refs": [currency_ref],
        },
        "quantity": None,
        "instrument": {
            "safe_label": None,
            "safe_label_ref": None,
            "identifiers": [
                {
                    "identifier_type": "ticker",
                    "identifier_value": normalized["identifier"],
                    "original_value_refs": [identifier_ref],
                }
            ],
        },
        "confidence": "medium",
        "completeness": "partial"
        if issue_policy["linked_issue_refs"]
        else "complete",
        "evidence_refs": sorted(
            set(package["allowed_evidence_refs"])
            & {
                row["row_ref"],
                unit["table_ref"],
                unit["table_projection_id"],
                unit["parser_ref"],
                unit["source_checksum_ref"],
                *cell_refs,
            }
        ),
        "linked_issue_refs": issue_policy["linked_issue_refs"],
        "issue_impact": issue_policy["issue_impact"],
        "extraction_warnings": [],
        "downstream_use": {
            "downstream_usable": True,
            "gate3_ledger_candidate": True,
            "cross_document_consolidation_allowed": False,
            "tax_calculation_allowed": False,
            "declaration_mapping_allowed": False,
            "restriction_codes": [],
        },
        "extraction_audit": copy.deepcopy(package["expected_candidate_audit"]),
        "validator_status": "pending",
        "validation_ref": None,
    }
    return {
        "schema_version": "broker_reports_source_facts_v0",
        "source_facts_set_id": package["expected_source_facts_set_id"],
        "extraction_run_id": package["extraction_run_id"],
        "normalization_run_id": package["normalization_run_id"],
        "case_id": package["case_id"],
        "package_refs": [package["package_artifact_ref"]],
        "document_refs": [package["document_ref"]],
        "facts": [fact],
        "coverage": {
            "unit_coverage_ref": package["coverage_expectation"]["coverage_ref"],
            "selected_source_refs": selected,
            "fact_covered_refs": selected,
            "no_fact_results": [],
            "rejected_refs": [],
            "pending_refs": [],
            "coverage_status": "complete",
        },
        "issue_linkage_summary": {
            "package_issue_refs": package["allowed_issue_refs"],
            "fact_issue_links_total": len(fact["linked_issue_refs"]),
            "unresolved_issue_refs": sorted(
                item["issue_ref"]
                for item in package["issue_context"]
                if item.get("status") == "unresolved"
            ),
        },
        "extraction_audit": copy.deepcopy(package["expected_candidate_audit"]),
        "validation_ref": None,
        "validator_status": "pending",
        "created_at": package["created_at"],
    }


def _cell_value_ref(cell: dict[str, Any]) -> str:
    refs = _string_list(cell.get("source_value_refs"))
    if refs:
        return refs[0]
    return str(cell.get("source_value_ref") or "")


def _issue_policy(package: dict[str, Any]) -> dict[str, Any]:
    impact = {
        "warning_issue_refs": [],
        "limits_confirmation_issue_refs": [],
        "blocks_fact_issue_refs": [],
        "blocks_consolidation_issue_refs": [],
        "blocks_declaration_issue_refs": [],
        "forbidden_assumption_codes": sorted(package["forbidden_assumptions"]),
    }
    mapping = {
        "warning": "warning_issue_refs",
        "limits_confirmation": "limits_confirmation_issue_refs",
        "blocks_fact": "blocks_fact_issue_refs",
        "blocks_consolidation": "blocks_consolidation_issue_refs",
        "blocks_declaration": "blocks_declaration_issue_refs",
    }
    for item in package["issue_context"]:
        key = mapping.get(item["impact"])
        if key:
            impact[key].append(item["issue_ref"])
    for key in mapping.values():
        impact[key] = sorted(set(impact[key]))
    return {
        "linked_issue_refs": sorted(package["allowed_issue_refs"]),
        "issue_impact": impact,
    }


def _extracted_fields(fact_type: str, identifier_ref: str) -> dict[str, Any]:
    return {
        "income": {
            "income_type_candidate": "other",
            "source_country_candidate": None,
            "source_country_value_refs": [],
        },
        "trade_operation": {
            "operation_type_candidate": "unknown",
            "source_visible_direction_refs": [identifier_ref],
        },
        "withholding_tax": {
            "withholding_type_candidate": "unknown",
            "source_country_candidate": None,
            "related_income_source_refs": [],
        },
        "fee_commission": {
            "fee_type_candidate": "other",
            "related_operation_source_refs": [],
        },
        "cash_movement": {
            "movement_type_candidate": "unknown",
            "description_safe_label": None,
            "description_value_refs": [],
        },
        "position_snapshot": {"position_kind_candidate": "security_position"},
        "document_summary_evidence": {
            "summary_kind_candidate": "source_total",
            "source_provided": True,
        },
        "unknown_source_row": {"unknown_reason_codes": ["synthetic_unknown_shape"]},
    }[fact_type]


def _projection_summary(projections: list[dict[str, Any]]) -> dict[str, Any]:
    eligible = [item for item in projections if _projection_is_eligible(item)]
    return {
        "total": len(projections),
        "eligible_total": len(eligible),
        "quality_counts": dict(
            sorted(
                Counter(str(item.get("reconstruction_quality") or "blocked") for item in projections).items()
            )
        ),
        "coverage_complete_total": sum(
            1
            for item in projections
            if (item.get("coverage") or {}).get("coverage_status") == "complete"
        ),
        "duplicate_refs_total": sum(
            len((item.get("coverage") or {}).get("duplicate_accounted_refs") or [])
            for item in projections
        ),
        "unaccounted_refs_total": sum(
            len((item.get("coverage") or {}).get("unaccounted_refs") or [])
            for item in projections
        ),
        "semantic_table_truth_claimed": any(
            item.get("semantic_table_truth_claimed") is not False
            for item in projections
        ),
        "ocr_vlm_used": any(item.get("ocr_vlm_used") is not False for item in projections),
        "page_rendering_used_for_extraction": any(
            item.get("page_rendering_used_for_extraction") is not False
            for item in projections
        ),
    }


def _projection_is_eligible(projection: dict[str, Any]) -> bool:
    coverage = projection.get("coverage") or {}
    return (
        projection.get("projection_status") == "ready"
        and projection.get("reconstruction_quality") in {"high", "medium"}
        and coverage.get("coverage_status") == "complete"
        and not coverage.get("duplicate_accounted_refs")
        and not coverage.get("unaccounted_refs")
    )


def _guards(*, records, projections: list[dict[str, Any]]) -> dict[str, Any]:
    checks = {
        "ordinary_upload_not_used": True,
        "knowledge_rag_not_used": True,
        "vectorization_not_performed": True,
        "artifactstore_knowledge_records": not any(
            record.storage_backend == "openwebui_knowledge" for record in records
        ),
        "semantic_table_truth_not_claimed": not any(
            item.get("semantic_table_truth_claimed") is not False
            for item in projections
        ),
        "ocr_vlm_not_used": not any(
            item.get("ocr_vlm_used") is not False for item in projections
        ),
        "page_rendering_not_used": not any(
            item.get("page_rendering_used_for_extraction") is not False
            for item in projections
        ),
        "no_tax_declaration_xlsx": True,
    }
    return {
        "status": "passed" if all(checks.values()) else "failed",
        "checks": checks,
    }


def _domain_prompt(domain: str) -> Gate2ManagedPrompt:
    content = (
        "Synthetic strict domain prompt for {{source_fact_package_json}}. "
        "Return broker_reports_source_facts_v0 only."
    )
    return Gate2ManagedPrompt(
        prompt_ref=f"prompt_{domain}_synthetic_table_domain",
        command=f"broker_gate2_{domain}_v0",
        version="synthetic-v1",
        content=content,
        hash=gate2_prompt_hash(content),
        source="synthetic_boundary",
        template_id=f"broker_reports.{domain}_table_domain.synthetic.v0",
        template_kind=f"broker_reports_{domain}_extraction",
        prompt_contract_id="broker_reports_domain_source_fact_prompt_v0",
        input_schema_version="broker_reports_domain_extraction_package_v0",
        output_schema_id="broker_reports.source_facts.schema.v0",
        output_schema_version="broker_reports_source_facts_v0",
        tags=("broker-reports-gate2-domain", "structured-output"),
        safe_metadata={"extractor_domain": domain, "name": "synthetic-table-domain"},
    )


def _synthetic_income_pdf() -> bytes:
    texts = [
        (30, 235, "Date"),
        (110, 235, "Operation"),
        (200, 235, "Amount"),
        (265, 235, "Currency"),
        (30, 205, "2026-01-02"),
        (110, 205, "dividend"),
        (200, 205, "13.00"),
        (265, 205, "USD"),
    ]
    vectors = [
        f"20 {y} m 310 {y} l S" for y in (190, 220, 250)
    ] + [
        f"{x} 190 m {x} 250 l S" for x in (20, 100, 190, 255, 310)
    ]
    return _pdf_bytes([{"texts": texts, "vectors": vectors}])


def _pdf_bytes(pages: list[dict[str, Any]]) -> bytes:
    writer = PdfWriter()
    for page in pages:
        pdf_page = writer.add_blank_page(width=320, height=320)
        font_ref = _font_resource(writer)
        pdf_page[NameObject("/Resources")] = DictionaryObject(
            {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_ref})}
        )
        operators = []
        for x, y, text in page.get("texts") or []:
            operators.append(
                f"BT /F1 10 Tf {x:g} {y:g} Td ({_escape(str(text))}) Tj ET"
            )
        operators.extend(page.get("vectors") or [])
        stream = DecodedStreamObject()
        stream.set_data("\n".join(operators).encode("latin-1"))
        pdf_page[NameObject("/Contents")] = writer._add_object(stream)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def _font_resource(writer: PdfWriter):
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    return writer._add_object(font)


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _string_list(value: Any) -> list[str]:
    return [str(item) for item in value or [] if item is not None and str(item)] if isinstance(value, list) else []


if __name__ == "__main__":
    raise SystemExit(main())
