from __future__ import annotations

import copy
import hashlib
import re
from typing import Any

from broker_reports_gate1.pdf_dual_vlm_canonical_table_contracts import (
    canonical_json_bytes,
    canonicalize_table,
    sha256_json,
    validate_table_output,
)


REVIEW_TEMPLATE_SCHEMA = (
    "broker_reports_pdf_dual_vlm_canonical_table_review_template_v1"
)
REVIEW_DECISIONS_SCHEMA = (
    "broker_reports_pdf_dual_vlm_canonical_table_review_decisions_v1"
)
HUMAN_REFERENCE_SCHEMA = (
    "broker_reports_pdf_dual_vlm_canonical_table_human_reference_v1"
)
HUMAN_REFERENCE_SEAL_SCHEMA = (
    "broker_reports_pdf_dual_vlm_canonical_table_human_reference_seal_v1"
)
REFERENCE_CONTRACT_VERSION = "pdf_dual_vlm_canonical_reference_contract_v1"
DELEGATED_REVIEW_DECISIONS_SCHEMA = (
    "broker_reports_pdf_dual_vlm_canonical_table_delegated_review_decisions_v1"
)
DELEGATED_REFERENCE_SCHEMA = (
    "broker_reports_pdf_dual_vlm_canonical_table_delegated_reference_v1"
)
DELEGATED_REFERENCE_SEAL_SCHEMA = (
    "broker_reports_pdf_dual_vlm_canonical_table_delegated_reference_seal_v1"
)
DELEGATED_REFERENCE_CONTRACT_VERSION = (
    "pdf_dual_vlm_canonical_delegated_reference_contract_v1"
)

REVIEW_DECISIONS = frozenset({"approve", "correct"})
REVIEW_ATTESTATIONS = (
    "visual_crop_opened",
    "every_visible_cell_checked",
    "merged_spans_checked",
    "empty_and_unreadable_states_checked",
    "provider_outputs_not_used",
)
_AI_REVIEWER_MARKERS = (
    "ai",
    "assistant",
    "bot",
    "chatgpt",
    "claude",
    "codex",
    "gemini",
    "gpt",
    "model",
    "openai",
)


class CanonicalReferenceError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def build_review_template(
    *,
    controlled_reference: dict[str, Any],
    controlled_reference_sha256: str,
    crop_pack: dict[str, Any],
    crop_pack_sha256: str,
) -> dict[str, Any]:
    cases = controlled_reference.get("cases")
    crops = crop_pack.get("crops")
    if (
        controlled_reference.get("benchmark_id") != "pdf_dual_vlm_canonical_table_v1"
        or not isinstance(cases, list)
        or not isinstance(crops, list)
    ):
        raise CanonicalReferenceError("canonical_reference_source_invalid")
    crop_by_case = {
        str(item.get("case_id") or ""): item for item in crops if isinstance(item, dict)
    }
    entries = []
    for case in cases:
        if not isinstance(case, dict):
            raise CanonicalReferenceError("canonical_reference_case_invalid")
        case_id = str(case.get("case_id") or "")
        crop = crop_by_case.get(case_id)
        table = case.get("table")
        if (
            crop is None
            or not _identifier(case_id)
            or validate_table_output(table, table_id=case_id)
        ):
            raise CanonicalReferenceError("canonical_reference_case_invalid")
        entries.append(
            {
                "case_id": case_id,
                "crop_path": str(crop.get("crop_path") or ""),
                "crop_sha256": _sha256(crop.get("crop_sha256")),
                "crop_width": _positive_int(crop.get("crop_width")),
                "crop_height": _positive_int(crop.get("crop_height")),
                "proposed_table": canonicalize_table(table, table_id=case_id),
            }
        )
    if len(entries) != len(crop_by_case) or len(entries) != 5:
        raise CanonicalReferenceError("canonical_reference_case_set_invalid")
    template = {
        "schema_version": REVIEW_TEMPLATE_SCHEMA,
        "reference_contract_version": REFERENCE_CONTRACT_VERSION,
        "benchmark_id": "pdf_dual_vlm_canonical_table_v1",
        "controlled_reference_sha256": _sha256(controlled_reference_sha256),
        "crop_pack_sha256": _sha256(crop_pack_sha256),
        "provider_outputs_included": False,
        "consensus_included": False,
        "entries": entries,
    }
    template["template_hash"] = sha256_json(template)
    return template


