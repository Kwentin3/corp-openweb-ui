"""Minimal OpenWebUI adapter for the existing Gate 1 -> Gate 5 owner chain."""

from __future__ import annotations

import base64
import copy
import hashlib
from importlib import resources
import json
from typing import Any, Mapping

from .artifact_lifecycle import lifecycle_for_visibility
from .artifact_models import (
    ArtifactAccessContext,
    ArtifactRecord,
    RetentionPolicy,
)
from .artifact_resolver import ArtifactResolver
from .gate5_end_to_end_full_target_xml import (
    GATE5_END_TO_END_STATUS,
    Gate5EndToEndFullTargetXmlError,
)


GATE5_OPENWEBUI_PRODUCT_DEFINITION_RESOURCE = (
    "gate5_openwebui_product_definition.v0.json"
)
GATE5_OPENWEBUI_PRODUCT_DEFINITION_SHA256 = (
    "d9f6e89998bc3c92457aba99bd6c7ec389cfbd5304fb58aef9e19d9b940a97b3"
)
GATE5_OPENWEBUI_PRODUCT_STATUS = "REAL_PRODUCT_PATH_XML_VALID"
GATE5_OPENWEBUI_DECLARATION_STATUS = "DECLARATION_COMPLETE_FOR_SUPPLIED_CASE"
GATE5_OPENWEBUI_CASE_FACT_ARTIFACT_TYPE = (
    "broker_reports_gate5_openwebui_case_fact_submission_v0"
)
GATE5_OPENWEBUI_XML_ARTIFACT_TYPE = (
    "broker_reports_gate5_openwebui_xml_artifact_v0"
)
GATE5_OPENWEBUI_DELIVERY_ARTIFACT_TYPE = (
    "broker_reports_gate5_openwebui_xml_delivery_receipt_v0"
)

FACTORY_REQUIRED = (
    "Gate5OpenWebUIProductRuntimeFactory.create is the only product adapter entrypoint; "
    "it delegates Gate 4 through target projection to "
    "Gate5EndToEndFullTargetXmlRuntime.continue_from_validated_gate3"
)
FORBIDDEN = (
    "hidden G5.35 supplied-case resource, direct provider client, direct SQL, "
    "manual XML, target mapping, case-time tax inference or ACL bypass"
)


class Gate5OpenWebUIProductError(RuntimeError):
    def __init__(self, code: str, *, detail: Mapping[str, Any] | None = None) -> None:
        self.code = code
        self.detail = copy.deepcopy(dict(detail or {}))
        super().__init__(code)


class Gate5OpenWebUIProductDefinitionAuthorityFactory:
    @classmethod
    def create(cls) -> "Gate5OpenWebUIProductDefinitionAuthority":
        return Gate5OpenWebUIProductDefinitionAuthority()


class Gate5OpenWebUIProductDefinitionAuthority:
    def resolve(self) -> dict[str, Any]:
        raw = (
            resources.files("broker_reports_gate1")
            .joinpath(GATE5_OPENWEBUI_PRODUCT_DEFINITION_RESOURCE)
            .read_bytes()
        )
        if hashlib.sha256(raw).hexdigest() != GATE5_OPENWEBUI_PRODUCT_DEFINITION_SHA256:
            _fail("gate5_product_definition_hash_mismatch")
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise Gate5OpenWebUIProductError(
                "gate5_product_definition_invalid"
            ) from exc
        required = value.get("required_case_sections")
        provenance = value.get("critical_provenance")
        if (
            set(value)
            != {
                "schema_version",
                "definition_id",
                "definition_version",
                "answer_marker",
                "required_case_sections",
                "critical_provenance",
            }
            or value.get("schema_version")
            != "broker_reports_gate5_openwebui_product_definition_v0"
            or not _nonempty(value.get("definition_id"))
            or not _nonempty(value.get("definition_version"))
            or not _nonempty(value.get("answer_marker"))
            or not isinstance(required, list)
            or not required
            or len(required) != len(set(required))
            or not all(_nonempty(item) for item in required)
            or not isinstance(provenance, list)
            or not provenance
        ):
            _fail("gate5_product_definition_invalid")
        return copy.deepcopy(value)


