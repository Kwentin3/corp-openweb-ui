from __future__ import annotations

import copy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import hashlib
import inspect
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
import pytest
from referencing import Registry, Resource

from broker_reports_gate1 import (
    ArtifactAccessContext,
    ArtifactStoreConfig,
    ArtifactStoreFactory,
    CASE_COMPLETE_FOR_CURRENT_INPUT_SET,
    CASE_INCOMPLETE,
    CanonicalArtifactStoreFactory,
    CanonicalNormalizerConfig,
    CanonicalNormalizerFactory,
    CanonicalReaderFactory,
    CanonicalStorageConfig,
    Gate4FinancialCaseCacheError,
    Gate4FinancialCaseMaterializationError,
    Gate4FinancialCaseRuntimeFactory,
    Gate4FinancialCaseSqlCacheFactory,
    build_retention_policy,
)
from broker_reports_gate1.artifact_lifecycle import lifecycle_for_visibility
from broker_reports_gate1.artifact_models import ArtifactRecord
from broker_reports_gate1.gate3_financial_annotations_persistence import (
    GATE3_FINANCIAL_ANNOTATIONS_ARTIFACT_TYPE,
)
from broker_reports_gate1.gate4_financial_case_cache import (
    FACTORY_REQUIRED as CACHE_FACTORY_REQUIRED,
    FORBIDDEN as CACHE_FORBIDDEN,
)
from broker_reports_gate1.gate4_financial_case_materialization import (
    FACTORY_REQUIRED as MATERIALIZER_FACTORY_REQUIRED,
    FORBIDDEN as MATERIALIZER_FORBIDDEN,
)


SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SERVICE_ROOT.parents[1]
CONTRACTS = REPO_ROOT / "docs" / "stage2" / "contracts"
MODEL_ID = "models/gemini-3.5-flash"

_SOURCE_ROWS = (
    "Покупка|10.01.2026|ACME|10|125,00|USD|12,50",
    "Продажа|11.02.2026|ACME|4|60,00|USD|15,00",
    "Дивиденд|12.03.2026|ACME|8,00|USD",
    "Комиссия|11.02.2026|1,25|USD",
    "Налог|12.03.2026|1,20|USD",
)
_FACT_SPECS = (
    (
        "SECURITY_PURCHASE",
        (
            ("date", "10.01.2026"),
            ("asset", "ACME"),
            ("quantity", "10"),
            ("amount", "125,00"),
            ("currency", "USD"),
            ("unit_price", "12,50"),
        ),
    ),
    (
        "SECURITY_DISPOSAL",
        (
            ("date", "11.02.2026"),
            ("asset", "ACME"),
            ("quantity", "4"),
            ("amount", "60,00"),
            ("currency", "USD"),
            ("unit_price", "15,00"),
        ),
    ),
    (
        "DIVIDEND_INCOME",
        (
            ("date", "12.03.2026"),
            ("amount", "8,00"),
            ("currency", "USD"),
            ("asset", "ACME"),
        ),
    ),
    (
        "TRANSACTION_CHARGE",
        (
            ("date", "11.02.2026"),
            ("amount", "1,25"),
            ("currency", "USD"),
            ("asset", None),
        ),
    ),
    (
        "TAX_WITHHELD",
        (
            ("date", "12.03.2026"),
            ("amount", "1,20"),
            ("currency", "USD"),
            ("asset", None),
        ),
    ),
)
_SOURCE_ROW_BY_TYPE = {
    financial_type: source_row
    for (financial_type, _), source_row in zip(
        _FACT_SPECS, _SOURCE_ROWS, strict=True
    )
}
_FACT_SPEC_BY_TYPE = dict(_FACT_SPECS)
_REPRESENTATIVE_FINANCIAL_TYPES = (
    "SECURITY_PURCHASE",
    "SECURITY_DISPOSAL",
    "DIVIDEND_INCOME",
    "TRANSACTION_CHARGE",
    "TAX_WITHHELD",
)


def _representative_downstream_consumer(*, runtime, context):
    current_case = runtime.read_case(context=context)
    by_type = {
        financial_type: tuple(
            runtime.list_by_financial_type(
                context=context,
                financial_type=financial_type,
            )
        )
        for financial_type in _REPRESENTATIVE_FINANCIAL_TYPES
    }
    by_asset = tuple(runtime.list_by_asset(context=context, asset="ACME"))
    by_period = tuple(
        runtime.list_by_period(
            context=context,
            date_from="2026-02-11",
            date_to="2026-03-12",
        )
    )
    selected = runtime.get_fact(
        context=context,
        fact_id=current_case.facts[0]["fact_id"],
    )
    return {
        "current_case": current_case,
        "by_type": by_type,
        "by_asset": by_asset,
        "by_period": by_period,
        "selected": selected,
    }


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


_FACT_SCHEMA = _read_json(
    CONTRACTS / "BROKER_REPORTS_GATE4_FINANCIAL_CASE_FACT.v1.schema.json"
)
_TARGET_SCHEMA = _read_json(
    CONTRACTS / "BROKER_REPORTS_GATE3_TARGET.v1.schema.json"
)
_REGISTRY = Registry().with_resource(
    _TARGET_SCHEMA["$id"], Resource.from_contents(_TARGET_SCHEMA)
)
_FACT_VALIDATOR = Draft202012Validator(
    _FACT_SCHEMA,
    registry=_REGISTRY,
    format_checker=FormatChecker(),
)


