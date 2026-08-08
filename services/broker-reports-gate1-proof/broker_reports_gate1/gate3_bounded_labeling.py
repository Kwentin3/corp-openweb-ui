"""Gate 3 pass 1: document + dictionary + instruction -> validation."""

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
    GATE3_DICTIONARY_V1_VERSION,
    Gate3FinancialLabelDictionaryFactory,
)
from .gate3_projection import Gate3ProjectionFactory


GATE3_LABELING_INSTRUCTION_ID = "broker-reports-bounded-semantic-labeling"
GATE3_LABELING_INSTRUCTION_VERSION = "1.0.1"
GATE3_LABELING_INSTRUCTION = (
    "Выбери только уверенно подтверждённые финансовые факты. "
    "Используй только financial_label из переданного словаря и target_alias "
    "из переданного документа. В target_alias верни ровно bare alias: для "
    "[t123] значение поля равно t123. Внутри значения разрешены только t и "
    "цифры; не добавляй скобки, Markdown, префиксы или пояснения. "
    "При неопределённости опускай annotation; "
    "пустой annotations — нормальный результат. Не создавай labels или "
    "canonical refs и не изменяй документ. Верни только объект "
    "Gate3LabelingResponseV1 без пояснений."
)
GATE3_LABELING_RESPONSE_SCHEMA_RESOURCE = (
    "gate3_labeling_response.v1.schema.json"
)
GATE3_LABELING_RESPONSE_SCHEMA_SHA256 = (
    "59453c7dd4298a7d50f87d6d61be7abb4e5a0573a9b9b366f986407e7263867e"
)
GATE3_LABELING_RESPONSE_SCHEMA_VERSION = (
    "broker_reports_gate3_labeling_response_v1"
)
FINANCIAL_ANNOTATIONS_SCHEMA_VERSION = (
    "broker_reports_financial_annotations_v1"
)

