from __future__ import annotations

import copy
import hashlib
import inspect
import json
from pathlib import Path

import pytest

from broker_reports_gate1.artifact_lifecycle import lifecycle_for_visibility
from broker_reports_gate1.artifact_models import ArtifactRecord
from broker_reports_gate1.artifact_retention import build_retention_policy
from broker_reports_gate1.canonical_artifact import (
    CanonicalNormalizerConfig,
    CanonicalNormalizerFactory,
)
from broker_reports_gate1.canonical_store import (
    CanonicalArtifactStoreFactory,
    CanonicalReaderFactory,
    CanonicalStorageConfig,
)
from broker_reports_gate1.ordinary_trade_production_runtime import (
    FORBIDDEN,
    ORDINARY_TRADE_PRODUCTION_ROUTE_ID,
    OrdinaryTradeProductionRuntimeFactory,
)
from broker_reports_gate1.ordinary_trade_projection import (
    OrdinaryTradeProjectionFactory,
)
from broker_reports_gate1.ordinary_trade_qualified_mappings import (
    QUALIFICATION_SCHEMA_VERSION,
    OrdinaryTradeQualifiedMappingAuthorityFactory,
    validate_qualified_mapping,
)
from broker_reports_gate1.ordinary_trade_semantic_compiler import (
    OrdinaryTradeSemanticCompilerFactory,
    compile_schema_mapping,
)

import test_broker_reports_gate4_sql_materialization as gate4_fixtures


_REPO_ROOT = Path(__file__).resolve().parents[3]
_PIPE_SOURCE = (
    _REPO_ROOT
    / "services"
    / "broker-reports-gate1-proof"
    / "openwebui_actions"
    / "broker_reports_gate1_pipe.py"
)


def test_release_route_uses_packaged_exact_mapping_and_reaches_gate5(
    tmp_path: Path,
) -> None:
    store, context = gate4_fixtures._store_context(tmp_path)
    mapping = OrdinaryTradeQualifiedMappingAuthorityFactory.create().list_mappings()[0]
    rows = (
        tuple(item["header_literal"] for item in mapping["columns"]),
        tuple(_literal_for_role(item["semantic_role"]) for item in mapping["columns"]),
    )
    document_id = "qualified-ordinary-trade"
    gate4_fixtures._activate_canonical(
        store=store,
        context=context,
        document_id=document_id,
        artifact_version=1,
        expected_previous_version_id=None,
        table_rows=rows,
    )
    version = next(
        item
        for item in store.list_canonical_versions(
            context=context,
            document_id=document_id,
        )
        if item.status == "ACTIVE"
    )
    assert version.manifest_ref
    runtime = OrdinaryTradeProductionRuntimeFactory(
        store=store,
        read_enabled=True,
    ).create()

    first = runtime.run(
        canonical_artifact_refs=[version.manifest_ref],
        context=context,
    )
    second = runtime.run(canonical_artifact_refs=[], context=context)

    assert first["route_owner"] == ORDINARY_TRADE_PRODUCTION_ROUTE_ID
    assert first["provider_calls_total"] == 0
    assert first["semantic_fallback_used"] is False
    assert first["legacy_fallback_used"] is False
    assert first["documents"][0]["matched_qualified_tables"] == 1
    assert first["product"]["gate4"] == {
        "status": "candidate_projection_facts",
        "facts_total": 3,
        "security_facts_total": 1,
        "transaction_charge_facts_total": 2,
    }
    assert first["system_identity"] == second["system_identity"]


