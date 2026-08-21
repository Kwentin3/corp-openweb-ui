from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest


SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SERVICE_ROOT.parents[1]
sys.path.insert(0, str(SERVICE_ROOT))

from broker_reports_gate1.artifact_lifecycle import (  # noqa: E402
    lifecycle_for_visibility,
)
from broker_reports_gate1.artifact_models import (  # noqa: E402
    ArtifactAccessContext,
    ArtifactRecord,
)
from broker_reports_gate1.artifact_resolver import ArtifactResolver  # noqa: E402
from broker_reports_gate1.artifact_store import (  # noqa: E402
    ArtifactStoreConfig,
    ArtifactStoreFactory,
)
from broker_reports_gate1.artifact_retention import (  # noqa: E402
    build_retention_policy,
)
from broker_reports_gate1.gate2_financial_evidence_registry import (  # noqa: E402
    Gate2FinancialEvidenceRegistryFactory,
)
from broker_reports_gate1.gate2_financial_semantic_v6_choice import (  # noqa: E402
    Gate2FinancialSemanticV6ChoiceError,
)
from broker_reports_gate1.gate2_financial_semantic_v6_evidence import (  # noqa: E402
    Gate2FinancialSemanticV6DecisionEvidenceError,
    Gate2FinancialSemanticV6DecisionEvidenceFactory,
    replay_financial_semantic_v6_type_first_proof,
)
from broker_reports_gate1.gate2_same_source_type_first_proof import (  # noqa: E402
    Gate2SameSourceTypeFirstProof,
    false_singleton_comparator,
    safe_trace_pack,
)


FIXTURE_PATH = (
    SERVICE_ROOT
    / "tests"
    / "fixtures"
    / "kt2_same_source_type_first_corpus.safe.json"
)
BINDING_PATH = (
    SERVICE_ROOT
    / "tests"
    / "fixtures"
    / "kt2_same_source_type_first_binding.safe.json"
)
PROOF_BUILDER_PATH = (
    SERVICE_ROOT / "scripts" / "build_kt2_same_source_type_first_proof.py"
)
PROOF_MODULE = (
    SERVICE_ROOT
    / "broker_reports_gate1"
    / "gate2_same_source_type_first_proof.py"
)
PRODUCT_ROUTE = (
    SERVICE_ROOT / "broker_reports_gate1" / "gate2_domain_runtime.py"
)
FUNCTION_ROOTS = (
    SERVICE_ROOT / "openwebui_actions" / "broker_reports_gate1_pipe_bundled.py",
    SERVICE_ROOT
    / "openwebui_actions"
    / "broker_reports_gate2_source_fact_pipe_bundled.py",
    SERVICE_ROOT
    / "openwebui_actions"
    / "broker_reports_gate2_domain_source_fact_pipe_bundled.py",
)


@pytest.fixture(scope="module")
def corpus() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def authorities(corpus):
    registry = Gate2FinancialEvidenceRegistryFactory().create()
    proof = Gate2SameSourceTypeFirstProof(registry=registry)
    indexes = corpus["proof_bounded_source_unit_package_indexes"]
    packages = tuple(corpus["packages"][index] for index in indexes)
    prepared = proof.prepare(gate2_packages=packages)
    response = proof.response(
        prepared=prepared,
        plausible_types_by_unit={
            "u01": ("t01", "t02"),
            "u02": ("t02",),
            "u03": (),
        },
    )
    execution = proof.execute(
        prepared=prepared,
        simulated_response=response,
    )
    return registry, proof, packages, prepared, response, execution


def test_historical_private_binding_and_public_corpus_are_exact(corpus):
    binding = json.loads(BINDING_PATH.read_text(encoding="utf-8"))
    assert binding["public_fixture"]["real_gate2_packages_total"] == 1
    assert binding["public_fixture"]["real_source_units_total"] == 3
    assert all(
        item["structure_equal"] for item in binding["structure_comparison"]
    )
    assert corpus["full_real_package_structural_copy_index"] == 0
    assert corpus["proof_bounded_source_unit_package_indexes"] == [1, 2, 3]
    assert corpus["primary_input"]["factory"] == "Gate2TablePackageFactory"
    assert corpus["privacy"] == {
        "customer_values": False,
        "private_paths": False,
        "raw_provider_payloads": False,
        "raw_source_refs": False,
        "safe_placeholders_only": True,
        "synthetic_semantic_labels": True,
    }


