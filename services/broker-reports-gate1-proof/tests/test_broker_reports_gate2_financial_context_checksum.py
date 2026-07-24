from __future__ import annotations

import ast
import asyncio
import copy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from broker_reports_gate1.gate2_financial_context import (  # noqa: E402
    Gate2FinancialContextProjectionFactory,
)
from broker_reports_gate1.gate2_financial_context_checksum import (  # noqa: E402
    CHECKSUM_SCHEMA_VERSION,
    Gate2ChecksumExpectedMetric,
    Gate2ChecksumMetricRequest,
    Gate2FinancialContextChecksumComparatorFactory,
    Gate2FinancialContextChecksumContractFactory,
    Gate2FinancialContextChecksumError,
    Gate2FinancialContextChecksumRunnerFactory,
    safe_checksum_receipt,
)
from broker_reports_gate1.gate2_financial_evidence_catalog import (  # noqa: E402
    SUPPORTED_SOURCE_FAMILIES,
)
from broker_reports_gate1.gate2_financial_evidence_decision import (  # noqa: E402
    FinancialEvidenceDecisionPackage,
    FinancialEvidenceValueCandidate,
    Gate2FinancialEvidenceDecisionContractFactory,
)
from broker_reports_gate1.gate2_financial_evidence_materialization import (  # noqa: E402
    FinancialEvidenceAuthoritativeSourceValue,
    FinancialEvidenceExecutionMetadata,
    FinancialEvidenceSourceLineage,
    Gate2FinancialEvidenceMaterializerFactory,
    Gate2FinancialEvidenceSourcePackageFactory,
    Gate2FinancialEvidenceValidatedDecisionFactory,
)
from broker_reports_gate1.gate2_financial_evidence_registry import (  # noqa: E402
    Gate2FinancialEvidenceRegistryFactory,
)
from broker_reports_gate1.gate2_model_contracts import (  # noqa: E402
    Gate2StructuredModelResult,
)
from broker_reports_gate1.gate2_model_requests import (  # noqa: E402
    FINANCIAL_CONTEXT_CHECKSUM_REQUEST_PROFILE,
    Gate2OpenWebUIRequestBuilder,
)


MODULE_PATH = (
    ROOT
    / "broker_reports_gate1"
    / "gate2_financial_context_checksum.py"
)


class _FakeModelClient:
    def __init__(self, content):
        self.content = content
        self.calls = []

    async def extract(self, **kwargs):
        self.calls.append(kwargs)
        return Gate2StructuredModelResult(content=copy.deepcopy(self.content))


def _registry():
    return Gate2FinancialEvidenceRegistryFactory().create()


def _case(suffix: str):
    definitions = (
        ("amount", "source_decimal", "-120.50", ("amount",)),
        ("date", "source_date", "2025-12-31", ("as_of_date",)),
        ("scope", "source_reference", "Statement", ("statement_scope",)),
        (
            "printed-label",
            "source_reference",
            "Printed total",
            ("printed_label_evidence_ref",),
        ),
        ("period", "source_period", "2025 Q4", ("period",)),
        ("currency", "source_currency", "RUB", ("currency",)),
        ("label", "source_text", f"Synthetic metric {suffix}", ("source_label",)),
    )
    values = tuple(
        FinancialEvidenceAuthoritativeSourceValue(
            source_value_ref=f"value:{name}:{suffix}",
            source_ref=f"source:{name}:{suffix}",
            value_type=value_type,
            literal_value=literal_value,
            source_evidence_refs=(f"evidence:{suffix}",),
            lineage=FinancialEvidenceSourceLineage(
                document_ref="document:synthetic",
                page_ref=f"page:{suffix}",
                table_ref=f"table:{suffix}",
                row_ref=f"row:{suffix}:{index}",
                cell_ref=f"cell:{suffix}:{index}",
            ),
        )
        for index, (name, value_type, literal_value, _) in enumerate(
            definitions, start=1
        )
    )
    package = Gate2FinancialEvidenceSourcePackageFactory(
        package_ref=f"package:{suffix}",
        normalization_run_ref="normalization:synthetic",
        document_ref="document:synthetic",
        source_scope_ref=f"scope:{suffix}",
        source_family_id=SUPPORTED_SOURCE_FAMILIES[0],
        source_values=values,
        source_evidence_refs=(f"evidence:{suffix}",),
        completeness="complete",
    ).create()
    candidates = tuple(
        FinancialEvidenceValueCandidate(
            source_value_ref=f"value:{name}:{suffix}",
            source_ref=f"source:{name}:{suffix}",
            value_type=value_type,
            allowed_roles=roles,
        )
        for name, value_type, _, roles in definitions
    )
    decision_contract = Gate2FinancialEvidenceDecisionContractFactory(
        registry=_registry(),
        package=FinancialEvidenceDecisionPackage(
            source_scope_ref=package.source_scope_ref,
            source_family_id=package.source_family_id,
            candidates=candidates,
        ),
    ).create()
    decision = {
        "decision": {
            "disposition": "typed_input",
            "input_type_id": "printed_financial_metric_v1",
            "value_bindings": {
                "amount": f"value:amount:{suffix}",
                "printed_label_evidence_ref": f"value:printed-label:{suffix}",
                "statement_scope": f"value:scope:{suffix}",
                "as_of_date": None,
                "currency": f"value:currency:{suffix}",
                "period": f"value:period:{suffix}",
                "source_label": f"value:label:{suffix}",
                "unit": None,
            },
            "reason_code": "typed_supported",
        }
    }
    validated = Gate2FinancialEvidenceValidatedDecisionFactory(
        contract=decision_contract
    ).create(decision)
    artifact = Gate2FinancialEvidenceMaterializerFactory(
        registry=_registry(),
        source_package=package,
        execution_metadata=FinancialEvidenceExecutionMetadata(
            execution_ref=f"execution:{suffix}",
            decision_validation_ref=f"validation:{suffix}",
        ),
    ).create().materialize(validated_decision=validated)
    return artifact, package


