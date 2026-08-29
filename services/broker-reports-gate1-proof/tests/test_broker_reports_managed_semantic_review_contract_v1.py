from __future__ import annotations

import copy
from typing import Any

import pytest

from broker_reports_gate1 import ordinary_trade_semantic_mapping as mapping_module
from broker_reports_gate1.ordinary_trade_semantic_mapping import (
    MANAGED_DOCUMENT_SEMANTIC_CRITIC_SCHEMA_VERSION,
    MANAGED_DOCUMENT_SEMANTIC_PROPOSAL_SCHEMA_VERSION,
)
from tests.test_broker_reports_logical_row_table_recovery import (
    _page_candidate_refs,
)
from tests.test_broker_reports_managed_document_semantic_evidence_v1 import (
    TITLE_INJECTION,
    USER_SCOPE_SHA256,
    _builder,
    _injection_continuation_pdf,
    _observations,
    _run as _run_evidence,
)
from tests.test_broker_reports_managed_pdf_document_v2 import (
    _GeminiBoundary,
    _managed_full_source,
    _openwebui_request,
    _route_openwebui_resolver_to_boundary,
)
from tests.test_broker_reports_pdf_document_visual_adjudication import (
    _visual_table,
)
from tests.test_broker_reports_pdf_layout_slice2 import _pdf_bytes


def _proposal(*options: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": MANAGED_DOCUMENT_SEMANTIC_PROPOSAL_SCHEMA_VERSION,
        "evidence_scope_ref": "AUTO_SCOPE",
        "tables": [{"table_ref": "table_1", "options": list(options)}],
    }


def _option(disposition: str) -> dict[str, Any]:
    return {
        "disposition": disposition,
        "columns": [],
        "amount_currency_bindings": [],
        "side_values": [],
    }


def _critic(decision: str, option_ref: str | None) -> dict[str, Any]:
    return {
        "schema_version": MANAGED_DOCUMENT_SEMANTIC_CRITIC_SCHEMA_VERSION,
        "evidence_scope_ref": "AUTO_SCOPE",
        "proposal_ref": "AUTO_PROPOSAL",
        "tables": [
            {
                "table_ref": "table_1",
                "decision": decision,
                "option_ref": option_ref,
            }
        ],
    }


def _trade_pdf() -> bytes:
    xs = (10, 54, 98, 142, 186, 230, 274)
    boundaries = (7, 51, 95, 139, 183, 227, 271, 319)
    return _pdf_bytes(
        [
            {
                "texts": [
                    *[
                        (x, 72, value)
                        for x, value in zip(
                            xs,
                            ("Trade", "Settle", "Oper", "Qty", "Unit", "Curr", "Gross"),
                            strict=True,
                        )
                    ],
                    *[
                        (x, 55, value)
                        for x, value in zip(
                            xs,
                            ("Date", "Date", "Side", "Qty", "Price", "Code", "Amount"),
                            strict=True,
                        )
                    ],
                    *[
                        (x, y, value)
                        for y in (38, 22)
                        for x, value in zip(
                            xs,
                            ("D1", "D2", "BUY", "10", "100", "RUB", "1000"),
                            strict=True,
                        )
                    ],
                ],
                "vectors": [
                    *[f"7 {y} m 319 {y} l S" for y in (15, 30, 46, 63, 82)],
                    *[
                        f"{x} 15 m {x} 82 l S"
                        for x in boundaries
                    ],
                ],
            },
        ]
    )


def _trade_observations(payload: dict[str, Any]) -> dict[str, Any]:
    first = _page_candidate_refs(payload, 1)
    assert len(first) == 28
    return {
        "pages": [
            {
                "tables": [
                    _visual_table(
                        payload,
                        page_number=1,
                        title_refs=[],
                        header_groups=[first[:7], first[7:14]],
                        body_refs=first[14:],
                    )
                ]
            },
        ]
    }


def _security_option(*, swap_date_quantity: bool = False) -> dict[str, Any]:
    roles = [
        "quantity" if swap_date_quantity else "trade_date",
        "asset_name",
        "side",
        "trade_date" if swap_date_quantity else "quantity",
        "unit_price",
        "currency",
        "gross_amount",
    ]
    return {
        "disposition": "SECURITY_TRADES",
        "columns": [
            {
                "column_ref": f"table_1_column_{ordinal}",
                "semantic_role": role,
            }
            for ordinal, role in enumerate(roles, start=1)
        ],
        "amount_currency_bindings": [
            {
                "amount_column_ref": "table_1_column_7",
                "currency_column_ref": "table_1_column_6",
            }
        ],
        "side_values": [
            {"value_ref": "value_16", "normalized_value": "PURCHASE"},
        ],
    }


