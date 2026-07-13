from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

from .contracts import stable_digest
from .pdf_hybrid_contracts import sha256_json


PDF_HYBRID_REPEATABILITY_LEDGER_SCHEMA = (
    "broker_reports_pdf_hybrid_repeatability_ledger_v2"
)
PDF_HYBRID_SHADOW_ARBITRATION_SCHEMA = (
    "broker_reports_pdf_hybrid_shadow_arbitration_v2"
)
PDF_HYBRID_RELIABILITY_POLICY_VERSION = "pdf_hybrid_reliability_policy_v2"
ALLOWED_TERMINALS = {
    "accepted_shadow",
    "human_review_required",
    "blocked_context_budget",
    "blocked_non_repeatable",
    "blocked_structural_placement",
    "unsupported",
}
FACTORY_REQUIRED = (
    "PdfHybridReliabilityFactory.create is the only repeatability and shadow arbitration entrypoint"
)
FORBIDDEN = (
    "Arbitration must not choose the best-looking revision or erase a recorded checksum conflict"
)


class PdfHybridReliabilityError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class PdfHybridReliabilityConfig:
    policy_version: str = PDF_HYBRID_RELIABILITY_POLICY_VERSION
    maximum_same_evidence_attempts: int = 2


class PdfHybridReliabilityFactory:
    def __init__(self, config: PdfHybridReliabilityConfig | None = None) -> None:
        self.config = config or PdfHybridReliabilityConfig()

    def create(
        self,
        *,
        initial_repeatability_ledger: dict[str, Any] | None = None,
    ) -> "PdfHybridReliabilityRuntime":
        if self.config.policy_version != PDF_HYBRID_RELIABILITY_POLICY_VERSION:
            raise PdfHybridReliabilityError("pdf_hybrid_reliability_policy_invalid")
        if self.config.maximum_same_evidence_attempts != 2:
            raise PdfHybridReliabilityError("pdf_hybrid_repeatability_attempt_policy_invalid")
        return PdfHybridReliabilityRuntime(
            self.config,
            initial_repeatability_ledger=initial_repeatability_ledger,
        )


