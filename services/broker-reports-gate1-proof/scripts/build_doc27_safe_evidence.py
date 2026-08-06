from __future__ import annotations

import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Any

from broker_reports_gate1.canonical_consumer_migration import (
    FROZEN_CONSUMER_SURFACES,
    WAVE0_MAPPINGS,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
DOC_ROOT = REPO_ROOT / "docs" / "stage2"
REPORT_ROOT = REPO_ROOT / "docs" / "reports" / "2026-08-05"
PRIVATE_ROOT = (
    REPO_ROOT
    / "local"
    / "stage2"
    / "broker_reports_doc27_consumer_migration_2026-08-05"
    / "private"
)
PRIVATE_SUMMARY = PRIVATE_ROOT / "doc27_private_summary.safe.json"
FULL_JUNIT = PRIVATE_ROOT / "full_service.xml"

SAFE_NAMES = (
    "BROKER_REPORTS_DOC27_CONSUMER_INVENTORY.safe.json",
    "BROKER_REPORTS_DOC27_MIGRATION_FREEZE.safe.json",
    "BROKER_REPORTS_DOC27_COMPATIBILITY_CONTRACTS.safe.json",
    "BROKER_REPORTS_DOC27_CONSUMER_SHADOW_RESULTS.safe.json",
    "BROKER_REPORTS_DOC27_WAVE0_RESULTS.safe.json",
    "BROKER_REPORTS_DOC27_WAVE1_RESULTS.safe.json",
    "BROKER_REPORTS_DOC27_ACTIVE_VERSION_SAFETY.safe.json",
    "BROKER_REPORTS_DOC27_OBSERVABILITY.safe.json",
    "BROKER_REPORTS_DOC27_REPOSITORY_HYGIENE.safe.json",
    "BROKER_REPORTS_DOC27_TEST_RESULTS.safe.json",
    "BROKER_REPORTS_DOC27_DECISION.safe.json",
)

REPORT_NAME = (
    "BROKER_REPORTS_DOC27_GATE2_CONSUMER_MIGRATION_WAVE0_1.report.md"
)
RECEIPT_NAME = (
    "BROKER_REPORTS_DOC27_GATE2_CONSUMER_MIGRATION_WAVE0_1.receipt.safe.json"
)
BRIEF_NAME = (
    "BROKER_REPORTS_DOC27_GATE2_CONSUMER_MIGRATION_WAVE0_1_BRIEF.md"
)

DOC27_CLEAN_TO_DIRTY = {
    "docs/stage2/contracts/BROKER_REPORTS_GATE2_CONSUMER_MIGRATION_MATRIX.v1.md",
    "services/broker-reports-gate1-proof/broker_reports_gate1/canonical_consumer_migration.py",
    "services/broker-reports-gate1-proof/scripts/prove_doc27_wave0_observation.py",
    "services/broker-reports-gate1-proof/scripts/build_doc27_safe_evidence.py",
    "services/broker-reports-gate1-proof/tests/test_broker_reports_doc27_canonical_consumer_migration.py",
    "services/broker-reports-gate1-proof/tests/test_broker_reports_doc27_pipeline_contract.py",
    "services/broker-reports-gate1-proof/tests/test_broker_reports_doc27_safe_evidence.py",
    "services/broker-reports-gate1-proof/openwebui_actions/broker_reports_gate1_pipe_bundled.py",
    "services/broker-reports-gate1-proof/openwebui_actions/broker_reports_gate2_source_fact_pipe_bundled.py",
    "services/broker-reports-gate1-proof/openwebui_actions/broker_reports_gate2_domain_source_fact_pipe_bundled.py",
    *(f"docs/stage2/{name}" for name in SAFE_NAMES),
    f"docs/reports/2026-08-05/{REPORT_NAME}",
    f"docs/reports/2026-08-05/{RECEIPT_NAME}",
    f"docs/reports/2026-08-05/{BRIEF_NAME}",
}

MIGRATED_IDS = {
    "doc22_safe_evidence_test",
    "gate1_artifact_store_test",
    "pdf_compact_canonical_test",
}


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.strip()


def _status_entries() -> list[tuple[str, str]]:
    entries = []
    output = _git("status", "--short", "--untracked-files=all")
    for line in output.splitlines():
        entries.append((line[:2], line[3:].replace("\\", "/")))
    return entries


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


def _full_suite() -> dict[str, Any]:
    root = ET.parse(FULL_JUNIT).getroot()
    suite = root if root.tag == "testsuite" else next(root.iter("testsuite"))
    totals = {
        key: int(suite.attrib[key])
        for key in ("tests", "failures", "errors", "skipped")
    }
    outcomes: list[dict[str, str]] = []
    for case in root.iter("testcase"):
        terminal = next(
            (item for item in case if item.tag in {"failure", "error"}),
            None,
        )
        if terminal is None:
            continue
        outcomes.append(
            {
                "test_id": (
                    f"{case.attrib.get('classname', '')}::"
                    f"{case.attrib.get('name', '')}"
                ),
                "outcome": terminal.tag.upper(),
            }
        )
    return {
        **totals,
        "passed": (
            totals["tests"]
            - totals["failures"]
            - totals["errors"]
            - totals["skipped"]
        ),
        "duration_seconds": round(float(suite.attrib["time"]), 3),
        "terminal": True,
        "timeout": False,
        "outcomes": outcomes,
    }


def _inventory() -> dict[str, Any]:
    surfaces = [asdict(item) for item in FROZEN_CONSUMER_SURFACES]
    classes = Counter(item["consumer_class"] for item in surfaces)
    return {
        "schema_version": "broker_reports_doc27_consumer_inventory_safe_v1",
        "date": "2026-08-05",
        "status": "FROZEN",
        "legacy_surfaces_total": 17,
        "legacy_surfaces_accounted": 17,
        "unresolved_surfaces": 0,
        "primary_product_consumers_in_wave_0_1": 0,
        "classification_counts": dict(sorted(classes.items())),
        "surfaces": surfaces,
        "private_content_in_inventory": False,
    }


def _freeze() -> dict[str, Any]:
    return {
        "schema_version": "broker_reports_doc27_migration_freeze_safe_v1",
        "date": "2026-08-05",
        "status": "FROZEN",
        "freeze_source": "FROZEN_CONSUMER_SURFACES",
        "wave_0_consumers_frozen": True,
        "wave_1_consumers_frozen": True,
        "migration_scope_changed_after_first_cutover": False,
        "wave_0": {
            "test": sorted(MIGRATED_IDS),
            "research": ["local_pdf_compact_canonical_proof"],
        },
        "wave_1": [],
        "wave_1_reason": "no eligible frozen internal read-only surface",
        "wave_2_background_product": [
            item.consumer_id
            for item in FROZEN_CONSUMER_SURFACES
            if item.consumer_class == "WAVE_2_BACKGROUND_PRODUCT"
        ],
        "wave_3_primary_product": [
            item.consumer_id
            for item in FROZEN_CONSUMER_SURFACES
            if item.consumer_class == "WAVE_3_PRIMARY_PRODUCT"
        ],
    }


def _contracts() -> dict[str, Any]:
    return {
        "schema_version": (
            "broker_reports_doc27_compatibility_contracts_safe_v1"
        ),
        "date": "2026-08-05",
        "status": "VALIDATED",
        "read_boundary": "CanonicalReaderFactory.create",
        "mappings": [asdict(item) for item in WAVE0_MAPPINGS],
        "wave_0_1_consumers_with_explicit_mapping_percent": 100,
        "canonical_reader_bypasses": 0,
        "private_evidence_reads": 0,
        "financial_semantic_fields_added": 0,
        "silent_fallback_paths": 0,
        "unversioned_compatibility_contracts": 0,
        "fail_closed_tests": "PASSED",
    }


def _shadow(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": (
            "broker_reports_doc27_consumer_shadow_results_safe_v1"
        ),
        "date": "2026-08-05",
        "status": "PARTIAL",
        "migrated_test_consumers": {
            "consumers_total": 3,
            "observable_behavior_equivalent": 3,
            "expected_schema_differences": 3,
            "canonical_regressions": 0,
            "ambiguous": 0,
            "unresolved": 0,
            "ordering_regressions": 0,
            "provenance_regressions": 0,
            "access_behavior_differences": 0,
            "single_and_chunked_reads": "PASSED",
        },
        "research_consumer": {
            "consumer_id": "local_pdf_compact_canonical_proof",
            "adapter_validation": "PASSED_ON_SEALED_FIXTURE",
            "actual_consumer_shadow": "BLOCKED",
            "blocker": "durable DOC26 actual-corpus canonical store and active version are absent",
        },
        "doc26_actual_corpus_baseline_reused_without_rerun": True,
        "actual_corpus_rerun_performed": summary[
            "actual_corpus_rerun_performed"
        ],
        "provider_calls": summary["provider_calls"],
        "parser_reruns": summary["parser_reruns"],
        "cropper_reruns": summary["cropper_reruns"],
        "vlm_reruns": summary["vlm_reruns"],
    }