def test_unknown_schema_is_preserved_unmapped_without_semantic_fallback(
    tmp_path: Path,
) -> None:
    store, context = gate4_fixtures._store_context(tmp_path)
    document_id = "unknown-ordinary-trade-shape"
    gate4_fixtures._activate_canonical(
        store=store,
        context=context,
        document_id=document_id,
        artifact_version=1,
        expected_previous_version_id=None,
        table_rows=(("Unknown", "Shape"), ("value", "1")),
    )
    version = next(
        item
        for item in store.list_canonical_versions(
            context=context,
            document_id=document_id,
        )
        if item.status == "ACTIVE"
    )
    result = (
        OrdinaryTradeProductionRuntimeFactory(
            store=store,
            read_enabled=True,
        )
        .create()
        .run(
            canonical_artifact_refs=[str(version.manifest_ref)],
            context=context,
        )
    )
    projection = (
        OrdinaryTradeProjectionFactory(
            store=store,
            read_enabled=True,
        )
        .create()
        .current_case(context=context)[0][1]
    )

    assert result["product"]["gate4"]["facts_total"] == 0
    assert result["provider_calls_total"] == 0
    assert result["semantic_fallback_used"] is False
    assert projection["runtime_records"] == []
    assert {item["disposition"] for item in projection["source_observations"]} == {
        "RELEVANT_UNMAPPED"
    }
    note = result["product"]["preparation"]["final_note"]
    assert note["source_completeness_status"] == "RELEVANT_UNMAPPED"
    assert note["position_evaluation_status"] == (
        "NOT_EVALUATED_SOURCE_FACTS_UNAVAILABLE"
    )
    assert note["profile"]["support"] == (
        "NOT_EVALUATED_SOURCE_COVERAGE_INCOMPLETE"
    )
    assert note["filing_eligible"] is False


def test_missing_canonical_stops_without_old_semantic_fallback(tmp_path: Path) -> None:
    store, context = gate4_fixtures._store_context(tmp_path)
    result = (
        OrdinaryTradeProductionRuntimeFactory(
            store=store,
            read_enabled=True,
        )
        .create()
        .run(canonical_artifact_refs=[], context=context)
    )

    assert result["status"] == "blocked"
    assert result["provider_calls_total"] == 0
    assert result["semantic_fallback_used"] is False
    assert result["product"]["terminal"] == (
        "ordinary_trade_canonical_evidence_missing"
    )
    assert result["product"]["gate4"]["facts_total"] == 0
    note = result["product"]["preparation"]["final_note"]
    assert note["source_completeness_status"] == "CANONICAL_EVIDENCE_MISSING"
    assert note["position_evaluation_status"] == (
        "NOT_EVALUATED_SOURCE_FACTS_UNAVAILABLE"
    )
    assert note["selected_tax_period"] is None
    assert note["detected_operation_years"] == []
    assert note["profile"]["support"] == (
        "NOT_EVALUATED_SOURCE_COVERAGE_INCOMPLETE"
    )
    assert note["positions"] == []
    assert note["calculated_disposal_fact_ids"] == []
    assert note["filing_eligible"] is False


def test_zero_observation_document_cannot_complete_case_coverage(
    tmp_path: Path,
) -> None:
    store, context = gate4_fixtures._store_context(tmp_path)
    document_id = "paragraph-only-broker-document"
    canonical = _activate_pdf_text_canonical(
        store=store,
        context=context,
        document_id=document_id,
        text="Readable document text without a recovered table.",
    )
    assert canonical.artifact_ref
    runtime = OrdinaryTradeProductionRuntimeFactory(
        store=store,
        read_enabled=True,
    ).create()

    first = runtime.run(
        canonical_artifact_refs=[canonical.artifact_ref],
        context=context,
    )
    second = runtime.run(canonical_artifact_refs=[], context=context)
    projection_runtime = OrdinaryTradeProjectionFactory(
        store=store,
        read_enabled=True,
    ).create()
    current = projection_runtime.current_case(context=context)
    coverage = projection_runtime.current_case_coverage(context=context)

    assert len(current) == 1
    assert current[0][1]["source_observations"] == []
    assert current[0][1]["runtime_records"] == []
    assert coverage["status"] == "relevant_unmapped"
    assert coverage["runtime_ready_observations"] == 0
    assert coverage["relevant_unmapped_observations"] == 0
    assert first["product"]["status"] == "PREPARATION_INCOMPLETE"
    assert first["product"]["terminal"] == (
        "ordinary_trade_declaration_canonical_relevant_unmapped"
    )
    assert first["product"]["declaration_ready"] is False
    assert first["product"]["xml_created"] is False
    assert first["product"]["gate4"]["facts_total"] == 0
    assert first["provider_calls_total"] == 0
    assert first["semantic_fallback_used"] is False
    assert first["legacy_fallback_used"] is False
    assert first["system_identity"] == second["system_identity"]
    assert first["product"]["terminal"] == second["product"]["terminal"]


