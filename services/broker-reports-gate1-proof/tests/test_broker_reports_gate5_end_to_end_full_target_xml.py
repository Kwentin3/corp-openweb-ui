from __future__ import annotations

import ast
import asyncio
import copy
import hashlib
import inspect
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from broker_reports_gate1 import gate5_end_to_end_full_target_xml as module
from broker_reports_gate1.artifact_models import ArtifactAccessContext
from broker_reports_gate1.artifact_resolver import ArtifactResolver
from broker_reports_gate1.artifact_models import ArtifactStoreError
from broker_reports_gate1.artifact_store import ArtifactStoreConfig, ArtifactStoreFactory
from broker_reports_gate1.gate2_model_clients import (
    Gate2StructuredModelClientConfig,
    Gate2StructuredModelClientFactory,
)
from broker_reports_gate1.gate2_model_requests import (
    GATE3_BOUNDED_LABELING_REQUEST_PROFILE,
)
from broker_reports_gate1.gate5_end_to_end_full_target_xml import (
    FACTORY_REQUIRED,
    FORBIDDEN,
    GATE5_END_TO_END_STATUS,
    GATE5_END_TO_END_SUPPLIED_CASE_RESOURCE,
    GATE5_END_TO_END_SUPPLIED_CASE_SHA256,
    Gate5EndToEndFullTargetXmlError,
    Gate5EndToEndFullTargetXmlRuntimeFactory,
    Gate5EndToEndSuppliedCaseAuthorityFactory,
)
from broker_reports_gate1.gate5_full_target_xml_projection import (
    Gate5FullTargetXmlProjectionError,
    Gate5FullTargetXmlProjectionRuntimeFactory,
)
from broker_reports_gate1.artifact_retention import build_retention_policy
from broker_reports_gate1.gate5_openwebui_product import (
    GATE5_OPENWEBUI_PRODUCT_STATUS,
    Gate5OpenWebUIProductRuntimeFactory,
)


MODEL_ID = "models/gemini-3.5-flash"
PROVIDER_PROFILE_ID = "google_gemini"


def test_source_to_official_xml_replays_every_gate_and_emits_hash_chain(
    tmp_path: Path,
) -> None:
    result, captured = _run(tmp_path, _proof_input())

    assert result["status"] == GATE5_END_TO_END_STATUS
    assert result["receipt"]["status"] == GATE5_END_TO_END_STATUS
    assert result["receipt"]["blockers"] == []
    assert result["receipt"]["target_result"]["status"] == (
        "FULL_TARGET_XML_VALID"
    )
    assert result["receipt"]["target_result"]["conformance_proof"][
        "xsd_valid"
    ] is True
    assert result["receipt"]["target_result"]["semantic_mapping_proof"][
        "status"
    ] == "passed"
    assert len(captured) == 2
    assert [
        item["response_format"]["json_schema"]["name"] for item in captured
    ] == [
        "broker_reports_gate3_labeling_response_v1",
        "broker_reports_gate3_role_labeling_response_v1",
    ]
    assert [row["stage"] for row in result["receipt"]["hash_chain"]] == [
        "original_supplied_source",
        "gate1_custody_artifact",
        "gate2_canonical_artifact",
        "gate3_financial_annotations",
        "gate4_financial_case",
        "gate5_residency_classification",
        "gate5_operation_tax_model",
        "gate5_category_tax_model",
        "gate5_income_group_tax_base",
        "gate5_trusted_components",
        "full_declaration_definition",
        "declaration_scope_receipt",
        "resolved_declaration_package",
        "declaration_semantic_input",
        "projection_definition",
        "full_target_xml",
        "official_xsd",
    ]
    Gate5EndToEndFullTargetXmlRuntimeFactory(
        store=None,
        read_enabled=True,
        retention_policy=build_retention_policy(mode="synthetic_dev"),
        gate3_model_client=object(),
        gate3_model_id=MODEL_ID,
        gate3_provider_profile_id=PROVIDER_PROFILE_ID,
    ).create().validate_receipt(result["receipt"])
    audit = result["receipt"]["critical_provenance_audit"]
    assert len(audit) == 10
    assert all(item["projection_mapping"]["xml_target"] for item in audit)
    assert all(
        item["sealed_component"]["source_component_sha256"] for item in audit
    )


