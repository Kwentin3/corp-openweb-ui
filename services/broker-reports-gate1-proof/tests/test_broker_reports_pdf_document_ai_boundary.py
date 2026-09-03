from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import io
import inspect
import socket
import sys
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest

from broker_reports_gate1.inputs import FileInput
from broker_reports_gate1.normalizer import Gate1Normalizer
from broker_reports_gate1.pdf_document_ai import (
    PDF_DOCUMENT_AI_NOT_CONFIGURED,
    PdfDocumentExtraction,
    PdfDocumentExtractorFactory,
    PdfDocumentImageRef,
    PdfSourceContext,
    UnconfiguredPdfDocumentExtractor,
)
from openwebui_actions.broker_reports_gate1_pipe import Pipe


REPO_ROOT = Path(__file__).resolve().parents[3]
PUBLIC_PDF = next(
    (REPO_ROOT / "docs" / "reports" / "2026-09-02" / "artifacts").glob(
        "*/fidelity/source.pdf"
    )
)
BUNDLED_PIPE_PATH = (
    REPO_ROOT
    / "services"
    / "broker-reports-gate1-proof"
    / "openwebui_actions"
    / "broker_reports_gate1_pipe_bundled.py"
)


def _input(pdf_bytes: bytes) -> FileInput:
    return FileInput.from_bytes(
        private_ref="public-pdf-boundary-test",
        filename="public-sample.pdf",
        content=pdf_bytes,
        mime_type="application/pdf",
        source_kind="synthetic",
    )


class _OfflineFixtureExtractor:
    def extract(
        self,
        pdf_bytes: bytes,
        source_context: PdfSourceContext,
    ) -> PdfDocumentExtraction:
        markdown = b"# Exact offline fixture\n\n| A | B |\n|---|---|\n| 1 | 2 |\n"
        return PdfDocumentExtraction(
            source_pdf_sha256=hashlib.sha256(pdf_bytes).hexdigest(),
            page_numbers=tuple(range(1, source_context.preflight_page_count + 1)),
            markdown_bytes=markdown,
            markdown_sha256=hashlib.sha256(markdown).hexdigest(),
            image_refs=(),
            provider_id="offline_fixture_provider",
            model_id="offline_fixture_model",
            adapter_id="offline_fixture_adapter_v1",
            qualification_status="offline_fixture",
            usage_page_count=source_context.preflight_page_count,
            safe_technical_summary=(
                ("markdown_bytes", len(markdown)),
                ("pages_count", source_context.preflight_page_count),
            ),
        )


class _SecondOfflineFixtureExtractor(_OfflineFixtureExtractor):
    pass


def test_production_factory_is_sole_fail_closed_composition() -> None:
    extractor = PdfDocumentExtractorFactory.create()

    assert isinstance(extractor, UnconfiguredPdfDocumentExtractor)
    assert "_pdf_document_extractor" in inspect.signature(Gate1Normalizer).parameters
    assert "pdf_document_extractor" not in inspect.signature(Gate1Normalizer).parameters


def test_unconfigured_pdf_is_terminal_before_network_and_creates_no_downstream() -> None:
    pdf_bytes = PUBLIC_PDF.read_bytes()

    with patch.object(socket, "create_connection", side_effect=AssertionError("network")), patch.object(
        socket.socket,
        "connect",
        side_effect=AssertionError("network"),
    ):
        result = Gate1Normalizer().normalize([_input(pdf_bytes)])

    blocker_codes = {
        item["code"] for item in result.package["normalization_blockers"]
    }
    assert PDF_DOCUMENT_AI_NOT_CONFIGURED in blocker_codes
    assert result.package["private_normalized_source_payloads"] == []
    assert result.package["private_normalized_source_units"] == []
    assert result.package["private_normalized_table_projections"] == []
    assert result.package["taxonomy_candidates"] == []
    assert "canonical_artifacts" not in result.package
    assert "source_facts" not in result.package
    assert "gate1_issue_ledger" not in result.package
    assert "document_usage_classification" not in result.package
    assert "domain_context_packet" not in result.package
    assert "domain_ingestion_summary" not in result.package


