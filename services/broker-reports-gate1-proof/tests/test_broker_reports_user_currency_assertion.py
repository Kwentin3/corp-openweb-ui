from __future__ import annotations

import copy

from broker_reports_gate1.canonical_store import CanonicalReaderFactory
from broker_reports_gate1.gate4_ordinary_trade_candidate import (
    Gate4OrdinaryTradeCandidateRuntime,
)
from broker_reports_gate1.ordinary_trade_mapping_case import (
    OrdinaryTradeMappingCaseFactory,
)
from broker_reports_gate1.ordinary_trade_semantic_compiler import (
    OrdinaryTradeSemanticCompilerFactory,
    compile_schema_mapping,
)

import test_broker_reports_ordinary_trade_production_candidate as candidate


def test_user_currency_is_case_bound_and_never_becomes_pdf_cell_evidence(
    tmp_path,
) -> None:
    headers = list(candidate._ROWS[0])
    currency_index = candidate._ROLES.index("currency")
    headers.pop(currency_index)
    rows = tuple(
        tuple(value for index, value in enumerate(row) if index != currency_index)
        for row in (candidate._ROWS[0], *candidate._ROWS[1:])
    )
    rows = (tuple(headers), *rows[1:])
    store, context = candidate.gate4_fixtures._store_context(tmp_path)
    document_id = "ordinary-trade-user-currency"
    candidate.gate4_fixtures._activate_canonical(
        store=store,
        context=context,
        document_id=document_id,
        artifact_version=1,
        expected_previous_version_id=None,
        table_rows=rows,
    )
    envelope = CanonicalReaderFactory(store=store, read_enabled=True).create().read_active_envelope(
        document_id, context
    )
    table = next(item for item in envelope.artifact["nodes"] if item["node_type"] == "TABLE")
    table_node_id = table["node_id"]
    cases = OrdinaryTradeMappingCaseFactory(store=store, read_enabled=True).create()
    cases.save_mapping_outcome(
        document_id=document_id,
        context=context,
        outcome={
            "status": "CURRENCY_ASSERTION_REQUIRED",
            "message": "Currency required.",
            "question": None,
            "currency_mapping_plan": {
                "response": {"table_decisions": []},
                "execution_metadata": {},
                "table_node_ids": [table_node_id],
            },
        },
        provider_calls_total=1,
    )
    _record, assertion_case = cases.record_user_currency_assertion(
        document_id=document_id,
        context=context,
        currency_code="USD",
        table_node_ids=[table_node_id],
    )
    # A later request may cover the same source table.  It reuses the one
    # case-bound assertion and advances the pending case; it must not append a
    # second assertion merely because the user repeats the visible answer.
    cases.save_mapping_outcome(
        document_id=document_id,
        context=context,
        outcome={
            "status": "CURRENCY_ASSERTION_REQUIRED",
            "message": "Currency still required for a later mapping turn.",
            "question": None,
            "currency_mapping_plan": {
                "response": {"table_decisions": []},
                "execution_metadata": {},
                "table_node_ids": [table_node_id],
            },
        },
        provider_calls_total=1,
    )
    _record, resumed_case = cases.resume_existing_currency_assertion(
        document_id=document_id,
        context=context,
        currency_code="USD",
        table_node_ids=[table_node_id],
    )
    assert resumed_case["status"] == "MAPPING_REQUIRED"
    assert resumed_case["confirmed_understandings"] == assertion_case[
        "confirmed_understandings"
    ]
    decision = assertion_case["confirmed_understandings"][0]["decision"]
    assertion = {
        key: decision[key]
        for key in (
            "schema_version",
            "assertion_id",
            "currency_code",
            "case_binding_sha256",
            "table_node_ids",
        )
    }
    source = envelope.artifact["source"]
    roles = [role for role in candidate._ROLES if role != "currency"]
    mapping = compile_schema_mapping(
        title_literal=None,
        headers=[
            {"column": index, "literal": literal}
            for index, literal in enumerate(headers, start=1)
        ],
        model_columns=[
            {"column": index, "semantic_role": role}
            for index, role in enumerate(roles, start=1)
        ],
        amount_currency_bindings=[
            {
                "amount_column": index,
                "currency_source": {"kind": "user_assertion"},
            }
            for index, role in enumerate(roles, start=1)
            if role in {"gross_amount", "broker_commission", "exchange_commission"}
        ],
        side_values=copy.deepcopy(candidate._QUALIFIED_MAPPING["side_values"]),
        qualification_ref={"qualification_id": "otqual_" + "a" * 32, "receipt_sha256": "b" * 64},
        user_currency_assertion=assertion,
    )
    projection = OrdinaryTradeSemanticCompilerFactory.create().compile(
        canonical=envelope.artifact,
        canonical_binding={
            "document_id": envelope.document_id,
            "canonical_version_id": envelope.canonical_version_id,
            "canonical_root_sha256": envelope.canonical_root_sha256,
            "source_artifact_ref": source["source_artifact_ref"],
            "source_sha256": source["source_sha256"],
        },
        mappings=[],
        scoped_mappings=[{"table_node_id": table_node_id, "mapping": mapping}],
        semantic_mapping_case_ref="art_otmapcase_" + "a" * 32 + "_0001",
    )
    currency_role = next(
        role
        for role in projection["runtime_records"][0]["roles"]
        if role["role"] == "currency"
    )
    assert currency_role["value"] == "USD"
    assert "canonical_cell" not in currency_role["source_binding"]
    assert currency_role["source_binding"]["user_currency_assertion"] == assertion

    class _ProjectionBoundary:
        def current_case(self, *, context):
            return [(type("Record", (), {"artifact_id": "art_projection"})(), projection)]

    facts = Gate4OrdinaryTradeCandidateRuntime(
        projections=_ProjectionBoundary()
    ).list_facts(context=context)
    fact_currency = next(role for role in facts[0]["roles"] if role["role"] == "currency")
    assert fact_currency["source_binding"]["target"] == {
        "kind": "user_assertion",
        "assertion_id": assertion["assertion_id"],
    }
    assert fact_currency["source_binding"]["exact_text"] == "USD"


