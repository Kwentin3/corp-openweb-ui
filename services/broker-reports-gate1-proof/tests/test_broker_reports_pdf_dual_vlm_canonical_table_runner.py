from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "scripts"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SCRIPT_DIR))

import pdf_dual_vlm_canonical_table_contracts as CONTRACTS  # noqa: E402


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPT_DIR / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RUNNER = _load(
    "local_pdf_dual_vlm_canonical_table_run_test",
    "local_pdf_dual_vlm_canonical_table_run.py",
)
SCORER = _load(
    "local_pdf_dual_vlm_canonical_table_score_test",
    "local_pdf_dual_vlm_canonical_table_score.py",
)


def _table(table_id: str = "fixture") -> dict[str, object]:
    return {
        "schema_version": CONTRACTS.CANONICAL_TABLE_SCHEMA_VERSION,
        "table_id": table_id,
        "row_count": 1,
        "column_count": 1,
        "cells": [
            {
                "row_index": 0,
                "column_index": 0,
                "row_span": 1,
                "column_span": 1,
                "content_state": "present",
                "source_text": "1,000",
            }
        ],
    }


class BoundaryProvider:
    def __init__(self, output: dict[str, object]) -> None:
        self.output = output
        self.count_calls = 0
        self.invoke_calls = 0

    def count_tokens(self, **kwargs: object) -> dict[str, object]:
        self.count_calls += 1
        schema = kwargs["output_schema"]
        return {
            "total_tokens": 100,
            "canonical_schema_hash": CONTRACTS.sha256_json(schema),
            "adapted_schema_hash": CONTRACTS.sha256_json(schema),
            "schema_transform_count": 0,
        }

    def invoke(self, **kwargs: object) -> dict[str, object]:
        self.invoke_calls += 1
        return {
            "attempt": {
                "attempt_number": kwargs["attempt_number"],
                "attempt_lineage": kwargs["attempt_lineage"],
                "hidden_retry": False,
                "provider_failover": False,
                "crop_sha256": kwargs["crop_sha256"],
                "model_view_hash": CONTRACTS.sha256_json(kwargs["model_view"]),
                "terminal_failure_class": None,
            },
            "text": CONTRACTS.canonical_json_bytes(self.output).decode("utf-8"),
            "json_output": copy.deepcopy(self.output),
            "response_bytes": 500,
        }


def test_global_padding_is_exactly_eight_percent_per_page_side() -> None:
    detected = [0.10, 0.20, 0.80, 0.90]

    padded = RUNNER._apply_padding(
        detected, CONTRACTS.GLOBAL_PADDING_FRACTION_PER_PAGE_SIDE
    )

    assert detected == [0.10, 0.20, 0.80, 0.90]
    assert padded == [0.02, 0.12, 0.88, 0.98]


def test_manifest_freezes_neutral_contract_and_real_truth_boundary() -> None:
    manifest = json.loads(
        (
            ROOT / "benchmarks" / "pdf_dual_vlm_canonical_table_v1" / "manifest.json"
        ).read_text(encoding="utf-8")
    )

    assert manifest["padding_policy"]["fraction_per_page_side"] == 0.08
    assert manifest["padding_policy"]["global_for_every_table"] is True
    assert manifest["padding_policy"]["per_table_tuning"] is False
    assert manifest["canonical_contract"]["coordinates_allowed"] is False
    assert manifest["canonical_contract"]["cell_roles_allowed"] is False
    assert manifest["canonical_contract"]["content_types_allowed"] is False
    assert (
        manifest["canonical_contract"]["prompt_contract_version"]
        == "dual_vlm_canonical_table_normalizer_v4"
    )
    assert manifest["corpora"]["real_pdf"]["accuracy_scoring_allowed"] is False
    assert (
        manifest["corpora"]["real_pdf"]["historical_reference_human_reviewed"] is False
    )


def test_provider_operation_has_one_preflight_and_one_generate_call() -> None:
    png = b"immutable-table-crop"
    output = _table()
    provider = BoundaryProvider(output)
    view = CONTRACTS.normalizer_model_view(
        crop_sha256=RUNNER.hashlib.sha256(png).hexdigest(),
        table_id="fixture",
        image_width=100,
        image_height=50,
    )

    operation = RUNNER._provider_operation(
        provider=provider,
        provider_name="gemini",
        task_id="task",
        model_view=view,
        output_schema=CONTRACTS.canonical_table_schema(),
        png_bytes=png,
        table_id="fixture",
    )

    assert provider.count_calls == 1
    assert provider.invoke_calls == 1
    assert operation["terminal_status"] == "completed"
    assert operation["attempt"]["attempt_number"] == 1
    assert operation["attempt"]["attempt_lineage"] == []
    assert operation["hidden_retry"] is False
    assert operation["provider_failover"] is False