def test_archive_containing_only_pdf_is_terminal_before_domain_ingestion() -> None:
    archive_buffer = io.BytesIO()
    with zipfile.ZipFile(archive_buffer, "w") as archive:
        archive.writestr("public-sample.pdf", PUBLIC_PDF.read_bytes())

    result = Gate1Normalizer().normalize(
        [
            FileInput.from_bytes(
                private_ref="public-pdf-archive-boundary-test",
                filename="public-sample.zip",
                content=archive_buffer.getvalue(),
                mime_type="application/zip",
                source_kind="synthetic",
            )
        ]
    )

    assert PDF_DOCUMENT_AI_NOT_CONFIGURED in {
        item["code"] for item in result.package["normalization_blockers"]
    }
    assert result.package["normalization_run"]["run_status"] == "failed_safe"
    assert "gate1_issue_ledger" not in result.package
    assert "document_usage_classification" not in result.package
    assert "domain_context_packet" not in result.package
    assert "domain_ingestion_summary" not in result.package


def test_archive_with_two_duplicate_pdfs_is_terminal_and_valid_before_downstream() -> None:
    archive_buffer = io.BytesIO()
    with zipfile.ZipFile(archive_buffer, "w") as archive:
        archive.writestr("first.pdf", PUBLIC_PDF.read_bytes())
        archive.writestr("second.pdf", PUBLIC_PDF.read_bytes())

    result = Gate1Normalizer().normalize(
        [
            FileInput.from_bytes(
                private_ref="public-multi-pdf-archive-boundary-test",
                filename="public-multi-pdf.zip",
                content=archive_buffer.getvalue(),
                mime_type="application/zip",
                source_kind="synthetic",
            )
        ]
    )

    pdf_documents = [
        item
        for item in result.package["document_inventory"]["documents"]
        if item["container_format"] == "pdf"
    ]
    pdf_blockers = [
        item
        for item in result.package["normalization_blockers"]
        if item["code"] == PDF_DOCUMENT_AI_NOT_CONFIGURED
    ]
    assert len(pdf_documents) == 2
    assert len(pdf_blockers) == 2
    assert pdf_documents[1]["duplicate_of_document_id"] == pdf_documents[0]["document_id"]
    assert result.package["normalization_run"]["run_status"] == "failed_safe"
    assert result.package["validation_result"]["status"] == "passed"
    for key in (
        "canonical_artifacts",
        "source_facts",
        "gate1_issue_ledger",
        "document_usage_classification",
        "domain_context_packet",
        "domain_ingestion_summary",
    ):
        assert key not in result.package


def _pipe_file(
    file_id: str,
    filename: str,
    mime_type: str,
    content_bytes: bytes,
) -> dict:
    return {
        "type": "file",
        "file": {
            "id": file_id,
            "filename": filename,
            "mime_type": mime_type,
            "content_bytes": content_bytes,
        },
    }