def test_user_currency_assertion_rejects_other_case_binding(tmp_path) -> None:
    store, context, document_id, _mapping = candidate._case(tmp_path)
    cases = OrdinaryTradeMappingCaseFactory(store=store, read_enabled=True).create()
    table = next(
        item
        for item in CanonicalReaderFactory(store=store, read_enabled=True)
        .create()
        .read_active_envelope(document_id, context)
        .artifact["nodes"]
        if item["node_type"] == "TABLE"
    )
    cases.save_mapping_outcome(
        document_id=document_id,
        context=context,
        outcome={
            "status": "CURRENCY_ASSERTION_REQUIRED",
            "message": "Currency required.",
            "question": None,
            "currency_mapping_plan": {
                "response": {"table_decisions": []},
                "execution_metadata": {},
                "table_node_ids": [table["node_id"]],
            },
        },
        provider_calls_total=1,
    )
    _record, payload = cases.record_user_currency_assertion(
        document_id=document_id,
        context=context,
        currency_code="USD",
        table_node_ids=[table["node_id"]],
    )
    tampered = copy.deepcopy(payload)
    tampered["confirmed_understandings"][0]["decision"]["case_binding_sha256"] = "0" * 64
    tampered["integrity_sha256"] = "0" * 64
    try:
        # The internal validator is intentionally reached only through a stored case.
        cases._next_payload(  # noqa: SLF001
            document_id=document_id,
            context=context,
            prior=None,
            status="MAPPING_REQUIRED",
            message="x",
            question=None,
            pending_candidate=None,
            confirmed_understandings=tampered["confirmed_understandings"],
            qualified_mappings=[],
            qualification_receipts=[],
            table_resolutions=[],
            provider_calls_total=0,
            model_response_sha256=None,
            execution_metadata_sha256=None,
            reason_code=None,
        )
    except Exception as exc:
        assert getattr(exc, "code", None) == "ordinary_trade_mapping_case_confirmation_invalid"
    else:
        raise AssertionError("foreign case binding was accepted")
