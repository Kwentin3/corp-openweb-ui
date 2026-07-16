#!/usr/bin/env python3
"""Build and confirm a compact human review delta for fact locators."""

from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import html
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
SERVICE_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

import pdf_dual_vlm_fact_review as review  # noqa: E402


BULK_ATTESTATION_SCHEMA = "broker_reports_pdf_dual_vlm_fact_bulk_attestation_v1"
LOCATOR_DELTA_SCHEMA = "broker_reports_pdf_dual_vlm_fact_locator_delta_v1"
LOCATOR_CONFIRMATION_SCHEMA = review.LOCATOR_CONFIRMATION_SCHEMA
REFERENCE_PREPARATION_SCHEMA = (
    "broker_reports_pdf_dual_vlm_fact_reference_preparation_v1"
)
ATTESTATION_SCOPE_ALL_VISIBLE = "all_visible_regions_values_and_negative_classification"
HEADERLESS_CODE = "header_not_present_in_source"
TEXT_MISMATCH_CODE = "source_locator_text_mismatch_requires_human_confirmation"
ALLOWED_FACT_CHANGE_KEYS = frozenset({"source_regions", "uncertainty"})
CONFIRMATION_TEMPLATE = (
    "Подтверждаю locator-delta SHA-256: {payload_sha256}; "
    "все {changed_facts} изменений источника верны."
)
FROZEN_ROMAN_ATTESTATION_STATEMENTS = (
    "Там слишком много флагов, но всё верно, претензий нет, "
    "идентифицировал таблицы правильно, регион определил правильно, "
    "интерпретировал их значения, перевёл обратно в текст из растра, тоже всё "
    "правильно, замечаний нет, всё отлично.",
    "betterment_p02 — это не таблица, а оглавление; проверяющий — Роман",
)


class LocatorDeltaError(RuntimeError):
    pass


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build or confirm a compact locator review delta"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build")
    _add_lineage_arguments(build)
    build.add_argument("--output-dir", required=True)
    build.add_argument("--reviewer-identity", required=True)
    build.add_argument("--reviewed-at", required=True)
    build.add_argument("--statement", action="append", required=True)
    build.add_argument(
        "--attestation-scope",
        choices=(ATTESTATION_SCOPE_ALL_VISIBLE,),
        required=True,
    )
    confirm = commands.add_parser("confirm")
    _add_lineage_arguments(confirm)
    confirm.add_argument("--attestation", required=True)
    confirm.add_argument("--delta", required=True)
    confirm.add_argument("--confirmation", required=True)
    confirm.add_argument("--confirmed-at", required=True)
    confirm.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    lineage = {
        "baseline_proposed_path": Path(args.baseline_proposed).resolve(),
        "baseline_review_index_path": Path(args.baseline_review_index).resolve(),
        "revised_proposed_path": Path(args.revised_proposed).resolve(),
        "revised_review_index_path": Path(args.revised_review_index).resolve(),
        "revised_preparation_path": Path(args.revised_preparation).resolve(),
        "revised_artifact_root": Path(args.revised_artifact_root).resolve(),
    }
    if args.command == "build":
        result = build_locator_delta(
            **lineage,
            output_dir=Path(args.output_dir).resolve(),
            reviewer_identity=args.reviewer_identity,
            reviewed_at=args.reviewed_at,
            statements=args.statement,
            attestation_scope=args.attestation_scope,
        )
    else:
        result = confirm_locator_delta(
            **lineage,
            attestation_path=Path(args.attestation).resolve(),
            delta_path=Path(args.delta).resolve(),
            confirmation=args.confirmation,
            confirmed_at=args.confirmed_at,
            output_dir=Path(args.output_dir).resolve(),
        )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


def _add_lineage_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--baseline-proposed", required=True)
    parser.add_argument("--baseline-review-index", required=True)
    parser.add_argument("--revised-proposed", required=True)
    parser.add_argument("--revised-review-index", required=True)
    parser.add_argument("--revised-preparation", required=True)
    parser.add_argument("--revised-artifact-root", required=True)


