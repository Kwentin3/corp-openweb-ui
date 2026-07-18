"""Public, versioned Gate 1 surface consumed by Gate 2.

Gate 2 must import source-representation validators and resolvers from this
module instead of depending on format-specific Gate 1 implementations.
"""

from .csv_profile import CSV_SUPPORTED_PROFILE_ID
from .domain_ingestion import (
    DOCUMENT_USAGE_CLASSIFICATION_SCHEMA_VERSION,
    DOMAIN_CONTEXT_PACKET_SCHEMA_VERSION,
    ISSUE_LEDGER_SCHEMA_VERSION,
)
from .document_memory import (
    DOCUMENT_MEMORY_SCHEMA_VERSION,
    SUPPORTED_PROFILE_ID,
    validate_document_memory_manifest,
)
from .full_source import SOURCE_UNIT_SCHEMA_VERSION, validate_full_source_unit
from .pdf_layout_units import resolve_pdf_layout_unit_source_value
from .pdf_text_layer import validate_pdf_source_unit
from .source_provenance import (
    NormalizedSliceProvenanceFactory,
    reproduce_normalized_value,
    resolve_source_value,
    resolve_source_values,
    validate_normalized_slice_provenance,
)
from .table_projection import TABLE_PROJECTION_SCHEMA_VERSION, TableProjectionValidator


FACTORY_REQUIRED = (
    "Gate 2 consumes Gate 1 source truth only through gate1_public_contracts "
    "and resolver-accessible artifact refs"
)
FORBIDDEN = (
    "Gate 2 must not import format parsers, source normalizer internals or "
    "Gate 1 storage implementation details"
)


__all__ = [
    "CSV_SUPPORTED_PROFILE_ID",
    "DOCUMENT_USAGE_CLASSIFICATION_SCHEMA_VERSION",
    "DOMAIN_CONTEXT_PACKET_SCHEMA_VERSION",
    "ISSUE_LEDGER_SCHEMA_VERSION",
    "DOCUMENT_MEMORY_SCHEMA_VERSION",
    "NormalizedSliceProvenanceFactory",
    "SOURCE_UNIT_SCHEMA_VERSION",
    "SUPPORTED_PROFILE_ID",
    "TABLE_PROJECTION_SCHEMA_VERSION",
    "TableProjectionValidator",
    "reproduce_normalized_value",
    "resolve_pdf_layout_unit_source_value",
    "resolve_source_value",
    "resolve_source_values",
    "validate_full_source_unit",
    "validate_document_memory_manifest",
    "validate_normalized_slice_provenance",
    "validate_pdf_source_unit",
]