def test_zero_observation_document_blocks_mixed_case_declaration(
    tmp_path: Path,
) -> None:
    store, context = gate4_fixtures._store_context(tmp_path)
    mapping = OrdinaryTradeQualifiedMappingAuthorityFactory.create().list_mappings()[0]
    trade = gate4_fixtures._activate_canonical(
        store=store,
        context=context,
        document_id="mixed-case-qualified-trade",
        artifact_version=1,
        expected_previous_version_id=None,
        table_rows=(
            tuple(item["header_literal"] for item in mapping["columns"]),
            tuple(
                _literal_for_role(item["semantic_role"])
                for item in mapping["columns"]
            ),
        ),
    )
    paragraph = _activate_pdf_text_canonical(
        store=store,
        context=context,
        document_id="mixed-case-paragraph-only",
        text="Additional readable content without a recovered table.",
    )
    assert trade.artifact_ref
    assert paragraph.artifact_ref

    result = OrdinaryTradeProductionRuntimeFactory(
        store=store,
        read_enabled=True,
    ).create().run(
        canonical_artifact_refs=[trade.artifact_ref, paragraph.artifact_ref],
        context=context,
    )
    coverage = OrdinaryTradeProjectionFactory(
        store=store,
        read_enabled=True,
    ).create().current_case_coverage(context=context)

    assert coverage["status"] == "relevant_unmapped"
    assert len(coverage["document_scope"]) == 2
    assert len(coverage["projections"]) == 2
    assert result["product"]["status"] == "PREPARATION_INCOMPLETE"
    assert result["product"]["terminal"] == (
        "ordinary_trade_declaration_canonical_relevant_unmapped"
    )
    assert result["product"]["declaration_ready"] is False
    assert result["product"]["xml_created"] is False
    assert result["provider_calls_total"] == 0
    # The guard blocks declaration publication. Existing Gate 4 persistence is
    # intentionally unchanged and remains a separate atomicity task.
    assert result["product"]["gate4"]["facts_total"] == 3


def test_supported_table_survives_unknown_table_in_same_canonical(tmp_path: Path) -> None:
    store, context = gate4_fixtures._store_context(tmp_path)
    mapping = OrdinaryTradeQualifiedMappingAuthorityFactory.create().list_mappings()[0]
    rows = (
        tuple(item["header_literal"] for item in mapping["columns"]),
        tuple(_literal_for_role(item["semantic_role"]) for item in mapping["columns"]),
    )
    document_id = "supported-with-unknown"
    gate4_fixtures._activate_canonical(
        store=store,
        context=context,
        document_id=document_id,
        artifact_version=1,
        expected_previous_version_id=None,
        table_rows=rows,
    )
    envelope = (
        CanonicalReaderFactory(store=store, read_enabled=True)
        .create()
        .read_active_envelope(document_id, context)
    )
    canonical = copy.deepcopy(envelope.artifact)
    known = next(item for item in canonical["nodes"] if item["node_type"] == "TABLE")
    unknown = copy.deepcopy(known)
    unknown["node_id"] = "node_unknown_operation_table"
    unknown["content"]["cells"][0]["displayed_value"] = "Unknown operation"
    canonical["nodes"].append(unknown)
    projection = OrdinaryTradeSemanticCompilerFactory.create().compile(
        canonical=canonical,
        canonical_binding={
            "document_id": document_id,
            "canonical_version_id": envelope.canonical_version_id,
            "canonical_root_sha256": envelope.canonical_root_sha256,
            "source_artifact_ref": canonical["source"]["source_artifact_ref"],
            "source_sha256": canonical["source"]["source_sha256"],
        },
        mappings=[mapping],
    )

    assert sum(
        item["disposition"] == "RUNTIME_READY"
        for item in projection["source_observations"]
    ) == 1
    assert sum(
        item["disposition"] == "RELEVANT_UNMAPPED"
        for item in projection["source_observations"]
    ) == 2
    assert len(projection["runtime_records"]) == 3


