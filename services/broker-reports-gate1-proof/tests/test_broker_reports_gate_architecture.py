from __future__ import annotations

import ast
import json
import unittest
from pathlib import Path

from broker_reports_gate1.architecture_policy import (
    ARCHITECTURE_AUTHORITY,
    CANONICAL_PROMOTION_AUTHORITY,
    COMPONENT_RUNTIME_STATUSES,
    GATE1_INTERMEDIATE_LIFETIME,
    GATE1_PRIVATE_REPRESENTATION_AUTHORITY,
    GATE1_RUN_WIDE_PRIVATE_GRAPH_ALLOWED,
    KNOWLEDGE_RAG_VECTORIZATION_ALLOWED,
    LOCAL_OCR_WORKER_POOL_ALLOWED,
    LOCAL_OCR_PRODUCTION_ALLOWED,
    MODEL_CANONICAL_AUTHORITY,
    NATIVE_OPENWEBUI_DOCUMENT_PROCESSING_ALLOWED,
    PROVIDER_OUTPUT_AUTHORITY,
    WORKLOAD_ADMISSION,
    WORKLOAD_AUTHORITY,
    WORKLOAD_PRIMARY_WALL_TIMEOUT,
    VISUAL_RECOVERY_INPUT_SCOPES,
    VISUAL_RECOVERY_PRODUCTION_PROVIDER_PROFILES,
    WHOLE_DOCUMENT_PROVIDER_UPLOAD_ALLOWED,
)
from broker_reports_gate1 import architecture_policy
from broker_reports_gate1.gate2_financial_evidence_registry import (
    Gate2FinancialEvidenceRegistryFactory,
)
from broker_reports_gate1.gate2_financial_semantic_v6_choice import (
    LOCAL_CHOICE_OUTPUT_FIELDS,
    SEMANTIC_CHOICE_OUTPUT_FIELDS,
    _choice_schema,
    _context_v2_1_choice_schema,
    _local_choice_schema,
)
from broker_reports_gate1.gate2_financial_semantic_v6_evidence import (
    COMPATIBILITY_WRAPPER_DELEGATES_ONLY,
)


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "broker_reports_gate1"
REPOSITORY_ROOT = ROOT.parents[1]
ARCHITECTURE_DOCUMENT = REPOSITORY_ROOT / ARCHITECTURE_AUTHORITY
IMPLEMENTATION_AUTHORITY_DOCUMENT = (
    REPOSITORY_ROOT
    / "docs"
    / "stage2"
    / "contracts"
    / "BROKER_REPORTS_ARCHITECTURE_AUTHORITIES.md"
)
SERVICE_GUIDANCE = ROOT / "AGENTS.md"
GOAL12_CONTRACT = (
    REPOSITORY_ROOT
    / "docs"
    / "stage2"
    / "contracts"
    / "BROKER_REPORTS_GATE2_CONTEXT_V2_1_BUDGET_MODEL_SMOKE.v1.md"
)
GOAL12_PRECALL_PLAN = (
    REPOSITORY_ROOT
    / "docs"
    / "reports"
    / "2026-07-29"
    / (
        "BROKER_REPORTS_GATE2_CONTEXT_V2_1_BUDGET_MODEL_SMOKE_"
        "GOAL12.precall.plan.safe.json"
    )
)
GOAL12_LIVE_RUNNER = (
    ROOT
    / "scripts"
    / (
        "live_gate2_financial_semantic_v6_context_v2_1_"
        "three_provider_smoke.py"
    )
)
BROKER_REPORTS_CI_WORKFLOW = (
    REPOSITORY_ROOT / ".github" / "workflows" / "broker-reports-ci.yml"
)
OPENWEBUI_ACTIONS = ROOT / "openwebui_actions"
GENERATED_BUNDLES = (
    OPENWEBUI_ACTIONS / "broker_reports_gate1_pipe_bundled.py",
    OPENWEBUI_ACTIONS / "broker_reports_gate2_source_fact_pipe_bundled.py",
    OPENWEBUI_ACTIONS / "broker_reports_gate2_domain_source_fact_pipe_bundled.py",
)

GATE2_MODULES = {
    path.stem for path in PACKAGE.glob("gate2_*.py") if path.stem != "gate2_handoff"
} | {"gate3_context_manifest"}
GATE1_PRIVATE_IMPLEMENTATIONS = {
    "csv_profile",
    "bounded_graph",
    "document_memory",
    "full_source",
    "pdf_layout_units",
    "pdf_text_layer",
    "source_provenance",
    "table_projection",
    "visual_table_review_contracts",
}
PLATFORM_IMPLEMENTATIONS = {"artifact_store"}
PROVIDER_TRANSPORT_MODULES = {"gate2_model_clients", "gate2_provider_adapters"}
GATE2_BUSINESS_RUNTIME_MODULES = {
    "gate2_candidate_binding",
    "gate2_candidate_binding_runtime",
    "gate2_domain_finalization",
    "gate2_domain_packages",
    "gate2_domain_routing",
    "gate2_domain_runtime",
    "gate2_input_readiness",
    "gate2_source_fact_runtime",
    "gate2_source_fact_stitching",
    "gate2_source_fact_validation",
    "gate2_source_unit_segmentation",
    "gate2_table_packages",
    "gate3_context_manifest",
}
GATE3_FINANCIAL_DOMAIN_SUCCESSOR = "gate3_financial_domain_context"
GATE3_CURRENT_PROJECTION = "gate3_projection"
GATE3_CURRENT_CHUNKING = "gate3_structural_chunking"
GATE3_CURRENT_DICTIONARY = "gate3_financial_label_dictionary"
GATE3_CURRENT_DICTIONARY_CLI = "gate3_financial_label_dictionary_cli"
GATE3_CURRENT_LABELING = "gate3_bounded_labeling"
GATE3_CURRENT_ROLE_PACK = "gate3_financial_role_pack"
GATE3_CURRENT_ROLE_LABELING = "gate3_role_labeling"
GATE3_CURRENT_CHUNK_BATCH = "gate3_chunk_batch_labeling"
GATE3_CURRENT_ANNOTATIONS_PERSISTENCE = (
    "gate3_financial_annotations_persistence"
)
GATE3_CURRENT_CASE_READINESS = "gate3_ndfl_case_readiness"
GATE3_CURRENT_NDFL_WORKFLOW = "gate3_ndfl_workflow"
GATE3_CURRENT_METADATA_SOURCE_FACTS = "gate3_metadata_source_facts"
GATE3_LLM_METADATA_ADAPTER = "gate3_llm_metadata_adapter"
GATE3_CURRENT_EVIDENCE_DEMAND_PORT = "gate3_evidence_demand_port"


