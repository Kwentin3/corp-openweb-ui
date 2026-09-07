from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from broker_reports_gate1.artifact_models import ArtifactAccessContext
from broker_reports_gate1.artifact_retention import build_retention_policy
from broker_reports_gate1.artifact_store import ArtifactStoreConfig, ArtifactStoreFactory
from broker_reports_gate1.ordinary_trade_declaration_case_bundle import (
    OrdinaryTradeDeclarationCaseBundleFactory,
)
from broker_reports_gate1.ordinary_trade_production_runtime import (
    OrdinaryTradeProductionRuntimeFactory,
)


def test_bundle_binds_current_owner_material_and_stales_on_real_coverage_change(
    tmp_path: Path,
) -> None:
    state = _state()
    runtime = _runtime(tmp_path, state)
    context = _context()

    first = runtime.stabilize_current_scope(context=context, tax_period="2025")
    again = runtime.stabilize_current_scope(context=context, tax_period="2025")

    assert first["status"] == "CURRENT"
    assert first["created"] is True
    assert again["created"] is False
    assert first["bundle_artifact_ref"] == again["bundle_artifact_ref"]
    assert "facts" not in first["bundle"]
    assert "private-value" not in str(first["bundle"])
    assert "private" not in str(first["bundle"])
    assert runtime.read_current(context=context, tax_period="2025")["status"] == "CURRENT"

    state["coverage"] = _coverage(root="b" * 64)

    stale = runtime.read_current(context=context, tax_period="2025")
    assert stale["status"] == "BUNDLE_STALE"
    assert stale["bundle_artifact_ref"] == first["bundle_artifact_ref"]


def test_bundle_stales_when_admitted_facts_or_user_facts_change(tmp_path: Path) -> None:
    state = _state()
    runtime = _runtime(tmp_path, state)
    context = _context()
    runtime.stabilize_current_scope(context=context, tax_period="2025")

    state["fact_set"] = {
        **state["fact_set"],
        "facts": [{"fact_id": "fact-two", "value": "new-private-value"}],
    }
    assert runtime.read_current(context=context, tax_period="2025")["status"] == "BUNDLE_STALE"

    state = _state()
    runtime = _runtime(tmp_path / "second", state)
    runtime.stabilize_current_scope(context=context, tax_period="2025")
    state["user_facts"] = [
        {"user_case_fact_ref": "user-fact-two", "value": {"value": "new-private"}}
    ]
    assert runtime.read_current(context=context, tax_period="2025")["status"] == "BUNDLE_STALE"


def test_bundle_scope_cannot_be_read_by_another_authenticated_case(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path, _state())
    context = _context()
    runtime.stabilize_current_scope(context=context, tax_period="2025")

    other = replace(context, case_id="case-other")

    assert runtime.read_current(context=other, tax_period="2025") == {
        "status": "BUNDLE_STABILIZATION_REQUIRED",
        "bundle": None,
    }


def test_production_composition_exposes_only_bundle_owner_terminal(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    runtime = OrdinaryTradeProductionRuntimeFactory(
        store=store,
        read_enabled=True,
        retention_policy=build_retention_policy(mode="api_smoke"),
    ).create()

    assert runtime.current_declaration_case_bundle(
        context=_context(), tax_period="2025"
    ) == {"status": "BUNDLE_STABILIZATION_REQUIRED", "bundle": None}


def _runtime(tmp_path: Path, state: dict):
    store = _store(tmp_path)
    return OrdinaryTradeDeclarationCaseBundleFactory(
        store=store,
        retention_policy=build_retention_policy(mode="api_smoke"),
        coverage_reader=lambda **_kwargs: state["coverage"],
        fact_set_reader=lambda **_kwargs: state["fact_set"],
        user_facts_reader=lambda **_kwargs: state["user_facts"],
    ).create()


def _store(tmp_path: Path):
    return ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=tmp_path / "artifacts.sqlite3",
            payload_root=tmp_path / "payloads",
        )
    ).create()


def _context() -> ArtifactAccessContext:
    return ArtifactAccessContext(
        user_id="user-one",
        case_id="case-one",
        chat_id=None,
        workspace_model_id="workspace-one",
        normalization_run_id="run-one",
        allow_private=True,
    )


def _state() -> dict:
    return {
        "coverage": _coverage(root="a" * 64),
        "fact_set": {
            "schema_version": "broker_reports_gate4_ordinary_trade_current_fact_set_v1",
            "status": "READY",
            "facts": [{"fact_id": "fact-one", "value": "private-value"}],
            "blockers": [],
        },
        "user_facts": [
            {"user_case_fact_ref": "user-fact-one", "value": {"value": "private"}}
        ],
    }


def _coverage(*, root: str) -> dict:
    return {
        "schema_version": "broker_reports_ordinary_trade_current_case_coverage_v2",
        "status": "complete",
        "coverage_ref": "ordinary_trade_coverage_" + root[:32],
        "coverage_sha256": root,
        "document_scope": [
            {
                "document_id": "document-one",
                "canonical_version_id": "canonical-one",
                "canonical_root_sha256": root,
                "manifest_ref": "art_manifest_one",
            }
        ],
        "projections": [
            {"projection_artifact_id": "art_projection_one"}
        ],
    }
