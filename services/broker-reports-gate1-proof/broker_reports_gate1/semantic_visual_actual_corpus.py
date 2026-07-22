from __future__ import annotations

import copy
import hashlib
import re
from typing import Any

from .pdf_dual_vlm_canonical_table_contracts import canonical_json_bytes
from .semantic_visual_table_hypothesis import (
    SEMANTIC_ACTUAL_CORPUS_REFERENCE_SCHEMA,
    validate_source_reference,
)


DELEGATED_REFERENCE_SCHEMA = (
    "broker_reports_actual_corpus_vlm_delegated_reference_v1_private"
)
DELEGATED_REFERENCE_SEAL_SCHEMA = (
    "broker_reports_actual_corpus_vlm_delegated_reference_seal_v1"
)
SUPPLEMENT_SCHEMA = (
    "broker_reports_semantic_actual_corpus_reference_supplement_v1_private"
)
ACCEPTED_DISPOSITION = "accepted_numeric_profile_candidate"
UNSUPPORTED_DISPOSITION = "unsupported_layout"
EXPECTED_CORPUS_TABLES = 9
EXPECTED_ACCEPTED_TABLES = 8

_CURRENCY_PREFIX = re.compile(r"^([$€£¥₽])\s+(.+)$")
_AMOUNT = re.compile(r"^\(?[+-]?\d[\d\s,.]*(?:%|\))?$")


