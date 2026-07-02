import asyncio
import json
import sqlite3
import time
import uuid

import pytest

from stage2_stt.artifact_store import ArtifactStoreError, ArtifactStoreFactory
from stage2_stt.config import load_stt_config
from stage2_stt.contracts import (
    ArtifactAccessContextV1,
    OpenWebUIFileReferenceV1,
    OpenWebUITranscriptionEnvelopeV1,
    PostProcessingRequestV1,
    PromptCatalogUserContextV1,
    SourceMediaMetadataV1,
    PreparedAudioMetadataV1,
    TranscriptResultV1,
    TranscriptSegmentV1,
)
from stage2_stt.jobs import create_transcription_job
from stage2_stt.post_processing import (
    PostProcessingError,
    PostProcessingService,
    build_transcript_projection,
    render_prompt_body,
)
from stage2_stt.prompt_catalog import PromptCatalogError
from stage2_stt.transcript_store import TranscriptArtifactLinks, TranscriptStoreAdapter


class FakeExecutor:
    def __init__(self) -> None:
        self.rendered_prompts: list[str] = []

    async def execute(self, rendered_prompt: str) -> str:
        self.rendered_prompts.append(rendered_prompt)
        return "Processed transcript result"


def test_post_processing_executes_template_and_stores_result(tmp_path):
    config = _config(tmp_path)
    _create_prompt_db(tmp_path / "webui.db")
    _insert_prompt(
        tmp_path / "webui.db",
        prompt_id="prompt-summary",
        command="stt-summary",
        name="Краткий пересказ",
        content="Summarize:\n{{TRANSCRIPT_WITH_SPEAKERS}}",
        template_id="stage2.stt.summary.v1",
        requires_speakers=False,
    )
    store = ArtifactStoreFactory(config).create()
    transcript_ref = _put_transcript(config, store, _speaker_transcript())
    executor = FakeExecutor()
    service = PostProcessingService(config=config, artifact_store=store, executor=executor)

    result = asyncio.run(
        service.execute(
            PostProcessingRequestV1(
                transcript_ref=transcript_ref,
                template_id="stage2.stt.summary.v1",
                user_context=PromptCatalogUserContextV1(user_id="user-1", user_role="user"),
                artifact_context=_artifact_context(),
            )
        )
    )

    assert result.result_ref is not None
    assert result.result_ref.startswith("art_")
    assert result.transcript_ref == transcript_ref
    assert result.template_id == "stage2.stt.summary.v1"
    assert result.openwebui_prompt_id == "prompt-summary"
    assert result.prompt_body_hash
    assert result.text == "Processed transcript result"
    assert "Summarize" not in result.model_dump_json()
    assert "speaker_0: hello" in executor.rendered_prompts[0]
    assert _artifact_count(config.artifact_store_path, "post_processing_result") == 1


def test_post_processing_refuses_long_transcript_without_chunking(tmp_path):
    config = _config(tmp_path, max_chars=10)
    _create_prompt_db(tmp_path / "webui.db")
    _insert_prompt(
        tmp_path / "webui.db",
        prompt_id="prompt-summary",
        command="stt-summary",
        name="Краткий пересказ",
        content="{{TRANSCRIPT_TEXT}}",
        template_id="stage2.stt.summary.v1",
    )
    store = ArtifactStoreFactory(config).create()
    transcript_ref = _put_transcript(
        config,
        store,
        _speaker_transcript(text="this transcript is too long for the configured single pass"),
    )
    service = PostProcessingService(config=config, artifact_store=store, executor=FakeExecutor())

    with pytest.raises(PostProcessingError) as refused:
        asyncio.run(
            service.execute(
                PostProcessingRequestV1(
                    transcript_ref=transcript_ref,
                    template_id="stage2.stt.summary.v1",
                    user_context=PromptCatalogUserContextV1(user_id="user-1", user_role="user"),
                    artifact_context=_artifact_context(),
                )
            )
        )
    assert refused.value.code == "transcript_too_long_single_pass"


def test_post_processing_refuses_speaker_required_template_without_speakers(tmp_path):
    config = _config(tmp_path)
    _create_prompt_db(tmp_path / "webui.db")
    _insert_prompt(
        tmp_path / "webui.db",
        prompt_id="prompt-meeting",
        command="stt-meeting-protocol",
        name="Протокол встречи",
        content="{{TRANSCRIPT_WITH_SPEAKERS}}",
        template_id="stage2.stt.meeting_protocol.v1",
        requires_speakers=True,
    )
    store = ArtifactStoreFactory(config).create()
    transcript_ref = _put_transcript(config, store, _speaker_transcript(speaker=None))
    service = PostProcessingService(config=config, artifact_store=store, executor=FakeExecutor())

    with pytest.raises(PostProcessingError) as refused:
        asyncio.run(
            service.execute(
                PostProcessingRequestV1(
                    transcript_ref=transcript_ref,
                    template_id="stage2.stt.meeting_protocol.v1",
                    user_context=PromptCatalogUserContextV1(user_id="user-1", user_role="user"),
                    artifact_context=_artifact_context(),
                )
            )
        )
    assert refused.value.code == "speakers_required"


