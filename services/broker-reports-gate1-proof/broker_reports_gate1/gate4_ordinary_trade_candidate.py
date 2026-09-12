"""Gate 4 fact adapter for the ordinary-trade production candidate."""

from __future__ import annotations

import copy
from typing import Any

from .artifact_models import ArtifactAccessContext
from .ordinary_trade_projection import OrdinaryTradeProjectionFactory
from .qualified_projection_fact_v3 import build_qualified_projection_fact_v3
GATE4_ORDINARY_TRADE_CURRENT_FACT_SET_SCHEMA_VERSION = (
    "broker_reports_gate4_ordinary_trade_current_fact_set_v1"
)
GATE4_ORDINARY_TRADE_BLOCKER_SCHEMA_VERSION = (
    "broker_reports_gate4_ordinary_trade_blocker_v1"
)
GATE4_ORDINARY_TRADE_SECURITY_POSITION_SOURCE_CONTRACT_MISSING = (
    "gate4_ordinary_trade_security_position_source_contract_missing"
)
GATE4_ORDINARY_TRADE_SOURCE_ROLE_INCOMPLETE = (
    "gate4_ordinary_trade_source_role_incomplete"
)


FACTORY_REQUIRED = (
    "Gate4OrdinaryTradeCandidateRuntimeFactory.create is the only projection "
    "to qualified Runtime fact contract adapter entrypoint"
)
FORBIDDEN = (
    "Canonical reads, LLM calls, financial classification, value invention, "
    "value-based deduplication, tax logic or a second SQL cache"
)


class Gate4OrdinaryTradeCandidateError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class Gate4OrdinaryTradeCandidateRuntimeFactory:
    def __init__(self, *, store: Any, read_enabled: bool) -> None:
        self._store = store
        self._read_enabled = read_enabled

    def create(self) -> "Gate4OrdinaryTradeCandidateRuntime":
        return Gate4OrdinaryTradeCandidateRuntime(
            projections=OrdinaryTradeProjectionFactory(
                store=self._store,
                read_enabled=self._read_enabled,
            ).create()
        )