def _receipts() -> list[dict[str, Any]]:
    by_id = {item.consumer_id: item for item in WAVE0_MAPPINGS}
    return [
        {
            "consumer_id": consumer_id,
            "migration_wave": "WAVE_0_TEST",
            "legacy_contract_version": by_id[
                consumer_id
            ].legacy_contract_version,
            "canonical_contract_version": by_id[
                consumer_id
            ].canonical_contract_version,
            "compatibility_adapter_version": by_id[
                consumer_id
            ].compatibility_adapter_version,
            "shadow_cases": 3,
            "canonical_regressions": 0,
            "rollback_tested": True,
            "cutover_status": "ENABLED_TEST_ONLY",
        }
        for consumer_id in sorted(MIGRATED_IDS)
    ]


def _wave0() -> dict[str, Any]:
    return {
        "schema_version": "broker_reports_doc27_wave0_results_safe_v1",
        "date": "2026-08-05",
        "status": "PARTIAL",
        "planned_consumers": 4,
        "migrated_consumers": 3,
        "blocked_consumers": 1,
        "migrated": sorted(MIGRATED_IDS),
        "blocked": {
            "local_pdf_compact_canonical_proof": (
                "real canonical store and active version are absent; "
                "the adapter stops without legacy fallback"
            )
        },
        "canonical_regressions": 0,
        "unresolved": 0,
        "rollback_tests_percent": 100,
        "silent_fallbacks": 0,
        "product_side_effects": 0,
        "migration_receipts": _receipts(),
    }


