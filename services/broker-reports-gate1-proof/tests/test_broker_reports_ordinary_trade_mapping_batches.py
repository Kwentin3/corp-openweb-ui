from __future__ import annotations

import copy
import hashlib
import json
import asyncio
import logging
import sys
from dataclasses import replace
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from broker_reports_gate1.ordinary_trade_semantic_mapping import (
    MAPPING_INPUT_DOCUMENT_OPENING_SCHEMA_VERSION,
    OrdinaryTradeSemanticMappingError,
    OrdinaryTradeSemanticMappingFactory,
)

import test_broker_reports_issue312_mapping_case as case_fixtures
import test_broker_reports_ordinary_trade_production_candidate as candidate_fixtures
import test_broker_reports_issue312_mapping_runtime as runtime_fixtures
import broker_reports_gate1.ordinary_trade_semantic_mapping as semantic_module
from broker_reports_gate1.ordinary_trade_mapping_case import OrdinaryTradeMappingCaseFactory
from broker_reports_gate1.ordinary_trade_mapping_case import OrdinaryTradeMappingCaseError
from broker_reports_gate1.ordinary_trade_mapping_case import MAPPING_RAW_OUTPUT_ARTIFACT_TYPE
from broker_reports_gate1.ordinary_trade_mapping_case import (
    MAPPING_RAW_OUTPUT_REFERENCE_SCHEMA_VERSION,
)
from broker_reports_gate1.artifact_resolver import ArtifactResolver
from broker_reports_gate1.artifact_models import ArtifactStoreError
from broker_reports_gate1.ordinary_trade_grouped_mapping_v14 import OrdinaryTradeGroupedMappingV14AdapterFactory
from openwebui_actions.broker_reports_gate1_pipe import Pipe
from broker_reports_gate1.ordinary_trade_mapping_prompt import (
    ORDINARY_TRADE_MAPPING_V16_COMPACT_RESPONSE_SCHEMA_VERSION,
    ORDINARY_TRADE_MAPPING_V16_PROMPT_COMMAND,
    ORDINARY_TRADE_MAPPING_V16_PROMPT_REQUIRED_TAG,
    ORDINARY_TRADE_MAPPING_V16_PROMPT_TEMPLATE_ID,
    ORDINARY_TRADE_MAPPING_V16_PROMPT_TEMPLATE_KIND,
)


def _prepared(tmp_path):
    _store, context, _document_id, canonical, binding = (
        case_fixtures._unknown_two_table_case(tmp_path)
    )
    semantic = OrdinaryTradeSemanticMappingFactory.create()
    target_ids = [
        item["node_id"] for item in canonical["nodes"] if item["node_type"] == "TABLE"
    ]
    plan = semantic.build_mapping_batch_plan(
        canonical=canonical,
        confirmed_understandings=[],
        target_table_node_ids=target_ids,
    )
    plan = {
        **plan,
        "batches": [
            {
                "batch_id": f"batch_{index:04d}",
                "target_table_node_ids": [table_node_id],
                "mapping_package_sha256": _sha256_json(
                    semantic.build_mapping_package(
                        canonical=canonical,
                        confirmed_understandings=[],
                        target_table_node_ids=[table_node_id],
                    )
                ),
            }
            for index, table_node_id in enumerate(plan["target_table_node_ids"], start=1)
        ],
    }
    tables = {item["node_id"]: item for item in canonical["nodes"] if item["node_type"] == "TABLE"}
    outcomes = []
    for batch in plan["batches"]:
        table = tables[batch["target_table_node_ids"][0]]
        headers = tuple(
            cell["displayed_value"]
            for cell in sorted(
                (
                    cell
                    for cell in table["content"]["cells"]
                    if cell["row"] == 1
                ),
                key=lambda cell: cell["column"],
            )
        )
        response = case_fixtures._complete(
            table, candidate_fixtures._mapping_from_headers(headers)
        )
        outcomes.append(
            {
                "batch_id": batch["batch_id"],
                "outcome": semantic.validate_mapping_response(
                    response=response,
                    canonical=canonical,
                    canonical_binding=binding,
                    model_id="models/gemini-3.5-flash",
                    provider_profile_id="google_gemini",
                    execution_metadata=case_fixtures._metadata(),
                    confirmed_understandings=[],
                    user_scope_sha256=hashlib.sha256(
                        context.user_id.encode()
                    ).hexdigest(),
                    target_table_node_ids=batch["target_table_node_ids"],
                ),
            }
        )
    return semantic, canonical, binding, context, plan, outcomes


def _sha256_json(value) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        .encode("utf-8")
    ).hexdigest()


def _physical_continuation_context(*table_node_ids: str) -> dict:
    assert len(table_node_ids) == 2
    return {
        "schema_version": "broker_reports_physical_table_continuation_context_v1",
        "sidecar_artifact_ref": "private-sidecar",
        "sidecar_id": "ptcont_test",
        "source_binding": {
            "normalization_run_id": "run",
            "document_id": "document",
            "source_artifact_ref": "source",
            "source_sha256": "a" * 64,
            "canonical_version_id": "version",
            "canonical_root_sha256": "b" * 64,
        },
        "links": [
            {
                "parent_table_node_id": table_node_ids[0],
                "child_table_node_id": table_node_ids[1],
            }
        ],
    }


