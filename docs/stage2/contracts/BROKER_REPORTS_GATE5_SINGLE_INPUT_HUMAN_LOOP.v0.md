# Broker Reports Gate 5 Single-Input Human Loop v0

Status: `EXPERIMENTAL_G5_6_CONTRACT`

Goal status: `G5.6_CLOSED`

Proof outcome: `PROVEN`

Product status: `INACTIVE`

Date: 2026-08-09

## Purpose

This contract defines one bounded conversational adapter for one missing money
input. Both LLM turns use strict structured output. The model remains a
proposal source; deterministic code owns validation and G5.3 persistence.

```text
G5.5 one missing requirement
-> strict structured question
-> one human answer
-> strict structured proposal
-> deterministic validation
-> unchanged G5.3 put
-> unchanged G5.5 recheck
```

## Ownership

| Concern | Owner |
| --- | --- |
| missing/satisfied state | unchanged `Gate5SupplementalFactDiscoveryRuntime.check` |
| structured model/provider execution | existing `Gate2StructuredModelClientFactory.create` and provider adapter factory |
| one question/proposal interaction and deterministic proposal validation | `Gate5SingleInputHumanLoopRuntimeFactory.create` |
| trusted supplemental persistence | unchanged `Gate5SupplementalFactRuntime.put` |
| conversation rendering/input collection | existing OpenWebUI surface; not activated by G5.6 |

The runtime accepts an existing structured model client. It does not create a
second provider stack or allow the LLM to access ArtifactStore.

## Runtime calls

```python
question = await runtime.ask(
    methodology=<broker_reports_gate5_combined_requirements_v0>,
    context=<trusted ArtifactAccessContext>,
)

result = await runtime.submit(
    methodology=<same requirement>,
    human_answer="Покупал за 70 000 рублей",
    context=<same trusted ArtifactAccessContext>,
)
```

Both calls rerun G5.5 and require exactly one currently missing requirement.
No workflow or interview state is persisted.

## Exact minimal model-visible task payload

Question phase:

```json
{
  "phase": "ask",
  "missing_input": {
    "financial_type": "SECURITY_DISPOSAL",
    "value_key": "acquisition_cost",
    "value_kind": "money",
    "currency_required": true
  }
}
```

Interpretation phase adds only the human answer:

```json
{
  "phase": "interpret",
  "missing_input": {
    "financial_type": "SECURITY_DISPOSAL",
    "value_key": "acquisition_cost",
    "value_kind": "money",
    "currency_required": true
  },
  "human_answer": "Покупал за 70 000 рублей"
}
```

The model does not receive case/user/run/workspace identity, methodology,
Financial Case facts, G5.5 checks/summary, supplemental refs, persisted facts,
provenance or ArtifactStore metadata.

Each retained field is required for this representative task:

- `financial_type` identifies the kind of object/event;
- `value_key` identifies the missing meaning;
- `value_kind` constrains the expected value;
- `currency_required` makes currency explicit;
- `human_answer` is required only for interpretation.

Opaque `requirement_id` and `subject_ref` are intentionally withheld. The
deterministic runtime retains them for the later G5.3 binding.

## Structured question output

The first LLM call is constrained by a closed strict JSON Schema:

```json
{
  "schema_version": "broker_reports_gate5_single_input_question_v0",
  "action": "ask_user",
  "question_text": "Укажите стоимость приобретения ценной бумаги для текущего выбытия, сумму и валюту."
}
```

Free-form model text is not accepted as the runtime result.

## Structured proposal output

The second LLM call is constrained by a separate closed strict JSON Schema:

```json
{
  "schema_version": "broker_reports_gate5_single_input_proposal_v0",
  "action": "propose_fact",
  "amount": "70000.00",
  "currency": "RUB"
}
```

For an insufficient or ambiguous answer the model may return:

```json
{
  "schema_version": "broker_reports_gate5_single_input_proposal_v0",
  "action": "needs_clarification",
  "amount": null,
  "currency": null
}
```

## Deterministic validation before persistence

The runtime accepts a proposal only when:

1. the provider result reports strict JSON Schema mode with no fallback;
2. the proposal is a closed object with the exact schema/action;
3. `amount` and `currency` satisfy the bounded money contract;
4. the human answer contains exactly one deterministic money amount and one
   currency meaning;
5. normalized answer evidence equals the proposed amount/currency.

The LLM never supplies `requirement_ref`, `subject_ref`, `fact_key` or trusted
scope. Ordinary code takes these only from the current G5.5 missing result and
`ArtifactAccessContext`.

Rejected/ambiguous input does not call G5.3 and leaves G5.5 `missing`.

## Existing model/provider path

G5.6 adds one bounded request profile to the existing request builder. Runtime
execution remains:

```text
Gate2StructuredModelClientFactory.create
-> Gate2OpenWebUIRequestBuilder
-> Gate2ProviderAdapterFactory.create
-> OpenWebUI completion boundary
-> Gate2StructuredModelResult
```

The response format is strict JSON Schema in both phases. No provider SDK,
HTTP call or response parser is added to Gate 5.

## Fail-closed boundary

- zero or more than one missing requirements are rejected;
- empty/oversized human answers are rejected before a model call;
- free-form, fallback, malformed or mismatched model output is not persisted;
- multiple numeric values or currency meanings in the human answer are
  ambiguous and not persisted even if the model proposes one value;
- G5.3 and G5.5 access/lifecycle/run rules remain unchanged;
- provider/G5.3/G5.5 failures pass through without fabricated success.

## Representative acceptance

The proof must show:

1. G5.5 initially returns one missing `acquisition_cost`;
2. the first strict model result contains one understandable question;
3. actual captured model-visible payload equals the minimal projection above;
4. the delegated human answer is `Покупал за 70 000 рублей`;
5. the second strict model result proposes `70000.00 RUB`;
6. deterministic validation passes before the irreversible G5.3 write;
7. G5.3 persists one fact and G5.5 returns `satisfied`;
8. a new store/runtime sees the same persistent result;
9. an ambiguous two-amount answer creates no supplemental fact and remains
   `missing`;
10. Gate 4 is unchanged.

## KISS and stop condition

G5.6 may add one orchestration adapter, one bounded existing-client request
profile, two strict output schemas, one closed contract and focused tests. It
must not add a TaxInterviewEngine, registry, workflow, TaxAgent, PromptEngine,
Tax Case, provider abstraction, DB/table, multi-input interview, cross-run
framework, tax calculation or subsequent Gate 5 slice.

The exact-boundary representative tests and one live approved-provider
adequacy run passed. `G5.6_CLOSED`; the product route remains inactive.
