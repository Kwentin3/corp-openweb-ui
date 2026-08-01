# Broker Reports DOC4 Semantic Response v1

Status: `CONTRACTED_INACTIVE_EXPERIMENT_ONLY`

Schema: `broker_reports_doc4_semantic_response_v1`

Owner: the sole validator in `pdf_view_semantic_contracts.py`.

This contract is the identical semantic output boundary for the native-PDF and complete-LLM-View arms. It is not a product prompt, extraction authority, canonical financial record, or Gate 2 admission.

The root contains exactly `schema_version`, `source_mode`, `document_passport`, `document_structure`, `tables`, `financial_facts`, `uncertainties`, and `source_quality`. All objects are closed. The passport contains all nine fields in contract order. UNKNOWN and NOT_APPLICABLE are explicit and never represented by omission.

PRESENT requires a source literal or normalized value and at least one valid pointer. Critical PRESENT/CONFLICTING values without evidence fail closed. PDF pointers require a 1-based page and an exact excerpt of at most 160 characters. LLM_VIEW pointers require a block ID and an anchor used by that block; every financial fact requires table coordinates that resolve to the exact existing cell containing its source literal. Pointer modes cannot be mixed.

Numeric and date normalization is literal-bound. No calculation, rounding, sign inference, currency conversion, row merging, outside classification, chain-of-thought, free-form report, tool result, web fact, or loss-ledger-derived financial fact is allowed.

The normative machine authority is [BROKER_REPORTS_DOC4_SEMANTIC_RESPONSE.v1.schema.json](./BROKER_REPORTS_DOC4_SEMANTIC_RESPONSE.v1.schema.json).