def test_safe_trace_and_proof_receipt_are_byte_exact():
    completed = subprocess.run(
        [sys.executable, str(PROOF_BUILDER_PATH), "--check"],
        cwd=SERVICE_ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout) == {
        "mode": "check",
        "provider_calls_total": 0,
        "status": "passed",
        "traces_total": 4,
        "unaccounted_units_total": 0,
    }


def test_pack_backed_cards_prebound_options_and_model_boundary(authorities):
    _registry, _proof, _packages, prepared, _response, _execution = authorities
    cards = prepared.candidate.payload["type_cards"]
    assert len(cards) == 2
    assert [item["local_type_key"] for item in cards] == ["t01", "t02"]
    for card in cards:
        assert set(card) == {
            "local_type_key",
            "display_name",
            "definition",
            "positive_signals",
            "negative_signals",
            "competitors",
            "counterexamples",
            "supported_source_shapes",
            "required_context_facets",
            "context_disqualifiers",
            "projection_version",
        }
        assert card["positive_signals"]
        assert card["negative_signals"]
        assert card["competitors"]
        assert card["counterexamples"]
        assert card["required_context_facets"]
        assert card["context_disqualifiers"]
    request_text = json.dumps(prepared.candidate.payload, sort_keys=True)
    assert "cash_balance_snapshot_v1" not in request_text
    assert "printed_financial_metric_v1" not in request_text
    assert "source_value_ref" not in request_text
    assert "typed_option" not in request_text
    assert prepared.candidate.active is False
    assert prepared.candidate.transport_eligible is False
    assert prepared.candidate.provider_calls_total == 0

    mapping = prepared.mapping_receipt
    assert len(mapping.type_restoration) == 2
    assert len(mapping.option_restoration) == 0
    for option in mapping.option_restoration:
        assert set(option) == {
            "local_option_key",
            "local_type_key",
            "canonical_type_id",
            "canonical_typed_option_id",
            "source_unit_key",
            "value_bindings",
            "source_refs",
            "constructibility_status",
            "option_hash",
        }
        assert option["constructibility_status"] == "exact_materializable"
        assert option["value_bindings"]
        assert option["source_refs"]


def test_vertical_rechecks_old_singleton_and_fails_closed(authorities):
    _registry, _proof, _packages, prepared, response, execution = authorities
    assert execution.accounting == {
        "total_units": 3,
        "typed": 0,
        "unclassified": 3,
        "no_fact": 0,
        "unsupported": 0,
        "technical_failure": 0,
        "excluded": 0,
        "unaccounted_units": 0,
    }
    assert [item.code_reason for item in execution.units] == [
        "MULTIPLE_PLAUSIBLE_TYPES",
        "INSUFFICIENT_SEMANTIC_CONTEXT",
        "NO_PLAUSIBLE_TYPE",
    ]
    old_singleton = execution.units[1]
    assert old_singleton.disposition == "unclassified_financial_input"
    assert old_singleton.context_sufficiency is not None
    assert old_singleton.context_sufficiency.status == "INSUFFICIENT"
    assert set(old_singleton.context_sufficiency.missing_facets) == {
        "date_or_period",
        "printed_label_evidence_ref",
        "statement_scope",
    }
    assert all(
        item.disposition == "unclassified_financial_input"
        for item in execution.units
    )
    assert execution.provider_calls_total == 0
    assert execution.retries_total == 0
    assert execution.repairs_total == 0
    assert execution.fallbacks_total == 0
    assert execution.model_generated_values_total == 0
    assert response["unit_decisions"][0]["plausible_type_keys"] == [
        "t01",
        "t02",
    ]


def test_false_singleton_is_observable_and_never_typed(authorities):
    _registry, _proof, _packages, prepared, _response, execution = authorities
    unit = prepared.units[0]
    assert unit.scope.decision_contract.eligible_type_ids == (
        "printed_financial_metric_v1",
    )
    assert unit.compilation.typed_options == ()
    comparator = false_singleton_comparator(
        prepared=prepared,
        execution=execution,
    )
    assert comparator == {
        "false_singleton_cases_total": 1,
        "false_singleton_detected_total": 1,
        "false_singleton_typed_total": 0,
        "unsafe_typed_total": 0,
        "wrong_singleton_total": 0,
        "provider_calls_total": 0,
        "proof_passed": True,
    }


