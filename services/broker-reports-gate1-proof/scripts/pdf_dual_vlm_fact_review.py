from __future__ import annotations

import base64
import copy
import hashlib
import html
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence


PROPOSED_REFERENCE_SCHEMA = "broker_reports_pdf_dual_vlm_fact_proposed_reference_v1"
REVIEW_INDEX_SCHEMA = "broker_reports_pdf_dual_vlm_fact_review_index_v1"
REVIEW_INTENT_SCHEMA = "broker_reports_pdf_dual_vlm_fact_review_intent_v1"
REVIEW_DECISIONS_SCHEMA = "broker_reports_pdf_dual_vlm_fact_review_decisions_v1"
FINAL_REFERENCE_SCHEMA = "broker_reports_pdf_dual_vlm_fact_human_reference_v1"
FINAL_REFERENCE_SEAL_SCHEMA = "broker_reports_pdf_dual_vlm_fact_human_reference_seal_v1"

FACTORY_REQUIRED = (
    "PdfDualVlmFactReviewDecisionFactory.create is the only decision-ledger entrypoint"
)
FORBIDDEN = (
    "HTML may export operator intent only; it must not decide facts, mint a "
    "human reviewer, or set human_reviewed"
)

REGION_DECISIONS = {"approve", "correct", "ambiguous", "reject"}
FACT_DECISIONS = {"confirm", "correct", "ambiguous", "reject"}
CHECKLIST_VALUES = {"pass", "issue", "uncertain"}
CHECKLIST_FIELDS = (
    "crop_completeness",
    "row_label",
    "value",
    "sign",
    "period",
    "currency",
    "scale",
    "header_relationship",
    "source_address",
    "missing_or_invented_facts",
)
EVIDENCE_MEDIUM_CHECKLIST_FIELD = "evidence_medium"
EVIDENCE_MEDIA = {"text_layer", "mixed", "raster"}
SIGN_VALUES = {"positive", "negative", "zero", "unknown", "not_applicable"}
EXPECTED_KINDS = {"table", "negative"}
CARD_KINDS = {"table_region", "negative_case"}
_HEX_64 = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_FORBIDDEN_REVIEWER_TOKENS = {
    "agent",
    "ai",
    "assistant",
    "bot",
    "chatgpt",
    "claude",
    "codex",
    "gemini",
    "llm",
    "machine",
    "model",
    "openai",
}
_FORBIDDEN_REVIEWER_FRAGMENTS = ("агент", "ассистент", "бот", "модель", "ии")


class ReviewContractError(ValueError):
    def __init__(self, code: str, path: str = "$") -> None:
        self.code = code
        self.path = path
        super().__init__(f"{code}:{path}")


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def validate_proposed_reference(value: Any) -> list[str]:
    errors: list[str] = []
    _validate_proposed_reference(value, errors, "$")
    return errors


def validate_review_index(value: Any) -> list[str]:
    errors: list[str] = []
    _validate_review_index(value, errors, "$")
    return errors


def validate_review_decisions(value: Any, review_index: Any) -> list[str]:
    errors: list[str] = []
    _validate_review_index(review_index, errors, "$.review_index")
    if errors:
        return errors
    _validate_review_decisions(value, review_index, errors, "$")
    return errors


def generate_review_pack(
    *,
    proposed_reference: dict[str, Any],
    page_artifact_paths: Mapping[str, str | Path],
    crop_artifact_paths: Mapping[str, str | Path],
    output_dir: str | Path,
) -> dict[str, Any]:
    """Create a source-only static review pack.

    Crop map keys use ``<case_id>:<region_id>``. The generated browser code only
    records form intent. It has no finalization or domain-decision capability.
    """

    _require_valid(
        validate_proposed_reference(proposed_reference),
        "proposed_reference_invalid",
    )
    proposal = copy.deepcopy(proposed_reference)
    proposal_sha = sha256_json(proposal)
    cases = proposal["cases"]
    expected_page_keys = {case["case_id"] for case in cases}
    if set(page_artifact_paths) != expected_page_keys:
        raise ReviewContractError("review_page_artifact_keys_mismatch")
    expected_crop_keys = {
        _crop_key(case["case_id"], region["region_id"])
        for case in cases
        for region in case["regions"]
    }
    if set(crop_artifact_paths) != expected_crop_keys:
        raise ReviewContractError("review_crop_artifact_keys_mismatch")

    cards: list[dict[str, Any]] = []
    image_data: dict[str, dict[str, str | None]] = {}
    for case in cases:
        case_id = case["case_id"]
        page_meta, page_uri = _read_image_artifact(
            page_artifact_paths[case_id], case["page_sha256"]
        )
        base = {
            "case_id": case_id,
            "document_id": case["document_id"],
            "pdf_sha256": case["pdf_sha256"],
            "page_number": case["page_number"],
            "expected_kind": case["expected_kind"],
            "page_artifact": page_meta,
            "checklist_fields": list(CHECKLIST_FIELDS),
        }
        if case["expected_kind"] == "negative":
            card_id = f"negative:{case_id}"
            card = {
                "card_id": card_id,
                "card_kind": "negative_case",
                **base,
                "region": None,
                "crop_artifact": None,
            }
            cards.append(card)
            image_data[card_id] = {"page": page_uri, "crop": None}
            continue
        for region in case["regions"]:
            region_id = region["region_id"]
            card_id = f"region:{case_id}:{region_id}"
            crop_meta, crop_uri = _read_image_artifact(
                crop_artifact_paths[_crop_key(case_id, region_id)],
                region["crop_sha256"],
            )
            card = {
                "card_id": card_id,
                "card_kind": "table_region",
                **base,
                "checklist_fields": [
                    *CHECKLIST_FIELDS,
                    EVIDENCE_MEDIUM_CHECKLIST_FIELD,
                ],
                "region": copy.deepcopy(region),
                "crop_artifact": crop_meta,
            }
            cards.append(card)
            image_data[card_id] = {"page": page_uri, "crop": crop_uri}

    review_index: dict[str, Any] = {
        "schema_version": REVIEW_INDEX_SCHEMA,
        "benchmark_id": proposal["benchmark_id"],
        "manifest_sha256": proposal["manifest_sha256"],
        "proposed_reference_sha256": proposal_sha,
        "cards": cards,
    }
    review_index["index_sha256"] = sha256_json(review_index)
    _require_valid(validate_review_index(review_index), "review_index_invalid")

    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    index_path = target / "review.index.json"
    html_path = target / "review.html"
    _write_new(index_path, canonical_json_bytes(review_index))
    rendered = _render_review_html(review_index, image_data).encode("utf-8")
    try:
        _write_new(html_path, rendered)
    except Exception:
        index_path.unlink(missing_ok=True)
        raise
    return {
        "review_index": review_index,
        "review_index_path": str(index_path),
        "review_html_path": str(html_path),
        "review_html_sha256": hashlib.sha256(rendered).hexdigest(),
    }