def build_decisions_template(review_template: dict[str, Any]) -> dict[str, Any]:
    validate_review_template(review_template)
    return {
        "schema_version": REVIEW_DECISIONS_SCHEMA,
        "reference_contract_version": REFERENCE_CONTRACT_VERSION,
        "benchmark_id": review_template["benchmark_id"],
        "template_hash": review_template["template_hash"],
        "reviewer": {
            "kind": "human",
            "identity": "",
            "reviewed_at": "",
        },
        "entries": [
            {
                "case_id": item["case_id"],
                "decision": "",
                "attestations": {key: False for key in REVIEW_ATTESTATIONS},
                "corrected_table": None,
                "review_note": "",
            }
            for item in review_template["entries"]
        ],
    }


def build_delegated_decisions_template(
    review_template: dict[str, Any],
    *,
    delegator_identity: str,
    delegation_statement_sha256: str,
) -> dict[str, Any]:
    validate_review_template(review_template)
    delegation = {
        "kind": "explicit_user_delegation",
        "delegator_identity": delegator_identity,
        "delegation_statement_sha256": _sha256(delegation_statement_sha256),
        "delegation_statement_retained": False,
    }
    if _delegation_errors(delegation):
        raise CanonicalReferenceError("canonical_reference_delegation_invalid")
    return {
        "schema_version": DELEGATED_REVIEW_DECISIONS_SCHEMA,
        "reference_contract_version": DELEGATED_REFERENCE_CONTRACT_VERSION,
        "benchmark_id": review_template["benchmark_id"],
        "template_hash": review_template["template_hash"],
        "delegation": delegation,
        "reviewer": {
            "kind": "delegated_agent",
            "identity": "",
            "reviewed_at": "",
        },
        "entries": [
            {
                "case_id": item["case_id"],
                "decision": "",
                "attestations": {key: False for key in REVIEW_ATTESTATIONS},
                "corrected_table": None,
                "review_note": "",
            }
            for item in review_template["entries"]
        ],
    }


