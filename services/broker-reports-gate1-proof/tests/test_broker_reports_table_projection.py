from __future__ import annotations

import copy
import json
import tempfile
import time
import unittest
from pathlib import Path

from broker_reports_gate1 import (
    ArtifactAccessContext,
    ArtifactStoreConfig,
    ArtifactStoreFactory,
    FileInput,
    FullSourceArtifactFactory,
    Gate1Normalizer,
    Gate2InputReadinessFactory,
    Gate2InputReadinessConfig,
    Gate2SourceUnitRouterFactory,
    Gate2SourceUnitSegmenterFactory,
    Gate2TablePackageFactory,
    NormalizedTableProjectionConfig,
    NormalizedTableProjectionFactory,
    TableProjectionValidator,
    build_retention_policy,
    persist_gate1_result,
    resolve_source_value,
    resolve_source_values,
    validate_gate2_table_package,
)
from broker_reports_gate1.table_projection import FACTORY_REQUIRED, FORBIDDEN
from tests.test_broker_reports_gate1_backend_contract import (
    BrokerReportsGate1BackendContractTest,
)
from tests.test_broker_reports_pdf_layout_slice2 import (
    _aligned_table_pdf,
    _pdf_bytes,
    _paragraph_pdf,
    _ruled_table_pdf,
)


def _repeated_header_wrapped_pdf() -> bytes:
    texts = [
        (30, 235, "Date"),
        (150, 235, "Note"),
        (30, 205, "2026-01-01"),
        (150, 205, "First"),
        (30, 175, "Date"),
        (150, 175, "Note"),
        (30, 148, "2026-01-02"),
        (150, 151, "Wrapped"),
        (150, 139, "value"),
        (30, 115, "Total"),
        (150, 115, "2"),
        (30, 30, "Synthetic Footer"),
    ]
    vectors = [
        f"20 {y} m 300 {y} l S" for y in (100, 130, 160, 190, 220, 250)
    ] + [
        "20 100 m 20 250 l S",
        "130 100 m 130 250 l S",
        "300 100 m 300 250 l S",
    ]
    return _pdf_bytes([{"texts": texts, "vectors": vectors}])


def _broker_profile_ruled_table_pdf() -> bytes:
    rows = [
        (220, ("Date", "Amount", "Currency")),
        (195, ("1", "2", "3")),
        (170, ("2026-01-01", "10.00", "USD")),
        (145, ("Total", "10.00", "USD")),
    ]
    texts = [
        item
        for y, values in rows
        for item in zip((30, 125, 225), (y, y, y), values)
    ]
    vectors = [
        f"20 {y} m 300 {y} l S" for y in (130, 155, 180, 205, 230)
    ] + [
        "20 130 m 20 230 l S",
        "110 130 m 110 230 l S",
        "210 130 m 210 230 l S",
        "300 130 m 300 230 l S",
    ]
    return _pdf_bytes([{"texts": texts, "vectors": vectors}])


