from __future__ import annotations

import copy
import json
from collections import Counter
from typing import Any, Callable

from .gate2_deterministic_financial_scopes import (
    Gate2DeterministicFinancialScopeFromGate1V2Factory,
    validate_deterministic_financial_scope_v2,
)
from .gate2_financial_context import (
    Gate2FinancialContextProjectionFactory,
    validate_financial_context,
)
from .gate2_financial_domain_catalog import (
    Gate2FinancialDomainCatalogFactory,
)
from .gate2_financial_domain_contracts import (
    FINANCIAL_DOMAIN_QUERY_POLICY_VERSION,
    FINANCIAL_DOMAIN_QUERY_SCHEMA_VERSION,
    FINANCIAL_DOMAIN_SNAPSHOT_SCHEMA_VERSION,
    FinancialDomainAccessContext,
    canonical_json,
    sha256_json,
)
from .gate2_financial_domain_persistence import (
    FINANCIAL_DOMAIN_PERSISTENCE_SCHEMA_VERSION,
    Gate2FinancialDomainPersistenceFactory,
)
from .gate2_financial_domain_query import (
    Gate2FinancialDomainQueryFactory,
)
from .gate2_financial_evidence_decision import DISPOSITIONS
from .gate2_financial_evidence_materialization import (
    FinancialEvidenceExecutionMetadata,
    Gate2FinancialEvidenceMaterializerFactory,
    Gate2FinancialEvidenceValidatedDecisionFactory,
    validate_financial_evidence_inputs,
)
from .gate2_financial_evidence_registry import (
    Gate2FinancialEvidenceRegistrySnapshot,
)
from .gate2_financial_evidence_source_context import (
    SOURCE_CONTEXT_SCHEMA_VERSION,
    Gate2FinancialEvidenceSourceContextFactory,
    validate_financial_evidence_source_context,
)
from .gate2_financial_evidence_successor import (
    SUCCESSOR_MODEL_INPUT_SCHEMA_VERSION_V4,
    SUCCESSOR_PROMPT_CONTRACT_ID_V4,
    Gate2FinancialEvidenceSuccessorConfig,
    Gate2FinancialEvidenceSuccessorRunnerFactory,
    validate_financial_evidence_successor_model_input_v4,
)
from .gate2_financial_semantic_model_assets import (
    MANAGED_ASSET_IDENTITIES_SHA256,
    load_gate2_financial_semantic_model_assets,
)
from .gate2_successor_local_proof import (
    _EvaluatedCase,
    _fixture_package,
    _model_output,
    _validate_coverage,
    _validate_fixture_authority,
)
from .gate2_successor_local_proof_v2 import (
    Gate2SuccessorLocalProofV2Factory,
)
from .gate2_successor_product_comparator import (
    Gate2SuccessorProductComparatorFactory,
    Gate2SuccessorProductExpectation,
    Gate2SuccessorScopeObservation,
)


LOCAL_DOMAIN_PROOF_RECEIPT_SCHEMA_VERSION = (
    "broker_reports_gate2_managed_financial_domain_local_proof_receipt_v1"
)
LOCAL_DOMAIN_PROOF_POLICY_VERSION = (
    "gate2_managed_financial_domain_local_end_to_end_proof_v1"
)

FACTORY_REQUIRED = (
    "Gate2FinancialDomainLocalProofFactory.create is the only frozen "
    "synthetic managed financial domain end-to-end proof entrypoint"
)
FORBIDDEN = (
    "Local domain proof must not call providers, write persistence, activate "
    "production routes, use customer data or replace canonical authorities"
)

_ACCESS_CONTEXT = FinancialDomainAccessContext(
    user_ref="user:synthetic-local-domain-proof",
    case_ref="case:synthetic-local-domain-proof",
    workspace_ref="workspace:synthetic-local-domain-proof",
)
_CREATED_AT = "2026-07-26T00:00:00+00:00"


class Gate2FinancialDomainLocalProofError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class _NoCallModelClient:
    def __init__(self) -> None:
        self.calls_total = 0

    async def extract(self, **kwargs):
        self.calls_total += 1
        _fail("financial_domain_local_proof_provider_call_forbidden")


