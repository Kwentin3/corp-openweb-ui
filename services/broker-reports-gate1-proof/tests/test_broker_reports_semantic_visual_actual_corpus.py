from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from broker_reports_gate1.pdf_dual_vlm_canonical_table_contracts import (
    canonical_json_bytes,
)
from broker_reports_gate1.semantic_visual_actual_corpus import (
    DELEGATED_REFERENCE_SCHEMA,
    DELEGATED_REFERENCE_SEAL_SCHEMA,
    EXPECTED_ACCEPTED_TABLES,
    EXPECTED_CORPUS_TABLES,
    SUPPLEMENT_SCHEMA,
    SemanticActualCorpusError,
    build_semantic_source_reference,
)
from broker_reports_gate1.pdf_dual_vlm_runtime import sha256_json
from broker_reports_gate1.semantic_visual_table_contracts import (
    SEMANTIC_TABLE_TRANSCRIPTION_PROMPT,
    semantic_table_transcription_model_view,
    semantic_table_transcription_schema,
)


SERVICE_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = (
    SERVICE_ROOT / "benchmarks" / "semantic_visual_actual_corpus_v1" / "manifest.json"
)


def _inputs() -> tuple[dict, dict, dict]:
    tables = []
    reviews = []
    plans = []
    for index in range(EXPECTED_CORPUS_TABLES):
        candidate_ref = f"candidate_{index}"
        crop_sha256 = f"{index + 1:064x}"
        unsupported = index == EXPECTED_CORPUS_TABLES - 1
        entries = [
            {
                "cell_state": "value",
                "review_status": "confirmed",
                "row_label_text": "Year",
                "visible_value_text": "$ 1,000",
            },
            {
                "cell_state": "empty",
                "review_status": "confirmed",
                "row_label_text": "Year",
                "visible_value_text": "-",
            },
        ]
        tables.append(
            {
                "runtime_candidate_ref": candidate_ref,
                "evaluated_crop_sha256": crop_sha256,
                "entries": entries,
            }
        )
        reviews.append(
            {
                "runtime_candidate_ref": candidate_ref,
                "evaluated_crop_sha256": crop_sha256,
                "disposition": (
                    "unsupported_layout"
                    if unsupported
                    else "assisted_review_candidate"
                ),
            }
        )
        plan = {
            "candidate_ref": candidate_ref,
            "crop_sha256": crop_sha256,
            "disposition": (
                "unsupported_layout"
                if unsupported
                else "accepted_numeric_profile_candidate"
            ),
            "layout_families": ["simple_grid"],
        }
        if unsupported:
            plan["unsupported_reason"] = "long-form prose"
        else:
            plan["row_plan"] = [
                {"literal_labels": ["Header A", "Header B"]},
                {"entry_indices": [0, 1]},
            ]
        plans.append(plan)
    reference = {
        "schema_version": DELEGATED_REFERENCE_SCHEMA,
        "human_reviewed": False,
        "delegated_agent_reviewed": True,
        "customer_accepted": False,
        "lineage": {
            "provider_outputs_used": False,
            "provider_consensus_used": False,
        },
        "literal_reference": {"tables": tables},
        "table_reviews": reviews,
    }
    canonical = canonical_json_bytes(reference)
    seal = {
        "schema_version": DELEGATED_REFERENCE_SEAL_SCHEMA,
        "reference_sha256": hashlib.sha256(canonical).hexdigest(),
        "reference_size_bytes": len(canonical),
        "human_reviewed": False,
        "delegated_agent_reviewed": True,
        "customer_accepted": False,
    }
    supplement = {
        "schema_version": SUPPLEMENT_SCHEMA,
        "frozen_before_provider_execution": True,
        "source_only": True,
        "provider_outputs_used": False,
        "provider_agreement_used": False,
        "customer_acceptance_claimed": False,
        "upstream_delegated_reference_canonical_sha256": seal[
            "reference_sha256"
        ],
        "tables": plans,
    }
    return reference, seal, supplement


def test_builds_eight_semantic_tables_and_keeps_prose_unsupported() -> None:
    reference, seal, supplement = _inputs()
    projected, unsupported = build_semantic_source_reference(
        reference, seal, supplement
    )

    assert len(projected["tables"]) == EXPECTED_ACCEPTED_TABLES
    assert len(unsupported) == 1
    row = projected["tables"][0]["rows"][1]
    assert row == {
        "cells": ["Year", "$", "1,000", "-"],
        "labels": ["Year"],
        "amounts": ["1,000"],
        "markers": ["$", "-"],
    }


def test_rejects_provider_tainted_supplement() -> None:
    reference, seal, supplement = _inputs()
    supplement["provider_outputs_used"] = True

    with pytest.raises(SemanticActualCorpusError):
        build_semantic_source_reference(reference, seal, supplement)


def test_rejects_duplicate_or_missing_entry_projection() -> None:
    reference, seal, supplement = _inputs()
    supplement["tables"][0]["row_plan"][1]["entry_indices"] = [0, 0]

    with pytest.raises(SemanticActualCorpusError) as raised:
        build_semantic_source_reference(reference, seal, supplement)

    assert raised.value.code == "semantic_actual_corpus_entry_coverage_invalid"


def test_rejects_seal_drift() -> None:
    reference, seal, supplement = _inputs()
    drifted = copy.deepcopy(reference)
    drifted["literal_reference"]["tables"][0]["entries"][0][
        "visible_value_text"
    ] = "$ 9,999"

    with pytest.raises(SemanticActualCorpusError) as raised:
        build_semantic_source_reference(drifted, seal, supplement)

    assert raised.value.code == "semantic_actual_corpus_upstream_invalid"


def test_frozen_actual_corpus_manifest_keeps_factory_and_gate_boundary() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert manifest["frozen_before_provider_execution"] is True
    assert len(manifest["cases"]) == EXPECTED_CORPUS_TABLES
    assert (
        sum(
            case["disposition"] == "accepted_numeric_profile_candidate"
            for case in manifest["cases"]
        )
        == EXPECTED_ACCEPTED_TABLES
    )
    assert manifest["provider_contracts"]["gemini"]["executions"] == 18
    assert manifest["provider_contracts"]["openai"]["executions"] == 9
    assert manifest["gate"]["gemini_execution_count"] == 16
    assert manifest["gate"]["amount_fidelity_required"] == 1.0
    assert manifest["gate"]["row_value_binding_required"] == 1.0
    assert manifest["gate"]["hallucinated_amount_count_required"] == 0
    policy = manifest["execution_policy"]
    assert policy["runtime_factory"] == "PdfDualVlmRuntimeFactory.create_for_openwebui"
    assert policy["raster_factory"] == "PdfTableRasterFactory"
    assert policy["provider_merge"] is False
    assert policy["provider_repair"] is False
    assert policy["geometric_metrics"] is False
    contract = manifest["semantic_contract"]
    assert contract["schema_sha256"] == sha256_json(
        semantic_table_transcription_schema()
    )
    assert contract["model_view_sha256"] == sha256_json(
        semantic_table_transcription_model_view()
    )
    assert contract["prompt_sha256"] == hashlib.sha256(
        SEMANTIC_TABLE_TRANSCRIPTION_PROMPT.encode("utf-8")
    ).hexdigest()
