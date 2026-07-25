from __future__ import annotations

import copy
from collections import Counter
from dataclasses import dataclass
from typing import Any, Callable

from .gate2_deterministic_financial_scopes import (
    Gate2DeterministicFinancialScope,
    Gate2DeterministicFinancialScopeFromGate1Factory,
    validate_deterministic_financial_scope,
)
from .gate2_financial_context import (
    Gate2FinancialContextProjectionFactory,
    validate_financial_context,
)
from .gate2_financial_evidence_decision import DISPOSITIONS
from .gate2_financial_evidence_materialization import (
    FinancialEvidenceExecutionMetadata,
    Gate2FinancialEvidenceMaterializerFactory,
    Gate2FinancialEvidenceValidatedDecisionFactory,
    validate_financial_evidence_inputs,
)
from .gate2_financial_evidence_materialization_contracts import (
    sha256_json,
)
from .gate2_financial_evidence_registry import (
    Gate2FinancialEvidenceRegistrySnapshot,
)
from .gate2_successor_compatibility import (
    Gate2SuccessorCompatibilityReader,
    Gate2SuccessorCompatibilityReaderFactory,
)
from .gate2_successor_product_comparator import (
    Gate2SuccessorProductComparatorFactory,
    Gate2SuccessorProductExpectation,
    Gate2SuccessorScopeObservation,
)


LOCAL_PROOF_MANIFEST_SCHEMA_VERSION = (
    "broker_reports_gate2_financial_successor_fixture_manifest_v1"
)
LOCAL_PROOF_RECEIPT_SCHEMA_VERSION = (
    "broker_reports_gate2_financial_successor_local_proof_receipt_v1"
)
LOCAL_PROOF_POLICY_VERSION = (
    "gate2_financial_successor_local_proof_v1"
)
REQUIRED_FEATURES = (
    "signed_literals",
    "currency_date",
    "detail_vs_subtotal",
    "repeated_headers",
    "missing_optional_dimensions",
    "adjacent_equal_values",
    "adjacent_fx_values",
    "multiple_hypotheses",
    "forbidden_neighbouring_refs",
    "explicit_unclassified",
    "unsupported_source_shape",
)

FACTORY_REQUIRED = (
    "Gate2SuccessorLocalProofFactory.create is the only frozen synthetic "
    "Q0/Q1 successor proof entrypoint"
)
FORBIDDEN = (
    "Local proof must not call providers, retry, repair, fallback, persist "
    "artifacts, activate routing or weaken canonical validators"
)


class Gate2SuccessorLocalProofError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class _FixturePackage:
    payload: dict[str, Any]
    selected_value_refs: dict[str, str]
    selected_literals: dict[str, str]
    forbidden_value_refs: tuple[str, ...]


@dataclass(frozen=True)
class _EvaluatedCase:
    scope: Gate2DeterministicFinancialScope
    model_output: dict[str, Any]
    materialized_artifact: dict[str, Any]
    execution_ref: str
    decision_validation_ref: str
    expected_disposition: str
    expected_input_type_id: str | None


