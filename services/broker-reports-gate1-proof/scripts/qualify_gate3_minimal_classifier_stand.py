#!/usr/bin/env python3
"""Research-only A/B qualification of a closed Gate 3 machine classifier."""

from __future__ import annotations

import argparse
import asyncio
from collections import Counter
import copy
from dataclasses import asdict, is_dataclass
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import sys
from types import SimpleNamespace
from typing import Any

import requests


SCRIPT_DIR = Path(__file__).resolve().parent
SERVICE_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SERVICE_ROOT.parents[1]
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(SERVICE_ROOT))

from broker_reports_gate1 import (  # noqa: E402
    ArtifactAccessContext,
    ArtifactStoreConfig,
    ArtifactStoreFactory,
    Gate3StructuralChunkFactory,
)
from broker_reports_gate1.gate2_model_clients import (  # noqa: E402
    Gate2StructuredModelClientFactory,
)
from broker_reports_gate1.gate2_model_contracts import (  # noqa: E402
    Gate2StructuredModelClientConfig,
    gate2_provider_profile,
)
from broker_reports_gate1.gate2_model_requests import (  # noqa: E402
    GATE3_BOUNDED_LABELING_REQUEST_PROFILE,
)
from broker_reports_gate1.gate3_financial_label_dictionary import (  # noqa: E402
    GATE3_DICTIONARY_CURRENT_VERSION,
    Gate3FinancialLabelDictionaryFactory,
)
from broker_reports_gate1.gate3_ndfl_workflow import (  # noqa: E402
    NDFL_PROVIDER_MODEL_ID,
    NDFL_PROVIDER_PROFILE_ID,
)
from live_gate2_economy_contract_qualification import (  # noqa: E402
    _completion_boundary,
    _published_model_ids,
    _request_context,
)
from live_gate2_synthetic_extraction_smoke import _current_user  # noqa: E402
from live_no_rag_source_intake_smoke import (  # noqa: E402
    _base_url,
    _read_env,
    _signin,
    _url,
)


FROZEN_CANONICAL_ROOT_SHA256 = (
    "bbf20e4ea5cd706398d459716fdab60812ef48ed6b0cd2d0264a778a77ab079d"
)
EXPECTED_CURRENT_TARGETS = 2236
RUNS = 3
RESPONSE_SCHEMA_VERSION = "broker_reports_gate3_minimal_classifier_response_v1"
INSTRUCTION_ID = "broker-reports-gate3-minimal-closed-machine-classifier"
INSTRUCTION_VERSION = "0.1.0-research-only"
INSTRUCTION = (
    "Код заранее объявил все существующие source objects в этом batch. "
    "Верни для каждого object_id ровно одно решение, в исходном порядке; "
    "в assertion_id скопируй exact object_id. "
    "Выбери только один machine_code из закрытого catalog. Не создавай, не "
    "переименовывай и не пропускай объекты или коды. Классифицируй только "
    "local_source_text; table_header_context и row_context разрешены лишь для "
    "понимания этого exact object. Если object не утверждает ровно один "
    "разрешённый financial meaning, включая compound object с несколькими "
    "независимыми meanings, верни F00. Не извлекай роли или значения, не "
    "делай вычислений, связей, налоговых выводов или пояснений. Верни только "
    "Gate3MinimalClassifierResponseV1."
)

MACHINE_CODE_TO_LABEL = {
    "F01": "SECURITY_PURCHASE",
    "F02": "SECURITY_DISPOSAL",
    "F03": "DIVIDEND_INCOME",
    "F04": "COUPON_INCOME",
    "F05": "INTEREST_INCOME",
    "F06": "SECURITIES_LENDING_INCOME",
    "F07": "ACCRUED_COUPON_COMPONENT",
    "F08": "TRANSACTION_CHARGE",
    "F09": "COMMISSION",
    "F10": "COMMISSION_TOTAL",
    "F11": "TAX_WITHHELD",
    "F12": "TAX_WITHHELD_TOTAL",
}
UNMAPPED_CODE = "F00"

