from __future__ import annotations

import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from broker_reports_gate1 import (
    Gate2CandidateBindingConfig,
    Gate2CandidateBindingKernelFactory,
    Gate2CandidateBindingRuntimeFactory,
    Gate2DomainCandidateFinalizerFactory,
    Gate2DomainPackageBuilderConfig,
    Gate2DomainPackageBuilderFactory,
    Gate2LlmContextBudget,
    Gate2LlmContextPackageFactory,
    Gate2SourceFactStitcherFactory,
    Gate2SourceUnitRouterFactory,
    candidate_binding_schema_hash,
    candidate_binding_provider_json_schema,
    context_component_metrics,
    detect_context_duplication,
    package_feasibility,
    safe_inspection,
)
from broker_reports_gate1.artifact_models import (
    ArtifactAccessContext,
    ArtifactRecord,
    RetentionPolicy,
)
from broker_reports_gate1.artifact_resolver import ArtifactResolver
from broker_reports_gate1.artifact_store import (
    ArtifactStoreConfig,
    ArtifactStoreFactory,
)
from broker_reports_gate1.contracts import stable_digest
from broker_reports_gate1.gate2_candidate_binding import (
    FACTORY_REQUIRED as KERNEL_FACTORY_REQUIRED,
    FORBIDDEN as KERNEL_FORBIDDEN,
)
from broker_reports_gate1.gate2_candidate_binding_runtime import (
    FACTORY_REQUIRED as RUNTIME_FACTORY_REQUIRED,
    FORBIDDEN as RUNTIME_FORBIDDEN,
    candidate_binding_response_format,
)
from broker_reports_gate1.gate2_domain_contracts import (
    domain_source_facts_response_format,
)
from broker_reports_gate1.gate2_model_contracts import gate2_provider_profile
from broker_reports_gate1.gate2_provider_adapters import (
    Gate2ProviderAdapterFactory,
)
from broker_reports_gate1.gate2_source_fact_contracts import (
    Gate2ManagedPrompt,
    gate2_prompt_hash,
    model_call_audit_metadata,
    source_facts_provider_schema_hash,
    source_facts_response_format,
    source_facts_schema_hash,
)
from broker_reports_gate1.gate2_source_fact_stitching import (
    validate_source_fact_stitch_result,
)
from broker_reports_gate1.gate2_source_fact_validation import (
    Gate2SourceFactValidatorFactory,
)


DOMAIN_ROWS = {
    "cash_movement": (
        ["operation", "amount", "currency", "date"],
        ["deposit", "25.00", "USD", "2026-01-01"],
    ),
    "income": (
        ["operation", "amount", "currency", "date"],
        ["dividend", "5.00", "USD", "2026-01-02"],
    ),
    "withholding_tax": (
        ["operation", "amount", "currency", "date"],
        ["withholding_tax", "1.00", "USD", "2026-01-02"],
    ),
    "fee_commission": (
        ["operation", "amount", "currency", "date"],
        ["broker_commission", "0.50", "USD", "2026-01-03"],
    ),
    "position_snapshot": (
        ["operation", "instrument", "quantity", "amount", "currency", "date"],
        ["position_snapshot", "SYNTH-POS", "10", "100.00", "USD", "2026-01-04"],
    ),
    "trade_operation": (
        ["operation", "instrument", "quantity", "amount", "currency", "date"],
        ["sell", "SYNTH-TRADE", "2", "20.00", "USD", "2026-01-05"],
    ),
    "currency_fx": (
        ["amount", "currency", "amount", "currency", "rate", "operation", "date"],
        ["100.00", "USD", "90.00", "EUR", "0.90", "explicit_fx_rate", "2026-01-06"],
    ),
    "document_summary_evidence": (
        ["operation", "amount", "currency", "date"],
        ["source_summary", "141.75", "USD", "2026-01-07"],
    ),
    "unknown_source_row": (
        ["operation", "amount", "currency"],
        ["unclassified_source_row", "3.00", "USD"],
    ),
}


