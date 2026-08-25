"""Strict metadata source facts from explicitly labelled Canonical text."""

from __future__ import annotations

import copy
from dataclasses import replace
from datetime import datetime
import hashlib
import json
import re
from typing import Any, Iterable

from .artifact_models import ArtifactAccessContext, ArtifactStorePort
from .artifact_resolver import ArtifactResolver
from .canonical_store import CanonicalReader, CanonicalReaderFactory


GATE3_METADATA_SOURCE_FACT_COLLECTION_SCHEMA_VERSION = (
    "broker_reports_gate3_metadata_source_fact_collection_v2"
)
GATE3_METADATA_SOURCE_FACT_SCHEMA_VERSION = (
    "broker_reports_gate3_metadata_source_fact_v2"
)
GATE3_METADATA_SOURCE_FACT_TERMINAL = "METADATA_SOURCE_FACT_CONTRACT_PROVEN"
GATE3_MINIMAL_METADATA_CONTRACT_VERSION = "1.0.0"

GATE3_MINIMAL_METADATA_FACT_TYPES = (
    "PARTY_NAME",
    "PERSON_BIRTH_DATE",
    "TAXPAYER_TAX_IDENTIFIER",
    "PERSON_CITIZENSHIP",
    "DOCUMENT_TYPE",
    "DOCUMENT_NUMBER",
    "DOCUMENT_DATE",
    "STATEMENT_PERIOD",
    "BROKER_LEGAL_NAME",
    "ACCOUNT_IDENTIFIER",
    "ACCOUNT_CONTRACT_IDENTIFIER",
    "BROKER_TAX_IDENTIFIER",
    "BROKER_KPP",
    "BROKER_OKTMO",
    "PAYER_ORGANIZATION_JURISDICTION",
    "REALIZATION_LOCATION_JURISDICTION",
    "ADMITTED_EXCHANGE_FACT",
    "MARKET_QUOTATION_FACT",
    "IIS_STATUS_ASSERTION",
    "EXEMPTION_SOURCE_ASSERTION",
)

GATE3_MINIMAL_METADATA_SOURCE_EXAMPLE_STATUS = {
    "PARTY_NAME": "REAL_SOURCE_EXAMPLE",
    "PERSON_BIRTH_DATE": "NO_REAL_SOURCE_EXAMPLE",
    "TAXPAYER_TAX_IDENTIFIER": "NO_REAL_SOURCE_EXAMPLE",
    "PERSON_CITIZENSHIP": "NO_REAL_SOURCE_EXAMPLE",
    "DOCUMENT_TYPE": "REAL_SOURCE_EXAMPLE",
    "DOCUMENT_NUMBER": "NO_REAL_SOURCE_EXAMPLE",
    "DOCUMENT_DATE": "REAL_SOURCE_EXAMPLE",
    "STATEMENT_PERIOD": "REAL_SOURCE_EXAMPLE",
    "BROKER_LEGAL_NAME": "REAL_SOURCE_EXAMPLE",
    "ACCOUNT_IDENTIFIER": "REAL_SOURCE_EXAMPLE",
    "ACCOUNT_CONTRACT_IDENTIFIER": "REAL_SOURCE_EXAMPLE",
    "BROKER_TAX_IDENTIFIER": "NO_REAL_SOURCE_EXAMPLE",
    "BROKER_KPP": "NO_REAL_SOURCE_EXAMPLE",
    "BROKER_OKTMO": "NO_REAL_SOURCE_EXAMPLE",
    "PAYER_ORGANIZATION_JURISDICTION": "NO_REAL_SOURCE_EXAMPLE",
    "REALIZATION_LOCATION_JURISDICTION": "NO_REAL_SOURCE_EXAMPLE",
    "ADMITTED_EXCHANGE_FACT": "NO_REAL_SOURCE_EXAMPLE",
    "MARKET_QUOTATION_FACT": "NO_REAL_SOURCE_EXAMPLE",
    "IIS_STATUS_ASSERTION": "NO_REAL_SOURCE_EXAMPLE",
    "EXEMPTION_SOURCE_ASSERTION": "NO_REAL_SOURCE_EXAMPLE",
}

FACTORY_REQUIRED = (
    "Gate3MetadataSourceFactRuntimeFactory.create composes "
    "ArtifactResolver.catalog_case and CanonicalReaderFactory.create",
)
FORBIDDEN = (
    "Gate 4 reads, tax-case assembly, financial classification, unlabelled "
    "entity-role inference, broker-country to income-source or residency "
    "inference, metadata defaults, reconciliation or persistence",
)

