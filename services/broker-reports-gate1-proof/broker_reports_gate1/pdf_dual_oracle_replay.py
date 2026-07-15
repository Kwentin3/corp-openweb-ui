from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from typing import Any

from .pdf_dual_oracle_contracts import (
    PdfDualOracleContractError,
    PdfDualOracleContractFactory,
)
from .pdf_hybrid_budget import PdfHybridBudgetFactory
from .pdf_hybrid_contracts import sha256_json, validate_binding_output_shape
from .pdf_hybrid_windows import PdfHybridWindowError, PdfHybridWindowFactory


PDF_DUAL_ORACLE_LEGACY_REPLAY_SCHEMA = (
    "broker_reports_pdf_dual_oracle_legacy_grid_replay_v1"
)
PDF_DUAL_ORACLE_LEGACY_REPLAY_POLICY = (
    "pdf_dual_oracle_legacy_grid_replay_policy_v1"
)
LEGACY_GRID_STAGE = "grid"
LEGACY_FREE_ARM = "free_csv_challenge"
LEGACY_PACKAGE_ARMS = ("verbose_json", "compact_json", "candidate_csv")
LEGACY_VERBOSE_ARM = "verbose_json"
LEGACY_FULL_TABLE_PACKAGE_ID = "full-table-crop"
_FACTORY_TOKEN = object()
FACTORY_REQUIRED = (
    "PdfDualOracleReplayFactory.create is the only legacy-journal replay entrypoint; "
    "joined attempts must route through PdfHybridWindowFactory"
)
FORBIDDEN = (
    "Replay must not read references, call providers, trust journal ordering, or join "
    "unchecked package and candidate identities; repeat history must not be rewritten "
    "or lose a prior conflict"
)


class PdfDualOracleReplayError(ValueError):
    def __init__(self, code: str, subject: str = "") -> None:
        self.code = code
        self.subject = subject
        super().__init__(code if not subject else f"{code}:{subject}")


@dataclass(frozen=True)
class PdfDualOracleReplayConfig:
    policy_version: str = PDF_DUAL_ORACLE_LEGACY_REPLAY_POLICY
    expected_journal_entry_count: int = 80
    maximum_attempt_number: int = 2


class PdfDualOracleReplayFactory:
    def __init__(self, config: PdfDualOracleReplayConfig | None = None) -> None:
        self.config = config or PdfDualOracleReplayConfig()

    def create(self) -> "PdfDualOracleReplayRuntime":
        if self.config.policy_version != PDF_DUAL_ORACLE_LEGACY_REPLAY_POLICY:
            raise PdfDualOracleReplayError("pdf_dual_oracle_replay_policy_invalid")
        if self.config.expected_journal_entry_count != 80:
            raise PdfDualOracleReplayError(
                "pdf_dual_oracle_replay_legacy_entry_count_invalid"
            )
        if self.config.maximum_attempt_number != 2:
            raise PdfDualOracleReplayError(
                "pdf_dual_oracle_replay_attempt_policy_invalid"
            )
        window_runtime = PdfHybridWindowFactory().create(
            budget=PdfHybridBudgetFactory().create()
        )
        return PdfDualOracleReplayRuntime(
            self.config,
            window_runtime,
            _factory_token=_FACTORY_TOKEN,
        )