def test_production_purchase_only_is_open_long_not_missing_disposal(
    tmp_path: Path,
) -> None:
    store, context = gate4_fixtures._store_context(tmp_path)
    mapping = OrdinaryTradeQualifiedMappingAuthorityFactory.create().list_mappings()[0]
    document_id = "purchase-only-open-long"
    gate4_fixtures._activate_canonical(
        store=store,
        context=context,
        document_id=document_id,
        artifact_version=1,
        expected_previous_version_id=None,
        table_rows=(
            tuple(item["header_literal"] for item in mapping["columns"]),
            _row_for_mapping(
                mapping,
                side="PURCHASE",
                trade_date="01.12.2022",
                asset="ACME",
                quantity="10",
                gross_amount="100.00",
            ),
        ),
    )
    version = next(
        item
        for item in store.list_canonical_versions(context=context, document_id=document_id)
        if item.status == "ACTIVE"
    )

    result = OrdinaryTradeProductionRuntimeFactory(
        store=store, read_enabled=True
    ).create().run(
        canonical_artifact_refs=[str(version.manifest_ref)], context=context
    )
    group = result["product"]["gate5"]["security_groups"][0]

    assert result["product"]["status"] == "OPEN_POSITION_RETAINED"
    assert result["product"]["terminal"] == "ordinary_trade_closed_disposal_absent"
    assert result["product"]["gate5"]["execution_status"] == (
        "open_position_not_tax_activated"
    )
    assert result["product"]["gate5"]["blocker_reason_codes"] == []
    assert group["position_scope"]["state"] == "OPEN_LONG_PROVEN"
    assert group["blocker"] is None
    assert result["product"]["xml_created"] is False


def test_production_sale_only_reports_horizon_gap_without_short_inference(
    tmp_path: Path,
) -> None:
    store, context = gate4_fixtures._store_context(tmp_path)
    mapping = OrdinaryTradeQualifiedMappingAuthorityFactory.create().list_mappings()[0]
    document_id = "sale-only-horizon-gap"
    gate4_fixtures._activate_canonical(
        store=store,
        context=context,
        document_id=document_id,
        artifact_version=1,
        expected_previous_version_id=None,
        table_rows=(
            tuple(item["header_literal"] for item in mapping["columns"]),
            _row_for_mapping(
                mapping,
                side="DISPOSAL",
                trade_date="01.03.2025",
                asset="ACME",
                quantity="7",
                gross_amount="210.00",
            ),
        ),
    )
    version = next(
        item
        for item in store.list_canonical_versions(context=context, document_id=document_id)
        if item.status == "ACTIVE"
    )

    result = OrdinaryTradeProductionRuntimeFactory(
        store=store, read_enabled=True
    ).create().run(
        canonical_artifact_refs=[str(version.manifest_ref)], context=context
    )
    group = result["product"]["gate5"]["security_groups"][0]

    assert result["product"]["terminal"] == (
        "gate5_source_fact_acquisition_evidence_horizon_unproven"
    )
    assert result["product"]["gate5"]["blocker_reason_codes"] == [
        "gate5_source_fact_acquisition_evidence_horizon_unproven"
    ]
    assert result["product"]["gate5"]["security_tax_input_status"] == (
        "SOURCE_EVIDENCE_INSUFFICIENT"
    )
    assert group["position_scope"]["state"] == (
        "UNRESOLVED_DISPOSAL_EVIDENCE_HORIZON"
    )
    assert group["position_scope"]["short_inference_performed"] is False


