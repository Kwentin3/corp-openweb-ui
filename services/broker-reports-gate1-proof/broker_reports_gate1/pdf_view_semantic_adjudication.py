from __future__ import annotations

import copy
import re
from collections import Counter
from datetime import datetime
from typing import Any

from .pdf_view_semantic_contracts import (
    ADJUDICATION_SCHEMA_VERSION,
    CORPUS_IDS,
    FINAL_RESULT_SCHEMA_VERSION,
    GOLD_CHECKLIST_SCHEMA_VERSION,
    SEMANTIC_COMPARISON_SCHEMA_VERSION,
    Doc4ContractError,
    ViewPointerRegistry,
    canonical_json_bytes,
    extract_structured_response,
    integrity_sha256,
    sha256_bytes,
    validate_financial_normalizations,
    validate_json_contract,
    validate_semantic_response,
)


COMPARATOR_VERSION = "broker_reports_doc4_deterministic_comparator_v1"
ADJUDICATION_OWNER_VERSION = "broker_reports_doc4_source_adjudication_owner_v1"
STABILITY_COMPARATOR_VERSION = "broker_reports_doc4_stability_comparator_v1"


class PdfViewSemanticComparator:
    """The sole deterministic RUN C owner; it never receives either source."""

    def compare(
        self,
        *,
        safe_id: str,
        pdf_response: dict[str, Any],
        view_response: dict[str, Any],
        comparison_schema: dict[str, Any],
    ) -> dict[str, Any]:
        if pdf_response.get("source_mode") != "PDF":
            raise Doc4ContractError("comparator_pdf_arm_not_pdf")
        if view_response.get("source_mode") != "LLM_VIEW":
            raise Doc4ContractError("comparator_view_arm_not_view")
        pdf_items = _flatten_response(pdf_response)
        view_items = _flatten_response(view_response)
        items: list[dict[str, Any]] = []
        for index, key in enumerate(sorted(set(pdf_items) | set(view_items))):
            left = pdf_items.get(key)
            right = view_items.get(key)
            critical = bool((left or right)["critical"])
            category = _comparison_category(left, right)
            items.append(
                {
                    "comparison_id": f"comparison_{index:06d}",
                    "semantic_key": key,
                    "critical": critical,
                    "category": category,
                    "pdf_status": left["status"] if left else None,
                    "view_status": right["status"] if right else None,
                    "pdf_value_sha256": _value_hash(left),
                    "view_value_sha256": _value_hash(right),
                    "pdf_pointer_valid": _pointer_present(left),
                    "view_pointer_valid": _pointer_present(right),
                }
            )
        counts = Counter(item["category"] for item in items)
        critical_items = [item for item in items if item["critical"]]
        noncritical_items = [item for item in items if not item["critical"]]
        matching = {"MATCH_EXACT", "MATCH_NORMALIZED"}
        result = {
            "schema_version": SEMANTIC_COMPARISON_SCHEMA_VERSION,
            "safe_id": safe_id,
            "pdf_response_sha256": sha256_bytes(canonical_json_bytes(pdf_response)),
            "view_response_sha256": sha256_bytes(canonical_json_bytes(view_response)),
            "comparator_version": COMPARATOR_VERSION,
            "items": items,
            "metrics": {
                "items_total": len(items),
                "match_exact_total": counts["MATCH_EXACT"],
                "match_normalized_total": counts["MATCH_NORMALIZED"],
                "critical_items_total": len(critical_items),
                "critical_matches_total": sum(item["category"] in matching for item in critical_items),
                "critical_match_rate": _rate(
                    sum(item["category"] in matching for item in critical_items),
                    len(critical_items),
                ),
                "noncritical_items_total": len(noncritical_items),
                "noncritical_matches_total": sum(item["category"] in matching for item in noncritical_items),
                "noncritical_match_rate": _rate(
                    sum(item["category"] in matching for item in noncritical_items),
                    len(noncritical_items),
                ),
                "conflicts_total": sum(item["category"] not in matching for item in items),
                "agreement_requires_source_adjudication": True,
            },
            "integrity_sha256": "",
        }
        result["integrity_sha256"] = integrity_sha256(result)
        validate_json_contract(result, comparison_schema, label="semantic_comparison")
        return result


