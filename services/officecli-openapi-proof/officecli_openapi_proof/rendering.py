"""Bounded native screenshots for the authors' render/look/fix workflow."""

from io import BytesIO
from typing import Literal

from PIL import Image
from pydantic import BaseModel, Field, model_validator

from .officecli import OfficeCliFailure


class RenderOfficeRequest(BaseModel):
    file_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9-]+$",
        description="Native source/result file ID to inspect visually; this operation does not modify it.")
    format: Literal["docx", "xlsx", "pptx"]
    page: int = Field(default=1, ge=1, le=1000,
        description="Single Word page or PowerPoint slide, 1-based. For XLSX use range to select a region; without range only the active sheet is shown.")
    range: str | None = Field(default=None, min_length=1, max_length=512,
        description="Native screenshot --range: a sheet-qualified cell range or an actual document element path. See installed view help.")
    grid: int | None = Field(default=None, ge=1, le=6,
        description="Native DOCX/PPTX --grid column count: render a contact sheet of all pages/slides. Use for whole-document pagination checks, then inspect details as needed. Cannot combine with range or a non-default page.")

    @model_validator(mode="after")
    def grid_scope(self):
        if self.grid is not None and (self.format == "xlsx" or self.range is not None or self.page != 1):
            raise ValueError("grid requires DOCX/PPTX, no range and default page; it covers the whole document")
        return self


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
