"""Seal confirmed user input into the one immutable final Canonical version."""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import replace
from typing import Any

from .artifact_models import ArtifactAccessContext, RetentionPolicy
from .canonical_artifact import (
    CANONICAL_FINALIZATION_SCHEMA_VERSION,
    CANONICAL_USER_ASSERTION_SCHEMA_VERSION,
    _root_hash_material,
)
from .canonical_store import CanonicalArtifactStoreFactory, CanonicalReaderFactory
from .ordinary_trade_mapping_case import OrdinaryTradeMappingCaseFactory


CANONICAL_FINALIZATION_ROUTE_ID = "canonical_user_finalization_v1"
FACTORY_REQUIRED = (
    "CanonicalFinalizationFactory.create is the only owner that seals "
    "confirmed user input into a final Canonical version"
)


class CanonicalFinalizationError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class CanonicalFinalizationFactory:
    def __init__(self, *, store: Any, read_enabled: bool) -> None:
        self._store = store
        self._read_enabled = read_enabled

    def create(self) -> "CanonicalFinalizationRuntime":
        return CanonicalFinalizationRuntime(
            store=self._store, read_enabled=self._read_enabled
        )


class CanonicalFinalizationRuntime:
    def __init__(self, *, store: Any, read_enabled: bool) -> None:
        self._store = store
        self._reader = CanonicalReaderFactory(
            store=store, read_enabled=read_enabled
        ).create()
        self._cases = OrdinaryTradeMappingCaseFactory(
            store=store, read_enabled=read_enabled
        ).create()
        self._writer = CanonicalArtifactStoreFactory(store=store).create()

    def finalize(
        self,
        *,
        document_id: str,
        context: ArtifactAccessContext,
        retention_policy: RetentionPolicy,
    ) -> dict[str, str]:
        """Create and activate exactly one derived Canonical after confirmation.

        The original Canonical remains immutable and traceable.  The derived
        version carries only confirmed choices, labelled as user input, and is
        published by the same CanonicalArtifactStore with a CAS activation.
        """

        active = self._reader.read_active_envelope(document_id, context)
        existing = active.artifact.get("finalization")
        if isinstance(existing, dict):
            return {
                "artifact_ref": self._manifest_ref(active, context),
                "canonical_version_id": active.canonical_version_id,
                "canonical_root_sha256": active.canonical_root_sha256,
            }
        current = self._cases.current(document_id=document_id, context=context)
        if current is None or current[1].get("status") != "COMPLETE":
            raise CanonicalFinalizationError("canonical_finalization_mapping_incomplete")
        case_record, case_payload = current
        binding = (case_payload.get("case_binding") or {}).get("canonical_binding")
        if (
            not isinstance(binding, dict)
            or binding.get("canonical_version_id") != active.canonical_version_id
            or binding.get("canonical_root_sha256") != active.canonical_root_sha256
        ):
            raise CanonicalFinalizationError("canonical_finalization_binding_stale")
        assertions = _assertions(
            confirmed=case_payload.get("confirmed_understandings"),
            mapping_case_artifact_ref=case_record.artifact_id,
            mapping_case_sha256=_sha256(case_payload),
        )
        if not assertions:
            # No extra fact was requested from the user: the already immutable
            # source Canonical is the final Canonical for this document.
            return {
                "artifact_ref": self._manifest_ref(active, context),
                "canonical_version_id": active.canonical_version_id,
                "canonical_root_sha256": active.canonical_root_sha256,
            }
        artifact = copy.deepcopy(active.artifact)
        artifact["user_assertions"] = assertions
        artifact["finalization"] = {
            "schema_version": CANONICAL_FINALIZATION_SCHEMA_VERSION,
            "base_canonical_version_id": active.canonical_version_id,
            "base_canonical_root_sha256": active.canonical_root_sha256,
            "mapping_case_artifact_ref": case_record.artifact_id,
            "mapping_case_sha256": _sha256(case_payload),
        }
        artifact["canonical_root_hash"] = _sha256(
            _root_hash_material(
                normalizer_version=str(artifact.get("normalizer_version") or ""),
                source_format=str((artifact.get("source") or {}).get("source_format") or ""),
                source_sha256=str((artifact.get("source") or {}).get("source_sha256") or ""),
                containers=artifact.get("containers") or [],
                nodes=artifact.get("nodes") or [],
                provenance=artifact.get("provenance") or [],
                issues=artifact.get("issues") or [],
                user_assertions=assertions,
                finalization=artifact["finalization"],
            )
        )
        final_context = replace(
            context,
            normalization_run_id="canonical_finalization_"
            + _sha256(
                {
                    "base_canonical_version_id": active.canonical_version_id,
                    "mapping_case_artifact_ref": case_record.artifact_id,
                    "mapping_case_sha256": _sha256(case_payload),
                }
            )[:40],
        )
        persisted = self._writer.put_candidate(
            artifact=artifact,
            context=final_context,
            source_context=context,
            retention_policy=retention_policy,
            compare_receipt=None,
        )
        self._reader.activate(
            canonical_version_id=persisted.canonical_version_id,
            expected_previous_version_id=active.canonical_version_id,
            context=final_context,
            actor=CANONICAL_FINALIZATION_ROUTE_ID,
            reason="confirmed_user_input_finalized",
        )
        return {
            "artifact_ref": persisted.artifact_ref,
            "canonical_version_id": persisted.canonical_version_id,
            "canonical_root_sha256": artifact["canonical_root_hash"],
        }

    def _manifest_ref(self, envelope: Any, context: ArtifactAccessContext) -> str:
        versions = self._reader.history(envelope.document_id, context)
        version = next(
            (item for item in versions if item.canonical_version_id == envelope.canonical_version_id),
            None,
        )
        if version is None or not version.manifest_ref:
            raise CanonicalFinalizationError("canonical_finalization_manifest_missing")
        return version.manifest_ref