def _run_mixed_pipe(
    pipe_variant: str,
    tmp_path: Path,
    files: list[dict],
) -> tuple[object, str, int]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    maintained_modules = {
        name: module
        for name, module in sys.modules.items()
        if name == "broker_reports_gate1" or name.startswith("broker_reports_gate1.")
    }
    if pipe_variant == "bundled":
        for name in maintained_modules:
            del sys.modules[name]
        spec = importlib.util.spec_from_file_location(
            "broker_reports_gate1_pdf_boundary_bundle_test",
            BUNDLED_PIPE_PATH,
        )
        if spec is None or spec.loader is None:
            raise AssertionError("could not load bundled Gate 1 Pipe")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        pipe_type = module.Pipe
    else:
        pipe_type = Pipe
    pipe = pipe_type()
    pipe.valves.artifact_store_path = str(tmp_path / "artifacts.sqlite3")
    pipe.valves.artifact_payload_root = str(tmp_path / "payloads")

    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("mixed PDF route must not call the network")

    async def run() -> tuple[str, int]:
        with (
            patch.object(
                pipe,
                "_maybe_run_passport_stage",
                wraps=pipe._maybe_run_passport_stage,
            ) as passport_stage,
            patch.object(socket, "create_connection", side_effect=forbidden),
            patch.object(socket.socket, "connect", side_effect=forbidden),
        ):
            content = await pipe.pipe(
                {
                    "messages": [
                        {
                            "role": "user",
                            "content": "Gate 1 mixed normalization",
                            "files": files,
                        }
                    ]
                },
                __user__={"id": "mixed-pdf-boundary-user"},
                __metadata__={
                    "chat_id": "mixed-pdf-boundary-chat",
                    "model_id": "broker_reports_gate1_pipe_test",
                },
            )
            return content, passport_stage.await_count

    try:
        content, passport_await_count = asyncio.run(run())
    finally:
        if pipe_variant == "bundled":
            for name in list(sys.modules):
                if name == "broker_reports_gate1" or name.startswith(
                    "broker_reports_gate1."
                ):
                    del sys.modules[name]
            sys.modules.update(maintained_modules)
    return pipe, content, passport_await_count


@pytest.mark.parametrize("pipe_variant", ("maintained", "bundled"))
def test_mixed_csv_and_pdf_continues_reduced_subset_in_production_pipe(
    pipe_variant: str,
    tmp_path: Path,
) -> None:
    pipe, content, passport_await_count = _run_mixed_pipe(
        pipe_variant,
        tmp_path,
        [
            _pipe_file(
                "mixed-csv",
                "operations.csv",
                "text/csv",
                b"symbol,quantity\nSYNTH-A,1\n",
            ),
            _pipe_file(
                "mixed-pdf",
                "statement.pdf",
                "application/pdf",
                PUBLIC_PDF.read_bytes(),
            ),
        ],
    )

    report = pipe.last_safe_report
    assert report is not None
    documents = {item["container_format"]: item for item in report["documents"]}
    included = set(report["gate2_handoff"]["included_document_ids"])
    assert report["run_status"] == "completed_with_blockers"
    assert report["validation_result"]["status"] == "passed"
    assert report["gate2_handoff_status"] == "ready_with_reduced_subset"
    assert documents["csv"]["document_id"] in included
    assert documents["pdf"]["document_id"] not in included
    assert report["private_artifact_summary"]["private_normalized_source_units_count"] > 0
    assert report["domain_context_packet"] is not None
    assert passport_await_count == 1
    assert pipe.last_workload_snapshot["state"] == "completed"
    assert pipe.last_workload_snapshot["cleanup_status"] == "cleaned"
    assert "Gate 1 stopped at the PDF Document AI boundary" not in content


