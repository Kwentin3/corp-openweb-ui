"""Single owner for Definition-driven Declaration scope decisions."""

from __future__ import annotations

import copy
import hashlib
import json
import re
from typing import Any

from .artifact_models import (
    ArtifactAccessContext,
    ArtifactRecord,
    ArtifactStorePort,
    RetentionPolicy,
    new_artifact_id,
)
from .artifact_resolver import ArtifactResolver
from .gate4_financial_case_cache import Gate4FinancialCaseRuntimeFactory
from .gate4_ordinary_trade_candidate import (
    Gate4OrdinaryTradeCandidateRuntimeFactory,
)
from .ordinary_trade_tax_model_bridge import (
    validate_ordinary_trade_taxpayer_binding,
)
from .gate5_full_declaration_definition import (
    GATE5_FULL_DECLARATION_DEFINITION_PUBLICATION_SCHEMA_VERSION,
    Gate5TrustedFullDeclarationDefinitionAuthority,
    Gate5TrustedFullDeclarationDefinitionAuthorityFactory,
)
from .gate5_securities_disposal_tax_model import (
    GATE5_SECURITIES_DISPOSAL_OPERATION_TAX_MODEL_SCHEMA_VERSION,
)
from .gate5_tax_period_category_aggregation import (
    Gate5TaxPeriodCategoryAggregationRuntime,
    Gate5TaxPeriodCategoryAggregationRuntimeFactory,
)
from .gate5_declaration_income_sources import (
    GATE5_TAXABLE_INCOME_SOURCE_COMPONENT_FAMILY,
    GATE5_TAXABLE_INCOME_SOURCE_COMPONENT_SCHEMA_VERSION,
    GATE5_TAXABLE_INCOME_SOURCE_OBLIGATION_REFS,
    Gate5DeclarationIncomeSourcesRuntime,
    Gate5DeclarationIncomeSourcesRuntimeFactory,
)
from .gate5_real_tax_case_assembly import (
    GATE5_REAL_TAX_CASE_ASSEMBLY_SCHEMA_VERSION,
    Gate5RealTaxCaseAssemblyRuntime,
    Gate5RealTaxCaseAssemblyRuntimeFactory,
)


GATE5_DECLARATION_SCOPE_SCHEMA_VERSION = "broker_reports_gate5_declaration_scope_v0"
GATE5_DECLARATION_SCOPE_COMPONENT_EVIDENCE_SCHEMA_VERSION = (
    "broker_reports_gate5_declaration_scope_component_evidence_v0"
)
GATE5_DECLARATION_SCOPE_RECEIPT_SCHEMA_VERSION = (
    "broker_reports_gate5_declaration_scope_resolution_receipt_v1"
)
GATE5_CURRENT_FACT_DECLARATION_SCOPE_RECEIPT_SCHEMA_VERSION = (
    "broker_reports_gate5_current_fact_declaration_scope_resolution_receipt_v0"
)
GATE5_DECLARATION_SCOPE_MISSING_SOURCE_INDICATION_SCHEMA_VERSION = (
    "broker_reports_gate5_supplied_case_missing_source_indication_v1"
)
GATE5_DECLARATION_SCOPE_MISSING_SOURCE_REQUEST_SCHEMA_VERSION = (
    "broker_reports_gate5_supplied_case_missing_source_request_v1"
)
GATE5_DECLARATION_SCOPE_SEMANTICS = {
    "kind": "supplied_case_evidence_set",
    "activation_rule": "positive_or_missing_source_evidence_only",
    "real_world_taxpayer_absence_asserted": False,
}
GATE5_DECLARATION_SCOPE_HUMAN_REQUEST_SCHEMA_VERSION = (
    "broker_reports_gate5_declaration_scope_human_request_v0"
)
GATE5_DECLARATION_SCOPE_HUMAN_ANSWER_SCHEMA_VERSION = (
    "broker_reports_gate5_declaration_scope_human_answer_v0"
)
GATE5_DECLARATION_SCOPE_ASSERTION_SCHEMA_VERSION = (
    "broker_reports_gate5_declaration_scope_assertion_v0"
)
GATE5_DECLARATION_SCOPE_ASSERTION_ARTIFACT_TYPE = (
    "broker_reports_gate5_declaration_scope_assertion_v0"
)
GATE5_DECLARATION_SCOPE_ACTIVATION_SCHEMA_VERSION = (
    "broker_reports_gate5_declaration_scope_activation_v0"
)
GATE5_USER_INTENT_SCHEMA_VERSION = "broker_reports_gate5_user_intent_v0"
GATE5_DECLARATION_SCOPE_ACTIVATION_TERMINAL = "DECLARATION_SCOPE_ACTIVATION_PROVEN"

FACTORY_REQUIRED = (
    "Gate5DeclarationScopeResolutionRuntimeFactory.create",
    "Gate5TrustedFullDeclarationDefinitionAuthorityFactory.create owns domains and policies",
    "Gate4FinancialCaseRuntimeFactory.create owns every Financial Case read",
    "Gate5TaxPeriodCategoryAggregationRuntimeFactory.create validates typed evidence",
    "Gate5DeclarationIncomeSourcesRuntimeFactory.create validates exact taxable-source evidence",
    "ArtifactResolver.resolve enforces assertion access and lifecycle",
    "Gate5DeclarationScopeActivationRuntimeFactory.create owns supplied-case "
    "intent/evidence activation in this same scope domain",
    "Gate5DeclarationScopeResolutionRuntimeFactory.create_current_source_fact_scope "
    "is the additive active Fact v2 reader",
    "Gate4OrdinaryTradeCandidateRuntimeFactory.create owns every current Fact v2 read",
)
FORBIDDEN = (
    "handwritten Declaration domain or applicability-policy list",
    "direct Gate 4 SQL, cache schema, CanonicalArtifact or Gate 3 target read",
    "current-input absence as negative taxpayer-scope evidence or real-world claim",
    "LLM applicability authority, rules engine, questionnaire or new base primitive",
    "last-write-wins conflict resolution or Declaration Model projection",
)

_DEFINITION_BINDING_KEYS = frozenset(
    {
        "schema_version",
        "status",
        "definition_id",
        "definition_version",
        "definition_sha256",
        "validation_sha256",
        "obligation_package_sha256",
    }
)
_ACTIVATION_INTENT_KEYS = frozenset(
    {"schema_version", "form", "tax_period", "task", "domains"}
)
_ACTIVATION_SUPPORTED_TASK = "prepare_tax_declaration"
_ACTIVATION_SUPPORTED_DOMAIN_INTENTS = {"broker_securities_income"}
_ACTIVATION_SECURITY_TYPES = {"SECURITY_PURCHASE", "SECURITY_DISPOSAL"}
_ACTIVATION_INCOME_TYPES = {
    "COUPON_INCOME",
    "DIVIDEND_INCOME",
    "INTEREST_INCOME",
    "SECURITIES_LENDING_INCOME",
    "SECURITY_DISPOSAL",
}
_ACTIVATION_SECURITIES_OBLIGATION_REFS = {
    "obl_securities_and_derivatives_results",
}
_ACTIVATION_INCOME_OBLIGATION_REFS = {
    "obl_income_group_tax_base_results",
    "obl_income_group_tax_settlement_results",
    "obl_russian_source_taxable_income",
    "obl_foreign_source_taxable_income_and_foreign_tax",
}
_ACTIVATION_BROKER_INTENT_OBLIGATION_REFS = {
    *_ACTIVATION_SECURITIES_OBLIGATION_REFS,
    *_ACTIVATION_INCOME_OBLIGATION_REFS,
}
_SCOPE_INPUT_KEYS = frozenset(
    {
        "schema_version",
        "scope_ref",
        "taxpayer_scope_ref",
        "tax_period",
    }
)
_SCOPE_BINDING_KEYS = frozenset(
    {
        *_SCOPE_INPUT_KEYS,
        "authenticated_user_ref",
        "case_id",
        "normalization_run_ref",
        "scope_binding_sha256",
    }
)
_COMPONENT_EVIDENCE_KEYS = frozenset(
    {"schema_version", "component_contract_id", "component_sha256", "payload"}
)
_MISSING_SOURCE_INDICATION_KEYS = frozenset(
    {
        "schema_version",
        "component_contract_id",
        "source_fact_id",
        "source_fact_sha256",
        "missing_role_names",
    }
)
_MISSING_SOURCE_REQUEST_KEYS = frozenset(
    {
        "schema_version",
        "domain_id",
        "component_contract_id",
        "source_fact_id",
        "source_fact_sha256",
        "scope_binding_sha256",
        "missing_role_names",
        "reason",
        "action",
        "indication_sha256",
        "request_sha256",
    }
)
_ASSERTION_KEYS = frozenset(
    {
        "schema_version",
        "assertion_ref",
        "definition_binding",
        "scope_binding",
        "domain_id",
        "policy",
        "answer",
        "polarity",
        "request_sha256",
        "provenance",
    }
)
_EVIDENCE_BINDING_KEYS = frozenset(
    {
        "authority_class",
        "evidence_kind",
        "evidence_ref",
        "evidence_sha256",
        "polarity",
    }
)
_DOMAIN_ROW_KEYS = frozenset(
    {
        "domain_id",
        "mode",
        "policy",
        "state",
        "resolution_route",
        "evidence_bindings",
        "decision_sha256",
    }
)
_HUMAN_REQUEST_KEYS = frozenset(
    {
        "schema_version",
        "domain_id",
        "policy",
        "definition_sha256",
        "scope_binding_sha256",
        "question_context",
        "answer_contract",
        "request_sha256",
    }
)
_RECEIPT_KEYS = frozenset(
    {
        "schema_version",
        "status",
        "definition_binding",
        "scope_binding",
        "gate4_binding",
        "scope_semantics",
        "domains",
        "unresolved_domains",
        "conflicts",
        "missing_source_requests",
        "human_residual",
        "first_downstream_blocker",
        "receipt_sha256",
    }
)
_CURRENT_FACT_RECEIPT_KEYS = frozenset({*_RECEIPT_KEYS, "taxpayer_binding"})
_GATE4_BINDING_KEYS = frozenset(
    {
        "boundary",
        "status",
        "gate3_case_status",
        "sources",
        "facts",
        "binding_sha256",
    }
)
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_ARTIFACT_REF = re.compile(r"^art_[A-Za-z0-9_-]{32}$")
_STATES = {
    "APPLICABLE",
    "NOT_APPLICABLE",
    "NOT_ACTIVATED_FOR_SUPPLIED_CASE",
    "UNRESOLVED",
    "CONFLICT",
}
_ROUTES = {"RESOLVE", "ACQUIRE", "EXECUTE"}
_ANSWERS = {"yes", "no"}
_HUMAN_POLARITY = {
    "elective_claim": {"yes": "positive", "no": "negative"},
    "factual_occurrence": {"yes": "positive", "no": "negative"},
}