def build_locator_delta(
    *,
    baseline_proposed_path: Path,
    baseline_review_index_path: Path,
    revised_proposed_path: Path,
    revised_review_index_path: Path,
    revised_preparation_path: Path,
    revised_artifact_root: Path,
    output_dir: Path,
    reviewer_identity: str,
    reviewed_at: str,
    statements: list[str],
    attestation_scope: str,
) -> dict[str, Any]:
    _require_fresh(output_dir)
    baseline = _json_object(baseline_proposed_path, "locator_delta_baseline_invalid")
    baseline_index = _json_object(
        baseline_review_index_path, "locator_delta_baseline_index_invalid"
    )
    revised = _json_object(revised_proposed_path, "locator_delta_revised_invalid")
    revised_index = _json_object(
        revised_review_index_path, "locator_delta_revised_index_invalid"
    )
    revised_preparation = _json_object(
        revised_preparation_path, "locator_delta_revised_preparation_invalid"
    )
    _validate_inputs(baseline, baseline_index, revised, revised_index)
    _validate_revised_preparation(
        revised_preparation,
        revised=revised,
        revised_index=revised_index,
    )
    reviewer = {
        "kind": "human",
        "identity": reviewer_identity.strip(),
        "reviewed_at": reviewed_at,
    }
    review._require_human_reviewer(reviewer)
    clean_statements = [item.strip() for item in statements if item.strip()]
    if not clean_statements:
        raise LocatorDeltaError("locator_delta_attestation_statement_missing")

    changes = _fact_changes(baseline, revised)
    changed_ids = {item["fact_key"] for item in changes}
    _require_revised_sources_complete(revised, changed_ids)
    attestation = _bulk_attestation(
        baseline=baseline,
        baseline_index=baseline_index,
        reviewer=reviewer,
        statements=clean_statements,
        changes=changes,
        attestation_scope=attestation_scope,
    )
    groups, image_data = _groups(
        changes=changes,
        revised_index=revised_index,
        artifact_root=revised_artifact_root,
    )
    delta = _locator_delta_value(
        baseline=baseline,
        baseline_index=baseline_index,
        revised=revised,
        revised_index=revised_index,
        revised_preparation=revised_preparation,
        revised_preparation_path=revised_preparation_path,
        attestation=attestation,
        changes=changes,
        groups=groups,
    )

    attestation_path = output_dir / "review.bulk-attestation.private.json"
    delta_path = output_dir / "locator-delta.private.json"
    html_path = output_dir / "locator-delta.html"
    rendered = _render(delta, image_data).encode("utf-8")
    written: list[Path] = []
    try:
        _write_new(attestation_path, review.canonical_json_bytes(attestation))
        written.append(attestation_path)
        _write_new(delta_path, review.canonical_json_bytes(delta))
        written.append(delta_path)
        _write_new(html_path, rendered)
        written.append(html_path)
    except Exception:
        for path in reversed(written):
            path.unlink(missing_ok=True)
        raise
    return {
        "status": (
            "locator_delta_human_confirmation_required"
            if changes
            else "locator_delta_empty"
        ),
        "changed_facts": len(changes),
        "groups": len(groups),
        "payload_sha256": delta["payload_sha256"],
        "attestation": str(attestation_path),
        "attestation_checksum": attestation["attestation_checksum"],
        "delta": str(delta_path),
        "delta_checksum": delta["delta_checksum"],
        "html": str(html_path),
        "html_sha256": hashlib.sha256(rendered).hexdigest(),
        "confirmation_text": delta["confirmation_text"],
    }


def _locator_delta_value(
    *,
    baseline: dict[str, Any],
    baseline_index: dict[str, Any],
    revised: dict[str, Any],
    revised_index: dict[str, Any],
    revised_preparation: dict[str, Any],
    revised_preparation_path: Path,
    attestation: dict[str, Any],
    changes: list[dict[str, Any]],
    groups: list[dict[str, Any]],
) -> dict[str, Any]:
    delta = {
        "schema_version": LOCATOR_DELTA_SCHEMA,
        "benchmark_id": revised["benchmark_id"],
        "manifest_sha256": revised["manifest_sha256"],
        "source_policy": {
            "revised_preparation_binding_valid": True,
            "locator_geometry_lineage": {
                "declared_origin": "legacy_pdf_table_strategy_terminal",
                "legacy_provider_vlm_involvement_disclosed": True,
                "legacy_terminal_file_reverified_by_delta_builder": False,
            },
            "current_dual_vlm_run1_lineage": {
                "direct_run1_artifacts_are_builder_inputs": False,
                "absence_from_upstream_preparation_proven_here": False,
            },
            "revised_preparation": {
                "schema_version": revised_preparation["schema_version"],
                "preparation_sha256": revised_preparation["preparation_sha256"],
                "file_sha256": hashlib.sha256(
                    revised_preparation_path.read_bytes()
                ).hexdigest(),
                "legacy_reference_sha256": revised_preparation[
                    "legacy_reference_sha256"
                ],
                "legacy_terminal_sha256": revised_preparation["legacy_terminal_sha256"],
            },
        },
        "baseline": {
            "proposed_reference_sha256": review.sha256_json(baseline),
            "review_index_sha256": baseline_index["index_sha256"],
        },
        "revised": {
            "proposed_reference_sha256": review.sha256_json(revised),
            "review_index_sha256": revised_index["index_sha256"],
        },
        "bulk_attestation_checksum": attestation["attestation_checksum"],
        "summary": _summary(changes, groups),
        "groups": groups,
    }
    payload_sha = review.sha256_json(delta)
    delta["payload_sha256"] = payload_sha
    delta["confirmation_text"] = CONFIRMATION_TEMPLATE.format(
        payload_sha256=payload_sha,
        changed_facts=len(changes),
    )
    delta["delta_checksum"] = review.sha256_json(delta)
    return delta