class Gate4OrdinaryTradeCandidateRuntime:
    """Expose qualified projection records through the V3 fact shape."""

    def __init__(self, *, projections: Any) -> None:
        self._projections = projections

    def current_fact_set(
        self, *, context: ArtifactAccessContext
    ) -> dict[str, Any]:
        case_binding = _case_binding(context)
        facts: list[dict[str, Any]] = []
        projections = self._projections.current_case(context=context)
        for record, projection in projections:
            projection_binding = projection["canonical_binding"]
            canonical_binding = {
                "document_id": projection_binding["document_id"],
                "canonical_version_id": projection_binding["canonical_version_id"],
                "canonical_root_sha256": projection_binding[
                    "canonical_root_sha256"
                ],
            }
            observations = {
                item["observation_id"]: item
                for item in projection["source_observations"]
            }
            for runtime_record in projection["runtime_records"]:
                observation = observations.get(
                    runtime_record.get("source_observation_id")
                )
                mapping_id = (
                    observation.get("mapping_id")
                    if isinstance(observation, dict)
                    else None
                )
                if not isinstance(mapping_id, str) or not mapping_id.startswith(
                    "otmap_"
                ):
                    raise Gate4OrdinaryTradeCandidateError(
                        "gate4_ordinary_trade_mapping_authority_invalid"
                    )
                semantic_binding = {
                    "dictionary": {
                        "authority_id": (
                            f"ordinary_trade_schema_mapping:{mapping_id}"
                        ),
                        "semantic_version": "1.0.0",
                    },
                    "role_pack": {
                        "authority_id": "ordinary_trade_runtime_projection",
                        "semantic_version": "1.0.0",
                    },
                }
                roles = [_fact_role(item) for item in runtime_record["roles"]]
                facts.append(
                    build_qualified_projection_fact_v3(
                        case_binding=case_binding,
                        projection_artifact_id=record.artifact_id,
                        canonical_binding=canonical_binding,
                        source_observation_id=runtime_record[
                            "source_observation_id"
                        ],
                        semantic_mapping_case_ref=projection[
                            "semantic_mapping_case_ref"
                        ],
                        runtime_record_id=runtime_record["runtime_record_id"],
                        semantic_kind="normalized_source_fact",
                        semantic_binding=semantic_binding,
                        financial_type=runtime_record["record_type"],
                        annotation_target=runtime_record["annotation_target"],
                        roles=roles,
                        status="role_complete",
                    )
                )
        ids = [item["fact_id"] for item in facts]
        if len(ids) != len(set(ids)):
            raise Gate4OrdinaryTradeCandidateError(
                "gate4_ordinary_trade_fact_duplicate"
            )
        security_facts = [
            item
            for item in facts
            if item["financial_type"] in {"SECURITY_PURCHASE", "SECURITY_DISPOSAL"}
        ]
        relevant_unmapped = any(
            observation.get("disposition") == "RELEVANT_UNMAPPED"
            for _record, projection in projections
            for observation in projection["source_observations"]
        )
        if relevant_unmapped:
            facts = []
            security_facts = []
        incomplete_table_resolutions = [
            resolution
            for _record, projection in projections
            for resolution in projection["qualified_table_resolutions"]
            if resolution.get("disposition") == "SECURITY_TRADES_INCOMPLETE"
        ]
        incomplete_trade_rows = any(
            observation.get("disposition")
            in {
                "SOURCE_RETAINED_FINANCIAL_ROLE_INCOMPLETE",
                # Historical projections retained the exact incomplete-row
                # reason but used the no-consumer disposition.
                "SOURCE_RETAINED_NO_CONSUMER",
            }
            and observation.get("reason_code") == "ORDINARY_TRADE_ROW_CONTRACT_INCOMPLETE"
            for _record, projection in projections
            for observation in projection["source_observations"]
        )
        blockers = []
        if incomplete_table_resolutions and not relevant_unmapped:
            missing_roles = sorted(
                {
                    role
                    for resolution in incomplete_table_resolutions
                    for role in resolution["missing_required_roles"]
                }
            )
            blockers.append(
                {
                    "schema_version": GATE4_ORDINARY_TRADE_BLOCKER_SCHEMA_VERSION,
                    "reason_code": GATE4_ORDINARY_TRADE_SOURCE_ROLE_INCOMPLETE,
                    "required_input": (
                        "ordinary_trade_source.financial_roles."
                        + ",".join(missing_roles)
                    ),
                    "gap_owner_classification": "REAL_SOURCE_EVIDENCE_MISSING",
                    "owner": "Gate4OrdinaryTradeCandidateRuntime",
                    "blocking_scope": "recognized_security_trade_source_table",
                }
            )
        if incomplete_trade_rows and not relevant_unmapped:
            blockers.append(
                {
                    "schema_version": GATE4_ORDINARY_TRADE_BLOCKER_SCHEMA_VERSION,
                    "reason_code": GATE4_ORDINARY_TRADE_SOURCE_ROLE_INCOMPLETE,
                    "required_input": "ordinary_trade_source.financial_rows.complete_record",
                    "gap_owner_classification": "REAL_SOURCE_EVIDENCE_MISSING",
                    "owner": "Gate4OrdinaryTradeCandidateRuntime",
                    "blocking_scope": "recognized_security_trade_source_row",
                }
            )
        if not blockers and projections and not security_facts and not relevant_unmapped:
            blockers.append(
                {
                    "schema_version": GATE4_ORDINARY_TRADE_BLOCKER_SCHEMA_VERSION,
                    "reason_code": (
                        GATE4_ORDINARY_TRADE_SECURITY_POSITION_SOURCE_CONTRACT_MISSING
                    ),
                    "required_input": (
                        "ordinary_trade_projection.runtime_records."
                        "security_position_semantics"
                    ),
                    "gap_owner_classification": (
                        "INTERNAL_CONTRACT_OR_PIPELINE_DEFECT"
                    ),
                    "owner": "Gate4OrdinaryTradeCandidateRuntime",
                    "blocking_scope": (
                        "active_security_position_source_contract"
                    ),
                }
            )
        return {
            "schema_version": GATE4_ORDINARY_TRADE_CURRENT_FACT_SET_SCHEMA_VERSION,
            "status": (
                "SOURCE_MAPPING_INCOMPLETE"
                if relevant_unmapped
                else "SOURCE_ROLE_INCOMPLETE"
                if incomplete_table_resolutions or incomplete_trade_rows
                else "SECURITY_POSITION_SOURCE_CONTRACT_MISSING"
                if blockers
                else "READY"
            ),
            "facts": copy.deepcopy(facts),
            "blockers": copy.deepcopy(blockers),
        }

    def list_facts(
        self, *, context: ArtifactAccessContext
    ) -> list[dict[str, Any]]:
        return self.current_fact_set(context=context)["facts"]