def finalize_human_reference(
    *,
    review_template: dict[str, Any],
    decisions: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    validate_review_template(review_template)
    _validate_decisions(decisions, review_template)
    decisions_hash = sha256_json(decisions)
    template_entries = {item["case_id"]: item for item in review_template["entries"]}
    reference_cases = []
    for decision in decisions["entries"]:
        template_entry = template_entries[decision["case_id"]]
        table = (
            template_entry["proposed_table"]
            if decision["decision"] == "approve"
            else decision["corrected_table"]
        )
        reference_cases.append(
            {
                "case_id": decision["case_id"],
                "crop_sha256": template_entry["crop_sha256"],
                "review_decision": decision["decision"],
                "table": canonicalize_table(table, table_id=decision["case_id"]),
            }
        )
    reference = {
        "schema_version": HUMAN_REFERENCE_SCHEMA,
        "reference_contract_version": REFERENCE_CONTRACT_VERSION,
        "benchmark_id": review_template["benchmark_id"],
        "human_reviewed": True,
        "reviewer": copy.deepcopy(decisions["reviewer"]),
        "lineage": {
            "review_template_hash": review_template["template_hash"],
            "review_decisions_hash": decisions_hash,
            "controlled_reference_sha256": review_template[
                "controlled_reference_sha256"
            ],
            "crop_pack_sha256": review_template["crop_pack_sha256"],
            "provider_outputs_used": False,
            "provider_consensus_used": False,
        },
        "cases": reference_cases,
    }
    errors = validate_human_reference(reference)
    if errors:
        raise CanonicalReferenceError(errors[0])
    reference_bytes = canonical_json_bytes(reference)
    reference_sha256 = hashlib.sha256(reference_bytes).hexdigest()
    seal = {
        "schema_version": HUMAN_REFERENCE_SEAL_SCHEMA,
        "reference_contract_version": REFERENCE_CONTRACT_VERSION,
        "benchmark_id": reference["benchmark_id"],
        "reference_filename": "reference.human-reviewed.private.json",
        "reference_sha256": reference_sha256,
        "reference_size_bytes": len(reference_bytes),
        "human_reviewed": True,
        "reviewer_identity": reference["reviewer"]["identity"],
        "reviewed_at": reference["reviewer"]["reviewed_at"],
    }
    seal["seal_sha256"] = sha256_json(seal)
    return reference, seal


def finalize_delegated_reference(
    *,
    review_template: dict[str, Any],
    decisions: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    validate_review_template(review_template)
    _validate_delegated_decisions(decisions, review_template)
    decisions_hash = sha256_json(decisions)
    template_entries = {item["case_id"]: item for item in review_template["entries"]}
    reference_cases = []
    for decision in decisions["entries"]:
        template_entry = template_entries[decision["case_id"]]
        table = (
            template_entry["proposed_table"]
            if decision["decision"] == "approve"
            else decision["corrected_table"]
        )
        reference_cases.append(
            {
                "case_id": decision["case_id"],
                "crop_sha256": template_entry["crop_sha256"],
                "review_decision": decision["decision"],
                "table": canonicalize_table(table, table_id=decision["case_id"]),
            }
        )
    reference = {
        "schema_version": DELEGATED_REFERENCE_SCHEMA,
        "reference_contract_version": DELEGATED_REFERENCE_CONTRACT_VERSION,
        "benchmark_id": review_template["benchmark_id"],
        "human_reviewed": False,
        "delegated_agent_reviewed": True,
        "reviewer": copy.deepcopy(decisions["reviewer"]),
        "delegation": copy.deepcopy(decisions["delegation"]),
        "lineage": {
            "review_template_hash": review_template["template_hash"],
            "review_decisions_hash": decisions_hash,
            "controlled_reference_sha256": review_template[
                "controlled_reference_sha256"
            ],
            "crop_pack_sha256": review_template["crop_pack_sha256"],
            "provider_outputs_used": False,
            "provider_consensus_used": False,
        },
        "cases": reference_cases,
    }
    errors = validate_delegated_reference(reference)
    if errors:
        raise CanonicalReferenceError(errors[0])
    reference_bytes = canonical_json_bytes(reference)
    reference_sha256 = hashlib.sha256(reference_bytes).hexdigest()
    seal = {
        "schema_version": DELEGATED_REFERENCE_SEAL_SCHEMA,
        "reference_contract_version": DELEGATED_REFERENCE_CONTRACT_VERSION,
        "benchmark_id": reference["benchmark_id"],
        "reference_filename": "reference.delegated-agent.private.json",
        "reference_sha256": reference_sha256,
        "reference_size_bytes": len(reference_bytes),
        "human_reviewed": False,
        "delegated_agent_reviewed": True,
        "reviewer_identity": reference["reviewer"]["identity"],
        "reviewed_at": reference["reviewer"]["reviewed_at"],
        "delegation_statement_sha256": reference["delegation"][
            "delegation_statement_sha256"
        ],
    }
    seal["seal_sha256"] = sha256_json(seal)
    return reference, seal


def validate_review_template(value: Any) -> list[str]:
    if not isinstance(value, dict):
        return ["canonical_reference_review_template_invalid"]
    expected = {
        "schema_version",
        "reference_contract_version",
        "benchmark_id",
        "controlled_reference_sha256",
        "crop_pack_sha256",
        "provider_outputs_included",
        "consensus_included",
        "entries",
        "template_hash",
    }
    errors = []
    if set(value) != expected:
        errors.append("canonical_reference_review_template_fields_invalid")
    if (
        value.get("schema_version") != REVIEW_TEMPLATE_SCHEMA
        or value.get("reference_contract_version") != REFERENCE_CONTRACT_VERSION
        or value.get("benchmark_id") != "pdf_dual_vlm_canonical_table_v1"
        or value.get("provider_outputs_included") is not False
        or value.get("consensus_included") is not False
        or not _is_sha256(value.get("controlled_reference_sha256"))
        or not _is_sha256(value.get("crop_pack_sha256"))
    ):
        errors.append("canonical_reference_review_template_invalid")
    entries = value.get("entries")
    if not isinstance(entries, list) or len(entries) != 5:
        errors.append("canonical_reference_review_template_entries_invalid")
    else:
        case_ids = []
        for entry in entries:
            if not isinstance(entry, dict) or set(entry) != {
                "case_id",
                "crop_path",
                "crop_sha256",
                "crop_width",
                "crop_height",
                "proposed_table",
            }:
                errors.append("canonical_reference_review_template_entry_invalid")
                continue
            case_id = entry.get("case_id")
            case_ids.append(case_id)
            if (
                not _identifier(case_id)
                or not isinstance(entry.get("crop_path"), str)
                or not entry.get("crop_path")
                or not _is_sha256(entry.get("crop_sha256"))
                or not _is_positive_int(entry.get("crop_width"))
                or not _is_positive_int(entry.get("crop_height"))
                or validate_table_output(entry.get("proposed_table"), table_id=case_id)
            ):
                errors.append("canonical_reference_review_template_entry_invalid")
        if len(case_ids) != len(set(case_ids)):
            errors.append("canonical_reference_review_template_case_duplicate")
    unhashed = copy.deepcopy(value)
    actual_hash = unhashed.pop("template_hash", None)
    if not _is_sha256(actual_hash) or sha256_json(unhashed) != actual_hash:
        errors.append("canonical_reference_review_template_hash_invalid")
    return sorted(set(errors))


def validate_human_reference(value: Any) -> list[str]:
    if not isinstance(value, dict):
        return ["canonical_human_reference_invalid"]
    expected = {
        "schema_version",
        "reference_contract_version",
        "benchmark_id",
        "human_reviewed",
        "reviewer",
        "lineage",
        "cases",
    }
    errors = []
    if set(value) != expected:
        errors.append("canonical_human_reference_fields_invalid")
    if (
        value.get("schema_version") != HUMAN_REFERENCE_SCHEMA
        or value.get("reference_contract_version") != REFERENCE_CONTRACT_VERSION
        or value.get("benchmark_id") != "pdf_dual_vlm_canonical_table_v1"
        or value.get("human_reviewed") is not True
    ):
        errors.append("canonical_human_reference_invalid")
    if _reviewer_errors(value.get("reviewer")):
        errors.append("canonical_human_reference_reviewer_invalid")
    lineage = value.get("lineage")
    if (
        not isinstance(lineage, dict)
        or set(lineage)
        != {
            "review_template_hash",
            "review_decisions_hash",
            "controlled_reference_sha256",
            "crop_pack_sha256",
            "provider_outputs_used",
            "provider_consensus_used",
        }
        or not all(
            _is_sha256(lineage.get(key))
            for key in (
                "review_template_hash",
                "review_decisions_hash",
                "controlled_reference_sha256",
                "crop_pack_sha256",
            )
        )
        or lineage.get("provider_outputs_used") is not False
        or lineage.get("provider_consensus_used") is not False
    ):
        errors.append("canonical_human_reference_lineage_invalid")
    cases = value.get("cases")
    if not isinstance(cases, list) or len(cases) != 5:
        errors.append("canonical_human_reference_cases_invalid")
    else:
        case_ids = []
        for case in cases:
            if not isinstance(case, dict) or set(case) != {
                "case_id",
                "crop_sha256",
                "review_decision",
                "table",
            }:
                errors.append("canonical_human_reference_case_invalid")
                continue
            case_id = case.get("case_id")
            case_ids.append(case_id)
            if (
                not _identifier(case_id)
                or not _is_sha256(case.get("crop_sha256"))
                or case.get("review_decision") not in REVIEW_DECISIONS
                or validate_table_output(case.get("table"), table_id=case_id)
            ):
                errors.append("canonical_human_reference_case_invalid")
        if len(case_ids) != len(set(case_ids)):
            errors.append("canonical_human_reference_case_duplicate")
    return sorted(set(errors))


def validate_reference_seal(*, reference: dict[str, Any], seal: Any) -> list[str]:
    errors = validate_human_reference(reference)
    if not isinstance(seal, dict):
        return sorted(set(errors + ["canonical_human_reference_seal_invalid"]))
    expected = {
        "schema_version",
        "reference_contract_version",
        "benchmark_id",
        "reference_filename",
        "reference_sha256",
        "reference_size_bytes",
        "human_reviewed",
        "reviewer_identity",
        "reviewed_at",
        "seal_sha256",
    }
    reference_bytes = canonical_json_bytes(reference)
    if (
        set(seal) != expected
        or seal.get("schema_version") != HUMAN_REFERENCE_SEAL_SCHEMA
        or seal.get("reference_contract_version") != REFERENCE_CONTRACT_VERSION
        or seal.get("benchmark_id") != reference.get("benchmark_id")
        or seal.get("reference_filename") != "reference.human-reviewed.private.json"
        or seal.get("reference_sha256") != hashlib.sha256(reference_bytes).hexdigest()
        or seal.get("reference_size_bytes") != len(reference_bytes)
        or seal.get("human_reviewed") is not True
        or seal.get("reviewer_identity")
        != _object(reference.get("reviewer")).get("identity")
        or seal.get("reviewed_at")
        != _object(reference.get("reviewer")).get("reviewed_at")
    ):
        errors.append("canonical_human_reference_seal_invalid")
    unhashed = copy.deepcopy(seal)
    actual_hash = unhashed.pop("seal_sha256", None)
    if not _is_sha256(actual_hash) or sha256_json(unhashed) != actual_hash:
        errors.append("canonical_human_reference_seal_hash_invalid")
    return sorted(set(errors))


def validate_delegated_reference(value: Any) -> list[str]:
    if not isinstance(value, dict):
        return ["canonical_delegated_reference_invalid"]
    expected = {
        "schema_version",
        "reference_contract_version",
        "benchmark_id",
        "human_reviewed",
        "delegated_agent_reviewed",
        "reviewer",
        "delegation",
        "lineage",
        "cases",
    }
    errors = []
    if set(value) != expected:
        errors.append("canonical_delegated_reference_fields_invalid")
    if (
        value.get("schema_version") != DELEGATED_REFERENCE_SCHEMA
        or value.get("reference_contract_version")
        != DELEGATED_REFERENCE_CONTRACT_VERSION
        or value.get("benchmark_id") != "pdf_dual_vlm_canonical_table_v1"
        or value.get("human_reviewed") is not False
        or value.get("delegated_agent_reviewed") is not True
    ):
        errors.append("canonical_delegated_reference_invalid")
    if _delegated_reviewer_errors(value.get("reviewer")):
        errors.append("canonical_delegated_reference_reviewer_invalid")
    if _delegation_errors(value.get("delegation")):
        errors.append("canonical_delegated_reference_delegation_invalid")
    lineage = value.get("lineage")
    if (
        not isinstance(lineage, dict)
        or set(lineage)
        != {
            "review_template_hash",
            "review_decisions_hash",
            "controlled_reference_sha256",
            "crop_pack_sha256",
            "provider_outputs_used",
            "provider_consensus_used",
        }
        or not all(
            _is_sha256(lineage.get(key))
            for key in (
                "review_template_hash",
                "review_decisions_hash",
                "controlled_reference_sha256",
                "crop_pack_sha256",
            )
        )
        or lineage.get("provider_outputs_used") is not False
        or lineage.get("provider_consensus_used") is not False
    ):
        errors.append("canonical_delegated_reference_lineage_invalid")
    errors.extend(_reference_case_errors(value.get("cases"), delegated=True))
    return sorted(set(errors))


def validate_delegated_reference_seal(
    *,
    reference: dict[str, Any],
    seal: Any,
) -> list[str]:
    errors = validate_delegated_reference(reference)
    if not isinstance(seal, dict):
        return sorted(set(errors + ["canonical_delegated_reference_seal_invalid"]))
    expected = {
        "schema_version",
        "reference_contract_version",
        "benchmark_id",
        "reference_filename",
        "reference_sha256",
        "reference_size_bytes",
        "human_reviewed",
        "delegated_agent_reviewed",
        "reviewer_identity",
        "reviewed_at",
        "delegation_statement_sha256",
        "seal_sha256",
    }
    reference_bytes = canonical_json_bytes(reference)
    if (
        set(seal) != expected
        or seal.get("schema_version") != DELEGATED_REFERENCE_SEAL_SCHEMA
        or seal.get("reference_contract_version")
        != DELEGATED_REFERENCE_CONTRACT_VERSION
        or seal.get("benchmark_id") != reference.get("benchmark_id")
        or seal.get("reference_filename")
        != "reference.delegated-agent.private.json"
        or seal.get("reference_sha256") != hashlib.sha256(reference_bytes).hexdigest()
        or seal.get("reference_size_bytes") != len(reference_bytes)
        or seal.get("human_reviewed") is not False
        or seal.get("delegated_agent_reviewed") is not True
        or seal.get("reviewer_identity")
        != _object(reference.get("reviewer")).get("identity")
        or seal.get("reviewed_at")
        != _object(reference.get("reviewer")).get("reviewed_at")
        or seal.get("delegation_statement_sha256")
        != _object(reference.get("delegation")).get("delegation_statement_sha256")
    ):
        errors.append("canonical_delegated_reference_seal_invalid")
    unhashed = copy.deepcopy(seal)
    actual_hash = unhashed.pop("seal_sha256", None)
    if not _is_sha256(actual_hash) or sha256_json(unhashed) != actual_hash:
        errors.append("canonical_delegated_reference_seal_hash_invalid")
    return sorted(set(errors))


def _validate_decisions(decisions: Any, review_template: dict[str, Any]) -> None:
    if not isinstance(decisions, dict) or set(decisions) != {
        "schema_version",
        "reference_contract_version",
        "benchmark_id",
        "template_hash",
        "reviewer",
        "entries",
    }:
        raise CanonicalReferenceError("canonical_reference_decisions_invalid")
    if (
        decisions.get("schema_version") != REVIEW_DECISIONS_SCHEMA
        or decisions.get("reference_contract_version") != REFERENCE_CONTRACT_VERSION
        or decisions.get("benchmark_id") != review_template.get("benchmark_id")
        or decisions.get("template_hash") != review_template.get("template_hash")
        or _reviewer_errors(decisions.get("reviewer"))
    ):
        raise CanonicalReferenceError("canonical_reference_decisions_invalid")
    entries = decisions.get("entries")
    expected_ids = [item["case_id"] for item in review_template["entries"]]
    if (
        not isinstance(entries, list)
        or [item.get("case_id") for item in entries if isinstance(item, dict)]
        != expected_ids
    ):
        raise CanonicalReferenceError("canonical_reference_decision_set_invalid")
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {
            "case_id",
            "decision",
            "attestations",
            "corrected_table",
            "review_note",
        }:
            raise CanonicalReferenceError("canonical_reference_decision_invalid")
        if entry.get("decision") not in REVIEW_DECISIONS:
            raise CanonicalReferenceError("canonical_reference_decision_invalid")
        attestations = entry.get("attestations")
        if (
            not isinstance(attestations, dict)
            or set(attestations) != set(REVIEW_ATTESTATIONS)
            or not all(attestations.get(key) is True for key in REVIEW_ATTESTATIONS)
        ):
            raise CanonicalReferenceError(
                "canonical_reference_review_attestation_incomplete"
            )
        corrected = entry.get("corrected_table")
        if entry["decision"] == "approve" and corrected is not None:
            raise CanonicalReferenceError("canonical_reference_correction_unexpected")
        if entry["decision"] == "correct" and validate_table_output(
            corrected, table_id=entry["case_id"]
        ):
            raise CanonicalReferenceError("canonical_reference_correction_invalid")
        note = entry.get("review_note")
        if not isinstance(note, str) or len(note) > 2000:
            raise CanonicalReferenceError("canonical_reference_review_note_invalid")


def _validate_delegated_decisions(
    decisions: Any,
    review_template: dict[str, Any],
) -> None:
    if not isinstance(decisions, dict) or set(decisions) != {
        "schema_version",
        "reference_contract_version",
        "benchmark_id",
        "template_hash",
        "delegation",
        "reviewer",
        "entries",
    }:
        raise CanonicalReferenceError("canonical_delegated_decisions_invalid")
    if (
        decisions.get("schema_version") != DELEGATED_REVIEW_DECISIONS_SCHEMA
        or decisions.get("reference_contract_version")
        != DELEGATED_REFERENCE_CONTRACT_VERSION
        or decisions.get("benchmark_id") != review_template.get("benchmark_id")
        or decisions.get("template_hash") != review_template.get("template_hash")
        or _delegation_errors(decisions.get("delegation"))
        or _delegated_reviewer_errors(decisions.get("reviewer"))
    ):
        raise CanonicalReferenceError("canonical_delegated_decisions_invalid")
    entries = decisions.get("entries")
    expected_ids = [item["case_id"] for item in review_template["entries"]]
    if (
        not isinstance(entries, list)
        or [item.get("case_id") for item in entries if isinstance(item, dict)]
        != expected_ids
    ):
        raise CanonicalReferenceError("canonical_reference_decision_set_invalid")
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {
            "case_id",
            "decision",
            "attestations",
            "corrected_table",
            "review_note",
        }:
            raise CanonicalReferenceError("canonical_reference_decision_invalid")
        if entry.get("decision") not in REVIEW_DECISIONS:
            raise CanonicalReferenceError("canonical_reference_decision_invalid")
        attestations = entry.get("attestations")
        if (
            not isinstance(attestations, dict)
            or set(attestations) != set(REVIEW_ATTESTATIONS)
            or not all(attestations.get(key) is True for key in REVIEW_ATTESTATIONS)
        ):
            raise CanonicalReferenceError(
                "canonical_reference_review_attestation_incomplete"
            )
        corrected = entry.get("corrected_table")
        if entry["decision"] == "approve" and corrected is not None:
            raise CanonicalReferenceError("canonical_reference_correction_unexpected")
        if entry["decision"] == "correct" and validate_table_output(
            corrected, table_id=entry["case_id"]
        ):
            raise CanonicalReferenceError("canonical_reference_correction_invalid")
        note = entry.get("review_note")
        if not isinstance(note, str) or len(note) > 2000:
            raise CanonicalReferenceError("canonical_reference_review_note_invalid")


def _reference_case_errors(value: Any, *, delegated: bool) -> list[str]:
    prefix = "canonical_delegated_reference" if delegated else "canonical_human_reference"
    errors = []
    if not isinstance(value, list) or len(value) != 5:
        return [prefix + "_cases_invalid"]
    case_ids = []
    for case in value:
        if not isinstance(case, dict) or set(case) != {
            "case_id",
            "crop_sha256",
            "review_decision",
            "table",
        }:
            errors.append(prefix + "_case_invalid")
            continue
        case_id = case.get("case_id")
        case_ids.append(case_id)
        if (
            not _identifier(case_id)
            or not _is_sha256(case.get("crop_sha256"))
            or case.get("review_decision") not in REVIEW_DECISIONS
            or validate_table_output(case.get("table"), table_id=case_id)
        ):
            errors.append(prefix + "_case_invalid")
    if len(case_ids) != len(set(case_ids)):
        errors.append(prefix + "_case_duplicate")
    return errors


def _reviewer_errors(value: Any) -> list[str]:
    if not isinstance(value, dict) or set(value) != {
        "kind",
        "identity",
        "reviewed_at",
    }:
        return ["reviewer_invalid"]
    identity = value.get("identity")
    reviewed_at = value.get("reviewed_at")
    if (
        value.get("kind") != "human"
        or not isinstance(identity, str)
        or not 1 <= len(identity.strip()) <= 200
        or any(
            re.search(rf"(^|\W){re.escape(marker)}($|\W)", identity.lower())
            for marker in _AI_REVIEWER_MARKERS
        )
        or not isinstance(reviewed_at, str)
        or not re.fullmatch(
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})",
            reviewed_at,
        )
    ):
        return ["reviewer_invalid"]
    return []