class Gate5OpenWebUIProductRuntimeFactory:
    def __init__(
        self,
        *,
        store: Any,
        retention_policy: RetentionPolicy,
        full_target_runtime: Any,
    ) -> None:
        self._store = store
        self._retention_policy = retention_policy
        self._full_target_runtime = full_target_runtime

    def create(self) -> "Gate5OpenWebUIProductRuntime":
        if not isinstance(self._retention_policy, RetentionPolicy):
            _fail("gate5_product_retention_policy_required")
        continuation = getattr(
            self._full_target_runtime,
            "continue_from_validated_gate3",
            None,
        )
        if not callable(continuation):
            _fail("gate5_product_full_target_owner_required")
        return Gate5OpenWebUIProductRuntime(
            store=self._store,
            retention_policy=self._retention_policy,
            full_target_runtime=self._full_target_runtime,
        )


class Gate5OpenWebUIProductRuntime:
    def __init__(
        self,
        *,
        store: Any,
        retention_policy: RetentionPolicy,
        full_target_runtime: Any,
    ) -> None:
        self._store = store
        self._retention_policy = retention_policy
        self._full_target_runtime = full_target_runtime
        self._definition = (
            Gate5OpenWebUIProductDefinitionAuthorityFactory.create().resolve()
        )
        self._resolver = ArtifactResolver(store)

    def process(
        self,
        *,
        context: ArtifactAccessContext,
        source_file_id: str,
        source_filename: str,
        source_mime_type: str,
        source_bytes: bytes,
        financial_annotations_artifact_id: str,
        latest_user_message: str,
    ) -> dict[str, Any]:
        self._validate_context(context)
        patch = self._parse_submission(latest_user_message)
        if patch is not None:
            self._persist_submission(
                context=context,
                source_file_id=source_file_id,
                patch=patch,
            )
        facts, fact_artifact_ids = self._merged_case_facts(context=context)
        missing_sections = [
            item
            for item in self._definition["required_case_sections"]
            if item not in facts
        ]
        if missing_sections:
            return self._case_fact_blocker(
                missing_sections,
                latest_user_message=latest_user_message,
            )

        proof_input = self._proof_input(
            context=context,
            source_file_id=source_file_id,
            source_filename=source_filename,
            source_mime_type=source_mime_type,
            source_bytes=source_bytes,
            facts=facts,
        )
        try:
            result = self._full_target_runtime.continue_from_validated_gate3(
                proof_input=proof_input,
                context=context,
                financial_annotations_artifact_id=(
                    financial_annotations_artifact_id
                ),
            )
        except Gate5EndToEndFullTargetXmlError as exc:
            return {
                "schema_version": "broker_reports_gate5_openwebui_product_result_v0",
                "status": "blocked",
                "blocker_code": exc.code,
                "blocker": copy.deepcopy(exc.blocker),
                "missing_fact": exc.field or None,
                "xml_created": False,
            }
        if result.get("status") != GATE5_END_TO_END_STATUS:
            _fail("gate5_product_full_target_terminal_missing")
        xml_record = self._persist_xml(
            context=context,
            source_file_id=source_file_id,
            fact_artifact_ids=fact_artifact_ids,
            result=result,
        )
        target = result["receipt"]["target_result"]
        return {
            "schema_version": "broker_reports_gate5_openwebui_product_result_v0",
            "status": GATE5_OPENWEBUI_PRODUCT_STATUS,
            "declaration_status": GATE5_OPENWEBUI_DECLARATION_STATUS,
            "xml_created": True,
            "xml_artifact_id": xml_record.artifact_id,
            "xml_filename": self._xml_filename(proof_input, target),
            "xml_bytes": result["xml_bytes"],
            "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
            "semantic_input_sha256": result["semantic_input"][
                "semantic_input_sha256"
            ],
            "projection_definition_sha256": target[
                "projection_definition_binding"
            ]["projection_definition_sha256"],
            "xml_sha256": target["xml_binding"]["xml_sha256"],
            "official_xsd_sha256": target["conformance_proof"]["xsd_sha256"],
            "official_xsd_valid": target["conformance_proof"]["xsd_valid"],
            "fact_artifact_ids": fact_artifact_ids,
        }

    def persist_delivery_receipt(
        self,
        *,
        context: ArtifactAccessContext,
        source_file_id: str,
        xml_artifact_id: str,
        openwebui_file_id: str,
        xml_sha256: str,
    ) -> ArtifactRecord:
        payload = {
            "schema_version": "broker_reports_gate5_openwebui_xml_delivery_receipt_v0",
            "xml_artifact_id": xml_artifact_id,
            "openwebui_file_id": openwebui_file_id,
            "xml_sha256": xml_sha256,
            "authenticated_user_ref": context.user_id,
            "case_id": context.case_id,
            "synthetic_proof_evidence": True,
            "real_user_fact": False,
        }
        return self._put_or_reuse_exact(
            context=context,
            record=self._private_record(
                artifact_id=_artifact_id("g536delivery", context, payload),
                artifact_type=GATE5_OPENWEBUI_DELIVERY_ARTIFACT_TYPE,
                context=context,
                source_file_id=source_file_id,
                payload=payload,
                safe_metadata={
                    "xml_sha256": xml_sha256,
                    "native_download_boundary": True,
                },
            ),
        )

    def _parse_submission(self, text: str) -> dict[str, Any] | None:
        marker = self._definition["answer_marker"]
        if marker not in str(text or ""):
            return None
        raw = str(text).split(marker, 1)[1].strip()
        if raw.startswith("```"):
            lines = raw.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            raw = "\n".join(lines).strip()
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise Gate5OpenWebUIProductError(
                "gate5_product_case_fact_json_invalid"
            ) from exc
        allowed = set(self._definition["required_case_sections"])
        if (
            not isinstance(value, dict)
            or not value
            or not set(value) <= allowed
            or any(not isinstance(item, (dict, list)) for item in value.values())
        ):
            _fail("gate5_product_case_fact_patch_invalid")
        return copy.deepcopy(value)

    def _persist_submission(
        self,
        *,
        context: ArtifactAccessContext,
        source_file_id: str,
        patch: dict[str, Any],
    ) -> ArtifactRecord:
        current, _ = self._merged_case_facts(context=context)
        _merge_without_conflicts(current, patch)
        payload = {
            "schema_version": "broker_reports_gate5_openwebui_case_fact_submission_v0",
            "definition_binding": {
                "definition_id": self._definition["definition_id"],
                "definition_version": self._definition["definition_version"],
                "definition_sha256": GATE5_OPENWEBUI_PRODUCT_DEFINITION_SHA256,
            },
            "patch": copy.deepcopy(patch),
            "synthetic_proof_evidence": True,
            "real_user_fact": False,
        }
        return self._put_or_reuse_exact(
            context=context,
            record=self._private_record(
                artifact_id=_artifact_id("g536facts", context, payload),
                artifact_type=GATE5_OPENWEBUI_CASE_FACT_ARTIFACT_TYPE,
                context=context,
                source_file_id=source_file_id,
                payload=payload,
                safe_metadata={
                    "definition_sha256": GATE5_OPENWEBUI_PRODUCT_DEFINITION_SHA256,
                    "patch_sha256": _sha256(patch),
                    "synthetic_proof_evidence": True,
                },
            ),
        )

    def _merged_case_facts(
        self,
        *,
        context: ArtifactAccessContext,
    ) -> tuple[dict[str, Any], list[str]]:
        records = sorted(
            (
                record
                for record in self._resolver.catalog_run(context)
                if record.artifact_type == GATE5_OPENWEBUI_CASE_FACT_ARTIFACT_TYPE
            ),
            key=lambda item: (item.created_at, item.artifact_id),
        )
        merged: dict[str, Any] = {}
        artifact_ids: list[str] = []
        for record in records:
            resolved = self._resolver.resolve(record.artifact_id, context)
            payload = resolved["payload"]
            if (
                not isinstance(payload, dict)
                or payload.get("schema_version")
                != "broker_reports_gate5_openwebui_case_fact_submission_v0"
                or payload.get("synthetic_proof_evidence") is not True
                or payload.get("real_user_fact") is not False
                or not isinstance(payload.get("patch"), dict)
            ):
                _fail("gate5_product_case_fact_artifact_invalid")
            _merge_without_conflicts(merged, payload["patch"])
            artifact_ids.append(record.artifact_id)
        return merged, artifact_ids

    def _proof_input(
        self,
        *,
        context: ArtifactAccessContext,
        source_file_id: str,
        source_filename: str,
        source_mime_type: str,
        source_bytes: bytes,
        facts: dict[str, Any],
    ) -> dict[str, Any]:
        if not isinstance(source_bytes, bytes) or not source_bytes:
            _fail("gate5_product_source_bytes_required")
        try:
            content_transport = {"content_utf8": source_bytes.decode("utf-8")}
        except UnicodeDecodeError:
            content_transport = {
                "content_base64": base64.b64encode(source_bytes).decode("ascii")
            }
        scope = facts.get("scope")
        if not isinstance(scope, dict):
            _fail("gate5_product_scope_facts_required")
        proof_input: dict[str, Any] = {
            "schema_version": "broker_reports_gate5_end_to_end_supplied_case_v0",
            "case_fact_set_id": "g536_" + _sha256(
                {
                    "user_id": context.user_id,
                    "case_id": context.case_id,
                    "normalization_run_id": context.normalization_run_id,
                }
            )[:24],
            "case_fact_set_version": (
                self._definition["definition_version"] + "+" + _sha256(facts)[:16]
            ),
            "binding": {
                "authenticated_user_ref": context.user_id,
                "case_id": context.case_id,
                "workspace_model_id": context.workspace_model_id,
                "normalization_run_ref": context.normalization_run_id,
                "taxpayer_scope_ref": scope.get("taxpayer_scope_ref"),
                "tax_period": scope.get("tax_period"),
                "synthetic_proof_evidence": True,
                "real_user_fact": False,
            },
            "supplied_source": {
                "private_ref": source_file_id,
                "filename": source_filename,
                "mime_type": source_mime_type,
                "source_kind": "synthetic",
                **content_transport,
                "content_sha256": hashlib.sha256(source_bytes).hexdigest(),
                "custody": {
                    "openwebui_file_id": source_file_id,
                    "authenticated_owner_ref": context.user_id,
                    "original_custody": True,
                    "synthetic_proof_evidence": True,
                    "real_user_fact": False,
                },
            },
            "critical_provenance": copy.deepcopy(
                self._definition["critical_provenance"]
            ),
        }
        for key in self._definition["required_case_sections"]:
            proof_input[key] = copy.deepcopy(facts[key])
        filing_identity = proof_input.get("filing_and_party_identity")
        signer = (
            filing_identity.get("signer")
            if isinstance(filing_identity, dict)
            else None
        )
        if (
            isinstance(signer, dict)
            and signer.get("signer_capacity") == "taxpayer_self"
        ):
            # The authenticated native OpenWebUI user is already trusted case
            # context. Do not ask the operator to repeat or guess its internal ID.
            signer["signer_ref"] = context.user_id
        return proof_input

    def _persist_xml(
        self,
        *,
        context: ArtifactAccessContext,
        source_file_id: str,
        fact_artifact_ids: list[str],
        result: dict[str, Any],
    ) -> ArtifactRecord:
        xml_bytes = result["xml_bytes"]
        target = result["receipt"]["target_result"]
        payload = {
            "schema_version": "broker_reports_gate5_openwebui_xml_artifact_v0",
            "xml_base64": base64.b64encode(xml_bytes).decode("ascii"),
            "xml_sha256": target["xml_binding"]["xml_sha256"],
            "semantic_input_sha256": result["semantic_input"][
                "semantic_input_sha256"
            ],
            "projection_definition_binding": copy.deepcopy(
                target["projection_definition_binding"]
            ),
            "official_xsd_conformance": copy.deepcopy(
                target["conformance_proof"]
            ),
            "gate5_receipt": copy.deepcopy(result["receipt"]),
            "case_fact_artifact_ids": list(fact_artifact_ids),
            "synthetic_proof_evidence": True,
            "real_user_fact": False,
        }
        if hashlib.sha256(xml_bytes).hexdigest() != payload["xml_sha256"]:
            _fail("gate5_product_xml_hash_mismatch")
        return self._put_or_reuse_exact(
            context=context,
            record=self._private_record(
                artifact_id=_artifact_id("g536xml", context, payload),
                artifact_type=GATE5_OPENWEBUI_XML_ARTIFACT_TYPE,
                context=context,
                source_file_id=source_file_id,
                payload=payload,
                safe_metadata={
                    "xml_sha256": payload["xml_sha256"],
                    "semantic_input_sha256": payload["semantic_input_sha256"],
                    "projection_definition_sha256": payload[
                        "projection_definition_binding"
                    ]["projection_definition_sha256"],
                    "official_xsd_valid": payload["official_xsd_conformance"][
                        "xsd_valid"
                    ],
                },
            ),
        )

    def _put_or_reuse_exact(
        self,
        *,
        context: ArtifactAccessContext,
        record: ArtifactRecord,
    ) -> ArtifactRecord:
        for existing in self._resolver.catalog_run(context):
            if existing.artifact_id != record.artifact_id:
                continue
            resolved = self._resolver.resolve(existing.artifact_id, context)
            if (
                existing.artifact_type != record.artifact_type
                or resolved["payload"] != record.payload
            ):
                _fail("gate5_product_idempotent_artifact_conflict")
            return resolved["record"]
        return self._store.put_record(record)

    def _private_record(
        self,
        *,
        artifact_id: str,
        artifact_type: str,
        context: ArtifactAccessContext,
        source_file_id: str,
        payload: dict[str, Any],
        safe_metadata: dict[str, Any],
    ) -> ArtifactRecord:
        return ArtifactRecord(
            artifact_id=artifact_id,
            artifact_type=artifact_type,
            case_id=context.case_id,
            chat_id=context.chat_id,
            user_id=context.user_id,
            workspace_model_id=context.workspace_model_id,
            normalization_run_id=context.normalization_run_id,
            document_id=None,
            source_file_ref={
                "provider": "openwebui",
                "openwebui_file_id": source_file_id,
                "source_deleted": False,
            },
            visibility="private_case",
            storage_backend="project_artifact_payload",
            retention_policy=self._retention_policy,
            access_policy={
                "requires_user_id": True,
                "requires_case_or_chat": True,
                "requires_workspace_model_id_when_present": True,
            },
            validation_status="validated",
            lifecycle_status=lifecycle_for_visibility(
                visibility="private_case",
                validation_status="validated",
            ),
            payload_kind="json_file",
            payload=copy.deepcopy(payload),
            safe_metadata=copy.deepcopy(safe_metadata),
        )

    def _case_fact_blocker(
        self,
        missing_sections: list[str],
        *,
        latest_user_message: str,
    ) -> dict[str, Any]:
        return {
            "schema_version": "broker_reports_gate5_openwebui_product_result_v0",
            "status": "blocked",
            "blocker_code": "gate5_product_case_facts_required",
            "blocker": {
                "stage": "trusted_case_fact_boundary",
                "missing_sections": list(missing_sections),
                "action": "provide_structured_supplied_case_facts",
                "answer_marker": self._definition["answer_marker"],
                "answer_marker_observed": (
                    self._definition["answer_marker"]
                    in str(latest_user_message or "")
                ),
                "interaction_chars": len(str(latest_user_message or "")),
            },
            "missing_fact": None,
            "xml_created": False,
        }

    @staticmethod
    def _validate_context(context: ArtifactAccessContext) -> None:
        if (
            not isinstance(context, ArtifactAccessContext)
            or not context.user_id
            or not context.case_id
            or not context.workspace_model_id
            or not context.allow_private
        ):
            _fail("gate5_product_authenticated_case_context_required")

    @staticmethod
    def _xml_filename(
        proof_input: dict[str, Any],
        target: dict[str, Any],
    ) -> str:
        tax_period = str(proof_input["binding"]["tax_period"] or "unknown")
        return (
            f"3-ndfl-{tax_period}-"
            f"{target['xml_binding']['xml_sha256'][:12]}.xml"
        )


