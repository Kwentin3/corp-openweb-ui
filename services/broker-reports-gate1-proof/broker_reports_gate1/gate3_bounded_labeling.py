"""Gate 3 source meaning only: label source claims, never tax consequences."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
import hashlib
from importlib import resources
import json
import re
from typing import Any

from .artifact_models import ArtifactAccessContext
from .gate3_financial_label_dictionary import (
    GATE3_DICTIONARY_CURRENT_VERSION,
    Gate3FinancialLabelDictionaryFactory,
)
from .gate3_projection import Gate3ProjectionFactory


GATE3_LABELING_INSTRUCTION_ID = "broker-reports-bounded-semantic-labeling"
GATE3_LABELING_INSTRUCTION_VERSION = "1.0.2"
GATE3_LABELING_INSTRUCTION = (
    "Выбери только уверенно подтверждённые финансовые факты. "
    "Используй только financial_label из переданного словаря и target_alias "
    "из переданного документа. В target_alias верни ровно bare alias: для "
    "[t123] значение поля равно t123. Внутри значения разрешены только t и "
    "цифры; не добавляй скобки, Markdown, префиксы или пояснения. "
    "Каждый annotation описывает одно независимое source assertion. Если "
    "один exact target прямо сообщает несколько разрешённых фактов, верни "
    "отдельный annotation для каждого такого financial_label; не объединяй "
    "и не сверяй detail assertions и aggregate totals. "
    "При неопределённости опускай annotation; "
    "пустой annotations — нормальный результат. Не создавай labels или "
    "canonical refs и не изменяй документ. Верни только объект "
    "Gate3LabelingResponseV1 без пояснений."
)
GATE3_LABELING_RESPONSE_SCHEMA_RESOURCE = "gate3_labeling_response.v1.schema.json"
GATE3_LABELING_RESPONSE_SCHEMA_SHA256 = (
    "59453c7dd4298a7d50f87d6d61be7abb4e5a0573a9b9b366f986407e7263867e"
)
GATE3_LABELING_RESPONSE_SCHEMA_VERSION = "broker_reports_gate3_labeling_response_v1"
FINANCIAL_ANNOTATIONS_SCHEMA_VERSION = "broker_reports_financial_annotations_v1"
GATE3_PREDECLARED_ASSERTION_INSTRUCTION_ID = (
    "broker-reports-predeclared-atomic-assertion-labeling"
)
GATE3_PREDECLARED_ASSERTION_INSTRUCTION_VERSION = "0.1.0"
GATE3_PREDECLARED_ASSERTION_INSTRUCTION = (
    "Код уже объявил все source assertions, которые существуют в этом batch. "
    "Классифицируй каждый assertion_id ровно один раз и в переданном порядке; "
    "не выбирай и не создавай source targets. Используй только смысловые "
    "financial types из переданного словаря. Если конкретный assertion не "
    "подтверждает ни один тип, верни для него только UNMAPPED. Если один exact "
    "source target прямо сообщает несколько независимых фактов из текущего "
    "словаря, перечисли каждый тип ровно один раз. Контекст можно читать, но "
    "классифицировать можно только заранее объявленные assertion_id. Не "
    "извлекай roles или values, не делай вычислений, налоговых выводов, "
    "отношений, исправлений или пояснений. Верни только объект "
    "Gate3PredeclaredAssertionLabelingResponseV1."
)
GATE3_PREDECLARED_ASSERTION_RESPONSE_SCHEMA_RESOURCE = (
    "gate3_predeclared_assertion_labeling_response.v1.schema.json"
)
GATE3_PREDECLARED_ASSERTION_RESPONSE_SCHEMA_SHA256 = (
    "0548347ab9f3707bb9338eca987c9f4de024b2b37ccaabcb8aa5e68a3a1af9bc"
)
GATE3_PREDECLARED_ASSERTION_RESPONSE_SCHEMA_VERSION = (
    "broker_reports_gate3_predeclared_assertion_labeling_response_v1"
)
GATE3_PREDECLARED_ASSERTION_CLASSIFICATION_SCHEMA_VERSION = (
    "broker_reports_gate3_predeclared_assertion_classification_v1"
)

FACTORY_REQUIRED = (
    "Gate3BoundedLabelingFactory.create/create_from_chunk/"
    "prepare_predeclared_assertion_batch/create_from_predeclared_assertions "
    "are the only G3.4 "
    "composition and validation entrypoints; they must use the exact G3.2 "
    "projection or G3.4B chunk, Gate3FinancialLabelDictionaryFactory.create "
    "and the configured provider factory client"
)
FORBIDDEN = (
    "G3.4 must not read source files, build a second projection, infer labels "
    "with code, repair provider output, retry a semantic response, persist annotations, use RAG, "
    "Financial Domain, old Gate 2 labels or activate a product route"
)

_ALIAS = re.compile(r"^t[0-9]{3,}$")


class Gate3BoundedLabelingError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class _DuplicateJsonKeyError(ValueError):
    pass


def gate3_target_alias_is_valid(value: Any) -> bool:
    """Return whether value follows the one backend-owned target alias grammar."""

    return isinstance(value, str) and _ALIAS.fullmatch(value) is not None


@dataclass(frozen=True)
class Gate3BoundedLabelingAttempt:
    projection: dict[str, Any] = field(repr=False)
    dictionary: dict[str, Any] = field(repr=False)
    dictionary_managed_binding: dict[str, Any] = field(repr=False)
    dictionary_markdown: str = field(repr=False)
    instruction: str = field(repr=False)
    model_visible_request: dict[str, Any] = field(repr=False)
    final_provider_request: dict[str, Any] = field(repr=False)
    raw_provider_response: dict[str, Any] = field(repr=False)
    raw_model_output: Any = field(repr=False)
    validated_output: dict[str, Any] | None = field(repr=False)
    validation_status: str
    validation_error_code: str | None
    execution_metadata: Any
    operational_retry_receipt: dict[str, Any] | None
    metrics: dict[str, Any]


@dataclass(frozen=True)
class Gate3PredeclaredAssertionLabelingAttempt:
    projection: dict[str, Any] = field(repr=False)
    assertion_envelope: dict[str, Any] = field(repr=False)
    dictionary: dict[str, Any] = field(repr=False)
    dictionary_managed_binding: dict[str, Any] = field(repr=False)
    dictionary_markdown: str = field(repr=False)
    instruction: str = field(repr=False)
    model_visible_request: dict[str, Any] = field(repr=False)
    final_provider_request: dict[str, Any] = field(repr=False)
    raw_provider_response: dict[str, Any] = field(repr=False)
    raw_model_output: Any = field(repr=False)
    validated_output: dict[str, Any] | None = field(repr=False)
    validation_status: str
    validation_error_code: str | None
    execution_metadata: Any
    operational_retry_receipt: dict[str, Any] | None
    metrics: dict[str, Any]


class Gate3BoundedLabelingFactory:
    """Run one sparse provider proposal and restore only validated aliases."""

    def __init__(
        self,
        *,
        store: Any,
        read_enabled: bool,
        model_client: Any,
        model_id: str,
        dictionary_version: str = GATE3_DICTIONARY_CURRENT_VERSION,
    ) -> None:
        self._store = store
        self._read_enabled = read_enabled
        self._model_client = model_client
        self._model_id = model_id
        self._dictionary_version = dictionary_version

    async def create(
        self,
        *,
        document_id: str,
        context: ArtifactAccessContext,
    ) -> Gate3BoundedLabelingAttempt:
        projection = Gate3ProjectionFactory(
            store=self._store,
            read_enabled=self._read_enabled,
        ).create(document_id=document_id, context=context)
        return await self._create_from_projection(projection=projection)

    async def create_from_chunk(
        self,
        *,
        chunk: dict[str, Any],
        requested_financial_labels: tuple[str, ...] | None = None,
    ) -> Gate3BoundedLabelingAttempt:
        """Run the same one-attempt route over one exact G3.4B chunk."""

        return await self._create_from_projection(
            projection=_projection_from_structural_chunk(chunk),
            requested_financial_labels=requested_financial_labels,
        )

    async def create_from_predeclared_assertions(
        self,
        *,
        chunk: dict[str, Any],
    ) -> Gate3PredeclaredAssertionLabelingAttempt:
        """Classify every code-declared row assertion in one exact chunk batch."""

        prepared = self.prepare_predeclared_assertion_batch(chunk=chunk)
        projection = prepared["projection"]
        assertion_envelope = prepared["assertion_envelope"]
        dictionary = prepared["dictionary"]
        dictionary_managed_binding = prepared["dictionary_managed_binding"]
        dictionary_markdown = prepared["dictionary_markdown"]
        response_schema = prepared["response_schema"]
        model_visible_request = prepared["model_visible_request"]
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
            dictionary_markdown=dictionary_markdown,
        )
        raw_model_output = copy.deepcopy(model_result.adapter_extracted_output)
        validation_status = "validated"
        validation_error_code = None
        try:
            validated_output = _validate_predeclared_assertion_response(
                raw_model_output=raw_model_output,
                projection=projection,
                assertion_envelope=assertion_envelope,
                dictionary=dictionary,
                model_id=self._model_id,
            )
        except Gate3BoundedLabelingError as exc:
            validated_output = None
            validation_status = "rejected"
            validation_error_code = exc.code
        metrics = _predeclared_assertion_metrics(
            assertion_envelope=assertion_envelope,
            dictionary_markdown=dictionary_markdown,
            final_provider_request=final_provider_request,
            raw_model_output=raw_model_output,
            validated_output=validated_output,
            execution_metadata=model_result.execution_metadata,
        )
        return Gate3PredeclaredAssertionLabelingAttempt(
            projection=copy.deepcopy(projection),
            assertion_envelope=copy.deepcopy(assertion_envelope),
            dictionary=copy.deepcopy(dictionary),
            dictionary_managed_binding=copy.deepcopy(dictionary_managed_binding),
            dictionary_markdown=dictionary_markdown,
            instruction=GATE3_PREDECLARED_ASSERTION_INSTRUCTION,
            model_visible_request=copy.deepcopy(model_visible_request),
            final_provider_request=final_provider_request,
            raw_provider_response=copy.deepcopy(model_result.raw_provider_response),
            raw_model_output=raw_model_output,
            validated_output=validated_output,
            validation_status=validation_status,
            validation_error_code=validation_error_code,
            execution_metadata=model_result.execution_metadata,
            operational_retry_receipt=copy.deepcopy(
                getattr(model_result, "operational_retry_receipt", None)
            ),
            metrics=metrics,
        )

    def prepare_predeclared_assertion_batch(
        self,
        *,
        chunk: dict[str, Any],
    ) -> dict[str, Any]:
        """Build the exact deterministic candidate request without transport."""

        if not isinstance(self._model_id, str) or not self._model_id.strip():
            raise Gate3BoundedLabelingError("gate3_labeling_model_id_required")
        projection = _projection_from_structural_chunk(chunk)
        assertion_envelope = _predeclared_assertion_envelope(projection)
        dictionary_owner = Gate3FinancialLabelDictionaryFactory.create()
        dictionary = dictionary_owner.load_published(self._dictionary_version)
        dictionary_managed_binding = dictionary_owner.managed_binding(
            self._dictionary_version
        )
        dictionary_markdown = dictionary_owner.render_model_markdown(
            self._dictionary_version
        )
        response_schema = _load_predeclared_assertion_response_schema()
        model_visible_request = _compose_predeclared_assertion_request(
            dictionary=dictionary,
            dictionary_markdown=dictionary_markdown,
            assertion_envelope=assertion_envelope,
            response_schema=response_schema,
        )
        return {
            "projection": copy.deepcopy(projection),
            "assertion_envelope": copy.deepcopy(assertion_envelope),
            "dictionary": copy.deepcopy(dictionary),
            "dictionary_managed_binding": copy.deepcopy(
                dictionary_managed_binding
            ),
            "dictionary_markdown": dictionary_markdown,
            "response_schema": copy.deepcopy(response_schema),
            "model_visible_request": copy.deepcopy(model_visible_request),
        }

    async def _create_from_projection(
        self,
        *,
        projection: dict[str, Any],
        requested_financial_labels: tuple[str, ...] | None = None,
    ) -> Gate3BoundedLabelingAttempt:
        if not isinstance(self._model_id, str) or not self._model_id.strip():
            raise Gate3BoundedLabelingError("gate3_labeling_model_id_required")
        dictionary_owner = Gate3FinancialLabelDictionaryFactory.create()
        dictionary = dictionary_owner.load_published(self._dictionary_version)
        dictionary_managed_binding = dictionary_owner.managed_binding(
            self._dictionary_version
        )
        dictionary_markdown = dictionary_owner.render_model_markdown(
            self._dictionary_version
        )
        demand_labels = _validated_demand_labels(
            requested_financial_labels,
            dictionary=dictionary,
        )
        response_schema = _load_response_schema()
        model_visible_request = _compose_model_visible_request(
            dictionary=dictionary,
            dictionary_markdown=dictionary_markdown,
            projection=projection,
            response_schema=response_schema,
            demand_labels=demand_labels,
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
            dictionary_markdown=dictionary_markdown,
        )
        raw_model_output = copy.deepcopy(model_result.adapter_extracted_output)
        validation_status = "validated"
        validation_error_code = None
        try:
            validated_output = _validate_and_restore(
                raw_model_output=raw_model_output,
                projection=projection,
                dictionary=dictionary,
                model_id=self._model_id,
            )
        except Gate3BoundedLabelingError as exc:
            validated_output = None
            validation_status = "rejected"
            validation_error_code = exc.code
        metrics = _metrics(
            projection=projection,
            dictionary_markdown=dictionary_markdown,
            final_provider_request=final_provider_request,
            raw_model_output=raw_model_output,
            validated_output=validated_output,
            execution_metadata=model_result.execution_metadata,
        )
        return Gate3BoundedLabelingAttempt(
            projection=copy.deepcopy(projection),
            dictionary=copy.deepcopy(dictionary),
            dictionary_managed_binding=copy.deepcopy(dictionary_managed_binding),
            dictionary_markdown=dictionary_markdown,
            instruction=GATE3_LABELING_INSTRUCTION,
            model_visible_request=copy.deepcopy(model_visible_request),
            final_provider_request=final_provider_request,
            raw_provider_response=copy.deepcopy(model_result.raw_provider_response),
            raw_model_output=raw_model_output,
            validated_output=validated_output,
            validation_status=validation_status,
            validation_error_code=validation_error_code,
            execution_metadata=model_result.execution_metadata,
            operational_retry_receipt=copy.deepcopy(
                getattr(model_result, "operational_retry_receipt", None)
            ),
            metrics=metrics,
        )


def _projection_from_structural_chunk(
    chunk: dict[str, Any],
) -> dict[str, Any]:
    required = {
        "chunk_id",
        "ordinal",
        "canonical_binding",
        "structural_kind",
        "structural_scope",
        "context_policy",
        "model_view",
        "target_mappings",
        "metrics",
    }
    if not isinstance(chunk, dict) or set(chunk) != required:
        raise Gate3BoundedLabelingError("gate3_labeling_chunk_invalid")
    binding = chunk.get("canonical_binding")
    model_view = chunk.get("model_view")
    mappings = chunk.get("target_mappings")
    context_policy = chunk.get("context_policy")
    metrics = chunk.get("metrics")
    if (
        not isinstance(chunk.get("chunk_id"), str)
        or not isinstance(chunk.get("ordinal"), int)
        or isinstance(chunk.get("ordinal"), bool)
        or chunk["ordinal"] < 1
        or not isinstance(binding, dict)
        or set(binding) != {"document_id", "canonical_version_id"}
        or not all(isinstance(value, str) and value for value in binding.values())
        or not isinstance(model_view, dict)
        or set(model_view) != {"media_type", "content"}
        or model_view.get("media_type") != "text/markdown"
        or not isinstance(model_view.get("content"), str)
        or not isinstance(mappings, list)
        or not isinstance(context_policy, dict)
        or context_policy.get("context_only_target_aliases") != 0
        or context_policy.get("data_row_overlap") != 0
        or not isinstance(metrics, dict)
        or metrics.get("model_view_chars") != len(model_view["content"])
        or metrics.get("target_count") != len(mappings)
    ):
        raise Gate3BoundedLabelingError("gate3_labeling_chunk_invalid")
    aliases = [
        mapping.get("target_alias") for mapping in mappings if isinstance(mapping, dict)
    ]
    if (
        len(aliases) != len(mappings)
        or any(not isinstance(alias, str) for alias in aliases)
        or len(aliases) != len(set(aliases))
        or re.findall(r"(?<!\\)\[(t[0-9]{3,})\]", model_view["content"]) != aliases
    ):
        raise Gate3BoundedLabelingError("gate3_labeling_chunk_invalid")
    return {
        "schema_version": "broker_reports_gate3_projection_v1",
        "canonical_binding": copy.deepcopy(binding),
        "model_view": copy.deepcopy(model_view),
        "target_mappings": copy.deepcopy(mappings),
    }


def _load_response_schema() -> dict[str, Any]:
    try:
        raw = (
            resources.files(__package__)
            .joinpath(GATE3_LABELING_RESPONSE_SCHEMA_RESOURCE)
            .read_bytes()
        )
    except (FileNotFoundError, OSError) as exc:
        raise Gate3BoundedLabelingError(
            "gate3_labeling_response_schema_unavailable"
        ) from exc
    if hashlib.sha256(raw).hexdigest() != GATE3_LABELING_RESPONSE_SCHEMA_SHA256:
        raise Gate3BoundedLabelingError("gate3_labeling_response_schema_hash_mismatch")
    try:
        schema = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Gate3BoundedLabelingError(
            "gate3_labeling_response_schema_invalid"
        ) from exc
    if not isinstance(schema, dict):
        raise Gate3BoundedLabelingError("gate3_labeling_response_schema_invalid")
    return schema


def _load_predeclared_assertion_response_schema() -> dict[str, Any]:
    try:
        raw = (
            resources.files(__package__)
            .joinpath(GATE3_PREDECLARED_ASSERTION_RESPONSE_SCHEMA_RESOURCE)
            .read_bytes()
        )
    except (FileNotFoundError, OSError) as exc:
        raise Gate3BoundedLabelingError(
            "gate3_predeclared_assertion_response_schema_unavailable"
        ) from exc
    if (
        hashlib.sha256(raw).hexdigest()
        != GATE3_PREDECLARED_ASSERTION_RESPONSE_SCHEMA_SHA256
    ):
        raise Gate3BoundedLabelingError(
            "gate3_predeclared_assertion_response_schema_hash_mismatch"
        )
    try:
        schema = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Gate3BoundedLabelingError(
            "gate3_predeclared_assertion_response_schema_invalid"
        ) from exc
    if not isinstance(schema, dict):
        raise Gate3BoundedLabelingError(
            "gate3_predeclared_assertion_response_schema_invalid"
        )
    return schema


def _predeclared_assertion_envelope(
    projection: dict[str, Any],
) -> dict[str, Any]:
    content = str(projection["model_view"]["content"])
    lines = content.splitlines()
    row_mappings = [
        mapping
        for mapping in projection["target_mappings"]
        if mapping["canonical_target"].get("kind") == "table_row"
    ]
    if not row_mappings:
        raise Gate3BoundedLabelingError(
            "gate3_predeclared_assertion_rows_required"
        )
    row_aliases = [mapping["target_alias"] for mapping in row_mappings]
    row_alias_set = set(row_aliases)
    local_line_by_alias: dict[str, str] = {}
    shared_lines: list[str] = []
    for line in lines:
        visible = re.findall(r"(?<!\\)\[(t[0-9]{3,})\]", line)
        declared_rows = [alias for alias in visible if alias in row_alias_set]
        if len(declared_rows) > 1:
            raise Gate3BoundedLabelingError(
                "gate3_predeclared_assertion_local_text_ambiguous"
            )
        if declared_rows:
            alias = declared_rows[0]
            if alias in local_line_by_alias:
                raise Gate3BoundedLabelingError(
                    "gate3_predeclared_assertion_local_text_ambiguous"
                )
            local_line_by_alias[alias] = line
        else:
            shared_lines.append(line)
    if set(local_line_by_alias) != row_alias_set:
        raise Gate3BoundedLabelingError(
            "gate3_predeclared_assertion_local_text_missing"
        )
    assertions = [
        {
            "assertion_id": alias,
            "source_target_ref": alias,
            "local_source_text": local_line_by_alias[alias],
        }
        for alias in row_aliases
    ]
    return {
        "schema_version": "broker_reports_gate3_predeclared_assertion_batch_v1",
        "shared_structural_context": "\n".join(shared_lines).strip(),
        "assertions": assertions,
    }


def _compose_predeclared_assertion_request(
    *,
    dictionary: dict[str, Any],
    dictionary_markdown: str,
    assertion_envelope: dict[str, Any],
    response_schema: dict[str, Any],
) -> dict[str, Any]:
    label_ids = [str(item.get("label_id") or "") for item in dictionary["labels"]]
    if (
        any(
            label_id in GATE3_PREDECLARED_ASSERTION_INSTRUCTION
            for label_id in label_ids
        )
        or not dictionary_markdown
        or dictionary_markdown.count("# Financial labels") != 1
        or assertion_envelope.get("schema_version")
        != "broker_reports_gate3_predeclared_assertion_batch_v1"
        or not isinstance(assertion_envelope.get("assertions"), list)
        or not assertion_envelope["assertions"]
    ):
        raise Gate3BoundedLabelingError(
            "gate3_predeclared_assertion_context_invalid"
        )
    assertion_content = json.dumps(
        assertion_envelope,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    request = {
        "messages": [
            {"role": "system", "content": GATE3_PREDECLARED_ASSERTION_INSTRUCTION},
            {"role": "user", "content": dictionary_markdown},
            {"role": "user", "content": assertion_content},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": GATE3_PREDECLARED_ASSERTION_RESPONSE_SCHEMA_VERSION,
                "strict": True,
                "schema": copy.deepcopy(response_schema),
            },
        },
    }
    contents = [item["content"] for item in request["messages"]]
    if sum(content.count(dictionary_markdown) for content in contents) != 1:
        raise Gate3BoundedLabelingError(
            "gate3_labeling_dictionary_injection_count_invalid"
        )
    return request


def _compose_model_visible_request(
    *,
    dictionary: dict[str, Any],
    dictionary_markdown: str,
    projection: dict[str, Any],
    response_schema: dict[str, Any],
    demand_labels: tuple[str, ...],
) -> dict[str, Any]:
    label_ids = [str(item.get("label_id") or "") for item in dictionary["labels"]]
    if (
        any(label_id in GATE3_LABELING_INSTRUCTION for label_id in label_ids)
        or not dictionary_markdown
        or dictionary_markdown.count("# Financial labels") != 1
        or projection.get("schema_version") != "broker_reports_gate3_projection_v1"
        or set(projection)
        != {
            "schema_version",
            "canonical_binding",
            "model_view",
            "target_mappings",
        }
        or (projection.get("model_view") or {}).get("media_type") != "text/markdown"
        or not isinstance((projection.get("model_view") or {}).get("content"), str)
    ):
        raise Gate3BoundedLabelingError("gate3_labeling_context_invalid")
    demand_context = ""
    if demand_labels:
        demand_context = (
            "# Active consumer evidence demand\n"
            "Prioritize checking the supplied targets for these existing "
            "published financial labels: "
            + ", ".join(demand_labels)
            + ". This request does not assert that any such fact exists. "
            "Keep the same dictionary, omission policy and response schema.\n\n"
        )
    messages = [
        {"role": "system", "content": GATE3_LABELING_INSTRUCTION},
        {"role": "user", "content": dictionary_markdown},
        {
            "role": "user",
            "content": demand_context + projection["model_view"]["content"],
        },
    ]
    request = {
        "messages": messages,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": GATE3_LABELING_RESPONSE_SCHEMA_VERSION,
                "strict": True,
                "schema": copy.deepcopy(response_schema),
            },
        },
    }
    contents = [item["content"] for item in request["messages"]]
    if sum(content.count(dictionary_markdown) for content in contents) != 1:
        raise Gate3BoundedLabelingError(
            "gate3_labeling_dictionary_injection_count_invalid"
        )
    return request


def _validated_demand_labels(
    value: tuple[str, ...] | None,
    *,
    dictionary: dict[str, Any],
) -> tuple[str, ...]:
    if value is None:
        return ()
    labels = tuple(value)
    published = {item["label_id"] for item in dictionary["labels"]}
    if (
        not labels
        or labels != tuple(sorted(set(labels)))
        or any(not isinstance(item, str) or item not in published for item in labels)
    ):
        raise Gate3BoundedLabelingError("gate3_labeling_demand_labels_invalid")
    return labels


def _audit_final_provider_request(
    *,
    final_provider_request: dict[str, Any],
    model_visible_request: dict[str, Any],
    model_id: str,
    dictionary_markdown: str,
) -> None:
    if not isinstance(final_provider_request, dict):
        raise Gate3BoundedLabelingError("gate3_labeling_model_input_audit_failed")
    messages = final_provider_request.get("messages")
    system = final_provider_request.get("system")
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
    expected_parts = [item["content"] for item in model_visible_request["messages"]]
    if (
        final_provider_request.get("model") != model_id
        or parts != expected_parts
        or sum(part.count(dictionary_markdown) for part in parts) != 1
        or "metadata" in final_provider_request
    ):
        raise Gate3BoundedLabelingError("gate3_labeling_model_input_audit_failed")


def _validate_and_restore(
    *,
    raw_model_output: Any,
    projection: dict[str, Any],
    dictionary: dict[str, Any],
    model_id: str,
) -> dict[str, Any]:
    response = _decode_response(raw_model_output)
    if (
        set(response) != {"schema_version", "annotations"}
        or response.get("schema_version") != GATE3_LABELING_RESPONSE_SCHEMA_VERSION
        or not isinstance(response.get("annotations"), list)
    ):
        raise Gate3BoundedLabelingError("gate3_labeling_response_contract_invalid")
    mappings = projection.get("target_mappings")
    if not isinstance(mappings, list):
        raise Gate3BoundedLabelingError("gate3_labeling_projection_mapping_invalid")
    mapping_by_alias: dict[str, dict[str, Any]] = {}
    for mapping in mappings:
        if (
            not isinstance(mapping, dict)
            or set(mapping) != {"target_alias", "canonical_target"}
            or not isinstance(mapping.get("target_alias"), str)
            or not isinstance(mapping.get("canonical_target"), dict)
            or mapping["target_alias"] in mapping_by_alias
        ):
            raise Gate3BoundedLabelingError("gate3_labeling_projection_mapping_invalid")
        mapping_by_alias[mapping["target_alias"]] = mapping["canonical_target"]
    known_labels = {str(label.get("label_id") or "") for label in dictionary["labels"]}
    restored: list[dict[str, Any]] = []
    seen_pairs: set[tuple[str, str]] = set()
    for annotation in response["annotations"]:
        if not isinstance(annotation, dict) or set(annotation) != {
            "target_alias",
            "financial_label",
        }:
            raise Gate3BoundedLabelingError("gate3_labeling_response_contract_invalid")
        alias = annotation.get("target_alias")
        label = annotation.get("financial_label")
        if not gate3_target_alias_is_valid(alias):
            raise Gate3BoundedLabelingError("gate3_labeling_response_contract_invalid")
        if not isinstance(label, str):
            raise Gate3BoundedLabelingError("gate3_labeling_response_contract_invalid")
        if alias not in mapping_by_alias:
            raise Gate3BoundedLabelingError("gate3_labeling_alias_unknown")
        if label not in known_labels:
            raise Gate3BoundedLabelingError("gate3_labeling_label_unknown")
        pair = (alias, label)
        if pair in seen_pairs:
            raise Gate3BoundedLabelingError("gate3_labeling_annotation_duplicate")
        seen_pairs.add(pair)
        restored.append(
            {
                "target": copy.deepcopy(mapping_by_alias[alias]),
                "financial_label": label,
            }
        )
    return {
        "schema_version": FINANCIAL_ANNOTATIONS_SCHEMA_VERSION,
        "canonical_binding": copy.deepcopy(projection["canonical_binding"]),
        "dictionary_identity": {
            "dictionary_id": dictionary["dictionary_id"],
            "semantic_version": dictionary["semantic_version"],
        },
        "instruction_identity": {
            "instruction_id": GATE3_LABELING_INSTRUCTION_ID,
            "semantic_version": GATE3_LABELING_INSTRUCTION_VERSION,
        },
        "model_identity": {"model_id": model_id},
        "annotations": restored,
        "validation_status": "validated",
    }


def _validate_predeclared_assertion_response(
    *,
    raw_model_output: Any,
    projection: dict[str, Any],
    assertion_envelope: dict[str, Any],
    dictionary: dict[str, Any],
    model_id: str,
) -> dict[str, Any]:
    response = _decode_response(raw_model_output)
    if (
        set(response) != {"schema_version", "classifications"}
        or response.get("schema_version")
        != GATE3_PREDECLARED_ASSERTION_RESPONSE_SCHEMA_VERSION
        or not isinstance(response.get("classifications"), list)
    ):
        raise Gate3BoundedLabelingError(
            "gate3_predeclared_assertion_response_contract_invalid"
        )
    assertions = assertion_envelope["assertions"]
    expected_ids = [item["assertion_id"] for item in assertions]
    classifications = response["classifications"]
    if len(classifications) != len(expected_ids):
        raise Gate3BoundedLabelingError(
            "gate3_predeclared_assertion_coverage_invalid"
        )
    mapping_by_alias = {
        mapping["target_alias"]: mapping["canonical_target"]
        for mapping in projection["target_mappings"]
    }
    known_labels = {str(label.get("label_id") or "") for label in dictionary["labels"]}
    restored: list[dict[str, Any]] = []
    actual_ids: list[str] = []
    for classification in classifications:
        if not isinstance(classification, dict) or set(classification) != {
            "assertion_id",
            "financial_types",
        }:
            raise Gate3BoundedLabelingError(
                "gate3_predeclared_assertion_response_contract_invalid"
            )
        assertion_id = classification.get("assertion_id")
        financial_types = classification.get("financial_types")
        if (
            not gate3_target_alias_is_valid(assertion_id)
            or not isinstance(financial_types, list)
            or not financial_types
            or any(not isinstance(item, str) for item in financial_types)
            or len(financial_types) != len(set(financial_types))
            or any(
                item != "UNMAPPED" and item not in known_labels
                for item in financial_types
            )
            or ("UNMAPPED" in financial_types and financial_types != ["UNMAPPED"])
        ):
            raise Gate3BoundedLabelingError(
                "gate3_predeclared_assertion_response_contract_invalid"
            )
        actual_ids.append(assertion_id)
        if assertion_id not in mapping_by_alias:
            raise Gate3BoundedLabelingError(
                "gate3_predeclared_assertion_id_unknown"
            )
        restored.append(
            {
                "assertion_id": assertion_id,
                "source_target": copy.deepcopy(mapping_by_alias[assertion_id]),
                "financial_types": list(financial_types),
            }
        )
    if actual_ids != expected_ids:
        if len(actual_ids) != len(set(actual_ids)):
            code = "gate3_predeclared_assertion_id_duplicate"
        elif set(actual_ids) != set(expected_ids):
            code = "gate3_predeclared_assertion_id_unknown"
        else:
            code = "gate3_predeclared_assertion_order_invalid"
        raise Gate3BoundedLabelingError(code)
    return {
        "schema_version": GATE3_PREDECLARED_ASSERTION_CLASSIFICATION_SCHEMA_VERSION,
        "canonical_binding": copy.deepcopy(projection["canonical_binding"]),
        "dictionary_identity": {
            "dictionary_id": dictionary["dictionary_id"],
            "semantic_version": dictionary["semantic_version"],
        },
        "instruction_identity": {
            "instruction_id": GATE3_PREDECLARED_ASSERTION_INSTRUCTION_ID,
            "semantic_version": GATE3_PREDECLARED_ASSERTION_INSTRUCTION_VERSION,
        },
        "model_identity": {"model_id": model_id},
        "classifications": restored,
        "validation_status": "validated",
        "target_discovery_by_model": False,
    }


def _decode_response(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return copy.deepcopy(value)
    if not isinstance(value, str):
        raise Gate3BoundedLabelingError("gate3_labeling_response_contract_invalid")
    try:
        decoded = json.loads(
            value,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_json_constant,
        )
    except (ValueError, json.JSONDecodeError) as exc:
        raise Gate3BoundedLabelingError(
            "gate3_labeling_response_contract_invalid"
        ) from exc
    if not isinstance(decoded, dict):
        raise Gate3BoundedLabelingError("gate3_labeling_response_contract_invalid")
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


def _metrics(
    *,
    projection: dict[str, Any],
    dictionary_markdown: str,
    final_provider_request: dict[str, Any],
    raw_model_output: Any,
    validated_output: dict[str, Any] | None,
    execution_metadata: Any,
) -> dict[str, Any]:
    projection_text = projection["model_view"]["content"]
    final_json = json.dumps(
        final_provider_request,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
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
    )
    return {
        "projection_chars": len(projection_text),
        "projection_bytes": len(projection_text.encode("utf-8")),
        "dictionary_chars": len(dictionary_markdown),
        "dictionary_bytes": len(dictionary_markdown.encode("utf-8")),
        "instruction_chars": len(GATE3_LABELING_INSTRUCTION),
        "instruction_bytes": len(GATE3_LABELING_INSTRUCTION.encode("utf-8")),
        "final_model_input_chars": len(final_json),
        "final_model_input_bytes": len(final_json.encode("utf-8")),
        "raw_model_output_chars": len(raw_json),
        "raw_model_output_bytes": len(raw_json.encode("utf-8")),
        "input_tokens": getattr(execution_metadata, "input_tokens", None),
        "output_tokens": getattr(execution_metadata, "output_tokens", None),
        "total_tokens": getattr(execution_metadata, "total_tokens", None),
        "duration_ms": getattr(execution_metadata, "duration_ms", None),
        "dictionary_injection_count": 1,
        "meaningful_context_parts": 3,
        "annotations_validated": (
            len(validated_output["annotations"]) if validated_output is not None else 0
        ),
    }


def _predeclared_assertion_metrics(
    *,
    assertion_envelope: dict[str, Any],
    dictionary_markdown: str,
    final_provider_request: dict[str, Any],
    raw_model_output: Any,
    validated_output: dict[str, Any] | None,
    execution_metadata: Any,
) -> dict[str, Any]:
    envelope_json = json.dumps(
        assertion_envelope,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    final_json = json.dumps(
        final_provider_request,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
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
    )
    classifications = (
        validated_output["classifications"] if validated_output is not None else []
    )
    return {
        "assertions_predeclared": len(assertion_envelope["assertions"]),
        "assertions_validated": len(classifications),
        "unknown_assertion_ids": 0 if validated_output is not None else None,
        "duplicate_assertion_ids": 0 if validated_output is not None else None,
        "invented_source_objects": 0 if validated_output is not None else None,
        "target_discovery_by_model": False,
        "assertion_envelope_chars": len(envelope_json),
        "assertion_envelope_bytes": len(envelope_json.encode("utf-8")),
        "dictionary_chars": len(dictionary_markdown),
        "dictionary_bytes": len(dictionary_markdown.encode("utf-8")),
        "instruction_chars": len(GATE3_PREDECLARED_ASSERTION_INSTRUCTION),
        "instruction_bytes": len(
            GATE3_PREDECLARED_ASSERTION_INSTRUCTION.encode("utf-8")
        ),
        "final_model_input_chars": len(final_json),
        "final_model_input_bytes": len(final_json.encode("utf-8")),
        "raw_model_output_chars": len(raw_json),
        "raw_model_output_bytes": len(raw_json.encode("utf-8")),
        "input_tokens": getattr(execution_metadata, "input_tokens", None),
        "output_tokens": getattr(execution_metadata, "output_tokens", None),
        "total_tokens": getattr(execution_metadata, "total_tokens", None),
        "duration_ms": getattr(execution_metadata, "duration_ms", None),
        "dictionary_injection_count": 1,
        "meaningful_context_parts": 3,
    }


__all__ = [
    "FACTORY_REQUIRED",
    "FORBIDDEN",
    "GATE3_LABELING_INSTRUCTION",
    "GATE3_LABELING_INSTRUCTION_ID",
    "GATE3_LABELING_INSTRUCTION_VERSION",
    "GATE3_LABELING_RESPONSE_SCHEMA_SHA256",
    "GATE3_PREDECLARED_ASSERTION_INSTRUCTION",
    "GATE3_PREDECLARED_ASSERTION_INSTRUCTION_ID",
    "GATE3_PREDECLARED_ASSERTION_INSTRUCTION_VERSION",
    "GATE3_PREDECLARED_ASSERTION_RESPONSE_SCHEMA_SHA256",
    "Gate3BoundedLabelingAttempt",
    "Gate3BoundedLabelingError",
    "Gate3BoundedLabelingFactory",
    "Gate3PredeclaredAssertionLabelingAttempt",
    "gate3_target_alias_is_valid",
]