def test_materializes_five_representative_types_without_financial_inference(
    tmp_path: Path,
) -> None:
    store, context, document_id, canonical = _setup(tmp_path)
    sidecar = _persist_sidecar(
        store=store,
        context=context,
        document_id=document_id,
        canonical_version_id=canonical.canonical_version_id,
        artifact_id="g3-v2-representative-a",
        created_at="2026-08-08T10:00:00+00:00",
    )
    runtime = Gate4FinancialCaseRuntimeFactory(
        store=store,
        read_enabled=True,
    ).create()

    result = runtime.materialize_artifact(
        financial_annotations_artifact_id=sidecar.artifact_id,
        context=context,
    )

    assert [fact["financial_type"] for fact in result.facts] == [
        item[0] for item in _FACT_SPECS
    ]
    assert all(fact["status"] == "role_complete" for fact in result.facts)
    for fact in result.facts:
        _FACT_VALIDATOR.validate(fact)
        assert fact["gate3_binding"]["financial_annotations_artifact_id"] == (
            sidecar.artifact_id
        )
        assert fact["gate3_binding"]["canonical_binding"] == {
            "document_id": document_id,
            "canonical_version_id": canonical.canonical_version_id,
        }
    purchase = result.facts[0]
    assert _values(purchase) == {
        "date": "2026-01-10",
        "asset": "ACME",
        "quantity": "10",
        "amount": "125.00",
        "currency": "USD",
        "unit_price": "12.50",
    }
    charge = result.facts[3]
    assert _values(charge)["asset"] is None
    amount = next(item for item in charge["roles"] if item["role"] == "amount")
    assert amount["source_binding"]["source_literal"] == "1,25"
    assert amount["value"] == "1.25"


def test_required_missing_is_preserved_and_unsupported_value_fails_closed(
    tmp_path: Path,
) -> None:
    store, context, document_id, canonical = _setup(tmp_path)
    missing = _persist_sidecar(
        store=store,
        context=context,
        document_id=document_id,
        canonical_version_id=canonical.canonical_version_id,
        artifact_id="g3-v2-required-missing",
        created_at="2026-08-08T10:00:00+00:00",
        purchase_date=None,
    )
    runtime = Gate4FinancialCaseRuntimeFactory(
        store=store,
        read_enabled=True,
    ).create()
    facts = runtime.materialize_artifact(
        financial_annotations_artifact_id=missing.artifact_id,
        context=context,
    ).facts

    assert facts[0]["status"] == "role_incomplete"
    assert facts[0]["roles"][0] == {
        "role": "date",
        "requirement": "required",
        "status": "missing",
    }
    _FACT_VALIDATOR.validate(facts[0])

    cached = runtime.rebuild_artifact(
        financial_annotations_artifact_id=missing.artifact_id,
        context=context,
    )
    read_back = runtime.get_fact(
        context=context,
        fact_id=cached[0]["fact_id"],
    )
    assert read_back is not None
    assert read_back["status"] == "role_incomplete"
    assert read_back["roles"][0] == {
        "role": "date",
        "requirement": "required",
        "status": "missing",
    }

    invalid = _persist_sidecar(
        store=store,
        context=context,
        document_id=document_id,
        canonical_version_id=canonical.canonical_version_id,
        artifact_id="g3-v2-invalid-date",
        created_at="2026-08-08T10:01:00+00:00",
        purchase_date="10",
    )
    with pytest.raises(Gate4FinancialCaseMaterializationError) as failure:
        runtime.materialize_artifact(
            financial_annotations_artifact_id=invalid.artifact_id,
            context=context,
        )
    assert failure.value.code == "gate4_role_value_invalid"


def test_sql_queries_and_delete_rebuild_preserve_exact_facts(
    tmp_path: Path,
) -> None:
    store, context, document_id, canonical = _setup(tmp_path)
    sidecar = _persist_sidecar(
        store=store,
        context=context,
        document_id=document_id,
        canonical_version_id=canonical.canonical_version_id,
        artifact_id="g3-v2-cache-a",
        created_at="2026-08-08T10:00:00+00:00",
    )
    runtime = Gate4FinancialCaseRuntimeFactory(
        store=store,
        read_enabled=True,
    ).create()

    first = runtime.rebuild_artifact(
        financial_annotations_artifact_id=sidecar.artifact_id,
        context=context,
    )
    first_bytes = _canonical_json(first)
    first_ids = [fact["fact_id"] for fact in first]

    for financial_type in (
        "SECURITY_PURCHASE",
        "SECURITY_DISPOSAL",
        "DIVIDEND_INCOME",
        "TRANSACTION_CHARGE",
        "TAX_WITHHELD",
    ):
        selected = runtime.list_by_financial_type(
            context=context,
            financial_type=financial_type,
        )
        assert [fact["financial_type"] for fact in selected] == [financial_type]
    assert {
        fact["financial_type"]
        for fact in runtime.list_by_asset(context=context, asset="ACME")
    } == {
        "SECURITY_PURCHASE",
        "SECURITY_DISPOSAL",
        "DIVIDEND_INCOME",
    }
    assert {
        fact["financial_type"]
        for fact in runtime.list_by_period(
            context=context,
            date_from="2026-02-11",
            date_to="2026-02-11",
        )
    } == {"SECURITY_DISPOSAL", "TRANSACTION_CHARGE"}
    assert runtime.get_fact(context=context, fact_id=first_ids[0]) == first[0]

    runtime.clear_case_cache(context=context)
    with pytest.raises(Gate4FinancialCaseCacheError) as missing:
        runtime.list_facts(context=context)
    assert missing.value.code == "gate4_cache_missing"

    rebuilt = runtime.rebuild_artifact(
        financial_annotations_artifact_id=sidecar.artifact_id,
        context=context,
    )
    assert [fact["fact_id"] for fact in rebuilt] == first_ids
    assert _canonical_json(rebuilt) == first_bytes


