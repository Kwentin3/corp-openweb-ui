"""Immutable authenticated-case lifecycle for unknown-schema mapping."""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import replace
from typing import Any

from .artifact_lifecycle import lifecycle_for_visibility
from .artifact_models import ArtifactAccessContext, ArtifactRecord
from .artifact_resolver import ArtifactResolver
from .canonical_store import CanonicalReaderFactory
from .ordinary_trade_qualified_mappings import (
    OrdinaryTradeQualifiedMappingAuthorityFactory,
)
from .ordinary_trade_mapping_prompt import (
    validate_ordinary_trade_mapping_prompt_snapshot,
)
from .ordinary_trade_semantic_mapping import (
    MAPPING_CASE_SCHEMA_VERSION,
    mapping_question_option_communication_description,
    validate_internal_mapping_question,
)
from .ordinary_trade_semantic_compiler import USER_CURRENCY_ASSERTION_SCHEMA_VERSION


# The model package remains v2.  This is the separately versioned, durable
# private receipt that additionally binds a managed Workspace Prompt snapshot.
MAPPING_CASE_RECEIPT_SCHEMA_VERSION = "broker_reports_ordinary_trade_mapping_case_v4"
MAPPING_CASE_ARTIFACT_TYPE = MAPPING_CASE_RECEIPT_SCHEMA_VERSION
_LEGACY_MAPPING_CASE_ARTIFACT_TYPE = MAPPING_CASE_SCHEMA_VERSION
_V3_MAPPING_CASE_ARTIFACT_TYPE = "broker_reports_ordinary_trade_mapping_case_v3"
FACTORY_REQUIRED = (
    "OrdinaryTradeMappingCaseFactory.create is the only mapping-case state "
    "persistence and continuation entrypoint"
)
FORBIDDEN = (
    "global mapping reuse, mutable overwrite, caller tenant scope, latest-wins "
    "ambiguity, partial Fact publication or unconfirmed answer application"
)
_STATUSES = {
    "COMPLETE",
    "CLARIFICATION_REQUIRED",
    "CONFIRMATION_REQUIRED",
    "MAPPING_REQUIRED",
    "UNSUPPORTED",
    "SPECIALIST_REVIEW_REQUIRED",
    "PROVIDER_UNAVAILABLE",
    "SOURCE_CONTEXT_LIMIT",
    "MAPPING_OUTPUT_INVALID",
    "CURRENCY_ASSERTION_REQUIRED",
}


def mapping_case_artifact_types() -> frozenset[str]:
    """Return the closed receipt types accepted during the v2-to-v3 migration."""

    return frozenset(
        {
            MAPPING_CASE_ARTIFACT_TYPE,
            _V3_MAPPING_CASE_ARTIFACT_TYPE,
            _LEGACY_MAPPING_CASE_ARTIFACT_TYPE,
        }
    )


class OrdinaryTradeMappingCaseError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class OrdinaryTradeMappingCaseFactory:
    def __init__(self, *, store: Any, read_enabled: bool) -> None:
        self._store = store
        self._read_enabled = read_enabled

    def create(self) -> "OrdinaryTradeMappingCaseRuntime":
        return OrdinaryTradeMappingCaseRuntime(
            store=self._store,
            read_enabled=self._read_enabled,
        )


