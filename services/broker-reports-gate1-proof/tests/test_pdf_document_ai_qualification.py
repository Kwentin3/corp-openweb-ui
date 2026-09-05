from __future__ import annotations

import asyncio
import copy
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
from broker_reports_gate1.pdf_document_ai_qualification_review import (
    PDF_DOCUMENT_AI_BASELINE_SCHEMA_VERSION,
    PDF_DOCUMENT_AI_REVIEW_CHECKS,
    PDF_DOCUMENT_AI_REVIEW_POLICY_VERSION,
    build_safe_review_evidence_digest,
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


def _pipe_success(kwargs: dict, *, fidelity_image_count: int = 7) -> dict[str, object]:
    permit = kwargs["qualification_permit"]
    contract = permit.execution_contract.safe_dict()
    contract.pop("accepted_provider_reported_model_ids")
    binding = {
        **contract,
        "provider_reported_model_id": "mistral-ocr-4-1",
    }
    checks = {key: True for key in PDF_DOCUMENT_AI_REVIEW_CHECKS}
    image_count = fidelity_image_count if kwargs["fixture_id"] == "fidelity" else 0
    images = [
        {
            "page_number": index + 1,
            "markdown_target": f"img-{index}.jpeg",
            "sha256": "c" * 64,
        }
        for index in range(image_count)
    ]
    content_evidence = {
        "markdown_sha256": ["a" * 64],
        "page_markdown_sha256": ["b" * 64],
        "image_associations": images,
    }
    structural_counts = {
        "pages_count": 1,
        "markdown_bytes": 1,
        "images_count": len(images),
    }
    reviewed_at = "2026-09-05T12:00:00+00:00"
    live_output_digest = build_safe_review_evidence_digest(
        repository_head=permit.repository_head,
        fixture_id=kwargs["fixture_id"],
        source_pdf_sha256=kwargs["expected_sha256"],
        execution_binding=binding,
        content_evidence=content_evidence,
        structural_counts=structural_counts,
    )
    baseline = {
        "schema_version": PDF_DOCUMENT_AI_BASELINE_SCHEMA_VERSION,
        "repository_head": permit.repository_head,
        "fixture_id": kwargs["fixture_id"],
        "source_pdf_sha256": kwargs["expected_sha256"],
        "live_output_digest": live_output_digest,
        "execution_binding": binding,
        "content_evidence": content_evidence,
        "structural_counts": structural_counts,
        "checks": checks,
        "reviewer_id": "reviewer",
        "reviewed_at": reviewed_at,
        "contains_private_payload": False,
    }
    return {
        "status": "succeeded",
        "provider_calls_total": 1,
        "private_full_source_readback": True,
        "private_image_readback_count": image_count,
        "private_artifacts_purged": True,
        "review": {
            "policy_version": PDF_DOCUMENT_AI_REVIEW_POLICY_VERSION,
            "status": "passed",
            "repository_head": permit.repository_head,
            "fixture_id": kwargs["fixture_id"],
            "source_pdf_sha256": kwargs["expected_sha256"],
            "execution_binding": binding,
            "content_evidence": content_evidence,
            "structural_counts": structural_counts,
            "checks": checks,
            "checks_passed": len(PDF_DOCUMENT_AI_REVIEW_CHECKS),
            "checks_total": len(PDF_DOCUMENT_AI_REVIEW_CHECKS),
            "live_output_digest": live_output_digest,
            "reviewer_id": "reviewer",
            "reviewed_at": reviewed_at,
            "contains_private_payload": False,
            "baseline_candidate": baseline,
        },
    }


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
    assert "expected_image_count" not in receipt
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


@pytest.mark.parametrize("fidelity_image_count", (7, 8))
def test_executor_accepts_consistent_observed_graph_and_consumes_exactly_two_slots(
    tmp_path: Path,
    fidelity_image_count: int,
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
        return _pipe_success(kwargs, fidelity_image_count=fidelity_image_count)

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
    assert [item["private_image_readback_count"] for item in receipt["outcomes"]] == [
        0,
        fidelity_image_count,
    ]
    assert len(list((tmp_path / "claims").glob("*.consumed.safe.json"))) == 2


def test_executor_rejects_readback_count_not_bound_to_review_graph(
    tmp_path: Path,
) -> None:
    def pipe_runner(**kwargs):
        result = _pipe_success(kwargs)
        result["private_image_readback_count"] = 1
        return result

    receipt = PdfDocumentAiQualificationExecutor(
        claim_root=tmp_path / "claims",
        pipe_runner=pipe_runner,
    ).execute(plan=_plan(), fixture_reader=_reader)

    assert receipt["status"] == "failed"
    assert receipt["provider_call_slots_consumed_total"] == 1


def test_async_executor_uses_same_irreversible_slots_and_stops_on_failure(
    tmp_path: Path,
) -> None:
    calls: list[str] = []

    async def pipe_runner(**kwargs):
        calls.append(kwargs["fixture_id"])
        return {
            "status": "failed" if len(calls) == 1 else "succeeded",
        }

    receipt = asyncio.run(
        PdfDocumentAiQualificationExecutor(
            claim_root=tmp_path / "claims",
        ).execute_async(
            plan=_plan(),
            fixture_reader=_reader,
            pipe_runner=pipe_runner,
        )
    )
    assert calls == ["drivewealth"]
    assert receipt["status"] == "failed"
    assert receipt["provider_call_slots_consumed_total"] == 1
    assert len(list((tmp_path / "claims").glob("*.consumed.safe.json"))) == 1


@pytest.mark.parametrize(
    "missing_field",
    (
        "baseline_candidate",
        "reviewer_id",
        "reviewed_at",
        "checks",
        "content_evidence",
    ),
)
def test_executor_rejects_incomplete_positive_review_receipt(
    tmp_path: Path, missing_field: str
) -> None:
    calls: list[str] = []

    def pipe_runner(**kwargs):
        calls.append(kwargs["fixture_id"])
        result = copy.deepcopy(_pipe_success(kwargs))
        result["review"].pop(missing_field)
        return result

    receipt = PdfDocumentAiQualificationExecutor(
        claim_root=tmp_path / "claims",
        pipe_runner=pipe_runner,
    ).execute(plan=_plan(), fixture_reader=_reader)

    assert calls == ["drivewealth"]
    assert receipt["status"] == "failed"
    assert receipt["provider_call_slots_consumed_total"] == 1


def test_executor_rejects_unexpected_provider_reported_model(tmp_path: Path) -> None:
    def pipe_runner(**kwargs):
        result = copy.deepcopy(_pipe_success(kwargs))
        result["review"]["execution_binding"]["provider_reported_model_id"] = (
            "mistral-ocr-other"
        )
        result["review"]["baseline_candidate"]["execution_binding"] = dict(
            result["review"]["execution_binding"]
        )
        return result

    receipt = PdfDocumentAiQualificationExecutor(
        claim_root=tmp_path / "claims",
        pipe_runner=pipe_runner,
    ).execute(plan=_plan(), fixture_reader=_reader)

    assert receipt["status"] == "failed"
    assert receipt["provider_call_slots_consumed_total"] == 1


@pytest.mark.parametrize("mutation", ("bound_content", "extra_private_field"))
def test_executor_recomputes_digest_and_keeps_receipt_closed_world(
    tmp_path: Path, mutation: str
) -> None:
    def pipe_runner(**kwargs):
        result = copy.deepcopy(_pipe_success(kwargs))
        if mutation == "bound_content":
            result["review"]["content_evidence"]["page_markdown_sha256"][0] = "e" * 64
            result["review"]["baseline_candidate"]["content_evidence"] = copy.deepcopy(
                result["review"]["content_evidence"]
            )
        else:
            result["review"]["private_markdown"] = "must not pass"
        return result

    receipt = PdfDocumentAiQualificationExecutor(
        claim_root=tmp_path / "claims",
        pipe_runner=pipe_runner,
    ).execute(plan=_plan(), fixture_reader=_reader)

    assert receipt["status"] == "failed"
    assert receipt["provider_call_slots_consumed_total"] == 1


def _captured_permit(tmp_path: Path):
    permits = []

    def pipe_runner(**kwargs):
        permits.append(kwargs["qualification_permit"])
        return _pipe_success(kwargs)

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

    def pipe_runner(**kwargs):
        nonlocal calls
        calls += 1
        return _pipe_success(kwargs)

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


def test_review_lifecycle_dry_run_reads_private_graph_then_purges_without_provider(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _script_module()
    monkeypatch.setattr(module, "_require_clean_committed_head", lambda: HEAD)
    monkeypatch.setattr(module, "_require_green_actions", lambda _head: None)
    assert module.main(["--review-lifecycle-dry-run"]) == 0
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["mode"] == "review_lifecycle_dry_run"
    assert receipt["repository_head"] == HEAD
    assert receipt["private_full_source_readback"] is True
    assert receipt["private_image_readback_count"] == 1
    assert receipt["private_artifacts_purged"] is True
    assert receipt["provider_calls_total"] == 0
    assert receipt["native_config_read"] is False
    assert receipt["api_key_read"] is False
    assert receipt["external_sends_total"] == 0
    assert receipt["review"]["status"] == "passed"
    assert receipt["review"]["contains_private_payload"] is False


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


def test_exact_green_open_pr_head_is_accepted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _script_module()
    responses = iter(
        (
            {
                "check_runs": [
                    {
                        "name": "broker-reports-ci",
                        "head_sha": HEAD,
                        "status": "completed",
                        "conclusion": "success",
                        "app": {"slug": "github-actions"},
                        "pull_requests": [{"number": 377}],
                    }
                ]
            },
            {
                "headRefOid": HEAD,
                "state": "OPEN",
                "isDraft": False,
                "number": 377,
            },
        )
    )
    monkeypatch.setattr(module, "_gh_json", lambda _command: next(responses))
    module._require_green_actions(HEAD)


def test_exact_green_default_branch_head_is_accepted_after_merge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _script_module()
    responses = iter(
        (
            {
                "check_runs": [
                    {
                        "name": "broker-reports-ci",
                        "head_sha": HEAD,
                        "status": "completed",
                        "conclusion": "success",
                        "app": {"slug": "github-actions"},
                        "pull_requests": [],
                    }
                ]
            },
            {"defaultBranchRef": {"name": "main"}},
            {"commit": {"sha": HEAD}},
        )
    )
    monkeypatch.setattr(module, "_gh_json", lambda _command: next(responses))
    module._require_green_actions(HEAD)


def test_green_unassociated_non_default_branch_head_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _script_module()
    responses = iter(
        (
            {
                "check_runs": [
                    {
                        "name": "broker-reports-ci",
                        "head_sha": HEAD,
                        "status": "completed",
                        "conclusion": "success",
                        "app": {"slug": "github-actions"},
                        "pull_requests": [],
                    }
                ]
            },
            {"defaultBranchRef": {"name": "main"}},
            {"commit": {"sha": "c" * 40}},
        )
    )
    monkeypatch.setattr(module, "_gh_json", lambda _command: next(responses))
    with pytest.raises(PdfDocumentAiQualificationError) as caught:
        module._require_green_actions(HEAD)
    assert caught.value.code == "pdf_document_ai_qualification_ci_not_green_for_head"


def test_cli_exposes_no_arbitrary_provider_or_fixture_inputs() -> None:
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    assert '"--preflight-only"' in source
    assert '"--execute-exact-attempt"' in source
    assert '"--review-lifecycle-dry-run"' in source
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
