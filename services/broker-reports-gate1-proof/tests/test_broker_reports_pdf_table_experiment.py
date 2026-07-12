from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "local_pdf_table_approach_experiment.py"
SPEC = importlib.util.spec_from_file_location("pdf_table_experiment", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def test_score_penalizes_omission_and_invention() -> None:
    reference = {
        "cells": [["Header", "Amount"], ["Known", "10.00"], ["", "20.00"]],
        "header_rows": 1,
    }
    result = MODULE._score_table(
        reference,
        [["Header", "Amount"], ["Known", ""], ["Invented", "20.00"]],
        1,
    )
    assert result["structure_exact"] is True
    assert result["cells_exact"] == 4
    assert result["cells_total"] == 6
    assert result["numeric_exact"] == 1
    assert result["numeric_total"] == 2
    assert result["omitted_nonempty_cells"] == 1
    assert result["hallucinated_nonempty_cells"] == 1


def test_score_requires_exact_structure_and_header_count() -> None:
    reference = {"cells": [["A", "B"], ["1", "2"]], "header_rows": 1}
    result = MODULE._score_table(reference, [["A", "B", "extra"], ["1", "2", ""]], 0)
    assert result["structure_exact"] is False
    assert result["header_structure_exact"] is False
    assert result["hallucinated_nonempty_cells"] == 1


def test_component_metrics_reports_duplicate_objects_and_text() -> None:
    value = [{"text": "same"}, {"text": "same"}, {"text": "other"}]
    result = MODULE._component_metrics(value)
    assert result["item_count"] == 3
    assert result["unique_object_count"] == 2
    assert result["duplicate_object_count"] == 1
    assert result["text_occurrences"] == 3
    assert result["unique_text_count"] == 2


def test_projection_grid_materializes_only_persisted_values() -> None:
    projection = {
        "projection_status": "ready",
        "row_count": 2,
        "column_count": 2,
        "private_values": [{"value_path_ref": "v1", "normalized_value": "10.00"}],
        "cells": [{"row_ordinal": 2, "column_ordinal": 2, "normalized_private_value_path": "v1"}],
    }
    assert MODULE._projection_grid(projection) == [["", ""], ["", "10.00"]]


def test_hybrid_schema_restricts_candidate_ids() -> None:
    schema = MODULE._hybrid_schema("1:1", ["w0001", "w0002"])
    candidate_schema = (
        schema["properties"]["rows"]["items"]["properties"]["cells"]["items"]
        ["properties"]["candidate_ids"]["items"]
    )
    assert candidate_schema == {"type": "string", "enum": ["w0001", "w0002"]}


def test_local_output_validation_is_fail_closed() -> None:
    raster = {
        "schema_version": MODULE.RASTER_OUTPUT_SCHEMA,
        "table_key": "1:1",
        "rows": [{"cells": ["10.00"], "row_kind": "data", "uncertainty": []}],
        "warnings": [],
    }
    assert MODULE._validate_raster_output(raster, "1:1") is None
    raster["rows"][0]["unexpected"] = "field"
    assert MODULE._validate_raster_output(raster, "1:1") == "row_shape_invalid"

    hybrid = {
        "schema_version": MODULE.HYBRID_OUTPUT_SCHEMA,
        "table_key": "1:1",
        "rows": [{
            "cells": [{"candidate_ids": ["w0001"], "uncertainty": []}],
            "row_kind": "data",
        }],
        "warnings": [],
    }
    assert MODULE._validate_hybrid_output(hybrid, "1:1", {"w0001"}) is None
    hybrid["rows"][0]["cells"][0]["candidate_ids"] = ["outside"]
    assert MODULE._validate_hybrid_output(hybrid, "1:1", {"w0001"}) == "candidate_id_outside_enum"


def test_checkpoint_revalidation_penalizes_invalid_parsed_output() -> None:
    checkpoint = {
        "private": {
            "arm": "raster",
            "table_key": "1:1",
            "parsed": {"unexpected": "shape"},
            "score": {"cells_exact": 1},
        },
        "safe": {
            "arm": "raster",
            "table_key": "1:1",
            "http_status": 200,
            "provider_status": "passed",
            "score": {"cells_exact": 1},
        },
    }
    result = MODULE._revalidate_checkpoint(
        checkpoint,
        references={"1:1": {"cells": [["10.00"]], "header_rows": 0}},
        candidates_by_table={},
    )
    assert result["safe"]["provider_status"] == "failed"
    assert result["safe"]["validation_error"] == "output_identity_mismatch"
    assert result["safe"]["score"]["omitted_nonempty_cells"] == 1


def test_experiment_status_separates_completion_from_call_success() -> None:
    passed = [{"provider_status": "passed"}, {"provider_status": "passed"}]
    with_failure = [{"provider_status": "passed"}, {"provider_status": "failed"}]
    assert MODULE._experiment_status(skip_vlm=False, runs=passed, expected_jobs=2) == "passed"
    assert (
        MODULE._experiment_status(skip_vlm=False, runs=with_failure, expected_jobs=2)
        == "completed_with_failures"
    )
    assert MODULE._experiment_status(skip_vlm=True, runs=[], expected_jobs=2) == "deterministic_only"
    assert MODULE._experiment_status(skip_vlm=True, runs=passed[:1], expected_jobs=2) == "partial_resume"


def test_bbox_iou_uses_installed_pymupdf_rect_api() -> None:
    assert MODULE._bbox_iou([0, 0, 10, 10], [0, 0, 10, 10]) == 1.0
    assert MODULE._bbox_iou([0, 0, 10, 10], [10, 10, 20, 20]) == 0.0


def test_failed_vlm_outcome_is_terminal_and_penalized() -> None:
    result = MODULE._failed_vlm_outcome(
        job={"arm": "raster", "table_key": "1:1", "dpi": 150},
        reference={"cells": [["10.00"]], "header_rows": 0},
        crop={"png_bytes": 10, "width": 20, "height": 30},
        model_id="model",
        exc=TimeoutError(),
    )
    assert result["safe"]["provider_status"] == "failed"
    assert result["safe"]["score"]["omitted_nonempty_cells"] == 1
    assert result["private"]["error_class"] == "TimeoutError"


def test_best_production_word_requires_exact_text_and_unused_ref() -> None:
    words = [
        {"word_ref": "w1", "text": "10.00", "bbox": [0, 0, 5, 5]},
        {"word_ref": "w2", "text": "10.00", "bbox": [10, 0, 15, 5]},
    ]
    result = MODULE._best_production_word(
        text="10.00", bbox=[9, 0, 14, 5], production_words=words, used_refs={"w1"}
    )
    assert result["word_ref"] == "w2"
    assert MODULE._best_production_word(
        text="11.00", bbox=[0, 0, 5, 5], production_words=words, used_refs=set()
    ) is None