def test_same_source_case_and_authorities_produce_same_semantics_and_xml(
    tmp_path: Path,
) -> None:
    first, _ = _run(tmp_path / "first", _proof_input())
    second, _ = _run(tmp_path / "second", _proof_input())

    assert first["xml_bytes"] == second["xml_bytes"]
    assert first["receipt"]["determinism"] == second["receipt"]["determinism"]
    assert first["receipt"]["target_result"]["xml_binding"] == second[
        "receipt"
    ]["target_result"]["xml_binding"]


def test_structurally_missing_supplied_value_yields_acquisition_request_before_xml(
    tmp_path: Path,
) -> None:
    value = _proof_input()
    source = value["supplied_source"]
    source["content_utf8"] = source["content_utf8"].replace(
        ",100.00,RUB\n", ",,RUB\n"
    )
    source["content_sha256"] = hashlib.sha256(
        source["content_utf8"].encode("utf-8")
    ).hexdigest()

    with pytest.raises(Gate5EndToEndFullTargetXmlError) as exc_info:
        _run(tmp_path, value, missing_amount=True)

    assert exc_info.value.code == "gate5_e2e_supplied_source_incomplete"
    assert exc_info.value.blocker["stage"] == "gate4_financial_case"
    assert exc_info.value.blocker["missing_role_names"] == ["amount"]
    request = exc_info.value.blocker["acquisition_request"]
    assert request["action"] == "provide_missing_source_or_values"
    assert request["missing_role_names"] == ["amount"]


def test_missing_mandatory_case_fact_fails_after_source_path_without_default(
    tmp_path: Path,
) -> None:
    value = _proof_input()
    del value["filing_and_party_identity"]["filing_instance"]["declaration_date"]

    with pytest.raises(Gate5EndToEndFullTargetXmlError) as exc_info:
        _run(tmp_path, value)

    assert exc_info.value.code == "gate5_e2e_case_fact_missing"
    assert exc_info.value.field == "declaration_date"
    assert exc_info.value.blocker == {
        "stage": "trusted_case_fact_boundary",
        "missing_fact": "declaration_date",
        "action": "provide_mandatory_case_fact",
    }


def test_tampered_sealed_semantic_input_and_receipt_fail_closed(
    tmp_path: Path,
) -> None:
    result, _ = _run(tmp_path, _proof_input())
    semantic_input = copy.deepcopy(result["semantic_input"])
    semantic_input["declaration_semantics"]["tax_period"] = "2024"

    with pytest.raises(Gate5FullTargetXmlProjectionError) as semantic_failure:
        Gate5FullTargetXmlProjectionRuntimeFactory.create().project(
            semantic_input=semantic_input
        )
    assert semantic_failure.value.code == "gate5_full_target_semantic_input_invalid"

    receipt = copy.deepcopy(result["receipt"])
    receipt["hash_chain"][3]["artifact_sha256"] = "0" * 64
    with pytest.raises(Gate5EndToEndFullTargetXmlError) as receipt_failure:
        Gate5EndToEndFullTargetXmlRuntimeFactory(
            store=None,
            read_enabled=True,
            retention_policy=build_retention_policy(mode="synthetic_dev"),
            gate3_model_client=object(),
            gate3_model_id=MODEL_ID,
            gate3_provider_profile_id=PROVIDER_PROFILE_ID,
        ).create().validate_receipt(receipt)
    assert receipt_failure.value.code == "gate5_e2e_receipt_hash_chain_invalid"


