from __future__ import annotations

import copy
import json
import sys
from collections import Counter
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from broker_reports_gate1.gate2_deterministic_financial_scopes import (  # noqa: E402
    Gate2DeterministicFinancialScopeFromGate1V2Factory,
)
from broker_reports_gate1.gate2_financial_evidence_materialization_contracts import (  # noqa: E402,E501
    FinancialEvidenceAuthoritativeSourceValue,
    FinancialEvidenceSourceLineage,
    Gate2FinancialEvidenceSourcePackage,
    sha256_json,
)
from broker_reports_gate1.gate2_financial_evidence_registry import (  # noqa: E402
    Gate2FinancialEvidenceRegistryFactory,
    Gate2FinancialEvidenceRegistrySnapshot,
)
from broker_reports_gate1.gate2_financial_evidence_source_package import (  # noqa: E402,E501
    Gate2FinancialEvidenceSourcePackageFactory,
)
from broker_reports_gate1.gate2_financial_semantic_v6_bundle import (  # noqa: E402,E501
    EVIDENCE_BUNDLE_ID_PREFIX,
    EVIDENCE_BUNDLE_POLICY_VERSION,
    EVIDENCE_BUNDLE_SCHEMA_VERSION,
    FinancialEvidenceBundleAssociation,
    FinancialEvidenceBundleSourceValue,
    Gate2FinancialEvidenceBundle,
    Gate2FinancialEvidenceBundleFactory,
)
from broker_reports_gate1.gate2_financial_semantic_v6_candidate_compiler import (  # noqa: E402,E501
    Gate2FinancialCandidateCompilerFactory,
)
from broker_reports_gate1.gate2_financial_semantic_v6_packet import (  # noqa: E402,E501
    Gate2FinancialSemanticV6PacketError,
    Gate2FinancialSemanticV6PacketFactory,
    validate_financial_semantic_context_v2_material,
)
from broker_reports_gate1.gate2_financial_semantic_v5_projection import (  # noqa: E402,E501
    Gate2FinancialSemanticV5ProjectionFactory,
)
from broker_reports_gate1.gate2_successor_local_proof import (  # noqa: E402
    _fixture_package,
)


BASE_MANIFEST_PATH = (
    ROOT / "benchmarks" / "gate2_financial_successor_v2" / "manifest.json"
)
BASE_CASE_ID = "syn_successor_v2_unique_cash"
TEXT_SEGMENT_REF = "segment:context-v2:cash"


@pytest.fixture(scope="module")
def base_authorities() -> tuple[
    Gate2FinancialEvidenceRegistrySnapshot,
    dict[str, Any],
    Gate2FinancialEvidenceSourcePackage,
]:
    manifest = json.loads(BASE_MANIFEST_PATH.read_text(encoding="utf-8"))
    case = next(
        item for item in manifest["cases"] if item["case_id"] == BASE_CASE_ID
    )
    gate1_payload = _fixture_package(copy.deepcopy(case)).payload
    registry = Gate2FinancialEvidenceRegistryFactory().create()
    scope = Gate2DeterministicFinancialScopeFromGate1V2Factory(
        registry=registry
    ).create(gate1_packages=(gate1_payload,)).scopes[0]
    return registry, gate1_payload, scope.source_package


def _reseal_source_package(
    source_package: Gate2FinancialEvidenceSourcePackage,
    source_values: tuple[FinancialEvidenceAuthoritativeSourceValue, ...],
) -> Gate2FinancialEvidenceSourcePackage:
    return Gate2FinancialEvidenceSourcePackageFactory(
        package_ref=source_package.package_ref,
        normalization_run_ref=source_package.normalization_run_ref,
        document_ref=source_package.document_ref,
        source_scope_ref=source_package.source_scope_ref,
        source_family_id=source_package.source_family_id,
        source_values=source_values,
        source_evidence_refs=source_package.source_evidence_refs,
        completeness=source_package.completeness,
        restriction_codes=source_package.restriction_codes,
        issue_refs=source_package.issue_refs,
    ).create()