class BrokerReportsGate2CandidateBindingTest(unittest.TestCase):
    def test_factory_anchors_and_all_domain_binding_matrix(self):
        self.assertIn("Gate2CandidateBindingKernelFactory.create", KERNEL_FACTORY_REQUIRED)
        self.assertIn("must not choose semantic roles", KERNEL_FORBIDDEN)
        self.assertIn("Gate2CandidateBindingRuntimeFactory.create", RUNTIME_FACTORY_REQUIRED)
        self.assertIn("must not choose candidates", RUNTIME_FORBIDDEN)

        for domain in DOMAIN_ROWS:
            with self.subTest(domain=domain):
                package = _domain_package(domain)
                selection = _valid_selection(package)
                outcome = Gate2CandidateBindingRuntimeFactory().create().validate_and_materialize(
                    selection=selection,
                    package=package,
                )
                self.assertEqual(
                    outcome.validation["validator_status"],
                    "passed",
                    outcome.validation,
                )
                self.assertIsNotNone(outcome.legacy_candidate)
                facts = outcome.legacy_candidate["facts"]
                self.assertEqual(len(facts), 1)
                self.assertEqual(facts[0]["fact_type"], domain)
                if domain != "unknown_source_row":
                    self.assertTrue(
                        any(value is not None for value in facts[0]["normalized_values"].values())
                        or any(
                            value
                            for value in facts[0]["extracted_fields"].values()
                            if isinstance(value, list)
                        )
                    )

    def test_currency_fx_requires_relation_and_keeps_equal_values_distinct(self):
        package = _domain_package(
            "currency_fx",
            values=["100.00", "USD", "100.00", "EUR", "1.00", "explicit_fx_rate", "2026-01-06"],
        )
        candidates = package["source_value_candidate_set"]["candidates"]
        amounts = [item for item in candidates if item["candidate_kind"] == "decimal_amount"]
        self.assertGreaterEqual(len(amounts), 2)
        self.assertNotEqual(amounts[0]["candidate_id"], amounts[1]["candidate_id"])
        self.assertNotEqual(amounts[0]["source_value_refs"], amounts[1]["source_value_refs"])
        self.assertIsNotNone(amounts[0]["ambiguity_group_ref"])
        self.assertEqual(amounts[0]["ambiguity_group_ref"], amounts[1]["ambiguity_group_ref"])

        selection = _valid_selection(package, resolve_ambiguity=True)
        selection["binding_results"][0]["selected_relation_ids"] = []
        validation = Gate2CandidateBindingRuntimeFactory().create().validate_and_materialize(
            selection=selection, package=package
        ).validation
        self.assertIn(
            "candidate_binding_required_relation_missing",
            validation["error_code_counts"],
        )

    def test_provider_schema_binds_candidate_and_relation_ids_not_values(self):
        package = _domain_package("currency_fx")
        schema = candidate_binding_provider_json_schema(package)
        rendered = json.dumps(schema, ensure_ascii=False, sort_keys=True)
        candidate_ids = package["source_value_candidate_set"]["candidate_ids"]
        relation_ids = package["candidate_relation_set"]["relation_ids"]
        self.assertTrue(all(candidate_id in rendered for candidate_id in candidate_ids))
        self.assertTrue(all(relation_id in rendered for relation_id in relation_ids))
        self.assertNotIn("100.00", rendered)
        self.assertNotIn("SYNTH", rendered)

    def test_llm_context_v2_is_compact_provenance_complete_and_inspectable(self):
        package = _domain_package("cash_movement")
        context = package["llm_context_package"]
        self.assertEqual(
            context["schema_version"],
            "broker_reports_gate2_llm_context_package_v2",
        )
        self.assertEqual(context["target_source_refs"], package["candidate_source_refs"])
        self.assertNotIn("document_context", context)
        self.assertNotIn("source_value_index", context)
        self.assertEqual(context["material_issues"], [])
        self.assertTrue(context["candidate_evidence"])
        for candidate in context["candidate_evidence"]:
            self.assertTrue(candidate["visible_label"])
            self.assertTrue(candidate["source_value_refs"])
            self.assertTrue(candidate["row_ref"])
        inspection = safe_inspection(context)
        self.assertEqual(inspection["domain"], "cash_movement")
        self.assertEqual(inspection["target_refs_total"], 1)
        metrics = context_component_metrics(context)
        self.assertGreater(metrics["candidate_evidence"]["estimated_tokens"], 0)
        self.assertEqual(context["budget"]["silent_truncation_used"], False)

    def test_context_duplication_detection_is_component_specific(self):
        first = _domain_package("cash_movement")["llm_context_package"]
        second = copy.deepcopy(first)
        result = detect_context_duplication([first, second])
        self.assertEqual(result["local_structure"]["repeated_sends_total"], 1)
        second["material_issues"] = [{"issue_ref": "different"}]
        result = detect_context_duplication([first, second])
        self.assertEqual(result["material_issues"]["repeated_sends_total"], 0)

    def test_material_issue_that_limits_target_confirmation_is_preserved(self):
        package = _domain_package("cash_movement", issue_limited=True)
        issues = package["llm_context_package"]["material_issues"]
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0]["issue_ref"], "issue_limit")
        self.assertEqual(issues[0]["impact"], "limits_confirmation")
        schema = candidate_binding_provider_json_schema(package)
        completeness = schema["properties"]["binding_results"]["items"]["properties"]["completeness"]
        self.assertNotIn("complete", completeness["enum"])

    def test_package_feasibility_blocks_impossible_roles_before_model(self):
        package = _domain_package("cash_movement")
        self.assertEqual(package_feasibility(package)["status"], "passed")
        package["candidate_binding_profile"]["required_roles"] = ["impossible_role"]
        feasibility = package_feasibility(package)
        self.assertEqual(feasibility["status"], "blocked")
        self.assertIn(
            "gate2_package_feasibility_required_roles_unavailable",
            feasibility["reason_codes"],
        )

    def test_compact_schema_is_flat_and_gemini_projectable(self):
        package = _domain_package("document_summary_evidence")
        schema = candidate_binding_provider_json_schema(package)
        rendered = json.dumps(schema, ensure_ascii=False, sort_keys=True)
        self.assertNotIn('"anyOf"', rendered)
        self.assertNotIn('"oneOf"', rendered)
        self.assertLess(len(rendered), 20000)
        adapter = Gate2ProviderAdapterFactory(
            profile=gate2_provider_profile("google_gemini")
        ).create()
        prepared = adapter.prepare_form_data(
            form_data={
                "model": "models/gemini-3.1-flash-lite",
                "messages": [],
                "response_format": candidate_binding_response_format(package),
            },
            response_format=candidate_binding_response_format(package),
        )
        self.assertTrue(prepared.form_data["response_format"]["json_schema"]["strict"])

    def test_context_budget_blocks_without_silent_truncation(self):
        package = _domain_package("cash_movement")
        context = Gate2LlmContextPackageFactory(
            Gate2LlmContextBudget(max_context_chars=100)
        ).create().build(package)
        self.assertEqual(context["budget"]["status"], "blocked")
        self.assertIn(
            "gate2_llm_context_budget_exceeded",
            context["budget"]["error_code"],
        )
        self.assertFalse(context["budget"]["silent_truncation_used"])

    def test_gemini_projection_characterizes_real_gate2_schema_family(self):
        package = _domain_package("cash_movement")
        adapter = Gate2ProviderAdapterFactory(
            profile=gate2_provider_profile("google_gemini"),
        ).create()
        response_formats = {
            "source": source_facts_response_format(package),
            "domain": domain_source_facts_response_format(package),
            "candidate_binding": candidate_binding_response_format(package),
        }
        dynamic_values = (
            package["source_value_candidate_set"]["candidate_ids"]
            + package["candidate_relation_set"]["relation_ids"]
            + package["allowed_source_value_refs"]
        )

        for name, response_format in response_formats.items():
            with self.subTest(name=name):
                canonical = copy.deepcopy(response_format)
                prepared = adapter.prepare_form_data(
                    form_data={
                        "model": "models/gemini-3.5-flash",
                        "messages": [],
                        "response_format": copy.deepcopy(response_format),
                    },
                    response_format=response_format,
                )
                adapted = prepared.form_data["response_format"]
                canonical_schema = canonical["json_schema"]["schema"]
                adapted_schema = adapted["json_schema"]["schema"]

                self.assertEqual(response_format, canonical)
                self.assertTrue(adapted["json_schema"]["strict"])
                self.assertGreater(prepared.schema_transform_count, 0)
                self.assertNotEqual(
                    prepared.canonical_schema_hash,
                    prepared.adapted_schema_hash,
                )
                self.assertEqual(
                    _structural_schema_signature(canonical_schema),
                    _structural_schema_signature(adapted_schema),
                )
                rendered_adapted = json.dumps(
                    adapted_schema,
                    ensure_ascii=False,
                    sort_keys=True,
                )
                self.assertNotIn('"const"', rendered_adapted)
                if name == "candidate_binding":
                    self.assertIn('"semantic_role"', rendered_adapted)
                    self.assertIn('"fact_field_path"', rendered_adapted)
                    self.assertIn('"candidate_id"', rendered_adapted)
                if name == "candidate_binding":
                    self.assertTrue(
                        all(
                            value in rendered_adapted
                            for value in package["source_value_candidate_set"]["candidate_ids"]
                        )
                    )
                    self.assertTrue(
                        all(
                            value not in rendered_adapted
                            for value in package["allowed_source_value_refs"]
                        )
                    )
                else:
                    self.assertTrue(
                        all(value not in rendered_adapted for value in dynamic_values)
                    )

    def test_negative_case_matrix_fails_with_typed_codes(self):
        cases = []

        package = _domain_package("cash_movement")
        foreign = _valid_selection(package)
        foreign["binding_results"][0]["selected_bindings"][0]["candidate_id"] = "svcand_foreign"
        cases.append((package, foreign, "candidate_binding_foreign_candidate_id"))

        package = _domain_package("cash_movement")
        forbidden_field = _valid_selection(package)
        forbidden_field["binding_results"][0]["selected_bindings"][0]["fact_field_path"] = "normalized_values.rate"
        cases.append((package, forbidden_field, "candidate_binding_fact_field_forbidden"))

        package = _domain_package("cash_movement")
        forbidden_role = _valid_selection(package)
        forbidden_role["binding_results"][0]["selected_bindings"][0]["semantic_role"] = "base_amount"
        cases.append((package, forbidden_role, "candidate_binding_semantic_role_forbidden"))

        package = _domain_package("cash_movement")
        forbidden_kind = _valid_selection(package)
        selected_id = forbidden_kind["binding_results"][0]["selected_bindings"][0][
            "candidate_id"
        ]
        selected_candidate = next(
            item
            for item in package["source_value_candidate_set"]["candidates"]
            if item["candidate_id"] == selected_id
        )
        selected_candidate["candidate_kind"] = "unknown_mechanical_value"
        package["source_value_candidate_set"]["candidate_set_hash"] = stable_digest(
            package["source_value_candidate_set"]["candidates"], length=32
        )
        forbidden_kind["candidate_set_hash"] = package["source_value_candidate_set"][
            "candidate_set_hash"
        ]
        cases.append(
            (package, forbidden_kind, "candidate_binding_candidate_kind_forbidden")
        )

        package = _domain_package("cash_movement")
        reused = _valid_selection(package)
        first = copy.deepcopy(reused["binding_results"][0]["selected_bindings"][0])
        first["semantic_role"] = "movement_currency"
        first["fact_field_path"] = "normalized_values.currency"
        reused["binding_results"][0]["selected_bindings"].append(first)
        cases.append((package, reused, "candidate_binding_candidate_reuse_forbidden"))

        package = _domain_package("cash_movement")
        coverage = _valid_selection(package)
        coverage["binding_results"] = []
        cases.append((package, coverage, "candidate_binding_coverage_gap"))

        package = _domain_package("cash_movement", issue_limited=True)
        complete = _valid_selection(package)
        complete["binding_results"][0]["completeness"] = "complete"
        cases.append((package, complete, "candidate_binding_issue_limited_completeness"))

        package = _domain_package("currency_fx")
        missing_relation = _valid_selection(package)
        missing_relation["binding_results"][0]["selected_relation_ids"] = []
        cases.append((package, missing_relation, "candidate_binding_required_relation_missing"))

        package = _domain_package("currency_fx")
        invalid_relation = _valid_selection(package)
        invalid_relation["binding_results"][0]["selected_relation_ids"] = ["svrel_foreign"]
        cases.append((package, invalid_relation, "candidate_binding_relation_not_found"))

        package = _domain_package("currency_fx")
        cross_row = _valid_selection(package)
        relation_id = cross_row["binding_results"][0]["selected_relation_ids"][0]
        next(
            item
            for item in package["candidate_relation_set"]["relations"]
            if item["relation_id"] == relation_id
        )["row_refs"] = ["row_foreign"]
        cases.append((package, cross_row, "candidate_binding_cross_row_relation"))

        package = _domain_package(
            "currency_fx",
            values=["100.00", "USD", "100.00", "EUR", "1.00", "explicit_fx_rate", "2026-01-06"],
        )
        ambiguous = _valid_selection(package, resolve_ambiguity=False)
        cases.append((package, ambiguous, "candidate_binding_ambiguity_unresolved"))

        package = _domain_package("cash_movement")
        changed_set = _valid_selection(package)
        changed_set["candidate_set_hash"] = "changed"
        cases.append((package, changed_set, "candidate_binding_contract_mismatch"))

        package = _domain_package("cash_movement")
        tampered_value = _valid_selection(package)
        selected_id = tampered_value["binding_results"][0]["selected_bindings"][0][
            "candidate_id"
        ]
        next(
            item
            for item in package["source_value_candidate_set"]["candidates"]
            if item["candidate_id"] == selected_id
        )["normalized_value"] = "999.99"
        cases.append(
            (
                package,
                tampered_value,
                "candidate_binding_candidate_value_unreproducible",
            )
        )

        package = _domain_package("cash_movement")
        tampered_checksum = _valid_selection(package)
        selected_id = tampered_checksum["binding_results"][0]["selected_bindings"][0][
            "candidate_id"
        ]
        next(
            item
            for item in package["source_value_candidate_set"]["candidates"]
            if item["candidate_id"] == selected_id
        )["value_checksum_refs"] = ["valuechk_foreign"]
        cases.append(
            (
                package,
                tampered_checksum,
                "candidate_binding_candidate_checksum_mismatch",
            )
        )

        for index, (package, selection, expected_code) in enumerate(cases):
            with self.subTest(index=index, expected_code=expected_code):
                validation = Gate2CandidateBindingRuntimeFactory().create().validate_and_materialize(
                    selection=selection,
                    package=package,
                ).validation
                self.assertEqual(validation["validator_status"], "failed")
                self.assertIn(expected_code, validation["error_code_counts"], validation)

    def test_unknown_fallback_and_missing_required_candidate(self):
        package = _domain_package("cash_movement")
        unknown = _unknown_selection(package)
        outcome = Gate2CandidateBindingRuntimeFactory().create().validate_and_materialize(
            selection=unknown,
            package=package,
        )
        self.assertEqual(outcome.validation["validator_status"], "passed")
        self.assertEqual(
            outcome.legacy_candidate["facts"][0]["fact_type"],
            "unknown_source_row",
        )

        missing = _valid_selection(package)
        missing["binding_results"][0]["selected_bindings"] = [
            item
            for item in missing["binding_results"][0]["selected_bindings"]
            if item["semantic_role"] != "movement_amount"
        ]
        validation = Gate2CandidateBindingRuntimeFactory().create().validate_and_materialize(
            selection=missing,
            package=package,
        ).validation
        self.assertIn("candidate_binding_required_role_missing", validation["error_code_counts"])

    def test_candidate_and_relation_budgets_fail_closed(self):
        package = _domain_package("cash_movement")
        with self.assertRaisesRegex(
            ValueError, "candidate_binding_candidate_budget_exceeded"
        ):
            Gate2CandidateBindingKernelFactory(
                config=Gate2CandidateBindingConfig(max_candidates=1)
            ).create().build(package)
        with self.assertRaisesRegex(
            ValueError, "candidate_binding_relation_budget_exceeded"
        ):
            Gate2CandidateBindingKernelFactory(
                config=Gate2CandidateBindingConfig(max_relations=1)
            ).create().build(package)

    def test_all_domain_full_production_factory_path_validates_and_stitches(self):
        for domain in DOMAIN_ROWS:
            with self.subTest(domain=domain), tempfile.TemporaryDirectory() as temp_dir:
                base = _base_package(domain)
                route = Gate2SourceUnitRouterFactory().create().route(base)
                package = _domain_package_from_base(
                    base=base,
                    route=route,
                    domain=domain,
                )
                prompt = _prepare_package_for_strict_validation(package, domain)
                selection = _valid_selection(package)
                selected_bindings = selection["binding_results"][0][
                    "selected_bindings"
                ]
                selected_roles = {
                    item["semantic_role"] for item in selected_bindings
                }

                if domain == "currency_fx":
                    self.assertTrue(
                        {
                            "base_amount",
                            "quote_amount",
                            "base_currency",
                            "quote_currency",
                        }
                        <= selected_roles
                    )
                    selected_relation_ids = selection["binding_results"][0][
                        "selected_relation_ids"
                    ]
                    relation_by_id = {
                        item["relation_id"]: item
                        for item in package["candidate_relation_set"]["relations"]
                    }
                    self.assertEqual(len(selected_relation_ids), 1)
                    self.assertEqual(
                        relation_by_id[selected_relation_ids[0]]["relation_kind"],
                        "base_quote_amount_currency_group",
                    )

                if domain == "trade_operation":
                    self.assertTrue(
                        {
                            "trade_direction",
                            "trade_instrument",
                            "trade_quantity",
                            "trade_amount",
                        }
                        <= selected_roles
                    )
                    candidate_by_id = {
                        item["candidate_id"]: item
                        for item in package["source_value_candidate_set"]["candidates"]
                    }
                    role_kinds = {
                        item["semantic_role"]: candidate_by_id[item["candidate_id"]][
                            "candidate_kind"
                        ]
                        for item in selected_bindings
                    }
                    self.assertEqual(
                        role_kinds["trade_direction"], "categorical_direction"
                    )
                    self.assertIn(
                        role_kinds["trade_instrument"],
                        {"instrument_identifier", "instrument_label"},
                    )
                    self.assertEqual(role_kinds["trade_quantity"], "quantity")
                    self.assertEqual(role_kinds["trade_amount"], "decimal_amount")

                binding_outcome = (
                    Gate2CandidateBindingRuntimeFactory()
                    .create()
                    .validate_and_materialize(selection=selection, package=package)
                )
                self.assertEqual(
                    binding_outcome.validation["validator_status"],
                    "passed",
                    binding_outcome.validation,
                )
                self.assertIsNotNone(binding_outcome.legacy_candidate)
                finalized_candidate = (
                    Gate2DomainCandidateFinalizerFactory()
                    .create()
                    .finalize(
                        candidate=binding_outcome.legacy_candidate,
                        package=package,
                    )
                )

                validation_outcome = _strict_validate_candidate(
                    temp_dir=Path(temp_dir),
                    package=package,
                    selection=selection,
                    candidate=finalized_candidate,
                    prompt=prompt,
                )
                self.assertEqual(
                    validation_outcome.validation["validator_status"],
                    "passed",
                    validation_outcome.validation,
                )
                self.assertEqual(validation_outcome.validation["errors"], [])
                self.assertIsNotNone(validation_outcome.finalized_source_facts)
                source_facts = validation_outcome.finalized_source_facts
                self.assertEqual(source_facts["validator_status"], "passed")
                self.assertEqual(
                    source_facts["coverage"]["coverage_status"], "complete"
                )

                validation_ref = f"art_candidate_binding_validation_{domain}"
                stitch = Gate2SourceFactStitcherFactory().create().stitch(
                    extraction_run_id=str(package["extraction_run_id"]),
                    route_ref=f"art_candidate_binding_route_{domain}",
                    route=route,
                    accepted_domain_outputs=[
                        {
                            "wrapper_schema_version": (
                                "broker_reports_domain_source_facts_v0"
                            ),
                            "validator_status": "passed",
                            "extractor_domain": domain,
                            "source_facts_ref": f"art_candidate_binding_facts_{domain}",
                            "validation_ref": validation_ref,
                            "source_facts": source_facts,
                        }
                    ],
                    rejected_domain_outputs=[],
                )
                validate_source_fact_stitch_result(stitch)
                self.assertEqual(stitch["coverage"]["coverage_status"], "complete")
                self.assertTrue(stitch["coverage"]["all_selected_refs_accounted"])
                self.assertEqual(stitch["coverage"]["uncovered_total"], 0)
                self.assertEqual(stitch["coverage"]["conflict_total"], 0)
                self.assertEqual(len(stitch["ownership_map"]), 1)
                if domain == "unknown_source_row":
                    self.assertEqual(stitch["coverage"]["unknown_total"], 1)
                    self.assertEqual(
                        stitch["ownership_map"][0]["ownership_status"],
                        "unknown_source_row",
                    )
                    self.assertEqual(
                        stitch["unknown_source_row_refs"],
                        package["candidate_source_refs"],
                    )
                else:
                    self.assertEqual(
                        stitch["coverage"]["accepted_fact_owned_total"], 1
                    )
                    self.assertEqual(
                        stitch["ownership_map"][0]["ownership_status"],
                        "accepted_fact",
                    )

    def test_candidate_binding_carries_issue_limits_through_unchanged_validator(self):
        domain = "cash_movement"
        base = _base_package(domain, issue_limited=True)
        route = Gate2SourceUnitRouterFactory().create().route(base)
        package = _domain_package_from_base(base=base, route=route, domain=domain)
        prompt = _prepare_package_for_strict_validation(package, domain)
        selection = _valid_selection(package)
        self.assertEqual(selection["binding_results"][0]["completeness"], "partial")
        binding_outcome = (
            Gate2CandidateBindingRuntimeFactory()
            .create()
            .validate_and_materialize(selection=selection, package=package)
        )
        self.assertEqual(
            binding_outcome.validation["validator_status"],
            "passed",
            binding_outcome.validation,
        )
        candidate = (
            Gate2DomainCandidateFinalizerFactory()
            .create()
            .finalize(candidate=binding_outcome.legacy_candidate, package=package)
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            validation_outcome = _strict_validate_candidate(
                temp_dir=Path(temp_dir),
                package=package,
                selection=selection,
                candidate=candidate,
                prompt=prompt,
            )
        self.assertEqual(
            validation_outcome.validation["validator_status"],
            "passed",
            validation_outcome.validation,
        )
        facts = validation_outcome.finalized_source_facts
        self.assertIsNotNone(facts)
        self.assertEqual(facts["facts"][0]["linked_issue_refs"], ["issue_limit"])
        self.assertEqual(facts["facts"][0]["completeness"], "partial")
        self.assertEqual(
            facts["facts"][0]["issue_impact"]["limits_confirmation_issue_refs"],
            ["issue_limit"],
        )
        self.assertEqual(
            validation_outcome.validation["issue_carry_forward"],
            {
                "allowed_issue_refs": ["issue_limit"],
                "issue_linked_facts_total": 1,
            },
        )

    def test_repair_context_preserves_candidate_relation_and_provider_schema_identity(self):
        package = _domain_package("currency_fx")
        before = {
            "candidate_set_id": package["source_value_candidate_set"]["candidate_set_id"],
            "candidate_set_hash": package["source_value_candidate_set"]["candidate_set_hash"],
            "relation_set_id": package["candidate_relation_set"]["relation_set_id"],
            "relation_set_hash": package["candidate_relation_set"]["relation_set_hash"],
            "schema_hash": candidate_binding_schema_hash(package),
        }
        repair_package = copy.deepcopy(package)
        repair_package["repair_context"] = {
            "schema_version": "gate2_domain_source_fact_repair_context_v0",
            "repair_attempt_count": 1,
            "validation_errors": [
                {
                    "code": "candidate_binding_required_relation_missing",
                    "subject": "currency_fx",
                }
            ],
        }
        after = {
            "candidate_set_id": repair_package["source_value_candidate_set"]["candidate_set_id"],
            "candidate_set_hash": repair_package["source_value_candidate_set"]["candidate_set_hash"],
            "relation_set_id": repair_package["candidate_relation_set"]["relation_set_id"],
            "relation_set_hash": repair_package["candidate_relation_set"]["relation_set_hash"],
            "schema_hash": candidate_binding_schema_hash(repair_package),
        }
        self.assertEqual(after, before)


def _domain_package(
    domain: str,
    *,
    values: list[str] | None = None,
    issue_limited: bool = False,
) -> dict:
    base = _base_package(domain, values=values, issue_limited=issue_limited)
    route = Gate2SourceUnitRouterFactory().create().route(base)
    return _domain_package_from_base(base=base, route=route, domain=domain)


def _domain_package_from_base(*, base: dict, route: dict, domain: str) -> dict:
    packages = Gate2DomainPackageBuilderFactory(
        Gate2DomainPackageBuilderConfig(candidate_binding_enabled=True)
    ).create().build(base_package=base, route=route)
    package = next(item for item in packages if item["extractor_domain"] == domain)
    package["package_artifact_ref"] = f"art_domain_package_{domain}"
    package["expected_source_facts_set_id"] = f"sfset_candidate_binding_{domain}"
    package["expected_candidate_audit"] = {
        "prompt_ref": f"prompt_candidate_binding_{domain}"
    }
    return package


def _base_package(
    domain: str,
    *,
    values: list[str] | None = None,
    issue_limited: bool = False,
) -> dict:
    headers, defaults = DOMAIN_ROWS[domain]
    values = list(values or defaults)
    row_ref = f"row_{domain}"
    cells = []
    source_index = []
    cell_provenance = []
    value_refs = []
    for index, (header, value) in enumerate(zip(headers, values), start=1):
        cell_ref = f"cell_{domain}_{index}"
        value_ref = f"value_{domain}_{index}"
        value_refs.append(value_ref)
        cells.append(
            {
                "column_ordinal": index,
                "column_ref": f"column_{index}",
                "header_label": header,
                "cell_ref": cell_ref,
                "source_value_ref": value_ref,
                "value": value,
                "value_kind_hints": _value_kind_hints(value),
            }
        )
        cell_provenance.append(
            {
                "row_ordinal": 1,
                "column_ordinal": index,
                "cell_ref": cell_ref,
                "source_value_ref": value_ref,
            }
        )
        source_index.append(
            {
                "source_value_ref": value_ref,
                "row_ref": row_ref,
                "cell_ref": cell_ref,
                "value_path": {
                    "kind": "table_cell",
                    "row_index": 0,
                    "column_index": index - 1,
                },
                "value_checksum_ref": _value_checksum_ref(value),
            }
        )
    issue_refs = ["issue_limit"] if issue_limited else []
    return {
        "schema_version": "broker_reports_source_fact_package_v0",
        "package_id": f"base_{domain}",
        "extraction_run_id": f"run_{domain}",
        "normalization_run_id": "normalization",
        "case_id": "candidate-binding-case",
        "document_ref": f"document_{domain}",
        "source_bucket_roles": ["primary_source_extraction_refs"],
        "document_context": {"usage_modes": ["source_fact"]},
        "source_unit": {
            "unit_id": f"unit_{domain}",
            "unit_kind": "table_row_window",
            "source_input_mode": "normalized_table_projection",
            "private_slice_artifact_ref": f"art_slice_{domain}",
            "slice_ref": f"slice_{domain}",
            "document_ref": f"document_{domain}",
            "source_checksum_ref": f"checksum_{domain}",
            "parser_ref": "parser_candidate_binding",
            "table_ref": f"table_{domain}",
            "table_projection_id": f"projection_{domain}",
            "row_range_ref": f"row_range_{domain}",
            "normalized_header_descriptors": [
                {
                    "column_ordinal": index,
                    "normalized_label": header,
                    "header_ref": f"header_{index}",
                }
                for index, header in enumerate(headers, start=1)
            ],
            "row_refs": [row_ref],
            "row_provenance": [
                {
                    "row_ref": row_ref,
                    "row_ordinal": 1,
                    "row_role": "summary_row"
                    if domain == "document_summary_evidence"
                    else "data_row",
                }
            ],
            "cell_refs": [item["cell_ref"] for item in cell_provenance],
            "cell_provenance": cell_provenance,
            "cell_value_refs": value_refs,
            "source_value_refs": value_refs,
            "source_value_index": source_index,
            "text_segment_refs": [],
            "section_refs": [],
            "page_refs": [],
            "character_span_refs": [],
            "segment_provenance": [],
            "normalized_source_projection": {"cells": [values]},
            "model_source_projection": {
                "schema_version": "gate2_model_table_projection_v0",
                "rows": [
                    {
                        "row_ref": row_ref,
                        "row_role": "summary_row"
                        if domain == "document_summary_evidence"
                        else "data_row",
                        "fact_type_hint": domain,
                        "fact_type_hint_policy": "synthetic_binding_matrix",
                        "cells": cells,
                    }
                ],
            },
        },
        "allowed_evidence_refs": [row_ref, f"table_{domain}"],
        "allowed_source_value_refs": value_refs,
        "issue_context": [
            {
                "issue_ref": "issue_limit",
                "status": "unresolved",
                "impact": "limits_confirmation",
            }
        ]
        if issue_limited
        else [],
        "allowed_issue_refs": issue_refs,
        "forbidden_assumptions": ["no_free_form_values"],
        "coverage_expectation": {
            "coverage_ref": f"coverage_{domain}",
            "selected_source_refs": [row_ref],
            "ignorable_header_refs": [],
            "ignorable_blank_refs": [],
            "layout_candidate_refs": [],
            "mandatory_no_fact_results": [],
            "fact_candidate_refs": [row_ref],
            "required_accounting_total": 1,
        },
        "privacy_policy": {
            "knowledge_rag_used": False,
            "vectorization_performed": False,
        },
        "created_at": "2026-07-11T00:00:00Z",
    }


def _valid_selection(package: dict, *, resolve_ambiguity: bool = True) -> dict:
    profile = package["candidate_binding_profile"]
    candidates = package["source_value_candidate_set"]["candidates"]
    source_ref = package["candidate_source_refs"][0]
    selected = []
    used: set[str] = set()
    used_roles: set[str] = set()

    def choose(role: str) -> None:
        if role in used_roles:
            return
        options = [
            item
            for item in candidates
            if role in item["allowed_semantic_roles"]
            and item["candidate_id"] not in used
        ]
        if not options:
            return
        options.sort(key=lambda item: (int(item.get("column_ordinal") or 0), item["candidate_id"]))
        candidate = options[0]
        used.add(candidate["candidate_id"])
        used_roles.add(role)
        selected.append(
            {
                "fact_field_path": profile["roles"][role]["fact_field_path"],
                "candidate_id": candidate["candidate_id"],
                "semantic_role": role,
            }
        )

    if package["extractor_domain"] != "unknown_source_row":
        for role in profile["required_roles"]:
            choose(role)
        for group in profile["required_role_groups"]:
            for role in group:
                before = len(selected)
                choose(role)
                if len(selected) > before:
                    break
        for role in profile["roles"]:
            choose(role)

    selected_ids = {item["candidate_id"] for item in selected}
    relation_ids = []
    for kind in profile["required_relation_kinds"]:
        relation = next(
            item
            for item in package["candidate_relation_set"]["relations"]
            if item["relation_kind"] == kind
        )
        relation_ids.append(relation["relation_id"])
    ambiguity_refs = sorted(
        {
            str(item["ambiguity_group_ref"])
            for item in candidates
            if item.get("ambiguity_group_ref")
            and item["candidate_id"] in selected_ids
        }
    )
    fact_type = package["extractor_domain"]
    if fact_type == "unknown_source_row":
        return _unknown_selection(package)
    subtype = {
        "cash_movement": "deposit",
        "income": "dividend",
        "withholding_tax": "unknown",
        "fee_commission": "broker_commission",
        "position_snapshot": "security_position",
        "trade_operation": "sell",
        "currency_fx": "explicit_rate",
        "document_summary_evidence": "source_summary",
    }[fact_type]
    return _selection(
        package,
        {
            "source_ref": source_ref,
            "fact_type": fact_type,
            "selected_bindings": selected,
            "selected_relation_ids": relation_ids,
            "subtype_candidate": subtype,
            "confidence": "high",
            "completeness": "partial"
            if package.get("allowed_issue_refs")
            else "complete",
            "uncertainty_codes": [],
            "resolved_ambiguity_group_refs": ambiguity_refs if resolve_ambiguity else [],
        },
    )


def _unknown_selection(package: dict) -> dict:
    return _selection(
        package,
        {
            "source_ref": package["candidate_source_refs"][0],
            "fact_type": "unknown_source_row",
            "selected_bindings": [],
            "selected_relation_ids": [],
            "subtype_candidate": "unknown",
            "confidence": "low",
            "completeness": "uncertain",
            "uncertainty_codes": ["candidate_binding_no_safe_semantic_role"],
            "resolved_ambiguity_group_refs": [],
        },
    )


def _selection(package: dict, result: dict) -> dict:
    candidate_set = package["source_value_candidate_set"]
    relation_set = package["candidate_relation_set"]
    return {
        "schema_version": "broker_reports_candidate_binding_output_v0",
        "package_id": package["package_id"],
        "candidate_set_id": candidate_set["candidate_set_id"],
        "candidate_set_hash": candidate_set["candidate_set_hash"],
        "relation_set_id": relation_set["relation_set_id"],
        "relation_set_hash": relation_set["relation_set_hash"],
        "binding_results": [result],
        "no_fact_results": [],
    }


def _prepare_package_for_strict_validation(
    package: dict, domain: str
) -> Gate2ManagedPrompt:
    content = (
        f"Synthetic managed {domain} candidate-binding prompt with "
        "{{source_fact_package_json}}."
    )
    prompt = Gate2ManagedPrompt(
        prompt_ref=f"prompt_candidate_binding_{domain}",
        command=f"broker_gate2_{domain}_v0",
        version="test-v1",
        content=content,
        hash=gate2_prompt_hash(content),
        source="test_boundary",
        template_id=f"broker_reports.{domain}_extraction.v0",
        template_kind=f"broker_reports_{domain}_extraction",
        prompt_contract_id="broker_reports_domain_source_fact_prompt_v0",
        input_schema_version="broker_reports_domain_extraction_package_v0",
        output_schema_id="broker_reports.source_facts.schema.v0",
        output_schema_version="broker_reports_source_facts_v0",
        tags=("broker-reports-gate2-domain", "structured-output"),
        safe_metadata={"extractor_domain": domain, "name": "synthetic"},
    )
    model_id = "synthetic-candidate-binding-matrix"
    package["prompt_contract"] = prompt.snapshot()
    package["model_id"] = model_id
    package["expected_candidate_audit"] = model_call_audit_metadata(
        prompt=prompt,
        model_id=model_id,
        raw_output_artifact_ref=None,
        extraction_attempt_ordinal=1,
        repair_attempt_count=0,
        created_at=str(package["created_at"]),
    )
    package["output_schema"].update(
        {
            "output_schema_hash": source_facts_schema_hash(),
            "provider_response_schema_hash": source_facts_provider_schema_hash(),
            "provider_union_keyword": "anyOf",
            "schema_validation_required": True,
        }
    )
    package["output_schema"]["package_response_schema_hash"] = (
        candidate_binding_schema_hash(package)
    )
    return prompt


def _strict_validate_candidate(
    *,
    temp_dir: Path,
    package: dict,
    selection: dict,
    candidate: dict,
    prompt: Gate2ManagedPrompt,
):
    domain = str(package["extractor_domain"])
    model_id = "synthetic-candidate-binding-matrix"
    package_ref = str(package["package_artifact_ref"])
    raw_output_ref = f"art_candidate_binding_raw_{domain}"
    validation_ref = f"art_candidate_binding_validation_{domain}"
    store = ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=temp_dir / "artifacts.sqlite3",
            payload_root=temp_dir / "payloads",
        )
    ).create()
    context = ArtifactAccessContext(
        user_id="candidate-binding-matrix-user",
        normalization_run_id=str(package["normalization_run_id"]),
        case_id=str(package["case_id"]),
        chat_id="candidate-binding-matrix-chat",
        workspace_model_id="candidate-binding-matrix-workspace",
        allow_private=True,
        require_source_available=True,
    )
    _put_private_artifact(
        store=store,
        context=context,
        artifact_id=str(package["source_unit"]["private_slice_artifact_ref"]),
        artifact_type="private_normalized_table_slice_v0",
        document_id=str(package["document_ref"]),
        payload={"schema_version": "private_normalized_table_slice_v0"},
    )
    _put_private_artifact(
        store=store,
        context=context,
        artifact_id=package_ref,
        artifact_type="broker_reports_domain_extraction_package_v0",
        document_id=str(package["document_ref"]),
        payload=package,
    )
    raw_output = {
        "schema_version": "broker_reports_source_fact_raw_output_v0",
        "extraction_run_id": package["extraction_run_id"],
        "package_ref": package_ref,
        "document_ref": package["document_ref"],
        "source_unit_ref": package["source_unit"]["unit_id"],
        "model_call_status": "passed",
        "error_code": None,
        "raw_output": copy.deepcopy(selection),
        "structured_output_mode": "openwebui_response_format_json_schema",
        "response_format_type": "json_schema",
        "response_format_schema_mode": "strict_json_schema",
        "fallback_used": False,
        "repair_attempt_count": 0,
        "extraction_attempt_ordinal": 1,
        "provider_response_schema_hash": source_facts_provider_schema_hash(),
        "package_response_schema_hash": package["output_schema"][
            "package_response_schema_hash"
        ],
        "provider_union_keyword": "anyOf",
        "prompt_snapshot": prompt.snapshot(),
        "model_id": model_id,
        "extractor_domain": domain,
        "created_at": package["created_at"],
    }
    _put_private_artifact(
        store=store,
        context=context,
        artifact_id=raw_output_ref,
        artifact_type="broker_reports_source_fact_raw_output_v0",
        document_id=str(package["document_ref"]),
        payload=raw_output,
    )
    return Gate2SourceFactValidatorFactory(
        resolver=ArtifactResolver(store),
        context=context,
    ).create().validate(
        candidate=candidate,
        package=package,
        package_artifact_ref=package_ref,
        raw_output_artifact_ref=raw_output_ref,
        validation_artifact_ref=validation_ref,
        prompt=prompt,
        model_id=model_id,
        expected_candidate_audit=package["expected_candidate_audit"],
    )


