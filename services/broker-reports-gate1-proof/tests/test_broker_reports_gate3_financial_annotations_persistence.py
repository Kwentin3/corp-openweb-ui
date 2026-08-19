from __future__ import annotations

import copy
import hashlib
from pathlib import Path

import pytest

from broker_reports_gate1 import (
    ArtifactAccessContext,
    ArtifactStoreConfig,
    ArtifactStoreFactory,
    CanonicalArtifactStoreFactory,
    CanonicalNormalizerConfig,
    CanonicalNormalizerFactory,
    CanonicalReaderFactory,
    CanonicalStorageConfig,
    GATE3_CHUNK_BATCH_LABELING_RESULT_SCHEMA_VERSION,
    Gate3FinancialAnnotationsPersistenceError,
    Gate3FinancialAnnotationsPersistenceFactory,
    Gate3StructuralChunkFactory,
    Gate4FinancialCaseRuntimeFactory,
    Gate5DeterministicSourceFactConsumptionRuntimeFactory,
    build_retention_policy,
)
from broker_reports_gate1.artifact_lifecycle import lifecycle_for_visibility
from broker_reports_gate1.artifact_models import ArtifactRecord, ArtifactStoreError
from broker_reports_gate1.gate3_financial_annotations_persistence import (
    FACTORY_REQUIRED,
    FORBIDDEN,
    GATE3_FINANCIAL_ANNOTATIONS_ARTIFACT_TYPE,
    GATE3_HISTORICAL_FINANCIAL_ANNOTATIONS_ARTIFACT_TYPE,
)
from broker_reports_gate1.gate3_financial_label_dictionary import (
    GATE3_DICTIONARY_CURRENT_VERSION,
)
from broker_reports_gate1.gate3_financial_role_pack import (
    GATE3_ROLE_PACK_CURRENT_VERSION,
    Gate3FinancialRolePackFactory,
)
from broker_reports_gate1.gate3_role_labeling import (
    GATE3_ROLE_LABELING_INSTRUCTION_VERSION,
)
from broker_reports_gate1.gate5_trusted_methodology import (
    GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_ID,
    GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_VERSION,
    GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION,
)


MODEL_ID = "models/gemini-3.5-flash"
PROVIDER_PROFILE_ID = "google_gemini"


def test_save_read_access_binding_and_retention(tmp_path: Path) -> None:
    store, context, document_id, canonical = _setup(tmp_path)
    service = Gate3FinancialAnnotationsPersistenceFactory(
        store=store, read_enabled=True
    ).create()
    result = _complete_result(store, context, document_id)

    stored = service.save(
        document_id=document_id,
        context=context,
        validated_document_result=result,
        provider_profile_id=PROVIDER_PROFILE_ID,
    )

    assert stored.artifact_type == GATE3_FINANCIAL_ANNOTATIONS_ARTIFACT_TYPE
    assert stored.visibility == "private_case"
    assert stored.storage_backend == "project_artifact_payload"
    assert stored.validation_status == "validated"
    assert stored.safe_metadata == {
        "provider_profile_id": PROVIDER_PROFILE_ID,
        "document_completion_status": "complete",
        "source_fact_completeness_status": "incomplete",
        "annotations_total": 1,
        "facts_role_complete": 0,
        "facts_role_incomplete": 1,
        "facts_incomplete_due_to_role_rejection": 0,
        "facts_rejected": 0,
        "role_bindings_rejected": 0,
        "chunks_with_local_failures": 0,
        "publication_mode": "FULL",
        "semantic_view_mode": "FULL_CURRENT_VIEW",
    }
    payload = service.read(artifact_id=stored.artifact_id, context=context)
    assert payload == result["merged_output"]
    assert payload["canonical_binding"]["canonical_version_id"] == (
        canonical.canonical_version_id
    )
    version = store.get_active_canonical_version(
        context=context, document_id=document_id
    )
    manifest = store.get_record_unchecked(version.manifest_ref)
    assert manifest is not None
    assert stored.retention_policy == manifest.retention_policy

    denied = copy.deepcopy(context)
    object.__setattr__(denied, "user_id", "different-user")
    with pytest.raises(ArtifactStoreError) as failure:
        service.read(artifact_id=stored.artifact_id, context=denied)
    assert failure.value.code == "artifact_access_denied"


def test_local_role_rejection_accounting_survives_immutable_sidecar_write(
    tmp_path: Path,
) -> None:
    store, context, document_id, _canonical = _setup(tmp_path)
    service = Gate3FinancialAnnotationsPersistenceFactory(
        store=store, read_enabled=True
    ).create()
    result = _complete_result(store, context, document_id)
    result["metrics"].update(
        {
            "chunks_with_local_failures": 1,
            "facts_incomplete_due_to_role_rejection": 1,
            "role_bindings_rejected": 1,
        }
    )

    stored = service.save(
        document_id=document_id,
        context=context,
        validated_document_result=result,
        provider_profile_id=PROVIDER_PROFILE_ID,
    )

    assert stored.validation_status == "validated"
    assert stored.safe_metadata["document_completion_status"] == "complete"
    assert stored.safe_metadata["source_fact_completeness_status"] == "incomplete"
    assert stored.safe_metadata["chunks_with_local_failures"] == 1
    assert stored.safe_metadata["facts_incomplete_due_to_role_rejection"] == 1
    assert stored.safe_metadata["role_bindings_rejected"] == 1
    assert service.read(artifact_id=stored.artifact_id, context=context) == result[
        "merged_output"
    ]


