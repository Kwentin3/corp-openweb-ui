from __future__ import annotations

import copy
import hashlib
import unittest

from broker_reports_gate1.pdf_dual_oracle_contracts import (
    PdfDualOracleContractFactory,
)
from broker_reports_gate1.pdf_hybrid_contracts import sha256_json
from broker_reports_gate1.pdf_parser_geometry import PdfParserGeometryFactory
from broker_reports_gate1.pdf_structural_repair_runtime import (
    PdfStructuralRepairRuntimeFactory,
)
from broker_reports_gate1.pdf_structural_row_windows import (
    FACTORY_REQUIRED,
    FORBIDDEN,
    PdfStructuralRowWindowError,
    PdfStructuralRowWindowConfig,
    PdfStructuralRowWindowFactory,
    PdfStructuralRowWindowRuntime,
)
from broker_reports_gate1.pdf_visual_topology import (
    PDF_VISUAL_TOPOLOGY_RESPONSE_SCHEMA,
    PdfVisualTopologyFactory,
)


class _WindowProvider:
    def __init__(self, *, counted_tokens: int = 500) -> None:
        self.counted_tokens = counted_tokens
        self.count_calls = 0
        self.generate_calls = 0
        self.provider_package_ids: list[str] = []

    def qualify(self) -> dict:
        return {
            "status": "qualified",
            "provider_profile": "google_gemini",
            "requested_model_id": "models/gemini-3.5-flash",
            "resolved_model_id": "models/gemini-3.5-flash",
            "exact_model_match": True,
            "image_input_supported": True,
            "structured_output_supported": True,
            "maximum_input_tokens": 1_000_000,
            "maximum_output_tokens": 65_536,
            "hidden_retry": False,
            "provider_failover": False,
        }

    def count_tokens(self, *, model_view: dict, **kwargs) -> dict:
        self.count_calls += 1
        self.provider_package_ids.append(model_view["identity"]["package_id"])
        return {
            "total_tokens": self.counted_tokens,
            "model_requested": "models/gemini-3.5-flash",
            "within_hard_guard": True,
        }

    def invoke(
        self,
        *,
        task_id: str,
        model_view: dict,
        attempt_number: int,
        attempt_lineage: list[str],
        **kwargs,
    ) -> dict:
        self.generate_calls += 1
        package_id = model_view["identity"]["package_id"]
        self.provider_package_ids.append(package_id)
        window = model_view.get("window")
        window_index = int(window.get("window_index") or 1) if window else 1
        core_y = window.get("core_y_normalized_in_crop") if window else None
        rows = (
            [0.0, core_y[1], 1.0]
            if core_y and window_index == 1
            else [0.0, core_y[0], 1.0]
            if core_y
            else [0.0, 0.5, 1.0]
        )
        attempt_id = f"{task_id}_a{attempt_number}"
        return {
            "attempt": {
                "task_id": task_id,
                "attempt_id": attempt_id,
                "attempt_number": attempt_number,
                "attempt_lineage": list(attempt_lineage),
                "model_requested": "models/gemini-3.5-flash",
                "model_resolved": "models/gemini-3.5-flash",
                "started_at": f"2026-07-14T00:00:0{attempt_number}Z",
                "usage": {
                    "input_tokens": self.counted_tokens,
                    "output_tokens": 20,
                    "total_tokens": self.counted_tokens + 20,
                },
                "finish_reason": "STOP",
                "terminal_failure_class": None,
                "hidden_retry": False,
                "provider_failover": False,
            },
            "json_output": _response(
                package_id,
                header_row_count=1 if window_index == 1 else 0,
                rows=rows,
            ),
            "raw_private_response": {"private": True},
            "visible_output_bytes": 100,
            "response_bytes": 200,
        }


class _FirstWindowContinuationProvider(_WindowProvider):
    def invoke(self, **kwargs) -> dict:
        result = super().invoke(**kwargs)
        if self.generate_calls == 1:
            result["json_output"]["hypotheses"][0][
                "continuation_required"
            ] = True
        return result