_METADATA_CATEGORIES = (
    "PERSON_IDENTITY",
    "DOCUMENT_IDENTITY",
    "ISSUER_IDENTITY",
    "ACCOUNT_IDENTITY",
    "DECLARATION_SOURCE_ASSERTION",
)
_DATE_VALUE = r"(?:\d{2}[./-]\d{2}[./-]\d{4}|\d{4}-\d{2}-\d{2})"
_DATE = rf"(?P<start>{_DATE_VALUE})"
_DATE_END = rf"(?P<end>{_DATE_VALUE})"
_OPTIONAL_TIME = r"(?:\s+\d{2}:\d{2}:\d{2})?"
_PATTERNS: tuple[tuple[str, str, re.Pattern[str]], ...] = (
    (
        "TAXPAYER_TAX_IDENTIFIER",
        "PERSON_IDENTITY",
        re.compile(
            r"(?im)^\s*(?:инн\s+(?:налогоплательщика|клиента)|taxpayer\s+inn)"
            r"\s*[:#-]\s*(?P<value>[0-9]{12})\s*$"
        ),
    ),
    (
        "BROKER_TAX_IDENTIFIER",
        "ISSUER_IDENTITY",
        re.compile(
            r"(?im)^\s*(?:инн\s+(?:брокера|источника\s+дохода)|broker\s+inn)"
            r"\s*[:#-]\s*(?P<value>[0-9]{10})\s*$"
        ),
    ),
    (
        "BROKER_KPP",
        "ISSUER_IDENTITY",
        re.compile(
            r"(?im)^\s*(?:кпп\s+(?:брокера|источника\s+дохода)|broker\s+kpp)"
            r"\s*[:#-]\s*(?P<value>[0-9]{9})\s*$"
        ),
    ),
    (
        "BROKER_OKTMO",
        "ISSUER_IDENTITY",
        re.compile(
            r"(?im)^\s*(?:октмо\s+(?:брокера|источника\s+дохода)|broker\s+oktmo)"
            r"\s*[:#-]\s*(?P<value>[0-9]{8}(?:[0-9]{3})?)\s*$"
        ),
    ),
    (
        "PAYER_ORGANIZATION_JURISDICTION",
        "DECLARATION_SOURCE_ASSERTION",
        re.compile(
            r"(?im)^\s*(?:юрисдикция\s+(?:брокера|источника\s+дохода)|"
            r"payer\s+organization\s+jurisdiction)\s*[:#-]\s*"
            r"(?P<value>RU|РФ)\s*$"
        ),
    ),
    (
        "REALIZATION_LOCATION_JURISDICTION",
        "DECLARATION_SOURCE_ASSERTION",
        re.compile(
            r"(?im)^\s*(?:место\s+реализации|realization\s+location)\s*[:#-]\s*"
            r"(?P<value>RU|РФ)\s*$"
        ),
    ),
    (
        "ADMITTED_EXCHANGE_FACT",
        "DECLARATION_SOURCE_ASSERTION",
        re.compile(
            r"(?im)^\s*(?:допуск\s+к\s+торгам|admitted\s+exchange\s+fact)"
            r"\s*[:#-]\s*(?P<value>ADMITTED|NOT_ADMITTED|ДОПУЩЕНА)\s*$"
        ),
    ),
    (
        "MARKET_QUOTATION_FACT",
        "DECLARATION_SOURCE_ASSERTION",
        re.compile(
            r"(?im)^\s*(?:рыночная\s+котировка|market\s+quotation\s+fact)"
            r"\s*[:#-]\s*(?P<value>AVAILABLE|ИМЕЕТСЯ)\s*$"
        ),
    ),
    (
        "IIS_STATUS_ASSERTION",
        "DECLARATION_SOURCE_ASSERTION",
        re.compile(
            r"(?im)^\s*(?:режим\s+сч[её]та|account\s+regime)\s*[:#-]\s*"
            r"(?P<value>OUTSIDE_IIS|ВНЕ\s+ИИС)\s*$"
        ),
    ),
    (
        "EXEMPTION_SOURCE_ASSERTION",
        "DECLARATION_SOURCE_ASSERTION",
        re.compile(
            r"(?im)^\s*(?:заявленное\s+освобождение|source\s+exemption\s+claim)"
            r"\s*[:#-]\s*(?P<value>NONE|НЕТ)\s*$"
        ),
    ),
    (
        "BROKER_LEGAL_NAME",
        "ISSUER_IDENTITY",
        re.compile(r"(?im)^\s*(?:broker|брокер)\s*:\s*" r"(?P<value>[^\r\n,]{2,160})"),
    ),
    (
        "PARTY_NAME",
        "PERSON_IDENTITY",
        re.compile(
            r"(?im)^\s*(?:\(\s*фио\s*\)|фио|client name|customer name|"
            r"account holder|клиент|инвестор|владелец сч[её]та)\s*[:#-]\s*"
            r"(?P<value>[^\r\n,(;:]{2,160})"
        ),
    ),
    (
        "ACCOUNT_IDENTIFIER",
        "ACCOUNT_IDENTITY",
        re.compile(
            r"(?i)(?:account (?:number|no\.?)|номер сч[её]та|лицевой сч[её]т|субсч[её]т)"
            r"\s*[:#-]?\s*(?P<value>[A-Za-z0-9._/-]{2,128})"
        ),
    ),
    (
        "ACCOUNT_CONTRACT_IDENTIFIER",
        "ACCOUNT_IDENTITY",
        re.compile(
            r"(?im)^\s*генеральное соглашение\s*:\s*"
            r"(?P<value>[A-Za-zА-Яа-яЁё0-9._/-]{2,128})"
        ),
    ),
    (
        "ACCOUNT_CONTRACT_IDENTIFIER",
        "ACCOUNT_IDENTITY",
        re.compile(
            rf"(?im)^\s*договор\s+(?P<value>[A-Za-zА-Яа-яЁё0-9._/-]{{2,128}})"
            rf"\s+от\s+{_DATE_VALUE}\s*$"
        ),
    ),
    (
        "DOCUMENT_TYPE",
        "DOCUMENT_IDENTITY",
        re.compile(
            r"(?im)^\s*(?P<value>брокерский отч[её]т|отч[её]т брокера|"
            r"отч[её]т по сделкам для налоговой декларации|отч[её]т по операциям|"
            r"отч[её]т о расч[её]те налогооблагаемой базы физического лица)\b"
        ),
    ),
    (
        "DOCUMENT_DATE",
        "DOCUMENT_IDENTITY",
        re.compile(
            rf"(?im)^\s*(?:дата\s+(?:формирования|создания|подготовки|составления)"
            rf"\s+отч[её]та|дата\s+создания)\s*:?\s*(?P<value>{_DATE_VALUE})\s*$"
        ),
    ),
    (
        "STATEMENT_PERIOD",
        "DOCUMENT_IDENTITY",
        re.compile(
            rf"(?im)^\s*(?:statement period|reporting period|период|налоговый период)"
            rf"\s*:?\s*(?:с\s*)?{_DATE}{_OPTIONAL_TIME}\s*"
            rf"(?:-|–|—|to|through|по)\s*{_DATE_END}{_OPTIONAL_TIME}"
        ),
    ),
    (
        "STATEMENT_PERIOD",
        "DOCUMENT_IDENTITY",
        re.compile(
            rf"(?is)(?:отч[её]т[^\r\n]{{0,160}}\s+за период(?:\s+с)?|"
            rf"за период(?:\s+с)?)\D{{0,32}}{_DATE}{_OPTIONAL_TIME}\s*"
            rf"(?:-|–|—|to|through|по)\s*{_DATE_END}{_OPTIONAL_TIME}"
        ),
    ),
    (
        "STATEMENT_PERIOD",
        "DOCUMENT_IDENTITY",
        re.compile(
            rf"(?im)^\s*отч[её]т\s+(?:по сделкам для налоговой декларации|по операциям)"
            rf"[^\r\n]*\r?\n\s*{_DATE}{_OPTIONAL_TIME}\s*"
            rf"(?:-|–|—|to|through|по)\s*{_DATE_END}{_OPTIONAL_TIME}"
        ),
    ),
)