def confirm_locator_delta(
    *,
    baseline_proposed_path: Path,
    baseline_review_index_path: Path,
    revised_proposed_path: Path,
    revised_review_index_path: Path,
    revised_preparation_path: Path,
    revised_artifact_root: Path,
    attestation_path: Path,
    delta_path: Path,
    confirmation: str,
    confirmed_at: str,
    output_dir: Path,
) -> dict[str, Any]:
    baseline = _json_object(
        baseline_proposed_path, "locator_confirmation_baseline_invalid"
    )
    baseline_index = _json_object(
        baseline_review_index_path, "locator_confirmation_baseline_index_invalid"
    )
    revised = _json_object(
        revised_proposed_path, "locator_confirmation_revised_invalid"
    )
    revised_index = _json_object(
        revised_review_index_path, "locator_confirmation_revised_index_invalid"
    )
    revised_preparation = _json_object(
        revised_preparation_path,
        "locator_confirmation_revised_preparation_invalid",
    )
    attestation = _json_object(
        attestation_path, "locator_confirmation_attestation_invalid"
    )
    stored_delta = _json_object(delta_path, "locator_confirmation_delta_invalid")
    _validate_inputs(baseline, baseline_index, revised, revised_index)
    _validate_revised_preparation(
        revised_preparation,
        revised=revised,
        revised_index=revised_index,
    )
    changes = _fact_changes(baseline, revised)
    if not changes:
        raise LocatorDeltaError("locator_confirmation_delta_empty")
    changed_ids = {item["fact_key"] for item in changes}
    _require_revised_sources_complete(revised, changed_ids)
    expected_attestation = _validated_bulk_attestation(
        attestation,
        baseline=baseline,
        baseline_index=baseline_index,
        changes=changes,
    )
    groups, _image_data = _groups(
        changes=changes,
        revised_index=revised_index,
        artifact_root=revised_artifact_root,
    )
    expected_delta = _locator_delta_value(
        baseline=baseline,
        baseline_index=baseline_index,
        revised=revised,
        revised_index=revised_index,
        revised_preparation=revised_preparation,
        revised_preparation_path=revised_preparation_path,
        attestation=expected_attestation,
        changes=changes,
        groups=groups,
    )
    if review.sha256_json(stored_delta) != review.sha256_json(expected_delta):
        raise LocatorDeltaError("locator_confirmation_delta_lineage_mismatch")
    if confirmation != expected_delta["confirmation_text"]:
        raise LocatorDeltaError("locator_confirmation_text_mismatch")

    intent = _review_intent_from_confirmation(
        revised_index=revised_index,
        attestation=expected_attestation,
        payload_sha256=expected_delta["payload_sha256"],
        confirmed_at=confirmed_at,
    )
    decisions = review.PdfDualVlmFactReviewDecisionFactory().create_from_intent(
        review_index=revised_index,
        intent=intent,
    )
    confirmation_record = {
        "schema_version": LOCATOR_CONFIRMATION_SCHEMA,
        "locator_delta_payload_sha256": expected_delta["payload_sha256"],
        "locator_delta_checksum": expected_delta["delta_checksum"],
        "bulk_attestation_checksum": expected_attestation["attestation_checksum"],
        "confirmation_text": confirmation,
        "reviewer": copy.deepcopy(intent["reviewer"]),
        "review_intent_sha256": review.sha256_json(intent),
        "expected_review_decisions_sha256": review.sha256_json(decisions),
        "authority": {
            "final_decisions_must_use_review_decision_factory": True,
            "final_reference_created_here": False,
        },
    }
    confirmation_record["confirmation_checksum"] = review.sha256_json(
        confirmation_record
    )

    _require_fresh(output_dir)
    intent_path = output_dir / "review.intent.private.json"
    confirmation_path = output_dir / "locator-confirmation.private.json"
    written: list[Path] = []
    try:
        _write_new(intent_path, review.canonical_json_bytes(intent))
        written.append(intent_path)
        _write_new(
            confirmation_path,
            review.canonical_json_bytes(confirmation_record),
        )
        written.append(confirmation_path)
    except Exception:
        for path in reversed(written):
            path.unlink(missing_ok=True)
        raise
    return {
        "status": "locator_confirmation_review_intent_ready",
        "payload_sha256": expected_delta["payload_sha256"],
        "review_intent": str(intent_path),
        "review_intent_sha256": confirmation_record["review_intent_sha256"],
        "expected_review_decisions_sha256": confirmation_record[
            "expected_review_decisions_sha256"
        ],
        "confirmation_record": str(confirmation_path),
        "confirmation_checksum": confirmation_record["confirmation_checksum"],
    }