def test_sidecar_is_immutable_and_relabel_does_not_mutate_gate2(
    tmp_path: Path,
) -> None:
    store, context, document_id, _canonical = _setup(tmp_path)
    reader = CanonicalReaderFactory(store=store, read_enabled=True).create()
    canonical_before = reader.read_active_envelope(document_id, context)
    service = Gate3FinancialAnnotationsPersistenceFactory(
        store=store, read_enabled=True
    ).create()
    first_result = _complete_result(store, context, document_id)
    first = service.save(
        document_id=document_id,
        context=context,
        validated_document_result=first_result,
        provider_profile_id=PROVIDER_PROFILE_ID,
    )
    second_result = copy.deepcopy(first_result)
    second_result["merged_output"]["annotations"][0]["financial_label"] = "TAX_WITHHELD"
    second = service.save(
        document_id=document_id,
        context=context,
        validated_document_result=second_result,
        provider_profile_id=PROVIDER_PROFILE_ID,
    )

    assert first.artifact_id != second.artifact_id
    assert (
        service.read(artifact_id=first.artifact_id, context=context)
        == (first_result["merged_output"])
    )
    assert (
        service.read(artifact_id=second.artifact_id, context=context)
        == (second_result["merged_output"])
    )
    mutated = copy.deepcopy(first)
    mutated.payload = copy.deepcopy(second_result["merged_output"])
    with pytest.raises(ArtifactStoreError) as immutable:
        store.put_record(mutated)
    assert immutable.value.code == "artifact_immutable"
    canonical_after = reader.read_active_envelope(document_id, context)
    assert canonical_after.canonical_version_id == canonical_before.canonical_version_id
    assert (
        canonical_after.canonical_root_sha256 == canonical_before.canonical_root_sha256
    )


def test_demand_scoped_result_cannot_use_full_publication_entrypoint(
    tmp_path: Path,
) -> None:
    store, context, document_id, _canonical = _setup(tmp_path)
    service = Gate3FinancialAnnotationsPersistenceFactory(
        store=store, read_enabled=True
    ).create()
    demand = _demand_result(
        _complete_result(store, context, document_id),
        labels=["TRANSACTION_CHARGE"],
    )

    with pytest.raises(Gate3FinancialAnnotationsPersistenceError) as failure:
        service.save(
            document_id=document_id,
            context=context,
            validated_document_result=demand,
            provider_profile_id=PROVIDER_PROFILE_ID,
        )
    assert failure.value.code == "gate3_annotations_publication_scope_invalid"


def test_recovery_preserves_unrelated_adds_different_target_and_supersedes_exact(
    tmp_path: Path,
) -> None:
    store, context, document_id, _canonical = _setup(tmp_path)
    service = Gate3FinancialAnnotationsPersistenceFactory(
        store=store, read_enabled=True
    ).create()
    full = _complete_result(store, context, document_id)
    targets = _targets(store, context, document_id)
    full["merged_output"]["annotations"] = [
        _annotation("TRANSACTION_CHARGE", targets[0]),
        _annotation("TAX_WITHHELD", targets[1]),
        _annotation("SECURITY_PURCHASE", targets[2]),
    ]
    _refresh_metrics(full)
    base = service.save(
        document_id=document_id,
        context=context,
        validated_document_result=full,
        provider_profile_id=PROVIDER_PROFILE_ID,
    )
    completed = _annotation("SECURITY_PURCHASE", targets[2])
    completed["roles"][3] = {
        "role": "amount",
        "status": "bound",
        "target": copy.deepcopy(targets[2]),
        "exact_text": "12.00",
    }
    added = _annotation("SECURITY_PURCHASE", targets[3])
    demand = _demand_result(
        full,
        labels=["SECURITY_PURCHASE"],
        annotations=[completed, added],
    )

    recovered = service.save_recovery(
        document_id=document_id,
        context=context,
        validated_document_result=demand,
        provider_profile_id=PROVIDER_PROFILE_ID,
        base_annotations_artifact_id=base.artifact_id,
        demand_request_id="demand-purchase",
    )
    payload = service.read(
        artifact_id=recovered.record.artifact_id,
        context=context,
    )

    assert [item["financial_label"] for item in payload["annotations"]] == [
        "TRANSACTION_CHARGE",
        "TAX_WITHHELD",
        "SECURITY_PURCHASE",
        "SECURITY_PURCHASE",
    ]
    assert payload["annotations"][2] == completed
    assert recovered.receipt["added_total"] == 1
    assert recovered.receipt["superseded_total"] == 1
    assert recovered.receipt["preserved_unrelated_total"] == 2
    assert recovered.receipt["deleted_total"] == 0
    assert recovered.record.safe_metadata["publication_mode"] == "DEMAND_SCOPED"
    assert recovered.record.safe_metadata["semantic_view_mode"] == ("FULL_CURRENT_VIEW")