def _contract():
    cases = tuple(_case(suffix) for suffix in ("a", "b", "c"))
    context = Gate2FinancialContextProjectionFactory(
        registry=_registry()
    ).create(
        materialized_artifacts=tuple(item[0] for item in cases),
        source_packages=tuple(item[1] for item in cases),
    )
    requests = tuple(
        Gate2ChecksumMetricRequest(
            metric_id=f"metric:{suffix}",
            source_label=f"Synthetic metric {suffix}",
        )
        for suffix in ("a", "b", "c")
    )
    contract = Gate2FinancialContextChecksumContractFactory(
        registry=_registry()
    ).create(financial_context=context, metric_requests=requests)
    return contract


def _rows(contract):
    entries = {
        item["source_scope_ref"]: item
        for item in contract.financial_context["entries"]
    }
    return [
        {
            "metric_id": f"metric:{suffix}",
            "source_label": f"Synthetic metric {suffix}",
            "value": "-120.50",
            "currency": "RUB",
            "unit": "",
            "sign": "negative",
            "period": "2025 Q4",
            "context_entry_id": entries[f"scope:{suffix}"]["context_entry_id"],
            "source_scope_ref": f"scope:{suffix}",
            "source_value_ref": f"value:amount:{suffix}",
            "page_ref": f"page:{suffix}",
        }
        for suffix in ("a", "b", "c")
    ]


def _expected(contract):
    rows = _rows(contract)
    return tuple(
        Gate2ChecksumExpectedMetric(
            metric_id=row["metric_id"],
            source_label=row["source_label"],
            normalized_value="-120.50",
            currency="RUB",
            unit="",
            sign="negative",
            period_literals=("2025 Q4", "2025-Q4"),
            context_entry_id=row["context_entry_id"],
            source_scope_ref=row["source_scope_ref"],
            source_value_ref=row["source_value_ref"],
            page_ref=row["page_ref"],
            semantic_visual_table_derived=True,
            arithmetic_operands=("-120.50",) if index == 0 else (),
        )
        for index, row in enumerate(rows)
    )


def test_contract_projects_only_gate2_context_and_requested_identity():
    contract = _contract()
    package = contract.model_package()["llm_context_package"]

    assert set(package) == {
        "checksum_schema_version",
        "requested_metrics",
        "financial_context",
    }
    assert package["checksum_schema_version"] == CHECKSUM_SCHEMA_VERSION
    assert len(package["requested_metrics"]) == 3
    assert "expected" not in repr(package).casefold()
    assert "semantic_table" not in repr(package).casefold()
    assert "document_memory" not in repr(package).casefold()
    assert "gate3" not in repr(package).casefold()
    assert "tax_skill" not in repr(package).casefold()


