#!/usr/bin/env python3
"""Run the Goal 2 candidate-bound hybrid vertical on the controlled private PDF."""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import re
import sys
import unicodedata
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import requests


SCRIPT_DIR = Path(__file__).resolve().parent
SERVICE_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SERVICE_ROOT.parents[1]
sys.path.insert(0, str(SERVICE_ROOT))

from broker_reports_gate1 import (  # noqa: E402
    ArtifactAccessContext,
    ArtifactStoreConfig,
    ArtifactStoreFactory,
    FileInput,
    Gate1Normalizer,
    persist_gate1_result,
)
from broker_reports_gate1.artifact_models import RetentionPolicy  # noqa: E402
from broker_reports_gate1.pdf_hybrid_provider import (  # noqa: E402
    PdfHybridProviderConfig,
    PdfHybridProviderFactory,
)
from broker_reports_gate1.pdf_hybrid_shadow import (  # noqa: E402
    PdfHybridShadowConfig,
    PdfHybridShadowFactory,
)


SAFE_SCHEMA = "broker_reports_pdf_hybrid_goal2_controlled_proof_v1"
STRUCTURAL_SIGNALS = {
    "1:3": {"multi_row_or_merged_header": True, "header_depth": 3},
    "3:2": {"multi_row_or_merged_header": True, "header_depth": 2},
    "4:1": {"continuation_signal": True, "header_depth": 0},
    "4:2": {"multi_row_or_merged_header": True, "header_depth": 3},
    "5:3": {"multi_row_or_merged_header": True, "header_depth": 2},
}
REPEAT_KEYS = {"4:1", "4:2", "5:3"}
DPI_ESCALATION_REASONS = {
    "4:1": "pdf_hybrid_continuation_structure_sensitivity_check",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--reference", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--env-file", default=str(REPO_ROOT / ".env"))
    parser.add_argument("--skip-provider", action="store_true")
    parser.add_argument("--model-id", default="models/gemini-3.5-flash")
    args = parser.parse_args()

    pdf_path = Path(args.pdf).resolve()
    reference_path = Path(args.reference).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    payload_root = output_dir / "payloads"
    database_path = output_dir / "artifacts.sqlite3"
    pdf_bytes = pdf_path.read_bytes()
    pdf_sha256 = hashlib.sha256(pdf_bytes).hexdigest()
    reference = json.loads(reference_path.read_text(encoding="utf-8"))
    reference_tables = {
        str(item.get("table_key") or ""): item
        for item in reference.get("tables") or []
        if isinstance(item, dict)
    }

    file_input = FileInput.from_bytes(
        private_ref=f"controlled-private-pdf:{pdf_sha256}",
        filename="controlled.pdf",
        content=pdf_bytes,
        mime_type=mimetypes.guess_type("controlled.pdf")[0] or "application/pdf",
        source_kind="local_private_test",
    )
    result = Gate1Normalizer().normalize(
        [file_input],
        entrypoint="local_pdf_hybrid_goal2_proof",
        trigger_type="controlled_private_proof",
        input_context={
            "pdf_layout_slice2_enabled": True,
            "pdf_compact_canonical_dual_write": True,
            "pdf_hybrid_shadow_enabled": True,
        },
    )
    run_id = result.package["normalization_run"]["run_id"]
    context = ArtifactAccessContext(
        user_id="controlled-proof-user",
        case_id="controlled-proof-case",
        chat_id="controlled-proof-chat",
        workspace_model_id="broker-reports-gate1",
        normalization_run_id=run_id,
        allow_private=True,
    )
    retention = RetentionPolicy(
        mode="synthetic_dev",
        ttl_seconds=None,
        expires_at=None,
        explicit=True,
    )
    store = ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=database_path,
            payload_root=payload_root,
        )
    ).create()
    gate1_manifest = persist_gate1_result(
        store=store,
        result=result,
        context=context,
        retention_policy=retention,
        source_file_refs=[
            {
                "provider": "controlled_private_registry",
                "file_hash_sha256": pdf_sha256,
                "content_type": "application/pdf",
                "size_bytes": len(pdf_bytes),
            }
        ],
    )
    source_payload = (result.package.get("private_normalized_source_payloads") or [])[0]
    table_map = _table_reference_map(source_payload, reference_tables)
    signal_overrides = {
        table_ref: STRUCTURAL_SIGNALS.get(table_key, {})
        for table_ref, table_key in table_map.items()
    }
    repeatability_refs = {
        table_ref for table_ref, table_key in table_map.items() if table_key in REPEAT_KEYS
    }
    dpi_escalation_reasons = {
        table_ref: DPI_ESCALATION_REASONS[table_key]
        for table_ref, table_key in table_map.items()
        if table_key in DPI_ESCALATION_REASONS
    }

    qualification: dict[str, Any]
    provider = None
    if args.skip_provider:
        qualification = {"status": "skipped"}
    else:
        try:
            request = _openwebui_request(Path(args.env_file))
            provider = PdfHybridProviderFactory(
                PdfHybridProviderConfig(model_id=args.model_id)
            ).create_for_openwebui(request)
            qualification = provider.qualify()
            if qualification.get("status") != "qualified":
                provider = None
        except Exception as exc:
            qualification = {
                "status": "blocked",
                "failure_class": type(exc).__name__,
            }
            provider = None

    shadow = PdfHybridShadowFactory(
        PdfHybridShadowConfig(enabled=True)
    ).create(provider=provider).run(
        store=store,
        package=result.package,
        context=context,
        retention_policy=retention,
        pdf_bytes_by_sha256={pdf_sha256: pdf_bytes},
        signal_overrides_by_table=signal_overrides,
        repeatability_table_refs=repeatability_refs if provider is not None else set(),
        dpi_escalation_reasons_by_table=(
            dpi_escalation_reasons if provider is not None else {}
        ),
    )
    records = store.list_by_run(run_id)
    decisions = [
        store.read_payload(record)
        for record in records
        if record.artifact_type == "broker_reports_pdf_hybrid_shadow_decision_v1"
    ]
    scheduled_keys = {"1:3", "3:2", "4:1", "4:2", "5:3"}
    scheduled = [
        (table_map.get(str(item.get("table_ref") or "")), item)
        for item in decisions
        if table_map.get(str(item.get("table_ref") or "")) in scheduled_keys
    ]
    materialized_scores = []
    accepted_scores = []
    scheduled_scores = []
    table_results = []
    for table_key, decision in scheduled:
        score = None
        refs = decision.get("artifact_refs") if isinstance(decision.get("artifact_refs"), dict) else {}
        materialization_ref = refs.get("materialization")
        if materialization_ref:
            record = store.get_record_unchecked(str(materialization_ref))
            materialization = store.read_payload(record) if record else None
            if isinstance(materialization, dict):
                score = _score(reference_tables[table_key], materialization)
                materialized_scores.append(score)
        if score is not None and decision.get("hybrid_status") == "accepted_shadow":
            accepted_scores.append(score)
            scheduled_scores.append(score)
        else:
            scheduled_scores.append(_failed_scheduled_score(reference_tables[table_key]))
        table_results.append(
            {
                "table_key": table_key,
                "structural_case": _structural_case(table_key),
                "current_status": decision.get("current_status"),
                "terminal_status": decision.get("hybrid_status"),
                "current_shape": decision.get("current_shape"),
                "hybrid_shape": decision.get("hybrid_shape"),
                "accepted_cell_count": decision.get("accepted_cell_count"),
                "explicit_empty_count": decision.get("explicit_empty_count"),
                "source_value_refs_count": decision.get("source_value_refs_count"),
                "word_refs_count": decision.get("word_refs_count"),
                "blocker_codes": decision.get("blocker_codes"),
                "context": decision.get("component_accounting"),
                "repeatability_required": decision.get("repeatability_required"),
                "repeatability_match": decision.get("repeatability_match"),
                "dpi_revision_comparison": _safe_dpi_comparison(
                    decision.get("dpi_revision_comparison")
                ),
                "score": score,
            }
        )
    deterministic_repeat = _deterministic_control_repeat(
        pdf_bytes=pdf_bytes,
        pdf_sha256=pdf_sha256,
        primary_package=result.package,
        decisions=decisions,
    )
    provider_attempts = [
        _safe_provider_attempt(record.safe_metadata, table_map)
        for record in records
        if record.artifact_type == "broker_reports_pdf_provider_attempt_v1"
    ]
    artifact_counts = _counts(record.artifact_type for record in records)
    payload_bytes = {
        artifact_type: sum(
            len(
                json.dumps(
                    store.read_payload(record),
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            )
            for record in records
            if record.artifact_type == artifact_type
        )
        for artifact_type in artifact_counts
    }
    safe = {
        "schema_version": SAFE_SCHEMA,
        "source_revision": _git_revision(),
        "pdf_sha256": pdf_sha256,
        "normalization_run_id": run_id,
        "goal1": {
            "table_decisions": len(result.package.get("private_normalized_table_projections") or []),
            "accepted_tables": sum(
                item.get("projection_status") == "ready"
                for item in result.package.get("private_normalized_table_projections") or []
            ),
            "blocked_tables": sum(
                item.get("projection_status") != "ready"
                for item in result.package.get("private_normalized_table_projections") or []
            ),
            "compact_artifacts": artifact_counts.get(
                "broker_reports_pdf_compact_canonical_document_v1", 0
            ),
            "production_gate2_selection_changed": False,
        },
        "provider_qualification": qualification,
        "classifier": shadow.get("summary", {}).get("classifier_paths"),
        "terminal_outcomes": shadow.get("summary", {}).get("terminal_outcomes"),
        "tables": sorted(table_results, key=lambda item: item["table_key"]),
        "scheduled_score": _aggregate_scores(
            scheduled_scores,
            scheduled_total=len(scheduled),
            accepted_scored_tables=len(accepted_scores),
        ),
        "accepted_only_score": _aggregate_scores(
            accepted_scores,
            scheduled_total=len(accepted_scores),
            accepted_scored_tables=len(accepted_scores),
        ),
        "materialized_diagnostic_score": _aggregate_scores(
            materialized_scores,
            scheduled_total=len(materialized_scores),
            accepted_scored_tables=len(materialized_scores),
        ),
        "artifact_counts": artifact_counts,
        "artifact_payload_bytes": payload_bytes,
        "largest_package": shadow.get("summary", {}).get("largest_package"),
        "provider_attempts": provider_attempts,
        "repeatability": {
            "deterministic_control": deterministic_repeat,
            "hybrid_tables": [
                {
                    "table_key": item["table_key"],
                    "required": item["repeatability_required"],
                    "materialization_checksum_equal": item["repeatability_match"],
                }
                for item in table_results
                if item["repeatability_required"]
            ],
        },
        "reference_status": reference.get("human_review_status"),
        "reference_is_provisional": True,
        "gate1_manifest_ref_present": bool(gate1_manifest.gate2_handoff_ref),
        "authority_state": "non_authoritative",
        "production_ready": False,
        "production_gate2_selection_changed": False,
        "knowledge_rag_used": False,
        "vectorization_performed": False,
        "ocr_used": False,
        "customer_values_included": False,
        "crop_bytes_included": False,
        "raw_provider_response_included": False,
        "private_paths_included": False,
    }
    (output_dir / "evidence.safe.json").write_text(
        json.dumps(safe, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps(safe, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _deterministic_control_repeat(
    *,
    pdf_bytes: bytes,
    pdf_sha256: str,
    primary_package: dict[str, Any],
    decisions: list[dict[str, Any]],
) -> dict[str, Any]:
    simple = next(
        (
            item
            for item in decisions
            if item.get("hybrid_status") == "deterministic_control_no_vlm"
        ),
        None,
    )
    if simple is None:
        return {"status": "not_available", "materialization_checksum_equal": False}
    repeat_input = FileInput.from_bytes(
        private_ref=f"controlled-private-pdf:{pdf_sha256}",
        filename="controlled.pdf",
        content=pdf_bytes,
        mime_type="application/pdf",
        source_kind="local_private_test",
    )
    repeated = Gate1Normalizer().normalize(
        [repeat_input],
        entrypoint="local_pdf_hybrid_goal2_proof_repeat",
        trigger_type="controlled_private_proof",
        input_context={
            "pdf_layout_slice2_enabled": True,
            "pdf_compact_canonical_dual_write": True,
            "pdf_hybrid_shadow_enabled": True,
        },
    )
    table_ref = str(simple.get("table_ref") or "")
    primary = next(
        (
            item
            for item in primary_package.get("private_normalized_table_projections") or []
            if isinstance(item, dict) and item.get("table_ref") == table_ref
        ),
        None,
    )
    second = next(
        (
            item
            for item in repeated.package.get("private_normalized_table_projections") or []
            if isinstance(item, dict) and item.get("table_ref") == table_ref
        ),
        None,
    )
    first_hash = _canonical_hash(primary)
    second_hash = _canonical_hash(second)
    return {
        "status": "passed" if first_hash and first_hash == second_hash else "failed",
        "table_ref": table_ref,
        "materialization_checksum_equal": bool(first_hash and first_hash == second_hash),
    }


def _canonical_hash(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _safe_dpi_comparison(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    return {
        key: value.get(key)
        for key in (
            "primary_dpi",
            "escalation_dpi",
            "typed_reason",
            "primary_terminal_status",
            "escalation_terminal_status",
            "crop_identity_changed",
            "package_identity_changed",
            "materialization_checksum_equal",
            "placement_checksum_equal",
        )
    }


def _safe_provider_attempt(
    metadata: dict[str, Any], table_map: dict[str, str]
) -> dict[str, Any]:
    usage = metadata.get("usage") if isinstance(metadata.get("usage"), dict) else {}
    return {
        "table_key": table_map.get(str(metadata.get("table_ref") or "")),
        "attempt_number": metadata.get("attempt_number"),
        "repeatability_probe": bool(metadata.get("repeatability_probe")),
        "provider_profile": metadata.get("provider_profile"),
        "model_requested": metadata.get("model_requested"),
        "model_resolved": metadata.get("model_resolved"),
        "duration_ms": metadata.get("duration_ms"),
        "http_status": metadata.get("http_status"),
        "input_tokens": usage.get("input_tokens"),
        "output_tokens": usage.get("output_tokens"),
        "finish_reason": metadata.get("finish_reason"),
        "parse_result": metadata.get("parse_result"),
        "validation_result": metadata.get("validation_result"),
        "terminal_failure_class": metadata.get("terminal_failure_class"),
        "provider_token_amplification_ratio": metadata.get(
            "provider_token_amplification_ratio"
        ),
    }


def _openwebui_request(env_path: Path) -> Any:
    env = _read_env(env_path)
    host = str(
        env.get("OPENWEBUI_HOST")
        or env.get("OPENWEBUI_BASE_URL")
        or env.get("BASE_URL")
        or ""
    ).rstrip("/")
    base_url = host if host.startswith(("http://", "https://")) else f"https://{host}"
    email = str(
        env.get("WEBUI_ADMIN_EMAIL")
        or env.get("OPENWEBUI_ADMIN_EMAIL")
        or env.get("ADMIN_EMAIL")
        or ""
    )
    password = str(
        env.get("WEBUI_ADMIN_PASSWORD")
        or env.get("OPENWEBUI_ADMIN_PASSWORD")
        or env.get("ADMIN_PASSWORD")
        or ""
    )
    if not all((base_url, email, password)):
        raise ValueError("openwebui_live_credentials_missing")
    session = requests.Session()
    response = session.post(
        base_url + "/api/v1/auths/signin",
        json={"email": email, "password": password},
        timeout=30,
    )
    response.raise_for_status()
    token = str(response.json().get("token") or "")
    session.headers.update({"Authorization": f"Bearer {token}"})
    config_response = session.get(base_url + "/openai/config", timeout=30)
    config_response.raise_for_status()
    config = config_response.json()
    config_object = SimpleNamespace(
        OPENAI_API_BASE_URLS=config.get("OPENAI_API_BASE_URLS"),
        OPENAI_API_KEYS=config.get("OPENAI_API_KEYS"),
        OPENAI_API_CONFIGS=config.get("OPENAI_API_CONFIGS"),
    )
    return SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(config=config_object))
    )


def _read_env(path: Path) -> dict[str, str]:
    result = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key.strip()] = value.strip().strip('"').strip("'")
    return result


def _table_reference_map(
    source_payload: dict[str, Any], reference_tables: dict[str, dict[str, Any]]
) -> dict[str, str]:
    projection = source_payload.get("pdf_text_layer_projection") or {}
    bboxes = {
        str(item.get("bbox_ref") or ""): item.get("bbox")
        for item in projection.get("bbox_inventory") or []
        if isinstance(item, dict)
    }
    page_numbers = {
        str(item.get("page_ref") or ""): int(item.get("page_number") or 0)
        for item in projection.get("page_inventory") or []
        if isinstance(item, dict)
    }
    result = {}
    for candidate in projection.get("table_candidate_inventory") or []:
        if not isinstance(candidate, dict):
            continue
        page = page_numbers.get(str(candidate.get("page_ref") or ""), 0)
        bbox = bboxes.get(str(candidate.get("bbox_ref") or ""))
        direct_key = f"{page}:{int(candidate.get('parser_ordinal') or 0)}"
        if direct_key in reference_tables:
            result[str(candidate.get("table_candidate_ref") or "")] = direct_key
            continue
        choices = [item for item in reference_tables.values() if item.get("page") == page]
        match = max(choices, key=lambda item: _iou(bbox, item.get("bbox")), default=None)
        if match and _iou(bbox, match.get("bbox")) > 0.05:
            result[str(candidate.get("table_candidate_ref") or "")] = str(
                match.get("table_key") or ""
            )
    return result


def _iou(left: Any, right: Any) -> float:
    if not isinstance(left, list) or not isinstance(right, list) or len(left) != 4 or len(right) != 4:
        return 0.0
    x0, y0 = max(left[0], right[0]), max(left[1], right[1])
    x1, y1 = min(left[2], right[2]), min(left[3], right[3])
    intersection = max(0.0, x1 - x0) * max(0.0, y1 - y0)
    area_left = max(0.0, left[2] - left[0]) * max(0.0, left[3] - left[1])
    area_right = max(0.0, right[2] - right[0]) * max(0.0, right[3] - right[1])
    union = area_left + area_right - intersection
    return intersection / union if union else 0.0


def _score(reference: dict[str, Any], materialization: dict[str, Any]) -> dict[str, Any]:
    rows = int(materialization.get("row_count") or 0)
    columns = int(materialization.get("column_count") or 0)
    predicted = [[""] * columns for _ in range(rows)]
    for cell in materialization.get("cells") or []:
        row = int(cell.get("row_ordinal") or 0) - 1
        column = int(cell.get("column_ordinal") or 0) - 1
        if 0 <= row < rows and 0 <= column < columns:
            predicted[row][column] = " ".join(
                str(item) for item in cell.get("resolved_source_values") or []
            )
    expected = reference.get("cells") or []
    height = max(len(expected), len(predicted))
    width = max(
        max((len(row) for row in expected), default=0),
        max((len(row) for row in predicted), default=0),
    )
    pairs = []
    for row in range(height):
        for column in range(width):
            left = expected[row][column] if row < len(expected) and column < len(expected[row]) else ""
            right = predicted[row][column] if row < len(predicted) and column < len(predicted[row]) else ""
            pairs.append((_normalize(left), _normalize(right)))
    numeric = [pair for pair in pairs if _numeric(pair[0])]
    return {
        "structure_exact": len(expected) == len(predicted)
        and all(len(left) == len(right) for left, right in zip(expected, predicted)),
        "headers_exact": len(materialization.get("header_rows") or [])
        == int(reference.get("header_rows") or 0),
        "cells_exact": sum(left == right for left, right in pairs),
        "cells_total": len(pairs),
        "numeric_exact": sum(left == right for left, right in numeric),
        "numeric_total": len(numeric),
        "empty_exact": sum(left == right for left, right in pairs if not left),
        "empty_total": sum(not left for left, _ in pairs),
        "hallucinated_nonempty": sum(not left and bool(right) for left, right in pairs),
        "omitted_nonempty": sum(bool(left) and not right for left, right in pairs),
    }


def _failed_scheduled_score(reference: dict[str, Any]) -> dict[str, Any]:
    expected = reference.get("cells") or []
    width = max((len(row) for row in expected), default=0)
    values = [
        _normalize(row[column] if column < len(row) else "")
        for row in expected
        for column in range(width)
    ]
    return {
        "structure_exact": False,
        "headers_exact": False,
        "cells_exact": 0,
        "cells_total": len(values),
        "numeric_exact": 0,
        "numeric_total": sum(_numeric(value) for value in values),
        "empty_exact": 0,
        "empty_total": sum(not value for value in values),
        "hallucinated_nonempty": 0,
        "omitted_nonempty": sum(bool(value) for value in values),
    }


def _aggregate_scores(
    scores: list[dict[str, Any]],
    scheduled_total: int,
    accepted_scored_tables: int,
) -> dict[str, Any]:
    cells = sum(item["cells_total"] for item in scores)
    numeric = sum(item["numeric_total"] for item in scores)
    empty = sum(item["empty_total"] for item in scores)
    return {
        "scheduled_tables": scheduled_total,
        "accepted_scored_tables": accepted_scored_tables,
        "structure_exact_tables": sum(item["structure_exact"] for item in scores),
        "header_exact_tables": sum(item["headers_exact"] for item in scores),
        "cells_exact": sum(item["cells_exact"] for item in scores),
        "cells_total": cells,
        "cell_accuracy": round(sum(item["cells_exact"] for item in scores) / cells, 6) if cells else 0.0,
        "numeric_exact": sum(item["numeric_exact"] for item in scores),
        "numeric_total": numeric,
        "numeric_accuracy": round(sum(item["numeric_exact"] for item in scores) / numeric, 6) if numeric else 0.0,
        "empty_exact": sum(item["empty_exact"] for item in scores),
        "empty_total": empty,
        "empty_accuracy": round(sum(item["empty_exact"] for item in scores) / empty, 6) if empty else 0.0,
        "provider_or_validation_failed_scheduled_tables": (
            scheduled_total - accepted_scored_tables
        ),
    }


def _structural_case(table_key: str) -> str:
    return {
        "1:3": "wide_multi_row_header",
        "3:2": "wide_trade_multi_line_header",
        "4:1": "cross_page_continuation",
        "4:2": "grouped_header_sparse_totals",
        "5:3": "tax_summary_merged_section",
    }.get(table_key, "other")


def _normalize(value: Any) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", str(value or ""))).strip()


def _numeric(value: str) -> bool:
    return bool(re.fullmatch(r"[+\-]?[\d\s]+(?:[.,]\d+)?", value))


def _counts(values: Any) -> dict[str, int]:
    result: dict[str, int] = {}
    for value in values:
        result[value] = result.get(value, 0) + 1
    return dict(sorted(result.items()))


def _git_revision() -> str:
    import subprocess

    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True
    ).strip()


if __name__ == "__main__":
    raise SystemExit(main())