FACTORY_REQUIRED = (
    "ArtifactStoreFactory.create, Gate3StructuralChunkFactory.create and "
    "Gate2StructuredModelClientFactory.create are the only research path"
)
FORBIDDEN = (
    "production activation, bundle inclusion, Gate 4/5, PDF reads, retry, "
    "repair, best-of-N, free-text labels, new financial meanings or roles"
)


class MinimalClassifierStandError(RuntimeError):
    pass


def machine_code_catalog() -> list[dict[str, Any]]:
    dictionary = Gate3FinancialLabelDictionaryFactory.create().load_published(
        GATE3_DICTIONARY_CURRENT_VERSION
    )
    by_label = {item["label_id"]: item for item in dictionary["labels"]}
    if set(by_label) != set(MACHINE_CODE_TO_LABEL.values()):
        raise MinimalClassifierStandError("current_dictionary_code_map_drift")
    catalog = [
        {
            "machine_code": UNMAPPED_CODE,
            "existing_financial_label": None,
            "meaning": (
                "Exact source object does not assert exactly one published "
                "financial meaning, or asserts several independent meanings."
            ),
        }
    ]
    for code, label_id in MACHINE_CODE_TO_LABEL.items():
        label = by_label[label_id]
        catalog.append(
            {
                "machine_code": code,
                "existing_financial_label": label_id,
                "meaning": label["meaning"],
                "apply_when": copy.deepcopy(label["apply_when"]),
                "do_not_apply_when": copy.deepcopy(label["do_not_apply_when"]),
            }
        )
    return catalog


def response_schema(object_ids: list[str]) -> dict[str, Any]:
    if not object_ids or object_ids != list(dict.fromkeys(object_ids)):
        raise MinimalClassifierStandError("source_object_ids_invalid")
    codes = [UNMAPPED_CODE, *MACHINE_CODE_TO_LABEL]
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["schema_version", "decisions"],
        "properties": {
            "schema_version": {"const": RESPONSE_SCHEMA_VERSION},
            "decisions": {
                "type": "array",
                "minItems": len(object_ids),
                "maxItems": len(object_ids),
                "items": {"$ref": "#/$defs/classification"},
            },
        },
        "$defs": {
            "classification": {
                "type": "object",
                "additionalProperties": False,
                "required": ["assertion_id", "machine_code"],
                "properties": {
                    "assertion_id": {
                        "type": "string",
                        "pattern": "^o[0-9]{3}$",
                        "description": (
                            "Exact predeclared object_id from the batch; copy it "
                            "without brackets, prefixes or explanations."
                        ),
                    },
                    "machine_code": {"type": "string", "enum": codes},
                },
            }
        },
    }


def validate_response(raw: Any, *, object_ids: list[str]) -> dict[str, Any]:
    value = _decode_json(raw)
    if (
        set(value) != {"schema_version", "decisions"}
        or value.get("schema_version") != RESPONSE_SCHEMA_VERSION
        or not isinstance(value.get("decisions"), list)
    ):
        raise MinimalClassifierStandError("classifier_response_contract_invalid")
    decisions = value["decisions"]
    if len(decisions) != len(object_ids):
        raise MinimalClassifierStandError("classifier_response_coverage_invalid")
    actual_ids: list[str] = []
    allowed_codes = {UNMAPPED_CODE, *MACHINE_CODE_TO_LABEL}
    restored: list[dict[str, str]] = []
    for item in decisions:
        if (
            not isinstance(item, dict)
            or set(item) != {"assertion_id", "machine_code"}
            or not isinstance(item.get("assertion_id"), str)
            or item.get("machine_code") not in allowed_codes
        ):
            raise MinimalClassifierStandError(
                "classifier_response_contract_invalid"
            )
        actual_ids.append(item["assertion_id"])
        restored.append(
            {
                "object_id": item["assertion_id"],
                "machine_code": item["machine_code"],
            }
        )
    if actual_ids != object_ids:
        if len(actual_ids) != len(set(actual_ids)):
            code = "classifier_response_object_duplicate"
        elif set(actual_ids) != set(object_ids):
            code = "classifier_response_object_unknown"
        else:
            code = "classifier_response_order_invalid"
        raise MinimalClassifierStandError(code)
    return {
        "schema_version": "broker_reports_gate3_minimal_classification_v1",
        "instruction_identity": {
            "instruction_id": INSTRUCTION_ID,
            "semantic_version": INSTRUCTION_VERSION,
        },
        "decisions": restored,
        "explicit_coverage": len(restored),
        "validation_status": "validated",
    }