class Gate2FinancialDomainLocalProofFactory:
    def __init__(
        self,
        *,
        registry: Gate2FinancialEvidenceRegistrySnapshot,
        snapshot_authority_key: bytes,
        continuation_key: bytes,
    ) -> None:
        self.registry = registry
        self._snapshot_authority_key = bytes(snapshot_authority_key)
        self._continuation_key = bytes(continuation_key)

    def create(self, *, manifest: dict[str, Any]) -> dict[str, Any]:
        frozen_manifest = copy.deepcopy(manifest)
        prerequisite = Gate2SuccessorLocalProofV2Factory(
            registry=self.registry
        ).create(manifest=frozen_manifest)
        if prerequisite["status"] != "passed":
            _fail("financial_domain_local_proof_prerequisite_failed")

        assets = load_gate2_financial_semantic_model_assets()
        model_client = _NoCallModelClient()
        runner = Gate2FinancialEvidenceSuccessorRunnerFactory(
            registry=self.registry,
            model_client=model_client,
            config=Gate2FinancialEvidenceSuccessorConfig(
                model_id="local-domain-proof-no-call",
                provider_profile_id="local_domain_proof_no_call",
                model_input_schema_version=(
                    SUCCESSOR_MODEL_INPUT_SCHEMA_VERSION_V4
                ),
                prompt_contract_id=SUCCESSOR_PROMPT_CONTRACT_ID_V4,
            ),
        ).create()
        scope_factory = Gate2DeterministicFinancialScopeFromGate1V2Factory(
            registry=self.registry
        )
        context_factory = Gate2FinancialEvidenceSourceContextFactory()

        evaluated: list[_EvaluatedCase] = []
        artifacts: list[dict[str, Any]] = []
        source_packages = []
        model_inputs: list[dict[str, Any]] = []
        source_contexts = []
        model_input_hashes: set[str] = set()
        source_context_hashes: set[str] = set()
        disposition_counts: Counter[str] = Counter()

        for case in frozen_manifest["cases"]:
            fixture = _fixture_package(case)
            batch = scope_factory.create(gate1_packages=(fixture.payload,))
            repeated = scope_factory.create(
                gate1_packages=(copy.deepcopy(fixture.payload),)
            )
            if batch != repeated or len(batch.scopes) != 1:
                _fail("financial_domain_local_proof_scope_not_deterministic")
            _validate_coverage(batch.coverage)
            scope = batch.scopes[0]
            validate_deterministic_financial_scope_v2(scope)
            _validate_fixture_authority(scope=scope, fixture=fixture)

            source_context = context_factory.create(
                source_scope_ref=scope.source_package.source_scope_ref,
                source_values=scope.source_package.source_values,
                candidates=scope.decision_contract.package.candidates,
                gate1_packages=(fixture.payload,),
            )
            validate_financial_evidence_source_context(
                context=source_context,
                source_scope_ref=scope.source_package.source_scope_ref,
                source_values=scope.source_package.source_values,
                candidates=scope.decision_contract.package.candidates,
            )
            model_input = runner.model_input(
                scope=scope,
                source_context=source_context,
            )
            validate_financial_evidence_successor_model_input_v4(
                model_input=model_input,
                scope=scope,
                source_context=source_context,
            )
            if (
                model_input["managed_assets"] != assets["managed_assets"]
                or model_input["semantic_pack"]
                != assets["semantic_pack"]
                or "expected" in canonical_json(model_input).lower()
                or "decision" in model_input
            ):
                _fail("financial_domain_local_proof_model_input_invalid")
            model_inputs.append(model_input)
            source_contexts.append(source_context)
            model_input_hashes.add(sha256_json(model_input))
            source_context_hashes.add(source_context.integrity_hash)

            model_output = _model_output(
                case=case,
                scope=scope,
                selected_value_refs=fixture.selected_value_refs,
            )
            validated = Gate2FinancialEvidenceValidatedDecisionFactory(
                contract=scope.decision_contract
            ).create(model_output)
            execution_ref = (
                f"execution:local-domain-proof:{case['case_id']}"
            )
            decision_validation_ref = (
                f"validation:local-domain-proof:{case['case_id']}"
            )
            artifact = Gate2FinancialEvidenceMaterializerFactory(
                registry=self.registry,
                source_package=scope.source_package,
                execution_metadata=FinancialEvidenceExecutionMetadata(
                    execution_ref=execution_ref,
                    decision_validation_ref=decision_validation_ref,
                ),
            ).create().materialize(validated_decision=validated)
            validate_financial_evidence_inputs(
                payload=artifact,
                registry=self.registry,
                source_package=scope.source_package,
            )
            disposition = model_output["decision"]["disposition"]
            evaluated.append(
                _EvaluatedCase(
                    scope=scope,
                    model_output=model_output,
                    materialized_artifact=artifact,
                    execution_ref=execution_ref,
                    decision_validation_ref=decision_validation_ref,
                    expected_disposition=disposition,
                    expected_input_type_id=model_output["decision"].get(
                        "input_type_id"
                    ),
                )
            )
            artifacts.append(artifact)
            source_packages.append(scope.source_package)
            disposition_counts[disposition] += 1

        product_receipt = self._product_receipt(
            evaluated=evaluated,
            artifacts=artifacts,
            source_packages=source_packages,
        )
        snapshot = Gate2FinancialDomainCatalogFactory(
            registry=self.registry,
            snapshot_authority_key=self._snapshot_authority_key,
        ).create(
            materialized_artifacts=artifacts,
            source_packages=source_packages,
            access_context=_ACCESS_CONTEXT,
            created_at=_CREATED_AT,
            expires_at=None,
        )
        persistence = Gate2FinancialDomainPersistenceFactory(
            snapshot_authority_key=self._snapshot_authority_key
        )
        serialized = persistence.serialize(snapshot=snapshot)
        restored = persistence.restore(serialized=serialized)
        if restored != snapshot:
            _fail("financial_domain_local_proof_persistence_roundtrip_invalid")
        query = Gate2FinancialDomainQueryFactory(
            snapshot=restored,
            registry=self.registry,
            access_context=_ACCESS_CONTEXT,
            snapshot_authority_key=self._snapshot_authority_key,
            continuation_key=self._continuation_key,
        ).create()
        query_evidence = _query_evidence(query=query, snapshot=restored)
        negative_checks = self._negative_checks(
            model_input=model_inputs[0],
            scope=evaluated[0].scope,
            source_context=source_contexts[0],
            artifacts=artifacts,
            source_packages=source_packages,
            snapshot=restored,
            serialized=serialized,
            query=query,
        )

        metrics = product_receipt["metrics"]
        checks = {
            "frozen_scope_prerequisite": True,
            "deterministic_scope_v2": True,
            "semantic_pack_loaded_by_managed_loader": True,
            "managed_asset_manifest_bound": True,
            "model_input_v4_validated": True,
            "all_terminal_decision_branches": (
                set(disposition_counts) == set(DISPOSITIONS)
                and all(disposition_counts[item] > 0 for item in DISPOSITIONS)
            ),
            "canonical_decision_validation": True,
            "authoritative_materialization": True,
            "persistence_roundtrip": restored == snapshot,
            "catalog_snapshot_validated": True,
            "query_completeness": query_evidence["query_gaps_total"] == 0,
            "provenance_completeness": (
                query_evidence["provenance_gaps_total"] == 0
            ),
            "coverage_completeness": (
                query_evidence["coverage_gaps_total"] == 0
            ),
            "fail_closed_negatives": all(negative_checks.values()),
        }
        passed = (
            all(checks.values())
            and metrics["literal_loss_total"] == 0
            and query_evidence["query_gaps_total"] == 0
            and model_client.calls_total == 0
        )
        receipt: dict[str, Any] = {
            "schema_version": LOCAL_DOMAIN_PROOF_RECEIPT_SCHEMA_VERSION,
            "policy_version": LOCAL_DOMAIN_PROOF_POLICY_VERSION,
            "status": "passed" if passed else "failed",
            "acceptance": {
                "local_domain_proof": (
                    "PASSED" if passed else "FAILED"
                ),
                "literal_loss": (
                    "ZERO"
                    if metrics["literal_loss_total"] == 0
                    else "NONZERO"
                ),
                "query_gaps": (
                    "ZERO"
                    if query_evidence["query_gaps_total"] == 0
                    else "NONZERO"
                ),
                "provider_calls": (
                    "ZERO" if model_client.calls_total == 0 else "NONZERO"
                ),
            },
            "manifest": {
                "schema_version": frozen_manifest["schema_version"],
                "benchmark_id": frozen_manifest["benchmark_id"],
                "integrity_sha256": sha256_json(frozen_manifest),
                "contains_customer_data": False,
                "cases_total": len(frozen_manifest["cases"]),
            },
            "exact_contracts": {
                "model_input_schema_version": (
                    SUCCESSOR_MODEL_INPUT_SCHEMA_VERSION_V4
                ),
                "prompt_contract_id": SUCCESSOR_PROMPT_CONTRACT_ID_V4,
                "prompt_sha256": runner.prompt.hash,
                "source_context_schema_version": (
                    SOURCE_CONTEXT_SCHEMA_VERSION
                ),
                "domain_snapshot_schema_version": (
                    FINANCIAL_DOMAIN_SNAPSHOT_SCHEMA_VERSION
                ),
                "persistence_schema_version": (
                    FINANCIAL_DOMAIN_PERSISTENCE_SCHEMA_VERSION
                ),
                "query_schema_version": (
                    FINANCIAL_DOMAIN_QUERY_SCHEMA_VERSION
                ),
                "query_policy_version": (
                    FINANCIAL_DOMAIN_QUERY_POLICY_VERSION
                ),
                "semantic_pack_sha256": assets["semantic_pack"][
                    "integrity_sha256"
                ],
                "managed_asset_identities_git_blob_sha256": (
                    MANAGED_ASSET_IDENTITIES_SHA256
                ),
                "managed_asset_manifest_sha256": assets[
                    "managed_assets"
                ]["manifest_sha256"],
            },
            "checks": checks,
            "terminal_disposition_counts": {
                item: disposition_counts[item] for item in DISPOSITIONS
            },
            "product_invariants": {
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
            "domain": {
                "snapshot_integrity_sha256": snapshot.integrity_sha256,
                "serialized_snapshot_sha256": sha256_json(
                    json.loads(serialized)
                ),
                "records_total": (
                    len(snapshot.typed_records())
                    + len(snapshot.unclassified_records())
                ),
                **query_evidence,
            },
            "exact_hashes": {
                "model_input_sha256": sorted(model_input_hashes),
                "source_context_sha256": sorted(source_context_hashes),
                "prerequisite_receipt_sha256": prerequisite[
                    "integrity_hash"
                ],
            },
            "negative_checks": negative_checks,
            "execution_accounting": {
                "provider_calls_total": model_client.calls_total,
                "source_model_calls_total": 0,
                "domain_model_calls_total": 0,
                "financial_model_calls_total": 0,
                "fallback_total": 0,
                "repair_attempts_total": 0,
                "hidden_retry_total": 0,
                "persistence_writes_total": 0,
                "production_route_activations_total": 0,
            },
        }
        receipt["integrity_sha256"] = sha256_json(receipt)
        if receipt["status"] != "passed":
            _fail("financial_domain_local_proof_failed")
        return receipt

    def _product_receipt(
        self,
        *,
        evaluated: list[_EvaluatedCase],
        artifacts: list[dict[str, Any]],
        source_packages: list[Any],
    ) -> dict[str, Any]:
        context = Gate2FinancialContextProjectionFactory(
            registry=self.registry
        ).create(
            materialized_artifacts=artifacts,
            source_packages=source_packages,
        )
        validate_financial_context(payload=context, registry=self.registry)
        receipt = Gate2SuccessorProductComparatorFactory(
            registry=self.registry
        ).create().compare(
            authorized_scopes=(item.scope for item in evaluated),
            observations=(
                Gate2SuccessorScopeObservation(
                    source_scope_ref=(
                        item.scope.source_package.source_scope_ref
                    ),
                    model_output=item.model_output,
                    materialized_artifact=item.materialized_artifact,
                    execution_ref=item.execution_ref,
                    decision_validation_ref=item.decision_validation_ref,
                    expectation=Gate2SuccessorProductExpectation(
                        expected_disposition=item.expected_disposition,
                        expected_input_type_id=(
                            item.expected_input_type_id
                        ),
                    ),
                )
                for item in evaluated
            ),
            final_context=context,
        )
        if receipt["status"] != "passed":
            _fail("financial_domain_local_proof_product_invariants_failed")
        return receipt

    def _negative_checks(
        self,
        *,
        model_input: dict[str, Any],
        scope: Any,
        source_context: Any,
        artifacts: list[dict[str, Any]],
        source_packages: list[Any],
        snapshot: Any,
        serialized: str,
        query: Any,
    ) -> dict[str, bool]:
        tampered_input = copy.deepcopy(model_input)
        tampered_input["managed_assets"]["manifest_sha256"] = "0" * 64
        model_input_rejected = _rejects(
            lambda: validate_financial_evidence_successor_model_input_v4(
                model_input=tampered_input,
                scope=scope,
                source_context=source_context,
            )
        )

        tampered_artifacts = copy.deepcopy(artifacts)
        tampered_artifacts[0]["coverage"][
            "candidate_refs_total"
        ] = -1
        artifact_rejected = _rejects(
            lambda: Gate2FinancialDomainCatalogFactory(
                registry=self.registry,
                snapshot_authority_key=self._snapshot_authority_key,
            ).create(
                materialized_artifacts=tampered_artifacts,
                source_packages=source_packages,
                access_context=_ACCESS_CONTEXT,
                created_at=_CREATED_AT,
                expires_at=None,
            )
        )

        envelope = json.loads(serialized)
        envelope["snapshot_payload"]["integrity_sha256"] = "0" * 64
        persistence = Gate2FinancialDomainPersistenceFactory(
            snapshot_authority_key=self._snapshot_authority_key
        )
        persistence_tamper_rejected = _rejects(
            lambda: persistence.restore(serialized=canonical_json(envelope))
        )
        wrong_key_rejected = _rejects(
            lambda: Gate2FinancialDomainPersistenceFactory(
                snapshot_authority_key=(
                    b"wrong-local-domain-proof-authority-key"
                )
            ).restore(serialized=serialized)
        )
        wrong_access_rejected = _rejects(
            lambda: Gate2FinancialDomainQueryFactory(
                snapshot=snapshot,
                registry=self.registry,
                access_context=FinancialDomainAccessContext(
                    user_ref="user:wrong-synthetic",
                    case_ref="case:synthetic-local-domain-proof",
                    workspace_ref=(
                        "workspace:synthetic-local-domain-proof"
                    ),
                ),
                snapshot_authority_key=self._snapshot_authority_key,
                continuation_key=self._continuation_key,
            ).create()
        )
        first_page = query.get_coverage(limit=1)
        continuation = first_page["continuation"]
        if not isinstance(continuation, str):
            _fail("financial_domain_local_proof_continuation_missing")
        tampered_continuation = continuation[:-1] + (
            "0" if continuation[-1] != "0" else "1"
        )
        continuation_rejected = _rejects(
            lambda: query.get_coverage(
                limit=1,
                continuation=tampered_continuation,
            )
        )
        query_gap_rejected = _rejects(
            lambda: _assert_exact_results(
                expected=snapshot.coverage_records(),
                observed=snapshot.coverage_records()[:-1],
                code="financial_domain_local_proof_query_gap",
            )
        )
        return {
            "managed_asset_drift_rejected": model_input_rejected,
            "materialized_artifact_tamper_rejected": artifact_rejected,
            "persistence_envelope_tamper_rejected": (
                persistence_tamper_rejected
            ),
            "wrong_snapshot_authority_rejected": wrong_key_rejected,
            "wrong_access_scope_rejected": wrong_access_rejected,
            "continuation_tamper_rejected": continuation_rejected,
            "query_gap_rejected": query_gap_rejected,
        }


def _query_evidence(*, query: Any, snapshot: Any) -> dict[str, Any]:
    typed = _all_pages(query.query_typed_records)
    unclassified = _all_pages(query.query_unclassified_records)
    coverage = _all_pages(query.get_coverage)
    provenance = _all_pages(query.get_provenance)
    described = _all_pages(query.describe_domain)

    _assert_exact_results(
        expected=snapshot.typed_records(),
        observed=typed["results"],
        code="financial_domain_local_proof_typed_query_gap",
    )
    _assert_exact_results(
        expected=snapshot.unclassified_records(),
        observed=unclassified["results"],
        code="financial_domain_local_proof_unclassified_query_gap",
    )
    _assert_exact_results(
        expected=snapshot.coverage_records(),
        observed=coverage["results"],
        code="financial_domain_local_proof_coverage_query_gap",
    )
    _assert_exact_results(
        expected=snapshot.provenance_records(),
        observed=provenance["results"],
        code="financial_domain_local_proof_provenance_query_gap",
    )
    _assert_exact_results(
        expected=snapshot.declared_scope()["declared_types"],
        observed=described["results"],
        code="financial_domain_local_proof_catalog_query_gap",
    )
    return {
        "typed_records_total": len(typed["results"]),
        "unclassified_records_total": len(unclassified["results"]),
        "coverage_records_total": len(coverage["results"]),
        "provenance_records_total": len(provenance["results"]),
        "declared_types_total": len(described["results"]),
        "query_pages_total": sum(
            item["pages_total"]
            for item in (
                typed,
                unclassified,
                coverage,
                provenance,
                described,
            )
        ),
        "query_gaps_total": 0,
        "coverage_gaps_total": 0,
        "provenance_gaps_total": 0,
        "query_results_sha256": sha256_json(
            {
                "typed": typed["results"],
                "unclassified": unclassified["results"],
                "coverage": coverage["results"],
                "provenance": provenance["results"],
                "described": described["results"],
            }
        ),
    }


def _all_pages(method: Callable[..., dict[str, Any]]) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    continuation: str | None = None
    pages_total = 0
    matching_total: int | None = None
    while True:
        response = method(limit=1, continuation=continuation)
        pages_total += 1
        current_matching = response["completeness_status"][
            "matching_records_total"
        ]
        if matching_total is None:
            matching_total = current_matching
        if current_matching != matching_total:
            _fail("financial_domain_local_proof_query_count_drift")
        results.extend(response["results"])
        continuation = response["continuation"]
        if continuation is None:
            if (
                response["completeness_status"]["query_result_complete"]
                is not True
                or response["completeness_status"]["page_status"]
                != "complete_final_page"
            ):
                _fail("financial_domain_local_proof_query_not_terminal")
            break
        if pages_total > 256:
            _fail("financial_domain_local_proof_query_unbounded")
    if len(results) != matching_total:
        _fail("financial_domain_local_proof_query_gap")
    return {"results": results, "pages_total": pages_total}


def _assert_exact_results(
    *,
    expected: list[dict[str, Any]],
    observed: list[dict[str, Any]],
    code: str,
) -> None:
    expected_hashes = sorted(sha256_json(item) for item in expected)
    observed_hashes = sorted(sha256_json(item) for item in observed)
    if (
        len(expected_hashes) != len(set(expected_hashes))
        or len(observed_hashes) != len(set(observed_hashes))
        or expected_hashes != observed_hashes
    ):
        _fail(code)


def _rejects(operation: Callable[[], Any]) -> bool:
    try:
        operation()
    except ValueError:
        return True
    return False


def _fail(code: str) -> None:
    raise Gate2FinancialDomainLocalProofError(code)