def test_new_sidecar_and_new_canonical_never_reuse_old_current_cache(
    tmp_path: Path,
) -> None:
    store, context, document_id, canonical = _setup(tmp_path)
    first_sidecar = _persist_sidecar(
        store=store,
        context=context,
        document_id=document_id,
        canonical_version_id=canonical.canonical_version_id,
        artifact_id="g3-v2-stale-a",
        created_at="2026-08-08T10:00:00+00:00",
    )
    runtime = Gate4FinancialCaseRuntimeFactory(
        store=store,
        read_enabled=True,
    ).create()
    old = runtime.rebuild_artifact(
        financial_annotations_artifact_id=first_sidecar.artifact_id,
        context=context,
    )

    second_sidecar = _persist_sidecar(
        store=store,
        context=context,
        document_id=document_id,
        canonical_version_id=canonical.canonical_version_id,
        artifact_id="g3-v2-stale-b",
        created_at="2026-08-08T10:01:00+00:00",
    )
    with pytest.raises(Gate4FinancialCaseCacheError) as sidecar_stale:
        runtime.list_facts(context=context)
    assert sidecar_stale.value.code == "gate4_cache_stale"
    refreshed = runtime.rebuild_artifact(
        financial_annotations_artifact_id=second_sidecar.artifact_id,
        context=context,
    )
    assert {fact["fact_id"] for fact in refreshed}.isdisjoint(
        fact["fact_id"] for fact in old
    )

    replacement_context = replace(
        context,
        normalization_run_id="g4-runtime-run-2",
    )
    _activate_canonical(
        store=store,
        context=replacement_context,
        document_id=document_id,
        artifact_version=2,
        expected_previous_version_id=canonical.canonical_version_id,
    )
    with pytest.raises(Gate4FinancialCaseCacheError) as canonical_stale:
        runtime.get_fact(context=context, fact_id=refreshed[0]["fact_id"])
    assert canonical_stale.value.code == "gate4_cache_stale"


def test_cache_uses_existing_artifact_lifecycle_and_tenant_scope(
    tmp_path: Path,
) -> None:
    store, context, document_id, canonical = _setup(tmp_path)
    sidecar = _persist_sidecar(
        store=store,
        context=context,
        document_id=document_id,
        canonical_version_id=canonical.canonical_version_id,
        artifact_id="g3-v2-lifecycle-a",
        created_at="2026-08-08T10:00:00+00:00",
    )
    runtime = Gate4FinancialCaseRuntimeFactory(
        store=store,
        read_enabled=True,
    ).create()
    cached = runtime.rebuild_artifact(
        financial_annotations_artifact_id=sidecar.artifact_id,
        context=context,
    )

    different_tenant = replace(context, user_id="different-user")
    with pytest.raises(Gate4FinancialCaseCacheError) as denied:
        runtime.get_fact(
            context=different_tenant,
            fact_id=cached[0]["fact_id"],
        )
    assert denied.value.code == "gate4_cache_missing"

    store.purge_case(context)
    cache = Gate4FinancialCaseSqlCacheFactory(
        store=store,
        read_enabled=True,
    ).create()
    with cache._transactions.open(context=context, write=False) as repository:
        assert repository.generations() == ()