class Gate5DeclarationScopeResolutionError(ValueError):
    def __init__(self, code: str, field: str = "") -> None:
        self.code = code
        self.field = field
        super().__init__(code if not field else f"{code}:{field}")


class Gate5DeclarationScopeResolutionRuntimeFactory:
    def __init__(
        self,
        *,
        store: ArtifactStorePort,
        read_enabled: bool,
        retention_policy: RetentionPolicy,
    ) -> None:
        self._store = store
        self._read_enabled = read_enabled
        self._retention_policy = retention_policy

    def create(self) -> "Gate5DeclarationScopeResolutionRuntime":
        if not isinstance(self._retention_policy, RetentionPolicy):
            _fail("gate5_declaration_scope_retention_policy_required")
        return self._create_with_gate4(
            gate4_runtime=Gate4FinancialCaseRuntimeFactory(
                store=self._store,
                read_enabled=self._read_enabled,
            ).create(),
            current_source_fact=False,
        )

    def create_current_source_fact_scope(
        self,
    ) -> "Gate5DeclarationScopeResolutionRuntime":
        """Create the additive active-Fact-v2 reader; historical create stays exact."""

        if not isinstance(self._retention_policy, RetentionPolicy):
            _fail("gate5_declaration_scope_retention_policy_required")
        return self._create_with_gate4(
            gate4_runtime=Gate4OrdinaryTradeCandidateRuntimeFactory(
                store=self._store,
                read_enabled=self._read_enabled,
            ).create(),
            current_source_fact=True,
        )

    def _create_with_gate4(
        self,
        *,
        gate4_runtime: Any,
        current_source_fact: bool,
    ) -> "Gate5DeclarationScopeResolutionRuntime":
        return Gate5DeclarationScopeResolutionRuntime(
            store=self._store,
            retention_policy=self._retention_policy,
            resolver=ArtifactResolver(self._store),
            definition_authority=(
                Gate5TrustedFullDeclarationDefinitionAuthorityFactory.create()
            ),
            gate4_runtime=gate4_runtime,
            component_runtime=(
                Gate5TaxPeriodCategoryAggregationRuntimeFactory.create()
            ),
            income_sources_runtime=Gate5DeclarationIncomeSourcesRuntimeFactory.create(),
            current_source_fact=current_source_fact,
        )