def test_insufficient_context_and_four_human_reviewable_traces(authorities):
    _registry, proof, _packages, prepared, response, execution = authorities
    no_exact_response = proof.response(
        prepared=prepared,
        plausible_types_by_unit={
            "u01": ("t02",),
            "u02": ("t01", "t02"),
            "u03": ("t01",),
        },
    )
    no_exact_execution = proof.execute(
        prepared=prepared,
        simulated_response=no_exact_response,
    )
    assert no_exact_execution.units[0].code_reason == (
        "INSUFFICIENT_SEMANTIC_CONTEXT"
    )
    assert no_exact_execution.units[0].disposition == (
        "unclassified_financial_input"
    )
    main_trace = safe_trace_pack(
        prepared=prepared,
        response=response,
        execution=execution,
    )
    derived_trace = safe_trace_pack(
        prepared=prepared,
        response=no_exact_response,
        execution=no_exact_execution,
    )
    selected = [
        main_trace["traces"][1],
        main_trace["traces"][0],
        derived_trace["traces"][0],
        main_trace["traces"][2],
    ]
    assert len(selected) == 4
    assert {item["code_reason"] for item in selected} == {
        "INSUFFICIENT_SEMANTIC_CONTEXT",
        "MULTIPLE_PLAUSIBLE_TYPES",
        "NO_PLAUSIBLE_TYPE",
    }
    assert all(
        item["materialization"]["owner"]
        == "Gate2FinancialEvidenceMaterializerFactory"
        for item in selected
    )


def test_existing_evidence_replay_is_exact(authorities):
    registry, _proof, packages, prepared, response, execution = authorities
    evidence = Gate2FinancialSemanticV6DecisionEvidenceFactory(
        registry=registry
    ).create_type_first_proof(
        case_id="kt2-main",
        gate2_packages=packages,
        prepared=prepared,
        simulated_response=response,
        execution=execution,
    )
    replay = replay_financial_semantic_v6_type_first_proof(
        private_evidence=evidence.private_evidence,
        registry=registry,
    )
    assert replay.status == "exact"
    assert replay.replay_hash_match is True
    assert replay.provider_calls_total == 0
    assert replay.execution_integrity_hash == execution.integrity_hash
    assert evidence.safe_receipt["customer_values_present"] is False
    assert evidence.safe_receipt["raw_source_refs_present"] is False
    assert evidence.safe_receipt["raw_provider_payload_present"] is False


def test_private_evidence_and_materialized_outputs_round_trip_artifact_store(
    tmp_path,
    authorities,
):
    registry, _proof, packages, prepared, response, execution = authorities
    evidence = Gate2FinancialSemanticV6DecisionEvidenceFactory(
        registry=registry
    ).create_type_first_proof(
        case_id="kt2-store",
        gate2_packages=packages,
        prepared=prepared,
        simulated_response=response,
        execution=execution,
    )
    store = ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=tmp_path / "artifacts.sqlite3",
            payload_root=tmp_path / "payloads",
        )
    ).create()
    context = ArtifactAccessContext(
        user_id="kt2-user",
        case_id="kt2-case",
        chat_id="kt2-chat",
        workspace_model_id="kt2-workspace",
        normalization_run_id="kt2-normalization",
        allow_private=True,
    )
    retention = build_retention_policy(mode="synthetic_dev")
    payloads = [
        ("art_kt2_private_evidence", "debug_diagnostic_v0", evidence.private_evidence),
        *[
            (
                f"art_kt2_materialized_{index}",
                "broker_reports_financial_evidence_inputs_v2",
                unit.total_materialization.canonical_artifact,
            )
            for index, unit in enumerate(execution.units, start=1)
        ],
    ]
    for artifact_id, artifact_type, payload in payloads:
        store.put_record(
            ArtifactRecord(
                artifact_id=artifact_id,
                artifact_type=artifact_type,
                case_id=context.case_id,
                chat_id=context.chat_id,
                user_id=context.user_id,
                workspace_model_id=context.workspace_model_id,
                normalization_run_id=context.normalization_run_id,
                document_id=None,
                source_file_ref=None,
                visibility="private_case",
                storage_backend="project_artifact_payload",
                retention_policy=retention,
                access_policy={"requires_user_id": True},
                validation_status="validated",
                lifecycle_status=lifecycle_for_visibility(
                    visibility="private_case",
                    validation_status="validated",
                ),
                payload_kind="json_file",
                payload=copy.deepcopy(payload),
                safe_metadata={"proof": "kt2_type_first"},
            )
        )
    resolver = ArtifactResolver(store)
    assert resolver.resolve("art_kt2_private_evidence", context)[
        "payload"
    ] == evidence.private_evidence
    for index, unit in enumerate(execution.units, start=1):
        assert resolver.resolve(
            f"art_kt2_materialized_{index}", context
        )["payload"] == unit.total_materialization.canonical_artifact