def test_case_assembly_combines_three_documents_and_keeps_duplicate_like_facts(
    tmp_path: Path,
) -> None:
    store, context = _store_context(tmp_path)
    published = (
        _publish_document(
            store=store,
            context=context,
            document_id="document-a",
            financial_types=(
                "SECURITY_PURCHASE",
                "SECURITY_DISPOSAL",
                "DIVIDEND_INCOME",
            ),
            sidecar_artifact_id="g3-v2-case-a",
            created_at="2026-08-08T10:00:00+00:00",
        ),
        _publish_document(
            store=store,
            context=context,
            document_id="document-b",
            financial_types=("DIVIDEND_INCOME", "TAX_WITHHELD"),
            sidecar_artifact_id="g3-v2-case-b",
            created_at="2026-08-08T10:01:00+00:00",
        ),
        _publish_document(
            store=store,
            context=context,
            document_id="document-c",
            financial_types=("TRANSACTION_CHARGE",),
            sidecar_artifact_id="g3-v2-case-c",
            created_at="2026-08-08T10:02:00+00:00",
        ),
    )
    runtime = Gate4FinancialCaseRuntimeFactory(
        store=store,
        read_enabled=True,
    ).create()

    assembled = runtime.rebuild_case(context=context)

    assert assembled.status == CASE_COMPLETE_FOR_CURRENT_INPUT_SET
    assert assembled.gate3_case_status == "ready_for_gate4_handoff"
    assert [source.document_id for source in assembled.sources] == [
        "document-a",
        "document-b",
        "document-c",
    ]
    assert all(source.status == "CURRENT_GATE3_V2" for source in assembled.sources)
    assert len(assembled.facts) == 6
    assert {
        financial_type: sum(
            fact["financial_type"] == financial_type
            for fact in assembled.facts
        )
        for financial_type in _FACT_SPEC_BY_TYPE
    } == {
        "SECURITY_PURCHASE": 1,
        "SECURITY_DISPOSAL": 1,
        "DIVIDEND_INCOME": 2,
        "TRANSACTION_CHARGE": 1,
        "TAX_WITHHELD": 1,
    }
    dividends = [
        fact
        for fact in assembled.facts
        if fact["financial_type"] == "DIVIDEND_INCOME"
    ]
    assert [_values(fact) for fact in dividends] == [
        {
            "date": "2026-03-12",
            "amount": "8.00",
            "currency": "USD",
            "asset": "ACME",
        },
        {
            "date": "2026-03-12",
            "amount": "8.00",
            "currency": "USD",
            "asset": "ACME",
        },
    ]
    assert len({fact["fact_id"] for fact in dividends}) == 2
    assert {
        fact["gate3_binding"]["canonical_binding"]["document_id"]
        for fact in dividends
    } == {"document-a", "document-b"}
    assert {
        fact["gate3_binding"]["financial_annotations_artifact_id"]
        for fact in assembled.facts
    } == {item[2].artifact_id for item in published}
    for fact in assembled.facts:
        _FACT_VALIDATOR.validate(fact)

    consumer_result = _representative_downstream_consumer(
        runtime=runtime,
        context=context,
    )
    assert consumer_result["current_case"] == assembled
    assert tuple(runtime.list_facts(context=context)) == assembled.facts
    for financial_type, expected_count in (
        ("SECURITY_PURCHASE", 1),
        ("SECURITY_DISPOSAL", 1),
        ("DIVIDEND_INCOME", 2),
        ("TRANSACTION_CHARGE", 1),
        ("TAX_WITHHELD", 1),
    ):
        assert len(consumer_result["by_type"][financial_type]) == expected_count
    assert {
        fact["financial_type"] for fact in consumer_result["by_asset"]
    } == {
        "SECURITY_PURCHASE",
        "SECURITY_DISPOSAL",
        "DIVIDEND_INCOME",
    }
    assert {
        fact["financial_type"] for fact in consumer_result["by_period"]
    } == {
        "SECURITY_DISPOSAL",
        "DIVIDEND_INCOME",
        "TRANSACTION_CHARGE",
        "TAX_WITHHELD",
    }

    selected = consumer_result["selected"]
    assert selected is not None
    for field in (
        "fact_id",
        "financial_type",
        "roles",
        "status",
        "annotation_target",
        "gate3_binding",
    ):
        assert field in selected
    assert selected["status"] == "role_complete"
    assert selected["gate3_binding"]["financial_annotations_artifact_id"]
    assert selected["gate3_binding"]["canonical_binding"]["document_id"]
    for role in selected["roles"]:
        if role["status"] == "value":
            assert role["source_binding"]["target"]
            assert role["source_binding"]["source_literal"]

    consumer_source = inspect.getsource(_representative_downstream_consumer)
    for required_read in (
        "runtime.read_case",
        "runtime.list_by_financial_type",
        "runtime.list_by_asset",
        "runtime.list_by_period",
        "runtime.get_fact",
    ):
        assert required_read in consumer_source
    for forbidden_dependency in (
        "CanonicalReader",
        "Gate3",
        "sqlite3",
        "gate4_financial_case_fact_cache_v1",
        "gate4_financial_case_cache_generation_v1",
        "broker parser",
    ):
        assert forbidden_dependency not in consumer_source


