from __future__ import annotations

import copy
import json
from types import SimpleNamespace

import pytest

from broker_reports_gate1.gate2_model_clients import (
    Gate2OpenWebUIStructuredModelClient,
)
from broker_reports_gate1.ordinary_trade_semantic_mapping import (
    MANAGED_DOCUMENT_SEMANTIC_CRITIC_SCHEMA_VERSION,
    MANAGED_DOCUMENT_SEMANTIC_PROPOSAL_SCHEMA_VERSION,
    OrdinaryTradeSemanticMappingError,
    _validate_semantic_review_candidate_binding,
)
from tests.test_broker_reports_managed_semantic_provider_review_v1 import (
    MODEL_ID,
    _provider_builder,
)
from tests.test_broker_reports_managed_semantic_review_contract_v1 import (
    _security_option,
    _trade_observations,
    _trade_pdf,
)
from tests.test_broker_reports_managed_document_candidate_v1 import _page
from tests.test_broker_reports_managed_pdf_document_v2 import (
    _GeminiBoundary,
    _managed_full_source,
    _openwebui_request,
    _route_openwebui_resolver_to_boundary,
)
from tests.test_broker_reports_pdf_layout_slice2 import _pdf_bytes
from tests.test_broker_reports_logical_row_table_recovery import _page_candidate_refs
from tests.test_broker_reports_pdf_document_visual_adjudication import _visual_table


class _ReviewBoundary:
    def __init__(self, *, security: bool, unresolved: bool = False) -> None:
        self.security = security
        self.unresolved = unresolved
        self.calls: list[dict] = []

    def resolve(self, user_id: str):
        return self.complete, SimpleNamespace(id=user_id, role="user")

    def complete(self, *, form_data, **_kwargs):
        package = json.loads(form_data["messages"][1]["content"])
        self.calls.append(copy.deepcopy(form_data))
        if package["phase"] == "managed_semantic_proposal":
            def option_for(table):
                header_literals = {
                    cell["source_literal"]
                    for row in table["rows"]
                    if row["row_role"] == "COLUMN_HEADER"
                    for cell in row["cells"]
                }
                if self.security and {
                    "Trade", "Date", "Side", "Qty", "Price", "Code", "Amount"
                }.issubset(header_literals):
                    option = _security_option()
                    buy_refs = [
                        cell["value_ref"]
                        for row in table["rows"]
                        for cell in row["cells"]
                        if cell["source_literal"] == "BUY"
                    ]
                    assert len(set(buy_refs)) == 1
                    option["side_values"][0]["value_ref"] = buy_refs[0]
                    return option
                return {
                    "disposition": "SAFE_AUXILIARY",
                    "columns": [],
                    "amount_currency_bindings": [],
                    "side_values": [],
                }
            output = {
                "schema_version": MANAGED_DOCUMENT_SEMANTIC_PROPOSAL_SCHEMA_VERSION,
                "evidence_scope_ref": package["evidence_scope_ref"],
                "tables": [
                    {
                        "table_ref": table["table_ref"],
                        "options": [
                            option_for(table),
                            *([{
                                "disposition": "UNSUPPORTED_FINANCIAL",
                                "columns": [],
                                "amount_currency_bindings": [],
                                "side_values": [],
                            }] if self.unresolved else []),
                        ],
                    }
                    for table in package["evidence"]["tables"]
                ],
            }
        else:
            output = {
                "schema_version": MANAGED_DOCUMENT_SEMANTIC_CRITIC_SCHEMA_VERSION,
                "evidence_scope_ref": package["evidence_scope_ref"],
                "proposal_ref": package["proposal_ref"],
                "tables": [
                    {
                        "table_ref": table["table_ref"],
                        "decision": (
                            "UNRESOLVED" if self.unresolved else "SELECT_OPTION"
                        ),
                        "option_ref": (
                            None
                            if self.unresolved
                            else table["options"][0]["option_ref"]
                        ),
                    }
                    for table in package["host_options"]
                ],
            }
        return {
            "id": f"compiled-review-{len(self.calls)}",
            "model": MODEL_ID,
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 20,
                "total_tokens": 120,
            },
            "choices": [
                {"finish_reason": "stop", "message": {"content": output}}
            ],
        }


