from stage2_stt.config import OutputProfile, load_stt_config
from stage2_stt.contracts import (
    PreparedAudioMetadataV1,
    SourceMediaMetadataV1,
    TranscriptResultV1,
)
from stage2_stt.jobs import apply_provider_result, create_transcription_job, request_cancel
from stage2_stt.lemonfox import LemonfoxSttAdapter
from stage2_stt.storage import (
    StaticStorageHealthProbe,
    StorageModeError,
    generate_prepared_audio_object_key,
    resolve_storage_decision,
)
from stage2_stt.validation import BYTES_PER_MB, validate_prepared_audio


def test_output_profile_validation_accepts_matching_supported_profile():
    config = load_stt_config({})
    capability = LemonfoxSttAdapter(config).capabilities()

    result = validate_prepared_audio(
        config=config,
        capability=capability,
        output_profile=OutputProfile.OPUS_WEBM_COMPACT,
        mime_type="audio/webm;codecs=opus",
        size_bytes=10 * BYTES_PER_MB,
    )

    assert result.accepted is True
    assert result.error is None


def test_output_profile_validation_rejects_wrong_mime():
    config = load_stt_config({})
    capability = LemonfoxSttAdapter(config).capabilities()

    result = validate_prepared_audio(
        config=config,
        capability=capability,
        output_profile=OutputProfile.OPUS_WEBM_COMPACT,
        mime_type="audio/mpeg",
        size_bytes=10 * BYTES_PER_MB,
    )

    assert result.accepted is False
    assert result.error is not None
    assert result.error.code == "unsupported_input_format"


def test_prepared_audio_over_100_mb_fails_by_default():
    config = load_stt_config({})
    capability = LemonfoxSttAdapter(config).capabilities()

    result = validate_prepared_audio(
        config=config,
        capability=capability,
        output_profile=OutputProfile.MP3_HIGH_COMPAT,
        mime_type="audio/mpeg",
        size_bytes=101 * BYTES_PER_MB,
    )

    assert result.accepted is False
    assert result.error is not None
    assert result.error.code == "prepared_audio_too_large"


def test_provider_direct_upload_limit_exceeded_when_internal_limit_is_higher():
    config = load_stt_config(
        {
            "STAGE2_STT_MAX_PREPARED_AUDIO_MB": "500",
            "STAGE2_LEMONFOX_MAX_DIRECT_UPLOAD_MB": "100",
        }
    )
    capability = LemonfoxSttAdapter(config).capabilities()

    result = validate_prepared_audio(
        config=config,
        capability=capability,
        output_profile=OutputProfile.MP3_HIGH_COMPAT,
        mime_type="audio/mpeg",
        size_bytes=101 * BYTES_PER_MB,
    )

    assert result.accepted is False
    assert result.error is not None
    assert result.error.code == "provider_direct_upload_limit_exceeded"


def test_storage_mode_auto_s3_none_branches():
    auto_config = load_stt_config({"STAGE2_STT_STORAGE_MODE": "auto"})
    auto_decision = resolve_storage_decision(auto_config)
    assert auto_decision.available is False
    assert auto_decision.persistent_prepared_audio is False
    assert "prepared_audio_storage_transient" in auto_decision.warnings

    s3_config = load_stt_config(
        {
            "STAGE2_STT_STORAGE_MODE": "s3",
            "STAGE2_STT_AUDIO_BUCKET": "stage2-audio",
        }
    )
    s3_decision = resolve_storage_decision(
        s3_config,
        health_probe=StaticStorageHealthProbe(available=True),
    )
    assert s3_decision.available is True
    assert s3_decision.persistent_prepared_audio is True

    none_config = load_stt_config({"STAGE2_STT_STORAGE_MODE": "none"})
    none_decision = resolve_storage_decision(none_config)
    assert none_decision.available is False
    assert none_decision.persistent_prepared_audio is False


def test_storage_mode_s3_requires_available_storage():
    s3_config = load_stt_config({"STAGE2_STT_STORAGE_MODE": "s3"})

    try:
        resolve_storage_decision(s3_config)
    except StorageModeError as exc:
        assert "requires configured healthy storage" in str(exc)
    else:
        raise AssertionError("s3 mode must fail without storage")


def test_object_key_generation_uses_safe_job_id_only():
    object_key = generate_prepared_audio_object_key(
        "stage2/stt/prepared-audio/",
        "job/with user@example.com",
    )

    assert object_key == "stage2/stt/prepared-audio/job-with-user-example.com/prepared-audio"


def test_local_cancel_state_transition_for_unknown_provider_cancel():
    config = load_stt_config({})
    capability = LemonfoxSttAdapter(config).capabilities()
    job = create_transcription_job(
        config=config,
        job_id="job-1",
        source_media=SourceMediaMetadataV1(file_name="source.webm"),
        prepared_audio=PreparedAudioMetadataV1(
            output_profile="opus_webm_compact",
            mime_type="audio/webm;codecs=opus",
            size_bytes=1,
        ),
        storage_available=False,
    )

    cancelled = request_cancel(job=job, config=config, capability=capability)

    assert cancelled.status == "cancelled"
    assert cancelled.cancel_state.requested is True
    assert cancelled.cancel_state.reason == "provider_cancel_unknown"
    assert cancelled.cancel_state.late_provider_result_ignored is True


def test_late_provider_result_does_not_complete_cancelled_job():
    config = load_stt_config({"STAGE2_STT_PROVIDER_CANCEL_SUPPORT": "false"})
    capability = LemonfoxSttAdapter(config).capabilities()
    job = create_transcription_job(
        config=config,
        job_id="job-2",
        source_media=SourceMediaMetadataV1(file_name="source.mp3"),
        prepared_audio=PreparedAudioMetadataV1(
            output_profile="mp3_high_compat",
            mime_type="audio/mpeg",
            size_bytes=1,
        ),
        storage_available=False,
    )
    cancelled = request_cancel(job=job, config=config, capability=capability)

    after_late_result = apply_provider_result(
        job=cancelled,
        result=TranscriptResultV1(
            text="late",
            output_profile="mp3_high_compat",
            provider_id="lemonfox",
            adapter_id="lemonfox",
        ),
    )

    assert after_late_result.status == "cancelled"
    assert after_late_result.cancel_state.reason == "late_provider_result_ignored"