def _delegated_reviewer_errors(value: Any) -> list[str]:
    if not isinstance(value, dict) or set(value) != {
        "kind",
        "identity",
        "reviewed_at",
    }:
        return ["delegated_reviewer_invalid"]
    identity = value.get("identity")
    reviewed_at = value.get("reviewed_at")
    if (
        value.get("kind") != "delegated_agent"
        or not isinstance(identity, str)
        or not 1 <= len(identity.strip()) <= 200
        or not isinstance(reviewed_at, str)
        or not re.fullmatch(
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})",
            reviewed_at,
        )
    ):
        return ["delegated_reviewer_invalid"]
    return []


def _delegation_errors(value: Any) -> list[str]:
    if not isinstance(value, dict) or set(value) != {
        "kind",
        "delegator_identity",
        "delegation_statement_sha256",
        "delegation_statement_retained",
    }:
        return ["delegation_invalid"]
    identity = value.get("delegator_identity")
    if (
        value.get("kind") != "explicit_user_delegation"
        or not isinstance(identity, str)
        or not 1 <= len(identity.strip()) <= 200
        or not _is_sha256(value.get("delegation_statement_sha256"))
        or value.get("delegation_statement_retained") is not False
    ):
        return ["delegation_invalid"]
    return []


def _identifier(value: Any) -> bool:
    return isinstance(value, str) and bool(
        re.fullmatch(r"[A-Za-z0-9_.:-]{1,160}", value)
    )


def _sha256(value: Any) -> str:
    if not _is_sha256(value):
        raise CanonicalReferenceError("canonical_reference_sha256_invalid")
    return str(value)


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and bool(re.fullmatch(r"[0-9a-f]{64}", value))


def _positive_int(value: Any) -> int:
    if not _is_positive_int(value):
        raise CanonicalReferenceError("canonical_reference_dimension_invalid")
    return int(value)


def _is_positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
