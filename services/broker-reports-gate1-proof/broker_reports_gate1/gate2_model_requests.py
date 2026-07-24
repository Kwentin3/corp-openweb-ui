from __future__ import annotations

import json
from typing import Any

from .gate2_model_contracts import Gate2SourceFactRuntimeError
from .gate2_source_fact_contracts import Gate2PromptError


SOURCE_REQUEST_PROFILE = "source_v0"
DOMAIN_REQUEST_PROFILE = "domain_v0"
FINANCIAL_EVIDENCE_REQUEST_PROFILE = "financial_evidence_decision_v1"
GATE2_REQUEST_PROFILES = (SOURCE_REQUEST_PROFILE, DOMAIN_REQUEST_PROFILE)
_SUPPORTED_REQUEST_PROFILES = (
    *GATE2_REQUEST_PROFILES,
    FINANCIAL_EVIDENCE_REQUEST_PROFILE,
)


class Gate2OpenWebUIRequestBuilder:
    def __init__(self, *, request_profile: str) -> None:
        if request_profile not in _SUPPORTED_REQUEST_PROFILES:
            raise Gate2SourceFactRuntimeError(
                "gate2_model_request_profile_unknown",
                "Unknown Gate 2 model request profile",
            )
        self.request_profile = request_profile

    def build(
        self,
        *,
        prompt,
        package: dict[str, Any],
        model_id: str,
        response_format: dict[str, Any],
    ) -> dict[str, Any]:
        if self.request_profile == SOURCE_REQUEST_PROFILE:
            return self._build_source(
                prompt=prompt,
                package=package,
                model_id=model_id,
                response_format=response_format,
            )
        if self.request_profile == FINANCIAL_EVIDENCE_REQUEST_PROFILE:
            return self._build_financial_evidence(
                prompt=prompt,
                package=package,
                model_id=model_id,
                response_format=response_format,
            )
        return self._build_domain(
            prompt=prompt,
            package=package,
            model_id=model_id,
            response_format=response_format,
        )

    def _build_source(
        self,
        *,
        prompt,
        package: dict[str, Any],
        model_id: str,
        response_format: dict[str, Any],
    ) -> dict[str, Any]:
        marker = "{{source_fact_package_json}}"
        if marker not in prompt.content:
            raise Gate2PromptError(
                "gate2_prompt_contract_mismatch",
                "Managed Prompt input marker is missing",
            )
        model_package = package.get("llm_context_package") or package
        package_json = json.dumps(model_package, ensure_ascii=False, sort_keys=True)
        system_content = prompt.content.replace(marker, package_json)
        user_content = json.dumps(
            {
                "task": "extract_broker_reports_source_facts_v0",
                "package_ref": package.get("package_artifact_ref"),
                "instruction": (
                    "Return exactly one broker_reports_source_facts_v0 JSON object. "
                    "Use only the package embedded in the managed Prompt and its allowed refs."
                ),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        return {
            "model": model_id,
            "messages": [
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_content},
            ],
            "stream": False,
            "response_format": response_format,
            "metadata": {
                "broker_reports_gate2": {
                    "source_fact_extraction": True,
                    "structured_output_mode": "openwebui_response_format_json_schema",
                    "prompt_ref": prompt.prompt_ref,
                    "prompt_hash": prompt.hash,
                    "output_schema_id": prompt.output_schema_id,
                    "output_schema_version": prompt.output_schema_version,
                    "output_schema_hash": package.get("output_schema", {}).get(
                        "output_schema_hash"
                    ),
                    "package_ref": package.get("package_artifact_ref"),
                }
            },
        }

    def _build_financial_evidence(
        self,
        *,
        prompt,
        package: dict[str, Any],
        model_id: str,
        response_format: dict[str, Any],
    ) -> dict[str, Any]:
        marker = "{{financial_evidence_package_json}}"
        if marker not in prompt.content:
            raise Gate2PromptError(
                "gate2_financial_evidence_prompt_contract_mismatch",
                "Managed financial evidence Prompt input marker is missing",
            )
        model_package = package.get("llm_context_package")
        if not isinstance(model_package, dict):
            raise Gate2PromptError(
                "gate2_financial_evidence_package_missing",
                "Financial evidence model package is missing",
            )
        system_content = prompt.content.replace(
            marker,
            json.dumps(
                model_package,
                ensure_ascii=False,
                sort_keys=True,
            ),
        )
        return {
            "model": model_id,
            "messages": [
                {"role": "system", "content": system_content},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "task": (
                                "decide_broker_reports_financial_evidence_v1"
                            ),
                            "source_scope_ref": package.get(
                                "source_scope_ref"
                            ),
                            "instruction": (
                                "Return exactly one decision object allowed "
                                "by the supplied strict JSON Schema."
                            ),
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                },
            ],
            "stream": False,
            "response_format": response_format,
            "metadata": {
                "broker_reports_gate2": {
                    "financial_evidence_shadow": True,
                    "structured_output_mode": (
                        "openwebui_response_format_json_schema"
                    ),
                    "prompt_ref": prompt.prompt_ref,
                    "prompt_hash": prompt.hash,
                    "source_scope_ref": package.get("source_scope_ref"),
                    "knowledge_rag_used": False,
                    "vectorization_performed": False,
                }
            },
        }

    def _build_domain(
        self,
        *,
        prompt,
        package: dict[str, Any],
        model_id: str,
        response_format: dict[str, Any],
    ) -> dict[str, Any]:
        marker = "{{source_fact_package_json}}"
        if marker not in prompt.content:
            raise Gate2PromptError(
                "gate2_domain_prompt_contract_mismatch",
                "Managed domain Prompt input marker is missing",
            )
        domain = str(package.get("extractor_domain") or "")
        candidate_binding = bool(package.get("candidate_binding_mode"))
        model_package = package.get("llm_context_package") or package
        system_content = prompt.content.replace(
            marker, json.dumps(model_package, ensure_ascii=False, sort_keys=True)
        )
        user_content = json.dumps(
            {
                "task": (
                    "select_broker_reports_candidate_bindings_v0"
                    if candidate_binding
                    else "extract_broker_reports_domain_source_facts_v0"
                ),
                "extractor_domain": domain,
                "package_ref": package.get("package_artifact_ref"),
                "allowed_fact_types": package.get("allowed_fact_types"),
                "instruction": (
                    "Return exactly one broker_reports_candidate_binding_output_v0 object. "
                    "Select only package candidate ids, relation ids and allowed semantic roles."
                    if candidate_binding
                    else "Return exactly one broker_reports_source_facts_v0 JSON object "
                    "for this domain package. Use only allowed refs and values."
                ),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        return {
            "model": model_id,
            "messages": [
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_content},
            ],
            "stream": False,
            "response_format": response_format,
            "metadata": {
                "broker_reports_gate2": {
                    "domain_source_fact_extraction": True,
                    "candidate_binding_enabled": candidate_binding,
                    "extractor_domain": domain,
                    "structured_output_mode": "openwebui_response_format_json_schema",
                    "prompt_ref": prompt.prompt_ref,
                    "prompt_hash": prompt.hash,
                    "package_ref": package.get("package_artifact_ref"),
                    "knowledge_rag_used": False,
                    "vectorization_performed": False,
                }
            },
        }
