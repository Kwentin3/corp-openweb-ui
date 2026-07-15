from __future__ import annotations

import copy
import re
import unicodedata
from dataclasses import dataclass
from typing import Any

from .contracts import stable_digest
from .pdf_hybrid_contracts import canonical_json_bytes, sha256_json
from .pdf_semantic_header_contracts import (
    MAX_SEMANTIC_CONTEXT_BYTES,
    MAX_SEMANTIC_PHYSICAL_ALTERNATIVES,
    MAX_SEMANTIC_REPRESENTATIVE_ROWS,
    PDF_SEMANTIC_HEADER_POLICY_VERSION,
    PDF_SEMANTIC_HEADER_PROJECTION_SCHEMA,
    PHYSICAL_TOPOLOGY_STATUSES,
    SEMANTIC_CURRENCY_CODE_ALLOWLIST,
    SEMANTIC_UNIT_CODE_ALLOWLIST,
    physical_column_id,
    physical_span_id,
    semantic_header_configuration,
    validate_physical_alternative_shape,
    validate_semantic_header_projection,
)


_FACTORY_TOKEN = object()
_CURRENCY_SYMBOLS = ("$", "€", "£", "¥", "₽")
_ROLE_ALIASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "total_or_subtotal",
        ("total", "subtotal", "итого", "подытог", "всего"),
    ),
    (
        "description",
        (
            "description",
            "details",
            "narrative",
            "operation",
            "transaction",
            "instrument",
            "описание",
            "операция",
            "наименование",
            "инструмент",
        ),
    ),
    (
        "entity",
        (
            "entity",
            "issuer",
            "broker",
            "company",
            "counterparty",
            "эмитент",
            "брокер",
            "компания",
            "контрагент",
        ),
    ),
    ("date", ("date", "дата")),
    ("period", ("period", "период", "quarter", "month", "квартал", "месяц")),
    (
        "amount",
        (
            "amount",
            "value",
            "proceeds",
            "income",
            "cost",
            "сумма",
            "стоимость",
            "доход",
            "выручка",
        ),
    ),
    ("quantity", ("quantity", "qty", "count", "количество", "кол во")),
    (
        "percentage",
        ("percentage", "percent", "rate", "процент", "ставка"),
    ),
    ("currency", ("currency", "валюта", "curr")),
    ("unit", ("unit", "units", "единица", "единицы", "ед")),
)


class PdfSemanticHeaderProjectionError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class PdfSemanticHeaderProjectionConfig:
    policy_version: str = PDF_SEMANTIC_HEADER_POLICY_VERSION
    max_context_bytes: int = 48 * 1024
    max_physical_alternatives: int = 8
    max_representative_rows: int = 3


class PdfSemanticHeaderProjectionFactory:
    def __init__(self, config: PdfSemanticHeaderProjectionConfig | None = None) -> None:
        self.config = config or PdfSemanticHeaderProjectionConfig()

    def create(self) -> "PdfSemanticHeaderProjectionRuntime":
        if self.config.policy_version != PDF_SEMANTIC_HEADER_POLICY_VERSION:
            raise PdfSemanticHeaderProjectionError(
                "pdf_semantic_header_projection_policy_invalid"
            )
        positive = (
            self.config.max_context_bytes,
            self.config.max_physical_alternatives,
            self.config.max_representative_rows,
        )
        if any(
            not isinstance(item, int) or isinstance(item, bool) or item < 1
            for item in positive
        ) or (
            self.config.max_context_bytes > MAX_SEMANTIC_CONTEXT_BYTES
            or self.config.max_physical_alternatives
            > MAX_SEMANTIC_PHYSICAL_ALTERNATIVES
            or self.config.max_representative_rows
            > MAX_SEMANTIC_REPRESENTATIVE_ROWS
        ):
            raise PdfSemanticHeaderProjectionError(
                "pdf_semantic_header_projection_budget_invalid"
            )
        return PdfSemanticHeaderProjectionRuntime(
            config=self.config,
            _factory_token=_FACTORY_TOKEN,
        )