class OrdinaryTradeMappingCaseRuntime:
    def __init__(self, *, store: Any, read_enabled: bool) -> None:
        self._store = store
        self._reader = CanonicalReaderFactory(
            store=store, read_enabled=read_enabled
        ).create()
        self._resolver = ArtifactResolver(store)
        self._authority = OrdinaryTradeQualifiedMappingAuthorityFactory.create()

    def case_binding(
        self, *, document_id: str, context: ArtifactAccessContext
    ) -> dict[str, Any]:
        _private_case(context)
        envelope = self._reader.read_active_envelope(document_id, context)
        source = envelope.artifact.get("source") or {}
        finalization = envelope.artifact.get("finalization") or {}
        base_version_id = str(
            finalization.get("base_canonical_version_id")
            or envelope.canonical_version_id
        )
        base_root_sha256 = str(
            finalization.get("base_canonical_root_sha256")
            or envelope.canonical_root_sha256
        )
        canonical_binding = {
            "document_id": envelope.document_id,
            "canonical_version_id": base_version_id,
            "canonical_root_sha256": base_root_sha256,
            "source_artifact_ref": str(source.get("source_artifact_ref") or ""),
            "source_sha256": str(source.get("source_sha256") or ""),
        }
        if not all(canonical_binding.values()):
            _fail("ordinary_trade_mapping_case_canonical_binding_invalid")
        user_scope_sha256 = _sha256_json(
            {
                "user_id": context.user_id,
                "case_id": context.case_id,
                "chat_id": context.chat_id,
                "workspace_model_id": context.workspace_model_id,
            }
        )
        identity = {
            "canonical_binding": canonical_binding,
            "user_scope_sha256": user_scope_sha256,
        }
        return {
            **identity,
            "case_binding_sha256": _sha256_json(identity),
            "case_id": "otcase_" + _sha256_json(identity)[:32],
            "canonical": envelope.artifact,
        }

    def current(
        self, *, document_id: str, context: ArtifactAccessContext
    ) -> tuple[ArtifactRecord, dict[str, Any]] | None:
        binding = self.case_binding(document_id=document_id, context=context)
        records: list[tuple[ArtifactRecord, dict[str, Any]]] = []
        for record in self._resolver.catalog_case(context):
            if (
                record.artifact_type not in mapping_case_artifact_types()
                or record.document_id != document_id
            ):
                continue
            record_context = replace(
                context, normalization_run_id=record.normalization_run_id
            )
            resolved = self._resolver.resolve(record.artifact_id, record_context)
            payload = resolved["payload"]
            _validate_payload(payload, authority=self._authority)
            if payload["case_id"] != binding["case_id"]:
                continue
            records.append((record, payload))
        if not records:
            return None
        revisions = [item[1]["revision"] for item in records]
        if len(revisions) != len(set(revisions)) or sorted(revisions) != list(
            range(1, max(revisions) + 1)
        ):
            _fail("ordinary_trade_mapping_case_history_ambiguous")
        latest = max(records, key=lambda item: item[1]["revision"])
        if latest[1]["case_binding"] != _public_binding(binding):
            _fail("ordinary_trade_mapping_case_binding_stale")
        return latest

    def save_mapping_outcome(
        self,
        *,
        document_id: str,
        context: ArtifactAccessContext,
        outcome: dict[str, Any],
        provider_calls_total: int,
        mapping_prompt_snapshot: dict[str, Any] | None = None,
    ) -> tuple[ArtifactRecord, dict[str, Any]]:
        current = self.current(document_id=document_id, context=context)
        if current is not None and current[1]["status"] not in {
            "MAPPING_REQUIRED",
            "PROVIDER_UNAVAILABLE",
        }:
            _fail("ordinary_trade_mapping_case_transition_invalid")
        status = outcome.get("status")
        if status not in {
            "COMPLETE",
            "CLARIFICATION_REQUIRED",
            "UNSUPPORTED",
            "SPECIALIST_REVIEW_REQUIRED",
            "CURRENCY_ASSERTION_REQUIRED",
        }:
            _fail("ordinary_trade_mapping_case_outcome_invalid")
        prior = current[1] if current is not None else None
        payload = self._next_payload(
            document_id=document_id,
            context=context,
            prior=prior,
            status=status,
            message=str(outcome.get("message") or ""),
            question=copy.deepcopy(outcome.get("question")),
            pending_candidate=copy.deepcopy(outcome.get("currency_mapping_plan")),
            confirmed_understandings=copy.deepcopy(
                (prior or {}).get("confirmed_understandings") or []
            ),
            qualified_mappings=copy.deepcopy(outcome.get("qualified_mappings") or []),
            qualification_receipts=copy.deepcopy(
                outcome.get("qualification_receipts") or []
            ),
            table_resolutions=copy.deepcopy(outcome.get("table_resolutions") or []),
            provider_calls_total=(
                int((prior or {}).get("provider_calls_total") or 0)
                + provider_calls_total
            ),
            model_response_sha256=outcome.get("model_response_sha256"),
            execution_metadata_sha256=outcome.get("execution_metadata_sha256"),
            mapping_prompt_snapshot=mapping_prompt_snapshot,
            mapping_batch_state=None,
            reason_code=None,
        )
        return self._put(payload=payload, document_id=document_id, context=context)

    def save_batch_state(
        self,
        *,
        document_id: str,
        context: ArtifactAccessContext,
        status: str,
        message: str,
        mapping_batch_state: dict[str, Any],
        provider_calls_total: int,
        mapping_prompt_snapshot: dict[str, Any],
        pending_candidate: dict[str, Any] | None = None,
        reason_code: str | None = None,
    ) -> tuple[ArtifactRecord, dict[str, Any]]:
        """Persist batch transport progress without publishing partial mappings."""

        if status not in {
            "MAPPING_REQUIRED",
            "CURRENCY_ASSERTION_REQUIRED",
            "PROVIDER_UNAVAILABLE",
            "MAPPING_OUTPUT_INVALID",
            "SPECIALIST_REVIEW_REQUIRED",
            "UNSUPPORTED",
        }:
            _fail("ordinary_trade_mapping_case_outcome_invalid")
        current = self.current(document_id=document_id, context=context)
        if current is not None and current[1]["status"] not in {
            "MAPPING_REQUIRED",
            "CURRENCY_ASSERTION_REQUIRED",
            "PROVIDER_UNAVAILABLE",
        }:
            _fail("ordinary_trade_mapping_case_transition_invalid")
        prior = current[1] if current is not None else None
        payload = self._next_payload(
            document_id=document_id,
            context=context,
            prior=prior,
            status=status,
            message=message,
            question=None,
            pending_candidate=copy.deepcopy(pending_candidate),
            confirmed_understandings=copy.deepcopy(
                (prior or {}).get("confirmed_understandings") or []
            ),
            qualified_mappings=[],
            qualification_receipts=[],
            table_resolutions=[],
            provider_calls_total=(
                int((prior or {}).get("provider_calls_total") or 0)
                + provider_calls_total
            ),
            model_response_sha256=None,
            execution_metadata_sha256=None,
            mapping_prompt_snapshot=mapping_prompt_snapshot,
            mapping_batch_state=mapping_batch_state,
            reason_code=reason_code,
        )
        return self._put(payload=payload, document_id=document_id, context=context)

    def save_provider_terminal(
        self,
        *,
        document_id: str,
        context: ArtifactAccessContext,
        status: str,
        reason_code: str,
        message: str,
        provider_calls_total: int,
        mapping_prompt_snapshot: dict[str, Any] | None = None,
    ) -> tuple[ArtifactRecord, dict[str, Any]]:
        if status not in {
            "PROVIDER_UNAVAILABLE",
            "SOURCE_CONTEXT_LIMIT",
            "MAPPING_OUTPUT_INVALID",
        }:
            _fail("ordinary_trade_mapping_case_outcome_invalid")
        return self._save_terminal(
            document_id=document_id,
            context=context,
            status=status,
            reason_code=reason_code,
            message=message,
            provider_calls_total=provider_calls_total,
            mapping_prompt_snapshot=mapping_prompt_snapshot,
        )

    def save_deterministic_terminal(
        self,
        *,
        document_id: str,
        context: ArtifactAccessContext,
        status: str,
        reason_code: str,
        message: str,
    ) -> tuple[ArtifactRecord, dict[str, Any]]:
        if status != "SPECIALIST_REVIEW_REQUIRED":
            _fail("ordinary_trade_mapping_case_outcome_invalid")
        return self._save_terminal(
            document_id=document_id,
            context=context,
            status=status,
            reason_code=reason_code,
            message=message,
            provider_calls_total=0,
            mapping_prompt_snapshot=None,
        )

    def record_user_currency_assertion(
        self,
        *,
        document_id: str,
        context: ArtifactAccessContext,
        currency_code: str,
        table_node_ids: list[str],
    ) -> tuple[ArtifactRecord, dict[str, Any]]:
        """Record one bounded user value without representing it as source text."""

        binding = self.case_binding(document_id=document_id, context=context)
        if (
            not isinstance(currency_code, str)
            or len(currency_code) != 3
            or currency_code != currency_code.upper()
            or not currency_code.isalpha()
            or not isinstance(table_node_ids, list)
            or not table_node_ids
            or table_node_ids != sorted(set(table_node_ids))
            or any(not isinstance(item, str) or not item for item in table_node_ids)
        ):
            _fail("ordinary_trade_user_currency_assertion_invalid")
        current = self.current(document_id=document_id, context=context)
        if (
            current is None
            or current[1]["status"] != "CURRENCY_ASSERTION_REQUIRED"
            or not isinstance(current[1].get("pending_candidate"), dict)
        ):
            _fail("ordinary_trade_mapping_case_transition_invalid")
        assertion_material = {
            "schema_version": USER_CURRENCY_ASSERTION_SCHEMA_VERSION,
            "currency_code": currency_code,
            "case_binding_sha256": binding["case_binding_sha256"],
            "table_node_ids": table_node_ids,
        }
        decision = {
            **assertion_material,
            "decision_kind": "USER_PROVIDED_CURRENCY",
            "assertion_id": "usrassert_" + _sha256_json(assertion_material)[:32],
        }
        label = "User-provided transaction currency: " + currency_code
        confirmed = [
            *copy.deepcopy((current or ({}, {}))[1].get("confirmed_understandings") or []),
            {
                "question_id": "q_user_currency_assertion",
                "option_id": "currency_" + currency_code.lower(),
                "label": label,
                "label_sha256": hashlib.sha256(label.encode("utf-8")).hexdigest(),
                "decision": decision,
                "decision_sha256": _sha256_json(decision),
            },
        ]
        payload = self._next_payload(
            document_id=document_id,
            context=context,
            prior=(current[1] if current is not None else None),
            status="MAPPING_REQUIRED",
            message="Currency supplied by the user is recorded separately from the source document.",
            question=None,
            pending_candidate=copy.deepcopy(current[1]["pending_candidate"]),
            confirmed_understandings=confirmed,
            qualified_mappings=[],
            qualification_receipts=[],
            table_resolutions=[],
            provider_calls_total=int((current or ({}, {}))[1].get("provider_calls_total") or 0),
            model_response_sha256=None,
            execution_metadata_sha256=None,
            reason_code=None,
        )
        return self._put(payload=payload, document_id=document_id, context=context)

    def resume_existing_currency_assertion(
        self,
        *,
        document_id: str,
        context: ArtifactAccessContext,
        currency_code: str,
        table_node_ids: list[str],
    ) -> tuple[ArtifactRecord, dict[str, Any]]:
        """Advance a repeated, already case-bound currency answer once."""

        if (
            not isinstance(currency_code, str)
            or len(currency_code) != 3
            or currency_code != currency_code.upper()
            or not currency_code.isalpha()
            or not isinstance(table_node_ids, list)
            or not table_node_ids
            or table_node_ids != sorted(set(table_node_ids))
            or any(not isinstance(item, str) or not item for item in table_node_ids)
        ):
            _fail("ordinary_trade_user_currency_assertion_invalid")
        current = self.current(document_id=document_id, context=context)
        if (
            current is None
            or current[1]["status"] != "CURRENCY_ASSERTION_REQUIRED"
            or not isinstance(current[1].get("pending_candidate"), dict)
            or not _has_confirmed_currency_assertion(
                confirmed_understandings=current[1]["confirmed_understandings"],
                currency_code=currency_code,
                table_node_ids=table_node_ids,
            )
        ):
            _fail("ordinary_trade_mapping_case_transition_invalid")
        payload = self._next_payload(
            document_id=document_id,
            context=context,
            prior=current[1],
            status="MAPPING_REQUIRED",
            message=(
                "Previously supplied user currency is retained separately from the "
                "source document."
            ),
            question=None,
            pending_candidate=copy.deepcopy(current[1]["pending_candidate"]),
            confirmed_understandings=copy.deepcopy(
                current[1]["confirmed_understandings"]
            ),
            qualified_mappings=[],
            qualification_receipts=[],
            table_resolutions=[],
            provider_calls_total=int(current[1]["provider_calls_total"]),
            model_response_sha256=None,
            execution_metadata_sha256=None,
            reason_code=None,
        )
        return self._put(payload=payload, document_id=document_id, context=context)

    def _save_terminal(
        self,
        *,
        document_id: str,
        context: ArtifactAccessContext,
        status: str,
        reason_code: str,
        message: str,
        provider_calls_total: int,
        mapping_prompt_snapshot: dict[str, Any] | None = None,
    ) -> tuple[ArtifactRecord, dict[str, Any]]:
        current = self.current(document_id=document_id, context=context)
        prior = current[1] if current is not None else None
        if prior is not None and prior["status"] == "COMPLETE":
            _fail("ordinary_trade_mapping_case_transition_invalid")
        payload = self._next_payload(
            document_id=document_id,
            context=context,
            prior=prior,
            status=status,
            message=message,
            question=copy.deepcopy((prior or {}).get("question")),
            pending_candidate=None,
            confirmed_understandings=copy.deepcopy(
                (prior or {}).get("confirmed_understandings") or []
            ),
            qualified_mappings=[],
            qualification_receipts=[],
            table_resolutions=[],
            provider_calls_total=(
                int((prior or {}).get("provider_calls_total") or 0)
                + provider_calls_total
            ),
            model_response_sha256=None,
            execution_metadata_sha256=None,
            mapping_prompt_snapshot=mapping_prompt_snapshot,
            reason_code=reason_code,
        )
        return self._put(payload=payload, document_id=document_id, context=context)

    def save_answer_candidate(
        self,
        *,
        document_id: str,
        context: ArtifactAccessContext,
        interpretation: dict[str, Any],
        provider_calls_total: int,
    ) -> tuple[ArtifactRecord, dict[str, Any]]:
        current = self.current(document_id=document_id, context=context)
        if (
            current is None
            or current[1]["status"]
            not in {"CLARIFICATION_REQUIRED", "PROVIDER_UNAVAILABLE"}
            or not isinstance(current[1].get("question"), dict)
        ):
            _fail("ordinary_trade_mapping_case_transition_invalid")
        prior = current[1]
        status = interpretation.get("status")
        if status == "SPECIALIST_REVIEW":
            target_status = "SPECIALIST_REVIEW_REQUIRED"
            candidate = None
        elif status == "CLARIFY":
            target_status = "CLARIFICATION_REQUIRED"
            candidate = None
        elif status == "CANDIDATE":
            target_status = "CONFIRMATION_REQUIRED"
            selected_option = next(
                item
                for item in prior["question"]["options"]
                if item["option_id"] == interpretation["option_id"]
            )
            candidate = {
                "question_id": prior["question"]["question_id"],
                "option_id": interpretation["option_id"],
                "message": (
                    "Подтвердите выбранное понимание исходных данных:\n"
                    f"> {selected_option['label']}"
                ),
                "evidence_quote_sha256": hashlib.sha256(
                    interpretation["evidence_quote"].encode("utf-8")
                ).hexdigest(),
            }
        else:
            _fail("ordinary_trade_mapping_case_outcome_invalid")
        payload = self._next_payload(
            document_id=document_id,
            context=context,
            prior=prior,
            status=target_status,
            message=interpretation["message"],
            question=copy.deepcopy(prior["question"]),
            pending_candidate=candidate,
            confirmed_understandings=copy.deepcopy(prior["confirmed_understandings"]),
            qualified_mappings=[],
            qualification_receipts=[],
            table_resolutions=[],
            provider_calls_total=(prior["provider_calls_total"] + provider_calls_total),
            model_response_sha256=None,
            execution_metadata_sha256=None,
            reason_code=None,
        )
        return self._put(payload=payload, document_id=document_id, context=context)

    def promote_exclusion_confirmation(
        self,
        *,
        document_id: str,
        context: ArtifactAccessContext,
    ) -> tuple[ArtifactRecord, dict[str, Any]]:
        """Expose one code-owned yes/no confirmation for validated exclusions."""

        current = self.current(document_id=document_id, context=context)
        if (
            current is None
            or current[1]["status"] != "CLARIFICATION_REQUIRED"
            or not isinstance(current[1].get("question"), dict)
            or current[1]["question"].get("question_id") != "q_exclusion_batch"
        ):
            _fail("ordinary_trade_mapping_case_transition_invalid")
        prior = current[1]
        selected = next(
            (
                item
                for item in prior["question"]["options"]
                if item.get("effect") == "APPLY_DECISIONS"
            ),
            None,
        )
        if not isinstance(selected, dict):
            _fail("ordinary_trade_mapping_case_question_invalid")
        count = len(selected.get("decisions") or [])
        candidate = {
            "question_id": "q_exclusion_batch",
            "option_id": selected["option_id"],
            "message": (
                "В отчёте найдены служебные разделы, не участвующие в расчёте "
                f"сделок ({count}). Продолжить без включения их в расчёт? Ответьте «Да» или «Нет»."
            ),
            "evidence_quote_sha256": hashlib.sha256(
                selected["label"].encode("utf-8")
            ).hexdigest(),
        }
        payload = self._next_payload(
            document_id=document_id,
            context=context,
            prior=prior,
            status="CONFIRMATION_REQUIRED",
            message=candidate["message"],
            question=copy.deepcopy(prior["question"]),
            pending_candidate=candidate,
            confirmed_understandings=copy.deepcopy(prior["confirmed_understandings"]),
            qualified_mappings=[],
            qualification_receipts=[],
            table_resolutions=[],
            provider_calls_total=prior["provider_calls_total"],
            model_response_sha256=None,
            execution_metadata_sha256=None,
            reason_code=None,
        )
        return self._put(payload=payload, document_id=document_id, context=context)

    def confirm_pending_answer(
        self,
        *,
        document_id: str,
        context: ArtifactAccessContext,
        expected_artifact_id: str,
        accepted: bool,
    ) -> tuple[ArtifactRecord, dict[str, Any]]:
        current = self.current(document_id=document_id, context=context)
        if (
            current is None
            or current[0].artifact_id != expected_artifact_id
            or current[1]["status"] != "CONFIRMATION_REQUIRED"
            or not isinstance(current[1].get("pending_candidate"), dict)
        ):
            _fail("ordinary_trade_mapping_case_concurrent_answer")
        prior = current[1]
        if not accepted:
            exclusion_confirmation = (
                prior["question"].get("question_id") == "q_exclusion_batch"
            )
            status = (
                "SPECIALIST_REVIEW_REQUIRED"
                if exclusion_confirmation
                else "CLARIFICATION_REQUIRED"
            )
            confirmed = copy.deepcopy(prior["confirmed_understandings"])
            message = (
                "Исключение служебных разделов не подтверждено; требуется проверка специалиста."
                if exclusion_confirmation
                else "Предложенное понимание не подтверждено. Уточните ответ."
            )
        else:
            pending = prior["pending_candidate"]
            option = next(
                item
                for item in prior["question"]["options"]
                if item["option_id"] == pending["option_id"]
            )
            if option.get("effect") == "SPECIALIST_REVIEW":
                confirmed = copy.deepcopy(prior["confirmed_understandings"])
                status = "SPECIALIST_REVIEW_REQUIRED"
            else:
                decisions = option.get("decisions")
                if not isinstance(decisions, list):
                    decisions = [option["decision"]]
                confirmed = [
                    *copy.deepcopy(prior["confirmed_understandings"]),
                    *[
                        {
                            "question_id": pending["question_id"],
                            "option_id": pending["option_id"],
                            "label_sha256": hashlib.sha256(
                                option["label"].encode("utf-8")
                            ).hexdigest(),
                            "label": option["label"],
                            "decision": copy.deepcopy(decision),
                            "decision_sha256": _sha256_json(decision),
                        }
                        for decision in decisions
                    ],
                ]
                status = "MAPPING_REQUIRED"
            message = "Понимание подтверждено; mapping будет проверен повторно."
        payload = self._next_payload(
            document_id=document_id,
            context=context,
            prior=prior,
            status=status,
            message=message,
            question=(None if accepted else copy.deepcopy(prior["question"])),
            pending_candidate=None,
            confirmed_understandings=confirmed,
            qualified_mappings=[],
            qualification_receipts=[],
            table_resolutions=[],
            provider_calls_total=prior["provider_calls_total"],
            model_response_sha256=None,
            execution_metadata_sha256=None,
            reason_code=None,
        )
        return self._put(payload=payload, document_id=document_id, context=context)

    def qualified_material(
        self, *, document_id: str, context: ArtifactAccessContext
    ) -> dict[str, Any] | None:
        current = self.current(document_id=document_id, context=context)
        if current is None or current[1]["status"] != "COMPLETE":
            return None
        return {
            "mapping_case_artifact_id": current[0].artifact_id,
            "qualified_mappings": copy.deepcopy(current[1]["qualified_mappings"]),
            "qualification_receipts": copy.deepcopy(
                current[1]["qualification_receipts"]
            ),
            "table_resolutions": copy.deepcopy(current[1]["table_resolutions"]),
        }

    def public_state(
        self, *, document_id: str, context: ArtifactAccessContext
    ) -> dict[str, Any] | None:
        current = self.current(document_id=document_id, context=context)
        if current is None:
            return None
        payload = current[1]
        question = payload.get("question")
        return {
            "status": payload["status"],
            "message": payload["message"],
            "question": (
                {
                    "question_ref": question["question_id"],
                    "question": question["question"],
                    "options": [
                        {
                            "option_ref": item["option_id"],
                            "label": item["label"],
                            "source_literals": list(item["source_literals"]),
                            "safe_description": mapping_question_option_communication_description(
                                item
                            ),
                        }
                        for item in question["options"]
                    ],
                }
                if isinstance(question, dict)
                else None
            ),
            "confirmation_message": (
                (payload.get("pending_candidate") or {}).get("message")
                if payload["status"] == "CONFIRMATION_REQUIRED"
                else None
            ),
            "confirmation_option_ref": (
                (payload.get("pending_candidate") or {}).get("option_id")
                if payload["status"] == "CONFIRMATION_REQUIRED"
                else None
            ),
            "may_resume": payload["status"]
            in {
                "CLARIFICATION_REQUIRED",
                "CONFIRMATION_REQUIRED",
                "MAPPING_REQUIRED",
                "PROVIDER_UNAVAILABLE",
                "CURRENCY_ASSERTION_REQUIRED",
            },
            "provider_calls_total": payload["provider_calls_total"],
        }

    def _next_payload(
        self, *, prior: dict[str, Any] | None, **values: Any
    ) -> dict[str, Any]:
        binding = self.case_binding(
            document_id=values["document_id"], context=values["context"]
        )
        revision = int((prior or {}).get("revision") or 0) + 1
        prompt_snapshot = values.get("mapping_prompt_snapshot")
        if prompt_snapshot is None and prior is not None:
            prompt_snapshot = prior.get("mapping_prompt_snapshot")
        if prompt_snapshot is not None:
            prompt_snapshot = validate_ordinary_trade_mapping_prompt_snapshot(
                prompt_snapshot
            )
        # Absence preserves a paused batch during an unrelated case update;
        # an explicit None is the terminal aggregate's instruction to clear it.
        batch_state = values.get("mapping_batch_state")
        if "mapping_batch_state" not in values and prior is not None:
            batch_state = prior.get("mapping_batch_state")
        if batch_state is not None and prompt_snapshot is None:
            _fail("ordinary_trade_mapping_case_prompt_snapshot_invalid")
        payload = {
            "schema_version": (
                MAPPING_CASE_RECEIPT_SCHEMA_VERSION
                if prompt_snapshot is not None
                else MAPPING_CASE_SCHEMA_VERSION
            ),
            "case_id": binding["case_id"],
            "revision": revision,
            "predecessor_sha256": (prior or {}).get("integrity_sha256"),
            "case_binding": _public_binding(binding),
            "status": values["status"],
            "message": values["message"],
            "question": values["question"],
            "pending_candidate": values["pending_candidate"],
            "confirmed_understandings": values["confirmed_understandings"],
            "qualified_mappings": values["qualified_mappings"],
            "qualification_receipts": values["qualification_receipts"],
            "table_resolutions": values["table_resolutions"],
            "provider_calls_total": values["provider_calls_total"],
            "model_response_sha256": values["model_response_sha256"],
            "execution_metadata_sha256": values["execution_metadata_sha256"],
            "reason_code": values["reason_code"],
        }
        if prompt_snapshot is not None:
            payload["mapping_prompt_snapshot"] = prompt_snapshot
            payload["mapping_batch_state"] = copy.deepcopy(batch_state)
        payload["integrity_sha256"] = _sha256_json(payload)
        _validate_payload(payload, authority=self._authority)
        return payload

    def _put(
        self,
        *,
        payload: dict[str, Any],
        document_id: str,
        context: ArtifactAccessContext,
    ) -> tuple[ArtifactRecord, dict[str, Any]]:
        active = self._store.get_active_canonical_version(
            context=context, document_id=document_id
        )
        if not active.manifest_ref:
            _fail("ordinary_trade_mapping_case_canonical_manifest_missing")
        manifest = self._resolver.resolve_record(active.manifest_ref, context)
        artifact_id = (
            "art_otmapcase_" + payload["case_id"][7:27] + f"_{payload['revision']:04d}"
        )
        record = ArtifactRecord(
            artifact_id=artifact_id,
            artifact_type=MAPPING_CASE_ARTIFACT_TYPE,
            case_id=context.case_id,
            chat_id=context.chat_id,
            user_id=context.user_id,
            workspace_model_id=context.workspace_model_id,
            normalization_run_id=context.normalization_run_id,
            document_id=document_id,
            source_file_ref=copy.deepcopy(manifest.source_file_ref),
            visibility="private_case",
            storage_backend="project_artifact_payload",
            retention_policy=manifest.retention_policy,
            access_policy={
                "requires_user_id": True,
                "requires_case_or_chat": True,
                "requires_workspace_model_id_when_present": bool(
                    context.workspace_model_id
                ),
                "ordinary_trade_mapping_case_only": True,
            },
            validation_status="validated",
            lifecycle_status=lifecycle_for_visibility(
                visibility="private_case", validation_status="validated"
            ),
            payload_kind="json_file",
            payload=payload,
            safe_metadata={
                "status": payload["status"],
                "revision": payload["revision"],
                "provider_calls_total": payload["provider_calls_total"],
                "global_reuse_allowed": False,
                "contains_source_values": True,
            },
        )
        try:
            stored = self._store.put_record(record)
        except Exception as exc:
            winner = self._store.get_record_unchecked(artifact_id)
            if winner is not None:
                raise OrdinaryTradeMappingCaseError(
                    "ordinary_trade_mapping_case_concurrent_answer"
                ) from exc
            raise
        return stored, copy.deepcopy(payload)