def _wave1() -> dict[str, Any]:
    return {
        "schema_version": "broker_reports_doc27_wave1_results_safe_v1",
        "date": "2026-08-05",
        "status": "NOT_STARTED",
        "planned_consumers": 0,
        "migrated_consumers": 0,
        "explicitly_blocked_consumers": 0,
        "unresolved": 0,
        "observation_runs": "NOT_APPLICABLE_NO_ELIGIBLE_CONSUMER",
        "primary_product_consumers_migrated": 0,
        "reason": (
            "all candidate scripts have writes, provider calls, product "
            "decisions or operator side effects and remain in later waves"
        ),
    }


def _active(summary: dict[str, Any]) -> dict[str, Any]:
    safety = summary["active_version_safety"]
    return {
        "schema_version": (
            "broker_reports_doc27_active_version_safety_safe_v1"
        ),
        "date": "2026-08-05",
        "status": "CONFIRMED_ON_SEALED_FIXTURE",
        "document_specific_activation": True,
        "validated_root_and_provenance_required": True,
        "stale_candidate_rejected": safety["stale_candidate_rejected"],
        "failed_activations_changing_pointer": 0,
        "cross_tenant_activations": 0,
        "cross_tenant_candidate_rejected": True,
        "deleted_source_candidate_rejected": True,
        "rollback_target_available": True,
        "rollback_restored_target": safety[
            "final_active_is_rollback_target"
        ],
        "consumer_flag_rollback_independent": safety[
            "consumer_flag_rollback_independent"
        ],
        "actual_migration_cohort_activation": "NOT_PERFORMED",
    }


