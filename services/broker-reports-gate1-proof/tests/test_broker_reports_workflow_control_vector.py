from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest


SERVICE_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = SERVICE_ROOT / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import broker_reports_workflow_control_vector as CONTROL_VECTOR  # noqa: E402


SOURCE_SHA256 = "7" * 64
PRIVATE_LABELS = (
    "PRIVATE_LABEL_ALPHA_SENTINEL",
    "PRIVATE_LABEL_BETA_SENTINEL",
    "PRIVATE_LABEL_GAMMA_SENTINEL",
)
PRIVATE_VALUES = (
    "9182736455463728",
    "7162538492073618",
    "5647382910192837",
)


def _metric(index: int) -> dict:
    normalized_value = PRIVATE_VALUES[index]
    arithmetic = {
        "applicable": False,
        "reason": "printed_total_scope_is_not_atomically_reconciled",
    }
    if index == 0:
        arithmetic = {
            "applicable": True,
            "operands": [
                {"operation": "add", "normalized_value": "4000000000000000"},
                {"operation": "add", "normalized_value": "5182736455463728"},
            ],
        }
    return {
        "metric_id": f"control_metric_{index + 1}",
        "source_scope_id": f"logical_source_scope_{index + 1}",
        "source_label_literal": PRIVATE_LABELS[index],
        "source_value_literal": f"$ {normalized_value}",
        "normalized_comparison_value": normalized_value,
        "currency": "USD",
        "unit": "thousands",
        "sign": "positive",
        "period": {
            "kind": "as_of",
            "literal": "December 31, 2024",
            "normalized": "2024-12-31",
        },
        "document_sha256": SOURCE_SHA256,
        "page_number": index + 1,
        "source_medium": "rasterized_original_pdf_page",
        "representation_route": "semantic_visual_table",
        "source_only_decision": "accepted",
        "arithmetic_reconciliation": arithmetic,
    }


def _draft() -> dict:
    return {
        "schema_version": CONTROL_VECTOR.DRAFT_SCHEMA,
        "created_for_goal": "GOAL_0_SOURCE_CONTROL_VECTOR",
        "control_id": "workflow_semantic_checksum_control_v1",
        "selection": {
            "source_authorization_status": "authorized_private_corpus",
            "selected_before_workflow": True,
            "original_pdf_opened_directly": True,
            "source_only": True,
            "provider_outputs_opened": False,
            "provider_outputs_used_as_reference": False,
            "expected_values_hidden_from_runtime": True,
            "workflow_execution_started": False,
            "source_document_sha256": SOURCE_SHA256,
            "source_document_page_count": 12,
        },
        "review": {
            "reviewer_kind": "delegated_agent",
            "reviewer_identity": "OpenAI Codex",
            "delegation_kind": "program_authorized_agent_review",
            "review_method": "direct_original_pdf_visual_inspection",
            "human_reviewed": False,
            "customer_accepted": False,
        },
        "attestations": {
            "literal_labels_transcribed_from_source": True,
            "literal_values_transcribed_from_source": True,
            "provider_output_not_used_as_truth": True,
            "expected_values_not_exposed_to_runtime": True,
            "metrics_selected_before_workflow": True,
        },
        "metrics": [_metric(index) for index in range(3)],
    }


def _write_draft(tmp_path: Path, value: dict | None = None) -> Path:
    path = tmp_path / "control-vector.draft.private.json"
    path.write_text(
        json.dumps(value if value is not None else _draft()),
        encoding="utf-8",
    )
    return path


