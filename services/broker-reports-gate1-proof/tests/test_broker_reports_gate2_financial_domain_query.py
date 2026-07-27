from __future__ import annotations

import ast
import copy
import json
import sys
from dataclasses import replace
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from broker_reports_gate1.gate2_financial_domain_catalog import (  # noqa: E402
    Gate2FinancialDomainCatalogFactory,
)
from broker_reports_gate1.gate2_financial_domain_contracts import (  # noqa: E402
    FINANCIAL_DOMAIN_QUERY_POLICY_VERSION,
    FINANCIAL_DOMAIN_QUERY_SCHEMA_VERSION,
    FINANCIAL_DOMAIN_SNAPSHOT_SCHEMA_VERSION,
    FinancialDomainAccessContext,
    FinancialDomainQueryFilters,
    Gate2FinancialDomainError,
    canonical_json,
    sha256_json,
    validate_financial_domain_query_response,
)
from broker_reports_gate1.gate2_financial_domain_query import (  # noqa: E402
    Gate2FinancialDomainQuery,
    Gate2FinancialDomainQueryFactory,
)
from broker_reports_gate1.gate3_financial_domain_context import (  # noqa: E402
    Gate3FinancialDomainContextConsumer,
    Gate3FinancialDomainContextError,
    Gate3FinancialDomainContextFactory,
)
from broker_reports_gate1.gate2_financial_domain_projection import (  # noqa: E402,E501
    snapshot_integrity_material as _snapshot_integrity_material,
)
from broker_reports_gate1.gate2_financial_evidence_catalog import (  # noqa: E402
    SUPPORTED_SOURCE_FAMILIES,
)
from broker_reports_gate1.gate2_financial_evidence_decision import (  # noqa: E402
    FinancialEvidenceDecisionPackage,
    FinancialEvidenceValueCandidate,
    Gate2FinancialEvidenceDecisionContractFactory,
)
from broker_reports_gate1.gate2_financial_evidence_materialization import (  # noqa: E402,E501
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


BOUNDARY_MODULE_PATHS = (
    ROOT / "broker_reports_gate1" / "gate2_financial_domain_contracts.py",
    ROOT / "broker_reports_gate1" / "gate2_financial_domain_projection.py",
    ROOT / "broker_reports_gate1" / "gate2_financial_domain_validation.py",
    ROOT / "broker_reports_gate1" / "gate2_financial_domain_catalog.py",
    ROOT / "broker_reports_gate1" / "gate2_financial_domain_query.py",
)
ACCESS_CONTEXT = FinancialDomainAccessContext(
    user_ref="user:synthetic",
    case_ref="case:synthetic",
    workspace_ref="workspace:synthetic",
)
ACCESS_SCOPE_FINGERPRINT = (
    ACCESS_CONTEXT.access_scope().access_scope_fingerprint
)
CONTINUATION_KEY = b"synthetic-server-continuation-key-32-bytes"
SNAPSHOT_AUTHORITY_KEY = (
    b"synthetic-server-snapshot-authority-key-32-bytes"
)
CREATED_AT = "2026-07-26T00:00:00+00:00"
MANAGED_DOMAIN_SCHEMA = (
    ROOT.parents[1]
    / "docs"
    / "stage2"
    / "contracts"
    / "BROKER_REPORTS_MANAGED_FINANCIAL_DOMAIN.v1.schema.json"
)

_DEFINITIONS = (
    ("amount", "source_decimal", "-120.50", ("amount",)),
    ("date", "source_date", "2025-12-31", ("as_of_date",)),
    (
        "scope",
        "source_reference",
        "Synthetic statement",
        ("statement_scope",),
    ),
    (
        "printed-label",
        "source_reference",
        "Synthetic printed total",
        ("printed_label_evidence_ref",),
    ),
    ("period", "source_period", "2025 Q4", ("period",)),
    ("currency", "source_currency", "RUB", ("currency",)),
    (
        "label",
        "source_text",
        "Synthetic literal marker",
        ("source_label",),
    ),
)


def _registry():
    return Gate2FinancialEvidenceRegistryFactory().create()


def _source_values(suffix: str):
    return tuple(
        FinancialEvidenceAuthoritativeSourceValue(
            source_value_ref=f"value:{name}:{suffix}",
            source_ref=f"source:cell:{name}:{suffix}",
            value_type=value_type,
            literal_value=literal_value,
            source_evidence_refs=(
                f"evidence:table:{suffix}",
                f"evidence:cell:{name}:{suffix}",
            ),
            lineage=FinancialEvidenceSourceLineage(
                document_ref=f"document:synthetic:{suffix}",
                page_ref=f"page:{suffix}:1",
                table_ref=f"table:{suffix}:1",
                row_ref=f"row:{suffix}:{index}",
                cell_ref=f"cell:{suffix}:{index}",
            ),
        )
        for index, (
            name,
            value_type,
            literal_value,
            _,
        ) in enumerate(_DEFINITIONS, start=1)
    )


def _candidates(suffix: str):
    return tuple(
        FinancialEvidenceValueCandidate(
            source_value_ref=f"value:{name}:{suffix}",
            source_ref=f"source:cell:{name}:{suffix}",
            value_type=value_type,
            allowed_roles=allowed_roles,
        )
        for name, value_type, _, allowed_roles in _DEFINITIONS
    )


def _source_package(suffix: str):
    return Gate2FinancialEvidenceSourcePackageFactory(
        package_ref=f"source-package:synthetic:{suffix}",
        normalization_run_ref=f"normalization:synthetic:{suffix}",
        document_ref=f"document:synthetic:{suffix}",
        source_scope_ref=f"scope:table:{suffix}",
        source_family_id=SUPPORTED_SOURCE_FAMILIES[0],
        source_values=_source_values(suffix),
        source_evidence_refs=(
            f"evidence:document:{suffix}",
            f"evidence:table:{suffix}",
        ),
        completeness="complete",
        restriction_codes=(),
        issue_refs=(),
    ).create()


def _decision(status: str, suffix: str):
    if status == "cash":
        return {
            "decision": {
                "disposition": "typed_input",
                "input_type_id": "cash_balance_snapshot_v1",
                "value_bindings": {
                    "amount": f"value:amount:{suffix}",
                    "as_of_date": f"value:date:{suffix}",
                    "statement_scope": f"value:scope:{suffix}",
                    "balance_class": None,
                    "currency": f"value:currency:{suffix}",
                    "source_label": f"value:label:{suffix}",
                    "unit": None,
                },
                "reason_code": "typed_supported",
            }
        }
    if status == "unclassified":
        return {
            "decision": {
                "disposition": "unclassified_financial_input",
                "value_bindings": [
                    {
                        "role_id": allowed_roles[0],
                        "source_value_ref": f"value:{name}:{suffix}",
                    }
                    for name, _, _, allowed_roles in _DEFINITIONS
                ],
                "reason_code": "no_registry_type",
            }
        }
    if status == "no_financial":
        return {
            "decision": {
                "disposition": "no_financial_input",
                "reason_code": "non_financial_content",
            }
        }
    return {
        "decision": {
            "disposition": "unsupported",
            "reason_code": "source_shape_unsupported",
        }
    }


def _case(status: str, suffix: str):
    registry = _registry()
    source_package = _source_package(suffix)
    decision_package = FinancialEvidenceDecisionPackage(
        source_scope_ref=source_package.source_scope_ref,
        source_family_id=source_package.source_family_id,
        candidates=_candidates(suffix),
    )
    contract = Gate2FinancialEvidenceDecisionContractFactory(
        registry=registry,
        package=decision_package,
    ).create()
    validated = Gate2FinancialEvidenceValidatedDecisionFactory(
        contract=contract
    ).create(_decision(status, suffix))
    artifact = Gate2FinancialEvidenceMaterializerFactory(
        registry=registry,
        source_package=source_package,
        execution_metadata=FinancialEvidenceExecutionMetadata(
            execution_ref=f"execution:synthetic:{suffix}",
            decision_validation_ref=f"validation:synthetic:{suffix}",
        ),
    ).create().materialize(validated_decision=validated)
    return artifact, source_package


def _domain(*, prefix: str = ""):
    registry = _registry()
    cases = (
        _case("cash", f"{prefix}cash"),
        _case("unclassified", f"{prefix}unclassified"),
        _case("no_financial", f"{prefix}none"),
        _case("unsupported", f"{prefix}unsupported"),
    )
    snapshot = Gate2FinancialDomainCatalogFactory(
        registry=registry,
        snapshot_authority_key=SNAPSHOT_AUTHORITY_KEY,
    ).create(
        materialized_artifacts=tuple(item[0] for item in cases),
        source_packages=tuple(item[1] for item in cases),
        access_context=ACCESS_CONTEXT,
        created_at=CREATED_AT,
        expires_at=None,
    )
    query = Gate2FinancialDomainQueryFactory(
        snapshot=snapshot,
        registry=registry,
        access_context=ACCESS_CONTEXT,
        snapshot_authority_key=SNAPSHOT_AUTHORITY_KEY,
        continuation_key=CONTINUATION_KEY,
    ).create()
    return query, snapshot, cases, registry


def _assert_common_response(response, *, query_kind: str):
    validate_financial_domain_query_response(response)
    assert response["schema_version"] == (
        FINANCIAL_DOMAIN_QUERY_SCHEMA_VERSION
    )
    assert response["query_policy_version"] == (
        FINANCIAL_DOMAIN_QUERY_POLICY_VERSION
    )
    assert response["query_kind"] == query_kind
    completeness = response["completeness_status"]
    assert completeness["source_data"] == "complete"
    assert completeness["domain_coverage_status"] == "complete"
    assert completeness["records_returned_this_page"] == len(
        response["results"]
    )
    assert response["result_count"] == len(response["results"])
    assert completeness["matching_records_total"] >= response["result_count"]


def test_domain_catalog_describes_pack_scope_and_capabilities():
    query, snapshot, _, _ = _domain()

    response = query.describe_domain()

    _assert_common_response(response, query_kind="describe_domain")
    assert snapshot.schema_version == FINANCIAL_DOMAIN_SNAPSHOT_SCHEMA_VERSION
    assert response["domain_snapshot"]["domain_snapshot_id"].startswith(
        "findom_"
    )
    assert response["semantic_pack_identity"] == (
        snapshot.semantic_pack_identity()
    )
    assert all(
        callable(getattr(query, capability))
        for capability in (
            "describe_domain",
            "query_typed_records",
            "query_unclassified_records",
            "get_coverage",
            "get_provenance",
        )
    )
    assert response["declared_scope"]["records_total"] == 2
    assert response["declared_scope"]["typed_records_total"] == 1
    assert response["declared_scope"]["unclassified_records_total"] == 1
    assert {
        item["input_type_id"] for item in response["results"]
    } == {
        item["input_type_id"]
        for item in response["declared_scope"]["declared_types"]
    }
    assert response["coverage"]["declared_source_refs_total"] == 4
    assert response["coverage"]["terminal_ownership_complete"] is True
    encoded_snapshot = canonical_json(response["domain_snapshot"])
    assert "user:synthetic" not in encoded_snapshot
    assert "case:synthetic" not in encoded_snapshot
    assert "workspace:synthetic" not in encoded_snapshot
    assert "authority_hmac_sha256" not in encoded_snapshot
    encoded_response = canonical_json(response)
    assert CONTINUATION_KEY.decode("ascii") not in encoded_response
    assert SNAPSHOT_AUTHORITY_KEY.decode("ascii") not in encoded_response


@pytest.mark.parametrize(
    "filters",
    (
        FinancialDomainQueryFilters(
            input_type_id="cash_balance_snapshot_v1"
        ),
        FinancialDomainQueryFilters(
            normalization_run_ref="normalization:synthetic:cash"
        ),
        FinancialDomainQueryFilters(
            document_ref="document:synthetic:cash"
        ),
        FinancialDomainQueryFilters(period="2025-12-31"),
        FinancialDomainQueryFilters(currency="rub"),
        FinancialDomainQueryFilters(classification_status="typed_input"),
    ),
)
def test_typed_query_supports_every_declared_filter(filters):
    query, _, _, _ = _domain()

    response = query.query_typed_records(filters=filters)

    _assert_common_response(response, query_kind="query_typed_records")
    assert (
        response["completeness_status"]["matching_records_total"] == 1
    )
    assert response["results"][0]["record_kind"] == "typed"
    assert response["results"][0]["input_type_id"] == (
        "cash_balance_snapshot_v1"
    )
    assert response["results"][0]["domain_snapshot_id"] == (
        response["domain_snapshot"]["domain_snapshot_id"]
    )
    assert response["results"][0]["semantic_pack_identity"] == (
        response["semantic_pack_identity"]
    )


def test_unclassified_query_preserves_authoritative_literals():
    query, _, _, _ = _domain()

    response = query.query_unclassified_records(
        filters=FinancialDomainQueryFilters(
            classification_status="unclassified_financial_input",
            period="2025 q4",
            currency="RUB",
        )
    )

    _assert_common_response(
        response,
        query_kind="query_unclassified_records",
    )
    assert (
        response["completeness_status"]["matching_records_total"] == 1
    )
    record = response["results"][0]
    assert record["record_kind"] == "unclassified"
    assert {
        item["literal_value"]
        for item in record["source_values"]
    } == {item[2] for item in _DEFINITIONS}


def test_typed_query_can_expand_normative_provenance():
    query, _, _, _ = _domain()

    response = query.query_typed_records(include_provenance=True)

    _assert_common_response(response, query_kind="query_typed_records")
    record = response["results"][0]
    assert response["provenance_included"] is True
    assert record["provenance"]["provenance_ref"] == (
        record["provenance_ref"]
    )
    unsigned = dict(record)
    claimed_hash = unsigned.pop("record_sha256")
    assert claimed_hash == sha256_json(unsigned)


def test_coverage_query_accounts_all_four_terminal_dispositions():
    query, _, _, _ = _domain()

    response = query.get_coverage()

    _assert_common_response(response, query_kind="get_coverage")
    assert (
        response["completeness_status"]["matching_records_total"] == 4
    )
    assert {
        item["classification_status"] for item in response["results"]
    } == {
        "typed_input",
        "unclassified_financial_input",
        "no_financial_input",
        "unsupported",
    }
    assert all(item["scope_accounted"] for item in response["results"])


def test_provenance_query_exposes_refs_without_literal_values():
    query, _, _, _ = _domain()

    response = query.get_provenance()

    _assert_common_response(response, query_kind="get_provenance")
    assert (
        response["completeness_status"]["matching_records_total"] == 4
    )
    encoded = canonical_json(response["results"])
    for _, _, literal, _ in _DEFINITIONS:
        assert literal not in encoded
    assert all(item["provenance_ref"] for item in response["results"])
    assert response["provenance_refs"]


def test_continuation_is_bounded_deterministic_and_scope_bound():
    query, snapshot, _, registry = _domain()
    first = query.get_coverage(limit=1)
    repeated = query.get_coverage(limit=1)

    assert first == repeated
    assert first["result_count"] == 1
    assert (
        first["completeness_status"]["matching_records_total"] == 4
    )
    assert (
        first["completeness_status"]["query_result_complete"] is False
    )
    assert first["continuation"]
    second = query.get_coverage(
        limit=1,
        continuation=first["continuation"],
    )
    assert second["results"] != first["results"]
    assert (
        second["completeness_status"]["records_returned_through_page"]
        == 2
    )

    tampered = first["continuation"][:-1] + (
        "0" if first["continuation"][-1] != "0" else "1"
    )
    with pytest.raises(
        Gate2FinancialDomainError,
        match="financial_domain_query_continuation_invalid",
    ):
        query.get_coverage(limit=1, continuation=tampered)
    with pytest.raises(
        Gate2FinancialDomainError,
        match="financial_domain_query_continuation_invalid",
    ):
        query.get_coverage(
            filters=FinancialDomainQueryFilters(
                classification_status="typed_input"
            ),
            limit=1,
            continuation=first["continuation"],
        )
    other_query, _, _, _ = _domain(prefix="other-")
    with pytest.raises(
        Gate2FinancialDomainError,
        match="financial_domain_query_continuation_invalid",
    ):
        other_query.get_coverage(
            limit=1,
            continuation=first["continuation"],
        )
    wrong_key_query = Gate2FinancialDomainQueryFactory(
        snapshot=snapshot,
        registry=registry,
        access_context=ACCESS_CONTEXT,
        snapshot_authority_key=SNAPSHOT_AUTHORITY_KEY,
        continuation_key=b"different-server-continuation-key-32-bytes",
    ).create()
    with pytest.raises(
        Gate2FinancialDomainError,
        match="financial_domain_query_continuation_invalid",
    ):
        wrong_key_query.get_coverage(
            limit=1,
            continuation=first["continuation"],
        )
    unkeyed_forgery = "findompage_2_" + sha256_json(
        {
            "domain_snapshot_id": snapshot.snapshot_id,
            "query_fingerprint": first["query_fingerprint"],
            "next_record_position": 2,
            "access_scope_fingerprint": (
                snapshot.access_scope_fingerprint()
            ),
            "expires_at": snapshot.expires_at(),
        }
    )[:24]
    with pytest.raises(
        Gate2FinancialDomainError,
        match="financial_domain_query_continuation_invalid",
    ):
        query.get_coverage(limit=1, continuation=unkeyed_forgery)


def test_query_response_integrity_is_fail_closed():
    query, _, _, _ = _domain()
    response = query.query_typed_records()
    response["results"][0]["role_values"][0][
        "literal_value"
    ] = "tampered"

    with pytest.raises(
        Gate2FinancialDomainError,
        match="financial_domain_query_response_integrity_invalid",
    ):
        validate_financial_domain_query_response(response)


def test_catalog_rejects_missing_package_and_rehashed_forgery():
    _, _, cases, registry = _domain()
    factory = Gate2FinancialDomainCatalogFactory(
        registry=registry,
        snapshot_authority_key=SNAPSHOT_AUTHORITY_KEY,
    )
    with pytest.raises(
        Gate2FinancialDomainError,
        match="financial_domain_source_package_set_mismatch",
    ):
        factory.create(
            materialized_artifacts=tuple(item[0] for item in cases),
            source_packages=tuple(item[1] for item in cases[:-1]),
            access_context=ACCESS_CONTEXT,
            created_at=CREATED_AT,
            expires_at=None,
        )

    forged = copy.deepcopy(cases[0][0])
    terminal = forged["typed_inputs"][0]
    terminal["source_values"][0]["source_ref"] = "source:cell:forged"
    unsigned_terminal = dict(terminal)
    unsigned_terminal.pop("integrity_hash")
    terminal["integrity_hash"] = sha256_json(unsigned_terminal)
    unsigned_artifact = dict(forged)
    unsigned_artifact.pop("integrity_hash")
    forged["integrity_hash"] = sha256_json(unsigned_artifact)
    with pytest.raises(Exception) as exc_info:
        factory.create(
            materialized_artifacts=(
                forged,
                *(item[0] for item in cases[1:]),
            ),
            source_packages=tuple(item[1] for item in cases),
            access_context=ACCESS_CONTEXT,
            created_at=CREATED_AT,
            expires_at=None,
        )
    assert str(exc_info.value) == "financial_evidence_package_binding_invalid"


def test_query_factory_rejects_self_consistent_forged_authority():
    _, snapshot, _, registry = _domain()
    forged_registry_hash = "0" * 64
    material = _snapshot_integrity_material(
        snapshot=snapshot.identity_payload(),
        catalog=snapshot.declared_scope(),
        coverage=snapshot.coverage_summary(),
        typed_records=snapshot.typed_records(),
        unclassified_records=snapshot.unclassified_records(),
        record_index_values=snapshot.record_index(),
        coverage_records=snapshot.coverage_records(),
        provenance_records=snapshot.provenance_records(),
        registry_version=snapshot.registry_version,
        registry_hash=forged_registry_hash,
        completeness_status=snapshot.completeness_status,
        snapshot_seed_sha256=snapshot.snapshot_seed_sha256,
    )
    integrity = sha256_json(material)
    forged = replace(
        snapshot,
        registry_hash=forged_registry_hash,
        integrity_sha256=integrity,
    )
    forged.validate()

    with pytest.raises(
        Gate2FinancialDomainError,
        match="financial_domain_snapshot_authority_mismatch",
    ):
        Gate2FinancialDomainQueryFactory(
            snapshot=forged,
            registry=registry,
            access_context=ACCESS_CONTEXT,
            snapshot_authority_key=SNAPSHOT_AUTHORITY_KEY,
            continuation_key=CONTINUATION_KEY,
        ).create()


def test_query_factory_rejects_current_authority_record_forgery():
    _, snapshot, _, registry = _domain()
    typed_records = snapshot.typed_records()
    typed_records[0]["role_values"][0][
        "literal_value"
    ] = "synthetic forged value"
    unsigned_record = dict(typed_records[0])
    unsigned_record.pop("record_sha256")
    typed_records[0]["record_sha256"] = sha256_json(unsigned_record)
    snapshot_payload = snapshot.identity_payload()
    all_records = sorted(
        [*typed_records, *snapshot.unclassified_records()],
        key=lambda item: item["record_id"],
    )
    snapshot_payload["record_set_sha256"] = sha256_json(
        [
            {
                "record_id": item["record_id"],
                "record_sha256": item["record_sha256"],
            }
            for item in all_records
        ]
    )
    material = _snapshot_integrity_material(
        snapshot=snapshot_payload,
        catalog=snapshot.declared_scope(),
        coverage=snapshot.coverage_summary(),
        typed_records=typed_records,
        unclassified_records=snapshot.unclassified_records(),
        record_index_values=snapshot.record_index(),
        coverage_records=snapshot.coverage_records(),
        provenance_records=snapshot.provenance_records(),
        registry_version=snapshot.registry_version,
        registry_hash=snapshot.registry_hash,
        completeness_status=snapshot.completeness_status,
        snapshot_seed_sha256=snapshot.snapshot_seed_sha256,
    )
    forged = replace(
        snapshot,
        snapshot_json=canonical_json(snapshot_payload),
        typed_records_json=tuple(
            canonical_json(item) for item in typed_records
        ),
        integrity_sha256=sha256_json(material),
    )
    forged.validate()

    with pytest.raises(
        Gate2FinancialDomainError,
        match="financial_domain_snapshot_authority_attestation_invalid",
    ):
        Gate2FinancialDomainQueryFactory(
            snapshot=forged,
            registry=registry,
            access_context=ACCESS_CONTEXT,
            snapshot_authority_key=SNAPSHOT_AUTHORITY_KEY,
            continuation_key=CONTINUATION_KEY,
        ).create()


def test_snapshot_authority_keys_fail_closed():
    _, snapshot, _, registry = _domain()

    with pytest.raises(
        Gate2FinancialDomainError,
        match="financial_domain_snapshot_authority_attestation_invalid",
    ):
        Gate2FinancialDomainQueryFactory(
            snapshot=snapshot,
            registry=registry,
            access_context=ACCESS_CONTEXT,
            snapshot_authority_key=(
                b"different-server-snapshot-authority-key-32-bytes"
            ),
            continuation_key=CONTINUATION_KEY,
        ).create()
    with pytest.raises(
        Gate2FinancialDomainError,
        match="financial_domain_snapshot_authority_key_invalid",
    ):
        Gate2FinancialDomainQueryFactory(
            snapshot=snapshot,
            registry=registry,
            access_context=ACCESS_CONTEXT,
            snapshot_authority_key=b"short",
            continuation_key=CONTINUATION_KEY,
        ).create()
    with pytest.raises(
        Gate2FinancialDomainError,
        match="financial_domain_snapshot_authority_key_invalid",
    ):
        Gate2FinancialDomainCatalogFactory(
            registry=registry,
            snapshot_authority_key=b"short",
        )


def test_snapshot_rejects_rehashed_cross_entity_count_drift():
    _, snapshot, _, _ = _domain()
    catalog = snapshot.declared_scope()
    catalog["records_total"] += 1
    unsigned_catalog = dict(catalog)
    unsigned_catalog.pop("catalog_sha256")
    catalog["catalog_sha256"] = sha256_json(unsigned_catalog)
    material = _snapshot_integrity_material(
        snapshot=snapshot.identity_payload(),
        catalog=catalog,
        coverage=snapshot.coverage_summary(),
        typed_records=snapshot.typed_records(),
        unclassified_records=snapshot.unclassified_records(),
        record_index_values=snapshot.record_index(),
        coverage_records=snapshot.coverage_records(),
        provenance_records=snapshot.provenance_records(),
        registry_version=snapshot.registry_version,
        registry_hash=snapshot.registry_hash,
        completeness_status=snapshot.completeness_status,
        snapshot_seed_sha256=snapshot.snapshot_seed_sha256,
    )
    forged = replace(
        snapshot,
        catalog_json=canonical_json(catalog),
        integrity_sha256=sha256_json(material),
    )

    with pytest.raises(
        Gate2FinancialDomainError,
        match="financial_domain_catalog_count_invalid",
    ):
        forged.validate()


def test_snapshot_entities_validate_against_normative_goal1_schema():
    _, snapshot, _, _ = _domain()
    schema = json.loads(MANAGED_DOMAIN_SCHEMA.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    entities = [
        snapshot.identity_payload(),
        snapshot.declared_scope(),
        snapshot.coverage_summary(),
        *snapshot.typed_records(),
        *snapshot.unclassified_records(),
        *snapshot.provenance_records(),
    ]

    for entity in entities:
        validator.validate(entity)


def test_access_scope_and_factory_bypass_fail_closed():
    _, snapshot, _, registry = _domain()

    with pytest.raises(
        Gate2FinancialDomainError,
        match="financial_domain_access_scope_mismatch",
    ):
        Gate2FinancialDomainQueryFactory(
            snapshot=snapshot,
            registry=registry,
            access_context=FinancialDomainAccessContext(
                user_ref="user:foreign",
                case_ref="case:synthetic",
                workspace_ref="workspace:synthetic",
            ),
            snapshot_authority_key=SNAPSHOT_AUTHORITY_KEY,
            continuation_key=CONTINUATION_KEY,
        ).create()
    with pytest.raises(
        Gate2FinancialDomainError,
        match="financial_domain_query_factory_required",
    ):
        Gate2FinancialDomainQuery(
            snapshot=snapshot,
            access_scope_fingerprint=ACCESS_SCOPE_FINGERPRINT,
            continuation_key=CONTINUATION_KEY,
        )
    with pytest.raises(
        Gate2FinancialDomainError,
        match="financial_domain_source_unavailable",
    ):
        Gate2FinancialDomainQueryFactory(
            snapshot=snapshot,
            registry=registry,
            access_context=FinancialDomainAccessContext(
                user_ref="user:synthetic",
                case_ref="case:synthetic",
                workspace_ref="workspace:synthetic",
                source_available=False,
            ),
            snapshot_authority_key=SNAPSHOT_AUTHORITY_KEY,
            continuation_key=CONTINUATION_KEY,
        ).create()
    with pytest.raises(
        Gate2FinancialDomainError,
        match="financial_domain_continuation_key_invalid",
    ):
        Gate2FinancialDomainQueryFactory(
            snapshot=snapshot,
            registry=registry,
            access_context=ACCESS_CONTEXT,
            snapshot_authority_key=SNAPSHOT_AUTHORITY_KEY,
            continuation_key=b"short",
        ).create()


def test_expired_snapshot_is_not_queryable():
    _, _, cases, registry = _domain()
    snapshot = Gate2FinancialDomainCatalogFactory(
        registry=registry,
        snapshot_authority_key=SNAPSHOT_AUTHORITY_KEY,
    ).create(
        materialized_artifacts=tuple(item[0] for item in cases),
        source_packages=tuple(item[1] for item in cases),
        access_context=ACCESS_CONTEXT,
        created_at="2020-01-01T00:00:00+00:00",
        expires_at="2021-01-01T00:00:00+00:00",
    )

    with pytest.raises(
        Gate2FinancialDomainError,
        match="financial_domain_snapshot_expired",
    ):
        Gate2FinancialDomainQueryFactory(
            snapshot=snapshot,
            registry=registry,
            access_context=ACCESS_CONTEXT,
            snapshot_authority_key=SNAPSHOT_AUTHORITY_KEY,
            continuation_key=CONTINUATION_KEY,
        ).create()


def test_domain_query_boundary_has_zero_artifact_store_access():
    forbidden_modules = {
        "artifact_store",
        "artifact_resolver",
        "gate2_artifact_store",
        "gate2_artifact_resolver",
    }
    for path in BOUNDARY_MODULE_PATHS:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        }
        imported.update(
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        )
        assert not any(
            module.rsplit(".", 1)[-1] in forbidden_modules
            for module in imported
        )
    assert not hasattr(Gate2FinancialDomainQuery, "artifact_store")
    assert not hasattr(Gate2FinancialDomainQuery, "artifact_resolver")


def test_gate3_consumer_uses_domain_api_with_exact_query_parity():
    query, snapshot, _, _ = _domain()

    context = (
        Gate3FinancialDomainContextFactory(
            query=query,
            page_limit=1,
        )
        .create()
        .build_context()
    )

    assert context["domain_snapshot"] == snapshot.identity_payload()
    assert context["declared_scope"] == snapshot.declared_scope()
    assert context["typed_records"]
    assert context["unclassified_records"]
    assert len(context["coverage_records"]) == 4
    assert len(context["provenance_records"]) == 4
    assert context["proof"] == {
        "gate3_domain_only": "passed",
        "catalog_exact": True,
        "query_parity": "exact",
        "provenance_complete": True,
        "source_llm_calls_total": 0,
        "domain_llm_calls_total": 0,
    }
    unsigned = dict(context)
    claimed_hash = unsigned.pop("integrity_sha256")
    assert claimed_hash == sha256_json(unsigned)
    assert all(
        len(receipt["page_integrity_sha256"]) > 1
        for receipt in context["query_receipts"].values()
        if receipt["matching_records_total"] > 1
    )


def test_gate3_consumer_is_factory_only_and_domain_api_only():
    query, _, _, _ = _domain()

    with pytest.raises(
        Gate3FinancialDomainContextError,
        match="gate3_financial_domain_consumer_factory_required",
    ):
        Gate3FinancialDomainContextConsumer(
            query=query,
            page_limit=1,
        )

    path = ROOT / "broker_reports_gate1" / "gate3_financial_domain_context.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    imported.update(
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    )
    assert not any(
        module.rsplit(".", 1)[-1]
        in {
            "artifact_models",
            "artifact_resolver",
            "artifact_store",
            "gate1_public_contracts",
            "gate2_domain_runtime",
        }
        for module in imported
    )
    assert not hasattr(
        Gate3FinancialDomainContextConsumer,
        "artifact_store",
    )
    assert not hasattr(
        Gate3FinancialDomainContextConsumer,
        "artifact_resolver",
    )
