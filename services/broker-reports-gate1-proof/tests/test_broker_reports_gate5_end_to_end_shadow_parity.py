from __future__ import annotations

import asyncio
import copy
import hashlib
import inspect
import json
from collections import Counter
from pathlib import Path

import pytest

from broker_reports_gate1 import gate5_end_to_end_full_target_xml as module
from broker_reports_gate1.artifact_models import ArtifactAccessContext
from broker_reports_gate1.artifact_resolver import ArtifactResolver
from broker_reports_gate1.artifact_retention import build_retention_policy
from broker_reports_gate1.artifact_store import ArtifactStoreConfig, ArtifactStoreFactory
from broker_reports_gate1.gate4_financial_case_cache import Gate4FinancialCaseRuntime
from broker_reports_gate1.gate5_declaration_semantic_input import (
    Gate5DeclarationSemanticInputRuntime,
)
from broker_reports_gate1.gate5_end_to_end_full_target_xml import (
    GATE5_END_TO_END_STATUS,
    GATE5_E2E_SHADOW_PARITY_STATUS,
    GATE5_E2E_SHADOW_PROFILE_NOT_PROVEN_STATUS,
    GATE5_E2E_SHADOW_RECEIPT_SCHEMA_VERSION,
    Gate5EndToEndFullTargetXmlRuntime,
    Gate5EndToEndFullTargetXmlRuntimeFactory,
)
from broker_reports_gate1.gate5_full_target_xml_projection import (
    Gate5FullTargetXmlProjectionError,
    Gate5FullTargetXmlProjectionRuntime,
)
from broker_reports_gate1.gate5_resolved_declaration_package import (
    Gate5ResolvedDeclarationPackageRuntime,
)
import test_broker_reports_gate5_end_to_end_full_target_xml as e2e_fixtures


@pytest.fixture(scope="module")
def legacy_baseline(tmp_path_factory: pytest.TempPathFactory) -> dict:
    result, _captured, artifact_index = _execute(
        tmp_path_factory.mktemp("g539ah-legacy-baseline"),
        shadow_sink=None,
    )
    return {"result": result, "artifact_index": artifact_index}


def test_ah_real_e2e_shadow_uses_same_package_without_upstream_recomputation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    legacy_baseline: dict,
) -> None:
    counters: Counter[str] = Counter()
    _count_runtime_calls(monkeypatch, counters)
    receipts: list[dict] = []

    result, captured, artifact_index = _execute(
        tmp_path,
        shadow_sink=receipts.append,
    )

    _assert_legacy_authority_unchanged(result, legacy_baseline["result"])
    assert artifact_index == legacy_baseline["artifact_index"]
    assert set(result) == {"status", "xml_bytes", "semantic_input", "receipt"}
    assert "shadow" not in json.dumps(result["receipt"], ensure_ascii=False).lower()
    assert len(captured) == 2
    assert counters == {
        "source_read": 2,
        "gate4_rebuild": 1,
        "tax_models": 1,
        "package_assemble": 1,
        "semantic_compile_per_branch": 2,
        "legacy_projection": 1,
        "consumer_projection": 1,
    }

    assert len(receipts) == 1
    receipt = receipts[0]
    assert receipt["schema_version"] == GATE5_E2E_SHADOW_RECEIPT_SCHEMA_VERSION
    assert receipt["status"] == GATE5_E2E_SHADOW_PARITY_STATUS
    assert receipt["blockers"] == []
    assert receipt["profile"] == {
        "profile_id": "payable_one_allocation",
        "proof_boundary": "G5.39AG",
    }
    assert receipt["package_binding"]["same_resolved_package"] is True
    assert len(set(receipt["package_binding"].values()) - {True}) == 1
    assert receipt["parity"] == {
        "mapping_id_target_value_hashes_equal": True,
        "official_xsd_conformance_equal": True,
        "xml_binding_equal": True,
        "xml_bytes_equal": True,
    }
    assert receipt["safety"] == {
        "legacy_product_authority": True,
        "shadow_returned_to_user": False,
        "shadow_persisted": False,
        "shadow_downloadable": False,
        "candidate_disposition": "DISCARDED",
    }
    assert receipt["rollback"] == {
        "action": "stop_shadow_receipt_sink_invocation",
        "data_migration_required": False,
        "tax_replay_required": False,
    }
    assert receipt["receipt_sha256"] == _sha256(
        {key: value for key, value in receipt.items() if key != "receipt_sha256"}
    )