def test_mapping_package_projects_only_opaque_physical_continuation_refs(tmp_path) -> None:
    _store, _context, _document_id, canonical, _binding = (
        case_fixtures._unknown_two_table_case(tmp_path)
    )
    semantic = OrdinaryTradeSemanticMappingFactory.create()
    table_ids = [
        node["node_id"] for node in canonical["nodes"] if node["node_type"] == "TABLE"
    ]

    package = semantic.build_mapping_package(
        canonical=canonical,
        confirmed_understandings=[],
        target_table_node_ids=table_ids,
        physical_table_continuation_context=_physical_continuation_context(*table_ids),
    )

    assert package["case"]["physical_table_continuation_links"] == [
        {"parent_table_ref": "table_1", "child_table_ref": "table_2"}
    ]
    assert all("node_id" not in item for item in package["case"]["tables"])
    assert "sidecar_artifact_ref" not in str(package)


def test_physical_continuation_rejects_partial_scope_and_oversize_pair(
    tmp_path, monkeypatch
) -> None:
    _store, _context, _document_id, canonical, _binding = (
        case_fixtures._unknown_two_table_case(tmp_path)
    )
    semantic = OrdinaryTradeSemanticMappingFactory.create()
    table_ids = [
        node["node_id"] for node in canonical["nodes"] if node["node_type"] == "TABLE"
    ]
    physical_context = _physical_continuation_context(*table_ids)

    with pytest.raises(OrdinaryTradeSemanticMappingError) as partial:
        semantic.build_mapping_package(
            canonical=canonical,
            confirmed_understandings=[],
            target_table_node_ids=[table_ids[0]],
            physical_table_continuation_context=physical_context,
        )
    assert partial.value.code == "ordinary_trade_mapping_physical_continuation_scope_incomplete"

    singleton = semantic.build_mapping_package(
        canonical=canonical,
        confirmed_understandings=[],
        target_table_node_ids=[table_ids[0]],
    )
    monkeypatch.setattr(
        semantic_module,
        "_MAX_CONTEXT_BYTES",
        len(json.dumps(singleton, ensure_ascii=False).encode("utf-8")) + 1,
    )
    with pytest.raises(OrdinaryTradeSemanticMappingError) as oversize:
        semantic.build_mapping_batch_plan(
            canonical=canonical,
            confirmed_understandings=[],
            target_table_node_ids=table_ids,
            physical_table_continuation_context=physical_context,
        )
    assert oversize.value.code == "ordinary_trade_semantic_mapping_context_limit"


def test_batch_plan_rejects_forged_split_of_physical_continuation_pair(tmp_path) -> None:
    _store, _context, _document_id, canonical, binding = (
        case_fixtures._unknown_two_table_case(tmp_path)
    )
    semantic = OrdinaryTradeSemanticMappingFactory.create()
    table_ids = [
        node["node_id"] for node in canonical["nodes"] if node["node_type"] == "TABLE"
    ]
    forged_plan = {
        "schema_version": "broker_reports_ordinary_trade_mapping_batch_plan_v1",
        "target_table_node_ids": table_ids,
        "batches": [
            {
                "batch_id": "batch_0001",
                "target_table_node_ids": [table_ids[0]],
                "mapping_package_sha256": "a" * 64,
            },
            {
                "batch_id": "batch_0002",
                "target_table_node_ids": [table_ids[1]],
                "mapping_package_sha256": "b" * 64,
            },
        ],
    }

    with pytest.raises(OrdinaryTradeSemanticMappingError) as split:
        semantic.aggregate_mapping_batch_outcomes(
            canonical=canonical,
            canonical_binding=binding,
            user_scope_sha256="c" * 64,
            confirmed_understandings=[],
            batch_plan=forged_plan,
            batch_outcomes=[],
            physical_table_continuation_context=_physical_continuation_context(*table_ids),
        )
    assert split.value.code == "ordinary_trade_mapping_physical_continuation_scope_incomplete"


def _product_batches(tmp_path, monkeypatch):
    store, context, document_id, canonical, _binding = case_fixtures._unknown_two_table_case(tmp_path)
    tables = [node for node in canonical["nodes"] if node["node_type"] == "TABLE"]
    monkeypatch.setattr(semantic_module, "_MAX_CELLS_TOTAL", max(len(t["content"]["cells"]) for t in tables))
    responses = []
    for table in tables:
        headers = tuple(c["displayed_value"] for c in sorted(table["content"]["cells"], key=lambda c: c["column"]) if c["row"] == 1)
        responses.append(case_fixtures._complete(table, candidate_fixtures._mapping_from_headers(headers)))
    client = runtime_fixtures.BoundaryModelClient(responses)
    runtime = runtime_fixtures._runtime(store, client)
    return store, context, document_id, client, runtime


def _install_openwebui_private_file_boundary(monkeypatch, tmp_path):
    rows = {}

    class FileForm:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class Files:
        @staticmethod
        async def get_file_by_id(file_id):
            return rows.get(file_id)

        @staticmethod
        async def insert_new_file(user_id, form):
            row = SimpleNamespace(**form.__dict__, user_id=user_id)
            rows[form.id] = row
            return row

    class Storage:
        @staticmethod
        def upload_file(stream, name, _headers):
            content = stream.read()
            path = tmp_path / name
            path.write_bytes(content)
            return content, str(path)

        @staticmethod
        def get_file(path):
            return path

        @staticmethod
        def delete_file(path):
            Path(path).unlink(missing_ok=True)

    openwebui = ModuleType("open_webui")
    models = ModuleType("open_webui.models")
    files = ModuleType("open_webui.models.files")
    storage = ModuleType("open_webui.storage")
    provider = ModuleType("open_webui.storage.provider")
    files.FileForm = FileForm
    files.Files = Files
    provider.Storage = Storage
    monkeypatch.setitem(sys.modules, "open_webui", openwebui)
    monkeypatch.setitem(sys.modules, "open_webui.models", models)
    monkeypatch.setitem(sys.modules, "open_webui.models.files", files)
    monkeypatch.setitem(sys.modules, "open_webui.storage", storage)
    monkeypatch.setitem(sys.modules, "open_webui.storage.provider", provider)
    return rows


