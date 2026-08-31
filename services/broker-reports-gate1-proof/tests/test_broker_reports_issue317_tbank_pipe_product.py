from __future__ import annotations

import asyncio
import copy
import importlib
import importlib.util
import json
import os
import shutil
import struct
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

import test_broker_reports_pdf_table_intake_gate1 as tbank_fixtures


SERVICE_ROOT = Path(__file__).resolve().parents[1]
BUNDLE_PATH = (
    SERVICE_ROOT / "openwebui_actions" / "broker_reports_gate1_pipe_bundled.py"
)
MODEL_ID = "models/gemini-3.5-flash"
WORKSPACE_MODEL_ID = "broker_reports_ndfl"


class FrozenLocatorProvider:
    def __init__(self) -> None:
        self.invocations = 0
        self.full_page_png_sizes: list[tuple[int, int]] = []

    @staticmethod
    def qualify() -> dict:
        return {
            "status": "qualified",
            "provider_profile": "google_gemini",
            "provider_profile_revision": "frozen-product-proof-v1",
            "requested_model_id": MODEL_ID,
            "resolved_model_id": MODEL_ID,
            "exact_model_match": True,
            "image_input_supported": True,
            "structured_output_supported": True,
            "response_hash": "frozen-locator-qualification",
            "native_provider_transport": True,
            "credentials_from_openwebui_connection": True,
            "hidden_retry": False,
            "provider_failover": False,
        }

    @staticmethod
    def count_tokens(**_kwargs) -> dict:
        return {
            "total_tokens": 100,
            "request_hash": "frozen-locator-token-request",
            "response_hash": "frozen-locator-token-response",
            "within_hard_guard": True,
        }

    def invoke(self, **kwargs) -> dict:
        self.invocations += 1
        page = self.invocations
        assert kwargs["attempt_number"] == 1
        assert kwargs["attempt_lineage"] == []
        png_bytes = kwargs["png_bytes"]
        assert png_bytes.startswith(b"\x89PNG\r\n\x1a\n")
        size = struct.unpack(">II", png_bytes[16:24])
        assert size == (1754, 1240)
        self.full_page_png_sizes.append(size)
        tables = [
            {
                "table_box_2d": table,
                "title_box_2d": title,
                "header_box_2d": header,
            }
            for table, title, header in tbank_fixtures.TBANK_FROZEN_LOCATOR_V2[page]
        ]
        return {
            "attempt": {
                "terminal_failure_class": None,
                "provider_profile": "google_gemini",
                "provider_profile_revision": "frozen-product-proof-v1",
                "model_requested": MODEL_ID,
                "model_resolved": MODEL_ID,
                "adapter_identity": "frozen-locator-transport-v1",
                "request_hash": f"frozen-locator-page-{page}",
                "hidden_retry": False,
                "provider_failover": False,
            },
            "json_output": {"tables": tables},
            "raw_private_response": {"frozen_page": page},
            "response_hash": f"frozen-locator-response-{page}",
        }


def _proposal(case_package: dict) -> dict:
    roles = (
        "trade_id",
        "unmapped",
        "unmapped",
        "trade_date",
        "trade_time",
        "description",
        "venue",
        "side",
        "asset_name",
        "security_code",
        "unit_price",
        "currency",
        "quantity",
        "unmapped",
        "accrued_interest",
        "gross_amount",
        "currency",
        "broker_commission",
        "currency",
        "exchange_commission",
        "currency",
        "retained_transaction_charge",
        "currency",
        "unmapped",
        "description",
        "settlement_date",
        "unmapped",
        "status",
        "unmapped",
        "unmapped",
        "unmapped",
        "comment",
    )
    trade_table = case_package["case"]["tables"][0]
    side_literal = next(
        cell["literal"]
        for row in trade_table["rows"]
        for cell in row["cells"]
        if cell["column"] == 8 and cell["literal"]
    )
    decisions = [
        {
            "table_ref": "table_1",
            "disposition": "SECURITY_TRADES",
            "columns": [
                {"column": column, "semantic_role": role}
                for column, role in enumerate(roles, start=1)
            ],
            "amount_currency_bindings": [
                {"amount_column": 16, "currency_column": 17},
                {"amount_column": 18, "currency_column": 19},
                {"amount_column": 20, "currency_column": 21},
                {"amount_column": 22, "currency_column": 23},
            ],
            "side_values": [
                {"source_literal": side_literal, "normalized_value": "PURCHASE"}
            ],
        }
    ]
    decisions.extend(
        {
            "table_ref": f"table_{index}",
            "disposition": "NO_NAMED_CONSUMER",
            "columns": [],
            "amount_currency_bindings": [],
            "side_values": [],
        }
        for index in range(2, 16)
    )
    return {
        "schema_version": "broker_reports_ordinary_trade_semantic_mapping_response_v2",
        "status": "COMPLETE",
        "table_decisions": decisions,
        "clarification": None,
        "message": "Complete document-wide mapping with retained clearing charges.",
    }


