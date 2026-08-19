# Broker Reports Frozen LLM Semantic Reliability Benchmark v1

Статус: measurement-only contract G5.69. Не является product activation.

## Назначение

Контракт измеряет повторяемость semantic output одной модели на побитово одинаковом model-visible request. Он не разрешает улучшение prompt, pipeline, validator или runtime voting.

## Frozen boundary

- metadata contract: `1.0.0`, ровно 11 типов;
- instruction: `1.2.0`, SHA-256 `dd18bcc17c69fd111d29e2bbde4f8aaf6058bfac51b9c9506de25d516ca58d67`;
- context policy: `broker_reports_metadata_context_policy_v4`;
- context schema: `broker_reports_llm_metadata_context_v2`;
- binding registry: `broker_reports_llm_metadata_binding_registry_v2`;
- proposal schema: `broker_reports_llm_metadata_proposal_v2`, SHA-256 `524e8fb2b3b55fb55af3d62fe7465f147f7ad6da18ad9c9cca5b68ecf458ac29`;
- production model parameters, source binding, role/value validation, Gate 4 and Gate 5 unchanged.

Production semantic changes are forbidden. A private benchmark harness may only freeze requests, invoke the existing factories, journal independent outcomes and qualify them offline.

## Frozen cases and request identity

Exactly two cases are selected before semantic calls:

- `case_f`: known `CLIENT_CODE -> ACCOUNT_IDENTIFIER` diagnostic failure;
- `case_c`: clean minimal G5.68 control.

The request fingerprint covers the exact model-visible messages, strict JSON schema and effective model parameters. Every run of a case must have the same fingerprint. Timestamp, run id and benchmark metadata must not enter the model-visible payload.

## Execution law

Gemini `models/gemini-3.5-flash` receives five independent single-shot executions per case. Every semantic result is retained. Retry, best-of-N, voting, judge, output repair and result selection are forbidden.

One stronger model is selected before any G5.69 semantic result and may run only through the same `Gate3LlmMetadataAdapterFactory` and `Gate2StructuredModelClientFactory` route with the same instruction, context and strict schema. If that exact model cannot pass the frozen one-shot contract, the required terminal is:

```text
COMPARISON_MODEL_NOT_AVAILABLE_ON_SAME_CONTRACT
```

Schema weakening, direct provider transport, a new adapter and replacement-model roulette are forbidden.

## Qualification

Each run is compared independently with the frozen oracle. Qualification records:

- correct and missed facts;
- semantic extras and wrong roles;
- wrong value boundaries and structural rejections;
- invented literals, invalid provenance and duplicates;
- normalized semantic-set hash and per-fact frequency;
- transport failure separately from semantic result.

Classification per case:

- `STABLE_CORRECT`: one identical correct semantic set in all five runs;
- `STABLE_WRONG`: one identical wrong semantic set in all five runs;
- `STOCHASTIC`: materially different semantic sets across runs.

The benchmark does not authorize multi-run production inference.

## Optional full corpus

One full-corpus single shot is allowed only if the frozen stronger model first proves clearly better and stable behavior on both cases. Otherwise it is not authorized.

## G5.69 terminal boundary

```text
LLM_METADATA_REPEATABILITY_BENCHMARK_COMPLETE
SAME_INPUT_OUTPUT_VARIANCE_MEASURED
NO_BENCHMARK_RESULT_SELECTION
COMPARISON_MODEL_NOT_AVAILABLE_ON_SAME_CONTRACT
FLASH_SINGLE_SHOT_STOCHASTIC
FINANCIAL_GENERALIZATION_PRESERVED
```

`MODEL_CAPABILITY_COMPARISON_COMPLETE` is not declared when the comparison model is stopped before the provider boundary. No claim about a stronger model's semantic quality follows from such a stop.
