#!/usr/bin/env python3
"""Read-only DOC33 proof over the retained 16-document canonical cohort.

The proof combines the eight non-PDF active versions from the isolated DOC29
restore with the eight corrected PDF active versions from the DOC32 isolated
store. Private state supplies only authenticated lookup context; stdout contains
aggregate counts and never document identity or content.
"""

from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

SERVICE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_ROOT))

import doc29_durable_contour as doc29  # noqa: E402
import doc32_pdf_roundtrip_repair as doc32  # noqa: E402
from broker_reports_gate1 import (  # noqa: E402
    CanonicalReaderFactory,
    assess_canonical_completeness,
    render_neutral_canonical_projection,
)
from broker_reports_gate1.canonical_consumer_migration import (  # noqa: E402
    _neutral_container_marker,
    _neutral_table_rows,
)


SCHEMA_VERSION = "broker_reports_doc33_unified_projection_proof_v1"
EXPECTED_FORMATS = {"pdf": 8, "html": 4, "csv": 2, "xlsx": 2}
FACTORY_REQUIRED = "DOC33 cohort reads enter only through CanonicalReaderFactory.create"
FORBIDDEN = (
    "Product writes, activation, fallback, provider calls, source bytes and "
    "private evidence are forbidden"
)


def prove(*, doc29_root: Path, doc32_root: Path) -> dict[str, Any]:
    observations: list[dict[str, Any]] = []

    doc29_state = doc29._load_state(doc29_root)
    doc29_store = doc29._store(doc29_root)
    doc29_reader = CanonicalReaderFactory(store=doc29_store, read_enabled=True).create()
    doc29_context = doc29._context(str(doc29_state["run_id"]))
    for item in doc29_state["documents"]:
        expected_format = str((item.get("expected") or {}).get("source_format") or "")
        if expected_format == "pdf":
            continue
        if expected_format == "html_text":
            expected_format = "html"
        envelope = doc29_reader.read_active_envelope(
            str(item["document_id"]), doc29_context
        )
        observations.append(
            _observe(
                envelope,
                expected_format,
                reader_implementation=type(doc29_reader).__name__,
            )
        )

    doc32_documents, doc32_profile = doc32._state_documents(doc32_root, "isolated")
    doc32_store = doc32._store(doc32_root)
    doc32_reader = CanonicalReaderFactory(store=doc32_store, read_enabled=True).create()
    for item in doc32_documents:
        context = doc32._context(
            str(item["normalization_run_id"]), profile=doc32_profile
        )
        envelope = doc32_reader.read_active_envelope(str(item["document_id"]), context)
        observations.append(
            _observe(
                envelope,
                "pdf",
                reader_implementation=type(doc32_reader).__name__,
            )
        )

    formats = Counter(item["source_format"] for item in observations)
    layouts = Counter(item["physical_layout"] for item in observations)
    roots = Counter(item["root_container_type"] for item in observations)
    renderer_source = "\n".join(
        (
            inspect.getsource(render_neutral_canonical_projection),
            inspect.getsource(_neutral_container_marker),
            inspect.getsource(_neutral_table_rows),
        )
    )
    forbidden_renderer_tokens = (
        "source_format",
        "ArtifactStore",
        "ArtifactResolver",
        "raw_pdf",
        "provider_payload",
        "private_evidence",
    )
    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "status": "PASS",
        "documents_total": len(observations),
        "format_counts": dict(sorted(formats.items())),
        "canonical_schema_versions": sorted(
            {item["schema_version"] for item in observations}
        ),
        "reader_authority": "CanonicalReaderFactory.create",
        "reader_implementations": sorted(
            {item["reader_implementation"] for item in observations}
        ),
        "root_hashes_matched": sum(item["root_hash_matched"] for item in observations),
        "completeness_passed": sum(
            item["completeness_passed"] for item in observations
        ),
        "nonempty_neutral_projections": sum(
            item["neutral_projection_nonempty"] for item in observations
        ),
        "logical_containers_total": sum(
            item["containers_total"] for item in observations
        ),
        "logical_nodes_total": sum(item["nodes_total"] for item in observations),
        "logical_tables_total": sum(item["tables_total"] for item in observations),
        "physical_layout_counts": dict(sorted(layouts.items())),
        "root_container_type_counts": dict(sorted(roots.items())),
        "renderer_format_branches": sum(
            token == "source_format" and token in renderer_source
            for token in forbidden_renderer_tokens
        ),
        "renderer_forbidden_dependency_hits": sorted(
            token
            for token in forbidden_renderer_tokens
            if token != "source_format" and token in renderer_source
        ),
        "private_state_usage": "authenticated_lookup_only",
        "private_content_in_output": False,
        "provider_calls": 0,
        "product_writes": 0,
        "activation_changes": 0,
        "legacy_fallbacks": 0,
        "gate3_started": False,
    }
    passed = all(
        (
            len(observations) == 16,
            dict(formats) == EXPECTED_FORMATS,
            result["canonical_schema_versions"] == ["canonical_artifact_v1"],
            result["reader_implementations"] == ["CanonicalReader"],
            result["root_hashes_matched"] == 16,
            result["completeness_passed"] == 16,
            result["nonempty_neutral_projections"] == 16,
            result["renderer_format_branches"] == 0,
            result["renderer_forbidden_dependency_hits"] == [],
        )
    )
    result["status"] = "PASS" if passed else "FAILED"
    material = json.dumps(
        result, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    )
    result["integrity_sha256"] = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return result


def _observe(
    envelope, expected_format: str, *, reader_implementation: str
) -> dict[str, Any]:
    artifact = envelope.artifact
    source_format = str((artifact.get("source") or {}).get("source_format") or "")
    if source_format != expected_format:
        raise RuntimeError("doc33_source_format_mismatch")
    completeness = assess_canonical_completeness(artifact)
    projection = render_neutral_canonical_projection(artifact)
    root = next(
        item
        for item in artifact.get("containers") or []
        if item.get("container_id") == artifact.get("root_container_ref")
    )
    return {
        "source_format": source_format,
        "schema_version": str(artifact.get("schema_version") or ""),
        "reader_implementation": reader_implementation,
        "root_hash_matched": int(
            envelope.canonical_root_sha256 == artifact.get("canonical_root_hash")
        ),
        "completeness_passed": int(completeness["status"] == "passed"),
        "neutral_projection_nonempty": int(bool(projection.strip())),
        "containers_total": len(artifact.get("containers") or []),
        "nodes_total": len(artifact.get("nodes") or []),
        "tables_total": sum(
            node.get("node_type") == "TABLE" for node in artifact.get("nodes") or []
        ),
        "physical_layout": envelope.physical_layout,
        "root_container_type": str(root.get("container_type") or ""),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read-only DOC33 unified canonical reader proof"
    )
    parser.add_argument("--doc29-store-root", type=Path, required=True)
    parser.add_argument("--doc32-store-root", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = prove(
            doc29_root=args.doc29_store_root.resolve(),
            doc32_root=args.doc32_store_root.resolve(),
        )
    except Exception as exc:  # pragma: no cover - terminal CLI guard
        result = {
            "schema_version": SCHEMA_VERSION,
            "status": "FAILED",
            "error_type": type(exc).__name__,
            "error_code": str(exc).split(":", 1)[0],
            "private_content_in_output": False,
        }
        material = json.dumps(
            result, ensure_ascii=True, sort_keys=True, separators=(",", ":")
        )
        result["integrity_sha256"] = hashlib.sha256(
            material.encode("utf-8")
        ).hexdigest()
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