def _invalid_response_cases(base: dict) -> list[tuple[str, object, str]]:
    cases: list[tuple[str, object, str]] = []

    def changed(name, mutate, code):
        value = copy.deepcopy(base)
        mutate(value)
        cases.append((name, value, code))

    changed("unknown_key", lambda x: x["unit_decisions"][0]["plausible_type_keys"].append("t99"), "local_key_unknown")
    changed("duplicate_key", lambda x: x["unit_decisions"][0].update(plausible_type_keys=["t01", "t01"]), "plausible_keys_invalid")
    changed("unknown_unit", lambda x: x["unit_decisions"][0].update(source_unit_key="u99"), "unit_decision_invalid")
    changed("missing_unit", lambda x: x["unit_decisions"].pop(), "unit_coverage_invalid")
    changed("reordered_units", lambda x: x["unit_decisions"].reverse(), "unit_decision_invalid")
    changed("request_key", lambda x: x.update(request_key="stale"), "request_key_mismatch")
    changed("request_hash", lambda x: x.update(request_hash="0" * 64), "request_hash_mismatch")
    changed("mapping_hash", lambda x: x.update(mapping_hash="0" * 64), "mapping_hash_mismatch")
    changed("pack_hash", lambda x: x.update(semantic_pack_integrity_sha256="0" * 64), "pack_hash_mismatch")
    changed("root_extra", lambda x: x.update(reason="model reason"), "response_schema_invalid")
    changed("unit_extra", lambda x: x["unit_decisions"][0].update(reason="model reason"), "unit_decision_invalid")
    changed("model_value", lambda x: x["unit_decisions"][0].update(value="999"), "unit_decision_invalid")
    changed("model_source_ref", lambda x: x["unit_decisions"][0].update(source_ref="ref"), "unit_decision_invalid")
    changed("canonical_type_id", lambda x: x["unit_decisions"][0].update(plausible_type_keys=["cash_balance_snapshot_v1"]), "local_key_unknown")
    changed("wrong_schema", lambda x: x.update(schema_version="v0"), "response_schema_invalid")
    changed("missing_schema", lambda x: x.pop("schema_version"), "response_schema_invalid")
    changed("not_array", lambda x: x["unit_decisions"][0].update(plausible_type_keys="t01"), "unit_decision_invalid")
    changed("unknown_root_shape", lambda x: x.update(unit_decision=[]), "response_schema_invalid")
    cases.append(("not_object", [], "response_schema_invalid"))
    cases.append(("invalid_json", "{", "response_json_invalid"))
    duplicate_json = json.dumps(base).replace(
        '"request_key":', '"request_key":"duplicate","request_key":', 1
    )
    cases.append(("duplicate_json_object_key", duplicate_json, "response_duplicate_key"))
    cases.append(("oversize", "{" + ("x" * 17000), "response_size_invalid"))
    return cases


def test_adversarial_response_matrix_has_at_least_twenty_one_fail_closed_cases(
    authorities,
):
    _registry, proof, _packages, prepared, response, _execution = authorities
    cases = _invalid_response_cases(response)
    assert len(cases) >= 21
    for case_id, invalid, expected in cases:
        with pytest.raises(
            Gate2FinancialSemanticV6ChoiceError,
            match=expected,
        ), pytest.MonkeyPatch.context() as _context:
            proof.execute(prepared=prepared, simulated_response=invalid)


