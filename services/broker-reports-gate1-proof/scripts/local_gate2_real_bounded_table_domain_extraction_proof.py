#!/usr/bin/env python3
"""Local real-source bounded table-domain Gate 2 extraction proof.

The script prints safe aggregates only. Raw model outputs and accepted source
facts are persisted only inside a temporary private ArtifactStore.
"""

from __future__ import annotations

import argparse
import asyncio
import copy
import json
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path
from typing import Any


SERVICE_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(SERVICE_ROOT))
sys.path.insert(0, str(SCRIPTS_ROOT))

from broker_reports_gate1 import (  # noqa: E402
    ArtifactAccessContext,
    ArtifactResolver,
    ArtifactStoreConfig,
    ArtifactStoreFactory,
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
from live_case_group_process_false_gate1_run import (  # noqa: E402
    DEFAULT_CASE_GROUPS,
    DEFAULT_CASE_GROUP_ID,
    DEFAULT_PRIVATE_REGISTRY,
    DEFAULT_SAFE_SOURCE_REGISTRY,
    _resolve_case_group_sources,
)
from local_case_group_pdf_text_layer_slice1_proof import (  # noqa: E402
    _file_input,
    _repo_path,
)


TARGET_DOMAIN = "unknown_source_row"
DEFAULT_TARGETS = (
    {
        "scenario_id": "real_native_html_unknown_source_row",
        "source_index": 12,
        "projection_source_format": "html",
    },
    {
        "scenario_id": "real_pdf_structural_unknown_source_row",
        "source_index": 11,
        "projection_source_format": "pdf",
    },
)


class UnknownSourceRowModel:
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
        if domain != TARGET_DOMAIN:
            raise RuntimeError("real_proof_domain_widening_forbidden")
        return Gate2StructuredModelResult(
            content=_unknown_source_row_candidate(package=package)
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Print compact JSON")
    args = parser.parse_args()
    started = time.perf_counter()
    sources = _resolve_case_group_sources(
        case_group_id=DEFAULT_CASE_GROUP_ID,
        private_registry_path=_repo_path(DEFAULT_PRIVATE_REGISTRY),
        safe_source_registry_path=_repo_path(DEFAULT_SAFE_SOURCE_REGISTRY),
        case_groups_path=_repo_path(DEFAULT_CASE_GROUPS),
    )
    scenarios = [
        _run_scenario(sources=sources, **target) for target in DEFAULT_TARGETS
    ]
    checks = {
        "real_native_passed": scenarios[0]["status"] == "passed",
        "real_pdf_passed": scenarios[1]["status"] == "passed",
        "all_runtime_paths_completed": all(
            item["runtime"]["terminal_status"] == "completed" for item in scenarios
        ),
        "all_coverage_complete": all(
            int(item["runtime"]["coverage"].get("uncovered_total") or 0) == 0
            and int(item["runtime"]["coverage"].get("conflict_total") or 0) == 0
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
        "scope": "real_bounded_table_domain_gate2_extraction",
        "case_group_id": DEFAULT_CASE_GROUP_ID,
        "runtime_entrypoint": "Gate2DomainSourceFactRuntimeFactory.create",
        "prefer_table_projections": True,
        "target_domain": TARGET_DOMAIN,
        "scenarios": scenarios,
        "checks": checks,
        "runtime_seconds": round(time.perf_counter() - started, 3),
    }
    print(
        json.dumps(
            output,
            ensure_ascii=False,
            sort_keys=True,
            indent=None if args.json else 2,
        )
    )
    return 0 if output["status"] == "passed" else 1


def _run_scenario(
    *,
    sources: dict[str, Any],
    scenario_id: str,
    source_index: int,
    projection_source_format: str,
) -> dict[str, Any]:
    source = sources["files"][source_index]
    normalizer = Gate1Normalizer()
    gate1 = normalizer.normalize(
        [_file_input(source, source_index + 1)],
        input_context={
            "clarification_criticality_refinement_enabled": True,
            "pdf_layout_slice2_enabled": True,
        },
    )
    run_id = gate1.package["normalization_run"]["run_id"]
    projections = [
        item
        for item in gate1.package.get("private_normalized_table_projections") or []
        if item.get("source_format") == projection_source_format
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
            user_id="real-table-domain-proof",
            normalization_run_id=run_id,
            case_id=f"{scenario_id}_case",
            chat_id=f"{scenario_id}_chat",
            workspace_model_id="real-table-domain-local-proof-model",
            allow_private=True,
            require_source_available=True,
        )
        manifest = persist_gate1_result(
            store=store,
            result=gate1,
            context=context,
            retention_policy=build_retention_policy(
                mode="customer_approved_test", explicit=True
            ),
        )
        dcp_ref = manifest.artifact_refs_by_type["domain_context_packet_v0"][0]
        target = _select_target_segment(
            store=store,
            context=context,
            dcp_ref=dcp_ref,
            projection_source_format=projection_source_format,
        )
        model = UnknownSourceRowModel()
        runtime = Gate2DomainSourceFactRuntimeFactory(
            store=store,
            prompt_resolver=StaticGate2DomainPromptResolver(
                {TARGET_DOMAIN: _domain_prompt(TARGET_DOMAIN)}
            ),
            model_client=model,
            config=Gate2DomainSourceFactRuntimeConfig(
                model_id="real-table-domain-local-proof-model",
                wave="all",
                run_mode="customer",
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
            "target_segment_unknown_source_row": target["domain"] == TARGET_DOMAIN,
            "runtime_completed": runtime_result.terminal_status == "completed",
            "one_source_facts_artifact": len(runtime_result.source_facts_refs) == 1,
            "validator_passed": bool(validation_payloads)
            and all(
                item.get("validator_status") == "passed"
                for item in validation_payloads
            ),
            "coverage_complete": int(coverage.get("uncovered_total") or 0) == 0
            and int(coverage.get("conflict_total") or 0) == 0,
            "guards_passed": guards["status"] == "passed",
        }
        return {
            "scenario_id": scenario_id,
            "status": "passed" if all(scenario_checks.values()) else "failed",
            "source_index": source_index,
            "source_container_format": source.get("container_format"),
            "projection_source_format": projection_source_format,
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
                "source_facts_total": type_counts[
                    "broker_reports_source_facts_v0"
                ],
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
    projection_source_format: str,
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
        if unit.get("source_format") != projection_source_format:
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
            if TARGET_DOMAIN not in domains:
                continue
            selected_refs = derived_route["selected_source_refs"]
            rows = _selected_rows(derived["source_unit"], selected_refs)
            cell_refs = sorted(
                {
                    str(cell.get("cell_ref") or "")
                    for row in rows
                    for cell in row.get("cells") or []
                    if cell.get("cell_ref")
                }
            )
            source_value_refs = sorted(
                {
                    ref
                    for row in rows
                    for cell in row.get("cells") or []
                    for ref in _cell_source_value_refs(cell)
                }
            )
            return {
                "source_unit_start": package_index,
                "source_segment_start": segment_index,
                "domain": TARGET_DOMAIN,
                "candidate_domains": domains,
                "selected_refs_total": len(selected_refs),
                "selected_row_refs_total": len(rows),
                "selected_cell_refs_total": len(cell_refs),
                "selected_source_value_refs_total": len(source_value_refs),
                "source_input_mode": unit.get("source_input_mode"),
                "source_format": unit.get("source_format"),
                "projection_quality": unit.get("table_quality", {}).get(
                    "reconstruction_quality"
                ),
                "semantic_table_truth_claimed": unit.get(
                    "semantic_table_truth_claimed"
                ),
                "derived_package_size_bytes": len(
                    json.dumps(derived, ensure_ascii=False, sort_keys=True).encode(
                        "utf-8"
                    )
                ),
            }
    raise RuntimeError(f"no_{TARGET_DOMAIN}_{projection_source_format}_table_segment_found")


def _unknown_source_row_candidate(*, package: dict[str, Any]) -> dict[str, Any]:
    unit = package["source_unit"]
    selected = package["coverage_expectation"]["selected_source_refs"]
    rows = _selected_rows(unit, selected)
    row = rows[0]
    value_cell = _first_value_cell(row)
    identifier_ref = _cell_source_value_refs(value_cell)[0]
    identifier_value = str(value_cell.get("value") or "").strip()
    cell_refs = sorted(
        {
            str(cell.get("cell_ref") or "")
            for cell in row.get("cells") or []
            if cell.get("cell_ref")
        }
    )
    row_range_ref = row.get("row_range_ref")
    allowed_evidence = set(package["allowed_evidence_refs"])
    evidence_refs = sorted(
        allowed_evidence
        & {
            str(row.get("row_ref") or ""),
            str(row_range_ref or ""),
            str(unit.get("table_ref") or ""),
            str(unit.get("table_projection_id") or ""),
            str(unit.get("parser_ref") or ""),
            str(unit.get("source_checksum_ref") or ""),
            *cell_refs,
        }
    )
    if row_range_ref and str(row_range_ref) not in allowed_evidence:
        row_range_ref = None
    issue_policy = _issue_policy(package)
    blocked = bool(issue_policy["issue_impact"]["blocks_fact_issue_refs"])
    fact = {
        "fact_id": "pending",
        "fact_type": TARGET_DOMAIN,
        "fact_subtype": None,
        "document_ref": package["document_ref"],
        "extraction_package_ref": package["package_artifact_ref"],
        "source_unit_ref": unit["unit_id"],
        "source_location": {
            "private_slice_artifact_ref": unit["private_slice_artifact_ref"],
            "slice_ref": unit["slice_ref"],
            "source_granularity": "table_row",
            "page_ref": None,
            "section_ref": None,
            "table_ref": unit["table_ref"],
            "row_ref": row["row_ref"],
            "row_range_ref": row_range_ref,
            "cell_refs": cell_refs,
            "text_segment_refs": [],
            "parser_ref": unit["parser_ref"],
            "source_checksum_ref": unit["source_checksum_ref"],
        },
        "extracted_fields": {
            "unknown_reason_codes": ["bounded_real_table_row_requires_later_domain_review"]
        },
        "normalized_values": {
            "date": None,
            "amount": None,
            "currency": None,
            "quantity": None,
            "rate": None,
            "converted_amount": None,
            "identifier": identifier_value,
            "label": None,
        },
        "original_value_refs": {
            "date": [],
            "amount": [],
            "currency": [],
            "quantity": [],
            "rate": [],
            "converted_amount": [],
            "identifier": [identifier_ref],
            "label": [],
        },
        "date": None,
        "amount": None,
        "currency": None,
        "quantity": None,
        "instrument": {
            "safe_label": None,
            "safe_label_ref": None,
            "identifiers": [
                {
                    "identifier_type": "unknown_visible_identifier",
                    "identifier_value": identifier_value,
                    "original_value_refs": [identifier_ref],
                }
            ],
        },
        "confidence": "low",
        "completeness": "blocked" if blocked else "uncertain",
        "evidence_refs": evidence_refs,
        "linked_issue_refs": issue_policy["linked_issue_refs"],
        "issue_impact": issue_policy["issue_impact"],
        "extraction_warnings": [
            "bounded_real_table_row_preserved_as_unknown_source_row"
        ],
        "downstream_use": {
            "downstream_usable": False,
            "gate3_ledger_candidate": False,
            "cross_document_consolidation_allowed": False,
            "tax_calculation_allowed": False,
            "declaration_mapping_allowed": False,
            "restriction_codes": ["unknown_source_row"],
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


def _selected_rows(unit: dict[str, Any], selected_refs: list[str]) -> list[dict[str, Any]]:
    selected = set(selected_refs)
    rows = [
        item
        for item in (unit.get("model_source_projection") or {}).get("rows") or []
        if item.get("row_ref") in selected
    ]
    if not rows:
        raise RuntimeError("real_proof_selected_row_missing")
    return rows


def _first_value_cell(row: dict[str, Any]) -> dict[str, Any]:
    for cell in row.get("cells") or []:
        refs = _cell_source_value_refs(cell)
        if refs:
            return cell
    raise RuntimeError("real_proof_selected_row_value_ref_missing")


def _cell_source_value_refs(cell: dict[str, Any]) -> list[str]:
    refs = cell.get("source_value_refs")
    if isinstance(refs, list):
        return [str(item) for item in refs if item]
    ref = cell.get("source_value_ref")
    return [str(ref)] if ref else []


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


def _projection_summary(projections: list[dict[str, Any]]) -> dict[str, Any]:
    eligible = [item for item in projections if _projection_is_eligible(item)]
    return {
        "total": len(projections),
        "eligible_total": len(eligible),
        "quality_counts": dict(
            sorted(
                Counter(
                    str(item.get("reconstruction_quality") or "blocked")
                    for item in projections
                ).items()
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
        "ocr_vlm_used": any(
            item.get("ocr_vlm_used") is not False for item in projections
        ),
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
        "Local real bounded table-domain proof prompt for "
        "{{source_fact_package_json}}. Return broker_reports_source_facts_v0 only."
    )
    return Gate2ManagedPrompt(
        prompt_ref=f"prompt_{domain}_real_table_domain_proof",
        command=f"broker_gate2_{domain}_v0",
        version="real-proof-v1",
        content=content,
        hash=gate2_prompt_hash(content),
        source="local_real_proof_boundary",
        template_id=f"broker_reports.{domain}_table_domain.real_proof.v0",
        template_kind=f"broker_reports_{domain}_extraction",
        prompt_contract_id="broker_reports_domain_source_fact_prompt_v0",
        input_schema_version="broker_reports_domain_extraction_package_v0",
        output_schema_id="broker_reports.source_facts.schema.v0",
        output_schema_version="broker_reports_source_facts_v0",
        tags=("broker-reports-gate2-domain", "structured-output"),
        safe_metadata={"extractor_domain": domain, "name": "real-table-domain-proof"},
    )


if __name__ == "__main__":
    raise SystemExit(main())
