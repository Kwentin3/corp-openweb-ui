from __future__ import annotations

import asyncio
import copy
import json
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT))

from broker_reports_gate1 import (
    AnswerContextSelectionFactory,
    ArtifactAccessContext,
    ArtifactResolver,
    ArtifactStoreConfig,
    ArtifactStoreError,
    ArtifactStoreFactory,
    FileInput,
    Gate1Normalizer,
    Gate2ManagedPrompt,
    Gate2InputReadinessConfig,
    Gate2InputReadinessFactory,
    Gate2ManagedPromptResolverFactory,
    Gate2DomainSourceFactRuntimeConfig,
    Gate2DomainSourceFactRuntimeFactory,
    Gate3ContextManifestFactory,
    Gate2PromptConfig,
    Gate2PromptError,
    Gate2PromptUserContext,
    Gate2ProviderExecutionMetadata,
    Gate2SourceFactRuntimeConfig,
    Gate2SourceFactRuntimeFactory,
    Gate2StructuredModelResult,
    StaticGate2PromptResolver,
    StaticGate2DomainPromptResolver,
    build_retention_policy,
    gate2_prompt_hash,
    persist_gate1_result,
    source_facts_json_schema,
    source_facts_provider_schema_hash,
    source_facts_response_format,
    source_facts_schema_hash,
    source_fact_selection_provider_json_schema,
    validate_source_fact_selection,
)
from broker_reports_gate1.gate2_source_fact_contracts import FACT_TYPES
from broker_reports_gate1.gate2_source_fact_runtime import (
    FACTORY_REQUIRED as RUNTIME_FACTORY_REQUIRED,
    FORBIDDEN as RUNTIME_FORBIDDEN,
)
from broker_reports_gate1.gate2_source_fact_validation import (
    FACTORY_REQUIRED as VALIDATOR_FACTORY_REQUIRED,
    FORBIDDEN as VALIDATOR_FORBIDDEN,
)


FIXTURES = REPO / "docs" / "stage2" / "testdata" / "broker_reports_gate1_normalization"


def _enum_value_count(value: Any) -> int:
    if isinstance(value, dict):
        own = len(value.get("enum") or []) if isinstance(value.get("enum"), list) else 0
        return own + sum(_enum_value_count(item) for item in value.values())
    if isinstance(value, list):
        return sum(_enum_value_count(item) for item in value)
    return 0


class RuntimeBoundaryModel:
    @staticmethod
    def execution_contract(model_id: str) -> Gate2ProviderExecutionMetadata:
        return Gate2ProviderExecutionMetadata(
            provider_id="test",
            provider_profile_id="test_boundary",
            provider_profile_revision="test-boundary-revision",
            adapter_id="test_boundary",
            adapter_version="1.0.0",
            requested_model_id=model_id,
            structured_output_mode="openwebui_response_format_json_schema",
            response_format_type="json_schema",
            response_format_schema_mode="strict_json_schema",
        )


class FullUnionBoundaryModel(RuntimeBoundaryModel):
    def __init__(self, *, mutation: str | None = None) -> None:
        self.mutation = mutation
        self.calls: list[dict[str, Any]] = []

    async def extract(self, *, prompt, package, model_id, response_format):
        self.calls.append(
            {
                "prompt_ref": prompt.prompt_ref,
                "package_ref": package.get("package_artifact_ref"),
                "model_id": model_id,
                "response_format": copy.deepcopy(response_format),
            }
        )
        candidate = _full_union_candidate(package)
        if self.mutation == "foreign_ref":
            candidate["facts"][0]["original_value_refs"]["amount"] = ["srcval_foreign"]
        elif self.mutation == "gate3_field":
            candidate["facts"][0]["tax_base"] = "100.00"
        elif self.mutation == "duplicate_fact":
            candidate["facts"].append(copy.deepcopy(candidate["facts"][0]))
            candidate["issue_linkage_summary"]["fact_issue_links_total"] = sum(
                len(item["linked_issue_refs"]) for item in candidate["facts"]
            )
        elif self.mutation == "raw_private":
            candidate["facts"][0]["raw_text"] = "forbidden private source content"
        elif self.mutation == "coverage_gap":
            candidate["coverage"]["no_fact_results"].pop()
        elif self.mutation == "normalized_value":
            candidate["facts"][0]["normalized_values"]["amount"] = "999.00"
            candidate["facts"][0]["amount"]["value_decimal"] = "999.00"
        elif self.mutation == "extracted_foreign_ref":
            candidate["facts"][0]["extracted_fields"][
                "source_visible_direction_refs"
            ] = ["srcval_foreign"]
        elif self.mutation == "overcomplete_issue" and candidate["facts"][0]["linked_issue_refs"]:
            candidate["facts"][0]["completeness"] = "complete"
        if self.mutation == "fallback":
            return Gate2StructuredModelResult(
                content=candidate,
                structured_output_mode="openwebui_response_format_json_object_fallback",
                response_format_type="json_object",
                response_format_schema_mode=None,
                fallback_used=True,
            )
        if self.mutation == "anthropic_strict":
            return Gate2StructuredModelResult(
                content=candidate,
                structured_output_mode="openwebui_anthropic_output_config_json_schema",
                response_format_type="json_schema",
                response_format_schema_mode="strict_json_schema",
                fallback_used=False,
            )
        return Gate2StructuredModelResult(content=candidate)


class InstrumentedFullUnionBoundaryModel(FullUnionBoundaryModel):
    def execution_contract(self, model_id: str) -> Gate2ProviderExecutionMetadata:
        return self._execution_metadata(model_id=model_id)

    async def extract(self, *, prompt, package, model_id, response_format):
        result = await super().extract(
            prompt=prompt,
            package=package,
            model_id=model_id,
            response_format=response_format,
        )
        return Gate2StructuredModelResult(
            content=result.content,
            execution_metadata=self._execution_metadata(
                model_id=model_id,
                resolved=True,
            ),
        )

    @staticmethod
    def _execution_metadata(
        *,
        model_id: str,
        resolved: bool = False,
    ) -> Gate2ProviderExecutionMetadata:
        return Gate2ProviderExecutionMetadata(
            provider_id="openai",
            provider_profile_id="openai_gpt",
            provider_profile_revision="test-source-profile-revision",
            adapter_id="openai_response_format",
            adapter_version="1.0.0",
            requested_model_id=model_id,
            resolved_model_id="resolved-source-model" if resolved else None,
            provider_response_id="private-source-response-id" if resolved else None,
            structured_output_mode="openwebui_response_format_json_schema",
            response_format_type="json_schema",
            response_format_schema_mode="strict_json_schema",
            duration_ms=11 if resolved else None,
            input_tokens=70 if resolved else None,
            output_tokens=30 if resolved else None,
            total_tokens=100 if resolved else None,
            finish_reason="stop" if resolved else None,
        )


class RepairingBoundaryModel(RuntimeBoundaryModel):
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def extract(self, *, prompt, package, model_id, response_format):
        self.calls.append(
            {
                "repair_context": copy.deepcopy(package.get("repair_context")),
                "expected_candidate_audit": copy.deepcopy(
                    package.get("expected_candidate_audit")
                ),
                "response_format": copy.deepcopy(response_format),
            }
        )
        candidate = _full_union_candidate(package)
        if package.get("repair_context") is None:
            candidate["coverage"]["no_fact_results"] = []
        return Gate2StructuredModelResult(content=candidate)


class SemanticSelectionBoundaryModel(RuntimeBoundaryModel):
    def __init__(self, *, mutation: str | None = None) -> None:
        self.mutation = mutation
        self.calls: list[dict[str, Any]] = []

    async def extract(self, *, prompt, package, model_id, response_format):
        expectation = package["coverage_expectation"]
        mandatory_refs = {
            item["source_ref"]
            for item in expectation["mandatory_no_fact_results"]
        }
        decision_refs = [
            item
            for item in expectation["selected_source_refs"]
            if item not in mandatory_refs
        ]
        selection = {
            "facts": [
                {
                    "source_ref": source_ref,
                    "fact_type": "unknown_source_row",
                    "fact_subtype": "unknown",
                    "value_bindings": [],
                    "confidence": "low",
                    "completeness": "uncertain",
                    "uncertainty_codes": ["synthetic_unknown"],
                }
                for source_ref in decision_refs
            ],
            "no_fact_results": [],
        }
        if self.mutation in {"typed", "cross_row_value_ref"}:
            rows = {
                row["row_ref"]: row
                for row in package["source_unit"]["model_source_projection"][
                    "rows"
                ]
            }
            typed_facts = []
            for source_ref in decision_refs:
                cells = rows[source_ref]["cells"]
                values = {
                    cell["header_label"]: cell for cell in cells
                }
                operation = values["operation"]["value"]
                fact_type = (
                    "trade_operation" if operation == "sell" else "income"
                )
                typed_facts.append(
                    {
                        "source_ref": source_ref,
                        "fact_type": fact_type,
                        "fact_subtype": operation,
                        "value_bindings": [
                            {
                                "field": field,
                                "source_value_ref": values[field][
                                    "source_value_ref"
                                ],
                            }
                            for field in ("date", "amount", "currency")
                        ],
                        "confidence": "high",
                        "completeness": "complete",
                        "uncertainty_codes": [],
                    }
                )
            selection["facts"] = typed_facts
            if self.mutation == "cross_row_value_ref":
                selection["facts"][0]["value_bindings"][0][
                    "source_value_ref"
                ] = selection["facts"][1]["value_bindings"][0][
                    "source_value_ref"
                ]
        elif self.mutation == "coverage_gap" and selection["facts"]:
            selection["facts"].pop()
        elif self.mutation == "system_metadata":
            selection["schema_version"] = "forbidden_model_metadata"
        self.calls.append(
            {
                "selection": copy.deepcopy(selection),
                "response_format": copy.deepcopy(response_format),
                "provider_schema_hash": package["output_schema"][
                    "provider_response_schema_hash"
                ],
            }
        )
        return Gate2StructuredModelResult(content=selection)