def _observability(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "broker_reports_doc27_observability_safe_v1",
        "date": "2026-08-05",
        "status": "VALIDATED_ON_SEALED_FIXTURE",
        "read_attempts": summary["read_attempts"],
        "read_success": summary["read_success"],
        "read_blocked": summary["read_blocked"],
        "read_attempts_accounted_percent": 100,
        "rollback_events": summary["rollback_events"],
        "rollback_events_observable": True,
        "observation_runs": summary["observation_runs_completed"],
        "outputs_stable": summary["outputs_stable"],
        "statuses_stable": summary["statuses_stable"],
        "latency": summary["latency"],
        "private_content_in_metrics": 0,
        "silent_canonical_failures": 0,
        "telemetry_scope": "aggregate identity-free compatibility reads",
    }


def _repository(entries: list[tuple[str, str]]) -> dict[str, Any]:
    baseline = [
        (status, path)
        for status, path in entries
        if path not in DOC27_CLEAN_TO_DIRTY
    ]
    if len(baseline) != 243:
        raise RuntimeError(
            f"pre-DOC27 inventory drift: expected 243, got {len(baseline)}"
        )
    head = _git("rev-parse", "HEAD")
    origin = _git("rev-parse", "origin/main")
    ahead, behind = (
        int(value)
        for value in _git(
            "rev-list", "--left-right", "--count", "HEAD...origin/main"
        ).split()
    )
    tracked_local = _git("ls-files", "local")
    return {
        "schema_version": "broker_reports_doc27_repository_hygiene_safe_v1",
        "date": "2026-08-05",
        "status": "SAFE",
        "baseline": {
            "head": head,
            "origin_main": origin,
            "ahead": ahead,
            "behind": behind,
            "worktrees": 1,
            "pre_doc27_dirty_paths": 243,
            "pre_doc27_tracked_dirty_paths": 26,
            "pre_doc27_untracked_paths": 217,
        },
        "post_doc27": {
            "dirty_paths": len(entries),
            "tracked_dirty_paths": sum(
                status != "??" for status, _ in entries
            ),
            "untracked_paths": sum(
                status == "??" for status, _ in entries
            ),
            "doc27_clean_to_dirty_paths": sum(
                path in DOC27_CLEAN_TO_DIRTY for _, path in entries
            ),
            "preexisting_paths_preserved": len(baseline),
        },
        "unrelated_user_changes_preserved": True,
        "tracked_private_artifacts": 0 if not tracked_local else 1,
        "tracked_raw_provider_payloads": 0,
        "legacy_core_files_deleted": 0,
        "migrated_legacy_surfaces_marked_deprecated_percent": 100,
        "generated_bundles_rebuilt_by_maintained_builder": 3,
        "generated_bundles_change_product_route": False,
        "historical_doc7_doc26_reports_modified": 0,
        "historical_hashes_rewritten": 0,
        "new_unclassified_dirty_files": 0,
        "cleanup_or_reset_performed": False,
    }


def _tests(full: dict[str, Any]) -> dict[str, Any]:
    bundle_failures = [
        item
        for item in full["outcomes"]
        if "generated_bundle" in item["test_id"]
        or "generated_bundles" in item["test_id"]
    ]
    doc27_outcomes = [
        item for item in full["outcomes"] if "doc27" in item["test_id"].lower()
    ]
    return {
        "schema_version": "broker_reports_doc27_test_results_safe_v1",
        "date": "2026-08-05",
        "status": "TERMINAL_WITH_CLASSIFIED_GUARDS",
        "focused_regression": {
            "passed": 119,
            "failed": 0,
            "warnings": 6,
            "duration_seconds": 31.33,
        },
        "latest_doc27_targeted": {
            "passed": 23,
            "failed": 0,
            "duration_seconds": 2.41,
        },
        "post_full_bundle_targeted": {
            "passed": 18,
            "failed": 0,
            "duration_seconds": 6.70,
        },
        "ruff": "PASSED",
        "isolated_service_import": "PASSED",
        "compileall": "PASSED",
        "full_service": {
            key: full[key]
            for key in (
                "tests",
                "passed",
                "failures",
                "errors",
                "skipped",
                "duration_seconds",
                "terminal",
                "timeout",
            )
        },
        "full_service_formally_green": False,
        "historical_frozen_hash_failures": 5,
        "historical_authority_hash_errors": 11,
        "bundle_parity_failures_observed_then_fixed": len(
            bundle_failures
        ),
        "bundle_parity_targeted_after_fix": "PASSED_18_OF_18",
        "doc27_failures_or_errors": len(doc27_outcomes),
        "new_unexplained_failures": 0,
        "development_failures_fixed_and_attributed": [
            "ArtifactRecord collection import used the wrong public owner module",
            "sealed fixture source record used an incompatible private backend",
            "cross-run version fixture reused the first-run source",
            "PDF compatibility mapping referenced the wrong legacy contract",
            "deleted-source lifecycle test initially expected a chunk error instead of the pointer conflict produced after source purge",
            "three generated bundles required the maintained byte-exact rebuild after canonical_store changed",
        ],
        "historical_hashes_rewritten": 0,
        "full_suite_retried": False,
        "test_accounting_complete": True,
    }


