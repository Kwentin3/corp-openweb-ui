from __future__ import annotations

import ast
import copy
import hashlib
import inspect
import json
from pathlib import Path

import pytest

from broker_reports_gate1 import (
    GATE5_EXTERNAL_EVIDENCE_ACCEPTANCE_RESULT_SCHEMA_VERSION,
    GATE5_EXTERNAL_EVIDENCE_PROPOSAL_SCHEMA_VERSION,
    GATE5_EXTERNAL_EVIDENCE_REQUIREMENT_SCHEMA_VERSION,
    GATE5_EXTERNAL_EVIDENCE_ROUTING_RESULT_SCHEMA_VERSION,
    GATE5_EXTERNAL_REFERENCE_FACT_SCHEMA_VERSION,
    ArtifactAccessContext,
    ArtifactStoreConfig,
    ArtifactStoreFactory,
    Gate4FinancialCaseRuntimeFactory,
    Gate5ExternalEvidenceDocument,
    Gate5ExternalEvidenceError,
    Gate5ExternalEvidenceRuntime,
    Gate5ExternalEvidenceRuntimeFactory,
    gate5_external_evidence_proposal_response_format,
)
from broker_reports_gate1 import gate5_external_evidence as evidence_module
from broker_reports_gate1.gate5_external_evidence import FACTORY_REQUIRED, FORBIDDEN
import test_broker_reports_gate4_sql_materialization as gate4_fixtures


ORDER_URL = "https://www.nalog.gov.ru/rn77/about_fts/docs/16589324/"
PROCEDURE_URL = (
    "https://www.nalog.gov.ru/html/sites/www.new.nalog.ru/files/"
    "about_fts/docs/16589324_2.docx"
)