class NarrowDomainBoundaryModel(RuntimeBoundaryModel):
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def extract(self, *, prompt, package, model_id, response_format):
        domain = str(package["extractor_domain"])
        self.calls.append(
            {
                "domain": domain,
                "candidate_source_refs": copy.deepcopy(
                    package["candidate_source_refs"]
                ),
                "allowed_fact_types": copy.deepcopy(package["allowed_fact_types"]),
                "provider_fact_types": sorted(
                    item["properties"]["fact_type"]["const"]
                    for item in response_format["json_schema"]["schema"][
                        "properties"
                    ]["facts"]["items"]["anyOf"]
                ),
            }
        )
        helper_package = copy.deepcopy(package)
        helper_unit = helper_package["source_unit"]
        table_projection_mode = (
            helper_unit.get("source_input_mode") == "normalized_table_projection"
        )
        if table_projection_mode:
            for item in helper_unit["row_provenance"]:
                item["row_kind"] = (
                    "fact"
                    if item.get("row_role")
                    not in {"header_row", "repeated_header_row", "blank_row", "layout_row"}
                    else "layout"
                )
                item["row_range_ref"] = helper_unit["table_ref"]
            for item in helper_unit["cell_provenance"]:
                item["source_value_ref"] = next(
                    iter(item.get("source_value_refs") or []), None
                )
        ordinal_map = {
            int(item["row_ordinal"]): index
            for index, item in enumerate(helper_unit["row_provenance"], start=1)
        }
        for item in helper_unit["row_provenance"]:
            item["row_ordinal"] = ordinal_map[int(item["row_ordinal"])]
        for item in helper_unit["cell_provenance"]:
            item["row_ordinal"] = ordinal_map[int(item["row_ordinal"])]
        candidate = _full_union_candidate(helper_package)
        candidate["facts"] = [
            item for item in candidate["facts"] if item["fact_type"] == domain
        ]
        if table_projection_mode:
            for fact in candidate["facts"]:
                fact["source_location"]["row_range_ref"] = None
        selected = package["coverage_expectation"]["selected_source_refs"]
        candidate["coverage"]["fact_covered_refs"] = selected
        candidate["coverage"]["no_fact_results"] = []
        candidate["issue_linkage_summary"]["fact_issue_links_total"] = sum(
            len(item["linked_issue_refs"]) for item in candidate["facts"]
        )
        return Gate2StructuredModelResult(content=candidate)


class ResolvedNarrowDomainBoundaryModel(NarrowDomainBoundaryModel):
    @staticmethod
    def execution_contract(model_id: str) -> Gate2ProviderExecutionMetadata:
        return ResolvedNarrowDomainBoundaryModel._metadata(model_id)

    async def extract(self, *, prompt, package, model_id, response_format):
        result = await super().extract(
            prompt=prompt,
            package=package,
            model_id=model_id,
            response_format=response_format,
        )
        return Gate2StructuredModelResult(
            content=result.content,
            execution_metadata=self._metadata(model_id),
        )

    @staticmethod
    def _metadata(model_id: str) -> Gate2ProviderExecutionMetadata:
        return Gate2ProviderExecutionMetadata(
            provider_id="openai",
            provider_profile_id="openai_gpt",
            provider_profile_revision="test-gate3-provider-profile-revision",
            adapter_id="openai_response_format",
            adapter_version="1.0.0",
            requested_model_id=model_id,
            resolved_model_id=model_id,
            structured_output_mode="openwebui_response_format_json_schema",
            response_format_type="json_schema",
            response_format_schema_mode="strict_json_schema",
            canonical_request_schema_hash="test-canonical-request-schema-hash",
            adapted_request_schema_hash="test-adapted-request-schema-hash",
            finish_reason="stop",
        )


class CandidateBindingBoundaryModel:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def execution_contract(self, model_id: str) -> Gate2ProviderExecutionMetadata:
        return self._execution_metadata(model_id=model_id)

    async def extract(self, *, prompt, package, model_id, response_format):
        candidate_set = package["source_value_candidate_set"]
        relation_set = package["candidate_relation_set"]
        profile = package["candidate_binding_profile"]
        selected_refs = package["coverage_expectation"]["selected_source_refs"]
        binding_results = []
        selected_candidates: list[dict[str, Any]] = []
        for source_ref in selected_refs:
            row_candidates = [
                item
                for item in candidate_set["candidates"]
                if item["row_ref"] == source_ref
            ]
            selected_bindings = []
            used_candidate_ids: set[str] = set()
            selected_roles: set[str] = set()

            def select_role(role: str) -> None:
                if role in selected_roles:
                    return
                spec = profile["roles"][role]
                candidate = next(
                    (
                        item
                        for item in row_candidates
                        if item["candidate_id"] not in used_candidate_ids
                        and role in item["allowed_semantic_roles"]
                        and item["candidate_kind"] in spec["candidate_kinds"]
                    ),
                    None,
                )
                if candidate is None:
                    raise AssertionError(
                        f"synthetic boundary cannot satisfy required role {role}"
                    )
                selected_bindings.append(
                    {
                        "fact_field_path": spec["fact_field_path"],
                        "candidate_id": candidate["candidate_id"],
                        "semantic_role": role,
                    }
                )
                selected_candidates.append(copy.deepcopy(candidate))
                selected_roles.add(role)
                used_candidate_ids.add(candidate["candidate_id"])

            for role in profile["required_roles"]:
                select_role(role)
            for role_group in profile["required_role_groups"]:
                if not set(role_group) & selected_roles:
                    select_role(
                        next(
                            role
                            for role in role_group
                            if any(
                                role in item["allowed_semantic_roles"]
                                for item in row_candidates
                            )
                        )
                    )
            relation_ids = [
                relation["relation_id"]
                for kind in profile["required_relation_kinds"]
                for relation in relation_set["relations"]
                if relation["relation_kind"] == kind
                and relation["row_refs"] == [source_ref]
            ][: len(profile["required_relation_kinds"])]
            binding_results.append(
                {
                    "source_ref": source_ref,
                    "fact_type": profile["domain"],
                    "selected_bindings": selected_bindings,
                    "selected_relation_ids": relation_ids,
                    "subtype_candidate": "unknown",
                    "confidence": "high",
                    "completeness": (
                        "partial" if package["allowed_issue_refs"] else "complete"
                    ),
                    "uncertainty_codes": [],
                    "resolved_ambiguity_group_refs": sorted(
                        {
                            item["ambiguity_group_ref"]
                            for item in selected_candidates
                            if item.get("ambiguity_group_ref")
                            and item["row_ref"] == source_ref
                        }
                    ),
                }
            )
        selection = {
            "schema_version": "broker_reports_candidate_binding_output_v0",
            "package_id": package["package_id"],
            "candidate_set_id": candidate_set["candidate_set_id"],
            "candidate_set_hash": candidate_set["candidate_set_hash"],
            "relation_set_id": relation_set["relation_set_id"],
            "relation_set_hash": relation_set["relation_set_hash"],
            "binding_results": binding_results,
            "no_fact_results": [],
        }
        self.calls.append(
            {
                "candidate_binding_mode": package["candidate_binding_mode"],
                "profile_domain": profile["domain"],
                "response_format": copy.deepcopy(response_format),
                "selection": copy.deepcopy(selection),
                "selected_candidates": selected_candidates,
            }
        )
        return Gate2StructuredModelResult(
            content=selection,
            execution_metadata=self._execution_metadata(
                model_id=model_id,
                resolved=True,
            ),
        )

    @staticmethod
    def _execution_metadata(
        *,
        model_id: str,
        resolved: bool = False,
    ) -> Gate2ProviderExecutionMetadata:
        return Gate2ProviderExecutionMetadata(
            provider_id="openai",
            provider_profile_id="openai_gpt",
            provider_profile_revision="test-profile-revision",
            adapter_id="openai_response_format",
            adapter_version="1.0.0",
            requested_model_id=model_id,
            resolved_model_id=model_id if resolved else None,
            provider_response_id=(
                "private-provider-response-id" if resolved else None
            ),
            structured_output_mode="openwebui_response_format_json_schema",
            response_format_type="json_schema",
            response_format_schema_mode="strict_json_schema",
            duration_ms=7 if resolved else None,
            input_tokens=41 if resolved else None,
            output_tokens=13 if resolved else None,
            total_tokens=54 if resolved else None,
            finish_reason="stop" if resolved else None,
        )


