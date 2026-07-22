# Broker Reports Semantic Visual Table Validator v1

Status: `VERSIONED_AND_AUTHORITATIVE`

Validator identity: `semantic_visual_table_validator_v1`

## Purpose

This contract defines one bounded deterministic validator for
`broker_reports_semantic_table_transcription_v1`. It validates the response
contract; it does not prove that a VLM transcribed every visible source value
correctly.

`SemanticVisualTableValidatorFactory.create` is the only maintained validator
entrypoint.

## Strict checks

The validator requires:

- one valid JSON object and no explanation, comment, or Markdown fence outside
  that object;
- exact equality between the raw JSON text and the parsed response object;
- exactly the root fields `description` and `rows`;
- a string description of at most 120 deterministic tokens and 2,048
  characters;
- at least one row and no more than 200 rows;
- every row to be a non-empty array of at most 200 cells;
- every cell to be a string or `null`;
- no nested object or array in a cell;
- at most 12,000 characters in a cell string.

Description tokens use `unicode_word_or_punctuation_v1`: every Unicode word or
standalone punctuation mark counts as one token. This versioned local policy is
a deterministic contract budget, not a claim about provider tokenizer billing.

## No repair and no geometry

The validator does not strip code fences, extract a JSON substring, coerce
numbers to strings, flatten nested cells, pad rows, normalize text, retry a
provider, or merge providers. Invalid output remains a terminal schema
violation.

The validator does not require or inspect row spans, column spans, merged-cell
coverage, bounding boxes, physical positions, source coordinates, or review
receipts.

## Envelope binding

At the private envelope layer, the parsed semantic response and exact raw JSON
text are bound to the selected execution, provider response hash, immutable crop
hash, and decision ID. Missing, duplicated, changed, or hash-invalid evidence
fails closed before materialization.

## Acceptance meaning

A passing result means only:

`semantic_response_contract_passed = true`

Every validation result explicitly records:

- `hidden_repair_performed = false`;
- `geometric_validation_performed = false`;
- `human_review_required = false`;
- `source_content_correctness_claimed = false`;
- `financial_correctness_claimed = false`.

Literal and amount fidelity are measured separately against sealed source-only
references in the qualification goals.