def test_post_processing_refuses_loader_visible_ref_without_full_artifact_context(tmp_path):
    config = _config(tmp_path)
    _create_prompt_db(tmp_path / "webui.db")
    _insert_prompt(
        tmp_path / "webui.db",
        prompt_id="prompt-summary",
        command="stt-summary",
        name="РљСЂР°С‚РєРёР№ РїРµСЂРµСЃРєР°Р·",
        content="{{TRANSCRIPT_TEXT}}",
        template_id="stage2.stt.summary.v1",
    )
    store = ArtifactStoreFactory(config).create()
    transcript_ref = _put_transcript(config, store, _speaker_transcript())
    service = PostProcessingService(config=config, artifact_store=store, executor=FakeExecutor())

    with pytest.raises(ArtifactStoreError) as refused:
        asyncio.run(
            service.execute(
                PostProcessingRequestV1(
                    transcript_ref=transcript_ref,
                    template_id="stage2.stt.summary.v1",
                    user_context=PromptCatalogUserContextV1(user_id="user-1", user_role="user"),
                    artifact_context=ArtifactAccessContextV1(user_id="user-1"),
                )
            )
        )
    assert refused.value.code == "artifact_scope_unverified"


def test_post_processing_prompt_access_checked_at_execution_boundary(tmp_path):
    config = _config(tmp_path)
    _create_prompt_db(tmp_path / "webui.db")
    _insert_prompt(
        tmp_path / "webui.db",
        prompt_id="prompt-private",
        command="stt-summary",
        name="РљСЂР°С‚РєРёР№ РїРµСЂРµСЃРєР°Р·",
        content="{{TRANSCRIPT_TEXT}}",
        template_id="stage2.stt.summary.v1",
        public=False,
    )
    store = ArtifactStoreFactory(config).create()
    transcript_ref = _put_transcript(config, store, _speaker_transcript())
    service = PostProcessingService(config=config, artifact_store=store, executor=FakeExecutor())

    with pytest.raises(PromptCatalogError) as refused:
        asyncio.run(
            service.execute(
                PostProcessingRequestV1(
                    transcript_ref=transcript_ref,
                    template_id="stage2.stt.summary.v1",
                    user_context=PromptCatalogUserContextV1(user_id="user-2", user_role="user"),
                    artifact_context=_artifact_context(),
                )
            )
        )
    assert getattr(refused.value, "code", None) == "prompt_access_denied"


def test_post_processing_result_keeps_original_prompt_hash_after_prompt_change(tmp_path):
    config = _config(tmp_path)
    db_path = tmp_path / "webui.db"
    _create_prompt_db(db_path)
    _insert_prompt(
        db_path,
        prompt_id="prompt-summary",
        command="stt-summary",
        name="РљСЂР°С‚РєРёР№ РїРµСЂРµСЃРєР°Р·",
        content="Version 1 {{TRANSCRIPT_TEXT}}",
        template_id="stage2.stt.summary.v1",
    )
    store = ArtifactStoreFactory(config).create()
    transcript_ref = _put_transcript(config, store, _speaker_transcript())
    service = PostProcessingService(config=config, artifact_store=store, executor=FakeExecutor())

    first = asyncio.run(
        service.execute(
            PostProcessingRequestV1(
                transcript_ref=transcript_ref,
                template_id="stage2.stt.summary.v1",
                user_context=PromptCatalogUserContextV1(user_id="user-1", user_role="user"),
                artifact_context=_artifact_context(),
            )
        )
    )
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE prompt SET content = ?, version_id = ? WHERE id = ?",
            ("Version 2 {{TRANSCRIPT_TEXT}}", "version-2", "prompt-summary"),
        )
        conn.commit()

    second = asyncio.run(
        service.execute(
            PostProcessingRequestV1(
                transcript_ref=transcript_ref,
                template_id="stage2.stt.summary.v1",
                user_context=PromptCatalogUserContextV1(user_id="user-1", user_role="user"),
                artifact_context=_artifact_context(),
            )
        )
    )
    stored_first = _stored_payload(config.artifact_store_path, first.result_ref)

    assert first.prompt_body_hash != second.prompt_body_hash
    assert first.prompt_version == "version-prompt-summary"
    assert second.prompt_version == "version-2"
    assert stored_first["prompt_body_hash"] == first.prompt_body_hash
    assert stored_first["prompt_version"] == first.prompt_version


def test_render_prompt_body_uses_normalized_projection_only():
    projection = build_transcript_projection(_speaker_transcript())

    rendered = render_prompt_body("Body:\n{{TRANSCRIPT_WITH_SPEAKERS}}", projection)

    assert "speaker_0: hello" in rendered
    assert "raw_provider" not in rendered


