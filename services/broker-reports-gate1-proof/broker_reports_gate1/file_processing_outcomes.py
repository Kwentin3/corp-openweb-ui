from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Iterable


FILE_PROCESSING_OUTCOME_SCHEMA_VERSION = (
    "broker_reports_file_processing_outcome_v1"
)
FILE_PROCESSING_BATCH_SCHEMA_VERSION = "broker_reports_file_processing_batch_v1"
PRIVATE_PROCESSING_DIAGNOSTIC_SCHEMA_VERSION = (
    "broker_reports_private_processing_diagnostic_v1"
)
FILE_PROCESSING_OUTCOME_VALIDATION_SCHEMA_VERSION = (
    "broker_reports_file_processing_outcome_validation_v1"
)
FILE_PROCESSING_BATCH_VALIDATION_SCHEMA_VERSION = (
    "broker_reports_file_processing_batch_validation_v1"
)
PRIVATE_PROCESSING_DIAGNOSTIC_VALIDATION_SCHEMA_VERSION = (
    "broker_reports_private_processing_diagnostic_validation_v1"
)
FILE_PROCESSING_OUTCOME_POLICY_VERSION = "file_processing_outcome_policy_v1"

FACTORY_REQUIRED = (
    "FileProcessingOutcomeFactory.create is the only production entrypoint for "
    "safe per-file outcomes, private diagnostics, and batch summaries"
)
FORBIDDEN = (
    "Callers must not construct model-facing outcomes from raw exceptions, file paths, "
    "provider payloads, secrets, ad hoc reason codes, or private diagnostics"
)

FILE_OUTCOME_FALLBACK_MESSAGE = (
    "Не удалось определить результат обработки файла. "
    "Повторите попытку или обратитесь к оператору."
)
BATCH_OUTCOME_FALLBACK_MESSAGE = (
    "Не удалось определить общий результат обработки файлов. "
    "Повторите попытку или обратитесь к оператору."
)

_STATUSES = {"success", "partial", "failed"}
_STAGES = {
    "intake",
    "byte_access",
    "container_detection",
    "parsing",
    "document_profiling",
    "table_detection",
    "visual_topology",
    "input_budget",
    "provider_call",
    "oracle_consensus",
    "table_materialization",
    "output_validation",
    "processing",
    "completed",
}
_NEXT_ACTIONS = {
    "none",
    "use_partial_result",
    "retry",
    "retry_later",
    "upload_supported_file",
    "upload_unencrypted_file",
    "upload_clean_copy",
    "reduce_document_scope",
    "manual_review",
    "contact_operator",
    "fix_safe_projection",
}
_FILE_REF_RE = re.compile(
    r"^(?:file|doc|brdoc|document|artifact|upload)_[A-Za-z0-9][A-Za-z0-9._:-]{0,119}$"
)
_REF_RE = re.compile(r"^[a-z]+_[0-9a-f]{24,64}$")
_EXCEPTION_TYPE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]{0,159}$")
_FACTORY_TOKEN = object()


@dataclass(frozen=True)
class FileProcessingOutcomeConfig:
    policy_version: str = FILE_PROCESSING_OUTCOME_POLICY_VERSION
    maximum_batch_files: int = 1000
    maximum_private_text_chars: int = 16_384


@dataclass(frozen=True)
class _ReasonPolicy:
    retryable: bool
    next_action: str
    user_message: str
    stages: frozenset[str]


