from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable

from .gate2_financial_context_contracts import (
    FINANCIAL_CONTEXT_SCHEMA_VERSION,
)
from .gate2_financial_context_validation import validate_financial_context
from .gate2_financial_evidence_materialization_contracts import sha256_json
from .gate2_financial_evidence_registry import (
    Gate2FinancialEvidenceRegistrySnapshot,
)
from .gate2_model_contracts import (
    Gate2StructuredModelClient,
    gate2_provider_execution_safe_metadata,
)


CHECKSUM_SCHEMA_VERSION = (
    "broker_reports_gate2_financial_context_checksum_v1"
)
CHECKSUM_PROMPT_CONTRACT_ID = (
    "broker_reports_gate2_financial_context_checksum_prompt_v1"
)
CHECKSUM_SCHEMA_NAME = "broker_reports_gate2_financial_context_checksum"
FACTORY_REQUIRED = (
    "Gate2FinancialContextChecksumContractFactory.create, "
    "Gate2FinancialContextChecksumRunnerFactory.create and "
    "Gate2FinancialContextChecksumComparatorFactory.create are the only "
    "Goal 8 checksum entrypoints"
)
FORBIDDEN = (
    "The answering model must not receive PDFs, crops, Gate 1 document "
    "memory, Gate 1 semantic tables, sealed expected values, customer "
    "methodology, Gate 3 instructions or tax skills"
)

_FORBIDDEN_MODEL_KEYS = frozenset(
    {
        "arithmetic_reconciliation",
        "crop",
        "customer_methodology",
        "document_memory",
        "expected",
        "expected_metric",
        "gate1",
        "gate1_content",
        "gate3",
        "pdf",
        "sealed_reference",
        "semantic_table",
        "tax_skill",
    }
)
_ANSWER_FIELDS = frozenset(
    {
        "metric_id",
        "source_label",
        "value",
        "currency",
        "unit",
        "sign",
        "period",
        "context_entry_id",
        "source_scope_ref",
        "source_value_ref",
        "page_ref",
    }
)


class Gate2FinancialContextChecksumError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Gate2ChecksumMetricRequest:
    metric_id: str
    source_label: str


@dataclass(frozen=True)
class Gate2ChecksumExpectedMetric:
    metric_id: str
    source_label: str
    normalized_value: str
    currency: str
    unit: str
    sign: str
    period_literals: tuple[str, ...]
    context_entry_id: str
    source_scope_ref: str
    source_value_ref: str
    page_ref: str
    semantic_visual_table_derived: bool
    arithmetic_operands: tuple[str, ...] = ()


@dataclass(frozen=True)
class Gate2FinancialContextChecksumPrompt:
    prompt_ref: str
    content: str
    hash: str