def _create_packet(
    *,
    registry: Gate2FinancialEvidenceRegistrySnapshot,
    gate1_payload: dict[str, Any],
    source_package: Gate2FinancialEvidenceSourcePackage,
):
    bundle = Gate2FinancialEvidenceBundleFactory().create(
        source_package=source_package,
        gate1_packages=(gate1_payload,),
    )
    compilation = Gate2FinancialCandidateCompilerFactory(
        registry=registry
    ).create(
        evidence_bundle=bundle,
        source_package=source_package,
    )
    packet = Gate2FinancialSemanticV6PacketFactory(
        registry=registry
    ).create(
        evidence_bundle=bundle,
        source_package=source_package,
        compilation=compilation,
    )
    assert packet.context_v2_candidate.provider_calls_total == 0
    assert packet.context_v2_mapping_receipt.provider_calls_total == 0
    return packet, bundle, compilation


def _source_children(packet) -> list[dict[str, Any]]:
    return packet.context_v2_candidate.payload["source"]["document"][
        "children"
    ]


def _necessary_reference_targets(packet) -> list[dict[str, str]]:
    return packet.context_v2_mapping_receipt.local_mappings[
        "evidence_reference_targets"
    ]


def test_context_v2_preserves_table_to_row_hierarchy(
    base_authorities,
) -> None:
    registry, gate1_payload, source_package = base_authorities

    packet, _, _ = _create_packet(
        registry=registry,
        gate1_payload=gate1_payload,
        source_package=source_package,
    )

    children = _source_children(packet)
    assert [item["kind"] for item in children] == ["table"]
    assert [item["kind"] for item in children[0]["children"]] == ["row"]
    assert all(
        item == {
            "source_value_ref": item["source_value_ref"],
            "target_kind": "location",
            "target": "the only visible row",
        }
        for item in _necessary_reference_targets(packet)
    )


def test_context_v2_renders_direct_row_when_table_lineage_is_absent(
    base_authorities,
) -> None:
    registry, gate1_payload, source_package = base_authorities
    direct_row_package = _reseal_source_package(
        source_package,
        tuple(
            replace(
                value,
                lineage=replace(value.lineage, table_ref=None),
            )
            for value in source_package.source_values
        ),
    )

    packet, _, _ = _create_packet(
        registry=registry,
        gate1_payload=gate1_payload,
        source_package=direct_row_package,
    )

    children = _source_children(packet)
    assert [item["kind"] for item in children] == ["row"]
    assert len(children[0]["values"]) == 4
    assert {
        (item["target_kind"], item["target"])
        for item in _necessary_reference_targets(packet)
    } == {("location", "the only visible row")}


def test_context_v2_renders_gate1_text_segment_projection(
    base_authorities,
) -> None:
    registry, gate1_payload, source_package = base_authorities
    text_payload = copy.deepcopy(gate1_payload)
    cells = text_payload["source_unit"]["model_source_projection"]["rows"][0][
        "cells"
    ]
    text_payload["source_unit"]["model_source_projection"] = {
        "schema_version": "gate2_model_text_projection_v0",
        "segments": [
            {
                "source_value_ref": cell["source_value_ref"],
                "text_segment_ref": TEXT_SEGMENT_REF,
                "visible_label": cell["header_label"],
                "value": cell["value"],
            }
            for cell in cells
        ],
    }
    text_package = _reseal_source_package(
        source_package,
        tuple(
            replace(
                value,
                lineage=FinancialEvidenceSourceLineage(
                    document_ref=value.lineage.document_ref,
                    text_segment_ref=TEXT_SEGMENT_REF,
                ),
            )
            for value in source_package.source_values
        ),
    )

    packet, _, _ = _create_packet(
        registry=registry,
        gate1_payload=text_payload,
        source_package=text_package,
    )

    children = _source_children(packet)
    assert [item["kind"] for item in children] == ["text segment"]
    assert len(children[0]["values"]) == 4
    assert {
        (item["target_kind"], item["target"])
        for item in _necessary_reference_targets(packet)
    } == {("location", "the only visible text segment")}