class PdfStructuralRowWindowTests(unittest.TestCase):
    def setUp(self) -> None:
        projection = _projection_193()
        contracts = PdfDualOracleContractFactory().create()
        self.observation = contracts.build_parser_observation_from_word_atoms(
            document_ref="document-window",
            pdf_sha256="pdf-window-sha",
            page_ref="page-window-1",
            page_number=1,
            table_ref="table-window-1",
            table_bbox=[0.0, 0.0, 200.0, 100.0],
            pdf_text_layer_projection=projection,
        )
        self.geometry = PdfParserGeometryFactory().create().build_observation(
            document_ref="document-window",
            pdf_sha256="pdf-window-sha",
            page_ref="page-window-1",
            page_number=1,
            table_ref="table-window-1",
            table_bbox=[0.0, 0.0, 200.0, 100.0],
            pdf_text_layer_projection=projection,
        )

    def _window_packages(
        self,
        *,
        runtime: object,
        observation: dict,
        plan: dict,
        full_package: dict,
    ) -> list[dict]:
        visual = PdfVisualTopologyFactory().create()
        result = []
        for window in plan["windows"]:
            png_bytes = b"edge-window-" + str(window["window_index"]).encode()
            result.append(
                visual.build_window_package(
                    parser_observation=observation,
                    full_package=full_package,
                    window_plan=plan,
                    window=window,
                    crop_manifest=_crop_manifest(
                        png_bytes,
                        crop_id=f"edge-window-{window['window_index']}",
                        bbox=window["crop_bbox"],
                    ),
                )
            )
        return result

    def test_factory_plans_exact_once_raw_atom_ownership(self) -> None:
        planner = PdfStructuralRowWindowFactory().create()
        plan = planner.plan(self.observation)

        self.assertIn("PdfStructuralRowWindowFactory.create", FACTORY_REQUIRED)
        self.assertIn("must not consume parser rows", FORBIDDEN)
        self.assertEqual("vertical_atom_windows", plan["mode"])
        self.assertEqual(2, plan["window_count"])
        self.assertTrue(plan["candidate_ownership_exact"])
        self.assertFalse(plan["column_splitting_used"])
        self.assertTrue(
            all(item["owner_atom_count"] <= 192 for item in plan["windows"])
        )
        owned = [
            candidate_id
            for window in plan["windows"]
            for candidate_id in window["owner_candidate_ids"]
        ]
        self.assertEqual(self.observation["candidate_order"], owned)
        self.assertEqual(len(owned), len(set(owned)))
        with self.assertRaisesRegex(
            PdfStructuralRowWindowError,
            "pdf_structural_window_factory_required",
        ):
            PdfStructuralRowWindowRuntime(planner.config)

    def test_330_atoms_use_two_windows_and_192_stays_on_whole_table_path(
        self,
    ) -> None:
        planner = PdfStructuralRowWindowFactory().create()
        observation_330 = _observation(_projection_bands((165, 165)))
        plan = planner.plan(observation_330)
        self.assertEqual(330, plan["candidate_atoms"])
        self.assertEqual(2, plan["window_count"])
        self.assertEqual([165, 165], [w["owner_atom_count"] for w in plan["windows"]])

        projection_192 = _projection_bands((96, 96))
        observation_192 = _observation(projection_192)
        self.assertEqual("whole_table", planner.execution_mode(observation_192))
        provider = _WindowProvider()
        runtime = PdfStructuralRepairRuntimeFactory().create(provider=provider)
        geometry_192 = PdfParserGeometryFactory().create().build_observation(
            document_ref="document-window",
            pdf_sha256="pdf-window-sha",
            page_ref="page-window-1",
            page_number=1,
            table_ref="table-window-1",
            table_bbox=[0.0, 0.0, 200.0, 100.0],
            pdf_text_layer_projection=projection_192,
        )
        png_bytes = b"whole-table-192"
        package = PdfVisualTopologyFactory().create().build_package(
            parser_observation=observation_192,
            crop_manifest=_crop_manifest(png_bytes, crop_id="whole-192"),
        )
        provider.package_id = package["package_id"]
        result = runtime.run_target(
            target_id="whole_192",
            parser_observation=observation_192,
            parser_geometry_observation=geometry_192,
            visual_package=package,
            png_bytes=png_bytes,
            provider_qualification=runtime.qualify_provider(),
        )
        self.assertEqual("accepted_unique_consensus", result["runtime_terminal_status"])
        self.assertEqual((2, 2), (provider.count_calls, provider.generate_calls))

    def test_plan_tampering_missing_duplicate_and_crossing_atom_fail_closed(
        self,
    ) -> None:
        planner = PdfStructuralRowWindowFactory().create()
        plan = planner.plan(self.observation)

        tampered_hash = copy.deepcopy(plan)
        tampered_hash["plan_hash"] = "forged"
        self.assertIn(
            "pdf_structural_window_plan_hash_invalid",
            planner.validate_plan(
                parser_observation=self.observation,
                plan=tampered_hash,
            ),
        )

        missing = copy.deepcopy(plan)
        missing["windows"][1]["owner_candidate_ids"].pop()
        missing["windows"][1]["owner_atom_count"] -= 1
        _resign_plan(missing)
        self.assertIn(
            "pdf_structural_window_candidate_ownership_invalid",
            planner.validate_plan(
                parser_observation=self.observation,
                plan=missing,
            ),
        )

        duplicate = copy.deepcopy(plan)
        duplicate["windows"][1]["owner_candidate_ids"][0] = duplicate[
            "windows"
        ][0]["owner_candidate_ids"][0]
        _resign_plan(duplicate)
        self.assertIn(
            "pdf_structural_window_candidate_ownership_invalid",
            planner.validate_plan(
                parser_observation=self.observation,
                plan=duplicate,
            ),
        )

        crossing_cut = copy.deepcopy(plan)
        crossing_cut["windows"][0]["core_bbox"][3] = 35.0
        crossing_cut["windows"][1]["core_bbox"][1] = 35.0
        crossing_cut["windows"][0]["core_y_normalized_in_table"][1] = 0.35
        crossing_cut["windows"][1]["core_y_normalized_in_table"][0] = 0.35
        crossing_cut["windows"][0]["core_y_normalized_in_crop"][1] = round(
            35.0 / 90.0, 9
        )
        crossing_cut["windows"][1]["core_y_normalized_in_crop"][0] = round(
            25.0 / 90.0, 9
        )
        _resign_plan(crossing_cut)
        self.assertIn(
            "pdf_structural_window_safe_cut_unavailable",
            planner.validate_plan(
                parser_observation=self.observation,
                plan=crossing_cut,
            ),
        )

        crossing_observation = _observation(
            _projection_bands((96, 96), crossing_atom=True)
        )
        with self.assertRaisesRegex(
            PdfStructuralRowWindowError,
            "pdf_structural_window_owner_band_budget_exceeded",
        ):
            planner.plan(crossing_observation)

    def test_windowed_runtime_uses_exact_2w_calls_and_never_sends_ledger(self) -> None:
        provider = _WindowProvider()
        runtime = PdfStructuralRepairRuntimeFactory().create(provider=provider)
        plan = runtime.plan_windowed_target(self.observation)
        full_png = b"full-ledger-png"
        full_package = runtime.build_windowed_ledger_package(
            parser_observation=self.observation,
            crop_manifest=_crop_manifest(full_png, crop_id="full-ledger"),
        )
        visual = PdfVisualTopologyFactory().create()
        window_inputs = []
        for window in plan["windows"]:
            png_bytes = b"window-png-" + str(window["window_index"]).encode()
            package = visual.build_window_package(
                parser_observation=self.observation,
                full_package=full_package,
                window_plan=plan,
                window=window,
                crop_manifest=_crop_manifest(
                    png_bytes,
                    crop_id=f"window-{window['window_index']}",
                    bbox=window["crop_bbox"],
                ),
            )
            self.assertLessEqual(
                package["component_accounting"]["atom_count"], 192
            )
            self.assertNotIn("private-value", repr(package["model_facing"]))
            self.assertIn(
                "continuation_required MUST be false",
                package["model_facing"]["task"],
            )
            window_inputs.append(
                {
                    "window_id": window["window_id"],
                    "window_package": package,
                    "png_bytes": png_bytes,
                }
            )

        result = runtime.run_windowed_target(
            target_id="windowed_193",
            parser_observation=self.observation,
            parser_geometry_observation=self.geometry,
            visual_package=full_package,
            window_plan=plan,
            window_inputs=window_inputs,
            provider_qualification=runtime.qualify_provider(),
        )

        self.assertFalse(full_package["provider_input_allowed"])
        self.assertEqual("accepted_unique_consensus", result["runtime_terminal_status"])
        self.assertEqual(4, provider.count_calls)
        self.assertEqual(4, provider.generate_calls)
        self.assertEqual(4, result["new_provider_count_token_calls"])
        self.assertEqual(4, result["new_provider_generate_calls"])
        self.assertEqual(4, result["safe_summary"]["attempts_expected"])
        self.assertEqual(2, len(result["window_stitches"]))
        self.assertTrue(
            all(item["attempts_mixed"] is False for item in result["window_stitches"])
        )
        provider_attempt_ids = {
            item["provider_attempt"]["attempt_id"] for item in result["journal"]
        }
        self.assertTrue(
            all(
                item["composite_attempt_id"] not in provider_attempt_ids
                for item in result["window_stitches"]
            )
        )
        self.assertNotIn(full_package["package_id"], provider.provider_package_ids)
        self.assertTrue(result["safe_summary"]["all_candidates_accounted"])
        self.assertEqual(0, result["materialization"]["model_invented_values_total"])
        self.assertEqual([], runtime.validate_result(result))

        tampered = copy.deepcopy(result["window_stitches"][0])
        tampered["window_attempt_ids"].reverse()
        self.assertIn(
            "pdf_structural_window_stitch_lineage_invalid",
            runtime.windowing.validate_stitch(tampered),
        )
        with self.assertRaisesRegex(
            PdfStructuralRowWindowError,
            "pdf_structural_window_stitch_input_invalid",
        ):
            runtime.windowing.stitch_attempt(
                plan=plan,
                full_package_id=full_package["package_id"],
                window_packages=[item["window_package"] for item in window_inputs],
                topology_responses=[
                    _response(
                        item["window_package"]["package_id"],
                        header_row_count=1 if index == 1 else 0,
                        rows=(
                            [
                                0.0,
                                plan["windows"][0][
                                    "core_y_normalized_in_crop"
                                ][1],
                                1.0,
                            ]
                            if index == 1
                            else [
                                0.0,
                                plan["windows"][1][
                                    "core_y_normalized_in_crop"
                                ][0],
                                1.0,
                            ]
                        ),
                    )
                    for index, item in enumerate(window_inputs, start=1)
                ],
                window_attempt_ids=["window_1_a1", "window_2_a2"],
                attempt_number=1,
            )

    def test_invalid_window_response_does_not_abort_exact_2w_schedule(self) -> None:
        provider = _FirstWindowContinuationProvider()
        runtime = PdfStructuralRepairRuntimeFactory().create(provider=provider)
        plan = runtime.plan_windowed_target(self.observation)
        full_package = runtime.build_windowed_ledger_package(
            parser_observation=self.observation,
            crop_manifest=_crop_manifest(b"invalid-ledger", crop_id="invalid-ledger"),
        )
        packages = self._window_packages(
            runtime=runtime,
            observation=self.observation,
            plan=plan,
            full_package=full_package,
        )
        window_inputs = [
            {
                "window_id": window["window_id"],
                "window_package": package,
                "png_bytes": b"edge-window-" + str(index).encode(),
            }
            for index, (window, package) in enumerate(
                zip(plan["windows"], packages), start=1
            )
        ]

        result = runtime.run_windowed_target(
            target_id="window_invalid_first_response",
            parser_observation=self.observation,
            parser_geometry_observation=self.geometry,
            visual_package=full_package,
            window_plan=plan,
            window_inputs=window_inputs,
            provider_qualification=runtime.qualify_provider(),
        )

        self.assertEqual((4, 4), (provider.count_calls, provider.generate_calls))
        self.assertEqual(4, len(result["journal"]))
        self.assertEqual([2], [item["attempt_number"] for item in result["window_stitches"]])
        self.assertEqual("no_valid_consensus", result["runtime_terminal_status"])
        self.assertEqual(
            ["pdf_structural_window_response_invalid"],
            result["safe_summary"]["reason_codes"],
        )
        self.assertEqual([], runtime.validate_result(result))

    def test_window_budget_block_preserves_observed_total_without_generate(self) -> None:
        provider = _WindowProvider(counted_tokens=20_001)
        runtime = PdfStructuralRepairRuntimeFactory().create(provider=provider)
        plan = runtime.plan_windowed_target(self.observation)
        full_package = runtime.build_windowed_ledger_package(
            parser_observation=self.observation,
            crop_manifest=_crop_manifest(b"budget-ledger", crop_id="budget-ledger"),
        )
        packages = self._window_packages(
            runtime=runtime,
            observation=self.observation,
            plan=plan,
            full_package=full_package,
        )
        window_inputs = [
            {
                "window_id": window["window_id"],
                "window_package": package,
                "png_bytes": b"edge-window-" + str(index).encode(),
            }
            for index, (window, package) in enumerate(
                zip(plan["windows"], packages), start=1
            )
        ]
        result = runtime.run_windowed_target(
            target_id="window_budget_block",
            parser_observation=self.observation,
            parser_geometry_observation=self.geometry,
            visual_package=full_package,
            window_plan=plan,
            window_inputs=window_inputs,
            provider_qualification=runtime.qualify_provider(),
        )

        self.assertEqual("preflight_blocked", result["runtime_terminal_status"])
        self.assertEqual(1, provider.count_calls)
        self.assertEqual(0, provider.generate_calls)
        self.assertEqual([20_001], result["safe_summary"]["counted_input_tokens"])
        self.assertEqual(
            ["pdf_structural_repair_counted_input_budget_exceeded"],
            result["safe_summary"]["reason_codes"],
        )
        self.assertEqual(20_000, runtime.config.maximum_counted_input_tokens)

    def test_stitch_fails_closed_on_column_or_cut_ambiguity(self) -> None:
        provider = _WindowProvider()
        runtime = PdfStructuralRepairRuntimeFactory().create(provider=provider)
        plan = runtime.plan_windowed_target(self.observation)
        full_png = b"full-ledger-png"
        full_package = runtime.build_windowed_ledger_package(
            parser_observation=self.observation,
            crop_manifest=_crop_manifest(full_png, crop_id="full-ledger"),
        )
        visual = PdfVisualTopologyFactory().create()
        packages = []
        for window in plan["windows"]:
            png_bytes = b"window-png-" + str(window["window_index"]).encode()
            packages.append(
                visual.build_window_package(
                    parser_observation=self.observation,
                    full_package=full_package,
                    window_plan=plan,
                    window=window,
                    crop_manifest=_crop_manifest(
                        png_bytes,
                        crop_id=f"window-{window['window_index']}",
                        bbox=window["crop_bbox"],
                    ),
                )
            )
        responses = [
            _response(
                packages[0]["package_id"],
                header_row_count=1,
                rows=[
                    0.0,
                    plan["windows"][0]["core_y_normalized_in_crop"][1],
                    1.0,
                ],
            ),
            _response(
                packages[1]["package_id"],
                header_row_count=0,
                rows=[
                    0.0,
                    plan["windows"][1]["core_y_normalized_in_crop"][0],
                    1.0,
                ],
                columns=[0.0, 0.75, 1.0],
            ),
        ]
        with self.assertRaisesRegex(
            PdfStructuralRowWindowError,
            "pdf_structural_window_column_ambiguity",
        ):
            runtime.windowing.stitch_attempt(
                plan=plan,
                full_package_id=full_package["package_id"],
                window_packages=packages,
                topology_responses=responses,
                window_attempt_ids=["window_1_a1", "window_2_a1"],
                attempt_number=1,
            )

        responses[1] = _response(
            packages[1]["package_id"],
            header_row_count=0,
            rows=[0.0, 0.75, 1.0],
        )
        with self.assertRaisesRegex(
            PdfStructuralRowWindowError,
            "pdf_structural_window_boundary_ambiguity",
        ):
            runtime.windowing.stitch_attempt(
                plan=plan,
                full_package_id=full_package["package_id"],
                window_packages=packages,
                topology_responses=responses,
                window_attempt_ids=["window_1_a1", "window_2_a1"],
                attempt_number=1,
            )

    def test_no_shared_multiline_boundary_span_crossing_and_product_overflow_block(
        self,
    ) -> None:
        runtime = PdfStructuralRepairRuntimeFactory().create(
            provider=_WindowProvider()
        )
        plan = runtime.plan_windowed_target(self.observation)
        full_package = runtime.build_windowed_ledger_package(
            parser_observation=self.observation,
            crop_manifest=_crop_manifest(b"edge-ledger", crop_id="edge-ledger"),
        )
        packages = self._window_packages(
            runtime=runtime,
            observation=self.observation,
            plan=plan,
            full_package=full_package,
        )
        first_rows = [
            0.0,
            plan["windows"][0]["core_y_normalized_in_crop"][1],
            1.0,
        ]
        second_rows = [
            0.0,
            plan["windows"][1]["core_y_normalized_in_crop"][0],
            1.0,
        ]
        no_shared_boundary = [
            _response(
                packages[0]["package_id"],
                header_row_count=1,
                rows=first_rows,
            ),
            _response(
                packages[1]["package_id"],
                header_row_count=0,
                rows=[0.0, 0.8, 1.0],
            ),
        ]
        with self.assertRaisesRegex(
            PdfStructuralRowWindowError,
            "pdf_structural_window_boundary_ambiguity",
        ):
            runtime.windowing.stitch_attempt(
                plan=plan,
                full_package_id=full_package["package_id"],
                window_packages=packages,
                topology_responses=no_shared_boundary,
                window_attempt_ids=["window_1_a1", "window_2_a1"],
                attempt_number=1,
            )

        crossing_span = [
            _response(
                packages[0]["package_id"],
                header_row_count=1,
                rows=first_rows,
            ),
            _response(
                packages[1]["package_id"],
                header_row_count=0,
                rows=second_rows,
            ),
        ]
        crossing_span[0]["hypotheses"][0]["spans"] = [
            {
                "start_row": 1,
                "end_row": 2,
                "start_column": 1,
                "end_column": 1,
                "relation": "merged",
            }
        ]
        with self.assertRaisesRegex(
            PdfStructuralRowWindowError,
            "pdf_structural_window_span_ambiguity",
        ):
            runtime.windowing.stitch_attempt(
                plan=plan,
                full_package_id=full_package["package_id"],
                window_packages=packages,
                topology_responses=crossing_span,
                window_attempt_ids=["window_1_a1", "window_2_a1"],
                attempt_number=1,
            )

        strict_planner = PdfStructuralRowWindowFactory(
            PdfStructuralRowWindowConfig(maximum_alternative_combinations=1)
        ).create()
        strict_plan = strict_planner.plan(self.observation)
        strict_packages = self._window_packages(
            runtime=runtime,
            observation=self.observation,
            plan=strict_plan,
            full_package=full_package,
        )
        alternatives = []
        for index, package in enumerate(strict_packages):
            rows = (
                [
                    0.0,
                    strict_plan["windows"][0][
                        "core_y_normalized_in_crop"
                    ][1],
                    1.0,
                ]
                if index == 0
                else [
                    0.0,
                    strict_plan["windows"][1][
                        "core_y_normalized_in_crop"
                    ][0],
                    1.0,
                ]
            )
            response = _response(
                package["package_id"],
                header_row_count=1 if index == 0 else 0,
                rows=rows,
            )
            alternative = copy.deepcopy(response["hypotheses"][0])
            alternative["hypothesis_key"] = "alternate"
            response["hypotheses"].append(alternative)
            response["decision"] = "ambiguous"
            alternatives.append(response)
        with self.assertRaisesRegex(
            PdfStructuralRowWindowError,
            "pdf_structural_window_alternative_ambiguity",
        ):
            strict_planner.stitch_attempt(
                plan=strict_plan,
                full_package_id=full_package["package_id"],
                window_packages=strict_packages,
                topology_responses=alternatives,
                window_attempt_ids=["window_1_a1", "window_2_a1"],
                attempt_number=1,
            )


