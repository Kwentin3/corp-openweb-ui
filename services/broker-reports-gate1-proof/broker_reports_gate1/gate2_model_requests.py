from __future__ import annotations

import json
from typing import Any

from .gate2_financial_evidence_materialization_contracts import (
    sha256_json as _sha256_json,
)
from .gate2_model_contracts import Gate2SourceFactRuntimeError
from .gate2_source_fact_contracts import Gate2PromptError


SOURCE_REQUEST_PROFILE = "source_v0"
SOURCE_QUALIFICATION_REQUEST_PROFILE = "source_qualification_v1"
DOMAIN_REQUEST_PROFILE = "domain_v0"
DOMAIN_QUALIFICATION_REQUEST_PROFILE = "domain_qualification_v1"
FINANCIAL_EVIDENCE_REQUEST_PROFILE = "financial_evidence_decision_v1"
FINANCIAL_EVIDENCE_SUCCESSOR_QUALIFICATION_REQUEST_PROFILE = (
    "financial_evidence_successor_qualification_v1"
)
FINANCIAL_EVIDENCE_SUCCESSOR_QUALIFICATION_REQUEST_PROFILE_V2 = (
    "financial_evidence_successor_qualification_v2"
)
FINANCIAL_EVIDENCE_SUCCESSOR_QUALIFICATION_REQUEST_PROFILE_V3 = (
    "financial_evidence_successor_qualification_v3"
)
FINANCIAL_SEMANTIC_V5_REQUEST_PROFILE = "financial_semantic_v5"
FINANCIAL_SEMANTIC_V6_QUALIFICATION_REQUEST_PROFILE = (
    "financial_semantic_v6_qualification_v1"
)
FINANCIAL_CONTEXT_CHECKSUM_REQUEST_PROFILE = (
    "financial_context_checksum_v1"
)
GATE2_REQUEST_PROFILES = (SOURCE_REQUEST_PROFILE, DOMAIN_REQUEST_PROFILE)
_SUPPORTED_REQUEST_PROFILES = (
    *GATE2_REQUEST_PROFILES,
    SOURCE_QUALIFICATION_REQUEST_PROFILE,
    DOMAIN_QUALIFICATION_REQUEST_PROFILE,
    FINANCIAL_EVIDENCE_REQUEST_PROFILE,
    FINANCIAL_EVIDENCE_SUCCESSOR_QUALIFICATION_REQUEST_PROFILE,
    FINANCIAL_EVIDENCE_SUCCESSOR_QUALIFICATION_REQUEST_PROFILE_V2,
    FINANCIAL_EVIDENCE_SUCCESSOR_QUALIFICATION_REQUEST_PROFILE_V3,
    FINANCIAL_SEMANTIC_V5_REQUEST_PROFILE,
    FINANCIAL_SEMANTIC_V6_QUALIFICATION_REQUEST_PROFILE,
    FINANCIAL_CONTEXT_CHECKSUM_REQUEST_PROFILE,
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
        if self.request_profile == SOURCE_QUALIFICATION_REQUEST_PROFILE:
            return self._build_source_qualification(
                prompt=prompt,
                package=package,
                model_id=model_id,
                response_format=response_format,
            )
        if self.request_profile == DOMAIN_QUALIFICATION_REQUEST_PROFILE:
            return self._build_domain_qualification(
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
        if (
            self.request_profile
            == FINANCIAL_EVIDENCE_SUCCESSOR_QUALIFICATION_REQUEST_PROFILE
        ):
            return self._build_financial_evidence_successor_qualification(
                prompt=prompt,
                package=package,
                model_id=model_id,
                response_format=response_format,
            )
        if (
            self.request_profile
            == FINANCIAL_EVIDENCE_SUCCESSOR_QUALIFICATION_REQUEST_PROFILE_V2
        ):
            return self._build_financial_evidence_successor_qualification_v2(
                prompt=prompt,
                package=package,
                model_id=model_id,
                response_format=response_format,
            )
        if (
            self.request_profile
            == FINANCIAL_EVIDENCE_SUCCESSOR_QUALIFICATION_REQUEST_PROFILE_V3
        ):
            return self._build_financial_evidence_successor_qualification_v3(
                prompt=prompt,
                package=package,
                model_id=model_id,
                response_format=response_format,
            )
        if self.request_profile == FINANCIAL_SEMANTIC_V5_REQUEST_PROFILE:
            return self._build_financial_semantic_v5(
                prompt=prompt,
                package=package,
                model_id=model_id,
                response_format=response_format,
            )
        if (
            self.request_profile
            == FINANCIAL_SEMANTIC_V6_QUALIFICATION_REQUEST_PROFILE
        ):
            return self._build_financial_semantic_v6_qualification(
                prompt=prompt,
                package=package,
                model_id=model_id,
                response_format=response_format,
            )
        if (
            self.request_profile
            == FINANCIAL_CONTEXT_CHECKSUM_REQUEST_PROFILE
        ):
            return self._build_financial_context_checksum(
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

    def _build_source_qualification(
        self,
        *,
        prompt,
        package: dict[str, Any],
        model_id: str,
        response_format: dict[str, Any],
    ) -> dict[str, Any]:
        marker = "{{source_qualification_package_json}}"
        if marker not in prompt.content:
            raise Gate2PromptError(
                "gate2_source_qualification_prompt_contract_mismatch",
                "Source qualification Prompt input marker is missing",
            )
        model_package = package.get("llm_context_package")
        if not isinstance(model_package, dict):
            raise Gate2PromptError(
                "gate2_source_qualification_package_missing",
                "Source qualification model package is missing",
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
                                "qualify_broker_reports_source_"
                                "secretary_v1"
                            ),
                            "instruction": (
                                "Return exactly one strict source "
                                "qualification object for every supplied "
                                "synthetic case. Do not add prose."
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
                    "source_qualification": True,
                    "synthetic_non_customer": True,
                    "structured_output_mode": (
                        "openwebui_response_format_json_schema"
                    ),
                    "prompt_ref": prompt.prompt_ref,
                    "prompt_hash": prompt.hash,
                    "output_schema_id": prompt.output_schema_id,
                    "output_schema_version": (
                        prompt.output_schema_version
                    ),
                    "output_schema_hash": package.get(
                        "output_schema",
                        {},
                    ).get("output_schema_hash"),
                    "knowledge_rag_used": False,
                    "vectorization_performed": False,
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

    def _build_financial_evidence_successor_qualification(
        self,
        *,
        prompt,
        package: dict[str, Any],
        model_id: str,
        response_format: dict[str, Any],
    ) -> dict[str, Any]:
        marker = "{{financial_evidence_successor_input_json}}"
        if marker not in prompt.content:
            raise Gate2PromptError(
                "gate2_financial_evidence_successor_prompt_contract_mismatch",
                "Managed successor Financial Evidence input marker is missing",
            )
        if set(package) != {"eligible_types", "source_values"}:
            raise Gate2PromptError(
                "gate2_financial_evidence_successor_package_invalid",
                "Successor Financial Evidence package is not the bounded projection",
            )
        system_content = prompt.content.replace(
            marker,
            json.dumps(
                package,
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
                                "qualify_broker_reports_financial_evidence_successor_v1"
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
                    "financial_evidence_successor_qualification": True,
                    "synthetic_non_customer": True,
                    "structured_output_mode": (
                        "openwebui_response_format_json_schema"
                    ),
                    "prompt_ref": prompt.prompt_ref,
                    "prompt_hash": prompt.hash,
                    "knowledge_rag_used": False,
                    "vectorization_performed": False,
                }
            },
        }

    def _build_financial_evidence_successor_qualification_v2(
        self,
        *,
        prompt,
        package: dict[str, Any],
        model_id: str,
        response_format: dict[str, Any],
    ) -> dict[str, Any]:
        marker = "{{financial_evidence_successor_input_json}}"
        if marker not in prompt.content:
            raise Gate2PromptError(
                "gate2_financial_evidence_successor_v2_prompt_contract_mismatch",
                "Managed successor v2 Financial Evidence input marker is missing",
            )
        if set(package) != {"eligible_types", "source_groups"}:
            raise Gate2PromptError(
                "gate2_financial_evidence_successor_v2_package_invalid",
                "Successor v2 Financial Evidence package is not the bounded projection",
            )
        system_content = prompt.content.replace(
            marker,
            json.dumps(
                package,
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
                                "qualify_broker_reports_financial_evidence_"
                                "successor_v2"
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
                    "financial_evidence_successor_qualification_v2": True,
                    "synthetic_non_customer": True,
                    "structured_output_mode": (
                        "openwebui_response_format_json_schema"
                    ),
                    "prompt_ref": prompt.prompt_ref,
                    "prompt_hash": prompt.hash,
                    "knowledge_rag_used": False,
                    "vectorization_performed": False,
                }
            },
        }

    def _build_financial_evidence_successor_qualification_v3(
        self,
        *,
        prompt,
        package: dict[str, Any],
        model_id: str,
        response_format: dict[str, Any],
    ) -> dict[str, Any]:
        marker = "{{financial_semantic_matching_input_json}}"
        if marker not in prompt.content:
            raise Gate2PromptError(
                "gate2_financial_evidence_successor_v3_prompt_contract_mismatch",
                "Managed successor v3 Financial Domain marker is missing",
            )
        if set(package) != {
            "managed_assets",
            "semantic_pack",
            "structural_scope",
            "source_groups",
        }:
            raise Gate2PromptError(
                "gate2_financial_evidence_successor_v3_package_invalid",
                "Successor v3 package is not the bounded Pack projection",
            )
        system_content = prompt.content.replace(
            marker,
            json.dumps(
                package,
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
                                "qualify_broker_reports_financial_evidence_"
                                "successor_v3"
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
                    "financial_evidence_successor_qualification_v3": True,
                    "synthetic_non_customer": True,
                    "semantic_pack_complete": True,
                    "semantic_selection_owner": "llm",
                    "structured_output_mode": (
                        "openwebui_response_format_json_schema"
                    ),
                    "prompt_ref": prompt.prompt_ref,
                    "prompt_hash": prompt.hash,
                    "knowledge_rag_used": False,
                    "vectorization_performed": False,
                }
            },
        }

    def _build_financial_semantic_v5(
        self,
        *,
        prompt,
        package: dict[str, Any],
        model_id: str,
        response_format: dict[str, Any],
    ) -> dict[str, Any]:
        marker = "{{financial_semantic_decision_packet_json}}"
        if prompt.content.count(marker) != 1:
            raise Gate2PromptError(
                "gate2_financial_semantic_v5_prompt_contract_mismatch",
                "Managed V5 decision-packet marker is missing or duplicated",
            )
        if not isinstance(package, dict) or not package:
            raise Gate2PromptError(
                "gate2_financial_semantic_v5_packet_invalid",
                "V5 decision packet must be one non-empty object",
            )
        json_schema = response_format.get("json_schema")
        if (
            response_format.get("type") != "json_schema"
            or not isinstance(json_schema, dict)
            or json_schema.get("strict") is not True
            or not isinstance(json_schema.get("schema"), dict)
        ):
            raise Gate2PromptError(
                "gate2_financial_semantic_v5_response_schema_not_strict",
                "V5 requires one strict JSON response schema",
            )
        system_content = prompt.content.replace(
            marker,
            json.dumps(
                package,
                ensure_ascii=False,
                sort_keys=True,
            ),
        )
        return {
            "model": model_id,
            "messages": [
                {"role": "system", "content": system_content},
            ],
            "stream": False,
            "response_format": response_format,
            "metadata": {
                "broker_reports_gate2": {
                    "financial_semantic_v5": True,
                    "structured_output_mode": (
                        "openwebui_response_format_json_schema"
                    ),
                    "prompt_ref": prompt.prompt_ref,
                    "prompt_hash": prompt.hash,
                    "semantic_selection_owner": "llm",
                    "execution_components": [
                        "managed_prompt",
                        "decision_packet",
                        "strict_response_schema",
                    ],
                    "knowledge_rag_used": False,
                    "vectorization_performed": False,
                }
            },
        }

    def _build_financial_semantic_v6_qualification(
        self,
        *,
        prompt,
        package: dict[str, Any],
        model_id: str,
        response_format: dict[str, Any],
    ) -> dict[str, Any]:
        from .gate2_financial_semantic_v6_prompt import (
            V6_SEMANTIC_PROMPT_HASH,
            V6_SEMANTIC_PROMPT_VERSION,
            V6_SEMANTIC_SYSTEM_PROMPT,
        )
        from .gate2_financial_semantic_v6_packet import (
            SEMANTIC_PACKET_BLOCKS,
        )

        if (
            getattr(prompt, "content", None) != V6_SEMANTIC_SYSTEM_PROMPT
            or getattr(prompt, "version", None) != V6_SEMANTIC_PROMPT_VERSION
            or getattr(prompt, "hash", None) != V6_SEMANTIC_PROMPT_HASH
        ):
            raise Gate2PromptError(
                "gate2_financial_semantic_v6_prompt_contract_mismatch",
                "V6 qualification requires the exact canonical Prompt",
            )
        if (
            not isinstance(package, dict)
            or tuple(package) != SEMANTIC_PACKET_BLOCKS
            or getattr(prompt, "packet_hash", None) != _sha256_json(package)
        ):
            raise Gate2PromptError(
                "gate2_financial_semantic_v6_packet_invalid",
                "V6 qualification requires the exact four-block packet",
            )
        json_schema = response_format.get("json_schema")
        if (
            response_format.get("type") != "json_schema"
            or not isinstance(json_schema, dict)
            or json_schema.get("strict") is not True
            or not isinstance(json_schema.get("schema"), dict)
            or getattr(prompt, "choice_schema_hash", None)
            != _sha256_json(json_schema.get("schema"))
        ):
            raise Gate2PromptError(
                "gate2_financial_semantic_v6_response_schema_not_strict",
                "V6 qualification requires one strict JSON response schema",
            )
        return {
            "model": model_id,
            "messages": [
                {"role": "system", "content": prompt.content},
                {
                    "role": "user",
                    "content": json.dumps(
                        package,
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                },
            ],
            "stream": False,
            "response_format": response_format,
            "metadata": {
                "broker_reports_gate2": {
                    "financial_semantic_v6": True,
                    "request_profile": (
                        FINANCIAL_SEMANTIC_V6_QUALIFICATION_REQUEST_PROFILE
                    ),
                    "prompt_version": prompt.version,
                    "prompt_hash": prompt.hash,
                    "packet_hash": prompt.packet_hash,
                    "choice_schema_hash": prompt.choice_schema_hash,
                    "semantic_selection_owner": "llm",
                    "knowledge_rag_used": False,
                    "vectorization_performed": False,
                }
            },
        }

    def _build_domain_qualification(
        self,
        *,
        prompt,
        package: dict[str, Any],
        model_id: str,
        response_format: dict[str, Any],
    ) -> dict[str, Any]:
        marker = "{{domain_qualification_package_json}}"
        if marker not in prompt.content:
            raise Gate2PromptError(
                "gate2_domain_qualification_prompt_contract_mismatch",
                "Domain qualification Prompt input marker is missing",
            )
        model_package = package.get("llm_context_package")
        if not isinstance(model_package, dict):
            raise Gate2PromptError(
                "gate2_domain_qualification_package_missing",
                "Domain qualification model package is missing",
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
                                "qualify_broker_reports_domain_candidate_binding_v1"
                            ),
                            "case_id": package.get("case_id"),
                            "instruction": (
                                "Return exactly one strict candidate-binding "
                                "object for this synthetic case. Select only "
                                "the supplied candidate and relation IDs. "
                                "Do not add prose."
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
                    "domain_qualification": True,
                    "synthetic_non_customer": True,
                    "structured_output_mode": (
                        "openwebui_response_format_json_schema"
                    ),
                    "prompt_ref": prompt.prompt_ref,
                    "prompt_hash": prompt.hash,
                    "case_id": package.get("case_id"),
                    "extractor_domain": package.get("extractor_domain"),
                    "output_schema_id": prompt.output_schema_id,
                    "output_schema_version": (
                        prompt.output_schema_version
                    ),
                    "output_schema_hash": package.get(
                        "output_schema",
                        {},
                    ).get("output_schema_hash"),
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

    def _build_financial_context_checksum(
        self,
        *,
        prompt,
        package: dict[str, Any],
        model_id: str,
        response_format: dict[str, Any],
    ) -> dict[str, Any]:
        marker = "{{financial_context_checksum_package_json}}"
        if marker not in prompt.content:
            raise Gate2PromptError(
                "gate2_financial_context_checksum_prompt_contract_mismatch",
                "Managed financial context checksum marker is missing",
            )
        model_package = package.get("llm_context_package")
        if not isinstance(model_package, dict):
            raise Gate2PromptError(
                "gate2_financial_context_checksum_package_missing",
                "Financial context checksum model package is missing",
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
                                "reconstruct_broker_reports_financial_"
                                "context_checksum_v1"
                            ),
                            "instruction": (
                                "Return exactly three requested printed "
                                "metrics under the supplied strict schema."
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
                    "financial_context_checksum": True,
                    "structured_output_mode": (
                        "openwebui_response_format_json_schema"
                    ),
                    "prompt_ref": prompt.prompt_ref,
                    "prompt_hash": prompt.hash,
                    "financial_context_integrity_hash": package.get(
                        "financial_context_integrity_hash"
                    ),
                    "knowledge_rag_used": False,
                    "vectorization_performed": False,
                }
            },
        }
