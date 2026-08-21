"""Research-only compatibility imports for the retired grid-provider name.

The product bundle imports ``pdf_table_locator_provider`` directly.  This shim
keeps standalone historical experiments reproducible without making them a
product fallback.
"""

from .pdf_table_locator_provider import (
    MAX_PROVIDER_RESPONSE_BYTES,
    PDF_GRID_PROVIDER_ADAPTER_VERSION,
    PdfGridExperimentProviderFactory,
    PdfGridProviderConfig,
    PdfGridProviderError,
    project_gemini_schema,
)


RUNTIME_STATUS = "research_compatibility_only"

__all__ = [
    "MAX_PROVIDER_RESPONSE_BYTES",
    "PDF_GRID_PROVIDER_ADAPTER_VERSION",
    "PdfGridExperimentProviderFactory",
    "PdfGridProviderConfig",
    "PdfGridProviderError",
    "project_gemini_schema",
]