def test_external_rate_research_is_source_bound_and_does_not_enrich_gate4(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, context = _representative_case(tmp_path, monkeypatch)
    runtime = _runtime(store)
    gate4_before = _financial_case(store, context)
    records_before = tuple(store.list_by_case_context(context))
    assert _role_values(gate4_before.facts[0]) == {
        "date": "2025-02-11",
        "asset": "ACME",
        "quantity": "1",
        "amount": "100.00",
        "currency": "RUB",
        "unit_price": "100.00",
    }

    routing = runtime.prepare(requirement=_requirement(), context=context)

    assert routing["schema_version"] == (
        GATE5_EXTERNAL_EVIDENCE_ROUTING_RESULT_SCHEMA_VERSION
    )
    assert routing["status"] == "external_research_required"
    assert routing["route"] == "external_authoritative_research"
    assert routing["financial_case_audit"]["required_fact_status"] == ("not_asserted")
    visible = routing["research_request"]
    visible_json = json.dumps(visible, ensure_ascii=False, sort_keys=True)
    assert visible["required_fact"] == {
        "fact_key": "resident_securities_income_group_rate_schedule",
        "value_kind": "progressive_rate_schedule",
    }
    assert visible["entity"] == {
        "jurisdiction": "RU",
        "tax_period": "2025",
        "income_group_code": "02",
        "taxpayer_status": "resident_individual",
    }
    for hidden in (
        "ACME",
        context.user_id,
        context.case_id,
        context.normalization_run_id,
        "fact_id",
        "artifact",
        "Financial Case",
    ):
        assert hidden not in visible_json

    documents = _official_boundary_documents()
    proposal = _proposal(routing=routing, documents=documents)
    accepted = runtime.accept(
        routing_result=routing,
        proposal=proposal,
        evidence_documents=documents,
    )

    assert accepted["schema_version"] == (
        GATE5_EXTERNAL_EVIDENCE_ACCEPTANCE_RESULT_SCHEMA_VERSION
    )
    assert accepted["status"] == "accepted"
    assert accepted["validation"] == {"status": "passed", "errors": []}
    assert accepted["persistence"] == "not_persisted_g5_11"
    fact = accepted["external_fact"]
    assert fact["schema_version"] == GATE5_EXTERNAL_REFERENCE_FACT_SCHEMA_VERSION
    assert fact["external_fact_ref"].startswith("g5ext_")
    assert fact["value"] == _rate_value()
    assert fact["provenance"]["source_kind"] == ("external_authoritative_evidence")
    assert fact["provenance"]["evidence_class"] == ("externally_verified_reference")
    assert fact["provenance"]["derived_tax_conclusion"] is False
    assert {
        item["content_sha256"] for item in fact["provenance"]["evidence_documents"]
    } == {hashlib.sha256(item.content).hexdigest() for item in documents}

    replayed = _runtime(store).accept(
        routing_result=routing,
        proposal=copy.deepcopy(proposal),
        evidence_documents=documents,
    )
    assert replayed == accepted
    assert _financial_case(store, context) == gate4_before
    assert tuple(store.list_by_case_context(context)) == records_before


def test_non_authoritative_or_conflicting_proposal_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, context = _representative_case(tmp_path, monkeypatch)
    runtime = _runtime(store)
    routing = runtime.prepare(requirement=_requirement(), context=context)
    gate4_before = _financial_case(store, context)
    records_before = tuple(store.list_by_case_context(context))
    blog = Gate5ExternalEvidenceDocument(
        evidence_ref="blog-rate",
        source_url="https://example.com/tax-rate",
        media_type="text/html",
        content=b"non-authoritative commentary",
    )
    proposal = _proposal(routing=routing, documents=(blog,))
    proposal["evidence_refs"][0]["authority_kind"] = "tax_authority_primary"

    rejected = runtime.accept(
        routing_result=routing,
        proposal=proposal,
        evidence_documents=(blog,),
    )

    assert rejected["status"] == "rejected"
    assert "evidence_source_not_allowed" in rejected["validation"]["errors"]
    assert rejected["external_fact"] is None

    conflicting = _proposal(
        routing=routing,
        documents=_official_boundary_documents(),
    )
    conflicting["conflicting_values"] = [
        {
            **_rate_value(),
            "lower_rate_percent": "12.00",
            "amount_at_threshold": "288000.00",
        }
    ]
    rejected_conflict = runtime.accept(
        routing_result=routing,
        proposal=conflicting,
        evidence_documents=_official_boundary_documents(),
    )
    assert rejected_conflict["status"] == "rejected"
    assert "conflicting_evidence_values" in (rejected_conflict["validation"]["errors"])
    assert rejected_conflict["external_fact"] is None

    open_ended = _proposal(
        routing=routing,
        documents=_official_boundary_documents(),
    )
    open_ended["evidence_refs"][0]["effective_context"]["tax_period_to"] = None
    rejected_period = runtime.accept(
        routing_result=routing,
        proposal=open_ended,
        evidence_documents=_official_boundary_documents(),
    )
    assert rejected_period["status"] == "rejected"
    assert (
        "evidence_effective_period_mismatch"
        in (rejected_period["validation"]["errors"])
    )
    assert rejected_period["external_fact"] is None
    assert _financial_case(store, context) == gate4_before
    assert tuple(store.list_by_case_context(context)) == records_before


def test_unresolved_and_invalid_binding_never_create_a_fact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, context = _representative_case(tmp_path, monkeypatch)
    runtime = _runtime(store)
    routing = runtime.prepare(requirement=_requirement(), context=context)
    unresolved = {
        "schema_version": GATE5_EXTERNAL_EVIDENCE_PROPOSAL_SCHEMA_VERSION,
        "action": "unresolved",
        "research_request_sha256": routing["research_request_sha256"],
        "claim": None,
        "evidence_refs": [],
        "conflicting_values": [],
        "unresolved_reason": "authoritative effective-period evidence not found",
    }

    result = runtime.accept(
        routing_result=routing,
        proposal=unresolved,
        evidence_documents=(),
    )
    assert result["status"] == "unresolved"
    assert result["validation"] == {"status": "passed", "errors": []}
    assert result["external_fact"] is None

    wrong_binding = copy.deepcopy(unresolved)
    wrong_binding["research_request_sha256"] = "0" * 64
    rejected = runtime.accept(
        routing_result=routing,
        proposal=wrong_binding,
        evidence_documents=(),
    )
    assert rejected["status"] == "rejected"
    assert rejected["validation"]["errors"] == ["research_request_binding_mismatch"]
    assert rejected["external_fact"] is None


def test_contract_and_factory_keep_research_bounded_and_read_only() -> None:
    factory_source = inspect.getsource(Gate5ExternalEvidenceRuntimeFactory)
    runtime_source = inspect.getsource(Gate5ExternalEvidenceRuntime)
    module_source = inspect.getsource(evidence_module)
    tree = ast.parse(module_source)
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }

    assert "Gate5ExternalEvidenceRuntimeFactory.create" in FACTORY_REQUIRED
    assert "Gate4FinancialCaseRuntimeFactory.create" in FACTORY_REQUIRED[1]
    assert "Supplemental Fact" in FORBIDDEN[2]
    assert "Gate4FinancialCaseRuntimeFactory(" in factory_source
    assert "self._financial_case.read_case(" in runtime_source
    assert ".put(" not in runtime_source
    for forbidden in (
        "CanonicalReader",
        "FinancialAnnotations",
        "sqlite3",
        "Gate5SupplementalFactRuntimeFactory",
        "requests",
        "httpx",
    ):
        assert forbidden not in module_source
    assert imports.isdisjoint({"requests", "httpx", "openai"})

    response_format = gate5_external_evidence_proposal_response_format()
    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["strict"] is True
    schema = response_format["json_schema"]["schema"]
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {
        "schema_version",
        "action",
        "research_request_sha256",
        "claim",
        "evidence_refs",
        "conflicting_values",
        "unresolved_reason",
    }


