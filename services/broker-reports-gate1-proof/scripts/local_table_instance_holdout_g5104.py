#!/usr/bin/env python3
"""Run the frozen G5.104 cross-report table-instance holdout once."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

import pypdf

from broker_reports_gate1.gemini_normalized_table_boxes import (
    GEMINI_NORMALIZED_TABLE_BOX_RESPONSE_SCHEMA,
    GeminiNormalizedTableBoxError,
    GeminiNormalizedTableBoxProjectionFactory,
)
from scripts.local_minimal_native_pdfplumber_plan_g5100 import (
    REPO_ROOT,
    _provider,
    _read_object,
    _sha256,
    _sha256_json,
    _write_json,
)
from scripts.local_table_instance_separation_g5103 import PROMPT


SCRIPT_PATH = Path(__file__).resolve()
SERVICE_ROOT = SCRIPT_PATH.parent.parent
G5103_SCRIPT_PATH = SCRIPT_PATH.with_name(
    "local_table_instance_separation_g5103.py"
)
PROJECTION_OWNER_PATH = (
    SERVICE_ROOT / "broker_reports_gate1" / "gemini_normalized_table_boxes.py"
)
DEFAULT_MANIFEST = (
    SERVICE_ROOT
    / "benchmarks"
    / "table_instance_separation_holdout_g5104"
    / "manifest.json"
)
DEFAULT_SOURCE_ROOT = (
    REPO_ROOT
    / "local"
    / "stage2"
    / "broker_reports_pdf_structural_holdout_public_v5_2026-07-15"
    / "corpus"
)
DEFAULT_PRIVATE_BASE = (
    REPO_ROOT
    / "local"
    / "stage2"
    / "broker_reports_table_instance_holdout_g5104_2026-08-19"
    / "private"
)
DEFAULT_FREEZE_RENDERS = (
    DEFAULT_PRIVATE_BASE / "freeze_renders" / "freeze_renders.private.json"
)
DEFAULT_VISUAL_TRUTH = DEFAULT_PRIVATE_BASE / "visual_truth.private.json"
DEFAULT_PRIVATE_OUTPUT = DEFAULT_PRIVATE_BASE / "holdout.execution.private.json"
DEFAULT_SAFE_OUTPUT = (
    REPO_ROOT
    / "docs"
    / "reports"
    / "2026-08-19"
    / "BROKER_REPORTS_G5104_TABLE_INSTANCE_HOLDOUT_EXECUTION.safe.json"
)
FACTORY_REQUIRED = (
    "PdfTableRasterFactory.create frozen render -> "
    "PdfGridExperimentProviderFactory.create_for_openwebui -> "
    "GeminiNormalizedTableBoxProjectionFactory.create"
)
FORBIDDEN = (
    "No prompt/schema/model change, broker/domain hint, rerender after model "
    "output, retry, best-of-N, table extraction, column geometry, Canonical, "
    "or product routing"
)


class G5104Error(RuntimeError):
    pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--source-root", default=str(DEFAULT_SOURCE_ROOT))
    parser.add_argument("--freeze-renders", default=str(DEFAULT_FREEZE_RENDERS))
    parser.add_argument("--visual-truth", default=str(DEFAULT_VISUAL_TRUTH))
    parser.add_argument("--env-file", default=str(REPO_ROOT / ".env"))
    parser.add_argument("--private-output", default=str(DEFAULT_PRIVATE_OUTPUT))
    parser.add_argument("--safe-output", default=str(DEFAULT_SAFE_OUTPUT))
    args = parser.parse_args(argv)
    result = run_holdout(
        manifest_path=Path(args.manifest),
        source_root=Path(args.source_root),
        freeze_renders_path=Path(args.freeze_renders),
        visual_truth_path=Path(args.visual_truth),
        env_path=Path(args.env_file),
        private_output=Path(args.private_output),
        safe_output=Path(args.safe_output),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def run_holdout(
    *,
    manifest_path: Path,
    source_root: Path,
    freeze_renders_path: Path,
    visual_truth_path: Path,
    env_path: Path,
    private_output: Path,
    safe_output: Path,
) -> dict[str, Any]:
    if private_output.exists() or safe_output.exists():
        raise G5104Error("g5104_outputs_already_exist")
    manifest = _read_object(manifest_path)
    freeze_renders = _read_object(freeze_renders_path)
    visual_truth = _read_object(visual_truth_path)
    _validate_freeze(
        manifest=manifest,
        source_root=source_root,
        freeze_renders=freeze_renders,
        freeze_renders_path=freeze_renders_path,
        visual_truth=visual_truth,
        visual_truth_path=visual_truth_path,
    )

    projection = GeminiNormalizedTableBoxProjectionFactory().create()
    provider = _provider(env_path)
    qualification = provider.qualify()
    if qualification.get("status") != "qualified":
        raise G5104Error("g5104_provider_not_qualified")

    truth_by_case = {
        str(item["case_id"]): item for item in visual_truth["cases"]
    }
    render_by_case = {
        str(item["case_id"]): item for item in freeze_renders["records"]
    }
    results = []
    for case in manifest["cases"]:
        case_id = str(case["case_id"])
        frozen_render = render_by_case[case_id]
        page_png = Path(str(frozen_render["private_image_path"])).read_bytes()
        if _sha256(page_png) != case["page_png_sha256"]:
            raise G5104Error("g5104_frozen_page_png_drift")

        outcome = provider.invoke(
            task_id=case_id,
            model_view={"task": PROMPT},
            output_schema=copy.deepcopy(
                GEMINI_NORMALIZED_TABLE_BOX_RESPONSE_SCHEMA
            ),
            png_bytes=page_png,
            crop_sha256=case["page_png_sha256"],
            attempt_number=1,
            attempt_lineage=[],
        )
        provider_value = outcome.get("json_output")
        projected = None
        projection_error = None
        try:
            projected = projection.project(
                provider_value=provider_value,
                raster_manifest=frozen_render["raster_manifest"],
                expected_page_bbox=list(frozen_render["page_bbox"]),
            )
        except GeminiNormalizedTableBoxError as exc:
            projection_error = exc.code
        results.append(
            {
                "case_id": case_id,
                "document_id": case["document_id"],
                "page": case["page"],
                "expected_visual_tables": truth_by_case[case_id][
                    "expected_visual_tables"
                ],
                "page_png_sha256": case["page_png_sha256"],
                "provider_value": provider_value,
                "projection": projected,
                "projection_error": projection_error,
                "attempt": outcome.get("attempt"),
                "response_hash": outcome.get("response_hash"),
                "raw_private_response": outcome.get("raw_private_response"),
            }
        )

    metrics = _metrics(results)
    terminals = _terminals(metrics)
    private = {
        "schema_version": (
            "broker_reports_table_instance_holdout_g5104_execution_private_v1"
        ),
        "goal": "G5.104",
        "phase": "cross_report_holdout",
        "manifest_sha256": _sha256(manifest_path.read_bytes()),
        "freeze_renders_file_sha256": _sha256(freeze_renders_path.read_bytes()),
        "visual_truth_file_sha256": _sha256(visual_truth_path.read_bytes()),
        "prompt_sha256": _sha256_json(PROMPT),
        "response_schema_sha256": _sha256_json(
            GEMINI_NORMALIZED_TABLE_BOX_RESPONSE_SCHEMA
        ),
        "implementation_sha256": _sha256(SCRIPT_PATH.read_bytes()),
        "provider_policy": manifest["frozen_contract"],
        "qualification": qualification,
        "results": results,
        "metrics": metrics,
        "terminals": terminals,
        "visual_adjudication_status": "pending_after_machine_execution",
    }
    private_output.parent.mkdir(parents=True, exist_ok=True)
    _write_json(private_output, private)
    safe = {
        "schema_version": (
            "broker_reports_table_instance_holdout_g5104_execution_safe_v1"
        ),
        "goal": "G5.104",
        "phase": "cross_report_holdout",
        "corpus_role": manifest["corpus_role"],
        "global_unseen_claim": manifest["global_unseen_claim"],
        "provider_calls": len(results),
        "metrics": metrics,
        "terminals": terminals,
        "visual_adjudication_status": "pending_after_machine_execution",
        "prompt_or_schema_changed_from_g5103": False,
        "private_canonical_json_sha256": _sha256_json(private),
        "privacy": {
            "customer_bytes_in_git": False,
            "raw_provider_response_in_git": False,
            "source_literals_in_git": False,
            "normalized_coordinates_in_safe_report": False,
            "pdf_coordinates_in_safe_report": False,
        },
    }
    _write_json(safe_output, safe)
    return {"status": "complete", "metrics": metrics, "terminals": terminals}


def _validate_freeze(
    *,
    manifest: dict[str, Any],
    source_root: Path,
    freeze_renders: dict[str, Any],
    freeze_renders_path: Path,
    visual_truth: dict[str, Any],
    visual_truth_path: Path,
) -> None:
    if (
        manifest.get("schema_version")
        != "broker_reports_table_instance_separation_holdout_g5104_manifest_v1"
        or manifest.get("status") != "frozen_before_provider"
        or manifest.get("global_unseen_claim") is not False
    ):
        raise G5104Error("g5104_manifest_invalid")
    contract = manifest.get("frozen_contract") or {}
    if (
        contract.get("prompt_sha256") != _sha256_json(PROMPT)
        or contract.get("response_schema_sha256")
        != _sha256_json(GEMINI_NORMALIZED_TABLE_BOX_RESPONSE_SCHEMA)
        or contract.get("g5103_harness_sha256")
        != _sha256(G5103_SCRIPT_PATH.read_bytes())
        or contract.get("g5102_projection_owner_sha256")
        != _sha256(PROJECTION_OWNER_PATH.read_bytes())
        or contract.get("model") != "models/gemini-3.5-flash"
        or contract.get("thinking_level") != "minimal"
        or contract.get("attempts_per_page") != 1
        or contract.get("retry") is not False
        or contract.get("best_of_n") is not False
        or contract.get("prompt_repair") is not False
        or contract.get("broker_or_domain_hint") is not False
    ):
        raise G5104Error("g5104_frozen_contract_drift")
    private_hashes = manifest.get("private_evidence_hashes") or {}
    if (
        private_hashes.get("freeze_renders_file_sha256")
        != _sha256(freeze_renders_path.read_bytes())
        or private_hashes.get("visual_truth_file_sha256")
        != _sha256(visual_truth_path.read_bytes())
    ):
        raise G5104Error("g5104_private_freeze_hash_drift")
    cases = list(manifest.get("cases") or [])
    truth_cases = list(visual_truth.get("cases") or [])
    render_cases = list(freeze_renders.get("records") or [])
    case_ids = [str(item.get("case_id")) for item in cases]
    if (
        len(cases) != 5
        or len(set(case_ids)) != len(case_ids)
        or case_ids != [str(item.get("case_id")) for item in truth_cases]
        or case_ids != [str(item.get("case_id")) for item in render_cases]
        or sum(int(item["expected_visual_tables"]) for item in truth_cases) != 3
    ):
        raise G5104Error("g5104_case_freeze_invalid")
    _validate_source_documents(manifest=manifest, source_root=source_root)
    for case, frozen_render in zip(cases, render_cases, strict=True):
        if (
            case["document_id"] != frozen_render["document_id"]
            or case["page"] != frozen_render["page"]
            or case["page_png_sha256"] != frozen_render["page_png_sha256"]
            or frozen_render["document_sha256"]
            != next(
                item["source_sha256"]
                for item in manifest["documents"]
                if item["document_id"] == case["document_id"]
            )
        ):
            raise G5104Error("g5104_render_freeze_invalid")


def _validate_source_documents(
    *,
    manifest: dict[str, Any],
    source_root: Path,
) -> None:
    expected = {
        str(item["source_sha256"]): int(item["page_count"])
        for item in manifest["documents"]
    }
    resolved: dict[str, Path] = {}
    for path in source_root.glob("*.pdf"):
        digest = _sha256(path.read_bytes())
        if digest in expected:
            if digest in resolved:
                raise G5104Error("g5104_duplicate_source_hash")
            resolved[digest] = path
    if set(resolved) != set(expected):
        raise G5104Error("g5104_source_set_invalid")
    for digest, path in resolved.items():
        if len(pypdf.PdfReader(path).pages) != expected[digest]:
            raise G5104Error("g5104_source_page_count_drift")


def _proposal_count(value: Any) -> int:
    if not isinstance(value, dict):
        return 0
    tables = value.get("tables")
    return len(tables) if isinstance(tables, list) else 0


def _metrics(results: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "documents": len({item["document_id"] for item in results}),
        "pages": len(results),
        "positive_pages": sum(item["expected_visual_tables"] > 0 for item in results),
        "negative_pages": sum(item["expected_visual_tables"] == 0 for item in results),
        "expected_visual_tables": sum(item["expected_visual_tables"] for item in results),
        "proposed_tables": sum(_proposal_count(item["provider_value"]) for item in results),
        "projected_boxes": sum(
            len((item.get("projection") or {}).get("tables") or [])
            for item in results
        ),
        "pages_with_exact_table_count": sum(
            _proposal_count(item["provider_value"]) == item["expected_visual_tables"]
            for item in results
        ),
        "false_boxes_on_negative_pages": sum(
            _proposal_count(item["provider_value"])
            for item in results
            if item["expected_visual_tables"] == 0
        ),
        "invalid_responses": sum(item.get("projection_error") is not None for item in results),
        "provider_non_success_terminals": sum(
            (item.get("attempt") or {}).get("finish_reason") != "STOP"
            or (item.get("attempt") or {}).get("terminal_failure_class") is not None
            for item in results
        ),
        "vlm_body_values_used": 0,
        "invented_source_literals": 0,
    }


def _terminals(metrics: dict[str, int]) -> list[str]:
    if metrics["provider_non_success_terminals"] or metrics["invalid_responses"]:
        return ["TABLE_INSTANCE_HOLDOUT_CONTRACT_FAILED"]
    if (
        metrics["pages_with_exact_table_count"] != metrics["pages"]
        or metrics["false_boxes_on_negative_pages"] != 0
    ):
        return ["TABLE_INSTANCE_HOLDOUT_COUNT_FAILED"]
    return ["TABLE_INSTANCE_HOLDOUT_MACHINE_COUNTS_PASSED_VISUAL_REVIEW_REQUIRED"]


if __name__ == "__main__":
    raise SystemExit(main())