def test_contract_failure_is_terminal_and_not_repaired() -> None:
    png = b"immutable-table-crop"
    malformed = _table()
    malformed["cells"] = []
    provider = BoundaryProvider(malformed)
    view = CONTRACTS.normalizer_model_view(
        crop_sha256=RUNNER.hashlib.sha256(png).hexdigest(),
        table_id="fixture",
        image_width=100,
        image_height=50,
    )

    operation = RUNNER._provider_operation(
        provider=provider,
        provider_name="openai",
        task_id="task",
        model_view=view,
        output_schema=CONTRACTS.canonical_table_schema(),
        png_bytes=png,
        table_id="fixture",
    )

    assert operation["terminal_status"] == "terminal_contract_failure"
    assert operation["failure_code"] == "canonical_table_cells_invalid"
    assert operation["json_output"]["cells"] == []


def test_controlled_false_consensus_is_not_accepted() -> None:
    reference = _table("controlled_1")
    wrong = copy.deepcopy(reference)
    wrong["cells"][0]["source_text"] = "9,999"
    crop = {
        "case_id": "controlled_1",
        "table_id": "controlled_1",
        "corpus": "controlled_exact_ground_truth",
        "category_tags": [],
        "crop_path": "crops/example.png",
        "crop_sha256": "f" * 64,
        "detected_bbox_normalized": [0.1, 0.1, 0.9, 0.9],
        "padded_crop_bbox_normalized": [0.02, 0.02, 0.98, 0.98],
        "padding_fraction_per_page_side": 0.08,
        "byte_identical_reproduction": True,
    }
    providers = {
        provider: {
            "terminal_status": "completed",
            "failure_code": None,
            "json_output": copy.deepcopy(wrong),
        }
        for provider in ("gemini", "openai")
    }

    result = SCORER._score_crop(
        crop=crop,
        providers=providers,
        reference_by_id={"controlled_1": {"table": reference}},
    )

    assert result["consensus"]["FULL_TABLE_CONSENSUS"] is True
    assert result["outcome"] == "false_consensus"


def test_real_pdf_result_never_receives_accuracy_without_reviewed_truth() -> None:
    crop = {
        "case_id": "real_1",
        "table_id": "real_1:table_0",
        "corpus": "real_pdf_unreviewed",
        "category_tags": [],
        "crop_path": "crops/example.png",
        "crop_sha256": "f" * 64,
        "detected_bbox_normalized": [0.1, 0.1, 0.9, 0.9],
        "padded_crop_bbox_normalized": [0.02, 0.02, 0.98, 0.98],
        "padding_fraction_per_page_side": 0.08,
        "byte_identical_reproduction": True,
    }
    table = _table("real_1:table_0")
    providers = {
        provider: {
            "terminal_status": "completed",
            "failure_code": None,
            "json_output": copy.deepcopy(table),
        }
        for provider in ("gemini", "openai")
    }

    result = SCORER._score_crop(
        crop=crop,
        providers=providers,
        reference_by_id={},
    )

    assert result["accuracy_scored"] is False
    assert result["provider_accuracy"] is None
    assert result["outcome"] == "unreviewed_real_pdf_diagnostic"


def test_repeatability_metric_counts_changed_canonical_outputs() -> None:
    records = [
        {
            "table_id": "real_1:table_0",
            "corpus": "real_pdf_unreviewed",
            "providers": {
                "gemini": {
                    "previous_status": "completed",
                    "current_status": "completed",
                    "status_stable": True,
                    "canonical_output_repeatable": True,
                }
            },
        },
        {
            "table_id": "real_2:table_0",
            "corpus": "real_pdf_unreviewed",
            "providers": {
                "gemini": {
                    "previous_status": "completed",
                    "current_status": "completed",
                    "status_stable": True,
                    "canonical_output_repeatable": False,
                }
            },
        },
    ]

    metric = SCORER._repeatability_aggregate(
        records,
        provider="gemini",
        corpus="real_pdf_unreviewed",
    )

    assert metric["canonical_output_repeatable_tables"] == 1
    assert metric["canonical_output_repeatability_rate"] == 0.5
    assert metric["changed_tables"] == ["real_2:table_0"]
