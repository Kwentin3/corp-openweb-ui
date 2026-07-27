# Broker Reports — V6 qualification Goal 2 usage normalization

Date: 2026-07-27  
Base revision: `ad6d8c3f2d61a282a85356210b24205600e94070`

## Result

| Acceptance item | Result |
| --- | --- |
| `OPENAI_USAGE` | `NORMALIZED` |
| `ANTHROPIC_USAGE` | `NORMALIZED` |
| `TOTAL_TOKENS_PROVIDER_REQUIREMENT` | `OPTIONAL` |
| `PROVIDER_SPECIFIC_LOGIC_IN_HARNESS` | `ZERO` |
| `PROVIDER_CALLS` | `ZERO` |
| New DTOs/adapters | `ZERO` |
| Stage mutations | `ZERO` |

The existing OpenAI and Anthropic adapters continue to own provider response
and usage interpretation. Both now normalize input and output tokens first.
When `total_tokens` is absent and both components are available, the adapter
derives the canonical aggregate as:

```text
input_tokens + output_tokens
```

A provider-supplied valid aggregate remains authoritative. A malformed
reported aggregate is not masked. If either component is unavailable, the
canonical aggregate remains `None`, preserving the existing optional
`Gate2ProviderExecutionMetadata.total_tokens` contract.

The V6 qualification runner contains no OpenAI or Anthropic field lookup.

## Captured-shape proof

Adapter-path fixtures prove:

| Provider shape | Input | Output | Reported total | Canonical total |
| --- | ---: | ---: | ---: | ---: |
| OpenAI chat completion | 23 | 4 | absent | 27 |
| Anthropic native message | 29 | 6 | absent | 35 |
| OpenAI incomplete usage | 11 | absent | absent | `None` |

The fixtures also retain provider request/response identity and nonnegative
duration metadata.

## Verification

```text
Provider/model-client tests: 23 passed
Budget, V6 execution-identity and runner tests: 46 passed
Full service suite: 1817 passed, 20 skipped
Targeted Ruff: All checks passed
```

No provider transport was invoked. Tokens and cost incurred by this Goal are
zero. Fallback, repair and retry counts are zero. No customer bytes, raw
provider output, real provider response identifiers, credentials or private
paths were added to Git.

## Unchanged contracts

Canonical usage DTO fields and schema version, provider profiles, provider
transport, request builder, V6 Prompt/packet/choice, expansion,
validator/materializer, product scorer, Managed Domain, Domain API and stage
Action remain unchanged.

## Next permitted goal

Goal 3 may separate existing budget pre-call admission from non-destructive
post-call actual accounting. Provider calls remain forbidden.
