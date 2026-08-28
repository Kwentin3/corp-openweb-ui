#!/usr/bin/env python3
"""Freeze and execute the research-only visual title/header structure proof."""

from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
SERVICE_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SERVICE_ROOT.parents[1]
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(SERVICE_ROOT))

from broker_reports_gate1.pdf_table_locator_provider import (  # noqa: E402
    PdfGridExperimentProviderFactory,
    PdfGridProviderConfig,
)
from broker_reports_gate1.pdf_table_raster import (  # noqa: E402
    PdfTableRasterFactory,
)
from broker_reports_gate1.pdf_text_layer import (  # noqa: E402
    PdfParserCapabilityRequest,
    PdfTextLayerParserFactory,
)
from broker_reports_gate1.visual_table_structure_research import (  # noqa: E402
    VisualTableStructureError,
    VisualTableStructureProjectionFactory,
    model_view,
    response_schema,
)
from local_pdf_vlm_guided_intake_development import (  # noqa: E402
    _openwebui_request,
)


FREEZE_SCHEMA = "broker_reports_visual_table_structure_freeze_rd_v1"
PRIVATE_RESULT_SCHEMA = "broker_reports_visual_table_structure_result_private_rd_v1"
SAFE_RESULT_SCHEMA = "broker_reports_visual_table_structure_result_safe_rd_v1"
INPUT_SCHEMA = "broker_reports_visual_table_structure_input_private_rd_v1"
MODEL_ID = "models/gemini-3.5-flash"
PROVIDER_PROFILE = "google_gemini"


class VisualTableStructureLiveError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--input", type=Path, required=True)
    prepare.add_argument("--private-output-root", type=Path, required=True)

    execute = subparsers.add_parser("execute")
    execute.add_argument("--freeze", type=Path, required=True)
    execute.add_argument("--env-file", type=Path, required=True)
    execute.add_argument("--private-output-root", type=Path, required=True)

    args = parser.parse_args()
    if args.command == "prepare":
        return _prepare(args)
    return _execute(args)


