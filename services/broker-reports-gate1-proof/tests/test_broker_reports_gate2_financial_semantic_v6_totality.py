from __future__ import annotations

import copy
import json
import sys
from dataclasses import replace
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
from broker_reports_gate1.gate2_financial_evidence_materialization_contracts import (  # noqa: E402,E501
    sha256_json,
)
from broker_reports_gate1.gate2_financial_semantic_v6_bundle import (  # noqa: E402
    Gate2FinancialEvidenceBundleFactory,
)
from broker_reports_gate1.gate2_financial_semantic_v6_candidate_compiler import (  # noqa: E402,E501
    Gate2FinancialCandidateCompilerFactory,
)
from broker_reports_gate1.gate2_financial_semantic_v6_choice import (  # noqa: E402,E501
    Gate2FinancialSemanticV6ChoiceContractFactory,
)
from broker_reports_gate1.gate2_financial_semantic_v6_expansion import (  # noqa: E402,E501
    Gate2FinancialSemanticV6DecisionExpansionFactory,
)
from broker_reports_gate1.gate2_financial_semantic_v6_packet import (  # noqa: E402,E501
    Gate2FinancialSemanticV6PacketFactory,
)
from broker_reports_gate1.gate2_financial_semantic_v6_totality import (  # noqa: E402,E501
    FACTORY_REQUIRED,
    FORBIDDEN,
    TOTALITY_CHECKS,
    TOTAL_MATERIALIZATION_SCHEMA_VERSION,
    Gate2FinancialSemanticV6TotalityError,
    Gate2FinancialSemanticV6TotalMaterializerFactory,
    validate_financial_semantic_v6_total_materialization,
)
from broker_reports_gate1.gate2_successor_local_proof import (  # noqa: E402
    _fixture_package,
)


MANIFEST_PATH = ROOT / "benchmarks" / "gate2_financial_successor_v1" / "manifest.json"
MODULE_PATH = ROOT / "broker_reports_gate1" / "gate2_financial_semantic_v6_totality.py"


def _cases() -> dict[str, dict]:
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return {item["case_id"]: item for item in payload["cases"]}


def _case_count() -> int:
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return int(payload["case_count"])


def _authorities(
    case_id: str = "syn_successor_signed_literal",
):
    fixture = _fixture_package(copy.deepcopy(_cases()[case_id]))
    registry = Gate2FinancialEvidenceRegistryFactory().create()
    scope = (
        Gate2DeterministicFinancialScopeFromGate1V2Factory(registry=registry)
        .create(gate1_packages=(fixture.payload,))
        .scopes[0]
    )
    bundle = Gate2FinancialEvidenceBundleFactory().create(
        source_package=scope.source_package,
        gate1_packages=(fixture.payload,),
    )
    compilation = Gate2FinancialCandidateCompilerFactory(registry=registry).create(
        evidence_bundle=bundle,
        source_package=scope.source_package,
    )
    packet = Gate2FinancialSemanticV6PacketFactory(registry=registry).create(
        evidence_bundle=bundle,
        source_package=scope.source_package,
        compilation=compilation,
    )
    choice_contract = Gate2FinancialSemanticV6ChoiceContractFactory(
        registry=registry
    ).create(
        packet=packet,
        evidence_bundle=bundle,
        source_package=scope.source_package,
        compilation=compilation,
    )
    return {
        "registry": registry,
        "scope": scope,
        "bundle": bundle,
        "compilation": compilation,
        "packet": packet,
        "choice_contract": choice_contract,
    }


def _total(authorities, model_output):
    expansion = Gate2FinancialSemanticV6DecisionExpansionFactory(
        registry=authorities["registry"]
    ).create(
        model_output=model_output,
        choice_contract=authorities["choice_contract"],
        packet=authorities["packet"],
        evidence_bundle=authorities["bundle"],
        source_package=authorities["scope"].source_package,
        compilation=authorities["compilation"],
    )
    result = Gate2FinancialSemanticV6TotalMaterializerFactory(
        registry=authorities["registry"]
    ).create(
        expansion=expansion,
        model_output=model_output,
        choice_contract=authorities["choice_contract"],
        packet=authorities["packet"],
        evidence_bundle=authorities["bundle"],
        source_package=authorities["scope"].source_package,
        compilation=authorities["compilation"],
    )
    return expansion, result


def test_typed_expansion_always_materializes_with_all_structural_checks():
    authorities = _authorities()
    option = authorities["compilation"].typed_options[0]
    expansion, result = _total(
        authorities,
        {
            "disposition": "typed_input",
            "typed_option_id": option.typed_option_id,
        },
    )

    assert result.schema_version == TOTAL_MATERIALIZATION_SCHEMA_VERSION
    assert result.terminal_disposition == "typed_input"
    assert result.validated_but_unmaterializable is False
    assert result.materializer_totality_status == ("proven_for_expansion")
    assert result.totality_checks == TOTALITY_CHECKS
    assert len(result.canonical_artifact["typed_inputs"]) == 1
    assert result.canonical_artifact["unclassified_inputs"] == []
    terminal = result.canonical_artifact["typed_inputs"][0]
    assert terminal["input_type_id"] == option.input_type_id
    assert terminal["date_period"]
    assert terminal["currency_unit"]
    assert terminal["source_sign_policy"]
    assert terminal["identity_policy"]["identity_roles"]
    assert set(result.terminal_source_value_refs) == set(
        expansion.retained_source_value_refs
    )
    assert "Factory.create" in FACTORY_REQUIRED
    assert "must not implement a second materializer" in FORBIDDEN