def _response(
    package_id: str,
    *,
    header_row_count: int,
    rows: list[float] | None = None,
    columns: list[float] | None = None,
) -> dict:
    return {
        "schema_version": PDF_VISUAL_TOPOLOGY_RESPONSE_SCHEMA,
        "package_id": package_id,
        "decision": "bound",
        "alternatives_complete": True,
        "hypotheses": [
            {
                "hypothesis_key": "primary",
                "row_boundaries": rows or [0.0, 0.5, 1.0],
                "column_boundaries": columns or [0.0, 0.5, 1.0],
                "header_row_count": header_row_count,
                "spans": [],
                "header_hierarchy": [],
                "continuation_required": False,
                "uncertainty_codes": [],
            }
        ],
        "uncertainty_codes": [],
    }


def _projection_193() -> dict:
    bboxes = []
    words = []
    for ordinal in range(1, 194):
        top_band = ordinal <= 97
        left_column = ordinal % 2 == 1
        bbox = [
            10.0 if left_column else 110.0,
            10.0 if top_band else 60.0,
            90.0 if left_column else 190.0,
            40.0 if top_band else 90.0,
        ]
        bbox_ref = f"bbox-{ordinal}"
        bboxes.append({"bbox_ref": bbox_ref, "bbox": bbox})
        words.append(
            {
                "parser_ordinal": ordinal,
                "word_ref": f"word-{ordinal}",
                "page_ref": "page-window-1",
                "bbox_ref": bbox_ref,
                "text": f"private-value-{ordinal}",
                "geometry_reading_order": ordinal,
                "text_checksum_ref": f"text-checksum-{ordinal}",
                "source_value_ref": f"source-{ordinal}",
            }
        )
    vector_specs = (
        [0.0, 0.0, 0.0, 100.0],
        [100.0, 0.0, 100.0, 100.0],
        [200.0, 0.0, 200.0, 100.0],
        [0.0, 0.0, 200.0, 0.0],
        [0.0, 50.0, 200.0, 50.0],
        [0.0, 100.0, 200.0, 100.0],
    )
    vectors = []
    for ordinal, bbox in enumerate(vector_specs, start=1):
        bbox_ref = f"vector-bbox-{ordinal}"
        bboxes.append({"bbox_ref": bbox_ref, "bbox": list(bbox)})
        vectors.append(
            {
                "parser_ordinal": ordinal,
                "object_ref": f"vector-{ordinal}",
                "page_ref": "page-window-1",
                "bbox_ref": bbox_ref,
                "linewidth": 0.5,
            }
        )
    return {
        "bbox_inventory": bboxes,
        "word_inventory": words,
        "line_inventory": [],
        "vector_line_inventory": vectors,
        "rect_inventory": [],
    }


