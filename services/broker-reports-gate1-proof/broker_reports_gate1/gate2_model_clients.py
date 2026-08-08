from __future__ import annotations

import copy
import hashlib
import inspect
import json
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Callable

from .gate2_economy_budget import (
    Gate2EconomyBudgetSession,
    Gate2EconomyBudgetSessionFactory,
)
from .gate2_model_contracts import (
    PROVIDER_STATUS_APPROVED,
    PROVIDER_STATUS_PROBE_REQUIRED,
    Gate2ProviderProfile,
    Gate2ProviderExecutionMetadata,
    Gate2SourceFactRuntimeError,
    Gate2StructuredModelClientConfig,
    Gate2StructuredModelResult,
    gate2_provider_profile,
)
from .gate2_model_requests import (
    FINANCIAL_SEMANTIC_V6_CONTEXT_V2_1_BUDGET_SMOKE_REQUEST_PROFILE,
    GATE3_BOUNDED_LABELING_REQUEST_PROFILE,
    SOURCE_QUALIFICATION_REQUEST_PROFILE,
    SOURCE_REQUEST_PROFILE,
    Gate2OpenWebUIRequestBuilder,
)
from .gate2_provider_adapters import (
    CONTEXT_V2_1_BUDGET_SMOKE_TRANSPORT_POLICY,
    Gate2ContextV21BudgetSmokeTransportContract,
    Gate2NativeProviderTransportConfig,
    Gate2OpenWebUIProviderConnectionResolver,
    Gate2PreparedProviderRequest,
    Gate2ProviderAdapter,
    Gate2ProviderAdapterFactory,
    provider_error_code,
)


FACTORY_REQUIRED = (
    "Gate2StructuredModelClientFactory.create is the only production Gate 2 model client entrypoint"
)
FORBIDDEN = (
    "Pipes, control checks and smoke scripts must not call OpenWebUI completion functions or provider SDKs directly"
)


CompletionResolver = Callable[[str], Any]
NativeTransportResolver = Callable[[Gate2ProviderProfile, dict[str, Any]], Any]
MAX_PRIVATE_INVALID_RESPONSE_BYTES = 65_536
MAX_MODEL_CONTENT_BYTES = 524_288
MAX_MODEL_CONTENT_NODES = 20_000
MAX_MODEL_CONTENT_DEPTH = 64
MAX_MODEL_STRING_BYTES = 131_072
_ADAPTER_EXTRACTED_OUTPUT_UNAVAILABLE = object()


@dataclass(frozen=True)
class Gate2ContextV21BudgetSmokeModelResult:
    adapter_extracted_output: Any = field(repr=False)
    execution_metadata: Gate2ProviderExecutionMetadata
    economy_budget_receipt: dict[str, Any]
    prepared_request: Gate2PreparedProviderRequest = field(repr=False)
    raw_provider_response: dict[str, Any] = field(repr=False)
    prepared_request_hash: str


@dataclass(frozen=True)
class Gate3BoundedLabelingModelResult:
    adapter_extracted_output: Any = field(repr=False)
    execution_metadata: Gate2ProviderExecutionMetadata
    prepared_request: Gate2PreparedProviderRequest = field(repr=False)
    raw_provider_response: dict[str, Any] = field(repr=False)