class PdfViewSemanticAdjudicationFactory:
    """The sole RUN D sealing owner; human/source findings remain the authority."""

    def seal_gold(
        self,
        draft: dict[str, Any],
        *,
        gold_schema: dict[str, Any],
        expected_pdf_sha256: str,
        expected_pdf_page_texts: tuple[str, ...],
        provider_calls_started: bool,
        expected_pdf_pages: int | None = None,
    ) -> dict[str, Any]:
        if provider_calls_started:
            raise Doc4ContractError("gold_created_after_provider_calls")
        value = copy.deepcopy(draft)
        value["schema_version"] = GOLD_CHECKLIST_SCHEMA_VERSION
        value["pdf_sha256"] = expected_pdf_sha256
        value["created_before_provider_calls"] = True
        value["immutable"] = True
        if value.get("adjudicator_isolated_from_view") is not True:
            raise Doc4ContractError("gold_adjudicator_view_isolation_not_proven")
        if value.get("adjudicator_isolated_from_model_responses") is not True:
            raise Doc4ContractError("gold_adjudicator_response_isolation_not_proven")
        try:
            created_at = datetime.fromisoformat(value["created_at"].replace("Z", "+00:00"))
        except (KeyError, AttributeError, ValueError) as exc:
            raise Doc4ContractError("gold_created_at_invalid") from exc
        if created_at.tzinfo is None:
            raise Doc4ContractError("gold_created_at_timezone_missing")
        if not value.get("items"):
            raise Doc4ContractError("gold_checklist_empty")
        identifiers = [item.get("gold_item_id") for item in value.get("items", [])]
        semantic_keys = [item.get("semantic_key") for item in value.get("items", [])]
        if len(identifiers) != len(set(identifiers)):
            raise Doc4ContractError("gold_item_ids_not_unique")
        if len(semantic_keys) != len(set(semantic_keys)):
            raise Doc4ContractError("gold_semantic_keys_not_unique")
        expected_critical = sorted(
            item["gold_item_id"] for item in value.get("items", []) if item.get("critical") is True
        )
        if sorted(value.get("critical_fact_ids", [])) != expected_critical:
            raise Doc4ContractError("gold_critical_fact_ids_incomplete")
        category_prefixes = {
            "PASSPORT": "passport.",
            "STRUCTURE": "structure.",
            "TABLE": "table.",
            "FINANCIAL_FACT": "financial.",
            "UNCERTAINTY": "uncertainty.",
        }
        for item in value["items"]:
            if not item["semantic_key"].startswith(category_prefixes[item["category"]]):
                raise Doc4ContractError("gold_semantic_key_category_mismatch")
            financial = item["category"] == "FINANCIAL_FACT"
            if financial != (item.get("fact_kind") is not None):
                raise Doc4ContractError("gold_fact_kind_category_mismatch")
        _validate_gold_source_grounding(
            value,
            pdf_page_texts=expected_pdf_page_texts,
            expected_pdf_pages=expected_pdf_pages,
        )
        value["integrity_sha256"] = ""
        value["integrity_sha256"] = integrity_sha256(value)
        validate_json_contract(value, gold_schema, label="gold_checklist")
        return value


    def seal_adjudication(
        self,
        draft: dict[str, Any],
        *,
        gold: dict[str, Any],
        pdf_response: dict[str, Any],
        view_response: dict[str, Any],
        comparison: dict[str, Any],
        adjudication_schema: dict[str, Any],
        view_registry: ViewPointerRegistry | None = None,
        critical_stability_conflicts_total: int = 0,
    ) -> dict[str, Any]:
        if gold.get("integrity_sha256") != integrity_sha256(gold):
            raise Doc4ContractError("gold_checklist_integrity_invalid")
        if comparison.get("integrity_sha256") != integrity_sha256(comparison):
            raise Doc4ContractError("semantic_comparison_integrity_invalid")
        if comparison.get("safe_id") != gold.get("safe_id"):
            raise Doc4ContractError("adjudication_safe_id_mismatch")
        if comparison.get("pdf_response_sha256") != sha256_bytes(canonical_json_bytes(pdf_response)):
            raise Doc4ContractError("adjudication_pdf_response_binding_mismatch")
        if comparison.get("view_response_sha256") != sha256_bytes(canonical_json_bytes(view_response)):
            raise Doc4ContractError("adjudication_view_response_binding_mismatch")
        value = copy.deepcopy(draft)
        value["schema_version"] = ADJUDICATION_SCHEMA_VERSION
        value["safe_id"] = gold["safe_id"]
        value["gold_checklist_sha256"] = sha256_bytes(canonical_json_bytes(gold))
        value["pdf_response_sha256"] = sha256_bytes(canonical_json_bytes(pdf_response))
        value["view_response_sha256"] = sha256_bytes(canonical_json_bytes(view_response))
        value["comparison_sha256"] = sha256_bytes(canonical_json_bytes(comparison))
        value["complete"] = True
        _validate_adjudication_coverage(
            value,
            gold=gold,
            pdf_response=pdf_response,
            view_response=view_response,
            comparison=comparison,
            view_registry=view_registry,
        )
        metrics = _adjudication_metrics(
            value["findings"],
            gold,
            pdf_response=pdf_response,
            view_response=view_response,
            comparison=comparison,
            critical_stability_conflicts_total=critical_stability_conflicts_total,
        )
        value["metrics"] = metrics
        model_task_adequacy = _model_task_adequacy(metrics)
        value["model_task_adequacy"] = model_task_adequacy
        value.pop("semantic_equivalence", None)
        value["document_semantic_assessment"] = _document_semantic_assessment(
            model_task_adequacy=model_task_adequacy,
            metrics=metrics,
            comparison=comparison,
        )
        value["integrity_sha256"] = ""
        value["integrity_sha256"] = integrity_sha256(value)
        validate_json_contract(value, adjudication_schema, label="source_adjudication")
        return value


class PdfViewSemanticResultFactory:
    """Seal the only terminal four-document DOC4 semantic result."""

    def finalize(
        self,
        *,
        adjudications: dict[str, dict[str, Any]],
        comparisons: dict[str, dict[str, Any]],
        gold_checklists: dict[str, dict[str, Any]],
        pdf_responses: dict[str, dict[str, Any]],
        view_responses: dict[str, dict[str, Any]],
        validated_receipts: dict[str, dict[str, dict[str, Any]]],
        run_traces: dict[str, dict[str, dict[str, Any]]],
        expected_request_sha256_by_safe_id: dict[str, dict[str, str]],
        expected_preflight_request_sha256_by_safe_id: dict[
            str, dict[str, tuple[str, ...]]
        ],
        expected_pdf_sha256_by_safe_id: dict[str, str],
        pdf_page_texts_by_safe_id: dict[str, tuple[str, ...]],
        view_registries: dict[str, ViewPointerRegistry],
        critical_stability_conflicts_by_safe_id: dict[str, int],
        context_preflight: dict[str, Any],
        expected_run_plan_sha256: str,
        expected_candidate: dict[str, Any],
        gold_schema: dict[str, Any],
        response_schema: dict[str, Any],
        comparison_schema: dict[str, Any],
        adjudication_schema: dict[str, Any],
        result_schema: dict[str, Any],
    ) -> dict[str, Any]:
        validate_doc4_context_preflight(
            context_preflight,
            expected_run_plan_sha256=expected_run_plan_sha256,
            expected_candidate=expected_candidate,
            expected_request_sha256_by_safe_id=(
                expected_preflight_request_sha256_by_safe_id
            ),
        )
        corpus_mappings = {
            "paired": (pdf_responses, view_responses),
            "gold": (gold_checklists, expected_pdf_sha256_by_safe_id, pdf_page_texts_by_safe_id),
            "adjudication": (adjudications, comparisons, view_registries, critical_stability_conflicts_by_safe_id),
            "run_evidence": (validated_receipts, run_traces, expected_request_sha256_by_safe_id),
        }
        for label, mappings in corpus_mappings.items():
            if any(tuple(mapping) != CORPUS_IDS for mapping in mappings):
                raise Doc4ContractError(f"terminal_{label}_corpus_incomplete")

        documents: list[dict[str, Any]] = []
        for safe_id in CORPUS_IDS:
            item = adjudications[safe_id]
            gold = gold_checklists[safe_id]
            validate_json_contract(gold, gold_schema, label="gold_checklist")
            if gold.get("safe_id") != safe_id:
                raise Doc4ContractError("terminal_gold_safe_id_mismatch")
            if gold.get("integrity_sha256") != integrity_sha256(gold):
                raise Doc4ContractError("terminal_gold_integrity_invalid")
            if gold.get("pdf_sha256") != expected_pdf_sha256_by_safe_id[safe_id]:
                raise Doc4ContractError("terminal_gold_pdf_binding_invalid")
            _validate_gold_source_grounding(
                gold,
                pdf_page_texts=pdf_page_texts_by_safe_id[safe_id],
                expected_pdf_pages=len(pdf_page_texts_by_safe_id[safe_id]),
            )
            for arm, response in (
                ("PDF", pdf_responses[safe_id]),
                ("LLM_VIEW", view_responses[safe_id]),
            ):
                validate_semantic_response(
                    response,
                    response_schema,
                    expected_source_mode=arm,
                    pdf_pages_total=(
                        len(pdf_page_texts_by_safe_id[safe_id])
                        if arm == "PDF"
                        else None
                    ),
                    pdf_page_texts=(
                        pdf_page_texts_by_safe_id[safe_id]
                        if arm == "PDF"
                        else None
                    ),
                    view_registry=(
                        view_registries[safe_id]
                        if arm == "LLM_VIEW"
                        else None
                    ),
                )
                _validate_terminal_arm_evidence(
                    safe_id=safe_id,
                    source_mode=arm,
                    response=response,
                    validated_receipt=validated_receipts[safe_id][arm],
                    run_trace=run_traces[safe_id][arm],
                    expected_request_sha256=expected_request_sha256_by_safe_id[
                        safe_id
                    ][arm],
                    expected_model_id=expected_candidate["request_model_id"],
                )
            validate_json_contract(
                item, adjudication_schema, label="source_adjudication"
            )
            replayed_comparison = PdfViewSemanticComparator().compare(
                safe_id=safe_id,
                pdf_response=pdf_responses[safe_id],
                view_response=view_responses[safe_id],
                comparison_schema=comparison_schema,
            )
            if canonical_json_bytes(replayed_comparison) != canonical_json_bytes(
                comparisons[safe_id]
            ):
                raise Doc4ContractError("terminal_comparison_replay_mismatch")
            if item.get("schema_version") != ADJUDICATION_SCHEMA_VERSION:
                raise Doc4ContractError("terminal_adjudication_version_invalid")
            if item.get("safe_id") != safe_id:
                raise Doc4ContractError("terminal_adjudication_safe_id_mismatch")
            if item.get("complete") is not True:
                raise Doc4ContractError("terminal_adjudication_incomplete")
            if item.get("integrity_sha256") != integrity_sha256(item):
                raise Doc4ContractError("terminal_adjudication_integrity_invalid")
            if item.get("gold_checklist_sha256") != sha256_bytes(
                canonical_json_bytes(gold)
            ):
                raise Doc4ContractError("terminal_gold_binding_invalid")
            if item.get("pdf_response_sha256") != sha256_bytes(
                canonical_json_bytes(pdf_responses[safe_id])
            ) or item.get("view_response_sha256") != sha256_bytes(
                canonical_json_bytes(view_responses[safe_id])
            ):
                raise Doc4ContractError("terminal_response_binding_invalid")
            replayed = PdfViewSemanticAdjudicationFactory().seal_adjudication(
                item,
                gold=gold,
                pdf_response=pdf_responses[safe_id],
                view_response=view_responses[safe_id],
                comparison=comparisons[safe_id],
                adjudication_schema=adjudication_schema,
                view_registry=view_registries[safe_id],
                critical_stability_conflicts_total=(
                    critical_stability_conflicts_by_safe_id[safe_id]
                ),
            )
            if canonical_json_bytes(replayed) != canonical_json_bytes(item):
                raise Doc4ContractError("terminal_adjudication_replay_mismatch")
            documents.append(
                {
                    "safe_id": safe_id,
                    "adjudication_sha256": sha256_bytes(canonical_json_bytes(item)),
                    "model_task_adequacy": item["model_task_adequacy"],
                    "document_semantic_assessment": item[
                        "document_semantic_assessment"
                    ],
                }
            )

        metrics = _terminal_metrics(adjudications)
        model_task_adequacy = (
            "PASSED"
            if all(item["model_task_adequacy"] == "PASSED" for item in documents)
            else "FAILED"
        )
        semantic_equivalence = _terminal_semantic_equivalence(
            documents=documents,
            model_task_adequacy=model_task_adequacy,
            metrics=metrics,
        )
        result = {
            "schema_version": FINAL_RESULT_SCHEMA_VERSION,
            "eligible_documents_total": len(CORPUS_IDS),
            "completed_paired_documents_total": len(CORPUS_IDS),
            "sealed_adjudications_total": len(documents),
            "documents": documents,
            "metrics": metrics,
            "model_task_adequacy": model_task_adequacy,
            "semantic_equivalence": semantic_equivalence,
            "integrity_sha256": "",
        }
        result["integrity_sha256"] = integrity_sha256(result)
        validate_json_contract(result, result_schema, label="semantic_result")
        return result


