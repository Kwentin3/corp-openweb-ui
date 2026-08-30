from __future__ import annotations

import ast
import copy
import hashlib
import inspect
import json
import threading
from collections import Counter
from dataclasses import FrozenInstanceError
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from broker_reports_gate1.full_source import (
    FullSourceArtifactBuilder,
    FullSourceArtifactFactory,
    FullSourceBuildResult,
)
from broker_reports_gate1.gate2_model_contracts import (
    Gate2SourceFactRuntimeError,
)
from broker_reports_gate1.gate2_provider_adapters import (
    Gate2OpenWebUIProviderConnection,
    Gate2OpenWebUIProviderConnectionResolver,
)
from broker_reports_gate1.logical_row_table_recovery import (
    LogicalRowTableFactory,
    LogicalRowTableRecoveryRuntime,
)
from broker_reports_gate1.managed_document_contracts_v2 import (
    SCHEMA_CANONICAL_SHA256,
    ManagedDocumentContractV2Error,
    ManagedDocumentContractV2Validator,
    _reviewed_source_bound_inventory,
    _source_unit_ledger_inventory,
)
from broker_reports_gate1.managed_document_contracts import (
    compute_document_integrity_sha256,
)
from broker_reports_gate1.managed_pdf_document_v2 import (
    FACTORY_REQUIRED,
    FORBIDDEN,
    ManagedPdfDocumentV2Error,
    ManagedPdfDocumentV2Factory,
    _bind_source_unit_ledger,
    _managed_document_recovery_projection,
)
from broker_reports_gate1.pdf_document_visual_adjudication import (
    PdfDocumentVisualAdjudicationError,
    PdfDocumentVisualAdjudicationFactory,
)
from broker_reports_gate1.pdf_layout import (
    PDF_LAYOUT_POLICY_VERSION,
    PdfLayoutParserConfig,
)
from broker_reports_gate1.pdf_table_raster import PdfTableRasterFactory
from tests.test_broker_reports_logical_row_table_recovery import (
    _source_bound_case,
)
from tests.test_broker_reports_pdf_document_visual_adjudication import (
    _numeric_headerless_case,
    _two_page_observations,
)
from tests.test_broker_reports_pdf_layout_slice2 import (
    _aligned_table_pdf,
    _ruled_table_pdf,
)


SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = SERVICE_ROOT.parents[1]
SCHEMA_PATH = (
    REPOSITORY_ROOT
    / "docs"
    / "stage2"
    / "contracts"
    / "BROKER_REPORTS_MANAGED_DOCUMENT.v2.schema.json"
)
MODULE_PATH = (
    SERVICE_ROOT
    / "broker_reports_gate1"
    / "managed_pdf_document_v2.py"
)
# Frozen by executing the real legacy builder at PR3 exact head 1ce206f over
# `_ruled_table_pdf()` with the source identity used by the parity test below.
PR3_LEGACY_CONTENT_SHA256 = (
    "b1d556c1090fda2e5283fd9bcbd23c0ed033d33512dd5379f3c739f8dd9403f8"
)
PR3_LEGACY_INTEGRITY_SHA256 = (
    "110fb0447a60c9b69a69cf24861ac11f6658266dee1392b9af23c419a06974df"
)
PR3_LEGACY_CANONICAL_SHA256 = (
    "15f0446b2e7755ad1997e292bcacaba88f6f57ba41fc8d7c1931c4283b5bad05"
)
SOURCE_CHAIN_AUTHORITY_INTEGRITY_SHA256 = (
    "dbc78ba3314eeece841dece22fa735d86929fe9851ca7ce100b2a5e4ed70b70f"
)
SOURCE_CHAIN_AUTHORITY_CANONICAL_SHA256 = (
    "62d75d2a6f7a5f12ffe1b143b2c5331bdb1efd0667069d32d055fd80a7b4dd50"
)
UNRESOLVED_REGION_AUTHORITY_INTEGRITY_SHA256 = (
    "fd09a87841254caa8c4b5a30491e4bb1e7f67f619dc9418d0fcd3871a2789c23"
)
UNRESOLVED_REGION_AUTHORITY_CANONICAL_SHA256 = (
    "6a17073f38618907bb38d60277c7935157a3ca1131fcbc9be8778a7fd89bc3c0"
)
PR3_LEGACY_LAYOUT_CONFIG_REF = "pdflayoutcfg_552ad5c15996174bb154a2a0"


class _GeminiBoundary:
    def __init__(self, generations: list[dict[str, Any]]) -> None:
        self.generations = copy.deepcopy(generations)
        self.requests: list[dict[str, Any]] = []
        boundary = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802
                length = int(self.headers.get("Content-Length", "0"))
                body = json.loads(self.rfile.read(length).decode("utf-8"))
                boundary.requests.append(
                    {"path": self.path, "body": copy.deepcopy(body)}
                )
                if self.path.split("?", 1)[0].endswith(":countTokens"):
                    payload = {
                        "totalTokens": 100,
                        "promptTokensDetails": [
                            {"modality": "IMAGE", "tokenCount": 100}
                        ],
                    }
                else:
                    value = boundary.generations.pop(0)
                    payload = {
                        "responseId": "managed-document-visual-response",
                        "modelVersion": "models/gemini-3.5-flash",
                        "candidates": [
                            {
                                "content": {
                                    "parts": [
                                        {
                                            "text": json.dumps(
                                                value,
                                                separators=(",", ":"),
                                                sort_keys=True,
                                            )
                                        }
                                    ]
                                },
                                "finishReason": "STOP",
                            }
                        ],
                        "usageMetadata": {
                            "promptTokenCount": 100,
                            "candidatesTokenCount": 20,
                            "totalTokenCount": 120,
                        },
                    }
                encoded = json.dumps(payload).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

            def log_message(self, _format: str, *_args: Any) -> None:
                return

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(
            target=self.server.serve_forever,
            daemon=True,
        )

    def __enter__(self) -> "_GeminiBoundary":
        self.thread.start()
        return self

    def __exit__(self, *_args: Any) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        assert not self.thread.is_alive()
        assert self.generations == []

    @property
    def connection(self) -> Gate2OpenWebUIProviderConnection:
        host, port = self.server.server_address
        return Gate2OpenWebUIProviderConnection(
            base_url=f"http://{host}:{port}/v1beta/openai",
            api_key="test-only-secret",
        )