def test_recovery_supersedes_cell_anchor_with_proven_same_row_anchor(
    tmp_path: Path,
) -> None:
    store, context, document_id, _canonical = _setup(tmp_path, with_table=True)
    service = Gate3FinancialAnnotationsPersistenceFactory(
        store=store, read_enabled=True
    ).create()
    full = _complete_result(store, context, document_id)
    text_target = copy.deepcopy(full["merged_output"]["annotations"][0]["target"])
    row_target, cells = _table_targets(store, context, document_id, row=2)
    existing = _bound_purchase(cells[6], cells)
    existing["roles"][2] = {"role": "quantity", "status": "missing"}
    full["merged_output"]["annotations"] = [
        _annotation("TRANSACTION_CHARGE", text_target),
        existing,
    ]
    _refresh_metrics(full)
    base = service.save(
        document_id=document_id,
        context=context,
        validated_document_result=full,
        provider_profile_id=PROVIDER_PROFILE_ID,
    )
    proposal = _bound_purchase(row_target, cells)
    demand = _demand_result(
        full,
        labels=["SECURITY_PURCHASE"],
        annotations=[proposal],
    )

    recovered = service.save_recovery(
        document_id=document_id,
        context=context,
        validated_document_result=demand,
        provider_profile_id=PROVIDER_PROFILE_ID,
        base_annotations_artifact_id=base.artifact_id,
        demand_request_id="same-source-row-refinement",
    )
    payload = service.read(artifact_id=recovered.record.artifact_id, context=context)

    assert payload["annotations"] == [
        _annotation("TRANSACTION_CHARGE", text_target),
        proposal,
    ]
    assert recovered.receipt["superseded_total"] == 1
    assert recovered.receipt["added_total"] == 0
    assert recovered.receipt["preserved_unrelated_total"] == 1
    assert recovered.receipt["deleted_total"] == 0


def test_recovery_does_not_collapse_equal_values_from_different_rows(
    tmp_path: Path,
) -> None:
    store, context, document_id, _canonical = _setup(tmp_path, with_table=True)
    service = Gate3FinancialAnnotationsPersistenceFactory(
        store=store, read_enabled=True
    ).create()
    full = _complete_result(store, context, document_id)
    _row_two, cells_two = _table_targets(store, context, document_id, row=2)
    row_three, cells_three = _table_targets(store, context, document_id, row=3)
    existing = _bound_purchase(cells_two[6], cells_two)
    proposal = _bound_purchase(row_three, cells_three)
    full["merged_output"]["annotations"] = [existing]
    _refresh_metrics(full)
    base = service.save(
        document_id=document_id,
        context=context,
        validated_document_result=full,
        provider_profile_id=PROVIDER_PROFILE_ID,
    )

    recovered = service.save_recovery(
        document_id=document_id,
        context=context,
        validated_document_result=_demand_result(
            full,
            labels=["SECURITY_PURCHASE"],
            annotations=[proposal],
        ),
        provider_profile_id=PROVIDER_PROFILE_ID,
        base_annotations_artifact_id=base.artifact_id,
        demand_request_id="same-values-different-rows",
    )
    payload = service.read(artifact_id=recovered.record.artifact_id, context=context)

    assert payload["annotations"] == [existing, proposal]
    assert recovered.receipt["added_total"] == 1
    assert recovered.receipt["superseded_total"] == 0


def test_recovery_does_not_collapse_unproven_cell_to_cell_overlap(
    tmp_path: Path,
) -> None:
    store, context, document_id, _canonical = _setup(tmp_path, with_table=True)
    service = Gate3FinancialAnnotationsPersistenceFactory(
        store=store, read_enabled=True
    ).create()
    full = _complete_result(store, context, document_id)
    _row_target, cells = _table_targets(store, context, document_id, row=2)
    existing = _bound_purchase(cells[6], cells)
    proposal = _bound_purchase(cells[0], cells)
    full["merged_output"]["annotations"] = [existing]
    _refresh_metrics(full)
    base = service.save(
        document_id=document_id,
        context=context,
        validated_document_result=full,
        provider_profile_id=PROVIDER_PROFILE_ID,
    )

    recovered = service.save_recovery(
        document_id=document_id,
        context=context,
        validated_document_result=_demand_result(
            full,
            labels=["SECURITY_PURCHASE"],
            annotations=[proposal],
        ),
        provider_profile_id=PROVIDER_PROFILE_ID,
        base_annotations_artifact_id=base.artifact_id,
        demand_request_id="unproven-cell-overlap",
    )

    assert recovered.receipt["added_total"] == 1
    assert recovered.receipt["superseded_total"] == 0


def test_recovery_does_not_merge_different_labels_on_same_row(
    tmp_path: Path,
) -> None:
    store, context, document_id, _canonical = _setup(tmp_path, with_table=True)
    service = Gate3FinancialAnnotationsPersistenceFactory(
        store=store, read_enabled=True
    ).create()
    full = _complete_result(store, context, document_id)
    row_target, cells = _table_targets(store, context, document_id, row=2)
    purchase = _bound_purchase(cells[6], cells)
    charge = _annotation("TRANSACTION_CHARGE", row_target)
    full["merged_output"]["annotations"] = [purchase]
    _refresh_metrics(full)
    base = service.save(
        document_id=document_id,
        context=context,
        validated_document_result=full,
        provider_profile_id=PROVIDER_PROFILE_ID,
    )

    recovered = service.save_recovery(
        document_id=document_id,
        context=context,
        validated_document_result=_demand_result(
            full,
            labels=["TRANSACTION_CHARGE"],
            annotations=[charge],
        ),
        provider_profile_id=PROVIDER_PROFILE_ID,
        base_annotations_artifact_id=base.artifact_id,
        demand_request_id="different-label-same-row",
    )

    assert recovered.receipt["added_total"] == 1
    assert recovered.receipt["preserved_unrelated_total"] == 1