def test_product_splits_and_publishes_only_full_scope(tmp_path, monkeypatch):
    store, context, document_id, client, runtime = _product_batches(tmp_path, monkeypatch)
    result = asyncio.run(runtime.resolve(document_id=document_id, context=context))
    assert result["status"] == "COMPLETE"
    assert len(client.calls) == 2
    assert all(len(call["package"]["case"]["tables"]) == 1 for call in client.calls)
    material = runtime._cases.qualified_material(document_id=document_id, context=context)
    assert len(material["qualified_mappings"]) == 2


def test_batches_use_current_v14_response_adapter(tmp_path, monkeypatch):
    _store, context, document_id, client, runtime = _product_batches(tmp_path, monkeypatch)
    runtime._mapping_response_adapter = OrdinaryTradeGroupedMappingV14AdapterFactory.create()
    for response in client.outputs:
        response["schema_version"] = "broker_reports_ordinary_trade_grouped_mapping_response_v14"
        for decision in response["table_decisions"]:
            decision.pop("row_dispositions")
            decision["row_policy"] = {"default_disposition": "SECURITY_TRADES", "exception_rows": []}
    result = asyncio.run(runtime.resolve(document_id=document_id, context=context))
    assert result["status"] == "COMPLETE"
    assert len(client.calls) == 2
    assert all(call["response_format"]["json_schema"]["name"].endswith("v14") for call in client.calls)


class SimulatedCrash(BaseException):
    pass


def test_started_batch_crash_is_never_retried(tmp_path, monkeypatch):
    store, context, document_id, client, runtime = _product_batches(tmp_path, monkeypatch)
    class CrashClient:
        async def extract(self, **kwargs):
            state = runtime._cases.current(document_id=document_id, context=context)[1]
            assert state["mapping_batch_state"]["started_batch_id"] == "batch_0001"
            raise SimulatedCrash()
    runtime._model_client = CrashClient()
    with pytest.raises(SimulatedCrash):
        asyncio.run(runtime.resolve(document_id=document_id, context=context))
    resumed = runtime_fixtures._runtime(store, client)
    result = asyncio.run(resumed.resolve(document_id=document_id, context=context))
    assert result["status"] == "MAPPING_OUTPUT_INVALID"
    assert client.calls == []
    assert resumed._cases.qualified_material(document_id=document_id, context=context) is None


@pytest.mark.parametrize("changed_profile", [False, True, "prompt", "input_contract"])
def test_resume_runs_only_unstarted_batch(tmp_path, monkeypatch, changed_profile):
    store, context, document_id, client, runtime = _product_batches(tmp_path, monkeypatch)
    original = runtime._mapping_prompt_resolver
    class CrashBetweenBatches:
        calls = 0
        def resolve(self, user_context):
            self.calls += 1
            if self.calls == 2:
                raise SimulatedCrash()
            return original.resolve(user_context)
    runtime._mapping_prompt_resolver = CrashBetweenBatches()
    with pytest.raises(SimulatedCrash):
        asyncio.run(runtime.resolve(document_id=document_id, context=context))
    assert len(client.calls) == 1
    cases = OrdinaryTradeMappingCaseFactory(store=store, read_enabled=True).create()
    assert cases.qualified_material(document_id=document_id, context=context) is None
    resumed = runtime_fixtures._runtime(store, client)
    if changed_profile == "prompt":
        resumed._mapping_prompt_resolver = runtime_fixtures.StaticOrdinaryTradeMappingPromptResolver(
            replace(runtime_fixtures._test_mapping_prompt(), version="changed-history")
        )
    elif changed_profile == "input_contract":
        resumed._input_schema_version = MAPPING_INPUT_DOCUMENT_OPENING_SCHEMA_VERSION
        resumed._mapping_prompt_resolver = (
            runtime_fixtures.StaticOrdinaryTradeMappingPromptResolver(
                replace(
                    runtime_fixtures._test_mapping_prompt(),
                    command=ORDINARY_TRADE_MAPPING_V16_PROMPT_COMMAND,
                    version="v16-history",
                    template_id=ORDINARY_TRADE_MAPPING_V16_PROMPT_TEMPLATE_ID,
                    template_kind=ORDINARY_TRADE_MAPPING_V16_PROMPT_TEMPLATE_KIND,
                    input_schema_version=MAPPING_INPUT_DOCUMENT_OPENING_SCHEMA_VERSION,
                    output_schema_id=ORDINARY_TRADE_MAPPING_V16_COMPACT_RESPONSE_SCHEMA_VERSION,
                    output_schema_version=ORDINARY_TRADE_MAPPING_V16_COMPACT_RESPONSE_SCHEMA_VERSION,
                    tags=(ORDINARY_TRADE_MAPPING_V16_PROMPT_REQUIRED_TAG,),
                )
            )
        )
    elif changed_profile:
        resumed._model_id = "changed-profile"
    result = asyncio.run(resumed.resolve(document_id=document_id, context=context))
    expected = "MAPPING_OUTPUT_INVALID" if changed_profile else "COMPLETE"
    assert result["status"] == expected
    assert len(client.calls) == (1 if changed_profile else 2)
    if changed_profile:
        assert cases.qualified_material(document_id=document_id, context=context) is None
    if changed_profile in {"prompt", "input_contract"}:
        assert cases.current(document_id=document_id, context=context)[1]["reason_code"] == (
            "ordinary_trade_mapping_batch_prompt_snapshot_mismatch"
        )
        assert result["provider_calls_this_turn"] == 0