class PdfHybridReliabilityRuntime:
    def __init__(
        self,
        config: PdfHybridReliabilityConfig,
        *,
        initial_repeatability_ledger: dict[str, Any] | None,
    ) -> None:
        self.config = config
        initial = initial_repeatability_ledger or {}
        if initial and initial.get("schema_version") != PDF_HYBRID_REPEATABILITY_LEDGER_SCHEMA:
            raise PdfHybridReliabilityError("pdf_hybrid_repeatability_ledger_schema_invalid")
        self._records: dict[str, dict[str, Any]] = {
            str(item.get("task_key") or ""): copy.deepcopy(item)
            for item in initial.get("records") or []
            if isinstance(item, dict) and item.get("task_key")
        }

    @staticmethod
    def task_key(
        *,
        evidence_package_hashes: list[str],
        provider: str,
        model: str,
        provider_config_hash: str,
        output_schema_hashes: list[str],
    ) -> str:
        return "pdfhybridrepeat_" + stable_digest(
            [
                evidence_package_hashes,
                provider,
                model,
                provider_config_hash,
                output_schema_hashes,
            ],
            length=32,
        )

    def record(
        self,
        *,
        task_key: str,
        placement_checksum: str,
        attempt_number: int,
        evidence_revision: str,
    ) -> dict[str, Any]:
        if attempt_number not in {1, 2}:
            raise PdfHybridReliabilityError("pdf_hybrid_repeatability_attempt_number_invalid")
        record = self._records.setdefault(
            task_key,
            {
                "task_key": task_key,
                "evidence_revision": evidence_revision,
                "checksums_observed": [],
                "attempts": [],
                "ever_conflicted": False,
                "conflict_codes": [],
            },
        )
        if record.get("evidence_revision") != evidence_revision:
            raise PdfHybridReliabilityError("pdf_hybrid_repeatability_evidence_revision_mismatch")
        checksums = list(record.get("checksums_observed") or [])
        if checksums and placement_checksum not in checksums:
            record["ever_conflicted"] = True
            record["conflict_codes"] = sorted(
                set(record.get("conflict_codes") or [])
                | {"pdf_hybrid_non_repeatable_placement_checksum"}
            )
        if placement_checksum not in checksums:
            checksums.append(placement_checksum)
        record["checksums_observed"] = checksums
        record.setdefault("attempts", []).append(
            {
                "attempt_number": attempt_number,
                "placement_checksum": placement_checksum,
            }
        )
        record["stable"] = (
            len(record["attempts"]) >= 2
            and len(record["checksums_observed"]) == 1
            and not record["ever_conflicted"]
        )
        record["later_agreement_can_clear_conflict"] = False
        record["record_checksum"] = sha256_json(
            {key: value for key, value in record.items() if key != "record_checksum"}
        )
        return copy.deepcopy(record)

    def result(self, task_key: str, *, required: bool) -> dict[str, Any]:
        record = copy.deepcopy(self._records.get(task_key) or {})
        if not required:
            return {
                "required": False,
                "passed": True,
                "ever_conflicted": bool(record.get("ever_conflicted")),
                "reason_codes": [],
                "record": record or None,
            }
        errors = []
        if not record or len(record.get("attempts") or []) < 2:
            errors.append("pdf_hybrid_repeatability_evidence_incomplete")
        if record.get("ever_conflicted"):
            errors.append("pdf_hybrid_non_repeatable_placement_checksum")
        if not record.get("stable"):
            errors.append("pdf_hybrid_repeatability_not_proven")
        return {
            "required": True,
            "passed": not errors,
            "ever_conflicted": bool(record.get("ever_conflicted")),
            "reason_codes": sorted(set(errors)),
            "record": record or None,
        }

    def ledger(self) -> dict[str, Any]:
        result = {
            "schema_version": PDF_HYBRID_REPEATABILITY_LEDGER_SCHEMA,
            "policy_version": self.config.policy_version,
            "records": [self._records[key] for key in sorted(self._records)],
            "conflicted_task_keys": sorted(
                key
                for key, value in self._records.items()
                if value.get("ever_conflicted")
            ),
            "monotonic_conflict_memory": True,
            "later_agreement_can_clear_conflict": False,
        }
        result["ledger_checksum"] = sha256_json(result)
        return copy.deepcopy(result)

    def arbitrate(
        self,
        *,
        table_ref: str,
        deterministic_signal: dict[str, Any],
        hybrid_150_signal: dict[str, Any],
        hybrid_200_signal: dict[str, Any] | None,
        structural_signal: dict[str, Any] | None,
        continuation_signal: dict[str, Any] | None,
        repeatability_signal: dict[str, Any] | None,
    ) -> dict[str, Any]:
        hybrid_200_signal = hybrid_200_signal or {"required": False, "status": "not_run"}
        structural_signal = structural_signal or {"required": True, "passed": False}
        continuation_signal = continuation_signal or {"required": False, "passed": True}
        repeatability_signal = repeatability_signal or {"required": True, "passed": False}
        reason_codes: list[str] = []
        terminal: str
        if hybrid_150_signal.get("supported") is False:
            terminal = "unsupported"
            reason_codes.append("pdf_hybrid_arbitration_provider_or_table_unsupported")
        elif hybrid_150_signal.get("context_budget_passed") is not True:
            terminal = "blocked_context_budget"
            reason_codes.extend(
                str(item) for item in hybrid_150_signal.get("reason_codes") or []
            )
        elif repeatability_signal.get("ever_conflicted") or (
            repeatability_signal.get("required")
            and repeatability_signal.get("passed") is not True
        ):
            terminal = "blocked_non_repeatable"
            reason_codes.extend(
                str(item) for item in repeatability_signal.get("reason_codes") or []
            )
        elif structural_signal.get("passed") is not True or (
            continuation_signal.get("required")
            and continuation_signal.get("passed") is not True
        ):
            terminal = "blocked_structural_placement"
            reason_codes.extend(
                str(item) for item in structural_signal.get("reason_codes") or []
            )
            reason_codes.extend(
                str(item) for item in hybrid_150_signal.get("reason_codes") or []
            )
            reason_codes.extend(
                str(item) for item in continuation_signal.get("reason_codes") or []
            )
        elif (
            hybrid_150_signal.get("binding_status") != "bound"
            or hybrid_150_signal.get("provider_passed") is not True
            or (
                hybrid_200_signal.get("required")
                and hybrid_200_signal.get("placement_checksum_match") is not True
            )
        ):
            terminal = "human_review_required"
            reason_codes.extend(
                str(item) for item in hybrid_150_signal.get("reason_codes") or []
            )
            reason_codes.extend(
                str(item) for item in hybrid_200_signal.get("reason_codes") or []
            )
        else:
            terminal = "accepted_shadow"
        if terminal not in ALLOWED_TERMINALS:
            raise PdfHybridReliabilityError("pdf_hybrid_arbitration_terminal_invalid")
        result = {
            "schema_version": PDF_HYBRID_SHADOW_ARBITRATION_SCHEMA,
            "policy_version": self.config.policy_version,
            "table_ref": table_ref,
            "terminal_status": terminal,
            "reason_codes": sorted(set(reason_codes)),
            "signals": {
                "deterministic": copy.deepcopy(deterministic_signal),
                "hybrid_150": copy.deepcopy(hybrid_150_signal),
                "hybrid_200": copy.deepcopy(hybrid_200_signal),
                "independent_structural": copy.deepcopy(structural_signal),
                "continuation": copy.deepcopy(continuation_signal),
                "repeatability": copy.deepcopy(repeatability_signal),
            },
            "best_looking_result_selection_used": False,
            "silent_revision_selection_used": False,
            "authority_state": "non_authoritative",
            "production_gate2_selection_changed": False,
        }
        result["arbitration_checksum"] = sha256_json(result)
        return result