class BrokerReportsTableProjectionTest(unittest.TestCase):
    def test_batch_source_value_lookup_indexes_entries_and_private_values_once(self):
        rows = ["Date,Amount,Note"] + [
            f"2026-01-{(index % 28) + 1:02d},{index}.00,row-{index}"
            for index in range(1, 201)
        ]
        result = Gate1Normalizer().normalize(
            [
                FileInput.from_bytes(
                    private_ref="batch-source-values",
                    filename="batch_source_values.csv",
                    content=("\n".join(rows) + "\n").encode("utf-8"),
                    mime_type="text/csv",
                )
            ],
            input_context={"clarification_criticality_refinement_enabled": True},
        )
        projection = copy.deepcopy(
            result.package["private_normalized_table_projections"][0]
        )

        class CountingList(list):
            def __init__(self, values):
                super().__init__(values)
                self.iterations = 0

            def __iter__(self):
                self.iterations += 1
                return super().__iter__()

        source_index = CountingList(projection["source_value_index"])
        private_values = CountingList(projection["private_values"])
        projection["source_value_index"] = source_index
        projection["private_values"] = private_values
        refs = list(projection["source_value_refs"])

        resolved = resolve_source_values(projection, refs)

        self.assertEqual(len(resolved), len(refs))
        self.assertEqual(source_index.iterations, 1)
        self.assertEqual(private_values.iterations, 1)
        for source_value_ref in refs[:10]:
            self.assertEqual(
                resolved[source_value_ref],
                resolve_source_value(projection, source_value_ref),
            )

    def test_batch_source_value_lookup_preserves_failure_codes(self):
        result = Gate1Normalizer().normalize(
            [
                FileInput.from_bytes(
                    private_ref="batch-source-value-errors",
                    filename="batch_source_value_errors.csv",
                    content=b"Date,Amount\n2026-01-01,10.00\n",
                    mime_type="text/csv",
                )
            ],
            input_context={"clarification_criticality_refinement_enabled": True},
        )
        projection = result.package["private_normalized_table_projections"][0]
        source_value_ref = str(projection["source_value_refs"][0])

        duplicate = copy.deepcopy(projection)
        duplicate["source_value_index"].append(
            copy.deepcopy(
                next(
                    item
                    for item in duplicate["source_value_index"]
                    if item["source_value_ref"] == source_value_ref
                )
            )
        )
        with self.assertRaisesRegex(
            ValueError, "source_value_ref_not_unique_or_missing"
        ):
            resolve_source_values(duplicate, [source_value_ref])

        with self.assertRaisesRegex(
            ValueError, "source_value_ref_not_unique_or_missing"
        ):
            resolve_source_values(projection, ["srcval_missing"])

        checksum = copy.deepcopy(projection)
        checksum_entry = next(
            item
            for item in checksum["source_value_index"]
            if item["source_value_ref"] == source_value_ref
        )
        checksum_entry["value_checksum_ref"] = "valuechk_foreign"
        with self.assertRaisesRegex(ValueError, "source_value_checksum_mismatch"):
            resolve_source_values(checksum, [source_value_ref])

        duplicate_private_value = copy.deepcopy(projection)
        target_entry = next(
            item
            for item in duplicate_private_value["source_value_index"]
            if item["source_value_ref"] == source_value_ref
        )
        value_path_ref = target_entry["value_path"]["value_path_ref"]
        target_private_value = next(
            item
            for item in duplicate_private_value["private_values"]
            if item["value_path_ref"] == value_path_ref
        )
        duplicate_private_value["private_values"].append(
            copy.deepcopy(target_private_value)
        )
        with self.assertRaisesRegex(ValueError, "source_value_path_invalid"):
            resolve_source_values(duplicate_private_value, [source_value_ref])

    def test_native_composite_cash_headers_are_mechanically_normalized(self):
        result = Gate1Normalizer().normalize(
            [
                FileInput.from_bytes(
                    private_ref="native-cash-headers",
                    filename="synthetic.csv",
                    content=(
                        "Дата,Торговая площадка,Описание операции,Валюта,"
                        "Сумма зачисления,Сумма списания\n"
                        "12.12.2022,Основной рынок,Списание д/с,RUB,0.00,2400000.00\n"
                    ).encode("utf-8"),
                    mime_type="text/csv",
                )
            ],
            input_context={"clarification_criticality_refinement_enabled": True},
        )
        projection = result.package["private_normalized_table_projections"][0]

        self.assertEqual(
            [
                item["normalized_label"]
                for item in projection["header_model"]["column_labels"]
            ],
            ["date", "market", "operation", "currency", "amount", "amount"],
        )

    def test_factory_anchors_and_native_csv_html_xlsx_projection(self):
        self.assertIn("NormalizedTableProjectionFactory.create", FACTORY_REQUIRED)
        self.assertIn("must not mint replacement row, cell or source-value refs", FORBIDDEN)
        xlsx = BrokerReportsGate1BackendContractTest()._synthetic_xlsx_bytes()
        result = Gate1Normalizer().normalize(
            [
                FileInput.from_bytes(
                    private_ref="native-csv",
                    filename="synthetic.csv",
                    content=(
                        b'Date,Amount,Note\n'
                        b'2026-01-01,10,"wrapped\nvalue"\n'
                        b'Total,10,summary\n'
                    ),
                    mime_type="text/csv",
                ),
                FileInput.from_bytes(
                    private_ref="native-html",
                    filename="synthetic.html",
                    content=(
                        b"<table><tr><th>Date</th><th>Amount</th></tr>"
                        b"<tr><td>2026-01-01</td><td>10</td></tr></table>"
                    ),
                    mime_type="text/html",
                ),
                FileInput.from_bytes(
                    private_ref="native-xlsx",
                    filename="synthetic.xlsx",
                    content=xlsx,
                    mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                ),
            ],
            input_context={"clarification_criticality_refinement_enabled": True},
        )
        self.assertEqual(result.package["validation_result"]["status"], "passed")
        projections = result.package["private_normalized_table_projections"]
        self.assertEqual({item["source_format"] for item in projections}, {"csv", "html", "xlsx"})
        self.assertTrue(all(item["validator_status"] == "passed" for item in projections))
        self.assertTrue(all(item["coverage"]["coverage_status"] == "complete" for item in projections))
        csv_projection = next(item for item in projections if item["source_format"] == "csv")
        self.assertEqual(
            [item["row_role"] for item in csv_projection["rows"]],
            ["header_row", "data_row", "summary_row"],
        )
        self.assertTrue(any(item["multi_line_cell"] for item in csv_projection["cells"]))
        source_unit = next(
            item
            for item in result.package["private_normalized_source_units"]
            if item["unit_ref"] == csv_projection["source_unit_ref"]
        )
        self.assertEqual(csv_projection["row_refs"], source_unit["row_refs"])
        self.assertEqual(csv_projection["cell_refs"], source_unit["cell_refs"])
        self.assertEqual(
            set(csv_projection["source_value_refs"]),
            set(source_unit["source_value_refs"]),
        )

    def test_pdf_geometry_projection_fallback_and_no_semantic_truth(self):
        ruled = self._project_pdf(_ruled_table_pdf())
        projection = ruled.projections[0]
        self.assertEqual(projection["table_candidate_status"], "validated_geometry")
        self.assertEqual(projection["reconstruction_quality"], "high")
        self.assertFalse(projection["semantic_table_truth_claimed"])
        self.assertTrue(projection["geometry"]["contributing_word_refs"])
        self.assertTrue(projection["geometry"]["fallback_text_refs"])
        self.assertEqual(projection["coverage"]["duplicate_accounted_refs"], [])
        self.assertEqual(projection["coverage"]["unaccounted_refs"], [])

        aligned = self._project_pdf(_aligned_table_pdf())
        self.assertEqual(
            aligned.projections[0]["reconstruction_strategy"], "aligned_words"
        )
        ambiguous_build = FullSourceArtifactFactory().create().build(
            normalization_run_id="norm_ambiguous",
            document_id="doc_ambiguous",
            profile_id="profile_ambiguous",
            container_format="pdf",
            content_bytes=_aligned_table_pdf(ambiguous=True),
            source_checksum_sha256="b" * 64,
        )
        ambiguous = NormalizedTableProjectionFactory().create().build_for_document(
            source_format="pdf",
            payloads=ambiguous_build.payloads,
            source_units=ambiguous_build.units,
        )
        self.assertEqual(ambiguous.projections, [])
        self.assertTrue(
            all(
                unit.get("pdf_unit_type") == "pdf_line_cluster_unit"
                for unit in ambiguous_build.units
            )
        )
        non_table = self._project_pdf(_paragraph_pdf())
        self.assertEqual(non_table.projections, [])

        repeated = self._project_pdf(_repeated_header_wrapped_pdf())
        repeated_projection = repeated.projections[0]
        self.assertIn(
            "repeated_header_row",
            [item["row_role"] for item in repeated_projection["rows"]],
        )
        self.assertTrue(
            any(
                item["multi_line_cell"] and item["wrapped_text_cell"]
                for item in repeated_projection["cells"]
            )
        )
        self.assertTrue(repeated_projection["geometry"]["fallback_text_refs"])

    def test_pdf_candidate_rejection_preserves_fallback_coverage_without_fake_cells(self):
        built = FullSourceArtifactFactory().create().build(
            normalization_run_id="norm_reject",
            document_id="doc_reject",
            profile_id="profile_reject",
            container_format="pdf",
            content_bytes=_ruled_table_pdf(),
            source_checksum_sha256="c" * 64,
        )
        rejected = NormalizedTableProjectionFactory(
            NormalizedTableProjectionConfig(min_pdf_geometry_confidence=0.99)
        ).create().build_for_document(
            source_format="pdf",
            payloads=built.payloads,
            source_units=built.units,
        )
        projection = rejected.projections[0]
        self.assertEqual(projection["table_candidate_status"], "rejected_to_line_cluster")
        self.assertEqual(projection["projection_status"], "blocked")
        self.assertEqual(projection["cells"], [])
        self.assertEqual(projection["rows"], [])
        self.assertEqual(projection["coverage"]["coverage_status"], "complete")
        self.assertTrue(projection["coverage"]["fallback_text_refs"])
        self.assertTrue(projection["coverage"]["rejected_refs"])
        self.assertEqual(TableProjectionValidator().validate(projection)["validator_status"], "passed")

    def test_gate2_native_and_pdf_packages_route_segment_and_do_not_mutate_store(self):
        result = Gate1Normalizer().normalize(
            [
                FileInput.from_bytes(
                    private_ref="package-native",
                    filename="native.csv",
                    content=b"Date,Amount\n2026-01-01,10\nTotal,10\n",
                    mime_type="text/csv",
                ),
                FileInput.from_bytes(
                    private_ref="package-pdf",
                    filename="table.pdf",
                    content=_ruled_table_pdf(),
                    mime_type="application/pdf",
                ),
            ],
            input_context={"clarification_criticality_refinement_enabled": True},
        )
        self.assertEqual(result.package["validation_result"]["status"], "passed")
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            store = ArtifactStoreFactory(
                ArtifactStoreConfig(
                    mode="sqlite",
                    sqlite_path=root / "artifacts.sqlite3",
                    payload_root=root / "payloads",
                )
            ).create()
            run_id = result.package["normalization_run"]["run_id"]
            context = ArtifactAccessContext(
                user_id="table-user",
                normalization_run_id=run_id,
                case_id="table-case",
                chat_id="table-chat",
                workspace_model_id="table-model",
                allow_private=True,
                require_source_available=True,
            )
            manifest = persist_gate1_result(
                store=store,
                result=result,
                context=context,
                retention_policy=build_retention_policy(mode="api_smoke"),
            )
            before = [record.artifact_id for record in store.list_by_run(run_id)]
            readiness = Gate2InputReadinessFactory(
                store=store,
                config=Gate2InputReadinessConfig(prefer_table_projections=True),
            ).create().audit_and_build(
                domain_context_packet_ref=manifest.artifact_refs_by_type[
                    "domain_context_packet_v0"
                ][0],
                context=context,
            )
            after = [record.artifact_id for record in store.list_by_run(run_id)]
            self.assertEqual(readiness.validation["validator_status"], "passed")
            self.assertEqual(before, after)
            table_packages = [
                item
                for item in readiness.packages
                if item["package_mode"]
                == "gate2_normalized_table_projection_no_model_call"
            ]
            self.assertEqual(
                {item["source_unit"]["source_format"] for item in table_packages},
                {"csv"},
            )
            for package in table_packages:
                projection = next(
                    item
                    for item in result.package["private_normalized_table_projections"]
                    if item["table_projection_id"]
                    == package["source_unit"]["table_projection_id"]
                )
                self.assertEqual(
                    validate_gate2_table_package(package, projection)[
                        "validator_status"
                    ],
                    "passed",
                )
                self.assertFalse(package["prompt_contract"]["model_call_performed"])
                route = Gate2SourceUnitRouterFactory().create().route(package)
                self.assertTrue(route["coverage"]["all_selected_refs_routed"])
                segmentation = Gate2SourceUnitSegmenterFactory().create().segment(
                    base_package=package, parent_route=route
                )
                self.assertTrue(
                    segmentation.plan["coverage"][
                        "all_parent_selected_refs_partitioned"
                    ]
                )
            self.assertFalse(
                any(
                    record.storage_backend == "openwebui_knowledge"
                    for record in store.list_by_run(run_id)
                )
            )

            default_readiness = Gate2InputReadinessFactory(
                store=store
            ).create().audit_and_build(
                domain_context_packet_ref=manifest.artifact_refs_by_type[
                    "domain_context_packet_v0"
                ][0],
                context=context,
            )
            self.assertEqual(default_readiness.validation["validator_status"], "passed")
            self.assertGreater(
                default_readiness.validation["slice_audit"][
                    "unselected_scope_reason_counts"
                ].get("gate2_noncanonical_table_candidate_scope_blocked", 0),
                0,
            )
            self.assertTrue(
                all(
                    item["source_unit"].get("pdf_unit_type")
                    != "pdf_table_candidate_unit"
                    for item in default_readiness.packages
                )
            )

    def test_gate2_table_package_requires_eligible_quality_and_complete_coverage(self):
        projection = self._project_pdf(
            _broker_profile_ruled_table_pdf()
        ).projections[0]
        package = Gate2TablePackageFactory().create().build(
            projection=projection,
            case_id="table-eligibility-case",
        )

        low_quality = copy.deepcopy(projection)
        low_quality["reconstruction_quality"] = "low"
        low_quality["quality"]["reconstruction_quality"] = "low"
        with self.assertRaisesRegex(
            ValueError, "gate2_table_projection_quality_not_eligible"
        ):
            validate_gate2_table_package(package, low_quality)

        incomplete_coverage = copy.deepcopy(projection)
        incomplete_coverage["coverage"]["coverage_status"] = "partial"
        with self.assertRaisesRegex(
            ValueError, "gate2_table_projection_coverage_not_eligible"
        ):
            validate_gate2_table_package(package, incomplete_coverage)

        geometry_only = self._project_pdf(_ruled_table_pdf()).projections[0]
        with self.assertRaisesRegex(
            ValueError, "gate2_pdf_canonical_table_not_validated"
        ):
            Gate2TablePackageFactory().create().build(
                projection=geometry_only,
                case_id="table-eligibility-case",
            )

    def test_budget_overflow_is_blocked_and_performance_metrics_are_bounded(self):
        built = FullSourceArtifactFactory().create().build(
            normalization_run_id="norm_budget",
            document_id="doc_budget",
            profile_id="profile_budget",
            container_format="csv",
            content_bytes=b"A,B\n1,2\n3,4\n",
            source_checksum_sha256="d" * 64,
        )
        started = time.perf_counter()
        result = NormalizedTableProjectionFactory(
            NormalizedTableProjectionConfig(max_rows=2)
        ).create().build_for_document(
            source_format="csv",
            payloads=built.payloads,
            source_units=built.units,
        )
        elapsed_ms = (time.perf_counter() - started) * 1000
        projection = result.projections[0]
        payload_size = len(
            json.dumps(projection, ensure_ascii=False, sort_keys=True).encode("utf-8")
        )
        self.assertEqual(projection["projection_status"], "blocked")
        self.assertEqual(projection["reconstruction_quality"], "blocked")
        self.assertIn(
            "table_projection_row_budget_exceeded",
            projection["reconstruction_reason_codes"],
        )
        with self.assertRaisesRegex(ValueError, "gate2_table_projection_not_ready"):
            Gate2TablePackageFactory().create().build(
                projection=projection, case_id="budget-case"
            )
        self.assertLess(elapsed_ms, 2_000)
        self.assertLess(payload_size, 1_000_000)

    @staticmethod
    def _project_pdf(content: bytes):
        built = FullSourceArtifactFactory().create().build(
            normalization_run_id="norm_pdf_table",
            document_id="doc_pdf_table",
            profile_id="profile_pdf_table",
            container_format="pdf",
            content_bytes=content,
            source_checksum_sha256="a" * 64,
        )
        return NormalizedTableProjectionFactory().create().build_for_document(
            source_format="pdf",
            payloads=built.payloads,
            source_units=built.units,
        )


if __name__ == "__main__":
    unittest.main()