def test_concurrent_resolves_do_not_repeat_started_batch(tmp_path, monkeypatch):
    store, context, document_id, client, first = _product_batches(tmp_path, monkeypatch)

    async def exercise():
        started = asyncio.Event()
        release = asyncio.Event()

        class BlockedClient:
            calls = 0

            async def extract(self, **kwargs):
                self.calls += 1
                started.set()
                await release.wait()
                return await client.extract(**kwargs)

        blocked = BlockedClient()
        first._model_client = blocked
        second = runtime_fixtures._runtime(store, blocked)
        task = asyncio.create_task(first.resolve(document_id=document_id, context=context))
        await asyncio.wait_for(started.wait(), timeout=5)
        try:
            result = await second.resolve(document_id=document_id, context=context)
            assert result["status"] == "MAPPING_OUTPUT_INVALID"
            assert blocked.calls == 1
            assert first._cases.qualified_material(document_id=document_id, context=context) is None
        finally:
            release.set()
        results = await asyncio.gather(task, return_exceptions=True)
        assert isinstance(results[0], Exception) or results[0]["status"] != "COMPLETE"
        assert blocked.calls == 1
        assert first._cases.qualified_material(document_id=document_id, context=context) is None

    asyncio.run(exercise())


def test_stale_request_cannot_replay_completed_idle_batch(tmp_path, monkeypatch):
    store, context, document_id, client, advancing = _product_batches(tmp_path, monkeypatch)

    async def exercise():
        waiting = asyncio.Event()
        release = asyncio.Event()
        stale_client = runtime_fixtures.BoundaryModelClient([])
        stale = runtime_fixtures._runtime(store, stale_client)
        original = stale._mapping_prompt_resolver

        class DelayedPrompt:
            async def resolve(self, user_context):
                waiting.set()
                await release.wait()
                return original.resolve(user_context)

        class StopAfterFirstBatch:
            calls = 0

            def resolve(self, user_context):
                self.calls += 1
                if self.calls == 2:
                    raise SimulatedCrash()
                return original.resolve(user_context)

        stale._mapping_prompt_resolver = DelayedPrompt()
        advancing._mapping_prompt_resolver = StopAfterFirstBatch()
        task = asyncio.create_task(stale.resolve(document_id=document_id, context=context))
        await asyncio.wait_for(waiting.wait(), timeout=5)
        try:
            with pytest.raises(SimulatedCrash):
                await advancing.resolve(document_id=document_id, context=context)
            cases = OrdinaryTradeMappingCaseFactory(store=store, read_enabled=True).create()
            before = cases.current(document_id=document_id, context=context)[1]
            assert before["mapping_batch_state"]["started_batch_id"] is None
            assert [item["batch_id"] for item in before["mapping_batch_state"]["completed_batch_outcomes"]] == ["batch_0001"]
        finally:
            release.set()
        result = (await asyncio.gather(task, return_exceptions=True))[0]
        assert getattr(result, "code", None) == "ordinary_trade_mapping_case_batch_progress_stale"
        assert stale_client.calls == []
        assert len(client.calls) == 1
        assert cases.current(document_id=document_id, context=context)[1] == before
        assert cases.qualified_material(document_id=document_id, context=context) is None

    asyncio.run(exercise())


def test_invalid_batch_preserves_private_raw_response_without_logging_it(
    tmp_path, monkeypatch, caplog
):
    store, context, document_id, client, runtime = _product_batches(tmp_path, monkeypatch)
    private_response = {"provider_private_value": "batch-output-do-not-log"}
    client.outputs[1] = private_response
    caplog.set_level(
        logging.INFO,
        logger="broker_reports_gate1.ordinary_trade_mapping_case",
    )
    result = asyncio.run(runtime.resolve(document_id=document_id, context=context))
    assert result["status"] == "MAPPING_OUTPUT_INVALID"
    assert len(client.calls) == 2
    assert runtime._cases.qualified_material(document_id=document_id, context=context) is None
    raw_ref = result["private_mapping_raw_output_ref"]
    assert raw_ref == runtime._cases.invalid_mapping_raw_output_ref(
        document_id=document_id, context=context
    )
    assert raw_ref == {
        "schema_version": MAPPING_RAW_OUTPUT_REFERENCE_SCHEMA_VERSION,
        "artifact_ref": raw_ref["artifact_ref"],
        "mapping_case_artifact_id": result["mapping_case_artifact_id"],
    }
    assert private_response["provider_private_value"] not in repr(result)
    assert "private_mapping_raw_output_ref" not in result["public_state"]
    assert asyncio.run(runtime.resolve(document_id=document_id, context=context))["status"] == "MAPPING_OUTPUT_INVALID"
    assert len(client.calls) == 2
    raw_records = store.list_by_type(
        context.normalization_run_id, MAPPING_RAW_OUTPUT_ARTIFACT_TYPE
    )
    assert len(raw_records) == 1
    raw_record = raw_records[0]
    assert raw_record.visibility == "private_case"
    assert raw_record.artifact_id == raw_ref["artifact_ref"]
    assert raw_record.user_id == context.user_id
    assert raw_record.case_id == context.case_id
    assert raw_record.chat_id == context.chat_id
    assert raw_record.workspace_model_id == context.workspace_model_id
    assert raw_record.safe_metadata["contains_provider_response"] is True
    raw = ArtifactResolver(store).resolve(raw_record.artifact_id, context)["payload"]
    assert raw["response_content"] == private_response
    receipt = [
        record.message
        for record in caplog.records
        if "broker_reports_mapping_invalid_terminal" in record.message
    ]
    assert receipt == [
        "broker_reports_mapping_invalid_terminal "
        "reason_code=ordinary_trade_semantic_mapping_response_invalid "
        "revision=5 provider_calls_total=2 raw_response_saved=True"
    ]
    assert "batch-output-do-not-log" not in caplog.text