def test_same_row_role_conflict_fails_closed_and_downstream_keeps_five(
    tmp_path: Path,
) -> None:
    store, context, document_id, _canonical = _setup(tmp_path, with_table=True)
    service = Gate3FinancialAnnotationsPersistenceFactory(
        store=store, read_enabled=True
    ).create()
    full = _complete_result(store, context, document_id)
    text_targets = [
        target
        for target in _targets(store, context, document_id)
        if target.get("kind") == "node"
    ]
    purchases = []
    proposals = []
    for row in range(2, 7):
        row_target, cells = _table_targets(store, context, document_id, row=row)
        purchases.append(_bound_purchase(cells[6], cells))
        proposals.append(
            _bound_purchase(
                row_target,
                cells,
                amount_column=6,
                currency_column=2,
            )
        )
    unrelated = [
        _annotation(
            "COMMISSION" if index < 8 else "TRANSACTION_CHARGE",
            target,
        )
        for index, target in enumerate(text_targets[:16])
    ]
    full["merged_output"]["annotations"] = [*purchases, *unrelated]
    _refresh_metrics(full)
    base = service.save(
        document_id=document_id,
        context=context,
        validated_document_result=full,
        provider_profile_id=PROVIDER_PROFILE_ID,
    )
    before = len(store.list_by_run(context.normalization_run_id))

    with pytest.raises(Gate3FinancialAnnotationsPersistenceError) as failure:
        service.save_recovery(
            document_id=document_id,
            context=context,
            validated_document_result=_demand_result(
                full,
                labels=["SECURITY_PURCHASE"],
                annotations=proposals,
            ),
            provider_profile_id=PROVIDER_PROFILE_ID,
            base_annotations_artifact_id=base.artifact_id,
            demand_request_id="same-row-conflicting-role-bindings",
        )
    assert failure.value.code == "gate3_annotations_recovery_conflict"
    assert len(store.list_by_run(context.normalization_run_id)) == before

    gate4 = (
        Gate4FinancialCaseRuntimeFactory(store=store, read_enabled=True)
        .create()
        .rebuild_case(context=context)
    )
    labels = [fact["financial_type"] for fact in gate4.facts]
    gate5 = (
        Gate5DeterministicSourceFactConsumptionRuntimeFactory(
            store=store, read_enabled=True
        )
        .create()
        .assess(
            methodology_ref={
                "schema_version": GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION,
                "methodology_id": GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_ID,
                "methodology_version": (
                    GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_VERSION
                ),
            },
            context=context,
        )
    )

    assert len(gate4.facts) == 21
    assert labels.count("SECURITY_PURCHASE") == 5
    assert labels.count("COMMISSION") == 8
    assert labels.count("TRANSACTION_CHARGE") == 8
    assert gate5["facts_total"] == 21
    assert gate5["security_fact_counts"]["total"] == 5
    assert len(gate5["assertions"]["commissions"]["detail"]) == 16


def test_empty_recovery_publishes_identical_full_view_with_zero_deletions(
    tmp_path: Path,
) -> None:
    store, context, document_id, _canonical = _setup(tmp_path)
    service = Gate3FinancialAnnotationsPersistenceFactory(
        store=store, read_enabled=True
    ).create()
    full = _complete_result(store, context, document_id)
    base = service.save(
        document_id=document_id,
        context=context,
        validated_document_result=full,
        provider_profile_id=PROVIDER_PROFILE_ID,
    )
    demand = _demand_result(
        full,
        labels=["SECURITY_PURCHASE"],
        annotations=[],
    )

    recovered = service.save_recovery(
        document_id=document_id,
        context=context,
        validated_document_result=demand,
        provider_profile_id=PROVIDER_PROFILE_ID,
        base_annotations_artifact_id=base.artifact_id,
        demand_request_id="demand-empty",
    )

    assert service.read(
        artifact_id=recovered.record.artifact_id, context=context
    ) == service.read(artifact_id=base.artifact_id, context=context)
    assert recovered.receipt["added_total"] == 0
    assert recovered.receipt["superseded_total"] == 0
    assert recovered.receipt["deleted_total"] == 0


def test_twenty_one_to_five_demand_replay_keeps_all_gate4_and_gate5_facts(
    tmp_path: Path,
) -> None:
    store, context, document_id, _canonical = _setup(tmp_path)
    service = Gate3FinancialAnnotationsPersistenceFactory(
        store=store, read_enabled=True
    ).create()
    full = _complete_result(store, context, document_id)
    targets = _targets(store, context, document_id)
    purchases = [_annotation("SECURITY_PURCHASE", target) for target in targets[:5]]
    unrelated = [
        _annotation(
            "COMMISSION" if index < 8 else "TRANSACTION_CHARGE",
            target,
        )
        for index, target in enumerate(targets[5:21])
    ]
    full["merged_output"]["annotations"] = [*purchases, *unrelated]
    _refresh_metrics(full)
    base = service.save(
        document_id=document_id,
        context=context,
        validated_document_result=full,
        provider_profile_id=PROVIDER_PROFILE_ID,
    )
    demand = _demand_result(
        full,
        labels=["SECURITY_PURCHASE"],
        annotations=purchases,
    )

    recovered = service.save_recovery(
        document_id=document_id,
        context=context,
        validated_document_result=demand,
        provider_profile_id=PROVIDER_PROFILE_ID,
        base_annotations_artifact_id=base.artifact_id,
        demand_request_id="g554-five-purchases",
    )
    gate4 = (
        Gate4FinancialCaseRuntimeFactory(store=store, read_enabled=True)
        .create()
        .rebuild_case(context=context)
    )
    labels = [fact["financial_type"] for fact in gate4.facts]
    gate5 = (
        Gate5DeterministicSourceFactConsumptionRuntimeFactory(
            store=store, read_enabled=True
        )
        .create()
        .assess(
            methodology_ref={
                "schema_version": GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION,
                "methodology_id": GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_ID,
                "methodology_version": (
                    GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_VERSION
                ),
            },
            context=context,
        )
    )

    assert len(gate4.facts) == 21
    assert labels.count("SECURITY_PURCHASE") == 5
    assert labels.count("COMMISSION") == 8
    assert labels.count("TRANSACTION_CHARGE") == 8
    assert gate5["facts_total"] == 21
    assert gate5["security_fact_counts"]["total"] == 5
    assert len(gate5["assertions"]["commissions"]["detail"]) == 16
    assert gate5["terminals"] == ["SOURCE_FACT_ASSERTIONS_PRESERVED"]
    assert recovered.receipt["unchanged_recovered_total"] == 5
    assert recovered.receipt["preserved_unrelated_total"] == 16
    assert recovered.receipt["deleted_total"] == 0


