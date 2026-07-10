from __future__ import annotations

import copy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .gate2_domain_packages import DOMAIN_PACKAGE_SCHEMA_VERSION
from .gate2_domain_routing import DOMAIN_EXTRACTOR_IDS, FACT_DOMAIN_ORDER
from .gate2_source_fact_contracts import (
    OUTPUT_SCHEMA_ID,
    SOURCE_FACTS_SCHEMA_VERSION,
    Gate2ManagedPrompt,
    Gate2ManagedPromptResolverFactory,
    Gate2PromptConfig,
    Gate2PromptError,
    Gate2PromptUserContext,
    source_facts_response_format,
)


DOMAIN_SOURCE_FACTS_SCHEMA_VERSION = "broker_reports_domain_source_facts_v0"
DOMAIN_PROMPT_CONTRACT_ID = "broker_reports_domain_source_fact_prompt_v0"
DOMAIN_PROMPT_REQUIRED_TAG = "broker-reports-gate2-domain"

FACTORY_REQUIRED = (
    "Gate2DomainPromptResolverFactory.create is the only production domain Prompt registry entrypoint"
)
FORBIDDEN = (
    "Domain prompt bodies must remain in managed OpenWebUI Prompts and must not be embedded in Python, Pipes or Valves"
)


@dataclass(frozen=True)
class Gate2DomainPromptConfig:
    source: str = "openwebui_sqlite"
    db_path: Path | None = None
    prompt_ids: dict[str, str] = field(default_factory=dict)
    prompt_commands: dict[str, str] = field(default_factory=dict)


class Gate2DomainPromptResolverFactory:
    def __init__(self, config: Gate2DomainPromptConfig) -> None:
        self.config = config

    def create(self) -> "Gate2DomainPromptResolver":
        return Gate2DomainPromptResolver(self.config)


class Gate2DomainPromptResolver:
    def __init__(self, config: Gate2DomainPromptConfig) -> None:
        self.config = config

    def resolve(
        self,
        domain: str,
        user_context: Gate2PromptUserContext,
    ) -> Gate2ManagedPrompt:
        if domain not in DOMAIN_EXTRACTOR_IDS:
            raise Gate2PromptError(
                "gate2_domain_prompt_domain_invalid",
                "Unsupported Gate 2 extractor domain",
            )
        prompt_id = self.config.prompt_ids.get(
            domain, f"broker_reports_gate2_{domain}_prompt_v0"
        )
        command = self.config.prompt_commands.get(
            domain, f"broker_gate2_{domain}_v0"
        )
        resolver = Gate2ManagedPromptResolverFactory(
            Gate2PromptConfig(
                source=self.config.source,
                db_path=self.config.db_path,
                prompt_id=prompt_id,
                command=command,
                required_template_id=f"broker_reports.{domain}_extraction.v0",
                required_template_kind=f"broker_reports_{domain}_extraction",
                required_prompt_contract_id=DOMAIN_PROMPT_CONTRACT_ID,
                required_input_schema_version=DOMAIN_PACKAGE_SCHEMA_VERSION,
                required_output_schema_id=OUTPUT_SCHEMA_ID,
                required_output_schema_version=SOURCE_FACTS_SCHEMA_VERSION,
                required_tag=DOMAIN_PROMPT_REQUIRED_TAG,
            )
        ).create()
        prompt = resolver.resolve(user_context)
        if prompt.safe_metadata.get("extractor_domain") != domain:
            raise Gate2PromptError(
                "gate2_domain_prompt_contract_mismatch",
                "Managed Prompt extractor domain does not match the package domain",
            )
        return prompt


class StaticGate2DomainPromptResolver:
    def __init__(self, prompts: dict[str, Gate2ManagedPrompt]) -> None:
        self.prompts = copy.deepcopy(prompts)

    def resolve(
        self,
        domain: str,
        user_context: Gate2PromptUserContext,
    ) -> Gate2ManagedPrompt:
        if not user_context.user_id or domain not in self.prompts:
            raise Gate2PromptError(
                "gate2_domain_prompt_not_found", "Domain Prompt is unavailable"
            )
        return copy.deepcopy(self.prompts[domain])


def domain_source_facts_response_format(package: dict[str, Any]) -> dict[str, Any]:
    allowed = set(package.get("allowed_fact_types") or [])
    if not allowed:
        raise ValueError("gate2_domain_allowed_fact_types_missing")
    response_format = source_facts_response_format(package)
    variants = response_format["json_schema"]["schema"]["properties"]["facts"][
        "items"
    ]["anyOf"]
    actual = {
        item["properties"]["fact_type"]["const"] for item in variants
    }
    domain = str(package.get("extractor_domain") or "")
    if not actual or not actual <= allowed or domain not in actual:
        raise ValueError("gate2_domain_provider_schema_not_narrow")
    return response_format


def build_domain_source_facts_wrapper(
    *,
    package: dict[str, Any],
    domain_package_ref: str,
    source_facts_ref: str,
    validation_ref: str,
    finalized_source_facts: dict[str, Any],
) -> dict[str, Any]:
    fact_types = sorted(
        {
            str(item.get("fact_type") or "")
            for item in finalized_source_facts.get("facts") or []
            if isinstance(item, dict) and item.get("fact_type")
        }
    )
    allowed = sorted(str(item) for item in package.get("allowed_fact_types") or [])
    if not set(fact_types) <= set(allowed):
        raise ValueError("gate2_domain_wrapper_fact_type_forbidden")
    return {
        "schema_version": DOMAIN_SOURCE_FACTS_SCHEMA_VERSION,
        "domain_source_facts_id": f"dsf_{package.get('package_id')}",
        "extraction_run_id": package.get("extraction_run_id"),
        "document_ref": package.get("document_ref"),
        "source_unit_ref": (package.get("source_unit") or {}).get("unit_id"),
        "extractor_domain": package.get("extractor_domain"),
        "extractor_id": package.get("extractor_id"),
        "domain_package_ref": domain_package_ref,
        "source_facts_ref": source_facts_ref,
        "validation_ref": validation_ref,
        "allowed_fact_types": allowed,
        "fact_ids": [
            str(item.get("fact_id"))
            for item in finalized_source_facts.get("facts") or []
            if isinstance(item, dict) and item.get("fact_id")
        ],
        "fact_types": fact_types,
        "covered_source_refs": copy.deepcopy(
            (finalized_source_facts.get("coverage") or {}).get(
                "fact_covered_refs"
            )
            or []
        ),
        "no_fact_results": copy.deepcopy(
            (finalized_source_facts.get("coverage") or {}).get("no_fact_results")
            or []
        ),
        "validator_status": "passed",
        "created_at": finalized_source_facts.get("created_at"),
    }


def required_domain_prompt_identities() -> list[dict[str, str]]:
    return [
        {
            "domain": domain,
            "extractor_id": DOMAIN_EXTRACTOR_IDS[domain],
            "prompt_id": f"broker_reports_gate2_{domain}_prompt_v0",
            "prompt_command": f"broker_gate2_{domain}_v0",
            "template_id": f"broker_reports.{domain}_extraction.v0",
            "template_kind": f"broker_reports_{domain}_extraction",
            "prompt_contract_id": DOMAIN_PROMPT_CONTRACT_ID,
        }
        for domain in FACT_DOMAIN_ORDER
    ]
