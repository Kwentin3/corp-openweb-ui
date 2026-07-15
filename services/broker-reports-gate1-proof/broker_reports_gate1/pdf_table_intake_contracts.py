from __future__ import annotations

import copy
import math
import re
from dataclasses import asdict, dataclass
from typing import Any, Iterable

from .pdf_hybrid_contracts import canonical_json_bytes, sha256_json


FACTORY_REQUIRED = (
    "PdfTableIntakeContractFactory.create is the only table-intake decision "
    "contract entrypoint; build_decisions and finalize_decisions remain "
    "factory-owned"
)
FORBIDDEN = (
    "Rows, columns, density, area, empty bands, ruling evidence, and parser "
    "strategy are metadata only; they must never decide technical "
    "processability or holdout selection"
)

DETECTION_DECISIONS = frozenset(
    {
        "plausible",
        "implausible",
        "uncertain",
        "absent_due_to_upstream_failure",
    }
)
PROCESSABILITY_DECISIONS = frozenset({"processable", "unsupported"})
HOLDOUT_DECISIONS = frozenset({"selected", "not_selected", "not_evaluated"})
INTAKE_SCOPES = frozenset({"candidate_crop", "page"})

PDF_TABLE_INTAKE_DECISION_SCHEMA = "broker_reports_pdf_vlm_guided_intake_decision_v1"
PDF_TABLE_INTAKE_DECISION_REVISION = "pdf_table_intake_contract_v1"

_FACTORY_TOKEN = object()
_REASON_CODE = re.compile(r"^[a-z][a-z0-9_]{2,95}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_TOP_LEVEL_KEYS = {
    "schema_version",
    "revision",
    "detection",
    "processability",
    "holdout",
    "metadata",
    "technical_facts",
    "contract_checksum",
}
_DECISION_KEYS = {"decision", "reason_codes", "evidence_binding"}
_EVIDENCE_BINDING_KEYS = {
    "document_ref",
    "pdf_sha256",
    "page_ref",
    "page_number",
    "scope_ref",
    "table_ref",
    "evidence_checksum",
    "assessor_stage",
}
_TECHNICAL_FACT_KEYS = {
    "scope",
    "page_bbox",
    "candidate_bbox",
    "coordinate_bboxes_total",
    "invalid_coordinate_bboxes_total",
    "out_of_scope_coordinate_bboxes_total",
    "provenance_verified",
    "crop_identity_verified",
    "exact_ownership_verified",
    "atom_count",
    "model_json_bytes",
    "counted_input_tokens",
    "image_count",
    "crop_count",
    "pdf_count",
    "image_bytes",
    "proposed_region_bboxes",
    "proposed_region_bboxes_total",
    "invalid_proposed_region_bboxes_total",
    "out_of_page_proposed_region_bboxes_total",
    "overlapping_proposed_region_pairs_total",
    "upstream_failure_reason_codes",
    "limits",
}
_LIMIT_KEYS = {
    "maximum_atoms",
    "maximum_model_json_bytes",
    "maximum_counted_input_tokens",
    "maximum_image_bytes",
    "maximum_page_region_proposals",
}
_METADATA_DECISION_KEYS = {
    "decision",
    "detection",
    "eligible",
    "holdout",
    "not_evaluated",
    "not_selected",
    "processable",
    "processability",
    "reason_codes",
    "selected",
    "schema_version",
    "revision",
    "contract_checksum",
    "technical_facts",
    "document_ref",
    "pdf_sha256",
    "page_ref",
    "page_number",
    "scope_ref",
    "table_ref",
    "evidence_checksum",
    "assessor_stage",
    "upstream_failure_reason_codes",
    "counted_input_tokens",
    "unsupported",
}


class PdfTableIntakeContractError(ValueError):
    def __init__(self, code: str, subject: str = "") -> None:
        self.code = code
        self.subject = subject
        super().__init__(code if not subject else f"{code}:{subject}")


@dataclass(frozen=True)
class PdfTableIntakeContractConfig:
    maximum_atoms: int = 1_000
    maximum_model_json_bytes: int = 48 * 1024
    maximum_counted_input_tokens: int = 20_000
    maximum_image_bytes: int = 8 * 1024 * 1024
    maximum_page_region_proposals: int = 2