@pytest.mark.parametrize("pipe_variant", ("maintained", "bundled"))
def test_archive_pdf_and_xml_continues_xml_in_production_pipe(
    pipe_variant: str,
    tmp_path: Path,
) -> None:
    mixed_archive_buffer = io.BytesIO()
    with zipfile.ZipFile(mixed_archive_buffer, "w") as archive:
        archive.writestr("statement.pdf", PUBLIC_PDF.read_bytes())
        archive.writestr(
            "operations.xml",
            b"<operations><quantity>1</quantity></operations>",
        )
    control_archive_buffer = io.BytesIO()
    with zipfile.ZipFile(control_archive_buffer, "w") as archive:
        archive.writestr(
            "operations.xml",
            b"<operations><quantity>1</quantity></operations>",
        )

    pipe, content, passport_await_count = _run_mixed_pipe(
        pipe_variant,
        tmp_path / "mixed",
        [
            _pipe_file(
                "mixed-archive",
                "mixed.zip",
                "application/zip",
                mixed_archive_buffer.getvalue(),
            )
        ],
    )
    control_pipe, _control_content, control_passport_await_count = _run_mixed_pipe(
        pipe_variant,
        tmp_path / "control",
        [
            _pipe_file(
                "xml-only-archive",
                "xml-only.zip",
                "application/zip",
                control_archive_buffer.getvalue(),
            )
        ],
    )

    report = pipe.last_safe_report
    control_report = control_pipe.last_safe_report
    assert report is not None
    assert control_report is not None
    documents = {item["container_format"]: item for item in report["documents"]}
    eligibility = {
        item["document_id"]: item
        for item in report["document_source_eligibility"]["entries"]
    }
    control_xml_document = next(
        item
        for item in control_report["documents"]
        if item["container_format"] == "xml"
    )
    control_xml_eligibility = next(
        item
        for item in control_report["document_source_eligibility"]["entries"]
        if item["document_id"] == control_xml_document["document_id"]
    )
    xml_eligibility = eligibility[documents["xml"]["document_id"]]
    pdf_eligibility = eligibility[documents["pdf"]["document_id"]]
    assert report["run_status"] == "completed_with_blockers"
    assert report["validation_result"]["status"] == "passed"
    assert report["gate2_handoff_status"] == control_report["gate2_handoff_status"]
    assert report["gate2_handoff_mode"] == control_report["gate2_handoff_mode"]
    assert {
        key: xml_eligibility[key]
        for key in (
            "source_eligibility",
            "can_enter_gate2",
            "reason_codes",
            "review_action",
        )
    } == {
        key: control_xml_eligibility[key]
        for key in (
            "source_eligibility",
            "can_enter_gate2",
            "reason_codes",
            "review_action",
        )
    }
    assert pdf_eligibility["source_eligibility"] == "excluded_from_gate2"
    assert pdf_eligibility["reason_codes"] == [PDF_DOCUMENT_AI_NOT_CONFIGURED]
    private_summary = report["private_artifact_summary"]
    control_private_summary = control_report["private_artifact_summary"]
    for key in (
        "private_normalized_slices_count",
        "private_normalized_source_payloads_count",
        "private_normalized_source_units_count",
        "private_normalized_table_projections_count",
        "full_source_raw_content_chat_visible",
        "chat_visible_raw_slice_content",
    ):
        assert private_summary[key] == control_private_summary[key]
    assert private_summary["private_normalized_source_units_count"] > 0
    assert report["domain_context_packet"] is not None
    assert passport_await_count == 1
    assert control_passport_await_count == 1
    assert pipe.last_workload_snapshot["state"] == "completed"
    assert pipe.last_workload_snapshot["cleanup_status"] == "cleaned"
    assert "Gate 1 stopped at the PDF Document AI boundary" not in content


def test_pipe_returns_unconfigured_pdf_before_any_provider_or_semantic_artifact(
    tmp_path: Path,
) -> None:
    pdf_bytes = PUBLIC_PDF.read_bytes()
    pipe = Pipe()
    pipe.valves.artifact_store_path = str(tmp_path / "artifacts.sqlite3")
    pipe.valves.artifact_payload_root = str(tmp_path / "payloads")
    pipe.valves.passport_enabled = True
    pipe.valves.passport_model_id = "must-not-run"
    pipe.valves.clarification_enabled = True
    pipe.valves.clarification_model_id = "must-not-run"

    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("downstream stage must not run")

    body = {
        "messages": [
            {
                "role": "user",
                "content": "Gate 1 normalization",
                "files": [
                    {
                        "type": "file",
                        "file": {
                            "id": "pdf-document-ai-boundary",
                            "filename": "boundary.pdf",
                            "mime_type": "application/pdf",
                            "content_bytes": pdf_bytes,
                        },
                    }
                ],
            }
        ]
    }

    async def run() -> str:
        with (
            patch.object(pipe, "_maybe_run_passport_stage", side_effect=forbidden),
            patch.object(pipe, "_maybe_run_clarification_stage", side_effect=forbidden),
            patch.object(pipe, "_maybe_run_ndfl_gate3", side_effect=forbidden),
            patch.object(
                pipe, "_openwebui_completion_dependencies", side_effect=forbidden
            ),
            patch.object(socket, "create_connection", side_effect=forbidden),
            patch.object(socket.socket, "connect", side_effect=forbidden),
        ):
            return await pipe.pipe(
                body,
                __user__={"id": "pdf-boundary-user"},
                __metadata__={
                    "chat_id": "pdf-boundary-chat",
                    "model_id": "broker_reports_gate1_pipe_test",
                },
            )

    content = asyncio.run(run())

    assert content
    assert pipe.last_artifact_manifest is not None
    artifact_types = set(pipe.last_artifact_manifest["artifact_refs_by_type"])
    assert artifact_types.isdisjoint(
        {
            "full_source_v0",
            "canonical_artifact_v1",
            "normalized_source_facts_v0",
            "gate1_issue_ledger_v0",
            "document_usage_classification_v0",
            "domain_context_packet_v0",
            "domain_ingestion_summary_v0",
        }
    )
    assert pipe.last_safe_report is not None
    assert {item["code"] for item in pipe.last_safe_report["blockers"]} >= {
        PDF_DOCUMENT_AI_NOT_CONFIGURED
    }
    assert PDF_DOCUMENT_AI_NOT_CONFIGURED in content
    assert "PDF Document AI is not configured" in content
    assert "successfully processed" not in content.lower()


