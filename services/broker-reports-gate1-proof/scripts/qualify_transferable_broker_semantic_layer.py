#!/usr/bin/env python3
"""Qualify a research-only semantic layer from saved broker-report evidence.

The script deliberately performs no provider calls and does not touch production.
It replays the already saved development and holdout decisions under a contract
that preserves source observations, permits repeated roles, and materializes
runtime facts only through deterministic source-ref bindings.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
SERVICE_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(SERVICE_ROOT))

import qualify_canonical_minimal_semantic_compiler as msc  # noqa: E402
import qualify_canonical_semantic_transferability as transfer  # noqa: E402
import qualify_canonical_typed_broker_registers_benchmark as typed  # noqa: E402


RESULT_VERSION = "broker_transferable_semantic_layer_qualification_v1"
OBSERVATION_VERSION = "broker_source_observation_v1"
FIELD_CONTRACT_VERSION = "broker_source_field_contract_v1"
RUNTIME_BINDING_VERSION = "broker_runtime_binding_v1"
VERDICT = "TRANSFERABLE_WITH_EXPLICIT_BOUNDARIES"


class SemanticLayerQualificationError(RuntimeError):
    pass


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _field_id(*, fingerprint: str, column: int, header_ref: str) -> str:
    return "bsf_" + _sha256_json(
        {
            "fingerprint": fingerprint,
            "column": column,
            "header_ref": header_ref,
        }
    )[:24]


def compile_field_contract(
    *, context: dict[str, Any], mapping: dict[str, Any]
) -> dict[str, Any]:
    """Compile a schema-local field contract; repeated semantic roles are valid."""

    headers = context.get("headers")
    columns = mapping.get("columns")
    if not isinstance(headers, list) or not headers:
        raise SemanticLayerQualificationError("field_contract_headers_required")
    if not isinstance(columns, list) or len(columns) != len(headers):
        raise SemanticLayerQualificationError("field_contract_header_accounting")
    if mapping.get("logical_table_id") != context.get("logical_table_id"):
        raise SemanticLayerQualificationError("field_contract_table_binding")
    expected_refs = [item["source_ref"] for item in headers]
    actual_refs = [item.get("header_ref") for item in columns]
    if actual_refs != expected_refs or len(set(actual_refs)) != len(actual_refs):
        raise SemanticLayerQualificationError("field_contract_header_order")
    if any(item.get("normalized_role") not in msc.NORMALIZED_ROLES for item in columns):
        raise SemanticLayerQualificationError("field_contract_role_invalid")

    fingerprint = transfer.structural_fingerprint(context)
    fields = []
    for header, decision in zip(headers, columns, strict=True):
        fields.append(
            {
                "source_field_id": _field_id(
                    fingerprint=fingerprint,
                    column=int(header["column"]),
                    header_ref=header["source_ref"],
                ),
                "column": int(header["column"]),
                "semantic_role": decision["normalized_role"],
                "source_qualifier": {
                    "kind": "SOURCE_HEADER",
                    "header_ref": header["source_ref"],
                    "header_literal": header["literal"],
                },
            }
        )
    return {
        "schema_version": FIELD_CONTRACT_VERSION,
        "logical_table_id": context["logical_table_id"],
        "table_type": mapping["table_type"],
        "structural_fingerprint": fingerprint,
        "fields": fields,
    }


def validate_saved_h3(
    *, raw: Any, contexts: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Validate saved H3 without the invalid one-role-per-table restriction."""

    value = typed._decode(raw)
    items = value.get("classifications") if isinstance(value, dict) else None
    if not isinstance(items, list) or len(items) != len(contexts):
        raise SemanticLayerQualificationError("h3_table_accounting")
    if [item.get("assertion_id") for item in items] != [
        item["logical_table_id"] for item in contexts
    ]:
        raise SemanticLayerQualificationError("h3_table_order")
    restored = []
    for item, context in zip(items, contexts, strict=True):
        mapping = {
            "logical_table_id": item.get("assertion_id"),
            "table_type": item.get("table_type"),
            "columns": copy.deepcopy(item.get("columns")),
        }
        if mapping["table_type"] not in msc.TABLE_TYPES:
            raise SemanticLayerQualificationError("h3_table_type")
        compile_field_contract(context=context, mapping=mapping)
        restored.append(mapping)
    return restored


