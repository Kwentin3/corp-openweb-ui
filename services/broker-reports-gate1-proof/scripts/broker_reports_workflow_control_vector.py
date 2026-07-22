from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


DRAFT_SCHEMA = "broker_reports_workflow_control_vector_draft_v1_private"
REFERENCE_SCHEMA = "broker_reports_workflow_control_vector_v1_private"
SEAL_SCHEMA = "broker_reports_workflow_control_vector_seal_v1_private"
SAFE_RECEIPT_SCHEMA = "broker_reports_workflow_control_vector_receipt_v1_safe"

METRIC_COUNT = 3
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
METRIC_ID_PATTERN = re.compile(r"[a-z][a-z0-9_]{2,63}")
NORMALIZED_NUMBER_PATTERN = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?")
PERIOD_KINDS = frozenset({"as_of", "period_ended"})
ARITHMETIC_OPERATIONS = frozenset({"add", "subtract"})


class ControlVectorError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    seal_parser = subparsers.add_parser("seal")
    seal_parser.add_argument("--draft", type=Path, required=True)
    seal_parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)

    try:
        _, _, receipt = seal_control_vector(
            draft_path=args.draft,
            output_dir=args.output_dir,
        )
    except (ControlVectorError, OSError) as exc:
        failure_code = (
            exc.code
            if isinstance(exc, ControlVectorError)
            else "control_vector_io_failure"
        )
        print(_canonical_json({"status": "blocked", "failure_code": failure_code}).decode())
        return 1

    # The command line boundary returns only the safe receipt. Literal labels and
    # expected values remain confined to the ignored private output directory.
    print(_canonical_json(receipt).decode())
    return 0