def test_unclassified_materialization_has_exact_retention_and_ownership():
    authorities = _authorities("syn_successor_adjacent_equal")
    expansion, result = _total(
        authorities,
        {
            "disposition": "unclassified_financial_input",
            "reason_code": "ambiguous_registry_type",
        },
    )

    assert result.terminal_disposition == ("unclassified_financial_input")
    assert result.canonical_artifact["typed_inputs"] == []
    assert len(result.canonical_artifact["unclassified_inputs"]) == 1
    terminal = result.canonical_artifact["unclassified_inputs"][0]
    refs = {item["source_value_ref"] for item in terminal["source_values"]}
    assert refs == set(authorities["bundle"].retention_set)
    assert len(refs) == len(terminal["source_values"])
    assert set(result.terminal_source_value_refs) == refs
    assert set(expansion.retained_source_value_refs) == refs
    assert terminal["typed_input_published"] is False
    assert terminal["source_ownership"] == {
        "normalization_run_ref": (
            authorities["scope"].source_package.normalization_run_ref
        ),
        "document_ref": (authorities["scope"].source_package.document_ref),
        "source_package_ref": (authorities["scope"].source_package.package_ref),
        "source_scope_ref": (authorities["scope"].source_package.source_scope_ref),
    }


def test_every_sealed_provider_schema_choice_is_materializable():
    choices_total = 0
    typed_choices_total = 0
    for case_id in _cases():
        authorities = _authorities(case_id)
        model_outputs = [
            {
                "disposition": "typed_input",
                "typed_option_id": option.typed_option_id,
            }
            for option in authorities["compilation"].typed_options
        ]
        typed_choices_total += len(model_outputs)
        model_outputs.extend(
            {
                "disposition": "unclassified_financial_input",
                "reason_code": reason_code,
            }
            for reason_code in authorities["choice_contract"].unclassified_reason_codes
        )
        for model_output in model_outputs:
            _, result = _total(authorities, model_output)
            choices_total += 1
            assert result.validated_but_unmaterializable is False
            assert result.materializer_totality_status == ("proven_for_expansion")
            assert (
                result.canonical_artifact["terminal_disposition"]
                == (model_output["disposition"])
            )
    assert len(_cases()) == _case_count()
    assert choices_total >= 2 * _case_count()
    assert typed_choices_total > 0


def test_signed_literal_pack_registry_and_artifact_integrity_are_exact():
    authorities = _authorities()
    option = authorities["compilation"].typed_options[0]
    _, result = _total(
        authorities,
        {
            "disposition": "typed_input",
            "typed_option_id": option.typed_option_id,
        },
    )
    artifact = result.canonical_artifact
    terminal = artifact["typed_inputs"][0]
    amount_ref = next(
        item.source_value_ref
        for item in authorities["bundle"].source_values
        if item.value_type == "source_decimal"
    )

    assert artifact["semantic_pack"]["integrity_sha256"] == (
        option.materializability_receipt.semantic_pack_integrity_sha256
    )
    assert artifact["registry"]["registry_hash"] == (
        authorities["registry"].registry_hash
    )
    assert artifact["source_package"]["integrity_hash"] == (
        authorities["scope"].source_package.integrity_hash
    )
    assert terminal["source_sign_by_value_ref"][amount_ref] == ("negative")
    assert artifact["integrity_hash"] == sha256_json(
        {key: value for key, value in artifact.items() if key != "integrity_hash"}
    )
    assert result.canonical_artifact_hash == sha256_json(artifact)


def test_totality_result_is_deterministic_safe_and_tamper_evident():
    authorities = _authorities()
    model_output = {
        "disposition": "unclassified_financial_input",
        "reason_code": "no_registry_type",
    }
    expansion, first = _total(authorities, model_output)
    _, second = _total(authorities, model_output)

    assert first == second
    safe = json.dumps(first.safe_summary(), sort_keys=True)
    assert all(ref not in safe for ref in first.terminal_source_value_refs)
    assert first.safe_summary()["ownership_gaps_total"] == 0
    assert first.safe_summary()["date_period_failures_after_model_total"] == 0

    tampered = replace(first, canonical_artifact_hash="0" * 64)
    with pytest.raises(
        Gate2FinancialSemanticV6TotalityError,
        match=("financial_semantic_v6_total_materialization_integrity_invalid"),
    ):
        validate_financial_semantic_v6_total_materialization(
            result=tampered,
            expansion=expansion,
            model_output=model_output,
            choice_contract=authorities["choice_contract"],
            packet=authorities["packet"],
            evidence_bundle=authorities["bundle"],
            source_package=authorities["scope"].source_package,
            compilation=authorities["compilation"],
            registry=authorities["registry"],
        )


def test_totality_module_delegates_to_canonical_materializer_without_repair():
    source = MODULE_PATH.read_text(encoding="utf-8")

    assert "Gate2FinancialEvidenceMaterializerFactory" in source
    assert "def _materialize_typed" not in source
    assert "def _materialize_unclassified" not in source
    assert "typed_to_unclassified" not in source
    assert "fallback" not in source.casefold()
    assert "retry" not in source.casefold()