def test_cross_year_acquisition_closes_selected_year_disposal_and_open_group_survives(
    tmp_path: Path,
) -> None:
    store, context = gate4_fixtures._store_context(tmp_path)
    mapping = OrdinaryTradeQualifiedMappingAuthorityFactory.create().list_mappings()[0]
    document_id = "cross-year-mixed-positions"
    gate4_fixtures._activate_canonical(
        store=store,
        context=context,
        document_id=document_id,
        artifact_version=1,
        expected_previous_version_id=None,
        table_rows=(
            tuple(item["header_literal"] for item in mapping["columns"]),
            _row_for_mapping(
                mapping,
                side="PURCHASE",
                trade_date="01.12.2024",
                asset="ACME",
                quantity="10",
                gross_amount="100.00",
            ),
            _row_for_mapping(
                mapping,
                side="DISPOSAL",
                trade_date="01.03.2025",
                asset="ACME",
                quantity="6",
                gross_amount="90.00",
            ),
            _row_for_mapping(
                mapping,
                side="PURCHASE",
                trade_date="02.03.2025",
                asset="BETA",
                quantity="3",
                gross_amount="30.00",
            ),
        ),
    )
    version = next(
        item
        for item in store.list_canonical_versions(context=context, document_id=document_id)
        if item.status == "ACTIVE"
    )

    result = OrdinaryTradeProductionRuntimeFactory(
        store=store, read_enabled=True
    ).create().run(
        canonical_artifact_refs=[str(version.manifest_ref)], context=context
    )
    gate5 = result["product"]["gate5"]
    groups = {item["asset"]: item for item in gate5["security_groups"]}

    assert gate5["operation_period_observation"]["observed_operation_years"] == [
        "2024",
        "2025",
    ]
    assert len(gate5["fifo_calculations"]) == 1
    assert groups["ACME"]["position_scope"]["resolved_disposal_quantity"] == "6"
    assert groups["ACME"]["position_scope"]["open_long_quantity"] == "4"
    assert groups["BETA"]["position_scope"]["state"] == "OPEN_LONG_PROVEN"
    assert gate5["blocker_reason_codes"] == []


def test_charge_identity_is_bound_to_exact_commission_cell_and_trade_row(
    tmp_path: Path,
) -> None:
    store, context = gate4_fixtures._store_context(tmp_path)
    mapping = OrdinaryTradeQualifiedMappingAuthorityFactory.create().list_mappings()[0]
    rows = (
        tuple(item["header_literal"] for item in mapping["columns"]),
        tuple(_literal_for_role(item["semantic_role"]) for item in mapping["columns"]),
    )
    document_id = "charge-binding"
    gate4_fixtures._activate_canonical(
        store=store,
        context=context,
        document_id=document_id,
        artifact_version=1,
        expected_previous_version_id=None,
        table_rows=rows,
    )
    version = next(
        item
        for item in store.list_canonical_versions(
            context=context,
            document_id=document_id,
        )
        if item.status == "ACTIVE"
    )
    OrdinaryTradeProductionRuntimeFactory(
        store=store,
        read_enabled=True,
    ).create().run(
        canonical_artifact_refs=[str(version.manifest_ref)],
        context=context,
    )
    projection = (
        OrdinaryTradeProjectionFactory(
            store=store,
            read_enabled=True,
        )
        .create()
        .current_case(context=context)[0][1]
    )
    observation = projection["source_observations"][0]
    records = projection["runtime_records"]
    trade = next(
        item for item in records if item["record_type"].startswith("SECURITY_")
    )
    charges = [item for item in records if item["record_type"] == "TRANSACTION_CHARGE"]

    assert len(charges) == 2
    assert len({item["claim_refs"][0] for item in charges}) == 2
    for charge in charges:
        amount = next(item for item in charge["roles"] if item["role"] == "amount")
        source_ref = amount["source_binding"]["source_ref"]
        source_field = next(
            item for item in observation["fields"] if item["source_ref"] == source_ref
        )
        assert charge["claim_refs"] == [source_ref]
        assert amount["source_binding"]["source_literal"] == source_field["literal"]
        assert (
            amount["source_binding"]["canonical_cell"] == source_field["canonical_cell"]
        )
        assert charge["source_observation_id"] == trade["source_observation_id"]
        assert charge["annotation_target"] == trade["annotation_target"]