_REASON_POLICIES: dict[tuple[str, str], _ReasonPolicy] = {
    ("success", "completed"): _ReasonPolicy(
        False,
        "none",
        "Файл успешно обработан.",
        frozenset({"completed"}),
    ),
    ("partial", "partial_result_available"): _ReasonPolicy(
        True,
        "use_partial_result",
        "Файл обработан частично. Доступную часть можно использовать; "
        "остальное требует повторной обработки или проверки.",
        frozenset({"processing", "table_materialization", "output_validation"}),
    ),
    ("failed", "bytes_unavailable"): _ReasonPolicy(
        True,
        "retry",
        "Система не смогла прочитать загруженный файл. Повторите попытку.",
        frozenset({"byte_access"}),
    ),
    ("failed", "unsupported_format"): _ReasonPolicy(
        False,
        "upload_supported_file",
        "Формат файла пока не поддерживается. Загрузите файл в поддерживаемом формате.",
        frozenset({"container_detection"}),
    ),
    ("failed", "encrypted_file"): _ReasonPolicy(
        False,
        "upload_unencrypted_file",
        "Файл защищён шифрованием. Загрузите незашифрованную копию.",
        frozenset({"parsing"}),
    ),
    ("failed", "corrupt_file"): _ReasonPolicy(
        False,
        "upload_clean_copy",
        "Файл повреждён или имеет неверную структуру. Загрузите исправную копию.",
        frozenset({"parsing"}),
    ),
    ("failed", "parser_failed"): _ReasonPolicy(
        True,
        "retry",
        "Не удалось разобрать структуру файла. Повторите попытку или передайте файл на проверку.",
        frozenset({"parsing", "document_profiling", "table_detection"}),
    ),
    ("partial", "atom_budget_exceeded"): _ReasonPolicy(
        True,
        "use_partial_result",
        "Файл обработан частично: одна из таблиц превысила допустимую сложность.",
        frozenset({"visual_topology"}),
    ),
    ("failed", "atom_budget_exceeded"): _ReasonPolicy(
        False,
        "reduce_document_scope",
        "Обработка остановлена: таблица превысила допустимую сложность.",
        frozenset({"visual_topology"}),
    ),
    ("partial", "model_input_budget_exceeded"): _ReasonPolicy(
        True,
        "use_partial_result",
        "Файл обработан частично: одна из частей превысила лимит модели.",
        frozenset({"input_budget"}),
    ),
    ("failed", "model_input_budget_exceeded"): _ReasonPolicy(
        False,
        "reduce_document_scope",
        "Обработка остановлена: файл превысил лимит модели.",
        frozenset({"input_budget"}),
    ),
    ("partial", "provider_temporarily_unavailable"): _ReasonPolicy(
        True,
        "retry_later",
        "Файл обработан частично: сервис модели временно недоступен.",
        frozenset({"provider_call"}),
    ),
    ("failed", "provider_temporarily_unavailable"): _ReasonPolicy(
        True,
        "retry_later",
        "Сервис модели временно недоступен. Повторите попытку позже.",
        frozenset({"provider_call"}),
    ),
    ("partial", "provider_rate_limited"): _ReasonPolicy(
        True,
        "retry_later",
        "Файл обработан частично: сервис модели временно ограничил число запросов.",
        frozenset({"provider_call"}),
    ),
    ("failed", "provider_rate_limited"): _ReasonPolicy(
        True,
        "retry_later",
        "Сервис модели временно ограничил число запросов. Повторите попытку позже.",
        frozenset({"provider_call"}),
    ),
    ("partial", "provider_response_invalid"): _ReasonPolicy(
        True,
        "manual_review",
        "Файл обработан частично: ответ модели не прошёл проверку.",
        frozenset({"provider_call"}),
    ),
    ("failed", "provider_response_invalid"): _ReasonPolicy(
        True,
        "retry",
        "Ответ модели не прошёл проверку. Повторите попытку.",
        frozenset({"provider_call"}),
    ),
    ("partial", "consensus_not_reached"): _ReasonPolicy(
        True,
        "manual_review",
        "Файл обработан частично: две проверки не согласовали структуру одной из таблиц.",
        frozenset({"oracle_consensus"}),
    ),
    ("failed", "consensus_not_reached"): _ReasonPolicy(
        True,
        "manual_review",
        "Две проверки не согласовали структуру таблицы. Результат не опубликован.",
        frozenset({"oracle_consensus"}),
    ),
    ("partial", "table_validation_failed"): _ReasonPolicy(
        True,
        "manual_review",
        "Файл обработан частично: одна из таблиц не прошла итоговую проверку.",
        frozenset({"output_validation"}),
    ),
    ("failed", "table_validation_failed"): _ReasonPolicy(
        True,
        "manual_review",
        "Таблица не прошла итоговую проверку. Результат не опубликован.",
        frozenset({"output_validation"}),
    ),
    ("failed", "privacy_projection_blocked"): _ReasonPolicy(
        False,
        "fix_safe_projection",
        "Публикация результата остановлена защитной проверкой. Данные не опубликованы.",
        frozenset({"output_validation"}),
    ),
    ("failed", "internal_processing_failed"): _ReasonPolicy(
        True,
        "contact_operator",
        "Во время обработки возникла внутренняя ошибка. Повторите попытку; если ошибка повторится, "
        "обратитесь к оператору.",
        frozenset({"processing"}),
    ),
}

