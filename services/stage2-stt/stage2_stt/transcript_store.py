from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from stage2_stt.artifact_store import (
    ArtifactStoreAdapter,
    ArtifactStoreError,
    new_artifact_ref,
    utc_now_iso,
)
from stage2_stt.config import SttConfig
from stage2_stt.contracts import (
    ArtifactAccessContextV1,
    ArtifactRecordV1,
    ArtifactScopeV1,
    OpenWebUITranscriptionEnvelopeV1,
    TranscriptResultV1,
    TranscriptionJobV1,
)


@dataclass(frozen=True)
class TranscriptArtifactLinks:
    job: TranscriptionJobV1
    envelope: OpenWebUITranscriptionEnvelopeV1


class TranscriptStoreAdapter:
    def __init__(self, *, store: ArtifactStoreAdapter, config: SttConfig) -> None:
        self.store = store
        self.config = config

    def put_transcript(
        self,
        result: TranscriptResultV1,
        links: TranscriptArtifactLinks,
    ) -> str:
        scope = build_artifact_scope(links.envelope, links.job)
        source_ref = new_artifact_ref(
            artifact_type="source_file",
            artifact_scope=scope,
            expires_at=_expires_at(days=self.config.artifact_transcript_ttl_days),
        )
        prepared_ref = new_artifact_ref(
            artifact_type="prepared_audio",
            artifact_scope=scope,
            expires_at=_expires_at(hours=self.config.artifact_prepared_audio_ttl_hours),
        )
        stt_job_ref = new_artifact_ref(
            artifact_type="stt_job",
            artifact_scope=scope,
            expires_at=_expires_at(days=self.config.artifact_transformation_ttl_days),
        )

        self.store.put_artifact(
            ArtifactRecordV1(
                artifact_ref=source_ref,
                payload_kind="redacted",
                safe_metadata=_source_file_metadata(links),
                retention_class="source_file_ref",
                created_by=scope.user_id,
            )
        )
        self.store.put_artifact(
            ArtifactRecordV1(
                artifact_ref=prepared_ref,
                parent_refs=[source_ref.artifact_ref],
                payload_kind="redacted",
                safe_metadata=_prepared_audio_metadata(links),
                checksum_sha256=None,
                size_bytes=links.job.prepared_audio.size_bytes,
                retention_class="prepared_audio_ref",
                created_by=scope.user_id,
            )
        )
        self.store.put_artifact(
            ArtifactRecordV1(
                artifact_ref=stt_job_ref,
                parent_refs=[prepared_ref.artifact_ref],
                payload_kind="inline_json",
                payload_inline=_job_payload(links.job),
                safe_metadata={
                    "provider_id": links.job.provider_id,
                    "adapter_id": links.job.adapter_id,
                    "selected_output_profile": links.job.selected_output_profile,
                },
                retention_class="stt_job",
                created_by=scope.user_id,
            )
        )

        source_links = {
            "source_file_ref": source_ref.artifact_ref,
            "prepared_audio_ref": prepared_ref.artifact_ref,
            "stt_job_ref": stt_job_ref.artifact_ref,
            "openwebui_file_id": scope.openwebui_file_id,
        }
        enriched = result.model_copy(
            update={
                "artifact_scope": scope,
                "source_links": source_links,
                "safe_provider_metadata": _safe_provider_metadata(result, self.config),
            }
        )
        transcript_hash = transcript_content_hash(enriched)
        transcript_ref = new_artifact_ref(
            artifact_type="transcript_result",
            artifact_scope=scope,
            expires_at=_expires_at(days=self.config.artifact_transcript_ttl_days),
        )
        enriched = enriched.model_copy(
            update={
                "transcript_ref": transcript_ref.artifact_ref,
                "transcript_hash": transcript_hash,
            }
        )

        self.store.put_artifact(
            ArtifactRecordV1(
                artifact_ref=transcript_ref,
                parent_refs=[stt_job_ref.artifact_ref],
                payload_kind="inline_json",
                payload_inline=enriched.model_dump(mode="json", exclude_none=True),
                checksum_sha256=transcript_hash,
                size_bytes=len(enriched.model_dump_json()),
                safe_metadata={
                    "transcript_hash": transcript_hash,
                    "provider_id": enriched.provider_id,
                    "adapter_id": enriched.adapter_id,
                    "segment_count": len(enriched.segments),
                    "speaker_label_count": len(
                        {
                            segment.speaker
                            for segment in enriched.segments
                            if segment.speaker is not None
                        }
                    ),
                },
                retention_class="product_transcript",
                created_by=scope.user_id,
            )
        )
        self.store.link_artifacts(
            source_ref.artifact_ref,
            prepared_ref.artifact_ref,
            "normalize_audio",
        )
        chain = self.store.link_artifacts(
            prepared_ref.artifact_ref,
            stt_job_ref.artifact_ref,
            "transcribe",
        )
        chain = self.store.link_artifacts(
            stt_job_ref.artifact_ref,
            transcript_ref.artifact_ref,
            "transcribe",
        )
        self.store.index_transcript(
            transcript_ref=transcript_ref.artifact_ref,
            transcript_hash=transcript_hash,
            chain_id=chain.chain_id,
            artifact_ref=transcript_ref.artifact_ref,
            created_at=transcript_ref.created_at,
            expires_at=transcript_ref.expires_at,
        )
        return transcript_ref.artifact_ref

    def get_transcript(
        self,
        transcript_ref: str,
        user_context: ArtifactAccessContextV1,
    ) -> TranscriptResultV1:
        record = self.store.get_artifact(transcript_ref, user_context)
        if record.artifact_ref.artifact_type != "transcript_result":
            raise ArtifactStoreError("artifact_not_found", "Artifact ref is not a transcript")
        if record.payload_kind != "inline_json" or record.payload_inline is None:
            raise ArtifactStoreError(
                "artifact_payload_unavailable",
                "Transcript payload is unavailable",
            )
        return TranscriptResultV1.model_validate(record.payload_inline)

    def link_to_chat(
        self,
        transcript_ref: str,
        chat_id: str,
        message_id: str,
        file_id: str,
    ) -> None:
        return None

    def expire(self, transcript_ref: str) -> None:
        self.store.expire_artifact(transcript_ref, "transcript_expired")