class Gate2SuccessorLocalProofFactory:
    def __init__(
        self,
        *,
        registry: Gate2FinancialEvidenceRegistrySnapshot,
    ) -> None:
        self.registry = registry

    def create(self, *, manifest: dict[str, Any]) -> dict[str, Any]:
        frozen_manifest = _validate_manifest(manifest)
        scope_factory = Gate2DeterministicFinancialScopeFromGate1Factory(
            registry=self.registry
        )
        compatibility = Gate2SuccessorCompatibilityReaderFactory(
            registry=self.registry
        ).create()

        evaluated: list[_EvaluatedCase] = []
        source_packages = []
        artifacts: list[dict[str, Any]] = []
        feature_counts: Counter[str] = Counter()
        terminal_counts: Counter[str] = Counter()
        provider_schema_hashes: dict[str, set[str]] = {
            "openai": set(),
            "gemini": set(),
        }
        source_literals_total = 0
        forbidden_refs_total = 0
        selected_source_refs_total = 0
        deterministic_no_fact_refs_total = 0

        for case in frozen_manifest["cases"]:
            fixture = _fixture_package(case)
            batch = scope_factory.create(
                gate1_packages=(fixture.payload,)
            )
            repeated = scope_factory.create(
                gate1_packages=(fixture.payload,)
            )
            if batch != repeated or batch.safe_summary() != (
                repeated.safe_summary()
            ):
                _fail("successor_local_proof_scope_not_deterministic")
            if len(batch.scopes) != 1:
                _fail("successor_local_proof_scope_count_invalid")
            scope = batch.scopes[0]
            validate_deterministic_financial_scope(scope)
            _validate_coverage(batch.coverage)
            _validate_fixture_authority(
                scope=scope,
                fixture=fixture,
            )

            openai_schema = scope.decision_contract.openai_response_format()
            gemini_schema = scope.decision_contract.gemini_response_format()
            _validate_provider_schema(
                response_format=openai_schema,
            )
            _validate_provider_schema(
                response_format=gemini_schema,
            )
            provider_schema_hashes["openai"].add(
                scope.decision_contract.provider_schema_hash("openai")
            )
            provider_schema_hashes["gemini"].add(
                scope.decision_contract.provider_schema_hash("gemini")
            )

            model_output = _model_output(
                case=case,
                scope=scope,
                selected_value_refs=fixture.selected_value_refs,
            )
            validated = Gate2FinancialEvidenceValidatedDecisionFactory(
                contract=scope.decision_contract
            ).create(model_output)
            execution_ref = f"execution:local-proof:{case['case_id']}"
            decision_validation_ref = (
                f"validation:local-proof:{case['case_id']}"
            )
            metadata = FinancialEvidenceExecutionMetadata(
                execution_ref=execution_ref,
                decision_validation_ref=decision_validation_ref,
            )
            materializer = Gate2FinancialEvidenceMaterializerFactory(
                registry=self.registry,
                source_package=scope.source_package,
                execution_metadata=metadata,
            ).create()
            first_artifact = materializer.materialize(
                validated_decision=validated
            )
            second_artifact = materializer.materialize(
                validated_decision=validated
            )
            if first_artifact != second_artifact:
                _fail(
                    "successor_local_proof_materialization_not_deterministic"
                )
            validate_financial_evidence_inputs(
                payload=first_artifact,
                registry=self.registry,
            )
            before_hash = sha256_json(first_artifact)
            read = compatibility.read(
                artifact_ref=f"artifact:local-proof:{case['case_id']}",
                payload=first_artifact,
            )
            if (
                sha256_json(first_artifact) != before_hash
                or read.artifact_sha256 != before_hash
                or read.read_kind != "successor_financial_evidence"
                or read.legacy_payload_rewritten
                or read.silent_conversion_used
            ):
                _fail("successor_local_proof_compatibility_read_invalid")

            disposition = model_output["decision"]["disposition"]
            input_type_id = model_output["decision"].get(
                "input_type_id"
            )
            evaluated.append(
                _EvaluatedCase(
                    scope=scope,
                    model_output=model_output,
                    materialized_artifact=first_artifact,
                    execution_ref=execution_ref,
                    decision_validation_ref=decision_validation_ref,
                    expected_disposition=disposition,
                    expected_input_type_id=input_type_id,
                )
            )
            source_packages.append(scope.source_package)
            artifacts.append(first_artifact)
            feature_counts.update(case["features"])
            terminal_counts[disposition] += 1
            source_literals_total += len(fixture.selected_literals)
            forbidden_refs_total += len(fixture.forbidden_value_refs)
            selected_source_refs_total += batch.coverage[
                "selected_source_refs_total"
            ]
            deterministic_no_fact_refs_total += batch.coverage[
                "deterministic_no_fact_source_refs_total"
            ]

        first_context = Gate2FinancialContextProjectionFactory(
            registry=self.registry
        ).create(
            materialized_artifacts=artifacts,
            source_packages=source_packages,
        )
        second_context = Gate2FinancialContextProjectionFactory(
            registry=self.registry
        ).create(
            materialized_artifacts=tuple(reversed(artifacts)),
            source_packages=tuple(reversed(source_packages)),
        )
        if first_context != second_context:
            _fail("successor_local_proof_context_not_deterministic")
        validate_financial_context(
            payload=first_context,
            registry=self.registry,
        )

        product_receipt = Gate2SuccessorProductComparatorFactory(
            registry=self.registry
        ).create().compare(
            authorized_scopes=(
                item.scope for item in evaluated
            ),
            observations=(
                Gate2SuccessorScopeObservation(
                    source_scope_ref=(
                        item.scope.source_package.source_scope_ref
                    ),
                    model_output=item.model_output,
                    materialized_artifact=item.materialized_artifact,
                    execution_ref=item.execution_ref,
                    decision_validation_ref=(
                        item.decision_validation_ref
                    ),
                    expectation=Gate2SuccessorProductExpectation(
                        expected_disposition=(
                            item.expected_disposition
                        ),
                        expected_input_type_id=(
                            item.expected_input_type_id
                        ),
                    ),
                )
                for item in evaluated
            ),
            final_context=first_context,
        )
        if product_receipt["status"] != "passed":
            _fail("successor_local_proof_product_invariants_failed")

        negative_checks = _negative_checks(
            evaluated=evaluated,
            compatibility=compatibility,
            context=first_context,
            registry=self.registry,
        )
        q0_checks = {
            "scope_determinism": True,
            "package_integrity": True,
            "provider_schema_generation": True,
            "canonical_branch_validation": True,
            "materialization_determinism": True,
            "context_determinism": True,
            "compatibility_read": True,
            "coverage_accounting": True,
            "negative_fail_closed": all(negative_checks.values()),
        }
        q1_checks = {
            feature: feature_counts[feature] > 0
            for feature in REQUIRED_FEATURES
        }
        metrics = product_receipt["metrics"]
        receipt: dict[str, Any] = {
            "schema_version": LOCAL_PROOF_RECEIPT_SCHEMA_VERSION,
            "policy_version": LOCAL_PROOF_POLICY_VERSION,
            "status": (
                "passed"
                if all(q0_checks.values())
                and all(q1_checks.values())
                and metrics["literal_loss_total"] == 0
                else "failed"
            ),
            "manifest": {
                "schema_version": frozen_manifest["schema_version"],
                "benchmark_id": frozen_manifest["benchmark_id"],
                "integrity_hash": sha256_json(frozen_manifest),
                "frozen": True,
                "contains_customer_data": False,
                "cases_total": len(frozen_manifest["cases"]),
            },
            "q0_contract_tests": {
                "status": (
                    "passed" if all(q0_checks.values()) else "failed"
                ),
                "checks": q0_checks,
            },
            "q1_product_invariant_fixtures": {
                "status": (
                    "passed" if all(q1_checks.values()) else "failed"
                ),
                "required_features_total": len(REQUIRED_FEATURES),
                "covered_features_total": sum(q1_checks.values()),
                "checks": q1_checks,
            },
            "terminal_disposition_counts": {
                disposition: terminal_counts[disposition]
                for disposition in DISPOSITIONS
            },
            "provider_schema_generation": {
                "openai_schema_hashes": sorted(
                    provider_schema_hashes["openai"]
                ),
                "gemini_schema_hashes": sorted(
                    provider_schema_hashes["gemini"]
                ),
                "strict_json_schema": True,
                "canonical_validator_replacement": False,
            },
            "product_invariants": {
                "status": product_receipt["status"],
                "checks": copy.deepcopy(product_receipt["checks"]),
                "literal_loss_total": metrics["literal_loss_total"],
                "invented_values_total": metrics[
                    "invented_values_total"
                ],
                "duplicate_bindings_total": metrics[
                    "duplicate_bindings_total"
                ],
                "cross_scope_bindings_total": metrics[
                    "cross_scope_bindings_total"
                ],
                "terminal_ownership_gap_total": metrics[
                    "terminal_ownership_gap_total"
                ],
            },
            "coverage": {
                "selected_source_refs_total": selected_source_refs_total,
                "deterministic_no_fact_refs_total": (
                    deterministic_no_fact_refs_total
                ),
                "source_literals_total": source_literals_total,
                "source_literals_preserved_total": (
                    source_literals_total
                ),
                "forbidden_neighbouring_refs_total": (
                    forbidden_refs_total
                ),
                "forbidden_neighbouring_refs_admitted_total": 0,
                "unaccounted_source_refs_total": 0,
            },
            "negative_checks": negative_checks,
            "execution_accounting": {
                "provider_calls_total": 0,
                "source_model_calls_total": 0,
                "domain_model_calls_total": 0,
                "financial_model_calls_total": 0,
                "fallback_total": 0,
                "repair_attempts_total": 0,
                "hidden_retry_total": 0,
                "persistence_writes_total": 0,
                "production_route_activations_total": 0,
            },
            "context_integrity_hash": first_context["integrity_hash"],
        }
        receipt["integrity_hash"] = sha256_json(receipt)
        if receipt["status"] != "passed":
            _fail("successor_local_proof_failed")
        return receipt