class PdfDualOracleReplayRuntime:
    def __init__(
        self,
        config: PdfDualOracleReplayConfig,
        window_runtime: Any,
        *,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise PdfDualOracleReplayError(
                "pdf_dual_oracle_replay_factory_required"
            )
        self.config = config
        self._window_runtime = window_runtime
        self._contracts = PdfDualOracleContractFactory().create()

    def build_expected_manifest(
        self,
        *,
        package_ids_by_table: dict[str, list[str]],
        attempt_numbers_by_table: dict[str, list[int]],
    ) -> list[dict[str, Any]]:
        package_map = _object_map(
            package_ids_by_table,
            "pdf_dual_oracle_replay_package_manifest_not_object",
        )
        attempt_map = _object_map(
            attempt_numbers_by_table,
            "pdf_dual_oracle_replay_attempt_manifest_not_object",
        )
        if not package_map or set(package_map) != set(attempt_map):
            raise PdfDualOracleReplayError(
                "pdf_dual_oracle_replay_manifest_table_set_invalid"
            )
        manifest: list[dict[str, Any]] = []
        package_ids_seen: set[str] = set()
        for table_key, raw_package_ids in package_map.items():
            package_ids = _string_list(
                raw_package_ids,
                "pdf_dual_oracle_replay_manifest_package_ids_invalid",
                subject=table_key,
            )
            if not package_ids or len(package_ids) != len(set(package_ids)):
                raise PdfDualOracleReplayError(
                    "pdf_dual_oracle_replay_manifest_package_ids_invalid", table_key
                )
            if package_ids_seen & set(package_ids):
                raise PdfDualOracleReplayError(
                    "pdf_dual_oracle_replay_manifest_package_id_reused", table_key
                )
            package_ids_seen.update(package_ids)
            attempts = _attempt_numbers(
                attempt_map[table_key],
                maximum=self.config.maximum_attempt_number,
                subject=table_key,
            )
            for attempt in attempts:
                manifest.append(
                    _job_identity(
                        arm=LEGACY_FREE_ARM,
                        table_key=table_key,
                        package_id=LEGACY_FULL_TABLE_PACKAGE_ID,
                        attempt_number=attempt,
                    )
                )
            for package_id in package_ids:
                for arm in LEGACY_PACKAGE_ARMS:
                    for attempt in attempts:
                        manifest.append(
                            _job_identity(
                                arm=arm,
                                table_key=table_key,
                                package_id=package_id,
                                attempt_number=attempt,
                            )
                        )
        if len(manifest) != self.config.expected_journal_entry_count:
            raise PdfDualOracleReplayError(
                "pdf_dual_oracle_replay_manifest_entry_count_invalid",
                str(len(manifest)),
            )
        return manifest

    def replay(
        self,
        *,
        journal: Any,
        expected_manifest: Any,
        compact_ledgers_by_table: Any,
        plans_by_table: Any,
        packages_by_table: Any,
        repeat_scopes_by_table: Any | None = None,
        prior_repeat_histories_by_table: Any | None = None,
        evidence_revisions_by_table: Any | None = None,
    ) -> dict[str, Any]:
        manifest = self._validate_manifest(expected_manifest)
        entries_by_key = self._validate_journal(journal, manifest)
        table_inputs = self._validate_table_inputs(
            manifest=manifest,
            compact_ledgers_by_table=compact_ledgers_by_table,
            plans_by_table=plans_by_table,
            packages_by_table=packages_by_table,
        )
        private_joined_attempts: dict[str, list[dict[str, Any]]] = {}
        table_summaries: list[dict[str, Any]] = []
        repeat_history_authorities: dict[str, dict[str, Any]] = {}
        verbose_entry_count = 0
        repeat_inputs_supplied = any(
            value is not None
            for value in (
                repeat_scopes_by_table,
                prior_repeat_histories_by_table,
                evidence_revisions_by_table,
            )
        )
        if repeat_inputs_supplied and (
            repeat_scopes_by_table is None or evidence_revisions_by_table is None
        ):
            raise PdfDualOracleReplayError(
                "pdf_dual_oracle_replay_repeat_history_inputs_incomplete"
            )
        repeat_scopes = (
            _object_map(
                repeat_scopes_by_table,
                "pdf_dual_oracle_replay_repeat_scopes_not_object",
            )
            if repeat_inputs_supplied
            else {}
        )
        prior_histories = (
            _object_map(
                prior_repeat_histories_by_table or {},
                "pdf_dual_oracle_replay_prior_histories_not_object",
            )
            if repeat_inputs_supplied
            else {}
        )
        evidence_revisions = (
            _object_map(
                evidence_revisions_by_table,
                "pdf_dual_oracle_replay_evidence_revisions_not_object",
            )
            if repeat_inputs_supplied
            else {}
        )
        if repeat_inputs_supplied:
            expected_tables = set(table_inputs)
            if (
                set(repeat_scopes) != expected_tables
                or set(evidence_revisions) != expected_tables
                or set(prior_histories) - expected_tables
            ):
                raise PdfDualOracleReplayError(
                    "pdf_dual_oracle_replay_repeat_history_table_set_mismatch"
                )
        for table_key, state in table_inputs.items():
            attempts = state["attempt_numbers"]
            joined_attempts: list[dict[str, Any]] = []
            safe_attempts: list[dict[str, Any]] = []
            for attempt_number in attempts:
                bindings: list[dict[str, Any]] = []
                token_totals = {
                    "provider_counted_input_tokens": 0,
                    "provider_actual_input_tokens": 0,
                    "provider_output_tokens": 0,
                    "visible_output_bytes": 0,
                }
                for package in state["ordered_packages"]:
                    job_key = _job_identity(
                        arm=LEGACY_VERBOSE_ARM,
                        table_key=table_key,
                        package_id=str(package["package_id"]),
                        attempt_number=attempt_number,
                    )["job_key"]
                    binding, metrics = self._validate_verbose_entry(
                        entry=entries_by_key[job_key],
                        package=package,
                        window=_object(package.get("window")),
                    )
                    bindings.append(binding)
                    verbose_entry_count += 1
                    for key in token_totals:
                        token_totals[key] += metrics[key]
                try:
                    logical_evidence, joined_binding = self._window_runtime.join(
                        compact_ledger=state["compact_ledger"],
                        plan=state["plan"],
                        packages=state["ordered_packages"],
                        bindings=bindings,
                    )
                except (PdfHybridWindowError, KeyError, TypeError, ValueError) as exc:
                    code = getattr(exc, "code", type(exc).__name__)
                    raise PdfDualOracleReplayError(
                        "pdf_dual_oracle_replay_window_join_failed",
                        f"{table_key}:a{attempt_number}:{code}",
                    ) from exc
                topology_checksum = _topology_checksum(joined_binding)
                candidate_grid_checksum = _candidate_grid_checksum(joined_binding)
                joined_attempts.append(
                    {
                        "attempt_number": attempt_number,
                        "logical_evidence": logical_evidence,
                        "binding": joined_binding,
                        "topology_checksum": topology_checksum,
                        "candidate_grid_checksum": candidate_grid_checksum,
                    }
                )
                safe_attempts.append(
                    {
                        "attempt_number": attempt_number,
                        "topology_checksum": topology_checksum,
                        "candidate_grid_checksum": candidate_grid_checksum,
                        **token_totals,
                    }
                )
            topology_checksums = [item["topology_checksum"] for item in safe_attempts]
            distinct_topologies = sorted(set(topology_checksums))
            repeat_required = len(attempts) > 1
            ever_conflicted = len(distinct_topologies) > 1
            private_joined_attempts[table_key] = joined_attempts
            if repeat_inputs_supplied:
                revision = evidence_revisions.get(table_key)
                if not isinstance(revision, str) or not revision:
                    raise PdfDualOracleReplayError(
                        "pdf_dual_oracle_replay_evidence_revision_invalid",
                        table_key,
                    )
                try:
                    empty_history = self._contracts.create_repeat_history(
                        scope=repeat_scopes[table_key]
                    )
                    history = (
                        copy.deepcopy(prior_histories[table_key])
                        if table_key in prior_histories
                        else empty_history
                    )
                    if history.get("scope") != empty_history.get("scope"):
                        raise PdfDualOracleReplayError(
                            "pdf_dual_oracle_replay_repeat_history_scope_mismatch",
                            table_key,
                        )
                    for attempt in safe_attempts:
                        attempt_number = int(attempt["attempt_number"])
                        attempt_identity = {
                            "table_key": table_key,
                            "attempt_number": attempt_number,
                            "package_attempt_ids": sorted(
                                str(
                                    _object(
                                        entries_by_key[
                                            _job_identity(
                                                arm=LEGACY_VERBOSE_ARM,
                                                table_key=table_key,
                                                package_id=str(package["package_id"]),
                                                attempt_number=attempt_number,
                                            )["job_key"]
                                        ].get("safe")
                                    ).get("attempt_id")
                                    or ""
                                )
                                for package in state["ordered_packages"]
                            ),
                        }
                        attempt_id = "pdfduallegacyattempt_" + hashlib.sha256(
                            json.dumps(
                                attempt_identity,
                                ensure_ascii=False,
                                sort_keys=True,
                                separators=(",", ":"),
                            ).encode("utf-8")
                        ).hexdigest()[:24]
                        history = self._contracts.append_repeat_history_event(
                            history=history,
                            attempt_id=attempt_id,
                            attempt_number=attempt_number,
                            evidence_revision=revision,
                            canonical_grid_checksum=str(
                                attempt.get("candidate_grid_checksum") or ""
                            )
                            or None,
                            topology_checksum=str(
                                attempt.get("topology_checksum") or ""
                            )
                            or None,
                            terminal_status="human_review_required",
                            expected_prior_history_checksum=str(
                                history.get("history_checksum") or ""
                            ),
                        )
                    repeat_history_authorities[table_key] = history
                except PdfDualOracleContractError as exc:
                    raise PdfDualOracleReplayError(exc.code, table_key) from exc
            table_summaries.append(
                {
                    "table_key": table_key,
                    "window_count": len(state["ordered_packages"]),
                    "attempt_count": len(attempts),
                    "attempts": safe_attempts,
                    "repeatability": {
                        "required": repeat_required,
                        "pass": (not ever_conflicted) if repeat_required else None,
                        "ever_conflicted": ever_conflicted,
                        "distinct_topology_count": len(distinct_topologies),
                        "status": (
                            "conflict_preserved"
                            if ever_conflicted
                            else "stable"
                            if repeat_required
                            else "not_repeated"
                        ),
                    },
                }
            )
        safe_summary = {
            "schema_version": PDF_DUAL_ORACLE_LEGACY_REPLAY_SCHEMA,
            "policy_version": self.config.policy_version,
            "journal_entry_count": len(entries_by_key),
            "manifest_entry_count": len(manifest),
            "verbose_entry_count": verbose_entry_count,
            "job_key_set_exact": True,
            "journal_order_trusted": False,
            "plan_window_order_used": True,
            "private_text_reparsed": True,
            "private_binding_exact_match_required": True,
            "provider_calls_performed": 0,
            "reference_access_performed": False,
            "expected_manifest_checksum": sha256_json(manifest),
            "repeat_history_authority_status": (
                "sealed_append_only" if repeat_inputs_supplied else "not_supplied"
            ),
            "repeat_history_authorities": repeat_history_authorities,
            "table_summaries": table_summaries,
        }
        return {
            "safe_summary": safe_summary,
            "private_joined_attempts": private_joined_attempts,
        }

    def _validate_manifest(self, value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            raise PdfDualOracleReplayError("pdf_dual_oracle_replay_manifest_not_list")
        if len(value) != self.config.expected_journal_entry_count:
            raise PdfDualOracleReplayError(
                "pdf_dual_oracle_replay_manifest_entry_count_invalid", str(len(value))
            )
        manifest: list[dict[str, Any]] = []
        job_keys: set[str] = set()
        for index, raw in enumerate(value):
            if not isinstance(raw, dict):
                raise PdfDualOracleReplayError(
                    "pdf_dual_oracle_replay_manifest_entry_not_object", str(index)
                )
            if set(raw) != {
                "job_key",
                "task_id",
                "stage",
                "arm",
                "table_key",
                "package_id",
                "attempt_number",
            }:
                raise PdfDualOracleReplayError(
                    "pdf_dual_oracle_replay_manifest_entry_keys_invalid", str(index)
                )
            expected = _job_identity_from_mapping(raw, subject=f"manifest:{index}")
            if raw != expected:
                raise PdfDualOracleReplayError(
                    "pdf_dual_oracle_replay_manifest_identity_mismatch", str(index)
                )
            job_key = expected["job_key"]
            if job_key in job_keys:
                raise PdfDualOracleReplayError(
                    "pdf_dual_oracle_replay_manifest_job_key_duplicate", job_key
                )
            job_keys.add(job_key)
            manifest.append(copy.deepcopy(expected))
        return manifest

    def _validate_journal(
        self, value: Any, manifest: list[dict[str, Any]]
    ) -> dict[str, dict[str, Any]]:
        if not isinstance(value, list):
            raise PdfDualOracleReplayError("pdf_dual_oracle_replay_journal_not_list")
        if len(value) != self.config.expected_journal_entry_count:
            raise PdfDualOracleReplayError(
                "pdf_dual_oracle_replay_journal_entry_count_invalid", str(len(value))
            )
        expected_by_key = {item["job_key"]: item for item in manifest}
        entries_by_key: dict[str, dict[str, Any]] = {}
        for index, entry in enumerate(value):
            if not isinstance(entry, dict):
                raise PdfDualOracleReplayError(
                    "pdf_dual_oracle_replay_journal_entry_not_object", str(index)
                )
            if set(entry) != {"private", "safe"}:
                raise PdfDualOracleReplayError(
                    "pdf_dual_oracle_replay_journal_entry_keys_invalid", str(index)
                )
            safe = entry.get("safe")
            private = entry.get("private")
            if not isinstance(safe, dict) or not isinstance(private, dict):
                raise PdfDualOracleReplayError(
                    "pdf_dual_oracle_replay_journal_payload_not_object", str(index)
                )
            job_key = safe.get("job_key")
            if not isinstance(job_key, str) or not job_key:
                raise PdfDualOracleReplayError(
                    "pdf_dual_oracle_replay_journal_job_key_invalid", str(index)
                )
            if job_key in entries_by_key:
                raise PdfDualOracleReplayError(
                    "pdf_dual_oracle_replay_journal_job_key_duplicate", job_key
                )
            expected = expected_by_key.get(job_key)
            if expected is None:
                raise PdfDualOracleReplayError(
                    "pdf_dual_oracle_replay_journal_job_unknown", job_key
                )
            actual = _job_identity_from_mapping(safe, subject=f"journal:{index}")
            if actual != expected:
                raise PdfDualOracleReplayError(
                    "pdf_dual_oracle_replay_journal_identity_mismatch", job_key
                )
            entries_by_key[job_key] = entry
        if set(entries_by_key) != set(expected_by_key):
            raise PdfDualOracleReplayError(
                "pdf_dual_oracle_replay_journal_job_set_mismatch"
            )
        return entries_by_key

    def _validate_table_inputs(
        self,
        *,
        manifest: list[dict[str, Any]],
        compact_ledgers_by_table: Any,
        plans_by_table: Any,
        packages_by_table: Any,
    ) -> dict[str, dict[str, Any]]:
        ledgers = _object_map(
            compact_ledgers_by_table, "pdf_dual_oracle_replay_ledgers_not_object"
        )
        plans = _object_map(plans_by_table, "pdf_dual_oracle_replay_plans_not_object")
        packages = _object_map(
            packages_by_table, "pdf_dual_oracle_replay_packages_not_object"
        )
        manifest_tables = list(dict.fromkeys(str(item["table_key"]) for item in manifest))
        expected_tables = set(manifest_tables)
        if (
            set(ledgers) != expected_tables
            or set(plans) != expected_tables
            or set(packages) != expected_tables
        ):
            raise PdfDualOracleReplayError(
                "pdf_dual_oracle_replay_table_input_set_mismatch"
            )
        states: dict[str, dict[str, Any]] = {}
        all_package_ids: set[str] = set()
        for table_key in manifest_tables:
            ledger = ledgers[table_key]
            plan = plans[table_key]
            raw_packages = packages[table_key]
            if not isinstance(ledger, dict) or not isinstance(plan, dict):
                raise PdfDualOracleReplayError(
                    "pdf_dual_oracle_replay_table_contract_not_object", table_key
                )
            if not isinstance(raw_packages, list) or not all(
                isinstance(item, dict) for item in raw_packages
            ):
                raise PdfDualOracleReplayError(
                    "pdf_dual_oracle_replay_table_packages_invalid", table_key
                )
            windows = plan.get("windows")
            if not isinstance(windows, list) or not windows or not all(
                isinstance(item, dict) for item in windows
            ):
                raise PdfDualOracleReplayError(
                    "pdf_dual_oracle_replay_plan_windows_invalid", table_key
                )
            if len(raw_packages) != len(windows):
                raise PdfDualOracleReplayError(
                    "pdf_dual_oracle_replay_package_window_count_mismatch", table_key
                )
            self._validate_plan(
                table_key=table_key,
                compact_ledger=ledger,
                plan=plan,
                windows=windows,
            )
            packages_by_window: dict[str, dict[str, Any]] = {}
            packages_by_id: dict[str, dict[str, Any]] = {}
            for package in raw_packages:
                package_id = _nonempty_string(
                    package.get("package_id"),
                    "pdf_dual_oracle_replay_package_id_invalid",
                    subject=table_key,
                )
                window = package.get("window")
                if not isinstance(window, dict):
                    raise PdfDualOracleReplayError(
                        "pdf_dual_oracle_replay_package_window_invalid", package_id
                    )
                window_id = _nonempty_string(
                    window.get("window_id"),
                    "pdf_dual_oracle_replay_package_window_invalid",
                    subject=package_id,
                )
                if (
                    package_id in packages_by_id
                    or window_id in packages_by_window
                    or package_id in all_package_ids
                ):
                    raise PdfDualOracleReplayError(
                        "pdf_dual_oracle_replay_package_identity_duplicate", package_id
                    )
                packages_by_id[package_id] = package
                packages_by_window[window_id] = package
                all_package_ids.add(package_id)
            ordered_packages: list[dict[str, Any]] = []
            for window in windows:
                window_id = str(window.get("window_id") or "")
                package = packages_by_window.get(window_id)
                if package is None:
                    raise PdfDualOracleReplayError(
                        "pdf_dual_oracle_replay_window_package_missing",
                        f"{table_key}:{window_id}",
                    )
                self._validate_package(
                    table_key=table_key,
                    compact_ledger=ledger,
                    plan=plan,
                    expected_window=window,
                    package=package,
                )
                ordered_packages.append(package)
            attempt_numbers = self._validate_manifest_matrix(
                table_key=table_key,
                manifest=manifest,
                package_ids=[str(item["package_id"]) for item in ordered_packages],
            )
            states[table_key] = {
                "compact_ledger": ledger,
                "plan": plan,
                "ordered_packages": ordered_packages,
                "attempt_numbers": attempt_numbers,
            }
        return states

    def _validate_plan(
        self,
        *,
        table_key: str,
        compact_ledger: dict[str, Any],
        plan: dict[str, Any],
        windows: list[dict[str, Any]],
    ) -> None:
        if plan.get("ledger_id") != compact_ledger.get("ledger_id"):
            raise PdfDualOracleReplayError(
                "pdf_dual_oracle_replay_plan_ledger_mismatch", table_key
            )
        candidate_order = _string_list(
            compact_ledger.get("candidate_order"),
            "pdf_dual_oracle_replay_ledger_candidate_order_invalid",
            subject=table_key,
        )
        dictionary = compact_ledger.get("private_candidate_dictionary")
        if not isinstance(dictionary, dict) or list(dictionary) != candidate_order:
            raise PdfDualOracleReplayError(
                "pdf_dual_oracle_replay_ledger_dictionary_invalid", table_key
            )
        if compact_ledger.get("candidate_dictionary_hash") != sha256_json(dictionary):
            raise PdfDualOracleReplayError(
                "pdf_dual_oracle_replay_ledger_dictionary_hash_mismatch", table_key
            )
        assigned: list[str] = []
        expected_row_start = 1
        for expected_index, window in enumerate(windows, start=1):
            row_start = _positive_integer(window.get("row_start"))
            row_end = _positive_integer(window.get("row_end"))
            row_count = _positive_integer(window.get("row_count"))
            if (
                window.get("window_index") != expected_index
                or row_start != expected_row_start
                or row_end < row_start
                or row_count != row_end - row_start + 1
                or window.get("column_start") != 1
                or window.get("column_end") != plan.get("column_count")
                or window.get("column_count") != plan.get("column_count")
                or window.get("column_split_performed") is not False
                or window.get("silent_truncation_performed") is not False
            ):
                raise PdfDualOracleReplayError(
                    "pdf_dual_oracle_replay_plan_window_order_invalid",
                    f"{table_key}:{expected_index}",
                )
            ids = _string_list(
                window.get("candidate_ids"),
                "pdf_dual_oracle_replay_window_candidate_ids_invalid",
                subject=f"{table_key}:{expected_index}",
            )
            if len(ids) != len(set(ids)) or window.get("candidate_count") != len(ids):
                raise PdfDualOracleReplayError(
                    "pdf_dual_oracle_replay_window_candidate_ids_invalid",
                    f"{table_key}:{expected_index}",
                )
            assigned.extend(ids)
            expected_row_start = row_end + 1
        if (
            assigned != candidate_order
            or len(assigned) != len(set(assigned))
            or plan.get("candidate_count") != len(assigned)
            or plan.get("row_count") != expected_row_start - 1
            or plan.get("candidate_ids_assigned") != len(assigned)
            or plan.get("candidate_ids_unique") != len(set(assigned))
            or plan.get("exactly_once_candidate_ownership") is not True
            or plan.get("column_split_performed") is not False
            or plan.get("silent_truncation_performed") is not False
        ):
            raise PdfDualOracleReplayError(
                "pdf_dual_oracle_replay_plan_candidate_ownership_invalid", table_key
            )

    def _validate_package(
        self,
        *,
        table_key: str,
        compact_ledger: dict[str, Any],
        plan: dict[str, Any],
        expected_window: dict[str, Any],
        package: dict[str, Any],
    ) -> None:
        package_id = str(package.get("package_id") or "")
        actual_window = _object(package.get("window"))
        compared_window_keys = {
            "window_id",
            "window_index",
            "row_start",
            "row_end",
            "row_count",
            "column_start",
            "column_end",
            "column_count",
            "candidate_ids",
            "candidate_count",
            "column_split_performed",
            "silent_truncation_performed",
        }
        if any(
            actual_window.get(key) != expected_window.get(key)
            for key in compared_window_keys
        ):
            raise PdfDualOracleReplayError(
                "pdf_dual_oracle_replay_package_window_mismatch", package_id
            )
        crop = package.get("crop_identity")
        private_dictionary = package.get("private_candidate_dictionary")
        model_facing = package.get("model_facing")
        if (
            package.get("logical_table_id") != plan.get("logical_table_id")
            or package.get("ledger_id") != compact_ledger.get("ledger_id")
            or not isinstance(crop, dict)
            or not isinstance(private_dictionary, dict)
            or not isinstance(model_facing, dict)
        ):
            raise PdfDualOracleReplayError(
                "pdf_dual_oracle_replay_package_contract_invalid", package_id
            )
        crop_sha256 = crop.get("crop_sha256")
        dictionary_hash = package.get("candidate_dictionary_hash")
        expected_ids = [str(item) for item in expected_window.get("candidate_ids") or []]
        identity = model_facing.get("i")
        records = model_facing.get("c")
        if (
            not isinstance(crop_sha256, str)
            or not crop_sha256
            or not isinstance(dictionary_hash, str)
            or not dictionary_hash
            or list(private_dictionary) != expected_ids
            or sha256_json(private_dictionary) != dictionary_hash
            or not isinstance(identity, dict)
            or identity
            != {
                "package_id": package_id,
                "crop_sha256": crop_sha256,
                "candidate_dictionary_hash": dictionary_hash,
            }
            or not isinstance(records, list)
            or not all(isinstance(item, list) and item for item in records)
            or [str(item[0]) for item in records] != expected_ids
        ):
            raise PdfDualOracleReplayError(
                "pdf_dual_oracle_replay_package_candidate_ownership_invalid",
                f"{table_key}:{package_id}",
            )

    def _validate_manifest_matrix(
        self,
        *,
        table_key: str,
        manifest: list[dict[str, Any]],
        package_ids: list[str],
    ) -> list[int]:
        table_items = [item for item in manifest if item["table_key"] == table_key]
        attempts = sorted({int(item["attempt_number"]) for item in table_items})
        attempts = _attempt_numbers(
            attempts, maximum=self.config.maximum_attempt_number, subject=table_key
        )
        expected = []
        for attempt in attempts:
            expected.append(
                _job_identity(
                    arm=LEGACY_FREE_ARM,
                    table_key=table_key,
                    package_id=LEGACY_FULL_TABLE_PACKAGE_ID,
                    attempt_number=attempt,
                )
            )
        for package_id in package_ids:
            for arm in LEGACY_PACKAGE_ARMS:
                for attempt in attempts:
                    expected.append(
                        _job_identity(
                            arm=arm,
                            table_key=table_key,
                            package_id=package_id,
                            attempt_number=attempt,
                        )
                    )
        if {item["job_key"] for item in table_items} != {
            item["job_key"] for item in expected
        }:
            raise PdfDualOracleReplayError(
                "pdf_dual_oracle_replay_manifest_table_matrix_incomplete", table_key
            )
        return attempts

    def _validate_verbose_entry(
        self,
        *,
        entry: dict[str, Any],
        package: dict[str, Any],
        window: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, int]]:
        safe = _object(entry.get("safe"))
        private = _object(entry.get("private"))
        package_id = str(package.get("package_id") or "")
        attempt_number = int(safe.get("attempt_number") or 0)
        provider_task_id = "pdfhybridtask_" + package_id.removeprefix(
            "pdfhybridpkg_"
        )
        if (
            safe.get("artifact_status") != "accepted"
            or safe.get("finish_reason") != "STOP"
            or safe.get("validation_error") is not None
            or safe.get("terminal_failure_class") is not None
            or safe.get("hidden_retry") is not False
            or safe.get("provider_failover") is not False
            or safe.get("attempt_id") != f"{provider_task_id}_a{attempt_number}"
            or safe.get("candidate_coverage_ratio") != 1.0
        ):
            raise PdfDualOracleReplayError(
                "pdf_dual_oracle_replay_verbose_entry_not_accepted",
                str(safe.get("job_key") or package_id),
            )
        raw_text = private.get("text")
        binding = private.get("binding")
        if not isinstance(raw_text, str) or not isinstance(binding, dict):
            raise PdfDualOracleReplayError(
                "pdf_dual_oracle_replay_verbose_private_invalid",
                str(safe.get("job_key") or package_id),
            )
        parsed = _strict_json_object(raw_text, subject=str(safe.get("job_key") or ""))
        if parsed != binding:
            raise PdfDualOracleReplayError(
                "pdf_dual_oracle_replay_text_binding_mismatch",
                str(safe.get("job_key") or package_id),
            )
        shape_errors = validate_binding_output_shape(binding)
        if shape_errors:
            raise PdfDualOracleReplayError(
                "pdf_dual_oracle_replay_binding_shape_invalid",
                f"{package_id}:{shape_errors[0]}",
            )
        crop = _object(package.get("crop_identity"))
        if (
            binding.get("decision") != "bound"
            or binding.get("package_id") != package_id
            or binding.get("crop_sha256") != crop.get("crop_sha256")
            or binding.get("candidate_dictionary_hash")
            != package.get("candidate_dictionary_hash")
            or binding.get("row_count") != window.get("row_count")
            or binding.get("column_count") != window.get("column_count")
        ):
            raise PdfDualOracleReplayError(
                "pdf_dual_oracle_replay_binding_package_identity_mismatch", package_id
            )
        expected_ids = [str(item) for item in window.get("candidate_ids") or []]
        try:
            used_ids = [
                candidate_id
                for row in binding["rows"]
                for cell in row["cells"]
                for candidate_id in cell
            ]
        except (KeyError, TypeError) as exc:
            raise PdfDualOracleReplayError(
                "pdf_dual_oracle_replay_binding_candidate_ids_invalid", package_id
            ) from exc
        if (
            len(used_ids) != len(set(used_ids))
            or len(used_ids) != len(expected_ids)
            or set(used_ids) != set(expected_ids)
        ):
            raise PdfDualOracleReplayError(
                "pdf_dual_oracle_replay_binding_candidate_ownership_mismatch",
                package_id,
            )
        text_bytes = raw_text.encode("utf-8")
        if (
            safe.get("visible_output_bytes") != len(text_bytes)
            or safe.get("visible_output_hash")
            != hashlib.sha256(text_bytes).hexdigest()
            or safe.get("candidate_grid_hash") != _candidate_grid_checksum(binding)
        ):
            raise PdfDualOracleReplayError(
                "pdf_dual_oracle_replay_verbose_checksum_mismatch", package_id
            )
        metrics: dict[str, int] = {}
        for key in (
            "provider_counted_input_tokens",
            "provider_actual_input_tokens",
            "provider_output_tokens",
            "visible_output_bytes",
        ):
            metric = safe.get(key)
            if not isinstance(metric, int) or isinstance(metric, bool) or metric < 0:
                raise PdfDualOracleReplayError(
                    "pdf_dual_oracle_replay_verbose_metric_invalid",
                    f"{package_id}:{key}",
                )
            metrics[key] = metric
        return copy.deepcopy(binding), metrics


def _job_identity_from_mapping(value: dict[str, Any], *, subject: str) -> dict[str, Any]:
    stage = value.get("stage")
    arm = value.get("arm")
    table_key = value.get("table_key")
    package_id = value.get("package_id")
    attempt_number = value.get("attempt_number")
    if stage != LEGACY_GRID_STAGE:
        raise PdfDualOracleReplayError("pdf_dual_oracle_replay_job_stage_invalid", subject)
    if arm not in {LEGACY_FREE_ARM, *LEGACY_PACKAGE_ARMS}:
        raise PdfDualOracleReplayError("pdf_dual_oracle_replay_job_arm_invalid", subject)
    table_key = _nonempty_string(
        table_key, "pdf_dual_oracle_replay_job_table_key_invalid", subject=subject
    )
    package_id = _nonempty_string(
        package_id, "pdf_dual_oracle_replay_job_package_id_invalid", subject=subject
    )
    if not isinstance(attempt_number, int) or isinstance(attempt_number, bool):
        raise PdfDualOracleReplayError(
            "pdf_dual_oracle_replay_job_attempt_invalid", subject
        )
    expected = _job_identity(
        arm=str(arm),
        table_key=table_key,
        package_id=package_id,
        attempt_number=attempt_number,
    )
    if (
        value.get("job_key") != expected["job_key"]
        or value.get("task_id") != expected["task_id"]
    ):
        raise PdfDualOracleReplayError(
            "pdf_dual_oracle_replay_job_derived_identity_mismatch", subject
        )
    return expected


def _job_identity(
    *, arm: str, table_key: str, package_id: str, attempt_number: int
) -> dict[str, Any]:
    if attempt_number not in {1, 2}:
        raise PdfDualOracleReplayError(
            "pdf_dual_oracle_replay_job_attempt_invalid",
            f"{table_key}:{attempt_number}",
        )
    identity = f"{arm}|{table_key}|{package_id}"
    return {
        "job_key": f"{identity}|a{attempt_number}",
        "task_id": "pdfgridtask_"
        + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24],
        "stage": LEGACY_GRID_STAGE,
        "arm": arm,
        "table_key": table_key,
        "package_id": package_id,
        "attempt_number": attempt_number,
    }