def test_case_rebuild_is_order_independent_and_byte_deterministic(
    tmp_path: Path,
) -> None:
    store, context = _store_context(tmp_path)
    for document_id, financial_type, created_at in (
        ("document-c", "TRANSACTION_CHARGE", "2026-08-08T10:02:00+00:00"),
        ("document-a", "SECURITY_PURCHASE", "2026-08-08T10:00:00+00:00"),
        ("document-b", "DIVIDEND_INCOME", "2026-08-08T10:01:00+00:00"),
    ):
        _publish_document(
            store=store,
            context=context,
            document_id=document_id,
            financial_types=(financial_type,),
            sidecar_artifact_id=f"g3-v2-rebuild-{document_id}",
            created_at=created_at,
        )
    runtime = Gate4FinancialCaseRuntimeFactory(
        store=store,
        read_enabled=True,
    ).create()

    first = runtime.rebuild_case(context=context)
    first_bytes = _canonical_json(first.facts)
    first_ids = tuple(fact["fact_id"] for fact in first.facts)
    assert [source.document_id for source in first.sources] == [
        "document-a",
        "document-b",
        "document-c",
    ]

    runtime.clear_case_cache(context=context)
    with pytest.raises(Gate4FinancialCaseCacheError) as missing:
        runtime.read_case(context=context)
    assert missing.value.code == "gate4_cache_missing"

    rebuilt = runtime.rebuild_case(context=context)
    assert tuple(fact["fact_id"] for fact in rebuilt.facts) == first_ids
    assert _canonical_json(rebuilt.facts) == first_bytes
    assert rebuilt == first


def test_case_completeness_is_technical_and_reports_not_ready_documents(
    tmp_path: Path,
) -> None:
    store, context = _store_context(tmp_path)
    _publish_document(
        store=store,
        context=context,
        document_id="document-ready",
        financial_types=("SECURITY_PURCHASE",),
        sidecar_artifact_id="g3-v2-incomplete-ready",
        created_at="2026-08-08T10:00:00+00:00",
    )
    not_ready_context = replace(
        context,
        normalization_run_id="g4-case-document-not-ready-v1",
    )
    _activate_canonical(
        store=store,
        context=not_ready_context,
        document_id="document-not-ready",
        artifact_version=1,
        expected_previous_version_id=None,
        source_rows=(_SOURCE_ROW_BY_TYPE["DIVIDEND_INCOME"],),
    )
    runtime = Gate4FinancialCaseRuntimeFactory(
        store=store,
        read_enabled=True,
    ).create()

    assembled = runtime.rebuild_case(context=context)

    assert assembled.status == CASE_INCOMPLETE
    assert assembled.gate3_case_status == "gate3_incomplete"
    assert len(assembled.facts) == 1
    states = {source.document_id: source for source in assembled.sources}
    assert states["document-ready"].status == "CURRENT_GATE3_V2"
    assert states["document-not-ready"].status == "NOT_READY"
    assert states["document-not-ready"].reason_codes == (
        "GATE3_ANNOTATIONS_MISSING",
    )
    assert states["document-not-ready"].canonical_version_id is not None
    assert states["document-not-ready"].financial_annotations_artifact_id is None


def test_new_current_document_makes_case_stale_until_whole_case_rebuild(
    tmp_path: Path,
) -> None:
    store, context = _store_context(tmp_path)
    for document_id, financial_type in (
        ("document-a", "SECURITY_PURCHASE"),
        ("document-b", "DIVIDEND_INCOME"),
    ):
        _publish_document(
            store=store,
            context=context,
            document_id=document_id,
            financial_types=(financial_type,),
            sidecar_artifact_id=f"g3-v2-add-{document_id}",
            created_at="2026-08-08T10:00:00+00:00",
        )
    runtime = Gate4FinancialCaseRuntimeFactory(
        store=store,
        read_enabled=True,
    ).create()
    first = runtime.rebuild_case(context=context)
    assert len(first.facts) == 2

    _publish_document(
        store=store,
        context=context,
        document_id="document-c",
        financial_types=("TRANSACTION_CHARGE",),
        sidecar_artifact_id="g3-v2-add-document-c",
        created_at="2026-08-08T10:01:00+00:00",
    )
    with pytest.raises(Gate4FinancialCaseCacheError) as stale_case:
        runtime.read_case(context=context)
    assert stale_case.value.code == "gate4_cache_stale"
    with pytest.raises(Gate4FinancialCaseCacheError) as stale_query:
        runtime.list_facts(context=context)
    assert stale_query.value.code == "gate4_cache_stale"

    rebuilt = runtime.rebuild_case(context=context)
    assert rebuilt.status == CASE_COMPLETE_FOR_CURRENT_INPUT_SET
    assert len(rebuilt.facts) == 3
    assert {
        fact["financial_type"] for fact in rebuilt.facts
    } == {
        "SECURITY_PURCHASE",
        "DIVIDEND_INCOME",
        "TRANSACTION_CHARGE",
    }


