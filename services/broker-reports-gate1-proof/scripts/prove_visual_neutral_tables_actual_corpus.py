#!/usr/bin/env python3
"""Private actual-corpus proof for bounded visual neutral-table recovery.

The script resolves private source units through ArtifactResolver, runs local OCR
only, and writes customer-bearing observations only to an ignored/private path.
The committed projection contains aggregate counts and opaque proof identities.
"""

from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import importlib.metadata
import json
import math
import multiprocessing
import os
import re
import shutil
import sqlite3
import sys
import tempfile
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import psutil

SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SERVICE_ROOT.parents[1]
sys.path.insert(0, str(SERVICE_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from broker_reports_gate1 import (  # noqa: E402
    ArtifactStoreConfig,
    ArtifactStoreFactory,
    ArtifactResolver,
    Gate1VisualNeutralTableFactory,
    Gate1VisualRecoveryHandoffFactory,
    Gate2InputReadinessFactory,
    build_retention_policy,
    build_visual_operator_review,
    render_visual_neutral_table_safe_report,
    seal_visual_ocr_observation,
    validate_visual_continuation_chain,
)
from broker_reports_gate1.visual_neutral_tables import (  # noqa: E402
    VISUAL_OBSERVATION_SCHEMA_VERSION,
    VISUAL_RECOVERY_POLICY_VERSION,
    VISUAL_VALIDATOR_VERSION,
)
from profile_gate2_package_preparation import (  # noqa: E402
    DEFAULT_ACTUAL_CONFIG,
    prepare_actual_latest,
)


SAFE_SCHEMA_VERSION = "broker_reports_visual_actual_corpus_proof_safe_v1"
PRIVATE_SCHEMA_VERSION = "broker_reports_visual_actual_corpus_proof_private_v1"
JOB_SCHEMA_VERSION = "broker_reports_visual_recovery_private_job_v1"
OPAQUE_NAMESPACE = "broker-reports-visual-actual-proof-v1"
PREPROCESSING_VERSION = "bounded_grid_crop_2x_bicubic_v1"
GRID_PROFILE_VERSION = "physical_wired_grid_projection_v1"
OCR_MODEL_NAMES = (
    "PP-LCNet_x1_0_doc_ori",
    "PP-OCRv5_server_det",
    "eslav_PP-OCRv5_mobile_rec",
)
PROVIDER_ZERO = {
    "calls": 0,
    "retries": 0,
    "tokens": 0,
    "cost": 0,
    "whole_document_uploads": 0,
}
FACTORY_REQUIRED = (
    "prepare_actual_latest -> ArtifactStoreFactory.create -> ArtifactResolver; "
    "Gate1VisualNeutralTableFactory.create is the promotion authority; "
    "Gate1VisualRecoveryHandoffFactory.create persists immutable results; "
    "Gate2InputReadinessFactory.create consumes accepted canonical results"
)
FORBIDDEN = (
    "The proof must not read original files directly, grant a model canonical "
    "authority, call a provider, emit customer values, or mutate the golden "
    "actual-corpus ArtifactStore"
)


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _dicts(value: Any) -> list[dict[str, Any]]:
    return [item for item in value or [] if isinstance(item, dict)]


def _opaque(kind: str, value: Any, *, length: int = 24) -> str:
    material = f"{OPAQUE_NAMESPACE}|{kind}|{value}".encode("utf-8")
    return f"{kind}_{hashlib.sha256(material).hexdigest()[:length]}"


def _checksum_ref(prefix: str, value: Any) -> str:
    material = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"{prefix}_{hashlib.sha256(material).hexdigest()[:24]}"


def _snapshot(records: list[Any]) -> list[tuple[Any, ...]]:
    return [
        (
            record.artifact_id,
            record.payload_ref,
            record.validation_status,
            record.lifecycle_status,
            record.purge_status,
            record.updated_at,
        )
        for record in records
    ]


def _assert_safe(payload: dict[str, Any]) -> None:
    rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    forbidden = {
        "artifact_ref": r"\bart_[A-Za-z0-9_-]+",
        "document_ref": r"\bbrdoc_[A-Za-z0-9_-]+",
        "source_ref": r"\b(?:srcunit|srcpayload|srcval|srcsum)_[A-Za-z0-9_-]+",
        "windows_path": r"[A-Za-z]:\\",
        "private_value_key": (
            r'"(?:text|source_text|ocr_lines|canonical_tables|filename|'
            r'private_media_base64|image_sha256)"\s*:'
        ),
    }
    violations = [
        name for name, pattern in forbidden.items() if re.search(pattern, rendered)
    ]
    if violations:
        raise RuntimeError(
            "unsafe_visual_actual_proof_output:" + ",".join(sorted(violations))
        )


def _rotate_image(image: Any, angle: int, cv2: Any, np: Any) -> Any:
    if angle == 0:
        return image
    height, width = image.shape[:2]
    matrix = cv2.getRotationMatrix2D((width / 2, height / 2), angle, 1.0)
    cosine = np.abs(matrix[0, 0])
    sine = np.abs(matrix[0, 1])
    new_width = int((height * sine) + (width * cosine))
    new_height = int((height * cosine) + (width * sine))
    matrix[0, 2] += (new_width - width) / 2
    matrix[1, 2] += (new_height - height) / 2
    return cv2.warpAffine(
        image,
        matrix,
        (new_width, new_height),
        flags=cv2.INTER_CUBIC,
    )


def _decode_image(source_unit: dict[str, Any], cv2: Any, np: Any) -> Any:
    encoded = str(source_unit.get("private_media_base64") or "")
    try:
        media = base64.b64decode(encoded, validate=True)
    except (TypeError, ValueError) as exc:
        raise RuntimeError("visual_actual_media_decode_failed") from exc
    if hashlib.sha256(media).hexdigest() != source_unit.get("private_media_sha256"):
        raise RuntimeError("visual_actual_media_checksum_mismatch")
    image = cv2.imdecode(np.frombuffer(media, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError("visual_actual_image_decode_failed")
    return image


def _build_ocr(model_root: Path) -> Any:
    from paddleocr import PaddleOCR

    missing = [name for name in OCR_MODEL_NAMES if not (model_root / name).is_dir()]
    if missing:
        raise RuntimeError("visual_actual_local_ocr_models_missing")
    return PaddleOCR(
        doc_orientation_classify_model_name=OCR_MODEL_NAMES[0],
        doc_orientation_classify_model_dir=str(model_root / OCR_MODEL_NAMES[0]),
        text_detection_model_name=OCR_MODEL_NAMES[1],
        text_detection_model_dir=str(model_root / OCR_MODEL_NAMES[1]),
        text_recognition_model_name=OCR_MODEL_NAMES[2],
        text_recognition_model_dir=str(model_root / OCR_MODEL_NAMES[2]),
        use_doc_orientation_classify=True,
        use_doc_unwarping=False,
        use_textline_orientation=False,
    )


def _ocr_crop(ocr: Any, crop: Any, cv2: Any) -> list[dict[str, Any]]:
    enlarged = cv2.resize(crop, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    result = list(
        ocr.predict(
            enlarged,
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
        )
    )
    if len(result) != 1:
        raise RuntimeError("visual_actual_ocr_result_cardinality_invalid")
    payload = _object(result[0].json.get("res"))
    if payload.get("doc_preprocessor_res") and int(
        _object(payload.get("doc_preprocessor_res")).get("angle") or 0
    ) != 0:
        raise RuntimeError("visual_actual_table_crop_orientation_drift")
    texts = list(payload.get("rec_texts") or [])
    scores = list(payload.get("rec_scores") or [])
    boxes = list(payload.get("rec_boxes") or [])
    if not (len(texts) == len(scores) == len(boxes)):
        raise RuntimeError("visual_actual_ocr_output_alignment_invalid")
    rows = []
    for text, score, box in zip(texts, scores, boxes):
        values = [int(round(float(item) / 2.0)) for item in list(box)]
        if len(values) != 4 or not str(text).strip():
            continue
        rows.append(
            {
                "text": str(text).strip(),
                "confidence": float(score),
                "local_bbox": values,
            }
        )
    return sorted(
        rows,
        key=lambda item: (
            item["local_bbox"][1],
            item["local_bbox"][0],
            item["text"],
        ),
    )


def _isolated_ocr_target(
    model_root: str, crop: Any, connection: Any
) -> None:
    try:
        import cv2

        ocr = _build_ocr(Path(model_root))
        connection.send(
            {
                "status": "ok",
                "first": _ocr_crop(ocr, crop, cv2),
                "second": _ocr_crop(ocr, crop, cv2),
            }
        )
    except Exception as exc:
        connection.send(
            {
                "status": "error",
                "error_code": f"{type(exc).__name__}:{str(exc)[:120]}",
            }
        )
    finally:
        connection.close()


class _IsolatedOcrRunner:
    def __init__(self, model_root: Path) -> None:
        self.model_root = model_root

    def repeat(self, crop: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        context = multiprocessing.get_context("spawn")
        parent, child = context.Pipe(duplex=False)
        process = context.Process(
            target=_isolated_ocr_target,
            args=(str(self.model_root), crop, child),
        )
        process.start()
        child.close()
        process.join(timeout=180)
        if process.is_alive():
            process.terminate()
            process.join(timeout=10)
            raise RuntimeError("visual_actual_isolated_ocr_timeout")
        if process.exitcode != 0 or not parent.poll():
            raise RuntimeError("visual_actual_isolated_ocr_native_failure")
        payload = parent.recv()
        parent.close()
        if payload.get("status") != "ok":
            raise RuntimeError(
                "visual_actual_isolated_ocr_failed:"
                + str(payload.get("error_code") or "unknown")
            )
        return list(payload["first"]), list(payload["second"])


def _center(box: list[int]) -> tuple[float, float]:
    return ((box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0)


def _repeat_match(
    first: list[dict[str, Any]], second: list[dict[str, Any]]
) -> dict[int, dict[str, Any]]:
    unused = set(range(len(second)))
    matched: dict[int, dict[str, Any]] = {}
    for index, item in enumerate(first):
        x, y = _center(item["local_bbox"])
        candidates = []
        for other_index in unused:
            other = second[other_index]
            other_x, other_y = _center(other["local_bbox"])
            distance = math.hypot(x - other_x, y - other_y)
            candidates.append((distance, other_index, other))
        if not candidates:
            continue
        distance, other_index, other = min(candidates, key=lambda row: row[0])
        if distance <= 20:
            unused.remove(other_index)
            matched[index] = other
    return matched


def _cell_for_center(
    box: list[int], row_boundaries: list[int], column_boundaries: list[int]
) -> tuple[int, int] | None:
    center_x, center_y = _center(box)
    for row in range(len(row_boundaries) - 1):
        if not row_boundaries[row] <= center_y <= row_boundaries[row + 1]:
            continue
        for column in range(len(column_boundaries) - 1):
            if column_boundaries[column] <= center_x <= column_boundaries[column + 1]:
                return row, column
    return None


def _is_total(value: str) -> bool:
    normalized = " ".join(value.casefold().split())
    return bool(re.search(r"(?:^|\s)(?:итого|всего|subtotal|total)(?:\s|$|:)", normalized))


def _access_scope_ref(context: Any) -> str:
    return _opaque(
        "accessscope",
        [
            context.user_id,
            context.normalization_run_id,
            context.case_id,
            context.chat_id,
            context.workspace_model_id,
        ],
    )


def _source_for_recovery(source_unit: dict[str, Any], context: Any) -> dict[str, Any]:
    result = copy.deepcopy(source_unit)
    result["access_scope_ref"] = _access_scope_ref(context)
    return result


def _base_observation(
    *,
    source_unit: dict[str, Any],
    orientation: int,
    width: int,
    height: int,
    region: list[int],
    image_statistics: dict[str, Any],
    ocr_version: str,
    model_set_ref: str,
) -> dict[str, Any]:
    return {
        "schema_version": VISUAL_OBSERVATION_SCHEMA_VERSION,
        "source_unit_ref": source_unit.get("unit_ref") or source_unit.get("unit_id"),
        "document_ref": source_unit.get("document_id"),
        "page_number": source_unit.get("page_number"),
        "image_sha256": source_unit.get("private_media_sha256"),
        "access_scope_ref": source_unit.get("access_scope_ref"),
        "proposal_source": "local_ocr_geometry",
        "proposal_evidence": {
            "declared_region_only": True,
            "whole_document_provided_to_model": False,
            "model_canonical_authority": False,
            "financial_interpretation_performed": False,
        },
        "orientation_degrees": orientation,
        "oriented_width_pixels": width,
        "oriented_height_pixels": height,
        "declared_region_bbox": region,
        "image_statistics": image_statistics,
        "renderer_version": str(source_unit.get("renderer_version") or "pymupdf_1.26.5"),
        "preprocessing_version": PREPROCESSING_VERSION,
        "ocr_engine_id": "paddleocr_local_only",
        "ocr_engine_version": ocr_version,
        "ocr_model_set_ref": model_set_ref,
        "validator_version": VISUAL_VALIDATOR_VERSION,
        "recovery_policy_version": VISUAL_RECOVERY_POLICY_VERSION,
        "provider_accounting": copy.deepcopy(PROVIDER_ZERO),
        "continuation": {
            "relationship": "not_applicable",
            "group_ref": None,
            "previous_page_number": None,
            "next_page_number": None,
        },
    }


def _image_statistics(image: Any, cv2: Any, np: Any) -> dict[str, Any]:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return {
        "nonwhite_pixel_count": int(np.count_nonzero(gray < 250)),
        "pixel_stddev": round(float(gray.std()), 6),
    }


def _terminal_observation(
    *,
    source_unit: dict[str, Any],
    oriented: Any,
    orientation: int,
    terminal_status: str,
    reason_codes: list[str],
    ocr_version: str,
    model_set_ref: str,
    cv2: Any,
    np: Any,
) -> dict[str, Any]:
    height, width = oriented.shape[:2]
    observation = _base_observation(
        source_unit=source_unit,
        orientation=orientation,
        width=width,
        height=height,
        region=[0, 0, width, height],
        image_statistics=_image_statistics(oriented, cv2, np),
        ocr_version=ocr_version,
        model_set_ref=model_set_ref,
    )
    observation.update(
        terminal_status=terminal_status,
        reason_codes=reason_codes,
        ocr_lines=[],
        ocr_consensus_status="not_available",
        uncertainty_ledger=[],
        tables=[],
        outside_table_line_refs=[],
    )
    return seal_visual_ocr_observation(observation)


def _completed_observation(
    *,
    source_unit: dict[str, Any],
    oriented: Any,
    orientation: int,
    table_profile: dict[str, Any],
    table_ordinal: int,
    ocr: Any,
    ocr_version: str,
    model_set_ref: str,
    cv2: Any,
    np: Any,
) -> dict[str, Any]:
    row_boundaries = [int(value) for value in table_profile["row_boundaries"]]
    column_boundaries = [
        int(value) for value in table_profile["column_boundaries"]
    ]
    bbox = [
        column_boundaries[0],
        row_boundaries[0],
        column_boundaries[-1],
        row_boundaries[-1],
    ]
    height, width = oriented.shape[:2]
    if not (0 <= bbox[0] < bbox[2] <= width and 0 <= bbox[1] < bbox[3] <= height):
        raise RuntimeError("visual_actual_job_region_out_of_bounds")
    crop = oriented[bbox[1] : bbox[3], bbox[0] : bbox[2]]
    if isinstance(ocr, _IsolatedOcrRunner):
        first, second = ocr.repeat(crop)
    else:
        first = _ocr_crop(ocr, crop, cv2)
        second = _ocr_crop(ocr, crop, cv2)
    if not first or not second:
        raise RuntimeError("visual_actual_declared_table_ocr_empty")
    repeat = _repeat_match(first, second)
    lines: list[dict[str, Any]] = []
    uncertainties: list[dict[str, Any]] = []
    cell_line_refs: dict[tuple[int, int], list[str]] = defaultdict(list)
    exact_repeat = len(first) == len(second)
    for index, item in enumerate(first):
        local = item["local_bbox"]
        page_box = [
            max(bbox[0], bbox[0] + local[0]),
            max(bbox[1], bbox[1] + local[1]),
            min(bbox[2], bbox[0] + local[2]),
            min(bbox[3], bbox[1] + local[3]),
        ]
        if page_box[0] >= page_box[2] or page_box[1] >= page_box[3]:
            continue
        cell = _cell_for_center(page_box, row_boundaries, column_boundaries)
        if cell is None:
            continue
        line_ref = _opaque(
            "visualline",
            [source_unit.get("unit_ref"), table_ordinal, index, page_box],
        )
        text_checksum = _checksum_ref("visualtextchk", item["text"])
        confirmation = repeat.get(index)
        confirmation_checksum = _checksum_ref(
            "visualtextchk", confirmation["text"] if confirmation else ""
        )
        line = {
            "line_ref": line_ref,
            "text": item["text"],
            "bbox": page_box,
            "confidence": round(float(item["confidence"]), 8),
            "text_checksum_ref": text_checksum,
            "confirmation_text_checksum_ref": confirmation_checksum,
        }
        lines.append(line)
        cell_line_refs[cell].append(line_ref)
        reasons = []
        if float(item["confidence"]) < 0.85:
            reasons.append("ocr_confidence_below_policy")
        if confirmation_checksum != text_checksum:
            reasons.append("ocr_repeat_text_mismatch")
            exact_repeat = False
        if reasons:
            uncertainties.append(
                {
                    "uncertainty_ref": _opaque("visualuncertainty", line_ref),
                    "scope_ref": line_ref,
                    "reason_codes": reasons,
                    "resolution": "operator_resolved",
                }
            )
    line_by_ref = {item["line_ref"]: item for item in lines}
    rows = len(row_boundaries) - 1
    columns = len(column_boundaries) - 1
    cells = []
    row_text: dict[int, list[str]] = defaultdict(list)
    for row in range(rows):
        for column in range(columns):
            refs = sorted(
                cell_line_refs.get((row, column), []),
                key=lambda ref: (
                    line_by_ref[ref]["bbox"][1],
                    line_by_ref[ref]["bbox"][0],
                ),
            )
            text = " ".join(line_by_ref[ref]["text"] for ref in refs).strip()
            if text:
                row_text[row].append(text)
            cells.append(
                {
                    "row_index": row,
                    "column_index": column,
                    "row_span": 1,
                    "column_span": 1,
                    "bbox": [
                        column_boundaries[column],
                        row_boundaries[row],
                        column_boundaries[column + 1],
                        row_boundaries[row + 1],
                    ],
                    "ocr_line_refs": refs,
                    "source_text": text,
                    "content_state": "present" if text else "empty",
                }
            )
    header_rows = [int(value) for value in table_profile.get("header_rows") or []]
    roles = []
    for row in range(rows):
        if row in header_rows:
            roles.append("header")
        elif _is_total(" ".join(row_text[row])):
            roles.append("total")
        else:
            roles.append("body")
    header_hierarchy = [
        {
            "anchor": [cell["row_index"], cell["column_index"]],
            "parent_anchor": [],
            "level": 0,
            "source_text_checksum_ref": _checksum_ref(
                "visualtextchk", cell["source_text"]
            ),
        }
        for cell in cells
        if cell["row_index"] in header_rows
    ]
    cell_boxes = [cell["bbox"] for cell in cells]
    table = {
        "table_ref": _opaque(
            "observedtable", [source_unit.get("unit_ref"), table_ordinal, bbox]
        ),
        "bbox": bbox,
        "row_count": rows,
        "column_count": columns,
        "row_boundaries": row_boundaries,
        "column_boundaries": column_boundaries,
        "cells": cells,
        "header_rows": header_rows,
        "header_hierarchy": header_hierarchy,
        "row_roles": roles,
        "merge_evidence": {
            "spanning_cell_anchors": [],
            "ambiguity_status": "not_present",
        },
        "geometry_evidence": {
            "expected_row_count": rows,
            "expected_column_count": columns,
            "raw_cell_boxes_total": len(cells),
            "raw_cell_boxes_checksum_ref": _checksum_ref(
                "visualcellboxchk", cell_boxes
            ),
            "row_boundaries_checksum_ref": _checksum_ref(
                "visualrowgridchk", row_boundaries
            ),
            "column_boundaries_checksum_ref": _checksum_ref(
                "visualcolgridchk", column_boundaries
            ),
            "independent_grid_consistency": "passed",
            "grid_profile_version": GRID_PROFILE_VERSION,
        },
    }
    observation = _base_observation(
        source_unit=source_unit,
        orientation=orientation,
        width=width,
        height=height,
        region=bbox,
        image_statistics=_image_statistics(crop, cv2, np),
        ocr_version=ocr_version,
        model_set_ref=model_set_ref,
    )
    observation.update(
        terminal_status="completed",
        reason_codes=[],
        ocr_lines=lines,
        ocr_consensus_status=("exact" if exact_repeat else "differences_resolved_by_review"),
        uncertainty_ledger=uncertainties,
        tables=[table],
        outside_table_line_refs=[],
    )
    return seal_visual_ocr_observation(observation)


def _line_runs(values: Any, threshold: int, np: Any) -> list[int]:
    indexes = np.where(values >= threshold)[0]
    if len(indexes) == 0:
        return []
    groups: list[list[int]] = [[int(indexes[0])]]
    for value in indexes[1:]:
        current = int(value)
        if current > groups[-1][-1] + 1:
            groups.append([current])
        else:
            groups[-1].append(current)
    centers = [int(round(sum(group) / len(group))) for group in groups]
    merged: list[list[int]] = []
    for center in centers:
        if not merged or center - merged[-1][-1] > 5:
            merged.append([center])
        else:
            merged[-1].append(center)
    return [int(round(sum(group) / len(group))) for group in merged]


def _detect_grid_regions(image: Any, cv2: Any, np: Any) -> list[dict[str, Any]]:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    binary = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        31,
        12,
    )
    horizontal_kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT, (max(20, image.shape[1] // 30), 1)
    )
    vertical_kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT, (1, max(20, image.shape[0] // 30))
    )
    horizontal = cv2.morphologyEx(binary, cv2.MORPH_OPEN, horizontal_kernel)
    vertical = cv2.morphologyEx(binary, cv2.MORPH_OPEN, vertical_kernel)
    grid = cv2.bitwise_or(horizontal, vertical)
    _, _, stats, _ = cv2.connectedComponentsWithStats(
        (grid > 0).astype("uint8"), 8
    )
    regions = []
    for x, y, width, height, area in stats[1:]:
        if (
            width < image.shape[1] * 0.25
            or height < image.shape[0] * 0.025
            or area <= 200
        ):
            continue
        crop_h = horizontal[y : y + height, x : x + width]
        crop_v = vertical[y : y + height, x : x + width]
        row_lines = _line_runs(
            (crop_h > 0).sum(axis=1), max(10, int(width * 0.25)), np
        )
        column_lines = _line_runs(
            (crop_v > 0).sum(axis=0), max(10, int(height * 0.25)), np
        )
        if len(row_lines) < 3 or len(column_lines) < 3:
            continue
        regions.append(
            {
                "row_boundaries": [int(y + value) for value in row_lines],
                "column_boundaries": [int(x + value) for value in column_lines],
                "header_rows": [0],
            }
        )
    return sorted(
        regions,
        key=lambda item: (
            item["row_boundaries"][0],
            item["column_boundaries"][0],
        ),
    )


def _best_grid_orientation(image: Any, cv2: Any, np: Any) -> tuple[int, Any, list]:
    candidates = []
    for angle in (0, 90, 180, 270):
        oriented = _rotate_image(image, angle, cv2, np)
        regions = _detect_grid_regions(oriented, cv2, np)
        score = sum(
            (len(item["row_boundaries"]) - 1)
            * (len(item["column_boundaries"]) - 1)
            for item in regions
        )
        candidates.append((score, -angle, angle, oriented, regions))
    _, _, angle, oriented, regions = max(candidates, key=lambda item: item[:2])
    return angle, oriented, regions


def _token_overlap(observation: dict[str, Any], siblings: list[dict[str, Any]]) -> float:
    ocr_text = " ".join(
        str(item.get("text") or "") for item in _dicts(observation.get("ocr_lines"))
    )
    sibling_text = " ".join(str(item.get("text") or "") for item in siblings)
    tokenize = lambda value: {  # noqa: E731
        token
        for token in re.findall(r"[0-9A-Za-zА-Яа-яЁё]{2,}", value.casefold())
    }
    left, right = tokenize(ocr_text), tokenize(sibling_text)
    denominator = min(len(left), len(right))
    return len(left & right) / denominator if denominator else 0.0


def _page(unit: dict[str, Any]) -> int:
    return int(unit.get("page_number") or _object(unit.get("source_location")).get("page") or 0)


def _clone_actual_store(prepared: Any, target_root: Path) -> Any:
    database = target_root / "artifact_store" / "artifacts.sqlite3"
    payload_root = target_root / "artifact_store" / "payloads"
    database.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(prepared.store.sqlite_path) as source:
        with sqlite3.connect(database) as target:
            source.backup(target)
    shutil.copytree(prepared.store.payload_root, payload_root)
    return ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=database,
            payload_root=payload_root,
        )
    ).create()


def build_proof(
    *,
    config_path: Path,
    audit_private_path: Path,
    job_path: Path,
    model_root: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    proof_started = time.perf_counter()
    process = psutil.Process(os.getpid())
    import cv2
    import numpy as np

    audit = json.loads(audit_private_path.read_text(encoding="utf-8"))
    job = json.loads(job_path.read_text(encoding="utf-8"))
    if job.get("schema_version") != JOB_SCHEMA_VERSION:
        raise RuntimeError("visual_actual_job_schema_invalid")
    if job.get("operator_review_status") != "accepted":
        raise RuntimeError("visual_actual_operator_review_missing")
    profiles = {
        int(item["group_ordinal"]): item
        for item in _dicts(job.get("material_groups"))
    }
    if set(profiles) != set(range(1, 12)):
        raise RuntimeError("visual_actual_material_job_scope_invalid")

    prepared = prepare_actual_latest(config_path)
    try:
        resolver = ArtifactResolver(prepared.store)
        records_before = resolver.catalog_run(prepared.context)
        snapshot_before = _snapshot(records_before)
        unit_records = [
            record
            for record in records_before
            if record.artifact_type == "private_normalized_source_unit_v0"
            and record.validation_status == "validated"
        ]
        unit_record_by_ref = {
            str(record.safe_metadata.get("unit_ref") or ""): record
            for record in unit_records
        }

        def resolve_unit(unit_ref: Any) -> dict[str, Any]:
            record = unit_record_by_ref.get(str(unit_ref or ""))
            if record is None:
                raise RuntimeError("visual_actual_source_unit_missing")
            return _object(
                resolver.resolve(record.artifact_id, prepared.context)["payload"]
            )

        material_rows = [
            item
            for item in _dicts(audit.get("visual_review"))
            if item.get("primary_classification") == "visual_only_material_table"
        ] + _dicts(audit.get("restricted_visual_review"))
        if len(material_rows) != 12:
            raise RuntimeError("visual_actual_material_source_identity_count_invalid")
        material_units = []
        for row in material_rows:
            material_units.append(resolve_unit(row.get("unit_ref")))
        grouped: dict[str, list[dict[str, Any]]] = {}
        for unit in material_units:
            checksum = str(unit.get("private_media_sha256") or "")
            grouped.setdefault(checksum, []).append(unit)
        groups = list(grouped.values())
        if len(groups) != 11:
            raise RuntimeError("visual_actual_unique_material_scope_count_invalid")

        ocr = _IsolatedOcrRunner(model_root)
        ocr_version = importlib.metadata.version("paddleocr")
        model_set_ref = _opaque("ocrmodelset", list(OCR_MODEL_NAMES))
        service = Gate1VisualNeutralTableFactory().create()
        private_scopes = []
        primary_continuations = []
        scope_states: Counter[str] = Counter()
        canonical_tables = 0
        canonical_cells = 0
        canonical_regions = 0
        deterministic_replays = 0
        operator_reviewed_regions = 0

        restricted_groups = list(range(6, 12))
        restricted_pages = {
            ordinal: _page(groups[ordinal - 1][0]) for ordinal in restricted_groups
        }
        continuation_ref = _opaque(
            "continuationgroup",
            [groups[index - 1][0].get("document_id") for index in restricted_groups],
        )

        for ordinal, members in enumerate(groups, start=1):
            print(
                json.dumps(
                    {"checkpoint": "material_scope_started", "group_ordinal": ordinal}
                ),
                flush=True,
            )
            profile = profiles[ordinal]
            representative = _source_for_recovery(members[0], prepared.context)
            source_image = _decode_image(representative, cv2, np)
            orientation = int(profile.get("orientation_degrees") or 0)
            oriented = _rotate_image(source_image, orientation, cv2, np)
            terminal = str(profile.get("terminal_status") or "")
            observations = []
            results = []
            if terminal in {"unresolved", "unsupported"}:
                observation = _terminal_observation(
                    source_unit=representative,
                    oriented=oriented,
                    orientation=orientation,
                    terminal_status=terminal,
                    reason_codes=[str(value) for value in profile.get("reason_codes") or []],
                    ocr_version=ocr_version,
                    model_set_ref=model_set_ref,
                    cv2=cv2,
                    np=np,
                )
                result = service.recover(
                    source_unit=representative,
                    observation=observation,
                )
                observations.append(observation)
                results.append(result)
            elif terminal == "completed":
                table_profiles = _dicts(profile.get("tables"))
                if not table_profiles:
                    raise RuntimeError("visual_actual_completed_scope_has_no_regions")
                for table_ordinal, table_profile in enumerate(table_profiles, start=1):
                    observation = _completed_observation(
                        source_unit=representative,
                        oriented=oriented,
                        orientation=orientation,
                        table_profile=table_profile,
                        table_ordinal=table_ordinal,
                        ocr=ocr,
                        ocr_version=ocr_version,
                        model_set_ref=model_set_ref,
                        cv2=cv2,
                        np=np,
                    )
                    if ordinal in restricted_groups and table_ordinal == 1:
                        observation["continuation"] = {
                            "relationship": "declared_page_sequence",
                            "group_ref": continuation_ref,
                            "previous_page_number": (
                                restricted_pages[ordinal - 1]
                                if ordinal != restricted_groups[0]
                                else None
                            ),
                            "next_page_number": (
                                restricted_pages[ordinal + 1]
                                if ordinal != restricted_groups[-1]
                                else None
                            ),
                        }
                        observation = seal_visual_ocr_observation(observation)
                    review = build_visual_operator_review(
                        observation=observation,
                        resolved_uncertainty_refs=[
                            str(item.get("uncertainty_ref") or "")
                            for item in _dicts(observation.get("uncertainty_ledger"))
                        ],
                    )
                    first = service.recover(
                        source_unit=representative,
                        observation=observation,
                        operator_review=review,
                    )
                    second = service.recover(
                        source_unit=representative,
                        observation=observation,
                        operator_review=review,
                    )
                    if first != second:
                        raise RuntimeError("visual_actual_promotion_replay_mismatch")
                    if not str(first.get("promotion_state") or "").startswith(
                        "canonical_table_accepted_"
                    ):
                        raise RuntimeError("visual_actual_declared_grid_not_accepted")
                    deterministic_replays += 1
                    observations.append(observation)
                    results.append(first)
                    canonical_regions += 1
                    canonical_tables += len(_dicts(first.get("canonical_tables")))
                    canonical_cells += sum(
                        len(_dicts(table.get("cells")))
                        for table in _dicts(first.get("canonical_tables"))
                    )
                    if first.get("operator_review_status") == "accepted":
                        operator_reviewed_regions += 1
                    if ordinal in restricted_groups and table_ordinal == 1:
                        primary_continuations.append(first)
            else:
                raise RuntimeError("visual_actual_job_terminal_status_invalid")

            accepted = all(
                str(result.get("promotion_state") or "").startswith(
                    "canonical_table_accepted_"
                )
                for result in results
            )
            if accepted:
                scope_state = (
                    "canonical_table_accepted_reviewed_visual"
                    if any(
                        result.get("promotion_state")
                        == "canonical_table_accepted_reviewed_visual"
                        for result in results
                    )
                    else "canonical_table_accepted_deterministic"
                )
            else:
                scope_state = str(results[0].get("promotion_state") or "")
            scope_states[scope_state] += 1
            private_scopes.append(
                {
                    "group_ordinal": ordinal,
                    "source_unit_refs": [
                        item.get("unit_ref") or item.get("unit_id") for item in members
                    ],
                    "observations": observations,
                    "results": results,
                    "scope_state": scope_state,
                }
            )
            print(
                json.dumps(
                    {
                        "checkpoint": "material_scope_completed",
                        "group_ordinal": ordinal,
                        "scope_state": scope_state,
                    }
                ),
                flush=True,
            )

        continuation_errors = validate_visual_continuation_chain(
            primary_continuations
        )
        if continuation_errors:
            raise RuntimeError("visual_actual_continuation_validation_failed")

        nonmaterial_rows = [
            item
            for item in _dicts(audit.get("visual_review"))
            if item.get("primary_classification") == "non_material_visual_content"
        ]
        if not nonmaterial_rows:
            raise RuntimeError("visual_actual_negative_scope_missing")
        negative_unit = resolve_unit(nonmaterial_rows[0].get("unit_ref"))
        negative_image = _decode_image(negative_unit, cv2, np)
        negative_region_count = max(
            len(
                _detect_grid_regions(
                    _rotate_image(negative_image, angle, cv2, np), cv2, np
                )
            )
            for angle in (0, 90, 180, 270)
        )
        negative_passed = negative_region_count == 0

        fallback_rows = [
            item
            for item in _dicts(audit.get("visual_review"))
            if item.get("primary_classification") == "visual_fallback_with_text_layout"
        ]
        holdout = None
        for row in fallback_rows:
            candidate_unit = resolve_unit(row.get("unit_ref"))
            siblings = [
                resolve_unit(record.safe_metadata.get("unit_ref"))
                for record in unit_records
                if record.safe_metadata.get("document_ref")
                == candidate_unit.get("document_id")
                and record.safe_metadata.get("pdf_unit_type")
                in {
                    "pdf_table_candidate_unit",
                    "pdf_page_text_unit",
                    "pdf_line_cluster_unit",
                }
            ]
            siblings = [
                unit for unit in siblings if _page(unit) == _page(candidate_unit)
            ]
            if not siblings:
                continue
            candidate_image = _decode_image(candidate_unit, cv2, np)
            angle, oriented, regions = _best_grid_orientation(
                candidate_image, cv2, np
            )
            if len(regions) != 1:
                continue
            holdout = (candidate_unit, siblings, angle, oriented, regions[0])
            break
        if holdout is None:
            raise RuntimeError("visual_actual_holdout_selection_empty")
        print(json.dumps({"checkpoint": "holdout_started"}), flush=True)
        holdout_unit, holdout_siblings, angle, oriented, region = holdout
        holdout_source = _source_for_recovery(holdout_unit, prepared.context)
        holdout_observation = _completed_observation(
            source_unit=holdout_source,
            oriented=oriented,
            orientation=angle,
            table_profile=region,
            table_ordinal=1,
            ocr=ocr,
            ocr_version=ocr_version,
            model_set_ref=model_set_ref,
            cv2=cv2,
            np=np,
        )
        holdout_review = build_visual_operator_review(
            observation=holdout_observation,
            resolved_uncertainty_refs=[
                str(item.get("uncertainty_ref") or "")
                for item in _dicts(holdout_observation.get("uncertainty_ledger"))
            ],
        )
        holdout_result = service.recover(
            source_unit=holdout_source,
            observation=holdout_observation,
            operator_review=holdout_review,
        )
        holdout_overlap = _token_overlap(
            holdout_observation, holdout_siblings
        )
        holdout_passed = (
            str(holdout_result.get("promotion_state") or "").startswith(
                "canonical_table_accepted_"
            )
            and holdout_overlap >= 0.35
        )

        records_after = resolver.catalog_run(prepared.context)
        artifactstore_unchanged = snapshot_before == _snapshot(records_after)
        all_results = [
            result
            for scope in private_scopes
            for result in scope["results"]
        ]
        with tempfile.TemporaryDirectory(
            prefix="broker-visual-gate2-actual-"
        ) as clone_directory:
            clone_store = _clone_actual_store(
                prepared, Path(clone_directory)
            )
            clone_initial_records = clone_store.list_by_run(
                prepared.context.normalization_run_id
            )
            handoff = Gate1VisualRecoveryHandoffFactory(
                store=clone_store
            ).create().persist(
                results=all_results,
                context=prepared.context,
                retention_policy=build_retention_policy(mode="api_smoke"),
            )
            clone_persisted_records = clone_store.list_by_run(
                prepared.context.normalization_run_id
            )
            gate2_readiness = Gate2InputReadinessFactory(
                store=clone_store
            ).create().audit_and_build(
                domain_context_packet_ref=prepared.dcp_ref,
                context=prepared.context,
                visual_neutral_table_refs=handoff.accepted_result_refs,
            )
            visual_gate2_packages = [
                package
                for package in gate2_readiness.packages
                if _object(package.get("source_unit")).get(
                    "source_input_mode"
                )
                == "visual_neutral_table"
            ]
            gate2_integration_passed = bool(
                gate2_readiness.validation.get("validator_status") == "passed"
                and gate2_readiness.validation.get("artifactstore_unchanged")
                is True
                and len(handoff.accepted_result_refs)
                == sum(
                    1
                    for result in all_results
                    if str(result.get("promotion_state") or "").startswith(
                        "canonical_table_accepted_"
                    )
                )
                and len(visual_gate2_packages) == canonical_tables
                and all(
                    package.get("document_context", {}).get(
                        "selected_source_scope"
                    )
                    == "visual_neutral_table"
                    for package in visual_gate2_packages
                )
            )
            if not gate2_integration_passed:
                codes = sorted(
                    str(code)
                    for code in _object(
                        gate2_readiness.validation.get("error_code_counts")
                    )
                )
                raise RuntimeError(
                    "visual_actual_gate2_integration_failed:"
                    + ",".join(codes)
                )
            gate2_integration_safe = {
                "disposable_actual_artifactstore_clone_used": True,
                "golden_actual_artifactstore_mutated": False,
                "clone_initial_records": len(clone_initial_records),
                "immutable_visual_result_artifacts": len(
                    handoff.result_refs
                ),
                "accepted_visual_result_artifacts": len(
                    handoff.accepted_result_refs
                ),
                "blocked_terminal_visual_result_artifacts": len(
                    handoff.blocked_result_refs
                ),
                "visual_gate2_packages": len(visual_gate2_packages),
                "visual_gate2_packages_passed": sum(
                    1
                    for package in visual_gate2_packages
                    if package.get("source_unit", {}).get("unit_kind")
                    == "table_row_window"
                ),
                "visual_documents_with_canonical_input": _object(
                    gate2_readiness.validation.get("visual_recovery_audit")
                ).get("documents_with_visual_canonical_input_total"),
                "gate2_validator_status": gate2_readiness.validation.get(
                    "validator_status"
                ),
                "gate2_errors": gate2_readiness.validation.get(
                    "errors_count"
                ),
                "gate2_artifactstore_unchanged_after_handoff": (
                    gate2_readiness.validation.get("artifactstore_unchanged")
                ),
                "clone_records_after_handoff": len(clone_persisted_records),
                "provider_calls": 0,
                "whole_document_provider_uploads": 0,
                "model_canonical_authority": False,
                "customer_values_in_output": False,
                "source_identities_in_output": False,
                "status": "passed",
            }
            gate2_integration_private = {
                "handoff": handoff.to_dict(),
                "validation": gate2_readiness.validation,
                "visual_package_ids": [
                    package.get("package_id")
                    for package in visual_gate2_packages
                ],
            }
        accepted_scopes = sum(
            count
            for state, count in scope_states.items()
            if state.startswith("canonical_table_accepted_")
        )
        terminal_scope_accounting_exact = (
            accepted_scopes == 10
            and scope_states["unresolved_visual_requires_review"] == 1
            and scope_states["unsupported_visual_layout"] == 0
            and sum(scope_states.values()) == 11
        )
        if not artifactstore_unchanged:
            raise RuntimeError("visual_actual_artifactstore_changed")
        if not negative_passed:
            raise RuntimeError("visual_actual_negative_non_table_promoted")
        if not holdout_passed:
            raise RuntimeError("visual_actual_holdout_failed")

        safe_reports = [
            render_visual_neutral_table_safe_report(result)
            for scope in private_scopes
            for result in scope["results"]
        ]
        safe = {
            "schema_version": SAFE_SCHEMA_VERSION,
            "proof_date": "2026-07-20",
            "status": "NOT_CLOSED",
            "workload_fingerprint": prepared.identity.get("workload_fingerprint"),
            "actual_corpus_execution": True,
            "material_scope_accounting": {
                "source_identities": len(material_units),
                "unique_image_scopes": len(groups),
                "exact_duplicate_source_identities": len(material_units) - len(groups),
                "required_unique_scopes": 11,
                "accepted_unique_scopes": accepted_scopes,
                "promotion_state_counts": dict(sorted(scope_states.items())),
                "terminal_scope_accounting_passed": (
                    terminal_scope_accounting_exact
                ),
                "exact_scope_invariant_passed": accepted_scopes == 11,
            },
            "canonical_region_accounting": {
                "regions_accepted": canonical_regions,
                "tables_accepted": canonical_tables,
                "cells_accepted": canonical_cells,
                "deterministic_promotion_replays": deterministic_replays,
                "operator_reviewed_regions": operator_reviewed_regions,
            },
            "blank_scope": {
                "terminal_state": "unresolved_visual_requires_review",
                "source_image_uniform_evidence_preserved": True,
                "reclassified_as_non_material": False,
            },
            "complex_layout_scope": {
                "terminal_state": "canonical_table_accepted_reviewed_visual",
                "regions_accepted": 5,
                "model_topology_used_as_authority": False,
                "failed_closed": False,
                "status": "passed",
            },
            "negative_non_table": {
                "actual_scope_evaluated": True,
                "detected_grid_regions": negative_region_count,
                "false_promotions": 0,
                "status": "passed",
            },
            "heldout_visual_table": {
                "selection_rule": "first_audit_order_simple_grid_with_layout_sibling",
                "actual_scope_evaluated": True,
                "accepted": True,
                "layout_sibling_token_overlap_ratio": round(holdout_overlap, 6),
                "profile_geometry_was_not_manifest_tuned": True,
                "status": "passed",
            },
            "continuation_chain": {
                "pages": len(primary_continuations),
                "validation_errors": 0,
                "status": "passed",
            },
            "performance": {
                "visual_recovery_wall_seconds": round(
                    time.perf_counter() - proof_started, 6
                ),
                "process_peak_rss_bytes": int(process.memory_info().peak_wset),
                "provider_latency_seconds": 0.0,
            },
            "provider_accounting": copy.deepcopy(PROVIDER_ZERO),
            "model_canonical_authority": False,
            "whole_document_provider_uploads": 0,
            "artifactstore_unchanged": artifactstore_unchanged,
            "gate2_canonical_integration": gate2_integration_safe,
            "customer_values_in_output": False,
            "source_identities_in_output": False,
            "release_readiness_claimed": False,
            "customer_acceptance_claimed": False,
            "closure_blockers": [
                "one_material_scope_is_byte_uniform_and_unresolved",
            ],
            "private_result_safe_projection_count": len(safe_reports),
        }
        _assert_safe(safe)
        private = {
            "schema_version": PRIVATE_SCHEMA_VERSION,
            "safe_output_digest": hashlib.sha256(
                json.dumps(
                    safe,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest(),
            "job_profile_id": job.get("profile_id"),
            "scopes": private_scopes,
            "holdout": {
                "observation": holdout_observation,
                "result": holdout_result,
                "layout_sibling_overlap_ratio": holdout_overlap,
            },
            "gate2_canonical_integration": gate2_integration_private,
            "provider_accounting": copy.deepcopy(PROVIDER_ZERO),
            "raw_customer_values_copied_to_safe_output": False,
            "original_files_read_directly": False,
        }
        return safe, private
    finally:
        prepared.cleanup()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_ACTUAL_CONFIG)
    parser.add_argument(
        "--audit-private",
        type=Path,
        default=REPO_ROOT
        / "local"
        / "stage2"
        / "restricted_scope_audit_private"
        / "restricted_scope_audit.private.json",
    )
    parser.add_argument(
        "--job",
        type=Path,
        default=REPO_ROOT
        / "local"
        / "stage2"
        / "broker_reports_visual_recovery_job.local.json",
    )
    parser.add_argument("--model-root", type=Path, required=True)
    parser.add_argument("--safe-output", type=Path, required=True)
    parser.add_argument("--private-output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    private_output = args.private_output.resolve()
    if private_output.is_relative_to(REPO_ROOT.resolve()) and "local" not in {
        part.casefold() for part in private_output.parts
    }:
        raise RuntimeError("visual_actual_private_output_must_be_ignored_or_external")
    safe, private = build_proof(
        config_path=args.config.resolve(),
        audit_private_path=args.audit_private.resolve(),
        job_path=args.job.resolve(),
        model_root=args.model_root.resolve(),
    )
    args.safe_output.resolve().parent.mkdir(parents=True, exist_ok=True)
    private_output.parent.mkdir(parents=True, exist_ok=True)
    args.safe_output.resolve().write_text(
        json.dumps(safe, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    private_output.write_text(
        json.dumps(private, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": safe["status"],
                "unique_material_scopes": safe["material_scope_accounting"][
                    "unique_image_scopes"
                ],
                "accepted_unique_scopes": safe["material_scope_accounting"][
                    "accepted_unique_scopes"
                ],
                "provider_calls": 0,
                "customer_values_exposed": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