def _assertions(
    *,
    confirmed: Any,
    mapping_case_artifact_ref: str,
    mapping_case_sha256: str,
) -> list[dict[str, Any]]:
    if not isinstance(confirmed, list):
        raise CanonicalFinalizationError("canonical_finalization_confirmations_invalid")
    result = []
    for item in confirmed:
        if not isinstance(item, dict):
            raise CanonicalFinalizationError("canonical_finalization_confirmations_invalid")
        material = {
            "question_id": item.get("question_id"),
            "option_id": item.get("option_id"),
            "label_sha256": item.get("label_sha256"),
            "decision_sha256": item.get("decision_sha256"),
            "mapping_case_artifact_ref": mapping_case_artifact_ref,
            "mapping_case_sha256": mapping_case_sha256,
        }
        if not all(isinstance(value, str) and value for value in material.values()):
            raise CanonicalFinalizationError("canonical_finalization_confirmations_invalid")
        decision = copy.deepcopy(item["decision"])
        kind = (
            "user_provided_currency"
            if decision.get("decision_kind") == "USER_PROVIDED_CURRENCY"
            else "mapping_decision"
        )
        result.append(
            {
                "schema_version": CANONICAL_USER_ASSERTION_SCHEMA_VERSION,
                "assertion_id": "usrassert_" + _sha256(material)[:32],
                "kind": kind,
                "question_id": item["question_id"],
                "option_id": item["option_id"],
                "label": item["label"],
                "label_sha256": item["label_sha256"],
                "decision": decision,
                "decision_sha256": item["decision_sha256"],
                "mapping_case_artifact_ref": mapping_case_artifact_ref,
                "mapping_case_sha256": mapping_case_sha256,
                "provenance_kind": "user_confirmed",
            }
        )
    return sorted(result, key=lambda item: item["assertion_id"])


def _sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