def _validate_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(manifest, dict):
        _fail("successor_local_proof_manifest_invalid")
    frozen = copy.deepcopy(manifest)
    if (
        frozen.get("schema_version")
        != LOCAL_PROOF_MANIFEST_SCHEMA_VERSION
        or frozen.get("benchmark_id")
        != "gate2_financial_successor_v1"
        or frozen.get("frozen") is not True
        or frozen.get("contains_customer_data") is not False
        or frozen.get("case_count") != len(frozen.get("cases") or [])
    ):
        _fail("successor_local_proof_manifest_identity_invalid")
    policy = frozen.get("execution_policy") or {}
    if (
        policy.get("provider_calls") != 0
        or policy.get("hidden_retry") is not False
        or policy.get("repair") is not False
        or policy.get("fallback") is not False
        or policy.get("canonical_validator_replacement") is not False
        or policy.get("raw_output_in_safe_receipt") is not False
    ):
        _fail("successor_local_proof_execution_policy_invalid")
    if tuple(frozen.get("required_features") or []) != REQUIRED_FEATURES:
        _fail("successor_local_proof_required_features_invalid")
    cases = frozen.get("cases") or []
    case_ids = [item.get("case_id") for item in cases]
    if (
        not cases
        or len(case_ids) != len(set(case_ids))
        or not all(isinstance(item, str) and item for item in case_ids)
    ):
        _fail("successor_local_proof_cases_invalid")
    observed_features = {
        feature
        for case in cases
        for feature in case.get("features") or []
    }
    if observed_features != set(REQUIRED_FEATURES):
        _fail("successor_local_proof_feature_coverage_invalid")
    return frozen