def test_conflicting_recovery_fails_closed_without_persistence(
    tmp_path: Path,
) -> None:
    store, context, document_id, _canonical = _setup(tmp_path)
    service = Gate3FinancialAnnotationsPersistenceFactory(
        store=store, read_enabled=True
    ).create()
    full = _complete_result(store, context, document_id)
    targets = _targets(store, context, document_id)
    existing = _annotation("SECURITY_PURCHASE", targets[2])
    existing["roles"][3] = {
        "role": "amount",
        "status": "bound",
        "target": copy.deepcopy(targets[2]),
        "exact_text": "12.00",
    }
    full["merged_output"]["annotations"] = [existing]
    base = service.save(
        document_id=document_id,
        context=context,
        validated_document_result=full,
        provider_profile_id=PROVIDER_PROFILE_ID,
    )
    conflicting = copy.deepcopy(existing)
    conflicting["roles"][3]["target"] = copy.deepcopy(targets[3])
    conflicting["roles"][3]["exact_text"] = "7.00"
    demand = _demand_result(
        full,
        labels=["SECURITY_PURCHASE"],
        annotations=[conflicting],
    )
    before = len(store.list_by_run(context.normalization_run_id))

    with pytest.raises(Gate3FinancialAnnotationsPersistenceError) as failure:
        service.save_recovery(
            document_id=document_id,
            context=context,
            validated_document_result=demand,
            provider_profile_id=PROVIDER_PROFILE_ID,
            base_annotations_artifact_id=base.artifact_id,
            demand_request_id="demand-conflict",
        )
    assert failure.value.code == "gate3_annotations_recovery_conflict"
    assert len(store.list_by_run(context.normalization_run_id)) == before


def test_recovery_rejects_stale_base_and_source_version_change(
    tmp_path: Path,
) -> None:
    store, context, document_id, _canonical = _setup(tmp_path)
    service = Gate3FinancialAnnotationsPersistenceFactory(
        store=store, read_enabled=True
    ).create()
    full = _complete_result(store, context, document_id)
    base = service.save(
        document_id=document_id,
        context=context,
        validated_document_result=full,
        provider_profile_id=PROVIDER_PROFILE_ID,
    )
    demand = _demand_result(
        full,
        labels=["SECURITY_PURCHASE"],
        annotations=[],
    )
    first = service.save_recovery(
        document_id=document_id,
        context=context,
        validated_document_result=demand,
        provider_profile_id=PROVIDER_PROFILE_ID,
        base_annotations_artifact_id=base.artifact_id,
        demand_request_id="demand-first",
    )
    before = len(store.list_by_run(context.normalization_run_id))

    with pytest.raises(Gate3FinancialAnnotationsPersistenceError) as stale:
        service.save_recovery(
            document_id=document_id,
            context=context,
            validated_document_result=demand,
            provider_profile_id=PROVIDER_PROFILE_ID,
            base_annotations_artifact_id=base.artifact_id,
            demand_request_id="demand-stale",
        )
    assert stale.value.code == "gate3_annotations_recovery_base_stale"

    new_source = copy.deepcopy(demand)
    new_source["merged_output"] = copy.deepcopy(full["merged_output"])
    _refresh_metrics(new_source)
    new_source["merged_output"]["canonical_binding"]["canonical_version_id"] = (
        "different-source-version"
    )
    with pytest.raises(Gate3FinancialAnnotationsPersistenceError) as changed:
        service.save_recovery(
            document_id=document_id,
            context=context,
            validated_document_result=new_source,
            provider_profile_id=PROVIDER_PROFILE_ID,
            base_annotations_artifact_id=first.record.artifact_id,
            demand_request_id="demand-new-source",
        )
    assert changed.value.code == "gate3_annotations_canonical_binding_mismatch"
    assert len(store.list_by_run(context.normalization_run_id)) == before