def verdict(
    *,
    candidate_hashes: list[str],
    candidate_correct: list[int],
    objects_total: int,
    baseline_correct: list[int],
) -> str:
    if (
        len(candidate_hashes) == RUNS
        and len(set(candidate_hashes)) == 1
        and min(candidate_correct, default=-1) == objects_total
        and sum(candidate_correct) > sum(baseline_correct)
    ):
        return "CLOSED_MACHINE_CLASSIFIER_REPEATABILITY_PROVEN"
    if (
        len(candidate_hashes) == RUNS
        and min(candidate_correct, default=-1) >= max(baseline_correct, default=0)
    ):
        return "CLOSED_MACHINE_CLASSIFIER_PROMISING"
    return "INDEXED_CLASSIFIER_DOES_NOT_SOLVE_GATE3_VARIANCE"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute-three-runs", action="store_true")
    parser.add_argument("--env-file", type=Path, default=REPO_ROOT / ".env")
    parser.add_argument("--private-store-root", type=Path, required=True)
    parser.add_argument("--current-runs-dir", type=Path, required=True)
    parser.add_argument("--private-source-truth", type=Path, required=True)
    parser.add_argument("--private-results-dir", type=Path, required=True)
    parser.add_argument("--safe-receipt-path", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=int, default=600)
    args = parser.parse_args()
    if not args.execute_three_runs:
        raise SystemExit("explicit_execute_flag_required")
    if not 1 <= args.timeout_seconds <= 900:
        raise SystemExit("timeout_out_of_bounds")

    store_root = args.private_store_root.resolve()
    current_runs_dir = args.current_runs_dir.resolve()
    source_truth_path = args.private_source_truth.resolve()
    private_results = args.private_results_dir.resolve()
    safe_receipt = args.safe_receipt_path.resolve()
    for private_path in (
        store_root,
        current_runs_dir,
        source_truth_path,
        private_results,
    ):
        if _is_within(private_path, REPO_ROOT.resolve()):
            raise SystemExit("private_evidence_must_be_outside_repository")
    if not _is_within(safe_receipt, REPO_ROOT.resolve()):
        raise SystemExit("safe_receipt_must_be_inside_repository")
    if private_results.exists() and any(private_results.iterdir()):
        raise SystemExit("private_results_must_be_new_or_empty")
    private_results.mkdir(parents=True, exist_ok=True)

    source_truth_raw = source_truth_path.read_bytes()
    source_truth = _validated_source_truth(json.loads(source_truth_raw))
    store = ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=store_root / "artifacts.sqlite3",
            payload_root=store_root / "payloads",
        )
    ).create()
    document_id, context = _frozen_context(store_root)
    chunk_set = Gate3StructuralChunkFactory(store=store, read_enabled=True).create(
        document_id=document_id,
        context=context,
    )
    if (
        len(chunk_set["chunks"]) != 1
        or chunk_set["coverage"]["eligible_targets"]
        != EXPECTED_CURRENT_TARGETS
        or chunk_set["coverage"]["lost_targets"] != 0
        or chunk_set["coverage"]["duplicated_working_targets"] != 0
    ):
        raise SystemExit("frozen_canonical_seam_changed")
    chunk = chunk_set["chunks"][0]
    batch = _build_batch(chunk=chunk, source_truth=source_truth)
    object_ids = [item["object_id"] for item in batch["objects"]]
    schema = response_schema(object_ids)
    request = _model_request(batch=batch, schema=schema)
    request_sha256 = _stable_sha256(request)

    baseline = _current_baseline(
        current_runs_dir=current_runs_dir,
        chunk=chunk,
        source_truth=source_truth,
    )
    context_audit = _current_context_audit(
        current_runs_dir=current_runs_dir,
        chunk=chunk,
    )
    plan = {
        "schema_version": "broker_reports_gate3_minimal_classifier_plan_v1",
        "goal": "Gate 3 Minimal Classifier Stand",
        "frozen_canonical_root_sha256": FROZEN_CANONICAL_ROOT_SHA256,
        "source_truth_sha256": hashlib.sha256(source_truth_raw).hexdigest(),
        "objects": copy.deepcopy(batch["objects"]),
        "expected_codes": {
            item["object_id"]: item["expected_code"]
            for item in source_truth["objects"]
        },
        "machine_code_catalog": machine_code_catalog(),
        "model_visible_request": request,
        "request_sha256": request_sha256,
        "provider_profile_id": NDFL_PROVIDER_PROFILE_ID,
        "model_id": NDFL_PROVIDER_MODEL_ID,
        "runs": RUNS,
        "semantic_retry": False,
        "repair": False,
        "best_of_n": False,
        "role_pass": False,
        "production_activation": False,
    }
    _atomic_write(private_results / "frozen-plan.private.json", _json_bytes(plan))

    client, submissions = _live_client(
        env_file=args.env_file,
        timeout_seconds=args.timeout_seconds,
    )
    candidate_runs: list[dict[str, Any]] = []
    for ordinal in range(1, RUNS + 1):
        before = submissions["count"]
        model_result = asyncio.run(
            client.label_gate3_once(
                model_visible_request=request,
                canonical_schema=schema,
                model_id=NDFL_PROVIDER_MODEL_ID,
            )
        )
        validated = validate_response(
            model_result.adapter_extracted_output,
            object_ids=object_ids,
        )
        if _stable_sha256(request) != request_sha256:
            raise SystemExit("frozen_request_mutated")
        private = {
            "ordinal": ordinal,
            "validated_output": validated,
            "raw_model_output": copy.deepcopy(
                model_result.adapter_extracted_output
            ),
            "raw_provider_response": copy.deepcopy(
                model_result.raw_provider_response
            ),
            "execution_metadata": _plain(model_result.execution_metadata),
            "operational_retry_receipt": copy.deepcopy(
                getattr(model_result, "operational_retry_receipt", None)
            ),
        }
        _atomic_write(
            private_results / f"run-{ordinal}.private.json",
            _json_bytes(private),
        )
        candidate_runs.append(
            _safe_candidate_run(
                ordinal=ordinal,
                validated=validated,
                source_truth=source_truth,
                execution_metadata=model_result.execution_metadata,
                submissions=submissions["count"] - before,
            )
        )

    candidate_hashes = [item["mapping_sha256"] for item in candidate_runs]
    candidate_correct = [item["source_truth_correct"] for item in candidate_runs]
    baseline_correct = [item["source_truth_correct"] for item in baseline]
    final_terminal = verdict(
        candidate_hashes=candidate_hashes,
        candidate_correct=candidate_correct,
        objects_total=len(object_ids),
        baseline_correct=baseline_correct,
    )
    receipt = {
        "schema_version": "broker_reports_gate3_minimal_classifier_receipt_v1",
        "status": final_terminal,
        "terminals": [
            "CURRENT_GATE3_CONTEXT_EXCESSIVE_FREEDOM_PROVEN",
            final_terminal,
        ],
        "research_only": True,
        "production_changed": False,
        "frozen_canonical_root_sha256": FROZEN_CANONICAL_ROOT_SHA256,
        "source_truth_sha256": hashlib.sha256(source_truth_raw).hexdigest(),
        "source_truth_objects": len(object_ids),
        "source_truth_classified": sum(
            item["expected_code"] != UNMAPPED_CODE
            for item in source_truth["objects"]
        ),
        "source_truth_unmapped": sum(
            item["expected_code"] == UNMAPPED_CODE
            for item in source_truth["objects"]
        ),
        "current_context_audit": context_audit,
        "current_baseline": baseline,
        "closed_classifier": {
            "object_unit": "existing_canonical_table_cell",
            "context_only": ["same_table_header", "same_source_row"],
            "machine_codes": len(MACHINE_CODE_TO_LABEL),
            "unmapped_code": UNMAPPED_CODE,
            "request_sha256": request_sha256,
            "instruction_sha256": hashlib.sha256(
                INSTRUCTION.encode("utf-8")
            ).hexdigest(),
            "response_schema_sha256": _stable_sha256(schema),
            "runs": candidate_runs,
            "exact_mapping_repeatability": len(set(candidate_hashes)) == 1,
            "explicit_coverage_each_run": all(
                item["explicit_answers"] == len(object_ids)
                for item in candidate_runs
            ),
            "invented_objects": 0,
            "omitted_objects": 0,
            "unknown_codes": 0,
            "role_passes": 0,
        },
        "comparison": {
            "current_mapping_hashes_unique": len(
                {item["mapping_sha256"] for item in baseline}
            ),
            "candidate_mapping_hashes_unique": len(set(candidate_hashes)),
            "current_source_truth_correct": baseline_correct,
            "candidate_source_truth_correct": candidate_correct,
            "current_model_explicit_answer_counts": [
                item["model_explicit_answers"] for item in baseline
            ],
            "candidate_explicit_answer_counts": [
                item["explicit_answers"] for item in candidate_runs
            ],
        },
        "retry_count": 0,
        "repair_count": 0,
        "best_of_n": False,
        "manual_result_changes": 0,
        "provider_submissions": submissions["count"],
        "prior_g592_reused_not_repeated": True,
        "prior_g592_lesson": (
            "whole table rows are often compound and are not atomic one-code objects"
        ),
    }
    _atomic_write(safe_receipt, _json_bytes(receipt))
    print(
        json.dumps(
            {
                "status": final_terminal,
                "baseline_correct": baseline_correct,
                "candidate_correct": candidate_correct,
                "baseline_explicit": [
                    item["model_explicit_answers"] for item in baseline
                ],
                "candidate_explicit": [
                    item["explicit_answers"] for item in candidate_runs
                ],
                "candidate_exact_repeatability": len(set(candidate_hashes)) == 1,
                "provider_submissions": submissions["count"],
            },
            sort_keys=True,
        )
    )
    return 0


