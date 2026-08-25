"""Exact, minimal human or document actions for deterministic case gaps."""

from __future__ import annotations

import copy
import hashlib
import json
import re
from datetime import date
from typing import Any

from .artifact_models import (
    ArtifactAccessContext,
    ArtifactRecord,
    ArtifactStoreError,
    ArtifactStorePort,
    RetentionPolicy,
)
from .artifact_resolver import ArtifactResolver

from .gate5_evidence_intake import (
    GATE5_EVIDENCE_INTAKE_SCHEMA_VERSION,
)
from .gate5_client_evidence_review import (
    GATE5_CLIENT_EVIDENCE_REVIEW_SCHEMA_VERSION,
)
from .gate5_evidence_demand import GATE5_GAP_OWNER_CLASSIFICATIONS
from .gate5_declaration_scope_resolution import (
    GATE5_DECLARATION_SCOPE_ACTIVATION_SCHEMA_VERSION,
)
from .gate5_residency_evidence import (
    GATE5_RESIDENCY_CLASSIFICATION_SCHEMA_VERSION,
    GATE5_RESIDENCY_EVIDENCE_PROPOSAL_SCHEMA_VERSION,
    Gate5ResidencyEvidenceRuntimeFactory,
)


GATE5_HUMAN_GAP_CLOSURE_SCHEMA_VERSION = "broker_reports_gate5_human_gap_closure_v1"
GATE5_GAP_REQUEST_SCHEMA_VERSION = "broker_reports_gate5_gap_request_v1"
GATE5_GAP_REQUEST_PUBLICATION_SCHEMA_VERSION = (
    "broker_reports_gate5_gap_request_publication_v1"
)
GATE5_USER_CASE_FACT_SCHEMA_VERSION = "broker_reports_gate5_user_case_fact_v1"
GATE5_LEGACY_USER_CASE_FACT_SCHEMA_VERSION = "broker_reports_gate5_user_case_fact_v0"
GATE5_HUMAN_FACT_SCOPE_SCHEMA_VERSION = "broker_reports_gate5_human_fact_scope_v1"
GATE5_GAP_REQUEST_ARTIFACT_TYPE = GATE5_GAP_REQUEST_SCHEMA_VERSION
GATE5_GAP_REQUEST_PUBLICATION_ARTIFACT_TYPE = (
    GATE5_GAP_REQUEST_PUBLICATION_SCHEMA_VERSION
)
GATE5_USER_CASE_FACT_ARTIFACT_TYPE = GATE5_USER_CASE_FACT_SCHEMA_VERSION
GATE5_HUMAN_GAP_CLOSURE_TERMINAL = "HUMAN_GAP_CLOSURE_LOOP_PROVEN"

FACTORY_REQUIRED = (
    "Gate5HumanGapClosureRuntimeFactory.create consumes typed intake, scoped "
    "declaration demands, deterministic client findings and trusted "
    "ArtifactAccessContext; publish_requests and normalize_answer reuse the "
    "existing ArtifactStore and ArtifactResolver owners",
)
FORBIDDEN = (
    "raw transaction prompt, LLM blocker closure, inferred answer, tax "
    "calculation, methodology mutation, source-document fact fabrication, "
    "caller-published request, hash-only origin, run-bound fact, universal "
    "questionnaire or continuation of stale LLM reasoning",
)

_USER_FACT_KEYS = frozenset(
    {
        "schema_version",
        "user_case_fact_ref",
        "fact_key",
        "value",
        "scope_binding",
        "request_binding",
        "provenance",
        "fact_sha256",
    }
)
_SCOPE_KEYS = frozenset(
    {
        "schema_version",
        "authenticated_user_ref",
        "case_id",
        "taxpayer_scope_ref",
        "tax_period",
        "scope_binding_sha256",
    }
)
_REQUEST_CONTENT_BINDING_KEYS = frozenset(
    {"request_ref", "request_id", "request_sha256"}
)
_REQUEST_BINDING_KEYS = frozenset(
    {
        "request_ref",
        "request_id",
        "request_sha256",
        "request_publication_ref",
    }
)
_REQUEST_KEYS = frozenset(
    {
        "schema_version",
        "kind",
        "priority",
        "closure_type",
        "gap_owner_classification",
        "fact_key",
        "demand_refs",
        "evidence_refs",
        "subject",
        "question",
        "reason",
        "helpful_evidence",
        "client_benefit",
        "answer_contract",
        "scope_binding",
        "semantic_request_key",
        "request_id",
        "request_sha256",
        "request_ref",
    }
)
_REQUEST_PUBLICATION_KEYS = frozenset(
    {
        "schema_version",
        "request_publication_ref",
        "request_lane_sha256",
        "semantic_request_key",
        "scope_binding",
        "fact_key",
        "closure_type",
        "request_binding",
        "predecessor_publication_ref",
        "publication_sha256",
    }
)
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_ARTIFACT_REF = re.compile(r"^art_[A-Fa-f0-9]{32}$")
_KNOWN_FACT_KEYS = {
    "selected_tax_period",
    "profile_mismatch_mode",
    "taxpayer_identity_confirmed",
    "taxpayer_identity",
    "taxpayer_capacity",
    "filing_instance_identity",
    "filing_destination_code",
    "signer_and_representation",
    "budget_disposition",
    "budget_oktmo",
    "residency_evidence",
    "declaration_date",
    "ordinary_trade_declaration_zero_scope_confirmed",
}
_CLOSURE_TYPES = {
    "EXISTING_EVIDENCE",
    "EXTERNAL_AUTHORITY",
    "USER_FACT",
    "ADDITIONAL_DOCUMENT",
    "METHODOLOGY_RESEARCH",
    "OWNER_UNRESOLVED",
}
_USER_FACING_CLOSURE_TYPES = {"USER_FACT", "ADDITIONAL_DOCUMENT"}
_GAP_OWNER_BY_CLOSURE_TYPE = {
    "EXISTING_EVIDENCE": "INTERNAL_CONTRACT_OR_PIPELINE_DEFECT",
    "EXTERNAL_AUTHORITY": "EXTERNAL_AUTHORITATIVE_FACT_MISSING",
    "USER_FACT": "USER_CASE_FACT_MISSING",
    "ADDITIONAL_DOCUMENT": "REAL_SOURCE_EVIDENCE_MISSING",
    "METHODOLOGY_RESEARCH": "METHODOLOGY_RULE_MISSING",
    "OWNER_UNRESOLVED": "INTERNAL_CONTRACT_OR_PIPELINE_DEFECT",
}


class Gate5HumanGapClosureError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class Gate5HumanGapClosureRuntimeFactory:
    @classmethod
    def create(
        cls,
        *,
        store: ArtifactStorePort | None = None,
        retention_policy: RetentionPolicy | None = None,
    ) -> "Gate5HumanGapClosureRuntime":
        return Gate5HumanGapClosureRuntime(
            store=store,
            resolver=ArtifactResolver(store) if store is not None else None,
            retention_policy=retention_policy,
        )


_IDENTITY_METADATA_FACT_TYPES = {
    "PARTY_NAME",
    "PERSON_BIRTH_DATE",
    "PERSON_CITIZENSHIP",
    "TAXPAYER_TAX_IDENTIFIER",
}