_OUTCOME_KEYS = {
    "schema_version",
    "policy_version",
    "outcome_id",
    "outcome_checksum_ref",
    "file_ref",
    "status",
    "stage",
    "reason_code",
    "retryable",
    "next_action",
    "user_message",
    "terminal",
}
_BATCH_KEYS = {
    "schema_version",
    "policy_version",
    "batch_id",
    "batch_checksum_ref",
    "overall_status",
    "files_total",
    "status_counts",
    "outcomes",
    "user_message",
    "terminal",
}
_PRIVATE_DIAGNOSTIC_KEYS = {
    "schema_version",
    "diagnostic_id",
    "diagnostic_checksum_ref",
    "file_ref",
    "stage",
    "exception_type",
    "exception_message",
    "source_path",
    "provider_payload",
    "private_context",
}


class FileProcessingOutcomeError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class PrivateFileProcessingDiagnostic:
    __slots__ = ("_snapshot",)

    def __init__(self, snapshot: dict[str, Any], *, _factory_token: object) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise FileProcessingOutcomeError("file_outcome_factory_required")
        self._snapshot = copy.deepcopy(snapshot)

    def snapshot(self) -> dict[str, Any]:
        return copy.deepcopy(self._snapshot)

    def __repr__(self) -> str:
        return (
            "PrivateFileProcessingDiagnostic("
            f"diagnostic_id={self._snapshot.get('diagnostic_id')!r})"
        )