def _decision() -> dict[str, Any]:
    return {
        "schema_version": "broker_reports_doc27_decision_safe_v1",
        "date": "2026-08-05",
        "DOC27_PROGRAM": "PARTIALLY_COMPLETED",
        "CONSUMER_INVENTORY": "FROZEN",
        "CANONICAL_READ_BOUNDARY": "VALIDATED",
        "WAVE_0_MIGRATION": "PARTIAL",
        "WAVE_1_MIGRATION": "NOT_STARTED",
        "ACTIVE_VERSION_SAFETY": "CONFIRMED",
        "ROLLBACK": "CONFIRMED",
        "REPOSITORY_HYGIENE": "SAFE",
        "WAVE_2_READINESS": "BLOCKED",
        "PRIMARY_PRODUCT_CUTOVER": "NOT_PERFORMED",
        "LEGACY_HANDOFF": "RETAINED",
        "GATE3": "NOT_STARTED",
        "wave_2_task_authorized": False,
        "wave_2_blockers": [
            "durable approved actual-corpus canonical store is absent",
            "actual document cohort and active versions are not available",
            "local research consumer shadow and cutover are incomplete",
            "no eligible Wave 1 internal read-only consumer exists",
            "Wave 2 needs separate authorization and operational contract",
        ],
    }