def compare_stability_replay(
    *,
    safe_id: str,
    source_mode: str,
    primary: dict[str, Any],
    replica: dict[str, Any],
) -> dict[str, Any]:
    if primary.get("source_mode") != source_mode or replica.get("source_mode") != source_mode:
        raise Doc4ContractError("stability_source_mode_mismatch")
    left = _flatten_response(primary)
    right = _flatten_response(replica)
    items: list[dict[str, Any]] = []
    for key in sorted(set(left) | set(right)):
        primary_item = left.get(key)
        replica_item = right.get(key)
        category = _comparison_category(primary_item, replica_item)
        pointer_match = (
            primary_item is not None
            and replica_item is not None
            and primary_item["evidence"] == replica_item["evidence"]
        )
        items.append(
            {
                "semantic_key": key,
                "critical": bool((primary_item or replica_item)["critical"]),
                "category": category,
                "pointer_match": pointer_match,
            }
        )
    matching = {"MATCH_EXACT", "MATCH_NORMALIZED"}
    critical_conflicts = sum(
        item["critical"]
        and (item["category"] not in matching or not item["pointer_match"])
        for item in items
    )
    result = {
        "schema_version": "broker_reports_doc4_model_stability_comparison_v1",
        "comparator_version": STABILITY_COMPARATOR_VERSION,
        "safe_id": safe_id,
        "source_mode": source_mode,
        "primary_response_sha256": sha256_bytes(canonical_json_bytes(primary)),
        "replica_response_sha256": sha256_bytes(canonical_json_bytes(replica)),
        "items": items,
        "critical_stability_conflicts_total": critical_conflicts,
        "stable": critical_conflicts == 0,
        "integrity_sha256": "",
    }
    result["integrity_sha256"] = integrity_sha256(result)
    return result


def _flatten_response(value: dict[str, Any]) -> dict[str, dict[str, Any]]:
    flattened: dict[str, dict[str, Any]] = {}
    for item in value["document_passport"]:
        _add_flattened(
            flattened,
            f"passport.{item['field_id']}",
            item,
            critical=item["field_id"] in {"reporting_period", "owner_or_account"},
            ordinal=None,
        )
    for item in value["document_structure"]:
        _add_flattened(
            flattened,
            f"structure.{item['element_id']}",
            item,
            critical=item["type"] in {"TABLE", "TABLE_ROW"},
            ordinal=item["ordinal"],
        )
    for item in value["tables"]:
        _add_flattened(
            flattened,
            f"table.{item['table_key']}",
            item,
            critical=True,
            ordinal=item["ordinal"],
        )
    for item in value["financial_facts"]:
        _add_flattened(
            flattened,
            f"financial.{item['fact_id']}",
            item,
            critical=bool(item["critical"]),
            ordinal=item["record_ordinal"],
        )
    for item in value["uncertainties"]:
        _add_flattened(
            flattened,
            f"uncertainty.{item['uncertainty_id']}",
            {
                "status": "PRESENT",
                "source_literal": item["description"],
                "normalized_value": item["category"],
                "evidence": item["evidence"],
            },
            critical=bool(item["critical"]),
            ordinal=None,
        )
    return flattened