def _case_material(
    *,
    trade: bool,
    source_ref: str | None,
) -> tuple[bytes, str, dict[str, Any]]:
    pdf_bytes = _trade_pdf() if trade else _injection_continuation_pdf()
    resolved_source_ref = source_ref or (
        "private_pdf_semantic_review_trade"
        if trade
        else "private_pdf_semantic_review"
    )
    payload = _managed_full_source(
        pdf_bytes,
        source_artifact_ref=resolved_source_ref,
    ).payloads[0]
    observations = _trade_observations(payload) if trade else _observations(payload)
    return pdf_bytes, resolved_source_ref, observations


def _bind_raw_responses(
    monkeypatch: pytest.MonkeyPatch,
    *,
    proposal: dict[str, Any],
    critic: dict[str, Any],
    trade: bool = False,
    source_ref: str | None = None,
    task_id: str = "managed_semantic_review",
    user_scope_sha256: str = USER_SCOPE_SHA256,
) -> tuple[dict[str, Any], dict[str, Any]]:
    pdf_bytes, source_ref, observations = _case_material(
        trade=trade,
        source_ref=source_ref,
    )
    request = _openwebui_request()
    with _GeminiBoundary([observations, observations]) as boundary:
        _route_openwebui_resolver_to_boundary(
            monkeypatch,
            request=request,
            boundary=boundary,
        )
        evidence_result = _builder(request).build_with_semantic_evidence(
            pdf_bytes,
            tenant_id="tenant",
            artifact_version=1,
            source_artifact_ref=source_ref,
            task_id=task_id,
            user_scope_sha256=user_scope_sha256,
            created_at="2026-08-30T00:00:00Z",
        )
    evidence = evidence_result.semantic_evidence
    canonical = evidence_result.canonical_result.canonical_artifact
    assert evidence is not None and canonical is not None
    bound_proposal = copy.deepcopy(proposal)
    scope_ref = mapping_module._managed_semantic_evidence_scope_ref(
        evidence["evidence_sha256"]
    )
    bound_proposal["evidence_scope_ref"] = scope_ref
    options, proposal_ref, _proposal_sha256 = (
        mapping_module._managed_semantic_proposal(
            canonical=canonical,
            canonical_binding=evidence["canonical_binding"],
            evidence=evidence,
            evidence_scope_ref=scope_ref,
            response=bound_proposal,
        )
    )
    bound_critic = copy.deepcopy(critic)
    bound_critic["evidence_scope_ref"] = scope_ref
    bound_critic["proposal_ref"] = proposal_ref
    critic_option = bound_critic["tables"][0]["option_ref"]
    if isinstance(critic_option, str) and critic_option.startswith("table_1_option_"):
        ordinal = int(critic_option.rsplit("_", 1)[1]) - 1
        bound_critic["tables"][0]["option_ref"] = options[0]["options"][ordinal][
            "option_ref"
        ]
    return bound_proposal, bound_critic


def _execute_review(
    monkeypatch: pytest.MonkeyPatch,
    *,
    proposal: dict[str, Any],
    critic: dict[str, Any],
    trade: bool = False,
    source_ref: str | None = None,
    task_id: str = "managed_semantic_review",
    user_scope_sha256: str = USER_SCOPE_SHA256,
):
    pdf_bytes, source_ref, observations = _case_material(
        trade=trade,
        source_ref=source_ref,
    )
    request = _openwebui_request()
    with _GeminiBoundary([observations, observations]) as boundary:
        _route_openwebui_resolver_to_boundary(
            monkeypatch,
            request=request,
            boundary=boundary,
        )
        result = _builder(request).build_with_semantic_review_contract(
            pdf_bytes,
            tenant_id="tenant",
            artifact_version=1,
            source_artifact_ref=source_ref,
            task_id=task_id,
            user_scope_sha256=user_scope_sha256,
            proposal_response=proposal,
            critic_response=critic,
            created_at="2026-08-30T00:00:00Z",
        )
        requests = copy.deepcopy(boundary.requests)
    return result, requests