def _validate_payload(payload: Any, *, authority: Any) -> None:
    expected_keys = {
        "schema_version",
        "case_id",
        "revision",
        "predecessor_sha256",
        "case_binding",
        "status",
        "message",
        "question",
        "pending_candidate",
        "confirmed_understandings",
        "qualified_mappings",
        "qualification_receipts",
        "table_resolutions",
        "provider_calls_total",
        "model_response_sha256",
        "execution_metadata_sha256",
        "reason_code",
        "integrity_sha256",
    }
    schema_version = payload.get("schema_version") if isinstance(payload, dict) else None
    if schema_version == MAPPING_CASE_RECEIPT_SCHEMA_VERSION:
        expected_keys = {*expected_keys, "mapping_prompt_snapshot", "mapping_batch_state"}
    elif schema_version == _V3_MAPPING_CASE_ARTIFACT_TYPE:
        expected_keys = {*expected_keys, "mapping_prompt_snapshot"}
    if (
        not isinstance(payload, dict)
        or set(payload) != expected_keys
        or schema_version
        not in {
            MAPPING_CASE_SCHEMA_VERSION,
            _V3_MAPPING_CASE_ARTIFACT_TYPE,
            MAPPING_CASE_RECEIPT_SCHEMA_VERSION,
        }
        or not isinstance(payload.get("case_id"), str)
        or not payload["case_id"].startswith("otcase_")
        or not isinstance(payload.get("revision"), int)
        or payload["revision"] < 1
        or payload.get("status") not in _STATUSES
        or not isinstance(payload.get("message"), str)
        or not isinstance(payload.get("provider_calls_total"), int)
        or payload["provider_calls_total"] < 0
    ):
        _fail("ordinary_trade_mapping_case_invalid")
    if schema_version in {
        _V3_MAPPING_CASE_ARTIFACT_TYPE,
        MAPPING_CASE_RECEIPT_SCHEMA_VERSION,
    }:
        try:
            validate_ordinary_trade_mapping_prompt_snapshot(
                payload["mapping_prompt_snapshot"]
            )
        except Exception as exc:
            raise OrdinaryTradeMappingCaseError(
                "ordinary_trade_mapping_case_prompt_snapshot_invalid"
            ) from exc
    if schema_version == MAPPING_CASE_RECEIPT_SCHEMA_VERSION:
        _validate_mapping_batch_state(payload.get("mapping_batch_state"))
    frozen = copy.deepcopy(payload)
    digest = frozen.pop("integrity_sha256", None)
    if digest != _sha256_json(frozen):
        _fail("ordinary_trade_mapping_case_integrity_invalid")
    binding = payload.get("case_binding")
    if (
        not isinstance(binding, dict)
        or set(binding)
        != {
            "canonical_binding",
            "user_scope_sha256",
            "case_binding_sha256",
        }
        or payload["case_id"]
        != "otcase_"
        + _sha256_json(
            {
                "canonical_binding": binding["canonical_binding"],
                "user_scope_sha256": binding["user_scope_sha256"],
            }
        )[:32]
        or binding["case_binding_sha256"]
        != _sha256_json(
            {
                "canonical_binding": binding["canonical_binding"],
                "user_scope_sha256": binding["user_scope_sha256"],
            }
        )
    ):
        _fail("ordinary_trade_mapping_case_binding_invalid")
    confirmed = payload.get("confirmed_understandings")
    if not isinstance(confirmed, list):
        _fail("ordinary_trade_mapping_case_confirmation_invalid")
    for item in confirmed:
        normal_confirmation = (
            not isinstance(item, dict)
            or set(item)
            != {
                "question_id",
                "option_id",
                "label_sha256",
                "label",
                "decision",
                "decision_sha256",
            }
            or hashlib.sha256(item["label"].encode("utf-8")).hexdigest()
            != item["label_sha256"]
            or _sha256_json(item["decision"]) != item["decision_sha256"]
        )
        decision = item.get("decision") if isinstance(item, dict) else None
        user_currency_confirmation = (
            not normal_confirmation
            and isinstance(decision, dict)
            and decision.get("decision_kind") == "USER_PROVIDED_CURRENCY"
            and _valid_user_currency_decision(decision, binding=binding)
        )
        if normal_confirmation or (
            isinstance(decision, dict)
            and decision.get("decision_kind") == "USER_PROVIDED_CURRENCY"
            and not user_currency_confirmation
        ):
            _fail("ordinary_trade_mapping_case_confirmation_invalid")
    if payload.get("question") is not None:
        try:
            validate_internal_mapping_question(payload["question"])
        except Exception as exc:
            raise OrdinaryTradeMappingCaseError(
                "ordinary_trade_mapping_case_question_invalid"
            ) from exc
    mappings = payload.get("qualified_mappings")
    receipts = payload.get("qualification_receipts")
    resolutions = payload.get("table_resolutions")
    if not all(isinstance(item, list) for item in (mappings, receipts, resolutions)):
        _fail("ordinary_trade_mapping_case_material_invalid")
    if payload["status"] == "COMPLETE":
        if len(mappings) != len(receipts) or not resolutions:
            _fail("ordinary_trade_mapping_case_material_invalid")
        receipts_by_id = {item.get("qualification_id"): item for item in receipts}
        for mapping in mappings:
            receipt = receipts_by_id.get(
                (mapping.get("qualification_ref") or {}).get("qualification_id")
            )
            if receipt is None:
                _fail("ordinary_trade_mapping_case_material_invalid")
            table_node_id = (receipt.get("case_scope") or {}).get("table_node_id")
            expected_scope = {
                **binding["canonical_binding"],
                "user_scope_sha256": binding["user_scope_sha256"],
                "table_node_id": table_node_id,
            }
            authority.validate_case_mapping(
                mapping=mapping,
                receipt=receipt,
                expected_case_scope=expected_scope,
            )
    elif mappings or receipts or resolutions:
        _fail("ordinary_trade_mapping_case_partial_publication")
    if payload["status"] == "CLARIFICATION_REQUIRED":
        if not isinstance(payload.get("question"), dict):
            _fail("ordinary_trade_mapping_case_question_invalid")
    if payload["status"] == "CURRENCY_ASSERTION_REQUIRED":
        if (
            payload.get("question") is not None
            or not isinstance(payload.get("pending_candidate"), dict)
            or not isinstance(payload["pending_candidate"].get("response"), dict)
            or not isinstance(
                payload["pending_candidate"]["response"].get("table_decisions"), list
            )
            or not isinstance(payload["pending_candidate"].get("execution_metadata"), dict)
            or not isinstance(payload["pending_candidate"].get("table_node_ids"), list)
            or not payload["pending_candidate"]["table_node_ids"]
            or payload["pending_candidate"]["table_node_ids"]
            != sorted(set(payload["pending_candidate"]["table_node_ids"]))
            or any(
                not isinstance(item, str) or not item
                for item in payload["pending_candidate"]["table_node_ids"]
            )
            or (
                "target_table_node_ids" in payload["pending_candidate"]
                and (
                    not isinstance(
                        payload["pending_candidate"]["target_table_node_ids"],
                        list,
                    )
                    or not payload["pending_candidate"]["target_table_node_ids"]
                    or len(payload["pending_candidate"]["target_table_node_ids"])
                    != len(
                        set(payload["pending_candidate"]["target_table_node_ids"])
                    )
                    or any(
                        not isinstance(item, str) or not item
                        for item in payload["pending_candidate"][
                            "target_table_node_ids"
                        ]
                    )
                )
            )
        ):
            _fail("ordinary_trade_mapping_case_currency_request_invalid")
    if payload["status"] == "CONFIRMATION_REQUIRED":
        candidate = payload.get("pending_candidate")
        question = payload.get("question")
        if (
            not isinstance(candidate, dict)
            or not isinstance(question, dict)
            or candidate.get("question_id") != question.get("question_id")
            or candidate.get("option_id")
            not in {item.get("option_id") for item in question.get("options", [])}
        ):
            _fail("ordinary_trade_mapping_case_candidate_invalid")