def _put_private_artifact(
    *,
    store,
    context: ArtifactAccessContext,
    artifact_id: str,
    artifact_type: str,
    document_id: str,
    payload: dict,
) -> None:
    store.put_record(
        ArtifactRecord(
            artifact_id=artifact_id,
            artifact_type=artifact_type,
            case_id=context.case_id,
            chat_id=context.chat_id,
            user_id=context.user_id,
            workspace_model_id=context.workspace_model_id,
            normalization_run_id=context.normalization_run_id,
            document_id=document_id,
            source_file_ref={"provider": "synthetic", "source_deleted": False},
            visibility="private_case",
            storage_backend="project_artifact_payload",
            retention_policy=RetentionPolicy(
                mode="synthetic_dev",
                ttl_seconds=None,
                expires_at=None,
                explicit=True,
            ),
            access_policy={
                "requires_user_id": True,
                "requires_case_or_chat": True,
                "requires_workspace_model_id_when_present": True,
            },
            validation_status="validated",
            lifecycle_status="private_ready",
            payload_kind="json_file",
            payload=payload,
            safe_metadata={"synthetic_candidate_binding_matrix": True},
        )
    )


def _value_checksum_ref(value: str) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return f"valuechk_{hashlib.sha256(encoded).hexdigest()[:24]}"


