"""Inactive compatibility-only full-pipeline proof orchestrator.

Despite its historical ``gate5_`` filename, this module is not a Gate 5 domain
owner. It may compose official owners for exact replay but must not acquire new
source, tax, release or projection meaning.
"""

from __future__ import annotations

import base64
from collections.abc import Callable
import copy
from dataclasses import asdict
import hashlib
from importlib import resources
import json
from typing import Any, Mapping

from .artifact_models import ArtifactAccessContext, RetentionPolicy
from .artifact_resolver import ArtifactResolver
from .canonical_store import CanonicalReaderFactory
from .gate2_handoff import persist_gate1_result
from .gate3_chunk_batch_labeling import (
    GATE3_CHUNK_BATCH_LABELING_RESULT_SCHEMA_VERSION,
    Gate3ChunkBatchLabelingFactory,
)
from .gate3_financial_annotations_persistence import (
    GATE3_FINANCIAL_ANNOTATIONS_ARTIFACT_TYPE,
    Gate3FinancialAnnotationsPersistenceFactory,
)
from .gate4_financial_case_cache import (
    CASE_COMPLETE_FOR_CURRENT_INPUT_SET,
    Gate4FinancialCaseRuntimeFactory,
)
from .gate5_declaration_budget_outcome import (
    GATE5_DECLARATION_BUDGET_DISPOSITION_COMPONENT_SCHEMA_VERSION,
)
from .gate5_declaration_filing_context import (
    GATE5_FILING_AND_PARTY_IDENTITY_COMPONENT_SCHEMA_VERSION,
)
from .gate5_declaration_financial_investment_results import (
    GATE5_FINANCIAL_INVESTMENT_RESULTS_COMPONENT_SCHEMA_VERSION,
)
from .gate5_declaration_income_sources import (
    GATE5_TAXABLE_INCOME_SOURCE_COMPONENT_SCHEMA_VERSION,
)
from .gate5_declaration_right_side_assembly import (
    Gate5DeclarationRightSideAssemblyError,
    Gate5DeclarationRightSideAssemblyRuntimeFactory,
)
from .gate5_declaration_scope_resolution import (
    GATE5_DECLARATION_SCOPE_COMPONENT_EVIDENCE_SCHEMA_VERSION,
    GATE5_DECLARATION_SCOPE_MISSING_SOURCE_INDICATION_SCHEMA_VERSION,
    GATE5_DECLARATION_SCOPE_SCHEMA_VERSION,
    Gate5DeclarationScopeResolutionRuntimeFactory,
)
from .gate5_declaration_semantic_input import (
    Gate5DeclarationSemanticInputRuntimeFactory,
)
from .gate5_declaration_tax_settlement import (
    GATE5_INCOME_GROUP_TAX_RESULTS_COMPONENT_SCHEMA_VERSION,
)
from .gate5_full_declaration_definition import (
    Gate5TrustedFullDeclarationDefinitionAuthorityFactory,
)
from .gate5_full_target_xml_projection import (
    GATE5_CONSUMER_FIRST_XML_PROJECTION_SHA256,
    GATE5_CONSUMER_FIRST_XML_STATUS,
    GATE5_FULL_TARGET_XML_STATUS,
    GATE5_TARGET_MECHANICS_SCHEMA_VERSION,
    GATE5_TARGET_MECHANICS_STATUS,
    Gate5ConsumerFirstXmlProjectionDefinitionAuthorityFactory,
    Gate5FullTargetXmlProjectionDefinitionAuthorityFactory,
    Gate5FullTargetXmlProjectionRuntimeFactory,
)
from .gate5_resolved_declaration_package import (
    Gate5ResolvedDeclarationPackageRuntimeFactory,
)
from .gate5_residency_evidence import gate5_residency_methodology_input
from .gate5_securities_disposal_tax_model import (
    GATE5_SECURITIES_DISPOSAL_OPERATION_TAX_MODEL_SCHEMA_VERSION,
    GATE5_SECURITIES_DISPOSAL_RESOLVED_INPUTS_SCHEMA_VERSION,
    Gate5SecuritiesDisposalTaxModelRuntimeFactory,
)
from .gate5_supplemental_fact import (
    GATE5_SUPPLEMENTAL_FACT_ARTIFACT_TYPE,
    GATE5_SUPPLEMENTAL_FACT_INPUT_SCHEMA_VERSION,
    Gate5SupplementalFactRuntimeFactory,
)
from .gate5_tax_period_category_aggregation import (
    GATE5_TAX_PERIOD_CATEGORY_SCOPE_SCHEMA_VERSION,
    GATE5_TAX_PERIOD_COMPLETENESS_EVIDENCE_SCHEMA_VERSION,
    Gate5TaxPeriodCategoryAggregationRuntimeFactory,
)
from .gate5_trusted_methodology import (
    GATE5_SECURITIES_DISPOSAL_OPERATION_METHODOLOGY_VERSION,
    GATE5_SECURITIES_DISPOSAL_TAX_MODEL_METHODOLOGY_ID,
    GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION,
)
from .inputs import FileInput
from .normalizer import Gate1Normalizer


GATE5_END_TO_END_SUPPLIED_CASE_SCHEMA_VERSION = (
    "broker_reports_gate5_end_to_end_supplied_case_v0"
)
GATE5_END_TO_END_RECEIPT_SCHEMA_VERSION = (
    "broker_reports_gate5_end_to_end_full_target_xml_receipt_v0"
)
GATE5_END_TO_END_STATUS = "END_TO_END_FULL_TARGET_XML_VALID"
GATE5_E2E_SHADOW_RECEIPT_SCHEMA_VERSION = (
    "broker_reports_gate5_e2e_projection_shadow_receipt_v0"
)
GATE5_E2E_SHADOW_PARITY_STATUS = "E2E_SHADOW_PARITY_PROVEN"
GATE5_E2E_SHADOW_PARITY_FAILED_STATUS = "E2E_SHADOW_PARITY_FAILED"
GATE5_E2E_SHADOW_PROFILE_NOT_PROVEN_STATUS = "PROFILE_NOT_PROVEN"
GATE5_E2E_SHADOW_FAILED_STATUS = "E2E_SHADOW_FAILED"
GATE5_DECLARATION_MODEL_AUDIT_RECEIPT_SCHEMA_VERSION = (
    "broker_reports_gate5_declaration_model_assembly_audit_receipt_v0"
)
GATE5_DECLARATION_MODEL_AUDIT_STATUS = "DECLARATION_MODEL_ASSEMBLY_PROVEN"
GATE5_END_TO_END_SUPPLIED_CASE_RESOURCE = "gate5_end_to_end_supplied_case.proof.v0.json"
GATE5_END_TO_END_SUPPLIED_CASE_SHA256 = (
    "84c248c6437924493609b343d8ec619cd08242c9ed8ac13023b817749d0c2a94"
)

FACTORY_REQUIRED = (
    "Gate5EndToEndFullTargetXmlRuntimeFactory.create is the only G5.35 replay entrypoint",
    "Gate1Normalizer.normalize and persist_gate1_result own supplied-source custody",
    "CanonicalReaderFactory.create owns Gate 2 activation and reads",
    "Gate3ChunkBatchLabelingFactory.create and Gate3FinancialAnnotationsPersistenceFactory.create own Gate 3",
    "Gate4FinancialCaseRuntimeFactory.create owns Gate 4",
    "existing Gate 5 factories own every tax, declaration and target result",
)
FORBIDDEN = (
    "prebuilt CanonicalArtifact, FinancialAnnotations, Gate4 fact, Tax Model, Scope Receipt, Resolved Package or Semantic Input",
    "direct SQL, manual XML, target literals, case-time LLM tax authority or second pipeline",
    "case facts in Python constants, Projection Definition or target fixture",
)