FACTORY_REQUIRED = (
    "Gate3BoundedLabelingFactory.create/create_from_chunk are the only G3.4 "
    "composition and validation entrypoints; they must use the exact G3.2 "
    "projection or G3.4B chunk, Gate3FinancialLabelDictionaryFactory.create "
    "and the configured provider factory client"
)
FORBIDDEN = (
    "G3.4 must not read source files, build a second projection, infer labels "
    "with code, repair provider output, retry, persist annotations, use RAG, "
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
        dictionary_version: str = GATE3_DICTIONARY_V1_VERSION,
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
    ) -> Gate3BoundedLabelingAttempt:
        """Run the same one-attempt route over one exact G3.4B chunk."""

        return await self._create_from_projection(
            projection=_projection_from_structural_chunk(chunk)
        )

    async def _create_from_projection(
        self,
        *,
        projection: dict[str, Any],
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
        response_schema = _load_response_schema()
        model_visible_request = _compose_model_visible_request(
            dictionary=dictionary,
            dictionary_markdown=dictionary_markdown,
            projection=projection,
            response_schema=response_schema,
        )
        model_result = await self._model_client.label_gate3_once(
            model_visible_request=model_visible_request,
            canonical_schema=response_schema,
            model_id=self._model_id,
        )
        final_provider_request = copy.deepcopy(
            model_result.prepared_request.form_data
        )
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
            dictionary_managed_binding=copy.deepcopy(
                dictionary_managed_binding
            ),
            dictionary_markdown=dictionary_markdown,
            instruction=GATE3_LABELING_INSTRUCTION,
            model_visible_request=copy.deepcopy(model_visible_request),
            final_provider_request=final_provider_request,
            raw_provider_response=copy.deepcopy(
                model_result.raw_provider_response
            ),
            raw_model_output=raw_model_output,
            validated_output=validated_output,
            validation_status=validation_status,
            validation_error_code=validation_error_code,
            execution_metadata=model_result.execution_metadata,
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
        mapping.get("target_alias")
        for mapping in mappings
        if isinstance(mapping, dict)
    ]
    if (
        len(aliases) != len(mappings)
        or any(not isinstance(alias, str) for alias in aliases)
        or len(aliases) != len(set(aliases))
        or re.findall(r"(?<!\\)\[(t[0-9]{3,})\]", model_view["content"])
        != aliases
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
        raise Gate3BoundedLabelingError(
            "gate3_labeling_response_schema_hash_mismatch"
        )
    try:
        schema = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Gate3BoundedLabelingError(
            "gate3_labeling_response_schema_invalid"
        ) from exc
    if not isinstance(schema, dict):
        raise Gate3BoundedLabelingError(
            "gate3_labeling_response_schema_invalid"
        )
    return schema


def _compose_model_visible_request(
    *,
    dictionary: dict[str, Any],
    dictionary_markdown: str,
    projection: dict[str, Any],
    response_schema: dict[str, Any],
) -> dict[str, Any]:
    label_ids = [str(item.get("label_id") or "") for item in dictionary["labels"]]
    if (
        any(label_id in GATE3_LABELING_INSTRUCTION for label_id in label_ids)
        or not dictionary_markdown
        or dictionary_markdown.count("# Financial labels") != 1
        or projection.get("schema_version")
        != "broker_reports_gate3_projection_v1"
        or set(projection) != {
            "schema_version",
            "canonical_binding",
            "model_view",
            "target_mappings",
        }
        or (projection.get("model_view") or {}).get("media_type")
        != "text/markdown"
        or not isinstance((projection.get("model_view") or {}).get("content"), str)
    ):
        raise Gate3BoundedLabelingError("gate3_labeling_context_invalid")
    request = {
        "messages": [
            {"role": "system", "content": GATE3_LABELING_INSTRUCTION},
            {"role": "user", "content": dictionary_markdown},
            {
                "role": "user",
                "content": projection["model_view"]["content"],
            },
        ],
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
    expected_parts = [
        item["content"] for item in model_visible_request["messages"]
    ]
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
        raise Gate3BoundedLabelingError(
            "gate3_labeling_response_contract_invalid"
        )
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
            raise Gate3BoundedLabelingError(
                "gate3_labeling_projection_mapping_invalid"
            )
        mapping_by_alias[mapping["target_alias"]] = mapping["canonical_target"]
    known_labels = {
        str(label.get("label_id") or "") for label in dictionary["labels"]
    }
    restored: list[dict[str, Any]] = []
    seen_pairs: set[tuple[str, str]] = set()
    for annotation in response["annotations"]:
        if (
            not isinstance(annotation, dict)
            or set(annotation) != {"target_alias", "financial_label"}
        ):
            raise Gate3BoundedLabelingError(
                "gate3_labeling_response_contract_invalid"
            )
        alias = annotation.get("target_alias")
        label = annotation.get("financial_label")
        if not gate3_target_alias_is_valid(alias):
            raise Gate3BoundedLabelingError(
                "gate3_labeling_response_contract_invalid"
            )
        if not isinstance(label, str):
            raise Gate3BoundedLabelingError(
                "gate3_labeling_response_contract_invalid"
            )
        if alias not in mapping_by_alias:
            raise Gate3BoundedLabelingError("gate3_labeling_alias_unknown")
        if label not in known_labels:
            raise Gate3BoundedLabelingError("gate3_labeling_label_unknown")
        pair = (alias, label)
        if pair in seen_pairs:
            raise Gate3BoundedLabelingError(
                "gate3_labeling_annotation_duplicate"
            )
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


def _decode_response(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return copy.deepcopy(value)
    if not isinstance(value, str):
        raise Gate3BoundedLabelingError(
            "gate3_labeling_response_contract_invalid"
        )
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
        raise Gate3BoundedLabelingError(
            "gate3_labeling_response_contract_invalid"
        )
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
            len(validated_output["annotations"])
            if validated_output is not None
            else 0
        ),
    }


__all__ = [
    "FACTORY_REQUIRED",
    "FORBIDDEN",
    "GATE3_LABELING_INSTRUCTION",
    "GATE3_LABELING_INSTRUCTION_ID",
    "GATE3_LABELING_INSTRUCTION_VERSION",
    "GATE3_LABELING_RESPONSE_SCHEMA_SHA256",
    "Gate3BoundedLabelingAttempt",
    "Gate3BoundedLabelingError",
    "Gate3BoundedLabelingFactory",
    "gate3_target_alias_is_valid",
]
