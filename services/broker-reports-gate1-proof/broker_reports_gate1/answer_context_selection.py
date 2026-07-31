from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from typing import Any

from .artifact_lifecycle import lifecycle_for_visibility
from .artifact_models import (
    ArtifactAccessContext,
    ArtifactRecord,
    ArtifactStorePort,
)
from .artifact_resolver import ArtifactResolver
from .contracts import SOURCE_FACT_STITCH_RESULT_SCHEMA_VERSION, stable_digest
from .gate2_domain_contracts import DOMAIN_RUN_SCHEMA_VERSION
from .semantic_visual_table_contracts import SEMANTIC_VISUAL_TABLE_ORIGIN
from .table_projection import TableProjectionValidator


SEMANTIC_VISUAL_TABLE_ENVELOPE_SCHEMA_VERSION = (
    "broker_reports_semantic_visual_table_envelope_v1"
)
ANSWER_CONTEXT_SCHEMA_VERSION = "broker_reports_answer_context_v1"
ANSWER_CONTEXT_POLICY_VERSION = "broker_reports_answer_context_selection_v1"
ANSWER_CONTEXT_RECEIPT_SCHEMA_VERSION = (
    "broker_reports_answer_context_selection_receipt_v1"
)
FACTORY_REQUIRED = "AnswerContextSelectionFactory.create is the only production answer-context selection entrypoint"
FORBIDDEN = (
    "Callers must not assemble answer context from raw source, crop, provider output, "
    "Knowledge, RAG or duplicate representations"
)


def answer_context_ref_for_run(
    *, extraction_run_ref: str, normalization_run_id: str
) -> str:
    if not extraction_run_ref or not normalization_run_id:
        raise AnswerContextSelectionError("answer_context_run_identity_missing")
    return "answerctx_" + stable_digest(
        [
            ANSWER_CONTEXT_SCHEMA_VERSION,
            normalization_run_id,
            extraction_run_ref,
        ],
        length=24,
    )


def answer_context_receipt_ref_for_run(
    *, extraction_run_ref: str, normalization_run_id: str
) -> str:
    return "answerctxreceipt_" + stable_digest(
        [
            ANSWER_CONTEXT_RECEIPT_SCHEMA_VERSION,
            normalization_run_id,
            extraction_run_ref,
        ],
        length=24,
    )


class AnswerContextSelectionError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class AnswerContextSelectionResult:
    context_ref: str
    receipt_ref: str
    selection_status: str
    safe_summary: dict[str, Any]


class AnswerContextSelectionFactory:
    def __init__(self, *, store: ArtifactStorePort) -> None:
        self.store = store

    def create(self) -> "AnswerContextSelectionService":
        return AnswerContextSelectionService(self.store)


