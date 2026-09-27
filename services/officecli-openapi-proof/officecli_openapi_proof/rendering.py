"""Bounded native screenshots for the authors' render/look/fix workflow."""

from io import BytesIO
from typing import Literal

from PIL import Image
from pydantic import BaseModel, Field

from .officecli import OfficeCliFailure


class RenderOfficeRequest(BaseModel):
    file_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9-]+$",
        description="Native source/result file ID to inspect visually; this operation does not modify it.")
    format: Literal["docx", "xlsx", "pptx"]
    page: int = Field(default=1, ge=1, le=1000,
        description="Single Word page or PowerPoint slide, 1-based. XLSX screenshots show only the active sheet: they do not verify all sheets.")


def checked_png(data: bytes) -> bytes:
    if not data or len(data) > 8 * 1024 * 1024:
        raise OfficeCliFailure("Screenshot is empty or exceeds the 8 MiB limit")
    try:
        with Image.open(BytesIO(data)) as image:
            if image.format != "PNG" or image.width * image.height > 8_000_000:
                raise OfficeCliFailure("Screenshot is not a bounded PNG")
            image.verify()
    except (OSError, ValueError) as error:
        raise OfficeCliFailure("Screenshot is not a valid PNG") from error
    return data