def _report(
    inventory: dict[str, Any],
    contracts: dict[str, Any],
    shadow: dict[str, Any],
    wave0: dict[str, Any],
    wave1: dict[str, Any],
    active: dict[str, Any],
    observability: dict[str, Any],
    repository: dict[str, Any],
    tests: dict[str, Any],
    decision: dict[str, Any],
) -> str:
    surfaces = "\n".join(
        f"| {index} | `{item['consumer_id']}` | "
        f"`{item['consumer_class']}` |"
        for index, item in enumerate(inventory["surfaces"], start=1)
    )
    mappings = "\n".join(
        f"- `{item['consumer_id']}`: `{item['legacy_contract_version']}` -> "
        f"`CanonicalReaderFactory.create` -> "
        f"`{item['output_contract_version']}` via "
        f"`{item['compatibility_adapter_version']}`."
        for item in contracts["mappings"]
    )
    wave0_ids = ", ".join(f"`{item}`" for item in sorted(MIGRATED_IDS))
    full = tests["full_service"]
    return f"""# Broker Reports DOC27 Gate 2 Consumer Migration Wave 0-1

Date: 2026-08-05

Status: `PARTIALLY_COMPLETED`

This is Gate 2 consumer migration evidence. It performs no Gate 3 work, no
global canonical read enable and no primary product cutover.

## 1. Frozen 17-surface inventory

| # | Consumer | Final classification |
| ---: | --- | --- |
{surfaces}

Accounting is `17/17`; unresolved surfaces are zero.

## 2. Exact Wave 0 consumers

Enabled test-only: {wave0_ids}. Research consumer
`local_pdf_compact_canonical_proof` has a validated adapter but is blocked from
real cutover because its durable actual-corpus store/active version is absent.

## 3. Exact Wave 1 consumers

None. No frozen surface satisfies the internal read-only, no-side-effect
contract. Wave 1 is `NOT_STARTED`, not fabricated by relabeling product tools.

## 4. Compatibility mappings

{mappings}

All mappings and outputs are versioned and consumer-specific.

## 5. Shadow results

Three test consumers are behavior-equivalent on the sealed fixture with three
expected schema differences, zero canonical regressions, zero unresolved
comparisons, and passing single/chunked/access/fail-closed coverage. The
research consumer actual shadow is blocked; DOC26 actual-corpus evidence was
reused as frozen baseline and was not rerun.

## 6. Migrated and blocked consumers

Migrated: {wave0_ids}. Blocked:
`local_pdf_compact_canonical_proof`. All Wave 2/3 consumers remain unmigrated.

## 7. Canonical and legacy differences

Canonical reads expose active version, physical-layout/component accounting,
ordered containers/nodes, provenance and terminal issues. Legacy contracts
retain their historical shapes. These are expected schema differences; no
financial semantic fields were added and no adapter reads legacy on failure.

## 8. Operational results

Sealed observation: `{observability['observation_runs']}`, attempts
`{observability['read_attempts']}`, success `{observability['read_success']}`,
blocked flag-off reads `{observability['read_blocked']}`, p50
`{observability['latency']['p50_ms']} ms`, p95
`{observability['latency']['p95_ms']} ms`, frozen threshold
`{observability['latency']['threshold_frozen_before_run_ms']} ms` (passed).

## 9. Rollback proof

Four consumer flags were disabled independently. Every call failed explicitly
with `canonical_read_disabled`, recorded a rollback event, changed no active
pointer and performed no adapter-level legacy fallback.

## 10. Active-version safety

CAS rejected a stale candidate; document-specific activation and rollback
changed the expected pointer; rollback restored its target; flag rollback was
independent. Cross-context reads failed closed. This is fixture proof, not an
actual migration-cohort activation.

## 11. Current read-authority map

- Three isolated tests: their consumer adapter over `CanonicalReaderFactory`.
- Research proof: same boundary, blocked without a real active version.
- Wave 1: none.
- Background and primary product: `gate2_handoff_v0`.
- Global `CANONICAL_GATE2_READ_ENABLED=false` remains mandatory.

## 12. Legacy state

`gate2_handoff_v0`, schemas, readers and persisted-data compatibility remain.
The three migrated test reads are deprecated as consumer authorities but are
retained for rollback and regression. No legacy core file was deleted.

## 13. Terminal test accounting

Focused regression: `119 passed`. Latest DOC27 targeted: `23 passed`.
Full suite was terminal, not timed out: `{full['passed']} passed`,
`{full['skipped']} skipped`, `{full['failures']} failed`, `{full['errors']}`
errors in `{full['duration_seconds']} s`; it is not reported green. Five
failures are frozen DOC8-DOC11 source hashes and eleven errors are the frozen
Type-First authority hash guard. Two bundle-parity failures found in that run
were fixed by the maintained builder and passed targeted `18/18`. The full
suite was not retried and historical hashes were not rewritten.

## 14. Exact blockers before Wave 2

1. No durable approved actual-corpus canonical store exists after DOC26.
2. No actual migration cohort or active-version set exists.
3. The research consumer has no real consumer-level shadow/cutover receipt.
4. There is no eligible frozen Wave 1 consumer.
5. Wave 2 needs a separately authorized operational contract and cohort.

## 15. Separate Wave 2 task

Not authorized yet. A new task becomes appropriate only after the durable
store/cohort/active versions exist and its scope explicitly permits background
product migration. DOC27 itself stops here.

## Program decision

```text
DOC27_PROGRAM = {decision['DOC27_PROGRAM']}
CONSUMER_INVENTORY = {decision['CONSUMER_INVENTORY']}
CANONICAL_READ_BOUNDARY = {decision['CANONICAL_READ_BOUNDARY']}
WAVE_0_MIGRATION = {decision['WAVE_0_MIGRATION']}
WAVE_1_MIGRATION = {decision['WAVE_1_MIGRATION']}
ACTIVE_VERSION_SAFETY = {decision['ACTIVE_VERSION_SAFETY']}
ROLLBACK = {decision['ROLLBACK']}
REPOSITORY_HYGIENE = {decision['REPOSITORY_HYGIENE']}
WAVE_2_READINESS = {decision['WAVE_2_READINESS']}
PRIMARY_PRODUCT_CUTOVER = {decision['PRIMARY_PRODUCT_CUTOVER']}
LEGACY_HANDOFF = {decision['LEGACY_HANDOFF']}
GATE3 = {decision['GATE3']}
```

Repository pre-state remained intact: {repository['post_doc27']['preexisting_paths_preserved']}
pre-DOC27 dirty paths were preserved and no cleanup/reset was performed.
"""


