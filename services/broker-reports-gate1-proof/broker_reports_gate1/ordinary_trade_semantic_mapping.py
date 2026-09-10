"""Case-scoped semantic mapping contracts for unknown ordinary-trade tables."""

from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import asdict, is_dataclass
from typing import Any, Iterable, Mapping

from .gate2_source_fact_contracts import Gate2ManagedPrompt
from .instructional_table_classification import (
    InstructionalClassificationContractError,
    build_case as build_instructional_classification_case,
    validate_response as validate_instructional_classification_response,
)
from .ordinary_trade_qualified_mappings import (
    OrdinaryTradeQualifiedMappingAuthorityFactory,
)
from .ordinary_trade_semantic_compiler import (
    OrdinaryTradeSemanticCompilerError,
    canonical_cell_literal,
)
from .ordinary_trade_semantic_compiler import structural_fingerprint
from .ordinary_trade_semantic_compiler import OrdinaryTradeSemanticCompilerFactory


MAPPING_RESPONSE_SCHEMA_VERSION = (
    "broker_reports_ordinary_trade_semantic_mapping_response_v14"
)
_MODEL_SELECTED_CLASSIFICATION_EVIDENCE_RESPONSE_V11 = (
    "broker_reports_ordinary_trade_semantic_mapping_response_v11"
)
_LEGACY_MAPPING_RESPONSE_SCHEMA_VERSIONS = frozenset(
    {
        "broker_reports_ordinary_trade_semantic_mapping_response_v6",
        "broker_reports_ordinary_trade_semantic_mapping_response_v7",
        "broker_reports_ordinary_trade_semantic_mapping_response_v8",
        "broker_reports_ordinary_trade_semantic_mapping_response_v9",
        "broker_reports_ordinary_trade_semantic_mapping_response_v10",
        _MODEL_SELECTED_CLASSIFICATION_EVIDENCE_RESPONSE_V11,
        "broker_reports_ordinary_trade_semantic_mapping_response_v13",
    }
)
_MODEL_SELECTED_CLASSIFICATION_EVIDENCE_SCHEMA_VERSIONS = frozenset(
    {
        "broker_reports_ordinary_trade_semantic_mapping_response_v9",
        "broker_reports_ordinary_trade_semantic_mapping_response_v10",
        _MODEL_SELECTED_CLASSIFICATION_EVIDENCE_RESPONSE_V11,
        MAPPING_RESPONSE_SCHEMA_VERSION,
    }
)
_MODEL_SUPPLIED_MISSING_REQUIRED_ROLES_SCHEMA_VERSIONS = frozenset(
    {
        "broker_reports_ordinary_trade_semantic_mapping_response_v6",
        "broker_reports_ordinary_trade_semantic_mapping_response_v7",
        "broker_reports_ordinary_trade_semantic_mapping_response_v8",
        "broker_reports_ordinary_trade_semantic_mapping_response_v9",
        "broker_reports_ordinary_trade_semantic_mapping_response_v10",
    }
)
_MODEL_SPARSE_COLUMNS_SCHEMA_VERSIONS = frozenset(
    {
        _MODEL_SELECTED_CLASSIFICATION_EVIDENCE_RESPONSE_V11,
        MAPPING_RESPONSE_SCHEMA_VERSION,
    }
)
_MODEL_SUPPLIED_CLASSIFICATION_EVIDENCE_SCHEMA_VERSIONS = frozenset(
    {
        "broker_reports_ordinary_trade_semantic_mapping_response_v6",
        "broker_reports_ordinary_trade_semantic_mapping_response_v7",
        *_MODEL_SELECTED_CLASSIFICATION_EVIDENCE_SCHEMA_VERSIONS,
    }
)
ANSWER_RESPONSE_SCHEMA_VERSION = (
    "broker_reports_ordinary_trade_mapping_answer_response_v1"
)
MAPPING_CASE_SCHEMA_VERSION = "broker_reports_ordinary_trade_mapping_case_v2"
MAPPING_BATCH_PLAN_SCHEMA_VERSION = "broker_reports_ordinary_trade_mapping_batch_plan_v1"
INSTRUCTIONAL_CLASSIFICATION_DESCRIPTOR_SCHEMA_VERSION = (
    "broker_reports_instructional_table_descriptor_v1"
)
ANSWER_PROMPT_VERSION = "ordinary_trade_mapping_answer_prompt_v2"
FACTORY_REQUIRED = (
    "OrdinaryTradeSemanticMappingFactory.create is the only unknown-schema "
    "mapping contract and case-qualification entrypoint"
)
FORBIDDEN = (
    "broker/year/filename routing, fuzzy reuse, model-authored source values, "
    "partial Fact publication, regex interpretation of human answers"
)

_MAPPING_STATUSES = {
    "COMPLETE",
    "CLARIFICATION_REQUIRED",
    "UNSUPPORTED",
    "SPECIALIST_REVIEW_REQUIRED",
    "CURRENCY_ASSERTION_REQUIRED",
}
_TABLE_DISPOSITIONS = {
    "HEADER_ABSENT",
    "SECURITY_TRADES",
    "SECURITY_TRADES_INCOMPLETE",
    "NO_NAMED_CONSUMER",
    "UNSUPPORTED_FINANCIAL_MEANING",
}
_NO_CONSUMER_KINDS = {
    "INSTRUCTIONAL_REFERENCE",
    "OTHER_NO_NAMED_CONSUMER",
}
_SEMANTIC_ROLES = {
    "asset_name",
    "trade_date",
    "side",
    "quantity",
    "unit_price",
    "currency",
    "gross_amount",
    "broker_commission",
    "exchange_commission",
    "settlement_date",
    "trade_time",
    "security_code",
    "accrued_interest",
    "trade_id",
    "venue",
    "comment",
    "status",
    "description",
    "unmapped",
}
_REQUIRED_ROLES = {
    "asset_name",
    "trade_date",
    "side",
    "quantity",
    "unit_price",
    "currency",
    "gross_amount",
}
_MAX_TABLES = 64
_MAX_ROWS_PER_TABLE = 256
# This is a structural work bound, not the authoritative model-context bound.
# The serialized package limit below remains the final admission check.  Keep
# the structural bound high enough for one ordinary report with many narrow
# tables, while rejecting pathological Canonical shapes before deep copying.
_MAX_CELLS_TOTAL = 16_384
_MAX_CONTEXT_BYTES = 524_288
# Keep enough local source structure to distinguish an instructional table from
# a declarant record, while retaining the prior bounded context budget.
_MAX_LOCAL_CONTEXT_ITEMS = 8
_MAX_LOCAL_CONTEXT_ITEMS_PER_RELATION = 4
_MAX_LOCAL_CONTEXT_LITERAL_CHARS = 512
_MAX_DISTINCT_VALUES_PER_COLUMN = 64
_MAX_EXCLUSION_CONFIRMATION_TABLES = 12
_DECISION_KINDS = {
    "COLUMN_ROLE",
    "AMOUNT_CURRENCY_BINDING",
    "SIDE_VALUE",
    "TABLE_DISPOSITION",
}


class OrdinaryTradeSemanticMappingError(RuntimeError):
    def __init__(self, code: str, *, diagnostic_code: str | None = None) -> None:
        self.code = code
        # A diagnostic code describes only the rejected wire shape.  It never
        # contains a source literal, model text, table identifier or reference.
        # The product receipt keeps the stable public code; an isolated lab may
        # use this extra value to locate the contract seam without inventing a
        # second validator.
        self.diagnostic_code = diagnostic_code
        super().__init__(code)


class OrdinaryTradeSemanticMappingFactory:
    @staticmethod
    def create() -> "OrdinaryTradeSemanticMapping":
        return OrdinaryTradeSemanticMapping()