def _run_review(
    monkeypatch: pytest.MonkeyPatch,
    *,
    proposal: dict[str, Any],
    critic: dict[str, Any],
    trade: bool = False,
    source_ref: str | None = None,
    task_id: str = "managed_semantic_review",
    user_scope_sha256: str = USER_SCOPE_SHA256,
):
    proposal, critic = _bind_raw_responses(
        monkeypatch,
        proposal=proposal,
        critic=critic,
        trade=trade,
        source_ref=source_ref,
        task_id=task_id,
        user_scope_sha256=user_scope_sha256,
    )
    return _execute_review(
        monkeypatch,
        proposal=proposal,
        critic=critic,
        trade=trade,
        source_ref=source_ref,
        task_id=task_id,
        user_scope_sha256=user_scope_sha256,
    )


def _recursive_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {
            key for item in value.values() for key in _recursive_keys(item)
        }
    if isinstance(value, list):
        return {key for item in value for key in _recursive_keys(item)}
    return set()


def test_safe_auxiliary_is_reviewed_without_outputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result, requests = _run_review(
        monkeypatch,
        proposal=_proposal(_option("SAFE_AUXILIARY")),
        critic=_critic("SELECT_OPTION", "table_1_option_1"),
    )
    review = result.semantic_review_contract
    assert result.status == "REVIEWED_CANDIDATE"
    assert review is not None
    assert review["record_candidates"] == []
    assert review["consumer_eligible"] is False
    assert review["runtime_activation"] is False
    assert review["publication_authorized"] is False
    assert review["evidence_scope_ref"].startswith("semantic_evidence_scope_")
    assert review["proposal_ref"].startswith("semantic_proposal_")
    assert review["table_options"][0]["options"][0]["option_ref"].startswith(
        "semantic_option_"
    )
    evidence = result.evidence_result.semantic_evidence
    assert evidence is not None
    title_row = evidence["model_evidence"]["tables"][0]["rows"][0]
    assert " ".join(
        cell["source_literal"] for cell in title_row["cells"]
    ) == TITLE_INJECTION
    assert len(requests) == 4
    assert {
        "facts",
        "runtime_records",
        "question",
        "model_client",
        "provider",
    }.isdisjoint(_recursive_keys(review))


@pytest.mark.parametrize(
    ("proposal", "critic", "reason"),
    [
        (
            _proposal(_option("UNSUPPORTED_FINANCIAL")),
            _critic("SELECT_OPTION", "table_1_option_1"),
            "UNSUPPORTED_FINANCIAL_CONTENT",
        ),
        (
            _proposal(_option("SAFE_AUXILIARY")),
            _critic("REJECT_FINANCIAL_RISK", None),
            "FINANCIAL_RISK_REJECTED",
        ),
    ],
)
def test_dividend_or_incomplete_financial_shape_blocks_atomically(
    monkeypatch: pytest.MonkeyPatch,
    proposal: dict[str, Any],
    critic: dict[str, Any],
    reason: str,
) -> None:
    result, _requests = _run_review(
        monkeypatch,
        proposal=proposal,
        critic=critic,
    )
    review = result.semantic_review_contract
    assert result.status == "BLOCKED"
    assert review is not None
    assert review["record_candidates"] == []
    assert review["blockers"] == [{"table_ref": "table_1", "reason_code": reason}]


def test_obvious_mapping_choice_is_selected_by_critic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result, _requests = _run_review(
        monkeypatch,
        proposal=_proposal(
            _security_option(),
            _security_option(swap_date_quantity=True),
        ),
        critic=_critic("SELECT_OPTION", "table_1_option_1"),
        trade=True,
    )
    review = result.semantic_review_contract
    assert result.status == "REVIEWED_CANDIDATE"
    assert review is not None
    assert len(review["table_options"][0]["options"]) == 2
    assert review["table_reviews"][0]["selected_option_ref"] == (
        review["table_options"][0]["options"][0]["option_ref"]
    )
    assert review["record_candidates"] == []


def test_genuine_mapping_ambiguity_requires_clarification_without_question_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result, _requests = _run_review(
        monkeypatch,
        proposal=_proposal(
            _security_option(),
            _security_option(swap_date_quantity=True),
        ),
        critic=_critic("UNRESOLVED", None),
        trade=True,
    )
    review = result.semantic_review_contract
    assert result.status == "CLARIFICATION_REQUIRED"
    assert review is not None
    assert review["record_candidates"] == []
    assert review["unresolved"] == [
        {"table_ref": "table_1", "reason_code": "SEMANTIC_REVIEW_UNRESOLVED"}
    ]
    assert "question" not in _recursive_keys(review)