class Gate5HumanGapClosureRuntime:
    def __init__(
        self,
        *,
        store: ArtifactStorePort | None,
        resolver: ArtifactResolver | None,
        retention_policy: RetentionPolicy | None,
    ) -> None:
        self._store = store
        self._resolver = resolver
        self._retention_policy = retention_policy

    def plan(
        self,
        *,
        intake: dict[str, Any],
        scope_activation: dict[str, Any],
        client_review: dict[str, Any],
        user_case_facts: list[dict[str, Any]],
        residency_classification: dict[str, Any],
        context: ArtifactAccessContext,
        taxpayer_scope_ref: str,
        tax_period: str,
    ) -> dict[str, Any]:
        _validate_inputs(
            intake=intake,
            scope_activation=scope_activation,
            client_review=client_review,
        )
        scope_binding = _human_fact_scope(
            context=context,
            taxpayer_scope_ref=taxpayer_scope_ref,
            tax_period=tax_period,
        )
        facts = self.validate_user_case_facts(
            user_case_facts,
            context=context,
            taxpayer_scope_ref=taxpayer_scope_ref,
            tax_period=tax_period,
        )
        if (
            not isinstance(residency_classification, dict)
            or residency_classification.get("schema_version")
            != GATE5_RESIDENCY_CLASSIFICATION_SCHEMA_VERSION
        ):
            _fail("gate5_gap_residency_classification_invalid")
        facts_by_key = {item["fact_key"]: item for item in facts}
        known_document_facts_reused = sum(
            item.get("fact_type") in _IDENTITY_METADATA_FACT_TYPES
            for item in intake.get("metadata_facts", [])
        )
        requests: list[dict[str, Any]] = []
        requests.extend(_source_requests(client_review, scope_binding=scope_binding))
        requests.extend(
            _declaration_requests(
                intake=intake,
                scope_activation=scope_activation,
                facts_by_key=facts_by_key,
                source_requests=requests,
                residency_classification=residency_classification,
                scope_binding=scope_binding,
            )
        )
        requests = _deduplicated_requests(requests)
        required = [item for item in requests if item["kind"] == "REQUIRED"]
        advisory = [item for item in requests if item["kind"] == "ADVISORY"]
        deferred = [item for item in requests if item["kind"] == "DEFERRED"]
        user_required = [
            item
            for item in required
            if item["closure_type"] in _USER_FACING_CLOSURE_TYPES
        ]
        internal_required = [
            item
            for item in required
            if item["closure_type"] not in _USER_FACING_CLOSURE_TYPES
        ]
        user_advisory = [
            item
            for item in advisory
            if item["closure_type"] in _USER_FACING_CLOSURE_TYPES
        ]
        internal_advisory = [
            item
            for item in advisory
            if item["closure_type"] not in _USER_FACING_CLOSURE_TYPES
        ]
        return {
            "schema_version": GATE5_HUMAN_GAP_CLOSURE_SCHEMA_VERSION,
            "status": "exact_gap_actions_ready",
            "terminals": [GATE5_HUMAN_GAP_CLOSURE_TERMINAL],
            "required_actions": copy.deepcopy(required),
            "advisory_actions": copy.deepcopy(advisory),
            "deferred_actions": copy.deepcopy(deferred),
            "user_facing_required_actions": copy.deepcopy(user_required),
            "internal_owner_required_actions": copy.deepcopy(internal_required),
            "user_facing_advisory_actions": copy.deepcopy(user_advisory),
            "internal_owner_advisory_actions": copy.deepcopy(internal_advisory),
            "known_user_case_facts": copy.deepcopy(facts),
            "scope_binding": copy.deepcopy(scope_binding),
            "request_publication": "CANDIDATES_NOT_YET_PUBLISHED",
            "search_order": [
                "NORMALIZED_DOCUMENT_FACTS",
                "INTERNAL_SOURCE_OWNER_REVIEW",
                "DOCUMENT_METADATA",
                "OTHER_SUPPLIED_DOCUMENTS",
                "AUTHORITATIVE_EXTERNAL_REFERENCES",
                "USER_OR_ADDITIONAL_DOCUMENT",
            ],
            "llm_adapter_input": {
                "schema_version": "broker_reports_gate5_gap_dialog_adapter_input_v0",
                "required_actions": [_adapter_request(item) for item in user_required],
                "advisory_actions": [_adapter_request(item) for item in user_advisory],
                "internal_owner_action_count": (
                    len(internal_required) + len(internal_advisory)
                ),
                "raw_transactions_supplied": False,
                "may_close_by_assumption": False,
                "calculation_authority": False,
            },
            "replay_contract": {
                "entrypoint": "Gate5DeclarationPreparationRuntimeFactory.create",
                "new_document_route": "ordinary normalization path through Gate 1 to Gate 4",
                "new_user_fact_route": "validated typed user/case fact input",
                "reuse_previous_llm_reasoning_as_authority": False,
            },
            "residency_classification": copy.deepcopy(residency_classification),
            "metrics": {
                "required_actions": len(required),
                "user_facing_required_actions": len(user_required),
                "internal_owner_required_actions": len(internal_required),
                "advisory_actions": len(advisory),
                "deferred_actions": len(deferred),
                "already_known_not_asked": len(facts),
                "known_document_facts_reused": known_document_facts_reused,
                "invented_facts": 0,
                "invented_relations": 0,
                "provider_calls": 0,
            },
        }

    def publish_requests(self, **plan_inputs: Any) -> dict[str, Any]:
        """Build and persist the exact owner-produced requests for one case scope."""

        self._publication_dependencies()
        result = self.plan(**plan_inputs)
        context = plan_inputs.get("context")
        published: dict[str, dict[str, Any]] = {}
        for request in [
            *result["required_actions"],
            *result["advisory_actions"],
            *result["deferred_actions"],
        ]:
            published[request["request_ref"]] = self._persist_request(
                request=request,
                context=context,
            )
        for request in published.values():
            self._reject_stale_request(request=request, context=context)
        for key in (
            "required_actions",
            "advisory_actions",
            "deferred_actions",
            "user_facing_required_actions",
            "internal_owner_required_actions",
            "user_facing_advisory_actions",
            "internal_owner_advisory_actions",
        ):
            result[key] = [published[item["request_ref"]] for item in result[key]]
        for key in ("required_actions", "advisory_actions"):
            result["llm_adapter_input"][key] = [
                {
                    **item,
                    "request_publication_ref": published[item["request_ref"]][
                        "request_publication_ref"
                    ],
                }
                for item in result["llm_adapter_input"][key]
            ]
        return {
            **result,
            "request_publication": "OWNER_PUBLISHED",
            "published_request_refs": sorted(published),
            "published_request_publication_refs": sorted(
                item["request_publication_ref"] for item in published.values()
            ),
        }

    def publish_ordinary_trade_declaration_requests(
        self,
        *,
        context: ArtifactAccessContext,
        taxpayer_scope_ref: str,
        tax_period: str,
        identity_candidates: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Publish the bounded product's user questions through this owner."""

        self._publication_dependencies()
        facts = self.current_user_case_facts(
            context=context,
            taxpayer_scope_ref=taxpayer_scope_ref,
            tax_period=tax_period,
        )
        facts_by_key = {item["fact_key"]: item for item in facts}
        request_facts_by_key = dict(facts_by_key)
        # The current Canonical identity candidate is request content. Re-publish
        # this one lane even after confirmation so a candidate successor makes
        # the old fact stale. If the candidate is unchanged, content addressing
        # reuses the publication and the current fact suppresses the question.
        request_facts_by_key.pop("taxpayer_identity", None)
        requests = _ordinary_trade_product_requests(
            facts_by_key=request_facts_by_key,
            identity_candidates=identity_candidates,
            scope_binding=_human_fact_scope(
                context=context,
                taxpayer_scope_ref=taxpayer_scope_ref,
                tax_period=tax_period,
            ),
        )
        published = []
        for item in requests:
            current_change = self._current_product_change_request(
                request=item,
                context=context,
            )
            published.append(
                current_change
                if current_change is not None
                else self._persist_request(request=item, context=context)
            )
        for request in published:
            self._reject_stale_request(request=request, context=context)
        current_facts = self.current_user_case_facts(
            context=context,
            taxpayer_scope_ref=taxpayer_scope_ref,
            tax_period=tax_period,
        )
        current_fact_keys = {item["fact_key"] for item in current_facts}
        published = [
            item for item in published if item["fact_key"] not in current_fact_keys
        ]
        return {
            "schema_version": "broker_reports_ordinary_trade_user_actions_v1",
            "status": "OWNER_PUBLISHED",
            "scope_binding": _human_fact_scope(
                context=context,
                taxpayer_scope_ref=taxpayer_scope_ref,
                tax_period=tax_period,
            ),
            "actions": published,
            "current_user_case_facts": current_facts,
            "provider_calls_total": 0,
        }

    def publish_tax_period_selection_request(
        self,
        *,
        context: ArtifactAccessContext,
        taxpayer_scope_ref: str,
        detected_operation_years: list[str],
    ) -> dict[str, Any]:
        """Publish/read the case-scoped period choice before a tax scope exists."""

        self._publication_dependencies()
        if (
            not isinstance(detected_operation_years, list)
            or detected_operation_years != sorted(set(detected_operation_years))
            or any(re.fullmatch(r"[0-9]{4}", item) is None for item in detected_operation_years)
        ):
            _fail("gate5_tax_period_detection_invalid")
        neutral_period = "0000"
        scope = _human_fact_scope(
            context=context,
            taxpayer_scope_ref=taxpayer_scope_ref,
            tax_period=neutral_period,
        )
        facts = self.current_user_case_facts(
            context=context,
            taxpayer_scope_ref=taxpayer_scope_ref,
            tax_period=neutral_period,
        )
        selected = next(
            (item for item in facts if item["fact_key"] == "selected_tax_period"),
            None,
        )
        request = _request(
            kind="REQUIRED",
            priority="HIGH",
            closure_type="USER_FACT",
            fact_key="selected_tax_period",
            demand_refs=["ordinary_trade_selected_tax_period"],
            evidence_refs=[],
            question=(
                "Choose the tax period for this case. Detected operation years: "
                + (", ".join(detected_operation_years) if detected_operation_years else "none")
                + "."
            ),
            reason="the filing or analysis period must be explicitly selected",
            helpful_evidence="a four-digit tax year chosen by the authenticated user",
            client_benefit="prevents silently moving source operations into another year",
            answer_contract={"kind": "code", "pattern": "^[0-9]{4}$"},
            subject={"detected_operation_years": detected_operation_years},
            scope_binding=scope,
            semantic_request_key="human_fact:selected_tax_period",
        )
        published = self._persist_request(request=request, context=context)
        self._reject_stale_request(request=published, context=context)
        if selected is not None:
            current = self.current_user_case_facts(
                context=context,
                taxpayer_scope_ref=taxpayer_scope_ref,
                tax_period=neutral_period,
            )
            selected = next(
                (item for item in current if item["fact_key"] == "selected_tax_period"),
                None,
            )
        return {
            "schema_version": "broker_reports_tax_period_selection_v0",
            "status": "SELECTED" if selected is not None else "INPUT_REQUIRED",
            "detected_operation_years": copy.deepcopy(detected_operation_years),
            "selected_tax_period_fact": copy.deepcopy(selected),
            "actions": [] if selected is not None else [published],
            "scope_binding": scope,
            "provider_calls_total": 0,
        }

    def publish_profile_mismatch_mode_request(
        self,
        *,
        context: ArtifactAccessContext,
        taxpayer_scope_ref: str,
        tax_period: str,
    ) -> dict[str, Any]:
        """Offer only non-filing outcomes when the exact year profile is absent."""

        self._publication_dependencies()
        scope = _human_fact_scope(
            context=context,
            taxpayer_scope_ref=taxpayer_scope_ref,
            tax_period=tax_period,
        )
        facts = self.current_user_case_facts(
            context=context,
            taxpayer_scope_ref=taxpayer_scope_ref,
            tax_period=tax_period,
        )
        selected = next(
            (item for item in facts if item["fact_key"] == "profile_mismatch_mode"),
            None,
        )
        request = _request(
            kind="REQUIRED",
            priority="HIGH",
            closure_type="USER_FACT",
            fact_key="profile_mismatch_mode",
            demand_refs=["ordinary_trade_exact_year_profile"],
            evidence_refs=[],
            question=(
                f"The exact declaration profile for {tax_period} is not available. "
                "Choose analysis only, a clearly non-filing surrogate draft, or stop and resume later."
            ),
            reason="a filing artifact cannot use a profile from another tax year",
            helpful_evidence="an explicit non-filing mode choice",
            client_benefit="prevents generating wrong-year filing XML",
            answer_contract={
                "kind": "code",
                "allowed": [
                    "ANALYSIS_ONLY",
                    "SURROGATE_DRAFT",
                    "STOP_RESUMABLE",
                ],
            },
            subject={"tax_period": tax_period, "filing_eligible": False},
            scope_binding=scope,
            semantic_request_key="human_fact:profile_mismatch_mode",
        )
        published = self._persist_request(request=request, context=context)
        self._reject_stale_request(request=published, context=context)
        if selected is not None:
            current = self.current_user_case_facts(
                context=context,
                taxpayer_scope_ref=taxpayer_scope_ref,
                tax_period=tax_period,
            )
            selected = next(
                (item for item in current if item["fact_key"] == "profile_mismatch_mode"),
                None,
            )
        return {
            "schema_version": "broker_reports_profile_mismatch_mode_v0",
            "status": "SELECTED" if selected is not None else "INPUT_REQUIRED",
            "tax_period": tax_period,
            "selected_mode_fact": copy.deepcopy(selected),
            "actions": [] if selected is not None else [published],
            "scope_binding": scope,
            "provider_calls_total": 0,
        }

    def publish_ordinary_trade_declaration_change_request(
        self,
        *,
        context: ArtifactAccessContext,
        taxpayer_scope_ref: str,
        tax_period: str,
        fact_key: str,
        identity_candidates: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Publish an owner-bound successor before changing one current fact."""

        self._publication_dependencies()
        facts = self.current_user_case_facts(
            context=context,
            taxpayer_scope_ref=taxpayer_scope_ref,
            tax_period=tax_period,
        )
        facts_by_key = {item["fact_key"]: item for item in facts}
        current_fact = facts_by_key.get(fact_key)
        if current_fact is None:
            _fail("gate5_user_case_fact_change_target_missing")
        request_facts_by_key = dict(facts_by_key)
        request_facts_by_key.pop(fact_key)
        requests = _ordinary_trade_product_requests(
            facts_by_key=request_facts_by_key,
            identity_candidates=identity_candidates,
            scope_binding=_human_fact_scope(
                context=context,
                taxpayer_scope_ref=taxpayer_scope_ref,
                tax_period=tax_period,
            ),
            change_fact={
                "fact_key": fact_key,
                "user_case_fact_ref": current_fact["user_case_fact_ref"],
            },
        )
        request = next(
            (item for item in requests if item.get("fact_key") == fact_key), None
        )
        if request is None:
            _fail("gate5_user_case_fact_change_target_invalid")
        published = self._persist_request(request=request, context=context)
        self._reject_stale_request(request=published, context=context)
        return published

    def normalize_answer(
        self,
        *,
        request: dict[str, Any],
        answer: dict[str, Any],
        context: ArtifactAccessContext,
    ) -> dict[str, Any]:
        self._publication_dependencies()
        validated = self._resolve_request(request=request, context=context)
        self._reject_stale_request(request=validated, context=context)
        if not isinstance(answer, dict) or set(answer) != {"kind", "value"}:
            _fail("gate5_gap_answer_invalid")
        if validated["closure_type"] == "ADDITIONAL_DOCUMENT":
            if (
                answer.get("kind") != "document_submission"
                or answer.get("value") is not True
            ):
                _fail("gate5_gap_document_answer_invalid")
            return {
                "status": "NORMALIZATION_REQUIRED",
                "request_id": validated["request_id"],
                "typed_user_case_fact": None,
                "route": "ordinary normalization path through Gate 1 to Gate 4",
            }
        if validated["closure_type"] != "USER_FACT":
            _fail("gate5_gap_answer_not_user_fact")
        expected = validated["answer_contract"]
        if answer.get("kind") != expected["kind"]:
            _fail("gate5_gap_answer_kind_invalid")
        value = copy.deepcopy(answer["value"])
        if expected["kind"] == "identity_choice":
            value = _normalized_identity_choice(
                value=value,
                candidate=expected.get("candidate"),
            )
            if value is None:
                return {
                    "status": "USER_CASE_FACT_DEFERRED",
                    "request_id": validated["request_id"],
                    "typed_user_case_fact": None,
                    "route": "deterministic case replay",
                }
        if expected["kind"] == "residency_evidence":
            if not isinstance(value, dict) or set(value) != {
                "human_answer",
                "proposal",
            }:
                _fail("gate5_gap_answer_value_invalid")
            value = (
                Gate5ResidencyEvidenceRuntimeFactory.create().normalize_human_answer(
                    human_answer=value["human_answer"],
                    proposal=value["proposal"],
                    source_ref=validated["request_id"],
                )
            )
        if expected["kind"] == "confirmation" and not isinstance(value, bool):
            _fail("gate5_gap_answer_value_invalid")
        if expected["kind"] in {"text", "code"} and (
            not isinstance(value, str) or not value.strip() or len(value) > 512
        ):
            _fail("gate5_gap_answer_value_invalid")
        if expected.get("allowed") and value not in expected["allowed"]:
            _fail("gate5_gap_answer_value_invalid")
        if expected.get("pattern") and (
            not isinstance(value, str)
            or re.fullmatch(expected["pattern"], value) is None
        ):
            _fail("gate5_gap_answer_value_invalid")
        if validated["fact_key"] == "declaration_date":
            try:
                date.fromisoformat(value)
            except (TypeError, ValueError):
                _fail("gate5_gap_declaration_date_invalid")
        fact = {
            "schema_version": GATE5_USER_CASE_FACT_SCHEMA_VERSION,
            "user_case_fact_ref": "",
            "fact_key": validated["fact_key"],
            "value": {"kind": expected["kind"], "value": value},
            "scope_binding": copy.deepcopy(validated["scope_binding"]),
            "request_binding": {
                "request_ref": validated["request_ref"],
                "request_id": validated["request_id"],
                "request_sha256": validated["request_sha256"],
                "request_publication_ref": validated[
                    "request_publication_ref"
                ],
            },
            "provenance": {
                "source_kind": "USER_ATTESTED_CASE_FACT",
                "provided_by": "authenticated_user",
                "input_channel": "gate5_human_gap_closure_v1",
                "calculation_authority": False,
                "document_source_fact": False,
            },
            "fact_sha256": "",
        }
        fact_material = {
            key: copy.deepcopy(item)
            for key, item in fact.items()
            if key not in {"user_case_fact_ref", "fact_sha256"}
        }
        fact["fact_sha256"] = _sha256(fact_material)
        fact["user_case_fact_ref"] = _artifact_ref(
            {"kind": "user_case_fact", "fact_sha256": fact["fact_sha256"]}
        )
        self._persist_fact(fact=fact, context=context)
        try:
            persisted = self.validate_user_case_facts(
                [fact],
                context=context,
                taxpayer_scope_ref=validated["scope_binding"][
                    "taxpayer_scope_ref"
                ],
                tax_period=validated["scope_binding"]["tax_period"],
            )[0]
        except Gate5HumanGapClosureError as exc:
            if exc.code != "gate5_user_case_fact_conflict":
                raise
            return {
                "status": "USER_CASE_FACT_CONFLICT",
                "request_id": validated["request_id"],
                "typed_user_case_fact": copy.deepcopy(fact),
                "route": "owner_conflict_resolution_required",
            }
        return {
            "status": "TYPED_USER_CASE_FACT_READY",
            "request_id": validated["request_id"],
            "typed_user_case_fact": persisted,
            "route": "deterministic case replay",
        }

    def normalize_published_answer(
        self,
        *,
        request_publication_ref: str,
        answer: dict[str, Any],
        context: ArtifactAccessContext,
    ) -> dict[str, Any]:
        """Resolve the private request by its owner publication before answering."""

        self._publication_dependencies()
        if not _artifact_ref_valid(request_publication_ref):
            _fail("gate5_gap_request_publication_invalid")
        assert self._resolver is not None
        try:
            resolved = self._resolver.resolve_case(
                request_publication_ref, context
            )
        except ArtifactStoreError as exc:
            raise Gate5HumanGapClosureError(
                "gate5_gap_request_publication_invalid"
            ) from exc
        publication = _validated_request_publication(resolved["payload"])
        if (
            resolved["record"].artifact_type
            != GATE5_GAP_REQUEST_PUBLICATION_ARTIFACT_TYPE
        ):
            _fail("gate5_gap_request_publication_invalid")
        request = self._resolve_request_binding(
            binding={
                **publication["request_binding"],
                "request_publication_ref": request_publication_ref,
            },
            context=context,
        )
        return self.normalize_answer(
            request=request,
            answer=answer,
            context=context,
        )

    def validate_user_case_facts(
        self,
        value: list[dict[str, Any]],
        *,
        context: ArtifactAccessContext,
        taxpayer_scope_ref: str,
        tax_period: str,
    ) -> list[dict[str, Any]]:
        scope = _human_fact_scope(
            context=context,
            taxpayer_scope_ref=taxpayer_scope_ref,
            tax_period=tax_period,
        )
        if not isinstance(value, list):
            _fail("gate5_user_case_facts_invalid")
        if not value:
            return []
        if self._resolver is None:
            _fail("gate5_user_case_fact_store_required")
        result: list[dict[str, Any]] = []
        seen: set[str] = set()
        for supplied in value:
            validated = _validated_user_fact_shape(supplied)
            if validated["fact_key"] in seen:
                _fail("gate5_user_case_fact_duplicate")
            seen.add(validated["fact_key"])
            try:
                resolved = self._resolver.resolve_case(
                    validated["user_case_fact_ref"], context
                )
            except ArtifactStoreError as exc:
                raise Gate5HumanGapClosureError(
                    "gate5_user_case_fact_owner_binding_invalid"
                ) from exc
            if (
                resolved["record"].artifact_type != GATE5_USER_CASE_FACT_ARTIFACT_TYPE
                or resolved["payload"] != validated
                or validated["scope_binding"] != scope
            ):
                _fail("gate5_user_case_fact_owner_binding_invalid")
            request = self._resolve_request_binding(
                binding=validated["request_binding"],
                context=context,
            )
            if (
                request["scope_binding"] != scope
                or request.get("closure_type") != "USER_FACT"
                or request.get("fact_key") != validated["fact_key"]
                or request.get("answer_contract", {}).get("kind")
                != validated["value"]["kind"]
            ):
                _fail("gate5_user_case_fact_request_binding_invalid")
            self._reject_stale_request(request=request, context=context)
            self._reject_owner_visible_fact_conflict(
                fact=validated,
                context=context,
            )
            result.append(validated)
        return sorted(result, key=lambda item: item["fact_key"])

    def current_user_case_facts(
        self,
        *,
        context: ArtifactAccessContext,
        taxpayer_scope_ref: str,
        tax_period: str,
    ) -> list[dict[str, Any]]:
        """Return only current request-bound facts from this owner's catalog."""

        self._publication_dependencies()
        scope = _human_fact_scope(
            context=context,
            taxpayer_scope_ref=taxpayer_scope_ref,
            tax_period=tax_period,
        )
        current: list[dict[str, Any]] = []
        assert self._resolver is not None
        for record in self._resolver.catalog_case(context):
            if record.artifact_type != GATE5_USER_CASE_FACT_ARTIFACT_TYPE:
                continue
            resolved = self._resolver.resolve_case(record.artifact_id, context)
            fact = _validated_user_fact_shape(resolved["payload"])
            if fact["scope_binding"] != scope:
                continue
            try:
                self._reject_stale_request(
                    request=self._resolve_request_binding(
                        binding=fact["request_binding"], context=context
                    ),
                    context=context,
                )
            except Gate5HumanGapClosureError as exc:
                if exc.code == "gate5_gap_request_stale":
                    continue
                raise
            current.append(fact)
        return self.validate_user_case_facts(
            current,
            context=context,
            taxpayer_scope_ref=taxpayer_scope_ref,
            tax_period=tax_period,
        )

    def _publication_dependencies(self) -> None:
        if (
            self._store is None
            or self._resolver is None
            or not isinstance(self._retention_policy, RetentionPolicy)
        ):
            _fail("gate5_human_fact_publication_dependencies_required")

    def _current_product_change_request(
        self,
        *,
        request: dict[str, Any],
        context: ArtifactAccessContext,
    ) -> dict[str, Any] | None:
        current = self._current_request_publication(
            request_lane_sha256=_request_lane_sha256(request),
            context=context,
        )
        if current is None:
            return None
        binding = {
            **current["request_binding"],
            "request_publication_ref": current["request_publication_ref"],
        }
        owner_request = self._resolve_request_binding(
            binding=binding,
            context=context,
        )
        contract = owner_request.get("answer_contract")
        contract = contract if isinstance(contract, dict) else {}
        if (
            owner_request.get("fact_key") != request.get("fact_key")
            or owner_request.get("semantic_request_key")
            != request.get("semantic_request_key")
            or owner_request.get("scope_binding") != request.get("scope_binding")
            or not _artifact_ref_valid(contract.get("change_of_user_case_fact_ref"))
        ):
            return None
        return {
            **owner_request,
            "request_publication_ref": current["request_publication_ref"],
        }

    def _persist_request(
        self, *, request: dict[str, Any], context: ArtifactAccessContext
    ) -> dict[str, Any]:
        validated = _validated_request(request)
        if validated["scope_binding"] != _human_fact_scope(
            context=context,
            taxpayer_scope_ref=validated["scope_binding"]["taxpayer_scope_ref"],
            tax_period=validated["scope_binding"]["tax_period"],
        ):
            _fail("gate5_gap_request_scope_invalid")
        self._put_or_reuse(
            artifact_ref=validated["request_ref"],
            artifact_type=GATE5_GAP_REQUEST_ARTIFACT_TYPE,
            payload=validated,
            context=context,
        )
        publication = self._publish_current_request(
            request=validated,
            context=context,
        )
        return {
            **validated,
            "request_publication_ref": publication["request_publication_ref"],
        }

    def _publish_current_request(
        self, *, request: dict[str, Any], context: ArtifactAccessContext
    ) -> dict[str, Any]:
        lane_sha256 = _request_lane_sha256(request)
        current = self._current_request_publication(
            request_lane_sha256=lane_sha256,
            context=context,
        )
        request_binding = _request_content_binding(request)
        if current is not None and current["request_binding"] == request_binding:
            return current
        base = {
            "schema_version": GATE5_GAP_REQUEST_PUBLICATION_SCHEMA_VERSION,
            "request_lane_sha256": lane_sha256,
            "semantic_request_key": request["semantic_request_key"],
            "scope_binding": copy.deepcopy(request["scope_binding"]),
            "fact_key": request.get("fact_key"),
            "closure_type": request["closure_type"],
            "request_binding": request_binding,
            "predecessor_publication_ref": (
                None if current is None else current["request_publication_ref"]
            ),
        }
        publication_sha256 = _sha256(base)
        with_hash = {**base, "publication_sha256": publication_sha256}
        publication = {
            **with_hash,
            "request_publication_ref": _artifact_ref(
                {"kind": "gap_request_publication", "publication": with_hash}
            ),
        }
        self._put_or_reuse(
            artifact_ref=publication["request_publication_ref"],
            artifact_type=GATE5_GAP_REQUEST_PUBLICATION_ARTIFACT_TYPE,
            payload=publication,
            context=context,
        )
        resolved_current = self._current_request_publication(
            request_lane_sha256=lane_sha256,
            context=context,
        )
        if resolved_current != publication:
            _fail("gate5_gap_request_publication_conflict")
        return publication

    def _persist_fact(
        self, *, fact: dict[str, Any], context: ArtifactAccessContext
    ) -> None:
        validated = _validated_user_fact_shape(fact)
        self._put_or_reuse(
            artifact_ref=validated["user_case_fact_ref"],
            artifact_type=GATE5_USER_CASE_FACT_ARTIFACT_TYPE,
            payload=validated,
            context=context,
        )

    def _put_or_reuse(
        self,
        *,
        artifact_ref: str,
        artifact_type: str,
        payload: dict[str, Any],
        context: ArtifactAccessContext,
    ) -> None:
        assert self._store is not None
        assert self._resolver is not None
        assert isinstance(self._retention_policy, RetentionPolicy)
        existing = self._store.get_record_unchecked(artifact_ref)
        if existing is not None:
            try:
                resolved = self._resolver.resolve_case(artifact_ref, context)
            except ArtifactStoreError as exc:
                raise Gate5HumanGapClosureError(
                    "gate5_human_fact_artifact_conflict"
                ) from exc
            if (
                resolved["record"].artifact_type != artifact_type
                or resolved["payload"] != payload
            ):
                _fail("gate5_human_fact_artifact_conflict")
            return
        self._store.put_record(
            ArtifactRecord(
                artifact_id=artifact_ref,
                artifact_type=artifact_type,
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
                    "requires_workspace_model_id_when_present": True,
                },
                validation_status="validated",
                lifecycle_status="private_ready",
                payload=copy.deepcopy(payload),
                safe_metadata={
                    "schema_version": payload["schema_version"],
                    "tax_period": payload["scope_binding"]["tax_period"],
                    "fact_key": payload.get("fact_key"),
                },
            )
        )

    def _resolve_request(
        self, *, request: dict[str, Any], context: ArtifactAccessContext
    ) -> dict[str, Any]:
        validated = _validated_request(request)
        if not _artifact_ref_valid(validated.get("request_publication_ref")):
            _fail("gate5_gap_request_publication_required")
        resolved = self._resolve_request_binding(
            binding={
                "request_ref": validated["request_ref"],
                "request_id": validated["request_id"],
                "request_sha256": validated["request_sha256"],
                "request_publication_ref": validated[
                    "request_publication_ref"
                ],
            },
            context=context,
        )
        if resolved != validated:
            _fail("gate5_gap_request_owner_binding_invalid")
        return resolved

    def _resolve_request_binding(
        self, *, binding: dict[str, Any], context: ArtifactAccessContext
    ) -> dict[str, Any]:
        if not isinstance(binding, dict) or set(binding) != _REQUEST_BINDING_KEYS:
            _fail("gate5_user_case_fact_request_binding_invalid")
        if self._resolver is None:
            _fail("gate5_user_case_fact_store_required")
        try:
            resolved = self._resolver.resolve_case(binding.get("request_ref"), context)
        except ArtifactStoreError as exc:
            raise Gate5HumanGapClosureError(
                "gate5_gap_request_owner_binding_invalid"
            ) from exc
        request_content = _validated_request(resolved["payload"])
        if (
            resolved["record"].artifact_type != GATE5_GAP_REQUEST_ARTIFACT_TYPE
            or request_content["request_ref"] != binding.get("request_ref")
            or request_content["request_id"] != binding.get("request_id")
            or request_content["request_sha256"] != binding.get("request_sha256")
        ):
            _fail("gate5_gap_request_owner_binding_invalid")
        try:
            publication_record = self._resolver.resolve_case(
                binding.get("request_publication_ref"), context
            )
        except ArtifactStoreError as exc:
            raise Gate5HumanGapClosureError(
                "gate5_gap_request_publication_invalid"
            ) from exc
        publication = _validated_request_publication(
            publication_record["payload"]
        )
        if (
            publication_record["record"].artifact_type
            != GATE5_GAP_REQUEST_PUBLICATION_ARTIFACT_TYPE
            or publication["request_publication_ref"]
            != binding.get("request_publication_ref")
            or publication["request_binding"]
            != _request_content_binding(request_content)
            or publication["semantic_request_key"]
            != request_content["semantic_request_key"]
            or publication["request_lane_sha256"]
            != _request_lane_sha256(request_content)
        ):
            _fail("gate5_gap_request_publication_invalid")
        return {
            **request_content,
            "request_publication_ref": publication[
                "request_publication_ref"
            ],
        }

    def _reject_stale_request(
        self, *, request: dict[str, Any], context: ArtifactAccessContext
    ) -> None:
        current = self._current_request_publication(
            request_lane_sha256=_request_lane_sha256(request),
            context=context,
        )
        if (
            current is None
            or current["request_publication_ref"]
            != request.get("request_publication_ref")
        ):
            _fail("gate5_gap_request_stale")

    def _current_request_publication(
        self,
        *,
        request_lane_sha256: str,
        context: ArtifactAccessContext,
    ) -> dict[str, Any] | None:
        assert self._resolver is not None
        publications: dict[str, dict[str, Any]] = {}
        for record in self._resolver.catalog_case(context):
            if record.artifact_type != GATE5_GAP_REQUEST_PUBLICATION_ARTIFACT_TYPE:
                continue
            resolved = self._resolver.resolve_case(record.artifact_id, context)
            publication = _validated_request_publication(resolved["payload"])
            if publication["request_lane_sha256"] != request_lane_sha256:
                continue
            request_record = self._resolver.resolve_case(
                publication["request_binding"]["request_ref"], context
            )
            request = _validated_request(request_record["payload"])
            if (
                request_record["record"].artifact_type
                != GATE5_GAP_REQUEST_ARTIFACT_TYPE
                or publication["request_binding"]
                != _request_content_binding(request)
                or publication["semantic_request_key"]
                != request["semantic_request_key"]
                or publication["request_lane_sha256"]
                != _request_lane_sha256(request)
                or publication["scope_binding"] != request["scope_binding"]
                or publication["fact_key"] != request.get("fact_key")
                or publication["closure_type"] != request["closure_type"]
            ):
                _fail("gate5_gap_request_publication_invalid")
            publications[publication["request_publication_ref"]] = publication
        if not publications:
            return None
        children: dict[str, list[str]] = {
            publication_ref: [] for publication_ref in publications
        }
        roots = []
        for publication_ref, publication in publications.items():
            predecessor = publication["predecessor_publication_ref"]
            if predecessor is None:
                roots.append(publication_ref)
                continue
            if predecessor not in publications:
                _fail("gate5_gap_request_publication_conflict")
            children[predecessor].append(publication_ref)
        tips = [ref for ref, successors in children.items() if not successors]
        if (
            len(roots) != 1
            or len(tips) != 1
            or any(len(successors) > 1 for successors in children.values())
        ):
            _fail("gate5_gap_request_publication_conflict")
        visited = set()
        cursor = roots[0]
        while cursor not in visited:
            visited.add(cursor)
            successors = children[cursor]
            if not successors:
                break
            cursor = successors[0]
        if len(visited) != len(publications) or cursor != tips[0]:
            _fail("gate5_gap_request_publication_conflict")
        return publications[tips[0]]

    def _reject_owner_visible_fact_conflict(
        self, *, fact: dict[str, Any], context: ArtifactAccessContext
    ) -> None:
        assert self._resolver is not None
        versions = set()
        for record in self._resolver.catalog_case(context):
            if record.artifact_type != GATE5_USER_CASE_FACT_ARTIFACT_TYPE:
                continue
            resolved = self._resolver.resolve_case(record.artifact_id, context)
            candidate = _validated_user_fact_shape(resolved["payload"])
            if (
                candidate["scope_binding"] == fact["scope_binding"]
                and candidate["fact_key"] == fact["fact_key"]
                and candidate["request_binding"] == fact["request_binding"]
            ):
                versions.add(candidate["fact_sha256"])
        if len(versions) > 1:
            _fail("gate5_user_case_fact_conflict")


def _ordinary_trade_product_requests(
    *,
    facts_by_key: dict[str, dict[str, Any]],
    identity_candidates: list[dict[str, Any]],
    scope_binding: dict[str, Any],
    change_fact: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    candidate = _identity_candidate_from_metadata(identity_candidates)
    definitions = (
        (
            "taxpayer_identity",
            "Confirm the taxpayer INN and name found in the current document, "
            "replace them, or fill them later.",
            "taxpayer identity is required only for official XML fields",
            {
                "kind": "identity_choice",
                "candidate": candidate,
                "required_for": "DECLARATION_XML_READY",
            },
            ["obl_taxpayer_identity_and_period_status"],
        ),
        (
            "taxpayer_capacity",
            "State whether the taxpayer is an ordinary individual, an individual "
            "entrepreneur, or a private-practice professional for 2025.",
            "taxpayer capacity changes the supported declaration scope",
            {
                "kind": "code",
                "allowed": [
                    "individual_not_ip_not_private_practice",
                    "individual_entrepreneur",
                    "private_practice_professional",
                ],
                "required_for": "DRAFT_READY",
            },
            ["obl_taxpayer_identity_and_period_status"],
        ),
        (
            "residency_evidence",
            "Provide complete 2025 presence and absence intervals for the "
            "published residency methodology; do not provide only a tax conclusion.",
            "residency evidence is required before calculation",
            {
                "kind": "residency_evidence",
                "proposal_schema_version": (
                    GATE5_RESIDENCY_EVIDENCE_PROPOSAL_SCHEMA_VERSION
                ),
                "required_for": "DRAFT_READY",
            },
            ["obl_taxpayer_identity_and_period_status"],
        ),
        (
            "ordinary_trade_declaration_zero_scope_confirmed",
            "Confirm that this bounded declaration has no other income in the "
            "selected group, deductions, loss claims, credits or withheld tax.",
            "the calculation scope cannot be inferred from one broker operation",
            {
                "kind": "confirmation",
                "required_for": "DRAFT_READY",
            },
            [
                "obl_income_group_tax_base_results",
                "obl_income_group_tax_settlement_results",
            ],
        ),
        (
            "filing_instance_identity",
            "Choose initial filing or correction for the 2025 declaration.",
            "filing instance is required for official XML",
            {
                "kind": "code",
                "allowed": ["INITIAL", "CORRECTION"],
                "required_for": "DECLARATION_XML_READY",
            },
            ["obl_filing_instance_identity"],
        ),
        (
            "declaration_date",
            "Provide the declaration date in YYYY-MM-DD format.",
            "the declaration date must not be invented",
            {
                "kind": "text",
                "pattern": "^[0-9]{4}-[0-9]{2}-[0-9]{2}$",
                "required_for": "DECLARATION_XML_READY",
            },
            ["obl_filing_instance_identity"],
        ),
        (
            "filing_destination_code",
            "Provide the exact four-digit destination inspection code, or fill it later.",
            "the destination code must be user supplied or owner derived, never guessed",
            {
                "kind": "code",
                "pattern": "^[0-9]{4}$",
                "required_for": "DECLARATION_XML_READY",
            },
            ["obl_filing_instance_identity"],
        ),
        (
            "signer_and_representation",
            "State whether the taxpayer signs personally or through a representative.",
            "signer capacity is required for official XML",
            {
                "kind": "code",
                "allowed": ["SELF", "REPRESENTATIVE"],
                "required_for": "DECLARATION_XML_READY",
            },
            ["obl_signer_and_representation_authority"],
        ),
        (
            "budget_disposition",
            "Choose payment, additional payment, reduction or refund disposition.",
            "budget disposition is required for official XML",
            {
                "kind": "code",
                "allowed": [
                    "PAYMENT",
                    "ADDITIONAL_PAYMENT",
                    "REDUCTION",
                    "REFUND",
                ],
                "required_for": "DECLARATION_XML_READY",
            },
            ["obl_declaration_budget_disposition"],
        ),
        (
            "budget_oktmo",
            "Provide the exact 8- or 11-digit OKTMO for the budget result, or fill it later.",
            "OKTMO must be exact and must not be guessed",
            {
                "kind": "code",
                "pattern": "^[0-9]{8}(?:[0-9]{3})?$",
                "required_for": "DECLARATION_XML_READY",
            },
            ["obl_declaration_budget_disposition"],
        ),
    )
    requests: list[dict[str, Any]] = []
    for fact_key, question, reason, answer_contract, demand_refs in definitions:
        if fact_key in facts_by_key:
            continue
        effective_answer_contract = copy.deepcopy(answer_contract)
        if change_fact is not None and change_fact.get("fact_key") == fact_key:
            effective_answer_contract["change_of_user_case_fact_ref"] = change_fact[
                "user_case_fact_ref"
            ]
        requests.append(
            _request(
                kind="REQUIRED",
                priority=(
                    "HIGH"
                    if effective_answer_contract["required_for"] == "DRAFT_READY"
                    else "LOW"
                ),
                closure_type="USER_FACT",
                fact_key=fact_key,
                demand_refs=demand_refs,
                evidence_refs=(
                    list(candidate.get("source_fact_refs", []))
                    if fact_key == "taxpayer_identity" and candidate
                    else []
                ),
                question=question,
                reason=reason,
                helpful_evidence="current authenticated user answer",
                client_benefit="keeps declaration values explicit and reviewable",
                answer_contract=effective_answer_contract,
                subject={"profile": "ordinary_trade_declaration_mvp_2025"},
                scope_binding=scope_binding,
                semantic_request_key="human_fact:" + fact_key,
            )
        )
    return _deduplicated_requests(requests)


def _identity_candidate_from_metadata(
    facts: list[dict[str, Any]],
) -> dict[str, Any] | None:
    by_type: dict[str, list[dict[str, Any]]] = {}
    for item in facts:
        if isinstance(item, dict):
            by_type.setdefault(str(item.get("fact_type") or ""), []).append(item)
    inns = by_type.get("TAXPAYER_TAX_IDENTIFIER", [])
    names = by_type.get("PARTY_NAME", [])
    if len(inns) != 1 or len(names) != 1:
        return None
    try:
        name_parts = names[0]["value"]["normalized"].split()
        if len(name_parts) not in {2, 3}:
            return None
        candidate = {
            "inn": inns[0]["value"]["normalized"],
            "last_name": name_parts[0],
            "first_name": name_parts[1],
            "middle_name": name_parts[2] if len(name_parts) == 3 else "",
            "source_fact_refs": sorted([inns[0]["fact_id"], names[0]["fact_id"]]),
        }
    except (KeyError, TypeError):
        return None
    return candidate if _valid_identity(candidate, source_refs_required=True) else None


def _normalized_identity_choice(
    *, value: Any, candidate: Any
) -> dict[str, Any] | None:
    if not isinstance(value, dict) or set(value) != {"choice", "identity"}:
        _fail("gate5_gap_answer_value_invalid")
    choice = value.get("choice")
    if choice == "DEFER" and value.get("identity") is None:
        return None
    if choice == "CONFIRM" and value.get("identity") is None:
        if not _valid_identity(candidate, source_refs_required=True):
            _fail("gate5_gap_identity_candidate_missing")
        return copy.deepcopy(candidate)
    if choice == "CHANGE" and _valid_identity(
        value.get("identity"), source_refs_required=False
    ):
        return {
            "inn": value["identity"]["inn"],
            "last_name": value["identity"]["last_name"],
            "first_name": value["identity"]["first_name"],
            "middle_name": value["identity"]["middle_name"],
            "source_fact_refs": [],
        }
    changed = value.get("identity") if choice == "CHANGE" else None
    if (
        isinstance(changed, dict)
        and re.fullmatch(r"[0-9]{12}", str(changed.get("inn") or ""))
        and not _inn12_checksum_valid(changed["inn"])
    ):
        _fail("gate5_gap_taxpayer_inn_checksum_invalid")
    _fail("gate5_gap_answer_value_invalid")


def _valid_identity(value: Any, *, source_refs_required: bool) -> bool:
    if not isinstance(value, dict) or set(value) != {
        "inn",
        "last_name",
        "first_name",
        "middle_name",
        "source_fact_refs",
    }:
        return False
    inn = value.get("inn")
    refs = value.get("source_fact_refs")
    return bool(
        isinstance(inn, str)
        and re.fullmatch(r"[0-9]{12}", inn)
        and _inn12_checksum_valid(inn)
        and all(
            isinstance(value.get(key), str)
            and (value[key].strip() or key == "middle_name")
            and len(value[key]) <= 80
            for key in ("last_name", "first_name", "middle_name")
        )
        and isinstance(refs, list)
        and all(_identifier(item) for item in refs)
        and (bool(refs) if source_refs_required else not refs)
    )


def _inn12_checksum_valid(value: str) -> bool:
    if re.fullmatch(r"[0-9]{12}", value) is None:
        return False
    digits = [int(item) for item in value]
    check_11 = sum(
        weight * digit
        for weight, digit in zip((7, 2, 4, 10, 3, 5, 9, 4, 6, 8), digits[:10])
    )
    check_12 = sum(
        weight * digit
        for weight, digit in zip(
            (3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8), digits[:11]
        )
    )
    return check_11 % 11 % 10 == digits[10] and check_12 % 11 % 10 == digits[11]


def _source_requests(
    review: dict[str, Any], *, scope_binding: dict[str, Any]
) -> list[dict[str, Any]]:
    requests: list[dict[str, Any]] = []
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for finding in review["required_blockers"]:
        subject = finding["subject"]
        routing = _validated_routing(finding.get("routing"))
        if finding["closure_type"] != routing["closure_type"]:
            _fail("gate5_gap_owner_routing_invalid")
        group_key = (
            finding["closure_type"],
            finding["reason_code"],
            routing["route"],
            routing["owner"],
            subject.get("asset"),
            subject.get("currency"),
        )
        grouped.setdefault(group_key, []).append(finding)
    for group in grouped.values():
        first = group[0]
        quantitative = first["quantitative_gap"]
        minimum_gap = quantitative.get("minimum_missing_quantity")
        subject = first["subject"]
        routing = _validated_routing(first.get("routing"))
        if routing["user_or_additional_document_allowed"]:
            if first["closure_type"] != "ADDITIONAL_DOCUMENT":
                _fail("gate5_gap_external_route_invalid")
        elif first["closure_type"] in _USER_FACING_CLOSURE_TYPES:
            _fail("gate5_gap_internal_route_exposed_to_user")
        if minimum_gap is not None and first["closure_type"] == "ADDITIONAL_DOCUMENT":
            prompt = (
                "A disposal is documented, but acquisition evidence covers less "
                "than the required quantity. Please provide an earlier broker "
                f"statement or other acquisition document for at least {minimum_gap} "
                "additional units of the exact instrument and currency."
            )
            answer_contract = {"kind": "document_submission"}
        elif first["closure_type"] == "ADDITIONAL_DOCUMENT":
            prompt = (
                "The supplied source fact cannot satisfy the deterministic tax "
                f"input because {first['reason_code']}. Please provide the specific "
                "source document described in helpful_evidence."
            )
            answer_contract = {"kind": "document_submission"}
        elif first["closure_type"] == "EXISTING_EVIDENCE":
            prompt = (
                f"Internal action {routing['route']}: replay the existing source "
                f"through {routing['owner']}; do not ask the user for evidence."
            )
            answer_contract = {
                "kind": "owner_replay",
                "owner": routing["owner"],
            }
        elif first["closure_type"] == "METHODOLOGY_RESEARCH":
            prompt = (
                "Internal methodology action: resolve the published-methodology "
                "gap through its existing authority; do not ask the user."
            )
            answer_contract = {
                "kind": "methodology_review",
                "owner": routing["owner"],
            }
        elif first["closure_type"] == "EXTERNAL_AUTHORITY":
            prompt = (
                "External-authority action: resolve the authoritative reference "
                "through its existing owner; do not ask the user to restate it."
            )
            answer_contract = {
                "kind": "external_authority_review",
                "owner": routing["owner"],
            }
        else:
            prompt = (
                "Internal ownership is unresolved. Stop and assign an explicit "
                "owner; do not ask the user for another document."
            )
            answer_contract = {"kind": "owner_resolution"}
        requests.append(
            _request(
                kind="REQUIRED",
                priority="HIGH",
                closure_type=first["closure_type"],
                fact_key=None,
                demand_refs=sorted(
                    {
                        demand
                        for finding in group
                        for demand in finding["consumer_demands"]
                    }
                ),
                evidence_refs=sorted(finding["finding_id"] for finding in group),
                question=prompt,
                reason=first["why"],
                helpful_evidence=first["helpful_evidence"],
                client_benefit=first["client_benefit_rationale"],
                answer_contract=answer_contract,
                subject=subject,
                routing=routing,
                scope_binding=scope_binding,
                semantic_request_key=_source_gap_semantic_request_key(first),
            )
        )
    for finding in review["advisory_findings"]:
        requests.append(
            _request(
                kind="ADVISORY",
                priority=finding["priority"],
                closure_type=finding["closure_type"],
                fact_key=None,
                demand_refs=finding["consumer_demands"],
                evidence_refs=[finding["finding_id"]],
                question=(
                    "If available, provide the additional document described in "
                    "helpful_evidence; this is recommended and does not become a "
                    "hard blocker by itself."
                ),
                reason=finding["why"],
                helpful_evidence=finding["helpful_evidence"],
                client_benefit=finding["client_benefit_rationale"],
                answer_contract={"kind": "document_submission"},
                subject=finding["subject"],
                scope_binding=scope_binding,
                semantic_request_key="source_advisory:withholding_evidence",
            )
        )
    return requests


def _source_gap_semantic_request_key(finding: dict[str, Any]) -> str:
    """Preserve the source-review owner's grouping identity across request state."""

    subject = finding.get("subject")
    if (
        not isinstance(finding.get("reason_code"), str)
        or not finding["reason_code"]
        or not isinstance(subject, dict)
    ):
        _fail("gate5_gap_semantic_request_key_invalid")
    return "source_gap:" + _sha256(
        {
            "reason_code": finding["reason_code"],
            "asset": subject.get("asset"),
            "currency": subject.get("currency"),
        }
    )[:32]


def _declaration_requests(
    *,
    intake: dict[str, Any],
    scope_activation: dict[str, Any],
    facts_by_key: dict[str, dict[str, Any]],
    source_requests: list[dict[str, Any]],
    residency_classification: dict[str, Any],
    scope_binding: dict[str, Any],
) -> list[dict[str, Any]]:
    active = {item["demand"] for item in scope_activation["active_demands"]}
    metadata = intake["metadata_facts"]
    requests: list[dict[str, Any]] = []
    filing_demands = {
        "obl_filing_instance_identity",
        "obl_taxpayer_identity_and_period_status",
        "obl_signer_and_representation_authority",
    }
    if active & filing_demands:
        party_facts = [
            item
            for item in metadata
            if item["fact_type"] in _IDENTITY_METADATA_FACT_TYPES
        ]
        if "taxpayer_identity_confirmed" not in facts_by_key:
            requests.append(
                _request(
                    kind="REQUIRED",
                    priority="HIGH",
                    closure_type="USER_FACT",
                    fact_key="taxpayer_identity_confirmed",
                    demand_refs=["obl_taxpayer_identity_and_period_status"],
                    evidence_refs=[item["fact_id"] for item in party_facts],
                    question=(
                        "Confirm that the taxpayer for this declaration is the person "
                        "named in the supplied broker evidence."
                        if party_facts
                        else "Provide and confirm the taxpayer identity for this declaration."
                    ),
                    reason="authenticated taxpayer identity is required",
                    helpful_evidence="authenticated user confirmation",
                    client_benefit="prevents filing for the wrong taxpayer",
                    answer_contract={"kind": "confirmation"},
                    subject={},
                    scope_binding=scope_binding,
                    semantic_request_key="human_fact:taxpayer_identity_confirmed",
                )
            )
        if residency_classification["status"] == "INSUFFICIENT_EVIDENCE":
            requests.append(
                _request(
                    kind="REQUIRED",
                    priority="HIGH",
                    closure_type="USER_FACT",
                    fact_key="residency_evidence",
                    demand_refs=["obl_taxpayer_identity_and_period_status"],
                    evidence_refs=[],
                    question=(
                        "Describe the dates or intervals when you were physically present "
                        "in and absent from Russia during 2025, and state any relevant "
                        "absence reasons or exception documents. Do not answer only with "
                        "a resident/non-resident conclusion."
                    ),
                    reason=residency_classification["reason"],
                    helpful_evidence=(
                        "complete dated presence/absence intervals and factual absence-reason evidence"
                    ),
                    client_benefit=(
                        "allows the published residency methodology to classify period status without accepting a user tax conclusion"
                    ),
                    answer_contract={
                        "kind": "residency_evidence",
                        "proposal_schema_version": (
                            GATE5_RESIDENCY_EVIDENCE_PROPOSAL_SCHEMA_VERSION
                        ),
                    },
                    subject={"tax_period": "2025"},
                    scope_binding=scope_binding,
                    semantic_request_key="human_fact:residency_evidence",
                )
            )
        if "filing_instance_identity" not in facts_by_key:
            requests.append(
                _request(
                    kind="REQUIRED",
                    priority="HIGH",
                    closure_type="USER_FACT",
                    fact_key="filing_instance_identity",
                    demand_refs=["obl_filing_instance_identity"],
                    evidence_refs=[],
                    question=(
                        "Choose whether the 2025 declaration is an initial filing "
                        "or a correction."
                    ),
                    reason="filing instance election is absent from broker evidence",
                    helpful_evidence="authenticated initial-or-correction election",
                    client_benefit="prevents projection to the wrong filing instance",
                    answer_contract={
                        "kind": "code",
                        "allowed": ["INITIAL", "CORRECTION"],
                    },
                    subject={},
                    scope_binding=scope_binding,
                    semantic_request_key="human_fact:filing_instance_identity",
                )
            )
        if "declaration_date" not in facts_by_key:
            requests.append(
                _request(
                    kind="REQUIRED",
                    priority="HIGH",
                    closure_type="USER_FACT",
                    fact_key="declaration_date",
                    demand_refs=["obl_filing_instance_identity"],
                    evidence_refs=[],
                    question=(
                        "Provide the declaration signing date in YYYY-MM-DD format."
                    ),
                    reason="declaration date is absent from broker evidence",
                    helpful_evidence="authenticated declaration signing date",
                    client_benefit="prevents an invented declaration date",
                    answer_contract={"kind": "text"},
                    subject={},
                    scope_binding=scope_binding,
                    semantic_request_key="human_fact:declaration_date",
                )
            )
        if "ordinary_trade_declaration_zero_scope_confirmed" not in facts_by_key:
            requests.append(
                _request(
                    kind="REQUIRED",
                    priority="HIGH",
                    closure_type="USER_FACT",
                    fact_key="ordinary_trade_declaration_zero_scope_confirmed",
                    demand_refs=[
                        "obl_income_group_tax_base_results",
                        "obl_income_group_tax_settlement_results",
                    ],
                    evidence_refs=[],
                    question=(
                        "Confirm for this bounded ordinary-trade declaration that "
                        "there is no other income in the selected group, no non-taxable "
                        "income, deductions, loss claim, tax credits, withheld tax, or "
                        "simplified-procedure return/credit to declare."
                    ),
                    reason=(
                        "zero-valued declaration scope cannot be inferred from broker "
                        "operations"
                    ),
                    helpful_evidence="authenticated closed zero-scope confirmation",
                    client_benefit="prevents omitted income, deductions, losses or credits",
                    answer_contract={"kind": "confirmation"},
                    subject={"profile": "ordinary_trade_declaration_mvp_2025"},
                    scope_binding=scope_binding,
                    semantic_request_key=(
                        "human_fact:ordinary_trade_declaration_zero_scope_confirmed"
                    ),
                )
            )
        if "obl_filing_instance_identity" in active:
            requests.append(
                _request(
                    kind="REQUIRED",
                    priority="HIGH",
                    closure_type="EXTERNAL_AUTHORITY",
                    fact_key=None,
                    demand_refs=["obl_filing_instance_identity"],
                    evidence_refs=[],
                    question=(
                        "Resolve the declaration destination/inspection through "
                        "the existing External Authority owner; do not ask the "
                        "user to supply an authority code as a Human fact."
                    ),
                    reason=(
                        "destination tax authority is not a Human factual/elective "
                        "authority"
                    ),
                    helpful_evidence=(
                        "an owner-validated destination/inspection authority binding"
                    ),
                    client_benefit="prevents filing to an unverified destination",
                    answer_contract={
                        "kind": "external_authority_review",
                        "owner": "authoritative_external_reference_owner",
                    },
                    subject={"tax_period": scope_binding["tax_period"]},
                    scope_binding=scope_binding,
                    semantic_request_key="external_authority:filing_destination",
                )
            )
        if "signer_and_representation" not in facts_by_key:
            requests.append(
                _request(
                    kind="REQUIRED",
                    priority="HIGH",
                    closure_type="USER_FACT",
                    fact_key="signer_and_representation",
                    demand_refs=["obl_signer_and_representation_authority"],
                    evidence_refs=[],
                    question=(
                        "State whether the taxpayer signs personally or a representative "
                        "signs with supporting authority."
                    ),
                    reason="signer authority is not a broker-document fact",
                    helpful_evidence="authenticated signer instruction and authority if represented",
                    client_benefit="prevents an unauthorised filing",
                    answer_contract={
                        "kind": "code",
                        "allowed": ["SELF", "REPRESENTATIVE"],
                    },
                    subject={},
                    scope_binding=scope_binding,
                    semantic_request_key="human_fact:signer_and_representation",
                )
            )
    source_demands = {
        "obl_russian_source_taxable_income",
        "obl_foreign_source_taxable_income_and_foreign_tax",
    }
    source_rows = [
        item
        for item in scope_activation["active_demands"]
        if item["demand"] in source_demands
        and item["terminal"] == "METHODOLOGY_UNRESOLVED"
    ]
    if source_rows:
        requests.append(
            _request(
                kind="REQUIRED",
                priority="HIGH",
                closure_type="METHODOLOGY_RESEARCH",
                fact_key=None,
                demand_refs=sorted(item["demand"] for item in source_rows),
                evidence_refs=sorted(
                    {
                        fact_id
                        for item in source_rows
                        for fact_id in item["available_evidence"]["fact_ids"]
                    }
                ),
                question=(
                    "Close the reviewed income-source and foreign-tax methodology "
                    "for the already retained broker-reported facts."
                ),
                reason=(
                    "income-source classification and foreign-tax credit treatment "
                    "belong to Gate 5 methodology; a second document must not be "
                    "requested merely to repeat broker-reported withholding"
                ),
                helpful_evidence=(
                    "the retained broker income, withholding and adjustment facts, "
                    "plus external treaty authority only where credit treatment needs it"
                ),
                client_benefit="supports the correct source schedule and foreign-tax treatment",
                answer_contract={"kind": "internal_methodology_decision"},
                subject={},
                scope_binding=scope_binding,
                semantic_request_key="methodology:income_source_and_foreign_tax",
            )
        )
    if "obl_declaration_budget_disposition" in active and (
        "budget_disposition" not in facts_by_key
    ):
        source_blocked = any(item["kind"] == "REQUIRED" for item in source_requests)
        requests.append(
            _request(
                kind="DEFERRED" if source_blocked else "REQUIRED",
                priority="LOW" if source_blocked else "HIGH",
                closure_type="USER_FACT",
                fact_key="budget_disposition",
                demand_refs=["obl_declaration_budget_disposition"],
                evidence_refs=[],
                question=(
                    "Choose payment, additional payment, reduction or refund disposition "
                    "after the supported settlement amount is known."
                ),
                reason="budget disposition depends on the completed tax settlement",
                helpful_evidence="authenticated disposition instruction after calculation",
                client_benefit="avoids asking for a downstream election before it is actionable",
                answer_contract={
                    "kind": "code",
                    "allowed": ["PAYMENT", "ADDITIONAL_PAYMENT", "REDUCTION", "REFUND"],
                },
                subject={},
                scope_binding=scope_binding,
                semantic_request_key="human_fact:budget_disposition",
            )
        )
    return requests


def _request(
    *,
    kind: str,
    priority: str,
    closure_type: str,
    fact_key: str | None,
    demand_refs: list[str],
    evidence_refs: list[str],
    question: str,
    reason: str,
    helpful_evidence: str,
    client_benefit: str,
    answer_contract: dict[str, Any],
    subject: dict[str, Any],
    scope_binding: dict[str, Any],
    semantic_request_key: str,
    routing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if closure_type not in _CLOSURE_TYPES:
        _fail("gate5_gap_closure_type_invalid")
    gap_owner_classification = _GAP_OWNER_BY_CLOSURE_TYPE[closure_type]
    if routing is not None and routing.get("gap_owner_classification") != (
        gap_owner_classification
    ):
        _fail("gate5_gap_owner_classification_mismatch")
    if not _identifier(semantic_request_key):
        _fail("gate5_gap_semantic_request_key_invalid")
    base = {
        "schema_version": GATE5_GAP_REQUEST_SCHEMA_VERSION,
        "kind": kind,
        "priority": priority,
        "closure_type": closure_type,
        "gap_owner_classification": gap_owner_classification,
        "fact_key": fact_key,
        "demand_refs": sorted(demand_refs),
        "evidence_refs": sorted(evidence_refs),
        "subject": copy.deepcopy(subject),
        "question": question,
        "reason": reason,
        "helpful_evidence": helpful_evidence,
        "client_benefit": client_benefit,
        "answer_contract": copy.deepcopy(answer_contract),
        "scope_binding": _validated_human_fact_scope(scope_binding),
        "semantic_request_key": semantic_request_key,
    }
    if routing is not None:
        base["routing"] = _validated_routing(routing)
    request_sha256 = _sha256(base)
    with_identity = {
        **base,
        "request_id": "g5request_" + request_sha256[:32],
        "request_sha256": request_sha256,
    }
    return {
        **with_identity,
        "request_ref": _artifact_ref({"kind": "gap_request", "request": with_identity}),
    }


def _validated_routing(value: Any) -> dict[str, Any]:
    required = {
        "ownership_state",
        "route",
        "owner",
        "closure_type",
        "user_or_additional_document_allowed",
        "gap_owner_classification",
    }
    if (
        not isinstance(value, dict)
        or set(value) != required
        or value.get("closure_type") not in _CLOSURE_TYPES
        or not all(
            isinstance(value.get(key), str) and value[key]
            for key in ("ownership_state", "route", "owner")
        )
        or not isinstance(value.get("user_or_additional_document_allowed"), bool)
        or value.get("gap_owner_classification") not in GATE5_GAP_OWNER_CLASSIFICATIONS
    ):
        _fail("gate5_gap_owner_routing_invalid")
    if (
        value["user_or_additional_document_allowed"] is False
        and value["closure_type"] in _USER_FACING_CLOSURE_TYPES
    ):
        _fail("gate5_gap_internal_route_exposed_to_user")
    if (
        value["gap_owner_classification"]
        != _GAP_OWNER_BY_CLOSURE_TYPE[value["closure_type"]]
    ):
        _fail("gate5_gap_owner_classification_mismatch")
    return copy.deepcopy(value)


def _validated_request(value: Any) -> dict[str, Any]:
    keys = frozenset(value) if isinstance(value, dict) else frozenset()
    content_keys = keys - {"request_publication_ref"}
    if (
        not isinstance(value, dict)
        or content_keys not in {_REQUEST_KEYS, _REQUEST_KEYS | {"routing"}}
        or keys - content_keys
        not in {frozenset(), frozenset({"request_publication_ref"})}
        or (
            "request_publication_ref" in value
            and not _artifact_ref_valid(value.get("request_publication_ref"))
        )
        or value.get("schema_version") != GATE5_GAP_REQUEST_SCHEMA_VERSION
        or value.get("closure_type") not in _CLOSURE_TYPES
        or value.get("gap_owner_classification") not in GATE5_GAP_OWNER_CLASSIFICATIONS
        or not isinstance(value.get("request_id"), str)
        or not isinstance(value.get("request_sha256"), str)
        or not _artifact_ref_valid(value.get("request_ref"))
        or not isinstance(value.get("answer_contract"), dict)
        or not _identifier(value.get("semantic_request_key"))
    ):
        _fail("gate5_gap_request_invalid")
    _validated_human_fact_scope(value.get("scope_binding"))
    content = {
        key: copy.deepcopy(item)
        for key, item in value.items()
        if key != "request_publication_ref"
    }
    with_identity = {
        key: copy.deepcopy(item)
        for key, item in content.items()
        if key != "request_ref"
    }
    base = {
        key: copy.deepcopy(item)
        for key, item in with_identity.items()
        if key not in {"request_id", "request_sha256"}
    }
    request_sha256 = _sha256(base)
    if (
        value["request_sha256"] != request_sha256
        or value["request_id"] != "g5request_" + request_sha256[:32]
        or value["request_ref"]
        != _artifact_ref({"kind": "gap_request", "request": with_identity})
    ):
        _fail("gate5_gap_request_invalid")
    if "routing" in content:
        routing = _validated_routing(content["routing"])
        if content["closure_type"] != routing["closure_type"]:
            _fail("gate5_gap_owner_routing_invalid")
    return copy.deepcopy(value)


def _request_content_binding(request: dict[str, Any]) -> dict[str, str]:
    validated = _validated_request(request)
    return {
        key: validated[key] for key in sorted(_REQUEST_CONTENT_BINDING_KEYS)
    }


def _request_lane_sha256(request: dict[str, Any]) -> str:
    validated = _validated_request(request)
    return _sha256(
        {
            "scope_binding_sha256": validated["scope_binding"][
                "scope_binding_sha256"
            ],
            "semantic_request_key": validated["semantic_request_key"],
        }
    )


def _validated_request_publication(value: Any) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or set(value) != _REQUEST_PUBLICATION_KEYS
        or value.get("schema_version")
        != GATE5_GAP_REQUEST_PUBLICATION_SCHEMA_VERSION
        or not _artifact_ref_valid(value.get("request_publication_ref"))
        or not isinstance(value.get("request_lane_sha256"), str)
        or re.fullmatch(r"[0-9a-f]{64}", value["request_lane_sha256"]) is None
        or not _identifier(value.get("semantic_request_key"))
        or value.get("fact_key") not in _KNOWN_FACT_KEYS | {None}
        or value.get("closure_type") not in _CLOSURE_TYPES
        or not isinstance(value.get("request_binding"), dict)
        or set(value["request_binding"]) != _REQUEST_CONTENT_BINDING_KEYS
        or not all(
            isinstance(value["request_binding"].get(key), str)
            for key in _REQUEST_CONTENT_BINDING_KEYS
        )
        or not _artifact_ref_valid(value["request_binding"].get("request_ref"))
        or (
            value.get("predecessor_publication_ref") is not None
            and not _artifact_ref_valid(value["predecessor_publication_ref"])
        )
    ):
        _fail("gate5_gap_request_publication_invalid")
    _validated_human_fact_scope(value.get("scope_binding"))
    base = {
        key: copy.deepcopy(item)
        for key, item in value.items()
        if key not in {"request_publication_ref", "publication_sha256"}
    }
    publication_sha256 = _sha256(base)
    with_hash = {**base, "publication_sha256": publication_sha256}
    if (
        value.get("publication_sha256") != publication_sha256
        or value["request_publication_ref"]
        != _artifact_ref(
            {"kind": "gap_request_publication", "publication": with_hash}
        )
    ):
        _fail("gate5_gap_request_publication_invalid")
    return copy.deepcopy(value)


def _validated_user_fact_shape(item: Any) -> dict[str, Any]:
    if (
        not isinstance(item, dict)
        or set(item) != _USER_FACT_KEYS
        or item.get("schema_version") != GATE5_USER_CASE_FACT_SCHEMA_VERSION
        or not _artifact_ref_valid(item.get("user_case_fact_ref"))
        or item.get("fact_key") not in _KNOWN_FACT_KEYS
        or not isinstance(item.get("value"), dict)
        or set(item["value"]) != {"kind", "value"}
        or not isinstance(item.get("request_binding"), dict)
        or set(item["request_binding"]) != _REQUEST_BINDING_KEYS
        or not isinstance(item.get("provenance"), dict)
        or item["provenance"]
        != {
            "source_kind": "USER_ATTESTED_CASE_FACT",
            "provided_by": "authenticated_user",
            "input_channel": "gate5_human_gap_closure_v1",
            "calculation_authority": False,
            "document_source_fact": False,
        }
    ):
        _fail("gate5_user_case_facts_invalid")
    _validated_human_fact_scope(item.get("scope_binding"))
    binding = item["request_binding"]
    if (
        not _artifact_ref_valid(binding.get("request_ref"))
        or not _artifact_ref_valid(binding.get("request_publication_ref"))
        or not isinstance(binding.get("request_id"), str)
        or not isinstance(binding.get("request_sha256"), str)
    ):
        _fail("gate5_user_case_facts_invalid")
    material = {
        key: copy.deepcopy(value)
        for key, value in item.items()
        if key not in {"user_case_fact_ref", "fact_sha256"}
    }
    fact_sha256 = _sha256(material)
    if item.get("fact_sha256") != fact_sha256 or item[
        "user_case_fact_ref"
    ] != _artifact_ref({"kind": "user_case_fact", "fact_sha256": fact_sha256}):
        _fail("gate5_user_case_facts_invalid")
    return copy.deepcopy(item)


def _validate_inputs(
    *,
    intake: dict[str, Any],
    scope_activation: dict[str, Any],
    client_review: dict[str, Any],
) -> None:
    if intake.get("schema_version") != GATE5_EVIDENCE_INTAKE_SCHEMA_VERSION:
        _fail("gate5_gap_intake_invalid")
    if (
        scope_activation.get("schema_version")
        != GATE5_DECLARATION_SCOPE_ACTIVATION_SCHEMA_VERSION
    ):
        _fail("gate5_gap_scope_invalid")
    if (
        client_review.get("schema_version")
        != GATE5_CLIENT_EVIDENCE_REVIEW_SCHEMA_VERSION
    ):
        _fail("gate5_gap_review_invalid")


def _deduplicated_requests(value: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {item["request_id"]: item for item in value}
    return sorted(
        (copy.deepcopy(item) for item in by_id.values()),
        key=lambda item: (
            {"REQUIRED": 0, "ADVISORY": 1, "DEFERRED": 2}[item["kind"]],
            item["priority"],
            item["request_id"],
        ),
    )


def _adapter_request(item: dict[str, Any]) -> dict[str, Any]:
    result = {
        key: copy.deepcopy(item[key])
        for key in (
            "request_ref",
            "request_id",
            "request_sha256",
            "kind",
            "priority",
            "closure_type",
            "gap_owner_classification",
            "fact_key",
            "scope_binding",
            "question",
            "reason",
            "helpful_evidence",
            "client_benefit",
            "answer_contract",
        )
    }
    if "routing" in item:
        result["routing"] = copy.deepcopy(item["routing"])
    return result


def _human_fact_scope(
    *,
    context: ArtifactAccessContext,
    taxpayer_scope_ref: str,
    tax_period: str,
) -> dict[str, Any]:
    if (
        not isinstance(context, ArtifactAccessContext)
        or not context.allow_private
        or not _identifier(context.user_id)
        or not _identifier(context.normalization_run_id)
        or not _identifier(context.case_id)
        or not _identifier(taxpayer_scope_ref)
        or not isinstance(tax_period, str)
        or re.fullmatch(r"[0-9]{4}", tax_period) is None
        or (
            context.workspace_model_id is not None
            and not _identifier(context.workspace_model_id)
        )
    ):
        _fail("gate5_human_fact_scope_invalid")
    base = {
        "schema_version": GATE5_HUMAN_FACT_SCOPE_SCHEMA_VERSION,
        "authenticated_user_ref": context.user_id,
        "case_id": context.case_id,
        "taxpayer_scope_ref": taxpayer_scope_ref,
        "tax_period": tax_period,
    }
    return {**base, "scope_binding_sha256": _sha256(base)}
def _validated_human_fact_scope(value: Any) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or set(value) != _SCOPE_KEYS
        or value.get("schema_version") != GATE5_HUMAN_FACT_SCOPE_SCHEMA_VERSION
        or not all(
            _identifier(value.get(key))
            for key in (
                "authenticated_user_ref",
                "case_id",
                "taxpayer_scope_ref",
            )
        )
        or not isinstance(value.get("tax_period"), str)
        or re.fullmatch(r"[0-9]{4}", value["tax_period"]) is None
    ):
        _fail("gate5_human_fact_scope_invalid")
    base = {
        key: copy.deepcopy(item)
        for key, item in value.items()
        if key != "scope_binding_sha256"
    }
    if value["scope_binding_sha256"] != _sha256(base):
        _fail("gate5_human_fact_scope_invalid")
    return copy.deepcopy(value)


def _identifier(value: Any) -> bool:
    return isinstance(value, str) and _IDENTIFIER.fullmatch(value) is not None


def _artifact_ref(value: Any) -> str:
    return "art_" + _sha256(value)[:32]


def _artifact_ref_valid(value: Any) -> bool:
    return isinstance(value, str) and _ARTIFACT_REF.fullmatch(value) is not None


def _sha256(value: Any) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _fail(code: str) -> None:
    raise Gate5HumanGapClosureError(code)


__all__ = [
    "FACTORY_REQUIRED",
    "FORBIDDEN",
    "GATE5_GAP_REQUEST_SCHEMA_VERSION",
    "GATE5_GAP_REQUEST_ARTIFACT_TYPE",
    "GATE5_HUMAN_FACT_SCOPE_SCHEMA_VERSION",
    "GATE5_HUMAN_GAP_CLOSURE_SCHEMA_VERSION",
    "GATE5_HUMAN_GAP_CLOSURE_TERMINAL",
    "GATE5_USER_CASE_FACT_SCHEMA_VERSION",
    "GATE5_USER_CASE_FACT_ARTIFACT_TYPE",
    "GATE5_LEGACY_USER_CASE_FACT_SCHEMA_VERSION",
    "Gate5HumanGapClosureError",
    "Gate5HumanGapClosureRuntime",
    "Gate5HumanGapClosureRuntimeFactory",
]