class Gate5DeclarationScopeResolutionRuntime:
    def __init__(
        self,
        *,
        store: ArtifactStorePort,
        retention_policy: RetentionPolicy,
        resolver: ArtifactResolver,
        definition_authority: Gate5TrustedFullDeclarationDefinitionAuthority,
        gate4_runtime: Any,
        component_runtime: Gate5TaxPeriodCategoryAggregationRuntime,
        income_sources_runtime: Gate5DeclarationIncomeSourcesRuntime,
        current_source_fact: bool = False,
    ) -> None:
        self._store = store
        self._retention_policy = retention_policy
        self._resolver = resolver
        self._definition_authority = definition_authority
        self._gate4_runtime = gate4_runtime
        self._component_runtime = component_runtime
        self._income_sources_runtime = income_sources_runtime
        self._current_source_fact = current_source_fact

    def resolve(
        self,
        *,
        definition_ref: dict[str, Any],
        scope: dict[str, Any],
        typed_component_evidence: list[dict[str, Any]],
        assertion_refs: list[str],
        context: ArtifactAccessContext,
        missing_source_indications: list[dict[str, Any]] | None = None,
        taxpayer_binding: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        publication = _definition_binding(definition_ref)
        contract = self._definition_authority.resolve_for_scope(
            publication["definition_id"],
            publication["definition_version"],
            publication["definition_sha256"],
        )
        if contract["publication"] != publication:
            _fail("gate5_declaration_scope_definition_binding_invalid")
        definition = contract["definition"]
        policies = _policy_rows(contract["applicability_audit"], definition)
        scope_binding = _scope_binding(
            scope,
            context=context,
            definition_tax_period=definition["declaration_identity"]["tax_period"],
        )
        if self._current_source_fact:
            gate4_facts = tuple(self._gate4_runtime.list_facts(context=context))
            gate4_binding = _current_fact_binding(gate4_facts)
        else:
            financial_case = self._gate4_runtime.read_case(context=context)
            gate4_facts = tuple(financial_case.facts)
            gate4_binding = _gate4_binding(financial_case)
        validated_taxpayer_binding = None
        if self._current_source_fact:
            validated_taxpayer_binding = validate_ordinary_trade_taxpayer_binding(
                taxpayer_binding
            )
            if validated_taxpayer_binding is None:
                _fail("gate5_declaration_scope_taxpayer_binding_invalid")
            if (
                validated_taxpayer_binding["taxpayer_scope_ref"]
                != scope_binding["taxpayer_scope_ref"]
            ):
                _fail("gate5_declaration_scope_taxpayer_binding_mismatch")
        component_bindings = self._component_bindings(
            typed_component_evidence,
            definition=definition,
            policies=policies,
            scope=scope_binding,
            gate4_facts=gate4_facts,
            taxpayer_binding=validated_taxpayer_binding,
        )
        assertion_bindings = self._assertion_bindings(
            assertion_refs,
            definition=definition,
            definition_binding=publication,
            policies=policies,
            scope=scope_binding,
            context=context,
        )
        missing_source_bindings, missing_source_requests = (
            self._missing_source_bindings(
                missing_source_indications or [],
                definition=definition,
                scope=scope_binding,
                gate4_facts=gate4_facts,
            )
        )
        evidence_by_domain: dict[str, list[dict[str, str]]] = {}
        for binding in [
            *component_bindings,
            *assertion_bindings,
            *missing_source_bindings,
        ]:
            evidence_by_domain.setdefault(binding.pop("domain_id"), []).append(binding)

        rows: list[dict[str, Any]] = []
        for domain in definition["domains"]:
            policy = policies[domain["domain_id"]]
            evidence = sorted(
                evidence_by_domain.get(domain["domain_id"], []),
                key=lambda item: (
                    item["authority_class"],
                    item["evidence_ref"],
                    item["polarity"],
                ),
            )
            if policy["mode"] == "always":
                evidence = [
                    {
                        "authority_class": "trusted_declaration_definition",
                        "evidence_kind": "definition_mandatory",
                        "evidence_ref": domain["domain_id"],
                        "evidence_sha256": publication["definition_sha256"],
                        "polarity": "positive",
                    }
                ]
                state = "APPLICABLE"
                route = "RESOLVE"
            else:
                positive = any(item["polarity"] == "positive" for item in evidence)
                negative = any(item["polarity"] == "negative" for item in evidence)
                blocking = any(item["polarity"] == "blocking" for item in evidence)
                if positive and negative:
                    state = "CONFLICT"
                elif blocking:
                    state = "UNRESOLVED"
                elif positive:
                    state = "APPLICABLE"
                elif negative:
                    state = "NOT_APPLICABLE"
                else:
                    state = "NOT_ACTIVATED_FOR_SUPPLIED_CASE"
                route = (
                    "ACQUIRE"
                    if blocking
                    else "EXECUTE"
                    if any(
                        item["authority_class"] == "validated_typed_component"
                        for item in evidence
                    )
                    else "ACQUIRE"
                    if evidence
                    else "RESOLVE"
                )
            row = {
                "domain_id": domain["domain_id"],
                "mode": policy["mode"],
                "policy": policy["policy"],
                "state": state,
                "resolution_route": route,
                "evidence_bindings": evidence,
            }
            rows.append({**row, "decision_sha256": _canonical_sha256(row)})

        unresolved = [row["domain_id"] for row in rows if row["state"] == "UNRESOLVED"]
        conflicts = [row["domain_id"] for row in rows if row["state"] == "CONFLICT"]
        human_residual = (
            None
            if conflicts
            else _first_human_residual(
                rows=rows,
                definition=definition,
                policies=policies,
                definition_binding=publication,
                scope=scope_binding,
            )
        )
        base = {
            "schema_version": (
                GATE5_CURRENT_FACT_DECLARATION_SCOPE_RECEIPT_SCHEMA_VERSION
                if self._current_source_fact
                else GATE5_DECLARATION_SCOPE_RECEIPT_SCHEMA_VERSION
            ),
            "status": (
                "SCOPE_RESOLVED_FOR_SUPPLIED_CASE"
                if not unresolved and not conflicts
                else "SCOPE_INCOMPLETE_FOR_SUPPLIED_CASE"
            ),
            "definition_binding": publication,
            "scope_binding": scope_binding,
            "gate4_binding": gate4_binding,
            "scope_semantics": copy.deepcopy(GATE5_DECLARATION_SCOPE_SEMANTICS),
            "domains": rows,
            "unresolved_domains": unresolved,
            "conflicts": conflicts,
            "missing_source_requests": missing_source_requests,
            "human_residual": human_residual,
            "first_downstream_blocker": _first_downstream_blocker(
                rows=rows,
                definition=definition,
            ),
        }
        if self._current_source_fact:
            base["taxpayer_binding"] = copy.deepcopy(validated_taxpayer_binding)
        receipt = {**base, "receipt_sha256": _canonical_sha256(base)}
        self.validate_receipt(receipt=receipt, context=context)
        return receipt

    def submit_human_answer(
        self,
        *,
        receipt: dict[str, Any],
        human_answer: dict[str, Any],
        context: ArtifactAccessContext,
        domain_id: str | None = None,
    ) -> dict[str, Any]:
        validated_receipt = self.validate_receipt(receipt=receipt, context=context)
        request = validated_receipt["human_residual"]
        if domain_id is not None:
            definition = self._definition_authority.resolve(
                validated_receipt["definition_binding"]["definition_id"],
                validated_receipt["definition_binding"]["definition_version"],
                validated_receipt["definition_binding"]["definition_sha256"],
            )
            contract = self._definition_authority.resolve_for_scope(
                validated_receipt["definition_binding"]["definition_id"],
                validated_receipt["definition_binding"]["definition_version"],
                validated_receipt["definition_binding"]["definition_sha256"],
            )
            policies = _policy_rows(contract["applicability_audit"], definition)
            domain = next(
                (
                    item
                    for item in definition["domains"]
                    if item["domain_id"] == domain_id
                ),
                None,
            )
            row = next(
                (
                    item
                    for item in validated_receipt["domains"]
                    if item["domain_id"] == domain_id
                ),
                None,
            )
            if (
                domain is None
                or row is None
                or row["state"] != "NOT_ACTIVATED_FOR_SUPPLIED_CASE"
            ):
                _fail("gate5_declaration_scope_human_request_absent")
            request = _human_request(
                domain=domain,
                policy=policies[domain_id],
                definition_binding=validated_receipt["definition_binding"],
                scope=validated_receipt["scope_binding"],
            )
        if request is None or validated_receipt["conflicts"]:
            _fail("gate5_declaration_scope_human_request_absent")
        answer = _human_answer(human_answer)
        policy = request["policy"]
        if policy not in _HUMAN_POLARITY:
            _fail("gate5_declaration_scope_human_policy_incompatible")
        assertion_ref = new_artifact_id()
        assertion = {
            "schema_version": GATE5_DECLARATION_SCOPE_ASSERTION_SCHEMA_VERSION,
            "assertion_ref": assertion_ref,
            "definition_binding": copy.deepcopy(
                validated_receipt["definition_binding"]
            ),
            "scope_binding": copy.deepcopy(validated_receipt["scope_binding"]),
            "domain_id": request["domain_id"],
            "policy": policy,
            "answer": answer,
            "polarity": _HUMAN_POLARITY[policy][answer],
            "request_sha256": request["request_sha256"],
            "provenance": {
                "source_kind": "user_case_evidence",
                "provided_by": "authenticated_user",
                "input_channel": "declaration_scope_residual",
                "gate4_derived": False,
            },
        }
        record = ArtifactRecord(
            artifact_id=assertion_ref,
            artifact_type=GATE5_DECLARATION_SCOPE_ASSERTION_ARTIFACT_TYPE,
            case_id=context.case_id,
            chat_id=None,
            user_id=context.user_id,
            workspace_model_id=context.workspace_model_id,
            normalization_run_id=context.normalization_run_id,
            document_id=None,
            source_file_ref=None,
            visibility="private_case",
            storage_backend="project_artifact_payload",
            retention_policy=self._retention_policy,
            access_policy={
                "scope": "case_private",
                "requires_user_id": True,
                "requires_case_id": True,
            },
            validation_status="validated",
            lifecycle_status="private_ready",
            payload=assertion,
            safe_metadata={
                "schema_version": GATE5_DECLARATION_SCOPE_ASSERTION_SCHEMA_VERSION,
                "source_kind": "user_case_evidence",
                "gate4_derived": False,
            },
        )
        self._store.put_record(record)
        persisted = self._assertion(
            assertion_ref,
            definition_binding=validated_receipt["definition_binding"],
            scope=validated_receipt["scope_binding"],
            definition=self._definition_authority.resolve(
                validated_receipt["definition_binding"]["definition_id"],
                validated_receipt["definition_binding"]["definition_version"],
                validated_receipt["definition_binding"]["definition_sha256"],
            ),
            policies=None,
            context=context,
        )
        return {
            "status": "stored",
            "assertion_ref": assertion_ref,
            "assertion_sha256": _canonical_sha256(persisted),
        }

    def validate_receipt(
        self,
        *,
        receipt: dict[str, Any],
        context: ArtifactAccessContext,
    ) -> dict[str, Any]:
        expected_keys = (
            _CURRENT_FACT_RECEIPT_KEYS if self._current_source_fact else _RECEIPT_KEYS
        )
        expected_schema = (
            GATE5_CURRENT_FACT_DECLARATION_SCOPE_RECEIPT_SCHEMA_VERSION
            if self._current_source_fact
            else GATE5_DECLARATION_SCOPE_RECEIPT_SCHEMA_VERSION
        )
        if (
            not isinstance(receipt, dict)
            or set(receipt) != expected_keys
            or receipt.get("schema_version") != expected_schema
        ):
            _fail("gate5_declaration_scope_receipt_invalid")
        publication = _definition_binding(receipt.get("definition_binding"))
        contract = self._definition_authority.resolve_for_scope(
            publication["definition_id"],
            publication["definition_version"],
            publication["definition_sha256"],
        )
        if contract["publication"] != publication:
            _fail("gate5_declaration_scope_definition_binding_invalid")
        definition = contract["definition"]
        policies = _policy_rows(contract["applicability_audit"], definition)
        scope = _validated_scope_binding(
            receipt.get("scope_binding"),
            context=context,
            definition_tax_period=definition["declaration_identity"]["tax_period"],
        )
        if self._current_source_fact:
            gate4_facts = tuple(self._gate4_runtime.list_facts(context=context))
            _validated_current_fact_binding(receipt.get("gate4_binding"))
            current_gate4_binding = _current_fact_binding(gate4_facts)
            taxpayer_binding = validate_ordinary_trade_taxpayer_binding(
                receipt.get("taxpayer_binding")
            )
            if (
                taxpayer_binding is None
                or taxpayer_binding["taxpayer_scope_ref"] != scope["taxpayer_scope_ref"]
            ):
                _fail("gate5_declaration_scope_taxpayer_binding_invalid")
        else:
            _validated_gate4_binding(receipt.get("gate4_binding"))
            financial_case = self._gate4_runtime.read_case(context=context)
            gate4_facts = tuple(financial_case.facts)
            current_gate4_binding = _gate4_binding(financial_case)
        if receipt.get("gate4_binding") != current_gate4_binding:
            _fail("gate5_declaration_scope_gate4_binding_stale")
        if receipt.get("scope_semantics") != GATE5_DECLARATION_SCOPE_SEMANTICS:
            _fail("gate5_declaration_scope_semantics_invalid")
        missing_source_requests = _validated_missing_source_requests(
            receipt.get("missing_source_requests"),
            scope=scope,
            gate4_binding=current_gate4_binding,
            gate4_facts=gate4_facts,
            definition=definition,
        )
        rows = _validated_domain_rows(
            receipt.get("domains"),
            definition=definition,
            policies=policies,
            definition_binding=publication,
        )
        blocking_accounts = [
            (row["domain_id"], evidence["evidence_ref"])
            for row in rows
            for evidence in row["evidence_bindings"]
            if evidence["polarity"] == "blocking"
        ]
        expected_blocking_accounts = {
            (request["domain_id"], request["request_sha256"])
            for request in missing_source_requests
        }
        if (
            len(blocking_accounts) != len(set(blocking_accounts))
            or set(blocking_accounts) != expected_blocking_accounts
        ):
            _fail("gate5_declaration_scope_missing_source_accounting_invalid")
        unresolved = [row["domain_id"] for row in rows if row["state"] == "UNRESOLVED"]
        conflicts = [row["domain_id"] for row in rows if row["state"] == "CONFLICT"]
        if (
            receipt.get("unresolved_domains") != unresolved
            or receipt.get("conflicts") != conflicts
            or receipt.get("status")
            != (
                "SCOPE_RESOLVED_FOR_SUPPLIED_CASE"
                if not unresolved and not conflicts
                else "SCOPE_INCOMPLETE_FOR_SUPPLIED_CASE"
            )
            or receipt.get("first_downstream_blocker")
            != _first_downstream_blocker(rows=rows, definition=definition)
        ):
            _fail("gate5_declaration_scope_receipt_accounting_invalid")
        expected_human = (
            None
            if conflicts
            else _first_human_residual(
                rows=rows,
                definition=definition,
                policies=policies,
                definition_binding=publication,
                scope=scope,
            )
        )
        if receipt.get("human_residual") != expected_human:
            _fail("gate5_declaration_scope_human_request_invalid")
        base = {
            key: copy.deepcopy(receipt[key])
            for key in receipt
            if key != "receipt_sha256"
        }
        if receipt.get("receipt_sha256") != _canonical_sha256(base):
            _fail("gate5_declaration_scope_receipt_hash_mismatch")
        return copy.deepcopy(receipt)

    def _component_bindings(
        self,
        value: Any,
        *,
        definition: dict[str, Any],
        policies: dict[str, dict[str, Any]],
        scope: dict[str, Any],
        gate4_facts: tuple[dict[str, Any], ...],
        taxpayer_binding: dict[str, Any] | None,
    ) -> list[dict[str, str]]:
        if not isinstance(value, list):
            _fail("gate5_declaration_scope_component_evidence_invalid")
        contract_domains: dict[str, str] = {}
        for domain in definition["domains"]:
            for contract_id in domain["expected_component"]["contract_ids"]:
                if contract_id in contract_domains:
                    _fail("gate5_declaration_scope_component_authority_ambiguous")
                contract_domains[contract_id] = domain["domain_id"]
            if domain["expected_component"][
                "family"
            ] == GATE5_TAXABLE_INCOME_SOURCE_COMPONENT_FAMILY and domain[
                "obligation_refs"
            ] == list(GATE5_TAXABLE_INCOME_SOURCE_OBLIGATION_REFS):
                contract_domains[
                    GATE5_TAXABLE_INCOME_SOURCE_COMPONENT_SCHEMA_VERSION
                ] = domain["domain_id"]
        result: list[dict[str, str]] = []
        seen: set[str] = set()
        for position, item in enumerate(value):
            if (
                not isinstance(item, dict)
                or set(item) != _COMPONENT_EVIDENCE_KEYS
                or item.get("schema_version")
                != GATE5_DECLARATION_SCOPE_COMPONENT_EVIDENCE_SCHEMA_VERSION
                or not _identifier(item.get("component_contract_id"))
                or not _sha256(item.get("component_sha256"))
                or not isinstance(item.get("payload"), dict)
                or item["component_sha256"] != _canonical_sha256(item["payload"])
            ):
                _fail(
                    "gate5_declaration_scope_component_evidence_invalid",
                    str(position),
                )
            contract_id = item["component_contract_id"]
            if contract_id not in contract_domains:
                _fail("gate5_declaration_scope_component_unknown", contract_id)
            if item["component_sha256"] in seen:
                _fail("gate5_declaration_scope_component_duplicate")
            seen.add(item["component_sha256"])
            domain_id = contract_domains[contract_id]
            policy = policies[domain_id]
            if "validated_typed_component" not in policy["allowed_authority_classes"]:
                _fail("gate5_declaration_scope_policy_evidence_incompatible")
            try:
                if (
                    contract_id
                    == GATE5_SECURITIES_DISPOSAL_OPERATION_TAX_MODEL_SCHEMA_VERSION
                ):
                    payload = self._component_runtime.validate_operation_member(
                        tax_model=item["payload"]
                    )
                elif (
                    contract_id == GATE5_TAXABLE_INCOME_SOURCE_COMPONENT_SCHEMA_VERSION
                ):
                    payload = self._income_sources_runtime.validate_component(
                        component=item["payload"],
                        scope_binding=scope,
                    )
                else:
                    _fail(
                        "gate5_declaration_scope_component_validator_missing",
                        contract_id,
                    )
            except Gate5DeclarationScopeResolutionError:
                raise
            except ValueError as exc:
                raise Gate5DeclarationScopeResolutionError(
                    "gate5_declaration_scope_component_validation_failed"
                ) from exc
            if (
                contract_id
                == GATE5_SECURITIES_DISPOSAL_OPERATION_TAX_MODEL_SCHEMA_VERSION
            ):
                subject_ref = payload["operation_scope"]["subject_ref"]
                if self._current_source_fact:
                    if (
                        taxpayer_binding is None
                        or subject_ref != taxpayer_binding["operation_subject_ref"]
                        or scope["taxpayer_scope_ref"]
                        != taxpayer_binding["taxpayer_scope_ref"]
                    ):
                        _fail("gate5_declaration_scope_component_identity_mismatch")
                elif subject_ref != scope["taxpayer_scope_ref"]:
                    _fail("gate5_declaration_scope_component_scope_mismatch")
                if (
                    payload["operation_scope"]["tax_period"].get("value")
                    != scope["tax_period"]
                ):
                    _fail("gate5_declaration_scope_component_scope_mismatch")
            if (
                contract_id
                == GATE5_SECURITIES_DISPOSAL_OPERATION_TAX_MODEL_SCHEMA_VERSION
            ):
                _validate_current_financial_sources(payload, gate4_facts=gate4_facts)
            result.append(
                {
                    "domain_id": domain_id,
                    "authority_class": "validated_typed_component",
                    "evidence_kind": contract_id,
                    "evidence_ref": item["component_sha256"],
                    "evidence_sha256": item["component_sha256"],
                    "polarity": "positive",
                }
            )
        return result

    def _missing_source_bindings(
        self,
        value: Any,
        *,
        definition: dict[str, Any],
        scope: dict[str, Any],
        gate4_facts: tuple[dict[str, Any], ...],
    ) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
        if not isinstance(value, list):
            _fail("gate5_declaration_scope_missing_source_indications_invalid")
        contract_domains: dict[str, str] = {}
        domain_order: dict[str, int] = {}
        for position, domain in enumerate(definition["domains"]):
            domain_order[domain["domain_id"]] = position
            for contract_id in domain["expected_component"]["contract_ids"]:
                if contract_id in contract_domains:
                    _fail("gate5_declaration_scope_component_authority_ambiguous")
                contract_domains[contract_id] = domain["domain_id"]
        current = {fact["fact_id"]: fact for fact in gate4_facts}
        bindings: list[dict[str, str]] = []
        requests: list[dict[str, Any]] = []
        seen: set[str] = set()
        for position, item in enumerate(value):
            if (
                not isinstance(item, dict)
                or set(item) != _MISSING_SOURCE_INDICATION_KEYS
                or item.get("schema_version")
                != GATE5_DECLARATION_SCOPE_MISSING_SOURCE_INDICATION_SCHEMA_VERSION
                or item.get("component_contract_id") not in contract_domains
                or not _identifier(item.get("source_fact_id"))
                or not _sha256(item.get("source_fact_sha256"))
                or not isinstance(item.get("missing_role_names"), list)
                or not item["missing_role_names"]
                or item["missing_role_names"] != sorted(set(item["missing_role_names"]))
                or any(not _identifier(name) for name in item["missing_role_names"])
            ):
                _fail(
                    "gate5_declaration_scope_missing_source_indication_invalid",
                    str(position),
                )
            fact = current.get(item["source_fact_id"])
            missing_roles = (
                []
                if fact is None
                else sorted(
                    role["role"]
                    for role in fact.get("roles", [])
                    if role.get("requirement") == "required"
                    and role.get("status") == "missing"
                )
            )
            if (
                fact is None
                or item["source_fact_sha256"] != _canonical_sha256(fact)
                or fact.get("status") != "role_incomplete"
                or item["missing_role_names"] != missing_roles
            ):
                _fail("gate5_declaration_scope_missing_source_fact_invalid")
            indication_sha256 = _canonical_sha256(item)
            if indication_sha256 in seen:
                _fail("gate5_declaration_scope_missing_source_duplicate")
            seen.add(indication_sha256)
            domain_id = contract_domains[item["component_contract_id"]]
            request_base = {
                "schema_version": GATE5_DECLARATION_SCOPE_MISSING_SOURCE_REQUEST_SCHEMA_VERSION,
                "domain_id": domain_id,
                "component_contract_id": item["component_contract_id"],
                "source_fact_id": item["source_fact_id"],
                "source_fact_sha256": item["source_fact_sha256"],
                "scope_binding_sha256": scope["scope_binding_sha256"],
                "missing_role_names": copy.deepcopy(item["missing_role_names"]),
                "reason": "observed_financial_fact_missing_required_values",
                "action": "provide_missing_source_or_values",
                "indication_sha256": indication_sha256,
            }
            request = {
                **request_base,
                "request_sha256": _canonical_sha256(request_base),
            }
            requests.append(request)
            bindings.append(
                {
                    "domain_id": domain_id,
                    "authority_class": "supplied_case_missing_source_indication",
                    "evidence_kind": (
                        GATE5_DECLARATION_SCOPE_MISSING_SOURCE_INDICATION_SCHEMA_VERSION
                    ),
                    "evidence_ref": request["request_sha256"],
                    "evidence_sha256": request["request_sha256"],
                    "polarity": "blocking",
                }
            )
        paired = sorted(
            zip(bindings, requests, strict=True),
            key=lambda pair: (
                domain_order[pair[1]["domain_id"]],
                pair[1]["source_fact_id"],
                pair[1]["component_contract_id"],
            ),
        )
        return [pair[0] for pair in paired], [pair[1] for pair in paired]

    def _assertion_bindings(
        self,
        value: Any,
        *,
        definition: dict[str, Any],
        definition_binding: dict[str, Any],
        policies: dict[str, dict[str, Any]],
        scope: dict[str, Any],
        context: ArtifactAccessContext,
    ) -> list[dict[str, str]]:
        if (
            not isinstance(value, list)
            or any(not isinstance(ref, str) for ref in value)
            or len(value) != len(set(value))
        ):
            _fail("gate5_declaration_scope_assertion_refs_invalid")
        result = []
        for ref in value:
            assertion = self._assertion(
                ref,
                definition_binding=definition_binding,
                scope=scope,
                definition=definition,
                policies=policies,
                context=context,
            )
            result.append(
                {
                    "domain_id": assertion["domain_id"],
                    "authority_class": "user_case_evidence",
                    "evidence_kind": GATE5_DECLARATION_SCOPE_ASSERTION_SCHEMA_VERSION,
                    "evidence_ref": assertion["assertion_ref"],
                    "evidence_sha256": _canonical_sha256(assertion),
                    "polarity": assertion["polarity"],
                }
            )
        return result

    def _assertion(
        self,
        assertion_ref: str,
        *,
        definition_binding: dict[str, Any],
        scope: dict[str, Any],
        definition: dict[str, Any],
        policies: dict[str, dict[str, Any]] | None,
        context: ArtifactAccessContext,
    ) -> dict[str, Any]:
        if (
            not isinstance(assertion_ref, str)
            or _ARTIFACT_REF.fullmatch(assertion_ref) is None
        ):
            _fail("gate5_declaration_scope_assertion_ref_invalid")
        resolved = self._resolver.resolve(assertion_ref, context)
        record = resolved["record"]
        value = resolved["payload"]
        if (
            record.artifact_type != GATE5_DECLARATION_SCOPE_ASSERTION_ARTIFACT_TYPE
            or not isinstance(value, dict)
            or set(value) != _ASSERTION_KEYS
            or value.get("schema_version")
            != GATE5_DECLARATION_SCOPE_ASSERTION_SCHEMA_VERSION
            or value.get("assertion_ref") != assertion_ref
            or value.get("definition_binding") != definition_binding
            or value.get("scope_binding") != scope
            or value.get("answer") not in _ANSWERS
            or value.get("provenance")
            != {
                "source_kind": "user_case_evidence",
                "provided_by": "authenticated_user",
                "input_channel": "declaration_scope_residual",
                "gate4_derived": False,
            }
        ):
            _fail("gate5_declaration_scope_assertion_invalid")
        domain = next(
            (
                item
                for item in definition["domains"]
                if item["domain_id"] == value.get("domain_id")
            ),
            None,
        )
        if domain is None:
            _fail("gate5_declaration_scope_assertion_domain_unknown")
        if policies is None:
            contract = self._definition_authority.resolve_for_scope(
                definition_binding["definition_id"],
                definition_binding["definition_version"],
                definition_binding["definition_sha256"],
            )
            policies = _policy_rows(contract["applicability_audit"], definition)
        policy = policies[domain["domain_id"]]
        request = _human_request(
            domain=domain,
            policy=policy,
            definition_binding=definition_binding,
            scope=scope,
        )
        if (
            value.get("policy") != policy["policy"]
            or "user_case_evidence" not in policy["allowed_authority_classes"]
            or policy["policy"] not in _HUMAN_POLARITY
            or value.get("polarity")
            != _HUMAN_POLARITY[policy["policy"]][value["answer"]]
            or value.get("request_sha256") != request["request_sha256"]
        ):
            _fail("gate5_declaration_scope_policy_evidence_incompatible")
        return copy.deepcopy(value)


def _definition_binding(value: Any) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or set(value) != _DEFINITION_BINDING_KEYS
        or value.get("schema_version")
        != GATE5_FULL_DECLARATION_DEFINITION_PUBLICATION_SCHEMA_VERSION
        or value.get("status") != "trusted_repository_published"
        or not _identifier(value.get("definition_id"))
        or not _identifier(value.get("definition_version"))
        or not all(
            _sha256(value.get(key))
            for key in (
                "definition_sha256",
                "validation_sha256",
                "obligation_package_sha256",
            )
        )
    ):
        _fail("gate5_declaration_scope_definition_binding_invalid")
    return copy.deepcopy(value)