def test_historical_v1_sidecar_remains_readable(tmp_path: Path) -> None:
    store, context, document_id, _canonical = _setup(tmp_path)
    service = Gate3FinancialAnnotationsPersistenceFactory(
        store=store, read_enabled=True
    ).create()
    current = service.save(
        document_id=document_id,
        context=context,
        validated_document_result=_complete_result(store, context, document_id),
        provider_profile_id=PROVIDER_PROFILE_ID,
    )
    current_payload = service.read(
        artifact_id=current.artifact_id,
        context=context,
    )
    historical_payload = {
        key: copy.deepcopy(value)
        for key, value in current_payload.items()
        if key not in {"role_pack_identity", "role_instruction_identity"}
    }
    historical_payload["schema_version"] = (
        GATE3_HISTORICAL_FINANCIAL_ANNOTATIONS_ARTIFACT_TYPE
    )
    historical_payload["annotations"] = [
        {
            "target": copy.deepcopy(annotation["target"]),
            "financial_label": annotation["financial_label"],
        }
        for annotation in current_payload["annotations"]
    ]
    historical = copy.deepcopy(current)
    historical.artifact_id = "historical-financial-annotations-v1"
    historical.artifact_type = GATE3_HISTORICAL_FINANCIAL_ANNOTATIONS_ARTIFACT_TYPE
    historical.payload = historical_payload
    historical.safe_metadata = copy.deepcopy(current.safe_metadata)
    stored = store.put_record(historical)

    assert service.read(artifact_id=stored.artifact_id, context=context) == (
        historical_payload
    )


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        (
            lambda value: value.update(document_status="incomplete"),
            "gate3_annotations_document_result_incomplete",
        ),
        (
            lambda value: value["merged_output"]["canonical_binding"].update(
                canonical_version_id="wrong-version"
            ),
            "gate3_annotations_canonical_binding_mismatch",
        ),
        (
            lambda value: value["merged_output"]["dictionary_identity"].update(
                dictionary_id="second-dictionary"
            ),
            "gate3_annotations_dictionary_identity_mismatch",
        ),
        (
            lambda value: value["merged_output"]["role_pack_identity"].update(
                role_pack_id="second-role-pack"
            ),
            "gate3_annotations_role_pack_identity_mismatch",
        ),
        (
            lambda value: value["merged_output"]["instruction_identity"].update(
                semantic_version="9.9.9"
            ),
            "gate3_annotations_payload_contract_invalid",
        ),
        (
            lambda value: value["merged_output"]["model_identity"].update(
                model_id="unapproved-model"
            ),
            "gate3_annotations_model_identity_mismatch",
        ),
        (
            lambda value: value["merged_output"]["annotations"][0].update(
                target={"kind": "node", "node_id": "missing-node"}
            ),
            "gate3_annotations_target_unknown",
        ),
        (
            lambda value: value["merged_output"]["annotations"][0]["roles"][1].update(
                target={"kind": "node", "node_id": "missing-node"}
            ),
            "gate3_annotations_role_target_unknown",
        ),
        (
            lambda value: value["merged_output"]["annotations"][0]["roles"][1].update(
                exact_text="12,00"
            ),
            "gate3_role_exact_text_not_literal_substring",
        ),
        (
            lambda value: value["merged_output"]["annotations"][0]["roles"].pop(),
            "gate3_annotations_role_cardinality_invalid",
        ),
    ],
)
def test_incomplete_or_misbound_result_fails_closed(
    tmp_path: Path, mutation, expected_code: str
) -> None:
    store, context, document_id, _canonical = _setup(tmp_path)
    result = _complete_result(store, context, document_id)
    mutation(result)
    service = Gate3FinancialAnnotationsPersistenceFactory(
        store=store, read_enabled=True
    ).create()

    with pytest.raises(Gate3FinancialAnnotationsPersistenceError) as failure:
        service.save(
            document_id=document_id,
            context=context,
            validated_document_result=result,
            provider_profile_id=PROVIDER_PROFILE_ID,
        )
    assert failure.value.code == expected_code


def test_existing_case_purge_removes_sidecar_payload(tmp_path: Path) -> None:
    store, context, document_id, _canonical = _setup(tmp_path)
    service = Gate3FinancialAnnotationsPersistenceFactory(
        store=store, read_enabled=True
    ).create()
    stored = service.save(
        document_id=document_id,
        context=context,
        validated_document_result=_complete_result(store, context, document_id),
        provider_profile_id=PROVIDER_PROFILE_ID,
    )

    purge = store.purge_case(context)
    assert stored.artifact_id in purge.artifact_ids
    with pytest.raises(ArtifactStoreError) as failure:
        service.read(artifact_id=stored.artifact_id, context=context)
    assert failure.value.code == "artifact_purged"


def test_factory_and_no_second_store_guards() -> None:
    assert "Gate3FinancialAnnotationsPersistenceFactory.create" in FACTORY_REQUIRED
    assert "ArtifactStore" in FACTORY_REQUIRED
    assert "incomplete" in FORBIDDEN
    source = (
        Path(__file__).resolve().parents[1]
        / "broker_reports_gate1"
        / "gate3_financial_annotations_persistence.py"
    ).read_text(encoding="utf-8")
    assert "import sqlite" not in source
    assert "ArtifactStoreFactory(" not in source
    assert "ArtifactResolver" in source