class AnswerContextSelectionService:
    def __init__(self, store: ArtifactStorePort) -> None:
        self.store = store
        self.resolver = ArtifactResolver(store)

    def build_and_persist(
        self,
        *,
        extraction_run_ref: str,
        context: ArtifactAccessContext,
    ) -> AnswerContextSelectionResult:
        self._require_private_context(context)
        run_resolved = self.resolver.resolve(extraction_run_ref, context)
        run_record = run_resolved["record"]
        run = _object(run_resolved["payload"])
        if run_record.artifact_type != DOMAIN_RUN_SCHEMA_VERSION:
            raise AnswerContextSelectionError("answer_context_run_type_mismatch")
        if run.get("run_status") != "completed":
            raise AnswerContextSelectionError("answer_context_gate2_run_not_completed")

        graph = self._build_graph(run=run, context=context)
        if not graph["evidence_groups"]:
            raise AnswerContextSelectionError("answer_context_evidence_group_missing")

        context_ref = answer_context_ref_for_run(
            extraction_run_ref=extraction_run_ref,
            normalization_run_id=context.normalization_run_id,
        )
        receipt_ref = answer_context_receipt_ref_for_run(
            extraction_run_ref=extraction_run_ref,
            normalization_run_id=context.normalization_run_id,
        )
        payload = {
            "schema_version": ANSWER_CONTEXT_SCHEMA_VERSION,
            "policy_version": ANSWER_CONTEXT_POLICY_VERSION,
            "context_id": context_ref,
            "normalization_run_id": context.normalization_run_id,
            "terminal_gate2_run_ref": extraction_run_ref,
            "selection_contract": {
                "one_interpretation_bearing_representation_per_evidence_group": True,
                "semantic_visual_table_preferred": True,
                "provenance_only_content_presented_as_financial_facts": False,
                "answer_model_deduplication_required": False,
            },
            "evidence_groups": graph["evidence_groups"],
            "knowledge_vector_guard": {
                "knowledge_rag_used": False,
                "vectorization_performed": False,
                "ordinary_upload_used": False,
                "document_store_write_performed": False,
            },
        }
        payload["integrity_hash"] = _integrity_hash(payload)
        validate_answer_context(payload)

        retention_policy = run_record.retention_policy
        self.store.put_record(
            ArtifactRecord(
                artifact_id=context_ref,
                artifact_type=ANSWER_CONTEXT_SCHEMA_VERSION,
                case_id=context.case_id,
                chat_id=context.chat_id,
                user_id=context.user_id,
                workspace_model_id=context.workspace_model_id,
                normalization_run_id=context.normalization_run_id,
                document_id=None,
                source_file_ref=None,
                visibility="private_case",
                storage_backend="project_artifact_payload",
                retention_policy=retention_policy,
                access_policy={
                    "requires_user_id": True,
                    "requires_case_or_chat": True,
                    "requires_workspace_model_id_when_present": bool(
                        context.workspace_model_id
                    ),
                    "answer_model_context_only": True,
                },
                validation_status="validated",
                lifecycle_status=lifecycle_for_visibility(
                    visibility="private_case", validation_status="validated"
                ),
                payload_kind="json_file",
                payload=payload,
                safe_metadata={
                    "selection_status": "passed",
                    "evidence_groups_total": len(graph["evidence_groups"]),
                    "semantic_groups_total": graph["semantic_groups_total"],
                    "interpretation_bearing_total": len(graph["evidence_groups"]),
                    "duplicate_financial_fact_presentations_total": 0,
                    "integrity_hash": payload["integrity_hash"],
                },
            )
        )

        receipt = {
            "schema_version": ANSWER_CONTEXT_RECEIPT_SCHEMA_VERSION,
            "selection_status": "passed",
            "context_ref": context_ref,
            "context_integrity_hash": payload["integrity_hash"],
            "terminal_gate2_run_ref": extraction_run_ref,
            "evidence_groups_total": len(graph["evidence_groups"]),
            "semantic_groups_total": graph["semantic_groups_total"],
            "interpretation_bearing_total": len(graph["evidence_groups"]),
            "provenance_only_representations_total": graph[
                "provenance_only_representations_total"
            ],
            "duplicate_financial_fact_presentations_total": 0,
            "source_evidence_resolvable": True,
            "answer_model_deduplication_required": False,
            "private_values_in_receipt": False,
            "knowledge_rag_used": False,
            "vectorization_performed": False,
        }
        receipt["integrity_hash"] = _integrity_hash(receipt)
        self.store.put_record(
            ArtifactRecord(
                artifact_id=receipt_ref,
                artifact_type=ANSWER_CONTEXT_RECEIPT_SCHEMA_VERSION,
                case_id=context.case_id,
                chat_id=context.chat_id,
                user_id=context.user_id,
                workspace_model_id=context.workspace_model_id,
                normalization_run_id=context.normalization_run_id,
                document_id=None,
                source_file_ref=None,
                visibility="safe_internal",
                storage_backend="project_artifact_store",
                retention_policy=retention_policy,
                access_policy={
                    "requires_user_id": True,
                    "requires_case_or_chat": True,
                    "requires_workspace_model_id_when_present": bool(
                        context.workspace_model_id
                    ),
                },
                validation_status="validated",
                lifecycle_status=lifecycle_for_visibility(
                    visibility="safe_internal", validation_status="validated"
                ),
                payload_kind="inline_json",
                payload=receipt,
                safe_metadata=copy.deepcopy(receipt),
            )
        )
        return AnswerContextSelectionResult(
            context_ref=context_ref,
            receipt_ref=receipt_ref,
            selection_status="passed",
            safe_summary=copy.deepcopy(receipt),
        )

    def resolve_for_answer(
        self,
        *,
        context_ref: str,
        context: ArtifactAccessContext,
    ) -> dict[str, Any]:
        self._require_private_context(context)
        resolved = self.resolver.resolve(context_ref, context)
        record = resolved["record"]
        if record.artifact_type != ANSWER_CONTEXT_SCHEMA_VERSION:
            raise AnswerContextSelectionError("answer_context_type_mismatch")
        payload = _object(resolved["payload"])
        validate_answer_context(payload)
        for ref in _provenance_artifact_refs(payload):
            self.resolver.resolve_record(ref, context)
        return copy.deepcopy(payload)

    def _build_graph(
        self,
        *,
        run: dict[str, Any],
        context: ArtifactAccessContext,
    ) -> dict[str, Any]:
        package_refs = _strings(run.get("domain_package_refs"))
        facts_refs = _strings(run.get("source_facts_refs"))
        derived_refs = _strings(run.get("derived_source_unit_refs"))
        owner_fact_ids = self._owner_fact_ids(run=run, context=context)
        packages = {ref: self._resolve_payload(ref, context) for ref in package_refs}
        facts_by_package: dict[str, list[tuple[str, dict[str, Any]]]] = {}
        for facts_ref in facts_refs:
            facts_payload = self._resolve_payload(facts_ref, context)
            for package_ref in _strings(facts_payload.get("package_refs")):
                facts_by_package.setdefault(package_ref, []).append(
                    (facts_ref, facts_payload)
                )

        selected_units: list[tuple[str, dict[str, Any]]] = []
        for ref in derived_refs:
            payload = self._resolve_payload(ref, context)
            selected_units.append((ref, _object(payload.get("source_unit"))))
        if not selected_units:
            selected_units = [
                (ref, _object(package.get("source_unit")))
                for ref, package in packages.items()
            ]

        semantic_groups: dict[str, dict[str, Any]] = {}
        ordinary_groups: dict[str, dict[str, Any]] = {}
        for unit_artifact_ref, unit in selected_units:
            if not unit:
                continue
            representation = _object(unit.get("upstream_source_representation"))
            if (
                representation.get("source_representation_kind")
                == "semantic_visual_logical_table"
            ):
                projection_ref = str(
                    unit.get("table_projection_artifact_ref")
                    or unit.get("private_slice_artifact_ref")
                    or ""
                )
                if not projection_ref:
                    raise AnswerContextSelectionError(
                        "answer_context_semantic_projection_ref_missing"
                    )
                semantic_groups.setdefault(
                    projection_ref,
                    {"unit_refs": [], "package_refs": []},
                )["unit_refs"].append(unit_artifact_ref)
            else:
                unit_id = str(unit.get("unit_id") or unit_artifact_ref)
                ordinary_groups.setdefault(
                    unit_id,
                    {
                        "unit": unit,
                        "unit_refs": [],
                        "package_refs": [],
                    },
                )["unit_refs"].append(unit_artifact_ref)

        for package_ref, package in packages.items():
            unit = _object(package.get("source_unit"))
            representation = _object(unit.get("upstream_source_representation"))
            if (
                representation.get("source_representation_kind")
                == "semantic_visual_logical_table"
            ):
                projection_ref = str(
                    unit.get("table_projection_artifact_ref")
                    or unit.get("private_slice_artifact_ref")
                    or ""
                )
                if projection_ref in semantic_groups:
                    semantic_groups[projection_ref]["package_refs"].append(package_ref)
            else:
                unit_id = str(unit.get("unit_id") or "")
                if unit_id in ordinary_groups:
                    ordinary_groups[unit_id]["package_refs"].append(package_ref)

        catalog = self.resolver.catalog_run(context)
        groups: list[dict[str, Any]] = []
        provenance_only_total = 0
        for projection_ref, group in sorted(semantic_groups.items()):
            projection = self._resolve_payload(projection_ref, context)
            if projection.get("table_origin") != SEMANTIC_VISUAL_TABLE_ORIGIN:
                raise AnswerContextSelectionError(
                    "answer_context_semantic_projection_origin_mismatch"
                )
            if (
                TableProjectionValidator().validate(projection).get("validator_status")
                != "passed"
            ):
                raise AnswerContextSelectionError(
                    "answer_context_semantic_projection_invalid"
                )
            document_ref = str(projection.get("source_document_ref") or "")
            source_scope_ref = str(projection.get("source_unit_ref") or "")
            envelope = self._semantic_envelope(
                catalog=catalog,
                document_ref=document_ref,
                source_scope_ref=source_scope_ref,
                context=context,
            )
            package_group_refs = sorted(set(group["package_refs"]))
            facts_group_refs = sorted(
                {
                    facts_ref
                    for package_ref in package_group_refs
                    for facts_ref, _ in facts_by_package.get(package_ref, [])
                }
            )
            source_refs = self._source_evidence_refs(
                catalog=catalog,
                document_ref=document_ref,
                excluded={
                    projection_ref,
                    *group["unit_refs"],
                    *package_group_refs,
                    *facts_group_refs,
                },
            )
            group_id = "evidencegroup_" + stable_digest(
                [document_ref, source_scope_ref, projection.get("table_projection_id")],
                length=24,
            )
            provenance = [
                _provenance_representation(
                    representation_id="provsource_"
                    + stable_digest([group_id, source_refs], length=20),
                    kind="retained_source_evidence",
                    artifact_refs=source_refs,
                    derived_from=[],
                ),
                _provenance_representation(
                    representation_id="provgate2_"
                    + stable_digest(
                        [group_id, package_group_refs, facts_group_refs], length=20
                    ),
                    kind="gate2_derived_facts",
                    artifact_refs=[*package_group_refs, *facts_group_refs],
                    derived_from=[projection_ref],
                ),
            ]
            provenance = [item for item in provenance if item["artifact_refs"]]
            provenance_only_total += len(provenance)
            transcription = _object(envelope.get("semantic_transcription"))
            groups.append(
                {
                    "evidence_group_id": group_id,
                    "source_scope_id": "sourcescope_"
                    + stable_digest([document_ref, source_scope_ref], length=24),
                    "source_document_ref": document_ref,
                    "source_unit_ref": source_scope_ref,
                    "source_reference": {
                        "page_refs": _strings(projection.get("page_refs")),
                        "section_refs": _strings(projection.get("section_refs")),
                    },
                    "representations": [
                        {
                            "representation_id": str(
                                envelope.get("envelope_id") or projection_ref
                            ),
                            "representation_kind": ("semantic_visual_logical_table"),
                            "interpretation_selection_role": ("interpretation_bearing"),
                            "derived_from_artifact_refs": [projection_ref],
                            "content": {
                                "description": transcription.get("description"),
                                "rows": copy.deepcopy(transcription.get("rows") or []),
                            },
                        },
                        *provenance,
                    ],
                }
            )

        for unit_id, group in sorted(ordinary_groups.items()):
            package_group_refs = sorted(set(group["package_refs"]))
            compact_facts: list[dict[str, Any]] = []
            facts_group_refs: list[str] = []
            seen_fact_ids: set[str] = set()
            for package_ref in package_group_refs:
                for facts_ref, facts_payload in facts_by_package.get(package_ref, []):
                    facts_group_refs.append(facts_ref)
                    for fact in _dicts(facts_payload.get("facts")):
                        fact_id = str(fact.get("fact_id") or "")
                        if not fact_id or fact_id in seen_fact_ids:
                            continue
                        if owner_fact_ids is not None and fact_id not in owner_fact_ids:
                            continue
                        seen_fact_ids.add(fact_id)
                        compact_facts.append(_compact_fact(fact))
            if not compact_facts:
                continue
            unit = group["unit"]
            document_ref = str(
                next(
                    (
                        packages[ref].get("document_ref")
                        for ref in package_group_refs
                        if ref in packages
                    ),
                    "",
                )
                or ""
            )
            source_refs = self._source_evidence_refs(
                catalog=catalog,
                document_ref=document_ref,
                excluded={
                    *group["unit_refs"],
                    *package_group_refs,
                    *facts_group_refs,
                },
            )
            group_id = "evidencegroup_" + stable_digest(
                [document_ref, unit_id], length=24
            )
            provenance = _provenance_representation(
                representation_id="provsource_"
                + stable_digest([group_id, source_refs], length=20),
                kind="retained_source_evidence",
                artifact_refs=source_refs,
                derived_from=[],
            )
            representations = [
                {
                    "representation_id": "gate2facts_"
                    + stable_digest([group_id, sorted(seen_fact_ids)], length=20),
                    "representation_kind": "validated_gate2_facts",
                    "interpretation_selection_role": "interpretation_bearing",
                    "derived_from_artifact_refs": sorted(
                        set([*package_group_refs, *facts_group_refs])
                    ),
                    "content": {"facts": compact_facts},
                }
            ]
            if provenance["artifact_refs"]:
                representations.append(provenance)
                provenance_only_total += 1
            groups.append(
                {
                    "evidence_group_id": group_id,
                    "source_scope_id": "sourcescope_"
                    + stable_digest([document_ref, unit_id], length=24),
                    "source_document_ref": document_ref,
                    "source_unit_ref": unit_id,
                    "source_reference": {
                        "page_refs": _strings(unit.get("page_refs")),
                        "section_refs": _strings(unit.get("section_refs")),
                    },
                    "representations": representations,
                }
            )

        return {
            "evidence_groups": sorted(
                groups, key=lambda item: str(item["evidence_group_id"])
            ),
            "semantic_groups_total": len(semantic_groups),
            "provenance_only_representations_total": provenance_only_total,
        }

    def _owner_fact_ids(
        self,
        *,
        run: dict[str, Any],
        context: ArtifactAccessContext,
    ) -> set[str] | None:
        stitch_refs = _strings(run.get("stitch_result_refs"))
        if not stitch_refs:
            return None
        owner_fact_ids: set[str] = set()
        for stitch_ref in stitch_refs:
            stitch = self._resolve_payload(stitch_ref, context)
            if (
                stitch.get("schema_version")
                != SOURCE_FACT_STITCH_RESULT_SCHEMA_VERSION
            ):
                raise AnswerContextSelectionError(
                    "answer_context_stitch_result_type_mismatch"
                )
            for ownership in _dicts(stitch.get("ownership_map")):
                if ownership.get("ownership_status") not in {
                    "accepted_fact",
                    "unknown_source_row",
                }:
                    continue
                fact_id = str(ownership.get("owner_fact_id") or "")
                if not fact_id:
                    raise AnswerContextSelectionError(
                        "answer_context_owner_fact_id_missing"
                    )
                owner_fact_ids.add(fact_id)
        return owner_fact_ids

    def _resolve_payload(
        self, ref: str, context: ArtifactAccessContext
    ) -> dict[str, Any]:
        return _object(self.resolver.resolve(ref, context)["payload"])

    def _semantic_envelope(
        self,
        *,
        catalog: list[ArtifactRecord],
        document_ref: str,
        source_scope_ref: str,
        context: ArtifactAccessContext,
    ) -> dict[str, Any]:
        matches = [
            record
            for record in catalog
            if record.artifact_type == SEMANTIC_VISUAL_TABLE_ENVELOPE_SCHEMA_VERSION
            and str(record.document_id or "") == document_ref
            and str(record.safe_metadata.get("candidate_ref") or "") == source_scope_ref
        ]
        if len(matches) != 1:
            raise AnswerContextSelectionError(
                "answer_context_semantic_envelope_identity_not_unique"
            )
        return self._resolve_payload(matches[0].artifact_id, context)

    def _source_evidence_refs(
        self,
        *,
        catalog: list[ArtifactRecord],
        document_ref: str,
        excluded: set[str],
    ) -> list[str]:
        allowed_types = {
            "source_file_ref_v0",
            "private_normalized_source_payload_v0",
        }
        return sorted(
            record.artifact_id
            for record in catalog
            if str(record.document_id or "") == document_ref
            and record.artifact_type in allowed_types
            and record.artifact_id not in excluded
        )

    @staticmethod
    def _require_private_context(context: ArtifactAccessContext) -> None:
        if not context.allow_private or not context.require_source_available:
            raise AnswerContextSelectionError(
                "answer_context_private_source_available_context_required"
            )