def _scope_binding(
    value: Any,
    *,
    context: ArtifactAccessContext,
    definition_tax_period: str,
) -> dict[str, Any]:
    scope = _scope(value, context=context, definition_tax_period=definition_tax_period)
    return {**scope, "scope_binding_sha256": _canonical_sha256(scope)}


def _scope(
    value: Any,
    *,
    context: ArtifactAccessContext,
    definition_tax_period: str,
) -> dict[str, Any]:
    if (
        not isinstance(context, ArtifactAccessContext)
        or not context.allow_private
        or not isinstance(context.case_id, str)
        or not _identifier(context.case_id)
        or not _identifier(context.user_id)
        or not _identifier(context.normalization_run_id)
        or not isinstance(value, dict)
        or set(value) != _SCOPE_INPUT_KEYS
        or value.get("schema_version") != GATE5_DECLARATION_SCOPE_SCHEMA_VERSION
        or not all(
            _identifier(value.get(key))
            for key in (
                "scope_ref",
                "taxpayer_scope_ref",
            )
        )
        or value.get("tax_period") != definition_tax_period
    ):
        _fail("gate5_declaration_scope_scope_binding_invalid")
    return {
        **copy.deepcopy(value),
        "authenticated_user_ref": context.user_id,
        "case_id": context.case_id,
        "normalization_run_ref": context.normalization_run_id,
    }