def _projection_bands(
    band_sizes: tuple[int, ...],
    *,
    crossing_atom: bool = False,
) -> dict:
    if len(band_sizes) != 2:
        raise ValueError("test helper requires two vertical bands")
    bboxes = []
    words = []
    ordinal = 0
    for band_index, band_size in enumerate(band_sizes):
        for item_index in range(band_size):
            ordinal += 1
            left_column = item_index % 2 == 0
            bbox = [
                10.0 if left_column else 110.0,
                10.0 if band_index == 0 else 60.0,
                90.0 if left_column else 190.0,
                40.0 if band_index == 0 else 90.0,
            ]
            bbox_ref = f"bbox-{ordinal}"
            bboxes.append({"bbox_ref": bbox_ref, "bbox": bbox})
            words.append(
                {
                    "parser_ordinal": ordinal,
                    "word_ref": f"word-{ordinal}",
                    "page_ref": "page-window-1",
                    "bbox_ref": bbox_ref,
                    "text": f"private-value-{ordinal}",
                    "geometry_reading_order": ordinal,
                    "text_checksum_ref": f"text-checksum-{ordinal}",
                    "source_value_ref": f"source-{ordinal}",
                }
            )
    if crossing_atom:
        ordinal += 1
        bbox_ref = f"bbox-{ordinal}"
        bboxes.append(
            {"bbox_ref": bbox_ref, "bbox": [50.0, 30.0, 70.0, 70.0]}
        )
        words.append(
            {
                "parser_ordinal": ordinal,
                "word_ref": f"word-{ordinal}",
                "page_ref": "page-window-1",
                "bbox_ref": bbox_ref,
                "text": "private-crossing-value",
                "geometry_reading_order": ordinal,
                "text_checksum_ref": f"text-checksum-{ordinal}",
                "source_value_ref": f"source-{ordinal}",
            }
        )
    vectors = []
    for vector_ordinal, bbox in enumerate(
        (
            [0.0, 0.0, 0.0, 100.0],
            [100.0, 0.0, 100.0, 100.0],
            [200.0, 0.0, 200.0, 100.0],
            [0.0, 0.0, 200.0, 0.0],
            [0.0, 50.0, 200.0, 50.0],
            [0.0, 100.0, 200.0, 100.0],
        ),
        start=1,
    ):
        bbox_ref = f"vector-bbox-{vector_ordinal}"
        bboxes.append({"bbox_ref": bbox_ref, "bbox": list(bbox)})
        vectors.append(
            {
                "parser_ordinal": vector_ordinal,
                "object_ref": f"vector-{vector_ordinal}",
                "page_ref": "page-window-1",
                "bbox_ref": bbox_ref,
                "linewidth": 0.5,
            }
        )
    return {
        "bbox_inventory": bboxes,
        "word_inventory": words,
        "line_inventory": [],
        "vector_line_inventory": vectors,
        "rect_inventory": [],
    }


