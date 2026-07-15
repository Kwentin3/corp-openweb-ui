from __future__ import annotations

import copy
import hashlib
from dataclasses import asdict, dataclass
from typing import Any

from .pdf_dual_oracle_consensus import PdfDualOracleConsensusFactory
from .pdf_dual_oracle_contracts import PdfDualOracleContractFactory
from .pdf_grid_experiment_provider import PdfGridProviderError
from .pdf_hybrid_contracts import canonical_json_bytes, sha256_json
from .pdf_hybrid_materialization import (
    PdfHybridMaterializationError,
    PdfHybridMaterializationFactory,
)
from .pdf_parser_geometry import PdfParserGeometryFactory
from .pdf_structural_row_windows import (
    PdfStructuralRowWindowError,
    PdfStructuralRowWindowFactory,
)
from .pdf_topology_assembly import PdfTopologyAssemblyFactory
from .pdf_visual_topology import (
    PDF_VISUAL_TOPOLOGY_RESPONSE_SCHEMA,
    PdfVisualTopologyConfig,
    PdfVisualTopologyFactory,
)


PDF_STRUCTURAL_REPAIR_RUNTIME_RESULT_SCHEMA = (
    "broker_reports_pdf_structural_repair_runtime_result_v1"
)
PDF_STRUCTURAL_REPAIR_RUNTIME_POLICY_VERSION = (
    "pdf_structural_repair_runtime_policy_v1"
)
PDF_STRUCTURAL_REPAIR_WINDOWED_RUNTIME_RESULT_SCHEMA = (
    "broker_reports_pdf_structural_repair_windowed_runtime_result_v1"
)
PDF_STRUCTURAL_REPAIR_CONTINUATION_RESULT_SCHEMA = (
    "broker_reports_pdf_structural_repair_continuation_result_v1"
)
PDF_VLM_GUIDED_INTAKE_RESULT_SCHEMA = (
    "broker_reports_pdf_vlm_guided_intake_result_v1"
)
PDF_VLM_GUIDED_INTAKE_SAFE_SUMMARY_SCHEMA = (
    "broker_reports_pdf_vlm_guided_intake_safe_summary_v1"
)
PDF_VLM_PAGE_PROPOSAL_RESULT_SCHEMA = (
    "broker_reports_pdf_vlm_page_proposal_result_v1"
)
PDF_VLM_PAGE_PROPOSAL_SAFE_SUMMARY_SCHEMA = (
    "broker_reports_pdf_vlm_page_proposal_safe_summary_v1"
)

FACTORY_REQUIRED = (
    "PdfStructuralRepairRuntimeFactory.create is the only countTokens, "
    "one-call page proposal, guided candidate, two-attempt, assembly, "
    "consensus, materialization and zero-provider continuation-group entrypoint"
)
FORBIDDEN = (
    "Callers must not bypass provider factories, hide retries, select the "
    "best-looking attempt, expose raw provider data, claim global uniqueness, "
    "or promote supplied-scope consensus to production authority; continuation "
    "groups must not trigger "
    "new provider calls or bypass checked fragment evidence; windowed runs "
    "must not compact source values, call a full-table provider fallback, or "
    "mix windows from different attempts; page proposals must not consume parser "
    "atoms, retry, fail over, assemble, or materialize"
)

_FACTORY_TOKEN = object()
_ATTEMPTS = (1, 2)
_GUIDED_INTAKE_EXECUTION_CONTRACT = "candidate_crop_one_call_v1"
_PAGE_PROPOSAL_EXECUTION_CONTRACT = "page_level_one_call_shadow_v1"
_PAGE_PROPOSAL_RESULT_KEYS = {
    "schema_version",
    "policy_version",
    "policy_configuration_hash",
    "run_id",
    "target_id",
    "execution_contract",
    "package_id",
    "package_hash",
    "provider_qualification",
    "journal",
    "proposal",
    "table_presence",
    "runtime_terminal_status",
    "new_provider_count_token_calls",
    "new_provider_generate_calls",
    "authority_state",
    "default_enabled",
    "production_ready",
    "production_gate2_selection_changed",
    "safe_summary",
    "result_checksum",
}
_PAGE_PROPOSAL_SAFE_SUMMARY_KEYS = {
    "schema_version",
    "target_id",
    "runtime_terminal_status",
    "reason_codes",
    "count_token_calls",
    "generate_calls",
    "table_presence",
    "regions_proposed",
    "input_atom_count",
    "proposal_persisted",
    "hidden_retry",
    "provider_failover",
    "default_enabled",
    "production_authority",
    "result_checksum_ref",
}
_PAGE_PROPOSAL_JOURNAL_KEYS = {
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
    "provider_count_token_call_performed",
    "provider_generate_call_performed",
}
_PAGE_PROPOSAL_REASON_CODES = frozenset(
    {
        "pdf_structural_repair_count_tokens_failed",
        "pdf_structural_repair_counted_input_budget_exceeded",
        "pdf_structural_repair_provider_attempt_failed",
        "pdf_structural_repair_provider_lineage_invalid",
        "pdf_structural_repair_provider_accounting_invalid",
        "pdf_vlm_page_proposal_response_invalid",
        "pdf_structural_repair_unknown_failure",
    }
)
_GUIDED_INTAKE_RESULT_KEYS = {
    "schema_version",
    "policy_version",
    "policy_configuration_hash",
    "run_id",
    "target_id",
    "execution_contract",
    "package_id",
    "package_hash",
    "parser_observation_checksum",
    "parser_geometry_observation_checksum",
    "provider_qualification",
    "journal",
    "proposal_decision",
    "assembly",
    "accepted_binding",
    "materialization",
    "post_validation",
    "runtime_terminal_status",
    "new_provider_count_token_calls",
    "new_provider_generate_calls",
    "authority_state",
    "production_ready",
    "production_gate2_selection_changed",
    "safe_summary",
    "result_checksum",
}
_GUIDED_INTAKE_POST_VALIDATION_KEYS = {
    "passed",
    "reason_codes",
    "single_bound_hypothesis",
    "alternatives_complete",
    "exact_candidate_ownership",
    "coordinate_compatible",
    "certified_separators_preserved",
    "spans_headers_valid",
    "crop_identity_preserved",
    "ambiguity_preserved",
    "source_only_materialization",
}
_GUIDED_INTAKE_SAFE_SUMMARY_KEYS = {
    "schema_version",
    "target_id",
    "runtime_terminal_status",
    "reason_codes",
    "count_token_calls",
    "generate_calls",
    "candidate_atoms",
    "row_count",
    "column_count",
    "all_candidates_accounted",
    "model_invented_values_total",
    "hidden_retry",
    "provider_failover",
    "production_authority",
}
_RESULT_KEYS = {
    "schema_version",
    "policy_version",
    "policy_configuration_hash",
    "run_id",
    "target_id",
    "package_id",
    "package_hash",
    "provider_qualification",
    "journal",
    "hypothesis_set",
    "repeatability",
    "consensus_result",
    "accepted_binding",
    "materialization",
    "runtime_terminal_status",
    "new_provider_count_token_calls",
    "new_provider_generate_calls",
    "safe_summary",
    "result_checksum",
}
_WINDOWED_RESULT_KEYS = {
    *_RESULT_KEYS,
    "execution_mode",
    "window_plan",
    "window_stitches",
}
_SAFE_SUMMARY_KEYS = {
    "schema_version",
    "run_id",
    "target_id",
    "runtime_terminal_status",
    "reason_codes",
    "attempts_expected",
    "attempts_recorded",
    "count_token_calls",
    "generate_calls",
    "counted_input_tokens",
    "actual_input_tokens",
    "output_tokens",
    "candidate_atoms",
    "row_count",
    "column_count",
    "all_candidates_accounted",
    "model_invented_values_total",
    "hidden_retry",
    "provider_failover",
    "production_authority",
    "search_scope",
    "supplied_hypotheses_exhausted",
    "structural_domain_complete",
    "uniqueness_proven",
    "ambiguity_proven",
    "domain_incomplete",
    "search_not_certifiable",
    "consensus_explanation",
    "result_checksum_ref",
}
_SAFE_REASON_CODES = frozenset(
    {
        "pdf_structural_repair_input_invalid",
        "pdf_structural_repair_provider_not_qualified",
        "pdf_structural_repair_count_tokens_failed",
        "pdf_structural_repair_counted_input_budget_exceeded",
        "pdf_structural_repair_provider_attempt_failed",
        "pdf_structural_repair_provider_lineage_invalid",
        "pdf_structural_repair_provider_accounting_invalid",
        "pdf_structural_repair_topology_invalid",
        "pdf_structural_repair_consensus_unavailable",
        "pdf_structural_repair_consensus_not_unique",
        "pdf_structural_repair_incomplete_evidence",
        "pdf_structural_repair_supplied_consensus_ambiguous",
        "pdf_structural_repair_supplied_consensus_conflict",
        "pdf_structural_repair_no_valid_supplied_consensus",
        "pdf_structural_repair_materialization_failed",
        "pdf_structural_repair_unknown_failure",
        "pdf_structural_window_plan_invalid",
        "pdf_structural_window_package_invalid",
        "pdf_structural_window_boundary_ambiguity",
        "pdf_structural_window_column_ambiguity",
        "pdf_structural_window_span_ambiguity",
        "pdf_structural_window_alternative_ambiguity",
        "pdf_structural_window_response_invalid",
    }
)
_CONTINUATION_RESULT_KEYS = {
    "schema_version",
    "policy_version",
    "policy_configuration_hash",
    "continuation_group_id",
    "continuation_contract",
    "fragment_target_ids",
    "fragment_runtime_result_checksums",
    "fragment_evidence",
    "continuation_consensus_result",
    "materialization",
    "runtime_terminal_status",
    "private_failure_code",
    "new_provider_count_token_calls",
    "new_provider_generate_calls",
    "safe_summary",
    "authority_state",
    "production_ready",
    "production_gate2_selection_changed",
    "result_checksum",
}
_CONTINUATION_SAFE_SUMMARY_KEYS = {
    "schema_version",
    "continuation_group_id",
    "runtime_terminal_status",
    "reason_codes",
    "fragment_count",
    "row_count",
    "column_count",
    "all_candidates_accounted",
    "model_invented_values_total",
    "count_token_calls",
    "generate_calls",
    "production_authority",
}
_CONTINUATION_SAFE_REASON_CODES = frozenset(
    {
        "pdf_structural_repair_continuation_incomplete_evidence",
        "pdf_structural_repair_continuation_supplied_consensus_ambiguous",
        "pdf_structural_repair_continuation_consensus_unsupported",
        "pdf_structural_repair_continuation_not_accepted_supplied_scope",
        "pdf_structural_repair_continuation_materialization_failed",
    }
)
_CONTINUATION_FRAGMENT_INPUT_KEYS = {
    "target_id",
    "parser_observation",
    "visual_package",
    "runtime_result",
    "repeat_history_ever_conflicted",
}


class PdfStructuralRepairRuntimeError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class PdfStructuralRepairRuntimeConfig:
    policy_version: str = PDF_STRUCTURAL_REPAIR_RUNTIME_POLICY_VERSION
    provider_profile: str = "google_gemini"
    provider_name: str = "google"
    model_id: str = "models/gemini-3.5-flash"
    maximum_counted_input_tokens: int = 20_000
    maximum_output_tokens: int = 8_192
    maximum_visible_output_bytes: int = 512 * 1024
    maximum_provider_response_bytes: int = 2 * 1024 * 1024
    maximum_image_bytes: int = 8 * 1024 * 1024


class PdfStructuralRepairRuntimeFactory:
    def __init__(
        self, config: PdfStructuralRepairRuntimeConfig | None = None
    ) -> None:
        self.config = config or PdfStructuralRepairRuntimeConfig()

    def create(self, *, provider: Any) -> "PdfStructuralRepairRuntime":
        if self.config.policy_version != PDF_STRUCTURAL_REPAIR_RUNTIME_POLICY_VERSION:
            raise PdfStructuralRepairRuntimeError(
                "pdf_structural_repair_runtime_policy_invalid"
            )
        budgets = (
            self.config.maximum_counted_input_tokens,
            self.config.maximum_output_tokens,
            self.config.maximum_visible_output_bytes,
            self.config.maximum_provider_response_bytes,
            self.config.maximum_image_bytes,
        )
        if budgets != (
            20_000,
            8_192,
            512 * 1024,
            2 * 1024 * 1024,
            8 * 1024 * 1024,
        ) or not self.config.model_id:
            raise PdfStructuralRepairRuntimeError(
                "pdf_structural_repair_runtime_config_invalid"
            )
        required = ("qualify", "count_tokens", "invoke")
        if provider is None or any(
            not callable(getattr(provider, name, None)) for name in required
        ):
            raise PdfStructuralRepairRuntimeError(
                "pdf_structural_repair_provider_invalid"
            )
        return PdfStructuralRepairRuntime(
            self.config,
            provider=provider,
            _factory_token=_FACTORY_TOKEN,
        )