def _safe_page() -> dict:
    return {
        "texts": [
            (10, 55, "Item"), (110, 55, "Amount"),
            (10, 38, "Opening"), (110, 38, "100"),
            (10, 22, "Closing"), (110, 22, "200"),
        ],
        "vectors": [
            *[f"7 {y} m 200 {y} l S" for y in (15, 30, 46, 63)],
            *[f"{x} 15 m {x} 63 l S" for x in (7, 107, 200)],
        ],
    }


async def _run_trade(
    monkeypatch, boundary: _ReviewBoundary, *, incomplete: bool = False,
    mixed_safe: bool = False,
):
    pdf_bytes = (
        _trade_pdf()
        if incomplete
        else _pdf_bytes([
            _page(title="Trades", first_date="15.01.2025", second_date="16.01.2025"),
            *([_safe_page()] if mixed_safe else []),
        ])
    )
    source_ref = "private_pdf_semantic_compiled_trade"
    payload = _managed_full_source(
        pdf_bytes, source_artifact_ref=source_ref
    ).payloads[0]
    observations = _trade_observations(payload)
    if not incomplete:
        pages = []
        for page_number in range(1, 3 if mixed_safe else 2):
            candidate_refs = _page_candidate_refs(payload, page_number)
            page_ref = next(
                page["page_ref"]
                for page in payload["pdf_text_layer_projection"]["page_inventory"]
                if page["page_number"] == page_number
            )
            candidate_set = set(candidate_refs)
            title_refs = [
                item["word_ref"]
                for item in payload["pdf_text_layer_projection"]["word_inventory"]
                if item["page_ref"] == page_ref and item["word_ref"] not in candidate_set
            ]
            header_width = 7 if page_number == 1 else 2
            header_groups = (
                [candidate_refs[:7], candidate_refs[7:14]]
                if page_number == 1
                else [candidate_refs[:2]]
            )
            body_start = 14 if page_number == 1 else header_width
            pages.append({"tables": [_visual_table(
                payload,
                page_number=page_number,
                title_refs=title_refs,
                header_groups=header_groups,
                body_refs=candidate_refs[body_start:],
            )]})
        observations = {"pages": pages}
    request = _openwebui_request()
    with _GeminiBoundary([observations, observations]) as visual_boundary:
        _route_openwebui_resolver_to_boundary(
            monkeypatch, request=request, boundary=visual_boundary
        )
        monkeypatch.setattr(
            Gate2OpenWebUIStructuredModelClient,
            "_resolve_openwebui_completion_dependencies",
            lambda _self, user_id: boundary.resolve(user_id),
        )
        return await _provider_builder(
            request
        ).build_with_semantic_compiled_document_candidate(
            pdf_bytes,
            tenant_id="tenant",
            artifact_version=1,
            source_artifact_ref=source_ref,
            task_id="semantic_compiled_trade",
            user_scope_sha256="a" * 64,
            proposal_model_id=MODEL_ID,
            critic_model_id=MODEL_ID,
            created_at="2026-08-30T00:00:00Z",
        )


