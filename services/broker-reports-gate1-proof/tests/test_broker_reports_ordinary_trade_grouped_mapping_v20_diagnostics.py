from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import replace

import pytest

from broker_reports_gate1.ordinary_trade_grouped_mapping_v20 import (
    ORDINARY_TRADE_GROUPED_MAPPING_V20_RESPONSE_SCHEMA_VERSION,
    OrdinaryTradeGroupedMappingV20AdapterFactory,
)
from broker_reports_gate1.gate2_model_contracts import gate2_provider_profile
from broker_reports_gate1.gate2_provider_adapters import Gate2ProviderAdapterFactory
from broker_reports_gate1.ordinary_trade_mapping_case import (
    MAPPING_RAW_OUTPUT_ARTIFACT_TYPE,
    OrdinaryTradeMappingCaseFactory,
)
from broker_reports_gate1.ordinary_trade_mapping_prompt import (
    StaticOrdinaryTradeMappingPromptResolver,
)
from broker_reports_gate1.artifact_resolver import ArtifactResolver
from broker_reports_gate1.artifact_models import ArtifactStoreError
from broker_reports_gate1.ordinary_trade_mapping_runtime import (
    OrdinaryTradeAutomaticMappingRuntimeFactory,
    _audit_mapping_request_preflight,
    _audit_mapping_request_preflight_invalid,
    _audit_provider_mapping_output_invalid,
)
from broker_reports_gate1.ordinary_trade_semantic_mapping import (
    MAPPING_INPUT_DOCUMENT_OPENING_SCHEMA_VERSION,
    OrdinaryTradeSemanticMappingFactory,
)
from broker_reports_gate1.ordinary_trade_projection import (
    ORDINARY_TRADE_PROJECTION_ARTIFACT_TYPE,
    OrdinaryTradeProjectionFactory,
)

import test_broker_reports_issue312_mapping_case as case_fixtures
import test_broker_reports_issue312_mapping_runtime as runtime_fixtures
import test_broker_reports_ordinary_trade_production_candidate as candidate_fixtures
import broker_reports_gate1.ordinary_trade_semantic_mapping as semantic_module


def _runtime(*, store, client):
    return OrdinaryTradeAutomaticMappingRuntimeFactory(
        store=store,
        read_enabled=True,
        model_client=client,
        mapping_response_adapter=OrdinaryTradeGroupedMappingV20AdapterFactory.create(),
        **runtime_fixtures._mapping_prompt_dependencies(),
        model_id="models/gemini-3.5-flash",
        provider_profile_id="google_gemini",
    ).create()


def _runtime_with_prompt(*, store, client, prompt):
    dependencies = runtime_fixtures._mapping_prompt_dependencies()
    dependencies["mapping_prompt_resolver"] = StaticOrdinaryTradeMappingPromptResolver(
        prompt
    )
    return OrdinaryTradeAutomaticMappingRuntimeFactory(
        store=store,
        read_enabled=True,
        model_client=client,
        mapping_response_adapter=OrdinaryTradeGroupedMappingV20AdapterFactory.create(),
        **dependencies,
        model_id="models/gemini-3.5-flash",
        provider_profile_id="google_gemini",
    ).create()


def _v20_response(*, table: dict, mapping: dict, policy: dict) -> dict:
    decision = case_fixtures._complete(table, mapping)["table_decisions"][0]
    del decision["row_dispositions"]
    decision["row_policy"] = policy
    return {
        "schema_version": ORDINARY_TRADE_GROUPED_MAPPING_V20_RESPONSE_SCHEMA_VERSION,
        "status": "COMPLETE",
        "table_decisions": [decision],
        "clarification": None,
        "message": "complete",
        "explicit_header_source_claims": {
            "schema_version": (
                "broker_reports_ordinary_trade_explicit_header_source_response_v1"
            ),
            "claims": [],
        },
    }