def _observation(projection: dict) -> dict:
    return PdfDualOracleContractFactory().create().build_parser_observation_from_word_atoms(
        document_ref="document-window",
        pdf_sha256="pdf-window-sha",
        page_ref="page-window-1",
        page_number=1,
        table_ref="table-window-1",
        table_bbox=[0.0, 0.0, 200.0, 100.0],
        pdf_text_layer_projection=projection,
    )


def _resign_plan(plan: dict) -> None:
    plan["plan_hash"] = sha256_json(
        {key: value for key, value in plan.items() if key != "plan_hash"}
    )


def _crop_manifest(
    png_bytes: bytes,
    *,
    crop_id: str,
    bbox: list[float] | None = None,
) -> dict:
    crop_bbox = [float(value) for value in (bbox or [0.0, 0.0, 200.0, 100.0])]
    width = 400
    height = max(1, round(width * (crop_bbox[3] - crop_bbox[1]) / 200.0))
    value = {
        "schema_version": "broker_reports_pdf_table_crop_v1",
        "policy_version": "pdf_table_raster_policy_v1",
        "crop_id": crop_id,
        "document_ref": "document-window",
        "pdf_sha256": "pdf-window-sha",
        "page_number": 1,
        "table_ref": "table-window-1",
        "declared_table_bbox": crop_bbox,
        "rendered_bbox": crop_bbox,
        "source_coordinate_space": "pdf_top_left_points",
        "pixel_coordinate_space": "crop_top_left_pixels",
        "source_to_pixel_transform": {
            "scale_x": width / (crop_bbox[2] - crop_bbox[0]),
            "scale_y": height / (crop_bbox[3] - crop_bbox[1]),
            "translate_source_x": -crop_bbox[0],
            "translate_source_y": -crop_bbox[1],
        },
        "renderer": "pymupdf",
        "renderer_version": "1.26.5",
        "page_rotation": 0,
        "applied_rotation": 0,
        "padding_points": 0.0,
        "dpi": 150,
        "dpi_revision_reason": "primary_150_dpi",
        "width": width,
        "height": height,
        "pixels": width * height,
        "png_bytes": len(png_bytes),
        "png_sha256": hashlib.sha256(png_bytes).hexdigest(),
        "lossless": True,
        "silent_resize_performed": False,
    }
    value["manifest_hash"] = sha256_json(value)
    return value


if __name__ == "__main__":
    unittest.main()