def _validated_source_truth(value: Any) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or set(value)
        != {"schema_version", "frozen_canonical_root_sha256", "objects"}
        or value.get("schema_version")
        != "broker_reports_gate3_minimal_classifier_source_truth_v1"
        or value.get("frozen_canonical_root_sha256")
        != FROZEN_CANONICAL_ROOT_SHA256
        or not isinstance(value.get("objects"), list)
        or not value["objects"]
    ):
        raise MinimalClassifierStandError("source_truth_invalid")
    object_ids: list[str] = []
    aliases: list[str] = []
    for item in value["objects"]:
        if (
            not isinstance(item, dict)
            or set(item) != {"object_id", "target_alias", "expected_code"}
            or not re.fullmatch(r"o[0-9]{3}", str(item.get("object_id") or ""))
            or not re.fullmatch(r"t[0-9]{3,}", str(item.get("target_alias") or ""))
            or item.get("expected_code")
            not in {UNMAPPED_CODE, *MACHINE_CODE_TO_LABEL}
        ):
            raise MinimalClassifierStandError("source_truth_invalid")
        object_ids.append(item["object_id"])
        aliases.append(item["target_alias"])
    if (
        object_ids != sorted(set(object_ids))
        or len(aliases) != len(set(aliases))
    ):
        raise MinimalClassifierStandError("source_truth_identity_invalid")
    return copy.deepcopy(value)


