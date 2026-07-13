from __future__ import annotations

import copy
import hashlib
import unittest

from broker_reports_gate1.pdf_hybrid_budget import (
    PdfHybridBudgetConfig,
    PdfHybridBudgetError,
    PdfHybridBudgetFactory,
)
from broker_reports_gate1.pdf_hybrid_compaction import PdfHybridCompactionFactory
from broker_reports_gate1.pdf_hybrid_contracts import (
    PDF_HYBRID_BINDING_OUTPUT_SCHEMA,
    sha256_json,
)
from broker_reports_gate1.pdf_hybrid_materialization import (
    PdfHybridMaterializationFactory,
)
from broker_reports_gate1.pdf_hybrid_reliability import PdfHybridReliabilityFactory
from broker_reports_gate1.pdf_hybrid_structure import (
    PDF_HYBRID_CONTINUATION_SCHEMA,
    PdfHybridStructureFactory,
)
from broker_reports_gate1.pdf_hybrid_windows import (
    PdfHybridWindowConfig,
    PdfHybridWindowError,
    PdfHybridWindowFactory,
)


class PdfHybridCompactionWindowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.candidate, self.projection = _table_fixture(rows=4, columns=2)
        self.ledger = PdfHybridCompactionFactory().create().compact(
            document_ref="doc",
            pdf_sha256="a" * 64,
            page_ref="page1",
            page_number=1,
            table_candidate=self.candidate,
            pdf_text_layer_projection=self.projection,
            header_depth=1,
        )
        self.budget = PdfHybridBudgetFactory().create()
        self.windows = PdfHybridWindowFactory(
            PdfHybridWindowConfig(
                maximum_rows_per_window=2,
                maximum_candidates_per_window=4,
            )
        ).create(budget=self.budget)

    def test_compaction_is_reversible_and_exactly_once(self) -> None:
        dictionary = self.ledger["private_candidate_dictionary"]
        all_word_refs = [
            ref for candidate in dictionary.values() for ref in candidate["word_refs"]
        ]
        self.assertEqual(len(dictionary), 7)
        self.assertEqual(len(all_word_refs), 7)
        self.assertEqual(len(all_word_refs), len(set(all_word_refs)))
        self.assertEqual(self.ledger["source_accounting"]["word_coverage_ratio"], 1.0)
        self.assertTrue(
            all(len(item["candidate_checksum"]) == 64 for item in dictionary.values())
        )
        self.assertEqual(
            [item[0] for item in self.ledger["model_candidate_records"]],
            self.ledger["candidate_order"],
        )

    def test_row_windows_cover_every_candidate_without_column_split(self) -> None:
        plan = self.windows.plan(compact_ledger=self.ledger)
        assigned = [
            candidate_id
            for window in plan["windows"]
            for candidate_id in window["candidate_ids"]
        ]
        self.assertEqual(assigned, self.ledger["candidate_order"])
        self.assertEqual(len(assigned), len(set(assigned)))
        self.assertEqual(
            [(item["row_start"], item["row_end"]) for item in plan["windows"]],
            [(1, 2), (3, 4)],
        )
        self.assertTrue(all(not item["column_split_performed"] for item in plan["windows"]))

    def test_window_join_passes_full_materialization_and_structure(self) -> None:
        plan, packages, bindings = _packages_and_bindings(
            ledger=self.ledger,
            windows=self.windows,
        )
        evidence, joined = self.windows.join(
            compact_ledger=self.ledger,
            plan=plan,
            packages=packages,
            bindings=bindings,
        )
        materialization = PdfHybridMaterializationFactory().create().materialize(
            evidence_package=evidence,
            binding_output=joined,
        )
        structure = PdfHybridStructureFactory().create().validate_placement(
            compact_ledger=self.ledger,
            materialization=materialization,
        )
        self.assertEqual(materialization["row_count"], 4)
        self.assertEqual(materialization["column_count"], 2)
        self.assertEqual(len(materialization["cells"]), 8)
        self.assertEqual(materialization["omitted_candidate_ids"], [])
        self.assertTrue(structure["passed"], structure["reason_codes"])

    def test_join_rejects_repeated_header_from_later_window(self) -> None:
        plan, packages, bindings = _packages_and_bindings(
            ledger=self.ledger,
            windows=self.windows,
        )
        bindings[1]["header_rows"] = [1]
        with self.assertRaisesRegex(
            PdfHybridWindowError, "pdf_hybrid_window_join_repeated_header_output"
        ):
            self.windows.join(
                compact_ledger=self.ledger,
                plan=plan,
                packages=packages,
                bindings=bindings,
            )

    def test_708_candidate_table_is_bounded_by_row_windows_without_loss(self) -> None:
        empty_positions = {
            (row, column)
            for row in range(1, 49)
            for column in range(1, 17)
        }
        for position in sorted(empty_positions)[:708]:
            empty_positions.remove(position)
        candidate, projection = _table_fixture(
            rows=48,
            columns=16,
            empty_positions=empty_positions,
            table_ref="wide",
        )
        ledger = PdfHybridCompactionFactory().create().compact(
            document_ref="doc",
            pdf_sha256="b" * 64,
            page_ref="page1",
            page_number=1,
            table_candidate=candidate,
            pdf_text_layer_projection=projection,
            header_depth=2,
        )
        plan = PdfHybridWindowFactory().create(
            budget=PdfHybridBudgetFactory().create()
        ).plan(compact_ledger=ledger)
        assigned = [item for window in plan["windows"] for item in window["candidate_ids"]]
        self.assertEqual(len(ledger["candidate_order"]), 708)
        self.assertEqual(len(assigned), 708)
        self.assertEqual(len(set(assigned)), 708)
        self.assertTrue(
            all(window["candidate_count"] <= 192 for window in plan["windows"])
        )