class Gate2StructuredModelClientFactory:
    def __init__(
        self,
        *,
        config: Gate2StructuredModelClientConfig,
        user: Any,
        request: Any,
        completion_resolver: CompletionResolver | None = None,
        native_transport_resolver: NativeTransportResolver | None = None,
        native_transport_config: Gate2NativeProviderTransportConfig | None = None,
        provider_connection_resolver=None,
    ) -> None:
        self.config = config
        self.user = user
        self.request = request
        self.completion_resolver = completion_resolver
        self.native_transport_resolver = native_transport_resolver
        self.native_transport_config = (
            native_transport_config or Gate2NativeProviderTransportConfig()
        )
        self.provider_connection_resolver = provider_connection_resolver

    def create(self) -> "Gate2OpenWebUIStructuredModelClient":
        if self.config.transport != "openwebui":
            raise Gate2SourceFactRuntimeError(
                "gate2_model_transport_unsupported",
                "Unsupported Gate 2 model transport",
            )
        request_builder = Gate2OpenWebUIRequestBuilder(
            request_profile=self.config.request_profile
        )
        provider_profile = gate2_provider_profile(self.config.provider_profile_id)
        probe_allowed = (
            self.config.capability_probe
            and provider_profile.gate2_status == PROVIDER_STATUS_PROBE_REQUIRED
        )
        if provider_profile.gate2_status != PROVIDER_STATUS_APPROVED and not probe_allowed:
            raise Gate2SourceFactRuntimeError(
                "gate2_no_strict_structured_provider_available",
                "Selected provider is not approved for strict Gate 2 structured output",
            )
        default_connection_resolver = (
            Gate2OpenWebUIProviderConnectionResolver(self.request)
        )
        provider_adapter = Gate2ProviderAdapterFactory(
            profile=provider_profile,
            capability_probe=self.config.capability_probe,
            native_transport_config=self.native_transport_config,
            native_transport_resolver=self.native_transport_resolver,
            provider_connection_resolver=(
                self.provider_connection_resolver
                or (
                    default_connection_resolver
                    .resolve_context_v2_1_budget_smoke
                    if self.config.request_profile
                    == (
                        FINANCIAL_SEMANTIC_V6_CONTEXT_V2_1_BUDGET_SMOKE_REQUEST_PROFILE
                    )
                    else default_connection_resolver.resolve
                )
            ),
        ).create()
        budget_session = (
            Gate2EconomyBudgetSessionFactory().create(
                request_profile=self.config.request_profile,
            )
            if self.config.economy_budget_enforcement
            else None
        )
        return Gate2OpenWebUIStructuredModelClient(
            request_profile=self.config.request_profile,
            provider_profile=provider_profile,
            request_builder=request_builder,
            provider_adapter=provider_adapter,
            user=self.user,
            request=self.request,
            completion_resolver=self.completion_resolver,
            budget_session=budget_session,
        )