class PdfSemanticHeaderProjectionRuntime:
    def __init__(
        self,
        config: PdfSemanticHeaderProjectionConfig,
        *,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise PdfSemanticHeaderProjectionError(
                "pdf_semantic_header_projection_factory_required"
            )
        self.config = config

    def project(
        self,
        *,
        structural_result_checksum: str,
        physical_topology_status: str,
        physical_alternatives: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if not isinstance(structural_result_checksum, str) or not re.fullmatch(
            r"[0-9a-f]{64}", structural_result_checksum
        ):
            raise PdfSemanticHeaderProjectionError(
                "pdf_semantic_header_structural_result_checksum_invalid"
            )
        if physical_topology_status not in PHYSICAL_TOPOLOGY_STATUSES:
            raise PdfSemanticHeaderProjectionError(
                "pdf_semantic_header_physical_topology_status_invalid"
            )
        if not isinstance(physical_alternatives, list) or not physical_alternatives:
            raise PdfSemanticHeaderProjectionError(
                "pdf_semantic_header_physical_alternatives_invalid"
            )
        if len(physical_alternatives) > self.config.max_physical_alternatives:
            raise PdfSemanticHeaderProjectionError(
                "pdf_semantic_header_alternative_budget_exceeded"
            )
        if (
            physical_topology_status == "accepted_supplied_consensus"
            and len(physical_alternatives) != 1
        ):
            raise PdfSemanticHeaderProjectionError(
                "pdf_semantic_header_accepted_alternative_count_invalid"
            )
        if (
            physical_topology_status == "ambiguous_multiple_consensus"
            and len(physical_alternatives) < 2
        ):
            raise PdfSemanticHeaderProjectionError(
                "pdf_semantic_header_ambiguous_alternatives_missing"
            )

        source_snapshot = copy.deepcopy(physical_alternatives)
        for alternative in source_snapshot:
            shape_errors = validate_physical_alternative_shape(alternative)
            if shape_errors:
                raise PdfSemanticHeaderProjectionError(shape_errors[0])
        grid_checksums = [str(item["grid_checksum"]) for item in source_snapshot]
        if len(grid_checksums) != len(set(grid_checksums)):
            raise PdfSemanticHeaderProjectionError(
                "pdf_semantic_header_grid_checksum_duplicate"
            )

        input_identity = {
            "physical_topology_status": physical_topology_status,
            "physical_alternatives": source_snapshot,
        }
        input_hash = sha256_json(input_identity)
        projected: list[dict[str, Any]] = []
        for alternative in source_snapshot:
            projected.append(self._project_alternative(alternative))

        top_reasons = sorted(
            {
                reason
                for item in projected
                for reason in item["reason_codes"]
            }
        )
        any_unknown = any(
            item["unmapped_physical_column_ids"]
            or any(field["role"] == "unknown" for field in item["semantic_fields"])
            for item in projected
        )
        if any_unknown:
            top_reasons = sorted(
                set(top_reasons)
                | {"pdf_semantic_header_unknown_or_unmapped_columns"}
            )
        projection_status = (
            "projected"
            if not any_unknown
            and all(item["projection_status"] == "projected" for item in projected)
            else "incomplete"
        )
        equivalence_status = self._equivalence_status(
            physical_topology_status=physical_topology_status,
            projected=projected,
            any_unknown=any_unknown,
            projection_status=projection_status,
        )
        configuration = semantic_header_configuration(
            policy_version=self.config.policy_version,
            max_context_bytes=self.config.max_context_bytes,
            max_physical_alternatives=self.config.max_physical_alternatives,
            max_representative_rows=self.config.max_representative_rows,
        )
        configuration_checksum = sha256_json(configuration)
        projection_id = "pdfsemanticprojection_" + stable_digest(
            [
                PDF_SEMANTIC_HEADER_PROJECTION_SCHEMA,
                self.config.policy_version,
                structural_result_checksum,
                configuration_checksum,
                input_hash,
            ],
            length=24,
        )
        result: dict[str, Any] = {
            "schema_version": PDF_SEMANTIC_HEADER_PROJECTION_SCHEMA,
            "policy_version": self.config.policy_version,
            "projection_id": projection_id,
            "physical_topology_status": physical_topology_status,
            "physical_ambiguity_preserved": physical_topology_status
            == "ambiguous_multiple_consensus",
            "physical_alternatives": projected,
            "projection_status": projection_status,
            "semantic_equivalence_status": equivalence_status,
            "semantic_equivalence_scope": "logical_field_roles_only",
            "semantic_equivalence_does_not_select_topology": True,
            "reason_codes": top_reasons,
            "input_hash": input_hash,
            "structural_result_checksum": structural_result_checksum,
            "configuration": configuration,
            "configuration_checksum": configuration_checksum,
            "source_value_change_allowed": False,
            "geometry_change_allowed": False,
            "physical_cell_change_allowed": False,
            "reference_answer_used": False,
            "authority_state": "non_authoritative",
            "production_gate2_selection_changed": False,
        }
        result["projection_checksum"] = sha256_json(result)
        validation_errors = validate_semantic_header_projection(
            result,
            physical_alternatives=source_snapshot,
        )
        if validation_errors:
            raise PdfSemanticHeaderProjectionError(validation_errors[0])
        if physical_alternatives != source_snapshot:
            raise PdfSemanticHeaderProjectionError(
                "pdf_semantic_header_input_mutated"
            )
        return result

    def _project_alternative(
        self,
        alternative: dict[str, Any],
    ) -> dict[str, Any]:
        grid_checksum = str(alternative["grid_checksum"])
        physical_columns = [
            {
                "physical_column_id": physical_column_id(grid_checksum, ordinal),
                "column_ordinal": ordinal,
            }
            for ordinal in range(1, int(alternative["column_count"]) + 1)
        ]
        context_view = self._context_view(alternative)
        context_bytes = len(canonical_json_bytes(context_view))
        overflow_reason = None
        if context_bytes > self.config.max_context_bytes:
            overflow_reason = "pdf_semantic_header_context_budget_exceeded"
        if overflow_reason is not None:
            all_column_ids = [item["physical_column_id"] for item in physical_columns]
            return {
                "grid_checksum": grid_checksum,
                "projection_status": "context_budget_exceeded",
                "reason_codes": [overflow_reason],
                "context_bytes": context_bytes,
                "physical_columns": physical_columns,
                "semantic_fields": [],
                "qualifiers": [],
                "mapped_physical_column_ids": [],
                "unmapped_physical_column_ids": all_column_ids,
                "logical_schema_signature": [],
            }

        header_index = self._header_index(alternative)
        column_roles = {
            ordinal: _classify_role(
                " ".join(header_index[ordinal]["exact_values"])
            )
            for ordinal in range(1, int(alternative["column_count"]) + 1)
        }
        amount_ordinals = [
            ordinal for ordinal, role in column_roles.items() if role == "amount"
        ]
        quantity_ordinals = [
            ordinal for ordinal, role in column_roles.items() if role == "quantity"
        ]
        currency_ordinals = [
            ordinal for ordinal, role in column_roles.items() if role == "currency"
        ]
        unit_ordinals = [
            ordinal for ordinal, role in column_roles.items() if role == "unit"
        ]
        absorbed_currency = {
            ordinal
            for ordinal in currency_ordinals
            if len(currency_ordinals) == 1 and len(amount_ordinals) == 1
        }
        absorbed_unit = {
            ordinal
            for ordinal in unit_ordinals
            if len(unit_ordinals) == 1 and len(quantity_ordinals) == 1
        }
        qualifier_binding_ambiguous = (
            bool(currency_ordinals)
            and bool(amount_ordinals)
            and not (
                len(currency_ordinals) == 1 and len(amount_ordinals) == 1
            )
        ) or (
            bool(unit_ordinals)
            and bool(quantity_ordinals)
            and not (len(unit_ordinals) == 1 and len(quantity_ordinals) == 1)
        )
        header_rows = set(alternative["header_rows"])
        representative_rows_incomplete = (
            bool(amount_ordinals or quantity_ordinals)
            and sum(
                int(row["row_ordinal"]) not in header_rows
                for row in alternative["rows"]
            )
            > self.config.max_representative_rows
        )
        absorbed = absorbed_currency | absorbed_unit

        semantic_fields: list[dict[str, Any]] = []
        core_by_ordinal: dict[int, dict[str, Any]] = {}
        for ordinal, role in column_roles.items():
            if ordinal in absorbed:
                continue
            evidence = header_index[ordinal]
            field_id = self._field_id(grid_checksum, "column", role, [ordinal])
            field = {
                "field_id": field_id,
                "role": role,
                "logical_type": "monetary_amount" if role == "amount" else role,
                "physical_column_ids": [physical_column_id(grid_checksum, ordinal)],
                "header_cell_refs": evidence["cell_refs"],
                "header_span_refs": evidence["span_refs"],
                "header_atom_ids": evidence["atom_ids"],
                "qualifier_refs": [],
            }
            semantic_fields.append(field)
            core_by_ordinal[ordinal] = field

        structural_fields = self._structural_header_fields(
            alternative=alternative,
            header_index=header_index,
        )
        semantic_fields.extend(structural_fields)
        qualifiers = self._currency_qualifiers(
            alternative=alternative,
            header_index=header_index,
            column_roles=column_roles,
            core_by_ordinal=core_by_ordinal,
            absorbed_currency=absorbed_currency,
        )
        qualifiers.extend(
            self._unit_qualifiers(
                alternative=alternative,
                header_index=header_index,
                column_roles=column_roles,
                core_by_ordinal=core_by_ordinal,
                absorbed_unit=absorbed_unit,
            )
        )
        qualifiers_by_measure: dict[str, list[str]] = {}
        for qualifier in qualifiers:
            measure = qualifier["measure_field_id"]
            if isinstance(measure, str):
                qualifiers_by_measure.setdefault(measure, []).append(
                    qualifier["qualifier_id"]
                )
        for field in semantic_fields:
            field["qualifier_refs"] = sorted(
                qualifiers_by_measure.get(field["field_id"], [])
            )

        mapped_ordinals = {
            ordinal for ordinal, role in column_roles.items() if role != "unknown"
        }
        mapped_ids = [
            physical_column_id(grid_checksum, ordinal)
            for ordinal in sorted(mapped_ordinals)
        ]
        unmapped_ids = [
            physical_column_id(grid_checksum, ordinal)
            for ordinal in sorted(set(column_roles) - mapped_ordinals)
        ]
        signature: list[str] = []
        for ordinal in sorted(column_roles):
            if ordinal in absorbed:
                continue
            role = column_roles[ordinal]
            logical_type = "monetary_amount" if role == "amount" else role
            signature.append(logical_type)
        reasons = []
        if unmapped_ids:
            reasons.append("pdf_semantic_header_unknown_or_unmapped_columns")
        if qualifier_binding_ambiguous:
            reasons.append(
                "pdf_semantic_header_qualifier_measure_binding_ambiguous"
            )
        if representative_rows_incomplete:
            reasons.append(
                "pdf_semantic_header_representative_rows_incomplete"
            )
        alternative_status = (
            "qualifier_binding_incomplete"
            if qualifier_binding_ambiguous
            else "representative_sample_incomplete"
            if representative_rows_incomplete
            else "projected"
        )
        return {
            "grid_checksum": grid_checksum,
            "projection_status": alternative_status,
            "reason_codes": sorted(reasons),
            "context_bytes": context_bytes,
            "physical_columns": physical_columns,
            "semantic_fields": semantic_fields,
            "qualifiers": qualifiers,
            "mapped_physical_column_ids": mapped_ids,
            "unmapped_physical_column_ids": unmapped_ids,
            "logical_schema_signature": signature,
        }

    def _context_view(self, alternative: dict[str, Any]) -> dict[str, Any]:
        header_rows = set(alternative["header_rows"])
        data_rows = [
            int(row["row_ordinal"])
            for row in alternative["rows"]
            if int(row["row_ordinal"]) not in header_rows
        ][: self.config.max_representative_rows]
        selected_rows = header_rows | set(data_rows)
        cells = [
            {
                "cell_ref": cell["cell_ref"],
                "row_ordinal": cell["row_ordinal"],
                "column_ordinal": cell["column_ordinal"],
                "candidate_ids": cell["candidate_ids"],
                "exact_values": cell["exact_values"],
            }
            for cell in alternative["cells"]
            if int(cell["row_ordinal"]) in selected_rows
        ]
        return {
            "grid_checksum": alternative["grid_checksum"],
            "row_count": alternative["row_count"],
            "column_count": alternative["column_count"],
            "header_rows": alternative["header_rows"],
            "header_hierarchy": alternative["header_hierarchy"],
            "spans": alternative["spans"],
            "rows": [
                row
                for row in alternative["rows"]
                if int(row["row_ordinal"]) in selected_rows
            ],
            "cells": cells,
        }

    def _header_index(
        self,
        alternative: dict[str, Any],
    ) -> dict[int, dict[str, list[str]]]:
        grid_checksum = str(alternative["grid_checksum"])
        header_rows = set(alternative["header_rows"])
        cells_by_position = {
            (int(cell["row_ordinal"]), int(cell["column_ordinal"])): cell
            for cell in alternative["cells"]
        }
        spans_by_anchor: dict[tuple[int, int], list[dict[str, Any]]] = {}
        for span in alternative["spans"]:
            if int(span["start_row"]) in header_rows:
                spans_by_anchor.setdefault(
                    (int(span["start_row"]), int(span["start_column"])), []
                ).append(span)
        index: dict[int, dict[str, list[str]]] = {}
        for ordinal in range(1, int(alternative["column_count"]) + 1):
            cell_refs: list[str] = []
            atom_ids: list[str] = []
            exact_values: list[str] = []
            span_refs: list[str] = []
            for row_ordinal in alternative["header_rows"]:
                covering_spans = [
                    span
                    for spans in spans_by_anchor.values()
                    for span in spans
                    if int(span["start_row"]) <= row_ordinal <= int(span["end_row"])
                    and int(span["start_column"]) <= ordinal <= int(span["end_column"])
                ]
                if covering_spans:
                    for span in covering_spans:
                        anchor = cells_by_position[
                            (int(span["start_row"]), int(span["start_column"]))
                        ]
                        _append_unique(cell_refs, str(anchor["cell_ref"]))
                        for atom_id in anchor["candidate_ids"]:
                            _append_unique(atom_ids, str(atom_id))
                        for exact_value in anchor["exact_values"]:
                            _append_unique(exact_values, str(exact_value))
                        _append_unique(
                            span_refs,
                            physical_span_id(grid_checksum, span),
                        )
                else:
                    cell = cells_by_position[(row_ordinal, ordinal)]
                    _append_unique(cell_refs, str(cell["cell_ref"]))
                    for atom_id in cell["candidate_ids"]:
                        _append_unique(atom_ids, str(atom_id))
                    for exact_value in cell["exact_values"]:
                        _append_unique(exact_values, str(exact_value))
            index[ordinal] = {
                "cell_refs": cell_refs,
                "span_refs": span_refs,
                "atom_ids": atom_ids,
                "exact_values": exact_values,
            }
        return index

    def _structural_header_fields(
        self,
        *,
        alternative: dict[str, Any],
        header_index: dict[int, dict[str, list[str]]],
    ) -> list[dict[str, Any]]:
        grid_checksum = str(alternative["grid_checksum"])
        header_rows = set(alternative["header_rows"])
        cells_by_position = {
            (int(cell["row_ordinal"]), int(cell["column_ordinal"])): cell
            for cell in alternative["cells"]
        }
        fields: list[dict[str, Any]] = []
        for span in alternative["spans"]:
            if int(span["start_row"]) not in header_rows:
                continue
            ordinals = list(
                range(int(span["start_column"]), int(span["end_column"]) + 1)
            )
            anchor = cells_by_position[
                (int(span["start_row"]), int(span["start_column"]))
            ]
            fields.append(
                {
                    "field_id": self._field_id(
                        grid_checksum,
                        "group",
                        "group_header",
                        ordinals,
                    ),
                    "role": "group_header",
                    "logical_type": "group_header",
                    "physical_column_ids": [
                        physical_column_id(grid_checksum, ordinal)
                        for ordinal in ordinals
                    ],
                    "header_cell_refs": [str(anchor["cell_ref"])],
                    "header_span_refs": [physical_span_id(grid_checksum, span)],
                    "header_atom_ids": [str(item) for item in anchor["candidate_ids"]],
                    "qualifier_refs": [],
                }
            )

        if not header_rows:
            return fields
        deepest_header_row = max(header_rows)
        for ordinal in range(1, int(alternative["column_count"]) + 1):
            evidence_cells, evidence_spans = self._effective_header_evidence(
                alternative=alternative,
                row_ordinal=deepest_header_row,
                column_ordinal=ordinal,
                cells_by_position=cells_by_position,
            )
            fields.append(
                {
                    "field_id": self._field_id(
                        grid_checksum,
                        "leaf",
                        "leaf_header",
                        [ordinal],
                    ),
                    "role": "leaf_header",
                    "logical_type": "leaf_header",
                    "physical_column_ids": [physical_column_id(grid_checksum, ordinal)],
                    "header_cell_refs": [
                        str(cell["cell_ref"]) for cell in evidence_cells
                    ],
                    "header_span_refs": [
                        physical_span_id(grid_checksum, span)
                        for span in evidence_spans
                    ],
                    "header_atom_ids": _ordered_unique(
                        [
                            str(item)
                            for cell in evidence_cells
                            for item in cell["candidate_ids"]
                        ]
                    ),
                    "qualifier_refs": [],
                }
            )
        return fields

    def _effective_header_evidence(
        self,
        *,
        alternative: dict[str, Any],
        row_ordinal: int,
        column_ordinal: int,
        cells_by_position: dict[tuple[int, int], dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        covering_spans = [
            span
            for span in alternative["spans"]
            if int(span["start_row"]) <= row_ordinal <= int(span["end_row"])
            and int(span["start_column"])
            <= column_ordinal
            <= int(span["end_column"])
        ]
        if not covering_spans:
            return [cells_by_position[(row_ordinal, column_ordinal)]], []
        anchors: list[dict[str, Any]] = []
        for span in covering_spans:
            anchor = cells_by_position[
                (int(span["start_row"]), int(span["start_column"]))
            ]
            if anchor not in anchors:
                anchors.append(anchor)
        return anchors, covering_spans

    def _currency_qualifiers(
        self,
        *,
        alternative: dict[str, Any],
        header_index: dict[int, dict[str, list[str]]],
        column_roles: dict[int, str],
        core_by_ordinal: dict[int, dict[str, Any]],
        absorbed_currency: set[int],
    ) -> list[dict[str, Any]]:
        grid_checksum = str(alternative["grid_checksum"])
        amount_ordinals = [
            ordinal for ordinal, role in column_roles.items() if role == "amount"
        ]
        if not amount_ordinals:
            return []
        cells_by_position = {
            (int(cell["row_ordinal"]), int(cell["column_ordinal"])): cell
            for cell in alternative["cells"]
        }
        header_rows = set(alternative["header_rows"])
        qualifiers: list[dict[str, Any]] = []
        amount_has_evidence = {ordinal: False for ordinal in amount_ordinals}

        for span in alternative["spans"]:
            if (
                int(span["start_row"]) not in header_rows
                or int(span["start_column"]) != 1
                or int(span["end_column"]) != int(alternative["column_count"])
            ):
                continue
            anchor = cells_by_position[
                (int(span["start_row"]), int(span["start_column"]))
            ]
            evidence = _single_exact_value(anchor)
            if evidence is None or not _has_currency_evidence(evidence):
                continue
            for amount_ordinal in amount_ordinals:
                measure = core_by_ordinal[amount_ordinal]
                qualifiers.append(
                    self._qualifier(
                        grid_checksum=grid_checksum,
                        kind="currency",
                        scope="table",
                        measure_field_id=measure["field_id"],
                        column_ordinals=list(
                            range(1, int(alternative["column_count"]) + 1)
                        ),
                        evidence_cells=[anchor],
                        normalized_code=_currency_code_from_text(evidence),
                    )
                )
                amount_has_evidence[amount_ordinal] = True

        data_row_ordinals = [
            int(row["row_ordinal"])
            for row in alternative["rows"]
            if int(row["row_ordinal"]) not in header_rows
        ][: self.config.max_representative_rows]
        if absorbed_currency:
            measure_ordinal = amount_ordinals[0]
            measure = core_by_ordinal[measure_ordinal]
            for currency_ordinal in sorted(absorbed_currency):
                header_cells = self._cells_for_refs(
                    alternative,
                    header_index[currency_ordinal]["cell_refs"],
                )
                qualifiers.append(
                    self._qualifier(
                        grid_checksum=grid_checksum,
                        kind="currency",
                        scope="column",
                        measure_field_id=measure["field_id"],
                        column_ordinals=[currency_ordinal],
                        evidence_cells=header_cells,
                        normalized_code=_currency_code_from_cells(header_cells),
                    )
                )
                amount_has_evidence[measure_ordinal] = True
                for row_ordinal in data_row_ordinals:
                    cell = cells_by_position[(row_ordinal, currency_ordinal)]
                    evidence = _single_exact_value(cell)
                    if evidence is None or not _has_currency_evidence(evidence):
                        continue
                    qualifiers.append(
                        self._qualifier(
                            grid_checksum=grid_checksum,
                            kind="currency",
                            scope="row",
                            measure_field_id=measure["field_id"],
                            column_ordinals=[currency_ordinal, measure_ordinal],
                            evidence_cells=[cell],
                            normalized_code=_currency_code_from_text(evidence),
                        )
                    )

        for amount_ordinal in amount_ordinals:
            measure = core_by_ordinal[amount_ordinal]
            header_cells = self._cells_for_refs(
                alternative,
                header_index[amount_ordinal]["cell_refs"],
            )
            header_values = [
                value
                for cell in header_cells
                for value in cell["exact_values"]
                if isinstance(value, str)
            ]
            if any(_has_currency_evidence(value) for value in header_values):
                qualifiers.append(
                    self._qualifier(
                        grid_checksum=grid_checksum,
                        kind="currency",
                        scope="column",
                        measure_field_id=measure["field_id"],
                        column_ordinals=[amount_ordinal],
                        evidence_cells=header_cells,
                        normalized_code=_currency_code_from_values(header_values),
                    )
                )
                amount_has_evidence[amount_ordinal] = True
            for row_ordinal in data_row_ordinals:
                cell = cells_by_position[(row_ordinal, amount_ordinal)]
                evidence = _single_exact_value(cell)
                if evidence is None or not _has_currency_evidence(evidence):
                    continue
                qualifiers.append(
                    self._qualifier(
                        grid_checksum=grid_checksum,
                        kind="currency",
                        scope="cell",
                        measure_field_id=measure["field_id"],
                        column_ordinals=[amount_ordinal],
                        evidence_cells=[cell],
                        normalized_code=_currency_code_from_text(evidence),
                    )
                )
                amount_has_evidence[amount_ordinal] = True
            if not amount_has_evidence[amount_ordinal]:
                qualifiers.append(
                    self._qualifier(
                        grid_checksum=grid_checksum,
                        kind="currency",
                        scope="unknown",
                        measure_field_id=measure["field_id"],
                        column_ordinals=[amount_ordinal],
                        evidence_cells=header_cells,
                        normalized_code=None,
                    )
                )
        return _deduplicate_qualifiers(qualifiers)

    def _unit_qualifiers(
        self,
        *,
        alternative: dict[str, Any],
        header_index: dict[int, dict[str, list[str]]],
        column_roles: dict[int, str],
        core_by_ordinal: dict[int, dict[str, Any]],
        absorbed_unit: set[int],
    ) -> list[dict[str, Any]]:
        grid_checksum = str(alternative["grid_checksum"])
        quantity_ordinals = [
            ordinal for ordinal, role in column_roles.items() if role == "quantity"
        ]
        if not quantity_ordinals:
            return []
        cells_by_position = {
            (int(cell["row_ordinal"]), int(cell["column_ordinal"])): cell
            for cell in alternative["cells"]
        }
        header_rows = set(alternative["header_rows"])
        data_row_ordinals = [
            int(row["row_ordinal"])
            for row in alternative["rows"]
            if int(row["row_ordinal"]) not in header_rows
        ][: self.config.max_representative_rows]
        qualifiers: list[dict[str, Any]] = []
        quantity_has_evidence = {ordinal: False for ordinal in quantity_ordinals}

        for span in alternative["spans"]:
            if (
                int(span["start_row"]) not in header_rows
                or int(span["start_column"]) != 1
                or int(span["end_column"]) != int(alternative["column_count"])
            ):
                continue
            anchor = cells_by_position[
                (int(span["start_row"]), int(span["start_column"]))
            ]
            evidence = _single_exact_value(anchor)
            if evidence is None or not _has_unit_evidence(evidence):
                continue
            for quantity_ordinal in quantity_ordinals:
                measure = core_by_ordinal[quantity_ordinal]
                qualifiers.append(
                    self._qualifier(
                        grid_checksum=grid_checksum,
                        kind="unit",
                        scope="table",
                        measure_field_id=measure["field_id"],
                        column_ordinals=list(
                            range(1, int(alternative["column_count"]) + 1)
                        ),
                        evidence_cells=[anchor],
                        normalized_code=_unit_code_from_text(evidence),
                    )
                )
                quantity_has_evidence[quantity_ordinal] = True

        for quantity_ordinal in quantity_ordinals:
            measure = core_by_ordinal[quantity_ordinal]
            if absorbed_unit:
                for unit_ordinal in sorted(absorbed_unit):
                    header_cells = self._cells_for_refs(
                        alternative,
                        header_index[unit_ordinal]["cell_refs"],
                    )
                    qualifiers.append(
                        self._qualifier(
                            grid_checksum=grid_checksum,
                            kind="unit",
                            scope="column",
                            measure_field_id=measure["field_id"],
                            column_ordinals=[unit_ordinal],
                            evidence_cells=header_cells,
                            normalized_code=_unit_code_from_cells(header_cells),
                        )
                    )
                    quantity_has_evidence[quantity_ordinal] = True
                    for row_ordinal in data_row_ordinals:
                        cell = cells_by_position[(row_ordinal, unit_ordinal)]
                        evidence = _single_exact_value(cell)
                        if evidence is None or not _has_unit_evidence(evidence):
                            continue
                        qualifiers.append(
                            self._qualifier(
                                grid_checksum=grid_checksum,
                                kind="unit",
                                scope="row",
                                measure_field_id=measure["field_id"],
                                column_ordinals=[
                                    unit_ordinal,
                                    quantity_ordinal,
                                ],
                                evidence_cells=[cell],
                                normalized_code=_unit_code_from_text(evidence),
                            )
                        )
            header_cells = self._cells_for_refs(
                alternative,
                header_index[quantity_ordinal]["cell_refs"],
            )
            header_values = [
                value
                for cell in header_cells
                for value in cell["exact_values"]
                if isinstance(value, str)
            ]
            if any(_has_unit_evidence(value) for value in header_values):
                qualifiers.append(
                    self._qualifier(
                        grid_checksum=grid_checksum,
                        kind="unit",
                        scope="column",
                        measure_field_id=measure["field_id"],
                        column_ordinals=[quantity_ordinal],
                        evidence_cells=header_cells,
                        normalized_code=_unit_code_from_values(header_values),
                    )
                )
                quantity_has_evidence[quantity_ordinal] = True
            for row_ordinal in data_row_ordinals:
                cell = cells_by_position[(row_ordinal, quantity_ordinal)]
                evidence = _single_exact_value(cell)
                if evidence is None or not _has_unit_evidence(evidence):
                    continue
                qualifiers.append(
                    self._qualifier(
                        grid_checksum=grid_checksum,
                        kind="unit",
                        scope="cell",
                        measure_field_id=measure["field_id"],
                        column_ordinals=[quantity_ordinal],
                        evidence_cells=[cell],
                        normalized_code=_unit_code_from_text(evidence),
                    )
                )
                quantity_has_evidence[quantity_ordinal] = True
            if not quantity_has_evidence[quantity_ordinal]:
                qualifiers.append(
                    self._qualifier(
                        grid_checksum=grid_checksum,
                        kind="unit",
                        scope="unknown",
                        measure_field_id=measure["field_id"],
                        column_ordinals=[quantity_ordinal],
                        evidence_cells=header_cells,
                        normalized_code=None,
                    )
                )
        return _deduplicate_qualifiers(qualifiers)

    def _qualifier(
        self,
        *,
        grid_checksum: str,
        kind: str,
        scope: str,
        measure_field_id: str,
        column_ordinals: list[int],
        evidence_cells: list[dict[str, Any]],
        normalized_code: str | None,
    ) -> dict[str, Any]:
        column_ordinals = sorted(set(column_ordinals))
        cell_refs = _ordered_unique(
            [str(cell["cell_ref"]) for cell in evidence_cells]
        )
        atom_ids = _ordered_unique(
            [str(atom) for cell in evidence_cells for atom in cell["candidate_ids"]]
        )
        qualifier_id = "pdfsemanticqualifier_" + stable_digest(
            [
                grid_checksum,
                kind,
                scope,
                measure_field_id,
                ",".join(str(item) for item in column_ordinals),
                ",".join(cell_refs),
                normalized_code,
            ],
            length=24,
        )
        return {
            "qualifier_id": qualifier_id,
            "kind": kind,
            "scope": scope,
            "measure_field_id": measure_field_id,
            "physical_column_ids": [
                physical_column_id(grid_checksum, ordinal)
                for ordinal in column_ordinals
            ],
            "evidence_cell_refs": cell_refs,
            "evidence_atom_ids": atom_ids,
            "normalized_code": normalized_code,
        }

    def _field_id(
        self,
        grid_checksum: str,
        kind: str,
        role: str,
        column_ordinals: list[int],
    ) -> str:
        digest = stable_digest(
            [
                grid_checksum,
                kind,
                role,
                ",".join(str(item) for item in column_ordinals),
            ],
            length=24,
        )
        return f"pdfsemanticfield_{digest}"

    def _cells_for_refs(
        self,
        alternative: dict[str, Any],
        cell_refs: list[str],
    ) -> list[dict[str, Any]]:
        by_ref = {str(cell["cell_ref"]): cell for cell in alternative["cells"]}
        return [by_ref[cell_ref] for cell_ref in cell_refs]

    def _equivalence_status(
        self,
        *,
        physical_topology_status: str,
        projected: list[dict[str, Any]],
        any_unknown: bool,
        projection_status: str,
    ) -> str:
        if projection_status != "projected" or any_unknown:
            return "incomplete"
        if physical_topology_status != "ambiguous_multiple_consensus":
            return "not_applicable"
        signatures = {
            tuple(item["logical_schema_signature"])
            for item in projected
        }
        return "equivalent" if len(signatures) == 1 else "different"


def _classify_role(text: str) -> str:
    normalized = _normalize_label(text)
    if not normalized:
        return "unknown"
    padded = f" {normalized} "
    for role, aliases in _ROLE_ALIASES:
        for alias in aliases:
            normalized_alias = _normalize_label(alias)
            if f" {normalized_alias} " in padded:
                return role
    if _currency_code_from_text(text) is not None or any(
        symbol in text for symbol in _CURRENCY_SYMBOLS
    ):
        return "currency"
    if "%" in text:
        return "percentage"
    return "unknown"


def _normalize_label(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return " ".join(re.findall(r"[\w]+", normalized, flags=re.UNICODE))


def _has_currency_evidence(value: str) -> bool:
    stripped = value.strip()
    return _currency_code_from_text(stripped) is not None or any(
        symbol in stripped for symbol in _CURRENCY_SYMBOLS
    )


def _currency_codes_from_text(value: str) -> list[str]:
    choices = "|".join(sorted(SEMANTIC_CURRENCY_CODE_ALLOWLIST))
    pattern = r"(?<![A-Z0-9])(?:" + choices + r")(?![A-Z0-9])"
    return _ordered_unique(re.findall(pattern, value))


def _currency_code_from_text(value: str) -> str | None:
    codes = _currency_codes_from_text(value)
    return codes[0] if len(codes) == 1 else None


def _currency_code_from_values(values: list[str]) -> str | None:
    codes = _ordered_unique(
        [code for value in values for code in _currency_codes_from_text(value)]
    )
    return codes[0] if len(codes) == 1 else None


def _currency_code_from_cells(cells: list[dict[str, Any]]) -> str | None:
    return _currency_code_from_values(
        [
            str(value)
            for cell in cells
            for value in cell["exact_values"]
            if isinstance(value, str)
        ]
    )


def _has_unit_evidence(value: str) -> bool:
    return _unit_code_from_text(value) is not None


def _unit_codes_from_text(value: str) -> list[str]:
    choices = "|".join(sorted(SEMANTIC_UNIT_CODE_ALLOWLIST))
    pattern = r"(?<![\w])(?:" + choices + r")(?![\w])"
    return _ordered_unique(
        re.findall(pattern, value.casefold(), flags=re.UNICODE)
    )


def _unit_code_from_text(value: str) -> str | None:
    codes = _unit_codes_from_text(value)
    return codes[0] if len(codes) == 1 else None


def _unit_code_from_values(values: list[str]) -> str | None:
    codes = _ordered_unique(
        [code for value in values for code in _unit_codes_from_text(value)]
    )
    return codes[0] if len(codes) == 1 else None


def _unit_code_from_cells(cells: list[dict[str, Any]]) -> str | None:
    return _unit_code_from_values(
        [
            str(value)
            for cell in cells
            for value in cell["exact_values"]
            if isinstance(value, str)
        ]
    )


def _single_exact_value(cell: dict[str, Any]) -> str | None:
    values = cell["exact_values"]
    if len(values) != 1 or not isinstance(values[0], str):
        return None
    return values[0]


def _append_unique(target: list[str], value: str) -> None:
    if value not in target:
        target.append(value)


def _ordered_unique(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        _append_unique(result, value)
    return result


def _deduplicate_qualifiers(values: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for value in values:
        qualifier_id = str(value["qualifier_id"])
        if qualifier_id not in seen:
            seen.add(qualifier_id)
            result.append(value)
    return result
