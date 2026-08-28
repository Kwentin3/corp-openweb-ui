#!/usr/bin/env python3
"""Prepare and execute one research-only exact-crop logical-column proposal."""

from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
SERVICE_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SERVICE_ROOT.parents[1]
sys.path[:0] = [str(SCRIPT_DIR), str(SERVICE_ROOT)]

from broker_reports_gate1.full_source import FullSourceArtifactFactory  # noqa: E402
from broker_reports_gate1.pdf_table_locator_provider import (  # noqa: E402
    PdfGridExperimentProviderFactory,
    PdfGridProviderConfig,
)
from broker_reports_gate1.pdf_table_raster import (  # noqa: E402
    PdfTableRasterConfig,
    PdfTableRasterFactory,
)
from broker_reports_gate1.visual_table_structure_research import (  # noqa: E402
    VisualTableStructureError,
    VisualTableStructureProjectionFactory,
    logical_column_proposal_response_schema,
)
from local_pdf_vlm_guided_intake_development import (  # noqa: E402
    _openwebui_request,
)


INPUT_SCHEMA = "broker_reports_visual_logical_column_input_private_rd_v1"
FREEZE_SCHEMA = "broker_reports_visual_logical_column_freeze_private_rd_v1"
PRIVATE_RESULT_SCHEMA = "broker_reports_visual_logical_column_result_private_rd_v1"
SAFE_RESULT_SCHEMA = "broker_reports_visual_logical_column_result_safe_rd_v1"
MODEL_ID = "models/gemini-3.5-flash"
PROVIDER_PROFILE = "google_gemini"


class VisualLogicalColumnLiveError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--input", type=Path, required=True)
    prepare.add_argument("--private-output-root", type=Path, required=True)
    execute = subparsers.add_parser("execute")
    execute.add_argument("--freeze", type=Path, required=True)
    execute.add_argument("--env-file", type=Path, required=True)
    execute.add_argument("--private-output-root", type=Path, required=True)
    args = parser.parse_args()
    return _prepare(args) if args.command == "prepare" else _execute(args)


