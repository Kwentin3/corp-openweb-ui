from __future__ import annotations

import importlib.util
import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from broker_reports_gate1.pdf_document_ai_qualification import (
    PDF_DOCUMENT_AI_QUALIFICATION_FIXTURES,
    PdfDocumentAiQualificationError,
    PdfDocumentAiQualificationExecutor,
    PdfDocumentAiQualificationPlanFactory,
)
from broker_reports_gate1.pdf_document_ai import (
    PDF_DOCUMENT_AI_LIVE_QUALIFICATION_REQUIRED,
    PdfDocumentExtractionError,
    PdfDocumentExtractorFactory,
)


SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SERVICE_ROOT.parents[1]
SCRIPT_PATH = SERVICE_ROOT / "scripts" / "live_pdf_document_ai_qualification.py"
HEAD = "a" * 40


def _reader(repository_path: str) -> bytes:
    return (REPO_ROOT / repository_path).read_bytes()


def _plan():
    return PdfDocumentAiQualificationPlanFactory.create(
        repository_head=HEAD,
        fixture_reader=_reader,
    )


def _script_module():
    spec = importlib.util.spec_from_file_location(
        "live_pdf_document_ai_qualification_test", SCRIPT_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_plan_has_exact_closed_two_pdf_allowlist_and_zero_call_receipt() -> None:
    assert PDF_DOCUMENT_AI_QUALIFICATION_FIXTURES == (
        (
            "drivewealth",
            "docs/reports/2026-09-02/artifacts/mistral-public-pairs/drivewealth/source.pdf",
            "738a0279eba3020c9a6cf3a650df254d0a2a8a0800aae80b4889efcc0a8bec57",
        ),
        (
            "fidelity",
            "docs/reports/2026-09-02/artifacts/mistral-public-pairs/fidelity/source.pdf",
            "36a166a5a13e6d6d86b391233023f83f6f7b4d268a4a23fbae01cb81290e3b96",
        ),
    )
    receipt = _plan().safe_receipt()
    assert receipt["fixtures_total"] == 2
    assert receipt["planned_provider_calls_max"] == 2
    assert receipt["provider_calls_total"] == 0
    assert receipt["provider_call_slots_consumed_total"] == 0
    assert receipt["native_config_read"] is False
    assert receipt["api_key_read"] is False
    assert receipt["external_pdf_send_total"] == 0
    assert receipt["production_activation"] is False


def test_plan_fails_closed_on_fixture_mutation() -> None:
    first_path = PDF_DOCUMENT_AI_QUALIFICATION_FIXTURES[0][1]
    with pytest.raises(PdfDocumentAiQualificationError) as caught:
        PdfDocumentAiQualificationPlanFactory.create(
            repository_head=HEAD,
            fixture_reader=lambda path: (
                _reader(path) + b"changed" if path == first_path else _reader(path)
            ),
        )
    assert caught.value.code == "pdf_document_ai_qualification_fixture_hash_mismatch"


def test_executor_consumes_exactly_two_slots_and_delegates_to_pipe(
    tmp_path: Path,
) -> None:
    calls: list[tuple[str, str, str]] = []
    permits = []

    def pipe_runner(**kwargs):
        permits.append(kwargs["qualification_permit"])
        calls.append(
            (
                kwargs["fixture_id"],
                kwargs["expected_sha256"],
                kwargs["plan_sha256"],
            )
        )
        assert kwargs["pdf_bytes"].startswith(b"%PDF")
        return {"status": "succeeded"}

    plan = _plan()
    receipt = PdfDocumentAiQualificationExecutor(
        claim_root=tmp_path / "claims",
        pipe_runner=pipe_runner,
    ).execute(plan=plan, fixture_reader=_reader)
    assert [item[0] for item in calls] == ["drivewealth", "fidelity"]
    assert len({item[1] for item in calls}) == 2
    assert all(item[2] == plan.plan_sha256 for item in calls)
    assert [permit.fixture_sha256 for permit in permits] == [item[1] for item in calls]
    assert receipt["status"] == "succeeded"
    assert receipt["provider_call_slots_consumed_total"] == 2
    assert receipt["provider_calls_max"] == 2
    assert receipt["hidden_retry_total"] == 0
    assert receipt["fallback_total"] == 0
    assert receipt["repair_total"] == 0
    assert len(list((tmp_path / "claims").glob("*.consumed.safe.json"))) == 2


def _captured_permit(tmp_path: Path):
    permits = []

    def pipe_runner(**kwargs):
        permits.append(kwargs["qualification_permit"])
        return {"status": "succeeded"}

    PdfDocumentAiQualificationExecutor(
        claim_root=tmp_path / "claims",
        pipe_runner=pipe_runner,
    ).execute(plan=_plan(), fixture_reader=_reader)
    return permits[0]


def test_factory_qualification_permit_checks_digest_before_key_access(
    tmp_path: Path,
) -> None:
    class Config:
        CONTENT_EXTRACTION_ENGINE = "mistral_ocr"

        @property
        def MISTRAL_OCR_API_KEY(self):
            raise AssertionError("key must not be read")

    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(config=Config()))
    )
    extractor = PdfDocumentExtractorFactory.create(
        server_request=request,
        qualification_permit=_captured_permit(tmp_path),
    )

    with pytest.raises(PdfDocumentExtractionError) as caught:
        extractor.extract(b"%PDF-not-the-allowlisted-document", SimpleNamespace())

    assert caught.value.code == "PDF_DOCUMENT_AI_QUALIFICATION_FIXTURE_FORBIDDEN"


