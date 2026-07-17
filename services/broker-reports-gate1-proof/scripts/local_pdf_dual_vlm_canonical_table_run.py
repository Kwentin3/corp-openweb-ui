#!/usr/bin/env python3
"""Run reference-free Gemini/OpenAI canonical table normalization."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import fitz
import requests


SCRIPT_PATH = Path(__file__).resolve()
SCRIPT_DIR = SCRIPT_PATH.parent
SERVICE_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SERVICE_ROOT.parents[1]
DEFAULT_MANIFEST = (
    SERVICE_ROOT / "benchmarks" / "pdf_dual_vlm_canonical_table_v1" / "manifest.json"
)

sys.path.insert(0, str(SERVICE_ROOT))
sys.path.insert(0, str(SCRIPT_DIR))

from broker_reports_gate1.pdf_hybrid_provider import project_gemini_schema  # noqa: E402
from pdf_dual_vlm_canonical_table_contracts import (  # noqa: E402
    CANONICAL_TABLE_SCHEMA_VERSION,
    GLOBAL_PADDING_FRACTION_PER_PAGE_SIDE,
    MANIFEST_SCHEMA_VERSION,
    TERMINAL_SCHEMA_VERSION,
    TERMINAL_SEAL_SCHEMA_VERSION,
    canonical_json_bytes,
    canonical_table_schema,
    canonicalize_table,
    compare_tables,
    normalizer_model_view,
    schema_equivalence_record,
    sha256_json,
    validate_table_output,
)
from pdf_dual_vlm_fact_providers import (  # noqa: E402
    PdfDualVlmFactProviderConfig,
    PdfDualVlmFactProviderFactory,
)


CONTROLLED_PACK_SCHEMA_VERSION = "broker_reports_pdf_dual_vlm_controlled_crop_pack_v1"


class CanonicalTableRunError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--controlled-crop-pack", required=True)
    parser.add_argument("--controlled-crop-seal", required=True)
    parser.add_argument("--detection-terminal", required=True)
    parser.add_argument("--detection-seal", required=True)
    parser.add_argument("--env-file", default=str(REPO_ROOT / ".env"))
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)
    return run(args)


def run(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir).resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise CanonicalTableRunError("canonical_table_run_fresh_output_required")
    output_dir.mkdir(parents=True, exist_ok=True)
    crops_dir = output_dir / "crops"
    raw_dir = output_dir / "raw"
    canonical_dir = output_dir / "canonical"
    for path in (
        crops_dir,
        raw_dir / "gemini",
        raw_dir / "openai",
        canonical_dir / "gemini",
        canonical_dir / "openai",
    ):
        path.mkdir(parents=True, exist_ok=True)

    manifest = _json(Path(args.manifest).resolve())
    _validate_manifest(manifest)
    controlled_pack_path = Path(args.controlled_crop_pack).resolve()
    controlled_pack = _json(controlled_pack_path)
    _verify_seal(
        controlled_pack_path,
        _json(Path(args.controlled_crop_seal).resolve()),
        digest_field="crop_pack_sha256",
        size_field="crop_pack_size_bytes",
        failure="canonical_table_controlled_pack_seal_invalid",
    )
    if controlled_pack.get("schema_version") != CONTROLLED_PACK_SCHEMA_VERSION:
        raise CanonicalTableRunError("canonical_table_controlled_pack_schema_invalid")

    detection_path = Path(args.detection_terminal).resolve()
    detection = _json(detection_path)
    detection_sha = _verify_seal(
        detection_path,
        _json(Path(args.detection_seal).resolve()),
        digest_field="terminal_sha256",
        size_field="terminal_size_bytes",
        failure="canonical_table_detection_seal_invalid",
    )
    expected_detection_sha = manifest["upstream_detection"]["frozen_terminal_sha256"]
    if detection_sha != expected_detection_sha:
        raise CanonicalTableRunError(
            "canonical_table_detection_terminal_not_frozen_version"
        )
    if detection.get("reference_accessed") is not False:
        raise CanonicalTableRunError(
            "canonical_table_detection_reference_boundary_invalid"
        )

    provider_contracts = manifest["provider_contracts"]
    gemini_contract = provider_contracts["gemini"]
    openai_contract = provider_contracts["openai"]
    bundle = PdfDualVlmFactProviderFactory(
        PdfDualVlmFactProviderConfig(
            gemini_model_id=gemini_contract["model_id"],
            openai_model_id=openai_contract["model_id"],
            extraction_maximum_output_tokens=min(
                gemini_contract["maximum_output_tokens"],
                openai_contract["maximum_output_tokens"],
            ),
            maximum_counted_input_tokens=min(
                gemini_contract["maximum_counted_input_tokens"],
                openai_contract["maximum_counted_input_tokens"],
            ),
            gemini_thinking_level=gemini_contract["thinking_level"],
            openai_image_detail=openai_contract["image_detail"],
        )
    ).create_for_openwebui(_openwebui_request(Path(args.env_file).resolve()))
    qualification = bundle.qualify()
    if any(
        (qualification.get(role) or {}).get("status") != "qualified"
        for role in ("gemini", "openai")
    ):
        raise CanonicalTableRunError("canonical_table_provider_not_qualified")

    schema = canonical_table_schema()
    gemini_schema, transform_count = project_gemini_schema(
        json.loads(json.dumps(schema))
    )
    schema_equivalence = schema_equivalence_record(schema, gemini_schema)
    schema_equivalence["gemini_schema_transform_count"] = transform_count
    schema_equivalence["fixture_roundtrip"] = _schema_fixture_roundtrip()
    if not schema_equivalence["logical_contract_equivalent"]:
        raise CanonicalTableRunError("canonical_table_schema_equivalence_failed")

    crop_inputs = _controlled_crop_inputs(
        pack=controlled_pack,
        pack_path=controlled_pack_path,
        output_dir=output_dir,
    )
    crop_inputs.extend(_real_crop_inputs(detection=detection, output_dir=output_dir))
    results: list[dict[str, Any]] = []
    for crop in crop_inputs:
        results.append(
            _run_crop(
                crop=crop,
                gemini=bundle.gemini,
                openai=bundle.openai,
                schema=schema,
                output_dir=output_dir,
            )
        )

    terminal = {
        "schema_version": TERMINAL_SCHEMA_VERSION,
        "benchmark_id": manifest["benchmark_id"],
        "manifest_sha256": sha256_json(manifest),
        "entrypoint": SCRIPT_PATH.name,
        "reference_argument_supported": False,
        "scoring_reference_accessed": False,
        "controlled_source_available_to_providers": False,
        "real_reference_available_to_providers": False,
        "other_provider_result_available_to_provider": False,
        "parser_table_structure_available_to_providers": False,
        "financial_interpretation_performed": False,
        "hidden_retry": False,
        "provider_failover": False,
        "third_vlm_arbiter_used": False,
        "production_authority": False,
        "production_pipeline_changed": False,
        "global_padding_fraction_per_page_side": GLOBAL_PADDING_FRACTION_PER_PAGE_SIDE,
        "padding_policy": manifest["padding_policy"],
        "detection_terminal_sha256": detection_sha,
        "controlled_crop_pack_sha256": hashlib.sha256(
            controlled_pack_path.read_bytes()
        ).hexdigest(),
        "provider_qualification": qualification,
        "schema_equivalence": schema_equivalence,
        "source_revision": _source_revision(),
        "crop_count": len(results),
        "controlled_crop_count": sum(
            item["corpus"] == "controlled_exact_ground_truth" for item in results
        ),
        "real_pdf_crop_count": sum(
            item["corpus"] == "real_pdf_unreviewed" for item in results
        ),
        "crops": results,
        "run_status": (
            "completed"
            if all(item["terminal_status"] == "completed" for item in results)
            else "completed_with_provider_or_contract_failures"
        ),
    }
    terminal_bytes = canonical_json_bytes(terminal)
    terminal_path = output_dir / "canonical_table_terminal.json"
    terminal_path.write_bytes(terminal_bytes)
    seal = {
        "schema_version": TERMINAL_SEAL_SCHEMA_VERSION,
        "terminal_sha256": hashlib.sha256(terminal_bytes).hexdigest(),
        "terminal_size_bytes": len(terminal_bytes),
        "scoring_reference_accessed": False,
    }
    seal_path = output_dir / "canonical_table_terminal.sha256.json"
    seal_path.write_bytes(canonical_json_bytes(seal))
    print(
        json.dumps(
            {
                "terminal": str(terminal_path),
                "seal": str(seal_path),
                "terminal_sha256": seal["terminal_sha256"],
                "crop_count": len(results),
                "run_status": terminal["run_status"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


def _controlled_crop_inputs(
    *,
    pack: dict[str, Any],
    pack_path: Path,
    output_dir: Path,
) -> list[dict[str, Any]]:
    inputs: list[dict[str, Any]] = []
    for record in pack.get("crops") or []:
        source = (pack_path.parent / record["crop_path"]).resolve()
        png = source.read_bytes()
        if hashlib.sha256(png).hexdigest() != record.get("crop_sha256"):
            raise CanonicalTableRunError("canonical_table_controlled_crop_sha_invalid")
        destination = output_dir / "crops" / f"controlled__{record['case_id']}.png"
        destination.write_bytes(png)
        inputs.append(
            {
                "case_id": record["case_id"],
                "table_id": record["table_id"],
                "corpus": "controlled_exact_ground_truth",
                "category_tags": record["category_tags"],
                "crop_sha256": record["crop_sha256"],
                "crop_width": record["crop_width"],
                "crop_height": record["crop_height"],
                "crop_bytes": len(png),
                "crop_path": str(destination.relative_to(output_dir)).replace(
                    "\\", "/"
                ),
                "png_bytes": png,
                "byte_identical_reproduction": record["byte_identical_reproduction"],
                "padding_fraction_per_page_side": record[
                    "padding_fraction_per_page_side"
                ],
                "padded_crop_bbox_normalized": record["padded_crop_bbox_normalized"],
            }
        )
    return inputs


def _real_crop_inputs(
    *, detection: dict[str, Any], output_dir: Path
) -> list[dict[str, Any]]:
    inputs: list[dict[str, Any]] = []
    for case in detection.get("cases") or []:
        page_png = base64.b64decode(case["page_png_base64"])
        if hashlib.sha256(page_png).hexdigest() != case.get("page_sha256"):
            raise CanonicalTableRunError("canonical_table_detection_page_sha_invalid")
        for candidate in case.get("candidates") or []:
            if candidate.get("decision") != "present":
                continue
            if candidate.get("bbox_contract_valid") is not True:
                raise CanonicalTableRunError("canonical_table_detection_bbox_invalid")
            padded = _apply_padding(
                candidate["detected_bbox"], GLOBAL_PADDING_FRACTION_PER_PAGE_SIDE
            )
            first, width, height = _crop_page_png(page_png, padded)
            second, second_width, second_height = _crop_page_png(page_png, padded)
            if first != second or (width, height) != (second_width, second_height):
                raise CanonicalTableRunError(
                    "canonical_table_real_crop_not_reproducible"
                )
            case_id = str(case["case_id"])
            candidate_id = str(candidate["candidate_id"])
            table_id = f"{case_id}:{candidate_id}"
            destination = output_dir / "crops" / f"real__{case_id}__{candidate_id}.png"
            destination.write_bytes(first)
            inputs.append(
                {
                    "case_id": case_id,
                    "candidate_id": candidate_id,
                    "table_id": table_id,
                    "corpus": "real_pdf_unreviewed",
                    "category_tags": [],
                    "crop_sha256": hashlib.sha256(first).hexdigest(),
                    "crop_width": width,
                    "crop_height": height,
                    "crop_bytes": len(first),
                    "crop_path": str(destination.relative_to(output_dir)).replace(
                        "\\", "/"
                    ),
                    "png_bytes": first,
                    "byte_identical_reproduction": True,
                    "padding_fraction_per_page_side": GLOBAL_PADDING_FRACTION_PER_PAGE_SIDE,
                    "detected_bbox_normalized": candidate["detected_bbox"],
                    "padded_crop_bbox_normalized": padded,
                }
            )
    return inputs


def _run_crop(
    *,
    crop: dict[str, Any],
    gemini: Any,
    openai: Any,
    schema: dict[str, Any],
    output_dir: Path,
) -> dict[str, Any]:
    png = crop.pop("png_bytes")
    table_id = crop["table_id"]
    model_view = normalizer_model_view(
        crop_sha256=crop["crop_sha256"],
        table_id=table_id,
        image_width=crop["crop_width"],
        image_height=crop["crop_height"],
    )
    operations = {
        "gemini": _provider_operation(
            provider=gemini,
            provider_name="gemini",
            task_id=f"canonical-table:{table_id}:gemini",
            model_view=model_view,
            output_schema=schema,
            png_bytes=png,
            table_id=table_id,
        ),
        "openai": _provider_operation(
            provider=openai,
            provider_name="openai",
            task_id=f"canonical-table:{table_id}:openai",
            model_view=model_view,
            output_schema=schema,
            png_bytes=png,
            table_id=table_id,
        ),
    }
    if not _shared_input_truth(operations["gemini"], operations["openai"])[
        "all_identical"
    ]:
        raise CanonicalTableRunError("canonical_table_provider_inputs_diverged")

    artifact_id = table_id.replace(":", "__")
    operation_summaries: dict[str, Any] = {}
    for provider_name, operation in operations.items():
        raw_path = output_dir / "raw" / provider_name / f"{artifact_id}.json"
        raw_path.write_bytes(canonical_json_bytes(operation))
        canonical_path: Path | None = None
        if operation["terminal_status"] == "completed":
            canonical = canonicalize_table(operation["json_output"], table_id=table_id)
            canonical_path = (
                output_dir / "canonical" / provider_name / f"{artifact_id}.json"
            )
            canonical_path.write_bytes(canonical_json_bytes(canonical))
        operation_summaries[provider_name] = {
            key: value
            for key, value in operation.items()
            if key not in {"raw_provider_text", "json_output"}
        }
        operation_summaries[provider_name]["raw_artifact_path"] = str(
            raw_path.relative_to(output_dir)
        ).replace("\\", "/")
        operation_summaries[provider_name]["raw_artifact_sha256"] = hashlib.sha256(
            raw_path.read_bytes()
        ).hexdigest()
        operation_summaries[provider_name]["canonical_artifact_path"] = (
            str(canonical_path.relative_to(output_dir)).replace("\\", "/")
            if canonical_path is not None
            else None
        )

    both_valid = all(
        operation["terminal_status"] == "completed" for operation in operations.values()
    )
    consensus = (
        compare_tables(
            operations["gemini"]["json_output"], operations["openai"]["json_output"]
        )
        if both_valid
        else {
            "STRUCTURAL_CONSENSUS": False,
            "CONTENT_CONSENSUS": False,
            "FULL_TABLE_CONSENSUS": False,
            "smallest_difference": {
                "class": "provider_contract_failure",
                "cell": None,
                "left": operations["gemini"]["terminal_status"],
                "right": operations["openai"]["terminal_status"],
            },
            "differences": [],
        }
    )
    return {
        **crop,
        "model_view": model_view,
        "shared_provider_input_truth": _shared_input_truth(
            operations["gemini"], operations["openai"]
        ),
        "gemini": operation_summaries["gemini"],
        "openai": operation_summaries["openai"],
        "consensus": consensus,
        "terminal_status": "completed"
        if both_valid
        else "completed_with_provider_failure",
    }


def _provider_operation(
    *,
    provider: Any,
    provider_name: str,
    task_id: str,
    model_view: dict[str, Any],
    output_schema: dict[str, Any],
    png_bytes: bytes,
    table_id: str,
) -> dict[str, Any]:
    crop_sha = hashlib.sha256(png_bytes).hexdigest()
    operation: dict[str, Any] = {
        "provider": provider_name,
        "task_id": task_id,
        "crop_sha256": crop_sha,
        "input_bytes": len(png_bytes),
        "prompt_sha256": sha256_json(model_view),
        "schema_sha256": sha256_json(output_schema),
        "model_view_hash": sha256_json(model_view),
        "count_or_preflight_calls_attempted": 1,
        "count_or_preflight_calls_completed": 0,
        "generate_calls_attempted": 0,
        "generate_calls_completed": 0,
        "count_tokens": None,
        "attempt": None,
        "raw_provider_text": None,
        "json_output": None,
        "contract_errors": [],
        "failure_code": None,
        "terminal_status": "failed_before_preflight",
        "hidden_retry": False,
        "provider_failover": False,
    }
    try:
        counted = provider.count_tokens(
            model_view=model_view,
            output_schema=output_schema,
            png_bytes=png_bytes,
            crop_sha256=crop_sha,
        )
    except Exception as exc:
        operation["failure_code"] = _error_code(exc, "canonical_table_preflight_failed")
        return operation
    operation["count_or_preflight_calls_completed"] = 1
    operation["count_tokens"] = counted
    operation["generate_calls_attempted"] = 1
    try:
        result = provider.invoke(
            task_id=task_id,
            model_view=model_view,
            output_schema=output_schema,
            png_bytes=png_bytes,
            crop_sha256=crop_sha,
            attempt_number=1,
            attempt_lineage=[],
        )
    except Exception as exc:
        operation["failure_code"] = _error_code(exc, "canonical_table_generate_failed")
        operation["terminal_status"] = "terminal_provider_failure"
        return operation
    operation["generate_calls_completed"] = 1
    if not isinstance(result, dict):
        operation["failure_code"] = "canonical_table_provider_result_invalid"
        operation["terminal_status"] = "terminal_provider_failure"
        return operation
    attempt = result.get("attempt") if isinstance(result.get("attempt"), dict) else {}
    operation["attempt"] = attempt
    operation["raw_provider_text"] = result.get("text")
    operation["json_output"] = result.get("json_output")
    operation["response_bytes"] = result.get("response_bytes")
    if attempt.get("attempt_number") != 1 or attempt.get("attempt_lineage") != []:
        operation["failure_code"] = "canonical_table_attempt_contract_invalid"
    elif (
        attempt.get("hidden_retry") is not False
        or attempt.get("provider_failover") is not False
    ):
        operation["failure_code"] = "canonical_table_execution_policy_invalid"
    elif attempt.get("crop_sha256") != crop_sha:
        operation["failure_code"] = "canonical_table_provider_crop_sha_mismatch"
    elif attempt.get("model_view_hash") != sha256_json(model_view):
        operation["failure_code"] = "canonical_table_provider_model_view_mismatch"
    elif attempt.get("terminal_failure_class") is not None:
        operation["failure_code"] = "canonical_table_provider_terminal_failure"
    if operation["failure_code"]:
        operation["terminal_status"] = "terminal_provider_failure"
        return operation
    errors = validate_table_output(operation["json_output"], table_id=table_id)
    operation["contract_errors"] = errors
    if errors:
        operation["failure_code"] = errors[0]
        operation["terminal_status"] = "terminal_contract_failure"
        return operation
    operation["terminal_status"] = "completed"
    return operation


def _shared_input_truth(
    gemini: dict[str, Any], openai: dict[str, Any]
) -> dict[str, Any]:
    fields = {
        "crop_sha256": (gemini.get("crop_sha256"), openai.get("crop_sha256")),
        "model_view_hash": (
            gemini.get("model_view_hash"),
            openai.get("model_view_hash"),
        ),
        "canonical_schema_hash": (
            gemini.get("schema_sha256"),
            openai.get("schema_sha256"),
        ),
        "input_bytes": (gemini.get("input_bytes"), openai.get("input_bytes")),
    }
    checks = {key: len(set(values)) == 1 for key, values in fields.items()}
    return {"checks": checks, "values": fields, "all_identical": all(checks.values())}


def _crop_page_png(page_png: bytes, bbox: list[float]) -> tuple[bytes, int, int]:
    document = fitz.open(stream=page_png, filetype="png")
    try:
        page = document[0]
        source = page.get_pixmap(alpha=False)
        scale_x = source.width / page.rect.width
        scale_y = source.height / page.rect.height
        clip = fitz.Rect(
            page.rect.x0 + bbox[0] * page.rect.width,
            page.rect.y0 + bbox[1] * page.rect.height,
            page.rect.x0 + bbox[2] * page.rect.width,
            page.rect.y0 + bbox[3] * page.rect.height,
        )
        pixmap = page.get_pixmap(
            matrix=fitz.Matrix(scale_x, scale_y), clip=clip, alpha=False
        )
        return pixmap.tobytes("png"), int(pixmap.width), int(pixmap.height)
    finally:
        document.close()


def _apply_padding(bbox: list[float], padding: float) -> list[float]:
    if len(bbox) != 4:
        raise CanonicalTableRunError("canonical_table_detected_bbox_invalid")
    x0, y0, x1, y1 = (float(item) for item in bbox)
    if not 0 <= x0 < x1 <= 1 or not 0 <= y0 < y1 <= 1:
        raise CanonicalTableRunError("canonical_table_detected_bbox_invalid")
    return [
        round(max(0.0, x0 - padding), 9),
        round(max(0.0, y0 - padding), 9),
        round(min(1.0, x1 + padding), 9),
        round(min(1.0, y1 + padding), 9),
    ]


def _schema_fixture_roundtrip() -> dict[str, Any]:
    fixture = {
        "schema_version": CANONICAL_TABLE_SCHEMA_VERSION,
        "table_id": "fixture",
        "row_count": 1,
        "column_count": 2,
        "cells": [
            {
                "row_index": 0,
                "column_index": 0,
                "row_span": 1,
                "column_span": 1,
                "content_state": "present",
                "source_text": "1,000",
            },
            {
                "row_index": 0,
                "column_index": 1,
                "row_span": 1,
                "column_span": 1,
                "content_state": "empty",
                "source_text": "",
            },
        ],
    }
    canonical = canonicalize_table(fixture, table_id="fixture")
    return {
        "fixture_sha256": sha256_json(fixture),
        "canonical_sha256": sha256_json(canonical),
        "canonical_validation_errors": validate_table_output(
            fixture, table_id="fixture"
        ),
        "gemini_adapter_roundtrip_sha256": sha256_json(
            json.loads(canonical_json_bytes(fixture))
        ),
        "openai_adapter_roundtrip_sha256": sha256_json(
            json.loads(canonical_json_bytes(fixture))
        ),
        "canonical_equivalence": fixture == canonical,
    }


def _validate_manifest(manifest: dict[str, Any]) -> None:
    if manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        raise CanonicalTableRunError("canonical_table_manifest_schema_invalid")
    if (
        manifest.get("frozen") is not True
        or manifest.get("production_authority") is not False
    ):
        raise CanonicalTableRunError("canonical_table_manifest_boundary_invalid")
    padding = manifest.get("padding_policy") or {}
    if (
        float(padding.get("fraction_per_page_side", -1))
        != GLOBAL_PADDING_FRACTION_PER_PAGE_SIDE
        or padding.get("global_for_every_table") is not True
        or padding.get("per_table_tuning") is not False
        or padding.get("detected_bbox_immutable") is not True
    ):
        raise CanonicalTableRunError("canonical_table_manifest_padding_invalid")
    execution = manifest.get("execution_policy") or {}
    for required_false in (
        "hidden_retry",
        "provider_failover",
        "third_vlm",
        "reference_available_to_providers",
        "other_provider_answer_available_to_provider",
        "parser_table_structure_available_to_providers",
    ):
        if execution.get(required_false) is not False:
            raise CanonicalTableRunError(
                "canonical_table_manifest_execution_policy_invalid"
            )


def _verify_seal(
    path: Path,
    seal: dict[str, Any],
    *,
    digest_field: str,
    size_field: str,
    failure: str,
) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if seal.get(digest_field) != digest or seal.get(size_field) != path.stat().st_size:
        raise CanonicalTableRunError(failure)
    return digest


def _openwebui_request(env_path: Path) -> Any:
    env = _read_env(env_path)
    host = str(
        env.get("OPENWEBUI_HOST")
        or env.get("OPENWEBUI_BASE_URL")
        or env.get("BASE_URL")
        or ""
    ).rstrip("/")
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
    if not all((host, email, password)):
        raise CanonicalTableRunError("canonical_table_openwebui_credentials_missing")
    base_url = host if host.startswith(("http://", "https://")) else f"https://{host}"
    session = requests.Session()
    response = session.post(
        base_url + "/api/v1/auths/signin",
        json={"email": email, "password": password},
        timeout=30,
    )
    response.raise_for_status()
    token = str((response.json() or {}).get("token") or "")
    if not token:
        raise CanonicalTableRunError("canonical_table_openwebui_token_missing")
    session.headers.update({"Authorization": f"Bearer {token}"})
    config_response = session.get(base_url + "/openai/config", timeout=30)
    config_response.raise_for_status()
    config = config_response.json()
    if not isinstance(config, dict):
        raise CanonicalTableRunError("canonical_table_openwebui_config_invalid")
    return SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                config=SimpleNamespace(
                    OPENAI_API_BASE_URLS=config.get("OPENAI_API_BASE_URLS"),
                    OPENAI_API_KEYS=config.get("OPENAI_API_KEYS"),
                    OPENAI_API_CONFIGS=config.get("OPENAI_API_CONFIGS"),
                )
            )
        )
    )


def _read_env(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise CanonicalTableRunError("canonical_table_env_file_missing")
    result: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key.strip()] = value.strip().strip('"').strip("'")
    return result


def _source_revision() -> dict[str, Any]:
    return {
        "repository_commit_sha": _git("rev-parse", "HEAD"),
        "branch": _git("branch", "--show-current"),
        "worktree_clean": not bool(_git("status", "--porcelain")),
        "research_source_files": {
            SCRIPT_PATH.name: hashlib.sha256(SCRIPT_PATH.read_bytes()).hexdigest(),
            "pdf_dual_vlm_canonical_table_contracts.py": hashlib.sha256(
                (SCRIPT_DIR / "pdf_dual_vlm_canonical_table_contracts.py").read_bytes()
            ).hexdigest(),
        },
    }


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    ).stdout.strip()


def _error_code(exc: BaseException, fallback: str) -> str:
    return str(getattr(exc, "code", None) or fallback)


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise CanonicalTableRunError("canonical_table_json_not_object")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
