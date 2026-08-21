"""Gate 3 second pass: bind labeled facts to source-backed financial roles."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
import hashlib
from importlib import resources
import json
import re
from typing import Any

from .artifact_models import ArtifactAccessContext
from .canonical_store import CanonicalReaderFactory
from .gate3_bounded_labeling import (
    FINANCIAL_ANNOTATIONS_SCHEMA_VERSION,
    Gate3BoundedLabelingAttempt,
    gate3_target_alias_is_valid,
)
from .gate3_financial_role_pack import (
    GATE3_ROLE_PACK_CURRENT_VERSION,
    Gate3FinancialRolePackFactory,
)


FINANCIAL_ANNOTATIONS_V2_SCHEMA_VERSION = "broker_reports_financial_annotations_v2"
GATE3_ROLE_LABELING_RESPONSE_SCHEMA_VERSION = (
    "broker_reports_gate3_role_labeling_response_v1"
)
GATE3_ROLE_CONTEXT_SCHEMA_VERSION = "broker_reports_gate3_role_context_v1"
GATE3_ROLE_LABELING_RESPONSE_SCHEMA_RESOURCE = (
    "gate3_role_labeling_response.v1.schema.json"
)
GATE3_ROLE_LABELING_RESPONSE_SCHEMA_SHA256 = (
    "9585d83de337e8fbacf1f000a797c4018c034ab9fa0e28e5054c1842c29b99d8"
)
GATE3_ROLE_LABELING_INSTRUCTION_ID = "broker-reports-source-bound-role-labeling"
GATE3_ROLE_LABELING_INSTRUCTION_VERSION = "1.1.0"
GATE3_ROLE_LABELING_INSTRUCTION = (
    "Для каждого переданного fact_alias верни ровно один факт с неизменным "
    "financial_label. Для каждой разрешённой этому типу роли из Role Pack "
    "верни ровно одну запись. Financial fact и его exact accepted target уже "
    "выбраны semantic pass: не ищи событие заново и не меняй строку/region. "
    "Используй status=bound только с bare target_alias из указанного для этого "
    "fact_alias списка allowed_role_target_aliases. Если target содержит больший текст, "
    "добавь exact_text как точную регистрозависимую подстроку источника. "
    "Не вычисляй, не нормализуй и не угадывай значения. Если безопасной "
    "привязки нет, верни только role и status=missing. Не добавляй факты, "
    "роли, canonical refs или пояснения. Верни только "
    "Gate3RoleLabelingResponseV1."
)

FACTORY_REQUIRED = (
    "Gate3RoleLabelingFactory.create_from_chunk is the only Gate 3 role-pass "
    "entrypoint; it must consume the validated pass-1 attempt, exact chunk, "
    "Gate3RoleContextFactory.create_from_accepted_facts, "
    "Gate3FinancialRolePackFactory.create and "
    "Gate3RoleValueResolverFactory.create_from_active_canonical"
)
FORBIDDEN = (
    "The role pass must not relabel facts, duplicate Role Pack meaning, read "
    "source formats or raw provider output, normalize or compute values, retry, "
    "repair, use RAG, persist a parallel artifact or start Gate 4; a coarse "
    "canonical region must not be expanded into unrelated structural rows"
)

_FACT_ALIAS = re.compile(r"^f[0-9]{3,}$")
_TARGET_ALIAS = re.compile(r"(?<!\\)\[(t[0-9]{3,})\]")
_LOCAL_ROLE_REJECTION_CODES = frozenset(
    {
        "gate3_role_target_alias_unknown",
        "gate3_role_target_outside_fact_context",
        "gate3_role_target_text_empty",
        "gate3_role_target_text_ambiguous",
        "gate3_role_exact_text_not_literal_substring",
    }
)


class Gate3RoleLabelingError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class _DuplicateJsonKeyError(ValueError):
    pass


@dataclass(frozen=True)
class Gate3RoleLabelingAttempt:
    chunk: dict[str, Any] = field(repr=False)
    role_context: dict[str, Any] = field(repr=False)
    role_provenance: dict[str, Any] = field(repr=False)
    pass1_output: dict[str, Any] = field(repr=False)
    facts: tuple[dict[str, Any], ...] = field(repr=False)
    role_pack: dict[str, Any] = field(repr=False)
    role_pack_markdown: str = field(repr=False)
    instruction: str = field(repr=False)
    model_visible_request: dict[str, Any] | None = field(repr=False)
    final_provider_request: dict[str, Any] | None = field(repr=False)
    raw_provider_response: dict[str, Any] | None = field(repr=False)
    raw_model_output: Any = field(repr=False)
    validated_output: dict[str, Any] | None = field(repr=False)
    rejected_role_bindings: tuple[dict[str, Any], ...] = field(repr=False)
    execution_status: str
    validation_error_code: str | None
    execution_metadata: Any
    operational_retry_receipt: dict[str, Any] | None
    metrics: dict[str, Any]


class Gate3RoleContextFactory:
    """Build the minimal accepted-target context for the role proposal.

    The semantic pass has already selected the fact target. This owner keeps
    only that exact canonical row/region (plus cells in the same canonical
    table row and context-only structural headers). It never discovers or
    relabels financial events.
    """

    @staticmethod
    def create_from_accepted_facts(
        *,
        chunk: dict[str, Any],
        facts: list[dict[str, Any]],
    ) -> dict[str, Any]:
        mappings = list(chunk.get("target_mappings") or [])
        mapping_by_alias = {
            str(mapping.get("target_alias") or ""): mapping
            for mapping in mappings
            if isinstance(mapping, dict)
        }
        if len(mapping_by_alias) != len(mappings) or any(
            not gate3_target_alias_is_valid(alias) for alias in mapping_by_alias
        ):
            raise Gate3RoleLabelingError("gate3_role_context_mapping_invalid")

        allowed_by_fact: dict[str, list[str]] = {}
        accepted_aliases: list[str] = []
        for fact in facts:
            fact_alias = str(fact.get("fact_alias") or "")
            target_alias = str(fact.get("fact_target_alias") or "")
            target = fact.get("target")
            if (
                _FACT_ALIAS.fullmatch(fact_alias) is None
                or target_alias not in mapping_by_alias
                or not isinstance(target, dict)
                or mapping_by_alias[target_alias].get("canonical_target") != target
            ):
                raise Gate3RoleLabelingError("gate3_role_context_fact_invalid")
            allowed = _fact_row_or_region_aliases(
                target_alias=target_alias,
                target=target,
                mappings=mappings,
            )
            if target_alias not in allowed:
                raise Gate3RoleLabelingError("gate3_role_context_fact_invalid")
            allowed_by_fact[fact_alias] = allowed
            if target_alias not in accepted_aliases:
                accepted_aliases.append(target_alias)

        visible_aliases = [
            alias
            for alias in mapping_by_alias
            if any(alias in allowed for allowed in allowed_by_fact.values())
        ]
        content = str((chunk.get("model_view") or {}).get("content") or "")
        context_lines, target_lines = _accepted_context_lines(
            content=content,
            visible_aliases=set(visible_aliases),
            mappings=mappings,
        )
        target_content = "\n".join(target_lines).replace("<br>", "\n").strip()
        context_content = "\n".join(context_lines).strip()
        if context_content:
            model_content = (
                "## Structural context (context only)\n\n"
                + context_content
                + "\n\n## Accepted semantic row or region\n\n"
                + target_content
                + "\n"
            )
        else:
            model_content = target_content + ("\n" if target_content else "")
        model_aliases = _TARGET_ALIAS.findall(model_content)
        if model_aliases != visible_aliases:
            raise Gate3RoleLabelingError("gate3_role_context_visibility_invalid")

        selected_mappings = [
            copy.deepcopy(mapping_by_alias[alias]) for alias in visible_aliases
        ]
        identity_material = {
            "schema_version": GATE3_ROLE_CONTEXT_SCHEMA_VERSION,
            "canonical_binding": chunk.get("canonical_binding"),
            "source_chunk_id": chunk.get("chunk_id"),
            "accepted_target_aliases": accepted_aliases,
            "allowed_role_target_aliases_by_fact": allowed_by_fact,
            "model_view_sha256": hashlib.sha256(
                model_content.encode("utf-8")
            ).hexdigest(),
        }
        context_id = (
            "g3rolectx_"
            + hashlib.sha256(
                json.dumps(
                    identity_material,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest()[:24]
        )
        return {
            "schema_version": GATE3_ROLE_CONTEXT_SCHEMA_VERSION,
            "context_id": context_id,
            "canonical_binding": copy.deepcopy(chunk.get("canonical_binding")),
            "source_chunk_id": chunk.get("chunk_id"),
            "construction_policy": {
                "accepted_fact_targets_only": True,
                "same_table_row_cell_closure": True,
                "same_table_structural_headers_context_only": True,
                "same_table_source_first_row_context_only": True,
                "coarse_region_to_unrelated_rows": False,
                "document_wide_event_discovery": False,
                "broker_specific_rules": False,
            },
            "accepted_target_aliases": accepted_aliases,
            "allowed_role_target_aliases_by_fact": copy.deepcopy(allowed_by_fact),
            "model_view": {
                "media_type": "text/markdown",
                "content": model_content,
            },
            "target_mappings": selected_mappings,
            "structural_sources": [],
            "structural_literal_index": [],
            "metrics": {
                "source_chunk_chars": len(content),
                "role_context_chars": len(model_content),
                "accepted_facts_total": len(facts),
                "accepted_targets_total": len(accepted_aliases),
                "visible_role_targets_total": len(selected_mappings),
                "excluded_chunk_targets_total": len(mappings) - len(selected_mappings),
                "structural_projections_total": 0,
                "structural_rows_total": 0,
                "structural_cells_total": 0,
            },
        }


class Gate3RoleLabelingFactory:
    """Run at most one role proposal for all pass-1 facts in one chunk."""

    def __init__(
        self,
        *,
        store: Any,
        read_enabled: bool,
        model_client: Any,
        model_id: str,
        role_pack_version: str = GATE3_ROLE_PACK_CURRENT_VERSION,
    ) -> None:
        self._store = store
        self._read_enabled = read_enabled
        self._model_client = model_client
        self._model_id = model_id
        self._role_pack_version = role_pack_version

    async def create_from_chunk(
        self,
        *,
        chunk: dict[str, Any],
        context: ArtifactAccessContext,
        pass1_attempt: Gate3BoundedLabelingAttempt,
    ) -> Gate3RoleLabelingAttempt:
        if not isinstance(self._model_id, str) or not self._model_id:
            raise Gate3RoleLabelingError("gate3_role_model_id_required")
        pass1_output = pass1_attempt.validated_output
        if (
            pass1_attempt.validation_status != "validated"
            or not isinstance(pass1_output, dict)
            or pass1_output.get("schema_version")
            != FINANCIAL_ANNOTATIONS_SCHEMA_VERSION
        ):
            raise Gate3RoleLabelingError("gate3_role_pass1_not_validated")
        projection = pass1_attempt.projection
        _validate_chunk_and_projection(chunk=chunk, projection=projection)
        if pass1_output.get("canonical_binding") != chunk.get(
            "canonical_binding"
        ) or pass1_output.get("model_identity") != {"model_id": self._model_id}:
            raise Gate3RoleLabelingError("gate3_role_pass1_identity_mismatch")

        owner = Gate3FinancialRolePackFactory.create()
        role_pack = owner.load_published(self._role_pack_version)
        role_pack_markdown = owner.render_model_markdown(self._role_pack_version)
        facts = _facts_from_pass1(
            pass1_output=pass1_output,
            target_mappings=chunk["target_mappings"],
            role_pack=role_pack,
        )
        resolver = Gate3RoleValueResolverFactory.create_from_active_canonical(
            store=self._store,
            read_enabled=self._read_enabled,
            document_id=chunk["canonical_binding"]["document_id"],
            expected_canonical_version_id=chunk["canonical_binding"][
                "canonical_version_id"
            ],
            context=context,
        )
        role_context = Gate3RoleContextFactory.create_from_accepted_facts(
            chunk=chunk,
            facts=facts,
        )

        if not facts:
            validated_output = _build_v2_output(
                pass1_output=pass1_output,
                role_pack=role_pack,
                annotations=[],
            )
            return Gate3RoleLabelingAttempt(
                chunk=copy.deepcopy(chunk),
                role_context=copy.deepcopy(role_context),
                role_provenance=_build_role_provenance(
                    role_context=role_context,
                    facts=facts,
                    validated_output=validated_output,
                    resolver=resolver,
                ),
                pass1_output=copy.deepcopy(pass1_output),
                facts=(),
                role_pack=copy.deepcopy(role_pack),
                role_pack_markdown=role_pack_markdown,
                instruction=GATE3_ROLE_LABELING_INSTRUCTION,
                model_visible_request=None,
                final_provider_request=None,
                raw_provider_response=None,
                raw_model_output=None,
                validated_output=validated_output,
                rejected_role_bindings=(),
                execution_status="skipped_empty",
                validation_error_code=None,
                execution_metadata=None,
                operational_retry_receipt=None,
                metrics=_metrics(
                    chunk=chunk,
                    role_context=role_context,
                    facts=facts,
                    role_pack_markdown=role_pack_markdown,
                    final_provider_request=None,
                    raw_provider_response=None,
                    raw_model_output=None,
                    validated_output=validated_output,
                    role_pack=role_pack,
                    rejected_role_bindings=(),
                    provider_called=False,
                ),
            )

        response_schema = _load_response_schema()
        model_visible_request = _compose_model_visible_request(
            role_context=role_context,
            facts=facts,
            role_pack_markdown=role_pack_markdown,
            response_schema=response_schema,
        )
        model_result = await self._model_client.label_gate3_once(
            model_visible_request=model_visible_request,
            canonical_schema=response_schema,
            model_id=self._model_id,
        )
        final_provider_request = copy.deepcopy(model_result.prepared_request.form_data)
        _audit_final_provider_request(
            final_provider_request=final_provider_request,
            model_visible_request=model_visible_request,
            model_id=self._model_id,
            role_pack_markdown=role_pack_markdown,
        )
        raw_model_output = copy.deepcopy(model_result.adapter_extracted_output)
        execution_status = "validated"
        validation_error_code = None
        rejected_role_bindings: list[dict[str, Any]] = []
        try:
            validated_output, rejected_role_bindings = _validate_and_restore(
                raw_model_output=raw_model_output,
                facts=facts,
                target_mappings=role_context["target_mappings"],
                allowed_aliases_by_fact=role_context[
                    "allowed_role_target_aliases_by_fact"
                ],
                role_pack=role_pack,
                pass1_output=pass1_output,
                resolver=resolver,
            )
            if rejected_role_bindings:
                execution_status = "validated_with_local_rejections"
        except Gate3RoleLabelingError as exc:
            validated_output = None
            rejected_role_bindings = []
            execution_status = "rejected"
            validation_error_code = exc.code
        role_provenance = _build_role_provenance(
            role_context=role_context,
            facts=facts,
            validated_output=validated_output,
            resolver=resolver,
        )
        return Gate3RoleLabelingAttempt(
            chunk=copy.deepcopy(chunk),
            role_context=copy.deepcopy(role_context),
            role_provenance=role_provenance,
            pass1_output=copy.deepcopy(pass1_output),
            facts=tuple(copy.deepcopy(facts)),
            role_pack=copy.deepcopy(role_pack),
            role_pack_markdown=role_pack_markdown,
            instruction=GATE3_ROLE_LABELING_INSTRUCTION,
            model_visible_request=copy.deepcopy(model_visible_request),
            final_provider_request=final_provider_request,
            raw_provider_response=copy.deepcopy(model_result.raw_provider_response),
            raw_model_output=raw_model_output,
            validated_output=validated_output,
            rejected_role_bindings=tuple(copy.deepcopy(rejected_role_bindings)),
            execution_status=execution_status,
            validation_error_code=validation_error_code,
            execution_metadata=model_result.execution_metadata,
            operational_retry_receipt=copy.deepcopy(
                getattr(model_result, "operational_retry_receipt", None)
            ),
            metrics=_metrics(
                chunk=chunk,
                role_context=role_context,
                facts=facts,
                role_pack_markdown=role_pack_markdown,
                final_provider_request=final_provider_request,
                raw_provider_response=model_result.raw_provider_response,
                raw_model_output=raw_model_output,
                validated_output=validated_output,
                role_pack=role_pack,
                rejected_role_bindings=rejected_role_bindings,
                provider_called=True,
            ),
        )


class Gate3RoleValueResolverFactory:
    """Create the deterministic canonical-target value resolver for consumers."""

    @staticmethod
    def create(*, canonical_artifact: dict[str, Any]) -> "Gate3RoleValueResolver":
        return Gate3RoleValueResolver(canonical_artifact=canonical_artifact)

    @classmethod
    def create_from_active_canonical(
        cls,
        *,
        store: Any,
        read_enabled: bool,
        document_id: str,
        expected_canonical_version_id: str,
        context: ArtifactAccessContext,
    ) -> "Gate3RoleValueResolver":
        envelope = (
            CanonicalReaderFactory(
                store=store,
                read_enabled=read_enabled,
            )
            .create()
            .read_active_envelope(document_id, context)
        )
        if envelope.canonical_version_id != expected_canonical_version_id:
            raise Gate3RoleLabelingError("gate3_role_canonical_binding_stale")
        return cls.create(canonical_artifact=envelope.artifact)


class Gate3RoleValueResolver:
    """Resolve a persisted role binding without financial interpretation."""

    def __init__(self, *, canonical_artifact: dict[str, Any]) -> None:
        if not isinstance(canonical_artifact, dict):
            raise Gate3RoleLabelingError("gate3_role_canonical_invalid")
        nodes = canonical_artifact.get("nodes")
        if not isinstance(nodes, list):
            raise Gate3RoleLabelingError("gate3_role_canonical_invalid")
        self._nodes = {
            str(node.get("node_id") or ""): node
            for node in nodes
            if isinstance(node, dict) and node.get("node_id")
        }
        if len(self._nodes) != len(nodes):
            raise Gate3RoleLabelingError("gate3_role_canonical_invalid")
        provenance = canonical_artifact.get("provenance")
        if not isinstance(provenance, list):
            raise Gate3RoleLabelingError("gate3_role_canonical_invalid")
        self._provenance = {
            str(item.get("provenance_id") or ""): item
            for item in provenance
            if isinstance(item, dict) and item.get("provenance_id")
        }
        if len(self._provenance) != len(provenance):
            raise Gate3RoleLabelingError("gate3_role_canonical_invalid")

    def resolve(self, role_binding: dict[str, Any]) -> str | None:
        if not isinstance(role_binding, dict):
            raise Gate3RoleLabelingError("gate3_role_binding_invalid")
        status = role_binding.get("status")
        if status == "missing":
            if set(role_binding) != {"role", "status"}:
                raise Gate3RoleLabelingError("gate3_role_binding_invalid")
            return None
        if status != "bound" or set(role_binding) not in (
            {"role", "status", "target"},
            {"role", "status", "target", "exact_text"},
        ):
            raise Gate3RoleLabelingError("gate3_role_binding_invalid")
        source_texts = tuple(
            text
            for text in self._target_source_texts(role_binding.get("target"))
            if text
        )
        exact_text = role_binding.get("exact_text")
        if exact_text is None:
            if not source_texts:
                raise Gate3RoleLabelingError("gate3_role_target_text_empty")
            if len(source_texts) != 1:
                raise Gate3RoleLabelingError("gate3_role_target_text_ambiguous")
            return source_texts[0]
        if (
            not isinstance(exact_text, str)
            or not exact_text
            or len(exact_text) > 2048
            or not any(exact_text in source_text for source_text in source_texts)
        ):
            raise Gate3RoleLabelingError("gate3_role_exact_text_not_literal_substring")
        return exact_text

    def is_unambiguously_atomic_assertion_target(self, target: Any) -> bool:
        """Classify source addressability without assigning financial meaning."""

        if not isinstance(target, dict):
            raise Gate3RoleLabelingError("gate3_role_target_invalid")
        kind = target.get("kind")
        texts = tuple(text for text in self._target_source_texts(target) if text)
        if kind in {"table_row", "table_cell", "list_item"}:
            return bool(texts)
        if kind != "node" or len(texts) != 1:
            return False
        return len(texts[0].splitlines()) == 1

    def has_unambiguous_literal_anchor(self, annotation: Any) -> bool:
        """Return whether a bound exact literal uniquely anchors the assertion."""

        if not isinstance(annotation, dict):
            raise Gate3RoleLabelingError("gate3_role_binding_invalid")
        roles = annotation.get("roles")
        if not isinstance(roles, list):
            raise Gate3RoleLabelingError("gate3_role_binding_invalid")
        for role in roles:
            if not isinstance(role, dict) or role.get("status") != "bound":
                continue
            exact_text = role.get("exact_text")
            if not isinstance(exact_text, str) or not exact_text:
                continue
            source_texts = self._target_source_texts(role.get("target"))
            if sum(text.count(exact_text) for text in source_texts) == 1:
                return True
        return False

    def _target_source_texts(self, target: Any) -> tuple[str, ...]:
        if not isinstance(target, dict):
            raise Gate3RoleLabelingError("gate3_role_target_invalid")
        kind = target.get("kind")
        expected_keys = {
            "node": {"kind", "node_id"},
            "list_item": {"kind", "node_id", "item_index"},
            "table_row": {"kind", "node_id", "row"},
            "table_cell": {"kind", "node_id", "row", "column"},
        }.get(kind)
        if expected_keys is None or set(target) != expected_keys:
            raise Gate3RoleLabelingError("gate3_role_target_invalid")
        node = self._nodes.get(str(target.get("node_id") or ""))
        if node is None:
            raise Gate3RoleLabelingError("gate3_role_target_unknown")
        content = node.get("content")
        if not isinstance(content, dict):
            raise Gate3RoleLabelingError("gate3_role_target_invalid")
        node_type = str(node.get("node_type") or "")
        if kind == "node":
            if node_type == "TABLE":
                values = [content.get("title"), *(content.get("notes") or [])]
                return tuple(
                    _source_scalar_text(value) for value in values if value is not None
                )
            for field_name in ("text", "summary", "title", "value"):
                if content.get(field_name) is not None:
                    return (_source_scalar_text(content[field_name]),)
            raise Gate3RoleLabelingError("gate3_role_target_text_empty")
        if kind == "list_item":
            if node_type != "LIST":
                raise Gate3RoleLabelingError("gate3_role_target_invalid")
            index = target.get("item_index")
            items = content.get("items")
            if (
                isinstance(index, bool)
                or not isinstance(index, int)
                or not isinstance(items, list)
                or not 0 <= index < len(items)
            ):
                raise Gate3RoleLabelingError("gate3_role_target_unknown")
            item = items[index]
            if isinstance(item, dict):
                item = item.get("text")
            return (_source_scalar_text(item),)
        if node_type != "TABLE":
            raise Gate3RoleLabelingError("gate3_role_target_invalid")
        cells = content.get("cells")
        if not isinstance(cells, list):
            raise Gate3RoleLabelingError("gate3_role_target_invalid")
        row = target.get("row")
        if isinstance(row, bool) or not isinstance(row, int) or row < 1:
            raise Gate3RoleLabelingError("gate3_role_target_invalid")
        row_cells = [
            cell for cell in cells if isinstance(cell, dict) and cell.get("row") == row
        ]
        if kind == "table_cell":
            column = target.get("column")
            if isinstance(column, bool) or not isinstance(column, int) or column < 1:
                raise Gate3RoleLabelingError("gate3_role_target_invalid")
            matches = [cell for cell in row_cells if cell.get("column") == column]
            if len(matches) != 1:
                raise Gate3RoleLabelingError("gate3_role_target_unknown")
            return (_cell_source_text(matches[0]),)
        if not row_cells:
            raise Gate3RoleLabelingError("gate3_role_target_unknown")
        ordered = sorted(row_cells, key=lambda cell: int(cell.get("column") or 0))
        return tuple(_cell_source_text(cell) for cell in ordered)


def _validate_chunk_and_projection(
    *,
    chunk: dict[str, Any],
    projection: dict[str, Any],
) -> None:
    if (
        not isinstance(chunk, dict)
        or not isinstance(projection, dict)
        or projection.get("schema_version") != "broker_reports_gate3_projection_v1"
        or projection.get("canonical_binding") != chunk.get("canonical_binding")
        or projection.get("model_view") != chunk.get("model_view")
        or projection.get("target_mappings") != chunk.get("target_mappings")
        or not isinstance(chunk.get("target_mappings"), list)
        or not isinstance((chunk.get("model_view") or {}).get("content"), str)
    ):
        raise Gate3RoleLabelingError("gate3_role_chunk_invalid")


def _fact_row_or_region_aliases(
    *,
    target_alias: str,
    target: dict[str, Any],
    mappings: list[dict[str, Any]],
) -> list[str]:
    if target.get("kind") not in {"table_row", "table_cell"}:
        return [target_alias]
    node_id = target.get("node_id")
    row = target.get("row")
    return [
        str(mapping["target_alias"])
        for mapping in mappings
        if isinstance(mapping, dict)
        and isinstance(mapping.get("canonical_target"), dict)
        and mapping["canonical_target"].get("kind") in {"table_row", "table_cell"}
        and mapping["canonical_target"].get("node_id") == node_id
        and mapping["canonical_target"].get("row") == row
    ]


def _accepted_context_lines(
    *,
    content: str,
    visible_aliases: set[str],
    mappings: list[dict[str, Any]],
) -> tuple[list[str], list[str]]:
    target_by_alias = {
        str(mapping["target_alias"]): mapping["canonical_target"]
        for mapping in mappings
    }
    accepted_table_nodes = {
        str(target_by_alias[alias].get("node_id") or "")
        for alias in visible_aliases
        if target_by_alias[alias].get("kind") in {"table_row", "table_cell"}
    }
    context_lines: list[str] = []
    target_lines: list[str] = []
    context_only_section = False
    for line in content.splitlines():
        if line.strip() == "## Structural context (context only)":
            context_only_section = True
            continue
        if line.strip() == "## Target content":
            context_only_section = False
            continue
        aliases = _TARGET_ALIAS.findall(line)
        if aliases and any(alias in visible_aliases for alias in aliases):
            if any(alias not in visible_aliases for alias in aliases):
                raise Gate3RoleLabelingError(
                    "gate3_role_context_row_closure_incomplete"
                )
            target_lines.append(line)
            continue
        if context_only_section:
            context_lines.append(line)
            continue
        if aliases and accepted_table_nodes:
            targets = [target_by_alias.get(alias) or {} for alias in aliases]
            same_table = all(
                str(target.get("node_id") or "") in accepted_table_nodes
                for target in targets
            )
            table_rows = {
                (str(target.get("node_id") or ""), target.get("row"))
                for target in targets
                if target.get("kind") in {"table_row", "table_cell"}
            }
            generated_header_row = bool(
                re.match(
                    r"^\|\s*(?:\[t[0-9]{3,}\]\s*)?header\s*\|",
                    line,
                )
            )
            source_first_row = len(table_rows) == 1 and next(iter(table_rows))[1] == 1
            table_title = any(target.get("kind") == "node" for target in targets)
            if same_table and (generated_header_row or source_first_row or table_title):
                context_lines.append(_TARGET_ALIAS.sub("", line))
            continue
        if accepted_table_nodes and (
            line.startswith("| row |") or line.startswith("| --- |")
        ):
            context_lines.append(line)

    while context_lines and not context_lines[0].strip():
        context_lines.pop(0)
    while context_lines and not context_lines[-1].strip():
        context_lines.pop()
    if visible_aliases and not target_lines:
        raise Gate3RoleLabelingError("gate3_role_context_target_missing")
    return context_lines, target_lines


def _facts_from_pass1(
    *,
    pass1_output: dict[str, Any],
    target_mappings: list[dict[str, Any]],
    role_pack: dict[str, Any],
) -> list[dict[str, Any]]:
    alias_by_target: dict[str, str] = {}
    for mapping in target_mappings:
        if (
            not isinstance(mapping, dict)
            or set(mapping) != {"target_alias", "canonical_target"}
            or not gate3_target_alias_is_valid(mapping.get("target_alias"))
            or not isinstance(mapping.get("canonical_target"), dict)
        ):
            raise Gate3RoleLabelingError("gate3_role_chunk_mapping_invalid")
        key = _stable_json(mapping["canonical_target"])
        if key in alias_by_target:
            raise Gate3RoleLabelingError("gate3_role_chunk_mapping_invalid")
        alias_by_target[key] = mapping["target_alias"]
    profiles = {
        profile["financial_label"]: profile for profile in role_pack["profiles"]
    }
    annotations = pass1_output.get("annotations")
    if not isinstance(annotations, list):
        raise Gate3RoleLabelingError("gate3_role_pass1_contract_invalid")
    facts: list[dict[str, Any]] = []
    for index, annotation in enumerate(annotations, start=1):
        if (
            not isinstance(annotation, dict)
            or set(annotation) != {"target", "financial_label"}
            or annotation.get("financial_label") not in profiles
        ):
            raise Gate3RoleLabelingError("gate3_role_pass1_contract_invalid")
        target_key = _stable_json(annotation.get("target"))
        target_alias = alias_by_target.get(target_key)
        if target_alias is None:
            raise Gate3RoleLabelingError("gate3_role_fact_target_unknown")
        facts.append(
            {
                "fact_alias": f"f{index:03d}",
                "financial_label": annotation["financial_label"],
                "fact_target_alias": target_alias,
                "target": copy.deepcopy(annotation["target"]),
            }
        )
    return facts


def _load_response_schema() -> dict[str, Any]:
    try:
        raw = (
            resources.files(__package__)
            .joinpath(GATE3_ROLE_LABELING_RESPONSE_SCHEMA_RESOURCE)
            .read_bytes()
        )
    except (FileNotFoundError, OSError) as exc:
        raise Gate3RoleLabelingError("gate3_role_response_schema_unavailable") from exc
    if hashlib.sha256(raw).hexdigest() != (GATE3_ROLE_LABELING_RESPONSE_SCHEMA_SHA256):
        raise Gate3RoleLabelingError("gate3_role_response_schema_hash_mismatch")
    try:
        schema = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Gate3RoleLabelingError("gate3_role_response_schema_invalid") from exc
    if not isinstance(schema, dict):
        raise Gate3RoleLabelingError("gate3_role_response_schema_invalid")
    return schema


def _compose_model_visible_request(
    *,
    role_context: dict[str, Any],
    facts: list[dict[str, Any]],
    role_pack_markdown: str,
    response_schema: dict[str, Any],
) -> dict[str, Any]:
    facts_lines = ["# Labeled facts"]
    for fact in facts:
        facts_lines.extend(
            [
                "",
                f"- fact_alias: `{fact['fact_alias']}`",
                f"  financial_label: `{fact['financial_label']}`",
                f"  fact_target_alias: `{fact['fact_target_alias']}`",
                "  allowed_role_target_aliases: `"
                + ",".join(
                    role_context["allowed_role_target_aliases_by_fact"][
                        fact["fact_alias"]
                    ]
                )
                + "`",
            ]
        )
    facts_markdown = "\n".join(facts_lines).rstrip() + "\n"
    facts_and_chunk = (
        facts_markdown
        + "\n# Deterministic accepted-target role context\n\n"
        + role_context["model_view"]["content"]
    )
    request = {
        "messages": [
            {"role": "system", "content": GATE3_ROLE_LABELING_INSTRUCTION},
            {"role": "user", "content": role_pack_markdown},
            {"role": "user", "content": facts_and_chunk},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": GATE3_ROLE_LABELING_RESPONSE_SCHEMA_VERSION,
                "strict": True,
                "schema": copy.deepcopy(response_schema),
            },
        },
    }
    contents = [item["content"] for item in request["messages"]]
    if sum(value.count(role_pack_markdown) for value in contents) != 1:
        raise Gate3RoleLabelingError("gate3_role_pack_injection_count_invalid")
    return request


def _audit_final_provider_request(
    *,
    final_provider_request: dict[str, Any],
    model_visible_request: dict[str, Any],
    model_id: str,
    role_pack_markdown: str,
) -> None:
    messages = (
        final_provider_request.get("messages")
        if isinstance(final_provider_request, dict)
        else None
    )
    system = (
        final_provider_request.get("system")
        if isinstance(final_provider_request, dict)
        else None
    )
    if system is None:
        parts = (
            [item.get("content") for item in messages]
            if isinstance(messages, list)
            and all(isinstance(item, dict) for item in messages)
            else []
        )
    else:
        parts = (
            [system, *[item.get("content") for item in messages]]
            if isinstance(system, str)
            and isinstance(messages, list)
            and all(isinstance(item, dict) for item in messages)
            else []
        )
    expected = [item["content"] for item in model_visible_request["messages"]]
    if (
        not isinstance(final_provider_request, dict)
        or final_provider_request.get("model") != model_id
        or parts != expected
        or sum(part.count(role_pack_markdown) for part in parts) != 1
        or "metadata" in final_provider_request
    ):
        raise Gate3RoleLabelingError("gate3_role_model_input_audit_failed")


def _validate_and_restore(
    *,
    raw_model_output: Any,
    facts: list[dict[str, Any]],
    target_mappings: list[dict[str, Any]],
    allowed_aliases_by_fact: dict[str, list[str]],
    role_pack: dict[str, Any],
    pass1_output: dict[str, Any],
    resolver: Gate3RoleValueResolver,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    response = _decode_response(raw_model_output)
    if (
        set(response) != {"schema_version", "facts"}
        or response.get("schema_version") != GATE3_ROLE_LABELING_RESPONSE_SCHEMA_VERSION
        or not isinstance(response.get("facts"), list)
    ):
        raise Gate3RoleLabelingError("gate3_role_response_contract_invalid")
    response_facts = response["facts"]
    if not all(
        isinstance(response_fact, dict)
        and set(response_fact) == {"fact_alias", "financial_label", "roles"}
        and isinstance(response_fact.get("fact_alias"), str)
        and _FACT_ALIAS.fullmatch(response_fact["fact_alias"]) is not None
        and isinstance(response_fact.get("roles"), list)
        for response_fact in response_facts
    ):
        raise Gate3RoleLabelingError("gate3_role_response_contract_invalid")
    expected_aliases = [fact["fact_alias"] for fact in facts]
    response_aliases = [fact["fact_alias"] for fact in response_facts]
    if set(response_aliases) != set(expected_aliases):
        raise Gate3RoleLabelingError("gate3_role_fact_set_mismatch")
    duplicate_aliases = {
        alias for alias in expected_aliases if response_aliases.count(alias) > 1
    }
    response_by_alias = {
        response_fact["fact_alias"]: response_fact
        for response_fact in response_facts
        if response_fact["fact_alias"] not in duplicate_aliases
    }
    expected_by_alias = {fact["fact_alias"]: fact for fact in facts}
    profiles = {
        profile["financial_label"]: profile for profile in role_pack["profiles"]
    }
    target_by_alias = {
        mapping["target_alias"]: mapping["canonical_target"]
        for mapping in target_mappings
    }
    annotations: list[dict[str, Any]] = []
    rejected_role_bindings: list[dict[str, Any]] = []
    for fact_alias in expected_aliases:
        expected = expected_by_alias[fact_alias]
        profile = profiles[expected["financial_label"]]
        allowed_order = [
            *profile["required_roles"],
            *profile["optional_roles"],
        ]
        if fact_alias in duplicate_aliases:
            rejected_role_bindings.extend(
                {
                    "fact_alias": fact_alias,
                    "financial_label": expected["financial_label"],
                    "role": role,
                    "error_code": "gate3_role_fact_alias_duplicated",
                }
                for role in allowed_order
            )
            annotations.append(
                {
                    "target": copy.deepcopy(expected["target"]),
                    "financial_label": expected["financial_label"],
                    "roles": [
                        {"role": role, "status": "missing"}
                        for role in allowed_order
                    ],
                }
            )
            continue
        response_fact = response_by_alias[fact_alias]
        if response_fact.get("financial_label") != expected["financial_label"]:
            raise Gate3RoleLabelingError("gate3_role_fact_label_mismatch")
        bindings_by_role: dict[str, dict[str, Any]] = {}
        for response_binding in response_fact["roles"]:
            if (
                not isinstance(response_binding, dict)
                or not isinstance(response_binding.get("role"), str)
                or response_binding["role"] not in allowed_order
                or response_binding["role"] in bindings_by_role
            ):
                raise Gate3RoleLabelingError("gate3_role_binding_not_allowed")
            role = response_binding["role"]
            status = response_binding.get("status")
            if status == "missing":
                if set(response_binding) != {"role", "status"}:
                    raise Gate3RoleLabelingError("gate3_role_binding_invalid")
                restored = {"role": role, "status": "missing"}
            elif status == "bound":
                if set(response_binding) not in (
                    {"role", "status", "target_alias"},
                    {"role", "status", "target_alias", "exact_text"},
                ):
                    raise Gate3RoleLabelingError("gate3_role_binding_invalid")
                try:
                    target_alias = response_binding.get("target_alias")
                    if (
                        not gate3_target_alias_is_valid(target_alias)
                        or target_alias not in target_by_alias
                    ):
                        raise Gate3RoleLabelingError(
                            "gate3_role_target_alias_unknown"
                        )
                    if target_alias not in allowed_aliases_by_fact.get(
                        response_fact["fact_alias"], []
                    ):
                        raise Gate3RoleLabelingError(
                            "gate3_role_target_outside_fact_context"
                        )
                    restored = {
                        "role": role,
                        "status": "bound",
                        "target": copy.deepcopy(target_by_alias[target_alias]),
                    }
                    if "exact_text" in response_binding:
                        restored["exact_text"] = response_binding["exact_text"]
                    resolver.resolve(restored)
                except Gate3RoleLabelingError as exc:
                    if exc.code not in _LOCAL_ROLE_REJECTION_CODES:
                        raise
                    rejected_role_bindings.append(
                        {
                            "fact_alias": response_fact["fact_alias"],
                            "financial_label": response_fact["financial_label"],
                            "role": role,
                            "error_code": exc.code,
                        }
                    )
                    restored = {"role": role, "status": "missing"}
            else:
                raise Gate3RoleLabelingError("gate3_role_binding_invalid")
            bindings_by_role[role] = restored
        if set(bindings_by_role) != set(allowed_order):
            raise Gate3RoleLabelingError("gate3_role_cardinality_invalid")
        annotations.append(
            {
                "target": copy.deepcopy(expected["target"]),
                "financial_label": expected["financial_label"],
                "roles": [
                    copy.deepcopy(bindings_by_role[role]) for role in allowed_order
                ],
            }
        )
    return (
        _build_v2_output(
            pass1_output=pass1_output,
            role_pack=role_pack,
            annotations=annotations,
        ),
        rejected_role_bindings,
    )


def _build_role_provenance(
    *,
    role_context: dict[str, Any],
    facts: list[dict[str, Any]],
    validated_output: dict[str, Any] | None,
    resolver: Gate3RoleValueResolver,
) -> dict[str, Any]:
    annotations = (
        list(validated_output.get("annotations") or [])
        if isinstance(validated_output, dict)
        else []
    )
    provenance_facts: list[dict[str, Any]] = []
    for fact_index, fact in enumerate(facts):
        annotation = annotations[fact_index] if fact_index < len(annotations) else None
        alias = str(fact["fact_target_alias"])
        accepted_target = fact["target"]
        accepted_row = _canonical_row_identity(accepted_target)
        roles: list[dict[str, Any]] = []
        for binding in (annotation or {}).get("roles") or []:
            if binding.get("status") == "missing":
                roles.append({"role": binding.get("role"), "status": "missing"})
                continue
            literal = resolver.resolve(binding)
            if literal is None:
                raise Gate3RoleLabelingError("gate3_role_provenance_literal_invalid")
            literal_sha256 = hashlib.sha256(literal.encode("utf-8")).hexdigest()
            role_target = binding["target"]
            role_row = _canonical_row_identity(role_target)
            if accepted_row is not None and role_row != accepted_row:
                raise Gate3RoleLabelingError("gate3_role_binding_outside_accepted_row")
            roles.append(
                {
                    "role": binding.get("role"),
                    "status": "bound",
                    "literal_sha256": literal_sha256,
                    "canonical_literal_validated": True,
                    "canonical_target": copy.deepcopy(role_target),
                    "canonical_target_sha256": hashlib.sha256(
                        _stable_json(role_target).encode("utf-8")
                    ).hexdigest(),
                    "accepted_target_relation": (
                        "same_canonical_table_row"
                        if accepted_row is not None
                        else "inside_exact_accepted_canonical_region"
                    ),
                }
            )
        row_status = (
            "unique_exact_canonical_row"
            if accepted_row is not None
            else "accepted_canonical_region_only"
        )
        provenance_facts.append(
            {
                "fact_alias": fact["fact_alias"],
                "financial_label": fact["financial_label"],
                "accepted_target_alias": alias,
                "canonical_target": copy.deepcopy(accepted_target),
                "canonical_target_sha256": hashlib.sha256(
                    _stable_json(accepted_target).encode("utf-8")
                ).hexdigest(),
                "row_binding_status": row_status,
                "canonical_row_identity": copy.deepcopy(accepted_row),
                "roles": roles,
            }
        )
    return {
        "schema_version": "broker_reports_gate3_role_provenance_v1",
        "role_context_id": role_context["context_id"],
        "facts": provenance_facts,
        "contains_source_literals": False,
    }


def _canonical_row_identity(target: Any) -> dict[str, Any] | None:
    if not isinstance(target, dict) or target.get("kind") not in {
        "table_row",
        "table_cell",
    }:
        return None
    return {
        "node_id": target.get("node_id"),
        "row": target.get("row"),
    }


def _build_v2_output(
    *,
    pass1_output: dict[str, Any],
    role_pack: dict[str, Any],
    annotations: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": FINANCIAL_ANNOTATIONS_V2_SCHEMA_VERSION,
        "canonical_binding": copy.deepcopy(pass1_output["canonical_binding"]),
        "dictionary_identity": copy.deepcopy(pass1_output["dictionary_identity"]),
        "role_pack_identity": {
            "role_pack_id": role_pack["role_pack_id"],
            "semantic_version": role_pack["semantic_version"],
        },
        "instruction_identity": copy.deepcopy(pass1_output["instruction_identity"]),
        "role_instruction_identity": {
            "instruction_id": GATE3_ROLE_LABELING_INSTRUCTION_ID,
            "semantic_version": GATE3_ROLE_LABELING_INSTRUCTION_VERSION,
        },
        "model_identity": copy.deepcopy(pass1_output["model_identity"]),
        "annotations": copy.deepcopy(annotations),
        "validation_status": "validated",
    }


def _decode_response(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return copy.deepcopy(value)
    if not isinstance(value, str):
        raise Gate3RoleLabelingError("gate3_role_response_contract_invalid")
    try:
        decoded = json.loads(
            value,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_json_constant,
        )
    except (ValueError, json.JSONDecodeError) as exc:
        raise Gate3RoleLabelingError("gate3_role_response_contract_invalid") from exc
    if not isinstance(decoded, dict):
        raise Gate3RoleLabelingError("gate3_role_response_contract_invalid")
    return decoded


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateJsonKeyError(key)
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise ValueError(value)


def _source_scalar_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (str, int, float)):
        return str(value)
    raise Gate3RoleLabelingError("gate3_role_target_text_invalid")


def _cell_source_text(cell: dict[str, Any]) -> str:
    for field_name in ("displayed_value", "cached_value", "value", "raw_value"):
        if cell.get(field_name) is not None:
            return _source_scalar_text(cell[field_name])
    return ""


def _stable_json(value: Any) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise Gate3RoleLabelingError("gate3_role_contract_invalid") from exc


def _metrics(
    *,
    chunk: dict[str, Any],
    role_context: dict[str, Any],
    facts: list[dict[str, Any]],
    role_pack_markdown: str,
    final_provider_request: dict[str, Any] | None,
    raw_provider_response: dict[str, Any] | None,
    raw_model_output: Any,
    validated_output: dict[str, Any] | None,
    role_pack: dict[str, Any],
    rejected_role_bindings: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    provider_called: bool,
) -> dict[str, Any]:
    request_json = (
        json.dumps(
            final_provider_request,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        if final_provider_request is not None
        else ""
    )
    raw_json = (
        raw_model_output
        if isinstance(raw_model_output, str)
        else json.dumps(
            raw_model_output,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        if raw_model_output is not None
        else ""
    )
    required_by_label = {
        profile["financial_label"]: set(profile["required_roles"])
        for profile in role_pack["profiles"]
    }
    validated_annotations = (
        list(validated_output["annotations"]) if validated_output is not None else []
    )
    facts_role_incomplete = sum(
        any(
            role["role"] in required_by_label[annotation["financial_label"]]
            and role["status"] == "missing"
            for role in annotation["roles"]
        )
        for annotation in validated_annotations
    )
    rejected_fact_aliases = {
        item["fact_alias"] for item in rejected_role_bindings
    }
    return {
        "chunk_chars": len(chunk["model_view"]["content"]),
        "role_context_chars": len(role_context["model_view"]["content"]),
        "role_context_targets": len(role_context["target_mappings"]),
        "role_context_excluded_chunk_targets": role_context["metrics"][
            "excluded_chunk_targets_total"
        ],
        "facts_total": len(facts),
        "role_pack_chars": len(role_pack_markdown),
        "role_pack_bytes": len(role_pack_markdown.encode("utf-8")),
        "provider_called": provider_called,
        "final_model_input_chars": len(request_json),
        "raw_model_output_chars": len(raw_json),
        **_safe_raw_response_diagnostics(
            final_provider_request=final_provider_request,
            raw_provider_response=raw_provider_response,
            raw_model_output=raw_model_output,
        ),
        "annotations_validated": (
            len(validated_output["annotations"]) if validated_output is not None else 0
        ),
        "facts_role_complete": len(validated_annotations) - facts_role_incomplete,
        "facts_role_incomplete": facts_role_incomplete,
        "facts_incomplete_due_to_role_rejection": len(rejected_fact_aliases),
        "role_bindings_rejected": len(rejected_role_bindings),
    }


def _safe_raw_response_diagnostics(
    *,
    final_provider_request: dict[str, Any] | None,
    raw_provider_response: dict[str, Any] | None,
    raw_model_output: Any,
) -> dict[str, Any]:
    if raw_model_output is None:
        output_kind = "none"
        decoded = None
        json_decodable = False
    elif isinstance(raw_model_output, dict):
        output_kind = "object"
        decoded = raw_model_output
        json_decodable = True
    elif isinstance(raw_model_output, str):
        output_kind = "string"
        try:
            decoded = json.loads(raw_model_output)
            json_decodable = True
        except (ValueError, json.JSONDecodeError):
            decoded = None
            json_decodable = False
    else:
        output_kind = "other"
        decoded = None
        json_decodable = False

    facts = decoded.get("facts") if isinstance(decoded, dict) else None
    facts_list = isinstance(facts, list)
    fact_shape_match = facts_list and all(
        isinstance(fact, dict)
        and set(fact) == {"fact_alias", "financial_label", "roles"}
        and isinstance(fact.get("roles"), list)
        for fact in facts
    )
    finish_reason = "unknown"
    if isinstance(raw_provider_response, dict):
        choices = raw_provider_response.get("choices")
        if isinstance(choices, list) and choices and isinstance(choices[0], dict):
            candidate = choices[0].get("finish_reason")
            if candidate in {"stop", "length", "content_filter", "tool_calls"}:
                finish_reason = candidate
            elif candidate is not None:
                finish_reason = "other"
    requested_max_tokens = (
        final_provider_request.get("max_tokens")
        if isinstance(final_provider_request, dict)
        and isinstance(final_provider_request.get("max_tokens"), int)
        else None
    )
    return {
        "raw_output_kind": output_kind,
        "raw_output_json_decodable": json_decodable,
        "raw_output_top_level_contract_match": (
            isinstance(decoded, dict) and set(decoded) == {"schema_version", "facts"}
        ),
        "raw_output_schema_version_match": (
            isinstance(decoded, dict)
            and decoded.get("schema_version")
            == GATE3_ROLE_LABELING_RESPONSE_SCHEMA_VERSION
        ),
        "raw_output_facts_list": facts_list,
        "raw_output_facts_total": len(facts) if facts_list else None,
        "raw_output_fact_shape_contract_match": fact_shape_match,
        "provider_finish_reason": finish_reason,
        "requested_max_tokens": requested_max_tokens,
    }


__all__ = [
    "FACTORY_REQUIRED",
    "FORBIDDEN",
    "FINANCIAL_ANNOTATIONS_V2_SCHEMA_VERSION",
    "GATE3_ROLE_CONTEXT_SCHEMA_VERSION",
    "GATE3_ROLE_LABELING_INSTRUCTION",
    "GATE3_ROLE_LABELING_INSTRUCTION_ID",
    "GATE3_ROLE_LABELING_INSTRUCTION_VERSION",
    "GATE3_ROLE_LABELING_RESPONSE_SCHEMA_SHA256",
    "GATE3_ROLE_LABELING_RESPONSE_SCHEMA_VERSION",
    "Gate3RoleLabelingAttempt",
    "Gate3RoleContextFactory",
    "Gate3RoleLabelingError",
    "Gate3RoleLabelingFactory",
    "Gate3RoleValueResolver",
    "Gate3RoleValueResolverFactory",
]