def test_factory_without_permit_keeps_production_admission_closed() -> None:
    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                config=SimpleNamespace(CONTENT_EXTRACTION_ENGINE="mistral_ocr")
            )
        )
    )
    extractor = PdfDocumentExtractorFactory.create(server_request=request)

    with pytest.raises(PdfDocumentExtractionError) as caught:
        extractor.extract(b"%PDF", SimpleNamespace())

    assert caught.value.code == PDF_DOCUMENT_AI_LIVE_QUALIFICATION_REQUIRED


def test_allowlisted_permit_routes_through_the_sole_factory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import broker_reports_gate1.mistral_pdf_document_ai as adapter_module

    fixture_path = PDF_DOCUMENT_AI_QUALIFICATION_FIXTURES[0][1]
    pdf_bytes = _reader(fixture_path)
    marker = object()
    calls = []

    class Extractor:
        def extract(self, observed_bytes, source_context):
            calls.append((observed_bytes, source_context))
            return marker

    def create_from_request(*, server_request, qualification_status):
        calls.append((server_request, qualification_status))
        return Extractor()

    monkeypatch.setattr(
        adapter_module, "create_from_openwebui_request", create_from_request
    )
    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                config=SimpleNamespace(CONTENT_EXTRACTION_ENGINE="mistral_ocr")
            )
        )
    )
    extractor = PdfDocumentExtractorFactory.create(
        server_request=request,
        qualification_permit=_captured_permit(tmp_path),
    )
    source_context = SimpleNamespace()

    assert extractor.extract(pdf_bytes, source_context) is marker
    assert calls == [
        (request, "qualification_attempt"),
        (pdf_bytes, source_context),
    ]


def test_failure_consumes_slot_and_cannot_be_retried(tmp_path: Path) -> None:
    calls = 0

    def failing_runner(**_kwargs):
        nonlocal calls
        calls += 1
        raise TimeoutError("private provider detail")

    plan = _plan()
    executor = PdfDocumentAiQualificationExecutor(
        claim_root=tmp_path / "claims",
        pipe_runner=failing_runner,
    )
    receipt = executor.execute(plan=plan, fixture_reader=_reader)
    assert calls == 1
    assert receipt["status"] == "failed"
    assert receipt["provider_call_slots_consumed_total"] == 1
    assert "private provider detail" not in json.dumps(receipt)
    with pytest.raises(PdfDocumentAiQualificationError) as caught:
        executor.execute(plan=plan, fixture_reader=_reader)
    assert caught.value.code == "pdf_document_ai_qualification_slot_already_consumed"
    assert calls == 1


def test_executor_rejects_forged_plan_before_pipe(tmp_path: Path) -> None:
    calls = 0

    def pipe_runner(**_kwargs):
        nonlocal calls
        calls += 1
        return {"status": "succeeded"}

    plan = _plan()
    forged = replace(plan, plan_sha256="0" * 64)
    with pytest.raises(PdfDocumentAiQualificationError) as caught:
        PdfDocumentAiQualificationExecutor(
            claim_root=tmp_path / "claims",
            pipe_runner=pipe_runner,
        ).execute(plan=forged, fixture_reader=_reader)
    assert caught.value.code == "pdf_document_ai_qualification_plan_invalid"
    assert calls == 0


def test_cli_default_preflight_does_not_require_pipe_or_read_runtime_config(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _script_module()
    monkeypatch.setattr(module, "_require_clean_committed_head", lambda: HEAD)
    monkeypatch.setattr(module, "_require_green_actions", lambda _head: None)
    assert module.main([]) == 0
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["mode"] == "preflight_only"
    assert receipt["provider_calls_total"] == 0
    assert receipt["native_config_read"] is False
    assert receipt["api_key_read"] is False


def test_execute_checks_repository_and_ci_before_requesting_pipe_runner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _script_module()
    events: list[str] = []
    monkeypatch.setattr(
        module,
        "_require_clean_committed_head",
        lambda: events.append("repository") or HEAD,
    )
    monkeypatch.setattr(
        module,
        "_require_green_actions",
        lambda _head: events.append("ci"),
    )
    with pytest.raises(PdfDocumentAiQualificationError) as caught:
        module.main(["--execute-exact-attempt"])
    assert caught.value.code == "pdf_document_ai_qualification_pipe_runner_required"
    assert events == ["repository", "ci"]


def test_repository_or_exact_ci_failure_is_terminal_before_execution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _script_module()
    monkeypatch.setattr(module, "_run", lambda _command: " M changed.py\n")
    with pytest.raises(PdfDocumentAiQualificationError) as dirty:
        module._require_clean_committed_head()
    assert dirty.value.code == "pdf_document_ai_qualification_repository_not_clean"

    responses = iter(
        (
            {
                "headRefOid": HEAD,
                "state": "OPEN",
                "isDraft": False,
                "number": 376,
            },
            {
                "check_runs": [
                    {
                        "name": "broker-reports-ci",
                        "head_sha": "b" * 40,
                        "status": "completed",
                        "conclusion": "success",
                        "app": {"slug": "github-actions"},
                        "pull_requests": [{"number": 376}],
                    }
                ]
            },
        )
    )
    monkeypatch.setattr(module, "_gh_json", lambda _command: next(responses))
    with pytest.raises(PdfDocumentAiQualificationError) as ci:
        module._require_green_actions(HEAD)
    assert ci.value.code == "pdf_document_ai_qualification_ci_not_green_for_head"


def test_cli_exposes_no_arbitrary_provider_or_fixture_inputs() -> None:
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    assert '"--preflight-only"' in source
    assert '"--execute-exact-attempt"' in source
    for forbidden_argument in (
        "--pdf",
        "--path",
        "--url",
        "--key",
        "--model",
        "--hash",
        "MistralPdfDocumentExtractor",
        "mistral_pdf_document_ai",
    ):
        assert forbidden_argument not in source