def test_context_v2_uses_evidence_group_for_ambiguous_reference_target(
    base_authorities,
) -> None:
    registry, gate1_payload, source_package = base_authorities
    semantic_index = 0
    split_values: list[FinancialEvidenceAuthoritativeSourceValue] = []
    for value in source_package.source_values:
        if value.value_type == "source_reference":
            split_values.append(value)
            continue
        semantic_index += 1
        row_ref = (
            "row:context-v2:left"
            if semantic_index <= 2
            else "row:context-v2:right"
        )
        split_values.append(
            replace(
                value,
                lineage=replace(
                    value.lineage,
                    table_ref=None,
                    row_ref=row_ref,
                ),
            )
        )
    split_package = _reseal_source_package(
        source_package,
        tuple(split_values),
    )

    packet, bundle, _ = _create_packet(
        registry=registry,
        gate1_payload=gate1_payload,
        source_package=split_package,
    )

    assert {
        item.association_ref
        for item in bundle.source_values
        if item.value_type != "source_reference"
    } == {"row:syn_successor_v2_unique_cash:primary"}
    assert {
        item.lineage.row_ref
        for item in bundle.source_values
        if item.value_type != "source_reference"
    } == {"row:context-v2:left", "row:context-v2:right"}
    children = _source_children(packet)
    assert [item["kind"] for item in children] == [
        "row",
        "row",
        "evidence group",
    ]
    targets = _necessary_reference_targets(packet)
    assert len(targets) == 2
    assert {
        (item["target_kind"], item["target"]) for item in targets
    } == {("location", "the only visible evidence group")}
    evidence_group_index = next(
        index
        for index, item in enumerate(children)
        if item["kind"] == "evidence group"
    )
    evidence_group_kind_source = next(
        item
        for item in packet.context_v2_mapping_receipt.visible_field_sources
        if item["json_pointer"]
        == f"/source/document/children/{evidence_group_index}/kind"
    )
    first_reference_index = next(
        index
        for index, item in enumerate(bundle.source_values)
        if item.source_value_ref == targets[0]["source_value_ref"]
    )
    assert evidence_group_kind_source["authority_kind"] == "evidence_bundle"
    assert evidence_group_kind_source["authority_pointer"] == (
        f"/source_values/{first_reference_index}"
    )


def test_context_v2_preserves_interleaved_row_literal_occurrences(
    base_authorities,
) -> None:
    registry, gate1_payload, source_package = base_authorities
    semantic_index = 0
    interleaved_values: list[FinancialEvidenceAuthoritativeSourceValue] = []
    for value in source_package.source_values:
        if value.value_type == "source_reference":
            interleaved_values.append(value)
            continue
        semantic_index += 1
        interleaved_values.append(
            replace(
                value,
                lineage=replace(
                    value.lineage,
                    table_ref=None,
                    row_ref=(
                        "row:context-v2:left"
                        if semantic_index % 2
                        else "row:context-v2:right"
                    ),
                ),
            )
        )
    interleaved_package = _reseal_source_package(
        source_package,
        tuple(interleaved_values),
    )

    packet, bundle, _ = _create_packet(
        registry=registry,
        gate1_payload=gate1_payload,
        source_package=interleaved_package,
    )

    expected_literals = [
        item.literal_value
        for item in bundle.source_values
        if item.value_type != "source_reference"
    ]
    rows = [
        item for item in _source_children(packet) if item["kind"] == "row"
    ]
    rendered_literals = [
        value["literal"] for row in rows for value in row["values"]
    ]
    assert len(rows) == 2
    assert [len(row["values"]) for row in rows] == [2, 2]
    assert rendered_literals != expected_literals
    assert Counter(rendered_literals) == Counter(expected_literals)

    literal_sources = [
        item
        for item in packet.context_v2_mapping_receipt.visible_field_sources
        if item["json_pointer"].endswith("/literal")
    ]
    assert {
        item["authority_pointer"] for item in literal_sources
    } == {
        f"/source_values/{index}/literal_value"
        for index, item in enumerate(bundle.source_values)
        if item.value_type != "source_reference"
    }


