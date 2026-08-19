# Broker Reports LLM Metadata Adapter Proof v1

Status: `FROZEN_FOR_G5_61_PROOF`

## Boundary

G5.61 проверяет только один общий LLM-adapter над неизменным `BROKER_REPORTS_MINIMAL_PERSON_DOCUMENT_METADATA` `1.0.0`. Текущий deterministic owner G5.60 не удаляется, не расширяет vocabulary и остаётся production authority до положительного terminal.

Разрешены ровно 11 физических source-fact types:

```text
PARTY_NAME
PERSON_BIRTH_DATE
TAXPAYER_TAX_IDENTIFIER
PERSON_CITIZENSHIP
DOCUMENT_TYPE
DOCUMENT_NUMBER
DOCUMENT_DATE
STATEMENT_PERIOD
BROKER_LEGAL_NAME
ACCOUNT_IDENTIFIER
ACCOUNT_CONTRACT_IDENTIFIER
```

Новые поля, tax meaning, residency inference, generic extraction, новая persistence и Gate 3/Gate 4 unification запрещены.

## Frozen corpus and oracle

Corpus зафиксирован до implementation:

| Safe alias | G5.60 oracle facts | Oracle type counts |
|---|---:|---|
| `pdf_002` | 8 | `PARTY_NAME=1`, `DOCUMENT_TYPE=1`, `DOCUMENT_DATE=1`, `STATEMENT_PERIOD=3`, `BROKER_LEGAL_NAME=1`, `ACCOUNT_IDENTIFIER=1` |
| `pdf_024` | 5 | `PARTY_NAME=1`, `DOCUMENT_TYPE=1`, `DOCUMENT_DATE=1`, `ACCOUNT_IDENTIFIER=1`, `ACCOUNT_CONTRACT_IDENTIFIER=1` |
| `holdout_a` | 3 | `PARTY_NAME=1`, `DOCUMENT_TYPE=1`, `STATEMENT_PERIOD=1` |
| `holdout_b` | 5 | `DOCUMENT_TYPE=1`, `STATEMENT_PERIOD=1`, `ACCOUNT_IDENTIFIER=3` |

Private artifact identities, source hashes, values and full oracle remain outside Git. No additional holdout is added: the four frozen documents already cover text assertions, adjacent label/value cells, header-to-many-values and multiple periods.

## One frozen instruction

Instruction version: `1.0.0`.

```text
You are the single Broker Reports Minimal Person and Document Metadata adapter for contract 1.0.0.

You receive opaque Canonical region aliases with source text or small table rows. Extract only explicit source assertions for the 11 allowed fact types. Decide the fact type from the human meaning of the supplied region, never from value shape alone.

PARTY_NAME is the natural person who is explicitly the report or account subject. PERSON_BIRTH_DATE, TAXPAYER_TAX_IDENTIFIER and PERSON_CITIZENSHIP require an explicit assertion about that person. DOCUMENT_TYPE, DOCUMENT_NUMBER and DOCUMENT_DATE describe the current report itself, not an operation, contract or identity document mentioned inside it. STATEMENT_PERIOD requires both explicit source boundaries. BROKER_LEGAL_NAME is the legal entity explicitly acting as the report issuer or broker, not any company mention. ACCOUNT_IDENTIFIER and ACCOUNT_CONTRACT_IDENTIFIER must follow their explicit account or contract meaning.

For each fact, copy only the exact value text into source_literal and select exactly one supplied source_target_alias that contains it. For STATEMENT_PERIOD also copy the exact start and end boundary literals. Preserve every independent account identifier and every independent statement period. Do not infer, complete, translate, repair, reconcile or add unsupported metadata. Citizenship never means tax residency. If evidence is absent or ambiguous, omit the fact; an empty facts array is valid.

Return only broker_reports_llm_metadata_proposal_v1 under the strict response schema.
```

Эта instruction одинакова для каждого документа. Broker-specific prompts, examples, few-shot snippets and synonym lists: `0`.

## One model-visible package

Context policy version: `broker_reports_metadata_context_policy_v1`.

Canonical остаётся физическим owner. Packager не ищет human-language labels и не знает oracle. В document order он формирует:

1. `TEXT_HEAD`: до 24 первых непустых строк каждого `TEXT` node, до 3,000 characters;
2. `SMALL_TABLE_ROW`: только `TABLE` с не более чем 64 непустыми cells; один target содержит первую structural row и одну текущую row, до 16 rows и до 3,000 characters;
3. общий лимит: 96 targets и 32,768 rendered characters.

В LLM видны только `target_alias`, `region_kind` и `content`. Canonical document/version/node/path/source refs хранятся в локальном binding registry и не выбираются моделью.

До implementation read-only projection покрыла все 21 G5.60 oracle facts. Frozen measurements: `pdf_002=18 targets/14945 chars`, `pdf_024=6/7440`, `holdout_a=59/9273`, `holdout_b=14/1686`. Truncation-induced oracle loss: `0`.

Selection не содержит broker name, page number, fixed column, field keyword, regex или synonym branch.

## One proposal schema and validator

Output schema version: `broker_reports_llm_metadata_proposal_v1`.

```json
{
  "schema_version": "broker_reports_llm_metadata_proposal_v1",
  "facts": [
    {
      "fact_type": "one of the frozen 11 fact types",
      "source_target_alias": "one opaque alias from this package",
      "source_literal": "exact non-empty substring of target content",
      "period_start_literal": "exact boundary literal or null",
      "period_end_literal": "exact boundary literal or null"
    }
  ]
}
```

Один deterministic validator для всех документов обязан fail closed проверить:

- exact schema and allowed fact type;
- alias exists exactly once in this document package;
- binding registry belongs to the requested document and Canonical version;
- `source_literal` is an exact target substring;
- period boundaries are both present, exact target substrings and parse to dates only for `STATEMENT_PERIOD`;
- non-period facts have null period boundaries;
- Canonical node, field paths and non-empty source refs exist;
- duplicate semantic assertions are rejected, not voted or reconciled.

Validated output uses the existing G5.60 normalized source-fact schema. Validator does not assign tax meaning.

## Execution and decision

Frozen provider policy for the four-document proof:

```text
provider_profile = google_gemini
model_id = models/gemini-3.5-flash
provider_attempts_per_document = 1
retry = 0
best_of_n = false
manual_output_repair = false
```

The request must pass through `Gate2StructuredModelClientFactory`; direct provider/OpenWebUI completion assembly is forbidden. Same contract, instruction, context policy, schema and validator apply to all four documents.

Semantic/provenance acceptance requires exact comparison with the frozen private G5.60 oracle and visual qualification. A single wrong type, invented/missing fact, invalid binding or duplicate produces an honest negative G5.61 terminal. No regex, synonym or per-document repair is allowed after execution.

If and only if all four single-attempt results pass, the LLM adapter may become the KISS primary candidate. This GOAL does not activate product runtime. Otherwise G5.60 remains authority and the exact failure class is reported.