def _case_binding(context: ArtifactAccessContext) -> dict[str, str]:
    if (
        not isinstance(context, ArtifactAccessContext)
        or not context.user_id
        or not context.case_id
        or not context.allow_private
    ):
        raise Gate4OrdinaryTradeCandidateError(
            "gate4_ordinary_trade_private_case_context_required"
        )
    return {"scope_kind": "case", "scope_id": context.case_id}


def _fact_role(item: dict[str, Any]) -> dict[str, Any]:
    binding = item.get("source_binding")
    cell = binding.get("canonical_cell") if isinstance(binding, dict) else None
    assertion = (
        binding.get("user_currency_assertion") if isinstance(binding, dict) else None
    )
    if assertion is not None:
        if (
            item.get("role") != "currency"
            or not isinstance(assertion, dict)
            or assertion.get("schema_version")
            != "broker_reports_user_currency_assertion_v1"
            or not isinstance(assertion.get("assertion_id"), str)
            or not assertion["assertion_id"].startswith("usrassert_")
            or item.get("value") != assertion.get("currency_code")
            or binding.get("source_ref")
            != "canonical_user_assertion:" + assertion["assertion_id"]
            or binding.get("source_literal") != assertion.get("currency_code")
        ):
            raise Gate4OrdinaryTradeCandidateError(
                "gate4_ordinary_trade_user_currency_assertion_invalid"
            )
        return {
            "role": item["role"],
            "requirement": "required",
            "status": "value",
            "value": item["value"],
            "source_binding": {
                "target": {
                    "kind": "user_assertion",
                    "assertion_id": assertion["assertion_id"],
                },
                "exact_text": assertion["currency_code"],
                "source_literal": assertion["currency_code"],
            },
        }
    if (
        not isinstance(cell, dict)
        or not isinstance(cell.get("node_id"), str)
        or not isinstance(cell.get("row"), int)
        or not isinstance(cell.get("column"), int)
        or not isinstance(binding.get("source_literal"), str)
        or not binding["source_literal"]
    ):
        raise Gate4OrdinaryTradeCandidateError(
            "gate4_ordinary_trade_role_source_invalid"
        )
    return {
        "role": item["role"],
        # An opening-short effect refines a proved disposal; it is never a
        # required source field for ordinary long trades.
        "requirement": (
            "optional" if item["role"] == "position_effect" else "required"
        ),
        "status": "value",
        "value": item["value"],
        "source_binding": {
            "target": {
                "kind": "table_cell",
                "node_id": cell["node_id"],
                "row": cell["row"],
                "column": cell["column"],
            },
            "exact_text": binding["source_literal"],
            "source_literal": binding["source_literal"],
        },
    }


__all__ = [
    "FACTORY_REQUIRED",
    "FORBIDDEN",
    "GATE4_ORDINARY_TRADE_BLOCKER_SCHEMA_VERSION",
    "GATE4_ORDINARY_TRADE_CURRENT_FACT_SET_SCHEMA_VERSION",
    "GATE4_ORDINARY_TRADE_SECURITY_POSITION_SOURCE_CONTRACT_MISSING",
    "Gate4OrdinaryTradeCandidateError",
    "Gate4OrdinaryTradeCandidateRuntime",
    "Gate4OrdinaryTradeCandidateRuntimeFactory",
]
