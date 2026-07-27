# Broker Reports — V6 qualification Goal 1 request-builder seam

Date: 2026-07-27  
Base revision: `2312b5565c32e0ff63f4f1a449010004d1632b9e`

## Result

| Acceptance item | Result |
| --- | --- |
| `CANONICAL_REQUEST_BUILDER` | `REUSED` |
| `PROMPT_CONTRACT_MISMATCH` | `ZERO_IN_CONTRACT_PROOF` |
| `PARALLEL_REQUEST_BUILDER` | `ZERO` |
| `PROVIDER_CALLS` | `ZERO` |
| New schemas/factories/adapters | `ZERO` |
| Stage mutations | `ZERO` |

`Gate2OpenWebUIRequestBuilder` is now the only implementation that constructs
the V6 provider request. The former
`financial_semantic_v6_canonical_request` entrypoint remains for compatibility
and evidence validation, but delegates directly to that builder instead of
maintaining a second request dictionary.

The already-existing exact V6 Prompt contract was separated into
`gate2_financial_semantic_v6_prompt.py`. This is a module-boundary move, not a
new schema or factory. Prompt content, version and SHA-256 identity are
unchanged.

Preflight and terminal qualification now create one exact Prompt object and
pass that same object to the canonical builder path. The builder additionally
fails closed when:

- Prompt content, version or pinned hash drifts;
- the four-block packet or its hash drifts;
- the strict response schema or its choice-schema hash drifts.

The built request takes the system message and metadata directly from the
validated Prompt object. The semantic packet is serialized into exactly one
user message, and the existing strict response format is attached unchanged.

## Verification

Focused V6 qualification, evidence and terminal-runner tests:

```text
30 passed
```

Structured model client and architecture tests:

```text
32 passed
```

Full Broker Reports service suite:

```text
1815 passed, 20 skipped
```

Targeted Ruff check:

```text
All checks passed!
```

No provider transport was invoked. Tokens, cost, fallback, repair and retries
are all zero. No customer bytes, provider output, response identifiers,
credentials or private paths were added to Git.

## Unchanged product contracts

Financial Semantic Pack meanings and projection, Evidence Bundle, Typed
Options, Candidate Compiler, four-block packet payload, minimal choice,
deterministic expansion, validator, materializer, Managed Domain, Domain API,
Gate 3 successor, technical preclose and the no-financial-regex invariant are
unchanged.

## Next permitted goal

Goal 2 may normalize usage inside the existing OpenAI and Anthropic adapters.
Provider calls remain forbidden.