def test_requirement_is_closed_to_the_declaration_driven_proof(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, context = _representative_case(tmp_path, monkeypatch)
    invalid = _requirement()
    invalid["entity"]["tax_period"] = "2024"

    with pytest.raises(Gate5ExternalEvidenceError) as caught:
        _runtime(store).prepare(requirement=invalid, context=context)

    assert caught.value.code == "gate5_external_evidence_requirement_invalid"


def _representative_case(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setitem(
        gate4_fixtures._FACT_SPEC_BY_TYPE,
        "SECURITY_DISPOSAL",
        (
            ("date", "11.02.2025"),
            ("asset", "ACME"),
            ("quantity", "1"),
            ("amount", "100,00"),
            ("currency", "RUB"),
            ("unit_price", "100,00"),
        ),
    )
    monkeypatch.setitem(
        gate4_fixtures._SOURCE_ROW_BY_TYPE,
        "SECURITY_DISPOSAL",
        "Продажа|11.02.2025|ACME|1|100,00|RUB|100,00",
    )
    config = ArtifactStoreConfig(
        mode="sqlite",
        sqlite_path=tmp_path / "artifacts.sqlite3",
        payload_root=tmp_path / "payloads",
    )
    store = ArtifactStoreFactory(config).create()
    context = ArtifactAccessContext(
        user_id="g5-external-evidence-user",
        normalization_run_id="g5-external-evidence-run-1",
        case_id="g5-external-evidence-case",
        workspace_model_id="broker-reports-ndfl",
        allow_private=True,
    )
    gate4_fixtures._publish_document(
        store=store,
        context=context,
        document_id="gate5-external-evidence-document",
        financial_types=("SECURITY_DISPOSAL",),
        sidecar_artifact_id="g3-v2-gate5-external-evidence",
        created_at="2026-08-09T18:00:00+00:00",
    )
    Gate4FinancialCaseRuntimeFactory(
        store=store,
        read_enabled=True,
    ).create().rebuild_case(context=context)
    return store, context


def _runtime(store) -> Gate5ExternalEvidenceRuntime:
    return Gate5ExternalEvidenceRuntimeFactory(
        store=store,
        read_enabled=True,
    ).create()


def _financial_case(store, context: ArtifactAccessContext):
    return (
        Gate4FinancialCaseRuntimeFactory(
            store=store,
            read_enabled=True,
        )
        .create()
        .read_case(context=context)
    )


def _requirement() -> dict:
    return {
        "schema_version": GATE5_EXTERNAL_EVIDENCE_REQUIREMENT_SCHEMA_VERSION,
        "requirement_id": "ru-ndfl-2025-group-02-rate-schedule",
        "fact_key": "resident_securities_income_group_rate_schedule",
        "entity": {
            "jurisdiction": "RU",
            "tax_period": "2025",
            "income_group_code": "02",
            "taxpayer_status": "resident_individual",
        },
        "declaration_binding": {"form": "3-NDFL", "knd": "1151020"},
    }


def _official_boundary_documents() -> tuple[Gate5ExternalEvidenceDocument, ...]:
    return (
        Gate5ExternalEvidenceDocument(
            evidence_ref="fns-order-913-page",
            source_url=ORDER_URL,
            media_type="text/html",
            content=b"synthetic boundary bytes for official order applicability",
        ),
        Gate5ExternalEvidenceDocument(
            evidence_ref="fns-order-913-procedure",
            source_url=PROCEDURE_URL,
            media_type=(
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document"
            ),
            content=b"synthetic boundary bytes for official procedure paragraph 48",
        ),
    )


def _proposal(
    *,
    routing: dict,
    documents: tuple[Gate5ExternalEvidenceDocument, ...],
) -> dict:
    refs = []
    for index, document in enumerate(documents):
        refs.append(
            {
                "evidence_ref": document.evidence_ref,
                "authority_kind": "tax_authority_primary",
                "source_url": document.source_url,
                "source_document_id": (
                    "FNS_ORDER_ED-7-11/913@"
                    if index == 0
                    else "FNS_ORDER_ED-7-11/913@_APPENDIX_2"
                ),
                "content_sha256": hashlib.sha256(document.content).hexdigest(),
                "locator": (
                    "item 3"
                    if index == 0
                    else "section V, paragraph 48, income group 02"
                ),
                "supports": (["effective_period"] if index == 0 else ["claim_value"]),
                "effective_context": {
                    "tax_period_from": "2025",
                    "tax_period_to": "2025",
                    "source_published_on": "2025-12-12",
                },
            }
        )
    return {
        "schema_version": GATE5_EXTERNAL_EVIDENCE_PROPOSAL_SCHEMA_VERSION,
        "action": "propose_fact",
        "research_request_sha256": routing["research_request_sha256"],
        "claim": {
            "fact_key": "resident_securities_income_group_rate_schedule",
            "entity": copy.deepcopy(routing["research_request"]["entity"]),
            "value": _rate_value(),
        },
        "evidence_refs": refs,
        "conflicting_values": [],
        "unresolved_reason": None,
    }


def _rate_value() -> dict[str, str]:
    return {
        "kind": "progressive_rate_schedule",
        "currency": "RUB",
        "threshold_amount": "2400000.00",
        "lower_rate_percent": "13.00",
        "amount_at_threshold": "312000.00",
        "excess_rate_percent": "15.00",
    }


def _role_values(fact: dict) -> dict[str, str]:
    return {
        role["role"]: role["value"]
        for role in fact["roles"]
        if role["status"] == "value"
    }