def _private_case(context: ArtifactAccessContext) -> None:
    if (
        not isinstance(context, ArtifactAccessContext)
        or not context.user_id
        or not context.case_id
        or not context.allow_private
    ):
        _fail("ordinary_trade_mapping_private_case_context_required")


def _validate_mapping_batch_state(value: Any) -> None:
    if value is None:
        return
    if (
        not isinstance(value, dict)
        or set(value)
        != {
            "schema_version",
            "plan",
            "completed_batch_outcomes",
            "pending_batch_id",
        }
        or value.get("schema_version")
        != "broker_reports_ordinary_trade_mapping_batch_state_v1"
        or not isinstance(value.get("plan"), dict)
        or not isinstance(value.get("completed_batch_outcomes"), list)
        or (
            value.get("pending_batch_id") is not None
            and (
                not isinstance(value.get("pending_batch_id"), str)
                or not value["pending_batch_id"]
            )
        )
    ):
        _fail("ordinary_trade_mapping_case_batch_state_invalid")
    for item in value["completed_batch_outcomes"]:
        if (
            not isinstance(item, dict)
            or set(item) != {"batch_id", "outcome"}
            or not isinstance(item.get("batch_id"), str)
            or not item["batch_id"]
            or not isinstance(item.get("outcome"), dict)
        ):
            _fail("ordinary_trade_mapping_case_batch_state_invalid")


