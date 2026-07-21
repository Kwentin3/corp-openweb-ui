from __future__ import annotations

import argparse
import copy
import hashlib
import importlib
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any


SCRIPT_ROOT = Path(__file__).resolve().parent
SERVICE_ROOT = SCRIPT_ROOT.parent
sys.path.insert(0, str(SERVICE_ROOT))

from broker_reports_gate1.pdf_dual_vlm_runtime import (  # noqa: E402
    PDF_DUAL_VLM_RUNTIME_POLICY_VERSION,
    PDF_DUAL_VLM_VALIDATOR_VERSION,
    PdfDualVlmRuntimeConfig,
    PdfDualVlmRuntimeFactory,
)
from broker_reports_gate1.pdf_hybrid_contracts import (  # noqa: E402
    canonical_json_bytes,
    sha256_json,
)
from broker_reports_gate1.pdf_table_raster import (  # noqa: E402
    PdfTableRasterConfig,
    PdfTableRasterFactory,
)


QUALIFICATION_SCHEMA = "broker_reports_pdf_dual_vlm_model_qualification_v1_safe"
SYNTHETIC_SOURCE_SHA256 = hashlib.sha256(
    b"broker-reports-dual-vlm-live-qualification-v1"
).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--openwebui-config-module",
        default="open_webui.config",
    )
    parser.add_argument("--gemini-model", default="models/gemini-3.5-flash")
    parser.add_argument("--openai-model", default="gpt-5.4-mini-2026-03-17")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    result = qualify(
        config_module=args.openwebui_config_module,
        gemini_model=args.gemini_model,
        openai_model=args.openai_model,
    )
    payload = canonical_json_bytes(result) + b"\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(payload)
    print(payload.decode("utf-8"), end="")
    return 0 if result["status"] == "requalified" else 1


def qualify(
    *,
    config_module: str,
    gemini_model: str,
    openai_model: str,
) -> dict[str, Any]:
    openwebui_config = importlib.import_module(config_module)
    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(config=openwebui_config),
        )
    )
    candidate = _synthetic_candidate()
    runtime = PdfDualVlmRuntimeFactory(
        PdfDualVlmRuntimeConfig(
            enabled=True,
            gemini_model_id=gemini_model,
            openai_model_id=openai_model,
            maximum_candidates=1,
        )
    ).create_for_openwebui(request)
    outcome = runtime.run([candidate])
    decision = outcome.private_decisions[0] if outcome.private_decisions else {}
    executions = {
        str(item.get("provider")): _safe_execution(item)
        for item in decision.get("executions") or []
        if isinstance(item, dict)
    }
    qualifications = outcome.safe_summary.get("provider_qualifications") or {}
    checks = {
        "synthetic_bounded_crop": _bounded_crop_checks(candidate),
        "gemini_exact_model": _qualification_passed(
            qualifications.get("gemini"), gemini_model
        ),
        "openai_exact_model": _qualification_passed(
            qualifications.get("openai"), openai_model
        ),
        "gemini_live_image_structured_output": _execution_passed(
            executions.get("gemini")
        ),
        "openai_live_image_structured_output": _execution_passed(
            executions.get("openai")
        ),
        "same_crop_for_both_providers": (
            len(
                {
                    item.get("input_hash")
                    for item in executions.values()
                    if isinstance(item, dict)
                }
            )
            == 1
            and len(executions) == 2
        ),
        "provider_agreement_not_canonical": (
            decision.get("canonical_table") is None
            and decision.get("provider_proposal_canonical_authority") is False
            and decision.get("status") == "proposal_requires_review"
        ),
        "hidden_retry_absent": all(
            item.get("hidden_retry") is False for item in executions.values()
        ),
        "provider_failover_absent": all(
            item.get("provider_failover") is False for item in executions.values()
        ),
        "whole_document_upload_absent": all(
            item.get("whole_document_uploaded") is False for item in executions.values()
        ),
    }
    passed = bool(checks) and all(checks.values())
    implementation_hashes = _implementation_hashes()
    receipt = {
        "schema_version": QUALIFICATION_SCHEMA,
        "status": "requalified" if passed else "blocked",
        "qualified_at": datetime.now(timezone.utc).isoformat(),
        "synthetic_only": True,
        "customer_data_used": False,
        "runtime_policy_version": PDF_DUAL_VLM_RUNTIME_POLICY_VERSION,
        "validator_version": PDF_DUAL_VLM_VALIDATOR_VERSION,
        "implementation_source_hashes": implementation_hashes,
        "configured_models": {
            "gemini": gemini_model,
            "openai": openai_model,
        },
        "checks": checks,
        "provider_qualifications": copy.deepcopy(qualifications),
        "executions": executions,
        "decision": {
            "status": decision.get("status"),
            "reason_codes": copy.deepcopy(decision.get("reason_codes") or []),
            "decision_hash": decision.get("decision_hash"),
            "canonical_table_published": decision.get("canonical_table") is not None,
            "provider_proposal_canonical_authority": decision.get(
                "provider_proposal_canonical_authority"
            ),
        },
        "raw_provider_responses_retained": False,
        "provider_output_values_retained": False,
    }
    receipt["qualification_hash"] = sha256_json(receipt)
    return receipt


def _synthetic_candidate() -> dict[str, Any]:
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("pdf_dual_vlm_qualification_renderer_unavailable") from exc

    document = fitz.open()
    page = document.new_page(width=360, height=240)
    table_bbox = fitz.Rect(45, 50, 315, 190)
    for x in (45, 180, 315):
        page.draw_line((x, 50), (x, 190), color=(0, 0, 0), width=1)
    for y in (50, 120, 190):
        page.draw_line((45, y), (315, y), color=(0, 0, 0), width=1)
    page.insert_text((70, 90), "Qualification", fontsize=14)
    page.insert_text((220, 90), "Status", fontsize=14)
    page.insert_text((70, 160), "Synthetic", fontsize=14)
    page.insert_text((220, 160), "OK", fontsize=14)
    pdf_bytes = document.tobytes(garbage=4, deflate=True)
    document.close()
    pdf_sha256 = hashlib.sha256(pdf_bytes).hexdigest()
    renderer = PdfTableRasterFactory(
        PdfTableRasterConfig(
            horizontal_padding_fraction=0.08,
            vertical_padding_fraction=0.08,
        )
    ).create()
    return renderer.render_detected_region(
        pdf_bytes=pdf_bytes,
        pdf_sha256=pdf_sha256,
        document_ref="synthetic_qualification_document",
        page_number=1,
        candidate_ref="synthetic_qualification_table",
        detected_bbox_normalized=[
            round(table_bbox.x0 / 360, 9),
            round(table_bbox.y0 / 240, 9),
            round(table_bbox.x1 / 360, 9),
            round(table_bbox.y1 / 240, 9),
        ],
        detector_contract_version="synthetic_qualification_detector_v1",
        detector_identity={
            "provider_profile": "synthetic_no_provider",
            "response_hash": SYNTHETIC_SOURCE_SHA256,
        },
        dpi=150,
    )


def _safe_execution(value: dict[str, Any]) -> dict[str, Any]:
    return {
        key: copy.deepcopy(value.get(key))
        for key in (
            "schema_version",
            "policy_version",
            "provider",
            "provider_profile",
            "provider_profile_revision",
            "requested_model_id",
            "resolved_model_id",
            "prompt_id",
            "prompt_version",
            "prompt_hash",
            "model_view_hash",
            "output_schema_version",
            "canonical_schema_hash",
            "provider_adapted_schema_hash",
            "schema_transform_count",
            "maximum_output_tokens",
            "maximum_counted_input_tokens",
            "transport_timeout_seconds",
            "deadline_policy",
            "attempt_number",
            "attempt_lineage",
            "preflight",
            "usage",
            "latency_ms",
            "terminal_provider_status",
            "finish_reason",
            "response_hash",
            "validator_result",
            "hidden_retry",
            "provider_failover",
            "provider_switch",
            "whole_document_uploaded",
            "execution_hash",
            "input_hash",
        )
    }


def _qualification_passed(value: Any, model_id: str) -> bool:
    return (
        isinstance(value, dict)
        and value.get("status") == "qualified"
        and value.get("requested_model_id") == model_id
        and value.get("resolved_model_id") == model_id
        and value.get("exact_model_match") is True
        and value.get("image_input_supported") is True
        and value.get("structured_output_supported") is True
        and value.get("native_provider_transport") is True
        and value.get("credentials_from_openwebui_connection") is True
    )


def _execution_passed(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and value.get("terminal_provider_status") == "completed"
        and value.get("requested_model_id") == value.get("resolved_model_id")
        and len(str(value.get("canonical_schema_hash") or "")) == 64
        and len(str(value.get("provider_adapted_schema_hash") or "")) == 64
        and isinstance(value.get("preflight"), dict)
        and value["preflight"].get("within_hard_guard") is True
        and isinstance(value.get("validator_result"), dict)
        and value["validator_result"].get("status") == "passed"
    )


def _bounded_crop_checks(candidate: dict[str, Any]) -> bool:
    manifest = candidate.get("manifest")
    return (
        set(candidate) == {"manifest", "private_png_base64"}
        and isinstance(manifest, dict)
        and manifest.get("schema_version") == "broker_reports_pdf_table_candidate_v1"
        and manifest.get("page_number") == 1
        and manifest.get("dpi") == 150
        and manifest.get("lossless") is True
        and manifest.get("silent_resize_performed") is False
        and "pdf_bytes" not in candidate
    )


def _implementation_hashes() -> dict[str, str]:
    modules = (
        "broker_reports_gate1.gate2_provider_adapters",
        "broker_reports_gate1.pdf_grid_experiment_provider",
        "broker_reports_gate1.pdf_dual_vlm_fact_providers",
        "broker_reports_gate1.pdf_dual_vlm_canonical_table_contracts",
        "broker_reports_gate1.pdf_dual_vlm_runtime",
    )
    result = {}
    for module_name in modules:
        module = importlib.import_module(module_name)
        source_path = Path(str(module.__file__ or ""))
        if not source_path.is_file():
            raise RuntimeError("pdf_dual_vlm_qualification_source_unavailable")
        result[module_name] = hashlib.sha256(source_path.read_bytes()).hexdigest()
    result["qualification_tool"] = hashlib.sha256(
        Path(__file__).read_bytes()
    ).hexdigest()
    return result


if __name__ == "__main__":
    raise SystemExit(main())