class FrozenSemanticCompletion:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def __call__(
        self,
        *,
        request,
        form_data,
        user,
        bypass_filter=False,
        bypass_system_prompt=False,
    ) -> dict:
        assert request is not None
        assert user is not None
        assert bypass_filter is True
        assert bypass_system_prompt is True
        phase = form_data["metadata"]["broker_reports_ordinary_trade"]["phase"]
        package = json.loads(form_data["messages"][1]["content"])
        self.calls.append(
            {
                "phase": phase,
                "package": copy.deepcopy(package),
                "model": form_data["model"],
            }
        )
        if phase == "map":
            value = _proposal(package)
        elif phase == "critic":
            value = {
                "schema_version": "broker_reports_ordinary_trade_semantic_critic_response_v1",
                "verdict": "APPROVE",
                "reviewed_response": copy.deepcopy(package["proposal"]),
                "message": "Independent review approved the complete mapping.",
            }
        else:
            raise AssertionError(f"unexpected semantic phase: {phase}")
        return {
            "id": f"frozen-{phase}",
            "model": MODEL_ID,
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {
                        "role": "assistant",
                        "content": json.dumps(value, ensure_ascii=False),
                    },
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 10,
                "total_tokens": 20,
            },
        }


def _install_openwebui_completion(
    monkeypatch: pytest.MonkeyPatch, completion: FrozenSemanticCompletion
) -> None:
    openwebui = ModuleType("open_webui")
    utils = ModuleType("open_webui.utils")
    chat = ModuleType("open_webui.utils.chat")
    models = ModuleType("open_webui.models")
    users = ModuleType("open_webui.models.users")

    class Users:
        @staticmethod
        def get_user_by_id(user_id: str):
            return SimpleNamespace(id=user_id, role="admin")

    chat.generate_chat_completion = completion
    users.Users = Users
    monkeypatch.setitem(sys.modules, "open_webui", openwebui)
    monkeypatch.setitem(sys.modules, "open_webui.utils", utils)
    monkeypatch.setitem(sys.modules, "open_webui.utils.chat", chat)
    monkeypatch.setitem(sys.modules, "open_webui.models", models)
    monkeypatch.setitem(sys.modules, "open_webui.models.users", users)


def _configure_pipe(pipe, tmp_path: Path) -> None:
    pipe.valves.ordinary_trade_candidate_enabled = True
    pipe.valves.ordinary_trade_semantic_mapping_enabled = True
    pipe.valves.canonical_gate2_write_enabled = True
    pipe.valves.canonical_gate2_read_enabled = True
    pipe.valves.pdf_compact_canonical_dual_write = True
    pipe.valves.pdf_table_intake_enabled = True
    pipe.valves.passport_enabled = False
    pipe.valves.clarification_enabled = False
    pipe.valves.ndfl_presentation_llm_enabled = False
    pipe.valves.artifact_store_path = str(tmp_path / "artifacts.sqlite3")
    pipe.valves.artifact_payload_root = str(tmp_path / "payloads")
    pipe.valves.workload_store_path = str(tmp_path / "workloads.sqlite3")
    pipe.valves.workload_temp_root = str(tmp_path / "workload-temp")
    pipe.valves.artifact_retention_mode = "synthetic_dev"


def _stabilize_canonical_capacity(monkeypatch: pytest.MonkeyPatch) -> None:
    canonical_store = importlib.import_module("broker_reports_gate1.canonical_store")
    monkeypatch.setattr(
        canonical_store.shutil,
        "disk_usage",
        lambda _: shutil._ntuple_diskusage(
            10_000_000_000, 1_000_000_000, 9_000_000_000
        ),
    )


