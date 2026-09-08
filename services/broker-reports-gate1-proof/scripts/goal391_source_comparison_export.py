"""Run the private, read-only Goal #391 source-comparison export on one selection."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from broker_reports_gate1.artifact_resolver import ArtifactResolver
from broker_reports_gate1.artifact_store import ArtifactStoreConfig, ArtifactStoreFactory
from broker_reports_gate1.canonical_store import CanonicalReaderFactory
from broker_reports_gate1.goal391_private_corpus_export import (
    load_private_corpus_selection,
)
from broker_reports_gate1.goal391_source_comparison_export import (
    Goal391SourceComparisonMappingScope,
    Goal391SourceComparisonExportCoordinator,
)
from broker_reports_gate1.openwebui_file_bytes import (
    OpenWebUIFileBytesResolverFactory,
)
from broker_reports_gate1.ordinary_trade_semantic_mapping import (
    OrdinaryTradeSemanticMappingFactory,
)


MAPPING_SCOPES_SCHEMA_VERSION = "goal391_source_comparison_mapping_scopes_v1"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--private-corpus-root", type=Path, required=True)
    parser.add_argument("--sqlite-path", type=Path, required=True)
    parser.add_argument("--payload-root", type=Path, required=True)
    parser.add_argument("--mapping-scopes", type=Path, required=True)
    args = parser.parse_args()

    selection = load_private_corpus_selection(args.selection)
    store = ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=args.sqlite_path,
            payload_root=args.payload_root,
        )
    ).create_read_only()
    receipt = asyncio.run(
        Goal391SourceComparisonExportCoordinator(
            reader=CanonicalReaderFactory(store=store, read_enabled=True).create(),
            artifact_resolver=ArtifactResolver(store),
            file_bytes_resolver=OpenWebUIFileBytesResolverFactory.create(),
            mapping_package_builder=OrdinaryTradeSemanticMappingFactory.create(),
            private_corpus_root=args.private_corpus_root,
        ).export(
            selection=selection,
            mapping_scopes=_load_mapping_scopes(args.mapping_scopes),
        )
    )
    print(
        json.dumps(
            {
                "status": receipt["status"],
                "selection_count": receipt["selection_count"],
                "full_source_payloads_total": sum(
                    int(item["full_source_payloads_total"])
                    for item in receipt["entries"]
                ),
                "full_source_units_total": sum(
                    int(item["full_source_units_total"])
                    for item in receipt["entries"]
                ),
            },
            sort_keys=True,
        )
    )
    return 0


def _load_mapping_scopes(path: Path) -> tuple[Goal391SourceComparisonMappingScope, ...]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit("goal391_mapping_scopes_unreadable") from exc
    if (
        not isinstance(value, dict)
        or set(value) != {"schema_version", "scopes"}
        or value.get("schema_version") != MAPPING_SCOPES_SCHEMA_VERSION
        or not isinstance(value.get("scopes"), list)
        or not value["scopes"]
    ):
        raise SystemExit("goal391_mapping_scopes_invalid")
    scopes = []
    for item in value["scopes"]:
        if (
            not isinstance(item, dict)
            or set(item)
            != {"slot_id", "target_table_node_ids", "confirmed_understandings"}
            or not isinstance(item.get("slot_id"), str)
            or not item["slot_id"]
            or not isinstance(item.get("target_table_node_ids"), list)
            or not item["target_table_node_ids"]
            or any(
                not isinstance(node_id, str) or not node_id
                for node_id in item["target_table_node_ids"]
            )
            or len(item["target_table_node_ids"])
            != len(set(item["target_table_node_ids"]))
            or not isinstance(item.get("confirmed_understandings"), list)
            or any(
                not isinstance(understanding, dict)
                for understanding in item["confirmed_understandings"]
            )
        ):
            raise SystemExit("goal391_mapping_scopes_invalid")
        scopes.append(
            Goal391SourceComparisonMappingScope(
                slot_id=item["slot_id"],
                target_table_node_ids=tuple(item["target_table_node_ids"]),
                confirmed_understandings=tuple(item["confirmed_understandings"]),
            )
        )
    if len({item.slot_id for item in scopes}) != len(scopes):
        raise SystemExit("goal391_mapping_scopes_invalid")
    return tuple(scopes)


if __name__ == "__main__":
    raise SystemExit(main())
