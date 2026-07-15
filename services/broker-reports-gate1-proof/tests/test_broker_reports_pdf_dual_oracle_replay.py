from __future__ import annotations

import copy
import hashlib
import json
import unittest
from typing import Any

from broker_reports_gate1.pdf_dual_oracle_replay import (
    FACTORY_REQUIRED,
    FORBIDDEN,
    PdfDualOracleReplayConfig,
    PdfDualOracleReplayError,
    PdfDualOracleReplayFactory,
    PdfDualOracleReplayRuntime,
)
from broker_reports_gate1.pdf_hybrid_contracts import (
    PDF_HYBRID_BINDING_OUTPUT_SCHEMA,
    sha256_json,
)


TABLE_WINDOW_COUNTS = {
    "1:2": 1,
    "1:3": 2,
    "3:2": 4,
    "4:1": 3,
    "4:2": 1,
    "5:3": 1,
}
REPEATED_TABLES = {"1:2", "1:3", "3:2", "4:1", "4:2"}


class PdfDualOracleReplayTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runtime = PdfDualOracleReplayFactory().create()

    def test_exact_80_entry_replay_uses_plan_order_and_preserves_conflict(self) -> None:
        fixture = _fixture(self.runtime)
        fixture["journal"].reverse()
        fixture["packages_by_table"]["3:2"].reverse()

        result = self.runtime.replay(**fixture)

        safe = result["safe_summary"]
        self.assertEqual(safe["journal_entry_count"], 80)
        self.assertEqual(safe["verbose_entry_count"], 23)
        self.assertTrue(safe["job_key_set_exact"])
        self.assertFalse(safe["journal_order_trusted"])
        self.assertTrue(safe["plan_window_order_used"])
        self.assertEqual(safe["provider_calls_performed"], 0)
        self.assertFalse(safe["reference_access_performed"])
        self.assertNotIn("private_joined_attempts", safe)
        summaries = {item["table_key"]: item for item in safe["table_summaries"]}
        self.assertEqual(
            summaries["1:3"]["repeatability"]["status"], "conflict_preserved"
        )
        self.assertTrue(summaries["1:3"]["repeatability"]["ever_conflicted"])
        self.assertEqual(
            summaries["1:2"]["repeatability"]["status"], "stable"
        )
        self.assertEqual(
            summaries["5:3"]["repeatability"]["status"], "not_repeated"
        )
        joined = result["private_joined_attempts"]["3:2"][0]
        expected_package_order = [
            f"pkg_3_2_{index}" for index in range(1, TABLE_WINDOW_COUNTS["3:2"] + 1)
        ]
        self.assertEqual(
            joined["logical_evidence"]["window_package_ids"], expected_package_order
        )
        self.assertEqual(
            [row["row_ordinal"] for row in joined["binding"]["rows"]],
            [1, 2, 3, 4],
        )

    def test_duplicate_and_missing_journal_entries_fail_closed(self) -> None:
        duplicate = _fixture(self.runtime)
        duplicate["journal"][-1] = copy.deepcopy(duplicate["journal"][0])
        with self.assertRaisesRegex(
            PdfDualOracleReplayError,
            "pdf_dual_oracle_replay_journal_job_key_duplicate",
        ):
            self.runtime.replay(**duplicate)

        missing = _fixture(self.runtime)
        missing["journal"].pop()
        with self.assertRaisesRegex(
            PdfDualOracleReplayError,
            "pdf_dual_oracle_replay_journal_entry_count_invalid",
        ):
            self.runtime.replay(**missing)

    def test_manifest_must_be_exact_and_caller_supplied(self) -> None:
        fixture = _fixture(self.runtime)
        fixture["expected_manifest"].pop()
        with self.assertRaisesRegex(
            PdfDualOracleReplayError,
            "pdf_dual_oracle_replay_manifest_entry_count_invalid",
        ):
            self.runtime.replay(**fixture)

    def test_recomputed_job_and_task_identity_rejects_field_tamper(self) -> None:
        fixture = _fixture(self.runtime)
        fixture["journal"][0]["safe"]["task_id"] = "tampered"
        with self.assertRaisesRegex(
            PdfDualOracleReplayError,
            "pdf_dual_oracle_replay_job_derived_identity_mismatch",
        ):
            self.runtime.replay(**fixture)

    def test_private_text_is_reparsed_and_must_exactly_match_binding(self) -> None:
        fixture = _fixture(self.runtime)
        entry = _first_verbose(fixture["journal"])
        parsed = json.loads(entry["private"]["text"])
        parsed["uncertainty_codes"] = ["tampered"]
        entry["private"]["text"] = json.dumps(parsed, separators=(",", ":"))
        with self.assertRaisesRegex(
            PdfDualOracleReplayError,
            "pdf_dual_oracle_replay_text_binding_mismatch",
        ):
            self.runtime.replay(**fixture)

    def test_binding_package_identity_mismatch_fails_after_exact_text_check(self) -> None:
        fixture = _fixture(self.runtime)
        entry = _first_verbose(fixture["journal"])
        entry["private"]["binding"]["package_id"] = "tampered-package"
        _reserialize_verbose(entry)
        with self.assertRaisesRegex(
            PdfDualOracleReplayError,
            "pdf_dual_oracle_replay_binding_package_identity_mismatch",
        ):
            self.runtime.replay(**fixture)

    def test_candidate_ownership_tamper_fails_closed(self) -> None:
        fixture = _fixture(self.runtime)
        entry = _first_verbose(fixture["journal"])
        cells = entry["private"]["binding"]["rows"][0]["cells"]
        cells[1] = list(cells[0])
        _reserialize_verbose(entry)
        with self.assertRaisesRegex(
            PdfDualOracleReplayError,
            "pdf_dual_oracle_replay_binding_candidate_ownership_mismatch",
        ):
            self.runtime.replay(**fixture)

    def test_plan_window_order_tamper_is_not_hidden_by_package_mapping(self) -> None:
        fixture = _fixture(self.runtime)
        fixture["plans_by_table"]["1:3"]["windows"].reverse()
        with self.assertRaisesRegex(
            PdfDualOracleReplayError,
            "pdf_dual_oracle_replay_plan_window_order_invalid",
        ):
            self.runtime.replay(**fixture)

    def test_repeat_attempt_lineage_must_start_at_one(self) -> None:
        fixture = _fixture(self.runtime)
        for identity in fixture["expected_manifest"]:
            if identity["table_key"] == "5:3":
                _rewrite_attempt(identity, 2)
        for entry in fixture["journal"]:
            if entry["safe"]["table_key"] == "5:3":
                _rewrite_attempt(entry["safe"], 2)
        with self.assertRaisesRegex(
            PdfDualOracleReplayError,
            "pdf_dual_oracle_replay_attempt_numbers_invalid",
        ):
            self.runtime.replay(**fixture)

    def test_repeat_history_authority_is_idempotent_and_preserves_conflict(
        self,
    ) -> None:
        fixture = _fixture(self.runtime)
        scopes = _repeat_scopes()
        revisions = {table_key: "legacy-revision-1" for table_key in scopes}
        first = self.runtime.replay(
            **fixture,
            repeat_scopes_by_table=scopes,
            evidence_revisions_by_table=revisions,
        )
        histories = first["safe_summary"]["repeat_history_authorities"]

        self.assertEqual(
            "sealed_append_only",
            first["safe_summary"]["repeat_history_authority_status"],
        )
        self.assertTrue(histories["1:3"]["ever_conflicted"])
        self.assertFalse(histories["1:2"]["ever_conflicted"])
        self.assertEqual(2, len(histories["1:3"]["events"]))
        replayed = self.runtime.replay(
            **fixture,
            repeat_scopes_by_table=scopes,
            prior_repeat_histories_by_table=histories,
            evidence_revisions_by_table=revisions,
        )
        replayed_histories = replayed["safe_summary"][
            "repeat_history_authorities"
        ]
        self.assertEqual(
            histories["1:3"]["history_checksum"],
            replayed_histories["1:3"]["history_checksum"],
        )
        self.assertEqual(histories["1:3"]["events"], replayed_histories["1:3"]["events"])

        tampered = copy.deepcopy(histories)
        tampered["1:3"]["ever_conflicted"] = False
        with self.assertRaisesRegex(
            PdfDualOracleReplayError,
            "pdf_dual_oracle_repeat_history_integrity_invalid",
        ):
            self.runtime.replay(
                **fixture,
                repeat_scopes_by_table=scopes,
                prior_repeat_histories_by_table=tampered,
                evidence_revisions_by_table=revisions,
            )

    def test_json_container_types_and_factory_anchors_are_enforced(self) -> None:
        fixture = _fixture(self.runtime)
        fixture["journal"] = {"not": "a-list"}
        with self.assertRaisesRegex(
            PdfDualOracleReplayError, "pdf_dual_oracle_replay_journal_not_list"
        ):
            self.runtime.replay(**fixture)
        self.assertIn("PdfDualOracleReplayFactory.create", FACTORY_REQUIRED)
        self.assertIn("call providers", FORBIDDEN)

    def test_runtime_constructor_requires_factory_token(self) -> None:
        with self.assertRaisesRegex(
            PdfDualOracleReplayError, "pdf_dual_oracle_replay_factory_required"
        ):
            PdfDualOracleReplayRuntime(PdfDualOracleReplayConfig(), None)