@dataclass(frozen=True)
class Gate2FinancialContextChecksumContract:
    financial_context: dict[str, Any]
    metric_requests: tuple[Gate2ChecksumMetricRequest, ...]

    def canonical_schema(self) -> dict[str, Any]:
        metric_ids = [item.metric_id for item in self.metric_requests]
        metric = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "metric_id": {"type": "string", "enum": metric_ids},
                "source_label": {"type": "string"},
                "value": {"type": "string"},
                "currency": {"type": "string"},
                "unit": {"type": "string"},
                "sign": {
                    "type": "string",
                    "enum": ["positive", "negative", "zero"],
                },
                "period": {"type": "string"},
                "context_entry_id": {"type": "string"},
                "source_scope_ref": {"type": "string"},
                "source_value_ref": {"type": "string"},
                "page_ref": {"type": "string"},
            },
            "required": sorted(_ANSWER_FIELDS),
        }
        return {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "metrics": {
                    "type": "array",
                    "items": metric,
                    "minItems": len(self.metric_requests),
                    "maxItems": len(self.metric_requests),
                }
            },
            "required": ["metrics"],
        }

    def openai_response_format(self) -> dict[str, Any]:
        return {
            "type": "json_schema",
            "json_schema": {
                "name": CHECKSUM_SCHEMA_NAME,
                "strict": True,
                "schema": copy.deepcopy(self.canonical_schema()),
            },
        }

    def model_package(self) -> dict[str, Any]:
        package = {
            "checksum_schema_version": CHECKSUM_SCHEMA_VERSION,
            "requested_metrics": [
                {
                    "metric_id": item.metric_id,
                    "source_label": item.source_label,
                }
                for item in self.metric_requests
            ],
            "financial_context": copy.deepcopy(self.financial_context),
        }
        _validate_model_package_isolation(package)
        return {
            "llm_context_package": package,
            "financial_context_integrity_hash": self.financial_context[
                "integrity_hash"
            ],
        }

    def parse_model_output(
        self, payload: str | dict[str, Any]
    ) -> tuple[dict[str, str], ...]:
        if isinstance(payload, str):
            try:
                parsed = json.loads(payload)
            except json.JSONDecodeError:
                _fail("financial_context_checksum_json_invalid")
        else:
            parsed = payload
        if not isinstance(parsed, dict) or set(parsed) != {"metrics"}:
            _fail("financial_context_checksum_root_invalid")
        rows = parsed["metrics"]
        if not isinstance(rows, list):
            _fail("financial_context_checksum_metrics_invalid")
        result = []
        for row in rows:
            if not isinstance(row, dict) or set(row) != _ANSWER_FIELDS:
                _fail("financial_context_checksum_metric_shape_invalid")
            if not all(isinstance(row[key], str) for key in _ANSWER_FIELDS):
                _fail("financial_context_checksum_metric_type_invalid")
            if row["sign"] not in {"positive", "negative", "zero"}:
                _fail("financial_context_checksum_sign_invalid")
            result.append(dict(row))
        return tuple(result)


class Gate2FinancialContextChecksumContractFactory:
    def __init__(
        self,
        *,
        registry: Gate2FinancialEvidenceRegistrySnapshot,
    ) -> None:
        self.registry = registry

    def create(
        self,
        *,
        financial_context: dict[str, Any],
        metric_requests: Iterable[Gate2ChecksumMetricRequest],
    ) -> Gate2FinancialContextChecksumContract:
        validate_financial_context(
            payload=financial_context,
            registry=self.registry,
        )
        requests = tuple(metric_requests)
        if len(requests) != 3:
            _fail("financial_context_checksum_metric_count_invalid")
        if any(
            not item.metric_id.strip() or not item.source_label.strip()
            for item in requests
        ):
            _fail("financial_context_checksum_metric_request_invalid")
        if len({item.metric_id for item in requests}) != len(requests):
            _fail("financial_context_checksum_metric_id_duplicate")
        contract = Gate2FinancialContextChecksumContract(
            financial_context=copy.deepcopy(financial_context),
            metric_requests=requests,
        )
        contract.model_package()
        return contract


class Gate2FinancialContextChecksumPromptFactory:
    def create(self) -> Gate2FinancialContextChecksumPrompt:
        content = (
            "You are the isolated Gate 2 financial-context checksum. Use "
            "only requested_metrics and financial_context from the embedded "
            "package. Do not use external knowledge, infer absent facts, "
            "calculate new metrics, or access any other broker-report "
            "artifact. Reconstruct exactly one printed metric row for each "
            "request. Copy the value and its Gate 2 binding exactly. Return "
            "only the strict schema object.\n"
            "{{financial_context_checksum_package_json}}"
        )
        digest = hashlib.sha256(
            (
                content + "\ncontract:" + CHECKSUM_PROMPT_CONTRACT_ID
            ).encode("utf-8")
        ).hexdigest()
        return Gate2FinancialContextChecksumPrompt(
            prompt_ref="code:" + CHECKSUM_PROMPT_CONTRACT_ID,
            content=content,
            hash=digest,
        )


class Gate2FinancialContextChecksumRunnerFactory:
    def __init__(
        self,
        *,
        model_client: Gate2StructuredModelClient,
        model_id: str,
        provider_profile_id: str,
    ) -> None:
        self.model_client = model_client
        self.model_id = model_id
        self.provider_profile_id = provider_profile_id

    def create(self) -> "Gate2FinancialContextChecksumRunner":
        if not self.model_id or not self.provider_profile_id:
            _fail("financial_context_checksum_provider_config_invalid")
        return Gate2FinancialContextChecksumRunner(
            model_client=self.model_client,
            model_id=self.model_id,
            provider_profile_id=self.provider_profile_id,
            prompt=Gate2FinancialContextChecksumPromptFactory().create(),
        )


