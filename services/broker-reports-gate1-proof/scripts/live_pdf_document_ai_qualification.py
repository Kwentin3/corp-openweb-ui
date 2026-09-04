#!/usr/bin/env python3
"""Preflight or execute the one bounded public-PDF qualification attempt."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Sequence
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
    args = parser.parse_args(argv)

    head = _require_clean_committed_head()
    _require_green_actions(head)
    plan = PdfDocumentAiQualificationPlanFactory.create(
        repository_head=head,
        fixture_reader=_read_repository_fixture,
    )
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
