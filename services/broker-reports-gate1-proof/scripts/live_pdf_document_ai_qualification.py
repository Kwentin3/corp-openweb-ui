#!/usr/bin/env python3
"""Preflight or execute the one bounded public-PDF qualification attempt."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
SERVICE_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SERVICE_ROOT.parents[1]
sys.path.insert(0, str(SERVICE_ROOT))

from broker_reports_gate1.pdf_document_ai_qualification import (  # noqa: E402
    ExistingPipeRunner,
    PdfDocumentAiQualificationError,
    PdfDocumentAiQualificationExecutor,
    PdfDocumentAiQualificationPlanFactory,
)
from broker_reports_gate1.artifact_models import (  # noqa: E402
    ArtifactAccessContext,
    ArtifactRecord,
    build_private_binary_payload,
)
from broker_reports_gate1.artifact_retention import build_retention_policy  # noqa: E402
from broker_reports_gate1.artifact_store import (  # noqa: E402
    ArtifactStoreConfig,
    ArtifactStoreFactory,
)
from broker_reports_gate1.pdf_document_ai_qualification_review import (  # noqa: E402
    PDF_DOCUMENT_AI_REVIEW_CHECKS,
    PdfDocumentAiQualificationReviewFactory,
    PdfDocumentAiQualificationReviewVerdict,
)


BROKER_REPORTS_ACTIONS_JOB_NAME = "broker-reports-ci"
FACTORY_REQUIRED = (
    "Live execution delegates only to an injected existing Broker Reports Pipe runner"
)
FORBIDDEN = (
    "This CLI accepts no PDF path, URL, key, model or hash and never creates "
    "a provider adapter"
)


def main(
    argv: Sequence[str] | None = None,
    *,
    pipe_runner: ExistingPipeRunner | None = None,
) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument(
        "--preflight-only",
        action="store_true",
        help="Validate the frozen plan without reading config/key or calling providers (default).",
    )
    modes.add_argument(
        "--execute-exact-attempt",
        action="store_true",
        help="Consume the two exact one-shot slots through an injected existing-Pipe runner.",
    )
    modes.add_argument(
        "--review-lifecycle-dry-run",
        action="store_true",
        help=(
            "Exercise private Full Source review and purge with synthetic bytes; "
            "never read config/key or call providers."
        ),
    )
    args = parser.parse_args(argv)

    head = _require_clean_committed_head()
    _require_green_actions(head)
    plan = PdfDocumentAiQualificationPlanFactory.create(
        repository_head=head,
        fixture_reader=_read_repository_fixture,
    )
    if args.review_lifecycle_dry_run:
        print(_pretty_json(_review_lifecycle_dry_run(head)), end="")
        return 0
    if not args.execute_exact_attempt:
        print(_pretty_json(plan.safe_receipt()), end="")
        return 0
    if pipe_runner is None:
        raise PdfDocumentAiQualificationError(
            "pdf_document_ai_qualification_pipe_runner_required"
        )
    receipt = PdfDocumentAiQualificationExecutor(
        claim_root=_claim_root(),
        pipe_runner=pipe_runner,
    ).execute(plan=plan, fixture_reader=_read_repository_fixture)
    print(_pretty_json(receipt), end="")
    return 0 if receipt["status"] == "succeeded" else 2


def _review_lifecycle_dry_run(repository_head: str) -> dict[str, object]:
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=15)
    context = ArtifactAccessContext(
        user_id="qualification-dry-run",
        case_id="qualification-dry-run",
        chat_id="qualification-dry-run",
        workspace_model_id="broker_reports_gate1_pipe",
        normalization_run_id="qualification-dry-run",
        allow_private=True,
        require_source_available=True,
    )
    retention = build_retention_policy(
        mode="expires_after_ttl", ttl_seconds=900, now=now
    )
    markdown = "# Private review lifecycle dry-run\n\n| A | B |\n|---|---|\n| 1 | 2 |"
    markdown_sha256 = hashlib.sha256(markdown.encode("utf-8")).hexdigest()
    source_pdf = b"%PDF-qualification-review-dry-run"
    source_pdf_sha256 = hashlib.sha256(source_pdf).hexdigest()
    request_parameters = {"include_image_base64": True}
    request_parameters_sha256 = hashlib.sha256(
        b'{"include_image_base64":true}'
    ).hexdigest()
    image = b"qualification-review-dry-run-image"
    image_sha256 = hashlib.sha256(image).hexdigest()
    common = {
        "case_id": context.case_id,
        "chat_id": context.chat_id,
        "user_id": context.user_id,
        "workspace_model_id": context.workspace_model_id,
        "normalization_run_id": context.normalization_run_id,
        "document_id": "qualification-dry-run-document",
        "source_file_ref": {"openwebui_file_id": "qualification-dry-run"},
        "visibility": "private_case",
        "storage_backend": "project_artifact_payload",
        "retention_policy": retention,
        "access_policy": {"requires_user_id": True},
        "validation_status": "validated",
        "lifecycle_status": "private_ready",
    }
    with tempfile.TemporaryDirectory(prefix="broker-reports-review-") as root:
        root_path = Path(root)
        store = ArtifactStoreFactory(
            ArtifactStoreConfig(
                mode="sqlite",
                sqlite_path=root_path / "artifacts.sqlite3",
                payload_root=root_path / "payloads",
            )
        ).create()
        store.put_records_atomic(
            [
                ArtifactRecord(
                    artifact_id="qualification-dry-run-full-source",
                    artifact_type="private_normalized_source_payload_v0",
                    payload={
                        "normalized_projection": {"text": markdown},
                        "document_ai_markdown_sha256": markdown_sha256,
                        "format_structural_inventory": {
                            "pages_count": 1,
                            "images_count": 1,
                            "markdown_bytes": len(markdown.encode("utf-8")),
                        },
                        "document_ai_provenance": {
                            "provider_id": "mistral",
                            "source_pdf_sha256": source_pdf_sha256,
                            "requested_model_id": "mistral-ocr-4-1",
                            "model_id": "mistral-ocr-4-1",
                            "adapter_id": "mistral_serverless_ocr_adapter_v2",
                            "request_contract_version": "mistral_ocr_request_v1",
                            "request_parameters": request_parameters,
                            "request_parameters_sha256": request_parameters_sha256,
                            "page_markdown_sha256": [markdown_sha256],
                        },
                        "document_ai_image_refs": [
                            {
                                "page_number": 1,
                                "markdown_target": "dry-run-image.bin",
                                "local_ref": "qualification-dry-run-image",
                                "sha256": image_sha256,
                            }
                        ],
                    },
                    **common,
                ),
                ArtifactRecord(
                    artifact_id="qualification-dry-run-image",
                    artifact_type="private_binary_artifact_v1",
                    payload=build_private_binary_payload(
                        content=image, media_type="application/octet-stream"
                    ),
                    **common,
                ),
            ]
        )

        async def reviewer(view):
            if view.markdown != markdown or view.images[0][3] != image:
                raise PdfDocumentAiQualificationError(
                    "pdf_document_ai_review_dry_run_readback_failed"
                )
            return PdfDocumentAiQualificationReviewVerdict(
                live_output_digest=view.live_output_digest,
                checks={key: True for key in PDF_DOCUMENT_AI_REVIEW_CHECKS},
            )

        review = asyncio.run(
            PdfDocumentAiQualificationReviewFactory.create(
                store=store,
                context=context,
                full_source_refs=["qualification-dry-run-full-source"],
                repository_head=repository_head,
                fixture_id="synthetic-review-lifecycle",
                source_file_id="qualification-dry-run",
                source_pdf_bytes=source_pdf,
                expected_source_pdf_sha256=source_pdf_sha256,
                expected_image_count=1,
                expires_at=expires_at,
            ).review(actor_context=context, reviewer=reviewer, now=now)
        )
    return {
        "mode": "review_lifecycle_dry_run",
        "repository_head": repository_head,
        "private_full_source_readback": True,
        "private_image_readback_count": 1,
        "private_artifacts_purged": True,
        "provider_calls_total": 0,
        "native_config_read": False,
        "api_key_read": False,
        "external_sends_total": 0,
        "review": review,
    }


def _read_repository_fixture(repository_path: str) -> bytes:
    allowed = {
        "docs/reports/2026-09-02/artifacts/mistral-public-pairs/drivewealth/source.pdf",
        "docs/reports/2026-09-02/artifacts/mistral-public-pairs/fidelity/source.pdf",
    }
    if repository_path not in allowed:
        raise PdfDocumentAiQualificationError(
            "pdf_document_ai_qualification_fixture_path_forbidden"
        )
    return (REPO_ROOT / repository_path).read_bytes()


def _require_clean_committed_head() -> str:
    status = _run(["git", "status", "--porcelain=v1"])
    if status.strip():
        raise PdfDocumentAiQualificationError(
            "pdf_document_ai_qualification_repository_not_clean"
        )
    head = _run(["git", "rev-parse", "HEAD"]).strip()
    if len(head) != 40:
        raise PdfDocumentAiQualificationError(
            "pdf_document_ai_qualification_head_invalid"
        )
    return head


def _require_green_actions(head: str) -> None:
    checks = _gh_json(
        [
            "gh",
            "api",
            "-H",
            "Accept: application/vnd.github+json",
            f"repos/{{owner}}/{{repo}}/commits/{head}/check-runs?filter=latest&per_page=100",
        ]
    ).get("check_runs")
    matching = (
        [
            item
            for item in checks
            if isinstance(item, dict)
            and item.get("name") == BROKER_REPORTS_ACTIONS_JOB_NAME
            and item.get("head_sha") == head
            and isinstance(item.get("app"), dict)
            and item["app"].get("slug") == "github-actions"
        ]
        if isinstance(checks, list)
        else []
    )
    if len(matching) != 1 or matching[0].get("status") != "completed" or matching[
        0
    ].get("conclusion") != "success":
        raise PdfDocumentAiQualificationError(
            "pdf_document_ai_qualification_ci_not_green_for_head"
        )
    pull_requests = matching[0].get("pull_requests")
    if not isinstance(pull_requests, list):
        raise PdfDocumentAiQualificationError(
            "pdf_document_ai_qualification_ci_not_green_for_head"
        )
    pr_numbers = [
        item.get("number")
        for item in pull_requests
        if isinstance(item, dict) and type(item.get("number")) is int
    ]
    if pr_numbers:
        if len(pr_numbers) != 1:
            raise PdfDocumentAiQualificationError(
                "pdf_document_ai_qualification_ci_not_green_for_head"
            )
        pr = _gh_json(
            [
                "gh",
                "pr",
                "view",
                str(pr_numbers[0]),
                "--json",
                "headRefOid,state,isDraft,number",
            ]
        )
        if (
            pr.get("headRefOid") == head
            and pr.get("state") == "OPEN"
            and pr.get("isDraft") is False
            and pr.get("number") == pr_numbers[0]
        ):
            return
        raise PdfDocumentAiQualificationError(
            "pdf_document_ai_qualification_ci_not_green_for_head"
        )

    repository = _gh_json(["gh", "repo", "view", "--json", "defaultBranchRef"])
    default_branch_ref = repository.get("defaultBranchRef")
    default_branch = (
        default_branch_ref.get("name")
        if isinstance(default_branch_ref, dict)
        else None
    )
    if not isinstance(default_branch, str) or not default_branch:
        raise PdfDocumentAiQualificationError(
            "pdf_document_ai_qualification_ci_not_green_for_head"
        )
    branch = _gh_json(
        ["gh", "api", f"repos/{{owner}}/{{repo}}/branches/{default_branch}"]
    )
    commit = branch.get("commit")
    if not isinstance(commit, dict) or commit.get("sha") != head:
        raise PdfDocumentAiQualificationError(
            "pdf_document_ai_qualification_ci_not_green_for_head"
        )


def _gh_json(command: list[str]) -> dict[str, object]:
    try:
        value = json.loads(_run(command))
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        raise PdfDocumentAiQualificationError(
            "pdf_document_ai_qualification_github_unavailable"
        ) from exc
    if not isinstance(value, dict):
        raise PdfDocumentAiQualificationError(
            "pdf_document_ai_qualification_github_unavailable"
        )
    return value


def _run(command: list[str]) -> str:
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout


def _claim_root() -> Path:
    common = Path(_run(["git", "rev-parse", "--git-common-dir"]).strip())
    if not common.is_absolute():
        common = REPO_ROOT / common
    return common.resolve() / "codex-broker-reports" / "issue-374-pdf-qualification"


def _pretty_json(payload: dict[str, object]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