def _setup(tmp_path: Path, *, with_table: bool = False):
    store = ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=tmp_path / "artifacts.sqlite3",
            payload_root=tmp_path / "payloads",
        )
    ).create()
    context = ArtifactAccessContext(
        user_id="g3-persistence-user",
        normalization_run_id="g3-persistence-run",
        case_id="g3-persistence-case",
        workspace_model_id="g3-persistence-workspace",
        allow_private=True,
    )
    document_id = "g3-persistence-document"
    retention = build_retention_policy(mode="api_smoke")
    source_ref = "g3-persistence-source"
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
            source_file_ref={"openwebui_file_id": "synthetic-file"},
            visibility="private_case",
            storage_backend="project_artifact_payload",
            retention_policy=retention,
            access_policy={"requires_user_id": True},
            validation_status="validated",
            lifecycle_status=lifecycle_for_visibility(
                visibility="private_case", validation_status="validated"
            ),
            payload={"synthetic": True},
        )
    )
    normalizer = CanonicalNormalizerFactory(
        CanonicalNormalizerConfig(normalizer_version="g3-persistence-test-v1")
    ).create()
    text_blocks = [
        {
            "kind": "text",
            "text": "Broker fee 12.00",
            "source_location": {"block_index": 1},
        },
        {
            "kind": "text",
            "text": "Tax withheld 2.00",
            "source_location": {"block_index": 2},
        },
        {
            "kind": "text",
            "text": "Purchase AAPL 3 12.00 USD",
            "source_location": {"block_index": 3},
        },
        {
            "kind": "text",
            "text": "Purchase MSFT 1 7.00 USD",
            "source_location": {"block_index": 4},
        },
        *[
            {
                "kind": "text",
                "text": f"Evidence item {index} 1.00",
                "source_location": {"block_index": index},
            }
            for index in range(5, 22)
        ],
    ]
    table_values = (
        ("Date", "Asset", "Quantity", "Amount", "Currency", "Unit price", "Type"),
        ("2025-01-01", "ASSET", "2", "20.00", "RUB", "10.00", "Purchase"),
        ("2025-01-01", "ASSET", "2", "20.00", "RUB", "10.00", "Purchase"),
        ("2025-01-02", "ASSET-B", "1", "30.00", "RUB", "30.00", "Purchase"),
        ("2025-01-03", "ASSET-C", "4", "40.00", "RUB", "10.00", "Purchase"),
        ("2025-01-04", "ASSET-D", "5", "50.00", "RUB", "10.00", "Purchase"),
    )
    artifact = normalizer.build(
        tenant_id=context.user_id,
        artifact_version=1,
        document={
            "container_format": "pdf" if with_table else "html_text",
            "sha256": hashlib.sha256(b"g3-persistence").hexdigest(),
            "declared_mime_type": "application/pdf" if with_table else "text/html",
        },
        source_artifact_ref=source_ref,
        source_payloads=(
            [
                {
                    "parser_completeness_status": "complete",
                    "parser_completeness_reason_codes": [],
                    "pdf_text_layer_projection": {
                        "page_inventory": [{"page_number": 1}],
                        "line_inventory": [],
                    },
                }
            ]
            if with_table
            else [{"canonical_projection": {"blocks": text_blocks}}]
        ),
        source_units=(
            [
                *[
                    {
                        "unit_ref": f"g3-persistence-text-{index}",
                        "source_location": {"page": 1, "line_start": index},
                        "text": block["text"],
                    }
                    for index, block in enumerate(text_blocks, 1)
                ],
                {
                    "unit_ref": "g3-persistence-table-unit",
                    "source_location": {"page": 1, "line_start": 30},
                    "text": "Synthetic purchase table",
                },
            ]
            if with_table
            else []
        ),
        table_projections=(
            [
                {
                    "projection_status": "ready",
                    "table_projection_id": "g3-persistence-table",
                    "source_unit_ref": "g3-persistence-table-unit",
                    "row_count": len(table_values),
                    "column_count": len(table_values[0]),
                    "cells": [
                        {
                            "row_ordinal": row,
                            "column_ordinal": column,
                            "normalized_private_value_path": f"v-{row}-{column}",
                        }
                        for row in range(1, len(table_values) + 1)
                        for column in range(1, len(table_values[0]) + 1)
                    ],
                    "private_values": [
                        {
                            "value_path_ref": f"v-{row}-{column}",
                            "normalized_value": value,
                        }
                        for row, values in enumerate(table_values, 1)
                        for column, value in enumerate(values, 1)
                    ],
                }
            ]
            if with_table
            else []
        ),
    )
    canonical = (
        CanonicalArtifactStoreFactory(
            store=store,
            config=CanonicalStorageConfig(capacity_check_enabled=False),
        )
        .create()
        .put_candidate(
            artifact=artifact,
            context=context,
            retention_policy=retention,
            compare_receipt=None,
        )
    )
    CanonicalReaderFactory(store=store, read_enabled=True).create().activate(
        canonical_version_id=canonical.canonical_version_id,
        expected_previous_version_id=None,
        context=context,
        actor="g3-persistence-test",
        reason="G3.5 persistence test",
    )
    return store, context, document_id, canonical


def _complete_result(store, context, document_id: str) -> dict:
    chunk_set = Gate3StructuralChunkFactory(store=store, read_enabled=True).create(
        document_id=document_id, context=context
    )
    ordinals = [int(chunk["ordinal"]) for chunk in chunk_set["chunks"]]
    target = copy.deepcopy(
        chunk_set["chunks"][0]["target_mappings"][0]["canonical_target"]
    )
    payload = {
        "schema_version": "broker_reports_financial_annotations_v2",
        "canonical_binding": copy.deepcopy(chunk_set["canonical_binding"]),
        "dictionary_identity": {
            "dictionary_id": "broker-reports-financial-labels",
            "semantic_version": GATE3_DICTIONARY_CURRENT_VERSION,
        },
        "role_pack_identity": {
            "role_pack_id": "broker-reports-financial-roles",
            "semantic_version": GATE3_ROLE_PACK_CURRENT_VERSION,
        },
        "instruction_identity": {
            "instruction_id": "broker-reports-bounded-semantic-labeling",
            "semantic_version": "1.0.2",
        },
        "role_instruction_identity": {
            "instruction_id": "broker-reports-source-bound-role-labeling",
            "semantic_version": GATE3_ROLE_LABELING_INSTRUCTION_VERSION,
        },
        "model_identity": {"model_id": MODEL_ID},
        "annotations": [
            {
                "target": target,
                "financial_label": "TRANSACTION_CHARGE",
                "roles": [
                    {"role": "date", "status": "missing"},
                    {
                        "role": "amount",
                        "status": "bound",
                        "target": copy.deepcopy(target),
                        "exact_text": "12.00",
                    },
                    {"role": "currency", "status": "missing"},
                    {"role": "asset", "status": "missing"},
                ],
            }
        ],
        "validation_status": "validated",
    }
    return {
        "schema_version": GATE3_CHUNK_BATCH_LABELING_RESULT_SCHEMA_VERSION,
        "semantic_scope": {
            "publication_mode": "FULL",
            "document_id": document_id,
            "requested_financial_labels": [],
            "requested_roles": [],
            "selected_chunk_ordinals": ordinals,
        },
        "selected_chunk_ordinals": ordinals,
        "selection_mode": "full_document",
        "document_status": "complete",
        "metrics": {
            "chunks_total": len(ordinals),
            "chunks_validated": len(ordinals),
            "chunks_rejected": 0,
            "chunks_provider_failed": 0,
            "chunks_with_local_failures": 0,
            "fully_unusable_chunks": 0,
            "annotations_validated": 1,
            "facts_role_complete": 0,
            "facts_role_incomplete": 1,
            "facts_incomplete_due_to_role_rejection": 0,
            "facts_rejected": 0,
            "role_bindings_rejected": 0,
            "source_fact_completeness_status": "incomplete",
        },
        "merged_output": payload,
    }