def test_product_human_residual_persists_replays_and_denies_other_user(
    tmp_path: Path,
) -> None:
    proof = _proof_input()
    baseline, _ = _run(tmp_path, proof)
    store = ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=tmp_path / "artifacts.sqlite3",
            payload_root=tmp_path / "payloads",
        )
    ).create()
    binding = proof["binding"]
    context = ArtifactAccessContext(
        user_id=binding["authenticated_user_ref"],
        normalization_run_id=binding["normalization_run_ref"],
        case_id=binding["case_id"],
        workspace_model_id=binding["workspace_model_id"],
        allow_private=True,
        require_source_available=True,
    )
    full_target_runtime = Gate5EndToEndFullTargetXmlRuntimeFactory(
        store=store,
        read_enabled=True,
        retention_policy=build_retention_policy(mode="synthetic_dev"),
        gate3_model_client=object(),
        gate3_model_id=MODEL_ID,
        gate3_provider_profile_id=PROVIDER_PROFILE_ID,
    ).create()
    product = Gate5OpenWebUIProductRuntimeFactory(
        store=store,
        retention_policy=build_retention_policy(mode="synthetic_dev"),
        full_target_runtime=full_target_runtime,
    ).create()
    facts = {
        key: copy.deepcopy(proof[key])
        for key in (
            "scope",
            "residency_evidence",
            "supplemental_money",
            "securities_disposal",
            "tax_period_category",
            "income_group",
            "settlement",
            "filing_and_party_identity",
            "taxable_income_source",
            "budget_disposition",
            "financial_investment",
        )
    }
    declaration_date = facts["filing_and_party_identity"]["filing_instance"].pop(
        "declaration_date"
    )
    common = {
        "context": context,
        "source_file_id": proof["supplied_source"]["private_ref"],
        "source_filename": proof["supplied_source"]["filename"],
        "source_mime_type": proof["supplied_source"]["mime_type"],
        "source_bytes": proof["supplied_source"]["content_utf8"].encode("utf-8"),
        "financial_annotations_artifact_id": baseline["receipt"][
            "gate3_boundary_evidence"
        ]["artifact_id"],
    }

    blocked = product.process(
        **common,
        latest_user_message=(
            "3-НДФЛ факты: " + json.dumps(facts, ensure_ascii=False)
        ),
    )
    assert blocked["status"] == "blocked"
    assert blocked["blocker_code"] == "gate5_e2e_case_fact_missing"
    assert blocked["missing_fact"] == "declaration_date"
    assert blocked["xml_created"] is False

    completed = product.process(
        **common,
        latest_user_message=(
            "3-НДФЛ факты: "
            + json.dumps(
                {
                    "filing_and_party_identity": {
                        "filing_instance": {"declaration_date": declaration_date}
                    }
                },
                ensure_ascii=False,
            )
        ),
    )
    assert completed["status"] == GATE5_OPENWEBUI_PRODUCT_STATUS
    assert completed["xml_bytes"] == baseline["xml_bytes"]
    assert completed["official_xsd_valid"] is True

    replayed = product.process(
        **common,
        latest_user_message=(
            "3-НДФЛ факты: "
            + json.dumps(
                {
                    "filing_and_party_identity": {
                        "filing_instance": {"declaration_date": declaration_date}
                    }
                },
                ensure_ascii=False,
                indent=2,
            )
        ),
    )
    assert replayed["status"] == GATE5_OPENWEBUI_PRODUCT_STATUS
    assert replayed["xml_bytes"] == completed["xml_bytes"]
    assert replayed["xml_artifact_id"] == completed["xml_artifact_id"]

    wrong_user = ArtifactAccessContext(
        user_id="different-authenticated-user",
        normalization_run_id=context.normalization_run_id,
        case_id=context.case_id,
        workspace_model_id=context.workspace_model_id,
        allow_private=True,
    )
    with pytest.raises(ArtifactStoreError) as denial:
        ArtifactResolver(store).resolve(completed["xml_artifact_id"], wrong_user)
    assert denial.value.code == "artifact_access_denied"


