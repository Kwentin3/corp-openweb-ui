from __future__ import annotations

import base64
import copy
import hashlib
import math
from dataclasses import asdict, dataclass
from typing import Any

from .pdf_hybrid_contracts import sha256_json
from .pdf_structural_row_windows import PdfStructuralRowWindowFactory
from .pdf_visual_topology import PdfVisualTopologyFactory


PDF_STRUCTURAL_HOLDOUT_PREREGISTRATION_SCHEMA = (
    "broker_reports_pdf_structural_holdout_preregistration_v1"
)
PDF_STRUCTURAL_HOLDOUT_PREREGISTRATION_SCHEMA_V2 = (
    "broker_reports_pdf_structural_holdout_preregistration_v2"
)
PDF_STRUCTURAL_HOLDOUT_PREREGISTRATION_SCHEMA_V3 = (
    "broker_reports_pdf_structural_holdout_preregistration_v3"
)
PDF_STRUCTURAL_HOLDOUT_TERMINAL_SCHEMA = (
    "broker_reports_pdf_structural_holdout_terminal_private_v1"
)
PDF_STRUCTURAL_HOLDOUT_TERMINAL_SCHEMA_V2 = (
    "broker_reports_pdf_structural_holdout_terminal_private_v2"
)
PDF_STRUCTURAL_HOLDOUT_TERMINAL_SCHEMA_V3 = (
    "broker_reports_pdf_structural_holdout_terminal_private_v3"
)
PDF_STRUCTURAL_HOLDOUT_PREFLIGHT_TERMINAL_SCHEMA = (
    "broker_reports_pdf_structural_holdout_preflight_terminal_private_v1"
)
PDF_STRUCTURAL_HOLDOUT_PREFLIGHT_TERMINAL_SCHEMA_V2 = (
    "broker_reports_pdf_structural_holdout_preflight_terminal_private_v2"
)
PDF_STRUCTURAL_HOLDOUT_POLICY_VERSION = "pdf_structural_holdout_policy_v1"
PDF_STRUCTURAL_HOLDOUT_POLICY_VERSION_V2 = "pdf_structural_holdout_policy_v2"
PDF_STRUCTURAL_HOLDOUT_JOURNAL_SCHEMA = (
    "broker_reports_pdf_structural_holdout_journal_entry_private_v1"
)
PDF_STRUCTURAL_HOLDOUT_WINDOW_JOURNAL_SCHEMA = (
    "broker_reports_pdf_structural_holdout_window_journal_entry_private_v1"
)
PDF_STRUCTURAL_HOLDOUT_TARGET_EXECUTION_SCHEMA = (
    "broker_reports_pdf_structural_holdout_target_execution_private_v1"
)
PDF_STRUCTURAL_HOLDOUT_FRESHNESS_SCHEMA = (
    "broker_reports_pdf_structural_holdout_freshness_scan_private_v1"
)

PDF_STRUCTURAL_HOLDOUT_EXECUTION_CLASSES = frozenset(
    {
        "fresh_holdout",
        "fresh_holdout_v2",
        "fresh_holdout_v3",
        "fresh_holdout_v4",
        "fresh_holdout_v5",
        "development_regression",
    }
)
PDF_STRUCTURAL_HOLDOUT_CERTIFICATION_CLASSES = frozenset(
    {
        "fresh_holdout",
        "fresh_holdout_v2",
        "fresh_holdout_v3",
        "fresh_holdout_v4",
        "fresh_holdout_v5",
    }
)
PDF_STRUCTURAL_HOLDOUT_CORPUS_POLICIES = {
    "fresh_holdout": {
        "policy_id": "official_public_broker_pdf_2026_07_14_v1",
        "document_count": 7,
        "repo_relative_root": (
            "local/stage2/"
            "broker_reports_pdf_structural_holdout_public_2026-07-14/corpus"
        ),
        "sha256": frozenset(
            {
                "0801355fd94f8fd8d63c2255771b53dcfe8148953891973b29657aeaba7cd17c",
                "36a166a5a13e6d6d86b391233023f83f6f7b4d268a4a23fbae01cb81290e3b96",
                "427b3621fe31bc96a4e98aacf9f36dd3cddfa1b48b3f138d3a3d3181deadc879",
                "8fbb27ace15e0eea8e81c214215f6bac823d559f601a338a25ded9ae245a2360",
                "a2d5053e9e3353ad6576c2872579e39aaaeee50663d87b3eb8933f9fdea09009",
                "e6c5ff0171e7561a53ce1d33da377721ef1035b633dca2c4525286d0a683a52e",
                "f870b8f0460ab4b221b95752961f8518ceaf77f23e403ece3bd0f496f5edc986",
            }
        ),
    },
    "fresh_holdout_v2": {
        "policy_id": "official_public_broker_pdf_2026_07_14_v2",
        "document_count": 7,
        "repo_relative_root": (
            "local/stage2/"
            "broker_reports_pdf_structural_holdout_public_v2_2026-07-14/corpus"
        ),
        "sha256": frozenset(
            {
                "1231292d67c3d7f3902b01a3f85c59dc143830155af6dd9a2d8bdf6157b09fe0",
                "3e1c2c4835ad4825ceeaa53ee1d6cebf8a885f20d8ed39775334ef5a75e97996",
                "763983a3f93a7c954708adcf2fec86938b08f1df667620f9d09c6219f8707091",
                "991c75ecdc008ae8d9f94cae623d1c7ebbbd010dff2470cfc49aea0df88a014a",
                "a54e3b81cf548353941212d40a2a4206436f81a07e0632959f80c7b98ab7924c",
                "b5691a1e4d481c284e8127286472b1ee7fa0daeb30982f35728e5f28b0650fcc",
                "e4dba251aad8bdc86d1d6a6ff755be7bcabaa22e622cc12ac1a757a625815c07",
            }
        ),
    },
    "fresh_holdout_v3": {
        "policy_id": "official_public_broker_pdf_2026_07_14_v3",
        "document_count": 7,
        "repo_relative_root": (
            "local/stage2/"
            "broker_reports_pdf_structural_holdout_public_v3_2026-07-14/corpus"
        ),
        "sha256": frozenset(
            {
                "1060b1313d802e1c720eebbb1a58e6425fed7540c5907c36cfb902c8bcb838a8",
                "1ec8d1b0f08a359d1ac2d2c8bd9d7a854d8dbd0571c1574506d1ace3ce4af2e7",
                "48ec45e1646b270cf361980b8deec8007ba63a10572586e2d8cb98e5a8494262",
                "c26a89cf4b1e8950eac7fdcff8000b450caeee8c4711418713ab70d51269cce2",
                "c4ddb1a2db63b2e079d265f153be2db0a7dacfb5ec02ec4ce5a534f560cf8d21",
                "c89992aa6e7fe3986495b64ff350d854c167726a361d69727ecdf808c87f4805",
                "e4ea55d2948100cd42fb6ddfeb9451d992f78979d6c047d85b6378e7eb3e1d72",
            }
        ),
    },
    "fresh_holdout_v4": {
        "policy_id": "official_public_broker_pdf_2026_07_14_v4",
        "document_count": 7,
        "repo_relative_root": (
            "local/stage2/"
            "broker_reports_pdf_structural_holdout_public_v4_2026-07-14/corpus"
        ),
        "sha256": frozenset(
            {
                "058c46e897f1bc9bef936bb50e442473e74082d78e72bcebd18d193d0f8fbe6c",
                "2256394d91684eef1c6272b978035d24b7aa8b8fe6b6882ffbf0c5a66b8c89bf",
                "288f8706b4306a6b1a9d239222c72662259bf120b7714a59b966dd10ac99e48e",
                "4133f7d7045d95636e647415502f86e6024407d23bda4e80e6de2cab0e55d7ac",
                "5a4d3f684a1b323754b6d8329ae3bda5f8badc32520e4ce40da8aacea765e4d8",
                "89f93d494233000c422c46fe4f23648c18e11447abc2792d39bcc641f8f4bdf6",
                "9d1c4874f225fdf469c00d789a5daf65da59f95a5c35b80d524cfe104743d8cf",
            }
        ),
    },
    "fresh_holdout_v5": {
        "policy_id": "official_public_broker_pdf_2026_07_15_v5",
        "document_count": 7,
        "repo_relative_root": (
            "local/stage2/"
            "broker_reports_pdf_structural_holdout_public_v5_2026-07-15/corpus"
        ),
        "sha256": frozenset(
            {
                "fbe6a299b05615643a0f0264568c65a64bd857b6b77752163b8c2e52bbcbf71e",
                "738a0279eba3020c9a6cf3a650df254d0a2a8a0800aae80b4889efcc0a8bec57",
                "6486885e58867d382bd433228193e476a07b6cea2061ddbd74bef1dc6c65a118",
                "d635df4866a040ce665bfde0da74dbf4dc8933931337a1b023377bf02cf60c2c",
                "bad1e5fa045f0735f02487aca14236d84037f82fd2b1230ee3c56ba3420aee67",
                "766448b2bf8b9ebe9172e4a07b0392134787a3b642288a93fbe6c0f9999ed0d3",
                "d3c6736d02e0853369ca6e18d19ab9abdbc79bc46dd346218e949516db0aff63",
            }
        ),
    },
    "development_regression": {
        "policy_id": "legacy_exposed_six_pdf_2026_07_14_v1",
        "document_count": 6,
        "repo_relative_root": None,
        "sha256": frozenset(
            {
                "1c6582477921cc5166bf76f721f1832e2aca6fcd3dcd28cc475eb855d827d9ff",
                "66a3087cb242ace4943eda1710b91c9ae526c2e27b6630330270688995f108f1",
                "f68f7ac26a2683799e0d9a0a3f24cc839c6af55c99f2983235923e3d36f1e19d",
                "7cfd297786cc91cbccbe0c2ae5bce905a2a11ac6b35e5b0a795cf9c6d41bd015",
                "74e5de8408a87508bd19ddbefec4d6403548535473c8fd4a82e89850868d21f0",
                "6137e019ea76c86fc2db9cf599ee906d840418a45ea96db000ce4a8aef731e8f",
            }
        ),
    },
}

_SELECTION_RULE = (
    "sha256_ascending_first_document_with_at_least_three_parser_"
    "table_candidates_then_first_three_page_parser_order"
)
_SELECTION_RULE_V2 = (
    "sha256_ascending_first_document_with_at_least_three_parser_only_"
    "eligible_table_candidates_then_first_three_page_parser_order_no_"
    "post_freeze_substitution"
)
_SELECTION_RULE_V5 = (
    "sha256_ascending_first_document_with_three_v5_eligible_candidates_"
    "select_first_aligned_then_first_wide_or_highest_column_remaining_"
    "then_first_ruled_or_first_remaining_require_aligned_and_ruled_store_"
    "page_parser_order_no_post_freeze_substitution"
)
PDF_STRUCTURAL_HOLDOUT_ELIGIBILITY_SCHEMA = (
    "broker_reports_pdf_structural_holdout_candidate_eligibility_private_v1"
)
PDF_STRUCTURAL_HOLDOUT_ELIGIBILITY_POLICY = {
    "schema_version": (
        "broker_reports_pdf_structural_holdout_candidate_eligibility_policy_v1"
    ),
    "allowed_table_strategy_refs": ["ruled_lines_v0"],
    "minimum_geometry_confidence": 0.9,
    "minimum_rows": 2,
    "maximum_rows": 20,
    "minimum_columns": 2,
    "maximum_columns": 16,
    "minimum_bbox_width_ratio": 0.1,
    "maximum_bbox_width_ratio": 0.98,
    "minimum_bbox_height_ratio": 0.02,
    "maximum_bbox_height_ratio": 0.55,
    "maximum_bbox_area_ratio": 0.55,
    "minimum_populated_cells": 4,
    "minimum_populated_cell_ratio": 0.5,
    "minimum_ruling_evidence": 4,
    "require_every_row_and_column_populated": True,
    "require_candidate_words_accounted_exactly_once": True,
    "source_values_or_reference_may_be_read": False,
}
PDF_STRUCTURAL_HOLDOUT_ELIGIBILITY_POLICY_CHECKSUM = sha256_json(
    PDF_STRUCTURAL_HOLDOUT_ELIGIBILITY_POLICY
)
PDF_STRUCTURAL_HOLDOUT_ELIGIBILITY_POLICY_V5 = {
    **PDF_STRUCTURAL_HOLDOUT_ELIGIBILITY_POLICY,
    "schema_version": (
        "broker_reports_pdf_structural_holdout_candidate_eligibility_policy_v2"
    ),
    "allowed_table_strategy_refs": ["aligned_text_v0", "ruled_lines_v0"],
    "minimum_geometry_confidence": 0.8,
    "minimum_ruling_evidence": 0,
    "strategy_requirements": {
        "aligned_text_v0": {
            "minimum_geometry_confidence": 0.8,
            "minimum_ruling_evidence": 0,
        },
        "ruled_lines_v0": {
            "minimum_geometry_confidence": 0.9,
            "minimum_ruling_evidence": 4,
        },
    },
}
PDF_STRUCTURAL_HOLDOUT_ELIGIBILITY_POLICY_V5_CHECKSUM = sha256_json(
    PDF_STRUCTURAL_HOLDOUT_ELIGIBILITY_POLICY_V5
)

FACTORY_REQUIRED = (
    "PdfStructuralRepairHoldoutContractFactory.create is the only holdout "
    "preregistration and terminal contract entrypoint"
)
FORBIDDEN = (
    "Holdout targets must not contain expected rows, columns, cells, spans, "
    "reference answers, prompts, per-target model settings, or policy overrides"
)