def _build_batch(
    *, chunk: dict[str, Any], source_truth: dict[str, Any]
) -> dict[str, Any]:
    mapping_by_alias = {
        item["target_alias"]: item["canonical_target"]
        for item in chunk["target_mappings"]
    }
    text_by_alias, row_line_by_key = _visible_text_index(
        content=chunk["model_view"]["content"],
        mapping_by_alias=mapping_by_alias,
    )
    row_targets = [
        target
        for target in mapping_by_alias.values()
        if target.get("kind") == "table_row"
    ]
    minimum_row_by_node = {
        node_id: min(
            int(item["row"])
            for item in row_targets
            if item.get("node_id") == node_id
        )
        for node_id in {str(item.get("node_id")) for item in row_targets}
    }
    objects = []
    for item in source_truth["objects"]:
        alias = item["target_alias"]
        target = mapping_by_alias.get(alias)
        if not isinstance(target, dict) or target.get("kind") != "table_cell":
            raise MinimalClassifierStandError("source_object_not_existing_cell")
        node_id = str(target.get("node_id") or "")
        row = target.get("row")
        if not isinstance(row, int):
            raise MinimalClassifierStandError("source_object_row_invalid")
        row_context = row_line_by_key.get((node_id, row))
        header_context = row_line_by_key.get(
            (node_id, minimum_row_by_node[node_id])
        )
        local_text = text_by_alias.get(alias)
        if not local_text or row_context is None or header_context is None:
            raise MinimalClassifierStandError("source_object_text_unavailable")
        objects.append(
            {
                "object_id": item["object_id"],
                "source_object_kind": "canonical_table_cell",
                "local_source_text": local_text,
                "table_header_context": header_context,
                "row_context": row_context,
            }
        )
    return {
        "schema_version": "broker_reports_gate3_minimal_classifier_batch_v1",
        "objects": objects,
    }


