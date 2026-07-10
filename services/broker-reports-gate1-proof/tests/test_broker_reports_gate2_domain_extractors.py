from __future__ import annotations

import sys
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from broker_reports_gate1.gate2_domain_contracts import (
    Gate2DomainPromptConfig,
    Gate2DomainPromptResolverFactory,
    domain_source_facts_response_format,
)
from broker_reports_gate1.gate2_source_fact_contracts import Gate2PromptUserContext
from broker_reports_gate1.gate2_domain_packages import (
    Gate2DomainPackageBuilderFactory,
    validate_domain_extraction_package,
)
from broker_reports_gate1.gate2_domain_finalization import (
    Gate2DomainCandidateFinalizerFactory,
)
from broker_reports_gate1.gate2_domain_routing import (
    Gate2SourceUnitRouterFactory,
    validate_source_unit_domain_route,
)
from broker_reports_gate1.gate2_source_fact_stitching import (
    Gate2SourceFactStitcherFactory,
    validate_source_fact_stitch_result,
)
from broker_reports_gate1.gate2_source_unit_segmentation import (
    FACTORY_REQUIRED as SEGMENTER_FACTORY_REQUIRED,
    FORBIDDEN as SEGMENTER_FORBIDDEN,
    Gate2SourceUnitSegmenterConfig,
    Gate2SourceUnitSegmenterFactory,
    mark_segmentation_selection,
    validate_source_unit_segmentation,
)
from broker_reports_gate1.gate2_domain_runtime import (
    FACTORY_REQUIRED as DOMAIN_RUNTIME_FACTORY_REQUIRED,
    FORBIDDEN as DOMAIN_RUNTIME_FORBIDDEN,
)