class FileProcessingOutcomeRecord:
    __slots__ = ("_safe_outcome", "_private_diagnostic")

    def __init__(
        self,
        safe_outcome: dict[str, Any],
        private_diagnostic: PrivateFileProcessingDiagnostic | None,
        *,
        _factory_token: object,
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise FileProcessingOutcomeError("file_outcome_factory_required")
        self._safe_outcome = copy.deepcopy(safe_outcome)
        self._private_diagnostic = private_diagnostic

    @property
    def has_private_diagnostic(self) -> bool:
        return self._private_diagnostic is not None

    def safe_snapshot(self) -> dict[str, Any]:
        return copy.deepcopy(self._safe_outcome)

    def model_context(self) -> dict[str, Any]:
        """Return the only payload permitted to enter an LLM context."""
        return self.safe_snapshot()

    def private_snapshot(self) -> dict[str, Any] | None:
        if self._private_diagnostic is None:
            return None
        return self._private_diagnostic.snapshot()

    def __repr__(self) -> str:
        return (
            "FileProcessingOutcomeRecord("
            f"outcome_id={self._safe_outcome.get('outcome_id')!r}, "
            f"status={self._safe_outcome.get('status')!r})"
        )


class FileProcessingBatchRecord:
    __slots__ = ("_safe_batch",)

    def __init__(self, safe_batch: dict[str, Any], *, _factory_token: object) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise FileProcessingOutcomeError("file_outcome_factory_required")
        self._safe_batch = copy.deepcopy(safe_batch)

    def safe_snapshot(self) -> dict[str, Any]:
        return copy.deepcopy(self._safe_batch)

    def model_context(self) -> dict[str, Any]:
        """Return the safe per-file batch; private diagnostics cannot enter it."""
        return self.safe_snapshot()

    def __repr__(self) -> str:
        return (
            "FileProcessingBatchRecord("
            f"batch_id={self._safe_batch.get('batch_id')!r}, "
            f"overall_status={self._safe_batch.get('overall_status')!r})"
        )


class FileProcessingOutcomeFactory:
    def __init__(self, config: FileProcessingOutcomeConfig | None = None) -> None:
        self.config = config or FileProcessingOutcomeConfig()

    def create(self) -> "_FileProcessingOutcomeService":
        if self.config.policy_version != FILE_PROCESSING_OUTCOME_POLICY_VERSION:
            raise FileProcessingOutcomeError("file_outcome_policy_version_invalid")
        if not _positive_integer(self.config.maximum_batch_files):
            raise FileProcessingOutcomeError("file_outcome_batch_limit_invalid")
        if not _positive_integer(self.config.maximum_private_text_chars):
            raise FileProcessingOutcomeError("file_outcome_private_text_limit_invalid")
        return _FileProcessingOutcomeService(self.config)


class _FileProcessingOutcomeService:
    def __init__(self, config: FileProcessingOutcomeConfig) -> None:
        self.config = config

    def success(self, *, file_ref: str) -> FileProcessingOutcomeRecord:
        return self._terminal(
            file_ref=file_ref,
            status="success",
            stage="completed",
            reason_code="completed",
            private_diagnostic=None,
        )

    def partial(
        self,
        *,
        file_ref: str,
        stage: str,
        reason_code: str,
        private_diagnostic: PrivateFileProcessingDiagnostic | None = None,
    ) -> FileProcessingOutcomeRecord:
        return self._terminal(
            file_ref=file_ref,
            status="partial",
            stage=stage,
            reason_code=reason_code,
            private_diagnostic=private_diagnostic,
        )

    def failed(
        self,
        *,
        file_ref: str,
        stage: str,
        reason_code: str,
        private_diagnostic: PrivateFileProcessingDiagnostic | None = None,
    ) -> FileProcessingOutcomeRecord:
        return self._terminal(
            file_ref=file_ref,
            status="failed",
            stage=stage,
            reason_code=reason_code,
            private_diagnostic=private_diagnostic,
        )

    def private_diagnostic(
        self,
        *,
        file_ref: str,
        stage: str,
        exception: BaseException | None = None,
        source_path: str | None = None,
        provider_payload: Any = None,
        private_context: dict[str, Any] | None = None,
    ) -> PrivateFileProcessingDiagnostic:
        _require_file_ref(file_ref)
        _require_stage(stage)
        exception_type = type(exception).__name__ if exception is not None else None
        exception_message = str(exception) if exception is not None else None
        if exception_type is not None and not _EXCEPTION_TYPE_RE.fullmatch(exception_type):
            exception_type = "Exception"
        source_path_value = _optional_private_text(
            source_path,
            self.config.maximum_private_text_chars,
            "file_outcome_private_source_path_invalid",
        )
        exception_message_value = _optional_private_text(
            exception_message,
            self.config.maximum_private_text_chars,
            "file_outcome_private_exception_message_invalid",
        )
        if private_context is not None and not isinstance(private_context, dict):
            raise FileProcessingOutcomeError("file_outcome_private_context_invalid")
        if not _is_json_value(provider_payload) or not _is_json_value(
            private_context or {}
        ):
            raise FileProcessingOutcomeError("file_outcome_private_payload_invalid")
        core = {
            "schema_version": PRIVATE_PROCESSING_DIAGNOSTIC_SCHEMA_VERSION,
            "file_ref": file_ref,
            "stage": stage,
            "exception_type": exception_type,
            "exception_message": exception_message_value,
            "source_path": source_path_value,
            "provider_payload": copy.deepcopy(provider_payload),
            "private_context": copy.deepcopy(private_context or {}),
        }
        diagnostic = {
            **core,
            "diagnostic_id": _digest_ref("diag", core, length=24),
            "diagnostic_checksum_ref": None,
        }
        diagnostic["diagnostic_checksum_ref"] = _checksum_ref(
            "diagchk", diagnostic, "diagnostic_checksum_ref"
        )
        validation = validate_private_processing_diagnostic(diagnostic)
        if not validation["passed"]:
            raise FileProcessingOutcomeError("file_outcome_private_diagnostic_invalid")
        return PrivateFileProcessingDiagnostic(
            diagnostic,
            _factory_token=_FACTORY_TOKEN,
        )

    def batch(
        self,
        records: Iterable[FileProcessingOutcomeRecord],
    ) -> FileProcessingBatchRecord:
        values = list(records)
        if not values:
            raise FileProcessingOutcomeError("file_outcome_batch_empty")
        if len(values) > self.config.maximum_batch_files:
            raise FileProcessingOutcomeError("file_outcome_batch_limit_exceeded")
        if not all(isinstance(item, FileProcessingOutcomeRecord) for item in values):
            raise FileProcessingOutcomeError("file_outcome_batch_record_invalid")
        outcomes = sorted(
            (item.safe_snapshot() for item in values),
            key=lambda item: item["file_ref"],
        )
        file_refs = [item["file_ref"] for item in outcomes]
        if len(file_refs) != len(set(file_refs)):
            raise FileProcessingOutcomeError("file_outcome_batch_duplicate_file_ref")
        for outcome in outcomes:
            if not validate_file_processing_outcome(outcome)["passed"]:
                raise FileProcessingOutcomeError("file_outcome_batch_outcome_invalid")
        counts = {
            status: sum(item["status"] == status for item in outcomes)
            for status in ("success", "partial", "failed")
        }
        overall_status = _batch_status(counts, len(outcomes))
        message = _batch_message(counts, len(outcomes), overall_status)
        core = {
            "schema_version": FILE_PROCESSING_BATCH_SCHEMA_VERSION,
            "policy_version": self.config.policy_version,
            "overall_status": overall_status,
            "files_total": len(outcomes),
            "status_counts": counts,
            "outcomes": outcomes,
            "user_message": message,
            "terminal": True,
        }
        batch = {
            **core,
            "batch_id": _digest_ref("batch", core, length=24),
            "batch_checksum_ref": None,
        }
        batch["batch_checksum_ref"] = _checksum_ref(
            "batchchk", batch, "batch_checksum_ref"
        )
        validation = validate_file_processing_batch(batch)
        if not validation["passed"]:
            raise FileProcessingOutcomeError("file_outcome_batch_invalid")
        return FileProcessingBatchRecord(batch, _factory_token=_FACTORY_TOKEN)

    def _terminal(
        self,
        *,
        file_ref: str,
        status: str,
        stage: str,
        reason_code: str,
        private_diagnostic: PrivateFileProcessingDiagnostic | None,
    ) -> FileProcessingOutcomeRecord:
        _require_file_ref(file_ref)
        _require_stage(stage)
        policy = _reason_policy(status, reason_code, stage)
        if private_diagnostic is not None:
            if not isinstance(private_diagnostic, PrivateFileProcessingDiagnostic):
                raise FileProcessingOutcomeError(
                    "file_outcome_private_diagnostic_type_invalid"
                )
            private_snapshot = private_diagnostic.snapshot()
            private_validation = validate_private_processing_diagnostic(
                private_snapshot
            )
            if not private_validation["passed"]:
                raise FileProcessingOutcomeError(
                    "file_outcome_private_diagnostic_invalid"
                )
            if (
                private_snapshot["file_ref"] != file_ref
                or private_snapshot["stage"] != stage
            ):
                raise FileProcessingOutcomeError(
                    "file_outcome_private_diagnostic_mismatch"
                )
        if status == "success" and private_diagnostic is not None:
            raise FileProcessingOutcomeError(
                "file_outcome_success_private_diagnostic_forbidden"
            )
        core = {
            "schema_version": FILE_PROCESSING_OUTCOME_SCHEMA_VERSION,
            "policy_version": self.config.policy_version,
            "file_ref": file_ref,
            "status": status,
            "stage": stage,
            "reason_code": reason_code,
            "retryable": policy.retryable,
            "next_action": policy.next_action,
            "user_message": policy.user_message,
            "terminal": True,
        }
        outcome = {
            **core,
            "outcome_id": _digest_ref("outcome", core, length=24),
            "outcome_checksum_ref": None,
        }
        outcome["outcome_checksum_ref"] = _checksum_ref(
            "outcomechk", outcome, "outcome_checksum_ref"
        )
        validation = validate_file_processing_outcome(outcome)
        if not validation["passed"]:
            raise FileProcessingOutcomeError("file_outcome_safe_contract_invalid")
        return FileProcessingOutcomeRecord(
            outcome,
            private_diagnostic,
            _factory_token=_FACTORY_TOKEN,
        )


def validate_file_processing_outcome(value: Any) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(value, dict):
        errors.append("file_outcome_not_object")
        return _validation(
            FILE_PROCESSING_OUTCOME_VALIDATION_SCHEMA_VERSION, errors
        )
    if set(value) != _OUTCOME_KEYS:
        errors.append("file_outcome_shape_invalid")
    if value.get("schema_version") != FILE_PROCESSING_OUTCOME_SCHEMA_VERSION:
        errors.append("file_outcome_schema_version_invalid")
    if value.get("policy_version") != FILE_PROCESSING_OUTCOME_POLICY_VERSION:
        errors.append("file_outcome_policy_version_invalid")
    if not _valid_file_ref(value.get("file_ref")):
        errors.append("file_outcome_file_ref_invalid")
    status = value.get("status")
    stage = value.get("stage")
    reason_code = value.get("reason_code")
    if status not in _STATUSES:
        errors.append("file_outcome_status_invalid")
    if stage not in _STAGES:
        errors.append("file_outcome_stage_invalid")
    policy: _ReasonPolicy | None = None
    if isinstance(status, str) and isinstance(reason_code, str):
        policy = _REASON_POLICIES.get((status, reason_code))
    if policy is None:
        errors.append("file_outcome_reason_code_invalid")
    elif stage not in policy.stages:
        errors.append("file_outcome_reason_stage_invalid")
    else:
        if value.get("retryable") is not policy.retryable:
            errors.append("file_outcome_retryable_invalid")
        if value.get("next_action") != policy.next_action:
            errors.append("file_outcome_next_action_invalid")
        if value.get("user_message") != policy.user_message:
            errors.append("file_outcome_user_message_invalid")
    if value.get("next_action") not in _NEXT_ACTIONS:
        errors.append("file_outcome_next_action_invalid")
    if value.get("terminal") is not True:
        errors.append("file_outcome_not_terminal")
    if not isinstance(value.get("retryable"), bool):
        errors.append("file_outcome_retryable_invalid")
    if not _REF_RE.fullmatch(str(value.get("outcome_id") or "")):
        errors.append("file_outcome_id_invalid")
    else:
        expected_id = _try_digest_ref(
            "outcome",
            {key: value.get(key) for key in _OUTCOME_KEYS if key not in {
                "outcome_id",
                "outcome_checksum_ref",
            }},
            length=24,
        )
        if value.get("outcome_id") != expected_id:
            errors.append("file_outcome_id_mismatch")
    expected_checksum = _try_checksum_ref(
        "outcomechk", value, "outcome_checksum_ref"
    )
    if value.get("outcome_checksum_ref") != expected_checksum:
        errors.append("file_outcome_checksum_mismatch")
    return _validation(FILE_PROCESSING_OUTCOME_VALIDATION_SCHEMA_VERSION, errors)


def validate_file_processing_batch(value: Any) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(value, dict):
        errors.append("file_outcome_batch_not_object")
        return _validation(FILE_PROCESSING_BATCH_VALIDATION_SCHEMA_VERSION, errors)
    if set(value) != _BATCH_KEYS:
        errors.append("file_outcome_batch_shape_invalid")
    if value.get("schema_version") != FILE_PROCESSING_BATCH_SCHEMA_VERSION:
        errors.append("file_outcome_batch_schema_version_invalid")
    if value.get("policy_version") != FILE_PROCESSING_OUTCOME_POLICY_VERSION:
        errors.append("file_outcome_batch_policy_version_invalid")
    outcomes = value.get("outcomes")
    if not isinstance(outcomes, list) or not outcomes:
        errors.append("file_outcome_batch_outcomes_invalid")
        outcomes = []
    outcome_errors = [
        validation
        for item in outcomes
        if not (validation := validate_file_processing_outcome(item))["passed"]
    ]
    if outcome_errors:
        errors.append("file_outcome_batch_child_invalid")
    file_refs = [
        item.get("file_ref") for item in outcomes if isinstance(item, dict)
    ]
    file_refs_are_strings = len(file_refs) == len(outcomes) and all(
        isinstance(item, str) for item in file_refs
    )
    if not file_refs_are_strings or len(file_refs) != len(set(file_refs)):
        errors.append("file_outcome_batch_file_refs_invalid")
    if file_refs_are_strings and file_refs != sorted(file_refs):
        errors.append("file_outcome_batch_order_invalid")
    total = len(outcomes)
    if value.get("files_total") != total:
        errors.append("file_outcome_batch_total_invalid")
    counts = {
        status: sum(
            isinstance(item, dict) and item.get("status") == status
            for item in outcomes
        )
        for status in ("success", "partial", "failed")
    }
    if value.get("status_counts") != counts:
        errors.append("file_outcome_batch_counts_invalid")
    expected_status = _batch_status(counts, total) if total else None
    if value.get("overall_status") != expected_status:
        errors.append("file_outcome_batch_status_invalid")
    expected_message = (
        _batch_message(counts, total, expected_status) if expected_status else None
    )
    if value.get("user_message") != expected_message:
        errors.append("file_outcome_batch_user_message_invalid")
    if value.get("terminal") is not True:
        errors.append("file_outcome_batch_not_terminal")
    if not _REF_RE.fullmatch(str(value.get("batch_id") or "")):
        errors.append("file_outcome_batch_id_invalid")
    else:
        expected_id = _try_digest_ref(
            "batch",
            {key: value.get(key) for key in _BATCH_KEYS if key not in {
                "batch_id",
                "batch_checksum_ref",
            }},
            length=24,
        )
        if value.get("batch_id") != expected_id:
            errors.append("file_outcome_batch_id_mismatch")
    expected_checksum = _try_checksum_ref(
        "batchchk", value, "batch_checksum_ref"
    )
    if value.get("batch_checksum_ref") != expected_checksum:
        errors.append("file_outcome_batch_checksum_mismatch")
    return _validation(FILE_PROCESSING_BATCH_VALIDATION_SCHEMA_VERSION, errors)


def validate_private_processing_diagnostic(value: Any) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(value, dict):
        errors.append("file_outcome_private_diagnostic_not_object")
        return _validation(
            PRIVATE_PROCESSING_DIAGNOSTIC_VALIDATION_SCHEMA_VERSION, errors
        )
    if set(value) != _PRIVATE_DIAGNOSTIC_KEYS:
        errors.append("file_outcome_private_diagnostic_shape_invalid")
    if (
        value.get("schema_version")
        != PRIVATE_PROCESSING_DIAGNOSTIC_SCHEMA_VERSION
    ):
        errors.append("file_outcome_private_diagnostic_schema_invalid")
    if not _valid_file_ref(value.get("file_ref")):
        errors.append("file_outcome_private_diagnostic_file_ref_invalid")
    if value.get("stage") not in _STAGES:
        errors.append("file_outcome_private_diagnostic_stage_invalid")
    exception_type = value.get("exception_type")
    if exception_type is not None and not (
        isinstance(exception_type, str)
        and _EXCEPTION_TYPE_RE.fullmatch(exception_type)
    ):
        errors.append("file_outcome_private_diagnostic_exception_type_invalid")
    for key in ("exception_message", "source_path"):
        if value.get(key) is not None and not isinstance(value.get(key), str):
            errors.append("file_outcome_private_diagnostic_text_invalid")
    if not isinstance(value.get("private_context"), dict):
        errors.append("file_outcome_private_diagnostic_context_invalid")
    if not _is_json_value(value.get("provider_payload")) or not _is_json_value(
        value.get("private_context")
    ):
        errors.append("file_outcome_private_diagnostic_payload_invalid")
    if not _REF_RE.fullmatch(str(value.get("diagnostic_id") or "")):
        errors.append("file_outcome_private_diagnostic_id_invalid")
    else:
        expected_id = _try_digest_ref(
            "diag",
            {key: value.get(key) for key in _PRIVATE_DIAGNOSTIC_KEYS if key not in {
                "diagnostic_id",
                "diagnostic_checksum_ref",
            }},
            length=24,
        )
        if value.get("diagnostic_id") != expected_id:
            errors.append("file_outcome_private_diagnostic_id_mismatch")
    expected_checksum = _try_checksum_ref(
        "diagchk", value, "diagnostic_checksum_ref"
    )
    if value.get("diagnostic_checksum_ref") != expected_checksum:
        errors.append("file_outcome_private_diagnostic_checksum_mismatch")
    return _validation(
        PRIVATE_PROCESSING_DIAGNOSTIC_VALIDATION_SCHEMA_VERSION, errors
    )


def render_file_processing_outcome(value: Any) -> str:
    try:
        outcome = value.safe_snapshot() if isinstance(
            value, FileProcessingOutcomeRecord
        ) else copy.deepcopy(value)
        validation = validate_file_processing_outcome(outcome)
    except (TypeError, ValueError, OverflowError, RecursionError):
        return FILE_OUTCOME_FALLBACK_MESSAGE
    if not validation["passed"]:
        return FILE_OUTCOME_FALLBACK_MESSAGE
    return f"{outcome['file_ref']}: {outcome['user_message']}"


def render_file_processing_batch(value: Any) -> str:
    try:
        batch = value.safe_snapshot() if isinstance(
            value, FileProcessingBatchRecord
        ) else copy.deepcopy(value)
        validation = validate_file_processing_batch(batch)
    except (TypeError, ValueError, OverflowError, RecursionError):
        return BATCH_OUTCOME_FALLBACK_MESSAGE
    if not validation["passed"]:
        return BATCH_OUTCOME_FALLBACK_MESSAGE
    lines = [batch["user_message"]]
    lines.extend(
        f"{item['file_ref']}: {item['user_message']}" for item in batch["outcomes"]
    )
    return "\n".join(lines)


def _reason_policy(status: str, reason_code: str, stage: str) -> _ReasonPolicy:
    if status not in _STATUSES:
        raise FileProcessingOutcomeError("file_outcome_status_invalid")
    policy = _REASON_POLICIES.get((status, reason_code))
    if policy is None:
        raise FileProcessingOutcomeError("file_outcome_reason_code_invalid")
    if stage not in policy.stages:
        raise FileProcessingOutcomeError("file_outcome_reason_stage_invalid")
    return policy


def _require_file_ref(value: Any) -> None:
    if not _valid_file_ref(value):
        raise FileProcessingOutcomeError("file_outcome_file_ref_invalid")


def _valid_file_ref(value: Any) -> bool:
    return bool(
        isinstance(value, str)
        and _FILE_REF_RE.fullmatch(value)
        and ".." not in value
    )


def _require_stage(value: Any) -> None:
    if value not in _STAGES:
        raise FileProcessingOutcomeError("file_outcome_stage_invalid")


def _batch_status(counts: dict[str, int], total: int) -> str:
    if counts["success"] == total:
        return "success"
    if counts["failed"] == total:
        return "failed"
    return "partial"


def _batch_message(
    counts: dict[str, int], total: int, overall_status: str
) -> str:
    if overall_status == "success":
        return f"Все файлы успешно обработаны: {total}."
    if overall_status == "failed":
        return f"Не удалось обработать ни один файл: {total}."
    return (
        "Обработка файлов завершена частично: "
        f"успешно — {counts['success']}, "
        f"частично — {counts['partial']}, "
        f"с ошибкой — {counts['failed']}."
    )


def _validation(schema_version: str, errors: list[str]) -> dict[str, Any]:
    canonical_errors = sorted(set(errors))
    return {
        "schema_version": schema_version,
        "passed": not canonical_errors,
        "errors": [{"code": code} for code in canonical_errors],
    }


def _digest_ref(prefix: str, value: Any, *, length: int) -> str:
    return f"{prefix}_{hashlib.sha256(_canonical_json_bytes(value)).hexdigest()[:length]}"


def _checksum_ref(prefix: str, value: dict[str, Any], field: str) -> str:
    payload = copy.deepcopy(value)
    payload.pop(field, None)
    return f"{prefix}_{hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()}"


def _try_digest_ref(prefix: str, value: Any, *, length: int) -> str | None:
    try:
        return _digest_ref(prefix, value, length=length)
    except (TypeError, ValueError, OverflowError, RecursionError):
        return None


def _try_checksum_ref(
    prefix: str,
    value: dict[str, Any],
    field: str,
) -> str | None:
    try:
        return _checksum_ref(prefix, value, field)
    except (TypeError, ValueError, OverflowError, RecursionError):
        return None


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _is_json_value(value: Any) -> bool:
    try:
        _canonical_json_bytes(value)
    except (TypeError, ValueError, OverflowError):
        return False
    return True


def _optional_private_text(
    value: Any,
    maximum_chars: int,
    error_code: str,
) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > maximum_chars:
        raise FileProcessingOutcomeError(error_code)
    return value


def _positive_integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0