def test_contract_requires_three_unique_metric_requests():
    contract = _contract()
    with pytest.raises(Gate2FinancialContextChecksumError) as rejected:
        Gate2FinancialContextChecksumContractFactory(
            registry=_registry()
        ).create(
            financial_context=contract.financial_context,
            metric_requests=contract.metric_requests[:2],
        )
    assert rejected.value.code == (
        "financial_context_checksum_metric_count_invalid"
    )


def test_openai_schema_is_strict_bounded_and_parse_is_fail_closed():
    contract = _contract()
    response_format = contract.openai_response_format()
    schema = response_format["json_schema"]["schema"]

    assert response_format["json_schema"]["strict"] is True
    assert schema["properties"]["metrics"]["minItems"] == 3
    assert schema["properties"]["metrics"]["maxItems"] == 3
    assert "uniqueItems" not in repr(schema)
    assert contract.parse_model_output({"metrics": _rows(contract)})

    invalid = _rows(contract)
    invalid[0]["unexpected"] = "forbidden"
    with pytest.raises(Gate2FinancialContextChecksumError) as rejected:
        contract.parse_model_output({"metrics": invalid})
    assert rejected.value.code == (
        "financial_context_checksum_metric_shape_invalid"
    )


def test_request_builder_embeds_checksum_package_without_rag():
    contract = _contract()
    prompt = type(
        "Prompt",
        (),
        {
            "content": "before {{financial_context_checksum_package_json}} after",
            "prompt_ref": "prompt:checksum",
            "hash": "a" * 64,
        },
    )()
    request = Gate2OpenWebUIRequestBuilder(
        request_profile=FINANCIAL_CONTEXT_CHECKSUM_REQUEST_PROFILE
    ).build(
        prompt=prompt,
        package=contract.model_package(),
        model_id="gpt-test",
        response_format=contract.openai_response_format(),
    )

    assert request["metadata"]["broker_reports_gate2"][
        "financial_context_checksum"
    ] is True
    assert request["metadata"]["broker_reports_gate2"][
        "knowledge_rag_used"
    ] is False
    assert request["metadata"]["broker_reports_gate2"][
        "vectorization_performed"
    ] is False
    assert "{{financial_context_checksum_package_json}}" not in (
        request["messages"][0]["content"]
    )


def test_runner_uses_model_boundary_once_without_fallback_or_repair():
    contract = _contract()
    client = _FakeModelClient({"metrics": _rows(contract)})
    runner = Gate2FinancialContextChecksumRunnerFactory(
        model_client=client,
        model_id="gpt-test",
        provider_profile_id="openai",
    ).create()

    result = asyncio.run(runner.run(contract=contract))

    assert len(client.calls) == 1
    assert result["fallback_used"] is False
    assert result["repair_attempt_count"] == 0
    assert len(result["rows"]) == 3


def test_comparator_passes_identity_dimensions_binding_and_reconciliation():
    contract = _contract()
    receipt = Gate2FinancialContextChecksumComparatorFactory().create(
        contract=contract,
        expected_metrics=_expected(contract),
        answer_rows=_rows(contract),
    )
    safe = safe_checksum_receipt(receipt)

    assert receipt["status"] == "passed"
    assert receipt["metrics_passed_total"] == 3
    assert receipt["duplicate_rows_total"] == 0
    assert receipt["invented_metrics_total"] == 0
    assert receipt["arithmetic_reconciliation_applicable_total"] == 1
    assert receipt["arithmetic_reconciliation_passed_total"] == 1
    assert all(receipt["checks"].values())
    assert "private_metric_results" not in safe
    assert safe["status"] == "passed"


def test_comparator_detects_duplicate_invented_and_wrong_binding():
    contract = _contract()
    rows = _rows(contract)
    rows[0]["source_value_ref"] = "value:wrong"
    rows.append({**rows[1]})
    rows.append({**rows[2], "metric_id": "metric:invented"})
    receipt = Gate2FinancialContextChecksumComparatorFactory().create(
        contract=contract,
        expected_metrics=_expected(contract),
        answer_rows=rows,
    )

    assert receipt["status"] == "failed"
    assert receipt["duplicate_rows_total"] == 1
    assert receipt["invented_metrics_total"] == 1
    assert receipt["checks"]["source_binding_3_of_3"] is False
    assert receipt["checks"]["duplicate_rows_zero"] is False
    assert receipt["checks"]["invented_metrics_zero"] is False


def test_checksum_module_has_no_direct_provider_or_gate1_import_bypass():
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    calls = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
    }

    assert not any(name.startswith("requests") for name in imports)
    assert not any("gate1" in name for name in imports)
    assert "post" not in calls