def test_gemini_projection_keeps_strict_default_trade_row_policy() -> None:
    """Gemini must receive the same fixed default disposition as the owner."""

    response_format = OrdinaryTradeGroupedMappingV20AdapterFactory.create().mapping_response_format(
        v13_response_format=OrdinaryTradeSemanticMappingFactory.create().mapping_response_format()
    )
    canonical_policies = [
        variant["properties"]["row_policy"]
        for variant in response_format["json_schema"]["schema"]["properties"][
            "table_decisions"
        ]["items"]["anyOf"]
        if "row_policy" in variant["properties"]
    ]
    adapter = Gate2ProviderAdapterFactory(
        profile=gate2_provider_profile("google_gemini")
    ).create()
    prepared = adapter.prepare_form_data(
        form_data={
            "model": "models/gemini-3.5-flash",
            "messages": [],
            "response_format": response_format,
        },
        response_format=response_format,
    )
    projected_policies = [
        variant["properties"]["row_policy"]
        for variant in prepared.form_data["response_format"]["json_schema"]["schema"][
            "properties"
        ]["table_decisions"]["items"]["anyOf"]
        if "row_policy" in variant["properties"]
    ]

    assert len(canonical_policies) == len(projected_policies) == 2
    for canonical_policy, projected_policy in zip(canonical_policies, projected_policies):
        assert canonical_policy["properties"]["default_disposition"] == {
            "const": "SECURITY_TRADES"
        }
        assert projected_policy["required"] == [
            "default_disposition",
            "exception_rows",
        ]
        assert projected_policy["additionalProperties"] is False
        assert projected_policy["properties"]["default_disposition"] == {
            "enum": ["SECURITY_TRADES"]
        }
        assert projected_policy["properties"]["exception_rows"]["type"] == "array"


def test_revised_prompt_retries_one_prior_invalid_row_policy_attempt(tmp_path) -> None:
    """A published prompt revision permits one fresh strict provider attempt."""

    store, context, document_id, _canonical, _binding, table, mapping = (
        case_fixtures._unknown_case(tmp_path)
    )
    invalid = _v20_response(
        table=table,
        mapping=mapping,
        policy={"default_disposition": "NO_NAMED_CONSUMER", "exception_rows": []},
    )
    initial = asyncio.run(
        _runtime(
            store=store,
            client=runtime_fixtures.BoundaryModelClient([invalid]),
        ).resolve(document_id=document_id, context=context)
    )
    assert initial["status"] == "MAPPING_OUTPUT_INVALID"

    revised_prompt = replace(
        runtime_fixtures._test_mapping_prompt(),
        version="test-v2",
        hash="c" * 64,
        content=(
            "Map {{ordinary_trade_mapping_case_json}} as strict JSON with an "
            "exact row_policy object."
        ),
    )
    revised_client = runtime_fixtures.BoundaryModelClient([invalid])
    retried = asyncio.run(
        _runtime_with_prompt(
            store=store,
            client=revised_client,
            prompt=revised_prompt,
        ).resolve(document_id=document_id, context=context)
    )
    assert retried["status"] == "MAPPING_OUTPUT_INVALID"
    assert retried["provider_calls_this_turn"] == 1
    assert len(revised_client.calls) == 1

    repeated_client = runtime_fixtures.BoundaryModelClient([])
    repeated = asyncio.run(
        _runtime_with_prompt(
            store=store,
            client=repeated_client,
            prompt=revised_prompt,
        ).resolve(document_id=document_id, context=context)
    )
    assert repeated["status"] == "MAPPING_OUTPUT_INVALID"
    assert repeated["provider_calls_this_turn"] == 0
    assert repeated_client.calls == []


def test_v20_full_ordered_columns_complete_and_compile_projection(tmp_path) -> None:
    """A complete V20 column contract reaches the existing projection owner."""

    store, context, document_id, _canonical, _binding, table, mapping = (
        case_fixtures._unknown_case(tmp_path)
    )
    response = _v20_response(
        table=table,
        mapping=mapping,
        policy={"default_disposition": "SECURITY_TRADES", "exception_rows": []},
    )
    client = runtime_fixtures.BoundaryModelClient([response])

    result = asyncio.run(
        _runtime(store=store, client=client).resolve(
            document_id=document_id, context=context
        )
    )

    assert result["status"] == "COMPLETE"
    assert result["provider_calls_this_turn"] == 1
    assert len(client.calls) == 1
    projections = OrdinaryTradeProjectionFactory(store=store, read_enabled=True).create()
    projection = projections.compile_and_save(document_id=document_id, context=context)
    assert projection.artifact_type == ORDINARY_TRADE_PROJECTION_ARTIFACT_TYPE
    projection_payload = projections.read(
        artifact_id=projection.artifact_id, context=context
    )
    assert projection_payload["runtime_records"]
    assert projection_payload["qualified_table_resolutions"][0]["disposition"] == (
        "SECURITY_TRADES"
    )
    assert store.list_by_type(
        context.normalization_run_id, MAPPING_RAW_OUTPUT_ARTIFACT_TYPE
    ) == []