class OrdinaryTradeSemanticMapping:
    def mapping_response_contract_failure_code(self, response: Any) -> str | None:
        """Classify only the public shape of a rejected model response.

        The returned code deliberately contains no model text or source values.  It
        is retained in the private case receipt so an invalid strict response can
        be repaired at the contract boundary rather than guessed from a document.
        """

        value = getattr(response, "content", response)
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                return "ordinary_trade_semantic_mapping_response_json_invalid"
        if not isinstance(value, dict):
            return "ordinary_trade_semantic_mapping_response_shape_invalid"
        if set(value) != {
            "schema_version",
            "status",
            "table_decisions",
            "clarification",
            "message",
        }:
            return "ordinary_trade_semantic_mapping_response_fields_invalid"
        if value.get("schema_version") not in (
            _LEGACY_MAPPING_RESPONSE_SCHEMA_VERSIONS
            | {MAPPING_RESPONSE_SCHEMA_VERSION}
        ):
            return "ordinary_trade_semantic_mapping_response_version_invalid"
        if value.get("status") not in _MAPPING_STATUSES:
            return "ordinary_trade_semantic_mapping_response_status_invalid"
        if not isinstance(value.get("table_decisions"), list):
            return "ordinary_trade_semantic_mapping_response_decisions_invalid"
        if not isinstance(value.get("message"), str) or not value["message"].strip():
            return "ordinary_trade_semantic_mapping_response_message_invalid"
        return None

    def answer_prompt(self) -> Gate2ManagedPrompt:
        content = (
            "Interpret one natural-language answer to one supplied mapping question. "
            "Do not infer tax meaning or inspect broker identity. Select CANDIDATE only "
            "when the answer unambiguously matches exactly one supplied option_id. "
            "Use SPECIALIST_REVIEW, not CLARIFY, when the user says that none of the "
            "offered options is true, that the needed value is absent, or that they "
            "cannot determine the answer. Use CLARIFY only when the user message is "
            "too unclear to establish either a supplied option or that explicit stop. "
            "Copy a short exact evidence_quote from the "
            "user message. Return only strict JSON."
        )
        return _managed_prompt(
            version=ANSWER_PROMPT_VERSION,
            content=content,
            output_schema_id=ANSWER_RESPONSE_SCHEMA_VERSION,
        )

    def mapping_response_format(self) -> dict[str, Any]:
        return _response_format(
            name="ordinary_trade_semantic_mapping_v1",
            schema=_mapping_response_schema(),
        )

    def answer_response_format(self) -> dict[str, Any]:
        return _response_format(
            name="ordinary_trade_mapping_answer_v1",
            schema=_answer_response_schema(),
        )

    def build_instructional_classification_descriptor(
        self, *, canonical: Mapping[str, Any], table_node_id: str
    ) -> dict[str, Any]:
        """Build the sole model-visible case for one Canonical table.

        The descriptor remains transient until a MappingCase owner persists a
        safe execution receipt.  It contains no caller-authored table meaning.
        """
        tables = _selected_table_surfaces(
            canonical=canonical, target_table_node_ids=[table_node_id]
        )
        model_tables, refs_by_node_id = _model_table_surfaces(
            canonical, target_table_node_ids=[table_node_id]
        )
        if (
            len(tables) != 1
            or len(model_tables) != 1
            or refs_by_node_id.get(table_node_id) != model_tables[0].get("table_ref")
        ):
            _fail("ordinary_trade_instructional_descriptor_invalid")
        # The retired one-table classifier has its own frozen wire contract.
        # It is not the current product route and must not silently gain the
        # newer physical-header field.
        classifier_table = copy.deepcopy(model_tables[0])
        classifier_table.pop("physical_header_row", None)
        case = build_instructional_classification_case(table=classifier_table)
        return {
            "schema_version": INSTRUCTIONAL_CLASSIFICATION_DESCRIPTOR_SCHEMA_VERSION,
            "table_node_id": table_node_id,
            "table_ref": model_tables[0]["table_ref"],
            "case_sha256": _sha256_json(case),
            "case": case,
        }

    def admit_instructional_classification(
        self,
        *,
        canonical: Mapping[str, Any],
        descriptor: Mapping[str, Any],
        response: Any,
    ) -> dict[str, Any]:
        """Admit a narrow model answer as an owner-bound table resolution.

        A coordinator can request this operation, but it cannot manufacture a
        resolution: this owner rebuilds the descriptor from Canonical and uses
        the existing table-decision validator for evidence and structural scope.
        """
        table_node_id = descriptor.get("table_node_id") if isinstance(descriptor, Mapping) else None
        if not isinstance(table_node_id, str) or not table_node_id:
            _fail("ordinary_trade_instructional_descriptor_invalid")
        expected = self.build_instructional_classification_descriptor(
            canonical=canonical, table_node_id=table_node_id
        )
        if dict(descriptor) != expected:
            _fail("ordinary_trade_instructional_descriptor_stale")
        try:
            accepted = validate_instructional_classification_response(
                response=_strict_model_value(response), case=expected["case"]
            )
        except InstructionalClassificationContractError as exc:
            _fail(f"ordinary_trade_instructional_{exc}")
        classification = accepted["classification"]
        if classification != "INSTRUCTIONAL_REFERENCE":
            return {
                "classification": classification,
                "table_node_id": table_node_id,
                "table_resolution": None,
            }
        table = _selected_table_surfaces(
            canonical=canonical, target_table_node_ids=[table_node_id]
        )[0]
        resolved = _validate_table_decision(
            decision={
                "table_node_id": table_node_id,
                "header_row": accepted["header_row"],
                "disposition": "NO_NAMED_CONSUMER",
                "columns": [],
                "amount_currency_bindings": [],
                "side_values": [],
                "row_dispositions": [],
                "no_consumer_kind": "INSTRUCTIONAL_REFERENCE",
                "classification_evidence": accepted["classification_evidence"],
            },
            table=table,
            model_supplies_classification_evidence=True,
            preserve_model_classification_evidence=True,
        )
        resolution = {
            key: copy.deepcopy(resolved[key])
            for key in (
                "table_node_id",
                "header_row",
                "structural_fingerprint",
                "evidence_surface",
                "disposition",
                "security_trade_rows",
                "no_consumer_kind",
                "classification_evidence",
            )
            if key in resolved
        }
        return {
            "classification": classification,
            "table_node_id": table_node_id,
            "table_resolution": resolution,
        }

    def rebind_instructional_classification_outcomes(
        self,
        *,
        canonical: Mapping[str, Any],
        target_table_node_ids: Iterable[str],
        classifier_outcomes: Iterable[Mapping[str, Any]],
    ) -> dict[str, Any]:
        """Rebind stored narrow answers to the exact current Canonical scope."""

        target_ids = _ordered_target_table_node_ids(
            canonical=canonical, target_table_node_ids=target_table_node_ids
        )
        outcomes = list(classifier_outcomes)
        if len(outcomes) != len(target_ids):
            _fail("ordinary_trade_instructional_classifier_count_invalid")
        instructional_resolutions: list[dict[str, Any]] = []
        mapping_target_ids: list[str] = []
        for expected_id, item in zip(target_ids, outcomes, strict=True):
            if (
                not isinstance(item, Mapping)
                or set(item) != {"table_node_id", "response"}
                or item.get("table_node_id") != expected_id
            ):
                _fail("ordinary_trade_instructional_classifier_order_invalid")
            admitted = self.admit_instructional_classification(
                canonical=canonical,
                descriptor=self.build_instructional_classification_descriptor(
                    canonical=canonical, table_node_id=expected_id
                ),
                response=item.get("response"),
            )
            if admitted["classification"] == "SPECIALIST_REVIEW_REQUIRED":
                _fail("ordinary_trade_instructional_specialist_review_required")
            resolution = admitted["table_resolution"]
            if resolution is None:
                mapping_target_ids.append(expected_id)
            else:
                instructional_resolutions.append(resolution)
        return {
            "target_table_node_ids": target_ids,
            "instructional_resolutions": instructional_resolutions,
            "mapping_target_table_node_ids": mapping_target_ids,
        }

    def finalize_instructional_preclassification(
        self,
        *,
        canonical: Mapping[str, Any],
        canonical_binding: Mapping[str, str],
        user_scope_sha256: str,
        target_table_node_ids: Iterable[str],
        classifier_outcomes: Iterable[Mapping[str, Any]],
        mapping_outcome: Mapping[str, Any] | None,
        frozen_mappings: Iterable[Mapping[str, Any]] = (),
    ) -> dict[str, Any]:
        """Publish one complete scope after re-binding its narrow classifications.

        The coordinator supplies opaque model responses only.  This owner rebuilds
        every descriptor from the current Canonical before a classifier result can
        exclude a table from ordinary role mapping.
        """

        rebound = self.rebind_instructional_classification_outcomes(
            canonical=canonical,
            target_table_node_ids=target_table_node_ids,
            classifier_outcomes=classifier_outcomes,
        )
        target_ids = rebound["target_table_node_ids"]
        instructional_resolutions = rebound["instructional_resolutions"]
        mapping_target_ids = rebound["mapping_target_table_node_ids"]

        mapping_resolutions: list[dict[str, Any]] = []
        qualified_mappings: list[dict[str, Any]] = []
        qualification_receipts: list[dict[str, Any]] = []
        model_response_sha256 = None
        execution_metadata_sha256 = None
        if mapping_target_ids:
            if not isinstance(mapping_outcome, Mapping) or mapping_outcome.get("status") != "COMPLETE":
                _fail("ordinary_trade_instructional_mapping_outcome_required")
            mapping_resolutions = copy.deepcopy(mapping_outcome.get("table_resolutions") or [])
            qualified_mappings = copy.deepcopy(mapping_outcome.get("qualified_mappings") or [])
            qualification_receipts = copy.deepcopy(
                mapping_outcome.get("qualification_receipts") or []
            )
            if (
                not all(
                    isinstance(value, list)
                    for value in (
                        mapping_resolutions,
                        qualified_mappings,
                        qualification_receipts,
                    )
                )
                or [item.get("table_node_id") for item in mapping_resolutions]
                != mapping_target_ids
                or len(qualified_mappings) != len(qualification_receipts)
            ):
                _fail("ordinary_trade_instructional_mapping_outcome_invalid")
            model_response_sha256 = mapping_outcome.get("model_response_sha256")
            execution_metadata_sha256 = mapping_outcome.get(
                "execution_metadata_sha256"
            )
        elif mapping_outcome is not None:
            _fail("ordinary_trade_instructional_mapping_outcome_unexpected")

        merged_resolutions = [*instructional_resolutions, *mapping_resolutions]
        merged_ids = [
            item.get("table_node_id")
            for item in merged_resolutions
            if isinstance(item, Mapping)
        ]
        if (
            len(merged_ids) != len(merged_resolutions)
            or any(not isinstance(item, str) or not item for item in merged_ids)
        ):
            _fail("ordinary_trade_instructional_resolution_invalid")
        if len(merged_ids) != len(set(merged_ids)):
            _fail("ordinary_trade_instructional_resolution_overlap")
        if set(merged_ids) != set(target_ids):
            _fail("ordinary_trade_instructional_resolution_coverage_invalid")
        resolutions_by_id = {
            item["table_node_id"]: copy.deepcopy(item)
            for item in merged_resolutions
        }
        table_resolutions = [resolutions_by_id[item] for item in target_ids]

        receipts_by_id = {
            item.get("qualification_id"): item
            for item in qualification_receipts
            if isinstance(item, Mapping) and item.get("qualification_id")
        }
        if len(receipts_by_id) != len(qualification_receipts):
            _fail("ordinary_trade_instructional_mapping_outcome_invalid")
        authority = OrdinaryTradeQualifiedMappingAuthorityFactory.create()
        scoped_mappings: list[dict[str, Any]] = []
        for mapping in qualified_mappings:
            if not isinstance(mapping, Mapping):
                _fail("ordinary_trade_instructional_mapping_outcome_invalid")
            receipt = receipts_by_id.get(
                (mapping.get("qualification_ref") or {}).get("qualification_id")
            )
            table_node_id = (
                (receipt.get("case_scope") or {}).get("table_node_id")
                if isinstance(receipt, Mapping)
                else None
            )
            if table_node_id not in mapping_target_ids:
                _fail("ordinary_trade_instructional_mapping_outcome_invalid")
            expected_scope = {
                **{
                    key: str(canonical_binding.get(key) or "")
                    for key in (
                        "document_id",
                        "canonical_version_id",
                        "canonical_root_sha256",
                        "source_artifact_ref",
                        "source_sha256",
                    )
                },
                "user_scope_sha256": user_scope_sha256,
                "table_node_id": table_node_id,
            }
            if not all(expected_scope.values()):
                _fail("ordinary_trade_semantic_mapping_canonical_binding_invalid")
            authority.validate_case_mapping(
                mapping=mapping, receipt=receipt, expected_case_scope=expected_scope
            )
            scoped_mappings.append(
                {"table_node_id": table_node_id, "mapping": copy.deepcopy(mapping)}
            )
        compiler_resolutions = [
            item
            for item in table_resolutions
            if item.get("disposition") != "SECURITY_TRADES_INCOMPLETE"
        ]
        projection = OrdinaryTradeSemanticCompilerFactory.create().compile(
            canonical=canonical,
            canonical_binding=canonical_binding,
            mappings=frozen_mappings,
            scoped_mappings=scoped_mappings,
            table_resolutions=compiler_resolutions,
        )
        incomplete_ids = {
            item["table_node_id"]
            for item in table_resolutions
            if item.get("disposition") == "SECURITY_TRADES_INCOMPLETE"
        }
        if any(
            item.get("disposition") == "RELEVANT_UNMAPPED"
            and item.get("table_node_id") in set(target_ids)
            and item.get("table_node_id") not in incomplete_ids
            for item in projection["source_observations"]
        ):
            _fail("ordinary_trade_instructional_compiler_coverage_invalid")
        return {
            "status": "COMPLETE",
            "message": "Instructional references are separated before role mapping.",
            "question": None,
            "qualified_mappings": qualified_mappings,
            "qualification_receipts": qualification_receipts,
            "table_resolutions": table_resolutions,
            "model_response_sha256": model_response_sha256,
            "execution_metadata_sha256": execution_metadata_sha256,
        }

    def build_mapping_package(
        self,
        *,
        canonical: Mapping[str, Any],
        confirmed_understandings: list[dict[str, Any]],
        target_table_node_ids: Iterable[str] | None = None,
        physical_table_continuation_context: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        tables, refs_by_node_id = _model_table_surfaces(
            canonical,
            target_table_node_ids=target_table_node_ids,
            include_column_distinct_values=False,
        )
        confirmed_decisions = []
        user_currency_assertions = []
        for item in confirmed_understandings:
            decision = copy.deepcopy(item["decision"])
            # This case-bound user input belongs to deterministic projection,
            # not to model-visible source decisions.  The model receives only a
            # separately marked instruction so it does not ask the same user
            # question twice.
            if decision.get("decision_kind") == "USER_PROVIDED_CURRENCY":
                if (
                    set(decision)
                    != {
                        "schema_version",
                        "assertion_id",
                        "currency_code",
                        "case_binding_sha256",
                        "table_node_ids",
                        "decision_kind",
                    }
                    or not isinstance(decision["currency_code"], str)
                    or re.fullmatch(r"[A-Z]{3}", decision["currency_code"])
                    is None
                    or not isinstance(decision["table_node_ids"], list)
                ):
                    _fail("ordinary_trade_user_currency_assertion_invalid")
                for table_node_id in decision["table_node_ids"]:
                    table_ref = refs_by_node_id.get(table_node_id)
                    if table_ref is not None:
                        user_currency_assertions.append(
                            {
                                "table_ref": table_ref,
                                "currency_code": decision["currency_code"],
                            }
                        )
                continue
            table_node_id = decision.pop("table_node_id")
            if table_node_id not in refs_by_node_id:
                continue
            decision["table_ref"] = refs_by_node_id[table_node_id]
            confirmed_decisions.append(decision)
        continuation_links = _physical_continuation_links_for_scope(
            canonical=canonical,
            target_table_node_ids=list(refs_by_node_id),
            physical_table_continuation_context=physical_table_continuation_context,
        )
        package = {
            "phase": "map",
            "case": {
                "allowed_semantic_roles": sorted(_SEMANTIC_ROLES),
                "required_security_trade_roles": sorted(_REQUIRED_ROLES),
                "allowed_table_dispositions": sorted(_TABLE_DISPOSITIONS),
                "tables": tables,
                "confirmed_decisions": confirmed_decisions,
                "user_currency_assertions": user_currency_assertions,
            },
        }
        if continuation_links:
            package["case"]["physical_table_continuation_links"] = [
                {
                    "parent_table_ref": refs_by_node_id[parent_id],
                    "child_table_ref": refs_by_node_id[child_id],
                }
                for parent_id, child_id in continuation_links
            ]
        if len(_canonical_json(package).encode("utf-8")) > _MAX_CONTEXT_BYTES:
            _fail("ordinary_trade_semantic_mapping_context_limit")
        return package

    def build_classification_evidence_envelopes(
        self,
        *,
        canonical: Mapping[str, Any],
        target_table_node_ids: Iterable[str],
    ) -> dict[str, list[dict[str, str]]]:
        """Bind explicit Canonical tables to their complete private evidence.

        This narrow owner seam is for a trusted preflight receipt only.  It does
        not reuse the model package because that representation deliberately
        strips Canonical ids and private source evidence.  It returns no source
        literal: only the already-validated, bounded provenance envelope.
        """

        target_ids = _ordered_target_table_node_ids(
            canonical=canonical,
            target_table_node_ids=target_table_node_ids,
        )
        tables = _selected_table_surfaces(
            canonical=canonical,
            target_table_node_ids=target_ids,
        )
        if [item["table_node_id"] for item in tables] != target_ids:
            _fail("ordinary_trade_semantic_mapping_target_scope_stale")
        return {
            table["table_node_id"]: _classification_evidence_envelope(table=table)
            for table in tables
        }

    def build_mapping_batch_plan(
        self,
        *,
        canonical: Mapping[str, Any],
        confirmed_understandings: list[dict[str, Any]],
        target_table_node_ids: Iterable[str],
        physical_table_continuation_context: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Split one explicit table scope into deterministic bounded packages.

        This is a transport plan only.  It neither classifies tables nor changes
        their meaning: every emitted batch is an unchanged call to this owner's
        existing ``build_mapping_package``.  The canonical node order owns the
        order, so caller ordering cannot alter a model-visible package.
        """

        target_ids = _ordered_target_table_node_ids(
            canonical=canonical,
            target_table_node_ids=target_table_node_ids,
        )
        batches: list[dict[str, Any]] = []
        pending: list[str] = []
        for group in _physical_continuation_batch_groups(
            canonical=canonical,
            target_table_node_ids=target_ids,
            physical_table_continuation_context=physical_table_continuation_context,
        ):
            candidate = [*pending, *group]
            try:
                package = self.build_mapping_package(
                    canonical=canonical,
                    confirmed_understandings=confirmed_understandings,
                    target_table_node_ids=candidate,
                    physical_table_continuation_context=physical_table_continuation_context,
                )
            except OrdinaryTradeSemanticMappingError as exc:
                if exc.code != "ordinary_trade_semantic_mapping_context_limit":
                    raise
                package = None
            if package is not None:
                pending = candidate
                continue
            if not pending:
                # A singleton that cannot fit has no safe smaller transport.
                _fail("ordinary_trade_semantic_mapping_context_limit")
            finalized = self.build_mapping_package(
                canonical=canonical,
                confirmed_understandings=confirmed_understandings,
                target_table_node_ids=pending,
                physical_table_continuation_context=physical_table_continuation_context,
            )
            batches.append(
                {
                    "batch_id": f"batch_{len(batches) + 1:04d}",
                    "target_table_node_ids": list(pending),
                    "mapping_package_sha256": _sha256_json(finalized),
                }
            )
            self.build_mapping_package(
                canonical=canonical,
                confirmed_understandings=confirmed_understandings,
                target_table_node_ids=group,
                physical_table_continuation_context=physical_table_continuation_context,
            )
            pending = list(group)
        if not pending:
            _fail("ordinary_trade_mapping_batch_plan_invalid")
        finalized = self.build_mapping_package(
            canonical=canonical,
            confirmed_understandings=confirmed_understandings,
            target_table_node_ids=pending,
            physical_table_continuation_context=physical_table_continuation_context,
        )
        batches.append(
            {
                "batch_id": f"batch_{len(batches) + 1:04d}",
                "target_table_node_ids": list(pending),
                "mapping_package_sha256": _sha256_json(finalized),
            }
        )
        plan = {
            "schema_version": MAPPING_BATCH_PLAN_SCHEMA_VERSION,
            "target_table_node_ids": target_ids,
            "batches": batches,
        }
        _validate_mapping_batch_plan(
            plan=plan,
            canonical=canonical,
            confirmed_understandings=confirmed_understandings,
            physical_table_continuation_context=physical_table_continuation_context,
        )
        return plan

    def aggregate_mapping_batch_outcomes(
        self,
        *,
        canonical: Mapping[str, Any],
        canonical_binding: Mapping[str, str],
        user_scope_sha256: str,
        confirmed_understandings: list[dict[str, Any]],
        batch_plan: Mapping[str, Any],
        batch_outcomes: Iterable[Mapping[str, Any]],
        frozen_mappings: Iterable[Mapping[str, Any]] = (),
        transport_confirmed_understandings: list[dict[str, Any]] | None = None,
        physical_table_continuation_context: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Validate a complete batch set, then replay the existing compiler once.

        The method intentionally merges only already-qualified table material.
        It does not choose a disposition, repair an outcome, deduplicate a
        mapping, or make a second semantic decision.
        """

        plan = _validate_mapping_batch_plan(
            plan=batch_plan,
            canonical=canonical,
            confirmed_understandings=(
                confirmed_understandings if transport_confirmed_understandings is None
                else transport_confirmed_understandings
            ),
            physical_table_continuation_context=physical_table_continuation_context,
        )
        submitted = list(batch_outcomes)
        expected_batches = plan["batches"]
        if len(submitted) != len(expected_batches):
            _fail("ordinary_trade_mapping_batch_outcome_coverage_invalid")
        outcomes_by_id: dict[str, Mapping[str, Any]] = {}
        for item in submitted:
            if (
                not isinstance(item, Mapping)
                or set(item) != {"batch_id", "outcome"}
                or not isinstance(item.get("batch_id"), str)
                or not isinstance(item.get("outcome"), Mapping)
                or item["batch_id"] in outcomes_by_id
            ):
                _fail("ordinary_trade_mapping_batch_outcome_invalid")
            outcomes_by_id[item["batch_id"]] = item["outcome"]
        if set(outcomes_by_id) != {item["batch_id"] for item in expected_batches}:
            _fail("ordinary_trade_mapping_batch_outcome_coverage_invalid")

        all_mappings: list[dict[str, Any]] = []
        all_receipts: list[dict[str, Any]] = []
        all_scoped_mappings: list[dict[str, Any]] = []
        all_resolutions: list[dict[str, Any]] = []
        authority = OrdinaryTradeQualifiedMappingAuthorityFactory.create()
        for batch in expected_batches:
            expected_ids = batch["target_table_node_ids"]
            outcome = outcomes_by_id[batch["batch_id"]]
            if outcome.get("status") != "COMPLETE":
                _fail("ordinary_trade_mapping_batch_not_complete")
            mappings = outcome.get("qualified_mappings")
            receipts = outcome.get("qualification_receipts")
            resolutions = outcome.get("table_resolutions")
            if not all(isinstance(value, list) for value in (mappings, receipts, resolutions)):
                _fail("ordinary_trade_mapping_batch_outcome_invalid")
            resolution_ids = [
                item.get("table_node_id") if isinstance(item, Mapping) else None
                for item in resolutions
            ]
            if resolution_ids != expected_ids:
                _fail("ordinary_trade_mapping_batch_outcome_coverage_invalid")
            if len(mappings) != len(receipts):
                _fail("ordinary_trade_mapping_batch_outcome_invalid")
            receipts_by_id = {
                item.get("qualification_id"): item
                for item in receipts
                if isinstance(item, Mapping) and item.get("qualification_id")
            }
            if len(receipts_by_id) != len(receipts):
                _fail("ordinary_trade_mapping_batch_outcome_invalid")
            for mapping in mappings:
                if not isinstance(mapping, Mapping):
                    _fail("ordinary_trade_mapping_batch_outcome_invalid")
                receipt = receipts_by_id.get(
                    (mapping.get("qualification_ref") or {}).get("qualification_id")
                )
                table_node_id = (
                    (receipt.get("case_scope") or {}).get("table_node_id")
                    if isinstance(receipt, Mapping)
                    else None
                )
                if table_node_id not in expected_ids:
                    _fail("ordinary_trade_mapping_batch_outcome_coverage_invalid")
                expected_scope = {
                    **{
                        key: str(canonical_binding.get(key) or "")
                        for key in (
                            "document_id",
                            "canonical_version_id",
                            "canonical_root_sha256",
                            "source_artifact_ref",
                            "source_sha256",
                        )
                    },
                    "user_scope_sha256": user_scope_sha256,
                    "table_node_id": table_node_id,
                }
                if not all(expected_scope.values()):
                    _fail("ordinary_trade_semantic_mapping_canonical_binding_invalid")
                authority.validate_case_mapping(
                    mapping=mapping,
                    receipt=receipt,
                    expected_case_scope=expected_scope,
                )
                all_scoped_mappings.append(
                    {
                        "table_node_id": table_node_id,
                        "mapping": copy.deepcopy(mapping),
                    }
                )
            all_mappings.extend(copy.deepcopy(mappings))
            all_receipts.extend(copy.deepcopy(receipts))
            all_resolutions.extend(copy.deepcopy(resolutions))

        resolution_ids = [item["table_node_id"] for item in all_resolutions]
        if resolution_ids != plan["target_table_node_ids"]:
            _fail("ordinary_trade_mapping_batch_outcome_coverage_invalid")
        compiler_resolutions = [
            item
            for item in all_resolutions
            if item.get("disposition") != "SECURITY_TRADES_INCOMPLETE"
        ]
        projection = OrdinaryTradeSemanticCompilerFactory.create().compile(
            canonical=canonical,
            canonical_binding=canonical_binding,
            mappings=frozen_mappings,
            scoped_mappings=all_scoped_mappings,
            table_resolutions=compiler_resolutions,
        )
        incomplete_ids = {
            item["table_node_id"]
            for item in all_resolutions
            if item.get("disposition") == "SECURITY_TRADES_INCOMPLETE"
        }
        target_ids = set(plan["target_table_node_ids"])
        if any(
            item.get("disposition") == "RELEVANT_UNMAPPED"
            and item.get("table_node_id") in target_ids
            and item.get("table_node_id") not in incomplete_ids
            for item in projection["source_observations"]
        ):
            _fail("ordinary_trade_mapping_batch_compiler_coverage_invalid")
        return {
            "status": "COMPLETE",
            "batch_plan_sha256": _sha256_json(plan),
            "qualified_mappings": all_mappings,
            "qualification_receipts": all_receipts,
            "table_resolutions": all_resolutions,
            "projection": projection,
        }

    def build_answer_package(
        self,
        *,
        question: dict[str, Any],
        user_message: str,
    ) -> dict[str, Any]:
        message = str(user_message or "").strip()
        if not message or len(message.encode("utf-8")) > 16_384:
            _fail("ordinary_trade_mapping_answer_invalid")
        _validate_question(question, internal=True)
        return {
            "phase": "interpret_answer",
            "case": {
                "question": {
                    "question_id": question["question_id"],
                    "question": question["question"],
                    "options": [
                        {
                            "option_id": item["option_id"],
                            "label": item["label"],
                        }
                        for item in question["options"]
                    ],
                },
                "user_message": message,
            },
        }

    @staticmethod
    def interpret_manual_confirmation(user_message: str) -> bool | None:
        """Accept the two exact confirmation strings rendered by the public UI."""

        text = str(user_message or "").strip().casefold()
        if text in {"да", "yes"}:
            return True
        if text in {"нет", "no"}:
            return False
        return None

    def validate_mapping_response(
        self,
        *,
        response: Any,
        canonical: Mapping[str, Any],
        canonical_binding: Mapping[str, str],
        model_id: str,
        provider_profile_id: str,
        execution_metadata: Any,
        confirmed_understandings: list[dict[str, Any]],
        user_scope_sha256: str,
        target_table_node_ids: Iterable[str] | None = None,
        frozen_mappings: Iterable[Mapping[str, Any]] = (),
    ) -> dict[str, Any]:
        value = _strict_model_value(response)
        if (
            set(value)
            != {
                "schema_version",
                "status",
                "table_decisions",
                "clarification",
                "message",
            }
            or value.get("schema_version")
            not in _LEGACY_MAPPING_RESPONSE_SCHEMA_VERSIONS
            | {MAPPING_RESPONSE_SCHEMA_VERSION}
            or value.get("status") not in _MAPPING_STATUSES
            or not isinstance(value.get("table_decisions"), list)
            or not isinstance(value.get("message"), str)
            or not value["message"].strip()
        ):
            _fail("ordinary_trade_semantic_mapping_response_invalid")
        table_surfaces = _selected_table_surfaces(
            canonical=canonical,
            target_table_node_ids=target_table_node_ids,
        )
        tables = {item["table_node_id"]: item for item in table_surfaces}
        _model_tables, refs_by_node_id = _model_table_surfaces(
            canonical,
            target_table_node_ids=target_table_node_ids,
        )
        node_ids_by_ref = {value: key for key, value in refs_by_node_id.items()}
        status = value["status"]
        if status == "CLARIFICATION_REQUIRED":
            if value["table_decisions"] or not isinstance(
                value.get("clarification"), dict
            ):
                _fail("ordinary_trade_semantic_mapping_clarification_invalid")
            question = _normalize_model_question(
                value["clarification"],
                tables=tables,
                node_ids_by_ref=node_ids_by_ref,
            )
            return {
                "status": status,
                "message": "Mapping requires a retired interactive decision.",
                "question": question,
                "model_response_sha256": _sha256_json(value),
                "execution_metadata_sha256": _execution_metadata_sha256(
                    execution_metadata
                ),
            }
        if status == "CURRENCY_ASSERTION_REQUIRED":
            if value.get("clarification") is not None:
                _fail("ordinary_trade_user_currency_request_invalid")
            decisions = _normalize_model_decisions(
                value["table_decisions"], node_ids_by_ref=node_ids_by_ref
            )
            ids = [
                item.get("table_node_id")
                for item in decisions
                if isinstance(item, dict)
            ]
            if (
                len(ids) != len(tables)
                or set(ids) != set(tables)
                or len(ids) != len(set(ids))
            ):
                _fail("ordinary_trade_semantic_mapping_table_coverage_invalid")
            resolved = [
                _validate_table_decision(
                    decision=item,
                    table=tables[str(item["table_node_id"])],
                    allow_user_currency=True,
                    model_supplies_classification_evidence=(
                        value["schema_version"]
                        in _MODEL_SUPPLIED_CLASSIFICATION_EVIDENCE_SCHEMA_VERSIONS
                    ),
                    model_supplies_missing_required_roles=(
                        value["schema_version"]
                        in _MODEL_SUPPLIED_MISSING_REQUIRED_ROLES_SCHEMA_VERSIONS
                    ),
                    model_supplies_sparse_columns=(
                        value["schema_version"]
                        in _MODEL_SPARSE_COLUMNS_SCHEMA_VERSIONS
                    ),
                    preserve_model_classification_evidence=(
                        value["schema_version"]
                        in _MODEL_SELECTED_CLASSIFICATION_EVIDENCE_SCHEMA_VERSIONS
                    ),
                )
                for item in decisions
            ]
            if any(
                item["disposition"] == "UNSUPPORTED_FINANCIAL_MEANING"
                for item in resolved
            ):
                return {
                    "status": "UNSUPPORTED",
                    "message": value["message"].strip(),
                    "question": None,
                    "qualified_mappings": [],
                    "qualification_receipts": [],
                    "table_resolutions": [],
                    "model_response_sha256": _sha256_json(value),
                    "execution_metadata_sha256": _execution_metadata_sha256(
                        execution_metadata
                    ),
                }
            scoped = [
                item["table_node_id"]
                for item in resolved
                if item["disposition"] == "SECURITY_TRADES"
            ]
            if not scoped:
                _fail("ordinary_trade_user_currency_request_invalid")
            return {
                "status": status,
                "message": "Укажите валюту сделок в формате «Валюта: USD». Значение будет сохранено как ваш ответ, а не как текст PDF.",
                "question": None,
                "currency_mapping_plan": {
                    "response": copy.deepcopy(value),
                    "execution_metadata": _execution_metadata_value(execution_metadata),
                    "table_node_ids": sorted(scoped),
                    # Model table_ref values are positional, so preserve the
                    # exact canonical order used for this request.
                    "target_table_node_ids": list(tables),
                },
                "currency_table_node_ids": sorted(scoped),
                "model_response_sha256": _sha256_json(value),
                "execution_metadata_sha256": _execution_metadata_sha256(execution_metadata),
            }
        if status == "SPECIALIST_REVIEW_REQUIRED":
            if value["table_decisions"] or value.get("clarification") is not None:
                _fail("ordinary_trade_semantic_mapping_specialist_invalid")
            return {
                "status": status,
                "message": value["message"].strip(),
                "question": None,
                "model_response_sha256": _sha256_json(value),
                "execution_metadata_sha256": _execution_metadata_sha256(
                    execution_metadata
                ),
            }
        if value.get("clarification") is not None:
            _fail("ordinary_trade_semantic_mapping_clarification_invalid")
        decisions = _normalize_model_decisions(
            value["table_decisions"], node_ids_by_ref=node_ids_by_ref
        )
        ids = [
            item.get("table_node_id") for item in decisions if isinstance(item, dict)
        ]
        if (
            len(ids) != len(tables)
            or set(ids) != set(tables)
            or len(ids) != len(set(ids))
        ):
            _fail("ordinary_trade_semantic_mapping_table_coverage_invalid")
        case_scope_base = {
            key: str(canonical_binding.get(key) or "")
            for key in (
                "document_id",
                "canonical_version_id",
                "canonical_root_sha256",
                "source_artifact_ref",
                "source_sha256",
            )
        }
        case_scope_base["user_scope_sha256"] = user_scope_sha256
        if not all(case_scope_base.values()):
            _fail("ordinary_trade_semantic_mapping_canonical_binding_invalid")
        model_decision = {
            "model_id": model_id,
            "provider_profile_id": provider_profile_id,
            "response_sha256": _sha256_json(value),
            "execution_metadata_sha256": _execution_metadata_sha256(execution_metadata),
        }
        authority = OrdinaryTradeQualifiedMappingAuthorityFactory.create()
        qualified_mappings: list[dict[str, Any]] = []
        qualification_receipts: list[dict[str, Any]] = []
        table_resolutions: list[dict[str, Any]] = []
        resolved_decisions = []
        for decision in decisions:
            table = tables[str(decision.get("table_node_id"))]
            assertion = _confirmed_user_currency_assertion(
                confirmed_understandings=confirmed_understandings,
                table_node_id=table["table_node_id"],
            )
            resolved = _validate_table_decision(
                decision=decision,
                table=table,
                user_currency_assertion=assertion,
                model_supplies_classification_evidence=(
                    value["schema_version"]
                    in _MODEL_SUPPLIED_CLASSIFICATION_EVIDENCE_SCHEMA_VERSIONS
                ),
                model_supplies_missing_required_roles=(
                    value["schema_version"]
                    in _MODEL_SUPPLIED_MISSING_REQUIRED_ROLES_SCHEMA_VERSIONS
                ),
                model_supplies_sparse_columns=(
                    value["schema_version"]
                    in _MODEL_SPARSE_COLUMNS_SCHEMA_VERSIONS
                ),
                preserve_model_classification_evidence=(
                    value["schema_version"]
                    in _MODEL_SELECTED_CLASSIFICATION_EVIDENCE_SCHEMA_VERSIONS
                    and (
                        value["schema_version"] != MAPPING_RESPONSE_SCHEMA_VERSION
                        or decision.get("no_consumer_kind")
                        == "INSTRUCTIONAL_REFERENCE"
                    )
                ),
            )
            resolved_decisions.append(resolved)
        _validate_confirmed_decisions(
            confirmed_understandings=confirmed_understandings,
            resolved_decisions=resolved_decisions,
        )
        confirmed_exclusion_resolutions = _confirmed_exclusion_resolutions(
            confirmed_understandings=confirmed_understandings,
            tables=tables,
        )
        if any(
            item["disposition"] == "UNSUPPORTED_FINANCIAL_MEANING"
            for item in resolved_decisions
        ):
            return {
                "status": "UNSUPPORTED",
                "message": value["message"].strip(),
                "question": None,
                "qualified_mappings": [],
                "qualification_receipts": [],
                "table_resolutions": [],
                "model_response_sha256": model_decision["response_sha256"],
                "execution_metadata_sha256": model_decision[
                    "execution_metadata_sha256"
                ],
            }
        resolutions_by_node_id = {
            item["table_node_id"]: {
                key: copy.deepcopy(item[key])
                for key in (
                    "table_node_id",
                    "header_row",
                    "structural_fingerprint",
                    "evidence_surface",
                    "disposition",
                    "security_trade_rows",
                )
            }
            for item in confirmed_exclusion_resolutions
        }
        for resolved in resolved_decisions:
            if resolved["disposition"] == "SECURITY_TRADES":
                case_scope = {
                    **case_scope_base,
                    "table_node_id": resolved["table_node_id"],
                }
                mapping, receipt = authority.qualify_case_mapping(
                    title_literal=None,
                    headers=resolved["headers"],
                    model_columns=resolved["columns"],
                    amount_currency_bindings=resolved["amount_currency_bindings"],
                    side_values=resolved["side_values"],
                    case_scope=case_scope,
                    model_decision=model_decision,
                    confirmed_understandings=[
                        {
                            key: item[key]
                            for key in (
                                "question_id",
                                "option_id",
                                "label_sha256",
                                "decision_sha256",
                            )
                        }
                        for item in confirmed_understandings
                    ],
                    user_currency_assertion=_confirmed_user_currency_assertion(
                        confirmed_understandings=confirmed_understandings,
                        table_node_id=resolved["table_node_id"],
                    ),
                )
                qualified_mappings.append(mapping)
                qualification_receipts.append(receipt)
            resolution = {
                key: copy.deepcopy(resolved[key])
                for key in (
                    "table_node_id",
                    "header_row",
                    "structural_fingerprint",
                    "evidence_surface",
                    "disposition",
                    "security_trade_rows",
                    "no_consumer_kind",
                    "classification_evidence",
                )
                if key in resolved
            }
            if resolved["disposition"] == "SECURITY_TRADES_INCOMPLETE":
                resolution.update(
                    {
                        "columns": copy.deepcopy(resolved["columns"]),
                        "side_values": copy.deepcopy(resolved["side_values"]),
                        "missing_required_roles": copy.deepcopy(
                            resolved["missing_required_roles"]
                        ),
                    }
                )
            resolutions_by_node_id[resolved["table_node_id"]] = resolution
        table_resolutions = [
            resolutions_by_node_id[table["table_node_id"]]
            for table in table_surfaces
            if table["table_node_id"] in resolutions_by_node_id
        ]
        # Keep the owner result exact, but pass only compiler-supported source-gap
        # dispositions into this local no-publication coverage check. The caller
        # retains the unmodified resolution for the downstream seam.
        compiler_table_resolutions = [
            item
            for item in table_resolutions
            if item["disposition"] != "SECURITY_TRADES_INCOMPLETE"
        ]
        dry_run = OrdinaryTradeSemanticCompilerFactory.create().compile(
            canonical=canonical,
            canonical_binding=canonical_binding,
            mappings=frozen_mappings,
            scoped_mappings=[
                {
                    "table_node_id": receipt["case_scope"]["table_node_id"],
                    "mapping": mapping,
                }
                for mapping, receipt in zip(
                    qualified_mappings,
                    qualification_receipts,
                    strict=True,
                )
            ],
            table_resolutions=compiler_table_resolutions,
        )
        incomplete_table_node_ids = {
            item["table_node_id"]
            for item in table_resolutions
            if item["disposition"]
            in {"SECURITY_TRADES_INCOMPLETE", "HEADER_ABSENT"}
        }
        if any(
            item.get("disposition") == "RELEVANT_UNMAPPED"
            and item.get("table_node_id") in tables
            and item.get("table_node_id") not in incomplete_table_node_ids
            for item in dry_run["source_observations"]
        ):
            _fail("ordinary_trade_semantic_mapping_dry_run_incomplete")
        return {
            "status": "COMPLETE",
            "message": value["message"].strip(),
            "question": None,
            "qualified_mappings": qualified_mappings,
            "qualification_receipts": qualification_receipts,
            "table_resolutions": table_resolutions,
            "model_response_sha256": model_decision["response_sha256"],
            "execution_metadata_sha256": model_decision["execution_metadata_sha256"],
        }

    def validate_answer_response(
        self,
        *,
        response: Any,
        question: dict[str, Any],
        user_message: str,
    ) -> dict[str, Any]:
        value = _strict_model_value(response)
        if (
            set(value)
            != {"schema_version", "status", "option_id", "message", "evidence_quote"}
            or value.get("schema_version") != ANSWER_RESPONSE_SCHEMA_VERSION
            or value.get("status") not in {"CANDIDATE", "CLARIFY", "SPECIALIST_REVIEW"}
            or not isinstance(value.get("message"), str)
            or not value["message"].strip()
            or not isinstance(value.get("evidence_quote"), str)
        ):
            _fail("ordinary_trade_mapping_answer_response_invalid")
        _validate_question(question, internal=True)
        option_ids = {item["option_id"] for item in question["options"]}
        option_id = value.get("option_id")
        if value["status"] == "CANDIDATE":
            if option_id not in option_ids or not value["evidence_quote"].strip():
                _fail("ordinary_trade_mapping_answer_candidate_invalid")
            if value["evidence_quote"] not in str(user_message):
                _fail("ordinary_trade_mapping_answer_quote_invalid")
        elif option_id is not None:
            _fail("ordinary_trade_mapping_answer_candidate_invalid")
        return copy.deepcopy(value)


def _managed_prompt(
    *, version: str, content: str, output_schema_id: str
) -> Gate2ManagedPrompt:
    return Gate2ManagedPrompt(
        prompt_ref=f"managed://broker-reports/{version}",
        command=None,
        version=version,
        content=content,
        hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
        source="package_immutable",
        template_id=version,
        template_kind="system",
        prompt_contract_id=version,
        input_schema_version=MAPPING_CASE_SCHEMA_VERSION,
        output_schema_id=output_schema_id,
        output_schema_version=output_schema_id,
        tags=("broker-reports", "ordinary-trade", "source-semantic"),
        safe_metadata={"runtime_active": True, "broker_specific": False},
    )


def _physical_continuation_links_for_scope(
    *,
    canonical: Mapping[str, Any],
    target_table_node_ids: Iterable[str],
    physical_table_continuation_context: Mapping[str, Any] | None,
) -> list[tuple[str, str]]:
    """Return exact source-bound links only when their full pair is in scope."""

    if physical_table_continuation_context is None:
        return []
    if (
        not isinstance(physical_table_continuation_context, Mapping)
        or physical_table_continuation_context.get("schema_version")
        != "broker_reports_physical_table_continuation_context_v1"
        or not isinstance(physical_table_continuation_context.get("links"), list)
    ):
        _fail("ordinary_trade_mapping_physical_continuation_context_invalid")
    target_ids = _ordered_target_table_node_ids(
        canonical=canonical, target_table_node_ids=target_table_node_ids
    )
    canonical_ids = _ordered_target_table_node_ids(
        canonical=canonical,
        target_table_node_ids=[
            node["node_id"]
            for node in canonical.get("nodes", [])
            if isinstance(node, Mapping) and node.get("node_type") == "TABLE"
        ],
    )
    known_ids = set(canonical_ids)
    selected_ids = set(target_ids)
    links: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for link in physical_table_continuation_context["links"]:
        if (
            not isinstance(link, Mapping)
            or set(link) != {"parent_table_node_id", "child_table_node_id"}
            or not isinstance(link.get("parent_table_node_id"), str)
            or not isinstance(link.get("child_table_node_id"), str)
        ):
            _fail("ordinary_trade_mapping_physical_continuation_context_invalid")
        pair = (link["parent_table_node_id"], link["child_table_node_id"])
        if pair[0] == pair[1] or not set(pair).issubset(known_ids) or pair in seen:
            _fail("ordinary_trade_mapping_physical_continuation_context_invalid")
        seen.add(pair)
        in_scope = [endpoint in selected_ids for endpoint in pair]
        if any(in_scope) and not all(in_scope):
            _fail("ordinary_trade_mapping_physical_continuation_scope_incomplete")
        if all(in_scope):
            links.append(pair)
    positions = {table_node_id: index for index, table_node_id in enumerate(canonical_ids)}
    return sorted(links, key=lambda pair: (positions[pair[0]], positions[pair[1]]))


def _physical_continuation_batch_groups(
    *,
    canonical: Mapping[str, Any],
    target_table_node_ids: Iterable[str],
    physical_table_continuation_context: Mapping[str, Any] | None,
) -> list[list[str]]:
    """Make each physical continuation component a contiguous batch unit."""

    target_ids = _ordered_target_table_node_ids(
        canonical=canonical, target_table_node_ids=target_table_node_ids
    )
    links = _physical_continuation_links_for_scope(
        canonical=canonical,
        target_table_node_ids=target_ids,
        physical_table_continuation_context=physical_table_continuation_context,
    )
    if not links:
        return [[table_node_id] for table_node_id in target_ids]
    positions = {table_node_id: index for index, table_node_id in enumerate(target_ids)}
    intervals = sorted(
        (min(positions[parent], positions[child]), max(positions[parent], positions[child]))
        for parent, child in links
    )
    merged: list[tuple[int, int]] = []
    for start, end in intervals:
        if merged and start <= merged[-1][1] + 1:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    groups: list[list[str]] = []
    cursor = 0
    for start, end in merged:
        while cursor < start:
            groups.append([target_ids[cursor]])
            cursor += 1
        groups.append(target_ids[start : end + 1])
        cursor = end + 1
    while cursor < len(target_ids):
        groups.append([target_ids[cursor]])
        cursor += 1
    return groups


def _ordered_target_table_node_ids(
    *, canonical: Mapping[str, Any], target_table_node_ids: Iterable[str]
) -> list[str]:
    requested = list(target_table_node_ids)
    if (
        not requested
        or len(requested) != len(set(requested))
        or any(not isinstance(item, str) or not item for item in requested)
    ):
        _fail("ordinary_trade_mapping_batch_plan_invalid")
    requested_ids = set(requested)
    canonical_order: list[str] = []
    seen: set[str] = set()
    nodes = canonical.get("nodes") if isinstance(canonical, Mapping) else None
    if not isinstance(nodes, list):
        _fail("ordinary_trade_semantic_mapping_canonical_invalid")
    for node in nodes:
        if not isinstance(node, Mapping):
            _fail("ordinary_trade_semantic_mapping_canonical_invalid")
        if node.get("node_type") != "TABLE":
            continue
        node_id = node.get("node_id")
        if not isinstance(node_id, str) or not node_id:
            _fail("ordinary_trade_semantic_mapping_canonical_invalid")
        if node_id in seen:
            _fail("ordinary_trade_semantic_mapping_canonical_invalid")
        seen.add(node_id)
        if node_id in requested_ids:
            canonical_order.append(node_id)
    if set(canonical_order) != requested_ids:
        _fail("ordinary_trade_semantic_mapping_target_scope_stale")
    if requested != canonical_order:
        _fail("ordinary_trade_semantic_mapping_target_order_invalid")
    return canonical_order


def _validate_mapping_batch_plan(
    *,
    plan: Mapping[str, Any],
    canonical: Mapping[str, Any],
    confirmed_understandings: list[dict[str, Any]],
    physical_table_continuation_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if (
        not isinstance(plan, Mapping)
        or set(plan) != {"schema_version", "target_table_node_ids", "batches"}
        or plan.get("schema_version") != MAPPING_BATCH_PLAN_SCHEMA_VERSION
        or not isinstance(plan.get("target_table_node_ids"), list)
        or not isinstance(plan.get("batches"), list)
    ):
        _fail("ordinary_trade_mapping_batch_plan_invalid")
    target_ids = _ordered_target_table_node_ids(
        canonical=canonical,
        target_table_node_ids=plan["target_table_node_ids"],
    )
    if target_ids != plan["target_table_node_ids"] or not plan["batches"]:
        _fail("ordinary_trade_mapping_batch_plan_coverage_invalid")
    seen: list[str] = []
    for index, batch in enumerate(plan["batches"], start=1):
        expected_batch_id = f"batch_{index:04d}"
        if (
            not isinstance(batch, Mapping)
            or set(batch)
            != {"batch_id", "target_table_node_ids", "mapping_package_sha256"}
            or batch.get("batch_id") != expected_batch_id
            or not isinstance(batch.get("target_table_node_ids"), list)
            or not isinstance(batch.get("mapping_package_sha256"), str)
        ):
            _fail("ordinary_trade_mapping_batch_plan_invalid")
        ids = batch["target_table_node_ids"]
        if not ids or any(item not in target_ids for item in ids):
            _fail("ordinary_trade_mapping_batch_plan_coverage_invalid")
        seen.extend(ids)
    if seen != target_ids or len(seen) != len(set(seen)):
        _fail("ordinary_trade_mapping_batch_plan_coverage_invalid")
    semantic = OrdinaryTradeSemanticMappingFactory.create()
    for batch in plan["batches"]:
        package = semantic.build_mapping_package(
            canonical=canonical,
            confirmed_understandings=confirmed_understandings,
            target_table_node_ids=batch["target_table_node_ids"],
            physical_table_continuation_context=physical_table_continuation_context,
        )
        if batch["mapping_package_sha256"] != _sha256_json(package):
            _fail("ordinary_trade_mapping_batch_plan_integrity_invalid")
    return {
        "schema_version": MAPPING_BATCH_PLAN_SCHEMA_VERSION,
        "target_table_node_ids": list(target_ids),
        "batches": [copy.deepcopy(dict(item)) for item in plan["batches"]],
    }


def _table_surfaces(
    canonical: Mapping[str, Any],
    *,
    target_table_node_ids: Iterable[str] | None = None,
) -> list[dict[str, Any]]:
    nodes = canonical.get("nodes") if isinstance(canonical, Mapping) else None
    if not isinstance(nodes, list):
        _fail("ordinary_trade_semantic_mapping_canonical_invalid")
    preceding_sibling_by_container = _preceding_sibling_containers(canonical)
    target_ids = None
    if target_table_node_ids is not None:
        target_ids = list(target_table_node_ids)
        if (
            not target_ids
            or len(target_ids) != len(set(target_ids))
            or any(not isinstance(item, str) or not item for item in target_ids)
        ):
            _fail("ordinary_trade_semantic_mapping_target_scope_invalid")
        target_ids = set(target_ids)
    literal_nodes_by_container = _literal_nodes_by_container(
        nodes=nodes,
        container_refs=set(preceding_sibling_by_container),
    )
    tables = []
    cells_total = 0
    ordered_nodes = sorted(
        nodes,
        key=lambda node: (node["container_ref"], node["order"]),
    )
    for node in ordered_nodes:
        if node.get("node_type") != "TABLE":
            continue
        container_ref = node["container_ref"]
        node_id = node.get("node_id")
        content = node.get("content")
        cells = (content or {}).get("cells")
        if (
            not isinstance(node_id, str)
            or not node_id
            or not isinstance(content, Mapping)
            or not isinstance(cells, list)
        ):
            _fail("ordinary_trade_semantic_mapping_canonical_invalid")
        if target_ids is not None and node_id not in target_ids:
            continue
        by_row: dict[int, list[dict[str, Any]]] = {}
        for cell in cells:
            if not isinstance(cell, dict):
                _fail("ordinary_trade_semantic_mapping_canonical_invalid")
            row = cell.get("row")
            column = cell.get("column")
            try:
                literal = canonical_cell_literal(cell)
            except OrdinaryTradeSemanticCompilerError:
                _fail("ordinary_trade_semantic_mapping_canonical_invalid")
            if (
                not isinstance(row, int)
                or row < 1
                or not isinstance(column, int)
                or column < 1
            ):
                _fail("ordinary_trade_semantic_mapping_canonical_invalid")
            by_row.setdefault(row, []).append({"column": column, "literal": literal})
            cells_total += 1
        if len(by_row) > _MAX_ROWS_PER_TABLE:
            _fail("ordinary_trade_semantic_mapping_context_limit")
        rows = [
            {"row": row, "cells": sorted(items, key=lambda item: item["column"])}
            for row, items in sorted(by_row.items())
        ]
        header = content.get("header")
        metadata = content.get("metadata")
        physical_header_state = (
            metadata.get("physical_header_state")
            if isinstance(metadata, Mapping)
            else None
        )
        if isinstance(metadata, Mapping) and (
            "physical_header_state" in metadata
            and physical_header_state not in {"PRESENT", "ABSENT"}
        ):
            _fail("ordinary_trade_semantic_mapping_canonical_invalid")
        if physical_header_state in {"PRESENT", "ABSENT"}:
            if not isinstance(header, list):
                _fail("ordinary_trade_semantic_mapping_canonical_invalid")
            if (physical_header_state == "PRESENT") != bool(header):
                _fail("ordinary_trade_semantic_mapping_canonical_invalid")
            physical_header_row = 1 if physical_header_state == "PRESENT" else None
        else:
            # Compatibility for immutable Canonical fixtures written before the
            # source owner emitted an explicit physical-header surface.
            physical_header_row = rows[0]["row"] if rows else None
        tables.append(
            {
                "table_node_id": node_id,
                "rows": rows,
                "physical_header_row": physical_header_row,
                **_source_context_for_table(
                    table_node_id=node_id,
                    title_value=(node.get("content") or {}).get("title"),
                    table_order=node["order"],
                    container_ref=container_ref,
                    preceding_sibling_ref=preceding_sibling_by_container[container_ref],
                    literal_nodes_by_container=literal_nodes_by_container,
                ),
            }
        )
    if not tables or len(tables) > _MAX_TABLES or cells_total > _MAX_CELLS_TOTAL:
        _fail("ordinary_trade_semantic_mapping_context_limit")
    if target_ids is not None and {item["table_node_id"] for item in tables} != target_ids:
        _fail("ordinary_trade_semantic_mapping_target_scope_stale")
    return tables


def _preceding_sibling_containers(canonical: Mapping[str, Any]) -> dict[str, str | None]:
    """Return the one document-adjacent container, or reject ambiguous topology."""

    containers = canonical.get("containers") if isinstance(canonical, Mapping) else None
    if containers is None:
        # Older neutral Canonical fixtures have no container tree.  They retain
        # the established same-container-only projection and cannot gain a
        # sibling context by inference.
        nodes = canonical.get("nodes") if isinstance(canonical, Mapping) else None
        if not isinstance(nodes, list):
            _fail("ordinary_trade_semantic_mapping_canonical_invalid")
        refs = set()
        for node in nodes:
            container_ref = node.get("container_ref") if isinstance(node, dict) else None
            if not isinstance(container_ref, str) or not container_ref:
                _fail("ordinary_trade_semantic_mapping_canonical_invalid")
            refs.add(container_ref)
        return {container_ref: None for container_ref in refs}
    if not isinstance(containers, list) or not containers:
        _fail("ordinary_trade_semantic_mapping_canonical_invalid")
    by_id: dict[str, dict[str, Any]] = {}
    children_by_parent: dict[str | None, list[dict[str, Any]]] = {}
    for container in containers:
        if not isinstance(container, dict):
            _fail("ordinary_trade_semantic_mapping_canonical_invalid")
        container_id = container.get("container_id")
        parent = container.get("parent_container_ref")
        order = container.get("order")
        if (
            not isinstance(container_id, str)
            or not container_id
            or container_id in by_id
            or (parent is not None and (not isinstance(parent, str) or not parent))
            or isinstance(order, bool)
            or not isinstance(order, int)
            or order < 0
        ):
            _fail("ordinary_trade_semantic_mapping_canonical_invalid")
        by_id[container_id] = container
        children_by_parent.setdefault(parent, []).append(container)
    if any(
        parent is not None and parent not in by_id
        for parent in children_by_parent
    ):
        _fail("ordinary_trade_semantic_mapping_canonical_invalid")
    root_ref = canonical.get("root_container_ref")
    roots = [
        container_id
        for container_id, container in by_id.items()
        if container["parent_container_ref"] is None
    ]
    if (
        not isinstance(root_ref, str)
        or root_ref not in by_id
        or roots != [root_ref]
    ):
        _fail("ordinary_trade_semantic_mapping_canonical_invalid")
    for container_id, container in by_id.items():
        seen: set[str] = {container_id}
        parent = container["parent_container_ref"]
        while parent is not None:
            if parent in seen:
                _fail("ordinary_trade_semantic_mapping_canonical_invalid")
            seen.add(parent)
            parent = by_id[parent]["parent_container_ref"]

    preceding: dict[str, str | None] = {}
    for siblings in children_by_parent.values():
        ordered = sorted(siblings, key=lambda item: item["order"])
        if [item["order"] for item in ordered] != list(range(len(ordered))):
            _fail("ordinary_trade_semantic_mapping_canonical_invalid")
        for index, container in enumerate(ordered):
            preceding[container["container_id"]] = (
                ordered[index - 1]["container_id"] if index else None
            )
    return preceding


def _literal_nodes_by_container(
    *, nodes: list[Any], container_refs: set[str]
) -> dict[str, list[tuple[int, str, str]]]:
    """Keep literal text nodes, ordered inside their authoritative container."""

    by_container: dict[str, list[tuple[int, str, str]]] = {}
    for node in nodes:
        if not isinstance(node, dict):
            _fail("ordinary_trade_semantic_mapping_canonical_invalid")
        container_ref = node.get("container_ref")
        node_id = node.get("node_id")
        order = node.get("order")
        if (
            not isinstance(container_ref, str)
            or container_ref not in container_refs
            or not isinstance(node_id, str)
            or not node_id
            or isinstance(order, bool)
            or not isinstance(order, int)
            or order < 0
        ):
            _fail("ordinary_trade_semantic_mapping_canonical_invalid")
        if node.get("node_type") not in {"HEADING", "TEXT", "NOTE"}:
            continue
        content = node.get("content")
        if not isinstance(content, Mapping):
            _fail("ordinary_trade_semantic_mapping_canonical_invalid")
        literal = content.get("text")
        if not isinstance(literal, str):
            _fail("ordinary_trade_semantic_mapping_canonical_invalid")
        if literal:
            by_container.setdefault(container_ref, []).append((order, node_id, literal))
    for literals in by_container.values():
        literals.sort(key=lambda item: item[0])
    return by_container


def _source_context_for_table(
    *,
    table_node_id: str,
    title_value: Any,
    table_order: int,
    container_ref: str,
    preceding_sibling_ref: str | None,
    literal_nodes_by_container: Mapping[str, list[tuple[int, str, str]]],
) -> dict[str, Any]:
    """Project bounded literal context with private Canonical provenance.

    The model receives only opaque references, structural relations and literals.
    Canonical node identity and literal digest remain private for response binding.
    """

    sibling = list(literal_nodes_by_container.get(preceding_sibling_ref or "", []))
    local = [
        item
        for item in literal_nodes_by_container.get(container_ref, [])
        if item[0] < table_order
    ]
    sibling_context = [
        ("PRECEDING_SIBLING_CONTAINER", node_id, literal)
        for _order, node_id, literal in sibling
    ]
    local_context = [
        ("PRECEDING_SAME_CONTAINER", node_id, literal)
        for _order, node_id, literal in local
    ]
    bounded = [*sibling_context, *local_context]
    # The two immediately adjacent Canonical relations are distinct structural
    # evidence.  Reserve a bounded tail for each; this selects no meaning and
    # keeps the established eight-literal model budget.
    selected = [
        *sibling_context[-_MAX_LOCAL_CONTEXT_ITEMS_PER_RELATION:],
        *local_context[-_MAX_LOCAL_CONTEXT_ITEMS_PER_RELATION:],
    ]
    omitted = [
        *sibling_context[:-_MAX_LOCAL_CONTEXT_ITEMS_PER_RELATION],
        *local_context[:-_MAX_LOCAL_CONTEXT_ITEMS_PER_RELATION],
    ]
    title_source_literal = title_value if isinstance(title_value, str) else ""
    candidates = (
        [("TABLE_TITLE", table_node_id, title_source_literal)]
        if title_source_literal
        else []
    ) + selected
    entries = []
    private_entries = []
    for index, (relation, node_id, literal) in enumerate(candidates, start=1):
        context_ref = f"context_{index}"
        projected_literal = _source_context_literal(literal)
        entries.append(
            {
                "context_ref": context_ref,
                "relation": relation,
                "literal": projected_literal,
            }
        )
        private_entries.append(
            {
                "context_ref": context_ref,
                "relation": relation,
                "canonical_node_id": node_id,
                # Keep the established projected digest for response binding.
                "literal_sha256": _sha256_text(projected_literal),
                # These receipt-only fields make local-window loss auditable;
                # neither raw Canonical text nor this private evidence reaches
                # the model package.
                "canonical_literal_sha256": _sha256_text(literal),
                "canonical_literal_chars": len(literal),
                "projected_literal_sha256": _sha256_text(projected_literal),
                "projected_literal_chars": len(projected_literal),
                "literal_truncated": len(literal) != len(projected_literal),
            }
        )
    return {
        "source_context": {"entries": entries},
        "source_context_evidence": private_entries,
        "source_context_audit": {
            "eligible_context_entries_total": len(candidates) + len(bounded) - len(selected),
            "omitted_context_entries_total": len(bounded) - len(selected),
            "truncated_context_entries_total": sum(
                len(literal) != len(_source_context_literal(literal))
                for _relation, _node_id, literal in candidates
            ),
            "eligible_preceding_sibling_container_total": sum(
                relation == "PRECEDING_SIBLING_CONTAINER"
                for relation, _node_id, _literal in bounded
            ),
            "eligible_preceding_same_container_total": sum(
                relation == "PRECEDING_SAME_CONTAINER"
                for relation, _node_id, _literal in bounded
            ),
            "omitted_preceding_sibling_container_total": sum(
                relation == "PRECEDING_SIBLING_CONTAINER"
                for relation, _node_id, _literal in omitted
            ),
            "omitted_preceding_same_container_total": sum(
                relation == "PRECEDING_SAME_CONTAINER"
                for relation, _node_id, _literal in omitted
            ),
        },
    }


def _source_context_literal(value: Any) -> str:
    """Project a bounded literal only; it assigns no meaning to source text."""

    if not isinstance(value, str):
        return ""
    return value[:_MAX_LOCAL_CONTEXT_LITERAL_CHARS]


def _model_table_surfaces(
    canonical: Mapping[str, Any],
    *,
    target_table_node_ids: Iterable[str] | None = None,
    include_column_distinct_values: bool = True,
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Expose one complete, bounded Canonical table scope to the mapper.

    The mapper's response contract binds a disposition to every non-empty
    Canonical row.  Giving it a sample here would make that contract impossible
    for a longer table.  The existing per-table and package context limits own
    the transport bound; classification has its own, deliberately smaller
    descriptor and is not affected by this mapping representation.
    """

    tables = _selected_table_surfaces(
        canonical=canonical,
        target_table_node_ids=target_table_node_ids,
    )
    refs_by_node_id = {
        table["table_node_id"]: f"table_{index}"
        for index, table in enumerate(tables, start=1)
    }
    model_tables = []
    for table in tables:
        rows = table["rows"]
        model_table = {
            "table_ref": refs_by_node_id[table["table_node_id"]],
            "rows_total": len(rows),
            "physical_header_row": table["physical_header_row"],
            # This is a structural selector, not a financial interpretation.
            # It prevents the model from referring to a visual row number that
            # does not exist in the Canonical table contract.
            "header_row_choices": (
                [table["physical_header_row"]]
                if table["physical_header_row"] is not None
                else []
            ),
            "rows": copy.deepcopy(rows),
            "rows_truncated": False,
            "source_context": copy.deepcopy(table["source_context"]),
        }
        if include_column_distinct_values:
            distinct_by_column: dict[int, list[str]] = {}
            for row in rows:
                for cell in row["cells"]:
                    values = distinct_by_column.setdefault(cell["column"], [])
                    if cell["literal"] and cell["literal"] not in values:
                        values.append(cell["literal"])
            model_table["column_distinct_values"] = [
                    {
                        "column": column,
                        "values": copy.deepcopy(
                            values[:_MAX_DISTINCT_VALUES_PER_COLUMN]
                        ),
                        "values_truncated": (
                            len(values) > _MAX_DISTINCT_VALUES_PER_COLUMN
                        ),
                    }
                    for column, values in sorted(distinct_by_column.items())
                ]
        model_tables.append(model_table)
    return model_tables, refs_by_node_id


def _selected_table_surfaces(
    *,
    canonical: Mapping[str, Any],
    target_table_node_ids: Iterable[str] | None,
) -> list[dict[str, Any]]:
    if target_table_node_ids is None:
        return _table_surfaces(canonical)
    target_ids = list(target_table_node_ids)
    tables = _table_surfaces(
        canonical,
        target_table_node_ids=target_ids,
    )
    by_id = {item["table_node_id"]: item for item in tables}
    return [by_id[item] for item in target_ids]


def _normalize_model_decisions(
    decisions: Any, *, node_ids_by_ref: dict[str, str]
) -> list[dict[str, Any]]:
    if not isinstance(decisions, list):
        _fail("ordinary_trade_semantic_mapping_table_coverage_invalid")
    normalized = []
    for item in decisions:
        if not isinstance(item, dict) or "table_ref" not in item:
            _fail("ordinary_trade_semantic_mapping_table_coverage_invalid")
        node_id = node_ids_by_ref.get(str(item.get("table_ref")))
        if node_id is None:
            _fail("ordinary_trade_semantic_mapping_table_coverage_invalid")
        translated = copy.deepcopy(item)
        translated["table_node_id"] = node_id
        translated.pop("table_ref")
        normalized.append(translated)
    return normalized


def _normalize_model_question(
    question: Any,
    *,
    tables: dict[str, dict[str, Any]],
    node_ids_by_ref: dict[str, str],
) -> dict[str, Any]:
    _validate_question(question, table_refs=set(node_ids_by_ref))
    normalized = copy.deepcopy(question)
    node_id = node_ids_by_ref[normalized.pop("table_ref")]
    normalized["table_node_id"] = node_id
    normalized["question_id"] = "q_choice_prompt"
    normalized["question"] = "Какое из следующих проверяемых решений верно?"
    for index, option in enumerate(normalized["options"], start=1):
        option["option_id"] = f"o_choice_{index}"
        decision = option["decision"]
        if decision["table_ref"] != question["table_ref"]:
            _fail("ordinary_trade_semantic_mapping_question_decision_invalid")
        decision["table_node_id"] = node_ids_by_ref[decision.pop("table_ref")]
        _validate_clarification_decision(
            decision=decision,
            table=tables[decision["table_node_id"]],
        )
        option["label"] = _render_decision_label(
            decision=decision,
            table=tables[decision["table_node_id"]],
        )
        option["source_literals"] = _decision_source_literals(
            decision=decision,
            table=tables[decision["table_node_id"]],
        )
    digests = [_sha256_json(item["decision"]) for item in normalized["options"]]
    if len(digests) != len(set(digests)):
        _fail("ordinary_trade_semantic_mapping_question_decision_invalid")
    _validate_question(normalized, internal=True)
    return normalized


def _build_no_named_consumer_batch_question(
    *,
    decisions: list[dict[str, Any]],
    tables: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Group only already-validated exclusions for one explicit user decision."""

    batch = decisions[:_MAX_EXCLUSION_CONFIRMATION_TABLES]
    if not batch or any(
        item.get("disposition") != "NO_NAMED_CONSUMER" for item in batch
    ):
        _fail("ordinary_trade_semantic_mapping_exclusion_batch_invalid")
    confirmation_decisions = []
    source_literals = []
    for resolved in batch:
        table = tables.get(str(resolved.get("table_node_id")))
        if table is None:
            _fail("ordinary_trade_semantic_mapping_exclusion_batch_invalid")
        decision = {
            "decision_kind": "TABLE_DISPOSITION",
            "table_node_id": resolved["table_node_id"],
            "header_row": resolved["header_row"],
            "column": None,
            "semantic_role": None,
            "amount_column": None,
            "currency_column": None,
            "source_literal": None,
            "normalized_value": None,
            "disposition": "NO_NAMED_CONSUMER",
        }
        _validate_clarification_decision(decision=decision, table=table)
        confirmation_decisions.append(decision)
        headers = next(
            item for item in table["rows"] if item["row"] == resolved["header_row"]
        )["cells"]
        literal = " | ".join(str(item["literal"]).strip() for item in headers)
        if (
            literal
            and literal not in source_literals
            and len(source_literals) < 4
        ):
            source_literals.append(literal[:500])
    total = len(confirmation_decisions)
    question = {
        "question_id": "q_exclusion_batch",
        "table_node_ids": [item["table_node_id"] for item in confirmation_decisions],
        "question": (
            "Подтвердите исключение группы таблиц, не относящихся к поддерживаемым операциям. "
            f"Количество таблиц в группе: {total}. "
            "Вариант 1 применяется только к перечисленным источникам; вариант 2 остановит обработку для проверки специалистом."
        ),
        "options": [
            {
                "option_id": "o_confirm_exclusion_batch",
                "label": "Подтверждаю: указанная группа не относится к поддерживаемым операциям",
                "effect": "APPLY_DECISIONS",
                "decisions": confirmation_decisions,
                "source_literals": source_literals,
            },
            {
                "option_id": "o_review_exclusion_batch",
                "label": "Не подтверждаю: нужна проверка специалистом",
                "effect": "SPECIALIST_REVIEW",
                "decisions": [],
                "source_literals": [],
            },
        ],
    }
    _validate_question(question, internal=True)
    return question


_ROLE_LABELS = {
    "asset_name": "ценная бумага",
    "trade_date": "дата сделки",
    "side": "направление сделки",
    "quantity": "количество",
    "unit_price": "цена одной бумаги",
    "currency": "валюта",
    "gross_amount": "общая сумма сделки",
    "broker_commission": "комиссия брокера",
    "exchange_commission": "комиссия биржи",
    "settlement_date": "дата расчётов",
    "trade_time": "время сделки",
    "security_code": "код ценной бумаги",
    "accrued_interest": "накопленный купонный доход",
    "trade_id": "идентификатор сделки",
    "venue": "место заключения сделки",
    "comment": "комментарий к сделке",
    "status": "состояние сделки",
    "description": "описание сделки",
    "unmapped": "неиспользуемая колонка",
}
_DISPOSITION_LABELS = {
    "SECURITY_TRADES": "таблица содержит сделки с ценными бумагами",
    "NO_NAMED_CONSUMER": "таблица не относится к поддерживаемым операциям",
    "UNSUPPORTED_FINANCIAL_MEANING": (
        "таблица содержит неподдерживаемый финансовый смысл"
    ),
}


def _render_decision_label(*, decision: dict[str, Any], table: dict[str, Any]) -> str:
    """Render the exact validated machine decision without model-authored wording."""

    header = next(
        item for item in table["rows"] if item["row"] == decision["header_row"]
    )
    headers = {item["column"]: item["literal"] for item in header["cells"]}
    kind = decision["decision_kind"]
    if kind == "COLUMN_ROLE":
        role = decision["semantic_role"]
        role_label = _ROLE_LABELS.get(role, str(role))
        return (
            f"Колонка {decision['column']} «{headers[decision['column']]}» — "
            f"{role_label}"
        )
    if kind == "AMOUNT_CURRENCY_BINDING":
        amount = decision["amount_column"]
        currency = decision["currency_column"]
        return (
            f"Сумма в колонке {amount} «{headers[amount]}» выражена в валюте "
            f"из колонки {currency} «{headers[currency]}»"
        )
    if kind == "SIDE_VALUE":
        normalized = (
            "покупка" if decision["normalized_value"] == "PURCHASE" else "продажа"
        )
        return f"Значение «{decision['source_literal']}» означает: {normalized}"
    disposition = decision["disposition"]
    return _DISPOSITION_LABELS[disposition]


def mapping_decision_communication_description(decision: dict[str, Any]) -> str:
    """Describe one validated decision without copying source-controlled text."""

    kind = decision["decision_kind"]
    if kind == "COLUMN_ROLE":
        return (
            f"колонка {decision['column']} — {_ROLE_LABELS[decision['semantic_role']]}"
        )
    if kind == "AMOUNT_CURRENCY_BINDING":
        return (
            f"сумма в колонке {decision['amount_column']} связана с валютой "
            f"из колонки {decision['currency_column']}"
        )
    if kind == "SIDE_VALUE":
        normalized = (
            "покупка" if decision["normalized_value"] == "PURCHASE" else "продажа"
        )
        return f"процитированное значение означает «{normalized}»"
    return _DISPOSITION_LABELS[decision["disposition"]]


def mapping_question_option_communication_description(option: dict[str, Any]) -> str:
    """Render only code-owned meaning for one persisted mapping option."""

    decision = option.get("decision")
    if isinstance(decision, dict):
        return mapping_decision_communication_description(decision)
    if option.get("effect") == "APPLY_DECISIONS":
        decisions = option.get("decisions")
        if not isinstance(decisions, list) or not decisions:
            _fail("ordinary_trade_semantic_mapping_question_invalid")
        return "подтверждение исключения указанной группы вне поддерживаемых операций"
    if option.get("effect") == "SPECIALIST_REVIEW":
        return "остановка обработки и передача на проверку специалисту"
    _fail("ordinary_trade_semantic_mapping_question_invalid")


def _decision_source_literals(
    *, decision: dict[str, Any], table: dict[str, Any]
) -> list[str]:
    """Keep source wording explicit and separate from code-owned decision text."""

    header = next(
        item for item in table["rows"] if item["row"] == decision["header_row"]
    )
    headers = {item["column"]: item["literal"] for item in header["cells"]}
    kind = decision["decision_kind"]
    if kind == "COLUMN_ROLE":
        return [headers[decision["column"]]]
    if kind == "AMOUNT_CURRENCY_BINDING":
        return [
            headers[decision["amount_column"]],
            headers[decision["currency_column"]],
        ]
    if kind == "SIDE_VALUE":
        return [decision["source_literal"]]
    return []


def _validated_classification_evidence(
    *,
    evidence: Any,
    table: dict[str, Any],
    allow_legacy_singleton: bool,
) -> list[dict[str, str]]:
    """Bind an exclusion to an ordered subset of its Canonical context.

    V7 admits a nonempty list in the exact order that the bounded source-context
    owner exposed. A V6 singleton is read only for immutable replay; it is
    normalized to the same resolved list and cannot be emitted by the V7 schema.
    """

    if allow_legacy_singleton and isinstance(evidence, dict):
        entries = [evidence]
    elif isinstance(evidence, list):
        entries = evidence
    else:
        _fail("ordinary_trade_semantic_mapping_classification_evidence_invalid")
    source_entries = table.get("source_context_evidence")
    if (
        not isinstance(source_entries, list)
        or not entries
        or len(entries) > len(source_entries)
    ):
        _fail("ordinary_trade_semantic_mapping_classification_evidence_invalid")
    resolved: list[dict[str, str]] = []
    previous_index = -1
    for evidence_entry in entries:
        if (
            not isinstance(evidence_entry, dict)
            or set(evidence_entry) != {"context_ref", "relation"}
            or not all(
                isinstance(evidence_entry.get(key), str) and evidence_entry[key]
                for key in evidence_entry
            )
        ):
            _fail("ordinary_trade_semantic_mapping_classification_evidence_invalid")
        matches = [
            (index, item)
            for index, item in enumerate(source_entries)
            if isinstance(item, dict)
            and item.get("context_ref") == evidence_entry["context_ref"]
            and item.get("relation") == evidence_entry["relation"]
        ]
        if len(matches) != 1:
            _fail("ordinary_trade_semantic_mapping_classification_evidence_invalid")
        index, match = matches[0]
        if index <= previous_index or (
            not isinstance(match.get("canonical_node_id"), str)
            or not match["canonical_node_id"]
            or not isinstance(match.get("literal_sha256"), str)
            or re.fullmatch(r"[0-9a-f]{64}", match["literal_sha256"]) is None
        ):
            _fail("ordinary_trade_semantic_mapping_classification_evidence_invalid")
        previous_index = index
        resolved.append(
            {
                key: str(match[key])
                for key in (
                    "context_ref",
                    "relation",
                    "canonical_node_id",
                    "literal_sha256",
                )
            }
        )
    return resolved


def _classification_evidence_envelope(*, table: dict[str, Any]) -> list[dict[str, str]]:
    """Return the complete bounded Canonical context owned by this mapping run.

    The model classifies a table's purpose.  It neither selects nor authors the
    provenance for that conclusion: the mapping owner binds every already
    exposed source-context entry, in the source owner's established order.
    """

    source_entries = table.get("source_context_evidence")
    if not isinstance(source_entries, list) or not source_entries:
        _fail("ordinary_trade_semantic_mapping_classification_evidence_invalid")
    envelope: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for entry in source_entries:
        if (
            not isinstance(entry, dict)
            or any(
                not isinstance(entry.get(key), str) or not entry[key]
                for key in (
                    "context_ref",
                    "relation",
                    "canonical_node_id",
                    "literal_sha256",
                )
            )
            or re.fullmatch(r"[0-9a-f]{64}", entry["literal_sha256"]) is None
        ):
            _fail("ordinary_trade_semantic_mapping_classification_evidence_invalid")
        identity = (entry["context_ref"], entry["relation"])
        if identity in seen:
            _fail("ordinary_trade_semantic_mapping_classification_evidence_invalid")
        seen.add(identity)
        envelope.append(
            {
                key: str(entry[key])
                for key in (
                    "context_ref",
                    "relation",
                    "canonical_node_id",
                    "literal_sha256",
                )
            }
        )
    return envelope


def _validate_table_decision(
    *,
    decision: Any,
    table: dict[str, Any],
    user_currency_assertion: dict[str, Any] | None = None,
    allow_user_currency: bool = False,
    allow_legacy_no_consumer: bool = False,
    model_supplies_classification_evidence: bool = False,
    model_supplies_missing_required_roles: bool = False,
    model_supplies_sparse_columns: bool = False,
    preserve_model_classification_evidence: bool = False,
) -> dict[str, Any]:
    base_fields = {
        "table_node_id",
        "header_row",
        "disposition",
        "columns",
        "amount_currency_bindings",
        "side_values",
        "row_dispositions",
    }
    incomplete_fields = (
        base_fields | {"missing_required_roles"}
        if model_supplies_missing_required_roles
        else base_fields
    )
    no_consumer_fields = base_fields | {
        "no_consumer_kind",
    }
    legacy_no_consumer_fields = no_consumer_fields | {
        "classification_evidence",
    }
    if not isinstance(decision, dict):
        _fail(
            "ordinary_trade_semantic_mapping_table_decision_invalid",
            diagnostic_code="ordinary_trade_mapping_decision_not_object",
        )
    if set(decision) not in {
        frozenset(base_fields),
        frozenset(incomplete_fields),
        frozenset(no_consumer_fields),
        frozenset(legacy_no_consumer_fields),
    }:
        _fail(
            "ordinary_trade_semantic_mapping_table_decision_invalid",
            diagnostic_code="ordinary_trade_mapping_decision_fields_invalid",
        )
    if decision.get("table_node_id") != table["table_node_id"]:
        _fail(
            "ordinary_trade_semantic_mapping_table_decision_invalid",
            diagnostic_code="ordinary_trade_mapping_decision_table_binding_invalid",
        )
    if not (
        isinstance(decision.get("header_row"), int)
        or decision.get("header_row") is None
    ):
        _fail(
            "ordinary_trade_semantic_mapping_table_decision_invalid",
            diagnostic_code="ordinary_trade_mapping_decision_header_type_invalid",
        )
    if decision.get("disposition") not in _TABLE_DISPOSITIONS:
        _fail(
            "ordinary_trade_semantic_mapping_table_decision_invalid",
            diagnostic_code="ordinary_trade_mapping_decision_disposition_invalid",
        )
    if not all(
        isinstance(decision.get(key), list)
        for key in (
            "columns",
            "amount_currency_bindings",
            "side_values",
            "row_dispositions",
        )
    ):
        _fail(
            "ordinary_trade_semantic_mapping_table_decision_invalid",
            diagnostic_code="ordinary_trade_mapping_decision_collection_invalid",
        )
    disposition = decision["disposition"]
    if disposition == "HEADER_ABSENT":
        if (
            decision.get("header_row") is not None
            or table.get("physical_header_row") is not None
            or any(
                decision[key]
                for key in (
                    "columns",
                    "amount_currency_bindings",
                    "side_values",
                    "row_dispositions",
                )
            )
        ):
            _fail("ordinary_trade_semantic_mapping_header_absent_invalid")
        headers: list[dict[str, Any]] = []
        return {
            "table_node_id": table["table_node_id"],
            "header_row": None,
            "structural_fingerprint": structural_fingerprint(
                title_literal=None, columns=[]
            ),
            "evidence_surface": {"title_literal": None, "headers": headers},
            "disposition": disposition,
            "headers": headers,
            "columns": [],
            "amount_currency_bindings": [],
            "side_values": [],
            "security_trade_rows": [],
        }
    if (
        not isinstance(decision.get("header_row"), int)
        or decision["header_row"] != table.get("physical_header_row")
    ):
        _fail("ordinary_trade_semantic_mapping_header_invalid")
    incomplete = disposition == "SECURITY_TRADES_INCOMPLETE"
    if (
        model_supplies_missing_required_roles
        and (
            (incomplete and set(decision) != incomplete_fields)
            or (not incomplete and set(decision) == incomplete_fields)
        )
    ):
        _fail(
            "ordinary_trade_semantic_mapping_table_decision_invalid",
            diagnostic_code="ordinary_trade_mapping_decision_incomplete_fields_invalid",
        )
    no_consumer = disposition == "NO_NAMED_CONSUMER"
    requires_model_classification_evidence = (
        model_supplies_classification_evidence
        and (
            decision.get("no_consumer_kind") == "INSTRUCTIONAL_REFERENCE"
            or preserve_model_classification_evidence
        )
    )
    expected_no_consumer_fields = (
        legacy_no_consumer_fields
        if requires_model_classification_evidence
        else no_consumer_fields
    )
    if no_consumer and set(decision) != expected_no_consumer_fields and not (
        allow_legacy_no_consumer and set(decision) == base_fields
    ):
        _fail(
            "ordinary_trade_semantic_mapping_table_decision_invalid",
            diagnostic_code="ordinary_trade_mapping_decision_no_consumer_fields_invalid",
        )
    if (
        no_consumer
        and "no_consumer_kind" in decision
        and decision["no_consumer_kind"] not in _NO_CONSUMER_KINDS
    ):
        _fail(
            "ordinary_trade_semantic_mapping_table_decision_invalid",
            diagnostic_code="ordinary_trade_mapping_decision_no_consumer_kind_invalid",
        )
    classification_evidence = None
    if no_consumer and requires_model_classification_evidence:
        # V6/V7 are immutable model replays.  Keep their old wire contracts
        # readable, including their model-selected subset, but never promote
        # that selection as provenance for a new resolved outcome.
        model_evidence = _validated_classification_evidence(
            evidence=decision["classification_evidence"],
            table=table,
            allow_legacy_singleton=True,
        )
        if preserve_model_classification_evidence:
            classification_evidence = model_evidence
    if (
        no_consumer
        and not allow_legacy_no_consumer
        and not preserve_model_classification_evidence
    ):
        classification_evidence = _classification_evidence_envelope(table=table)
    row = next(
        (item for item in table["rows"] if item["row"] == decision["header_row"]),
        None,
    )
    if row is None or not row["cells"]:
        _fail("ordinary_trade_semantic_mapping_header_invalid")
    headers = [
        {"column": item["column"], "literal": item["literal"]} for item in row["cells"]
    ]
    fingerprint = structural_fingerprint(
        title_literal=None,
        columns=[
            {"column": item["column"], "header_literal": item["literal"]}
            for item in headers
        ],
    )
    if disposition not in {"SECURITY_TRADES", "SECURITY_TRADES_INCOMPLETE"}:
        if any(
            decision[key]
            for key in (
                "columns",
                "amount_currency_bindings",
                "side_values",
                "row_dispositions",
            )
        ):
            _fail("ordinary_trade_semantic_mapping_non_trade_material_invalid")
        resolved = {
            "table_node_id": table["table_node_id"],
            "header_row": decision["header_row"],
            "structural_fingerprint": fingerprint,
            "evidence_surface": {"title_literal": None, "headers": headers},
            "disposition": disposition,
            "headers": headers,
            "columns": [],
            "amount_currency_bindings": [],
            "side_values": [],
            "security_trade_rows": [],
        }
        if no_consumer and "no_consumer_kind" in decision:
            resolved["no_consumer_kind"] = decision["no_consumer_kind"]
        if classification_evidence is not None:
            resolved["classification_evidence"] = classification_evidence
        return resolved
    model_columns = decision["columns"]
    if model_supplies_sparse_columns:
        header_columns = [item["column"] for item in headers]
        if (
            any(
                not isinstance(item, dict)
                or set(item) != {"column", "semantic_role"}
                or item.get("column") not in header_columns
                or item.get("semantic_role") not in _SEMANTIC_ROLES
                for item in model_columns
            )
            or len({item["column"] for item in model_columns}) != len(model_columns)
        ):
            _fail("ordinary_trade_semantic_mapping_columns_invalid")
        roles_by_column = {
            item["column"]: item["semantic_role"] for item in model_columns
        }
        columns = [
            {
                "column": item["column"],
                "semantic_role": roles_by_column.get(item["column"], "unmapped"),
            }
            for item in headers
        ]
    else:
        columns = model_columns
    if (
        len(columns) != len(headers)
        or [item.get("column") for item in columns]
        != [item["column"] for item in headers]
        or any(
            not isinstance(item, dict)
            or set(item) != {"column", "semantic_role"}
            or item.get("semantic_role") not in _SEMANTIC_ROLES
            for item in columns
        )
        or (
            not incomplete
            and not (
                (_REQUIRED_ROLES - {"currency"})
                <= {item["semantic_role"] for item in columns}
                if (user_currency_assertion is not None or allow_user_currency)
                else _REQUIRED_ROLES <= {item["semantic_role"] for item in columns}
            )
        )
        or (
            (user_currency_assertion is not None or allow_user_currency)
            and "currency" in {item["semantic_role"] for item in columns}
        )
    ):
        _fail("ordinary_trade_semantic_mapping_columns_invalid")
    present_required_roles = {
        item["semantic_role"] for item in columns if item["semantic_role"] in _REQUIRED_ROLES
    }
    if incomplete:
        missing_required_roles = sorted(_REQUIRED_ROLES - present_required_roles)
        if (
            not missing_required_roles
            or (
                model_supplies_missing_required_roles
                and decision.get("missing_required_roles") != missing_required_roles
            )
            or decision["amount_currency_bindings"]
            or user_currency_assertion is not None
            or allow_user_currency
        ):
            _fail("ordinary_trade_semantic_mapping_incomplete_trade_invalid")
    side_columns = [
        item["column"] for item in columns if item["semantic_role"] == "side"
    ]
    if len(side_columns) != 1 and not (incomplete and not side_columns):
        _fail("ordinary_trade_semantic_mapping_side_invalid")
    expected_rows = sorted(
        source_row["row"]
        for source_row in table["rows"]
        if source_row["row"] > decision["header_row"]
        and any(cell["literal"].strip() for cell in source_row["cells"])
    )
    row_dispositions = decision["row_dispositions"]
    if (
        not row_dispositions
        or any(
            not isinstance(item, dict)
            or set(item) != {"row", "disposition"}
            or not isinstance(item.get("row"), int)
            or item.get("disposition")
            not in {"SECURITY_TRADES", "NO_NAMED_CONSUMER"}
            for item in row_dispositions
        )
        or [item["row"] for item in row_dispositions]
        != sorted(set(item["row"] for item in row_dispositions))
        or {item["row"] for item in row_dispositions} != set(expected_rows)
    ):
        _fail("ordinary_trade_semantic_mapping_row_coverage_invalid")
    security_trade_rows = [
        item["row"]
        for item in row_dispositions
        if item["disposition"] == "SECURITY_TRADES"
    ]
    if not security_trade_rows:
        _fail("ordinary_trade_semantic_mapping_row_coverage_invalid")
    source_side_literals = {
        cell["literal"]
        for source_row in table["rows"]
        if source_row["row"] in security_trade_rows
        for cell in source_row["cells"]
        if side_columns and cell["column"] == side_columns[0] and cell["literal"]
    }
    side_values = decision["side_values"]
    if (
        (not side_values and side_columns)
        or any(
            not isinstance(item, dict)
            or set(item) != {"source_literal", "normalized_value"}
            or item.get("source_literal") not in source_side_literals
            or item.get("normalized_value") not in {"PURCHASE", "DISPOSAL"}
            for item in side_values
        )
        or len({item["source_literal"] for item in side_values}) != len(side_values)
        or {item["source_literal"] for item in side_values} != source_side_literals
    ):
        _fail("ordinary_trade_semantic_mapping_side_invalid")
    bindings = copy.deepcopy(decision["amount_currency_bindings"])
    if user_currency_assertion is not None:
        if bindings:
            _fail("ordinary_trade_user_currency_request_invalid")
        bindings = [
            {"amount_column": item["column"], "currency_source": {"kind": "user_assertion"}}
            for item in columns
            if item["semantic_role"]
            in {"gross_amount", "broker_commission", "exchange_commission"}
        ]
    elif allow_user_currency and bindings:
        _fail("ordinary_trade_user_currency_request_invalid")
    return {
        "table_node_id": table["table_node_id"],
        "header_row": decision["header_row"],
        "structural_fingerprint": fingerprint,
        "evidence_surface": {"title_literal": None, "headers": headers},
        "disposition": disposition,
        "headers": headers,
        "columns": copy.deepcopy(columns),
        "amount_currency_bindings": bindings,
        "side_values": copy.deepcopy(side_values),
        "security_trade_rows": security_trade_rows,
        **(
            {"missing_required_roles": copy.deepcopy(missing_required_roles)}
            if incomplete
            else {}
        ),
    }


_DECISION_FIELDS = {
    "decision_kind",
    "table_ref",
    "header_row",
    "column",
    "semantic_role",
    "amount_column",
    "currency_column",
    "source_literal",
    "normalized_value",
    "disposition",
}
_INTERNAL_DECISION_FIELDS = (_DECISION_FIELDS - {"table_ref"}) | {"table_node_id"}


def _validate_clarification_decision(*, decision: Any, table: dict[str, Any]) -> None:
    if (
        not isinstance(decision, dict)
        or set(decision) != _INTERNAL_DECISION_FIELDS
        or decision.get("decision_kind") not in _DECISION_KINDS
        or decision.get("table_node_id") != table["table_node_id"]
        or not isinstance(decision.get("header_row"), int)
    ):
        _fail("ordinary_trade_semantic_mapping_question_decision_invalid")
    header = next(
        (item for item in table["rows"] if item["row"] == decision["header_row"]),
        None,
    )
    columns = {item["column"] for item in (header or {}).get("cells", [])}
    kind = decision["decision_kind"]
    required_non_null: set[str]
    if kind == "COLUMN_ROLE":
        required_non_null = {"column", "semantic_role"}
        valid = (
            decision["column"] in columns
            and decision["semantic_role"] in _SEMANTIC_ROLES
        )
    elif kind == "AMOUNT_CURRENCY_BINDING":
        required_non_null = {"amount_column", "currency_column"}
        valid = {
            decision["amount_column"],
            decision["currency_column"],
        } <= columns
    elif kind == "SIDE_VALUE":
        required_non_null = {"source_literal", "normalized_value"}
        source_literals = {
            cell["literal"]
            for row in table["rows"]
            if row["row"] > decision["header_row"]
            for cell in row["cells"]
            if cell["literal"]
        }
        valid = decision["source_literal"] in source_literals and decision[
            "normalized_value"
        ] in {"PURCHASE", "DISPOSAL"}
    else:
        required_non_null = {"disposition"}
        valid = decision["disposition"] in _TABLE_DISPOSITIONS
    nullable = (
        _INTERNAL_DECISION_FIELDS
        - {"decision_kind", "table_node_id", "header_row"}
        - required_non_null
    )
    if (
        not valid
        or any(decision[key] is None for key in required_non_null)
        or any(decision[key] is not None for key in nullable)
    ):
        _fail("ordinary_trade_semantic_mapping_question_decision_invalid")


def _validate_confirmed_decisions(
    *,
    confirmed_understandings: list[dict[str, Any]],
    resolved_decisions: list[dict[str, Any]],
) -> None:
    by_table = {item["table_node_id"]: item for item in resolved_decisions}
    for understanding in confirmed_understandings:
        decision = understanding.get("decision")
        if isinstance(decision, dict) and decision.get("decision_kind") == "USER_PROVIDED_CURRENCY":
            continue
        resolved = by_table.get((decision or {}).get("table_node_id"))
        if (
            isinstance(decision, dict)
            and decision.get("decision_kind") == "TABLE_DISPOSITION"
            and decision.get("disposition") == "NO_NAMED_CONSUMER"
            and resolved is None
        ):
            continue
        if resolved is None or not _resolved_decision_satisfies(
            resolved=resolved, decision=decision
        ):
            _fail("ordinary_trade_semantic_mapping_confirmed_decision_conflict")


def _confirmed_user_currency_assertion(
    *, confirmed_understandings: list[dict[str, Any]], table_node_id: str
) -> dict[str, Any] | None:
    matches = []
    for item in confirmed_understandings:
        decision = item.get("decision") if isinstance(item, dict) else None
        if (
            isinstance(decision, dict)
            and decision.get("decision_kind") == "USER_PROVIDED_CURRENCY"
            and table_node_id in (decision.get("table_node_ids") or [])
        ):
            matches.append(decision)
    if len(matches) > 1:
        _fail("ordinary_trade_user_currency_assertion_ambiguous")
    if not matches:
        return None
    decision = matches[0]
    return {
        key: decision[key]
        for key in (
            "schema_version",
            "assertion_id",
            "currency_code",
            "case_binding_sha256",
            "table_node_ids",
        )
    }


def _confirmed_exclusion_resolutions(
    *,
    confirmed_understandings: list[dict[str, Any]],
    tables: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Read pre-v6 confirmed exclusions without sending them to the model again.

    This is persistence compatibility only.  New model responses pass through
    ``_validate_table_decision`` with ``allow_legacy_no_consumer=False`` and
    therefore cannot promote an unevidenced exclusion.
    """

    results = []
    for understanding in confirmed_understandings:
        decision = understanding.get("decision")
        if not (
            isinstance(decision, dict)
            and decision.get("decision_kind") == "TABLE_DISPOSITION"
            and decision.get("disposition") == "NO_NAMED_CONSUMER"
        ):
            continue
        table_node_id = str(decision.get("table_node_id") or "")
        table = tables.get(table_node_id)
        if table is None:
            _fail("ordinary_trade_semantic_mapping_confirmed_decision_conflict")
        results.append(
            _validate_table_decision(
                decision={
                    "table_node_id": table_node_id,
                    "header_row": decision.get("header_row"),
                    "disposition": "NO_NAMED_CONSUMER",
                    "columns": [],
                    "amount_currency_bindings": [],
                    "side_values": [],
                    "row_dispositions": [],
                },
                table=table,
                allow_legacy_no_consumer=True,
            )
        )
    if len({item["table_node_id"] for item in results}) != len(results):
        _fail("ordinary_trade_semantic_mapping_confirmed_decision_conflict")
    return results


def _resolved_decision_satisfies(
    *, resolved: dict[str, Any], decision: dict[str, Any]
) -> bool:
    kind = decision["decision_kind"]
    if resolved["header_row"] != decision["header_row"]:
        return False
    if kind == "TABLE_DISPOSITION":
        return resolved["disposition"] == decision["disposition"]
    if resolved["disposition"] != "SECURITY_TRADES":
        return False
    if kind == "COLUMN_ROLE":
        return {
            "column": decision["column"],
            "semantic_role": decision["semantic_role"],
        } in resolved["columns"]
    if kind == "AMOUNT_CURRENCY_BINDING":
        return {
            "amount_column": decision["amount_column"],
            "currency_column": decision["currency_column"],
        } in resolved["amount_currency_bindings"]
    return {
        "source_literal": decision["source_literal"],
        "normalized_value": decision["normalized_value"],
    } in resolved["side_values"]


def _validate_question(
    question: Any,
    *,
    table_refs: set[str] | None = None,
    internal: bool = False,
) -> None:
    table_key = "table_node_id" if internal else "table_ref"
    allowed_question_keys = {
        "question_id",
        table_key,
        "question",
        "options",
    }
    if internal:
        allowed_question_keys_batch = {
            "question_id",
            "table_node_ids",
            "question",
            "options",
        }
    else:
        allowed_question_keys_batch = set()
    is_batch = (
        internal
        and isinstance(question, dict)
        and set(question) == allowed_question_keys_batch
    )
    if (
        not isinstance(question, dict)
        or frozenset(question)
        not in {
            frozenset(allowed_question_keys),
            frozenset(allowed_question_keys_batch),
        }
        or not isinstance(question.get("question_id"), str)
        or (
            internal
            and re.fullmatch(r"q_[a-z0-9][a-z0-9_-]{5,63}", question["question_id"])
            is None
        )
        or (not internal and not question["question_id"].strip())
        or (
            (not is_batch and not isinstance(question.get(table_key), str))
            or (
                not is_batch
                and table_refs is not None
                and question[table_key] not in table_refs
            )
            or (
                is_batch
                and (
                    not isinstance(question.get("table_node_ids"), list)
                    or not question["table_node_ids"]
                    or len(question["table_node_ids"])
                    > _MAX_EXCLUSION_CONFIRMATION_TABLES
                    or len(question["table_node_ids"])
                    != len(set(question["table_node_ids"]))
                    or any(
                        not isinstance(item, str) or not item
                        for item in question["table_node_ids"]
                    )
                )
            )
        )
        or not isinstance(question.get("question"), str)
        or not question["question"].strip()
        or not isinstance(question.get("options"), list)
        or not 2 <= len(question["options"]) <= 4
    ):
        _fail("ordinary_trade_semantic_mapping_question_invalid")
    option_ids = []
    for option in question["options"]:
        is_batch_option = (
            internal
            and isinstance(option, dict)
            and set(option)
            == {"option_id", "label", "effect", "decisions", "source_literals"}
        )
        if (
            not isinstance(option, dict)
            or (is_batch and not is_batch_option)
            or (not is_batch and is_batch_option)
            or (
                not is_batch_option
                and set(option)
                != (
                    {"option_id", "label", "decision", "source_literals"}
                    if internal
                    else {"option_id", "label", "decision"}
                )
            )
            or not isinstance(option.get("option_id"), str)
            or (
                internal
                and re.fullmatch(r"o_[a-z0-9][a-z0-9_-]{2,63}", option["option_id"])
                is None
            )
            or (not internal and not option["option_id"].strip())
            or not isinstance(option.get("label"), str)
            or not option["label"].strip()
            or (
                not is_batch_option
                and (
                    not isinstance(option.get("decision"), dict)
                    or set(option["decision"])
                    != (_INTERNAL_DECISION_FIELDS if internal else _DECISION_FIELDS)
                )
            )
            or (
                internal
                and (
                    not isinstance(option.get("source_literals"), list)
                    or len(option["source_literals"]) > 4
                    or any(
                        not isinstance(item, str) or not item.strip() or len(item) > 500
                        for item in option["source_literals"]
                    )
                    or len(option["source_literals"])
                    != len(set(option["source_literals"]))
                )
            )
            or (
                is_batch_option
                and (
                    option.get("effect") not in {"APPLY_DECISIONS", "SPECIALIST_REVIEW"}
                    or not isinstance(option.get("decisions"), list)
                    or (
                        option["effect"] == "APPLY_DECISIONS"
                        and (
                            not option["decisions"]
                            or len(option["decisions"])
                            != len(question["table_node_ids"])
                        )
                    )
                    or (option["effect"] == "SPECIALIST_REVIEW" and option["decisions"])
                    or any(
                        not isinstance(decision, dict)
                        or set(decision) != _INTERNAL_DECISION_FIELDS
                        or decision.get("decision_kind") != "TABLE_DISPOSITION"
                        or decision.get("disposition") != "NO_NAMED_CONSUMER"
                        or not isinstance(decision.get("header_row"), int)
                        or any(
                            decision.get(key) is not None
                            for key in (
                                "column",
                                "semantic_role",
                                "amount_column",
                                "currency_column",
                                "source_literal",
                                "normalized_value",
                            )
                        )
                        for decision in option["decisions"]
                    )
                )
            )
        ):
            _fail("ordinary_trade_semantic_mapping_question_invalid")
        if is_batch_option and option["effect"] == "APPLY_DECISIONS":
            decision_node_ids = [
                decision["table_node_id"] for decision in option["decisions"]
            ]
            if decision_node_ids != question["table_node_ids"]:
                _fail("ordinary_trade_semantic_mapping_question_invalid")
        option_ids.append(option["option_id"])
    if len(option_ids) != len(set(option_ids)):
        _fail("ordinary_trade_semantic_mapping_question_invalid")


def validate_internal_mapping_question(question: Any) -> None:
    """Validate the stored mapping-owner question before it crosses an adapter."""

    _validate_question(question, internal=True)


def _strict_model_value(response: Any) -> dict[str, Any]:
    value = getattr(response, "content", response)
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            _fail("ordinary_trade_semantic_mapping_response_invalid")
    if not isinstance(value, dict):
        _fail("ordinary_trade_semantic_mapping_response_invalid")
    return copy.deepcopy(value)


def _execution_metadata_sha256(value: Any) -> str:
    return _sha256_json(_execution_metadata_value(value))


def _execution_metadata_value(value: Any) -> dict[str, Any]:
    if value is None:
        _fail("ordinary_trade_semantic_mapping_execution_metadata_missing")
    if hasattr(value, "snapshot"):
        value = value.snapshot()
    elif is_dataclass(value):
        value = asdict(value)
    if not isinstance(value, dict):
        _fail("ordinary_trade_semantic_mapping_execution_metadata_missing")
    return copy.deepcopy(value)


def _response_format(*, name: str, schema: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {"name": name, "strict": True, "schema": schema},
    }


def _mapping_response_schema() -> dict[str, Any]:
    column = {
        "type": "object",
        "additionalProperties": False,
        "required": ["column", "semantic_role"],
        "properties": {
            "column": {"type": "integer", "minimum": 1},
            "semantic_role": {"type": "string", "enum": sorted(_SEMANTIC_ROLES)},
        },
    }
    table_decision_common = {
        "table_ref": {"type": "string", "minLength": 1},
        "header_row": {
            "anyOf": [
                {"type": "integer", "minimum": 1},
                {"type": "null"},
            ]
        },
    }
    security_trade_table_decision = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "table_ref",
            "header_row",
            "disposition",
            "columns",
            "amount_currency_bindings",
            "side_values",
            "row_dispositions",
        ],
        "properties": {
            **table_decision_common,
            "disposition": {"const": "SECURITY_TRADES"},
            "columns": {"type": "array", "items": column},
            "amount_currency_bindings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["amount_column", "currency_column"],
                    "properties": {
                        "amount_column": {"type": "integer", "minimum": 1},
                        "currency_column": {"type": "integer", "minimum": 1},
                    },
                },
            },
            "side_values": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["source_literal", "normalized_value"],
                    "properties": {
                        "source_literal": {"type": "string", "minLength": 1},
                        "normalized_value": {
                            "type": "string",
                            "enum": ["PURCHASE", "DISPOSAL"],
                        },
                    },
                },
            },
            "row_dispositions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["row", "disposition"],
                    "properties": {
                        "row": {"type": "integer", "minimum": 1},
                        "disposition": {
                            "type": "string",
                            "enum": ["SECURITY_TRADES", "NO_NAMED_CONSUMER"],
                        },
                    },
                },
            },
        },
    }
    incomplete_security_trade_table_decision = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "table_ref",
            "header_row",
            "disposition",
            "columns",
            "amount_currency_bindings",
            "side_values",
            "row_dispositions",
        ],
        "properties": {
            **table_decision_common,
            "disposition": {"const": "SECURITY_TRADES_INCOMPLETE"},
            "columns": {"type": "array", "items": column},
            "amount_currency_bindings": {"type": "array", "maxItems": 0},
            "side_values": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["source_literal", "normalized_value"],
                    "properties": {
                        "source_literal": {"type": "string", "minLength": 1},
                        "normalized_value": {
                            "type": "string",
                            "enum": ["PURCHASE", "DISPOSAL"],
                        },
                    },
                },
            },
            "row_dispositions": security_trade_table_decision["properties"][
                "row_dispositions"
            ],
        },
    }
    classification_evidence = {
        "type": "array",
        "minItems": 1,
        "items": {
            "type": "object",
            "additionalProperties": False,
            "required": ["context_ref", "relation"],
            "properties": {
                "context_ref": {"type": "string", "minLength": 1},
                "relation": {"type": "string", "minLength": 1},
            },
        },
    }
    instructional_reference_table_decision = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "table_ref",
            "header_row",
            "disposition",
            "columns",
            "amount_currency_bindings",
            "side_values",
            "row_dispositions",
            "no_consumer_kind",
            "classification_evidence",
        ],
        "properties": {
            **table_decision_common,
            "disposition": {"const": "NO_NAMED_CONSUMER"},
            "columns": {"type": "array", "maxItems": 0},
            "amount_currency_bindings": {"type": "array", "maxItems": 0},
            "side_values": {"type": "array", "maxItems": 0},
            "row_dispositions": {"type": "array", "maxItems": 0},
            "no_consumer_kind": {"const": "INSTRUCTIONAL_REFERENCE"},
            "classification_evidence": classification_evidence,
        },
    }
    other_no_named_consumer_table_decision = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "table_ref",
            "header_row",
            "disposition",
            "columns",
            "amount_currency_bindings",
            "side_values",
            "row_dispositions",
            "no_consumer_kind",
        ],
        "properties": {
            **table_decision_common,
            "disposition": {"const": "NO_NAMED_CONSUMER"},
            "columns": {"type": "array", "maxItems": 0},
            "amount_currency_bindings": {"type": "array", "maxItems": 0},
            "side_values": {"type": "array", "maxItems": 0},
            "row_dispositions": {"type": "array", "maxItems": 0},
            "no_consumer_kind": {"const": "OTHER_NO_NAMED_CONSUMER"},
        },
    }
    unsupported_financial_meaning_table_decision = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "table_ref",
            "header_row",
            "disposition",
            "columns",
            "amount_currency_bindings",
            "side_values",
            "row_dispositions",
        ],
        "properties": {
            **table_decision_common,
            "disposition": {"const": "UNSUPPORTED_FINANCIAL_MEANING"},
            "columns": {"type": "array", "maxItems": 0},
            "amount_currency_bindings": {"type": "array", "maxItems": 0},
            "side_values": {"type": "array", "maxItems": 0},
            "row_dispositions": {"type": "array", "maxItems": 0},
        },
    }
    header_absent_table_decision = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "table_ref",
            "header_row",
            "disposition",
            "columns",
            "amount_currency_bindings",
            "side_values",
            "row_dispositions",
        ],
        "properties": {
            **table_decision_common,
            "header_row": {"type": "null"},
            "disposition": {"const": "HEADER_ABSENT"},
            "columns": {"type": "array", "maxItems": 0},
            "amount_currency_bindings": {"type": "array", "maxItems": 0},
            "side_values": {"type": "array", "maxItems": 0},
            "row_dispositions": {"type": "array", "maxItems": 0},
        },
    }
    table_decision = {
        "anyOf": [
            header_absent_table_decision,
            security_trade_table_decision,
            incomplete_security_trade_table_decision,
            instructional_reference_table_decision,
            other_no_named_consumer_table_decision,
            unsupported_financial_meaning_table_decision,
        ]
    }
    decision = {
        "type": "object",
        "additionalProperties": False,
        "required": sorted(_DECISION_FIELDS),
        "properties": {
            "decision_kind": {
                "type": "string",
                "enum": sorted(_DECISION_KINDS),
            },
            "table_ref": {"type": "string", "minLength": 1},
            "header_row": {"type": "integer", "minimum": 1},
            "column": {"anyOf": [{"type": "null"}, {"type": "integer", "minimum": 1}]},
            "semantic_role": {
                "anyOf": [
                    {"type": "null"},
                    {"type": "string", "enum": sorted(_SEMANTIC_ROLES)},
                ]
            },
            "amount_column": {
                "anyOf": [{"type": "null"}, {"type": "integer", "minimum": 1}]
            },
            "currency_column": {
                "anyOf": [{"type": "null"}, {"type": "integer", "minimum": 1}]
            },
            "source_literal": {
                "anyOf": [{"type": "null"}, {"type": "string", "minLength": 1}]
            },
            "normalized_value": {
                "anyOf": [
                    {"type": "null"},
                    {"type": "string", "enum": ["PURCHASE", "DISPOSAL"]},
                ]
            },
            "disposition": {
                "anyOf": [
                    {"type": "null"},
                    {"type": "string", "enum": sorted(_TABLE_DISPOSITIONS)},
                ]
            },
        },
    }
    question = {
        "type": "object",
        "additionalProperties": False,
        "required": ["question_id", "table_ref", "question", "options"],
        "properties": {
            "question_id": {"type": "string", "minLength": 1},
            "table_ref": {"type": "string", "minLength": 1},
            "question": {"type": "string", "minLength": 1},
            "options": {
                "type": "array",
                "minItems": 2,
                "maxItems": 4,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["option_id", "label", "decision"],
                    "properties": {
                        "option_id": {"type": "string", "minLength": 1},
                        "label": {"type": "string", "minLength": 1},
                        "decision": decision,
                    },
                },
            },
        },
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "schema_version",
            "status",
            "table_decisions",
            "clarification",
            "message",
        ],
        "properties": {
            "schema_version": {
                "type": "string",
                "const": MAPPING_RESPONSE_SCHEMA_VERSION,
            },
            "status": {"type": "string", "enum": sorted(_MAPPING_STATUSES)},
            "table_decisions": {"type": "array", "items": table_decision},
            "clarification": {"anyOf": [{"type": "null"}, question]},
            "message": {"type": "string", "minLength": 1},
        },
    }


def _answer_response_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "schema_version",
            "status",
            "option_id",
            "message",
            "evidence_quote",
        ],
        "properties": {
            "schema_version": {
                "type": "string",
                "const": ANSWER_RESPONSE_SCHEMA_VERSION,
            },
            "status": {
                "type": "string",
                "enum": ["CANDIDATE", "CLARIFY", "SPECIALIST_REVIEW"],
            },
            "option_id": {
                "anyOf": [{"type": "null"}, {"type": "string", "minLength": 1}]
            },
            "message": {"type": "string", "minLength": 1},
            "evidence_quote": {"type": "string"},
        },
    }


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _fail(code: str, *, diagnostic_code: str | None = None) -> None:
    raise OrdinaryTradeSemanticMappingError(code, diagnostic_code=diagnostic_code)


__all__ = [
    "ANSWER_RESPONSE_SCHEMA_VERSION",
    "FACTORY_REQUIRED",
    "FORBIDDEN",
    "MAPPING_BATCH_PLAN_SCHEMA_VERSION",
    "MAPPING_CASE_SCHEMA_VERSION",
    "MAPPING_RESPONSE_SCHEMA_VERSION",
    "OrdinaryTradeSemanticMapping",
    "OrdinaryTradeSemanticMappingError",
    "OrdinaryTradeSemanticMappingFactory",
]
