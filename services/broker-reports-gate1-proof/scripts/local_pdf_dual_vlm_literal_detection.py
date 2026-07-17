#!/usr/bin/env python3
"""Run reference-free table detection and predeclared crop-padding renders."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import struct
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import requests


SCRIPT_PATH = Path(__file__).resolve()
SCRIPT_DIR = SCRIPT_PATH.parent
SERVICE_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SERVICE_ROOT.parents[1]
DEFAULT_MANIFEST = SERVICE_ROOT / "benchmarks" / "pdf_dual_vlm_literal_v1" / "manifest.json"
DEFAULT_CORPUS_ROOT = (
    REPO_ROOT
    / "local"
    / "stage2"
    / "broker_reports_pdf_structural_holdout_public_v5_2026-07-15"
    / "corpus"
)

sys.path.insert(0, str(SERVICE_ROOT))
sys.path.insert(0, str(SCRIPT_DIR))

from broker_reports_gate1.pdf_grid_experiment_provider import (  # noqa: E402
    PdfGridExperimentProviderFactory,
    PdfGridProviderConfig,
)
from broker_reports_gate1.pdf_table_raster import (  # noqa: E402
    PdfTableRasterConfig,
    PdfTableRasterFactory,
)
from pdf_dual_vlm_literal_contracts import (  # noqa: E402
    PADDING_VARIANTS,
    canonical_json_bytes,
    detection_model_view,
    detection_schema,
    normalized_bbox_to_points,
    padding_transformation,
    sha256_json,
    validate_detection_output,
    valid_bbox,
)


DETECTION_TERMINAL_SCHEMA = "broker_reports_pdf_dual_vlm_literal_detection_terminal_v2"
DETECTION_SEAL_SCHEMA = "broker_reports_pdf_dual_vlm_literal_detection_terminal_seal_v2"


class LiteralDetectionError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--corpus-root", default=str(DEFAULT_CORPUS_ROOT))
    parser.add_argument("--env-file", default=str(REPO_ROOT / ".env"))
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)
    return run(args)


def run(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir).resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise LiteralDetectionError("literal_detection_fresh_output_required")
    output_dir.mkdir(parents=True, exist_ok=True)
    terminal_path = output_dir / "detection.terminal.private.json"
    seal_path = output_dir / "detection.terminal.private.sha256.json"
    terminal: dict[str, Any] = {
        "schema_version": DETECTION_TERMINAL_SCHEMA,
        "entrypoint": SCRIPT_PATH.name,
        "reference_argument_supported": False,
        "reference_accessed": False,
        "production_authority": False,
        "production_pipeline_changed": False,
        "openwebui_core_changed": False,
        "human_reference_available_to_detector": False,
        "parser_text_available_to_detector": False,
        "hidden_retry": False,
        "provider_failover": False,
        "manifest_sha256": None,
        "source_revision": _source_revision(),
        "provider_qualification": None,
        "cases": [],
        "failures": [],
        "run_status": "failed_before_execution",
    }
    exit_code = 1
    try:
        manifest_path = Path(args.manifest).resolve()
        manifest = _json(manifest_path)
        if manifest.get("schema_version") != "broker_reports_pdf_dual_vlm_literal_manifest_v1":
            raise LiteralDetectionError("literal_detection_manifest_invalid")
        terminal["manifest_sha256"] = sha256_json(manifest)
        cases = _source_cases(manifest)
        detector_contract = (manifest.get("provider_contracts") or {}).get("detection") or {}
        detector = PdfGridExperimentProviderFactory(
            PdfGridProviderConfig(
                provider_profile=str(detector_contract["provider_profile"]),
                model_id=str(detector_contract["model_id"]),
                maximum_output_tokens=int(detector_contract["maximum_output_tokens"]),
                maximum_counted_input_tokens=int(
                    detector_contract["maximum_counted_input_tokens"]
                ),
                thinking_level=str(detector_contract["thinking_level"]),
            )
        ).create_for_openwebui(_openwebui_request(Path(args.env_file).resolve()))
        qualification = detector.qualify()
        terminal["provider_qualification"] = qualification
        if qualification.get("status") != "qualified":
            raise LiteralDetectionError("literal_detection_provider_not_qualified")
        renderer = PdfTableRasterFactory(PdfTableRasterConfig(padding_points=0)).create()
        corpus_root = Path(args.corpus_root).resolve()
        for case in cases:
            try:
                terminal["cases"].append(
                    _run_case(
                        case=case,
                        corpus_root=corpus_root,
                        detector=detector,
                        renderer=renderer,
                    )
                )
            except Exception as exc:
                code = _error_code(exc, "literal_detection_case_unexpected_failure")
                terminal["cases"].append(
                    {
                        "case_id": case["case_id"],
                        "page_number": case["page_number"],
                        "terminal_status": "failed",
                        "failure_code": code,
                        "detection": None,
                        "candidates": [],
                    }
                )
                terminal["failures"].append({"case_id": case["case_id"], "code": code})
        for case in terminal["cases"]:
            if case.get("terminal_status") != "completed":
                terminal["failures"].append(
                    {
                        "case_id": case.get("case_id"),
                        "code": case.get("failure_code") or "literal_detection_case_failed",
                    }
                )
        terminal["run_status"] = (
            "completed" if not terminal["failures"] else "completed_with_failures"
        )
        exit_code = 0 if terminal["run_status"] == "completed" else 1
    except Exception as exc:
        terminal["failures"].append(
            {"case_id": None, "code": _error_code(exc, "literal_detection_runner_failure")}
        )
        terminal["run_status"] = "failed_before_case_completion"
    terminal_bytes = canonical_json_bytes(terminal)
    terminal_path.write_bytes(terminal_bytes)
    seal = {
        "schema_version": DETECTION_SEAL_SCHEMA,
        "terminal_sha256": hashlib.sha256(terminal_bytes).hexdigest(),
        "terminal_size_bytes": len(terminal_bytes),
        "reference_accessed": False,
    }
    seal_path.write_bytes(canonical_json_bytes(seal))
    print(
        json.dumps(
            {
                "run_status": terminal["run_status"],
                "terminal": str(terminal_path),
                "seal": str(seal_path),
                "terminal_sha256": seal["terminal_sha256"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return exit_code


def _run_case(*, case: dict[str, Any], corpus_root: Path, detector: Any, renderer: Any) -> dict[str, Any]:
    case_id = str(case["case_id"])
    pdf_path = _source_path(corpus_root, str(case["relative_pdf"]))
    pdf_bytes = pdf_path.read_bytes()
    if len(pdf_bytes) != int(case["pdf_bytes"]) or hashlib.sha256(pdf_bytes).hexdigest() != case["pdf_sha256"]:
        raise LiteralDetectionError("literal_detection_source_identity_mismatch")
    full_page = renderer.render_full_page(
        pdf_bytes=pdf_bytes,
        pdf_sha256=str(case["pdf_sha256"]),
        document_ref=case_id,
        page_ref=f"literal_detection_{case_id}",
        page_number=int(case["page_number"]),
        expected_page_bbox=[float(item) for item in case["page_bbox_points"]],
        dpi=int(case["render_dpi"]),
    )
    page_png = base64.b64decode(full_page["private_png_base64"])
    page_sha = hashlib.sha256(page_png).hexdigest()
    model_view = detection_model_view(
        page_number=int(case["page_number"]), page_sha256=page_sha
    )
    operation = _provider_operation(
        provider=detector,
        task_id=f"literal_detection:{case_id}",
        model_view=model_view,
        output_schema=detection_schema(),
        png_bytes=page_png,
    )
    result = operation.get("json_output")
    errors = validate_detection_output(result, page_number=int(case["page_number"]))
    candidates: list[dict[str, Any]] = []
    if isinstance(result, dict) and isinstance(result.get("candidates"), list):
        for candidate in result["candidates"]:
            if not isinstance(candidate, dict):
                continue
            candidate_record = {
                "candidate_id": candidate.get("candidate_id"),
                "decision": candidate.get("decision"),
                "detected_bbox": copy_list(candidate.get("bbox") or []),
                "bbox_contract_valid": valid_bbox(candidate.get("bbox")),
                "terminal_contract_error": (
                    None
                    if valid_bbox(candidate.get("bbox"))
                    else "literal_detection_candidate_bbox_invalid"
                ),
                "uncertainty_codes": list(candidate.get("uncertainty_codes") or []),
                "padding_variants": [],
            }
            candidates.append(candidate_record)
            if not candidate_record["bbox_contract_valid"]:
                continue
            for padding in PADDING_VARIANTS:
                transformation = padding_transformation(candidate["bbox"], padding)
                point_bbox = normalized_bbox_to_points(
                    transformation["padded_crop_bbox"], case["page_bbox_points"]
                )
                first = renderer.render(
                    pdf_bytes=pdf_bytes,
                    pdf_sha256=str(case["pdf_sha256"]),
                    document_ref=case_id,
                    page_number=int(case["page_number"]),
                    table_ref=f"{case_id}_{candidate['candidate_id']}_p{padding}",
                    table_bbox=point_bbox,
                    dpi=int(case["render_dpi"]),
                )
                second = renderer.render(
                    pdf_bytes=pdf_bytes,
                    pdf_sha256=str(case["pdf_sha256"]),
                    document_ref=case_id,
                    page_number=int(case["page_number"]),
                    table_ref=f"{case_id}_{candidate['candidate_id']}_p{padding}",
                    table_bbox=point_bbox,
                    dpi=int(case["render_dpi"]),
                )
                first_png = base64.b64decode(first["private_png_base64"])
                second_png = base64.b64decode(second["private_png_base64"])
                width, height = _png_dimensions(first_png)
                candidate_record["padding_variants"].append(
                    {
                        **transformation,
                        "padded_crop_bbox_points": [round(item, 6) for item in point_bbox],
                        "crop_sha256": hashlib.sha256(first_png).hexdigest(),
                        "crop_bytes": len(first_png),
                        "crop_width": width,
                        "crop_height": height,
                        "byte_identical_reproduction": first_png == second_png,
                        "png_base64": base64.b64encode(first_png).decode("ascii"),
                    }
                )
    return {
        "case_id": case_id,
        "document_sha256": case["pdf_sha256"],
        "page_number": case["page_number"],
        "page_sha256": page_sha,
        "page_dimensions": list(_png_dimensions(page_png)),
        "page_png_base64": base64.b64encode(page_png).decode("ascii"),
        "detection": operation,
        "detection_contract_errors": errors,
        "candidates": candidates,
        "terminal_status": "completed" if not errors and not operation.get("failure_code") else "failed",
        "failure_code": errors[0] if errors else operation.get("failure_code"),
    }


def _provider_operation(
    *,
    provider: Any,
    task_id: str,
    model_view: dict[str, Any],
    output_schema: dict[str, Any],
    png_bytes: bytes,
) -> dict[str, Any]:
    crop_sha = hashlib.sha256(png_bytes).hexdigest()
    operation: dict[str, Any] = {
        "task_id": task_id,
        "image_bytes": len(png_bytes),
        "crop_sha256": crop_sha,
        "prompt_sha256": sha256_json(model_view),
        "schema_sha256": sha256_json(output_schema),
        "model_view_hash": sha256_json(model_view),
        "count_or_preflight_calls_attempted": 1,
        "count_or_preflight_calls_completed": 0,
        "generate_calls_attempted": 0,
        "generate_calls_completed": 0,
        "count_tokens": None,
        "attempt": None,
        "json_output": None,
        "raw_provider_text": None,
        "response_bytes": None,
        "failure_code": None,
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
        operation["failure_code"] = _error_code(exc, "literal_detection_preflight_failed")
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
        operation["failure_code"] = _error_code(exc, "literal_detection_generate_failed")
        return operation
    operation["generate_calls_completed"] = 1
    if not isinstance(result, dict):
        operation["failure_code"] = "literal_detection_provider_result_invalid"
        return operation
    attempt = result.get("attempt") if isinstance(result.get("attempt"), dict) else {}
    operation["attempt"] = attempt
    operation["json_output"] = result.get("json_output")
    operation["raw_provider_text"] = result.get("text")
    operation["response_bytes"] = result.get("response_bytes")
    if attempt.get("attempt_number") != 1 or attempt.get("attempt_lineage") != []:
        operation["failure_code"] = "literal_detection_attempt_contract_invalid"
    elif attempt.get("hidden_retry") is not False or attempt.get("provider_failover") is not False:
        operation["failure_code"] = "literal_detection_execution_policy_invalid"
    elif attempt.get("crop_sha256") != crop_sha:
        operation["failure_code"] = "literal_detection_provider_crop_sha_mismatch"
    elif attempt.get("model_view_hash") != sha256_json(model_view):
        operation["failure_code"] = "literal_detection_provider_model_view_mismatch"
    elif attempt.get("terminal_failure_class") is not None:
        operation["failure_code"] = "literal_detection_provider_terminal_failure"
    return operation


def _source_cases(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    contract = manifest.get("source_case_manifest") or {}
    path = _repo_path(contract.get("path"))
    if hashlib.sha256(path.read_bytes()).hexdigest() != contract.get("file_sha256"):
        raise LiteralDetectionError("literal_detection_source_manifest_sha_mismatch")
    source = _json(path)
    cases = source.get("cases")
    if not isinstance(cases, list) or len(cases) != manifest.get("case_count"):
        raise LiteralDetectionError("literal_detection_source_cases_invalid")
    allowed = set(contract.get("case_fields_imported") or [])
    result = []
    for case in cases:
        if not isinstance(case, dict) or not allowed <= set(case):
            raise LiteralDetectionError("literal_detection_source_case_invalid")
        result.append({key: case[key] for key in allowed})
    return result


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
        raise LiteralDetectionError("literal_detection_openwebui_credentials_missing")
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
        raise LiteralDetectionError("literal_detection_openwebui_token_missing")
    session.headers.update({"Authorization": f"Bearer {token}"})
    config_response = session.get(base_url + "/openai/config", timeout=30)
    config_response.raise_for_status()
    config = config_response.json()
    if not isinstance(config, dict):
        raise LiteralDetectionError("literal_detection_openwebui_config_invalid")
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
        raise LiteralDetectionError("literal_detection_env_file_missing")
    result: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key.strip()] = value.strip().strip('"').strip("'")
    return result


def _source_revision() -> dict[str, Any]:
    commit = _git("rev-parse", "HEAD")
    status = _git("status", "--porcelain")
    return {
        "repository_commit_sha": commit,
        "branch": _git("branch", "--show-current"),
        "worktree_clean": not bool(status),
        "research_source_files": {
            SCRIPT_PATH.name: hashlib.sha256(SCRIPT_PATH.read_bytes()).hexdigest(),
            "pdf_dual_vlm_literal_contracts.py": hashlib.sha256(
                (SCRIPT_DIR / "pdf_dual_vlm_literal_contracts.py").read_bytes()
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


def _png_dimensions(value: bytes) -> tuple[int, int]:
    if len(value) < 24 or value[:8] != b"\x89PNG\r\n\x1a\n":
        raise LiteralDetectionError("literal_detection_png_invalid")
    return struct.unpack(">II", value[16:24])


def _repo_path(value: Any) -> Path:
    if not isinstance(value, str):
        raise LiteralDetectionError("literal_detection_repo_path_invalid")
    path = (REPO_ROOT / value).resolve()
    try:
        path.relative_to(REPO_ROOT)
    except ValueError as exc:
        raise LiteralDetectionError("literal_detection_repo_path_escape") from exc
    return path


def _source_path(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise LiteralDetectionError("literal_detection_source_path_escape") from exc
    return path


def _json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise LiteralDetectionError("literal_detection_json_invalid") from exc
    if not isinstance(value, dict):
        raise LiteralDetectionError("literal_detection_json_not_object")
    return value


def copy_list(value: Any) -> list[float]:
    return [float(item) for item in value]


def _error_code(exc: BaseException, fallback: str) -> str:
    return str(getattr(exc, "code", None) or fallback)


if __name__ == "__main__":
    raise SystemExit(main())