def test_seals_exact_source_only_vector_and_emits_value_free_receipt(
    tmp_path: Path,
) -> None:
    draft_path = _write_draft(tmp_path)
    output_dir = tmp_path / "reference-v1"

    reference, seal, receipt = CONTROL_VECTOR.seal_control_vector(
        draft_path=draft_path,
        output_dir=output_dir,
    )

    assert reference["status"] == "sealed"
    assert reference["sealed_before_workflow_execution"] is True
    assert reference["review"]["reviewer_kind"] == "delegated_agent"
    assert reference["review"]["human_reviewed"] is False
    assert reference["review"]["customer_accepted"] is False
    assert reference["selection"]["provider_outputs_used_as_reference"] is False
    assert all(
        len(metric["metric_integrity_sha256"]) == 64
        for metric in reference["metrics"]
    )
    assert seal["metric_count"] == 3
    assert receipt["metric_count"] == 3
    assert receipt["distinct_source_scope_count"] == 3
    assert receipt["semantic_visual_table_metric_count"] == 3
    assert receipt["arithmetic_reconciliation_applicable_count"] == 1
    assert receipt["arithmetic_reconciliation_passed_count"] == 1

    safe_text = (output_dir / "receipt.safe.json").read_text(encoding="utf-8")
    for sentinel in (*PRIVATE_LABELS, *PRIVATE_VALUES):
        assert sentinel not in safe_text
    assert "source_label_literal" not in safe_text
    assert "normalized_comparison_value" not in safe_text


@pytest.mark.parametrize(
    ("mutation", "failure_code"),
    [
        (
            lambda value: value["metrics"].pop(),
            "control_vector_metric_count_invalid",
        ),
        (
            lambda value: value["selection"].update(
                {"provider_outputs_used_as_reference": True}
            ),
            "control_vector_attestation_invalid",
        ),
        (
            lambda value: value["review"].update({"human_reviewed": True}),
            "control_vector_attestation_invalid",
        ),
        (
            lambda value: value["metrics"][1].update(
                {"source_scope_id": value["metrics"][0]["source_scope_id"]}
            ),
            "control_vector_source_scope_invalid",
        ),
        (
            lambda value: value["metrics"][0]["arithmetic_reconciliation"][
                "operands"
            ][0].update({"normalized_value": "1"}),
            "control_vector_arithmetic_mismatch",
        ),
        (
            lambda value: value["metrics"][0].update(
                {"provider_output": "must_not_be_retained"}
            ),
            "control_vector_metric_fields_invalid",
        ),
    ],
)
def test_rejects_non_controlled_reference_drafts(
    tmp_path: Path,
    mutation,
    failure_code: str,
) -> None:
    value = copy.deepcopy(_draft())
    mutation(value)
    draft_path = _write_draft(tmp_path, value)

    with pytest.raises(CONTROL_VECTOR.ControlVectorError) as exc_info:
        CONTROL_VECTOR.seal_control_vector(
            draft_path=draft_path,
            output_dir=tmp_path / "reference-v1",
        )

    assert exc_info.value.code == failure_code
    assert not (tmp_path / "reference-v1").exists()


def test_refuses_to_overwrite_an_existing_reference(tmp_path: Path) -> None:
    draft_path = _write_draft(tmp_path)
    output_dir = tmp_path / "reference-v1"
    CONTROL_VECTOR.seal_control_vector(
        draft_path=draft_path,
        output_dir=output_dir,
    )

    with pytest.raises(CONTROL_VECTOR.ControlVectorError) as exc_info:
        CONTROL_VECTOR.seal_control_vector(
            draft_path=draft_path,
            output_dir=output_dir,
        )

    assert exc_info.value.code == "control_vector_output_not_fresh"


def test_cli_stdout_contains_only_the_safe_receipt(tmp_path: Path) -> None:
    draft_path = _write_draft(tmp_path)
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_DIR / "broker_reports_workflow_control_vector.py"),
            "seal",
            "--draft",
            str(draft_path),
            "--output-dir",
            str(tmp_path / "reference-v1"),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    stdout = completed.stdout.strip()
    receipt = json.loads(stdout)
    assert receipt["schema_version"] == CONTROL_VECTOR.SAFE_RECEIPT_SCHEMA
    for sentinel in (*PRIVATE_LABELS, *PRIVATE_VALUES):
        assert sentinel not in stdout