def _strict_json_object(value: str, *, subject: str) -> dict[str, Any]:
    def reject_constant(_value: str) -> None:
        raise ValueError("non_finite_number")

    def pairs_hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, item in pairs:
            if key in result:
                raise ValueError("duplicate_key")
            result[key] = item
        return result

    try:
        parsed = json.loads(
            value,
            parse_constant=reject_constant,
            object_pairs_hook=pairs_hook,
        )
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise PdfDualOracleReplayError(
            "pdf_dual_oracle_replay_text_invalid_json", subject
        ) from exc
    if not isinstance(parsed, dict):
        raise PdfDualOracleReplayError(
            "pdf_dual_oracle_replay_text_not_object", subject
        )
    return parsed


def _candidate_grid_checksum(binding: dict[str, Any]) -> str:
    rows = binding.get("rows")
    grid = [row.get("cells") or [] for row in rows or [] if isinstance(row, dict)]
    return sha256_json(grid)


def _topology_checksum(binding: dict[str, Any]) -> str:
    return sha256_json(
        {
            "decision": binding.get("decision"),
            "row_count": binding.get("row_count"),
            "column_count": binding.get("column_count"),
            "header_rows": binding.get("header_rows"),
            "header_hierarchy": binding.get("header_hierarchy"),
            "rows": binding.get("rows"),
            "spans": binding.get("spans"),
            "uncertainty_codes": binding.get("uncertainty_codes"),
        }
    )