def _fixture(runtime: Any) -> dict[str, Any]:
    compact_ledgers_by_table: dict[str, dict[str, Any]] = {}
    plans_by_table: dict[str, dict[str, Any]] = {}
    packages_by_table: dict[str, list[dict[str, Any]]] = {}
    package_ids_by_table: dict[str, list[str]] = {}
    attempt_numbers_by_table: dict[str, list[int]] = {}
    bindings: dict[tuple[str, str, int], dict[str, Any]] = {}
    for table_key, window_count in TABLE_WINDOW_COUNTS.items():
        slug = table_key.replace(":", "_")
        logical_table_id = f"logical_{slug}"
        ledger_id = f"ledger_{slug}"
        global_dictionary: dict[str, dict[str, Any]] = {}
        candidate_order: list[str] = []
        windows: list[dict[str, Any]] = []
        packages: list[dict[str, Any]] = []
        for window_index in range(1, window_count + 1):
            candidate_ids = [
                f"candidate_{slug}_{window_index}_1",
                f"candidate_{slug}_{window_index}_2",
            ]
            for candidate_id in candidate_ids:
                global_dictionary[candidate_id] = {
                    "candidate_id": candidate_id,
                    "exact_source_span": candidate_id,
                }
            candidate_order.extend(candidate_ids)
            window = {
                "window_id": f"window_{slug}_{window_index}",
                "window_index": window_index,
                "row_start": window_index,
                "row_end": window_index,
                "row_count": 1,
                "column_start": 1,
                "column_end": 2,
                "column_count": 2,
                "candidate_ids": candidate_ids,
                "candidate_count": len(candidate_ids),
                "column_split_performed": False,
                "silent_truncation_performed": False,
            }
            windows.append(window)
            package_id = f"pkg_{slug}_{window_index}"
            private_dictionary = {
                candidate_id: copy.deepcopy(global_dictionary[candidate_id])
                for candidate_id in candidate_ids
            }
            dictionary_hash = sha256_json(private_dictionary)
            crop_sha256 = hashlib.sha256(package_id.encode("utf-8")).hexdigest()
            package = {
                "package_id": package_id,
                "logical_table_id": logical_table_id,
                "ledger_id": ledger_id,
                "window": copy.deepcopy(window),
                "crop_identity": {"crop_sha256": crop_sha256},
                "candidate_dictionary_hash": dictionary_hash,
                "private_candidate_dictionary": private_dictionary,
                "model_facing": {
                    "i": {
                        "package_id": package_id,
                        "crop_sha256": crop_sha256,
                        "candidate_dictionary_hash": dictionary_hash,
                    },
                    "c": [[candidate_id] for candidate_id in candidate_ids],
                },
            }
            packages.append(package)
        ledger = {
            "ledger_id": ledger_id,
            "document_ref": f"document_{slug}",
            "pdf_sha256": "a" * 64,
            "page_ref": f"page_{slug}",
            "page_number": 1,
            "table_ref": f"table_{slug}",
            "candidate_order": candidate_order,
            "private_candidate_dictionary": global_dictionary,
            "candidate_dictionary_hash": sha256_json(global_dictionary),
        }
        plan = {
            "ledger_id": ledger_id,
            "logical_table_id": logical_table_id,
            "row_count": window_count,
            "column_count": 2,
            "windows": windows,
            "candidate_count": len(candidate_order),
            "candidate_ids_assigned": len(candidate_order),
            "candidate_ids_unique": len(set(candidate_order)),
            "exactly_once_candidate_ownership": True,
            "column_split_performed": False,
            "silent_truncation_performed": False,
            "plan_checksum": sha256_json(windows),
        }
        compact_ledgers_by_table[table_key] = ledger
        plans_by_table[table_key] = plan
        packages_by_table[table_key] = packages
        package_ids_by_table[table_key] = [str(item["package_id"]) for item in packages]
        attempts = [1, 2] if table_key in REPEATED_TABLES else [1]
        attempt_numbers_by_table[table_key] = attempts
        for package in packages:
            candidate_ids = list(package["window"]["candidate_ids"])
            for attempt in attempts:
                cells = [[candidate_ids[0]], [candidate_ids[1]]]
                if table_key == "1:3" and package is packages[0] and attempt == 2:
                    cells.reverse()
                bindings[(table_key, str(package["package_id"]), attempt)] = {
                    "schema_version": PDF_HYBRID_BINDING_OUTPUT_SCHEMA,
                    "package_id": package["package_id"],
                    "crop_sha256": package["crop_identity"]["crop_sha256"],
                    "candidate_dictionary_hash": package["candidate_dictionary_hash"],
                    "decision": "bound",
                    "row_count": 1,
                    "column_count": 2,
                    "header_rows": [],
                    "header_hierarchy": [],
                    "rows": [
                        {
                            "row_ordinal": 1,
                            "row_kind": "data",
                            "cells": cells,
                        }
                    ],
                    "spans": [],
                    "uncertainty_codes": [],
                }
    manifest = runtime.build_expected_manifest(
        package_ids_by_table=package_ids_by_table,
        attempt_numbers_by_table=attempt_numbers_by_table,
    )
    journal = []
    for identity in manifest:
        safe = copy.deepcopy(identity)
        private: dict[str, Any] = {}
        if identity["arm"] == "verbose_json":
            binding = copy.deepcopy(
                bindings[
                    (
                        str(identity["table_key"]),
                        str(identity["package_id"]),
                        int(identity["attempt_number"]),
                    )
                ]
            )
            text = json.dumps(binding, ensure_ascii=False, separators=(",", ":"))
            provider_task_id = "pdfhybridtask_" + str(
                identity["package_id"]
            ).removeprefix("pdfhybridpkg_")
            safe.update(
                {
                    "attempt_id": f"{provider_task_id}_a{identity['attempt_number']}",
                    "artifact_status": "accepted",
                    "finish_reason": "STOP",
                    "validation_error": None,
                    "terminal_failure_class": None,
                    "hidden_retry": False,
                    "provider_failover": False,
                    "candidate_coverage_ratio": 1.0,
                    "candidate_grid_hash": sha256_json(
                        [row["cells"] for row in binding["rows"]]
                    ),
                    "visible_output_bytes": len(text.encode("utf-8")),
                    "visible_output_hash": hashlib.sha256(
                        text.encode("utf-8")
                    ).hexdigest(),
                    "provider_counted_input_tokens": 100,
                    "provider_actual_input_tokens": 100,
                    "provider_output_tokens": 10,
                }
            )
            private = {"text": text, "binding": binding}
        journal.append({"private": private, "safe": safe})
    return {
        "journal": journal,
        "expected_manifest": manifest,
        "compact_ledgers_by_table": compact_ledgers_by_table,
        "plans_by_table": plans_by_table,
        "packages_by_table": packages_by_table,
    }