def _validated_bulk_attestation(
    value: dict[str, Any],
    *,
    baseline: dict[str, Any],
    baseline_index: dict[str, Any],
    changes: list[dict[str, Any]],
) -> dict[str, Any]:
    reviewer = value.get("reviewer")
    statements = value.get("statements")
    reported_scope = value.get("reported_scope")
    if (
        value.get("schema_version") != BULK_ATTESTATION_SCHEMA
        or not isinstance(reviewer, dict)
        or not isinstance(statements, list)
        or any(not isinstance(item, str) or not item.strip() for item in statements)
        or not isinstance(reported_scope, dict)
        or not isinstance(reported_scope.get("scope_kind"), str)
    ):
        raise LocatorDeltaError("locator_confirmation_attestation_invalid")
    review._require_human_reviewer(reviewer)
    if (
        reviewer.get("identity") != "Роман"
        or tuple(statements) != FROZEN_ROMAN_ATTESTATION_STATEMENTS
    ):
        raise LocatorDeltaError("locator_confirmation_attestation_scope_unproven")
    expected = _bulk_attestation(
        baseline=baseline,
        baseline_index=baseline_index,
        reviewer=reviewer,
        statements=statements,
        changes=changes,
        attestation_scope=reported_scope["scope_kind"],
    )
    if review.sha256_json(value) != review.sha256_json(expected):
        raise LocatorDeltaError("locator_confirmation_attestation_lineage_mismatch")
    return expected


def _review_intent_from_confirmation(
    *,
    revised_index: dict[str, Any],
    attestation: dict[str, Any],
    payload_sha256: str,
    confirmed_at: str,
) -> dict[str, Any]:
    scope = attestation["reported_scope"]
    attested_at = _review_timestamp(attestation["reviewer"]["reviewed_at"])
    confirmed_timestamp = _review_timestamp(confirmed_at)
    if confirmed_timestamp < attested_at:
        raise LocatorDeltaError("locator_confirmation_timestamp_precedes_review")
    classifications = scope["human_reported_negative_classifications"]
    expected_cards = {
        *scope["human_reported_table_region_cards"],
        *scope["human_reported_negative_cards"],
    }
    cards = {card["card_id"]: card for card in revised_index["cards"]}
    if expected_cards != set(cards):
        raise LocatorDeltaError("locator_confirmation_scope_mismatch")
    entries = []
    reviewer_identity = attestation["reviewer"]["identity"]
    for card_id in sorted(cards):
        card = cards[card_id]
        region = card.get("region")
        if card["card_kind"] == "negative_case":
            classification = classifications.get(card["case_id"])
            if classification == "table_of_contents_not_table":
                note = (
                    f"{reviewer_identity} подтвердил: страница является "
                    "оглавлением, а не "
                    f"таблицей; locator-delta SHA-256: {payload_sha256}."
                )
            elif classification == "not_table":
                note = (
                    f"{reviewer_identity} подтвердил: страница не содержит "
                    "таблицы; "
                    f"locator-delta SHA-256: {payload_sha256}."
                )
            else:
                raise LocatorDeltaError(
                    "locator_confirmation_negative_classification_invalid"
                )
            facts: list[dict[str, Any]] = []
        else:
            if not isinstance(region, dict):
                raise LocatorDeltaError("locator_confirmation_region_missing")
            note = (
                f"{reviewer_identity} подтвердил регион, значения и привязки к PDF; "
                f"locator-delta SHA-256: {payload_sha256}."
            )
            facts = region["facts"]
        entries.append(
            {
                "card_id": card_id,
                "region_decision": "approve",
                "region_note": note,
                "corrected_region": None,
                "checklist": {key: "pass" for key in card["checklist_fields"]},
                "fact_decisions": [
                    {
                        "fact_id": fact["fact_id"],
                        "decision": "confirm",
                        "note": (
                            f"{reviewer_identity} подтвердил значение, "
                            "интерпретацию и адрес "
                            "источника; locator-delta SHA-256: "
                            f"{payload_sha256}."
                        ),
                        "corrected_fact": None,
                    }
                    for fact in facts
                ],
            }
        )
    return {
        "schema_version": review.REVIEW_INTENT_SCHEMA,
        "review_index_sha256": revised_index["index_sha256"],
        "proposed_reference_sha256": revised_index["proposed_reference_sha256"],
        "reviewer": {
            "kind": "human",
            "identity": reviewer_identity,
            "reviewed_at": confirmed_at,
        },
        "entries": entries,
    }


