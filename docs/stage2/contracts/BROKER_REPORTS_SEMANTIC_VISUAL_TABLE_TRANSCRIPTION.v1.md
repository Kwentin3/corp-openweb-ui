# Broker Reports Semantic Visual Table Transcription v1

Status: `VERSIONED_AND_AUTHORITATIVE`

Contract identity: `broker_reports_semantic_table_transcription_v1`

Architecture authority:
[Broker Reports Global Gate Architecture](../blueprints/BROKER_REPORTS_GATE_ARCHITECTURE.md).

## 1. Purpose

This is the single model-facing response contract for new Broker Reports
visual-table extraction. It describes semantic transcription of source-visible
content, not reconstruction of physical PDF or raster geometry.

The contract changes one boundary inside the maintained pipeline. It does not
create another VLM provider stack, raster pipeline, storage system, review
framework, or downstream financial interpreter.

## 2. Model response

The VLM returns exactly one JSON object:

```json
{
  "description": "short source-oriented description",
  "rows": [
    ["visible text", null, "visible text"]
  ]
}
```

The root fields are exactly `description` and `rows`.

### `description`

- is a short observation about the visible table;
- has a maximum budget of 120 tokens;
- is counted deterministically with the versioned
  `unicode_word_or_punctuation_v1` policy and has a 2,048-character hard guard;
- may identify the table subject, visible sections, ambiguous layout, or
  unreadable material;
- must not calculate, interpret financially, or repeat the entire table.

### `rows`

- preserves logical row order;
- contains one array per logical row;
- contains only strings or `null` cells;
- uses `null` when no visible text exists in a logical position;
- preserves all values as strings;
- preserves source spelling, labels, amounts, currency signs, parentheses,
  percentage signs, signs, and separators literally;
- may collapse multi-line text inside one logical cell to one space;
- uses the minimum logical column count needed to preserve label/value binding;
- does not create columns from indentation, visual whitespace, or decorative
  bands;
- may represent a section row as one visible string followed by `null` cells;
- includes only source-visible text and no inferred or editorial headers;
- contains no explanations inside cells.

## 3. Forbidden model responsibility

The model response must not contain:

- schema, table, document, artifact, page, crop, provider, model, prompt, or
  hash metadata;
- row or column indexes;
- row or column spans;
- bounding boxes, coordinates, or physical grid dimensions;
- cell identity or `content_state`;
- a claim of full physical slot coverage;
- Markdown;
- comments or explanations outside the JSON object.

The VLM does not classify financial meaning. Financial interpretation remains
in global Gate 2.

## 4. Deterministic ownership

Deterministic application code owns:

- table and source identity;
- page and crop lineage;
- provider and model identity;
- prompt/schema/request/response hashes;
- token, latency, and terminal metadata;
- strict parsing and validation;
- logical row and column indexes;
- padding shorter rows with explicit logical `null` cells;
- span-1 logical cell materialization;
- integrity, persistence, terminal state, and packaging.

A materialized logical table must declare semantic VLM transcription as its
origin. It must not claim to prove the physical PDF topology.

## 5. Provider policy

- Gemini (`google_gemini`) is the master visual-table extractor.
- OpenAI (`openai_gpt`) is an optional control or explicit versioned fallback.
- A valid Gemini result does not trigger an OpenAI call merely for consensus.
- Provider agreement is not required for success.
- OpenAI output cannot silently repair, merge with, overwrite, or impersonate a
  Gemini result.
- Malformed or invalid output remains a visible terminal failure; code does not
  semantically repair provider content.

## 6. Runtime exclusions

- Markdown is not an intermediate or parser dependency.
- PaddleOCR, PaddleOCR-VL, PaddlePaddle, Torch, and comparable heavy local OCR
  are outside production scope.
- Human review is an exception for unsupported or review-required layouts, not
  a mandatory dependency for a future accepted semantic profile.

This contract authority does not activate a runtime profile. Prompt/provider
boundary migration, deterministic materialization, validation, qualification,
downstream migration, and release remain separately gated changes.

## 7. Legacy disposition

`broker_reports_canonical_table_v1` remains readable for historical evidence
and existing immutable artifacts. It is not the default model-facing contract
for new semantic visual-table extraction. Existing evidence is not deleted,
rewritten, or silently upgraded.

## 8. Acceptance meaning

Schema validity means only that the semantic response contract passed. It is
not proof of literal, visual, financial, or tax correctness. Content-fidelity
qualification remains a separate evidence gate.

The maintained validator contract is
`BROKER_REPORTS_SEMANTIC_VISUAL_TABLE_VALIDATOR.v1.md`.