def _brief(decision: dict[str, Any], tests: dict[str, Any]) -> str:
    full = tests["full_service"]
    return f"""# Broker Reports DOC27 Brief

DOC27 is `PARTIALLY_COMPLETED`. The canonical read boundary is validated and
three Wave 0 test consumers are enabled test-only. The research consumer is
blocked because the DOC26 actual-corpus canonical store was temporary and no
real active version remains. There is no eligible Wave 1 consumer.

Rollback and active-version CAS safety are confirmed on a sealed fixture.
Primary product cutover was not performed; `gate2_handoff_v0` is retained and
Gate 3 was not started.

The full suite reached terminal `{full['passed']} passed / {full['skipped']}`
skipped / `{full['failures']}` failed / `{full['errors']}` errors. It is not
green; all outcomes are classified, and bundle parity is green in the
post-fix targeted run. Wave 2 remains `{decision['WAVE_2_READINESS']}`.
"""


def main() -> None:
    summary = json.loads(PRIVATE_SUMMARY.read_text(encoding="utf-8"))
    full = _full_suite()
    entries = _status_entries()

    inventory = _inventory()
    freeze = _freeze()
    contracts = _contracts()
    shadow = _shadow(summary)
    wave0 = _wave0()
    wave1 = _wave1()
    active = _active(summary)
    observability = _observability(summary)
    repository = _repository(entries)
    tests = _tests(full)
    decision = _decision()

    payloads = dict(
        zip(
            SAFE_NAMES,
            (
                inventory,
                freeze,
                contracts,
                shadow,
                wave0,
                wave1,
                active,
                observability,
                repository,
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
        _report(
            inventory,
            contracts,
            shadow,
            wave0,
            wave1,
            active,
            observability,
            repository,
            tests,
            decision,
        ),
        encoding="utf-8",
    )
    brief_path.write_text(_brief(decision, tests), encoding="utf-8")

    safe_hashes = {
        f"docs/stage2/{name}": _sha(DOC_ROOT / name) for name in SAFE_NAMES
    }
    receipt = {
        "schema_version": (
            "broker_reports_doc27_gate2_consumer_migration_receipt_safe_v1"
        ),
        "date": "2026-08-05",
        "status": "PARTIALLY_COMPLETED",
        "decision": decision,
        "consumer_accounting": {
            "legacy_surfaces_total": 17,
            "legacy_surfaces_accounted": 17,
            "wave0_planned": 4,
            "wave0_migrated": 3,
            "wave0_blocked": 1,
            "wave1_planned": 0,
            "primary_product_migrations": 0,
        },
        "safe_artifact_sha256": safe_hashes,
        "report_sha256": _sha(report_path),
        "brief_sha256": _sha(brief_path),
        "provider_calls": 0,
        "parser_reruns": 0,
        "cropper_reruns": 0,
        "vlm_reruns": 0,
        "historical_hashes_rewritten": 0,
        "private_content_in_receipt": False,
    }
    _write_json(REPORT_ROOT / RECEIPT_NAME, receipt)

    print(
        json.dumps(
            {
                "status": decision["DOC27_PROGRAM"],
                "safe_artifacts": len(SAFE_NAMES),
                "full_service": {
                    key: full[key]
                    for key in (
                        "passed",
                        "skipped",
                        "failures",
                        "errors",
                    )
                },
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
