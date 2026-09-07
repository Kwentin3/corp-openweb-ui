"""Focused public contract checks for the private Goal #391 R&D helper."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from broker_reports_gate1.goal391_private_corpus_export import (
    PrivateCorpusSelection,
    PrivateCorpusSelectionManifest,
)
from broker_reports_gate1.goal391_source_comparison_export import (
    Goal391SourceComparisonMappingScope,
    Goal391SourceComparisonExportCoordinator,
    Goal391SourceComparisonExportError,
)
from broker_reports_gate1.contracts import stable_digest


def test_read_only_export_joins_only_exact_source_bound_owner_outputs() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        private_root = root / "_private_test_corpora"
        private_root.mkdir(mode=0o700)
        source = b"synthetic owned PDF bytes"
        checksum = hashlib.sha256(source).hexdigest()
        selection = _selection()
        resolver = _Resolver(checksum)
        mapping_owner = _MappingPackageOwner()
        with patch(
            "broker_reports_gate1.goal391_source_comparison_export.validate_full_source_unit",
            return_value={"passed": True},
        ) as validated:
            receipt = asyncio.run(
                Goal391SourceComparisonExportCoordinator(
                    reader=_Reader(checksum),
                    artifact_resolver=resolver,
                    file_bytes_resolver=_OwnedFileResolver(source, checksum),
                    mapping_package_builder=mapping_owner,
                    private_corpus_root=private_root,
                ).export(selection=selection, mapping_scopes=_mapping_scopes())
            )

        target = private_root / "corpus-source-comparison"
        assert receipt["status"] == "EXPORTED"
        assert receipt["contains_private_payload"] is False
        assert receipt["entries"][0]["original_sha256"] == checksum
        assert "synthetic owned PDF bytes" not in json.dumps(receipt)
        assert (target / "canonical" / "slot-1.json").is_file()
        assert (target / "original" / "slot-1.pdf").read_bytes() == source
        assert (target / "full-source" / "slot-1.json").is_file()
        assert (target / "mapping-package" / "slot-1.json").is_file()
        assert mapping_owner.calls == [("table-1",)]
        assert validated.call_count == 1
        if os.name != "nt":
            assert (target.stat().st_mode & 0o077) == 0


def test_mismatched_native_source_hash_stops_before_lab_directory_exists() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        private_root = root / "_private_test_corpora"
        private_root.mkdir(mode=0o700)
        selection = _selection()
        source = b"synthetic owned PDF bytes"
        canonical_checksum = hashlib.sha256(b"different").hexdigest()
        with pytest.raises(Goal391SourceComparisonExportError) as mismatch:
            asyncio.run(
                Goal391SourceComparisonExportCoordinator(
                    reader=_Reader(canonical_checksum),
                    artifact_resolver=_Resolver(canonical_checksum),
                    file_bytes_resolver=_OwnedFileResolver(source, hashlib.sha256(source).hexdigest()),
                    mapping_package_builder=_MappingPackageOwner(),
                    private_corpus_root=private_root,
                ).export(selection=selection, mapping_scopes=_mapping_scopes())
            )
        assert mismatch.value.code == "goal391_source_comparison_original_binding_invalid"
        assert list(private_root.iterdir()) == []


def test_deleted_source_is_rejected_before_private_export() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        private_root = Path(temp_dir) / "_private_test_corpora"
        private_root.mkdir(mode=0o700)
        source = b"synthetic owned PDF bytes"
        checksum = hashlib.sha256(source).hexdigest()
        with pytest.raises(Goal391SourceComparisonExportError) as deleted:
            asyncio.run(
                Goal391SourceComparisonExportCoordinator(
                    reader=_Reader(checksum),
                    artifact_resolver=_Resolver(checksum, source_deleted=True),
                    file_bytes_resolver=_OwnedFileResolver(source, checksum),
                    mapping_package_builder=_MappingPackageOwner(),
                    private_corpus_root=private_root,
                ).export(selection=_selection(), mapping_scopes=_mapping_scopes())
            )
        assert deleted.value.code == "goal391_source_comparison_source_record_invalid"
        assert list(private_root.iterdir()) == []


def test_constructed_traversal_selection_stops_before_source_read_or_export() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        private_root = root / "_private_test_corpora"
        private_root.mkdir(mode=0o700)
        source = b"synthetic owned PDF bytes"
        checksum = hashlib.sha256(source).hexdigest()
        reader = _Reader(checksum)
        selection = PrivateCorpusSelectionManifest(
            corpus_id="../escape",
            selections=(
                PrivateCorpusSelection(
                    slot_id="../slot",
                    manifest_ref="manifest-1",
                    user_id="user-1",
                    normalization_run_id="run-1",
                    case_id="case-1",
                    chat_id=None,
                    workspace_model_id="workspace-1",
                ),
            ),
        )
        with pytest.raises(Goal391SourceComparisonExportError) as rejected:
            asyncio.run(
                Goal391SourceComparisonExportCoordinator(
                    reader=reader,
                    artifact_resolver=_Resolver(checksum),
                    file_bytes_resolver=_OwnedFileResolver(source, checksum),
                    mapping_package_builder=_MappingPackageOwner(),
                    private_corpus_root=private_root,
                ).export(
                    selection=selection,
                    mapping_scopes=(
                        Goal391SourceComparisonMappingScope(
                            slot_id="../slot", target_table_node_ids=("table-1",)
                        ),
                    ),
                )
            )
        assert rejected.value.code == "goal391_source_comparison_selection_invalid"
        assert reader.calls == 0
        assert list(private_root.iterdir()) == []
        assert not (root / "escape-source-comparison").exists()


def test_mismatched_full_source_payload_binding_stops_before_private_export() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        private_root = Path(temp_dir) / "_private_test_corpora"
        private_root.mkdir(mode=0o700)
        source = b"synthetic owned PDF bytes"
        checksum = hashlib.sha256(source).hexdigest()
        resolver = _Resolver(
            checksum, unit_payload_checksum_ref="different-payload-checksum"
        )
        with patch(
            "broker_reports_gate1.goal391_source_comparison_export.validate_full_source_unit",
            return_value={"passed": True},
        ):
            with pytest.raises(Goal391SourceComparisonExportError) as invalid:
                asyncio.run(
                    Goal391SourceComparisonExportCoordinator(
                        reader=_Reader(checksum),
                        artifact_resolver=resolver,
                        file_bytes_resolver=_OwnedFileResolver(source, checksum),
                        mapping_package_builder=_MappingPackageOwner(),
                        private_corpus_root=private_root,
                    ).export(selection=_selection(), mapping_scopes=_mapping_scopes())
                )
        assert invalid.value.code == "goal391_source_comparison_full_source_binding_invalid"
        assert list(private_root.iterdir()) == []


def _selection() -> PrivateCorpusSelectionManifest:
    return PrivateCorpusSelectionManifest(
        corpus_id="corpus",
        selections=(
            PrivateCorpusSelection(
                slot_id="slot-1",
                manifest_ref="manifest-1",
                user_id="user-1",
                normalization_run_id="run-1",
                case_id="case-1",
                chat_id=None,
                workspace_model_id="workspace-1",
            ),
        ),
    )


def _mapping_scopes() -> tuple[Goal391SourceComparisonMappingScope, ...]:
    return (
        Goal391SourceComparisonMappingScope(
            slot_id="slot-1", target_table_node_ids=("table-1",)
        ),
    )


class _Reader:
    def __init__(self, checksum: str) -> None:
        self.checksum = checksum
        self.calls = 0

    def read_envelope(self, manifest_ref, context, *, expected_normalization_run_id):
        self.calls += 1
        assert manifest_ref == "manifest-1"
        assert expected_normalization_run_id == "run-1"
        assert context.require_source_available is True
        return SimpleNamespace(
            document_id="document-1",
            artifact={
                "tenant_id": "user-1",
                "source": {
                    "source_artifact_ref": "source-artifact-1",
                    "source_sha256": self.checksum,
                },
            },
        )


class _Resolver:
    def __init__(
        self,
        checksum: str,
        *,
        source_deleted: bool = False,
        unit_payload_checksum_ref: str | None = None,
    ) -> None:
        self.checksum = checksum
        self.payload_checksum_ref = "payload-checksum-1"
        self.unit_payload_checksum_ref = (
            unit_payload_checksum_ref or self.payload_checksum_ref
        )
        self.source_ref = {
            "openwebui_file_id": "file-1",
            "file_hash_sha256": checksum,
            "source_deleted": source_deleted,
        }
        self.records = {
            "source-artifact-1": SimpleNamespace(
                artifact_id="source-artifact-1",
                artifact_type="source_file_ref_v0",
                document_id="document-1",
                source_file_ref=self.source_ref,
            ),
            "payload-1": SimpleNamespace(
                artifact_id="payload-1",
                artifact_type="private_normalized_source_payload_v0",
                document_id="document-1",
                source_file_ref=self.source_ref,
            ),
            "unit-1": SimpleNamespace(
                artifact_id="unit-1",
                artifact_type="private_normalized_source_unit_v0",
                document_id="document-1",
                source_file_ref=self.source_ref,
            ),
        }

    def catalog_run(self, context):
        assert context.normalization_run_id == "run-1"
        assert context.require_source_available is True
        return list(self.records.values())[1:]

    def resolve(self, artifact_id, context):
        record = self.records[artifact_id]
        payload = (
            self.source_ref
            if artifact_id == "source-artifact-1"
            else {
                "schema_version": "private_normalized_source_payload_v0",
                "document_ref": "document-1",
                "normalization_run_id": "run-1",
                "source_payload_ref": "payload-ref-1",
                "payload_checksum_ref": self.payload_checksum_ref,
                "source_checksum_ref": f"srcsum_{stable_digest(['document-1', self.checksum], length=24)}",
                "parser_completeness_status": "complete",
                "normalized_projection_status": "materialized",
                "visibility": "private_case",
                "knowledge_rag_used": False,
                "vectorization_performed": False,
            }
            if artifact_id == "payload-1"
            else {
                "parent_payload_ref": "payload-ref-1",
                "payload_checksum_ref": self.unit_payload_checksum_ref,
                "unit_ref": "unit-ref-1",
            }
        )
        return {"record": record, "payload": payload}


class _OwnedFileResolver:
    def __init__(self, payload: bytes, checksum: str) -> None:
        self.payload = payload
        self.checksum = checksum

    async def resolve(self, *, file_id: str, actor_user_id: str):
        assert file_id == "file-1"
        assert actor_user_id == "user-1"
        return SimpleNamespace(
            file_id=file_id,
            user_id=actor_user_id,
            content_type="application/pdf",
            payload=self.payload,
            sha256=self.checksum,
        )


class _MappingPackageOwner:
    """Explicit projection boundary: semantics stay outside the coordinator."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []

    def build_mapping_package(
        self, *, canonical, confirmed_understandings, target_table_node_ids
    ):
        assert canonical["tenant_id"] == "user-1"
        assert confirmed_understandings == []
        table_ids = tuple(target_table_node_ids)
        self.calls.append(table_ids)
        return {"phase": "map", "case": {"tables": [{"table_ref": "table_1"}]}}