class PdfTableIntakeContractFactory:
    def __init__(self, config: PdfTableIntakeContractConfig | None = None) -> None:
        self.config = config or PdfTableIntakeContractConfig()

    def create(self) -> "PdfTableIntakeContractRuntime":
        if self.config != PdfTableIntakeContractConfig():
            raise PdfTableIntakeContractError(
                "pdf_table_intake_budget_override_forbidden"
            )
        return PdfTableIntakeContractRuntime(
            self.config,
            _factory_token=_FACTORY_TOKEN,
        )


class PdfTableIntakeContractRuntime:
    def __init__(
        self,
        config: PdfTableIntakeContractConfig,
        *,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise PdfTableIntakeContractError("pdf_table_intake_factory_required")
        self.config = config

    def build_decisions(
        self,
        *,
        document_ref: str,
        pdf_sha256: str,
        page_ref: str,
        page_number: int,
        scope_ref: str,
        evidence_checksum: str,
        assessor_stage: str,
        scope: str,
        table_ref: str | None = None,
        detection_decision: str,
        detection_reason_codes: Iterable[str] = (),
        upstream_failure_reason_codes: Iterable[str] = (),
        holdout_decision: str = "not_evaluated",
        holdout_reason_codes: Iterable[str] = (),
        page_bbox: Any,
        candidate_bbox: Any = None,
        coordinate_bboxes: Iterable[Any] = (),
        provenance_verified: bool,
        crop_identity_verified: bool,
        exact_ownership_verified: bool,
        atom_count: int,
        model_json_bytes: int,
        counted_input_tokens: int | None,
        image_count: int,
        crop_count: int,
        pdf_count: int,
        image_bytes: int,
        proposed_region_bboxes: Iterable[Any] = (),
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if scope not in INTAKE_SCOPES:
            raise PdfTableIntakeContractError(
                "pdf_table_intake_scope_invalid", str(scope)
            )
        if detection_decision not in DETECTION_DECISIONS:
            raise PdfTableIntakeContractError(
                "pdf_table_intake_detection_decision_invalid"
            )
        if holdout_decision not in HOLDOUT_DECISIONS:
            raise PdfTableIntakeContractError(
                "pdf_table_intake_holdout_decision_invalid"
            )

        evidence_binding = _evidence_binding(
            document_ref=document_ref,
            pdf_sha256=pdf_sha256,
            page_ref=page_ref,
            page_number=page_number,
            scope_ref=scope_ref,
            table_ref=table_ref,
            evidence_checksum=evidence_checksum,
            assessor_stage=assessor_stage,
            scope=scope,
        )

        detection_reasons = _reason_codes(detection_reason_codes)
        upstream_reasons = _reason_codes(upstream_failure_reason_codes)
        holdout_reasons = _reason_codes(holdout_reason_codes)
        if upstream_reasons:
            effective_detection = "absent_due_to_upstream_failure"
            detection_reasons = upstream_reasons
        elif detection_decision == "absent_due_to_upstream_failure":
            raise PdfTableIntakeContractError(
                "pdf_table_intake_upstream_failure_reason_required"
            )
        else:
            effective_detection = detection_decision
        if effective_detection != "plausible" and not detection_reasons:
            raise PdfTableIntakeContractError(
                "pdf_table_intake_detection_reason_required"
            )

        normalized_page_bbox = _normalized_bbox(page_bbox)
        normalized_candidate_bbox = _normalized_bbox(candidate_bbox)
        coordinate_items = list(coordinate_bboxes)
        invalid_coordinates = 0
        outside_coordinates = 0
        coordinate_scope = (
            normalized_candidate_bbox
            if scope == "candidate_crop"
            else normalized_page_bbox
        )
        for coordinate_bbox in coordinate_items:
            normalized_coordinate = _normalized_bbox(coordinate_bbox)
            if normalized_coordinate is None:
                invalid_coordinates += 1
            elif coordinate_scope is None or not _bbox_contains(
                coordinate_scope, normalized_coordinate
            ):
                outside_coordinates += 1

        proposed_region_items = list(proposed_region_bboxes)
        normalized_regions: list[list[float]] = []
        invalid_regions = 0
        outside_regions = 0
        for proposed_region_bbox in proposed_region_items:
            normalized_region = _normalized_bbox(proposed_region_bbox)
            if normalized_region is None:
                invalid_regions += 1
            else:
                normalized_regions.append(normalized_region)
                if normalized_page_bbox is None or not _bbox_contains(
                    normalized_page_bbox, normalized_region
                ):
                    outside_regions += 1
        overlapping_region_pairs = sum(
            1
            for index, left in enumerate(normalized_regions)
            for right in normalized_regions[index + 1 :]
            if _bboxes_overlap(left, right)
        )

        for name, value in (
            ("provenance_verified", provenance_verified),
            ("crop_identity_verified", crop_identity_verified),
            ("exact_ownership_verified", exact_ownership_verified),
        ):
            if not isinstance(value, bool):
                raise PdfTableIntakeContractError(
                    "pdf_table_intake_boolean_fact_invalid", name
                )

        facts = {
            "scope": scope,
            "page_bbox": normalized_page_bbox,
            "candidate_bbox": normalized_candidate_bbox,
            "coordinate_bboxes_total": len(coordinate_items),
            "invalid_coordinate_bboxes_total": invalid_coordinates,
            "out_of_scope_coordinate_bboxes_total": outside_coordinates,
            "provenance_verified": provenance_verified,
            "crop_identity_verified": crop_identity_verified,
            "exact_ownership_verified": exact_ownership_verified,
            "atom_count": _nonnegative_int(atom_count, "atom_count"),
            "model_json_bytes": _nonnegative_int(model_json_bytes, "model_json_bytes"),
            "counted_input_tokens": _optional_nonnegative_int(
                counted_input_tokens, "counted_input_tokens"
            ),
            "image_count": _nonnegative_int(image_count, "image_count"),
            "crop_count": _nonnegative_int(crop_count, "crop_count"),
            "pdf_count": _nonnegative_int(pdf_count, "pdf_count"),
            "image_bytes": _nonnegative_int(image_bytes, "image_bytes"),
            "proposed_region_bboxes": normalized_regions,
            "proposed_region_bboxes_total": len(proposed_region_items),
            "invalid_proposed_region_bboxes_total": invalid_regions,
            "out_of_page_proposed_region_bboxes_total": outside_regions,
            "overlapping_proposed_region_pairs_total": (overlapping_region_pairs),
            "upstream_failure_reason_codes": upstream_reasons,
            "limits": asdict(self.config),
        }
        technical_reasons = _technical_reason_codes(facts)
        frozen_metadata = _metadata(metadata)
        result = {
            "schema_version": PDF_TABLE_INTAKE_DECISION_SCHEMA,
            "revision": PDF_TABLE_INTAKE_DECISION_REVISION,
            "detection": {
                "decision": effective_detection,
                "reason_codes": detection_reasons,
                "evidence_binding": copy.deepcopy(evidence_binding),
            },
            "processability": {
                "decision": ("unsupported" if technical_reasons else "processable"),
                "reason_codes": technical_reasons,
                "evidence_binding": copy.deepcopy(evidence_binding),
            },
            "holdout": {
                "decision": holdout_decision,
                "reason_codes": holdout_reasons,
                "evidence_binding": copy.deepcopy(evidence_binding),
            },
            "metadata": frozen_metadata,
            "technical_facts": facts,
        }
        result["contract_checksum"] = sha256_json(result)
        errors = self.validate_decisions(result)
        if errors:
            raise PdfTableIntakeContractError(errors[0])
        return copy.deepcopy(result)

    def finalize_decisions(
        self,
        *,
        decisions: dict[str, Any],
        actual_counted_input_tokens: int | None = None,
        upstream_failure_reason_codes: Iterable[str] | None = None,
        detection_decision: str | None = None,
        detection_reason_codes: Iterable[str] | None = None,
    ) -> dict[str, Any]:
        """Seal facts learned after preflight without rebuilding other decisions.

        A count result may fill an uncounted input, but it cannot contradict an
        already sealed count.  Newly observed upstream failures are additive so
        finalization cannot erase a previously proven technical terminal.
        """

        errors = self.validate_decisions(decisions)
        if errors:
            raise PdfTableIntakeContractError(
                "pdf_table_intake_finalize_source_invalid", errors[0]
            )
        if (
            actual_counted_input_tokens is None
            and upstream_failure_reason_codes is None
            and detection_decision is None
            and detection_reason_codes is None
        ):
            raise PdfTableIntakeContractError(
                "pdf_table_intake_finalize_observation_required"
            )

        result = copy.deepcopy(decisions)
        facts = result["technical_facts"]
        binding = copy.deepcopy(
            result["processability"]["evidence_binding"]
        )
        if detection_decision is not None:
            if detection_decision not in DETECTION_DECISIONS or (
                detection_decision == "absent_due_to_upstream_failure"
            ):
                raise PdfTableIntakeContractError(
                    "pdf_table_intake_detection_decision_invalid"
                )
            observed_detection_reasons = _reason_codes(
                detection_reason_codes or ()
            )
            if (
                detection_decision != "plausible"
                and not observed_detection_reasons
            ):
                raise PdfTableIntakeContractError(
                    "pdf_table_intake_detection_reason_required"
                )
            result["detection"] = {
                "decision": detection_decision,
                "reason_codes": observed_detection_reasons,
                "evidence_binding": copy.deepcopy(binding),
            }
        elif detection_reason_codes is not None:
            raise PdfTableIntakeContractError(
                "pdf_table_intake_detection_decision_required"
            )
        if actual_counted_input_tokens is not None:
            actual_count = _nonnegative_int(
                actual_counted_input_tokens,
                "actual_counted_input_tokens",
            )
            sealed_count = facts.get("counted_input_tokens")
            if sealed_count is not None and sealed_count != actual_count:
                raise PdfTableIntakeContractError(
                    "pdf_table_intake_counted_input_tokens_conflict"
                )
            facts["counted_input_tokens"] = actual_count

        if upstream_failure_reason_codes is not None:
            observed_upstream_reasons = _reason_codes(upstream_failure_reason_codes)
            if not observed_upstream_reasons:
                raise PdfTableIntakeContractError(
                    "pdf_table_intake_upstream_failure_reason_required"
                )
            facts["upstream_failure_reason_codes"] = sorted(
                set(facts["upstream_failure_reason_codes"])
                | set(observed_upstream_reasons)
            )

        upstream_reasons = facts["upstream_failure_reason_codes"]
        if upstream_reasons:
            result["detection"] = {
                "decision": "absent_due_to_upstream_failure",
                "reason_codes": copy.deepcopy(upstream_reasons),
                "evidence_binding": copy.deepcopy(binding),
            }
        technical_reasons = _technical_reason_codes(facts)
        result["processability"] = {
            "decision": ("unsupported" if technical_reasons else "processable"),
            "reason_codes": technical_reasons,
            "evidence_binding": binding,
        }
        result.pop("contract_checksum", None)
        result["contract_checksum"] = sha256_json(result)
        errors = self.validate_decisions(result)
        if errors:
            raise PdfTableIntakeContractError(errors[0])
        return copy.deepcopy(result)

    def validate_decisions(self, value: Any) -> list[str]:
        if not isinstance(value, dict) or set(value) != _TOP_LEVEL_KEYS:
            return ["pdf_table_intake_contract_keys_invalid"]
        data = copy.deepcopy(value)
        stored_checksum = data.pop("contract_checksum", None)
        errors: list[str] = []

        detection = data.get("detection")
        processability = data.get("processability")
        holdout = data.get("holdout")
        facts = data.get("technical_facts")
        facts_valid = _valid_technical_facts(facts, self.config)
        if data.get("schema_version") != PDF_TABLE_INTAKE_DECISION_SCHEMA:
            errors.append("pdf_table_intake_schema_invalid")
        if data.get("revision") != PDF_TABLE_INTAKE_DECISION_REVISION:
            errors.append("pdf_table_intake_revision_invalid")
        if not _valid_decision(detection, DETECTION_DECISIONS):
            errors.append("pdf_table_intake_detection_invalid")
        if not _valid_decision(processability, PROCESSABILITY_DECISIONS):
            errors.append("pdf_table_intake_processability_invalid")
        if not _valid_decision(holdout, HOLDOUT_DECISIONS):
            errors.append("pdf_table_intake_holdout_invalid")
        if not facts_valid:
            errors.append("pdf_table_intake_technical_facts_invalid")
        try:
            _metadata(data.get("metadata"))
        except PdfTableIntakeContractError:
            errors.append("pdf_table_intake_metadata_invalid")

        decisions = [detection, processability, holdout]
        bindings = [
            item.get("evidence_binding") for item in decisions if isinstance(item, dict)
        ]
        scope = (
            facts.get("scope")
            if isinstance(facts, dict) and facts.get("scope") in INTAKE_SCOPES
            else None
        )
        if len(bindings) != 3 or any(
            not _valid_evidence_binding(item, scope=scope) for item in bindings
        ):
            errors.append("pdf_table_intake_evidence_binding_invalid")
        elif any(item != bindings[0] for item in bindings[1:]):
            errors.append("pdf_table_intake_evidence_binding_drift")

        if isinstance(detection, dict) and facts_valid:
            upstream_reasons = facts.get("upstream_failure_reason_codes")
            if upstream_reasons:
                if (
                    detection.get("decision") != "absent_due_to_upstream_failure"
                    or detection.get("reason_codes") != upstream_reasons
                ):
                    errors.append("pdf_table_intake_upstream_detection_invalid")
            elif detection.get("decision") == "absent_due_to_upstream_failure":
                errors.append("pdf_table_intake_upstream_detection_invalid")
            elif detection.get("decision") != "plausible" and not detection.get(
                "reason_codes"
            ):
                errors.append("pdf_table_intake_detection_reason_missing")

        if isinstance(processability, dict) and facts_valid:
            expected_reasons = _technical_reason_codes(facts)
            expected_decision = "unsupported" if expected_reasons else "processable"
            if (
                processability.get("decision") != expected_decision
                or processability.get("reason_codes") != expected_reasons
            ):
                errors.append("pdf_table_intake_processability_drift")

        try:
            checksum_valid = bool(
                isinstance(stored_checksum, str)
                and _SHA256.fullmatch(stored_checksum)
                and stored_checksum == sha256_json(data)
            )
        except (TypeError, ValueError):
            checksum_valid = False
        if not checksum_valid:
            errors.append("pdf_table_intake_checksum_invalid")
        return sorted(set(errors))


def _technical_reason_codes(facts: dict[str, Any]) -> list[str]:
    reasons = list(facts.get("upstream_failure_reason_codes") or [])
    scope = facts.get("scope")
    page_bbox = _normalized_bbox(facts.get("page_bbox"))
    candidate_bbox = _normalized_bbox(facts.get("candidate_bbox"))
    if page_bbox is None:
        reasons.append("page_bbox_invalid")
    if not facts.get("provenance_verified"):
        reasons.append("provenance_unverified")
    if not facts.get("crop_identity_verified"):
        reasons.append("crop_identity_unverified")
    if facts.get("invalid_coordinate_bboxes_total", 0) > 0:
        reasons.append("coordinate_bbox_invalid")
    if facts.get("out_of_scope_coordinate_bboxes_total", 0) > 0:
        reasons.append("coordinate_bbox_outside_owned_bbox")

    atom_count = facts.get("atom_count", 0)
    coordinate_count = facts.get("coordinate_bboxes_total", 0)
    limits = facts.get("limits") if isinstance(facts.get("limits"), dict) else {}
    if scope == "candidate_crop":
        if candidate_bbox is None:
            reasons.append("candidate_bbox_invalid")
        elif page_bbox is not None and not _bbox_contains(page_bbox, candidate_bbox):
            reasons.append("candidate_bbox_outside_page")
        if not facts.get("exact_ownership_verified"):
            reasons.append("exact_ownership_unverified")
        if atom_count == 0:
            reasons.append("candidate_atoms_missing")
        if atom_count != coordinate_count:
            reasons.append("atom_coordinate_count_mismatch")
        if atom_count > limits.get("maximum_atoms", -1):
            reasons.append("candidate_atom_budget_exceeded")
        if facts.get("crop_count") != 1:
            reasons.append("candidate_crop_count_invalid")
        if facts.get("proposed_region_bboxes_total") != 0:
            reasons.append("candidate_region_proposal_unexpected")
    elif scope == "page":
        if candidate_bbox is not None:
            reasons.append("page_candidate_bbox_unexpected")
        if atom_count != 0 or coordinate_count != 0:
            reasons.append("page_atoms_present_before_region_proposal")
        if facts.get("crop_count") != 0:
            reasons.append("page_crop_count_invalid")
        if facts.get("invalid_proposed_region_bboxes_total", 0) > 0:
            reasons.append("page_region_bbox_invalid")
        if facts.get("out_of_page_proposed_region_bboxes_total", 0) > 0:
            reasons.append("page_region_bbox_outside_page")
        if facts.get("overlapping_proposed_region_pairs_total", 0) > 0:
            reasons.append("page_region_proposals_overlap")
        if facts.get("proposed_region_bboxes_total", 0) > limits.get(
            "maximum_page_region_proposals", -1
        ):
            reasons.append("page_region_proposal_budget_exceeded")
    else:
        reasons.append("intake_scope_invalid")

    if facts.get("model_json_bytes", 0) == 0:
        reasons.append("model_json_missing")
    elif facts.get("model_json_bytes", 0) > limits.get("maximum_model_json_bytes", -1):
        reasons.append("model_json_budget_exceeded")
    counted_tokens = facts.get("counted_input_tokens")
    if counted_tokens is not None and counted_tokens > limits.get(
        "maximum_counted_input_tokens", -1
    ):
        reasons.append("counted_input_token_budget_exceeded")
    if facts.get("image_count") != 1:
        reasons.append("image_count_invalid")
    if facts.get("pdf_count") != 0:
        reasons.append("pdf_payload_forbidden")
    if facts.get("image_bytes", 0) == 0:
        reasons.append("image_missing")
    elif facts.get("image_bytes", 0) > limits.get("maximum_image_bytes", -1):
        reasons.append("image_budget_exceeded")
    return sorted(set(reasons))


def _valid_decision(value: Any, allowed: frozenset[str]) -> bool:
    return bool(
        isinstance(value, dict)
        and set(value) == _DECISION_KEYS
        and value.get("decision") in allowed
        and _is_reason_code_list(value.get("reason_codes"))
        and isinstance(value.get("evidence_binding"), dict)
    )


def _evidence_binding(
    *,
    document_ref: Any,
    pdf_sha256: Any,
    page_ref: Any,
    page_number: Any,
    scope_ref: Any,
    table_ref: Any,
    evidence_checksum: Any,
    assessor_stage: Any,
    scope: str,
) -> dict[str, Any]:
    binding = {
        "document_ref": _closed_ref(document_ref, "document_ref"),
        "pdf_sha256": _sha256(pdf_sha256, "pdf_sha256"),
        "page_ref": _closed_ref(page_ref, "page_ref"),
        "page_number": _positive_int(page_number, "page_number"),
        "scope_ref": _closed_ref(scope_ref, "scope_ref"),
        "table_ref": (
            _closed_ref(table_ref, "table_ref") if table_ref is not None else None
        ),
        "evidence_checksum": _sha256(evidence_checksum, "evidence_checksum"),
        "assessor_stage": _reason_code(assessor_stage, "assessor_stage"),
    }
    if scope == "candidate_crop" and binding["table_ref"] is None:
        raise PdfTableIntakeContractError("pdf_table_intake_table_ref_required")
    if scope == "page" and binding["table_ref"] is not None:
        raise PdfTableIntakeContractError("pdf_table_intake_page_table_ref_forbidden")
    return binding


def _valid_evidence_binding(value: Any, *, scope: Any) -> bool:
    if not isinstance(value, dict) or set(value) != _EVIDENCE_BINDING_KEYS:
        return False
    if not all(
        _is_closed_ref(value.get(key))
        for key in ("document_ref", "page_ref", "scope_ref")
    ):
        return False
    if not _is_sha256(value.get("pdf_sha256")) or not _is_sha256(
        value.get("evidence_checksum")
    ):
        return False
    if not _is_positive_int(value.get("page_number")):
        return False
    if not (
        isinstance(value.get("assessor_stage"), str)
        and _REASON_CODE.fullmatch(value["assessor_stage"])
    ):
        return False
    table_ref = value.get("table_ref")
    if scope == "candidate_crop":
        return _is_closed_ref(table_ref)
    if scope == "page":
        return table_ref is None
    return False


def _valid_technical_facts(value: Any, config: PdfTableIntakeContractConfig) -> bool:
    if not isinstance(value, dict) or set(value) != _TECHNICAL_FACT_KEYS:
        return False
    if value.get("scope") not in INTAKE_SCOPES:
        return False
    if value.get("limits") != asdict(config):
        return False
    if set(value.get("limits") or {}) != _LIMIT_KEYS:
        return False
    if not all(
        isinstance(value.get(key), bool)
        for key in (
            "provenance_verified",
            "crop_identity_verified",
            "exact_ownership_verified",
        )
    ):
        return False
    if not all(
        _is_nonnegative_int(value.get(key))
        for key in (
            "coordinate_bboxes_total",
            "invalid_coordinate_bboxes_total",
            "out_of_scope_coordinate_bboxes_total",
            "atom_count",
            "model_json_bytes",
            "image_count",
            "crop_count",
            "pdf_count",
            "image_bytes",
            "proposed_region_bboxes_total",
            "invalid_proposed_region_bboxes_total",
            "out_of_page_proposed_region_bboxes_total",
            "overlapping_proposed_region_pairs_total",
        )
    ):
        return False
    if value.get("counted_input_tokens") is not None and not _is_nonnegative_int(
        value.get("counted_input_tokens")
    ):
        return False
    if not _is_reason_code_list(value.get("upstream_failure_reason_codes")):
        return False
    if value.get("invalid_coordinate_bboxes_total", 0) > value.get(
        "coordinate_bboxes_total", 0
    ):
        return False
    if value.get("out_of_scope_coordinate_bboxes_total", 0) > value.get(
        "coordinate_bboxes_total", 0
    ):
        return False
    proposed_regions = value.get("proposed_region_bboxes")
    if (
        not isinstance(proposed_regions, list)
        or any(_normalized_bbox(item) is None for item in proposed_regions)
        or len(proposed_regions) + value.get("invalid_proposed_region_bboxes_total", 0)
        != value.get("proposed_region_bboxes_total", 0)
        or value.get("out_of_page_proposed_region_bboxes_total", 0)
        > len(proposed_regions)
    ):
        return False
    expected_overlaps = sum(
        1
        for index, left in enumerate(proposed_regions)
        for right in proposed_regions[index + 1 :]
        if _bboxes_overlap(left, right)
    )
    if value.get("overlapping_proposed_region_pairs_total") != expected_overlaps:
        return False
    normalized_page_bbox = _normalized_bbox(value.get("page_bbox"))
    expected_outside_regions = sum(
        1
        for region in proposed_regions
        if normalized_page_bbox is None
        or not _bbox_contains(normalized_page_bbox, region)
    )
    if (
        value.get("out_of_page_proposed_region_bboxes_total")
        != expected_outside_regions
    ):
        return False
    if value.get("invalid_coordinate_bboxes_total", 0) + value.get(
        "out_of_scope_coordinate_bboxes_total", 0
    ) > value.get("coordinate_bboxes_total", 0):
        return False
    if (
        value.get("page_bbox") is not None
        and _normalized_bbox(value.get("page_bbox")) is None
    ):
        return False
    if (
        value.get("candidate_bbox") is not None
        and _normalized_bbox(value.get("candidate_bbox")) is None
    ):
        return False
    return True


def _normalized_bbox(value: Any) -> list[float] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        return None
    if any(
        isinstance(item, bool)
        or not isinstance(item, (int, float))
        or not math.isfinite(float(item))
        for item in value
    ):
        return None
    bbox = [float(item) for item in value]
    if bbox[0] < 0.0 or bbox[1] < 0.0:
        return None
    if bbox[2] <= bbox[0] or bbox[3] <= bbox[1]:
        return None
    return bbox


def _bbox_contains(outer: list[float], inner: list[float]) -> bool:
    return bool(
        inner[0] >= outer[0]
        and inner[1] >= outer[1]
        and inner[2] <= outer[2]
        and inner[3] <= outer[3]
    )


def _bboxes_overlap(left: list[float], right: list[float]) -> bool:
    return bool(
        min(left[2], right[2]) > max(left[0], right[0])
        and min(left[3], right[3]) > max(left[1], right[1])
    )


def _reason_codes(values: Iterable[str]) -> list[str]:
    try:
        items = list(values)
    except TypeError as exc:
        raise PdfTableIntakeContractError(
            "pdf_table_intake_reason_codes_invalid"
        ) from exc
    if any(
        not isinstance(item, str) or not _REASON_CODE.fullmatch(item) for item in items
    ):
        raise PdfTableIntakeContractError("pdf_table_intake_reason_codes_invalid")
    return sorted(set(items))


def _reason_code(value: Any, name: str) -> str:
    if not isinstance(value, str) or not _REASON_CODE.fullmatch(value):
        raise PdfTableIntakeContractError("pdf_table_intake_reason_code_invalid", name)
    return value


def _closed_ref(value: Any, name: str) -> str:
    if not _is_closed_ref(value):
        raise PdfTableIntakeContractError("pdf_table_intake_identity_invalid", name)
    return value


def _is_closed_ref(value: Any) -> bool:
    return bool(
        isinstance(value, str)
        and value == value.strip()
        and 0 < len(value) <= 256
        and all(ord(character) >= 32 for character in value)
    )


def _sha256(value: Any, name: str) -> str:
    if not _is_sha256(value):
        raise PdfTableIntakeContractError("pdf_table_intake_identity_invalid", name)
    return value


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and bool(_SHA256.fullmatch(value))


def _positive_int(value: Any, name: str) -> int:
    if not _is_positive_int(value):
        raise PdfTableIntakeContractError("pdf_table_intake_identity_invalid", name)
    return value


def _is_positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _is_reason_code_list(value: Any) -> bool:
    return bool(
        isinstance(value, list)
        and all(
            isinstance(item, str) and _REASON_CODE.fullmatch(item) for item in value
        )
        and value == sorted(set(value))
    )


def _nonnegative_int(value: Any, name: str) -> int:
    if not _is_nonnegative_int(value):
        raise PdfTableIntakeContractError("pdf_table_intake_integer_fact_invalid", name)
    return value


def _optional_nonnegative_int(value: Any, name: str) -> int | None:
    if value is None:
        return None
    return _nonnegative_int(value, name)


def _is_nonnegative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _metadata(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise PdfTableIntakeContractError("pdf_table_intake_metadata_invalid")
    if _contains_metadata_decision_key(value):
        raise PdfTableIntakeContractError(
            "pdf_table_intake_metadata_decision_forbidden"
        )
    frozen = copy.deepcopy(value)
    if not _finite_json_value(frozen):
        raise PdfTableIntakeContractError("pdf_table_intake_metadata_invalid")
    try:
        canonical_json_bytes(frozen)
    except (TypeError, ValueError) as exc:
        raise PdfTableIntakeContractError("pdf_table_intake_metadata_invalid") from exc
    return frozen


def _contains_metadata_decision_key(value: Any) -> bool:
    if isinstance(value, dict):
        return any(
            str(key).lower() in _METADATA_DECISION_KEYS
            or _contains_metadata_decision_key(item)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_contains_metadata_decision_key(item) for item in value)
    return False


def _finite_json_value(value: Any) -> bool:
    if value is None or isinstance(value, (str, bool, int)):
        return True
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, list):
        return all(_finite_json_value(item) for item in value)
    if isinstance(value, dict):
        return all(
            isinstance(key, str) and _finite_json_value(item)
            for key, item in value.items()
        )
    return False