class PdfDualVlmFactReviewDecisionFactory:
    def create(
        self,
        *,
        review_index: dict[str, Any],
        reviewer: dict[str, Any],
        entries: Sequence[dict[str, Any]],
        prior_decisions: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        _require_valid(validate_review_index(review_index), "review_index_invalid")
        _require_human_reviewer(reviewer)
        normalized_entries = copy.deepcopy(list(entries))
        _require_valid(
            _validate_entries_for_index(normalized_entries, review_index),
            "review_entries_invalid",
        )

        ledger: list[dict[str, Any]] = []
        prior_by_card: dict[str, dict[str, Any]] = {}
        if prior_decisions is not None:
            _require_valid(
                validate_review_decisions(prior_decisions, review_index),
                "prior_review_decisions_invalid",
            )
            ledger = copy.deepcopy(prior_decisions["ledger"])
            prior_by_card = {
                entry["card_id"]: entry for entry in prior_decisions["entries"]
            }

        previous_hash = ledger[-1]["event_sha256"] if ledger else None
        current_identity = reviewer["identity"].strip()
        last_event_by_card = {event["card_id"]: event for event in ledger}
        for entry in sorted(normalized_entries, key=lambda item: item["card_id"]):
            card_id = entry["card_id"]
            entry_sha = sha256_json(entry)
            prior_entry = prior_by_card.get(card_id)
            last_event = last_event_by_card.get(card_id)
            unchanged = (
                prior_entry is not None and sha256_json(prior_entry) == entry_sha
            )
            same_reviewer = (
                last_event is not None
                and last_event["reviewer_identity"] == current_identity
            )
            if unchanged and same_reviewer:
                continue
            sequence = len(ledger) + 1
            event_id = (
                "review_event_"
                + hashlib.sha256(
                    canonical_json_bytes(
                        [sequence, card_id, entry_sha, previous_hash, current_identity]
                    )
                ).hexdigest()[:24]
            )
            event = {
                "sequence": sequence,
                "event_id": event_id,
                "recorded_at": reviewer["reviewed_at"],
                "reviewer_kind": "human",
                "reviewer_identity": current_identity,
                "card_id": card_id,
                "entry_sha256": entry_sha,
                "previous_event_sha256": previous_hash,
            }
            event["event_sha256"] = sha256_json(event)
            ledger.append(event)
            previous_hash = event["event_sha256"]

        decisions = {
            "schema_version": REVIEW_DECISIONS_SCHEMA,
            "review_index_sha256": review_index["index_sha256"],
            "proposed_reference_sha256": review_index["proposed_reference_sha256"],
            "reviewer": {
                "kind": "human",
                "identity": current_identity,
                "reviewed_at": reviewer["reviewed_at"],
            },
            "entries": normalized_entries,
            "ledger": ledger,
        }
        _require_valid(
            validate_review_decisions(decisions, review_index),
            "review_decisions_invalid",
        )
        return decisions

    def create_from_intent(
        self,
        *,
        review_index: dict[str, Any],
        intent: dict[str, Any],
        prior_decisions: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        _require_review_intent(intent, review_index)
        return self.create(
            review_index=review_index,
            reviewer=intent["reviewer"],
            entries=intent["entries"],
            prior_decisions=prior_decisions,
        )


def finalize_human_reference(
    *,
    proposed_reference: dict[str, Any],
    review_index: dict[str, Any],
    review_decisions: dict[str, Any],
    output_dir: str | Path,
) -> dict[str, Any]:
    """Finalize a human reference without consulting provider outputs.

    The irreversible boundary is exclusive creation of the reference file. No
    validation or domain interpretation runs after that boundary.
    """

    _require_human_reviewer(_object(review_decisions).get("reviewer"))
    _require_valid(
        validate_proposed_reference(proposed_reference),
        "proposed_reference_invalid",
    )
    _require_valid(validate_review_index(review_index), "review_index_invalid")
    _require_valid(
        validate_review_decisions(review_decisions, review_index),
        "review_decisions_invalid",
    )
    if not review_index["cards"]:
        raise ReviewContractError("review_index_empty")
    proposal_sha = sha256_json(proposed_reference)
    if proposal_sha != review_index["proposed_reference_sha256"]:
        raise ReviewContractError("review_proposed_reference_lineage_mismatch")
    if review_decisions["proposed_reference_sha256"] != proposal_sha:
        raise ReviewContractError("review_decision_proposal_lineage_mismatch")

    entries = {entry["card_id"]: entry for entry in review_decisions["entries"]}
    cards = {card["card_id"]: card for card in review_index["cards"]}
    final_cases: dict[str, dict[str, Any]] = {}
    for card_id in sorted(cards):
        card = cards[card_id]
        entry = entries[card_id]
        case = final_cases.setdefault(
            card["case_id"],
            {
                "case_id": card["case_id"],
                "document_id": card["document_id"],
                "pdf_sha256": card["pdf_sha256"],
                "page_number": card["page_number"],
                "page_sha256": card["page_artifact"]["sha256"],
                "expected_kind": card["expected_kind"],
                "regions": [],
                "negative_review": None,
            },
        )
        effective_region = _effective_region(card, entry)
        effective_facts = (
            effective_region["facts"] if effective_region is not None else []
        )
        fact_decisions = {item["fact_id"]: item for item in entry["fact_decisions"]}
        reviewed_facts = []
        region_allows_acceptance = entry["region_decision"] in {
            "approve",
            "correct",
        }
        for fact in effective_facts:
            fact_review = fact_decisions[fact["fact_id"]]
            decision = fact_review["decision"]
            selected = fact_review["corrected_fact"] if decision == "correct" else fact
            fact_human_approved = decision in {"confirm", "correct"}
            accepted = region_allows_acceptance and fact_human_approved
            if fact_human_approved:
                _require_complete_fact(
                    selected,
                    expected_artifact_sha256=effective_region["crop_sha256"],
                    path=f"$.entries[{card_id}].facts[{fact['fact_id']}]",
                )
            reviewed_facts.append(
                {
                    "fact": copy.deepcopy(selected),
                    "review_decision": decision,
                    "review_note": fact_review["note"],
                    "accepted_for_scoring": accepted,
                }
            )
        region_review = {
            "decision": entry["region_decision"],
            "note": entry["region_note"],
            "checklist": copy.deepcopy(entry["checklist"]),
        }
        if card["card_kind"] == "negative_case" and effective_region is None:
            case["negative_review"] = region_review
            continue
        if effective_region is None:
            raise ReviewContractError("review_corrected_region_missing", card_id)
        reviewed_region = copy.deepcopy(effective_region)
        reviewed_region["facts"] = reviewed_facts
        reviewed_region["review"] = region_review
        case["regions"].append(reviewed_region)
        if card["card_kind"] == "negative_case":
            case["expected_kind"] = "table"
            case["negative_review"] = region_review

    reviewer = review_decisions["reviewer"]
    reference = {
        "schema_version": FINAL_REFERENCE_SCHEMA,
        "benchmark_id": proposed_reference["benchmark_id"],
        "manifest_sha256": proposed_reference["manifest_sha256"],
        "human_reviewed": True,
        "reviewer": copy.deepcopy(reviewer),
        "lineage": {
            "proposed_reference_sha256": proposal_sha,
            "review_index_sha256": review_index["index_sha256"],
            "review_decisions_sha256": sha256_json(review_decisions),
            "decision_ledger_tail_sha256": review_decisions["ledger"][-1][
                "event_sha256"
            ],
        },
        "cases": [final_cases[key] for key in sorted(final_cases)],
    }
    reference_bytes = canonical_json_bytes(reference)
    reference_sha = hashlib.sha256(reference_bytes).hexdigest()
    seal = {
        "schema_version": FINAL_REFERENCE_SEAL_SCHEMA,
        "reference_filename": "reference.human-reviewed.private.json",
        "reference_sha256": reference_sha,
        "reference_size_bytes": len(reference_bytes),
        "human_reviewed": True,
        "reviewer_identity": reviewer["identity"],
        "reviewed_at": reviewer["reviewed_at"],
        "manifest_sha256": proposed_reference["manifest_sha256"],
        "proposed_reference_sha256": proposal_sha,
        "review_index_sha256": review_index["index_sha256"],
        "review_decisions_sha256": sha256_json(review_decisions),
    }
    seal["seal_sha256"] = sha256_json(seal)
    seal_bytes = canonical_json_bytes(seal)

    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    reference_path = target / "reference.human-reviewed.private.json"
    seal_path = target / "reference.human-reviewed.private.sha256.json"
    if reference_path.exists() or seal_path.exists():
        raise ReviewContractError("review_final_output_exists")
    _write_new(reference_path, reference_bytes)
    try:
        _write_new(seal_path, seal_bytes)
    except Exception:
        reference_path.unlink(missing_ok=True)
        raise
    return {
        "reference": reference,
        "seal": seal,
        "reference_path": str(reference_path),
        "seal_path": str(seal_path),
    }


def _validate_proposed_reference(value: Any, errors: list[str], path: str) -> None:
    if not _closed_object(
        value,
        {"schema_version", "benchmark_id", "manifest_sha256", "cases"},
        errors,
        path,
    ):
        return
    if value["schema_version"] != PROPOSED_REFERENCE_SCHEMA:
        errors.append(f"proposed_reference_schema_invalid:{path}.schema_version")
    _validate_identifier(value["benchmark_id"], errors, f"{path}.benchmark_id")
    _validate_hash(value["manifest_sha256"], errors, f"{path}.manifest_sha256")
    cases = value["cases"]
    if not isinstance(cases, list):
        errors.append(f"proposed_reference_cases_invalid:{path}.cases")
        return
    seen: set[str] = set()
    for index, case in enumerate(cases):
        case_path = f"{path}.cases[{index}]"
        if not _closed_object(
            case,
            {
                "case_id",
                "document_id",
                "pdf_sha256",
                "page_number",
                "page_sha256",
                "expected_kind",
                "regions",
            },
            errors,
            case_path,
        ):
            continue
        _validate_identifier(case["case_id"], errors, f"{case_path}.case_id")
        _validate_identifier(case["document_id"], errors, f"{case_path}.document_id")
        if case["case_id"] in seen:
            errors.append(f"proposed_reference_case_duplicate:{case_path}.case_id")
        seen.add(case["case_id"])
        _validate_hash(case["pdf_sha256"], errors, f"{case_path}.pdf_sha256")
        _validate_hash(case["page_sha256"], errors, f"{case_path}.page_sha256")
        if not isinstance(case["page_number"], int) or case["page_number"] < 1:
            errors.append(f"proposed_reference_page_invalid:{case_path}.page_number")
        if case["expected_kind"] not in EXPECTED_KINDS:
            errors.append(f"proposed_reference_kind_invalid:{case_path}.expected_kind")
        regions = case["regions"]
        if not isinstance(regions, list):
            errors.append(f"proposed_reference_regions_invalid:{case_path}.regions")
            continue
        if case["expected_kind"] == "negative" and regions:
            errors.append(
                f"proposed_reference_negative_has_regions:{case_path}.regions"
            )
        if case["expected_kind"] == "table" and not regions:
            errors.append(f"proposed_reference_table_regions_empty:{case_path}.regions")
        region_ids: set[str] = set()
        for region_index, region in enumerate(regions):
            region_path = f"{case_path}.regions[{region_index}]"
            _validate_region(
                region, errors, region_path, require_complete_sources=False
            )
            if isinstance(region, dict) and isinstance(region.get("region_id"), str):
                if region["region_id"] in region_ids:
                    errors.append(
                        f"proposed_reference_region_duplicate:{region_path}.region_id"
                    )
                region_ids.add(region["region_id"])


def _validate_region(
    value: Any,
    errors: list[str],
    path: str,
    *,
    require_complete_sources: bool,
) -> None:
    if not _closed_object(
        value,
        {
            "region_id",
            "bbox_normalized",
            "crop_sha256",
            "evidence_medium",
            "one_complete_table",
            "cuts",
            "includes_neighboring_prose",
            "includes_other_table",
            "facts",
        },
        errors,
        path,
    ):
        return
    _validate_identifier(value["region_id"], errors, f"{path}.region_id")
    _validate_bbox(value["bbox_normalized"], errors, f"{path}.bbox_normalized")
    _validate_hash(value["crop_sha256"], errors, f"{path}.crop_sha256")
    if value["evidence_medium"] not in EVIDENCE_MEDIA:
        errors.append(f"review_region_evidence_medium_invalid:{path}.evidence_medium")
    for key in (
        "one_complete_table",
        "includes_neighboring_prose",
        "includes_other_table",
    ):
        if not isinstance(value[key], bool):
            errors.append(f"review_region_boolean_invalid:{path}.{key}")
    cuts = value["cuts"]
    if _closed_object(
        cuts, {"header", "total", "row", "column"}, errors, f"{path}.cuts"
    ):
        for key in ("header", "total", "row", "column"):
            if not isinstance(cuts[key], bool):
                errors.append(f"review_region_cut_invalid:{path}.cuts.{key}")
    facts = value["facts"]
    if not isinstance(facts, list):
        errors.append(f"review_region_facts_invalid:{path}.facts")
        return
    seen: set[str] = set()
    for index, fact in enumerate(facts):
        fact_path = f"{path}.facts[{index}]"
        _validate_fact(
            fact,
            errors,
            fact_path,
            require_complete_sources=require_complete_sources,
            expected_artifact_sha256=value["crop_sha256"],
        )
        if isinstance(fact, dict) and isinstance(fact.get("fact_id"), str):
            if fact["fact_id"] in seen:
                errors.append(f"review_fact_duplicate:{fact_path}.fact_id")
            seen.add(fact["fact_id"])


def _validate_fact(
    value: Any,
    errors: list[str],
    path: str,
    *,
    require_complete_sources: bool,
    expected_artifact_sha256: str,
) -> None:
    keys = {
        "fact_id",
        "fact_type",
        "row_label",
        "normalized_row_identity",
        "header_path",
        "visible_value",
        "numeric_value",
        "sign",
        "period",
        "currency",
        "unit",
        "scale",
        "entity",
        "qualifiers",
        "source_regions",
        "uncertainty",
        "alternative_interpretation",
    }
    if not _closed_object(value, keys, errors, path):
        return
    _validate_identifier(value["fact_id"], errors, f"{path}.fact_id")
    for key in ("fact_type", "row_label", "visible_value"):
        if not _nonempty_string(value[key]):
            errors.append(f"review_fact_required_field_invalid:{path}.{key}")
    for key in (
        "normalized_row_identity",
        "numeric_value",
        "period",
        "currency",
        "unit",
        "scale",
        "entity",
        "alternative_interpretation",
    ):
        if value[key] is not None and not _nonempty_string(value[key]):
            errors.append(f"review_fact_optional_field_invalid:{path}.{key}")
    if value["sign"] not in SIGN_VALUES:
        errors.append(f"review_fact_sign_invalid:{path}.sign")
    for key in ("header_path", "qualifiers", "uncertainty"):
        if not isinstance(value[key], list) or any(
            not _nonempty_string(item) for item in value[key]
        ):
            errors.append(f"review_fact_string_list_invalid:{path}.{key}")
    _validate_source_regions(
        value["source_regions"],
        errors,
        f"{path}.source_regions",
        require_complete=require_complete_sources,
        expected_artifact_sha256=expected_artifact_sha256,
        fact=value,
    )


def _validate_source_regions(
    value: Any,
    errors: list[str],
    path: str,
    *,
    require_complete: bool,
    expected_artifact_sha256: str,
    fact: dict[str, Any],
) -> None:
    if not _closed_object(
        value, {"row_label", "header", "value", "context"}, errors, path
    ):
        return
    row = value["row_label"]
    headers = value["header"]
    fact_value = value["value"]
    context = value["context"]
    if row is not None:
        _validate_source_locator(row, errors, f"{path}.row_label")
    if fact_value is not None:
        _validate_source_locator(fact_value, errors, f"{path}.value")
    for key, items in (("header", headers), ("context", context)):
        if not isinstance(items, list):
            errors.append(f"review_source_region_list_invalid:{path}.{key}")
            continue
        for index, item in enumerate(items):
            _validate_source_locator(item, errors, f"{path}.{key}[{index}]")
    if not require_complete:
        return
    if row is None:
        errors.append(f"review_fact_row_source_missing:{path}.row_label")
    if (
        not isinstance(headers, list)
        or not headers
        or len(headers) != len(fact["header_path"])
    ):
        errors.append(f"review_fact_header_source_missing:{path}.header")
    if fact_value is None:
        errors.append(f"review_fact_value_source_missing:{path}.value")
    locators = (
        ([row] if row is not None else [])
        + (headers if isinstance(headers, list) else [])
        + ([fact_value] if fact_value is not None else [])
    )
    for locator in locators:
        if (
            isinstance(locator, dict)
            and locator.get("artifact_sha256") != expected_artifact_sha256
        ):
            errors.append(f"review_fact_source_lineage_mismatch:{path}")
    if isinstance(row, dict) and row.get("visible_text") != fact["row_label"]:
        errors.append(f"review_fact_row_source_text_mismatch:{path}.row_label")
    if (
        isinstance(fact_value, dict)
        and fact_value.get("visible_text") != fact["visible_value"]
    ):
        errors.append(f"review_fact_value_source_text_mismatch:{path}.value")
    if isinstance(headers, list) and len(headers) == len(fact["header_path"]):
        for index, (locator, expected_text) in enumerate(
            zip(headers, fact["header_path"])
        ):
            if (
                isinstance(locator, dict)
                and locator.get("visible_text") != expected_text
            ):
                errors.append(
                    f"review_fact_header_source_text_mismatch:{path}.header[{index}]"
                )


def _validate_source_locator(value: Any, errors: list[str], path: str) -> None:
    if not _closed_object(
        value,
        {"artifact_sha256", "bbox_normalized", "visible_text"},
        errors,
        path,
    ):
        return
    _validate_hash(value["artifact_sha256"], errors, f"{path}.artifact_sha256")
    _validate_bbox(value["bbox_normalized"], errors, f"{path}.bbox_normalized")
    if not _nonempty_string(value["visible_text"]):
        errors.append(f"review_source_visible_text_invalid:{path}.visible_text")


def _validate_review_index(value: Any, errors: list[str], path: str) -> None:
    if not _closed_object(
        value,
        {
            "schema_version",
            "benchmark_id",
            "manifest_sha256",
            "proposed_reference_sha256",
            "cards",
            "index_sha256",
        },
        errors,
        path,
    ):
        return
    if value["schema_version"] != REVIEW_INDEX_SCHEMA:
        errors.append(f"review_index_schema_invalid:{path}.schema_version")
    _validate_identifier(value["benchmark_id"], errors, f"{path}.benchmark_id")
    _validate_hash(value["manifest_sha256"], errors, f"{path}.manifest_sha256")
    _validate_hash(
        value["proposed_reference_sha256"],
        errors,
        f"{path}.proposed_reference_sha256",
    )
    _validate_hash(value["index_sha256"], errors, f"{path}.index_sha256")
    unsigned = dict(value)
    unsigned.pop("index_sha256", None)
    if (
        isinstance(value["index_sha256"], str)
        and sha256_json(unsigned) != value["index_sha256"]
    ):
        errors.append(f"review_index_checksum_mismatch:{path}.index_sha256")
    cards = value["cards"]
    if not isinstance(cards, list):
        errors.append(f"review_index_cards_invalid:{path}.cards")
        return
    seen: set[str] = set()
    for index, card in enumerate(cards):
        card_path = f"{path}.cards[{index}]"
        _validate_review_card(card, errors, card_path)
        if isinstance(card, dict) and isinstance(card.get("card_id"), str):
            if card["card_id"] in seen:
                errors.append(f"review_index_card_duplicate:{card_path}.card_id")
            seen.add(card["card_id"])


def _validate_review_card(value: Any, errors: list[str], path: str) -> None:
    if not _closed_object(
        value,
        {
            "card_id",
            "card_kind",
            "case_id",
            "document_id",
            "pdf_sha256",
            "page_number",
            "expected_kind",
            "page_artifact",
            "checklist_fields",
            "region",
            "crop_artifact",
        },
        errors,
        path,
    ):
        return
    for key in ("card_id", "case_id", "document_id"):
        _validate_identifier(value[key], errors, f"{path}.{key}")
    if value["card_kind"] not in CARD_KINDS:
        errors.append(f"review_card_kind_invalid:{path}.card_kind")
    if value["expected_kind"] not in EXPECTED_KINDS:
        errors.append(f"review_card_expected_kind_invalid:{path}.expected_kind")
    _validate_hash(value["pdf_sha256"], errors, f"{path}.pdf_sha256")
    if not isinstance(value["page_number"], int) or value["page_number"] < 1:
        errors.append(f"review_card_page_invalid:{path}.page_number")
    _validate_artifact_meta(value["page_artifact"], errors, f"{path}.page_artifact")
    expected_checklist = list(CHECKLIST_FIELDS)
    if value["card_kind"] == "table_region":
        expected_checklist.append(EVIDENCE_MEDIUM_CHECKLIST_FIELD)
    if value["checklist_fields"] != expected_checklist:
        errors.append(f"review_card_checklist_invalid:{path}.checklist_fields")
    if value["card_kind"] == "negative_case":
        if value["region"] is not None or value["crop_artifact"] is not None:
            errors.append(f"review_negative_card_payload_invalid:{path}")
    else:
        _validate_region(
            value["region"], errors, f"{path}.region", require_complete_sources=False
        )
        _validate_artifact_meta(value["crop_artifact"], errors, f"{path}.crop_artifact")
        if (
            isinstance(value["region"], dict)
            and isinstance(value["crop_artifact"], dict)
            and value["region"].get("crop_sha256")
            != value["crop_artifact"].get("sha256")
        ):
            errors.append(f"review_card_crop_lineage_mismatch:{path}")


def _validate_artifact_meta(value: Any, errors: list[str], path: str) -> None:
    if not _closed_object(value, {"filename", "sha256", "mime_type"}, errors, path):
        return
    if not _nonempty_string(value["filename"]):
        errors.append(f"review_artifact_filename_invalid:{path}.filename")
    _validate_hash(value["sha256"], errors, f"{path}.sha256")
    if value["mime_type"] not in {"image/png", "image/jpeg"}:
        errors.append(f"review_artifact_mime_invalid:{path}.mime_type")


def _validate_review_decisions(
    value: Any,
    review_index: dict[str, Any],
    errors: list[str],
    path: str,
) -> None:
    if not _closed_object(
        value,
        {
            "schema_version",
            "review_index_sha256",
            "proposed_reference_sha256",
            "reviewer",
            "entries",
            "ledger",
        },
        errors,
        path,
    ):
        return
    if value["schema_version"] != REVIEW_DECISIONS_SCHEMA:
        errors.append(f"review_decisions_schema_invalid:{path}.schema_version")
    if value["review_index_sha256"] != review_index["index_sha256"]:
        errors.append(f"review_decisions_index_lineage_mismatch:{path}")
    if value["proposed_reference_sha256"] != review_index["proposed_reference_sha256"]:
        errors.append(f"review_decisions_proposal_lineage_mismatch:{path}")
    _validate_human_reviewer(value["reviewer"], errors, f"{path}.reviewer")
    entry_errors = _validate_entries_for_index(value["entries"], review_index)
    errors.extend(entry_errors)
    ledger = value["ledger"]
    if not isinstance(ledger, list):
        errors.append(f"review_decision_ledger_invalid:{path}.ledger")
        return
    if value["entries"] and not ledger:
        errors.append(f"review_decision_ledger_empty:{path}.ledger")
        return
    previous: str | None = None
    last_by_card: dict[str, dict[str, Any]] = {}
    for index, event in enumerate(ledger):
        event_path = f"{path}.ledger[{index}]"
        keys = {
            "sequence",
            "event_id",
            "recorded_at",
            "reviewer_kind",
            "reviewer_identity",
            "card_id",
            "entry_sha256",
            "previous_event_sha256",
            "event_sha256",
        }
        if not _closed_object(event, keys, errors, event_path):
            continue
        if event["sequence"] != index + 1:
            errors.append(f"review_ledger_sequence_invalid:{event_path}.sequence")
        _validate_identifier(event["event_id"], errors, f"{event_path}.event_id")
        _validate_timestamp(event["recorded_at"], errors, f"{event_path}.recorded_at")
        if event["reviewer_kind"] != "human":
            errors.append(f"review_ledger_reviewer_kind_invalid:{event_path}")
        _validate_human_identity(
            event["reviewer_identity"], errors, f"{event_path}.reviewer_identity"
        )
        _validate_identifier(event["card_id"], errors, f"{event_path}.card_id")
        _validate_hash(event["entry_sha256"], errors, f"{event_path}.entry_sha256")
        if event["previous_event_sha256"] != previous:
            errors.append(f"review_ledger_chain_invalid:{event_path}")
        _validate_hash(event["event_sha256"], errors, f"{event_path}.event_sha256")
        unsigned = dict(event)
        unsigned.pop("event_sha256", None)
        if (
            isinstance(event["event_sha256"], str)
            and sha256_json(unsigned) != event["event_sha256"]
        ):
            errors.append(f"review_ledger_checksum_mismatch:{event_path}")
        previous = event.get("event_sha256")
        last_by_card[event.get("card_id")] = event
    if isinstance(value["entries"], list):
        for entry in value["entries"]:
            if not isinstance(entry, dict):
                continue
            last = last_by_card.get(entry.get("card_id"))
            if last is None or last.get("entry_sha256") != sha256_json(entry):
                errors.append(
                    f"review_ledger_entry_not_current:$.entries[{entry.get('card_id')}]"
                )


def _validate_entries_for_index(
    entries: Any, review_index: dict[str, Any]
) -> list[str]:
    errors: list[str] = []
    if not isinstance(entries, list):
        return ["review_entries_not_list:$.entries"]
    cards = {card["card_id"]: card for card in review_index["cards"]}
    seen: set[str] = set()
    for index, entry in enumerate(entries):
        path = f"$.entries[{index}]"
        if not _closed_object(
            entry,
            {
                "card_id",
                "region_decision",
                "region_note",
                "corrected_region",
                "checklist",
                "fact_decisions",
            },
            errors,
            path,
        ):
            continue
        card_id = entry["card_id"]
        if card_id not in cards:
            errors.append(f"review_entry_card_unknown:{path}.card_id")
            continue
        card = cards[card_id]
        if card_id in seen:
            errors.append(f"review_entry_card_duplicate:{path}.card_id")
        seen.add(card_id)
        if entry["region_decision"] not in REGION_DECISIONS:
            errors.append(f"review_region_decision_pending:{path}.region_decision")
        if not _nonempty_string(entry["region_note"]):
            errors.append(f"review_region_note_missing:{path}.region_note")
        if entry["region_decision"] == "correct":
            if entry["corrected_region"] is None:
                errors.append(
                    f"review_corrected_region_missing:{path}.corrected_region"
                )
            else:
                _validate_region(
                    entry["corrected_region"],
                    errors,
                    f"{path}.corrected_region",
                    require_complete_sources=False,
                )
                crop_artifact = card.get("crop_artifact")
                if not isinstance(crop_artifact, dict):
                    errors.append(
                        f"review_corrected_region_requires_regenerated_pack:{path}"
                    )
                elif isinstance(entry["corrected_region"], dict) and entry[
                    "corrected_region"
                ].get("crop_sha256") != crop_artifact.get("sha256"):
                    errors.append(
                        f"review_corrected_region_lineage_mismatch:{path}.corrected_region"
                    )
        elif entry["corrected_region"] is not None:
            errors.append(f"review_unexpected_corrected_region:{path}.corrected_region")
        checklist = entry["checklist"]
        checklist_fields = card["checklist_fields"]
        if not _closed_object(
            checklist, set(checklist_fields), errors, f"{path}.checklist"
        ):
            checklist = {}
        for key in checklist_fields:
            if checklist.get(key) not in CHECKLIST_VALUES:
                errors.append(f"review_checklist_pending:{path}.checklist.{key}")
        effective = _effective_region(card, entry)
        expected_facts = effective["facts"] if effective is not None else []
        _validate_fact_decisions(
            entry["fact_decisions"], expected_facts, errors, f"{path}.fact_decisions"
        )
    if seen != set(cards):
        errors.append("review_entries_incomplete:$.entries")
    return errors


def _validate_fact_decisions(
    value: Any,
    expected_facts: list[dict[str, Any]],
    errors: list[str],
    path: str,
) -> None:
    if not isinstance(value, list):
        errors.append(f"review_fact_decisions_invalid:{path}")
        return
    expected = {fact["fact_id"]: fact for fact in expected_facts}
    seen: set[str] = set()
    for index, item in enumerate(value):
        item_path = f"{path}[{index}]"
        if not _closed_object(
            item,
            {"fact_id", "decision", "note", "corrected_fact"},
            errors,
            item_path,
        ):
            continue
        fact_id = item["fact_id"]
        if fact_id not in expected:
            errors.append(f"review_fact_decision_unknown:{item_path}.fact_id")
            continue
        if fact_id in seen:
            errors.append(f"review_fact_decision_duplicate:{item_path}.fact_id")
        seen.add(fact_id)
        if item["decision"] not in FACT_DECISIONS:
            errors.append(f"review_fact_decision_pending:{item_path}.decision")
        if not _nonempty_string(item["note"]):
            errors.append(f"review_fact_note_missing:{item_path}.note")
        if item["decision"] == "correct":
            if item["corrected_fact"] is None:
                errors.append(
                    f"review_corrected_fact_missing:{item_path}.corrected_fact"
                )
            else:
                _validate_fact(
                    item["corrected_fact"],
                    errors,
                    f"{item_path}.corrected_fact",
                    require_complete_sources=False,
                    expected_artifact_sha256="",
                )
                if (
                    isinstance(item["corrected_fact"], dict)
                    and item["corrected_fact"].get("fact_id") != fact_id
                ):
                    errors.append(f"review_corrected_fact_id_mismatch:{item_path}")
        elif item["corrected_fact"] is not None:
            errors.append(
                f"review_unexpected_corrected_fact:{item_path}.corrected_fact"
            )
    if seen != set(expected):
        errors.append(f"review_fact_decisions_incomplete:{path}")


def _require_complete_fact(
    fact: dict[str, Any], *, expected_artifact_sha256: str, path: str
) -> None:
    errors: list[str] = []
    _validate_fact(
        fact,
        errors,
        path,
        require_complete_sources=True,
        expected_artifact_sha256=expected_artifact_sha256,
    )
    _require_valid(errors, "review_accepted_fact_incomplete")


def _require_review_intent(value: Any, review_index: dict[str, Any]) -> None:
    if not isinstance(value, dict) or set(value) != {
        "schema_version",
        "review_index_sha256",
        "proposed_reference_sha256",
        "reviewer",
        "entries",
    }:
        raise ReviewContractError("review_intent_shape_invalid")
    if value["schema_version"] != REVIEW_INTENT_SCHEMA:
        raise ReviewContractError("review_intent_schema_invalid")
    if value["review_index_sha256"] != review_index["index_sha256"]:
        raise ReviewContractError("review_intent_index_lineage_mismatch")
    if value["proposed_reference_sha256"] != review_index["proposed_reference_sha256"]:
        raise ReviewContractError("review_intent_proposal_lineage_mismatch")
    _require_human_reviewer(value["reviewer"])
    _require_valid(
        _validate_entries_for_index(value["entries"], review_index),
        "review_intent_entries_invalid",
    )


def _effective_region(
    card: dict[str, Any], entry: dict[str, Any]
) -> dict[str, Any] | None:
    if entry.get("region_decision") == "correct":
        corrected = entry.get("corrected_region")
        return corrected if isinstance(corrected, dict) else None
    region = card.get("region")
    return region if isinstance(region, dict) else None


def _validate_human_reviewer(value: Any, errors: list[str], path: str) -> None:
    if not _closed_object(value, {"kind", "identity", "reviewed_at"}, errors, path):
        return
    if value["kind"] != "human":
        errors.append(f"reviewer_kind_not_human:{path}.kind")
    _validate_human_identity(value["identity"], errors, f"{path}.identity")
    _validate_timestamp(value["reviewed_at"], errors, f"{path}.reviewed_at")


def _require_human_reviewer(value: Any) -> None:
    errors: list[str] = []
    _validate_human_reviewer(value, errors, "$.reviewer")
    if errors:
        raise ReviewContractError("reviewer_not_human", errors[0])


def _validate_human_identity(value: Any, errors: list[str], path: str) -> None:
    if not _nonempty_string(value):
        errors.append(f"reviewer_identity_missing:{path}")
        return
    normalized = value.strip().casefold()
    tokens = set(re.split(r"[^a-z0-9]+", normalized))
    if tokens & _FORBIDDEN_REVIEWER_TOKENS or any(
        fragment in normalized for fragment in _FORBIDDEN_REVIEWER_FRAGMENTS
    ):
        errors.append(f"reviewer_identity_ai_forbidden:{path}")


def _validate_timestamp(value: Any, errors: list[str], path: str) -> None:
    if not _nonempty_string(value):
        errors.append(f"reviewer_timestamp_missing:{path}")
        return
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        errors.append(f"reviewer_timestamp_invalid:{path}")
        return
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        errors.append(f"reviewer_timestamp_timezone_missing:{path}")


def _closed_object(
    value: Any,
    keys: set[str],
    errors: list[str],
    path: str,
) -> bool:
    if not isinstance(value, dict):
        errors.append(f"review_object_invalid:{path}")
        return False
    actual = set(value)
    if actual != keys:
        errors.append(
            f"review_object_keys_invalid:{path}:"
            f"missing={sorted(keys - actual)}:extra={sorted(actual - keys)}"
        )
        return False
    return True


def _validate_identifier(value: Any, errors: list[str], path: str) -> None:
    if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
        errors.append(f"review_identifier_invalid:{path}")


def _validate_hash(value: Any, errors: list[str], path: str) -> None:
    if not isinstance(value, str) or _HEX_64.fullmatch(value) is None:
        errors.append(f"review_sha256_invalid:{path}")


def _validate_bbox(value: Any, errors: list[str], path: str) -> None:
    if (
        not isinstance(value, list)
        or len(value) != 4
        or any(
            isinstance(item, bool) or not isinstance(item, (int, float))
            for item in value
        )
    ):
        errors.append(f"review_bbox_invalid:{path}")
        return
    x0, y0, x1, y1 = (float(item) for item in value)
    if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
        errors.append(f"review_bbox_invalid:{path}")


def _read_image_artifact(
    path_value: str | Path, expected_sha256: str
) -> tuple[dict[str, str], str]:
    path = Path(path_value)
    if not path.is_file():
        raise ReviewContractError("review_image_artifact_missing", str(path))
    payload = path.read_bytes()
    actual = hashlib.sha256(payload).hexdigest()
    if actual != expected_sha256:
        raise ReviewContractError("review_image_artifact_checksum_mismatch", str(path))
    suffix = path.suffix.casefold()
    mime = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}.get(
        suffix
    )
    if mime is None:
        raise ReviewContractError("review_image_artifact_type_unsupported", str(path))
    meta = {"filename": path.name, "sha256": actual, "mime_type": mime}
    uri = f"data:{mime};base64,{base64.b64encode(payload).decode('ascii')}"
    return meta, uri


def _render_review_html(
    review_index: dict[str, Any],
    image_data: dict[str, dict[str, str | None]],
) -> str:
    cards = review_index["cards"]
    rendered_cards = "".join(
        _render_card(card, image_data[card["card_id"]]) for card in cards
    )
    empty_hidden = " hidden" if cards else ""
    success_hidden = "" if cards else " hidden"
    embedded = json.dumps(review_index, ensure_ascii=False).replace("</", "<\\/")
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>PDF financial fact human review</title>
  <style>
    :root {{ color-scheme: light dark; font-family: system-ui, sans-serif; }}
    body {{ margin: 0; line-height: 1.5; }}
    main {{ max-width: 90rem; margin: auto; padding: 1rem; }}
    article {{ border: 1px solid currentColor; border-radius: .5rem; padding: 1rem; margin: 1rem 0; }}
    img {{ display: block; max-width: 100%; max-height: 48rem; border: 1px solid #777; }}
    .page-wrap {{ position: relative; display: inline-block; max-width: 100%; }}
    .page-wrap img {{ width: auto; height: auto; }}
    .bbox-overlay {{ position: absolute; border: .25rem solid #e11900; box-sizing: border-box;
      background: rgb(225 25 0 / 8%); pointer-events: none; }}
    fieldset {{ margin: 1rem 0; }}
    label {{ display: block; margin: .35rem 0; }}
    textarea, input[type="text"], select {{ width: min(100%, 56rem); box-sizing: border-box; }}
    button {{ padding: .7rem 1rem; font-weight: 700; }}
    button[disabled] {{ opacity: .55; cursor: wait; }}
    :focus-visible {{ outline: .25rem solid #ffbf47; outline-offset: .2rem; }}
    .state {{ border-left: .35rem solid #276ef1; padding: .75rem; margin: .75rem 0; }}
    .error {{ border-color: #b10e1e; }}
    .images {{ display: grid; gap: 1rem; grid-template-columns: repeat(auto-fit, minmax(20rem, 1fr)); }}
    .fact {{ border-left: .25rem solid #777; padding-left: 1rem; }}
    .primary {{ background: #276ef1; color: white; border: .15rem solid #174ea6; }}
    .muted {{ color: #666; }}
    pre {{ white-space: pre-wrap; overflow-wrap: anywhere; }}
  </style>
</head>
<body>
<main id="review-app" aria-busy="false">
  <h1>PDF financial fact human review</h1>
  <p>Review source pages and immutable crops. This form records human intent only.</p>
  <section id="state-loading" class="state" role="status" aria-live="polite" hidden>
    Preparing the review export…
  </section>
  <section id="state-error" class="state error" role="alert" tabindex="-1" hidden></section>
  <section id="state-empty" class="state" role="status"{empty_hidden}>
    No review cards are available. Check the proposed-reference input and regenerate the pack.
  </section>
  <section id="state-success" class="state" role="status"{success_hidden}>
    Review pack loaded successfully. Complete every decision, note, and checklist item.
  </section>
  <form id="review-form" novalidate>
    <fieldset>
      <legend>Human reviewer</legend>
      <input type="hidden" id="reviewer-kind" value="human">
      <label for="reviewer-identity">Name or accountable identity</label>
      <input id="reviewer-identity" name="reviewer-identity" type="text" required autocomplete="name">
      <label for="reviewed-at">Review timestamp with timezone</label>
      <input id="reviewed-at" name="reviewed-at" type="text" required placeholder="2026-07-16T12:00:00+03:00">
    </fieldset>
    <section id="review-cards" aria-label="Review cards">{rendered_cards}</section>
    <button id="export-intent" class="primary" type="button" aria-describedby="export-feedback"{"" if cards else " disabled"}>
      Export review intent JSON
    </button>
    <p id="export-feedback" role="status" aria-live="polite" tabindex="-1">No export attempted.</p>
  </form>
</main>
<script id="review-index-data" type="application/json">{embedded}</script>
<script>
(() => {{
  'use strict';
  const intentSchema = {json.dumps(REVIEW_INTENT_SCHEMA)};
  const index = JSON.parse(document.getElementById('review-index-data').textContent);
  const app = document.getElementById('review-app');
  const button = document.getElementById('export-intent');
  const feedback = document.getElementById('export-feedback');
  const loading = document.getElementById('state-loading');
  const success = document.getElementById('state-success');
  const error = document.getElementById('state-error');

  function selected(name) {{
    const input = document.querySelector(`input[name="${{CSS.escape(name)}}"]:checked`);
    return input ? input.value : 'pending';
  }}

  function parseOptionalJson(id, label) {{
    const raw = document.getElementById(id).value.trim();
    if (!raw) return null;
    try {{ return JSON.parse(raw); }}
    catch (cause) {{ throw new Error(`${{label}} is not valid JSON.`); }}
  }}

  function collectCard(card) {{
    const safe = card.card_id.replace(/[^A-Za-z0-9_-]/g, '_');
    const facts = card.region ? card.region.facts : [];
    const regionDecision = selected(`${{safe}}-region-decision`);
    const checklist = {{}};
    for (const field of card.checklist_fields) {{
      checklist[field] = document.getElementById(`${{safe}}-check-${{field}}`).value;
    }}
    return {{
      card_id: card.card_id,
      region_decision: regionDecision,
      region_note: document.getElementById(`${{safe}}-region-note`).value,
      corrected_region: regionDecision === 'correct' ? parseOptionalJson(
        `${{safe}}-corrected-region`, `Corrected region for ${{card.card_id}}`
      ) : null,
      checklist,
      fact_decisions: facts.map((fact) => {{
        const factSafe = `${{safe}}-${{fact.fact_id.replace(/[^A-Za-z0-9_-]/g, '_')}}`;
        const factDecision = selected(`${{factSafe}}-decision`);
        return {{
          fact_id: fact.fact_id,
          decision: factDecision,
          note: document.getElementById(`${{factSafe}}-note`).value,
          corrected_fact: factDecision === 'correct' ? parseOptionalJson(
            `${{factSafe}}-corrected`, `Corrected fact ${{fact.fact_id}}`
          ) : null
        }};
      }})
    }};
  }}

  button.addEventListener('click', () => {{
    button.disabled = true;
    button.setAttribute('aria-busy', 'true');
    app.setAttribute('aria-busy', 'true');
    loading.hidden = false;
    error.hidden = true;
    try {{
      const intent = {{
        schema_version: intentSchema,
        review_index_sha256: index.index_sha256,
        proposed_reference_sha256: index.proposed_reference_sha256,
        reviewer: {{
          kind: document.getElementById('reviewer-kind').value,
          identity: document.getElementById('reviewer-identity').value,
          reviewed_at: document.getElementById('reviewed-at').value
        }},
        entries: index.cards.map(collectCard)
      }};
      const payload = JSON.stringify(intent, null, 2);
      const url = URL.createObjectURL(new Blob([payload], {{type: 'application/json'}}));
      const link = document.createElement('a');
      link.href = url;
      link.download = 'review.intent.json';
      link.click();
      URL.revokeObjectURL(url);
      feedback.textContent = 'Review intent exported. Python validation and human finalization are still required.';
      success.hidden = false;
      feedback.focus();
    }} catch (cause) {{
      const message = cause instanceof Error ? cause.message : 'Review export failed.';
      error.textContent = message;
      error.hidden = false;
      feedback.textContent = 'Export failed. Correct the highlighted JSON or missing form intent.';
      error.focus();
    }} finally {{
      loading.hidden = true;
      app.setAttribute('aria-busy', 'false');
      button.removeAttribute('aria-busy');
      button.disabled = false;
    }}
  }});
}})();
</script>
</body>
</html>
"""


def _render_card(card: dict[str, Any], images: dict[str, str | None]) -> str:
    card_id = card["card_id"]
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", card_id)
    title = (
        f"Negative case {card['case_id']}"
        if card["card_kind"] == "negative_case"
        else f"Table {card['case_id']} / {card['region']['region_id']}"
    )
    crop = ""
    if images["crop"] is not None:
        crop = (
            "<figure><figcaption>Immutable table crop</figcaption>"
            f'<img src="{images["crop"]}" alt="Immutable crop for '
            f'{html.escape(title)}"></figure>'
        )
    facts = card["region"]["facts"] if card["region"] is not None else []
    facts_html = "".join(_render_fact_form(safe, fact) for fact in facts)
    checklist = "".join(
        f'<label for="{safe}-check-{field}">{html.escape(field.replace("_", " ").title())}</label>'
        f'<select id="{safe}-check-{field}" required>'
        '<option value="pending">Choose…</option>'
        '<option value="pass">Pass</option><option value="issue">Issue</option>'
        '<option value="uncertain">Uncertain</option></select>'
        for field in card["checklist_fields"]
    )
    evidence_medium = (
        card["region"]["evidence_medium"]
        if card["region"] is not None
        else "not applicable"
    )
    corrected_region = (
        html.escape(json.dumps(card["region"], ensure_ascii=False, indent=2))
        if card["region"] is not None
        else ""
    )
    overlay = ""
    if card["region"] is not None:
        x0, y0, x1, y1 = card["region"]["bbox_normalized"]
        overlay = (
            '<span class="bbox-overlay" aria-label="Proposed table bounding box" '
            f'style="left:{x0 * 100:.6f}%;top:{y0 * 100:.6f}%;'
            f'width:{(x1 - x0) * 100:.6f}%;height:{(y1 - y0) * 100:.6f}%"></span>'
        )
    return f"""
<article data-card-id="{html.escape(card_id)}" tabindex="-1" aria-labelledby="{safe}-title">
  <h2 id="{safe}-title">{html.escape(title)}</h2>
  <p class="muted">Page {card["page_number"]} · PDF {html.escape(card["pdf_sha256"])}</p>
  <p><strong>Proposed evidence medium:</strong> {html.escape(evidence_medium)}</p>
  <div class="images">
    <figure><figcaption>Source page with candidate context</figcaption>
      <span class="page-wrap"><img src="{images["page"]}" alt="Source page for {html.escape(title)}">
        {overlay}
      </span>
    </figure>
    {crop}
  </div>
  <fieldset>
    <legend>Region or negative-case decision</legend>
    {_radio(safe, "region-decision", "approve", "Approve")}
    {_radio(safe, "region-decision", "correct", "Correct")}
    {_radio(safe, "region-decision", "ambiguous", "Ambiguous")}
    {_radio(safe, "region-decision", "reject", "Reject")}
    <label for="{safe}-region-note">Decision note</label>
    <textarea id="{safe}-region-note" rows="3" required></textarea>
    <label for="{safe}-corrected-region">Corrected region JSON (required only for Correct)</label>
    <textarea id="{safe}-corrected-region" rows="6" spellcheck="false">{corrected_region}</textarea>
  </fieldset>
  <fieldset>
    <legend>Review checklist</legend>
    {checklist}
  </fieldset>
  <section aria-label="Financial fact decisions">{facts_html}</section>
</article>
"""


def _render_fact_form(card_safe: str, fact: dict[str, Any]) -> str:
    fact_safe = f"{card_safe}-{re.sub(r'[^A-Za-z0-9_-]', '_', fact['fact_id'])}"
    header = " > ".join(fact["header_path"]) or "Unknown header"
    source_regions = html.escape(
        json.dumps(fact["source_regions"], ensure_ascii=False, indent=2)
    )
    corrected_fact = html.escape(json.dumps(fact, ensure_ascii=False, indent=2))
    return f"""
<fieldset class="fact">
  <legend>Fact {html.escape(fact["fact_id"])}</legend>
  <p><strong>Row:</strong> {html.escape(fact["row_label"])}<br>
     <strong>Header:</strong> {html.escape(header)}<br>
     <strong>Visible value:</strong> {html.escape(fact["visible_value"])}<br>
     <strong>Period:</strong> {html.escape(str(fact["period"] or "unknown"))}<br>
     <strong>Currency / unit / scale:</strong>
       {html.escape(str(fact["currency"] or "unknown"))} /
       {html.escape(str(fact["unit"] or "unknown"))} /
       {html.escape(str(fact["scale"] or "unknown"))}</p>
  <details><summary>Proposed source addresses</summary><pre>{source_regions}</pre></details>
  {_radio(fact_safe, "decision", "confirm", "Confirm")}
  {_radio(fact_safe, "decision", "correct", "Correct")}
  {_radio(fact_safe, "decision", "ambiguous", "Ambiguous")}
  {_radio(fact_safe, "decision", "reject", "Reject")}
  <label for="{fact_safe}-note">Fact decision note</label>
  <textarea id="{fact_safe}-note" rows="3" required></textarea>
  <label for="{fact_safe}-corrected">Corrected fact JSON (required only for Correct)</label>
  <textarea id="{fact_safe}-corrected" rows="8" spellcheck="false">{corrected_fact}</textarea>
</fieldset>
"""


def _radio(prefix: str, field: str, value: str, label: str) -> str:
    control_id = f"{prefix}-{field}-{value}"
    name = f"{prefix}-{field}"
    return (
        f'<label for="{control_id}"><input id="{control_id}" name="{name}" '
        f'type="radio" value="{value}" required> {label}</label>'
    )


def _write_new(path: Path, payload: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    descriptor = os.open(path, flags, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
    except Exception:
        path.unlink(missing_ok=True)
        raise


def _crop_key(case_id: str, region_id: str) -> str:
    return f"{case_id}:{region_id}"


def _require_valid(errors: list[str], code: str) -> None:
    if errors:
        raise ReviewContractError(code, errors[0])


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())