def test_replaced_canonical_and_sidecar_replace_old_case_facts(
    tmp_path: Path,
) -> None:
    store, context = _store_context(tmp_path)
    _document_context, first_canonical, _first_sidecar = _publish_document(
        store=store,
        context=context,
        document_id="document-a",
        financial_types=("SECURITY_PURCHASE",),
        sidecar_artifact_id="g3-v2-replace-a-v1",
        created_at="2026-08-08T10:00:00+00:00",
    )
    runtime = Gate4FinancialCaseRuntimeFactory(
        store=store,
        read_enabled=True,
    ).create()
    first = runtime.rebuild_case(context=context)
    first_ids = {fact["fact_id"] for fact in first.facts}

    replacement_context = replace(
        context,
        normalization_run_id="g4-case-document-a-v2",
    )
    replacement = _activate_canonical(
        store=store,
        context=replacement_context,
        document_id="document-a",
        artifact_version=2,
        expected_previous_version_id=first_canonical.canonical_version_id,
        source_rows=(_SOURCE_ROW_BY_TYPE["SECURITY_PURCHASE"],),
    )
    with pytest.raises(Gate4FinancialCaseCacheError) as canonical_stale:
        runtime.read_case(context=context)
    assert canonical_stale.value.code == "gate4_cache_stale"

    _persist_sidecar(
        store=store,
        context=replacement_context,
        document_id="document-a",
        canonical_version_id=replacement.canonical_version_id,
        artifact_id="g3-v2-replace-a-v2",
        created_at="2026-08-08T10:01:00+00:00",
        fact_specs=((
            "SECURITY_PURCHASE",
            _FACT_SPEC_BY_TYPE["SECURITY_PURCHASE"],
        ),),
    )
    with pytest.raises(Gate4FinancialCaseCacheError) as sidecar_stale:
        runtime.list_facts(context=context)
    assert sidecar_stale.value.code == "gate4_cache_stale"

    rebuilt = runtime.rebuild_case(context=context)
    assert rebuilt.status == CASE_COMPLETE_FOR_CURRENT_INPUT_SET
    assert {fact["fact_id"] for fact in rebuilt.facts}.isdisjoint(first_ids)
    assert {
        fact["gate3_binding"]["canonical_binding"]["canonical_version_id"]
        for fact in rebuilt.facts
    } == {replacement.canonical_version_id}


def test_expired_document_follows_existing_lifecycle_without_ghost_facts(
    tmp_path: Path,
) -> None:
    store, context = _store_context(tmp_path)
    _publish_document(
        store=store,
        context=context,
        document_id="document-a",
        financial_types=("SECURITY_PURCHASE",),
        sidecar_artifact_id="g3-v2-expire-a",
        created_at="2026-08-08T10:00:00+00:00",
    )
    document_b_context, _canonical_b, _sidecar_b = _publish_document(
        store=store,
        context=context,
        document_id="document-b",
        financial_types=("DIVIDEND_INCOME",),
        sidecar_artifact_id="g3-v2-expire-b",
        created_at="2026-08-08T10:01:00+00:00",
    )
    runtime = Gate4FinancialCaseRuntimeFactory(
        store=store,
        read_enabled=True,
    ).create()
    first = runtime.rebuild_case(context=context)
    expired_ids = {
        fact["fact_id"]
        for fact in first.facts
        if fact["gate3_binding"]["canonical_binding"]["document_id"]
        == "document-b"
    }
    assert expired_ids

    expired = store.expire_run(
        document_b_context,
        now=datetime.now(timezone.utc) + timedelta(days=8),
    )
    assert expired.records_changed > 0

    current = runtime.read_case(context=context)
    assert current.status == CASE_INCOMPLETE
    assert current.gate3_case_status == "gate3_incomplete"
    states = {source.document_id: source.status for source in current.sources}
    assert states == {
        "document-a": "CURRENT_GATE3_V2",
        "document-b": "NOT_READY",
    }
    assert {fact["fact_id"] for fact in current.facts}.isdisjoint(expired_ids)
    assert {
        fact["gate3_binding"]["canonical_binding"]["document_id"]
        for fact in current.facts
    } == {"document-a"}


def test_factory_closed_world_and_non_goal_guards() -> None:
    assert "Gate4FinancialCaseMaterializerFactory.create" in (
        MATERIALIZER_FACTORY_REQUIRED
    )
    assert "Gate4FinancialCaseRuntimeFactory.create" in CACHE_FACTORY_REQUIRED
    assert "ArtifactStore" in CACHE_FACTORY_REQUIRED
    assert "LLM" in MATERIALIZER_FORBIDDEN
    assert "second database" in CACHE_FORBIDDEN
    assert "deduplicate" in CACHE_FORBIDDEN
    assert "reconcile" in CACHE_FORBIDDEN

    materializer_source = (
        SERVICE_ROOT
        / "broker_reports_gate1"
        / "gate4_financial_case_materialization.py"
    ).read_text(encoding="utf-8")
    cache_source = (
        SERVICE_ROOT
        / "broker_reports_gate1"
        / "gate4_financial_case_cache.py"
    ).read_text(encoding="utf-8")
    bundle_builder = (
        SERVICE_ROOT / "scripts" / "build_openwebui_pipe_bundle.py"
    ).read_text(encoding="utf-8")
    assert "Gate3RoleValueResolverFactory.create_from_active_canonical" in (
        materializer_source
    )
    assert "Gate3FinancialRolePackFactory.create" in materializer_source
    assert "Gate3NdflCaseReadinessFactory" in cache_source
    assert "def rebuild_case(" in cache_source
    assert "def read_case(" in cache_source
    assert "repository.replace_case" in cache_source
    assert cache_source.count("CREATE TABLE IF NOT EXISTS") == 2
    assert cache_source.count("CREATE INDEX IF NOT EXISTS") == 3
    assert "self._store.sqlite_path" in cache_source
    assert "process.env" not in cache_source
    for forbidden_source_marker in (
        "pdf",
        "csv",
        "xlsx",
        "raw_report",
        "source_payload",
    ):
        assert forbidden_source_marker not in cache_source.casefold()
        assert forbidden_source_marker not in materializer_source.casefold()
    assert '"gate4_financial_case_materialization"' in bundle_builder
    assert '"gate4_financial_case_cache"' in bundle_builder