class BrokerReportsGateArchitectureTest(unittest.TestCase):
    def test_pdf_table_context_keeps_existing_domain_owners_separate(self):
        normalizer = (PACKAGE / "normalizer.py").read_text(encoding="utf-8")
        locator = (PACKAGE / "pdf_table_locator.py").read_text(encoding="utf-8")
        layout = (PACKAGE / "pdf_layout.py").read_text(encoding="utf-8")
        projection = (PACKAGE / "table_projection.py").read_text(
            encoding="utf-8"
        )
        canonical = (PACKAGE / "canonical_artifact.py").read_text(
            encoding="utf-8"
        )
        locator_imports = {
            str(node.module or "")
            for node in ast.walk(ast.parse(locator))
            if isinstance(node, ast.ImportFrom)
        }
        layout_imports = {
            str(node.module or "")
            for node in ast.walk(ast.parse(layout))
            if isinstance(node, ast.ImportFrom)
        }

        self.assertIn("NormalizedTableProjectionFactory(", normalizer)
        self.assertIn("PdfTableLocatorProjectionFactory", locator)
        self.assertFalse(
            {"pdf_layout", "pdf_layout_units", "table_projection"}
            & locator_imports
        )
        self.assertIn("class PdfPlumberLayoutAdapter", layout)
        self.assertNotIn("pdf_table_locator", layout_imports)
        self.assertIn("class TableProjectionValidator", projection)
        self.assertNotIn("CanonicalNormalizerFactory", projection)
        self.assertIn("class CanonicalNormalizerFactory", canonical)
        self.assertNotIn("PdfTableIntakeRuntimeFactory", canonical)

    def test_canonical_architecture_contains_runtime_authority_markers(self):
        authority = ARCHITECTURE_DOCUMENT.read_text(encoding="utf-8")
        required = {
            "Status: `CURRENT`",
            "CURRENT_PIPELINE_AUTHORITY = ONE",
            "### Gate 1 — Source custody",
            "### Gate 2 — Canonical source representation",
            "### Adaptive Context Boundary",
            "### Gate 3 — Source semantic adapter",
            "### Gate 4 — Normalized source facts",
            "### Gate 5 — Tax methodology and deterministic calculation",
            "### Declaration Semantics",
            "### Release / Completeness",
            "### Projection",
            "Gate3EvidenceDemandPortFactory.create",
            "Gate 5 never receives Canonical bytes",
            "Cold-agent navigation checks",
        }
        self.assertEqual(
            sorted(marker for marker in required if marker not in authority),
            [],
        )

    def test_active_ordinary_trade_route_has_one_documented_factory_chain(self):
        pipeline = ARCHITECTURE_DOCUMENT.read_text(encoding="utf-8")
        owners = IMPLEMENTATION_AUTHORITY_DOCUMENT.read_text(encoding="utf-8")
        guidance = SERVICE_GUIDANCE.read_text(encoding="utf-8")
        pipe = (
            OPENWEBUI_ACTIONS / "broker_reports_gate1_pipe.py"
        ).read_text(encoding="utf-8")

        required_pipeline = {
            "ACTIVE_ORDINARY_TRADE_ROUTE = ordinary_trade_exact_fingerprint_v1",
            "GATE3_EXECUTION_IN_ACTIVE_ORDINARY_TRADE_ROUTE = DISABLED",
            "LEGACY_SEMANTIC_FALLBACK = FORBIDDEN",
            "GATE3_BINDING_FIELD = COMPATIBILITY_FIELD_ONLY",
            "OrdinaryTradeProductionRuntimeFactory.create",
            "Gate4OrdinaryTradeCandidateRuntimeFactory.create",
        }
        self.assertEqual(
            sorted(marker for marker in required_pipeline if marker not in pipeline),
            [],
        )
        for marker in (
            "## Active ordinary-trade architecture",
            "### Active authorities",
            "### Historical / evidence only",
            "### Supported boundaries",
            "### Unsupported boundaries",
            "### Known compatibility debt",
            "### Forbidden cross-domain dependencies",
        ):
            self.assertIn(marker, owners)
        self.assertIn("Current Gate 3 type/role", guidance)
        self.assertIn("model passes", guidance)
        self.assertIn("never a semantic fallback", guidance)

        production_imports = _local_imports("ordinary_trade_production_runtime")
        self.assertTrue(
            {
                "canonical_store",
                "gate4_ordinary_trade_candidate",
                "ordinary_trade_candidate_runtime",
                "ordinary_trade_projection",
            }
            <= production_imports
        )
        self.assertTrue(
            {
                "canonical_store",
                "ordinary_trade_qualified_mappings",
                "ordinary_trade_semantic_compiler",
            }
            <= _local_imports("ordinary_trade_projection")
        )
        self.assertNotIn("ordinary_trade_qualified_mappings", production_imports)
        self.assertEqual(
            sorted(
                name
                for name in production_imports
                if name.startswith("gate3_")
                or name == "gate4_financial_case_cache"
            ),
            [],
        )
        self.assertNotIn(
            "canonical_store", _local_imports("gate4_ordinary_trade_candidate")
        )
        direct_gate5_composers = {
            path.stem
            for path in PACKAGE.glob("*.py")
            if "Gate5DeterministicSourceFactConsumptionRuntime"
            in _call_names(ast.parse(path.read_text(encoding="utf-8")))
        }
        self.assertEqual(
            direct_gate5_composers,
            {
                "gate5_deterministic_source_fact_consumption",
                "ordinary_trade_candidate_runtime",
            },
        )
        self.assertLess(
            pipe.index("if candidate_enabled:"),
            pipe.index("Gate2StructuredModelClientFactory("),
        )
        self.assertIn(
            "and not bool(self.valves.ordinary_trade_candidate_enabled)", pipe
        )

    def test_machine_readable_gate_ownership_matches_current_pipeline(self):
        self.assertEqual(
            architecture_policy.ARCHITECTURE_POLICY_VERSION,
            "broker_reports_architecture_policy_v14",
        )
        self.assertEqual(
            architecture_policy.GATE_OWNERSHIP,
            {
                "gate1": "authenticated_source_intake_and_custody",
                "gate2": "canonical_source_preservation",
                "adaptive_context": "structure_preserving_context_packaging",
                "gate3": "source_financial_labeling_and_role_binding",
                "gate4": "normalized_source_facts_and_case_query",
                "gate5": "deterministic_tax_methodology_and_calculation",
                "human_adapter": "typed_factual_human_evidence",
                "external_reference_facts": "typed_authoritative_external_evidence",
                "methodology_adapter": "reviewed_methodology_proposals_only",
                "declaration_semantics": "target_independent_declaration_meaning",
                "release": "evidence_completeness_and_release_decision",
                "projection": "representation_only",
                "presentation_adapter": (
                    "public_dialogue_wording_and_non_authoritative_answer_proposal"
                ),
            },
        )
        self.assertEqual(
            architecture_policy.ACTIVE_PRODUCT_ROUTES,
            {
                "ordinary_security_trades": {
                    "route_id": "ordinary_trade_exact_fingerprint_v1",
                    "composition_root": "OrdinaryTradeProductionRuntimeFactory.create",
                    "source_semantics_owner": (
                        "OrdinaryTradeQualifiedMappingAuthorityFactory.create"
                        "+OrdinaryTradeSemanticCompilerFactory.create"
                    ),
                    "mapping_contract": (
                        "broker_reports_ordinary_trade_schema_mapping_v3"
                    ),
                    "qualification_contract": (
                        "broker_reports_ordinary_trade_mapping_qualification_v2"
                    ),
                    "normalized_fact_contract": "Gate4FinancialCaseFactV2",
                    "canonical_completeness_owner": (
                        "OrdinaryTradeProjectionRuntime.current_case_coverage"
                    ),
                    "human_fact_owner": "Gate5HumanGapClosureRuntime",
                    "public_dialogue_owner": (
                        "ordinary_trade_declaration_chat_adapter"
                    ),
                    "presentation_transport_owner": (
                        "Pipe._call_openwebui_presentation_completion"
                    ),
                    "presentation_model_boundary": "PRESENTATION_ADAPTER",
                    "presentation_business_authority": False,
                    "case_metadata_source_owner": (
                        "Gate3MetadataSourceFactRuntime"
                    ),
                    "declaration_contract": (
                        "BROKER_REPORTS_ORDINARY_TRADE_DECLARATION_MVP.v1"
                    ),
                    "declaration_status": "active_bounded_fail_closed",
                    "taxpayer_identity_contract": (
                        "broker_reports_gate5_user_case_fact_v1:taxpayer_identity"
                    ),
                    "taxpayer_scope_contract": (
                        "primary_user_attested_taxpayer_slot_v1"
                    ),
                    "tax_period_selection_contract": (
                        "broker_reports_gate5_user_case_fact_v1:selected_tax_period"
                    ),
                    "operation_period_owner": (
                        "Gate5DeterministicSourceFactConsumptionRuntime.assemble_available"
                    ),
                    "position_scope_contract": (
                        "broker_reports_gate5_security_position_scope_v0"
                    ),
                    "profile_owners": [
                        "Gate5TrustedMethodologyAuthorityFactory.create",
                        (
                            "Gate5FullTargetXmlProjectionDefinitionAuthorityFactory."
                            "create"
                        ),
                    ],
                    "product_states": [
                        "INPUT_REQUIRED",
                        "DRAFT_READY",
                        "DECLARATION_XML_READY",
                        "OPEN_POSITION_RETAINED",
                        "ANALYSIS_READY_WITH_OPEN_ITEMS",
                        "ANALYSIS_ONLY_READY",
                        "NON_FILING_SURROGATE_READY",
                        "STOPPED_RESUMABLE",
                    ],
                    "gate3_runtime_status": (
                        "financial_llm_deployment_rollback_only"
                    ),
                    "case_metadata_source_status": (
                        "current_exact_canonical_supporting_owner"
                    ),
                    "semantic_fallback_allowed": False,
                }
            },
        )

    def test_public_dialogue_model_is_one_representation_only_boundary(self):
        route = architecture_policy.ACTIVE_PRODUCT_ROUTES[
            "ordinary_security_trades"
        ]
        classification = architecture_policy.PROVIDER_CALL_SITE_CLASSIFICATIONS[
            "ordinary_trade_public_dialogue"
        ]
        pipe = (
            OPENWEBUI_ACTIONS / "broker_reports_gate1_pipe.py"
        ).read_text(encoding="utf-8")

        self.assertEqual(
            classification,
            (
                "PRESENTATION_ADAPTER",
                "plain_language_dialogue_wording_and_answer_proposal",
                (
                    "ordinary_trade_public_dialogue_message_v1"
                    "|broker_reports_ordinary_trade_public_interpretation_v1"
                ),
            ),
        )
        self.assertIn(classification[0], architecture_policy.LLM_BOUNDARY_CLASSES)
        self.assertEqual(
            route["public_dialogue_owner"],
            "ordinary_trade_declaration_chat_adapter",
        )
        self.assertEqual(
            route["presentation_transport_owner"],
            "Pipe._call_openwebui_presentation_completion",
        )
        self.assertEqual(route["presentation_model_boundary"], classification[0])
        self.assertFalse(route["presentation_business_authority"])
        self.assertNotIn('getattr(request, "base_url"', pipe)
        self.assertIn("ndfl_presentation_openwebui_origin", pipe)
        self.assertIn("_NdflPresentationNoRedirectHandler", pipe)
        self.assertIn("NDFL_PRESENTATION_MAX_RESPONSE_BYTES + 1", pipe)

    def test_machine_readable_policy_is_fail_closed(self):
        self.assertFalse(NATIVE_OPENWEBUI_DOCUMENT_PROCESSING_ALLOWED)
        self.assertFalse(KNOWLEDGE_RAG_VECTORIZATION_ALLOWED)
        self.assertEqual(
            VISUAL_RECOVERY_PRODUCTION_PROVIDER_PROFILES,
            frozenset({"google_gemini"}),
        )
        self.assertEqual(
            VISUAL_RECOVERY_INPUT_SCOPES,
            frozenset({"declared_page", "table_crop"}),
        )
        self.assertFalse(WHOLE_DOCUMENT_PROVIDER_UPLOAD_ALLOWED)
        self.assertFalse(LOCAL_OCR_PRODUCTION_ALLOWED)
        self.assertFalse(LOCAL_OCR_WORKER_POOL_ALLOWED)
        self.assertEqual(PROVIDER_OUTPUT_AUTHORITY, "table_region_location_only")
        self.assertEqual(
            CANONICAL_PROMOTION_AUTHORITY,
            "deterministic_pdfplumber_source_projection_else_fail_closed",
        )
        self.assertEqual(MODEL_CANONICAL_AUTHORITY, 0)
        self.assertFalse(GATE1_RUN_WIDE_PRIVATE_GRAPH_ALLOWED)
        self.assertEqual(
            GATE1_INTERMEDIATE_LIFETIME,
            "one_document_then_seal_persist_release",
        )
        self.assertEqual(
            GATE1_PRIVATE_REPRESENTATION_AUTHORITY,
            "artifactstore_resolver_only",
        )
        self.assertEqual(
            COMPONENT_RUNTIME_STATUSES["gate1_bounded_graph"],
            "maintained",
        )
        self.assertEqual(COMPONENT_RUNTIME_STATUSES["workload_authority"], "maintained")
        self.assertEqual(WORKLOAD_AUTHORITY, "sqlite_cross_process_single_authority")
        self.assertEqual(WORKLOAD_ADMISSION, "capacity_queue_plus_worker_lease")
        self.assertIsNone(WORKLOAD_PRIMARY_WALL_TIMEOUT)

    def test_production_pipes_use_one_persisted_workload_factory_without_local_queues(self):
        pipe_paths = (
            OPENWEBUI_ACTIONS / "broker_reports_gate1_pipe.py",
            OPENWEBUI_ACTIONS / "broker_reports_gate2_source_fact_pipe.py",
            OPENWEBUI_ACTIONS / "broker_reports_gate2_domain_source_fact_pipe.py",
        )
        violations = []
        for path in pipe_paths:
            source = path.read_text(encoding="utf-8")
            if "WorkloadAuthorityFactory(" not in source:
                violations.append(f"{path.name}:factory_missing")
            if "wait_for_admission(" not in source:
                violations.append(f"{path.name}:admission_missing")
            for forbidden in (
                "asyncio.Semaphore(",
                "ThreadPoolExecutor(",
                "ProcessPoolExecutor(",
                "workload_admission.py",
            ):
                if forbidden in source:
                    violations.append(f"{path.name}:{forbidden}")
            if "gate2_" in path.name and "_assert_gate1_workload_completed(" not in source:
                violations.append(f"{path.name}:gate1_completion_gate_missing")
        self.assertEqual(violations, [])

    def test_production_python_has_no_heavy_local_ocr_import(self):
        forbidden_roots = {"paddle", "paddleocr", "easyocr", "torch"}
        violations = []
        for root in (PACKAGE, OPENWEBUI_ACTIONS):
            for path in sorted(root.glob("*.py")):
                tree = ast.parse(path.read_text(encoding="utf-8"))
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        imports = {alias.name.split(".", 1)[0] for alias in node.names}
                    elif isinstance(node, ast.ImportFrom) and node.module:
                        imports = {node.module.split(".", 1)[0]}
                    else:
                        continue
                    for name in sorted(imports & forbidden_roots):
                        violations.append(f"{path.name}:{name}")
        self.assertEqual(violations, [])

    def test_visual_components_are_explicitly_classified(self):
        expected = {
            "visual_table_vlm": "research_only",
            "visual_neutral_tables": "maintained_qualified_default_on",
            "visual_review_boundary": "research_only",
            "visual_recovery_handoff": "research_only",
            "pdf_table_locator_provider": "maintained_current",
            "pdf_csv_experiment_provider": "proof_only",
            "pdf_grid_experiment_provider": "compatibility_only",
            "pdf_hybrid_provider": "research_only",
            "pdf_dual_vlm_fact_providers": "research_only",
            "pdf_dual_vlm_canonical_table": "research_only",
            "pdf_dual_vlm_runtime": "research_only",
            "prove_visual_neutral_tables_actual_corpus": "offline_only",
        }
        self.assertEqual(
            {key: COMPONENT_RUNTIME_STATUSES.get(key) for key in expected},
            expected,
        )

    def test_gate2_imports_gate1_only_through_public_contract_surface(self):
        violations = []
        for module_name in sorted(GATE2_MODULES):
            for imported in _local_imports(module_name):
                if imported in GATE1_PRIVATE_IMPLEMENTATIONS:
                    violations.append(f"{module_name}->{imported}")
        self.assertEqual(violations, [])

    def test_gate2_does_not_import_or_call_store_implementation_reads(self):
        violations = []
        forbidden_calls = (
            ".get_record_unchecked(",
            ".list_by_run(",
            ".read_payload(",
        )
        for module_name in sorted(GATE2_MODULES):
            source = _source(module_name)
            for imported in _local_imports(module_name):
                if imported in PLATFORM_IMPLEMENTATIONS:
                    violations.append(f"{module_name}->{imported}")
            for marker in forbidden_calls:
                if marker in source:
                    violations.append(f"{module_name}:{marker}")
        self.assertEqual(violations, [])

    def test_gate1_has_no_reverse_dependency_on_gate2_business_runtime(self):
        allowed_compatibility_edge = ("table_projection", "gate2_table_packages")
        violations = []
        for path in sorted(PACKAGE.glob("*.py")):
            module_name = path.stem
            if module_name in GATE2_MODULES or module_name in {
                "__init__",
                "artifact_lifecycle",
                "artifact_models",
                "artifact_resolver",
                "artifact_retention",
                "artifact_store",
            }:
                continue
            for imported in _local_imports(module_name):
                edge = (module_name, imported)
                if (
                    imported in GATE2_BUSINESS_RUNTIME_MODULES
                    and edge != allowed_compatibility_edge
                ):
                    violations.append(f"{module_name}->{imported}")
        self.assertEqual(violations, [])

    def test_provider_transport_does_not_import_gate2_business_runtime(self):
        violations = []
        for module_name in sorted(PROVIDER_TRANSPORT_MODULES):
            for imported in _local_imports(module_name):
                if imported in GATE2_BUSINESS_RUNTIME_MODULES:
                    violations.append(f"{module_name}->{imported}")
        self.assertEqual(violations, [])

    def test_qualification_and_evidence_reuse_canonical_request_builder(self):
        qualification = "gate2_financial_semantic_v6_qualification_run"
        evidence = "gate2_financial_semantic_v6_evidence"

        self.assertNotIn("gate2_model_requests", _local_imports(qualification))
        self.assertEqual(
            _call_owners(evidence, "Gate2OpenWebUIRequestBuilder"),
            {"financial_semantic_v6_canonical_request"},
        )
        self.assertEqual(
            _call_owners(
                qualification,
                "financial_semantic_v6_canonical_request",
            ),
            {
                "qualify_financial_semantic_v6",
                "smoke_financial_semantic_v6",
            },
        )

    def test_qualification_does_not_parse_provider_specific_fields(self):
        module_name = "gate2_financial_semantic_v6_qualification_run"
        forbidden_payload_fields = {
            "choices",
            "prompt_tokens",
            "completion_tokens",
            "input_tokens_details",
            "output_tokens_details",
        }

        self.assertNotIn(
            "gate2_provider_adapters",
            _local_imports(module_name),
        )
        self.assertEqual(
            _string_constants(_tree(module_name)) & forbidden_payload_fields,
            set(),
        )

    def test_compatibility_request_entrypoint_delegates_only(self):
        wrapper = _function_node(
            _tree("gate2_financial_semantic_v6_evidence"),
            "financial_semantic_v6_canonical_request",
        )

        self.assertTrue(COMPATIBILITY_WRAPPER_DELEGATES_ONLY)
        self.assertEqual(
            _call_names(wrapper) & {"Gate2OpenWebUIRequestBuilder"},
            {"Gate2OpenWebUIRequestBuilder"},
        )
        self.assertFalse(
            any(isinstance(node, ast.Dict) for node in ast.walk(wrapper))
        )

    def test_candidate_compiler_has_no_financial_type_ids_or_regex(self):
        module_name = "gate2_financial_semantic_v6_candidate_compiler"
        tree = _tree(module_name)
        registry = Gate2FinancialEvidenceRegistryFactory().create()
        known_type_ids = set(registry.provider_type_enum())
        imported_roots = {
            name
            for node in ast.walk(tree)
            for name in _import_roots(node)
        }

        self.assertEqual(_string_constants(tree) & known_type_ids, set())
        self.assertNotIn("re", imported_roots)
        self.assertEqual(
            {
                name
                for name in _call_names(tree)
                if name in {"compile", "match", "search", "fullmatch"}
            },
            set(),
        )

    def test_v6_slim_candidate_stays_inside_the_existing_packet_owner(self):
        module_name = "gate2_financial_semantic_v6_packet"
        tree = _tree(module_name)
        class_names = {
            node.name for node in tree.body if isinstance(node, ast.ClassDef)
        }

        self.assertIn(
            "Gate2FinancialSemanticV6PacketFactory",
            class_names,
        )
        self.assertEqual(
            {
                name
                for name in class_names
                if name.endswith("SlimViewFactory")
                or name.endswith("SlimCandidateFactory")
            },
            set(),
        )
        self.assertEqual(
            list(PACKAGE.glob("gate2_financial_semantic_v6*slim*.py")),
            [],
        )

    def test_current_context_v2_1_reuses_existing_packet_and_projection_owners(
        self,
    ):
        packet_tree = _tree("gate2_financial_semantic_v6_packet")
        loader_definitions = {
            f"{path.stem}.{node.name}"
            for path in PACKAGE.glob("*.py")
            for node in ast.parse(path.read_text(encoding="utf-8")).body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == "load_gate2_financial_semantic_model_assets"
        }
        context_v2_factories = {
            f"{path.stem}.{node.name}"
            for path in PACKAGE.glob("*.py")
            for node in ast.parse(path.read_text(encoding="utf-8")).body
            if isinstance(node, ast.ClassDef)
            and "ContextV2" in node.name
            and node.name.endswith("Factory")
        }
        public_context_v2_builders = {
            f"{path.stem}.{node.name}"
            for path in PACKAGE.glob("*.py")
            for node in ast.parse(path.read_text(encoding="utf-8")).body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and not node.name.startswith("_")
            and "context_v2" in node.name
            and ("build" in node.name or "create" in node.name)
        }

        self.assertEqual(
            loader_definitions,
            {
                (
                    "gate2_financial_semantic_model_assets."
                    "load_gate2_financial_semantic_model_assets"
                )
            },
        )
        self.assertEqual(
            {
                path.name for path in PACKAGE.glob("*context_v2*.py")
            },
            {
                (
                    "gate2_financial_semantic_v6_context_v2_1_"
                    "budget_smoke.py"
                ),
                (
                    "gate2_financial_semantic_v6_context_v2_1_"
                    "budget_smoke_plan.py"
                ),
                (
                    "gate2_financial_semantic_v6_context_v2_1_"
                    "provider_proof.py"
                )
            },
        )
        self.assertEqual(
            context_v2_factories,
            {
                (
                    "gate2_financial_semantic_v6_context_v2_1_"
                    "budget_smoke_plan."
                    "Gate2FinancialSemanticV6ContextV21BudgetSmokePlanFactory"
                ),
                (
                    "gate2_financial_semantic_v6_context_v2_1_"
                    "provider_proof."
                    "Gate2FinancialSemanticV6ContextV21ProviderProofFactory"
                )
            },
        )
        self.assertEqual(
            public_context_v2_builders,
            {
                (
                    "gate2_financial_semantic_v6_context_v2_1_"
                    "budget_smoke."
                    "build_financial_semantic_v6_context_v2_1_"
                    "budget_smoke_plan"
                )
            },
        )
        self.assertEqual(
            {
                node.name
                for node in packet_tree.body
                if isinstance(node, ast.ClassDef)
                and node.name.endswith("Factory")
            },
            {"Gate2FinancialSemanticV6PacketFactory"},
        )
        self.assertIsNotNone(
            _method_node(
                _tree("gate2_financial_semantic_v5_projection"),
                "Gate2FinancialSemanticV5ProjectionFactory",
                "create_context_v2_candidate",
            )
        )
        self.assertEqual(
            _call_owners(
                "gate2_financial_semantic_v6_packet",
                "create_context_v2_candidate",
            ),
            set(),
        )
        self.assertEqual(
            _call_owners(
                "gate2_financial_semantic_v6_packet",
                "_context_v2_candidate_and_receipt",
            ),
            set(),
        )
        self.assertEqual(
            _call_owners(
                "gate2_financial_semantic_v6_packet",
                "create_minimal_managed_projection",
            ),
            {"Gate2FinancialSemanticV6PacketFactory._build"},
        )
        self.assertEqual(
            _call_owners(
                "gate2_financial_semantic_v6_packet",
                "_context_v2_1_candidate_and_receipt",
            ),
            {"Gate2FinancialSemanticV6PacketFactory._build"},
        )

        current_candidate_calls = [
            node
            for node in ast.walk(packet_tree)
            if isinstance(node, ast.Call)
            and _call_name(node.func)
            == "Gate2FinancialSemanticV6ContextV21Candidate"
        ]
        self.assertEqual(len(current_candidate_calls), 1)
        current_candidate_keywords = {
            keyword.arg: keyword.value
            for keyword in current_candidate_calls[0].keywords
            if keyword.arg is not None
        }
        for field, expected in (
            ("active", False),
            ("transport_eligible", False),
            ("provider_calls_total", 0),
        ):
            value = current_candidate_keywords.get(field)
            self.assertIsInstance(value, ast.Constant)
            self.assertEqual(value.value, expected)

    def test_minimal_managed_projection_reuses_owner_and_stays_inactive(self):
        projection_tree = _tree(
            "gate2_financial_semantic_v5_projection"
        )
        minimal_factories = {
            f"{path.stem}.{node.name}"
            for path in PACKAGE.glob("*.py")
            for node in ast.parse(
                path.read_text(encoding="utf-8")
            ).body
            if isinstance(node, ast.ClassDef)
            and "Minimal" in node.name
            and node.name.endswith("Factory")
        }

        self.assertIsNotNone(
            _method_node(
                projection_tree,
                "Gate2FinancialSemanticV5ProjectionFactory",
                "create_minimal_managed_projection",
            )
        )
        projection_factory = next(
            node
            for node in projection_tree.body
            if isinstance(node, ast.ClassDef)
            and node.name == "Gate2FinancialSemanticV5ProjectionFactory"
        )
        self.assertEqual(
            {
                node.name
                for node in projection_factory.body
                if isinstance(
                    node,
                    (ast.FunctionDef, ast.AsyncFunctionDef),
                )
                and not node.name.startswith("_")
            },
            {
                "create",
                "create_context_v2_candidate",
                "create_minimal_managed_projection",
            },
        )
        self.assertEqual(minimal_factories, set())
        self.assertEqual(
            list(PACKAGE.glob("*minimal*projection*.py")),
            [],
        )
        self.assertEqual(
            {
                owner
                for path in PACKAGE.glob("*.py")
                for owner in _call_owners(
                    path.stem,
                    "create_minimal_managed_projection",
                )
            },
            {"Gate2FinancialSemanticV6PacketFactory._build"},
        )
        inactive_profile = "minimal_model_surface_v1_candidate"
        for module_name in (
            "gate2_financial_semantic_v6_packet",
            "gate2_financial_semantic_v6_choice",
            "gate2_financial_semantic_v6_qualification_run",
            "gate2_model_requests",
            "gate2_model_clients",
            "gate2_provider_adapters",
        ):
            self.assertNotIn(
                inactive_profile,
                _string_constants(_tree(module_name)),
            )

    def test_context_v2_1_sidecars_enter_only_choice_and_linter_authorities(
        self,
    ):
        sidecar_fields = {
            "context_v2_candidate",
            "context_v2_mapping_receipt",
        }
        sidecar_markers = {
            "broker_reports_gate2_llm_semantic_context_v2_1_candidate",
            "broker_reports_gate2_llm_semantic_context_v2_1_mapping_receipt_v1",
            "non_active_context_v2_1_candidate",
            "private_context_v2_1_mapping_receipt",
        }
        active_packet_consumers = (
            "gate2_financial_semantic_v6_evidence",
            "gate2_financial_semantic_v6_qualification_run",
        )
        sealed_modules = (
            "gate2_financial_semantic_v6_qualification_run",
            "gate2_financial_semantic_v6_expansion",
            "gate2_financial_semantic_v6_prompt",
            "gate2_financial_semantic_v6_totality",
            "gate2_model_requests",
            "gate2_model_clients",
            "gate2_provider_adapters",
        )

        for module_name in sealed_modules:
            tree = _tree(module_name)
            self.assertEqual(
                _string_constants(tree) & sidecar_fields,
                set(),
            )
            self.assertTrue(
                all(
                    path.rsplit(".", 1)[-1] not in sidecar_fields
                    for path in _attribute_paths(tree)
                )
            )
            self.assertEqual(
                _string_constants(tree) & sidecar_markers,
                set(),
            )
        for authority_module in (
            "gate2_financial_semantic_v6_choice",
            "gate2_financial_semantic_v6_context_linter",
        ):
            authority_paths = _attribute_paths(_tree(authority_module))
            self.assertEqual(
                {
                    path.rsplit(".", 1)[-1]
                    for path in authority_paths
                    if path.rsplit(".", 1)[-1] in sidecar_fields
                },
                sidecar_fields,
            )
        evidence_tree = _tree("gate2_financial_semantic_v6_evidence")
        evidence_sidecar_owners = set()
        for node in evidence_tree.body:
            candidates = (
                (
                    (node.name, node),
                )
                if isinstance(
                    node,
                    (ast.FunctionDef, ast.AsyncFunctionDef),
                )
                else (
                    tuple(
                        (f"{node.name}.{method.name}", method)
                        for method in node.body
                        if isinstance(
                            method,
                            (ast.FunctionDef, ast.AsyncFunctionDef),
                        )
                    )
                    if isinstance(node, ast.ClassDef)
                    else ()
                )
            )
            for owner, candidate in candidates:
                if any(
                    path.rsplit(".", 1)[-1] in sidecar_fields
                    for path in _attribute_paths(candidate)
                ):
                    evidence_sidecar_owners.add(owner)
        self.assertEqual(
            evidence_sidecar_owners,
            {
                (
                    "Gate2FinancialSemanticV6DecisionEvidenceFactory."
                    "create_context_v2_1_candidate"
                ),
                "replay_financial_semantic_v6_context_v2_1_decision",
                "_context_v2_1_prepared_authority_is_valid",
                "_context_v2_1_replay_authorities",
                "_budget_smoke_request_authority",
                "_budget_smoke_replay_authorities",
            },
        )
        for active_evidence_node in (
            _method_node(
                evidence_tree,
                "Gate2FinancialSemanticV6DecisionEvidenceFactory",
                "create",
            ),
            _function_node(
                evidence_tree,
                "replay_financial_semantic_v6_decision",
            ),
            _function_node(
                evidence_tree,
                "financial_semantic_v6_canonical_request",
            ),
        ):
            self.assertTrue(
                all(
                    path.rsplit(".", 1)[-1] not in sidecar_fields
                    for path in _attribute_paths(active_evidence_node)
                )
            )
        proof_paths = _attribute_paths(
            _tree(
                "gate2_financial_semantic_v6_context_v2_1_"
                "provider_proof"
            )
        )
        self.assertEqual(
            {
                path.rsplit(".", 1)[-1]
                for path in proof_paths
                if path.rsplit(".", 1)[-1] in sidecar_fields
            },
            sidecar_fields,
        )
        linter_paths = _attribute_paths(
            _tree("gate2_financial_semantic_v6_context_linter")
        )
        self.assertIn(
            "choice_contract.context_v2_1_response_profile",
            linter_paths,
        )
        for module_name in active_packet_consumers:
            self.assertIn("packet.payload", _attribute_paths(_tree(module_name)))

    def test_goal12_precall_plan_is_frozen_non_active_and_bounded(self):
        contract = GOAL12_CONTRACT.read_text(encoding="utf-8")
        plan = json.loads(GOAL12_PRECALL_PLAN.read_text(encoding="utf-8"))
        accounting = plan["execution_accounting"]
        providers = plan["provider_model_parameter_ledger"]
        slots = plan["slots"]

        self.assertEqual(
            plan["integrity_hash"],
            "9191197bdc947d6ba86db3169ba0d8c911ef88423d611e2c4424a9379167cbab",
        )
        self.assertEqual(plan["status"], "frozen_preflight_not_executed")
        self.assertTrue(plan["frozen"])
        self.assertFalse(plan["active"])
        self.assertFalse(plan["transport_executed"])
        self.assertEqual(plan["production_admissions"], [])
        self.assertEqual(
            plan["provider_order"],
            ["openai_gpt", "anthropic_claude", "google_gemini"],
        )
        self.assertEqual(len(slots), 12)
        self.assertEqual(
            accounting,
            {
                "fallback_total": 0,
                "maximum_provider_submissions_total": 12,
                "planned_slots_total": 12,
                "provider_responses_total": 0,
                "provider_submissions_total": 0,
                "repair_total": 0,
                "retry_total": 0,
            },
        )
        self.assertTrue(
            all(slot["maximum_provider_submissions"] == 1 for slot in slots)
        )
        self.assertTrue(
            all(
                slot[counter] == 0
                for slot in slots
                for counter in (
                    "retry_total",
                    "repair_total",
                    "fallback_total",
                )
            )
        )
        self.assertTrue(
            all(
                provider["parameters"][flag] is False
                for provider in providers
                for flag in (
                    "model_aliases_allowed",
                    "runtime_model_override_allowed",
                    "runtime_parameter_override_allowed",
                    "retry_allowed",
                    "repair_allowed",
                    "fallback_allowed",
                )
            )
        )

        google = next(
            provider
            for provider in providers
            if provider["provider_profile_id"] == "google_gemini"
        )
        self.assertEqual(
            google["exact_model_id"],
            "models/gemini-3.1-flash-lite",
        )
        self.assertFalse(google["immutable_model_id_proven"])
        self.assertEqual(
            google["model_identity_kind"],
            "stable_selector_not_immutable",
        )
        self.assertEqual(
            google["model_identity_caveat"],
            "provider_inventory_has_no_dated_immutable_google_model_id",
        )
        self.assertTrue(
            all(
                slot["immutable_model_id_proven"] is False
                for slot in slots
                if slot["provider_profile_id"] == "google_gemini"
            )
        )

        required_contract_markers = {
            "# Broker Reports Gate 2 Context V2.1 Budget Model Smoke v1",
            plan["integrity_hash"],
            "`3 × 4 = 12` provider submissions",
            "`active=false`",
            "`production_admissions=[]`",
            "real `broker-reports-ci` GitHub Actions check",
            "fail closed\nbefore transport",
        }
        self.assertEqual(
            sorted(
                marker
                for marker in required_contract_markers
                if marker not in contract
            ),
            [],
        )

    def test_goal12_reuses_plan_client_evidence_and_report_authorities(self):
        plan_module = (
            "gate2_financial_semantic_v6_context_v2_1_budget_smoke_plan"
        )
        coordinator_module = (
            "gate2_financial_semantic_v6_context_v2_1_budget_smoke"
        )
        evidence_module = "gate2_financial_semantic_v6_evidence"
        report_module = "gate2_financial_semantic_v6_smoke_report"
        plan_tree = _tree(plan_module)
        coordinator_tree = _tree(coordinator_module)
        evidence_tree = _tree(evidence_module)
        report_tree = _tree(report_module)

        goal12_plan_factories = {
            f"{path.stem}.{node.name}"
            for path in PACKAGE.glob("*.py")
            for node in ast.parse(
                path.read_text(encoding="utf-8")
            ).body
            if isinstance(node, ast.ClassDef)
            and "BudgetSmokePlanFactory" in node.name
        }
        self.assertEqual(
            goal12_plan_factories,
            {
                (
                    f"{plan_module}."
                    "Gate2FinancialSemanticV6ContextV21BudgetSmokePlanFactory"
                )
            },
        )
        self.assertIsNotNone(
            _method_node(
                plan_tree,
                "Gate2FinancialSemanticV6ContextV21BudgetSmokePlanFactory",
                "create",
            )
        )
        self.assertIsNotNone(
            _method_node(
                coordinator_tree,
                "Gate2FinancialSemanticV6ContextV21BudgetSmokeCoordinator",
                "execute_slot",
            )
        )
        self.assertEqual(
            _call_owners(
                coordinator_module,
                "extract_context_v2_1_once",
            ),
            {
                (
                    "Gate2FinancialSemanticV6ContextV21BudgetSmokeCoordinator."
                    "execute_slot"
                )
            },
        )
        self.assertEqual(
            _call_owners(
                coordinator_module,
                "create_context_v2_1_budget_smoke_candidate",
            ),
            {
                (
                    "Gate2FinancialSemanticV6ContextV21BudgetSmokeCoordinator."
                    "execute_slot"
                )
            },
        )
        self.assertEqual(
            _call_owners(
                coordinator_module,
                "create_context_v2_1_budget_smoke_failure",
            ),
            {
                (
                    "Gate2FinancialSemanticV6ContextV21BudgetSmokeCoordinator."
                    "_failure_outcome"
                )
            },
        )

        for method_name in (
            "create_context_v2_1_budget_smoke_candidate",
            "create_context_v2_1_budget_smoke_failure",
        ):
            self.assertIsNotNone(
                _method_node(
                    evidence_tree,
                    "Gate2FinancialSemanticV6DecisionEvidenceFactory",
                    method_name,
                )
            )
        for function_name in (
            (
                "serialize_financial_semantic_v6_context_v2_1_"
                "budget_smoke_private_evidence"
            ),
            (
                "restore_financial_semantic_v6_context_v2_1_"
                "budget_smoke_private_evidence"
            ),
            (
                "validate_financial_semantic_v6_context_v2_1_"
                "budget_smoke_evidence_bundle"
            ),
            (
                "replay_financial_semantic_v6_context_v2_1_"
                "budget_smoke_decision"
            ),
        ):
            self.assertIsNotNone(_function_node(evidence_tree, function_name))
        for method_name in (
            "create_context_v2_1_budget_smoke_case",
            "create_context_v2_1_budget_smoke_report",
        ):
            self.assertIsNotNone(
                _method_node(
                    report_tree,
                    "Gate2FinancialSemanticV6TransparentSmokeReportFactory",
                    method_name,
                )
            )

        self.assertNotIn(evidence_module, _local_imports("gate2_model_clients"))
        self.assertNotIn(report_module, _local_imports("gate2_model_clients"))
        self.assertNotIn(
            coordinator_module,
            _local_imports("gate2_provider_adapters"),
        )
        self.assertNotIn(
            coordinator_module,
            _local_imports("gate2_model_requests"),
        )

    def test_goal12_google_and_ci_gates_precede_provider_transport(self):
        coordinator_tree = _tree(
            "gate2_financial_semantic_v6_context_v2_1_budget_smoke"
        )
        execute = _method_node(
            coordinator_tree,
            "Gate2FinancialSemanticV6ContextV21BudgetSmokeCoordinator",
            "execute_slot",
        )
        identity_gate = next(
            node
            for node in ast.walk(execute)
            if isinstance(node, ast.If)
            and "slot.immutable_model_id_proven"
            in _attribute_paths(node.test)
        )
        self.assertIn("_preflight_failure", _call_names(identity_gate))
        self.assertTrue(
            any(isinstance(node, ast.Return) for node in identity_gate.body)
        )
        self.assertTrue(
            {
                "consume_slot",
                "extract_context_v2_1_once",
            }.isdisjoint(_call_names(identity_gate))
        )
        consume_lines = _call_lines(execute, "consume_slot")
        transport_lines = _call_lines(execute, "extract_context_v2_1_once")
        self.assertEqual(len(consume_lines), 1)
        self.assertEqual(len(transport_lines), 1)
        self.assertLess(identity_gate.lineno, consume_lines[0])
        self.assertLess(consume_lines[0], transport_lines[0])

        runner_tree = ast.parse(
            GOAL12_LIVE_RUNNER.read_text(encoding="utf-8")
        )
        main = _function_node(runner_tree, "main")
        execute_delegate = _function_node(runner_tree, "_main_unleased")
        lease_lines = _call_lines(main, "_execution_process_lease")
        delegate_lines = _call_lines(main, "_main_unleased")
        self.assertEqual(len(lease_lines), 1)
        self.assertEqual(len(delegate_lines), 2)
        self.assertLess(lease_lines[0], delegate_lines[-1])
        self.assertIn(
            "goal12_execution_process_lease_required",
            _string_constants(execute_delegate),
        )
        clean_head_lines = _call_lines(
            execute_delegate,
            "_clean_repository_head",
        )
        actions_gate_lines = _call_lines(
            execute_delegate,
            "_require_green_actions",
        )
        self.assertEqual(len(clean_head_lines), 1)
        self.assertEqual(len(actions_gate_lines), 1)
        self.assertLess(clean_head_lines[0], actions_gate_lines[0])
        actions_gate = _function_node(runner_tree, "_require_green_actions")
        self.assertTrue(
            {
                "success",
                "goal12_actions_not_green_for_head",
            }.issubset(_string_constants(actions_gate))
        )
        self.assertIn(
            "BROKER_REPORTS_ACTIONS_JOB_NAME",
            {
                node.id
                for node in ast.walk(actions_gate)
                if isinstance(node, ast.Name)
            },
        )
        self.assertIn("broker-reports-ci", _string_constants(runner_tree))
        self.assertIn(
            ".github/workflows/broker-reports-ci.yml",
            _string_constants(runner_tree),
        )

        workflow = BROKER_REPORTS_CI_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("on:\n  pull_request:", workflow)
        self.assertEqual(workflow.count("name: broker-reports-ci"), 1)
        self.assertIn(
            "python scripts/build_context_v2_1_budget_smoke_plan.py --check",
            workflow,
        )

    def test_model_choice_schema_contains_only_minimal_choice_fields(self):
        schema = _choice_schema(("opaque_typed_option",))
        variants = schema["anyOf"]
        observed_fields = {
            field
            for variant in variants
            for field in variant["properties"]
        }

        self.assertEqual(
            observed_fields,
            set(SEMANTIC_CHOICE_OUTPUT_FIELDS),
        )
        self.assertTrue(
            all(variant["additionalProperties"] is False for variant in variants)
        )
        self.assertTrue(
            observed_fields.isdisjoint(
                {
                    "source_ref",
                    "source_value_ref",
                    "role_bindings",
                    "value_bindings",
                    "provenance",
                    "retention",
                }
            )
        )

    def test_v6_local_choice_is_non_active_and_has_no_second_factory(self):
        tree = _tree("gate2_financial_semantic_v6_choice")
        class_names = {
            node.name for node in tree.body if isinstance(node, ast.ClassDef)
        }
        local_schema = _local_choice_schema(("A", "B"))
        context_v2_1_schema = _context_v2_1_choice_schema(
            choice_keys=("choice_1", "choice_2"),
            reason_codes=(
                "no_registry_type",
                "single_registry_type_no_safe_record",
                "ambiguous_registry_type",
            ),
        )
        local_fields = {
            field
            for variant in local_schema["anyOf"]
            for field in variant["properties"]
        }

        self.assertIn(
            "Gate2FinancialSemanticV6ChoiceContractFactory",
            class_names,
        )
        self.assertEqual(
            {
                name
                for name in class_names
                if name.endswith("LocalChoiceFactory")
                or name.endswith("LocalChoiceCandidateFactory")
            },
            set(),
        )
        self.assertEqual(local_fields, set(LOCAL_CHOICE_OUTPUT_FIELDS))
        self.assertNotIn("typed_option_id", str(local_schema))
        self.assertNotIn("typed_option_id", str(context_v2_1_schema))
        self.assertEqual(
            {
                field
                for variant in context_v2_1_schema["anyOf"]
                for field in variant["properties"]
            },
            set(LOCAL_CHOICE_OUTPUT_FIELDS),
        )
        self.assertEqual(
            list(PACKAGE.glob("gate2_financial_semantic_v6*local_choice*.py")),
            [],
        )
        for module_name in (
            "gate2_financial_semantic_v6_evidence",
            "gate2_financial_semantic_v6_qualification_run",
            "gate2_model_requests",
        ):
            source = _source(module_name)
            self.assertNotIn("create_from_local_candidate", source)
            self.assertNotIn(
                "normalize_financial_semantic_v6_local_choice",
                source,
            )

    def test_v6_context_linter_seals_the_existing_request_builder(self):
        linter_module = "gate2_financial_semantic_v6_context_linter"
        tree = _tree(linter_module)
        class_names = {
            node.name for node in tree.body if isinstance(node, ast.ClassDef)
        }
        builder = _method_node(
            _tree("gate2_model_requests"),
            "Gate2OpenWebUIRequestBuilder",
            "_build_financial_semantic_v6_slim_linted",
        )

        self.assertEqual(
            {
                name
                for name in class_names
                if name.endswith("ContextLinterFactory")
            },
            {"Gate2FinancialSemanticV6ContextLinterFactory"},
        )
        self.assertEqual(
            _call_owners(linter_module, "Gate2OpenWebUIRequestBuilder"),
            {"Gate2FinancialSemanticV6ContextLinterFactory.create"},
        )
        self.assertNotIn(
            linter_module,
            _local_imports("gate2_model_requests"),
        )
        self.assertIn(
            "Gate2FinancialSemanticV6ContextLintReceipt",
            {
                node.id
                for node in ast.walk(builder)
                if isinstance(node, ast.Name)
            },
        )
        self.assertIn(
            "gate2_financial_semantic_v6_context_lint_required",
            _string_constants(builder),
        )
        for bundle_path in GENERATED_BUNDLES:
            self.assertNotIn(
                linter_module,
                _bundled_modules(bundle_path),
            )

    def test_generated_bundle_modules_match_maintained_source(self):
        mismatches = []
        for bundle_path in GENERATED_BUNDLES:
            modules = _bundled_modules(bundle_path)
            for module_name, bundled_source in modules.items():
                if module_name == "__init__":
                    continue
                if bundled_source != _source(module_name):
                    mismatches.append(f"{bundle_path.name}:{module_name}")
        self.assertEqual(mismatches, [])

    def test_model_client_uses_one_budget_admission_authority(self):
        factory_callers = {
            module_name
            for path in PACKAGE.glob("*.py")
            for module_name in (path.stem,)
            if _call_owners(
                module_name,
                "Gate2EconomyBudgetSessionFactory",
            )
        }
        extract = _method_node(
            _tree("gate2_model_clients"),
            "Gate2OpenWebUIStructuredModelClient",
            "extract",
        )
        context_v2_1_extract = _method_node(
            _tree("gate2_model_clients"),
            "Gate2OpenWebUIStructuredModelClient",
            "extract_context_v2_1_once",
        )
        execute_prepared = _method_node(
            _tree("gate2_model_clients"),
            "Gate2OpenWebUIStructuredModelClient",
            "_execute_prepared_once",
        )

        self.assertEqual(
            factory_callers,
            {
                "gate2_financial_semantic_v5_qualification",
                "gate2_financial_semantic_v6_qualification",
                (
                    "gate2_financial_semantic_v6_context_v2_1_"
                    "budget_smoke"
                ),
                "gate2_model_clients",
                "gate2_provider_adapters",
            },
        )
        self.assertTrue(
            all(
                "gate2_economy_budget" in _local_imports(module_name)
                for module_name in factory_callers
            )
        )
        self.assertEqual(
            _call_owners(
                "gate2_model_clients",
                "Gate2EconomyBudgetSessionFactory",
            ),
            {"Gate2StructuredModelClientFactory.create"},
        )
        for extraction_method in (extract, context_v2_1_extract):
            admission_lines = _call_lines(
                extraction_method,
                "prepare_call",
            )
            execution_lines = _call_lines(
                extraction_method,
                "_execute_prepared_once",
            )
            self.assertEqual(len(admission_lines), 1)
            self.assertEqual(len(execution_lines), 1)
            self.assertLess(admission_lines[0], execution_lines[0])
        transport_lines = (
            _call_lines(execute_prepared, "invoke_native_once")
            + _call_lines(execute_prepared, "_invoke_completion_once")
            + _call_lines(
                execute_prepared,
                "invoke_context_v2_1_budget_smoke_once",
            )
        )
        self.assertEqual(len(transport_lines), 3)
        direct_transport_callers = {
            path.stem
            for path in PACKAGE.glob("*.py")
            if _call_owners(
                path.stem,
                "invoke_context_v2_1_budget_smoke_once",
            )
        }
        self.assertEqual(
            direct_transport_callers,
            {"gate2_model_clients"},
        )
        self.assertEqual(
            _call_owners(
                "gate2_model_clients",
                "invoke_context_v2_1_budget_smoke_once",
            ),
            {
                (
                    "Gate2OpenWebUIStructuredModelClient."
                    "_execute_prepared_once"
                )
            },
        )

    def test_unclassified_retention_is_code_owned(self):
        tree = _tree("gate2_financial_semantic_v6_expansion")
        expand = _method_node(
            tree,
            "Gate2FinancialSemanticV6DecisionExpansionFactory",
            "_expand",
        )
        unclassified = _function_node(
            tree,
            "_unclassified_canonical_choice",
        )

        self.assertIn(
            "evidence_bundle.retention_set",
            _attribute_paths(expand),
        )
        self.assertNotIn(
            "model_output",
            {arg.arg for arg in unclassified.args.kwonlyargs},
        )
        self.assertEqual(
            set(SEMANTIC_CHOICE_OUTPUT_FIELDS)
            & {"retention", "source_refs", "value_bindings"},
            set(),
        )

    def test_validated_decision_uses_canonical_materialization_totality(self):
        tree = _tree("gate2_financial_semantic_v6_totality")
        materialize = _method_node(
            tree,
            "Gate2FinancialSemanticV6TotalMaterializerFactory",
            "_materialize",
        )

        self.assertIn(
            "gate2_financial_evidence_materialization",
            _local_imports("gate2_financial_semantic_v6_totality"),
        )
        self.assertIn(
            "Gate2FinancialEvidenceMaterializerFactory",
            _call_names(materialize),
        )
        self.assertIn("materialize", _call_names(materialize))
        self.assertIn(
            "financial_semantic_v6_validated_but_unmaterializable",
            _string_constants(materialize),
        )

    def test_artifact_store_and_gate2_runs_are_append_only_by_construction(self):
        store_source = _source("artifact_store")
        runtime_sources = "\n".join(
            _source(module_name)
            for module_name in ("gate2_source_fact_runtime", "gate2_domain_runtime")
        )

        self.assertNotIn("INSERT OR REPLACE", store_source.upper())
        self.assertIn("artifact_immutable", store_source)
        self.assertNotIn("_replace_run_record", runtime_sources)
        self.assertIn("_persist_terminal_run_record", runtime_sources)

    def test_gate3_business_runtime_uses_declared_context_boundary(self):
        gate3_business_modules = {
            path.stem
            for path in PACKAGE.glob("gate3_*.py")
            if path.stem != "gate3_context_manifest"
        }
        violations = []
        for module_name in sorted(gate3_business_modules):
            imports = _local_imports(module_name)
            if module_name == GATE3_FINANCIAL_DOMAIN_SUCCESSOR:
                if "gate2_financial_domain_query" not in imports:
                    violations.append(
                        f"{module_name}:financial_domain_boundary_missing"
                    )
                if "gate3_context_manifest" in imports:
                    violations.append(
                        f"{module_name}:legacy_manifest_boundary_present"
                    )
                forbidden_successor_imports = {
                    "artifact_resolver",
                    "artifact_store",
                    "gate1_public_contracts",
                    "gate2_financial_domain_catalog",
                } | GATE1_PRIVATE_IMPLEMENTATIONS
                for imported in sorted(imports & forbidden_successor_imports):
                    violations.append(
                        f"{module_name}:forbidden_import:{imported}"
                    )
            elif module_name == GATE3_CURRENT_PROJECTION:
                if "canonical_store" not in imports:
                    violations.append(f"{module_name}:canonical_reader_missing")
                forbidden_projection_imports = {
                    "artifact_resolver",
                    "artifact_store",
                    "gate3_context_manifest",
                } | GATE1_PRIVATE_IMPLEMENTATIONS
                for imported in sorted(imports & forbidden_projection_imports):
                    violations.append(
                        f"{module_name}:forbidden_import:{imported}"
                    )
            elif module_name == GATE3_CURRENT_CHUNKING:
                if GATE3_CURRENT_PROJECTION not in imports:
                    violations.append(
                        f"{module_name}:projection_factory_boundary_missing"
                    )
                forbidden_chunking_imports = {
                    "artifact_resolver",
                    "artifact_store",
                    "canonical_store",
                    "gate3_context_manifest",
                    GATE3_CURRENT_DICTIONARY,
                    GATE3_CURRENT_LABELING,
                } | GATE1_PRIVATE_IMPLEMENTATIONS
                for imported in sorted(imports & forbidden_chunking_imports):
                    violations.append(
                        f"{module_name}:forbidden_import:{imported}"
                    )
            elif module_name == GATE3_CURRENT_DICTIONARY:
                forbidden_dictionary_imports = {
                    "artifact_resolver",
                    "artifact_store",
                    "canonical_store",
                    "gate3_context_manifest",
                } | GATE1_PRIVATE_IMPLEMENTATIONS
                for imported in sorted(imports & forbidden_dictionary_imports):
                    violations.append(
                        f"{module_name}:forbidden_import:{imported}"
                    )
            elif module_name == GATE3_CURRENT_DICTIONARY_CLI:
                if imports != {GATE3_CURRENT_DICTIONARY}:
                    violations.append(
                        f"{module_name}:dictionary_factory_boundary_missing"
                    )
            elif module_name == GATE3_CURRENT_ROLE_PACK:
                if GATE3_CURRENT_DICTIONARY not in imports:
                    violations.append(
                        f"{module_name}:dictionary_factory_boundary_missing"
                    )
                forbidden_role_pack_imports = {
                    "artifact_resolver",
                    "artifact_store",
                    "canonical_store",
                    "gate3_context_manifest",
                } | GATE1_PRIVATE_IMPLEMENTATIONS
                for imported in sorted(imports & forbidden_role_pack_imports):
                    violations.append(
                        f"{module_name}:forbidden_import:{imported}"
                    )
            elif module_name == GATE3_CURRENT_LABELING:
                required_labeling_imports = {
                    GATE3_CURRENT_DICTIONARY,
                    GATE3_CURRENT_PROJECTION,
                }
                if not required_labeling_imports <= imports:
                    violations.append(
                        f"{module_name}:labeling_factory_boundary_missing"
                    )
                forbidden_labeling_imports = {
                    "artifact_resolver",
                    "artifact_store",
                    "canonical_store",
                    "gate3_context_manifest",
                } | GATE1_PRIVATE_IMPLEMENTATIONS
                for imported in sorted(imports & forbidden_labeling_imports):
                    violations.append(
                        f"{module_name}:forbidden_import:{imported}"
                    )
            elif module_name == GATE3_CURRENT_ROLE_LABELING:
                required_role_labeling_imports = {
                    "canonical_store",
                    GATE3_CURRENT_LABELING,
                    GATE3_CURRENT_ROLE_PACK,
                }
                if not required_role_labeling_imports <= imports:
                    violations.append(
                        f"{module_name}:role_labeling_factory_boundary_missing"
                    )
                forbidden_role_labeling_imports = {
                    "artifact_resolver",
                    "artifact_store",
                    "gate3_context_manifest",
                } | GATE1_PRIVATE_IMPLEMENTATIONS
                for imported in sorted(
                    imports & forbidden_role_labeling_imports
                ):
                    violations.append(
                        f"{module_name}:forbidden_import:{imported}"
                    )
            elif module_name == GATE3_CURRENT_CHUNK_BATCH:
                required_batch_imports = {
                    GATE3_CURRENT_CHUNKING,
                    GATE3_CURRENT_LABELING,
                    GATE3_CURRENT_ROLE_LABELING,
                }
                if not required_batch_imports <= imports:
                    violations.append(
                        f"{module_name}:batch_factory_boundary_missing"
                    )
                forbidden_batch_imports = {
                    "artifact_resolver",
                    "artifact_store",
                    "canonical_store",
                    "gate3_context_manifest",
                    GATE3_CURRENT_DICTIONARY,
                    GATE3_CURRENT_PROJECTION,
                } | GATE1_PRIVATE_IMPLEMENTATIONS
                for imported in sorted(imports & forbidden_batch_imports):
                    violations.append(
                        f"{module_name}:forbidden_import:{imported}"
                    )
            elif module_name == GATE3_CURRENT_ANNOTATIONS_PERSISTENCE:
                required_persistence_imports = {
                    "artifact_resolver",
                    GATE3_CURRENT_CHUNKING,
                    GATE3_CURRENT_DICTIONARY,
                    GATE3_CURRENT_LABELING,
                    GATE3_CURRENT_ROLE_PACK,
                    GATE3_CURRENT_ROLE_LABELING,
                    GATE3_CURRENT_CHUNK_BATCH,
                }
                if not required_persistence_imports <= imports:
                    violations.append(
                        f"{module_name}:persistence_factory_boundary_missing"
                    )
                forbidden_persistence_imports = {
                    "artifact_store",
                    "canonical_store",
                    "gate3_context_manifest",
                } | GATE1_PRIVATE_IMPLEMENTATIONS
                for imported in sorted(
                    imports & forbidden_persistence_imports
                ):
                    violations.append(
                        f"{module_name}:forbidden_import:{imported}"
                    )
            elif module_name == GATE3_CURRENT_CASE_READINESS:
                required_readiness_imports = {
                    "artifact_resolver",
                    GATE3_CURRENT_ANNOTATIONS_PERSISTENCE,
                }
                if not required_readiness_imports <= imports:
                    violations.append(
                        f"{module_name}:readiness_factory_boundary_missing"
                    )
                forbidden_readiness_imports = {
                    "artifact_store",
                    "canonical_store",
                    "gate3_context_manifest",
                    GATE3_CURRENT_CHUNKING,
                    GATE3_CURRENT_DICTIONARY,
                    GATE3_CURRENT_LABELING,
                    GATE3_CURRENT_ROLE_PACK,
                    GATE3_CURRENT_ROLE_LABELING,
                    GATE3_CURRENT_CHUNK_BATCH,
                } | GATE1_PRIVATE_IMPLEMENTATIONS
                for imported in sorted(imports & forbidden_readiness_imports):
                    violations.append(
                        f"{module_name}:forbidden_import:{imported}"
                    )
            elif module_name == GATE3_CURRENT_NDFL_WORKFLOW:
                required_workflow_imports = {
                    "canonical_store",
                    GATE3_CURRENT_CHUNK_BATCH,
                    GATE3_CURRENT_ANNOTATIONS_PERSISTENCE,
                }
                if not required_workflow_imports <= imports:
                    violations.append(
                        f"{module_name}:workflow_factory_boundary_missing"
                    )
                forbidden_workflow_imports = {
                    "artifact_resolver",
                    "artifact_store",
                    "gate3_context_manifest",
                    GATE3_CURRENT_PROJECTION,
                    GATE3_CURRENT_CHUNKING,
                    GATE3_CURRENT_DICTIONARY,
                    GATE3_CURRENT_LABELING,
                } | GATE1_PRIVATE_IMPLEMENTATIONS
                for imported in sorted(imports & forbidden_workflow_imports):
                    violations.append(
                        f"{module_name}:forbidden_import:{imported}"
                    )
            elif module_name == GATE3_CURRENT_METADATA_SOURCE_FACTS:
                required_metadata_imports = {"artifact_resolver", "canonical_store"}
                if not required_metadata_imports <= imports:
                    violations.append(
                        f"{module_name}:metadata_source_boundary_missing"
                    )
                for imported in sorted(
                    item
                    for item in imports
                    if item.startswith("gate4_")
                    or item.startswith("gate5_")
                    or item == "gate3_context_manifest"
                ):
                    violations.append(
                        f"{module_name}:forbidden_import:{imported}"
                    )
            elif module_name == GATE3_LLM_METADATA_ADAPTER:
                required_adapter_imports = {
                    "artifact_resolver",
                    "canonical_store",
                    GATE3_CURRENT_METADATA_SOURCE_FACTS,
                }
                if not required_adapter_imports <= imports:
                    violations.append(
                        f"{module_name}:llm_metadata_adapter_boundary_missing"
                    )
                for imported in sorted(
                    item
                    for item in imports
                    if item.startswith("gate4_")
                    or item.startswith("gate5_")
                    or item == "gate3_context_manifest"
                ):
                    violations.append(
                        f"{module_name}:forbidden_import:{imported}"
                    )
            elif module_name == GATE3_CURRENT_EVIDENCE_DEMAND_PORT:
                required_port_imports = {
                    GATE3_CURRENT_DICTIONARY,
                    GATE3_CURRENT_ROLE_PACK,
                }
                if not required_port_imports <= imports:
                    violations.append(
                        f"{module_name}:published_contract_boundary_missing"
                    )
                for imported in sorted(
                    item
                    for item in imports
                    if item.startswith("gate4_") or item.startswith("gate5_")
                ):
                    violations.append(
                        f"{module_name}:forbidden_import:{imported}"
                    )
            elif "gate3_context_manifest" not in imports:
                violations.append(f"{module_name}:manifest_boundary_missing")
            if imports & GATE1_PRIVATE_IMPLEMENTATIONS:
                violations.append(f"{module_name}:gate1_private_import")
        self.assertEqual(violations, [])