def test_complete_batch_exposes_no_private_raw_response_ref(tmp_path, monkeypatch):
    store, context, document_id, _client, runtime = _product_batches(tmp_path, monkeypatch)

    result = asyncio.run(runtime.resolve(document_id=document_id, context=context))

    assert result["status"] == "COMPLETE"
    assert "private_mapping_raw_output_ref" not in result
    assert runtime._cases.invalid_mapping_raw_output_ref(
        document_id=document_id, context=context
    ) is None
    assert store.list_by_type(
        context.normalization_run_id, MAPPING_RAW_OUTPUT_ARTIFACT_TYPE
    ) == []


def test_pipe_projects_only_invalid_mapping_raw_response_to_owner_file(
    tmp_path, monkeypatch, caplog
):
    store, context, document_id, client, runtime = _product_batches(tmp_path, monkeypatch)
    private_response = {"provider_private_value": "mapping-output-do-not-log"}
    client.outputs[1] = private_response
    mapping = asyncio.run(runtime.resolve(document_id=document_id, context=context))
    assert mapping["status"] == "MAPPING_OUTPUT_INVALID"
    raw_ref = mapping["private_mapping_raw_output_ref"]

    rows = _install_openwebui_private_file_boundary(monkeypatch, tmp_path)
    caplog.set_level(logging.INFO, logger="openwebui_actions.broker_reports_gate1_pipe")
    Pipe._audit_mapping_terminal(mapping)
    delivery = asyncio.run(
        Pipe._publish_mapping_forensics_file(
            store=store,
            context=context,
            user={"id": context.user_id, "email": "", "name": ""},
            semantic_mapping=mapping,
        )
    )

    assert delivery is not None
    assert delivery["filename"] == "mapping-response-forensics.json"
    assert delivery["content_type"] == "application/json"
    assert delivery["url"] == (
        f"/api/v1/files/{delivery['file_id']}/content?attachment=true"
    )
    assert len(rows) == 1
    row = rows[delivery["file_id"]]
    assert row.user_id == context.user_id
    assert row.filename == delivery["filename"]
    assert json.loads(Path(row.path).read_text(encoding="utf-8")) == private_response
    assert row.meta["data"]["broker_reports_mapping_forensics"] is True
    assert row.meta["data"]["mapping_case_artifact_id"] == raw_ref[
        "mapping_case_artifact_id"
    ]
    assert "provider_private_value" not in repr(delivery)
    assert "mapping-output-do-not-log" not in caplog.text
    public_link = Pipe._mapping_forensics_download_line(delivery)
    assert delivery["url"] in public_link
    assert "mapping-output-do-not-log" not in public_link

    # The public turn state and its opaque private response reference have to
    # name the same MappingCase before the Pipe resolves anything.  This is a
    # real boundary mutation: the stored private artifact remains valid, but
    # a forged coordinator result cannot publish it as another case.
    misbound_mapping = dict(mapping)
    misbound_mapping["mapping_case_artifact_id"] = "foreign-mapping-case"
    # If the Pipe resolved first, this unknown ref would yield
    # ``artifact_not_found``.  The binding error proves the mandatory check is
    # before private resolution.
    misbound_mapping["private_mapping_raw_output_ref"] = {
        **raw_ref,
        "artifact_ref": "not-a-mapping-raw-artifact",
    }
    with pytest.raises(ArtifactStoreError) as misbound:
        asyncio.run(
            Pipe._publish_mapping_forensics_file(
                store=store,
                context=context,
                user={"id": context.user_id, "email": "", "name": ""},
                semantic_mapping=misbound_mapping,
            )
        )
    assert misbound.value.code == "mapping_forensics_private_case_binding_invalid"
    assert len(rows) == 1

    overfull_reference = dict(mapping)
    overfull_reference["private_mapping_raw_output_ref"] = {
        **raw_ref,
        "untrusted_extra": "must-not-be-accepted",
    }
    with pytest.raises(ArtifactStoreError) as overfull:
        asyncio.run(
            Pipe._publish_mapping_forensics_file(
                store=store,
                context=context,
                user={"id": context.user_id, "email": "", "name": ""},
                semantic_mapping=overfull_reference,
            )
        )
    assert overfull.value.code == "mapping_forensics_private_reference_invalid"
    assert len(rows) == 1

    foreign_context = replace(context, user_id="other-user")
    with pytest.raises(ArtifactStoreError) as foreign:
        asyncio.run(
            Pipe._publish_mapping_forensics_file(
                store=store,
                context=foreign_context,
                user={"id": "other-user", "email": "", "name": ""},
                semantic_mapping=mapping,
            )
        )
    assert foreign.value.code == "artifact_access_denied"
    assert len(rows) == 1

    complete_store, complete_context, complete_document_id, _client, complete_runtime = (
        _product_batches(tmp_path / "complete", monkeypatch)
    )
    complete = asyncio.run(
        complete_runtime.resolve(
            document_id=complete_document_id,
            context=complete_context,
        )
    )
    assert complete["status"] == "COMPLETE"
    assert (
        asyncio.run(
            Pipe._publish_mapping_forensics_file(
                store=complete_store,
                context=complete_context,
                user={"id": complete_context.user_id, "email": "", "name": ""},
                semantic_mapping=complete,
            )
        )
        is None
    )
    assert len(rows) == 1


