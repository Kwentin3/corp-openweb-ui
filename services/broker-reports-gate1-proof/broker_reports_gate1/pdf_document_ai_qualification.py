from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


PDF_DOCUMENT_AI_QUALIFICATION_POLICY_VERSION = (
    "broker_reports_pdf_document_ai_qualification_v1"
)
PDF_DOCUMENT_AI_QUALIFICATION_FIXTURES = (
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
PDF_DOCUMENT_AI_QUALIFICATION_MAX_PROVIDER_CALLS = 2

FACTORY_REQUIRED = (
    "Qualification execution must delegate each exact fixture to the existing "
    "Broker Reports Pipe boundary"
)
FORBIDDEN = (
    "Arbitrary files, provider clients, key or URL inputs, retry, fallback, "
    "repair and production admission are forbidden"
)


class PdfDocumentAiQualificationError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class ExistingPipeRunner(Protocol):
    def __call__(
        self,
        *,
        fixture_id: str,
        pdf_bytes: bytes,
        expected_sha256: str,
        plan_sha256: str,
        qualification_permit: "PdfDocumentAiQualificationPermit",
    ) -> Mapping[str, object]: ...


_PERMIT_CAPABILITY = object()


@dataclass(frozen=True)
class PdfDocumentAiQualificationPermit:
    """One-process capability for one exact public fixture attempt."""

    repository_head: str
    plan_sha256: str
    fixture_id: str
    fixture_sha256: str
    _capability: object

    def admits(self, observed_sha256: str) -> bool:
        return (
            self._capability is _PERMIT_CAPABILITY
            and self.fixture_sha256 == observed_sha256
            and self.fixture_sha256
            in {item[2] for item in PDF_DOCUMENT_AI_QUALIFICATION_FIXTURES}
        )


@dataclass(frozen=True)
class PdfDocumentAiQualificationFixture:
    fixture_id: str
    repository_path: str
    sha256: str
    size_bytes: int


@dataclass(frozen=True)
class PdfDocumentAiQualificationPlan:
    repository_head: str
    fixtures: tuple[PdfDocumentAiQualificationFixture, ...]
    plan_sha256: str

    def safe_receipt(self) -> dict[str, object]:
        return {
            "policy_version": PDF_DOCUMENT_AI_QUALIFICATION_POLICY_VERSION,
            "mode": "preflight_only",
            "repository_head": self.repository_head,
            "plan_sha256": self.plan_sha256,
            "fixture_sha256": [item.sha256 for item in self.fixtures],
            "fixtures_total": len(self.fixtures),
            "planned_provider_calls_max": (
                PDF_DOCUMENT_AI_QUALIFICATION_MAX_PROVIDER_CALLS
            ),
            "provider_call_slots_consumed_total": 0,
            "provider_calls_total": 0,
            "hidden_retry_total": 0,
            "fallback_total": 0,
            "repair_total": 0,
            "native_config_read": False,
            "api_key_read": False,
            "external_pdf_send_total": 0,
            "contains_secret": False,
            "production_activation": False,
        }


class PdfDocumentAiQualificationPlanFactory:
    @staticmethod
    def create(
        *,
        repository_head: str,
        fixture_reader: Callable[[str], bytes],
    ) -> PdfDocumentAiQualificationPlan:
        if not re.fullmatch(r"[0-9a-f]{40}", repository_head):
            raise PdfDocumentAiQualificationError(
                "pdf_document_ai_qualification_head_invalid"
            )
        fixtures: list[PdfDocumentAiQualificationFixture] = []
        for (
            fixture_id,
            repository_path,
            expected_sha256,
        ) in PDF_DOCUMENT_AI_QUALIFICATION_FIXTURES:
            payload = fixture_reader(repository_path)
            if not isinstance(payload, bytes) or not payload.startswith(b"%PDF"):
                raise PdfDocumentAiQualificationError(
                    "pdf_document_ai_qualification_fixture_invalid"
                )
            observed_sha256 = hashlib.sha256(payload).hexdigest()
            if observed_sha256 != expected_sha256:
                raise PdfDocumentAiQualificationError(
                    "pdf_document_ai_qualification_fixture_hash_mismatch"
                )
            fixtures.append(
                PdfDocumentAiQualificationFixture(
                    fixture_id=fixture_id,
                    repository_path=repository_path,
                    sha256=expected_sha256,
                    size_bytes=len(payload),
                )
            )
        material = {
            "policy_version": PDF_DOCUMENT_AI_QUALIFICATION_POLICY_VERSION,
            "repository_head": repository_head,
            "fixtures": [
                {
                    "fixture_id": item.fixture_id,
                    "repository_path": item.repository_path,
                    "sha256": item.sha256,
                    "size_bytes": item.size_bytes,
                }
                for item in fixtures
            ],
            "provider_calls_max": PDF_DOCUMENT_AI_QUALIFICATION_MAX_PROVIDER_CALLS,
            "retry_total": 0,
            "fallback_total": 0,
            "repair_total": 0,
            "production_activation": False,
        }
        plan_sha256 = hashlib.sha256(_canonical_json(material)).hexdigest()
        return PdfDocumentAiQualificationPlan(
            repository_head=repository_head,
            fixtures=tuple(fixtures),
            plan_sha256=plan_sha256,
        )


class PdfDocumentAiQualificationExecutor:
    """Consume at most one irreversible Pipe slot per allowlisted PDF."""

    def __init__(self, *, claim_root: Path, pipe_runner: ExistingPipeRunner) -> None:
        self._claim_root = claim_root
        self._pipe_runner = pipe_runner

    def execute(
        self,
        *,
        plan: PdfDocumentAiQualificationPlan,
        fixture_reader: Callable[[str], bytes],
    ) -> dict[str, object]:
        expected_plan = PdfDocumentAiQualificationPlanFactory.create(
            repository_head=plan.repository_head,
            fixture_reader=fixture_reader,
        )
        if plan != expected_plan:
            raise PdfDocumentAiQualificationError(
                "pdf_document_ai_qualification_plan_invalid"
            )
        outcomes: list[dict[str, object]] = []
        for fixture in plan.fixtures:
            payload = fixture_reader(fixture.repository_path)
            if hashlib.sha256(payload).hexdigest() != fixture.sha256:
                raise PdfDocumentAiQualificationError(
                    "pdf_document_ai_qualification_fixture_hash_mismatch"
                )
            self._consume_slot(plan=plan, fixture=fixture)
            permit = PdfDocumentAiQualificationPermit(
                repository_head=plan.repository_head,
                plan_sha256=plan.plan_sha256,
                fixture_id=fixture.fixture_id,
                fixture_sha256=fixture.sha256,
                _capability=_PERMIT_CAPABILITY,
            )
            try:
                result = self._pipe_runner(
                    fixture_id=fixture.fixture_id,
                    pdf_bytes=payload,
                    expected_sha256=fixture.sha256,
                    plan_sha256=plan.plan_sha256,
                    qualification_permit=permit,
                )
            except Exception:
                outcomes.append({"fixture_id": fixture.fixture_id, "status": "failed"})
                return self._execution_receipt(plan=plan, outcomes=outcomes)
            if result.get("status") != "succeeded":
                outcomes.append({"fixture_id": fixture.fixture_id, "status": "failed"})
                return self._execution_receipt(plan=plan, outcomes=outcomes)
            outcomes.append({"fixture_id": fixture.fixture_id, "status": "succeeded"})
        return self._execution_receipt(plan=plan, outcomes=outcomes)

    def _consume_slot(
        self,
        *,
        plan: PdfDocumentAiQualificationPlan,
        fixture: PdfDocumentAiQualificationFixture,
    ) -> None:
        self._claim_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        claim_path = self._claim_root / (
            f"{plan.plan_sha256}-{fixture.sha256}.consumed.safe.json"
        )
        payload = _canonical_json(
            {
                "policy_version": PDF_DOCUMENT_AI_QUALIFICATION_POLICY_VERSION,
                "plan_sha256": plan.plan_sha256,
                "repository_head": plan.repository_head,
                "fixture_id": fixture.fixture_id,
                "fixture_sha256": fixture.sha256,
                "status": "consumed_before_pipe_runner",
                "contains_secret": False,
            }
        )
        try:
            descriptor = os.open(
                claim_path,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
            )
        except FileExistsError as exc:
            raise PdfDocumentAiQualificationError(
                "pdf_document_ai_qualification_slot_already_consumed"
            ) from exc
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
        except BaseException:
            # A failed durable claim stays consumed: it must never reopen a
            # potentially submitted provider slot.
            raise

    @staticmethod
    def _execution_receipt(
        *,
        plan: PdfDocumentAiQualificationPlan,
        outcomes: list[dict[str, object]],
    ) -> dict[str, object]:
        consumed = len(outcomes)
        return {
            "policy_version": PDF_DOCUMENT_AI_QUALIFICATION_POLICY_VERSION,
            "mode": "execute_exact_attempt",
            "repository_head": plan.repository_head,
            "plan_sha256": plan.plan_sha256,
            "status": (
                "succeeded"
                if consumed == len(plan.fixtures)
                and all(item["status"] == "succeeded" for item in outcomes)
                else "failed"
            ),
            "outcomes": outcomes,
            "provider_call_slots_consumed_total": consumed,
            "provider_calls_max": PDF_DOCUMENT_AI_QUALIFICATION_MAX_PROVIDER_CALLS,
            "hidden_retry_total": 0,
            "fallback_total": 0,
            "repair_total": 0,
            "contains_secret": False,
            "contains_pdf_or_provider_payload": False,
            "production_activation": False,
        }


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