def validate_answer_context(payload: dict[str, Any]) -> None:
    if payload.get("schema_version") != ANSWER_CONTEXT_SCHEMA_VERSION:
        raise AnswerContextSelectionError("answer_context_schema_mismatch")
    if payload.get("policy_version") != ANSWER_CONTEXT_POLICY_VERSION:
        raise AnswerContextSelectionError("answer_context_policy_mismatch")
    if _integrity_hash(payload) != payload.get("integrity_hash"):
        raise AnswerContextSelectionError("answer_context_integrity_mismatch")
    group_ids: set[str] = set()
    for group in _dicts(payload.get("evidence_groups")):
        group_id = str(group.get("evidence_group_id") or "")
        if not group_id or group_id in group_ids:
            raise AnswerContextSelectionError("answer_context_evidence_group_duplicate")
        group_ids.add(group_id)
        representations = _dicts(group.get("representations"))
        selected = [
            item
            for item in representations
            if item.get("interpretation_selection_role") == "interpretation_bearing"
        ]
        if len(selected) != 1:
            raise AnswerContextSelectionError(
                "answer_context_interpretation_representation_count_invalid"
            )
        for representation in representations:
            role = representation.get("interpretation_selection_role")
            if role not in {"interpretation_bearing", "provenance_only"}:
                raise AnswerContextSelectionError(
                    "answer_context_representation_role_invalid"
                )
            if role == "provenance_only" and "content" in representation:
                raise AnswerContextSelectionError(
                    "answer_context_provenance_content_forbidden"
                )
        semantic = [
            item
            for item in representations
            if item.get("representation_kind") == "semantic_visual_logical_table"
        ]
        if semantic and semantic != selected:
            raise AnswerContextSelectionError(
                "answer_context_semantic_representation_not_selected"
            )
    guard = _object(payload.get("knowledge_vector_guard"))
    if any(value is not False for value in guard.values()):
        raise AnswerContextSelectionError("answer_context_knowledge_guard_failed")
    if _contains_forbidden_content(payload):
        raise AnswerContextSelectionError("answer_context_forbidden_content")