def test_g46_confirms_existing_runtime_as_the_only_read_boundary() -> None:
    contract = (
        CONTRACTS / "BROKER_REPORTS_GATE4_SQL_MATERIALIZATION.v1.md"
    ).read_text(encoding="utf-8")
    pipeline = (
        CONTRACTS / "BROKER_REPORTS_PIPELINE_GATES.v1.md"
    ).read_text(encoding="utf-8")
    authority = (
        CONTRACTS / "BROKER_REPORTS_ARCHITECTURE_AUTHORITIES.md"
    ).read_text(encoding="utf-8")
    closure = (
        REPO_ROOT
        / "docs"
        / "reports"
        / "2026-08-08"
        / "BROKER_REPORTS_GATE4_READ_BOUNDARY_G4_6_CLOSURE.report.md"
    ).read_text(encoding="utf-8")
    runtime_source = (
        SERVICE_ROOT
        / "broker_reports_gate1"
        / "gate4_financial_case_cache.py"
    ).read_text(encoding="utf-8")

    for marker in (
        "G4.6_CLOSED — NO_NEW_READ_LAYER_REQUIRED",
        "Gate4FinancialCaseRuntimeFactory.create",
        "read_case(context)",
        "get_fact(context, fact_id)",
        "list_by_financial_type(context, financial_type)",
        "list_by_asset(context, asset)",
        "list_by_period(context, date_from, date_to)",
        "physical SQL cache",
    ):
        assert marker in contract or marker in pipeline or marker in closure
    assert "Gate 4 SQL cache rebuild and explicit reads" in authority
    assert "Gate4FinancialCaseRuntimeFactory.create" in authority
    assert "NO_NEW_READ_LAYER_REQUIRED" in pipeline
    assert "NEXT_ALLOWED_GOAL = G4.7_REPRESENTATIVE_INTEGRATION_PROOF" in closure
    for forbidden_framework_marker in (
        "class Gate4FinancialCaseReadModel",
        "class Gate4FinancialCaseRepository",
        "class QuerySpec",
        "class FilterExpression",
        "class QueryPlanner",
    ):
        assert forbidden_framework_marker not in runtime_source


def _setup(tmp_path: Path):
    store, context = _store_context(tmp_path)
    document_id = "g4-runtime-document"
    canonical = _activate_canonical(
        store=store,
        context=context,
        document_id=document_id,
        artifact_version=1,
        expected_previous_version_id=None,
    )
    return store, context, document_id, canonical


def _store_context(tmp_path: Path):
    store = ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=tmp_path / "artifacts.sqlite3",
            payload_root=tmp_path / "payloads",
        )
    ).create()
    context = ArtifactAccessContext(
        user_id="g4-runtime-user",
        normalization_run_id="g4-runtime-run-1",
        case_id="g4-runtime-case",
        workspace_model_id="broker-reports-ndfl",
        allow_private=True,
    )
    return store, context


def _publish_document(
    *,
    store,
    context: ArtifactAccessContext,
    document_id: str,
    financial_types: tuple[str, ...],
    sidecar_artifact_id: str,
    created_at: str,
):
    document_context = replace(
        context,
        normalization_run_id=f"g4-case-{document_id}-v1",
    )
    fact_specs = tuple(
        (financial_type, _FACT_SPEC_BY_TYPE[financial_type])
        for financial_type in financial_types
    )
    canonical = _activate_canonical(
        store=store,
        context=document_context,
        document_id=document_id,
        artifact_version=1,
        expected_previous_version_id=None,
        source_rows=tuple(
            _SOURCE_ROW_BY_TYPE[financial_type]
            for financial_type in financial_types
        ),
    )
    sidecar = _persist_sidecar(
        store=store,
        context=document_context,
        document_id=document_id,
        canonical_version_id=canonical.canonical_version_id,
        artifact_id=sidecar_artifact_id,
        created_at=created_at,
        fact_specs=fact_specs,
    )
    return document_context, canonical, sidecar


