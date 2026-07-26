from __future__ import annotations

import ast
import copy
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from broker_reports_gate1.gate2_deterministic_financial_scopes import (  # noqa: E402
    Gate2DeterministicFinancialScopeFromGate1V2Factory,
)
from broker_reports_gate1.gate2_financial_evidence_registry import (  # noqa: E402
    Gate2FinancialEvidenceRegistryFactory,
)
from broker_reports_gate1.gate2_financial_evidence_source_context import (  # noqa: E402
    FACTORY_REQUIRED,
    FORBIDDEN,
    MAX_VISIBLE_CONTEXT_CHARS,
    SOURCE_CONTEXT_POLICY_VERSION,
    SOURCE_CONTEXT_SCHEMA_VERSION,
    Gate2FinancialEvidenceSourceContext,
    Gate2FinancialEvidenceSourceContextError,
    Gate2FinancialEvidenceSourceContextFactory,
    validate_financial_evidence_source_context,
)
from broker_reports_gate1.gate2_financial_evidence_successor import (  # noqa: E402
    FORBIDDEN_MODEL_INPUT_FIELDS,
    SUCCESSOR_MODEL_INPUT_SCHEMA_VERSION,
    SUCCESSOR_MODEL_INPUT_SCHEMA_VERSION_V2,
    Gate2FinancialEvidenceSuccessorConfig,
    Gate2FinancialEvidenceSuccessorError,
    Gate2FinancialEvidenceSuccessorRunnerFactory,
    validate_financial_evidence_successor_model_input_v2,
)
from broker_reports_gate1.gate2_successor_local_proof import (  # noqa: E402
    _fixture_package,
)


MANIFEST_PATH = (
    ROOT
    / "benchmarks"
    / "gate2_financial_successor_v1"
    / "manifest.json"
)
MODULE_PATH = (
    ROOT
    / "broker_reports_gate1"
    / "gate2_financial_evidence_source_context.py"
)
MODEL_ID = "gpt-5.4-nano-2026-03-17"
PROVIDER_PROFILE_ID = "openai_gpt"


class _NeverModelClient:
    calls = 0

    async def extract(self, **kwargs):
        self.calls += 1
        raise AssertionError("provider_call_forbidden")


def _cases() -> dict[str, dict]:
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return {item["case_id"]: item for item in payload["cases"]}


def _scope_context(case_id: str):
    registry = Gate2FinancialEvidenceRegistryFactory().create()
    fixture = _fixture_package(copy.deepcopy(_cases()[case_id]))
    scope = Gate2DeterministicFinancialScopeFromGate1V2Factory(
        registry=registry
    ).create(gate1_packages=(fixture.payload,)).scopes[0]
    context = Gate2FinancialEvidenceSourceContextFactory().create(
        source_scope_ref=scope.source_package.source_scope_ref,
        source_values=scope.source_package.source_values,
        candidates=scope.decision_contract.package.candidates,
        gate1_packages=(fixture.payload,),
    )
    return scope, context, registry, fixture


def _runner(*, registry, version):
    return Gate2FinancialEvidenceSuccessorRunnerFactory(
        registry=registry,
        model_client=_NeverModelClient(),
        config=Gate2FinancialEvidenceSuccessorConfig(
            model_id=MODEL_ID,
            provider_profile_id=PROVIDER_PROFILE_ID,
            model_input_schema_version=version,
        ),
    ).create()


