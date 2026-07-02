import inspect
import sqlite3

import pytest

import stage2_stt.app as app_module
from stage2_stt.artifact_store import (
    FACTORY_REQUIRED,
    FORBIDDEN,
    ArtifactStoreError,
    ArtifactStoreFactory,
    new_artifact_ref,
)
from stage2_stt.config import load_stt_config
from stage2_stt.contracts import (
    ArtifactAccessContextV1,
    OpenWebUIFileReferenceV1,
    OpenWebUITranscriptionEnvelopeV1,
    PreparedAudioMetadataV1,
    SourceMediaMetadataV1,
    TranscriptResultV1,
    TranscriptSegmentV1,
    TranscriptWordV1,
)
from stage2_stt.jobs import create_transcription_job
from stage2_stt.lemonfox import LemonfoxSttAdapter
from stage2_stt.transcript_store import (
    TranscriptArtifactLinks,
    TranscriptStoreAdapter,
    build_artifact_scope,
    transcript_content_hash,
)


def test_artifact_store_factory_anti_drift_anchors_are_present():
    source = inspect.getsource(app_module)

    assert "ArtifactStoreFactory" in source
    assert "SqliteArtifactStoreAdapter(" not in source
    assert "ArtifactStoreFactory.create" in FACTORY_REQUIRED
    assert "must not instantiate SqliteArtifactStoreAdapter directly" in FORBIDDEN


def test_transcript_store_persists_structured_transcript_and_lineage(tmp_path):
    config = _config(tmp_path)
    store = ArtifactStoreFactory(config).create()
    transcript_store = TranscriptStoreAdapter(store=store, config=config)
    result = _speaker_result()
    links = _links(config)

    transcript_ref = transcript_store.put_transcript(result, links)
    loaded = transcript_store.get_transcript(transcript_ref, _access_context())
    chain = store.list_chain(transcript_ref, _access_context())

    assert transcript_ref.startswith("art_")
    assert loaded.transcript_ref == transcript_ref
    assert loaded.artifact_scope is not None
    assert loaded.artifact_scope.user_id == "user-1"
    assert loaded.segments[0].speaker == "speaker_0"
    assert loaded.segments[1].words[0].speaker == "speaker_1"
    assert loaded.transcript_hash == transcript_content_hash(loaded)
    assert "raw-lemonfox-marker" not in loaded.model_dump_json()
    assert [edge.transform for edge in chain.edges] == [
        "normalize_audio",
        "transcribe",
        "transcribe",
    ]
    assert _transcript_index_count(config.artifact_store_path) == 1


def test_transcript_store_access_failures_are_typed(tmp_path):
    config = _config(tmp_path)
    store = ArtifactStoreFactory(config).create()
    transcript_store = TranscriptStoreAdapter(store=store, config=config)
    transcript_ref = transcript_store.put_transcript(_speaker_result(), _links(config))

    with pytest.raises(ArtifactStoreError) as missing_context:
        transcript_store.get_transcript(transcript_ref, ArtifactAccessContextV1())
    assert missing_context.value.code == "artifact_scope_unverified"

    with pytest.raises(ArtifactStoreError) as wrong_user:
        transcript_store.get_transcript(
            transcript_ref,
            _access_context(user_id="user-2"),
        )
    assert wrong_user.value.code == "artifact_access_denied"


def test_expired_transcript_ref_returns_typed_refusal(tmp_path):
    config = _config(tmp_path)
    store = ArtifactStoreFactory(config).create()
    transcript_store = TranscriptStoreAdapter(store=store, config=config)
    transcript_ref = transcript_store.put_transcript(_speaker_result(), _links(config))

    transcript_store.expire(transcript_ref)

    with pytest.raises(ArtifactStoreError) as expired:
        transcript_store.get_transcript(transcript_ref, _access_context())
    assert expired.value.code == "artifact_expired"