def _visible_text_index(
    *, content: str, mapping_by_alias: dict[str, dict[str, Any]]
) -> tuple[dict[str, str], dict[tuple[str, int], str]]:
    text_by_alias: dict[str, str] = {}
    row_lines: dict[tuple[str, int], str] = {}
    for line in content.splitlines():
        parts = re.split(r"\[(t[0-9]+)\]\s*", line)[1:]
        if not parts:
            continue
        aliases = parts[0::2]
        fragments = parts[1::2]
        for alias, fragment in zip(aliases, fragments, strict=True):
            text_by_alias[alias] = fragment.split("|", 1)[0].strip()
        for alias in aliases:
            target = mapping_by_alias.get(alias) or {}
            if target.get("kind") == "table_row":
                key = (str(target.get("node_id") or ""), int(target["row"]))
                if key in row_lines:
                    raise MinimalClassifierStandError(
                        "source_row_context_ambiguous"
                    )
                row_lines[key] = line
    return text_by_alias, row_lines


def _model_request(
    *, batch: dict[str, Any], schema: dict[str, Any]
) -> dict[str, Any]:
    return {
        "messages": [
            {"role": "system", "content": INSTRUCTION},
            {
                "role": "user",
                "content": json.dumps(
                    {"machine_code_catalog": machine_code_catalog()},
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                    allow_nan=False,
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {"batch": batch},
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                    allow_nan=False,
                ),
            },
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": RESPONSE_SCHEMA_VERSION,
                "strict": True,
                "schema": copy.deepcopy(schema),
            },
        },
    }


