from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any

from .pdf_dual_vlm_runtime import PDF_DUAL_VLM_DECISION_SCHEMA
from .semantic_visual_table_materialization import (
    SemanticVisualTableMaterializationError,
    SemanticVisualTableMaterializationFactory,
)


SEMANTIC_VISUAL_TABLE_MIGRATION_POLICY_VERSION = (
    "broker_reports_semantic_visual_table_migration_policy_v1"
)
SEMANTIC_VISUAL_TABLE_ACCEPTED_PROFILE_ID = (
    "broker_reports_semantic_visual_numeric_profile_v1"
)
GOAL5_QUALIFICATION_RECEIPT_HASH = (
    "96820ec84e1a4bfa167ac4c85090c0295f337ac24d2694d4f6fde0c535ed2ad7"
)
GOAL5_QUALIFICATION_GATE_HASH = (
    "2860e0d181ae4a8137ec4db796b2f26070f2df32e4581f4438107410fc62adbb"
)

FACTORY_REQUIRED = (
    "SemanticVisualTableMigrationFactory.create is the only maintained boundary "
    "from semantic VLM decisions to Gate 1 envelopes and Gate 2 projections"
)
FORBIDDEN = (
    "Legacy visual decisions must not be auto-upgraded; accepted semantic "
    "decisions must not be merged, repaired, or made review-dependent"
)

_AMOUNT = re.compile(
    r"^(?:[$€£¥₽]\s*)?\(?[+-]?\d[\d\s,.]*(?:%|\))?$"
)
_UNSUPPORTED_DESCRIPTION_SIGNALS = (
    "ambiguous",
    "cropped",
    "incomplete",
    "long-form prose",
    "obscured",
    "unreadable",
)


class SemanticVisualTableMigrationError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class SemanticVisualTableMigrationConfig:
    enabled: bool = False
    policy_version: str = SEMANTIC_VISUAL_TABLE_MIGRATION_POLICY_VERSION
    accepted_profile_id: str = SEMANTIC_VISUAL_TABLE_ACCEPTED_PROFILE_ID
    qualification_receipt_hash: str = GOAL5_QUALIFICATION_RECEIPT_HASH
    qualification_gate_hash: str = GOAL5_QUALIFICATION_GATE_HASH
    maximum_rows: int = 64
    maximum_columns: int = 4
    maximum_cell_characters: int = 256


@dataclass(frozen=True)
class SemanticVisualTableMigrationResult:
    safe_summary: dict[str, Any]
    private_envelopes: list[dict[str, Any]]
    gate2_projections: list[dict[str, Any]]


class SemanticVisualTableMigrationFactory:
    def __init__(
        self, config: SemanticVisualTableMigrationConfig | None = None
    ) -> None:
        self.config = config or SemanticVisualTableMigrationConfig()

    def create(self) -> "SemanticVisualTableMigrator":
        if (
            self.config.policy_version
            != SEMANTIC_VISUAL_TABLE_MIGRATION_POLICY_VERSION
            or self.config.accepted_profile_id
            != SEMANTIC_VISUAL_TABLE_ACCEPTED_PROFILE_ID
            or self.config.qualification_receipt_hash
            != GOAL5_QUALIFICATION_RECEIPT_HASH
            or self.config.qualification_gate_hash
            != GOAL5_QUALIFICATION_GATE_HASH
            or self.config.maximum_rows < 1
            or self.config.maximum_rows > 64
            or self.config.maximum_columns < 1
            or self.config.maximum_columns > 4
            or self.config.maximum_cell_characters < 1
            or self.config.maximum_cell_characters > 256
        ):
            raise SemanticVisualTableMigrationError(
                "semantic_visual_table_migration_config_invalid"
            )
        return SemanticVisualTableMigrator(self.config)