def _openwebui_request(
    *,
    urls: list[str] | None = None,
    keys: list[str] | None = None,
) -> Any:
    configured_urls = urls or [
        "https://generativelanguage.googleapis.com/v1beta/openai"
    ]
    configured_keys = keys or ["test-only-openwebui-admin-secret"]
    return SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                config=SimpleNamespace(
                    OPENAI_API_BASE_URLS=configured_urls,
                    OPENAI_API_KEYS=configured_keys,
                    OPENAI_API_CONFIGS={
                        str(index): {"enable": True}
                        for index in range(len(configured_urls))
                    },
                )
            )
        )
    )


def _route_openwebui_resolver_to_boundary(
    monkeypatch: pytest.MonkeyPatch,
    *,
    request: Any,
    boundary: _GeminiBoundary,
) -> list[Any]:
    calls: list[Any] = []

    def resolve(
        owner: Gate2OpenWebUIProviderConnectionResolver,
        profile: Any,
    ) -> Gate2OpenWebUIProviderConnection:
        assert owner.request is request
        assert profile.profile_id == "google_gemini"
        assert "models/gemini-3.5-flash" in profile.approved_model_ids
        calls.append(profile)
        return boundary.connection

    monkeypatch.setattr(
        Gate2OpenWebUIProviderConnectionResolver,
        "resolve",
        resolve,
    )
    return calls