class PdfHybridBudgetTests(unittest.TestCase):
    def test_provider_count_is_guarded_and_actual_usage_is_reconciled(self) -> None:
        guard = PdfHybridBudgetFactory().create()
        accounting = guard.estimate(
            model_facing={"t": "bind", "c": [["0", "10"]]},
            output_schema={"type": "object"},
            crop_manifest={"width": 960, "height": 540, "dpi": 150, "png_bytes": 20},
            candidate_count=1,
            row_count=1,
            column_count=1,
        )
        counted = guard.apply_provider_count(accounting, counted_input_tokens=1200)
        guard.require_provider_count(counted)
        reconciled = guard.reconcile_actual(counted, actual_input_tokens=1201)
        self.assertTrue(reconciled["estimator_calibration_passed"])
        self.assertEqual(reconciled["counted_to_actual_error_tokens"], 1)

    def test_provider_count_over_guard_is_typed_block(self) -> None:
        guard = PdfHybridBudgetFactory(
            PdfHybridBudgetConfig(
                maximum_counted_input_tokens=100,
                provider_input_safety_margin_tokens=20,
                maximum_provider_input_tokens=120,
            )
        ).create()
        accounting = {"hard_budget_failure_codes": []}
        counted = guard.apply_provider_count(accounting, counted_input_tokens=101)
        with self.assertRaisesRegex(
            PdfHybridBudgetError,
            "pdf_hybrid_provider_counted_input_budget_exceeded",
        ):
            guard.require_provider_count(counted)


class PdfHybridStructureReliabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        candidate, projection = _table_fixture(rows=4, columns=2)
        self.ledger = PdfHybridCompactionFactory().create().compact(
            document_ref="doc",
            pdf_sha256="a" * 64,
            page_ref="page1",
            page_number=1,
            table_candidate=candidate,
            pdf_text_layer_projection=projection,
            header_depth=1,
        )
        self.windows = PdfHybridWindowFactory(
            PdfHybridWindowConfig(maximum_rows_per_window=2, maximum_candidates_per_window=4)
        ).create(budget=PdfHybridBudgetFactory().create())
        plan, packages, bindings = _packages_and_bindings(
            ledger=self.ledger,
            windows=self.windows,
        )
        evidence, joined = self.windows.join(
            compact_ledger=self.ledger,
            plan=plan,
            packages=packages,
            bindings=bindings,
        )
        self.evidence = evidence
        self.joined = joined

    def test_wrong_column_is_independently_blocked(self) -> None:
        broken = copy.deepcopy(self.joined)
        broken["rows"][1]["cells"][0], broken["rows"][1]["cells"][1] = (
            broken["rows"][1]["cells"][1],
            broken["rows"][1]["cells"][0],
        )
        materialization = PdfHybridMaterializationFactory().create().materialize(
            evidence_package=self.evidence,
            binding_output=broken,
        )
        result = PdfHybridStructureFactory().create().validate_placement(
            compact_ledger=self.ledger,
            materialization=materialization,
        )
        self.assertFalse(result["passed"])
        self.assertIn(
            "pdf_hybrid_structure_candidate_column_mismatch", result["reason_codes"]
        )

    def test_continuation_requires_shared_columns_order_and_full_coverage(self) -> None:
        second_candidate, second_projection = _table_fixture(
            rows=3,
            columns=2,
            table_ref="table2",
            page_ref="page2",
            word_prefix="b",
        )
        second_ledger = PdfHybridCompactionFactory().create().compact(
            document_ref="doc",
            pdf_sha256="a" * 64,
            page_ref="page2",
            page_number=2,
            table_candidate=second_candidate,
            pdf_text_layer_projection=second_projection,
            header_depth=0,
        )
        second_windows = PdfHybridWindowFactory().create(
            budget=PdfHybridBudgetFactory().create()
        )
        fragments = []
        for ledger, runtime in ((self.ledger, self.windows), (second_ledger, second_windows)):
            plan, packages, bindings = _packages_and_bindings(
                ledger=ledger,
                windows=runtime,
            )
            evidence, joined = runtime.join(
                compact_ledger=ledger,
                plan=plan,
                packages=packages,
                bindings=bindings,
            )
            material = PdfHybridMaterializationFactory().create().materialize(
                evidence_package=evidence,
                binding_output=joined,
            )
            structural = PdfHybridStructureFactory().create().validate_placement(
                compact_ledger=ledger,
                materialization=material,
            )
            fragments.append(
                {
                    "compact_ledger": ledger,
                    "materialization": material,
                    "structural_validation": structural,
                }
            )
        contract = {
            "schema_version": PDF_HYBRID_CONTINUATION_SCHEMA,
            "continuation_group_id": "group1",
            "shared_column_count": 2,
            "fragments": [
                {
                    "fragment_order": 1,
                    "page_number": 1,
                    "table_ref": "table1",
                    "repeated_header_policy": "source_header",
                },
                {
                    "fragment_order": 2,
                    "page_number": 2,
                    "table_ref": "table2",
                    "repeated_header_policy": "no_repeated_header",
                },
            ],
            "subtotal_policy": "preserve_fragment_subtotals",
            "duplicate_row_policy": "allow_explicit_repeated_header_only",
        }
        result = PdfHybridStructureFactory().create().validate_continuation(
            contract=contract,
            fragment_results=fragments,
        )
        self.assertTrue(result["passed"], result["reason_codes"])
        self.assertEqual(result["fragment_coverage"]["candidates_expected"], 12)

    def test_non_repeatability_is_monotonic_and_arbitration_is_typed(self) -> None:
        reliability = PdfHybridReliabilityFactory().create()
        task_key = reliability.task_key(
            evidence_package_hashes=["p1"],
            provider="google",
            model="models/gemini-3.5-flash",
            provider_config_hash="config",
            output_schema_hashes=["schema"],
        )
        reliability.record(
            task_key=task_key,
            placement_checksum="a",
            attempt_number=1,
            evidence_revision="150",
        )
        reliability.record(
            task_key=task_key,
            placement_checksum="b",
            attempt_number=2,
            evidence_revision="150",
        )
        # A later matching observation is represented by a persisted import; it cannot clear the flag.
        ledger = reliability.ledger()
        resumed = PdfHybridReliabilityFactory().create(
            initial_repeatability_ledger=ledger
        )
        resumed.record(
            task_key=task_key,
            placement_checksum="a",
            attempt_number=2,
            evidence_revision="150",
        )
        repeat = resumed.result(task_key, required=True)
        self.assertTrue(repeat["ever_conflicted"])
        arbitration = resumed.arbitrate(
            table_ref="table1",
            deterministic_signal={"status": "blocked"},
            hybrid_150_signal={
                "supported": True,
                "context_budget_passed": True,
                "provider_passed": True,
                "binding_status": "bound",
            },
            hybrid_200_signal=None,
            structural_signal={"passed": True, "reason_codes": []},
            continuation_signal={"required": False, "passed": True},
            repeatability_signal=repeat,
        )
        self.assertEqual(arbitration["terminal_status"], "blocked_non_repeatable")
        self.assertFalse(arbitration["best_looking_result_selection_used"])


