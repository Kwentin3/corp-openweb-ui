# Broker Reports Gate 2 — Context V2.1 GOAL 12 budget smoke

- Status: `completed`
- Plan: `9191197bdc947d6ba86db3169ba0d8c911ef88423d611e2c4424a9379167cbab`
- Provider submissions: `8` of maximum `12`
- Retry / repair / fallback: `0 / 0 / 0`
- Context V2.1 active: `false`
- Production admissions: `[]`

## Provider verdicts

| Provider | Exact model/selector | Technical | Semantic | Benchmark admission |
|---|---|---|---|---|
| openai_gpt | `gpt-5.4-nano-2026-03-17` | `TECHNICAL_SMOKE_PASSED` | `SEMANTIC_SMOKE_FAILED` | `false` |
| anthropic_claude | `claude-haiku-4-5-20251001` | `TECHNICAL_SMOKE_PASSED` | `SEMANTIC_SMOKE_FAILED` | `false` |
| google_gemini | `models/gemini-3.1-flash-lite` | `TECHNICAL_SMOKE_FAILED` | `SEMANTIC_SMOKE_FAILED` | `false` |

## Evidence

The adjacent transparent JSON contains every exact synthetic final request, system message, user content, provider-visible schema, adapter-extracted output, normalized answer, audited expected answer, field-level diff, tokens, cost and latency.
Raw provider envelopes and response identifiers are retained only in hash-linked private evidence outside Git.
Google remained uncalled because the published `models/gemini-3.1-flash-lite` value is a stable selector, not a proven dated immutable model ID.

Safe receipt: `0a000d3bbec1a3cf9e5c50c1f6c7401181c217d7f35b7643d6a34e163a9b6a93`.
