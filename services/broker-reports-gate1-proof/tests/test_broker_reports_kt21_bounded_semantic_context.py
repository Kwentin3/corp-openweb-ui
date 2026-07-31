from __future__ import annotations

import copy
import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest


SERVICE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_ROOT))

from broker_reports_gate1.gate2_bounded_semantic_context import (  # noqa: E402
    Gate2BoundedSemanticContextConfig,
    Gate2BoundedSemanticContextError,
    Gate2BoundedSemanticContextFactory,
    Gate2ContextSufficiencyGuard,
)
from broker_reports_gate1.gate2_financial_evidence_registry import (  # noqa: E402
    Gate2FinancialEvidenceRegistryFactory,
)
from broker_reports_gate1.gate2_financial_semantic_v6_evidence import (  # noqa: E402
    Gate2FinancialSemanticV6DecisionEvidenceFactory,
    replay_financial_semantic_v6_type_first_proof,
)
from broker_reports_gate1.gate2_same_source_type_first_proof import (  # noqa: E402
    Gate2SameSourceTypeFirstProof,
    Gate2SameSourceTypeFirstProofError,
)


CORPUS_PATH = (
    SERVICE_ROOT
    / "tests"
    / "fixtures"
    / "kt2_same_source_type_first_corpus.safe.json"
)
PACK_PATH = (
    SERVICE_ROOT
    / "semantic_packs"
    / "broker_reports_financial_semantic_pack.v1.json"
)
CONTEXT_MODULE_PATH = (
    SERVICE_ROOT
    / "broker_reports_gate1"
    / "gate2_bounded_semantic_context.py"
)
PRODUCT_ROUTE_PATH = (
    SERVICE_ROOT / "broker_reports_gate1" / "gate2_domain_runtime.py"
)
FUNCTION_PATHS = (
    SERVICE_ROOT / "openwebui_actions" / "broker_reports_gate1_pipe_bundled.py",
    SERVICE_ROOT
    / "openwebui_actions"
    / "broker_reports_gate2_source_fact_pipe_bundled.py",
    SERVICE_ROOT
    / "openwebui_actions"
    / "broker_reports_gate2_domain_source_fact_pipe_bundled.py",
)
PROOF_BUILDER_PATH = (
    SERVICE_ROOT / "scripts" / "build_kt21_bounded_semantic_context_proof.py"
)
PROOF_RECEIPT_PATH = (
    SERVICE_ROOT
    / "tests"
    / "fixtures"
    / "kt21_bounded_semantic_context_proof_receipt.safe.json"
)