@pytest.mark.parametrize(
    ("fault", "expected_status"),
    [
        ("parity_mismatch", "E2E_SHADOW_PARITY_FAILED"),
        ("profile_not_proven", GATE5_E2E_SHADOW_PROFILE_NOT_PROVEN_STATUS),
    ],
)
def test_ah_shadow_failure_is_discarded_and_legacy_remains_unchanged(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    legacy_baseline: dict,
    fault: str,
    expected_status: str,
) -> None:
    original = Gate5FullTargetXmlProjectionRuntime.project_released

    def faulted_project_released(self, *, released_values, target_mechanics):
        if fault == "profile_not_proven":
            raise Gate5FullTargetXmlProjectionError(
                "gate5_consumer_first_projection_profile_unproven",
                "budget_dispositions",
            )
        candidate = original(
            self,
            released_values=released_values,
            target_mechanics=target_mechanics,
        )
        candidate = copy.deepcopy(candidate)
        candidate["xml_bytes"] += b"\n"
        return candidate

    monkeypatch.setattr(
        Gate5FullTargetXmlProjectionRuntime,
        "project_released",
        faulted_project_released,
    )
    receipts: list[dict] = []
    result, _captured, artifact_index = _execute(
        tmp_path / fault,
        shadow_sink=receipts.append,
    )

    _assert_legacy_authority_unchanged(result, legacy_baseline["result"])
    assert artifact_index == legacy_baseline["artifact_index"]
    assert result["status"] == GATE5_END_TO_END_STATUS
    assert len(receipts) == 1
    receipt = receipts[0]
    assert receipt["status"] == expected_status
    assert receipt["blockers"]
    assert receipt["safety"]["legacy_product_authority"] is True
    assert receipt["safety"]["candidate_disposition"] == "DISCARDED"
    assert receipt["safety"]["shadow_persisted"] is False


def test_ah_shadow_is_opt_in_control_only_and_absent_from_product_owner() -> None:
    runtime_source = Gate5EndToEndFullTargetXmlRuntime.run.__doc__ or ""
    shadow_source = inspect.getsource(
        Gate5EndToEndFullTargetXmlRuntime._projection_shadow_receipt
    )
    product_source = Path(module.__file__).with_name(
        "gate5_openwebui_product.py"
    ).read_text(encoding="utf-8")

    assert "legacy result shape" in runtime_source
    for forbidden_read_or_owner in (
        "_source(",
        "Gate4",
        "TaxModel",
        "Gate5ResolvedDeclarationPackageRuntimeFactory",
        "ArtifactResolver",
        "ArtifactStore",
        "self._store",
        "persist_gate1_result",
        "_persist_xml",
        "model_client",
    ):
        assert forbidden_read_or_owner not in shadow_source
    assert "_projection_shadow_receipt_sink" not in product_source
    assert "project_released" not in product_source


def _execute(root: Path, *, shadow_sink):
    root.mkdir(parents=True, exist_ok=True)
    proof = e2e_fixtures._proof_input()
    binding = proof["binding"]
    context = ArtifactAccessContext(
        user_id=binding["authenticated_user_ref"],
        normalization_run_id=binding["normalization_run_ref"],
        case_id=binding["case_id"],
        workspace_model_id=binding["workspace_model_id"],
        allow_private=True,
        require_source_available=True,
    )
    store = ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=root / "artifacts.sqlite3",
            payload_root=root / "payloads",
        )
    ).create()
    client, captured = e2e_fixtures._model_client(
        user_id=context.user_id,
        missing_amount=False,
    )
    runtime = Gate5EndToEndFullTargetXmlRuntimeFactory(
        store=store,
        read_enabled=True,
        retention_policy=build_retention_policy(mode="synthetic_dev"),
        gate3_model_client=client,
        gate3_model_id=e2e_fixtures.MODEL_ID,
        gate3_provider_profile_id=e2e_fixtures.PROVIDER_PROFILE_ID,
    ).create()
    kwargs = {}
    if shadow_sink is not None:
        kwargs["_projection_shadow_receipt_sink"] = shadow_sink
    result = asyncio.run(runtime.run(proof_input=proof, context=context, **kwargs))
    artifact_index = Counter(
        record.artifact_type
        for record in ArtifactResolver(store).catalog_run(context)
    )
    return result, captured, artifact_index


def _count_runtime_calls(
    monkeypatch: pytest.MonkeyPatch,
    counters: Counter[str],
) -> None:
    targets = (
        (module, "_source", "source_read"),
        (Gate4FinancialCaseRuntime, "rebuild_case", "gate4_rebuild"),
        (
            Gate5EndToEndFullTargetXmlRuntime,
            "_tax_models",
            "tax_models",
        ),
        (
            Gate5ResolvedDeclarationPackageRuntime,
            "assemble",
            "package_assemble",
        ),
        (
            Gate5DeclarationSemanticInputRuntime,
            "compile",
            "semantic_compile_per_branch",
        ),
        (
            Gate5FullTargetXmlProjectionRuntime,
            "project",
            "legacy_projection",
        ),
        (
            Gate5FullTargetXmlProjectionRuntime,
            "project_released",
            "consumer_projection",
        ),
    )
    for owner, name, counter_name in targets:
        original = getattr(owner, name)

        def counted(*args, __original=original, __name=counter_name, **kwargs):
            counters[__name] += 1
            return __original(*args, **kwargs)

        monkeypatch.setattr(owner, name, counted)


def _assert_legacy_authority_unchanged(result: dict, baseline: dict) -> None:
    assert set(result) == set(baseline)
    assert result["status"] == baseline["status"] == GATE5_END_TO_END_STATUS
    assert result["xml_bytes"] == baseline["xml_bytes"]
    assert result["receipt"]["determinism"] == baseline["receipt"]["determinism"]
    target = result["receipt"]["target_result"]
    baseline_target = baseline["receipt"]["target_result"]
    assert target["status"] == baseline_target["status"] == "FULL_TARGET_XML_VALID"
    assert target["xml_binding"] == baseline_target["xml_binding"]
    assert target["conformance_proof"] == baseline_target["conformance_proof"]
    assert target["semantic_mapping_proof"] == baseline_target[
        "semantic_mapping_proof"
    ]


def _sha256(value) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