def test_valid_adversarial_dispositions_never_create_unsafe_typed(authorities):
    _registry, proof, _packages, prepared, _response, _execution = authorities
    cases = (
        {"u01": (), "u02": (), "u03": ()},
        {"u01": ("t01", "t02"), "u02": ("t01", "t02"), "u03": ("t01", "t02")},
        {"u01": ("t02",), "u02": ("t01", "t02"), "u03": ()},
        {"u01": ("t01", "t02"), "u02": ("t02",), "u03": ("t01",)},
    )
    for plausible in cases:
        response = proof.response(
            prepared=prepared,
            plausible_types_by_unit=plausible,
        )
        execution = proof.execute(
            prepared=prepared,
            simulated_response=response,
        )
        for result in execution.units:
            if result.disposition == "typed_input":
                assert result.code_reason == (
                    "UNIQUE_PLAUSIBLE_TYPE_AND_EXACT_OPTION"
                )
                assert len(result.plausible_type_ids) == 1
                assert len(result.exact_restored_option_keys) == 1


def _rehash_private_evidence(value: dict) -> dict:
    import hashlib

    result = copy.deepcopy(value)
    result.pop("private_evidence_hash", None)
    result["private_evidence_hash"] = hashlib.sha256(
        json.dumps(
            result,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return result


@pytest.mark.parametrize(
    "mutation",
    (
        "local_key_substitution",
        "source_ref_substitution",
        "source_ref_reorder",
        "fixture_value_mutation",
        "mapping_substitution",
        "pack_substitution",
    ),
)
def test_replay_detects_all_authority_and_fixture_substitutions(
    authorities,
    mutation,
):
    registry, _proof, packages, prepared, response, execution = authorities
    evidence = Gate2FinancialSemanticV6DecisionEvidenceFactory(
        registry=registry
    ).create_type_first_proof(
        case_id="kt2-tamper",
        gate2_packages=packages,
        prepared=prepared,
        simulated_response=response,
        execution=execution,
    )
    tampered = copy.deepcopy(evidence.private_evidence)
    if mutation == "local_key_substitution":
        tampered["simulated_response"]["unit_decisions"][1][
            "plausible_type_keys"
        ] = ["t01"]
    elif mutation == "source_ref_substitution":
        tampered["gate2_packages"][0]["source_unit"][
            "source_value_index"
        ][0]["cell_ref"] += "_substituted"
    elif mutation == "source_ref_reorder":
        tampered["gate2_packages"][0]["source_unit"][
            "source_value_refs"
        ].reverse()
    elif mutation == "fixture_value_mutation":
        tampered["gate2_packages"][0]["source_unit"][
            "model_source_projection"
        ]["rows"][0]["cells"][0]["value"] = "999.00"
    elif mutation == "mapping_substitution":
        tampered["sealed_mapping"]["type_restoration"].reverse()
    elif mutation == "pack_substitution":
        tampered["semantic_pack"]["integrity_sha256"] = "0" * 64
    tampered = _rehash_private_evidence(tampered)
    with pytest.raises(Gate2FinancialSemanticV6DecisionEvidenceError):
        replay_financial_semantic_v6_type_first_proof(
            private_evidence=tampered,
            registry=registry,
        )


def test_anti_duplication_and_product_unreachability_guards(corpus):
    proof_source = PROOF_MODULE.read_text(encoding="utf-8")
    product_source = PRODUCT_ROUTE.read_text(encoding="utf-8")
    assert "gate2_same_source_type_first_proof" not in product_source
    for path in FUNCTION_ROOTS:
        assert "gate2_same_source_type_first_proof" not in path.read_text(
            encoding="utf-8"
        )
    assert "Gate2FinancialSemanticContractFactory" in proof_source
    assert "Gate2FinancialSemanticV6ChoiceContractFactory" in proof_source
    assert "Gate2FinancialSemanticV6DecisionExpansionFactory" in proof_source
    assert "Gate2FinancialSemanticV6TotalMaterializerFactory" in proof_source
    assert "Gate2FinancialEvidenceMaterializerFactory(" not in proof_source
    assert "re.compile" not in proof_source
    assert "synonym" not in proof_source.casefold()
    assert "subagent" not in proof_source.casefold()
    assert "provider_client" not in proof_source
    assert "source_fact_selection_v3" not in proof_source
    assert "GOAL17" not in json.dumps(corpus, sort_keys=True)
    assert len(
        Gate2FinancialEvidenceRegistryFactory().create().provider_type_enum()
    ) == 2