def first_persisted_valid_h3(
    *, private_runs: list[dict[str, Any]], contexts: list[dict[str, Any]]
) -> tuple[int, list[dict[str, Any]]]:
    """Use chronological first-valid evidence, never best-of-N selection."""

    for run in sorted(private_runs, key=lambda item: int(item["ordinal"])):
        raw = (run.get("h3") or {}).get("raw_model_output")
        if raw is None:
            continue
        try:
            return int(run["ordinal"]), validate_saved_h3(raw=raw, contexts=contexts)
        except (SemanticLayerQualificationError, ValueError, TypeError):
            continue
    raise SemanticLayerQualificationError("h3_no_persisted_valid_response")


def _observation(
    *,
    canonical_root_sha256: str,
    field_contract: dict[str, Any],
    row: int,
    cells: dict[int, dict[str, Any]],
    disposition: str,
    perspective_ref: str,
) -> dict[str, Any]:
    fields = []
    for field in field_contract["fields"]:
        cell = cells.get(field["column"])
        if cell is None:
            continue
        fields.append(
            {
                "source_field_id": field["source_field_id"],
                "semantic_role": field["semantic_role"],
                "source_qualifier": copy.deepcopy(field["source_qualifier"]),
                "source_ref": cell["source_ref"],
                "literal": cell["literal"],
            }
        )
    source_refs = [field["source_ref"] for field in fields]
    observation_id = "bso_" + _sha256_json(
        {
            "canonical_root_sha256": canonical_root_sha256,
            "logical_table_id": field_contract["logical_table_id"],
            "row": row,
            "source_refs": source_refs,
        }
    )[:32]
    event_key_fields = [
        field
        for field in fields
        if field["semantic_role"] == "trade_id" and field["literal"]
    ]
    return {
        "schema_version": OBSERVATION_VERSION,
        "observation_id": observation_id,
        "canonical_root_sha256": canonical_root_sha256,
        "logical_table_id": field_contract["logical_table_id"],
        "row": row,
        "perspective": {"source_ref": perspective_ref},
        "explicit_event_key": (
            {
                "source_ref": event_key_fields[0]["source_ref"],
                "literal": event_key_fields[0]["literal"],
            }
            if len(event_key_fields) == 1
            else None
        ),
        "disposition": disposition,
        "fields": fields,
    }