def _compact_fact(fact: dict[str, Any]) -> dict[str, Any]:
    source_location = _object(fact.get("source_location"))
    normalized = _object(fact.get("normalized_values"))
    return {
        "fact_id": fact.get("fact_id"),
        "fact_type": fact.get("fact_type"),
        "fact_subtype": fact.get("fact_subtype"),
        "label": normalized.get("label"),
        "amount": normalized.get("amount"),
        "currency": normalized.get("currency"),
        "quantity": normalized.get("quantity"),
        "rate": normalized.get("rate"),
        "date_or_period": normalized.get("date"),
        "identifier": normalized.get("identifier"),
        "source_reference": {
            "page_ref": source_location.get("page_ref"),
            "section_ref": source_location.get("section_ref"),
            "table_ref": source_location.get("table_ref"),
            "row_ref": source_location.get("row_ref"),
        },
    }


def _provenance_representation(
    *,
    representation_id: str,
    kind: str,
    artifact_refs: list[str],
    derived_from: list[str],
) -> dict[str, Any]:
    return {
        "representation_id": representation_id,
        "representation_kind": kind,
        "interpretation_selection_role": "provenance_only",
        "artifact_refs": sorted(set(artifact_refs)),
        "derived_from_artifact_refs": sorted(set(derived_from)),
        "content_presented_to_answer_model": False,
    }