def _attempt_numbers(value: Any, *, maximum: int, subject: str) -> list[int]:
    if not isinstance(value, list) or not value or not all(
        isinstance(item, int) and not isinstance(item, bool) for item in value
    ):
        raise PdfDualOracleReplayError(
            "pdf_dual_oracle_replay_attempt_numbers_invalid", subject
        )
    attempts = list(value)
    if (
        attempts != sorted(set(attempts))
        or attempts != list(range(1, len(attempts) + 1))
        or attempts[-1] > maximum
    ):
        raise PdfDualOracleReplayError(
            "pdf_dual_oracle_replay_attempt_numbers_invalid", subject
        )
    return attempts


def _object_map(value: Any, code: str) -> dict[str, Any]:
    if not isinstance(value, dict) or not all(
        isinstance(key, str) and key for key in value
    ):
        raise PdfDualOracleReplayError(code)
    return value


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _string_list(value: Any, code: str, *, subject: str) -> list[str]:
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item for item in value
    ):
        raise PdfDualOracleReplayError(code, subject)
    return list(value)


def _nonempty_string(value: Any, code: str, *, subject: str) -> str:
    if not isinstance(value, str) or not value:
        raise PdfDualOracleReplayError(code, subject)
    return value


def _positive_integer(value: Any) -> int:
    return (
        value
        if isinstance(value, int) and not isinstance(value, bool) and value > 0
        else 0
    )