def _add_flattened(
    target: dict[str, dict[str, Any]],
    key: str,
    item: dict[str, Any],
    *,
    critical: bool,
    ordinal: int | None,
) -> None:
    if key in target:
        raise Doc4ContractError("comparator_semantic_key_duplicate")
    exact = {
        "status": item["status"],
        "source_literal": item.get("source_literal"),
        "normalized_value": item.get("normalized_value"),
        "normalized_decimal": item.get("normalized_decimal"),
        "normalized_date": item.get("normalized_date"),
        "currency": item.get("currency"),
        "unit": item.get("unit"),
        "sign": item.get("sign"),
        "ordinal": ordinal,
    }
    normalized = {name: item for name, item in exact.items() if name != "source_literal"}
    target[key] = {
        "status": item["status"],
        "critical": critical,
        "fact_kind": item.get("fact_kind"),
        "category": key.split(".", 1)[0],
        "exact": exact,
        "normalized": normalized,
        "evidence": item.get("evidence", []),
    }


def _comparison_category(
    left: dict[str, Any] | None,
    right: dict[str, Any] | None,
) -> str:
    if left is None:
        return "VIEW_ONLY_FACT"
    if right is None:
        return "PDF_ONLY_FACT"
    if left["status"] != right["status"]:
        return "STATUS_CONFLICT"
    if left["exact"].get("ordinal") != right["exact"].get("ordinal"):
        return "ORDER_CONFLICT"
    if left["exact"] == right["exact"]:
        return "MATCH_EXACT"
    if left["normalized"] == right["normalized"]:
        return "MATCH_NORMALIZED"
    return "VALUE_CONFLICT"


def _value_hash(item: dict[str, Any] | None) -> str | None:
    return sha256_bytes(canonical_json_bytes(item["exact"])) if item else None


def _pointer_present(item: dict[str, Any] | None) -> bool | None:
    if item is None:
        return None
    if item["status"] in {"UNKNOWN", "NOT_APPLICABLE"}:
        return None
    return bool(item["evidence"])


def _validate_adjudication_coverage(
    value: dict[str, Any],
    *,
    gold: dict[str, Any],
    pdf_response: dict[str, Any],
    view_response: dict[str, Any],
    comparison: dict[str, Any],
    view_registry: ViewPointerRegistry | None,
) -> None:
    findings = value.get("findings")
    if not isinstance(findings, list):
        raise Doc4ContractError("adjudication_findings_invalid")
    keys = [item.get("semantic_key") for item in findings if isinstance(item, dict)]
    if len(keys) != len(set(keys)):
        raise Doc4ContractError("adjudication_semantic_key_duplicate")
    gold_by_key = {item["semantic_key"]: item for item in gold["items"]}
    comparison_by_key = {item["semantic_key"]: item for item in comparison["items"]}
    pdf_items = _flatten_response(pdf_response)
    view_items = _flatten_response(view_response)
    source_keys = set(pdf_items) | set(view_items)
    required = set(gold_by_key)
    required.update(source_keys - set(gold_by_key))
    required.update(
        item["semantic_key"]
        for item in comparison["items"]
        if item["category"] not in {"MATCH_EXACT", "MATCH_NORMALIZED"}
        or item["critical"]
    )
    required.update(
        key
        for key, item in {**pdf_items, **view_items}.items()
        if item.get("fact_kind")
        in {
            "TOTAL",
            "SUBTOTAL",
            "COMMISSION",
            "TAX",
            "BALANCE",
            "OPENING_BALANCE",
            "CLOSING_BALANCE",
        }
    )
    if view_registry is not None and view_registry.block_types is not None:
        for item in view_response["financial_facts"]:
            if any(
                view_registry.block_types.get(pointer.get("block_id")) == "UNKNOWN"
                for pointer in item["evidence"]
            ):
                required.add(f"financial.{item['fact_id']}")
    if not required.issubset(set(keys)):
        raise Doc4ContractError("adjudication_required_coverage_incomplete")
    allowed = set(gold_by_key) | source_keys
    if not set(keys).issubset(allowed):
        raise Doc4ContractError("adjudication_unknown_semantic_key")
    matched_noncritical = {
        item["semantic_key"]
        for item in comparison["items"]
        if not item["critical"]
        and item["category"] in {"MATCH_EXACT", "MATCH_NORMALIZED"}
    }
    if len(set(keys) & matched_noncritical) < min(20, len(matched_noncritical)):
        raise Doc4ContractError("adjudication_noncritical_sample_incomplete")
    for finding in findings:
        key = finding["semantic_key"]
        gold_item = gold_by_key.get(key)
        expected_gold_id = gold_item["gold_item_id"] if gold_item else None
        if finding.get("gold_item_id") != expected_gold_id:
            raise Doc4ContractError("adjudication_gold_item_binding_invalid")
        comparison_item = comparison_by_key.get(key)
        finding["evidence_binding_sha256"] = sha256_bytes(
            canonical_json_bytes(
                {
                    "safe_id": gold["safe_id"],
                    "semantic_key": key,
                    "gold_item": gold_item,
                    "pdf_item": pdf_items.get(key),
                    "view_item": view_items.get(key),
                    "comparison_item": comparison_item,
                }
            )
        )
        expected_category = comparison_item["category"] if comparison_item else "UNCOMPARABLE"
        if finding.get("comparison_category") != expected_category:
            raise Doc4ContractError("adjudication_comparison_binding_invalid")
        critical = bool(
            (gold_item or {}).get("critical")
            or (pdf_items.get(key) or {}).get("critical")
            or (view_items.get(key) or {}).get("critical")
        )
        if finding.get("critical") is not critical:
            raise Doc4ContractError("adjudication_criticality_mismatch")
        expected_pdf_correct = _arm_matches_gold(gold_item, pdf_items.get(key))
        expected_view_correct = _arm_matches_gold(gold_item, view_items.get(key))
        if (
            finding["pdf_arm_correct"] is not expected_pdf_correct
            or finding["view_arm_correct"] is not expected_view_correct
        ):
            raise Doc4ContractError("adjudication_correctness_not_derived_from_gold")
        expected_pdf_unsupported = gold_item is None and key in pdf_items
        expected_view_unsupported = gold_item is None and key in view_items
        if (
            finding["pdf_arm_unsupported"] is not expected_pdf_unsupported
            or finding["view_arm_unsupported"] is not expected_view_unsupported
            or finding["unsupported_fact"]
            is not (expected_pdf_unsupported or expected_view_unsupported)
        ):
            raise Doc4ContractError("adjudication_unsupported_flag_mismatch")
        expected_pdf_pointer = (
            comparison_item.get("pdf_pointer_valid") if comparison_item else None
        )
        expected_view_pointer = (
            comparison_item.get("view_pointer_valid") if comparison_item else None
        )
        if (
            finding["pdf_pointer_valid"] != expected_pdf_pointer
            or finding["view_pointer_valid"] != expected_view_pointer
        ):
            raise Doc4ContractError("adjudication_pointer_verdict_not_deterministic")
        if finding["invalid_pointer"] is not (
            expected_pdf_pointer is False or expected_view_pointer is False
        ):
            raise Doc4ContractError("adjudication_invalid_pointer_flag_mismatch")
        for arm, arm_items in (("pdf", pdf_items), ("view", view_items)):
            present = key in arm_items
            if finding[f"{arm}_arm_correct"] and not present:
                raise Doc4ContractError("adjudication_missing_arm_marked_correct")
            if finding[f"{arm}_arm_unsupported"] and (
                not present or gold_item is not None or finding[f"{arm}_arm_correct"]
            ):
                raise Doc4ContractError("adjudication_unsupported_arm_invalid")
            pointer_expected = present and arm_items[key]["status"] in {
                "PRESENT",
                "CONFLICTING",
            }
            pointer_value = finding[f"{arm}_pointer_valid"]
            if pointer_expected != isinstance(pointer_value, bool):
                raise Doc4ContractError("adjudication_pointer_verdict_missing_or_extra")
        disposition = finding.get("disposition")
        expected_disposition = {
            (True, True): "BOTH_CORRECT",
            (True, False): "ARTIFACT_SEMANTIC_GAP",
            (False, True): "PDF_NATIVE_MODEL_GAP",
            (False, False): "BOTH_WRONG",
        }[(expected_pdf_correct, expected_view_correct)]
        if disposition != expected_disposition:
            raise Doc4ContractError("adjudication_disposition_not_derived_from_gold")
        if finding["artifact_semantic_gap"] is not (
            expected_disposition == "ARTIFACT_SEMANTIC_GAP"
        ) or finding["pdf_native_model_gap"] is not (
            expected_disposition == "PDF_NATIVE_MODEL_GAP"
        ) or finding["both_wrong"] is not (expected_disposition == "BOTH_WRONG"):
            raise Doc4ContractError("adjudication_gap_flags_not_derived_from_gold")
        flags = {
            "ARTIFACT_SEMANTIC_GAP": "artifact_semantic_gap",
            "PDF_NATIVE_MODEL_GAP": "pdf_native_model_gap",
            "BOTH_WRONG": "both_wrong",
        }
        for expected_disposition, flag in flags.items():
            if bool(finding.get(flag)) != (disposition == expected_disposition):
                raise Doc4ContractError("adjudication_disposition_flag_mismatch")
        expected_correctness = {
            "PDF_ARM_CORRECT": (True, False),
            "VIEW_ARM_CORRECT": (False, True),
            "BOTH_CORRECT": (True, True),
            "PDF_ARM_WRONG": (False, True),
            "VIEW_ARM_WRONG": (True, False),
            "BOTH_WRONG": (False, False),
            "ARTIFACT_SEMANTIC_GAP": (True, False),
            "PDF_NATIVE_MODEL_GAP": (False, True),
            "MODEL_GENERAL_FAILURE": (False, False),
        }.get(disposition)
        if expected_correctness is not None and expected_correctness != (
            finding["pdf_arm_correct"],
            finding["view_arm_correct"],
        ):
            raise Doc4ContractError("adjudication_disposition_correctness_mismatch")


