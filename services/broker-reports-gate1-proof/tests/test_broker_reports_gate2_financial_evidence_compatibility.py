from __future__ import annotations

import ast
import copy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from broker_reports_gate1.gate2_financial_evidence_catalog import (  # noqa: E402
    LEGACY_BROAD_FINANCIAL_IDS,
    SUPPORTED_SOURCE_FAMILIES,
)
from broker_reports_gate1.gate2_financial_evidence_compatibility import (  # noqa: E402
    COMPATIBILITY_POLICY_VERSION,
    DUAL_READ_RESULT_SCHEMA_VERSION,
    ExplicitLegacyFinancialEvidenceMapping,
    Gate2FinancialEvidenceCompatibilityError,
    Gate2FinancialEvidenceCompatibilityFactory,
)
from broker_reports_gate1.gate2_financial_evidence_decision import (  # noqa: E402
    FinancialEvidenceDecisionPackage,
    FinancialEvidenceValueCandidate,
    Gate2FinancialEvidenceDecisionContractFactory,
)
from broker_reports_gate1.gate2_financial_evidence_legacy_validation import (  # noqa: E402
    LEGACY_VALIDATOR_ID,
    LEGACY_VALIDATOR_POLICY_VERSION,
    PinnedLegacySourceFactsValidatorFactory,
)
from broker_reports_gate1.gate2_financial_evidence_materialization import (  # noqa: E402
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
from broker_reports_gate1.gate2_fns_2ndfl_contracts import (  # noqa: E402
    ADAPTER_ID,
    ADAPTER_VERSION,
    FACT_RESTRICTIONS,
    FNS_SCHEMA_FAMILY,
    TYPED_FACTS_SCHEMA_VERSION,
    integrity_ref,
)


BOUNDARY_MODULE_PATHS = (
    ROOT
    / "broker_reports_gate1"
    / "gate2_financial_evidence_compatibility.py",
    ROOT
    / "broker_reports_gate1"
    / "gate2_financial_evidence_legacy_validation.py",
)


def _registry():
    return Gate2FinancialEvidenceRegistryFactory().create()


def _compatibility():
    return Gate2FinancialEvidenceCompatibilityFactory(
        registry=_registry()
    ).create()


def _legacy_fact(
    fact_id: str,
    fact_type: str,
    source_ref: str,
):
    return {
        "fact_id": fact_id,
        "fact_type": fact_type,
        "validator_status": "passed",
        "validation_ref": "validation:legacy:1",
        "evidence_refs": [source_ref],
        "source_location": {
            "row_ref": source_ref,
            "text_segment_refs": [source_ref],
        },
    }


def _legacy_payload():
    facts = [
        _legacy_fact(
            "legacy-fact:trade:1",
            "trade_operation",
            "source:row:1",
        ),
        _legacy_fact(
            "legacy-fact:summary:1",
            "document_summary_evidence",
            "source:row:2",
        ),
        _legacy_fact(
            "legacy-fact:unknown:1",
            "unknown_source_row",
            "source:row:3",
        ),
    ]
    return {
        "schema_version": "broker_reports_source_facts_v0",
        "source_facts_set_id": "legacy-set:1",
        "extraction_run_id": "legacy-run:1",
        "normalization_run_id": "legacy-normalization:1",
        "case_id": "legacy-case:synthetic",
        "package_refs": ["legacy-package:1"],
        "document_refs": ["legacy-document:1"],
        "facts": facts,
        "coverage": {
            "unit_coverage_ref": "legacy-coverage:1",
            "selected_source_refs": [
                "source:row:1",
                "source:row:2",
                "source:row:3",
            ],
            "fact_covered_refs": [
                "source:row:1",
                "source:row:2",
                "source:row:3",
            ],
            "no_fact_results": [],
            "rejected_refs": [],
            "pending_refs": [],
            "coverage_status": "complete",
        },
        "issue_linkage_summary": {
            "package_issue_refs": [],
            "fact_issue_links_total": 0,
            "unresolved_issue_refs": [],
        },
        "extraction_audit": {
            "prompt_contract_id": "legacy-pinned-synthetic"
        },
        "validation_ref": "validation:legacy:1",
        "validator_status": "passed",
        "created_at": "2026-01-01T00:00:00Z",
    }


def _successor_artifact():
    registry = _registry()
    definitions = (
        (
            "amount",
            "source_decimal",
            "120.50",
            ("amount",),
        ),
        (
            "date",
            "source_date",
            "2025-12-31",
            ("as_of_date",),
        ),
        (
            "scope",
            "source_reference",
            "Synthetic statement",
            ("statement_scope",),
        ),
    )
    candidates = tuple(
        FinancialEvidenceValueCandidate(
            source_value_ref=f"value:{name}:migration",
            source_ref=f"source:{name}:migration",
            value_type=value_type,
            allowed_roles=roles,
        )
        for name, value_type, _, roles in definitions
    )
    source_values = tuple(
        FinancialEvidenceAuthoritativeSourceValue(
            source_value_ref=f"value:{name}:migration",
            source_ref=f"source:{name}:migration",
            value_type=value_type,
            literal_value=literal,
            source_evidence_refs=(f"evidence:{name}:migration",),
            lineage=FinancialEvidenceSourceLineage(
                document_ref="document:synthetic:migration",
                page_ref="page:migration:1",
                table_ref="table:migration:1",
                row_ref=f"row:migration:{index}",
            ),
        )
        for index, (
            name,
            value_type,
            literal,
            _,
        ) in enumerate(definitions, start=1)
    )
    decision_package = FinancialEvidenceDecisionPackage(
        source_scope_ref="scope:table:migration",
        source_family_id=SUPPORTED_SOURCE_FAMILIES[0],
        candidates=candidates,
    )
    contract = Gate2FinancialEvidenceDecisionContractFactory(
        registry=registry,
        package=decision_package,
    ).create()
    validated = Gate2FinancialEvidenceValidatedDecisionFactory(
        contract=contract
    ).create(
        {
            "decision": {
                "disposition": "typed_input",
                "input_type_id": "cash_balance_snapshot_v1",
                "value_bindings": {
                    "amount": "value:amount:migration",
                    "as_of_date": "value:date:migration",
                    "statement_scope": "value:scope:migration",
                    "balance_class": None,
                    "currency": None,
                    "source_label": None,
                    "unit": None,
                },
                "reason_code": "typed_supported",
            }
        }
    )
    source_package = Gate2FinancialEvidenceSourcePackageFactory(
        package_ref="source-package:synthetic:migration",
        normalization_run_ref="normalization:synthetic:migration",
        document_ref="document:synthetic:migration",
        source_scope_ref="scope:table:migration",
        source_family_id=SUPPORTED_SOURCE_FAMILIES[0],
        source_values=source_values,
        source_evidence_refs=("evidence:document:migration",),
        completeness="complete",
    ).create()
    return Gate2FinancialEvidenceMaterializerFactory(
        registry=registry,
        source_package=source_package,
        execution_metadata=FinancialEvidenceExecutionMetadata(
            execution_ref="execution:synthetic:migration",
            decision_validation_ref="validation:synthetic:migration",
        ),
    ).create().materialize(validated_decision=validated)


def _fns_fact(family: str, index: int):
    fact_id = f"fns-fact:{index}"
    node_ref = f"fns-node:{index}"
    value_ref = f"fns-value:{index}"
    fact = {
        "fact_id": fact_id,
        "fact_family": family,
        "source_document_ref": "fns-document:synthetic",
        "source_package_ref": "fns-package:synthetic",
        "adapter_id": ADAPTER_ID,
        "adapter_version": ADAPTER_VERSION,
        "schema_family": FNS_SCHEMA_FAMILY,
        "schema_version_id": "fns-schema:synthetic",
        "validation_status": "validated",
        "restrictions": list(FACT_RESTRICTIONS),
        "original_node_refs": [node_ref],
        "original_value_refs": [value_ref],
        "fields": [
            {
                "field_code": f"synthetic_field_{index}",
                "value_type": "source_text",
                "value": "synthetic",
                "original_value_ref": value_ref,
                "original_node_ref": node_ref,
            }
        ],
    }
    if family in {
        "income_source_row",
        "deduction_source_row",
        "tax_summary_source_fact",
    }:
        fact["source_section_ref"] = node_ref
    fact["integrity_ref"] = integrity_ref("fnsfactchk", fact)
    return fact


def _fns_payload():
    families = (
        "source_certificate_identity",
        "tax_agent_identity",
        "recipient_identity",
        "income_source_row",
        "tax_summary_source_fact",
        "certificate_metadata",
    )
    payload = {
        "schema_version": TYPED_FACTS_SCHEMA_VERSION,
        "adapter_id": ADAPTER_ID,
        "adapter_version": ADAPTER_VERSION,
        "schema_family": FNS_SCHEMA_FAMILY,
        "terminal_status": "validated",
        "source_document_ref": "fns-document:synthetic",
        "source_package_ref": "fns-package:synthetic",
        "schema_version_id": "fns-schema:synthetic",
        "report_period": "2025",
        "vendor_extensions": [],
        "non_fact_source_nodes": [],
        "provider_accounting": {
            "calls": 0,
            "tokens": 0,
            "cost": 0,
            "llm_fallback_allowed": False,
        },
        "facts": [
            _fns_fact(family, index)
            for index, family in enumerate(families, start=1)
        ],
    }
    payload["integrity_ref"] = integrity_ref("fnsoutchk", payload)
    return payload


def test_compatibility_policy_and_pinned_validator_are_explicit():
    assert COMPATIBILITY_POLICY_VERSION == (
        "broker_reports_financial_evidence_compatibility_v1"
    )
    assert DUAL_READ_RESULT_SCHEMA_VERSION == (
        "broker_reports_financial_evidence_dual_read_result_v1"
    )
    assert LEGACY_VALIDATOR_ID == (
        "broker_reports_legacy_source_facts_validator_v1"
    )
    assert LEGACY_VALIDATOR_POLICY_VERSION == (
        "broker_reports_legacy_source_facts_replay_policy_v1"
    )


def test_legacy_artifact_is_readable_without_payload_rewrite():
    payload = _legacy_payload()
    original = copy.deepcopy(payload)
    result = _compatibility().read(
        artifact_ref="artifact:legacy:1",
        payload=payload,
    )

    assert result.read_kind == "legacy_source_facts"
    assert result.validator_id == LEGACY_VALIDATOR_ID
    assert result.validator_status == "passed"
    assert result.payload_copy() == original
    assert payload == original
    assert result.artifact_schema_version == (
        "broker_reports_source_facts_v0"
    )


def test_legacy_namespaces_are_separate_and_all_mappings_are_unmapped():
    result = _compatibility().read(
        artifact_ref="artifact:legacy:1",
        payload=_legacy_payload(),
    )
    by_type = {item.source_type_id: item for item in result.records}

    assert by_type["trade_operation"].namespace == (
        "legacy_financial_input"
    )
    assert by_type["document_summary_evidence"].namespace == (
        "evidence_kind"
    )
    assert by_type["unknown_source_row"].namespace == (
        "legacy_technical_disposition"
    )
    assert all(item.mapping_status == "unmapped" for item in result.records)
    assert all(
        item.canonical_input_type_id is None for item in result.records
    )


def test_no_legacy_broad_id_is_registry_type_or_alias():
    registry = _registry()
    canonical = set(registry.provider_type_enum())
    aliases = {item.alias_id for item in registry.aliases}

    assert set(LEGACY_BROAD_FINANCIAL_IDS).isdisjoint(canonical)
    assert set(LEGACY_BROAD_FINANCIAL_IDS).isdisjoint(aliases)
    assert registry.aliases == ()


def test_invalid_or_nonterminal_legacy_artifact_fails_pinned_validation():
    payload = _legacy_payload()
    payload["validator_status"] = "pending"

    validation = (
        PinnedLegacySourceFactsValidatorFactory().create().validate(payload)
    )
    assert validation["validator_status"] == "failed"
    assert any(
        item["code"] == "legacy_artifact_not_terminally_validated"
        for item in validation["errors"]
    )
    with pytest.raises(Gate2FinancialEvidenceCompatibilityError) as exc:
        _compatibility().read(
            artifact_ref="artifact:legacy:invalid",
            payload=payload,
        )
    assert exc.value.code == (
        "financial_evidence_legacy_validation_failed"
    )


def test_legacy_replay_is_exact_and_passes_with_same_payload():
    compatibility = _compatibility()
    payload = _legacy_payload()
    read = compatibility.read(
        artifact_ref="artifact:legacy:1",
        payload=payload,
    )
    receipt = compatibility.replay(expected=read, payload=payload)

    assert receipt["replay_status"] == "passed"
    assert receipt["validator_id"] == LEGACY_VALIDATOR_ID
    assert receipt["artifact_sha256"] == read.artifact_sha256
    assert receipt["payload_rewritten"] is False


def test_replay_rejects_any_persisted_payload_change():
    compatibility = _compatibility()
    payload = _legacy_payload()
    read = compatibility.read(
        artifact_ref="artifact:legacy:1",
        payload=payload,
    )
    changed = copy.deepcopy(payload)
    changed["created_at"] = "2026-01-02T00:00:00Z"

    with pytest.raises(Gate2FinancialEvidenceCompatibilityError) as exc:
        compatibility.replay(expected=read, payload=changed)

    assert exc.value.code == (
        "financial_evidence_compatibility_replay_mismatch"
    )


def test_successor_artifact_is_dual_read_as_native_contract():
    result = _compatibility().read(
        artifact_ref="artifact:successor:1",
        payload=_successor_artifact(),
    )

    assert result.read_kind == "successor_financial_evidence"
    assert len(result.records) == 1
    assert result.records[0].source_type_id == (
        "cash_balance_snapshot_v1"
    )
    assert result.records[0].mapping_status == "native"
    assert result.records[0].canonical_input_type_id == (
        "cash_balance_snapshot_v1"
    )


def test_write_policy_rejects_legacy_and_accepts_successor_only():
    compatibility = _compatibility()
    successor = _successor_artifact()

    assert compatibility.validate_write_contract(successor) == successor
    with pytest.raises(Gate2FinancialEvidenceCompatibilityError) as exc:
        compatibility.validate_write_contract(_legacy_payload())
    assert exc.value.code == "financial_evidence_legacy_write_forbidden"


def test_explicit_migration_prepares_single_successor_write():
    compatibility = _compatibility()
    source = compatibility.read(
        artifact_ref="artifact:legacy:1",
        payload=_legacy_payload(),
    )
    target = _successor_artifact()
    target_id = target["typed_inputs"][0]["input_id"]
    mappings = tuple(
        ExplicitLegacyFinancialEvidenceMapping(
            legacy_record_id=item.record_id,
            target_terminal_id=target_id,
            mapping_basis_ref=f"mapping-basis:{index}",
        )
        for index, item in enumerate(source.records, start=1)
    )

    prepared = compatibility.prepare_migration_write(
        source=source,
        target_payload=target,
        explicit_mappings=mappings,
    )

    assert prepared.payload_copy() == target
    assert prepared.receipt["write_contract"] == (
        "single_write_successor_only"
    )
    assert prepared.receipt["source_payload_rewritten"] is False
    assert prepared.receipt["automatic_aliases_used"] is False
    assert len(prepared.receipt["explicit_mappings"]) == 3
    assert prepared.receipt["target_schema_version"] == (
        "broker_reports_financial_evidence_inputs_v1"
    )


def test_migration_requires_complete_explicit_mapping():
    compatibility = _compatibility()
    source = compatibility.read(
        artifact_ref="artifact:legacy:1",
        payload=_legacy_payload(),
    )
    target = _successor_artifact()

    with pytest.raises(Gate2FinancialEvidenceCompatibilityError) as exc:
        compatibility.prepare_migration_write(
            source=source,
            target_payload=target,
            explicit_mappings=(),
        )

    assert exc.value.code == (
        "financial_evidence_explicit_mapping_incomplete"
    )


def test_migration_rejects_mapping_to_unknown_target():
    compatibility = _compatibility()
    source = compatibility.read(
        artifact_ref="artifact:legacy:1",
        payload=_legacy_payload(),
    )
    mappings = tuple(
        ExplicitLegacyFinancialEvidenceMapping(
            legacy_record_id=item.record_id,
            target_terminal_id="finin:unknown",
            mapping_basis_ref=f"mapping-basis:{index}",
        )
        for index, item in enumerate(source.records, start=1)
    )

    with pytest.raises(Gate2FinancialEvidenceCompatibilityError) as exc:
        compatibility.prepare_migration_write(
            source=source,
            target_payload=_successor_artifact(),
            explicit_mappings=mappings,
        )
    assert exc.value.code == (
        "financial_evidence_explicit_mapping_target_invalid"
    )


def test_fns_specialized_family_reads_separately_without_mapping():
    result = _compatibility().read(
        artifact_ref="artifact:fns:1",
        payload=_fns_payload(),
    )

    assert result.read_kind == "fns_specialized"
    assert len(result.records) == 6
    assert all(
        item.namespace == "fns_specialized_fact_family"
        and item.mapping_status == "separate"
        and item.canonical_input_type_id is None
        for item in result.records
    )


def test_fns_migration_is_forbidden_until_explicit_family_mapping():
    compatibility = _compatibility()
    source = compatibility.read(
        artifact_ref="artifact:fns:1",
        payload=_fns_payload(),
    )

    with pytest.raises(Gate2FinancialEvidenceCompatibilityError) as exc:
        compatibility.prepare_migration_write(
            source=source,
            target_payload=_successor_artifact(),
            explicit_mappings=(),
        )
    assert exc.value.code == "financial_evidence_fns_mapping_not_adopted"


def test_unknown_artifact_schema_is_not_guessed():
    with pytest.raises(Gate2FinancialEvidenceCompatibilityError) as exc:
        _compatibility().read(
            artifact_ref="artifact:unknown:1",
            payload={"schema_version": "future_unknown_v9"},
        )
    assert exc.value.code == (
        "financial_evidence_compatibility_schema_unsupported"
    )


def test_compatibility_is_factory_managed_pure_and_closed_world():
    sources = [
        path.read_text(encoding="utf-8")
        for path in BOUNDARY_MODULE_PATHS
    ]
    source = "\n".join(sources)
    trees = [ast.parse(item) for item in sources]
    imported_modules = {
        node.module
        for tree in trees
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    } | {
        alias.name
        for tree in trees
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }

    assert "Gate2FinancialEvidenceCompatibilityFactory.create" in source
    assert "PinnedLegacySourceFactsValidatorFactory.create" in source
    assert "must not rewrite persisted payloads" in source
    assert imported_modules <= {
        "__future__",
        "copy",
        "dataclasses",
        "gate2_financial_evidence_catalog",
        "gate2_financial_evidence_legacy_validation",
        "gate2_financial_evidence_materialization_contracts",
        "gate2_financial_evidence_materialization_validation",
        "gate2_financial_evidence_registry",
        "gate2_fns_2ndfl_contracts",
        "gate2_source_fact_contracts",
        "json",
        "typing",
    }
    assert "artifact_store" not in source
    assert "provider_clients" not in source
    assert "persist(" not in source