def _packages_and_bindings(*, ledger: dict, windows: object):
    plan = windows.plan(compact_ledger=ledger)
    packages = []
    bindings = []
    dictionary = ledger["private_candidate_dictionary"]
    for window in plan["windows"]:
        crop_bytes = f"crop-{window['window_id']}".encode()
        manifest = {
            "table_ref": ledger["table_ref"],
            "declared_table_bbox": window["crop_bbox"],
            "png_sha256": hashlib.sha256(crop_bytes).hexdigest(),
            "crop_id": "crop",
            "dpi": 150,
            "width": 800,
            "height": 300,
            "png_bytes": len(crop_bytes),
            "renderer": "pymupdf",
            "renderer_version": "1.26.5",
            "source_to_pixel_transform": {},
        }
        package = windows.build_package(
            compact_ledger=ledger,
            plan=plan,
            window=window,
            crop_manifest=manifest,
            private_crop_artifact_ref="private-crop",
        )
        rows = []
        for local_row, global_row in enumerate(
            range(window["row_start"], window["row_end"] + 1), start=1
        ):
            rows.append(
                {
                    "row_ordinal": local_row,
                    "row_kind": "header" if global_row <= ledger["header_depth"] else "data",
                    "cells": [
                        [
                            candidate_id
                            for candidate_id in window["candidate_ids"]
                            if dictionary[candidate_id]["expected_row_ordinal"] == global_row
                            and dictionary[candidate_id]["expected_column_ordinal"] == column
                        ]
                        for column in range(1, ledger["column_count"] + 1)
                    ],
                }
            )
        binding = {
            "schema_version": PDF_HYBRID_BINDING_OUTPUT_SCHEMA,
            "package_id": package["package_id"],
            "crop_sha256": package["crop_identity"]["crop_sha256"],
            "candidate_dictionary_hash": package["candidate_dictionary_hash"],
            "decision": "bound",
            "row_count": window["row_count"],
            "column_count": window["column_count"],
            "header_rows": (
                list(range(1, ledger["header_depth"] + 1))
                if window["window_index"] == 1
                else []
            ),
            "header_hierarchy": [],
            "rows": rows,
            "spans": [],
            "uncertainty_codes": [],
        }
        packages.append(package)
        bindings.append(binding)
    return plan, packages, bindings


def _table_fixture(
    *,
    rows: int,
    columns: int,
    empty_positions: set[tuple[int, int]] | None = None,
    table_ref: str = "table1",
    page_ref: str = "page1",
    word_prefix: str = "w",
) -> tuple[dict, dict]:
    empty_positions = empty_positions if empty_positions is not None else {(3, 2)}
    table_bbox_ref = f"bbox-{table_ref}"
    bboxes = [{"bbox_ref": table_bbox_ref, "bbox": [0.0, 0.0, 200.0, rows * 20.0]}]
    words = []
    cells = []
    contributing = []
    ordinal = 0
    for row in range(1, rows + 1):
        for column in range(1, columns + 1):
            x0 = (column - 1) * (200.0 / columns)
            x1 = column * (200.0 / columns)
            y0 = (row - 1) * 20.0
            y1 = row * 20.0
            bbox_ref = f"bbox-{table_ref}-{row}-{column}"
            bboxes.append({"bbox_ref": bbox_ref, "bbox": [x0, y0, x1, y1]})
            refs = []
            if (row, column) not in empty_positions:
                word_ref = f"{word_prefix}-{row}-{column}"
                word_bbox_ref = f"bbox-{word_ref}"
                bboxes.append(
                    {
                        "bbox_ref": word_bbox_ref,
                        "bbox": [x0 + 2, y0 + 4, x1 - 2, y1 - 4],
                    }
                )
                ordinal += 1
                words.append(
                    {
                        "word_ref": word_ref,
                        "page_ref": page_ref,
                        "bbox_ref": word_bbox_ref,
                        "text": str(ordinal),
                        "source_value_ref": f"src-{word_ref}",
                        "text_checksum_ref": f"checksum-{word_ref}",
                        "geometry_reading_order": ordinal,
                        "parser_ordinal": ordinal,
                    }
                )
                refs.append(word_ref)
                contributing.append(word_ref)
            cells.append(
                {
                    "cell_ref": f"cell-{table_ref}-{row}-{column}",
                    "bbox_ref": bbox_ref,
                    "page_ref": page_ref,
                    "row_ordinal": row,
                    "column_ordinal": column,
                    "word_refs": refs,
                }
            )
    candidate = {
        "table_candidate_ref": table_ref,
        "page_ref": page_ref,
        "bbox_ref": table_bbox_ref,
        "contributing_word_refs": contributing,
        "cell_inventory": cells,
    }
    projection = {"bbox_inventory": bboxes, "word_inventory": words}
    return candidate, projection


if __name__ == "__main__":
    unittest.main()