def test_pipe_keeps_persisted_invalid_terminal_when_native_file_boundary_is_unavailable(
    tmp_path, monkeypatch, caplog
):
    store, context, document_id, client, runtime = _product_batches(tmp_path, monkeypatch)
    client.outputs[1] = {"provider_private_value": "mapping-output-do-not-log"}
    mapping = asyncio.run(runtime.resolve(document_id=document_id, context=context))
    assert mapping["status"] == "MAPPING_OUTPUT_INVALID"
    persisted_before = runtime._cases.current(document_id=document_id, context=context)

    caplog.set_level(logging.WARNING, logger="openwebui_actions.broker_reports_gate1_pipe")
    delivery = asyncio.run(
        Pipe._try_publish_mapping_forensics_file(
            store=store,
            context=context,
            user={"id": context.user_id, "email": "", "name": ""},
            semantic_mapping=mapping,
        )
    )

    # No OpenWebUI Files/Storage modules are installed in this test process:
    # this invokes the real private-publication boundary and proves the Pipe
    # retains the owner-persisted terminal when that optional boundary fails.
    assert delivery is None
    persisted_after = runtime._cases.current(document_id=document_id, context=context)
    assert persisted_after == persisted_before
    assert persisted_after[1]["status"] == "MAPPING_OUTPUT_INVALID"
    assert runtime._cases.invalid_mapping_raw_output_ref(
        document_id=document_id, context=context
    ) == mapping["private_mapping_raw_output_ref"]
    assert "private_mapping_raw_output_ref" not in mapping["public_state"]
    assert "mapping-output-do-not-log" not in caplog.text
    assert "private_file_projection_boundary_unavailable" in caplog.text


@pytest.mark.parametrize("restart", [False, True, "after_assertion", "resolver_fails_pending"])
def test_batch_currency_answer_preserves_plan_without_recalling_batch(tmp_path, monkeypatch, restart):
    store, context, document_id, client, runtime = _product_batches(tmp_path, monkeypatch)
    response = client.outputs[0]
    response["status"] = "CURRENCY_ASSERTION_REQUIRED"
    response["table_decisions"][0]["amount_currency_bindings"] = []
    response["table_decisions"][0]["columns"][5]["semantic_role"] = "unmapped"
    pending = asyncio.run(runtime.resolve(document_id=document_id, context=context))
    assert pending["status"] == "CURRENCY_ASSERTION_REQUIRED"
    assert len(client.calls) == 1
    cases = OrdinaryTradeMappingCaseFactory(store=store, read_enabled=True).create()
    before = cases.current(document_id=document_id, context=context)[1]
    state = before["mapping_batch_state"]
    assert state["pending_batch_id"] == "batch_0001"
    assert state["started_batch_id"] is None
    assert cases.qualified_material(document_id=document_id, context=context) is None
    if restart:
        runtime = runtime_fixtures._runtime(store, client)
    if restart == "resolver_fails_pending":
        original = runtime._mapping_prompt_resolver
        class PendingResolverUnavailable:
            def resolve(self, user_context):
                if cases.current(document_id=document_id, context=context)[1]["mapping_batch_state"]["pending_batch_id"] is not None:
                    raise RuntimeError("resolver unavailable during deterministic replay")
                return original.resolve(user_context)
        runtime._mapping_prompt_resolver = PendingResolverUnavailable()
    unchanged = asyncio.run(runtime.resolve(document_id=document_id, context=context, user_message="не знаю"))
    assert unchanged["status"] == "CURRENCY_ASSERTION_REQUIRED"
    assert cases.current(document_id=document_id, context=context)[1] == before
    if restart == "after_assertion":
        asserted = cases.record_user_currency_assertion(
            document_id=document_id, context=context, currency_code="USD",
            table_node_ids=state["plan"]["batches"][0]["target_table_node_ids"],
        )[1]
        runtime = runtime_fixtures._runtime(store, client)
        altered = asyncio.run(runtime.resolve(document_id=document_id, context=context, user_message="currency: EUR"))
        assert altered["status"] == "MAPPING_REQUIRED"
        assert cases.current(document_id=document_id, context=context)[1] == asserted
        assert len(client.calls) == 1
    completed = asyncio.run(runtime.resolve(document_id=document_id, context=context, user_message="currency: USD"))
    assert completed["status"] == "COMPLETE"
    assert len(client.calls) == 2
    assert _sha256_json(client.calls[0]["package"]) == state["plan"]["batches"][0]["mapping_package_sha256"]
    assert _sha256_json(client.calls[1]["package"]) == state["plan"]["batches"][1]["mapping_package_sha256"]
    final = cases.current(document_id=document_id, context=context)[1]
    assert final["confirmed_understandings"][-1]["decision"]["currency_code"] == "USD"
    repeated = asyncio.run(runtime.resolve(document_id=document_id, context=context, user_message="currency: EUR"))
    assert repeated["status"] == "COMPLETE"
    assert cases.current(document_id=document_id, context=context)[1] == final
    assert len(client.calls) == 2


