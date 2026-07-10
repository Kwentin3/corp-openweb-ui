# Broker Reports Gate 1 LLM Passport Structured Output Research

Date: 2026-07-09

Scope: Gate 1 `document_metadata_passport_v0` only. No Gate 2 execution, source fact extraction, tax calculation, declaration generation, XLS generation, OCR/VLM, Knowledge loading, RAG, or ordinary upload processing.

## Runtime Findings

OpenWebUI path checked on the live runtime:

- `generate_chat_completion` accepts `form_data` and forwards provider payloads.
- OpenAI-compatible router allowlist includes `response_format`.
- OpenWebUI payload utilities preserve OpenAI-compatible `response_format` and can map schema payloads to Ollama `format` when relevant.

Live minimal structured-output probes:

| Model | Result |
| --- | --- |
| `gpt-5.4-mini-2026-03-17` | HTTP 200, JSON object matched the requested schema keys |
| `claude-sonnet-5` | HTTP 200, JSON object matched the requested schema keys |
| `claude-sonnet-4-6` | HTTP 200, JSON object matched the requested schema keys |
| `deepseek-v4-pro` | HTTP 400, not usable for this structured-output path |

Selected runtime model for proof: `gpt-5.4-mini-2026-03-17`.

## Decision

Use native OpenWebUI/provider structured output first:

1. Send `response_format.type=json_schema` with schema name `document_metadata_passport_v0`.
2. Record schema id/hash on prompt snapshot, packages, raw outputs, validation artifacts, and ArtifactStore safe metadata.
3. Keep the existing strict validator as final authority.
4. If the provider rejects native schema mode, fall back to `response_format.type=json_object`.
5. If validator fails, perform one bounded repair attempt using only safe validator error summary plus an explicit allowed evidence-ref whitelist.
6. Fail closed if validation still fails.

The implementation intentionally does not relax validator rules and does not auto-correct passports after model output.

## Proof Boundary

Synthetic proof must pass before customer case proof. The customer case proof may still be blocked for Gate 2 readiness or specialist review; that is not a structured-output failure when passport validation passes.