def _source(module_name: str) -> str:
    return (PACKAGE / f"{module_name}.py").read_text(encoding="utf-8")


def _tree(module_name: str) -> ast.Module:
    return ast.parse(_source(module_name))


def _local_imports(module_name: str) -> set[str]:
    tree = _tree(module_name)
    imports: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or node.level != 1:
            continue
        if node.module:
            imports.add(node.module.split(".", 1)[0])
        else:
            imports.update(alias.name.split(".", 1)[0] for alias in node.names)
    return imports


def _import_roots(node: ast.AST) -> set[str]:
    if isinstance(node, ast.Import):
        return {alias.name.split(".", 1)[0] for alias in node.names}
    if isinstance(node, ast.ImportFrom) and node.module:
        return {node.module.split(".", 1)[0]}
    return set()


def _call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _call_names(node: ast.AST) -> set[str]:
    return {
        name
        for item in ast.walk(node)
        if isinstance(item, ast.Call)
        for name in (_call_name(item.func),)
        if name is not None
    }


def _call_lines(node: ast.AST, target: str) -> list[int]:
    return sorted(
        item.lineno
        for item in ast.walk(node)
        if isinstance(item, ast.Call)
        and _call_name(item.func) == target
    )


def _call_owners(module_name: str, target: str) -> set[str]:
    owners = set()
    for node in _tree(module_name).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if target in _call_names(node):
                owners.add(node.name)
        elif isinstance(node, ast.ClassDef):
            for method in node.body:
                if not isinstance(
                    method,
                    (ast.FunctionDef, ast.AsyncFunctionDef),
                ):
                    continue
                if target in _call_names(method):
                    owners.add(f"{node.name}.{method.name}")
    return owners