def test_prompt_package_schema_mismatch_stops_before_provider_call(tmp_path) -> None:
    """A wrong input contract is an input failure, never a Gemini attempt."""

    store, context, document_id, _canonical, _binding, _table, _mapping = (
        case_fixtures._unknown_case(tmp_path)
    )
    client = runtime_fixtures.BoundaryModelClient([])
    runtime = OrdinaryTradeAutomaticMappingRuntimeFactory(
        store=store,
        read_enabled=True,
        model_client=client,
        mapping_response_adapter=OrdinaryTradeGroupedMappingV20AdapterFactory.create(),
        **runtime_fixtures._mapping_prompt_dependencies(),
        model_id="models/gemini-3.5-flash",
        provider_profile_id="google_gemini",
        input_schema_version=MAPPING_INPUT_DOCUMENT_OPENING_SCHEMA_VERSION,
    ).create()

    result = asyncio.run(runtime.resolve(document_id=document_id, context=context))

    assert result["status"] == "MAPPING_OUTPUT_INVALID"
    assert result["provider_calls_this_turn"] == 0
    assert client.calls == []
    saved = OrdinaryTradeMappingCaseFactory(
        store=store, read_enabled=True
    ).create().current(document_id=document_id, context=context)[1]
    assert saved["provider_calls_total"] == 0
    assert saved["reason_code"] == (
        "ordinary_trade_mapping_request_prompt_input_schema_mismatch"
    )
    assert store.list_by_type(
        context.normalization_run_id,
        MAPPING_RAW_OUTPUT_ARTIFACT_TYPE,
    ) == []


@pytest.mark.parametrize("malformation", ["omit", "duplicate", "reorder", "invent"])
def test_v20_malformed_columns_stay_terminal_and_never_project(
    tmp_path, malformation: str
) -> None:
    store, context, document_id, _canonical, _binding, table, mapping = (
        case_fixtures._unknown_case(tmp_path)
    )
    response = _v20_response(
        table=table,
        mapping=mapping,
        policy={"default_disposition": "SECURITY_TRADES", "exception_rows": []},
    )
    columns = response["table_decisions"][0]["columns"]
    if malformation == "omit":
        columns.pop()
    elif malformation == "duplicate":
        columns[-1] = dict(columns[0])
    elif malformation == "reorder":
        columns.reverse()
    else:
        columns[0] = {**columns[0], "column": 987654321}

    result = asyncio.run(
        _runtime(
            store=store,
            client=runtime_fixtures.BoundaryModelClient([response]),
        ).resolve(document_id=document_id, context=context)
    )

    assert result["status"] == "MAPPING_OUTPUT_INVALID"
    saved = OrdinaryTradeMappingCaseFactory(
        store=store, read_enabled=True
    ).create().current(document_id=document_id, context=context)[1]
    assert saved["reason_code"] == "ordinary_trade_semantic_mapping_columns_invalid"
    assert store.list_by_type(
        context.normalization_run_id,
        ORDINARY_TRADE_PROJECTION_ARTIFACT_TYPE,
    ) == []
    raw_records = store.list_by_type(
        context.normalization_run_id, MAPPING_RAW_OUTPUT_ARTIFACT_TYPE
    )
    assert len(raw_records) == 1
    raw_record = raw_records[0]
    assert raw_record.visibility == "private_case"
    assert raw_record.storage_backend == "project_artifact_payload"
    assert raw_record.source_file_ref == OrdinaryTradeMappingCaseFactory(
        store=store, read_enabled=True
    ).create().current(document_id=document_id, context=context)[0].source_file_ref
    assert raw_record.retention_policy == OrdinaryTradeMappingCaseFactory(
        store=store, read_enabled=True
    ).create().current(document_id=document_id, context=context)[0].retention_policy
    raw = ArtifactResolver(store).resolve(raw_record.artifact_id, context)["payload"]
    assert raw["schema_version"] == MAPPING_RAW_OUTPUT_ARTIFACT_TYPE
    assert raw["response_content"] == response
    assert response["message"] not in json.dumps(saved, ensure_ascii=False)
    with pytest.raises(ArtifactStoreError) as denied:
        ArtifactResolver(store).resolve(
            raw_record.artifact_id,
            type(context)(
                user_id="other-user",
                normalization_run_id=context.normalization_run_id,
                case_id=context.case_id,
                chat_id=context.chat_id,
                workspace_model_id=context.workspace_model_id,
                allow_private=True,
            ),
        )
    assert denied.value.code == "artifact_access_denied"