def _provenance_artifact_refs(payload: dict[str, Any]) -> list[str]:
    return sorted(
        {
            ref
            for group in _dicts(payload.get("evidence_groups"))
            for representation in _dicts(group.get("representations"))
            if representation.get("interpretation_selection_role") == "provenance_only"
            for ref in _strings(representation.get("artifact_refs"))
        }
    )


def _contains_forbidden_content(value: Any) -> bool:
    forbidden = {
        "pdf_bytes",
        "file_bytes",
        "crop_bytes",
        "image_bytes",
        "raw_provider_response",
        "sealed_reference",
        "expected_value",
        "knowledge_context",
        "rag_context",
        "embedding",
    }
    if isinstance(value, dict):
        return any(
            str(key).lower() in forbidden or _contains_forbidden_content(child)
            for key, child in value.items()
        )
    if isinstance(value, list):
        return any(_contains_forbidden_content(item) for item in value)
    return False


def _integrity_hash(payload: dict[str, Any]) -> str:
    material = copy.deepcopy(payload)
    material.pop("integrity_hash", None)
    return hashlib.sha256(
        json.dumps(
            material,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _dicts(value: Any) -> list[dict[str, Any]]:
    return (
        [item for item in value or [] if isinstance(item, dict)]
        if isinstance(value, list)
        else []
    )


def _strings(value: Any) -> list[str]:
    return (
        [str(item) for item in value or [] if item is not None and str(item)]
        if isinstance(value, list)
        else []
    )