def _run_product_turn(pipe, *, pdf_bytes: bytes, completion) -> tuple[str, dict, dict]:
    metadata = {
        "chat_id": "issue317-tbank-pipe-product",
        "case_id": "issue317-tbank-pipe-product",
        "model_id": WORKSPACE_MODEL_ID,
    }
    user = {"id": "issue317-tbank-user", "email": "", "name": ""}
    content = asyncio.run(
        pipe.pipe(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": "Подготовь 3-НДФЛ по этому отчету.",
                        "files": [
                            {
                                "type": "file",
                                "file": {
                                    "id": "issue317-tbank-real-pdf",
                                    "filename": "tbank-public-control.pdf",
                                    "mime_type": "application/pdf",
                                    "content_bytes": pdf_bytes,
                                },
                            }
                        ],
                    }
                ]
            },
            __user__=user,
            __metadata__=metadata,
            __request__=object(),
        )
    )
    first_manifest = copy.deepcopy(pipe.last_artifact_manifest)
    first_result = copy.deepcopy(first_manifest["ndfl_gate3"])
    safe_report = copy.deepcopy(pipe.last_safe_report)
    assert first_result["provider_calls_total"] == 2, json.dumps(
        {
            "result": first_result,
            "manifest": pipe.last_artifact_manifest,
            "report": pipe.last_safe_report,
            "locator_calls": getattr(completion, "locator_calls", None),
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    assert first_result["product"]["status"] == "OPEN_POSITION_RETAINED"
    assert first_result["semantic_mapping"]["status"] == "COMPLETE"
    assert len(completion.calls) == 2
    assert [item["phase"] for item in completion.calls] == ["map", "critic"]
    mapping_case = completion.calls[0]["package"]["case"]
    assert mapping_case == completion.calls[1]["package"]["case"]
    assert len(mapping_case["tables"]) == 15
    assert len(mapping_case["tables"][0]["rows"]) == 5
    assert safe_report["gate2_handoff"]["gate2_handoff_status"] == "blocked"
    assert safe_report["document_class_counts"] == {"unknown_or_needs_review": 1}
    assert safe_report["taxonomy_candidates"][0]["source_role_policy_status"] == (
        "context_issue"
    )

    return content, first_result, first_manifest


def _assert_product_result(content: str, result: dict, first_manifest: dict, locator) -> None:
    assert locator.invocations == 4
    assert locator.full_page_png_sizes == [(1754, 1240)] * 4
    assert first_manifest["pdf_table_intake"]["regions_total"] == 15
    assert result["provider_calls_total"] == 2
    assert result["product"]["status"] == "OPEN_POSITION_RETAINED"
    assert result["product"]["xml_created"] is False
    assert result["declaration"] is None
    assert result["product"]["preparation"]["user_actions"] == []
    assert result["public_dialogue"]["context"]["current_question"] is None
    gate4 = result["product"]["gate4"]
    assert gate4["facts_total"] == 15
    assert gate4["security_facts_total"] == 5
    assert gate4["transaction_charge_facts_total"] == 10
    gate5 = result["product"]["gate5"]
    assert gate5["blocker_reason_codes"] == []
    assert gate5["execution_status"] == "open_position_not_tax_activated"
    assert gate5["fifo_calculations"] == []
    group = gate5["security_groups"][0]
    assert group["asset"] == "Ozon Holdings PLC ORD SHS ADR"
    position = group["position_scope"]
    assert position["state"] == "OPEN_LONG_PROVEN"
    assert position["open_long_quantity"] == "7"
    assert position["tax_activation_status"] == "NOT_ACTIVATED_NO_DISPOSAL"
    assert position["resolved_disposal_quantity"] == "0"
    assert gate5["blocker_reason_codes"] == []
    assert "source gap" not in content.casefold()
    assert "source_gap" not in content.casefold()
    assert "открытая длинная позиция" in content
    assert "в налоговую базу не включена" in content


def test_source_pipe_runs_real_tbank_to_open_long(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from openwebui_actions.broker_reports_gate1_pipe import Pipe

    pdf_bytes, _digest = tbank_fixtures._public_tbank_control()
    locator = FrozenLocatorProvider()
    provider_module = importlib.import_module(
        "broker_reports_gate1.pdf_table_locator_provider"
    )
    monkeypatch.setattr(
        provider_module.PdfTableLocatorProviderFactory,
        "create_for_openwebui",
        lambda _self, _request: locator,
    )
    completion = FrozenSemanticCompletion()
    _install_openwebui_completion(monkeypatch, completion)
    _stabilize_canonical_capacity(monkeypatch)
    pipe = Pipe()
    _configure_pipe(pipe, tmp_path / f"source-{os.getpid()}")

    content, result, first_manifest = _run_product_turn(
        pipe, pdf_bytes=pdf_bytes, completion=completion
    )

    _assert_product_result(content, result, first_manifest, locator)


def test_bundled_pipe_runs_real_tbank_to_open_long(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    maintained = {
        name: module
        for name, module in sys.modules.items()
        if name == "broker_reports_gate1" or name.startswith("broker_reports_gate1.")
    }
    for name in maintained:
        sys.modules.pop(name, None)
    try:
        spec = importlib.util.spec_from_file_location(
            "issue317_tbank_pipe_bundle", BUNDLE_PATH
        )
        assert spec is not None and spec.loader is not None
        bundled = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bundled)
        pdf_bytes, _digest = tbank_fixtures._public_tbank_control()
        locator = FrozenLocatorProvider()
        provider_module = importlib.import_module(
            "broker_reports_gate1.pdf_table_locator_provider"
        )
        monkeypatch.setattr(
            provider_module.PdfTableLocatorProviderFactory,
            "create_for_openwebui",
            lambda _self, _request: locator,
        )
        completion = FrozenSemanticCompletion()
        _install_openwebui_completion(monkeypatch, completion)
        _stabilize_canonical_capacity(monkeypatch)
        pipe = bundled.Pipe()
        _configure_pipe(pipe, tmp_path / f"bundle-{os.getpid()}")

        content, result, first_manifest = _run_product_turn(
            pipe, pdf_bytes=pdf_bytes, completion=completion
        )

        _assert_product_result(content, result, first_manifest, locator)
    finally:
        for name in list(sys.modules):
            if name == "broker_reports_gate1" or name.startswith(
                "broker_reports_gate1."
            ):
                sys.modules.pop(name, None)
        sys.modules.update(maintained)