def test_context_v2_rejects_existing_but_wrong_authority_pointer(
    base_authorities,
) -> None:
    registry, gate1_payload, source_package = base_authorities
    packet, bundle, compilation = _create_packet(
        registry=registry,
        gate1_payload=gate1_payload,
        source_package=source_package,
    )
    field_sources = [
        copy.deepcopy(item)
        for item in packet.context_v2_mapping_receipt.visible_field_sources
    ]
    title_source = next(
        item
        for item in field_sources
        if item["json_pointer"] == "/unclassified_reasons/0/title"
    )
    title_source["authority_pointer"] = "/reasons/1/human_title"
    tampered_receipt = replace(
        packet.context_v2_mapping_receipt,
        visible_field_sources=tuple(field_sources),
    )
    receipt_material = tampered_receipt.to_private_dict()
    receipt_material.pop("integrity_hash")
    tampered_receipt = replace(
        tampered_receipt,
        integrity_hash=sha256_json(receipt_material),
    )
    projection = (
        Gate2FinancialSemanticV5ProjectionFactory()
        .create_context_v2_candidate(
            registry=registry,
            source_family_id=bundle.source_family_id,
        )
    )

    with pytest.raises(
        Gate2FinancialSemanticV6PacketError,
        match="financial_semantic_context_v2_receipt_material_invalid",
    ):
        validate_financial_semantic_context_v2_material(
            candidate=packet.context_v2_candidate,
            receipt=tampered_receipt,
            evidence_bundle=bundle,
            compilation=compilation,
            registry=registry,
            projection=projection,
            active_payload=packet.payload,
            active_packet_hash=packet.packet_hash,
        )


def test_context_v2_rejects_resealed_wrong_reference_target(
    base_authorities,
) -> None:
    registry, gate1_payload, source_package = base_authorities
    packet, bundle, compilation = _create_packet(
        registry=registry,
        gate1_payload=gate1_payload,
        source_package=source_package,
    )
    local_mappings = copy.deepcopy(
        packet.context_v2_mapping_receipt.local_mappings
    )
    reference_row = local_mappings["evidence_reference_targets"][0]
    assert reference_row["target"] == "the only visible row"
    reference_row["target"] = "the only visible table"
    tampered_receipt = replace(
        packet.context_v2_mapping_receipt,
        local_mappings=local_mappings,
    )
    receipt_material = tampered_receipt.to_private_dict()
    receipt_material.pop("integrity_hash")
    tampered_receipt = replace(
        tampered_receipt,
        integrity_hash=sha256_json(receipt_material),
    )
    projection = (
        Gate2FinancialSemanticV5ProjectionFactory()
        .create_context_v2_candidate(
            registry=registry,
            source_family_id=bundle.source_family_id,
        )
    )

    with pytest.raises(
        Gate2FinancialSemanticV6PacketError,
        match="financial_semantic_context_v2_receipt_material_invalid",
    ):
        validate_financial_semantic_context_v2_material(
            candidate=packet.context_v2_candidate,
            receipt=tampered_receipt,
            evidence_bundle=bundle,
            compilation=compilation,
            registry=registry,
            projection=projection,
            active_payload=packet.payload,
            active_packet_hash=packet.packet_hash,
        )


def test_context_v2_fails_closed_when_only_unbound_references_are_available(
    base_authorities,
) -> None:
    registry, gate1_payload, source_package = base_authorities
    reference_package = _reseal_source_package(
        source_package,
        tuple(
            value
            for value in source_package.source_values
            if value.value_type == "source_reference"
        ),
    )
    complete_bundle = Gate2FinancialEvidenceBundleFactory().create(
        source_package=source_package,
        gate1_packages=(gate1_payload,),
    )
    # The Bundle factory deliberately requires at least one Gate1-visible
    # value. This all-reference negative branch therefore uses the narrowest
    # integrity-sealed Bundle dataclass derived from canonical factory output.
    reference_bundle = _sealed_reference_only_bundle(
        source_package=reference_package,
        source_values=tuple(
            value
            for value in complete_bundle.source_values
            if value.value_type == "source_reference"
        ),
    )
    compilation = Gate2FinancialCandidateCompilerFactory(
        registry=registry
    ).create(
        evidence_bundle=reference_bundle,
        source_package=reference_package,
    )
    assert compilation.typed_options == ()

    with pytest.raises(
        Gate2FinancialSemanticV6PacketError,
        match="financial_semantic_context_v2_visible_hierarchy_empty",
    ):
        Gate2FinancialSemanticV6PacketFactory(
            registry=registry
        ).create(
            evidence_bundle=reference_bundle,
            source_package=reference_package,
            compilation=compilation,
        )