def _arm_matches_gold(
    gold_item: dict[str, Any] | None,
    arm_item: dict[str, Any] | None,
) -> bool:
    if gold_item is None or arm_item is None:
        return False
    expected = {
        "status": gold_item["status"],
        "source_literal": gold_item.get("source_literal"),
        "normalized_value": gold_item.get("normalized_value"),
        "normalized_decimal": gold_item.get("normalized_decimal"),
        "normalized_date": gold_item.get("normalized_date"),
        "currency": gold_item.get("currency"),
        "unit": gold_item.get("unit"),
        "sign": gold_item.get("sign"),
        "ordinal": gold_item.get("ordinal"),
    }
    return arm_item["exact"] == expected and arm_item.get("fact_kind") == gold_item.get(
        "fact_kind"
    )


def _adjudication_metrics(
    findings: list[dict[str, Any]],
    gold: dict[str, Any],
    *,
    pdf_response: dict[str, Any],
    view_response: dict[str, Any],
    comparison: dict[str, Any],
    critical_stability_conflicts_total: int,
) -> dict[str, Any]:
    if critical_stability_conflicts_total < 0:
        raise Doc4ContractError("adjudication_stability_count_invalid")
    gold_by_key = {item["semantic_key"]: item for item in gold["items"]}
    findings_by_key = {item["semantic_key"]: item for item in findings}
    arm_items = {
        "pdf": _flatten_response(pdf_response),
        "view": _flatten_response(view_response),
    }
    gold_keys = {
        True: {key for key, item in gold_by_key.items() if item["critical"]},
        False: {key for key, item in gold_by_key.items() if not item["critical"]},
    }
    metrics: dict[str, Any] = {
        "gold_critical_facts_total": len(gold_keys[True]),
        "gold_noncritical_facts_total": len(gold_keys[False]),
    }
    for arm in ("pdf", "view"):
        for critical, label in ((True, "critical"), (False, "noncritical")):
            keys = gold_keys[critical]
            correct = sum(findings_by_key[key][f"{arm}_arm_correct"] for key in keys)
            missing = sum(key not in arm_items[arm] for key in keys)
            wrong = sum(
                key in arm_items[arm]
                and not findings_by_key[key][f"{arm}_arm_correct"]
                for key in keys
            )
            unsupported = sum(
                item[f"{arm}_arm_unsupported"] and item["critical"] is critical
                for item in findings
            )
            metrics[f"{arm}_correct_{label}_facts_total"] = correct
            metrics[f"{arm}_missing_{label}_facts_total"] = missing
            metrics[f"{arm}_wrong_{label}_facts_total"] = wrong
            metrics[f"{arm}_unsupported_{label}_facts_total"] = unsupported
            metrics[f"{arm}_{label}_precision"] = _rate(
                correct,
                correct + wrong + unsupported,
            )
            metrics[f"{arm}_{label}_recall"] = _rate(correct, len(keys))
        metrics[f"{arm}_numeric_exact_match_total"] = _gold_exact_total(
            gold_by_key,
            arm_items[arm],
            "normalized_decimal",
        )
        metrics[f"{arm}_date_exact_match_total"] = _gold_exact_total(
            gold_by_key,
            arm_items[arm],
            "normalized_date",
        )
        metrics[f"{arm}_currency_exact_match_total"] = _gold_exact_total(
            gold_by_key,
            arm_items[arm],
            "currency",
        )
        pointer_values = [
            item[f"{arm}_pointer_valid"]
            for item in findings
            if isinstance(item[f"{arm}_pointer_valid"], bool)
        ]
        metrics[f"{arm}_pointer_valid_total"] = sum(pointer_values)
        metrics[f"{arm}_pointer_invalid_total"] = sum(not item for item in pointer_values)
        metrics[f"{arm}_critical_pointer_invalid_total"] = sum(
            item["critical"] and item[f"{arm}_pointer_valid"] is False
            for item in findings
        )
        metrics[f"{arm}_structure_order_match"] = _structure_order_matches(
            gold_by_key,
            arm_items[arm],
        )
    metrics.update(
        {
            "unsupported_facts_total": sum(item["unsupported_fact"] for item in findings),
            "unsupported_critical_facts_total": sum(
                item["critical"] and item["unsupported_fact"] for item in findings
            ),
            "artifact_semantic_gaps_total": sum(item["artifact_semantic_gap"] for item in findings),
            "pdf_native_model_gaps_total": sum(item["pdf_native_model_gap"] for item in findings),
            "both_arms_wrong_total": sum(item["both_wrong"] for item in findings),
            "invalid_source_pointers_total": sum(item["invalid_pointer"] for item in findings),
            "critical_stability_conflicts_total": critical_stability_conflicts_total,
            "critical_cross_arm_correct_matches_total": sum(
                item["critical"]
                and item["pdf_arm_correct"]
                and item["view_arm_correct"]
                and item["comparison_category"]
                in {"MATCH_EXACT", "MATCH_NORMALIZED"}
                for item in findings
            ),
            "critical_cross_arm_correct_match_rate": _rate(
                sum(
                    item["critical"]
                    and item["pdf_arm_correct"]
                    and item["view_arm_correct"]
                    and item["comparison_category"]
                    in {"MATCH_EXACT", "MATCH_NORMALIZED"}
                    for item in findings
                ),
                sum(item["critical"] for item in findings),
            ),
            "noncritical_cross_arm_correct_matches_total": sum(
                not item["critical"]
                and item["pdf_arm_correct"]
                and item["view_arm_correct"]
                and item["comparison_category"]
                in {"MATCH_EXACT", "MATCH_NORMALIZED"}
                for item in findings
            ),
            "noncritical_cross_arm_correct_match_rate": _rate(
                sum(
                    not item["critical"]
                    and item["pdf_arm_correct"]
                    and item["view_arm_correct"]
                    and item["comparison_category"]
                    in {"MATCH_EXACT", "MATCH_NORMALIZED"}
                    for item in findings
                ),
                sum(not item["critical"] for item in findings),
            ),
        }
    )
    if comparison["metrics"]["agreement_requires_source_adjudication"] is not True:
        raise Doc4ContractError("comparison_adjudication_policy_invalid")
    return metrics