def _current_baseline(
    *,
    current_runs_dir: Path,
    chunk: dict[str, Any],
    source_truth: dict[str, Any],
) -> list[dict[str, Any]]:
    target_by_alias = {
        item["target_alias"]: item["canonical_target"]
        for item in chunk["target_mappings"]
    }
    label_to_code = {label: code for code, label in MACHINE_CODE_TO_LABEL.items()}
    expected = {
        item["object_id"]: item["expected_code"]
        for item in source_truth["objects"]
    }
    aliases = {
        item["object_id"]: item["target_alias"]
        for item in source_truth["objects"]
    }
    runs = []
    for ordinal in range(1, RUNS + 1):
        value = _read_json(current_runs_dir / f"run-{ordinal}.private.json")
        annotations = value["merged_output"]["annotations"]
        decisions: dict[str, str] = {}
        explicit = 0
        multiple = 0
        for object_id, alias in aliases.items():
            target = target_by_alias[alias]
            labels = [
                item["financial_label"]
                for item in annotations
                if item.get("target") == target
            ]
            if labels:
                explicit += 1
            if len(labels) == 0:
                code = UNMAPPED_CODE
            elif len(labels) == 1:
                code = label_to_code[labels[0]]
            else:
                multiple += 1
                code = "MULTIPLE"
            decisions[object_id] = code
        runs.append(
            {
                "ordinal": ordinal,
                "annotations_total": len(annotations),
                "model_explicit_answers": explicit,
                "analysis_filled_omissions": len(expected) - explicit,
                "multiple_codes_on_object": multiple,
                "source_truth_correct": sum(
                    decisions[key] == expected[key] for key in expected
                ),
                "mapping_sha256": _stable_sha256(decisions),
            }
        )
    return runs


def _current_context_audit(
    *, current_runs_dir: Path, chunk: dict[str, Any]
) -> dict[str, Any]:
    run = _read_json(current_runs_dir / "run-1.private.json")
    attempt = run["outcomes"][0]["pass1_attempt"]
    role_attempt = run["outcomes"][0]["role_attempt"]
    response = attempt["model_visible_request"]["response_format"]["json_schema"][
        "schema"
    ]
    annotations_schema = response["properties"]["annotations"]
    return {
        "chunks": 1,
        "eligible_targets": EXPECTED_CURRENT_TARGETS,
        "target_kind_counts": dict(
            sorted(
                Counter(
                    item["canonical_target"]["kind"]
                    for item in chunk["target_mappings"]
                ).items()
            )
        ),
        "projection_chars": len(chunk["model_view"]["content"]),
        "pass1_final_model_input_chars": attempt["metrics"][
            "final_model_input_chars"
        ],
        "role_final_model_input_chars": role_attempt["metrics"][
            "final_model_input_chars"
        ],
        "sparse_annotations_min_items": annotations_schema.get("minItems"),
        "sparse_annotations_max_items": annotations_schema.get("maxItems"),
        "empty_annotations_allowed_by_instruction": True,
        "model_selects_target_alias": True,
        "model_selects_annotation_count": True,
        "multiple_labels_per_target_allowed": True,
        "role_target_selection_is_second_model_decision": True,
    }


def _safe_candidate_run(
    *,
    ordinal: int,
    validated: dict[str, Any],
    source_truth: dict[str, Any],
    execution_metadata: Any,
    submissions: int,
) -> dict[str, Any]:
    expected = {
        item["object_id"]: item["expected_code"]
        for item in source_truth["objects"]
    }
    actual = {
        item["object_id"]: item["machine_code"]
        for item in validated["decisions"]
    }
    metadata = _plain(execution_metadata)
    return {
        "ordinal": ordinal,
        "terminal_status": "validated",
        "explicit_answers": len(actual),
        "classified": sum(code != UNMAPPED_CODE for code in actual.values()),
        "unmapped": sum(code == UNMAPPED_CODE for code in actual.values()),
        "rejected": 0,
        "source_truth_correct": sum(
            actual[key] == expected[key] for key in expected
        ),
        "mapping_sha256": _stable_sha256(actual),
        "input_tokens": metadata.get("input_tokens"),
        "output_tokens": metadata.get("output_tokens"),
        "duration_ms": metadata.get("duration_ms"),
        "provider_submissions": submissions,
    }