_ROOT_KEYS = frozenset(
    {
        "schema_version",
        "case_fact_set_id",
        "case_fact_set_version",
        "binding",
        "supplied_source",
        "scope",
        "residency_evidence",
        "supplemental_money",
        "securities_disposal",
        "tax_period_category",
        "income_group",
        "settlement",
        "filing_and_party_identity",
        "taxable_income_source",
        "budget_disposition",
        "financial_investment",
        "critical_provenance",
    }
)
_BINDING_KEYS = frozenset(
    {
        "authenticated_user_ref",
        "case_id",
        "workspace_model_id",
        "normalization_run_ref",
        "taxpayer_scope_ref",
        "tax_period",
        "synthetic_proof_evidence",
        "real_user_fact",
    }
)
_SOURCE_KEYS = frozenset(
    {
        "private_ref",
        "filename",
        "mime_type",
        "source_kind",
        "content_sha256",
        "custody",
    }
)
_SOURCE_KEYSETS = frozenset(
    {
        _SOURCE_KEYS | {"content_utf8"},
        _SOURCE_KEYS | {"content_base64"},
    }
)
_CUSTODY_KEYS = frozenset(
    {
        "openwebui_file_id",
        "authenticated_owner_ref",
        "original_custody",
        "synthetic_proof_evidence",
        "real_user_fact",
    }
)


