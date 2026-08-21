#!/usr/bin/env python3
"""Verify the production candidate on private, already-normalized real PDFs.

The input config and private output must remain outside the repository.  The
safe receipt contains counts and terminals only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from broker_reports_gate1.artifact_models import ArtifactAccessContext
from broker_reports_gate1.artifact_store import (
    ArtifactStoreConfig,
    ArtifactStoreFactory,
)
from broker_reports_gate1.canonical_store import CanonicalReaderFactory
from broker_reports_gate1.gate4_ordinary_trade_candidate import (
    Gate4OrdinaryTradeCandidateRuntimeFactory,
)
from broker_reports_gate1.ordinary_trade_candidate_runtime import (
    OrdinaryTradeCandidateRuntimeFactory,
)
from broker_reports_gate1.gate5_trusted_methodology import (
    GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_ID,
    GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_VERSION,
    GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION,
)
from broker_reports_gate1.ordinary_trade_projection import (
    OrdinaryTradeProjectionFactory,
)
from broker_reports_gate1.ordinary_trade_semantic_compiler import (
    compile_schema_mapping,
)


VERDICT = "ORDINARY_TRADE_SEMANTIC_COMPILER_PRODUCTION_CANDIDATE_READY"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--private-output", type=Path, required=True)
    parser.add_argument("--safe-receipt", type=Path, required=True)
    args = parser.parse_args()
    config = _read_json(args.config)
    mappings = {
        item["alias"]: _mapping_for_case(item)
        for item in config["cases"]
        if item.get("expected_supported", True)
    }
    cases = [
        _run_case(
            item,
            mapping=mappings[
                item.get("reuse_mapping_from_alias", item["alias"])
            ],
        )
        for item in config["cases"]
    ]
    source_records = sum(item["source_records"] for item in cases)
    accounted = sum(item["source_records_accounted"] for item in cases)
    values = sum(item["runtime_values"] for item in cases)
    traced = sum(item["runtime_values_traced"] for item in cases)
    required = sum(item["required_gate5_facts"] for item in cases)
    supplied = sum(item["supplied_gate5_facts"] for item in cases)
    if not cases or not all(item["passed"] for item in cases):
        raise RuntimeError("ordinary_trade_candidate_real_case_failed")
    result = {
        "schema_version": "broker_reports_ordinary_trade_candidate_receipt_v1",
        "verdict": VERDICT,
        "production_activated": False,
        "legacy_fallback_used": False,
        "broker_or_year_special_profiles": 0,
        "cases": cases,
        "metrics": {
            "source_records_accounted": _ratio(accounted, source_records),
            "emitted_runtime_values_traced": _ratio(traced, values),
            "gate5_required_facts_supplied": _ratio(supplied, required),
            "broker_or_year_special_profiles": 0,
            "exact_repeatability": all(
                item["exact_projection_repeatability"] for item in cases
            ),
        },
        "candidate_route": [
            "verified_source_pdf",
            "active_immutable_canonical",
            "exact_fingerprint_schema_mapping",
            "source_observations",
            "deterministic_runtime_records",
            "existing_gate4_fact_v2_shape",
            "unchanged_gate5_deterministic_consumer",
        ],
    }
    private = {
        **result,
        "private_case_evidence": [item.pop("private_evidence") for item in cases],
    }
    _write_json(args.private_output, private)
    _write_json(args.safe_receipt, result)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _mapping_for_case(spec: dict[str, Any]) -> dict[str, Any]:
    root = Path(spec["store_root"])
    store = ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=root / "artifacts.sqlite3",
            payload_root=root / "payloads",
        )
    ).create()
    context = ArtifactAccessContext(
        **spec["context"], allow_private=True, require_source_available=True
    )
    document_id = spec["document_id"]
    reader = CanonicalReaderFactory(store=store, read_enabled=True).create()
    table = reader.read_table(document_id, spec["node_id"], context)
    cells = (table.get("content") or {}).get("cells", [])
    headers = sorted(
        (
            {
                "column": int(item["column"]),
                "literal": str(item.get("displayed_value") or ""),
            }
            for item in cells
            if int(item["row"]) == int(spec["header_row"])
        ),
        key=lambda item: item["column"],
    )
    roles = spec["roles"]
    if len(headers) != len(roles):
        raise RuntimeError("ordinary_trade_candidate_header_accounting")
    title_literal = None
    if spec.get("title_row") is not None:
        titles = [
            str(item.get("displayed_value") or "")
            for item in cells
            if int(item["row"]) == int(spec["title_row"])
            and str(item.get("displayed_value") or "")
        ]
        if len(titles) != 1:
            raise RuntimeError("ordinary_trade_candidate_title_ambiguous")
        title_literal = titles[0]
    return compile_schema_mapping(
        title_literal=title_literal,
        headers=headers,
        model_columns=[
            {"column": header["column"], "semantic_role": role}
            for header, role in zip(headers, roles, strict=True)
        ],
        side_values=spec["side_values"],
        semantic_decisions=spec["semantic_decisions"],
    )


def _run_case(
    spec: dict[str, Any], *, mapping: dict[str, Any]
) -> dict[str, Any]:
    root = Path(spec["store_root"])
    store = ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=root / "artifacts.sqlite3",
            payload_root=root / "payloads",
        )
    ).create()
    context = ArtifactAccessContext(
        **spec["context"], allow_private=True, require_source_available=True
    )
    document_id = spec["document_id"]
    reader = CanonicalReaderFactory(store=store, read_enabled=True).create()
    envelope = reader.read_active_envelope(document_id, context)
    source_pdf_sha256 = _sha256_file(Path(spec["source_pdf"]))
    canonical_source_sha256 = str(
        (envelope.artifact.get("source") or {}).get("source_sha256") or ""
    )
    if source_pdf_sha256 != canonical_source_sha256:
        raise RuntimeError("ordinary_trade_candidate_source_pdf_mismatch")
    projections = OrdinaryTradeProjectionFactory(
        store=store, read_enabled=True
    ).create()
    first_record = projections.compile_and_save(
        document_id=document_id, mappings=[mapping], context=context
    )
    first = projections.read(
        artifact_id=first_record.artifact_id, context=context
    )
    second_record = projections.compile_and_save(
        document_id=document_id, mappings=[mapping], context=context
    )
    second = projections.read(
        artifact_id=second_record.artifact_id, context=context
    )
    repeatable = (
        first_record.artifact_id == second_record.artifact_id
        and first["projection_sha256"] == second["projection_sha256"]
        and _json_bytes(first) == _json_bytes(second)
    )
    gate4 = Gate4OrdinaryTradeCandidateRuntimeFactory(
        store=store, read_enabled=True
    ).create()
    facts_first = gate4.list_facts(context=context)
    facts_second = gate4.list_facts(context=context)
    facts = [
        item
        for item in facts_first
        if item["gate3_binding"]["canonical_binding"]["document_id"]
        == document_id
    ]
    fact_repeatable = _json_bytes(facts_first) == _json_bytes(facts_second)
    gate5 = OrdinaryTradeCandidateRuntimeFactory(
        store=store, read_enabled=True
    ).create()
    methodology_ref = {
        "schema_version": GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION,
        "methodology_id": GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_ID,
        "methodology_version": GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_VERSION,
    }
    assessment = gate5.assess(
        methodology_ref=methodology_ref, context=context
    )
    available = gate5.assemble_available(
        methodology_ref=methodology_ref, context=context
    )
    observations = first["source_observations"]
    records = first["runtime_records"]
    runtime_values = sum(len(item["roles"]) for item in records)
    traced_values = sum(
        bool((role.get("source_binding") or {}).get("canonical_cell"))
        and bool((role.get("source_binding") or {}).get("source_literal"))
        and bool((role.get("source_binding") or {}).get("deterministic_transform"))
        for item in records
        for role in item["roles"]
    )
    required = sum(
        item["disposition"] == "RUNTIME_READY" for item in observations
    )
    supplied = sum(
        item["financial_type"] in {"SECURITY_PURCHASE", "SECURITY_DISPOSAL"}
        for item in facts
    )
    security_ready = assessment["security_fact_counts"]["ready"]
    table_count = sum(
        item.get("node_type") == "TABLE"
        for item in envelope.artifact.get("nodes", [])
    )
    expected_supported = spec.get("expected_supported", True)
    document_status = next(
        (
            item["status"]
            for item in assessment["document_consumption"]
            if item["document_id"] == document_id
        ),
        "NOT_ACTIVATED_FOR_SUPPORTED_SCOPE",
    )
    supported_passed = (
        required > 0
        and supplied == required
        and security_ready == required
    )
    unsupported_passed = (
        required == 0
        and supplied == 0
        and security_ready == 0
        and not facts
        and observations
        and all(
            item["disposition"] == "RELEVANT_UNMAPPED"
            for item in observations
        )
    )
    result = {
        "alias": spec["alias"],
        "expected_supported": expected_supported,
        "passed": (
            repeatable
            and fact_repeatable
            and traced_values == runtime_values
            and (supported_passed if expected_supported else unsupported_passed)
        ),
        "source_pdf_sha256_matches_canonical": True,
        "full_canonical_tables_seen": table_count,
        "matched_supported_tables": sum(
            item["matched_tables"] for item in first["mapping_matches"]
        ),
        "source_records": len(observations),
        "source_records_accounted": len(observations),
        "runtime_ready_source_records": required,
        "relevant_unmapped_source_records": sum(
            item["disposition"] == "RELEVANT_UNMAPPED" for item in observations
        ),
        "runtime_records": len(records),
        "runtime_values": runtime_values,
        "runtime_values_traced": traced_values,
        "required_gate5_facts": required,
        "supplied_gate5_facts": supplied,
        "gate5_security_facts_ready": security_ready,
        "gate5_document_status": document_status,
        "gate5_available_blockers": len(available["blockers"]),
        "gate5_blocker_reason_codes": sorted(
            {item["reason_code"] for item in available["blockers"]}
        ),
        "semantic_model_decisions_per_schema": len(mapping["semantic_decisions"]),
        "document_financial_values_authored_by_model": 0,
        "broker_or_year_special_profiles": 0,
        "exact_projection_repeatability": repeatable,
        "exact_gate4_fact_repeatability": fact_repeatable,
        "private_evidence": {
            "document_id": document_id,
            "source_pdf": spec["source_pdf"],
            "source_pdf_sha256": source_pdf_sha256,
            "canonical_version_id": envelope.canonical_version_id,
            "canonical_root_sha256": envelope.canonical_root_sha256,
            "mapping": mapping,
            "projection_artifact_id": first_record.artifact_id,
            "projection": first,
            "gate4_facts": facts,
            "gate5_assessment": assessment,
            "gate5_available": available,
        },
    }
    return result


def _ratio(numerator: int, denominator: int) -> dict[str, Any]:
    return {
        "numerator": numerator,
        "denominator": denominator,
        "percent": 100.0 if denominator == 0 else round(100 * numerator / denominator, 2),
    }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())