def _function_node(tree: ast.Module, name: str) -> ast.FunctionDef:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"function_missing:{name}")


def _method_node(
    tree: ast.Module,
    class_name: str,
    method_name: str,
) -> ast.FunctionDef | ast.AsyncFunctionDef:
    for node in tree.body:
        if not isinstance(node, ast.ClassDef) or node.name != class_name:
            continue
        for method in node.body:
            if isinstance(
                method,
                (ast.FunctionDef, ast.AsyncFunctionDef),
            ) and method.name == method_name:
                return method
    raise AssertionError(f"method_missing:{class_name}.{method_name}")


def _string_constants(node: ast.AST) -> set[str]:
    return {
        item.value
        for item in ast.walk(node)
        if isinstance(item, ast.Constant)
        and isinstance(item.value, str)
    }


def _attribute_path(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if not isinstance(node, ast.Attribute):
        return None
    parent = _attribute_path(node.value)
    return f"{parent}.{node.attr}" if parent else node.attr


def _attribute_paths(node: ast.AST) -> set[str]:
    return {
        path
        for item in ast.walk(node)
        if isinstance(item, ast.Attribute)
        for path in (_attribute_path(item),)
        if path is not None
    }


def _bundled_modules(path: Path) -> dict[str, str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(
            isinstance(target, ast.Name)
            and target.id == "_BUNDLED_MODULES"
            for target in node.targets
        ):
            continue
        value = ast.literal_eval(node.value)
        if not isinstance(value, dict) or any(
            not isinstance(key, str) or not isinstance(source, str)
            for key, source in value.items()
        ):
            raise AssertionError(f"bundled_modules_invalid:{path.name}")
        return value
    raise AssertionError(f"bundled_modules_missing:{path.name}")


if __name__ == "__main__":
    unittest.main()