def _sealed_reference_only_bundle(
    *,
    source_package: Gate2FinancialEvidenceSourcePackage,
    source_values: tuple[FinancialEvidenceBundleSourceValue, ...],
) -> Gate2FinancialEvidenceBundle:
    retention_set = tuple(item.source_value_ref for item in source_values)
    grouped: dict[tuple[str, str], list[str]] = {}
    for value in source_values:
        grouped.setdefault(
            (value.association_kind, value.association_ref),
            [],
        ).append(value.source_value_ref)
    associations = tuple(
        FinancialEvidenceBundleAssociation(
            association_ref=association_ref,
            association_kind=association_kind,
            source_value_refs=tuple(sorted(refs)),
        )
        for (association_kind, association_ref), refs in sorted(
            grouped.items()
        )
    )
    provenance_refs = tuple(
        sorted(
            {
                *source_package.source_evidence_refs,
                *(
                    ref
                    for value in source_package.source_values
                    for ref in value.source_evidence_refs
                ),
            }
        )
    )
    identity_material = {
        "schema_version": EVIDENCE_BUNDLE_SCHEMA_VERSION,
        "policy_version": EVIDENCE_BUNDLE_POLICY_VERSION,
        "source_package_ref": source_package.package_ref,
        "source_package_integrity_hash": source_package.integrity_hash,
        "normalization_run_ref": source_package.normalization_run_ref,
        "document_ref": source_package.document_ref,
        "source_scope_ref": source_package.source_scope_ref,
        "source_family_id": source_package.source_family_id,
        "completeness": source_package.completeness,
        "restriction_codes": list(source_package.restriction_codes),
        "issue_refs": list(source_package.issue_refs),
        "source_values": [
            _bundle_source_value_payload(value) for value in source_values
        ],
        "source_associations": [
            {
                "association_ref": item.association_ref,
                "association_kind": item.association_kind,
                "source_value_refs": list(item.source_value_refs),
            }
            for item in associations
        ],
        "provenance_refs": list(provenance_refs),
        "retention_set": list(retention_set),
    }
    bundle_id = EVIDENCE_BUNDLE_ID_PREFIX + sha256_json(identity_material)[:32]
    return Gate2FinancialEvidenceBundle(
        schema_version=EVIDENCE_BUNDLE_SCHEMA_VERSION,
        policy_version=EVIDENCE_BUNDLE_POLICY_VERSION,
        bundle_id=bundle_id,
        source_package_ref=source_package.package_ref,
        source_package_integrity_hash=source_package.integrity_hash,
        normalization_run_ref=source_package.normalization_run_ref,
        document_ref=source_package.document_ref,
        source_scope_ref=source_package.source_scope_ref,
        source_family_id=source_package.source_family_id,
        completeness=source_package.completeness,
        restriction_codes=source_package.restriction_codes,
        issue_refs=source_package.issue_refs,
        source_values=source_values,
        source_associations=associations,
        provenance_refs=provenance_refs,
        retention_set=retention_set,
        integrity_hash=sha256_json(
            {
                **identity_material,
                "bundle_id": bundle_id,
            }
        ),
    )


def _bundle_source_value_payload(
    value: FinancialEvidenceBundleSourceValue,
) -> dict[str, Any]:
    return {
        "source_value_ref": value.source_value_ref,
        "source_ref": value.source_ref,
        "value_type": value.value_type,
        "literal_value": value.literal_value,
        "source_evidence_refs": list(value.source_evidence_refs),
        "lineage": asdict(value.lineage),
        "association_ref": value.association_ref,
        "association_kind": value.association_kind,
        "visible_context": {
            "column_meaning": value.column_meaning,
            "visible_label": value.visible_label,
            "row_role": value.row_role,
            "section_role": value.section_role,
        },
    }