@pytest.mark.asyncio
async def test_raw_trade_review_compiles_and_binds_exact_receipt(monkeypatch) -> None:
    boundary = _ReviewBoundary(security=True)
    result = await _run_trade(monkeypatch, boundary)
    assert (result.status, result.reason_code) == ("CANDIDATE_COMPLETE", None)
    assert result.execution_receipt["provider_submissions"] == 2
    assert len(boundary.calls) == 2
    candidate = result.document_candidate
    binding = result.semantic_review_candidate_binding
    review = result.semantic_review_contract
    assert candidate is not None and binding is not None and review is not None
    assert candidate["document_candidate_status"] == "CANDIDATE_COMPLETE"
    assert candidate["document_record_candidates"]
    assert binding["semantic_review_receipt_sha256"] == review[
        "semantic_review_receipt_sha256"
    ]
    assert binding["document_candidate_sha256"] == candidate[
        "document_candidate_sha256"
    ]
    assert (
        binding["authority_scope"],
        binding["consumer_eligible"],
        binding["independent_derivation_proven"],
        binding["runtime_activation"],
    ) == ("SAME_CALL_COMPOSITION_ONLY", False, False, False)
    _validate_semantic_review_candidate_binding(
        binding=binding,
        semantic_review=review,
        document_candidate=candidate,
    )


@pytest.mark.asyncio
async def test_raw_trade_and_safe_table_complete_atomically(monkeypatch) -> None:
    result = await _run_trade(
        monkeypatch, _ReviewBoundary(security=True), mixed_safe=True
    )
    assert result.status == "CANDIDATE_COMPLETE"
    assert result.execution_receipt["provider_submissions"] == 2
    candidate = result.document_candidate
    assert candidate is not None
    assert sorted(
        table["terminal"] for table in candidate["table_outcomes"]
    ) == ["COMPILED_COMPLETE", "SOURCE_RETAINED_NO_CONSUMER"]
    safe = next(
        item
        for item in candidate["table_outcomes"]
        if item["terminal"] == "SOURCE_RETAINED_NO_CONSUMER"
    )
    assert safe["qualification_binding"] is None
    assert safe["row_compilations"] == []
    assert safe["record_candidates_total"] == 0
    assert candidate["document_record_candidates"]
    forbidden = {"facts", "runtime_records"}

    def keys(value):
        if isinstance(value, dict):
            return set(value) | set().union(*(keys(item) for item in value.values()))
        if isinstance(value, list):
            return set().union(*(keys(item) for item in value), set())
        return set()

    assert not forbidden.intersection(keys(candidate))


@pytest.mark.asyncio
async def test_raw_unresolved_review_never_creates_document_candidate(
    monkeypatch,
) -> None:
    boundary = _ReviewBoundary(security=True, unresolved=True)
    result = await _run_trade(monkeypatch, boundary)
    assert result.status == "CLARIFICATION_REQUIRED"
    assert result.document_candidate is None
    assert result.semantic_review_candidate_binding is None
    assert result.execution_receipt["provider_submissions"] == 2


@pytest.mark.asyncio
async def test_raw_incomplete_trade_blocks_document_atomically(monkeypatch) -> None:
    boundary = _ReviewBoundary(security=True)
    result = await _run_trade(monkeypatch, boundary, incomplete=True)
    assert result.status == "BLOCKED"
    assert result.document_candidate is not None
    assert result.document_candidate["document_record_candidates"] == []
    assert result.document_candidate["blockers"][0]["reason_code"] == (
        "TABLE_RELEVANT_PARTIAL"
    )
    assert result.semantic_review_candidate_binding is not None
    assert result.execution_receipt["provider_submissions"] == 2


@pytest.mark.asyncio
async def test_review_candidate_binding_rejects_stale_candidate_payload_hash(
    monkeypatch,
) -> None:
    result = await _run_trade(monkeypatch, _ReviewBoundary(security=True))
    review = result.semantic_review_contract
    candidate = copy.deepcopy(result.document_candidate)
    binding = result.semantic_review_candidate_binding
    assert review is not None and candidate is not None and binding is not None
    candidate["table_outcomes"][0]["reason_code"] = "forged"
    with pytest.raises(
        OrdinaryTradeSemanticMappingError,
        match="ordinary_trade_managed_document_candidate_hash_invalid",
    ):
        _validate_semantic_review_candidate_binding(
            binding=binding,
            semantic_review=review,
            document_candidate=candidate,
        )