_FACTORY_TOKEN = object()
_PREREGISTRATION_KEYS = {
    "schema_version",
    "policy_version",
    "holdout_id",
    "execution_class",
    "certification_eligible",
    "corpus_policy",
    "corpus_role",
    "selection_contract",
    "execution_policy",
    "frozen_source",
    "freshness_scan",
    "documents",
    "targets",
    "reference_boundary",
    "provider_calls_started",
    "payload_checksum",
}
_DOCUMENT_KEYS = {
    "document_id",
    "repo_relative_path",
    "pdf_sha256",
    "size_bytes",
    "page_count",
    "table_candidate_count",
    "selection_status",
    "prior_experiment_matches",
}
_DOCUMENT_KEYS_V2 = _DOCUMENT_KEYS | {"eligible_table_candidate_count"}
_TARGET_KEYS = {
    "target_id",
    "document_id",
    "page_number",
    "parser_ordinal",
    "parser_observation",
    "parser_geometry_observation",
    "visual_package",
    "private_png_base64",
}
_TARGET_KEYS_V2 = _TARGET_KEYS | {"eligibility_observation"}
_TARGET_EXECUTION_KEYS = {
    "schema_version",
    "execution_mode",
    "candidate_atoms",
    "full_package_id",
    "full_package_hash",
    "window_plan",
    "plan_hash",
    "window_count",
    "window_inputs",
    "expected_attempt_rounds",
    "expected_count_token_calls",
    "expected_generate_calls",
    "hidden_retry_allowed",
    "provider_failover_allowed",
    "column_splitting_allowed",
    "reference_or_source_values_consumed",
    "execution_contract_checksum",
}
_TARGET_EXECUTION_WINDOW_KEYS = {
    "window_id",
    "window_index",
    "full_width",
    "crop_sha256",
    "png_bytes",
    "package_id",
    "package_hash",
    "private_png_base64",
    "window_package",
}
_SELECTION_KEYS = {
    "rule",
    "table_limit",
    "corpus_sha_order",
    "selected_document_id",
}
_SELECTION_KEYS_V2 = _SELECTION_KEYS | {
    "eligibility_policy",
    "eligibility_policy_checksum",
}
_EXECUTION_KEYS = {
    "attempts_per_target",
    "dpi",
    "provider_profile",
    "model_id",
    "maximum_counted_input_tokens",
    "maximum_output_tokens",
    "maximum_image_bytes",
    "maximum_response_bytes",
    "hidden_retry_allowed",
    "provider_failover_allowed",
    "column_splitting_allowed",
}
_SOURCE_KEYS = {
    "git_revision",
    "inventory",
    "inventory_checksum",
}
_SOURCE_ITEM_KEYS = {"repo_relative_path", "size_bytes", "sha256"}
_FRESHNESS_KEYS = {
    "schema_version",
    "root_repo_relative_path",
    "excluded_repo_relative_root",
    "excluded_input_inventory",
    "experiment_roots",
    "inventory",
    "inventory_checksum",
}
_REFERENCE_BOUNDARY = {
    "reference_available_at_preregistration": False,
    "reference_material_accessed": False,
    "reference_commitment_sha256": None,
}
_TERMINAL_KEYS = {
    "schema_version",
    "policy_version",
    "holdout_id",
    "execution_class",
    "certification_eligible",
    "corpus_policy",
    "preregistration_file_sha256",
    "source_freeze",
    "provider_qualification",
    "provider_config",
    "journal",
    "targets",
    "new_provider_generate_calls",
    "reference_process_started",
    "terminal_seal",
    "terminal_seal_hash",
    "artifact_checksum",
}
_TERMINAL_KEYS_V3 = _TERMINAL_KEYS | {
    "new_provider_count_token_calls",
    "expected_provider_count_token_calls",
    "expected_provider_generate_calls",
}
_TERMINAL_TARGET_KEYS = {
    "scope",
    "parser_observation",
    "parser_geometry_observation",
    "visual_package",
    "assemblies",
    "hypothesis_set",
    "repeatability",
    "consensus_result",
    "accepted_binding",
    "materialization",
}
_TERMINAL_TARGET_KEYS_V2 = _TERMINAL_TARGET_KEYS | {
    "eligibility_observation"
}
_TERMINAL_EXECUTION_KEYS = {
    "execution_contract",
    "window_stitches",
    "window_runtime_result_checksum",
}
_TERMINAL_SCOPE_KEYS = {
    "target_id",
    "document_id",
    "page_number",
    "parser_ordinal",
}
_PREFLIGHT_SCOPE_KEYS_V2 = _TERMINAL_SCOPE_KEYS | {
    "eligibility_observation"
}
_ELIGIBILITY_KEYS = {
    "schema_version",
    "policy_checksum",
    "page_ref",
    "page_number",
    "parser_ordinal",
    "table_candidate_ref",
    "table_strategy_ref",
    "geometry_confidence",
    "page_bbox",
    "candidate_bbox",
    "bbox_width_ratio",
    "bbox_height_ratio",
    "bbox_area_ratio",
    "rows_total",
    "columns_total",
    "cells_total",
    "populated_cells_total",
    "populated_cell_ratio",
    "active_rows_total",
    "active_columns_total",
    "contributing_words_total",
    "accounted_words_total",
    "duplicate_accounted_words_total",
    "unaccounted_words_total",
    "ruling_evidence_total",
    "candidate_state",
    "reason_codes",
    "eligible",
    "observation_checksum",
}
_PREFLIGHT_KEYS = {
    "schema_version",
    "policy_version",
    "holdout_id",
    "execution_class",
    "certification_eligible",
    "corpus_policy",
    "corpus_role",
    "selection_contract",
    "execution_policy",
    "frozen_source",
    "freshness_scan",
    "documents",
    "target_scopes",
    "failed_target_id",
    "failure_code",
    "reference_boundary",
    "provider_calls_started",
    "new_provider_generate_calls",
    "reference_process_started",
    "artifact_checksum",
}
_JOURNAL_KEYS = {
    "schema_version",
    "target_id",
    "attempt_number",
    "task_id",
    "job_key",
    "evidence_revision",
    "provider_config_hash",
    "count_tokens",
    "provider_attempt",
    "provider_result",
    "topology_response",
    "assembly",
    "failure_code",
    "failure_class",
    "provider_generate_call_performed",
}
_WINDOW_JOURNAL_KEYS = _JOURNAL_KEYS | {
    "window_id",
    "window_package_id",
    "provider_count_token_call_performed",
}
_PROVIDER_CONFIG_KEYS = {
    "provider_profile",
    "model_id",
    "timeout_seconds",
    "maximum_output_tokens",
    "maximum_counted_input_tokens",
    "thinking_level",
}
_QUALIFICATION_KEYS = {
    "status",
    "provider_profile",
    "provider_profile_revision",
    "requested_model_id",
    "resolved_model_id",
    "exact_model_match",
    "image_input_supported",
    "structured_output_supported",
    "maximum_output_tokens",
    "maximum_input_tokens",
    "http_status",
    "response_hash",
    "native_provider_transport",
    "credentials_from_openwebui_connection",
    "hidden_retry",
    "provider_failover",
}
_COUNT_TOKENS_KEYS = {
    "total_tokens",
    "prompt_tokens_details",
    "http_status",
    "request_hash",
    "response_hash",
    "canonical_schema_hash",
    "adapted_schema_hash",
    "schema_transform_count",
    "model_requested",
    "transport_identity",
    "within_hard_guard",
}
_COUNT_TOKENS_BUDGET_KEYS = {
    "observed_total_tokens",
    "maximum_counted_input_tokens",
}
_PROVIDER_ATTEMPT_KEYS = {
    "task_id",
    "attempt_id",
    "attempt_number",
    "attempt_lineage",
    "provider",
    "provider_profile",
    "provider_profile_revision",
    "model_requested",
    "model_resolved",
    "adapter_identity",
    "transport_identity",
    "request_hash",
    "crop_sha256",
    "model_view_hash",
    "canonical_schema_hash",
    "adapted_schema_hash",
    "schema_transform_count",
    "started_at",
    "ended_at",
    "duration_ms",
    "http_status",
    "provider_response_id",
    "usage",
    "finish_reason",
    "thinking_level",
    "parse_result",
    "terminal_failure_class",
    "hidden_retry",
    "provider_failover",
}
_PROVIDER_USAGE_KEYS = {"input_tokens", "output_tokens", "total_tokens"}
_PROVIDER_RESULT_KEYS = {
    "attempt",
    "json_output",
    "text",
    "raw_private_response",
    "response_bytes",
    "response_hash",
    "visible_output_bytes",
    "visible_output_hash",
}
_PROVIDER_FAILURE_CLASSES = {
    "provider_non_terminal",
    "timeout_or_transport",
    "provider_invalid_json",
    "provider_http",
    "provider_server",
    "provider_authentication",
    "rate_limit",
    "timeout",
    "response_budget",
    "context_budget",
    "parse_failure",
    "resolved_model_mismatch",
    "request_validation",
    "attempt_policy",
}


class PdfStructuralRepairHoldoutContractError(ValueError):
    def __init__(self, code: str, subject: str = "") -> None:
        self.code = code
        self.subject = subject
        super().__init__(code if not subject else f"{code}:{subject}")


@dataclass(frozen=True)
class PdfStructuralRepairHoldoutConfig:
    policy_version: str = PDF_STRUCTURAL_HOLDOUT_POLICY_VERSION
    corpus_document_count: int = 7
    development_regression_document_count: int = 6
    table_limit: int = 3
    attempts_per_target: int = 2
    dpi: int = 150
    provider_profile: str = "google_gemini"
    model_id: str = "models/gemini-3.5-flash"
    maximum_counted_input_tokens: int = 20_000
    maximum_output_tokens: int = 8192
    maximum_image_bytes: int = 8 * 1024 * 1024
    maximum_response_bytes: int = 2 * 1024 * 1024


class PdfStructuralRepairHoldoutContractFactory:
    def __init__(
        self, config: PdfStructuralRepairHoldoutConfig | None = None
    ) -> None:
        self.config = config or PdfStructuralRepairHoldoutConfig()

    def create(self) -> "PdfStructuralRepairHoldoutContractRuntime":
        if (
            self.config.policy_version != PDF_STRUCTURAL_HOLDOUT_POLICY_VERSION
            or self.config.corpus_document_count != 7
            or self.config.development_regression_document_count != 6
            or self.config.table_limit != 3
            or self.config.attempts_per_target != 2
            or self.config.dpi != 150
            or self.config.provider_profile != "google_gemini"
            or self.config.model_id != "models/gemini-3.5-flash"
            or self.config.maximum_counted_input_tokens != 20_000
            or self.config.maximum_output_tokens != 8192
            or self.config.maximum_image_bytes != 8 * 1024 * 1024
            or self.config.maximum_response_bytes != 2 * 1024 * 1024
        ):
            raise PdfStructuralRepairHoldoutContractError(
                "pdf_structural_holdout_config_invalid"
            )
        return PdfStructuralRepairHoldoutContractRuntime(
            self.config, _factory_token=_FACTORY_TOKEN
        )