def _fixture_package(case: dict[str, Any]) -> _FixturePackage:
    case_id = case["case_id"]
    primary_row_ref = f"row:{case_id}:primary"
    neighbour_row_ref = f"row:{case_id}:neighbour"
    header_ref = f"header:{case_id}:repeated"
    primary = _row_cells(
        case_id=case_id,
        row_kind="primary",
        row_ref=primary_row_ref,
        cells=case.get("cells") or [],
    )
    neighbour = _row_cells(
        case_id=case_id,
        row_kind="neighbour",
        row_ref=neighbour_row_ref,
        cells=case.get("neighbour_cells") or [],
    )
    all_cells = [*primary, *neighbour]
    if not primary:
        _fail("successor_local_proof_fixture_cells_empty")
    rows = [
        _model_row(primary_row_ref, primary),
    ]
    row_refs = [primary_row_ref]
    if neighbour:
        rows.append(_model_row(neighbour_row_ref, neighbour))
        row_refs.append(neighbour_row_ref)
    value_index = [
        {
            "source_value_ref": item["source_value_ref"],
            "row_ref": item["row_ref"],
            "cell_ref": item["cell_ref"],
            "value_path": {
                "kind": "table_cell",
                "row_index": (
                    0 if item["row_ref"] == primary_row_ref else 1
                ),
                "column_index": item["column_ordinal"] - 1,
            },
            "value_checksum_ref": (
                f"checksum:{item['source_value_ref']}"
            ),
        }
        for item in all_cells
    ]
    payload = {
        "schema_version": "broker_reports_source_fact_package_v0",
        "package_id": f"package:{case_id}",
        "extraction_run_id": "extraction:local-successor-proof",
        "normalization_run_id": "normalization:local-successor-proof",
        "case_id": f"case:{case_id}",
        "document_ref": f"document:{case_id}",
        "source_bucket_roles": ["primary_source_refs"],
        "document_context": {
            "usage_modes": ["source_fact"],
            "passport": {"document_kind_candidate": "broker_report"},
        },
        "source_unit": {
            "unit_id": f"unit:{case_id}",
            "unit_kind": "table_row_window",
            "source_input_mode": "normalized_table_projection",
            "private_slice_artifact_ref": f"artifact:{case_id}",
            "slice_ref": f"slice:{case_id}",
            "document_ref": f"document:{case_id}",
            "source_checksum_ref": f"checksum:{case_id}",
            "slice_payload_checksum_ref": (
                f"payload-checksum:{case_id}"
            ),
            "parser_ref": "parser:local-successor-proof",
            "table_ref": f"table:{case_id}",
            "row_range_ref": f"row-range:{case_id}",
            "coverage_ref": f"coverage:{case_id}",
            "normalized_header_descriptors": [
                {
                    "column_ordinal": item["column_ordinal"],
                    "normalized_label": item["header_label"],
                }
                for item in primary
            ],
            "row_refs": row_refs,
            "row_provenance": [
                {
                    "row_ref": row_ref,
                    "row_ordinal": index,
                    "row_kind": "fact_candidate",
                }
                for index, row_ref in enumerate(row_refs, start=1)
            ],
            "cell_refs": [item["cell_ref"] for item in all_cells],
            "cell_provenance": [
                {
                    "row_ordinal": (
                        1
                        if item["row_ref"] == primary_row_ref
                        else 2
                    ),
                    "column_ordinal": item["column_ordinal"],
                    "row_ref": item["row_ref"],
                    "cell_ref": item["cell_ref"],
                    "source_value_ref": item["source_value_ref"],
                }
                for item in all_cells
            ],
            "cell_value_refs": [
                item["source_value_ref"] for item in all_cells
            ],
            "source_value_refs": [
                item["source_value_ref"] for item in all_cells
            ],
            "source_value_index": value_index,
            "private_values": [],
            "text_segment_refs": [],
            "section_refs": [],
            "page_refs": [],
            "character_span_refs": [],
            "segment_provenance": [],
            "normalized_source_projection": {
                "cells": [
                    [item["value"] for item in primary],
                    *(
                        [[item["value"] for item in neighbour]]
                        if neighbour
                        else []
                    ),
                ]
            },
            "model_source_projection": {
                "schema_version": "gate2_model_table_projection_v0",
                "rows": rows,
            },
        },
        "allowed_evidence_refs": [primary_row_ref, header_ref],
        "allowed_source_value_refs": [
            item["source_value_ref"] for item in all_cells
        ],
        "issue_context": [],
        "allowed_issue_refs": [],
        "forbidden_assumptions": [
            "do_not_infer_missing_values",
            "do_not_use_neighbouring_rows",
        ],
        "coverage_expectation": {
            "coverage_ref": f"coverage:{case_id}",
            "selected_source_refs": [primary_row_ref, header_ref],
            "ignorable_header_refs": [header_ref],
            "ignorable_blank_refs": [],
            "layout_candidate_refs": [],
            "mandatory_no_fact_results": [
                {
                    "source_ref": header_ref,
                    "reason_code": "header_row",
                }
            ],
        },
        "privacy_policy": {
            "knowledge_rag_used": False,
            "vectorization_performed": False,
        },
        "created_at": "2026-07-25T00:00:00Z",
    }
    if case.get("source_family_id"):
        payload["source_family_id"] = case["source_family_id"]
    return _FixturePackage(
        payload=payload,
        selected_value_refs={
            item["key"]: item["source_value_ref"] for item in primary
        },
        selected_literals={
            item["source_value_ref"]: item["value"] for item in primary
        },
        forbidden_value_refs=tuple(
            item["source_value_ref"] for item in neighbour
        ),
    )