class SemanticVisualTableMigrator:
    def __init__(self, config: SemanticVisualTableMigrationConfig) -> None:
        self.config = config
        self.materializer = SemanticVisualTableMaterializationFactory().create()

    def migrate(
        self,
        *,
        decisions: list[dict[str, Any]],
        provider_evidence: list[dict[str, Any]],
    ) -> SemanticVisualTableMigrationResult:
        if not isinstance(decisions, list) or not isinstance(
            provider_evidence, list
        ):
            raise SemanticVisualTableMigrationError(
                "semantic_visual_table_migration_input_invalid"
            )
        if not self.config.enabled:
            return SemanticVisualTableMigrationResult(
                safe_summary=self._summary(
                    status="disabled",
                    decisions_total=len(decisions),
                    accepted=[],
                    dispositions=[],
                ),
                private_envelopes=[],
                gate2_projections=[],
            )
        accepted: list[dict[str, Any]] = []
        dispositions: list[dict[str, Any]] = []
        seen_decisions: set[str] = set()
        seen_candidates: set[str] = set()
        for decision in decisions:
            if not isinstance(decision, dict):
                raise SemanticVisualTableMigrationError(
                    "semantic_visual_table_migration_decision_invalid"
                )
            decision_id = str(decision.get("decision_id") or "")
            lineage = decision.get("source_lineage")
            lineage = lineage if isinstance(lineage, dict) else {}
            candidate_ref = str(lineage.get("candidate_ref") or "")
            if decision.get("schema_version") != PDF_DUAL_VLM_DECISION_SCHEMA:
                dispositions.append(
                    _disposition(
                        decision_id or _sha256_json(decision),
                        candidate_ref,
                        "legacy_retained_under_original_contract",
                        ["ambiguous_auto_migration_forbidden"],
                    )
                )
                continue
            if not decision_id or decision_id in seen_decisions:
                raise SemanticVisualTableMigrationError(
                    "semantic_visual_table_migration_duplicate_decision"
                )
            seen_decisions.add(decision_id)
            if not candidate_ref or candidate_ref in seen_candidates:
                raise SemanticVisualTableMigrationError(
                    "semantic_visual_table_migration_duplicate_source_scope"
                )
            seen_candidates.add(candidate_ref)
            reasons = _accepted_profile_errors(decision, self.config)
            if reasons:
                dispositions.append(
                    _disposition(
                        decision_id,
                        candidate_ref,
                        "review_required_or_unsupported",
                        reasons,
                    )
                )
                continue
            try:
                materialized = self.materializer.materialize(
                    decision=decision,
                    provider_evidence=provider_evidence,
                )
            except SemanticVisualTableMaterializationError as exc:
                raise SemanticVisualTableMigrationError(
                    "semantic_visual_table_migration_materialization_failed"
                ) from exc
            accepted.append(
                {
                    "decision_id": decision_id,
                    "candidate_ref": candidate_ref,
                    "envelope": materialized.private_envelope,
                    "projection": materialized.gate2_projection,
                }
            )
            dispositions.append(
                _disposition(
                    decision_id,
                    candidate_ref,
                    "accepted_for_gate2_without_mandatory_review",
                    ["goal5_accepted_numeric_profile"],
                )
            )
        envelope_ids = [item["envelope"]["envelope_id"] for item in accepted]
        projection_ids = [
            item["projection"]["table_projection_id"] for item in accepted
        ]
        if (
            len(envelope_ids) != len(set(envelope_ids))
            or len(projection_ids) != len(set(projection_ids))
        ):
            raise SemanticVisualTableMigrationError(
                "semantic_visual_table_migration_duplicate_output_identity"
            )
        return SemanticVisualTableMigrationResult(
            safe_summary=self._summary(
                status="completed",
                decisions_total=len(decisions),
                accepted=accepted,
                dispositions=dispositions,
            ),
            private_envelopes=[
                copy.deepcopy(item["envelope"]) for item in accepted
            ],
            gate2_projections=[
                copy.deepcopy(item["projection"]) for item in accepted
            ],
        )

    def _summary(
        self,
        *,
        status: str,
        decisions_total: int,
        accepted: list[dict[str, Any]],
        dispositions: list[dict[str, Any]],
    ) -> dict[str, Any]:
        summary = {
            "schema_version": SEMANTIC_VISUAL_TABLE_MIGRATION_POLICY_VERSION,
            "status": status,
            "enabled": self.config.enabled,
            "accepted_profile_id": self.config.accepted_profile_id,
            "qualification_receipt_hash": self.config.qualification_receipt_hash,
            "qualification_gate_hash": self.config.qualification_gate_hash,
            "decisions_total": decisions_total,
            "accepted_for_gate2_total": len(accepted),
            "review_required_or_unsupported_total": sum(
                item["disposition"] == "review_required_or_unsupported"
                for item in dispositions
            ),
            "legacy_artifacts_auto_migrated_total": 0,
            "mandatory_human_review_for_accepted_profile": False,
            "gate2_projection_ids": sorted(
                item["projection"]["table_projection_id"] for item in accepted
            ),
            "dispositions": copy.deepcopy(dispositions),
            "provider_merge_performed": False,
            "provider_repair_performed": False,
            "physical_geometry_claimed": False,
            "other_source_families_changed": False,
            "raw_values_present": False,
        }
        summary["summary_hash"] = _sha256_json(summary)
        return summary