def _model_task_adequacy(metrics: dict[str, Any]) -> str:
    critical_total = metrics["gold_critical_facts_total"]
    passed = (
        critical_total > 0
        and metrics["pdf_critical_precision"] == "1.000000"
        and metrics["pdf_critical_recall"] == "1.000000"
        and metrics["view_critical_precision"] == "1.000000"
        and metrics["view_critical_recall"] == "1.000000"
        and float(metrics["pdf_noncritical_precision"]) >= 0.95
        and float(metrics["pdf_noncritical_recall"]) >= 0.95
        and float(metrics["view_noncritical_precision"]) >= 0.95
        and float(metrics["view_noncritical_recall"]) >= 0.95
        and metrics["unsupported_critical_facts_total"] == 0
        and metrics["pdf_critical_pointer_invalid_total"] == 0
        and metrics["view_critical_pointer_invalid_total"] == 0
        and metrics["invalid_source_pointers_total"] == 0
        and metrics["both_arms_wrong_total"] == 0
        and metrics["critical_stability_conflicts_total"] == 0
    )
    return "PASSED" if passed else "FAILED"


def _document_semantic_assessment(
    *,
    model_task_adequacy: str,
    metrics: dict[str, Any],
    comparison: dict[str, Any],
) -> str:
    if metrics["artifact_semantic_gaps_total"]:
        return "DOCUMENT_FAILED"
    if model_task_adequacy != "PASSED":
        return "DOCUMENT_INCONCLUSIVE_MODEL_INADEQUACY"
    if (
        metrics["view_wrong_critical_facts_total"]
        or metrics["unsupported_critical_facts_total"]
        or metrics["invalid_source_pointers_total"]
        or not metrics["view_structure_order_match"]
    ):
        return "DOCUMENT_FAILED"
    comparison_metrics = comparison["metrics"]
    if (
        comparison_metrics["conflicts_total"] == 0
        and metrics["critical_cross_arm_correct_match_rate"] == "1.000000"
        and metrics["noncritical_cross_arm_correct_match_rate"] == "1.000000"
    ):
        return "DOCUMENT_PASSED_STRICT"
    if (
        metrics["critical_cross_arm_correct_match_rate"] == "1.000000"
        and float(metrics["noncritical_cross_arm_correct_match_rate"]) >= 0.95
    ):
        return "DOCUMENT_PASSED_WITH_NONCRITICAL_VARIANCE"
    return "DOCUMENT_FAILED"