def test_case_resource_is_hash_pinned_closed_world_and_target_free_runtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package_resource = (
        Path(module.__file__).parent / GATE5_END_TO_END_SUPPLIED_CASE_RESOURCE
    )
    assert hashlib.sha256(package_resource.read_bytes()).hexdigest() == (
        GATE5_END_TO_END_SUPPLIED_CASE_SHA256
    )
    outside = tmp_path / "outside-repository-cwd"
    outside.mkdir()
    monkeypatch.chdir(outside)
    assert (
        Gate5EndToEndSuppliedCaseAuthorityFactory.create().load()[
            "case_fact_set_id"
        ]
        == "g535_supplied_broker_source_2025"
    )

    source = inspect.getsource(module)
    runtime_source = inspect.getsource(module.Gate5EndToEndFullTargetXmlRuntime)
    imports = {
        node.module
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    assert len(FACTORY_REQUIRED) == 6
    assert FORBIDDEN
    for owner in (
        "Gate1Normalizer().normalize",
        "persist_gate1_result",
        "CanonicalReaderFactory",
        "Gate3ChunkBatchLabelingFactory",
        "Gate3FinancialAnnotationsPersistenceFactory",
        "Gate4FinancialCaseRuntimeFactory",
        "Gate5SecuritiesDisposalTaxModelRuntimeFactory",
        "Gate5ResolvedDeclarationPackageRuntimeFactory",
        "Gate5DeclarationSemanticInputRuntimeFactory",
        "Gate5FullTargetXmlProjectionRuntimeFactory",
    ):
        assert owner in runtime_source
    for forbidden in (
        "test_broker_reports_",
        "sqlite3",
        "SELECT ",
        "1151020",
        "5.20",
        "КНД",
        "Файл",
        "Документ",
        "lxml",
        "xml.etree",
    ):
        assert forbidden not in runtime_source
    assert all(not name.startswith("test_") for name in imports)


def _proof_input() -> dict:
    return Gate5EndToEndSuppliedCaseAuthorityFactory.create().load()


def _run(
    root: Path,
    proof_input: dict,
    *,
    missing_amount: bool = False,
    audit_sink=None,
):
    root.mkdir(parents=True, exist_ok=True)
    store = ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=root / "artifacts.sqlite3",
            payload_root=root / "payloads",
        )
    ).create()
    binding = proof_input["binding"]
    context = ArtifactAccessContext(
        user_id=binding["authenticated_user_ref"],
        normalization_run_id=binding["normalization_run_ref"],
        case_id=binding["case_id"],
        workspace_model_id=binding["workspace_model_id"],
        allow_private=True,
        require_source_available=True,
    )
    client, captured = _model_client(
        user_id=context.user_id,
        missing_amount=missing_amount,
    )
    runtime = Gate5EndToEndFullTargetXmlRuntimeFactory(
        store=store,
        read_enabled=True,
        retention_policy=build_retention_policy(mode="synthetic_dev"),
        gate3_model_client=client,
        gate3_model_id=MODEL_ID,
        gate3_provider_profile_id=PROVIDER_PROFILE_ID,
    ).create()
    result = asyncio.run(
        runtime.run(
            proof_input=proof_input,
            context=context,
            _declaration_model_audit_receipt_sink=audit_sink,
        )
    )
    return result, captured


def _model_client(*, user_id: str, missing_amount: bool):
    captured: list[dict] = []

    def complete(*, form_data, **_kwargs):
        captured.append(json.loads(json.dumps(form_data, ensure_ascii=False)))
        name = form_data["response_format"]["json_schema"]["name"]
        if name == "broker_reports_gate3_labeling_response_v1":
            response = {
                "schema_version": "broker_reports_gate3_labeling_response_v1",
                "annotations": [
                    {
                        "target_alias": "t010",
                        "financial_label": "SECURITY_DISPOSAL",
                    }
                ],
            }
        else:
            assert name == "broker_reports_gate3_role_labeling_response_v1"
            amount = (
                {"role": "amount", "status": "missing"}
                if missing_amount
                else _bound("amount", "t017")
            )
            response = {
                "schema_version": (
                    "broker_reports_gate3_role_labeling_response_v1"
                ),
                "facts": [
                    {
                        "fact_alias": "f001",
                        "financial_label": "SECURITY_DISPOSAL",
                        "roles": [
                            _bound("date", "t012"),
                            _bound("asset", "t014"),
                            _bound("quantity", "t015"),
                            amount,
                            _bound("currency", "t018"),
                            _bound("unit_price", "t016"),
                        ],
                    }
                ],
            }
        return {
            "id": f"g535-provider-response-{len(captured)}",
            "model": MODEL_ID,
            "choices": [
                {
                    "message": {
                        "content": json.dumps(response, ensure_ascii=False)
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 20,
                "total_tokens": 120,
            },
        }

    user = SimpleNamespace(id=user_id)
    client = Gate2StructuredModelClientFactory(
        config=Gate2StructuredModelClientConfig(
            request_profile=GATE3_BOUNDED_LABELING_REQUEST_PROFILE,
            provider_profile_id=PROVIDER_PROFILE_ID,
        ),
        user=user,
        request=SimpleNamespace(),
        completion_resolver=lambda _user_id: (complete, user),
    ).create()
    return client, captured


def _bound(role: str, target_alias: str) -> dict[str, str]:
    return {"role": role, "status": "bound", "target_alias": target_alias}