class Gate2FinancialContextChecksumRunner:
    def __init__(
        self,
        *,
        model_client: Gate2StructuredModelClient,
        model_id: str,
        provider_profile_id: str,
        prompt: Gate2FinancialContextChecksumPrompt,
    ) -> None:
        self.model_client = model_client
        self.model_id = model_id
        self.provider_profile_id = provider_profile_id
        self.prompt = prompt

    async def run(
        self,
        *,
        contract: Gate2FinancialContextChecksumContract,
    ) -> dict[str, Any]:
        result = await self.model_client.extract(
            prompt=self.prompt,
            package=contract.model_package(),
            model_id=self.model_id,
            response_format=contract.openai_response_format(),
        )
        if result.fallback_used:
            _fail("financial_context_checksum_fallback_forbidden")
        if result.repair_attempt_count:
            _fail("financial_context_checksum_repair_forbidden")
        rows = contract.parse_model_output(result.content)
        return {
            "rows": rows,
            "provider_execution": (
                {}
                if result.execution_metadata is None
                else gate2_provider_execution_safe_metadata(
                    result.execution_metadata
                )
            ),
            "fallback_used": False,
            "repair_attempt_count": 0,
        }


class Gate2FinancialContextChecksumComparatorFactory:
    def create(
        self,
        *,
        contract: Gate2FinancialContextChecksumContract,
        expected_metrics: Iterable[Gate2ChecksumExpectedMetric],
        answer_rows: Iterable[dict[str, str]],
    ) -> dict[str, Any]:
        expected = tuple(expected_metrics)
        requests = {item.metric_id: item for item in contract.metric_requests}
        if (
            len(expected) != 3
            or {item.metric_id for item in expected} != set(requests)
        ):
            _fail("financial_context_checksum_expected_vector_invalid")
        rows = tuple(answer_rows)
        by_id: dict[str, list[dict[str, str]]] = {}
        for row in rows:
            by_id.setdefault(row.get("metric_id", ""), []).append(row)
        invented_ids = set(by_id) - set(requests)
        duplicate_rows_total = sum(
            max(0, len(values) - 1) for values in by_id.values()
        )
        results = [
            self._compare_metric(
                contract=contract,
                expected=item,
                rows=by_id.get(item.metric_id, []),
            )
            for item in expected
        ]
        metrics_passed_total = sum(item["passed"] for item in results)
        semantic_visual_passed_total = sum(
            item["passed"] and item["semantic_visual_table_derived"]
            for item in results
        )
        arithmetic_applicable_total = sum(
            item["arithmetic_reconciliation"]["applicable"]
            for item in results
        )
        arithmetic_passed_total = sum(
            item["arithmetic_reconciliation"]["passed"]
            for item in results
        )
        checks = {
            "gate1_content_in_model_context_zero": (
                _forbidden_model_key_count(contract.model_package()) == 0
            ),
            "metrics_reconstructed_3_of_3": metrics_passed_total == 3,
            "amount_currency_sign_period_3_of_3": all(
                item["amount_match"]
                and item["currency_match"]
                and item["sign_match"]
                and item["period_match"]
                for item in results
            ),
            "source_binding_3_of_3": all(
                item["source_binding_match"] for item in results
            ),
            "semantic_visual_table_metric_passed": (
                semantic_visual_passed_total >= 1
            ),
            "duplicate_rows_zero": duplicate_rows_total == 0,
            "invented_metrics_zero": not invented_ids,
            "arithmetic_reconciliation_passed_or_na": (
                arithmetic_applicable_total == 0
                or arithmetic_passed_total == arithmetic_applicable_total
            ),
        }
        receipt = {
            "schema_version": CHECKSUM_SCHEMA_VERSION,
            "status": "passed" if all(checks.values()) else "failed",
            "checks": checks,
            "metrics_total": len(expected),
            "metrics_passed_total": metrics_passed_total,
            "semantic_visual_table_metrics_total": sum(
                item.semantic_visual_table_derived for item in expected
            ),
            "semantic_visual_table_metrics_passed_total": (
                semantic_visual_passed_total
            ),
            "duplicate_rows_total": duplicate_rows_total,
            "invented_metrics_total": len(invented_ids),
            "arithmetic_reconciliation_applicable_total": (
                arithmetic_applicable_total
            ),
            "arithmetic_reconciliation_passed_total": (
                arithmetic_passed_total
            ),
            "private_metric_results": results,
        }
        receipt["integrity_hash"] = sha256_json(receipt)
        return receipt

    def _compare_metric(
        self,
        *,
        contract: Gate2FinancialContextChecksumContract,
        expected: Gate2ChecksumExpectedMetric,
        rows: list[dict[str, str]],
    ) -> dict[str, Any]:
        row = rows[0] if len(rows) == 1 else {}
        expected_value = Decimal(expected.normalized_value)
        amount_match = expected_value in _decimal_candidates(
            row.get("value", "")
        )
        period_match = _period_match(
            actual=row.get("period", ""),
            expected=expected.period_literals,
        )
        source_binding_match = all(
            (
                row.get("context_entry_id") == expected.context_entry_id,
                row.get("source_scope_ref") == expected.source_scope_ref,
                (
                    not expected.source_value_ref
                    or row.get("source_value_ref")
                    == expected.source_value_ref
                ),
                row.get("page_ref") == expected.page_ref,
                _gate2_binding_contains_value(
                    context=contract.financial_context,
                    expected=expected,
                    source_value_ref=row.get("source_value_ref", ""),
                ),
            )
        )
        arithmetic = _arithmetic_reconciliation(
            context=contract.financial_context,
            expected=expected,
            answer_amount_match=amount_match,
        )
        checks = {
            "exactly_one_row": len(rows) == 1,
            "metric_identity_match": (
                _normalize_text(row.get("source_label"))
                == _normalize_text(expected.source_label)
            ),
            "amount_match": amount_match,
            "currency_match": (
                _normalize_text(row.get("currency"))
                == _normalize_text(expected.currency)
            ),
            "unit_match": (
                _normalize_text(row.get("unit"))
                == _normalize_text(expected.unit)
            ),
            "sign_match": (
                _normalize_text(row.get("sign"))
                == _normalize_text(expected.sign)
            ),
            "period_match": period_match,
            "source_binding_match": source_binding_match,
        }
        return {
            "metric_id": expected.metric_id,
            **checks,
            "semantic_visual_table_derived": (
                expected.semantic_visual_table_derived
            ),
            "arithmetic_reconciliation": arithmetic,
            "passed": all(checks.values()),
            "private_expected_metric": asdict(expected),
            "private_answer_row": row,
        }


