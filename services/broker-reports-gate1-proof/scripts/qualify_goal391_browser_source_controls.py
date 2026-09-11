"""Build one private Goal #391 R&D pack from two browser-selected source files.

This is a server-local laboratory command, not an OpenWebUI product route.  A
control is named by a chat id and an OpenWebUI file id that were visible to the
authenticated user.  The OpenWebUI chat owner supplies the user identity;
ArtifactResolver then proves the exact file/run/document binding before the
existing private source-comparison exporter reads anything.

The command performs no provider call and writes only below an existing
private ``_private_test_corpora`` root.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import dataclass
from pathlib import Path

from broker_reports_gate1.artifact_models import ArtifactAccessContext
from broker_reports_gate1.artifact_resolver import ArtifactResolver
from broker_reports_gate1.artifact_store import ArtifactStoreConfig, ArtifactStoreFactory
from broker_reports_gate1.canonical_store import CanonicalReaderFactory
from broker_reports_gate1.gate3_ndfl_workflow import NDFL_WORKSPACE_MODEL_STABLE_ID
from broker_reports_gate1.goal391_private_selection_binding import (
    Goal391PrivateSelectionBindingIssuer,
    Goal391PrivateSourceFileSelectionRequest,
)
from broker_reports_gate1.goal391_source_comparison_export import (
    Goal391SourceComparisonExportCoordinator,
    Goal391SourceComparisonExportError,
    Goal391SourceComparisonMappingScope,
)
from broker_reports_gate1.openwebui_file_bytes import OpenWebUIFileBytesResolverFactory
from broker_reports_gate1.ordinary_trade_semantic_mapping import (
    OrdinaryTradeSemanticMappingError,
    OrdinaryTradeSemanticMappingFactory,
)
from open_webui.models.chats import Chats


@dataclass(frozen=True)
class BrowserSourceControl:
    slot_id: str
    chat_id: str
    openwebui_file_id: str


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--control",
        action="append",
        required=True,
        help="slot_id:chat_id:openwebui_file_id; exactly two distinct controls",
    )
    parser.add_argument("--corpus-id", required=True)
    parser.add_argument("--private-corpus-root", type=Path, required=True)
    parser.add_argument("--sqlite-path", type=Path, required=True)
    parser.add_argument("--payload-root", type=Path, required=True)
    parser.add_argument(
        "--plan-only",
        action="store_true",
        help="measure safe mapping-package capacity without exporting source data",
    )
    args = parser.parse_args()

    controls = _parse_controls(args.control)
    result = asyncio.run(
        _run(
            controls=controls,
            corpus_id=args.corpus_id,
            private_corpus_root=args.private_corpus_root,
            sqlite_path=args.sqlite_path,
            payload_root=args.payload_root,
            plan_only=args.plan_only,
        )
    )
    print(json.dumps(result, sort_keys=True))
    return 0


async def _run(
    *,
    controls: tuple[BrowserSourceControl, ...],
    corpus_id: str,
    private_corpus_root: Path,
    sqlite_path: Path,
    payload_root: Path,
    plan_only: bool,
) -> dict:
    store = ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite", sqlite_path=sqlite_path, payload_root=payload_root
        )
    ).create_read_only()
    reader = CanonicalReaderFactory(store=store, read_enabled=True).create()
    resolver = ArtifactResolver(store)
    requests = []
    for control in controls:
        requests.append(
            Goal391PrivateSourceFileSelectionRequest(
                slot_id=control.slot_id,
                openwebui_file_id=control.openwebui_file_id,
                context=ArtifactAccessContext(
                    user_id=await _chat_owner_id(control.chat_id),
                    normalization_run_id="browser-source-selection",
                    # The native NDFL Pipe promotes its server-attested chat
                    # id to the bounded case id when no separate case exists.
                    case_id=control.chat_id,
                    chat_id=control.chat_id,
                    workspace_model_id=NDFL_WORKSPACE_MODEL_STABLE_ID,
                    allow_private=True,
                ),
            )
        )
    selection = Goal391PrivateSelectionBindingIssuer(
        store=store, reader=reader, resolver=resolver
    ).issue_from_source_files(
        corpus_id=corpus_id,
        requests=tuple(requests),
    )
    scopes = tuple(
        Goal391SourceComparisonMappingScope(
            slot_id=item.slot_id,
            target_table_node_ids=_all_table_node_ids(item=item, reader=reader),
        )
        for item in selection.selections
    )
    mapping_builder = OrdinaryTradeSemanticMappingFactory.create()
    if plan_only:
        return _safe_capacity_plan(
            selection=selection,
            scopes=scopes,
            reader=reader,
            mapping_package_builder=mapping_builder,
        )
    receipt = await Goal391SourceComparisonExportCoordinator(
        reader=reader,
        artifact_resolver=resolver,
        file_bytes_resolver=OpenWebUIFileBytesResolverFactory.create(),
        mapping_package_builder=mapping_builder,
        private_corpus_root=private_corpus_root,
    ).export(selection=selection, mapping_scopes=scopes)
    return {
        "status": receipt["status"],
        "selection_count": receipt["selection_count"],
        "mapping_tables_total": sum(
            int(item["mapping_tables_total"]) for item in receipt["entries"]
        ),
        "full_source_units_total": sum(
            int(item["full_source_units_total"]) for item in receipt["entries"]
        ),
    }


def _parse_controls(raw_controls: list[str]) -> tuple[BrowserSourceControl, ...]:
    if len(raw_controls) != 2:
        raise SystemExit("goal391_browser_source_controls_exactly_two_required")
    controls = []
    for raw in raw_controls:
        values = str(raw or "").split(":")
        if len(values) != 3 or any(not value.strip() for value in values):
            raise SystemExit("goal391_browser_source_control_invalid")
        controls.append(BrowserSourceControl(*values))
    if (
        len({item.slot_id for item in controls}) != 2
        or len({item.chat_id for item in controls}) != 2
        or len({item.openwebui_file_id for item in controls}) != 2
    ):
        raise SystemExit("goal391_browser_source_control_duplicate")
    return tuple(controls)


async def _chat_owner_id(chat_id: str) -> str:
    chat = await Chats.get_chat_by_id(chat_id)
    user_id = str(getattr(chat, "user_id", "") or "").strip()
    if not user_id:
        raise Goal391SourceComparisonExportError(
            "goal391_browser_source_control_chat_not_found"
        )
    return user_id


def _all_table_node_ids(*, item, reader) -> tuple[str, ...]:
    envelope = reader.read_envelope(
        item.manifest_ref,
        item.access_context(require_source_available=True),
        expected_normalization_run_id=item.normalization_run_id,
    )
    artifact = getattr(envelope, "artifact", None)
    table_node_ids = tuple(
        str(node.get("node_id"))
        for node in (artifact.get("nodes") if isinstance(artifact, dict) else []) or []
        if isinstance(node, dict)
        and node.get("node_type") == "TABLE"
        and str(node.get("node_id") or "")
    )
    if not table_node_ids:
        raise Goal391SourceComparisonExportError(
            "goal391_browser_source_control_tables_missing"
        )
    return table_node_ids


def _safe_capacity_plan(
    *,
    selection,
    scopes: tuple[Goal391SourceComparisonMappingScope, ...],
    reader,
    mapping_package_builder,
) -> dict:
    by_slot = {scope.slot_id: scope for scope in scopes}
    controls = []
    for item in selection.selections:
        scope = by_slot[item.slot_id]
        whole_document_fits = _mapping_package_fits(
            mapping_package_builder=mapping_package_builder,
            item=item,
            reader=reader,
            table_node_ids=scope.target_table_node_ids,
        )
        singleton_fits = sum(
            _mapping_package_fits(
                mapping_package_builder=mapping_package_builder,
                item=item,
                reader=reader,
                table_node_ids=(node_id,),
            )
            for node_id in scope.target_table_node_ids
        )
        controls.append(
            {
                "table_count": len(scope.target_table_node_ids),
                "whole_document_fits": whole_document_fits,
                "singleton_tables_fit": singleton_fits,
                "singleton_tables_overflow": len(scope.target_table_node_ids)
                - singleton_fits,
            }
        )
    return {
        "status": "capacity_plan_ready",
        "selection_count": len(selection.selections),
        "controls": controls,
    }


def _mapping_package_fits(
    *,
    mapping_package_builder,
    item,
    reader,
    table_node_ids: tuple[str, ...],
) -> bool:
    envelope = reader.read_envelope(
        item.manifest_ref,
        item.access_context(require_source_available=True),
        expected_normalization_run_id=item.normalization_run_id,
    )
    try:
        mapping_package_builder.build_mapping_package(
            canonical=envelope.artifact,
            confirmed_understandings=[],
            target_table_node_ids=table_node_ids,
        )
    except OrdinaryTradeSemanticMappingError:
        return False
    return True


if __name__ == "__main__":
    raise SystemExit(main())