def test_batch_pins_existing_currency_without_copying_confirmations(tmp_path, monkeypatch):
    store, context, document_id, client, runtime = _product_batches(tmp_path, monkeypatch)
    cases = runtime._cases
    binding = cases.case_binding(document_id=document_id, context=context)
    table_id = next(node["node_id"] for node in binding["canonical"]["nodes"] if node["node_type"] == "TABLE")
    response = client.outputs[0]
    response["status"] = "CURRENCY_ASSERTION_REQUIRED"
    response["table_decisions"][0]["amount_currency_bindings"] = []
    response["table_decisions"][0]["columns"][5]["semantic_role"] = "unmapped"
    outcome = OrdinaryTradeSemanticMappingFactory.create().validate_mapping_response(
        response=response, canonical=binding["canonical"], canonical_binding=binding["canonical_binding"],
        model_id="models/gemini-3.5-flash", provider_profile_id="google_gemini",
        execution_metadata=case_fixtures._metadata(), confirmed_understandings=[],
        user_scope_sha256=binding["user_scope_sha256"], target_table_node_ids=[table_id],
    )
    cases.save_mapping_outcome(document_id=document_id, context=context, outcome=outcome, provider_calls_total=0)
    seeded = cases.record_user_currency_assertion(document_id=document_id, context=context, currency_code="USD", table_node_ids=[table_id])[1]
    forged_plan = runtime._semantic.build_mapping_batch_plan(
        canonical=binding["canonical"], confirmed_understandings=seeded["confirmed_understandings"],
        target_table_node_ids=[node["node_id"] for node in binding["canonical"]["nodes"] if node["node_type"] == "TABLE"],
    )
    forged_initial = {
        "schema_version": "broker_reports_ordinary_trade_mapping_batch_state_v3",
        "plan": forged_plan, "plan_sha256": _sha256_json(forged_plan),
        "completed_batch_outcomes": [], "pending_batch_id": None, "started_batch_id": None, "attempt_token": None,
        "base_decision_sha256": [], "base_confirmed_sha256": _sha256_json([]),
        "execution_binding_sha256": runtime._batch_execution_binding(binding, []),
    }
    with pytest.raises(OrdinaryTradeMappingCaseError) as exc:
        cases.save_batch_state(
            document_id=document_id, context=context, status="MAPPING_REQUIRED", message="forged initial base",
            mapping_batch_state=forged_initial, provider_calls_total=0,
            mapping_prompt_snapshot=runtime_fixtures._test_mapping_prompt().snapshot(),
        )
    assert exc.value.code == "ordinary_trade_mapping_case_batch_binding_changed"
    assert client.calls == []
    response["status"] = "COMPLETE"
    original = runtime._mapping_prompt_resolver

    class StopBetween:
        calls = 0
        def resolve(self, user_context):
            self.calls += 1
            if self.calls == 2:
                raise SimulatedCrash()
            return original.resolve(user_context)

    runtime._mapping_prompt_resolver = StopBetween()
    with pytest.raises(SimulatedCrash):
        asyncio.run(runtime.resolve(document_id=document_id, context=context))
    current = cases.current(document_id=document_id, context=context)[1]
    state = current["mapping_batch_state"]
    assert state["base_decision_sha256"] == [seeded["confirmed_understandings"][0]["decision_sha256"]]
    assert state["base_confirmed_sha256"] == _sha256_json(seeded["confirmed_understandings"])
    assert "confirmed_understandings" not in state
    assert client.calls[0]["package"]["case"]["user_currency_assertions"] == [{"table_ref": "table_1", "currency_code": "USD"}]
    tampered = copy.deepcopy(state)
    tampered["base_decision_sha256"] = ["f" * 64]
    with pytest.raises(OrdinaryTradeMappingCaseError) as exc:
        cases.save_batch_state(
            document_id=document_id, context=context, status="MAPPING_REQUIRED", message="tampered",
            mapping_batch_state=tampered, mapping_prompt_snapshot=current["mapping_prompt_snapshot"], provider_calls_total=0,
        )
    assert exc.value.code == "ordinary_trade_mapping_case_batch_binding_changed"
    assert cases.current(document_id=document_id, context=context)[1] == current
    result = asyncio.run(runtime_fixtures._runtime(store, client).resolve(document_id=document_id, context=context))
    assert result["status"] == "COMPLETE"
    assert len(client.calls) == 2


