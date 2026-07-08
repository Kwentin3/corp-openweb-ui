from __future__ import annotations

import struct

from .blockers import raster_requires_review
from .contracts import profile_id


def profile_image(run_id: str, document_id: str, content_bytes: bytes) -> tuple[dict, list[dict], list[dict]]:
    width, height, image_format = _image_size(content_bytes)
    blocker = raster_requires_review(run_id, document_id)
    profile = {
        "profile_id": profile_id(document_id),
        "document_id": document_id,
        "container_format": "image",
        "parser": "python_stdlib_image_header",
        "parser_version": "1",
        "profile_status": "profiled_with_review",
        "machine_readable": "no",
        "machine_readable_table": False,
        "image_format": image_format,
        "width_px": width,
        "height_px": height,
        "metadata_available": width is not None and height is not None,
        "ocr_performed": False,
        "normalized_slice_refs": [],
        "warnings": ["image_requires_ocr_or_review"],
        "blocker_refs": [blocker["blocker_id"]],
    }
    return profile, [], [blocker]


def _image_size(content_bytes: bytes) -> tuple[int | None, int | None, str]:
    if content_bytes.startswith(b"\x89PNG\r\n\x1a\n") and len(content_bytes) >= 24:
        width, height = struct.unpack(">II", content_bytes[16:24])
        return int(width), int(height), "png"
    if content_bytes.startswith(b"\xff\xd8"):
        index = 2
        while index + 9 < len(content_bytes):
            if content_bytes[index] != 0xFF:
                index += 1
                continue
            marker = content_bytes[index + 1]
            block_length = int.from_bytes(content_bytes[index + 2 : index + 4], "big")
            if marker in {0xC0, 0xC2} and index + 8 < len(content_bytes):
                height = int.from_bytes(content_bytes[index + 5 : index + 7], "big")
                width = int.from_bytes(content_bytes[index + 7 : index + 9], "big")
                return width, height, "jpeg"
            if block_length <= 0:
                break
            index += 2 + block_length
    return None, None, "unknown"