def test_mapping_output_invalid_public_state_has_only_closed_failure_reason(
    tmp_path,
) -> None:
    """The user-facing state may diagnose a class, never private mapping data."""

    store, context, document_id, _canonical, _binding, table, mapping = (
        case_fixtures._unknown_case(tmp_path)
    )
    response = _v20_response(
        table=table,
        mapping=mapping,
        policy={"default_disposition": "SECURITY_TRADES", "exception_rows": []},
    )
    response["message"] = "provider-private-value-987654321"
    response["table_decisions"][0]["columns"][0] = {
        **response["table_decisions"][0]["columns"][0],
        "column": 987654321,
    }

    result = asyncio.run(
        _runtime(
            store=store,
            client=runtime_fixtures.BoundaryModelClient([response]),
        ).resolve(document_id=document_id, context=context)
    )

    assert result["status"] == "MAPPING_OUTPUT_INVALID"
    public = OrdinaryTradeMappingCaseFactory(
        store=store, read_enabled=True
    ).create().public_state(document_id=document_id, context=context)
    assert public is not None
    assert public["mapping_failure_reason"] == "mapping_columns_invalid"
    exposed = json.dumps(public, ensure_ascii=False, sort_keys=True)
    assert "ordinary_trade_semantic_mapping_columns_invalid" not in exposed
    assert "provider-private-value-987654321" not in exposed
    assert "987654321" not in exposed


def test_mapping_output_invalid_public_state_uses_generic_closed_fallback(
    tmp_path,
) -> None:
    store, context, document_id, _canonical, _binding, table, mapping = (
        case_fixtures._unknown_case(tmp_path)
    )
    cases = OrdinaryTradeMappingCaseFactory(store=store, read_enabled=True).create()
    cases.save_provider_terminal(
        document_id=document_id,
        context=context,
        status="MAPPING_OUTPUT_INVALID",
        reason_code="provider-message-with-value-987654321",
        message="private terminal message",
        provider_calls_total=0,
    )

    public = cases.public_state(document_id=document_id, context=context)
    assert public is not None
    assert public["mapping_failure_reason"] == "mapping_output_invalid"
    exposed = json.dumps(public, ensure_ascii=False, sort_keys=True)
    assert "provider-message-with-value-987654321" not in exposed
    assert "987654321" not in exposed


def test_persisted_invalid_mapping_logs_one_closed_terminal_receipt(
    tmp_path, caplog
) -> None:
    """The shared persistence owner emits one safe receipt after its terminal write."""

    store, context, document_id, _canonical, _binding, _table, _mapping = (
        case_fixtures._unknown_case(tmp_path)
    )
    caplog.set_level(
        logging.INFO,
        logger="broker_reports_gate1.ordinary_trade_mapping_case",
    )

    saved = OrdinaryTradeMappingCaseFactory(store=store, read_enabled=True).create()
    saved.save_provider_terminal(
        document_id=document_id,
        context=context,
        status="MAPPING_OUTPUT_INVALID",
        reason_code="ordinary_trade_semantic_mapping_columns_invalid",
        message="provider-private-value-987654321",
        provider_calls_total=2,
    )

    receipt = [
        record.message
        for record in caplog.records
        if "broker_reports_mapping_invalid_terminal" in record.message
    ]
    assert receipt == [
        "broker_reports_mapping_invalid_terminal "
        "reason_code=ordinary_trade_semantic_mapping_columns_invalid "
        "revision=1 provider_calls_total=2 raw_response_saved=False"
    ]
    assert "provider-private-value-987654321" not in caplog.text
    assert context.user_id not in caplog.text
    assert document_id not in caplog.text


def test_request_preflight_log_is_body_free(caplog) -> None:
    caplog.set_level(
        logging.INFO,
        logger="broker_reports_gate1.ordinary_trade_mapping_runtime",
    )

    _audit_mapping_request_preflight(
        {
            "package_sha256": "a" * 64,
            "prompt_hash": "b" * 64,
            "tables_total": 2,
            "rows_total": 17,
            "source_literal": "private-value-987654321",
        }
    )

    assert "broker_reports_mapping_request_preflight" in caplog.text
    assert "a" * 64 in caplog.text
    assert "b" * 64 in caplog.text
    assert "private-value-987654321" not in caplog.text


def test_request_preflight_rejection_log_is_closed(caplog) -> None:
    caplog.set_level(
        logging.INFO,
        logger="broker_reports_gate1.ordinary_trade_mapping_runtime",
    )

    _audit_mapping_request_preflight_invalid("private-value-987654321")

    assert "broker_reports_mapping_request_preflight_rejected" in caplog.text
    assert "ordinary_trade_mapping_request_preflight_invalid" in caplog.text
    assert "private-value-987654321" not in caplog.text


def test_provider_mapping_contract_audit_never_logs_untrusted_reason_value(caplog) -> None:
    caplog.set_level(
        logging.INFO,
        logger="broker_reports_gate1.ordinary_trade_mapping_runtime",
    )

    _audit_provider_mapping_output_invalid("provider-private-value-987654321")

    assert "broker_reports_mapping_contract_rejected" in caplog.text
    assert "ordinary_trade_semantic_mapping_output_invalid" in caplog.text
    assert "provider-private-value-987654321" not in caplog.text