def test_qualification_reference_is_part_of_mapping_identity() -> None:
    mapping = OrdinaryTradeQualifiedMappingAuthorityFactory.create().list_mappings()[0]
    kwargs = {
        "title_literal": mapping["title_literal"],
        "headers": [
            {"column": item["column"], "literal": item["header_literal"]}
            for item in mapping["columns"]
        ],
        "model_columns": [
            {"column": item["column"], "semantic_role": item["semantic_role"]}
            for item in mapping["columns"]
        ],
        "amount_currency_bindings": mapping["amount_currency_bindings"],
        "side_values": mapping["side_values"],
        "qualification_ref": mapping["qualification_ref"],
    }
    rebuilt = compile_schema_mapping(**kwargs)
    assert rebuilt == mapping
    changed_ref = copy.deepcopy(kwargs)
    changed_ref["qualification_ref"]["receipt_sha256"] = "0" * 64
    assert compile_schema_mapping(**changed_ref)["mapping_id"] != mapping["mapping_id"]


def test_production_factory_is_the_only_candidate_route_and_has_no_old_owner() -> None:
    source = inspect.getsource(OrdinaryTradeProductionRuntimeFactory)
    pipe = _PIPE_SOURCE.read_text(encoding="utf-8")
    assert "Gate3" not in source
    assert "FinancialAnnotationsV2" not in source
    assert "Gate4FinancialCaseRuntimeFactory" not in source
    assert "semantic fallback" in FORBIDDEN
    assert pipe.index("if candidate_enabled:") < pipe.index(
        "Gate2StructuredModelClientFactory("
    )


def test_qualified_mapping_authority_is_immutable_and_has_no_profile_keys() -> None:
    authority = OrdinaryTradeQualifiedMappingAuthorityFactory.create()
    first = authority.list_mappings()
    second = authority.list_mappings()
    first[0]["columns"][0]["header_literal"] = "mutated"
    assert second == authority.list_mappings()
    assert all(
        not {"broker", "broker_id", "year", "filename", "profile"} & set(item)
        for item in second
    )


def test_changed_relation_is_rejected_without_matching_qualification() -> None:
    authority = OrdinaryTradeQualifiedMappingAuthorityFactory.create()
    mapping = authority.list_mappings()[1]
    receipt = authority.list_qualification_receipts()[1]
    changed = compile_schema_mapping(
        title_literal=mapping["title_literal"],
        headers=[
            {"column": item["column"], "literal": item["header_literal"]}
            for item in mapping["columns"]
        ],
        model_columns=[
            {"column": item["column"], "semantic_role": item["semantic_role"]}
            for item in mapping["columns"]
        ],
        amount_currency_bindings=[
            {"amount_column": 8, "currency_column": 5},
            {"amount_column": 10, "currency_column": 7},
            {"amount_column": 11, "currency_column": 7},
        ],
        side_values=mapping["side_values"],
        qualification_ref=mapping["qualification_ref"],
    )

    with pytest.raises(RuntimeError) as rejected:
        validate_qualified_mapping(mapping=changed, receipt=receipt)

    assert rejected.value.args == (
        "ordinary_trade_mapping_qualification_scope_invalid",
    )