def _live_client(*, env_file: Path, timeout_seconds: int) -> tuple[Any, dict[str, int]]:
    env = _read_env(env_file)
    base_url = _base_url(env)
    session = requests.Session()
    session.headers.update({"Accept": "application/json"})
    session.get(_url(base_url, "/health"), timeout=20).raise_for_status()
    token = _signin(session, base_url, env)
    session.headers.update({"Authorization": f"Bearer {token}"})
    if NDFL_PROVIDER_MODEL_ID not in _published_model_ids(session, base_url):
        raise SystemExit("current_model_not_published")
    if NDFL_PROVIDER_MODEL_ID not in gate2_provider_profile(
        NDFL_PROVIDER_PROFILE_ID
    ).approved_model_ids:
        raise SystemExit("current_model_not_approved")
    live_user_id = str(_current_user(session, base_url).get("id") or "")
    if not live_user_id:
        raise SystemExit("authenticated_user_missing")
    completion = _completion_boundary(
        session=session,
        base_url=base_url,
        timeout=timeout_seconds,
    )
    submissions = {"count": 0}

    def counted_completion(*, form_data: dict[str, Any], **kwargs: Any) -> Any:
        submissions["count"] += 1
        return completion(form_data=form_data, **kwargs)

    client = Gate2StructuredModelClientFactory(
        config=Gate2StructuredModelClientConfig(
            request_profile=GATE3_BOUNDED_LABELING_REQUEST_PROFILE,
            provider_profile_id=NDFL_PROVIDER_PROFILE_ID,
            capability_probe=False,
            economy_budget_enforcement=False,
        ),
        user=SimpleNamespace(id=live_user_id),
        request=_request_context(session, base_url),
        completion_resolver=lambda _user_id: (
            counted_completion,
            SimpleNamespace(id=live_user_id),
        ),
    ).create()
    return client, submissions


def _frozen_context(
    store_root: Path,
) -> tuple[str, ArtifactAccessContext]:
    with sqlite3.connect(store_root / "artifacts.sqlite3") as connection:
        rows = connection.execute(
            """
            SELECT user_id, case_id, chat_id, workspace_model_id,
                   normalization_run_id, document_id
            FROM canonical_versions
            WHERE status = 'ACTIVE' AND canonical_root_sha256 = ?
            """,
            (FROZEN_CANONICAL_ROOT_SHA256,),
        ).fetchall()
    if len(rows) != 1:
        raise SystemExit("frozen_canonical_identity_not_unique")
    value = rows[0]
    return (
        value[5],
        ArtifactAccessContext(
            user_id=value[0],
            case_id=value[1],
            chat_id=value[2],
            workspace_model_id=value[3],
            normalization_run_id=value[4],
            allow_private=True,
        ),
    )


def _decode_json(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return copy.deepcopy(value)
    if not isinstance(value, str):
        raise MinimalClassifierStandError("classifier_response_contract_invalid")
    try:
        result = json.loads(value)
    except json.JSONDecodeError as exc:
        raise MinimalClassifierStandError(
            "classifier_response_contract_invalid"
        ) from exc
    if not isinstance(result, dict):
        raise MinimalClassifierStandError("classifier_response_contract_invalid")
    return result


def _plain(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, dict):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise MinimalClassifierStandError(f"json_object_required:{path.name}")
    return value


def _stable_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_bytes(content)
    temporary.replace(path)


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


if __name__ == "__main__":
    raise SystemExit(main())
