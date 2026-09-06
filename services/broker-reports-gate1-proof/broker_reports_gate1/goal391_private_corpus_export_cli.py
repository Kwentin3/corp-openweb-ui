"""Executable, read-only composition for the Goal #391 private corpus lab."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from .artifact_models import ArtifactStoreError
from .artifact_store import ArtifactStoreConfig, ArtifactStoreFactory
from .canonical_store import CanonicalReaderFactory
from .goal391_private_corpus_export import (
    Goal391PrivateCorpusExportCoordinator,
    Goal391PrivateCorpusExportError,
    load_private_corpus_selection,
)


def export_private_corpus(
    *,
    artifact_store_sqlite_path: str | Path,
    artifact_payload_root: str | Path,
    selection_manifest: str | Path,
    private_corpus_root: str | Path,
) -> dict[str, object]:
    """Run the sole local R&D export composition; no discovery is available."""

    selection = load_private_corpus_selection(selection_manifest)
    store = ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=Path(artifact_store_sqlite_path),
            payload_root=Path(artifact_payload_root),
        )
    ).create_read_only()
    reader = CanonicalReaderFactory(store=store, read_enabled=True).create()
    return Goal391PrivateCorpusExportCoordinator(
        reader=reader,
        private_corpus_root=private_corpus_root,
    ).export(selection=selection)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Export explicitly selected private Canonical artifacts for Goal #391 R&D."
    )
    parser.add_argument("--artifact-store-sqlite-path", required=True)
    parser.add_argument("--artifact-payload-root", required=True)
    parser.add_argument("--selection-manifest", required=True)
    parser.add_argument("--private-corpus-root", required=True)
    arguments = parser.parse_args(argv)
    try:
        receipt = export_private_corpus(
            artifact_store_sqlite_path=arguments.artifact_store_sqlite_path,
            artifact_payload_root=arguments.artifact_payload_root,
            selection_manifest=arguments.selection_manifest,
            private_corpus_root=arguments.private_corpus_root,
        )
    except (ArtifactStoreError, Goal391PrivateCorpusExportError) as exc:
        print(getattr(exc, "code", "goal391_private_corpus_export_failed"), file=sys.stderr)
        return 2
    print(json.dumps(receipt, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover - module entrypoint
    raise SystemExit(main())