class Gate3MetadataSourceFactError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class Gate3MetadataSourceFactRuntimeFactory:
    def __init__(self, *, store: ArtifactStorePort, read_enabled: bool) -> None:
        self._store = store
        self._read_enabled = read_enabled

    def create(self) -> "Gate3MetadataSourceFactRuntime":
        return Gate3MetadataSourceFactRuntime(
            resolver=ArtifactResolver(self._store),
            canonical_reader=CanonicalReaderFactory(
                store=self._store,
                read_enabled=self._read_enabled,
            ).create(),
        )


class Gate3MetadataSourceFactRuntime:
    def __init__(
        self, *, resolver: ArtifactResolver, canonical_reader: CanonicalReader
    ) -> None:
        self._resolver = resolver
        self._canonical_reader = canonical_reader

    def collect(self, *, context: ArtifactAccessContext) -> dict[str, Any]:
        canonical_records = sorted(
            (
                record
                for record in self._resolver.catalog_case(context)
                if record.artifact_type == "broker_reports_canonical_artifact_v1"
            ),
            key=lambda item: (item.document_id or "", item.artifact_id),
        )
        facts: list[dict[str, Any]] = []
        documents: list[dict[str, Any]] = []
        for record in canonical_records:
            document_context = replace(
                context,
                normalization_run_id=record.normalization_run_id,
            )
            artifact = self._canonical_reader.read(record.artifact_id, document_context)
            document_facts = _metadata_facts(
                artifact=artifact,
                document_id=str(record.document_id or ""),
                canonical_version_id=str(artifact["artifact_id"]),
            )
            facts.extend(document_facts)
            documents.append(
                {
                    "document_id": str(record.document_id or ""),
                    "canonical_version_id": str(artifact["artifact_id"]),
                    "metadata_facts": len(document_facts),
                }
            )
        facts = _deduplicated_facts(facts)
        return {
            "schema_version": GATE3_METADATA_SOURCE_FACT_COLLECTION_SCHEMA_VERSION,
            "status": "metadata_source_facts_available",
            "terminals": [GATE3_METADATA_SOURCE_FACT_TERMINAL],
            "documents": documents,
            "metadata_facts": facts,
            "coverage": {
                "metadata_category_counts": {
                    category: sum(fact["category"] == category for fact in facts)
                    for category in _METADATA_CATEGORIES
                },
                "typed_metadata_facts": len(facts),
                "provenance_complete": all(
                    bool(fact["source_binding"]["source_refs"]) for fact in facts
                ),
                "invented_source_facts": 0,
                "unsupported_entity_role_inferences": 0,
            },
            "tax_meaning_assigned": False,
            "persistence": "none_new",
        }

    def collect_current(
        self,
        *,
        context: ArtifactAccessContext,
        canonical_coverage: dict[str, Any],
    ) -> dict[str, Any]:
        """Read only Canonical versions named by current case coverage."""

        scope = (
            canonical_coverage.get("document_scope")
            if isinstance(canonical_coverage, dict)
            else None
        )
        if (
            canonical_coverage.get("case_id") != context.case_id
            or canonical_coverage.get("status")
            not in {"complete", "relevant_unmapped", "missing_projection"}
            or not isinstance(scope, list)
            or not scope
        ):
            raise Gate3MetadataSourceFactError(
                "case_metadata_current_coverage_invalid"
            )
        facts: list[dict[str, Any]] = []
        documents: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in scope:
            if (
                not isinstance(item, dict)
                or set(item)
                != {
                    "document_id",
                    "canonical_version_id",
                    "canonical_root_sha256",
                    "manifest_ref",
                }
                or item["manifest_ref"] in seen
            ):
                raise Gate3MetadataSourceFactError(
                    "case_metadata_current_coverage_invalid"
                )
            seen.add(item["manifest_ref"])
            try:
                resolved = self._resolver.resolve_case(
                    item["manifest_ref"], context
                )
            except Exception as exc:
                raise Gate3MetadataSourceFactError(
                    "case_metadata_current_canonical_unavailable"
                ) from exc
            record = resolved["record"]
            if (
                record.artifact_type != "broker_reports_canonical_artifact_v1"
                or record.document_id != item["document_id"]
            ):
                raise Gate3MetadataSourceFactError(
                    "case_metadata_current_canonical_misbound"
                )
            document_context = replace(
                context,
                normalization_run_id=record.normalization_run_id,
            )
            artifact = self._canonical_reader.read(
                record.artifact_id, document_context
            )
            if (
                artifact.get("artifact_id") != item["canonical_version_id"]
                or artifact.get("canonical_root_hash")
                != item["canonical_root_sha256"]
            ):
                raise Gate3MetadataSourceFactError(
                    "case_metadata_current_canonical_misbound"
                )
            document_facts = _metadata_facts(
                artifact=artifact,
                document_id=item["document_id"],
                canonical_version_id=item["canonical_version_id"],
            )
            facts.extend(document_facts)
            documents.append(
                {
                    "document_id": item["document_id"],
                    "canonical_version_id": item["canonical_version_id"],
                    "metadata_facts": len(document_facts),
                }
            )
        facts = _deduplicated_facts(facts)
        return {
            "schema_version": GATE3_METADATA_SOURCE_FACT_COLLECTION_SCHEMA_VERSION,
            "status": "current_case_metadata_source_facts_available",
            "terminals": [GATE3_METADATA_SOURCE_FACT_TERMINAL],
            "coverage_ref": canonical_coverage.get("coverage_ref"),
            "documents": documents,
            "metadata_facts": facts,
            "tax_meaning_assigned": False,
            "persistence": "none_new",
        }

    @staticmethod
    def query(
        collection: dict[str, Any], *, fact_types: Iterable[str]
    ) -> list[dict[str, Any]]:
        requested = set(fact_types)
        return [
            copy.deepcopy(fact)
            for fact in collection.get("metadata_facts", [])
            if fact.get("fact_type") in requested
        ]