def seal_control_vector(
    *,
    draft_path: Path,
    output_dir: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ControlVectorError("control_vector_output_not_fresh")

    draft_bytes = draft_path.read_bytes()
    draft = _json_object(draft_bytes)
    validated = _validate_draft(draft)
    sealed_at = datetime.now(timezone.utc).isoformat()
    metrics = [
        {
            **metric,
            "metric_integrity_sha256": _sha256_json(metric),
        }
        for metric in validated["metrics"]
    ]
    source_document_sha256 = validated["selection"]["source_document_sha256"]

    reference = {
        "schema_version": REFERENCE_SCHEMA,
        "status": "sealed",
        "control_id": validated["control_id"],
        "created_for_goal": "GOAL_0_SOURCE_CONTROL_VECTOR",
        "sealed_at": sealed_at,
        "sealed_before_workflow_execution": True,
        "selection": validated["selection"],
        "review": validated["review"],
        "attestations": validated["attestations"],
        "metrics": metrics,
        "lineage": {
            "draft_sha256": hashlib.sha256(draft_bytes).hexdigest(),
            "source_document_sha256": source_document_sha256,
            "control_vector_sha256": _sha256_json(metrics),
        },
    }
    reference_bytes = _canonical_json(reference)
    seal = {
        "schema_version": SEAL_SCHEMA,
        "status": "sealed",
        "sealed_at": sealed_at,
        "reference_sha256": hashlib.sha256(reference_bytes).hexdigest(),
        "reference_size_bytes": len(reference_bytes),
        "metric_count": METRIC_COUNT,
        "source_document_sha256": source_document_sha256,
        "control_vector_sha256": reference["lineage"]["control_vector_sha256"],
    }
    seal_bytes = _canonical_json(seal)

    arithmetic_applicable = sum(
        metric["arithmetic_reconciliation"]["applicable"] for metric in metrics
    )
    receipt = {
        "schema_version": SAFE_RECEIPT_SCHEMA,
        "status": "sealed",
        "selection_status": "selected_before_workflow",
        "review_status": "delegated_agent_source_only",
        "human_review_status": "not_performed",
        "customer_acceptance_status": "not_claimed",
        "provider_reference_status": "not_used",
        "runtime_expected_value_exposure_status": "not_exposed",
        "document_count": 1,
        "metric_count": METRIC_COUNT,
        "distinct_source_scope_count": len(
            {metric["source_scope_id"] for metric in metrics}
        ),
        "semantic_visual_table_metric_count": sum(
            metric["representation_route"] == "semantic_visual_table"
            for metric in metrics
        ),
        "arithmetic_reconciliation_applicable_count": arithmetic_applicable,
        "arithmetic_reconciliation_passed_count": arithmetic_applicable,
        "source_document_sha256": source_document_sha256,
        "private_reference_sha256": seal["reference_sha256"],
        "private_reference_seal_sha256": hashlib.sha256(seal_bytes).hexdigest(),
        "control_vector_sha256": seal["control_vector_sha256"],
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_once(output_dir / "reference.delegated-agent.private.json", reference_bytes)
    _write_once(
        output_dir / "reference.delegated-agent.private.sha256.json",
        seal_bytes,
    )
    _write_once(output_dir / "receipt.safe.json", _canonical_json(receipt))
    return reference, seal, receipt


def _validate_draft(draft: dict[str, Any]) -> dict[str, Any]:
    _require_exact_keys(
        draft,
        {
            "schema_version",
            "created_for_goal",
            "control_id",
            "selection",
            "review",
            "attestations",
            "metrics",
        },
        "control_vector_draft_fields_invalid",
    )
    if draft.get("schema_version") != DRAFT_SCHEMA:
        raise ControlVectorError("control_vector_draft_schema_invalid")
    if draft.get("created_for_goal") != "GOAL_0_SOURCE_CONTROL_VECTOR":
        raise ControlVectorError("control_vector_goal_binding_invalid")
    control_id = _required_string(draft, "control_id")
    if not METRIC_ID_PATTERN.fullmatch(control_id):
        raise ControlVectorError("control_vector_id_invalid")

    selection = _required_object(draft, "selection")
    _require_exact_keys(
        selection,
        {
            "source_authorization_status",
            "selected_before_workflow",
            "original_pdf_opened_directly",
            "source_only",
            "provider_outputs_opened",
            "provider_outputs_used_as_reference",
            "expected_values_hidden_from_runtime",
            "workflow_execution_started",
            "source_document_sha256",
            "source_document_page_count",
        },
        "control_vector_selection_fields_invalid",
    )
    if selection.get("source_authorization_status") != "authorized_private_corpus":
        raise ControlVectorError("control_vector_source_not_authorized")
    _require_exact_true(selection, "selected_before_workflow")
    _require_exact_true(selection, "original_pdf_opened_directly")
    _require_exact_true(selection, "source_only")
    _require_exact_false(selection, "provider_outputs_opened")
    _require_exact_false(selection, "provider_outputs_used_as_reference")
    _require_exact_true(selection, "expected_values_hidden_from_runtime")
    _require_exact_false(selection, "workflow_execution_started")
    source_document_sha256 = _sha256_field(selection, "source_document_sha256")
    page_count = selection.get("source_document_page_count")
    if type(page_count) is not int or page_count < 1:
        raise ControlVectorError("control_vector_page_count_invalid")

    review = _required_object(draft, "review")
    _require_exact_keys(
        review,
        {
            "reviewer_kind",
            "reviewer_identity",
            "delegation_kind",
            "review_method",
            "human_reviewed",
            "customer_accepted",
        },
        "control_vector_review_fields_invalid",
    )
    if review.get("reviewer_kind") != "delegated_agent":
        raise ControlVectorError("control_vector_reviewer_kind_invalid")
    _required_string(review, "reviewer_identity")
    _required_string(review, "delegation_kind")
    if review.get("review_method") != "direct_original_pdf_visual_inspection":
        raise ControlVectorError("control_vector_review_method_invalid")
    _require_exact_false(review, "human_reviewed")
    _require_exact_false(review, "customer_accepted")

    attestations = _required_object(draft, "attestations")
    _require_exact_keys(
        attestations,
        {
            "literal_labels_transcribed_from_source",
            "literal_values_transcribed_from_source",
            "provider_output_not_used_as_truth",
            "expected_values_not_exposed_to_runtime",
            "metrics_selected_before_workflow",
        },
        "control_vector_attestation_fields_invalid",
    )
    for key in (
        "literal_labels_transcribed_from_source",
        "literal_values_transcribed_from_source",
        "provider_output_not_used_as_truth",
        "expected_values_not_exposed_to_runtime",
        "metrics_selected_before_workflow",
    ):
        _require_exact_true(attestations, key)

    metrics = draft.get("metrics")
    if not isinstance(metrics, list) or len(metrics) != METRIC_COUNT:
        raise ControlVectorError("control_vector_metric_count_invalid")

    metric_ids: set[str] = set()
    scope_ids: set[str] = set()
    semantic_count = 0
    for metric in metrics:
        if not isinstance(metric, dict):
            raise ControlVectorError("control_vector_metric_invalid")
        _require_exact_keys(
            metric,
            {
                "metric_id",
                "source_scope_id",
                "source_label_literal",
                "source_value_literal",
                "normalized_comparison_value",
                "currency",
                "unit",
                "sign",
                "period",
                "document_sha256",
                "page_number",
                "source_medium",
                "representation_route",
                "source_only_decision",
                "arithmetic_reconciliation",
            },
            "control_vector_metric_fields_invalid",
        )
        metric_id = _required_string(metric, "metric_id")
        if not METRIC_ID_PATTERN.fullmatch(metric_id) or metric_id in metric_ids:
            raise ControlVectorError("control_vector_metric_id_invalid")
        metric_ids.add(metric_id)

        scope_id = _required_string(metric, "source_scope_id")
        if not METRIC_ID_PATTERN.fullmatch(scope_id) or scope_id in scope_ids:
            raise ControlVectorError("control_vector_source_scope_invalid")
        scope_ids.add(scope_id)
        _required_string(metric, "source_label_literal")
        _required_string(metric, "source_value_literal")
        normalized_value = _normalized_number(metric, "normalized_comparison_value")
        currency = _required_string(metric, "currency")
        if not re.fullmatch(r"[A-Z]{3}", currency):
            raise ControlVectorError("control_vector_metric_currency_invalid")
        _required_string(metric, "unit")
        expected_sign = "zero" if normalized_value == 0 else (
            "positive" if normalized_value > 0 else "negative"
        )
        if metric.get("sign") != expected_sign:
            raise ControlVectorError("control_vector_metric_sign_invalid")

        period = _required_object(metric, "period")
        _require_exact_keys(
            period,
            {"kind", "literal", "normalized"},
            "control_vector_metric_period_fields_invalid",
        )
        if period.get("kind") not in PERIOD_KINDS:
            raise ControlVectorError("control_vector_metric_period_invalid")
        _required_string(period, "literal")
        normalized_period = _required_string(period, "normalized")
        if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", normalized_period):
            raise ControlVectorError("control_vector_metric_period_invalid")

        if _sha256_field(metric, "document_sha256") != source_document_sha256:
            raise ControlVectorError("control_vector_document_binding_invalid")
        page_number = metric.get("page_number")
        if type(page_number) is not int or not 1 <= page_number <= page_count:
            raise ControlVectorError("control_vector_page_binding_invalid")
        if metric.get("source_medium") != "rasterized_original_pdf_page":
            raise ControlVectorError("control_vector_source_medium_invalid")
        if metric.get("source_only_decision") != "accepted":
            raise ControlVectorError("control_vector_source_decision_invalid")
        if metric.get("representation_route") == "semantic_visual_table":
            semantic_count += 1
        else:
            raise ControlVectorError("control_vector_representation_route_invalid")
        _validate_arithmetic(metric, normalized_value)

    if semantic_count < 1:
        raise ControlVectorError("control_vector_semantic_metric_missing")
    return draft


def _validate_arithmetic(metric: dict[str, Any], expected: Decimal) -> None:
    reconciliation = _required_object(metric, "arithmetic_reconciliation")
    applicable = reconciliation.get("applicable")
    if type(applicable) is not bool:
        raise ControlVectorError("control_vector_arithmetic_applicability_invalid")
    if not applicable:
        _require_exact_keys(
            reconciliation,
            {"applicable", "reason"},
            "control_vector_arithmetic_fields_invalid",
        )
        _required_string(reconciliation, "reason")
        return

    _require_exact_keys(
        reconciliation,
        {"applicable", "operands"},
        "control_vector_arithmetic_fields_invalid",
    )
    operands = reconciliation.get("operands")
    if not isinstance(operands, list) or len(operands) < 2:
        raise ControlVectorError("control_vector_arithmetic_operands_invalid")
    total = Decimal(0)
    for operand in operands:
        if not isinstance(operand, dict):
            raise ControlVectorError("control_vector_arithmetic_operand_invalid")
        _require_exact_keys(
            operand,
            {"operation", "normalized_value"},
            "control_vector_arithmetic_operand_fields_invalid",
        )
        operation = operand.get("operation")
        if operation not in ARITHMETIC_OPERATIONS:
            raise ControlVectorError("control_vector_arithmetic_operation_invalid")
        value = _normalized_number(operand, "normalized_value")
        total = total + value if operation == "add" else total - value
    if total != expected:
        raise ControlVectorError("control_vector_arithmetic_mismatch")


def _required_object(value: dict[str, Any], key: str) -> dict[str, Any]:
    item = value.get(key)
    if not isinstance(item, dict):
        raise ControlVectorError("control_vector_required_object_missing")
    return item


def _require_exact_keys(
    value: dict[str, Any],
    expected: set[str],
    failure_code: str,
) -> None:
    if set(value) != expected:
        raise ControlVectorError(failure_code)


def _required_string(value: dict[str, Any], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item.strip():
        raise ControlVectorError("control_vector_required_string_missing")
    return item


def _sha256_field(value: dict[str, Any], key: str) -> str:
    item = _required_string(value, key)
    if not SHA256_PATTERN.fullmatch(item):
        raise ControlVectorError("control_vector_sha256_invalid")
    return item


def _normalized_number(value: dict[str, Any], key: str) -> Decimal:
    item = _required_string(value, key)
    if not NORMALIZED_NUMBER_PATTERN.fullmatch(item):
        raise ControlVectorError("control_vector_normalized_number_invalid")
    try:
        return Decimal(item)
    except InvalidOperation as exc:  # pragma: no cover - guarded by the regex
        raise ControlVectorError("control_vector_normalized_number_invalid") from exc


def _require_exact_true(value: dict[str, Any], key: str) -> None:
    if value.get(key) is not True:
        raise ControlVectorError("control_vector_attestation_invalid")


def _require_exact_false(value: dict[str, Any], key: str) -> None:
    if value.get(key) is not False:
        raise ControlVectorError("control_vector_attestation_invalid")


def _json_object(raw: bytes) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ControlVectorError("control_vector_draft_invalid_json") from exc
    if not isinstance(value, dict):
        raise ControlVectorError("control_vector_draft_invalid_json")
    return value


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _write_once(path: Path, raw: bytes) -> None:
    with path.open("xb") as stream:
        stream.write(raw)


if __name__ == "__main__":
    raise SystemExit(main())