@pytest.mark.parametrize(
    "mutation",
    ["foreign_table", "foreign_option", "stale_refs", "extra"],
)
def test_foreign_stale_or_extra_model_fields_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    proposal = _proposal(_option("SAFE_AUXILIARY"))
    critic = _critic("SELECT_OPTION", "table_1_option_1")
    proposal, critic = _bind_raw_responses(
        monkeypatch,
        proposal=proposal,
        critic=critic,
    )
    if mutation == "foreign_table":
        proposal["tables"][0]["table_ref"] = "table_foreign"
    elif mutation == "foreign_option":
        critic["tables"][0]["option_ref"] = "semantic_option_foreign"
    elif mutation == "stale_refs":
        proposal["evidence_scope_ref"] = "semantic_evidence_scope_stale"
    else:
        proposal["tables"][0]["options"][0]["message"] = "trust me"
    result, _requests = _execute_review(
        monkeypatch,
        proposal=proposal,
        critic=critic,
    )
    assert result.status == "BLOCKED"
    assert result.semantic_review_contract is None
    assert result.reason_code == "SEMANTIC_REVIEW_RESPONSE_INVALID"


@pytest.mark.parametrize("foreign_kind", ["document", "user_scope"])
def test_same_shape_foreign_scope_cannot_replay_both_raw_phases(
    monkeypatch: pytest.MonkeyPatch,
    foreign_kind: str,
) -> None:
    source_ref = "private_pdf_semantic_scope_origin"
    proposal, critic = _bind_raw_responses(
        monkeypatch,
        proposal=_proposal(_option("SAFE_AUXILIARY")),
        critic=_critic("SELECT_OPTION", "table_1_option_1"),
        source_ref=source_ref,
    )
    result, _requests = _execute_review(
        monkeypatch,
        proposal=proposal,
        critic=critic,
        source_ref=(
            "private_pdf_semantic_scope_foreign"
            if foreign_kind == "document"
            else source_ref
        ),
        user_scope_sha256=(
            "e" * 64 if foreign_kind == "user_scope" else USER_SCOPE_SHA256
        ),
    )
    assert result.status == "BLOCKED"
    assert result.semantic_review_contract is None
    assert result.reason_code == "SEMANTIC_REVIEW_RESPONSE_INVALID"


def test_changed_proposal_rejects_stale_critic_binding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    proposal, critic = _bind_raw_responses(
        monkeypatch,
        proposal=_proposal(_option("SAFE_AUXILIARY")),
        critic=_critic("SELECT_OPTION", "table_1_option_1"),
    )
    proposal["tables"][0]["options"][0][
        "disposition"
    ] = "UNSUPPORTED_FINANCIAL"
    result, _requests = _execute_review(
        monkeypatch,
        proposal=proposal,
        critic=critic,
    )
    assert result.status == "BLOCKED"
    assert result.semantic_review_contract is None
    assert result.reason_code == "SEMANTIC_REVIEW_RESPONSE_INVALID"


def test_unresolved_requires_two_distinct_options(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result, _requests = _run_review(
        monkeypatch,
        proposal=_proposal(_option("SAFE_AUXILIARY")),
        critic=_critic("UNRESOLVED", None),
    )
    assert result.status == "BLOCKED"
    assert result.semantic_review_contract is None
    assert result.reason_code == "SEMANTIC_REVIEW_RESPONSE_INVALID"


def test_review_route_preserves_pr337_evidence_result_exactly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    evidence_result, _requests = _run_evidence(
        monkeypatch,
        with_evidence=True,
    )
    monkeypatch.undo()
    review_result, _requests = _run_review(
        monkeypatch,
        proposal=_proposal(_option("SAFE_AUXILIARY")),
        critic=_critic("SELECT_OPTION", "table_1_option_1"),
        source_ref="private_pdf_managed_semantic_evidence",
        task_id="managed_semantic_evidence",
    )
    nested = review_result.evidence_result
    assert nested.canonical_result.canonical_artifact == (
        evidence_result.canonical_result.canonical_artifact
    )
    assert nested.semantic_evidence == evidence_result.semantic_evidence
    assert nested.canonical_result.safe_diagnostics == (
        evidence_result.canonical_result.safe_diagnostics
    )