def _accepted_profile_errors(
    decision: dict[str, Any], config: SemanticVisualTableMigrationConfig
) -> list[str]:
    errors: list[str] = []
    validator = decision.get("deterministic_validator")
    validator = validator if isinstance(validator, dict) else {}
    transcription = decision.get("semantic_transcription")
    transcription = transcription if isinstance(transcription, dict) else {}
    rows = transcription.get("rows")
    rows = rows if isinstance(rows, list) else []
    description = str(transcription.get("description") or "").lower()
    if (
        decision.get("status") != "semantic_transcription_valid"
        or decision.get("review_required") is not False
        or validator.get("selected_provider_contract_valid") is not True
        or validator.get("semantic_response_contract_passed") is not True
        or decision.get("provider_merge") is not False
        or decision.get("canonical_table") is not None
    ):
        errors.append("semantic_decision_not_terminally_valid")
    if len(rows) < 2 or len(rows) > config.maximum_rows:
        errors.append("accepted_profile_row_count_out_of_bounds")
    if any(
        not isinstance(row, list)
        or not row
        or len(row) > config.maximum_columns
        for row in rows
    ):
        errors.append("accepted_profile_column_count_out_of_bounds")
    cells = [cell for row in rows if isinstance(row, list) for cell in row]
    strings = [cell for cell in cells if isinstance(cell, str) and cell]
    if any(len(cell) > config.maximum_cell_characters for cell in strings):
        errors.append("accepted_profile_cell_length_out_of_bounds")
    amounts = [cell for cell in strings if _AMOUNT.fullmatch(cell.strip())]
    labels = [cell for cell in strings if not _AMOUNT.fullmatch(cell.strip())]
    if not amounts:
        errors.append("accepted_profile_visible_amount_missing")
    if not labels:
        errors.append("accepted_profile_visible_label_missing")
    if any(signal in description for signal in _UNSUPPORTED_DESCRIPTION_SIGNALS):
        errors.append("accepted_profile_description_reports_visual_uncertainty")
    return sorted(set(errors))


def _disposition(
    decision_id: str,
    candidate_ref: str,
    disposition: str,
    reason_codes: list[str],
) -> dict[str, Any]:
    return {
        "decision_id_hash": hashlib.sha256(decision_id.encode("utf-8")).hexdigest(),
        "candidate_ref_hash": hashlib.sha256(
            candidate_ref.encode("utf-8")
        ).hexdigest(),
        "disposition": disposition,
        "reason_codes": sorted(set(reason_codes)),
    }


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