def _config(tmp_path, max_chars=60000):
    return load_stt_config(
        {
            "STAGE2_STT_ARTIFACT_STORE_MODE": "sqlite",
            "STAGE2_STT_ARTIFACT_STORE_PATH": str(tmp_path / "artifacts.sqlite3"),
            "STAGE2_STT_PROMPT_CATALOG_MODE": "openwebui_sqlite",
            "STAGE2_STT_OPENWEBUI_PROMPT_DB_PATH": str(tmp_path / "webui.db"),
            "STAGE2_STT_POSTPROCESSING_MAX_TRANSCRIPT_CHARS": str(max_chars),
            "STAGE2_STT_INTERNAL_API_KEY": "unit-test-token",
        }
    )


def _put_transcript(config, store, transcript):
    transcript_store = TranscriptStoreAdapter(store=store, config=config)
    return transcript_store.put_transcript(transcript, _links(config))


def _links(config):
    envelope = OpenWebUITranscriptionEnvelopeV1(
        source_context="openwebui",
        user_id="user-1",
        user_email="user@example.test",
        user_role="user",
        chat_id="chat-1",
        message_id="message-1",
        workspace_id="workspace-1",
        file=OpenWebUIFileReferenceV1(
            file_id="file-1",
            filename="sample.mp3",
            mime_type="audio/mpeg",
            size_bytes=9,
        ),
        selected_output_profile="mp3_high_compat",
    )
    job = create_transcription_job(
        config=config,
        job_id="stt-test-job",
        source_media=SourceMediaMetadataV1(
            file_name="sample.mp3",
            mime_type="audio/mpeg",
            size_bytes=9,
        ),
        prepared_audio=PreparedAudioMetadataV1(
            output_profile="mp3_high_compat",
            mime_type="audio/mpeg",
            size_bytes=9,
        ),
        storage_available=False,
    ).model_copy(update={"status": "completed"})
    return TranscriptArtifactLinks(job=job, envelope=envelope)


def _speaker_transcript(text="hello", speaker="speaker_0"):
    return TranscriptResultV1(
        text=text,
        language="ru",
        duration_seconds=1.0,
        segments=[
            TranscriptSegmentV1(
                text=text,
                start_seconds=0,
                end_seconds=1,
                speaker=speaker,
            )
        ],
        output_profile="mp3_high_compat",
        provider_id="lemonfox",
        adapter_id="lemonfox",
        warnings=[],
    )


def _artifact_context():
    return ArtifactAccessContextV1(
        workspace_id="workspace-1",
        user_id="user-1",
        chat_id="chat-1",
        message_id="message-1",
        openwebui_file_id="file-1",
    )


def _artifact_count(path, artifact_type):
    with sqlite3.connect(path) as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM artifact_records WHERE artifact_type = ?",
            (artifact_type,),
        ).fetchone()
    return int(row[0])


def _create_prompt_db(path):
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE prompt (
                id TEXT PRIMARY KEY,
                command TEXT,
                user_id TEXT NOT NULL,
                name TEXT NOT NULL,
                content TEXT NOT NULL,
                data JSON,
                meta JSON,
                is_active BOOLEAN NOT NULL,
                version_id TEXT,
                tags JSON,
                created_at BIGINT NOT NULL,
                updated_at BIGINT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE access_grant (
                id TEXT PRIMARY KEY,
                resource_type TEXT NOT NULL,
                resource_id TEXT NOT NULL,
                principal_type TEXT NOT NULL,
                principal_id TEXT NOT NULL,
                permission TEXT NOT NULL,
                created_at BIGINT NOT NULL
            )
            """
        )
        conn.commit()


def _insert_prompt(
    path,
    *,
    prompt_id,
    command,
    name,
    content,
    template_id,
    requires_speakers=False,
    public=True,
):
    now = int(time.time())
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            INSERT INTO prompt(
                id, command, user_id, name, content, data, meta, is_active,
                version_id, tags, created_at, updated_at
            )
            VALUES (?, ?, 'user-1', ?, ?, '{}', ?, 1, ?, ?, ?, ?)
            """,
            (
                prompt_id,
                command,
                name,
                content,
                json.dumps(
                    {
                        "template_kind": "post_processing",
                        "template_id": template_id,
                        "requires_speakers": requires_speakers,
                        "chunkable": False,
                    }
                ),
                f"version-{prompt_id}",
                json.dumps(["stage2-stt-v2", "stt-post-processing"]),
                now,
                now,
            ),
        )
        if public:
            conn.execute(
                """
                INSERT INTO access_grant(
                    id, resource_type, resource_id, principal_type,
                    principal_id, permission, created_at
                )
                VALUES (?, 'prompt', ?, 'user', '*', 'read', ?)
                """,
                (str(uuid.uuid4()), prompt_id, now),
            )
        conn.commit()


def _stored_payload(path, artifact_ref):
    with sqlite3.connect(path) as conn:
        row = conn.execute(
            "SELECT payload_inline_json FROM artifact_records WHERE artifact_ref = ?",
            (artifact_ref,),
        ).fetchone()
    assert row is not None
    return json.loads(row[0])
