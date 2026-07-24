from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Iterable

from .gate2_financial_context import (
    Gate2FinancialContextProjectionFactory,
)
from .gate2_financial_evidence_catalog import (
    SUPPORTED_SOURCE_FAMILIES,
)
from .gate2_financial_evidence_decision import (
    FinancialEvidenceDecisionPackage,
    FinancialEvidenceValueCandidate,
    Gate2FinancialEvidenceDecisionContractFactory,
)
from .gate2_financial_evidence_materialization import (
    FinancialEvidenceAuthoritativeSourceValue,
    FinancialEvidenceExecutionMetadata,
    FinancialEvidenceSourceLineage,
    Gate2FinancialEvidenceMaterializerFactory,
    Gate2FinancialEvidenceSourcePackageFactory,
    Gate2FinancialEvidenceValidatedDecisionFactory,
)
from .gate2_financial_evidence_registry import (
    Gate2FinancialEvidenceRegistrySnapshot,
)


SEMANTIC_VISUAL_ADAPTER_VERSION = (
    "broker_reports_gate2_semantic_visual_financial_evidence_adapter_v1"
)
FACTORY_REQUIRED = (
    "Gate2SemanticVisualFinancialContextFactory.create is the only "
    "semantic-visual to row-scoped Gate 2 financial context entrypoint"
)
FORBIDDEN = (
    "Raw semantic-table containers, images, crops, PDFs and Gate 1 "
    "artifact metadata must not cross the resulting model context boundary"
)

_DECIMAL_RE = re.compile(r"^[+-]?(?:0|[1-9]\d*)(?:\.\d+)?$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_PERIOD_RE = re.compile(
    r"^(?:\d{4}(?:[- /]?(?:q[1-4]|h[12]|fy))?|"
    r"(?:q[1-4]|h[12]|fy)[- /]?\d{4})$",
    re.IGNORECASE,
)
_CURRENCIES = frozenset(
    {"AED", "CHF", "CNY", "EUR", "GBP", "HKD", "JPY", "KZT", "RUB", "USD"}
)


class Gate2SemanticVisualFinancialContextError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Gate2SemanticVisualTableEvidence:
    document_ref: str
    table_ref: str
    page_ref: str
    description_literals: tuple[str, ...]
    header_literals: tuple[str, ...]
    data_rows: tuple[tuple[str, ...], ...]