def _metadata_facts(
    *, artifact: dict[str, Any], document_id: str, canonical_version_id: str
) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    for node in artifact.get("nodes") or []:
        content = node.get("content") or {}
        source_refs = [str(item) for item in node.get("source_refs") or []]
        text_values: list[tuple[str, str]] = []
        if node.get("node_type") == "TEXT":
            node_text = str(content.get("text") or "")
            for index, line in enumerate(node_text.splitlines()):
                if line.strip():
                    text_values.append((f"content.text.lines[{index}]", line.strip()))
            if "\n" in node_text and node_text.strip():
                text_values.append(("content.text", node_text.strip()))
        elif node.get("node_type") == "TABLE":
            for index, cell in enumerate(content.get("cells") or []):
                value = _cell_text(cell)
                if value:
                    text_values.append((f"content.cells[{index}]", value))
        for field_path, source_text in text_values:
            for fact_type, category, pattern in _PATTERNS:
                for match in pattern.finditer(source_text):
                    normalized = _normalized_value(fact_type=fact_type, match=match)
                    if normalized is None:
                        continue
                    base = {
                        "schema_version": GATE3_METADATA_SOURCE_FACT_SCHEMA_VERSION,
                        "semantic_kind": "normalized_source_fact",
                        "fact_type": fact_type,
                        "category": category,
                        "value": normalized,
                        "source_binding": {
                            "document_id": document_id,
                            "canonical_version_id": canonical_version_id,
                            "node_id": str(node.get("node_id") or ""),
                            "field_path": field_path,
                            "source_refs": source_refs,
                            "matched_source_sha256": hashlib.sha256(
                                match.group(0).encode("utf-8")
                            ).hexdigest(),
                        },
                        "tax_meaning_assigned": False,
                    }
                    facts.append(
                        {**base, "fact_id": "g3metadata_" + _sha256(base)[:32]}
                    )
        if node.get("node_type") == "TABLE":
            facts.extend(
                _adjacent_table_metadata_facts(
                    cells=content.get("cells") or [],
                    document_id=document_id,
                    canonical_version_id=canonical_version_id,
                    node_id=str(node.get("node_id") or ""),
                    node_source_refs=source_refs,
                )
            )
            facts.extend(
                _column_header_metadata_facts(
                    cells=content.get("cells") or [],
                    document_id=document_id,
                    canonical_version_id=canonical_version_id,
                    node_id=str(node.get("node_id") or ""),
                    node_source_refs=source_refs,
                )
            )
    return _deduplicated_facts(facts)