class Gate2OpenWebUIStructuredModelClient:
    def __init__(
        self,
        *,
        request_profile: str,
        provider_profile: Gate2ProviderProfile,
        request_builder: Gate2OpenWebUIRequestBuilder,
        provider_adapter: Gate2ProviderAdapter,
        user: Any,
        request: Any,
        completion_resolver: CompletionResolver | None,
        budget_session: Gate2EconomyBudgetSession | None = None,
    ) -> None:
        self.request_profile = request_profile
        self.provider_profile = provider_profile
        self.request_builder = request_builder
        self.provider_adapter = provider_adapter
        self.user = user
        self.request = request
        self.completion_resolver = (
            completion_resolver or self._resolve_openwebui_completion_dependencies
        )
        self.budget_session = budget_session
        self._budget_operation_ordinal = 0
        self._qualification_local_invocations_total = 0
        self._qualification_provider_submissions_total = 0
        self._qualification_provider_responses_total = 0

    def execution_contract(self, model_id: str) -> Gate2ProviderExecutionMetadata:
        return self.provider_adapter.execution_contract(model_id)

    def qualification_lifecycle_snapshot(self) -> dict[str, int]:
        return {
            "local_invocations_total": (
                self._qualification_local_invocations_total
            ),
            "provider_submissions_total": (
                self._qualification_provider_submissions_total
            ),
            "provider_responses_total": (
                self._qualification_provider_responses_total
            ),
        }

    async def extract(self, *, prompt, package, model_id, response_format):
        self._qualification_local_invocations_total += 1
        user_id = self._validate_request_context()
        form_data = self.request_builder.build(
            prompt=prompt,
            package=package,
            model_id=model_id,
            response_format=response_format,
        )
        budget_authorization = None
        if self.budget_session is not None:
            self._budget_operation_ordinal += 1
            budget_authorization = self.budget_session.prepare_call(
                form_data=form_data,
                model_id=model_id,
                provider_profile_id=self.provider_profile.profile_id,
                operation_identity=(
                    f"gate2-economy-operation-"
                    f"{self._budget_operation_ordinal}"
                ),
            )
            form_data = budget_authorization.prepared_form_data
        effective_model_id = (
            budget_authorization.exact_model_id
            if budget_authorization is not None
            else model_id
        )
        execution_contract = self.execution_contract(effective_model_id)
        self.provider_adapter.validate_model(effective_model_id)
        prepared_request = self.provider_adapter.prepare_form_data(
            form_data=form_data,
            response_format=response_format,
        )
        result, _response_payload = await self._execute_prepared_once(
            user_id=user_id,
            effective_model_id=effective_model_id,
            execution_contract=execution_contract,
            prepared_request=prepared_request,
            budget_authorization=budget_authorization,
            content_extractor=self.provider_adapter.extract_content,
        )
        return result

    async def extract_context_v2_1_once(
        self,
        *,
        model_visible_request: dict[str, Any],
        canonical_schema: dict[str, Any],
        model_id: str,
        operation_identity: str,
        expected_prepared_request_hash: str,
        transport_policy: str,
        expected_transport_contract_hash: str,
    ) -> Gate2ContextV21BudgetSmokeModelResult:
        if (
            self.request_profile
            != FINANCIAL_SEMANTIC_V6_CONTEXT_V2_1_BUDGET_SMOKE_REQUEST_PROFILE
            or self.budget_session is None
            or getattr(self.provider_adapter, "capability_probe", False)
            is not True
        ):
            raise Gate2SourceFactRuntimeError(
                "gate2_model_request_profile_mismatch",
                "Context V2.1 budget smoke requires its governed client profile",
            )
        self._qualification_local_invocations_total += 1
        user_id = self._validate_request_context()
        form_data = self.request_builder.build_from_sealed_context_v2_1(
            model_visible_request=model_visible_request,
            model_id=model_id,
        )
        budget_authorization = self.budget_session.prepare_call(
            form_data=form_data,
            model_id=model_id,
            provider_profile_id=self.provider_profile.profile_id,
            operation_identity=operation_identity,
        )
        effective_model_id = budget_authorization.exact_model_id
        execution_contract = self.execution_contract(effective_model_id)
        self.provider_adapter.validate_model(effective_model_id)
        response_format = model_visible_request.get("response_format")
        prepared_request = (
            self.provider_adapter
            .prepare_context_v2_1_budget_smoke_form_data(
                form_data=budget_authorization.prepared_form_data,
                response_format=response_format,
            )
        )
        prepared_request_hash = self._prepared_request_hash(prepared_request)
        if (
            not isinstance(expected_prepared_request_hash, str)
            or prepared_request_hash != expected_prepared_request_hash
            or not prepared_request.context_v2_1_budget_smoke_contract_is_bound(
                canonical_schema=canonical_schema,
                provider_profile=self.provider_profile,
                model_visible_request=model_visible_request,
                exact_model_id=effective_model_id,
                operation_identity=operation_identity,
            )
        ):
            raise Gate2SourceFactRuntimeError(
                "gate2_model_request_plan_mismatch",
                "Context V2.1 budget-smoke request differs from the frozen plan",
            )
        if (
            transport_policy
            != CONTEXT_V2_1_BUDGET_SMOKE_TRANSPORT_POLICY
        ):
            raise Gate2SourceFactRuntimeError(
                "gate2_model_transport_plan_mismatch",
                "Context V2.1 budget-smoke transport policy is not frozen",
                failure_class="provider_configuration",
            )
        transport_contract = (
            self.provider_adapter
            .context_v2_1_budget_smoke_transport_contract(
                transport_policy=transport_policy,
            )
        )
        if (
            not isinstance(expected_transport_contract_hash, str)
            or transport_contract.integrity_hash
            != expected_transport_contract_hash
        ):
            raise Gate2SourceFactRuntimeError(
                "gate2_model_transport_plan_mismatch",
                "Context V2.1 budget-smoke transport contract is not frozen",
                failure_class="provider_configuration",
            )

        def extract_candidate(payload: dict[str, Any]) -> Any:
            return (
                self.provider_adapter
                .extract_context_v2_1_budget_smoke_prepared_content(
                    payload,
                    prepared_request=prepared_request,
                    canonical_schema=canonical_schema,
                    model_visible_request=model_visible_request,
                    exact_model_id=effective_model_id,
                    operation_identity=operation_identity,
                )
            )

        result, response_payload = await self._execute_prepared_once(
            user_id=user_id,
            effective_model_id=effective_model_id,
            execution_contract=execution_contract,
            prepared_request=prepared_request,
            budget_authorization=budget_authorization,
            content_extractor=extract_candidate,
            context_v2_1_transport_contract=transport_contract,
        )
        if (
            result.execution_metadata is None
            or result.economy_budget_receipt is None
        ):
            failure = Gate2SourceFactRuntimeError(
                "gate2_model_execution_evidence_missing",
                "Context V2.1 budget-smoke execution evidence is incomplete",
                execution_metadata=result.execution_metadata,
            )
            failure.adapter_extracted_output = copy.deepcopy(result.content)
            failure.raw_provider_response = copy.deepcopy(response_payload)
            failure.economy_budget_receipt = copy.deepcopy(
                result.economy_budget_receipt
            )
            raise failure
        return Gate2ContextV21BudgetSmokeModelResult(
            adapter_extracted_output=copy.deepcopy(result.content),
            execution_metadata=result.execution_metadata,
            economy_budget_receipt=copy.deepcopy(
                result.economy_budget_receipt
            ),
            prepared_request=copy.deepcopy(prepared_request),
            raw_provider_response=copy.deepcopy(response_payload),
            prepared_request_hash=prepared_request_hash,
        )

    async def label_gate3_once(
        self,
        *,
        model_visible_request: dict[str, Any],
        canonical_schema: dict[str, Any],
        model_id: str,
    ) -> Gate3BoundedLabelingModelResult:
        if (
            self.request_profile != GATE3_BOUNDED_LABELING_REQUEST_PROFILE
            or self.budget_session is not None
            or getattr(self.provider_adapter, "capability_probe", False) is True
        ):
            raise Gate2SourceFactRuntimeError(
                "gate2_model_request_profile_mismatch",
                "Gate 3 bounded labeling requires its one-attempt client profile",
            )
        self._qualification_local_invocations_total += 1
        user_id = self._validate_request_context()
        form_data = self.request_builder.build_from_sealed_gate3_labeling(
            model_visible_request=model_visible_request,
            model_id=model_id,
        )
        execution_contract = self.execution_contract(model_id)
        self.provider_adapter.validate_model(model_id)
        response_format = model_visible_request.get("response_format")
        prepared_request = (
            self.provider_adapter.prepare_gate3_bounded_labeling_form_data(
                form_data=form_data,
                response_format=response_format,
            )
        )
        provider_form_data = prepared_request.form_data
        provider_messages = provider_form_data.get("messages")
        provider_system = provider_form_data.get("system")
        if provider_system is None:
            provider_parts = (
                [item.get("content") for item in provider_messages]
                if isinstance(provider_messages, list)
                and all(isinstance(item, dict) for item in provider_messages)
                else []
            )
        else:
            provider_parts = (
                [
                    provider_system,
                    *[item.get("content") for item in provider_messages],
                ]
                if isinstance(provider_system, str)
                and isinstance(provider_messages, list)
                and all(isinstance(item, dict) for item in provider_messages)
                else []
            )
        expected_parts = [
            item["content"] for item in model_visible_request["messages"]
        ]
        canonical_schema_hash = hashlib.sha256(
            json.dumps(
                canonical_schema,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
        ).hexdigest()
        if (
            provider_parts != expected_parts
            or "metadata" in provider_form_data
            or prepared_request.canonical_schema_hash != canonical_schema_hash
        ):
            raise Gate2SourceFactRuntimeError(
                "gate2_model_request_invalid",
                "Gate 3 final provider context is not exact",
            )

        def extract_candidate(payload: dict[str, Any]) -> Any:
            return self.provider_adapter.extract_prepared_content(
                payload,
                prepared_request=prepared_request,
            )

        result, response_payload = await self._execute_prepared_once(
            user_id=user_id,
            effective_model_id=model_id,
            execution_contract=execution_contract,
            prepared_request=prepared_request,
            budget_authorization=None,
            content_extractor=extract_candidate,
            capture_private_evidence=True,
        )
        if result.execution_metadata is None:
            failure = Gate2SourceFactRuntimeError(
                "gate2_model_execution_evidence_missing",
                "Gate 3 provider execution evidence is incomplete",
            )
            failure.raw_provider_response = copy.deepcopy(response_payload)
            failure.prepared_request = copy.deepcopy(prepared_request)
            raise failure
        return Gate3BoundedLabelingModelResult(
            adapter_extracted_output=copy.deepcopy(result.content),
            execution_metadata=result.execution_metadata,
            prepared_request=copy.deepcopy(prepared_request),
            raw_provider_response=copy.deepcopy(response_payload),
        )

    async def _execute_prepared_once(
        self,
        *,
        user_id: str,
        effective_model_id: str,
        execution_contract: Gate2ProviderExecutionMetadata,
        prepared_request: Gate2PreparedProviderRequest,
        budget_authorization,
        content_extractor,
        context_v2_1_transport_contract: (
            Gate2ContextV21BudgetSmokeTransportContract | None
        ) = None,
        capture_private_evidence: bool = False,
    ) -> tuple[Gate2StructuredModelResult, dict[str, Any]]:
        # OpenWebUI's completion handler consumes request fields with ``pop``.
        # Dispatch a private copy so the sealed prepared request remains exact
        # audit evidence for the bytes submitted at this boundary.
        form_data = copy.deepcopy(prepared_request.form_data)
        started: float | None = None
        response_payload: dict[str, Any] | None = None
        economy_budget_receipt: dict[str, Any] | None = None
        submission_recorded = False
        response_recorded = False
        adapter_extracted_output: Any = (
            _ADAPTER_EXTRACTED_OUTPUT_UNAVAILABLE
        )
        context_v2_1_budget_smoke = (
            self.request_profile
            == FINANCIAL_SEMANTIC_V6_CONTEXT_V2_1_BUDGET_SMOKE_REQUEST_PROFILE
        )
        try:
            if context_v2_1_budget_smoke:
                if not isinstance(
                    context_v2_1_transport_contract,
                    Gate2ContextV21BudgetSmokeTransportContract,
                ):
                    raise Gate2SourceFactRuntimeError(
                        "gate2_model_transport_plan_mismatch",
                        (
                            "Context V2.1 budget-smoke transport "
                            "contract is unavailable"
                        ),
                        failure_class="provider_configuration",
                    )
                self.provider_adapter.validate_context_v2_1_budget_smoke_transport_configuration(
                    transport_policy=(
                        context_v2_1_transport_contract.transport_policy
                    ),
                )
                started = time.monotonic()
                self._qualification_provider_submissions_total += 1
                submission_recorded = True
                response = (
                    self.provider_adapter
                    .invoke_context_v2_1_budget_smoke_once(
                        form_data=form_data,
                        transport_policy=(
                            context_v2_1_transport_contract
                            .transport_policy
                        ),
                    )
                )
            elif not self.provider_adapter.uses_openwebui_completion:
                self.provider_adapter.validate_transport_configuration()
                started = time.monotonic()
                self._qualification_provider_submissions_total += 1
                submission_recorded = True
                response = self.provider_adapter.invoke_native_once(form_data)
            else:
                dependencies = self.completion_resolver(user_id)
                if inspect.isawaitable(dependencies):
                    dependencies = await dependencies
                completion_fn, user_model = dependencies
                if inspect.isawaitable(user_model):
                    user_model = await user_model
                if user_model is None:
                    raise Gate2SourceFactRuntimeError(
                        "gate2_model_unavailable",
                        self._user_unavailable_message(),
                    )
                started = time.monotonic()
                self._qualification_provider_submissions_total += 1
                submission_recorded = True
                response = self._invoke_completion_once(
                    completion_fn=completion_fn,
                    form_data=form_data,
                    user_model=user_model,
                )
            if inspect.isawaitable(response):
                response = await response
            self._qualification_provider_responses_total += 1
            response_recorded = True
            response_payload = self._response_payload(response)
            duration_ms = self._duration_ms(started)
            if "detail" in response_payload or "error" in response_payload:
                self._validate_model_content_budget(response_payload)
            if context_v2_1_budget_smoke:
                execution_metadata = (
                    self.provider_adapter
                    .context_v2_1_budget_smoke_execution_metadata(
                        payload=response_payload,
                        requested_model_id=effective_model_id,
                        duration_ms=duration_ms,
                        prepared_request=prepared_request,
                        transport_contract=(
                            context_v2_1_transport_contract
                        ),
                    )
                )
            else:
                execution_metadata = (
                    self.provider_adapter.execution_metadata(
                        payload=response_payload,
                        requested_model_id=effective_model_id,
                        duration_ms=duration_ms,
                        prepared_request=prepared_request,
                    )
                )
            self.provider_adapter.validate_execution_metadata(execution_metadata)
            if "detail" in response_payload or "error" in response_payload:
                raise Gate2SourceFactRuntimeError(
                    provider_error_code(
                        response_payload,
                        source_profile=self.request_profile
                        in {
                            SOURCE_REQUEST_PROFILE,
                            SOURCE_QUALIFICATION_REQUEST_PROFILE,
                        },
                    ),
                    self._provider_error_message(),
                    raw_output=response_payload,
                    execution_metadata=execution_metadata,
                    failure_class="provider_error_response",
                )
            economy_budget_receipt = (
                self.budget_session.finalize_call(
                    authorization=budget_authorization,
                    execution_metadata=execution_metadata,
                )
                if self.budget_session is not None
                and budget_authorization is not None
                else None
            )
            content = content_extractor(response_payload)
            if context_v2_1_budget_smoke:
                adapter_extracted_output = copy.deepcopy(content)
            self._validate_model_content_budget(content)
        except Gate2SourceFactRuntimeError as exc:
            if capture_private_evidence:
                exc.prepared_request = copy.deepcopy(prepared_request)
                if response_payload is not None:
                    exc.raw_provider_response = copy.deepcopy(response_payload)
            if (
                self.request_profile
                == FINANCIAL_SEMANTIC_V6_CONTEXT_V2_1_BUDGET_SMOKE_REQUEST_PROFILE
            ):
                if exc.raw_output is None and response_payload is not None:
                    exc.raw_output = copy.deepcopy(response_payload)
                if economy_budget_receipt is not None:
                    exc.economy_budget_receipt = copy.deepcopy(
                        economy_budget_receipt
                    )
                if adapter_extracted_output is not (
                    _ADAPTER_EXTRACTED_OUTPUT_UNAVAILABLE
                ):
                    exc.adapter_extracted_output = copy.deepcopy(
                        adapter_extracted_output
                    )
                    exc.raw_provider_response = copy.deepcopy(
                        response_payload
                    )
            if (
                submission_recorded
                and not response_recorded
                and (
                    exc.failure_class
                    in {"provider_response_invalid", "response_budget"}
                    or getattr(
                        exc,
                        "provider_response_received",
                        False,
                    )
                    is True
                )
            ):
                self._qualification_provider_responses_total += 1
                response_recorded = True
            if exc.execution_metadata is None:
                metadata_payload = (
                    None
                    if exc.code == "gate2_model_response_budget_exceeded"
                    else response_payload
                )
                if context_v2_1_budget_smoke and not submission_recorded:
                    exc.execution_metadata = None
                elif context_v2_1_budget_smoke:
                    exc.execution_metadata = (
                        self.provider_adapter
                        .context_v2_1_budget_smoke_execution_metadata(
                            payload=metadata_payload,
                            requested_model_id=effective_model_id,
                            duration_ms=self._duration_ms(started),
                            prepared_request=prepared_request,
                            transport_contract=(
                                context_v2_1_transport_contract
                            ),
                        )
                    )
                else:
                    exc.execution_metadata = (
                        self.provider_adapter.execution_metadata(
                            payload=metadata_payload,
                            requested_model_id=effective_model_id,
                            duration_ms=self._duration_ms(started),
                            prepared_request=prepared_request,
                        )
                    )
            raise
        except Exception as exc:
            diagnostic_text = str(exc)
            diagnostic = {
                "error": {
                    "type": exc.__class__.__name__,
                    "message_length": len(diagnostic_text),
                    "message_sha256": hashlib.sha256(
                        diagnostic_text.encode("utf-8")
                    ).hexdigest(),
                }
            }
            if context_v2_1_budget_smoke and not submission_recorded:
                failure_metadata = None
            elif context_v2_1_budget_smoke:
                failure_metadata = (
                    self.provider_adapter
                    .context_v2_1_budget_smoke_execution_metadata(
                        payload=response_payload,
                        requested_model_id=effective_model_id,
                        duration_ms=self._duration_ms(started),
                        prepared_request=prepared_request,
                        transport_contract=context_v2_1_transport_contract,
                    )
                )
            else:
                failure_metadata = self.provider_adapter.execution_metadata(
                    payload=response_payload,
                    requested_model_id=effective_model_id,
                    duration_ms=self._duration_ms(started),
                    prepared_request=prepared_request,
                )
            failure = Gate2SourceFactRuntimeError(
                "gate2_model_call_failed",
                exc.__class__.__name__,
                raw_output=diagnostic,
                execution_metadata=failure_metadata,
                failure_class=exc.__class__.__name__,
            )
            if capture_private_evidence:
                failure.prepared_request = copy.deepcopy(prepared_request)
                if response_payload is not None:
                    failure.raw_provider_response = copy.deepcopy(response_payload)
            if (
                self.request_profile
                == FINANCIAL_SEMANTIC_V6_CONTEXT_V2_1_BUDGET_SMOKE_REQUEST_PROFILE
                and adapter_extracted_output
                is not _ADAPTER_EXTRACTED_OUTPUT_UNAVAILABLE
            ):
                failure.adapter_extracted_output = copy.deepcopy(
                    adapter_extracted_output
                )
                failure.raw_provider_response = copy.deepcopy(
                    response_payload
                )
                if economy_budget_receipt is not None:
                    failure.economy_budget_receipt = copy.deepcopy(
                        economy_budget_receipt
                    )
            raise failure from exc
        if response_payload is None:
            raise Gate2SourceFactRuntimeError(
                "gate2_model_invalid_response",
                "Provider response payload is unavailable",
            )
        return (
            Gate2StructuredModelResult(
                content=content,
                structured_output_mode=(
                    execution_contract.structured_output_mode
                ),
                response_format_type=execution_contract.response_format_type,
                response_format_schema_mode=(
                    execution_contract.response_format_schema_mode
                ),
                execution_metadata=execution_metadata,
                economy_budget_receipt=economy_budget_receipt,
            ),
            response_payload,
        )

    def preflight_full_scope(
        self,
        *,
        model_id: str,
        default_call_input_tokens,
        fallback_call_input_tokens=(),
    ) -> dict[str, Any]:
        if self.budget_session is None:
            raise Gate2SourceFactRuntimeError(
                "gate2_economy_budget_not_enabled",
                "Economy budget enforcement is not enabled",
                failure_class="economy_budget",
            )
        return self.budget_session.preflight_full_scope(
            model_id=model_id,
            provider_profile_id=self.provider_profile.profile_id,
            default_call_input_tokens=default_call_input_tokens,
            fallback_call_input_tokens=fallback_call_input_tokens,
        )

    def _validate_request_context(self) -> str:
        user_id = self._user_id(self.user)
        if self.request_profile in {
            SOURCE_REQUEST_PROFILE,
            SOURCE_QUALIFICATION_REQUEST_PROFILE,
        }:
            if self.request is None:
                raise Gate2SourceFactRuntimeError(
                    "gate2_model_unavailable",
                    "OpenWebUI request object is required",
                )
            if not user_id:
                raise Gate2SourceFactRuntimeError(
                    "gate2_model_unavailable",
                    "Authenticated OpenWebUI user is required",
                )
            return user_id
        if self.request is None or not user_id:
            raise Gate2SourceFactRuntimeError(
                "gate2_model_unavailable",
                "Authenticated OpenWebUI request is required",
            )
        return user_id

    def _invoke_completion_once(self, *, completion_fn, form_data, user_model):
        variants = (
            (
                (),
                {
                    "request": self.request,
                    "form_data": form_data,
                    "user": user_model,
                    "bypass_filter": True,
                    "bypass_system_prompt": True,
                },
            ),
            (
                (),
                {
                    "request": self.request,
                    "form_data": form_data,
                    "user": user_model,
                },
            ),
            ((self.request, form_data, user_model), {}),
        )
        try:
            signature = inspect.signature(completion_fn)
        except (TypeError, ValueError):
            args, kwargs = variants[0]
            return completion_fn(*args, **kwargs)
        for args, kwargs in variants:
            try:
                signature.bind(*args, **kwargs)
            except TypeError:
                continue
            return completion_fn(*args, **kwargs)
        raise TypeError("Unsupported OpenWebUI completion function signature")

    @staticmethod
    def _duration_ms(started: float | None) -> int | None:
        if started is None:
            return None
        return max(0, round((time.monotonic() - started) * 1000))

    @staticmethod
    def _prepared_request_hash(
        prepared_request: Gate2PreparedProviderRequest,
    ) -> str:
        return hashlib.sha256(
            json.dumps(
                asdict(prepared_request),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
        ).hexdigest()

    def _resolve_openwebui_completion_dependencies(self, user_id: str):
        try:
            from open_webui.utils.chat import generate_chat_completion as completion_fn
        except Exception:
            from open_webui.main import generate_chat_completions as completion_fn
        from open_webui.models.users import Users

        return completion_fn, Users.get_user_by_id(user_id)

    def _response_payload(self, response: Any) -> dict[str, Any]:
        if isinstance(response, dict):
            return response
        body = getattr(response, "body", None)
        if isinstance(body, bytes):
            body_diagnostic = {
                "response_type": response.__class__.__name__,
                "body_length": len(body),
                "body_sha256": hashlib.sha256(body).hexdigest(),
            }
            try:
                payload = json.loads(body.decode("utf-8"))
            except (UnicodeDecodeError, ValueError) as exc:
                raise Gate2SourceFactRuntimeError(
                    "gate2_model_invalid_response",
                    self._invalid_body_message(),
                    raw_output=body_diagnostic,
                ) from exc
            if isinstance(payload, dict):
                return payload
            if (
                isinstance(payload, list)
                and len(payload) == 1
                and isinstance(payload[0], dict)
                and ("error" in payload[0] or "detail" in payload[0])
            ):
                return payload[0]
            raise Gate2SourceFactRuntimeError(
                "gate2_model_invalid_response",
                self._invalid_body_message(),
                raw_output=(
                    payload
                    if len(body) <= MAX_PRIVATE_INVALID_RESPONSE_BYTES
                    else {
                        **body_diagnostic,
                        "body_json_type": type(payload).__name__,
                    }
                ),
            )
        if isinstance(response, str):
            return {"content": response}
        raise Gate2SourceFactRuntimeError(
            "gate2_model_invalid_response",
            self._unsupported_response_message(),
            raw_output={"response_type": response.__class__.__name__},
        )

    @staticmethod
    def _validate_model_content_budget(content: Any) -> None:
        try:
            if isinstance(content, str):
                encoded = content.encode("utf-8")
            else:
                encoded = json.dumps(
                    content,
                    ensure_ascii=False,
                    separators=(",", ":"),
                    sort_keys=True,
                ).encode("utf-8")
        except (RecursionError, TypeError, ValueError) as exc:
            raise Gate2SourceFactRuntimeError(
                "gate2_model_response_budget_exceeded",
                "Model response cannot be bounded safely",
                raw_output={
                    "response_budget": {
                        "reason": "serialization_failed",
                        "content_type": content.__class__.__name__,
                    }
                },
                failure_class="response_budget",
            ) from exc
        digest = hashlib.sha256(encoded).hexdigest()
        if len(encoded) > MAX_MODEL_CONTENT_BYTES:
            raise Gate2SourceFactRuntimeError(
                "gate2_model_response_budget_exceeded",
                "Model response exceeds the byte budget",
                raw_output={
                    "response_budget": {
                        "reason": "bytes",
                        "observed": len(encoded),
                        "allowed": MAX_MODEL_CONTENT_BYTES,
                        "content_sha256": digest,
                    }
                },
                failure_class="response_budget",
            )
        bounded_value = content
        if isinstance(content, str):
            try:
                bounded_value = json.loads(content)
            except RecursionError as exc:
                raise Gate2SourceFactRuntimeError(
                    "gate2_model_response_budget_exceeded",
                    "Model response exceeds the JSON nesting budget",
                    raw_output={
                        "response_budget": {
                            "reason": "json_nesting",
                            "bytes": len(encoded),
                            "content_sha256": digest,
                        }
                    },
                    failure_class="response_budget",
                ) from exc
            except ValueError:
                bounded_value = content
        nodes_total = 0
        max_depth = 0
        stack: list[tuple[Any, int]] = [(bounded_value, 1)]
        seen_containers: set[int] = set()
        while stack:
            value, depth = stack.pop()
            nodes_total += 1
            max_depth = max(max_depth, depth)
            if nodes_total > MAX_MODEL_CONTENT_NODES:
                reason = "nodes"
                observed = nodes_total
                allowed = MAX_MODEL_CONTENT_NODES
                break
            if depth > MAX_MODEL_CONTENT_DEPTH:
                reason = "depth"
                observed = depth
                allowed = MAX_MODEL_CONTENT_DEPTH
                break
            if isinstance(value, str) and len(value.encode("utf-8")) > MAX_MODEL_STRING_BYTES:
                reason = "string_bytes"
                observed = len(value.encode("utf-8"))
                allowed = MAX_MODEL_STRING_BYTES
                break
            if isinstance(value, dict):
                identity = id(value)
                if identity in seen_containers:
                    continue
                seen_containers.add(identity)
                for key, child in value.items():
                    if len(str(key).encode("utf-8")) > MAX_MODEL_STRING_BYTES:
                        reason = "key_bytes"
                        observed = len(str(key).encode("utf-8"))
                        allowed = MAX_MODEL_STRING_BYTES
                        break
                    stack.append((child, depth + 1))
                else:
                    continue
                break
            if isinstance(value, list):
                identity = id(value)
                if identity in seen_containers:
                    continue
                seen_containers.add(identity)
                stack.extend((child, depth + 1) for child in value)
        else:
            return
        raise Gate2SourceFactRuntimeError(
            "gate2_model_response_budget_exceeded",
            "Model response exceeds the structural budget",
            raw_output={
                "response_budget": {
                    "reason": reason,
                    "observed": observed,
                    "allowed": allowed,
                    "bytes": len(encoded),
                    "nodes": nodes_total,
                    "max_depth": max_depth,
                    "content_sha256": digest,
                }
            },
            failure_class="response_budget",
        )

    def _user_unavailable_message(self) -> str:
        if self.request_profile in {
            SOURCE_REQUEST_PROFILE,
            SOURCE_QUALIFICATION_REQUEST_PROFILE,
        }:
            return "OpenWebUI user model is unavailable"
        return "OpenWebUI user is unavailable"

    def _invalid_body_message(self) -> str:
        if self.request_profile in {
            SOURCE_REQUEST_PROFILE,
            SOURCE_QUALIFICATION_REQUEST_PROFILE,
        }:
            return "Completion response body is not JSON"
        return "Completion body is not JSON"

    def _unsupported_response_message(self) -> str:
        if self.request_profile in {
            SOURCE_REQUEST_PROFILE,
            SOURCE_QUALIFICATION_REQUEST_PROFILE,
        }:
            return "Unsupported completion response shape"
        return "Unsupported completion response"

    def _provider_error_message(self) -> str:
        if self.request_profile in {
            SOURCE_REQUEST_PROFILE,
            SOURCE_QUALIFICATION_REQUEST_PROFILE,
        }:
            return "Provider returned a typed error object"
        return "Provider returned a typed error"

    @staticmethod
    def _user_id(user: Any) -> str:
        if isinstance(user, dict):
            return str(user.get("id") or user.get("user_id") or "")
        return str(getattr(user, "id", "") or "")