def _terminal_metrics(
    adjudications: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    values = [adjudications[safe_id] for safe_id in CORPUS_IDS]
    metrics = [item["metrics"] for item in values]

    def total(name: str) -> int:
        return sum(item[name] for item in metrics)

    gold_critical_total = total("gold_critical_facts_total")
    gold_noncritical_total = total("gold_noncritical_facts_total")
    pdf_critical_correct = total("pdf_correct_critical_facts_total")
    view_critical_correct = total("view_correct_critical_facts_total")
    pdf_noncritical_correct = total("pdf_correct_noncritical_facts_total")
    view_noncritical_correct = total("view_correct_noncritical_facts_total")
    critical_findings_total = sum(
        finding["critical"] for value in values for finding in value["findings"]
    )
    noncritical_findings_total = sum(
        not finding["critical"] for value in values for finding in value["findings"]
    )
    return {
        "gold_critical_facts_total": gold_critical_total,
        "gold_noncritical_facts_total": gold_noncritical_total,
        "pdf_arm_critical_precision": _rate(
            pdf_critical_correct,
            pdf_critical_correct
            + total("pdf_wrong_critical_facts_total")
            + total("pdf_unsupported_critical_facts_total"),
        ),
        "pdf_arm_critical_recall": _rate(
            pdf_critical_correct, gold_critical_total
        ),
        "view_arm_critical_precision": _rate(
            view_critical_correct,
            view_critical_correct
            + total("view_wrong_critical_facts_total")
            + total("view_unsupported_critical_facts_total"),
        ),
        "view_arm_critical_recall": _rate(
            view_critical_correct, gold_critical_total
        ),
        "pdf_arm_noncritical_precision": _rate(
            pdf_noncritical_correct,
            pdf_noncritical_correct
            + total("pdf_wrong_noncritical_facts_total")
            + total("pdf_unsupported_noncritical_facts_total"),
        ),
        "pdf_arm_noncritical_recall": _rate(
            pdf_noncritical_correct, gold_noncritical_total
        ),
        "view_arm_noncritical_precision": _rate(
            view_noncritical_correct,
            view_noncritical_correct
            + total("view_wrong_noncritical_facts_total")
            + total("view_unsupported_noncritical_facts_total"),
        ),
        "view_arm_noncritical_recall": _rate(
            view_noncritical_correct, gold_noncritical_total
        ),
        "critical_cross_arm_match_rate": _rate(
            total("critical_cross_arm_correct_matches_total"),
            critical_findings_total,
        ),
        "noncritical_cross_arm_match_rate": _rate(
            total("noncritical_cross_arm_correct_matches_total"),
            noncritical_findings_total,
        ),
        "artifact_semantic_gaps_total": total("artifact_semantic_gaps_total"),
        "unsupported_critical_facts_total": total(
            "unsupported_critical_facts_total"
        ),
        "invalid_critical_pointers_total": total(
            "pdf_critical_pointer_invalid_total"
        )
        + total("view_critical_pointer_invalid_total"),
        "invalid_source_pointers_total": total("invalid_source_pointers_total"),
        "both_arms_wrong_total": total("both_arms_wrong_total"),
        "critical_stability_conflicts_total": total(
            "critical_stability_conflicts_total"
        ),
        "view_structure_order_all_match": all(
            item["view_structure_order_match"] for item in metrics
        ),
    }


def validate_doc4_context_preflight(
    value: dict[str, Any],
    *,
    expected_run_plan_sha256: str,
    expected_candidate: dict[str, Any],
    expected_request_sha256_by_safe_id: dict[str, dict[str, tuple[str, ...]]],
) -> None:
    if value.get("schema_version") != "broker_reports_doc4_context_preflight_private_v1":
        raise Doc4ContractError("terminal_preflight_version_invalid")
    if value.get("integrity_sha256") != integrity_sha256(value):
        raise Doc4ContractError("terminal_preflight_integrity_invalid")
    if value.get("run_plan_sha256") != expected_run_plan_sha256:
        raise Doc4ContractError("terminal_preflight_plan_binding_invalid")
    if value.get("request_model_id") != expected_candidate.get("request_model_id"):
        raise Doc4ContractError("terminal_preflight_model_invalid")
    if tuple(expected_request_sha256_by_safe_id) != CORPUS_IDS:
        raise Doc4ContractError("terminal_preflight_request_corpus_incomplete")
    documents = value.get("documents")
    if not isinstance(documents, dict) or tuple(documents) != CORPUS_IDS:
        raise Doc4ContractError("terminal_eligible_corpus_incomplete")
    calls_total = 0
    for safe_id in CORPUS_IDS:
        arms = documents[safe_id]
        if not isinstance(arms, dict) or set(arms) != {"PDF", "LLM_VIEW"}:
            raise Doc4ContractError("terminal_preflight_arms_invalid")
        expected_arm_hashes = expected_request_sha256_by_safe_id[safe_id]
        if set(expected_arm_hashes) != {"PDF", "LLM_VIEW"}:
            raise Doc4ContractError("terminal_preflight_request_arms_invalid")
        for arm in ("PDF", "LLM_VIEW"):
            receipt = arms[arm]
            components = (
                "source_tokens",
                "system_tokens",
                "task_tokens",
                "schema_tokens",
                "request_envelope_tokens",
            )
            if any(
                not isinstance(receipt.get(name), int)
                or isinstance(receipt.get(name), bool)
                or receipt[name] < 0
                for name in (*components, "total_input_tokens")
            ):
                raise Doc4ContractError("terminal_preflight_token_counts_invalid")
            if sum(receipt[name] for name in components) != receipt["total_input_tokens"]:
                raise Doc4ContractError("terminal_preflight_token_partition_inexact")
            expected_budget = (
                expected_candidate["reserved_max_output_tokens"],
                expected_candidate["safety_margin_tokens"],
                expected_candidate["context_window"],
            )
            actual_budget = (
                receipt.get("reserved_output_tokens"),
                receipt.get("safety_margin_tokens"),
                receipt.get("context_window"),
            )
            if actual_budget != expected_budget:
                raise Doc4ContractError("terminal_preflight_budget_invalid")
            eligible = sum(
                (
                    receipt["total_input_tokens"],
                    receipt["reserved_output_tokens"],
                    receipt["safety_margin_tokens"],
                )
            ) <= receipt["context_window"]
            if receipt.get("eligible") is not eligible or receipt.get("reason") != (
                "FIT" if eligible else "NOT_ELIGIBLE_CONTEXT_LIMIT"
            ):
                raise Doc4ContractError("terminal_preflight_formula_invalid")
            if not eligible:
                raise Doc4ContractError("terminal_eligible_corpus_incomplete")
            call_receipts = receipt.get("token_count_call_receipts")
            expected_hashes = expected_arm_hashes[arm]
            if (
                receipt.get("token_count_calls_total") != 5
                or not isinstance(call_receipts, list)
                or len(call_receipts) != 5
                or tuple(item.get("request_sha256") for item in call_receipts)
                != expected_hashes
            ):
                raise Doc4ContractError("terminal_preflight_call_receipts_invalid")
            for call in call_receipts:
                _validate_provider_call_metadata(
                    call,
                    expected_request_sha256=call["request_sha256"],
                    expected_model_id=None,
                )
            expected_counts = (
                receipt["request_envelope_tokens"],
                receipt["request_envelope_tokens"] + receipt["system_tokens"],
                receipt["request_envelope_tokens"]
                + receipt["system_tokens"]
                + receipt["task_tokens"],
                receipt["request_envelope_tokens"]
                + receipt["system_tokens"]
                + receipt["task_tokens"]
                + receipt["source_tokens"],
                receipt["total_input_tokens"],
            )
            for call, expected_count in zip(
                call_receipts, expected_counts, strict=True
            ):
                raw_payload = call.get("raw_payload")
                if (
                    not isinstance(raw_payload, dict)
                    or call.get("raw_payload_sha256")
                    != sha256_bytes(canonical_json_bytes(raw_payload))
                    or raw_payload.get("input_tokens") != expected_count
                ):
                    raise Doc4ContractError(
                        "terminal_preflight_token_count_payload_invalid"
                    )
            calls_total += 5
    if value.get("provider_calls_total") != calls_total or calls_total != 40:
        raise Doc4ContractError("terminal_preflight_provider_call_count_invalid")


def _validate_terminal_arm_evidence(
    *,
    safe_id: str,
    source_mode: str,
    response: dict[str, Any],
    validated_receipt: dict[str, Any],
    run_trace: dict[str, Any],
    expected_request_sha256: str,
    expected_model_id: str,
) -> None:
    if response.get("source_mode") != source_mode:
        raise Doc4ContractError("terminal_response_source_mode_invalid")
    if validated_receipt.get("schema_version") != "broker_reports_doc4_validated_response_receipt_v1" or validated_receipt.get("integrity_sha256") != integrity_sha256(validated_receipt):
        raise Doc4ContractError("terminal_validated_receipt_invalid")
    if (
        validated_receipt.get("source_mode") != source_mode
        or validated_receipt.get("status") != "PASSED"
        or validated_receipt.get("response_sha256")
        != sha256_bytes(canonical_json_bytes(response))
        or validated_receipt.get("request_sha256") != expected_request_sha256
    ):
        raise Doc4ContractError("terminal_validated_receipt_binding_invalid")
    if run_trace.get("schema_version") != "broker_reports_doc4_arm_run_trace_v1" or run_trace.get("integrity_sha256") != integrity_sha256(run_trace):
        raise Doc4ContractError("terminal_run_trace_invalid")
    if (
        run_trace.get("arm_status") != "PASSED"
        or sha256_bytes(canonical_json_bytes(run_trace.get("request")))
        != expected_request_sha256
    ):
        raise Doc4ContractError("terminal_run_trace_request_binding_invalid")
    attempts = run_trace.get("attempts")
    if not isinstance(attempts, list) or not 1 <= len(attempts) <= 2:
        raise Doc4ContractError("terminal_run_trace_attempts_invalid")
    if run_trace.get("schema_retries_total") != len(attempts) - 1:
        raise Doc4ContractError("terminal_run_trace_schema_retry_invalid")
    if attempts[-1].get("validation_error") is not None:
        raise Doc4ContractError("terminal_run_trace_not_validated")
    if (len(attempts) == 1) != (run_trace.get("first_schema_error") is None):
        raise Doc4ContractError("terminal_run_trace_first_error_invalid")
    for index, attempt in enumerate(attempts):
        metadata = attempt.get("metadata")
        raw_payload = attempt.get("raw_payload")
        if not isinstance(metadata, dict) or not isinstance(raw_payload, dict):
            raise Doc4ContractError("terminal_run_trace_attempt_invalid")
        _validate_provider_call_metadata(
            metadata,
            expected_request_sha256=expected_request_sha256,
            expected_model_id=expected_model_id,
        )
        if raw_payload.get("model") != expected_model_id:
            raise Doc4ContractError("terminal_run_trace_model_invalid")
        if metadata.get("raw_payload_sha256") != sha256_bytes(
            canonical_json_bytes(raw_payload)
        ):
            raise Doc4ContractError("terminal_run_trace_raw_payload_binding_invalid")
        validation_error = attempt.get("validation_error")
        if index < len(attempts) - 1:
            if not isinstance(validation_error, str) or not validation_error:
                raise Doc4ContractError("terminal_run_trace_retry_outcome_invalid")
            continue
        extracted = extract_structured_response(raw_payload)
        if canonical_json_bytes(extracted) != canonical_json_bytes(response):
            raise Doc4ContractError("terminal_run_trace_response_binding_invalid")


def _validate_provider_call_metadata(
    value: dict[str, Any],
    *,
    expected_request_sha256: str,
    expected_model_id: str | None,
) -> None:
    attempts_total = value.get("attempts_total")
    retries_total = value.get("transport_retries_total")
    valid = (
        value.get("http_status") == 200
        and isinstance(attempts_total, int)
        and not isinstance(attempts_total, bool)
        and attempts_total >= 1
        and isinstance(retries_total, int)
        and not isinstance(retries_total, bool)
        and retries_total == attempts_total - 1
        and value.get("http_session_scope") == "ONE_REQUEST_NO_REUSE"
        and value.get("request_sha256") == expected_request_sha256
        and _is_sha256(value.get("response_sha256"))
        and isinstance(value.get("response_bytes"), int)
        and not isinstance(value.get("response_bytes"), bool)
        and value["response_bytes"] > 0
        and isinstance(value.get("duration_seconds"), (int, float))
        and not isinstance(value.get("duration_seconds"), bool)
        and value["duration_seconds"] >= 0
    )
    if expected_model_id is not None:
        valid = valid and value.get("resolved_model") == expected_model_id
    if not valid:
        raise Doc4ContractError("terminal_provider_call_metadata_invalid")


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _terminal_semantic_equivalence(
    *,
    documents: list[dict[str, Any]],
    model_task_adequacy: str,
    metrics: dict[str, Any],
) -> str:
    assessments = {
        item["document_semantic_assessment"] for item in documents
    }
    if "DOCUMENT_FAILED" in assessments or metrics["artifact_semantic_gaps_total"]:
        return "FAILED"
    if model_task_adequacy != "PASSED":
        return "INCONCLUSIVE_MODEL_INADEQUACY"
    if assessments == {"DOCUMENT_PASSED_STRICT"}:
        return "PASSED_STRICT"
    if assessments <= {
        "DOCUMENT_PASSED_STRICT",
        "DOCUMENT_PASSED_WITH_NONCRITICAL_VARIANCE",
    }:
        return "PASSED_WITH_NONCRITICAL_VARIANCE"
    raise Doc4ContractError("terminal_document_assessment_invalid")


def _gold_exact_total(
    gold_by_key: dict[str, dict[str, Any]],
    arm_items: dict[str, dict[str, Any]],
    field: str,
) -> int:
    return sum(
        gold_item.get(field) is not None
        and key in arm_items
        and arm_items[key]["exact"].get(field) == gold_item[field]
        for key, gold_item in gold_by_key.items()
    )


def _structure_order_matches(
    gold_by_key: dict[str, dict[str, Any]],
    arm_items: dict[str, dict[str, Any]],
) -> bool:
    ordered = [
        (key, item["ordinal"])
        for key, item in gold_by_key.items()
        if item["category"] in {"STRUCTURE", "TABLE"} and item["ordinal"] is not None
    ]
    return all(
        key in arm_items and arm_items[key]["exact"].get("ordinal") == ordinal
        for key, ordinal in ordered
    )


def _rate(numerator: int, denominator: int) -> str:
    if numerator < 0 or denominator < 0 or numerator > denominator:
        raise Doc4ContractError("metric_rate_inputs_invalid")
    if denominator == 0:
        return "1.000000"
    return f"{numerator / denominator:.6f}"


def _text_contains(container: str, excerpt: str) -> bool:
    normalized_container = " ".join(container.casefold().split())
    normalized_excerpt = " ".join(excerpt.casefold().split())
    return bool(normalized_excerpt and normalized_excerpt in normalized_container)


def _validate_gold_source_grounding(
    gold: dict[str, Any],
    *,
    pdf_page_texts: tuple[str, ...],
    expected_pdf_pages: int | None = None,
) -> None:
    if expected_pdf_pages is not None and len(pdf_page_texts) != expected_pdf_pages:
        raise Doc4ContractError("gold_pdf_page_text_coverage_invalid")
    for item in gold["items"]:
        if item["category"] == "FINANCIAL_FACT":
            validate_financial_normalizations(item)
        for pointer in item["evidence"]:
            page = pointer["page"]
            if expected_pdf_pages is not None and page > expected_pdf_pages:
                raise Doc4ContractError("gold_pdf_pointer_page_out_of_range")
            evidence_text = pointer["evidence_text"]
            if page > len(pdf_page_texts) or not _text_contains(
                pdf_page_texts[page - 1], evidence_text
            ):
                raise Doc4ContractError("gold_pdf_pointer_evidence_not_on_page")
            if item.get("source_literal") and not _text_contains(
                evidence_text, item["source_literal"]
            ):
                raise Doc4ContractError("gold_pdf_pointer_literal_not_in_evidence")