def _row_cells(
    *,
    case_id: str,
    row_kind: str,
    row_ref: str,
    cells: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    result = []
    keys = [item.get("key") for item in cells]
    if len(keys) != len(set(keys)):
        _fail("successor_local_proof_fixture_cell_key_duplicate")
    for index, item in enumerate(cells, start=1):
        if (
            not isinstance(item.get("key"), str)
            or not isinstance(item.get("header"), str)
            or not isinstance(item.get("literal"), str)
            or not item["literal"]
        ):
            _fail("successor_local_proof_fixture_cell_invalid")
        result.append(
            {
                "key": item["key"],
                "column_ordinal": index,
                "header_label": item["header"],
                "cell_ref": (
                    f"{case_id}:{row_kind}:cell:{item['key']}"
                ),
                "source_value_ref": (
                    f"{case_id}:{row_kind}:value:{item['key']}"
                ),
                "row_ref": row_ref,
                "value": item["literal"],
            }
        )
    return result


def _model_row(
    row_ref: str,
    cells: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "row_ref": row_ref,
        "row_kind": "fact_candidate",
        "fact_type_hint": "financial",
        "fact_type_hint_policy": "synthetic_local_proof",
        "cells": [
            {
                key: value
                for key, value in item.items()
                if key
                in {
                    "column_ordinal",
                    "header_label",
                    "cell_ref",
                    "source_value_ref",
                    "value",
                }
            }
            for item in cells
        ],
    }


def _model_output(
    *,
    case: dict[str, Any],
    scope: Gate2DeterministicFinancialScope,
    selected_value_refs: dict[str, str],
) -> dict[str, Any]:
    fixture_decision = case.get("decision") or {}
    disposition = fixture_decision.get("disposition")
    reason_code = fixture_decision.get("reason_code")
    if disposition == "typed_input":
        input_type_id = fixture_decision.get("input_type_id")
        declaration = scope.decision_contract.registry.get(
            input_type_id
        )
        raw_bindings = fixture_decision.get("bindings") or {}
        expected_roles = set(
            declaration.required_roles + declaration.optional_roles
        )
        if set(raw_bindings) != expected_roles:
            _fail("successor_local_proof_fixture_typed_roles_invalid")
        bindings = {
            role_id: _resolve_fixture_ref(
                value_key=value_key,
                role_id=role_id,
                scope=scope,
                selected_value_refs=selected_value_refs,
            )
            for role_id, value_key in raw_bindings.items()
        }
        return {
            "decision": {
                "disposition": disposition,
                "input_type_id": input_type_id,
                "value_bindings": bindings,
                "reason_code": reason_code,
            }
        }
    if disposition == "unclassified_financial_input":
        if fixture_decision.get("binding_mode") != "all_candidates":
            _fail(
                "successor_local_proof_fixture_unclassified_mode_invalid"
            )
        return {
            "decision": {
                "disposition": disposition,
                "value_bindings": [
                    {
                        "role_id": candidate.allowed_roles[0],
                        "source_value_ref": candidate.source_value_ref,
                    }
                    for candidate in scope.decision_contract.package.candidates
                ],
                "reason_code": reason_code,
            }
        }
    if disposition in {"no_financial_input", "unsupported"}:
        return {
            "decision": {
                "disposition": disposition,
                "reason_code": reason_code,
            }
        }
    _fail("successor_local_proof_fixture_disposition_invalid")


def _resolve_fixture_ref(
    *,
    value_key: Any,
    role_id: str,
    scope: Gate2DeterministicFinancialScope,
    selected_value_refs: dict[str, str],
) -> str | None:
    if value_key is None:
        return None
    if value_key == "@statement_scope":
        return _single_role_ref(scope, "statement_scope")
    if value_key == "@printed_label":
        return _single_role_ref(scope, "printed_label_evidence_ref")
    if value_key not in selected_value_refs:
        _fail("successor_local_proof_fixture_binding_key_unknown")
    ref = selected_value_refs[value_key]
    candidates = {
        item.source_value_ref: item
        for item in scope.decision_contract.package.candidates
    }
    if role_id not in candidates[ref].allowed_roles:
        _fail("successor_local_proof_fixture_binding_incompatible")
    return ref


def _single_role_ref(
    scope: Gate2DeterministicFinancialScope,
    role_id: str,
) -> str:
    refs = [
        item.source_value_ref
        for item in scope.decision_contract.package.candidates
        if item.allowed_roles == (role_id,)
    ]
    if len(refs) != 1:
        _fail("successor_local_proof_fixture_reference_role_invalid")
    return refs[0]


def _validate_fixture_authority(
    *,
    scope: Gate2DeterministicFinancialScope,
    fixture: _FixturePackage,
) -> None:
    values = {
        item.source_value_ref: item.literal_value
        for item in scope.source_package.source_values
    }
    if any(
        values.get(ref) != literal
        for ref, literal in fixture.selected_literals.items()
    ):
        _fail("successor_local_proof_literal_loss")
    candidates = {
        item.source_value_ref
        for item in scope.decision_contract.package.candidates
    }
    if set(fixture.forbidden_value_refs) & candidates:
        _fail("successor_local_proof_forbidden_neighbour_admitted")


def _validate_coverage(coverage: dict[str, Any]) -> None:
    if (
        coverage.get("all_selected_refs_terminally_accounted") is not True
        or coverage.get("unaccounted_source_refs")
        or coverage.get("duplicate_terminal_owner_refs")
        or coverage.get("model_calls_total") != 0
    ):
        _fail("successor_local_proof_coverage_invalid")


def _validate_provider_schema(
    *,
    response_format: dict[str, Any],
) -> None:
    schema = (response_format.get("json_schema") or {}).get("schema")
    if (
        response_format.get("type") != "json_schema"
        or (response_format.get("json_schema") or {}).get("strict")
        is not True
        or not isinstance(schema, dict)
        or schema.get("additionalProperties") is not False
    ):
        _fail("successor_local_proof_provider_schema_invalid")
    dispositions = {
        value
        for item in _walk_dicts(schema)
        for value in item.get("enum", [])
        if value in DISPOSITIONS
    }
    terminal_branches = set(DISPOSITIONS) - {"typed_input"}
    if not terminal_branches <= dispositions or not dispositions <= (
        set(DISPOSITIONS)
    ):
        _fail("successor_local_proof_provider_schema_branch_invalid")


def _walk_dicts(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_dicts(child)


def _negative_checks(
    *,
    evaluated: list[_EvaluatedCase],
    compatibility: Gate2SuccessorCompatibilityReader,
    context: dict[str, Any],
    registry: Gate2FinancialEvidenceRegistrySnapshot,
) -> dict[str, bool]:
    typed = next(
        item
        for item in evaluated
        if item.expected_disposition == "typed_input"
    )
    outside = copy.deepcopy(typed.model_output)
    amount_role = outside["decision"]["value_bindings"]
    amount_role["amount"] = "value:outside-authorized-package"
    unknown_field = copy.deepcopy(typed.model_output)
    unknown_field["decision"]["audit"] = {"created_by": "fixture"}
    tampered_artifact = copy.deepcopy(typed.materialized_artifact)
    tampered_artifact["coverage"]["candidate_refs_total"] = -1
    tampered_context = copy.deepcopy(context)
    tampered_context["scope_coverage"]["source_scopes_total"] = -1
    return {
        "out_of_package_binding_rejected": _fails(
            lambda: Gate2FinancialEvidenceValidatedDecisionFactory(
                contract=typed.scope.decision_contract
            ).create(outside)
        ),
        "model_system_field_rejected": _fails(
            lambda: Gate2FinancialEvidenceValidatedDecisionFactory(
                contract=typed.scope.decision_contract
            ).create(unknown_field)
        ),
        "materialized_artifact_tamper_rejected": _fails(
            lambda: validate_financial_evidence_inputs(
                payload=tampered_artifact,
                registry=registry,
            )
        ),
        "context_tamper_rejected": _fails(
            lambda: validate_financial_context(
                payload=tampered_context,
                registry=registry,
            )
        ),
        "unknown_compatibility_schema_rejected": _fails(
            lambda: compatibility.read(
                artifact_ref="artifact:local-proof:unknown",
                payload={"schema_version": "unknown_schema_v1"},
            )
        ),
    }


def _fails(operation: Callable[[], Any]) -> bool:
    try:
        operation()
    except ValueError:
        return True
    return False


def _fail(code: str) -> None:
    raise Gate2SuccessorLocalProofError(code)