def build_artifact_scope(
    envelope: OpenWebUITranscriptionEnvelopeV1,
    job: TranscriptionJobV1,
) -> ArtifactScopeV1:
    file_id = envelope.file.file_id if envelope.file is not None else None
    access_context = {
        "workspace_id": envelope.workspace_id or job.workspace_id,
        "user_id": envelope.user_id or job.user_id,
        "chat_id": envelope.chat_id,
        "message_id": envelope.message_id,
        "openwebui_file_id": file_id,
        "tenant_id": None,
    }
    access_hash = _stable_hash(access_context)
    scope_id = _stable_hash({**access_context, "stage2_job_id": job.job_id})
    return ArtifactScopeV1(
        scope_id=f"scope_{scope_id[:32]}",
        workspace_id=access_context["workspace_id"],
        user_id=access_context["user_id"],
        chat_id=access_context["chat_id"],
        message_id=access_context["message_id"],
        openwebui_file_id=access_context["openwebui_file_id"],
        stage2_job_id=job.job_id,
        tenant_id=None,
        access_context_hash=access_hash,
    )


def transcript_content_hash(result: TranscriptResultV1) -> str:
    payload = {
        "text": result.text,
        "language": result.language,
        "duration_seconds": result.duration_seconds,
        "segments": [
            {
                "text": segment.text,
                "start_seconds": segment.start_seconds,
                "end_seconds": segment.end_seconds,
                "speaker": segment.speaker,
                "words": [
                    {
                        "text": word.text,
                        "start_seconds": word.start_seconds,
                        "end_seconds": word.end_seconds,
                        "speaker": word.speaker,
                    }
                    for word in segment.words
                ],
            }
            for segment in result.segments
        ],
        "output_profile": result.output_profile,
        "provider_id": result.provider_id,
        "adapter_id": result.adapter_id,
        "warnings": result.warnings,
    }
    return _stable_hash(payload)


def _source_file_metadata(links: TranscriptArtifactLinks) -> dict:
    file_ref = links.envelope.file
    return {
        "openwebui_file_id": file_ref.file_id if file_ref is not None else None,
        "filename": file_ref.filename if file_ref is not None else links.job.source_media.file_name,
        "mime_type": links.job.source_media.mime_type,
        "size_bytes": links.job.source_media.size_bytes,
        "stored": links.job.source_media.stored,
    }


def _prepared_audio_metadata(links: TranscriptArtifactLinks) -> dict:
    return {
        "output_profile": links.job.prepared_audio.output_profile,
        "mime_type": links.job.prepared_audio.mime_type,
        "size_bytes": links.job.prepared_audio.size_bytes,
        "duration_seconds": links.job.prepared_audio.duration_seconds,
        "object_key_present": links.job.prepared_audio.object_key is not None,
    }


def _job_payload(job: TranscriptionJobV1) -> dict:
    return {
        "job_id": job.job_id,
        "status": job.status,
        "provider_id": job.provider_id,
        "adapter_id": job.adapter_id,
        "selected_output_profile": job.selected_output_profile,
        "storage_mode": job.storage_mode,
        "storage_available": job.storage_available,
    }


def _safe_provider_metadata(result: TranscriptResultV1, config: SttConfig) -> dict:
    return {
        "provider_id": result.provider_id,
        "adapter_id": result.adapter_id,
        "speaker_labels_requested": config.lemonfox.enable_speaker_labels,
        "timestamps_requested": config.lemonfox.enable_timestamps,
        "response_format": "verbose_json",
    }


def _expires_at(*, days: int | None = None, hours: int | None = None) -> str:
    delta = timedelta(days=days or 0, hours=hours or 0)
    return (datetime.now(timezone.utc) + delta).isoformat()


def _stable_hash(payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
