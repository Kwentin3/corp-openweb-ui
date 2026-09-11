"""Compatibility import for the Goal #391 R&D harness.

The maintained product contract lives in ``broker_reports_gate1``; the lab
keeps this tiny module only to retain its established import path.
"""
from broker_reports_gate1.instructional_table_classification import (
    INPUT_SCHEMA_VERSION,
    OUTPUT_SCHEMA_VERSION,
    PROMPT_CONTRACT_ID,
    PROMPT_PLACEHOLDER,
    InstructionalClassificationContractError,
    build_case,
    prompt_hash,
    response_format,
    validate_response,
)