def _fields_by_role(observation: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for field in observation["fields"]:
        result.setdefault(field["semantic_role"], []).append(field)
    return result


def _single_field(by_role: dict[str, list[dict[str, Any]]], role: str) -> dict[str, Any]:
    values = [item for item in by_role.get(role, []) if item["literal"]]
    if len(values) != 1:
        raise SemanticLayerQualificationError(f"runtime_role_{role}_ambiguous")
    return values[0]


def _gross_currency(
    *, observation: dict[str, Any], field_contract: dict[str, Any]
) -> dict[str, Any]:
    """Bind currency only when one source currency is adjacent to gross amount."""

    contract_by_id = {
        item["source_field_id"]: item for item in field_contract["fields"]
    }
    by_role = _fields_by_role(observation)
    gross = _single_field(by_role, "gross_amount")
    gross_column = contract_by_id[gross["source_field_id"]]["column"]
    candidates = [
        item
        for item in by_role.get("currency", [])
        if item["literal"]
        and abs(contract_by_id[item["source_field_id"]]["column"] - gross_column) == 1
    ]
    if len(candidates) != 1:
        raise SemanticLayerQualificationError("runtime_gross_currency_ambiguous")
    return candidates[0]


def _runtime_role(role: str, field: dict[str, Any]) -> dict[str, str]:
    return {
        "role": role,
        "source_ref": field["source_ref"],
        "literal_fragment": field["literal"],
    }


def materialize_trade_facts(
    *,
    observation: dict[str, Any],
    field_contract: dict[str, Any],
    side_by_literal: dict[str, str],
) -> list[dict[str, Any]]:
    by_role = _fields_by_role(observation)
    asset = _single_field(by_role, "asset_name")
    date = _single_field(by_role, "trade_date")
    side = _single_field(by_role, "side")
    quantity = _single_field(by_role, "quantity")
    unit_price = _single_field(by_role, "unit_price")
    amount = _single_field(by_role, "gross_amount")
    currency = _gross_currency(
        observation=observation,
        field_contract=field_contract,
    )
    normalized_side = side_by_literal.get(side["literal"])
    if normalized_side not in {"PURCHASE", "DISPOSAL"}:
        raise SemanticLayerQualificationError("runtime_side_unmapped")
    common_claims = [side["source_ref"]]
    facts = [
        {
            "record_type": (
                "SECURITY_PURCHASE"
                if normalized_side == "PURCHASE"
                else "SECURITY_DISPOSAL"
            ),
            "claim_refs": common_claims,
            "roles": [
                _runtime_role("date", date),
                _runtime_role("asset", asset),
                _runtime_role("quantity", quantity),
                _runtime_role("unit_price", unit_price),
                _runtime_role("amount", amount),
                _runtime_role("currency", currency),
            ],
            "withholding_status": "NOT_APPLICABLE",
        }
    ]
    for commission in by_role.get("broker_commission", []):
        if not commission["literal"] or typed._is_zero_literal(commission["literal"]):
            continue
        facts.append(
            {
                "record_type": "TRANSACTION_CHARGE",
                "claim_refs": [commission["source_ref"]],
                "roles": [
                    _runtime_role("date", date),
                    _runtime_role("asset", asset),
                    _runtime_role("amount", commission),
                    _runtime_role("currency", currency),
                ],
                "withholding_status": "NOT_APPLICABLE",
            }
        )
    for fact in facts:
        fact["typed_record_id"] = "bstr_" + _sha256_json(
            {
                "observation_id": observation["observation_id"],
                "record_type": fact["record_type"],
                "refs": [item["source_ref"] for item in fact["roles"]],
            }
        )[:32]
        fact["source_observation_id"] = observation["observation_id"]
    return facts


def _validate_source_accounting(observations: list[dict[str, Any]], expected: int) -> None:
    if len(observations) != expected:
        raise SemanticLayerQualificationError("source_accounting_count")
    identities = [item["observation_id"] for item in observations]
    if len(identities) != len(set(identities)):
        raise SemanticLayerQualificationError("source_observation_identity_duplicate")


def _validate_runtime_lineage(
    *, observations: list[dict[str, Any]], facts: list[dict[str, Any]]
) -> tuple[int, int]:
    literals = {
        (observation["observation_id"], field["source_ref"]): field["literal"]
        for observation in observations
        for field in observation["fields"]
    }
    values = 0
    traced = 0
    for fact in facts:
        observation_id = fact["source_observation_id"]
        for role in fact["roles"]:
            values += 1
            source_literal = literals.get((observation_id, role["source_ref"]))
            literal_fragment = role["literal_fragment"]
            if (
                not isinstance(source_literal, str)
                or not isinstance(literal_fragment, str)
                or not literal_fragment
                or literal_fragment not in source_literal
            ):
                raise SemanticLayerQualificationError("runtime_value_not_from_source")
            traced += 1
    return values, traced


def _holdout_replay(
    *, review: dict[str, Any], truth: dict[str, Any], results: dict[str, Any]
) -> dict[str, Any]:
    documents = {item["alias"]: item for item in review["documents"]}
    contexts: dict[str, dict[str, Any]] = {}
    cells_by_case: dict[str, dict[tuple[int, int], dict[str, Any]]] = {}
    for spec in truth["cases"]:
        context, cells = transfer._table_context(
            document=documents[spec["document_alias"]],
            spec=spec,
        )
        contexts[spec["case_id"]] = context
        cells_by_case[spec["case_id"]] = cells
    ordered_contexts = [contexts[item["case_id"]] for item in truth["cases"]]
    selected_run, mappings = first_persisted_valid_h3(
        private_runs=results["private_runs"],
        contexts=ordered_contexts,
    )
    run = next(item for item in results["private_runs"] if item["ordinal"] == selected_run)
    side_by_literal = {
        item["source_literal"]: item["normalized_value"]
        for item in run["h6"]["bindings"]
    }
    mapping_by_id = {item["logical_table_id"]: item for item in mappings}
    contracts = {
        case_id: compile_field_contract(
            context=contexts[case_id], mapping=mapping_by_id[case_id]
        )
        for case_id in mapping_by_id
    }
    observations: list[dict[str, Any]] = []
    facts: list[dict[str, Any]] = []
    materialized_primary = 0
    for spec in truth["cases"]:
        case_id = spec["case_id"]
        perspective_ref = (
            (contexts[case_id].get("table_identity") or {}).get("source_ref")
            or contexts[case_id]["headers"][0]["source_ref"]
        )
        for row in spec["materialization_rows"]:
            row_cells = {
                column: value
                for (cell_row, column), value in cells_by_case[case_id].items()
                if cell_row == int(row)
            }
            observation = _observation(
                canonical_root_sha256=documents[spec["document_alias"]][
                    "canonical_root_sha256"
                ],
                field_contract=contracts[case_id],
                row=int(row),
                cells=row_cells,
                disposition=(
                    "RUNTIME_READY"
                    if mapping_by_id[case_id]["table_type"] == "SECURITY_TRADES"
                    else "RELEVANT_UNMAPPED"
                ),
                perspective_ref=perspective_ref,
            )
            observations.append(observation)
            if observation["disposition"] == "RUNTIME_READY":
                row_facts = materialize_trade_facts(
                    observation=observation,
                    field_contract=contracts[case_id],
                    side_by_literal=side_by_literal,
                )
                facts.extend(row_facts)
                materialized_primary += int(bool(row_facts))

    residual_batch, _ = transfer._residual_batch(documents=documents, truth=truth)
    for ordinal, record in enumerate(residual_batch["records"], 1):
        literal = record["source_wording"]
        source_ref = record["source_wording_ref"]
        observation_id = "bso_" + _sha256_json(
            {
                "source_record_id": record["source_record_id"],
                "source_ref": source_ref,
            }
        )[:32]
        observations.append(
            {
                "schema_version": OBSERVATION_VERSION,
                "observation_id": observation_id,
                "canonical_root_sha256": "bound_in_source_ref",
                "logical_table_id": "mixed_cash_operations",
                "row": ordinal,
                "perspective": {"source_ref": source_ref},
                "explicit_event_key": None,
                "disposition": "RELEVANT_UNMAPPED",
                "fields": [
                    {
                        "source_field_id": "bsf_" + _sha256_json(source_ref)[:24],
                        "semantic_role": "description",
                        "source_qualifier": {
                            "kind": "SOURCE_HEADER",
                            "header_ref": source_ref,
                            "header_literal": "",
                        },
                        "source_ref": source_ref,
                        "literal": literal,
                    }
                ],
            }
        )

    expected_records = sum(len(item["materialization_rows"]) for item in truth["cases"]) + len(
        truth["residuals"]
    )
    _validate_source_accounting(observations, expected_records)
    values, traced = _validate_runtime_lineage(observations=observations, facts=facts)
    primary_required = sum(
        len(item["materialization_rows"])
        for item in truth["cases"]
        if item["expected_table_type"] == "SECURITY_TRADES"
    )
    if materialized_primary != primary_required:
        raise SemanticLayerQualificationError("holdout_primary_facts_incomplete")
    projection = {
        "schema_version": RUNTIME_BINDING_VERSION,
        "source_observations": observations,
        "runtime_facts": facts,
    }
    return {
        "selected_h3_run": selected_run,
        "selection_policy": "chronological_first_persisted_contract_valid",
        "source_records": len(observations),
        "source_records_accounted": len(observations),
        "runtime_facts": len(facts),
        "required_primary_facts": primary_required,
        "supplied_primary_facts": materialized_primary,
        "runtime_values": values,
        "runtime_values_traced": traced,
        "repeated_role_counts": {
            case_id: {
                role: len(items)
                for role, items in _group_contract_roles(contract).items()
                if len(items) > 1
            }
            for case_id, contract in contracts.items()
        },
        "unmapped_records": sum(
            item["disposition"] == "RELEVANT_UNMAPPED" for item in observations
        ),
        "projection_sha256": _sha256_json(projection),
        "private_projection": projection,
    }


def _group_contract_roles(
    contract: dict[str, Any]
) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for field in contract["fields"]:
        result.setdefault(field["semantic_role"], []).append(field)
    return result


def _development_replay(
    *,
    source_plan: dict[str, Any],
    source_truth: dict[str, Any],
    semantic_truth: dict[str, Any],
    task_runs: list[dict[str, Any]],
) -> dict[str, Any]:
    source_batch = source_plan["source_batch"]
    trade_id = semantic_truth["mapping_benchmark_table_id"]
    hashes = []
    metrics_by_run = []
    first_projection: dict[str, Any] | None = None
    first_header: list[dict[str, Any]] | None = None
    for task_run in task_runs:
        header = task_run["H3_ALL_TABLES_FORWARD_REFS"]["validated"]
        side = task_run["H6_SIDE_SINGLE_PURCHASE_REF"]["validated"]
        residual = task_run["H8_RESIDUAL_TABLE_CONTRACTS"]["validated"]
        trade_mapping_value = next(
            item for item in header if item["logical_table_id"] == trade_id
        )
        trade_mapping = {
            "assertion_id": trade_id,
            "table_type": trade_mapping_value["table_type"],
            "columns": trade_mapping_value["columns"],
            "value_bindings": side,
        }
        trade_projection, _ = msc.deterministic_trade_projection(
            source_batch=source_batch,
            mapping=trade_mapping,
        )
        semantic_for_materialization = copy.deepcopy(semantic_truth)
        actual_by_id = {item["logical_table_id"]: item for item in header}
        for mapping in semantic_for_materialization["schema_mappings"]:
            actual = actual_by_id[mapping["logical_table_id"]]
            mapping["columns"] = copy.deepcopy(actual["columns"])
            mapping["table_type"] = actual["table_type"]
        residual_projection = msc.materialize_residuals(
            response=residual,
            source_batch=source_batch,
            semantic_truth=semantic_for_materialization,
        )
        projection = msc.merge_projection(
            source_batch=source_batch,
            trade=trade_projection,
            residual=residual_projection,
        )
        metrics = typed.score_projection(
            projection=projection,
            truth=source_truth,
            batch=source_batch,
            deterministic_source_ids={"r004", "r005", "r006"},
            execution=[],
        )
        if (
            metrics["missing_typed_records"]
            or metrics["extra_typed_records"]
            or metrics["exact_typed_records_correct"]
            != metrics["expected_typed_records"]
            or not metrics["source_accounting_exact"]
        ):
            raise SemanticLayerQualificationError("development_replay_not_exact")
        hashes.append(metrics["projection_sha256"])
        metrics_by_run.append(metrics)
        if first_projection is None:
            first_projection = copy.deepcopy(projection)
            first_header = copy.deepcopy(header)
    if len(set(hashes)) != 1:
        raise SemanticLayerQualificationError("development_projection_not_repeatable")
    first = metrics_by_run[0]
    if first_projection is None or first_header is None:
        raise SemanticLayerQualificationError("development_projection_missing")
    mapping_by_id = {item["logical_table_id"]: item for item in first_header}
    contexts: dict[str, dict[str, Any]] = {}
    for row in source_batch["source_records"]:
        table_id = row["logical_table_id"]
        candidate = {
            "logical_table_id": table_id,
            "headers": copy.deepcopy(row["header_context"]),
        }
        existing = contexts.setdefault(table_id, candidate)
        if existing != candidate:
            raise SemanticLayerQualificationError("development_header_changed")
    contracts = {
        table_id: compile_field_contract(
            context=context,
            mapping=mapping_by_id[table_id],
        )
        for table_id, context in contexts.items()
    }
    classification_by_id = {
        item["assertion_id"]: item for item in first_projection["classifications"]
    }
    observations = []
    runtime_facts = []
    for ordinal, row in enumerate(source_batch["source_records"], 1):
        classification = classification_by_id[row["source_record_id"]]
        observation = _observation(
            canonical_root_sha256=source_truth["frozen_canonical_root_sha256"],
            field_contract=contracts[row["logical_table_id"]],
            row=ordinal,
            cells={int(item["column"]): item for item in row["elements"]},
            disposition=(
                "RUNTIME_READY"
                if classification["disposition"] == "MATERIALIZED"
                else classification["disposition"]
            ),
            perspective_ref=row["header_context"][0]["source_ref"],
        )
        observations.append(observation)
        for record in classification["typed_records"]:
            restored = copy.deepcopy(record)
            restored["source_observation_id"] = observation["observation_id"]
            runtime_facts.append(restored)
    _validate_source_accounting(observations, len(source_batch["source_records"]))
    runtime_values, traced_values = _validate_runtime_lineage(
        observations=observations,
        facts=runtime_facts,
    )
    return {
        "runs": len(task_runs),
        "source_records": len(source_batch["source_records"]),
        "source_records_accounted": len(source_batch["source_records"]),
        "required_facts": first["expected_typed_records"],
        "supplied_facts": first["exact_typed_records_correct"],
        "runtime_values": runtime_values,
        "runtime_values_traced": traced_values,
        "projection_sha256": hashes[0],
        "private_projection": {
            "schema_version": RUNTIME_BINDING_VERSION,
            "source_observations": observations,
            "runtime_facts": runtime_facts,
        },
    }


def qualify(args: argparse.Namespace) -> dict[str, Any]:
    source_plan = _read_json(args.typed_plan)
    source_truth = _read_json(args.typed_truth)
    semantic_truth = _read_json(args.semantic_truth)
    task_runs = [_read_json(path) for path in args.task_run]
    holdout_review = _read_json(args.holdout_review)
    holdout_truth = _read_json(args.holdout_truth)
    holdout_results = _read_json(args.holdout_results)
    prior_receipt = _read_json(args.prior_transferability_receipt)

    development = _development_replay(
        source_plan=source_plan,
        source_truth=source_truth,
        semantic_truth=semantic_truth,
        task_runs=task_runs,
    )
    holdout = _holdout_replay(
        review=holdout_review,
        truth=holdout_truth,
        results=holdout_results,
    )
    development_projection_copy = copy.deepcopy(
        development.pop("private_projection")
    )
    holdout_projection_copy = copy.deepcopy(holdout.pop("private_projection"))
    total_records = development["source_records"] + holdout["source_records"]
    accounted = (
        development["source_records_accounted"]
        + holdout["source_records_accounted"]
    )
    runtime_values = development["runtime_values"] + holdout["runtime_values"]
    traced_values = (
        development["runtime_values_traced"] + holdout["runtime_values_traced"]
    )
    required_facts = development["required_facts"] + holdout["required_primary_facts"]
    supplied_facts = development["supplied_facts"] + holdout["supplied_primary_facts"]
    row_level_llm_records = len(semantic_truth["residuals"]) + len(
        holdout_truth["residuals"]
    )
    result = {
        "schema_version": RESULT_VERSION,
        "verdict": VERDICT,
        "report": "docs/reports/2026-08-21/BROKER_REPORTS_TRANSFERABLE_SEMANTIC_LAYER.md",
        "production_changed": False,
        "provider_calls_in_replay": 0,
        "legacy_fallback_used": False,
        "new_broker_or_year_profiles": 0,
        "selected_contract": {
            "source_owner": OBSERVATION_VERSION,
            "schema_field_owner": FIELD_CONTRACT_VERSION,
            "consumer_binding_owner": RUNTIME_BINDING_VERSION,
            "canonical_mutated": False,
            "repeated_roles_allowed": True,
            "qualifier_kind": "source_header_ref_and_literal",
            "value_based_deduplication": False,
            "unknown_terminal": "RELEVANT_UNMAPPED",
        },
        "candidate_comparison": [
            {
                "candidate": "flat_unique_role_dialect",
                "verdict": "REJECTED",
                "reason": "cannot_represent_repeated_source_roles",
            },
            {
                "candidate": "generic_eav_without_runtime_binding",
                "verdict": "REJECTED",
                "reason": "source_faithful_but_not_gate5_sufficient",
            },
            {
                "candidate": "global_event_ontology",
                "verdict": "REJECTED",
                "reason": "unbounded_vocabulary_and_profile_growth",
            },
            {
                "candidate": "source_observation_plus_schema_local_fields_plus_runtime_binding",
                "verdict": "SELECTED_WITH_BOUNDARIES",
                "reason": "preserves_source_and_keeps_gate5_adapter_deterministic",
            },
        ],
        "development": development,
        "holdout": holdout,
        "metrics": {
            "source_records_accounted": {
                "numerator": accounted,
                "denominator": total_records,
                "percent": round(100 * accounted / total_records, 2),
            },
            "runtime_values_deterministic": {
                "numerator": traced_values,
                "denominator": runtime_values,
                "percent": round(100 * traced_values / runtime_values, 2),
            },
            "source_records_requiring_row_level_llm": {
                "numerator": row_level_llm_records,
                "denominator": total_records,
                "percent": round(100 * row_level_llm_records / total_records, 2),
                "scope_note": "saved_selected_rows; schema decisions are amortized per exact fingerprint",
            },
            "gate5_required_facts_supplied_within_qualified_boundary": {
                "numerator": supplied_facts,
                "denominator": required_facts,
                "percent": round(100 * supplied_facts / required_facts, 2),
            },
            "new_special_rules_or_profiles": 0,
        },
        "amortization_evidence": {
            "mixed_cash_rows": prior_receipt["semantic_surface"][
                "cross_broker_cash_rows"
            ],
            "unique_operation_literals": prior_receipt["semantic_surface"][
                "cross_broker_unique_operation_literals"
            ],
            "decision_equivalent_percent": round(
                100
                * prior_receipt["semantic_surface"][
                    "cross_broker_unique_operation_literals"
                ]
                / prior_receipt["semantic_surface"]["cross_broker_cash_rows"],
                2,
            ),
            "status": "PROMISING_NOT_RUNTIME_QUALIFIED",
        },
        "explicit_boundaries": [
            "multi_page_continuation_requires_explicit_structural_lineage_link",
            "runtime_binding_requires_unambiguous_field_relation_or_fails_closed",
            "repo_and_unknown_operation_meanings_remain_relevant_unmapped",
            "mixed_operation_literal_reuse_is_not_yet_end_to_end_gate5_qualified",
            "holdout_primary_fact_score_covers_ordinary_security_trades_only",
        ],
        "privacy": {
            "raw_customer_documents_in_git": False,
            "raw_canonical_in_git": False,
            "raw_model_responses_in_git": False,
            "private_projection_outside_repository": True,
        },
    }
    private_result = copy.deepcopy(result)
    private_result["development_private_projection"] = development_projection_copy
    private_result["holdout_private_projection"] = holdout_projection_copy
    _write_json(args.private_output, private_result)
    _write_json(args.safe_receipt, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--typed-plan", type=Path, required=True)
    parser.add_argument("--typed-truth", type=Path, required=True)
    parser.add_argument("--semantic-truth", type=Path, required=True)
    parser.add_argument("--task-run", type=Path, action="append", required=True)
    parser.add_argument("--holdout-review", type=Path, required=True)
    parser.add_argument("--holdout-truth", type=Path, required=True)
    parser.add_argument("--holdout-results", type=Path, required=True)
    parser.add_argument("--prior-transferability-receipt", type=Path, required=True)
    parser.add_argument("--private-output", type=Path, required=True)
    parser.add_argument("--safe-receipt", type=Path, required=True)
    args = parser.parse_args()
    result = qualify(args)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
