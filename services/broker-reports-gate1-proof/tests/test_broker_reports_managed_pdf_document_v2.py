from __future__ import annotations

import ast
import copy
import hashlib
import inspect
import json
from pathlib import Path
from typing import Any

import pytest

from broker_reports_gate1.contracts import sha256_json
from broker_reports_gate1.full_source import (
    FullSourceArtifactBuilder,
    FullSourceArtifactFactory,
    FullSourceBuildResult,
)
from broker_reports_gate1.logical_row_table_recovery import (
    LogicalRowTableFactory,
    LogicalRowTableRecoveryError,
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
from tests.test_broker_reports_logical_row_table_recovery import (
    _page_candidate_refs,
    _scope_request,
    _source_bound_case,
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


def test_scope_bridge_real_owners_seal_reviewed_title_and_header_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pdf_bytes, source_sha256, _ = _source_bound_case(
        distinct_second_title=True
    )
    source_ref = "private_pdf_source_bound_title"
    payload = _managed_full_source(
        pdf_bytes,
        source_artifact_ref=source_ref,
    ).payloads[0]
    projection = payload["pdf_text_layer_projection"]
    first_refs = _page_candidate_refs(payload, 1)
    second_refs = _page_candidate_refs(payload, 2)
    second_page_ref = next(
        page["page_ref"]
        for page in projection["page_inventory"]
        if page["page_number"] == 2
    )
    title_refs = [
        word["word_ref"]
        for word in projection["word_inventory"]
        if word["page_ref"] == second_page_ref
        and word["word_ref"] not in set(second_refs)
    ]
    requests = (
        _scope_request(
            payload=payload,
            pdf_bytes=pdf_bytes,
            source_sha256=source_sha256,
            page_number=1,
            title_refs=[],
            header_ref_groups=[first_refs[:2]],
            body_refs=first_refs[2:],
        ),
        _scope_request(
            payload=payload,
            pdf_bytes=pdf_bytes,
            source_sha256=source_sha256,
            page_number=2,
            title_refs=title_refs,
            header_ref_groups=[second_refs[:2]],
            body_refs=second_refs[2:],
        ),
    )
    calls = _count_real_full_source_calls(monkeypatch)

    result = (
        ManagedPdfDocumentV2Factory()
        .create(_schema())
        .build_with_source_bound_scopes(
            pdf_bytes,
            source_artifact_ref=source_ref,
            source_bound_scope_requests=requests,
        )
    )
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

    assert len(calls) == 1
    assert result.status == "COMPLETE"
    assert len(tables) == 2
    assert {item["proposal_sha256"] for item in reviewed_parts} == {
        sha256_json(request["proposal"]) for request in requests
    }
    assert {item["raster_manifest_sha256"] for item in reviewed_parts} == {
        request["raster_manifest"]["manifest_hash"] for request in requests
    }
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
    with pytest.raises(
        ManagedDocumentContractV2Error,
        match="managed_document_v2_reviewed_source_bound_public_input_forbidden",
    ):
        ManagedDocumentContractV2Validator(_schema()).seal(
            result.managed_document.payload
        )


def test_scope_bridge_model_only_absent_stays_partial_without_join() -> None:
    pdf_bytes, source_sha256, _ = _source_bound_case()
    source_ref = "private_pdf_source_bound_absent"
    payload = _managed_full_source(
        pdf_bytes,
        source_artifact_ref=source_ref,
    ).payloads[0]
    second_refs = _page_candidate_refs(payload, 2)
    requests = (
        _scope_request(
            payload=payload,
            pdf_bytes=pdf_bytes,
            source_sha256=source_sha256,
            page_number=2,
            title_refs=[],
            header_ref_groups=[],
            body_refs=second_refs,
        ),
    )

    result = (
        ManagedPdfDocumentV2Factory()
        .create(_schema())
        .build_with_source_bound_scopes(
            pdf_bytes,
            source_artifact_ref=source_ref,
            source_bound_scope_requests=requests,
        )
    )
    tables = [
        block["content"]
        for block in result.managed_document.payload["blocks"]
        if block["block_type"] == "TABLE"
    ]

    assert result.status == "PARTIAL"
    assert len(tables) == 2
    assert all(len(table["source_parts"]) == 1 for table in tables)
    assert not any(
        row["role_origin"] == "REVIEWED_SOURCE_BOUND"
        or any(
            entry["origin"] == "REVIEWED_SOURCE_BOUND"
            for entry in row["entries"]
        )
        for table in tables
        for row in table["ordered_rows"]
    )
    audit_parts = [
        part["source_bound_audit_evidence"]
        for table in tables
        for part in table["source_parts"]
        if "source_bound_audit_evidence" in part
    ]
    assert len(audit_parts) == 1
    assert audit_parts[0]["structural_authority"] is False
    assert not any(
        "reviewed_source_bound_evidence" in part
        for table in tables
        for part in table["source_parts"]
    )
    assert any(
        issue["code"] == "logical_table_continuation_header_ambiguous"
        for issue in result.managed_document.payload["quality"]["issue_ledger"]
    )
    assert (
        result.safe_diagnostics["table_words_total"]
        + result.safe_diagnostics["paragraph_words_total"]
        == result.safe_diagnostics["source_words_total"]
    )


def test_no_public_fake_owner_full_source_or_ready_evidence_input() -> None:
    factory_parameters = inspect.signature(
        ManagedPdfDocumentV2Factory
    ).parameters
    builder = ManagedPdfDocumentV2Factory().create(_schema())
    legacy_parameters = inspect.signature(builder.build).parameters
    scoped_parameters = inspect.signature(
        builder.build_with_source_bound_scopes
    ).parameters

    assert list(factory_parameters) == ["config"]
    assert list(legacy_parameters) == ["content_bytes", "source_artifact_ref"]
    assert list(scoped_parameters) == [
        "content_bytes",
        "source_artifact_ref",
        "source_bound_scope_requests",
    ]
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
    }.intersection(
        {*factory_parameters, *legacy_parameters, *scoped_parameters}
    )
    with pytest.raises(TypeError):
        ManagedPdfDocumentV2Factory(full_source_factory=object())  # type: ignore[call-arg]
    assert not hasattr(builder, "full_source_builder")
    assert not hasattr(builder, "recovery_runtime")
    assert not hasattr(builder, "validator")
    with pytest.raises(AttributeError):
        builder.full_source_builder = object()  # type: ignore[attr-defined]
    with pytest.raises(AttributeError):
        builder.recovery_runtime = object()  # type: ignore[attr-defined]
    with pytest.raises(AttributeError):
        builder.validator = object()  # type: ignore[attr-defined]


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


def test_scope_bridge_rejects_ready_receipt_shape() -> None:
    with pytest.raises(
        LogicalRowTableRecoveryError,
        match="logical_row_source_bound_scope_requests_invalid",
    ):
        (
            ManagedPdfDocumentV2Factory()
            .create(_schema())
            .build_with_source_bound_scopes(
                _ruled_table_pdf(),
                source_artifact_ref="private_pdf_ready_receipt_rejected",
                source_bound_scope_requests=({"receipt": object()},),
            )
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