def _schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _document_id_for_source_ref(source_artifact_ref: str) -> str:
    canonical = json.dumps(
        ["private_source_artifact_identity", source_artifact_ref],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"document_pdf_{hashlib.sha256(canonical).hexdigest()[:24]}"


def _managed_full_source(
    pdf_bytes: bytes,
    *,
    source_artifact_ref: str,
) -> FullSourceBuildResult:
    checksum = hashlib.sha256(pdf_bytes).hexdigest()
    return FullSourceArtifactFactory().create().build(
        normalization_run_id=f"normrun_managed_{checksum[:24]}",
        document_id=_document_id_for_source_ref(source_artifact_ref),
        profile_id="broker_reports_managed_document_v2",
        container_format="pdf",
        content_bytes=pdf_bytes,
        source_checksum_sha256=checksum,
    )


def _count_real_full_source_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    original = FullSourceArtifactBuilder.build

    def counting_build(
        owner: FullSourceArtifactBuilder,
        **kwargs: Any,
    ) -> FullSourceBuildResult:
        result = original(owner, **kwargs)
        calls.append(
            {
                "kwargs": copy.deepcopy(kwargs),
                "result": copy.deepcopy(result),
            }
        )
        return result

    monkeypatch.setattr(FullSourceArtifactBuilder, "build", counting_build)
    return calls


def _count_real_recovery_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    original = LogicalRowTableRecoveryRuntime._recover

    def counting_recover(
        owner: LogicalRowTableRecoveryRuntime,
        projection: dict[str, Any],
        **kwargs: Any,
    ):
        calls.append(copy.deepcopy(kwargs))
        return original(owner, projection, **kwargs)

    monkeypatch.setattr(
        LogicalRowTableRecoveryRuntime,
        "_recover",
        counting_recover,
    )
    return calls


def test_policy_identity_migration_preserves_frozen_pr3_structure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pdf_bytes = _ruled_table_pdf()
    assert hashlib.sha256(pdf_bytes).hexdigest() == PR3_LEGACY_CONTENT_SHA256
    calls = _count_real_full_source_calls(monkeypatch)

    result = ManagedPdfDocumentV2Factory().create(_schema()).build(
        pdf_bytes,
        source_artifact_ref="private_pdf_pr3_legacy_parity",
    )

    assert len(calls) == 1
    assert result.status == "COMPLETE"
    assert (
        PDF_LAYOUT_POLICY_VERSION
        == "pdfplumber_layout_policy_v5_unresolved_table_regions"
    )
    assert PdfLayoutParserConfig().config_ref != PR3_LEGACY_LAYOUT_CONFIG_REF
    assert result.managed_document.integrity_sha256 != PR3_LEGACY_INTEGRITY_SHA256
    assert result.managed_document.integrity_sha256 != SOURCE_CHAIN_AUTHORITY_INTEGRITY_SHA256
    assert (
        result.managed_document.integrity_sha256
        == UNRESOLVED_REGION_AUTHORITY_INTEGRITY_SHA256
    )
    assert (
        hashlib.sha256(result.managed_document.canonical_json_bytes()).hexdigest()
        != PR3_LEGACY_CANONICAL_SHA256
    )
    assert (
        hashlib.sha256(result.managed_document.canonical_json_bytes()).hexdigest()
        != SOURCE_CHAIN_AUTHORITY_CANONICAL_SHA256
    )
    assert (
        hashlib.sha256(result.managed_document.canonical_json_bytes()).hexdigest()
        == UNRESOLVED_REGION_AUTHORITY_CANONICAL_SHA256
    )
    assert result.safe_diagnostics["logical_tables_total"] == 1
    assert result.safe_diagnostics["logical_rows_total"] == 3
    assert result.safe_diagnostics["source_words_total"] == 14
    assert result.safe_diagnostics["table_words_total"] == 9
    assert result.safe_diagnostics["paragraph_words_total"] == 5


def test_adjudicated_route_uses_one_source_and_recovery_then_seals_reviewed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pdf_bytes, _, _ = _source_bound_case(
        distinct_second_title=True
    )
    source_ref = "private_pdf_adjudicated_title"
    original_full_source = _managed_full_source(
        pdf_bytes,
        source_artifact_ref=source_ref,
    )
    payload = original_full_source.payloads[0]
    observations = _two_page_observations(
        payload,
        second_title=True,
    )
    full_source_calls = _count_real_full_source_calls(monkeypatch)
    recovery_calls = _count_real_recovery_calls(monkeypatch)
    request = _openwebui_request()

    with _GeminiBoundary([observations, observations]) as boundary:
        resolver_calls = _route_openwebui_resolver_to_boundary(
            monkeypatch,
            request=request,
            boundary=boundary,
        )
        result = (
            ManagedPdfDocumentV2Factory()
            .create_adjudicated_for_openwebui(_schema(), request)
            .build(
                pdf_bytes,
                source_artifact_ref=source_ref,
                task_id="managed_document_complete",
                dpi=150,
            )
        )
        requests = copy.deepcopy(boundary.requests)
    tables = [
        block["content"]
        for block in result.managed_document.payload["blocks"]
        if block["block_type"] == "TABLE"
    ]
    reviewed_parts = [
        part["reviewed_source_bound_evidence"]
        for table in tables
        for part in table["source_parts"]
    ]

    assert len(full_source_calls) == 1
    assert len(recovery_calls) == 1
    assert len(resolver_calls) == 1
    assert len(requests) == 4
    count_bodies = [
        request["body"]
        for request in requests
        if request["path"].split("?", 1)[0].endswith(":countTokens")
    ]
    generation_bodies = [
        request["body"]
        for request in requests
        if not request["path"].split("?", 1)[0].endswith(":countTokens")
    ]
    assert len(count_bodies) == len(generation_bodies) == 2
    counted_generation_bodies = [
        copy.deepcopy(body["generateContentRequest"])
        for body in count_bodies
    ]
    assert all(
        body.pop("model") == "models/gemini-3.5-flash"
        for body in counted_generation_bodies
    )
    assert counted_generation_bodies == generation_bodies
    image_sets = [
        [
            part["inlineData"]
            for part in body["contents"][0]["parts"]
            if "inlineData" in part
        ]
        for body in generation_bodies
    ]
    assert image_sets[0] == image_sets[1]
    assert result.status == "COMPLETE"
    assert result.managed_document is not None
    assert len(tables) == 2
    assert len(reviewed_parts) == 2
    assert all(len(item["proposal_sha256"]) == 64 for item in reviewed_parts)
    assert all(
        len(item["raster_manifest_sha256"]) == 64
        for item in reviewed_parts
    )
    assert all(
        row["role_origin"] == "REVIEWED_SOURCE_BOUND"
        and all(
            entry["origin"] == "REVIEWED_SOURCE_BOUND"
            for entry in row["entries"]
        )
        for table in tables
        for row in table["ordered_rows"]
        if row["role"] in {"TABLE_TITLE", "COLUMN_HEADER", "DATA"}
    )
    assert result.safe_diagnostics["unowned_words_total"] == 0
    assert result.safe_diagnostics["multiple_word_owners_total"] == 0
    assert result.safe_diagnostics["paragraph_table_overlap_total"] == 0
    assert result.safe_diagnostics["provider_http_calls"] == 4
    assert result.safe_diagnostics["model_generation_calls"] == 2
    assert result.safe_diagnostics["count_tokens_http_calls"] == 2
    assert result.safe_diagnostics["same_raster_binding"] is True
    assert result.safe_diagnostics["managed_document_created"] is True
    assert result.safe_diagnostics["canonical_artifacts_created"] == 0
    assert result.safe_diagnostics["facts_published"] == 0
    document_coverage = result.managed_document.payload["source"][
        "table_source_unit_coverage"
    ]
    records = [
        unit
        for table in tables
        for part in table["source_parts"]
        for unit in part["covered_source_units"]
    ]
    record_by_ref = {item["unit_ref"]: item for item in records}
    exact_full_source = full_source_calls[0]["result"]
    expected_units = {
        unit["unit_ref"]: unit
        for unit in exact_full_source.units
        if (unit.get("pdf_layout_coverage") or {}).get("owned_word_refs")
    }
    assert len(records) == len(record_by_ref) == len(expected_units) == 3
    assert Counter(
        unit["pdf_unit_type"] for unit in expected_units.values()
    ) == Counter(
        {
            "pdf_table_candidate_unit": 2,
            "pdf_line_cluster_unit": 1,
        }
    )
    title_unit = next(
        unit
        for unit in expected_units.values()
        if unit["pdf_unit_type"] == "pdf_line_cluster_unit"
    )
    page_two_ref = next(
        page["page_ref"]
        for page in exact_full_source.payloads[0][
            "pdf_text_layer_projection"
        ]["page_inventory"]
        if page["page_number"] == 2
    )
    assert title_unit["page_refs"] == [page_two_ref]
    assert [
        len(part["covered_source_units"])
        for table in tables
        for part in table["source_parts"]
    ] == [1, 2]
    assert document_coverage["covered_source_unit_refs"] == sorted(
        expected_units
    )
    assert document_coverage["duplicate_source_unit_refs"] == []
    assert document_coverage["duplicate_source_atom_refs"] == []
    assert document_coverage["duplicate_source_word_refs"] == []
    for unit_ref, source_unit in expected_units.items():
        record = record_by_ref[unit_ref]
        assert record["source_unit_checksum_ref"] == source_unit[
            "source_unit_checksum_ref"
        ]
        assert record["parent_payload_ref"] == source_unit[
            "parent_payload_ref"
        ]
        assert record["page_refs"] == sorted(source_unit["page_refs"])
        assert record["selected_source_atom_refs"] == sorted(
            source_unit["coverage"]["selected_source_refs"]
        )
        assert record["table_contributing_word_refs"] == sorted(
            source_unit["pdf_layout_coverage"]["owned_word_refs"]
        )
    assert document_coverage["covered_source_atom_refs"] == sorted(
        atom
        for record in records
        for atom in record["selected_source_atom_refs"]
    )
    assert document_coverage["covered_source_word_refs"] == sorted(
        word
        for record in records
        for word in record["table_contributing_word_refs"]
    )
    assert len(document_coverage["covered_source_word_refs"]) == 15
    ownership = result.managed_document.payload["source_word_ownership"]
    assert len(ownership) == 15
    anchor_by_id = {
        anchor["anchor_id"]: anchor
        for anchor in result.managed_document.payload["anchors"]
    }
    assert sorted(
        anchor_by_id[item["source_anchor_id"]]["locator"]["source_block_ref"]
        for item in ownership
    ) == document_coverage["covered_source_word_refs"]
    with pytest.raises(
        ManagedDocumentContractV2Error,
        match="managed_document_v2_reviewed_source_bound_public_input_forbidden",
    ):
        ManagedDocumentContractV2Validator(_schema()).seal(
            result.managed_document.payload
        )

    validator = ManagedDocumentContractV2Validator(_schema())
    reviewed_plan = tuple(
        _reviewed_source_bound_inventory(result.managed_document.payload)
    )
    ledger_plan = tuple(
        _source_unit_ledger_inventory(result.managed_document.payload)
    )
    checksum_mutation = copy.deepcopy(result.managed_document.payload)
    checksum_mutation.pop("integrity_sha256")
    checksum_mutation["blocks"][1]["content"]["source_parts"][0][
        "covered_source_units"
    ][0]["source_unit_checksum_ref"] = "srcunitchk_" + "0" * 24
    with pytest.raises(
        ManagedDocumentContractV2Error,
        match="managed_document_v2_source_unit_ledger_plan_mismatch",
    ):
        validator._seal_adjudicated_source_unit_ledger(
            checksum_mutation,
            expected_reviewed_source_bound=reviewed_plan,
            expected_source_unit_ledger=ledger_plan,
        )

    overlap_mutation = copy.deepcopy(result.managed_document.payload)
    overlap_mutation.pop("integrity_sha256")
    overlap_table = next(
        block["content"]
        for block in overlap_mutation["blocks"]
        if block["block_type"] == "TABLE"
    )
    duplicated_unit = copy.deepcopy(
        overlap_table["source_parts"][0]["covered_source_units"][0]
    )
    duplicated_unit["source_unit_checksum_ref"] = "srcunitchk_" + "f" * 24
    overlap_table["source_parts"][0]["covered_source_units"].append(
        duplicated_unit
    )
    with pytest.raises(
        ManagedDocumentContractV2Error,
        match="managed_document_v2_source_unit_part_word_partition_invalid",
    ):
        validator._seal_adjudicated_source_unit_ledger(
            overlap_mutation,
            expected_reviewed_source_bound=reviewed_plan,
            expected_source_unit_ledger=ledger_plan,
        )

    partial_unit = copy.deepcopy(result.managed_document.payload)
    partial_unit["source"].pop("table_source_unit_coverage")
    first_table = next(
        block["content"]
        for block in partial_unit["blocks"]
        if block["block_type"] == "TABLE"
    )
    first_table.pop("covered_source_atom_refs")
    first_table.pop("covered_source_word_refs")
    for part in first_table["source_parts"]:
        part.pop("covered_source_units")
    first_data_row = next(
        row for row in first_table["ordered_rows"] if row["role"] == "DATA"
    )
    first_data_row["entries"] = first_data_row["entries"][1:]
    with pytest.raises(
        ManagedPdfDocumentV2Error,
        match="managed_pdf_v2_source_unit_ledger_partial_unit_forbidden",
    ):
        _bind_source_unit_ledger(
            candidate=partial_unit,
            full_source=exact_full_source,
            source_checksum_sha256=hashlib.sha256(pdf_bytes).hexdigest(),
        )

    public_payload = copy.deepcopy(result.managed_document.payload)
    for table in [
        block["content"]
        for block in public_payload["blocks"]
        if block["block_type"] == "TABLE"
    ]:
        for part in table["source_parts"]:
            part.pop("reviewed_source_bound_evidence", None)
        for row in table["ordered_rows"]:
            if row["role_origin"] == "REVIEWED_SOURCE_BOUND":
                row["role_origin"] = "DETERMINISTIC_DERIVED"
            for entry in row["entries"]:
                if entry["origin"] == "REVIEWED_SOURCE_BOUND":
                    entry["origin"] = "DETERMINISTIC_DERIVED"
    public_payload["integrity_sha256"] = compute_document_integrity_sha256(
        public_payload
    )
    for operation in (
        lambda: validator.validate(public_payload),
        lambda: validator.parse_json(json.dumps(public_payload)),
        lambda: validator.seal(public_payload),
    ):
        with pytest.raises(
            ManagedDocumentContractV2Error,
            match="managed_document_v2_source_unit_ledger_public_input_forbidden",
        ):
            operation()


def test_adjudicated_partial_returns_zero_managed_canonical_and_facts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pdf_bytes, _, _ = _source_bound_case(distinct_second_title=True)
    source_ref = "private_pdf_adjudicated_partial"
    payload = _managed_full_source(
        pdf_bytes,
        source_artifact_ref=source_ref,
    ).payloads[0]
    proposal = _two_page_observations(
        payload,
        second_title=True,
    )
    critic = copy.deepcopy(proposal)
    critic["pages"][1]["tables"] = []
    full_source_calls = _count_real_full_source_calls(monkeypatch)
    recovery_calls = _count_real_recovery_calls(monkeypatch)
    request = _openwebui_request()

    with _GeminiBoundary([proposal, critic]) as boundary:
        resolver_calls = _route_openwebui_resolver_to_boundary(
            monkeypatch,
            request=request,
            boundary=boundary,
        )
        result = (
            ManagedPdfDocumentV2Factory()
            .create_adjudicated_for_openwebui(_schema(), request)
            .build(
                pdf_bytes,
                source_artifact_ref=source_ref,
                task_id="managed_document_partial",
                dpi=150,
            )
        )
        requests = copy.deepcopy(boundary.requests)

    assert result.status == "PARTIAL"
    assert result.managed_document is None
    assert len(full_source_calls) == 1
    assert len(recovery_calls) == 1
    assert len(resolver_calls) == 1
    assert len(requests) == 4
    assert result.safe_diagnostics["provider_http_calls"] == 4
    assert result.safe_diagnostics["model_generation_calls"] == 2
    assert result.safe_diagnostics["count_tokens_http_calls"] == 2
    assert result.safe_diagnostics["same_raster_binding"] is True
    assert result.safe_diagnostics["managed_document_created"] is False
    assert result.safe_diagnostics["whole_table_projection_status"] == "NOT_READY"
    assert result.safe_diagnostics["whole_table_projections_total"] == 0
    assert result.whole_table_projections == ()
    assert result.whole_table_projection_diagnostics == {
        "status": "NOT_READY",
        "issues": [{"code": "managed_whole_table_projection_managed_missing"}],
    }
    assert result.safe_diagnostics["canonical_artifacts_created"] == 0
    assert result.safe_diagnostics["facts_published"] == 0


def test_adjudicated_headerless_continuation_seals_one_whole_unit_table(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pdf_bytes, _, source_payload = _numeric_headerless_case()
    source_ref = "private_pdf_adjudicated_headerless"
    exact_payload = _managed_full_source(
        pdf_bytes,
        source_artifact_ref=source_ref,
    ).payloads[0]
    observations = _two_page_observations(exact_payload)
    full_source_calls = _count_real_full_source_calls(monkeypatch)
    request = _openwebui_request()

    with _GeminiBoundary([observations, observations]) as boundary:
        _route_openwebui_resolver_to_boundary(
            monkeypatch,
            request=request,
            boundary=boundary,
        )
        result = (
            ManagedPdfDocumentV2Factory()
            .create_adjudicated_for_openwebui(_schema(), request)
            .build(
                pdf_bytes,
                source_artifact_ref=source_ref,
                task_id="managed_document_headerless",
            )
        )

    assert source_payload["parser_completeness_status"] == "complete"
    assert result.status == "COMPLETE"
    assert result.managed_document is not None
    tables = [
        block["content"]
        for block in result.managed_document.payload["blocks"]
        if block["block_type"] == "TABLE"
    ]
    assert len(tables) == 1
    assert len(tables[0]["source_parts"]) == 2
    records = [
        unit
        for part in tables[0]["source_parts"]
        for unit in part["covered_source_units"]
    ]
    assert len(records) == 2
    exact_units = full_source_calls[0]["result"].units
    assert {
        unit["pdf_unit_type"]
        for unit in exact_units
        if unit["unit_ref"] in {record["unit_ref"] for record in records}
    } == {"pdf_table_candidate_unit"}
    assert len(tables[0]["covered_source_word_refs"]) == 12
    assert result.safe_diagnostics["whole_table_projection_status"] == "READY"
    assert result.safe_diagnostics["whole_table_projections_total"] == 1
    assert len(result.whole_table_projections) == 1
    projection = result.whole_table_projections[0]
    assert projection["ordered_rows"] == tables[0]["ordered_rows"]
    assert projection["source_part_refs"] == [
        part["source_part_id"] for part in tables[0]["source_parts"]
    ]
    assert projection["continuation_header_row_refs"] == []
    assert projection["receipt"]["continuation_headers_collapsed"] is False
    assert result.safe_diagnostics["canonical_artifacts_created"] == 0
    assert result.safe_diagnostics["facts_published"] == 0


@pytest.mark.parametrize(
    ("mutation", "expected_detail"),
    [
        (
            "checksum",
            "managed_pdf_v2_source_unit_ledger_unit_validation_failed",
        ),
        (
            "atom",
            "managed_pdf_v2_source_unit_ledger_unit_validation_failed",
        ),
        (
            "missing",
            "managed_pdf_v2_source_unit_ledger_unit_inventory_mismatch",
        ),
        (
            "parent",
            "managed_pdf_v2_source_unit_ledger_unit_validation_failed",
        ),
        (
            "payload_checksum",
            "managed_pdf_v2_source_unit_ledger_unit_validation_failed",
        ),
        (
            "normalization_run",
            "managed_pdf_v2_source_unit_ledger_unit_validation_failed",
        ),
        (
            "page",
            "managed_pdf_v2_source_unit_ledger_unit_validation_failed",
        ),
        (
            "source_value",
            "managed_pdf_v2_source_unit_ledger_unit_validation_failed",
        ),
    ],
)
def test_adjudicated_source_unit_mutation_returns_partial_without_managed(
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
    expected_detail: str,
) -> None:
    pdf_bytes, _, _ = _source_bound_case(distinct_second_title=True)
    source_ref = f"private_pdf_ledger_mutation_{mutation}"
    payload = _managed_full_source(
        pdf_bytes,
        source_artifact_ref=source_ref,
    ).payloads[0]
    observations = _two_page_observations(payload, second_title=True)
    original = FullSourceArtifactBuilder.build

    def mutated_build(
        owner: FullSourceArtifactBuilder,
        **kwargs: Any,
    ) -> FullSourceBuildResult:
        built = copy.deepcopy(original(owner, **kwargs))
        if mutation == "missing":
            built.units.pop()
        elif mutation == "checksum":
            built.units[0]["source_unit_checksum_ref"] = (
                "srcunitchk_" + "0" * 24
            )
        elif mutation == "atom":
            built.units[0]["coverage"]["selected_source_refs"][0] = (
                "textseg_" + "0" * 24
            )
        elif mutation == "parent":
            built.units[0]["parent_payload_ref"] = "sourcepayload_forged"
        elif mutation == "payload_checksum":
            built.units[0]["payload_checksum_ref"] = (
                "payloadchk_" + "0" * 24
            )
        elif mutation == "normalization_run":
            built.units[0]["normalization_run_id"] = "normrun_forged"
        elif mutation == "page":
            built.units[0]["page_refs"] = list(built.units[1]["page_refs"])
        else:
            built.units[0]["pdf_layout_source_value_refs"][0] = (
                "pdfvalue_forged"
            )
        return built

    monkeypatch.setattr(FullSourceArtifactBuilder, "build", mutated_build)
    request = _openwebui_request()
    with _GeminiBoundary([observations, observations]) as boundary:
        _route_openwebui_resolver_to_boundary(
            monkeypatch,
            request=request,
            boundary=boundary,
        )
        result = (
            ManagedPdfDocumentV2Factory()
            .create_adjudicated_for_openwebui(_schema(), request)
            .build(
                pdf_bytes,
                source_artifact_ref=source_ref,
                task_id=f"ledger_mutation_{mutation}",
            )
        )

    assert result.status == "PARTIAL"
    assert result.managed_document is None
    assert result.private_diagnostics["detail_code"] == expected_detail
    assert result.safe_diagnostics["managed_document_created"] is False
    assert result.safe_diagnostics["canonical_artifacts_created"] == 0
    assert result.safe_diagnostics["facts_published"] == 0


def test_no_public_fake_owner_full_source_or_ready_evidence_input() -> None:
    factory_parameters = inspect.signature(
        ManagedPdfDocumentV2Factory
    ).parameters
    adjudicated_factory_parameters = inspect.signature(
        ManagedPdfDocumentV2Factory.create_adjudicated_for_openwebui
    ).parameters
    builder = ManagedPdfDocumentV2Factory().create(_schema())
    legacy_parameters = inspect.signature(builder.build).parameters
    adjudicated_builder = (
        ManagedPdfDocumentV2Factory().create_adjudicated_for_openwebui(
            _schema(), _openwebui_request()
        )
    )
    adjudicated_parameters = inspect.signature(
        adjudicated_builder.build
    ).parameters

    assert list(factory_parameters) == ["config"]
    assert list(adjudicated_factory_parameters) == [
        "self",
        "schema",
        "request",
    ]
    assert list(legacy_parameters) == ["content_bytes", "source_artifact_ref"]
    assert list(adjudicated_parameters) == [
        "content_bytes",
        "source_artifact_ref",
        "task_id",
        "dpi",
    ]
    assert not hasattr(builder, "build_with_source_bound_scopes")
    assert not hasattr(ManagedPdfDocumentV2Factory, "create_adjudicated")
    assert not hasattr(
        PdfDocumentVisualAdjudicationFactory,
        "create_with_connection",
    )
    assert not {
        "full_source_factory",
        "logical_row_table_factory",
        "full_source",
        "profile_id",
        "units",
        "summary",
        "reviewed_plan",
        "ready_evidence",
        "source_bound_scope_receipts",
        "source_bound_scope_requests",
        "adjudication_result",
        "recovery",
        "connection",
    }.intersection(
        {
            *factory_parameters,
            *adjudicated_factory_parameters,
            *legacy_parameters,
            *adjudicated_parameters,
        }
    )
    with pytest.raises(TypeError):
        ManagedPdfDocumentV2Factory(full_source_factory=object())  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        PdfDocumentVisualAdjudicationFactory(  # type: ignore[call-arg]
            provider_factory=object()
        )
    assert not hasattr(builder, "full_source_builder")
    assert not hasattr(builder, "recovery_runtime")
    assert not hasattr(builder, "validator")
    with pytest.raises(AttributeError):
        builder.full_source_builder = object()  # type: ignore[attr-defined]
    with pytest.raises(AttributeError):
        builder.recovery_runtime = object()  # type: ignore[attr-defined]
    with pytest.raises(AttributeError):
        builder.validator = object()  # type: ignore[attr-defined]


def test_adjudicated_factory_rejects_local_lookalike_or_ambiguous_admin_connection_before_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    full_source_calls = _count_real_full_source_calls(monkeypatch)
    raster_calls: list[None] = []
    original_raster_create = PdfTableRasterFactory.create

    def counting_raster_create(owner: PdfTableRasterFactory):
        raster_calls.append(None)
        return original_raster_create(owner)

    monkeypatch.setattr(
        PdfTableRasterFactory,
        "create",
        counting_raster_create,
    )
    local = _openwebui_request(
        urls=["http://127.0.0.1:9876/v1beta/openai"],
        keys=["local-test-key"],
    )
    lookalike = _openwebui_request(
        urls=[
            "https://generativelanguage.googleapis.com.attacker.invalid/"
            "v1beta/openai"
        ],
        keys=["lookalike-test-key"],
    )
    traversal = _openwebui_request(
        urls=[
            "https://generativelanguage.googleapis.com/v1beta/"
            "%2e%2e/evil"
        ],
        keys=["traversal-test-key"],
    )
    double_encoded_traversal = _openwebui_request(
        urls=[
            "https://generativelanguage.googleapis.com/v1beta/"
            "%252e%252e/evil"
        ],
        keys=["double-encoded-traversal-test-key"],
    )
    empty_delimiter = _openwebui_request(
        urls=["https://generativelanguage.googleapis.com/v1beta/openai?"],
        keys=["empty-delimiter-test-key"],
    )
    canonical = "https://generativelanguage.googleapis.com/v1beta/openai"
    ambiguous = _openwebui_request(
        urls=[canonical, canonical],
        keys=["first-test-key", "second-test-key"],
    )

    for request in (
        local,
        lookalike,
        traversal,
        double_encoded_traversal,
        empty_delimiter,
        ambiguous,
    ):
        with pytest.raises(Gate2SourceFactRuntimeError) as blocked:
            ManagedPdfDocumentV2Factory().create_adjudicated_for_openwebui(
                _schema(),
                request,
            )
        assert blocked.value.code == "gate2_provider_configuration_blocked"

    assert full_source_calls == []
    assert raster_calls == []


def test_adjudicated_builder_fails_closed_on_nested_provider_mutation_before_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    full_source_calls = _count_real_full_source_calls(monkeypatch)
    request = _openwebui_request()

    with _GeminiBoundary([]) as boundary:
        _route_openwebui_resolver_to_boundary(
            monkeypatch,
            request=request,
            boundary=boundary,
        )
        builder = (
            ManagedPdfDocumentV2Factory()
            .create_adjudicated_for_openwebui(_schema(), request)
        )
        with pytest.raises(FrozenInstanceError):
            builder._adjudicator = object()  # type: ignore[misc]
        with pytest.raises(
            PdfDocumentVisualAdjudicationError,
            match="document_visual_runtime_mutation_forbidden",
        ):
            builder._adjudicator._provider = object()
        builder._adjudicator._provider.connection = (
            Gate2OpenWebUIProviderConnection(
                base_url="http://127.0.0.1:9876/v1beta/openai",
                api_key="attacker-key",
            )
        )
        with pytest.raises(
            PdfDocumentVisualAdjudicationError,
            match="document_visual_provider_authority_mutated",
        ):
            builder.build(
                _ruled_table_pdf(),
                source_artifact_ref="private_pdf_mutated_provider",
                task_id="mutated_provider",
            )

        assert boundary.requests == []
    assert full_source_calls == []


def test_legacy_adapter_rejects_malicious_source_bound_recovery() -> None:
    pdf_bytes = _ruled_table_pdf()
    source_ref = "private_pdf_legacy_malicious_recovery"
    checksum = hashlib.sha256(pdf_bytes).hexdigest()
    payload = _managed_full_source(
        pdf_bytes,
        source_artifact_ref=source_ref,
    ).payloads[0]
    recovered = LogicalRowTableFactory().create().recover(
        payload["pdf_text_layer_projection"],
        source_checksum_sha256=checksum,
        private_evidence_ref=source_ref,
    )
    malicious = copy.deepcopy(recovered)
    malicious.tables[0]["source_parts"][0]["source_bound_scope_ref"] = (
        "tablescopereceipt_" + "0" * 24
    )

    with pytest.raises(
        ManagedPdfDocumentV2Error,
        match="managed_pdf_v2_reviewed_source_bound_legacy_forbidden",
    ):
        _managed_document_recovery_projection(
            malicious,
            allow_reviewed=False,
        )


def test_adjudicated_public_build_rejects_ready_artifact_keywords() -> None:
    builder = ManagedPdfDocumentV2Factory().create_adjudicated_for_openwebui(
        _schema(), _openwebui_request()
    )
    for keyword in (
        "source_bound_scope_requests",
        "adjudication_result",
        "recovery",
        "full_source",
        "reviewed_plan",
    ):
        with pytest.raises(TypeError):
            builder.build(
                _ruled_table_pdf(),
                source_artifact_ref="private_pdf_ready_artifact_rejected",
                task_id="ready_artifact_rejected",
                **{keyword: object()},
            )


def test_factory_rejects_same_id_schema_tampering() -> None:
    tampered_schema = _schema()
    tampered_schema["$defs"]["tableContent"]["additionalProperties"] = True

    with pytest.raises(
        ManagedDocumentContractV2Error,
        match="managed_document_v2_schema_hash_invalid",
    ):
        ManagedPdfDocumentV2Factory().create(tampered_schema)


def test_source_artifact_identity_is_required() -> None:
    with pytest.raises(
        ManagedPdfDocumentV2Error,
        match="managed_pdf_v2_private_source_ref_required",
    ):
        ManagedPdfDocumentV2Factory().create(_schema()).build(
            _ruled_table_pdf()
        )


def test_real_public_factory_has_exact_word_accounting() -> None:
    result = ManagedPdfDocumentV2Factory().create(_schema()).build(
        _ruled_table_pdf(),
        source_artifact_ref="private_pdf_real_accounting",
    )

    assert result.status == "COMPLETE"
    assert result.safe_diagnostics[
        "managed_document_schema_canonical_sha256"
    ] == SCHEMA_CANONICAL_SHA256
    assert result.safe_diagnostics["unowned_words_total"] == 0
    assert result.safe_diagnostics["multiple_word_owners_total"] == 0
    assert result.safe_diagnostics["paragraph_table_overlap_total"] == 0
    assert (
        result.safe_diagnostics["table_words_total"]
        + result.safe_diagnostics["paragraph_words_total"]
        == result.safe_diagnostics["source_words_total"]
    )


def test_inactive_v2_builder_has_no_product_or_bundle_reachability() -> None:
    assert "ManagedPdfDocumentV2Factory.create" in FACTORY_REQUIRED
    assert "PdfLayoutUnitBuilder" in FORBIDDEN
    source = MODULE_PATH.read_text(encoding="utf-8")
    adjudicator_source = (
        SERVICE_ROOT
        / "broker_reports_gate1"
        / "pdf_document_visual_adjudication.py"
    ).read_text(encoding="utf-8")
    assert "create_with_connection" not in source
    assert "create_with_connection" not in adjudicator_source
    assert "create_for_openwebui" in adjudicator_source
    tree = ast.parse(source)
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert "pdf_layout_units" not in imported_modules
    assert "broker_pdf_neutral_tables" not in imported_modules
    assert "table_projection" not in imported_modules
    assert "canonical_artifact" not in imported_modules
    assert "normalizer" not in imported_modules
    assert not any(
        "canonical" in module
        or "_fact" in module
        or "product" in module
        for module in imported_modules
    )
    assert "managed_pdf_document_v2" not in (
        SERVICE_ROOT / "broker_reports_gate1" / "__init__.py"
    ).read_text(encoding="utf-8")
    assert not any(
        "managed_pdf_document_v2" in path.read_text(
            encoding="utf-8",
            errors="ignore",
        )
        for path in (SERVICE_ROOT / "openwebui_actions").glob("*.py")
    )
    reviewed_seal_callers = []
    for path in (SERVICE_ROOT / "broker_reports_gate1").glob("*.py"):
        candidate_tree = ast.parse(path.read_text(encoding="utf-8"))
        if any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "_seal_reviewed_source_bound"
            for node in ast.walk(candidate_tree)
        ):
            reviewed_seal_callers.append(path.name)
    assert reviewed_seal_callers == ["managed_pdf_document_v2.py"]
    adjudicator_consumers = [
        path.name
        for path in (SERVICE_ROOT / "broker_reports_gate1").glob("*.py")
        if path.name != "pdf_document_visual_adjudication.py"
        and "PdfDocumentVisualAdjudicationFactory" in path.read_text(
            encoding="utf-8"
        )
    ]
    assert adjudicator_consumers == ["managed_pdf_document_v2.py"]


def test_unresolved_source_region_stops_managed_before_provider_or_canonical() -> None:
    content = _aligned_table_pdf()
    legacy = ManagedPdfDocumentV2Factory().create(_schema())
    with pytest.raises(
        ManagedPdfDocumentV2Error,
        match="managed_pdf_v2_full_source_projection_incomplete",
    ):
        legacy.build(content, source_artifact_ref="artifact_unresolved_legacy")

    result = (
        ManagedPdfDocumentV2Factory()
        .create_adjudicated_for_openwebui(_schema(), _openwebui_request())
        .build(
            content,
            source_artifact_ref="artifact_unresolved_product",
            task_id="task_unresolved_product",
        )
    )

    assert result.status == "PARTIAL"
    assert result.managed_document is None
    assert result.safe_diagnostics["provider_calls_total"] == 0
    assert result.safe_diagnostics["model_generation_calls"] == 0
    assert result.safe_diagnostics["canonical_artifacts_created"] == 0
    assert result.safe_diagnostics["facts_published"] == 0
    assert result.safe_diagnostics["whole_table_projection_status"] == "NOT_READY"
    assert (
        result.private_diagnostics["detail_code"]
        == "managed_pdf_v2_source_table_region_unresolved"
    )
    assert len(result.private_diagnostics["unresolved_table_region_refs"]) == 1