def _adjacent_table_metadata_facts(
    *,
    cells: list[dict[str, Any]],
    document_id: str,
    canonical_version_id: str,
    node_id: str,
    node_source_refs: list[str],
) -> list[dict[str, Any]]:
    """Bind only unambiguous two-cell rows through the existing vocabulary."""
    facts: list[dict[str, Any]] = []
    for label_index, label_cell, value_index, value_cell in _two_cell_rows(cells):
        label = _cell_text(label_cell)
        value = _cell_text(value_cell)
        if not label or not value:
            continue
        candidate = f"{label}: {value}"
        value_offset = len(label) + 2
        for fact_type, category, pattern in _PATTERNS:
            for match in pattern.finditer(candidate):
                value_group = "start" if fact_type == "STATEMENT_PERIOD" else "value"
                if match.start() != 0 or match.start(value_group) < value_offset:
                    continue
                normalized = _normalized_value(fact_type=fact_type, match=match)
                if normalized is None:
                    continue
                pair_source_refs = sorted(
                    {
                        *node_source_refs,
                        *(str(item) for item in label_cell.get("source_refs") or []),
                        *(str(item) for item in value_cell.get("source_refs") or []),
                    }
                )
                base = {
                    "schema_version": GATE3_METADATA_SOURCE_FACT_SCHEMA_VERSION,
                    "semantic_kind": "normalized_source_fact",
                    "fact_type": fact_type,
                    "category": category,
                    "value": normalized,
                    "source_binding": {
                        "document_id": document_id,
                        "canonical_version_id": canonical_version_id,
                        "node_id": node_id,
                        "field_path": f"content.cells[{value_index}]",
                        "label_field_path": f"content.cells[{label_index}]",
                        "binding_kind": "adjacent_table_label_value",
                        "source_refs": pair_source_refs,
                        "matched_source_sha256": hashlib.sha256(
                            f"{label}\0{value}".encode("utf-8")
                        ).hexdigest(),
                    },
                    "tax_meaning_assigned": False,
                }
                facts.append({**base, "fact_id": "g3metadata_" + _sha256(base)[:32]})
    return facts