def _prepare(args: argparse.Namespace) -> int:
    _require_clean_head()
    source_input = _validated_input(_read_object(args.input.resolve()))
    output_root = args.private_output_root.resolve()
    _require_new_external_root(output_root)

    pdf_path = Path(source_input["pdf_path"])
    pdf_bytes = pdf_path.read_bytes()
    source_sha256 = hashlib.sha256(pdf_bytes).hexdigest()
    full_source = (
        FullSourceArtifactFactory()
        .create()
        .build(
            normalization_run_id="visual-logical-column-" + source_input["case_ref"],
            document_id="visual-logical-column-" + source_input["case_ref"],
            profile_id="visual-logical-column-live-research",
            container_format="pdf",
            content_bytes=pdf_bytes,
            source_checksum_sha256=source_sha256,
        )
    )
    if len(full_source.payloads) != 1:
        raise VisualLogicalColumnLiveError(
            "visual_logical_column_full_source_payload_invalid"
        )
    projection = full_source.payloads[0].get("pdf_text_layer_projection")
    parser_page = _projection_parser_page(
        projection=projection,
        page_number=source_input["page_number"],
        source_sha256=source_sha256,
    )
    projector = VisualTableStructureProjectionFactory().create()
    bound_structures = projector.bind(
        provider_value=source_input["visual_structure_provider_value"],
        parser_page=parser_page,
    )
    bound_structure = next(
        (
            item
            for item in bound_structures["tables"]
            if item.get("table_order") == source_input["table_order"]
        ),
        None,
    )
    if not isinstance(bound_structure, dict):
        raise VisualLogicalColumnLiveError(
            "visual_logical_column_table_order_unavailable"
        )
    if bound_structure.get("header_status") != "PRESENT" or not bound_structure.get(
        "header_word_refs"
    ):
        raise VisualLogicalColumnLiveError(
            "visual_logical_column_source_bound_header_required"
        )
    rendered = (
        PdfTableRasterFactory(PdfTableRasterConfig(padding_points=0))
        .create()
        .render(
            pdf_bytes=pdf_bytes,
            pdf_sha256=source_sha256,
            document_ref="visual_logical_column_" + source_input["case_ref"],
            page_number=source_input["page_number"],
            table_ref=f"table_{source_input['table_order']}",
            table_bbox=source_input["table_bbox"],
            dpi=150,
        )
    )
    prepared = projector.prepare_logical_column_crop_scope(
        case_ref=source_input["case_ref"],
        parser_page=parser_page,
        bound_structure=bound_structure,
        rendered_crop=rendered,
        table_order=source_input["table_order"],
    )
    png_bytes = base64.b64decode(rendered["private_png_base64"])

    output_root.mkdir(parents=True)
    png_path = output_root / "exact-table-crop.private.png"
    png_path.write_bytes(png_bytes)
    freeze = {
        "schema_version": FREEZE_SCHEMA,
        "source_head": _git_head(),
        "source_worktree_clean": True,
        "case_ref": source_input["case_ref"],
        "pdf_path": str(pdf_path),
        "source_sha256": source_sha256,
        "page_number": source_input["page_number"],
        "table_bbox": copy.deepcopy(source_input["table_bbox"]),
        "table_order": source_input["table_order"],
        "visual_structure_provider_value": copy.deepcopy(
            source_input["visual_structure_provider_value"]
        ),
        "visual_structure_provider_value_sha256": _sha256_json(
            source_input["visual_structure_provider_value"]
        ),
        "prepared_crop_scope": prepared,
        "png_path": str(png_path),
        "png_sha256": hashlib.sha256(png_bytes).hexdigest(),
        "provider_profile": PROVIDER_PROFILE,
        "model_id": MODEL_ID,
        "response_schema": logical_column_proposal_response_schema(),
        "scheduled_model_calls": 1,
        "retry": False,
        "repair": False,
        "best_of_n": False,
        "manual_output_edit": False,
        "financial_roles_assigned": False,
        "canonical_mutated": False,
        "product_activation": False,
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
                "case_ref": freeze["case_ref"],
                "scheduled_model_calls": 1,
                "crop_manifest_hash": prepared["crop_identity"]["manifest_hash"],
                "png_sha256": freeze["png_sha256"],
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
    png_bytes = Path(freeze["png_path"]).read_bytes()
    if hashlib.sha256(png_bytes).hexdigest() != freeze["png_sha256"]:
        raise VisualLogicalColumnLiveError("visual_logical_column_png_drift")

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
        raise VisualLogicalColumnLiveError(
            "visual_logical_column_provider_not_qualified"
        )
    prepared = freeze["prepared_crop_scope"]
    response = provider.invoke(
        task_id="visual_logical_column_" + freeze["case_ref"],
        model_view=prepared["model_view"],
        output_schema=freeze["response_schema"],
        png_bytes=png_bytes,
        crop_sha256=freeze["png_sha256"],
        attempt_number=1,
        attempt_lineage=[],
    )
    bound = None
    validation_error = None
    if response.get("json_output") is not None:
        try:
            bound = _bind_response(
                projector=VisualTableStructureProjectionFactory().create(),
                provider_value=response["json_output"],
                prepared=prepared,
            )
        except VisualTableStructureError as exc:
            validation_error = exc.code
    private, safe = _result_documents(
        freeze=freeze,
        qualification=qualification,
        response=response,
        bound=bound,
        validation_error=validation_error,
    )
    output_root.mkdir(parents=True)
    _write_new_json(output_root / "result.private.json", private)
    _write_new_json(output_root / "result.safe.json", safe)
    print(json.dumps(safe, ensure_ascii=False, indent=2))
    return 0 if safe["terminal"] == "SOURCE_BOUND" else 2


def _bind_response(
    *, projector: Any, provider_value: dict[str, Any], prepared: dict[str, Any]
) -> dict[str, Any]:
    """Keep the projection-owner call in one place as its crop contract evolves."""

    return projector.bind_logical_column_proposal(
        provider_value=provider_value,
        parser_page=prepared["parser_page"],
        bound_structure=prepared["bound_structure"],
        expected_crop_manifest_hash=prepared["crop_identity"]["manifest_hash"],
        crop_identity=prepared["crop_identity"],
    )


def _validated_input(value: Any) -> dict[str, Any]:
    required = {
        "schema_version",
        "case_ref",
        "pdf_path",
        "page_number",
        "table_bbox",
        "table_order",
        "visual_structure_provider_value",
    }
    if not isinstance(value, dict) or set(value) != required:
        raise VisualLogicalColumnLiveError("visual_logical_column_input_invalid")
    case_ref = value.get("case_ref")
    pdf_path = Path(str(value.get("pdf_path") or "")).resolve()
    if (
        value.get("schema_version") != INPUT_SCHEMA
        or not isinstance(case_ref, str)
        or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,127}", case_ref)
        or not pdf_path.is_file()
        or pdf_path.suffix.casefold() != ".pdf"
        or not _positive_int(value.get("page_number"))
        or not _positive_int(value.get("table_order"))
        or not _bbox(value.get("table_bbox"))
        or not isinstance(value.get("visual_structure_provider_value"), dict)
    ):
        raise VisualLogicalColumnLiveError("visual_logical_column_input_invalid")
    result = copy.deepcopy(value)
    result["pdf_path"] = str(pdf_path)
    result["table_bbox"] = [float(item) for item in result["table_bbox"]]
    return result


def _projection_parser_page(
    *, projection: Any, page_number: int, source_sha256: str
) -> dict[str, Any]:
    if (
        not isinstance(projection, dict)
        or projection.get("layout_projection_status") != "complete"
        or not isinstance(projection.get("page_inventory"), list)
        or not isinstance(projection.get("word_inventory"), list)
        or not isinstance(projection.get("bbox_inventory"), list)
    ):
        raise VisualLogicalColumnLiveError(
            "visual_logical_column_full_source_projection_incomplete"
        )
    page = next(
        (
            item
            for item in projection["page_inventory"]
            if isinstance(item, dict) and item.get("page_number") == page_number
        ),
        None,
    )
    if (
        not isinstance(page, dict)
        or page.get("layout_projection_status") != "complete"
        or not _finite_positive(page.get("layout_page_width"))
        or not _finite_positive(page.get("layout_page_height"))
        or not isinstance(page.get("page_ref"), str)
        or not page["page_ref"]
    ):
        raise VisualLogicalColumnLiveError(
            "visual_logical_column_full_source_page_unavailable"
        )
    bboxes = {
        item.get("bbox_ref"): item.get("bbox")
        for item in projection["bbox_inventory"]
        if isinstance(item, dict)
        and item.get("page_ref") == page["page_ref"]
        and isinstance(item.get("bbox_ref"), str)
    }
    words = []
    for item in projection["word_inventory"]:
        if not isinstance(item, dict) or item.get("page_ref") != page["page_ref"]:
            continue
        bbox = bboxes.get(item.get("bbox_ref"))
        word_ref = item.get("word_ref")
        if not _bbox(bbox) or not isinstance(word_ref, str) or not word_ref:
            raise VisualLogicalColumnLiveError(
                "visual_logical_column_full_source_word_invalid"
            )
        source_bbox = [float(value) for value in bbox]
        words.append(
            {
                "parser_ordinal": item.get("parser_ordinal"),
                "text": item.get("text"),
                "bbox": copy.deepcopy(source_bbox),
                "source_word_ref": word_ref,
                "source_bbox": source_bbox,
            }
        )
    if not words:
        raise VisualLogicalColumnLiveError(
            "visual_logical_column_full_source_words_empty"
        )
    return {
        "page_number": page_number,
        "source_sha256": source_sha256,
        "source_page_ref": page["page_ref"],
        "width": float(page["layout_page_width"]),
        "height": float(page["layout_page_height"]),
        "word_inventory": words,
    }