class Gate5EndToEndFullTargetXmlError(ValueError):
    def __init__(
        self,
        code: str,
        field: str = "",
        *,
        blocker: Mapping[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.field = field
        self.blocker = copy.deepcopy(dict(blocker or {}))
        super().__init__(code if not field else f"{code}:{field}")


class Gate5EndToEndSuppliedCaseAuthorityFactory:
    @classmethod
    def create(cls) -> "Gate5EndToEndSuppliedCaseAuthority":
        return Gate5EndToEndSuppliedCaseAuthority()


class Gate5EndToEndSuppliedCaseAuthority:
    def load(self) -> dict[str, Any]:
        raw = (
            resources.files("broker_reports_gate1")
            .joinpath(GATE5_END_TO_END_SUPPLIED_CASE_RESOURCE)
            .read_bytes()
        )
        if hashlib.sha256(raw).hexdigest() != GATE5_END_TO_END_SUPPLIED_CASE_SHA256:
            _fail("gate5_e2e_supplied_case_hash_mismatch")
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise Gate5EndToEndFullTargetXmlError(
                "gate5_e2e_supplied_case_invalid"
            ) from exc
        _validate_proof_input(value)
        return copy.deepcopy(value)


class Gate5EndToEndFullTargetXmlRuntimeFactory:
    def __init__(
        self,
        *,
        store: Any,
        read_enabled: bool,
        retention_policy: RetentionPolicy,
        gate3_model_client: Any,
        gate3_model_id: str,
        gate3_provider_profile_id: str,
    ) -> None:
        self._store = store
        self._read_enabled = read_enabled
        self._retention_policy = retention_policy
        self._gate3_model_client = gate3_model_client
        self._gate3_model_id = gate3_model_id
        self._gate3_provider_profile_id = gate3_provider_profile_id

    def create(self) -> "Gate5EndToEndFullTargetXmlRuntime":
        if not isinstance(self._retention_policy, RetentionPolicy):
            _fail("gate5_e2e_retention_policy_required")
        if not self._read_enabled:
            _fail("gate5_e2e_read_disabled")
        if self._gate3_model_client is None:
            _fail("gate5_e2e_gate3_model_client_required")
        if not _nonempty(self._gate3_model_id) or not _nonempty(
            self._gate3_provider_profile_id
        ):
            _fail("gate5_e2e_gate3_model_identity_required")
        return Gate5EndToEndFullTargetXmlRuntime(
            store=self._store,
            retention_policy=self._retention_policy,
            gate3_model_client=self._gate3_model_client,
            gate3_model_id=self._gate3_model_id,
            gate3_provider_profile_id=self._gate3_provider_profile_id,
        )


class Gate5EndToEndFullTargetXmlRuntime:
    def __init__(
        self,
        *,
        store: Any,
        retention_policy: RetentionPolicy,
        gate3_model_client: Any,
        gate3_model_id: str,
        gate3_provider_profile_id: str,
    ) -> None:
        self._store = store
        self._retention_policy = retention_policy
        self._gate3_model_client = gate3_model_client
        self._gate3_model_id = gate3_model_id
        self._gate3_provider_profile_id = gate3_provider_profile_id

    async def run(
        self,
        *,
        proof_input: dict[str, Any],
        context: ArtifactAccessContext,
        _projection_shadow_receipt_sink: (
            Callable[[dict[str, Any]], None] | None
        ) = None,
        _declaration_model_audit_receipt_sink: (
            Callable[[dict[str, Any]], None] | None
        ) = None,
    ) -> dict[str, Any]:
        """Return the legacy result shape; an opt-in sink receives safe shadow proof."""

        value = _validate_proof_input(proof_input)
        source, source_bytes = _source(value, context=context)
        _validate_context(value, context=context, source=source)

        file_input = FileInput.from_bytes(
            private_ref=source["private_ref"],
            filename=source["filename"],
            content=source_bytes,
            mime_type=source["mime_type"],
            source_kind=source["source_kind"],
        )
        gate1_result = Gate1Normalizer().normalize(
            [file_input],
            input_context={
                "canonical_gate2_write_enabled": True,
                "canonical_gate2_read_enabled": True,
                "normalizer_version": "g535-end-to-end-proof-v0",
            },
        )
        if gate1_result.package["normalization_run"]["run_id"] != (
            context.normalization_run_id
        ):
            _fail("gate5_e2e_normalization_run_binding_mismatch")
        if gate1_result.package["normalization_run"]["run_status"] != "completed":
            _fail("gate5_e2e_gate1_incomplete")
        manifest = persist_gate1_result(
            store=self._store,
            result=gate1_result,
            context=context,
            retention_policy=self._retention_policy,
            source_file_refs=[copy.deepcopy(source["custody"])],
        )

        canonical_refs = manifest.artifact_refs_by_type.get(
            "broker_reports_canonical_artifact_v1", []
        )
        if len(canonical_refs) != 1:
            _fail("gate5_e2e_gate2_canonical_missing")
        reader = CanonicalReaderFactory(
            store=self._store,
            read_enabled=True,
        ).create()
        canonical = reader.read_envelope(canonical_refs[0], context)
        reader.activate(
            canonical_version_id=canonical.canonical_version_id,
            expected_previous_version_id=None,
            context=context,
            actor="g535-end-to-end-proof",
            reason="source-to-target official-boundary replay",
        )

        gate3_result = await Gate3ChunkBatchLabelingFactory(
            store=self._store,
            read_enabled=True,
            model_client=self._gate3_model_client,
            model_id=self._gate3_model_id,
        ).create(document_id=canonical.document_id, context=context)
        if gate3_result.document_status != "complete" or (
            gate3_result.merged_output is None
        ):
            error_code = next(
                (
                    item.error_code
                    for item in gate3_result.outcomes
                    if item.error_code is not None
                ),
                "gate5_e2e_gate3_incomplete",
            )
            raise Gate5EndToEndFullTargetXmlError(
                "gate5_e2e_gate3_incomplete",
                blocker={"upstream_code": error_code},
            )
        gate3_document_result = _gate3_document_result(gate3_result)
        gate3_record = (
            Gate3FinancialAnnotationsPersistenceFactory(
                store=self._store,
                read_enabled=True,
            )
            .create()
            .save(
                document_id=canonical.document_id,
                context=context,
                validated_document_result=gate3_document_result,
                provider_profile_id=self._gate3_provider_profile_id,
            )
        )

        return self.continue_from_validated_gate3(
            proof_input=value,
            context=context,
            financial_annotations_artifact_id=gate3_record.artifact_id,
            _projection_shadow_receipt_sink=_projection_shadow_receipt_sink,
            _declaration_model_audit_receipt_sink=(
                _declaration_model_audit_receipt_sink
            ),
        )

    def continue_from_validated_gate3(
        self,
        *,
        proof_input: dict[str, Any],
        context: ArtifactAccessContext,
        financial_annotations_artifact_id: str,
        _projection_shadow_receipt_sink: (
            Callable[[dict[str, Any]], None] | None
        ) = None,
        _declaration_model_audit_receipt_sink: (
            Callable[[dict[str, Any]], None] | None
        ) = None,
    ) -> dict[str, Any]:
        """Run the unchanged Gate 4 -> target tail from a persisted Gate 3 sidecar."""

        value = _validate_proof_input(proof_input)
        source, source_bytes = _source(value, context=context)
        _validate_context(value, context=context, source=source)
        if not _nonempty(financial_annotations_artifact_id):
            _fail("gate5_e2e_gate3_artifact_id_required")

        gate3_persistence = Gate3FinancialAnnotationsPersistenceFactory(
            store=self._store,
            read_enabled=True,
        ).create()
        gate3_payload = gate3_persistence.read(
            artifact_id=financial_annotations_artifact_id,
            context=context,
        )
        gate3_record = ArtifactResolver(self._store).resolve_record(
            financial_annotations_artifact_id,
            context,
        )
        if gate3_record.artifact_type != GATE3_FINANCIAL_ANNOTATIONS_ARTIFACT_TYPE:
            _fail("gate5_e2e_validated_gate3_sidecar_required")
        canonical_binding = gate3_payload["canonical_binding"]
        canonical_version = self._store.get_canonical_version(
            context=context,
            canonical_version_id=canonical_binding["canonical_version_id"],
        )
        if (
            canonical_version.document_id != canonical_binding["document_id"]
            or not canonical_version.manifest_ref
        ):
            _fail("gate5_e2e_gate3_canonical_binding_mismatch")
        canonical = (
            CanonicalReaderFactory(
                store=self._store,
                read_enabled=True,
            )
            .create()
            .read_envelope(canonical_version.manifest_ref, context)
        )

        gate4_runtime = Gate4FinancialCaseRuntimeFactory(
            store=self._store,
            read_enabled=True,
        ).create()
        financial_case = gate4_runtime.rebuild_case(context=context)
        if financial_case.status != CASE_COMPLETE_FOR_CURRENT_INPUT_SET:
            _fail("gate5_e2e_gate4_case_incomplete")
        disposal_facts = [
            item
            for item in financial_case.facts
            if item.get("financial_type") == "SECURITY_DISPOSAL"
        ]
        if len(disposal_facts) != 1:
            _fail("gate5_e2e_representative_disposal_fact_required")
        if disposal_facts[0].get("status") != "role_complete":
            self._raise_missing_source(
                fact=disposal_facts[0],
                proof_input=value,
                context=context,
            )

        right_side = Gate5DeclarationRightSideAssemblyRuntimeFactory.create()
        try:
            residency_classification = right_side.residency_classification(value)
        except Gate5DeclarationRightSideAssemblyError as exc:
            _fail(exc.code, exc.field)
        operation, category = self._tax_models(
            proof_input=value,
            context=context,
            residency_classification=residency_classification,
        )
        try:
            tax_base = right_side.income_group_tax_base(
                category=category,
                residency=residency_classification,
                inputs=value,
            )
        except Gate5DeclarationRightSideAssemblyError as exc:
            _fail(exc.code, exc.field)
        definition_ref = (
            Gate5TrustedFullDeclarationDefinitionAuthorityFactory.create().publication()
        )
        scope_runtime = Gate5DeclarationScopeResolutionRuntimeFactory(
            store=self._store,
            read_enabled=True,
            retention_policy=self._retention_policy,
        ).create()
        scope = _scope(value)
        operation_evidence = _component_evidence(
            GATE5_SECURITIES_DISPOSAL_OPERATION_TAX_MODEL_SCHEMA_VERSION,
            operation,
        )

        provisional_scope = scope_runtime.resolve(
            definition_ref=definition_ref,
            scope=scope,
            typed_component_evidence=[operation_evidence],
            assertion_refs=[],
            context=context,
        )
        scope_binding = provisional_scope["scope_binding"]
        settlement = _right_side_result(
            right_side.settlement_component,
            inputs=value,
            scope_binding=scope_binding,
            tax_base=tax_base,
        )
        income_source = _right_side_result(
            right_side.income_source_component,
            inputs=value,
            scope_binding=scope_binding,
            settlement=settlement,
        )
        scope_receipt = scope_runtime.resolve(
            definition_ref=definition_ref,
            scope=scope,
            typed_component_evidence=[
                operation_evidence,
                _component_evidence(
                    GATE5_TAXABLE_INCOME_SOURCE_COMPONENT_SCHEMA_VERSION,
                    income_source,
                ),
            ],
            assertion_refs=[],
            context=context,
        )
        scope_binding = scope_receipt["scope_binding"]

        filing = _right_side_result(
            right_side.filing_component,
            inputs=value,
            scope_binding=scope_binding,
            residency=residency_classification,
        )
        budget = _right_side_result(
            right_side.budget_component,
            inputs=value,
            scope_binding=scope_binding,
            filing=filing,
            settlement=settlement,
        )
        financial = _right_side_result(
            right_side.financial_component,
            inputs=value,
            scope_binding=scope_binding,
            category=category,
        )
        components = [
            operation_evidence,
            _component_evidence(
                GATE5_FILING_AND_PARTY_IDENTITY_COMPONENT_SCHEMA_VERSION,
                filing,
            ),
            _component_evidence(
                GATE5_DECLARATION_BUDGET_DISPOSITION_COMPONENT_SCHEMA_VERSION,
                budget,
            ),
            _component_evidence(
                GATE5_INCOME_GROUP_TAX_RESULTS_COMPONENT_SCHEMA_VERSION,
                settlement,
            ),
            _component_evidence(
                GATE5_TAXABLE_INCOME_SOURCE_COMPONENT_SCHEMA_VERSION,
                income_source,
            ),
            _component_evidence(
                GATE5_FINANCIAL_INVESTMENT_RESULTS_COMPONENT_SCHEMA_VERSION,
                financial,
            ),
        ]
        package = (
            Gate5ResolvedDeclarationPackageRuntimeFactory(
                store=self._store,
                read_enabled=True,
                retention_policy=self._retention_policy,
            )
            .create()
            .assemble(
                definition_ref=definition_ref,
                scope_receipt=scope_receipt,
                typed_component_snapshots=components,
                context=context,
            )
        )
        semantic_input = Gate5DeclarationSemanticInputRuntimeFactory.create().compile(
            package=package
        )
        projected = Gate5FullTargetXmlProjectionRuntimeFactory.create().project(
            semantic_input=semantic_input
        )
        if projected["receipt"]["status"] != GATE5_FULL_TARGET_XML_STATUS:
            _fail("gate5_e2e_full_target_projection_incomplete")

        receipt = self._receipt(
            proof_input=value,
            context=context,
            source_bytes=source_bytes,
            canonical=canonical,
            gate3_record=gate3_record,
            gate3_payload=gate3_payload,
            financial_case=financial_case,
            residency_classification=residency_classification,
            operation=operation,
            category=category,
            tax_base=tax_base,
            components=components,
            definition_ref=definition_ref,
            scope_receipt=scope_receipt,
            package=package,
            semantic_input=semantic_input,
            projected=projected,
        )
        self.validate_receipt(receipt)
        legacy_result = {
            "status": GATE5_END_TO_END_STATUS,
            "xml_bytes": projected["xml_bytes"],
            "semantic_input": semantic_input,
            "receipt": receipt,
        }
        if _declaration_model_audit_receipt_sink is not None:
            audit_receipt = self._declaration_model_audit_receipt(
                proof_input=value,
                package=package,
                legacy_projected=projected,
                residency_classification=residency_classification,
            )
            _declaration_model_audit_receipt_sink(copy.deepcopy(audit_receipt))
        if _projection_shadow_receipt_sink is not None:
            shadow_receipt = self._projection_shadow_receipt(
                proof_input=value,
                package=package,
                legacy_projected=projected,
            )
            try:
                _projection_shadow_receipt_sink(copy.deepcopy(shadow_receipt))
            except Exception:
                # The non-authoritative control channel cannot affect legacy delivery.
                pass
        return legacy_result

    @staticmethod
    def _declaration_model_audit_receipt(
        *,
        proof_input: dict[str, Any],
        package: dict[str, Any],
        legacy_projected: dict[str, Any],
        residency_classification: dict[str, Any],
    ) -> dict[str, Any]:
        semantic_runtime = Gate5DeclarationSemanticInputRuntimeFactory.create()
        candidate = semantic_runtime.compile_declaration_value_candidate(
            package=package
        )
        released = semantic_runtime.release_declaration_value_candidate(
            package=package,
            candidate=candidate,
        )
        projection_input = semantic_runtime.prepare_released_projection_input(
            package=package,
            released=released,
        )
        target_mechanics = _shadow_target_mechanics(proof_input)
        projected = (
            Gate5FullTargetXmlProjectionRuntimeFactory.create().project_released(
                released_values=projection_input,
                target_mechanics=target_mechanics,
            )
        )
        if projected["receipt"]["status"] != GATE5_CONSUMER_FIRST_XML_STATUS:
            _fail("gate5_e2e_declaration_model_consumer_target_invalid")
        if projected["xml_bytes"] != legacy_projected["xml_bytes"]:
            _fail("gate5_e2e_declaration_model_target_parity_failed")
        definition = (
            Gate5ConsumerFirstXmlProjectionDefinitionAuthorityFactory.create().resolve()
        )
        trace = _declaration_value_traceability_audit(
            proof_input=proof_input,
            released=released,
            residency_classification=residency_classification,
            target_mechanics=target_mechanics,
            projection_definition=definition,
            projected=projected,
        )
        accounting = released["release_receipt"]["evidence_accounting"]
        income_source_component = next(
            item
            for item in package["component_snapshots"]
            if item["domain_id"] == "taxable_income_by_source"
            and item["root_coverage"] == "exact_root_domain"
        )
        source_obligations = copy.deepcopy(
            income_source_component["snapshot"]["obligation_resolutions"]
        )
        receipt_base = {
            "schema_version": (GATE5_DECLARATION_MODEL_AUDIT_RECEIPT_SCHEMA_VERSION),
            "status": GATE5_DECLARATION_MODEL_AUDIT_STATUS,
            "blockers": [],
            "terminals": [
                "DECLARATION_CONSUMER_MODEL_PROVEN",
                "DECLARATION_SEMANTIC_MODEL_COMPLETE",
                "END_TO_END_DECLARATION_ASSEMBLY_PROVEN",
                "DECLARATION_VALUE_TRACEABILITY_PROVEN",
                "CROSS_DOMAIN_DECLARATION_CONSISTENCY_PROVEN",
            ],
            "profile": {
                "form": "3-NDFL",
                "tax_period": "2025",
                "scope": "bounded_russian_source_broker_securities_payable",
                "controlled_evidence": True,
                "real_taxpayer_evidence": False,
            },
            "assembly": {
                "semantic_bypass": False,
                "release_required": True,
                "consumer_target_status": projected["receipt"]["status"],
                "legacy_target_byte_identical": True,
                "official_xsd_valid": projected["receipt"]["conformance_proof"][
                    "xsd_valid"
                ],
                "xml_sha256": projected["receipt"]["xml_binding"]["xml_sha256"],
            },
            "consumer_inventory": {
                "emitted_value_count": len(trace),
                "released_semantic_value_count": accounting["declared_value_count"],
                "released_semantic_values_consumed": sum(
                    item["semantic_value_path"] is not None for item in trace
                ),
                "official_constant_count": sum(
                    item["origin_kind"] == "OFFICIAL_TARGET_CONSTANT" for item in trace
                ),
                "target_mechanics_count": sum(
                    item["origin_kind"] == "FILING_TARGET_MECHANICS" for item in trace
                ),
                "unconsumed_released_semantic_value_count": 0,
                "unknown_origin_count": sum(item["origin_count"] < 1 for item in trace),
                "unowned_value_count": sum(not item["owner_factory"] for item in trace),
            },
            "projection_boundary": {
                "allowed_operations": [
                    "MAP",
                    "FORMAT",
                    "ENCODE",
                    "REPEAT",
                    "PLACE",
                    "SERIALIZE",
                    "VALIDATE",
                ],
                "interpretation_authority": False,
                "projection_definition_sha256": (
                    GATE5_CONSUMER_FIRST_XML_PROJECTION_SHA256
                ),
            },
            "conditional_scope": {
                "source_obligation_resolutions": source_obligations,
                "foreign_target_mapping_count": sum(
                    "ДоходИстИно" in item["target"] for item in trace
                ),
                "unrelated_conditional_domains_activated": 0,
            },
            "value_traceability": trace,
            "audit_envelope": {
                "is_projection_input": False,
                "target_depends_on_audit_metadata": False,
                "release_receipt_sha256": released["release_receipt"]["receipt_sha256"],
                "evidence_binding_manifest_sha256": accounting[
                    "evidence_binding_manifest_sha256"
                ],
            },
            "legal_methodology_gaps_remain": [
                "ambiguous_security_disposal_source_classification",
                "partial_acquisition_commission_allocation",
                "non_rub_intermediate_precision_and_rounding",
                "treaty_specific_foreign_tax_credit_limit",
            ],
            "safety": {
                "product_activation": False,
                "persisted": False,
                "downloadable": False,
                "controlled_case_called_real": False,
            },
        }
        return {**receipt_base, "receipt_sha256": _sha256(receipt_base)}

    def _projection_shadow_receipt(
        self,
        *,
        proof_input: dict[str, Any],
        package: dict[str, Any],
        legacy_projected: dict[str, Any],
    ) -> dict[str, Any]:
        package_sha256 = package["package_sha256"]
        legacy_package_sha256 = legacy_projected["receipt"]["semantic_input_binding"][
            "package_sha256"
        ]
        package_binding = {
            "resolved_package_sha256": package_sha256,
            "legacy_package_sha256": legacy_package_sha256,
            "shadow_release_package_sha256": package_sha256,
            "same_resolved_package": package_sha256 == legacy_package_sha256,
        }
        profile = {
            "profile_id": "payable_one_allocation",
            "proof_boundary": "G5.39AG",
        }
        safety = {
            "legacy_product_authority": True,
            "shadow_returned_to_user": False,
            "shadow_persisted": False,
            "shadow_downloadable": False,
            "candidate_disposition": "DISCARDED",
        }
        rollback = {
            "action": "stop_shadow_receipt_sink_invocation",
            "data_migration_required": False,
            "tax_replay_required": False,
        }
        try:
            semantic_runtime = Gate5DeclarationSemanticInputRuntimeFactory.create()
            candidate = semantic_runtime.compile_declaration_value_candidate(
                package=package
            )
            released = semantic_runtime.release_declaration_value_candidate(
                package=package,
                candidate=candidate,
            )
            released_values = semantic_runtime.prepare_released_projection_input(
                package=package,
                released=released,
            )
            target_mechanics = _shadow_target_mechanics(proof_input)
            shadow_projected = (
                Gate5FullTargetXmlProjectionRuntimeFactory.create().project_released(
                    released_values=released_values,
                    target_mechanics=target_mechanics,
                )
            )

            legacy_mappings = _shadow_mapping_projection(legacy_projected)
            shadow_mappings = _shadow_mapping_projection(shadow_projected)
            parity = {
                "mapping_id_target_value_hashes_equal": (
                    legacy_mappings == shadow_mappings
                ),
                "official_xsd_conformance_equal": (
                    legacy_projected["receipt"]["conformance_proof"]
                    == shadow_projected["receipt"]["conformance_proof"]
                ),
                "xml_binding_equal": (
                    legacy_projected["receipt"]["xml_binding"]
                    == shadow_projected["receipt"]["xml_binding"]
                ),
                "xml_bytes_equal": (
                    legacy_projected["xml_bytes"] == shadow_projected["xml_bytes"]
                ),
            }
            failed_checks = [key for key, value in parity.items() if not value]
            status = (
                GATE5_E2E_SHADOW_PARITY_STATUS
                if package_binding["same_resolved_package"] and not failed_checks
                else GATE5_E2E_SHADOW_PARITY_FAILED_STATUS
            )
            blockers = []
            if status != GATE5_E2E_SHADOW_PARITY_STATUS:
                blockers = [
                    {
                        "code": "gate5_e2e_shadow_parity_mismatch",
                        "failed_checks": (
                            failed_checks
                            if package_binding["same_resolved_package"]
                            else ["same_resolved_package"] + failed_checks
                        ),
                    }
                ]
            receipt_base = {
                "schema_version": GATE5_E2E_SHADOW_RECEIPT_SCHEMA_VERSION,
                "status": status,
                "blockers": blockers,
                "profile": profile,
                "package_binding": package_binding,
                "released_value_binding": copy.deepcopy(
                    shadow_projected["receipt"]["released_value_binding"]
                ),
                "parity_evidence": {
                    "legacy_mapping_occurrences_total": len(legacy_mappings),
                    "shadow_mapping_occurrences_total": len(shadow_mappings),
                    "legacy_mapping_projection_sha256": _sha256(legacy_mappings),
                    "shadow_mapping_projection_sha256": _sha256(shadow_mappings),
                    "legacy_xml_sha256": legacy_projected["receipt"]["xml_binding"][
                        "xml_sha256"
                    ],
                    "shadow_xml_sha256": shadow_projected["receipt"]["xml_binding"][
                        "xml_sha256"
                    ],
                },
                "parity": parity,
                "safety": safety,
                "rollback": rollback,
            }
        except Exception as exc:
            code = str(getattr(exc, "code", "gate5_e2e_shadow_candidate_failed"))
            field = str(getattr(exc, "field", "") or "")
            status = (
                GATE5_E2E_SHADOW_PROFILE_NOT_PROVEN_STATUS
                if code == "gate5_consumer_first_projection_profile_unproven"
                else GATE5_E2E_SHADOW_FAILED_STATUS
            )
            blocker = {"code": code}
            if field:
                blocker["field"] = field
            receipt_base = {
                "schema_version": GATE5_E2E_SHADOW_RECEIPT_SCHEMA_VERSION,
                "status": status,
                "blockers": [blocker],
                "profile": profile,
                "package_binding": package_binding,
                "parity": {
                    "mapping_id_target_value_hashes_equal": False,
                    "official_xsd_conformance_equal": False,
                    "xml_binding_equal": False,
                    "xml_bytes_equal": False,
                },
                "safety": safety,
                "rollback": rollback,
            }
        return {**receipt_base, "receipt_sha256": _sha256(receipt_base)}

    def _tax_models(
        self,
        *,
        proof_input: dict[str, Any],
        context: ArtifactAccessContext,
        residency_classification: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        try:
            supplemental = proof_input["supplemental_money"]
            resolved_inputs = copy.deepcopy(proof_input["securities_disposal"])
            category_facts = proof_input["tax_period_category"]
        except KeyError as exc:
            _missing_case_fact(exc)
        tax_context = resolved_inputs.get("tax_context")
        if not isinstance(tax_context, dict) or "residency" in tax_context:
            _fail("gate5_e2e_direct_taxpayer_status_forbidden", "tax_context.residency")
        tax_context["residency"] = gate5_residency_methodology_input(
            residency_classification,
            input_channel="minimal_tax_context",
        )
        if not isinstance(supplemental, list):
            _fail("gate5_e2e_case_fact_invalid", "supplemental_money")
        supplemental_runtime = Gate5SupplementalFactRuntimeFactory(
            store=self._store,
            retention_policy=self._retention_policy,
        ).create()
        resolver = ArtifactResolver(self._store)
        for item in supplemental:
            if not self._exact_supplemental_fact_exists(
                resolver=resolver,
                item=item,
                context=context,
            ):
                supplemental_runtime.put(
                    supplemental_input={
                        "schema_version": GATE5_SUPPLEMENTAL_FACT_INPUT_SCHEMA_VERSION,
                        **copy.deepcopy(item),
                    },
                    context=context,
                )
        tax_runtime = Gate5SecuritiesDisposalTaxModelRuntimeFactory(
            store=self._store,
            read_enabled=True,
            retention_policy=self._retention_policy,
        ).create()
        tax_methodology_ref = {
            "schema_version": GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION,
            "methodology_id": GATE5_SECURITIES_DISPOSAL_TAX_MODEL_METHODOLOGY_ID,
            "methodology_version": (
                GATE5_SECURITIES_DISPOSAL_OPERATION_METHODOLOGY_VERSION
            ),
        }
        tax_resolved_inputs = {
            "schema_version": GATE5_SECURITIES_DISPOSAL_RESOLVED_INPUTS_SCHEMA_VERSION,
            **copy.deepcopy(resolved_inputs),
        }
        operation_result = tax_runtime.run_operation(
            methodology_ref=tax_methodology_ref,
            resolved_inputs=tax_resolved_inputs,
            context=context,
        )
        operation = operation_result["tax_model"]

        category_runtime = Gate5TaxPeriodCategoryAggregationRuntimeFactory.create()
        binding = proof_input["binding"]
        category_scope = {
            "schema_version": GATE5_TAX_PERIOD_CATEGORY_SCOPE_SCHEMA_VERSION,
            "scope_ref": _required(category_facts, "scope_ref"),
            "taxpayer_scope_ref": binding["taxpayer_scope_ref"],
            "tax_period": binding["tax_period"],
            "operation_category": _required(category_facts, "operation_category"),
        }
        members = [
            {
                "operation_ref": _required(category_facts, "operation_ref"),
                "source_scope_ref": context.case_id,
                "tax_model": copy.deepcopy(operation),
            }
        ]
        category_binding = category_runtime.describe_scope(
            scope=category_scope,
            members=members,
        )
        category = category_runtime.run(
            scope=category_scope,
            members=members,
            completeness_evidence={
                "schema_version": GATE5_TAX_PERIOD_COMPLETENESS_EVIDENCE_SCHEMA_VERSION,
                "status": "asserted_complete",
                "coverage_kind": "all_operations_in_taxpayer_category_period_scope",
                "scope_binding_sha256": category_binding["scope_binding_sha256"],
                "provenance": copy.deepcopy(
                    _required(category_facts, "completeness_provenance")
                ),
            },
        )["category_tax_model"]

        return operation, category

    @staticmethod
    def _exact_supplemental_fact_exists(
        *,
        resolver: ArtifactResolver,
        item: dict[str, Any],
        context: ArtifactAccessContext,
    ) -> bool:
        expected = {
            key: copy.deepcopy(item.get(key))
            for key in ("requirement_ref", "subject_ref", "fact_key", "value")
        }
        for record in resolver.catalog_run(context):
            if record.artifact_type != GATE5_SUPPLEMENTAL_FACT_ARTIFACT_TYPE:
                continue
            payload = resolver.resolve(record.artifact_id, context)["payload"]
            if not isinstance(payload, dict):
                continue
            actual = {key: payload.get(key) for key in expected}
            if actual == expected:
                return True
        return False

    def _raise_missing_source(
        self,
        *,
        fact: dict[str, Any],
        proof_input: dict[str, Any],
        context: ArtifactAccessContext,
    ) -> None:
        missing_roles = sorted(
            item["role"]
            for item in fact["roles"]
            if item.get("status") == "missing" and item.get("requirement") == "required"
        )
        indication = {
            "schema_version": (
                GATE5_DECLARATION_SCOPE_MISSING_SOURCE_INDICATION_SCHEMA_VERSION
            ),
            "component_contract_id": (
                GATE5_SECURITIES_DISPOSAL_OPERATION_TAX_MODEL_SCHEMA_VERSION
            ),
            "source_fact_id": fact["fact_id"],
            "source_fact_sha256": _sha256(fact),
            "missing_role_names": missing_roles,
        }
        definition_ref = (
            Gate5TrustedFullDeclarationDefinitionAuthorityFactory.create().publication()
        )
        receipt = (
            Gate5DeclarationScopeResolutionRuntimeFactory(
                store=self._store,
                read_enabled=True,
                retention_policy=self._retention_policy,
            )
            .create()
            .resolve(
                definition_ref=definition_ref,
                scope=_scope(proof_input),
                typed_component_evidence=[],
                assertion_refs=[],
                missing_source_indications=[indication],
                context=context,
            )
        )
        request = next(
            (
                item
                for item in receipt["missing_source_requests"]
                if item["source_fact_id"] == fact["fact_id"]
            ),
            None,
        )
        raise Gate5EndToEndFullTargetXmlError(
            "gate5_e2e_supplied_source_incomplete",
            blocker={
                "stage": "gate4_financial_case",
                "missing_role_names": missing_roles,
                "acquisition_request": request,
            },
        )

    def _receipt(
        self,
        *,
        proof_input: dict[str, Any],
        context: ArtifactAccessContext,
        source_bytes: bytes,
        canonical: Any,
        gate3_record: Any,
        gate3_payload: dict[str, Any],
        financial_case: Any,
        residency_classification: dict[str, Any],
        operation: dict[str, Any],
        category: dict[str, Any],
        tax_base: dict[str, Any],
        components: list[dict[str, Any]],
        definition_ref: dict[str, Any],
        scope_receipt: dict[str, Any],
        package: dict[str, Any],
        semantic_input: dict[str, Any],
        projected: dict[str, Any],
    ) -> dict[str, Any]:
        source_record = ArtifactResolver(self._store).resolve_record(
            canonical.artifact["source"]["source_artifact_ref"],
            context,
        )
        custody_projection = {
            "artifact_type": source_record.artifact_type,
            "user_id": source_record.user_id,
            "case_id": source_record.case_id,
            "normalization_run_id": source_record.normalization_run_id,
            "document_id": source_record.document_id,
            "source_file_ref": source_record.source_file_ref,
            "source_sha256": canonical.artifact["source"]["source_sha256"],
        }
        projection_definition = (
            Gate5FullTargetXmlProjectionDefinitionAuthorityFactory.create().resolve()
        )
        stages = [
            ("original_supplied_source", hashlib.sha256(source_bytes).hexdigest()),
            ("gate1_custody_artifact", _sha256(custody_projection)),
            ("gate2_canonical_artifact", canonical.canonical_root_sha256),
            ("gate3_financial_annotations", _sha256(gate3_payload)),
            ("gate4_financial_case", _sha256(asdict(financial_case))),
            (
                "gate5_residency_classification",
                _sha256(residency_classification),
            ),
            ("gate5_operation_tax_model", _sha256(operation)),
            ("gate5_category_tax_model", _sha256(category)),
            ("gate5_income_group_tax_base", _sha256(tax_base)),
            (
                "gate5_trusted_components",
                _sha256([item["component_sha256"] for item in components]),
            ),
            ("full_declaration_definition", definition_ref["definition_sha256"]),
            ("declaration_scope_receipt", scope_receipt["receipt_sha256"]),
            ("resolved_declaration_package", package["package_sha256"]),
            ("declaration_semantic_input", semantic_input["semantic_input_sha256"]),
            (
                "projection_definition",
                projected["receipt"]["projection_definition_binding"][
                    "projection_definition_sha256"
                ],
            ),
            ("full_target_xml", projected["receipt"]["xml_binding"]["xml_sha256"]),
            (
                "official_xsd",
                projected["receipt"]["conformance_proof"]["xsd_sha256"],
            ),
        ]
        chain = _hash_chain(stages)
        result = {
            "schema_version": GATE5_END_TO_END_RECEIPT_SCHEMA_VERSION,
            "status": GATE5_END_TO_END_STATUS,
            "blockers": [],
            "case_binding": {
                "case_fact_set_id": proof_input["case_fact_set_id"],
                "case_fact_set_version": proof_input["case_fact_set_version"],
                "case_fact_set_sha256": _sha256(proof_input),
                "user_id": context.user_id,
                "case_id": context.case_id,
                "normalization_run_id": context.normalization_run_id,
                "tax_period": proof_input["binding"]["tax_period"],
                "synthetic_proof_evidence": True,
                "real_user_fact": False,
            },
            "gate_boundaries": {
                "gate1": "Gate1Normalizer.normalize+persist_gate1_result",
                "gate2": "CanonicalReaderFactory.create",
                "gate3": (
                    "Gate3ChunkBatchLabelingFactory.create+"
                    "Gate3FinancialAnnotationsPersistenceFactory.create"
                ),
                "gate4": "Gate4FinancialCaseRuntimeFactory.create",
                "gate5": "existing_trusted_gate5_factories",
                "target": "Gate5FullTargetXmlProjectionRuntimeFactory.create",
            },
            "gate3_boundary_evidence": {
                "artifact_id": gate3_record.artifact_id,
                "model_id": self._gate3_model_id,
                "provider_profile_id": self._gate3_provider_profile_id,
                "proposal_validated_by_gate3": True,
            },
            "hash_chain": chain,
            "hash_chain_terminal_sha256": chain[-1]["chain_sha256"],
            "trusted_tax_component_hashes": {
                "residency_classification_sha256": _sha256(residency_classification),
                "operation_tax_model_sha256": _sha256(operation),
                "category_tax_model_sha256": _sha256(category),
                "income_group_tax_base_sha256": _sha256(tax_base),
                "component_sha256s": [item["component_sha256"] for item in components],
            },
            "determinism": {
                "bound_input_sha256": _sha256(proof_input),
                "semantic_result_sha256": _sha256(
                    _deterministic_semantic_projection(semantic_input)
                ),
                "xml_sha256": projected["receipt"]["xml_binding"]["xml_sha256"],
                "excluded_external_identities": [
                    "artifact_id",
                    "canonical_version_id",
                    "created_at",
                ],
            },
            "critical_provenance_audit": _critical_provenance_audit(
                proof_input=proof_input,
                semantic_input=semantic_input,
                projection_definition=projection_definition,
            ),
            "target_result": copy.deepcopy(projected["receipt"]),
        }
        result["receipt_sha256"] = _sha256(result)
        return result

    @staticmethod
    def validate_receipt(value: Any) -> None:
        if (
            not isinstance(value, dict)
            or value.get("schema_version") != GATE5_END_TO_END_RECEIPT_SCHEMA_VERSION
            or value.get("status") != GATE5_END_TO_END_STATUS
            or value.get("blockers") != []
        ):
            _fail("gate5_e2e_receipt_invalid")
        chain = value.get("hash_chain")
        if not isinstance(chain, list) or not chain:
            _fail("gate5_e2e_receipt_hash_chain_invalid")
        previous = None
        for row in chain:
            if (
                not isinstance(row, dict)
                or set(row)
                != {"stage", "artifact_sha256", "previous_sha256", "chain_sha256"}
                or row["previous_sha256"] != previous
                or row["chain_sha256"]
                != _sha256(
                    {
                        "stage": row["stage"],
                        "artifact_sha256": row["artifact_sha256"],
                        "previous_sha256": previous,
                    }
                )
            ):
                _fail("gate5_e2e_receipt_hash_chain_invalid")
            previous = row["chain_sha256"]
        if value.get("hash_chain_terminal_sha256") != previous:
            _fail("gate5_e2e_receipt_hash_chain_invalid")
        receipt_hash = value.get("receipt_sha256")
        unsigned = {key: item for key, item in value.items() if key != "receipt_sha256"}
        if receipt_hash != _sha256(unsigned):
            _fail("gate5_e2e_receipt_hash_invalid")


def _validate_proof_input(value: Any) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or frozenset(value) not in {_ROOT_KEYS, _ROOT_KEYS - {"residency_evidence"}}
        or value.get("schema_version") != GATE5_END_TO_END_SUPPLIED_CASE_SCHEMA_VERSION
        or not _nonempty(value.get("case_fact_set_id"))
        or not _nonempty(value.get("case_fact_set_version"))
    ):
        _fail("gate5_e2e_supplied_case_invalid")
    binding = value.get("binding")
    source = value.get("supplied_source")
    if not isinstance(binding, dict) or set(binding) != _BINDING_KEYS:
        _fail("gate5_e2e_case_binding_invalid")
    if (
        binding.get("synthetic_proof_evidence") is not True
        or binding.get("real_user_fact") is not False
    ):
        _fail("gate5_e2e_case_provenance_invalid")
    if not isinstance(source, dict) or frozenset(source) not in _SOURCE_KEYSETS:
        _fail("gate5_e2e_supplied_source_invalid")
    custody = source.get("custody")
    if (
        not isinstance(custody, dict)
        or set(custody) != _CUSTODY_KEYS
        or custody.get("original_custody") is not True
        or custody.get("synthetic_proof_evidence") is not True
        or custody.get("real_user_fact") is not False
    ):
        _fail("gate5_e2e_source_custody_invalid")
    return copy.deepcopy(value)


def _source(
    proof_input: dict[str, Any],
    *,
    context: ArtifactAccessContext,
) -> tuple[dict[str, Any], bytes]:
    source = proof_input["supplied_source"]
    if source["custody"]["authenticated_owner_ref"] != context.user_id:
        _fail("gate5_e2e_source_owner_mismatch")
    if "content_utf8" in source:
        try:
            content = source["content_utf8"].encode("utf-8")
        except (AttributeError, UnicodeEncodeError) as exc:
            raise Gate5EndToEndFullTargetXmlError(
                "gate5_e2e_supplied_source_invalid"
            ) from exc
    else:
        encoded = source.get("content_base64")
        try:
            content = base64.b64decode(encoded, validate=True)
        except (TypeError, ValueError) as exc:
            raise Gate5EndToEndFullTargetXmlError(
                "gate5_e2e_supplied_source_invalid"
            ) from exc
        if base64.b64encode(content).decode("ascii") != encoded:
            _fail("gate5_e2e_supplied_source_invalid")
    if hashlib.sha256(content).hexdigest() != source["content_sha256"]:
        _fail("gate5_e2e_supplied_source_hash_mismatch")
    return source, content


def _validate_context(
    proof_input: dict[str, Any],
    *,
    context: ArtifactAccessContext,
    source: dict[str, Any],
) -> None:
    if not isinstance(context, ArtifactAccessContext) or not context.allow_private:
        _fail("gate5_e2e_authenticated_context_required")
    binding = proof_input["binding"]
    expected = {
        "authenticated_user_ref": context.user_id,
        "case_id": context.case_id,
        "workspace_model_id": context.workspace_model_id,
        "normalization_run_ref": context.normalization_run_id,
    }
    if any(binding.get(key) != item for key, item in expected.items()):
        _fail("gate5_e2e_case_binding_mismatch")
    if source.get("source_kind") != "synthetic":
        _fail("gate5_e2e_representative_source_kind_unsupported")


def _scope(proof_input: dict[str, Any]) -> dict[str, Any]:
    facts = proof_input.get("scope")
    if not isinstance(facts, dict):
        _fail("gate5_e2e_case_fact_missing", "scope")
    return {
        "schema_version": GATE5_DECLARATION_SCOPE_SCHEMA_VERSION,
        "scope_ref": _required(facts, "scope_ref"),
        "taxpayer_scope_ref": _required(facts, "taxpayer_scope_ref"),
        "tax_period": _required(facts, "tax_period"),
    }


def _gate3_document_result(value: Any) -> dict[str, Any]:
    return {
        "schema_version": GATE3_CHUNK_BATCH_LABELING_RESULT_SCHEMA_VERSION,
        "semantic_scope": copy.deepcopy(value.semantic_scope),
        "selected_chunk_ordinals": list(value.selected_chunk_ordinals),
        "selection_mode": value.selection_mode,
        "document_status": value.document_status,
        "metrics": copy.deepcopy(value.metrics),
        "merged_output": copy.deepcopy(value.merged_output),
    }


def _component_evidence(contract_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": GATE5_DECLARATION_SCOPE_COMPONENT_EVIDENCE_SCHEMA_VERSION,
        "component_contract_id": contract_id,
        "component_sha256": _sha256(payload),
        "payload": copy.deepcopy(payload),
    }


def _synthetic_provenance(source_ref: str, input_channel: str) -> dict[str, Any]:
    return {
        "source_kind": "synthetic_proof_evidence",
        "source_ref": source_ref,
        "input_channel": input_channel,
        "real_user_fact": False,
    }


def _hash_chain(stages: list[tuple[str, str]]) -> list[dict[str, Any]]:
    rows = []
    previous = None
    for stage, artifact_hash in stages:
        row = {
            "stage": stage,
            "artifact_sha256": artifact_hash,
            "previous_sha256": previous,
        }
        row["chain_sha256"] = _sha256(row)
        rows.append(row)
        previous = row["chain_sha256"]
    return rows


def _critical_provenance_audit(
    *,
    proof_input: dict[str, Any],
    semantic_input: dict[str, Any],
    projection_definition: dict[str, Any],
) -> list[dict[str, Any]]:
    mappings = _projection_mappings(projection_definition["tree"])
    components = {
        row["domain_id"]: row["typed_components"][0]
        for row in semantic_input["domains"]
        if row["typed_components"]
    }
    result = []
    for binding in proof_input["critical_provenance"]:
        origin_value = _path(proof_input, binding["case_fact_path"])
        matches = [
            item
            for item in mappings
            if item["projection_source"] == binding["projection_source"]
        ]
        if len(matches) != 1:
            _fail("gate5_e2e_critical_projection_mapping_invalid", binding["fact_key"])
        component = components.get(binding["domain_id"])
        if component is None:
            _fail("gate5_e2e_critical_component_missing", binding["domain_id"])
        value = _path(
            component["semantic_payload"],
            binding["semantic_value_path"],
        )
        result.append(
            {
                "fact_key": binding["fact_key"],
                "value": copy.deepcopy(value),
                "value_sha256": _sha256(value),
                "semantic_origin": binding["nature"],
                "case_fact_path": binding["case_fact_path"],
                "origin_value_sha256": _sha256(origin_value),
                "trusted_owner": binding["trusted_owner"],
                "sealed_component": {
                    "domain_id": binding["domain_id"],
                    "source_component_contract_id": component[
                        "source_component_contract_id"
                    ],
                    "source_component_sha256": component["source_component_sha256"],
                    "semantic_payload_sha256": component["semantic_payload_sha256"],
                },
                "semantic_input_source": binding["projection_source"],
                "projection_mapping": matches[0],
            }
        )
    return result


def _declaration_value_traceability_audit(
    *,
    proof_input: dict[str, Any],
    released: dict[str, Any],
    residency_classification: dict[str, Any],
    target_mechanics: dict[str, Any],
    projection_definition: dict[str, Any],
    projected: dict[str, Any],
) -> list[dict[str, Any]]:
    definition_mappings = {
        item["mapping_id"]: item
        for item in _projection_mapping_definitions(projection_definition["tree"])
    }
    bindings = {
        item["declared_value_path"]: item
        for item in released["release_receipt"]["evidence_accounting"]["bindings"]
    }
    occurrences = projected["receipt"]["semantic_mapping_proof"]["mappings"]
    if len(definition_mappings) != len(occurrences):
        _fail("gate5_e2e_declaration_trace_mapping_accounting_invalid")
    consumed_semantic_paths: list[str] = []
    rows = []
    for occurrence in occurrences:
        mapping = definition_mappings.get(occurrence["mapping_id"])
        if mapping is None:
            _fail(
                "gate5_e2e_declaration_trace_mapping_unknown",
                occurrence["mapping_id"],
            )
        source = occurrence.get("resolved_source")
        semantic_path = None
        if mapping["transform"]["kind"] == "constant":
            origin_kind = "OFFICIAL_TARGET_CONSTANT"
            owner = (
                "Gate5ConsumerFirstXmlProjectionDefinitionAuthorityFactory."
                "create.resolve"
            )
            origin_binding = {
                "authority_contract_id": (
                    projection_definition["projection_id"]
                    + "@"
                    + projection_definition["projection_version"]
                ),
                "authority_sha256": GATE5_CONSUMER_FIRST_XML_PROJECTION_SHA256,
                "direct_evidence_sha256": _sha256(
                    {
                        "mapping_id": mapping["mapping_id"],
                        "transform": mapping["transform"],
                        "evidence_refs": mapping["evidence_refs"],
                    }
                ),
            }
        elif source == "$root.target_mechanics.electronic_file_id":
            electronic_file_id = target_mechanics["electronic_file_id"]
            if occurrence["source_value_sha256"] != _sha256(electronic_file_id):
                _fail("gate5_e2e_declaration_trace_target_mechanics_mismatch")
            origin_kind = "FILING_TARGET_MECHANICS"
            owner = "Gate5FilingAndPartyIdentityRuntimeFactory.create"
            origin_binding = {
                "authority_contract_id": GATE5_TARGET_MECHANICS_SCHEMA_VERSION,
                "authority_sha256": target_mechanics["target_mechanics_sha256"],
                "direct_evidence_sha256": _sha256(
                    proof_input["filing_and_party_identity"]["filing_instance"][
                        "declaration_instance_ref"
                    ]
                ),
            }
        elif isinstance(source, str) and source.startswith("$root.declaration_values"):
            semantic_path = "$" + source[len("$root.declaration_values") :]
            binding = bindings.get(semantic_path)
            if (
                binding is None
                or binding["declared_value_sha256"] != occurrence["source_value_sha256"]
            ):
                _fail(
                    "gate5_e2e_declaration_trace_semantic_binding_missing",
                    semantic_path,
                )
            consumed_semantic_paths.append(semantic_path)
            if semantic_path == "$.taxpayer.period_status":
                if (
                    residency_classification.get("period_status")
                    != released["declaration_values"]["taxpayer"]["period_status"]
                    or residency_classification.get("calculation_authority")
                    != "Gate5ResidencyEvidenceRuntimeFactory.create"
                    or not isinstance(
                        residency_classification.get("methodology_binding"), dict
                    )
                ):
                    _fail("gate5_e2e_declaration_trace_residency_binding_invalid")
                methodology = residency_classification["methodology_binding"]
                origin_kind = "DERIVED"
                owner = residency_classification["calculation_authority"]
                origin_binding = {
                    "authority_contract_id": (
                        methodology["methodology_id"]
                        + "@"
                        + methodology["methodology_version"]
                    ),
                    "authority_sha256": methodology["resource_sha256"],
                    "calculation_authority_sha256": _sha256(methodology),
                    "replayable_input_snapshot_sha256": (
                        residency_classification["evidence_sha256"]
                    ),
                    "rule_id": methodology["rule_id"],
                }
            else:
                origin_kind = binding["origin_kind"]
                owner = binding["owner_factory"]
                origin_binding = {
                    key: copy.deepcopy(item)
                    for key, item in binding.items()
                    if key
                    not in {
                        "declared_value_path",
                        "declared_value_sha256",
                        "owner_factory",
                        "origin_kind",
                    }
                }
        else:
            _fail(
                "gate5_e2e_declaration_trace_source_unknown",
                str(source),
            )
        rows.append(
            {
                "mapping_id": occurrence["mapping_id"],
                "target": occurrence["target"],
                "target_value_sha256": occurrence["target_value_sha256"],
                "projection_source": occurrence["source"],
                "resolved_projection_source": source,
                "projection_transform": mapping["transform"]["kind"],
                "semantic_value_path": semantic_path,
                "semantic_value_sha256": occurrence["source_value_sha256"],
                "origin_kind": origin_kind,
                "owner_factory": owner,
                "origin_binding": origin_binding,
                "origin_count": 1,
                "methodology_or_direct_binding_known": True,
            }
        )
    if len(consumed_semantic_paths) != len(set(consumed_semantic_paths)) or set(
        consumed_semantic_paths
    ) != set(bindings):
        _fail("gate5_e2e_declaration_trace_semantic_accounting_invalid")
    return rows


def _projection_mapping_definitions(
    node: dict[str, Any],
) -> list[dict[str, Any]]:
    result = [copy.deepcopy(item) for item in node.get("attributes", [])]
    text_mapping = node.get("text_mapping")
    if text_mapping is not None:
        result.append(copy.deepcopy(text_mapping))
    for child in node.get("children", []):
        result.extend(_projection_mapping_definitions(child))
    return result


def _projection_mappings(
    node: dict[str, Any],
    parent_path: str = "",
) -> list[dict[str, str]]:
    path = f"{parent_path}/{node['element']}" if parent_path else node["element"]
    result = [
        {
            "mapping_id": item["mapping_id"],
            "projection_source": item["source"],
            "xml_target": f"{path}/@{item['name']}",
        }
        for item in node.get("attributes", [])
        if item.get("source") is not None
    ]
    text_mapping = node.get("text_mapping")
    if text_mapping is not None and text_mapping.get("source") is not None:
        result.append(
            {
                "mapping_id": text_mapping["mapping_id"],
                "projection_source": text_mapping["source"],
                "xml_target": f"{path}/text()",
            }
        )
    for child in node.get("children", []):
        result.extend(_projection_mappings(child, path))
    return result


def _deterministic_semantic_projection(value: dict[str, Any]) -> dict[str, Any]:
    return {
        "declaration_semantics": copy.deepcopy(value["declaration_semantics"]),
        "domains": [
            {
                "domain_id": row["domain_id"],
                "state": row["state"],
                "semantic_payloads": [
                    copy.deepcopy(item["semantic_payload"])
                    for item in row["typed_components"]
                ],
            }
            for row in value["domains"]
        ],
    }


def _path(value: dict[str, Any], path: str) -> Any:
    current: Any = value
    for part in path.split("."):
        if isinstance(current, list) and part.isdigit():
            index = int(part)
            if index >= len(current):
                _fail("gate5_e2e_case_fact_missing", path)
            current = current[index]
            continue
        if not isinstance(current, dict) or part not in current:
            _fail("gate5_e2e_case_fact_missing", path)
        current = current[part]
    return current


def _right_side_result(
    call: Callable[..., dict[str, Any]],
    **kwargs: Any,
) -> dict[str, Any]:
    try:
        return call(**kwargs)
    except Gate5DeclarationRightSideAssemblyError as exc:
        _fail(exc.code, exc.field)


def _required(value: Mapping[str, Any], key: str) -> Any:
    try:
        result = value[key]
    except (KeyError, TypeError) as exc:
        _missing_case_fact(exc, field=key)
    if result is None or result == "":
        _fail("gate5_e2e_case_fact_missing", key)
    return result


def _missing_case_fact(exc: Exception, *, field: str = "") -> None:
    name = field
    if not name and isinstance(exc, KeyError) and exc.args:
        name = str(exc.args[0])
    raise Gate5EndToEndFullTargetXmlError(
        "gate5_e2e_case_fact_missing",
        name,
        blocker={
            "stage": "trusted_case_fact_boundary",
            "missing_fact": name,
            "action": "provide_mandatory_case_fact",
        },
    ) from exc


def _missing_residency_evidence(reason: str) -> None:
    raise Gate5EndToEndFullTargetXmlError(
        "gate5_e2e_residency_evidence_insufficient",
        "residency_evidence",
        blocker={
            "stage": "residency_methodology_input",
            "gap_class": "MISSING_EVIDENCE",
            "missing_fact": "residency_evidence",
            "reason": reason,
            "action": "provide_complete_residency_presence_and_absence_evidence",
        },
    )


def _shadow_target_mechanics(proof_input: dict[str, Any]) -> dict[str, Any]:
    electronic_file_id = proof_input["filing_and_party_identity"]["filing_instance"][
        "declaration_instance_ref"
    ]
    base = {
        "schema_version": GATE5_TARGET_MECHANICS_SCHEMA_VERSION,
        "status": GATE5_TARGET_MECHANICS_STATUS,
        "electronic_file_id": electronic_file_id,
    }
    return {**base, "target_mechanics_sha256": _sha256(base)}


def _shadow_mapping_projection(projected: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "mapping_id": item["mapping_id"],
            "target": item["target"],
            "target_value_sha256": item["target_value_sha256"],
        }
        for item in projected["receipt"]["semantic_mapping_proof"]["mappings"]
    ]


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value) and value == value.strip()