@pytest.mark.parametrize("field", ["target_table_node_ids", "table_node_ids"])
def test_currency_candidate_scope_tampering_stops_without_calls(tmp_path, monkeypatch, field):
    _store, context, document_id, client, runtime = _product_batches(tmp_path, monkeypatch)
    response = client.outputs[0]
    response["status"] = "CURRENCY_ASSERTION_REQUIRED"
    response["table_decisions"][0]["amount_currency_bindings"] = []
    response["table_decisions"][0]["columns"][5]["semantic_role"] = "unmapped"
    assert asyncio.run(runtime.resolve(document_id=document_id, context=context))["status"] == "CURRENCY_ASSERTION_REQUIRED"
    cases = runtime._cases
    current = cases.current(document_id=document_id, context=context)[1]
    candidate = copy.deepcopy(current["pending_candidate"])
    candidate[field] = current["mapping_batch_state"]["plan"]["batches"][1]["target_table_node_ids"]
    with pytest.raises(OrdinaryTradeMappingCaseError) as exc:
        cases.save_batch_state(
            document_id=document_id, context=context, status="CURRENCY_ASSERTION_REQUIRED", message="tampered candidate",
            mapping_batch_state=current["mapping_batch_state"], pending_candidate=candidate,
            provider_calls_total=0, mapping_prompt_snapshot=current["mapping_prompt_snapshot"],
        )
    assert exc.value.code == "ordinary_trade_mapping_batch_currency_scope_invalid"
    # Emulate an older persisted candidate that predates this scope check.
    # The production resume must also reject it, without querying the model.
    historical = copy.deepcopy(current)
    historical["revision"] += 1
    historical["pending_candidate"] = candidate
    historical["predecessor_sha256"] = current["integrity_sha256"]
    historical.pop("integrity_sha256")
    historical["integrity_sha256"] = _sha256_json(historical)
    cases._put(payload=historical, document_id=document_id, context=context)
    result = asyncio.run(runtime.resolve(document_id=document_id, context=context, user_message="currency: USD"))
    assert result["status"] == "MAPPING_OUTPUT_INVALID"
    assert cases.current(document_id=document_id, context=context)[1]["reason_code"] == "ordinary_trade_mapping_batch_currency_scope_invalid"
    assert len(client.calls) == 1
    assert cases.qualified_material(document_id=document_id, context=context) is None


def test_singleton_overflow_has_zero_calls(tmp_path, monkeypatch):
    _store, context, document_id, client, runtime = _product_batches(tmp_path, monkeypatch)
    monkeypatch.setattr(semantic_module, "_MAX_ROWS_PER_TABLE", 1)
    result = asyncio.run(runtime.resolve(document_id=document_id, context=context))
    assert result["status"] == "SOURCE_CONTEXT_LIMIT"
    assert client.calls == []


def test_actual_257_row_table_stops_before_any_provider_call(tmp_path):
    rows = runtime_fixtures._unknown_rows()
    large_rows = (rows[0], *([rows[1]] * 256))
    store, context, document_id, _tables, _ref = runtime_fixtures._multi_table_case(
        tmp_path, table_row_sets=(rows, large_rows),
    )
    client = runtime_fixtures.BoundaryModelClient([])
    runtime = runtime_fixtures._runtime(store, client)
    result = asyncio.run(runtime.resolve(document_id=document_id, context=context))
    assert result["status"] == "SOURCE_CONTEXT_LIMIT"
    assert client.calls == []


def test_aggregate_replays_compiler_after_full_disjoint_coverage(tmp_path) -> None:
    semantic, canonical, binding, context, plan, outcomes = _prepared(tmp_path)

    aggregate = semantic.aggregate_mapping_batch_outcomes(
        canonical=canonical,
        canonical_binding=binding,
        user_scope_sha256=hashlib.sha256(context.user_id.encode()).hexdigest(),
        confirmed_understandings=[],
        batch_plan=plan,
        batch_outcomes=outcomes,
    )

    assert aggregate["status"] == "COMPLETE"
    assert [item["table_node_id"] for item in aggregate["table_resolutions"]] == plan[
        "target_table_node_ids"
    ]
    assert [item["table_node_id"] for item in aggregate["projection"]["qualified_table_resolutions"]] == plan[
        "target_table_node_ids"
    ]
    assert aggregate["projection"]["runtime_records"]


@pytest.mark.parametrize("kind", ["overlap", "missing"])
def test_batch_plan_rejects_overlap_or_missing_coverage(tmp_path, kind: str) -> None:
    semantic, canonical, binding, context, plan, outcomes = _prepared(tmp_path)
    forged = copy.deepcopy(plan)
    if kind == "overlap":
        forged["batches"][1]["target_table_node_ids"] = list(
            forged["batches"][0]["target_table_node_ids"]
        )
    else:
        forged["batches"] = forged["batches"][:1]

    with pytest.raises(OrdinaryTradeSemanticMappingError) as rejected:
        semantic.aggregate_mapping_batch_outcomes(
            canonical=canonical,
            canonical_binding=binding,
            user_scope_sha256=hashlib.sha256(context.user_id.encode()).hexdigest(),
            confirmed_understandings=[],
            batch_plan=forged,
            batch_outcomes=outcomes,
        )

    assert rejected.value.code == "ordinary_trade_mapping_batch_plan_coverage_invalid"


def test_aggregate_rejects_outcome_attached_to_wrong_batch(tmp_path) -> None:
    semantic, canonical, binding, context, plan, outcomes = _prepared(tmp_path)
    forged = copy.deepcopy(outcomes)
    forged[0]["batch_id"], forged[1]["batch_id"] = (
        forged[1]["batch_id"],
        forged[0]["batch_id"],
    )

    with pytest.raises(OrdinaryTradeSemanticMappingError) as rejected:
        semantic.aggregate_mapping_batch_outcomes(
            canonical=canonical,
            canonical_binding=binding,
            user_scope_sha256=hashlib.sha256(context.user_id.encode()).hexdigest(),
            confirmed_understandings=[],
            batch_plan=plan,
            batch_outcomes=forged,
        )

    assert rejected.value.code == "ordinary_trade_mapping_batch_outcome_coverage_invalid"