def test_offline_adapters_with_same_envelope_have_identical_representation_handoff() -> None:
    pdf_bytes = PUBLIC_PDF.read_bytes()
    first = Gate1Normalizer(
        _pdf_document_extractor=_OfflineFixtureExtractor()
    ).normalize([_input(pdf_bytes)])
    second = Gate1Normalizer(
        _pdf_document_extractor=_SecondOfflineFixtureExtractor()
    ).normalize([_input(pdf_bytes)])

    assert first.package["private_normalized_source_payloads"] == second.package[
        "private_normalized_source_payloads"
    ]
    assert first.package["private_normalized_source_units"] == second.package[
        "private_normalized_source_units"
    ]
    assert first.package["private_normalized_table_projections"] == []
    payload = first.package["private_normalized_source_payloads"][0]
    assert payload["normalized_projection"]["text"].startswith(
        "# Exact offline fixture"
    )
    assert payload["format_reason_codes"] == [
        "document_ai_content_not_semantically_parsed"
    ]


@pytest.mark.parametrize(
    "local_ref",
    (
        "../image.png",
        "images/../../image.png",
        r"images\..\image.png",
        r"C:\images\image.png",
        r"C:images\image.png",
        r"\\server\share\image.png",
        r"\images\image.png",
        "/images/image.png",
    ),
)
def test_image_ref_rejects_escape_and_absolute_path_mutations(local_ref: str) -> None:
    with pytest.raises(ValueError, match="pdf_document_image_ref_must_be_closed_local"):
        PdfDocumentImageRef(local_ref=local_ref, sha256="0" * 64)


@pytest.mark.parametrize(
    ("summary", "error"),
    (
        ((("pages_count", "one"),), "pdf_document_safe_summary_count_invalid"),
        ((("pages_count", True),), "pdf_document_safe_summary_count_invalid"),
        ((("pages_count", -1),), "pdf_document_safe_summary_count_invalid"),
        ((("pages_count", 2),), "pdf_document_safe_summary_count_mismatch"),
        ((("markdown_bytes", 0),), "pdf_document_safe_summary_count_mismatch"),
    ),
)
def test_safe_summary_rejects_text_boolean_negative_and_mismatched_counts(
    summary: tuple[tuple[str, object], ...],
    error: str,
) -> None:
    markdown = b"fixture"
    with pytest.raises(ValueError, match=error):
        PdfDocumentExtraction(
            source_pdf_sha256="0" * 64,
            page_numbers=(1,),
            markdown_bytes=markdown,
            markdown_sha256=hashlib.sha256(markdown).hexdigest(),
            image_refs=(),
            provider_id="offline_fixture_provider",
            model_id="offline_fixture_model",
            adapter_id="offline_fixture_adapter_v1",
            qualification_status="offline_fixture",
            usage_page_count=1,
            safe_technical_summary=summary,  # type: ignore[arg-type]
        )
