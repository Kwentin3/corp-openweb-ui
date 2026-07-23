from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
GATE1_BUNDLE = ROOT / "openwebui_actions" / "broker_reports_gate1_pipe_bundled.py"
SOURCE_BUNDLE = (
    ROOT / "openwebui_actions" / "broker_reports_gate2_source_fact_pipe_bundled.py"
)
DOMAIN_BUNDLE = (
    ROOT
    / "openwebui_actions"
    / "broker_reports_gate2_domain_source_fact_pipe_bundled.py"
)

from broker_reports_gate1 import (  # noqa: E402
    ArtifactStoreConfig,
    ArtifactStoreFactory,
    build_retention_policy,
)
from broker_reports_gate1.artifact_models import ArtifactRecord  # noqa: E402
from broker_reports_gate1.gate2_chat_dcp_resolution import (  # noqa: E402
    Gate2ChatDcpResolutionError,
    Gate2ChatDcpResolverConfig,
    Gate2ChatDcpResolverFactory,
)
from openwebui_actions.broker_reports_gate2_domain_source_fact_pipe import (  # noqa: E402
    Pipe as DomainPipe,
)
from openwebui_actions.broker_reports_gate2_source_fact_pipe import (  # noqa: E402
    Pipe as SourcePipe,
)


def _record(
    *,
    artifact_id: str,
    artifact_type: str = "domain_context_packet_v0",
    user_id: str = "owner-a",
    chat_id: str = "chat-a",
) -> ArtifactRecord:
    return ArtifactRecord(
        artifact_id=artifact_id,
        artifact_type=artifact_type,
        case_id="case-a",
        chat_id=chat_id,
        user_id=user_id,
        workspace_model_id="broker_reports_gate1_pipe",
        normalization_run_id=f"norm-{artifact_id}",
        document_id=None,
        source_file_ref=None,
        visibility="private_case",
        storage_backend="project_artifact_payload",
        retention_policy=build_retention_policy(
            mode="customer_approved_test",
            explicit=True,
        ),
        access_policy={
            "requires_user_id": True,
            "requires_case_or_chat": True,
        },
        validation_status="validated",
        lifecycle_status="private_ready",
        payload={"schema_version": artifact_type},
    )


@pytest.fixture()
def store():
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        yield ArtifactStoreFactory(
            ArtifactStoreConfig(
                mode="sqlite",
                sqlite_path=root / "artifacts.sqlite3",
                payload_root=root / "payloads",
            )
        ).create()


def _resolver(store):
    return Gate2ChatDcpResolverFactory(
        Gate2ChatDcpResolverConfig(
            artifact_store_path=store.sqlite_path,
        )
    ).create()


def test_resolver_finds_one_active_owner_scoped_chat_dcp(store):
    expected = store.put_record(_record(artifact_id="dcp-owner-a"))
    store.put_record(
        _record(
            artifact_id="dcp-owner-b",
            user_id="owner-b",
        )
    )
    store.put_record(
        _record(
            artifact_id="other-type",
            artifact_type="gate1_issue_ledger_v0",
        )
    )

    resolved = _resolver(store).resolve(
        user_id="owner-a",
        chat_id="chat-a",
    )

    assert resolved == expected.artifact_id


def test_resolver_fails_closed_on_missing_or_ambiguous_chat_dcp(store):
    with pytest.raises(Gate2ChatDcpResolutionError) as missing:
        _resolver(store).resolve(
            user_id="owner-a",
            chat_id="chat-a",
        )
    assert missing.value.code == "gate2_chat_dcp_not_found"

    store.put_record(_record(artifact_id="dcp-a"))
    store.put_record(_record(artifact_id="dcp-b"))

    with pytest.raises(Gate2ChatDcpResolutionError) as ambiguous:
        _resolver(store).resolve(
            user_id="owner-a",
            chat_id="chat-a",
        )
    assert ambiguous.value.code == "gate2_chat_dcp_ambiguous"


def test_chat_dcp_resolver_is_bundled_only_with_gate2_functions():
    marker = '"gate2_chat_dcp_resolution"'

    assert marker not in GATE1_BUNDLE.read_text(encoding="utf-8")
    assert marker in SOURCE_BUNDLE.read_text(encoding="utf-8")
    assert marker in DOMAIN_BUNDLE.read_text(encoding="utf-8")


@pytest.mark.parametrize("pipe_type", [SourcePipe, DomainPipe])
def test_gate2_pipe_resolves_dcp_from_server_chat_metadata(store, pipe_type):
    expected = store.put_record(_record(artifact_id="dcp-chat-metadata"))

    resolved = pipe_type._resolve_dcp_ref(
        resolver=_resolver(store),
        body={},
        metadata={"chat_id": "chat-a"},
        config={},
        user_id="owner-a",
    )

    assert resolved == expected.artifact_id


@pytest.mark.parametrize("pipe_type", [SourcePipe, DomainPipe])
def test_gate2_pipe_explicit_ref_wins_and_chat_fallback_is_fail_closed(
    store,
    pipe_type,
):
    assert (
        pipe_type._resolve_dcp_ref(
            resolver=_resolver(store),
            body={},
            metadata={},
            config={"domain_context_packet_ref": "explicit-dcp"},
            user_id="owner-a",
        )
        == "explicit-dcp"
    )
    assert (
        pipe_type._resolve_dcp_ref(
            resolver=_resolver(store),
            body={"metadata": {"chat_id": "missing-chat"}},
            metadata={},
            config={},
            user_id="owner-a",
        )
        == ""
    )