def test_provider_raw_payload_marker_is_not_stored_in_product_artifacts(tmp_path):
    marker = "raw-provider-marker-never-store"
    config = _config(tmp_path)
    adapter = LemonfoxSttAdapter(config)
    normalized = adapter.normalize_transcript(
        {
            "text": "hello",
            "raw_provider_marker": marker,
            "segments": [
                {
                    "text": "hello",
                    "speaker": "speaker_0",
                    "words": [{"word": "hello", "speaker": "speaker_0"}],
                }
            ],
        },
        output_profile="mp3_high_compat",
    )
    store = ArtifactStoreFactory(config).create()
    transcript_store = TranscriptStoreAdapter(store=store, config=config)

    transcript_ref = transcript_store.put_transcript(normalized, _links(config))
    loaded = transcript_store.get_transcript(transcript_ref, _access_context())

    assert loaded.segments[0].speaker == "speaker_0"
    assert marker not in loaded.model_dump_json()
    assert marker not in _sqlite_text(config.artifact_store_path)


def test_artifact_refs_are_opaque_and_unguessable(tmp_path):
    links = _links(_config(tmp_path))
    scope = build_artifact_scope(links.envelope, links.job)

    refs = [
        new_artifact_ref(
            artifact_type="transcript_result",
            artifact_scope=scope,
            expires_at=None,
        ).artifact_ref
        for _ in range(100)
    ]

    assert len(set(refs)) == 100
    assert all(ref.startswith("art_") for ref in refs)
    assert all(len(ref) > 32 for ref in refs)
    assert all(ref not in {f"art_{index}" for index in range(100)} for ref in refs)


def _config(tmp_path):
    return load_stt_config(
        {
            "STAGE2_STT_ARTIFACT_STORE_MODE": "sqlite",
            "STAGE2_STT_ARTIFACT_STORE_PATH": str(tmp_path / "artifacts.sqlite3"),
            "STAGE2_STT_ALLOW_STUB_TRANSCRIPT": "true",
            "STAGE2_STT_INTERNAL_API_KEY": "unit-test-token",
        }
    )


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


def _speaker_result() -> TranscriptResultV1:
    marker = "raw-lemonfox-marker"
    return TranscriptResultV1(
        text="Speaker A hello. Speaker B hi.",
        language="ru",
        duration_seconds=2.0,
        segments=[
            TranscriptSegmentV1(
                text="Speaker A hello.",
                start_seconds=0,
                end_seconds=1,
                speaker="speaker_0",
                words=[
                    TranscriptWordV1(
                        text="hello",
                        start_seconds=0,
                        end_seconds=1,
                        speaker="speaker_0",
                    )
                ],
            ),
            TranscriptSegmentV1(
                text="Speaker B hi.",
                start_seconds=1,
                end_seconds=2,
                speaker="speaker_1",
                words=[
                    TranscriptWordV1(
                        text="hi",
                        start_seconds=1,
                        end_seconds=2,
                        speaker="speaker_1",
                    )
                ],
            ),
        ],
        output_profile="mp3_high_compat",
        provider_id="lemonfox",
        adapter_id="lemonfox",
        warnings=[],
        safe_provider_metadata={"marker_not_raw": "safe"},
    ).model_copy(update={"source_links": {"marker_absent": marker.replace("raw-", "")}})


def _access_context(user_id: str = "user-1") -> ArtifactAccessContextV1:
    return ArtifactAccessContextV1(
        workspace_id="workspace-1",
        user_id=user_id,
        chat_id="chat-1",
        message_id="message-1",
        openwebui_file_id="file-1",
    )


def _transcript_index_count(path: str | None) -> int:
    assert path is not None
    with sqlite3.connect(path) as conn:
        row = conn.execute("SELECT COUNT(*) FROM transcript_index").fetchone()
    return int(row[0])


def _sqlite_text(path: str | None) -> str:
    assert path is not None
    with sqlite3.connect(path) as conn:
        rows = conn.execute(
            """
            SELECT payload_inline_json, safe_metadata_json, warnings_json
            FROM artifact_records
            """
        ).fetchall()
    return "\n".join(" ".join(str(value) for value in row if value is not None) for row in rows)