def _public_binding(binding: dict[str, Any]) -> dict[str, Any]:
    return {
        "canonical_binding": copy.deepcopy(binding["canonical_binding"]),
        "user_scope_sha256": binding["user_scope_sha256"],
        "case_binding_sha256": binding["case_binding_sha256"],
    }


def _valid_user_currency_decision(
    decision: dict[str, Any], *, binding: dict[str, Any]
) -> bool:
    keys = {
        "schema_version",
        "decision_kind",
        "assertion_id",
        "currency_code",
        "case_binding_sha256",
        "table_node_ids",
    }
    material = {
        "schema_version": decision.get("schema_version"),
        "currency_code": decision.get("currency_code"),
        "case_binding_sha256": decision.get("case_binding_sha256"),
        "table_node_ids": decision.get("table_node_ids"),
    }
    return (
        set(decision) == keys
        and decision.get("schema_version") == USER_CURRENCY_ASSERTION_SCHEMA_VERSION
        and isinstance(decision.get("currency_code"), str)
        and len(decision["currency_code"]) == 3
        and decision["currency_code"] == decision["currency_code"].upper()
        and decision["currency_code"].isalpha()
        and decision.get("case_binding_sha256") == binding.get("case_binding_sha256")
        and isinstance(decision.get("table_node_ids"), list)
        and decision["table_node_ids"]
        and decision["table_node_ids"] == sorted(set(decision["table_node_ids"]))
        and all(isinstance(item, str) and item for item in decision["table_node_ids"])
        and decision.get("assertion_id")
        == "usrassert_" + _sha256_json(material)[:32]
    )


def _has_confirmed_currency_assertion(
    *,
    confirmed_understandings: list[dict[str, Any]],
    currency_code: str,
    table_node_ids: list[str],
) -> bool:
    return any(
        isinstance(item, dict)
        and isinstance((decision := item.get("decision")), dict)
        and decision.get("decision_kind") == "USER_PROVIDED_CURRENCY"
        and decision.get("currency_code") == currency_code
        and set(table_node_ids).issubset(set(decision.get("table_node_ids") or []))
        for item in confirmed_understandings
    )


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _fail(code: str) -> None:
    raise OrdinaryTradeMappingCaseError(code)


__all__ = [
    "FACTORY_REQUIRED",
    "FORBIDDEN",
    "MAPPING_CASE_ARTIFACT_TYPE",
    "MAPPING_CASE_RECEIPT_SCHEMA_VERSION",
    "OrdinaryTradeMappingCaseError",
    "OrdinaryTradeMappingCaseFactory",
    "OrdinaryTradeMappingCaseRuntime",
    "mapping_case_artifact_types",
]