def safe_checksum_receipt(receipt: dict[str, Any]) -> dict[str, Any]:
    safe = {
        key: copy.deepcopy(value)
        for key, value in receipt.items()
        if key not in {"private_metric_results", "integrity_hash"}
    }
    safe["private_evidence_hash"] = receipt["integrity_hash"]
    safe["integrity_hash"] = sha256_json(safe)
    return safe


def _validate_model_package_isolation(package: dict[str, Any]) -> None:
    if set(package) != {
        "checksum_schema_version",
        "requested_metrics",
        "financial_context",
    }:
        _fail("financial_context_checksum_model_package_shape_invalid")
    context = package["financial_context"]
    if context.get("schema_version") != FINANCIAL_CONTEXT_SCHEMA_VERSION:
        _fail("financial_context_checksum_context_schema_invalid")
    if _forbidden_model_key_count(package):
        _fail("financial_context_checksum_forbidden_model_context")


def _forbidden_model_key_count(value: Any) -> int:
    if isinstance(value, dict):
        return sum(
            _normalize_text(key) in _FORBIDDEN_MODEL_KEYS
            for key in value
        ) + sum(_forbidden_model_key_count(child) for child in value.values())
    if isinstance(value, list):
        return sum(_forbidden_model_key_count(child) for child in value)
    return 0