def _validated_scope_binding(
    value: Any,
    *,
    context: ArtifactAccessContext,
    definition_tax_period: str,
) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != _SCOPE_BINDING_KEYS:
        _fail("gate5_declaration_scope_scope_binding_invalid")
    scope = _scope(
        {key: copy.deepcopy(value[key]) for key in _SCOPE_INPUT_KEYS},
        context=context,
        definition_tax_period=definition_tax_period,
    )
    if any(
        value[key] != scope[key]
        for key in ("authenticated_user_ref", "case_id", "normalization_run_ref")
    ):
        _fail("gate5_declaration_scope_scope_binding_invalid")
    if value.get("scope_binding_sha256") != _canonical_sha256(scope):
        _fail("gate5_declaration_scope_scope_hash_mismatch")
    return copy.deepcopy(value)


def _policy_rows(
    value: Any,
    definition: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    rows = value.get("rows") if isinstance(value, dict) else None
    if (
        not isinstance(value, dict)
        or value.get("status") != "passed"
        or not isinstance(rows, list)
    ):
        _fail("gate5_declaration_scope_policy_audit_invalid")
    expected_ids = [domain["domain_id"] for domain in definition["domains"]]
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        if (
            not isinstance(row, dict)
            or set(row)
            != {
                "domain_id",
                "mode",
                "policy",
                "allowed_authority_classes",
                "official_evidence_refs",
            }
            or row.get("domain_id") not in expected_ids
            or row["domain_id"] in result
            or row.get("mode") not in {"always", "conditional"}
            or not _identifier(row.get("policy"))
            or not isinstance(row.get("allowed_authority_classes"), list)
            or not row["allowed_authority_classes"]
        ):
            _fail("gate5_declaration_scope_policy_audit_invalid")
        result[row["domain_id"]] = copy.deepcopy(row)
    if list(result) != expected_ids:
        _fail("gate5_declaration_scope_policy_audit_invalid")
    return result


def _gate4_binding(financial_case: Any) -> dict[str, Any]:
    sources = sorted(
        (
            {
                "document_id": item.document_id,
                "status": item.status,
                "canonical_version_id": item.canonical_version_id,
                "financial_annotations_artifact_id": (
                    item.financial_annotations_artifact_id
                ),
            }
            for item in financial_case.sources
        ),
        key=lambda item: item["document_id"],
    )
    facts = sorted(
        (
            {
                "fact_id": item["fact_id"],
                "financial_type": item["financial_type"],
                "fact_sha256": _canonical_sha256(item),
            }
            for item in financial_case.facts
        ),
        key=lambda item: item["fact_id"],
    )
    base = {
        "boundary": "Gate4FinancialCaseRuntimeFactory.create",
        "status": financial_case.status,
        "gate3_case_status": financial_case.gate3_case_status,
        "sources": sources,
        "facts": facts,
    }
    return {**base, "binding_sha256": _canonical_sha256(base)}


def _validated_gate4_binding(value: Any) -> None:
    if (
        not isinstance(value, dict)
        or set(value) != _GATE4_BINDING_KEYS
        or value.get("boundary") != "Gate4FinancialCaseRuntimeFactory.create"
        or not isinstance(value.get("status"), str)
        or not isinstance(value.get("gate3_case_status"), str)
        or not isinstance(value.get("sources"), list)
        or not isinstance(value.get("facts"), list)
    ):
        _fail("gate5_declaration_scope_gate4_binding_invalid")


def _current_fact_binding(
    facts: tuple[dict[str, Any], ...],
) -> dict[str, Any]:
    sources_by_id: dict[str, dict[str, Any]] = {}
    fact_rows = []
    for fact in facts:
        gate3_binding = fact.get("gate3_binding", {})
        artifact_id = gate3_binding.get("financial_annotations_artifact_id")
        canonical = gate3_binding.get("canonical_binding")
        if not isinstance(artifact_id, str) or not isinstance(canonical, dict):
            _fail("gate5_declaration_scope_current_fact_binding_invalid")
        sources_by_id[artifact_id] = {
            "document_id": canonical.get("document_id"),
            "status": "current_fact_v2_source",
            "canonical_version_id": canonical.get("canonical_version_id"),
            "financial_annotations_artifact_id": artifact_id,
        }
        fact_rows.append(
            {
                "fact_id": fact.get("fact_id"),
                "financial_type": fact.get("financial_type"),
                "fact_sha256": _canonical_sha256(fact),
            }
        )
    base = {
        "boundary": "Gate4OrdinaryTradeCandidateRuntimeFactory.create",
        "status": "current_fact_v2_available",
        "gate3_case_status": "not_executed",
        "sources": sorted(sources_by_id.values(), key=lambda item: item["document_id"]),
        "facts": sorted(fact_rows, key=lambda item: item["fact_id"]),
    }
    return {**base, "binding_sha256": _canonical_sha256(base)}


def _validated_current_fact_binding(value: Any) -> None:
    if (
        not isinstance(value, dict)
        or set(value) != _GATE4_BINDING_KEYS
        or value.get("boundary") != "Gate4OrdinaryTradeCandidateRuntimeFactory.create"
        or value.get("status") != "current_fact_v2_available"
        or value.get("gate3_case_status") != "not_executed"
        or not isinstance(value.get("sources"), list)
        or not isinstance(value.get("facts"), list)
    ):
        _fail("gate5_declaration_scope_current_fact_binding_invalid")
    base = {key: copy.deepcopy(value[key]) for key in value if key != "binding_sha256"}
    if value.get("binding_sha256") != _canonical_sha256(base):
        _fail("gate5_declaration_scope_current_fact_binding_invalid")
    base = {key: copy.deepcopy(value[key]) for key in value if key != "binding_sha256"}
    if value.get("binding_sha256") != _canonical_sha256(base):
        _fail("gate5_declaration_scope_gate4_binding_invalid")


def _validated_missing_source_requests(
    value: Any,
    *,
    scope: dict[str, Any],
    gate4_binding: dict[str, Any],
    gate4_facts: tuple[dict[str, Any], ...],
    definition: dict[str, Any],
) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        _fail("gate5_declaration_scope_missing_source_requests_invalid")
    domains = {domain["domain_id"]: domain for domain in definition["domains"]}
    contract_domains = {
        contract_id: domain["domain_id"]
        for domain in definition["domains"]
        for contract_id in domain["expected_component"]["contract_ids"]
    }
    facts = {fact["fact_id"]: fact for fact in gate4_binding["facts"]}
    full_facts = {fact["fact_id"]: fact for fact in gate4_facts}
    seen: set[str] = set()
    result = []
    for position, item in enumerate(value):
        base = (
            {}
            if not isinstance(item, dict)
            else {
                key: copy.deepcopy(item[key]) for key in item if key != "request_sha256"
            }
        )
        fact = facts.get(item.get("source_fact_id")) if isinstance(item, dict) else None
        full_fact = (
            full_facts.get(item.get("source_fact_id"))
            if isinstance(item, dict)
            else None
        )
        missing_roles = (
            []
            if full_fact is None
            else sorted(
                role["role"]
                for role in full_fact.get("roles", [])
                if role.get("requirement") == "required"
                and role.get("status") == "missing"
            )
        )
        indication = (
            {}
            if not isinstance(item, dict)
            else {
                "schema_version": (
                    GATE5_DECLARATION_SCOPE_MISSING_SOURCE_INDICATION_SCHEMA_VERSION
                ),
                "component_contract_id": item.get("component_contract_id"),
                "source_fact_id": item.get("source_fact_id"),
                "source_fact_sha256": item.get("source_fact_sha256"),
                "missing_role_names": copy.deepcopy(item.get("missing_role_names")),
            }
        )
        if (
            not isinstance(item, dict)
            or set(item) != _MISSING_SOURCE_REQUEST_KEYS
            or item.get("schema_version")
            != GATE5_DECLARATION_SCOPE_MISSING_SOURCE_REQUEST_SCHEMA_VERSION
            or item.get("domain_id") not in domains
            or contract_domains.get(item.get("component_contract_id"))
            != item.get("domain_id")
            or fact is None
            or full_fact is None
            or fact.get("fact_sha256") != item.get("source_fact_sha256")
            or item.get("source_fact_sha256") != _canonical_sha256(full_fact)
            or item.get("scope_binding_sha256") != scope["scope_binding_sha256"]
            or not isinstance(item.get("missing_role_names"), list)
            or not item["missing_role_names"]
            or item["missing_role_names"] != sorted(set(item["missing_role_names"]))
            or any(not _identifier(name) for name in item["missing_role_names"])
            or item["missing_role_names"] != missing_roles
            or item.get("reason") != "observed_financial_fact_missing_required_values"
            or item.get("action") != "provide_missing_source_or_values"
            or item.get("indication_sha256") != _canonical_sha256(indication)
            or item.get("request_sha256") != _canonical_sha256(base)
            or item["request_sha256"] in seen
        ):
            _fail(
                "gate5_declaration_scope_missing_source_request_invalid",
                str(position),
            )
        seen.add(item["request_sha256"])
        result.append(copy.deepcopy(item))
    domain_order = {
        domain["domain_id"]: position
        for position, domain in enumerate(definition["domains"])
    }
    if result != sorted(
        result,
        key=lambda item: (
            domain_order[item["domain_id"]],
            item["source_fact_id"],
            item["component_contract_id"],
        ),
    ):
        _fail("gate5_declaration_scope_missing_source_accounting_invalid")
    return result


def _validate_current_financial_sources(
    payload: dict[str, Any],
    *,
    gate4_facts: tuple[dict[str, Any], ...],
) -> None:
    current = {fact["fact_id"]: fact for fact in gate4_facts}
    sources = _nested_financial_sources(payload)
    if not sources:
        _fail("gate5_declaration_scope_component_financial_source_missing")
    for source in sources:
        if source.get("source_kind") == "normalized_source_fact":
            fact = current.get(source.get("fact_id"))
            expected = (
                None
                if fact is None
                else {
                    "source_kind": "normalized_source_fact",
                    "fact_id": fact["fact_id"],
                    "financial_type": fact["financial_type"],
                    "gate3_binding": fact["gate3_binding"],
                    "annotation_target": fact["annotation_target"],
                }
            )
            if source != expected:
                _fail("gate5_declaration_scope_component_financial_source_stale")
            continue
        matches = source.get("matches")
        if not isinstance(matches, list) or not matches:
            _fail("gate5_declaration_scope_component_financial_source_stale")
        for match in matches:
            fact = (
                current.get(match.get("fact_id")) if isinstance(match, dict) else None
            )
            roles = (
                {}
                if fact is None
                else {
                    item.get("role"): item.get("value")
                    for item in fact["roles"]
                    if item.get("status") == "value"
                }
            )
            if (
                fact is None
                or set(match) != {"fact_id", "role", "value"}
                or roles.get(match["role"]) != match["value"]
            ):
                _fail("gate5_declaration_scope_component_financial_source_stale")


def _nested_financial_sources(value: Any) -> list[dict[str, Any]]:
    result = []
    if isinstance(value, dict):
        if value.get("source_kind") in {
            "financial_case",
            "normalized_source_fact",
        }:
            result.append(value)
        for nested in value.values():
            result.extend(_nested_financial_sources(nested))
    elif isinstance(value, list):
        for nested in value:
            result.extend(_nested_financial_sources(nested))
    return result


def _first_human_residual(
    *,
    rows: list[dict[str, Any]],
    definition: dict[str, Any],
    policies: dict[str, dict[str, Any]],
    definition_binding: dict[str, Any],
    scope: dict[str, Any],
) -> dict[str, Any] | None:
    by_id = {domain["domain_id"]: domain for domain in definition["domains"]}
    for row in rows:
        policy = policies[row["domain_id"]]
        if (
            row["state"] == "UNRESOLVED"
            and not any(
                evidence["polarity"] == "blocking"
                for evidence in row["evidence_bindings"]
            )
            and "user_case_evidence" in policy["allowed_authority_classes"]
            and policy["policy"] in _HUMAN_POLARITY
        ):
            return _human_request(
                domain=by_id[row["domain_id"]],
                policy=policy,
                definition_binding=definition_binding,
                scope=scope,
            )
    return None


def _human_request(
    *,
    domain: dict[str, Any],
    policy: dict[str, Any],
    definition_binding: dict[str, Any],
    scope: dict[str, Any],
) -> dict[str, Any]:
    base = {
        "schema_version": GATE5_DECLARATION_SCOPE_HUMAN_REQUEST_SCHEMA_VERSION,
        "domain_id": domain["domain_id"],
        "policy": policy["policy"],
        "definition_sha256": definition_binding["definition_sha256"],
        "scope_binding_sha256": scope["scope_binding_sha256"],
        "question_context": {
            "tax_period": scope["tax_period"],
            "semantic_meaning": domain["semantic_meaning"],
        },
        "answer_contract": ["yes", "no"],
    }
    return {**base, "request_sha256": _canonical_sha256(base)}


def _human_answer(value: Any) -> str:
    if (
        not isinstance(value, dict)
        or set(value) != {"schema_version", "answer"}
        or value.get("schema_version")
        != GATE5_DECLARATION_SCOPE_HUMAN_ANSWER_SCHEMA_VERSION
        or value.get("answer") not in _ANSWERS
    ):
        _fail("gate5_declaration_scope_human_answer_invalid")
    return value["answer"]


def _validated_domain_rows(
    value: Any,
    *,
    definition: dict[str, Any],
    policies: dict[str, dict[str, Any]],
    definition_binding: dict[str, Any],
) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        _fail("gate5_declaration_scope_domain_accounting_invalid")
    expected_ids = [domain["domain_id"] for domain in definition["domains"]]
    if [
        row.get("domain_id") if isinstance(row, dict) else None for row in value
    ] != expected_ids:
        _fail("gate5_declaration_scope_domain_accounting_invalid")
    result = []
    for row in value:
        policy = policies[row["domain_id"]]
        evidence = row.get("evidence_bindings")
        if (
            set(row) != _DOMAIN_ROW_KEYS
            or row.get("mode") != policy["mode"]
            or row.get("policy") != policy["policy"]
            or row.get("state") not in _STATES
            or row.get("resolution_route") not in _ROUTES
            or not isinstance(evidence, list)
        ):
            _fail("gate5_declaration_scope_domain_row_invalid", row["domain_id"])
        polarities = set()
        for binding in evidence:
            blocking = (
                isinstance(binding, dict)
                and binding.get("polarity") == "blocking"
                and binding.get("authority_class")
                == "supplied_case_missing_source_indication"
                and binding.get("evidence_kind")
                == GATE5_DECLARATION_SCOPE_MISSING_SOURCE_INDICATION_SCHEMA_VERSION
                and binding.get("evidence_ref") == binding.get("evidence_sha256")
            )
            if (
                not isinstance(binding, dict)
                or set(binding) != _EVIDENCE_BINDING_KEYS
                or binding.get("polarity") not in {"positive", "negative", "blocking"}
                or not _sha256(binding.get("evidence_sha256"))
                or not isinstance(binding.get("evidence_ref"), str)
                or (
                    not blocking
                    and binding.get("authority_class")
                    not in policy["allowed_authority_classes"]
                )
                or (binding.get("polarity") == "blocking" and not blocking)
            ):
                _fail("gate5_declaration_scope_policy_evidence_incompatible")
            polarities.add(binding["polarity"])
        expected_state = (
            "APPLICABLE"
            if policy["mode"] == "always"
            else "CONFLICT"
            if {"positive", "negative"}.issubset(polarities)
            else "UNRESOLVED"
            if "blocking" in polarities
            else "APPLICABLE"
            if polarities == {"positive"}
            else "NOT_APPLICABLE"
            if polarities == {"negative"}
            else "NOT_ACTIVATED_FOR_SUPPLIED_CASE"
        )
        if policy["mode"] == "always":
            expected = [
                {
                    "authority_class": "trusted_declaration_definition",
                    "evidence_kind": "definition_mandatory",
                    "evidence_ref": row["domain_id"],
                    "evidence_sha256": definition_binding["definition_sha256"],
                    "polarity": "positive",
                }
            ]
            if evidence != expected:
                _fail("gate5_declaration_scope_mandatory_evidence_invalid")
        expected_route = (
            "RESOLVE"
            if policy["mode"] == "always" or not evidence
            else "ACQUIRE"
            if "blocking" in polarities
            else "EXECUTE"
            if any(
                item["authority_class"] == "validated_typed_component"
                for item in evidence
            )
            else "ACQUIRE"
        )
        if row["state"] != expected_state or row["resolution_route"] != expected_route:
            _fail("gate5_declaration_scope_domain_state_invalid")
        base = {key: copy.deepcopy(row[key]) for key in row if key != "decision_sha256"}
        if row.get("decision_sha256") != _canonical_sha256(base):
            _fail("gate5_declaration_scope_decision_hash_mismatch")
        result.append(copy.deepcopy(row))
    return result


def _first_downstream_blocker(
    *,
    rows: list[dict[str, Any]],
    definition: dict[str, Any],
) -> dict[str, Any] | None:
    states = {row["domain_id"]: row["state"] for row in rows}
    for domain in definition["domains"]:
        component = domain["expected_component"]
        if (
            states[domain["domain_id"]] == "APPLICABLE"
            and component["availability"] != "published_exact"
        ):
            return {
                "domain_id": domain["domain_id"],
                "component_family": component["family"],
                "component_availability": component["availability"],
                "reason": (
                    "required_component_missing"
                    if component["availability"] == "missing"
                    else "required_component_bounded_only"
                ),
            }
    return None


def _identifier(value: Any) -> bool:
    return isinstance(value, str) and _IDENTIFIER.fullmatch(value) is not None


def _sha256(value: Any) -> bool:
    return isinstance(value, str) and _SHA256.fullmatch(value) is not None


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _fail(code: str, field: str = "") -> None:
    raise Gate5DeclarationScopeResolutionError(code, field)


class Gate5DeclarationScopeActivationError(ValueError):
    """Fail-closed error for the supplied-case activation operation."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class Gate5DeclarationScopeActivationRuntimeFactory:
    """The single scope owner also composes intent/evidence activation."""

    def __init__(self, *, store: ArtifactStorePort, read_enabled: bool) -> None:
        self._store = store
        self._read_enabled = read_enabled

    def create(self) -> "Gate5DeclarationScopeActivationRuntime":
        return Gate5DeclarationScopeActivationRuntime(
            case_assembler=Gate5RealTaxCaseAssemblyRuntimeFactory(
                store=self._store,
                read_enabled=self._read_enabled,
            ).create(),
            definition_authority=(
                Gate5TrustedFullDeclarationDefinitionAuthorityFactory.create()
            ),
        )


class Gate5DeclarationScopeActivationRuntime:
    def __init__(
        self,
        *,
        case_assembler: Gate5RealTaxCaseAssemblyRuntime,
        definition_authority: Gate5TrustedFullDeclarationDefinitionAuthority,
    ) -> None:
        self._case_assembler = case_assembler
        self._definition_authority = definition_authority

    def activate(
        self,
        *,
        user_intent: dict[str, Any],
        evidence_mode: str,
        source_fact_methodology_ref: dict[str, Any] | None = None,
        context: ArtifactAccessContext | None = None,
        case_assembly: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        intent = _validated_activation_intent(user_intent)
        if case_assembly is None:
            if source_fact_methodology_ref is None or context is None:
                _activation_fail("gate5_scope_activation_case_required")
            case_assembly = self._case_assembler.assemble(
                source_fact_methodology_ref=source_fact_methodology_ref,
                context=context,
                evidence_mode=evidence_mode,
            )
        case = _validated_activation_case(case_assembly, evidence_mode=evidence_mode)
        publication = self._definition_authority.publication()
        contract = self._definition_authority.resolve_for_scope(
            publication["definition_id"],
            publication["definition_version"],
            publication["definition_sha256"],
        )
        definition = contract["definition"]
        identity = definition["declaration_identity"]
        if (
            intent["form"] != identity["form"]
            or intent["tax_period"] != identity["tax_period"]
        ):
            _activation_fail("gate5_scope_activation_intent_definition_mismatch")
        policies = {
            row["domain_id"]: row for row in contract["applicability_audit"]["rows"]
        }
        activated_obligations: dict[str, set[str]] = {}
        for domain in definition["domains"]:
            if policies[domain["domain_id"]]["mode"] == "always":
                for obligation_ref in domain["obligation_refs"]:
                    activated_obligations.setdefault(obligation_ref, set()).add(
                        "MANDATORY_COMMON_DECLARATION_FIELD"
                    )
        if "broker_securities_income" in intent["domains"]:
            for obligation_ref in _ACTIVATION_BROKER_INTENT_OBLIGATION_REFS:
                activated_obligations.setdefault(obligation_ref, set()).add(
                    "USER_INTENT"
                )
        source = case["source_fact_assembly"]
        counts = source["financial_type_counts"]
        if any(counts.get(item, 0) for item in _ACTIVATION_SECURITY_TYPES):
            for obligation_ref in _ACTIVATION_SECURITIES_OBLIGATION_REFS:
                activated_obligations.setdefault(obligation_ref, set()).add(
                    "EVIDENCE_DISCOVERED_SECURITIES"
                )
        if any(counts.get(item, 0) for item in _ACTIVATION_INCOME_TYPES):
            for obligation_ref in _ACTIVATION_INCOME_OBLIGATION_REFS:
                activated_obligations.setdefault(obligation_ref, set()).add(
                    "EVIDENCE_DISCOVERED_TAXABLE_INCOME"
                )

        active_demands: list[dict[str, Any]] = []
        rows_by_id = {row["demand"]: row for row in case["declaration_demands"]}
        activated_domains: dict[str, set[str]] = {}
        for domain in definition["domains"]:
            domain_id = domain["domain_id"]
            domain_reasons = {
                reason
                for obligation_ref in domain["obligation_refs"]
                for reason in activated_obligations.get(obligation_ref, set())
            }
            if not domain_reasons:
                continue
            activated_domains[domain_id] = domain_reasons
            for obligation_ref in domain["obligation_refs"]:
                if obligation_ref not in activated_obligations:
                    continue
                source_row = rows_by_id[obligation_ref]
                active_demands.append(
                    {
                        **copy.deepcopy(source_row),
                        "activation_reasons": sorted(activated_domains[domain_id]),
                        "scope_state": (
                            "ACTIVE_UNRESOLVED"
                            if source_row["terminal"]
                            in {
                                "MISSING_EVIDENCE",
                                "SOURCE_EVIDENCE_INSUFFICIENT",
                                "METHODOLOGY_UNRESOLVED",
                            }
                            else "ACTIVE_AVAILABLE"
                        ),
                    }
                )
        active_demands.sort(key=lambda row: row["demand"])
        active_domain_rows = [
            {
                "domain_id": domain["domain_id"],
                "mode": policies[domain["domain_id"]]["mode"],
                "activation_reasons": sorted(activated_domains[domain["domain_id"]]),
                "active_demand_count": sum(
                    row["domain_id"] == domain["domain_id"] for row in active_demands
                ),
            }
            for domain in definition["domains"]
            if domain["domain_id"] in activated_domains
        ]
        return {
            "schema_version": GATE5_DECLARATION_SCOPE_ACTIVATION_SCHEMA_VERSION,
            "status": "scoped_for_supplied_case",
            "terminals": [GATE5_DECLARATION_SCOPE_ACTIVATION_TERMINAL],
            "evidence_mode": evidence_mode,
            "definition_binding": publication,
            "user_intent": intent,
            "active_domains": active_domain_rows,
            "active_demands": active_demands,
            "metrics": {
                "definition_demands": len(case["declaration_demands"]),
                "active_demands": len(active_demands),
                "inactive_demands_suppressed": (
                    len(case["declaration_demands"]) - len(active_demands)
                ),
                "active_domains": len(active_domain_rows),
                "runtime_questions_created": 0,
            },
            "supplied_case_completeness_only": True,
            "real_world_taxpayer_completeness_asserted": False,
            "absence_converted_to_not_applicable": False,
            "universal_questionnaire_created": False,
        }


def _validated_activation_intent(value: Any) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or set(value) != _ACTIVATION_INTENT_KEYS
        or value.get("schema_version") != GATE5_USER_INTENT_SCHEMA_VERSION
        or value.get("task") != _ACTIVATION_SUPPORTED_TASK
        or not isinstance(value.get("form"), str)
        or not isinstance(value.get("tax_period"), str)
        or not isinstance(value.get("domains"), list)
        or not value["domains"]
        or any(
            item not in _ACTIVATION_SUPPORTED_DOMAIN_INTENTS
            for item in value["domains"]
        )
        or len(value["domains"]) != len(set(value["domains"]))
    ):
        _activation_fail("gate5_scope_activation_intent_invalid")
    return copy.deepcopy(value)


def _validated_activation_case(value: Any, *, evidence_mode: str) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or value.get("schema_version") != GATE5_REAL_TAX_CASE_ASSEMBLY_SCHEMA_VERSION
        or value.get("evidence_mode") != evidence_mode
        or len(value.get("declaration_demands") or []) != 25
    ):
        _activation_fail("gate5_scope_activation_case_invalid")
    return copy.deepcopy(value)


def _activation_fail(code: str) -> None:
    raise Gate5DeclarationScopeActivationError(code)


__all__ = [
    "FACTORY_REQUIRED",
    "FORBIDDEN",
    "GATE5_DECLARATION_SCOPE_ASSERTION_ARTIFACT_TYPE",
    "GATE5_DECLARATION_SCOPE_ASSERTION_SCHEMA_VERSION",
    "GATE5_DECLARATION_SCOPE_ACTIVATION_SCHEMA_VERSION",
    "GATE5_DECLARATION_SCOPE_ACTIVATION_TERMINAL",
    "GATE5_DECLARATION_SCOPE_COMPONENT_EVIDENCE_SCHEMA_VERSION",
    "GATE5_CURRENT_FACT_DECLARATION_SCOPE_RECEIPT_SCHEMA_VERSION",
    "GATE5_DECLARATION_SCOPE_HUMAN_ANSWER_SCHEMA_VERSION",
    "GATE5_DECLARATION_SCOPE_HUMAN_REQUEST_SCHEMA_VERSION",
    "GATE5_DECLARATION_SCOPE_MISSING_SOURCE_INDICATION_SCHEMA_VERSION",
    "GATE5_DECLARATION_SCOPE_MISSING_SOURCE_REQUEST_SCHEMA_VERSION",
    "GATE5_DECLARATION_SCOPE_RECEIPT_SCHEMA_VERSION",
    "GATE5_DECLARATION_SCOPE_SCHEMA_VERSION",
    "GATE5_DECLARATION_SCOPE_SEMANTICS",
    "GATE5_USER_INTENT_SCHEMA_VERSION",
    "Gate5DeclarationScopeActivationError",
    "Gate5DeclarationScopeActivationRuntime",
    "Gate5DeclarationScopeActivationRuntimeFactory",
    "Gate5DeclarationScopeResolutionError",
    "Gate5DeclarationScopeResolutionRuntime",
    "Gate5DeclarationScopeResolutionRuntimeFactory",
]