def _package(
    *,
    index: int,
    document_ref: str | None = None,
    table_ref: str | None = None,
    row_ordinal: int = 1,
) -> dict:
    unit_id = f"kt21_unit_{index}"
    row_ref = f"row:kt21:{index}"
    document = document_ref or f"document:kt21:{index}"
    table = table_ref or f"table:kt21:{index}"
    values = (
        "Synthetic printed total",
        f"{200 + index}.00",
        "2026-06-30",
        "USD",
    )
    headers = ("Line item", "Amount", "As of date", "Currency")
    roles = ("source_label", "amount", "as_of_date", "currency")
    cells = []
    value_index = []
    value_refs = []
    for ordinal, (header, value) in enumerate(
        zip(headers, values, strict=True),
        start=1,
    ):
        cell_ref = f"{unit_id}:cell:{ordinal}"
        value_ref = f"{unit_id}:value:{ordinal}"
        value_refs.append(value_ref)
        cells.append(
            {
                "column_ordinal": ordinal,
                "header_label": header,
                "cell_ref": cell_ref,
                "source_value_ref": value_ref,
                "value": value,
            }
        )
        value_index.append(
            {
                "source_value_ref": value_ref,
                "row_ref": row_ref,
                "cell_ref": cell_ref,
                "value_path": {
                    "kind": "table_cell",
                    "row_index": 0,
                    "column_index": ordinal - 1,
                },
                "value_checksum_ref": f"checksum:{value_ref}",
            }
        )
    header_ref = f"{unit_id}:header"
    selected = [row_ref, header_ref]
    return {
        "schema_version": "broker_reports_source_fact_package_v0",
        "package_id": f"kt21_package_{index}",
        "extraction_run_id": "extraction:kt21:synthetic",
        "normalization_run_id": "normalization:kt21:synthetic",
        "case_id": "case:kt21:synthetic",
        "document_ref": document,
        "source_bucket_roles": ["primary_source_refs"],
        "document_context": {
            "usage_modes": ["source_fact"],
            "passport": {"document_kind_candidate": "broker_report"},
            "financial_interpretation_allowed": True,
            "document_role": "primary_statement",
            "document_title": "Synthetic quarterly statement",
            "issuer_role": "synthetic_issuer",
            "reporting_period": "2026-Q2",
            "statement_scope": "synthetic_statement_scope",
            "account_type": "synthetic_account",
            "language": "en",
        },
        "source_unit": {
            "unit_id": unit_id,
            "unit_kind": "table_row_window",
            "source_input_mode": "normalized_table_projection",
            "private_slice_artifact_ref": f"artifact:{unit_id}",
            "slice_ref": f"slice:{unit_id}",
            "document_ref": document,
            "source_checksum_ref": f"checksum:{unit_id}",
            "slice_payload_checksum_ref": f"payload-checksum:{unit_id}",
            "parser_ref": "parser:kt21:synthetic",
            "table_ref": table,
            "table_title": "Synthetic statement metrics",
            "safe_section_labels": ["Statement", "Totals"],
            "group_labels": ["Reported metrics"],
            "related_notes": ["Synthetic note"],
            "row_range_ref": f"row-range:{unit_id}",
            "coverage_ref": f"coverage:{unit_id}",
            "normalized_header_descriptors": [
                {"column_ordinal": ordinal, "normalized_label": role}
                for ordinal, role in enumerate(roles, start=1)
            ],
            "row_refs": [row_ref],
            "row_provenance": [
                {
                    "row_ref": row_ref,
                    "row_ordinal": row_ordinal,
                    "row_kind": "fact_candidate",
                }
            ],
            "cell_refs": [item["cell_ref"] for item in cells],
            "cell_provenance": [
                {
                    "row_ordinal": row_ordinal,
                    "column_ordinal": ordinal,
                    "row_ref": row_ref,
                    "cell_ref": item["cell_ref"],
                    "source_value_ref": item["source_value_ref"],
                }
                for ordinal, item in enumerate(cells, start=1)
            ],
            "cell_value_refs": value_refs,
            "source_value_refs": value_refs,
            "source_value_index": value_index,
            "private_values": [],
            "text_segment_refs": [],
            "section_refs": [],
            "page_refs": [],
            "character_span_refs": [],
            "segment_provenance": [],
            "normalized_source_projection": {"cells": [list(values)]},
            "model_source_projection": {
                "schema_version": "gate2_model_table_projection_v0",
                "rows": [
                    {
                        "row_ref": row_ref,
                        "row_kind": "fact_candidate",
                        "cells": cells,
                    }
                ],
            },
            "table_quality": {
                "header_confidence": "high",
                "reconstruction_quality": "high",
            },
            "continuation": {},
        },
        "allowed_evidence_refs": selected,
        "allowed_source_value_refs": value_refs,
        "issue_context": [],
        "allowed_issue_refs": [],
        "forbidden_assumptions": [],
        "coverage_expectation": {
            "coverage_ref": f"coverage:{unit_id}",
            "selected_source_refs": selected,
            "ignorable_header_refs": [header_ref],
            "ignorable_blank_refs": [],
            "layout_candidate_refs": [],
            "mandatory_no_fact_results": [
                {"source_ref": header_ref, "reason_code": "header_row"}
            ],
        },
        "privacy_policy": {
            "knowledge_rag_used": False,
            "vectorization_performed": False,
        },
        "created_at": "2026-07-31T00:00:00Z",
    }


