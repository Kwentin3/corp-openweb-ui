from __future__ import annotations

from dataclasses import dataclass

from stage2_stt.contracts import TranscriptResultV1, TranscriptionJobV1


@dataclass(frozen=True)
class StoredTranscriptionJob:
    job: TranscriptionJobV1
    result: TranscriptResultV1 | None = None


class InMemoryTranscriptionJobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, StoredTranscriptionJob] = {}

    def put(self, record: StoredTranscriptionJob) -> None:
        self._jobs[record.job.job_id] = record

    def get(self, job_id: str) -> StoredTranscriptionJob | None:
        return self._jobs.get(job_id)

    def update_job(self, job: TranscriptionJobV1) -> StoredTranscriptionJob:
        existing = self._jobs.get(job.job_id)
        result = existing.result if existing is not None else None
        updated = StoredTranscriptionJob(job=job, result=result)
        self.put(updated)
        return updated