def _gate2_binding_contains_value(
    *,
    context: dict[str, Any],
    expected: Gate2ChecksumExpectedMetric,
    source_value_ref: str | None = None,
) -> bool:
    for entry in context["entries"]:
        if (
            entry["context_entry_id"] != expected.context_entry_id
            or entry["source_scope_ref"] != expected.source_scope_ref
        ):
            continue
        interpretation = entry["interpretation_representation"]
        if (
            expected.page_ref
            and expected.page_ref
            not in interpretation["source_location"]["page_refs"]
        ):
            return False
        required_ref = (
            expected.source_value_ref
            if expected.source_value_ref
            else str(source_value_ref or "")
        )
        if not required_ref:
            return False
        for value in interpretation["values"]:
            if value["source_value_ref"] != required_ref:
                continue
            return Decimal(expected.normalized_value) in _decimal_candidates(
                value["literal_value"]
            )
    return False


def _arithmetic_reconciliation(
    *,
    context: dict[str, Any],
    expected: Gate2ChecksumExpectedMetric,
    answer_amount_match: bool,
) -> dict[str, Any]:
    if not expected.arithmetic_operands:
        return {"applicable": False, "passed": False, "status": "not_applicable"}
    available = {
        number
        for entry in context["entries"]
        for value in entry["interpretation_representation"]["values"]
        for number in _decimal_candidates(value["literal_value"])
    }
    operands = tuple(Decimal(item) for item in expected.arithmetic_operands)
    printed = Decimal(expected.normalized_value)
    passed = (
        all(item in available for item in operands)
        and sum(operands) == printed
        and _gate2_expected_value_present(
            context=context,
            expected=expected,
        )
        and answer_amount_match
    )
    return {
        "applicable": True,
        "passed": passed,
        "status": "passed" if passed else "failed",
        "operands_total": len(operands),
        "operands_present_total": sum(item in available for item in operands),
        "printed_gate2_llm_match": (
            _gate2_expected_value_present(
                context=context,
                expected=expected,
            )
            and answer_amount_match
        ),
    }


def _gate2_expected_value_present(
    *,
    context: dict[str, Any],
    expected: Gate2ChecksumExpectedMetric,
) -> bool:
    entry = next(
        (
            item
            for item in context["entries"]
            if item["context_entry_id"] == expected.context_entry_id
            and item["source_scope_ref"] == expected.source_scope_ref
        ),
        None,
    )
    if entry is None:
        return False
    expected_value = Decimal(expected.normalized_value)
    return any(
        (
            not expected.source_value_ref
            or value["source_value_ref"] == expected.source_value_ref
        )
        and expected_value in _decimal_candidates(value["literal_value"])
        for value in entry["interpretation_representation"]["values"]
    )


def _period_match(*, actual: str, expected: tuple[str, ...]) -> bool:
    values = {_normalize_text(item) for item in expected if item}
    if not values:
        return not _normalize_text(actual)
    normalized = _normalize_text(actual)
    return any(item in normalized or normalized in item for item in values)


def _normalize_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().casefold()


def _decimal_candidates(text: str) -> set[Decimal]:
    result: set[Decimal] = set()
    for token in re.findall(
        r"(?<![A-Za-z0-9])\(?[-+]?[0-9][0-9\s\u00a0'’.,]*\)?(?![A-Za-z0-9])",
        text,
    ):
        value = token.strip()
        negative_parentheses = value.startswith("(") and value.endswith(")")
        value = re.sub(r"[\s\u00a0'’]", "", value.strip("()").strip())
        variants = {value}
        if "," in value and "." in value:
            decimal_separator = "," if value.rfind(",") > value.rfind(".") else "."
            thousands_separator = "." if decimal_separator == "," else ","
            variants = {
                value.replace(thousands_separator, "").replace(
                    decimal_separator, "."
                )
            }
        elif "," in value:
            variants = {value.replace(",", "."), value.replace(",", "")}
        elif "." in value:
            variants = {value, value.replace(".", "")}
        for variant in variants:
            try:
                number = Decimal(variant)
            except InvalidOperation:
                continue
            result.add(-abs(number) if negative_parentheses else number)
    return result


def _fail(code: str) -> None:
    raise Gate2FinancialContextChecksumError(code)