def _full_authorities() -> tuple:
    packages = tuple(_package(index=index) for index in range(1, 4))
    registry = Gate2FinancialEvidenceRegistryFactory().create()
    proof = Gate2SameSourceTypeFirstProof(registry=registry)
    prepared = proof.prepare(gate2_packages=packages)
    response = proof.response(
        prepared=prepared,
        plausible_types_by_unit={
            unit.source_unit_key: ("t02",) for unit in prepared.units
        },
    )
    execution = proof.execute(
        prepared=prepared,
        simulated_response=response,
    )
    return registry, proof, packages, prepared, response, execution


def test_three_real_source_units_are_now_honestly_insufficient() -> None:
    corpus = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    packages = tuple(
        corpus["packages"][index]
        for index in corpus["proof_bounded_source_unit_package_indexes"]
    )
    proof = Gate2SameSourceTypeFirstProof(
        registry=Gate2FinancialEvidenceRegistryFactory().create()
    )
    prepared = proof.prepare(gate2_packages=packages)
    response = proof.response(
        prepared=prepared,
        plausible_types_by_unit={
            unit.source_unit_key: ("t02",) for unit in prepared.units
        },
    )
    execution = proof.execute(prepared=prepared, simulated_response=response)
    assert len(prepared.units) == 3
    assert all(
        unit.bounded_context.payload["table_context"]["raw_headers"]
        == ["unknown"]
        for unit in prepared.units
    )
    assert all(
        result.code_reason == "INSUFFICIENT_SEMANTIC_CONTEXT"
        and result.disposition == "unclassified_financial_input"
        for result in execution.units
    )
    assert execution.accounting["typed"] == 0
    assert execution.accounting["unclassified"] == 3


def test_kt21_trace_and_receipt_are_exact_managed_outputs() -> None:
    completed = subprocess.run(
        [sys.executable, str(PROOF_BUILDER_PATH), "--check"],
        cwd=SERVICE_ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout) == {
        "ablation_cases_total": 6,
        "missing_required_context_typed_total": 0,
        "mode": "check",
        "provider_calls_total": 0,
        "status": "passed",
        "values_only_typed_total": 0,
    }
    receipt = json.loads(PROOF_RECEIPT_PATH.read_text(encoding="utf-8"))
    assert receipt["real_source_units_total"] == 3
    assert receipt["normalized_roles_only_typed_total"] == 0
    assert receipt["sufficient_context_typed_total"] == 3
    assert receipt["insufficient_context_unclassified_total"] == 3
    assert receipt["status"] == "passed"


def test_type_context_requirements_are_projected_from_the_one_pack() -> None:
    _registry, _proof, _packages, prepared, _response, _execution = (
        _full_authorities()
    )
    pack = json.loads(PACK_PATH.read_text(encoding="utf-8"))
    cards = prepared.candidate.payload["type_cards"]
    by_title = {item["title"]: item for item in pack["full_compact_snapshot"]}
    for card in cards:
        declaration = by_title[card["display_name"]]
        assert card["context_disqualifiers"] == declaration[
            "ambiguity_guidance"
        ]
        assert "amount" in card["required_context_facets"]
        assert "statement_scope" in card["required_context_facets"]
    assert len(cards) == len(pack["full_compact_snapshot"]) == 2


def test_full_bounded_context_allows_singleton_only_through_existing_owners() -> None:
    registry, _proof, packages, prepared, response, execution = (
        _full_authorities()
    )
    assert execution.accounting["typed"] == 3
    assert all(
        result.code_reason == "UNIQUE_PLAUSIBLE_TYPE_AND_EXACT_OPTION"
        and result.context_sufficiency is not None
        and result.context_sufficiency.status == "SUFFICIENT"
        and result.disposition == "typed_input"
        for result in execution.units
    )
    evidence = Gate2FinancialSemanticV6DecisionEvidenceFactory(
        registry=registry
    ).create_type_first_proof(
        case_id="kt21-full-context",
        gate2_packages=packages,
        prepared=prepared,
        simulated_response=response,
        execution=execution,
    )
    replay = replay_financial_semantic_v6_type_first_proof(
        private_evidence=evidence.private_evidence,
        registry=registry,
    )
    assert replay.status == "exact"
    assert replay.replay_hash_match is True
    assert replay.provider_calls_total == 0


