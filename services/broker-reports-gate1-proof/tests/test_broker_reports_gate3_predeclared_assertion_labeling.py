from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from broker_reports_gate1.gate2_model_clients import (
    Gate2StructuredModelClientFactory,
)
from broker_reports_gate1.gate2_model_contracts import (
    Gate2StructuredModelClientConfig,
)
from broker_reports_gate1.gate2_model_requests import (
    GATE3_BOUNDED_LABELING_REQUEST_PROFILE,
)
from broker_reports_gate1.gate3_bounded_labeling import (
    FACTORY_REQUIRED,
    FORBIDDEN,
    GATE3_PREDECLARED_ASSERTION_INSTRUCTION,
    GATE3_PREDECLARED_ASSERTION_RESPONSE_SCHEMA_SHA256,
    Gate3BoundedLabelingFactory,
)
from broker_reports_gate1.gate3_financial_label_dictionary import (
    GATE3_DICTIONARY_V2_1_VERSION,
)


MODEL_ID = "models/gemini-3.5-flash"
PACKAGE_ROOT = Path(__file__).resolve().parents[1] / "broker_reports_gate1"
REPO_ROOT = Path(__file__).resolve().parents[3]


def test_predeclared_assertion_batch_reuses_row_aliases_and_restores_targets() -> None:
    response = {
        "schema_version": (
            "broker_reports_gate3_predeclared_assertion_labeling_response_v1"
        ),
        "classifications": [
            {
                "assertion_id": "t001",
                "financial_types": ["DIVIDEND_INCOME"],
            },
            {"assertion_id": "t003", "financial_types": ["UNMAPPED"]},
        ],
    }
    client, captured = _client(response)
    owner = Gate3BoundedLabelingFactory(
        store=None,
        read_enabled=False,
        model_client=client,
        model_id=MODEL_ID,
        dictionary_version=GATE3_DICTIONARY_V2_1_VERSION,
    )

    attempt = asyncio.run(
        owner.create_from_predeclared_assertions(chunk=_chunk())
    )

    assert attempt.validation_status == "validated"
    assert attempt.validation_error_code is None
    assert [
        item["assertion_id"] for item in attempt.assertion_envelope["assertions"]
    ] == ["t001", "t003"]
    assert all(
        item["assertion_id"] == item["source_target_ref"]
        for item in attempt.assertion_envelope["assertions"]
    )
    assert "[t001]" not in attempt.assertion_envelope["shared_structural_context"]
    assert "[t003]" not in attempt.assertion_envelope["shared_structural_context"]
    assert attempt.validated_output == {
        "schema_version": (
            "broker_reports_gate3_predeclared_assertion_classification_v1"
        ),
        "canonical_binding": {
            "document_id": "document-1",
            "canonical_version_id": "canonical-1",
        },
        "dictionary_identity": {
            "dictionary_id": "broker-reports-financial-labels",
            "semantic_version": GATE3_DICTIONARY_V2_1_VERSION,
        },
        "instruction_identity": {
            "instruction_id": (
                "broker-reports-predeclared-atomic-assertion-labeling"
            ),
            "semantic_version": "0.1.0",
        },
        "model_identity": {"model_id": MODEL_ID},
        "classifications": [
            {
                "assertion_id": "t001",
                "source_target": {
                    "kind": "table_row",
                    "node_id": "table-1",
                    "row": 1,
                },
                "financial_types": ["DIVIDEND_INCOME"],
            },
            {
                "assertion_id": "t003",
                "source_target": {
                    "kind": "table_row",
                    "node_id": "table-1",
                    "row": 2,
                },
                "financial_types": ["UNMAPPED"],
            },
        ],
        "validation_status": "validated",
        "target_discovery_by_model": False,
    }
    assert attempt.metrics["assertions_predeclared"] == 2
    assert attempt.metrics["assertions_validated"] == 2
    assert attempt.metrics["unknown_assertion_ids"] == 0
    assert attempt.metrics["duplicate_assertion_ids"] == 0
    assert attempt.metrics["invented_source_objects"] == 0
    assert len(captured) == 1
    assert [item["role"] for item in captured[0]["messages"]] == [
        "system",
        "user",
        "user",
    ]
    assert captured[0]["messages"][0]["content"] == (
        GATE3_PREDECLARED_ASSERTION_INSTRUCTION
    )
    assert client.qualification_lifecycle_snapshot()["provider_submissions_total"] == 1


