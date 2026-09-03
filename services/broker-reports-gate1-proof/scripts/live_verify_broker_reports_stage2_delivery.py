#!/usr/bin/env python3
"""Read-only repository/live parity proof for Broker Reports Stage 2 delivery."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import requests


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[2]
SERVICE_ROOT = ROOT / "services" / "broker-reports-gate1-proof"

sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(SERVICE_ROOT))

import live_update_function_and_passport_prompt as gate1_update  # noqa: E402
import live_update_gate2_domain_function_and_prompts as domain_update  # noqa: E402
import live_update_gate2_function_and_prompt as source_update  # noqa: E402
from broker_reports_gate1 import GATE2_PROVIDER_PROFILES  # noqa: E402
from broker_reports_atomic_stage_release_contracts import (  # noqa: E402
    GATE1_RETIRED_VALVE_KEYS,
    RETIRED_FUNCTION_IDS,
)
from live_no_rag_source_intake_smoke import (  # noqa: E402
    _base_url,
    _default_ssh_target,
    _read_env,
    _signin,
    _url,
)


@dataclass(frozen=True)
class FunctionContract:
    function_id: str
    bundle_path: Path
    required_markers: tuple[str, ...]


FUNCTION_CONTRACTS = (
    FunctionContract(
        function_id=gate1_update.FUNCTION_ID,
        bundle_path=gate1_update.BUNDLE_PATH,
        required_markers=(
            "NormalizedTableProjectionFactory",
            "Gate2StructuredModelClientFactory",
            "Gate2ProviderAdapterFactory",
            "gate2_provider_execution_metadata_v1",
            "PdfDocumentExtractorFactory",
            "PDF_DOCUMENT_AI_NOT_CONFIGURED",
            "Gate2TablePackageFactory",
            "Gate5DeclarationPreparationRuntimeFactory",
            "broker_reports_current_pipeline_result_v1",
        ),
    ),
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", default=str(ROOT / ".env"))
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--ssh-target", default=None)
    parser.add_argument("--scope", choices=("all", "gate1"), default="all")
    args = parser.parse_args()

    env = _read_env(Path(args.env_file))
    base_url = args.base_url.rstrip("/") if args.base_url else _base_url(env)
    ssh_target = (
        args.ssh_target
        or env.get("OPENWEBUI_SSH_TARGET")
        or _default_ssh_target(env)
    )
    session = requests.Session()
    session.headers.update({"Accept": "application/json"})
    token = _signin(session, base_url, env)
    session.headers.update({"Authorization": f"Bearer {token}"})

    expected_prompts = expected_prompt_contracts()
    if args.scope == "gate1":
        expected_prompts = {
            prompt_id: expected_prompts[prompt_id]
            for prompt_id in (
                gate1_update.PROMPT_ID,
                gate1_update.CLARIFICATION_PROMPT_ID,
            )
        }
    live_prompts = _read_live_prompt_state(
        ssh_target=ssh_target,
        prompt_ids=sorted(expected_prompts),
    )
    prompt_checks = [
        evaluate_prompt_contract(expected_prompts[prompt_id], live_prompts.get(prompt_id))
        for prompt_id in sorted(expected_prompts)
    ]
    function_contracts = (
        FUNCTION_CONTRACTS[:1]
        if args.scope == "gate1"
        else FUNCTION_CONTRACTS
    )
    function_checks = [
        evaluate_function_contract(
            contract,
            _get_live_function(session, base_url, contract.function_id),
        )
        for contract in function_contracts
    ]
    retired_function_checks = [
        {
            "function_id": function_id,
            "inactive": (
                (value := _get_live_function(session, base_url, function_id)) is None
                or value.get("is_active") in (False, 0, None)
            ),
        }
        for function_id in RETIRED_FUNCTION_IDS
    ]
    gate1_valves = _get_live_function_valves(
        session,
        base_url,
        gate1_update.FUNCTION_ID,
    )
    gate1_operational_state = evaluate_gate1_operational_state(valves=gate1_valves)
    repository_boundary = repository_factory_boundary_checks()
    provider_profile_ids = sorted(
        profile.profile_id for profile in GATE2_PROVIDER_PROFILES
    )
    provider_profile_statuses = {
        profile.profile_id: profile.gate2_status
        for profile in GATE2_PROVIDER_PROFILES
    }
    provider_approved_model_ids = {
        profile.profile_id: list(profile.approved_model_ids)
        for profile in GATE2_PROVIDER_PROFILES
        if profile.approved_model_ids
    }
    provider_model_id_prefixes = {
        profile.profile_id: list(profile.model_id_prefixes)
        for profile in GATE2_PROVIDER_PROFILES
    }
    checks = {
        "all_function_bundles_match": all(item["passed"] for item in function_checks),
        "retired_functions_inactive": all(
            item["inactive"] for item in retired_function_checks
        ),
        "all_managed_prompts_match": all(item["passed"] for item in prompt_checks),
        "provider_profiles_complete": provider_profile_ids
        == [
            "alibaba_qwen",
            "anthropic_claude",
            "deepseek",
            "google_gemini",
            "openai_gpt",
            "zai_glm",
        ],
        "provider_profile_statuses_match": provider_profile_statuses
        == {
            "alibaba_qwen": "unsupported",
            "anthropic_claude": "approved",
            "deepseek": "unsupported",
            "google_gemini": "approved",
            "openai_gpt": "approved",
            "zai_glm": "unsupported",
        },
        "provider_approved_models_match": provider_approved_model_ids
        == {
            "openai_gpt": ["gpt-5.6-luna", "gpt-5.6-sol"],
            "google_gemini": [
                "models/gemini-3.1-flash-lite",
                "models/gemini-3.5-flash",
            ],
            "anthropic_claude": ["claude-haiku-4-5-20251001"],
        },
        "provider_model_namespaces_match": provider_model_id_prefixes
        == {
            "alibaba_qwen": ["qwen-"],
            "anthropic_claude": ["claude-"],
            "deepseek": ["deepseek-"],
            "google_gemini": ["models/gemini-"],
            "openai_gpt": ["gpt-"],
            "zai_glm": ["glm-"],
        },
        "repository_factory_boundary_passed": all(repository_boundary.values()),
        "gate1_retired_table_valves_absent": gate1_operational_state[
            "retired_table_valves_absent"
        ],
        "gate1_pdf_document_ai_unconfigured": gate1_operational_state[
            "pdf_document_ai_unconfigured"
        ],
    }
    output = {
        "status": "passed" if all(checks.values()) else "failed",
        "schema_version": "broker_reports_stage2_live_delivery_parity_v0",
        "scope": args.scope,
        "checks": checks,
        "functions": function_checks,
        "retired_functions": retired_function_checks,
        "managed_prompts": prompt_checks,
        "managed_prompts_total": len(prompt_checks),
        "provider_profiles": provider_profile_ids,
        "provider_profile_statuses": provider_profile_statuses,
        "provider_approved_model_ids": provider_approved_model_ids,
        "provider_model_id_prefixes": provider_model_id_prefixes,
        "repository_factory_boundary": repository_boundary,
        "gate1_operational_state": gate1_operational_state,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if output["status"] == "passed" else 1


def expected_prompt_contracts() -> dict[str, dict[str, Any]]:
    passport_content = gate1_update._prompt_content_from_contract(
        gate1_update.PASSPORT_CONTRACT_PATH,
        "You are the Broker Reports Gate 1 document metadata passport classifier.",
    )
    clarification_content = gate1_update._prompt_content_from_contract(
        gate1_update.CLARIFICATION_CONTRACT_PATH,
        "You are the Broker Reports Gate 1 metadata clarification question writer.",
    )
    source_content = source_update._prompt_content_from_contract(
        source_update.PROMPT_CONTRACT_PATH,
        "You are the Broker Reports Gate 2 bounded semantic source-fact selector.",
    )
    rows: list[dict[str, Any]] = [
        {
            "prompt_id": gate1_update.PROMPT_ID,
            "command": gate1_update.PROMPT_COMMAND,
            "version": gate1_update.PROMPT_VERSION,
            "content": passport_content,
            "meta": {
                "template_id": "broker_reports.document_metadata_passport.v0",
                "output_schema_version": "document_metadata_passport_v0",
            },
        },
        {
            "prompt_id": gate1_update.CLARIFICATION_PROMPT_ID,
            "command": gate1_update.CLARIFICATION_PROMPT_COMMAND,
            "version": gate1_update.CLARIFICATION_PROMPT_VERSION,
            "content": clarification_content,
            "meta": {
                "template_id": "broker_reports.gate1_clarification_request.v0",
                "output_schema_version": "gate1_clarification_request_v0",
            },
        },
        {
            "prompt_id": source_update.PROMPT_ID,
            "command": source_update.PROMPT_COMMAND,
            "version": source_update.PROMPT_VERSION,
            "content": source_content,
            "meta": {
                "template_id": "broker_reports.source_fact_extraction.v0",
                "output_schema_version": "broker_reports_source_facts_v0",
                "provider_output_schema_version": (
                    source_update.SOURCE_FACT_SELECTION_SCHEMA_VERSION
                ),
                "structured_output_required": True,
            },
        },
    ]
    template = domain_update._domain_prompt_template(domain_update.PROMPT_CONTRACT_PATH)
    for item in domain_update._render_prompt_rows(template, domain_update.PROMPT_VERSION):
        rows.append(
            {
                "prompt_id": item["prompt_id"],
                "command": item["prompt_command"],
                "version": item["prompt_version"],
                "content": item["prompt_content"],
                "meta": {
                    "template_id": item["meta"]["template_id"],
                    "output_schema_version": item["meta"]["output_schema_version"],
                    "structured_output_required": True,
                    "extractor_domain": item["meta"]["extractor_domain"],
                    "knowledge_rag_allowed": False,
                    "vectorization_allowed": False,
                },
            }
        )
    result: dict[str, dict[str, Any]] = {}
    for item in rows:
        content = str(item["content"])
        result[str(item["prompt_id"])] = {
            **item,
            "content_sha256": content_sha256(content),
        }
    return result


def content_sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def evaluate_function_contract(
    contract: FunctionContract,
    live_function: dict[str, Any] | None,
) -> dict[str, Any]:
    local_content = contract.bundle_path.read_text(encoding="utf-8")
    live_content = str((live_function or {}).get("content") or "")
    checks = {
        "present": live_function is not None,
        "active": _is_active_function((live_function or {}).get("is_active")),
        "bundle_sha256_match": bool(live_content)
        and content_sha256(live_content) == content_sha256(local_content),
        "required_modules_present": all(
            marker in live_content for marker in contract.required_markers
        ),
    }
    return {
        "function_id": contract.function_id,
        "passed": all(checks.values()),
        "checks": checks,
        "repository_bundle_sha256": content_sha256(local_content),
        "live_bundle_sha256": content_sha256(live_content) if live_content else None,
        "required_markers": list(contract.required_markers),
    }


def _is_active_function(value: Any) -> bool:
    return value is True or (
        isinstance(value, int)
        and not isinstance(value, bool)
        and value == 1
    )


def evaluate_gate1_operational_state(
    *,
    valves: dict[str, Any],
) -> dict[str, Any]:
    retired_absent = all(key not in valves for key in GATE1_RETIRED_VALVE_KEYS)
    return {
        "retired_table_valves_absent": retired_absent,
        "pdf_document_ai_unconfigured": retired_absent,
    }


def evaluate_prompt_contract(
    expected: dict[str, Any],
    live_prompt: dict[str, Any] | None,
) -> dict[str, Any]:
    live_meta = (live_prompt or {}).get("meta")
    live_meta = live_meta if isinstance(live_meta, dict) else {}
    expected_meta = expected.get("meta") if isinstance(expected.get("meta"), dict) else {}
    checks = {
        "present": live_prompt is not None,
        "active": (live_prompt or {}).get("is_active") == 1,
        "command_match": (live_prompt or {}).get("command") == expected["command"],
        "version_match": (live_prompt or {}).get("version") == expected["version"],
        "content_sha256_match": (live_prompt or {}).get("content_sha256")
        == expected["content_sha256"],
        "metadata_match": all(live_meta.get(key) == value for key, value in expected_meta.items()),
    }
    return {
        "prompt_ref": expected["prompt_id"],
        "passed": all(checks.values()),
        "checks": checks,
        "repository_content_sha256": expected["content_sha256"],
        "live_content_sha256": (live_prompt or {}).get("content_sha256"),
        "content_length": (live_prompt or {}).get("content_length"),
    }


@dataclass(frozen=True)
class _PythonBoundaryFacts:
    classes: frozenset[str]
    imports: frozenset[str]
    calls: frozenset[str]
    strings: frozenset[str]


_PROVIDER_BOUNDARY_SOURCE_PATHS = {
    "provider_adapters": (
        SERVICE_ROOT / "broker_reports_gate1/gate2_provider_adapters.py"
    ),
    "model_clients": (
        SERVICE_ROOT / "broker_reports_gate1/gate2_model_clients.py"
    ),
    "source_pipe": (
        SERVICE_ROOT
        / "openwebui_actions/broker_reports_gate2_source_fact_pipe.py"
    ),
    "domain_pipe": (
        SERVICE_ROOT
        / "openwebui_actions/broker_reports_gate2_domain_source_fact_pipe.py"
    ),
    "source_runtime": (
        SERVICE_ROOT / "broker_reports_gate1/gate2_source_fact_runtime.py"
    ),
    "domain_runtime": (
        SERVICE_ROOT / "broker_reports_gate1/gate2_domain_runtime.py"
    ),
    "financial_runtime": (
        SERVICE_ROOT
        / "broker_reports_gate1/"
        "gate2_financial_evidence_production_runtime.py"
    ),
}
_PROVIDER_BOUNDARY_BUNDLE_PATHS = {
    "gate1_bundle": (
        SERVICE_ROOT
        / "openwebui_actions/broker_reports_gate1_pipe_bundled.py"
    ),
    "gate2_source_bundle": (
        SERVICE_ROOT
        / "openwebui_actions/broker_reports_gate2_source_fact_pipe_bundled.py"
    ),
    "gate2_domain_bundle": (
        SERVICE_ROOT
        / "openwebui_actions/"
        "broker_reports_gate2_domain_source_fact_pipe_bundled.py"
    ),
}
_PRODUCT_PROVIDER_CONSUMERS = (
    "source_pipe",
    "domain_pipe",
    "source_runtime",
    "domain_runtime",
    "financial_runtime",
)
_DIRECT_PROVIDER_IMPORT_ROOTS = frozenset(
    {
        "aiohttp",
        "httpx",
        "requests",
        "urllib.request",
    }
)
_DIRECT_PROVIDER_CALLS = frozenset(
    {
        "build_opener",
        "requests.post",
        "requests.request",
        "httpx.post",
        "httpx.request",
        "urlopen",
        "urllib.request.urlopen",
    }
)
_PROVIDER_HOSTS = (
    "api.openai.com",
    "api.anthropic.com",
    "generativelanguage.googleapis.com",
)
_OPENWEBUI_SECRET_CONFIG_KEYS = frozenset(
    {
        "OPENAI_API_BASE_URLS",
        "OPENAI_API_CONFIGS",
        "OPENAI_API_KEYS",
    }
)
_CONCRETE_PROVIDER_ADAPTERS = frozenset(
    {
        "Gate2AnthropicNativeMessagesAdapter",
        "Gate2GeminiResponseFormatAdapter",
        "Gate2OpenAIResponseFormatAdapter",
    }
)
_QUALIFICATION_MODULE_MARKERS = (
    "context_v2_1_budget_smoke",
    "financial_semantic_v6_evidence",
    "financial_semantic_v6_qualification",
    "financial_semantic_v6_local_proof",
)


def _dotted_symbol(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _dotted_symbol(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    if isinstance(node, ast.Call):
        return _dotted_symbol(node.func)
    return ""


def _python_boundary_facts(source: str) -> _PythonBoundaryFacts:
    tree = ast.parse(source)
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            imports.add(module)
            imports.update(
                f"{module}.{alias.name}" if module else alias.name
                for alias in node.names
            )
    return _PythonBoundaryFacts(
        classes=frozenset(
            node.name
            for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef)
        ),
        imports=frozenset(imports),
        calls=frozenset(
            _dotted_symbol(node.func)
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
        ),
        strings=frozenset(
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant)
            and isinstance(node.value, str)
        ),
    )


def _string_class_scopes(
    source: str,
    selected: frozenset[str],
) -> tuple[tuple[str, tuple[str, ...]], ...]:
    observed: list[tuple[str, tuple[str, ...]]] = []

    class Visitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self.class_stack: list[str] = []

        def visit_ClassDef(self, node: ast.ClassDef) -> None:  # noqa: N802
            self.class_stack.append(node.name)
            self.generic_visit(node)
            self.class_stack.pop()

        def visit_Constant(self, node: ast.Constant) -> None:  # noqa: N802
            if isinstance(node.value, str) and node.value in selected:
                observed.append((node.value, tuple(self.class_stack)))

    Visitor().visit(ast.parse(source))
    return tuple(observed)


def _bundled_module_sources(source: str) -> dict[str, str]:
    tree = ast.parse(source)
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
        if not isinstance(value, dict) or not all(
            isinstance(key, str) and isinstance(item, str)
            for key, item in value.items()
        ):
            return {}
        return value
    return {}


def _provider_adapter_boundary_invariants(
    source_overrides: Mapping[str, str] | None = None,
    bundle_overrides: Mapping[str, str] | None = None,
) -> dict[str, bool]:
    sources = {
        key: path.read_text(encoding="utf-8")
        for key, path in _PROVIDER_BOUNDARY_SOURCE_PATHS.items()
    }
    sources.update(source_overrides or {})
    bundles = {
        key: path.read_text(encoding="utf-8")
        for key, path in _PROVIDER_BOUNDARY_BUNDLE_PATHS.items()
    }
    bundles.update(bundle_overrides or {})
    facts = {
        key: _python_boundary_facts(source)
        for key, source in sources.items()
    }
    product_facts = tuple(
        facts[key] for key in _PRODUCT_PROVIDER_CONSUMERS
    )

    resolver_definitions = sum(
        "Gate2OpenWebUIProviderConnectionResolver" in item.classes
        for item in facts.values()
    )
    product_imports = set().union(
        *(item.imports for item in product_facts)
    )
    product_calls = set().union(*(item.calls for item in product_facts))
    product_strings = set().union(*(item.strings for item in product_facts))
    direct_import = any(
        imported == root or imported.startswith(f"{root}.")
        for imported in product_imports
        for root in _DIRECT_PROVIDER_IMPORT_ROOTS
    )
    direct_call = any(
        call in _DIRECT_PROVIDER_CALLS
        or any(call.endswith(f".{name}") for name in _DIRECT_PROVIDER_CALLS)
        for call in product_calls
    )
    secret_scopes = _string_class_scopes(
        sources["provider_adapters"],
        _OPENWEBUI_SECRET_CONFIG_KEYS,
    )
    product_has_secret_config = bool(
        product_strings & _OPENWEBUI_SECRET_CONFIG_KEYS
    )
    product_has_qualification_import = any(
        marker in imported
        for imported in product_imports
        for marker in _QUALIFICATION_MODULE_MARKERS
    )
    product_has_concrete_adapter = bool(
        (
            {
                imported.rsplit(".", 1)[-1]
                for imported in product_imports
            }
            | {
                call.rsplit(".", 1)[-1]
                for call in product_calls
            }
        )
        & (
            _CONCRETE_PROVIDER_ADAPTERS
            | {
                "Gate2ProviderAdapterFactory",
                "Gate2OpenWebUIProviderConnectionResolver",
            }
        )
    )
    embedded_modules = {
        key: _bundled_module_sources(source)
        for key, source in bundles.items()
    }
    bundles_exact = all(
        modules.get("gate2_provider_adapters")
        == sources["provider_adapters"]
        and modules.get("gate2_model_clients")
        == sources["model_clients"]
        for modules in embedded_modules.values()
    )
    bundles_exclude_qualification = all(
        not any(
            marker in module_name
            for module_name in modules
            for marker in _QUALIFICATION_MODULE_MARKERS
        )
        for modules in embedded_modules.values()
    )

    return {
        "provider_connection_resolver_is_single_authority": (
            resolver_definitions == 1
            and "Gate2OpenWebUIProviderConnectionResolver"
            in facts["model_clients"].calls
        ),
        "model_client_owns_provider_adapter_construction": (
            "Gate2ProviderAdapterFactory" in facts["model_clients"].calls
            and "Gate2ProviderAdapterFactory.create"
            in facts["model_clients"].calls
            and not product_has_concrete_adapter
        ),
        "product_domains_have_no_direct_provider_transport": (
            not direct_import
            and not direct_call
            and not any(
                host in literal
                for literal in product_strings
                for host in _PROVIDER_HOSTS
            )
        ),
        "provider_secret_resolution_is_resolver_scoped": (
            bool(secret_scopes)
            and all(
                "Gate2OpenWebUIProviderConnectionResolver" in scopes
                for _key, scopes in secret_scopes
            )
            and not product_has_secret_config
        ),
        "qualification_modules_are_not_product_consumers": (
            not product_has_qualification_import
        ),
        "historical_adapters_are_not_product_reachable": (
            not product_has_concrete_adapter
        ),
        "generated_bundles_preserve_provider_closed_world": (
            bundles_exact and bundles_exclude_qualification
        ),
    }


def repository_factory_boundary_checks() -> dict[str, bool]:
    gate1_pipe = (
        SERVICE_ROOT / "openwebui_actions/broker_reports_gate1_pipe.py"
    ).read_text(encoding="utf-8")
    normalizer = (
        SERVICE_ROOT / "broker_reports_gate1/normalizer.py"
    ).read_text(encoding="utf-8")
    pdf_document_ai = (
        SERVICE_ROOT / "broker_reports_gate1/pdf_document_ai.py"
    ).read_text(encoding="utf-8")
    source_pipe = (
        SERVICE_ROOT / "openwebui_actions/broker_reports_gate2_source_fact_pipe.py"
    ).read_text(encoding="utf-8")
    domain_pipe = (
        SERVICE_ROOT / "openwebui_actions/broker_reports_gate2_domain_source_fact_pipe.py"
    ).read_text(encoding="utf-8")
    model_clients = (
        SERVICE_ROOT / "broker_reports_gate1/gate2_model_clients.py"
    ).read_text(encoding="utf-8")
    provider_adapters = (
        SERVICE_ROOT / "broker_reports_gate1/gate2_provider_adapters.py"
    ).read_text(encoding="utf-8")
    model_contracts = (
        SERVICE_ROOT / "broker_reports_gate1/gate2_model_contracts.py"
    ).read_text(encoding="utf-8")
    source_runtime = (
        SERVICE_ROOT / "broker_reports_gate1/gate2_source_fact_runtime.py"
    ).read_text(encoding="utf-8")
    domain_runtime = (
        SERVICE_ROOT / "broker_reports_gate1/gate2_domain_runtime.py"
    ).read_text(encoding="utf-8")
    financial_runtime = (
        SERVICE_ROOT
        / "broker_reports_gate1/"
        "gate2_financial_evidence_production_runtime.py"
    ).read_text(encoding="utf-8")
    financial_contracts = (
        SERVICE_ROOT
        / "broker_reports_gate1/"
        "gate2_financial_evidence_materialization_contracts.py"
    ).read_text(encoding="utf-8")
    smoke_paths = (
        SERVICE_ROOT / "scripts/live_gate2_domain_synthetic_smoke.py",
        SERVICE_ROOT / "scripts/live_case_group_gate2_table_typed_vertical_proof.py",
    )
    smoke_sources = [path.read_text(encoding="utf-8") for path in smoke_paths]
    provider_boundary = _provider_adapter_boundary_invariants()
    return {
        "production_python_has_no_paddle_or_local_ocr_import": (
            _production_python_has_no_heavy_local_ocr_import()
        ),
        "gate1_uses_pdf_document_extractor_factory": (
            "PdfDocumentExtractorFactory.create()" in normalizer
            and "PdfDocumentExtractorFactory" not in gate1_pipe
        ),
        "gate1_pipe_does_not_construct_detector_adapter": (
            "GeminiGridExperimentAdapter(" not in gate1_pipe
        ),
        "pdf_document_ai_declares_factory_boundary": (
            "FACTORY_REQUIRED" in pdf_document_ai
            and "FORBIDDEN" in pdf_document_ai
            and "UnconfiguredPdfDocumentExtractor" in pdf_document_ai
        ),
        "source_pipe_uses_factory": "Gate2StructuredModelClientFactory(" in source_pipe,
        "domain_pipe_uses_factory": "Gate2StructuredModelClientFactory(" in domain_pipe,
        "pipes_do_not_import_openwebui_completion": all(
            marker not in source_pipe and marker not in domain_pipe
            for marker in ("generate_chat_completion", "generate_chat_completions")
        ),
        "model_client_forbids_bypass": "control checks and smoke scripts must not call" in model_clients,
        "model_client_uses_provider_adapter_factory": (
            "Gate2ProviderAdapterFactory(" in model_clients
        ),
        "provider_adapter_factory_is_explicit": (
            "Gate2ProviderAdapterFactory.create is the only production"
            in provider_adapters
        ),
        "provider_adapters_stay_inside_openwebui": all(
            provider_boundary.values()
        ),
        **provider_boundary,
        "native_anthropic_transport_adapter_owned": (
            "Gate2OpenWebUIProviderConnectionResolver" in provider_adapters
            and 'f"{connection.base_url}/messages"' in provider_adapters
            and "OPENAI_API_KEYS" in provider_adapters
            and "api.anthropic.com" not in model_clients
            and "api.anthropic.com" not in source_pipe
            and "api.anthropic.com" not in domain_pipe
            and "anthropic_api_key" not in source_pipe
            and "anthropic_api_key" not in domain_pipe
        ),
        "provider_execution_contract_present": (
            "gate2_provider_execution_metadata_v1" in model_contracts
        ),
        "source_runtime_persists_provider_execution": (
            "provider_execution_summary" in source_runtime
        ),
        "domain_runtime_persists_provider_execution": (
            "provider_execution_summary" in domain_runtime
        ),
        "financial_runtime_uses_factory": (
            "Gate2FinancialEvidenceProductionRuntimeFactory.create"
            in financial_runtime
            and "Gate2FinancialEvidenceProductionRuntimeFactory("
            in domain_pipe
        ),
        "financial_runtime_uses_authenticated_resolver": (
            "ArtifactResolver(self.store)" in financial_runtime
            and "resolver.resolve(ref, context)" in financial_runtime
        ),
        "financial_runtime_single_writes_new_schema": (
            '"write_policy": "new_schema_only"' in financial_runtime
            and (
                "FINANCIAL_INPUT_ARTIFACT_TYPE = "
                "FINANCIAL_EVIDENCE_INPUTS_SCHEMA_VERSION"
            )
            in financial_runtime
            and "broker_reports_financial_evidence_inputs_v2"
            in financial_contracts
        ),
        "model_client_has_no_json_object_downgrade": "json_object" not in model_clients,
        "candidate_binding_default_is_false": "candidate_binding_enabled: bool = Field(default=False)" in domain_pipe,
        "answer_context_selection_default_is_true": (
            "answer_context_selection_enabled: bool = Field(default=True)"
            in domain_pipe
        ),
        "live_smokes_use_function_boundary": all(
            '"model": FUNCTION_ID' in source for source in smoke_sources
        ),
        "live_smokes_select_provider_profile": all(
            "provider_profile_id" in source for source in smoke_sources
        ),
        "live_smokes_do_not_import_provider_completion": all(
            "generate_chat_completion" not in source
            and "generate_chat_completions" not in source
            for source in smoke_sources
        ),
    }


def _production_python_has_no_heavy_local_ocr_import() -> bool:
    forbidden_roots = {"paddle", "paddleocr", "easyocr", "torch"}
    source_paths = (
        *sorted((SERVICE_ROOT / "broker_reports_gate1").glob("*.py")),
        *sorted((SERVICE_ROOT / "openwebui_actions").glob("*.py")),
    )
    for path in source_paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports = {alias.name.split(".", 1)[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports = {node.module.split(".", 1)[0]}
            else:
                continue
            if imports & forbidden_roots:
                return False
    return True


def _get_live_function(
    session: requests.Session,
    base_url: str,
    function_id: str,
) -> dict[str, Any] | None:
    response = session.get(
        _url(base_url, f"/api/v1/functions/id/{function_id}"),
        timeout=30,
    )
    if response.status_code == 404:
        return None
    response.raise_for_status()
    value = response.json()
    return value if isinstance(value, dict) else None


def _get_live_function_valves(
    session: requests.Session,
    base_url: str,
    function_id: str,
) -> dict[str, Any]:
    response = session.get(
        _url(base_url, f"/api/v1/functions/id/{function_id}/valves"),
        timeout=30,
    )
    response.raise_for_status()
    value = response.json()
    if not isinstance(value, dict):
        raise RuntimeError("stage2_delivery_function_valves_invalid")
    return value




def _read_live_prompt_state(
    *,
    ssh_target: str,
    prompt_ids: list[str],
) -> dict[str, dict[str, Any]]:
    remote_code = r'''
import hashlib
import json
import sqlite3

prompt_ids = json.loads(__PROMPT_IDS_JSON__)
conn = sqlite3.connect("/app/backend/data/webui.db")
conn.row_factory = sqlite3.Row
result = []
try:
    for prompt_id in prompt_ids:
        row = conn.execute(
            "select id, command, version_id, is_active, content, meta from prompt where id = ?",
            (prompt_id,),
        ).fetchone()
        if row is None:
            continue
        content = str(row["content"] or "")
        try:
            meta = json.loads(row["meta"] or "{}")
        except (TypeError, ValueError):
            meta = {}
        result.append({
            "prompt_ref": str(row["id"]),
            "command": str(row["command"] or ""),
            "version": str(row["version_id"] or ""),
            "is_active": int(row["is_active"] or 0),
            "content_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
            "content_length": len(content),
            "meta": {
                key: meta.get(key)
                for key in (
                    "template_id", "output_schema_version",
                    "provider_output_schema_version",
                    "structured_output_required", "extractor_domain",
                    "knowledge_rag_allowed", "vectorization_allowed",
                )
            },
        })
finally:
    conn.close()
print(json.dumps(result, ensure_ascii=False, sort_keys=True))
'''
    remote_code = remote_code.replace(
        "__PROMPT_IDS_JSON__",
        json.dumps(json.dumps(prompt_ids, ensure_ascii=False), ensure_ascii=False),
    )
    completed = subprocess.run(
        [
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=10",
            "-o",
            "StrictHostKeyChecking=yes",
            ssh_target,
            "docker",
            "exec",
            "-i",
            "openwebui",
            "python",
            "-",
        ],
        cwd=ROOT,
        input=remote_code,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=90,
    )
    value = json.loads(completed.stdout)
    rows = value if isinstance(value, list) else []
    return {
        str(item.get("prompt_ref")): item
        for item in rows
        if isinstance(item, dict) and item.get("prompt_ref")
    }


if __name__ == "__main__":
    raise SystemExit(main())