def _two_cell_rows(
    cells: list[dict[str, Any]],
) -> list[tuple[int, dict[str, Any], int, dict[str, Any]]]:
    rows: dict[int, list[tuple[int, int, dict[str, Any]]]] = {}
    invalid_rows: set[int] = set()
    occupied: set[tuple[int, int]] = set()
    for index, cell in enumerate(cells):
        row = cell.get("row")
        column = cell.get("column")
        if (
            not isinstance(row, int)
            or row < 1
            or not isinstance(column, int)
            or column < 1
        ):
            continue
        coordinate = (row, column)
        if coordinate in occupied or cell.get("merged_range"):
            invalid_rows.add(row)
        occupied.add(coordinate)
        rows.setdefault(row, []).append((column, index, cell))
    result: list[tuple[int, dict[str, Any], int, dict[str, Any]]] = []
    for row, row_cells in rows.items():
        ordered = sorted(row_cells, key=lambda item: item[0])
        if row in invalid_rows or len(ordered) != 2:
            continue
        left, right = ordered
        if right[0] != left[0] + 1:
            continue
        result.append((left[1], left[2], right[1], right[2]))
    return result


def _column_header_metadata_facts(
    *,
    cells: list[dict[str, Any]],
    document_id: str,
    canonical_version_id: str,
    node_id: str,
    node_source_refs: list[str],
) -> list[dict[str, Any]]:
    """Bind every value under one unambiguous supported column header."""
    positioned: list[tuple[int, int, int, dict[str, Any]]] = []
    occupied: set[tuple[int, int]] = set()
    invalid_columns: set[int] = set()
    for index, cell in enumerate(cells):
        row = cell.get("row")
        column = cell.get("column")
        if (
            not isinstance(row, int)
            or row < 1
            or not isinstance(column, int)
            or column < 1
        ):
            continue
        coordinate = (row, column)
        if coordinate in occupied or cell.get("merged_range"):
            invalid_columns.add(column)
        occupied.add(coordinate)
        positioned.append((row, column, index, cell))
    if not positioned:
        return []

    header_row = min(item[0] for item in positioned)
    candidates: list[
        tuple[int, int, dict[str, Any], list[tuple[int, dict[str, Any], re.Match[str]]]]
    ] = []
    account_patterns = [
        pattern
        for fact_type, _category, pattern in _PATTERNS
        if fact_type == "ACCOUNT_IDENTIFIER"
    ]
    for row, column, header_index, header_cell in positioned:
        if row != header_row or column in invalid_columns:
            continue
        header = _cell_text(header_cell)
        if not header:
            continue
        matches: list[tuple[int, dict[str, Any], re.Match[str]]] = []
        for value_row, value_column, value_index, value_cell in positioned:
            if value_column != column or value_row <= header_row:
                continue
            value = _cell_text(value_cell)
            if not value:
                continue
            candidate = f"{header}: {value}"
            value_offset = len(header) + 2
            matched = next(
                (
                    match
                    for pattern in account_patterns
                    for match in pattern.finditer(candidate)
                    if match.start() == 0 and match.start("value") >= value_offset
                ),
                None,
            )
            if matched is not None:
                matches.append((value_index, value_cell, matched))
        if matches:
            candidates.append((header_index, column, header_cell, matches))

    if len(candidates) != 1:
        return []
    header_index, _column, header_cell, matches = candidates[0]
    header = _cell_text(header_cell)
    facts: list[dict[str, Any]] = []
    for value_index, value_cell, match in matches:
        value = _cell_text(value_cell)
        normalized = _normalized_value(fact_type="ACCOUNT_IDENTIFIER", match=match)
        if normalized is None:
            continue
        pair_source_refs = sorted(
            {
                *node_source_refs,
                *(str(item) for item in header_cell.get("source_refs") or []),
                *(str(item) for item in value_cell.get("source_refs") or []),
            }
        )
        base = {
            "schema_version": GATE3_METADATA_SOURCE_FACT_SCHEMA_VERSION,
            "semantic_kind": "normalized_source_fact",
            "fact_type": "ACCOUNT_IDENTIFIER",
            "category": "ACCOUNT_IDENTITY",
            "value": normalized,
            "source_binding": {
                "document_id": document_id,
                "canonical_version_id": canonical_version_id,
                "node_id": node_id,
                "field_path": f"content.cells[{value_index}]",
                "label_field_path": f"content.cells[{header_index}]",
                "binding_kind": "explicit_column_header_values",
                "source_refs": pair_source_refs,
                "matched_source_sha256": hashlib.sha256(
                    f"{header}\0{value}".encode("utf-8")
                ).hexdigest(),
            },
            "tax_meaning_assigned": False,
        }
        facts.append({**base, "fact_id": "g3metadata_" + _sha256(base)[:32]})
    return facts