class BrokerReportsGate2DomainExtractorsTest(unittest.TestCase):
    def test_segmentation_and_domain_runtime_factory_antidrift_anchors(self):
        self.assertIn(
            "Gate2SourceUnitSegmenterFactory.create",
            SEGMENTER_FACTORY_REQUIRED,
        )
        self.assertIn("must not select private row ownership", SEGMENTER_FORBIDDEN)
        self.assertIn(
            "Gate2DomainSourceFactRuntimeFactory.create",
            DOMAIN_RUNTIME_FACTORY_REQUIRED,
        )
        self.assertIn("must not route", DOMAIN_RUNTIME_FORBIDDEN)

    def test_domain_finalizer_fills_only_package_bound_provenance_issues_and_mechanical_values(self):
        base = _base_package()
        route = Gate2SourceUnitRouterFactory().create().route(base)
        package = next(
            item
            for item in Gate2DomainPackageBuilderFactory().create().build(
                base_package=base, route=route, route_artifact_ref="art_route"
            )
            if item["extractor_domain"] == "income"
        )
        package["package_artifact_ref"] = "art_domain_package"
        package["expected_source_facts_set_id"] = "sfset_expected"
        package["expected_candidate_audit"] = {"prompt_ref": "prompt_income"}
        package["deterministic_value_candidates"] = [
            {
                "source_ref": "row_income",
                "field": "date",
                "source_value_ref": "value_2_2",
                "normalized_value": "2026-01-02",
            },
            {
                "source_ref": "row_income",
                "field": "amount",
                "source_value_ref": "value_2_3",
                "normalized_value": "10.00",
            },
            {
                "source_ref": "row_income",
                "field": "currency",
                "source_value_ref": "value_2_4",
                "normalized_value": "USD",
            },
        ]
        candidate = {
            "facts": [
                {
                    "fact_type": "income",
                    "source_location": {"row_ref": "row_income"},
                    "normalized_values": {
                        field: None
                        for field in (
                            "date",
                            "amount",
                            "currency",
                            "quantity",
                            "rate",
                            "converted_amount",
                            "identifier",
                            "label",
                        )
                    },
                    "original_value_refs": {
                        field: []
                        for field in (
                            "date",
                            "amount",
                            "currency",
                            "quantity",
                            "rate",
                            "converted_amount",
                            "identifier",
                            "label",
                        )
                    },
                    "completeness": "complete",
                    "downstream_use": {
                        "downstream_usable": True,
                        "gate3_ledger_candidate": True,
                        "cross_document_consolidation_allowed": True,
                        "tax_calculation_allowed": True,
                        "declaration_mapping_allowed": True,
                        "restriction_codes": [],
                    },
                }
            ],
            "coverage": {"no_fact_results": []},
        }
        finalized = Gate2DomainCandidateFinalizerFactory().create().finalize(
            candidate=candidate, package=package
        )
        fact = finalized["facts"][0]
        self.assertEqual(fact["normalized_values"]["amount"], "10.00")
        self.assertEqual(
            fact["original_value_refs"]["amount"], ["value_2_3"]
        )
        self.assertEqual(fact["amount"]["value_decimal"], "10.00")
        self.assertEqual(fact["source_location"]["row_ref"], "row_income")
        self.assertIn("row_income", fact["evidence_refs"])
        self.assertEqual(fact["linked_issue_refs"], ["issue_unresolved"])
        self.assertEqual(fact["completeness"], "partial")
        self.assertFalse(
            fact["downstream_use"]["cross_document_consolidation_allowed"]
        )
        self.assertFalse(fact["downstream_use"]["tax_calculation_allowed"])
        self.assertEqual(finalized["coverage"]["coverage_status"], "partial")

    def test_managed_domain_prompt_resolver_checks_domain_contract_and_metadata(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "webui.db"
            conn = sqlite3.connect(db_path)
            try:
                conn.execute(
                    """
                    CREATE TABLE prompt(
                        id TEXT PRIMARY KEY, command TEXT, user_id TEXT, name TEXT,
                        content TEXT, data TEXT, meta TEXT, tags TEXT,
                        version_id TEXT, is_active INTEGER
                    )
                    """
                )
                meta = {
                    "template_id": "broker_reports.income_extraction.v0",
                    "template_kind": "broker_reports_income_extraction",
                    "prompt_contract_id": "broker_reports_domain_source_fact_prompt_v0",
                    "input_contract": "broker_reports_domain_extraction_package_v0",
                    "output_schema_id": "broker_reports.source_facts.schema.v0",
                    "output_schema_version": "broker_reports_source_facts_v0",
                    "structured_output_required": True,
                    "extractor_domain": "income",
                    "gate": "gate2",
                }
                conn.execute(
                    """
                    INSERT INTO prompt(id, command, user_id, name, content, data, meta, tags, version_id, is_active)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                    """,
                    (
                        "broker_reports_gate2_income_prompt_v0",
                        "broker_gate2_income_v0",
                        "owner",
                        "Income",
                        "Domain prompt {{source_fact_package_json}}",
                        "{}",
                        json.dumps(meta),
                        json.dumps(["broker-reports-gate2-domain", "structured-output"]),
                        "v1",
                    ),
                )
                conn.commit()
            finally:
                conn.close()
            resolver = Gate2DomainPromptResolverFactory(
                Gate2DomainPromptConfig(db_path=db_path)
            ).create()
            prompt = resolver.resolve(
                "income", Gate2PromptUserContext(user_id="owner")
            )
            self.assertEqual(prompt.safe_metadata["extractor_domain"], "income")
            self.assertEqual(
                prompt.input_schema_version,
                "broker_reports_domain_extraction_package_v0",
            )

    def test_router_routes_clean_ambiguous_unknown_and_non_fact_refs_without_drop(self):
        package = _base_package()
        route = Gate2SourceUnitRouterFactory().create().route(package)
        validate_source_unit_domain_route(route)
        by_ref = {item["source_ref"]: item for item in route["route_entries"]}

        self.assertEqual(
            by_ref["row_trade"]["candidate_domains"], ["trade_operation"]
        )
        self.assertEqual(by_ref["row_income"]["candidate_domains"], ["income"])
        self.assertEqual(
            by_ref["row_withholding"]["candidate_domains"], ["withholding_tax"]
        )
        self.assertEqual(
            by_ref["row_fee"]["candidate_domains"], ["fee_commission"]
        )
        self.assertEqual(
            by_ref["row_cash"]["candidate_domains"], ["cash_movement"]
        )
        self.assertEqual(
            by_ref["row_ambiguous"]["candidate_domains"],
            ["income", "fee_commission"],
        )
        self.assertEqual(
            by_ref["row_unknown"]["candidate_domains"], ["unknown_source_row"]
        )
        self.assertEqual(by_ref["row_header"]["route_kind"], "deterministic_no_fact")
        self.assertEqual(by_ref["row_blank"]["route_kind"], "deterministic_no_fact")
        self.assertEqual(by_ref["row_layout"]["route_kind"], "deterministic_no_fact")
        self.assertTrue(route["coverage"]["all_selected_refs_routed"])
        self.assertEqual(route["coverage"]["selected_total"], 10)
        self.assertEqual(route["coverage"]["routed_total"], 10)
        self.assertEqual(route["issue_refs"], ["issue_unresolved"])

    def test_router_keeps_unicode_exact_labels_as_safe_helper_signals(self):
        package = _base_package()
        unknown = next(
            item
            for item in package["source_unit"]["model_source_projection"]["rows"]
            if item["row_ref"] == "row_unknown"
        )
        unknown["cells"][0]["value"] = "Комиссия брокера по операции"
        route = Gate2SourceUnitRouterFactory().create().route(package)
        routed = next(
            item
            for item in route["route_entries"]
            if item["source_ref"] == "row_unknown"
        )
        self.assertEqual(routed["candidate_domains"], ["fee_commission"])
        self.assertEqual(routed["confidence"], "high")

    def test_domain_packages_are_narrow_and_provider_schema_limits_fact_types(self):
        package = _base_package()
        route = Gate2SourceUnitRouterFactory().create().route(package)
        packages = Gate2DomainPackageBuilderFactory().create().build(
            base_package=package,
            route=route,
            route_artifact_ref="art_route",
        )
        by_domain = {item["extractor_domain"]: item for item in packages}
        income = by_domain["income"]
        fee = by_domain["fee_commission"]

        self.assertEqual(
            income["candidate_source_refs"], ["row_income", "row_ambiguous"]
        )
        self.assertEqual(
            fee["candidate_source_refs"], ["row_fee", "row_ambiguous"]
        )
        self.assertNotIn("row_trade", income["allowed_evidence_refs"])
        self.assertLess(
            len(income["allowed_source_value_refs"]),
            len(package["allowed_source_value_refs"]),
        )
        self.assertEqual(
            [
                item["row_ref"]
                for item in income["source_unit"]["model_source_projection"]["rows"]
            ],
            ["row_income", "row_ambiguous"],
        )
        self.assertEqual(
            len(income["source_unit"]["normalized_source_projection"]["cells"]), 2
        )
        validate_domain_extraction_package(income)
        response_format = domain_source_facts_response_format(income)
        variants = response_format["json_schema"]["schema"]["properties"][
            "facts"
        ]["items"]["anyOf"]
        self.assertEqual(
            {item["properties"]["fact_type"]["const"] for item in variants},
            {"income", "unknown_source_row"},
        )
        self.assertTrue(response_format["json_schema"]["strict"])
        self.assertEqual(
            response_format["json_schema"]["schema"]["properties"]["facts"][
                "maxItems"
            ],
            2,
        )
        income_variant = next(
            item
            for item in variants
            if item["properties"]["fact_type"]["const"] == "income"
        )
        self.assertEqual(
            set(
                income_variant["properties"]["evidence_refs"]["items"]["enum"]
            ),
            set(income["allowed_evidence_refs"]),
        )
        self.assertEqual(
            set(
                income_variant["properties"]["original_value_refs"][
                    "properties"
                ]["amount"]["items"]["enum"]
            ),
            set(income["allowed_source_value_refs"]),
        )
        self.assertEqual(income["allowed_issue_refs"], ["issue_unresolved"])

    def test_truncated_parent_is_partitioned_into_complete_typed_derived_units(self):
        package = _base_package()
        package["source_unit"]["source_slice_truncated"] = True
        package["source_unit"]["slice_payload_checksum_ref"] = "payload_checksum"
        parent_route = Gate2SourceUnitRouterFactory().create().route(package)
        result = Gate2SourceUnitSegmenterFactory(
            Gate2SourceUnitSegmenterConfig(
                table_max_selected_refs=2,
                text_max_selected_refs=2,
            )
        ).create().segment(base_package=package, parent_route=parent_route)
        validate_source_unit_segmentation(result.plan, result.derived_packages)

        coverage = result.plan["coverage"]
        self.assertEqual(coverage["parent_selected_total"], 10)
        self.assertEqual(coverage["derived_accounted_total"], 10)
        self.assertEqual(coverage["parent_remainder_status"], "pending_gate1_reslice")
        self.assertTrue(coverage["all_parent_selected_refs_partitioned"])
        self.assertEqual(
            [
                ref
                for item in result.plan["segments"]
                for ref in item["selected_source_refs"]
            ],
            parent_route["selected_source_refs"],
        )
        self.assertTrue(
            any(
                item["segment_kind"] == "unknown_coverage_cluster"
                for item in result.plan["segments"]
            )
        )
        self.assertTrue(
            any(
                item["segment_kind"] == "deterministic_no_fact_cluster"
                for item in result.plan["segments"]
            )
        )

        trade = next(
            item
            for item in result.derived_packages
            if item["segmentation"]["segment_kind"]
            == "typed_high_confidence_cluster"
            and item["segmentation"]["candidate_domains"] == ["trade_operation"]
        )
        trade_unit = trade["source_unit"]
        self.assertFalse(trade_unit["source_slice_truncated"])
        self.assertTrue(trade_unit["parent_source_slice_truncated"])
        self.assertEqual(trade_unit["source_checksum_ref"], "checksum_ref")
        self.assertEqual(trade_unit["slice_payload_checksum_ref"], "payload_checksum")
        self.assertEqual(trade["coverage_expectation"]["selected_source_refs"], ["row_trade"])
        self.assertEqual(trade["allowed_issue_refs"], ["issue_unresolved"])
        self.assertEqual(
            [item["row_ref"] for item in trade_unit["row_provenance"]],
            ["row_trade"],
        )
        self.assertLess(
            len(trade["allowed_source_value_refs"]),
            len(package["allowed_source_value_refs"]),
        )

        derived_route = Gate2SourceUnitRouterFactory().create().route(trade)
        self.assertEqual(
            derived_route["route_entries"][0]["candidate_domains"],
            ["trade_operation"],
        )
        self.assertEqual(derived_route["route_entries"][0]["confidence"], "high")
        domain_packages = Gate2DomainPackageBuilderFactory().create().build(
            base_package=trade,
            route=derived_route,
            route_artifact_ref="art_derived_route",
        )
        self.assertEqual(
            [item["extractor_domain"] for item in domain_packages],
            ["trade_operation"],
        )
        self.assertEqual(
            domain_packages[0]["candidate_source_refs"], ["row_trade"]
        )

        selected_plan = mark_segmentation_selection(
            result.plan, [trade["segmentation"]["segment_ref"]]
        )
        self.assertEqual(
            selected_plan["coverage"]["selected_for_extraction_total"], 1
        )
        self.assertEqual(
            selected_plan["coverage"]["deferred_derived_units_total"],
            len(result.derived_packages) - 1,
        )

    def test_stitcher_detects_double_claim_preserves_unknown_and_accounts_no_fact(self):
        package = _base_package()
        route = Gate2SourceUnitRouterFactory().create().route(package)
        accepted = [
            _accepted_output(
                domain="trade_operation",
                source_ref="row_trade",
                fact_id="fact_trade",
                fact_type="trade_operation",
            ),
            _accepted_output(
                domain="income",
                source_ref="row_income",
                fact_id="fact_income",
                fact_type="income",
            ),
            _accepted_output(
                domain="withholding_tax",
                source_ref="row_withholding",
                fact_id="fact_withholding",
                fact_type="withholding_tax",
            ),
            _accepted_output(
                domain="fee_commission",
                source_ref="row_fee",
                fact_id="fact_fee",
                fact_type="fee_commission",
            ),
            _accepted_output(
                domain="cash_movement",
                source_ref="row_cash",
                fact_id="fact_cash",
                fact_type="cash_movement",
            ),
            _accepted_output(
                domain="income",
                source_ref="row_ambiguous",
                fact_id="fact_ambiguous_income",
                fact_type="income",
            ),
            _accepted_output(
                domain="fee_commission",
                source_ref="row_ambiguous",
                fact_id="fact_ambiguous_fee",
                fact_type="fee_commission",
            ),
            _accepted_output(
                domain="unknown_source_row",
                source_ref="row_unknown",
                fact_id="fact_unknown",
                fact_type="unknown_source_row",
            ),
        ]
        result = Gate2SourceFactStitcherFactory().create().stitch(
            extraction_run_id="domain_run",
            route_ref="art_route",
            route=route,
            accepted_domain_outputs=accepted,
            rejected_domain_outputs=[],
        )
        validate_source_fact_stitch_result(result)

        self.assertEqual(result["coverage"]["selected_total"], 10)
        self.assertEqual(result["coverage"]["accepted_fact_owned_total"], 5)
        self.assertEqual(result["coverage"]["unknown_total"], 1)
        self.assertEqual(result["coverage"]["no_fact_total"], 3)
        self.assertEqual(result["coverage"]["conflict_total"], 1)
        self.assertEqual(result["coverage"]["uncovered_total"], 0)
        self.assertEqual(result["coverage"]["coverage_status"], "conflicted")
        self.assertEqual(result["unknown_source_row_refs"], ["row_unknown"])
        self.assertEqual(result["conflicts"][0]["source_ref"], "row_ambiguous")
        self.assertEqual(len(result["issue_fact_linkage"]), 8)
        self.assertFalse(
            result["downstream_restrictions"]["tax_calculation_allowed"]
        )
        self.assertFalse(
            result["downstream_restrictions"]["declaration_mapping_allowed"]
        )

    def test_stitcher_marks_failed_domain_candidates_uncovered(self):
        package = _base_package()
        route = Gate2SourceUnitRouterFactory().create().route(package)
        result = Gate2SourceFactStitcherFactory().create().stitch(
            extraction_run_id="domain_run",
            route_ref="art_route",
            route=route,
            accepted_domain_outputs=[],
            rejected_domain_outputs=[
                {
                    "extractor_domain": "trade_operation",
                    "domain_package_ref": "art_pkg",
                    "validation_ref": "art_validation",
                    "candidate_source_refs": ["row_trade"],
                    "error_codes": ["source_fact_provenance_missing"],
                }
            ],
        )
        self.assertEqual(result["coverage"]["coverage_status"], "partial")
        self.assertIn("row_trade", result["uncovered_refs"])
        self.assertEqual(
            result["rejected_candidate_refs"][0]["error_codes"],
            ["source_fact_provenance_missing"],
        )


def _base_package():
    rows = [
        ("row_trade", "trade_operation", ["buy", "2026-01-01", "100.00", "USD"]),
        ("row_income", "income", ["dividend", "2026-01-02", "10.00", "USD"]),
        ("row_withholding", "withholding_tax", ["withholding_tax", "2026-01-02", "1.00", "USD"]),
        ("row_fee", "fee_commission", ["commission", "2026-01-03", "2.00", "USD"]),
        ("row_cash", "cash_movement", ["deposit", "2026-01-04", "50.00", "USD"]),
        ("row_ambiguous", None, ["dividend", "commission", "3.00", "USD"]),
        ("row_unknown", None, ["unmapped_event", "2026-01-05", "4.00", "USD"]),
    ]
    headers = ["operation", "description", "amount", "currency"]
    projected_rows = []
    row_provenance = []
    cell_provenance = []
    source_value_index = []
    normalized_cells = []
    all_value_refs = []
    for row_ordinal, (row_ref, hint, values) in enumerate(rows, start=1):
        projected_cells = []
        row_provenance.append(
            {"row_ref": row_ref, "row_ordinal": row_ordinal, "row_kind": "fact_candidate"}
        )
        normalized_cells.append(values)
        for column_ordinal, value in enumerate(values, start=1):
            cell_ref = f"cell_{row_ordinal}_{column_ordinal}"
            source_value_ref = f"value_{row_ordinal}_{column_ordinal}"
            all_value_refs.append(source_value_ref)
            projected_cells.append(
                {
                    "column_ordinal": column_ordinal,
                    "header_label": headers[column_ordinal - 1],
                    "cell_ref": cell_ref,
                    "source_value_ref": source_value_ref,
                    "value": value,
                }
            )
            cell_provenance.append(
                {
                    "row_ordinal": row_ordinal,
                    "column_ordinal": column_ordinal,
                    "cell_ref": cell_ref,
                    "source_value_ref": source_value_ref,
                }
            )
            source_value_index.append(
                {
                    "source_value_ref": source_value_ref,
                    "row_ref": row_ref,
                    "cell_ref": cell_ref,
                    "value_path": {
                        "kind": "table_cell",
                        "row_index": row_ordinal - 1,
                        "column_index": column_ordinal - 1,
                    },
                    "value_checksum_ref": f"checksum_{row_ordinal}_{column_ordinal}",
                }
            )
        projected_rows.append(
            {
                "row_ref": row_ref,
                "row_kind": "fact_candidate",
                "fact_type_hint": hint,
                "fact_type_hint_policy": "synthetic",
                "cells": projected_cells,
            }
        )
    selected = [item[0] for item in rows] + ["row_header", "row_blank", "row_layout"]
    return {
        "schema_version": "broker_reports_source_fact_package_v0",
        "package_id": "base_package",
        "extraction_run_id": "domain_run",
        "normalization_run_id": "normalization_run",
        "case_id": "synthetic_domain_case",
        "document_ref": "document_ref",
        "source_bucket_roles": ["primary_source_refs"],
        "document_context": {
            "usage_modes": ["source_fact"],
            "passport": {"document_kind_candidate": "broker_report"},
        },
        "source_unit": {
            "unit_id": "table_ref",
            "unit_kind": "table_row_window",
            "private_slice_artifact_ref": "art_slice",
            "slice_ref": "slice_ref",
            "document_ref": "document_ref",
            "source_checksum_ref": "checksum_ref",
            "parser_ref": "parser_ref",
            "table_ref": "table_ref",
            "row_range_ref": "row_range_ref",
            "coverage_ref": "coverage_ref",
            "normalized_header_descriptors": [
                {"column_ordinal": index, "normalized_label": label}
                for index, label in enumerate(headers, start=1)
            ],
            "row_refs": [item[0] for item in rows],
            "row_provenance": row_provenance,
            "cell_refs": [item["cell_ref"] for item in cell_provenance],
            "cell_provenance": cell_provenance,
            "cell_value_refs": all_value_refs,
            "source_value_refs": all_value_refs,
            "source_value_index": source_value_index,
            "text_segment_refs": [],
            "section_refs": [],
            "page_refs": [],
            "character_span_refs": [],
            "segment_provenance": [],
            "normalized_source_projection": {"cells": normalized_cells},
            "model_source_projection": {
                "schema_version": "gate2_model_table_projection_v0",
                "rows": projected_rows,
            },
        },
        "allowed_evidence_refs": selected,
        "allowed_source_value_refs": all_value_refs,
        "issue_context": [
            {
                "issue_ref": "issue_unresolved",
                "status": "unresolved",
                "impact": "limits_confirmation",
            }
        ],
        "allowed_issue_refs": ["issue_unresolved"],
        "forbidden_assumptions": ["do_not_infer_missing_values"],
        "coverage_expectation": {
            "coverage_ref": "coverage_ref",
            "selected_source_refs": selected,
            "ignorable_header_refs": ["row_header"],
            "ignorable_blank_refs": ["row_blank"],
            "layout_candidate_refs": ["row_layout"],
            "mandatory_no_fact_results": [
                {"source_ref": "row_header", "reason_code": "header_row"},
                {"source_ref": "row_blank", "reason_code": "blank_row"},
                {"source_ref": "row_layout", "reason_code": "layout_only"},
            ],
        },
        "privacy_policy": {
            "knowledge_rag_used": False,
            "vectorization_performed": False,
        },
        "created_at": "2026-07-10T00:00:00Z",
    }


def _accepted_output(*, domain, source_ref, fact_id, fact_type):
    source_facts_ref = f"art_{fact_id}"
    return {
        "validator_status": "passed",
        "extractor_domain": domain,
        "source_facts_ref": source_facts_ref,
        "validation_ref": f"validation_{fact_id}",
        "source_facts": {
            "facts": [
                {
                    "fact_id": fact_id,
                    "fact_type": fact_type,
                    "evidence_refs": [source_ref],
                    "linked_issue_refs": ["issue_unresolved"],
                }
            ],
            "coverage": {
                "fact_covered_refs": [source_ref],
                "no_fact_results": [],
            },
        },
    }


if __name__ == "__main__":
    unittest.main()