def test_receipts_cover_only_named_consumer_relations_and_are_immutable() -> None:
    authority = OrdinaryTradeQualifiedMappingAuthorityFactory.create()
    first = authority.list_qualification_receipts()
    second = authority.list_qualification_receipts()
    first[0]["relation_claims"][0]["currency_column"] = 999

    assert second == authority.list_qualification_receipts()
    assert all(
        claim["consumer_contract"] == "Gate4FinancialCaseFactV2.amount_currency"
        for receipt in second
        for claim in receipt["relation_claims"]
    )
    assert all(
        "unit_price" not in claim
        for receipt in second
        for claim in receipt["relation_claims"]
    )


def test_reviewed_relations_expose_question_rationale_and_limits() -> None:
    receipts = (
        OrdinaryTradeQualifiedMappingAuthorityFactory.create()
        .list_qualification_receipts()
    )
    claims = [claim for receipt in receipts for claim in receipt["relation_claims"]]
    reviewed = [
        claim
        for claim in claims
        if claim["evidence_basis"] == "REVIEWED_SCHEMA_SCOPE"
    ]
    explicit = [
        claim
        for claim in claims
        if claim["evidence_basis"] == "EXPLICIT_DENOMINATION_HEADER"
    ]

    assert {receipt["schema_version"] for receipt in receipts} == {
        QUALIFICATION_SCHEMA_VERSION
    }
    assert QUALIFICATION_SCHEMA_VERSION == (
        "broker_reports_ordinary_trade_mapping_qualification_v2"
    )
    assert len(reviewed) == 5
    assert len(explicit) == 1
    assert all("review_record" not in claim for claim in explicit)
    assert all(
        receipt["supporting_decision_scope"] == ["columns", "side_values"]
        for receipt in receipts
    )
    assert len(
        {claim["review_record"]["review_id"] for claim in reviewed}
    ) == len(reviewed)
    for claim in reviewed:
        review = claim["review_record"]
        assert review["reviewed_evidence"] == (
            "EXACT_TITLE_AND_COMPLETE_ORDERED_HEADER_SET"
        )
        assert review["decision"] == (
            "ADMITTED_AS_REVIEWED_SCHEMA_INTERPRETATION"
        )
        assert review["question"].strip()
        assert review["rationale"].strip()
        assert review["excluded_bases"] == [
            "COLUMN_PROXIMITY",
            "ROW_VALUE_EQUALITY",
            "CROSS_TABLE_RECONCILIATION",
            "DOWNSTREAM_RESULT",
            "BROKER_OR_FILENAME_IDENTITY",
        ]


def test_historical_scope_marker_cannot_be_resealed_as_authority() -> None:
    authority = OrdinaryTradeQualifiedMappingAuthorityFactory.create()
    mapping = authority.list_mappings()[0]
    receipt = authority.list_qualification_receipts()[0]
    claim = receipt["relation_claims"][0]
    claim["evidence_basis"] = "QUALIFIED_SCHEMA_SCOPE"
    claim.pop("review_record")
    receipt = _reseal_qualification_receipt(receipt)
    changed = compile_schema_mapping(
        title_literal=mapping["title_literal"],
        headers=[
            {"column": item["column"], "literal": item["header_literal"]}
            for item in mapping["columns"]
        ],
        model_columns=[
            {"column": item["column"], "semantic_role": item["semantic_role"]}
            for item in mapping["columns"]
        ],
        amount_currency_bindings=mapping["amount_currency_bindings"],
        side_values=mapping["side_values"],
        qualification_ref={
            "qualification_id": receipt["qualification_id"],
            "receipt_sha256": receipt["receipt_sha256"],
        },
    )

    with pytest.raises(RuntimeError) as rejected:
        validate_qualified_mapping(mapping=changed, receipt=receipt)

    assert rejected.value.args == (
        "ordinary_trade_mapping_relation_claim_invalid",
    )