@pytest.mark.parametrize(
    ("variant", "expected_status"),
    (
        ("values_only", "INSUFFICIENT"),
        ("normalized_roles_only", "INSUFFICIENT"),
        ("raw_headers_added", "INSUFFICIENT"),
        ("section_and_table_added", "INSUFFICIENT"),
        ("local_structural_context_added", "INSUFFICIENT"),
        ("full_bounded_context", "SUFFICIENT"),
    ),
)
def test_context_ablation_is_monotonic_and_never_invents_a_type(
    variant: str,
    expected_status: str,
) -> None:
    _registry, _proof, _packages, prepared, _response, _execution = (
        _full_authorities()
    )
    unit = prepared.units[0]
    card = next(
        item
        for item in prepared.candidate.payload["type_cards"]
        if item["local_type_key"] == "t02"
    )
    option = next(
        item
        for item in prepared.mapping_receipt.option_restoration
        if item["source_unit_key"] == unit.source_unit_key
        and item["local_type_key"] == "t02"
    )
    ablated = Gate2BoundedSemanticContextFactory().ablate(
        context=unit.bounded_context,
        variant=variant,
    )
    first = Gate2ContextSufficiencyGuard().evaluate(
        context=ablated,
        type_card=card,
        exact_option=option,
        expected_source_package_integrity_hash=unit.source_package.integrity_hash,
    )
    second = Gate2ContextSufficiencyGuard().evaluate(
        context=ablated,
        type_card=card,
        exact_option=option,
        expected_source_package_integrity_hash=unit.source_package.integrity_hash,
    )
    assert first == second
    assert first.status == expected_status
    if variant in {"values_only", "normalized_roles_only"}:
        assert "printed_label_evidence_ref" in first.missing_facets


def test_document_and_header_layers_are_independently_required() -> None:
    _registry, _proof, _packages, prepared, _response, _execution = (
        _full_authorities()
    )
    context = prepared.units[0].bounded_context
    factory = Gate2BoundedSemanticContextFactory()
    normalized_only = factory.ablate(
        context=context,
        variant="normalized_roles_only",
    )
    headers_only = factory.ablate(
        context=context,
        variant="raw_headers_added",
    )
    assert normalized_only.payload["table_context"]["raw_headers"] == []
    assert "printed_label_evidence_ref" not in normalized_only.present_facets
    assert headers_only.payload["table_context"]["raw_headers"]
    assert "statement_scope" not in headers_only.present_facets
    assert "printed_label_evidence_ref" not in headers_only.present_facets


def test_context_truncation_and_blocking_issue_fail_closed() -> None:
    packages = tuple(_package(index=index) for index in range(1, 4))
    registry = Gate2FinancialEvidenceRegistryFactory().create()
    prepared = Gate2SameSourceTypeFirstProof(registry=registry).prepare(
        gate2_packages=packages
    )
    unit = prepared.units[0]
    truncated = Gate2BoundedSemanticContextFactory(
        Gate2BoundedSemanticContextConfig(maximum_text_characters=8)
    ).create(
        source_package=unit.source_package,
        selected_source_refs=unit.scope.selected_source_refs,
        gate2_packages=packages,
    )
    card = next(
        item
        for item in prepared.candidate.payload["type_cards"]
        if item["local_type_key"] == "t02"
    )
    option = next(
        item
        for item in prepared.mapping_receipt.option_restoration
        if item["source_unit_key"] == unit.source_unit_key
        and item["local_type_key"] == "t02"
    )
    decision = Gate2ContextSufficiencyGuard().evaluate(
        context=truncated,
        type_card=card,
        exact_option=option,
        expected_source_package_integrity_hash=unit.source_package.integrity_hash,
    )
    assert truncated.context_truncated is True
    assert decision.status == "INSUFFICIENT"
    assert "context_truncated" in decision.triggered_disqualifiers