def _first_verbose(journal: list[dict[str, Any]]) -> dict[str, Any]:
    return next(item for item in journal if item["safe"]["arm"] == "verbose_json")


def _reserialize_verbose(entry: dict[str, Any]) -> None:
    binding = entry["private"]["binding"]
    text = json.dumps(binding, ensure_ascii=False, separators=(",", ":"))
    entry["private"]["text"] = text
    entry["safe"]["visible_output_bytes"] = len(text.encode("utf-8"))
    entry["safe"]["visible_output_hash"] = hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()
    entry["safe"]["candidate_grid_hash"] = sha256_json(
        [row["cells"] for row in binding["rows"]]
    )


def _rewrite_attempt(identity: dict[str, Any], attempt_number: int) -> None:
    base = (
        f"{identity['arm']}|{identity['table_key']}|{identity['package_id']}"
    )
    identity["attempt_number"] = attempt_number
    identity["job_key"] = f"{base}|a{attempt_number}"
    identity["task_id"] = (
        "pdfgridtask_"
        + hashlib.sha256(base.encode("utf-8")).hexdigest()[:24]
    )


def _repeat_scopes() -> dict[str, dict[str, str]]:
    return {
        table_key: {
            "parser_observation_checksum": f"parser-{table_key}",
            "provider": "legacy-provider",
            "model": "legacy-model",
            "configuration_hash": "legacy-config-v1",
            "crop_manifest_hash": f"crop-manifest-{table_key}",
            "solver_version": "legacy-replay-v1",
        }
        for table_key in TABLE_WINDOW_COUNTS
    }


if __name__ == "__main__":
    unittest.main()
