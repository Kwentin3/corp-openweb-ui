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
from .ordinary_trade_semantic_mapping import (
    MAPPING_CASE_SCHEMA_VERSION,
    mapping_decision_communication_description,
)


MAPPING_CASE_ARTIFACT_TYPE = MAPPING_CASE_SCHEMA_VERSION
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
}


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
        canonical_binding = {
            "document_id": envelope.document_id,
            "canonical_version_id": envelope.canonical_version_id,
            "canonical_root_sha256": envelope.canonical_root_sha256,
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
                record.artifact_type != MAPPING_CASE_ARTIFACT_TYPE
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
        if (
            len(revisions) != len(set(revisions))
            or sorted(revisions) != list(range(1, max(revisions) + 1))
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
            pending_candidate=None,
            confirmed_understandings=copy.deepcopy(
                (prior or {}).get("confirmed_understandings") or []
            ),
            qualified_mappings=copy.deepcopy(
                outcome.get("qualified_mappings") or []
            ),
            qualification_receipts=copy.deepcopy(
                outcome.get("qualification_receipts") or []
            ),
            table_resolutions=copy.deepcopy(
                outcome.get("table_resolutions") or []
            ),
            provider_calls_total=(
                int((prior or {}).get("provider_calls_total") or 0)
                + provider_calls_total
            ),
            model_response_sha256=outcome.get("model_response_sha256"),
            execution_metadata_sha256=outcome.get(
                "execution_metadata_sha256"
            ),
            reason_code=None,
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
        )

    def _save_terminal(
        self,
        *,
        document_id: str,
        context: ArtifactAccessContext,
        status: str,
        reason_code: str,
        message: str,
        provider_calls_total: int,
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
            confirmed_understandings=copy.deepcopy(
                prior["confirmed_understandings"]
            ),
            qualified_mappings=[],
            qualification_receipts=[],
            table_resolutions=[],
            provider_calls_total=(
                prior["provider_calls_total"] + provider_calls_total
            ),
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
            status = "CLARIFICATION_REQUIRED"
            confirmed = copy.deepcopy(prior["confirmed_understandings"])
            message = "Предложенное понимание не подтверждено. Уточните ответ."
        else:
            pending = prior["pending_candidate"]
            option = next(
                item
                for item in prior["question"]["options"]
                if item["option_id"] == pending["option_id"]
            )
            confirmed = [
                *copy.deepcopy(prior["confirmed_understandings"]),
                {
                    "question_id": pending["question_id"],
                    "option_id": pending["option_id"],
                    "label_sha256": hashlib.sha256(
                        option["label"].encode("utf-8")
                    ).hexdigest(),
                    "label": option["label"],
                    "decision": copy.deepcopy(option["decision"]),
                    "decision_sha256": _sha256_json(option["decision"]),
                },
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
                            "safe_description": (
                                mapping_decision_communication_description(
                                    item["decision"]
                                )
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
            },
            "provider_calls_total": payload["provider_calls_total"],
        }

    def _next_payload(self, *, prior: dict[str, Any] | None, **values: Any) -> dict[str, Any]:
        binding = self.case_binding(
            document_id=values["document_id"], context=values["context"]
        )
        revision = int((prior or {}).get("revision") or 0) + 1
        payload = {
            "schema_version": MAPPING_CASE_SCHEMA_VERSION,
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
            "art_otmapcase_"
            + payload["case_id"][7:27]
            + f"_{payload['revision']:04d}"
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
    if (
        not isinstance(payload, dict)
        or set(payload) != expected_keys
        or payload.get("schema_version") != MAPPING_CASE_SCHEMA_VERSION
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
        if (
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
        ):
            _fail("ordinary_trade_mapping_case_confirmation_invalid")
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


def _public_binding(binding: dict[str, Any]) -> dict[str, Any]:
    return {
        "canonical_binding": copy.deepcopy(binding["canonical_binding"]),
        "user_scope_sha256": binding["user_scope_sha256"],
        "case_binding_sha256": binding["case_binding_sha256"],
    }


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
    "OrdinaryTradeMappingCaseError",
    "OrdinaryTradeMappingCaseFactory",
    "OrdinaryTradeMappingCaseRuntime",
]
