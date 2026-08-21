from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "services" / "broker-reports-gate1-proof" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from live_pdf_table_intake_gate1_operator_proof import (  # noqa: E402
    _create_native_chat,
    _delete_chat,
    _evaluate,
    _run_chat,
)


class _Response:
    def __init__(self, value, status_code: int = 200):
        self._value = value
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"http_{self.status_code}")

    def json(self):
        return self._value


class _Session:
    def __init__(self, *, completion_content: str = "completed"):
        self.posts = []
        self.deletes = []
        self.completion_content = completion_content

    def post(self, url, **kwargs):
        self.posts.append((url, kwargs))
        if url.endswith("/api/v1/chats/new"):
            return _Response({"id": "chat-attested"})
        return _Response(
            {"choices": [{"message": {"content": self.completion_content}}]}
        )

    def delete(self, url, **kwargs):
        self.deletes.append((url, kwargs))
        return _Response({}, status_code=204)


def _uploads():
    return [
        {
            "id": "file-safe",
            "filename": "synthetic.pdf",
            "mime_type": "application/pdf",
            "size": 123,
        }
    ]


def test_operator_uses_server_attested_chat_context_and_terminal_response():
    session = _Session()
    native_chat = _create_native_chat(
        session,
        "https://example.invalid",
        workspace_model_id="broker-reports-ndfl",
        uploads=_uploads(),
    )

    content = _run_chat(
        session,
        "https://example.invalid",
        workspace_model_id="broker-reports-ndfl",
        case_id=native_chat["chat_id"],
        uploads=_uploads(),
        native_chat=native_chat,
        timeout=30,
    )

    assert content == "completed"
    assert native_chat["chat_id"] == "chat-attested"
    completion = session.posts[-1][1]["json"]
    assert completion["parent_id"] == native_chat["user_message_id"]
    assert completion["metadata"]["chat_id"] == "chat-attested"
    assert completion["metadata"]["session_id"] == "chat-attested"
    assert completion["metadata"]["message_id"] == (
        native_chat["assistant_message_id"]
    )
    assert completion["stream"] is False
    prompt = completion["messages"][0]["content"]
    assert "single current Broker Reports pipeline" in prompt
    assert "do not use Knowledge/RAG or legacy recovery routes" in prompt
    assert "or run Gate 2" not in prompt


def test_operator_deletes_the_exact_temporary_chat():
    session = _Session()

    _delete_chat(session, "https://example.invalid", "chat-attested")

    assert session.deletes == [
        ("https://example.invalid/api/v1/chats/chat-attested", {"timeout": 30})
    ]


def test_operator_keeps_gate1_evidence_readable_when_downstream_chat_is_empty():
    session = _Session(completion_content="")
    native_chat = _create_native_chat(
        session,
        "https://example.invalid",
        workspace_model_id="broker-reports-ndfl",
        uploads=_uploads(),
    )

    content = _run_chat(
        session,
        "https://example.invalid",
        workspace_model_id="broker-reports-ndfl",
        case_id=native_chat["chat_id"],
        uploads=_uploads(),
        native_chat=native_chat,
        timeout=30,
    )

    assert content == ""


def test_operator_accepts_current_neutral_canonical_projections():
    remote_evidence = _passing_remote_evidence()

    checks = _evaluate(
        remote_evidence=remote_evidence,
        chat_content="Gate 1 completed",
        uploads=_uploads(),
    )

    assert checks
    assert all(checks.values())


def test_operator_gate1_acceptance_does_not_depend_on_downstream_chat_content():
    remote_evidence = _passing_remote_evidence()

    checks = _evaluate(
        remote_evidence=remote_evidence,
        chat_content="",
        uploads=_uploads(),
    )

    assert checks["downstream_chat_response_private_safe"] is True
    assert all(checks.values())


def test_operator_accepts_validated_source_bound_low_quality_projection():
    remote_evidence = _passing_remote_evidence()
    remote_evidence["table_projections"][0]["safe_metadata"][
        "reconstruction_quality"
    ] = "low"

    checks = _evaluate(
        remote_evidence=remote_evidence,
        chat_content="",
        uploads=_uploads(),
    )

    assert checks["table_projections_match_regions"] is True
    assert all(checks.values())


def test_operator_gate1_acceptance_does_not_depend_on_business_handoff():
    remote_evidence = _passing_remote_evidence()
    remote_evidence["handoff"]["private_source_unit_refs"] = []

    checks = _evaluate(
        remote_evidence=remote_evidence,
        chat_content="",
        uploads=_uploads(),
    )

    assert all(checks.values())


def _passing_remote_evidence():
    table_units = [
        _source_unit("artifact-table-1", "unit-table-1"),
        _source_unit("artifact-table-2", "unit-table-2"),
    ]
    projections = [
        _projection("unit-table-1", rows=2, cells=4),
        _projection("unit-table-2", rows=3, cells=6),
    ]
    return {
        "run_summary": {
            "status": "completed",
            "gate2_boundary_ready": True,
            "detector_qualification": {"exact_model_match": True},
            "horizontal_padding_fraction": 0.08,
            "vertical_padding_fraction": 0.08,
            "rows_columns_cells_inferred": False,
            "financial_semantics_inferred": False,
            "model_values_used_as_source_literals": False,
            "pdfplumber_settings_selected_by_model": False,
            "regions_total": 2,
            "candidates_total": 2,
        },
        "handoff": {
            "private_source_unit_refs": [
                "artifact-table-1",
                "artifact-table-2",
                "artifact-text-1",
            ],
            "pdf_table_candidate_refs": [],
        },
        "attempts": [
            {
                "safe_metadata": {
                    "terminal_status": "validated",
                    "hidden_retry": False,
                    "provider_failover": False,
                }
            }
        ],
        "source_units": table_units,
        "table_projections": projections,
    }


def _source_unit(artifact_id: str, unit_ref: str):
    return {
        "artifact_id": artifact_id,
        "validation_status": "validated",
        "lifecycle_status": "private_ready",
        "safe_metadata": {
            "unit_ref": unit_ref,
            "pdf_unit_type": "pdf_table_candidate_unit",
            "parser_completeness_status": "complete",
            "pdf_text_layer_projection_status": "complete",
            "ocr_vlm_used": False,
            "page_rendering_used_for_extraction": False,
        },
    }


def _projection(source_unit_ref: str, *, rows: int, cells: int):
    return {
        "validation_status": "validated",
        "lifecycle_status": "private_ready",
        "safe_metadata": {
            "source_unit_ref": source_unit_ref,
            "table_origin": "deterministic_neutral_canonical_table",
            "projection_status": "ready",
            "table_candidate_status": "canonical_table_accepted",
            "coverage_status": "complete",
            "reconstruction_quality": "high",
            "row_count": rows,
            "column_count": 2,
            "cell_count": cells,
            "source_value_refs_count": cells,
            "knowledge_rag_used": False,
            "vectorization_performed": False,
        },
    }