class Gate2SemanticVisualFinancialContextFactory:
    def __init__(
        self,
        *,
        registry: Gate2FinancialEvidenceRegistrySnapshot,
    ) -> None:
        self.registry = registry

    def create(
        self,
        *,
        tables: Iterable[Gate2SemanticVisualTableEvidence],
    ) -> dict:
        artifacts = []
        packages = []
        tables_tuple = tuple(tables)
        if not tables_tuple:
            _fail("semantic_visual_financial_context_empty")
        dimensions_by_document = _document_dimensions(tables_tuple)
        for table in tables_tuple:
            self._validate_table(table)
            for row_index, row in enumerate(table.data_rows, start=1):
                artifact, package = self._materialize_row(
                    table=table,
                    row=row,
                    row_index=row_index,
                    document_dimensions=dimensions_by_document.get(
                        table.document_ref, ()
                    ),
                )
                artifacts.append(artifact)
                packages.append(package)
        if not artifacts:
            _fail("semantic_visual_financial_context_no_data_rows")
        context = Gate2FinancialContextProjectionFactory(
            registry=self.registry
        ).create(
            materialized_artifacts=artifacts,
            source_packages=packages,
        )
        return context

    @staticmethod
    def _validate_table(table: Gate2SemanticVisualTableEvidence) -> None:
        if not all(
            (
                table.document_ref.strip(),
                table.table_ref.strip(),
                table.page_ref.strip(),
                table.header_literals,
                table.data_rows,
            )
        ):
            _fail("semantic_visual_financial_context_table_invalid")
        if any(
            not isinstance(item, str) or not item.strip()
            for item in (
                *table.description_literals,
                *table.header_literals,
                *(cell for row in table.data_rows for cell in row),
            )
        ):
            _fail("semantic_visual_financial_context_literal_invalid")

    def _materialize_row(
        self,
        *,
        table: Gate2SemanticVisualTableEvidence,
        row: tuple[str, ...],
        row_index: int,
        document_dimensions: tuple[
            tuple[str, str, str, str], ...
        ],
    ):
        identity = {
            "adapter_version": SEMANTIC_VISUAL_ADAPTER_VERSION,
            "document_ref": table.document_ref,
            "table_ref": table.table_ref,
            "page_ref": table.page_ref,
            "row_index": row_index,
        }
        digest = hashlib.sha256(
            repr(sorted(identity.items())).encode("utf-8")
        ).hexdigest()[:24]
        values = []
        candidates = []
        literals = (
            *(
                ("description", index, literal)
                for index, literal in enumerate(
                    table.description_literals, start=1
                )
            ),
            *(
                ("header", index, literal)
                for index, literal in enumerate(
                    table.header_literals, start=1
                )
            ),
            *(
                ("cell", index, literal)
                for index, literal in enumerate(row, start=1)
            ),
            *(
                (kind, index, literal)
                for index, (
                    kind,
                    literal,
                    _,
                    _,
                ) in enumerate(document_dimensions, start=1)
            ),
        )
        for kind, index, literal in literals:
            dimension = next(
                (
                    item
                    for item in document_dimensions
                    if item[0] == kind and item[1] == literal
                ),
                None,
            )
            value_type, role = (
                (dimension[2], dimension[3])
                if dimension is not None
                else _classify_literal(literal)
            )
            value_ref = (
                f"value:gate2:semantic-visual:{digest}:{kind}:{index}"
            )
            source_ref = (
                f"source:gate2:semantic-visual:{digest}:{kind}:{index}"
            )
            value = FinancialEvidenceAuthoritativeSourceValue(
                source_value_ref=value_ref,
                source_ref=source_ref,
                value_type=value_type,
                literal_value=literal,
                source_evidence_refs=(table.table_ref, source_ref),
                lineage=FinancialEvidenceSourceLineage(
                    document_ref=table.document_ref,
                    page_ref=table.page_ref,
                    table_ref=table.table_ref,
                    row_ref=f"{table.table_ref}:row:{row_index}",
                    cell_ref=(
                        f"{table.table_ref}:row:{row_index}:{kind}:{index}"
                    ),
                ),
            )
            values.append(value)
            candidates.append(
                FinancialEvidenceValueCandidate(
                    source_value_ref=value_ref,
                    source_ref=source_ref,
                    value_type=value_type,
                    allowed_roles=(role,),
                )
            )
        source_scope_ref = f"scope:gate2:semantic-visual:{digest}"
        package = Gate2FinancialEvidenceSourcePackageFactory(
            package_ref=f"package:gate2:semantic-visual:{digest}",
            normalization_run_ref=(
                f"normalization:gate2:semantic-visual:{digest}"
            ),
            document_ref=table.document_ref,
            source_scope_ref=source_scope_ref,
            source_family_id=SUPPORTED_SOURCE_FAMILIES[0],
            source_values=tuple(values),
            source_evidence_refs=(table.table_ref,),
            completeness="complete",
        ).create()
        contract = Gate2FinancialEvidenceDecisionContractFactory(
            registry=self.registry,
            package=FinancialEvidenceDecisionPackage(
                source_scope_ref=source_scope_ref,
                source_family_id=package.source_family_id,
                candidates=tuple(candidates),
            ),
        ).create()
        decision = {
            "decision": {
                "disposition": "unclassified_financial_input",
                "value_bindings": [
                    {
                        "role_id": candidate.allowed_roles[0],
                        "source_value_ref": candidate.source_value_ref,
                    }
                    for candidate in candidates
                ],
                "reason_code": "no_registry_type",
            }
        }
        validated = Gate2FinancialEvidenceValidatedDecisionFactory(
            contract=contract
        ).create(decision)
        artifact = Gate2FinancialEvidenceMaterializerFactory(
            registry=self.registry,
            source_package=package,
            execution_metadata=FinancialEvidenceExecutionMetadata(
                execution_ref=(
                    f"execution:gate2:semantic-visual:{digest}"
                ),
                decision_validation_ref=(
                    f"validation:gate2:semantic-visual:{digest}"
                ),
            ),
        ).create().materialize(validated_decision=validated)
        return artifact, package


def _classify_literal(literal: str) -> tuple[str, str]:
    normalized = literal.strip()
    if _DATE_RE.fullmatch(normalized):
        return "source_date", "as_of_date"
    if _PERIOD_RE.fullmatch(normalized):
        return "source_period", "period"
    if normalized.upper() in _CURRENCIES:
        return "source_currency", "currency"
    if _DECIMAL_RE.fullmatch(normalized):
        return "source_decimal", "amount"
    return "source_text", "source_label"


def _document_dimensions(
    tables: tuple[Gate2SemanticVisualTableEvidence, ...],
) -> dict[str, tuple[tuple[str, str, str, str], ...]]:
    literals_by_document: dict[str, list[str]] = {}
    for table in tables:
        literals_by_document.setdefault(table.document_ref, []).extend(
            (
                *table.description_literals,
                *table.header_literals,
                *(cell for row in table.data_rows for cell in row),
            )
        )
    result = {}
    for document_ref, literals in literals_by_document.items():
        dimensions = []
        currency_codes = {
            code
            for code in _CURRENCIES
            if any(
                re.search(
                    rf"(?<![A-Za-z0-9]){re.escape(code)}"
                    rf"(?![A-Za-z0-9])",
                    item,
                    re.IGNORECASE,
                )
                for item in literals
            )
        }
        dollar_present = any(
            re.search(r"(?<![A-Za-z0-9])\$(?=\s|\d|$)", item)
            for item in literals
        )
        if dollar_present and currency_codes - {"USD"}:
            _fail("semantic_visual_document_currency_conflict")
        if not currency_codes and dollar_present:
            currency_codes = {"USD"}
        if len(currency_codes) > 1:
            _fail("semantic_visual_document_currency_conflict")
        if len(currency_codes) == 1:
            dimensions.append(
                (
                    "document-currency",
                    next(iter(currency_codes)),
                    "source_currency",
                    "currency",
                )
            )
        if any(
            re.search(r"\bthousands\b", item, re.IGNORECASE)
            for item in literals
        ):
            dimensions.append(
                (
                    "document-unit",
                    "thousands",
                    "source_unit",
                    "unit",
                )
            )
        result[document_ref] = tuple(dimensions)
    return result


def _fail(code: str) -> None:
    raise Gate2SemanticVisualFinancialContextError(code)