class SemanticActualCorpusError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def build_semantic_source_reference(
    delegated_reference: Any,
    delegated_reference_seal: Any,
    supplement: Any,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Project sealed source-only literals into semantic logical rows.

    The supplement may add source-visible section/header labels and row grouping,
    but it cannot add or alter value literals from the sealed delegated reference.
    """

    _validate_upstream(delegated_reference, delegated_reference_seal)
    _validate_supplement(supplement, delegated_reference_seal)

    delegated_tables = {
        table["runtime_candidate_ref"]: table
        for table in delegated_reference["literal_reference"]["tables"]
    }
    reviews = {
        review["runtime_candidate_ref"]: review
        for review in delegated_reference["table_reviews"]
    }
    supplement_refs = [table["candidate_ref"] for table in supplement["tables"]]
    if (
        set(supplement_refs) != set(delegated_tables)
        or set(supplement_refs) != set(reviews)
    ):
        raise SemanticActualCorpusError("semantic_actual_corpus_identity_set_mismatch")

    projected_tables: list[dict[str, Any]] = []
    unsupported: list[dict[str, Any]] = []
    for table_plan in supplement["tables"]:
        candidate_ref = table_plan["candidate_ref"]
        delegated_table = delegated_tables[candidate_ref]
        review = reviews[candidate_ref]
        crop_sha256 = table_plan["crop_sha256"]
        if (
            delegated_table.get("evaluated_crop_sha256") != crop_sha256
            or review.get("evaluated_crop_sha256") != crop_sha256
        ):
            raise SemanticActualCorpusError(
                "semantic_actual_corpus_crop_identity_mismatch"
            )
        disposition = table_plan["disposition"]
        if disposition == UNSUPPORTED_DISPOSITION:
            if review.get("disposition") != UNSUPPORTED_DISPOSITION:
                raise SemanticActualCorpusError(
                    "semantic_actual_corpus_unsupported_disposition_mismatch"
                )
            unsupported.append(
                {
                    "candidate_ref": candidate_ref,
                    "crop_sha256": crop_sha256,
                    "layout_families": copy.deepcopy(
                        table_plan["layout_families"]
                    ),
                    "reason": table_plan["unsupported_reason"],
                }
            )
            continue
        if review.get("disposition") != "assisted_review_candidate":
            raise SemanticActualCorpusError(
                "semantic_actual_corpus_accepted_disposition_mismatch"
            )
        projected_tables.append(
            {
                "table_id": candidate_ref,
                "crop_sha256": crop_sha256,
                "rows": _project_rows(
                    table_plan["row_plan"], delegated_table["entries"]
                ),
            }
        )

    if (
        len(projected_tables) != EXPECTED_ACCEPTED_TABLES
        or len(unsupported) != EXPECTED_CORPUS_TABLES - EXPECTED_ACCEPTED_TABLES
    ):
        raise SemanticActualCorpusError(
            "semantic_actual_corpus_disposition_count_invalid"
        )
    reference = {
        "schema_version": SEMANTIC_ACTUAL_CORPUS_REFERENCE_SCHEMA,
        "source_only": True,
        "provider_outputs_used": False,
        "provider_agreement_used": False,
        "customer_acceptance_claimed": False,
        "tables": projected_tables,
    }
    validate_source_reference(
        reference,
        expected_table_count=EXPECTED_ACCEPTED_TABLES,
        expected_schema_version=SEMANTIC_ACTUAL_CORPUS_REFERENCE_SCHEMA,
    )
    return reference, unsupported


def _validate_upstream(reference: Any, seal: Any) -> None:
    if not isinstance(reference, dict) or not isinstance(seal, dict):
        raise SemanticActualCorpusError("semantic_actual_corpus_upstream_invalid")
    lineage = reference.get("lineage")
    literal_reference = reference.get("literal_reference")
    tables = literal_reference.get("tables") if isinstance(literal_reference, dict) else None
    reviews = reference.get("table_reviews")
    canonical = canonical_json_bytes(reference)
    if (
        reference.get("schema_version") != DELEGATED_REFERENCE_SCHEMA
        or reference.get("human_reviewed") is not False
        or reference.get("delegated_agent_reviewed") is not True
        or reference.get("customer_accepted") is not False
        or not isinstance(lineage, dict)
        or lineage.get("provider_outputs_used") is not False
        or lineage.get("provider_consensus_used") is not False
        or not isinstance(tables, list)
        or len(tables) != EXPECTED_CORPUS_TABLES
        or not isinstance(reviews, list)
        or len(reviews) != EXPECTED_CORPUS_TABLES
        or seal.get("schema_version") != DELEGATED_REFERENCE_SEAL_SCHEMA
        or seal.get("reference_sha256")
        != hashlib.sha256(canonical).hexdigest()
        or seal.get("reference_size_bytes") != len(canonical)
        or seal.get("human_reviewed") is not False
        or seal.get("delegated_agent_reviewed") is not True
        or seal.get("customer_accepted") is not False
    ):
        raise SemanticActualCorpusError("semantic_actual_corpus_upstream_invalid")


def _validate_supplement(supplement: Any, seal: dict[str, Any]) -> None:
    tables = supplement.get("tables") if isinstance(supplement, dict) else None
    if (
        not isinstance(supplement, dict)
        or supplement.get("schema_version") != SUPPLEMENT_SCHEMA
        or supplement.get("frozen_before_provider_execution") is not True
        or supplement.get("source_only") is not True
        or supplement.get("provider_outputs_used") is not False
        or supplement.get("provider_agreement_used") is not False
        or supplement.get("customer_acceptance_claimed") is not False
        or supplement.get("upstream_delegated_reference_canonical_sha256")
        != seal.get("reference_sha256")
        or not isinstance(tables, list)
        or len(tables) != EXPECTED_CORPUS_TABLES
    ):
        raise SemanticActualCorpusError("semantic_actual_corpus_supplement_invalid")
    seen: set[str] = set()
    for table in tables:
        if not isinstance(table, dict):
            raise SemanticActualCorpusError("semantic_actual_corpus_table_plan_invalid")
        candidate_ref = table.get("candidate_ref")
        disposition = table.get("disposition")
        layouts = table.get("layout_families")
        if (
            not _nonempty(candidate_ref)
            or candidate_ref in seen
            or not _sha256(table.get("crop_sha256"))
            or disposition not in {ACCEPTED_DISPOSITION, UNSUPPORTED_DISPOSITION}
            or not isinstance(layouts, list)
            or not layouts
            or any(not _nonempty(item) for item in layouts)
        ):
            raise SemanticActualCorpusError("semantic_actual_corpus_table_plan_invalid")
        seen.add(candidate_ref)
        if disposition == UNSUPPORTED_DISPOSITION:
            if set(table) != {
                "candidate_ref",
                "crop_sha256",
                "disposition",
                "layout_families",
                "unsupported_reason",
            } or not _nonempty(table.get("unsupported_reason")):
                raise SemanticActualCorpusError(
                    "semantic_actual_corpus_unsupported_plan_invalid"
                )
        elif set(table) != {
            "candidate_ref",
            "crop_sha256",
            "disposition",
            "layout_families",
            "row_plan",
        } or not isinstance(table.get("row_plan"), list):
            raise SemanticActualCorpusError(
                "semantic_actual_corpus_accepted_plan_invalid"
            )


def _project_rows(row_plan: list[Any], entries: Any) -> list[dict[str, Any]]:
    if not isinstance(entries, list) or not entries:
        raise SemanticActualCorpusError("semantic_actual_corpus_entries_invalid")
    used: list[int] = []
    rows: list[dict[str, Any]] = []
    for planned_row in row_plan:
        if not isinstance(planned_row, dict):
            raise SemanticActualCorpusError("semantic_actual_corpus_row_plan_invalid")
        if set(planned_row) == {"literal_labels"}:
            labels = planned_row["literal_labels"]
            if not isinstance(labels, list) or not labels or any(
                not _nonempty(label) for label in labels
            ):
                raise SemanticActualCorpusError(
                    "semantic_actual_corpus_literal_labels_invalid"
                )
            rows.append(_row(labels=labels, amounts=[], markers=[]))
            continue
        if not set(planned_row).issubset({"entry_indices", "label_override"}) or (
            "entry_indices" not in planned_row
        ):
            raise SemanticActualCorpusError("semantic_actual_corpus_row_plan_invalid")
        indices = planned_row["entry_indices"]
        if not isinstance(indices, list) or not indices or any(
            not isinstance(index, int)
            or isinstance(index, bool)
            or index < 0
            or index >= len(entries)
            for index in indices
        ):
            raise SemanticActualCorpusError("semantic_actual_corpus_entry_index_invalid")
        selected = [entries[index] for index in indices]
        used.extend(indices)
        override = planned_row.get("label_override")
        source_labels = [entry.get("row_label_text") for entry in selected]
        if override is not None:
            if not _nonempty(override):
                raise SemanticActualCorpusError(
                    "semantic_actual_corpus_label_override_invalid"
                )
            labels = [override]
        elif len(set(source_labels)) == 1 and _nonempty(source_labels[0]):
            labels = [source_labels[0]]
        else:
            raise SemanticActualCorpusError(
                "semantic_actual_corpus_grouped_label_mismatch"
            )
        amounts: list[str] = []
        markers: list[str] = []
        values: list[str] = []
        for entry in selected:
            if (
                not isinstance(entry, dict)
                or entry.get("review_status") != "confirmed"
                or entry.get("cell_state") not in {"value", "empty"}
                or (
                    entry.get("cell_state") == "empty"
                    and entry.get("visible_value_text") != "-"
                )
            ):
                raise SemanticActualCorpusError(
                    "semantic_actual_corpus_entry_authority_invalid"
                )
            value_cells, value_amounts, value_markers = _value_roles(
                entry.get("visible_value_text")
            )
            values.extend(value_cells)
            amounts.extend(value_amounts)
            markers.extend(value_markers)
        rows.append(
            {
                "cells": labels + values,
                "labels": labels,
                "amounts": amounts,
                "markers": markers,
            }
        )
    if sorted(used) != list(range(len(entries))) or len(used) != len(set(used)):
        raise SemanticActualCorpusError("semantic_actual_corpus_entry_coverage_invalid")
    return rows


def _value_roles(value: Any) -> tuple[list[str], list[str], list[str]]:
    if not _nonempty(value):
        raise SemanticActualCorpusError("semantic_actual_corpus_visible_value_invalid")
    if value == "-":
        return [value], [], [value]
    currency = _CURRENCY_PREFIX.fullmatch(value)
    if currency:
        marker, amount = currency.groups()
        if not _AMOUNT.fullmatch(amount):
            raise SemanticActualCorpusError(
                "semantic_actual_corpus_visible_value_invalid"
            )
        return [marker, amount], [amount], [marker]
    if not _AMOUNT.fullmatch(value):
        raise SemanticActualCorpusError("semantic_actual_corpus_visible_value_invalid")
    return [value], [value], []


def _row(
    *, labels: list[str], amounts: list[str], markers: list[str]
) -> dict[str, Any]:
    return {
        "cells": labels + markers + amounts,
        "labels": copy.deepcopy(labels),
        "amounts": copy.deepcopy(amounts),
        "markers": copy.deepcopy(markers),
    }


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


def _sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )
