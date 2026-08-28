#!/usr/bin/env python3
"""Compare frozen Canonical-only role mapping with one source-image mapping."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
SERVICE_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SERVICE_ROOT.parents[1]
sys.path[:0] = [str(SCRIPT_DIR), str(SERVICE_ROOT)]

from broker_reports_gate1.pdf_table_locator_provider import (  # noqa: E402
    PdfGridExperimentProviderFactory,
    PdfGridProviderConfig,
)
from broker_reports_gate1.pdf_table_raster import (  # noqa: E402
    PdfTableRasterConfig,
    PdfTableRasterFactory,
)
from broker_reports_gate1.pdf_text_layer import (  # noqa: E402
    PdfParserCapabilityRequest,
    PdfTextLayerParserFactory,
)
from broker_reports_gate1.visual_role_context_research import (  # noqa: E402
    VisualRoleContextResearchFactory,
    compose_visual_role_model_view,
)
from canonical_financial_role_mapping_research import (  # noqa: E402
    apply_contract,
    stable_sha256,
    validate_response,
)
from local_pdf_vlm_guided_intake_development import (  # noqa: E402
    _openwebui_request,
)


FREEZE_SCHEMA = "broker_reports_visual_financial_role_ab_freeze_rd_v1"
RESULT_SCHEMA = "broker_reports_visual_financial_role_ab_result_safe_rd_v1"
MODEL_ID = "models/gemini-3.5-flash"
PROVIDER_PROFILE = "google_gemini"


class LiveVisualRoleAbError(RuntimeError):
    pass


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--prior-role-root", type=Path, required=True)
    prepare.add_argument("--normalization-result", type=Path, required=True)
    prepare.add_argument("--pdf", type=Path, required=True)
    prepare.add_argument("--private-output-root", type=Path, required=True)
    execute = subparsers.add_parser("execute")
    execute.add_argument("--freeze", type=Path, required=True)
    execute.add_argument("--env-file", type=Path, required=True)
    execute.add_argument("--private-output-root", type=Path, required=True)
    args = parser.parse_args()
    return _prepare(args) if args.command == "prepare" else _execute(args)


def _prepare(args: argparse.Namespace) -> int:
    _require_clean_head()
    output_root = args.private_output_root.resolve()
    _require_new_external_root(output_root)
    prior_root = args.prior_role_root.resolve()
    prior_freeze = _read_object(prior_root / "freeze.private.json")
    cases = _read_object(prior_root / "cases.private.json")
    case = cases.get("dev_tbank_t01")
    if not isinstance(case, dict):
        raise LiveVisualRoleAbError("visual_role_ab_prior_case_missing")
    role_module = SCRIPT_DIR / "canonical_financial_role_mapping_research.py"
    if prior_freeze.get("module_sha256") != _file_sha256(role_module):
        raise LiveVisualRoleAbError("visual_role_ab_mapper_drift")
    baseline_path = prior_root / (
        "development-dev_tbank_t01-header_plus_profiles.private.json"
    )
    baseline = _read_object(baseline_path)
    if baseline.get("status") != "VALIDATED_AND_APPLIED":
        raise LiveVisualRoleAbError("visual_role_ab_baseline_invalid")
    pdf_path = args.pdf.resolve()
    pdf_bytes = pdf_path.read_bytes()
    pdf_sha256 = hashlib.sha256(pdf_bytes).hexdigest()
    if case.get("manifest", {}).get("source_sha256") != pdf_sha256:
        raise LiveVisualRoleAbError("visual_role_ab_source_drift")
    normalization = _read_object(args.normalization_result.resolve())
    locator_pages = normalization.get("locator", {}).get("private_page_results")
    if not isinstance(locator_pages, list):
        raise LiveVisualRoleAbError("visual_role_ab_locator_evidence_missing")
    parsed = PdfTextLayerParserFactory().create(
        PdfParserCapabilityRequest(capability="table_candidates")
    ).parse(pdf_bytes, table_locator_pages=locator_pages)
    candidates = [
        (page, candidate)
        for page in parsed.pages
        for candidate in page.get("table_candidate_inventory", [])
    ]
    if not candidates:
        raise LiveVisualRoleAbError("visual_role_ab_candidate_missing")
    parser_page, candidate = candidates[0]
    table = case.get("table")
    if (
        not isinstance(table, dict)
        or len(table.get("columns", [])) != candidate.get("columns_total")
        or len(table.get("rows", [])) != candidate.get("rows_total")
    ):
        raise LiveVisualRoleAbError("visual_role_ab_candidate_canonical_mismatch")
    baseline_request = case.get("requests", {}).get("header_plus_profiles")
    if not isinstance(baseline_request, dict):
        raise LiveVisualRoleAbError("visual_role_ab_request_missing")
    geometry = VisualRoleContextResearchFactory().create().build_column_geometry(
        table_candidate=candidate,
        expected_column_refs=[f"c{item}" for item in table["columns"]],
    )
    model_view = compose_visual_role_model_view(
        baseline_request=baseline_request,
        column_geometry=geometry,
    )
    raster = PdfTableRasterFactory(
        PdfTableRasterConfig(padding_points=0)
    ).create()
    rendered = raster.render(
        pdf_bytes=pdf_bytes,
        pdf_sha256=pdf_sha256,
        document_ref="visual_role_ab_document",
        page_number=parser_page["page_number"],
        table_ref="table_1",
        table_bbox=candidate["bbox"],
        dpi=300,
        escalation_reason="research_visual_financial_role_ab",
    )
    png_bytes = base64.b64decode(rendered["private_png_base64"])
    output_root.mkdir(parents=True)
    png_path = output_root / "table_1.png"
    png_path.write_bytes(png_bytes)
    freeze = {
        "schema_version": FREEZE_SCHEMA,
        "source_head": _git_head(),
        "source_worktree_clean": True,
        "model_id": MODEL_ID,
        "provider_profile": PROVIDER_PROFILE,
        "source_sha256": pdf_sha256,
        "canonical_root_sha256": case["manifest"]["canonical_root_sha256"],
        "table_sha256": stable_sha256(table),
        "table": table,
        "baseline_request_sha256": stable_sha256(baseline_request),
        "baseline_contract": baseline["contract"],
        "baseline_application": baseline["application"],
        "baseline_evidence_sha256": _file_sha256(baseline_path),
        "visual_model_view": model_view,
        "response_schema": baseline_request["response_format"]["json_schema"]["schema"],
        "png_path": str(png_path),
        "png_sha256": hashlib.sha256(png_bytes).hexdigest(),
        "column_geometry": geometry,
        "rows": len(table["rows"]),
        "columns": len(table["columns"]),
        "scheduled_new_model_calls": 1,
        "baseline_model_calls_reused": 1,
        "retry": False,
        "repair": False,
        "best_of_n": False,
        "manual_output_edit": False,
        "canonical_mutated": False,
        "product_activation": False,
    }
    freeze["freeze_sha256"] = stable_sha256(freeze)
    freeze_path = output_root / "freeze.private.json"
    _write_new_json(freeze_path, freeze)
    print(json.dumps({
        "freeze_path": str(freeze_path),
        "freeze_sha256": freeze["freeze_sha256"],
        "source_head": freeze["source_head"],
        "rows": freeze["rows"],
        "columns": freeze["columns"],
        "scheduled_new_model_calls": 1,
    }, ensure_ascii=False, indent=2))
    return 0


def _execute(args: argparse.Namespace) -> int:
    freeze = _read_object(args.freeze.resolve())
    if (
        freeze.get("schema_version") != FREEZE_SCHEMA
        or freeze.get("source_head") != _git_head()
        or stable_sha256({k: v for k, v in freeze.items() if k != "freeze_sha256"})
        != freeze.get("freeze_sha256")
    ):
        raise LiveVisualRoleAbError("visual_role_ab_freeze_invalid_or_drifted")
    output_root = args.private_output_root.resolve()
    _require_new_external_root(output_root)
    png_bytes = Path(freeze["png_path"]).read_bytes()
    if hashlib.sha256(png_bytes).hexdigest() != freeze["png_sha256"]:
        raise LiveVisualRoleAbError("visual_role_ab_png_drift")
    provider = PdfGridExperimentProviderFactory(
        PdfGridProviderConfig(
            provider_profile=PROVIDER_PROFILE,
            model_id=MODEL_ID,
            timeout_seconds=300,
            maximum_output_tokens=8192,
            maximum_counted_input_tokens=24_000,
            thinking_level="minimal",
        )
    ).create_for_openwebui(_openwebui_request(args.env_file.resolve()))
    qualification = provider.qualify()
    if qualification.get("status") != "qualified":
        raise LiveVisualRoleAbError("visual_role_ab_provider_not_qualified")
    response = provider.invoke(
        task_id="visual_financial_role_ab_table_1",
        model_view=freeze["visual_model_view"],
        output_schema=freeze["response_schema"],
        png_bytes=png_bytes,
        crop_sha256=freeze["png_sha256"],
        attempt_number=1,
        attempt_lineage=[],
    )
    error = None
    visual_contract = None
    visual_application = None
    try:
        visual_contract = validate_response(
            raw_response=response.get("json_output"),
            table=freeze["table"],
            table_ref="table_1",
        )
        visual_application = apply_contract(
            table=freeze["table"], contract=visual_contract
        )
    except RuntimeError as exc:
        error = str(exc)
    baseline = _summary(
        contract=freeze["baseline_contract"],
        application=freeze["baseline_application"],
    )
    visual = _summary(contract=visual_contract, application=visual_application)
    safe = {
        "schema_version": RESULT_SCHEMA,
        "freeze_sha256": freeze["freeze_sha256"],
        "source_head": freeze["source_head"],
        "source_sha256": freeze["source_sha256"],
        "canonical_root_sha256": freeze["canonical_root_sha256"],
        "table_sha256": freeze["table_sha256"],
        "table_shape": {"rows": freeze["rows"], "columns": freeze["columns"]},
        "baseline": baseline,
        "visual": visual,
        "visual_validation_error": error,
        "provider_submission": 1,
        "baseline_model_calls_reused": 1,
        "retry": False,
        "repair": False,
        "best_of_n": False,
        "manual_output_edit": False,
        "source_literals_unchanged": (
            visual_application or {}
        ).get("source_literals_unchanged"),
        "canonical_mutated": False,
        "facts_published": 0,
        "private_values_committed": False,
        "product_activation": False,
    }
    safe["receipt_sha256"] = stable_sha256(safe)
    private = {
        **safe,
        "qualification": qualification,
        "provider_attempt": response.get("attempt"),
        "visual_contract": visual_contract,
        "visual_application": visual_application,
        "raw_private_response": response.get("raw_private_response"),
    }
    output_root.mkdir(parents=True)
    _write_new_json(output_root / "result.private.json", private)
    _write_new_json(output_root / "result.safe.json", safe)
    print(json.dumps(safe, ensure_ascii=False, indent=2))
    return 0 if visual_contract is not None else 2


def _summary(*, contract: Any, application: Any) -> dict[str, Any] | None:
    if not isinstance(contract, dict) or not isinstance(application, dict):
        return None
    roles = {item["column_ref"]: item["role"] for item in contract["columns"]}
    bindings = {
        item["amount_column_ref"]: item["currency_column_ref"]
        for item in contract["amount_currency_bindings"]
    }
    return {
        "table_kind": contract["table_kind"],
        "header_row": contract["header_row"],
        "terminal": application["terminal"],
        "observations": len(application["observations"]),
        "relevant_unmapped": application["relevant_unmapped"],
        "key_roles": {
            column: roles.get(column)
            for column in ("c3", "c7", "c8", "c13", "c15", "c18", "c20", "c22")
        },
        "amount_currency_bindings": {
            column: bindings.get(column) for column in ("c18", "c20", "c22")
        },
    }


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise LiveVisualRoleAbError("visual_role_ab_json_object_required")
    return value


def _write_new_json(path: Path, value: Any) -> None:
    if path.exists():
        raise LiveVisualRoleAbError("visual_role_ab_output_exists")
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_head() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True
    ).strip()


def _require_clean_head() -> None:
    status = subprocess.check_output(
        ["git", "status", "--porcelain"], cwd=REPO_ROOT, text=True
    )
    if status.strip():
        raise LiveVisualRoleAbError("visual_role_ab_worktree_not_clean")


def _require_new_external_root(path: Path) -> None:
    try:
        path.relative_to(REPO_ROOT.resolve())
    except ValueError:
        pass
    else:
        raise LiveVisualRoleAbError("visual_role_ab_output_inside_repository")
    if path.exists():
        raise LiveVisualRoleAbError("visual_role_ab_output_exists")


if __name__ == "__main__":
    raise SystemExit(main())