def _value_kind_hints(value: str) -> list[str]:
    stripped = value.strip().replace(" ", "")
    if stripped.replace(".", "", 1).lstrip("+-").isdigit():
        return ["decimal_like"]
    if len(value) == 3 and value.isupper():
        return ["currency_code_like"]
    if len(value) == 10 and value[4:5] == "-" and value[7:8] == "-":
        return ["iso_date_like"]
    return ["text"]


def _structural_schema_signature(schema: dict[str, Any]) -> dict[str, Any]:
    signature: dict[str, Any] = {}
    for field in ("type", "required", "additionalProperties"):
        if field in schema:
            signature[field] = copy.deepcopy(schema[field])
    properties = schema.get("properties")
    if isinstance(properties, dict):
        signature["properties"] = {
            str(name): _structural_schema_signature(child)
            for name, child in properties.items()
            if isinstance(child, dict)
        }
    items = schema.get("items")
    if isinstance(items, dict):
        signature["items"] = _structural_schema_signature(items)
    elif isinstance(items, list):
        signature["items"] = [
            _structural_schema_signature(item)
            for item in items
            if isinstance(item, dict)
        ]
    for field in ("allOf", "anyOf", "oneOf", "prefixItems"):
        children = schema.get(field)
        if isinstance(children, list):
            signature[field] = [
                _structural_schema_signature(child)
                for child in children
                if isinstance(child, dict)
            ]
    return signature


if __name__ == "__main__":
    unittest.main()