def _review_timestamp(value: Any) -> datetime:
    if not isinstance(value, str):
        raise LocatorDeltaError("locator_confirmation_timestamp_invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise LocatorDeltaError("locator_confirmation_timestamp_invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise LocatorDeltaError("locator_confirmation_timestamp_invalid")
    return parsed


def _validate_inputs(
    baseline: dict[str, Any],
    baseline_index: dict[str, Any],
    revised: dict[str, Any],
    revised_index: dict[str, Any],
) -> None:
    for value, index in ((baseline, baseline_index), (revised, revised_index)):
        errors = review.validate_proposed_reference(value)
        if errors:
            raise LocatorDeltaError(f"locator_delta_proposal_invalid:{errors[0]}")
        errors = review.validate_review_index(index)
        if errors:
            raise LocatorDeltaError(f"locator_delta_review_index_invalid:{errors[0]}")
        if index["proposed_reference_sha256"] != review.sha256_json(value):
            raise LocatorDeltaError("locator_delta_proposal_index_lineage_mismatch")
        _validate_index_projection(value, index)
    if (
        baseline["benchmark_id"] != revised["benchmark_id"]
        or baseline["manifest_sha256"] != revised["manifest_sha256"]
    ):
        raise LocatorDeltaError("locator_delta_benchmark_lineage_mismatch")
    if review.sha256_json(_semantic_projection(baseline)) != review.sha256_json(
        _semantic_projection(revised)
    ):
        raise LocatorDeltaError("locator_delta_semantic_change_forbidden")


def _validate_revised_preparation(
    preparation: dict[str, Any],
    *,
    revised: dict[str, Any],
    revised_index: dict[str, Any],
) -> None:
    required = {
        "schema_version",
        "human_reviewed",
        "may_be_used_for_scoring",
        "manifest_sha256",
        "proposed_reference_sha256",
        "legacy_reference_sha256",
        "legacy_terminal_sha256",
        "review_index_sha256",
        "review_html_sha256",
        "proposal_role",
        "human_action_required",
        "preparation_sha256",
    }
    if set(preparation) != required:
        raise LocatorDeltaError("locator_delta_revised_preparation_invalid")
    unsigned = copy.deepcopy(preparation)
    preparation_sha = unsigned.pop("preparation_sha256")
    if (
        preparation.get("schema_version") != REFERENCE_PREPARATION_SCHEMA
        or preparation.get("human_reviewed") is not False
        or preparation.get("may_be_used_for_scoring") is not False
        or preparation.get("human_action_required") is not True
        or preparation.get("proposal_role") != "unreviewed_source_only_candidate"
        or not _sha256(preparation_sha)
        or review.sha256_json(unsigned) != preparation_sha
        or preparation.get("manifest_sha256") != revised["manifest_sha256"]
        or preparation.get("proposed_reference_sha256") != review.sha256_json(revised)
        or preparation.get("review_index_sha256") != revised_index["index_sha256"]
        or any(
            not _sha256(preparation.get(key))
            for key in (
                "legacy_reference_sha256",
                "legacy_terminal_sha256",
                "review_html_sha256",
            )
        )
    ):
        raise LocatorDeltaError("locator_delta_revised_preparation_invalid")


def _validate_index_projection(
    proposal: dict[str, Any], review_index: dict[str, Any]
) -> None:
    cards = {card["card_id"]: card for card in review_index["cards"]}
    expected = set()
    for case in proposal["cases"]:
        base = {
            "case_id": case["case_id"],
            "document_id": case["document_id"],
            "pdf_sha256": case["pdf_sha256"],
            "page_number": case["page_number"],
            "expected_kind": case["expected_kind"],
        }
        if case["expected_kind"] == "negative":
            card_id = f"negative:{case['case_id']}"
            expected.add(card_id)
            card = cards.get(card_id)
            if (
                not isinstance(card, dict)
                or any(card.get(key) != value for key, value in base.items())
                or card.get("region") is not None
                or card.get("crop_artifact") is not None
                or card.get("page_artifact", {}).get("sha256") != case["page_sha256"]
            ):
                raise LocatorDeltaError(
                    "locator_delta_review_index_projection_mismatch"
                )
            continue
        for region in case["regions"]:
            card_id = f"region:{case['case_id']}:{region['region_id']}"
            expected.add(card_id)
            card = cards.get(card_id)
            if (
                not isinstance(card, dict)
                or any(card.get(key) != value for key, value in base.items())
                or review.sha256_json(card.get("region")) != review.sha256_json(region)
                or card.get("crop_artifact", {}).get("sha256") != region["crop_sha256"]
                or card.get("page_artifact", {}).get("sha256") != case["page_sha256"]
            ):
                raise LocatorDeltaError(
                    "locator_delta_review_index_projection_mismatch"
                )
    if set(cards) != expected:
        raise LocatorDeltaError("locator_delta_review_index_projection_mismatch")


def _semantic_projection(value: dict[str, Any]) -> dict[str, Any]:
    projected = copy.deepcopy(value)
    for case in projected["cases"]:
        for region in case["regions"]:
            for fact in region["facts"]:
                fact.pop("source_regions", None)
                fact.pop("uncertainty", None)
    return projected


def _fact_changes(
    baseline: dict[str, Any], revised: dict[str, Any]
) -> list[dict[str, Any]]:
    old = _fact_map(baseline)
    new = _fact_map(revised)
    if set(old) != set(new):
        raise LocatorDeltaError("locator_delta_fact_identity_changed")
    result = []
    for key in sorted(old):
        before = old[key]
        after = new[key]
        if review.sha256_json(before) == review.sha256_json(after):
            continue
        changed_keys = {
            field
            for field in before
            if review.sha256_json(before[field]) != review.sha256_json(after[field])
        }
        if not changed_keys <= ALLOWED_FACT_CHANGE_KEYS:
            raise LocatorDeltaError("locator_delta_fact_semantic_change_forbidden")
        change_kinds = []
        old_sources = before["source_regions"]
        new_sources = after["source_regions"]
        for role in ("row_label", "header", "value", "context"):
            if review.sha256_json(old_sources[role]) != review.sha256_json(
                new_sources[role]
            ):
                change_kinds.append(f"{role}_locator_changed")
        old_uncertainty = set(before["uncertainty"])
        new_uncertainty = set(after["uncertainty"])
        if HEADERLESS_CODE in new_uncertainty - old_uncertainty:
            change_kinds.append("header_absence_classification_added")
        if TEXT_MISMATCH_CODE in new_uncertainty:
            change_kinds.append("locator_text_mismatch_requires_confirmation")
        case_id, region_id, fact_id = key.split(":", 2)
        result.append(
            {
                "fact_key": key,
                "case_id": case_id,
                "region_id": region_id,
                "fact_id": fact_id,
                "before_sha256": review.sha256_json(before),
                "after_sha256": review.sha256_json(after),
                "change_kinds": change_kinds,
                "revised_fact": copy.deepcopy(after),
            }
        )
    return result


def _fact_map(value: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result = {}
    for case in value["cases"]:
        for region in case["regions"]:
            for fact in region["facts"]:
                key = f"{case['case_id']}:{region['region_id']}:{fact['fact_id']}"
                if key in result:
                    raise LocatorDeltaError("locator_delta_fact_duplicate")
                result[key] = fact
    return result


def _require_revised_sources_complete(
    revised: dict[str, Any], changed_ids: set[str]
) -> None:
    seen = set()
    for case in revised["cases"]:
        for region in case["regions"]:
            crop_sha = str(region["crop_sha256"])
            for fact in region["facts"]:
                key = f"{case['case_id']}:{region['region_id']}:{fact['fact_id']}"
                review._require_complete_fact(
                    fact,
                    expected_artifact_sha256=crop_sha,
                    path=f"$.facts[{key}]",
                )
                if key in changed_ids:
                    seen.add(key)
    if seen != changed_ids:
        raise LocatorDeltaError("locator_delta_changed_fact_missing")


def _bulk_attestation(
    *,
    baseline: dict[str, Any],
    baseline_index: dict[str, Any],
    reviewer: dict[str, Any],
    statements: list[str],
    changes: list[dict[str, Any]],
    attestation_scope: str,
) -> dict[str, Any]:
    if attestation_scope != ATTESTATION_SCOPE_ALL_VISIBLE:
        raise LocatorDeltaError("locator_delta_attestation_scope_invalid")
    table_cards = [
        card for card in baseline_index["cards"] if card["card_kind"] == "table_region"
    ]
    negative_cards = [
        card for card in baseline_index["cards"] if card["card_kind"] == "negative_case"
    ]
    negative_classifications = {
        card["case_id"]: (
            "table_of_contents_not_table"
            if card["case_id"] == "betterment_p02"
            else "not_table"
        )
        for card in negative_cards
    }
    value = {
        "schema_version": BULK_ATTESTATION_SCHEMA,
        "benchmark_id": baseline["benchmark_id"],
        "manifest_sha256": baseline["manifest_sha256"],
        "proposed_reference_sha256": review.sha256_json(baseline),
        "review_index_sha256": baseline_index["index_sha256"],
        "reviewer": copy.deepcopy(reviewer),
        "statements": list(statements),
        "reported_scope": {
            "scope_kind": attestation_scope,
            "human_reported_table_region_cards": [
                card["card_id"] for card in table_cards
            ],
            "human_reported_negative_cards": [
                card["card_id"] for card in negative_cards
            ],
            "human_reported_negative_classifications": negative_classifications,
            "human_reported_visible_values_and_interpretations": True,
            "human_reported_semantic_objections": 0,
        },
        "authority": {
            "authoritative_for_final_reference": False,
            "may_be_used_as_review_intent": False,
            "final_decisions_must_use_review_decision_factory": True,
        },
        "pending": {
            "locator_delta_confirmation_required": bool(changes),
            "changed_fact_keys": [item["fact_key"] for item in changes],
        },
    }
    value["attestation_checksum"] = review.sha256_json(value)
    return value


def _groups(
    *,
    changes: list[dict[str, Any]],
    revised_index: dict[str, Any],
    artifact_root: Path,
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    cards = {card["card_id"]: card for card in revised_index["cards"]}
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for change in changes:
        grouped.setdefault((change["case_id"], change["region_id"]), []).append(change)
    result = []
    images = {}
    for case_id, region_id in sorted(grouped):
        card_id = f"region:{case_id}:{region_id}"
        card = cards.get(card_id)
        if not isinstance(card, dict):
            raise LocatorDeltaError("locator_delta_review_card_missing")
        artifact = card.get("crop_artifact")
        if not isinstance(artifact, dict):
            raise LocatorDeltaError("locator_delta_crop_artifact_missing")
        path = (artifact_root / case_id / str(artifact.get("filename"))).resolve()
        try:
            path.relative_to(artifact_root)
        except ValueError as exc:
            raise LocatorDeltaError("locator_delta_crop_path_escape") from exc
        payload = path.read_bytes()
        if path.suffix.casefold() != ".png" or hashlib.sha256(
            payload
        ).hexdigest() != artifact.get("sha256"):
            raise LocatorDeltaError("locator_delta_crop_identity_mismatch")
        group_changes = grouped[(case_id, region_id)]
        result.append(
            {
                "card_id": card_id,
                "case_id": case_id,
                "region_id": region_id,
                "crop_artifact": copy.deepcopy(artifact),
                "headerless_facts": sum(
                    "header_absence_classification_added" in item["change_kinds"]
                    for item in group_changes
                ),
                "locator_changed_facts": sum(
                    any(
                        kind.endswith("_locator_changed")
                        for kind in item["change_kinds"]
                    )
                    for item in group_changes
                ),
                "text_mismatch_facts": sum(
                    "locator_text_mismatch_requires_confirmation"
                    in item["change_kinds"]
                    for item in group_changes
                ),
                "fact_changes": copy.deepcopy(group_changes),
            }
        )
        images[card_id] = "data:image/png;base64," + base64.b64encode(payload).decode(
            "ascii"
        )
    return result, images


def _summary(
    changes: list[dict[str, Any]], groups: list[dict[str, Any]]
) -> dict[str, Any]:
    return {
        "changed_facts": len(changes),
        "region_groups": len(groups),
        "headerless_classifications": sum(
            "header_absence_classification_added" in item["change_kinds"]
            for item in changes
        ),
        "locator_updates": sum(
            any(kind.endswith("_locator_changed") for kind in item["change_kinds"])
            for item in changes
        ),
        "text_mismatch_confirmations": sum(
            "locator_text_mismatch_requires_confirmation" in item["change_kinds"]
            for item in changes
        ),
    }


def _render(delta: dict[str, Any], image_data: dict[str, str]) -> str:
    summary = delta["summary"]
    cards = "".join(
        _render_group(group, image_data[group["card_id"]]) for group in delta["groups"]
    )
    confirmation = html.escape(delta["confirmation_text"])
    confirmation_json = json.dumps(delta["confirmation_text"], ensure_ascii=False)
    state_json = json.dumps(
        {"groups": len(delta["groups"])}, ensure_ascii=False, separators=(",", ":")
    )
    return f"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Короткая проверка привязок к PDF</title>
<style>
:root {{ font-family:system-ui,sans-serif; color-scheme:light dark }}
body {{ margin:0 }} main {{ max-width:90rem; margin:auto; padding:1rem }}
article {{ border:1px solid currentColor; border-radius:.5rem; margin:1rem 0; padding:1rem }}
.state {{ border-left:.35rem solid #1d70b8; padding:.75rem; margin:1rem 0 }}
.state.error {{ border-color:#d4351c }} .state.empty {{ border-color:#f47738 }}
.image-wrap {{ position:relative; display:inline-block; max-width:100% }}
img {{ display:block; max-width:100%; max-height:60rem; border:1px solid #777 }}
.box {{ position:absolute; box-sizing:border-box; pointer-events:none; border:.18rem solid }}
.row {{ border-color:#1d70b8 }} .value {{ border-color:#00703c }} .header {{ border-color:#f47738 }}
.warning {{ border-left:.35rem solid #d4351c; padding:.75rem }}
textarea {{ width:100%; box-sizing:border-box }}
button {{ padding:.7rem 1rem; font-weight:700; background:#276ef1; color:#fff; border:.15rem solid #174ea6 }}
button:disabled {{ cursor:not-allowed; opacity:.65 }}
:focus-visible {{ outline:.25rem solid #ffbf47; outline-offset:.2rem }}
details {{ margin:.75rem 0 }} code {{ overflow-wrap:anywhere }}
</style></head><body><main id="app" aria-busy="false">
<h1>Короткая проверка привязок к PDF</h1>
<p>Основные таблицы и значения вы уже подтвердили. Здесь остались только изменения
в адресах источника: где на изображении находятся строка, заголовок и значение.</p>
<ul><li>Изменено фактов: {summary["changed_facts"]}.</li>
<li>Компактных карточек: {summary["region_groups"]}.</li>
<li>Таблицы без отдельного заголовка столбца: {summary["headerless_classifications"]} факта.</li>
<li>Добавлены или уточнены рамки: {summary["locator_updates"]} фактов.</li>
<li>Особо проверить расхождение старого чтения и изображения: {summary["text_mismatch_confirmations"]} факт.</li></ul>
<section id="loading" class="state" role="status" aria-live="polite">Загружаем материалы…</section>
<section id="error" class="state error" role="alert" hidden>Не удалось открыть материалы проверки.</section>
<section id="empty" class="state empty" role="status" hidden>Изменений для проверки нет.</section>
<section id="success" class="state" role="status" aria-live="polite" hidden>Материалы готовы. Просмотрите {summary["region_groups"]} карточек ниже.</section>
<section id="review-content" hidden>{cards}
<section aria-labelledby="confirm-title"><h2 id="confirm-title">Подтверждение</h2>
<p>Если всё верно, скопируйте строку и отправьте её мне в чат:</p>
<label for="confirmation">Строка подтверждения всей дельты</label>
<textarea id="confirmation" rows="3" readonly>{confirmation}</textarea>
<button id="copy" type="button" aria-describedby="feedback" disabled>Скопировать строку подтверждения</button>
<p id="feedback" role="status" aria-live="polite">Строка ещё не скопирована.</p></section></section>
<noscript><style>#loading,#success{{display:none!important}}#review-content[hidden]{{display:block!important}}</style>
<p class="state">JavaScript отключён. Просмотрите карточки и скопируйте строку из поля вручную.</p></noscript>
</main><script id="state-data" type="application/json">{state_json}</script>
<script>(()=>{{'use strict';const button=document.getElementById('copy');
const feedback=document.getElementById('feedback');const app=document.getElementById('app');
const loading=document.getElementById('loading');const error=document.getElementById('error');
const empty=document.getElementById('empty');const success=document.getElementById('success');
const content=document.getElementById('review-content');const text={confirmation_json};let state;
try{{state=JSON.parse(document.getElementById('state-data').textContent);loading.hidden=true;
if(!Number.isInteger(state.groups)||state.groups<0)throw new Error('invalid state');
if(state.groups===0){{empty.hidden=false;return;}}success.hidden=false;content.hidden=false;button.disabled=false;
}}catch(cause){{loading.hidden=true;error.hidden=false;return;}}
button.addEventListener('click',async()=>{{
button.disabled=true;button.setAttribute('aria-busy','true');app.setAttribute('aria-busy','true');
feedback.textContent='Копируем строку…';try{{if(navigator.clipboard&&navigator.clipboard.writeText){{
await navigator.clipboard.writeText(text);}}else{{const area=document.getElementById('confirmation');
area.focus();area.select();if(!document.execCommand('copy'))throw new Error('copy failed');}}
feedback.textContent='Строка скопирована. Отправьте её мне в чат.';
}}catch(error){{feedback.textContent='Не удалось скопировать автоматически. Выделите строку в поле и скопируйте вручную.';
}}finally{{button.disabled=false;button.setAttribute('aria-busy','false');app.setAttribute('aria-busy','false');}}
}});}})();</script></body></html>"""


def _render_group(group: dict[str, Any], uri: str) -> str:
    overlays = _overlays(group["fact_changes"])
    facts = "".join(_render_fact(item) for item in group["fact_changes"])
    note = ""
    if group["text_mismatch_facts"]:
        note = (
            '<p class="warning"><strong>Особая проверка:</strong> старое автоматическое '
            "чтение одной цифры расходилось с изображением. Ориентируйтесь на изображение "
            "и значение в списке ниже.</p>"
        )
    return f"""<article><h2>{html.escape(group["case_id"])} · {html.escape(group["region_id"])}</h2>
<p>Без отдельного заголовка столбца: {group["headerless_facts"]}. Рамки добавлены или уточнены: {group["locator_changed_facts"]}.</p>
{note}<figure><figcaption>Синий — строка, зелёный — значение, оранжевый — заголовок.</figcaption>
<span class="image-wrap"><img src="{uri}" alt="Фрагмент таблицы {html.escape(group["case_id"])}">{overlays}</span></figure>
<details><summary>Показать список проверяемых значений ({len(group["fact_changes"])})</summary>{facts}</details></article>"""


def _render_fact(change: dict[str, Any]) -> str:
    fact = change["revised_fact"]
    header = " → ".join(fact["header_path"]) or "отдельного заголовка нет"
    warning = (
        " — проверьте особенно внимательно"
        if "locator_text_mismatch_requires_confirmation" in change["change_kinds"]
        else ""
    )
    return (
        f"<p><code>{html.escape(change['fact_id'])}</code>: "
        f"{html.escape(fact['row_label'])} — <strong>{html.escape(fact['visible_value'])}</strong>; "
        f"заголовок: {html.escape(header)}{warning}.</p>"
    )


def _overlays(changes: list[dict[str, Any]]) -> str:
    seen = set()
    result = []
    for change in changes:
        sources = change["revised_fact"]["source_regions"]
        items = [("row", sources["row_label"]), ("value", sources["value"])]
        items.extend(("header", locator) for locator in sources["header"])
        for role, locator in items:
            if not isinstance(locator, dict):
                continue
            bbox = locator["bbox_normalized"]
            key = (role, tuple(bbox), locator["visible_text"])
            if key in seen:
                continue
            seen.add(key)
            x0, y0, x1, y1 = (float(item) for item in bbox)
            label = {"row": "Строка", "value": "Значение", "header": "Заголовок"}[role]
            result.append(
                f'<span class="box {role}" aria-label="{label}: {html.escape(locator["visible_text"])}" '
                f'style="left:{x0 * 100:.6f}%;top:{y0 * 100:.6f}%;'
                f'width:{(x1 - x0) * 100:.6f}%;height:{(y1 - y0) * 100:.6f}%"></span>'
            )
    return "".join(result)


def _json_object(path: Path, code: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise LocatorDeltaError(code) from exc
    if not isinstance(value, dict):
        raise LocatorDeltaError(code)
    return value


def _sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _require_fresh(path: Path) -> None:
    if path.exists() and any(path.iterdir()):
        raise LocatorDeltaError("locator_delta_fresh_output_required")
    path.mkdir(parents=True, exist_ok=True)


def _write_new(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(payload)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (LocatorDeltaError, review.ReviewContractError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2) from exc