class BrokerReportsGate2SourceFactRuntimeTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.store = ArtifactStoreFactory(
            ArtifactStoreConfig(
                mode="sqlite",
                sqlite_path=root / "artifacts.sqlite3",
                payload_root=root / "payloads",
            )
        ).create()
        self.context, self.dcp_ref = self._persist_gate1()
        content = "Synthetic managed Gate 2 prompt with {{source_fact_package_json}}."
        self.prompt = Gate2ManagedPrompt(
            prompt_ref="prompt_gate2_test",
            command="broker_gate2_source_facts_v0",
            version="test-v1",
            content=content,
            hash=gate2_prompt_hash(content),
            source="test_boundary",
            template_id="broker_reports.source_fact_extraction.v0",
            template_kind="broker_reports_source_fact_extraction",
            prompt_contract_id="broker_reports_source_fact_prompt_v0",
            input_schema_version="broker_reports_source_fact_package_v0",
            output_schema_id="broker_reports.source_facts.schema.v0",
            output_schema_version="broker_reports_source_facts_v0",
            tags=("broker-reports-gate2", "structured-output"),
            safe_metadata={"name": "synthetic"},
        )

    def test_strict_schema_covers_full_v0_discriminated_union(self):
        schema = source_facts_json_schema()
        response_format = source_facts_response_format()
        variants = schema["properties"]["facts"]["items"]["oneOf"]
        fact_types = {
            variant["properties"]["fact_type"]["const"] for variant in variants
        }

        self.assertEqual(fact_types, FACT_TYPES)
        self.assertFalse(schema["additionalProperties"])
        self.assertTrue(response_format["json_schema"]["strict"])
        self.assertEqual(response_format["type"], "json_schema")
        provider_schema = response_format["json_schema"]["schema"]
        provider_variants = provider_schema["properties"]["facts"]["items"]["anyOf"]
        self.assertNotIn("oneOf", provider_schema["properties"]["facts"]["items"])
        self.assertEqual(
            {item["properties"]["fact_type"]["const"] for item in provider_variants},
            FACT_TYPES,
        )
        self.assertFalse(provider_schema["additionalProperties"])
        self.assertEqual(len(source_facts_schema_hash()), 64)
        self.assertEqual(len(source_facts_provider_schema_hash()), 64)
        self.assertNotEqual(source_facts_schema_hash(), source_facts_provider_schema_hash())

    def test_semantic_selection_runtime_materializes_canonical_facts(self):
        model = SemanticSelectionBoundaryModel()

        result = self._run(model, semantic_selection_enabled=True)

        self.assertEqual(result.terminal_status, "completed")
        self.assertEqual(
            len(result.selection_validation_refs),
            len(result.package_refs),
        )
        self.assertEqual(len(result.source_facts_refs), len(result.package_refs))
        self.assertEqual(len(result.raw_output_refs), len(result.package_refs))
        self.assertTrue(model.calls)
        for call, package_ref in zip(model.calls, result.package_refs, strict=True):
            schema = call["response_format"]["json_schema"]["schema"]
            self.assertEqual(set(schema["properties"]), {"facts", "no_fact_results"})
            self.assertNotIn("schema_version", schema["properties"])
            self.assertEqual(
                call["provider_schema_hash"],
                self.store.get_record_unchecked(package_ref).safe_metadata[
                    "package_response_schema_hash"
                ],
            )
            self.assertEqual(
                set(call["selection"]),
                {"facts", "no_fact_results"},
            )
        for ref in result.selection_validation_refs:
            record = self.store.get_record_unchecked(ref)
            self.assertEqual(
                record.artifact_type,
                "broker_reports_source_fact_selection_validation_v1",
            )
            self.assertEqual(record.safe_metadata["validator_status"], "passed")
            self.assertEqual(
                record.safe_metadata["model_system_metadata_fields_total"],
                0,
            )
        for ref in result.source_facts_refs:
            record = self.store.get_record_unchecked(ref)
            payload = self.store.read_payload(record)
            self.assertEqual(record.validation_status, "validated")
            self.assertEqual(payload["validator_status"], "passed")
            self.assertEqual(payload["coverage"]["coverage_status"], "complete")
            self.assertTrue(
                all(
                    fact["document_ref"] == record.document_id
                    and fact["extraction_audit"]["provider_response_schema_hash"]
                    == self.store.get_record_unchecked(
                        fact["extraction_package_ref"]
                    ).safe_metadata["package_response_schema_hash"]
                    for fact in payload["facts"]
                )
            )

    def test_semantic_selection_reproduces_bound_values_and_rejects_cross_row_refs(self):
        result = self._run(
            SemanticSelectionBoundaryModel(mutation="typed"),
            semantic_selection_enabled=True,
        )

        self.assertEqual(result.terminal_status, "completed")
        payload = self.store.read_payload(
            self.store.get_record_unchecked(result.source_facts_refs[0])
        )
        self.assertEqual(
            {fact["fact_type"] for fact in payload["facts"]},
            {"trade_operation", "income"},
        )
        self.assertTrue(
            all(
                fact["normalized_values"]["amount"] is not None
                and len(fact["original_value_refs"]["amount"]) == 1
                for fact in payload["facts"]
            )
        )

        rejected = self._run(
            SemanticSelectionBoundaryModel(mutation="cross_row_value_ref"),
            semantic_selection_enabled=True,
        )
        self.assertEqual(rejected.terminal_status, "completed_with_rejections")
        validation = self.store.read_payload(
            self.store.get_record_unchecked(
                rejected.selection_validation_refs[0]
            )
        )
        self.assertIn(
            "source_fact_selection_value_ref_out_of_scope",
            validation["error_code_counts"],
        )

    def test_semantic_selection_rejects_missing_coverage_without_canonical_output(self):
        result = self._run(
            SemanticSelectionBoundaryModel(mutation="coverage_gap"),
            semantic_selection_enabled=True,
        )

        self.assertEqual(result.terminal_status, "completed_with_rejections")
        self.assertFalse(result.source_facts_refs)
        self.assertTrue(result.selection_validation_refs)
        self.assertTrue(
            all(
                self.store.get_record_unchecked(ref).safe_metadata[
                    "validator_status"
                ]
                == "failed"
                for ref in result.selection_validation_refs
            )
        )

    def test_semantic_selection_schema_forbids_model_system_metadata(self):
        model = SemanticSelectionBoundaryModel(mutation="system_metadata")
        result = self._run(model, semantic_selection_enabled=True)

        self.assertEqual(result.terminal_status, "completed_with_rejections")
        selection = model.calls[0]["selection"]
        package = self.store.read_payload(
            self.store.get_record_unchecked(result.package_refs[0])
        )
        validation = validate_source_fact_selection(
            selection=selection,
            package=package,
        )
        self.assertEqual(validation["validator_status"], "failed")
        self.assertIn(
            "source_fact_selection_schema_mismatch",
            validation["error_code_counts"],
        )
        self.assertEqual(validation["model_system_metadata_fields_total"], 1)
        schema = source_fact_selection_provider_json_schema(package)
        self.assertFalse(schema["additionalProperties"])
        self.assertNotIn("schema_version", schema["properties"])

    def test_semantic_selection_schema_does_not_duplicate_bounded_enums(self):
        package = {
            "coverage_expectation": {
                "selected_source_refs": [f"source-{index}" for index in range(196)],
                "mandatory_no_fact_results": [],
            },
            "allowed_source_value_refs": [
                f"value-{index}" for index in range(59)
            ],
            "allowed_fact_types": sorted(FACT_TYPES),
        }

        schema = source_fact_selection_provider_json_schema(package)
        fact_schema = schema["properties"]["facts"]["items"]

        self.assertNotIn("anyOf", fact_schema)
        self.assertEqual(
            set(fact_schema["properties"]["fact_type"]["enum"]),
            FACT_TYPES,
        )
        self.assertLessEqual(_enum_value_count(schema), 1000)

    def test_gate2_execution_appends_artifacts_without_mutating_gate1_source_memory(self):
        gate1_before = {
            record.artifact_id: self._artifact_semantic_snapshot(record)
            for record in self.store.list_by_run(self.context.normalization_run_id)
        }

        result = self._run(FullUnionBoundaryModel())

        self.assertEqual(result.terminal_status, "completed")
        gate1_after = {
            record.artifact_id: self._artifact_semantic_snapshot(record)
            for record in self.store.list_by_run(self.context.normalization_run_id)
            if record.artifact_id in gate1_before
        }
        self.assertEqual(gate1_after, gate1_before)
        self.assertGreater(
            len(self.store.list_by_run(self.context.normalization_run_id)),
            len(gate1_before),
        )

    def test_domain_runtime_routes_narrows_validates_stitches_and_persists(self):
        model = NarrowDomainBoundaryModel()
        prompts = {
            domain: self._domain_prompt(domain)
            for domain in ("trade_operation", "income")
        }
        runtime = Gate2DomainSourceFactRuntimeFactory(
            store=self.store,
            prompt_resolver=StaticGate2DomainPromptResolver(prompts),
            model_client=model,
            config=Gate2DomainSourceFactRuntimeConfig(
                model_id="synthetic-domain-model",
                wave="primary",
                run_mode="synthetic",
                document_batch_limit=1,
                source_unit_limit=1,
                segmentation_enabled=False,
                domain_allowlist=("trade_operation", "income"),
                max_repair_attempts=0,
            ),
        ).create()
        result = asyncio.run(
            runtime.run(
                domain_context_packet_ref=self.dcp_ref,
                context=self.context,
                prompt_user_context=Gate2PromptUserContext(
                    user_id=self.context.user_id,
                    user_role="admin",
                ),
            )
        )

        self.assertEqual(result.terminal_status, "completed")
        self.assertEqual(len(result.route_refs), 1)
        self.assertEqual(len(result.domain_package_refs), 2)
        self.assertEqual(len(result.source_facts_refs), 2)
        self.assertEqual(len(result.domain_source_facts_refs), 2)
        self.assertEqual(len(result.stitch_result_refs), 1)
        self.assertEqual(
            result.safe_summary["domain_packages"],
            {
                "total": 2,
                "accepted": 2,
                "rejected": 0,
                "accepted_by_domain": {"income": 1, "trade_operation": 1},
                "rejected_by_domain": {},
            },
        )
        self.assertEqual(result.safe_summary["coverage"]["uncovered_total"], 0)
        self.assertEqual(result.safe_summary["coverage"]["conflict_total"], 0)
        self.assertTrue(result.safe_summary["ready_for_primary_expansion"])
        self.assertEqual({item["domain"] for item in model.calls}, {"income", "trade_operation"})
        for call in model.calls:
            self.assertTrue(
                set(call["provider_fact_types"]) <= set(call["allowed_fact_types"])
            )
            self.assertIn(call["domain"], call["provider_fact_types"])
            self.assertEqual(len(call["candidate_source_refs"]), 1)
        for ref in result.domain_package_refs:
            record = self.store.get_record_unchecked(ref)
            self.assertEqual(record.artifact_type, "broker_reports_domain_extraction_package_v0")
            self.assertEqual(record.storage_backend, "project_artifact_payload")
        for ref in result.source_facts_refs:
            self.assertEqual(
                self.store.get_record_unchecked(ref).artifact_type,
                "broker_reports_source_facts_v0",
            )
        self.assertEqual(
            self.store.get_record_unchecked(result.stitch_result_refs[0]).artifact_type,
            "broker_reports_source_fact_stitch_result_v0",
        )

    def test_domain_runtime_persists_selected_derived_unit_from_complete_parent(self):
        context, dcp_ref = self._persist_gate1(
            case_id="synthetic-segmented-domain-runtime-case",
            truncate_source_slice=True,
        )
        model = NarrowDomainBoundaryModel()
        runtime = Gate2DomainSourceFactRuntimeFactory(
            store=self.store,
            prompt_resolver=StaticGate2DomainPromptResolver(
                {"trade_operation": self._domain_prompt("trade_operation")}
            ),
            model_client=model,
            config=Gate2DomainSourceFactRuntimeConfig(
                model_id="synthetic-domain-model",
                wave="primary",
                run_mode="synthetic",
                document_batch_limit=1,
                source_unit_limit=1,
                segmentation_enabled=True,
                source_segment_start=1,
                source_segment_limit=1,
                domain_allowlist=("trade_operation",),
                max_repair_attempts=0,
            ),
        ).create()
        result = asyncio.run(
            runtime.run(
                domain_context_packet_ref=dcp_ref,
                context=context,
                prompt_user_context=Gate2PromptUserContext(
                    user_id=context.user_id,
                    user_role="admin",
                ),
            )
        )

        self.assertEqual(result.terminal_status, "completed")
        self.assertEqual(len(result.segmentation_plan_refs), 1)
        self.assertEqual(len(result.derived_source_unit_refs), 1)
        self.assertEqual(len(result.route_refs), 1)
        self.assertEqual(len(result.domain_package_refs), 1)
        self.assertEqual(result.safe_summary["typed_facts_total"], 1)
        self.assertEqual(
            result.safe_summary["facts_by_type"], {"trade_operation": 1}
        )
        self.assertEqual(result.safe_summary["coverage"]["selected_total"], 1)
        self.assertEqual(result.safe_summary["coverage"]["uncovered_total"], 0)
        self.assertEqual(result.safe_summary["source_units"]["truncated_total"], 0)
        self.assertEqual(
            result.safe_summary["source_units"]["parent_truncated_total"], 0
        )
        self.assertEqual(
            result.safe_summary["source_units"]["bounded_complete_total"], 1
        )
        self.assertTrue(result.safe_summary["ready_for_primary_expansion"])

        plan_record = self.store.get_record_unchecked(
            result.segmentation_plan_refs[0]
        )
        self.assertEqual(
            plan_record.artifact_type,
            "broker_reports_source_unit_segmentation_plan_v0",
        )
        self.assertEqual(plan_record.visibility, "safe_internal")
        self.assertEqual(
            plan_record.payload["coverage"]["selected_for_extraction_total"],
            1,
        )
        self.assertEqual(
            plan_record.payload["coverage"]["parent_remainder_status"],
            "not_applicable_parent_complete",
        )
        derived_record = self.store.get_record_unchecked(
            result.derived_source_unit_refs[0]
        )
        self.assertEqual(
            derived_record.artifact_type, "broker_reports_derived_source_unit_v0"
        )
        self.assertEqual(derived_record.visibility, "private_case")
        self.assertEqual(derived_record.storage_backend, "project_artifact_payload")
        derived_payload = ArtifactResolver(self.store).resolve(
            result.derived_source_unit_refs[0], context
        )["payload"]
        self.assertFalse(
            derived_payload["source_unit"]["source_slice_truncated"]
        )
        self.assertFalse(
            derived_payload["source_unit"][
                "parent_source_slice_truncated"
            ]
        )
        self.assertEqual(
            derived_payload["source_unit"]["parent_remainder_status"],
            "not_applicable_parent_complete",
        )
        self.assertEqual({item["domain"] for item in model.calls}, {"trade_operation"})

    def test_csv_gate3_manifest_is_authoritative_private_safe_and_lifecycle_closed(self):
        model = ResolvedNarrowDomainBoundaryModel()
        runtime = Gate2DomainSourceFactRuntimeFactory(
            store=self.store,
            prompt_resolver=StaticGate2DomainPromptResolver(
                {"trade_operation": self._domain_prompt("trade_operation")}
            ),
            model_client=model,
            config=Gate2DomainSourceFactRuntimeConfig(
                model_id="synthetic-gate3-model",
                provider_profile_id="openai_gpt",
                wave="primary",
                run_mode="synthetic",
                document_batch_limit=1,
                source_unit_limit=1,
                segmentation_enabled=True,
                source_segment_start=1,
                source_segment_limit=1,
                domain_allowlist=("trade_operation",),
                max_repair_attempts=0,
                gate3_context_manifest_enabled=True,
            ),
        ).create()
        result = asyncio.run(
            runtime.run(
                domain_context_packet_ref=self.dcp_ref,
                context=self.context,
                prompt_user_context=Gate2PromptUserContext(
                    user_id=self.context.user_id,
                    user_role="admin",
                ),
            )
        )

        self.assertEqual(result.terminal_status, "completed")
        self.assertIsNotNone(result.gate3_context_manifest_ref)
        self.assertIsNotNone(result.answer_context_ref)
        self.assertIsNotNone(result.answer_context_receipt_ref)
        self.assertEqual(
            result.answer_context_selection_summary["selection_status"],
            "passed",
        )
        answer_context = AnswerContextSelectionFactory(
            store=self.store
        ).create().resolve_for_answer(
            context_ref=str(result.answer_context_ref),
            context=self.context,
        )
        self.assertTrue(answer_context["evidence_groups"])
        self.assertTrue(
            all(
                len(
                    [
                        representation
                        for representation in group["representations"]
                        if representation["interpretation_selection_role"]
                        == "interpretation_bearing"
                    ]
                )
                == 1
                for group in answer_context["evidence_groups"]
            )
        )
        self.assertEqual(
            result.gate3_context_manifest_summary["gate3_input_status"],
            "ready",
            result.gate3_context_manifest_summary,
        )
        service = Gate3ContextManifestFactory(store=self.store).create()
        manifest = service.resolve_for_gate3(
            manifest_ref=str(result.gate3_context_manifest_ref),
            context=self.context,
        )
        record = self.store.get_record_unchecked(
            str(result.gate3_context_manifest_ref)
        )
        self.assertEqual(record.visibility, "safe_internal")
        self.assertEqual(record.storage_backend, "project_artifact_store")
        self.assertEqual(manifest["gate3_input_status"], "ready")
        self.assertEqual(
            manifest["declared_scope"]["scope_kind"],
            "bounded_deterministic_csv_segments",
        )
        self.assertEqual(manifest["terminal_gate2"]["typed_facts_total"], 1)
        self.assertEqual(
            manifest["terminal_gate2"]["rejected_packages_total"], 0
        )
        self.assertEqual(manifest["zero_loss_reconciliation"]["status"], "reconciled")
        self.assertEqual(manifest["decision_metrics"]["uncovered_total"], 0)
        self.assertEqual(manifest["decision_metrics"]["conflict_total"], 0)
        self.assertEqual(manifest["decision_metrics"]["repair_attempts_total"], 0)
        self.assertEqual(manifest["decision_metrics"]["fallback_attempts_total"], 0)
        self.assertTrue(manifest["retention"]["coherent_descendant_horizon"])
        self.assertFalse(manifest["knowledge_vector_guard"]["knowledge_rag_used"])
        serialized = json.dumps(manifest, ensure_ascii=False)
        self.assertNotIn("100.00", serialized)
        self.assertNotIn("synthetic_gate2_value_refs.csv", serialized)

        private_facts = ArtifactResolver(self.store).resolve(
            manifest["artifact_roots"]["validated_source_fact_refs"][0],
            self.context,
        )["payload"]
        self.assertTrue(private_facts["facts"])
        for changed in (
            {"user_id": "wrong-user"},
            {"case_id": "wrong-case"},
            {"workspace_model_id": "wrong-workspace"},
        ):
            wrong = ArtifactAccessContext(
                **{**self.context.__dict__, **changed}
            )
            with self.assertRaises(ArtifactStoreError) as denied:
                service.resolve_for_gate3(
                    manifest_ref=str(result.gate3_context_manifest_ref),
                    context=wrong,
                )
            self.assertEqual(denied.exception.code, "artifact_access_denied")

        self.store.expire_run(
            self.context,
            datetime.now(timezone.utc) + timedelta(days=2),
        )
        with self.assertRaises(ArtifactStoreError) as expired:
            service.resolve_for_gate3(
                manifest_ref=str(result.gate3_context_manifest_ref),
                context=self.context,
            )
        self.assertEqual(expired.exception.code, "artifact_expired")
        self.store.purge_run(self.context)
        with self.assertRaises(ArtifactStoreError) as purged:
            service.resolve_for_gate3(
                manifest_ref=str(result.gate3_context_manifest_ref),
                context=self.context,
            )
        self.assertEqual(purged.exception.code, "artifact_purged")

    def test_domain_runtime_opt_in_consumes_validated_table_projection(self):
        readiness = Gate2InputReadinessFactory(
            store=self.store,
            config=Gate2InputReadinessConfig(prefer_table_projections=True),
        ).create().audit_and_build(
            domain_context_packet_ref=self.dcp_ref,
            context=self.context,
        )
        self.assertEqual(
            readiness.validation["validator_status"],
            "passed",
            readiness.validation,
        )
        model = NarrowDomainBoundaryModel()
        runtime = Gate2DomainSourceFactRuntimeFactory(
            store=self.store,
            prompt_resolver=StaticGate2DomainPromptResolver(
                {"income": self._domain_prompt("income")}
            ),
            model_client=model,
            config=Gate2DomainSourceFactRuntimeConfig(
                model_id="synthetic-domain-model",
                wave="primary",
                run_mode="synthetic",
                document_batch_limit=1,
                source_unit_limit=1,
                segmentation_enabled=True,
                source_segment_start=4,
                source_segment_limit=1,
                table_segment_max_refs=1,
                domain_allowlist=("income",),
                max_repair_attempts=0,
                prefer_table_projections=True,
            ),
        ).create()
        result = asyncio.run(
            runtime.run(
                domain_context_packet_ref=self.dcp_ref,
                context=self.context,
                prompt_user_context=Gate2PromptUserContext(
                    user_id=self.context.user_id,
                    user_role="admin",
                ),
            )
        )

        self.assertEqual(
            result.terminal_status,
            "completed",
            [
                self.store.get_record_unchecked(ref).payload
                for ref in result.validation_refs
            ],
        )
        self.assertEqual(len(result.source_facts_refs), 1)
        package = ArtifactResolver(self.store).resolve(
            result.domain_package_refs[0], self.context
        )["payload"]
        unit = package["source_unit"]
        self.assertEqual(unit["source_input_mode"], "normalized_table_projection")
        self.assertEqual(
            unit["private_slice_artifact_ref"],
            unit["table_projection_artifact_ref"],
        )
        self.assertIn(unit["table_projection_id"], package["allowed_evidence_refs"])
        self.assertEqual(result.safe_summary["coverage"]["uncovered_total"], 0)
        self.assertEqual(result.safe_summary["coverage"]["conflict_total"], 0)

    def test_domain_runtime_candidate_binding_opt_in_reaches_strict_validation_and_stitch(self):
        model = CandidateBindingBoundaryModel()
        runtime = Gate2DomainSourceFactRuntimeFactory(
            store=self.store,
            prompt_resolver=StaticGate2DomainPromptResolver(
                {"income": self._domain_prompt("income")}
            ),
            model_client=model,
            config=Gate2DomainSourceFactRuntimeConfig(
                model_id="synthetic-candidate-binding-model",
                wave="primary",
                run_mode="synthetic",
                document_batch_limit=1,
                source_unit_limit=1,
                segmentation_enabled=True,
                source_segment_start=4,
                source_segment_limit=1,
                table_segment_max_refs=1,
                domain_allowlist=("income",),
                max_repair_attempts=0,
                prefer_table_projections=True,
                candidate_binding_enabled=True,
                gate3_context_manifest_enabled=True,
            ),
        ).create()
        result = asyncio.run(
            runtime.run(
                domain_context_packet_ref=self.dcp_ref,
                context=self.context,
                prompt_user_context=Gate2PromptUserContext(
                    user_id=self.context.user_id,
                    user_role="admin",
                ),
            )
        )

        resolver = ArtifactResolver(self.store)
        validations = [
            resolver.resolve(ref, self.context)["payload"]
            for ref in result.validation_refs
        ]
        self.assertEqual(result.terminal_status, "completed", validations)
        self.assertEqual(len(model.calls), 1)
        self.assertEqual(len(result.domain_package_refs), 1)
        self.assertEqual(len(result.source_value_candidate_set_refs), 1)
        self.assertEqual(len(result.candidate_relation_set_refs), 1)
        self.assertEqual(len(result.candidate_binding_validation_refs), 1)
        self.assertEqual(len(result.source_facts_refs), 1)
        self.assertEqual(len(result.raw_output_refs), 1)
        self.assertEqual(len(result.validation_refs), 1)

        package = resolver.resolve(
            result.domain_package_refs[0], self.context
        )["payload"]
        raw = resolver.resolve(result.raw_output_refs[0], self.context)["payload"]
        facts = resolver.resolve(result.source_facts_refs[0], self.context)["payload"]
        validation = validations[0]
        call = model.calls[0]
        selected_candidate = call["selected_candidates"][0]
        fact = facts["facts"][0]

        self.assertEqual(
            package["candidate_binding_mode"],
            "candidate_ids_and_semantic_roles_v0",
        )
        persisted_binding_artifacts = [
            self.store.get_record_unchecked(ref)
            for ref in (
                result.source_value_candidate_set_refs
                + result.candidate_relation_set_refs
                + result.candidate_binding_validation_refs
            )
        ]
        self.assertEqual(
            [item.artifact_type for item in persisted_binding_artifacts],
            [
                "broker_reports_source_value_candidate_set_v0",
                "broker_reports_candidate_relation_set_v0",
                "broker_reports_candidate_binding_validation_v0",
            ],
        )
        self.assertTrue(
            all(
                item.visibility == "private_case"
                and item.storage_backend == "project_artifact_payload"
                for item in persisted_binding_artifacts
            )
        )
        self.assertEqual(package["candidate_binding_profile"]["domain"], "income")
        self.assertTrue(package["source_value_candidate_set"]["candidates"])
        self.assertEqual(call["candidate_binding_mode"], package["candidate_binding_mode"])

        self.assertEqual(call["profile_domain"], "income")
        self.assertEqual(
            call["response_format"]["json_schema"]["name"],
            "broker_reports_candidate_binding_output_v0",
        )
        self.assertTrue(call["response_format"]["json_schema"]["strict"])
        self.assertEqual(
            raw["raw_output"]["schema_version"],
            "broker_reports_candidate_binding_output_v0",
        )
        self.assertEqual(raw["model_call_status"], "passed")
        self.assertEqual(raw["provider_profile_id"], "openai_gpt")
        self.assertFalse(raw["provider_capability_probe"])
        raw_record = self.store.get_record_unchecked(result.raw_output_refs[0])
        self.assertEqual(
            raw["provider_execution"]["provider_response_id"],
            "private-provider-response-id",
        )
        self.assertEqual(
            raw["provider_execution"]["resolved_model_id"],
            "synthetic-candidate-binding-model",
        )
        self.assertEqual(raw["provider_execution"]["total_tokens"], 54)
        self.assertEqual(raw["provider_execution"]["duration_ms"], 7)
        self.assertNotIn(
            "provider_response_id",
            raw["provider_execution_safe"],
        )
        self.assertTrue(
            raw["provider_execution_safe"]["provider_response_id_present"]
        )
        self.assertNotIn(
            "private-provider-response-id",
            json.dumps(raw_record.safe_metadata, sort_keys=True),
        )
        self.assertEqual(raw_record.safe_metadata["model_id"], raw["model_id"])
        self.assertEqual(
            raw_record.safe_metadata["package_response_schema_hash"],
            raw["package_response_schema_hash"],
        )
        self.assertEqual(
            raw_record.safe_metadata["provider_response_schema_hash"],
            raw["provider_response_schema_hash"],
        )
        self.assertEqual(
            raw_record.safe_metadata["prompt_hash"],
            raw["prompt_snapshot"]["prompt_hash"],
        )

        self.assertEqual(validation["validator_status"], "passed", validation)
        self.assertEqual(
            validation["raw_output_artifact_ref"],
            result.raw_output_refs[0],
        )
        self.assertEqual(
            validation["provider_execution"],
            raw["provider_execution_safe"],
        )
        validation_record = self.store.get_record_unchecked(
            result.validation_refs[0]
        )
        self.assertEqual(
            validation_record.safe_metadata["provider_execution"],
            raw["provider_execution_safe"],
        )
        self.assertNotIn(
            "private-provider-response-id",
            json.dumps(validation_record.safe_metadata, sort_keys=True),
        )
        self.assertEqual(validation["errors"], [])
        self.assertEqual(validation["privacy_status"], "passed")
        self.assertEqual(validation["boundary_status"], "passed")
        self.assertEqual(facts["validator_status"], "passed")
        self.assertEqual(facts["coverage"]["coverage_status"], "complete")
        self.assertEqual(
            facts["coverage"]["fact_covered_refs"],
            package["coverage_expectation"]["selected_source_refs"],
        )
        self.assertEqual(fact["validator_status"], "passed")
        self.assertEqual(fact["validation_ref"], result.validation_refs[0])
        self.assertTrue(fact["fact_id"].startswith("sf_"))
        self.assertEqual(fact["fact_type"], "income")
        self.assertEqual(
            fact["normalized_values"]["amount"],
            selected_candidate["normalized_value"],
        )
        self.assertEqual(
            fact["original_value_refs"]["amount"],
            selected_candidate["source_value_refs"],
        )
        self.assertEqual(
            fact["extraction_package_ref"], result.domain_package_refs[0]
        )
        self.assertEqual(result.safe_summary["coverage"]["uncovered_total"], 0)
        run_payload = resolver.resolve(
            result.extraction_run_ref,
            self.context,
        )["payload"]
        execution_summary = run_payload["provider_execution_summary"]
        self.assertEqual(execution_summary["attempts_total"], 1)
        self.assertEqual(
            execution_summary["provider_profile_counts"],
            {"openai_gpt": 1},
        )
        self.assertEqual(
            execution_summary["resolved_model_counts"],
            {"synthetic-candidate-binding-model": 1},
        )
        self.assertEqual(execution_summary["total_tokens_total"], 54)
        self.assertEqual(execution_summary["latency_total_ms"], 7)
        self.assertNotIn(
            "private-provider-response-id",
            json.dumps(execution_summary, sort_keys=True),
        )
        self.assertEqual(result.safe_summary["coverage"]["conflict_total"], 0)
        self.assertTrue(
            all(
                record.storage_backend != "openwebui_knowledge"
                for record in self.store.list_by_run(self.context.normalization_run_id)
            )
        )
        manifest = Gate3ContextManifestFactory(store=self.store).create().resolve_for_gate3(
            manifest_ref=str(result.gate3_context_manifest_ref),
            context=self.context,
        )
        roots = manifest["artifact_roots"]
        self.assertEqual(
            roots["source_value_candidate_set_refs"],
            result.source_value_candidate_set_refs,
        )
        self.assertEqual(
            roots["candidate_relation_set_refs"],
            result.candidate_relation_set_refs,
        )
        self.assertEqual(
            roots["candidate_binding_validation_refs"],
            result.candidate_binding_validation_refs,
        )
        self.assertEqual(
            manifest["terminal_gate2"]["candidate_binding_validations_total"],
            1,
        )

    def test_domain_runtime_accepts_explicit_provider_qualification_mode(self):
        config = Gate2DomainSourceFactRuntimeConfig(
            model_id="qualification-model",
            run_mode="provider_qualification",
            provider_profile_id="anthropic_claude",
            provider_capability_probe=True,
        )
        runtime = Gate2DomainSourceFactRuntimeFactory(
            store=self.store,
            prompt_resolver=StaticGate2DomainPromptResolver(
                {"income": self._domain_prompt("income")}
            ),
            model_client=CandidateBindingBoundaryModel(),
            config=config,
        ).create()
        self.assertEqual(runtime.config.run_mode, "provider_qualification")
        self.assertEqual(runtime.config.provider_profile_id, "anthropic_claude")
        self.assertTrue(runtime.config.provider_capability_probe)

    def test_managed_prompt_resolver_enforces_gate2_contract_access_and_hash(self):
        db_path = Path(self._tmp.name) / "webui.db"
        content = (
            "Managed Gate 2 source facts prompt.\n"
            "Input: {{source_fact_package_json}}"
        )
        meta = {
            "template_kind": "broker_reports_source_fact_extraction",
            "template_id": "broker_reports.source_fact_extraction.v0",
            "prompt_contract_id": "broker_reports_source_fact_prompt_v0",
            "input_contract": "broker_reports_source_fact_package_v0",
            "output_schema_id": "broker_reports.source_facts.schema.v0",
            "output_schema_version": "broker_reports_source_facts_v0",
            "structured_output_required": True,
            "gate": "gate2",
        }
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
            conn.execute(
                """
                INSERT INTO prompt(id, command, user_id, name, content, data, meta, tags, version_id, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (
                    "prompt_gate2",
                    "broker_gate2_source_facts_v0",
                    "prompt-owner",
                    "Gate 2",
                    content,
                    "{}",
                    json.dumps(meta),
                    json.dumps(["broker-reports-gate2", "structured-output"]),
                    "v1",
                ),
            )
            conn.commit()
        finally:
            conn.close()
        resolver = Gate2ManagedPromptResolverFactory(
            Gate2PromptConfig(db_path=db_path, prompt_id="prompt_gate2")
        ).create()
        resolved = resolver.resolve(
            Gate2PromptUserContext(user_id="prompt-owner", user_role="user")
        )
        self.assertEqual(resolved.hash, gate2_prompt_hash(content))
        self.assertEqual(resolved.output_schema_id, "broker_reports.source_facts.schema.v0")
        self.assertEqual(resolved.command, "broker_gate2_source_facts_v0")
        with self.assertRaises(Gate2PromptError) as denied:
            resolver.resolve(Gate2PromptUserContext(user_id="foreign", user_role="user"))
        self.assertEqual(denied.exception.code, "gate2_prompt_access_denied")

    def test_runtime_persists_only_validator_accepted_full_union(self):
        model = InstrumentedFullUnionBoundaryModel()
        result = self._run(model)

        self.assertIn("Gate2SourceFactRuntimeFactory.create", RUNTIME_FACTORY_REQUIRED)
        self.assertIn("must not call models", RUNTIME_FORBIDDEN)
        self.assertIn("Gate2SourceFactValidatorFactory.create", VALIDATOR_FACTORY_REQUIRED)
        self.assertIn("must not promote model candidates", VALIDATOR_FORBIDDEN)
        self.assertEqual(result.terminal_status, "completed")
        self.assertEqual(result.safe_summary["facts_total"], 9)
        self.assertEqual(set(result.safe_summary["facts_by_type"]), FACT_TYPES)
        self.assertEqual(result.safe_summary["packages"]["accepted"], 1)
        self.assertEqual(result.safe_summary["packages"]["rejected"], 0)
        self.assertTrue(result.safe_summary["gate3_handoff_ready"])
        self.assertGreater(result.safe_summary["issue_linked_facts_total"], 0)
        self.assertEqual(len(result.source_facts_refs), 1)
        self.assertEqual(len(result.raw_output_refs), 1)
        self.assertEqual(len(result.validation_refs), 1)
        self.assertEqual(len(result.package_refs), 1)
        self.assertEqual(model.calls[0]["response_format"]["type"], "json_schema")
        self.assertTrue(model.calls[0]["response_format"]["json_schema"]["strict"])

        resolver = ArtifactResolver(self.store)
        facts = resolver.resolve(result.source_facts_refs[0], self.context)
        validation = resolver.resolve(result.validation_refs[0], self.context)
        raw = resolver.resolve(result.raw_output_refs[0], self.context)
        package = resolver.resolve(result.package_refs[0], self.context)
        self.assertEqual(facts["record"].visibility, "private_case")
        self.assertEqual(raw["record"].visibility, "private_case")
        self.assertEqual(package["record"].visibility, "private_case")
        self.assertEqual(validation["record"].visibility, "safe_internal")
        response_schema = model.calls[0]["response_format"]["json_schema"]["schema"]
        const_without_type = [
            path
            for path, node in _walk_schema_nodes(response_schema)
            if "const" in node and "type" not in node
        ]
        self.assertEqual(const_without_type, [])
        enum_values_total = sum(
            len(node.get("enum") or [])
            for _, node in _walk_schema_nodes(response_schema)
            if isinstance(node.get("enum"), list)
        )
        self.assertLess(enum_values_total, 1000)
        self.assertEqual(
            response_schema["properties"]["source_facts_set_id"]["const"],
            package["payload"]["expected_source_facts_set_id"],
        )
        self.assertEqual(
            response_schema["properties"]["package_refs"]["type"],
            "array",
        )
        self.assertNotIn("const", response_schema["properties"]["package_refs"])
        self.assertEqual(
            raw["payload"]["package_response_schema_hash"],
            package["payload"]["output_schema"]["package_response_schema_hash"],
        )
        self.assertEqual(
            len(package["payload"]["output_schema"]["package_response_schema_hash"]),
            64,
        )
        projection = package["payload"]["source_unit"]["model_source_projection"]
        self.assertEqual(projection["schema_version"], "gate2_model_table_projection_v0")
        self.assertTrue(projection["rows"])
        self.assertTrue(
            all(row["row_kind"] == "fact" for row in projection["rows"])
        )
        self.assertTrue(
            package["payload"]["coverage_expectation"][
                "mandatory_no_fact_results"
            ]
        )
        self.assertTrue(
            all(
                cell["cell_ref"] and cell["source_value_ref"]
                for row in projection["rows"]
                for cell in row["cells"]
            )
        )
        self.assertEqual(facts["payload"]["validator_status"], "passed")
        self.assertTrue(all(item["validator_status"] == "passed" for item in facts["payload"]["facts"]))
        self.assertTrue(all(item["validation_ref"] == result.validation_refs[0] for item in facts["payload"]["facts"]))
        self.assertTrue(all(item["fact_id"].startswith("sf_") for item in facts["payload"]["facts"]))
        self.assertEqual(raw["payload"]["model_call_status"], "passed")
        self.assertEqual(
            raw["payload"]["provider_execution"]["provider_response_id"],
            "private-source-response-id",
        )
        self.assertEqual(
            raw["payload"]["provider_execution"]["resolved_model_id"],
            "resolved-source-model",
        )
        self.assertNotIn(
            "provider_response_id",
            raw["payload"]["provider_execution_safe"],
        )
        self.assertEqual(
            validation["payload"]["raw_output_artifact_ref"],
            result.raw_output_refs[0],
        )
        self.assertEqual(
            validation["payload"]["provider_execution"],
            raw["payload"]["provider_execution_safe"],
        )
        self.assertNotIn(
            "private-source-response-id",
            json.dumps(validation["record"].safe_metadata, sort_keys=True),
        )
        self.assertEqual(validation["payload"]["validator_status"], "passed")
        run_payload = resolver.resolve(
            result.extraction_run_ref,
            self.context,
        )["payload"]
        self.assertEqual(
            run_payload["provider_execution_summary"]["total_tokens_total"],
            100,
        )
        self.assertEqual(
            run_payload["provider_execution_summary"]["latency_total_ms"],
            11,
        )
        self.assertNotIn(
            "private-source-response-id",
            json.dumps(
                run_payload["provider_execution_summary"],
                sort_keys=True,
            ),
        )
        self.assertNotIn("100.00", result.compact_russian_summary)
        self.assertNotIn("synthetic_gate2_value_refs.csv", result.compact_russian_summary)
        self.assertIn("Расчёт налогов, декларация и XLS/XLSX не выполнялись.", result.compact_russian_summary)
        self.assertTrue(
            all(
                record.storage_backend != "openwebui_knowledge"
                for record in self.store.list_by_run(self.context.normalization_run_id)
            )
        )

    def test_runtime_accepts_anthropic_native_strict_mode_without_accepting_fallback(self):
        result = self._run(FullUnionBoundaryModel(mutation="anthropic_strict"))

        self.assertEqual(result.terminal_status, "completed")
        self.assertEqual(result.safe_summary["packages"]["accepted"], 1)
        self.assertEqual(result.safe_summary["packages"]["rejected"], 0)
        self.assertEqual(len(result.source_facts_refs), 1)
        self.assertEqual(len(result.validation_refs), 1)

    def test_foreign_value_ref_and_gate3_semantics_fail_closed_after_private_raw_persistence(self):
        for mutation, expected_code in (
            ("foreign_ref", "source_fact_unknown_value_ref"),
            ("gate3_field", "source_fact_gate3_boundary_forbidden"),
            ("duplicate_fact", "source_fact_duplicate_id"),
            ("raw_private", "source_fact_private_field_forbidden"),
            ("coverage_gap", "source_fact_coverage_gap"),
            ("normalized_value", "source_fact_normalized_value_unreproducible"),
            ("extracted_foreign_ref", "source_fact_unknown_value_ref"),
            ("overcomplete_issue", "source_fact_completeness_overstated"),
            ("fallback", "source_fact_structured_output_required"),
        ):
            with self.subTest(mutation=mutation):
                context, dcp_ref = self._persist_gate1(case_id=f"case-{mutation}")
                result = self._run(
                    FullUnionBoundaryModel(mutation=mutation),
                    context=context,
                    dcp_ref=dcp_ref,
                )
                self.assertEqual(result.terminal_status, "completed_with_rejections")
                self.assertEqual(result.source_facts_refs, [])
                self.assertEqual(len(result.raw_output_refs), 1)
                self.assertEqual(len(result.validation_refs), 1)
                raw_record = self.store.get_record_unchecked(result.raw_output_refs[0])
                validation_record = self.store.get_record_unchecked(result.validation_refs[0])
                self.assertEqual(raw_record.visibility, "private_case")
                self.assertEqual(validation_record.visibility, "safe_internal")
                validation = self.store.read_payload(validation_record)
                self.assertIn(expected_code, {item["code"] for item in validation["errors"]})
                self.assertEqual(validation["accepted_fact_ids"], [])

    def test_wrong_user_expiry_purge_and_source_delete_remain_fail_closed(self):
        with self.assertRaises(ArtifactStoreError) as wrong_user:
            self._run(
                FullUnionBoundaryModel(),
                context=ArtifactAccessContext(
                    **{**self.context.__dict__, "user_id": "foreign-user"}
                ),
            )
        self.assertEqual(wrong_user.exception.code, "artifact_access_denied")

        result = self._run(FullUnionBoundaryModel())
        facts_ref = result.source_facts_refs[0]
        affected = self.store.mark_source_file_deleted(
            ArtifactAccessContext(
                **{
                    **self.context.__dict__,
                    "source_file_id": "synthetic-source-file",
                }
            )
        )
        self.assertIn(facts_ref, affected.artifact_ids)
        with self.assertRaises(ArtifactStoreError) as purged:
            ArtifactResolver(self.store).resolve(facts_ref, self.context)
        self.assertEqual(purged.exception.code, "artifact_purged")

        context, dcp_ref = self._persist_gate1(case_id="case-expiry")
        expiring = self._run(FullUnionBoundaryModel(), context=context, dcp_ref=dcp_ref)
        self.store.expire_run(
            context,
            datetime.now(timezone.utc) + timedelta(days=2),
        )
        with self.assertRaises(ArtifactStoreError) as expired:
            ArtifactResolver(self.store).resolve(expiring.source_facts_refs[0], context)
        self.assertEqual(expired.exception.code, "artifact_expired")

    def test_truncated_legacy_preview_does_not_override_complete_full_source_unit(self):
        context, dcp_ref = self._persist_gate1(
            case_id="case-truncated-source-slice",
            truncate_source_slice=True,
        )
        result = self._run(
            FullUnionBoundaryModel(),
            context=context,
            dcp_ref=dcp_ref,
        )

        self.assertEqual(result.terminal_status, "completed")
        self.assertEqual(result.safe_summary["truncated_source_units_total"], 0)
        self.assertTrue(result.safe_summary["gate3_handoff_ready"])
        self.assertGreater(result.safe_summary["facts_total"], 0)

    def test_one_repair_attempt_uses_safe_errors_and_persists_both_audits(self):
        model = RepairingBoundaryModel()
        result = self._run(model, max_repair_attempts=1)

        self.assertEqual(result.terminal_status, "completed")
        self.assertEqual(len(model.calls), 2)
        self.assertIsNone(model.calls[0]["repair_context"])
        repair_context = model.calls[1]["repair_context"]
        self.assertEqual(repair_context["repair_attempt_count"], 1)
        self.assertTrue(repair_context["validation_errors"])
        self.assertEqual(
            set(repair_context["validation_errors"][0]),
            {"code", "subject"},
        )
        self.assertEqual(len(result.raw_output_refs), 2)
        self.assertEqual(len(result.validation_refs), 2)
        resolver = ArtifactResolver(self.store)
        raw_payloads = [
            resolver.resolve(ref, self.context)["payload"]
            for ref in result.raw_output_refs
        ]
        validations = [
            resolver.resolve(ref, self.context)["payload"]
            for ref in result.validation_refs
        ]
        facts = resolver.resolve(result.source_facts_refs[0], self.context)["payload"]
        self.assertEqual(
            [item["repair_attempt_count"] for item in raw_payloads],
            [0, 1],
        )
        self.assertEqual(
            [item["validator_status"] for item in validations],
            ["failed", "passed"],
        )
        self.assertEqual(facts["extraction_audit"]["repair_attempt_count"], 1)
        self.assertEqual(facts["extraction_audit"]["extraction_attempt_ordinal"], 2)

    def test_document_batch_is_explicit_in_run_and_summary(self):
        result = self._run(
            FullUnionBoundaryModel(),
            document_batch_start=0,
            document_batch_limit=1,
        )

        self.assertEqual(result.terminal_status, "completed")
        self.assertEqual(
            result.safe_summary["document_batch"],
            {
                "start": 0,
                "limit": 1,
                "wave_documents_total": 1,
                "selected_documents_total": 1,
                "has_more": False,
            },
        )

    def _run(
        self,
        model,
        *,
        context=None,
        dcp_ref=None,
        max_repair_attempts: int = 0,
        semantic_selection_enabled: bool = False,
        document_batch_start: int = 0,
        document_batch_limit: int | None = None,
    ):
        context = context or self.context
        runtime = Gate2SourceFactRuntimeFactory(
            store=self.store,
            prompt_resolver=StaticGate2PromptResolver(self.prompt),
            model_client=model,
            config=Gate2SourceFactRuntimeConfig(
                model_id="synthetic-structured-model",
                wave="primary",
                run_mode="synthetic",
                max_repair_attempts=max_repair_attempts,
                semantic_selection_enabled=semantic_selection_enabled,
                enable_exact_fact_type_hints=False,
                document_batch_start=document_batch_start,
                document_batch_limit=document_batch_limit,
            ),
        ).create()
        return asyncio.run(
            runtime.run(
                domain_context_packet_ref=dcp_ref or self.dcp_ref,
                context=context,
                prompt_user_context=Gate2PromptUserContext(
                    user_id=context.user_id,
                    user_role="admin",
                ),
            )
        )

    def _artifact_semantic_snapshot(self, record):
        return {
            "artifact_type": record.artifact_type,
            "schema_version": record.schema_version,
            "scope": (
                record.user_id,
                record.case_id,
                record.chat_id,
                record.workspace_model_id,
                record.normalization_run_id,
            ),
            "document_id": record.document_id,
            "source_file_ref": copy.deepcopy(record.source_file_ref),
            "visibility": record.visibility,
            "storage_backend": record.storage_backend,
            "retention_policy": record.retention_policy.to_dict(),
            "validation_status": record.validation_status,
            "lifecycle_status": record.lifecycle_status,
            "purge_status": record.purge_status,
            "payload": copy.deepcopy(self.store.read_payload(record)),
            "safe_metadata": copy.deepcopy(record.safe_metadata),
            "warning_codes": copy.deepcopy(record.warning_codes),
        }

    def _domain_prompt(self, domain: str) -> Gate2ManagedPrompt:
        content = f"Synthetic managed {domain} prompt with {{{{source_fact_package_json}}}}."
        return Gate2ManagedPrompt(
            prompt_ref=f"prompt_gate2_{domain}_test",
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

    def _persist_gate1(
        self,
        *,
        case_id: str = "synthetic-gate2-runtime-case",
        truncate_source_slice: bool = False,
    ):
        result = Gate1Normalizer().normalize(
            [
                FileInput.from_bytes(
                    private_ref="private-synthetic-gate2-runtime",
                    filename="synthetic_gate2_value_refs.csv",
                    content=(FIXTURES / "synthetic_gate2_value_refs.csv").read_bytes(),
                    mime_type="text/csv",
                )
            ],
            input_context={"clarification_criticality_refinement_enabled": True},
        )
        package = result.package
        document_ref = package["domain_context_packet"]["next_stage_refs"][
            "source_fact_ready_refs"
        ][0]
        slice_ref = next(
            item["slice_id"]
            for item in package["private_normalized_slices"]
            if item["document_id"] == document_ref
        )
        if truncate_source_slice:
            next(
                item
                for item in package["private_normalized_slices"]
                if item["slice_id"] == slice_ref
            )["truncated"] = True
        issue_ref = f"issue_synthetic_{case_id}"
        package["gate1_issue_ledger"]["entries"].append(
            {
                "issue_id": issue_ref,
                "normalization_run_id": package["normalization_run"]["run_id"],
                "issue_type": "metadata_gap",
                "target_document_refs": [document_ref],
                "criticality": "clarifying",
                "affected_stage": "source_fact_extraction",
                "blocked_stages": [],
                "stages_that_may_continue": ["source_fact_extraction"],
                "status": "unresolved",
                "unresolved_reason": "synthetic_proof_issue",
                "user_was_asked": False,
                "answer_supplied": False,
                "ask_policy": "do_not_ask",
                "resolution_refs": [],
                "evidence_refs": [slice_ref],
                "blocker_refs": [],
                "reason_codes": ["synthetic_confirmation_limit"],
                "provenance": {"source_artifact_type": "synthetic_fixture", "source_ref": slice_ref},
                "created_at": "2026-07-10T00:00:00Z",
                "updated_at": "2026-07-10T00:00:00Z",
                "safe_explanation": "Synthetic unresolved confirmation limit.",
            }
        )
        usage_entry = next(
            item
            for item in package["document_usage_classification"]["entries"]
            if item["document_ref"] == document_ref
        )
        usage_entry["issue_refs"] = sorted(set(usage_entry["issue_refs"] + [issue_ref]))
        usage_entry["warning_issue_refs"] = sorted(
            set(usage_entry["warning_issue_refs"] + [issue_ref])
        )
        usage_entry["issue_refs_by_stage"].setdefault("source_fact_extraction", []).append(
            issue_ref
        )
        usage_entry["readiness_by_stage"]["source_fact_extraction"] = "ready_with_issues"
        dcp = package["domain_context_packet"]
        dcp["unresolved_issue_refs"] = sorted(set(dcp["unresolved_issue_refs"] + [issue_ref]))
        dcp["document_issue_refs"].setdefault(document_ref, []).append(issue_ref)
        dcp["stage_readiness"]["source_fact_extraction"] = "ready_with_issue_context"
        package["gate2_handoff"].setdefault("document_issue_refs", {}).setdefault(
            document_ref, []
        ).append(issue_ref)
        run_id = result.package["normalization_run"]["run_id"]
        context = ArtifactAccessContext(
            user_id="gate2-runtime-user",
            normalization_run_id=run_id,
            case_id=case_id,
            chat_id=f"chat-{case_id}",
            workspace_model_id="broker-reports-gate2-runtime-test",
            allow_private=True,
            require_source_available=True,
        )
        manifest = persist_gate1_result(
            store=self.store,
            result=result,
            context=context,
            retention_policy=build_retention_policy(mode="api_smoke"),
            source_file_refs=[
                {
                    "provider": "openwebui",
                    "openwebui_file_id": "synthetic-source-file",
                    "source_deleted": False,
                }
            ],
        )
        return context, manifest.artifact_refs_by_type["domain_context_packet_v0"][0]


def _walk_schema_nodes(value: Any, path: str = "$"):
    if isinstance(value, dict):
        yield path, value
        for key, child in value.items():
            yield from _walk_schema_nodes(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk_schema_nodes(child, f"{path}[{index}]")


def _full_union_candidate(package: dict[str, Any]) -> dict[str, Any]:
    unit = package["source_unit"]
    projection = unit["normalized_source_projection"]
    if unit["unit_kind"] != "table_row_window":
        return _no_fact_candidate(package)
    cells = projection["cells"]
    row_provenance = unit["row_provenance"]
    cell_provenance = unit["cell_provenance"]
    fact_rows = [item for item in row_provenance if item["row_kind"] == "fact"]
    first_row = fact_rows[0]
    second_row = fact_rows[-1]

    def source_ref(row_ordinal: int, column_ordinal: int) -> str:
        return next(
            item["source_value_ref"]
            for item in cell_provenance
            if item["row_ordinal"] == row_ordinal and item["column_ordinal"] == column_ordinal
        )

    def cell_ref(row_ordinal: int, column_ordinal: int) -> str:
        return next(
            item["cell_ref"]
            for item in cell_provenance
            if item["row_ordinal"] == row_ordinal and item["column_ordinal"] == column_ordinal
        )

    issue_policy = _issue_policy(package)
    facts = []
    fact_types = [
        "trade_operation",
        "income",
        "withholding_tax",
        "fee_commission",
        "cash_movement",
        "currency_fx",
        "position_snapshot",
        "document_summary_evidence",
        "unknown_source_row",
    ]
    for index, fact_type in enumerate(fact_types):
        row = first_row if index % 2 == 0 else second_row
        row_ordinal = int(row["row_ordinal"])
        row_index = row_ordinal - 1
        row_values = cells[row_index]
        date_ref = source_ref(row_ordinal, 1)
        identifier_ref = source_ref(row_ordinal, 2)
        amount_ref = source_ref(row_ordinal, 3)
        currency_ref = source_ref(row_ordinal, 4)
        refs = {
            "date": [date_ref],
            "amount": [amount_ref],
            "currency": [currency_ref],
            "quantity": [],
            "rate": [],
            "converted_amount": [],
            "identifier": [identifier_ref],
            "label": [],
        }
        normalized = {
            "date": str(row_values[0]).strip(),
            "amount": str(row_values[2]).strip(),
            "currency": str(row_values[3]).strip().upper(),
            "quantity": None,
            "rate": None,
            "converted_amount": None,
            "identifier": str(row_values[1]).strip(),
            "label": None,
        }
        current_cell_refs = [
            cell_ref(row_ordinal, column) for column in (1, 2, 3, 4)
        ]
        evidence_refs = sorted(
            {
                row["row_ref"],
                row["row_range_ref"],
                unit["table_ref"],
                unit["parser_ref"],
                unit["source_checksum_ref"],
                *current_cell_refs,
            }
        )
        facts.append(
            {
                "fact_id": "pending",
                "fact_type": fact_type,
                "fact_subtype": None,
                "document_ref": package["document_ref"],
                "extraction_package_ref": package["package_artifact_ref"],
                "source_unit_ref": unit["unit_id"],
                "source_location": {
                    "private_slice_artifact_ref": unit["private_slice_artifact_ref"],
                    "slice_ref": unit["slice_ref"],
                    "source_granularity": "table_row",
                    "page_ref": None,
                    "section_ref": None,
                    "table_ref": unit["table_ref"],
                    "row_ref": row["row_ref"],
                    "row_range_ref": row["row_range_ref"],
                    "cell_refs": current_cell_refs,
                    "text_segment_refs": [],
                    "parser_ref": unit["parser_ref"],
                    "source_checksum_ref": unit["source_checksum_ref"],
                },
                "extracted_fields": _extracted_fields(fact_type, identifier_ref),
                "normalized_values": normalized,
                "original_value_refs": refs,
                "date": {
                    "value": normalized["date"],
                    "role": "source_unspecified_date",
                    "precision": "day",
                    "original_value_refs": [date_ref],
                },
                "amount": {
                    "value_decimal": normalized["amount"],
                    "amount_role": "source_visible_amount",
                    "currency": normalized["currency"],
                    "original_value_refs": [amount_ref],
                },
                "currency": {
                    "code": normalized["currency"],
                    "code_kind": "iso_4217_visible",
                    "original_value_refs": [currency_ref],
                },
                "quantity": None,
                "instrument": {
                    "safe_label": None,
                    "safe_label_ref": None,
                    "identifiers": [
                        {
                            "identifier_type": "ticker",
                            "identifier_value": normalized["identifier"],
                            "original_value_refs": [identifier_ref],
                        }
                    ],
                },
                "confidence": "low" if fact_type == "unknown_source_row" else "medium",
                "completeness": "uncertain" if fact_type == "unknown_source_row" else (
                    "partial" if issue_policy["linked_issue_refs"] else "complete"
                ),
                "evidence_refs": evidence_refs,
                "linked_issue_refs": issue_policy["linked_issue_refs"],
                "issue_impact": issue_policy["issue_impact"],
                "extraction_warnings": [],
                "downstream_use": {
                    "downstream_usable": True,
                    "gate3_ledger_candidate": True,
                    "cross_document_consolidation_allowed": False,
                    "tax_calculation_allowed": False,
                    "declaration_mapping_allowed": False,
                    "restriction_codes": [],
                },
                "extraction_audit": copy.deepcopy(package["expected_candidate_audit"]),
                "validator_status": "pending",
                "validation_ref": None,
            }
        )

    covered_refs = sorted({first_row["row_ref"], second_row["row_ref"]})
    expectation = package["coverage_expectation"]
    no_fact_results = [
        *[
            {"source_ref": ref, "reason_code": "header_row"}
            for ref in expectation["ignorable_header_refs"]
        ],
        *[
            {"source_ref": ref, "reason_code": "blank_row"}
            for ref in expectation["ignorable_blank_refs"]
        ],
        *[
            {"source_ref": ref, "reason_code": "layout_only"}
            for ref in expectation["layout_candidate_refs"]
        ],
    ]
    return {
        "schema_version": "broker_reports_source_facts_v0",
        "source_facts_set_id": package["expected_source_facts_set_id"],
        "extraction_run_id": package["extraction_run_id"],
        "normalization_run_id": package["normalization_run_id"],
        "case_id": package["case_id"],
        "package_refs": [package["package_artifact_ref"]],
        "document_refs": [package["document_ref"]],
        "facts": facts,
        "coverage": {
            "unit_coverage_ref": expectation["coverage_ref"],
            "selected_source_refs": expectation["selected_source_refs"],
            "fact_covered_refs": covered_refs,
            "no_fact_results": no_fact_results,
            "rejected_refs": [],
            "pending_refs": [],
            "coverage_status": "complete",
        },
        "issue_linkage_summary": {
            "package_issue_refs": package["allowed_issue_refs"],
            "fact_issue_links_total": sum(len(item["linked_issue_refs"]) for item in facts),
            "unresolved_issue_refs": sorted(
                item["issue_ref"]
                for item in package["issue_context"]
                if item.get("status") == "unresolved"
            ),
        },
        "extraction_audit": copy.deepcopy(package["expected_candidate_audit"]),
        "validation_ref": None,
        "validator_status": "pending",
        "created_at": package["created_at"],
    }


def _no_fact_candidate(package: dict[str, Any]) -> dict[str, Any]:
    expectation = package["coverage_expectation"]
    return {
        "schema_version": "broker_reports_source_facts_v0",
        "source_facts_set_id": package["expected_source_facts_set_id"],
        "extraction_run_id": package["extraction_run_id"],
        "normalization_run_id": package["normalization_run_id"],
        "case_id": package["case_id"],
        "package_refs": [package["package_artifact_ref"]],
        "document_refs": [package["document_ref"]],
        "facts": [],
        "coverage": {
            "unit_coverage_ref": expectation["coverage_ref"],
            "selected_source_refs": expectation["selected_source_refs"],
            "fact_covered_refs": [],
            "no_fact_results": [
                {"source_ref": ref, "reason_code": "non_fact_annotation"}
                for ref in expectation["selected_source_refs"]
            ],
            "rejected_refs": [],
            "pending_refs": [],
            "coverage_status": "complete",
        },
        "issue_linkage_summary": {
            "package_issue_refs": package["allowed_issue_refs"],
            "fact_issue_links_total": 0,
            "unresolved_issue_refs": sorted(
                item["issue_ref"]
                for item in package["issue_context"]
                if item.get("status") == "unresolved"
            ),
        },
        "extraction_audit": copy.deepcopy(package["expected_candidate_audit"]),
        "validation_ref": None,
        "validator_status": "pending",
        "created_at": package["created_at"],
    }


def _extracted_fields(fact_type: str, identifier_ref: str) -> dict[str, Any]:
    values = {
        "trade_operation": {
            "operation_type_candidate": "unknown",
            "source_visible_direction_refs": [identifier_ref],
        },
        "income": {
            "income_type_candidate": "other",
            "source_country_candidate": None,
            "source_country_value_refs": [],
        },
        "withholding_tax": {
            "withholding_type_candidate": "unknown",
            "source_country_candidate": None,
            "related_income_source_refs": [],
        },
        "fee_commission": {
            "fee_type_candidate": "other",
            "related_operation_source_refs": [],
        },
        "cash_movement": {
            "movement_type_candidate": "unknown",
            "description_safe_label": None,
            "description_value_refs": [],
        },
        "currency_fx": {"fx_fact_kind": "currency_amount"},
        "position_snapshot": {"position_kind_candidate": "security_position"},
        "document_summary_evidence": {
            "summary_kind_candidate": "source_total",
            "source_provided": True,
        },
        "unknown_source_row": {"unknown_reason_codes": ["synthetic_unknown_shape"]},
    }
    return values[fact_type]


def _issue_policy(package: dict[str, Any]) -> dict[str, Any]:
    impact = {
        "warning_issue_refs": [],
        "limits_confirmation_issue_refs": [],
        "blocks_fact_issue_refs": [],
        "blocks_consolidation_issue_refs": [],
        "blocks_declaration_issue_refs": [],
        "forbidden_assumption_codes": sorted(package["forbidden_assumptions"]),
    }
    mapping = {
        "warning": "warning_issue_refs",
        "limits_confirmation": "limits_confirmation_issue_refs",
        "blocks_fact": "blocks_fact_issue_refs",
        "blocks_consolidation": "blocks_consolidation_issue_refs",
        "blocks_declaration": "blocks_declaration_issue_refs",
    }
    for item in package["issue_context"]:
        key = mapping[item["impact"]]
        impact[key].append(item["issue_ref"])
    for key in mapping.values():
        impact[key] = sorted(set(impact[key]))
    return {
        "linked_issue_refs": sorted(package["allowed_issue_refs"]),
        "issue_impact": impact,
    }


if __name__ == "__main__":
    unittest.main()