@pytest.mark.parametrize(
    ("classifications", "error_code"),
    [
        (
            [{"assertion_id": "t001", "financial_types": ["DIVIDEND_INCOME"]}],
            "gate3_predeclared_assertion_coverage_invalid",
        ),
        (
            [
                {"assertion_id": "t001", "financial_types": ["DIVIDEND_INCOME"]},
                {"assertion_id": "t999", "financial_types": ["UNMAPPED"]},
            ],
            "gate3_predeclared_assertion_id_unknown",
        ),
        (
            [
                {"assertion_id": "t001", "financial_types": ["DIVIDEND_INCOME"]},
                {"assertion_id": "t001", "financial_types": ["UNMAPPED"]},
            ],
            "gate3_predeclared_assertion_id_duplicate",
        ),
        (
            [
                {"assertion_id": "t003", "financial_types": ["UNMAPPED"]},
                {"assertion_id": "t001", "financial_types": ["DIVIDEND_INCOME"]},
            ],
            "gate3_predeclared_assertion_order_invalid",
        ),
        (
            [
                {"assertion_id": "t001", "financial_types": ["UNMAPPED", "DIVIDEND_INCOME"]},
                {"assertion_id": "t003", "financial_types": ["UNMAPPED"]},
            ],
            "gate3_predeclared_assertion_response_contract_invalid",
        ),
    ],
)
def test_predeclared_assertion_validation_fails_closed(
    classifications: list[dict],
    error_code: str,
) -> None:
    client, _captured = _client(
        {
            "schema_version": (
                "broker_reports_gate3_predeclared_assertion_labeling_response_v1"
            ),
            "classifications": classifications,
        }
    )
    attempt = asyncio.run(
        Gate3BoundedLabelingFactory(
            store=None,
            read_enabled=False,
            model_client=client,
            model_id=MODEL_ID,
            dictionary_version=GATE3_DICTIONARY_V2_1_VERSION,
        ).create_from_predeclared_assertions(chunk=_chunk())
    )

    assert attempt.validation_status == "rejected"
    assert attempt.validation_error_code == error_code
    assert attempt.validated_output is None


def test_predeclared_assertion_schema_and_factory_antidrift_are_exact() -> None:
    package_schema = (
        PACKAGE_ROOT / "gate3_predeclared_assertion_labeling_response.v1.schema.json"
    )
    contract_schema = (
        REPO_ROOT
        / "docs/stage2/contracts/"
        "BROKER_REPORTS_GATE3_PREDECLARED_ASSERTION_LABELING_RESPONSE.v1.schema.json"
    )
    assert package_schema.read_bytes() == contract_schema.read_bytes()
    assert hashlib.sha256(package_schema.read_bytes()).hexdigest() == (
        GATE3_PREDECLARED_ASSERTION_RESPONSE_SCHEMA_SHA256
    )
    source = inspect.getsource(
        Gate3BoundedLabelingFactory.create_from_predeclared_assertions
    )
    prepare_source = inspect.getsource(
        Gate3BoundedLabelingFactory.prepare_predeclared_assertion_batch
    )
    assert "create_from_predeclared_assertions" in FACTORY_REQUIRED
    assert "prepare_predeclared_assertion_batch" in source
    assert "_projection_from_structural_chunk" in prepare_source
    assert "Gate3FinancialLabelDictionaryFactory" in prepare_source
    assert "label_gate3_once" in source
    assert "infer labels" in FORBIDDEN
    for forbidden in (
        "Gate3RoleLabelingFactory",
        "Gate3FinancialAnnotationsPersistenceFactory",
        "Gate4",
        "Gate5",
    ):
        assert forbidden not in source


def _chunk() -> dict:
    content = (
        "# Synthetic table\n\n"
        "| row | column 1 |\n"
        "| --- | --- |\n"
        "| [t001] 1 | [t002] Cash dividend |\n"
        "| [t003] 2 | [t004] Heading only |\n"
    )
    mappings = [
        {
            "target_alias": "t001",
            "canonical_target": {
                "kind": "table_row",
                "node_id": "table-1",
                "row": 1,
            },
        },
        {
            "target_alias": "t002",
            "canonical_target": {
                "kind": "table_cell",
                "node_id": "table-1",
                "row": 1,
                "column": 1,
            },
        },
        {
            "target_alias": "t003",
            "canonical_target": {
                "kind": "table_row",
                "node_id": "table-1",
                "row": 2,
            },
        },
        {
            "target_alias": "t004",
            "canonical_target": {
                "kind": "table_cell",
                "node_id": "table-1",
                "row": 2,
                "column": 1,
            },
        },
    ]
    return {
        "chunk_id": "g3chunk_synthetic",
        "ordinal": 1,
        "canonical_binding": {
            "document_id": "document-1",
            "canonical_version_id": "canonical-1",
        },
        "structural_kind": "whole_table",
        "structural_scope": {
            "container_refs": [],
            "node_refs": ["table-1"],
            "row_start": 1,
            "row_end": 2,
        },
        "context_policy": {
            "context_only_target_aliases": 0,
            "data_row_overlap": 0,
            "ancestor_headings": 0,
            "repeated_table_header": False,
            "repeated_table_notes": False,
        },
        "model_view": {"media_type": "text/markdown", "content": content},
        "target_mappings": mappings,
        "metrics": {
            "model_view_chars": len(content),
            "target_count": len(mappings),
            "context_overhead_chars": 0,
        },
    }


def _client(response: dict):
    captured: list[dict] = []

    def complete(*, form_data, **_kwargs):
        captured.append(json.loads(json.dumps(form_data, ensure_ascii=False)))
        return {
            "id": "gate3-predeclared-local-seam-response",
            "model": MODEL_ID,
            "choices": [
                {
                    "message": {
                        "content": json.dumps(response, ensure_ascii=False),
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 20,
                "total_tokens": 120,
            },
        }

    user = SimpleNamespace(id="gate3-user")
    client = Gate2StructuredModelClientFactory(
        config=Gate2StructuredModelClientConfig(
            request_profile=GATE3_BOUNDED_LABELING_REQUEST_PROFILE,
            provider_profile_id="google_gemini",
        ),
        user=user,
        request=SimpleNamespace(),
        completion_resolver=lambda _user_id: (complete, user),
    ).create()
    return client, captured