class PdfStructuralRepairRuntime:
    def __init__(
        self,
        config: PdfStructuralRepairRuntimeConfig,
        *,
        provider: Any,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise PdfStructuralRepairRuntimeError(
                "pdf_structural_repair_runtime_factory_required"
            )
        self.config = config
        self.provider = provider
        self.contracts = PdfDualOracleContractFactory().create()
        self.parser_geometry = PdfParserGeometryFactory().create()
        self.visual = PdfVisualTopologyFactory().create()
        self.ledger_visual = PdfVisualTopologyFactory(
            PdfVisualTopologyConfig(
                maximum_model_json_bytes=512 * 1024,
                maximum_static_input_tokens=150_000,
            )
        ).create()
        self.windowing = PdfStructuralRowWindowFactory().create()
        self.assembler = PdfTopologyAssemblyFactory(
            visual_topology=self.visual,
            parser_geometry=self.parser_geometry,
        ).create()
        self.window_assembler = PdfTopologyAssemblyFactory(
            visual_topology=self.ledger_visual,
            parser_geometry=self.parser_geometry,
        ).create()
        self.solver = PdfDualOracleConsensusFactory().create()
        self.materializer = PdfHybridMaterializationFactory().create()

    def execution_mode(self, parser_observation: dict[str, Any]) -> str:
        return self.windowing.execution_mode(parser_observation)

    def plan_windowed_target(
        self, parser_observation: dict[str, Any]
    ) -> dict[str, Any]:
        return self.windowing.plan(parser_observation)

    def build_windowed_ledger_package(
        self,
        *,
        parser_observation: dict[str, Any],
        crop_manifest: dict[str, Any],
    ) -> dict[str, Any]:
        if self.execution_mode(parser_observation) != "vertical_atom_windows":
            raise PdfStructuralRepairRuntimeError(
                "pdf_structural_window_plan_invalid"
            )
        return self.ledger_visual.build_ledger_package(
            parser_observation=parser_observation,
            crop_manifest=crop_manifest,
        )

    def qualify_provider(self) -> dict[str, Any]:
        qualification = self.provider.qualify()
        data = _object(qualification)
        if (
            data.get("status") != "qualified"
            or data.get("provider_profile") != self.config.provider_profile
            or data.get("requested_model_id") != self.config.model_id
            or data.get("resolved_model_id") != self.config.model_id
            or data.get("exact_model_match") is not True
            or data.get("image_input_supported") is not True
            or data.get("structured_output_supported") is not True
            or _strict_int(data.get("maximum_input_tokens"))
            < self.config.maximum_counted_input_tokens
            or _strict_int(data.get("maximum_output_tokens"))
            < self.config.maximum_output_tokens
            or data.get("hidden_retry") is not False
            or data.get("provider_failover") is not False
        ):
            raise PdfStructuralRepairRuntimeError(
                "pdf_structural_repair_provider_not_qualified"
            )
        return copy.deepcopy(data)

    def run_page_proposal_once(
        self,
        *,
        target_id: str,
        visual_package: dict[str, Any],
        png_bytes: bytes,
        provider_qualification: dict[str, Any],
    ) -> dict[str, Any]:
        """Run one default-disabled, non-authoritative page proposal call."""

        self._validate_page_proposal_input(
            target_id=target_id,
            visual_package=visual_package,
            png_bytes=png_bytes,
            provider_qualification=provider_qualification,
        )
        provider_config_hash = sha256_json(
            {
                "provider_profile": self.config.provider_profile,
                "provider_name": self.config.provider_name,
                "model_id": self.config.model_id,
                "maximum_counted_input_tokens": (
                    self.config.maximum_counted_input_tokens
                ),
                "maximum_output_tokens": self.config.maximum_output_tokens,
                "execution_contract": _PAGE_PROPOSAL_EXECUTION_CONTRACT,
            }
        )
        evidence_revision = sha256_json(
            {
                "package_hash": visual_package.get("package_hash"),
                "provider_config_hash": provider_config_hash,
                "model_view_hash": sha256_json(
                    visual_package.get("model_facing")
                ),
                "output_schema_hash": sha256_json(
                    visual_package.get("output_schema")
                ),
            }
        )
        task_id = "pdfpageproposaltask_" + hashlib.sha256(
            canonical_json_bytes(
                {
                    "target_id": target_id,
                    "package_hash": visual_package.get("package_hash"),
                    "evidence_revision": evidence_revision,
                    "model_id": self.config.model_id,
                }
            )
        ).hexdigest()[:24]
        run_id = "pdfpageproposalrun_" + hashlib.sha256(
            canonical_json_bytes(
                {
                    "task_id": task_id,
                    "policy_version": self.config.policy_version,
                    "execution_contract": _PAGE_PROPOSAL_EXECUTION_CONTRACT,
                }
            )
        ).hexdigest()[:24]

        counted: dict[str, Any] = {}
        provider_result: dict[str, Any] = {}
        provider_attempt: dict[str, Any] = {}
        topology_response: dict[str, Any] | None = None
        proposal: dict[str, Any] | None = None
        table_presence = "not_evaluated"
        terminal = "preflight_blocked"
        failure_code: str | None = None

        try:
            counted = _object(
                self.provider.count_tokens(
                    model_view=visual_package["model_facing"],
                    output_schema=visual_package["output_schema"],
                    png_bytes=png_bytes,
                    crop_sha256=visual_package["crop_identity"][
                        "crop_sha256"
                    ],
                )
            )
            self._validate_counted_tokens(counted)
        except (PdfGridProviderError, PdfStructuralRepairRuntimeError) as exc:
            counted = _counted_from_provider_error(
                exc,
                model_id=self.config.model_id,
                current=counted,
            )
            failure_code = (
                "pdf_structural_repair_counted_input_budget_exceeded"
                if _strict_int(counted.get("total_tokens"))
                > self.config.maximum_counted_input_tokens
                else "pdf_structural_repair_count_tokens_failed"
            )
            journal = [
                self._journal_entry(
                    target_id=target_id,
                    task_id=task_id,
                    attempt_number=1,
                    evidence_revision=evidence_revision,
                    provider_config_hash=provider_config_hash,
                    counted=counted,
                    provider_attempt={},
                    provider_result={},
                    topology_response=None,
                    assembly=None,
                    failure_code=failure_code,
                    count_token_call_performed=True,
                    generate_call_performed=False,
                )
            ]
            return self._page_proposal_result(
                run_id=run_id,
                target_id=target_id,
                visual_package=visual_package,
                provider_qualification=provider_qualification,
                journal=journal,
                proposal=None,
                table_presence=table_presence,
                terminal=terminal,
            )

        try:
            provider_result = _object(
                self.provider.invoke(
                    task_id=task_id,
                    model_view=visual_package["model_facing"],
                    output_schema=visual_package["output_schema"],
                    png_bytes=png_bytes,
                    crop_sha256=visual_package["crop_identity"][
                        "crop_sha256"
                    ],
                    attempt_number=1,
                    attempt_lineage=[],
                )
            )
            provider_attempt = _object(provider_result.get("attempt"))
            self._validate_provider_attempt(
                attempt=provider_attempt,
                task_id=task_id,
                attempt_number=1,
                attempt_lineage=[],
                counted=counted,
                provider_result=provider_result,
            )
            topology_response = _object(provider_result.get("json_output"))
            if not topology_response:
                raise PdfStructuralRepairRuntimeError(
                    "pdf_structural_repair_provider_attempt_failed"
                )
            proposal = self.visual.parse_region_proposal_response(
                topology_response,
                expected_package_id=str(
                    visual_package.get("package_id") or ""
                ),
                expected_proposal_scope="page_level",
            )
            table_presence = str(proposal.get("table_presence") or "")
            terminal = "proposal_persisted"
        except (
            PdfGridProviderError,
            PdfStructuralRepairRuntimeError,
            ValueError,
        ) as exc:
            failure_code = _safe_page_proposal_failure_code(exc)
            terminal = (
                "proposal_invalid"
                if topology_response is not None
                else "provider_failed"
            )
            proposal = None
            table_presence = "not_evaluated"

        journal = [
            self._journal_entry(
                target_id=target_id,
                task_id=task_id,
                attempt_number=1,
                evidence_revision=evidence_revision,
                provider_config_hash=provider_config_hash,
                counted=counted,
                provider_attempt=provider_attempt,
                provider_result=provider_result,
                topology_response=topology_response,
                assembly=None,
                failure_code=failure_code,
                count_token_call_performed=True,
                generate_call_performed=True,
            )
        ]
        return self._page_proposal_result(
            run_id=run_id,
            target_id=target_id,
            visual_package=visual_package,
            provider_qualification=provider_qualification,
            journal=journal,
            proposal=proposal,
            table_presence=table_presence,
            terminal=terminal,
        )

    def run_candidate_once(
        self,
        *,
        target_id: str,
        parser_observation: dict[str, Any],
        parser_geometry_observation: dict[str, Any],
        visual_package: dict[str, Any],
        png_bytes: bytes,
        provider_qualification: dict[str, Any],
    ) -> dict[str, Any]:
        """Run the default-disabled candidate-crop intake contract once.

        This route deliberately does not reuse the two-attempt consensus
        contract.  The provider may propose one bounded structure; parser
        geometry, exact atom ownership and source-only materialization then
        prove it or block it.  No retry, failover, ranking or best-candidate
        selection exists in this method.
        """

        self._validate_guided_intake_input(
            target_id=target_id,
            parser_observation=parser_observation,
            parser_geometry_observation=parser_geometry_observation,
            visual_package=visual_package,
            png_bytes=png_bytes,
            provider_qualification=provider_qualification,
        )
        provider_config_hash = sha256_json(
            {
                "provider_profile": self.config.provider_profile,
                "provider_name": self.config.provider_name,
                "model_id": self.config.model_id,
                "maximum_counted_input_tokens": (
                    self.config.maximum_counted_input_tokens
                ),
                "maximum_output_tokens": self.config.maximum_output_tokens,
                "execution_contract": _GUIDED_INTAKE_EXECUTION_CONTRACT,
            }
        )
        evidence_revision = sha256_json(
            {
                "package_hash": visual_package.get("package_hash"),
                "provider_config_hash": provider_config_hash,
                "model_view_hash": sha256_json(
                    visual_package.get("model_facing")
                ),
                "output_schema_hash": sha256_json(
                    visual_package.get("output_schema")
                ),
            }
        )
        task_id = "pdfguidedintaketask_" + hashlib.sha256(
            canonical_json_bytes(
                {
                    "target_id": target_id,
                    "package_hash": visual_package.get("package_hash"),
                    "evidence_revision": evidence_revision,
                    "model_id": self.config.model_id,
                }
            )
        ).hexdigest()[:24]
        run_id = "pdfguidedintakerun_" + hashlib.sha256(
            canonical_json_bytes(
                {
                    "task_id": task_id,
                    "policy_version": self.config.policy_version,
                    "execution_contract": _GUIDED_INTAKE_EXECUTION_CONTRACT,
                }
            )
        ).hexdigest()[:24]

        counted: dict[str, Any] = {}
        provider_result: dict[str, Any] = {}
        provider_attempt: dict[str, Any] = {}
        topology_response: dict[str, Any] | None = None
        parsed_response: dict[str, Any] | None = None
        assembly_package = visual_package
        assembly: dict[str, Any] | None = None
        accepted_binding: dict[str, Any] | None = None
        materialization: dict[str, Any] | None = None
        proposal_decision = "not_evaluated"
        terminal = "preflight_blocked"
        failure_code: str | None = None
        count_call_performed = False
        generate_call_performed = False

        try:
            count_call_performed = True
            counted = _object(
                self.provider.count_tokens(
                    model_view=visual_package["model_facing"],
                    output_schema=visual_package["output_schema"],
                    png_bytes=png_bytes,
                    crop_sha256=visual_package["crop_identity"][
                        "crop_sha256"
                    ],
                )
            )
            self._validate_counted_tokens(counted)
        except (PdfGridProviderError, PdfStructuralRepairRuntimeError) as exc:
            counted = _counted_from_provider_error(
                exc,
                model_id=self.config.model_id,
                current=counted,
            )
            failure_code = (
                "pdf_structural_repair_counted_input_budget_exceeded"
                if _strict_int(counted.get("total_tokens"))
                > self.config.maximum_counted_input_tokens
                else "pdf_structural_repair_count_tokens_failed"
            )
            journal = [
                self._journal_entry(
                    target_id=target_id,
                    task_id=task_id,
                    attempt_number=1,
                    evidence_revision=evidence_revision,
                    provider_config_hash=provider_config_hash,
                    counted=counted,
                    provider_attempt={},
                    provider_result={},
                    topology_response=None,
                    assembly=None,
                    failure_code=failure_code,
                    count_token_call_performed=True,
                    generate_call_performed=False,
                )
            ]
            return self._guided_intake_result(
                run_id=run_id,
                target_id=target_id,
                parser_observation=parser_observation,
                parser_geometry_observation=parser_geometry_observation,
                visual_package=visual_package,
                provider_qualification=provider_qualification,
                journal=journal,
                proposal_decision=proposal_decision,
                assembly=None,
                accepted_binding=None,
                materialization=None,
                post_validation=self._guided_post_validation(
                    reason_codes=[failure_code]
                ),
                terminal=terminal,
            )

        try:
            generate_call_performed = True
            provider_result = _object(
                self.provider.invoke(
                    task_id=task_id,
                    model_view=visual_package["model_facing"],
                    output_schema=visual_package["output_schema"],
                    png_bytes=png_bytes,
                    crop_sha256=visual_package["crop_identity"][
                        "crop_sha256"
                    ],
                    attempt_number=1,
                    attempt_lineage=[],
                )
            )
            provider_attempt = _object(provider_result.get("attempt"))
            self._validate_provider_attempt(
                attempt=provider_attempt,
                task_id=task_id,
                attempt_number=1,
                attempt_lineage=[],
                counted=counted,
                provider_result=provider_result,
            )
            topology_response = _object(provider_result.get("json_output"))
            if not topology_response:
                raise PdfStructuralRepairRuntimeError(
                    "pdf_structural_repair_provider_attempt_failed"
                )
            region_response = self.visual.parse_region_proposal_response(
                topology_response,
                expected_package_id=str(
                    visual_package.get("package_id") or ""
                ),
                expected_proposal_scope="candidate_crop",
            )
            presence = region_response.get("table_presence")
            if presence == "absent":
                proposal_decision = "unsupported"
                terminal = "proposal_absent"
            elif presence == "uncertain":
                proposal_decision = "ambiguous"
                terminal = "proposal_ambiguous"
            else:
                region = _dicts(region_response.get("regions"))[0]
                if region.get("bbox") != [0.0, 0.0, 1.0, 1.0]:
                    proposal_decision = "bound"
                    failure_code = (
                        "pdf_vlm_guided_intake_region_reselection_required"
                    )
                    terminal = "validation_blocked"
                else:
                    assembly_package = self._guided_legacy_package_from_region(
                        parser_observation=parser_observation,
                        region_package=visual_package,
                    )
                    parsed_response = self._guided_topology_from_region(
                        region_response=region_response,
                        legacy_package_id=str(
                            assembly_package.get("package_id") or ""
                        ),
                    )
                    proposal_decision = str(
                        parsed_response.get("decision") or "not_evaluated"
                    )

            if parsed_response is not None:
                assembly = self.assembler.assemble(
                    parser_observation=parser_observation,
                    parser_geometry_observation=parser_geometry_observation,
                    visual_package=assembly_package,
                    topology_response=parsed_response,
                    attempt_evidence={
                        "attempt_id": provider_attempt["attempt_id"],
                        "attempt_number": 1,
                        "evidence_revision": evidence_revision,
                        "provider": self.config.provider_name,
                        "model": self.config.model_id,
                        "provider_config_hash": provider_config_hash,
                    },
                    hypothesis_id_prefix=f"guided_{target_id}_a1",
                )
                if self.assembler.validate_result(assembly):
                    raise PdfStructuralRepairRuntimeError(
                        "pdf_structural_repair_topology_invalid"
                    )

                if proposal_decision == "unsupported":
                    terminal = "proposal_unsupported"
                elif (
                    proposal_decision != "bound"
                    or parsed_response.get("alternatives_complete") is not True
                    or len(_dicts(parsed_response.get("hypotheses"))) != 1
                ):
                    terminal = "proposal_ambiguous"
                else:
                    bindings = _dicts(assembly.get("binding_hypotheses"))
                    pre_reasons = self._guided_acceptance_reasons(
                        parser_observation=parser_observation,
                        visual_package=assembly_package,
                        parsed_response=parsed_response,
                        assembly=assembly,
                    )
                    if not pre_reasons and len(bindings) == 1:
                        candidate_binding = _object(
                            bindings[0].get("binding_output")
                        )
                        try:
                            candidate_materialization = (
                                self.materializer.materialize(
                                    evidence_package=assembly_package,
                                    binding_output=candidate_binding,
                                )
                            )
                        except PdfHybridMaterializationError as exc:
                            pre_reasons.append(exc.code)
                        else:
                            materialization_errors = (
                                self.materializer.validate_materialization(
                                    candidate_materialization
                                )
                            )
                            if materialization_errors:
                                pre_reasons.extend(materialization_errors)
                            else:
                                accepted_binding = candidate_binding
                                materialization = candidate_materialization
                    if (
                        pre_reasons
                        or accepted_binding is None
                        or materialization is None
                    ):
                        failure_code = (
                            sorted(set(pre_reasons))[0]
                            if pre_reasons
                            else "pdf_vlm_guided_intake_single_binding_required"
                        )
                        terminal = "validation_blocked"
                    else:
                        terminal = "accepted_physical_structure"
        except (
            PdfGridProviderError,
            PdfStructuralRepairRuntimeError,
            ValueError,
        ) as exc:
            failure_code = _safe_failure_code(exc)
            terminal = (
                "validation_blocked"
                if topology_response is not None
                else "provider_failed"
            )

        reason_codes = [failure_code] if failure_code else []
        post_validation = self._guided_post_validation(
            reason_codes=reason_codes,
            parsed_response=parsed_response,
            parser_observation=parser_observation,
            visual_package=assembly_package,
            assembly=assembly,
            materialization=materialization,
            terminal=terminal,
        )
        journal = [
            self._journal_entry(
                target_id=target_id,
                task_id=task_id,
                attempt_number=1,
                evidence_revision=evidence_revision,
                provider_config_hash=provider_config_hash,
                counted=counted,
                provider_attempt=provider_attempt,
                provider_result=provider_result,
                topology_response=topology_response,
                assembly=assembly,
                failure_code=failure_code,
                count_token_call_performed=count_call_performed,
                generate_call_performed=generate_call_performed,
            )
        ]
        return self._guided_intake_result(
            run_id=run_id,
            target_id=target_id,
            parser_observation=parser_observation,
            parser_geometry_observation=parser_geometry_observation,
            visual_package=visual_package,
            provider_qualification=provider_qualification,
            journal=journal,
            proposal_decision=proposal_decision,
            assembly=assembly,
            accepted_binding=accepted_binding,
            materialization=materialization,
            post_validation=post_validation,
            terminal=terminal,
        )

    def run_target(
        self,
        *,
        target_id: str,
        parser_observation: dict[str, Any],
        parser_geometry_observation: dict[str, Any],
        visual_package: dict[str, Any],
        png_bytes: bytes,
        provider_qualification: dict[str, Any],
    ) -> dict[str, Any]:
        self._validate_input(
            target_id=target_id,
            parser_observation=parser_observation,
            parser_geometry_observation=parser_geometry_observation,
            visual_package=visual_package,
            png_bytes=png_bytes,
            provider_qualification=provider_qualification,
        )
        provider_config_hash = sha256_json(
            {
                "provider_profile": self.config.provider_profile,
                "provider_name": self.config.provider_name,
                "model_id": self.config.model_id,
                "maximum_counted_input_tokens": (
                    self.config.maximum_counted_input_tokens
                ),
                "maximum_output_tokens": self.config.maximum_output_tokens,
            }
        )
        evidence_revision = sha256_json(
            {
                "package_hash": visual_package.get("package_hash"),
                "provider_config_hash": provider_config_hash,
                "model_view_hash": sha256_json(
                    visual_package.get("model_facing")
                ),
                "output_schema_hash": sha256_json(
                    visual_package.get("output_schema")
                ),
            }
        )
        task_id = "pdfstructrepairtask_" + hashlib.sha256(
            canonical_json_bytes(
                {
                    "target_id": target_id,
                    "package_hash": visual_package.get("package_hash"),
                    "evidence_revision": evidence_revision,
                    "model_id": self.config.model_id,
                }
            )
        ).hexdigest()[:24]
        run_id = "pdfstructrepairrun_" + hashlib.sha256(
            canonical_json_bytes(
                {
                    "task_id": task_id,
                    "policy_version": self.config.policy_version,
                }
            )
        ).hexdigest()[:24]

        journal: list[dict[str, Any]] = []
        attempt_ids: list[str] = []
        assemblies: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []
        preflight_reason: str | None = None

        for attempt_number in _ATTEMPTS:
            counted: dict[str, Any] = {}
            provider_result: dict[str, Any] = {}
            provider_attempt: dict[str, Any] = {}
            topology_response: dict[str, Any] | None = None
            assembly: dict[str, Any] | None = None
            failure_code: str | None = None
            try:
                counted = _object(
                    self.provider.count_tokens(
                        model_view=visual_package["model_facing"],
                        output_schema=visual_package["output_schema"],
                        png_bytes=png_bytes,
                        crop_sha256=visual_package["crop_identity"][
                            "crop_sha256"
                        ],
                    )
                )
                self._validate_counted_tokens(counted)
            except (PdfGridProviderError, PdfStructuralRepairRuntimeError) as exc:
                counted = _counted_from_provider_error(
                    exc,
                    model_id=self.config.model_id,
                    current=counted,
                )
                failure_code = "pdf_structural_repair_count_tokens_failed"
                if _strict_int(counted.get("total_tokens")) > (
                    self.config.maximum_counted_input_tokens
                ):
                    failure_code = (
                        "pdf_structural_repair_counted_input_budget_exceeded"
                    )
                preflight_reason = failure_code
                journal.append(
                    self._journal_entry(
                        target_id=target_id,
                        task_id=task_id,
                        attempt_number=attempt_number,
                        evidence_revision=evidence_revision,
                        provider_config_hash=provider_config_hash,
                        counted=counted,
                        provider_attempt={},
                        provider_result={},
                        topology_response=None,
                        assembly=None,
                        failure_code=failure_code,
                        count_token_call_performed=True,
                        generate_call_performed=False,
                    )
                )
                break

            try:
                provider_result = _object(
                    self.provider.invoke(
                        task_id=task_id,
                        model_view=visual_package["model_facing"],
                        output_schema=visual_package["output_schema"],
                        png_bytes=png_bytes,
                        crop_sha256=visual_package["crop_identity"][
                            "crop_sha256"
                        ],
                        attempt_number=attempt_number,
                        attempt_lineage=list(attempt_ids),
                    )
                )
                provider_attempt = _object(provider_result.get("attempt"))
                self._validate_provider_attempt(
                    attempt=provider_attempt,
                    task_id=task_id,
                    attempt_number=attempt_number,
                    attempt_lineage=attempt_ids,
                    counted=counted,
                    provider_result=provider_result,
                )
                attempt_ids.append(str(provider_attempt["attempt_id"]))
                topology_response = _object(provider_result.get("json_output"))
                if not topology_response:
                    raise PdfStructuralRepairRuntimeError(
                        "pdf_structural_repair_provider_attempt_failed"
                    )
                assembly = self.assembler.assemble(
                    parser_observation=parser_observation,
                    parser_geometry_observation=parser_geometry_observation,
                    visual_package=visual_package,
                    topology_response=topology_response,
                    attempt_evidence={
                        "attempt_id": provider_attempt["attempt_id"],
                        "attempt_number": attempt_number,
                        "evidence_revision": evidence_revision,
                        "provider": self.config.provider_name,
                        "model": self.config.model_id,
                        "provider_config_hash": provider_config_hash,
                    },
                    hypothesis_id_prefix=(
                        f"structural_{target_id}_a{attempt_number}"
                    ),
                )
                assembly_errors = self.assembler.validate_result(assembly)
                if assembly_errors:
                    raise PdfStructuralRepairRuntimeError(
                        "pdf_structural_repair_topology_invalid"
                    )
                assemblies.append(assembly)
            except (
                PdfGridProviderError,
                PdfStructuralRepairRuntimeError,
                ValueError,
            ) as exc:
                failure_code = _safe_failure_code(exc)
                if provider_attempt.get("attempt_id") and (
                    str(provider_attempt["attempt_id"]) not in attempt_ids
                ):
                    if (
                        provider_attempt.get("task_id") == task_id
                        and provider_attempt.get("attempt_number") == attempt_number
                        and provider_attempt.get("attempt_lineage") == attempt_ids
                    ):
                        attempt_ids.append(str(provider_attempt["attempt_id"]))
                rejected.append(
                    {
                        "evidence_id": "failed_"
                        + hashlib.sha256(
                            f"{task_id}|a{attempt_number}".encode("utf-8")
                        ).hexdigest()[:24],
                        "reason_codes": [failure_code],
                    }
                )

            journal.append(
                self._journal_entry(
                    target_id=target_id,
                    task_id=task_id,
                    attempt_number=attempt_number,
                    evidence_revision=evidence_revision,
                    provider_config_hash=provider_config_hash,
                    counted=counted,
                    provider_attempt=provider_attempt,
                    provider_result=provider_result,
                    topology_response=topology_response,
                    assembly=assembly,
                    failure_code=failure_code,
                    count_token_call_performed=True,
                    generate_call_performed=bool(
                        provider_attempt.get("started_at")
                    ),
                )
            )

        hypothesis_set: dict[str, Any] | None = None
        repeatability: dict[str, Any] | None = None
        consensus: dict[str, Any] | None = None
        accepted_binding: dict[str, Any] | None = None
        materialization: dict[str, Any] | None = None

        if preflight_reason is None:
            binding_inputs = [
                hypothesis
                for assembly in assemblies
                for hypothesis in _dicts(assembly.get("binding_hypotheses"))
            ]
            rejected.extend(
                evidence
                for assembly in assemblies
                for evidence in _dicts(assembly.get("rejected_evidence"))
            )
            model_context = self._model_context(
                visual_package=visual_package,
                journal=journal,
                assemblies=assemblies,
                provider_config_hash=provider_config_hash,
            )
            hypothesis_set = self.contracts.build_vlm_hypothesis_set(
                parser_observation=parser_observation,
                binding_hypotheses=binding_inputs,
                rejected_evidence=rejected,
                model_context=model_context,
            )
            hypothesis_errors = self.contracts.validate_vlm_hypothesis_set(
                parser_observation=parser_observation,
                hypothesis_set=hypothesis_set,
            )
            if hypothesis_errors:
                raise PdfStructuralRepairRuntimeError(hypothesis_errors[0])
            repeatability = self.solver.build_repeatability_record(
                parser_observation=parser_observation,
                vlm_hypothesis_set=hypothesis_set,
            )
            consensus = self.solver.solve(
                parser_observation=parser_observation,
                vlm_hypothesis_set=hypothesis_set,
                historical_repeatability=repeatability,
            )
            repeated = self.solver.solve(
                parser_observation=copy.deepcopy(parser_observation),
                vlm_hypothesis_set=copy.deepcopy(hypothesis_set),
                historical_repeatability=copy.deepcopy(repeatability),
            )
            if consensus != repeated:
                raise PdfStructuralRepairRuntimeError(
                    "pdf_structural_repair_solver_nondeterministic"
                )
            if consensus.get("terminal_status") == "accepted_supplied_consensus":
                accepted_binding = self.solver.binding_from_accepted_consensus(
                    parser_observation=parser_observation,
                    consensus_result=consensus,
                    vlm_hypothesis_set=hypothesis_set,
                    evidence_package=visual_package,
                )
                materialization = self.materializer.materialize(
                    evidence_package=visual_package,
                    binding_output=accepted_binding,
                )

        runtime_terminal = (
            "preflight_blocked"
            if preflight_reason is not None
            else str(
                _object(consensus).get("terminal_status")
                or "no_valid_consensus"
            )
        )
        result = {
            "schema_version": PDF_STRUCTURAL_REPAIR_RUNTIME_RESULT_SCHEMA,
            "policy_version": self.config.policy_version,
            "policy_configuration_hash": sha256_json(asdict(self.config)),
            "run_id": run_id,
            "target_id": target_id,
            "package_id": visual_package.get("package_id"),
            "package_hash": visual_package.get("package_hash"),
            "provider_qualification": copy.deepcopy(provider_qualification),
            "journal": journal,
            "hypothesis_set": hypothesis_set,
            "repeatability": repeatability,
            "consensus_result": consensus,
            "accepted_binding": accepted_binding,
            "materialization": materialization,
            "runtime_terminal_status": runtime_terminal,
            "new_provider_count_token_calls": sum(
                item.get("provider_count_token_call_performed") is True
                for item in journal
            ),
            "new_provider_generate_calls": sum(
                item.get("provider_generate_call_performed") is True
                for item in journal
            ),
            "safe_summary": {},
        }
        result["safe_summary"] = self._safe_summary(
            result=result,
            visual_package=visual_package,
            preflight_reason=preflight_reason,
        )
        result["result_checksum"] = _result_checksum(result)
        result["safe_summary"]["result_checksum_ref"] = result[
            "result_checksum"
        ]
        errors = self.validate_result(result)
        if errors:
            raise PdfStructuralRepairRuntimeError(errors[0])
        return result

    def run_windowed_target(
        self,
        *,
        target_id: str,
        parser_observation: dict[str, Any],
        parser_geometry_observation: dict[str, Any],
        visual_package: dict[str, Any],
        window_plan: dict[str, Any],
        window_inputs: list[dict[str, Any]],
        provider_qualification: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute exactly two observations for every preplanned row window."""

        self._validate_windowed_input(
            target_id=target_id,
            parser_observation=parser_observation,
            parser_geometry_observation=parser_geometry_observation,
            visual_package=visual_package,
            window_plan=window_plan,
            window_inputs=window_inputs,
            provider_qualification=provider_qualification,
        )
        provider_config_hash = sha256_json(
            {
                "provider_profile": self.config.provider_profile,
                "provider_name": self.config.provider_name,
                "model_id": self.config.model_id,
                "maximum_counted_input_tokens": (
                    self.config.maximum_counted_input_tokens
                ),
                "maximum_output_tokens": self.config.maximum_output_tokens,
            }
        )
        run_id = "pdfstructrepairwinrun_" + hashlib.sha256(
            canonical_json_bytes(
                {
                    "target_id": target_id,
                    "package_hash": visual_package.get("package_hash"),
                    "window_plan_hash": window_plan.get("plan_hash"),
                    "provider_config_hash": provider_config_hash,
                    "policy_version": self.config.policy_version,
                }
            )
        ).hexdigest()[:24]
        task_ids: dict[str, str] = {}
        evidence_revisions: dict[str, str] = {}
        attempt_lineages: dict[str, list[str]] = {}
        for item in window_inputs:
            package = _object(item.get("window_package"))
            window_id = str(item.get("window_id") or "")
            evidence_revision = sha256_json(
                {
                    "package_hash": package.get("package_hash"),
                    "provider_config_hash": provider_config_hash,
                    "model_view_hash": sha256_json(package.get("model_facing")),
                    "output_schema_hash": sha256_json(
                        package.get("output_schema")
                    ),
                    "window_plan_hash": window_plan.get("plan_hash"),
                }
            )
            task_id = "pdfstructrepairwintask_" + hashlib.sha256(
                canonical_json_bytes(
                    {
                        "target_id": target_id,
                        "window_id": window_id,
                        "evidence_revision": evidence_revision,
                        "model_id": self.config.model_id,
                    }
                )
            ).hexdigest()[:24]
            task_ids[window_id] = task_id
            evidence_revisions[window_id] = evidence_revision
            attempt_lineages[window_id] = []
        composite_evidence_revision = sha256_json(
            {
                "full_package_hash": visual_package.get("package_hash"),
                "window_plan_hash": window_plan.get("plan_hash"),
                "window_package_hashes": [
                    _object(item.get("window_package")).get("package_hash")
                    for item in window_inputs
                ],
                "provider_config_hash": provider_config_hash,
                "execution_contract": "two_observations_per_window_then_stitch",
            }
        )

        journal: list[dict[str, Any]] = []
        assemblies: list[dict[str, Any]] = []
        stitches: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []
        preflight_reason: str | None = None
        evidence_failure_reasons: set[str] = set()
        for attempt_number in _ATTEMPTS:
            round_responses: list[dict[str, Any]] = []
            round_packages: list[dict[str, Any]] = []
            round_attempt_ids: list[str] = []
            round_failed = False
            for item in window_inputs:
                window_id = str(item["window_id"])
                package = _object(item.get("window_package"))
                png_bytes = item.get("png_bytes")
                task_id = task_ids[window_id]
                evidence_revision = evidence_revisions[window_id]
                counted: dict[str, Any] = {}
                provider_result: dict[str, Any] = {}
                provider_attempt: dict[str, Any] = {}
                topology_response: dict[str, Any] | None = None
                local_failure: str | None = None
                try:
                    counted = _object(
                        self.provider.count_tokens(
                            model_view=package["model_facing"],
                            output_schema=package["output_schema"],
                            png_bytes=png_bytes,
                            crop_sha256=package["crop_identity"]["crop_sha256"],
                        )
                    )
                    self._validate_counted_tokens(counted)
                except (PdfGridProviderError, PdfStructuralRepairRuntimeError) as exc:
                    counted = _counted_from_provider_error(
                        exc,
                        model_id=self.config.model_id,
                        current=counted,
                    )
                    local_failure = _safe_failure_code(exc)
                    if _strict_int(counted.get("total_tokens")) > (
                        self.config.maximum_counted_input_tokens
                    ):
                        local_failure = (
                            "pdf_structural_repair_counted_input_budget_exceeded"
                        )
                    preflight_reason = local_failure
                    entry = self._journal_entry(
                        target_id=target_id,
                        task_id=task_id,
                        attempt_number=attempt_number,
                        evidence_revision=evidence_revision,
                        provider_config_hash=provider_config_hash,
                        counted=counted,
                        provider_attempt={},
                        provider_result={},
                        topology_response=None,
                        assembly=None,
                        failure_code=local_failure,
                        count_token_call_performed=True,
                        generate_call_performed=False,
                    )
                    entry["window_id"] = window_id
                    entry["window_package_id"] = package.get("package_id")
                    journal.append(entry)
                    break
                try:
                    lineage = list(attempt_lineages[window_id])
                    provider_result = _object(
                        self.provider.invoke(
                            task_id=task_id,
                            model_view=package["model_facing"],
                            output_schema=package["output_schema"],
                            png_bytes=png_bytes,
                            crop_sha256=package["crop_identity"]["crop_sha256"],
                            attempt_number=attempt_number,
                            attempt_lineage=lineage,
                        )
                    )
                    provider_attempt = _object(provider_result.get("attempt"))
                    self._validate_provider_attempt(
                        attempt=provider_attempt,
                        task_id=task_id,
                        attempt_number=attempt_number,
                        attempt_lineage=lineage,
                        counted=counted,
                        provider_result=provider_result,
                    )
                    attempt_lineages[window_id].append(
                        str(provider_attempt["attempt_id"])
                    )
                    round_attempt_ids.append(str(provider_attempt["attempt_id"]))
                    topology_response = self.visual.parse_response(
                        _object(provider_result.get("json_output")),
                        expected_package_id=str(package.get("package_id") or ""),
                    )
                    round_responses.append(topology_response)
                    round_packages.append(package)
                except (
                    PdfGridProviderError,
                    PdfStructuralRepairRuntimeError,
                    ValueError,
                ) as exc:
                    local_failure = _safe_window_failure_code(exc)
                    evidence_failure_reasons.add(local_failure)
                    round_failed = True
                    rejected.append(
                        {
                            "evidence_id": "failed_"
                            + hashlib.sha256(
                                f"{task_id}|a{attempt_number}".encode("utf-8")
                            ).hexdigest()[:24],
                            "reason_codes": [local_failure],
                        }
                    )
                entry = self._journal_entry(
                    target_id=target_id,
                    task_id=task_id,
                    attempt_number=attempt_number,
                    evidence_revision=evidence_revision,
                    provider_config_hash=provider_config_hash,
                    counted=counted,
                    provider_attempt=provider_attempt,
                    provider_result=provider_result,
                    topology_response=topology_response,
                    assembly=None,
                    failure_code=local_failure,
                    count_token_call_performed=True,
                    generate_call_performed=bool(provider_attempt.get("started_at")),
                )
                entry["window_id"] = window_id
                entry["window_package_id"] = package.get("package_id")
                journal.append(entry)
            if preflight_reason is not None:
                break
            if round_failed:
                continue
            try:
                stitch = self.windowing.stitch_attempt(
                    plan=window_plan,
                    full_package_id=str(visual_package.get("package_id") or ""),
                    window_packages=round_packages,
                    topology_responses=round_responses,
                    window_attempt_ids=round_attempt_ids,
                    attempt_number=attempt_number,
                )
                self.ledger_visual.parse_response(
                    _object(stitch.get("stitched_response")),
                    expected_package_id=str(visual_package.get("package_id") or ""),
                )
                stitches.append(stitch)
                assembly = self.window_assembler.assemble(
                    parser_observation=parser_observation,
                    parser_geometry_observation=parser_geometry_observation,
                    visual_package=visual_package,
                    topology_response=_object(stitch.get("stitched_response")),
                    attempt_evidence={
                        "attempt_id": stitch["composite_attempt_id"],
                        "attempt_number": attempt_number,
                        "evidence_revision": composite_evidence_revision,
                        "provider": self.config.provider_name,
                        "model": self.config.model_id,
                        "provider_config_hash": provider_config_hash,
                    },
                    hypothesis_id_prefix=f"structural_{target_id}_a{attempt_number}",
                )
                if self.window_assembler.validate_result(assembly):
                    raise PdfStructuralRepairRuntimeError(
                        "pdf_structural_repair_topology_invalid"
                    )
                assemblies.append(assembly)
                journal[-1]["assembly"] = copy.deepcopy(assembly)
                journal[-1]["evidence_revision"] = composite_evidence_revision
                journal[-1]["composite_attempt_id"] = stitch[
                    "composite_attempt_id"
                ]
            except (
                PdfStructuralRowWindowError,
                PdfStructuralRepairRuntimeError,
                ValueError,
            ) as exc:
                failure_reason = _safe_window_failure_code(exc)
                evidence_failure_reasons.add(failure_reason)
                rejected.append(
                    {
                        "evidence_id": "failed_stitch_"
                        + hashlib.sha256(
                            f"{run_id}|a{attempt_number}".encode("utf-8")
                        ).hexdigest()[:24],
                        "reason_codes": [failure_reason],
                    }
                )
                continue

        hypothesis_set: dict[str, Any] | None = None
        repeatability: dict[str, Any] | None = None
        consensus: dict[str, Any] | None = None
        accepted_binding: dict[str, Any] | None = None
        materialization: dict[str, Any] | None = None
        if preflight_reason is None and len(stitches) == 2:
            binding_inputs = [
                hypothesis
                for assembly in assemblies
                for hypothesis in _dicts(assembly.get("binding_hypotheses"))
            ]
            rejected.extend(
                evidence
                for assembly in assemblies
                for evidence in _dicts(assembly.get("rejected_evidence"))
            )
            model_context = self._window_model_context(
                visual_package=visual_package,
                window_plan=window_plan,
                window_inputs=window_inputs,
                journal=journal,
                assemblies=assemblies,
                stitches=stitches,
                provider_config_hash=provider_config_hash,
            )
            hypothesis_set = self.contracts.build_vlm_hypothesis_set(
                parser_observation=parser_observation,
                binding_hypotheses=binding_inputs,
                rejected_evidence=rejected,
                model_context=model_context,
            )
            hypothesis_errors = self.contracts.validate_vlm_hypothesis_set(
                parser_observation=parser_observation,
                hypothesis_set=hypothesis_set,
            )
            if hypothesis_errors:
                raise PdfStructuralRepairRuntimeError(hypothesis_errors[0])
            repeatability = self.solver.build_repeatability_record(
                parser_observation=parser_observation,
                vlm_hypothesis_set=hypothesis_set,
            )
            consensus = self.solver.solve(
                parser_observation=parser_observation,
                vlm_hypothesis_set=hypothesis_set,
                historical_repeatability=repeatability,
            )
            repeated = self.solver.solve(
                parser_observation=copy.deepcopy(parser_observation),
                vlm_hypothesis_set=copy.deepcopy(hypothesis_set),
                historical_repeatability=copy.deepcopy(repeatability),
            )
            if consensus != repeated:
                raise PdfStructuralRepairRuntimeError(
                    "pdf_structural_repair_solver_nondeterministic"
                )
            if consensus.get("terminal_status") == "accepted_supplied_consensus":
                accepted_binding = self.solver.binding_from_accepted_consensus(
                    parser_observation=parser_observation,
                    consensus_result=consensus,
                    vlm_hypothesis_set=hypothesis_set,
                    evidence_package=visual_package,
                )
                materialization = self.materializer.materialize(
                    evidence_package=visual_package,
                    binding_output=accepted_binding,
                )

        runtime_terminal = (
            "preflight_blocked"
            if preflight_reason
            in {
                "pdf_structural_repair_count_tokens_failed",
                "pdf_structural_repair_counted_input_budget_exceeded",
            }
            else str(
                _object(consensus).get("terminal_status")
                or "no_valid_consensus"
            )
        )
        result = {
            "schema_version": PDF_STRUCTURAL_REPAIR_WINDOWED_RUNTIME_RESULT_SCHEMA,
            "policy_version": self.config.policy_version,
            "policy_configuration_hash": sha256_json(asdict(self.config)),
            "run_id": run_id,
            "target_id": target_id,
            "package_id": visual_package.get("package_id"),
            "package_hash": visual_package.get("package_hash"),
            "execution_mode": "vertical_atom_windows",
            "window_plan": copy.deepcopy(window_plan),
            "window_stitches": copy.deepcopy(stitches),
            "provider_qualification": copy.deepcopy(provider_qualification),
            "journal": journal,
            "hypothesis_set": hypothesis_set,
            "repeatability": repeatability,
            "consensus_result": consensus,
            "accepted_binding": accepted_binding,
            "materialization": materialization,
            "runtime_terminal_status": runtime_terminal,
            "new_provider_count_token_calls": sum(
                item.get("provider_count_token_call_performed") is True
                for item in journal
            ),
            "new_provider_generate_calls": sum(
                item.get("provider_generate_call_performed") is True
                for item in journal
            ),
            "safe_summary": {},
        }
        result["safe_summary"] = self._window_safe_summary(
            result=result,
            visual_package=visual_package,
            failure_reason=(
                preflight_reason
                or next(iter(sorted(evidence_failure_reasons)), None)
            ),
        )
        result["result_checksum"] = _result_checksum(result)
        result["safe_summary"]["result_checksum_ref"] = result["result_checksum"]
        errors = self.validate_result(result)
        if errors:
            raise PdfStructuralRepairRuntimeError(errors[0])
        return result

    def run_continuation_group(
        self,
        *,
        continuation_group_id: str,
        fragments: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Join two independently accepted page fragments without provider calls."""

        checked = self._validate_continuation_fragments(
            continuation_group_id=continuation_group_id,
            fragments=fragments,
        )
        contract_fragments: list[dict[str, Any]] = []
        fragment_evidence: list[dict[str, Any]] = []
        fragment_materializations: list[dict[str, Any]] = []
        fragment_target_ids: list[str] = []
        fragment_result_checksums: list[str] = []
        shared_column_count = int(
            _object(checked[0]["runtime_result"].get("accepted_binding")).get(
                "column_count"
            )
            or 0
        )
        for fragment_order, fragment in enumerate(checked, start=1):
            observation = fragment["parser_observation"]
            runtime_result = fragment["runtime_result"]
            binding = _object(runtime_result.get("accepted_binding"))
            page_number = int(observation["page_number"])
            repeated_header_policy = (
                "source_header"
                if binding.get("header_rows")
                else "no_repeated_header"
            )
            contract_fragments.append(
                {
                    "fragment_order": fragment_order,
                    "page_number": page_number,
                    "table_ref": observation["table_ref"],
                    "repeated_header_policy": repeated_header_policy,
                }
            )
            fragment_evidence.append(
                self.contracts.build_continuation_fragment_evidence(
                    parser_observation=observation,
                    consensus_result=_object(
                        runtime_result.get("consensus_result")
                    ),
                    binding_output=binding,
                    fragment_order=fragment_order,
                    page_number=page_number,
                    repeated_header_policy=repeated_header_policy,
                )
            )
            fragment_materializations.append(
                copy.deepcopy(_object(runtime_result.get("materialization")))
            )
            fragment_target_ids.append(str(fragment["target_id"]))
            fragment_result_checksums.append(
                str(runtime_result["result_checksum"])
            )

        continuation_contract = self.contracts.build_continuation_contract(
            continuation_group_id=continuation_group_id,
            fragments=contract_fragments,
            shared_column_count=shared_column_count,
            subtotal_policy="preserve_fragment_subtotals",
            duplicate_row_policy="forbid",
        )
        consensus = self.solver.solve_continuation(
            continuation_contract=continuation_contract,
            fragment_results=[
                copy.deepcopy(_object(item["runtime_result"].get("consensus_result")))
                for item in checked
            ],
            fragment_evidence=fragment_evidence,
        )
        repeated = self.solver.solve_continuation(
            continuation_contract=copy.deepcopy(continuation_contract),
            fragment_results=[
                copy.deepcopy(_object(item["runtime_result"].get("consensus_result")))
                for item in checked
            ],
            fragment_evidence=copy.deepcopy(fragment_evidence),
        )
        if consensus != repeated:
            raise PdfStructuralRepairRuntimeError(
                "pdf_structural_repair_continuation_solver_nondeterministic"
            )
        consensus_errors = self.solver.validate_continuation_result(consensus)
        if consensus_errors:
            raise PdfStructuralRepairRuntimeError(consensus_errors[0])

        materialization: dict[str, Any] | None = None
        private_failure_code: str | None = None
        runtime_terminal = str(
            consensus.get("terminal_status") or "no_valid_consensus"
        )
        if runtime_terminal == "accepted_supplied_consensus":
            try:
                materialization = self.materializer.materialize_continuation(
                    continuation_result=consensus,
                    fragment_evidence=fragment_evidence,
                    fragment_materializations=fragment_materializations,
                )
                materialization_errors = (
                    self.materializer.validate_continuation_materialization(
                        materialization
                    )
                )
                if materialization_errors:
                    raise PdfHybridMaterializationError(
                        materialization_errors[0]
                    )
            except PdfHybridMaterializationError as exc:
                materialization = None
                private_failure_code = str(getattr(exc, "code", "") or exc)
                runtime_terminal = "materialization_failed"

        safe_reasons = []
        if runtime_terminal == "materialization_failed":
            safe_reasons.append(
                "pdf_structural_repair_continuation_materialization_failed"
            )
        elif runtime_terminal == "incomplete_evidence":
            safe_reasons.append(
                "pdf_structural_repair_continuation_incomplete_evidence"
            )
        elif runtime_terminal == "ambiguous_multiple_consensus":
            safe_reasons.append(
                "pdf_structural_repair_continuation_supplied_consensus_ambiguous"
            )
        elif runtime_terminal == "unsupported":
            safe_reasons.append(
                "pdf_structural_repair_continuation_consensus_unsupported"
            )
        elif runtime_terminal != "accepted_supplied_consensus":
            safe_reasons.append(
                "pdf_structural_repair_continuation_not_accepted_supplied_scope"
            )
        all_candidates_accounted = bool(
            materialization
            and materialization.get("candidate_ownership_exact") is True
            and not materialization.get("omitted_candidate_ids")
            and not materialization.get("extra_candidate_ids")
            and not materialization.get("duplicate_candidate_ids")
            and not materialization.get("structural_provenance_conflicts")
        )
        safe_summary = {
            "schema_version": (
                "broker_reports_pdf_structural_repair_continuation_safe_summary_v1"
            ),
            "continuation_group_id": continuation_group_id,
            "runtime_terminal_status": runtime_terminal,
            "reason_codes": safe_reasons,
            "fragment_count": len(checked),
            "row_count": (
                materialization.get("row_count") if materialization else None
            ),
            "column_count": (
                materialization.get("column_count") if materialization else None
            ),
            "all_candidates_accounted": all_candidates_accounted,
            "model_invented_values_total": (
                materialization.get("model_invented_values_total")
                if materialization
                else None
            ),
            "count_token_calls": 0,
            "generate_calls": 0,
            "production_authority": False,
        }
        result = {
            "schema_version": PDF_STRUCTURAL_REPAIR_CONTINUATION_RESULT_SCHEMA,
            "policy_version": self.config.policy_version,
            "policy_configuration_hash": sha256_json(asdict(self.config)),
            "continuation_group_id": continuation_group_id,
            "continuation_contract": continuation_contract,
            "fragment_target_ids": fragment_target_ids,
            "fragment_runtime_result_checksums": fragment_result_checksums,
            "fragment_evidence": fragment_evidence,
            "continuation_consensus_result": consensus,
            "materialization": materialization,
            "runtime_terminal_status": runtime_terminal,
            "private_failure_code": private_failure_code,
            "new_provider_count_token_calls": 0,
            "new_provider_generate_calls": 0,
            "safe_summary": safe_summary,
            "authority_state": "non_authoritative",
            "production_ready": False,
            "production_gate2_selection_changed": False,
        }
        result["result_checksum"] = _continuation_result_checksum(result)
        errors = self.validate_continuation_group_result(result)
        if errors:
            raise PdfStructuralRepairRuntimeError(errors[0])
        return result

    def validate_continuation_group_result(self, value: Any) -> list[str]:
        data = _object(value)
        errors: list[str] = []
        if set(data) != _CONTINUATION_RESULT_KEYS:
            return ["pdf_structural_repair_continuation_result_keys_invalid"]
        if (
            data.get("schema_version")
            != PDF_STRUCTURAL_REPAIR_CONTINUATION_RESULT_SCHEMA
            or data.get("policy_version") != self.config.policy_version
            or data.get("policy_configuration_hash")
            != sha256_json(asdict(self.config))
            or data.get("authority_state") != "non_authoritative"
            or data.get("production_ready") is not False
            or data.get("production_gate2_selection_changed") is not False
        ):
            errors.append(
                "pdf_structural_repair_continuation_result_identity_invalid"
            )
        safe = _object(data.get("safe_summary"))
        if set(safe) != _CONTINUATION_SAFE_SUMMARY_KEYS:
            errors.append(
                "pdf_structural_repair_continuation_safe_summary_keys_invalid"
            )
        if (
            any(
                code not in _CONTINUATION_SAFE_REASON_CODES
                for code in safe.get("reason_codes") or []
            )
            or safe.get("production_authority") is not False
            or safe.get("count_token_calls") != 0
            or safe.get("generate_calls") != 0
            or data.get("new_provider_count_token_calls") != 0
            or data.get("new_provider_generate_calls") != 0
        ):
            errors.append(
                "pdf_structural_repair_continuation_safe_summary_invalid"
            )
        consensus_errors = self.solver.validate_continuation_result(
            _object(data.get("continuation_consensus_result"))
        )
        if consensus_errors:
            errors.append(
                "pdf_structural_repair_continuation_consensus_invalid"
            )
        materialization = data.get("materialization")
        terminal = data.get("runtime_terminal_status")
        if terminal == "accepted_supplied_consensus":
            if not isinstance(materialization, dict) or (
                self.materializer.validate_continuation_materialization(
                    materialization
                )
            ):
                errors.append(
                    "pdf_structural_repair_continuation_materialization_invalid"
                )
            if (
                safe.get("all_candidates_accounted") is not True
                or safe.get("model_invented_values_total") != 0
            ):
                errors.append(
                    "pdf_structural_repair_continuation_safe_acceptance_invalid"
                )
        elif materialization is not None:
            errors.append(
                "pdf_structural_repair_continuation_terminal_materialization_invalid"
            )
        if data.get("result_checksum") != _continuation_result_checksum(data):
            errors.append(
                "pdf_structural_repair_continuation_result_checksum_invalid"
            )
        return sorted(set(errors))

    def _validate_continuation_fragments(
        self,
        *,
        continuation_group_id: str,
        fragments: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if (
            not isinstance(continuation_group_id, str)
            or not continuation_group_id
            or len(continuation_group_id) > 128
            or not isinstance(fragments, list)
            or len(fragments) != 2
            or any(
                not isinstance(item, dict)
                or set(item) != _CONTINUATION_FRAGMENT_INPUT_KEYS
                for item in fragments
            )
        ):
            raise PdfStructuralRepairRuntimeError(
                "pdf_structural_repair_continuation_input_invalid"
            )
        documents: set[str] = set()
        pdf_hashes: set[str] = set()
        pages: list[int] = []
        tables: set[str] = set()
        targets: set[str] = set()
        columns: set[int] = set()
        for fragment in fragments:
            target_id = str(fragment.get("target_id") or "")
            observation = _object(fragment.get("parser_observation"))
            package = _object(fragment.get("visual_package"))
            runtime_result = _object(fragment.get("runtime_result"))
            binding = _object(runtime_result.get("accepted_binding"))
            expected_provider_calls = _expected_provider_calls(runtime_result)
            package_errors = (
                self.ledger_visual.validate_ledger_package(
                    parser_observation=observation,
                    package=package,
                )
                if runtime_result.get("schema_version")
                == PDF_STRUCTURAL_REPAIR_WINDOWED_RUNTIME_RESULT_SCHEMA
                else self.visual.validate_package(
                    parser_observation=observation,
                    package=package,
                )
            )
            if (
                not target_id
                or fragment.get("repeat_history_ever_conflicted") is not False
                or self.contracts.validate_parser_observation(observation)
                or package_errors
                or self.validate_result(runtime_result)
                or runtime_result.get("target_id") != target_id
                or runtime_result.get("runtime_terminal_status")
                != "accepted_supplied_consensus"
                or runtime_result.get("accepted_binding") is None
                or runtime_result.get("materialization") is None
                or runtime_result.get("package_id") != package.get("package_id")
                or runtime_result.get("package_hash") != package.get("package_hash")
                or _object(runtime_result.get("safe_summary")).get(
                    "all_candidates_accounted"
                )
                is not True
                or _object(runtime_result.get("safe_summary")).get("hidden_retry")
                is not False
                or _object(runtime_result.get("safe_summary")).get(
                    "provider_failover"
                )
                is not False
                or runtime_result.get("new_provider_count_token_calls")
                != expected_provider_calls
                or runtime_result.get("new_provider_generate_calls")
                != expected_provider_calls
            ):
                raise PdfStructuralRepairRuntimeError(
                    "pdf_structural_repair_continuation_fragment_invalid"
                )
            documents.add(str(observation.get("document_ref") or ""))
            pdf_hashes.add(str(observation.get("pdf_sha256") or ""))
            pages.append(int(observation.get("page_number") or 0))
            tables.add(str(observation.get("table_ref") or ""))
            targets.add(target_id)
            columns.add(int(binding.get("column_count") or 0))
        if (
            len(documents) != 1
            or "" in documents
            or len(pdf_hashes) != 1
            or "" in pdf_hashes
            or len(tables) != 2
            or "" in tables
            or len(targets) != 2
            or pages[1] != pages[0] + 1
            or len(columns) != 1
            or min(columns) < 1
        ):
            raise PdfStructuralRepairRuntimeError(
                "pdf_structural_repair_continuation_fragment_scope_invalid"
            )
        return [copy.deepcopy(item) for item in fragments]

    def validate_result(self, value: Any) -> list[str]:
        data = _object(value)
        if data.get("schema_version") == PDF_VLM_PAGE_PROPOSAL_RESULT_SCHEMA:
            return self._validate_page_proposal_result(data)
        if data.get("schema_version") == PDF_VLM_GUIDED_INTAKE_RESULT_SCHEMA:
            return self._validate_guided_intake_result(data)
        if (
            data.get("schema_version")
            == PDF_STRUCTURAL_REPAIR_WINDOWED_RUNTIME_RESULT_SCHEMA
        ):
            return self._validate_windowed_result(data)
        errors: list[str] = []
        if set(data) != _RESULT_KEYS:
            errors.append("pdf_structural_repair_result_keys_invalid")
            return errors
        if (
            data.get("schema_version")
            != PDF_STRUCTURAL_REPAIR_RUNTIME_RESULT_SCHEMA
            or data.get("policy_version") != self.config.policy_version
            or data.get("policy_configuration_hash")
            != sha256_json(asdict(self.config))
        ):
            errors.append("pdf_structural_repair_result_identity_invalid")
        journal = data.get("journal")
        if (
            not isinstance(journal, list)
            or len(journal) > 2
            or any(not isinstance(item, dict) for item in journal)
        ):
            errors.append("pdf_structural_repair_journal_invalid")
        safe = _object(data.get("safe_summary"))
        if set(safe) != _SAFE_SUMMARY_KEYS:
            errors.append("pdf_structural_repair_safe_summary_keys_invalid")
        if any(
            code not in _SAFE_REASON_CODES for code in safe.get("reason_codes") or []
        ):
            errors.append("pdf_structural_repair_safe_reason_invalid")
        if safe.get("production_authority") is not False:
            errors.append("pdf_structural_repair_shadow_authority_invalid")
        if any(
            safe.get(key) != expected
            for key, expected in _safe_consensus_semantics(
                _object(data.get("consensus_result"))
            ).items()
        ):
            errors.append("pdf_structural_repair_safe_consensus_semantics_invalid")
        stored = data.get("result_checksum")
        if stored != _result_checksum(data):
            errors.append("pdf_structural_repair_result_checksum_invalid")
        if safe.get("result_checksum_ref") != stored:
            errors.append("pdf_structural_repair_safe_checksum_ref_invalid")
        return sorted(set(errors))

    def _validate_windowed_result(self, data: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        if set(data) != _WINDOWED_RESULT_KEYS:
            return ["pdf_structural_repair_window_result_keys_invalid"]
        if (
            data.get("schema_version")
            != PDF_STRUCTURAL_REPAIR_WINDOWED_RUNTIME_RESULT_SCHEMA
            or data.get("policy_version") != self.config.policy_version
            or data.get("policy_configuration_hash")
            != sha256_json(asdict(self.config))
            or data.get("execution_mode") != "vertical_atom_windows"
        ):
            errors.append("pdf_structural_repair_window_result_identity_invalid")
        plan = _object(data.get("window_plan"))
        plan_errors = self.windowing.validate_plan_integrity(plan)
        if plan_errors:
            errors.append("pdf_structural_repair_window_plan_invalid")
        window_count = _strict_int(plan.get("window_count"))
        expected_calls = 2 * window_count
        journal = _dicts(data.get("journal"))
        if (
            not isinstance(data.get("journal"), list)
            or len(journal) != len(data.get("journal") or [])
            or len(journal) > expected_calls
            or any(
                item.get("window_id")
                not in {
                    window.get("window_id")
                    for window in _dicts(plan.get("windows"))
                }
                for item in journal
            )
        ):
            errors.append("pdf_structural_repair_window_journal_invalid")
        stitches = _dicts(data.get("window_stitches"))
        if (
            not isinstance(data.get("window_stitches"), list)
            or len(stitches) > 2
            or any(self.windowing.validate_stitch(item) for item in stitches)
            or [item.get("attempt_number") for item in stitches]
            != sorted(
                {
                    item.get("attempt_number")
                    for item in stitches
                    if item.get("attempt_number") in _ATTEMPTS
                }
            )
        ):
            errors.append("pdf_structural_repair_window_stitch_invalid")
        journal_attempt_ids = {
            attempt_number: [
                str(_object(item.get("provider_attempt")).get("attempt_id") or "")
                for item in journal
                if item.get("attempt_number") == attempt_number
                and item.get("provider_generate_call_performed") is True
            ]
            for attempt_number in _ATTEMPTS
        }
        if any(
            item.get("window_attempt_ids")
            != journal_attempt_ids.get(int(item.get("attempt_number") or 0))
            for item in stitches
        ):
            errors.append("pdf_structural_repair_window_lineage_invalid")
        safe = _object(data.get("safe_summary"))
        if set(safe) != _SAFE_SUMMARY_KEYS:
            errors.append("pdf_structural_repair_safe_summary_keys_invalid")
        if any(
            code not in _SAFE_REASON_CODES for code in safe.get("reason_codes") or []
        ):
            errors.append("pdf_structural_repair_safe_reason_invalid")
        if any(
            safe.get(key) != expected
            for key, expected in _safe_consensus_semantics(
                _object(data.get("consensus_result"))
            ).items()
        ):
            errors.append("pdf_structural_repair_safe_consensus_semantics_invalid")
        counted_calls = sum(
            item.get("provider_count_token_call_performed") is True
            for item in journal
        )
        generated_calls = sum(
            item.get("provider_generate_call_performed") is True
            for item in journal
        )
        if (
            data.get("new_provider_count_token_calls") != counted_calls
            or data.get("new_provider_generate_calls") != generated_calls
            or safe.get("count_token_calls") != counted_calls
            or safe.get("generate_calls") != generated_calls
            or safe.get("attempts_expected") != expected_calls
            or safe.get("attempts_recorded") != len(journal)
            or safe.get("production_authority") is not False
        ):
            errors.append("pdf_structural_repair_window_accounting_invalid")
        if data.get("runtime_terminal_status") == "accepted_supplied_consensus" and (
            len(journal) != expected_calls
            or counted_calls != expected_calls
            or generated_calls != expected_calls
            or len(stitches) != 2
            or data.get("accepted_binding") is None
            or data.get("materialization") is None
            or safe.get("all_candidates_accounted") is not True
            or safe.get("hidden_retry") is not False
            or safe.get("provider_failover") is not False
        ):
            errors.append("pdf_structural_repair_window_acceptance_invalid")
        stored = data.get("result_checksum")
        if stored != _result_checksum(data):
            errors.append("pdf_structural_repair_result_checksum_invalid")
        if safe.get("result_checksum_ref") != stored:
            errors.append("pdf_structural_repair_safe_checksum_ref_invalid")
        return sorted(set(errors))

    def _validate_page_proposal_result(
        self, data: dict[str, Any]
    ) -> list[str]:
        errors: list[str] = []
        if set(data) != _PAGE_PROPOSAL_RESULT_KEYS:
            return ["pdf_vlm_page_proposal_result_keys_invalid"]
        if (
            data.get("schema_version") != PDF_VLM_PAGE_PROPOSAL_RESULT_SCHEMA
            or data.get("policy_version") != self.config.policy_version
            or data.get("policy_configuration_hash")
            != sha256_json(asdict(self.config))
            or data.get("execution_contract")
            != _PAGE_PROPOSAL_EXECUTION_CONTRACT
            or not isinstance(data.get("package_id"), str)
            or not data.get("package_id")
            or not isinstance(data.get("package_hash"), str)
            or not data.get("package_hash")
        ):
            errors.append("pdf_vlm_page_proposal_result_identity_invalid")
        journal = _dicts(data.get("journal"))
        if (
            not isinstance(data.get("journal"), list)
            or len(journal) != 1
            or len(journal) != len(data.get("journal") or [])
            or set(journal[0]) != _PAGE_PROPOSAL_JOURNAL_KEYS
            or journal[0].get("attempt_number") != 1
            or journal[0].get("target_id") != data.get("target_id")
            or journal[0].get("assembly") is not None
        ):
            errors.append("pdf_vlm_page_proposal_journal_invalid")
        counted_calls = sum(
            item.get("provider_count_token_call_performed") is True
            for item in journal
        )
        generated_calls = sum(
            item.get("provider_generate_call_performed") is True
            for item in journal
        )
        if (
            counted_calls != 1
            or generated_calls not in {0, 1}
            or data.get("new_provider_count_token_calls") != counted_calls
            or data.get("new_provider_generate_calls") != generated_calls
        ):
            errors.append("pdf_vlm_page_proposal_provider_accounting_invalid")
        terminal = data.get("runtime_terminal_status")
        proposal = data.get("proposal")
        table_presence = data.get("table_presence")
        if terminal not in {
            "preflight_blocked",
            "provider_failed",
            "proposal_invalid",
            "proposal_persisted",
        }:
            errors.append("pdf_vlm_page_proposal_terminal_invalid")
        if terminal == "preflight_blocked":
            if generated_calls != 0 or proposal is not None or table_presence != "not_evaluated":
                errors.append("pdf_vlm_page_proposal_preflight_contract_invalid")
        elif terminal in {"provider_failed", "proposal_invalid"}:
            if generated_calls != 1 or proposal is not None or table_presence != "not_evaluated":
                errors.append("pdf_vlm_page_proposal_failure_contract_invalid")
        elif terminal == "proposal_persisted":
            if generated_calls != 1 or not isinstance(proposal, dict):
                errors.append("pdf_vlm_page_proposal_persistence_invalid")
            else:
                try:
                    parsed = self.visual.parse_region_proposal_response(
                        proposal,
                        expected_package_id=str(data.get("package_id") or ""),
                        expected_proposal_scope="page_level",
                    )
                except ValueError:
                    errors.append("pdf_vlm_page_proposal_persistence_invalid")
                else:
                    if (
                        parsed != proposal
                        or table_presence != parsed.get("table_presence")
                    ):
                        errors.append("pdf_vlm_page_proposal_persistence_invalid")
        safe = _object(data.get("safe_summary"))
        reason_codes = safe.get("reason_codes")
        attempts = [
            _object(item.get("provider_attempt"))
            for item in journal
            if _object(item.get("provider_attempt"))
        ]
        hidden_retry = any(
            attempt.get("hidden_retry") is not False for attempt in attempts
        )
        provider_failover = any(
            attempt.get("provider_failover") is not False
            for attempt in attempts
        )
        expected_regions = (
            len(_dicts(_object(proposal).get("regions")))
            if terminal == "proposal_persisted"
            else 0
        )
        if (
            set(safe) != _PAGE_PROPOSAL_SAFE_SUMMARY_KEYS
            or safe.get("schema_version")
            != PDF_VLM_PAGE_PROPOSAL_SAFE_SUMMARY_SCHEMA
            or safe.get("target_id") != data.get("target_id")
            or safe.get("runtime_terminal_status") != terminal
            or not isinstance(reason_codes, list)
            or reason_codes != sorted(set(reason_codes))
            or any(code not in _PAGE_PROPOSAL_REASON_CODES for code in reason_codes)
            or safe.get("count_token_calls") != counted_calls
            or safe.get("generate_calls") != generated_calls
            or safe.get("table_presence") != table_presence
            or safe.get("regions_proposed") != expected_regions
            or safe.get("input_atom_count") != 0
            or safe.get("proposal_persisted")
            is not (terminal == "proposal_persisted")
            or safe.get("hidden_retry") is not hidden_retry
            or safe.get("provider_failover") is not provider_failover
            or safe.get("default_enabled") is not False
            or safe.get("production_authority") is not False
        ):
            errors.append("pdf_vlm_page_proposal_safe_summary_invalid")
        failure_code = journal[0].get("failure_code") if journal else None
        expected_reasons = [failure_code] if failure_code else []
        if reason_codes != expected_reasons:
            errors.append("pdf_vlm_page_proposal_reason_binding_invalid")
        if terminal == "preflight_blocked" and failure_code not in {
            "pdf_structural_repair_count_tokens_failed",
            "pdf_structural_repair_counted_input_budget_exceeded",
        }:
            errors.append("pdf_vlm_page_proposal_failure_reason_invalid")
        elif terminal == "provider_failed" and failure_code not in {
            "pdf_structural_repair_provider_attempt_failed",
            "pdf_structural_repair_provider_lineage_invalid",
            "pdf_structural_repair_provider_accounting_invalid",
            "pdf_structural_repair_unknown_failure",
        }:
            errors.append("pdf_vlm_page_proposal_failure_reason_invalid")
        elif (
            terminal == "proposal_invalid"
            and failure_code != "pdf_vlm_page_proposal_response_invalid"
        ):
            errors.append("pdf_vlm_page_proposal_failure_reason_invalid")
        elif terminal == "proposal_persisted" and failure_code is not None:
            errors.append("pdf_vlm_page_proposal_failure_reason_invalid")
        if (
            data.get("authority_state") != "shadow_non_authoritative"
            or data.get("default_enabled") is not False
            or data.get("production_ready") is not False
            or data.get("production_gate2_selection_changed") is not False
        ):
            errors.append("pdf_vlm_page_proposal_authority_invalid")
        stored = data.get("result_checksum")
        if stored != _result_checksum(data):
            errors.append("pdf_vlm_page_proposal_result_checksum_invalid")
        if safe.get("result_checksum_ref") != stored:
            errors.append("pdf_vlm_page_proposal_safe_checksum_ref_invalid")
        return sorted(set(errors))

    def _validate_guided_intake_result(
        self, data: dict[str, Any]
    ) -> list[str]:
        errors: list[str] = []
        if set(data) != _GUIDED_INTAKE_RESULT_KEYS:
            return ["pdf_vlm_guided_intake_result_keys_invalid"]
        if (
            data.get("schema_version") != PDF_VLM_GUIDED_INTAKE_RESULT_SCHEMA
            or data.get("policy_version") != self.config.policy_version
            or data.get("policy_configuration_hash")
            != sha256_json(asdict(self.config))
            or data.get("execution_contract")
            != _GUIDED_INTAKE_EXECUTION_CONTRACT
        ):
            errors.append("pdf_vlm_guided_intake_result_identity_invalid")
        journal = _dicts(data.get("journal"))
        if (
            not isinstance(data.get("journal"), list)
            or len(journal) != len(data.get("journal") or [])
            or len(journal) != 1
            or journal[0].get("attempt_number") != 1
        ):
            errors.append("pdf_vlm_guided_intake_journal_invalid")
        counted_calls = sum(
            item.get("provider_count_token_call_performed") is True
            for item in journal
        )
        generated_calls = sum(
            item.get("provider_generate_call_performed") is True
            for item in journal
        )
        if (
            data.get("new_provider_count_token_calls") != counted_calls
            or data.get("new_provider_generate_calls") != generated_calls
            or counted_calls != 1
            or generated_calls not in {0, 1}
        ):
            errors.append("pdf_vlm_guided_intake_provider_accounting_invalid")
        post = _object(data.get("post_validation"))
        if set(post) != _GUIDED_INTAKE_POST_VALIDATION_KEYS:
            errors.append("pdf_vlm_guided_intake_post_validation_keys_invalid")
        safe = _object(data.get("safe_summary"))
        if (
            set(safe) != _GUIDED_INTAKE_SAFE_SUMMARY_KEYS
            or safe.get("schema_version")
            != PDF_VLM_GUIDED_INTAKE_SAFE_SUMMARY_SCHEMA
            or safe.get("count_token_calls") != counted_calls
            or safe.get("generate_calls") != generated_calls
            or safe.get("production_authority") is not False
        ):
            errors.append("pdf_vlm_guided_intake_safe_summary_invalid")
        terminal = data.get("runtime_terminal_status")
        if terminal not in {
            "preflight_blocked",
            "provider_failed",
            "proposal_absent",
            "proposal_unsupported",
            "proposal_ambiguous",
            "validation_blocked",
            "accepted_physical_structure",
        }:
            errors.append("pdf_vlm_guided_intake_terminal_invalid")
        if data.get("proposal_decision") not in {
            "not_evaluated",
            "bound",
            "ambiguous",
            "unsupported",
        }:
            errors.append("pdf_vlm_guided_intake_proposal_decision_invalid")
        raw_response = (
            _object(journal[0].get("topology_response")) if journal else {}
        )
        if raw_response.get("proposal_scope") == "candidate_crop":
            try:
                region_response = self.visual.parse_region_proposal_response(
                    raw_response,
                    expected_package_id=str(data.get("package_id") or ""),
                    expected_proposal_scope="candidate_crop",
                )
            except ValueError:
                if terminal != "validation_blocked":
                    errors.append(
                        "pdf_vlm_guided_intake_region_response_invalid"
                    )
            else:
                presence = region_response.get("table_presence")
                if presence == "absent" and (
                    terminal != "proposal_absent"
                    or data.get("proposal_decision") != "unsupported"
                ):
                    errors.append(
                        "pdf_vlm_guided_intake_region_presence_invalid"
                    )
                elif presence == "uncertain" and (
                    terminal != "proposal_ambiguous"
                    or data.get("proposal_decision") != "ambiguous"
                ):
                    errors.append(
                        "pdf_vlm_guided_intake_region_presence_invalid"
                    )
                elif presence == "present":
                    regions = _dicts(region_response.get("regions"))
                    full_scope = bool(
                        len(regions) == 1
                        and regions[0].get("bbox")
                        == [0.0, 0.0, 1.0, 1.0]
                    )
                    if not full_scope and (
                        terminal != "validation_blocked"
                        or "pdf_vlm_guided_intake_region_reselection_required"
                        not in post.get("reason_codes", [])
                    ):
                        errors.append(
                            "pdf_vlm_guided_intake_region_reselection_invalid"
                        )
                    if (
                        terminal == "accepted_physical_structure"
                        and not full_scope
                    ):
                        errors.append(
                            "pdf_vlm_guided_intake_region_acceptance_invalid"
                        )
        if (
            data.get("authority_state") != "non_authoritative"
            or data.get("production_ready") is not False
            or data.get("production_gate2_selection_changed") is not False
        ):
            errors.append("pdf_vlm_guided_intake_authority_invalid")
        if terminal == "accepted_physical_structure":
            if (
                generated_calls != 1
                or data.get("proposal_decision") != "bound"
                or data.get("accepted_binding") is None
                or data.get("materialization") is None
                or post.get("passed") is not True
                or safe.get("all_candidates_accounted") is not True
                or safe.get("model_invented_values_total") != 0
                or safe.get("hidden_retry") is not False
                or safe.get("provider_failover") is not False
            ):
                errors.append("pdf_vlm_guided_intake_acceptance_invalid")
        elif (
            data.get("accepted_binding") is not None
            or data.get("materialization") is not None
            or post.get("passed") is True
        ):
            errors.append("pdf_vlm_guided_intake_blocked_materialization_invalid")
        unsigned = dict(data)
        stored = unsigned.pop("result_checksum", None)
        if stored != sha256_json(unsigned):
            errors.append("pdf_vlm_guided_intake_result_checksum_invalid")
        return sorted(set(errors))

    def _page_proposal_result(
        self,
        *,
        run_id: str,
        target_id: str,
        visual_package: dict[str, Any],
        provider_qualification: dict[str, Any],
        journal: list[dict[str, Any]],
        proposal: dict[str, Any] | None,
        table_presence: str,
        terminal: str,
    ) -> dict[str, Any]:
        count_calls = sum(
            item.get("provider_count_token_call_performed") is True
            for item in journal
        )
        generate_calls = sum(
            item.get("provider_generate_call_performed") is True
            for item in journal
        )
        attempts = [
            _object(item.get("provider_attempt"))
            for item in journal
            if _object(item.get("provider_attempt"))
        ]
        reason_codes = sorted(
            {
                str(item.get("failure_code"))
                for item in journal
                if item.get("failure_code")
            }
        )
        regions = _dicts(_object(proposal).get("regions"))
        safe_summary = {
            "schema_version": PDF_VLM_PAGE_PROPOSAL_SAFE_SUMMARY_SCHEMA,
            "target_id": target_id,
            "runtime_terminal_status": terminal,
            "reason_codes": reason_codes,
            "count_token_calls": count_calls,
            "generate_calls": generate_calls,
            "table_presence": table_presence,
            "regions_proposed": len(regions),
            "input_atom_count": _object(
                visual_package.get("component_accounting")
            ).get("atom_count"),
            "proposal_persisted": proposal is not None,
            "hidden_retry": any(
                attempt.get("hidden_retry") is not False
                for attempt in attempts
            ),
            "provider_failover": any(
                attempt.get("provider_failover") is not False
                for attempt in attempts
            ),
            "default_enabled": False,
            "production_authority": False,
            "result_checksum_ref": None,
        }
        result = {
            "schema_version": PDF_VLM_PAGE_PROPOSAL_RESULT_SCHEMA,
            "policy_version": self.config.policy_version,
            "policy_configuration_hash": sha256_json(asdict(self.config)),
            "run_id": run_id,
            "target_id": target_id,
            "execution_contract": _PAGE_PROPOSAL_EXECUTION_CONTRACT,
            "package_id": visual_package.get("package_id"),
            "package_hash": visual_package.get("package_hash"),
            "provider_qualification": copy.deepcopy(provider_qualification),
            "journal": copy.deepcopy(journal),
            "proposal": copy.deepcopy(proposal),
            "table_presence": table_presence,
            "runtime_terminal_status": terminal,
            "new_provider_count_token_calls": count_calls,
            "new_provider_generate_calls": generate_calls,
            "authority_state": "shadow_non_authoritative",
            "default_enabled": False,
            "production_ready": False,
            "production_gate2_selection_changed": False,
            "safe_summary": safe_summary,
        }
        result["result_checksum"] = _result_checksum(result)
        result["safe_summary"]["result_checksum_ref"] = result[
            "result_checksum"
        ]
        validation_errors = self._validate_page_proposal_result(result)
        if validation_errors:
            raise PdfStructuralRepairRuntimeError(validation_errors[0])
        return result

    def _validate_page_proposal_input(
        self,
        *,
        target_id: str,
        visual_package: dict[str, Any],
        png_bytes: bytes,
        provider_qualification: dict[str, Any],
    ) -> None:
        package_errors = self.visual.validate_region_proposal_package(
            visual_package
        )
        crop = _object(visual_package.get("crop_identity"))
        accounting = _object(visual_package.get("component_accounting"))
        model_view = _object(visual_package.get("model_facing"))
        if (
            not target_id
            or len(target_id) > 96
            or package_errors
            or visual_package.get("proposal_scope") != "page_level"
            or model_view.get("atoms") != []
            or accounting.get("atom_count") != 0
            or not isinstance(png_bytes, bytes)
            or not png_bytes
            or len(png_bytes) > self.config.maximum_image_bytes
            or hashlib.sha256(png_bytes).hexdigest()
            != crop.get("crop_sha256")
        ):
            raise PdfStructuralRepairRuntimeError(
                "pdf_structural_repair_input_invalid"
            )
        if (
            provider_qualification.get("status") != "qualified"
            or provider_qualification.get("requested_model_id")
            != self.config.model_id
            or provider_qualification.get("resolved_model_id")
            != self.config.model_id
            or provider_qualification.get("exact_model_match") is not True
            or provider_qualification.get("hidden_retry") is not False
            or provider_qualification.get("provider_failover") is not False
        ):
            raise PdfStructuralRepairRuntimeError(
                "pdf_structural_repair_provider_not_qualified"
            )

    def _validate_guided_intake_input(
        self,
        *,
        target_id: str,
        parser_observation: dict[str, Any],
        parser_geometry_observation: dict[str, Any],
        visual_package: dict[str, Any],
        png_bytes: bytes,
        provider_qualification: dict[str, Any],
    ) -> None:
        if not target_id or len(target_id) > 96:
            raise PdfStructuralRepairRuntimeError(
                "pdf_structural_repair_input_invalid"
            )
        common_errors = [
            *self.contracts.validate_parser_observation(parser_observation),
            *self.parser_geometry.validate_observation(
                parser_geometry_observation
            ),
        ]
        package_errors = self.visual.validate_region_proposal_package(
            visual_package
        )
        if (
            visual_package.get("proposal_scope") == "candidate_crop"
            and not package_errors
        ):
            self._guided_legacy_package_from_region(
                parser_observation=parser_observation,
                region_package=visual_package,
            )
        crop = _object(visual_package.get("crop_identity"))
        accounting = _object(visual_package.get("component_accounting"))
        atom_count = accounting.get("atom_count")
        if (
            common_errors
            or package_errors
            or visual_package.get("proposal_scope") != "candidate_crop"
            or not _is_strict_non_negative_int(atom_count)
            or atom_count < 1
            or atom_count > self.visual.config.maximum_atoms
            or accounting.get("model_json_bytes")
            > self.visual.config.maximum_model_json_bytes
            or not isinstance(png_bytes, bytes)
            or not png_bytes
            or len(png_bytes) > self.config.maximum_image_bytes
            or hashlib.sha256(png_bytes).hexdigest()
            != crop.get("crop_sha256")
        ):
            raise PdfStructuralRepairRuntimeError(
                "pdf_structural_repair_input_invalid"
            )
        if (
            provider_qualification.get("status") != "qualified"
            or provider_qualification.get("requested_model_id")
            != self.config.model_id
            or provider_qualification.get("resolved_model_id")
            != self.config.model_id
            or provider_qualification.get("exact_model_match") is not True
            or provider_qualification.get("hidden_retry") is not False
            or provider_qualification.get("provider_failover") is not False
        ):
            raise PdfStructuralRepairRuntimeError(
                "pdf_structural_repair_provider_not_qualified"
            )

    def _guided_acceptance_reasons(
        self,
        *,
        parser_observation: dict[str, Any],
        visual_package: dict[str, Any],
        parsed_response: dict[str, Any],
        assembly: dict[str, Any],
    ) -> list[str]:
        reasons: list[str] = []
        hypotheses = _dicts(parsed_response.get("hypotheses"))
        bindings = _dicts(assembly.get("binding_hypotheses"))
        if (
            parsed_response.get("decision") != "bound"
            or parsed_response.get("alternatives_complete") is not True
            or len(hypotheses) != 1
            or hypotheses[0].get("uncertainty_codes")
        ):
            reasons.append("pdf_vlm_guided_intake_single_bound_hypothesis_required")
        if (
            assembly.get("reconstruction_status") != "assembled"
            or len(bindings) != 1
            or assembly.get("rejected_evidence")
            or assembly.get("regional_issues")
        ):
            reasons.append("pdf_vlm_guided_intake_assembly_not_uniquely_bound")
        source = _object(assembly.get("source_accounting"))
        if source.get("all_bound_alternatives_exactly_once") is not True:
            reasons.append("pdf_vlm_guided_intake_candidate_ownership_invalid")
        adjustments = _dicts(assembly.get("structural_adjustments"))
        forbidden_adjustments = [
            item
            for item in adjustments
            if item.get("operation")
            != "replace_visual_boundary_with_parser_geometry"
        ]
        if forbidden_adjustments:
            reasons.append("pdf_vlm_guided_intake_proposal_repair_forbidden")
        if len(bindings) == 1:
            binding = _object(bindings[0].get("binding_output"))
            if binding.get("decision") != "bound":
                reasons.append("pdf_vlm_guided_intake_binding_not_bound")
            if not self._guided_binding_bbox_compatible(
                parser_observation=parser_observation,
                visual_package=visual_package,
                binding_hypothesis=bindings[0],
            ):
                reasons.append(
                    "pdf_vlm_guided_intake_atom_bbox_crosses_proposed_boundary"
                )
        if (
            assembly.get("package_id") != visual_package.get("package_id")
            or assembly.get("package_hash") != visual_package.get("package_hash")
            or assembly.get("parser_observation_checksum")
            != parser_observation.get("observation_checksum")
        ):
            reasons.append("pdf_vlm_guided_intake_crop_or_parser_identity_mismatch")
        return sorted(set(reasons))

    def _guided_legacy_package_from_region(
        self,
        *,
        parser_observation: dict[str, Any],
        region_package: dict[str, Any],
    ) -> dict[str, Any]:
        crop = _object(region_package.get("crop_identity"))
        crop_manifest = {
            "crop_id": crop.get("crop_id"),
            "pdf_sha256": region_package.get("pdf_sha256"),
            "page_number": region_package.get("page_number"),
            "table_ref": region_package.get("table_ref"),
            "declared_table_bbox": copy.deepcopy(
                crop.get("declared_table_bbox")
            ),
            "rendered_bbox": copy.deepcopy(crop.get("rendered_bbox")),
            "page_rotation": crop.get("page_rotation"),
            "applied_rotation": 0,
            "padding_points": crop.get("padding_points"),
            "dpi": crop.get("dpi"),
            "width": crop.get("width"),
            "height": crop.get("height"),
            "png_bytes": crop.get("png_bytes"),
            "png_sha256": crop.get("crop_sha256"),
            "manifest_hash": crop.get("manifest_hash"),
        }
        try:
            legacy = self.visual.build_package(
                parser_observation=parser_observation,
                crop_manifest=crop_manifest,
            )
        except ValueError as exc:
            raise PdfStructuralRepairRuntimeError(
                "pdf_structural_repair_input_invalid"
            ) from exc
        identity_fields = (
            "crop_identity",
            "parser_observation_id",
            "parser_observation_checksum",
            "neutral_atom_to_candidate_id",
            "candidate_dictionary_hash",
            "private_candidate_dictionary",
        )
        if any(
            legacy.get(field) != region_package.get(field)
            for field in identity_fields
        ):
            raise PdfStructuralRepairRuntimeError(
                "pdf_structural_repair_input_invalid"
            )
        legacy_atoms = _dicts(_object(legacy.get("model_facing")).get("atoms"))
        region_atoms = _dicts(
            _object(region_package.get("model_facing")).get("atoms")
        )
        neutral_map = _object(region_package.get("neutral_atom_to_candidate_id"))
        dictionary = _object(region_package.get("private_candidate_dictionary"))
        expected_region_atoms: list[dict[str, Any]] = []
        for atom in legacy_atoms:
            atom_id = str(atom.get("atom_id") or "")
            candidate_id = neutral_map.get(atom_id)
            source = _object(dictionary.get(candidate_id))
            exact_source_span = source.get("exact_source_span")
            if not isinstance(exact_source_span, str):
                raise PdfStructuralRepairRuntimeError(
                    "pdf_structural_repair_input_invalid"
                )
            expected_region_atoms.append(
                {
                    "atom_id": atom.get("atom_id"),
                    "bbox": copy.deepcopy(atom.get("bbox")),
                    "order": atom.get("order"),
                    "text": exact_source_span,
                }
            )
        if (
            region_atoms != expected_region_atoms
            or region_package.get("neutral_atom_manifest_hash")
            != sha256_json(region_atoms)
        ):
            raise PdfStructuralRepairRuntimeError(
                "pdf_structural_repair_input_invalid"
            )
        return legacy

    def _guided_topology_from_region(
        self,
        *,
        region_response: dict[str, Any],
        legacy_package_id: str,
    ) -> dict[str, Any]:
        regions = _dicts(region_response.get("regions"))
        if (
            region_response.get("table_presence") != "present"
            or len(regions) != 1
        ):
            raise PdfStructuralRepairRuntimeError(
                "pdf_structural_repair_topology_invalid"
            )
        region = regions[0]
        hypotheses = copy.deepcopy(_dicts(region.get("hypotheses")))
        uncertainty = sorted(
            {
                *[str(item) for item in region_response.get("uncertainty_codes") or []],
                *[str(item) for item in region.get("uncertainty_codes") or []],
            }
        )
        response = {
            "schema_version": PDF_VISUAL_TOPOLOGY_RESPONSE_SCHEMA,
            "package_id": legacy_package_id,
            "decision": (
                "bound"
                if len(hypotheses) == 1 and not uncertainty
                else "ambiguous"
            ),
            "alternatives_complete": (
                region_response.get("alternatives_complete") is True
            ),
            "hypotheses": hypotheses,
            "uncertainty_codes": uncertainty,
        }
        return self.visual.parse_response(
            response,
            expected_package_id=legacy_package_id,
        )

    def _guided_binding_bbox_compatible(
        self,
        *,
        parser_observation: dict[str, Any],
        visual_package: dict[str, Any],
        binding_hypothesis: dict[str, Any],
    ) -> bool:
        binding = _object(binding_hypothesis.get("binding_output"))
        geometry = _object(binding_hypothesis.get("proposed_geometry"))
        row_boundaries = [
            float(item)
            for item in _object(geometry.get("rows")).get("boundaries") or []
        ]
        column_boundaries = [
            float(item)
            for item in _object(geometry.get("columns")).get("boundaries") or []
        ]
        row_count = _strict_int(binding.get("row_count"))
        column_count = _strict_int(binding.get("column_count"))
        if (
            row_count < 1
            or column_count < 1
            or len(row_boundaries) != row_count + 1
            or len(column_boundaries) != column_count + 1
        ):
            return False
        neutral_map = _object(
            visual_package.get("neutral_atom_to_candidate_id")
        )
        atom_boxes = {
            str(neutral_map.get(str(atom.get("atom_id") or "")) or ""): [
                float(value) for value in atom.get("bbox") or []
            ]
            for atom in _dicts(
                _object(visual_package.get("model_facing")).get("atoms")
            )
        }
        positions: dict[str, tuple[int, int]] = {}
        for row in _dicts(binding.get("rows")):
            row_ordinal = _strict_int(row.get("row_ordinal"))
            cells = row.get("cells")
            if not isinstance(cells, list):
                return False
            for column_ordinal, cell in enumerate(cells, start=1):
                if not isinstance(cell, list):
                    return False
                for candidate_id in cell:
                    key = str(candidate_id)
                    if key in positions:
                        return False
                    positions[key] = (row_ordinal, column_ordinal)
        expected = {
            str(item) for item in parser_observation.get("candidate_order") or []
        }
        if set(positions) != expected or set(atom_boxes) != expected:
            return False
        spans = _dicts(binding.get("spans"))
        tolerance = self.assembler.config.atom_band_tolerance_normalized
        for candidate_id, (row, column) in positions.items():
            end_row = row
            end_column = column
            for span in spans:
                if (
                    span.get("start_row") == row
                    and span.get("start_column") == column
                ):
                    end_row = _strict_int(span.get("end_row"))
                    end_column = _strict_int(span.get("end_column"))
                    break
            if not (
                1 <= row <= end_row <= row_count
                and 1 <= column <= end_column <= column_count
            ):
                return False
            bbox = atom_boxes.get(candidate_id) or []
            if len(bbox) != 4 or not (
                bbox[0] >= column_boundaries[column - 1] - tolerance
                and bbox[1] >= row_boundaries[row - 1] - tolerance
                and bbox[2] <= column_boundaries[end_column] + tolerance
                and bbox[3] <= row_boundaries[end_row] + tolerance
            ):
                return False
        return True

    def _guided_post_validation(
        self,
        *,
        reason_codes: list[str],
        parsed_response: dict[str, Any] | None = None,
        parser_observation: dict[str, Any] | None = None,
        visual_package: dict[str, Any] | None = None,
        assembly: dict[str, Any] | None = None,
        materialization: dict[str, Any] | None = None,
        terminal: str | None = None,
    ) -> dict[str, Any]:
        parsed = _object(parsed_response)
        assembled = _object(assembly)
        materialized = _object(materialization)
        reasons = [str(item) for item in reason_codes if item]
        if parsed and parser_observation and visual_package and assembled:
            reasons.extend(
                self._guided_acceptance_reasons(
                    parser_observation=parser_observation,
                    visual_package=visual_package,
                    parsed_response=parsed,
                    assembly=assembled,
                )
            )
        materialization_errors = (
            self.materializer.validate_materialization(materialized)
            if materialized
            else ["pdf_vlm_guided_intake_materialization_missing"]
        )
        if terminal == "accepted_physical_structure":
            reasons.extend(materialization_errors)
        single_bound = bool(
            parsed.get("decision") == "bound"
            and len(_dicts(parsed.get("hypotheses"))) == 1
            and not _object(_dicts(parsed.get("hypotheses"))[0]).get(
                "uncertainty_codes"
            )
        )
        exact_ownership = bool(
            _object(assembled.get("source_accounting")).get(
                "all_bound_alternatives_exactly_once"
            )
            is True
        )
        coordinate_compatible = bool(
            parser_observation
            and visual_package
            and len(_dicts(assembled.get("binding_hypotheses"))) == 1
            and self._guided_binding_bbox_compatible(
                parser_observation=parser_observation,
                visual_package=visual_package,
                binding_hypothesis=_dicts(
                    assembled.get("binding_hypotheses")
                )[0],
            )
        )
        adjustments = _dicts(assembled.get("structural_adjustments"))
        separators_preserved = bool(
            assembled
            and not assembled.get("regional_issues")
            and all(
                item.get("operation")
                == "replace_visual_boundary_with_parser_geometry"
                for item in adjustments
            )
        )
        spans_headers_valid = bool(
            assembled
            and not any(
                str(item.get("axis") or "") in {"span", "header"}
                for item in adjustments
            )
        )
        crop_identity_preserved = bool(
            parser_observation
            and visual_package
            and assembled.get("package_id") == visual_package.get("package_id")
            and assembled.get("parser_observation_checksum")
            == parser_observation.get("observation_checksum")
        )
        source_only = bool(materialized and not materialization_errors)
        ambiguity_preserved = bool(
            terminal != "accepted_physical_structure"
            or single_bound
        )
        reasons = sorted(set(reasons))
        passed = bool(
            terminal == "accepted_physical_structure"
            and not reasons
            and single_bound
            and parsed.get("alternatives_complete") is True
            and exact_ownership
            and coordinate_compatible
            and separators_preserved
            and spans_headers_valid
            and crop_identity_preserved
            and ambiguity_preserved
            and source_only
        )
        return {
            "passed": passed,
            "reason_codes": reasons,
            "single_bound_hypothesis": single_bound,
            "alternatives_complete": parsed.get("alternatives_complete") is True,
            "exact_candidate_ownership": exact_ownership,
            "coordinate_compatible": coordinate_compatible,
            "certified_separators_preserved": separators_preserved,
            "spans_headers_valid": spans_headers_valid,
            "crop_identity_preserved": crop_identity_preserved,
            "ambiguity_preserved": ambiguity_preserved,
            "source_only_materialization": source_only,
        }

    def _guided_intake_result(
        self,
        *,
        run_id: str,
        target_id: str,
        parser_observation: dict[str, Any],
        parser_geometry_observation: dict[str, Any],
        visual_package: dict[str, Any],
        provider_qualification: dict[str, Any],
        journal: list[dict[str, Any]],
        proposal_decision: str,
        assembly: dict[str, Any] | None,
        accepted_binding: dict[str, Any] | None,
        materialization: dict[str, Any] | None,
        post_validation: dict[str, Any],
        terminal: str,
    ) -> dict[str, Any]:
        count_calls = sum(
            item.get("provider_count_token_call_performed") is True
            for item in journal
        )
        generate_calls = sum(
            item.get("provider_generate_call_performed") is True
            for item in journal
        )
        attempts = [
            _object(item.get("provider_attempt"))
            for item in journal
            if _object(item.get("provider_attempt"))
        ]
        materialized = _object(materialization)
        all_accounted = bool(
            materialized
            and materialized.get("omitted_candidate_ids") == []
            and materialized.get("extra_candidate_ids") == []
            and materialized.get("duplicate_candidate_ids") == []
            and materialized.get("structural_provenance_conflicts") == []
        )
        safe_summary = {
            "schema_version": PDF_VLM_GUIDED_INTAKE_SAFE_SUMMARY_SCHEMA,
            "target_id": target_id,
            "runtime_terminal_status": terminal,
            "reason_codes": copy.deepcopy(
                post_validation.get("reason_codes") or []
            ),
            "count_token_calls": count_calls,
            "generate_calls": generate_calls,
            "candidate_atoms": _object(
                visual_package.get("component_accounting")
            ).get("atom_count"),
            "row_count": materialized.get("row_count"),
            "column_count": materialized.get("column_count"),
            "all_candidates_accounted": all_accounted,
            "model_invented_values_total": (
                materialized.get("model_invented_values_total")
                if materialized
                else None
            ),
            "hidden_retry": any(
                item.get("hidden_retry") is not False for item in attempts
            ),
            "provider_failover": any(
                item.get("provider_failover") is not False for item in attempts
            ),
            "production_authority": False,
        }
        result = {
            "schema_version": PDF_VLM_GUIDED_INTAKE_RESULT_SCHEMA,
            "policy_version": self.config.policy_version,
            "policy_configuration_hash": sha256_json(asdict(self.config)),
            "run_id": run_id,
            "target_id": target_id,
            "execution_contract": _GUIDED_INTAKE_EXECUTION_CONTRACT,
            "package_id": visual_package.get("package_id"),
            "package_hash": visual_package.get("package_hash"),
            "parser_observation_checksum": parser_observation.get(
                "observation_checksum"
            ),
            "parser_geometry_observation_checksum": (
                parser_geometry_observation.get("observation_checksum")
            ),
            "provider_qualification": copy.deepcopy(provider_qualification),
            "journal": copy.deepcopy(journal),
            "proposal_decision": proposal_decision,
            "assembly": copy.deepcopy(assembly),
            "accepted_binding": copy.deepcopy(accepted_binding),
            "materialization": copy.deepcopy(materialization),
            "post_validation": copy.deepcopy(post_validation),
            "runtime_terminal_status": terminal,
            "new_provider_count_token_calls": count_calls,
            "new_provider_generate_calls": generate_calls,
            "authority_state": "non_authoritative",
            "production_ready": False,
            "production_gate2_selection_changed": False,
            "safe_summary": safe_summary,
        }
        result["result_checksum"] = sha256_json(result)
        validation_errors = self._validate_guided_intake_result(result)
        if validation_errors:
            raise PdfStructuralRepairRuntimeError(validation_errors[0])
        return result

    def _validate_input(
        self,
        *,
        target_id: str,
        parser_observation: dict[str, Any],
        parser_geometry_observation: dict[str, Any],
        visual_package: dict[str, Any],
        png_bytes: bytes,
        provider_qualification: dict[str, Any],
    ) -> None:
        if not target_id or len(target_id) > 96:
            raise PdfStructuralRepairRuntimeError(
                "pdf_structural_repair_input_invalid"
            )
        errors = [
            *self.contracts.validate_parser_observation(parser_observation),
            *self.parser_geometry.validate_observation(
                parser_geometry_observation
            ),
            *self.visual.validate_package(
                parser_observation=parser_observation,
                package=visual_package,
            ),
        ]
        crop = _object(visual_package.get("crop_identity"))
        if (
            errors
            or self.windowing.execution_mode(parser_observation) != "whole_table"
            or not png_bytes
            or len(png_bytes) > self.config.maximum_image_bytes
            or hashlib.sha256(png_bytes).hexdigest() != crop.get("crop_sha256")
        ):
            raise PdfStructuralRepairRuntimeError(
                "pdf_structural_repair_input_invalid"
            )
        if (
            provider_qualification.get("status") != "qualified"
            or provider_qualification.get("requested_model_id")
            != self.config.model_id
            or provider_qualification.get("resolved_model_id")
            != self.config.model_id
        ):
            raise PdfStructuralRepairRuntimeError(
                "pdf_structural_repair_provider_not_qualified"
            )

    def _validate_windowed_input(
        self,
        *,
        target_id: str,
        parser_observation: dict[str, Any],
        parser_geometry_observation: dict[str, Any],
        visual_package: dict[str, Any],
        window_plan: dict[str, Any],
        window_inputs: list[dict[str, Any]],
        provider_qualification: dict[str, Any],
    ) -> None:
        if not target_id or len(target_id) > 96:
            raise PdfStructuralRepairRuntimeError(
                "pdf_structural_repair_input_invalid"
            )
        errors = [
            *self.contracts.validate_parser_observation(parser_observation),
            *self.parser_geometry.validate_observation(
                parser_geometry_observation
            ),
            *self.ledger_visual.validate_ledger_package(
                parser_observation=parser_observation,
                package=visual_package,
            ),
            *self.windowing.validate_plan(
                parser_observation=parser_observation,
                plan=window_plan,
            ),
        ]
        windows = _dicts(window_plan.get("windows"))
        if (
            errors
            or self.windowing.execution_mode(parser_observation)
            != "vertical_atom_windows"
            or not isinstance(window_inputs, list)
            or len(window_inputs) != len(windows)
            or any(
                not isinstance(item, dict)
                or set(item) != {"window_id", "window_package", "png_bytes"}
                for item in window_inputs
            )
            or [item.get("window_id") for item in window_inputs]
            != [window.get("window_id") for window in windows]
        ):
            raise PdfStructuralRepairRuntimeError(
                "pdf_structural_window_plan_invalid"
            )
        for window, item in zip(windows, window_inputs):
            package = _object(item.get("window_package"))
            png_bytes = item.get("png_bytes")
            package_errors = self.visual.validate_window_package(
                parser_observation=parser_observation,
                full_package=visual_package,
                window_plan=window_plan,
                window=window,
                package=package,
            )
            crop = _object(package.get("crop_identity"))
            if (
                package_errors
                or not isinstance(png_bytes, bytes)
                or not png_bytes
                or len(png_bytes) > self.config.maximum_image_bytes
                or hashlib.sha256(png_bytes).hexdigest()
                != crop.get("crop_sha256")
                or package.get("schema_version")
                != "broker_reports_pdf_visual_topology_window_package_v1"
            ):
                raise PdfStructuralRepairRuntimeError(
                    "pdf_structural_window_package_invalid"
                )
        if (
            provider_qualification.get("status") != "qualified"
            or provider_qualification.get("requested_model_id")
            != self.config.model_id
            or provider_qualification.get("resolved_model_id")
            != self.config.model_id
        ):
            raise PdfStructuralRepairRuntimeError(
                "pdf_structural_repair_provider_not_qualified"
            )

    def _validate_counted_tokens(self, counted: dict[str, Any]) -> None:
        total = counted.get("total_tokens")
        if (
            counted.get("within_hard_guard") is not True
            or not _is_strict_non_negative_int(total)
            or total < 1
            or total > self.config.maximum_counted_input_tokens
            or counted.get("model_requested") != self.config.model_id
        ):
            code = (
                "pdf_structural_repair_counted_input_budget_exceeded"
                if _strict_int(total) > self.config.maximum_counted_input_tokens
                else "pdf_structural_repair_count_tokens_failed"
            )
            raise PdfStructuralRepairRuntimeError(code)

    def _validate_provider_attempt(
        self,
        *,
        attempt: dict[str, Any],
        task_id: str,
        attempt_number: int,
        attempt_lineage: list[str],
        counted: dict[str, Any],
        provider_result: dict[str, Any],
    ) -> None:
        expected_attempt_id = f"{task_id}_a{attempt_number}"
        if (
            attempt.get("task_id") != task_id
            or attempt.get("attempt_id") != expected_attempt_id
            or attempt.get("attempt_number") != attempt_number
            or attempt.get("attempt_lineage") != attempt_lineage
        ):
            raise PdfStructuralRepairRuntimeError(
                "pdf_structural_repair_provider_lineage_invalid"
            )
        usage = _object(attempt.get("usage"))
        input_tokens = usage.get("input_tokens")
        output_tokens = usage.get("output_tokens")
        total_tokens = usage.get("total_tokens")
        if (
            attempt.get("terminal_failure_class") is not None
            or attempt.get("finish_reason") != "STOP"
            or attempt.get("hidden_retry") is not False
            or attempt.get("provider_failover") is not False
            or attempt.get("model_requested") != self.config.model_id
            or attempt.get("model_resolved") != self.config.model_id
        ):
            raise PdfStructuralRepairRuntimeError(
                "pdf_structural_repair_provider_attempt_failed"
            )
        if (
            not _is_strict_non_negative_int(input_tokens)
            or not _is_strict_non_negative_int(output_tokens)
            or not _is_strict_non_negative_int(total_tokens)
            or input_tokens != counted.get("total_tokens")
            or total_tokens < input_tokens + output_tokens
            or output_tokens > self.config.maximum_output_tokens
            or not _is_strict_non_negative_int(
                provider_result.get("visible_output_bytes")
            )
            or provider_result.get("visible_output_bytes")
            > self.config.maximum_visible_output_bytes
            or not _is_strict_non_negative_int(
                provider_result.get("response_bytes")
            )
            or provider_result.get("response_bytes")
            > self.config.maximum_provider_response_bytes
        ):
            raise PdfStructuralRepairRuntimeError(
                "pdf_structural_repair_provider_accounting_invalid"
            )

    def _journal_entry(
        self,
        *,
        target_id: str,
        task_id: str,
        attempt_number: int,
        evidence_revision: str,
        provider_config_hash: str,
        counted: dict[str, Any],
        provider_attempt: dict[str, Any],
        provider_result: dict[str, Any],
        topology_response: dict[str, Any] | None,
        assembly: dict[str, Any] | None,
        failure_code: str | None,
        count_token_call_performed: bool,
        generate_call_performed: bool,
    ) -> dict[str, Any]:
        return {
            "target_id": target_id,
            "attempt_number": attempt_number,
            "task_id": task_id,
            "job_key": f"{task_id}|a{attempt_number}",
            "evidence_revision": evidence_revision,
            "provider_config_hash": provider_config_hash,
            "count_tokens": copy.deepcopy(counted),
            "provider_attempt": copy.deepcopy(provider_attempt),
            "provider_result": copy.deepcopy(provider_result),
            "topology_response": copy.deepcopy(topology_response),
            "assembly": copy.deepcopy(assembly),
            "failure_code": failure_code,
            "provider_count_token_call_performed": (
                count_token_call_performed
            ),
            "provider_generate_call_performed": generate_call_performed,
        }

    def _model_context(
        self,
        *,
        visual_package: dict[str, Any],
        journal: list[dict[str, Any]],
        assemblies: list[dict[str, Any]],
        provider_config_hash: str,
    ) -> dict[str, Any]:
        successful = [
            item for item in journal if isinstance(item.get("assembly"), dict)
        ]
        output_tokens = [
            _strict_int(
                _object(_object(item.get("provider_attempt")).get("usage")).get(
                    "output_tokens"
                )
            )
            for item in successful
        ]
        exact_accounting = bool(
            len(successful) == 2
            and all(
                _object(_object(item.get("provider_attempt")).get("usage")).get(
                    "input_tokens"
                )
                == _object(item.get("count_tokens")).get("total_tokens")
                for item in successful
            )
        )
        ownership = bool(
            len(assemblies) == 2
            and all(
                _object(assembly.get("source_accounting")).get(
                    "all_bound_alternatives_exactly_once"
                )
                is True
                for assembly in assemblies
            )
        )
        complete = bool(
            len(successful) == 2
            and all(
                _object(item.get("topology_response")).get(
                    "alternatives_complete"
                )
                is True
                for item in successful
            )
        )
        return {
            "provider": self.config.provider_name,
            "model": self.config.model_id,
            "configuration_hash": provider_config_hash,
            "bounded_row_windows": True,
            "provider_calls_replayed": 0,
            "new_provider_calls": sum(
                item.get("provider_generate_call_performed") is True
                for item in journal
            ),
            "execution_mode": "whole_table",
            "window_count": 1,
            "raw_provider_calls": sum(
                item.get("provider_generate_call_performed") is True
                for item in journal
            ),
            "stitched_oracle_observations": sum(
                item.get("provider_generate_call_performed") is True
                for item in journal
            ),
            "window_lineage_checksum": "not_applicable",
            "topology_input_basis": "visual_crop_without_parser_grid",
            "topology_dimensions_source": "vlm_visual_observation",
            "alternative_generation_contract": (
                "explicit_exhaustive_bounded_alternatives"
            ),
            "topology_prompt_contract_hash": sha256_json(
                _object(visual_package.get("model_facing")).get("task")
            ),
            "crop_manifest_hash": _object(
                visual_package.get("crop_identity")
            ).get("manifest_hash"),
            "observed_image_bytes": _object(
                visual_package.get("crop_identity")
            ).get("png_bytes"),
            "maximum_image_bytes": self.config.maximum_image_bytes,
            "observed_output_tokens": max(output_tokens, default=0),
            "maximum_output_tokens": self.config.maximum_output_tokens,
            "provider_token_accounting_exact": exact_accounting,
            "candidate_ownership_exact": ownership,
            "no_silent_truncation": bool(
                len(successful) == 2
                and all(
                    _object(item.get("provider_attempt")).get("finish_reason")
                    == "STOP"
                    for item in successful
                )
            ),
            "column_splitting_used": False,
            "hidden_provider_failover": False,
            "alternative_topology_hypotheses_complete": complete,
        }

    def _safe_summary(
        self,
        *,
        result: dict[str, Any],
        visual_package: dict[str, Any],
        preflight_reason: str | None,
    ) -> dict[str, Any]:
        journal = _dicts(result.get("journal"))
        counted = [
            _strict_int(_object(item.get("count_tokens")).get("total_tokens"))
            for item in journal
            if _object(item.get("count_tokens"))
        ]
        actual = [
            _strict_int(
                _object(_object(item.get("provider_attempt")).get("usage")).get(
                    "input_tokens"
                )
            )
            for item in journal
            if _object(item.get("provider_attempt"))
        ]
        output = [
            _strict_int(
                _object(_object(item.get("provider_attempt")).get("usage")).get(
                    "output_tokens"
                )
            )
            for item in journal
            if _object(item.get("provider_attempt"))
        ]
        consensus = _object(result.get("consensus_result"))
        materialization = _object(result.get("materialization"))
        reasons = []
        if preflight_reason:
            reasons.append(preflight_reason)
        reasons.extend(
            code
            for code in consensus.get("reason_codes") or []
            if code in _SAFE_REASON_CODES
        )
        terminal = result.get("runtime_terminal_status")
        if not reasons:
            safe_reason = {
                "incomplete_evidence": "pdf_structural_repair_incomplete_evidence",
                "ambiguous_multiple_consensus": (
                    "pdf_structural_repair_supplied_consensus_ambiguous"
                ),
                "parser_vlm_conflict": (
                    "pdf_structural_repair_supplied_consensus_conflict"
                ),
                "no_valid_consensus": (
                    "pdf_structural_repair_no_valid_supplied_consensus"
                ),
                "unsupported": "pdf_structural_repair_consensus_unavailable",
            }.get(str(terminal or ""))
            if safe_reason:
                reasons.append(safe_reason)
        return {
            "schema_version": (
                "broker_reports_pdf_structural_repair_runtime_safe_summary_v2"
            ),
            "run_id": result.get("run_id"),
            "target_id": result.get("target_id"),
            "runtime_terminal_status": result.get("runtime_terminal_status"),
            "reason_codes": sorted(set(reasons)),
            "attempts_expected": 2,
            "attempts_recorded": len(journal),
            "count_token_calls": result.get("new_provider_count_token_calls"),
            "generate_calls": result.get("new_provider_generate_calls"),
            "counted_input_tokens": counted,
            "actual_input_tokens": actual,
            "output_tokens": output,
            "candidate_atoms": _object(
                visual_package.get("component_accounting")
            ).get("atom_count"),
            "row_count": materialization.get("row_count"),
            "column_count": materialization.get("column_count"),
            "all_candidates_accounted": (
                not materialization.get("omitted_candidate_ids")
                if materialization
                else False
            ),
            "model_invented_values_total": (
                materialization.get("model_invented_values_total")
                if materialization
                else None
            ),
            "hidden_retry": any(
                _object(item.get("provider_attempt")).get("hidden_retry")
                is not False
                for item in journal
                if _object(item.get("provider_attempt"))
            ),
            "provider_failover": any(
                _object(item.get("provider_attempt")).get("provider_failover")
                is not False
                for item in journal
                if _object(item.get("provider_attempt"))
            ),
            "production_authority": False,
            **_safe_consensus_semantics(consensus),
            "result_checksum_ref": None,
        }

    def _window_model_context(
        self,
        *,
        visual_package: dict[str, Any],
        window_plan: dict[str, Any],
        window_inputs: list[dict[str, Any]],
        journal: list[dict[str, Any]],
        assemblies: list[dict[str, Any]],
        stitches: list[dict[str, Any]],
        provider_config_hash: str,
    ) -> dict[str, Any]:
        expected_calls = 2 * len(window_inputs)
        provider_journal = [
            item
            for item in journal
            if item.get("provider_generate_call_performed") is True
        ]
        output_tokens = [
            _strict_int(
                _object(_object(item.get("provider_attempt")).get("usage")).get(
                    "output_tokens"
                )
            )
            for item in provider_journal
        ]
        exact_accounting = bool(
            len(journal) == expected_calls
            and len(provider_journal) == expected_calls
            and all(
                _object(_object(item.get("provider_attempt")).get("usage")).get(
                    "input_tokens"
                )
                == _object(item.get("count_tokens")).get("total_tokens")
                for item in provider_journal
            )
        )
        ownership = bool(
            window_plan.get("candidate_ownership_exact") is True
            and len(assemblies) == 2
            and all(
                _object(assembly.get("source_accounting")).get(
                    "all_bound_alternatives_exactly_once"
                )
                is True
                for assembly in assemblies
            )
        )
        complete = bool(
            len(stitches) == 2
            and all(
                _object(item.get("stitched_response")).get(
                    "alternatives_complete"
                )
                is True
                for item in stitches
            )
        )
        image_sizes = [
            _strict_int(
                _object(_object(item.get("window_package")).get("crop_identity")).get(
                    "png_bytes"
                )
            )
            for item in window_inputs
        ]
        lineage_checksum = sha256_json(
            [
                {
                    "attempt_number": item.get("attempt_number"),
                    "composite_attempt_id": item.get("composite_attempt_id"),
                    "window_attempt_ids_checksum": item.get(
                        "window_attempt_ids_checksum"
                    ),
                }
                for item in stitches
            ]
        )
        return {
            "provider": self.config.provider_name,
            "model": self.config.model_id,
            "configuration_hash": provider_config_hash,
            "bounded_row_windows": True,
            "provider_calls_replayed": 0,
            "new_provider_calls": len(provider_journal),
            "execution_mode": "vertical_atom_windows",
            "window_count": len(window_inputs),
            "raw_provider_calls": len(provider_journal),
            "stitched_oracle_observations": len(stitches),
            "window_lineage_checksum": lineage_checksum,
            "topology_input_basis": "visual_crop_without_parser_grid",
            "topology_dimensions_source": "vlm_visual_observation",
            "alternative_generation_contract": (
                "explicit_exhaustive_bounded_alternatives"
            ),
            "topology_prompt_contract_hash": sha256_json(
                [
                    _object(_object(item.get("window_package")).get("model_facing")).get(
                        "task"
                    )
                    for item in window_inputs
                ]
            ),
            "crop_manifest_hash": str(window_plan.get("plan_hash") or ""),
            "observed_image_bytes": max(image_sizes, default=0),
            "maximum_image_bytes": self.config.maximum_image_bytes,
            "observed_output_tokens": max(output_tokens, default=0),
            "maximum_output_tokens": self.config.maximum_output_tokens,
            "provider_token_accounting_exact": exact_accounting,
            "candidate_ownership_exact": ownership,
            "no_silent_truncation": bool(
                len(provider_journal) == expected_calls
                and all(
                    _object(item.get("provider_attempt")).get("finish_reason")
                    == "STOP"
                    for item in provider_journal
                )
            ),
            "column_splitting_used": False,
            "hidden_provider_failover": False,
            "alternative_topology_hypotheses_complete": complete,
        }

    def _window_safe_summary(
        self,
        *,
        result: dict[str, Any],
        visual_package: dict[str, Any],
        failure_reason: str | None,
    ) -> dict[str, Any]:
        journal = _dicts(result.get("journal"))
        counted = [
            _strict_int(_object(item.get("count_tokens")).get("total_tokens"))
            for item in journal
            if _object(item.get("count_tokens"))
        ]
        actual = [
            _strict_int(
                _object(_object(item.get("provider_attempt")).get("usage")).get(
                    "input_tokens"
                )
            )
            for item in journal
            if _object(item.get("provider_attempt"))
        ]
        output = [
            _strict_int(
                _object(_object(item.get("provider_attempt")).get("usage")).get(
                    "output_tokens"
                )
            )
            for item in journal
            if _object(item.get("provider_attempt"))
        ]
        consensus = _object(result.get("consensus_result"))
        materialization = _object(result.get("materialization"))
        reasons = [failure_reason] if failure_reason in _SAFE_REASON_CODES else []
        reasons.extend(
            code
            for code in consensus.get("reason_codes") or []
            if code in _SAFE_REASON_CODES
        )
        terminal = result.get("runtime_terminal_status")
        if not reasons:
            safe_reason = {
                "incomplete_evidence": "pdf_structural_repair_incomplete_evidence",
                "ambiguous_multiple_consensus": (
                    "pdf_structural_repair_supplied_consensus_ambiguous"
                ),
                "parser_vlm_conflict": (
                    "pdf_structural_repair_supplied_consensus_conflict"
                ),
                "no_valid_consensus": (
                    "pdf_structural_repair_no_valid_supplied_consensus"
                ),
                "unsupported": "pdf_structural_repair_consensus_unavailable",
            }.get(str(terminal or ""))
            if safe_reason:
                reasons.append(safe_reason)
        expected = 2 * _strict_int(
            _object(result.get("window_plan")).get("window_count")
        )
        all_accounted = bool(
            materialization
            and not materialization.get("omitted_candidate_ids")
            and not materialization.get("extra_candidate_ids")
            and not materialization.get("duplicate_candidate_ids")
            and not materialization.get("structural_provenance_conflicts")
        )
        return {
            "schema_version": (
                "broker_reports_pdf_structural_repair_runtime_safe_summary_v2"
            ),
            "run_id": result.get("run_id"),
            "target_id": result.get("target_id"),
            "runtime_terminal_status": result.get("runtime_terminal_status"),
            "reason_codes": sorted(set(reasons)),
            "attempts_expected": expected,
            "attempts_recorded": len(journal),
            "count_token_calls": result.get("new_provider_count_token_calls"),
            "generate_calls": result.get("new_provider_generate_calls"),
            "counted_input_tokens": counted,
            "actual_input_tokens": actual,
            "output_tokens": output,
            "candidate_atoms": _object(
                visual_package.get("component_accounting")
            ).get("atom_count"),
            "row_count": materialization.get("row_count"),
            "column_count": materialization.get("column_count"),
            "all_candidates_accounted": all_accounted,
            "model_invented_values_total": (
                materialization.get("model_invented_values_total")
                if materialization
                else None
            ),
            "hidden_retry": any(
                _object(item.get("provider_attempt")).get("hidden_retry")
                is not False
                for item in journal
                if _object(item.get("provider_attempt"))
            ),
            "provider_failover": any(
                _object(item.get("provider_attempt")).get("provider_failover")
                is not False
                for item in journal
                if _object(item.get("provider_attempt"))
            ),
            "production_authority": False,
            **_safe_consensus_semantics(consensus),
            "result_checksum_ref": None,
        }


def _safe_consensus_semantics(consensus: dict[str, Any]) -> dict[str, Any]:
    if not consensus:
        return {
            "search_scope": "not_started",
            "supplied_hypotheses_exhausted": False,
            "structural_domain_complete": False,
            "uniqueness_proven": False,
            "ambiguity_proven": False,
            "domain_incomplete": True,
            "search_not_certifiable": True,
            "consensus_explanation": (
                "Consensus evaluation did not start; the structural domain was "
                "not enumerated."
            ),
        }
    return {
        "search_scope": str(consensus.get("search_scope") or "unknown"),
        "supplied_hypotheses_exhausted": (
            consensus.get("supplied_hypotheses_exhausted") is True
        ),
        "structural_domain_complete": (
            consensus.get("structural_domain_complete") is True
        ),
        "uniqueness_proven": consensus.get("uniqueness_proven") is True,
        "ambiguity_proven": consensus.get("ambiguity_proven") is True,
        "domain_incomplete": consensus.get("domain_incomplete") is True,
        "search_not_certifiable": consensus.get("search_not_certifiable") is True,
        "consensus_explanation": str(
            consensus.get("safe_explanation")
            or "Consensus semantics are unavailable."
        ),
    }


def _safe_failure_code(exc: BaseException) -> str:
    code = str(getattr(exc, "code", ""))
    if code in _SAFE_REASON_CODES:
        return code
    if code.startswith("pdf_grid_provider_count"):
        return "pdf_structural_repair_count_tokens_failed"
    if "lineage" in code:
        return "pdf_structural_repair_provider_lineage_invalid"
    if "accounting" in code or "budget" in code:
        return "pdf_structural_repair_provider_accounting_invalid"
    if code.startswith("pdf_grid_provider"):
        return "pdf_structural_repair_provider_attempt_failed"
    if "topology" in code or "assembly" in code:
        return "pdf_structural_repair_topology_invalid"
    return "pdf_structural_repair_unknown_failure"


def _safe_page_proposal_failure_code(exc: BaseException) -> str:
    code = str(getattr(exc, "code", ""))
    if code.startswith("pdf_visual_topology_"):
        return "pdf_vlm_page_proposal_response_invalid"
    mapped = _safe_failure_code(exc)
    return (
        mapped
        if mapped in _PAGE_PROPOSAL_REASON_CODES
        else "pdf_structural_repair_unknown_failure"
    )


def _safe_window_failure_code(exc: BaseException) -> str:
    code = str(getattr(exc, "code", ""))
    if code.startswith("pdf_visual_topology_"):
        return "pdf_structural_window_response_invalid"
    return _safe_failure_code(exc)


def _counted_from_provider_error(
    exc: BaseException,
    *,
    model_id: str,
    current: dict[str, Any],
) -> dict[str, Any]:
    if current:
        return current
    details = _object(getattr(exc, "safe_details", None))
    observed = details.get("observed_total_tokens")
    maximum = details.get("maximum_counted_input_tokens")
    if (
        not _is_strict_non_negative_int(observed)
        or not _is_strict_non_negative_int(maximum)
        or observed <= maximum
    ):
        return {}
    return {
        "total_tokens": observed,
        "model_requested": model_id,
        "within_hard_guard": False,
        "budget_exceeded": True,
        "maximum_counted_input_tokens": maximum,
    }


def _result_checksum(value: dict[str, Any]) -> str:
    unsigned = copy.deepcopy(value)
    unsigned.pop("result_checksum", None)
    safe = _object(unsigned.get("safe_summary"))
    if safe:
        safe["result_checksum_ref"] = None
        unsigned["safe_summary"] = safe
    return sha256_json(unsigned)


def _continuation_result_checksum(value: dict[str, Any]) -> str:
    unsigned = copy.deepcopy(value)
    unsigned.pop("result_checksum", None)
    return sha256_json(unsigned)


def _expected_provider_calls(result: dict[str, Any]) -> int:
    if (
        result.get("schema_version")
        == PDF_STRUCTURAL_REPAIR_WINDOWED_RUNTIME_RESULT_SCHEMA
    ):
        return 2 * _strict_int(
            _object(result.get("window_plan")).get("window_count")
        )
    return 2


def _is_strict_non_negative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _strict_int(value: Any) -> int:
    return value if _is_strict_non_negative_int(value) else 0


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _dicts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]