@pytest.mark.parametrize(
    ("policy", "category"),
    [
        (
            {"default_disposition": "NO_NAMED_CONSUMER", "exception_rows": []},
            "policy_object_invalid",
        ),
        (
            {
                "default_disposition": "SECURITY_TRADES",
                "exception_rows": [
                    {"row": 987654321, "disposition": "SECURITY_TRADES"}
                ],
            },
            "exception_item_invalid",
        ),
        (
            {
                "default_disposition": "SECURITY_TRADES",
                "exception_rows": [
                    {"row": 3, "disposition": "NO_NAMED_CONSUMER"},
                    {"row": 3, "disposition": "NO_NAMED_CONSUMER"},
                ],
            },
            "exception_rows_not_strictly_ordered",
        ),
        (
            {
                "default_disposition": "SECURITY_TRADES",
                "exception_rows": [
                    {"row": 987654321, "disposition": "NO_NAMED_CONSUMER"}
                ],
            },
            "exception_row_outside_data_rows",
        ),
    ],
)
def test_v20_persists_only_closed_row_policy_shape_category_and_stays_fail_closed(
    tmp_path, policy: dict, category: str
) -> None:
    store, context, document_id, _canonical, _binding, table, mapping = (
        case_fixtures._unknown_case(tmp_path)
    )
    response = _v20_response(table=table, mapping=mapping, policy=policy)

    result = asyncio.run(
        _runtime(
            store=store,
            client=runtime_fixtures.BoundaryModelClient([response]),
        ).resolve(document_id=document_id, context=context)
    )

    assert result["status"] == "MAPPING_OUTPUT_INVALID"
    saved = OrdinaryTradeMappingCaseFactory(
        store=store, read_enabled=True
    ).create().current(document_id=document_id, context=context)[1]
    assert saved["reason_code"] == (
        "ordinary_trade_grouped_mapping_v20_row_policy_invalid:" + category
    )
    # The durable mapping case has control state only: no rejected source row,
    # provider message, or model response is retained for this diagnostic.
    persisted = json.dumps(saved, ensure_ascii=False, sort_keys=True)
    assert "987654321" not in persisted
    assert response["message"] not in persisted
    assert store.list_by_type(
        context.normalization_run_id,
        ORDINARY_TRADE_PROJECTION_ARTIFACT_TYPE,
    ) == []


def test_v20_batch_receipt_keeps_only_safe_row_policy_category(
    tmp_path, monkeypatch
) -> None:
    store, context, document_id, canonical, _binding = (
        case_fixtures._unknown_two_table_case(tmp_path)
    )
    tables = [node for node in canonical["nodes"] if node["node_type"] == "TABLE"]
    monkeypatch.setattr(
        semantic_module,
        "_MAX_CELLS_TOTAL",
        max(len(table["content"]["cells"]) for table in tables),
    )
    responses = []
    for table in tables:
        headers = tuple(
            cell["displayed_value"]
            for cell in sorted(table["content"]["cells"], key=lambda cell: cell["column"])
            if cell["row"] == 1
        )
        responses.append(
            _v20_response(
                table=table,
                mapping=candidate_fixtures._mapping_from_headers(headers),
                policy={
                    "default_disposition": "SECURITY_TRADES",
                    "exception_rows": [
                        {"row": 987654321, "disposition": "NO_NAMED_CONSUMER"}
                    ],
                },
            )
        )
    client = runtime_fixtures.BoundaryModelClient(responses)
    runtime = runtime_fixtures._runtime(store, client)
    runtime._mapping_response_adapter = OrdinaryTradeGroupedMappingV20AdapterFactory.create()

    result = asyncio.run(runtime.resolve(document_id=document_id, context=context))

    assert result["status"] == "MAPPING_OUTPUT_INVALID"
    assert len(client.calls) == 1
    saved = OrdinaryTradeMappingCaseFactory(
        store=store, read_enabled=True
    ).create().current(document_id=document_id, context=context)[1]
    assert saved["reason_code"] == (
        "ordinary_trade_grouped_mapping_v20_row_policy_invalid:"
        "exception_row_outside_data_rows"
    )
    assert "987654321" not in json.dumps(saved, ensure_ascii=False, sort_keys=True)
    assert store.list_by_type(
        context.normalization_run_id,
        ORDINARY_TRADE_PROJECTION_ARTIFACT_TYPE,
    ) == []