def _activate_canonical(
    *,
    store,
    context: ArtifactAccessContext,
    document_id: str,
    artifact_version: int,
    expected_previous_version_id: str | None,
    source_rows: tuple[str, ...] = _SOURCE_ROWS,
):
    retention = build_retention_policy(mode="api_smoke")
    source_ref = f"g4-runtime-source-{document_id}-{artifact_version}"
    store.put_record(
        ArtifactRecord(
            artifact_id=source_ref,
            artifact_type="source_file_ref_v0",
            case_id=context.case_id,
            chat_id=None,
            user_id=context.user_id,
            workspace_model_id=context.workspace_model_id,
            normalization_run_id=context.normalization_run_id,
            document_id=document_id,
            source_file_ref={
                "openwebui_file_id": (
                    f"synthetic-g4-file-{document_id}-{artifact_version}"
                )
            },
            visibility="private_case",
            storage_backend="project_artifact_payload",
            retention_policy=retention,
            access_policy={"requires_user_id": True},
            validation_status="validated",
            lifecycle_status=lifecycle_for_visibility(
                visibility="private_case",
                validation_status="validated",
            ),
            payload={"synthetic": True},
        )
    )
    normalizer = CanonicalNormalizerFactory(
        CanonicalNormalizerConfig(
            normalizer_version=f"g4-runtime-test-v{artifact_version}"
        )
    ).create()
    artifact = normalizer.build(
        tenant_id=context.user_id,
        artifact_version=artifact_version,
        document={
            "container_format": "html_text",
            "sha256": hashlib.sha256(
                f"g4-runtime-{document_id}-{artifact_version}".encode("utf-8")
            ).hexdigest(),
            "declared_mime_type": "text/html",
        },
        source_artifact_ref=source_ref,
        source_payloads=[
            {
                "canonical_projection": {
                    "blocks": [
                        {
                            "kind": "text",
                            "text": text,
                            "source_location": {"block_index": index},
                        }
                        for index, text in enumerate(source_rows, start=1)
                    ]
                }
            }
        ],
        source_units=[],
        table_projections=[],
    )
    canonical = CanonicalArtifactStoreFactory(
        store=store,
        config=CanonicalStorageConfig(capacity_check_enabled=False),
    ).create().put_candidate(
        artifact=artifact,
        context=context,
        retention_policy=retention,
        compare_receipt=None,
    )
    CanonicalReaderFactory(store=store, read_enabled=True).create().activate(
        canonical_version_id=canonical.canonical_version_id,
        expected_previous_version_id=expected_previous_version_id,
        context=context,
        actor="g4-runtime-test",
        reason="G4.2 deterministic cache test",
    )
    return canonical


def _persist_sidecar(
    *,
    store,
    context: ArtifactAccessContext,
    document_id: str,
    canonical_version_id: str,
    artifact_id: str,
    created_at: str,
    purchase_date: str | None = "10.01.2026",
    fact_specs: tuple = _FACT_SPECS,
) -> ArtifactRecord:
    envelope = CanonicalReaderFactory(
        store=store,
        read_enabled=True,
    ).create().read_active_envelope(document_id, context)
    nodes = envelope.artifact["nodes"]
    assert len(nodes) >= len(fact_specs)
    annotations = []
    for index, (financial_type, role_specs) in enumerate(fact_specs):
        target = {"kind": "node", "node_id": nodes[index]["node_id"]}
        roles = []
        for role, literal in role_specs:
            if financial_type == "SECURITY_PURCHASE" and role == "date":
                literal = purchase_date
            if literal is None:
                roles.append({"role": role, "status": "missing"})
            else:
                roles.append(
                    {
                        "role": role,
                        "status": "bound",
                        "target": copy.deepcopy(target),
                        "exact_text": literal,
                    }
                )
        annotations.append(
            {
                "target": target,
                "financial_label": financial_type,
                "roles": roles,
            }
        )
    payload = {
        "schema_version": "broker_reports_financial_annotations_v2",
        "canonical_binding": {
            "document_id": document_id,
            "canonical_version_id": canonical_version_id,
        },
        "dictionary_identity": {
            "dictionary_id": "broker-reports-financial-labels",
            "semantic_version": "1.0.0",
        },
        "role_pack_identity": {
            "role_pack_id": "broker-reports-financial-roles",
            "semantic_version": "1.0.0",
        },
        "instruction_identity": {
            "instruction_id": "broker-reports-bounded-semantic-labeling",
            "semantic_version": "1.0.1",
        },
        "role_instruction_identity": {
            "instruction_id": "broker-reports-source-bound-role-labeling",
            "semantic_version": "1.0.0",
        },
        "model_identity": {"model_id": MODEL_ID},
        "annotations": annotations,
        "validation_status": "validated",
    }
    return store.put_record(
        ArtifactRecord(
            artifact_id=artifact_id,
            artifact_type=GATE3_FINANCIAL_ANNOTATIONS_ARTIFACT_TYPE,
            case_id=context.case_id,
            chat_id=context.chat_id,
            user_id=context.user_id,
            workspace_model_id=context.workspace_model_id,
            normalization_run_id=context.normalization_run_id,
            document_id=document_id,
            source_file_ref=None,
            visibility="private_case",
            storage_backend="project_artifact_payload",
            retention_policy=build_retention_policy(mode="api_smoke"),
            access_policy={
                "requires_user_id": True,
                "requires_case_or_chat": True,
                "requires_workspace_model_id_when_present": True,
                "financial_annotations_sidecar_only": True,
            },
            validation_status="validated",
            lifecycle_status=lifecycle_for_visibility(
                visibility="private_case",
                validation_status="validated",
            ),
            payload_kind="json_file",
            payload=payload,
            safe_metadata={
                "provider_profile_id": "google_gemini",
                "document_completion_status": "complete",
                "annotations_total": len(annotations),
            },
            created_at=created_at,
            updated_at=created_at,
        )
    )


def _values(fact: dict) -> dict[str, str | None]:
    return {
        item["role"]: item.get("value")
        for item in fact["roles"]
    }


def _canonical_json(value) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