def _activate_pdf_text_canonical(*, store, context, document_id: str, text: str):
    retention = build_retention_policy(mode="api_smoke")
    source_ref = f"zero-observation-source-{document_id}"
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
            source_file_ref={"openwebui_file_id": f"file-{document_id}"},
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
    artifact = CanonicalNormalizerFactory(
        CanonicalNormalizerConfig(
            normalizer_version="zero-observation-product-path-test-v1"
        )
    ).create().build(
        tenant_id=context.user_id,
        artifact_version=1,
        document={
            "container_format": "pdf",
            "sha256": hashlib.sha256(document_id.encode("utf-8")).hexdigest(),
            "declared_mime_type": "application/pdf",
        },
        source_artifact_ref=source_ref,
        source_payloads=[
            {
                "parser_completeness_status": "complete",
                "parser_completeness_reason_codes": [],
                "pdf_text_layer_projection": {
                    "page_inventory": [{"page_number": 1}],
                    "line_inventory": [{"line_ref": f"line-{document_id}"}],
                },
            }
        ],
        source_units=[
            {
                "unit_ref": f"text-unit-{document_id}",
                "pdf_unit_type": "pdf_page_text_unit",
                "source_location": {"page": 1, "line_start": 1},
                "coverage": {
                    "selected_source_refs": [f"atom-{document_id}"],
                    "all_selected_refs_accounted": True,
                },
                "text": text,
            }
        ],
        table_projections=[],
    )
    persisted = CanonicalArtifactStoreFactory(
        store=store,
        config=CanonicalStorageConfig(capacity_check_enabled=False),
    ).create().put_candidate(
        artifact=artifact,
        context=context,
        retention_policy=retention,
        compare_receipt=None,
    )
    CanonicalReaderFactory(store=store, read_enabled=True).create().activate(
        canonical_version_id=persisted.canonical_version_id,
        expected_previous_version_id=None,
        context=context,
        actor="zero-observation-product-path-test",
        reason="prove PDF zero-observation coverage blocks declaration",
    )
    return persisted


def _reseal_qualification_receipt(receipt: dict[str, object]) -> dict[str, object]:
    material = copy.deepcopy(receipt)
    material.pop("receipt_sha256")
    material.pop("qualification_id")
    qualification_id = "otqual_" + _sha256_json(material)[:32]
    resealed = {**material, "qualification_id": qualification_id}
    resealed["receipt_sha256"] = _sha256_json(resealed)
    return resealed


def _sha256_json(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _literal_for_role(role: str) -> str:
    return {
        "trade_date": "01.02.2026 10:00:00",
        "settlement_date": "03.02.2026",
        "trade_time": "10:00:00",
        "asset_name": "ACME",
        "security_code": "RU0000000000",
        "currency": "RUB",
        "side": "Продажа",
        "quantity": "2",
        "unit_price": "10.00",
        "gross_amount": "20.00",
        "accrued_interest": "0",
        "broker_commission": "1.00",
        "exchange_commission": "2.00",
        "trade_id": "trade-1",
        "comment": "",
        "status": "Исполнена",
        "unmapped": "",
        "venue": "MOEX",
    }[role]


def _row_for_mapping(
    mapping: dict,
    *,
    side: str,
    trade_date: str,
    asset: str,
    quantity: str,
    gross_amount: str,
) -> tuple[str, ...]:
    side_literal = next(
        item["source_literal"]
        for item in mapping["side_values"]
        if item["normalized_value"] == side
    )
    overrides = {
        "trade_date": trade_date,
        "asset_name": asset,
        "quantity": quantity,
        "gross_amount": gross_amount,
        "side": side_literal,
    }
    return tuple(
        overrides.get(item["semantic_role"], _literal_for_role(item["semantic_role"]))
        for item in mapping["columns"]
    )