def _targets(store, context, document_id: str) -> list[dict]:
    chunk_set = Gate3StructuralChunkFactory(store=store, read_enabled=True).create(
        document_id=document_id, context=context
    )
    return [
        copy.deepcopy(mapping["canonical_target"])
        for chunk in chunk_set["chunks"]
        for mapping in chunk["target_mappings"]
    ]


def _table_targets(
    store, context, document_id: str, *, row: int
) -> tuple[dict, list[dict]]:
    targets = _targets(store, context, document_id)
    row_targets = [
        target
        for target in targets
        if target.get("kind") == "table_row" and target.get("row") == row
    ]
    cell_targets = sorted(
        (
            target
            for target in targets
            if target.get("kind") == "table_cell" and target.get("row") == row
        ),
        key=lambda target: target["column"],
    )
    assert len(row_targets) == 1
    assert len(cell_targets) == 7
    return copy.deepcopy(row_targets[0]), copy.deepcopy(cell_targets)


def _annotation(label: str, target: dict) -> dict:
    role_orders = {
        "SECURITY_PURCHASE": [
            "date",
            "asset",
            "quantity",
            "amount",
            "currency",
            "unit_price",
        ],
        "TRANSACTION_CHARGE": ["date", "amount", "currency", "asset"],
        "COMMISSION": ["amount", "currency", "date", "asset"],
        "TAX_WITHHELD": ["date", "amount", "currency", "asset"],
    }
    return {
        "target": copy.deepcopy(target),
        "financial_label": label,
        "roles": [{"role": role, "status": "missing"} for role in role_orders[label]],
    }


def _bound_purchase(
    target: dict,
    cells: list[dict],
    *,
    amount_column: int = 4,
    currency_column: int = 5,
) -> dict:
    columns = {
        "date": 1,
        "asset": 2,
        "quantity": 3,
        "amount": amount_column,
        "currency": currency_column,
        "unit_price": 6,
    }
    return {
        "target": copy.deepcopy(target),
        "financial_label": "SECURITY_PURCHASE",
        "roles": [
            {
                "role": role,
                "status": "bound",
                "target": copy.deepcopy(cells[column - 1]),
            }
            for role, column in columns.items()
        ],
    }


def _demand_result(
    full: dict,
    *,
    labels: list[str],
    annotations: list[dict] | None = None,
) -> dict:
    result = copy.deepcopy(full)
    result["semantic_scope"]["publication_mode"] = "DEMAND_SCOPED"
    result["semantic_scope"]["requested_financial_labels"] = labels
    roles_by_label = {
        "SECURITY_PURCHASE": {
            "date",
            "asset",
            "quantity",
            "amount",
            "currency",
            "unit_price",
        },
        "TRANSACTION_CHARGE": {"date", "amount", "currency", "asset"},
    }
    result["semantic_scope"]["requested_roles"] = sorted(
        {role for label in labels for role in roles_by_label[label]}
    )
    if annotations is not None:
        result["merged_output"] = (
            None
            if not annotations
            else {
                **copy.deepcopy(full["merged_output"]),
                "annotations": copy.deepcopy(annotations),
            }
        )
        _refresh_metrics(result)
    return result


def _refresh_metrics(result: dict) -> None:
    annotations = list((result.get("merged_output") or {}).get("annotations") or [])
    role_pack = Gate3FinancialRolePackFactory.create().load_published(
        GATE3_ROLE_PACK_CURRENT_VERSION
    )
    required_by_label = {
        profile["financial_label"]: set(profile["required_roles"])
        for profile in role_pack["profiles"]
    }
    incomplete = sum(
        any(
            role["role"] in required_by_label[annotation["financial_label"]]
            and role["status"] == "missing"
            for role in annotation["roles"]
        )
        for annotation in annotations
    )
    result["metrics"].update(
        {
            "annotations_validated": len(annotations),
            "facts_role_complete": len(annotations) - incomplete,
            "facts_role_incomplete": incomplete,
            "facts_incomplete_due_to_role_rejection": 0,
            "facts_rejected": 0,
            "role_bindings_rejected": 0,
            "source_fact_completeness_status": (
                "incomplete" if incomplete else "complete"
            ),
        }
    )