def _result_documents(
    *,
    freeze: dict[str, Any],
    qualification: dict[str, Any],
    response: dict[str, Any],
    bound: dict[str, Any] | None,
    validation_error: str | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    attempt = (
        response.get("attempt") if isinstance(response.get("attempt"), dict) else {}
    )
    failure = attempt.get("terminal_failure_class")
    if failure:
        terminal = "PROVIDER_FAILED"
    elif bound is None:
        terminal = "SOURCE_BINDING_FAILED"
    else:
        terminal = "SOURCE_BOUND"
    proposed = response.get("json_output")
    boxes = (
        proposed.get("leaf_label_boxes_2d")
        if isinstance(proposed, dict)
        and isinstance(proposed.get("leaf_label_boxes_2d"), list)
        else []
    )
    leaf_columns = bound.get("leaf_columns") if isinstance(bound, dict) else []
    shared = (
        bound.get("shared_or_non_leaf_header_word_refs")
        if isinstance(bound, dict)
        else []
    )
    counts = {
        "provider_submissions": 1,
        "provider_responses": 1,
        "leaf_boxes_proposed": len(boxes),
        "leaf_columns_source_bound": len(leaf_columns or []),
        "leaf_source_words": sum(
            len(item.get("source_word_refs") or item.get("header_word_refs") or [])
            for item in leaf_columns or []
            if isinstance(item, dict)
        ),
        "shared_or_non_leaf_header_words": len(shared or []),
    }
    hashes = {
        "source_sha256": freeze["source_sha256"],
        "png_sha256": freeze["png_sha256"],
        "crop_manifest_hash": freeze["prepared_crop_scope"]["crop_identity"][
            "manifest_hash"
        ],
        "provider_response_hash": response.get("response_hash"),
        "bound_projection_sha256": _sha256_json(bound) if bound is not None else None,
    }
    private = {
        "schema_version": PRIVATE_RESULT_SCHEMA,
        "freeze_sha256": freeze["freeze_sha256"],
        "source_head": freeze["source_head"],
        "case_ref": freeze["case_ref"],
        "terminal": terminal,
        "counts": counts,
        "hashes": hashes,
        "validation_error": validation_error,
        "qualification": copy.deepcopy(qualification),
        "provider_attempt": copy.deepcopy(attempt),
        "provider_value": copy.deepcopy(proposed),
        "bound_projection": copy.deepcopy(bound),
        "raw_private_response": copy.deepcopy(response.get("raw_private_response")),
        "retry": False,
        "repair": False,
        "best_of_n": False,
        "manual_output_edit": False,
        "financial_roles_assigned": False,
        "canonical_mutated": False,
        "product_activation": False,
    }
    private["private_result_sha256"] = _sha256_json(private)
    safe = {
        "schema_version": SAFE_RESULT_SCHEMA,
        "freeze_sha256": freeze["freeze_sha256"],
        "source_head": freeze["source_head"],
        "case_ref": freeze["case_ref"],
        "terminal": terminal,
        "counts": copy.deepcopy(counts),
        "hashes": copy.deepcopy(hashes),
        "validation_error": validation_error,
        "provider_failure_class": failure,
        "private_result_sha256": private["private_result_sha256"],
        "one_frozen_model_call": True,
        "retry": False,
        "repair": False,
        "best_of_n": False,
        "manual_output_edit": False,
        "private_values_committed": False,
        "model_literals_used_as_source_values": False,
        "financial_roles_assigned": False,
        "canonical_mutated": False,
        "product_activation": False,
    }
    safe["receipt_sha256"] = _sha256_json(safe)
    return private, safe


def _validate_freeze(value: dict[str, Any]) -> None:
    unsigned = {key: item for key, item in value.items() if key != "freeze_sha256"}
    prepared = value.get("prepared_crop_scope")
    crop_identity = (
        prepared.get("crop_identity") if isinstance(prepared, dict) else None
    )
    if (
        value.get("schema_version") != FREEZE_SCHEMA
        or value.get("freeze_sha256") != _sha256_json(unsigned)
        or value.get("source_head") != _git_head()
        or _git_status()
        or value.get("source_worktree_clean") is not True
        or value.get("provider_profile") != PROVIDER_PROFILE
        or value.get("model_id") != MODEL_ID
        or value.get("response_schema") != logical_column_proposal_response_schema()
        or value.get("scheduled_model_calls") != 1
        or not isinstance(prepared, dict)
        or not isinstance(crop_identity, dict)
        or prepared.get("response_schema") != value.get("response_schema")
        or crop_identity.get("png_sha256") != value.get("png_sha256")
        or value.get("visual_structure_provider_value_sha256")
        != _sha256_json(value.get("visual_structure_provider_value"))
        or any(
            value.get(key) is not False
            for key in (
                "retry",
                "repair",
                "best_of_n",
                "manual_output_edit",
                "financial_roles_assigned",
                "canonical_mutated",
                "product_activation",
            )
        )
    ):
        raise VisualLogicalColumnLiveError(
            "visual_logical_column_freeze_invalid_or_drifted"
        )


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise VisualLogicalColumnLiveError("visual_logical_column_json_object_required")
    return value


def _write_new_json(path: Path, value: Any) -> None:
    if path.exists():
        raise VisualLogicalColumnLiveError("visual_logical_column_output_exists")
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


def _require_clean_head() -> None:
    if _git_status():
        raise VisualLogicalColumnLiveError("visual_logical_column_worktree_not_clean")


def _require_new_external_root(path: Path) -> None:
    if path.exists() or _is_within(path, REPO_ROOT.resolve()):
        raise VisualLogicalColumnLiveError("visual_logical_column_output_root_invalid")


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 1


def _finite_positive(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
        and float(value) > 0
    )


def _bbox(value: Any) -> bool:
    return (
        isinstance(value, list)
        and len(value) == 4
        and all(
            isinstance(item, (int, float))
            and not isinstance(item, bool)
            and math.isfinite(float(item))
            for item in value
        )
        and float(value[2]) > float(value[0])
        and float(value[3]) > float(value[1])
    )


if __name__ == "__main__":
    raise SystemExit(main())