def _cell_text(cell: dict[str, Any]) -> str:
    value = cell.get("displayed_value")
    if value is None:
        value = cell.get("value")
    return "" if value is None else str(value).strip()


def _normalized_value(*, fact_type: str, match: re.Match[str]) -> dict[str, Any] | None:
    if fact_type == "STATEMENT_PERIOD":
        start = _date(match.group("start"))
        end = _date(match.group("end"))
        if start is None or end is None or start > end:
            return None
        return {"kind": "period", "start": start, "end": end}
    if fact_type == "DOCUMENT_DATE":
        value = _date(match.group("value"))
        return None if value is None else {"kind": "date", "date": value}
    value = " ".join(match.group("value").split()).strip(" ,;:-")
    if not value or len(value) > 256:
        return None
    return {"kind": "text", "normalized": value}


def _date(value: str) -> str | None:
    for pattern in ("%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, pattern).date().isoformat()
        except ValueError:
            continue
    return None


def _deduplicated_facts(facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: list[dict[str, Any]] = []
    seen: set[str] = set()
    for fact in facts:
        semantic_key = _sha256(
            {
                "document_id": fact["source_binding"]["document_id"],
                "canonical_version_id": fact["source_binding"]["canonical_version_id"],
                "fact_type": fact["fact_type"],
                "value": fact["value"],
            }
        )
        if semantic_key in seen:
            continue
        seen.add(semantic_key)
        unique.append(copy.deepcopy(fact))
    return unique


def _sha256(value: Any) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


__all__ = [
    "FACTORY_REQUIRED",
    "FORBIDDEN",
    "GATE3_METADATA_SOURCE_FACT_COLLECTION_SCHEMA_VERSION",
    "GATE3_METADATA_SOURCE_FACT_SCHEMA_VERSION",
    "GATE3_METADATA_SOURCE_FACT_TERMINAL",
    "GATE3_MINIMAL_METADATA_CONTRACT_VERSION",
    "GATE3_MINIMAL_METADATA_FACT_TYPES",
    "GATE3_MINIMAL_METADATA_SOURCE_EXAMPLE_STATUS",
    "Gate3MetadataSourceFactError",
    "Gate3MetadataSourceFactRuntime",
    "Gate3MetadataSourceFactRuntimeFactory",
]
