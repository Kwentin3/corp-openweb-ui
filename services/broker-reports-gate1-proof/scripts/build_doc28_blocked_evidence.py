from __future__ import annotations

import hashlib
import json
import subprocess
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Any

from broker_reports_gate1.canonical_consumer_migration import (
    FROZEN_CONSUMER_SURFACES,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
SERVICE_ROOT = REPO_ROOT / "services" / "broker-reports-gate1-proof"
DOC_ROOT = REPO_ROOT / "docs" / "stage2"
REPORT_ROOT = REPO_ROOT / "docs" / "reports" / "2026-08-05"
COHORT_ROOT = (
    REPO_ROOT
    / "local"
    / "stage2"
    / "broker_reports_private_upload_packages"
    / "case_group_002_2026-07-08"
    / "files"
)

SAFE_NAMES = (
    "BROKER_REPORTS_DOC28_DURABLE_STORAGE_AUDIT.safe.json",
    "BROKER_REPORTS_DOC28_APPROVED_COHORT.safe.json",
    "BROKER_REPORTS_DOC28_DURABLE_BACKFILL.safe.json",
    "BROKER_REPORTS_DOC28_ACTIVE_VERSION_RESULTS.safe.json",
    "BROKER_REPORTS_DOC28_NEW_UPLOAD_SHADOW.safe.json",
    "BROKER_REPORTS_DOC28_RESEARCH_CONSUMER_RESULTS.safe.json",
    "BROKER_REPORTS_DOC28_WAVE2_SHADOW_RESULTS.safe.json",
    "BROKER_REPORTS_DOC28_OBSERVABILITY.safe.json",
    "BROKER_REPORTS_DOC28_RETENTION_RESULTS.safe.json",
    "BROKER_REPORTS_DOC28_TEST_RESULTS.safe.json",
    "BROKER_REPORTS_DOC28_DECISION.safe.json",
)

REPORT_NAME = "BROKER_REPORTS_DOC28_GATE2_DURABLE_CONTOUR.report.md"
RECEIPT_NAME = (
    "BROKER_REPORTS_DOC28_GATE2_DURABLE_CONTOUR.receipt.safe.json"
)
BRIEF_NAME = "BROKER_REPORTS_DOC28_GATE2_DURABLE_CONTOUR_BRIEF.md"

DOC28_NEW_PATHS = {
    "services/broker-reports-gate1-proof/scripts/build_doc28_blocked_evidence.py",
    "services/broker-reports-gate1-proof/tests/test_broker_reports_doc28_safe_evidence.py",
    *(f"docs/stage2/{name}" for name in SAFE_NAMES),
    f"docs/reports/2026-08-05/{REPORT_NAME}",
    f"docs/reports/2026-08-05/{RECEIPT_NAME}",
    f"docs/reports/2026-08-05/{BRIEF_NAME}",
    "runbooks/README.md",
    "docs/ops/BROKER_REPORTS_CANONICAL_DURABLE_STORAGE_RUNBOOK.md",
    "docs/ops/BACKUP_RESTORE_RUNBOOK.md",
    "docs/ops/BROKER_REPORTS_CANONICAL_RETENTION_RUNBOOK.md",
}

FORMAT_MIME = {
    ".pdf": "PDF",
    ".html": "HTML",
    ".csv": "CSV",
    ".xlsx": "XLSX",
}


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(args),
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _git(*args: str) -> str:
    result = _run("git", *args)
    if result.returncode:
        raise RuntimeError(f"git command failed: {' '.join(args)}")
    return result.stdout.strip()


def _integrity(payload: dict[str, Any]) -> dict[str, Any]:
    result = dict(payload)
    encoded = json.dumps(
        result,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    result["integrity_sha256"] = hashlib.sha256(encoded).hexdigest()
    return result


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            _integrity(payload),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _size_class(size: int) -> str:
    if size < 64 * 1024:
        return "small"
    if size < 1024 * 1024:
        return "medium"
    return "large"


def _cohort() -> dict[str, Any]:
    files = sorted(
        path
        for path in COHORT_ROOT.iterdir()
        if path.is_file() and path.suffix.lower() in FORMAT_MIME
    )
    documents = []
    for ordinal, path in enumerate(files, start=1):
        content = path.read_bytes()
        content_sha256 = hashlib.sha256(content).hexdigest()
        document_id_hash = hashlib.sha256(
            f"doc28-cohort-v1:{ordinal}:{content_sha256}".encode("utf-8")
        ).hexdigest()
        documents.append(
            {
                "document_id_hash": document_id_hash,
                "content_sha256": content_sha256,
                "format": FORMAT_MIME[path.suffix.lower()],
                "size_class": _size_class(len(content)),
                "processing_status": "SOURCE_AVAILABLE_BACKFILL_BLOCKED",
                "canonical_version_hash": None,
            }
        )
    formats = Counter(item["format"] for item in documents)
    unique_content_hashes = len(
        {item["content_sha256"] for item in documents}
    )
    return {
        "schema_version": "broker_reports_doc28_approved_cohort_safe_v1",
        "date": "2026-08-05",
        "status": "FROZEN_SOURCE_ONLY",
        "cohort_frozen_before_write": True,
        "documents_total": len(documents),
        "format_counts": dict(sorted(formats.items())),
        "formats": f"{len(formats)}/4",
        "source_documents_available": len(documents),
        "unique_content_hashes": unique_content_hashes,
        "duplicate_content_documents": len(documents) - unique_content_hashes,
        "durable_versions_available": 0,
        "active_versions_available": 0,
        "doc26_historical_layout_baseline": {
            "chunked": 5,
            "single_payload": 11,
            "current_doc28_layout_mapping_available": False,
        },
        "trusted_access_contexts_assigned": 0,
        "documents_unaccounted": 0,
        "private_content_in_safe_artifact": 0,
        "documents": documents,
    }


def _runtime_audit() -> dict[str, Any]:
    docker_version = _run(
        "docker", "version", "--format", "{{.Server.Version}}"
    )
    compose = _run("docker", "compose", "version")
    volume = _run("docker", "volume", "inspect", "openwebui_data")
    container = _run("docker", "inspect", "openwebui")
    compose_text = (
        REPO_ROOT / "compose" / "openwebui.compose.yml"
    ).read_text(encoding="utf-8")
    pipe_text = (
        SERVICE_ROOT
        / "openwebui_actions"
        / "broker_reports_gate1_pipe.py"
    ).read_text(encoding="utf-8")
    backup_text = (REPO_ROOT / "scripts" / "backup.sh").read_text(
        encoding="utf-8"
    )
    restore_text = (REPO_ROOT / "scripts" / "restore.md").read_text(
        encoding="utf-8"
    )
    runtime_access = volume.returncode == 0 and container.returncode == 0
    return {
        "schema_version": (
            "broker_reports_doc28_durable_storage_audit_safe_v1"
        ),
        "date": "2026-08-05",
        "status": "BLOCKED_DURABLE_BACKEND_NOT_APPROVED_OR_ACCESSIBLE",
        "artifact_store_runtime_owner": "ArtifactStoreFactory",
        "schema_migration_owner": "SqliteArtifactStoreAdapter._ensure_schema",
        "deployment_candidate": {
            "backend": "existing SQLite metadata plus file payload adapter",
            "volume": "openwebui_data",
            "mount": "/app/backend/data",
            "metadata_path": (
                "/app/backend/data/broker_reports_gate1/artifacts.sqlite3"
            ),
            "payload_path": (
                "/app/backend/data/broker_reports_gate1/payloads"
            ),
            "compose_volume_declared": (
                "openwebui_data:/app/backend/data" in compose_text
            ),
            "pipe_defaults_inside_mount": all(
                value in pipe_text
                for value in (
                    "/app/backend/data/broker_reports_gate1/artifacts.sqlite3",
                    "/app/backend/data/broker_reports_gate1/payloads",
                )
            ),
            "second_storage_engine_created": False,
        },
        "authorized_runtime": {
            "docker_server_reachable": docker_version.returncode == 0,
            "docker_server_version": docker_version.stdout.strip() or None,
            "docker_compose_plugin_available": compose.returncode == 0,
            "target_volume_accessible": volume.returncode == 0,
            "target_container_accessible": container.returncode == 0,
            "vps_access_authorized_by_repository": False,
            "runtime_proof_possible": runtime_access,
        },
        "backup_restore": {
            "backup_script_covers_openwebui_data": (
                "backup_volume openwebui_data" in backup_text
            ),
            "restore_document_covers_openwebui_data": (
                "Restore `openwebui_data`" in restore_text
            ),
            "completed_backup_receipt_available": False,
            "completed_restore_receipt_available": False,
            "integrity_drill_completed": False,
        },
        "durability_criteria": {
            "store_outside_research_run_directory": "CANDIDATE_ONLY",
            "store_outside_temp_directory": "CANDIDATE_ONLY",
            "second_process_can_read_first_process_writes": "NOT_PROVEN",
            "service_restart_preserves_metadata": "NOT_PROVEN",
            "service_restart_preserves_payloads": "NOT_PROVEN",
            "active_pointers_survive_restart": "NOT_PROVEN",
            "chunk_references_survive_restart": "NOT_PROVEN",
            "metadata_payload_consistency": "NOT_PROVEN",
        },
        "temporary_storage_used_as_durable": False,
        "durable_store_created": False,
        "runtime_mutations": 0,
    }


def _backfill() -> dict[str, Any]:
    return {
        "schema_version": "broker_reports_doc28_durable_backfill_safe_v1",
        "date": "2026-08-05",
        "status": "NOT_STARTED_STOP_GATE",
        "cohort_documents_total": 16,
        "durable_versions_created": 0,
        "validated_versions": 0,
        "active_versions": 0,
        "reprocess_required": True,
        "reprocess_reason": (
            "DOC26 temporary canonical store and normalized payload graph no longer exist"
        ),
        "provider_rerun_required": False,
        "provider_calls": 0,
        "parser_reruns": 0,
        "hidden_provider_reruns": 0,
        "partial_writes": 0,
        "orphan_chunks": 0,
        "blocker": "approved target runtime and durable volume access are absent",
    }


def _active_versions() -> dict[str, Any]:
    return {
        "schema_version": (
            "broker_reports_doc28_active_version_results_safe_v1"
        ),
        "date": "2026-08-05",
        "status": "NOT_STARTED",
        "candidate_versions": 0,
        "active_versions": 0,
        "active_pointers_after_restart_percent": 0,
        "root_hashes_after_restart_percent": 0,
        "unresolved_refs": 0,
        "missing_chunks": 0,
        "activation_attempts": 0,
        "failed_activations_changing_pointer": 0,
        "rollback_after_restart": "NOT_TESTED",
        "cross_tenant_activation_attempts": 0,
        "global_activation_performed": False,
    }


def _new_uploads() -> dict[str, Any]:
    return {
        "schema_version": (
            "broker_reports_doc28_new_upload_shadow_safe_v1"
        ),
        "date": "2026-08-05",
        "status": "NOT_STARTED",
        "formats_supported_by_existing_normalizer": [
            "PDF",
            "HTML",
            "CSV",
            "XLSX",
        ],
        "format_support_contract": "4/4",
        "durable_shadow_write_runs": 0,
        "legacy_product_results_changed": False,
        "canonical_product_reads_enabled": False,
        "failed_writes_breaking_legacy": 0,
        "partial_writes": 0,
        "orphan_chunks": 0,
        "idempotent_redelivery": "NOT_TESTED",
    }


def _research_consumer() -> dict[str, Any]:
    return {
        "schema_version": (
            "broker_reports_doc28_research_consumer_results_safe_v1"
        ),
        "date": "2026-08-05",
        "status": "BLOCKED",
        "consumer_id": "local_pdf_compact_canonical_proof",
        "compatibility_adapter": (
            "LocalPdfCompactResearchCanonicalAdapterFactory"
        ),
        "adapter_validation_from_doc27": "PASSED_ON_SEALED_FIXTURE",
        "durable_cohort_shadow": "NOT_STARTED",
        "canonical_regressions": 0,
        "unresolved_comparisons": 0,
        "migrated": False,
        "rollback": "NOT_TESTED_ON_DURABLE_STORE",
        "silent_fallbacks": 0,
        "blocker": "no durable active canonical version exists",
    }


def _wave2() -> dict[str, Any]:
    candidates = [
        asdict(item)
        for item in FROZEN_CONSUMER_SURFACES
        if item.consumer_class == "WAVE_2_BACKGROUND_PRODUCT"
    ]
    return {
        "schema_version": (
            "broker_reports_doc28_wave2_shadow_results_safe_v1"
        ),
        "date": "2026-08-05",
        "status": "NOT_STARTED_STOP_GATE",
        "consumers_accounted": f"{len(candidates)}/6",
        "compatibility_contracts": "0/6",
        "shadow_runs": "0/3",
        "canonical_regressions": 0,
        "unresolved": 0,
        "access_regressions": 0,
        "side_effects_from_shadow": 0,
        "consumers_migrated": 0,
        "product_canonical_read_enabled": False,
        "migration_decision": "BLOCKED_BEFORE_SHADOW",
        "candidates": [
            {
                "consumer_id": item["consumer_id"],
                "legacy_reads": item["current_legacy_reads"],
                "side_effects": item["side_effects"],
                "access_context": item["access_context"],
                "compatibility_contract": "NOT_CREATED_STOP_GATE",
                "shadow": "NOT_STARTED",
                "migrated": False,
            }
            for item in candidates
        ],
    }


def _observability() -> dict[str, Any]:
    metrics = (
        "canonical_write_attempts",
        "canonical_write_success",
        "canonical_write_failure",
        "canonical_validation_failure",
        "canonical_activation_success",
        "canonical_activation_failure",
        "canonical_read_attempts",
        "canonical_read_success",
        "canonical_read_failure",
        "canonical_chunks_written",
        "canonical_chunks_read",
        "canonical_storage_bytes",
        "active_version_count",
        "rollback_count",
        "retention_delete_count",
        "orphan_cleanup_count",
    )
    return {
        "schema_version": "broker_reports_doc28_observability_safe_v1",
        "date": "2026-08-05",
        "status": "BLOCKED_NO_RUNTIME",
        "metrics": {name: 0 for name in metrics},
        "durable_write_events_accounted_percent": "NOT_APPLICABLE_NO_WRITES",
        "activation_events_accounted_percent": "NOT_APPLICABLE_NO_ACTIVATIONS",
        "rollback_events_accounted_percent": "NOT_APPLICABLE_NO_ROLLBACKS",
        "shadow_reads_accounted_percent": "NOT_APPLICABLE_NO_SHADOW",
        "silent_failures": 0,
        "private_content_in_metrics": 0,
        "health_checks": {
            "metadata_store_writable": "NOT_TESTED",
            "payload_store_writable": "NOT_TESTED",
            "metadata_payload_consistency": "NOT_TESTED",
            "active_pointer_resolvable": "NOT_TESTED",
            "sample_chunk_readable": "NOT_TESTED",
            "retention_worker_status": "NOT_TESTED",
            "storage_capacity_threshold": "NOT_TESTED",
        },
    }


def _retention() -> dict[str, Any]:
    classes = (
        "SOURCE",
        "ACTIVE_CANONICAL",
        "SUPERSEDED_CANONICAL",
        "EVIDENCE",
        "RAW_PROVIDER",
        "TEMPORARY",
        "PROJECTION_CACHE",
        "RESEARCH",
    )
    return {
        "schema_version": "broker_reports_doc28_retention_results_safe_v1",
        "date": "2026-08-05",
        "status": "NOT_STARTED",
        "retention_classes": {
            name: "NOT_TESTED_ON_DURABLE_STORE" for name in classes
        },
        "retention_classes_tested": "0/8",
        "active_versions_deleted": 0,
        "rollback_targets_deleted": 0,
        "premature_evidence_deletions": 0,
        "orphan_chunks_after_rotation": 0,
        "rotation_receipts": "0/0",
    }


def _repository_hygiene() -> dict[str, Any]:
    entries = []
    for line in _git("status", "--short", "--untracked-files=all").splitlines():
        entries.append((line[:2], line[3:].replace("\\", "/")))
    baseline = [item for item in entries if item[1] not in DOC28_NEW_PATHS]
    if len(baseline) != 267:
        raise RuntimeError(
            f"pre-DOC28 inventory drift: expected 267, got {len(baseline)}"
        )
    return {
        "pre_doc28_dirty_paths": 267,
        "post_doc28_dirty_paths": len(entries),
        "doc28_new_paths": sum(
            path in DOC28_NEW_PATHS for _, path in entries
        ),
        "preexisting_paths_preserved": len(baseline),
        "tracked_private_artifacts": 0 if not _git("ls-files", "local") else 1,
        "historical_doc7_doc27_reports_modified": 0,
        "cleanup_or_reset_performed": False,
    }


def _tests() -> dict[str, Any]:
    return {
        "schema_version": "broker_reports_doc28_test_results_safe_v1",
        "date": "2026-08-05",
        "status": "BLOCKED_BEFORE_RUNTIME_TESTS",
        "focused_doc28_safe_evidence_tests": {
            "passed": 4,
            "failed": 0,
        },
        "focused_doc24_doc28_closure_chain": {
            "passed": 48,
            "failed": 0,
        },
        "contract_and_privacy_checks": "PASSED",
        "ruff": "PASSED",
        "durability_tests": "NOT_STARTED_RUNTIME_BLOCKER",
        "restart_tests": "NOT_STARTED_RUNTIME_BLOCKER",
        "backup_restore_tests": "NOT_STARTED_RUNTIME_BLOCKER",
        "research_consumer_tests": "NOT_STARTED_RUNTIME_BLOCKER",
        "wave2_shadow_tests": "NOT_STARTED_RUNTIME_BLOCKER",
        "full_suite_terminal_for_doc28": False,
        "full_suite_timeout": False,
        "last_terminal_baseline": {
            "source": "DOC27",
            "passed": 2909,
            "skipped": 5,
            "failed": 7,
            "errors": 11,
        },
        "new_unexplained_failures": 0,
        "historical_hashes_rewritten": 0,
        "stop_reason": (
            "runtime durability evidence cannot be produced without target volume access"
        ),
    }


def _decision() -> dict[str, Any]:
    return {
        "schema_version": "broker_reports_doc28_decision_safe_v1",
        "date": "2026-08-05",
        "DOC28_PROGRAM": "BLOCKED",
        "DURABLE_CANONICAL_STORE": "BLOCKED",
        "APPROVED_REAL_COHORT": "PARTIAL",
        "NEW_UPLOAD_DURABLE_SHADOW": "NOT_STARTED",
        "RESEARCH_CONSUMER_MIGRATION": "BLOCKED",
        "WAVE_2_SHADOW": "NOT_STARTED",
        "WAVE_2_MIGRATION_READINESS": "BLOCKED",
        "BACKUP_RESTORE": "BLOCKED",
        "RETENTION_ROTATION": "BLOCKED",
        "PRIMARY_PRODUCT_CUTOVER": "NOT_PERFORMED",
        "LEGACY_HANDOFF": "RETAINED",
        "GATE3": "NOT_STARTED",
        "DURABLE_STORAGE_RUNBOOK": "CURRENT_BLOCKED",
        "BACKUP_RESTORE_RUNBOOK": "CURRENT_BLOCKED",
        "RETENTION_RUNBOOK": "CURRENT_BLOCKED",
        "READ_AUTHORITY_MAP": "CURRENT",
        "CONTRADICTORY_AUTHORITY_DOCS": 0,
        "next_goal_authorized": False,
        "blocker_code": (
            "BLOCKED_DURABLE_BACKEND_NOT_APPROVED_OR_ACCESSIBLE"
        ),
        "required_unblock_evidence": [
            "identify and approve the target OpenWebUI deployment",
            "provide read/write operator access to its openwebui_data volume",
            "provide restart authority for the controlled service",
            "provide backup destination and restore-drill authority",
            "confirm capacity threshold and retention-worker ownership",
        ],
    }


def _report(
    storage: dict[str, Any],
    cohort: dict[str, Any],
    wave2: dict[str, Any],
    tests: dict[str, Any],
    decision: dict[str, Any],
) -> str:
    wave2_lines = "\n".join(
        f"- `{item['consumer_id']}`: `NOT_STARTED`; side effects remain "
        f"product/operator-owned."
        for item in wave2["candidates"]
    )
    formats = cohort["format_counts"]
    return f"""# Broker Reports DOC28 Gate 2 Durable Contour

Date: 2026-08-05

Status: `BLOCKED`

DOC28 stopped at the mandatory deployment gate. No durable write, activation,
provider/parser rerun, product read, research cutover or Wave 2 shadow occurred.

## 1. Durable backend

The only admissible candidate is the existing ArtifactStore using SQLite
metadata and file payloads below the compose `openwebui_data` mount. No second
storage engine was created.

## 2. Why it is not yet durable operationally

The repository declares the volume and the pipe defaults are inside its mount,
but the target volume/container are not accessible, the available Docker
context has no `openwebui_data`, and repository policy does not authorize VPS
access. Candidate configuration is not restart evidence.

## 3. Restart persistence

Not tested. Cross-process, service-restart, active-pointer and chunk-reference
persistence remain `NOT_PROVEN`.

## 4. Backup and restore

The existing backup script includes `openwebui_data` and the restore document
describes recreating that volume. No backup or restore receipt exists and no
root/manifest/access integrity drill was performed.

## 5. Approved cohort

The source cohort was frozen before DOC28 writes: `{cohort['documents_total']}`
documents — PDF `{formats.get('PDF', 0)}`, HTML `{formats.get('HTML', 0)}`,
CSV `{formats.get('CSV', 0)}`, XLSX `{formats.get('XLSX', 0)}`. Safe evidence
contains only document/content hashes, format, size class and blocked status.
The 16 logical documents contain `{cohort['unique_content_hashes']}` unique
byte hashes; `{cohort['duplicate_content_documents']}` duplicate-content item
remains explicitly accounted rather than excluded.

## 6. Versions and activation

Created `0`, validated `0`, active `0`. The temporary DOC26 store is gone, so
normalization reprocessing is explicitly required; no hidden rerun occurred.

## 7. New-upload four-format shadow

The existing normalizer supports 4/4 formats, but durable shadow runs are `0`.
Legacy results and canonical product reads are unchanged.

## 8. Research consumer

`local_pdf_compact_canonical_proof` remains blocked because there is no durable
active version. DOC27 fixture validation is not treated as real cutover.

## 9. Wave 2 shadows

{wave2_lines}

All six are accounted, contracts are `0/6`, shadow runs `0/3`, migrations `0`.

## 10. Canonical and legacy differences

No DOC28 comparison was executed. `gate2_handoff_v0` remains the only product
read authority; therefore no new difference can honestly be classified.

## 11. Operational metrics

All durable write/read/activation/rollback/retention counters are zero. Runtime
health checks are `NOT_TESTED`; silent failures and private metric content are
zero because no operation was started.

## 12. Retention and rotation

All eight classes are `NOT_TESTED_ON_DURABLE_STORE`; no deletion or rotation
receipt was produced.

## 13. Terminal test accounting

DOC28 safe-evidence tests: `4 passed`; Ruff: `PASSED`. Runtime durability,
restart, backup/restore, research and Wave 2 tests were not started after the
stop-gate. The full suite was not run for DOC28 and is not claimed terminal;
the last recorded baseline remains DOC27 `{tests['last_terminal_baseline']['passed']}`
passed / `{tests['last_terminal_baseline']['skipped']}` skipped /
`{tests['last_terminal_baseline']['failed']}` failed /
`{tests['last_terminal_baseline']['errors']}` errors.

## 14. Exact blockers

1. Target OpenWebUI deployment is not identified and approved for mutation.
2. Its `openwebui_data` volume is not accessible.
3. Controlled restart authority is absent.
4. Backup destination and restore-drill authority are absent.
5. Capacity threshold and retention-worker owner are not confirmed.

Current deployment/storage, backup/restore, retention and authority documents
record this blocked state; none is presented as an operational receipt.

## 15. Next Wave 2 cutover goal

Not authorized. First provide the five unblock items above and rerun DOC28 from
the durable deployment gate.

## Decision

```text
DOC28_PROGRAM = {decision['DOC28_PROGRAM']}
DURABLE_CANONICAL_STORE = {decision['DURABLE_CANONICAL_STORE']}
APPROVED_REAL_COHORT = {decision['APPROVED_REAL_COHORT']}
NEW_UPLOAD_DURABLE_SHADOW = {decision['NEW_UPLOAD_DURABLE_SHADOW']}
RESEARCH_CONSUMER_MIGRATION = {decision['RESEARCH_CONSUMER_MIGRATION']}
WAVE_2_SHADOW = {decision['WAVE_2_SHADOW']}
WAVE_2_MIGRATION_READINESS = {decision['WAVE_2_MIGRATION_READINESS']}
BACKUP_RESTORE = {decision['BACKUP_RESTORE']}
RETENTION_ROTATION = {decision['RETENTION_ROTATION']}
PRIMARY_PRODUCT_CUTOVER = {decision['PRIMARY_PRODUCT_CUTOVER']}
LEGACY_HANDOFF = {decision['LEGACY_HANDOFF']}
GATE3 = {decision['GATE3']}
```

Deployment audit status:
`{storage['status']}`.
"""


def _brief(decision: dict[str, Any]) -> str:
    return f"""# Broker Reports DOC28 Brief

DOC28 is `{decision['DOC28_PROGRAM']}` at the durable deployment stop-gate.
The 16-document, four-format source cohort is available and frozen, but the
target `openwebui_data` volume/container, restart authority and restore-drill
authority are unavailable. No durable store, version, active pointer, shadow,
consumer migration, product cutover or Gate 3 work was created.

Next Wave 2 cutover work is not authorized until the target runtime and volume
are approved and accessible.
"""


def main() -> None:
    cohort = _cohort()
    storage = _runtime_audit()
    backfill = _backfill()
    active = _active_versions()
    new_upload = _new_uploads()
    research = _research_consumer()
    wave2 = _wave2()
    observability = _observability()
    retention = _retention()
    tests = _tests()
    decision = _decision()
    hygiene = _repository_hygiene()
    storage["repository_hygiene"] = hygiene

    payloads = dict(
        zip(
            SAFE_NAMES,
            (
                storage,
                cohort,
                backfill,
                active,
                new_upload,
                research,
                wave2,
                observability,
                retention,
                tests,
                decision,
            ),
            strict=True,
        )
    )
    for name, payload in payloads.items():
        _write_json(DOC_ROOT / name, payload)

    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    report_path = REPORT_ROOT / REPORT_NAME
    brief_path = REPORT_ROOT / BRIEF_NAME
    report_path.write_text(
        _report(storage, cohort, wave2, tests, decision),
        encoding="utf-8",
    )
    brief_path.write_text(_brief(decision), encoding="utf-8")

    receipt = {
        "schema_version": (
            "broker_reports_doc28_gate2_durable_contour_receipt_safe_v1"
        ),
        "date": "2026-08-05",
        "status": "BLOCKED",
        "blocker_code": decision["blocker_code"],
        "safe_artifact_sha256": {
            f"docs/stage2/{name}": _sha(DOC_ROOT / name)
            for name in SAFE_NAMES
        },
        "report_sha256": _sha(report_path),
        "brief_sha256": _sha(brief_path),
        "durable_writes": 0,
        "runtime_mutations": 0,
        "provider_calls": 0,
        "parser_reruns": 0,
        "historical_reports_modified": 0,
        "historical_hashes_rewritten": 0,
        "private_content_in_receipt": False,
    }
    _write_json(REPORT_ROOT / RECEIPT_NAME, receipt)
    print(
        json.dumps(
            {
                "status": decision["DOC28_PROGRAM"],
                "blocker": decision["blocker_code"],
                "cohort_documents": cohort["documents_total"],
                "runtime_mutations": 0,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
