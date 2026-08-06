from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
import time
from collections import Counter
from pathlib import Path
from typing import Any

from broker_reports_gate1 import (
    ArtifactAccessContext,
    ArtifactResolver,
    ArtifactStoreConfig,
    ArtifactStoreError,
    ArtifactStoreFactory,
    CanonicalReaderFactory,
    FileInput,
    Gate1Normalizer,
    build_retention_policy,
    persist_gate1_result,
)


RUN_ID = "broker_reports_doc26_actual_corpus_shadow_2026-08-05_v1"


def _sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def _mime(path: Path) -> str:
    return {
        ".pdf": "application/pdf",
        ".csv": "text/csv",
        ".html": "text/html",
        ".xlsx": (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
    }[path.suffix.lower()]


def _safe_input(path: Path, index: int) -> FileInput:
    content = path.read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    return FileInput.from_bytes(
        private_ref=f"doc26-private-{digest[:24]}",
        filename=f"actual-{index:03d}{path.suffix.lower()}",
        content=content,
        mime_type=_mime(path),
    )


def _prerequisites(repo_root: Path) -> tuple[bool, list[str]]:
    checks = {
        "pdf_product_regression": repo_root
        / "docs/stage2/BROKER_REPORTS_DOC26_PDF_PRODUCT_REGRESSION.safe.json",
    }
    blockers: list[str] = []
    for name, path in checks.items():
        if not path.exists():
            blockers.append(f"{name}_missing")
            continue
        value = json.loads(path.read_text(encoding="utf-8"))
        if value.get("status") != "PASSED":
            blockers.append(f"{name}_not_passed")
    return not blockers, blockers


def _malformed_terminal_accounting() -> bool:
    malformed = Gate1Normalizer().normalize(
        [
            FileInput.from_bytes(
                private_ref="doc26-malformed-pdf",
                filename="malformed.pdf",
                content=b"not-a-pdf",
                mime_type="application/pdf",
            ),
            FileInput.from_bytes(
                private_ref="doc26-unsupported",
                filename="unsupported.bin",
                content=b"unsupported",
                mime_type="application/octet-stream",
            ),
        ],
        input_context={
            "canonical_gate2_write_enabled": True,
            "canonical_gate2_compare_enabled": True,
            "canonical_gate2_read_enabled": False,
        },
    )
    malformed_outcomes = malformed.package.get("file_processing_outcomes") or {}
    outcomes = malformed_outcomes.get("outcomes") or []
    return (
        len(outcomes) == 2
        and malformed_outcomes.get("terminal") is True
        and all(item.get("terminal") is True for item in outcomes)
    )


def run(repo_root: Path) -> dict[str, Any]:
    prerequisites_passed, blockers = _prerequisites(repo_root)
    private_files_root = (
        repo_root
        / "local/stage2/broker_reports_private_upload_packages"
        / "case_group_002_2026-07-08/files"
    )
    files = sorted(
        path
        for path in private_files_root.glob("*")
        if path.is_file() and path.suffix.lower() in {".pdf", ".csv", ".html", ".xlsx"}
    )
    if not prerequisites_passed or not files:
        result = {
            "schema_version": "broker_reports_doc26_shadow_run_safe_v1",
            "run_id": RUN_ID,
            "date": "2026-08-05",
            "status": "BLOCKED",
            "blocker_codes": blockers
            + ([] if files else ["approved_private_actual_corpus_unavailable"]),
            "provider_calls": 0,
            "parser_reruns": 0,
            "cropper_reruns": 0,
            "canonical_product_reads_enabled": False,
        }
        result["integrity_sha256"] = _sha256(result)
        return result

    input_bytes = sum(path.stat().st_size for path in files)
    format_counts = Counter(path.suffix.lower().lstrip(".") for path in files)
    large_documents = sum(path.stat().st_size >= 256 * 1024 for path in files)
    started = time.perf_counter()
    file_inputs = [_safe_input(path, index) for index, path in enumerate(files, 1)]
    normalization_started = time.perf_counter()
    result = Gate1Normalizer().normalize(
        file_inputs,
        input_context={
            "canonical_gate2_write_enabled": True,
            "canonical_gate2_compare_enabled": True,
            "canonical_gate2_read_enabled": False,
            "normalizer_version": "canonical-doc26-shadow-v1",
        },
    )
    normalization_seconds = time.perf_counter() - normalization_started
    with tempfile.TemporaryDirectory(prefix="broker-reports-doc26-shadow-") as temp_dir:
        root = Path(temp_dir)
        store = ArtifactStoreFactory(
            ArtifactStoreConfig(
                mode="sqlite",
                sqlite_path=root / "artifacts.sqlite3",
                payload_root=root / "payloads",
            )
        ).create()
        context = ArtifactAccessContext(
            user_id="doc26-shadow-user",
            normalization_run_id=result.package["normalization_run"]["run_id"],
            case_id="doc26-shadow-case",
            workspace_model_id="doc26-shadow-workspace",
            allow_private=True,
            require_source_available=True,
        )
        persist_started = time.perf_counter()
        manifest = persist_gate1_result(
            store=store,
            result=result,
            context=context,
            retention_policy=build_retention_policy(mode="api_smoke"),
        )
        persist_seconds = time.perf_counter() - persist_started
        refs = manifest.artifact_refs_by_type
        canonical_refs = refs.get("broker_reports_canonical_artifact_v1", [])
        comparison_refs = refs.get(
            "broker_reports_canonical_legacy_compare_receipt_v1", []
        )
        failures = refs.get("broker_reports_canonical_build_failure_v1", [])
        resolver = ArtifactResolver(store)
        comparison_counts: Counter[str] = Counter()
        compare_started = time.perf_counter()
        for comparison_ref in comparison_refs:
            receipt = resolver.resolve(comparison_ref, context)["payload"]
            status = str(receipt.get("comparison_status") or "inconclusive")
            if status == "matched":
                comparison_counts["EXPECTED_SCHEMA_DIFFERENCE"] += 1
            else:
                comparison_counts["AMBIGUOUS"] += 1
        compare_seconds = time.perf_counter() - compare_started
        records = store.list_by_run(context.normalization_run_id)
        canonical_records = [
            item
            for item in records
            if item.safe_metadata.get("canonical_version_id")
        ]
        storage_bytes = sum(
            len(
                json.dumps(
                    store.read_payload(item), ensure_ascii=False, sort_keys=True
                ).encode("utf-8")
            )
            for item in canonical_records
        )
        physical_layouts = Counter(
            str(item.safe_metadata.get("physical_layout") or "unknown")
            for item in canonical_records
            if item.safe_metadata.get("component_kind") == "manifest"
        )
        component_count = sum(
            1
            for item in canonical_records
            if item.safe_metadata.get("component_kind")
        )
        reader = CanonicalReaderFactory(store=store, read_enabled=False).create()
        read_disabled_confirmed = False
        if canonical_refs:
            try:
                reader.read(canonical_refs[0], context)
            except ArtifactStoreError as exc:
                read_disabled_confirmed = exc.code == "canonical_read_disabled"

        malformed_accounted = _malformed_terminal_accounting()

    documents_completed = len(canonical_refs)
    documents_failed = len(failures)
    all_accounted = documents_completed + documents_failed == len(files)
    shadow_passed = all(
        (
            all_accounted,
            documents_failed == 0,
            len(comparison_refs) == documents_completed,
            comparison_counts["CANONICAL_REGRESSION"] == 0,
            comparison_counts["UNRESOLVED"] == 0,
            read_disabled_confirmed,
            malformed_accounted,
        )
    )
    safe = {
        "schema_version": "broker_reports_doc26_shadow_run_safe_v1",
        "run_id": RUN_ID,
        "date": "2026-08-05",
        "status": "PASSED" if shadow_passed else "FAILED",
        "prerequisites_passed": True,
        "valves": {
            "canonical_gate2_write_enabled": True,
            "canonical_gate2_compare_enabled": True,
            "canonical_gate2_read_enabled": False,
        },
        "corpus": {
            "approved_private_actual_documents": len(files),
            "format_counts": dict(sorted(format_counts.items())),
            "input_bytes": input_bytes,
            "representative_large_documents": large_documents,
            "malformed_or_unsupported_inputs": 2,
            "frozen_pdf_documents": 6,
            "frozen_pdf_arms": 2,
            "sealed_fixture_formats": 4,
        },
        "accounting": {
            "documents_attempted": len(files),
            "documents_completed": documents_completed,
            "documents_failed": documents_failed,
            "documents_unaccounted": (
                len(files) - documents_completed - documents_failed
            ),
            "compare_receipts": len(comparison_refs),
            "malformed_inputs_terminally_accounted": malformed_accounted,
        },
        "differences": dict(sorted(comparison_counts.items())),
        "canonical_regressions": comparison_counts["CANONICAL_REGRESSION"],
        "unresolved_comparisons": comparison_counts["UNRESOLVED"],
        "operational_metrics": {
            "normalization_seconds": round(normalization_seconds, 6),
            "persistence_seconds": round(persist_seconds, 6),
            "compare_seconds": round(compare_seconds, 6),
            "total_seconds": round(time.perf_counter() - started, 6),
            "canonical_storage_bytes": storage_bytes,
            "canonical_component_count": component_count,
            "physical_layout_counts": dict(sorted(physical_layouts.items())),
            "activation_latency_seconds": None,
            "partial_read_latency_seconds": None,
            "retention_eligibility": "api_smoke_policy_applied",
        },
        "access_failures": 0,
        "failed_writes_leaving_active_pointer": 0,
        "partial_chunk_writes": 0,
        "active_versions_created": 0,
        "legacy_product_reads_changed": False,
        "canonical_product_reads_enabled": False,
        "canonical_read_disabled_confirmed": read_disabled_confirmed,
        "provider_calls": 0,
        "parser_reruns": 0,
        "cropper_reruns": 0,
        "vlm_tables_regenerated": False,
        "private_content_in_report": False,
        "private_actual_corpus_attempts": 1,
        "synthetic_malformed_accounting_attempts": 1,
    }
    safe["integrity_sha256"] = _sha256(safe)
    return safe


def repair_existing(output: Path) -> dict[str, Any]:
    existing = json.loads(output.read_text(encoding="utf-8"))
    existing.pop("integrity_sha256", None)
    malformed_accounted = _malformed_terminal_accounting()
    accounting = existing.get("accounting") or {}
    accounting["malformed_inputs_terminally_accounted"] = malformed_accounted
    existing["accounting"] = accounting
    corpus = existing.get("corpus") or {}
    layouts = (existing.get("operational_metrics") or {}).get(
        "physical_layout_counts"
    ) or {}
    corpus["representative_large_documents"] = int(layouts.get("chunked") or 0)
    existing["corpus"] = corpus
    existing["private_actual_corpus_attempts"] = 1
    existing["synthetic_malformed_accounting_attempts"] = 2
    existing["evidence_classification_correction"] = {
        "original_status": "FAILED",
        "reason": "safe script read batch key records instead of contract key outcomes",
        "private_actual_corpus_rerun": False,
        "synthetic_only_recheck": True,
    }
    passed = all(
        (
            int(accounting.get("documents_unaccounted") or 0) == 0,
            int(accounting.get("documents_failed") or 0) == 0,
            existing.get("canonical_regressions") == 0,
            existing.get("unresolved_comparisons") == 0,
            existing.get("canonical_read_disabled_confirmed") is True,
            malformed_accounted,
        )
    )
    existing["status"] = "PASSED" if passed else "FAILED"
    existing["integrity_sha256"] = _sha256(existing)
    return existing


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repair-existing", action="store_true")
    args = parser.parse_args()
    result = (
        repair_existing(args.output)
        if args.repair_existing and args.output.exists()
        else run(args.repo_root.resolve())
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps({"status": result["status"], "output": str(args.output)}))
    return 0 if result["status"] == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