def _prepare(args: argparse.Namespace) -> int:
    _require_clean_head()
    input_value = _read_object(args.input.resolve())
    if input_value.get("schema_version") != INPUT_SCHEMA:
        raise VisualTableStructureLiveError("visual_structure_input_schema_invalid")
    cases = input_value.get("cases")
    if not isinstance(cases, list) or not cases:
        raise VisualTableStructureLiveError("visual_structure_input_cases_invalid")
    output_root = args.private_output_root.resolve()
    _require_new_external_root(output_root)
    output_root.mkdir(parents=True)

    raster = PdfTableRasterFactory().create()
    prepared_cases = []
    seen_case_refs: set[str] = set()
    parsed_by_hash: dict[str, Any] = {}
    bytes_by_hash: dict[str, bytes] = {}
    for raw_case in cases:
        case = _validated_input_case(raw_case)
        if case["case_ref"] in seen_case_refs:
            raise VisualTableStructureLiveError("visual_structure_case_duplicate")
        seen_case_refs.add(case["case_ref"])
        pdf_path = Path(case["pdf_path"]).resolve()
        pdf_bytes = pdf_path.read_bytes()
        pdf_sha256 = hashlib.sha256(pdf_bytes).hexdigest()
        if pdf_sha256 not in parsed_by_hash:
            parsed_by_hash[pdf_sha256] = PdfTextLayerParserFactory().create(
                PdfParserCapabilityRequest(capability="layout_words")
            ).parse(pdf_bytes)
            bytes_by_hash[pdf_sha256] = pdf_bytes
        parsed = parsed_by_hash[pdf_sha256]
        if (
            parsed.layout_projection_status != "complete"
            or case["page_number"] > len(parsed.pages)
        ):
            raise VisualTableStructureLiveError(
                "visual_structure_parser_page_unavailable"
            )
        parser_page = parsed.pages[case["page_number"] - 1]
        page_bbox = [0.0, 0.0, parser_page["width"], parser_page["height"]]
        rendered = raster.render_full_page(
            pdf_bytes=bytes_by_hash[pdf_sha256],
            pdf_sha256=pdf_sha256,
            document_ref="visual_structure_" + case["case_ref"],
            page_ref=f"page_{case['page_number']}",
            page_number=case["page_number"],
            expected_page_bbox=page_bbox,
            dpi=150,
        )
        png_bytes = base64.b64decode(rendered["private_png_base64"])
        png_path = output_root / f"{case['case_ref']}.png"
        png_path.write_bytes(png_bytes)
        compact_page = {
            "page_number": parser_page["page_number"],
            "width": parser_page["width"],
            "height": parser_page["height"],
            "word_inventory": [
                {
                    "parser_ordinal": item["parser_ordinal"],
                    "text": item["text"],
                    "bbox": copy.deepcopy(item["bbox"]),
                }
                for item in parser_page["word_inventory"]
            ],
        }
        prepared_cases.append(
            {
                "case_ref": case["case_ref"],
                "corpus_role": case["corpus_role"],
                "pdf_path": str(pdf_path),
                "pdf_sha256": pdf_sha256,
                "page_number": case["page_number"],
                "png_path": str(png_path),
                "png_sha256": hashlib.sha256(png_bytes).hexdigest(),
                "raster_manifest_hash": rendered["manifest"]["manifest_hash"],
                "parser_page": compact_page,
                "gold": copy.deepcopy(case["gold"]),
                "model_view": model_view(case_ref=case["case_ref"]),
            }
        )

    freeze = {
        "schema_version": FREEZE_SCHEMA,
        "source_head": _git_head(),
        "source_worktree_clean": True,
        "provider_profile": PROVIDER_PROFILE,
        "model_id": MODEL_ID,
        "response_schema": response_schema(),
        "scheduled_model_calls": len(prepared_cases),
        "retry": False,
        "repair": False,
        "best_of_n": False,
        "manual_output_edit": False,
        "product_activation": False,
        "cases": prepared_cases,
    }
    freeze["freeze_sha256"] = _sha256_json(freeze)
    freeze_path = output_root / "freeze.private.json"
    _write_new_json(freeze_path, freeze)
    print(
        json.dumps(
            {
                "freeze_path": str(freeze_path),
                "freeze_sha256": freeze["freeze_sha256"],
                "source_head": freeze["source_head"],
                "cases": len(prepared_cases),
                "scheduled_model_calls": len(prepared_cases),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def _execute(args: argparse.Namespace) -> int:
    freeze = _read_object(args.freeze.resolve())
    _validate_freeze(freeze)
    output_root = args.private_output_root.resolve()
    _require_new_external_root(output_root)
    request = _openwebui_request(args.env_file.resolve())
    provider = PdfGridExperimentProviderFactory(
        PdfGridProviderConfig(
            provider_profile=PROVIDER_PROFILE,
            model_id=MODEL_ID,
            timeout_seconds=300,
            maximum_output_tokens=8192,
            maximum_counted_input_tokens=24_000,
            thinking_level="minimal",
        )
    ).create_for_openwebui(request)
    qualification = provider.qualify()
    if qualification.get("status") != "qualified":
        raise VisualTableStructureLiveError("visual_structure_provider_not_qualified")
    projector = VisualTableStructureProjectionFactory().create()
    output_root.mkdir(parents=True)
    private_runs = []
    safe_runs = []
    for case in freeze["cases"]:
        png_path = Path(case["png_path"])
        png_bytes = png_path.read_bytes()
        if hashlib.sha256(png_bytes).hexdigest() != case["png_sha256"]:
            raise VisualTableStructureLiveError("visual_structure_png_drift")
        response = provider.invoke(
            task_id=f"visual_table_structure_{case['case_ref']}",
            model_view=case["model_view"],
            output_schema=freeze["response_schema"],
            png_bytes=png_bytes,
            crop_sha256=case["png_sha256"],
            attempt_number=1,
            attempt_lineage=[],
        )
        bound = None
        terminal = "PROVIDER_OR_SCHEMA_FAILED"
        error = None
        provider_value = response.get("json_output")
        try:
            bound = projector.bind(
                provider_value=provider_value,
                parser_page=case["parser_page"],
            )
            terminal = "SOURCE_BOUND"
        except VisualTableStructureError as exc:
            error = exc.code
        evaluation = _evaluate(bound=bound, gold=case["gold"])
        if bound is not None and evaluation["all_expected_matched"]:
            terminal = "GOLD_MATCHED"
        private_runs.append(
            {
                "case_ref": case["case_ref"],
                "corpus_role": case["corpus_role"],
                "png_sha256": case["png_sha256"],
                "response_hash": response.get("response_hash"),
                "attempt": response.get("attempt"),
                "provider_value": provider_value,
                "bound": bound,
                "evaluation": evaluation,
                "validation_error": error,
                "raw_private_response": response.get("raw_private_response"),
            }
        )
        safe_runs.append(
            {
                "case_ref": case["case_ref"],
                "corpus_role": case["corpus_role"],
                "terminal": terminal,
                "expected_tables": evaluation["expected_tables"],
                "proposed_tables": evaluation["proposed_tables"],
                "source_bound_tables": evaluation["source_bound_tables"],
                "titles_matched": evaluation["titles_matched"],
                "headers_matched": evaluation["headers_matched"],
                "body_statuses_matched": evaluation["body_statuses_matched"],
                "all_expected_matched": evaluation["all_expected_matched"],
                "provider_submission": 1,
                "retry": False,
                "model_literals_used_as_source_values": False,
            }
        )

    aggregate = {
        "cases": len(safe_runs),
        "provider_submissions": len(safe_runs),
        "expected_tables": sum(item["expected_tables"] for item in safe_runs),
        "proposed_tables": sum(item["proposed_tables"] for item in safe_runs),
        "source_bound_tables": sum(item["source_bound_tables"] for item in safe_runs),
        "titles_matched": sum(item["titles_matched"] for item in safe_runs),
        "headers_matched": sum(item["headers_matched"] for item in safe_runs),
        "body_statuses_matched": sum(
            item["body_statuses_matched"] for item in safe_runs
        ),
        "gold_matched_cases": sum(item["all_expected_matched"] for item in safe_runs),
    }
    private_result = {
        "schema_version": PRIVATE_RESULT_SCHEMA,
        "freeze_sha256": freeze["freeze_sha256"],
        "source_head": freeze["source_head"],
        "qualification": qualification,
        "aggregate": aggregate,
        "retry": False,
        "repair": False,
        "best_of_n": False,
        "manual_output_edit": False,
        "product_activation": False,
        "runs": private_runs,
    }
    safe_result = {
        "schema_version": SAFE_RESULT_SCHEMA,
        "freeze_sha256": freeze["freeze_sha256"],
        "source_head": freeze["source_head"],
        "aggregate": aggregate,
        "all_cases_gold_matched": aggregate["gold_matched_cases"] == len(safe_runs),
        "all_outputs_source_bound": aggregate["source_bound_tables"]
        == aggregate["proposed_tables"],
        "retry": False,
        "repair": False,
        "best_of_n": False,
        "manual_output_edit": False,
        "private_values_committed": False,
        "model_literals_used_as_source_values": False,
        "product_activation": False,
        "runs": safe_runs,
    }
    safe_result["receipt_sha256"] = _sha256_json(safe_result)
    _write_new_json(output_root / "result.private.json", private_result)
    _write_new_json(output_root / "result.safe.json", safe_result)
    print(json.dumps(safe_result, ensure_ascii=False, indent=2))
    return 0 if safe_result["all_cases_gold_matched"] else 2


def _evaluate(*, bound: dict[str, Any] | None, gold: dict[str, Any]) -> dict[str, Any]:
    expected = gold["tables"]
    proposed = (bound or {}).get("tables") or []
    titles_matched = 0
    headers_matched = 0
    body_statuses_matched = 0
    for expected_table, proposed_table in zip(expected, proposed):
        if _contains_phrases(
            proposed_table.get("title_text", ""), expected_table["title_contains"]
        ):
            titles_matched += 1
        if _contains_phrases(
            proposed_table.get("header_text", ""), expected_table["header_contains"]
        ):
            headers_matched += 1
        if proposed_table.get("body_status") == expected_table["body_status"]:
            body_statuses_matched += 1
    expected_total = len(expected)
    all_expected_matched = (
        len(proposed) == expected_total
        and titles_matched == expected_total
        and headers_matched == expected_total
        and body_statuses_matched == expected_total
    )
    return {
        "expected_tables": expected_total,
        "proposed_tables": len(proposed),
        "source_bound_tables": len(proposed) if bound is not None else 0,
        "titles_matched": titles_matched,
        "headers_matched": headers_matched,
        "body_statuses_matched": body_statuses_matched,
        "all_expected_matched": all_expected_matched,
    }


def _contains_phrases(text: str, phrases: list[str]) -> bool:
    normalized = _normalized_tokens(text)
    return all(_normalized_tokens(phrase) <= normalized for phrase in phrases)


def _normalized_tokens(value: str) -> set[str]:
    return {
        item
        for item in re.split(r"[^0-9a-zа-яё]+", value.casefold())
        if item
    }


def _validated_input_case(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {
        "case_ref",
        "corpus_role",
        "pdf_path",
        "page_number",
        "gold",
    }:
        raise VisualTableStructureLiveError("visual_structure_input_case_invalid")
    if (
        not isinstance(value["case_ref"], str)
        or not re.fullmatch(r"[a-z0-9_]+", value["case_ref"])
        or value["corpus_role"] not in {"development", "holdout"}
        or not isinstance(value["pdf_path"], str)
        or not Path(value["pdf_path"]).resolve().is_file()
        or not isinstance(value["page_number"], int)
        or value["page_number"] < 1
    ):
        raise VisualTableStructureLiveError("visual_structure_input_case_invalid")
    _validate_gold(value["gold"])
    return copy.deepcopy(value)


def _validate_gold(value: Any) -> None:
    tables = value.get("tables") if isinstance(value, dict) else None
    if not isinstance(tables, list) or not tables:
        raise VisualTableStructureLiveError("visual_structure_gold_invalid")
    for table in tables:
        if not isinstance(table, dict) or set(table) != {
            "title_contains",
            "header_contains",
            "body_status",
        }:
            raise VisualTableStructureLiveError("visual_structure_gold_invalid")
        if (
            not isinstance(table["title_contains"], list)
            or not table["title_contains"]
            or not all(isinstance(item, str) and item for item in table["title_contains"])
            or not isinstance(table["header_contains"], list)
            or not table["header_contains"]
            or not all(isinstance(item, str) and item for item in table["header_contains"])
            or table["body_status"]
            not in {"HAS_DATA", "EMPTY_TEMPLATE", "UNCERTAIN"}
        ):
            raise VisualTableStructureLiveError("visual_structure_gold_invalid")


def _validate_freeze(value: dict[str, Any]) -> None:
    unsigned = {key: item for key, item in value.items() if key != "freeze_sha256"}
    if (
        value.get("schema_version") != FREEZE_SCHEMA
        or value.get("freeze_sha256") != _sha256_json(unsigned)
        or value.get("source_head") != _git_head()
        or _git_status()
        or value.get("provider_profile") != PROVIDER_PROFILE
        or value.get("model_id") != MODEL_ID
        or value.get("response_schema") != response_schema()
        or value.get("scheduled_model_calls") != len(value.get("cases") or [])
    ):
        raise VisualTableStructureLiveError("visual_structure_freeze_invalid_or_drifted")


def _require_clean_head() -> None:
    if _git_status():
        raise VisualTableStructureLiveError("visual_structure_worktree_not_clean")


def _require_new_external_root(path: Path) -> None:
    if path.exists() or _is_within(path, REPO_ROOT.resolve()):
        raise VisualTableStructureLiveError("visual_structure_output_root_invalid")


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise VisualTableStructureLiveError("visual_structure_json_object_required")
    return value


def _write_new_json(path: Path, value: Any) -> None:
    if path.exists():
        raise VisualTableStructureLiveError("visual_structure_output_exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def _git_head() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True
    ).strip()


def _git_status() -> str:
    return subprocess.check_output(
        ["git", "status", "--porcelain"], cwd=REPO_ROOT, text=True
    ).strip()


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


if __name__ == "__main__":
    raise SystemExit(main())