def _walk_dicts(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_dicts(child)


def test_context_v2_groups_authoritative_values_and_visible_meaning():
    scope, context, _, fixture = _scope_context(
        "syn_successor_signed_literal"
    )

    groups = context.provider_groups()
    assert [item["group_kind"] for item in groups] == [
        "table_row",
        "deterministic_reference",
    ]
    row_group = groups[0]
    assert row_group["row_role"] == "fact_candidate"
    assert row_group["section_role"] is None
    observed = {
        item["source_value_ref"]: item
        for item in row_group["values"]
    }
    for source_value_ref, literal in fixture.selected_literals.items():
        assert observed[source_value_ref]["literal_value"] == literal
    label_ref = fixture.selected_value_refs["label"]
    amount_ref = fixture.selected_value_refs["amount"]
    assert observed[label_ref]["column_meaning"] == "label"
    assert observed[amount_ref]["column_meaning"] == "amount"
    assert all(
        item["literal_value"] is None
        for item in groups[1]["values"]
    )
    assert context.source_values_total == len(
        scope.source_package.source_values
    )


def test_provider_projection_has_no_locator_graph_or_expected_answer():
    scope, context, registry, _ = _scope_context(
        "syn_successor_multiple_hypotheses"
    )
    runner = _runner(
        registry=registry,
        version=SUCCESSOR_MODEL_INPUT_SCHEMA_VERSION_V2,
    )

    model_input = runner.model_input(
        scope=scope,
        source_context=context,
    )

    assert set(model_input) == {"eligible_types", "source_groups"}
    assert [
        item["input_type_id"] for item in model_input["eligible_types"]
    ] == [
        "cash_balance_snapshot_v1",
        "printed_financial_metric_v1",
    ]
    assert len(model_input["source_groups"]) == 2
    assert not {
        key
        for item in _walk_dicts(model_input)
        for key in item
        if key in FORBIDDEN_MODEL_INPUT_FIELDS
    }
    rendered = json.dumps(model_input, ensure_ascii=False)
    assert "unclassified_financial_input" not in rendered
    assert "typed_input" not in rendered


def test_context_safe_summary_contains_no_literals_or_binding_refs():
    _, context, _, fixture = _scope_context(
        "syn_successor_currency_date"
    )

    summary = context.safe_summary()
    rendered = json.dumps(summary, sort_keys=True)
    assert summary["schema_version"] == SOURCE_CONTEXT_SCHEMA_VERSION
    assert summary["policy_version"] == SOURCE_CONTEXT_POLICY_VERSION
    assert summary["contains_source_literals"] is False
    assert summary["contains_source_value_refs"] is False
    assert summary["provider_calls_total"] == 0
    assert all(
        literal not in rendered
        for literal in fixture.selected_literals.values()
    )
    assert all(
        ref not in rendered for ref in fixture.selected_literals
    )


def test_context_and_model_input_v2_are_deterministic():
    scope, context, registry, fixture = _scope_context(
        "syn_successor_forbidden_neighbour"
    )
    repeated = Gate2FinancialEvidenceSourceContextFactory().create(
        source_scope_ref=scope.source_package.source_scope_ref,
        source_values=scope.source_package.source_values,
        candidates=scope.decision_contract.package.candidates,
        gate1_packages=(copy.deepcopy(fixture.payload),),
    )
    runner = _runner(
        registry=registry,
        version=SUCCESSOR_MODEL_INPUT_SCHEMA_VERSION_V2,
    )

    assert context.to_private_dict() == repeated.to_private_dict()
    assert runner.model_input(
        scope=scope,
        source_context=context,
    ) == runner.model_input(
        scope=scope,
        source_context=repeated,
    )


def test_v2_requires_context_and_v1_rejects_context_injection():
    scope, context, registry, _ = _scope_context(
        "syn_successor_signed_literal"
    )
    v2 = _runner(
        registry=registry,
        version=SUCCESSOR_MODEL_INPUT_SCHEMA_VERSION_V2,
    )
    v1 = _runner(
        registry=registry,
        version=SUCCESSOR_MODEL_INPUT_SCHEMA_VERSION,
    )

    with pytest.raises(
        Gate2FinancialEvidenceSuccessorError,
        match="financial_evidence_successor_v2_context_required",
    ):
        v2.model_input(scope=scope)
    with pytest.raises(
        Gate2FinancialEvidenceSuccessorError,
        match="financial_evidence_successor_v1_context_forbidden",
    ):
        v1.model_input(scope=scope, source_context=context)
    assert set(v1.model_input(scope=scope)) == {
        "eligible_types",
        "source_values",
    }


def test_v2_context_does_not_change_prompt_identity():
    _, _, registry, _ = _scope_context(
        "syn_successor_signed_literal"
    )
    v1 = _runner(
        registry=registry,
        version=SUCCESSOR_MODEL_INPUT_SCHEMA_VERSION,
    )
    v2 = _runner(
        registry=registry,
        version=SUCCESSOR_MODEL_INPUT_SCHEMA_VERSION_V2,
    )

    assert v1.prompt == v2.prompt


def test_tampered_context_integrity_and_system_field_fail_closed():
    scope, context, registry, _ = _scope_context(
        "syn_successor_signed_literal"
    )
    groups = context.provider_groups()
    groups[0]["values"][0]["literal_value"] = "tampered"
    tampered = Gate2FinancialEvidenceSourceContext(
        source_scope_ref=context.source_scope_ref,
        groups=tuple(groups),
        source_values_total=context.source_values_total,
        visible_source_values_total=(
            context.visible_source_values_total
        ),
        deterministic_reference_values_total=(
            context.deterministic_reference_values_total
        ),
        integrity_hash=context.integrity_hash,
    )
    with pytest.raises(
        Gate2FinancialEvidenceSourceContextError,
        match="financial_source_context_integrity_invalid",
    ):
        validate_financial_evidence_source_context(
            context=tampered,
            source_scope_ref=scope.source_package.source_scope_ref,
            source_values=scope.source_package.source_values,
            candidates=scope.decision_contract.package.candidates,
        )

    runner = _runner(
        registry=registry,
        version=SUCCESSOR_MODEL_INPUT_SCHEMA_VERSION_V2,
    )
    model_input = runner.model_input(
        scope=scope,
        source_context=context,
    )
    model_input["source_groups"][0]["row_ref"] = "forbidden"
    with pytest.raises(
        Gate2FinancialEvidenceSuccessorError,
        match="financial_evidence_successor_model_system_field_forbidden",
    ):
        validate_financial_evidence_successor_model_input_v2(
            model_input=model_input,
            scope=scope,
            registry=registry,
            source_context=context,
        )


def test_context_rejects_truncation_and_literal_authority_drift():
    scope, _, _, fixture = _scope_context(
        "syn_successor_signed_literal"
    )
    oversized = copy.deepcopy(fixture.payload)
    oversized["source_unit"]["model_source_projection"]["rows"][0][
        "cells"
    ][0]["header_label"] = "x" * (MAX_VISIBLE_CONTEXT_CHARS + 1)
    with pytest.raises(
        Gate2FinancialEvidenceSourceContextError,
        match="financial_source_context_visible_context_limit_exceeded",
    ):
        Gate2FinancialEvidenceSourceContextFactory().create(
            source_scope_ref=scope.source_package.source_scope_ref,
            source_values=scope.source_package.source_values,
            candidates=scope.decision_contract.package.candidates,
            gate1_packages=(oversized,),
        )

    drifted = copy.deepcopy(fixture.payload)
    drifted["source_unit"]["model_source_projection"]["rows"][0][
        "cells"
    ][0]["value"] = "changed after scope"
    with pytest.raises(
        Gate2FinancialEvidenceSourceContextError,
        match="financial_source_context_literal_authority_mismatch",
    ):
        Gate2FinancialEvidenceSourceContextFactory().create(
            source_scope_ref=scope.source_package.source_scope_ref,
            source_values=scope.source_package.source_values,
            candidates=scope.decision_contract.package.candidates,
            gate1_packages=(drifted,),
        )


def test_context_factory_has_no_provider_or_semantic_type_authority():
    assert "only bounded" in FACTORY_REQUIRED
    assert "must not expose document" in FORBIDDEN
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    imported_modules = {
        str(node.module or "")
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    assert not {
        module
        for module in imported_modules
        if "provider" in module
        or "model_client" in module
        or "production_runtime" in module
        or "financial_evidence_registry" in module
    }
