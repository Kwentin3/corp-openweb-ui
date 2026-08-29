from __future__ import annotations

import ast
import copy
import hashlib
import inspect
import json
import threading
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
)
from broker_reports_gate1.managed_pdf_document_v2 import (
    FACTORY_REQUIRED,
    FORBIDDEN,
    ManagedPdfDocumentV2Error,
    ManagedPdfDocumentV2Factory,
    _managed_document_recovery_projection,
)
from broker_reports_gate1.pdf_document_visual_adjudication import (
    PdfDocumentVisualAdjudicationError,
    PdfDocumentVisualAdjudicationFactory,
)
from broker_reports_gate1.pdf_table_raster import PdfTableRasterFactory
from tests.test_broker_reports_logical_row_table_recovery import (
    _source_bound_case,
)
from tests.test_broker_reports_pdf_document_visual_adjudication import (
    _two_page_observations,
)
from tests.test_broker_reports_pdf_layout_slice2 import _ruled_table_pdf


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
        calls.append(copy.deepcopy(kwargs))
        return original(owner, **kwargs)

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


def test_legacy_real_owner_matches_frozen_pr3_output(
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
    assert result.managed_document.integrity_sha256 == PR3_LEGACY_INTEGRITY_SHA256
    assert (
        hashlib.sha256(result.managed_document.canonical_json_bytes()).hexdigest()
        == PR3_LEGACY_CANONICAL_SHA256
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
    payload = _managed_full_source(
        pdf_bytes,
        source_artifact_ref=source_ref,
    ).payloads[0]
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
    with pytest.raises(
        ManagedDocumentContractV2Error,
        match="managed_document_v2_reviewed_source_bound_public_input_forbidden",
    ):
        ManagedDocumentContractV2Validator(_schema()).seal(
            result.managed_document.payload
        )


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
