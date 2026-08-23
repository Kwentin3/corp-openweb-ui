from __future__ import annotations

import copy
from pathlib import Path

import pytest

from broker_reports_gate1.artifact_models import ArtifactAccessContext
from broker_reports_gate1.artifact_retention import build_retention_policy
from broker_reports_gate1.artifact_store import ArtifactStoreConfig, ArtifactStoreFactory
from broker_reports_gate1.authenticated_case_taxpayer_binding import (
    AUTHENTICATED_CASE_TAXPAYER_ASSERTION_SCHEMA_VERSION,
    AuthenticatedCaseTaxpayerBindingError,
    AuthenticatedCaseTaxpayerBindingRuntimeFactory,
)


class CurrentIdentityProvider:
    def __init__(self, assertions: tuple[dict, ...]) -> None:
        self.assertions = assertions

    def current_assertions(self, *, context: ArtifactAccessContext) -> tuple[dict, ...]:
        return copy.deepcopy(self.assertions)


def test_provider_owned_binding_is_current_across_execution_runs(tmp_path: Path) -> None:
    provider = CurrentIdentityProvider((_assertion(),))
    runtime, first = _runtime(tmp_path, provider, run_id="run-a")

    binding = runtime.publish_current(context=first)[0]
    second = _context(run_id="run-b")

    assert binding["scope"]["taxpayer_scope_ref"] == "taxpayer-authenticated-1"
    assert binding["scope"]["taxpayer_scope_ref"] != "security-disposal-1"
    assert runtime.validate_current(binding=binding, context=second) == binding


def test_missing_foreign_and_stale_provider_bindings_fail_closed(tmp_path: Path) -> None:
    provider = CurrentIdentityProvider((_assertion(),))
    runtime, context = _runtime(tmp_path, provider)
    old = runtime.publish_current(context=context)[0]

    provider.assertions = ()
    with pytest.raises(AuthenticatedCaseTaxpayerBindingError) as missing:
        runtime.publish_current(context=context)
    assert missing.value.code == "authenticated_taxpayer_binding_missing"

    provider.assertions = (_assertion(assertion_id="assertion-b", taxpayer_ref="taxpayer-b"),)
    runtime.publish_current(context=context)
    with pytest.raises(AuthenticatedCaseTaxpayerBindingError) as stale:
        runtime.validate_current(binding=old, context=context)
    assert stale.value.code == "authenticated_taxpayer_binding_stale"

    with pytest.raises(AuthenticatedCaseTaxpayerBindingError) as foreign:
        runtime.validate_current(binding=old, context=_context(case_id="foreign-case"))
    assert foreign.value.code == "authenticated_taxpayer_binding_owner_artifact_invalid"


def test_a_b_a_and_multiple_taxpayers_preserve_provider_identity(tmp_path: Path) -> None:
    provider = CurrentIdentityProvider((_assertion(),))
    runtime, context = _runtime(tmp_path, provider)
    first_a = runtime.publish_current(context=context)[0]

    provider.assertions = (_assertion(assertion_id="assertion-b", taxpayer_ref="taxpayer-b"),)
    b = runtime.publish_current(context=context)[0]
    provider.assertions = (_assertion(),)
    second_a = runtime.publish_current(context=context)[0]

    assert second_a == first_a
    assert b != first_a
    assert runtime.validate_current(binding=second_a, context=context) == first_a

    provider.assertions = (
        _assertion(),
        _assertion(assertion_id="assertion-b", taxpayer_ref="taxpayer-b"),
    )
    assert [item["scope"]["taxpayer_scope_ref"] for item in runtime.publish_current(context=context)] == [
        "taxpayer-authenticated-1",
        "taxpayer-b",
    ]


def test_caller_resealed_or_context_misbound_assertions_are_rejected(tmp_path: Path) -> None:
    provider = CurrentIdentityProvider((_assertion(),))
    runtime, context = _runtime(tmp_path, provider)
    binding = runtime.publish_current(context=context)[0]
    binding["taxpayer"]["inn"] = "500100732260"

    with pytest.raises(AuthenticatedCaseTaxpayerBindingError) as mutated:
        runtime.validate_current(binding=binding, context=context)
    assert mutated.value.code == "authenticated_taxpayer_binding_invalid"

    provider.assertions = (_assertion(case_id="foreign-case"),)
    with pytest.raises(AuthenticatedCaseTaxpayerBindingError) as misbound:
        runtime.publish_current(context=context)
    assert misbound.value.code == "authenticated_taxpayer_binding_context_mismatch"


def _runtime(root: Path, provider: CurrentIdentityProvider, *, run_id: str = "run-a"):
    store = ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=root / "artifacts.sqlite3",
            payload_root=root / "payloads",
        )
    ).create()
    runtime = AuthenticatedCaseTaxpayerBindingRuntimeFactory(
        store=store,
        retention_policy=build_retention_policy(mode="synthetic_dev"),
        identity_provider=provider,
    ).create()
    return runtime, _context(run_id=run_id)


def _context(*, run_id: str = "run-a", case_id: str = "case-authenticated"):
    return ArtifactAccessContext(
        user_id="authenticated-user",
        normalization_run_id=run_id,
        case_id=case_id,
        workspace_model_id="broker_reports_gate2_domain_source_fact_pipe",
        allow_private=True,
    )


def _assertion(
    *,
    assertion_id: str = "assertion-a",
    taxpayer_ref: str = "taxpayer-authenticated-1",
    case_id: str = "case-authenticated",
) -> dict:
    return {
        "schema_version": AUTHENTICATED_CASE_TAXPAYER_ASSERTION_SCHEMA_VERSION,
        "assertion_id": assertion_id,
        "authenticated_user_id": "authenticated-user",
        "case_id": case_id,
        "taxpayer_scope_ref": taxpayer_ref,
        "taxpayer": {
            "inn": "500100732259",
            "last_name": "Иванов",
            "first_name": "Иван",
            "middle_name": "Иванович",
        },
        "origin": {
            "kind": "authenticated_identity_provider",
            "provider_id": "openwebui-authenticated-case-owner",
        },
    }