def _sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _fail(code: str, field: str = "") -> None:
    raise Gate5EndToEndFullTargetXmlError(code, field)


__all__ = [
    "FACTORY_REQUIRED",
    "FORBIDDEN",
    "GATE5_END_TO_END_RECEIPT_SCHEMA_VERSION",
    "GATE5_END_TO_END_STATUS",
    "GATE5_END_TO_END_SUPPLIED_CASE_RESOURCE",
    "GATE5_END_TO_END_SUPPLIED_CASE_SCHEMA_VERSION",
    "GATE5_END_TO_END_SUPPLIED_CASE_SHA256",
    "GATE5_E2E_SHADOW_FAILED_STATUS",
    "GATE5_E2E_SHADOW_PARITY_FAILED_STATUS",
    "GATE5_E2E_SHADOW_PARITY_STATUS",
    "GATE5_E2E_SHADOW_PROFILE_NOT_PROVEN_STATUS",
    "GATE5_E2E_SHADOW_RECEIPT_SCHEMA_VERSION",
    "Gate5EndToEndFullTargetXmlError",
    "Gate5EndToEndFullTargetXmlRuntime",
    "Gate5EndToEndFullTargetXmlRuntimeFactory",
    "Gate5EndToEndSuppliedCaseAuthority",
    "Gate5EndToEndSuppliedCaseAuthorityFactory",
]