def _merge_without_conflicts(target: dict[str, Any], patch: dict[str, Any]) -> None:
    for key, value in patch.items():
        if key not in target:
            target[key] = copy.deepcopy(value)
            continue
        current = target[key]
        if isinstance(current, dict) and isinstance(value, dict):
            _merge_without_conflicts(current, value)
            continue
        if current != value:
            raise Gate5OpenWebUIProductError(
                "gate5_product_case_fact_conflict",
                detail={"field": key},
            )


def _artifact_id(prefix: str, context: ArtifactAccessContext, payload: Any) -> str:
    return prefix + "_" + _sha256(
        {
            "user_id": context.user_id,
            "case_id": context.case_id,
            "normalization_run_id": context.normalization_run_id,
            "payload": payload,
        }
    )[:40]


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


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value) and value == value.strip()


def _fail(code: str) -> None:
    raise Gate5OpenWebUIProductError(code)


__all__ = [
    "FACTORY_REQUIRED",
    "FORBIDDEN",
    "GATE5_OPENWEBUI_CASE_FACT_ARTIFACT_TYPE",
    "GATE5_OPENWEBUI_DECLARATION_STATUS",
    "GATE5_OPENWEBUI_DELIVERY_ARTIFACT_TYPE",
    "GATE5_OPENWEBUI_PRODUCT_DEFINITION_RESOURCE",
    "GATE5_OPENWEBUI_PRODUCT_DEFINITION_SHA256",
    "GATE5_OPENWEBUI_PRODUCT_STATUS",
    "GATE5_OPENWEBUI_XML_ARTIFACT_TYPE",
    "Gate5OpenWebUIProductDefinitionAuthorityFactory",
    "Gate5OpenWebUIProductError",
    "Gate5OpenWebUIProductRuntimeFactory",
]