def test_package_mismatch_context_tampering_and_stale_request_are_rejected() -> None:
    _registry, proof, packages, prepared, response, _execution = (
        _full_authorities()
    )
    unit = prepared.units[0]
    with pytest.raises(
        Gate2BoundedSemanticContextError,
        match="bounded_context_source_unit_package_mismatch",
    ):
        Gate2BoundedSemanticContextFactory().create(
            source_package=unit.source_package,
            selected_source_refs=("row:outside",),
            gate2_packages=packages,
        )

    tampered_payload = copy.deepcopy(unit.bounded_context.payload)
    tampered_payload["document_context"]["statement_scope"] = "tampered"
    tampered_context = replace(unit.bounded_context, payload=tampered_payload)
    card = prepared.candidate.payload["type_cards"][1]
    with pytest.raises(
        Gate2BoundedSemanticContextError,
        match="bounded_context_integrity_invalid",
    ):
        Gate2ContextSufficiencyGuard().evaluate(
            context=tampered_context,
            type_card=card,
            exact_option=None,
            expected_source_package_integrity_hash=(
                unit.source_package.integrity_hash
            ),
        )

    stale_payload = copy.deepcopy(prepared.candidate.payload)
    stale_payload["source_units"][0]["bounded_semantic_context_hash"] = "0" * 64
    stale_candidate = replace(prepared.candidate, payload=stale_payload)
    stale_prepared = replace(prepared, candidate=stale_candidate)
    with pytest.raises(
        Gate2SameSourceTypeFirstProofError,
        match="type_first_prepared_proof_invalid",
    ):
        proof.execute(prepared=stale_prepared, simulated_response=response)


def test_neighbors_are_selected_only_by_document_table_and_row_ordinal() -> None:
    packages = (
        _package(
            index=1,
            document_ref="document:shared",
            table_ref="table:shared",
            row_ordinal=10,
        ),
        _package(
            index=2,
            document_ref="document:shared",
            table_ref="table:shared",
            row_ordinal=11,
        ),
        _package(
            index=3,
            document_ref="document:unrelated",
            table_ref="table:shared",
            row_ordinal=12,
        ),
    )
    prepared = Gate2SameSourceTypeFirstProof(
        registry=Gate2FinancialEvidenceRegistryFactory().create()
    ).prepare(gate2_packages=packages)
    shared = [
        unit
        for unit in prepared.units
        if unit.source_package.document_ref == "document:shared"
    ]
    assert len(shared) == 2
    neighbor_counts = [
        len(unit.bounded_context.payload["local_structural_context"]["previous_rows"])
        + len(unit.bounded_context.payload["local_structural_context"]["next_rows"])
        for unit in shared
    ]
    assert neighbor_counts == [1, 1]
    serialized = json.dumps(
        [unit.bounded_context.payload for unit in shared],
        sort_keys=True,
    )
    assert "203.00" not in serialized


def test_builder_has_no_semantic_shortlist_and_is_absent_from_product_bundles() -> None:
    module = CONTEXT_MODULE_PATH.read_text(encoding="utf-8")
    lowered = module.casefold()
    assert "cash_balance_snapshot_v1" not in module
    assert "printed_financial_metric_v1" not in module
    assert "import re" not in lowered
    assert "provider" not in "\n".join(
        line for line in lowered.splitlines() if line.startswith("from ")
    )
    product = PRODUCT_ROUTE_PATH.read_text(encoding="utf-8")
    assert "gate2_bounded_semantic_context" not in product
    for path in FUNCTION_PATHS:
        text = path.read_text(encoding="utf-8")
        assert "Gate2BoundedSemanticContextFactory" not in text
        assert "INSUFFICIENT_SEMANTIC_CONTEXT" not in text


def test_model_request_is_bounded_opaque_and_provider_free() -> None:
    _registry, _proof, _packages, prepared, _response, _execution = (
        _full_authorities()
    )
    serialized = json.dumps(prepared.candidate.payload, sort_keys=True)
    assert "source_value_ref" not in serialized
    assert "cash_balance_snapshot_v1" not in serialized
    assert "printed_financial_metric_v1" not in serialized
    assert prepared.candidate.provider_calls_total == 0
    assert prepared.candidate.active is False
    assert prepared.candidate.transport_eligible is False
    assert all(
        len(
            json.dumps(
                unit.bounded_context.payload,
                ensure_ascii=False,
                separators=(",", ":"),
            )
        )
        <= 24_000
        for unit in prepared.units
    )
