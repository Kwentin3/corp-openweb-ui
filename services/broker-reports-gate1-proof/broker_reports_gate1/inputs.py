from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Literal

from .contracts import stable_digest


SourceKind = Literal[
    "synthetic",
    "local_private_test",
    "openwebui_pipe",
    "archive_member_private",
]


class BytesUnavailable(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass
class ByteReadResult:
    status: str
    content_bytes: bytes | None = None
    reason: str | None = None
    source: str | None = None


@dataclass
class FileInput:
    private_ref: str
    original_filename_private: str
    mime_type: str = ""
    source_kind: SourceKind = "synthetic"
    modified_time: str | None = None
    declared_size_bytes: int | None = None
    bytes_provider: Callable[[], bytes] | None = None
    provider_label: str = "provided"
    privacy_markers: list[str] = field(default_factory=list)
    root_input_ordinal: int | None = None
    archive_parent_document_ref: str | None = None
    archive_member_ref: str | None = None
    archive_member_index: int | None = None

    @classmethod
    def from_bytes(
        cls,
        *,
        private_ref: str,
        filename: str,
        content: bytes,
        mime_type: str = "",
        source_kind: SourceKind = "synthetic",
        modified_time: str | None = None,
    ) -> "FileInput":
        return cls(
            private_ref=private_ref,
            original_filename_private=filename,
            mime_type=mime_type,
            source_kind=source_kind,
            modified_time=modified_time,
            declared_size_bytes=len(content),
            bytes_provider=lambda content=content: content,
            provider_label="inline_bytes",
        )

    @property
    def private_ref_hash(self) -> str:
        return stable_digest([self.private_ref], length=16)

    def private_markers(self) -> list[str]:
        markers = [self.private_ref, self.original_filename_private]
        markers.extend(self.privacy_markers)
        return [marker for marker in markers if marker]

    def read_bytes(self) -> ByteReadResult:
        if self.bytes_provider is None:
            return ByteReadResult(status="blocked", reason="bytes_provider_missing")
        try:
            content = self.bytes_provider()
        except BytesUnavailable as exc:
            return ByteReadResult(status="blocked", reason=exc.reason)
        except OSError:
            return ByteReadResult(status="blocked", reason="bytes_provider_os_error")
        if not isinstance(content, bytes):
            return ByteReadResult(status="blocked", reason="bytes_provider_returned_non_bytes")
        return ByteReadResult(status="available", content_bytes=content, source=self.provider_label)