class PdfStructuralRepairHoldoutContractRuntime:
    def __init__(
        self,
        config: PdfStructuralRepairHoldoutConfig,
        *,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise PdfStructuralRepairHoldoutContractError(
                "pdf_structural_holdout_factory_required"
            )
        self.config = config

    def execution_policy(self) -> dict[str, Any]:
        return {
            "attempts_per_target": self.config.attempts_per_target,
            "dpi": self.config.dpi,
            "provider_profile": self.config.provider_profile,
            "model_id": self.config.model_id,
            "maximum_counted_input_tokens": (
                self.config.maximum_counted_input_tokens
            ),
            "maximum_output_tokens": self.config.maximum_output_tokens,
            "maximum_image_bytes": self.config.maximum_image_bytes,
            "maximum_response_bytes": self.config.maximum_response_bytes,
            "hidden_retry_allowed": False,
            "provider_failover_allowed": False,
            "column_splitting_allowed": False,
        }

    def config_hash(self) -> str:
        return sha256_json(asdict(self.config))

    def build_candidate_eligibility_observation(
        self,
        *,
        candidate: dict[str, Any],
        page: dict[str, Any],
        candidate_bbox: list[Any],
        execution_class: str = "fresh_holdout_v2",
    ) -> dict[str, Any]:
        """Classify a parser candidate without reading text or a reference."""
        policy = _eligibility_policy(execution_class)
        policy_checksum = _eligibility_policy_checksum(execution_class)
        page_width = _finite_number(page.get("layout_page_width"))
        page_height = _finite_number(page.get("layout_page_height"))
        normalized_bbox = _normalized_bbox(candidate_bbox)
        page_bbox = [0.0, 0.0, page_width, page_height]
        if normalized_bbox and page_width > 0.0 and page_height > 0.0:
            bbox_width = normalized_bbox[2] - normalized_bbox[0]
            bbox_height = normalized_bbox[3] - normalized_bbox[1]
            width_ratio = round(bbox_width / page_width, 6)
            height_ratio = round(bbox_height / page_height, 6)
            area_ratio = round(
                (bbox_width * bbox_height) / (page_width * page_height), 6
            )
        else:
            width_ratio = height_ratio = area_ratio = 0.0
        cells = _dicts(candidate.get("cell_inventory"))
        populated = [item for item in cells if _strings(item.get("word_refs"))]
        rows_total = _integer_or_zero(candidate.get("rows_total"))
        columns_total = _integer_or_zero(candidate.get("columns_total"))
        populated_cells_total = len(populated)
        populated_cell_ratio = round(
            populated_cells_total / len(cells), 6
        ) if cells else 0.0
        active_rows = {
            _integer_or_zero(item.get("row_ordinal")) for item in populated
        }
        active_columns = {
            _integer_or_zero(item.get("column_ordinal")) for item in populated
        }
        contributing_words = _strings(candidate.get("contributing_word_refs"))
        accounted_words = [
            word_ref for item in cells for word_ref in _strings(item.get("word_refs"))
        ]
        accounting_mismatch = set(contributing_words) ^ set(accounted_words)
        result = {
            "schema_version": PDF_STRUCTURAL_HOLDOUT_ELIGIBILITY_SCHEMA,
            "policy_checksum": policy_checksum,
            "page_ref": str(page.get("page_ref") or ""),
            "page_number": _integer_or_zero(page.get("page_number")),
            "parser_ordinal": _integer_or_zero(candidate.get("parser_ordinal")),
            "table_candidate_ref": str(
                candidate.get("table_candidate_ref") or ""
            ),
            "table_strategy_ref": str(
                candidate.get("table_strategy_ref") or ""
            ),
            "geometry_confidence": _finite_number(
                candidate.get("geometry_confidence")
            ),
            "page_bbox": page_bbox,
            "candidate_bbox": normalized_bbox or [],
            "bbox_width_ratio": width_ratio,
            "bbox_height_ratio": height_ratio,
            "bbox_area_ratio": area_ratio,
            "rows_total": rows_total,
            "columns_total": columns_total,
            "cells_total": len(cells),
            "populated_cells_total": populated_cells_total,
            "populated_cell_ratio": populated_cell_ratio,
            "active_rows_total": len(active_rows - {0}),
            "active_columns_total": len(active_columns - {0}),
            "contributing_words_total": len(contributing_words),
            "accounted_words_total": len(accounted_words),
            "duplicate_accounted_words_total": (
                len(accounted_words) - len(set(accounted_words))
            ),
            "unaccounted_words_total": len(accounting_mismatch),
            "ruling_evidence_total": _integer_or_zero(
                candidate.get("ruling_evidence_total")
            ),
            "candidate_state": str(
                candidate.get("table_reconstruction_status") or ""
            ),
        }
        reason_codes = _candidate_eligibility_reason_codes(
            result, policy=policy
        )
        result["reason_codes"] = reason_codes
        result["eligible"] = not reason_codes
        result["observation_checksum"] = sha256_json(result)
        errors = self.validate_candidate_eligibility_observation(
            result, execution_class=execution_class
        )
        if errors:
            raise PdfStructuralRepairHoldoutContractError(errors[0])
        return result

    def validate_candidate_eligibility_observation(
        self,
        value: Any,
        *,
        execution_class: str = "fresh_holdout_v2",
    ) -> list[str]:
        data = _object(value)
        policy = _eligibility_policy(execution_class)
        policy_checksum = _eligibility_policy_checksum(execution_class)
        errors: list[str] = []
        if set(data) != _ELIGIBILITY_KEYS:
            return ["pdf_structural_holdout_eligibility_keys_invalid"]
        unsigned = dict(data)
        stored_checksum = unsigned.pop("observation_checksum", None)
        page_bbox = _normalized_bbox(data.get("page_bbox"))
        candidate_bbox = _normalized_bbox(data.get("candidate_bbox"))
        if (
            data.get("schema_version")
            != PDF_STRUCTURAL_HOLDOUT_ELIGIBILITY_SCHEMA
            or data.get("policy_checksum") != policy_checksum
            or not isinstance(data.get("page_ref"), str)
            or not data.get("page_ref")
            or not _positive_int(data.get("page_number"))
            or not _positive_int(data.get("parser_ordinal"))
            or not isinstance(data.get("table_candidate_ref"), str)
            or not data.get("table_candidate_ref")
            or not isinstance(data.get("table_strategy_ref"), str)
            or not _finite_nonnegative_number(data.get("geometry_confidence"))
            or page_bbox is None
            or candidate_bbox is None
            or page_bbox[:2] != [0.0, 0.0]
            or any(
                not _finite_nonnegative_number(data.get(key))
                for key in (
                    "bbox_width_ratio",
                    "bbox_height_ratio",
                    "bbox_area_ratio",
                    "populated_cell_ratio",
                )
            )
            or any(
                not _nonnegative_int(data.get(key))
                for key in (
                    "rows_total",
                    "columns_total",
                    "cells_total",
                    "populated_cells_total",
                    "active_rows_total",
                    "active_columns_total",
                    "contributing_words_total",
                    "accounted_words_total",
                    "duplicate_accounted_words_total",
                    "unaccounted_words_total",
                    "ruling_evidence_total",
                )
            )
            or not isinstance(data.get("candidate_state"), str)
            or not isinstance(data.get("reason_codes"), list)
            or any(not _reason_code(item) for item in data.get("reason_codes") or [])
            or data.get("reason_codes")
            != sorted(set(data.get("reason_codes") or []))
            or not isinstance(data.get("eligible"), bool)
            or _integer_or_zero(data.get("populated_cells_total"))
            > _integer_or_zero(data.get("cells_total"))
            or _integer_or_zero(data.get("active_rows_total"))
            > _integer_or_zero(data.get("rows_total"))
            or _integer_or_zero(data.get("active_columns_total"))
            > _integer_or_zero(data.get("columns_total"))
            or _integer_or_zero(data.get("duplicate_accounted_words_total"))
            > _integer_or_zero(data.get("accounted_words_total"))
            or data.get("populated_cell_ratio")
            != (
                round(
                    _integer_or_zero(data.get("populated_cells_total"))
                    / _integer_or_zero(data.get("cells_total")),
                    6,
                )
                if _integer_or_zero(data.get("cells_total")) > 0
                else 0.0
            )
        ):
            errors.append("pdf_structural_holdout_eligibility_shape_invalid")
        if page_bbox is not None and candidate_bbox is not None:
            page_width = page_bbox[2] - page_bbox[0]
            page_height = page_bbox[3] - page_bbox[1]
            candidate_width = candidate_bbox[2] - candidate_bbox[0]
            candidate_height = candidate_bbox[3] - candidate_bbox[1]
            expected_ratios = (
                round(candidate_width / page_width, 6),
                round(candidate_height / page_height, 6),
                round(
                    candidate_width
                    * candidate_height
                    / (page_width * page_height),
                    6,
                ),
            )
            if (
                page_width <= 0.0
                or page_height <= 0.0
                or candidate_bbox[0] < 0.0
                or candidate_bbox[1] < 0.0
                or candidate_bbox[2] > page_width
                or candidate_bbox[3] > page_height
                or tuple(
                    data.get(key)
                    for key in (
                        "bbox_width_ratio",
                        "bbox_height_ratio",
                        "bbox_area_ratio",
                    )
                )
                != expected_ratios
            ):
                errors.append("pdf_structural_holdout_eligibility_geometry_invalid")
        expected_reasons = _candidate_eligibility_reason_codes(
            data, policy=policy
        )
        if (
            data.get("reason_codes") != expected_reasons
            or data.get("eligible") is not (not expected_reasons)
        ):
            errors.append("pdf_structural_holdout_eligibility_decision_invalid")
        if stored_checksum != sha256_json(unsigned):
            errors.append("pdf_structural_holdout_eligibility_checksum_invalid")
        return sorted(set(errors))

    def build_target_execution_contract(
        self,
        *,
        parser_observation: dict[str, Any],
        visual_package: dict[str, Any],
        window_plan: dict[str, Any] | None = None,
        window_inputs: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        planner = PdfStructuralRowWindowFactory().create()
        mode = planner.execution_mode(parser_observation)
        raw_inputs = window_inputs or []
        frozen_inputs: list[dict[str, Any]] = []
        if mode == "vertical_atom_windows":
            if window_plan is None or planner.validate_plan(
                parser_observation=parser_observation,
                plan=window_plan,
            ):
                raise PdfStructuralRepairHoldoutContractError(
                    "pdf_structural_holdout_window_plan_invalid"
                )
            for index, item in enumerate(raw_inputs, start=1):
                package = _object(item.get("window_package"))
                png_bytes = item.get("png_bytes")
                crop = _object(package.get("crop_identity"))
                if not isinstance(png_bytes, bytes) or not png_bytes:
                    raise PdfStructuralRepairHoldoutContractError(
                        "pdf_structural_holdout_window_input_invalid"
                    )
                frozen_inputs.append(
                    {
                        "window_id": item.get("window_id"),
                        "window_index": index,
                        "full_width": True,
                        "crop_sha256": crop.get("crop_sha256"),
                        "png_bytes": len(png_bytes),
                        "package_id": package.get("package_id"),
                        "package_hash": package.get("package_hash"),
                        "private_png_base64": base64.b64encode(
                            png_bytes
                        ).decode("ascii"),
                        "window_package": copy.deepcopy(package),
                    }
                )
            provider_input_count = len(frozen_inputs)
            plan_hash: str | None = str(window_plan.get("plan_hash") or "")
            frozen_plan: dict[str, Any] | None = copy.deepcopy(window_plan)
        else:
            if window_plan is not None or raw_inputs:
                raise PdfStructuralRepairHoldoutContractError(
                    "pdf_structural_holdout_whole_execution_input_invalid"
                )
            provider_input_count = 1
            plan_hash = None
            frozen_plan = None
        result = {
            "schema_version": PDF_STRUCTURAL_HOLDOUT_TARGET_EXECUTION_SCHEMA,
            "execution_mode": mode,
            "candidate_atoms": len(
                _dicts(parser_observation.get("candidates"))
            ),
            "full_package_id": visual_package.get("package_id"),
            "full_package_hash": visual_package.get("package_hash"),
            "window_plan": frozen_plan,
            "plan_hash": plan_hash,
            "window_count": provider_input_count,
            "window_inputs": frozen_inputs,
            "expected_attempt_rounds": self.config.attempts_per_target,
            "expected_count_token_calls": (
                self.config.attempts_per_target * provider_input_count
            ),
            "expected_generate_calls": (
                self.config.attempts_per_target * provider_input_count
            ),
            "hidden_retry_allowed": False,
            "provider_failover_allowed": False,
            "column_splitting_allowed": False,
            "reference_or_source_values_consumed": False,
        }
        result["execution_contract_checksum"] = sha256_json(result)
        errors = self.validate_target_execution_contract(
            parser_observation=parser_observation,
            visual_package=visual_package,
            contract=result,
        )
        if errors:
            raise PdfStructuralRepairHoldoutContractError(errors[0])
        return result

    def validate_target_execution_contract(
        self,
        *,
        parser_observation: dict[str, Any],
        visual_package: dict[str, Any],
        contract: Any,
    ) -> list[str]:
        data = _object(contract)
        if set(data) != _TARGET_EXECUTION_KEYS:
            return ["pdf_structural_holdout_execution_contract_keys_invalid"]
        errors: list[str] = []
        planner = PdfStructuralRowWindowFactory().create()
        try:
            expected_mode = planner.execution_mode(parser_observation)
        except ValueError:
            expected_mode = "invalid"
        raw_windows = data.get("window_inputs")
        frozen_windows = _dicts(raw_windows)
        if (
            data.get("schema_version")
            != PDF_STRUCTURAL_HOLDOUT_TARGET_EXECUTION_SCHEMA
            or data.get("execution_mode") != expected_mode
            or data.get("candidate_atoms")
            != len(_dicts(parser_observation.get("candidates")))
            or data.get("full_package_id") != visual_package.get("package_id")
            or data.get("full_package_hash")
            != visual_package.get("package_hash")
            or not isinstance(raw_windows, list)
            or len(frozen_windows) != len(raw_windows)
            or data.get("expected_attempt_rounds")
            != self.config.attempts_per_target
            or data.get("hidden_retry_allowed") is not False
            or data.get("provider_failover_allowed") is not False
            or data.get("column_splitting_allowed") is not False
            or data.get("reference_or_source_values_consumed") is not False
        ):
            errors.append("pdf_structural_holdout_execution_contract_invalid")
        if expected_mode == "whole_table":
            if (
                data.get("window_plan") is not None
                or data.get("plan_hash") is not None
                or data.get("window_count") != 1
                or frozen_windows
            ):
                errors.append("pdf_structural_holdout_whole_execution_invalid")
            expected_inputs = 1
        elif expected_mode == "vertical_atom_windows":
            plan = _object(data.get("window_plan"))
            plan_windows = _dicts(plan.get("windows"))
            visual = PdfVisualTopologyFactory().create()
            if (
                planner.validate_plan(
                    parser_observation=parser_observation,
                    plan=plan,
                )
                or data.get("plan_hash") != plan.get("plan_hash")
                or data.get("window_count") != len(plan_windows)
                or len(frozen_windows) != len(plan_windows)
                or [item.get("window_id") for item in frozen_windows]
                != [item.get("window_id") for item in plan_windows]
            ):
                errors.append("pdf_structural_holdout_window_plan_invalid")
            for index, (window, frozen) in enumerate(
                zip(plan_windows, frozen_windows), start=1
            ):
                package = _object(frozen.get("window_package"))
                crop = _object(package.get("crop_identity"))
                try:
                    png_bytes = base64.b64decode(
                        str(frozen.get("private_png_base64") or ""),
                        validate=True,
                    )
                except (TypeError, ValueError):
                    png_bytes = b""
                if (
                    set(frozen) != _TARGET_EXECUTION_WINDOW_KEYS
                    or frozen.get("window_id") != window.get("window_id")
                    or frozen.get("window_index") != index
                    or frozen.get("full_width") is not True
                    or window.get("full_width") is not True
                    or frozen.get("crop_sha256") != crop.get("crop_sha256")
                    or frozen.get("png_bytes") != len(png_bytes)
                    or not png_bytes
                    or frozen.get("crop_sha256")
                    != hashlib.sha256(png_bytes).hexdigest()
                    or frozen.get("package_id") != package.get("package_id")
                    or frozen.get("package_hash")
                    != package.get("package_hash")
                    or visual.validate_window_package(
                        parser_observation=parser_observation,
                        full_package=visual_package,
                        window_plan=plan,
                        window=window,
                        package=package,
                    )
                ):
                    errors.append(
                        "pdf_structural_holdout_window_input_invalid"
                    )
                    break
            expected_inputs = len(plan_windows)
        else:
            expected_inputs = 0
            errors.append("pdf_structural_holdout_execution_mode_invalid")
        expected_calls = self.config.attempts_per_target * expected_inputs
        if (
            data.get("expected_count_token_calls") != expected_calls
            or data.get("expected_generate_calls") != expected_calls
        ):
            errors.append("pdf_structural_holdout_execution_call_plan_invalid")
        unsigned = dict(data)
        stored = unsigned.pop("execution_contract_checksum", None)
        if stored != sha256_json(unsigned):
            errors.append("pdf_structural_holdout_execution_checksum_invalid")
        return sorted(set(errors))

    def build_preflight_terminal(
        self,
        *,
        documents: list[dict[str, Any]],
        target_scopes: list[dict[str, Any]],
        frozen_source: dict[str, Any],
        freshness_scan: dict[str, Any],
        execution_class: str,
        failed_target_id: str,
        failure_code: str,
    ) -> dict[str, Any]:
        policy = _corpus_policy(execution_class)
        selected_ids = {
            str(item.get("document_id") or "") for item in target_scopes
        }
        selected_document_id = (
            next(iter(selected_ids)) if len(selected_ids) == 1 else ""
        )
        selection_contract = _selection_contract(
            execution_class=execution_class,
            table_limit=self.config.table_limit,
            corpus_sha_order=[
                str(item.get("pdf_sha256") or "") for item in documents
            ],
            selected_document_id=selected_document_id,
        )
        holdout_id = self._expected_holdout_id(
            documents=documents,
            targets=target_scopes,
            frozen_source=frozen_source,
            freshness_scan=freshness_scan,
            execution_class=execution_class,
        )
        result = {
            "schema_version": _preflight_schema(execution_class),
            "policy_version": _policy_version(execution_class),
            "holdout_id": holdout_id,
            "execution_class": execution_class,
            "certification_eligible": _certification_eligible(execution_class),
            "corpus_policy": policy.get("policy_id"),
            "corpus_role": execution_class,
            "selection_contract": selection_contract,
            "execution_policy": self.execution_policy(),
            "frozen_source": copy.deepcopy(frozen_source),
            "freshness_scan": copy.deepcopy(freshness_scan),
            "documents": copy.deepcopy(documents),
            "target_scopes": copy.deepcopy(target_scopes),
            "failed_target_id": failed_target_id,
            "failure_code": failure_code,
            "reference_boundary": dict(_REFERENCE_BOUNDARY),
            "provider_calls_started": False,
            "new_provider_generate_calls": 0,
            "reference_process_started": False,
        }
        result["artifact_checksum"] = sha256_json(result)
        errors = self.validate_preflight_terminal(result)
        if errors:
            raise PdfStructuralRepairHoldoutContractError(errors[0])
        return result

    def validate_preflight_terminal(self, value: Any) -> list[str]:
        data = _object(value)
        errors: list[str] = []
        execution_class = str(data.get("execution_class") or "")
        policy = _corpus_policy(execution_class)
        if set(data) != _PREFLIGHT_KEYS:
            errors.append("pdf_structural_holdout_preflight_keys_invalid")
        if (
            data.get("schema_version") != _preflight_schema(execution_class)
            or data.get("policy_version") != _policy_version(execution_class)
            or data.get("execution_class")
            not in PDF_STRUCTURAL_HOLDOUT_EXECUTION_CLASSES
            or data.get("corpus_role") != data.get("execution_class")
            or data.get("certification_eligible")
            is not _certification_eligible(execution_class)
            or data.get("corpus_policy") != policy.get("policy_id")
            or data.get("execution_policy") != self.execution_policy()
        ):
            errors.append("pdf_structural_holdout_preflight_identity_invalid")
        raw_documents = data.get("documents")
        raw_target_scopes = data.get("target_scopes")
        documents = _dicts(raw_documents)
        target_scopes = _dicts(raw_target_scopes)
        selection = _object(data.get("selection_contract"))
        if (
            not isinstance(raw_documents, list)
            or len(documents) != len(raw_documents)
            or len(documents) != _integer_or_zero(policy.get("document_count"))
            or any(
                set(item) != _document_keys(execution_class)
                for item in documents
            )
        ):
            errors.append("pdf_structural_holdout_preflight_documents_invalid")
        document_ids = [str(item.get("document_id") or "") for item in documents]
        pdf_hashes = [str(item.get("pdf_sha256") or "") for item in documents]
        if (
            not all(document_ids)
            or len(document_ids) != len(set(document_ids))
            or not all(_sha256(item) for item in pdf_hashes)
            or pdf_hashes != sorted(pdf_hashes)
            or len(pdf_hashes) != len(set(pdf_hashes))
            or set(pdf_hashes) != set(policy.get("sha256") or set())
            or any(
                not _document_path_matches_policy(
                    item.get("repo_relative_path"), policy
                )
                for item in documents
            )
            or any(
                not _repo_relative_path(item.get("repo_relative_path"))
                or not _positive_int(item.get("size_bytes"))
                or not _nonnegative_int(item.get("page_count"))
                or not _nonnegative_int(item.get("table_candidate_count"))
                or (
                    _is_v2_execution(execution_class)
                    and not _nonnegative_int(
                        item.get("eligible_table_candidate_count")
                    )
                )
                or (
                    _is_v2_execution(execution_class)
                    and _integer_or_zero(
                        item.get("eligible_table_candidate_count")
                    )
                    > _integer_or_zero(item.get("table_candidate_count"))
                )
                or item.get("selection_status")
                not in {
                    "not_selected_insufficient_candidates",
                    "selected",
                    "not_evaluated",
                }
                or not _nonnegative_int(item.get("prior_experiment_matches"))
                for item in documents
            )
        ):
            errors.append("pdf_structural_holdout_preflight_document_identity_invalid")
        if (
            set(selection) != _selection_keys(execution_class)
            or selection
            != _selection_contract(
                execution_class=execution_class,
                table_limit=self.config.table_limit,
                corpus_sha_order=pdf_hashes,
                selected_document_id=str(
                    selection.get("selected_document_id") or ""
                ),
            )
        ):
            errors.append("pdf_structural_holdout_preflight_selection_invalid")
        expected_target_ids = [
            f"holdout_{index:03d}"
            for index in range(1, self.config.table_limit + 1)
        ]
        target_ids = [str(item.get("target_id") or "") for item in target_scopes]
        target_document_ids = {
            str(item.get("document_id") or "") for item in target_scopes
        }
        target_order = [
            (
                _integer_or_zero(item.get("page_number")),
                _integer_or_zero(item.get("parser_ordinal")),
            )
            for item in target_scopes
        ]
        if (
            not isinstance(raw_target_scopes, list)
            or len(target_scopes) != len(raw_target_scopes)
            or len(target_scopes) != self.config.table_limit
            or any(
                set(item) != _preflight_scope_keys(execution_class)
                for item in target_scopes
            )
            or target_ids != expected_target_ids
            or len(target_document_ids) != 1
            or selection.get("selected_document_id") not in target_document_ids
            or target_order != sorted(target_order)
            or (
                _is_v5_execution(execution_class)
                and not _v5_strategy_coverage(target_scopes)
            )
            or (
                _is_v2_execution(execution_class)
                and len(target_order) != len(set(target_order))
            )
            or any(
                not _positive_int(item.get("page_number"))
                or not _positive_int(item.get("parser_ordinal"))
                or (
                    _is_v2_execution(execution_class)
                    and (
                        self.validate_candidate_eligibility_observation(
                            item.get("eligibility_observation"),
                            execution_class=execution_class,
                        )
                        or _object(
                            item.get("eligibility_observation")
                        ).get("eligible")
                        is not True
                        or _object(
                            item.get("eligibility_observation")
                        ).get("page_number")
                        != item.get("page_number")
                        or _object(
                            item.get("eligibility_observation")
                        ).get("parser_ordinal")
                        != item.get("parser_ordinal")
                    )
                )
                for item in target_scopes
            )
        ):
            errors.append("pdf_structural_holdout_preflight_targets_invalid")
        selected_documents = [
            item for item in documents if item.get("selection_status") == "selected"
        ]
        selected_index = (
            documents.index(selected_documents[0])
            if len(selected_documents) == 1
            else -1
        )
        if (
            len(selected_documents) != 1
            or selected_documents[0].get("document_id")
            != selection.get("selected_document_id")
            or _integer_or_zero(selected_documents[0].get("page_count")) < 1
            or _candidate_count_for_selection(
                selected_documents[0], execution_class
            )
            < self.config.table_limit
            or any(
                _integer_or_zero(item.get("page_number"))
                > _integer_or_zero(selected_documents[0].get("page_count"))
                for item in target_scopes
            )
            or selected_index < 0
            or any(
                item.get("selection_status")
                != "not_selected_insufficient_candidates"
                or _integer_or_zero(item.get("page_count")) < 1
                or (
                    not _is_v5_execution(execution_class)
                    and _candidate_count_for_selection(
                        item, execution_class
                    )
                    >= self.config.table_limit
                )
                for item in documents[:selected_index]
            )
            or any(
                item.get("selection_status") != "not_evaluated"
                or _integer_or_zero(item.get("page_count")) != 0
                or _integer_or_zero(item.get("table_candidate_count")) != 0
                or (
                    _is_v2_execution(execution_class)
                    and _integer_or_zero(
                        item.get("eligible_table_candidate_count")
                    )
                    != 0
                )
                for item in documents[selected_index + 1 :]
            )
        ):
            errors.append("pdf_structural_holdout_preflight_selected_document_invalid")
        errors.extend(_source_freeze_errors(_object(data.get("frozen_source"))))
        errors.extend(
            _freshness_scan_errors(
                _object(data.get("freshness_scan")),
                execution_class=str(data.get("execution_class") or ""),
            )
        )
        if _object(data.get("freshness_scan")).get(
            "excluded_input_inventory"
        ) != _document_input_inventory(documents):
            errors.append(
                "pdf_structural_holdout_preflight_input_inventory_invalid"
            )
        if _certification_eligible(execution_class) and any(
            _integer_or_zero(item.get("prior_experiment_matches")) != 0
            for item in documents
        ):
            errors.append("pdf_structural_holdout_preflight_freshness_invalid")
        if (
            data.get("reference_boundary") != _REFERENCE_BOUNDARY
            or data.get("provider_calls_started") is not False
            or data.get("new_provider_generate_calls") != 0
            or data.get("reference_process_started") is not False
            or data.get("failed_target_id") not in expected_target_ids
            or not _reason_code(data.get("failure_code"))
        ):
            errors.append("pdf_structural_holdout_preflight_boundary_invalid")
        expected_holdout_id = self._expected_holdout_id(
            documents=documents,
            targets=target_scopes,
            frozen_source=_object(data.get("frozen_source")),
            freshness_scan=_object(data.get("freshness_scan")),
            execution_class=str(data.get("execution_class") or ""),
        )
        if data.get("holdout_id") != expected_holdout_id:
            errors.append("pdf_structural_holdout_preflight_holdout_id_invalid")
        unsigned = dict(data)
        stored_checksum = unsigned.pop("artifact_checksum", None)
        if stored_checksum != sha256_json(unsigned):
            errors.append("pdf_structural_holdout_preflight_checksum_invalid")
        return sorted(set(errors))

    def build_preregistration(
        self,
        *,
        documents: list[dict[str, Any]],
        targets: list[dict[str, Any]],
        frozen_source: dict[str, Any],
        freshness_scan: dict[str, Any],
        execution_class: str,
    ) -> dict[str, Any]:
        policy = _corpus_policy(execution_class)
        corpus_sha_order = [
            str(item.get("pdf_sha256") or "") for item in documents
        ]
        selected_ids = {
            str(item.get("document_id") or "") for item in targets
        }
        selected_document_id = (
            next(iter(selected_ids)) if len(selected_ids) == 1 else ""
        )
        selection_contract = _selection_contract(
            execution_class=execution_class,
            table_limit=self.config.table_limit,
            corpus_sha_order=corpus_sha_order,
            selected_document_id=selected_document_id,
        )
        holdout_id = self._expected_holdout_id(
            documents=documents,
            targets=targets,
            frozen_source=frozen_source,
            freshness_scan=freshness_scan,
            execution_class=execution_class,
        )
        result = {
            "schema_version": PDF_STRUCTURAL_HOLDOUT_PREREGISTRATION_SCHEMA_V3,
            "policy_version": _policy_version(execution_class),
            "holdout_id": holdout_id,
            "execution_class": execution_class,
            "certification_eligible": _certification_eligible(execution_class),
            "corpus_policy": policy.get("policy_id"),
            "corpus_role": execution_class,
            "selection_contract": selection_contract,
            "execution_policy": self.execution_policy(),
            "frozen_source": copy.deepcopy(frozen_source),
            "freshness_scan": copy.deepcopy(freshness_scan),
            "documents": copy.deepcopy(documents),
            "targets": copy.deepcopy(targets),
            "reference_boundary": dict(_REFERENCE_BOUNDARY),
            "provider_calls_started": False,
        }
        result["payload_checksum"] = sha256_json(result)
        errors = self.validate_preregistration(result)
        if errors:
            raise PdfStructuralRepairHoldoutContractError(errors[0])
        return result

    def _expected_holdout_id(
        self,
        *,
        documents: list[dict[str, Any]],
        targets: list[dict[str, Any]],
        frozen_source: dict[str, Any],
        freshness_scan: dict[str, Any],
        execution_class: str,
    ) -> str:
        return "pdfholdout_" + sha256_json(
            {
                "documents": [
                    {
                        "document_id": item.get("document_id"),
                        "pdf_sha256": item.get("pdf_sha256"),
                    }
                    for item in documents
                ],
                "target_scopes": [
                    {
                        "target_id": item.get("target_id"),
                        "document_id": item.get("document_id"),
                        "page_number": item.get("page_number"),
                        "parser_ordinal": item.get("parser_ordinal"),
                        **(
                            {
                                "eligibility_observation_checksum": _object(
                                    item.get("eligibility_observation")
                                ).get("observation_checksum")
                            }
                            if _is_v2_execution(execution_class)
                            else {}
                        ),
                        **(
                            {
                                "execution_contract_checksum": _object(
                                    item.get("execution_contract")
                                ).get("execution_contract_checksum")
                            }
                            if isinstance(item.get("execution_contract"), dict)
                            else {}
                        ),
                    }
                    for item in targets
                ],
                "execution_policy": self.execution_policy(),
                "execution_class": execution_class,
                "corpus_policy": _corpus_policy(execution_class).get(
                    "policy_id"
                ),
                "policy_version": _policy_version(execution_class),
                "source_inventory_checksum": frozen_source.get(
                    "inventory_checksum"
                ),
                "freshness_inventory_checksum": freshness_scan.get(
                    "inventory_checksum"
                ),
            }
        )[:24]

    def validate_preregistration(self, value: Any) -> list[str]:
        data = _object(value)
        errors: list[str] = []
        execution_class = str(data.get("execution_class") or "")
        execution_v3 = (
            data.get("schema_version")
            == PDF_STRUCTURAL_HOLDOUT_PREREGISTRATION_SCHEMA_V3
        )
        policy = _corpus_policy(execution_class)
        if set(data) != _PREREGISTRATION_KEYS:
            errors.append("pdf_structural_holdout_preregistration_keys_invalid")
        if (
            data.get("schema_version")
            not in {
                _preregistration_schema(execution_class),
                PDF_STRUCTURAL_HOLDOUT_PREREGISTRATION_SCHEMA_V3,
            }
            or data.get("policy_version") != _policy_version(execution_class)
            or data.get("execution_class")
            not in PDF_STRUCTURAL_HOLDOUT_EXECUTION_CLASSES
            or data.get("corpus_role") != data.get("execution_class")
            or data.get("certification_eligible")
            is not _certification_eligible(execution_class)
            or data.get("corpus_policy") != policy.get("policy_id")
            or not isinstance(data.get("holdout_id"), str)
            or not str(data.get("holdout_id") or "").startswith("pdfholdout_")
        ):
            errors.append("pdf_structural_holdout_preregistration_identity_invalid")
        if data.get("execution_policy") != self.execution_policy():
            errors.append("pdf_structural_holdout_execution_policy_invalid")
        selection = _object(data.get("selection_contract"))
        raw_documents = data.get("documents")
        raw_targets = data.get("targets")
        documents = _dicts(raw_documents)
        targets = _dicts(raw_targets)
        source = _object(data.get("frozen_source"))
        freshness_scan = _object(data.get("freshness_scan"))
        if (
            set(selection) != _selection_keys(execution_class)
            or selection
            != _selection_contract(
                execution_class=execution_class,
                table_limit=self.config.table_limit,
                corpus_sha_order=[
                    str(item.get("pdf_sha256") or "")
                    for item in _dicts(data.get("documents"))
                ],
                selected_document_id=str(
                    selection.get("selected_document_id") or ""
                ),
            )
        ):
            errors.append("pdf_structural_holdout_selection_contract_invalid")
        if (
            not isinstance(raw_documents, list)
            or len(documents) != len(raw_documents)
            or len(documents) != _integer_or_zero(policy.get("document_count"))
            or any(
                set(item) != _document_keys(execution_class)
                for item in documents
            )
        ):
            errors.append("pdf_structural_holdout_document_contract_invalid")
        document_ids = [str(item.get("document_id") or "") for item in documents]
        pdf_hashes = [str(item.get("pdf_sha256") or "") for item in documents]
        if (
            not all(document_ids)
            or len(document_ids) != len(set(document_ids))
            or not all(_sha256(item) for item in pdf_hashes)
            or pdf_hashes != sorted(pdf_hashes)
            or len(pdf_hashes) != len(set(pdf_hashes))
            or set(pdf_hashes) != set(policy.get("sha256") or set())
            or selection.get("corpus_sha_order") != pdf_hashes
            or any(
                not _repo_relative_path(item.get("repo_relative_path"))
                or not _document_path_matches_policy(
                    item.get("repo_relative_path"), policy
                )
                or not _positive_int(item.get("size_bytes"))
                or not _nonnegative_int(item.get("page_count"))
                or not _nonnegative_int(item.get("table_candidate_count"))
                or (
                    _is_v2_execution(execution_class)
                    and not _nonnegative_int(
                        item.get("eligible_table_candidate_count")
                    )
                )
                or (
                    _is_v2_execution(execution_class)
                    and _integer_or_zero(
                        item.get("eligible_table_candidate_count")
                    )
                    > _integer_or_zero(item.get("table_candidate_count"))
                )
                or item.get("selection_status")
                not in {
                    "not_selected_insufficient_candidates",
                    "selected",
                    "not_evaluated",
                }
                or not _nonnegative_int(item.get("prior_experiment_matches"))
                for item in documents
            )
        ):
            errors.append("pdf_structural_holdout_document_identity_invalid")
        if (
            not isinstance(raw_targets, list)
            or len(targets) != len(raw_targets)
            or len(targets) != self.config.table_limit
            or any(
                set(item)
                != _target_keys(execution_class, execution_v3=execution_v3)
                for item in targets
            )
        ):
            errors.append("pdf_structural_holdout_target_contract_invalid")
        target_ids = [str(item.get("target_id") or "") for item in targets]
        expected_target_ids = [
            f"holdout_{index:03d}"
            for index in range(1, self.config.table_limit + 1)
        ]
        target_document_ids = {
            str(item.get("document_id") or "") for item in targets
        }
        target_order = [
            (
                _integer_or_zero(item.get("page_number")),
                _integer_or_zero(item.get("parser_ordinal")),
            )
            for item in targets
        ]
        if (
            target_ids != expected_target_ids
            or len(target_document_ids) != 1
            or selection.get("selected_document_id") not in target_document_ids
            or target_order != sorted(target_order)
            or (
                _is_v5_execution(execution_class)
                and not _v5_strategy_coverage(targets)
            )
            or (
                _is_v2_execution(execution_class)
                and len(target_order) != len(set(target_order))
            )
            or any(
                not _positive_int(item.get("page_number"))
                or not _positive_int(item.get("parser_ordinal"))
                or not isinstance(item.get("parser_observation"), dict)
                or not isinstance(item.get("parser_geometry_observation"), dict)
                or not isinstance(item.get("visual_package"), dict)
                or not isinstance(item.get("private_png_base64"), str)
                or not item.get("private_png_base64")
                or (
                    _is_v2_execution(execution_class)
                    and (
                        self.validate_candidate_eligibility_observation(
                            item.get("eligibility_observation"),
                            execution_class=execution_class,
                        )
                        or _object(
                            item.get("eligibility_observation")
                        ).get("eligible")
                        is not True
                        or _object(
                            item.get("eligibility_observation")
                        ).get("page_number")
                        != item.get("page_number")
                        or _object(
                            item.get("eligibility_observation")
                        ).get("parser_ordinal")
                        != item.get("parser_ordinal")
                    )
                )
                or (
                    execution_v3
                    and self.validate_target_execution_contract(
                        parser_observation=_object(
                            item.get("parser_observation")
                        ),
                        visual_package=_object(item.get("visual_package")),
                        contract=item.get("execution_contract"),
                    )
                )
                for item in targets
            )
        ):
            errors.append("pdf_structural_holdout_target_identity_invalid")
        selected_documents = [
            item for item in documents if item.get("selection_status") == "selected"
        ]
        selected_index = (
            documents.index(selected_documents[0])
            if len(selected_documents) == 1
            else -1
        )
        if (
            len(selected_documents) != 1
            or selected_documents[0].get("document_id")
            != selection.get("selected_document_id")
            or _candidate_count_for_selection(
                selected_documents[0], execution_class
            )
            < self.config.table_limit
            or selected_index < 0
            or any(
                item.get("selection_status")
                != "not_selected_insufficient_candidates"
                or _integer_or_zero(item.get("page_count")) < 1
                or (
                    not _is_v5_execution(execution_class)
                    and _candidate_count_for_selection(
                        item, execution_class
                    )
                    >= self.config.table_limit
                )
                for item in documents[:selected_index]
            )
            or any(
                item.get("selection_status") != "not_evaluated"
                or _integer_or_zero(item.get("page_count")) != 0
                or _integer_or_zero(item.get("table_candidate_count")) != 0
                or (
                    _is_v2_execution(execution_class)
                    and _integer_or_zero(
                        item.get("eligible_table_candidate_count")
                    )
                    != 0
                )
                for item in documents[selected_index + 1 :]
            )
        ):
            errors.append("pdf_structural_holdout_selected_document_invalid")
        errors.extend(_source_freeze_errors(source))
        errors.extend(
            _freshness_scan_errors(
                freshness_scan,
                execution_class=str(data.get("execution_class") or ""),
            )
        )
        if freshness_scan.get(
            "excluded_input_inventory"
        ) != _document_input_inventory(documents):
            errors.append("pdf_structural_holdout_input_inventory_invalid")
        if _certification_eligible(execution_class) and any(
            _integer_or_zero(item.get("prior_experiment_matches")) != 0
            for item in documents
        ):
            errors.append("pdf_structural_holdout_freshness_invalid")
        document_by_id = {
            str(item.get("document_id") or ""): item for item in documents
        }
        for target in targets:
            document = _object(
                document_by_id.get(str(target.get("document_id") or ""))
            )
            parser_observation = _object(target.get("parser_observation"))
            geometry = _object(target.get("parser_geometry_observation"))
            visual = _object(target.get("visual_package"))
            eligibility = _object(target.get("eligibility_observation"))
            crop = _object(visual.get("crop_identity"))
            try:
                png_bytes = base64.b64decode(
                    str(target.get("private_png_base64") or ""), validate=True
                )
            except (ValueError, TypeError):
                png_bytes = b""
            if (
                not document
                or _integer_or_zero(document.get("page_count")) < 1
                or _integer_or_zero(target.get("page_number"))
                > _integer_or_zero(document.get("page_count"))
                or parser_observation.get("pdf_sha256")
                != document.get("pdf_sha256")
                or geometry.get("pdf_sha256") != document.get("pdf_sha256")
                or visual.get("pdf_sha256") != document.get("pdf_sha256")
                or parser_observation.get("page_number")
                != target.get("page_number")
                or geometry.get("page_number") != target.get("page_number")
                or visual.get("page_number") != target.get("page_number")
                or len(
                    {
                        parser_observation.get("document_ref"),
                        geometry.get("document_ref"),
                        visual.get("document_ref"),
                    }
                )
                != 1
                or len(
                    {
                        parser_observation.get("page_ref"),
                        geometry.get("page_ref"),
                        visual.get("page_ref"),
                    }
                )
                != 1
                or len(
                    {
                        parser_observation.get("table_ref"),
                        geometry.get("table_ref"),
                        visual.get("table_ref"),
                    }
                )
                != 1
                or visual.get("parser_observation_checksum")
                != parser_observation.get("observation_checksum")
                or crop.get("dpi") != self.config.dpi
                or not png_bytes
                or crop.get("png_bytes") != len(png_bytes)
                or crop.get("crop_sha256")
                != hashlib.sha256(png_bytes).hexdigest()
                or (
                    _is_v2_execution(execution_class)
                    and (
                        eligibility.get("page_ref")
                        != parser_observation.get("page_ref")
                        or eligibility.get("page_number")
                        != parser_observation.get("page_number")
                        or eligibility.get("table_candidate_ref")
                        != parser_observation.get("table_ref")
                    )
                )
            ):
                errors.append("pdf_structural_holdout_target_lineage_invalid")
                break
        expected_holdout_id = self._expected_holdout_id(
            documents=documents,
            targets=targets,
            frozen_source=source,
            freshness_scan=freshness_scan,
            execution_class=str(data.get("execution_class") or ""),
        )
        if data.get("holdout_id") != expected_holdout_id:
            errors.append("pdf_structural_holdout_id_invalid")
        if data.get("reference_boundary") != _REFERENCE_BOUNDARY:
            errors.append("pdf_structural_holdout_reference_boundary_invalid")
        if data.get("provider_calls_started") is not False:
            errors.append("pdf_structural_holdout_provider_call_boundary_invalid")
        unsigned = dict(data)
        stored_checksum = unsigned.pop("payload_checksum", None)
        if stored_checksum != sha256_json(unsigned):
            errors.append("pdf_structural_holdout_preregistration_checksum_invalid")
        return sorted(set(errors))

    def terminal_seal(
        self,
        *,
        preregistration_file_sha256: str,
        source_freeze: dict[str, Any],
        execution_class: str,
        certification_eligible: bool,
        corpus_policy: str,
        provider_qualification: dict[str, Any],
        provider_config: dict[str, Any],
        journal: list[dict[str, Any]],
        targets: dict[str, Any],
        new_provider_generate_calls: int,
        reference_process_started: bool,
        new_provider_count_token_calls: int | None = None,
        expected_provider_count_token_calls: int | None = None,
        expected_provider_generate_calls: int | None = None,
    ) -> dict[str, Any]:
        if (
            execution_class not in PDF_STRUCTURAL_HOLDOUT_EXECUTION_CLASSES
            or certification_eligible is not _certification_eligible(
                execution_class
            )
            or corpus_policy
            != _corpus_policy(execution_class).get("policy_id")
            or not isinstance(provider_qualification, dict)
            or not isinstance(provider_config, dict)
            or not isinstance(journal, list)
            or len(_dicts(journal)) != len(journal)
            or not _nonnegative_int(new_provider_generate_calls)
            or not isinstance(reference_process_started, bool)
            or (
                new_provider_count_token_calls is not None
                and not _nonnegative_int(new_provider_count_token_calls)
            )
            or (
                expected_provider_count_token_calls is not None
                and not _positive_int(expected_provider_count_token_calls)
            )
            or (
                expected_provider_generate_calls is not None
                and not _positive_int(expected_provider_generate_calls)
            )
        ):
            raise PdfStructuralRepairHoldoutContractError(
                "pdf_structural_holdout_terminal_seal_accounting_invalid"
            )
        target_seals: dict[str, dict[str, Any]] = {}
        for target_id in sorted(targets):
            target = _object(targets.get(target_id))
            consensus = _object(target.get("consensus_result"))
            assemblies = target.get("assemblies")
            if (
                not isinstance(assemblies, list)
                or len(_dicts(assemblies)) != len(assemblies)
            ):
                raise PdfStructuralRepairHoldoutContractError(
                    "pdf_structural_holdout_terminal_assemblies_invalid",
                    target_id,
                )
            target_seals[target_id] = {
                "terminal_status": consensus.get("terminal_status"),
                "result_checksum": consensus.get("result_checksum"),
                "parser_observation_sha256": sha256_json(
                    target.get("parser_observation")
                ),
                "parser_geometry_observation_sha256": sha256_json(
                    target.get("parser_geometry_observation")
                ),
                "visual_package_sha256": sha256_json(
                    target.get("visual_package")
                ),
                "assembly_result_sha256s": [
                    sha256_json(item) for item in assemblies
                ],
                "hypothesis_set_sha256": sha256_json(
                    target.get("hypothesis_set")
                ),
                "repeatability_sha256": sha256_json(
                    target.get("repeatability")
                ),
                "consensus_result_sha256": sha256_json(consensus),
                "accepted_binding_sha256": (
                    sha256_json(target.get("accepted_binding"))
                    if isinstance(target.get("accepted_binding"), dict)
                    else None
                ),
                "materialization_sha256": (
                    sha256_json(target.get("materialization"))
                    if isinstance(target.get("materialization"), dict)
                    else None
                ),
            }
            if _is_v2_execution(execution_class):
                target_seals[target_id]["eligibility_observation_sha256"] = (
                    sha256_json(target.get("eligibility_observation"))
                )
            if isinstance(target.get("execution_contract"), dict):
                target_seals[target_id].update(
                    {
                        "execution_contract_sha256": sha256_json(
                            target.get("execution_contract")
                        ),
                        "window_stitches_sha256": sha256_json(
                            target.get("window_stitches")
                        ),
                        "window_runtime_result_checksum": target.get(
                            "window_runtime_result_checksum"
                        ),
                    }
                )
        result = {
            "preregistration_file_sha256": preregistration_file_sha256,
            "execution_class": execution_class,
            "certification_eligible": certification_eligible,
            "corpus_policy": corpus_policy,
            "source_inventory_checksum": source_freeze.get(
                "inventory_checksum"
            ),
            "provider_qualification_sha256": sha256_json(
                provider_qualification
            ),
            "provider_config_sha256": sha256_json(provider_config),
            "journal_sha256": sha256_json(journal),
            "new_provider_generate_calls": new_provider_generate_calls,
            "reference_process_started": reference_process_started,
            "targets": target_seals,
        }
        if new_provider_count_token_calls is not None:
            result.update(
                {
                    "new_provider_count_token_calls": (
                        new_provider_count_token_calls
                    ),
                    "expected_provider_count_token_calls": (
                        expected_provider_count_token_calls
                    ),
                    "expected_provider_generate_calls": (
                        expected_provider_generate_calls
                    ),
                }
            )
        return result

    def validate_terminal(self, value: Any) -> list[str]:
        data = _object(value)
        errors: list[str] = []
        execution_class = str(data.get("execution_class") or "")
        execution_v3 = (
            data.get("schema_version")
            == PDF_STRUCTURAL_HOLDOUT_TERMINAL_SCHEMA_V3
        )
        if set(data) != (_TERMINAL_KEYS_V3 if execution_v3 else _TERMINAL_KEYS):
            errors.append("pdf_structural_holdout_terminal_keys_invalid")
        if (
            data.get("schema_version")
            not in {
                _terminal_schema(execution_class),
                PDF_STRUCTURAL_HOLDOUT_TERMINAL_SCHEMA_V3,
            }
            or data.get("policy_version") != _policy_version(execution_class)
            or not str(data.get("holdout_id") or "").startswith("pdfholdout_")
            or data.get("execution_class")
            not in PDF_STRUCTURAL_HOLDOUT_EXECUTION_CLASSES
            or data.get("certification_eligible")
            is not _certification_eligible(execution_class)
            or data.get("corpus_policy")
            != _corpus_policy(str(data.get("execution_class") or "")).get(
                "policy_id"
            )
            or not _sha256(data.get("preregistration_file_sha256"))
            or data.get("reference_process_started") is not False
        ):
            errors.append("pdf_structural_holdout_terminal_identity_invalid")
        targets = _object(data.get("targets"))
        expected_ids = {
            f"holdout_{index:03d}"
            for index in range(1, self.config.table_limit + 1)
        }
        if set(targets) != expected_ids:
            errors.append("pdf_structural_holdout_terminal_target_set_invalid")
        for target_id in expected_ids:
            target = _object(targets.get(target_id))
            scope = _object(target.get("scope"))
            if (
                set(target)
                != _terminal_target_keys(
                    execution_class, execution_v3=execution_v3
                )
                or set(scope) != _TERMINAL_SCOPE_KEYS
                or scope.get("target_id") != target_id
                or not isinstance(scope.get("document_id"), str)
                or not scope.get("document_id")
                or not _positive_int(scope.get("page_number"))
                or not _positive_int(scope.get("parser_ordinal"))
                or not isinstance(target.get("parser_observation"), dict)
                or not isinstance(target.get("parser_geometry_observation"), dict)
                or not isinstance(target.get("visual_package"), dict)
                or not isinstance(target.get("assemblies"), list)
                or len(_dicts(target.get("assemblies")))
                != len(target.get("assemblies") or [])
                or not isinstance(target.get("hypothesis_set"), dict)
                or not isinstance(target.get("repeatability"), dict)
                or not isinstance(target.get("consensus_result"), dict)
                or (
                    _is_v5_execution(execution_class)
                    and not _v5_strategy_coverage(
                        list(_object(targets).values())
                    )
                )
                or (
                    _is_v2_execution(execution_class)
                    and (
                        self.validate_candidate_eligibility_observation(
                            target.get("eligibility_observation"),
                            execution_class=execution_class,
                        )
                        or _object(
                            target.get("eligibility_observation")
                        ).get("eligible")
                        is not True
                        or _object(
                            target.get("eligibility_observation")
                        ).get("page_number")
                        != scope.get("page_number")
                        or _object(
                            target.get("eligibility_observation")
                        ).get("parser_ordinal")
                        != scope.get("parser_ordinal")
                    )
                )
                or (
                    execution_v3
                    and self.validate_target_execution_contract(
                        parser_observation=_object(
                            target.get("parser_observation")
                        ),
                        visual_package=_object(target.get("visual_package")),
                        contract=target.get("execution_contract"),
                    )
                )
                or (
                    execution_v3
                    and not isinstance(target.get("window_stitches"), list)
                )
                or (
                    execution_v3
                    and not isinstance(
                        target.get("window_runtime_result_checksum"),
                        (str, type(None)),
                    )
                )
            ):
                errors.append("pdf_structural_holdout_terminal_target_invalid")
                break
            terminal_status = _object(target.get("consensus_result")).get(
                "terminal_status"
            )
            if (
                terminal_status == "accepted_supplied_consensus"
                and (
                    not isinstance(target.get("accepted_binding"), dict)
                    or not isinstance(target.get("materialization"), dict)
                )
            ) or (
                terminal_status != "accepted_supplied_consensus"
                and (
                    target.get("accepted_binding") is not None
                    or target.get("materialization") is not None
                )
            ):
                errors.append(
                    "pdf_structural_holdout_terminal_materialization_boundary_invalid"
                )
                break
        journal = data.get("journal")
        journal_items = _dicts(journal)
        performed_calls = sum(
            item.get("provider_generate_call_performed") is True
            for item in journal_items
        )
        if execution_v3:
            errors.extend(
                _execution_terminal_journal_errors(
                    journal=journal,
                    journal_items=journal_items,
                    targets=targets,
                    expected_target_ids=sorted(expected_ids),
                    holdout_id=str(data.get("holdout_id") or ""),
                    provider_config=_object(data.get("provider_config")),
                    provider_profile=self.config.provider_profile,
                    model_id=self.config.model_id,
                    maximum_counted_input_tokens=(
                        self.config.maximum_counted_input_tokens
                    ),
                    maximum_output_tokens=self.config.maximum_output_tokens,
                    attempts_per_target=self.config.attempts_per_target,
                    new_provider_count_token_calls=data.get(
                        "new_provider_count_token_calls"
                    ),
                    new_provider_generate_calls=data.get(
                        "new_provider_generate_calls"
                    ),
                    expected_provider_count_token_calls=data.get(
                        "expected_provider_count_token_calls"
                    ),
                    expected_provider_generate_calls=data.get(
                        "expected_provider_generate_calls"
                    ),
                )
            )
        else:
            expected_pairs = [
                (f"holdout_{target:03d}", attempt)
                for target in range(1, self.config.table_limit + 1)
                for attempt in range(1, self.config.attempts_per_target + 1)
            ]
            actual_pairs = [
                (
                    str(item.get("target_id") or ""),
                    _integer_or_zero(item.get("attempt_number")),
                )
                for item in journal_items
            ]
            if (
                not isinstance(journal, list)
                or len(journal)
                != self.config.table_limit * self.config.attempts_per_target
                or len(journal_items) != len(journal)
                or any(set(item) != _JOURNAL_KEYS for item in journal_items)
                or actual_pairs != expected_pairs
                or any(
                    item.get("schema_version")
                    != PDF_STRUCTURAL_HOLDOUT_JOURNAL_SCHEMA
                    or not str(item.get("task_id") or "").startswith(
                        "pdfvisualtopotask_"
                    )
                    or item.get("job_key")
                    != f"{item.get('task_id')}|a{item.get('attempt_number')}"
                    or not _sha256(item.get("evidence_revision"))
                    or not _sha256(item.get("provider_config_hash"))
                    or not isinstance(item.get("count_tokens"), dict)
                    or not isinstance(item.get("provider_attempt"), dict)
                    or not isinstance(item.get("provider_result"), dict)
                    or not isinstance(
                        item.get("topology_response"), (dict, type(None))
                    )
                    or not isinstance(
                        item.get("assembly"), (dict, type(None))
                    )
                    or not isinstance(
                        item.get("provider_generate_call_performed"), bool
                    )
                    or _object(item.get("provider_attempt")).get(
                        "hidden_retry"
                    )
                    is True
                    or _object(item.get("provider_attempt")).get(
                        "provider_failover"
                    )
                    is True
                    for item in journal_items
                )
                or any(
                    _journal_entry_errors(
                        item,
                        target=_object(
                            targets.get(str(item.get("target_id") or ""))
                        ),
                        holdout_id=str(data.get("holdout_id") or ""),
                        provider_config_hash=sha256_json(
                            _object(data.get("provider_config"))
                        ),
                        provider_profile=self.config.provider_profile,
                        model_id=self.config.model_id,
                        maximum_counted_input_tokens=(
                            self.config.maximum_counted_input_tokens
                        ),
                        maximum_output_tokens=self.config.maximum_output_tokens,
                    )
                    for item in journal_items
                )
                or not _journal_lineage_is_closed(journal_items)
                or not _nonnegative_int(
                    data.get("new_provider_generate_calls")
                )
                or _integer_or_zero(data.get("new_provider_generate_calls"))
                > self.config.table_limit * self.config.attempts_per_target
                or data.get("new_provider_generate_calls") != performed_calls
            ):
                errors.append(
                    "pdf_structural_holdout_terminal_journal_invalid"
                )
        source_freeze = _object(data.get("source_freeze"))
        errors.extend(_source_freeze_errors(source_freeze))
        provider_config = _object(data.get("provider_config"))
        qualification = _object(data.get("provider_qualification"))
        if (
            set(provider_config) != _PROVIDER_CONFIG_KEYS
            or provider_config.get("provider_profile")
            != self.config.provider_profile
            or provider_config.get("model_id") != self.config.model_id
            or provider_config.get("timeout_seconds") != 240
            or provider_config.get("maximum_counted_input_tokens")
            != self.config.maximum_counted_input_tokens
            or provider_config.get("maximum_output_tokens")
            != self.config.maximum_output_tokens
            or provider_config.get("thinking_level") != "minimal"
            or set(qualification) != _QUALIFICATION_KEYS
            or qualification.get("status") != "qualified"
            or qualification.get("provider_profile")
            != self.config.provider_profile
            or not isinstance(
                qualification.get("provider_profile_revision"), str
            )
            or not qualification.get("provider_profile_revision")
            or qualification.get("requested_model_id") != self.config.model_id
            or qualification.get("resolved_model_id") != self.config.model_id
            or qualification.get("exact_model_match") is not True
            or qualification.get("image_input_supported") is not True
            or qualification.get("structured_output_supported") is not True
            or qualification.get("native_provider_transport") is not True
            or qualification.get("credentials_from_openwebui_connection")
            is not True
            or qualification.get("hidden_retry") is not False
            or qualification.get("provider_failover") is not False
            or not _positive_int(qualification.get("maximum_output_tokens"))
            or _integer_or_zero(qualification.get("maximum_output_tokens"))
            < self.config.maximum_output_tokens
            or not _positive_int(qualification.get("maximum_input_tokens"))
            or _integer_or_zero(qualification.get("maximum_input_tokens"))
            < self.config.maximum_counted_input_tokens
            or qualification.get("http_status") != 200
            or not _sha256(qualification.get("response_hash"))
        ):
            errors.append("pdf_structural_holdout_terminal_provider_invalid")
        expected_provider_config_hash = sha256_json(provider_config)
        expected_window_provider_config_hash = _window_provider_config_hash(
            provider_profile=self.config.provider_profile,
            model_id=self.config.model_id,
            maximum_counted_input_tokens=(
                self.config.maximum_counted_input_tokens
            ),
            maximum_output_tokens=self.config.maximum_output_tokens,
        )
        if any(
            item.get("provider_config_hash")
            != (
                expected_window_provider_config_hash
                if execution_v3
                and item.get("schema_version")
                == PDF_STRUCTURAL_HOLDOUT_WINDOW_JOURNAL_SCHEMA
                else expected_provider_config_hash
            )
            for item in journal_items
        ):
            errors.append("pdf_structural_holdout_terminal_provider_hash_invalid")
        try:
            expected_seal = self.terminal_seal(
                preregistration_file_sha256=str(
                    data.get("preregistration_file_sha256") or ""
                ),
                source_freeze=source_freeze,
                execution_class=str(data.get("execution_class") or ""),
                certification_eligible=(
                    data.get("certification_eligible") is True
                ),
                corpus_policy=str(data.get("corpus_policy") or ""),
                provider_qualification=qualification,
                provider_config=provider_config,
                journal=journal_items,
                targets=targets,
                new_provider_generate_calls=_integer_or_zero(
                    data.get("new_provider_generate_calls")
                ),
                new_provider_count_token_calls=(
                    _integer_or_zero(
                        data.get("new_provider_count_token_calls")
                    )
                    if execution_v3
                    else None
                ),
                expected_provider_count_token_calls=(
                    _integer_or_zero(
                        data.get("expected_provider_count_token_calls")
                    )
                    if execution_v3
                    else None
                ),
                expected_provider_generate_calls=(
                    _integer_or_zero(
                        data.get("expected_provider_generate_calls")
                    )
                    if execution_v3
                    else None
                ),
                reference_process_started=(
                    data.get("reference_process_started") is True
                ),
            )
        except PdfStructuralRepairHoldoutContractError:
            expected_seal = {}
            errors.append("pdf_structural_holdout_terminal_seal_input_invalid")
        if (
            data.get("terminal_seal") != expected_seal
            or data.get("terminal_seal_hash") != sha256_json(expected_seal)
        ):
            errors.append("pdf_structural_holdout_terminal_seal_invalid")
        unsigned = dict(data)
        stored_checksum = unsigned.pop("artifact_checksum", None)
        if stored_checksum != sha256_json(unsigned):
            errors.append("pdf_structural_holdout_terminal_checksum_invalid")
        return sorted(set(errors))

    def validate_terminal_against_preregistration(
        self,
        *,
        terminal: Any,
        preregistration: Any,
        preregistration_file_sha256: str,
    ) -> list[str]:
        errors = self.validate_preregistration(preregistration)
        errors.extend(self.validate_terminal(terminal))
        prereg = _object(preregistration)
        result = _object(terminal)
        if (
            not _sha256(preregistration_file_sha256)
            or result.get("preregistration_file_sha256")
            != preregistration_file_sha256
            or result.get("holdout_id") != prereg.get("holdout_id")
            or result.get("source_freeze") != prereg.get("frozen_source")
            or result.get("execution_class") != prereg.get("execution_class")
            or result.get("certification_eligible")
            is not prereg.get("certification_eligible")
            or result.get("corpus_policy") != prereg.get("corpus_policy")
        ):
            errors.append("pdf_structural_holdout_terminal_preregistration_mismatch")
        prereg_targets = {
            str(item.get("target_id") or ""): item
            for item in _dicts(prereg.get("targets"))
        }
        terminal_targets = _object(result.get("targets"))
        journal = _dicts(result.get("journal"))
        for target_id in sorted(prereg_targets):
            frozen_target = _object(prereg_targets.get(target_id))
            terminal_target = _object(terminal_targets.get(target_id))
            scope = _object(terminal_target.get("scope"))
            matching_entries = [
                item for item in journal if item.get("target_id") == target_id
            ]
            journal_assemblies = [
                item.get("assembly")
                for item in matching_entries
                if isinstance(item.get("assembly"), dict)
            ]
            if (
                scope
                != {
                    "target_id": target_id,
                    "document_id": frozen_target.get("document_id"),
                    "page_number": frozen_target.get("page_number"),
                    "parser_ordinal": frozen_target.get("parser_ordinal"),
                }
                or terminal_target.get("parser_observation")
                != frozen_target.get("parser_observation")
                or terminal_target.get("parser_geometry_observation")
                != frozen_target.get("parser_geometry_observation")
                or terminal_target.get("visual_package")
                != frozen_target.get("visual_package")
                or (
                    prereg.get("schema_version")
                    == PDF_STRUCTURAL_HOLDOUT_PREREGISTRATION_SCHEMA_V3
                    and terminal_target.get("execution_contract")
                    != frozen_target.get("execution_contract")
                )
                or (
                    _is_v2_execution(
                        str(prereg.get("execution_class") or "")
                    )
                    and terminal_target.get("eligibility_observation")
                    != frozen_target.get("eligibility_observation")
                )
                or terminal_target.get("assemblies") != journal_assemblies
            ):
                errors.append(
                    "pdf_structural_holdout_terminal_target_preregistration_mismatch"
                )
                break
        return sorted(set(errors))


def _is_v2_execution(execution_class: str) -> bool:
    return execution_class in {
        "fresh_holdout_v2",
        "fresh_holdout_v3",
        "fresh_holdout_v4",
        "fresh_holdout_v5",
    }


def _is_v5_execution(execution_class: str) -> bool:
    return execution_class == "fresh_holdout_v5"


def _certification_eligible(execution_class: str) -> bool:
    return execution_class in PDF_STRUCTURAL_HOLDOUT_CERTIFICATION_CLASSES


def _policy_version(execution_class: str) -> str:
    return (
        PDF_STRUCTURAL_HOLDOUT_POLICY_VERSION_V2
        if _is_v2_execution(execution_class)
        else PDF_STRUCTURAL_HOLDOUT_POLICY_VERSION
    )


def _preregistration_schema(execution_class: str) -> str:
    return (
        PDF_STRUCTURAL_HOLDOUT_PREREGISTRATION_SCHEMA_V2
        if _is_v2_execution(execution_class)
        else PDF_STRUCTURAL_HOLDOUT_PREREGISTRATION_SCHEMA
    )


def _preflight_schema(execution_class: str) -> str:
    return (
        PDF_STRUCTURAL_HOLDOUT_PREFLIGHT_TERMINAL_SCHEMA_V2
        if _is_v2_execution(execution_class)
        else PDF_STRUCTURAL_HOLDOUT_PREFLIGHT_TERMINAL_SCHEMA
    )


def _terminal_schema(execution_class: str) -> str:
    return (
        PDF_STRUCTURAL_HOLDOUT_TERMINAL_SCHEMA_V2
        if _is_v2_execution(execution_class)
        else PDF_STRUCTURAL_HOLDOUT_TERMINAL_SCHEMA
    )


def _document_keys(execution_class: str) -> set[str]:
    return _DOCUMENT_KEYS_V2 if _is_v2_execution(execution_class) else _DOCUMENT_KEYS


def _target_keys(
    execution_class: str, *, execution_v3: bool = False
) -> set[str]:
    result = _TARGET_KEYS_V2 if _is_v2_execution(execution_class) else _TARGET_KEYS
    return result | {"execution_contract"} if execution_v3 else result


def _terminal_target_keys(
    execution_class: str, *, execution_v3: bool = False
) -> set[str]:
    result = (
        _TERMINAL_TARGET_KEYS_V2
        if _is_v2_execution(execution_class)
        else _TERMINAL_TARGET_KEYS
    )
    return result | _TERMINAL_EXECUTION_KEYS if execution_v3 else result


def _preflight_scope_keys(execution_class: str) -> set[str]:
    return (
        _PREFLIGHT_SCOPE_KEYS_V2
        if _is_v2_execution(execution_class)
        else _TERMINAL_SCOPE_KEYS
    )


def _selection_keys(execution_class: str) -> set[str]:
    return _SELECTION_KEYS_V2 if _is_v2_execution(execution_class) else _SELECTION_KEYS


def _selection_contract(
    *,
    execution_class: str,
    table_limit: int,
    corpus_sha_order: list[str],
    selected_document_id: str,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "rule": (
            _SELECTION_RULE_V5
            if _is_v5_execution(execution_class)
            else (
                _SELECTION_RULE_V2
                if _is_v2_execution(execution_class)
                else _SELECTION_RULE
            )
        ),
        "table_limit": table_limit,
        "corpus_sha_order": list(corpus_sha_order),
        "selected_document_id": selected_document_id,
    }
    if _is_v2_execution(execution_class):
        result.update(
            {
                "eligibility_policy": copy.deepcopy(
                    _eligibility_policy(execution_class)
                ),
                "eligibility_policy_checksum": _eligibility_policy_checksum(
                    execution_class
                ),
            }
        )
    return result


def _candidate_count_for_selection(
    document: dict[str, Any], execution_class: str
) -> int:
    key = (
        "eligible_table_candidate_count"
        if _is_v2_execution(execution_class)
        else "table_candidate_count"
    )
    return _integer_or_zero(document.get(key))


def _candidate_eligibility_reason_codes(
    value: dict[str, Any], *, policy: dict[str, Any]
) -> list[str]:
    reasons: list[str] = []
    rows = _integer_or_zero(value.get("rows_total"))
    columns = _integer_or_zero(value.get("columns_total"))
    cells = _integer_or_zero(value.get("cells_total"))
    populated = _integer_or_zero(value.get("populated_cells_total"))
    if (
        value.get("candidate_state") != "candidate"
        or not str(value.get("page_ref") or "")
        or not _positive_int(value.get("page_number"))
        or not _positive_int(value.get("parser_ordinal"))
        or not str(value.get("table_candidate_ref") or "")
    ):
        reasons.append("pdf_structural_holdout_candidate_state_invalid")
    if value.get("table_strategy_ref") not in policy["allowed_table_strategy_refs"]:
        reasons.append("pdf_structural_holdout_candidate_strategy_unsupported")
    strategy = str(value.get("table_strategy_ref") or "")
    strategy_requirements = _object(
        _object(policy.get("strategy_requirements")).get(strategy)
    )
    minimum_geometry_confidence = float(
        strategy_requirements.get(
            "minimum_geometry_confidence",
            policy["minimum_geometry_confidence"],
        )
    )
    minimum_ruling_evidence = int(
        strategy_requirements.get(
            "minimum_ruling_evidence",
            policy["minimum_ruling_evidence"],
        )
    )
    if (
        _finite_number(value.get("geometry_confidence"))
        < minimum_geometry_confidence
    ):
        reasons.append("pdf_structural_holdout_candidate_confidence_below_threshold")
    if not int(policy["minimum_rows"]) <= rows <= int(policy["maximum_rows"]):
        reasons.append("pdf_structural_holdout_candidate_row_extent_unsupported")
    if not int(policy["minimum_columns"]) <= columns <= int(
        policy["maximum_columns"]
    ):
        reasons.append("pdf_structural_holdout_candidate_column_extent_unsupported")
    width_ratio = _finite_number(value.get("bbox_width_ratio"))
    height_ratio = _finite_number(value.get("bbox_height_ratio"))
    area_ratio = _finite_number(value.get("bbox_area_ratio"))
    if not float(policy["minimum_bbox_width_ratio"]) <= width_ratio <= float(
        policy["maximum_bbox_width_ratio"]
    ):
        reasons.append("pdf_structural_holdout_candidate_page_width_extent_unsupported")
    if not float(policy["minimum_bbox_height_ratio"]) <= height_ratio <= float(
        policy["maximum_bbox_height_ratio"]
    ):
        reasons.append("pdf_structural_holdout_candidate_multi_region_height_rejected")
    if area_ratio > float(policy["maximum_bbox_area_ratio"]):
        reasons.append("pdf_structural_holdout_candidate_page_wide_area_rejected")
    if cells < 1 or cells > rows * columns:
        reasons.append("pdf_structural_holdout_candidate_cell_accounting_invalid")
    if (
        populated < int(policy["minimum_populated_cells"])
        or _finite_number(value.get("populated_cell_ratio"))
        < float(policy["minimum_populated_cell_ratio"])
    ):
        reasons.append("pdf_structural_holdout_candidate_structural_signal_sparse")
    if (
        _integer_or_zero(value.get("active_rows_total")) != rows
        or _integer_or_zero(value.get("active_columns_total")) != columns
    ):
        reasons.append("pdf_structural_holdout_candidate_multi_region_coverage_rejected")
    if (
        _integer_or_zero(value.get("contributing_words_total")) < 1
        or _integer_or_zero(value.get("accounted_words_total"))
        != _integer_or_zero(value.get("contributing_words_total"))
        or _integer_or_zero(value.get("duplicate_accounted_words_total")) != 0
        or _integer_or_zero(value.get("unaccounted_words_total")) != 0
    ):
        reasons.append("pdf_structural_holdout_candidate_word_accounting_invalid")
    if (
        _integer_or_zero(value.get("ruling_evidence_total"))
        < minimum_ruling_evidence
    ):
        reasons.append("pdf_structural_holdout_candidate_ruling_signal_insufficient")
    return sorted(set(reasons))


def _eligibility_policy(execution_class: str) -> dict[str, Any]:
    return (
        PDF_STRUCTURAL_HOLDOUT_ELIGIBILITY_POLICY_V5
        if _is_v5_execution(execution_class)
        else PDF_STRUCTURAL_HOLDOUT_ELIGIBILITY_POLICY
    )


def _eligibility_policy_checksum(execution_class: str) -> str:
    return (
        PDF_STRUCTURAL_HOLDOUT_ELIGIBILITY_POLICY_V5_CHECKSUM
        if _is_v5_execution(execution_class)
        else PDF_STRUCTURAL_HOLDOUT_ELIGIBILITY_POLICY_CHECKSUM
    )


def _v5_strategy_coverage(items: list[Any]) -> bool:
    strategies = {
        str(
            _object(_object(item).get("eligibility_observation")).get(
                "table_strategy_ref"
            )
            or ""
        )
        for item in items
    }
    return {"aligned_text_v0", "ruled_lines_v0"}.issubset(strategies)


def _finite_number(value: Any) -> float:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        rendered = float(value)
        if math.isfinite(rendered):
            return rendered
    return 0.0


def _finite_nonnegative_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
        and float(value) >= 0.0
    )


def _normalized_bbox(value: Any) -> list[float] | None:
    if (
        not isinstance(value, list)
        or len(value) != 4
        or any(
            not isinstance(item, (int, float))
            or isinstance(item, bool)
            or not math.isfinite(float(item))
            for item in value
        )
    ):
        return None
    result = [float(item) for item in value]
    if result[0] >= result[2] or result[1] >= result[3]:
        return None
    return result


def _strings(value: Any) -> list[str]:
    return (
        [item for item in value if isinstance(item, str) and item]
        if isinstance(value, list)
        else []
    )


def _repo_relative_path(value: Any) -> bool:
    if not isinstance(value, str) or not value or value.startswith(("/", "\\")):
        return False
    rendered = value.replace("\\", "/")
    return ":" not in rendered and ".." not in rendered.split("/")


def _sha256(value: Any) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    return all(character in "0123456789abcdef" for character in value)


def _positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _nonnegative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _integer_or_zero(value: Any) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _dicts(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _source_freeze_errors(value: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if set(value) != _SOURCE_KEYS:
        errors.append("pdf_structural_holdout_source_freeze_keys_invalid")
    raw_inventory = value.get("inventory")
    inventory = _dicts(raw_inventory)
    paths = [str(item.get("repo_relative_path") or "") for item in inventory]
    if (
        not isinstance(raw_inventory, list)
        or len(inventory) != len(raw_inventory)
        or not _git_revision_hash(value.get("git_revision"))
        or not inventory
        or any(set(item) != _SOURCE_ITEM_KEYS for item in inventory)
        or paths != sorted(paths)
        or len(paths) != len(set(paths))
        or any(
            not _repo_relative_path(item.get("repo_relative_path"))
            or not _nonnegative_int(item.get("size_bytes"))
            or not _sha256(item.get("sha256"))
            for item in inventory
        )
        or value.get("inventory_checksum") != sha256_json(inventory)
    ):
        errors.append("pdf_structural_holdout_source_freeze_invalid")
    return errors


def _freshness_scan_errors(
    value: dict[str, Any], *, execution_class: str
) -> list[str]:
    errors: list[str] = []
    if set(value) != _FRESHNESS_KEYS:
        errors.append("pdf_structural_holdout_freshness_scan_keys_invalid")
    root = value.get("root_repo_relative_path")
    excluded = value.get("excluded_repo_relative_root")
    raw_excluded_inputs = value.get("excluded_input_inventory")
    excluded_inputs = _dicts(raw_excluded_inputs)
    policy = _corpus_policy(execution_class)
    raw_roots = value.get("experiment_roots")
    raw_inventory = value.get("inventory")
    roots = (
        [item for item in raw_roots if isinstance(item, str)]
        if isinstance(raw_roots, list)
        else []
    )
    inventory = _dicts(raw_inventory)
    paths = [str(item.get("repo_relative_path") or "") for item in inventory]
    root_prefix = "local/stage2/"
    if (
        value.get("schema_version") != PDF_STRUCTURAL_HOLDOUT_FRESHNESS_SCHEMA
        or root != "local/stage2"
        or not isinstance(excluded, str)
        or not _repo_relative_path(excluded)
        or not excluded.startswith(root_prefix)
        or not isinstance(raw_roots, list)
        or len(roots) != len(raw_roots)
        or roots != sorted(roots)
        or len(roots) != len(set(roots))
        or any(
            not _repo_relative_path(item)
            or not item.startswith(root_prefix)
            or "/" in item[len(root_prefix) :]
            or not item[len(root_prefix) :].startswith(
                ("broker_reports_pdf", "broker_reports_direct_pdf")
            )
            or item == excluded
            for item in roots
        )
        or not isinstance(raw_excluded_inputs, list)
        or len(excluded_inputs) != len(raw_excluded_inputs)
        or len(excluded_inputs) != _integer_or_zero(policy.get("document_count"))
        or any(set(item) != _SOURCE_ITEM_KEYS for item in excluded_inputs)
        or [
            str(item.get("repo_relative_path") or "")
            for item in excluded_inputs
        ]
        != sorted(
            str(item.get("repo_relative_path") or "")
            for item in excluded_inputs
        )
        or len(
            {
                str(item.get("repo_relative_path") or "")
                for item in excluded_inputs
            }
        )
        != len(excluded_inputs)
        or {
            str(item.get("sha256") or "") for item in excluded_inputs
        }
        != set(policy.get("sha256") or set())
        or any(
            not _document_path_matches_policy(
                item.get("repo_relative_path"), policy
            )
            or not _positive_int(item.get("size_bytes"))
            or not _sha256(item.get("sha256"))
            for item in excluded_inputs
        )
        or not isinstance(raw_inventory, list)
        or len(inventory) != len(raw_inventory)
        or any(set(item) != _SOURCE_ITEM_KEYS for item in inventory)
        or paths != sorted(paths)
        or len(paths) != len(set(paths))
        or any(
            not _repo_relative_path(item.get("repo_relative_path"))
            or not _nonnegative_int(item.get("size_bytes"))
            or not _sha256(item.get("sha256"))
            or not any(
                str(item.get("repo_relative_path") or "")
                .startswith(experiment_root + "/")
                for experiment_root in roots
            )
            for item in inventory
        )
        or value.get("inventory_checksum")
        != sha256_json(
            {
                "excluded_input_inventory": excluded_inputs,
                "experiment_roots": roots,
                "inventory": inventory,
            }
        )
    ):
        errors.append("pdf_structural_holdout_freshness_scan_invalid")
    return errors


def _corpus_policy(execution_class: str) -> dict[str, Any]:
    value = PDF_STRUCTURAL_HOLDOUT_CORPUS_POLICIES.get(execution_class)
    return value if isinstance(value, dict) else {}


def _document_path_matches_policy(
    value: Any, policy: dict[str, Any]
) -> bool:
    if not _repo_relative_path(value):
        return False
    required_root = policy.get("repo_relative_root")
    return bool(
        required_root is None
        or (
            isinstance(required_root, str)
            and str(value).startswith(required_root + "/")
        )
    )


def _document_input_inventory(
    documents: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return sorted(
        [
            {
                "repo_relative_path": item.get("repo_relative_path"),
                "size_bytes": item.get("size_bytes"),
                "sha256": item.get("pdf_sha256"),
            }
            for item in documents
        ],
        key=lambda item: str(item.get("repo_relative_path") or ""),
    )


def _count_tokens_errors(
    value: dict[str, Any],
    *,
    model_id: str,
    maximum_counted_input_tokens: int,
) -> list[str]:
    prompt_details = value.get("prompt_tokens_details")
    details = _dicts(prompt_details)
    if (
        set(value) != _COUNT_TOKENS_KEYS
        or not _nonnegative_int(value.get("total_tokens"))
        or _integer_or_zero(value.get("total_tokens"))
        > maximum_counted_input_tokens
        or not isinstance(prompt_details, list)
        or len(details) != len(prompt_details)
        or value.get("http_status") != 200
        or not _sha256(value.get("request_hash"))
        or not _sha256(value.get("response_hash"))
        or not _sha256(value.get("canonical_schema_hash"))
        or not _sha256(value.get("adapted_schema_hash"))
        or not _nonnegative_int(value.get("schema_transform_count"))
        or value.get("model_requested") != model_id
        or value.get("transport_identity")
        != "gemini_count_tokens_generate_content_request"
        or value.get("within_hard_guard") is not True
    ):
        return ["pdf_structural_holdout_count_tokens_invalid"]
    return []


def _budget_count_tokens_errors(
    value: dict[str, Any], *, maximum_counted_input_tokens: int
) -> list[str]:
    observed = value.get("observed_total_tokens")
    maximum = value.get("maximum_counted_input_tokens")
    if (
        set(value) != _COUNT_TOKENS_BUDGET_KEYS
        or not _nonnegative_int(observed)
        or not _nonnegative_int(maximum)
        or maximum != maximum_counted_input_tokens
        or _integer_or_zero(observed) <= _integer_or_zero(maximum)
    ):
        return ["pdf_structural_holdout_count_tokens_budget_observation_invalid"]
    return []


def _count_tokens_observation_errors(
    value: dict[str, Any],
    *,
    model_id: str,
    maximum_counted_input_tokens: int,
) -> list[str]:
    if set(value) == _COUNT_TOKENS_BUDGET_KEYS:
        return _budget_count_tokens_errors(
            value,
            maximum_counted_input_tokens=maximum_counted_input_tokens,
        )
    return _count_tokens_errors(
        value,
        model_id=model_id,
        maximum_counted_input_tokens=maximum_counted_input_tokens,
    )


def _window_provider_config_hash(
    *,
    provider_profile: str,
    model_id: str,
    maximum_counted_input_tokens: int,
    maximum_output_tokens: int,
) -> str:
    return sha256_json(
        {
            "provider_profile": provider_profile,
            "provider_name": "google",
            "model_id": model_id,
            "maximum_counted_input_tokens": maximum_counted_input_tokens,
            "maximum_output_tokens": maximum_output_tokens,
        }
    )


def _whole_journal_count_token_calls(
    entries: list[dict[str, Any]],
) -> int:
    performed = 0
    prior_allows_next = True
    for item in entries:
        if prior_allows_next:
            performed += 1
        prior_allows_next = _whole_attempt_allows_next(item)
    return performed


def _whole_attempt_allows_next(item: dict[str, Any]) -> bool:
    attempt = _object(item.get("provider_attempt"))
    return bool(
        item.get("provider_generate_call_performed") is True
        and attempt.get("terminal_failure_class") is None
        and attempt.get("finish_reason") == "STOP"
        and attempt.get("hidden_retry") is False
        and attempt.get("provider_failover") is False
        and attempt.get("model_requested") == attempt.get("model_resolved")
    )


def _execution_terminal_journal_errors(
    *,
    journal: Any,
    journal_items: list[dict[str, Any]],
    targets: dict[str, Any],
    expected_target_ids: list[str],
    holdout_id: str,
    provider_config: dict[str, Any],
    provider_profile: str,
    model_id: str,
    maximum_counted_input_tokens: int,
    maximum_output_tokens: int,
    attempts_per_target: int,
    new_provider_count_token_calls: Any,
    new_provider_generate_calls: Any,
    expected_provider_count_token_calls: Any,
    expected_provider_generate_calls: Any,
) -> list[str]:
    errors: list[str] = []
    if (
        not isinstance(journal, list)
        or len(journal_items) != len(journal)
        or [str(item.get("target_id") or "") for item in journal_items]
        != sorted(str(item.get("target_id") or "") for item in journal_items)
    ):
        return ["pdf_structural_holdout_terminal_journal_invalid"]

    whole_provider_config_hash = sha256_json(provider_config)
    window_provider_config_hash = _window_provider_config_hash(
        provider_profile=provider_profile,
        model_id=model_id,
        maximum_counted_input_tokens=maximum_counted_input_tokens,
        maximum_output_tokens=maximum_output_tokens,
    )
    expected_count_calls = 0
    expected_generate_calls = 0
    actual_count_calls = 0
    actual_generate_calls = 0
    planner = PdfStructuralRowWindowFactory().create()

    for target_id in expected_target_ids:
        target = _object(targets.get(target_id))
        execution = _object(target.get("execution_contract"))
        mode = str(execution.get("execution_mode") or "")
        entries = [
            item for item in journal_items if item.get("target_id") == target_id
        ]
        expected_count_calls += _integer_or_zero(
            execution.get("expected_count_token_calls")
        )
        expected_generate_calls += _integer_or_zero(
            execution.get("expected_generate_calls")
        )
        terminal_status = _object(target.get("consensus_result")).get(
            "terminal_status"
        )
        assemblies = [
            item.get("assembly")
            for item in entries
            if isinstance(item.get("assembly"), dict)
        ]
        if target.get("assemblies") != assemblies:
            errors.append("pdf_structural_holdout_terminal_journal_invalid")

        if mode == "whole_table":
            expected_slots = [
                (attempt, None)
                for attempt in range(1, attempts_per_target + 1)
            ]
            actual_slots = [
                (_integer_or_zero(item.get("attempt_number")), None)
                for item in entries
            ]
            if (
                actual_slots != expected_slots
                or target.get("window_stitches") != []
                or target.get("window_runtime_result_checksum") is not None
                or any(
                    set(item) != _JOURNAL_KEYS
                    or item.get("schema_version")
                    != PDF_STRUCTURAL_HOLDOUT_JOURNAL_SCHEMA
                    or _journal_entry_errors(
                        item,
                        target=target,
                        holdout_id=holdout_id,
                        provider_config_hash=whole_provider_config_hash,
                        provider_profile=provider_profile,
                        model_id=model_id,
                        maximum_counted_input_tokens=(
                            maximum_counted_input_tokens
                        ),
                        maximum_output_tokens=maximum_output_tokens,
                    )
                    for item in entries
                )
                or (
                    len(entries) == attempts_per_target
                    and any(
                        (
                            entries[index].get("failure_code")
                            == (
                                "pdf_structural_holdout_"
                                "previous_attempt_not_started"
                            )
                        )
                        is _whole_attempt_allows_next(entries[index - 1])
                        for index in range(1, len(entries))
                    )
                )
            ):
                errors.append("pdf_structural_holdout_terminal_journal_invalid")
            actual_count_calls += _whole_journal_count_token_calls(entries)
            actual_generate_calls += sum(
                item.get("provider_generate_call_performed") is True
                for item in entries
            )
            if terminal_status == "accepted_supplied_consensus" and (
                len(assemblies) != attempts_per_target
                or actual_slots != expected_slots
                or any(
                    item.get("provider_generate_call_performed") is not True
                    for item in entries
                )
            ):
                errors.append(
                    "pdf_structural_holdout_terminal_acceptance_accounting_invalid"
                )
            continue

        if mode != "vertical_atom_windows":
            errors.append("pdf_structural_holdout_terminal_journal_invalid")
            continue
        plan = _object(execution.get("window_plan"))
        windows = _dicts(plan.get("windows"))
        frozen_inputs = _dicts(execution.get("window_inputs"))
        expected_slots = [
            (attempt, str(window.get("window_id") or ""))
            for attempt in range(1, attempts_per_target + 1)
            for window in windows
        ]
        actual_slots = [
            (
                _integer_or_zero(item.get("attempt_number")),
                str(item.get("window_id") or ""),
            )
            for item in entries
        ]
        if actual_slots != expected_slots[: len(actual_slots)]:
            errors.append("pdf_structural_holdout_window_journal_order_invalid")
        frozen_by_id = {
            str(item.get("window_id") or ""): item
            for item in frozen_inputs
        }
        last_window_id = (
            str(windows[-1].get("window_id") or "") if windows else ""
        )
        if any(
            set(item) != _WINDOW_JOURNAL_KEYS
            or _window_journal_entry_errors(
                item,
                target=target,
                frozen_window=_object(
                    frozen_by_id.get(str(item.get("window_id") or ""))
                ),
                provider_config_hash=window_provider_config_hash,
                provider_profile=provider_profile,
                model_id=model_id,
                maximum_counted_input_tokens=maximum_counted_input_tokens,
                maximum_output_tokens=maximum_output_tokens,
                is_last_window=(
                    str(item.get("window_id") or "") == last_window_id
                ),
            )
            for item in entries
        ):
            errors.append("pdf_structural_holdout_terminal_journal_invalid")
        count_calls = sum(
            item.get("provider_count_token_call_performed") is True
            for item in entries
        )
        generate_calls = sum(
            item.get("provider_generate_call_performed") is True
            for item in entries
        )
        actual_count_calls += count_calls
        actual_generate_calls += generate_calls

        stitches = _dicts(target.get("window_stitches"))
        stitch_attempt_numbers = [
            _integer_or_zero(item.get("attempt_number"))
            for item in stitches
        ]
        if (
            not isinstance(target.get("window_stitches"), list)
            or len(stitches) != len(target.get("window_stitches") or [])
            or len(stitches) > attempts_per_target
            or any(planner.validate_stitch(stitch) for stitch in stitches)
            or stitch_attempt_numbers != sorted(set(stitch_attempt_numbers))
            or any(
                attempt_number < 1
                or attempt_number > attempts_per_target
                for attempt_number in stitch_attempt_numbers
            )
            or not _sha256(target.get("window_runtime_result_checksum"))
        ):
            errors.append("pdf_structural_holdout_window_stitch_invalid")
        frozen_package_ids = [
            _object(item.get("window_package")).get("package_id")
            for item in frozen_inputs
        ]
        for stitch in stitches:
            attempt_number = _integer_or_zero(stitch.get("attempt_number"))
            round_entries = [
                item
                for item in entries
                if item.get("attempt_number") == attempt_number
                and item.get("provider_generate_call_performed") is True
            ]
            if (
                stitch.get("plan_hash") != execution.get("plan_hash")
                or stitch.get("full_package_id")
                != execution.get("full_package_id")
                or stitch.get("window_package_ids") != frozen_package_ids
                or stitch.get("window_attempt_ids")
                != [
                    _object(item.get("provider_attempt")).get("attempt_id")
                    for item in round_entries
                ]
                or stitch.get("window_response_checksums")
                != [
                    sha256_json(item.get("topology_response"))
                    for item in round_entries
                ]
            ):
                errors.append("pdf_structural_holdout_window_lineage_invalid")
                break
        if terminal_status == "accepted_supplied_consensus" and (
            actual_slots != expected_slots
            or count_calls != len(expected_slots)
            or generate_calls != len(expected_slots)
            or len(stitches) != attempts_per_target
            or len(assemblies) != attempts_per_target
        ):
            errors.append(
                "pdf_structural_holdout_terminal_acceptance_accounting_invalid"
            )

    if (
        not _nonnegative_int(new_provider_count_token_calls)
        or not _nonnegative_int(new_provider_generate_calls)
        or not _nonnegative_int(expected_provider_count_token_calls)
        or not _nonnegative_int(expected_provider_generate_calls)
        or expected_provider_count_token_calls != expected_count_calls
        or expected_provider_generate_calls != expected_generate_calls
        or new_provider_count_token_calls != actual_count_calls
        or new_provider_generate_calls != actual_generate_calls
        or actual_count_calls > expected_count_calls
        or actual_generate_calls > expected_generate_calls
    ):
        errors.append("pdf_structural_holdout_terminal_accounting_invalid")
    return sorted(set(errors))


def _window_journal_entry_errors(
    item: dict[str, Any],
    *,
    target: dict[str, Any],
    frozen_window: dict[str, Any],
    provider_config_hash: str,
    provider_profile: str,
    model_id: str,
    maximum_counted_input_tokens: int,
    maximum_output_tokens: int,
    is_last_window: bool,
) -> list[str]:
    errors: list[str] = []
    package = _object(frozen_window.get("window_package"))
    crop = _object(package.get("crop_identity"))
    plan = _object(_object(target.get("execution_contract")).get("window_plan"))
    counted = _object(item.get("count_tokens"))
    attempt = _object(item.get("provider_attempt"))
    result = _object(item.get("provider_result"))
    performed = item.get("provider_generate_call_performed") is True
    attempt_number = _integer_or_zero(item.get("attempt_number"))
    window_id = str(item.get("window_id") or "")
    local_evidence_revision = sha256_json(
        {
            "package_hash": package.get("package_hash"),
            "provider_config_hash": provider_config_hash,
            "model_view_hash": sha256_json(package.get("model_facing")),
            "output_schema_hash": sha256_json(package.get("output_schema")),
            "window_plan_hash": plan.get("plan_hash"),
        }
    )
    expected_task_id = "pdfstructrepairwintask_" + sha256_json(
        {
            "target_id": item.get("target_id"),
            "window_id": window_id,
            "evidence_revision": local_evidence_revision,
            "model_id": model_id,
        }
    )[:24]
    composite_evidence_revision = sha256_json(
        {
            "full_package_hash": _object(target.get("visual_package")).get(
                "package_hash"
            ),
            "window_plan_hash": plan.get("plan_hash"),
            "window_package_hashes": [
                _object(item.get("window_package")).get("package_hash")
                for item in _dicts(
                    _object(target.get("execution_contract")).get(
                        "window_inputs"
                    )
                )
            ],
            "provider_config_hash": provider_config_hash,
            "execution_contract": (
                "two_observations_per_window_then_stitch"
            ),
        }
    )
    has_assembly = isinstance(item.get("assembly"), dict)
    expected_evidence_revision = (
        composite_evidence_revision if has_assembly else local_evidence_revision
    )
    if (
        item.get("schema_version")
        != PDF_STRUCTURAL_HOLDOUT_WINDOW_JOURNAL_SCHEMA
        or item.get("window_package_id") != package.get("package_id")
        or frozen_window.get("window_id") != window_id
        or item.get("provider_config_hash") != provider_config_hash
        or item.get("task_id") != expected_task_id
        or item.get("job_key") != f"{expected_task_id}|a{attempt_number}"
        or item.get("evidence_revision") != expected_evidence_revision
        or item.get("provider_count_token_call_performed") is not True
        or not isinstance(item.get("provider_generate_call_performed"), bool)
        or not isinstance(item.get("count_tokens"), dict)
        or not isinstance(item.get("provider_attempt"), dict)
        or not isinstance(item.get("provider_result"), dict)
        or not isinstance(item.get("topology_response"), (dict, type(None)))
        or not isinstance(item.get("assembly"), (dict, type(None)))
        or (has_assembly and not is_last_window)
        or (
            item.get("failure_code") is None
            and item.get("failure_class") is not None
        )
        or (
            item.get("failure_code") is not None
            and item.get("failure_class") != "contract_or_terminal_failure"
        )
    ):
        errors.append("pdf_structural_holdout_window_journal_invalid")
    if counted:
        errors.extend(
            _count_tokens_observation_errors(
                counted,
                model_id=model_id,
                maximum_counted_input_tokens=maximum_counted_input_tokens,
            )
        )
    if not performed:
        if (
            attempt
            or result
            or item.get("topology_response") is not None
            or item.get("assembly") is not None
            or item.get("failure_code") is None
        ):
            errors.append(
                "pdf_structural_holdout_unperformed_attempt_payload_invalid"
            )
        return sorted(set(errors))
    if not counted:
        errors.append("pdf_structural_holdout_performed_count_tokens_missing")

    expected_attempt_id = f"{expected_task_id}_a{attempt_number}"
    expected_lineage = (
        [] if attempt_number == 1 else [f"{expected_task_id}_a1"]
    )
    usage = _object(attempt.get("usage"))
    token_values = [
        usage.get("input_tokens"),
        usage.get("output_tokens"),
        usage.get("total_tokens"),
    ]
    tokens_absent = all(value is None for value in token_values)
    tokens_valid = all(_nonnegative_int(value) for value in token_values)
    successful = attempt.get("terminal_failure_class") is None
    if (
        set(attempt) != _PROVIDER_ATTEMPT_KEYS
        or attempt.get("task_id") != expected_task_id
        or attempt.get("attempt_id") != expected_attempt_id
        or attempt.get("attempt_number") != attempt_number
        or attempt.get("attempt_lineage") != expected_lineage
        or attempt.get("provider") != "google"
        or attempt.get("provider_profile") != provider_profile
        or not isinstance(attempt.get("provider_profile_revision"), str)
        or not attempt.get("provider_profile_revision")
        or attempt.get("model_requested") != model_id
        or not isinstance(attempt.get("adapter_identity"), str)
        or not attempt.get("adapter_identity")
        or attempt.get("transport_identity")
        != "gemini_generate_content_native_table_crop_json_schema"
        or not _sha256(attempt.get("request_hash"))
        or attempt.get("crop_sha256") != crop.get("crop_sha256")
        or attempt.get("model_view_hash")
        != sha256_json(package.get("model_facing"))
        or attempt.get("canonical_schema_hash")
        != counted.get("canonical_schema_hash")
        or attempt.get("adapted_schema_hash")
        != counted.get("adapted_schema_hash")
        or attempt.get("schema_transform_count")
        != counted.get("schema_transform_count")
        or not isinstance(attempt.get("started_at"), str)
        or not attempt.get("started_at")
        or not isinstance(attempt.get("ended_at"), str)
        or not attempt.get("ended_at")
        or not isinstance(attempt.get("duration_ms"), (int, float))
        or isinstance(attempt.get("duration_ms"), bool)
        or float(attempt.get("duration_ms") or 0) < 0
        or not (
            attempt.get("http_status") is None
            or _nonnegative_int(attempt.get("http_status"))
        )
        or set(usage) != _PROVIDER_USAGE_KEYS
        or not (tokens_absent or tokens_valid)
        or attempt.get("thinking_level") != "minimal"
        or not isinstance(attempt.get("parse_result"), str)
        or not (
            attempt.get("terminal_failure_class") is None
            or attempt.get("terminal_failure_class")
            in _PROVIDER_FAILURE_CLASSES
        )
        or attempt.get("hidden_retry") is not False
        or attempt.get("provider_failover") is not False
    ):
        errors.append("pdf_structural_holdout_provider_attempt_lineage_invalid")
    if successful and (
        attempt.get("model_resolved") != model_id
        or attempt.get("finish_reason") != "STOP"
        or not tokens_valid
        or usage.get("input_tokens") != counted.get("total_tokens")
        or _integer_or_zero(usage.get("output_tokens"))
        > maximum_output_tokens
        or _integer_or_zero(usage.get("total_tokens"))
        < _integer_or_zero(usage.get("input_tokens"))
        + _integer_or_zero(usage.get("output_tokens"))
    ):
        errors.append("pdf_structural_holdout_provider_usage_invalid")
    if (
        set(result) != _PROVIDER_RESULT_KEYS
        or result.get("attempt") != attempt
        or not isinstance(result.get("raw_private_response"), dict)
        or not _nonnegative_int(result.get("response_bytes"))
        or _integer_or_zero(result.get("response_bytes")) > 2 * 1024 * 1024
        or not _sha256(result.get("response_hash"))
        or not _nonnegative_int(result.get("visible_output_bytes"))
        or _integer_or_zero(result.get("visible_output_bytes")) > 512 * 1024
        or not (
            result.get("visible_output_hash") is None
            or _sha256(result.get("visible_output_hash"))
        )
        or not isinstance(result.get("json_output"), (dict, type(None)))
        or (
            isinstance(item.get("topology_response"), dict)
            and _object(item.get("topology_response")).get("package_id")
            != package.get("package_id")
        )
    ):
        errors.append("pdf_structural_holdout_provider_result_invalid")
    return sorted(set(errors))


def _journal_entry_errors(
    item: dict[str, Any],
    *,
    target: dict[str, Any],
    holdout_id: str,
    provider_config_hash: str,
    provider_profile: str,
    model_id: str,
    maximum_counted_input_tokens: int,
    maximum_output_tokens: int,
) -> list[str]:
    errors: list[str] = []
    performed = item.get("provider_generate_call_performed") is True
    counted = _object(item.get("count_tokens"))
    attempt = _object(item.get("provider_attempt"))
    result = _object(item.get("provider_result"))
    if counted:
        errors.extend(
            _count_tokens_observation_errors(
                counted,
                model_id=model_id,
                maximum_counted_input_tokens=maximum_counted_input_tokens,
            )
        )
    if not performed:
        if attempt or result or item.get("topology_response") is not None:
            errors.append("pdf_structural_holdout_unperformed_attempt_payload_invalid")
        return errors
    if not counted:
        errors.append("pdf_structural_holdout_performed_count_tokens_missing")
    task_id = str(item.get("task_id") or "")
    attempt_number = _integer_or_zero(item.get("attempt_number"))
    expected_attempt_id = f"{task_id}_a{attempt_number}"
    expected_lineage = (
        [] if attempt_number == 1 else [f"{task_id}_a1"]
    )
    visual = _object(target.get("visual_package"))
    crop = _object(visual.get("crop_identity"))
    expected_evidence_revision = sha256_json(
        {
            "package_hash": visual.get("package_hash"),
            "provider_config_hash": provider_config_hash,
            "model_view_hash": sha256_json(visual.get("model_facing")),
            "output_schema_hash": sha256_json(visual.get("output_schema")),
            "holdout_id": holdout_id,
        }
    )
    expected_task_id = "pdfvisualtopotask_" + sha256_json(
        {
            "holdout_id": holdout_id,
            "target_id": item.get("target_id"),
            "package_hash": visual.get("package_hash"),
            "evidence_revision": expected_evidence_revision,
            "model_id": model_id,
        }
    )[:24]
    if (
        item.get("task_id") != expected_task_id
        or item.get("evidence_revision") != expected_evidence_revision
        or item.get("job_key") != f"{expected_task_id}|a{attempt_number}"
    ):
        errors.append("pdf_structural_holdout_task_lineage_invalid")
    usage = _object(attempt.get("usage"))
    token_values = [
        usage.get("input_tokens"),
        usage.get("output_tokens"),
        usage.get("total_tokens"),
    ]
    tokens_absent = all(value is None for value in token_values)
    tokens_valid = all(_nonnegative_int(value) for value in token_values)
    successful = attempt.get("terminal_failure_class") is None
    if (
        set(attempt) != _PROVIDER_ATTEMPT_KEYS
        or attempt.get("task_id") != task_id
        or attempt.get("attempt_id") != expected_attempt_id
        or attempt.get("attempt_number") != attempt_number
        or attempt.get("attempt_lineage") != expected_lineage
        or attempt.get("provider") != "google"
        or attempt.get("provider_profile") != provider_profile
        or not isinstance(attempt.get("provider_profile_revision"), str)
        or not attempt.get("provider_profile_revision")
        or attempt.get("model_requested") != model_id
        or not isinstance(attempt.get("adapter_identity"), str)
        or not attempt.get("adapter_identity")
        or attempt.get("transport_identity")
        != "gemini_generate_content_native_table_crop_json_schema"
        or not _sha256(attempt.get("request_hash"))
        or attempt.get("crop_sha256") != crop.get("crop_sha256")
        or attempt.get("model_view_hash") != sha256_json(visual.get("model_facing"))
        or attempt.get("canonical_schema_hash")
        != counted.get("canonical_schema_hash")
        or attempt.get("adapted_schema_hash")
        != counted.get("adapted_schema_hash")
        or attempt.get("schema_transform_count")
        != counted.get("schema_transform_count")
        or not isinstance(attempt.get("started_at"), str)
        or not attempt.get("started_at")
        or not isinstance(attempt.get("ended_at"), str)
        or not attempt.get("ended_at")
        or not isinstance(attempt.get("duration_ms"), (int, float))
        or isinstance(attempt.get("duration_ms"), bool)
        or float(attempt.get("duration_ms") or 0) < 0
        or not (
            attempt.get("http_status") is None
            or _nonnegative_int(attempt.get("http_status"))
        )
        or set(usage) != _PROVIDER_USAGE_KEYS
        or not (tokens_absent or tokens_valid)
        or attempt.get("thinking_level") != "minimal"
        or not isinstance(attempt.get("parse_result"), str)
        or not (
            attempt.get("terminal_failure_class") is None
            or attempt.get("terminal_failure_class")
            in _PROVIDER_FAILURE_CLASSES
        )
        or attempt.get("hidden_retry") is not False
        or attempt.get("provider_failover") is not False
    ):
        errors.append("pdf_structural_holdout_provider_attempt_lineage_invalid")
    if successful and (
        attempt.get("model_resolved") != model_id
        or attempt.get("finish_reason") != "STOP"
        or not tokens_valid
        or usage.get("input_tokens") != counted.get("total_tokens")
        or _integer_or_zero(usage.get("output_tokens")) > maximum_output_tokens
        or _integer_or_zero(usage.get("total_tokens"))
        < _integer_or_zero(usage.get("input_tokens"))
        + _integer_or_zero(usage.get("output_tokens"))
    ):
        errors.append("pdf_structural_holdout_provider_usage_invalid")
    if (
        set(result) != _PROVIDER_RESULT_KEYS
        or result.get("attempt") != attempt
        or not isinstance(result.get("raw_private_response"), dict)
        or not _nonnegative_int(result.get("response_bytes"))
        or _integer_or_zero(result.get("response_bytes")) > 2 * 1024 * 1024
        or not _sha256(result.get("response_hash"))
        or not _nonnegative_int(result.get("visible_output_bytes"))
        or _integer_or_zero(result.get("visible_output_bytes")) > 512 * 1024
        or not (
            result.get("visible_output_hash") is None
            or _sha256(result.get("visible_output_hash"))
        )
        or result.get("json_output") != item.get("topology_response")
    ):
        errors.append("pdf_structural_holdout_provider_result_invalid")
    return errors


def _journal_lineage_is_closed(items: list[dict[str, Any]]) -> bool:
    task_ids_by_target: dict[str, str] = {}
    evidence_by_target: dict[str, str] = {}
    for item in items:
        target_id = str(item.get("target_id") or "")
        task_id = str(item.get("task_id") or "")
        evidence_revision = str(item.get("evidence_revision") or "")
        if target_id in task_ids_by_target and task_ids_by_target[target_id] != task_id:
            return False
        if (
            target_id in evidence_by_target
            and evidence_by_target[target_id] != evidence_revision
        ):
            return False
        task_ids_by_target[target_id] = task_id
        evidence_by_target[target_id] = evidence_revision
    return len(set(task_ids_by_target.values())) == len(task_ids_by_target)


def _git_revision_hash(value: Any) -> bool:
    if not isinstance(value, str) or len(value) not in {40, 64}:
        return False
    return all(character in "0123456789abcdef" for character in value)


def _reason_code(value: Any) -> bool:
    return bool(
        isinstance(value, str)
        and 1 <= len(value) <= 128
        and all(character.islower() or character.isdigit() or character == "_" for character in value)
    )
